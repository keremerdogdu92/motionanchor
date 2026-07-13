# tools/build_rgba_contact_sheet.py
"""Render RGBA cutouts over diagnostic backgrounds for visual edge review."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rgba", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--indices", type=int, nargs="+", required=True)
    return parser.parse_args()


def checkerboard(height: int, width: int, cell: int = 24) -> np.ndarray:
    yy, xx = np.indices((height, width))
    cells = ((xx // cell) + (yy // cell)) % 2
    values = np.where(cells[..., None] == 0, 72, 144).astype(np.uint8)
    return np.repeat(values, 3, axis=2)


def composite(rgba: np.ndarray, background: np.ndarray) -> np.ndarray:
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    foreground = rgba[:, :, :3].astype(np.float32)
    result = foreground * alpha + background.astype(np.float32) * (1.0 - alpha)
    return np.rint(result).astype(np.uint8)


def main() -> None:
    args = parse_args()
    tiles: list[np.ndarray] = []
    for index in args.indices:
        path = args.rgba.resolve(strict=True) / f"frame_{index:06d}.png"
        rgba = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if rgba is None or rgba.ndim != 3 or rgba.shape[2] != 4:
            raise RuntimeError(f"invalid RGBA frame: {path}")
        height, width = rgba.shape[:2]
        backgrounds = [
            np.full((height, width, 3), 255, dtype=np.uint8),
            np.full((height, width, 3), 24, dtype=np.uint8),
            checkerboard(height, width),
        ]
        rendered = [composite(rgba, background) for background in backgrounds]
        strip = cv2.hconcat([cv2.resize(item, (320, 180)) for item in rendered])
        cv2.putText(strip, f"frame {index}", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 1, cv2.LINE_AA)
        tiles.append(strip)

    sheet = cv2.vconcat(tiles)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), sheet):
        raise RuntimeError("failed to write RGBA contact sheet")


if __name__ == "__main__":
    main()
