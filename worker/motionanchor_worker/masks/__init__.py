"""Mask engine contracts and deterministic OpenCV baselines."""

from .base import MaskEngine, MaskResult
from .opencv import ChromaKeyMaskEngine, ExistingAlphaMaskEngine

__all__ = [
    "ChromaKeyMaskEngine",
    "ExistingAlphaMaskEngine",
    "MaskEngine",
    "MaskResult",
]
