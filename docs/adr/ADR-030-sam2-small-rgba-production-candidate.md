# ADR-030: SAM 2.1 Small RGBA Production Candidate

**Status:** Accepted as an experimental production candidate
**Date:** 2026-07-13

## Context

The temporal-median baseline failed on the 240-frame Cat Trap dash fixture. SAM 2.1 Tiny improved the silhouette but retained unacceptable detail loss during the fastest motion frames.

## Decision

Use pinned SAM 2.1 Hiera Small for the current GPU quality candidate, behind MotionAnchor-owned adapters and an isolated Python 3.12 evaluation environment.

The selected checkpoint is `sam2.1_hiera_small.pt` with SHA-256 `6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38`.

Binary masks are post-processed by MotionAnchor using enclosed-hole filling, inward-only alpha feathering, and nearest-opaque-color defringing. Original frames are never modified.

## Evidence

- Mean centroid-aligned IoU: `0.944644`
- Minimum centroid-aligned IoU: `0.705224`
- Throughput on RTX 3060 Ti: `5.947 FPS`
- 240 RGBA frames generated with deterministic `1.5 px` inward feathering
- Hair, cape, sword, staff, and blue flame survived representative visual review
- Worker test suite: `96` passing tests

## Consequences

SAM 2.1 Small is not yet approved for bundled commercial distribution. Native Windows packaging, checkpoint redistribution, clean-machine installation, manual ground-truth scoring, and additional Cat Trap animations remain release gates.

Ground shadows, speed dust, and detached particles are intentionally excluded from the primary character mask and should be evaluated as separate FX layers.
