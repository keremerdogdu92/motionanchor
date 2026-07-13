"""Deterministic alpha-matte composition for model-independent mask outputs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class MatteResult:
    """Metadata describing a generated RGBA cutout."""

    source_path: str
    mask_path: str
    output_path: str
    width: int
    height: int
    feather_radius: float
    defringe: bool
    opaque_pixels: int
    translucent_pixels: int
    sha256: str


def build_inward_alpha(mask: np.ndarray, feather_radius: float = 1.5) -> np.ndarray:
    """Build an alpha channel that feathers only inside the foreground boundary."""

    if mask.dtype != np.uint8 or mask.ndim != 2:
        raise ValueError("mask must be an 8-bit single-channel image")
    if not np.isfinite(feather_radius) or feather_radius < 0:
        raise ValueError("feather radius must be finite and non-negative")

    binary = np.where(mask > 0, 255, 0).astype(np.uint8)
    if feather_radius == 0:
        return binary

    distance = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    alpha = np.clip(distance / float(feather_radius), 0.0, 1.0) * 255.0
    return np.rint(alpha).astype(np.uint8)


def _defringe_translucent_pixels(image: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Replace translucent RGB with the nearest fully opaque foreground color."""

    opaque = alpha == 255
    translucent = (alpha > 0) & (alpha < 255)
    if not np.any(opaque) or not np.any(translucent):
        return image.copy()

    distance_source = np.where(opaque, 0, 255).astype(np.uint8)
    _, labels = cv2.distanceTransformWithLabels(
        distance_source,
        cv2.DIST_L2,
        5,
        labelType=cv2.DIST_LABEL_PIXEL,
    )
    max_label = int(labels.max())
    color_lookup = np.zeros((max_label + 1, 3), dtype=np.uint8)
    color_lookup[labels[opaque]] = image[opaque]

    result = image.copy()
    result[translucent] = color_lookup[labels[translucent]]
    return result


def compose_rgba_cutout(
    source: Path,
    mask_path: Path,
    output: Path,
    feather_radius: float = 1.5,
    defringe: bool = True,
) -> MatteResult:
    """Combine a color source and binary mask into a deterministic RGBA image."""

    image = cv2.imread(str(source.resolve(strict=True)), cv2.IMREAD_COLOR)
    mask = cv2.imread(str(mask_path.resolve(strict=True)), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("source is not a readable color image")
    if mask is None:
        raise ValueError("mask is not a readable grayscale image")
    if image.shape[:2] != mask.shape:
        raise ValueError("source and mask dimensions must match")
    if output.exists():
        raise FileExistsError("RGBA output already exists")

    alpha = build_inward_alpha(mask, feather_radius)
    foreground = _defringe_translucent_pixels(image, alpha) if defringe else image
    rgba = cv2.cvtColor(foreground, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = alpha
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), rgba):
        raise RuntimeError("failed to write RGBA image")

    digest = hashlib.sha256(rgba.tobytes(order="C")).hexdigest()
    height, width = mask.shape
    opaque = int(np.count_nonzero(alpha == 255))
    translucent = int(np.count_nonzero((alpha > 0) & (alpha < 255)))
    return MatteResult(
        source_path=str(source.resolve()),
        mask_path=str(mask_path.resolve()),
        output_path=str(output.resolve()),
        width=width,
        height=height,
        feather_radius=float(feather_radius),
        defringe=bool(defringe),
        opaque_pixels=opaque,
        translucent_pixels=translucent,
        sha256=digest,
    )
