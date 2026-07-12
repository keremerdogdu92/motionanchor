# ADR-020: Worker Job Runner Foundation

**Status:** Accepted for Phase 0 foundation

## Context

Media extraction and later CV/AI operations can outlive a synchronous UI request. The worker needs a small owned job abstraction before protocol progress and cancellation are exposed.

## Decision

Add an in-memory, thread-safe `JobRunner` with explicit states:

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`

Jobs expose bounded progress, an optional status message, structured failure data, a result payload, timestamps, and a cooperative cancellation flag. Terminal jobs cannot be cancelled again, and unknown job identifiers fail explicitly.

## Current Boundary

This slice establishes worker-owned state and cancellation semantics only. It is not yet wired to NDJSON or Tauri commands. Active FFmpeg subprocess termination and artifact rollback remain required before media extraction cancellation is exposed to the UI.

## Consequences

The next slice can add `job.submit`, `job.status`, and `job.cancel` protocol operations without allowing FFmpeg, CV, or provider libraries to define the job model.
