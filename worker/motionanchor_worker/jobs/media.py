"""Background media job definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..media.ffmpeg import FfmpegAdapter
from ..media.motion_job import materialize_motion_selection
from ..segmentation import run_sam2_bootstrap_job, run_sam2_rgba_job
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

    def submit_motion_selection(
        self,
        frames_path: str,
        output_path: str,
        *,
        max_frames: int = 48,
        preview_width: int = 192,
        uniform_fraction: float = 0.5,
    ) -> str:
        def work(report, cancelled) -> dict[str, Any]:
            return materialize_motion_selection(
                frames_path,
                output_path,
                max_frames=max_frames,
                preview_width=preview_width,
                uniform_fraction=uniform_fraction,
                report=report,
                cancelled=cancelled,
            )

        return self.runner.submit("media.select_motion_frames", work)

    def submit_sam2_rgba(
        self,
        frames_path: str,
        output_path: str,
        prompt_path: str,
        *,
        model: str = "small",
        feather_radius: float = 1.5,
        defringe: bool = True,
    ) -> str:
        def work(report, cancelled) -> dict[str, Any]:
            return run_sam2_rgba_job(
                frames_path=frames_path,
                output_path=output_path,
                prompt_path=prompt_path,
                model=model,
                feather_radius=feather_radius,
                defringe=defringe,
                report=report,
                cancelled=cancelled,
            )

        return self.runner.submit("segmentation.sam2_rgba", work)


    def submit_sam2_bootstrap(self, script_path: str) -> str:
        def work(report, cancelled) -> dict[str, Any]:
            return run_sam2_bootstrap_job(
                script_path=script_path,
                report=report,
                cancelled=cancelled,
            )

        return self.runner.submit("segmentation.sam2_bootstrap", work)

    def status(self, job_id: str) -> dict[str, Any]:
        return self.runner.snapshot(job_id)

    def cancel(self, job_id: str) -> bool:
        return self.runner.cancel(job_id)
