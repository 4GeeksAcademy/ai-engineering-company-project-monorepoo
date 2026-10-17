import logging
import os
import secrets
import time
from collections.abc import Callable
from copy import deepcopy
from threading import RLock
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

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


class PublicCatalog:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.lock = RLock()
        self.entries: dict[CacheKey, tuple[float, CacheValue]] = {}
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
            now = self.clock()
            self.entries = {key: entry for key, entry in self.entries.items() if entry[0] > now}
            key = (family, country)
            if key in self.entries:
                return deepcopy(self.entries[key][1]), True
            result = self.load(family, country)
            ttl = MENU_TTL if family == "menu" else LOCATIONS_TTL
            self.entries[key] = (self.clock() + ttl, deepcopy(result))
            return result, False

    def update(self, family: Family, item_id: str, value: dict[str, object]) -> dict[str, object]:
        with self.lock:
            rows = self.menu if family == "menu" else self.locations
            for index, row in enumerate(rows):
                if row["id"] == item_id:
                    updated = {"id": item_id, **value}
                    rows[index] = updated
                    self.entries = {key: entry for key, entry in self.entries.items() if key[0] != family}
                    return deepcopy(updated)
            raise HTTPException(status_code=404, detail="Item not found")


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
    return {"status": "ok", "mode": "demo", "storage": "in-process"}


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