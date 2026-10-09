//! Orbital environment factors of the P7 thermal-closure cases (prereg `environment`): Earth view factors of a plate
//! and of a lateral cylinder by quadrature of the definition, the sun vector over a circular orbit, the cylindrical
//! shadow and the per-surface absorbed-flux factors. The eclipse fraction is cross-checked against the admitted kernel
//! `abep_mission::propagation::eclipse_fraction`. Geometry only: no requirement, margin or verdict here.

use abep_types::constants::{MU_EARTH, R_EARTH};
use std::f64::consts::PI;

/// Surface orientation classes of the prereg (`env_type`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EnvType {
    /// Cylinder lateral surface about the velocity axis.
    Lateral,
    /// Plate with outward normal -x (aft, wake-facing).
    AftFace,
    /// Plate with outward normal to zenith.
    Zenith,
}

impl EnvType {
    pub fn parse(s: &str) -> Option<EnvType> {
        match s {
            "LATERAL" => Some(EnvType::Lateral),
            "AFT_FACE" => Some(EnvType::AftFace),
            "ZENITH" => Some(EnvType::Zenith),
            _ => None,
        }
    }
}

/// Earth angular half-size seen from altitude h: sin(rho) = R / (R + h).
pub fn rho(alt_km: f64) -> f64 {
    (R_EARTH / (R_EARTH + alt_km * 1e3)).asin()
}

/// View factor from a plate with unit normal at angle `theta` from nadir to the Earth sphere (half-angle `rho`):
/// F = (1/pi) * integral over the cap of max(0, n.d) dOmega, midpoint quadrature `na` x `nb`.
pub fn plate_to_earth(theta: f64, rho: f64, na: usize, nb: usize) -> f64 {
    let (st, ct) = theta.sin_cos();
    let da = rho / na as f64;
    let db = 2.0 * PI / nb as f64;
    let mut sum = 0.0;
    for i in 0..na {
        let a = (i as f64 + 0.5) * da;
        let (sa, ca) = a.sin_cos();
        let mut ring = 0.0;
        for j in 0..nb {
            let b = (j as f64 + 0.5) * db;
            let c = st * sa * b.cos() + ct * ca;
            if c > 0.0 {
                ring += c;
            }
        }
        sum += ring * sa * da * db;
    }
    sum / PI
}

/// Earth view factor of the lateral surface of a cylinder whose axis is horizontal: the mean of the plate factor over
/// the normal direction swept around the axis (`n` steps).
pub fn lateral_to_earth(rho: f64, n: usize, na: usize, nb: usize) -> f64 {
    let mut s = 0.0;
    for k in 0..n {
        let phi = (k as f64 + 0.5) * 2.0 * PI / n as f64;
        s += plate_to_earth(phi, rho, na, nb);
    }
    s / n as f64
}

/// Quadrature resolution of the prereg (`view_factor_method.plate_to_earth`; `LATERAL`: 180 normal directions, each
/// plate factor at 180 x 360).
pub const NA: usize = 720;
pub const NB: usize = 1440;
pub const N_LAT: usize = 180;
pub const NA_LAT: usize = 180;
pub const NB_LAT: usize = 360;

/// Sun direction components in the body frame at orbit angle `u` (from orbit noon): (zenith, x, y).
pub fn sun(beta: f64, u: f64) -> (f64, f64, f64) {
    let cb = beta.cos();
    (cb * u.cos(), -cb * u.sin(), beta.sin())
}

/// Cylindrical shadow (the admitted kernel's model).
pub fn in_shadow(alt_km: f64, beta: f64, u: f64) -> bool {
    let (z, _, _) = sun(beta, u);
    let k = R_EARTH / (R_EARTH + alt_km * 1e3);
    z < 0.0 && (1.0 - z * z).max(0.0).sqrt() < k
}

/// Shadow entry and exit orbit angles in (pi/2, 3pi/2), or None when the orbit is in full sun.
pub fn shadow_window(alt_km: f64, beta: f64) -> Option<(f64, f64)> {
    let k = R_EARTH / (R_EARTH + alt_km * 1e3);
    let cb = beta.cos();
    if cb <= 0.0 {
        return None;
    }
    // In shadow when cos(u) < -sqrt(1 - k^2) / cos(beta).
    let c = -(1.0 - k * k).sqrt() / cb;
    if c <= -1.0 {
        return None;
    }
    let u0 = c.acos();
    Some((u0, 2.0 * PI - u0))
}

/// Eclipse fraction from the shadow window.
pub fn eclipse_fraction_local(alt_km: f64, beta: f64) -> f64 {
    match shadow_window(alt_km, beta) {
        None => 0.0,
        Some((a, b)) => (b - a) / (2.0 * PI),
    }
}

/// Smallest beta [rad] with zero eclipse at `alt_km` (full-sun orbit): cos(beta*) = sqrt(1 - k^2).
pub fn beta_star(alt_km: f64) -> f64 {
    let k = R_EARTH / (R_EARTH + alt_km * 1e3);
    (1.0 - k * k).sqrt().acos()
}

/// Circular orbit period [s].
pub fn period(alt_km: f64) -> f64 {
    let a = R_EARTH + alt_km * 1e3;
    2.0 * PI * (a * a * a / MU_EARTH).sqrt()
}

/// Circular orbital speed [m/s].
pub fn speed(alt_km: f64) -> f64 {
    (MU_EARTH / (R_EARTH + alt_km * 1e3)).sqrt()
}

/// Per-surface factors at one orbit angle: (F_sun, illumination, F_alb).
pub fn factors_at(t: EnvType, f_earth: f64, alt_km: f64, beta: f64, u: f64) -> (f64, f64, f64) {
    let (sz, sx, _) = sun(beta, u);
    let nu = if in_shadow(alt_km, beta, u) { 0.0 } else { 1.0 };
    let f_sun = match t {
        EnvType::Lateral => (1.0 - sx * sx).max(0.0).sqrt() / PI,
        EnvType::AftFace => (-sx).max(0.0),
        EnvType::Zenith => sz.max(0.0),
    };
    let f_alb = match t {
        EnvType::Zenith => 0.0,
        _ => f_earth * sz.max(0.0) * nu,
    };
    (f_sun, nu, f_alb)
}

/// Earth view factor per surface type at `alt_km`.
pub fn earth_factor(t: EnvType, alt_km: f64) -> f64 {
    let r = rho(alt_km);
    match t {
        EnvType::Lateral => lateral_to_earth(r, N_LAT, NA_LAT, NB_LAT),
        EnvType::AftFace => plate_to_earth(PI / 2.0, r, NA, NB),
        EnvType::Zenith => 0.0,
    }
}

/// Steady orbit-maximum factors of one surface (prereg `steady_hot_rule`): the u (1440 steps) that maximises
/// alpha S F_sun nu + alpha a S F_alb + eps OLR F_earth. Returns (u, F_sun, nu, F_alb, F_earth).
#[allow(clippy::too_many_arguments)]
pub fn steady_max(
    t: EnvType,
    f_earth: f64,
    alt_km: f64,
    beta: f64,
    alpha: f64,
    eps: f64,
    s: f64,
    a: f64,
    olr: f64,
) -> (f64, f64, f64, f64, f64) {
    let n = 1440;
    let mut best = (f64::NEG_INFINITY, 0.0, 0.0, 0.0, 0.0);
    for k in 0..n {
        let u = (k as f64 + 0.5) * 2.0 * PI / n as f64;
        let (fs, nu, fa) = factors_at(t, f_earth, alt_km, beta, u);
        let q = alpha * s * fs * nu + alpha * a * s * fa + eps * olr * f_earth;
        if q > best.0 {
            best = (q, u, fs, nu, fa);
        }
    }
    (best.1, best.2, best.3, best.4, f_earth)
}

/// ZOH series over one orbit (prereg `periodic_rule`): 72 equal u intervals plus the exact shadow entry / exit.
/// Returns breakpoints [s] and, per breakpoint, (F_sun, nu, F_alb) at the interval midpoint.
pub fn periodic_series(t: EnvType, f_earth: f64, alt_km: f64, beta: f64) -> (Vec<f64>, Vec<(f64, f64, f64)>) {
    let p = period(alt_km);
    let mut us: Vec<f64> = (0..72).map(|k| k as f64 * 2.0 * PI / 72.0).collect();
    if let Some((a, b)) = shadow_window(alt_km, beta) {
        us.push(a);
        us.push(b);
    }
    us.sort_by(|x, y| x.partial_cmp(y).expect("finite"));
    us.dedup_by(|x, y| (*x - *y).abs() < 1e-12);
    let mut bps = Vec::new();
    let mut vals = Vec::new();
    for (i, u0) in us.iter().enumerate() {
        let u1 = if i + 1 < us.len() { us[i + 1] } else { 2.0 * PI };
        let mid = 0.5 * (u0 + u1);
        bps.push(u0 / (2.0 * PI) * p);
        vals.push(factors_at(t, f_earth, alt_km, beta, mid));
    }
    (bps, vals)
}

/// Orbit-average absorbed flux of a zenith panel [W/m^2] (boundary-unit radiators).
pub fn zenith_orbit_average(alt_km: f64, beta: f64, alpha: f64, s: f64) -> f64 {
    let n = 14400;
    let mut q = 0.0;
    for k in 0..n {
        let u = (k as f64 + 0.5) * 2.0 * PI / n as f64;
        let (fs, nu, _) = factors_at(EnvType::Zenith, 0.0, alt_km, beta, u);
        q += alpha * s * fs * nu;
    }
    q / n as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plate_factor_matches_the_closed_form_when_fully_visible() {
        let r = rho(200.0);
        for theta in [0.0, 0.1, 0.2] {
            assert!(theta <= PI / 2.0 - r);
            let exact = r.sin().powi(2) * f64::cos(theta);
            assert!((plate_to_earth(theta, r, NA, NB) - exact).abs() < 1e-5, "theta {theta}");
        }
    }

    #[test]
    fn eclipse_fraction_matches_the_admitted_kernel() {
        for alt in [180.0, 205.0, 230.0] {
            for b in [0.0_f64, 30.0, 60.0, 75.0, 80.0] {
                let k = abep_mission::propagation::eclipse_fraction(alt, b).unwrap();
                assert!((eclipse_fraction_local(alt, b.to_radians()) - k).abs() < 1e-9, "{alt} {b}");
            }
            let bs = beta_star(alt).to_degrees();
            assert_eq!(abep_mission::propagation::eclipse_fraction(alt, bs + 1e-9).unwrap(), 0.0);
            assert!(abep_mission::propagation::eclipse_fraction(alt, bs - 1e-3).unwrap() > 0.0);
        }
    }
}
