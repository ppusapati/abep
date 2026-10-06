//! Electron-impact rate coefficients of the ABEP Rust simulator (SC-WP-03).
//!
//! The port of `abep_sim/rate_tables.py` under contract `PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1`
//! (`docs/rust_migration/contracts/C-ABEP_SIM_RATE_TABLES_PY/`), and the integrator side of IF-CHEM-REG-v1 (provider
//! abep-chem, consumer abep-icp; NP-ICP-NEUTRALIZER EQ-06, NP-ICP-CHEM-AIR IX-01..IX-06).
//!
//! * [`reference`]: the Python reference behaviour, operation by operation. The numpy routines it calls are replicated
//!   in [`numpy`]; Python exceptions are mirrored as [`abep_types::pyjson::PyException`]. The silent behaviours of the
//!   reference are kept here, for parity and for byte-identical table rebuilds: the held cross section beyond the last
//!   tabulated point (tail `hold`), 0.0 for T_e <= 0, NaN for non-finite T_e.
//! * [`checked`]: the API production code calls. It refuses everything the reference does silently: a missing
//!   `rate_validity.toml` entry is MODEL_ERROR, an `unresolved` one INCOMPLETE_EVIDENCE, a mean energy 3/2 T_e beyond
//!   the verified limit or a non-positive / non-finite T_e OUT_OF_DOMAIN, an invalid representation MODEL_ERROR.
//! * [`validity`]: the `rate_validity.toml` reader; [`dat`]: the HallThruster.jl rate-table reader. Both verify sha256
//!   pins on load.
//!
//! Nothing here comes from `abep_sim/plasma_chem.py` (NP-ICP-NEUTRALIZER EX-01).

pub mod checked;
pub mod dat;
pub mod numpy;
pub mod reference;
pub mod validity;

/// Electron mass [kg] of the reference (`rate_tables.ME`). Not the CODATA 2018 value 9.1093837015e-31: the frozen
/// tables were integrated with this one, and parity keeps it.
pub const ME: f64 = 9.10938e-31;

/// Elementary charge [C] (`rate_tables.QE`; exact SI value, equal to `abep_types::constants::E_CHARGE`).
pub const QE: f64 = 1.602176634e-19;

/// `QE ** 2` of the reference. CPython's `pow(QE, 2)` and `QE * QE` give the same bits (checked on the registration host).
pub const QE2: f64 = QE * QE;

/// Number of points of the reference's uniform integration grid `np.linspace(0, Emax, 20000)`.
pub const GRID_POINTS: usize = 20000;

/// The reference integrates up to `max(max(E), 60 T_e)`.
pub const TE_SPAN: f64 = 60.0;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constants_are_the_reference_values() {
        assert_eq!(QE.to_bits(), abep_types::constants::E_CHARGE.to_bits());
        assert_eq!(ME.to_bits(), 9.10938e-31_f64.to_bits());
        assert_eq!(QE2.to_bits(), (QE * QE).to_bits());
    }
}
