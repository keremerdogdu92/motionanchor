# MotionAnchor
## System Architecture Document (SAD)

**Document version:** 1.1  
**Status:** Approved baseline updated for modular open-source integration and OpenCode delivery  
**Date:** 2026-07-11  
**Product:** MotionAnchor — Consistent Characters. Production-Ready Motion.  
**Initial deployment:** Windows desktop, local-first  
**Initial engine adapter:** Unity 2022.3 LTS

---

## 1. Architecture Objectives

The architecture must provide:

- secure local desktop operation,
- responsive React-based UX,
- high-quality Python image/video processing,
- a controlled Rust security and process boundary,
- replaceable AI providers,
- deterministic and reproducible processing,
- crash-safe background jobs,
- an engine-independent export contract,
- future commercialization and cross-platform expansion,
- future 3D modules without rewriting the 2D core.

---

## 2. High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│ Tauri Desktop Application                                    │
│                                                              │
│  ┌─────────────────────┐        ┌─────────────────────────┐   │
│  │ React + TypeScript  │  IPC   │ Rust Application Host   │   │
│  │ UI                  │◄──────►│ Security / Commands     │   │
│  └─────────────────────┘        │ Jobs / Secrets / Files  │   │
│                                 └───────────┬─────────────┘   │
│                                             │ supervised IPC  │
│                                 ┌───────────▼─────────────┐   │
│                                 │ Python Processing       │   │
│                                 │ Sidecar                 │   │
│                                 │ Frames / CV / AI        │   │
│                                 └───────────┬─────────────┘   │
└─────────────────────────────────────────────┼─────────────────┘
                                              │ HTTPS
                                    ┌─────────▼──────────┐
                                    │ AI Providers       │
                                    │ Gemini / Groq /    │
                                    │ OpenRouter / etc.  │
                                    └────────────────────┘

Local storage:
- SQLite metadata database
- Project workspace files
- Windows Credential Manager secrets
- Cache and derived artifacts
```

---

## 3. Technology Stack

| Layer | Technology | Responsibility |
|---|---|---|
| Desktop shell | Tauri 2 | Native window, packaging, permissions, process supervision |
| Frontend | React + TypeScript | Desktop workflow UI, review tools, settings |
| Native host | Rust | Secure commands, filesystem boundaries, credentials, SQLite coordination, sidecar lifecycle |
| Processing | Python 3.12+ | Video decoding, OpenCV, masks, motion analysis, AI orchestration |
| Local database | SQLite | Project and job metadata; never raw API keys |
| Media decoding | FFmpeg executable adapter; PyAV evaluated only if needed | Exact frame/timestamp extraction without binding the domain layer to codec libraries |
| Image processing | OpenCV, Pillow, NumPy | Deterministic masks, contours, alignment, metrics, previews, and sheets |
| ML runtime | Optional ONNX Runtime / PyTorch | Local segmentation, embeddings, future models |
| Secrets | Windows Credential Manager | API key storage |
| Initial engine integration | Unity Editor package | Import manifest, slice sprites, create clips/controller |

Dependency versions must be pinned and reviewed before implementation. Source-code licenses, model/checkpoint licenses, transitive dependencies, commercial-use terms, and redistribution rights are separate release gates.

---


### 3.1 Build-versus-Adopt Boundary

MotionAnchor adopts mature infrastructure for commodity technical operations and builds the product-specific intelligence that converts those operations into production decisions.

```text
Adopt / Wrap
├── media decoding and probing
├── deterministic image primitives
├── scene-cut detection
├── change-point algorithms
├── segmentation/mask propagation
├── optical flow and point tracking
├── visual feature extraction
├── provider transport clients
├── structured-output validation
└── operating-system credential storage

Build / Own
├── motion-signal composition
├── animation-phase semantics
├── segment candidate policy
├── expected-motion profiles
├── drift classification and explanation
├── consistency aggregation
├── review and approval workflow
├── safe shared-canvas policy
├── deterministic animation asset contract
├── Unity import behavior
└── provenance and production-readiness scoring
```

No concrete third-party implementation may leak into domain entities, persisted project formats, or frontend state. Every external engine is replaceable through a typed adapter.

### 3.2 Component Classes

| Class | Meaning | Distribution status |
|---|---|---|
| Approved | License, model weights, benchmark, packaging, and fallback reviewed | Allowed |
| Experimental | Technical spike only; feature-flagged | Internal builds only |
| External tool | Separate process/binary with documented obligations | Conditional |
| Excluded | Non-commercial, AGPL/GPL conflict, missing license, or unacceptable privacy | Prohibited |
| Rejected | Evaluated but failed quality/performance/maintenance requirements | Prohibited |
| Pending review | Source/model/dependency terms incomplete | Prohibited |

The authoritative matrix lives in `04_Open_Source_Module_Strategy.md` and must be versioned with release decisions.

## 4. Process Topology

### 4.1 React Frontend

The frontend is untrusted relative to native capabilities. It may request typed application commands but cannot directly:

- read arbitrary filesystem paths,
- access secrets,
- launch arbitrary programs,
- call provider APIs with raw keys,
- modify Unity projects without approved native commands.

### 4.2 Rust Host

The Rust host is the trusted desktop boundary. It owns:

- Tauri capabilities and command allowlist,
- project workspace authorization,
- credential-store access,
- SQLite migrations and connection lifecycle,
- Python sidecar spawning/termination,
- job state reconciliation,
- application update verification,
- redacted logging,
- validated frontend/sidecar message routing.

### 4.3 Python Sidecar

The Python worker is packaged as an external binary/sidecar for production. It owns:

- media probing and decoding,
- frame extraction,
- foreground segmentation,
- motion feature calculation,
- motion segmentation,
- candidate generation,
- drift/consistency preprocessing,
- provider requests through abstract adapters,
- third-party CV/ML engines through adapter interfaces,
- component version/provenance reporting,
- sprite-sheet construction,
- export artifact generation excluding native secret storage.

The sidecar receives secret values only in process memory for a specific request and must not persist them.

### 4.4 IPC Strategy

MVP uses a supervised long-running sidecar with versioned JSON-RPC over stdin/stdout.

Advantages:

- no listening TCP port,
- smaller local attack surface,
- direct process ownership,
- simple log separation,
- deterministic request/response IDs,
- progress-event streaming.

Message envelope:

```json
{
  "protocol_version": "1.0",
  "message_id": "uuid",
  "type": "job.start",
  "job_id": "uuid",
  "payload": {}
}
```

Rules:

- JSON schemas validated in Rust and Python,
- bounded message sizes,
- file references passed as approved paths, not raw arbitrary paths,
- secret values never echoed,
- sidecar stdout reserved for protocol messages; diagnostics use stderr,
- heartbeat and protocol-version negotiation at startup.

A named-pipe or local socket transport may be evaluated later if binary payload transfer becomes a bottleneck.

---

## 5. Security Architecture

### 5.1 Credential Storage Decision

**Primary production store:** Windows Credential Manager.

Implementation approach:

- define a platform-neutral `CredentialStore` interface in Rust,
- use Windows Credential Manager through a maintained native Rust backend,
- store one secret per provider/account scope,
- persist only the credential reference ID in SQLite,
- keep decrypted keys in memory only for the duration needed,
- zero/replace sensitive buffers where practical,
- never return full secrets to the React frontend after save.

Example logical identifiers:

```text
service: ai-animation-toolkit
account: provider/gemini/default
account: provider/openrouter/default
```

### 5.2 DPAPI Role

DPAPI is not the primary public credential UI. Windows Credential Manager already provides an OS-native credential set and lifecycle suitable for API keys.

Direct DPAPI is reserved as a future fallback for application-managed encrypted blobs that cannot be represented cleanly in Credential Manager. If used:

- protection scope defaults to current user,
- encrypted blobs remain outside project workspaces,
- entropy/version metadata is managed by Rust,
- migration and recovery limitations are documented.

### 5.3 Development `.env` Policy

`.env` support is allowed only when all conditions are true:

- non-production/dev build,
- explicit configuration flag enabled,
- startup warning shown,
- `.env` excluded from Git,
- credential-store values take precedence or behavior is explicitly selected,
- logs never display loaded values.

Commercial builds must not require `.env`.

### 5.4 Tauri Permissions

- Use Tauri capability files with least privilege.
- Restrict filesystem access to selected project roots, app config, cache, and export destinations.
- Disable arbitrary shell execution from the frontend.
- Sidecar executable names are compiled/configured, not user supplied.
- Apply a strict content security policy.
- Remote navigation is disabled unless explicitly required.

### 5.5 Provider Data Security

Provider requests are constructed in the Python/Rust service boundary, not directly in frontend JavaScript.

Each request records:

- provider/model,
- files authorized for upload,
- data-retention classification,
- payload hash,
- request cost estimate,
- response metadata.

It never records API keys or provider authorization headers.

---

## 6. Data Architecture

### 6.1 Storage Separation

| Data | Storage |
|---|---|
| API keys | Windows Credential Manager |
| App settings | SQLite / app config |
| Project metadata | Project SQLite or application SQLite with project IDs |
| Original video | Project workspace |
| Extracted frames | Project workspace derived directory |
| Masks/metrics/embeddings | Cache/derived directories |
| AI responses | Structured redacted project analysis records |
| Export artifacts | Project export directory |
| Logs | App-local redacted log directory |

### 6.2 Recommended Project Layout

```text
<ProjectRoot>/
├── project.json
├── character-bible/
│   ├── references/
│   ├── weapons/
│   ├── palettes/
│   └── character-profile.json
├── animations/
│   └── idle-001/
│       ├── source/
│       ├── frames/
│       ├── masks/
│       ├── analysis/
│       ├── approved/
│       ├── exports/
│       └── animation.json
└── cache/
```

Original files are immutable. Derived directories may be regenerated.

### 6.3 Core Database Entities

#### `projects`

- id
- name
- workspace_path
- engine_profile
- schema_version
- created_at
- updated_at

#### `characters`

- id
- project_id
- name
- active_bible_version
- default_profile_json

#### `character_references`

- id
- character_id
- type
- path
- content_hash
- priority
- version

#### `source_media`

- id
- project_id
- character_id
- path
- content_hash
- media_metadata_json

#### `animation_jobs`

- id
- source_media_id
- animation_type
- state
- settings_json
- current_stage
- error_code
- created_at
- completed_at

#### `frames`

- id
- job_id
- frame_index
- timestamp_ms
- path
- content_hash
- metrics_json

#### `motion_segments`

- id
- job_id
- sequence
- start_frame
- end_frame
- label
- locked
- signal_summary_json

#### `frame_candidates`

- id
- segment_id
- frame_id
- deterministic_score
- ai_score
- status
- reasons_json

#### `analysis_runs`

- id
- job_id
- module
- module_version
- provider_id
- model_id
- input_hash
- result_json
- confidence
- created_at

#### `qa_findings`

- id
- job_id
- frame_id nullable
- region
- category
- severity
- status
- evidence_json
- user_resolution

#### `exports`

- id
- job_id
- adapter
- adapter_version
- manifest_path
- output_hash
- status

#### `provider_configs`

- id
- provider_type
- display_name
- credential_reference
- non_secret_settings_json
- enabled

#### `usage_ledger`

- id
- provider_config_id
- model_id
- request_type
- estimated_units_json
- provider_reported_units_json
- source_quality
- timestamp

No table contains raw secrets.

---


#### `component_registry`

- `component_id`
- `name`
- `category`
- `adapter_id`
- `status`
- `upstream_url`
- `version_or_commit`
- `source_license`
- `model_license`
- `commercial_use_status`
- `redistribution_status`
- `binary_or_model_checksum`
- `benchmark_profile_id`
- `last_verified_at`
- `notes`

Secrets are never stored in this table. A project export records only non-secret component identifiers, versions, and checksums needed for reproducibility.

## 7. Job and Pipeline Architecture

### 7.1 Job State Machine

```text
CREATED
  → VALIDATING
  → EXTRACTING
  → MASKING
  → MEASURING_MOTION
  → SEGMENT_REVIEW_REQUIRED
  → GENERATING_CANDIDATES
  → AI_REVIEW
  → FRAME_APPROVAL_REQUIRED
  → CLEANUP_AND_ALIGNMENT
  → LOOP_REVIEW_REQUIRED
  → READY_TO_EXPORT
  → EXPORTING
  → COMPLETED

Any state may transition to:
- PAUSED
- CANCELLED
- FAILED_RETRYABLE
- FAILED_TERMINAL
```

Approved stages are checkpointed. Rerunning an upstream stage invalidates only dependent unlocked outputs.

### 7.2 Artifact Addressing and Cache

Derived artifacts use content-addressed cache keys:

```text
hash(source_hash + module_version + normalized_settings + reference_hashes)
```

This permits:

- repeatable results,
- cache reuse,
- safe invalidation,
- comparison between algorithm/provider versions.

---

## 8. Motion Analysis Architecture

### 8.1 Preprocessing

1. Decode frames with exact timestamps.
2. Normalize orientation and color space.
3. Create foreground masks.
4. Calculate a stable global registration reference.
5. Estimate baseline and character center.
6. Optionally produce downscaled analysis frames while preserving original-resolution production frames.

### 8.2 Per-Frame Feature Vector

```text
F(t) = [
  centroid_x,
  centroid_y,
  bbox_width,
  bbox_height,
  silhouette_area,
  contour_descriptor,
  optical_flow_magnitude,
  optical_flow_direction,
  blur_score,
  perceptual_embedding,
  head_region_features,
  sword_region_features,
  staff_region_features,
  cape_region_features,
  baseline_contact
]
```

Not every feature is available for every source. Feature availability and confidence are stored.

### 8.3 Motion Segmentation

Segmentation uses multiple signals rather than one threshold:

- smoothed motion-energy curve,
- velocity and acceleration changes,
- silhouette/embedding change points,
- direction changes,
- low-motion hold detection,
- event classifiers,
- loop similarity candidates.

Proposed technical sequence:

1. robustly normalize signals,
2. smooth noise without deleting fast events,
3. detect change points,
4. merge micro-segments below duration threshold,
5. protect detected events such as blink/impact,
6. label segments using deterministic patterns and optional AI,
7. expose boundaries for user review.

Equal-interval selection is not part of the production algorithm. It may exist only as a comparison/debug option.

### 8.4 Candidate Generation

For each segment, candidates are drawn from:

- entry/exit frames,
- local extrema,
- strongest pose separation,
- low-blur neighborhood representatives,
- highest silhouette readability,
- event peak,
- user pins.

A diversity constraint prevents near-duplicate candidates.

### 8.5 AI Review Pack

The application produces a compact review pack rather than uploading the entire frame sequence by default:

- segment contact sheet,
- individual candidate crops,
- previous/next segment representative,
- character references,
- deterministic metric table,
- explicit evaluation schema.

This lowers cost and reduces unnecessary media disclosure.

---

## 9. Character Consistency and Drift Architecture

### 9.1 Two-Layer Evaluation

#### Layer A — Geometric/Signal Analysis

- region tracking,
- centroid and scale movement,
- contour difference,
- perceptual similarity,
- weapon length/angle approximation,
- baseline displacement,
- missing-region detection.

#### Layer B — Semantic Vision Review

- identity preservation,
- hairstyle/costume recognition,
- prop correctness,
- anatomy anomalies,
- style consistency,
- intentional versus implausible change.

### 9.2 Region Tracking

MVP uses coarse semantic regions:

- head,
- torso,
- cape,
- sword,
- staff,
- feet/full lower body,
- full silhouette.

Regions may be initialized using:

- user-defined boxes/masks,
- local segmentation/detection,
- character reference annotations,
- propagated tracking.

Later versions may add pose estimation and keypoints.

### 9.3 Expected Motion Profiles

Every animation type may define expected ranges:

```json
{
  "animation_type": "idle",
  "head": { "translation_px": [0, 4], "scale_pct": [0, 1] },
  "torso": { "translation_y_px": [0, 6] },
  "feet": { "translation_px": [0, 1] },
  "cape": { "translation_px": [0, 12] },
  "sword": { "rotation_deg": [0, 5], "length_change_pct": [0, 1] }
}
```

A motion outside the profile is not automatically wrong; it becomes a finding for semantic review or user confirmation.

### 9.4 Drift Finding Format

```json
{
  "region": "sword",
  "frames": [42, 47],
  "metric": "length_change_pct",
  "observed": 5.2,
  "expected_max": 1.0,
  "severity": "error",
  "confidence": 0.88,
  "classification": "unwanted_drift"
}
```

---

## 10. Background Removal and Safe Canvas Architecture

### 10.1 Mask Pipeline

`IMaskEngine` is the only boundary visible to the pipeline. Initial implementations are `ExistingAlphaMaskEngine`, `ChromaKeyMaskEngine`, `RembgMaskEngine`, `Sam2MaskEngine`, and experimental `CutieMaskEngine`/`XMemMaskEngine`. Per-frame independent masks are not considered production-safe when temporal flicker exceeds the configured threshold.

```text
Existing Alpha?
  ├─ Yes → Validate/Refine
  └─ No
      ↓
Chroma Key Applicable?
  ├─ Yes → Key + Spill Cleanup
  └─ No → Local Segmentation
                   ↓
          Optional AI Refinement
                   ↓
              Edge QA
```

Masks are versioned and non-destructive.

### 10.2 Edge Safety

The system assigns regions to preservation classes:

- critical opaque character,
- critical thin object (sword/staff/hair),
- semi-transparent FX,
- optional particles,
- background.

Crop/export warnings depend on class. A critical thin object touching the safety boundary blocks automatic approval.

### 10.3 Shared Canvas Algorithm

```text
approved_frame_masks
    → union bounds
    → include configured FX bounds
    → add safety padding
    → normalize cell dimensions
    → align baseline/pivot
    → edge-contact validation
```

No per-frame tight crop is used for final animation frames.

---

## 11. AI Provider Architecture

### 11.1 Provider Interface

The domain owns `IAIProvider`; aisuite, LiteLLM, official SDKs, or direct HTTP clients may implement transport adapters after benchmark and license review. No upstream provider library defines MotionAnchor task schemas, routing policy, retry policy, quota semantics, or persisted provider identifiers.

```python
class AiProvider(Protocol):
    def list_models(self) -> list[ModelDescriptor]: ...
    def test_connection(self) -> ConnectionResult: ...
    def invoke(self, request: AiRequest) -> AiResponse: ...
    def get_usage(self) -> UsageSnapshot: ...
    def capabilities(self) -> ProviderCapabilities: ...
```

### 11.2 Model Capability Descriptor

```json
{
  "provider": "example",
  "model_id": "model-name",
  "modalities": ["text", "image"],
  "structured_output": true,
  "max_images": 16,
  "reasoning_level": "high",
  "commercial_use": "unknown",
  "free_tier": "dynamic",
  "last_verified_at": "2026-07-11T00:00:00Z"
}
```

### 11.3 Task Router

The router receives a task contract:

```json
{
  "task": "critical_keyframe_review",
  "required_modalities": ["image", "text"],
  "minimum_benchmark": 0.85,
  "privacy_class": "character_asset",
  "max_estimated_cost": 0.05,
  "fallback_count": 2
}
```

Selection priority:

1. capability eligibility,
2. project/provider restrictions,
3. benchmark threshold,
4. quota availability,
5. privacy/commercial policy,
6. cost preference,
7. latency,
8. reliability.

### 11.4 Provider Registry

The registry stores dynamic metadata and benchmark results. It may use directories such as `freellm.net` for discovery, but official provider documentation/API is authoritative.

Hard-coded quotas are prohibited. Every dynamic field has:

- source,
- fetched time,
- confidence/provenance,
- expiry time.

### 11.5 Quota Adapter

```python
class QuotaStrategy(Protocol):
    def read(self) -> UsageSnapshot: ...
```

Implementations:

- official API strategy,
- response-header strategy,
- local-estimate strategy,
- manual-dashboard strategy.

The UI must not present estimates as authoritative limits.

### 11.6 Benchmark Harness

Critical provider routing requires an internal benchmark suite built from approved project samples and synthetic tests.

Dimensions:

- identity ranking accuracy,
- weapon/costume defect detection,
- structured JSON validity,
- frame-ranking agreement with human labels,
- latency,
- cost,
- retry/failure rate.

Benchmark results are model-version-specific.

---

## 12. Unity Export Architecture

### 12.1 Engine-Independent Manifest

Example:

```json
{
  "schema_version": "1.0",
  "animation": {
    "name": "Aeris_Idle_01",
    "fps": 8,
    "loop": true,
    "frame_count": 8,
    "pivot": { "mode": "bottom_center", "x": 0.5, "y": 0.0 },
    "pixels_per_unit": 160
  },
  "sprite_sheet": {
    "path": "Aeris_Idle_01.png",
    "columns": 4,
    "rows": 2,
    "cell_width": 512,
    "cell_height": 512,
    "padding": 0
  },
  "frames": [
    { "index": 0, "name": "Aeris_Idle_01_000", "duration_ms": 125 }
  ]
}
```

### 12.2 Export Adapter Interface

```text
ExportAdapter
- validate(profile, manifest)
- build_artifacts(job)
- describe_target()
- compatibility_version()
```

### 12.3 Unity Companion Package

A versioned Unity Editor package imports the manifest and uses Unity editor APIs to:

- configure `TextureImporter` as Sprite/Multiple,
- define sprite rectangles/pivots through supported Sprite Editor APIs,
- set filter, compression, alpha, and PPU,
- create an Animation Clip with ordered sprite references,
- set loop behavior,
- create/update an Animator Controller,
- show a dry-run diff before modifying existing assets.

This approach is safer than writing external `.meta` files because Unity GUIDs and serialized assets belong to the target project/editor context.


### 12.4 Deterministic Export Naming Contract

The export adapter receives a user-approved animation asset name before dry-run generation. The React preview, Rust dry-run planner, atomic exporter, manifest, and Unity companion importer must use the same normalized value.

```text
asset directory: Assets/MotionAnchor/<asset_name>/
frame filename:  <asset_name>_frame_0001.png
clip filename:   <asset_name>.anim
```

Normalization is deterministic and owned by the Rust export boundary. A name change invalidates any prior plan so that previewed paths cannot differ from published paths. Frame indices are one-based and padded to four digits to preserve lexical and animation order.

---

## 13. Frontend Architecture

### 13.1 Recommended Feature Modules

```text
src/
├── app/
├── features/
│   ├── projects/
│   ├── character-bible/
│   ├── media-import/
│   ├── motion-timeline/
│   ├── candidate-review/
│   ├── consistency-qa/
│   ├── mask-editor/
│   ├── loop-preview/
│   ├── sprite-builder/
│   ├── exports/
│   ├── providers/
│   └── jobs/
├── components/
├── services/
├── schemas/
└── state/
```

Use generated/shared TypeScript schemas for IPC payload validation.

### 13.2 State Management

- server-like/native state through query cache,
- minimal UI state store,
- no secret persistence,
- job progress through event subscription,
- optimistic updates only for reversible metadata changes.

### 13.3 Media Rendering

Large frame sets should use:

- virtualized lists,
- thumbnail pyramids,
- lazy full-resolution decode,
- GPU canvas/WebGL where necessary,
- off-main-thread image preparation where possible.

---

## 14. Python Module Architecture

```text
worker/
├── protocol/
├── jobs/
├── domain/
│   ├── results.py
│   ├── findings.py
│   └── component_ids.py
├── adapters/
│   ├── media/
│   │   └── ffmpeg/
│   ├── scenes/
│   │   └── pyscenedetect/
│   ├── masks/
│   │   ├── chroma/
│   │   ├── rembg/
│   │   ├── sam2/
│   │   ├── cutie/
│   │   └── xmem/
│   ├── flow/
│   │   ├── opencv/
│   │   └── raft/
│   ├── tracking/
│   │   ├── opencv/
│   │   └── tapir/
│   ├── embeddings/
│   │   └── dinov2/
│   └── providers/
├── media/
│   ├── probe.py
│   └── extract.py
├── masks/
├── motion/
│   ├── features.py
│   ├── segmentation.py
│   ├── candidates.py
│   ├── expected_profiles.py
│   └── loop.py
├── consistency/
│   ├── regions.py
│   ├── drift.py
│   ├── semantics.py
│   └── scoring.py
├── ai/
│   ├── routing/
│   ├── quotas/
│   ├── prompts/
│   └── schemas/
├── components/
│   ├── registry.py
│   ├── licensing.py
│   ├── checksums.py
│   └── benchmarks.py
├── sprite/
├── export/
└── diagnostics/
```

Concrete adapter packages may import third-party libraries. Domain, motion, consistency, sprite, and export modules may import only MotionAnchor interfaces and typed result contracts.

All modules return typed result objects containing:

- module version,
- confidence,
- warnings,
- artifact references,
- deterministic input hash.

---


### 14.1 Core Adapter Contracts

```python
from typing import Protocol, Sequence

class IMaskEngine(Protocol):
    engine_id: str

    def create_masks(self, request: "MaskRequest") -> "MaskResult": ...


class IPointTracker(Protocol):
    engine_id: str

    def track(self, request: "TrackRequest") -> "TrackResult": ...


class IAIProvider(Protocol):
    provider_id: str

    async def execute(self, request: "ProviderTask") -> "ProviderResult": ...
```

Contracts must expose engine identity, version, deterministic settings, hardware path, warnings, confidence, and artifact hashes. Adapter-specific objects must not cross the boundary.

### 14.2 Initial Adapter Decisions

| Capability | Baseline | Advanced candidate | MotionAnchor responsibility |
|---|---|---|---|
| Media decode | FFmpeg process | PyAV only if justified | Exact extraction policy and provenance |
| Basic CV | OpenCV | None required | Feature composition and thresholds |
| Scene cuts | PySceneDetect optional | Custom detectors only if needed | Decide whether a cut invalidates an animation source |
| Change points | ruptures | Custom/alternative benchmark | Motion-phase semantics |
| Background mask | Chroma/OpenCV, rembg | SAM 2, Cutie, XMem | Engine selection, temporal QA, edge safety |
| Optical flow | OpenCV | RAFT | Signal normalization and expected-motion use |
| Point tracks | OpenCV anchors | TAPIR/TAPNext | Anchor definitions and drift interpretation |
| Embeddings | DINOv2 standard candidate | Provider vision embeddings | Region comparison policy |
| AI transport | Direct/aisuite candidate | LiteLLM benchmark | Task schema, routing, quota and fallback policy |
| Structured output | Pydantic/Instructor | Provider-native schema | Validation rules and semantic acceptance |
| Secrets | keyring-rs + Windows native store | Platform stores later | Credential naming, access policy, redaction |

CoTracker and any non-commercial/research-only code or weights are excluded from commercial builds.

## 15. Testing Strategy

### 15.1 Unit Tests

- feature calculations,
- change-point utilities,
- crop union and padding,
- manifest validation,
- quota provenance,
- secret redaction,
- provider schema parsing.

### 15.2 Golden-Image Tests

Store licensed/internal fixtures and expected outputs for:

- masks,
- crop bounds,
- alignment,
- sprite-sheet layout,
- motion curves,
- drift overlays.

Use perceptual tolerances where exact pixels vary by platform/library.

### 15.3 Integration Tests

- adapter contract tests against shared fixtures,
- fallback behavior when an optional engine is unavailable,
- component registry/version/checksum capture,
- Windows packaging and cold-start tests for optional model packs,

- Rust ↔ Python protocol,
- credential storage/read/delete,
- SQLite migrations,
- provider adapter mocks,
- crash/restart recovery,
- Unity manifest import.

### 15.4 Provider Benchmark Tests

- stable labeled candidate sets,
- structured-output validity,
- human agreement score,
- task-specific thresholds.

### 15.5 End-to-End Test

A release-candidate test must use only components marked `approved` and must generate a machine-readable inventory proving that excluded or pending components are absent.

A fixture idle video must successfully pass:

```text
Import → Extract → Segment → Candidate Review → Crop → Sheet → Unity Clip
```

---

## 16. Packaging and Updates

### 16.1 Packaging

- Generate `THIRD_PARTY_NOTICES`, component lock data, and an SBOM-compatible inventory.
- Bundle only reviewed binaries and model packs.
- Prefer optional, checksum-verified model downloads where redistribution terms or installer size make bundling unsuitable.
- Do not bundle GPL/AGPL, non-commercial, research-only, or missing-license components in the commercial package.

- Tauri packages the desktop host.
- Python is bundled as a sidecar executable for the target architecture.
- Optional large local models should be downloadable packs rather than mandatory application payloads.
- Version compatibility is checked between host, sidecar, schema, and Unity package.

### 16.2 Updates

Future commercial builds should use Tauri’s signed updater mechanism. The application must not install unsigned update payloads.

### 16.3 Code Signing

Windows code signing is a v1.0 commercial release requirement, not an MVP blocker.

---

## 17. Commercialization Boundaries

MVP remains local and account-free, but the following interfaces must be isolated:

- `LicenseService`
- `EntitlementService`
- `UpdateChannelService`
- `TelemetryService`
- `CloudSyncService`

MVP implementations are local/no-op. This prevents future licensing from contaminating animation-processing modules.

---

## 18. Architecture Decision Records

### ADR-001 — Tauri + React + Rust + Python

**Decision:** Use Tauri/React for desktop UX, Rust for the trusted native boundary, and Python for image/video/AI processing.

**Reason:** It preserves familiar React/Python development while using Tauri’s native security and packaging model.

### ADR-002 — Windows Credential Manager

**Decision:** Store production provider API keys in Windows Credential Manager through a Rust credential abstraction.

**Reason:** Keys should not exist in plaintext project/config files. It also enables future platform keychain backends.

### ADR-003 — Local-First Media

**Decision:** Process source media locally and upload only explicit candidate/reference bundles.

**Reason:** Reduces privacy exposure, bandwidth, and provider cost.

### ADR-004 — Motion Segmentation Before Keyframe Selection

**Decision:** Segment movement phases before producing final frame candidates.

**Reason:** Equal/random sampling cannot reliably represent animation timing and key poses.

### ADR-005 — Human-in-the-Loop

**Decision:** Require approval before final export by default.

**Reason:** Assets are created once and reused repeatedly; silent quality errors are expensive.

### ADR-006 — Provider Abstraction and Benchmarking

**Decision:** Route tasks through a capability/benchmark-based provider layer.

**Reason:** Model availability, free tiers, quality, and quotas are dynamic.

### ADR-007 — Unity Companion Package

**Decision:** Export a stable manifest and let a Unity Editor package create Unity-native assets.

**Reason:** Avoid fragile external `.meta` and serialized asset generation.

### ADR-008 — Engine-Neutral Export Contract

**Decision:** Unity is an adapter, not the internal asset model.

**Reason:** Enables later Godot, Unreal, Spine, and 3D integrations.

### ADR-009 — Adopt Infrastructure, Own Production Intelligence

**Decision:** Integrate mature open-source infrastructure behind MotionAnchor interfaces while implementing motion-phase semantics, consistency policy, review workflow, and export contracts internally.

**Reason:** Avoids reimplementing commodity algorithms without surrendering the product’s differentiating logic or maintainability.

### ADR-010 — Code and Model Licenses Are Independent Gates

**Decision:** A permissive repository license does not approve its model weights, datasets, bundled assets, or transitive dependencies.

**Reason:** Commercial redistribution risk frequently exists outside the top-level source license.

### ADR-011 — No Unlicensed Source Incorporation

**Decision:** Repositories without an explicit license may be studied for behavior and test ideas but no code, assets, or implementation text may be copied.

**Reason:** Public availability is not permission to reuse.

---

## 19. Open Technical Investigations

These do not block document approval but must be resolved during the foundation phase:

1. Exact FFmpeg LGPL-compatible Windows build, codec flags, notices, and update process.
2. SAM 2 versus Cutie/XMem versus rembg quality, temporal stability, model licenses, Windows packaging, and fallback behavior.
3. Exact Rust credential crate/backend and Windows persistence mode.
4. Sidecar packaging size and cold-start performance.
5. SQLite ownership boundary: Rust-only versus controlled sidecar access.
6. GPU acceleration strategy on NVIDIA/AMD/Intel.
7. Unity package API compatibility across 2022.3 patch versions.
8. DINOv2 standard model versus provider embeddings for region similarity.
9. TAPIR/TAPNext runtime, checkpoint terms, Windows packaging, and point-track accuracy.
10. OpenCV flow versus RAFT quality/VRAM tradeoff.
11. aisuite versus LiteLLM versus direct provider adapters for image inputs, async behavior, structured outputs, quotas, and packaging.
12. Automated SBOM and third-party notice generation for Rust, Python, npm, binaries, and model packs.

---

## 20. Research Basis

- Tauri external binaries/sidecars: https://v2.tauri.app/develop/sidecar/
- Tauri security capabilities: https://v2.tauri.app/security/capabilities/
- Tauri SQL plugin/SQLite support: https://v2.tauri.app/plugin/sql/
- Tauri updater: https://v2.tauri.app/plugin/updater/
- Microsoft Credential APIs: https://learn.microsoft.com/en-us/windows/win32/api/wincred/
- Microsoft DPAPI: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
- Rust keyring documentation: https://docs.rs/keyring
- Windows-native keyring backend: https://docs.rs/windows-native-keyring-store
- Unity Sprite Editor Data Provider API: https://docs.unity3d.com/2022.3/Documentation/Manual/Sprite-data-provider-api.html
- Unity TextureImporter sprite sheet API: https://docs.unity3d.com/2022.3/Documentation/ScriptReference/TextureImporter-spritesheet.html
- Unity Animator Controller: https://docs.unity3d.com/2022.3/Documentation/Manual/class-AnimatorController.html
- FFmpeg: https://github.com/FFmpeg/FFmpeg
- OpenCV: https://github.com/opencv/opencv
- PySceneDetect: https://github.com/Breakthrough/PySceneDetect
- ruptures: https://github.com/deepcharles/ruptures
- rembg: https://github.com/danielgatis/rembg
- SAM 2: https://github.com/facebookresearch/sam2
- Cutie: https://github.com/hkchengrex/Cutie
- XMem: https://github.com/hkchengrex/XMem
- TAP tracking: https://github.com/google-deepmind/tapnet
- RAFT: https://github.com/princeton-vl/RAFT
- DINOv2: https://github.com/facebookresearch/dinov2
- aisuite: https://github.com/andrewyng/aisuite
- LiteLLM: https://github.com/BerriAI/litellm
- Instructor: https://github.com/567-labs/instructor
- keyring-rs: https://github.com/open-source-cooperative/keyring-rs

---

## 21. Architecture Approval Gate

Implementation may begin after approval of:

- process topology,
- secret-store decision,
- database ownership,
- project manifest schema direction,
- job state machine,
- provider abstraction,
- engine-neutral export manifest,
- Unity package strategy,
- open-source/module evaluation matrix,
- component registry and commercial distribution policy.
