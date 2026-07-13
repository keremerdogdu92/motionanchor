# MotionAnchor Engine-Neutral Manifest v2 and Project Format

**Status:** Initial approved design baseline
**Date:** 2026-07-14

## 1. Canonical Animation Manifest v2

The canonical manifest is portable and contains no engine-owned identifiers.

```json
{
  "schemaVersion": 2,
  "assetName": "warlock_dash",
  "frames": [
    { "index": 1, "path": "Frames/warlock_dash_frame_0001.png", "durationMs": 33.333 }
  ],
  "frameRate": 30,
  "loop": true,
  "canvas": { "width": 512, "height": 512 },
  "pivot": { "space": "normalized", "x": 0.5, "y": 0.1 },
  "pixelsPerUnit": 100,
  "tags": ["dash"],
  "events": [],
  "provenance": {},
  "contentHashes": {}
}
```

## 2. Required Rules

- `assetName` is sanitized deterministically.
- Frame naming uses `<asset_name>_frame_<zero-padded index>.png`.
- Frame order is explicit and authoritative.
- FPS is between 1 and 240.
- Pivot uses normalized coordinates unless another declared coordinate space is added in a later schema.
- Engine-specific IDs and serialized assets are prohibited from canonical fields.
- Schema migrations are explicit and testable.

## 3. Adapter Outputs

- Unity 6 adapter: Sprite imports, `.anim`, optional Animator Controller.
- Unity 2022.3 compatibility adapter: equivalent output where supported.
- Godot 4 adapter: imported textures, `SpriteFrames`, `.tres`, optional `AnimatedSprite2D` scene.
- Generic exporter: PNG sequence, sprite sheet, contact sheet, manifest.
- Future adapters: GameMaker, Unreal Paper2D, Spine/Live2D preparation.

## 4. `.motionanchor` Project Container

The future project container stores or references:

- project and character metadata,
- source media references and hashes,
- prompts and segmentation settings,
- approved masks and frame selections,
- timeline, loop, pivot, crop, and canvas decisions,
- manifest history,
- preview thumbnails,
- adapter export profiles and result history.

It must not contain API keys or other credentials. Large media may remain externally referenced with content hashes to keep project containers portable and manageable.

## 5. Compatibility Policy

Core project and manifest schemas are versioned independently from engine adapters. An adapter declares which manifest versions and engine versions it supports. Unsupported combinations fail during dry-run validation before any target project is modified.


## 6. Canonical Export Package

The production canonical exporter publishes packages under `<workspace>/exports/<asset_name>/` using an atomic staging directory. Each package contains the v2 manifest and naturally ordered RGBA frames under `Frames/`.

- Existing package directories are never replaced automatically.
- Every frame receives a SHA-256 entry keyed by its manifest-relative path.
- `contentHashes.packageSummary` is a deterministic SHA-256 digest of the validated manifest inputs and frame hashes before the summary field is inserted.
- Canonical provenance remains engine-neutral; adapter identity belongs to adapter outputs, not the canonical package.
- Unity adapters consume the published canonical package instead of reading `artifacts/rgba` directly during export execution.
