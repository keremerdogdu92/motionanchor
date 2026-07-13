# worker/motionanchor_worker/segmentation/sam2_process.py
"""Isolated SAM 2.1 GPU process for masks and RGBA artifacts.

This module runs only inside the pinned Python 3.12 SAM 2 environment and
communicates with the parent worker through NDJSON stdout events.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np
import torch
from sam2.build_sam import build_sam2_video_predictor

WORKER = Path(__file__).resolve().parents[2]
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from motionanchor_worker.benchmarks import compare_temporal_masks
from motionanchor_worker.masks import (
    analyze_rgba_sequence,
    compose_rgba_cutout,
    normalize_rgba_sequence,
)

MODEL = {
    "checkpoint": WORKER / "models" / "sam2" / "sam2.1_hiera_small.pt",
    "config": "configs/sam2.1/sam2.1_hiera_s.yaml",
    "sha256": "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
}


def emit(event_type: str, **payload: object) -> None:
    print(json.dumps({"type": event_type, **payload}, separators=(",", ":")), flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_prompts(path: Path, frame_count: int) -> dict[int, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    anchors = data.get("anchors") if isinstance(data, dict) else None
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("prompt file requires a non-empty anchors array")
    result: dict[int, dict] = {}
    for anchor in anchors:
        if not isinstance(anchor, dict) or not isinstance(anchor.get("frame_index"), int):
            raise ValueError("each anchor requires an integer frame_index")
        index = anchor["frame_index"]
        if index < 0 or index >= frame_count or index in result:
            raise ValueError("anchor frame_index is invalid or duplicated")
        box = anchor.get("box")
        positive = anchor.get("positive", [])
        negative = anchor.get("negative", [])
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError("anchor.box must contain four coordinates")
        if not isinstance(positive, list) or not positive:
            raise ValueError("anchor.positive must not be empty")
        if not isinstance(negative, list):
            raise ValueError("anchor.negative must be an array")
        result[index] = {"box": box, "positive": positive, "negative": negative}
    return result


def fill_enclosed_holes(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, mode="constant", constant_values=0)
    reachable = padded.copy()
    flood_mask = np.zeros((padded.shape[0] + 2, padded.shape[1] + 2), dtype=np.uint8)
    cv2.floodFill(reachable, flood_mask, (0, 0), 255)
    return cv2.bitwise_or(padded, cv2.bitwise_not(reachable))[1:-1, 1:-1]


def prepare_jpegs(frames: list[Path], target: Path) -> None:
    target.mkdir(parents=True)
    for index, frame in enumerate(frames):
        image = cv2.imread(str(frame), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"failed to read frame: {frame}")
        if not cv2.imwrite(str(target / f"{index:06d}.jpg"), image, [cv2.IMWRITE_JPEG_QUALITY, 100]):
            raise RuntimeError("failed to prepare SAM 2 JPEG frame")


def add_anchor(predictor: object, state: dict, frame_index: int, prompt: dict) -> None:
    points = np.asarray(prompt["positive"] + prompt["negative"], dtype=np.float32)
    labels = np.asarray([1] * len(prompt["positive"]) + [0] * len(prompt["negative"]), dtype=np.int32)
    predictor.add_new_points_or_box(
        inference_state=state,
        frame_idx=frame_index,
        obj_id=1,
        points=points,
        labels=labels,
        box=np.asarray(prompt["box"], dtype=np.float32),
        clear_old_points=True,
    )


def write_mask(logits: torch.Tensor, path: Path) -> None:
    mask = (logits > 0.0).detach().cpu().numpy().squeeze().astype(np.uint8) * 255
    if mask.ndim != 2:
        raise RuntimeError(f"unexpected SAM 2 mask shape: {mask.shape}")
    if not cv2.imwrite(str(path), fill_enclosed_holes(mask)):
        raise RuntimeError(f"failed to write mask: {path}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: sam2_process.py REQUEST.json")
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    frames_dir = Path(request["frames_path"])
    output = Path(request["output_path"])
    prompt_path = Path(request["prompt_path"])
    frames = sorted(frames_dir.glob("frame_*.png"))
    if len(frames) < 2:
        raise ValueError("frames_path must contain at least two frame_*.png files")
    prompts = load_prompts(prompt_path, len(frames))
    checkpoint = Path(MODEL["checkpoint"])
    if sha256(checkpoint) != MODEL["sha256"]:
        raise RuntimeError("SAM 2 checkpoint checksum mismatch")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for the SAM 2 small profile")

    jpeg_dir, masks_dir, rgba_dir = output / "_sam2_jpeg", output / "masks", output / "rgba"
    output.mkdir(parents=True)
    masks_dir.mkdir()
    rgba_dir.mkdir()
    emit("progress", progress=0.03, message="Preparing SAM 2 frames")
    prepare_jpegs(frames, jpeg_dir)

    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    predictor = build_sam2_video_predictor(MODEL["config"], str(checkpoint), device="cuda")
    started = time.perf_counter()
    mask_paths: list[Path | None] = [None] * len(frames)
    with torch.inference_mode(), torch.amp.autocast("cuda", dtype=torch.bfloat16):
        state = predictor.init_state(video_path=str(jpeg_dir), offload_video_to_cpu=True, offload_state_to_cpu=True)
        for frame_index, prompt in sorted(prompts.items()):
            add_anchor(predictor, state, frame_index, prompt)
        for count, (frame_index, object_ids, logits) in enumerate(predictor.propagate_in_video(state), start=1):
            if list(object_ids) != [1]:
                raise RuntimeError(f"unexpected SAM 2 object ids: {object_ids}")
            mask_path = masks_dir / frames[frame_index].name
            write_mask(logits, mask_path)
            mask_paths[frame_index] = mask_path
            emit("progress", progress=0.08 + 0.68 * count / len(frames), message=f"Segmenting frame {count}/{len(frames)}")

    if any(path is None for path in mask_paths):
        raise RuntimeError("SAM 2 did not produce every frame")
    resolved_masks = [path for path in mask_paths if path is not None]
    for index, (frame, mask) in enumerate(zip(frames, resolved_masks), start=1):
        compose_rgba_cutout(
            frame,
            mask,
            rgba_dir / frame.name,
            float(request["feather_radius"]),
            bool(request["defringe"]),
        )
        if index % 12 == 0 or index == len(frames):
            emit("progress", progress=0.78 + 0.17 * index / len(frames), message=f"Composing frame {index}/{len(frames)}")

    ordered_rgba = sorted(rgba_dir.glob("frame_*.png"))
    temporal = compare_temporal_masks(resolved_masks)
    quality = analyze_rgba_sequence(ordered_rgba)
    emit("progress", progress=0.96, message="Building shared animation canvas")
    shared_canvas = normalize_rgba_sequence(ordered_rgba, output / "shared_canvas", padding=16)
    report = {
        "engine_id": "sam2.1.video.hiera-small.v1",
        "frame_count": len(frames),
        "gpu": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
        "checkpoint_sha256": MODEL["sha256"],
        "elapsed_seconds": time.perf_counter() - started,
        "temporal": {key: value for key, value in asdict(temporal).items() if key != "pairs"},
        "quality": {key: value for key, value in asdict(quality).items() if key != "frames"},
        "shared_canvas": {
            "width": shared_canvas.canvas_width,
            "height": shared_canvas.canvas_height,
            "pivot_x": shared_canvas.pivot_x,
            "pivot_y": shared_canvas.pivot_y,
            "baseline_y": shared_canvas.baseline_y,
            "sequence_sha256": shared_canvas.sequence_sha256,
        },
        "masks_path": str(masks_dir.resolve()),
        "rgba_path": str(rgba_dir.resolve()),
        "normalized_rgba_path": shared_canvas.output_path,
        "shared_canvas_report_path": shared_canvas.report_path,
        "prompt_path": str(prompt_path.resolve()),
    }
    report_path = output / "sam2-rgba-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    shutil.rmtree(jpeg_dir)
    emit("result", payload={**report, "report_path": str(report_path.resolve())})


if __name__ == "__main__":
    main()
