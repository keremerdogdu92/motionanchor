# worker/motionanchor_worker/media/motion_job.py
"""Materialize motion-aware frame subsets for bounded downstream jobs."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .motion_selection import select_motion_frames

ProgressReporter = Callable[[float, str | None], None]
CancellationCheck = Callable[[], bool]


class MotionSelectionCancelled(RuntimeError):
    """Raised when frame subset materialization is cancelled."""


def materialize_motion_selection(
    frames_path: str | Path,
    output_path: str | Path,
    *,
    max_frames: int,
    preview_width: int = 192,
    uniform_fraction: float = 0.5,
    report: ProgressReporter | None = None,
    cancelled: CancellationCheck | None = None,
) -> dict[str, Any]:
    """Select, copy, and atomically publish a bounded frame directory."""

    source = Path(frames_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    if output.exists():
        raise ValueError("output_path must not already exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.motion-{uuid4().hex}.tmp")
    temporary.mkdir()

    try:
        if report:
            report(0.05, "Scoring frame motion")
        selection = select_motion_frames(
            source,
            max_frames=max_frames,
            preview_width=preview_width,
            uniform_fraction=uniform_fraction,
        )
        source_frames = sorted(source.glob("frame_*.png"))
        selected_records: list[dict[str, Any]] = []

        for target_index, source_index in enumerate(selection.selected_indices):
            if cancelled and cancelled():
                raise MotionSelectionCancelled("motion frame selection cancelled")
            target_name = f"frame_{target_index:06d}.png"
            shutil.copy2(source_frames[source_index], temporary / target_name)
            selected_records.append({
                "index": target_index,
                "source_index": source_index,
                "filename": target_name,
                "motion_score": selection.scores[source_index].score,
            })
            if report:
                progress = 0.15 + 0.75 * ((target_index + 1) / len(selection.selected_indices))
                report(progress, f"Copying selected frame {target_index + 1}/{len(selection.selected_indices)}")

        manifest = {
            "schema_version": 1,
            "source_path": str(source),
            "output_path": str(output),
            "source_frame_count": selection.source_frame_count,
            "selected_frame_count": len(selection.selected_indices),
            "max_frames": max_frames,
            "preview_width": preview_width,
            "uniform_fraction": uniform_fraction,
            "frames": selected_records,
        }
        manifest_path = temporary / "motion-selection.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if report:
            report(0.95, "Publishing selected frame set")
        os.replace(temporary, output)
        manifest["manifest_path"] = str(output / "motion-selection.json")
        if report:
            report(1.0, "Motion-aware frame set completed")
        return manifest
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
