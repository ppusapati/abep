//! Conservation-bound kernels of NP-HALL-PARAMETRIC-ENVELOPE addendum A4
//! (`docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a4_conservation_bounds.json`,
//! sec. kernels K-U, K-PHI, K-Q, K-TMAX, K-MDOT-REQ, K-AREQ, K-DCAP).
//!
//! Upper bounds on what any design and any chemistry could achieve under the admitted environment, from conservation
//! of mass, momentum and energy alone: the free-stream relative speed over every orbit of the altitude band, the
//! one-sided mass and energy flux of a drifting Maxwellian through a unit area at normal incidence, the thrust of an
//! exhaust of given mass flow and energy rate, and their inverses. Raw physics: no requirement value is read, no
//! comparison is made (the assessment applies HC-01..HC-03 in abep-assess). An upper bound on thrust is never a thrust
//! value and never enters the statewise T - D record. Inputs that are not finite or outside the kernel's domain are
//! refused with OUT_OF_DOMAIN.

use abep_atmos::mission_env_kernel::{J2, OMEGA_E};
use abep_types::constants::{AMU, E_CHARGE, K_B, MU_EARTH};
use abep_types::{AbepError, AbepResult};
use serde::Serialize;
use std::f64::consts::PI;

pub const LABEL: &str = "CONSERVATION_BOUND / FAVORABLE_UPPER_BOUND / NOT_A_PERFORMANCE_PREDICTION";
/// Speed of light, m/s (SI, exact).
pub const C_LIGHT: f64 = 299_792_458.0;
/// WGS 84 semi-major axis, m (NIMA TR8350.2, 3rd ed. 2000, Table 3.1; verify).
pub const WGS84_A: f64 = 6_378_137.0;
/// WGS 84 inverse flattening (NIMA TR8350.2, Table 3.1; verify).
pub const WGS84_INV_F: f64 = 298.257223563;
/// Lightest possible carrier of the unspeciated remainder density: lower end of the IUPAC 2021 standard atomic weight
/// interval of H, kg (verify).
pub const M_H_MIN: f64 = 1.00784 * AMU;
/// D0(H2), eV (Huber & Herzberg 1979; NIST Chemistry WebBook; verify).
pub const D0_H2_EV: f64 = 4.4781;

fn dom(msg: impl Into<String>) -> AbepError {
    AbepError::OutOfDomain { message: format!("conservation bound: {}", msg.into()) }
}

fn finite_nonneg(name: &str, x: f64) -> AbepResult<f64> {
    if x.is_finite() && x >= 0.0 {
        Ok(x)
    } else {
        Err(dom(format!("{name} = {x} must be finite and >= 0")))
    }
}

fn finite_pos(name: &str, x: f64) -> AbepResult<f64> {
    if x.is_finite() && x > 0.0 {
        Ok(x)
    } else {
        Err(dom(format!("{name} = {x} must be finite and > 0")))
    }
}

/// WGS 84 semi-minor axis, m.
pub fn wgs84_b() -> f64 {
    WGS84_A * (1.0 - 1.0 / WGS84_INV_F)
}

/// WGS 84 first eccentricity squared.
pub fn wgs84_e2() -> f64 {
    let f = 1.0 / WGS84_INV_F;
    f * (2.0 - f)
}

/// eps_x,max: the aggregate bound on the specific internal + chemical + recombination energy of captured free-stream
/// gas, D0(H2) / (2 m_H,min), J/kg.
pub fn eps_x_max_j_kg() -> f64 {
    D0_H2_EV * E_CHARGE / (2.0 * M_H_MIN)
}

// ------------------------------------------------------------------------------------------------ K-U

/// Inputs of the relative-speed bound at one state.
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub struct SpeedInputs {
    pub lat_deg: f64,
    /// geodetic altitude of the state, m
    pub alt_m: f64,
    /// registered altitude band, m
    pub alt_min_m: f64,
    pub alt_max_m: f64,
    /// admitted free-stream speed (circular inertial orbital speed), m/s
    pub v_admitted_m_s: f64,
    /// horizontal wind speed bound (magnitude + interpolation error), m/s
    pub wind_m_s: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub struct SpeedBound {
    pub r_geocentric_m: f64,
    pub v_orb_max_m_s: f64,
    pub v_orb_min_m_s: f64,
    pub v_rot_m_s: f64,
    pub wind_m_s: f64,
    pub u_max_m_s: f64,
    pub u_min_m_s: f64,
}

/// K-U: bounds of the free-stream speed relative to the atmosphere at a state, over every orbit inside the band.
pub fn speed_bound(i: &SpeedInputs) -> AbepResult<SpeedBound> {
    if !(i.lat_deg.is_finite() && i.lat_deg.abs() <= 90.0) {
        return Err(dom(format!("latitude {} deg", i.lat_deg)));
    }
    let h = finite_nonneg("alt_m", i.alt_m)?;
    let h_lo = finite_nonneg("alt_min_m", i.alt_min_m)?;
    let h_hi = finite_nonneg("alt_max_m", i.alt_max_m)?;
    if !(h_lo <= h && h <= h_hi) {
        return Err(dom(format!("altitude {h} m outside the band [{h_lo}, {h_hi}] m")));
    }
    let v_adm = finite_pos("v_admitted_m_s", i.v_admitted_m_s)?;
    let wind = finite_nonneg("wind_m_s", i.wind_m_s)?;
    let (a, b, e2) = (WGS84_A, wgs84_b(), wgs84_e2());
    let (s, c) = i.lat_deg.to_radians().sin_cos();
    let n = a / (1.0 - e2 * s * s).sqrt();
    let (x, z) = ((n + h) * c, (n * (1.0 - e2) + h) * s);
    let r = x.hypot(z);
    let j2 = 3.0 * J2 * (a / r).powi(2);
    let r_hi = (a + h_hi).max(r);
    let r_lo = (b + h_lo).min(r);
    let v_orb_max = v_adm.max((MU_EARTH * (2.0 / r - 2.0 / (r + r_hi)) * (1.0 + j2)).sqrt());
    let v_orb_min = (MU_EARTH * (2.0 / r - 2.0 / (r + r_lo)) * (1.0 - j2)).sqrt();
    let v_rot = OMEGA_E * (n + h) * c.abs();
    Ok(SpeedBound {
        r_geocentric_m: r,
        v_orb_max_m_s: v_orb_max,
        v_orb_min_m_s: v_orb_min,
        v_rot_m_s: v_rot,
        wind_m_s: wind,
        u_max_m_s: v_orb_max + v_rot + wind,
        u_min_m_s: (v_orb_min - v_rot - wind).max(0.0),
    })
}

// ------------------------------------------------------------------------------------------------ K-PHI / K-Q

/// One mass carrier of the free stream.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Carrier {
    pub name: String,
    pub rho_kg_m3: f64,
    pub m_kg: f64,
}

/// The carriers of a state: O, N2, O2 from their number densities and the unspeciated remainder of the stored total
/// density carried as atomic H (the lightest possible carrier). The total is max(rho, sum of the species).
pub fn carriers(rho: f64, n_o: f64, n_n2: f64, n_o2: f64) -> AbepResult<Vec<Carrier>> {
    use abep_types::constants::{M_N2, M_O, M_O2};
    let rho = finite_nonneg("rho", rho)?;
    let mut v = vec![];
    let mut sum = 0.0;
    for (name, n, m) in [("O", n_o, M_O), ("N2", n_n2, M_N2), ("O2", n_o2, M_O2)] {
        let r = finite_nonneg(&format!("n_{name}"), n)? * m;
        sum += r;
        v.push(Carrier { name: name.into(), rho_kg_m3: r, m_kg: m });
    }
    v.push(Carrier { name: "REMAINDER_AS_H".into(), rho_kg_m3: (rho - sum).max(0.0), m_kg: M_H_MIN });
    Ok(v)
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct CarrierFlux {
    pub name: String,
    pub speed_ratio: f64,
    pub phi_kg_m2_s: f64,
    pub q_translational_w_m2: f64,
    pub q_internal_w_m2: f64,
}

/// Upper bounds of the one-sided free-stream fluxes through a unit area at normal incidence.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct FluxBound {
    pub u_m_s: f64,
    pub t_k: f64,
    pub phi_max_kg_m2_s: f64,
    pub q_max_w_m2: f64,
    pub q_chemical_w_m2: f64,
    pub s_min: f64,
    pub carriers: Vec<CarrierFlux>,
}

/// K-PHI and K-Q at relative speed `u` and neutral temperature `t_k` (drifting Maxwellian per carrier, erf -> 1).
pub fn flux_bound(carriers: &[Carrier], t_k: f64, u: f64) -> AbepResult<FluxBound> {
    let t = finite_pos("T_K", t_k)?;
    let u = finite_pos("u_m_s", u)?;
    let sp = PI.sqrt();
    let (mut phi, mut q, mut s_min) = (0.0, 0.0, f64::INFINITY);
    let mut out = Vec::with_capacity(carriers.len());
    for k in carriers {
        let rho = finite_nonneg(&format!("rho_{}", k.name), k.rho_kg_m3)?;
        let m = finite_pos(&format!("m_{}", k.name), k.m_kg)?;
        let c = (2.0 * K_B * t / m).sqrt();
        let s = u / c;
        let ex = (-s * s).exp();
        let phi_k = rho * u * (1.0 + ex / (2.0 * sp * s));
        let q_tr = rho * c.powi(3) / (4.0 * sp) * ((s * s + 2.0) * ex + 2.0 * sp * s * (s * s + 2.5));
        let q_int = phi_k * 2.0 * K_B * t / m;
        if rho > 0.0 {
            s_min = s_min.min(s);
        }
        phi += phi_k;
        q += q_tr + q_int;
        out.push(CarrierFlux {
            name: k.name.clone(),
            speed_ratio: s,
            phi_kg_m2_s: phi_k,
            q_translational_w_m2: q_tr,
            q_internal_w_m2: q_int,
        });
    }
    if phi <= 0.0 || !phi.is_finite() {
        return Err(dom("free stream carries no mass"));
    }
    let q_chem = phi * eps_x_max_j_kg();
    Ok(FluxBound {
        u_m_s: u,
        t_k: t,
        phi_max_kg_m2_s: phi,
        q_max_w_m2: q + q_chem,
        q_chemical_w_m2: q_chem,
        s_min,
        carriers: out,
    })
}

// ------------------------------------------------------------------------------------------------ K-TMAX and inverses

/// K-TMAX: T_max(mdot, P) = sqrt(2 mdot P) + P / c, N (P: total energy rate available to the exhaust and radiation).
pub fn t_max(mdot_kg_s: f64, p_w: f64) -> AbepResult<f64> {
    let m = finite_nonneg("mdot", mdot_kg_s)?;
    let p = finite_nonneg("P", p_w)?;
    Ok((2.0 * m * p).sqrt() + p / C_LIGHT)
}

/// K-MDOT-REQ: the smallest mdot with T_max(mdot, P) >= T_req, kg/s.
pub fn mdot_required(t_req_n: f64, p_w: f64) -> AbepResult<f64> {
    let t = finite_nonneg("T_req", t_req_n)?;
    let p = finite_pos("P", p_w)?;
    let d = t - p / C_LIGHT;
    Ok(if d <= 0.0 { 0.0 } else { d * d / (2.0 * p) })
}

/// T_max of a collection area `a` (eta_cap = 1): T_max(Phi a, P0 + q a), N.
pub fn t_max_at_area(a_m2: f64, p0_w: f64, phi_kg_m2_s: f64, q_w_m2: f64) -> AbepResult<f64> {
    let a = finite_nonneg("A", a_m2)?;
    let phi = finite_pos("Phi", phi_kg_m2_s)?;
    let q = finite_nonneg("q", q_w_m2)?;
    t_max(phi * a, finite_nonneg("P0", p0_w)? + q * a)
}

/// K-AREQ: the smallest collection area A with T_max(Phi A, P0 + q A) >= T_req, m^2 (closed-form positive root).
pub fn area_required(t_req_n: f64, p0_w: f64, phi_kg_m2_s: f64, q_w_m2: f64) -> AbepResult<f64> {
    let t = finite_nonneg("T_req", t_req_n)?;
    let p0 = finite_pos("P0", p0_w)?;
    let phi = finite_pos("Phi", phi_kg_m2_s)?;
    let q = finite_nonneg("q", q_w_m2)?;
    let d = t - p0 / C_LIGHT;
    if d <= 0.0 {
        return Ok(0.0);
    }
    let c2 = C_LIGHT * C_LIGHT;
    let a = 2.0 * phi * q - q * q / c2;
    if a < 0.0 {
        return Err(dom(format!("q = {q} W/m^2 >= 2 Phi c^2")));
    }
    let b = 2.0 * phi * p0 + 2.0 * d * q / C_LIGHT;
    let cc = d * d;
    let area = 2.0 * cc / (b + (b * b + 4.0 * a * cc).sqrt());
    if p0 + q * area > t * C_LIGHT {
        return Err(dom("the root needs more radiated momentum than the required thrust"));
    }
    Ok(area)
}

/// K-DCAP: momentum removed from the captured flow brought to rest relative to the spacecraft, N (bulk form).
pub fn captured_momentum_drag(mdot_cap_kg_s: f64, u_m_s: f64) -> AbepResult<f64> {
    Ok(finite_nonneg("mdot_cap", mdot_cap_kg_s)? * finite_nonneg("U", u_m_s)?)
}

/// The largest mdot with T_max(mdot, P) >= mdot U (the larger root of (mdot U - P/c)^2 = 2 mdot P), kg/s.
pub fn mdot_td_max(p_w: f64, u_m_s: f64) -> AbepResult<f64> {
    let p = finite_pos("P", p_w)?;
    let u = finite_pos("U", u_m_s)?;
    let bb = 2.0 * u * p / C_LIGHT + 2.0 * p;
    let disc = bb * bb - 4.0 * u * u * p * p / (C_LIGHT * C_LIGHT);
    Ok((bb + disc.max(0.0).sqrt()) / (2.0 * u * u))
}

/// max over mdot of T_max(mdot, P) - mdot U = P / (2 U) + P / c, N.
pub fn max_t_minus_dcap(p_w: f64, u_m_s: f64) -> AbepResult<f64> {
    let p = finite_nonneg("P", p_w)?;
    let u = finite_pos("U", u_m_s)?;
    Ok(p / (2.0 * u) + p / C_LIGHT)
}
