//! Free-molecular test-particle Monte-Carlo (TPMC) channel trace - a line-by-line port of the reference
//! `abep_sim/intake_tpmc.py` (functions `_drifting_maxwellian`, `_flux_weighted_entry`, `_diffuse`, `_cll`,
//! `trace_channel`, `clausing_transmission`) with identical physics and I/O semantics. The Python file is the
//! authoritative reference; this code is an optional, switchable acceleration whose admission is decided by the
//! pre-registered statistical parity campaign (docs/performance/abep_core/parity_prereg_v1.json).
//!
//! Only the random stream differs (see rng.rs). Every geometric/flight formula, tie rule and the hit-budget
//! doubling rule are those of the reference; comments name the reference line they reproduce.

use crate::rng::Rng;

/// Boltzmann constant, exact SI value (2019 redefinition); equals abep_sim.constants.K_B (checked by the tests).
pub const K_B: f64 = 1.380649e-23;

pub type V3 = [f64; 3];

#[derive(Debug, Clone, PartialEq)]
pub enum TpmcError {
    InvalidArgument(String),
}

impl std::fmt::Display for TpmcError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TpmcError::InvalidArgument(s) => write!(f, "{}", s),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Scattering {
    Maxwell,
    Cll,
}

impl Scattering {
    /// The reference treats every value other than "cll" as Maxwell; abep_core refuses unknown names instead
    /// (documented divergence: no silent fallback).
    pub fn parse(s: &str) -> Result<Scattering, TpmcError> {
        match s {
            "maxwell" => Ok(Scattering::Maxwell),
            "cll" => Ok(Scattering::Cll),
            other => Err(TpmcError::InvalidArgument(format!(
                "abep_core.trace_channel: scattering must be 'maxwell' or 'cll', got {:?}",
                other
            ))),
        }
    }
}

#[inline]
fn dot(a: &V3, b: &V3) -> f64 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}

/// numpy.cross for 3-vectors: (a1 b2 - a2 b1, a2 b0 - a0 b2, a0 b1 - a1 b0).
#[inline]
fn cross(a: &V3, b: &V3) -> V3 {
    [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
}

/// numpy minimum semantics (NaN propagates), unlike f64::min.
#[inline]
fn np_minimum(a: f64, b: f64) -> f64 {
    if a.is_nan() || b.is_nan() {
        f64::NAN
    } else if a < b {
        a
    } else {
        b
    }
}

/// numpy maximum semantics (NaN propagates).
#[inline]
fn np_maximum(a: f64, b: f64) -> f64 {
    if a.is_nan() || b.is_nan() {
        f64::NAN
    } else if a > b {
        a
    } else {
        b
    }
}

/// Reference `_drifting_maxwellian`: N(0, vth) per component, + V cos(theta) on z, + V sin(theta) on x.
pub fn drifting_maxwellian(rng: &mut Rng, n: usize, v_drift: f64, theta: f64, t: f64, m: f64) -> Vec<V3> {
    let vth = (K_B * t / m).sqrt();
    let (vz_d, vx_d) = (v_drift * theta.cos(), v_drift * theta.sin());
    (0..n)
        .map(|_| {
            let x = vth * rng.standard_normal();
            let y = vth * rng.standard_normal();
            let z = vth * rng.standard_normal();
            [x + vx_d, y, z + vz_d]
        })
        .collect()
}

/// Reference `_flux_weighted_entry`: draw 3n drifting-Maxwellian velocities, keep v_z > 0, resample n with
/// replacement with probability proportional to v_z (inverse-CDF search, as numpy Generator.choice with p).
pub fn flux_weighted_entry(
    rng: &mut Rng,
    n: usize,
    v_drift: f64,
    theta: f64,
    t: f64,
    m: f64,
) -> Result<Vec<V3>, TpmcError> {
    let pool: Vec<V3> = drifting_maxwellian(rng, 3 * n, v_drift, theta, t, m)
        .into_iter()
        .filter(|v| v[2] > 0.0)
        .collect();
    if n == 0 {
        return Ok(Vec::new());
    }
    if pool.is_empty() {
        return Err(TpmcError::InvalidArgument(
            "abep_core.flux_weighted_entry: no sampled molecule crosses the aperture (v_z > 0); the reference \
             fails here too (probabilities are NaN)"
                .to_string(),
        ));
    }
    let mut cdf = Vec::with_capacity(pool.len());
    let mut acc = 0.0;
    for v in &pool {
        acc += v[2];
        cdf.push(acc);
    }
    let total = acc;
    let mut out = Vec::with_capacity(n);
    for _ in 0..n {
        let u = rng.uniform() * total;
        // first index with cdf > u (searchsorted side='right')
        let idx = cdf.partition_point(|&c| c <= u).min(pool.len() - 1);
        out.push(pool[idx]);
    }
    Ok(out)
}

/// Reference `_diffuse` for one molecule: cosine-law re-emission at T_w about the unit `normal`.
#[inline]
pub fn diffuse_one(rng: &mut Rng, vth: f64, normal: &V3) -> V3 {
    let vn = vth * (-2.0 * rng.uniform_range(1e-12, 1.0).ln()).sqrt();
    let vt1 = vth * rng.standard_normal();
    let vt2 = vth * rng.standard_normal();
    let mut t1 = cross(normal, &[0.0, 0.0, 1.0]);
    let nrm = dot(&t1, &t1).sqrt();
    if nrm < 1e-9 {
        t1 = cross(normal, &[1.0, 0.0, 0.0]);
    }
    let nrm = dot(&t1, &t1).sqrt();
    t1 = [t1[0] / nrm, t1[1] / nrm, t1[2] / nrm];
    let t2 = cross(normal, &t1);
    [
        vn * normal[0] + vt1 * t1[0] + vt2 * t2[0],
        vn * normal[1] + vt1 * t1[1] + vt2 * t2[1],
        vn * normal[2] + vt1 * t1[2] + vt2 * t2[2],
    ]
}

pub fn diffuse(rng: &mut Rng, normals: &[V3], t_w: f64, m: f64) -> Vec<V3> {
    let vth = (K_B * t_w / m).sqrt();
    normals.iter().map(|nr| diffuse_one(rng, vth, nr)).collect()
}

pub fn check_cll_alphas(alpha_n: f64, alpha_t: f64) -> Result<(), TpmcError> {
    // The reference raises (math domain error) for alpha_t outside [0, 1] and returns NaN for alpha_n outside;
    // abep_core refuses both (documented divergence).
    for (name, a) in [("alpha_n", alpha_n), ("alpha_t", alpha_t)] {
        if !(0.0..=1.0).contains(&a) {
            return Err(TpmcError::InvalidArgument(format!(
                "abep_core CLL: {} must lie in [0, 1], got {}",
                name, a
            )));
        }
    }
    Ok(())
}

/// Reference `_cll` for one molecule (Lord 1991 sampling exactly as coded in the reference). `normal` points into
/// the gas.
#[inline]
pub fn cll_one(rng: &mut Rng, v_in: &V3, normal: &V3, vmp: f64, alpha_n: f64, alpha_t: f64) -> V3 {
    let vn = dot(v_in, normal);
    let vt = [v_in[0] - vn * normal[0], v_in[1] - vn * normal[1], v_in[2] - vn * normal[2]];
    let sd = vmp / 2f64.sqrt();
    let (ka, kb) = ((1.0 - alpha_t).sqrt(), alpha_t.sqrt());
    let noise = [sd * rng.standard_normal(), sd * rng.standard_normal(), sd * rng.standard_normal()];
    let mut vt_out = [ka * vt[0] + kb * noise[0], ka * vt[1] + kb * noise[1], ka * vt[2] + kb * noise[2]];
    let proj = dot(&vt_out, normal);
    vt_out = [vt_out[0] - proj * normal[0], vt_out[1] - proj * normal[1], vt_out[2] - proj * normal[2]];
    let r = (-alpha_n * rng.uniform_range(1e-12, 1.0).ln()).sqrt();
    let th = 2.0 * std::f64::consts::PI * rng.uniform_range(0.0, 1.0);
    let vm = (1.0 - alpha_n).sqrt() * vn.abs() / vmp;
    let vn_out = (r * r + vm * vm + 2.0 * r * vm * th.cos()).sqrt() * vmp;
    [vt_out[0] + vn_out * normal[0], vt_out[1] + vn_out * normal[1], vt_out[2] + vn_out * normal[2]]
}

pub fn cll(
    rng: &mut Rng,
    v_in: &[V3],
    normals: &[V3],
    t_w: f64,
    m: f64,
    alpha_n: f64,
    alpha_t: f64,
) -> Result<Vec<V3>, TpmcError> {
    check_cll_alphas(alpha_n, alpha_t)?;
    if v_in.len() != normals.len() {
        return Err(TpmcError::InvalidArgument("abep_core.cll: v_in and normal must have the same length".into()));
    }
    let vmp = (2.0 * K_B * t_w / m).sqrt();
    Ok(v_in.iter().zip(normals).map(|(v, nr)| cll_one(rng, v, nr, vmp, alpha_n, alpha_t)).collect())
}

pub struct TraceParams {
    pub r: f64,
    pub l: f64,
    pub alpha: f64,
    pub t_w: f64,
    pub m: f64,
    pub max_hits: usize,
    pub scattering: Scattering,
    pub alpha_n: Option<f64>,
    pub alpha_t: Option<f64>,
    pub unresolved_tol: f64,
    pub max_hits_cap: usize,
}

pub struct TraceResult {
    pub collected: Vec<bool>,
    pub v: Vec<V3>,
    pub hits: Vec<i64>,
    pub back: Vec<bool>,
    pub unresolved: f64,
}

/// Reference `trace_channel`. The reference advances every alive molecule by one flight per step, all in lockstep,
/// so an alive molecule has made exactly `done_steps` flights; tracing each molecule up to `budget` flights per pass
/// is therefore the same rule. After each pass the unresolved fraction is evaluated and the budget doubles (capped)
/// exactly as in the reference; molecules still inside are reported unresolved, never assigned.
pub fn trace_channel(rng: &mut Rng, v0: &[V3], p: &TraceParams) -> Result<TraceResult, TpmcError> {
    if p.max_hits < 1 {
        return Err(TpmcError::InvalidArgument(
            "abep_core.trace_channel: max_hits must be >= 1 (the reference never terminates for max_hits = 0)".into(),
        ));
    }
    let (alpha_n, alpha_t) = (p.alpha_n.unwrap_or(p.alpha), p.alpha_t.unwrap_or(p.alpha));
    if p.scattering == Scattering::Cll {
        check_cll_alphas(alpha_n, alpha_t)?;
    }
    let n = v0.len();
    let (r_ch, l_ch) = (p.r, p.l);
    // entry position: r = R sqrt(U), phi = U(0, 2 pi), z = 0
    let mut pos: Vec<V3> = (0..n)
        .map(|_| {
            let r = r_ch * rng.uniform_range(0.0, 1.0).sqrt();
            let ph = rng.uniform_range(0.0, 2.0 * std::f64::consts::PI);
            [r * ph.cos(), r * ph.sin(), 0.0]
        })
        .collect();
    let mut v: Vec<V3> = v0.to_vec();
    let mut alive = vec![true; n];
    let mut collected = vec![false; n];
    let mut back = vec![false; n];
    let mut hits = vec![0i64; n];
    let mut steps = vec![0usize; n];
    let vth_w = (K_B * p.t_w / p.m).sqrt();
    let vmp_w = (2.0 * K_B * p.t_w / p.m).sqrt();
    let mut budget = p.max_hits;
    let unresolved;
    loop {
        for i in 0..n {
            while alive[i] && steps[i] < budget {
                steps[i] += 1;
                let (pv, vv) = (pos[i], v[i]);
                let a = vv[0] * vv[0] + vv[1] * vv[1];
                let b = 2.0 * (pv[0] * vv[0] + pv[1] * vv[1]);
                let c = pv[0] * pv[0] + pv[1] * pv[1] - r_ch * r_ch;
                let disc = np_maximum(b * b - 4.0 * a * c, 0.0);
                let t_wall = if a > 1e-30 { (-b + disc.sqrt()) / (2.0 * np_maximum(a, 1e-30)) } else { f64::INFINITY };
                let t_back = if vv[2] > 0.0 { (l_ch - pv[2]) / vv[2] } else { f64::INFINITY };
                let t_front = if vv[2] < 0.0 { (0.0 - pv[2]) / vv[2] } else { f64::INFINITY };
                let t = np_minimum(np_minimum(t_wall, t_back), t_front);
                let pw = [pv[0] + vv[0] * t, pv[1] + vv[1] * t, pv[2] + vv[2] * t];
                pos[i] = pw;
                let exit_back = (t_back <= t_wall) && (t_back <= t_front);
                let exit_front = (t_front < t_wall) && (t_front < t_back);
                if exit_back {
                    collected[i] = true;
                    alive[i] = false;
                } else if exit_front {
                    back[i] = true;
                    alive[i] = false;
                } else {
                    hits[i] += 1;
                    let normal = [-pw[0] / r_ch, -pw[1] / r_ch, -0.0 / r_ch];
                    v[i] = match p.scattering {
                        Scattering::Cll => cll_one(rng, &vv, &normal, vmp_w, alpha_n, alpha_t),
                        Scattering::Maxwell => {
                            if rng.uniform_range(0.0, 1.0) < p.alpha {
                                diffuse_one(rng, vth_w, &normal)
                            } else {
                                let vn = dot(&vv, &normal);
                                [vv[0] - 2.0 * vn * normal[0], vv[1] - 2.0 * vn * normal[1], vv[2] - 2.0 * vn * normal[2]]
                            }
                        }
                    };
                }
            }
        }
        let n_alive = alive.iter().filter(|&&x| x).count();
        let frac = if n == 0 { f64::NAN } else { n_alive as f64 / n as f64 };
        if frac <= p.unresolved_tol || budget >= p.max_hits_cap || n_alive == 0 {
            unresolved = frac;
            break;
        }
        budget = std::cmp::min(budget * 2, p.max_hits_cap);
    }
    Ok(TraceResult { collected, v, hits, back, unresolved })
}

/// Reference `clausing_transmission`: diffuse entry about +z at T_w, Maxwell trace with the reference defaults
/// (max_hits 200, cap 5000, tol 1e-3), returns the collected fraction (NaN for n = 0, as numpy's mean of empty).
pub fn clausing_transmission(rng: &mut Rng, r: f64, l: f64, alpha: f64, t_w: f64, m: f64, n: usize) -> Result<f64, TpmcError> {
    let normals = vec![[0.0, 0.0, 1.0]; n];
    let v0 = diffuse(rng, &normals, t_w, m);
    let p = TraceParams {
        r,
        l,
        alpha,
        t_w,
        m,
        max_hits: 200,
        scattering: Scattering::Maxwell,
        alpha_n: None,
        alpha_t: None,
        unresolved_tol: 1e-3,
        max_hits_cap: 5000,
    };
    let res = trace_channel(rng, &v0, &p)?;
    if n == 0 {
        return Ok(f64::NAN);
    }
    Ok(res.collected.iter().filter(|&&c| c).count() as f64 / n as f64)
}

#[cfg(test)]
mod tests {
    use super::*;

    const AMU: f64 = 1.66053906660e-27;

    fn params(l: f64, alpha: f64, scat: Scattering) -> TraceParams {
        TraceParams {
            r: 5e-3,
            l,
            alpha,
            t_w: 350.0,
            m: 28.0 * AMU,
            max_hits: 200,
            scattering: scat,
            alpha_n: None,
            alpha_t: None,
            unresolved_tol: 1e-3,
            max_hits_cap: 5000,
        }
    }

    #[test]
    fn partition_and_exit_direction() {
        let mut rng = Rng::new(3);
        let v0 = flux_weighted_entry(&mut rng, 5000, 7788.0, 0.05, 950.0, 28.0 * AMU).unwrap();
        for scat in [Scattering::Maxwell, Scattering::Cll] {
            let res = trace_channel(&mut rng, &v0, &params(0.05, 0.7, scat)).unwrap();
            let mut n_alive = 0;
            for i in 0..v0.len() {
                assert!(!(res.collected[i] && res.back[i]));
                if res.collected[i] {
                    assert!(res.v[i][2] > 0.0);
                } else if res.back[i] {
                    assert!(res.v[i][2] < 0.0);
                } else {
                    n_alive += 1;
                }
            }
            assert_eq!(res.unresolved, n_alive as f64 / v0.len() as f64);
        }
    }

    #[test]
    fn zero_length_channel_collects_everything_untouched() {
        let mut rng = Rng::new(5);
        let v0 = flux_weighted_entry(&mut rng, 1000, 7788.0, 0.0, 950.0, 28.0 * AMU).unwrap();
        let res = trace_channel(&mut rng, &v0, &params(0.0, 1.0, Scattering::Maxwell)).unwrap();
        assert!(res.collected.iter().all(|&c| c));
        assert!(res.hits.iter().all(|&h| h == 0));
        assert_eq!(res.v, v0);
    }

    #[test]
    fn specular_limits_preserve_axial_velocity() {
        let mut rng = Rng::new(9);
        let v0 = flux_weighted_entry(&mut rng, 2000, 7788.0, 0.0, 950.0, 28.0 * AMU).unwrap();
        for scat in [Scattering::Maxwell, Scattering::Cll] {
            let res = trace_channel(&mut rng, &v0, &params(0.1, 0.0, scat)).unwrap();
            for i in 0..v0.len() {
                assert!(res.collected[i]);
                assert_eq!(res.v[i][2], v0[i][2]);
                let (s0, s1) = (dot(&v0[i], &v0[i]).sqrt(), dot(&res.v[i], &res.v[i]).sqrt());
                assert!((s0 - s1).abs() <= 1e-9 * s0);
            }
        }
    }

    #[test]
    fn forced_budget_reports_unresolved() {
        let mut rng = Rng::new(11);
        let v0 = flux_weighted_entry(&mut rng, 2000, 7788.0, 0.0, 950.0, 28.0 * AMU).unwrap();
        let mut p = params(0.2, 1.0, Scattering::Maxwell);
        p.max_hits = 2;
        p.max_hits_cap = 4;
        let res = trace_channel(&mut rng, &v0, &p).unwrap();
        assert!(res.unresolved > 0.0);
        for i in 0..v0.len() {
            if !res.collected[i] && !res.back[i] {
                assert_eq!(res.hits[i], 4);
            }
        }
        p.max_hits = 0;
        assert!(trace_channel(&mut rng, &v0, &p).is_err());
    }

    #[test]
    fn empty_input_gives_nan_unresolved() {
        let mut rng = Rng::new(1);
        let res = trace_channel(&mut rng, &[], &params(0.05, 0.5, Scattering::Maxwell)).unwrap();
        assert!(res.collected.is_empty() && res.unresolved.is_nan());
    }

    #[test]
    fn diffuse_moments_follow_cosine_law() {
        // half-range Rayleigh normal component: E[vn] = vth sqrt(pi/2), E[vn^2] = 2 vth^2; tangential E = vth^2 each
        let mut rng = Rng::new(21);
        let n = 200_000;
        let normals = vec![[0.0, 0.0, 1.0]; n];
        let m = 28.0 * AMU;
        let out = diffuse(&mut rng, &normals, 350.0, m);
        let vth = (K_B * 350.0 / m).sqrt();
        let mean_vn: f64 = out.iter().map(|v| v[2]).sum::<f64>() / n as f64;
        let mean_vn2: f64 = out.iter().map(|v| v[2] * v[2]).sum::<f64>() / n as f64;
        let mean_vt2: f64 = out.iter().map(|v| v[0] * v[0] + v[1] * v[1]).sum::<f64>() / n as f64;
        assert!(out.iter().all(|v| v[2] > 0.0));
        assert!((mean_vn / (vth * (std::f64::consts::PI / 2.0).sqrt()) - 1.0).abs() < 0.01);
        assert!((mean_vn2 / (2.0 * vth * vth) - 1.0).abs() < 0.01);
        assert!((mean_vt2 / (2.0 * vth * vth) - 1.0).abs() < 0.01);
    }

    #[test]
    fn cll_zero_accommodation_is_specular() {
        let mut rng = Rng::new(4);
        let vin = vec![[100.0, -300.0, 7000.0], [-50.0, -20.0, 6000.0]];
        let normals = vec![[-1.0, 0.0, -0.0], [0.0, 1.0, -0.0]];
        let out = cll(&mut rng, &vin, &normals, 350.0, 28.0 * AMU, 0.0, 0.0).unwrap();
        for i in 0..2 {
            let vn = dot(&vin[i], &normals[i]);
            for k in 0..3 {
                let spec = vin[i][k] - 2.0 * vn * normals[i][k];
                assert!((out[i][k] - spec).abs() <= 1e-9 * 7000.0);
            }
        }
        assert!(cll(&mut rng, &vin, &normals, 350.0, 28.0 * AMU, 1.2, 0.0).is_err());
    }
}
