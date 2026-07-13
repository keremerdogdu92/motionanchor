from __future__ import annotations

import io
import json
import unittest

from motionanchor_worker.jobs import JobNotFoundError
from motionanchor_worker.protocol import envelope_to_json, make_envelope
from motionanchor_worker.worker import run_loop


class FakeJobs:
    def __init__(self) -> None:
        self.cancel_requests: list[str] = []

    def submit_extract_frames(self, source: str, output: str) -> str:
        return "job-123"

    def submit_sam2_rgba(self, frames: str, output: str, prompt: str, **settings) -> str:
        return "job-sam2"

    def status(self, job_id: str) -> dict:
        if job_id == "unknown-job":
            raise JobNotFoundError(job_id)
        return {"job_id": job_id, "operation": "media.extract_frames", "status": "running", "progress": 0.5, "message": "extracting", "result": None, "error": None, "created_at": 1.0, "updated_at": 2.0, "cancellation_requested": False}

    def cancel(self, job_id: str) -> bool:
        self.cancel_requests.append(job_id)
        return True


def run_messages(messages: list[dict], jobs: FakeJobs) -> list[dict]:
    data = "".join(envelope_to_json(item).decode("utf-8") for item in messages)
    stdin = io.StringIO(data)
    stdout = io.BytesIO()
    stderr = io.StringIO()
    run_loop(stdin, stdout, stderr, media_jobs=jobs)
    return [json.loads(line) for line in stdout.getvalue().decode("utf-8").splitlines()]


class TestJobProtocol(unittest.TestCase):
    def test_submit_returns_job_id(self) -> None:
        request = make_envelope(
            message_type="job.submit.media.extract_frames",
            message_id="submit-1",
            payload={"source_path": "source.mp4", "output_path": "frames"},
        )
        response = run_messages([request], FakeJobs())[1]
        self.assertEqual(response["type"], "job.accepted")
        self.assertEqual(response["message_id"], "submit-1")
        self.assertEqual(response["job_id"], "job-123")

    def test_submit_sam2_rgba_returns_job_id(self) -> None:
        request = make_envelope(
            message_type="job.submit.segmentation.sam2_rgba",
            message_id="submit-sam2",
            payload={
                "frames_path": "frames",
                "output_path": "rgba",
                "prompt_path": "prompts.json",
                "model": "small",
                "feather_radius": 1.5,
                "defringe": True,
            },
        )
        response = run_messages([request], FakeJobs())[1]
        self.assertEqual(response["type"], "job.accepted")
        self.assertEqual(response["job_id"], "job-sam2")
        self.assertEqual(response["payload"]["operation"], "segmentation.sam2_rgba")

    def test_status_returns_snapshot(self) -> None:
        request = make_envelope(
            message_type="job.status",
            message_id="status-1",
            job_id="job-123",
            payload={},
        )
        response = run_messages([request], FakeJobs())[1]
        self.assertEqual(response["type"], "job.status_result")
        self.assertEqual(response["payload"]["status"], "running")
        self.assertEqual(response["payload"]["progress"], 0.5)

    def test_cancel_returns_acceptance(self) -> None:
        jobs = FakeJobs()
        request = make_envelope(
            message_type="job.cancel",
            message_id="cancel-1",
            job_id="job-123",
            payload={},
        )
        response = run_messages([request], jobs)[1]
        self.assertEqual(response["type"], "job.cancel_result")
        self.assertTrue(response["payload"]["accepted"])
        self.assertEqual(jobs.cancel_requests, ["job-123"])

    def test_unknown_job_is_structured(self) -> None:
        request = make_envelope(
            message_type="job.status",
            message_id="status-missing",
            job_id="unknown-job",
            payload={},
        )
        response = run_messages([request], FakeJobs())[1]
        self.assertEqual(response["type"], "error")
        self.assertEqual(response["payload"]["code"], "job_not_found")

    def test_submit_requires_paths(self) -> None:
        request = make_envelope(
            message_type="job.submit.media.extract_frames",
            message_id="submit-invalid",
            payload={},
        )
        response = run_messages([request], FakeJobs())[1]
        self.assertEqual(response["type"], "error")
        self.assertEqual(response["payload"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
