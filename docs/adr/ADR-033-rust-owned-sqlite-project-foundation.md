# ADR-033: Rust-Owned SQLite Project Foundation

## Status
Accepted

## Context
MotionAnchor requires durable project metadata before media, jobs, and exports can be attached to a real workspace. The Rust host is the trusted filesystem and persistence boundary, while the React frontend must not receive arbitrary database access.

## Decision
- Use `rusqlite` with the bundled SQLite build.
- Store the application database under the Tauri app-data directory.
- Let Rust exclusively own connection configuration, migrations, and project commands.
- Apply ordered SQL migrations in an immediate transaction and track the schema through `PRAGMA user_version`.
- Start with the `projects` table and a nullable `archived_at` field required by the roadmap archive flow.
- Store no raw provider secrets in SQLite.
- Canonicalize and validate workspace directories before project insertion.

## Consequences
- Project metadata survives application restarts.
- React receives only typed Tauri command results.
- Future migrations must be append-only and covered by migration tests.
- Worker and artifact metadata will be attached to project IDs in later migrations.
