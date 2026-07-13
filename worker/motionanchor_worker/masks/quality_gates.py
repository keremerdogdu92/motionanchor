# worker/motionanchor_worker/masks/quality_gates.py
"""Apply conservative deterministic export gates to normalized RGBA sequences."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from .quality import analyze_rgba_sequence


@dataclass(frozen=True)
class QualityFinding:
    """One machine-readable blocker or warning produced by sequence analysis."""

    code: str
    severity: str
    message: str
    frame_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class ExportQualityReport:
    """Deterministic pre-export verdict with conservative safety semantics."""

    status: str
    blockers: tuple[QualityFinding, ...]
    warnings: tuple[QualityFinding, ...]
    exact_duplicate_pairs: tuple[tuple[int, int], ...]
    blur_scores: tuple[float, ...]
    foreground_ratios: tuple[float, ...]


def _read_rgba(path: Path) -> np.ndarray:
    image = cv2.imread(str(path.resolve(strict=True)), cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim != 3 or image.shape[2] != 4:
        raise ValueError(f"frame must be a readable four-channel image: {path}")
    return image


def _content_digest(image: np.ndarray) -> str:
    return hashlib.sha256(image.tobytes(order="C")).hexdigest()


def _blur_score(image: np.ndarray) -> float:
    alpha = image[:, :, 3]
    foreground = alpha > 0
    if not np.any(foreground):
        return 0.0
    gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
    values = cv2.Laplacian(gray, cv2.CV_64F)[foreground]
    return float(values.var()) if values.size else 0.0


def _duplicate_pairs(digests: list[str]) -> tuple[tuple[int, int], ...]:
    pairs: list[tuple[int, int]] = []
    for index in range(1, len(digests)):
        if digests[index] == digests[index - 1]:
            pairs.append((index, index + 1))
    return tuple(pairs)


def evaluate_export_quality(paths: list[Path]) -> ExportQualityReport:
    """Return blockers for objective safety failures and warnings for review signals."""

    quality = analyze_rgba_sequence(paths)
    images = [_read_rgba(path) for path in paths]
    blockers: list[QualityFinding] = []
    warnings: list[QualityFinding] = []

    if quality.empty_frame_count:
        indices = tuple(index + 1 for index, frame in enumerate(quality.frames) if frame.foreground_pixels == 0)
        blockers.append(QualityFinding(
            code="empty_foreground",
            severity="blocker",
            message="One or more frames contain no foreground pixels.",
            frame_indices=indices,
        ))
    if quality.edge_touch_frame_count:
        indices = tuple(index + 1 for index, frame in enumerate(quality.frames) if frame.touches_edge)
        blockers.append(QualityFinding(
            code="foreground_touches_canvas_edge",
            severity="blocker",
            message="Foreground touches the normalized canvas edge; safety padding is insufficient.",
            frame_indices=indices,
        ))

    digests = [_content_digest(image) for image in images]
    duplicates = _duplicate_pairs(digests)
    if duplicates:
        warnings.append(QualityFinding(
            code="exact_consecutive_duplicates",
            severity="warning",
            message="Exact consecutive duplicate frames were detected.",
            frame_indices=tuple(sorted({value for pair in duplicates for value in pair})),
        ))

    blur_scores = tuple(_blur_score(image) for image in images)
    positive_blur = [score for score in blur_scores if score > 0]
    if len(positive_blur) >= 3:
        median = float(np.median(positive_blur))
        low_indices = tuple(index + 1 for index, score in enumerate(blur_scores) if score < median * 0.25)
        if low_indices:
            warnings.append(QualityFinding(
                code="relative_blur_outlier",
                severity="warning",
                message="Frames substantially blurrier than the sequence median were detected.",
                frame_indices=low_indices,
            ))

    foreground_ratios = tuple(frame.foreground_ratio for frame in quality.frames)
    area_jump_indices: list[int] = []
    for index in range(1, len(foreground_ratios)):
        previous = foreground_ratios[index - 1]
        current = foreground_ratios[index]
        if previous <= 0 or current <= 0:
            continue
        ratio = max(previous, current) / min(previous, current)
        if ratio >= 1.75:
            area_jump_indices.extend((index, index + 1))
    if area_jump_indices:
        warnings.append(QualityFinding(
            code="foreground_area_jump",
            severity="warning",
            message="Large consecutive foreground-area changes require visual review.",
            frame_indices=tuple(sorted(set(area_jump_indices))),
        ))

    status = "blocked" if blockers else ("warning" if warnings else "passed")
    return ExportQualityReport(
        status=status,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        exact_duplicate_pairs=duplicates,
        blur_scores=blur_scores,
        foreground_ratios=foreground_ratios,
    )


def export_quality_report_dict(report: ExportQualityReport) -> dict[str, object]:
    """Serialize a quality report using stable camelCase JSON field names."""

    return {
        "status": report.status,
        "blockers": [asdict(finding) for finding in report.blockers],
        "warnings": [asdict(finding) for finding in report.warnings],
        "exactDuplicatePairs": [list(pair) for pair in report.exact_duplicate_pairs],
        "blurScores": list(report.blur_scores),
        "foregroundRatios": list(report.foreground_ratios),
    }
