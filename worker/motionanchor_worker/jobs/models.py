"""Thread-safe background job state models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Event, Lock
from time import time
from typing import Any


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobRecord:
    job_id: str
    operation: str
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    message: str | None = None
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)
    cancel_event: Event = field(default_factory=Event, repr=False)
    lock: Lock = field(default_factory=Lock, repr=False)
