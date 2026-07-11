# MotionAnchor Agent Instructions

## Source of Truth

Read before planning or editing:

1. `docs/01_Product_Requirements_Document.md`
2. `docs/02_System_Architecture_Document.md`
3. `docs/03_Development_Roadmap.md`
4. `docs/04_Open_Source_Module_Strategy.md`
5. `docs/05_OpenCode_Implementation_Handoff.md`

Current phase: **Phase 0 — Discovery and Technical Spikes**. Do not implement later phases unless the roadmap and user explicitly advance the phase.

## Mandatory Workflow

- Plan before non-trivial edits.
- Read current relevant source, config, schema, manifest, and lock files before changing them.
- Do not guess missing requirements or file contents; ask a focused question when a decision is genuinely unresolved.
- Deliver complete files ready to commit, not partial diffs or placeholder implementations.
- Run relevant formatting, type checks, tests, and fixture validation; report failures honestly.
- Update docs and ADRs whenever a decision, interface, dependency status, schema, or roadmap gate changes.

## Architecture Rules

- Windows desktop first: Tauri 2 + React/TypeScript + Rust host + Python sidecar.
- Media is local-first. Upload only explicitly approved review bundles.
- Frontend never receives raw provider secrets or arbitrary filesystem/shell authority.
- Production API keys use the credential-store abstraction; never store them in project files, SQLite, logs, command arguments, or plaintext `.env`.
- External engines are accessed only through MotionAnchor-owned adapters.
- Persist stable domain identifiers, never concrete third-party classes or payloads.
- Source media is immutable; derived operations are reversible and reproducible.
- Human approval is required before production export by default.
- Motion segmentation precedes final keyframe selection. Equal/random sampling is not a production strategy.
- Unity is the first export adapter; internal contracts remain engine-neutral.

## Dependency and License Rules

- Consult `docs/04_Open_Source_Module_Strategy.md` before adding a dependency/model.
- Verify official upstream source, source license, model/checkpoint license, transitive dependencies, commercial use, redistribution, Windows packaging, and checksum.
- Prefer MIT, Apache-2.0, BSD-2-Clause, and BSD-3-Clause.
- Do not add GPL/AGPL, non-commercial, research-only, missing-license, or unclear-license components to the commercial build without explicit approval.
- Do not copy code/assets from unlicensed repositories.
- Pin production-critical CV/ML dependencies and record them in the component registry.

## File Standards

- Put the file path at the top of new code files where the language permits a header comment.
- Add an English summary describing the file and integrations.
- English-only comments, logs, errors, summaries, and code documentation.
- Keep modules explicit, defensive, reusable, testable, and security-conscious.
- Use strict TypeScript, typed Rust errors, Python type hints, and validated IPC/provider schemas.

## Quality Gates

A slice is incomplete without:

- acceptance criteria mapped to tests,
- error and cancellation behavior,
- secret/log redaction review,
- path-boundary review,
- adapter contract tests when external engines are involved,
- documentation impact review,
- no unresolved claim of success.
