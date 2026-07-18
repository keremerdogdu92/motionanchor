use base64::{engine::general_purpose::STANDARD, Engine as _};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

const MAX_PREVIEWS: usize = 12;
const MAX_TOTAL_BYTES: usize = 12 * 1024 * 1024;

#[derive(Debug, Deserialize)]
struct FrameManifestEntry {
    index: usize,
    timestamp_seconds: f64,
    filename: String,
}

#[derive(Debug, Deserialize)]
struct MotionManifestEntry {
    index: usize,
    source_index: usize,
    filename: String,
}

#[derive(Debug, Deserialize)]
struct MotionManifest {
    frames: Vec<MotionManifestEntry>,
}

#[derive(Debug, Serialize)]
pub struct FramePreview {
    pub index: usize,
    pub timestamp_seconds: f64,
    pub filename: String,
    pub data_url: String,
}

fn selected_positions(total: usize, requested: usize) -> Vec<usize> {
    let count = requested.clamp(1, MAX_PREVIEWS).min(total);
    if count == 0 {
        return Vec::new();
    }
    if count == 1 {
        return vec![0];
    }
    (0..count)
        .map(|slot| slot * (total - 1) / (count - 1))
        .collect()
}

pub fn load_frame_previews(
    output_path: &str,
    requested: usize,
) -> Result<Vec<FramePreview>, String> {
    let root = PathBuf::from(output_path)
        .canonicalize()
        .map_err(|error| format!("invalid preview output path: {error}"))?;
    if !root.is_dir() {
        return Err("preview output path must be a directory".into());
    }

    let manifest_path = root.join("frames.json");
    let manifest_bytes = fs::read(&manifest_path)
        .map_err(|error| format!("could not read frame manifest: {error}"))?;
    let entries: Vec<FrameManifestEntry> = serde_json::from_slice(&manifest_bytes)
        .map_err(|error| format!("invalid frame manifest: {error}"))?;
    if entries.is_empty() {
        return Err("frame manifest is empty".into());
    }

    let mut total_bytes = 0usize;
    let mut previews = Vec::new();
    for position in selected_positions(entries.len(), requested) {
        let entry = &entries[position];
        validate_filename(&entry.filename)?;
        let frame_path = root
            .join(&entry.filename)
            .canonicalize()
            .map_err(|error| format!("invalid frame path: {error}"))?;
        if frame_path.parent() != Some(root.as_path()) {
            return Err("frame path escaped the output directory".into());
        }
        let bytes = fs::read(&frame_path)
            .map_err(|error| format!("could not read frame preview: {error}"))?;
        total_bytes = total_bytes.saturating_add(bytes.len());
        if total_bytes > MAX_TOTAL_BYTES {
            return Err("frame previews exceeded the safety limit".into());
        }
        previews.push(FramePreview {
            index: entry.index,
            timestamp_seconds: entry.timestamp_seconds,
            filename: entry.filename.clone(),
            data_url: format!("data:image/png;base64,{}", STANDARD.encode(bytes)),
        });
    }
    Ok(previews)
}

pub fn load_motion_previews(
    output_path: &str,
    requested: usize,
) -> Result<Vec<FramePreview>, String> {
    let root = PathBuf::from(output_path)
        .canonicalize()
        .map_err(|error| format!("invalid motion preview path: {error}"))?;
    let bytes = fs::read(root.join("motion-selection.json"))
        .map_err(|error| format!("could not read motion manifest: {error}"))?;
    let manifest: MotionManifest = serde_json::from_slice(&bytes)
        .map_err(|error| format!("invalid motion manifest: {error}"))?;
    if manifest.frames.is_empty() {
        return Err("motion manifest is empty".into());
    }
    let mut total_bytes = 0usize;
    let mut previews = Vec::new();
    for position in selected_positions(manifest.frames.len(), requested) {
        let entry = &manifest.frames[position];
        validate_filename(&entry.filename)?;
        let frame_path = root
            .join(&entry.filename)
            .canonicalize()
            .map_err(|error| format!("invalid motion frame path: {error}"))?;
        if frame_path.parent() != Some(root.as_path()) {
            return Err("motion frame path escaped output directory".into());
        }
        let frame_bytes = fs::read(&frame_path)
            .map_err(|error| format!("could not read motion preview: {error}"))?;
        total_bytes = total_bytes.saturating_add(frame_bytes.len());
        if total_bytes > MAX_TOTAL_BYTES {
            return Err("motion previews exceeded the safety limit".into());
        }
        previews.push(FramePreview {
            index: entry.source_index,
            timestamp_seconds: 0.0,
            filename: entry.filename.clone(),
            data_url: format!("data:image/png;base64,{}", STANDARD.encode(frame_bytes)),
        });
    }
    Ok(previews)
}

pub fn load_rgba_previews(
    output_path: &str,
    requested: usize,
) -> Result<Vec<FramePreview>, String> {
    let root = PathBuf::from(output_path)
        .canonicalize()
        .map_err(|error| format!("invalid RGBA output path: {error}"))?;
    let rgba_root = root
        .join("rgba")
        .canonicalize()
        .map_err(|error| format!("invalid RGBA frame directory: {error}"))?;
    if !rgba_root.is_dir() || rgba_root.parent() != Some(root.as_path()) {
        return Err("RGBA frame directory is invalid".into());
    }
    let mut paths: Vec<PathBuf> = fs::read_dir(&rgba_root)
        .map_err(|error| format!("could not read RGBA directory: {error}"))?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| name.starts_with("frame_") && name.ends_with(".png"))
        })
        .collect();
    paths.sort();
    if paths.is_empty() {
        return Err("RGBA output contains no frame PNG files".into());
    }
    let mut total_bytes = 0usize;
    let mut previews = Vec::new();
    for position in selected_positions(paths.len(), requested) {
        let path = paths[position]
            .canonicalize()
            .map_err(|error| format!("invalid RGBA frame path: {error}"))?;
        if path.parent() != Some(rgba_root.as_path()) {
            return Err("RGBA frame path escaped the output directory".into());
        }
        let filename = path
            .file_name()
            .and_then(|name| name.to_str())
            .ok_or_else(|| "RGBA frame filename is invalid".to_string())?;
        validate_filename(filename)?;
        let bytes =
            fs::read(&path).map_err(|error| format!("could not read RGBA preview: {error}"))?;
        total_bytes = total_bytes.saturating_add(bytes.len());
        if total_bytes > MAX_TOTAL_BYTES {
            return Err("RGBA previews exceeded the safety limit".into());
        }
        previews.push(FramePreview {
            index: position,
            timestamp_seconds: 0.0,
            filename: filename.to_string(),
            data_url: format!("data:image/png;base64,{}", STANDARD.encode(bytes)),
        });
    }
    Ok(previews)
}

fn validate_filename(filename: &str) -> Result<(), String> {
    let path = Path::new(filename);
    let valid_name = path.file_name().and_then(|value| value.to_str()) == Some(filename);
    if !valid_name || !filename.starts_with("frame_") || !filename.ends_with(".png") {
        return Err("frame manifest contains an invalid filename".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn fixture_root(name: &str) -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        std::env::temp_dir().join(format!("motionanchor-{name}-{nonce}"))
    }

    #[test]
    fn selects_evenly_spaced_positions() {
        assert_eq!(selected_positions(10, 4), vec![0, 3, 6, 9]);
        assert_eq!(selected_positions(3, 8), vec![0, 1, 2]);
    }

    #[test]
    fn loads_bounded_data_urls() {
        let root = fixture_root("previews");
        fs::create_dir_all(&root).expect("create fixture");
        let mut manifest = Vec::new();
        for index in 0..4 {
            let filename = format!("frame_{index:06}.png");
            fs::write(root.join(&filename), [137, 80, 78, 71]).expect("write frame");
            manifest.push(serde_json::json!({
                "index": index,
                "timestamp_seconds": index as f64 / 24.0,
                "filename": filename
            }));
        }
        fs::write(
            root.join("frames.json"),
            serde_json::to_vec(&manifest).unwrap(),
        )
        .expect("write manifest");
        let previews = load_frame_previews(root.to_str().unwrap(), 3).expect("load previews");
        assert_eq!(previews.len(), 3);
        assert!(previews[0].data_url.starts_with("data:image/png;base64,"));
        fs::remove_dir_all(root).expect("clean fixture");
    }

    #[test]
    fn loads_rgba_previews_from_nested_output() {
        let root = fixture_root("rgba-previews");
        let rgba = root.join("rgba");
        fs::create_dir_all(&rgba).expect("create RGBA fixture");
        for index in 0..4 {
            fs::write(
                rgba.join(format!("frame_{index:06}.png")),
                [137, 80, 78, 71],
            )
            .expect("write RGBA frame");
        }
        let previews = load_rgba_previews(root.to_str().unwrap(), 3).expect("load RGBA previews");
        assert_eq!(previews.len(), 3);
        assert!(previews[0].data_url.starts_with("data:image/png;base64,"));
        fs::remove_dir_all(root).expect("clean RGBA fixture");
    }

    #[test]
    fn rejects_manifest_path_traversal() {
        assert!(validate_filename("../frame_000001.png").is_err());
    }
}
