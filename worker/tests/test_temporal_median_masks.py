from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from motionanchor_worker.masks import TemporalMedianMaskEngine


class TestTemporalMedianMaskEngine(unittest.TestCase):
    def test_requires_fit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "frame.png"
            self.assertTrue(cv2.imwrite(str(source), np.zeros((32, 48, 3), np.uint8)))
            with self.assertRaises(RuntimeError):
                TemporalMedianMaskEngine().create_mask(source, root / "mask.png")

    def test_extracts_moving_subject_from_static_background(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            frames = []
            for index, x in enumerate((8, 24, 40, 56, 72)):
                image = np.full((64, 96, 3), (160, 160, 160), dtype=np.uint8)
                cv2.rectangle(image, (x, 20), (x + 15, 48), (20, 40, 180), -1)
                path = root / f"frame_{index}.png"
                self.assertTrue(cv2.imwrite(str(path), image))
                frames.append(path)
            engine = TemporalMedianMaskEngine(sample_count=5, lab_distance_threshold=10)
            engine.fit(frames)
            result = engine.create_mask(frames[2], root / "mask.png")
            mask = cv2.imread(str(root / "mask.png"), cv2.IMREAD_GRAYSCALE)
            self.assertGreater(int(mask[30, 45]), 0)
            self.assertEqual(int(mask[0, 0]), 0)
            self.assertLess(result.foreground_ratio, 0.2)


if __name__ == "__main__":
    unittest.main()
