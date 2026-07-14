# worker/tests/test_export_quality_gates.py
"""Tests conservative deterministic quality gates for exportable RGBA sequences."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from motionanchor_worker.masks import evaluate_export_quality


class ExportQualityGateTests(unittest.TestCase):
    def _write(self, path: Path, alpha: np.ndarray, value: int = 120) -> None:
        image = np.full((*alpha.shape, 4), value, dtype=np.uint8)
        image[:, :, 3] = alpha
        self.assertTrue(cv2.imwrite(str(path), image))

    def test_blocks_empty_foreground_and_edge_contact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            empty = root / "frame_1.png"
            edge = root / "frame_2.png"
            self._write(empty, np.zeros((16, 16), dtype=np.uint8))
            alpha = np.zeros((16, 16), dtype=np.uint8)
            alpha[2:12, 0:8] = 255
            self._write(edge, alpha)
            report = evaluate_export_quality([empty, edge])
            self.assertEqual(report.status, "blocked")
            self.assertEqual({finding.code for finding in report.blockers}, {
                "empty_foreground", "foreground_touches_canvas_edge"
            })

    def test_warns_for_exact_duplicates_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "frame_1.png"
            second = root / "frame_2.png"
            alpha = np.zeros((20, 20), dtype=np.uint8)
            alpha[4:16, 4:16] = 255
            self._write(first, alpha)
            self._write(second, alpha)
            report = evaluate_export_quality([first, second])
            self.assertEqual(report.status, "warning")
            self.assertFalse(report.blockers)
            self.assertEqual(report.exact_duplicate_pairs, ((1, 2),))

    def test_clean_sequence_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = []
            for index, offset in enumerate((3, 4, 5), start=1):
                path = root / f"frame_{index}.png"
                alpha = np.zeros((24, 24), dtype=np.uint8)
                alpha[5:19, offset:offset + 10] = 255
                self._write(path, alpha, value=80 + index * 20)
                paths.append(path)
            report = evaluate_export_quality(paths)
            self.assertEqual(report.status, "passed")
            self.assertFalse(report.blockers)
            self.assertFalse(report.warnings)

    def test_warns_for_calibrated_area_jump(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = []
            for index, width in enumerate((10, 13), start=1):
                path = root / f"frame_{index}.png"
                alpha = np.zeros((30, 30), dtype=np.uint8)
                alpha[5:25, 5:5 + width] = 255
                self._write(path, alpha, value=80 + index * 20)
                paths.append(path)
            report = evaluate_export_quality(paths)
            self.assertEqual(report.status, "warning")
            self.assertIn("foreground_area_jump", {finding.code for finding in report.warnings})

    def test_warns_only_for_substantial_detached_components(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "frame_1.png"
            alpha = np.zeros((40, 40), dtype=np.uint8)
            alpha[8:30, 8:25] = 255
            alpha[10:22, 29:37] = 255
            self._write(path, alpha)
            report = evaluate_export_quality([path])
            self.assertIn("detached_foreground_components", {finding.code for finding in report.warnings})

    def test_real_cat_trap_dash_report_fits_calibrated_geometry_thresholds(self) -> None:
        report_path = Path(__file__).resolve().parents[2] / "fixtures/cat-trap/dash/sam2-small-rgba-quality-report.json"
        data = json.loads(report_path.read_text(encoding="utf-8"))
        frames = data["frames"]
        ratios = [frame["foreground_ratio"] for frame in frames]
        maximum_jump = max(max(left, right) / min(left, right) for left, right in zip(ratios, ratios[1:]))
        self.assertLess(maximum_jump, 1.25)
        self.assertGreaterEqual(min(frame["largest_component_ratio"] for frame in frames), 0.98)


if __name__ == "__main__":
    unittest.main()
