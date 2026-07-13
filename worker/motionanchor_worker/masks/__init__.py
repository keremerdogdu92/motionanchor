"""Mask engine contracts and deterministic OpenCV baselines."""

from .base import MaskEngine, MaskResult
from .canvas import (
    SharedCanvasFrame,
    SharedCanvasPlan,
    SharedCanvasResult,
    build_shared_canvas_plan,
    normalize_rgba_sequence,
)
from .matte import MatteResult, build_inward_alpha, compose_rgba_cutout
from .opencv import BorderConnectedMaskEngine, ChromaKeyMaskEngine, ExistingAlphaMaskEngine
from .quality import RgbaFrameQuality, RgbaSequenceQuality, analyze_rgba_frame, analyze_rgba_sequence
from .temporal_median import TemporalMedianMaskEngine

__all__ = [
    "BorderConnectedMaskEngine",
    "ChromaKeyMaskEngine",
    "ExistingAlphaMaskEngine",
    "MaskEngine",
    "MaskResult",
    "MatteResult",
    "RgbaFrameQuality",
    "RgbaSequenceQuality",
    "SharedCanvasFrame",
    "SharedCanvasPlan",
    "SharedCanvasResult",
    "TemporalMedianMaskEngine",
    "analyze_rgba_frame",
    "analyze_rgba_sequence",
    "build_inward_alpha",
    "build_shared_canvas_plan",
    "compose_rgba_cutout",
    "normalize_rgba_sequence",
]
