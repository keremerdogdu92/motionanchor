from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from motionanchor_worker.benchmarks import compare_temporal_masks
from motionanchor_worker.masks import TemporalMedianMaskEngine

FRAMES = ROOT / "fixtures" / "cat-trap" / "dash" / "frames"
OUTPUT = ROOT / "fixtures" / "cat-trap" / "dash" / "masks-temporal-median-v1"
REPORT = ROOT / "fixtures" / "cat-trap" / "dash" / "mask-benchmark-report.json"
CONTACT = ROOT / "fixtures" / "cat-trap" / "dash" / "mask-worst-pairs.png"


def build_contact_sheet(pairs: list[dict[str, object]], frame_paths: list[Path], mask_paths: list[Path]) -> None:
    tiles = []
    for pair in pairs:
        index = int(pair["current_index"])
        frame = cv2.imread(str(frame_paths[index]), cv2.IMREAD_COLOR)
        mask = cv2.imread(str(mask_paths[index]), cv2.IMREAD_GRAYSCALE)
        if frame is None or mask is None:
            raise RuntimeError("failed to read benchmark artifact")
        overlay = frame.copy()
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, (0, 255, 255), 2)
        cv2.putText(overlay, f"pair {index-1}->{index} iou={pair['aligned_iou']:.3f}",
                    (24, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        tiles.append(cv2.resize(overlay, (480, 270), interpolation=cv2.INTER_AREA))
    rows = [cv2.hconcat(tiles[i:i + 2]) for i in range(0, len(tiles), 2)]
    sheet = cv2.vconcat(rows)
    if not cv2.imwrite(str(CONTACT), sheet):
        raise RuntimeError("failed to write contact sheet")


def main() -> None:
    frame_paths = sorted(FRAMES.glob("frame_*.png"))
    if len(frame_paths) != 240:
        raise RuntimeError(f"expected 240 extracted frames, found {len(frame_paths)}")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    engine = TemporalMedianMaskEngine(lab_distance_threshold=12.0, sample_count=30, minimum_component_pixels=300)
    engine.fit(frame_paths)
    mask_paths = []
    foreground_ratios = []
    for frame in frame_paths:
        mask_path = OUTPUT / frame.name
        result = engine.create_mask(frame, mask_path)
        mask_paths.append(mask_path)
        foreground_ratios.append(result.foreground_ratio)

    temporal = compare_temporal_masks(mask_paths)
    pairs = [asdict(pair) for pair in temporal.pairs]
    worst = sorted(pairs, key=lambda pair: (pair["aligned_iou"], -pair["boundary_turnover_ratio"]))[:8]
    payload = {key: value for key, value in asdict(temporal).items() if key != "pairs"}
    payload["engine_id"] = engine.engine_id
    payload["lab_distance_threshold"] = engine.lab_distance_threshold
    payload["sample_count"] = engine.sample_count
    payload["minimum_component_pixels"] = engine.minimum_component_pixels
    payload["mean_foreground_ratio"] = sum(foreground_ratios) / len(foreground_ratios)
    payload["minimum_foreground_ratio"] = min(foreground_ratios)
    payload["maximum_foreground_ratio"] = max(foreground_ratios)
    payload["worst_pairs"] = worst
    payload["approval_status"] = "rejected_for_production"
    payload["assessment"] = "Temporal median baseline isolates broad motion but merges speed lines and dust, loses interior character regions, and has excessive boundary turnover. No manually approved ground truth exists yet."
    REPORT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    build_contact_sheet(worst, frame_paths, mask_paths)
    print(json.dumps({key: payload[key] for key in (
        "frame_count", "mean_aligned_iou", "minimum_aligned_iou",
        "mean_boundary_turnover_ratio", "maximum_boundary_turnover_ratio",
        "mean_foreground_ratio")}, indent=2))


if __name__ == "__main__":
    main()
