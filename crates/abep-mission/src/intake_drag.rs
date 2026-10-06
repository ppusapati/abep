//! F1 intake-face drag per design state: `abep_sim/design/architecture_optimizer.py` drag_table
//! (PARITY-C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL-V1).
//!
//! Per (surface scenario, L/d, phi, state), the intake-face drag per unit frontal area from the committed F1 species
//! table (theta = 0):
//!
//! ```text
//! D/A = q sum_s w_s C_D,s,   SE/A = sqrt(sum_s (q w_s se_s)^2),   q = 1/2 rho V^2
//! ```
//!
//! with w_s the free-stream mass fractions of the frozen atmosphere at the state (the F1 candidate_state_metrics
//! expression). The F1 deliverable is read from its committed compact core view (sha256-pinned; only the species
//! table is expanded) and is never regenerated; its TPMC statistics are not recomputed. The surface scenario is a TBD
//! context axis, so every value is PARAMETRIC_SENSITIVITY_ONLY (EvalStatus INCOMPLETE_EVIDENCE), never EVALUATED.

use abep_atmos::design_state_set::required_states;
use abep_atmos::msis21::{atmosphere, Msis21Frozen, Solar};
use abep_atmos::pyfloat::{py_format_g, py_pow};
use abep_data::design_states::DesignStateSet;
use abep_data::pins::FrozenPins;
use abep_provenance::read_verified;
use abep_types::{AbepError, AbepResult, EvalStatus};
use serde_json::Value as Json;
use std::collections::HashMap;
use std::path::Path;

pub const F1_CORE_REL: &str = "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1_core.json";
pub const F1_CORE_SHA256: &str = "d397cb9348d06eafbe2e7cc3ee9ca035f97e8f423d63df8f42286ce75bc20854";
pub const F1_CORE_SCHEMA: &str = "f1_intake_synthesis_v1_core";
/// The design-case reference point (index 0 of the F1 states): frozen intake surface build state, 200 km, F10.7 150,
/// orbit-averaged atmosphere_msis21_v1. Not a member of the required design-state set (A9.14 S9.8).
pub const DESIGN_CASE_STATE_ID: &str = "h200_f150";
pub const DESIGN_CASE_ALT_KM: f64 = 200.0;
pub const DESIGN_CASE_F107: f64 = 150.0;
/// Status label of the F1 intake-face drag (reference vocabulary) and its EvalStatus.
pub const INTAKE_DRAG_LABEL: &str = "PARAMETRIC_SENSITIVITY_ONLY";
pub const INTAKE_DRAG_STATUS: EvalStatus = EvalStatus::IncompleteEvidence;

fn schema(msg: impl Into<String>) -> AbepError {
    AbepError::Schema { path: F1_CORE_REL.to_string(), message: msg.into() }
}

/// One theta-resolved row of the F1 species table (the columns drag_table reads).
#[derive(Debug, Clone, PartialEq)]
pub struct SpeciesRow {
    pub state_id: String,
    pub species: String,
    pub l_over_d: f64,
    pub phi: f64,
    pub alpha: f64,
    pub theta_deg: f64,
    pub scattering: String,
    pub c_d_species: f64,
    /// None where the deliverable has null (the reference then uses NaN)
    pub c_d_species_se: Option<f64>,
}

/// The F1 species table, expanded from the verified core view (`isy.expand_core`, species_table only).
#[derive(Debug, Clone)]
pub struct F1CoreSpeciesTable {
    pub orbit_states: Vec<String>,
    pub rows: Vec<SpeciesRow>,
}

fn f64_at(v: &Json, what: &str) -> AbepResult<f64> {
    v.as_f64().ok_or_else(|| schema(format!("{what}: number expected")))
}

impl F1CoreSpeciesTable {
    pub fn load(repo_root: &Path) -> AbepResult<Self> {
        let bytes = read_verified(&repo_root.join(F1_CORE_REL), F1_CORE_SHA256)?;
        let core: Json = serde_json::from_slice(&bytes).map_err(|e| schema(e.to_string()))?;
        Self::from_core(&core)
    }

    /// Expansion rule of `expand_core`: element 0 of an encoded row indexes `encoded.states`, the `source` column
    /// indexes `encoded.species_table.sources`, every other element is verbatim.
    pub fn from_core(core: &Json) -> AbepResult<Self> {
        if core.get("schema").and_then(Json::as_str) != Some(F1_CORE_SCHEMA) {
            return Err(AbepError::Model {
                message: format!("RuntimeError: not an F1 core view: schema {:?}", core.get("schema")),
            });
        }
        let strings = |v: Option<&Json>, what: &str| -> AbepResult<Vec<String>> {
            v.and_then(Json::as_array)
                .ok_or_else(|| schema(what.to_string()))?
                .iter()
                .map(|x| x.as_str().map(str::to_string).ok_or_else(|| schema(format!("{what}: string expected"))))
                .collect()
        };
        let states = strings(core.pointer("/encoded/states"), "encoded.states")?;
        let orbit_states = strings(core.pointer("/verbatim/coverage_rule/orbit_states"), "coverage_rule.orbit_states")?;
        let tab = core.pointer("/encoded/species_table").ok_or_else(|| schema("encoded.species_table"))?;
        let cols = strings(tab.get("columns"), "species_table.columns")?;
        let col = |name: &str| cols.iter().position(|c| c == name).ok_or_else(|| schema(format!("column {name}")));
        let (i_sp, i_ld, i_phi, i_al, i_th, i_sc, i_cd, i_se) = (
            col("species")?,
            col("L_over_d")?,
            col("phi")?,
            col("alpha")?,
            col("theta_deg")?,
            col("scattering")?,
            col("C_D_species")?,
            col("C_D_species_se")?,
        );
        if col("state_id")? != 0 {
            return Err(schema("state_id is not column 0"));
        }
        let rows_json = tab.get("rows").and_then(Json::as_array).ok_or_else(|| schema("species_table.rows"))?;
        let mut rows = Vec::with_capacity(rows_json.len());
        for r in rows_json {
            let r = r.as_array().ok_or_else(|| schema("row"))?;
            if r.len() != cols.len() {
                return Err(schema("row length"));
            }
            let si = r[0].as_u64().ok_or_else(|| schema("state index"))? as usize;
            let state_id = states.get(si).ok_or_else(|| schema("state index out of range"))?.clone();
            let s = |i: usize| r[i].as_str().map(str::to_string).ok_or_else(|| schema("string cell"));
            rows.push(SpeciesRow {
                state_id,
                species: s(i_sp)?,
                l_over_d: f64_at(&r[i_ld], "L_over_d")?,
                phi: f64_at(&r[i_phi], "phi")?,
                alpha: f64_at(&r[i_al], "alpha")?,
                theta_deg: f64_at(&r[i_th], "theta_deg")?,
                scattering: s(i_sc)?,
                c_d_species: f64_at(&r[i_cd], "C_D_species")?,
                c_d_species_se: if r[i_se].is_null() { None } else { Some(f64_at(&r[i_se], "C_D_species_se")?) },
            });
        }
        Ok(F1CoreSpeciesTable { orbit_states, rows })
    }
}

/// The free-stream quantities drag_table reads from one state's atmosphere.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct StateFreeStream {
    pub rho: f64,
    pub v: f64,
    pub f_o: f64,
    pub f_n2: f64,
    pub f_o2: f64,
}

/// The envelope states (`isy.envelope_states()`): the design-case reference h200_f150 first, then every required
/// state of the frozen design-state set v2, with their frozen atmospheres.
#[derive(Debug, Clone)]
pub struct EnvelopeAtmospheres {
    pub ids: Vec<String>,
    pub required_ids: Vec<String>,
    by_id: HashMap<String, StateFreeStream>,
}

impl EnvelopeAtmospheres {
    pub fn load(repo_root: &Path) -> AbepResult<Self> {
        let fz = Msis21Frozen::load(repo_root)?;
        let a = atmosphere(&fz, DESIGN_CASE_ALT_KM, Solar::F107(DESIGN_CASE_F107))?;
        if !a.source.starts_with("NRLMSIS 2.1 frozen scenario") {
            return Err(AbepError::Model {
                message: format!("RuntimeError: atmosphere for {DESIGN_CASE_STATE_ID} is not the frozen dataset"),
            });
        }
        let mut ids = vec![DESIGN_CASE_STATE_ID.to_string()];
        let mut by_id = HashMap::new();
        by_id.insert(
            DESIGN_CASE_STATE_ID.to_string(),
            StateFreeStream { rho: a.rho, v: a.V, f_o: a.fO, f_n2: a.fN2, f_o2: a.fO2 },
        );
        let pins = FrozenPins::load(repo_root)?;
        let set = DesignStateSet::load(repo_root, &pins)?;
        let mut required_ids = Vec::new();
        for st in required_states(&set)? {
            let x = st.atm()?;
            ids.push(st.state_id.clone());
            required_ids.push(st.state_id.clone());
            by_id.insert(
                st.state_id.clone(),
                StateFreeStream { rho: x.rho, v: x.V, f_o: x.fO, f_n2: x.fN2, f_o2: x.fO2 },
            );
        }
        Ok(EnvelopeAtmospheres { ids, required_ids, by_id })
    }

    pub fn get(&self, state_id: &str) -> Option<&StateFreeStream> {
        self.by_id.get(state_id)
    }
}

/// One drag_table entry.
#[derive(Debug, Clone, PartialEq)]
pub struct DragEntry {
    /// `<scattering>_a<alpha:g>`
    pub scenario: String,
    pub l_over_d: f64,
    pub phi: f64,
    pub state_id: String,
    /// intake-face drag per unit frontal area, N m^-2
    pub drag_per_area_n_m2: f64,
    /// its standard error, N m^-2
    pub drag_se_per_area_n_m2: f64,
}

/// drag_table result: entries in the reference's insertion order, with a key index.
#[derive(Debug, Clone)]
pub struct DragTable {
    pub entries: Vec<DragEntry>,
    index: HashMap<(String, u64, u64, String), usize>,
}

impl DragTable {
    pub fn get(&self, scenario: &str, l_over_d: f64, phi: f64, state_id: &str) -> Option<&DragEntry> {
        self.index
            .get(&(scenario.to_string(), l_over_d.to_bits(), phi.to_bits(), state_id.to_string()))
            .map(|&i| &self.entries[i])
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

/// Canonical key bits: Python dict keys compare floats by value (0.0 == -0.0).
fn key_bits(x: f64) -> u64 {
    if x == 0.0 {
        0
    } else {
        x.to_bits()
    }
}

/// `drag_table(f1)`: per-state intake-face drag per unit frontal area (theta 0), summed over the species rows in table
/// order; the SE is combined in quadrature. A state of the table without a frozen atmosphere is MODEL_ERROR (the
/// reference raises KeyError).
pub fn drag_table(table: &F1CoreSpeciesTable, atm: &EnvelopeAtmospheres) -> AbepResult<DragTable> {
    let mut entries: Vec<DragEntry> = Vec::new();
    let mut acc: Vec<(f64, f64)> = Vec::new();
    let mut index = HashMap::new();
    for r in &table.rows {
        if r.theta_deg != 0.0 {
            continue;
        }
        let a = atm.get(&r.state_id).ok_or_else(|| AbepError::Model {
            message: format!("KeyError: '{}' (no frozen atmosphere)", r.state_id),
        })?;
        let q = 0.5 * a.rho * py_pow(a.v, 2.0);
        let w = match r.species.as_str() {
            "O" => a.f_o,
            "N2" => a.f_n2,
            "O2" => a.f_o2,
            other => return Err(AbepError::Model { message: format!("KeyError: '{other}'") }),
        };
        let scenario = format!("{}_a{}", r.scattering, py_format_g(r.alpha));
        let key = (scenario.clone(), key_bits(r.l_over_d), key_bits(r.phi), r.state_id.clone());
        let i = *index.entry(key).or_insert_with(|| {
            entries.push(DragEntry {
                scenario,
                l_over_d: r.l_over_d,
                phi: r.phi,
                state_id: r.state_id.clone(),
                drag_per_area_n_m2: 0.0,
                drag_se_per_area_n_m2: 0.0,
            });
            acc.push((0.0, 0.0));
            entries.len() - 1
        });
        let se = r.c_d_species_se.unwrap_or(f64::NAN);
        let (d, v) = acc[i];
        acc[i] = (d + q * w * r.c_d_species, v + py_pow(q * w * se, 2.0));
    }
    for (e, (d, v)) in entries.iter_mut().zip(acc) {
        e.drag_per_area_n_m2 = d;
        e.drag_se_per_area_n_m2 = v.sqrt();
    }
    Ok(DragTable { entries, index })
}

/// Load the F1 core view and the envelope atmospheres from `repo_root` and evaluate drag_table.
pub fn load_drag_table(repo_root: &Path) -> AbepResult<(DragTable, EnvelopeAtmospheres)> {
    let table = F1CoreSpeciesTable::load(repo_root)?;
    let atm = EnvelopeAtmospheres::load(repo_root)?;
    if table.orbit_states != atm.ids {
        return Err(AbepError::Model {
            message:
                "RuntimeError: F1 deliverable was not evaluated on the current state set (design-case reference + \
                      the required states of the pinned design-state set v2)"
                    .into(),
        });
    }
    Ok((drag_table(&table, &atm)?, atm))
}
