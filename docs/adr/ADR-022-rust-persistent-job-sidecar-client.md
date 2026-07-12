# ADR-022: Rust Persistent Job Sidecar Client

**Status:** Accepted for Phase 0

## Context

Background job submission, polling, and cancellation must address the same worker process. Spawning a fresh worker for each Tauri command would lose the in-memory job registry and make cancellation impossible.

## Decision

The Rust host owns one lazily started `JobSidecarClient` behind Tauri managed state and a mutex. The client keeps the Python child process and stdout receiver alive across commands.

Typed commands are:

- `start_frame_extraction_job`
- `get_job_status`
- `cancel_job`

Each request uses a unique sequential message ID, validates the expected response type and ID, and deserializes into Rust-owned report structures. Source and output paths are validated before submission.

## Lifecycle

The worker starts on the first job command. The client attempts protocol shutdown when dropped and falls back to process termination if needed.

## Consequences

The frontend can now submit, poll, and cancel one worker-owned job through stable Tauri commands. Requests are serialized by the mutex. Multi-worker scheduling, persistence across application restart, event push, and recovery after worker crash remain separate slices.
