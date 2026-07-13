"""Mask engine contracts and deterministic OpenCV baselines."""

from .base import MaskEngine, MaskResult
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
    "TemporalMedianMaskEngine",
    "analyze_rgba_frame",
    "analyze_rgba_sequence",
    "build_inward_alpha",
    "compose_rgba_cutout",
]
