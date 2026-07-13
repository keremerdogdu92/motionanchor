# MotionAnchor
## Product Requirements Document (PRD)

**Document version:** 1.1  
**Status:** Approved baseline updated for open-source integration and OpenCode implementation handoff  
**Date:** 2026-07-11  
**Initial platform:** Windows desktop  
**Initial engine integration:** Unity 2022.3 LTS  
**Product name:** MotionAnchor  
**Tagline:** Consistent Characters. Production-Ready Motion.  
**Trademark status:** Working commercial name pending formal clearance before public launch

---

## 1. Executive Summary

MotionAnchor is a local-first desktop application that converts AI-generated motion reference videos into consistent, reviewable, production-ready game animation assets.

The tool is not intended to perform a naive “video to sprite sheet” conversion. Its primary value is a controlled production pipeline that:

1. separates motion into meaningful phases,
2. proposes frame candidates from each phase,
3. evaluates character, weapon, costume, and silhouette consistency,
4. identifies unwanted visual drift,
5. preserves transparent edges and full character bounds,
6. requires human approval before final export,
7. exports deterministic assets into Unity,
8. records enough metadata to reproduce every result.

The first user is a single developer producing the main character animations for **Cat Trap**. The architecture must nevertheless support future commercialization, licensing, additional users, other game engines, and future 3D-rig analysis.

---

## 2. Product Vision

> Build a professional AI-assisted animation production pipeline that transforms AI-generated motion references into consistent, production-ready game animation assets.

The product should reduce repetitive technical work without hiding important production decisions. Deterministic image-processing modules handle extraction, masking, alignment, measurement, and export. Vision/reasoning models evaluate semantic quality and consistency. The user remains the final approver.

---

## 3. Problem Statement

AI video tools can produce useful motion references, but the resulting videos are not directly suitable as reusable game assets. Common problems include:

- face and identity drift,
- weapon length and design changes,
- inconsistent costume details,
- body parts changing scale,
- feet sliding on the ground,
- unstable canvas position,
- malformed hands or accessories,
- incomplete transparency masks,
- hair, cape, staff, sword, or particles being cropped,
- loops that visibly jump,
- frame selection that ignores motion phases,
- inconsistent pivots and sprite dimensions,
- manual Unity import and animation setup.

For a main character with many animations and more than one hundred skills, these errors compound. A repeatable, auditable production pipeline is therefore more valuable than a one-off frame extractor.

---

## 4. Target Users

### 4.1 Primary User — Solo/Small-Team 2D Game Developer

Needs to:

- import AI-generated animation videos,
- preserve a fixed main-character identity,
- identify usable movement phases and key poses,
- create transparent and aligned frame sequences,
- export directly to Unity,
- reuse motion with different weapons and effects.

### 4.2 Secondary User — Technical Artist / Animator

Needs to:

- inspect motion graphs and visual drift,
- compare frames against character references,
- approve or replace keyframes,
- control crop, padding, baseline, and pivot,
- review AI findings rather than trust automatic output blindly.

### 4.3 Future User — Commercial Customer

May need:

- multiple projects,
- licensing and activation,
- additional engine exporters,
- team review workflows,
- reusable provider presets,
- batch processing,
- usage reporting,
- 3D rig and motion-analysis modules.

---

## 5. Product Principles

1. **Character preservation over speed.** A slower but consistent result is preferable to a fast unusable sprite sheet.
2. **Motion phases before frame selection.** Final frames must represent animation structure, not equal intervals or random samples.
3. **Human approval before production export.** Automatic suggestions are advisory by default.
4. **Local-first media processing.** Raw videos and frames remain local unless the user explicitly authorizes selected uploads to an AI provider.
5. **Deterministic operations remain deterministic.** Cropping, sheet layout, hashing, naming, and export must not depend on an LLM.
6. **AI is replaceable.** No critical product workflow may depend permanently on one model or provider.
7. **Reproducibility.** Every generated asset must retain source, settings, model, prompt, selected frames, and version metadata.
8. **Secure secret handling.** Production API keys must not be stored in project files, logs, SQLite, or plaintext `.env` files.
9. **Extensible architecture.** Unity and 2D are first, but exporter and analysis boundaries must support future engines and 3D workflows.
10. **No destructive implicit actions.** Background removal, crop, keyframe selection, and exports must remain reversible.
11. **Adopt proven infrastructure; own product intelligence.** Mature codecs, CV libraries, segmentation engines, trackers, credential stores, and provider clients should be integrated behind adapters rather than reimplemented. Motion interpretation, production decisions, review workflows, consistency scoring, and export policy remain MotionAnchor-owned logic.
12. **License-aware by design.** Code licenses, model-weight licenses, dataset terms, redistribution rights, and commercial-use restrictions are separate release gates.

---

## 6. Goals

### 6.1 MVP Goals

- Create and manage local animation projects.
- Import MP4, WebM, MOV, and GIF reference media.
- Extract exact video frames with timestamps.
- Generate motion signals and segment the animation into meaningful phases.
- Generate candidate frame groups per motion phase.
- Rank candidates using deterministic quality metrics and optional vision/reasoning AI.
- Compare candidates against one or more character reference images.
- Detect basic global and regional drift.
- Remove backgrounds while protecting fine edges.
- Apply safe shared-canvas crop and alignment.
- Build deterministic sprite sheets and individual PNG frames.
- Export through a Unity integration package.
- Configure multiple AI providers with secure API-key storage.
- Test provider connections and display available quota/usage information where providers expose it.
- Require final human approval before production export.
- Integrate approved open-source engines through replaceable interfaces.
- Maintain a dependency/model registry with license, source, version, checksum, redistribution status, and benchmark results.
- Produce third-party notices and an SBOM-ready dependency inventory for distributable builds.

### 6.2 Commercial Readiness Goals

- Keep account/licensing boundaries isolated so they can be added without rewriting the core.
- Support signed desktop updates.
- Retain project portability without exposing credentials.
- Permit future engine exporters and provider plugins.
- Provide structured logs, diagnostics, and crash-safe job recovery.

### 6.3 Future Goals

- Godot and Unreal Paper2D export.
- Spine/Live2D preparation.
- 3D motion reference analysis and rig-retargeting assistance.
- Team review and comments.
- Batch animation processing.
- Local vision models and offline inference.
- Automated variant generation for weapons, skins, and FX.

---

## 7. Non-Goals for MVP

- Fully automatic professional animation without user review.
- Frame-by-frame repainting of malformed AI frames.
- Guaranteed anatomical tracking of every finger or hair strand.
- Cloud project synchronization.
- Team accounts or permissions.
- Licensing/checkout implementation.
- Direct modification of a user’s Unity project without explicit confirmation.
- Direct generation of brittle cross-project `.meta` files.
- 3D rig generation in the first release.
- Training proprietary AI models.
- Reimplementing video codecs, general-purpose optical flow, standard image primitives, or operating-system credential storage already supplied by mature dependencies.
- Shipping GPL, AGPL, non-commercial, research-only, or unclear-license components in the commercial build without a separately approved legal and distribution strategy.

---

## 8. Locked Product Decisions

| Area | Decision |
|---|---|
| Current usage | Single user |
| Future direction | Sellable commercial product |
| Initial operating system | Windows desktop |
| Desktop shell | Tauri 2 |
| Frontend | React + TypeScript |
| Native host | Rust |
| Media/analysis worker | Python sidecar |
| Media processing | Local-first |
| AI execution | Internet providers initially |
| Provider architecture | Multi-provider abstraction from the start |
| Secrets | Windows Credential Manager in production |
| `.env` | Development-only, explicit opt-in fallback |
| Database | Local SQLite for non-secret metadata |
| Final approval | Human approval required by default |
| Initial production domain | 2D video-to-animation pipeline |
| Future domain | Extendable to 3D rig/motion workflows |
| Initial exporter | Unity 2022.3 LTS |
| Export architecture | Engine-independent interface |
| Product name | MotionAnchor; formal clearance pending |
| Product tagline | Consistent Characters. Production-Ready Motion. |
| Open-source strategy | Adopt mature infrastructure behind adapters; build MotionAnchor-specific decision logic |
| Distribution policy | Permissive dependencies preferred; copyleft/non-commercial components excluded by default |

---

## 9. Primary End-to-End Workflow

```text
Create Project
    ↓
Add Character Bible / Reference Images
    ↓
Import Motion Reference Video
    ↓
Extract Frames and Metadata
    ↓
Create Foreground Masks
    ↓
Measure Motion Signals
    ↓
Segment Motion into Phases
    ↓
Generate Candidate Frames per Phase
    ↓
Deterministic Quality Filtering
    ↓
AI Character/Weapon/Costume Review
    ↓
User Reviews and Locks Final Frames
    ↓
Background Cleanup and Safe Crop
    ↓
Baseline/Pivot Alignment
    ↓
Loop Preview and QA
    ↓
Build PNG Frames + Sprite Sheet
    ↓
Unity Export Package / Manifest
```

---

## 10. Functional Requirements

### 10.1 Project Workspace

The user must be able to:

- create, rename, archive, duplicate, and delete projects,
- define a project workspace directory,
- assign game engine and target profile,
- set default frame count, FPS, pivot, pixels-per-unit, padding, and export naming,
- store multiple characters per project,
- preserve source files and derived artifacts separately,
- reopen a project without recomputing completed analysis,
- invalidate and recompute only affected downstream stages.

Every project must contain a versioned manifest and content hashes for source and generated files.

### 10.2 Character Bible

A character profile must support:

- primary identity reference,
- turnaround sheet,
- animation reference sheet,
- face close-ups,
- weapon references,
- costume/material references,
- color palette,
- written immutable traits,
- optional negative constraints,
- version history.

The user must be able to mark references as:

- identity-critical,
- costume-critical,
- weapon-critical,
- style-only,
- optional.

AI review prompts must receive the correct reference subset for the requested task.

### 10.3 Video Import and Validation

The application must:

- support MP4, MOV, WebM, and GIF,
- show duration, FPS, resolution, codec, and frame count,
- detect variable frame-rate media,
- permit a user-selected time range,
- create a lossless or high-quality working copy when necessary,
- never overwrite the original source,
- warn when a source is too low-resolution, heavily compressed, blurred, or partially cropped.

### 10.4 Frame Extraction

Frame extraction must:

- preserve exact timestamps,
- permit extraction at native FPS or normalized FPS,
- produce stable sequential file names,
- retain color and alpha where available,
- store hashes and source timestamps,
- support regeneration with different sampling settings,
- avoid duplicate frames caused by decoding ambiguity.

### 10.5 Motion Segmentation

This module replaces naive equal-interval keyframe selection.

The application must calculate a motion feature timeline using signals such as:

- foreground centroid movement,
- silhouette area and contour change,
- optical-flow magnitude and direction,
- motion acceleration/deceleration,
- pose/embedding distance,
- head/body/weapon region movement where available,
- blink and FX event candidates,
- still holds,
- direction changes,
- similarity to possible loop boundaries.

The system must divide the timeline into meaningful phase groups, for example:

```text
Neutral Start
Breath Rising
Breath Peak
Breath Falling
Blink Event
Cape Return
Loop Closure
```

Requirements:

- segment boundaries must be editable,
- a segment may be merged, split, renamed, disabled, or locked,
- no final frame may be selected without belonging to a segment or explicit user override,
- the UI must show the signals that caused each proposed boundary,
- the system must distinguish transient events from sustained motion phases.

### 10.6 Candidate Frame Generation

Candidate generation must select representative frames **within each motion segment**, not across the full video at fixed intervals.

Candidate sources include:

- segment entry and exit,
- local motion extrema,
- acceleration inflection points,
- strongest readable silhouette,
- lowest blur frame near a target pose,
- event peak (blink, impact, flame pulse),
- loop boundary candidates,
- user-pinned frames.

Each segment should provide a configurable candidate set, typically 3–8 frames.

### 10.7 Deterministic Frame Quality Filtering

The system must calculate non-AI metrics including:

- blur/sharpness,
- alpha/mask completeness,
- foreground edge contact,
- duplicate similarity,
- frame corruption,
- unexpected canvas shift,
- gross silhouette area change,
- major weapon/character bounding-box anomalies.

These metrics may reject obviously unusable candidates before paid or limited AI calls.

### 10.8 AI-Assisted Candidate Review

Vision/reasoning models must review candidate sets with:

- segment intent,
- neighboring segment summaries,
- primary character references,
- relevant weapon/costume references,
- deterministic metrics,
- animation purpose,
- desired final frame count.

The AI response must be structured and include:

- selected candidate,
- confidence,
- reasons,
- rejected candidates and reasons,
- detected identity/costume/weapon errors,
- whether manual review is required.

The system should support:

- one-model review,
- ensemble review,
- a higher-quality tie-breaker model,
- manual-only operation.

AI selection is advisory until user approval.

### 10.9 Character Consistency Engine

The consistency engine is a core differentiator.

It must assess at minimum:

- face identity,
- hair silhouette and volume,
- skin tone consistency,
- body proportion consistency,
- costume color and major shape consistency,
- sword design/length/presence,
- staff design/length/presence,
- cape shape and attachment,
- missing or extra limbs/props,
- overall style consistency.

Output must include separate scores instead of a single opaque number:

```text
Character Identity     94
Face Consistency       91
Costume Consistency    97
Sword Consistency      88
Staff Consistency      96
Silhouette Stability   92
```

Scores must include confidence and supporting findings. The system must not mark an asset “production ready” based solely on one aggregate score.

### 10.10 Drift Detector

The drift detector must differentiate intentional motion from unwanted visual mutation.

Expected motion examples:

- torso rise during breathing,
- cape sway,
- head bob,
- sword rotation,
- staff translation with body movement.

Unwanted drift examples:

- head scale changing,
- face sliding independently,
- sword length changing,
- staff design mutating,
- hair volume changing without motion justification,
- feet sliding when the pose should remain planted.

MVP region scope:

- full silhouette,
- head,
- torso,
- feet/baseline,
- sword,
- staff,
- cape.

Reports must show:

- region,
- translation,
- rotation where measurable,
- scale/shape anomaly,
- expected range,
- severity,
- frame range,
- visual overlay.

### 10.11 Background Removal

Background removal must support layered strategies:

1. existing alpha passthrough,
2. chroma-key removal,
3. local foreground segmentation,
4. optional AI-assisted mask refinement,
5. future manual brush refinement.

The system must preserve:

- curly hair edges,
- cape tips,
- staff silhouette,
- sword glow,
- magic particles when configured,
- semi-transparent FX.

The UI must show mask confidence and an edge preview. Export must be blocked or warned when critical foreground touches the crop safety boundary.

### 10.12 Safe Auto-Crop and Alignment

Auto-crop must not tightly crop every frame independently.

Required method:

1. calculate foreground bounds for every approved frame,
2. compute union bounds across the full animation,
3. add configurable safety padding,
4. optionally include predicted overshoot for FX,
5. create one shared canvas for every frame,
6. align to a selected baseline and pivot,
7. validate that no critical pixel touches the safety boundary.

The user must be able to:

- increase/decrease padding,
- lock canvas dimensions,
- set bottom-center or custom pivot,
- choose body baseline versus visual center alignment,
- preview onion-skin overlays.

### 10.13 Loop Analysis and Preview

The system must:

- propose loop start/end pairs,
- calculate boundary similarity,
- preview the loop at configurable FPS,
- show a ping-pong preview where relevant,
- report visible center, scale, silhouette, and FX discontinuities,
- allow frame reordering and duplicated hold frames,
- preserve event timing such as blinks.

### 10.14 Sprite Sheet Builder

The builder must be deterministic and support:

- individual PNG frames,
- horizontal strip,
- vertical strip,
- configurable grid,
- fixed cell dimensions,
- padding and extrusion,
- power-of-two atlas option,
- frame order preview,
- naming templates,
- alpha validation,
- optional contact sheet for review.

It must never alter approved image content except explicit resize or color-space conversion configured by the user.

### 10.15 Unity Exporter

The initial exporter must target Unity 2022.3 LTS and use an engine-adapter interface.

The application must produce:

- sprite sheet PNG,
- optional individual frame PNGs,
- versioned animation manifest,
- import preset values,
- frame order and timing,
- pivot and pixels-per-unit,
- loop setting,
- filter/compression recommendations,
- artifact hashes.

A companion Unity Editor package should read the manifest and:

- configure texture import settings,
- slice sprite sheets,
- apply pivots,
- create Animation Clips,
- create or update an Animator Controller,
- preserve existing project assets unless the user explicitly approves replacement.

The exporter must not rely on generating reusable `.meta` files outside the target Unity project because GUID and editor-version coupling makes that approach fragile.


#### Export Asset Naming Standard

Before Unity export, the user must provide or confirm an animation asset name. The project name may be used as the initial suggestion, but the animation name remains editable per export. The same approved name must be visible in the RGBA preview and used by both dry-run and real export.

The locked individual-frame naming pattern is:

```text
<asset_name>_frame_<zero-padded 4-digit index>.png
```

Example:

```text
warlock_dash_frame_0001.png
warlock_dash_frame_0002.png
```

Unsupported filesystem characters and whitespace are normalized deterministically. Changing the asset name invalidates the previous dry-run plan. The export manifest must store the sanitized asset name and exact ordered frame filenames.

### 10.16 Provider Management

A provider settings area must support one screen per provider while sharing a common interface.

Each provider screen must provide:

- provider name and status,
- API-key entry/update/delete,
- secure storage confirmation,
- test connection,
- available models,
- vision/reasoning capability flags,
- configured default model per task,
- free/paid preference,
- timeout and retry policy,
- data-upload warning,
- quota/usage display where supported,
- link to provider dashboard where direct quota APIs are unavailable.

The application must never expose the full API key after storage. It may display a masked identifier.

### 10.17 Quota and Usage Manager

Providers expose usage differently. The system must support four strategies:

1. official usage/quota endpoint,
2. response headers,
3. locally estimated request/token/image accounting,
4. unknown/manual dashboard.

Every quota value must display a provenance label:

- authoritative,
- provider-header derived,
- locally estimated,
- unavailable.

Hard-coded free-tier limits are prohibited. Provider/model availability and quotas change frequently and must be refreshed through a registry or official provider APIs.

### 10.18 AI Task Router

Tasks must be classified by capability and criticality.

**Lightweight tasks**

- metadata normalization,
- report summarization,
- naming,
- schema repair.

**Moderate tasks**

- frame defect classification,
- segment labeling,
- basic consistency checks.

**Critical tasks**

- final keyframe recommendation,
- face/identity validation,
- weapon/costume drift evaluation,
- production-readiness review.

Routing decisions must consider:

- required modality,
- benchmark score for the task,
- current quota,
- estimated cost,
- latency,
- provider availability,
- privacy policy,
- user preference,
- commercial-use restrictions.

Free-tier models may be preferred for lightweight work but must not automatically receive critical work unless they pass the project benchmark threshold.

### 10.19 Human Review and Approval

Default production flow requires explicit approval for:

- motion segments,
- selected final frames,
- crop/canvas,
- final loop,
- Unity export.

The user must be able to lock approved items so reruns cannot silently replace them.

Future automatic approval may be enabled only through a configurable confidence policy. Main-character assets must default to manual approval.

### 10.20 Job History and Reproducibility

Each analysis/export run must record:

- source hash,
- application version,
- algorithm/module versions,
- settings,
- selected references,
- provider/model,
- prompts and structured responses,
- token/request estimates,
- selected/rejected frames,
- user overrides,
- output hashes,
- timestamps.

Secrets must never be recorded.

---


### 10.21 Open-Source Component Registry and Module Adapters

The product must maintain an explicit distinction between adopted infrastructure, benchmark candidates, excluded components, and MotionAnchor-owned product logic.

Required component states:

- `approved`: licensed, benchmarked, pinned, and allowed in distributable builds,
- `experimental`: available only behind a feature flag for technical evaluation,
- `external_tool`: invoked as a separately distributed executable with documented obligations,
- `excluded`: prohibited from commercial builds,
- `rejected`: evaluated and found unsuitable,
- `pending_review`: not usable until source, license, model weights, and dependencies are verified.

Every adopted engine must be accessed through a MotionAnchor-owned interface. The UI, project format, job model, and downstream modules must not depend directly on a specific implementation.

Initial interfaces include:

```text
IMediaDecoder
ISceneDetector
IMaskEngine
IChangePointDetector
IOpticalFlowEngine
IPointTracker
IFeatureEmbeddingEngine
IAIProvider
ICredentialStore
IExportAdapter
```

The registry must record:

- upstream repository and official documentation,
- exact version, tag, commit, or binary build,
- source-code license,
- model/checkpoint license,
- transitive dependency concerns,
- commercial-use and redistribution status,
- expected download size and hardware requirements,
- Windows packaging status,
- benchmark results on MotionAnchor fixtures,
- last verification date,
- replacement/fallback adapter.

A component may not move to `approved` solely because its repository uses a permissive license. Model weights and bundled assets must be reviewed independently.

Initial build/adopt decisions are defined in `04_Open_Source_Module_Strategy.md`.

## 11. User Experience Requirements

### 11.1 Core Screens

1. **Home / Projects**
2. **Project Dashboard**
3. **Character Bible**
4. **Video Import Wizard**
5. **Motion Timeline and Segmentation**
6. **Candidate Frame Review**
7. **Consistency and Drift QA**
8. **Mask / Crop / Alignment Editor**
9. **Loop Preview**
10. **Sprite Sheet Builder**
11. **Unity Export**
12. **Providers and API Keys**
13. **Quota and Usage**
14. **Job History / Diagnostics**

### 11.2 Review Interface

The review UI should show:

- segment timeline,
- motion graphs,
- candidate frames as synchronized columns,
- original/reference/candidate comparison,
- onion-skin overlay,
- region-level warnings,
- AI reasoning summary,
- confidence and source model,
- user lock/approve/reject controls.

### 11.3 Accessibility and Desktop Behavior

- scalable UI for 1080p and higher desktop displays,
- keyboard shortcuts for frame navigation and approval,
- zoom/pan for images,
- non-blocking background jobs,
- resumable workflows,
- clear destructive-action confirmations,
- no reliance on color alone for severity.

---

## 12. Data and Privacy Requirements

- Source videos and frames remain local by default.
- AI uploads require an explicit project/provider policy.
- The app should upload only selected candidate frames and required references, not full source video, unless a task explicitly requires video input and the user approves.
- Temporary upload bundles must be deleted locally after completion.
- Provider data-retention warnings must be visible.
- Projects must remain portable without API keys.
- Diagnostic exports must redact secrets and optionally exclude media.

---

## 13. Security Requirements

- API keys stored through Windows Credential Manager.
- No raw secrets in SQLite, project manifests, logs, telemetry, crash reports, command-line arguments, or frontend state persistence.
- `.env` permitted only in development builds with explicit feature flag and warnings.
- Tauri capabilities must grant only required commands and file scopes.
- Frontend must not execute arbitrary shell commands.
- Python sidecar must be launched and supervised by the Rust host.
- IPC messages must be validated against versioned schemas.
- Project file paths must be normalized and constrained to approved workspaces.
- Update packages must be signed before commercial distribution.
- Provider responses must be treated as untrusted input.

---

## 14. Non-Functional Requirements

### 14.1 Performance

- UI remains responsive during decoding and analysis.
- Long jobs expose progress, stage, estimated work remaining, cancel, and retry.
- Repeated runs reuse cached frames, masks, embeddings, and metrics when inputs/settings have not changed.
- 1080p short reference videos should be processed without requiring a discrete GPU for baseline features.
- GPU acceleration may be used for local segmentation or embeddings when available.

### 14.2 Reliability

- Jobs are restartable after application crash.
- No original asset is overwritten.
- Partial outputs are marked incomplete.
- Export is transactional: either the complete manifest/artifact set is committed or the previous export remains intact.

### 14.3 Maintainability

- External engines must remain isolated behind typed adapters and contract tests.
- No UI or domain module may import a concrete CV/AI engine directly.
- Dependency upgrades require fixture regression, license re-verification, and release-note review.
- The product must retain at least one deterministic fallback for every production-critical analysis stage where practical.

- Strict module boundaries.
- Versioned schemas and migrations.
- Provider adapters isolated from analysis logic.
- Export adapters isolated from engine-independent manifests.
- Unit, integration, golden-image, and end-to-end tests.

### 14.4 Observability

- structured local logs,
- per-job diagnostics,
- provider latency and failure metrics,
- redacted error reports,
- optional future telemetry with explicit opt-in.

---

## 15. Quality Model

The product must avoid a misleading universal score. Production readiness should be derived from weighted gates:

| Gate | Example rule |
|---|---|
| Critical anatomy/prop errors | Must be zero or explicitly waived |
| Identity consistency | Above project threshold |
| Weapon consistency | Above project threshold |
| Crop safety | No critical edge contact |
| Loop continuity | Below configured discontinuity threshold |
| Baseline stability | Within configured tolerance |
| Human approval | Required |

A final report may show an aggregate score, but every failed critical gate must remain visible.

---

## 16. MVP Acceptance Criteria

The MVP is accepted when a user can:

1. create a project and character profile,
2. securely configure at least two AI providers,
3. import an idle video,
4. extract frames and view timestamps,
5. receive editable motion segments based on measured movement,
6. view 3–8 candidate frames per segment,
7. receive structured AI candidate recommendations,
8. inspect basic face/weapon/silhouette consistency findings,
9. remove the background with edge preview,
10. produce a shared safe canvas without cutting character parts,
11. preview and approve an 8-frame loop,
12. export PNG frames, sprite sheet, and manifest,
13. import the manifest through the Unity package to create a working looping Animation Clip,
14. reproduce the export from job history without changing approved inputs.

---

## 17. Success Metrics

### Production Metrics

- reduction in manual frame extraction/alignment time,
- percentage of AI recommendations accepted without replacement,
- number of detected critical drift defects before Unity export,
- loop approval iterations,
- successful Unity imports,
- percentage of cached/reused analysis work.

### Product Metrics for Future Commercialization

- time to first successful export,
- provider connection success rate,
- crash-free sessions,
- update success rate,
- active projects per user,
- export volume,
- paid conversion and retention after commercialization.

---

## 18. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Vision models give inconsistent judgments | Structured schemas, reference sets, benchmark suite, ensembles, human approval |
| Free-tier models change or disappear | Dynamic registry, capability routing, multiple providers, no hard-coded model dependency |
| Background removal damages hair/FX | Layered masking, confidence visualization, safety margin, manual refinement roadmap |
| Drift tracking mistakes intended movement for mutation | Expected-motion profiles, region-specific thresholds, user overrides |
| Python sidecar packaging becomes large | Modular optional model packs, lazy downloads, build-size monitoring |
| FFmpeg/model license conflicts | Formal dependency/license review before commercial packaging |
| Unity asset generation breaks across versions | Versioned Unity adapter/package and integration tests against supported editor versions |
| API keys leak through logs | Native credential store, redaction tests, no command-line secrets |
| Product scope expands too early | MVP gates and strict non-goals |
| Upstream project is abandoned or changes license | Adapter isolation, pinned versions, source archive/checksum, fallback engines, periodic review |
| Code license is permissive but model weights are restricted | Separate code/model registry fields and mandatory model-card review |
| A copied repository has no explicit license | Treat as prohibited; inspect only for behavior/testing ideas, never copy code |
| Optional GPU engines fail on Windows packaging | Keep CPU baseline, feature flags, and benchmarked fallback adapters |

---


## 19. Open-Source Adoption and Build-vs-Adopt Policy

### 19.1 Adopt or Integrate Behind Adapters

- **FFmpeg:** media probing, decoding, exact frame extraction, clipping, and preview generation. Prefer a separately invoked LGPL-compatible build; GPL-enabled builds require separate approval.
- **OpenCV:** deterministic image processing, chroma keying, masks, contours, alignment, blur metrics, baseline optical flow, and geometry.
- **PySceneDetect:** optional detection of actual cuts, fades, and scene transitions; not animation-phase interpretation.
- **ruptures:** change-point algorithms over MotionAnchor-generated motion signals.
- **rembg:** baseline still-image background removal adapter; model weights reviewed separately.
- **SAM 2:** primary production candidate for promptable image/video segmentation and mask propagation.
- **Cutie/XMem:** benchmark candidates for temporally stable video object masks; Windows packaging must be proven.
- **TAPIR/TAPNext family:** point-tracking benchmark candidates for head, feet, weapon-tip, and anchor trajectories.
- **RAFT:** optional advanced optical-flow adapter after Windows/runtime benchmarking.
- **DINOv2 standard models:** candidate visual embeddings for similarity and anomaly signals; specialized research-only variants are excluded.
- **aisuite/direct adapters:** baseline candidates for provider abstraction.
- **LiteLLM:** benchmark candidate where its breadth, routing, and maintenance value justify its larger surface area.
- **Instructor/Pydantic:** structured AI response validation and repair.
- **keyring-rs with a Windows-native credential-store backend:** credential abstraction; no custom cryptography.

### 19.2 MotionAnchor-Owned Product Logic

MotionAnchor must own and test:

- motion-signal composition,
- animation-phase interpretation,
- segment-specific candidate generation,
- AI review-pack construction,
- final keyframe reasoning and ranking policy,
- expected motion versus unwanted drift classification,
- character/weapon/costume consistency aggregation,
- human-review workflow and approval gates,
- shared safe-canvas crop policy,
- deterministic sprite-sheet layout and metadata,
- engine-neutral export manifest,
- Unity companion package behavior,
- provenance, confidence, and production-readiness scoring.

### 19.3 Excluded by Default

- GPL/AGPL components embedded into a closed commercial build,
- Creative Commons NonCommercial or research-only code/weights,
- repositories without an explicit license,
- model checkpoints without verified commercial and redistribution terms,
- dependencies requiring source uploads or telemetry that conflict with local-first guarantees,
- upstream code copied directly into the core without an adapter and provenance record.

### 19.4 Evaluation Rule

No candidate is selected from reputation alone. Each engine must be tested against the same Cat Trap fixture set for quality, temporal stability, speed, VRAM/RAM, installation friction, Windows packaging, deterministic behavior, and license suitability.

---

## 20. Initial Provider Research Policy

- `freellm.net` may be used as a discovery and comparison source.
- Official provider documentation is the source of truth for models, rate limits, pricing, data use, and commercial restrictions.
- Every provider/model must pass an internal benchmark before receiving critical tasks.
- Provider capability and quota data must carry a last-checked timestamp.
- No free-tier promise should be embedded permanently in product copy or routing logic.

---

## 21. Research Basis

- Tauri supports frontend frameworks and a Rust application host: https://v2.tauri.app/start/
- Tauri external binaries/sidecars can bundle Python executables: https://v2.tauri.app/develop/sidecar/
- Tauri capability permissions constrain frontend access: https://v2.tauri.app/security/capabilities/
- Windows Credential Manager credential APIs: https://learn.microsoft.com/en-us/windows/win32/api/wincred/
- Windows DPAPI behavior: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
- Unity Sprite Editor and slicing: https://docs.unity3d.com/2022.3/Documentation/Manual/SpriteEditor.html
- Unity Sprite Data Provider API: https://docs.unity3d.com/2022.3/Documentation/Manual/Sprite-data-provider-api.html
- Unity Animator Controller: https://docs.unity3d.com/2022.3/Documentation/Manual/class-AnimatorController.html
- Gemini API pricing/rate limits: https://ai.google.dev/gemini-api/docs/pricing
- Groq rate limits: https://console.groq.com/docs/rate-limits
- OpenRouter limits/free variants: https://openrouter.ai/docs/api/reference/limits
- Free LLM discovery directory: https://freellm.net/about
- FFmpeg licensing overview: https://github.com/FFmpeg/FFmpeg
- OpenCV repository/license: https://github.com/opencv/opencv
- PySceneDetect: https://github.com/Breakthrough/PySceneDetect
- ruptures: https://github.com/deepcharles/ruptures
- rembg: https://github.com/danielgatis/rembg
- SAM 2: https://github.com/facebookresearch/sam2
- Cutie: https://github.com/hkchengrex/Cutie
- XMem: https://github.com/hkchengrex/XMem
- TAP tracking models: https://github.com/google-deepmind/tapnet
- RAFT: https://github.com/princeton-vl/RAFT
- DINOv2: https://github.com/facebookresearch/dinov2
- aisuite: https://github.com/andrewyng/aisuite
- LiteLLM: https://github.com/BerriAI/litellm
- Instructor: https://github.com/567-labs/instructor
- keyring-rs: https://github.com/open-source-cooperative/keyring-rs

---

## 22. Approval

This PRD establishes the baseline product scope. Changes that affect security, project format, provider abstraction, export manifest, or motion-selection methodology require a documented architecture decision and version update.
