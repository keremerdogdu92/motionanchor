# worker/motionanchor_worker/masks/quality.py
"""Analyze RGBA frame sequences without imposing product-specific thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class RgbaFrameQuality:
    """Objective alpha-channel diagnostics for one RGBA frame."""

    path: str
    width: int
    height: int
    foreground_pixels: int
    opaque_pixels: int
    translucent_pixels: int
    foreground_ratio: float
    translucent_ratio: float
    bbox_xywh: tuple[int, int, int, int] | None
    touches_edge: bool
    component_count: int
    largest_component_ratio: float


@dataclass(frozen=True)
class RgbaSequenceQuality:
    """Aggregate diagnostics for a dimensionally consistent RGBA sequence."""

    frame_count: int
    width: int
    height: int
    empty_frame_count: int
    edge_touch_frame_count: int
    maximum_component_count: int
    minimum_largest_component_ratio: float
    minimum_foreground_ratio: float
    maximum_foreground_ratio: float
    frames: tuple[RgbaFrameQuality, ...]


def analyze_rgba_frame(path: Path) -> RgbaFrameQuality:
    """Read one RGBA PNG and calculate deterministic alpha diagnostics."""

    image = cv2.imread(str(path.resolve(strict=True)), cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim != 3 or image.shape[2] != 4:
        raise ValueError("frame must be a readable four-channel image")

    alpha = image[:, :, 3]
    foreground = alpha > 0
    binary = np.where(foreground, 255, 0).astype(np.uint8)
    height, width = alpha.shape
    foreground_pixels = int(np.count_nonzero(foreground))
    opaque_pixels = int(np.count_nonzero(alpha == 255))
    translucent_pixels = int(np.count_nonzero((alpha > 0) & (alpha < 255)))

    points = cv2.findNonZero(binary)
    bbox = tuple(int(value) for value in cv2.boundingRect(points)) if points is not None else None
    touches_edge = bool(
        np.any(binary[0, :])
        or np.any(binary[-1, :])
        or np.any(binary[:, 0])
        or np.any(binary[:, -1])
    )

    component_count = 0
    largest_component_ratio = 0.0
    if foreground_pixels > 0:
        labels_count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        areas = stats[1:, cv2.CC_STAT_AREA]
        component_count = int(labels_count - 1)
        largest_component_ratio = float(int(areas.max()) / foreground_pixels)

    total_pixels = width * height
    return RgbaFrameQuality(
        path=str(path.resolve()),
        width=width,
        height=height,
        foreground_pixels=foreground_pixels,
        opaque_pixels=opaque_pixels,
        translucent_pixels=translucent_pixels,
        foreground_ratio=foreground_pixels / float(total_pixels),
        translucent_ratio=translucent_pixels / float(total_pixels),
        bbox_xywh=bbox,
        touches_edge=touches_edge,
        component_count=component_count,
        largest_component_ratio=largest_component_ratio,
    )


def analyze_rgba_sequence(paths: list[Path]) -> RgbaSequenceQuality:
    """Analyze an ordered RGBA sequence and enforce consistent dimensions."""

    if not paths:
        raise ValueError("at least one RGBA frame is required")

    frames = tuple(analyze_rgba_frame(path) for path in paths)
    dimensions = {(frame.width, frame.height) for frame in frames}
    if len(dimensions) != 1:
        raise ValueError("all RGBA frames must share identical dimensions")

    width, height = next(iter(dimensions))
    foreground_ratios = [frame.foreground_ratio for frame in frames]
    largest_ratios = [frame.largest_component_ratio for frame in frames]
    return RgbaSequenceQuality(
        frame_count=len(frames),
        width=width,
        height=height,
        empty_frame_count=sum(frame.foreground_pixels == 0 for frame in frames),
        edge_touch_frame_count=sum(frame.touches_edge for frame in frames),
        maximum_component_count=max(frame.component_count for frame in frames),
        minimum_largest_component_ratio=min(largest_ratios),
        minimum_foreground_ratio=min(foreground_ratios),
        maximum_foreground_ratio=max(foreground_ratios),
        frames=frames,
    )
