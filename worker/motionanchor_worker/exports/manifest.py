"""worker/motionanchor_worker/exports/manifest.py

Defines and validates the engine-neutral animation manifest consumed by export adapters.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ManifestValidationError(ValueError):
    """Raised when an animation manifest violates the stable export contract."""


@dataclass(frozen=True)
class Pivot:
    mode: str
    x: float
    y: float


@dataclass(frozen=True)
class AnimationFrame:
    index: int
    name: str
    duration_ms: int
    source_path: str
    sha256: str


@dataclass(frozen=True)
class SpriteSheet:
    path: str
    sha256: str
    columns: int
    rows: int
    cell_width: int
    cell_height: int
    padding: int


@dataclass(frozen=True)
class AnimationManifest:
    schema_version: str
    name: str
    fps: float
    loop: bool
    pixels_per_unit: float
    pivot: Pivot
    sprite_sheet: SpriteSheet
    frames: tuple[AnimationFrame, ...]


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestValidationError(f"{field} must be an object")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], field: str) -> None:
    missing = expected - value.keys()
    extra = value.keys() - expected
    if missing or extra:
        raise ManifestValidationError(
            f"{field} has invalid keys; missing={sorted(missing)}, extra={sorted(extra)}"
        )


def _positive_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestValidationError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ManifestValidationError(f"{field} must be finite and positive")
    return number


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManifestValidationError(f"{field} must be a positive integer")
    return value


def _unit_interval(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestValidationError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ManifestValidationError(f"{field} must be between 0 and 1")
    return number


def _safe_relative_path(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestValidationError(f"{field} must be a non-empty string")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ManifestValidationError(f"{field} must be a safe relative path")
    return path.as_posix()


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ManifestValidationError(f"{field} must be a 64-character SHA-256 hex string")
    try:
        int(value, 16)
    except ValueError as error:
        raise ManifestValidationError(f"{field} must contain hexadecimal characters") from error
    return value.lower()


def load_animation_manifest(path: Path) -> AnimationManifest:
    """Load a UTF-8 JSON manifest and enforce the version 1.0 contract."""
    resolved = path.resolve(strict=True)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManifestValidationError(f"manifest is not valid UTF-8 JSON: {error}") from error
    root = _object(payload, "manifest")
    _exact_keys(root, {"schema_version", "animation", "sprite_sheet", "frames"}, "manifest")
    if root["schema_version"] != "1.0":
        raise ManifestValidationError("schema_version must be exactly '1.0'")

    animation = _object(root["animation"], "animation")
    _exact_keys(animation, {"name", "fps", "loop", "frame_count", "pivot", "pixels_per_unit"}, "animation")
    name = animation["name"]
    if not isinstance(name, str) or not name.strip():
        raise ManifestValidationError("animation.name must be a non-empty string")
    if not isinstance(animation["loop"], bool):
        raise ManifestValidationError("animation.loop must be a boolean")
    fps = _positive_number(animation["fps"], "animation.fps")
    pixels_per_unit = _positive_number(animation["pixels_per_unit"], "animation.pixels_per_unit")
    frame_count = _positive_int(animation["frame_count"], "animation.frame_count")

    pivot_data = _object(animation["pivot"], "animation.pivot")
    _exact_keys(pivot_data, {"mode", "x", "y"}, "animation.pivot")
    if pivot_data["mode"] not in {"bottom_center", "center", "custom"}:
        raise ManifestValidationError("animation.pivot.mode is unsupported")
    pivot_x = _unit_interval(pivot_data["x"], "animation.pivot.x")
    pivot_y = _unit_interval(pivot_data["y"], "animation.pivot.y")
    pivot = Pivot(mode=pivot_data["mode"], x=pivot_x, y=pivot_y)

    sheet_data = _object(root["sprite_sheet"], "sprite_sheet")
    _exact_keys(sheet_data, {"path", "sha256", "columns", "rows", "cell_width", "cell_height", "padding"}, "sprite_sheet")
    padding = sheet_data["padding"]
    if isinstance(padding, bool) or not isinstance(padding, int) or padding < 0:
        raise ManifestValidationError("sprite_sheet.padding must be a non-negative integer")
    sheet = SpriteSheet(
        path=_safe_relative_path(sheet_data["path"], "sprite_sheet.path"),
        sha256=_sha256(sheet_data["sha256"], "sprite_sheet.sha256"),
        columns=_positive_int(sheet_data["columns"], "sprite_sheet.columns"),
        rows=_positive_int(sheet_data["rows"], "sprite_sheet.rows"),
        cell_width=_positive_int(sheet_data["cell_width"], "sprite_sheet.cell_width"),
        cell_height=_positive_int(sheet_data["cell_height"], "sprite_sheet.cell_height"),
        padding=padding,
    )

    raw_frames = root["frames"]
    if not isinstance(raw_frames, list) or not raw_frames:
        raise ManifestValidationError("frames must be a non-empty array")
    if len(raw_frames) != frame_count:
        raise ManifestValidationError("animation.frame_count must match frames length")
    if sheet.columns * sheet.rows < frame_count:
        raise ManifestValidationError("sprite sheet grid cannot contain all frames")

    frames: list[AnimationFrame] = []
    names: set[str] = set()
    for expected_index, raw_frame in enumerate(raw_frames):
        frame = _object(raw_frame, f"frames[{expected_index}]")
        _exact_keys(frame, {"index", "name", "duration_ms", "source_path", "sha256"}, f"frames[{expected_index}]")
        if frame["index"] != expected_index:
            raise ManifestValidationError("frame indices must be contiguous and zero-based")
        frame_name = frame["name"]
        if not isinstance(frame_name, str) or not frame_name.strip() or frame_name in names:
            raise ManifestValidationError("frame names must be non-empty and unique")
        names.add(frame_name)
        frames.append(AnimationFrame(
            index=expected_index,
            name=frame_name,
            duration_ms=_positive_int(frame["duration_ms"], f"frames[{expected_index}].duration_ms"),
            source_path=_safe_relative_path(frame["source_path"], f"frames[{expected_index}].source_path"),
            sha256=_sha256(frame["sha256"], f"frames[{expected_index}].sha256"),
        ))

    return AnimationManifest(
        schema_version="1.0", name=name, fps=fps, loop=animation["loop"],
        pixels_per_unit=pixels_per_unit, pivot=pivot, sprite_sheet=sheet, frames=tuple(frames)
    )
