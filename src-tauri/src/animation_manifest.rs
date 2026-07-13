//! Engine-neutral Animation Manifest v2 domain contract.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const ANIMATION_MANIFEST_SCHEMA_VERSION: u32 = 2;
pub const ANIMATION_MANIFEST_FILENAME: &str = "motionanchor-animation-v2.json";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AnimationManifestV2 {
    pub schema_version: u32,
    pub asset_name: String,
    pub frames: Vec<AnimationFrameV2>,
    pub frame_rate: f64,
    pub loop_animation: bool,
    pub canvas: CanvasSize,
    pub pivot: NormalizedPivot,
    pub pixels_per_unit: f64,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub events: Vec<AnimationEventV2>,
    #[serde(default)]
    pub provenance: BTreeMap<String, String>,
    #[serde(default)]
    pub content_hashes: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AnimationFrameV2 {
    pub index: usize,
    pub path: String,
    pub duration_ms: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CanvasSize { pub width: u32, pub height: u32 }

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct NormalizedPivot { pub space: String, pub x: f64, pub y: f64 }

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AnimationEventV2 { pub frame_index: usize, pub name: String }

impl AnimationManifestV2 {
    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != ANIMATION_MANIFEST_SCHEMA_VERSION { return Err("unsupported animation manifest schema version".into()); }
        if self.asset_name.trim().is_empty() { return Err("asset name is required".into()); }
        if !self.frame_rate.is_finite() || !(1.0..=240.0).contains(&self.frame_rate) { return Err("frame rate must be between 1 and 240".into()); }
        if self.frames.is_empty() { return Err("at least one animation frame is required".into()); }
        if self.canvas.width == 0 || self.canvas.height == 0 { return Err("canvas dimensions must be positive".into()); }
        if self.pivot.space != "normalized" || !(0.0..=1.0).contains(&self.pivot.x) || !(0.0..=1.0).contains(&self.pivot.y) { return Err("pivot must use normalized coordinates between 0 and 1".into()); }
        if !self.pixels_per_unit.is_finite() || self.pixels_per_unit <= 0.0 { return Err("pixels per unit must be positive".into()); }
        for (position, frame) in self.frames.iter().enumerate() {
            if frame.index != position + 1 { return Err("frame indexes must be contiguous and one-based".into()); }
            if frame.path.is_empty() || frame.path.starts_with('/') || frame.path.contains("..") || frame.path.contains('\\') { return Err("frame paths must be safe relative forward-slash paths".into()); }
            if !frame.duration_ms.is_finite() || frame.duration_ms <= 0.0 { return Err("frame duration must be positive".into()); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn validates_engine_neutral_manifest_contract() {
        let manifest = AnimationManifestV2 { schema_version: 2, asset_name: "dash".into(), frames: vec![AnimationFrameV2 { index: 1, path: "Frames/dash_frame_0001.png".into(), duration_ms: 1000.0 / 30.0 }], frame_rate: 30.0, loop_animation: true, canvas: CanvasSize { width: 64, height: 64 }, pivot: NormalizedPivot { space: "normalized".into(), x: 0.5, y: 0.0 }, pixels_per_unit: 100.0, tags: vec![], events: vec![], provenance: BTreeMap::new(), content_hashes: BTreeMap::new() };
        assert_eq!(manifest.validate(), Ok(()));
        let json = serde_json::to_value(&manifest).unwrap();
        assert_eq!(json["schemaVersion"], 2);
        assert!(json.get("engineProfile").is_none());
        assert!(json.get("unity").is_none());
    }
}
