-- src-tauri/migrations/0001_projects.sql
-- Creates the first MotionAnchor application database schema for persistent projects.

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
    workspace_path TEXT NOT NULL UNIQUE,
    engine_profile TEXT NOT NULL CHECK (length(trim(engine_profile)) BETWEEN 1 AND 64),
    schema_version INTEGER NOT NULL DEFAULT 1 CHECK (schema_version >= 1),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    archived_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_projects_active_updated
    ON projects (archived_at, updated_at DESC);

PRAGMA user_version = 1;
