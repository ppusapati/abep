//! P7 thermal closure (A9.38 priority 7, lane L-THERMAL): the frozen-topology DBF-1 thermal analysis run through the
//! admitted NP-THERMAL-CATHODELESS 2.0.0 network (`abep_subsystems::thermal::run_case_v2`, case class PARAMETRIC) under
//! the preregistration `docs/closure/thermal/thermal_cases_prereg_v1.json` (lock
//! `thermal_cases_prereg_lock_v1.json`), with versioned load inputs (`thermal_load_inputs_v<N>.json`).
//!
//! Physics stays in the thermal crate: this harness builds the registered cases, runs them, and compares the raw
//! temperatures with the registered limits under the DBF1-TH-03 rule (50 K below the limit with 1.2 x heat loads). A
//! node without an admissible limit gets a required capability, never an invented limit. Statuses fail closed: a run
//! that is not CONVERGED never yields a temperature.

pub mod assess;
pub mod build;
pub mod env;
pub mod loads;
pub mod record;

use abep_provenance::sha256_hex;
use abep_subsystems::thermal::{GovernedContextV2, RunContext};
use serde_json::Value;
use std::collections::BTreeMap;
use std::path::Path;
use std::sync::Mutex;

pub const PREREG_PATH: &str = "docs/closure/thermal/thermal_cases_prereg_v1.json";
pub const LOCK_PATH: &str = "docs/closure/thermal/thermal_cases_prereg_lock_v1.json";
pub const DESIGN_STATES_PATH: &str = "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json";
pub const DESIGN_STATES_SHA256: &str = "60073e214cf5edb92d7eacf70be1491ad29ff72f19db0ef3b96a4b30da6f4049";
pub const MARGIN_K: f64 = 50.0;

#[derive(Debug, Clone, PartialEq)]
pub struct ClosureError(pub String);

impl std::fmt::Display for ClosureError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

pub(crate) fn num(v: &Value, k: &str) -> Result<f64, ClosureError> {
    v[k].as_f64().ok_or_else(|| ClosureError(format!("missing number {k:?}")))
}

pub(crate) fn s(v: &Value, k: &str) -> Result<String, ClosureError> {
    v[k].as_str().map(String::from).ok_or_else(|| ClosureError(format!("missing string {k:?}")))
}

/// The verified preregistration with typed views of its network sections.
pub struct Prereg {
    pub raw: Value,
    pub sha256: String,
    pub model: Value,
    pub materials: BTreeMap<String, Value>,
    pub optics: BTreeMap<String, Value>,
    pub nodes: Vec<Value>,
    pub surfaces: Vec<Value>,
    pub enclosures: Vec<Value>,
    pub links: Vec<Value>,
    /// Validity range of every registered ranged scalar [K].
    pub range: (f64, f64),
    earth: Mutex<BTreeMap<(u8, u64), f64>>,
}

impl Prereg {
    pub fn from_bytes(bytes: &[u8]) -> Result<Prereg, ClosureError> {
        let raw: Value = serde_json::from_slice(bytes).map_err(|e| ClosureError(format!("prereg: {e}")))?;
        let obj = |k: &str| -> BTreeMap<String, Value> {
            raw[k].as_object().map(|m| m.iter().map(|(a, b)| (a.clone(), b.clone())).collect()).unwrap_or_default()
        };
        let arr = |k: &str| -> Vec<Value> { raw[k].as_array().cloned().unwrap_or_default() };
        Ok(Prereg {
            sha256: sha256_hex(bytes),
            model: raw["model"].clone(),
            materials: obj("materials"),
            optics: obj("optics"),
            nodes: arr("nodes"),
            surfaces: arr("surfaces"),
            enclosures: arr("enclosures"),
            links: arr("links"),
            range: (100.0, 1500.0),
            earth: Mutex::new(BTreeMap::new()),
            raw,
        })
    }

    /// Earth view factor per surface type and altitude (cached: the quadrature is the expensive part).
    pub fn earth_factor(&self, t: env::EnvType, alt_km: f64) -> f64 {
        let key = (t as u8, alt_km.to_bits());
        let mut m = self.earth.lock().expect("cache");
        *m.entry(key).or_insert_with(|| env::earth_factor(t, alt_km))
    }
}

/// Inputs of one closure run.
pub struct Context {
    pub prereg: Prereg,
    pub inputs: Value,
    pub inputs_path: String,
    pub inputs_sha256: String,
    pub lock_sha256: String,
    pub gov: GovernedContextV2,
    pub run: RunContext,
    /// Max design-state density per altitude [kg/m^3] (aerodynamic record; A_ram = 0).
    pub rho_max: BTreeMap<u64, f64>,
}

fn read(root: &Path, rel: &str) -> Result<Vec<u8>, ClosureError> {
    std::fs::read(root.join(rel)).map_err(|e| ClosureError(format!("{rel}: {e}")))
}

impl Context {
    /// Load and verify the preregistration (lock), the input file, the design states and the governed thermal context.
    pub fn load(root: &Path, inputs_rel: &str, run: RunContext) -> Result<Context, ClosureError> {
        let lock_bytes = read(root, LOCK_PATH)?;
        let lock: Value = serde_json::from_slice(&lock_bytes).map_err(|e| ClosureError(format!("lock: {e}")))?;
        let pre_bytes = read(root, PREREG_PATH)?;
        let pre_sha = sha256_hex(&pre_bytes);
        if lock["files"][PREREG_PATH].as_str() != Some(pre_sha.as_str()) {
            return Err(ClosureError(format!("{PREREG_PATH} sha256 {pre_sha} differs from the lock")));
        }
        let in_bytes = read(root, inputs_rel)?;
        let in_sha = sha256_hex(&in_bytes);
        if let Some(locked) = lock["files"][inputs_rel].as_str() {
            if locked != in_sha {
                return Err(ClosureError(format!("{inputs_rel} sha256 {in_sha} differs from the lock")));
            }
        }
        let inputs: Value = serde_json::from_slice(&in_bytes).map_err(|e| ClosureError(format!("inputs: {e}")))?;
        if inputs["prereg"].as_str() != Some(PREREG_PATH) {
            return Err(ClosureError("the input file does not name this preregistration".into()));
        }
        let ds_bytes = read(root, DESIGN_STATES_PATH)?;
        if sha256_hex(&ds_bytes) != DESIGN_STATES_SHA256 {
            return Err(ClosureError(format!("{DESIGN_STATES_PATH} sha256 mismatch")));
        }
        let ds: Value = serde_json::from_slice(&ds_bytes).map_err(|e| ClosureError(format!("design states: {e}")))?;
        let mut rho_max: BTreeMap<u64, f64> = BTreeMap::new();
        for st in ds["states"].as_array().cloned().unwrap_or_default() {
            if let (Some(a), Some(r)) = (st["alt_km"].as_f64(), st["rho_kg_m3"].as_f64()) {
                let e = rho_max.entry(a.to_bits()).or_insert(0.0);
                *e = e.max(r);
            }
        }
        let gov = GovernedContextV2::load(root).map_err(|e| ClosureError(format!("governed thermal context: {e}")))?;
        Ok(Context {
            prereg: Prereg::from_bytes(&pre_bytes)?,
            inputs,
            inputs_path: inputs_rel.to_string(),
            inputs_sha256: in_sha,
            lock_sha256: sha256_hex(&lock_bytes),
            gov,
            run,
            rho_max,
        })
    }

    pub fn rho(&self, alt_km: f64) -> Result<f64, ClosureError> {
        self.rho_max
            .get(&alt_km.to_bits())
            .copied()
            .ok_or_else(|| ClosureError(format!("no design state at {alt_km} km")))
    }
}
