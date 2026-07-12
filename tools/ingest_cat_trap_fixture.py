from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / "fixtures" / "cat-trap" / "incoming"
REFERENCES = ROOT / "fixtures" / "cat-trap" / "references"
VIDEOS = ROOT / "fixtures" / "cat-trap" / "videos"
REPORT = ROOT / "fixtures" / "cat-trap" / "fixture-report.json"

FILE_MAP = {
    "Chibi kahraman sprite sheet.png": REFERENCES / "animation-sheet.png",
    "1.png": REFERENCES / "turnaround.png",
    "2.png": REFERENCES / "rigging-reference.png",
    "Dash_animasyonu_yapalım.mp4": VIDEOS / "dash.mp4",
}


def inspect_image(path: Path) -> dict[str, object]:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"unreadable image: {path}")
    channels = 1 if image.ndim == 2 else image.shape[2]
    alpha_min = alpha_max = None
    if channels == 4:
        alpha = image[:, :, 3]
        alpha_min = int(alpha.min())
        alpha_max = int(alpha.max())
    height, width = image.shape[:2]
    return {
        "path": str(path.relative_to(ROOT)),
        "width": int(width),
        "height": int(height),
        "channels": int(channels),
        "alpha_min": alpha_min,
        "alpha_max": alpha_max,
        "embedded_checkerboard": channels == 4 and alpha_min == 255 and alpha_max == 255,
    }


def inspect_video(path: Path) -> dict[str, object]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"unreadable video: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    return {
        "path": str(path.relative_to(ROOT)),
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frames,
        "duration_seconds": frames / fps if fps > 0 else None,
    }


def main() -> None:
    REFERENCES.mkdir(parents=True, exist_ok=True)
    VIDEOS.mkdir(parents=True, exist_ok=True)
    missing = [name for name in FILE_MAP if not (INCOMING / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing incoming fixtures: {missing}")

    copied: list[str] = []
    for source_name, destination in FILE_MAP.items():
        source = INCOMING / source_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(str(destination.relative_to(ROOT)))

    images = [inspect_image(path) for path in sorted(REFERENCES.glob("*.png"))]
    videos = [inspect_video(path) for path in sorted(VIDEOS.glob("*.mp4"))]
    report = {
        "fixture_id": "cat-trap-aeris-v1",
        "copied_files": copied,
        "images": images,
        "videos": videos,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
