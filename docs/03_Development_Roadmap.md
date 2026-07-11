# MotionAnchor
## Development Roadmap

**Roadmap version:** 1.1  
**Status:** Approved roadmap updated for open-source evaluation and OpenCode implementation  
**Date:** 2026-07-11  
**Product:** MotionAnchor — Consistent Characters. Production-Ready Motion.  
**Planning model:** Solo developer with AI-assisted implementation  
**Sprint assumption:** 2-week sprints  
**Estimate status:** Planning range, not a delivery guarantee

---

## 1. Roadmap Strategy

The product will be built through vertical slices. Each milestone must produce a demonstrable workflow, not isolated infrastructure.

The critical path is:

```text
Secure Desktop Foundation
    ↓
Deterministic Video → Frame → Sheet Pipeline
    ↓
Motion Segmentation and Review
    ↓
AI Provider/Consistency Layer
    ↓
Unity Production Export
    ↓
Private Beta Hardening
    ↓
Commercial v1.0
```

3D and additional engines begin only after the 2D production pipeline is stable.

---

## 2. Release Definitions

### Prototype

Proves technical feasibility with developer-facing controls and fixture data.

### MVP / Alpha

Processes one real animation end to end with secure providers, human review, sprite output, and Unity import.

### Private Beta

Supports repeatable Cat Trap production usage and a small invited tester group.

### v1.0

Commercial-quality Windows release with installer, updater, diagnostics, documentation, and stable project format.

### v2.0

Expanded engine integrations, advanced automation, and initial 3D workflow support.

---

## 3. Phase 0 — Discovery and Technical Spikes

**Duration:** 1 sprint  
**Outcome:** Remove high-risk unknowns before core implementation.

### Work Items

- Confirm Tauri 2 + React starter structure.
- Build minimal Rust ↔ Python sidecar message exchange.
- Verify packaged Python sidecar startup on Windows.
- Test Windows Credential Manager create/read/delete using a Rust abstraction.
- Test `.env` development-only fallback behavior.
- Probe video with FFmpeg/PyAV and extract exact timestamps.
- Test one local background-removal approach on hair, cape, sword, staff, and glow.
- Create a Unity 2022.3 editor script that reads a small manifest and creates a sliced texture/Animation Clip.
- Complete code, model-weight, checkpoint, binary, and transitive-dependency license inventory.
- Build the Open Source & Model Evaluation Matrix.
- Benchmark FFmpeg, OpenCV, PySceneDetect, ruptures, rembg, SAM 2, Cutie/XMem, TAPIR/TAPNext, RAFT, DINOv2, aisuite/LiteLLM, Instructor, and keyring candidates only where relevant to the first release.
- Verify Windows installation, optional GPU paths, cold-start time, package size, and fallback behavior.
- Define component registry schema, checksum policy, `THIRD_PARTY_NOTICES`, and SBOM generation strategy.
- Confirm that CoTracker, non-commercial/research-only models, GPL/AGPL embedded components, and missing-license repositories are excluded from commercial builds.

### Deliverables

- spike repository/branch,
- architecture decision confirmations,
- sidecar protocol proof,
- credential-store proof,
- media extraction proof,
- Unity import proof,
- risk report,
- `04_Open_Source_Module_Strategy.md` decision update,
- first approved/experimental/excluded component registry,
- third-party notice and SBOM proof.

### Exit Criteria

- API key can be stored and retrieved without plaintext files.
- Tauri can launch and communicate with a packaged Python sidecar.
- An input video can produce timestamped PNG frames.
- A generated manifest can create a working Unity idle clip.
- No unresolved blocking license issue for the selected prototype dependencies or model weights.
- Every prototype engine runs behind a MotionAnchor adapter contract.
- At least one CPU-compatible deterministic fallback exists for the initial media and mask path.
- No excluded dependency is present in the distributable prototype.

---

## 4. Phase 1 — Desktop Foundation

**Duration:** 2 sprints  
**Target:** Internal version `0.1.0`

### Sprint 1 — Application Shell and Project Model

- Tauri 2 + React + TypeScript setup.
- Strict folder/module conventions.
- Tauri capability baseline.
- SQLite database and migrations.
- Project create/open/archive flow.
- Workspace permission and path validation.
- Structured logging with redaction.
- Host/sidecar protocol versioning.
- Background job skeleton with progress/cancel.

### Sprint 2 — Provider Settings and Secrets

- `CredentialStore` interface.
- Windows Credential Manager backend.
- Development `.env` adapter behind explicit flag.
- Provider configuration screens.
- API key add/update/delete with masked state.
- Test-connection action.
- Provider/model descriptor schema.
- Quota provenance model.
- Mock provider adapter for tests.

### Deliverables

- installable development build,
- local project database,
- secure provider configuration,
- sidecar job execution,
- no raw secret persistence.

### Exit Criteria

- Restarting the app retains projects and provider references.
- Secrets remain available through Credential Manager but cannot be read from project/SQLite/log files.
- Frontend has no arbitrary filesystem or shell access.
- Failed/crashed sidecar jobs are recoverable or clearly marked.

---

## 5. Phase 2 — Deterministic Media Pipeline

**Duration:** 2 sprints  
**Target:** Internal version `0.2.0`

### Sprint 3 — Import and Frame Extraction

- Media import wizard.
- Codec/FPS/resolution/variable-FPS inspection through the FFmpeg adapter.
- Time-range selection.
- Exact frame extraction and timestamps.
- Content hashes and cache keys.
- Thumbnail generation and virtualized frame browser.
- Duplicate/corrupt frame checks.

### Sprint 4 — Background, Crop, Alignment, Sheet

- Existing-alpha validation.
- OpenCV chroma-key mode.
- `IMaskEngine` contract.
- rembg baseline adapter.
- SAM 2 production-candidate spike with temporal-mask evaluation.
- Cutie/XMem retained as experimental benchmark candidates until Windows packaging is proven.
- Mask preview and confidence.
- Union-bounds safe crop.
- Configurable padding.
- Baseline and pivot alignment.
- Onion-skin preview.
- Deterministic sprite sheet builder.
- PNG frame and manifest export.

### Exit Criteria

- No approved hair, cape, sword, staff, or critical FX pixel is cut by auto-crop.
- All frames share identical canvas dimensions and pivot metadata.
- Re-running identical settings produces identical output hashes.
- Original source media is never overwritten.

---

## 6. Phase 3 — Motion Segmentation and Keyframe Review

**Duration:** 2 sprints  
**Target:** Internal version `0.3.0`

### Sprint 5 — Motion Signals and Segmentation

- Foreground centroid and silhouette metrics.
- Optical-flow motion-energy timeline.
- Blur and embedding-distance metrics.
- `IChangePointDetector` contract and ruptures baseline.
- Change-point detection over multi-signal feature vectors.
- OpenCV optical-flow baseline and adapter contract.
- TAPIR/TAPNext point-tracking spike for head, feet, sword tip, and staff tip anchors.
- RAFT evaluation only if the OpenCV baseline fails quality gates.
- Hold/event/loop candidate detection.
- Editable timeline segments.
- Segment split/merge/rename/lock.
- Signal visualizations.

### Sprint 6 — Candidate Generation and Manual Review

- Candidate generation per segment.
- Entry/exit/extrema/inflection/low-blur candidate rules.
- Candidate diversity filter.
- Side-by-side segment review.
- Pin/approve/reject/replace actions.
- Frame-count target validation.
- Loop preview at configurable FPS.
- Approval checkpoints.

### Exit Criteria

- The system never uses equal/random sampling as the production default.
- Every recommended final frame maps to a visible motion segment.
- The user can explain why a segment and candidate were proposed.
- A real idle video can be reduced to an approved 8-frame loop manually using the tool.

---

## 7. Phase 4 — Multi-Provider AI and Consistency Engine

**Duration:** 3 sprints  
**Target:** MVP/Alpha `0.5.0`

### Sprint 7 — Provider Adapter and Routing Core

- MotionAnchor-owned common provider interface.
- Benchmark direct SDK adapters, aisuite, and LiteLLM without allowing any upstream library to define domain schemas.
- First two real provider adapters.
- Pydantic schemas with Instructor/provider-native structured-output validation and repair.
- Retry, timeout, and fallback policies.
- Usage ledger and response-header capture.
- Task capability/criticality model.
- Provider/model routing policy.
- Selected-frame upload packaging.

### Sprint 8 — Provider Research and Benchmark Harness

- Research matrix using official provider documentation.
- Use `freellm.net` as discovery input, not source of truth.
- Build labeled candidate-review benchmark set.
- Score JSON reliability, human agreement, identity detection, weapon detection, latency, cost, and errors.
- Create model profiles and task thresholds.
- Build quota screen with provenance labels.
- Add dashboard links where quota APIs do not exist.

### Sprint 9 — Consistency and Drift MVP

- Character-reference comparison workflow.
- DINOv2 standard-model embedding spike; exclude specialized non-commercial/research-only variants.
- Coarse regions: full silhouette, head, torso, feet, sword, staff, cape.
- Scale/translation/shape anomaly metrics.
- Expected-motion profile for Idle.
- AI semantic review schema.
- Per-category consistency scoring.
- Drift overlays and findings.
- AI candidate ranking with reasons and rejections.
- Human confirmation and overrides.

### MVP/Alpha Exit Criteria

- At least two providers can be securely configured and tested.
- Critical review routing uses benchmark-qualified models.
- Candidate recommendations include structured reasons.
- The app can detect at least one intentionally injected face/weapon/scale defect in the test suite.
- Final approval remains manual.
- A real Cat Trap idle video can be processed end to end into approved frames.

---

## 8. Phase 5 — Unity Production Export

**Duration:** 2 sprints  
**Target:** Private Alpha `0.7.0`

### Sprint 10 — Engine-Neutral Export Contract

- Finalize animation manifest schema.
- Export adapter interface.
- Artifact transaction and rollback.
- Naming templates.
- PPU/pivot/FPS/loop profiles.
- Export validation and dry-run report.

### Sprint 11 — Unity 2022.3 Companion Package

- Unity package structure and installation guide.
- Manifest importer window.
- Texture import setup.
- Sprite rectangle/pivot creation.
- Animation Clip creation.
- Animator Controller create/update.
- Dry-run diff and conflict handling.
- Unity integration fixture tests.

### Exit Criteria

- Exported assets import into a clean Unity 2022.3 project.
- The idle clip loops with correct frame order, FPS, pivot, and PPU.
- Reimport updates owned generated assets without damaging unrelated assets.
- Existing target files require explicit replace/merge confirmation.

---

## 9. Phase 6 — Cat Trap Production Validation

**Duration:** 2 sprints  
**Target:** Private Beta `0.9.0`

### Sprint 12 — Real Animation Set

Process and validate at least:

- Idle,
- Walk,
- Dash,
- Sword Attack,
- Spell Cast,
- Hurt.

For each animation:

- record accepted/rejected AI suggestions,
- tune expected-motion profiles,
- tune crop/edge thresholds,
- tune provider routing,
- confirm Unity import.

### Sprint 13 — Workflow and Quality Hardening

- Batch job queue.
- Cached analysis reuse.
- Project backup/restore.
- Diagnostic bundle export with redaction.
- UX performance work.
- Crash/recovery tests.
- Golden-image regression suite.
- Beta documentation.

### Exit Criteria

- Six Cat Trap animations complete the same repeatable pipeline.
- No manual external frame extraction/collage step is required.
- Known errors are detected before Unity export in the regression suite.
- Project can be moved to another machine without moving credentials.

---

## 10. Phase 7 — Commercial v1.0

**Duration:** 3–4 sprints  
**Target:** Stable `1.0.0`

### Scope

- polished onboarding,
- installer/uninstaller,
- signed update pipeline,
- Windows code signing,
- production crash handling,
- privacy/data-upload controls,
- license/third-party notices,
- SBOM-compatible component inventory,
- signed component/model checksum manifest,
- automated commercial-build exclusion test for prohibited component statuses,
- provider documentation and warnings,
- app version/project schema migrations,
- stable Unity package release,
- performance tuning,
- accessibility and keyboard workflow,
- external beta feedback fixes,
- commercial-ready help documentation.

### Architecture Preparation, Not Necessarily Activated

- `LicenseService` interface,
- entitlement feature flags,
- release channels,
- opt-in telemetry interface,
- future account/cloud boundaries.

### v1.0 Exit Criteria

- stable project format and migration tests,
- signed installer and update artifacts,
- no critical secret leakage finding,
- documented supported Windows versions,
- repeatable release pipeline,
- successful external tester projects,
- Unity importer compatibility matrix published,
- acceptable crash-free and export-success metrics,
- every bundled dependency/model is approved in the component registry,
- commercial artifacts contain no excluded, pending-review, non-commercial, research-only, or missing-license component.

---

## 11. v1.x Roadmap

### v1.1 — Productivity

- reusable animation presets,
- project templates,
- batch processing,
- advanced manual mask brush,
- more provider adapters,
- local model option,
- provider benchmark auto-refresh.

### v1.2 — Additional 2D Integrations

- Godot exporter,
- Unreal Paper2D exporter,
- Spine/Live2D preparation manifests,
- engine adapter SDK documentation.

### v1.3 — Collaboration Foundations

- review comments,
- export approval records,
- shareable redacted review packages,
- optional cloud sync design validation.

---

## 12. v2.0 Roadmap — 3D and Advanced Motion

### Candidate Scope

- 3D reference-video ingestion,
- pose/keypoint extraction,
- skeleton mapping,
- motion segmentation for rigged characters,
- retargeting preparation,
- rig consistency checks,
- FBX/glTF-oriented export adapters,
- Blender/Unity 3D companion tooling,
- local GPU inference profiles.

The 3D module must reuse:

- project/job infrastructure,
- provider layer,
- credential storage,
- benchmark framework,
- human approval workflow,
- engine-neutral exporter contracts.

It must not force 3D concepts into the 2D frame model; a new media/asset domain interface should be introduced.

---

## 13. Provider Research Workstream

This is a continuing workstream, not a one-time list.

### Required Provider Matrix Fields

- provider,
- model ID/version,
- image/video input support,
- maximum image count/size,
- reasoning quality,
- structured-output reliability,
- free-tier availability,
- official rate limits,
- quota API/header availability,
- commercial-use terms,
- data retention/training policy,
- OpenAI-compatible API support,
- latency and reliability,
- internal benchmark scores,
- last verified date.

### Research Order

1. Gemini
2. OpenRouter
3. Groq
4. Cerebras
5. NVIDIA NIM
6. Mistral
7. Cloudflare Workers AI
8. other providers discovered through official sources and directories such as `freellm.net`

Providers without image input may still handle lightweight text/JSON/report tasks.

### Routing Policy Development

- Free models first for non-critical tasks when qualified.
- Best benchmarked vision/reasoning model for critical candidate/consistency review.
- Optional ensemble for main-character final approval.
- Paid fallback only within user-configured budget.
- Never silently switch to a provider with weaker privacy/commercial terms.

---


## 14. Open-Source and Model Evaluation Workstream

This workstream runs alongside implementation and is a release gate, not a one-time research task.

### Evaluation Matrix Fields

- capability and adapter interface,
- upstream repository and official documentation,
- exact version/tag/commit,
- source-code license,
- model/checkpoint license,
- transitive dependencies,
- commercial-use and redistribution decision,
- Windows installation and packaging status,
- CPU/GPU requirements,
- RAM/VRAM and disk footprint,
- cold-start and throughput,
- quality on shared Cat Trap fixtures,
- temporal stability,
- deterministic/reproducibility behavior,
- maintenance activity and replacement risk,
- fallback adapter,
- final status: approved, experimental, external tool, excluded, rejected, or pending review.

### First Evaluation Groups

1. Media: FFmpeg.
2. Deterministic CV: OpenCV and Pillow.
3. Scene transitions: PySceneDetect.
4. Change points: ruptures.
5. Masks: rembg, SAM 2, Cutie, XMem.
6. Flow/tracking: OpenCV, TAPIR/TAPNext, RAFT.
7. Embeddings: DINOv2 standard models.
8. AI transport/validation: direct adapters, aisuite, LiteLLM, Instructor/Pydantic.
9. Secrets: keyring-rs and Windows-native credential store.

### Commercial Exclusion Gate

The commercial build fails if it includes:

- GPL/AGPL components without an explicitly approved distribution plan,
- non-commercial or research-only code/weights,
- missing/unclear licenses,
- unverified model checkpoints,
- components absent from the registry,
- binaries or models whose checksum differs from the approved lock.

### Update Policy

Upgrades require license re-verification, changelog review, adapter contract tests, golden-fixture regression, performance comparison, and component-lock update. Automatic dependency upgrades are not allowed for production-critical CV/ML engines.

---

## 15. Testing and Quality Gates by Release

| Release | Mandatory tests |
|---|---|
| 0.1 | IPC, credential store, migrations, path boundaries |
| 0.2 | Extraction, mask, crop, sheet golden tests |
| 0.3 | Motion signal and segment fixture tests |
| 0.5 | Provider mocks, benchmark suite, structured AI schemas, drift fixtures |
| 0.7 | Unity clean-project integration tests |
| 0.9 | Real Cat Trap animation regression set |
| 1.0 | Installer/update/signing/security/recovery matrix |

No milestone is complete if its acceptance tests are deferred.

---

## 16. Prioritization Rules

When scope pressure occurs, preserve in this order:

1. secret security,
2. source-file safety,
3. reproducibility,
4. motion segmentation quality,
5. character consistency review,
6. human approval,
7. Unity export correctness,
8. UX polish,
9. additional providers,
10. additional engines/3D.

Do not trade away the first seven items to add breadth.

---

## 17. Immediate Next Actions

1. Create the MotionAnchor repository and copy this documentation pack into `docs/`.
2. Add the supplied root `AGENTS.md` and OpenCode project commands.
3. Use OpenCode’s plan agent to produce a Phase 0 execution plan; do not implement later phases.
4. Record ADR-001 through ADR-011 as repository ADR files.
5. Create the component registry/evaluation matrix before adding CV/ML dependencies.
6. Execute credential-store, Tauri↔Python sidecar, FFmpeg extraction, mask-engine, and Unity-manifest spikes.
7. Select exact Rust/Python/npm dependencies only after source, license, model-weight, and Windows packaging review.
8. Define protocol, component-lock, job, and export-manifest JSON schemas.
9. Build the first end-to-end fixture using the current Cat Trap idle video and character references.
10. Begin provider and keyframe-review benchmark datasets with manually approved ground truth.
11. Require a documentation update whenever a spike changes an approved architectural decision.

---

## 18. Planning Summary

| Milestone | Approximate cumulative range |
|---|---|
| Technical spikes complete | 2 weeks |
| Secure desktop foundation | 6 weeks |
| Deterministic media pipeline | 10 weeks |
| Motion segmentation review | 14 weeks |
| MVP/Alpha with AI consistency | 20 weeks |
| Unity private alpha | 24 weeks |
| Cat Trap private beta | 28 weeks |
| Commercial v1.0 | 34–36 weeks |

These ranges assume solo implementation and production-grade testing. They can shorten with reduced scope or parallel development, but the acceptance gates should remain unchanged.
