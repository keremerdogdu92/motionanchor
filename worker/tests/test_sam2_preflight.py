# worker/tests/test_sam2_preflight.py
"""Tests for the isolated SAM 2 runtime readiness contract."""

from __future__ import annotations

import json
import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from motionanchor_worker.segmentation.sam2_job import probe_sam2_runtime


class Sam2PreflightTests(unittest.TestCase):
    @patch("motionanchor_worker.segmentation.sam2_job.subprocess.run")
    def test_ready_report_requires_cuda_and_verified_checkpoint(self, run_mock) -> None:
        run_mock.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({
                "python": "python.exe",
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


if __name__ == "__main__":
    unittest.main()
