"""In-memory background job runner for worker operations."""

from __future__ import annotations

from threading import Lock, Thread
from time import time
from typing import Any, Callable
from uuid import uuid4

from .models import JobRecord, JobStatus

JobFunction = Callable[[Callable[[float, str | None], None], Callable[[], bool]], dict[str, Any]]


class JobNotFoundError(KeyError):
    pass


class JobRunner:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def submit(self, operation: str, function: JobFunction) -> str:
        job_id = str(uuid4())
        record = JobRecord(job_id=job_id, operation=operation)
        with self._lock:
            self._jobs[job_id] = record
        Thread(target=self._run, args=(record, function), daemon=True).start()
        return job_id

    def _run(self, record: JobRecord, function: JobFunction) -> None:
        with record.lock:
            if record.cancel_event.is_set():
                record.status = JobStatus.CANCELLED
                record.updated_at = time()
                return
            record.status = JobStatus.RUNNING
            record.updated_at = time()

        def report(progress: float, message: str | None = None) -> None:
            bounded = max(0.0, min(1.0, float(progress)))
            with record.lock:
                record.progress = bounded
                record.message = message
                record.updated_at = time()

        try:
            result = function(report, record.cancel_event.is_set)
            with record.lock:
                if record.cancel_event.is_set():
                    record.status = JobStatus.CANCELLED
                    record.result = None
                else:
                    record.status = JobStatus.COMPLETED
                    record.progress = 1.0
                    record.result = result
                record.updated_at = time()
        except Exception as exc:
            with record.lock:
                record.status = JobStatus.FAILED
                record.error = {
                    "code": "job_failed",
                    "message": str(exc),
                }
                record.updated_at = time()

    def cancel(self, job_id: str) -> bool:
        record = self._get(job_id)
        with record.lock:
            if record.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
                return False
            record.cancel_event.set()
            record.message = "cancellation requested"
            record.updated_at = time()
            return True

    def snapshot(self, job_id: str) -> dict[str, Any]:
        record = self._get(job_id)
        with record.lock:
            return {
                "job_id": record.job_id,
                "operation": record.operation,
                "status": record.status.value,
                "progress": record.progress,
                "message": record.message,
                "result": record.result,
                "error": record.error,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "cancellation_requested": record.cancel_event.is_set(),
            }

    def _get(self, job_id: str) -> JobRecord:
        with self._lock:
            record = self._jobs.get(job_id)
        if record is None:
            raise JobNotFoundError(job_id)
        return record
