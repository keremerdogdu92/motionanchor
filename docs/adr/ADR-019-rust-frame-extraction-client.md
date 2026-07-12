# ADR-019: Rust Frame Extraction Client

**Status:** Accepted for Phase 0

## Context

The Rust host can probe media, but the first real vertical slice also requires host-controlled frame extraction through the supervised Python worker.

## Decision

Add `extract_media_frames(source_path, output_path)` and expose it as the Tauri command `extract_frames`.

The Rust host:

- canonicalizes and validates the source file before starting the worker,
- requires an existing empty output directory or a new child path under an existing parent,
- sends `media.extract_frames` through Protocol 1.0,
- validates response type and message correlation,
- deserializes the response into `FrameExtractionReport`,
- allows 30 seconds for the synchronous Phase 0 extraction,
- performs graceful worker shutdown after success,
- kills the worker on failure.

The Python FFmpeg adapter remains responsible for exact timestamps, PNG output, manifest generation, and final non-overwrite checks.

## Consequences

The full Rust-to-Python extraction path is now proven against the real 240-frame Cat Trap dash fixture. FFmpeg discovery remains explicit through PATH or `MOTIONANCHOR_FFMPEG` / `MOTIONANCHOR_FFPROBE`. Progress and cancellation are deferred to the job-runner slice.
