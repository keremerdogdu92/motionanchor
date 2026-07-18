# worker/tests/test_motion_selection.py
"""Tests for deterministic, motion-preserving frame selection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from motionanchor_worker.media.motion_selection import MotionSelectionError, select_motion_frames


def write_frame(directory: Path, index: int, x_position: int, *, size: int = 64) -> None:
    image = np.zeros((size, size, 3), dtype=np.uint8)
    cv2.rectangle(image, (x_position, 20), (x_position + 10, 30), (255, 255, 255), -1)
    target = directory / f"frame_{index:06d}.png"
    if not cv2.imwrite(str(target), image):
        raise RuntimeError(f"failed to write test frame: {target}")


class MotionSelectionTests(unittest.TestCase):
    def test_preserves_endpoints_coverage_and_motion_peak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frames = Path(tmp)
            positions = [2, 3, 4, 5, 6, 40, 41, 42, 43, 44]
            for index, position in enumerate(positions):
                write_frame(frames, index, position)

            result = select_motion_frames(frames, max_frames=5, uniform_fraction=0.6)

            self.assertEqual(result.source_frame_count, 10)
            self.assertEqual(result.selected_indices[0], 0)
            self.assertEqual(result.selected_indices[-1], 9)
            self.assertIn(5, result.selected_indices)
            self.assertEqual(len(result.selected_indices), 5)

    def test_selection_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frames = Path(tmp)
            for index in range(12):
                write_frame(frames, index, (index * 3) % 40)

            first = select_motion_frames(frames, max_frames=6)
            second = select_motion_frames(frames, max_frames=6)

            self.assertEqual(first.selected_indices, second.selected_indices)
            self.assertEqual(first.scores, second.scores)

    def test_required_indices_are_retained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frames = Path(tmp)
            for index in range(12):
                write_frame(frames, index, index % 40)

            result = select_motion_frames(frames, max_frames=5, required_indices=(4, 8))

            self.assertEqual(len(result.selected_indices), 5)
            self.assertTrue({0, 4, 8, 11}.issubset(result.selected_indices))

    def test_returns_all_frames_when_below_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frames = Path(tmp)
            for index in range(4):
                write_frame(frames, index, index)

            result = select_motion_frames(frames, max_frames=8)

            self.assertEqual(result.selected_indices, (0, 1, 2, 3))

    def test_rejects_invalid_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frames = Path(tmp)
            write_frame(frames, 0, 0)

            with self.assertRaisesRegex(MotionSelectionError, "at least two"):
                select_motion_frames(frames, max_frames=4)

            write_frame(frames, 1, 1)
            with self.assertRaisesRegex(MotionSelectionError, "at least 2"):
                select_motion_frames(frames, max_frames=1)


if __name__ == "__main__":
    unittest.main()
