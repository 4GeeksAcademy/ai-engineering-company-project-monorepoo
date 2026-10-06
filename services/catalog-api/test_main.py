import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class CatalogTests(unittest.TestCase):
    def setUp(self):
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


if __name__ == "__main__":
    unittest.main()