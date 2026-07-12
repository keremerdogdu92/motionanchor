# ADR-021: Cancellable Media Job Protocol

**Status:** Accepted for Phase 0

## Context

Synchronous frame extraction blocks the request/response path and cannot be cancelled safely. MotionAnchor needs background extraction with observable state before the first production UI is built.

## Decision

The worker adds these protocol operations:

- `job.submit.media.extract_frames` -> `job.accepted`
- `job.status` -> `job.status_result`
- `job.cancel` -> `job.cancel_result`

The in-memory `JobRunner` owns queued, running, completed, failed, and cancelled state. Job snapshots include bounded progress, status text, result/error payloads, timestamps, and cancellation state.

FFmpeg extraction uses `subprocess.Popen`. Cancellation terminates the child process, escalates to kill after a bounded wait, and removes only partial frame/manifest artifacts created by the operation. The output directory itself is retained.

## Consequences

This enables polling-based progress and cooperative cancellation without blocking worker stdin. Jobs are process-local and are not recovered after worker restart. Persistent job storage and Tauri event streaming remain later slices.
