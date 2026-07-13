# worker/motionanchor_worker/jobs/runner.py
# Persistent, thread-safe background job runner with atomic crash-recovery snapshots.

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock, Thread
from time import sleep, time
from typing import Any, Callable
from uuid import uuid4

from .models import JobRecord, JobStatus

JobFunction = Callable[[Callable[[float, str | None], None], Callable[[], bool]], dict[str, Any]]
_TERMINAL = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
_MAX_PERSISTED_JOBS = 100
_SCHEMA_VERSION = 1


class JobNotFoundError(KeyError):
    pass


class JobRunner:
    def __init__(self, state_path: Path | bool | None = None) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()
        self._state_path = None if state_path is False else (Path(state_path) if state_path is not None else self._default_state_path())
        self._load_state()

    @staticmethod
    def _default_state_path() -> Path:
        configured = os.environ.get("MOTIONANCHOR_JOB_STATE_PATH")
        if configured:
            return Path(configured).expanduser()
        local_app_data = os.environ.get("LOCALAPPDATA")
        root = Path(local_app_data) if local_app_data else Path.home() / ".motionanchor"
        return root / "MotionAnchor" / "job-state.json"

    def submit(self, operation: str, function: JobFunction) -> str:
        job_id = str(uuid4())
        record = JobRecord(job_id=job_id, operation=operation)
        with self._lock:
            self._jobs[job_id] = record
            self._persist_locked()
        Thread(target=self._run, args=(record, function), daemon=True).start()
        return job_id

    def _run(self, record: JobRecord, function: JobFunction) -> None:
        with record.lock:
            if record.cancel_event.is_set():
                record.status = JobStatus.CANCELLED
                record.updated_at = time()
                should_run = False
            else:
                record.status = JobStatus.RUNNING
                record.updated_at = time()
                should_run = True
        self._persist()
        if not should_run:
            return

        def report(progress: float, message: str | None = None) -> None:
            bounded = max(0.0, min(1.0, float(progress)))
            with record.lock:
                record.progress = bounded
                record.message = message
                record.updated_at = time()
            self._persist()

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
                record.error = {"code": "job_failed", "message": str(exc)}
                record.updated_at = time()
        self._persist()

    def cancel(self, job_id: str) -> bool:
        record = self._get(job_id)
        with record.lock:
            if record.status in _TERMINAL:
                return False
            record.cancel_event.set()
            record.message = "cancellation requested"
            record.updated_at = time()
        self._persist()
        return True

    def snapshot(self, job_id: str) -> dict[str, Any]:
        record = self._get(job_id)
        with record.lock:
            return self._serialize(record)

    def _get(self, job_id: str) -> JobRecord:
        with self._lock:
            record = self._jobs.get(job_id)
        if record is None:
            raise JobNotFoundError(job_id)
        return record

    @staticmethod
    def _serialize(record: JobRecord) -> dict[str, Any]:
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

    def _persist(self) -> None:
        with self._lock:
            self._persist_locked()

    def _persist_locked(self) -> None:
        if self._state_path is None:
            return
        snapshots = []
        ordered = sorted(self._jobs.values(), key=lambda item: item.updated_at, reverse=True)
        for record in ordered[:_MAX_PERSISTED_JOBS]:
            with record.lock:
                snapshots.append(self._serialize(record))
        payload = {"schema_version": _SCHEMA_VERSION, "jobs": snapshots}
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_name(f".{self._state_path.name}.{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for attempt in range(8):
            try:
                os.replace(temporary, self._state_path)
                break
            except PermissionError:
                if attempt == 7:
                    temporary.unlink(missing_ok=True)
                    raise
                sleep(0.01 * (attempt + 1))

    def _load_state(self) -> None:
        if self._state_path is None or not self._state_path.is_file():
            return
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != _SCHEMA_VERSION or not isinstance(payload.get("jobs"), list):
                return
            recovered: dict[str, JobRecord] = {}
            changed = False
            for raw in payload["jobs"][:_MAX_PERSISTED_JOBS]:
                status = JobStatus(raw["status"])
                error = raw.get("error")
                message = raw.get("message")
                if status not in _TERMINAL:
                    status = JobStatus.FAILED
                    error = {"code": "job_interrupted", "message": "Worker restarted before the job reached a terminal state"}
                    message = "Interrupted by worker restart"
                    changed = True
                record = JobRecord(
                    job_id=str(raw["job_id"]), operation=str(raw["operation"]), status=status,
                    progress=float(raw.get("progress", 0.0)), message=message,
                    result=raw.get("result"), error=error,
                    created_at=float(raw.get("created_at", time())), updated_at=float(raw.get("updated_at", time())),
                )
                if status == JobStatus.CANCELLED:
                    record.cancel_event.set()
                recovered[record.job_id] = record
            self._jobs = recovered
            if changed:
                self._persist_locked()
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return
