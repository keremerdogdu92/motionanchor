# ADR-034: Engine-Neutral Core Architecture

**Status:** Accepted  
**Date:** 2026-07-14

## Context

MotionAnchor began with Unity 2022.3 export work because Cat Trap uses Unity. Unity's changing support tiers and Extended LTS access demonstrate that the product cannot treat a proprietary editor version as its core platform contract. Godot offers a strategically important open-source route, while other 2D engines may become valuable adapters later.

## Decision

MotionAnchor is an engine-neutral animation pipeline. The canonical output is Animation Manifest v2 plus deterministic RGBA artifacts. Engine assets are generated only by adapters.

Adapter priority is:

1. Unity 6 — first production adapter for current project continuity.
2. Godot 4 — second official adapter and preferred open-source strategic direction.
3. Unity 2022.3 — compatibility target.
4. GameMaker, Unreal Paper2D, and others — later feasibility-driven adapters.

The `.motionanchor` format will become a separate versioned project container. It will not replace the portable animation manifest and will never contain credentials.

## Consequences

- Core entities and schemas cannot depend on Unity, Godot, or another engine API.
- Unity-specific importer code remains isolated in the Unity adapter.
- Godot support can be added without migrating project data.
- Engine pricing, licensing, or version-policy changes do not invalidate MotionAnchor projects.
- Adapter contract tests and compatibility matrices become mandatory.
- Some engine-specific conveniences may require adapter profiles outside the canonical manifest.

## Naming Contract

Exported frame names remain deterministic:

```text
<asset_name>_frame_0001.png
<asset_name>_frame_0002.png
```

Adapters must preserve canonical frame order from the manifest rather than inferring order from filesystem enumeration.
