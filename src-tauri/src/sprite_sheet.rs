/// Deterministic engine-neutral sprite-sheet publication.
use image::{GenericImageView, ImageBuffer, Rgba};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Path, PathBuf},
};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SpriteSheetPlan {
    pub ready: bool,
    pub asset_name: String,
    pub destination_path: String,
    pub frame_count: usize,
    pub columns: u32,
    pub rows: u32,
    pub cell_width: u32,
    pub cell_height: u32,
    pub sheet_width: u32,
    pub sheet_height: u32,
    pub errors: Vec<String>,
}
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SpriteSheetResult {
    pub package_path: String,
    pub sheet_path: String,
    pub manifest_path: String,
    pub frame_count: usize,
    pub sheet_sha256: String,
}

fn sanitize(value: &str) -> Result<String, String> {
    crate::canonical_export::sanitize_asset_name(value)
}
fn frames(workspace: &Path) -> Result<Vec<PathBuf>, String> {
    let root = workspace.join("artifacts/rgba/shared_canvas");
    let mut files = fs::read_dir(&root)
        .map_err(|e| format!("could not inspect shared canvas: {e}"))?
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| p.extension().is_some_and(|x| x.eq_ignore_ascii_case("png")))
        .collect::<Vec<_>>();
    files.sort();
    if files.is_empty() {
        return Err("shared canvas contains no PNG frames".into());
    }
    Ok(files)
}
fn plan(
    workspace: &Path,
    asset_name: &str,
    columns: u32,
    padding: u32,
) -> Result<SpriteSheetPlan, String> {
    if columns == 0 || columns > 64 {
        return Err("columns must be between 1 and 64".into());
    }
    if padding > 64 {
        return Err("padding must be at most 64".into());
    }
    let asset_name = sanitize(asset_name)?;
    let files = frames(workspace)?;
    let first = image::open(&files[0]).map_err(|e| format!("invalid frame PNG: {e}"))?;
    let (w, h) = first.dimensions();
    let mut errors = Vec::new();
    for file in &files[1..] {
        match image::open(file) {
            Ok(img) if img.dimensions() == (w, h) => {}
            Ok(_) => errors.push(format!("frame dimensions do not match: {}", file.display())),
            Err(e) => errors.push(format!("invalid frame PNG {}: {e}", file.display())),
        }
    }
    let rows = ((files.len() as u32) + columns - 1) / columns;
    let sw = columns * w + (columns + 1) * padding;
    let sh = rows * h + (rows + 1) * padding;
    let destination = workspace
        .join("exports")
        .join(format!("{}_sheet", asset_name));
    if destination.exists() {
        errors.push("sprite-sheet destination already exists".into())
    }
    Ok(SpriteSheetPlan {
        ready: errors.is_empty(),
        asset_name,
        destination_path: destination.to_string_lossy().into_owned(),
        frame_count: files.len(),
        columns,
        rows,
        cell_width: w,
        cell_height: h,
        sheet_width: sw,
        sheet_height: sh,
        errors,
    })
}
#[tauri::command]
pub fn build_sprite_sheet_plan(
    workspace_path: &str,
    asset_name: &str,
    columns: u32,
    padding: u32,
) -> Result<SpriteSheetPlan, String> {
    let w = Path::new(workspace_path)
        .canonicalize()
        .map_err(|e| format!("invalid workspace: {e}"))?;
    plan(&w, asset_name, columns, padding)
}
#[tauri::command]
pub fn execute_sprite_sheet(
    workspace_path: &str,
    asset_name: &str,
    columns: u32,
    padding: u32,
) -> Result<SpriteSheetResult, String> {
    let w = Path::new(workspace_path)
        .canonicalize()
        .map_err(|e| format!("invalid workspace: {e}"))?;
    execute(&w, asset_name, columns, padding)
}
fn execute(
    workspace: &Path,
    asset_name: &str,
    columns: u32,
    padding: u32,
) -> Result<SpriteSheetResult, String> {
    let spec = plan(workspace, asset_name, columns, padding)?;
    if !spec.ready {
        return Err(format!(
            "sprite-sheet plan blocked: {}",
            spec.errors.join("; ")
        ));
    }
    let files = frames(workspace)?;
    let destination = PathBuf::from(&spec.destination_path);
    let parent = destination.parent().ok_or("destination has no parent")?;
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    let staging = parent.join(format!(".sheet-staging-{}", Uuid::new_v4()));
    fs::create_dir(&staging).map_err(|e| e.to_string())?;
    let result = (|| {
        let mut sheet = ImageBuffer::<Rgba<u8>, Vec<u8>>::new(spec.sheet_width, spec.sheet_height);
        for (i, file) in files.iter().enumerate() {
            let img = image::open(file).map_err(|e| e.to_string())?.to_rgba8();
            let col = (i as u32) % columns;
            let row = (i as u32) / columns;
            image::imageops::replace(
                &mut sheet,
                &img,
                (padding + col * (spec.cell_width + padding)).into(),
                (padding + row * (spec.cell_height + padding)).into(),
            );
        }
        let sheet_path = staging.join(format!("{}_sheet.png", spec.asset_name));
        sheet.save(&sheet_path).map_err(|e| e.to_string())?;
        let bytes = fs::read(&sheet_path).map_err(|e| e.to_string())?;
        let hash = format!("{:x}", Sha256::digest(bytes));
        let manifest = serde_json::json!({"schemaVersion":1,"assetName":spec.asset_name,"frameCount":spec.frame_count,"columns":spec.columns,"rows":spec.rows,"cellWidth":spec.cell_width,"cellHeight":spec.cell_height,"padding":padding,"sheetWidth":spec.sheet_width,"sheetHeight":spec.sheet_height,"sheetSha256":hash});
        let manifest_path = staging.join("sprite-sheet.json");
        fs::write(
            &manifest_path,
            serde_json::to_vec_pretty(&manifest).map_err(|e| e.to_string())?,
        )
        .map_err(|e| e.to_string())?;
        fs::rename(&staging, &destination).map_err(|e| e.to_string())?;
        Ok(SpriteSheetResult {
            package_path: destination.to_string_lossy().into_owned(),
            sheet_path: destination
                .join(format!("{}_sheet.png", spec.asset_name))
                .to_string_lossy()
                .into_owned(),
            manifest_path: destination
                .join("sprite-sheet.json")
                .to_string_lossy()
                .into_owned(),
            frame_count: spec.frame_count,
            sheet_sha256: hash,
        })
    })();
    if result.is_err() {
        let _ = fs::remove_dir_all(&staging);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn builds_deterministic_sheet() {
        let d = tempfile::tempdir().unwrap();
        let root = d.path().join("artifacts/rgba/shared_canvas");
        fs::create_dir_all(&root).unwrap();
        for i in 0..3 {
            ImageBuffer::<Rgba<u8>, Vec<u8>>::from_pixel(8, 4, Rgba([i, 0, 0, 255]))
                .save(root.join(format!("frame_{i:06}.png")))
                .unwrap();
        }
        let r = execute(d.path(), "Dash", 2, 1).unwrap();
        assert_eq!(r.frame_count, 3);
        assert!(Path::new(&r.sheet_path).is_file());
        let manifest: serde_json::Value =
            serde_json::from_slice(&fs::read(r.manifest_path).unwrap()).unwrap();
        assert_eq!(manifest["rows"], 2);
        assert!(execute(d.path(), "Dash", 2, 1)
            .unwrap_err()
            .contains("already exists"));
    }
}
