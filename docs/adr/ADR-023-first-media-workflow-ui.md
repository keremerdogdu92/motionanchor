# ADR-023: First Media Workflow UI

**Status:** Accepted for Phase 0

## Context

The backend can probe media and run cancellable frame-extraction jobs, but the React shell still contains only the starter greeting example.

## Decision

Replace the starter screen with a narrow developer-facing workflow that:

- accepts explicit source and output paths,
- invokes `probe_media`,
- submits `start_frame_extraction_job`,
- polls `get_job_status` every 350 ms while active,
- invokes `cancel_job`,
- renders typed metadata, progress, terminal state, errors, and result artifacts.

The UI does not add unrestricted filesystem access or a file-picker plugin in this slice. Paths remain explicit text inputs and backend validation remains authoritative.

## Consequences

MotionAnchor now has its first end-to-end interactive vertical slice. Native file/folder pickers, persisted project paths, thumbnail browsing, and automated UI tests remain follow-up work.
