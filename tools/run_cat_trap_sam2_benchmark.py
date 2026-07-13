# tools/run_cat_trap_sam2_benchmark.py
"""Run a pinned SAM 2.1 video-mask benchmark on Cat Trap dash frames."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np
import torch
from sam2.build_sam import build_sam2_video_predictor

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from motionanchor_worker.benchmarks import compare_temporal_masks

FRAMES = ROOT / "fixtures" / "cat-trap" / "dash" / "frames"
JPEG_FRAMES = ROOT / "fixtures" / "cat-trap" / "dash" / "frames-sam2-jpeg"
MODEL_NAME = os.environ.get("MOTIONANCHOR_SAM2_MODEL", "tiny").strip().lower()
MODEL_SPECS = {
    "tiny": {
        "checkpoint": WORKER / "models" / "sam2" / "sam2.1_hiera_tiny.pt",
        "config": "configs/sam2.1/sam2.1_hiera_t.yaml",
        "sha256": "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69",
    },
    "small": {
        "checkpoint": WORKER / "models" / "sam2" / "sam2.1_hiera_small.pt",
        "config": "configs/sam2.1/sam2.1_hiera_s.yaml",
        "sha256": "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
    },
}
if MODEL_NAME not in MODEL_SPECS:
    raise RuntimeError(f"unsupported SAM 2 benchmark model: {MODEL_NAME}")
MODEL = MODEL_SPECS[MODEL_NAME]
OUTPUT = ROOT / "fixtures" / "cat-trap" / "dash" / f"masks-sam2.1-{MODEL_NAME}-v1"
REPORT = ROOT / "fixtures" / "cat-trap" / "dash" / f"sam2-{MODEL_NAME}-mask-benchmark-report.json"
CONTACT = ROOT / "fixtures" / "cat-trap" / "dash" / f"sam2-{MODEL_NAME}-mask-contact-sheet.png"

ANCHORS = {
    0: {
        "box": [350.0, 20.0, 905.0, 710.0],
        "positive": [[640.0, 190.0], [620.0, 390.0], [560.0, 555.0], [430.0, 180.0], [800.0, 430.0]],
        "negative": [[360.0, 350.0], [895.0, 120.0], [895.0, 675.0]],
    },
    120: {
        "box": [145.0, 65.0, 1040.0, 700.0],
        "positive": [[475.0, 220.0], [580.0, 370.0], [500.0, 520.0], [235.0, 280.0], [850.0, 330.0]],
        "negative": [[80.0, 350.0], [1110.0, 300.0], [1120.0, 650.0]],
    },
    180: {
        "box": [360.0, 30.0, 920.0, 705.0],
        "positive": [[640.0, 200.0], [620.0, 390.0], [620.0, 570.0], [420.0, 190.0], [820.0, 500.0]],
        "negative": [[300.0, 580.0], [930.0, 100.0], [1120.0, 600.0]],
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_jpeg_frames(frame_paths: list[Path]) -> None:
    if JPEG_FRAMES.exists():
        shutil.rmtree(JPEG_FRAMES)
    JPEG_FRAMES.mkdir(parents=True)
    for index, frame_path in enumerate(frame_paths):
        image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"failed to read frame: {frame_path}")
        target = JPEG_FRAMES / f"{index:06d}.jpg"
        if not cv2.imwrite(str(target), image, [cv2.IMWRITE_JPEG_QUALITY, 100]):
            raise RuntimeError(f"failed to write SAM 2 JPEG frame: {target}")


def add_anchor(predictor: object, state: dict[str, object], frame_index: int) -> None:
    prompt = ANCHORS[frame_index]
    points = np.asarray(prompt["positive"] + prompt["negative"], dtype=np.float32)
    labels = np.asarray([1] * len(prompt["positive"]) + [0] * len(prompt["negative"]), dtype=np.int32)
    box = np.asarray(prompt["box"], dtype=np.float32)
    predictor.add_new_points_or_box(
        inference_state=state,
        frame_idx=frame_index,
        obj_id=1,
        points=points,
        labels=labels,
        box=box,
        clear_old_points=True,
    )


def fill_enclosed_holes(mask: np.ndarray) -> np.ndarray:
    """Fill only background regions that are not connected to the image border."""
    padded = np.pad(mask, 1, mode="constant", constant_values=0)
    reachable_background = padded.copy()
    flood_mask = np.zeros((padded.shape[0] + 2, padded.shape[1] + 2), dtype=np.uint8)
    cv2.floodFill(reachable_background, flood_mask, (0, 0), 255)
    enclosed_holes = cv2.bitwise_not(reachable_background)
    return cv2.bitwise_or(padded, enclosed_holes)[1:-1, 1:-1]


def write_mask(mask_logits: torch.Tensor, path: Path) -> float:
    mask = (mask_logits > 0.0).detach().cpu().numpy().squeeze().astype(np.uint8) * 255
    if mask.ndim != 2:
        raise RuntimeError(f"unexpected SAM 2 mask shape after squeeze: {mask.shape}")
    mask = fill_enclosed_holes(mask)
    if not cv2.imwrite(str(path), mask):
        raise RuntimeError(f"failed to write mask: {path}")
    return float(np.count_nonzero(mask) / mask.size)


def build_contact_sheet(frame_paths: list[Path], mask_paths: list[Path], indices: list[int]) -> None:
    tiles: list[np.ndarray] = []
    for index in indices:
        frame = cv2.imread(str(frame_paths[index]), cv2.IMREAD_COLOR)
        mask = cv2.imread(str(mask_paths[index]), cv2.IMREAD_GRAYSCALE)
        if frame is None or mask is None:
            raise RuntimeError("failed to load contact-sheet artifact")
        overlay = frame.copy()
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, (0, 255, 255), 2)
        cv2.putText(overlay, f"frame {index}", (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        tiles.append(cv2.resize(overlay, (480, 270), interpolation=cv2.INTER_AREA))
    rows = [cv2.hconcat(tiles[offset:offset + 2]) for offset in range(0, len(tiles), 2)]
    sheet = cv2.vconcat(rows)
    if not cv2.imwrite(str(CONTACT), sheet):
        raise RuntimeError("failed to write SAM 2 contact sheet")


def main() -> None:
    frame_paths = sorted(FRAMES.glob("frame_*.png"))
    if len(frame_paths) != 240:
        raise RuntimeError(f"expected 240 extracted frames, found {len(frame_paths)}")
    checkpoint = Path(MODEL["checkpoint"])
    checkpoint_sha256 = str(MODEL["sha256"])
    config = str(MODEL["config"])
    if sha256(checkpoint) != checkpoint_sha256:
        raise RuntimeError("SAM 2 checkpoint checksum mismatch")
    prepare_jpeg_frames(frame_paths)
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    predictor = build_sam2_video_predictor(config, str(checkpoint), device="cuda")
    started = time.perf_counter()
    with torch.inference_mode(), torch.amp.autocast("cuda", dtype=torch.bfloat16):
        state = predictor.init_state(
            video_path=str(JPEG_FRAMES),
            offload_video_to_cpu=True,
            offload_state_to_cpu=True,
        )
        for frame_index in sorted(ANCHORS):
            add_anchor(predictor, state, frame_index)

        mask_paths: list[Path | None] = [None] * len(frame_paths)
        foreground_ratios: list[float | None] = [None] * len(frame_paths)
        for frame_index, object_ids, mask_logits in predictor.propagate_in_video(state):
            if list(object_ids) != [1]:
                raise RuntimeError(f"unexpected SAM 2 object ids: {object_ids}")
            mask_path = OUTPUT / frame_paths[frame_index].name
            foreground_ratios[frame_index] = write_mask(mask_logits, mask_path)
            mask_paths[frame_index] = mask_path

    if any(path is None for path in mask_paths) or any(value is None for value in foreground_ratios):
        raise RuntimeError("SAM 2 propagation did not produce every frame")
    resolved_masks = [path for path in mask_paths if path is not None]
    ratios = [value for value in foreground_ratios if value is not None]
    temporal = compare_temporal_masks(resolved_masks)
    elapsed = time.perf_counter() - started

    report = {key: value for key, value in asdict(temporal).items() if key != "pairs"}
    report.update(
        {
            "engine_id": f"sam2.1.video.hiera-{MODEL_NAME}.v1",
            "sam2_commit": "2b90b9f5ceec907a1c18123530e92e794ad901a4",
            "checkpoint_sha256": checkpoint_sha256,
            "torch_version": torch.__version__,
            "gpu": torch.cuda.get_device_name(0),
            "anchor_prompts": ANCHORS,
            "mean_foreground_ratio": float(sum(ratios) / len(ratios)),
            "minimum_foreground_ratio": float(min(ratios)),
            "maximum_foreground_ratio": float(max(ratios)),
            "elapsed_seconds": elapsed,
            "frames_per_second": len(frame_paths) / elapsed,
            "approval_status": "experimental_pending_visual_review",
            "assessment": f"Multi-anchor SAM 2.1 {MODEL_NAME} propagation completed. Manual ground-truth masks are still required before production approval.",
        }
    )
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    build_contact_sheet(frame_paths, resolved_masks, [0, 30, 60, 90, 120, 150, 180, 210])
    print(json.dumps({key: report[key] for key in (
        "frame_count", "mean_aligned_iou", "minimum_aligned_iou",
        "mean_boundary_turnover_ratio", "maximum_boundary_turnover_ratio",
        "mean_foreground_ratio", "elapsed_seconds", "frames_per_second",
    )}, indent=2))


if __name__ == "__main__":
    main()
