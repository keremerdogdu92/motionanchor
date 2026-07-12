# ADR-014 — FFmpeg media adapter

## Status
Accepted for Phase 0 spike validation.

## Decision
MotionAnchor uses FFmpeg and ffprobe as external executables behind a Python-owned adapter. The selected Windows development build is the BtbN LGPL 8.1 branch, version `8.1.2-20260630`.

## Boundaries
- Executable paths are resolved from explicit `MOTIONANCHOR_FFMPEG` and `MOTIONANCHOR_FFPROBE` overrides or PATH.
- The domain receives typed probe and frame timestamp records, not raw FFmpeg JSON.
- Exact timestamps are collected with ffprobe and paired by decode order with lossless PNG output.
- Extraction requires an empty destination and never overwrites existing artifacts.
- Tool output and execution time are bounded.

## Consequences
FFmpeg remains replaceable and is not linked into the application. Distribution licensing, notices, binary checksum, and final bundled codec configuration remain separate release gates.
