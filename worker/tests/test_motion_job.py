from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from motionanchor_worker.media.motion_job import (
    MotionSelectionCancelled,
    materialize_motion_selection,
)


def write_frame(path: Path, value: int) -> None:
    image = np.full((24, 32, 3), value, dtype=np.uint8)
    if not cv2.imwrite(str(path), image):
        raise AssertionError(f"failed to write {path}")


class MotionJobTests(unittest.TestCase):
    def test_materializes_sequential_frames_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            output = Path(tmp) / "selected"
            source.mkdir()
            for index in range(8):
                write_frame(source / f"frame_{index:06d}.png", index * 20)
            result = materialize_motion_selection(source, output, max_frames=4)

            self.assertEqual(result["source_frame_count"], 8)
            self.assertEqual(result["selected_frame_count"], 4)
            self.assertTrue(output.is_dir())
            self.assertEqual(
                [path.name for path in sorted(output.glob("frame_*.png"))],
                [f"frame_{index:06d}.png" for index in range(4)],
            )
            manifest = json.loads((output / "motion-selection.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["frames"][0]["source_index"], 0)
            self.assertEqual(manifest["frames"][-1]["source_index"], 7)

    def test_existing_output_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            output = Path(tmp) / "selected"
            source.mkdir()
            output.mkdir()
            for index in range(2):
                write_frame(source / f"frame_{index:06d}.png", index * 30)

            with self.assertRaisesRegex(ValueError, "must not already exist"):
                materialize_motion_selection(source, output, max_frames=2)

    def test_cancellation_removes_temporary_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            output = Path(tmp) / "selected"
            source.mkdir()
            for index in range(4):
                write_frame(source / f"frame_{index:06d}.png", index * 40)
            calls = 0

            def cancelled() -> bool:
                nonlocal calls
                calls += 1
                return calls > 1

            with self.assertRaises(MotionSelectionCancelled):
                materialize_motion_selection(
                    source,
                    output,
                    max_frames=4,
                    cancelled=cancelled,
                )
            self.assertFalse(output.exists())
            self.assertFalse(list(Path(tmp).glob(".selected.motion-*.tmp")))


if __name__ == "__main__":
    unittest.main()