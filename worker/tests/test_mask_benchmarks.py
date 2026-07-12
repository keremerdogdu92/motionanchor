from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from motionanchor_worker.benchmarks import compare_masks


class TestMaskBenchmarks(unittest.TestCase):
    def test_identical_masks_score_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mask = np.zeros((32, 48), dtype=np.uint8)
            mask[5:27, 9:39] = 255
            first = root / "first.png"
            second = root / "second.png"
            self.assertTrue(cv2.imwrite(str(first), mask))
            self.assertTrue(cv2.imwrite(str(second), mask))

            result = compare_masks(first, second)
            self.assertEqual(result.intersection_over_union, 1.0)
            self.assertEqual(result.precision, 1.0)
            self.assertEqual(result.recall, 1.0)
            self.assertEqual(result.boundary_f1, 1.0)

    def test_shifted_mask_reports_quality_loss(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            expected = np.zeros((32, 48), dtype=np.uint8)
            predicted = np.zeros((32, 48), dtype=np.uint8)
            expected[8:24, 12:32] = 255
            predicted[8:24, 16:36] = 255
            expected_path = root / "expected.png"
            predicted_path = root / "predicted.png"
            self.assertTrue(cv2.imwrite(str(expected_path), expected))
            self.assertTrue(cv2.imwrite(str(predicted_path), predicted))

            result = compare_masks(predicted_path, expected_path)
            self.assertLess(result.intersection_over_union, 1.0)
            self.assertLess(result.precision, 1.0)
            self.assertLess(result.recall, 1.0)
            self.assertGreater(result.boundary_f1, 0.0)

    def test_dimension_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.png"
            second = root / "second.png"
            self.assertTrue(cv2.imwrite(str(first), np.zeros((8, 8), dtype=np.uint8)))
            self.assertTrue(cv2.imwrite(str(second), np.zeros((9, 8), dtype=np.uint8)))
            with self.assertRaises(ValueError):
                compare_masks(first, second)


if __name__ == "__main__":
    unittest.main()
