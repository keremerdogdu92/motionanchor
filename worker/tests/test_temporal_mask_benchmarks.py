from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from motionanchor_worker.benchmarks.temporal import compare_temporal_masks


class TestTemporalMaskBenchmarks(unittest.TestCase):
    def test_identical_masks_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = []
            for index in range(3):
                mask = np.zeros((40, 60), dtype=np.uint8)
                mask[10:30, 20:40] = 255
                path = root / f"mask-{index}.png"
                self.assertTrue(cv2.imwrite(str(path), mask))
                paths.append(path)
            report = compare_temporal_masks(paths)
            self.assertEqual(report.mean_aligned_iou, 1.0)
            self.assertEqual(report.maximum_area_change_ratio, 0.0)
            self.assertEqual(report.mean_boundary_turnover_ratio, 0.0)

    def test_translation_is_removed_before_shape_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = []
            for index, offset in enumerate((0, 8)):
                mask = np.zeros((50, 80), dtype=np.uint8)
                mask[12:38, 20 + offset:44 + offset] = 255
                path = root / f"mask-{index}.png"
                self.assertTrue(cv2.imwrite(str(path), mask))
                paths.append(path)
            report = compare_temporal_masks(paths)
            self.assertGreater(report.mean_aligned_iou, 0.95)
            self.assertGreater(report.mean_centroid_shift_pixels, 7.0)

    def test_requires_two_masks(self) -> None:
        with self.assertRaises(ValueError):
            compare_temporal_masks([])


if __name__ == "__main__":
    unittest.main()
