# ADR-016: Shared Mask Benchmark Harness

## Status

Accepted for Phase 0 fixture evaluation.

## Decision

Mask-engine candidates are compared against manually approved binary masks using MotionAnchor-owned metrics: intersection-over-union, precision, recall, and one-pixel-tolerant boundary F1.

Fixture metadata lives under `fixtures/masks/` and records source, ground-truth mask, feature tags, provenance, and manual approval state.

## Consequences

- OpenCV, rembg, SAM 2, Cutie, and XMem can be evaluated through the same result contract.
- Synthetic tests validate metric behavior, but do not establish Cat Trap production quality.
- Real project-owned fixtures and manually approved masks remain required before any advanced mask engine is approved.
