from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "fixtures" / "cat-trap" / "videos" / "dash.mp4"
FRAMES = ROOT / "fixtures" / "cat-trap" / "dash" / "frames"
SELECTED = ROOT / "fixtures" / "cat-trap" / "dash" / "selected"
REPORT = ROOT / "fixtures" / "cat-trap" / "dash" / "selection-report.json"


def discover_tool(name: str) -> str:
    roots = list((Path.home() / "AppData/Local/Microsoft/WinGet/Packages").glob("BtbN.FFmpeg.LGPL.8.1_*/**/bin"))
    for root in roots:
        candidate = root / f"{name}.exe"
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(f"{name}.exe not found")


def sharpness(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def motion(previous: np.ndarray, current: np.ndarray) -> float:
    a = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    return float(np.mean(cv2.absdiff(a, b)))


def main() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "worker"))
    from motionanchor_worker.media.ffmpeg import FfmpegAdapter

    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    if SELECTED.exists():
        shutil.rmtree(SELECTED)
    FRAMES.mkdir(parents=True, exist_ok=True)
    SELECTED.mkdir(parents=True, exist_ok=True)

    adapter = FfmpegAdapter(
        ffmpeg=discover_tool("ffmpeg"),
        ffprobe=discover_tool("ffprobe"),
    )
    records = adapter.extract_png_frames(VIDEO, FRAMES)

    images: list[np.ndarray] = []
    metrics: list[dict[str, float | int]] = []
    previous: np.ndarray | None = None
    for record in records:
        image = cv2.imread(str(FRAMES / record.filename), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"missing extracted frame: {record.filename}")
        images.append(image)
        metrics.append({
            "index": record.index,
            "timestamp_seconds": record.timestamp_seconds,
            "sharpness": sharpness(image),
            "motion_from_previous": 0.0 if previous is None else motion(previous, image),
        })
        previous = image

    target_count = 8
    bucket_size = max(1, len(metrics) // target_count)
    selected_indices: list[int] = []
    for bucket in range(target_count):
        start = bucket * bucket_size
        end = len(metrics) if bucket == target_count - 1 else min(len(metrics), start + bucket_size)
        candidates = metrics[start:end]
        best = max(
            candidates,
            key=lambda item: float(item["motion_from_previous"]) * 2.0 + float(item["sharpness"]) / 100.0,
        )
        selected_indices.append(int(best["index"]))

    selected_records: list[dict[str, object]] = []
    for order, index in enumerate(selected_indices):
        source = FRAMES / records[index].filename
        destination = SELECTED / f"dash_{order:02d}_frame_{index:06d}.png"
        shutil.copy2(source, destination)
        selected_records.append({
            "order": order,
            "frame_index": index,
            "timestamp_seconds": records[index].timestamp_seconds,
            "source_filename": records[index].filename,
            "selected_filename": destination.name,
            "sharpness": metrics[index]["sharpness"],
            "motion_from_previous": metrics[index]["motion_from_previous"],
        })

    report = {
        "fixture_id": "cat-trap-aeris-dash-v1",
        "video": str(VIDEO.relative_to(ROOT)),
        "frame_count": len(records),
        "selected_count": len(selected_records),
        "selection_policy": "8 temporal buckets; maximize motion energy plus normalized sharpness",
        "selected_frames": selected_records,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
