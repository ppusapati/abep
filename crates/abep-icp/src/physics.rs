//! Registered closed-form kernels. Each carries its prereg equation id and its primary-source locator; none is taken
//! from `abep_sim/plasma_chem.py` (EX-01). T_e is in eV throughout (energy per charge, e T_e in J).

use crate::constants::{EPS0, E_CHARGE, K_B, M_E};
use std::f64::consts::PI;

/// EQ-04: u_B,s = (Z_s e T_e / M_s)^(1/2). Lieberman 2015 slide 41 for Z = 1 (registered); Z > 1 is VER-08.
pub fn bohm_speed(t_e_ev: f64, z: u32, mass_kg: f64) -> f64 {
    (f64::from(z) * E_CHARGE * t_e_ev / mass_kg).sqrt()
}

/// EQ-08: v̄_e = (8 e T_e / (pi m_e))^(1/2) (Lieberman 2015 slide 48).
pub fn electron_mean_speed(t_e_ev: f64) -> f64 {
    (8.0 * E_CHARGE * t_e_ev / (PI * M_E)).sqrt()
}

/// EQ-02: v̄ = (8 k_B T / (pi M))^(1/2) (Chiggiato 2014 Eq. 3).
pub fn neutral_mean_speed(t_k: f64, mass_kg: f64) -> f64 {
    (8.0 * K_B * t_k / (PI * mass_kg)).sqrt()
}

/// EQ-08 single species: V_s = (T_e / 2) ln(M / (2 pi m_e)) (Lieberman 2015 slide 48).
pub fn floating_sheath_single_species(t_e_ev: f64, mass_kg: f64) -> f64 {
    0.5 * t_e_ev * (mass_kg / (2.0 * PI * M_E)).ln()
}

/// EQ-05 H-LIEB: lambda_i = 1 / (n_g sigma_i); infinite for n_g = 0.
pub fn ion_mean_free_path(n_g_m3: f64, sigma_i_m2: f64) -> f64 {
    if n_g_m3 == 0.0 {
        f64::INFINITY
    } else {
        1.0 / (n_g_m3 * sigma_i_m2)
    }
}

/// EQ-05 H-LIEB radial: h_R = 0.8 (4 + R / lambda_i)^(-1/2) (Lieberman 2015 slide 44). -> 0.4 as lambda_i -> inf.
pub fn h_radial_lieberman(r_m: f64, lambda_i_m: f64) -> f64 {
    0.8 / (4.0 + r_m / lambda_i_m).sqrt()
}

/// EQ-05 H-LIEB axial: h_L = 0.86 (3 + L / (2 lambda_i))^(-1/2) (Lieberman 2015 slides 43, 44).
pub fn h_axial_lieberman(l_m: f64, lambda_i_m: f64) -> f64 {
    0.86 / (3.0 + l_m / (2.0 * lambda_i_m)).sqrt()
}

/// EQ-02 tube transmission (Santeler 1986 as given by Chiggiato 2014 Eq. 21; < 0.7 % error); tau(0) = 1.
pub fn santeler_transmission(length_m: f64, radius_m: f64) -> f64 {
    let x = length_m / radius_m;
    1.0 / (1.0 + (3.0 * x / 8.0) * (1.0 + 1.0 / (3.0 * (1.0 + x / 7.0))))
}

/// DOM-04 neutral mean free path lambda = 1 / (sqrt(2) n sigma_c) (Chiggiato 2014 Eq. 7, as recorded in the citation
/// registry `INTERSTAGE_MODEL.md` sec. 7; mixture form 1/(sqrt(2) sum n_k sigma_k)). Infinite for an empty volume.
pub fn molecular_mean_free_path(sum_n_sigma_m: f64) -> f64 {
    if sum_n_sigma_m == 0.0 {
        f64::INFINITY
    } else {
        1.0 / (2f64.sqrt() * sum_n_sigma_m)
    }
}

/// DOM-07 (reported only): Debye length (eps0 T_e / (e n_e))^(1/2) with T_e in eV.
pub fn debye_length(t_e_ev: f64, n_e_m3: f64) -> f64 {
    (EPS0 * t_e_ev / (E_CHARGE * n_e_m3)).sqrt()
}

/// k_B T / e: a gas temperature in K expressed in eV.
pub fn kelvin_to_ev(t_k: f64) -> f64 {
    K_B * t_k / E_CHARGE
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn santeler_limits() {
        assert_eq!(santeler_transmission(0.0, 1.0), 1.0);
        assert!(santeler_transmission(10.0, 1.0) < 0.2);
    }

    #[test]
    fn lieberman_infinite_mean_free_path() {
        assert_eq!(h_radial_lieberman(0.1, f64::INFINITY), 0.4);
        assert_eq!(ion_mean_free_path(0.0, 1e-19), f64::INFINITY);
    }
}
