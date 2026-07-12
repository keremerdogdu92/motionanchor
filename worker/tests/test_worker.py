# worker/tests/test_worker.py
"""Unit tests for motionanchor_worker.worker main loop.

Tests feed synthetic NDJSON through StringIO/BytesIO and inspect what
the worker writes to stdout and stderr.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from motionanchor_worker import PROTOCOL_VERSION
from motionanchor_worker.media.ffmpeg import MediaToolError
from motionanchor_worker.protocol import (
    TYPE_MEDIA_FRAMES_EXTRACTED,
    TYPE_MEDIA_PROBED,
    TYPE_WORKER_PONG,
    TYPE_WORKER_READY,
    TYPE_WORKER_SHUTDOWN,
    TYPE_WORKER_STOPPED,
    envelope_to_json,
    make_envelope,
    make_error_envelope,
)
from motionanchor_worker.worker import run_loop


def _line(env: dict) -> str:
    """Encode an envelope dict as an NDJSON text line."""
    raw = envelope_to_json(env)
    return raw.decode("utf-8")


def _parse_lines(data: str) -> list[dict]:
    """Parse all non-empty NDJSON lines from a string."""
    results: list[dict] = []
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return results


class _Capture:
    """Minimal in-memory stdin/stdout/stderr pair for tests."""

    def __init__(self, input_lines: list[str]) -> None:
        self.stdin = io.StringIO("".join(input_lines))
        self.stdout_bytes = io.BytesIO()
        self.stderr = io.StringIO()

    @property
    def stdout_text(self) -> str:
        return self.stdout_bytes.getvalue().decode("utf-8")

    def output_envelopes(self) -> list[dict]:
        return _parse_lines(self.stdout_text)

    def stderr_lines(self) -> list[str]:
        return [l.strip() for l in self.stderr.getvalue().splitlines() if l.strip()]


class TestStartupHandshake(unittest.TestCase):
    def test_sends_worker_ready(self) -> None:
        cap = _Capture([])
        code = run_loop(cap.stdin, cap.stdout_bytes, cap.stderr)
        self.assertEqual(code, 0)
        envs = cap.output_envelopes()
        self.assertTrue(envs, "should produce at least one envelope")
        self.assertEqual(envs[0]["type"], TYPE_WORKER_READY)
        self.assertEqual(envs[0]["protocol_version"], PROTOCOL_VERSION)
        self.assertIn("worker_id", envs[0]["payload"])


class TestPingPong(unittest.TestCase):
    def test_ping_preserves_message_id(self) -> None:
        ping = make_envelope(message_type="worker.ping", message_id="ping-42")
        cap = _Capture([_line(ping)])
        run_loop(cap.stdin, cap.stdout_bytes, cap.stderr)
        envs = cap.output_envelopes()
        # First is worker.ready, second should be pong
        self.assertGreaterEqual(len(envs), 2)
        pong = envs[1]
        self.assertEqual(pong["type"], TYPE_WORKER_PONG)
        self.assertEqual(pong["message_id"], "ping-42")

    def test_multiple_pings(self) -> None:
        lines = []
        for i in range(5):
            ping = make_envelope(message_type="worker.ping", message_id=f"p-{i}")
            lines.append(_line(ping))
        cap = _Capture(lines)
        run_loop(cap.stdin, cap.stdout_bytes, cap.stderr)
        envs = cap.output_envelopes()
        # ready + 5 pongs
        pongs = [e for e in envs if e["type"] == TYPE_WORKER_PONG]
        self.assertEqual(len(pongs), 5)
        for i, pong in enumerate(pongs):
            self.assertEqual(pong["message_id"], f"p-{i}")


class TestGracefulShutdown(unittest.TestCase):
    def test_shutdown_sends_stopped(self) -> None:
        shut = make_envelope(message_type="worker.shutdown", message_id="shut-1")
        cap = _Capture([_line(shut)])
        code = run_loop(cap.stdin, cap.stdout_bytes, cap.stderr)
        self.assertEqual(code, 0)
        envs = cap.output_envelopes()
        stopped = [e for e in envs if e["type"] == TYPE_WORKER_STOPPED]
        self.assertEqual(len(stopped), 1)
        self.assertEqual(stopped[0]["message_id"], "shut-1")

    def test_eof_stops_loop(self) -> None:
        cap = _Capture([])
        code = run_loop(cap.stdin, cap.stdout_bytes, cap.stderr)
        self.assertEqual(code, 0)

    def test_no_messages_after_shutdown(self) -> None:
        shut = make_envelope(message_type="worker.shutdown")
        extra = make_envelope(message_type="worker.ping", message_id="after")
        cap = _Capture([_line(shut), _line(extra)])
        run_loop(cap.stdin, cap.stdout_bytes, cap.stderr)
        envs = cap.output_envelopes()
        after_types = [e["type"] for e in envs[1:]]  # skip ready
        # Only stopped should follow shutdown; the ping after should be ignored
        self.assertNotIn(TYPE_WORKER_PONG, after_types)


class TestUnknownType(unittest.TestCase):
    def test_returns_structured_error(self) -> None:
        msg = make_envelope(message_type="unknown.thing", message_id="unk-1")
        cap = _Capture([_line(msg)])
        run_loop(cap.stdin, cap.stdout_bytes, cap.stderr)
        envs = cap.output_envelopes()
        errors = [e for e in envs if e["type"] == "error"]
        self.assertTrue(errors)
        err = errors[0]
        self.assertEqual(err["payload"]["code"], "unknown_type")
        self.assertEqual(err["message_id"], "unk-1")


class TestMalformedJson(unittest.TestCase):
    def test_garbage_returns_error(self) -> None:
        cap = _Capture(["not json at all\n"])
        run_loop(cap.stdin, cap.stdout_bytes, cap.stderr)
        envs = cap.output_envelopes()
        errors = [e for e in envs if e["type"] == "error"]
        self.assertTrue(errors)
        self.assertEqual(errors[0]["payload"]["code"], "malformed_json")


class TestStderrDiagnostics(unittest.TestCase):
    def test_stderr_lines_populated(self) -> None:
        cap = _Capture([])
        run_loop(cap.stdin, cap.stdout_bytes, cap.stderr)
        lines = cap.stderr_lines()
        self.assertTrue(any("handshake" in l for l in lines))

    def test_no_stdout_from_diagnostics(self) -> None:
        cap = _Capture([])
        run_loop(cap.stdin, cap.stdout_bytes, cap.stderr)
        envs = cap.output_envelopes()
        for e in envs:
            self.assertIn(e["type"], {TYPE_WORKER_READY, TYPE_WORKER_PONG, TYPE_WORKER_STOPPED, "error"})


class TestProtocolVersionEnforcement(unittest.TestCase):
    def test_startup_envelope_version(self) -> None:
        cap = _Capture([])
        run_loop(cap.stdin, cap.stdout_bytes, cap.stderr)
        envs = cap.output_envelopes()
        self.assertEqual(envs[0]["protocol_version"], PROTOCOL_VERSION)


# ---------------------------------------------------------------------------
# Mock adapter for media dispatch tests
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeProbe:
    path: str = ""
    codec: str = "h264"
    width: int = 640
    height: int = 480
    duration_seconds: float = 1.0
    avg_frame_rate: str = "24/1"
    real_frame_rate: str = "24/1"
    frame_count: int | None = 24
    variable_frame_rate: bool = False


@dataclass(frozen=True)
class _FakeFrame:
    index: int = 0
    timestamp_seconds: float = 0.0
    duration_seconds: float | None = 0.042
    pict_type: str | None = "I"
    filename: str = "frame_000000.png"


class _FakeAdapter:
    def probe(self, source: Path) -> _FakeProbe:
        return _FakeProbe(path=str(source))

    def extract_png_frames(self, source: Path, output_dir: Path) -> list[_FakeFrame]:
        output_dir.mkdir(parents=True, exist_ok=True)
        recs = [
            _FakeFrame(index=0, timestamp_seconds=0.0),
            _FakeFrame(index=1, timestamp_seconds=0.042),
        ]
        (output_dir / "frames.json").write_text("[]", encoding="utf-8")
        for r in recs:
            (output_dir / r.filename).touch()
        return recs


class _BrokenAdapter:
    def probe(self, source: Path) -> None:
        raise MediaToolError("probe exploded")

    def extract_png_frames(self, source: Path, output_dir: Path) -> None:
        raise MediaToolError("extract exploded")


def _fake_factory():
    return _FakeAdapter()


def _broken_factory():
    return _BrokenAdapter()


# ---------------------------------------------------------------------------
# Media dispatch integration tests
# ---------------------------------------------------------------------------


class TestMediaProbeDispatch(unittest.TestCase):
    def test_probe_returns_media_probed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "in.mp4"
            source.touch()
            msg = make_envelope(
                message_type="media.probe",
                message_id="mp-1",
                payload={"source_path": str(source)},
            )
            cap = _Capture([_line(msg)])
            run_loop(cap.stdin, cap.stdout_bytes, cap.stderr, adapter_factory=_fake_factory)
            envs = cap.output_envelopes()
            probed = [e for e in envs if e["type"] == TYPE_MEDIA_PROBED]
            self.assertEqual(len(probed), 1)
            self.assertEqual(probed[0]["message_id"], "mp-1")
            self.assertEqual(probed[0]["payload"]["codec"], "h264")

    def test_probe_preserves_job_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "in.mp4"
            source.touch()
            msg = make_envelope(
                message_type="media.probe",
                message_id="mp-2",
                job_id="job-abc",
                payload={"source_path": str(source)},
            )
            cap = _Capture([_line(msg)])
            run_loop(cap.stdin, cap.stdout_bytes, cap.stderr, adapter_factory=_fake_factory)
            envs = cap.output_envelopes()
            probed = [e for e in envs if e["type"] == TYPE_MEDIA_PROBED]
            self.assertEqual(len(probed), 1)
            self.assertEqual(probed[0]["job_id"], "job-abc")


class TestMediaExtractFramesDispatch(unittest.TestCase):
    def test_extract_returns_frames_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "in.mp4"
            source.touch()
            output = Path(tmp) / "out"
            msg = make_envelope(
                message_type="media.extract_frames",
                message_id="me-1",
                payload={"source_path": str(source), "output_path": str(output)},
            )
            cap = _Capture([_line(msg)])
            run_loop(cap.stdin, cap.stdout_bytes, cap.stderr, adapter_factory=_fake_factory)
            envs = cap.output_envelopes()
            extracted = [e for e in envs if e["type"] == TYPE_MEDIA_FRAMES_EXTRACTED]
            self.assertEqual(len(extracted), 1)
            self.assertEqual(extracted[0]["message_id"], "me-1")
            self.assertEqual(extracted[0]["payload"]["frame_count"], 2)


class TestMediaErrorHandling(unittest.TestCase):
    def test_invalid_request_returns_error(self) -> None:
        msg = make_envelope(
            message_type="media.probe",
            message_id="err-1",
            payload={},
        )
        cap = _Capture([_line(msg)])
        run_loop(cap.stdin, cap.stdout_bytes, cap.stderr, adapter_factory=_fake_factory)
        envs = cap.output_envelopes()
        errors = [e for e in envs if e["type"] == "error"]
        self.assertTrue(errors)
        self.assertEqual(errors[0]["message_id"], "err-1")
        self.assertEqual(errors[0]["payload"]["code"], "invalid_request")

    def test_adapter_failure_returns_media_tool_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "in.mp4"
            source.touch()
            msg = make_envelope(
                message_type="media.probe",
                message_id="err-2",
                payload={"source_path": str(source)},
            )
            cap = _Capture([_line(msg)])
            run_loop(cap.stdin, cap.stdout_bytes, cap.stderr, adapter_factory=_broken_factory)
            envs = cap.output_envelopes()
            errors = [e for e in envs if e["type"] == "error"]
            self.assertTrue(errors)
            self.assertEqual(errors[0]["message_id"], "err-2")
            self.assertEqual(errors[0]["payload"]["code"], "media_tool_error")

    def test_media_dispatch_does_not_stop_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "in.mp4"
            source.touch()
            probe_msg = make_envelope(
                message_type="media.probe",
                payload={"source_path": str(source)},
            )
            ping_msg = make_envelope(
                message_type="worker.ping",
                message_id="after-media",
            )
            shut_msg = make_envelope(message_type="worker.shutdown")
            cap = _Capture([_line(probe_msg), _line(ping_msg), _line(shut_msg)])
            run_loop(cap.stdin, cap.stdout_bytes, cap.stderr, adapter_factory=_fake_factory)
            envs = cap.output_envelopes()
            types = [e["type"] for e in envs]
            self.assertIn(TYPE_MEDIA_PROBED, types)
            self.assertIn(TYPE_WORKER_PONG, types)
            self.assertIn(TYPE_WORKER_STOPPED, types)


if __name__ == "__main__":
    unittest.main()
