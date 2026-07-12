"""Deterministic mask quality metrics for shared fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class MaskBenchmarkResult:
    width: int
    height: int
    intersection_over_union: float
    precision: float
    recall: float
    boundary_f1: float
    predicted_foreground_pixels: int
    expected_foreground_pixels: int


def _load_binary(path: Path) -> np.ndarray:
    image = cv2.imread(str(path.resolve(strict=True)), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"mask is not readable: {path}")
    return image > 0


def _safe_ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 and numerator == 0 else (
        0.0 if denominator == 0 else numerator / denominator
    )


def _boundary(mask: np.ndarray) -> np.ndarray:
    image = mask.astype(np.uint8) * 255
    eroded = cv2.erode(image, np.ones((3, 3), dtype=np.uint8), iterations=1)
    return (image > eroded)


def compare_masks(predicted: Path, expected: Path) -> MaskBenchmarkResult:
    predicted_mask = _load_binary(predicted)
    expected_mask = _load_binary(expected)
    if predicted_mask.shape != expected_mask.shape:
        raise ValueError("predicted and expected masks must have identical dimensions")

    true_positive = int(np.count_nonzero(predicted_mask & expected_mask))
    false_positive = int(np.count_nonzero(predicted_mask & ~expected_mask))
    false_negative = int(np.count_nonzero(~predicted_mask & expected_mask))
    union = true_positive + false_positive + false_negative

    predicted_boundary = _boundary(predicted_mask)
    expected_boundary = _boundary(expected_mask)
    kernel = np.ones((3, 3), dtype=np.uint8)
    predicted_near = cv2.dilate(predicted_boundary.astype(np.uint8), kernel) > 0
    expected_near = cv2.dilate(expected_boundary.astype(np.uint8), kernel) > 0
    boundary_precision = _safe_ratio(
        int(np.count_nonzero(predicted_boundary & expected_near)),
        int(np.count_nonzero(predicted_boundary)),
    )
    boundary_recall = _safe_ratio(
        int(np.count_nonzero(expected_boundary & predicted_near)),
        int(np.count_nonzero(expected_boundary)),
    )
    boundary_f1 = _safe_ratio(
        2 * boundary_precision * boundary_recall,
        boundary_precision + boundary_recall,
    )

    height, width = predicted_mask.shape
    return MaskBenchmarkResult(
        width=width,
        height=height,
        intersection_over_union=_safe_ratio(true_positive, union),
        precision=_safe_ratio(true_positive, true_positive + false_positive),
        recall=_safe_ratio(true_positive, true_positive + false_negative),
        boundary_f1=boundary_f1,
        predicted_foreground_pixels=int(np.count_nonzero(predicted_mask)),
        expected_foreground_pixels=int(np.count_nonzero(expected_mask)),
    )
