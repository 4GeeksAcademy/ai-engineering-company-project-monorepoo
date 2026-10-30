import os
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
from types import SimpleNamespace
from uuid import uuid4

from celery.exceptions import Retry
from kombu.exceptions import OperationalError

from fastapi.testclient import TestClient

import main


class CatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        database_env = patch.dict(os.environ, {"CATALOG_DB_PATH": str(Path(temporary.name) / "catalog.sqlite3")})
        database_env.start()
        self.addCleanup(database_env.stop)
        self.now = 1000.0
        self.catalog = main.PublicCatalog(clock=lambda: self.now)
        self.catalog_patch = patch.object(main, "catalog", self.catalog)
        self.catalog_patch.start()
        self.addCleanup(self.catalog_patch.stop)
        self.env_patch = patch.dict(os.environ, {"CATALOG_ADMIN_TOKEN": "test-only-token"})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.auth = {"Authorization": "Bearer test-only-token"}

    def test_hits_skip_loader_and_expire_at_ttl(self):
        for path, ttl in [("/menu", main.MENU_TTL), ("/locations", main.LOCATIONS_TTL)]:
            with self.subTest(path=path), patch.object(self.catalog, "load", wraps=self.catalog.load) as loader:
                self.assertEqual(self.client.get(path).headers["X-Cache"], "MISS")
                self.now += ttl - 1
                self.assertEqual(self.client.get(path).headers["X-Cache"], "HIT")
                self.assertEqual(loader.call_count, 1)
                self.now += 1
                self.assertEqual(self.client.get(path).headers["X-Cache"], "MISS")
                self.assertEqual(loader.call_count, 2)

    def test_country_keys_are_isolated_and_bounded(self):
        for path in ["/menu", "/locations"]:
            for country in ["CO", "US"]:
                response = self.client.get(path, params={"country": country})
                self.assertEqual(response.headers["X-Cache"], "MISS")
                self.assertTrue(all(row["country"] == country for row in response.json()))
            self.assertEqual(len(self.client.get(path).json()), 2)
            self.assertEqual(self.client.get(path, params={"country": "FR"}).status_code, 422)
        self.assertEqual(len(self.catalog.entries), 6)

    def test_menu_write_invalidates_all_filters_only_for_menu(self):
        for path in ["/menu", "/locations"]:
            for params in [{}, {"country": "CO"}, {"country": "US"}]:
                self.client.get(path, params=params)
        response = self.client.put("/menu/demo-co", headers=self.auth,
                                   json={"name": "Updated", "country": "US", "price": 20})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(any(key[0] == "menu" for key in self.catalog.entries))
        self.assertEqual(self.client.get("/locations").headers["X-Cache"], "HIT")
        self.assertEqual(self.client.get("/menu", params={"country": "CO"}).json(), [])
        response = self.client.get("/menu", params={"country": "US"})
        self.assertEqual(response.headers["X-Cache"], "MISS")
        self.assertTrue(any(row["name"] == "Updated" and row["currency"] == "USD" for row in response.json()))

    def test_location_write_invalidates_all_location_filters(self):
        for params in [{}, {"country": "CO"}, {"country": "US"}]:
            self.client.get("/locations", params=params)
        response = self.client.put("/locations/demo-med", headers=self.auth,
                                   json={"name": "Updated", "country": "US", "city": "Doral"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.catalog.entries, {})
        self.assertEqual(self.client.get("/locations", params={"country": "CO"}).json(), [])
        self.assertEqual(len(self.client.get("/locations", params={"country": "US"}).json()), 2)

    def test_failed_writes_do_not_invalidate(self):
        self.client.get("/menu")
        payload = {"name": "Updated", "country": "CO", "price": 10}
        for item_id, headers, body, status in [
            ("demo-co", {}, payload, 401),
            ("missing", self.auth, payload, 404),
            ("demo-co", self.auth, {**payload, "price": -1}, 422),
        ]:
            self.assertEqual(self.client.put(f"/menu/{item_id}", headers=headers, json=body).status_code, status)
            self.assertEqual(self.client.get("/menu").headers["X-Cache"], "HIT")

    def test_writes_disabled_without_server_secret(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.put("/locations/demo-med", headers=self.auth,
                                       json={"name": "Updated", "country": "CO", "city": "Medellin"})
            self.assertEqual(response.status_code, 503)

    def test_cached_values_cannot_be_mutated_by_callers(self):
        rows, _ = self.catalog.read("menu", None)
        rows[0]["name"] = "Tampered"
        cached, hit = self.catalog.read("menu", None)
        self.assertTrue(hit)
        self.assertFalse(any(row["name"] == "Tampered" for row in cached))

    def test_concurrent_read_cannot_repopulate_stale_data_after_write(self):
        started = Event()
        release = Event()
        original = self.catalog.load

        def slow_load(family, country):
            started.set()
            if not release.wait(timeout=5):
                raise TimeoutError("Test synchronization failed")
            return original(family, country)

        with patch.object(self.catalog, "load", side_effect=slow_load), ThreadPoolExecutor(max_workers=2) as pool:
            read = pool.submit(self.catalog.read, "menu", None)
            self.assertTrue(started.wait(timeout=5))
            write = pool.submit(self.catalog.update, "menu", "demo-co",
                                {"name": "Updated", "country": "CO", "price": 12, "available": True})
            release.set()
            read.result(timeout=5)
            write.result(timeout=5)
        rows, hit = self.catalog.read("menu", None)
        self.assertFalse(hit)
        self.assertTrue(any(row["name"] == "Updated" for row in rows))

    def test_health_errors_and_docs_are_not_cached(self):
        for path in ["/health", "/missing", "/openapi.json", "/docs", "/redoc"]:
            response = self.client.get(path)
            self.assertNotIn("X-Cache", response.headers)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertIn("Server-Timing", response.headers)
        self.assertEqual(self.catalog.entries, {})

    def test_public_cache_contains_no_credentials(self):
        response = self.client.get("/menu", headers=self.auth)
        self.assertNotIn("test-only-token", str(self.catalog.entries))
        self.assertEqual(self.client.get("/menu").json(), response.json())
        self.assertEqual(self.client.get("/menu").headers["X-Cache"], "HIT")

    def test_timing_logs_do_not_contain_query_or_auth(self):
        with self.assertLogs("api.timing", level="INFO") as logs:
            self.client.get("/menu?token=private-query", headers=self.auth)
        self.assertIn("GET /menu -> 200", logs.output[0])
        self.assertNotIn("private-query", logs.output[0])
        self.assertNotIn("test-only-token", logs.output[0])

    def test_another_process_write_invalidates_cached_family(self):
        self.client.get("/menu")
        self.client.get("/locations")
        another_catalog = main.PublicCatalog()
        another_catalog.update("menu", "demo-co",
                               {"name": "Worker update", "country": "CO", "price": 12, "available": True})
        response = self.client.get("/menu")
        self.assertEqual(response.headers["X-Cache"], "MISS")
        self.assertTrue(any(row["name"] == "Worker update" for row in response.json()))
        self.assertEqual(self.client.get("/locations").headers["X-Cache"], "HIT")

    def enqueue(self):
        payload = {"items": [{"id": "demo-co", "name": "Imported", "country": "CO", "price": 19}]}
        with patch.object(main.import_menu, "apply_async") as publish:
            response = self.client.post("/menu/imports", headers=self.auth, json=payload)
        self.assertEqual(response.status_code, 202)
        task_id = response.json()["task_id"]
        self.assertEqual(publish.call_args.kwargs, {"args": [task_id], "task_id": task_id, "retry": False})
        self.assertEqual(response.headers["Location"], f"/tasks/{task_id}")
        self.assertEqual(main.storage.get_batch(task_id)["payload"]["items"][0]["name"], "Imported")
        self.assertFalse(any(row["name"] == "Imported" for row in self.catalog.menu))
        return task_id

    def test_enqueue_only_publishes_reference_and_does_not_execute(self):
        self.enqueue()

    def test_task_states_and_results(self):
        task_id = self.enqueue()
        for state, expected in [("PENDING", "pending"), ("STARTED", "started"), ("RETRY", "pending"),
                                ("SUCCESS", "success"), ("FAILURE", "failure")]:
            with self.subTest(state=state), patch.object(main.celery_app, "AsyncResult",
                    return_value=SimpleNamespace(state=state, result={"updated": 1} if state == "SUCCESS" else ValueError("failed"))):
                response = self.client.get(f"/tasks/{task_id}", headers=self.auth)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], expected)
                self.assertEqual(response.json()["result"], {"updated": 1} if state == "SUCCESS" else None)
                self.assertEqual(response.json()["error"], "failed" if state == "FAILURE" else None)

    def test_async_routes_require_auth_and_validate_input(self):
        self.assertEqual(self.client.post("/menu/imports", json={"items": []}).status_code, 401)
        self.assertEqual(self.client.post("/menu/imports", headers=self.auth, json={"items": []}).status_code, 422)
        self.assertEqual(self.client.get("/tasks/dead-letter").status_code, 401)
        self.assertEqual(self.client.get(f"/tasks/{uuid4()}", headers=self.auth).status_code, 404)
        self.assertEqual(self.client.get("/tasks/invalid", headers=self.auth).status_code, 422)

    def test_broker_failure_does_not_return_accepted(self):
        with patch.object(main.import_menu, "apply_async", side_effect=OperationalError("offline")):
            response = self.client.post("/menu/imports", headers=self.auth,
                json={"items": [{"id": "demo-co", "name": "Imported", "country": "CO", "price": 19}]})
        self.assertEqual(response.status_code, 503)

    def test_worker_retries_with_exponential_countdown_then_dlq(self):
        task_id = str(uuid4())
        main.storage.create_batch(task_id, {"items": [
            {"id": "missing", "name": "Invalid", "country": "CO", "price": 1}]})
        task = main.import_menu
        for retries in range(3):
            task.push_request(id=task_id, retries=retries)
            try:
                with patch.object(task, "retry", side_effect=Retry()) as retry:
                    with self.assertRaises(Retry):
                        task.run(task_id)
                self.assertEqual(retry.call_args.kwargs["countdown"], 2 ** (retries + 1))
                self.assertEqual(main.storage.get_dead_letters(), [])
            finally:
                task.pop_request()
        task.push_request(id=task_id, retries=3)
        try:
            with self.assertRaises(ValueError) as error:
                task.run(task_id)
            task.on_failure(error.exception, task_id, [task_id], {}, None)
        finally:
            task.pop_request()
        failure = self.client.get("/tasks/dead-letter", headers=self.auth).json()[0]
        self.assertEqual(failure["task_id"], task_id)
        self.assertEqual(failure["attempt"], 4)
        self.assertIn("Item not found", failure["error"])

    def test_worker_commits_once_on_redelivery(self):
        task_id = self.enqueue()
        main.import_menu.push_request(id=task_id, retries=0)
        try:
            self.assertEqual(main.import_menu.run(task_id), {"updated": 1})
            self.assertEqual(main.import_menu.run(task_id), {"updated": 1})
        finally:
            main.import_menu.pop_request()
        self.assertEqual(main.storage.catalog_snapshot()[0], {"menu": 1})
        self.assertTrue(any(row["name"] == "Imported" for row in self.client.get("/menu").json()))

    def test_batch_is_atomic_if_one_item_is_unknown(self):
        with self.assertRaises(ValueError):
            self.catalog.update_many("menu", [
                {"id": "demo-co", "name": "Do not save", "country": "CO", "price": 1},
                {"id": "missing", "name": "Invalid", "country": "CO", "price": 1}])
        self.assertEqual(main.storage.catalog_snapshot(), ({}, []))


if __name__ == "__main__":
    unittest.main()