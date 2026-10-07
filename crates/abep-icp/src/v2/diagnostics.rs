//! Reported diagnostics with no threshold (A9.31 OQ-NPICP-03, -09): EQ-19 magnetization ratios and EQ-20 sheath
//! ratios. None of them gates an output; DOM-06 v2 keeps every plasma, capacity and partition output
//! INCOMPLETE_EVIDENCE for B > 0 until a sourced criterion is registered.

use crate::constants::{E_CHARGE, M_E};
use crate::physics;
use std::f64::consts::PI;

/// EQ-19: omega_ce / nu_m = e B / (m_e nu_m) with nu_m = sum_k n_k k_m,k(T_e) [1/s].
pub fn omega_ce_over_nu_m(b_t: f64, nu_m_per_s: f64) -> f64 {
    E_CHARGE * b_t / (M_E * nu_m_per_s)
}

/// EQ-19 definition of the reported diagnostic: vbar_perp = (pi e T_e / (2 m_e))^(1/2), the mean speed of a
/// two-dimensional Maxwellian.
pub fn vbar_perp(t_e_ev: f64) -> f64 {
    (PI * E_CHARGE * t_e_ev / (2.0 * M_E)).sqrt()
}

/// EQ-19: r_ce / R = m_e vbar_perp / (e B R).
pub fn r_ce_over_r(t_e_ev: f64, b_t: f64, r_m: f64) -> f64 {
    M_E * vbar_perp(t_e_ev) / (E_CHARGE * b_t * r_m)
}

/// EQ-20: lambda_D = (eps0 T_e / (e n_e))^(1/2) (eps0 carries VER-25).
pub fn debye_length(t_e_ev: f64, n_e_m3: f64) -> f64 {
    physics::debye_length(t_e_ev, n_e_m3)
}
