# ADR-029: Isolated SAM 2.1 GPU Evaluation Environment

## Status

Accepted for Phase 0 evaluation only.

## Decision

Evaluate SAM 2.1 behind the MotionAnchor mask adapter boundary in a separate Python 3.12 virtual environment. Pin PyTorch 2.7.0 with CUDA 12.8 wheels, TorchVision 0.22.0, and SAM 2 source commit `2b90b9f5ceec907a1c18123530e92e794ad901a4`.

The environment is excluded from Git and is not included in the packaged production worker. The first benchmark uses the SAM 2.1 Hiera Tiny checkpoint on the 240-frame Cat Trap dash fixture.

## Rationale

The current standard worker uses Python 3.14 and deterministic OpenCV-only dependencies. Isolating the GPU experiment prevents a large PyTorch/model dependency surface from entering the production binary before quality, Windows packaging, VRAM usage, startup cost, and licensing are verified.

The development machine has an NVIDIA GeForce RTX 3060 Ti with 8 GB VRAM. The smallest official SAM 2.1 checkpoint is therefore the lowest-risk initial candidate.

## Constraints

SAM 2 officially recommends WSL for Windows installations. Native Windows execution remains experimental until the full video propagation benchmark succeeds. The checkpoint checksum, download provenance, benchmark metrics, and packaging result must be recorded before the adapter can move beyond experimental status.
