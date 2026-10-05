//! The design layer's view of the frozen design-state set v2 (`abep_sim/design/intake_synthesis.py`: DesignState,
//! `_design_state`, `atm`, `record`, `required_states`): the per-state environment the downstream chain consumes.
//! Free-stream speed is the circular inertial orbital speed (V_REL_BASIS); co-rotation and winds are not included.

use crate::msis21::orbital_velocity;
use abep_data::design_states::{DesignStateRecord, DesignStateSet, DESIGN_STATE_SET_ID, DESIGN_STATE_SET_SHA256};
use abep_types::constants::{K_B, M_N2, M_O, M_O2};
use abep_types::{AbepError, AbepResult};
use serde::Serialize;

pub const ORBIT_BASIS_LABEL: &str = "BROAD_ENVELOPE_ALL_INCLINATIONS_ALL_LTAN_NOT_MISSION_ICD";
pub const V_REL_BASIS: &str = "V_ORB_INERTIAL_CIRCULAR: free-stream speed = circular inertial orbital speed sqrt(mu / \
(R_E + h)) at the state altitude (abep_sim.atmosphere.orbital_velocity, the F1 convention since A9.7); Earth co-rotation \
and thermospheric winds are NOT included (they depend on the TBD inclination / LTAN; the set carries no relative \
velocity)";

/// One state of the set (`intake_synthesis.DesignState`).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct DesignState {
    pub state_id: String,
    pub alt_km: f64,
    pub scenario: String,
    pub f107: f64,
    pub f107a: f64,
    pub ap: f64,
    pub lat_deg: f64,
    pub lst_h: f64,
    pub lon_deg: f64,
    pub doy: f64,
    pub rho_kg_m3: f64,
    #[serde(rename = "n_O_m3")]
    pub n_o_m3: f64,
    #[serde(rename = "n_N2_m3")]
    pub n_n2_m3: f64,
    #[serde(rename = "n_O2_m3")]
    pub n_o2_m3: f64,
    #[serde(rename = "T_K")]
    pub t_k: f64,
    pub labels: Vec<String>,
    pub evaluation: String,
    pub interp_max_rel_err_rho: Option<f64>,
    pub nominal_mission_scenario: bool,
    pub required: bool,
}

/// `DesignState.atm()` (field order = the reference dict order).
#[derive(Debug, Clone, PartialEq, Serialize)]
#[allow(non_snake_case)]
pub struct StateAtmosphere {
    pub alt_km: f64,
    pub f107: f64,
    pub f107a: f64,
    pub ap: f64,
    pub rho: f64,
    pub fO: f64,
    pub fN2: f64,
    pub fO2: f64,
    pub m_mean: f64,
    pub n: f64,
    pub T: f64,
    pub V: f64,
    pub flux_kg_m2_s: f64,
    pub p_ambient_Pa: f64,
    pub n_O: f64,
    pub state_id: String,
    pub source: String,
    pub V_basis: &'static str,
    pub orbit_basis: &'static str,
}

/// `DesignState.record()` (compact provenance record).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct StateRecord {
    pub state_id: String,
    pub scenario: String,
    pub alt_km: f64,
    pub lat_deg: f64,
    pub lst_h: f64,
    pub lon_deg: f64,
    pub doy: f64,
    pub f107: f64,
    pub ap: f64,
    pub labels: Vec<String>,
    pub evaluation: String,
    pub interp_max_rel_err_rho: Option<f64>,
    pub nominal_mission_scenario: bool,
}

impl DesignState {
    /// `_design_state(x)`.
    pub fn from_record(x: &DesignStateRecord) -> DesignState {
        DesignState {
            state_id: x.state_id.clone(),
            alt_km: x.alt_km,
            scenario: x.scenario.clone(),
            f107: x.f107,
            f107a: x.f107a,
            ap: x.ap,
            lat_deg: x.lat_deg,
            lst_h: x.lst_h,
            lon_deg: x.lon_deg,
            doy: x.doy,
            rho_kg_m3: x.rho_kg_m3(),
            n_o_m3: x.n_o_m3(),
            n_n2_m3: x.n_n2_m3(),
            n_o2_m3: x.n_o2_m3(),
            t_k: x.t_k(),
            labels: x.labels.clone(),
            evaluation: x.evaluation.clone(),
            interp_max_rel_err_rho: x.interp_max_rel_err_rho,
            nominal_mission_scenario: x.nominal_mission_scenario,
            required: x.required,
        }
    }

    /// `DesignState.atm()`: mass fractions of O, N2, O2 renormalised over those three, rho the stored total mass
    /// density, n = rho / m_mean, V the circular inertial orbital speed.
    pub fn atm(&self) -> AbepResult<StateAtmosphere> {
        let (m_o, m_n2, m_o2) = (self.n_o_m3 * M_O, self.n_n2_m3 * M_N2, self.n_o2_m3 * M_O2);
        let tot = m_o + m_n2 + m_o2;
        let (f_o, f_n2, f_o2) = (m_o / tot, m_n2 / tot, m_o2 / tot);
        let m_mean = 1.0 / (f_o / M_O + f_n2 / M_N2 + f_o2 / M_O2);
        let rho = self.rho_kg_m3;
        let n = rho / m_mean;
        let v = orbital_velocity(self.alt_km)?;
        Ok(StateAtmosphere {
            alt_km: self.alt_km,
            f107: self.f107,
            f107a: self.f107a,
            ap: self.ap,
            rho,
            fO: f_o,
            fN2: f_n2,
            fO2: f_o2,
            m_mean,
            n,
            T: self.t_k,
            V: v,
            flux_kg_m2_s: rho * v,
            p_ambient_Pa: n * K_B * self.t_k,
            n_O: rho * f_o / M_O,
            state_id: self.state_id.clone(),
            source: format!("{DESIGN_STATE_SET_ID} sha256 {DESIGN_STATE_SET_SHA256} state {}", self.state_id),
            V_basis: V_REL_BASIS,
            orbit_basis: ORBIT_BASIS_LABEL,
        })
    }

    /// `DesignState.record()`.
    pub fn record(&self) -> StateRecord {
        StateRecord {
            state_id: self.state_id.clone(),
            scenario: self.scenario.clone(),
            alt_km: self.alt_km,
            lat_deg: self.lat_deg,
            lst_h: self.lst_h,
            lon_deg: self.lon_deg,
            doy: self.doy,
            f107: self.f107,
            ap: self.ap,
            labels: self.labels.clone(),
            evaluation: self.evaluation.clone(),
            interp_max_rel_err_rho: self.interp_max_rel_err_rho,
            nominal_mission_scenario: self.nominal_mission_scenario,
        }
    }
}

/// `required_states()`: every state flagged required, in file order (all 196 in v2); an empty selection is
/// MODEL_ERROR.
pub fn required_states(set: &DesignStateSet) -> AbepResult<Vec<DesignState>> {
    let st: Vec<DesignState> = set.states.iter().filter(|x| x.required).map(DesignState::from_record).collect();
    if st.is_empty() {
        return Err(AbepError::Model { message: "design-state set flags no required state".into() });
    }
    Ok(st)
}

/// State selection by id (None when the id is not a member of the set).
pub fn select<'a>(states: &'a [DesignState], state_id: &str) -> Option<&'a DesignState> {
    states.iter().find(|s| s.state_id == state_id)
}
