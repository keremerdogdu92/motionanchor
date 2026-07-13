from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from motionanchor_worker.jobs import JobNotFoundError, JobRunner


def wait_terminal(runner: JobRunner, job_id: str, timeout: float = 2.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        snapshot = runner.snapshot(job_id)
        if snapshot["status"] in {"completed", "failed", "cancelled"}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("job did not reach a terminal state")


class TestJobRunner(unittest.TestCase):
    def test_job_completes_with_progress_and_result(self) -> None:
        runner = JobRunner(state_path=False)

        def work(report, cancelled):
            self.assertFalse(cancelled())
            report(0.25, "starting")
            report(0.75, "working")
            return {"value": 42}

        job_id = runner.submit("fixture.work", work)
        snapshot = wait_terminal(runner, job_id)
        self.assertEqual(snapshot["status"], "completed")
        self.assertEqual(snapshot["progress"], 1.0)
        self.assertEqual(snapshot["result"], {"value": 42})

    def test_job_failure_is_structured(self) -> None:
        runner = JobRunner(state_path=False)

        def work(report, cancelled):
            raise RuntimeError("simulated failure")

        snapshot = wait_terminal(runner, runner.submit("fixture.fail", work))
        self.assertEqual(snapshot["status"], "failed")
        self.assertEqual(snapshot["error"]["code"], "job_failed")
        self.assertIn("simulated failure", snapshot["error"]["message"])

    def test_cooperative_cancellation(self) -> None:
        runner = JobRunner(state_path=False)

        def work(report, cancelled):
            for index in range(100):
                if cancelled():
                    return {"iterations": index}
                report(index / 100.0)
                time.sleep(0.005)
            return {"iterations": 100}

        job_id = runner.submit("fixture.cancel", work)
        time.sleep(0.03)
        self.assertTrue(runner.cancel(job_id))
        snapshot = wait_terminal(runner, job_id)
        self.assertEqual(snapshot["status"], "cancelled")
        self.assertTrue(snapshot["cancellation_requested"])
        self.assertIsNone(snapshot["result"])

    def test_unknown_job_raises(self) -> None:
        runner = JobRunner(state_path=False)
        with self.assertRaises(JobNotFoundError):
            runner.snapshot("missing")

    def test_terminal_job_cannot_be_cancelled(self) -> None:
        runner = JobRunner(state_path=False)
        job_id = runner.submit("fixture.done", lambda report, cancelled: {})
        wait_terminal(runner, job_id)
        self.assertFalse(runner.cancel(job_id))

    def test_progress_is_clamped(self) -> None:
        runner = JobRunner(state_path=False)

        def work(report, cancelled):
            report(9.0, "too high")
            return {}

        snapshot = wait_terminal(runner, runner.submit("fixture.clamp", work))
        self.assertEqual(snapshot["progress"], 1.0)

    def test_completed_job_is_restored_from_atomic_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "jobs.json"
            runner = JobRunner(state_path=state_path)
            job_id = runner.submit("fixture.persist", lambda report, cancelled: {"value": 7})
            wait_terminal(runner, job_id)
            deadline = time.time() + 2.0
            while time.time() < deadline:
                if state_path.is_file():
                    payload = json.loads(state_path.read_text(encoding="utf-8"))
                    if payload["jobs"][0]["status"] == "completed":
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("terminal snapshot was not persisted")
            restored = JobRunner(state_path=state_path).snapshot(job_id)
            self.assertEqual(restored["status"], "completed")
            self.assertEqual(restored["result"], {"value": 7})

    def test_incomplete_job_is_reconciled_as_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "jobs.json"
            state_path.write_text(json.dumps({
                "schema_version": 1,
                "jobs": [{
                    "job_id": "interrupted", "operation": "fixture.work",
                    "status": "running", "progress": 0.5, "message": "working",
                    "result": None, "error": None, "created_at": 1.0, "updated_at": 2.0,
                }],
            }), encoding="utf-8")
            snapshot = JobRunner(state_path=state_path).snapshot("interrupted")
            self.assertEqual(snapshot["status"], "failed")
            self.assertEqual(snapshot["error"]["code"], "job_interrupted")

    def test_corrupt_state_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "jobs.json"
            state_path.write_text("not-json", encoding="utf-8")
            runner = JobRunner(state_path=state_path)
            with self.assertRaises(JobNotFoundError):
                runner.snapshot("missing")


if __name__ == "__main__":
    unittest.main()
