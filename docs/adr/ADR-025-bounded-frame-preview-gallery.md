# ADR-025: Bounded Frame Preview Gallery

**Status:** Accepted for Phase 0

## Context

Frame extraction produced `frames.json` and PNG artifacts, but the desktop workflow exposed only raw paths and JSON. A representative visual review is required before mask and keyframe work.

## Decision

Add a Rust-owned preview loader and a React gallery.

- Rust reads `frames.json` from the selected extraction directory.
- Up to 12 evenly spaced frames may be requested; the UI requests 8.
- Manifest filenames must be direct `frame_*.png` children of the extraction directory.
- Canonical path checks prevent traversal outside the selected directory.
- Preview payloads use bounded PNG data URLs rather than adding broad filesystem access.
- Total preview bytes are capped at 12 MiB.

## Consequences

Completed extraction jobs automatically show representative frames with source index and exact timestamp. This remains a lightweight Phase 0 review surface, not the Phase 2 virtualized frame browser or thumbnail cache.
