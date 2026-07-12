# ADR-018: Rust Media Probe Client

**Status:** Accepted for Phase 0

## Context

The Python worker exposes `media.probe`, but the trusted Rust host must own process supervision, path validation, timeout behavior, typed deserialization, and the Tauri command boundary.

## Decision

The Rust sidecar module now provides `probe_media(source_path)` and a typed `MediaProbeReport`. The host canonicalizes the source path, requires an existing file, launches the development worker, validates the startup handshake, sends `media.probe`, validates response type and correlation ID, deserializes the payload, and performs graceful shutdown.

A Tauri command named `probe_media` exposes only the typed report or a redacted string error. The implementation remains one-shot and synchronous during Phase 0.

## Verification

The integration test probes the real Cat Trap dash fixture and confirms H.264, 1280x720, 240 frames, and approximately ten seconds duration. A missing-path test confirms rejection before the worker starts.

## Consequences

The Rust host now has a real media operation beyond ping/pong. Persistent workers, unique request-ID generation, extraction progress, cancellation, and concurrent jobs remain follow-up work.
