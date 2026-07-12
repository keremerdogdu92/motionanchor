"""Integration tests for the external FFmpeg adapter."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from motionanchor_worker.media import FfmpegAdapter, MediaToolError


class TestFfmpegAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = FfmpegAdapter()

    def _fixture(self, root: Path) -> Path:
        source = root / "fixture.mkv"
        completed = subprocess.run(
            [
                self.adapter.ffmpeg,
                "-v", "error",
                "-f", "lavfi",
                "-i", "testsrc=size=96x64:rate=4:duration=1",
                "-c:v", "ffv1",
                "-pix_fmt", "rgb24",
                str(source),
            ],
            check=False,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
        return source

    def test_probe_and_exact_timestamp_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self._fixture(root)
            probe = self.adapter.probe(source)
            self.assertEqual(probe.codec, "ffv1")
            self.assertEqual((probe.width, probe.height), (96, 64))
            self.assertAlmostEqual(probe.duration_seconds, 1.0, places=3)
            self.assertEqual(probe.avg_frame_rate, "4/1")
            self.assertFalse(probe.variable_frame_rate)

            output = root / "frames"
            records = self.adapter.extract_png_frames(source, output)
            self.assertEqual(len(records), 4)
            timestamps = [record.timestamp_seconds for record in records]
            self.assertEqual(timestamps, [0.0, 0.25, 0.5, 0.75])
            self.assertEqual(len(list(output.glob("frame_*.png"))), 4)
            manifest = json.loads((output / "frames.json").read_text(encoding="utf-8"))
            self.assertEqual([item["timestamp_seconds"] for item in manifest], timestamps)

    def test_requires_empty_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self._fixture(root)
            output = root / "frames"
            output.mkdir()
            (output / "existing.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(MediaToolError, "must be empty"):
                self.adapter.extract_png_frames(source, output)


if __name__ == "__main__":
    unittest.main()
