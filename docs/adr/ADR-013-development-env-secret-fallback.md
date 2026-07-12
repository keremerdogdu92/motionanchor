# ADR-013 — Development-only `.env` secret fallback

- **Status:** Accepted for Phase 0 spike
- **Date:** 2026-07-12

## Context

Production secrets use Windows Credential Manager. Developers may need a local plaintext fallback for isolated testing, but accidental activation or release-build use would violate the security baseline.

## Decision

Add a Rust `DevelopmentEnvStore` adapter with no runtime dependencies. It is available only when all of these conditions hold:

1. the binary is a debug build,
2. `MOTIONANCHOR_ALLOW_ENV_SECRETS=1`,
3. `MOTIONANCHOR_ENV_FILE` names an explicit file,
4. entries use the `MOTIONANCHOR_SECRET_` namespace.

Release builds reject the adapter unconditionally. Values are never logged or returned in probe reports. A security warning is emitted when the adapter is actually used.

## Limits

- Maximum file size: 64 KiB.
- Maximum secret size: 2 KiB.
- No implicit repository-root `.env` discovery.
- No generic environment-variable import.
- No write or delete support.
- Credential Manager remains the production store.

## Consequences

The fallback is deterministic and easy to remove. It does not introduce a dotenv dependency. Developers must explicitly select the adapter; there is no silent fallback from Credential Manager.
