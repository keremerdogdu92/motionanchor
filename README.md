# MotionAnchor — Documentation and OpenCode Handoff v1.1

**Tagline:** Consistent Characters. Production-Ready Motion.

This pack contains the approved product, architecture, roadmap, open-source integration, and OpenCode implementation guidance for MotionAnchor.

## Documents

1. `01_Product_Requirements_Document.md` — Product vision, users, scope, workflows, requirements, quality, privacy, and acceptance criteria.
2. `02_System_Architecture_Document.md` — Tauri/React/Rust/Python architecture, security, adapters, data, motion analysis, providers, Unity export, testing, and ADRs.
3. `03_Development_Roadmap.md` — Phase 0 through commercial v1.0, provider research, open-source evaluation, quality gates, and 3D expansion.
4. `04_Open_Source_Module_Strategy.md` — Adopt/build/benchmark/exclude matrix, adapter boundaries, licensing policy, and shared fixture plan.
5. `05_OpenCode_Implementation_Handoff.md` — Repository placement, OpenCode workflow, first prompt, phase boundaries, and delivery rules.

## OpenCode Files

- `AGENTS.md` — Copy to the repository root.
- `.opencode/agents/review.md`
- `.opencode/agents/docs.md`
- `.opencode/commands/phase0-plan.md`
- `.opencode/commands/implement-slice.md`
- `.opencode/commands/review-slice.md`
- `.opencode/commands/update-docs.md`

OpenCode officially supports root `AGENTS.md` instructions and project commands under `.opencode/commands/`.

## Locked Decisions

- Product working name: MotionAnchor.
- Windows desktop first.
- Tauri 2 + React + TypeScript frontend.
- Rust trusted host and Python processing sidecar.
- Local-first media processing; online AI providers.
- Multi-provider abstraction from the start.
- Windows Credential Manager through a Rust credential abstraction.
- `.env` only as explicit development fallback.
- Human approval before final production export by default.
- Motion segmentation before keyframe selection.
- Adopt mature infrastructure behind adapters; build MotionAnchor-specific intelligence.
- Code and model licenses are separate release gates.
- 2D first, architecture extensible to 3D.
- Unity 2022.3 LTS first, engine-neutral export contract.
- Current use is single-user; architecture prepared for commercialization.

## Recommended Repository Layout

```text
motionanchor/
├── AGENTS.md
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
```

## Reading Order

`AGENTS.md` → PRD → SAD → Roadmap → Open-Source Strategy → OpenCode Handoff

## First Action

Start OpenCode in plan mode and use the first-session prompt from `05_OpenCode_Implementation_Handoff.md`. The first implementation scope is Phase 0 technical spikes only.
