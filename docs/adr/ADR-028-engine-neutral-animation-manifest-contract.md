# ADR-028: Engine-Neutral Animation Manifest Contract

## Status

Accepted as the first half of the Phase 0 Unity import spike.

## Context

Unity import must consume a stable MotionAnchor-owned contract rather than Python classes, Unity serialization, or externally generated `.meta` files. The development machine does not currently have Unity Editor installed, so actual asset creation cannot yet be executed.

## Decision

Introduce schema version `1.0` with strict Python validation for animation metadata, pivot, pixels-per-unit, sprite-sheet geometry, ordered frames, safe relative paths, durations, and SHA-256 provenance.

Unknown fields, absolute paths, parent traversal, non-contiguous frame indices, invalid grid capacity, malformed hashes, and unsupported pivot data are rejected.

A repository fixture under `fixtures/unity/` is validated by automated tests.

## Consequences

Export adapters and the future Unity package can depend on a stable engine-neutral representation. The Unity Editor importer, texture slicing, Animation Clip generation, and clean-project integration test remain open and must not be marked complete until run in Unity 2022.3 LTS.