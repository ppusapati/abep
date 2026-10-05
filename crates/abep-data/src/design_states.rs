//! The frozen design-state sets of `atmosphere_msis21_orbit_v1` (A9.14 S9.8 OD3; A9.17 ORBIT).
//!
//! * [`read_design_states_file`]: `abep_sim/atmosphere_orbit.py::load_design_states` (v2 current set, v1 immutable
//!   traceability set), hash-verified against the dataset sidecar records.
//! * [`DesignStateSet::load`]: `abep_sim/design/intake_synthesis.py::load_design_state_set`, the design layer's fail-closed
//!   loader of the 196-state set v2 (sha256 60073e21...).
//!
//! Both also verify the configuration pins (model set, design-state set reference).

use crate::json::OValue;
use crate::orbit_v1::{self, OrbitV1Meta, DATASET_ID, DESIGN_V1_FILE, DESIGN_V2_FILE, JSON_FILE};
use crate::pins::FrozenPins;
use crate::{data_path, data_rel};
use abep_provenance::{read_bytes, sha256_hex};
use abep_types::{AbepError, AbepResult};
use std::path::Path;

pub const DESIGN_STATE_SET_ID: &str = "atmosphere_msis21_orbit_v1_design_states_v2";
pub const DESIGN_STATE_SET_SHA256: &str = "60073e214cf5edb92d7eacf70be1491ad29ff72f19db0ef3b96a4b30da6f4049";
pub const DESIGN_STATE_DATASET_SHA256: &str = "c0ce282e99695be8cae0834270c5b9ff7853033255665abda7ec18c307566164";

/// A design-state file read by [`read_design_states_file`].
#[derive(Debug, Clone)]
pub struct DesignStatesFile {
    pub version: String,
    pub sha256: String,
    /// The verified file text (the returned document, key order as stored).
    pub text: String,
    pub doc: OValue,
}

fn model(message: impl Into<String>) -> AbepError {
    AbepError::Model { message: message.into() }
}

/// `atmosphere_orbit.load_design_states(version)` on an already loaded and verified dataset (`meta`).
pub fn read_design_states_file(
    repo_root: &Path,
    pins: &FrozenPins,
    meta: &OrbitV1Meta,
    version: &str,
) -> AbepResult<DesignStatesFile> {
    let (file, rec_sha) = match version {
        "v2" => {
            let r = meta.design_states_file_v2().and_then(|r| r.get("sha256")).and_then(|s| s.as_str());
            (DESIGN_V2_FILE, r.map(str::to_string))
        }
        "v1" => (DESIGN_V1_FILE, meta.design_states_file.as_ref().and_then(|r| r.sha256.clone())),
        _ => {
            return Err(AbepError::OutOfDomain {
                message: format!("design-state version {version:?} unknown (v1, v2)"),
            })
        }
    };
    let path = data_path(repo_root, file);
    if !path.exists() {
        return Err(AbepError::Io {
            path: path.display().to_string(),
            message: format!("{DATASET_ID} design-state file missing; there is no fallback dataset"),
        });
    }
    let rec_sha = rec_sha.ok_or_else(|| model(format!("design-state {version} is not recorded in {JSON_FILE}")))?;
    let raw = read_bytes(&path)?;
    let sha = sha256_hex(&raw);
    if sha != rec_sha {
        return Err(AbepError::HashMismatch { path: path.display().to_string(), expected: rec_sha, actual: sha });
    }
    let extra: Vec<&str> = if version == "v2" { vec![pins.design_state_set_ref.sha256.as_str()] } else { vec![] };
    pins.read_pinned(repo_root, &data_rel(file), &extra)?;
    let text = String::from_utf8(raw).map_err(|e| model(format!("{file}: not UTF-8: {e}")))?;
    let doc = OValue::parse(text.as_bytes(), file)?;
    if doc.get("dataset_sha256").and_then(|s| s.as_str()) != Some(meta.sha256.as_str()) {
        return Err(model("design-states file was produced from a different dataset"));
    }
    Ok(DesignStatesFile { version: version.to_string(), sha256: sha, text, doc })
}

/// One state of the set v2 as stored.
#[derive(Debug, Clone, PartialEq)]
pub struct DesignStateRecord {
    pub alt_km: f64,
    pub lat_deg: f64,
    pub lst_h: f64,
    pub lon_deg: f64,
    pub doy: f64,
    pub scenario: String,
    pub f107: f64,
    pub f107a: f64,
    pub ap: f64,
    /// rho_kg_m3, n_N2_m3, n_O2_m3, n_O_m3, n_He_m3, n_Ar_m3, n_N_m3, n_total_m3, T_K, x_O, x_N2, x_O2, x_N, x_He,
    /// x_Ar (THERMO_FIELDS order).
    pub thermo: [f64; 15],
    pub source: String,
    pub evaluation: String,
    pub interp_max_rel_err_rho: Option<f64>,
    pub labels: Vec<String>,
    pub state_id: String,
    pub required: bool,
    pub nominal_mission_scenario: bool,
}

pub const THERMO_FIELDS: [&str; 15] = [
    "rho_kg_m3",
    "n_N2_m3",
    "n_O2_m3",
    "n_O_m3",
    "n_He_m3",
    "n_Ar_m3",
    "n_N_m3",
    "n_total_m3",
    "T_K",
    "x_O",
    "x_N2",
    "x_O2",
    "x_N",
    "x_He",
    "x_Ar",
];

impl DesignStateRecord {
    pub fn thermo(&self, name: &str) -> f64 {
        self.thermo[THERMO_FIELDS.iter().position(|f| *f == name).expect("registered thermo field")]
    }
    pub fn rho_kg_m3(&self) -> f64 {
        self.thermo[0]
    }
    pub fn n_n2_m3(&self) -> f64 {
        self.thermo[1]
    }
    pub fn n_o2_m3(&self) -> f64 {
        self.thermo[2]
    }
    pub fn n_o_m3(&self) -> f64 {
        self.thermo[3]
    }
    pub fn t_k(&self) -> f64 {
        self.thermo[8]
    }
}

/// The frozen design-state set v2 loaded by the design layer.
#[derive(Debug, Clone)]
pub struct DesignStateSet {
    pub sha256: String,
    pub dataset_sha256: String,
    pub n_states: usize,
    pub states: Vec<DesignStateRecord>,
}

fn num(x: &OValue, key: &str, id: &str) -> AbepResult<f64> {
    x.get(key).and_then(OValue::as_f64).ok_or_else(|| model(format!("state {id}: {key} is not a number")))
}

fn text(x: &OValue, key: &str, id: &str) -> AbepResult<String> {
    x.get(key).and_then(OValue::as_str).map(str::to_string).ok_or_else(|| model(format!("state {id}: {key} missing")))
}

impl DesignStateSet {
    /// `intake_synthesis.load_design_state_set()`: file present, sha256 equal to the pin, the dataset sidecar records
    /// the same file hash and dataset hash, set id / version / count / unique ids, and every state carries the
    /// dataset provenance, lies in the mission-domain altitude band and has finite positive rho, n_O, n_N2, n_O2, T.
    /// Any failure is `MODEL_ERROR` (DesignStateSetError; no fallback state set).
    pub fn load(repo_root: &Path, pins: &FrozenPins) -> AbepResult<DesignStateSet> {
        for f in [DESIGN_V2_FILE, JSON_FILE] {
            if !data_path(repo_root, f).exists() {
                return Err(model(format!(
                    "{} missing: the design layer needs the frozen design-state set {DESIGN_STATE_SET_ID} \
                     (repository-only data); no fallback state set",
                    data_rel(f)
                )));
            }
        }
        let rel = data_rel(DESIGN_V2_FILE);
        let raw = read_bytes(&data_path(repo_root, DESIGN_V2_FILE))?;
        let sha = sha256_hex(&raw);
        if sha != DESIGN_STATE_SET_SHA256 {
            return Err(AbepError::HashMismatch { path: rel, expected: DESIGN_STATE_SET_SHA256.into(), actual: sha });
        }
        pins.read_pinned(repo_root, &rel, &[&pins.design_state_set_ref.sha256])?;
        let (meta, _) = orbit_v1::load_meta(repo_root, pins)?;
        let rec = meta.design_states_file_v2();
        let rec_sha = rec.and_then(|r| r.get("sha256")).and_then(OValue::as_str);
        let rec_file = rec.and_then(|r| r.get("file")).and_then(OValue::as_str);
        if rec_sha != Some(DESIGN_STATE_SET_SHA256) || rec_file != Some(DESIGN_V2_FILE) {
            return Err(model("dataset manifest does not record the pinned design-state set v2"));
        }
        if meta.sha256 != DESIGN_STATE_DATASET_SHA256 {
            return Err(model("dataset manifest sha256 differs from the pinned orbit dataset"));
        }
        let d = OValue::parse(&raw, &rel)?;
        let s = |k: &str| d.get(k).and_then(OValue::as_str);
        if s("design_state_set_id") != Some(DESIGN_STATE_SET_ID) || s("version") != Some("v2") {
            return Err(model("design-state set id / version mismatch"));
        }
        if s("dataset_id") != Some(DATASET_ID) || s("dataset_sha256") != Some(DESIGN_STATE_DATASET_SHA256) {
            return Err(model("design-state set was produced from a different dataset"));
        }
        let st = d.get("states").and_then(OValue::as_array).unwrap_or(&[]);
        let n_states = match d.get("n_states") {
            Some(OValue::Int(n)) if *n >= 0 && *n as usize == st.len() && !st.is_empty() => st.len(),
            _ => return Err(model("design-state set n_states inconsistent with its state list")),
        };
        let mut ids = std::collections::BTreeSet::new();
        for x in st {
            match x.get("state_id").and_then(OValue::as_str) {
                Some(id) if !id.is_empty() && ids.insert(id.to_string()) => {}
                _ => return Err(model("design-state ids missing or not unique")),
            }
        }
        let (lo, hi) = pins.mission_altitude_band_km;
        let mut states = Vec::with_capacity(st.len());
        for x in st {
            let id = x.get("state_id").and_then(OValue::as_str).unwrap_or_default().to_string();
            let source = x.get("source").and_then(OValue::as_str).unwrap_or_default();
            if !source.contains(DESIGN_STATE_DATASET_SHA256) {
                return Err(model(format!("state {id} does not carry the dataset provenance")));
            }
            let alt = num(x, "alt_km", &id)?;
            if !(lo <= alt && alt <= hi) {
                return Err(model(format!("state {id} outside the mission-domain altitude band ({lo}, {hi})")));
            }
            let required = x
                .get("required")
                .and_then(OValue::as_bool)
                .ok_or_else(|| model(format!("state {id} has no boolean 'required' flag")))?;
            for k in ["rho_kg_m3", "n_O_m3", "n_N2_m3", "n_O2_m3", "T_K"] {
                match x.get(k).and_then(OValue::as_f64) {
                    Some(v) if v.is_finite() && v > 0.0 => {}
                    _ => return Err(model(format!("state {id}: {k} is not a finite positive number"))),
                }
            }
            let mut thermo = [0.0; 15];
            for (i, k) in THERMO_FIELDS.iter().enumerate() {
                thermo[i] = num(x, k, &id)?;
            }
            let labels = x
                .get("labels")
                .and_then(OValue::as_array)
                .map(|a| a.iter().map(|l| l.as_str().map(str::to_string)).collect::<Option<Vec<_>>>())
                .unwrap_or(None)
                .ok_or_else(|| model(format!("state {id}: labels")))?;
            let interp = match x.get("interp_max_rel_err_rho") {
                None | Some(OValue::Null) => None,
                Some(v) => Some(v.as_f64().ok_or_else(|| model(format!("state {id}: interp_max_rel_err_rho")))?),
            };
            let nominal = x
                .get("nominal_mission_scenario")
                .and_then(OValue::as_bool)
                .ok_or_else(|| model(format!("state {id}: nominal_mission_scenario")))?;
            states.push(DesignStateRecord {
                alt_km: alt,
                lat_deg: num(x, "lat_deg", &id)?,
                lst_h: num(x, "lst_h", &id)?,
                lon_deg: num(x, "lon_deg", &id)?,
                doy: num(x, "doy", &id)?,
                scenario: text(x, "scenario", &id)?,
                f107: num(x, "f107", &id)?,
                f107a: num(x, "f107a", &id)?,
                ap: num(x, "ap", &id)?,
                thermo,
                source: source.to_string(),
                evaluation: text(x, "evaluation", &id)?,
                interp_max_rel_err_rho: interp,
                labels,
                state_id: id,
                required,
                nominal_mission_scenario: nominal,
            });
        }
        Ok(DesignStateSet {
            sha256: DESIGN_STATE_SET_SHA256.to_string(),
            dataset_sha256: meta.sha256,
            n_states,
            states,
        })
    }

    /// The state with `state_id`, if it is a member of the set.
    pub fn select(&self, state_id: &str) -> Option<&DesignStateRecord> {
        self.states.iter().find(|s| s.state_id == state_id)
    }
}
