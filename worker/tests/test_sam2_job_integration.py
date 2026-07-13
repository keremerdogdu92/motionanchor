# worker/tests/test_sam2_job_integration.py
"""Integration tests for isolated SAM 2 process supervision and publication."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from motionanchor_worker.segmentation.sam2_job import run_sam2_rgba_job


FAKE_RUNNER = r'''from __future__ import annotations
import json
import sys
from pathlib import Path
request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
output = Path(request["output_path"])
(output / "masks").mkdir(parents=True)
(output / "rgba").mkdir()
(output / "shared_canvas").mkdir()
(output / "masks" / "frame_000000.png").write_bytes(b"mask")
(output / "rgba" / "frame_000000.png").write_bytes(b"rgba")
(output / "shared_canvas" / "frame_000000.png").write_bytes(b"normalized")
(output / "shared_canvas" / "shared-canvas-report.json").write_text("{}", encoding="utf-8")
report = output / "sam2-rgba-report.json"
report.write_text("{}", encoding="utf-8")
print(json.dumps({"type": "progress", "progress": 0.5, "message": "fake processing"}), flush=True)
print(json.dumps({"type": "result", "payload": {
    "engine_id": "fake.sam2",
    "frame_count": 1,
    "masks_path": str(output / "masks"),
    "rgba_path": str(output / "rgba"),
    "normalized_rgba_path": str(output / "shared_canvas"),
    "shared_canvas_report_path": str(output / "shared_canvas" / "shared-canvas-report.json"),
    "report_path": str(report),
}}), flush=True)
'''


class Sam2JobIntegrationTests(unittest.TestCase):
    def test_child_result_is_atomically_published_and_rebased(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = root / "frames"
            frames.mkdir()
            (frames / "frame_000000.png").write_bytes(b"frame")
            prompts = root / "prompts.json"
            prompts.write_text('{"anchors": [{"frame_index": 0, "box": [0, 0, 1, 1], "positive": [[0, 0]], "negative": []}]}', encoding="utf-8")
            runner = root / "fake_runner.py"
            runner.write_text(FAKE_RUNNER, encoding="utf-8")
            output = root / "published"
            progress: list[float] = []
            with patch.dict(os.environ, {"MOTIONANCHOR_SAM2_RUNNER": str(runner)}):
                result = run_sam2_rgba_job(
                    frames_path=str(frames),
                    output_path=str(output),
                    prompt_path=str(prompts),
                    model="small",
                    feather_radius=1.5,
                    defringe=True,
                    report=lambda value, _message: progress.append(value),
                    cancelled=lambda: False,
                )
            self.assertEqual(result["engine_id"], "fake.sam2")
            self.assertEqual(Path(result["output_path"]), output.resolve())
            self.assertEqual(Path(result["masks_path"]), output.resolve() / "masks")
            self.assertEqual(Path(result["rgba_path"]), output.resolve() / "rgba")
            self.assertEqual(Path(result["normalized_rgba_path"]), output.resolve() / "shared_canvas")
            self.assertTrue(Path(result["shared_canvas_report_path"]).is_file())
            self.assertTrue(Path(result["report_path"]).is_file())
            self.assertTrue((output / "rgba" / "frame_000000.png").is_file())
            self.assertEqual(progress[-1], 1.0)


if __name__ == "__main__":
    unittest.main()
