# worker/tests/test_alpha_matte.py
"""Tests deterministic inward alpha feathering and RGBA composition."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from motionanchor_worker.masks import build_inward_alpha, compose_rgba_cutout


class AlphaMatteTests(unittest.TestCase):
    def test_zero_radius_preserves_binary_mask(self) -> None:
        mask = np.zeros((12, 12), dtype=np.uint8)
        mask[3:9, 3:9] = 255
        alpha = build_inward_alpha(mask, feather_radius=0)
        self.assertTrue(np.array_equal(alpha, mask))

    def test_feathering_never_adds_external_foreground(self) -> None:
        mask = np.zeros((16, 16), dtype=np.uint8)
        mask[4:12, 4:12] = 255
        alpha = build_inward_alpha(mask, feather_radius=2.0)
        self.assertEqual(int(alpha[3, 8]), 0)
        self.assertGreater(int(alpha[4, 8]), 0)
        self.assertEqual(int(alpha[8, 8]), 255)

    def test_invalid_radius_is_rejected(self) -> None:
        mask = np.zeros((4, 4), dtype=np.uint8)
        with self.assertRaises(ValueError):
            build_inward_alpha(mask, feather_radius=-1)

    def test_composition_is_deterministic_and_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.png"
            mask_path = root / "mask.png"
            image = np.full((20, 24, 3), (40, 80, 160), dtype=np.uint8)
            mask = np.zeros((20, 24), dtype=np.uint8)
            mask[4:16, 6:18] = 255
            self.assertTrue(cv2.imwrite(str(source), image))
            self.assertTrue(cv2.imwrite(str(mask_path), mask))

            first = compose_rgba_cutout(source, mask_path, root / "first.png")
            second = compose_rgba_cutout(source, mask_path, root / "second.png")
            self.assertEqual(first.sha256, second.sha256)
            self.assertGreater(first.translucent_pixels, 0)
            self.assertGreater(first.opaque_pixels, 0)

            rgba = cv2.imread(str(root / "first.png"), cv2.IMREAD_UNCHANGED)
            self.assertEqual(rgba.shape, (20, 24, 4))
            self.assertEqual(int(rgba[0, 0, 3]), 0)
            self.assertEqual(int(rgba[10, 12, 3]), 255)

    def test_defringe_replaces_translucent_background_color(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.png"
            mask_path = root / "mask.png"
            image = np.full((12, 12, 3), (240, 240, 240), dtype=np.uint8)
            image[3:9, 3:9] = (20, 40, 180)
            mask = np.zeros((12, 12), dtype=np.uint8)
            mask[3:9, 3:9] = 255
            self.assertTrue(cv2.imwrite(str(source), image))
            self.assertTrue(cv2.imwrite(str(mask_path), mask))

            compose_rgba_cutout(source, mask_path, root / "cutout.png", feather_radius=2.0)
            rgba = cv2.imread(str(root / "cutout.png"), cv2.IMREAD_UNCHANGED)
            self.assertGreater(int(rgba[3, 6, 3]), 0)
            self.assertLess(int(rgba[3, 6, 3]), 255)
            self.assertTrue(np.array_equal(rgba[3, 6, :3], np.array([20, 40, 180], dtype=np.uint8)))

    def test_existing_output_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.png"
            mask_path = root / "mask.png"
            output = root / "cutout.png"
            self.assertTrue(cv2.imwrite(str(source), np.zeros((4, 4, 3), dtype=np.uint8)))
            self.assertTrue(cv2.imwrite(str(mask_path), np.zeros((4, 4), dtype=np.uint8)))
            output.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                compose_rgba_cutout(source, mask_path, output)


if __name__ == "__main__":
    unittest.main()
