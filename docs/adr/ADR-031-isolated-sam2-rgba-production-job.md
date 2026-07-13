# ADR-031: Isolated SAM 2 RGBA Production Job

**Status:** Accepted

## Context

The production worker runs on the lightweight application Python environment, while SAM 2.1 Small requires a pinned Python 3.12, PyTorch, CUDA, and model checkpoint stack. Importing that stack into the main worker would increase startup risk, packaging size, and dependency coupling.

## Decision

SAM 2 RGBA processing runs as a supervised child process launched by the worker job service. Requests carry an extracted-frame directory, an empty output path, a versioned prompt JSON file, the fixed `small` model profile, feather radius, and defringe flag.

The parent worker validates paths and settings, drains child stderr into a bounded buffer, streams NDJSON progress, supports cooperative cancellation with terminate/kill escalation, and publishes artifacts only after successful completion. Child output is created under a temporary sibling directory and atomically moved to the requested destination. Returned mask, RGBA, report, and output paths are rebased after publication.

`MOTIONANCHOR_SAM2_PYTHON` selects the pinned runtime. `MOTIONANCHOR_SAM2_RUNNER` is an explicit test seam for a deterministic fake child process and is not used by the normal application path.

## Consequences

- The main worker remains free of direct PyTorch and SAM 2 imports.
- Failed or cancelled jobs do not publish partial output directories.
- Long-running GPU work remains observable through the existing job status protocol.
- A separate clean-machine packaging and GPU capability gate is still required.
- Prompt editing is currently file-based; an interactive box/click editor remains future work.
