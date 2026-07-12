"""Mask engine contracts and deterministic result metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class MaskResult:
    engine_id: str
    engine_version: str
    source_path: str
    mask_path: str
    width: int
    height: int
    foreground_pixels: int
    foreground_ratio: float
    bbox_xywh: tuple[int, int, int, int] | None
    touches_edge: bool
    sha256: str


class MaskEngine(Protocol):
    """Replaceable mask-engine boundary owned by MotionAnchor."""

    engine_id: str

    def create_mask(self, source: Path, output: Path) -> MaskResult:
        """Create a binary mask without modifying the source image."""
