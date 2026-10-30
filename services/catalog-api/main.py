import logging
import os
import secrets
import time
from collections.abc import Callable
from copy import deepcopy
from threading import RLock
from typing import Annotated, Literal
from uuid import UUID, uuid4

from celery.exceptions import CeleryError
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from kombu.exceptions import OperationalError
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

import storage
from celery_app import celery_app, import_menu

Country = Literal["CO", "US"]
Family = Literal["menu", "locations"]
CacheKey = tuple[Family, Country | None]
CacheValue = list[dict[str, object]]

MENU_TTL = 60
LOCATIONS_TTL = 300
logger = logging.getLogger("api.timing")
app = FastAPI(title="Brasaland public catalog (demo)")
bearer = HTTPBearer(auto_error=False)


class MenuItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    country: Country
    price: float = Field(ge=0, allow_inf_nan=False)
    available: bool = True


class Location(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    country: Country
    city: str = Field(min_length=1, max_length=120)


class MenuUpdate(MenuItem):
    id: str = Field(min_length=1, max_length=120)


class MenuBatch(BaseModel):
    items: list[MenuUpdate] = Field(min_length=1, max_length=1000)


class PublicCatalog:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.lock = RLock()
        self.entries: dict[CacheKey, tuple[float, CacheValue]] = {}
        self.versions: dict[str, int] = {}
        self.menu: CacheValue = [
            {"id": "demo-co", "name": "Pollo a la brasa (demo)", "country": "CO", "price": 32000.0, "available": True},
            {"id": "demo-us", "name": "Grilled chicken (demo)", "country": "US", "price": 18.0, "available": True},
        ]
        self.locations: CacheValue = [
            {"id": "demo-med", "name": "Brasaland Medellin (demo)", "country": "CO", "city": "Medellin"},
            {"id": "demo-mia", "name": "Brasaland Florida (demo)", "country": "US", "city": "Miami"},
        ]

    def load(self, family: Family, country: Country | None) -> CacheValue:
        rows = self.menu if family == "menu" else self.locations
        result = [deepcopy(row) for row in rows if country is None or row["country"] == country]
        if family == "menu":
            for row in result:
                row["currency"] = "COP" if row["country"] == "CO" else "USD"
        return sorted(result, key=lambda row: str(row["name"]))

    def read(self, family: Family, country: Country | None) -> tuple[CacheValue, bool]:
        with self.lock:
            self.sync()
            now = self.clock()
            self.entries = {key: entry for key, entry in self.entries.items() if entry[0] > now}
            key = (family, country)
            if key in self.entries:
                return deepcopy(self.entries[key][1]), True
            result = self.load(family, country)
            ttl = MENU_TTL if family == "menu" else LOCATIONS_TTL
            self.entries[key] = (self.clock() + ttl, deepcopy(result))
            return result, False

    def sync(self):
        versions, updates = storage.catalog_snapshot()
        changed = {family for family in versions if versions[family] != self.versions.get(family)}
        for family, value in updates:
            if family in changed:
                rows = self.menu if family == "menu" else self.locations
                for index, row in enumerate(rows):
                    if row["id"] == value["id"]:
                        rows[index] = value
        self.entries = {key: entry for key, entry in self.entries.items() if key[0] not in changed}
        self.versions = versions

    def update_many(self, family: Family, values: CacheValue, task_id: str | None = None):
        with self.lock:
            rows = self.menu if family == "menu" else self.locations
            known_ids = {row["id"] for row in rows}
            if any(value["id"] not in known_ids for value in values):
                raise ValueError("Item not found")
            result = storage.save_updates([(family, value) for value in values], task_id)
            self.sync()
            return result

    def update(self, family: Family, item_id: str, value: dict[str, object]) -> dict[str, object]:
        updated = {"id": item_id, **value}
        try:
            self.update_many(family, [updated])
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return deepcopy(updated)


catalog = PublicCatalog()


def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    expected = os.environ.get("CATALOG_ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="Catalog writes are disabled")
    if credentials is None or not secrets.compare_digest(credentials.credentials.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"})


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["Cache-Control"] = "no-store"
        response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - start) * 1000:.1f}"
        return response
    finally:
        logger.info("%s %s -> %s | %.1fms", request.method, request.url.path, status_code,
                    (time.perf_counter() - start) * 1000)


@app.get("/health")
def health():
    return {"status": "ok", "mode": "demo", "storage": "sqlite"}


@app.get("/menu")
def menu(response: Response, country: Country | None = None):
    result, hit = catalog.read("menu", country)
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return result


@app.get("/locations")
def locations(response: Response, country: Country | None = None):
    result, hit = catalog.read("locations", country)
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return result


@app.put("/menu/{item_id}", dependencies=[Depends(require_admin)])
def update_menu(item_id: str, item: MenuItem):
    return catalog.update("menu", item_id, item.model_dump())


@app.put("/locations/{item_id}", dependencies=[Depends(require_admin)])
def update_location(item_id: str, location: Location):
    return catalog.update("locations", item_id, location.model_dump())


@app.post("/menu/imports", status_code=202, dependencies=[Depends(require_admin)])
def enqueue_menu_import(batch: MenuBatch, response: Response):
    task_id = str(uuid4())
    storage.create_batch(task_id, batch.model_dump())
    try:
        import_menu.apply_async(args=[task_id], task_id=task_id, retry=False)
    except (CeleryError, OperationalError, RedisError, OSError):
        logger.exception("task_id=%s enqueue failed", task_id)
        raise HTTPException(status_code=503, detail="Task broker unavailable") from None
    response.headers["Location"] = f"/tasks/{task_id}"
    return {"task_id": task_id}


@app.get("/tasks/dead-letter", dependencies=[Depends(require_admin)])
def dead_letters():
    return storage.get_dead_letters()


@app.get("/tasks/{task_id}", dependencies=[Depends(require_admin)])
def task_status(task_id: UUID):
    identifier = str(task_id)
    try:
        storage.get_batch(identifier)
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found") from None
    try:
        task = celery_app.AsyncResult(identifier)
        state = task.state
        status = {"PENDING": "pending", "RECEIVED": "pending", "STARTED": "started",
                  "RETRY": "pending", "SUCCESS": "success", "FAILURE": "failure",
                  "REVOKED": "failure"}.get(state, "pending")
        result = task.result if state == "SUCCESS" else None
        error = str(task.result) if state in {"FAILURE", "REVOKED"} else None
    except (CeleryError, RedisError, OSError):
        raise HTTPException(status_code=503, detail="Task backend unavailable") from None
    return {"task_id": identifier, "status": status, "result": result, "error": error}