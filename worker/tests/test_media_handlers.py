# worker/tests/test_media_handlers.py
"""Unit tests for motionanchor_worker.media.handlers.

Uses a deterministic mock adapter so FFmpeg/ffprobe are NOT required.
Integration tests live in test_ffmpeg_adapter.py.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from motionanchor_worker.media.handlers import (
    MediaRequestError,
    execute_media_request,
    handle_media_extract_frames,
    handle_media_probe,
)
from motionanchor_worker.media.ffmpeg import MediaToolError


# ---------------------------------------------------------------------------
# Mock adapter — returns predictable values without touching FFmpeg
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeMediaProbe:
    path: str = "/fake/source.mp4"
    codec: str = "h264"
    width: int = 1920
    height: int = 1080
    duration_seconds: float = 2.0
    avg_frame_rate: str = "30/1"
    real_frame_rate: str = "30/1"
    frame_count: int | None = 60
    variable_frame_rate: bool = False


@dataclass(frozen=True)
class _FakeFrameRecord:
    index: int = 0
    timestamp_seconds: float = 0.0
    duration_seconds: float | None = 0.033
    pict_type: str | None = "I"
    filename: str = "frame_000000.png"


class _FakeFfmpegAdapter:
    """Minimal stand-in that satisfies the handler's adapter_factory."""

    def probe(self, source: Path) -> _FakeMediaProbe:
        return _FakeMediaProbe(path=str(source.resolve()))

    def extract_png_frames(self, source: Path, output_dir: Path) -> list[_FakeFrameRecord]:
        output_dir.mkdir(parents=True, exist_ok=True)
        records = [
            _FakeFrameRecord(index=0, timestamp_seconds=0.0, filename="frame_000000.png"),
            _FakeFrameRecord(index=1, timestamp_seconds=0.033, filename="frame_000001.png"),
            _FakeFrameRecord(index=2, timestamp_seconds=0.066, filename="frame_000002.png"),
        ]
        manifest = [r.__dict__ for r in records]
        (output_dir / "frames.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        for r in records:
            (output_dir / r.filename).touch()
        return records


class _FailingFfmpegAdapter:
    """Adapter that raises MediaToolError on probe."""

    def probe(self, source: Path) -> None:
        raise MediaToolError("simulated ffprobe failure")

    def extract_png_frames(self, source: Path, output_dir: Path) -> None:
        raise MediaToolError("simulated ffmpeg failure")


def _fake_factory():
    return _FakeFfmpegAdapter()


def _failing_factory():
    return _FailingFfmpegAdapter()


# ---------------------------------------------------------------------------
# Tests — handle_media_probe
# ---------------------------------------------------------------------------


class TestHandleMediaProbe(unittest.TestCase):
    def test_valid_payload_returns_probe_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "test.mp4"
            source.touch()
            result = handle_media_probe(
                {"source_path": str(source)},
                adapter_factory=_fake_factory,
            )
            self.assertEqual(result["codec"], "h264")
            self.assertEqual(result["width"], 1920)
            self.assertEqual(result["height"], 1080)
            self.assertAlmostEqual(result["duration_seconds"], 2.0)
            self.assertEqual(result["avg_frame_rate"], "30/1")
            self.assertEqual(result["frame_count"], 60)
            self.assertFalse(result["variable_frame_rate"])

    def test_missing_source_path_raises(self) -> None:
        with self.assertRaises(MediaRequestError) as ctx:
            handle_media_probe({}, adapter_factory=_fake_factory)
        self.assertIn("source_path", str(ctx.exception))

    def test_empty_source_path_raises(self) -> None:
        with self.assertRaises(MediaRequestError):
            handle_media_probe({"source_path": "  "}, adapter_factory=_fake_factory)

    def test_non_string_source_path_raises(self) -> None:
        with self.assertRaises(MediaRequestError):
            handle_media_probe({"source_path": 123}, adapter_factory=_fake_factory)

    def test_adapter_tool_error_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "test.mp4"
            source.touch()
            with self.assertRaises(MediaToolError):
                handle_media_probe(
                    {"source_path": str(source)},
                    adapter_factory=_failing_factory,
                )


# ---------------------------------------------------------------------------
# Tests — handle_media_extract_frames
# ---------------------------------------------------------------------------


class TestHandleMediaExtractFrames(unittest.TestCase):
    def test_valid_payload_returns_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.touch()
            output = Path(tmp) / "frames"
            result = handle_media_extract_frames(
                {"source_path": str(source), "output_path": str(output)},
                adapter_factory=_fake_factory,
            )
            self.assertEqual(result["frame_count"], 3)
            self.assertIn("manifest_path", result)
            self.assertIn("source_path", result)
            self.assertIn("output_path", result)
            self.assertAlmostEqual(result["first_timestamp_seconds"], 0.0)
            self.assertAlmostEqual(result["last_timestamp_seconds"], 0.066)

    def test_missing_source_path_raises(self) -> None:
        with self.assertRaises(MediaRequestError):
            handle_media_extract_frames(
                {"output_path": "/tmp/out"},
                adapter_factory=_fake_factory,
            )

    def test_missing_output_path_raises(self) -> None:
        with self.assertRaises(MediaRequestError):
            handle_media_extract_frames(
                {"source_path": "/tmp/src.mp4"},
                adapter_factory=_fake_factory,
            )

    def test_adapter_tool_error_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.touch()
            output = Path(tmp) / "frames"
            with self.assertRaises(MediaToolError):
                handle_media_extract_frames(
                    {"source_path": str(source), "output_path": str(output)},
                    adapter_factory=_failing_factory,
                )


# ---------------------------------------------------------------------------
# Tests — execute_media_request
# ---------------------------------------------------------------------------


class TestExecuteMediaRequest(unittest.TestCase):
    def test_probe_routes_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "test.mp4"
            source.touch()
            response_type, payload = execute_media_request(
                "media.probe",
                {"source_path": str(source)},
                adapter_factory=_fake_factory,
            )
            self.assertEqual(response_type, "media.probed")
            self.assertEqual(payload["codec"], "h264")

    def test_extract_frames_routes_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src.mp4"
            source.touch()
            output = Path(tmp) / "out"
            response_type, payload = execute_media_request(
                "media.extract_frames",
                {"source_path": str(source), "output_path": str(output)},
                adapter_factory=_fake_factory,
            )
            self.assertEqual(response_type, "media.frames_extracted")
            self.assertEqual(payload["frame_count"], 3)

    def test_unsupported_type_raises(self) -> None:
        with self.assertRaises(MediaRequestError) as ctx:
            execute_media_request(
                "media.unknown_op",
                {},
                adapter_factory=_fake_factory,
            )
        self.assertIn("unsupported", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
