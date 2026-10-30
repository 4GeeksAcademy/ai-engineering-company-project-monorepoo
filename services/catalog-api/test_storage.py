import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {"CATALOG_DB_PATH": str(Path(temporary.name) / "test.sqlite3")})
        environment.start()
        self.addCleanup(environment.stop)

    def test_batch_commit_is_persistent_and_idempotent(self):
        storage.create_batch("batch-1", [{"id": "demo-co"}])
        updates = [("menu", {"id": "demo-co", "name": "Updated"})]
        self.assertEqual(storage.save_updates(updates, "batch-1"), {"updated": 1})
        self.assertEqual(storage.save_updates(updates, "batch-1"), {"updated": 1})
        versions, rows = storage.catalog_snapshot()
        self.assertEqual(versions, {"menu": 1})
        self.assertEqual(rows, updates)
        self.assertEqual(storage.get_batch("batch-1")["result"], {"updated": 1})

    def test_unknown_batch_does_not_write_catalog(self):
        with self.assertRaises(ValueError):
            storage.save_updates([("menu", {"id": "demo-co"})], "missing")
        self.assertEqual(storage.catalog_snapshot(), ({}, []))

    def test_dead_letter_is_durable_and_deduplicated(self):
        for _ in range(2):
            storage.record_dead_letter("batch-2", 4, "Full exception message")
        letters = storage.get_dead_letters()
        self.assertEqual(len(letters), 1)
        self.assertEqual(letters[0]["task_id"], "batch-2")
        self.assertEqual(letters[0]["attempt"], 4)
        self.assertEqual(letters[0]["error"], "Full exception message")
        self.assertTrue(letters[0]["timestamp"].endswith("Z"))