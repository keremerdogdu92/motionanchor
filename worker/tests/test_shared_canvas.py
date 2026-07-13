# worker/tests/test_shared_canvas.py
"""Contract tests for deterministic shared-canvas RGBA normalization."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from motionanchor_worker.masks import build_shared_canvas_plan, normalize_rgba_sequence


class SharedCanvasTests(unittest.TestCase):
    def _write_frame(self, path: Path, bbox: tuple[int, int, int, int]) -> None:
        image = np.zeros((32, 40, 4), dtype=np.uint8)
        x, y, width, height = bbox
        image[y:y + height, x:x + width, :3] = (20, 80, 180)
        image[y:y + height, x:x + width, 3] = 255
        self.assertTrue(cv2.imwrite(str(path), image))

    def test_plan_uses_union_bounds_padding_and_natural_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_frame(root / "frame_10.png", (18, 8, 8, 12))
            self._write_frame(root / "frame_2.png", (10, 6, 8, 16))
            plan = build_shared_canvas_plan(list(root.glob("*.png")), padding=4)
            self.assertTrue(plan.frame_paths[0].endswith("frame_2.png"))
            self.assertEqual(plan.crop_xywh, (10, 6, 16, 16))
            self.assertEqual((plan.canvas_width, plan.canvas_height), (24, 24))
            self.assertEqual(plan.baseline_y, 20)
            self.assertAlmostEqual(plan.pivot_y, 4 / 24)

    def test_normalization_preserves_relative_motion_and_safe_edges(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "frame_1.png"
            second = root / "frame_2.png"
            self._write_frame(first, (8, 10, 6, 10))
            self._write_frame(second, (20, 6, 6, 14))

            result = normalize_rgba_sequence([second, first], root / "normalized", padding=3)
            self.assertEqual(result.frame_count, 2)
            self.assertEqual((result.canvas_width, result.canvas_height), (24, 20))
            normalized_first = cv2.imread(
                str(root / "normalized" / "frame_1.png"), cv2.IMREAD_UNCHANGED
            )
            normalized_second = cv2.imread(
                str(root / "normalized" / "frame_2.png"), cv2.IMREAD_UNCHANGED
            )
            first_points = cv2.findNonZero(normalized_first[:, :, 3])
            second_points = cv2.findNonZero(normalized_second[:, :, 3])
            self.assertEqual(cv2.boundingRect(first_points), (3, 7, 6, 10))
            self.assertEqual(cv2.boundingRect(second_points), (15, 3, 6, 14))
            self.assertFalse(np.any(normalized_first[0, :, 3]))
            self.assertFalse(np.any(normalized_second[:, -1, 3]))

    def test_normalization_is_deterministic_and_non_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            frame = root / "frame.png"
            self._write_frame(frame, (9, 7, 12, 18))
            first = normalize_rgba_sequence([frame], root / "first", padding=5)
            second = normalize_rgba_sequence([frame], root / "second", padding=5)
            self.assertEqual(first.sequence_sha256, second.sequence_sha256)
            self.assertTrue(Path(first.report_path).is_file())
            with self.assertRaises(FileExistsError):
                normalize_rgba_sequence([frame], root / "first", padding=5)

    def test_rejects_empty_foreground_and_dimension_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            empty = root / "empty.png"
            valid = root / "valid.png"
            mismatched = root / "mismatched.png"
            self.assertTrue(cv2.imwrite(str(empty), np.zeros((32, 40, 4), dtype=np.uint8)))
            self._write_frame(valid, (4, 4, 8, 8))
            other = np.zeros((24, 40, 4), dtype=np.uint8)
            other[4:12, 4:12, 3] = 255
            self.assertTrue(cv2.imwrite(str(mismatched), other))
            with self.assertRaises(ValueError):
                build_shared_canvas_plan([empty])
            with self.assertRaises(ValueError):
                build_shared_canvas_plan([valid, mismatched])

    def test_invalid_padding_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_shared_canvas_plan([], padding=-1)


if __name__ == "__main__":
    unittest.main()
