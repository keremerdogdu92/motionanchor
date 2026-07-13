# tools/compose_rgba_sequence.py
"""Compose matching frame and mask directories into deterministic RGBA cutouts."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from motionanchor_worker.masks import compose_rgba_cutout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--masks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--feather-radius", type=float, default=1.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame_paths = sorted(args.frames.resolve(strict=True).glob("frame_*.png"))
    mask_paths = sorted(args.masks.resolve(strict=True).glob("frame_*.png"))
    if not frame_paths or len(frame_paths) != len(mask_paths):
        raise RuntimeError("frame and mask sequences must be non-empty and equal length")
    if args.output.exists():
        raise FileExistsError("output directory already exists")
    args.output.mkdir(parents=True)

    results = []
    for frame_path, mask_path in zip(frame_paths, mask_paths, strict=True):
        if frame_path.name != mask_path.name:
            raise RuntimeError("frame and mask filenames must match")
        result = compose_rgba_cutout(
            frame_path,
            mask_path,
            args.output / frame_path.name,
            feather_radius=args.feather_radius,
        )
        results.append(asdict(result))

    report = {
        "frame_count": len(results),
        "feather_radius": args.feather_radius,
        "translucent_pixels": sum(item["translucent_pixels"] for item in results),
        "opaque_pixels": sum(item["opaque_pixels"] for item in results),
        "frames": results,
    }
    report_path = args.output / "rgba-sequence-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "frame_count", "feather_radius", "translucent_pixels", "opaque_pixels"
    )}, indent=2))


if __name__ == "__main__":
    main()
