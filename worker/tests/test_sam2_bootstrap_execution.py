from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from motionanchor_worker.segmentation.sam2_bootstrap import (
    render_sam2_bootstrap_script,
    run_sam2_bootstrap_job,
)

TRUSTED_SCRIPT = render_sam2_bootstrap_script()


class TestSam2BootstrapExecution(unittest.TestCase):
    def test_rejects_untrusted_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "setup.ps1"
            script.write_text("Write-Host nope\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-MotionAnchor"):
                run_sam2_bootstrap_job(str(script), lambda *_: None, lambda: False, command=[sys.executable, "-c", "print('x')"], preflight=lambda: {"ready": True})

    def test_returns_bounded_log_and_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "setup.ps1"
            script.write_text(TRUSTED_SCRIPT, encoding="utf-8")
            code = "import sys; [print(f'line-{i}') for i in range(250)]; print('MA_PROGRESS:0.95:verify')"
            updates = []
            result = run_sam2_bootstrap_job(str(script), lambda p, m: updates.append((p, m)), lambda: False, command=[sys.executable, "-u", "-c", code], preflight=lambda: {"ready": True, "readiness_errors": []})
            self.assertFalse(result["cancelled"])
            self.assertEqual(len(result["log"]), 200)
            self.assertEqual(result["log"][0], "line-51")
            self.assertTrue(any(progress == 0.95 for progress, _ in updates))
            self.assertEqual(updates[-1], (1.0, "SAM 2 runtime ready"))

    def test_cancellation_terminates_child(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "setup.ps1"
            script.write_text(TRUSTED_SCRIPT, encoding="utf-8")
            cancelled = threading.Event()
            timer = threading.Timer(0.2, cancelled.set)
            timer.start()
            try:
                result = run_sam2_bootstrap_job(str(script), lambda *_: None, cancelled.is_set, command=[sys.executable, "-u", "-c", "import time; print('started'); time.sleep(30)"], preflight=lambda: {"ready": True})
            finally:
                timer.cancel()
            self.assertTrue(result["cancelled"])
            self.assertIn("started", result["log"])


if __name__ == "__main__":
    unittest.main()
