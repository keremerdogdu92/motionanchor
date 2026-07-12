# worker/motionanchor_worker/__init__.py
"""MotionAnchor Python worker sidecar — Phase 0 spike 0.2a.

Protocol 1.0 NDJSON over stdin/stdout.  Diagnostics go to stderr.
"""

from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"
MAX_MESSAGE_BYTES: int = 1024 * 1024  # 1 MiB

__all__ = ["PROTOCOL_VERSION", "MAX_MESSAGE_BYTES"]
