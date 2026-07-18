# worker/motionanchor_worker/media/motion_selection.py
"""Select a deterministic, motion-preserving subset from extracted PNG frames.

The selector integrates with the FFmpeg frame directory contract and prepares
bounded frame sets for expensive downstream segmentation such as SAM 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


class MotionSelectionError(ValueError):
    """Raised when a frame-selection request violates the production contract."""


@dataclass(frozen=True)
class MotionFrameScore:
    """Motion score associated with one source frame index."""

    index: int
    score: float


@dataclass(frozen=True)
class MotionSelection:
    """Deterministic source indices selected for downstream processing."""

    source_frame_count: int
    selected_indices: tuple[int, ...]
    scores: tuple[MotionFrameScore, ...]


def _load_gray_preview(path: Path, preview_width: int) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise MotionSelectionError(f"failed to read frame: {path}")
    if preview_width <= 0:
        raise MotionSelectionError("preview_width must be positive")
    if image.shape[1] <= preview_width:
        return image
    scale = preview_width / image.shape[1]
    height = max(1, round(image.shape[0] * scale))
    return cv2.resize(image, (preview_width, height), interpolation=cv2.INTER_AREA)


def _motion_scores(frame_paths: list[Path], preview_width: int) -> list[MotionFrameScore]:
    previous = _load_gray_preview(frame_paths[0], preview_width)
    scores = [MotionFrameScore(index=0, score=0.0)]
    for index, path in enumerate(frame_paths[1:], start=1):
        current = _load_gray_preview(path, preview_width)
        if current.shape != previous.shape:
            raise MotionSelectionError("all frames must have matching dimensions")
        difference = cv2.absdiff(previous, current)
        scores.append(MotionFrameScore(index=index, score=float(np.mean(difference) / 255.0)))
        previous = current
    return scores


def _uniform_anchors(frame_count: int, target_count: int) -> set[int]:
    if target_count <= 1:
        return {0}
    return {
        round(position * (frame_count - 1) / (target_count - 1))
        for position in range(target_count)
    }


def select_motion_frames(
    frames_path: str | Path,
    *,
    max_frames: int,
    preview_width: int = 192,
    uniform_fraction: float = 0.5,
) -> MotionSelection:
    """Select a bounded frame subset while preserving coverage and motion peaks."""

    directory = Path(frames_path).expanduser()
    if not directory.is_dir():
        raise MotionSelectionError("frames_path must reference an existing directory")
    frame_paths = sorted(directory.glob("frame_*.png"))
    if len(frame_paths) < 2:
        raise MotionSelectionError("frames_path must contain at least two frame_*.png files")
    if not isinstance(max_frames, int) or max_frames < 2:
        raise MotionSelectionError("max_frames must be an integer of at least 2")
    if not 0.0 <= float(uniform_fraction) <= 1.0:
        raise MotionSelectionError("uniform_fraction must be between 0 and 1")

    scores = _motion_scores(frame_paths, preview_width)
    target_count = min(max_frames, len(frame_paths))
    if target_count == len(frame_paths):
        selected = tuple(range(len(frame_paths)))
        return MotionSelection(len(frame_paths), selected, tuple(scores))

    uniform_count = max(2, min(target_count, round(target_count * uniform_fraction)))
    selected_indices = _uniform_anchors(len(frame_paths), uniform_count)
    selected_indices.update({0, len(frame_paths) - 1})

    ranked_motion = sorted(scores[1:], key=lambda item: (-item.score, item.index))
    for candidate in ranked_motion:
        if len(selected_indices) >= target_count:
            break
        selected_indices.add(candidate.index)

    selected = tuple(sorted(selected_indices))
    if len(selected) != target_count:
        raise MotionSelectionError("failed to produce the requested deterministic frame count")
    return MotionSelection(len(frame_paths), selected, tuple(scores))
