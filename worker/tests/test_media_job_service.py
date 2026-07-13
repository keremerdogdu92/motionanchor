from __future__ import annotations

import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path

from motionanchor_worker.jobs.media import MediaJobService
import motionanchor_worker.jobs.media as media_jobs_module


@dataclass(frozen=True)
class FakeRecord:
    index: int
    timestamp_seconds: float


class FakeAdapter:
    def extract_png_frames_cancellable(self, source, output, *, report, cancelled):
        output.mkdir(parents=True, exist_ok=True)
        for step in range(5):
            if cancelled():
                return []
            report(step / 5.0, f"step {step}")
            time.sleep(0.005)
        (output / "frames.json").write_text("[]", encoding="utf-8")
        return [FakeRecord(0, 0.0), FakeRecord(1, 0.25)]


def wait_terminal(service: MediaJobService, job_id: str) -> dict:
    deadline = time.time() + 2.0
    while time.time() < deadline:
        snapshot = service.status(job_id)
        if snapshot["status"] in {"completed", "failed", "cancelled"}:
            return snapshot
        time.sleep(0.005)
    raise AssertionError("job did not finish")


class TestMediaJobService(unittest.TestCase):
    def test_extract_job_completes_with_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.touch()
            output = Path(tmp) / "frames"
            service = MediaJobService(adapter_factory=FakeAdapter)
            job_id = service.submit_extract_frames(str(source), str(output))
            snapshot = wait_terminal(service, job_id)
            self.assertEqual(snapshot["status"], "completed")
            self.assertEqual(snapshot["result"]["frame_count"], 2)
            self.assertTrue(snapshot["result"]["manifest_path"].endswith("frames.json"))

    def test_sam2_job_completes_with_report(self) -> None:
        original = media_jobs_module.run_sam2_rgba_job
        media_jobs_module.run_sam2_rgba_job = lambda **kwargs: {"frame_count": 2, "rgba_path": "rgba"}
        try:
            service = MediaJobService(adapter_factory=FakeAdapter)
            job_id = service.submit_sam2_rgba("frames", "output", "prompts.json")
            snapshot = wait_terminal(service, job_id)
            self.assertEqual(snapshot["status"], "completed")
            self.assertEqual(snapshot["operation"], "segmentation.sam2_rgba")
            self.assertEqual(snapshot["result"]["frame_count"], 2)
        finally:
            media_jobs_module.run_sam2_rgba_job = original

    def test_extract_job_can_be_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.touch()
            output = Path(tmp) / "frames"
            service = MediaJobService(adapter_factory=FakeAdapter)
            job_id = service.submit_extract_frames(str(source), str(output))
            self.assertTrue(service.cancel(job_id))
            snapshot = wait_terminal(service, job_id)
            self.assertEqual(snapshot["status"], "cancelled")
            self.assertIsNone(snapshot["result"])


if __name__ == "__main__":
    unittest.main()
