# ADR-033: Unity Export Asset Naming

**Status:** Accepted  
**Date:** 2026-07-13

## Context

Unity exports require deterministic names that remain readable, sort correctly, and cannot diverge between preview, dry run, manifest generation, and real publication.

## Decision

The user confirms an animation asset name at export time. The project name is only the initial suggestion. Rust normalizes the value and owns the final naming contract.

```text
Assets/MotionAnchor/<asset_name>/
Frames/<asset_name>_frame_0001.png
Frames/<asset_name>_frame_0002.png
<asset_name>.anim
```

Frame numbering is one-based and zero-padded to four digits. The RGBA review screen displays the current asset name and example output pattern. Changing the name invalidates the prior dry-run plan. The manifest stores both `assetName` and the exact ordered frame paths.

## Consequences

- Lexical ordering matches animation ordering.
- Multiple animations from one project remain distinguishable.
- Dry-run and real export cannot silently use different names.
- Unity AnimationClip creation can reuse the same asset name later.
- Existing export targets remain protected by conflict checks.
