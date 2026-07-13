"""Temporal stability diagnostics for ordered binary mask sequences."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np


@dataclass(frozen=True)
class TemporalMaskPair:
    previous_index: int
    current_index: int
    aligned_iou: float
    area_change_ratio: float
    centroid_shift_pixels: float
    boundary_turnover_ratio: float


@dataclass(frozen=True)
class TemporalMaskReport:
    frame_count: int
    pair_count: int
    mean_aligned_iou: float
    minimum_aligned_iou: float
    mean_area_change_ratio: float
    maximum_area_change_ratio: float
    mean_centroid_shift_pixels: float
    maximum_centroid_shift_pixels: float
    mean_boundary_turnover_ratio: float
    maximum_boundary_turnover_ratio: float
    pairs: tuple[TemporalMaskPair, ...]


def _load_mask(path: Path) -> np.ndarray:
    image = cv2.imread(str(path.resolve(strict=True)), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"mask is not readable: {path}")
    return image > 0


def _centroid(mask: np.ndarray) -> tuple[float, float]:
    moments = cv2.moments(mask.astype(np.uint8), binaryImage=True)
    if moments["m00"] == 0:
        return (0.0, 0.0)
    return (moments["m10"] / moments["m00"], moments["m01"] / moments["m00"])


def _translate(mask: np.ndarray, dx: float, dy: float) -> np.ndarray:
    height, width = mask.shape
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    shifted = cv2.warpAffine(
        mask.astype(np.uint8),
        matrix,
        (width, height),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return shifted > 0


def _iou(first: np.ndarray, second: np.ndarray) -> float:
    union = int(np.count_nonzero(first | second))
    if union == 0:
        return 1.0
    return int(np.count_nonzero(first & second)) / union


def _boundary(mask: np.ndarray) -> np.ndarray:
    image = mask.astype(np.uint8)
    eroded = cv2.erode(image, np.ones((3, 3), dtype=np.uint8), iterations=1)
    return (image > eroded)


def compare_temporal_masks(paths: Sequence[Path]) -> TemporalMaskReport:
    if len(paths) < 2:
        raise ValueError("at least two masks are required")
    masks = [_load_mask(path) for path in paths]
    shape = masks[0].shape
    if any(mask.shape != shape for mask in masks[1:]):
        raise ValueError("all masks must have identical dimensions")

    pairs: list[TemporalMaskPair] = []
    for index, (previous, current) in enumerate(zip(masks, masks[1:]), start=1):
        previous_centroid = _centroid(previous)
        current_centroid = _centroid(current)
        dx = previous_centroid[0] - current_centroid[0]
        dy = previous_centroid[1] - current_centroid[1]
        aligned = _translate(current, dx, dy)
        previous_area = int(np.count_nonzero(previous))
        current_area = int(np.count_nonzero(current))
        denominator = max(previous_area, current_area, 1)
        previous_boundary = _boundary(previous)
        current_boundary = _boundary(aligned)
        boundary_union = int(np.count_nonzero(previous_boundary | current_boundary))
        boundary_difference = int(np.count_nonzero(previous_boundary ^ current_boundary))
        pairs.append(
            TemporalMaskPair(
                previous_index=index - 1,
                current_index=index,
                aligned_iou=_iou(previous, aligned),
                area_change_ratio=abs(current_area - previous_area) / denominator,
                centroid_shift_pixels=float(np.hypot(dx, dy)),
                boundary_turnover_ratio=(boundary_difference / boundary_union) if boundary_union else 0.0,
            )
        )

    def mean(values: list[float]) -> float:
        return float(sum(values) / len(values))

    aligned = [pair.aligned_iou for pair in pairs]
    area = [pair.area_change_ratio for pair in pairs]
    shifts = [pair.centroid_shift_pixels for pair in pairs]
    boundary = [pair.boundary_turnover_ratio for pair in pairs]
    return TemporalMaskReport(
        frame_count=len(masks),
        pair_count=len(pairs),
        mean_aligned_iou=mean(aligned),
        minimum_aligned_iou=min(aligned),
        mean_area_change_ratio=mean(area),
        maximum_area_change_ratio=max(area),
        mean_centroid_shift_pixels=mean(shifts),
        maximum_centroid_shift_pixels=max(shifts),
        mean_boundary_turnover_ratio=mean(boundary),
        maximum_boundary_turnover_ratio=max(boundary),
        pairs=tuple(pairs),
    )
