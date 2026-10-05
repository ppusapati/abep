//! Physical constants of the active chain (`abep_sim/constants.py`, contract PARITY-C-ABEP_SIM_CONSTANTS_PY-V1).
//!
//! The values are the reference literals; each species mass is one IEEE multiplication, as in the reference. The RFP
//! constraint set of the same Python module is requirement data and is not part of this physics vocabulary (RM-R14).

use crate::{AbepError, AbepResult};

pub const G0: f64 = 9.80665;
pub const E_CHARGE: f64 = 1.602176634e-19;
pub const AMU: f64 = 1.66053906660e-27;
pub const K_B: f64 = 1.380649e-23;
/// m^3 s^-2
pub const MU_EARTH: f64 = 3.986004418e14;
/// m
pub const R_EARTH: f64 = 6371.0e3;

pub const M_O: f64 = 16.0 * AMU;
pub const M_N2: f64 = 28.0 * AMU;
pub const M_O2: f64 = 32.0 * AMU;
/// 131.3 u, the reference value (not re-derived from a newer atomic mass).
pub const M_XE: f64 = 131.3 * AMU;

/// Species of `M_SPECIES`, in the reference key order.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Species {
    O,
    N2,
    O2,
    Xe,
}

impl Species {
    pub const ALL: [Species; 4] = [Species::O, Species::N2, Species::O2, Species::Xe];

    pub fn name(self) -> &'static str {
        match self {
            Species::O => "O",
            Species::N2 => "N2",
            Species::O2 => "O2",
            Species::Xe => "Xe",
        }
    }

    /// Particle mass in kg.
    pub fn mass(self) -> f64 {
        match self {
            Species::O => M_O,
            Species::N2 => M_N2,
            Species::O2 => M_O2,
            Species::Xe => M_XE,
        }
    }
}

/// `M_SPECIES[name]`; an unknown species is refused (the reference raises KeyError).
pub fn species_mass(name: &str) -> AbepResult<f64> {
    Species::ALL.iter().find(|s| s.name() == name).map(|s| s.mass()).ok_or_else(|| AbepError::OutOfDomain {
        message: format!("unknown species {name:?} (M_SPECIES: O, N2, O2, Xe)"),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::EvalStatus;

    #[test]
    fn species_masses_are_one_multiplication() {
        let amu = std::hint::black_box(AMU);
        assert_eq!(M_O.to_bits(), (16.0 * amu).to_bits());
        assert_eq!(M_N2.to_bits(), (28.0 * amu).to_bits());
        assert_eq!(M_O2.to_bits(), (32.0 * amu).to_bits());
        assert_eq!(M_XE.to_bits(), (131.3 * amu).to_bits());
    }

    #[test]
    fn unknown_species_is_out_of_domain() {
        assert_eq!(species_mass("N2").unwrap(), M_N2);
        assert_eq!(species_mass("He").unwrap_err().status(), EvalStatus::OutOfDomain);
    }
}
