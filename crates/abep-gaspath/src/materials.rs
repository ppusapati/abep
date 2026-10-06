//! Materials-database values the gas path reads (`abep_sim/materials.py` DB: density, yield, service limit, O-atom
//! wall recombination). They enter as explicit plain data until C-ABEP_SIM_MATERIALS_PY (SC-WP-12) is admitted;
//! nothing here holds a material value of its own.

use crate::error::{key_error, PyResult};
use crate::pyops;
use abep_types::constants::{E_CHARGE, K_B};
use serde::Deserialize;
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Deserialize)]
pub struct MaterialProps {
    /// kg m^-3
    pub density: f64,
    #[serde(rename = "yield_MPa")]
    pub yield_mpa: f64,
    #[serde(rename = "T_max_K")]
    pub t_max_k: f64,
    pub gamma_min: f64,
    pub gamma0: f64,
    #[serde(rename = "gamma_Ea_eV")]
    pub gamma_ea_ev: f64,
}

impl MaterialProps {
    /// `Material.gamma_O(T)` = gamma_min + gamma0 exp(-Ea e / (k_B T)) (the reference expression).
    pub fn gamma_o(&self, t_k: f64) -> PyResult<f64> {
        let arg = pyops::div(-self.gamma_ea_ev * E_CHARGE, K_B * t_k)?;
        Ok(self.gamma_min + self.gamma0 * pyops::exp(arg)?)
    }
}

/// The DB entries supplied by the caller (name -> properties).
#[derive(Debug, Clone, Default, PartialEq, Deserialize)]
#[serde(transparent)]
pub struct MaterialsView(pub BTreeMap<String, MaterialProps>);

impl MaterialsView {
    /// `DB[name]`; an unknown name is a KeyError, as in the reference.
    pub fn get(&self, name: &str) -> PyResult<&MaterialProps> {
        self.0.get(name).ok_or_else(|| key_error(name))
    }
    pub fn contains(&self, name: &str) -> bool {
        self.0.contains_key(name)
    }
}
