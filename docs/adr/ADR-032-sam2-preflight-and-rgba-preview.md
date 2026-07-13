# ADR-032: SAM 2 Preflight and Bounded RGBA Preview

**Status:** Accepted

## Context

The SAM 2 job previously failed only after submission when Python, CUDA, or the checkpoint was unavailable. Completed RGBA sequences were exposed as paths and JSON reports but not visually reviewable in the desktop application.

## Decision

Add a synchronous `segmentation.sam2_preflight` worker request. The isolated Python environment reports Torch availability, CUDA state, GPU name, VRAM, checkpoint existence, and the pinned checkpoint SHA-256. Readiness requires CUDA and the verified SAM 2.1 Small checkpoint.

Add a Rust-owned RGBA preview loader. It reads only direct `rgba/frame_*.png` children, rejects path escape, samples at most twelve frames, and enforces the existing 12 MiB aggregate response limit.

The React UI exposes an explicit runtime check and renders representative transparent frames over a checkerboard background.

## Consequences

- Missing GPU/runtime components are detected before a long job starts.
- Checkpoint corruption is reported deterministically.
- RGBA edge quality is visible without opening external tools.
- Preflight does not load the full SAM 2 model and is not a substitute for inference validation.
