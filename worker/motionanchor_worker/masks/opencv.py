"""Deterministic OpenCV mask engines for Phase 0 fixtures."""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

from .base import MaskResult


def _result(engine_id: str, source: Path, output: Path, mask: np.ndarray) -> MaskResult:
    if mask.dtype != np.uint8 or mask.ndim != 2:
        raise ValueError("mask must be an 8-bit single-channel image")
    binary = np.where(mask > 0, 255, 0).astype(np.uint8)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("mask output already exists")
    if not cv2.imwrite(str(output), binary):
        raise RuntimeError("failed to write mask image")
    points = cv2.findNonZero(binary)
    bbox = tuple(int(v) for v in cv2.boundingRect(points)) if points is not None else None
    foreground = int(np.count_nonzero(binary))
    touches = bool(
        np.any(binary[0, :]) or np.any(binary[-1, :])
        or np.any(binary[:, 0]) or np.any(binary[:, -1])
    )
    digest = hashlib.sha256(binary.tobytes(order="C")).hexdigest()
    height, width = binary.shape
    return MaskResult(
        engine_id=engine_id,
        engine_version=cv2.__version__,
        source_path=str(source.resolve()),
        mask_path=str(output.resolve()),
        width=width,
        height=height,
        foreground_pixels=foreground,
        foreground_ratio=foreground / float(width * height),
        bbox_xywh=bbox,
        touches_edge=touches,
        sha256=digest,
    )


class ExistingAlphaMaskEngine:
    engine_id = "opencv.existing-alpha.v1"

    def create_mask(self, source: Path, output: Path) -> MaskResult:
        image = cv2.imread(str(source.resolve(strict=True)), cv2.IMREAD_UNCHANGED)
        if image is None or image.ndim != 3 or image.shape[2] != 4:
            raise ValueError("source does not contain an alpha channel")
        return _result(self.engine_id, source, output, image[:, :, 3])


class ChromaKeyMaskEngine:
    engine_id = "opencv.chroma-key.v1"

    def __init__(self, lower_hsv: tuple[int, int, int] = (35, 60, 40), upper_hsv: tuple[int, int, int] = (90, 255, 255)) -> None:
        self.lower_hsv = np.array(lower_hsv, dtype=np.uint8)
        self.upper_hsv = np.array(upper_hsv, dtype=np.uint8)

    def create_mask(self, source: Path, output: Path) -> MaskResult:
        image = cv2.imread(str(source.resolve(strict=True)), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("source is not a readable color image")
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        background = cv2.inRange(hsv, self.lower_hsv, self.upper_hsv)
        foreground = cv2.bitwise_not(background)
        return _result(self.engine_id, source, output, foreground)
