"""worker/tests/test_animation_manifest.py

Verifies strict, deterministic validation of the engine-neutral export manifest.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from motionanchor_worker.exports import ManifestValidationError, load_animation_manifest


class AnimationManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "schema_version": "1.0",
            "animation": {
                "name": "CatTrap_Dash_01", "fps": 8, "loop": False, "frame_count": 2,
                "pivot": {"mode": "bottom_center", "x": 0.5, "y": 0.0}, "pixels_per_unit": 160
            },
            "sprite_sheet": {
                "path": "textures/CatTrap_Dash_01.png", "sha256": "a" * 64,
                "columns": 2, "rows": 1, "cell_width": 512, "cell_height": 512, "padding": 0
            },
            "frames": [
                {"index": 0, "name": "CatTrap_Dash_01_000", "duration_ms": 125, "source_path": "frames/000.png", "sha256": "b" * 64},
                {"index": 1, "name": "CatTrap_Dash_01_001", "duration_ms": 125, "source_path": "frames/001.png", "sha256": "c" * 64}
            ]
        }

    def write(self, payload: dict) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "animation.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_loads_valid_manifest(self) -> None:
        manifest = load_animation_manifest(self.write(self.payload))
        self.assertEqual(manifest.name, "CatTrap_Dash_01")
        self.assertEqual(len(manifest.frames), 2)
        self.assertEqual(manifest.pivot.y, 0.0)

    def test_repository_fixture_matches_contract(self) -> None:
        fixture = Path(__file__).resolve().parents[2] / "fixtures" / "unity" / "minimal-animation-manifest.json"
        manifest = load_animation_manifest(fixture)
        self.assertEqual(manifest.schema_version, "1.0")
        self.assertEqual(manifest.sprite_sheet.columns, 2)

    def test_rejects_unknown_root_fields(self) -> None:
        self.payload["unexpected"] = True
        with self.assertRaisesRegex(ManifestValidationError, "invalid keys"):
            load_animation_manifest(self.write(self.payload))

    def test_rejects_parent_traversal(self) -> None:
        self.payload["sprite_sheet"]["path"] = "../escape.png"
        with self.assertRaisesRegex(ManifestValidationError, "safe relative path"):
            load_animation_manifest(self.write(self.payload))

    def test_rejects_non_contiguous_indices(self) -> None:
        self.payload["frames"][1]["index"] = 3
        with self.assertRaisesRegex(ManifestValidationError, "contiguous"):
            load_animation_manifest(self.write(self.payload))

    def test_rejects_grid_capacity_mismatch(self) -> None:
        self.payload["sprite_sheet"]["columns"] = 1
        with self.assertRaisesRegex(ManifestValidationError, "cannot contain"):
            load_animation_manifest(self.write(self.payload))


if __name__ == "__main__":
    unittest.main()
