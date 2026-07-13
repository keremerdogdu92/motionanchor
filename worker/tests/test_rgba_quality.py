# worker/tests/test_rgba_quality.py
"""Tests for deterministic RGBA sequence diagnostics."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from motionanchor_worker.masks import analyze_rgba_frame, analyze_rgba_sequence


class RgbaQualityTests(unittest.TestCase):
    def _write_rgba(self, path: Path, alpha: np.ndarray) -> None:
        image = np.zeros((*alpha.shape, 4), dtype=np.uint8)
        image[:, :, :3] = (20, 40, 180)
        image[:, :, 3] = alpha
        self.assertTrue(cv2.imwrite(str(path), image))

    def test_reports_components_bbox_and_translucency(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "frame.png"
            alpha = np.zeros((20, 24), dtype=np.uint8)
            alpha[4:16, 5:18] = 255
            alpha[4, 5:18] = 128
            alpha[2:4, 20:22] = 255
            self._write_rgba(path, alpha)

            result = analyze_rgba_frame(path)
            self.assertEqual(result.bbox_xywh, (5, 2, 17, 14))
            self.assertEqual(result.component_count, 2)
            self.assertGreater(result.translucent_pixels, 0)
            self.assertFalse(result.touches_edge)

    def test_sequence_requires_matching_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.png"
            second = root / "second.png"
            self._write_rgba(first, np.full((8, 8), 255, dtype=np.uint8))
            self._write_rgba(second, np.full((9, 8), 255, dtype=np.uint8))

            with self.assertRaises(ValueError):
                analyze_rgba_sequence([first, second])

    def test_sequence_aggregates_empty_and_edge_touching_frames(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            empty = root / "empty.png"
            edge = root / "edge.png"
            alpha_empty = np.zeros((10, 12), dtype=np.uint8)
            alpha_edge = np.zeros((10, 12), dtype=np.uint8)
            alpha_edge[:, 0:3] = 255
            self._write_rgba(empty, alpha_empty)
            self._write_rgba(edge, alpha_edge)

            result = analyze_rgba_sequence([empty, edge])
            self.assertEqual(result.frame_count, 2)
            self.assertEqual(result.empty_frame_count, 1)
            self.assertEqual(result.edge_touch_frame_count, 1)
            self.assertEqual(result.maximum_component_count, 1)

    def test_empty_sequence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            analyze_rgba_sequence([])


if __name__ == "__main__":
    unittest.main()

    def test_sequence_requires_matching_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.png"
            second = root / "second.png"
            self._write_rgba(first, np.full((8, 8), 255, dtype=np.uint8))
            self._write_rgba(second, np.full((9, 8), 255, dtype=np.uint8))

            with self.assertRaises(ValueError):
                analyze_rgba_sequence([first, second])

    def test_sequence_aggregates_empty_and_edge_touching_frames(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            empty = root / "empty.png"
            edge = root / "edge.png"
            alpha_empty = np.zeros((10, 12), dtype=np.uint8)
            alpha_edge = np.zeros((10, 12), dtype=np.uint8)
            alpha_edge[:, 0:3] = 255
            self._write_rgba(empty, alpha_empty)
            self._write_rgba(edge, alpha_edge)

            result = analyze_rgba_sequence([empty, edge])
            self.assertEqual(result.frame_count, 2)
            self.assertEqual(result.empty_frame_count, 1)
            self.assertEqual(result.edge_touch_frame_count, 1)
            self.assertEqual(result.maximum_component_count, 1)

    def test_empty_sequence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            analyze_rgba_sequence([])


if __name__ == "__main__":
    unittest.main()
