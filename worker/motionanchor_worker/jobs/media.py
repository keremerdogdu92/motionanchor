"""Background media job definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..media.ffmpeg import FfmpegAdapter
from .runner import JobRunner

AdapterFactory = Callable[[], FfmpegAdapter]


class MediaJobService:
    def __init__(
        self,
        runner: JobRunner | None = None,
        adapter_factory: AdapterFactory = FfmpegAdapter,
    ) -> None:
        self.runner = runner or JobRunner()
        self.adapter_factory = adapter_factory

    def submit_extract_frames(self, source_path: str, output_path: str) -> str:
        source = Path(source_path).expanduser()
        output = Path(output_path).expanduser()

        def work(report, cancelled) -> dict[str, Any]:
            adapter = self.adapter_factory()
            records = adapter.extract_png_frames_cancellable(
                source,
                output,
                report=report,
                cancelled=cancelled,
            )
            if not records:
                return {}
            resolved_output = output.resolve()
            return {
                "source_path": str(source.resolve()),
                "output_path": str(resolved_output),
                "frame_count": len(records),
                "manifest_path": str(resolved_output / "frames.json"),
                "first_timestamp_seconds": records[0].timestamp_seconds,
                "last_timestamp_seconds": records[-1].timestamp_seconds,
            }

        return self.runner.submit("media.extract_frames", work)

    def status(self, job_id: str) -> dict[str, Any]:
        return self.runner.snapshot(job_id)

    def cancel(self, job_id: str) -> bool:
        return self.runner.cancel(job_id)
