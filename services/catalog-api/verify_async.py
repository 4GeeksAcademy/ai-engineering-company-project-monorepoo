import base64
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
from redis import Redis

from celery_app import celery_app

ROOT = Path(__file__).resolve().parents[2]


def compose(*arguments):
    return subprocess.run(["docker", "compose", *arguments], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout


def verify():
    token = os.environ.get("CATALOG_ADMIN_TOKEN")
    if not token:
        raise SystemExit("Set CATALOG_ADMIN_TOKEN to the same value used by docker compose up.")
    broker = Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    measurements = {}
    with httpx.Client(base_url="http://localhost:8000", headers={"Authorization": f"Bearer {token}"}, timeout=10) as client:
        compose("stop", "worker")
        try:
            client.get("/health").raise_for_status()
            payload = {"items": [{"id": "demo-co", "name": "Async demo", "country": "CO", "price": 32000}] * 1000}
            started = time.perf_counter()
            accepted = client.post("/menu/imports", json=payload)
            measurements["enqueue_ms"] = round((time.perf_counter() - started) * 1000, 3)
            assert accepted.status_code == 202, accepted.text
            assert measurements["enqueue_ms"] < 200, measurements
            success_id = accepted.json()["task_id"]
            pending = client.get(f"/tasks/{success_id}").json()
            assert pending["status"] == "pending", pending
            message = next(json.loads(raw) for raw in broker.lrange("catalog", 0, -1)
                           if json.loads(raw)["headers"]["id"] == success_id)
            arguments, keywords, _ = json.loads(base64.b64decode(message["body"]))
            assert arguments == [success_id] and keywords == {}, (arguments, keywords)
            measurements["message_arguments"] = arguments
            compose("stop", "api")
            events = broker.pubsub()
            events.subscribe(f"celery-task-meta-{success_id}")
            subscription = events.get_message(timeout=5)
            assert subscription and subscription["type"] == "subscribe", subscription
            compose("start", "worker")
            try:
                result = celery_app.AsyncResult(success_id).get(timeout=45)
                states = []
                while "SUCCESS" not in states:
                    event = events.get_message(timeout=5)
                    assert event is not None, states
                    if event["type"] == "message":
                        states.append(json.loads(event["data"])["status"])
                assert "STARTED" in states, states
                measurements["backend_states"] = states
            finally:
                events.close()
            assert result == {"updated": 1000}, result
            measurements["processed_while_api_stopped"] = True
            compose("up", "-d", "--wait", "api")
            completed = client.get(f"/tasks/{success_id}").json()
            assert completed["status"] == "success", completed
            assert any(item["name"] == "Async demo" for item in client.get("/menu").json())
            failed = client.post("/menu/imports", json={"items": [
                {"id": "missing-demo-item", "name": "DLQ demo", "country": "CO", "price": 1}]})
            assert failed.status_code == 202, failed.text
            failure_id = failed.json()["task_id"]
            celery_app.AsyncResult(failure_id).get(timeout=45, propagate=False)
            failure = client.get(f"/tasks/{failure_id}").json()
            assert failure["status"] == "failure", failure
            letters = client.get("/tasks/dead-letter").json()
            letter = next(item for item in letters if item["task_id"] == failure_id)
            assert letter["attempt"] == 4 and "Item not found" in letter["error"], letter
            flower = httpx.get("http://localhost:5555/tasks", timeout=10)
            assert flower.status_code == 200, flower.text
            measurements.update(success=completed, failure=failure, dead_letter=letter, flower_status=flower.status_code)
        finally:
            compose("up", "-d", "--wait", "api", "worker")
    print(json.dumps(measurements, indent=2))


if __name__ == "__main__":
    verify()