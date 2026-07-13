"""Deterministic static-background mask baseline for ordered video frames."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from .base import MaskResult
from .opencv import _result


class TemporalMedianMaskEngine:
    engine_id = "opencv.temporal-median.v1"

    def __init__(self, lab_distance_threshold: float = 12.0, sample_count: int = 30,
                 minimum_component_pixels: int = 300) -> None:
        if lab_distance_threshold <= 0 or sample_count < 3 or minimum_component_pixels < 1:
            raise ValueError("invalid temporal median mask configuration")
        self.lab_distance_threshold = float(lab_distance_threshold)
        self.sample_count = int(sample_count)
        self.minimum_component_pixels = int(minimum_component_pixels)
        self._background_lab: np.ndarray | None = None

    def fit(self, sources: Sequence[Path]) -> None:
        if len(sources) < 3:
            raise ValueError("at least three frames are required")
        positions = np.linspace(0, len(sources) - 1, min(self.sample_count, len(sources)), dtype=int)
        samples = []
        shape = None
        for position in positions:
            image = cv2.imread(str(sources[int(position)].resolve(strict=True)), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("source is not a readable color image")
            if shape is None:
                shape = image.shape
            elif image.shape != shape:
                raise ValueError("all source frames must have identical dimensions")
            samples.append(image)
        background = np.median(np.stack(samples, axis=0), axis=0).astype(np.uint8)
        self._background_lab = cv2.cvtColor(background, cv2.COLOR_BGR2LAB).astype(np.float32)

    def create_mask(self, source: Path, output: Path) -> MaskResult:
        if self._background_lab is None:
            raise RuntimeError("temporal median engine must be fitted before use")
        image = cv2.imread(str(source.resolve(strict=True)), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("source is not a readable color image")
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
        if lab.shape != self._background_lab.shape:
            raise ValueError("source dimensions do not match fitted background")
        distance = np.linalg.norm(lab - self._background_lab, axis=2)
        candidate = (distance >= self.lab_distance_threshold).astype(np.uint8) * 255
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        horizontal = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, np.ones((1, 31), np.uint8))
        vertical_support = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, np.ones((9, 1), np.uint8))
        thin_horizontal = cv2.bitwise_and(horizontal, cv2.bitwise_not(vertical_support))
        candidate = cv2.bitwise_and(candidate, cv2.bitwise_not(thin_horizontal))
        count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate, connectivity=8)
        if count <= 1:
            foreground = np.zeros_like(candidate)
        else:
            areas = stats[1:, cv2.CC_STAT_AREA]
            largest = int(np.argmax(areas)) + 1
            foreground = np.where(labels == largest, 255, 0).astype(np.uint8)
            x, y, width, height, _ = stats[largest]
            margin = 32
            expanded = (max(0, x - margin), max(0, y - margin),
                        min(image.shape[1], x + width + margin), min(image.shape[0], y + height + margin))
            for label in range(1, count):
                if label == largest or stats[label, cv2.CC_STAT_AREA] < self.minimum_component_pixels:
                    continue
                cx, cy, cw, ch, _ = stats[label]
                if cx < expanded[2] and cx + cw > expanded[0] and cy < expanded[3] and cy + ch > expanded[1]:
                    foreground[labels == label] = 255
        return _result(self.engine_id, source, output, foreground)
