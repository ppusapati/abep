//! Physical constants (SI) and the numerical settings of IN-24.
//!
//! The tolerances are numerical policy for IEEE double, not physics numbers (prereg `conservation_basis`).

/// Elementary charge [C], exact SI value (as `abep_sim/constants.py`).
pub const E_CHARGE: f64 = 1.602_176_634e-19;
/// Boltzmann constant [J/K], exact SI value.
pub const K_B: f64 = 1.380_649e-23;
/// Electron mass [kg], CODATA 2022 9.1093837139(28)e-31 (the value recorded in `abep_sim/interstage.py`).
pub const M_E: f64 = 9.109_383_713_9e-31;
/// Atomic mass constant [kg] (as `abep_sim/constants.py`).
pub const AMU: f64 = 1.660_539_066_60e-27;
/// Vacuum permittivity [F/m], CODATA 2018 (from memory: verify). Used only for the reported DOM-07 Debye ratio.
pub const EPS0: f64 = 8.854_187_812_8e-12;

/// The only registered RF frequency [Hz] (IN-07, VI-RF-01, DOM-11).
pub const F_RF_REGISTERED_HZ: f64 = 13.56e6;
/// 100 mTorr in Pa (Lieberman 2015 slide 44 domain of H-LIEB; 1 Torr = 133.32 Pa, Chiggiato 2014 Table 1).
pub const P_100_MTORR_PA: f64 = 0.1 * 133.32;
/// Free-molecular regime bound Kn > 0.5 (Chiggiato 2014 Table 7; DOM-04).
pub const KN_FREE_MOLECULAR_MIN: f64 = 0.5;

/// TOL-SOLVE: residual of each balance equation relative to its largest term.
pub const TOL_SOLVE: f64 = 1e-12;
/// TOL-CONS: conservation residuals CC-01..CC-07.
pub const TOL_CONS: f64 = 1e-10;
/// TOL-ANALYTIC: analytic limiting cases unless a case states otherwise.
pub const TOL_ANALYTIC: f64 = 1e-9;

/// Registered numerical settings (IN-24; prereg `numerical_verification`, "registered per solver"). The prereg fixes
/// the rules (full-domain bracketing, every sign change refined and reported, iteration limit = MODEL_ERROR); the grid
/// values are registered here and recorded in `verification_report_v1.json`.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct NumericalSettings {
    /// T_e root scan: log-spaced grid on [t_e_scan_min_ev, t_e_scan_max_ev]. Wider than every chemistry domain so a
    /// root outside the domain is found and reported OUT_OF_DOMAIN rather than missed.
    pub t_e_scan_min_ev: f64,
    pub t_e_scan_max_ev: f64,
    pub t_e_scan_points: usize,
    /// n_e root scan (cases where n_e does not cancel from the particle balance): log grid [min, max].
    pub n_e_scan_min_m3: f64,
    pub n_e_scan_max_m3: f64,
    pub n_e_points_per_decade: usize,
    /// Bisection stops at adjacent doubles; reaching this many halvings is MODEL_ERROR.
    pub bisection_max_iter: usize,
    /// Fixed point on the total neutral density (FLOW_BALANCE with H-LIEB edge factors).
    pub fixed_point_max_iter: usize,
    pub fixed_point_rel_tol: f64,
}

pub const NUMERICS: NumericalSettings = NumericalSettings {
    t_e_scan_min_ev: 0.1,
    t_e_scan_max_ev: 150.0,
    t_e_scan_points: 301,
    n_e_scan_min_m3: 1e8,
    n_e_scan_max_m3: 1e21,
    n_e_points_per_decade: 10,
    bisection_max_iter: 400,
    fixed_point_max_iter: 500,
    fixed_point_rel_tol: 1e-14,
};
