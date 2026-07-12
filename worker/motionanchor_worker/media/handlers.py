"""Protocol handlers for MotionAnchor media operations."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from .ffmpeg import FfmpegAdapter, MediaToolError

AdapterFactory = Callable[[], FfmpegAdapter]


class MediaRequestError(ValueError):
    """Raised when a media protocol payload is invalid."""


def _required_path(payload: dict[str, Any], field: str) -> Path:
    raw = payload.get(field)
    if not isinstance(raw, str) or not raw.strip():
        raise MediaRequestError(f"payload.{field} must be a non-empty string")
    return Path(raw).expanduser()


def handle_media_probe(
    payload: dict[str, Any],
    adapter_factory: AdapterFactory = FfmpegAdapter,
) -> dict[str, Any]:
    source = _required_path(payload, "source_path")
    probe = adapter_factory().probe(source)
    return asdict(probe)


def handle_media_extract_frames(
    payload: dict[str, Any],
    adapter_factory: AdapterFactory = FfmpegAdapter,
) -> dict[str, Any]:
    source = _required_path(payload, "source_path")
    output = _required_path(payload, "output_path")
    records = adapter_factory().extract_png_frames(source, output)
    return {
        "source_path": str(source.resolve()),
        "output_path": str(output.resolve()),
        "frame_count": len(records),
        "manifest_path": str((output.resolve() / "frames.json")),
        "first_timestamp_seconds": records[0].timestamp_seconds,
        "last_timestamp_seconds": records[-1].timestamp_seconds,
    }


def execute_media_request(
    message_type: str,
    payload: dict[str, Any],
    adapter_factory: AdapterFactory = FfmpegAdapter,
) -> tuple[str, dict[str, Any]]:
    if message_type == "media.probe":
        return "media.probed", handle_media_probe(payload, adapter_factory)
    if message_type == "media.extract_frames":
        return "media.frames_extracted", handle_media_extract_frames(payload, adapter_factory)
    raise MediaRequestError(f"unsupported media request: {message_type}")


__all__ = [
    "AdapterFactory",
    "MediaRequestError",
    "MediaToolError",
    "execute_media_request",
    "handle_media_extract_frames",
    "handle_media_probe",
]
