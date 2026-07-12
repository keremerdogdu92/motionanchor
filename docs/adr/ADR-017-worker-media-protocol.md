# ADR-017: Worker Media Protocol Operations

**Status:** Accepted for Phase 0

## Context

The Python sidecar previously supported lifecycle messages only. MotionAnchor now needs a narrow, testable path from the Rust host to the existing FFmpeg adapter without exposing adapter-specific objects or writing diagnostics to stdout.

## Decision

Protocol 1.0 adds two synchronous worker operations:

- `media.probe` -> `media.probed`
- `media.extract_frames` -> `media.frames_extracted`

Requests preserve `message_id` and optional `job_id`. Payloads require explicit source and output paths. Responses contain JSON-safe metadata and artifact paths only. Existing FFmpeg timeout, output-size, source immutability, and non-overwrite protections remain authoritative.

## Error Contract

- invalid payload: `invalid_request`
- FFmpeg/media failure: `media_tool_error`
- unexpected implementation failure: redacted `internal`

Raw exceptions and secrets are not written to protocol stdout.

## Consequences

This is synchronous Phase 0 functionality. Progress, cancellation, queueing, and persistent job state remain a separate follow-up slice. Rust and frontend integration are intentionally not included in this ADR.
