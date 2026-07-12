# ADR-012: Windows Credential Manager for Secrets

- Status: Accepted (Phase 0 spike)
- Date: 2026-07-12

## Decision

MotionAnchor stores provider secrets through a Rust-owned `CredentialStore` abstraction backed by Windows Credential Manager generic credentials. Targets use the `MotionAnchor/<key>` namespace and local-machine persistence. The React frontend and Python worker never receive arbitrary credential-store access.

## Security properties

- Secrets are never written to SQLite, project files, command-line arguments, stdout, or diagnostics.
- Credential keys are restricted to a bounded ASCII identifier set.
- Secret blobs are bounded to 2048 bytes.
- Temporary Rust buffers are overwritten after use where practical.
- Tests use unique temporary targets and delete them immediately.

## Dependency and licensing

The implementation uses `windows` 0.61.3 with only `Win32_Foundation` and `Win32_Security_Credentials` features. The crate is MIT/Apache-2.0 licensed. No Python or frontend dependency is added.

## Consequences

A development-only `.env` adapter remains a separate explicit-fallback spike. Production code must default to Windows Credential Manager and must not silently fall back to plaintext storage.