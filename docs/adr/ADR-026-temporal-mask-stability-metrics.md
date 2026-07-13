# ADR-026: Temporal Mask Stability Metrics

## Status

Accepted for Phase 0 diagnostics.

## Decision

Add MotionAnchor-owned temporal mask diagnostics for ordered binary mask sequences.

For each adjacent pair, the benchmark records:

- centroid shift in pixels;
- centroid-aligned intersection-over-union;
- foreground-area change ratio;
- boundary turnover ratio.

Sequence-level reports include mean and worst-case values plus per-pair results.

## Rationale

Per-frame IoU against ground truth does not expose temporal instability by itself. Centroid alignment separates expected character translation from silhouette changes, while area and boundary turnover expose likely mask flicker.

## Constraints

These metrics diagnose instability but do not determine production quality alone. Real Cat Trap approval still requires manually approved masks and visual review of hair, cape, weapons, glow, particles, and fast-motion frames.
