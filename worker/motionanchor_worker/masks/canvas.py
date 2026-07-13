# worker/motionanchor_worker/masks/canvas.py
"""Build deterministic shared-canvas RGBA sequences from approved cutouts."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class SharedCanvasFrame:
    """Placement and hash metadata for one normalized RGBA frame."""

    source_path: str
    output_path: str
    source_bbox_xywh: tuple[int, int, int, int]
    sha256: str


@dataclass(frozen=True)
class SharedCanvasPlan:
    """Validated geometry shared by every frame in a normalized sequence."""

    source_width: int
    source_height: int
    canvas_width: int
    canvas_height: int
    crop_xywh: tuple[int, int, int, int]
    padding: int
    pivot_x: float
    pivot_y: float
    baseline_y: int
    frame_paths: tuple[str, ...]


@dataclass(frozen=True)
class SharedCanvasResult:
    """Published shared-canvas sequence and deterministic package metadata."""

    output_path: str
    report_path: str
    frame_count: int
    canvas_width: int
    canvas_height: int
    pivot_x: float
    pivot_y: float
    baseline_y: int
    sequence_sha256: str
    frames: tuple[SharedCanvasFrame, ...]


def _natural_key(path: Path) -> tuple[object, ...]:
    parts: list[object] = []
    current = ""
    digit_state: bool | None = None
    for character in path.name.lower():
        is_digit = character.isdigit()
        if digit_state is not None and digit_state != is_digit:
            parts.append(int(current) if digit_state else current)
            current = ""
        digit_state = is_digit
        current += character
    if current:
        parts.append(int(current) if digit_state else current)
    return tuple(parts)


def _read_rgba(path: Path) -> np.ndarray:
    image = cv2.imread(str(path.resolve(strict=True)), cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim != 3 or image.shape[2] != 4:
        raise ValueError(f"frame must be a readable four-channel image: {path}")
    return image


def _alpha_bbox(image: np.ndarray, path: Path) -> tuple[int, int, int, int]:
    points = cv2.findNonZero(np.where(image[:, :, 3] > 0, 255, 0).astype(np.uint8))
    if points is None:
        raise ValueError(f"RGBA frame has no foreground pixels: {path}")
    return tuple(int(value) for value in cv2.boundingRect(points))


def build_shared_canvas_plan(frame_paths: list[Path], padding: int = 16) -> SharedCanvasPlan:
    """Calculate one union crop and bottom-center pivot for an RGBA sequence."""

    if not frame_paths:
        raise ValueError("at least one RGBA frame is required")
    if not isinstance(padding, int) or isinstance(padding, bool) or padding < 0 or padding > 4096:
        raise ValueError("padding must be an integer between 0 and 4096")

    ordered = sorted((Path(path) for path in frame_paths), key=_natural_key)
    dimensions: tuple[int, int] | None = None
    boxes: list[tuple[int, int, int, int]] = []
    for path in ordered:
        image = _read_rgba(path)
        height, width = image.shape[:2]
        if dimensions is None:
            dimensions = (width, height)
        elif dimensions != (width, height):
            raise ValueError("all RGBA frames must share identical dimensions")
        boxes.append(_alpha_bbox(image, path))

    assert dimensions is not None
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes)
    bottom = max(box[1] + box[3] for box in boxes)
    crop_width = right - left
    crop_height = bottom - top
    canvas_width = crop_width + (padding * 2)
    canvas_height = crop_height + (padding * 2)
    baseline_y = padding + crop_height

    return SharedCanvasPlan(
        source_width=dimensions[0],
        source_height=dimensions[1],
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        crop_xywh=(left, top, crop_width, crop_height),
        padding=padding,
        pivot_x=0.5,
        pivot_y=padding / float(canvas_height),
        baseline_y=baseline_y,
        frame_paths=tuple(str(path.resolve()) for path in ordered),
    )


def _frame_digest(image: np.ndarray) -> str:
    return hashlib.sha256(image.tobytes(order="C")).hexdigest()


def _sequence_digest(plan: SharedCanvasPlan, frames: list[SharedCanvasFrame]) -> str:
    payload = {
        "canvasWidth": plan.canvas_width,
        "canvasHeight": plan.canvas_height,
        "cropXywh": plan.crop_xywh,
        "padding": plan.padding,
        "pivot": {"x": plan.pivot_x, "y": plan.pivot_y},
        "baselineY": plan.baseline_y,
        "frames": [{"name": Path(frame.output_path).name, "sha256": frame.sha256} for frame in frames],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_rgba_sequence(
    frame_paths: list[Path],
    output_path: Path,
    padding: int = 16,
) -> SharedCanvasResult:
    """Publish a non-destructive shared-canvas sequence through atomic staging."""

    output = Path(output_path).expanduser()
    if output.exists():
        raise FileExistsError("shared-canvas output already exists")
    if not output.parent.is_dir():
        raise ValueError("shared-canvas output parent must exist")

    plan = build_shared_canvas_plan(frame_paths, padding)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-canvas-", dir=output.parent.resolve()))
    published = False

    try:
        left, top, crop_width, crop_height = plan.crop_xywh
        normalized_frames: list[SharedCanvasFrame] = []
        for source_raw in plan.frame_paths:
            source = Path(source_raw)
            image = _read_rgba(source)
            cropped = image[top:top + crop_height, left:left + crop_width]
            canvas = np.zeros((plan.canvas_height, plan.canvas_width, 4), dtype=np.uint8)
            canvas[
                plan.padding:plan.padding + crop_height,
                plan.padding:plan.padding + crop_width,
            ] = cropped
            target = staging / source.name
            if not cv2.imwrite(str(target), canvas):
                raise RuntimeError(f"failed to write normalized RGBA frame: {target}")
            normalized_frames.append(SharedCanvasFrame(
                source_path=str(source.resolve()),
                output_path=str((output / source.name).resolve()),
                source_bbox_xywh=_alpha_bbox(image, source),
                sha256=_frame_digest(canvas),
            ))

        sequence_sha256 = _sequence_digest(plan, normalized_frames)
        report_path = staging / "shared-canvas-report.json"
        report_payload = {
            "schemaVersion": 1,
            "plan": asdict(plan),
            "sequenceSha256": sequence_sha256,
            "frames": [asdict(frame) for frame in normalized_frames],
        }
        report_path.write_text(
            json.dumps(report_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        staging.replace(output)
        published = True
        return SharedCanvasResult(
            output_path=str(output.resolve()),
            report_path=str((output / report_path.name).resolve()),
            frame_count=len(normalized_frames),
            canvas_width=plan.canvas_width,
            canvas_height=plan.canvas_height,
            pivot_x=plan.pivot_x,
            pivot_y=plan.pivot_y,
            baseline_y=plan.baseline_y,
            sequence_sha256=sequence_sha256,
            frames=tuple(normalized_frames),
        )
    finally:
        if not published:
            shutil.rmtree(staging, ignore_errors=True)
