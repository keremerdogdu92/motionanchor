# ADR-024: Native Media Path Dialogs

**Status:** Accepted for Phase 0

## Context

The first media workflow required users to type absolute Windows paths. That was sufficient for IPC verification but not for a usable desktop spike.

## Decision

Use the official Tauri 2 dialog plugin for native file and directory selection.

- `@tauri-apps/plugin-dialog` 2.7.1 is used by React.
- `tauri-plugin-dialog` 2 is initialized in the Rust builder.
- The main capability grants only `dialog:default` in addition to `core:default`.
- Video selection is single-file and filtered to common video extensions.
- Output selection is single-directory.
- Manual path editing remains available for fixture and development workflows.

## Security

The frontend receives only user-selected paths. No filesystem plugin, arbitrary directory enumeration, or shell permission is added. Rust and worker path validation remain authoritative before media operations begin.

## Consequences

The workflow no longer depends on manually typing paths. Selected output directories must still be empty because extraction does not overwrite existing artifacts.
