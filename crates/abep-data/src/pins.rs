//! Hash pins of the frozen datasets.
//!
//! * `config/MANIFEST.json` pins `config/model_set/physics_model_set_v1.json`, whose `data[]` list pins every frozen
//!   data file by full sha256;
//! * `config/environment/design_state_set_ref_v1.json` pins the design-state set v2, the orbit dataset sidecar and
//!   the orbit dataset identity (uncompressed-CSV sha256);
//! * `config/constraints/engineering_constraints_v1.json` carries the mission-domain altitude band that the
//!   design-state set loader checks (A9.22 G5).

use abep_provenance::{read_bytes, sha256_hex, ConfigManifest};
use abep_types::{AbepError, AbepResult};
use serde::Deserialize;
use std::collections::BTreeMap;
use std::path::Path;

pub const MODEL_SET_REL: &str = "model_set/physics_model_set_v1.json";
pub const MODEL_SET_SCHEMA: &str = "abep_config_physics_model_set_v1";
pub const DESIGN_STATE_SET_REF_REL: &str = "environment/design_state_set_ref_v1.json";
pub const DESIGN_STATE_SET_REF_SCHEMA: &str = "abep_config_design_state_set_ref_v1";
pub const ENGINEERING_CONSTRAINTS_REL: &str = "constraints/engineering_constraints_v1.json";

#[derive(Deserialize)]
struct ModelSetFile {
    schema: String,
    data: Vec<ModelSetData>,
}

#[derive(Deserialize)]
struct ModelSetData {
    path: String,
    sha256: String,
}

/// `config/environment/design_state_set_ref_v1.json`.
#[derive(Debug, Clone, Deserialize)]
pub struct DesignStateSetRef {
    pub schema: String,
    pub id: String,
    pub path: String,
    pub sha256: String,
    pub n_states: u64,
    pub version: String,
    pub dataset_id: String,
    pub dataset_sha256: String,
    pub manifest: DesignStateSetRefManifest,
}

#[derive(Debug, Clone, Deserialize)]
pub struct DesignStateSetRefManifest {
    pub path: String,
    pub sha256: String,
    pub design_states_file_v2_sha256: String,
    pub dataset_sha256: String,
}

/// Every pin read from the configuration (verified against `config/MANIFEST.json` on load).
#[derive(Debug, Clone)]
pub struct FrozenPins {
    pub config_manifest_sha256: String,
    pub model_set_sha256: String,
    data: BTreeMap<String, String>,
    pub design_state_set_ref: DesignStateSetRef,
    pub design_state_set_ref_sha256: String,
    /// `constraints.altitude_band_km.value` (km).
    pub mission_altitude_band_km: (f64, f64),
}

fn schema_err(path: &str, message: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.to_string(), message: message.into() }
}

impl FrozenPins {
    /// Load and verify the pins of the repository at `repo_root`. Any configuration file that is missing, altered or
    /// of another schema is `MODEL_ERROR`.
    pub fn load(repo_root: &Path) -> AbepResult<FrozenPins> {
        let manifest = ConfigManifest::load(repo_root)?;
        let config_manifest_sha256 = sha256_hex(&read_bytes(&repo_root.join("config").join("MANIFEST.json"))?);

        let ms_bytes = manifest.read_verified(repo_root, MODEL_SET_REL)?;
        let ms: ModelSetFile = serde_json::from_slice(&ms_bytes)
            .map_err(|e| schema_err(&format!("config/{MODEL_SET_REL}"), e.to_string()))?;
        if ms.schema != MODEL_SET_SCHEMA {
            return Err(schema_err(&format!("config/{MODEL_SET_REL}"), format!("schema {:?}", ms.schema)));
        }
        let mut data = BTreeMap::new();
        for d in ms.data {
            if data.insert(d.path.clone(), d.sha256).is_some() {
                return Err(schema_err(&format!("config/{MODEL_SET_REL}"), format!("{} pinned twice", d.path)));
            }
        }

        let ref_bytes = manifest.read_verified(repo_root, DESIGN_STATE_SET_REF_REL)?;
        let dss: DesignStateSetRef = serde_json::from_slice(&ref_bytes)
            .map_err(|e| schema_err(&format!("config/{DESIGN_STATE_SET_REF_REL}"), e.to_string()))?;
        if dss.schema != DESIGN_STATE_SET_REF_SCHEMA {
            return Err(schema_err(&format!("config/{DESIGN_STATE_SET_REF_REL}"), format!("schema {:?}", dss.schema)));
        }
        if dss.sha256 != dss.manifest.design_states_file_v2_sha256 || dss.dataset_sha256 != dss.manifest.dataset_sha256
        {
            return Err(schema_err(&format!("config/{DESIGN_STATE_SET_REF_REL}"), "internally inconsistent pins"));
        }

        let ec_bytes = manifest.read_verified(repo_root, ENGINEERING_CONSTRAINTS_REL)?;
        let ec = crate::json::OValue::parse(&ec_bytes, ENGINEERING_CONSTRAINTS_REL)?;
        let band = ec
            .get("constraints")
            .and_then(|c| c.get("altitude_band_km"))
            .and_then(|a| a.get("value"))
            .and_then(|v| v.as_array())
            .filter(|v| v.len() == 2)
            .and_then(|v| Some((v[0].as_f64()?, v[1].as_f64()?)))
            .ok_or_else(|| {
                schema_err(&format!("config/{ENGINEERING_CONSTRAINTS_REL}"), "constraints.altitude_band_km.value")
            })?;

        Ok(FrozenPins {
            config_manifest_sha256,
            model_set_sha256: sha256_hex(&ms_bytes),
            data,
            design_state_set_ref: dss,
            design_state_set_ref_sha256: sha256_hex(&ref_bytes),
            mission_altitude_band_km: band,
        })
    }

    /// The model-set pin of a repository-relative data path.
    pub fn pin(&self, rel: &str) -> AbepResult<&str> {
        self.data.get(rel).map(|s| s.as_str()).ok_or_else(|| AbepError::Schema {
            path: rel.to_string(),
            message: format!("not pinned in config/{MODEL_SET_REL}"),
        })
    }

    /// Read a frozen data file and verify it against its model-set pin and every `extra` pin (sha256 hex).
    pub fn read_pinned(&self, repo_root: &Path, rel: &str, extra: &[&str]) -> AbepResult<Vec<u8>> {
        let pin = self.pin(rel)?.to_string();
        let path = repo_root.join(rel);
        let bytes = read_bytes(&path)?;
        let actual = sha256_hex(&bytes);
        for expected in std::iter::once(pin.as_str()).chain(extra.iter().copied()) {
            if actual != expected {
                return Err(AbepError::HashMismatch {
                    path: path.display().to_string(),
                    expected: expected.to_string(),
                    actual,
                });
            }
        }
        Ok(bytes)
    }
}
