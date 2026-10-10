//! `abep_sim/mission_env.py` constants kernel pulled forward for the orbit atmosphere (contract
//! PARITY-C-ABEP_SIM_MISSION_ENV_PY-CONSTANTS_KERNEL-V1): J2, OMEGA_E, the `Spacecraft` defaults and the J2
//! sun-synchronous inclination. The rest of mission_env (eclipse, arrays, pointing) belongs to SC-WP-09.

use crate::pyfloat::{degrees, py_pow, TWO_PI};
use abep_types::constants::{MU_EARTH, R_EARTH};
use abep_types::{AbepError, AbepResult};
use serde::Serialize;

pub const J2: f64 = 1.08262668e-3;
/// Earth rotation rate, rad s^-1 (rigid co-rotation of the atmosphere).
pub const OMEGA_E: f64 = 7.2921159e-5;

/// Label of the `inc_deg` / `ltan_h` defaults (A9.17 ORBIT): a parametric code default, never a requirement input;
/// inclination and LTAN are TBD from the official mission ICD.
pub const ORBIT_DEFAULT_STATUS: &str = "CODE_DEFAULT / PARAMETRIC";

/// `mission_env.Spacecraft` with its dataclass defaults (field order = the dataclass order).
#[derive(Debug, Clone, PartialEq, Serialize)]
#[allow(non_snake_case)]
pub struct Spacecraft {
    pub mass_kg: f64,
    /// Frontal area beyond the intake (bus, appendages).
    pub bus_frontal_m2: f64,
    pub bus_cd: f64,
    /// Total solar array area (both wings).
    pub array_area_m2: f64,
    /// Arrays aligned with velocity (thin edge to ram).
    pub array_edge_on: bool,
    pub array_thickness_m: f64,
    pub array_span_m: f64,
    pub array_eff: f64,
    pub array_deg_per_yr: f64,
    pub array_angle_from_thrust_axis_deg: f64,
    pub array_distance_m: f64,
    pub pointing_sigma_deg: f64,
    pub eps_eff: f64,
    pub bus_housekeeping_W: f64,
    /// SSO at 200 km; ORBIT_DEFAULT_STATUS.
    pub inc_deg: f64,
    /// 06:00 LTAN dawn-dusk; ORBIT_DEFAULT_STATUS.
    pub ltan_h: f64,
    pub intake_cd_ref: f64,
}

impl Default for Spacecraft {
    fn default() -> Self {
        Spacecraft {
            mass_kg: 150.0,
            bus_frontal_m2: 0.25,
            bus_cd: 2.2,
            array_area_m2: 2.0,
            array_edge_on: true,
            array_thickness_m: 0.02,
            array_span_m: 2.0,
            array_eff: 0.29,
            array_deg_per_yr: 0.03,
            array_angle_from_thrust_axis_deg: 75.0,
            array_distance_m: 1.2,
            pointing_sigma_deg: 1.0,
            eps_eff: 0.90,
            bus_housekeeping_W: 120.0,
            inc_deg: 96.33,
            ltan_h: 6.0,
            intake_cd_ref: 2.05,
        }
    }
}

fn refuse(alt_km: f64, why: &str) -> AbepError {
    AbepError::OutOfDomain { message: format!("sso_inclination_deg({alt_km}): {why}") }
}

/// Sun-synchronous inclination (RAAN drift 360 / 365.25 deg / day under J2), degrees. The reference's math domain
/// errors (zero radius, negative radius, overflow of a^3, |cos i| > 1: no SSO) are refused as OUT_OF_DOMAIN; a NaN
/// altitude is refused too (DIV-C-01).
pub fn sso_inclination_deg(alt_km: f64) -> AbepResult<f64> {
    if alt_km.is_nan() {
        return Err(refuse(alt_km, "altitude is NaN"));
    }
    let a = R_EARTH + alt_km * 1e3;
    let w_s = TWO_PI / (365.25 * 86400.0);
    let a3 = py_pow(a, 3.0);
    if a3.is_infinite() && a.is_finite() {
        return Err(refuse(alt_km, "a ** 3 overflows"));
    }
    if a3 == 0.0 {
        return Err(refuse(alt_km, "zero orbit radius"));
    }
    let q = MU_EARTH / a3;
    if q < 0.0 {
        return Err(refuse(alt_km, "negative orbit radius"));
    }
    let n = q.sqrt();
    let ratio = R_EARTH / a;
    let r2 = py_pow(ratio, 2.0);
    if r2.is_infinite() || (r2 != 0.0 && r2 < f64::MIN_POSITIVE) {
        return Err(refuse(alt_km, "(R_EARTH / a) ** 2 out of range"));
    }
    let den = 1.5 * n * J2 * r2;
    if den == 0.0 {
        return Err(refuse(alt_km, "zero denominator"));
    }
    let cos_i = -w_s / den;
    if !(-1.0..=1.0).contains(&cos_i) {
        return Err(refuse(alt_km, "no sun-synchronous inclination (|cos i| > 1)"));
    }
    Ok(degrees(cos_i.acos()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use abep_types::EvalStatus;

    #[test]
    fn sso_inclination_is_the_dawn_dusk_code_default_at_200_km() {
        let i = sso_inclination_deg(200.0).unwrap();
        assert!((i - Spacecraft::default().inc_deg).abs() < 0.1, "{i}");
        assert_eq!(ORBIT_DEFAULT_STATUS, "CODE_DEFAULT / PARAMETRIC");
    }

    #[test]
    fn math_domain_errors_are_out_of_domain() {
        for alt in [10000.0, -6371.0, -7000.0, 1.0e103, f64::INFINITY, f64::NEG_INFINITY, f64::NAN] {
            assert_eq!(sso_inclination_deg(alt).unwrap_err().status(), EvalStatus::OutOfDomain, "{alt}");
        }
    }
}
