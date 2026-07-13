# tools/analyze_rgba_sequence.py
"""Generate objective RGBA alpha-quality diagnostics for a frame sequence."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from motionanchor_worker.masks import analyze_rgba_sequence

SEQUENCE = ROOT / "fixtures" / "cat-trap" / "dash" / "rgba-sam2.1-small-v2-defringed"
REPORT = ROOT / "fixtures" / "cat-trap" / "dash" / "sam2-small-rgba-quality-report.json"


def main() -> None:
    paths = sorted(SEQUENCE.glob("frame_*.png"))
    result = analyze_rgba_sequence(paths)
    payload = asdict(result)
    payload["frames_by_fragmentation"] = [
        frame["path"] for frame in sorted(
            payload["frames"],
            key=lambda item: (item["largest_component_ratio"], -item["component_count"]),
        )[:12]
    ]
    REPORT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "frame_count": result.frame_count,
        "dimensions": [result.width, result.height],
        "empty_frame_count": result.empty_frame_count,
        "edge_touch_frame_count": result.edge_touch_frame_count,
        "maximum_component_count": result.maximum_component_count,
        "minimum_largest_component_ratio": result.minimum_largest_component_ratio,
        "minimum_foreground_ratio": result.minimum_foreground_ratio,
        "maximum_foreground_ratio": result.maximum_foreground_ratio,
        "report": str(REPORT),
    }, indent=2))


if __name__ == "__main__":
    main()
