# MotionAnchor

**Tagline:** Consistent Characters. Production-Ready Motion.

**Status:** Core production pipeline and real Cat Trap acceptance gate are complete; packaged Windows and clean Unity acceptance remain.

---

## Windows Prerequisites

| Requirement | Minimum Version | Check Command |
|---|---|---|
| Rust (rustc + cargo) | 1.97.0+ | `rustc --version` |
| MSVC C++ Build Tools | 2022+ (cl.exe 14.44+) | Installed via Visual Studio Installer |
| Windows SDK | 10.0.26100+ | Check `C:\Program Files (x86)\Windows Kits\10\Include` |
| WebView2 Runtime | Evergreen (150+) | Pre-installed on Windows 10/11 |
| Node.js | 24.x+ | `node --version` |
| npm | 11.x+ | `npm --version` |

All versions listed above were verified on the development machine during Spike 0.1.

---

## Development Commands

```bash
# Install npm dependencies (first time only)
npm install

# Type-check TypeScript without emitting
npm run typecheck

# Build frontend (tsc + vite)
npm run build

# Start Vite dev server only (frontend in browser)
npm run dev

# Start full Tauri development app (frontend + Rust + native window)
npm run tauri:dev

# Cargo check (Rust compilation check)
cargo check          # run from src-tauri/

# Cargo tests
cargo test           # run from src-tauri/

# Python worker tests
cd worker
python -m unittest discover -s tests -v

# Real Cat Trap release acceptance (run from repository root)
npm run acceptance:cat-trap
```

The first `npm run tauri:dev` or `cargo check` compiles ~400 Rust crates and takes approximately 90 seconds. Subsequent builds are cached.

---

## Repository Structure (Spike 0.2a)

```text
motionanchor/
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ AGENTS.md                         # OpenCode agent instructions
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ README.md                         # This file
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ package.json                      # npm manifest
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ package-lock.json                 # npm lock (reproducibility)
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ tsconfig.json                     # TypeScript config
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ tsconfig.node.json                # TypeScript config for Vite
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ vite.config.ts                    # Vite + Tauri dev server config
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ index.html                        # Vite entry HTML
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ .gitignore                        # Root ignore rules
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ .vscode/extensions.json           # VS Code recommendations
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ src/                              # React + TypeScript frontend
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ main.tsx                      # React root mount
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ App.tsx                       # Main component (invokes greet command)
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ App.css                       # Minimal styling
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ vite-env.d.ts                 # Vite type reference
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ assets/react.svg              # React logo
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ public/                           # Static assets
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ vite.svg
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ tauri.svg
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ src-tauri/                        # Rust host (Tauri 2)
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Cargo.toml                    # Rust crate manifest
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Cargo.lock                    # Rust lock (reproducibility)
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ tauri.conf.json               # Tauri application config
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ build.rs                      # Tauri build script
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ capabilities/default.json     # Minimal Tauri capabilities
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ src/lib.rs                    # Tauri commands + builder
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ src/sidecar.rs                # Rust worker supervisor and protocol probe
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ src/main.rs                   # Rust entry point
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ icons/                        # Scaffold app icons
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ .gitignore                    # Ignores target/, gen/schemas
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ worker/                           # Python protocol worker and tests
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ docs/                             # Product and architecture docs
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ 01_Product_Requirements_Document.md
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ 02_System_Architecture_Document.md
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ 03_Development_Roadmap.md
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ 04_Open_Source_Module_Strategy.md
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ 05_OpenCode_Implementation_Handoff.md
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ .opencode/                        # OpenCode configuration
    ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ agents/
    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ review.md
    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡   ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ docs.md
    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ commands/
        ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ phase0-plan.md
        ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ implement-slice.md
        ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ review-slice.md
        ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ update-docs.md
```

---

## Running the Development Application

1. Ensure all Windows prerequisites are installed.
2. Run `npm install` from the repository root.
3. Run `npm run tauri:dev`.
4. The first run compiles the Rust host (~90 seconds). A native window titled "MotionAnchor" opens.
5. The React interface renders with a text input and a "Greet" button.
6. Typing a name and clicking "Greet" invokes the Rust `greet` command via Tauri IPC and displays the response.
7. Edit `src/App.tsx` or `src-tauri/src/lib.rs` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Vite hot-reloads the frontend; Tauri recompiles Rust on save.

---

## Spike 0.1 Scope Exclusions

The following are **not** included in Spike 0.1 and will be addressed in later Phase 0 spikes or subsequent phases:

- Python project creation and virtual environment
- Pydantic or any Python validation library
- JSON-RPC protocol design
- Python sidecar binary or Tauri `externalBin` configuration
- FFmpeg integration or video probing
- OpenCV integration or image processing
- Media processing, frame extraction, or motion analysis
- Credential storage (Windows Credential Manager / keyring)
- SQLite database or migrations
- Packaging customization (NSIS, MSI, signing, updater)
- ESLint, Vitest, Prettier, or other code quality tooling
- Unity export or engine adapter code
- AI provider integration or API key management
- Any plugin beyond `core:default` Tauri capability

---

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

## Reading Order

`AGENTS.md` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ PRD ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ SAD ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Roadmap ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Open-Source Strategy ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ OpenCode Handoff

## Packaged Worker

Spike 0.2b packages the standard-library worker as a Windows x64 executable using PyInstaller 6.21.0. Build it with:

```powershell
powershell -ExecutionPolicy Bypass -File worker/build-worker.ps1
```

The generated target-triple binary is placed under `src-tauri/binaries/` and registered through Tauri `bundle.externalBin`. Rust integration tests launch the executable directly and verify handshake, ping/pong correlation, and graceful shutdown without a system Python dependency.
---

## Credential Store Spike

The Rust host now owns a `CredentialStore` abstraction backed by Windows Credential Manager. The Phase 0 probe writes a uniquely named temporary credential, reads and verifies it, deletes it, and confirms it is no longer retrievable.

Security constraints:

- target namespace: `MotionAnchor/<key>`
- bounded ASCII keys and 2048-byte secret limit
- no secret values in logs, command-line arguments, project files, SQLite, frontend state, or Python IPC
- temporary credential targets are deleted by the test
- production does not silently fall back to plaintext storage

Verification command: `cargo test --manifest-path src-tauri/Cargo.toml`

Decision record: `docs/adr/ADR-012-windows-credential-store.md`.

## FFmpeg Development Setup

MotionAnchor uses an external LGPL FFmpeg build behind the Python media adapter. The verified Windows development package is `BtbN.FFmpeg.LGPL.8.1` version `8.1.2-20260630`.

Set explicit tool paths when FFmpeg is not yet visible on PATH:

```powershell
$env:MOTIONANCHOR_FFMPEG="C:\path\to\ffmpeg.exe"
$env:MOTIONANCHOR_FFPROBE="C:\path\to\ffprobe.exe"
```

The adapter probes codec, dimensions, duration, rates, frame count, and VFR indication. Extraction writes lossless PNG frames plus `frames.json` containing exact ffprobe timestamps. Existing output directories are never overwritten.

## OpenCV Mask Baseline

Runtime dependencies are pinned in `worker/requirements-runtime.txt`: OpenCV headless 4.13.0.92 and NumPy 2.4.6. The MotionAnchor-owned `MaskEngine` contract currently has deterministic existing-alpha and chroma-key implementations. Results record engine/version, dimensions, foreground metrics, bounding box, edge contact, and a SHA-256 mask hash.

This spike uses synthetic thin-feature fixtures only. Cat Trap hair, cape, sword, staff, glow, and temporal-quality evaluation remain required before production approval.

## Mask Benchmark Harness

Shared mask metrics are implemented under `worker/motionanchor_worker/benchmarks`. Candidate masks are compared with manually approved ground truth using IoU, precision, recall, and boundary F1. Fixture metadata and provenance live under `fixtures/masks`. Real Cat Trap assets are not yet present, so production mask quality remains unverified.

## Worker Media Operations

Protocol 1.0 now accepts `media.probe` and `media.extract_frames`. Responses preserve request and job identifiers, return JSON-safe metadata/artifact summaries, and map invalid requests or FFmpeg failures to structured errors. Progress and cancellation are intentionally deferred to the next job-runner slice. Decision record: `docs/adr/ADR-017-worker-media-protocol.md`.

## Rust Media Probe Client

The Rust host now exposes a typed `probe_media` Tauri command. It canonicalizes and validates the source file, supervises the worker lifecycle, sends `media.probe`, validates the response correlation ID, deserializes `MediaProbeReport`, and shuts the worker down cleanly. The integration test probes the real Cat Trap dash fixture. Decision record: `docs/adr/ADR-018-rust-media-probe-client.md`.

## Rust Frame Extraction

The Tauri command `extract_frames` validates source and output paths, sends `media.extract_frames` to the worker, and returns a typed `FrameExtractionReport`. The real Cat Trap dash fixture is verified end to end at 240 frames. FFmpeg must be available through PATH or explicit `MOTIONANCHOR_FFMPEG` / `MOTIONANCHOR_FFPROBE` overrides. Decision record: `docs/adr/ADR-019-rust-frame-extraction-client.md`.

## Worker Job Foundation

The Python worker now owns an in-memory, thread-safe `JobRunner` with explicit queued, running, completed, failed, and cancelled states. Jobs expose bounded progress, optional status text, structured failures, result payloads, timestamps, and cooperative cancellation. Protocol/Tauri wiring and active FFmpeg subprocess termination are intentionally deferred to the next slice. See `docs/adr/ADR-020-worker-job-runner-foundation.md`.

## Cancellable Media Jobs

Frame extraction can now run as a worker-owned background job through `job.submit.media.extract_frames`, `job.status`, and `job.cancel`. FFmpeg is supervised with `Popen`; cancellation terminates the child process and removes partial frame artifacts while retaining the output directory. See `docs/adr/ADR-021-cancellable-media-job-protocol.md`.

## Persistent Rust Job Client

Tauri now exposes `start_frame_extraction_job`, `get_job_status`, and `cancel_job` through a lazily started persistent Python sidecar. Job IDs remain valid across polling and cancellation calls because the same supervised worker process owns the in-memory registry. Decision record: `docs/adr/ADR-022-rust-persistent-job-sidecar-client.md`.

## First Interactive Media Workflow

The React shell now exposes the real backend path: explicit source/output paths, media probe, cancellable frame-extraction submission, progress polling, terminal state, structured errors, and artifact result display. See `docs/adr/ADR-023-first-media-workflow-ui.md`.

## Native Path Selection

The media workflow uses the official Tauri dialog plugin for single-video and output-directory selection. The frontend receives only the selected paths; Rust and worker validation remain authoritative. No filesystem or shell capability was added. See `docs/adr/ADR-024-native-media-path-dialogs.md`.

## Representative Frame Preview

Completed frame-extraction jobs automatically load eight evenly spaced previews from `frames.json`. Rust validates every manifest filename, canonicalizes each child path, caps the total payload at 12 MiB, and returns PNG data URLs without granting general filesystem access. See `docs/adr/ADR-025-bounded-frame-preview-gallery.md`.

## Real Mask Baseline Result

The 240-frame Cat Trap dash fixture was evaluated with a deterministic temporal-median background baseline and centroid-aligned temporal metrics. The candidate was rejected for production because it merges speed lines and dust, loses interior character regions, and produces excessive boundary turnover. Aggregate results and the worst-pair diagnostic sheet live under `fixtures/cat-trap/dash/`; see `docs/adr/ADR-027-cat-trap-temporal-median-mask-baseline.md`.
