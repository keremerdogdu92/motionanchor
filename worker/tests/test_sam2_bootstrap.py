# worker/tests/test_sam2_bootstrap.py
"""Tests deterministic, user-controlled SAM 2 bootstrap generation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from motionanchor_worker.segmentation.sam2_bootstrap import (
    SAM2_CHECKPOINT_SHA256,
    SAM2_CHECKPOINT_URL,
    build_sam2_bootstrap_plan,
    write_sam2_bootstrap_script,
)


class Sam2BootstrapTests(unittest.TestCase):
    def test_plan_exposes_pinned_runtime_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "bootstrap.ps1"
            with patch("shutil.which", return_value=r"C:\Windows\py.exe"):
                plan = build_sam2_bootstrap_plan(str(target))
            self.assertTrue(plan.ready_to_generate)
            self.assertEqual(plan.schema_version, 1)
            self.assertEqual(plan.checkpoint_url, SAM2_CHECKPOINT_URL)
            self.assertEqual(plan.checkpoint_sha256, SAM2_CHECKPOINT_SHA256)
            self.assertEqual([step.step_id for step in plan.steps], [
                "create_environment", "install_packages",
                "install_checkpoint", "verify_runtime",
            ])

    def test_write_is_non_destructive_and_contains_checksum_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "bootstrap.ps1"
            with patch("shutil.which", return_value=r"C:\Windows\py.exe"):
                result = write_sam2_bootstrap_script(str(target))
            script = target.read_text(encoding="utf-8")
            self.assertEqual(Path(result["script_path"]), target.resolve())
            self.assertIn(SAM2_CHECKPOINT_URL, script)
            self.assertIn(SAM2_CHECKPOINT_SHA256, script)
            self.assertIn("Get-FileHash", script)
            self.assertIn("Invoke-WebRequest", script)
            with patch("shutil.which", return_value=r"C:\Windows\py.exe"):
                with self.assertRaisesRegex(ValueError, "already exists"):
                    write_sam2_bootstrap_script(str(target))

    def test_missing_launcher_blocks_new_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "bootstrap.ps1"
            with patch("shutil.which", return_value=None), patch(
                "motionanchor_worker.segmentation.sam2_bootstrap.Path.is_file",
                return_value=False,
            ):
                plan = build_sam2_bootstrap_plan(str(target))
            self.assertFalse(plan.ready_to_generate)
            self.assertTrue(any("launcher" in blocker for blocker in plan.blockers))


if __name__ == "__main__":
    unittest.main()
