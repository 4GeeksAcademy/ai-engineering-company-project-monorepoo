import logging
import os
import time

from celery import Celery, Task

import storage

logger = logging.getLogger("catalog.tasks")
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("brasaland", broker=redis_url, backend=redis_url)
celery_app.conf.update(
    task_default_queue="catalog",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=50,
    task_time_limit=60,
    broker_transport_options={"visibility_timeout": 120, "socket_connect_timeout": 0.1, "socket_timeout": 0.1},
    result_backend_transport_options={"visibility_timeout": 120},
    visibility_timeout=120,
    broker_connection_timeout=0.1,
    result_backend_always_retry=False,
    redis_socket_connect_timeout=1,
    redis_socket_timeout=1,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
)


class ImportTask(Task):
    max_retries = 3

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        storage.record_dead_letter(task_id, self.request.retries + 1, str(exc))
        logger.error("task_id=%s attempt=%s status=failure error=%s",
                     task_id, self.request.retries + 1, exc, exc_info=exc)


@celery_app.task(bind=True, base=ImportTask, name="catalog.import_menu", max_retries=3)
def import_menu(self, batch_id):
    started = time.monotonic()
    attempt = self.request.retries + 1
    state = "started"
    logger.info("task_id=%s attempt=%s status=started duration_ms=0", self.request.id, attempt)
    try:
        from main import MenuBatch, catalog

        batch = storage.get_batch(batch_id)
        if batch["result"] is not None:
            state = "success"
            return batch["result"]
        payload = MenuBatch.model_validate(batch["payload"])
        result = catalog.update_many("menu", [item.model_dump() for item in payload.items], batch_id)
        state = "success"
        return result
    except Exception as exc:
        state = "failure" if self.request.retries >= self.max_retries else "retry"
        logger.exception("task_id=%s attempt=%s status=%s error=%s",
                         self.request.id, attempt, state, exc)
        if state == "failure":
            raise
        raise self.retry(exc=exc, countdown=2 ** attempt)
    finally:
        logger.info("task_id=%s attempt=%s status=%s duration_ms=%.3f",
                    self.request.id, attempt, state, (time.monotonic() - started) * 1000)