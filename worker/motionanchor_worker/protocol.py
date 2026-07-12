# worker/motionanchor_worker/protocol.py
"""Protocol 1.0 message envelope construction and validation.

Message wire format (one JSON object per line, NDJSON):

    {
        "protocol_version": "1.0",
        "message_id":       "<uuid>",
        "type":             "<dotted.type>",
        "job_id":           "<uuid> | null",
        "payload":          { ... }
    }

This module knows nothing about I/O; it purely builds and inspects
envelope dicts so the worker loop and tests stay decoupled.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import uuid4

from . import MAX_MESSAGE_BYTES, PROTOCOL_VERSION
from .errors import WorkerError

# â”€â”€ Incoming message kinds handled by the worker â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

TYPE_WORKER_STARTUP: str = "worker.startup"
TYPE_WORKER_PING: str = "worker.ping"
TYPE_WORKER_SHUTDOWN: str = "worker.shutdown"
TYPE_MEDIA_PROBE: str = "media.probe"
TYPE_MEDIA_EXTRACT_FRAMES: str = "media.extract_frames"
TYPE_JOB_SUBMIT_EXTRACT_FRAMES: str = "job.submit.media.extract_frames"
TYPE_JOB_STATUS: str = "job.status"
TYPE_JOB_CANCEL: str = "job.cancel"

# Outgoing message kinds produced by the worker

TYPE_WORKER_READY: str = "worker.ready"
TYPE_WORKER_PONG: str = "worker.pong"
TYPE_WORKER_STOPPED: str = "worker.stopped"
TYPE_ERROR: str = "error"
TYPE_MEDIA_PROBED: str = "media.probed"
TYPE_MEDIA_FRAMES_EXTRACTED: str = "media.frames_extracted"
TYPE_JOB_ACCEPTED: str = "job.accepted"
TYPE_JOB_STATUS_RESULT: str = "job.status_result"
TYPE_JOB_CANCEL_RESULT: str = "job.cancel_result"

# All types the worker may produce (for validation helpers)

OUTPUT_TYPES: frozenset[str] = frozenset(
    {TYPE_WORKER_READY, TYPE_WORKER_PONG, TYPE_WORKER_STOPPED, TYPE_ERROR, TYPE_MEDIA_PROBED, TYPE_MEDIA_FRAMES_EXTRACTED, TYPE_JOB_ACCEPTED, TYPE_JOB_STATUS_RESULT, TYPE_JOB_CANCEL_RESULT}
)


# â”€â”€ Envelope helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def new_message_id() -> str:
    """Return a fresh UUID4 string."""
    return str(uuid4())


def make_envelope(
    *,
    message_type: str,
    payload: Optional[dict[str, Any]] = None,
    message_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build a protocol-compliant outgoing envelope."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "message_id": message_id or new_message_id(),
        "type": message_type,
        "job_id": job_id,
        "payload": payload or {},
    }


def make_error_envelope(
    error: WorkerError,
    *,
    in_reply_to: Optional[str] = None,
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build an error envelope referencing the failed ``message_id``."""
    payload: dict[str, Any] = {
        "code": error.code,
        "message": error.message,
    }
    if error.details is not None:
        payload["details"] = error.details
    return {
        "protocol_version": PROTOCOL_VERSION,
        "message_id": in_reply_to or new_message_id(),
        "type": TYPE_ERROR,
        "job_id": job_id,
        "payload": payload,
    }


def envelope_to_json(env: dict[str, Any]) -> bytes:
    """Serialise an envelope to a UTF-8 line suitable for stdout."""
    raw = json.dumps(env, separators=(",", ":")) + "\n"
    return raw.encode("utf-8")


def parse_line(raw_line: bytes) -> tuple[Optional[dict[str, Any]], Optional[WorkerError]]:
    """Try to decode a single NDJSON line into an envelope.

    Returns ``(envelope, None)`` on success or ``(None, error)`` on failure.
    Does **not** validate ``type`` or ``payload`` structure beyond the
    top-level JSON object.
    """
    if not raw_line or raw_line.isspace():
        return None, None  # blank lines are silently skipped

    if len(raw_line) > MAX_MESSAGE_BYTES:
        return None, WorkerError(
            code="malformed_json",
            message=f"Message exceeds {MAX_MESSAGE_BYTES} byte limit.",
        )

    try:
        obj = json.loads(raw_line)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        preview = raw_line[:80].decode("utf-8", errors="replace")
        return None, WorkerError(
            code="malformed_json",
            message=f"Could not decode request as JSON: {exc}",
            details={"raw_preview": preview},
        )

    if not isinstance(obj, dict):
        return None, WorkerError(
            code="malformed_json",
            message="Top-level JSON value must be an object.",
        )

    return obj, None


def validate_envelope(obj: dict[str, Any]) -> Optional[WorkerError]:
    """Validate required top-level envelope fields; return an error or *None*."""
    for field in ("protocol_version", "message_id", "type", "payload"):
        if field not in obj:
            return WorkerError(
                code="malformed_json",
                message=f"Missing required envelope field: {field!r}.",
            )

    if not isinstance(obj["payload"], dict):
        return WorkerError(
            code="malformed_json",
            message="'payload' must be a JSON object.",
        )

    return None
