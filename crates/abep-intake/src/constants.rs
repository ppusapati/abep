//! Physical constants of the intake path, identical to `abep_sim/constants.py` (INV-08 of the intake_tpmc contract).

/// Boltzmann constant, exact SI value (2019); the admitted Kernel-1 value.
pub const K_B: f64 = abep_core::tpmc::K_B;
/// Atomic mass unit as in abep_sim/constants.py (CODATA 2018 value 1.66053906660e-27 kg).
pub const AMU: f64 = 1.66053906660e-27;

/// Molecular masses of abep_sim.constants.M_SPECIES (multiplied exactly as the reference does).
pub fn species_mass(name: &str) -> Option<f64> {
    match name {
        "O" => Some(16.0 * AMU),
        "N2" => Some(28.0 * AMU),
        "O2" => Some(32.0 * AMU),
        "Xe" => Some(131.3 * AMU),
        _ => None,
    }
}

/// Species known to `species_mass`, in abep_sim.constants.M_SPECIES order.
pub const SPECIES: [&str; 4] = ["O", "N2", "O2", "Xe"];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constants_match_the_reference_values() {
        assert_eq!(K_B, 1.380649e-23);
        assert_eq!(species_mass("N2"), Some(28.0 * 1.66053906660e-27));
        assert_eq!(species_mass("Ar"), None);
        assert_eq!(SPECIES.iter().filter(|s| species_mass(s).is_some()).count(), 4);
    }
}
