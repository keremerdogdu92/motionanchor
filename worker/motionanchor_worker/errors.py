# worker/motionanchor_worker/errors.py
"""Structured IPC error types for the MotionAnchor worker protocol.

Every error carries a machine-readable ``code`` and a human-readable
``message``.  The ``code`` values are fixed strings agreed between
the Rust host and the Python worker so that the host can branch
programmatically on failure classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class WorkerError:
    """Immutable structured error returned inside an IPC error envelope."""

    code: str
    message: str
    details: Optional[dict] = None


# ---------------------------------------------------------------------------
# Well-known error codes
# ---------------------------------------------------------------------------

MALFORMED_JSON: str = "malformed_json"
UNKNOWN_TYPE: str = "unknown_type"
INTERNAL: str = "internal"
SHUTDOWN: str = "shutdown"
MEDIA_REQUEST: str = "media_request"
MEDIA_TOOL_ERROR: str = "media_tool_error"


def malformed_json(detail: Optional[str] = None) -> WorkerError:
    """The host sent bytes that could not be decoded as JSON."""
    msg = "Could not decode request as JSON."
    details: Optional[dict] = {"raw_preview": detail} if detail else None
    return WorkerError(code=MALFORMED_JSON, message=msg, details=details)


def unknown_type(message_type: Optional[str] = None) -> WorkerError:
    """The message ``type`` field is not recognised by this worker."""
    msg = f"Unknown message type: {message_type!r}."
    return WorkerError(code=UNKNOWN_TYPE, message=msg)


def internal(description: str) -> WorkerError:
    """An unexpected internal failure occurred."""
    return WorkerError(code=INTERNAL, message=description)


def media_request(detail: str) -> WorkerError:
    """A media protocol payload was invalid or incomplete."""
    return WorkerError(code=MEDIA_REQUEST, message=detail)


def media_tool_error(detail: str) -> WorkerError:
    """An underlying media tool (FFmpeg/ffprobe) invocation failed."""
    return WorkerError(code=MEDIA_TOOL_ERROR, message=detail)
