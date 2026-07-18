# worker/tests/test_sam2_preflight.py
"""Tests for the isolated SAM 2 runtime readiness contract."""

from __future__ import annotations

import json
import unittest
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

from motionanchor_worker.segmentation.sam2_job import Sam2ProcessError, _require_sam2_runtime, probe_sam2_runtime


class Sam2PreflightTests(unittest.TestCase):
    @patch("motionanchor_worker.segmentation.sam2_job.subprocess.run")
    def test_ready_report_requires_cuda_and_verified_checkpoint(self, run_mock) -> None:
        run_mock.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({
                "python": "python.exe",
                "python_version": "3.12.10",
                "packages": {name: {"available": True, "version": "test", "distribution": name, "error": None} for name in ("numpy", "cv2", "torch", "sam2")},
                "torch_available": True,
                "torch_version": "2.7.0",
                "cuda_available": True,
                "gpu": "RTX 3060 Ti",
                "vram_bytes": 8_000_000_000,
                "checkpoint_exists": True,
                "checkpoint_sha256": "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
            }),
            stderr="",
        )
        report = probe_sam2_runtime()
        self.assertTrue(report["ready"])
        self.assertTrue(report["checkpoint_valid"])

    @patch("motionanchor_worker.segmentation.sam2_job.subprocess.run")
    def test_invalid_checkpoint_blocks_runtime(self, run_mock) -> None:
        run_mock.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({
                "python": "python.exe",
                "python_version": "3.12.10",
                "packages": {name: {"available": True, "version": "test", "distribution": name, "error": None} for name in ("numpy", "cv2", "torch", "sam2")},
                "torch_available": True,
                "cuda_available": True,
                "checkpoint_exists": True,
                "checkpoint_sha256": "0" * 64,
            }),
            stderr="",
        )
        report = probe_sam2_runtime()
        self.assertFalse(report["ready"])
        self.assertFalse(report["checkpoint_valid"])

    @patch("motionanchor_worker.segmentation.sam2_job.subprocess.run")
    def test_missing_packages_are_reported_without_raising(self, run_mock) -> None:
        run_mock.return_value = CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({
                "python": "python.exe", "python_version": "3.12.10",
                "packages": {
                    "numpy": {"available": True}, "cv2": {"available": False},
                    "torch": {"available": False}, "sam2": {"available": False},
                },
                "torch_available": False, "cuda_available": False,
                "checkpoint_exists": True,
                "checkpoint_sha256": "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
            }), stderr="",
        )
        report = probe_sam2_runtime()
        self.assertFalse(report["ready"])
        self.assertEqual(report["missing_components"], ["cv2", "torch", "sam2"])
        self.assertTrue(report["readiness_errors"])

    @patch("motionanchor_worker.segmentation.sam2_job.subprocess.run")
    def test_timeout_is_reported_as_structured_process_error(self, run_mock) -> None:
        run_mock.side_effect = TimeoutExpired(cmd=["python"], timeout=90)

        with self.assertRaisesRegex(Sam2ProcessError, "preflight timed out"):
            probe_sam2_runtime()

    @patch("motionanchor_worker.segmentation.sam2_job.probe_sam2_runtime")
    def test_production_guard_blocks_incomplete_runtime(self, probe_mock) -> None:
        probe_mock.return_value = {
            "ready": False,
            "readiness_errors": ["Missing runtime packages: torch, sam2"],
        }
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(Sam2ProcessError, "Missing runtime packages"):
                _require_sam2_runtime()


if __name__ == "__main__":
    unittest.main()
