"""Production acceptance validation for the real Cat Trap dash fixture."""
from __future__ import annotations

import hashlib
import json
import struct

import cv2
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

@dataclass(frozen=True)
class AcceptanceCheck:
    name: str
    passed: bool
    detail: str

@dataclass(frozen=True)
class AcceptanceReport:
    fixture_id: str
    passed: bool
    checks: list[AcceptanceCheck]
    frame_count: int
    selected_count: int
    rgba_count: int
    width: int
    height: int
    sequence_sha256: str


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _png_info(path: Path) -> tuple[int, int, int]:
    with path.open("rb") as handle:
        if handle.read(8) != PNG_SIGNATURE:
            raise ValueError(f"invalid PNG signature: {path}")
        length = struct.unpack(">I", handle.read(4))[0]
        if handle.read(4) != b"IHDR" or length != 13:
            raise ValueError(f"missing PNG IHDR: {path}")
        width, height, _, color_type, _, _, _ = struct.unpack(">IIBBBBB", handle.read(13))
    return width, height, color_type


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_cat_trap_fixture(root: Path) -> AcceptanceReport:
    root = root.resolve()
    dash = root / "dash"
    frames_dir = dash / "frames"
    selected_dir = dash / "selected"
    rgba_dir = dash / "rgba-sam2.1-small-v2-defringed"
    video = root / "videos" / "dash.mp4"
    prompt_path = dash / "sam2-prompts.json"
    selection_path = dash / "selection-report.json"
    rgba_report_path = rgba_dir / "rgba-sequence-report.json"
    checks: list[AcceptanceCheck] = []

    required = [video, prompt_path, selection_path, rgba_report_path, frames_dir, selected_dir, rgba_dir]
    missing = [str(path) for path in required if not path.exists()]
    checks.append(AcceptanceCheck("required_artifacts", not missing, "all present" if not missing else "; ".join(missing)))
    if missing:
        return AcceptanceReport("cat-trap-aeris-dash-v1", False, checks, 0, 0, 0, 0, 0, "")

    frames = sorted(frames_dir.glob("frame_*.png"))
    selection = _json(selection_path)
    selected = selection.get("selected_frames", [])
    rgba_report = _json(rgba_report_path)
    rgba_frames = sorted(rgba_dir.glob("frame_*.png"))
    prompts = _json(prompt_path)

    checks.append(AcceptanceCheck("source_frames", len(frames) == 240, f"{len(frames)}/240 frames"))
    selected_files = [selected_dir / item.get("selected_filename", "") for item in selected if isinstance(item, dict)]
    selected_ok = len(selected) == 8 and all(path.is_file() for path in selected_files)
    checks.append(AcceptanceCheck("motion_selection", selected_ok, f"{len(selected)}/8 selected frames"))

    anchors = prompts.get("anchors", prompts.get("prompts", []))
    anchor_indexes = [item.get("frame_index") for item in anchors if isinstance(item, dict)] if isinstance(anchors, list) else []
    prompt_ok = bool(anchor_indexes) and all(isinstance(index, int) and 0 <= index < len(frames) for index in anchor_indexes)
    checks.append(AcceptanceCheck("sam2_prompts", prompt_ok, f"{len(anchor_indexes)} valid anchors"))

    report_frames = rgba_report.get("frames", [])
    rgba_count_ok = len(rgba_frames) == 240 and rgba_report.get("frame_count") == 240 and len(report_frames) == 240
    checks.append(AcceptanceCheck("rgba_sequence", rgba_count_ok, f"{len(rgba_frames)}/240 RGBA frames"))

    dimensions: set[tuple[int, int]] = set()
    rgba_color_types: set[int] = set()
    hash_failures: list[str] = []
    sequence = hashlib.sha256()
    report_by_name = {Path(item.get("output_path", "")).name: item for item in report_frames if isinstance(item, dict)}
    for path in rgba_frames:
        width, height, color_type = _png_info(path)
        dimensions.add((width, height))
        rgba_color_types.add(color_type)
        file_digest = _sha256(path)
        sequence.update(bytes.fromhex(file_digest))
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        content_digest = hashlib.sha256(image.tobytes(order="C")).hexdigest() if image is not None else ""
        expected = report_by_name.get(path.name, {}).get("sha256")
        if expected != content_digest:
            hash_failures.append(path.name)
    dimension_ok = dimensions == {(1280, 720)}
    checks.append(AcceptanceCheck("dimensions", dimension_ok, str(sorted(dimensions))))
    checks.append(AcceptanceCheck("alpha_channel", rgba_color_types == {6}, f"PNG color types: {sorted(rgba_color_types)}"))
    checks.append(AcceptanceCheck("artifact_hashes", not hash_failures, "all hashes match" if not hash_failures else ", ".join(hash_failures[:5])))

    alpha_metrics_ok = int(rgba_report.get("opaque_pixels", 0)) > 0 and int(rgba_report.get("translucent_pixels", 0)) > 0
    checks.append(AcceptanceCheck("alpha_metrics", alpha_metrics_ok, f"opaque={rgba_report.get('opaque_pixels', 0)}, translucent={rgba_report.get('translucent_pixels', 0)}"))

    passed = all(check.passed for check in checks)
    width, height = next(iter(dimensions), (0, 0))
    return AcceptanceReport(
        fixture_id=str(selection.get("fixture_id", "cat-trap-aeris-dash-v1")),
        passed=passed,
        checks=checks,
        frame_count=len(frames),
        selected_count=len(selected),
        rgba_count=len(rgba_frames),
        width=width,
        height=height,
        sequence_sha256=sequence.hexdigest(),
    )


def write_report(report: AcceptanceReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")

