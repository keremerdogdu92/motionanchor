# MotionAnchor
## Open-Source Module Strategy and Evaluation Matrix

**Document version:** 1.0  
**Status:** Approved implementation input; individual engines remain subject to Phase 0 verification  
**Date:** 2026-07-11  
**Product:** MotionAnchor — Consistent Characters. Production-Ready Motion.

---

## 1. Purpose

MotionAnchor should not reimplement mature codec, computer-vision, segmentation, tracking, provider-client, or credential-storage infrastructure. It should integrate suitable components through replaceable adapters while retaining ownership of animation semantics, character consistency policy, human review, reproducibility, and engine export.

This document is the source of truth for initial build-versus-adopt decisions. It does not constitute legal advice. Every distributable version must re-verify licenses and model terms against official upstream sources.

---

## 2. Decision Categories

| Status | Definition |
|---|---|
| Adopt | Intended baseline after Phase 0 verification |
| Benchmark | Candidate requiring quality, packaging, and license evaluation |
| Optional | Useful but not required for the first production path |
| Build | MotionAnchor-owned product logic |
| Exclude | Must not enter the commercial build |
| Inspect only | May inform behavior/tests; no source or assets may be copied |

---

## 3. Initial Module Matrix

| Capability | Candidate | Initial status | Integration model | License/packaging note | Decision owner |
|---|---|---:|---|---|---|
| Video probe/decode/extract | FFmpeg | Adopt | Separate executable adapter | Prefer LGPL-compatible build; record configure flags and notices | Media spike |
| Image primitives | OpenCV | Adopt | Python adapter/library | Apache-2.0 upstream; pin Python/native package and transitive licenses | CV spike |
| Image composition | Pillow/NumPy | Adopt | Python library | Verify pinned package licenses | CV spike |
| Actual scene cuts/fades | PySceneDetect | Optional | Adapter | BSD-3-Clause; not used for animation-phase semantics | Media spike |
| Change-point algorithms | ruptures | Adopt candidate | Adapter | BSD-2-Clause; MotionAnchor supplies signals and semantic interpretation | Motion spike |
| Flat/chroma background | OpenCV | Build with adopted primitives | MotionAnchor engine | Deterministic baseline and fallback | Mask spike |
| Still-image background removal | rembg | Benchmark | Adapter | MIT code; every model weight reviewed separately | Mask spike |
| Promptable video segmentation | SAM 2 | Benchmark, preferred advanced candidate | Optional model adapter | Verify code/checkpoint terms, size, GPU/CPU behavior, Windows packaging | Mask spike |
| Video object segmentation | Cutie | Benchmark | Experimental adapter | MIT code; official repo states Ubuntu-only testing, so Windows proof required | Mask spike |
| Long-term video masks | XMem | Benchmark/fallback | Experimental adapter | MIT code; model and dependencies reviewed separately | Mask spike |
| Baseline optical flow | OpenCV | Adopt | Adapter | CPU-compatible deterministic baseline | Motion spike |
| Advanced optical flow | RAFT | Optional benchmark | Optional model adapter | BSD-3-Clause code; checkpoint/dependency/runtime review required | Motion spike |
| Point tracking | TAPIR/TAPNext family | Benchmark | Optional model adapter | Apache-2.0 software; checkpoint and JAX/PyTorch packaging verified separately | Tracking spike |
| Visual embeddings | DINOv2 standard models | Benchmark | Optional model adapter | Standard code/weights are permissive; specialized research/medical variants excluded unless separately cleared | Consistency spike |
| Multi-provider transport | Direct official adapters | Adopt baseline | `IAIProvider` implementations | Lowest hidden behavior; more maintenance | Provider spike |
| Multi-provider transport | aisuite | Benchmark | Adapter implementation helper | MIT; verify vision, async, error, quota, and model-discovery behavior | Provider spike |
| Multi-provider transport | LiteLLM | Benchmark | Adapter implementation helper | Broad surface; verify exact OSS/commercial boundaries and packaging | Provider spike |
| Structured AI outputs | Pydantic + Instructor/provider-native schemas | Adopt candidate | Validation layer | Instructor MIT; domain schemas remain MotionAnchor-owned | Provider spike |
| Credential storage | keyring-rs + Windows-native store | Adopt candidate | Rust `ICredentialStore` | Use Windows Credential Manager; no custom encryption | Security spike |
| Character point tracking | CoTracker | Exclude | None | Non-commercial license is incompatible with intended commercial product | Architecture |
| Unlicensed sprite/video repos | Various | Inspect only | None | No code/assets copied without an explicit compatible license | Architecture |
| Sprite sheet layout | MotionAnchor | Build | Domain service | Fixed order, cell, pivot, baseline, manifest, reproducibility | Product core |
| Safe auto-crop | MotionAnchor | Build | Domain service using masks | Union bounds, safety margins, edge-contact failure, shared canvas | Product core |
| Motion-phase semantics | MotionAnchor | Build | Domain engine | Differentiating product logic | Product core |
| Keyframe review/ranking policy | MotionAnchor | Build | Domain + AI orchestration | Segment-aware, explainable, human-approved | Product core |
| Drift/consistency aggregation | MotionAnchor | Build | Domain engine | Combines geometry, tracks, embeddings, AI, expected profiles | Product core |
| Unity export | MotionAnchor Unity package | Build | Export adapter | Use official Unity Editor APIs and engine-neutral manifest | Product core |

---

## 4. Mandatory Adapter Boundaries

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

Rules:

1. Domain and UI code depend on interfaces, never concrete engines.
2. Adapter-specific configuration is stored in versioned adapter settings, not generic domain entities.
3. Each result includes engine ID, version, settings hash, hardware path, warnings, and artifact hashes.
4. Failure of an optional adapter must produce a controlled fallback or actionable error.
5. Project files remain readable when an optional engine is not installed.

---

## 5. License and Model Governance

### 5.1 Accepted by Default

- MIT
- Apache-2.0
- BSD-2-Clause
- BSD-3-Clause

Acceptance remains conditional on transitive dependencies, patents/codecs, bundled assets, and model terms.

### 5.2 Conditional

- LGPL: permitted only with an approved distribution and notice strategy; external-process use is preferred for FFmpeg.
- Provider SDK terms: reviewed for redistribution, telemetry, data handling, and commercial use.
- Model downloads: may be optional rather than bundled depending on license and installer size.

### 5.3 Excluded by Default

- GPL/AGPL embedded into the proprietary commercial build,
- Creative Commons NonCommercial,
- research-only licenses,
- missing or unclear licenses,
- checkpoints whose commercial or redistribution terms are not verified,
- dependencies that silently upload user media or telemetry against product policy.

### 5.4 Required Records

For every component and model:

- official upstream URL,
- version/tag/commit,
- checksum,
- source license,
- model/checkpoint license,
- commercial-use decision,
- redistribution decision,
- notices/attribution,
- transitive exceptions,
- last verified date,
- benchmark results,
- replacement adapter.

---

## 6. Shared Evaluation Fixture

All candidates must be tested using the same fixture set:

1. Current Cat Trap idle video.
2. Character turnaround reference.
3. Animation-prep reference.
4. Synthetic defects:
   - sword length mutation,
   - staff-tip mutation,
   - head scale drift,
   - face identity drift,
   - foot sliding,
   - cape clipping,
   - hair edge loss,
   - glow/particle crop risk.
5. Short, medium, and longer videos.
6. Existing-alpha, flat-background, and complex-background sources.

---

## 7. Benchmark Dimensions

| Dimension | Required output |
|---|---|
| Quality | Mask IoU/edge review, temporal flicker, track stability, defect detection agreement |
| Performance | Processing time, throughput, cold start, RAM, VRAM, disk size |
| Reliability | Crash/error rate, retry behavior, corrupt-input behavior |
| Windows readiness | Install, packaging, GPU/CPU path, sidecar behavior |
| Reproducibility | Determinism, model/version capture, output hash stability |
| Maintainability | API stability, release activity, documentation, replacement difficulty |
| Licensing | Code, weights, dependencies, commercial use, redistribution |
| UX impact | Required manual prompts, correction burden, preview latency |

---

## 8. Approval Gate

A candidate becomes `approved` only when:

- official source and license are recorded,
- weights/checkpoints are separately cleared,
- Windows installation and packaging are proven,
- shared fixtures pass defined quality thresholds,
- adapter contract tests pass,
- failure/fallback behavior is documented,
- component lock and checksum are generated,
- third-party notice entry is prepared,
- an ADR or matrix decision records the selection.

---

## 9. Sources

- FFmpeg: https://github.com/FFmpeg/FFmpeg
- OpenCV: https://github.com/opencv/opencv
- PySceneDetect: https://github.com/Breakthrough/PySceneDetect
- ruptures: https://github.com/deepcharles/ruptures
- rembg: https://github.com/danielgatis/rembg
- SAM 2: https://github.com/facebookresearch/sam2
- Cutie: https://github.com/hkchengrex/Cutie
- XMem: https://github.com/hkchengrex/XMem
- TAP tracking models: https://github.com/google-deepmind/tapnet
- RAFT: https://github.com/princeton-vl/RAFT
- DINOv2: https://github.com/facebookresearch/dinov2
- CoTracker license: https://github.com/facebookresearch/co-tracker/blob/main/LICENSE.md
- aisuite: https://github.com/andrewyng/aisuite
- LiteLLM: https://github.com/BerriAI/litellm
- Instructor: https://github.com/567-labs/instructor
- keyring-rs: https://github.com/open-source-cooperative/keyring-rs
