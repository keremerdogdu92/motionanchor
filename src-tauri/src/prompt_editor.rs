/// src-tauri/src/prompt_editor.rs
/// Secure prompt JSON persistence and frame-by-index preview loading for the visual editor.
use base64::{engine::general_purpose::STANDARD, Engine as _};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

const MAX_PROMPT_BYTES: u64 = 2 * 1024 * 1024;
const MAX_ANCHORS: usize = 512;
const MAX_POINTS_PER_KIND: usize = 2048;

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct PromptDocument {
    schema_version: String,
    object_id: u32,
    anchors: Vec<PromptAnchor>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct PromptAnchor {
    frame_index: usize,
    #[serde(rename = "box")]
    box_: Option<[f64; 4]>,
    positive: Vec<[f64; 2]>,
    negative: Vec<[f64; 2]>,
}

#[derive(Debug, Deserialize)]
struct FrameManifestEntry {
    index: usize,
    timestamp_seconds: f64,
    filename: String,
}

#[derive(Debug, Serialize)]
pub struct EditorFramePreview {
    index: usize,
    timestamp_seconds: f64,
    filename: String,
    data_url: String,
    width: u32,
    height: u32,
}

pub fn load_prompt(path: &str) -> Result<PromptDocument, String> {
    let path = canonical_file(path, "prompt JSON")?;
    let metadata =
        fs::metadata(&path).map_err(|error| format!("could not inspect prompt JSON: {error}"))?;
    if metadata.len() > MAX_PROMPT_BYTES {
        return Err("prompt JSON exceeds the 2 MB safety limit".into());
    }
    let bytes = fs::read(&path).map_err(|error| format!("could not read prompt JSON: {error}"))?;
    let mut document: PromptDocument =
        serde_json::from_slice(&bytes).map_err(|error| format!("invalid prompt JSON: {error}"))?;
    normalize_and_validate(&mut document)?;
    Ok(document)
}

pub fn save_prompt(path: &str, mut document: PromptDocument) -> Result<(), String> {
    normalize_and_validate(&mut document)?;
    let target = PathBuf::from(path);
    let parent = target
        .parent()
        .ok_or_else(|| "prompt path must have a parent directory".to_string())?;
    let parent = parent
        .canonicalize()
        .map_err(|error| format!("invalid prompt directory: {error}"))?;
    if !parent.is_dir() {
        return Err("prompt parent path must be a directory".into());
    }
    let filename = target
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or_else(|| "prompt filename is invalid".to_string())?;
    if !filename.to_ascii_lowercase().ends_with(".json")
        || Path::new(filename)
            .file_name()
            .and_then(|value| value.to_str())
            != Some(filename)
    {
        return Err("prompt filename must be a plain .json filename".into());
    }
    let bytes = serde_json::to_vec_pretty(&document)
        .map_err(|error| format!("could not serialize prompt JSON: {error}"))?;
    if bytes.len() as u64 > MAX_PROMPT_BYTES {
        return Err("prompt JSON exceeds the 2 MB safety limit".into());
    }
    let destination = parent.join(filename);
    let temporary = parent.join(format!(".{filename}.tmp"));
    fs::write(&temporary, bytes)
        .map_err(|error| format!("could not write temporary prompt JSON: {error}"))?;
    if destination.exists() {
        fs::remove_file(&destination)
            .map_err(|error| format!("could not replace prompt JSON: {error}"))?;
    }
    fs::rename(&temporary, &destination)
        .map_err(|error| format!("could not publish prompt JSON atomically: {error}"))?;
    Ok(())
}

pub fn load_frame(frames_path: &str, frame_index: usize) -> Result<EditorFramePreview, String> {
    let root = PathBuf::from(frames_path)
        .canonicalize()
        .map_err(|error| format!("invalid frames directory: {error}"))?;
    if !root.is_dir() {
        return Err("frames path must be a directory".into());
    }
    let manifest = fs::read(root.join("frames.json"))
        .map_err(|error| format!("could not read frame manifest: {error}"))?;
    let entries: Vec<FrameManifestEntry> = serde_json::from_slice(&manifest)
        .map_err(|error| format!("invalid frame manifest: {error}"))?;
    let entry = entries
        .iter()
        .find(|entry| entry.index == frame_index)
        .ok_or_else(|| format!("frame index {frame_index} is not present in frames.json"))?;
    validate_frame_filename(&entry.filename)?;
    let frame_path = root
        .join(&entry.filename)
        .canonicalize()
        .map_err(|error| format!("invalid frame path: {error}"))?;
    if frame_path.parent() != Some(root.as_path()) {
        return Err("frame path escaped the frames directory".into());
    }
    let bytes =
        fs::read(&frame_path).map_err(|error| format!("could not read frame image: {error}"))?;
    let (width, height) = png_dimensions(&bytes)?;
    Ok(EditorFramePreview {
        index: entry.index,
        timestamp_seconds: entry.timestamp_seconds,
        filename: entry.filename.clone(),
        data_url: format!("data:image/png;base64,{}", STANDARD.encode(&bytes)),
        width,
        height,
    })
}

fn canonical_file(path: &str, label: &str) -> Result<PathBuf, String> {
    let path = PathBuf::from(path)
        .canonicalize()
        .map_err(|error| format!("invalid {label} path: {error}"))?;
    if !path.is_file() {
        return Err(format!("{label} path must be a file"));
    }
    Ok(path)
}

fn normalize_and_validate(document: &mut PromptDocument) -> Result<(), String> {
    if document.schema_version != "1.0" {
        return Err("unsupported prompt schema_version; expected 1.0".into());
    }
    if document.object_id == 0 {
        return Err("object_id must be greater than zero".into());
    }
    if document.anchors.is_empty() || document.anchors.len() > MAX_ANCHORS {
        return Err(format!("anchors must contain 1 to {MAX_ANCHORS} entries"));
    }
    document.anchors.sort_by_key(|anchor| anchor.frame_index);
    for pair in document.anchors.windows(2) {
        if pair[0].frame_index == pair[1].frame_index {
            return Err(format!(
                "duplicate anchor frame_index {}",
                pair[0].frame_index
            ));
        }
    }
    for anchor in &document.anchors {
        if anchor.box_.is_none() && anchor.positive.is_empty() {
            return Err(format!(
                "anchor {} requires a box or positive point",
                anchor.frame_index
            ));
        }
        if anchor.positive.len() > MAX_POINTS_PER_KIND
            || anchor.negative.len() > MAX_POINTS_PER_KIND
        {
            return Err("anchor point count exceeds the safety limit".into());
        }
        if let Some([x1, y1, x2, y2]) = anchor.box_ {
            if !(x1.is_finite()
                && y1.is_finite()
                && x2.is_finite()
                && y2.is_finite()
                && x2 > x1
                && y2 > y1)
            {
                return Err(format!("anchor {} has an invalid box", anchor.frame_index));
            }
        }
        if anchor
            .positive
            .iter()
            .chain(anchor.negative.iter())
            .flatten()
            .any(|value| !value.is_finite() || *value < 0.0)
        {
            return Err(format!(
                "anchor {} has an invalid point",
                anchor.frame_index
            ));
        }
    }
    Ok(())
}

fn validate_frame_filename(filename: &str) -> Result<(), String> {
    let valid = Path::new(filename)
        .file_name()
        .and_then(|value| value.to_str())
        == Some(filename)
        && filename.starts_with("frame_")
        && filename.ends_with(".png");
    if !valid {
        return Err("frame manifest contains an invalid filename".into());
    }
    Ok(())
}

fn png_dimensions(bytes: &[u8]) -> Result<(u32, u32), String> {
    if bytes.len() < 24 || &bytes[..8] != b"\x89PNG\r\n\x1a\n" || &bytes[12..16] != b"IHDR" {
        return Err("frame preview is not a valid PNG".into());
    }
    let width = u32::from_be_bytes(bytes[16..20].try_into().expect("PNG width slice"));
    let height = u32::from_be_bytes(bytes[20..24].try_into().expect("PNG height slice"));
    if width == 0 || height == 0 {
        return Err("frame preview has invalid dimensions".into());
    }
    Ok((width, height))
}
