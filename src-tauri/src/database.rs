/// src-tauri/src/database.rs
/// Owns the trusted SQLite connection, migrations, and project repository commands.

use rusqlite::{params, Connection, OptionalExtension};
use serde::Serialize;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use tauri::Manager;
use uuid::Uuid;

const CURRENT_SCHEMA_VERSION: i64 = 1;
const MIGRATION_0001: &str = include_str!("../migrations/0001_projects.sql");

pub struct DatabaseState {
    connection: Mutex<Connection>,
    database_path: PathBuf,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DatabaseStatus {
    pub database_path: String,
    pub schema_version: i64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectRecord {
    pub id: String,
    pub name: String,
    pub workspace_path: String,
    pub engine_profile: String,
    pub schema_version: i64,
    pub created_at: String,
    pub updated_at: String,
    pub archived_at: Option<String>,
}

pub fn initialize(app: &tauri::AppHandle) -> Result<DatabaseState, String> {
    let app_data_dir = app
        .path()
        .app_data_dir()
        .map_err(|error| format!("could not resolve app data directory: {error}"))?;
    std::fs::create_dir_all(&app_data_dir)
        .map_err(|error| format!("could not create app data directory: {error}"))?;
    initialize_at(app_data_dir.join("motionanchor.sqlite3"))
}

fn initialize_at(database_path: PathBuf) -> Result<DatabaseState, String> {
    let connection = Connection::open(&database_path)
        .map_err(|error| format!("could not open MotionAnchor database: {error}"))?;
    configure_connection(&connection)?;
    apply_migrations(&connection)?;
    Ok(DatabaseState {
        connection: Mutex::new(connection),
        database_path,
    })
}

fn configure_connection(connection: &Connection) -> Result<(), String> {
    connection
        .execute_batch(
            "PRAGMA foreign_keys = ON;\n\
             PRAGMA journal_mode = WAL;\n\
             PRAGMA synchronous = NORMAL;\n\
             PRAGMA busy_timeout = 5000;",
        )
        .map_err(|error| format!("could not configure MotionAnchor database: {error}"))
}

fn apply_migrations(connection: &Connection) -> Result<(), String> {
    let version: i64 = connection
        .query_row("PRAGMA user_version", [], |row| row.get(0))
        .map_err(|error| format!("could not read database schema version: {error}"))?;
    if version > CURRENT_SCHEMA_VERSION {
        return Err(format!(
            "database schema version {version} is newer than supported version {CURRENT_SCHEMA_VERSION}"
        ));
    }
    if version == 0 {
        connection
            .execute_batch(&format!("BEGIN IMMEDIATE;\n{MIGRATION_0001}\nCOMMIT;"))
            .map_err(|error| format!("could not apply database migration 0001: {error}"))?;
    }
    Ok(())
}

fn canonical_workspace(path: &str) -> Result<String, String> {
    let canonical = Path::new(path)
        .canonicalize()
        .map_err(|error| format!("invalid project workspace path: {error}"))?;
    if !canonical.is_dir() {
        return Err("project workspace path must be a directory".into());
    }
    canonical
        .to_str()
        .map(str::to_owned)
        .ok_or_else(|| "project workspace path is not valid UTF-8".to_string())
}

fn validate_label(value: &str, label: &str, max_length: usize) -> Result<String, String> {
    let normalized = value.trim();
    if normalized.is_empty() || normalized.chars().count() > max_length {
        return Err(format!("{label} must contain 1 to {max_length} characters"));
    }
    Ok(normalized.to_owned())
}

fn row_to_project(row: &rusqlite::Row<'_>) -> rusqlite::Result<ProjectRecord> {
    Ok(ProjectRecord {
        id: row.get(0)?,
        name: row.get(1)?,
        workspace_path: row.get(2)?,
        engine_profile: row.get(3)?,
        schema_version: row.get(4)?,
        created_at: row.get(5)?,
        updated_at: row.get(6)?,
        archived_at: row.get(7)?,
    })
}

#[tauri::command]
pub fn database_status(state: tauri::State<'_, DatabaseState>) -> Result<DatabaseStatus, String> {
    let connection = state
        .connection
        .lock()
        .map_err(|_| "database lock poisoned".to_string())?;
    let schema_version = connection
        .query_row("PRAGMA user_version", [], |row| row.get(0))
        .map_err(|error| format!("could not read database status: {error}"))?;
    Ok(DatabaseStatus {
        database_path: state.database_path.to_string_lossy().into_owned(),
        schema_version,
    })
}

#[tauri::command]
pub fn create_project(
    name: &str,
    workspace_path: &str,
    engine_profile: &str,
    state: tauri::State<'_, DatabaseState>,
) -> Result<ProjectRecord, String> {
    let name = validate_label(name, "project name", 120)?;
    let engine_profile = validate_label(engine_profile, "engine profile", 64)?;
    let workspace_path = canonical_workspace(workspace_path)?;
    let id = Uuid::new_v4().to_string();
    let connection = state
        .connection
        .lock()
        .map_err(|_| "database lock poisoned".to_string())?;
    connection
        .execute(
            "INSERT INTO projects (id, name, workspace_path, engine_profile, schema_version)\n             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![id, name, workspace_path, engine_profile, CURRENT_SCHEMA_VERSION],
        )
        .map_err(|error| format!("could not create project: {error}"))?;
    connection
        .query_row(
            "SELECT id, name, workspace_path, engine_profile, schema_version, created_at, updated_at, archived_at\n             FROM projects WHERE id = ?1",
            params![id],
            row_to_project,
        )
        .map_err(|error| format!("could not load created project: {error}"))
}

#[tauri::command]
pub fn list_projects(
    include_archived: bool,
    state: tauri::State<'_, DatabaseState>,
) -> Result<Vec<ProjectRecord>, String> {
    let connection = state
        .connection
        .lock()
        .map_err(|_| "database lock poisoned".to_string())?;
    let sql = if include_archived {
        "SELECT id, name, workspace_path, engine_profile, schema_version, created_at, updated_at, archived_at\n         FROM projects ORDER BY updated_at DESC"
    } else {
        "SELECT id, name, workspace_path, engine_profile, schema_version, created_at, updated_at, archived_at\n         FROM projects WHERE archived_at IS NULL ORDER BY updated_at DESC"
    };
    let mut statement = connection
        .prepare(sql)
        .map_err(|error| format!("could not prepare project list: {error}"))?;
    let rows = statement
        .query_map([], row_to_project)
        .map_err(|error| format!("could not query projects: {error}"))?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|error| format!("could not decode project list: {error}"))
}

#[tauri::command]
pub fn archive_project(
    project_id: &str,
    state: tauri::State<'_, DatabaseState>,
) -> Result<ProjectRecord, String> {
    let connection = state
        .connection
        .lock()
        .map_err(|_| "database lock poisoned".to_string())?;
    let changed = connection
        .execute(
            "UPDATE projects\n             SET archived_at = COALESCE(archived_at, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),\n                 updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')\n             WHERE id = ?1",
            params![project_id],
        )
        .map_err(|error| format!("could not archive project: {error}"))?;
    if changed == 0 {
        return Err("project not found".into());
    }
    connection
        .query_row(
            "SELECT id, name, workspace_path, engine_profile, schema_version, created_at, updated_at, archived_at\n             FROM projects WHERE id = ?1",
            params![project_id],
            row_to_project,
        )
        .optional()
        .map_err(|error| format!("could not load archived project: {error}"))?
        .ok_or_else(|| "project not found".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn migration_creates_versioned_project_schema() {
        let directory = tempfile::tempdir().expect("temporary directory");
        let state = initialize_at(directory.path().join("test.sqlite3")).expect("database");
        let connection = state.connection.lock().expect("database lock");
        let version: i64 = connection
            .query_row("PRAGMA user_version", [], |row| row.get(0))
            .expect("schema version");
        let table: String = connection
            .query_row(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'projects'",
                [],
                |row| row.get(0),
            )
            .expect("projects table");
        assert_eq!(version, CURRENT_SCHEMA_VERSION);
        assert_eq!(table, "projects");
    }

    #[test]
    fn project_repository_creates_lists_and_archives() {
        let directory = tempfile::tempdir().expect("temporary directory");
        let state = initialize_at(directory.path().join("test.sqlite3")).expect("database");
        let workspace = directory.path().join("workspace");
        std::fs::create_dir(&workspace).expect("workspace");
        let connection = state.connection.lock().expect("database lock");
        let id = Uuid::new_v4().to_string();
        connection
            .execute(
                "INSERT INTO projects (id, name, workspace_path, engine_profile) VALUES (?1, ?2, ?3, ?4)",
                params![id, "Cat Trap", workspace.to_string_lossy(), "unity-2022.3"],
            )
            .expect("insert project");
        let active: i64 = connection
            .query_row("SELECT COUNT(*) FROM projects WHERE archived_at IS NULL", [], |row| row.get(0))
            .expect("active count");
        connection
            .execute(
                "UPDATE projects SET archived_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?1",
                params![id],
            )
            .expect("archive project");
        let archived: i64 = connection
            .query_row("SELECT COUNT(*) FROM projects WHERE archived_at IS NOT NULL", [], |row| row.get(0))
            .expect("archived count");
        assert_eq!(active, 1);
        assert_eq!(archived, 1);
    }
}
