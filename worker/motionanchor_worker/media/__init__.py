# worker/motionanchor_worker/media/__init__.py
"""Expose deterministic media adapters and motion-aware frame selection."""

from .ffmpeg import FfmpegAdapter, FrameRecord, MediaProbe, MediaToolError
from .motion_job import MotionSelectionCancelled, materialize_motion_selection
from .motion_selection import MotionFrameScore, MotionSelection, MotionSelectionError, select_motion_frames

__all__ = [
    "FfmpegAdapter",
    "FrameRecord",
    "MediaProbe",
    "MediaToolError",
    "MotionSelectionCancelled",
    "materialize_motion_selection",
    "MotionFrameScore",
    "MotionSelection",
    "MotionSelectionError",
    "select_motion_frames",
]
