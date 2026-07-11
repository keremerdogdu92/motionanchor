# MotionAnchor
## OpenCode Implementation Handoff

**Document version:** 1.0  
**Status:** Ready to place in the repository before implementation  
**Date:** 2026-07-11

---

## 1. Purpose

This document defines how OpenCode should consume the MotionAnchor documentation and execute implementation work without expanding scope, guessing architecture, or bypassing quality/security gates.

OpenCode supports repository-level instructions through a root `AGENTS.md`, project commands under `.opencode/commands/`, specialized agents, and project references. The supplied pack uses a concise `AGENTS.md` and focused commands so the primary context does not become bloated.

---

## 2. Repository Placement

Place the files as follows:

```text
motionanchor/
├── AGENTS.md
├── README.md
├── docs/
│   ├── 01_Product_Requirements_Document.md
│   ├── 02_System_Architecture_Document.md
│   ├── 03_Development_Roadmap.md
│   ├── 04_Open_Source_Module_Strategy.md
│   └── 05_OpenCode_Implementation_Handoff.md
└── .opencode/
    ├── agents/
    │   ├── review.md
    │   └── docs.md
    └── commands/
        ├── phase0-plan.md
        ├── implement-slice.md
        ├── review-slice.md
        └── update-docs.md
```

Do not ask OpenCode to generate a new `AGENTS.md` with `/init` after copying the supplied file unless the generated result is reviewed and merged manually; otherwise project-specific constraints may be overwritten or diluted.

---

## 3. Documentation Reading Order

Before planning or editing:

1. `AGENTS.md`
2. `docs/01_Product_Requirements_Document.md`
3. `docs/02_System_Architecture_Document.md`
4. `docs/03_Development_Roadmap.md`
5. `docs/04_Open_Source_Module_Strategy.md`
6. The source files relevant to the requested change

The PRD defines **what and why**. The SAD defines **boundaries and implementation constraints**. The roadmap defines **when and acceptance gates**. The module strategy defines **adopt/build/exclude decisions**.

---

## 4. Required Delivery Workflow

### Step 1 — Plan Mode

Use the OpenCode plan agent first for every phase or non-trivial slice.

The plan must include:

- files to create or modify,
- source files inspected,
- architectural boundaries involved,
- dependencies proposed and their review status,
- tests and acceptance criteria,
- security and license impact,
- documentation impact,
- rollback/recovery considerations.

No implementation begins until the plan matches the current phase and approved documents.

### Step 2 — Source Inspection

Before changing code, OpenCode must read the current relevant files. It must not infer file contents from names, earlier prompts, or architecture documents.

For database/schema changes, it must read the current schema and migrations first. For dependency changes, it must inspect the current manifest/lock files first.

### Step 3 — Narrow Implementation Slice

Implement one acceptance-testable slice. Avoid broad scaffolding that claims future behavior without tests.

Examples of acceptable Phase 0 slices:

- Tauri host starts and supervises a versioned Python sidecar.
- Windows credential store create/read/delete spike.
- FFmpeg adapter probes and extracts timestamped frames.
- One `IMaskEngine` baseline with shared fixture output.
- Unity package reads a minimal manifest and creates an idle clip.

### Step 4 — Verification

Run relevant formatters, type checks, unit tests, integration tests, and fixture comparisons. Report exact commands and results. Do not declare success when tests were skipped or unavailable.

### Step 5 — Review

Use the review workflow or a review agent to inspect:

- correctness,
- security boundaries,
- secret/log leakage,
- architecture violations,
- dependency and model-license state,
- Windows behavior,
- error handling,
- tests,
- documentation consistency.

### Step 6 — Documentation and Decision Update

Update documentation in the same change when implementation alters an approved decision, interface, schema, dependency status, or roadmap gate. New architecture decisions require an ADR.

---

## 5. Current Implementation Boundary

The repository begins at **Phase 0 — Discovery and Technical Spikes**.

OpenCode must not implement:

- the complete application,
- all providers,
- production licensing/accounts,
- 3D workflows,
- Godot/Unreal exporters,
- automatic final approval,
- full consistency scoring,
- UI polish beyond what a spike requires.

It should produce evidence that the proposed architecture works and resolve high-risk unknowns.

---

## 6. Dependency Rules for OpenCode

Before adding a dependency or model, OpenCode must:

1. identify the official upstream source,
2. inspect source and model licenses separately,
3. check commercial and redistribution suitability,
4. check Windows support and packaging,
5. classify it in the component registry,
6. place it behind the approved adapter interface,
7. pin the version/commit,
8. add tests and notices as applicable,
9. avoid copying code from repositories without a compatible explicit license.

OpenCode may use its read-only dependency-research/scout capability to inspect upstream repositories, but should not modify the workspace during that research step.

---

## 7. Code Standards

- English file summaries, comments, logs, errors, and documentation.
- Full files ready to commit; no unexplained partial snippets.
- Strict TypeScript, typed Rust errors, typed Python with validation at process boundaries.
- Defensive path handling and no arbitrary frontend filesystem/shell access.
- API keys only through the credential abstraction; never command arguments, project files, SQLite, `.env` in production, or logs.
- External engines only inside adapters.
- Reversible operations and immutable source media.
- Mobile-aware/responsive UI even though the first application is Windows desktop.
- Tests accompany every production behavior.

---

## 8. First OpenCode Session Prompt

Use this after placing the files in a new repository:

```text
Read AGENTS.md and all five documents under docs/ in the specified order.
We are starting only Phase 0 of MotionAnchor.
Do not write implementation code yet.
Inspect the current repository and produce a precise Phase 0 execution plan that:
1. identifies the smallest technical spikes,
2. lists exact files and package manifests that would be created,
3. defines acceptance tests for each spike,
4. identifies all dependencies and their current registry status,
5. separates parallel-safe work from sequential work,
6. records unresolved decisions without guessing,
7. proposes the order of implementation.
Return the plan for approval.
```

---

## 9. Recommended Phase 0 Order

1. Repository/toolchain baseline and test commands.
2. Tauri ↔ Python sidecar protocol spike.
3. Windows Credential Manager/keyring spike.
4. FFmpeg media adapter spike.
5. OpenCV deterministic CV fixture baseline.
6. `IMaskEngine` benchmark harness and first mask candidates.
7. Motion-signal/change-point fixture spike.
8. Unity manifest/import spike.
9. Component registry, notices, and SBOM proof.
10. Architecture review and Phase 0 decision update.

---

## 10. OpenCode Configuration Notes

- Keep `AGENTS.md` concise and committed at repository root.
- Keep detailed requirements in `docs/`; reference them rather than duplicating them in every agent prompt.
- Use `.opencode/commands/` for repeatable workflows and `.opencode/agents/` for the supplied read-only review and documentation subagents.
- Provider/model selection for OpenCode itself is a developer environment choice and is not encoded in the repository pack.
- Use explicit permissions; do not grant deployment, external service mutation, or destructive shell access unless a task requires it and the user approves.
- Project references in `opencode.jsonc` can be added later if shared docs or upstream source checkouts live outside the repository.

---

## 11. Completion Definition

The handoff is successful when OpenCode can:

- state the current phase and non-goals,
- identify which modules are adopted versus built,
- refuse prohibited/unreviewed dependencies,
- plan a narrow slice before editing,
- inspect current files before changes,
- run and report tests,
- update documentation/ADRs with decisions,
- avoid leaking secrets or bypassing the adapter architecture.

---

## 12. OpenCode Sources

- Rules and `AGENTS.md`: https://opencode.ai/docs/rules/
- Agents: https://opencode.ai/docs/agents/
- Commands: https://opencode.ai/docs/commands/
- Configuration: https://opencode.ai/docs/config/
- Project references: https://opencode.ai/docs/references/
- Permissions/tools: https://opencode.ai/docs/permissions/ and https://opencode.ai/docs/tools/
