//! Free-stream state consumed by the intake: the fields of the `atm` dict that abep_sim.intake / intake_tpmc read.
//!
//! The state itself comes from the frozen atmosphere (abep-atmos / abep-data, lane B1); this crate never derives it.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct FreeStream {
    /// number density, m^-3 (`n`)
    pub n: f64,
    /// mass density, kg m^-3 (`rho`)
    pub rho: f64,
    /// orbital speed, m/s (`V`)
    pub v: f64,
    /// relative wind speed, m/s (`V_rel`); when present it replaces `V` where the reference uses `atm.get("V_rel", V)`
    pub v_rel: Option<f64>,
    /// temperature, K (`T`)
    pub t: f64,
    /// mean molecular mass, kg (`m_mean`)
    pub m_mean: f64,
    /// free-stream mass fractions (`fO`, `fN2`, `fO2`)
    pub f_o: f64,
    pub f_n2: f64,
    pub f_o2: f64,
    /// incident mass flux rho V, kg m^-2 s^-1 (`flux_kg_m2_s`, as supplied by the atmosphere)
    pub flux_kg_m2_s: f64,
}

impl FreeStream {
    /// `atm.get("V_rel", atm["V"])`.
    pub fn v_rel_or_v(&self) -> f64 {
        self.v_rel.unwrap_or(self.v)
    }
}
