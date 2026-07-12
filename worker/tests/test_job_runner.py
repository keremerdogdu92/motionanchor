from __future__ import annotations

import time
import unittest

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
        runner = JobRunner()

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
        runner = JobRunner()

        def work(report, cancelled):
            raise RuntimeError("simulated failure")

        snapshot = wait_terminal(runner, runner.submit("fixture.fail", work))
        self.assertEqual(snapshot["status"], "failed")
        self.assertEqual(snapshot["error"]["code"], "job_failed")
        self.assertIn("simulated failure", snapshot["error"]["message"])

    def test_cooperative_cancellation(self) -> None:
        runner = JobRunner()

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
        runner = JobRunner()
        with self.assertRaises(JobNotFoundError):
            runner.snapshot("missing")

    def test_terminal_job_cannot_be_cancelled(self) -> None:
        runner = JobRunner()
        job_id = runner.submit("fixture.done", lambda report, cancelled: {})
        wait_terminal(runner, job_id)
        self.assertFalse(runner.cancel(job_id))

    def test_progress_is_clamped(self) -> None:
        runner = JobRunner()

        def work(report, cancelled):
            report(9.0, "too high")
            return {}

        snapshot = wait_terminal(runner, runner.submit("fixture.clamp", work))
        self.assertEqual(snapshot["progress"], 1.0)


if __name__ == "__main__":
    unittest.main()
