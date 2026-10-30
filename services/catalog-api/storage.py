import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def database():
    path = Path(os.environ.get("CATALOG_DB_PATH", Path(__file__).parent / "var/catalog.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS batches (
                task_id TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT
            );
            CREATE TABLE IF NOT EXISTS catalog_updates (
                family TEXT NOT NULL, item_id TEXT NOT NULL, value TEXT NOT NULL,
                PRIMARY KEY (family, item_id)
            );
            CREATE TABLE IF NOT EXISTS revisions (
                family TEXT PRIMARY KEY, version INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS dead_letters (
                task_id TEXT PRIMARY KEY, attempt INTEGER NOT NULL,
                error TEXT NOT NULL, timestamp TEXT NOT NULL DEFAULT
                (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );
        """)
        with connection:
            yield connection
    finally:
        connection.close()


def create_batch(task_id, payload):
    with database() as connection:
        connection.execute("INSERT INTO batches(task_id, payload) VALUES (?, ?)",
                           (task_id, json.dumps(payload)))


def get_batch(task_id):
    with database() as connection:
        row = connection.execute("SELECT * FROM batches WHERE task_id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError(f"Batch not found: {task_id}")
    return {"payload": json.loads(row["payload"]),
            "result": json.loads(row["result"]) if row["result"] else None}


def catalog_snapshot():
    with database() as connection:
        connection.execute("BEGIN")
        versions = dict(connection.execute("SELECT family, version FROM revisions").fetchall())
        rows = connection.execute("SELECT family, value FROM catalog_updates").fetchall()
    return versions, [(row["family"], json.loads(row["value"])) for row in rows]


def save_updates(updates, task_id=None):
    with database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if task_id:
            row = connection.execute("SELECT result FROM batches WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise ValueError(f"Batch not found: {task_id}")
            if row["result"]:
                return json.loads(row["result"])
        for family, value in updates:
            connection.execute("INSERT OR REPLACE INTO catalog_updates VALUES (?, ?, ?)",
                               (family, value["id"], json.dumps(value)))
        for family in {family for family, _ in updates}:
            connection.execute("""INSERT INTO revisions VALUES (?, 1)
                ON CONFLICT(family) DO UPDATE SET version = version + 1""", (family,))
        result = {"updated": len(updates)}
        if task_id:
            connection.execute("UPDATE batches SET result = ? WHERE task_id = ?",
                               (json.dumps(result), task_id))
    return result


def record_dead_letter(task_id, attempt, error):
    with database() as connection:
        connection.execute("""INSERT INTO dead_letters(task_id, attempt, error) VALUES (?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET attempt = excluded.attempt, error = excluded.error""",
                           (task_id, attempt, error))


def get_dead_letters():
    with database() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM dead_letters ORDER BY timestamp DESC")]