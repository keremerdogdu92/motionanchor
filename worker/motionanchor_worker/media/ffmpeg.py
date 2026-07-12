"""FFmpeg/ffprobe adapter for deterministic media inspection and extraction."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

MAX_TOOL_OUTPUT_BYTES = 8 * 1024 * 1024


class MediaToolError(RuntimeError):
    """Raised when FFmpeg tooling or media validation fails."""


@dataclass(frozen=True)
class MediaProbe:
    path: str
    codec: str
    width: int
    height: int
    duration_seconds: float
    avg_frame_rate: str
    real_frame_rate: str
    frame_count: int | None
    variable_frame_rate: bool


@dataclass(frozen=True)
class FrameRecord:
    index: int
    timestamp_seconds: float
    duration_seconds: float | None
    pict_type: str | None
    filename: str


def _resolve_tool(env_name: str, command: str) -> str:
    configured = os.environ.get(env_name)
    if configured:
        path = Path(configured).expanduser().resolve()
        if not path.is_file():
            raise MediaToolError(f"{env_name} does not point to a file")
        return str(path)
    resolved = shutil.which(command)
    if resolved is None:
        raise MediaToolError(f"{command} is not installed or not on PATH")
    return resolved


def _run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        timeout=30,
    )
    if len(completed.stdout) > MAX_TOOL_OUTPUT_BYTES:
        raise MediaToolError("ffprobe output exceeded the safety limit")
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace")[-1000:]
        raise MediaToolError(f"media tool failed: {message.strip()}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MediaToolError("ffprobe returned invalid JSON") from exc


def _rate(value: str) -> Fraction | None:
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return result if result > 0 else None


class FfmpegAdapter:
    def __init__(self, ffmpeg: str | None = None, ffprobe: str | None = None) -> None:
        self.ffmpeg = ffmpeg or _resolve_tool("MOTIONANCHOR_FFMPEG", "ffmpeg")
        self.ffprobe = ffprobe or _resolve_tool("MOTIONANCHOR_FFPROBE", "ffprobe")

    def probe(self, source: Path) -> MediaProbe:
        source = source.resolve(strict=True)
        data = _run_json([
            self.ffprobe,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries",
            "stream=codec_name,width,height,avg_frame_rate,r_frame_rate,nb_frames,duration:format=duration",
            "-of", "json",
            str(source),
        ])
        streams = data.get("streams") or []
        if not streams:
            raise MediaToolError("source contains no video stream")
        stream = streams[0]
        avg = str(stream.get("avg_frame_rate") or "0/0")
        real = str(stream.get("r_frame_rate") or "0/0")
        duration_raw = stream.get("duration") or (data.get("format") or {}).get("duration")
        if duration_raw is None:
            raise MediaToolError("media duration is unavailable")
        frame_count_raw = stream.get("nb_frames")
        frame_count = int(frame_count_raw) if str(frame_count_raw).isdigit() else None
        return MediaProbe(
            path=str(source),
            codec=str(stream.get("codec_name") or "unknown"),
            width=int(stream.get("width") or 0),
            height=int(stream.get("height") or 0),
            duration_seconds=float(duration_raw),
            avg_frame_rate=avg,
            real_frame_rate=real,
            frame_count=frame_count,
            variable_frame_rate=(_rate(avg) is not None and _rate(real) is not None and _rate(avg) != _rate(real)),
        )

    def frame_timestamps(self, source: Path) -> list[FrameRecord]:
        source = source.resolve(strict=True)
        data = _run_json([
            self.ffprobe,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_frames",
            "-show_entries", "frame=best_effort_timestamp_time,pkt_duration_time,pict_type",
            "-of", "json",
            str(source),
        ])
        records: list[FrameRecord] = []
        for index, frame in enumerate(data.get("frames") or []):
            timestamp = frame.get("best_effort_timestamp_time")
            if timestamp is None:
                raise MediaToolError(f"frame {index} has no timestamp")
            duration = frame.get("pkt_duration_time")
            records.append(FrameRecord(
                index=index,
                timestamp_seconds=float(timestamp),
                duration_seconds=float(duration) if duration is not None else None,
                pict_type=frame.get("pict_type"),
                filename=f"frame_{index:06d}.png",
            ))
        if not records:
            raise MediaToolError("source contains no decodable video frames")
        return records

    def extract_png_frames_cancellable(
        self,
        source: Path,
        output_dir: Path,
        *,
        report: Callable[[float, str | None], None],
        cancelled: Callable[[], bool],
    ) -> list[FrameRecord]:
        source = source.resolve(strict=True)
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        if any(output_dir.iterdir()):
            raise MediaToolError("output directory must be empty")

        report(0.05, "reading frame timestamps")
        records = self.frame_timestamps(source)
        if cancelled():
            return []
        pattern = output_dir / "frame_%06d.png"
        process = subprocess.Popen(
            [
                self.ffmpeg, "-v", "error", "-i", str(source),
                "-map", "0:v:0", "-vsync", "0",
                "-start_number", "0", str(pattern),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            while process.poll() is None:
                if cancelled():
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
                    self._cleanup_partial_output(output_dir)
                    return []
                count = sum(1 for _ in output_dir.glob("frame_*.png"))
                progress = 0.1 + 0.8 * min(1.0, count / len(records))
                report(progress, f"extracting frames ({count}/{len(records)})")
                time.sleep(0.05)
            stderr = (process.stderr.read() if process.stderr else b"")
            if process.returncode != 0:
                self._cleanup_partial_output(output_dir)
                message = stderr.decode("utf-8", errors="replace")[-1000:]
                raise MediaToolError(f"frame extraction failed: {message.strip()}")
            return self._finalize_extraction(output_dir, records, report)
        finally:
            if process.stderr is not None:
                process.stderr.close()

    @staticmethod
    def _cleanup_partial_output(output_dir: Path) -> None:
        for candidate in output_dir.iterdir():
            if candidate.is_file() and (candidate.name.startswith("frame_") or candidate.name == "frames.json"):
                candidate.unlink(missing_ok=True)

    @staticmethod
    def _finalize_extraction(
        output_dir: Path,
        records: list[FrameRecord],
        report: Callable[[float, str | None], None],
    ) -> list[FrameRecord]:
        files = sorted(output_dir.glob("frame_*.png"))
        if len(files) != len(records):
            raise MediaToolError(
                f"timestamp/frame count mismatch: {len(records)} timestamps, {len(files)} files"
            )
        manifest = [record.__dict__ for record in records]
        (output_dir / "frames.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        report(1.0, "frame extraction complete")
        return records

    def extract_png_frames(self, source: Path, output_dir: Path) -> list[FrameRecord]:
        source = source.resolve(strict=True)
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        if any(output_dir.iterdir()):
            raise MediaToolError("output directory must be empty")

        records = self.frame_timestamps(source)
        pattern = output_dir / "frame_%06d.png"
        completed = subprocess.run(
            [
                self.ffmpeg,
                "-v", "error",
                "-i", str(source),
                "-map", "0:v:0",
                "-vsync", "0",
                "-start_number", "0",
                str(pattern),
            ],
            check=False,
            capture_output=True,
            timeout=60,
        )
        if completed.returncode != 0:
            message = completed.stderr.decode("utf-8", errors="replace")[-1000:]
            raise MediaToolError(f"frame extraction failed: {message.strip()}")
        files = sorted(output_dir.glob("frame_*.png"))
        if len(files) != len(records):
            raise MediaToolError(
                f"timestamp/frame count mismatch: {len(records)} timestamps, {len(files)} files"
            )
        manifest = [record.__dict__ for record in records]
        (output_dir / "frames.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        return records
