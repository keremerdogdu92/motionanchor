"""Acceptance tests for the committed real Cat Trap fixture."""
from __future__ import annotations

import unittest
from pathlib import Path

from motionanchor_worker.acceptance import validate_cat_trap_fixture


class CatTrapAcceptanceTests(unittest.TestCase):
    def test_real_cat_trap_fixture_passes_release_gate(self) -> None:
        root = Path(__file__).resolve().parents[2] / "fixtures" / "cat-trap"
        report = validate_cat_trap_fixture(root)
        failures = [f"{check.name}: {check.detail}" for check in report.checks if not check.passed]
        self.assertTrue(report.passed, failures)
        self.assertEqual(report.frame_count, 240)
        self.assertEqual(report.selected_count, 8)
        self.assertEqual(report.rgba_count, 240)
        self.assertEqual((report.width, report.height), (1280, 720))
        self.assertEqual(len(report.sequence_sha256), 64)


if __name__ == "__main__":
    unittest.main()
