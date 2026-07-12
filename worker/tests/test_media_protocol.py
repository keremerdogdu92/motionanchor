from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from motionanchor_worker.media.ffmpeg import FrameRecord, MediaProbe, MediaToolError
from motionanchor_worker.protocol import envelope_to_json, make_envelope
from motionanchor_worker.worker import run_loop


class FakeAdapter:
    def probe(self, source: Path) -> MediaProbe:
        return MediaProbe(
            path=str(source.resolve()),
            codec="h264",
            width=1280,
            height=720,
            duration_seconds=10.0,
            avg_frame_rate="24/1",
            real_frame_rate="24/1",
            frame_count=240,
            variable_frame_rate=False,
        )

    def extract_png_frames(self, source: Path, output: Path) -> list[FrameRecord]:
        output.mkdir(parents=True, exist_ok=True)
        (output / "frames.json").write_text("[]", encoding="utf-8")
        return [
            FrameRecord(0, 0.0, 1 / 24, "I", "frame_000000.png"),
            FrameRecord(1, 1 / 24, 1 / 24, "P", "frame_000001.png"),
        ]


def run_request(message_type: str, payload: dict, message_id: str = "media-1") -> list[dict]:
    request = make_envelope(
        message_type=message_type,
        message_id=message_id,
        job_id="job-1",
        payload=payload,
    )
    stdin = io.StringIO(envelope_to_json(request).decode("utf-8"))
    stdout = io.BytesIO()
    stderr = io.StringIO()
    run_loop(stdin, stdout, stderr, adapter_factory=FakeAdapter)
    return [json.loads(line) for line in stdout.getvalue().splitlines()]


class TestMediaProtocol(unittest.TestCase):
    def test_probe_returns_typed_metadata_and_preserves_ids(self) -> None:
        messages = run_request("media.probe", {"source_path": "dash.mp4"})
        response = messages[1]
        self.assertEqual(response["type"], "media.probed")
        self.assertEqual(response["message_id"], "media-1")
        self.assertEqual(response["job_id"], "job-1")
        self.assertEqual(response["payload"]["frame_count"], 240)
        self.assertEqual(response["payload"]["width"], 1280)

    def test_extract_returns_manifest_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "frames"
            messages = run_request(
                "media.extract_frames",
                {"source_path": "dash.mp4", "output_path": str(output)},
            )
            response = messages[1]
            self.assertEqual(response["type"], "media.frames_extracted")
            self.assertEqual(response["payload"]["frame_count"], 2)
            self.assertTrue(response["payload"]["manifest_path"].endswith("frames.json"))

    def test_missing_path_returns_invalid_request(self) -> None:
        messages = run_request("media.probe", {})
        response = messages[1]
        self.assertEqual(response["type"], "error")
        self.assertEqual(response["payload"]["code"], "invalid_request")


class RaisingAdapter(FakeAdapter):
    def probe(self, source: Path) -> MediaProbe:
        raise MediaToolError("media probe failed")


class TestMediaProtocolFailures(unittest.TestCase):
    def test_media_tool_error_is_structured(self) -> None:
        request = make_envelope(
            message_type="media.probe",
            message_id="media-error",
            payload={"source_path": "dash.mp4"},
        )
        stdin = io.StringIO(envelope_to_json(request).decode("utf-8"))
        stdout = io.BytesIO()
        stderr = io.StringIO()
        run_loop(stdin, stdout, stderr, adapter_factory=RaisingAdapter)
        messages = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(messages[1]["payload"]["code"], "media_tool_error")
        self.assertEqual(messages[1]["message_id"], "media-error")


if __name__ == "__main__":
    unittest.main()
