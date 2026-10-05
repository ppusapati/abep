//! The complete 196-state execution of the frozen design-state set v2 (A9.29 sec. 6, RM-OQ-02; SC-WP-01).
//!
//! For every required state, in file order: the design layer's environment view (`DesignState::atm`), its provenance
//! record, the re-evaluation of the state from the frozen orbit dataset compared with the stored values under the
//! reference's DESIGN_V2_REL_TOL, and the frozen HWM14 v2 wind at the state (DESIGN_ENVELOPE_PARAMETRIC; not part of the
//! free-stream speed, V_REL_BASIS). Missing or altered frozen data is MODEL_ERROR for the whole run; a state outside
//! the accessor domain is OUT_OF_DOMAIN; a state the frozen dataset does not reproduce is MODEL_ERROR.

use crate::design_state_set::{required_states, DesignState, StateAtmosphere, StateRecord};
use crate::design_states::DESIGN_V2_REL_TOL;
use crate::orbit::OrbitAtmosphere;
use crate::wind::{Wind, WindAtmosphere};
use abep_data::design_states::{DesignStateSet, DESIGN_STATE_SET_ID};
use abep_data::hwm14_v2::{DATASET_ID as WIND_DATASET_ID, DATASET_STATUS as WIND_DATASET_STATUS};
use abep_data::orbit_v1::{ALT_KM, DOY, LAT_DEG, LON_DEG, LST_H};
use abep_types::{AbepError, AbepResult, EvalStatus};
use serde::Serialize;
use std::path::Path;

/// Every frozen input of the execution, loaded and verified.
#[derive(Debug, Clone)]
pub struct Environment {
    pub orbit: OrbitAtmosphere,
    pub wind: WindAtmosphere,
    pub set: DesignStateSet,
}

impl Environment {
    /// Load the design-state set (design-layer loader), the orbit dataset and the wind dataset, in the reference's
    /// order (`required_states()`, `atmosphere_orbit.load()`, `atmosphere_orbit_v2.load()`).
    pub fn load(repo_root: &Path) -> AbepResult<Environment> {
        let pins = abep_data::pins::FrozenPins::load(repo_root)?;
        let set = DesignStateSet::load(repo_root, &pins)?;
        let orbit = OrbitAtmosphere::load(repo_root)?;
        let wind = WindAtmosphere::load(repo_root, &orbit)?;
        Ok(Environment { orbit, wind, set })
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Reproduction {
    pub evaluation: String,
    /// max over the 15 stored thermodynamic fields of |a - b| / max(|a|, |b|) (reported, not a criterion).
    pub max_abs_rel_diff: f64,
    pub rel_tol: f64,
    pub reproduced: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct StateWind {
    #[serde(flatten)]
    pub wind: Wind,
    pub dataset_id: &'static str,
    pub dataset_status: &'static str,
    pub used_in_free_stream_velocity: bool,
}

/// One executed state.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct StateExecution {
    pub index: usize,
    pub state_id: String,
    pub status: EvalStatus,
    pub design_state: StateRecord,
    pub environment: Option<StateAtmosphere>,
    pub frozen_dataset_reproduction: Option<Reproduction>,
    pub wind: Option<StateWind>,
    pub error: Option<String>,
}

/// The execution of the whole set.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct DesignStateRun {
    pub design_state_set_id: &'static str,
    pub design_state_set_sha256: String,
    pub dataset_sha256: String,
    pub wind_dataset_sha256: String,
    pub wind_disturbance_sha256: String,
    pub config_manifest_sha256: String,
    pub model_set_sha256: String,
    pub n_states: usize,
    pub n_evaluated: usize,
    pub n_out_of_domain: usize,
    pub n_model_error: usize,
    pub records: Vec<StateExecution>,
}

fn rel_diff(a: f64, b: f64) -> f64 {
    if a == b {
        0.0
    } else if a.is_finite() && b.is_finite() {
        (a - b).abs() / a.abs().max(b.abs())
    } else {
        f64::INFINITY
    }
}

fn node(axis: &[f64], v: f64, what: &str) -> AbepResult<usize> {
    axis.iter()
        .position(|x| *x == v)
        .ok_or_else(|| AbepError::Model { message: format!("grid_node state has {what} = {v} off the grid") })
}

fn execute_one(
    env_orbit: &OrbitAtmosphere,
    wind: &WindAtmosphere,
    set: &DesignStateSet,
    index: usize,
    st: &DesignState,
) -> StateExecution {
    let mut rec = StateExecution {
        index,
        state_id: st.state_id.clone(),
        status: EvalStatus::Evaluated,
        design_state: st.record(),
        environment: None,
        frozen_dataset_reproduction: None,
        wind: None,
        error: None,
    };
    let result = (|| -> AbepResult<()> {
        rec.environment = Some(st.atm()?);
        let fresh = if st.evaluation == "grid_node" {
            let i_doy = node(&DOY, st.doy, "doy")?;
            let i_alt = node(&ALT_KM, st.alt_km, "alt_km")?;
            let i_lat = node(&LAT_DEG, st.lat_deg, "lat_deg")?;
            let i_lon = node(&LON_DEG, st.lon_deg, "lon_deg")?;
            let i_lst = node(&LST_H, st.lst_h, "lst_h")?;
            env_orbit.node_state(i_doy, i_alt, i_lat, i_lon, i_lst, &st.scenario)?
        } else {
            env_orbit.state(st.alt_km, st.lat_deg, st.lst_h, st.lon_deg, st.doy, &st.scenario)?
        };
        let stored = set.select(&st.state_id).ok_or_else(|| AbepError::Model {
            message: format!("state {} is not in the design-state set", st.state_id),
        })?;
        let d = stored.thermo.iter().zip(fresh.thermo()).map(|(a, b)| rel_diff(*a, b)).fold(0.0, f64::max);
        let reproduced = d <= DESIGN_V2_REL_TOL;
        rec.frozen_dataset_reproduction = Some(Reproduction {
            evaluation: fresh.evaluation.clone(),
            max_abs_rel_diff: d,
            rel_tol: DESIGN_V2_REL_TOL,
            reproduced,
        });
        let w = wind.wind(st.alt_km, st.lat_deg, st.lst_h, st.lon_deg, st.doy, &st.scenario)?;
        rec.wind = Some(StateWind {
            wind: w,
            dataset_id: WIND_DATASET_ID,
            dataset_status: WIND_DATASET_STATUS,
            used_in_free_stream_velocity: false,
        });
        if !reproduced {
            return Err(AbepError::Model {
                message: format!(
                    "state {} is not reproduced by the frozen dataset ({d:.3e} > DESIGN_V2_REL_TOL)",
                    st.state_id
                ),
            });
        }
        Ok(())
    })();
    if let Err(e) = result {
        rec.status = e.status();
        rec.error = Some(e.to_string());
    }
    rec
}

/// Execute `states` (in order) against the loaded environment.
pub fn execute_states(env: &Environment, states: &[DesignState]) -> Vec<StateExecution> {
    states.iter().enumerate().map(|(i, st)| execute_one(&env.orbit, &env.wind, &env.set, i, st)).collect()
}

/// Execute every required state of the loaded environment.
pub fn run(env: &Environment) -> AbepResult<DesignStateRun> {
    let states = required_states(&env.set)?;
    let records = execute_states(env, &states);
    let count = |s: EvalStatus| records.iter().filter(|r| r.status == s).count();
    Ok(DesignStateRun {
        design_state_set_id: DESIGN_STATE_SET_ID,
        design_state_set_sha256: env.set.sha256.clone(),
        dataset_sha256: env.orbit.data.meta.sha256.clone(),
        wind_dataset_sha256: env.wind.data.sha256.clone(),
        wind_disturbance_sha256: env.wind.data.disturbance_sha256.clone(),
        config_manifest_sha256: env.orbit.pins.config_manifest_sha256.clone(),
        model_set_sha256: env.orbit.pins.model_set_sha256.clone(),
        n_states: env.set.n_states,
        n_evaluated: count(EvalStatus::Evaluated),
        n_out_of_domain: count(EvalStatus::OutOfDomain),
        n_model_error: count(EvalStatus::ModelError),
        records,
    })
}

/// Load the frozen environment from `repo_root` and execute the complete design-state set.
pub fn run_design_state_set(repo_root: &Path) -> AbepResult<DesignStateRun> {
    run(&Environment::load(repo_root)?)
}
