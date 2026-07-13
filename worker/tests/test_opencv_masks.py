from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from motionanchor_worker.masks import ChromaKeyMaskEngine, ExistingAlphaMaskEngine


class TestOpenCvMaskEngines(unittest.TestCase):
    def test_existing_alpha_is_preserved_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "alpha.png"
            image = np.zeros((48, 64, 4), dtype=np.uint8)
            image[:, :, :3] = (40, 80, 160)
            image[8:40, 12:52, 3] = 255
            image[4:12, 30:34, 3] = 255
            self.assertTrue(cv2.imwrite(str(source), image))

            first = ExistingAlphaMaskEngine().create_mask(source, root / "mask-a.png")
            second = ExistingAlphaMaskEngine().create_mask(source, root / "mask-b.png")
            self.assertEqual(first.sha256, second.sha256)
            self.assertEqual(first.bbox_xywh, (12, 4, 40, 36))
            self.assertFalse(first.touches_edge)
            self.assertGreater(first.foreground_pixels, 0)

    def test_chroma_key_preserves_thin_non_green_features(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "green.png"
            image = np.full((64, 96, 3), (0, 255, 0), dtype=np.uint8)
            cv2.rectangle(image, (30, 18), (65, 55), (180, 80, 30), -1)
            cv2.line(image, (48, 18), (48, 4), (255, 255, 255), 2)
            cv2.line(image, (65, 30), (88, 10), (40, 40, 230), 2)
            self.assertTrue(cv2.imwrite(str(source), image))

            result = ChromaKeyMaskEngine().create_mask(source, root / "mask.png")
            mask = cv2.imread(str(root / "mask.png"), cv2.IMREAD_GRAYSCALE)
            self.assertIsNotNone(mask)
            self.assertGreater(int(mask[4, 48]), 0)
            self.assertGreater(int(mask[10, 88]), 0)
            self.assertFalse(result.touches_edge)
            self.assertEqual(result.engine_version, cv2.__version__)

    def test_output_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "alpha.png"
            image = np.zeros((8, 8, 4), dtype=np.uint8)
            self.assertTrue(cv2.imwrite(str(source), image))
            output = root / "mask.png"
            output.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                ExistingAlphaMaskEngine().create_mask(source, output)


if __name__ == "__main__":
    unittest.main()


class TestBorderConnectedMaskEngine(unittest.TestCase):
    def test_uniform_border_background_is_removed(self) -> None:
        from motionanchor_worker.masks import BorderConnectedMaskEngine

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "scene.png"
            image = np.full((80, 120, 3), (20, 30, 150), dtype=np.uint8)
            cv2.rectangle(image, (35, 20), (85, 70), (180, 80, 30), -1)
            cv2.line(image, (60, 20), (60, 5), (255, 255, 255), 2)
            self.assertTrue(cv2.imwrite(str(source), image))

            result = BorderConnectedMaskEngine().create_mask(source, root / "mask.png")
            mask = cv2.imread(str(root / "mask.png"), cv2.IMREAD_GRAYSCALE)
            self.assertEqual(int(mask[0, 0]), 0)
            self.assertGreater(int(mask[40, 60]), 0)
            self.assertGreater(int(mask[5, 60]), 0)
            self.assertFalse(result.touches_edge)

    def test_disconnected_matching_color_is_preserved(self) -> None:
        from motionanchor_worker.masks import BorderConnectedMaskEngine

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "scene.png"
            image = np.full((64, 96, 3), (20, 30, 150), dtype=np.uint8)
            cv2.rectangle(image, (24, 16), (72, 56), (80, 120, 220), -1)
            cv2.circle(image, (48, 36), 8, (20, 30, 150), -1)
            self.assertTrue(cv2.imwrite(str(source), image))

            BorderConnectedMaskEngine().create_mask(source, root / "mask.png")
            mask = cv2.imread(str(root / "mask.png"), cv2.IMREAD_GRAYSCALE)
            self.assertGreater(int(mask[36, 48]), 0)
