# ADR-015: OpenCV Deterministic Mask Baseline

- Status: Accepted for Phase 0 baseline
- Date: 2026-07-12

## Decision

Use `opencv-python-headless==4.13.0.92` with `numpy==2.4.6` behind a MotionAnchor-owned `MaskEngine` contract for deterministic image-mask primitives.

The initial adapters are:

- `ExistingAlphaMaskEngine`, which preserves an existing alpha channel as the mask;
- `ChromaKeyMaskEngine`, which creates a binary foreground mask from configurable HSV green-screen bounds.

Each result records the engine ID/version, dimensions, foreground pixel count and ratio, foreground bounds, edge-contact state, and a SHA-256 hash of the normalized binary mask.

## Rationale

OpenCV provides a CPU-compatible Windows baseline with a permissive upstream license and deterministic primitives. The headless package avoids unnecessary GUI dependencies. The MotionAnchor contract prevents concrete OpenCV types from entering domain or frontend interfaces.

## Constraints

- Source files and existing output files are never overwritten.
- This decision approves only deterministic primitives and synthetic fixture behavior.
- It does not approve OpenCV chroma keying as production-quality background removal for Cat Trap assets.
- Real hair, cape, sword, staff, glow, particle, and temporal-flicker evaluation remains mandatory.
- Advanced model-based mask engines remain separate benchmark candidates.

## Verification

Synthetic fixtures verify alpha preservation, thin non-green feature retention, edge-contact reporting, deterministic hashes, and non-overwrite behavior on Windows with Python 3.14.
