//! TPMC intake response layer: `abep_sim/intake_tpmc.py` intake_response / response_surface / clausing_transmission
//! (PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1, entry points E1-E3).
//!
//! Geometry: a honeycomb of parallel circular channels (diameter d, length L, open fraction phi) filling a ram aperture
//! of area A. Particle tracing is the admitted Kernel-1 library `abep_core` (one `Rng` per call, consumed in the
//! reference's order: entry, forward trace, Clausing back-trace). Parity is STATISTICAL (A9.29 sec. 7).

use crate::constants::{species_mass, K_B};
use crate::freestream::FreeStream;
use crate::{py_max, refuse};
use abep_core::rng::Rng;
use abep_core::tpmc::{self, Scattering, TraceParams};
use abep_types::{AbepError, AbepResult, EvalStatus};
use std::f64::consts::PI;

/// Admitted wall-scattering kernels (reference `SCATTERING_MODELS`).
pub const SCATTERING_MODELS: [&str; 2] = ["maxwell", "cll"];
/// Kernel of the thermal back-trace (reference `K_BACK_SCATTERING`).
pub const K_BACK_SCATTERING: &str = "maxwell";
/// Particles of the Clausing back-trace inside intake_response (reference default n).
pub const CLAUSING_N: usize = 20000;
/// Registered unresolved-particle criterion of the reference (`converged = unresolved <= 1e-3`).
pub const UNRESOLVED_TOL: f64 = 1e-3;
/// Output fields of intake_response in the reference dict order (response_surface appends "species").
pub const RESPONSE_FIELDS: [&str; 16] = [
    "eta_c",
    "C_D",
    "K_back",
    "CR_passive",
    "eta_open",
    "unresolved_fraction",
    "converged",
    "scattering",
    "K_back_scattering",
    "mean_wall_hits",
    "mass_kg",
    "alpha",
    "theta_deg",
    "L_over_d",
    "phi",
    "d_mm",
];

/// Reference `IntakeGeometry` (defaults identical).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct IntakeGeometry {
    pub area_m2: f64,
    pub d_mm: f64,
    pub l_over_d: f64,
    pub phi: f64,
    pub t_wall_k: f64,
    pub wall_thickness_mm: f64,
    pub wall_density_kg_m3: f64,
    pub coating_thickness_um: f64,
    pub coating_density_kg_m3: f64,
    pub support_mass_frac: f64,
    pub filter: bool,
    pub filter_open_frac: f64,
    pub filter_transmission: f64,
    pub filter_mass_per_m2: f64,
}

impl Default for IntakeGeometry {
    fn default() -> Self {
        IntakeGeometry {
            area_m2: 0.5,
            d_mm: 10.0,
            l_over_d: 10.0,
            phi: 0.85,
            t_wall_k: 350.0,
            wall_thickness_mm: 0.15,
            wall_density_kg_m3: 2700.0,
            coating_thickness_um: 2.0,
            coating_density_kg_m3: 2200.0,
            support_mass_frac: 0.35,
            filter: false,
            filter_open_frac: 0.7,
            filter_transmission: 0.6,
            filter_mass_per_m2: 0.8,
        }
    }
}

/// Reference `intake_response` output dict, plus the fail-closed status (Rust only, contract INV-09).
#[derive(Debug, Clone, PartialEq)]
pub struct IntakeResponse {
    pub eta_c: f64,
    pub c_d: f64,
    pub k_back: f64,
    pub cr_passive: f64,
    pub eta_open: f64,
    pub unresolved_fraction: f64,
    pub converged: bool,
    pub scattering: &'static str,
    pub k_back_scattering: &'static str,
    pub mean_wall_hits: f64,
    pub mass_kg: f64,
    pub alpha: f64,
    pub theta_deg: f64,
    pub l_over_d: f64,
    pub phi: f64,
    pub d_mm: f64,
    /// EVALUATED when converged, MODEL_ERROR otherwise (the values are returned as the reference returns them)
    pub status: EvalStatus,
}

/// One response_surface row: an intake_response plus its species label (`"mean"` for the mixture mass).
#[derive(Debug, Clone, PartialEq)]
pub struct SurfaceRowOut {
    pub response: IntakeResponse,
    pub species: String,
}

/// Python float division: ZeroDivisionError on a zero divisor is a refusal here, never inf / NaN.
#[inline]
pub(crate) fn pydiv(a: f64, b: f64, what: &str) -> AbepResult<f64> {
    if b == 0.0 {
        return Err(refuse("ZERO_DIVISION", format!("float division by zero in {what}")));
    }
    Ok(a / b)
}

/// Reference `_check_scattering` (exact, case-sensitive; no fallback).
pub fn check_scattering(scattering: &str) -> AbepResult<Scattering> {
    match scattering {
        "maxwell" => Ok(Scattering::Maxwell),
        "cll" => Ok(Scattering::Cll),
        other => Err(refuse(
            "UNKNOWN_SCATTERING",
            format!("intake_tpmc: unknown wall-scattering model {other:?}; admitted models are {SCATTERING_MODELS:?}"),
        )),
    }
}

/// Reference `_check_accommodation` with alpha_n = alpha_t = alpha (intake_response passes neither).
pub fn check_accommodation(scattering: Scattering, alpha: f64) -> AbepResult<()> {
    if !alpha.is_finite() || !(0.0..=1.0).contains(&alpha) {
        let name = match scattering {
            Scattering::Maxwell => "Maxwell alpha (diffuse fraction)",
            Scattering::Cll => "CLL alpha (used as alpha_n)",
        };
        return Err(refuse(
            "ACCOMMODATION_INVALID",
            format!("intake_tpmc: {name} must be finite and inside [0, 1], got {alpha}"),
        ));
    }
    Ok(())
}

fn check_n(n: usize) -> AbepResult<()> {
    if n < 1 {
        return Err(refuse("N_INVALID", "intake_tpmc: the particle count must be >= 1 (contract DIV-01 / DIV-03)"));
    }
    Ok(())
}

fn kernel(e: tpmc::TpmcError) -> AbepError {
    refuse("TPMC_REFUSED", format!("abep_core: {e}"))
}

/// Reference `clausing_transmission(rng, R, L, alpha, T_w, m, n)`: fraction of thermal plenum-side molecules that
/// leave through the front (Maxwell back-trace), with a fresh `Rng::new(seed)`.
pub fn clausing_transmission(seed: u64, r: f64, l: f64, alpha: f64, t_w: f64, m: f64, n: usize) -> AbepResult<f64> {
    check_accommodation(Scattering::Maxwell, alpha)?;
    check_n(n)?;
    let mut rng = Rng::new(seed);
    tpmc::clausing_transmission(&mut rng, r, l, alpha, t_w, m, n).map_err(kernel)
}

/// Reference `intake_response(geom, atm, alpha, theta_deg, n, seed, scattering, species_mass)`.
/// `species_mass = None` uses the free-stream mean molecular mass; `Some(m)` must be finite and > 0 (DIV-02).
#[allow(clippy::too_many_arguments)]
pub fn intake_response(
    geom: &IntakeGeometry,
    fs: &FreeStream,
    alpha: f64,
    theta_deg: f64,
    n: usize,
    seed: u64,
    scattering: &str,
    species_mass: Option<f64>,
) -> AbepResult<IntakeResponse> {
    let scat = check_scattering(scattering)?;
    check_accommodation(scat, alpha)?;
    check_n(n)?;
    if let Some(m) = species_mass {
        if !(m.is_finite() && m > 0.0) {
            return Err(refuse(
                "SPECIES_MASS_INVALID",
                format!("intake_tpmc: species_mass must be finite and > 0, got {m}"),
            ));
        }
    }
    let mut rng = Rng::new(seed);
    let m = species_mass.unwrap_or(fs.m_mean);
    let v = fs.v_rel_or_v();
    let t = fs.t;
    let r_ch = geom.d_mm * 1e-3 / 2.0;
    let l_ch = geom.l_over_d * geom.d_mm * 1e-3;
    let theta = theta_deg.to_radians();
    pydiv(K_B * t, m, "the entry thermal speed")?;
    let v0 = tpmc::flux_weighted_entry(&mut rng, n, v, theta, t, m).map_err(kernel)?;
    let p = TraceParams {
        r: r_ch,
        l: l_ch,
        alpha,
        t_w: geom.t_wall_k,
        m,
        max_hits: 200,
        scattering: scat,
        alpha_n: None,
        alpha_t: None,
        unresolved_tol: UNRESOLVED_TOL,
        max_hits_cap: 5000,
    };
    let res = tpmc::trace_channel(&mut rng, &v0, &p).map_err(kernel)?;
    let nf = n as f64;
    let eta_open = res.collected.iter().filter(|&&c| c).count() as f64 / nf;
    // momentum per molecule: collected molecules are absorbed, backscattered ones return v_out_z (< 0)
    let mut dp_sum = 0.0;
    for ((v_in, v_out), &back) in v0.iter().zip(&res.v).zip(&res.back) {
        let pz_in = m * v_in[2];
        let pz_out = if back { m * v_out[2] } else { 0.0 };
        dp_sum += pz_in - pz_out;
    }
    let dp_open = dp_sum / nf;
    let vz = v * theta.cos();
    let flux_num = fs.n * vz;
    let f_open = flux_num * dp_open;
    let dp_solid = m * vz + m * pydiv(PI * K_B * geom.t_wall_k, 2.0 * m, "the solid-face momentum")?.sqrt();
    let f_solid = flux_num * dp_solid;
    let f_area = geom.phi * f_open + (1.0 - geom.phi) * f_solid;
    let q = 0.5 * fs.rho * v * v;
    let c_d = pydiv(f_area, q, "C_D")?;
    let mut eta_c = geom.phi * eta_open * theta.cos();
    let mut k_back =
        tpmc::clausing_transmission(&mut rng, r_ch, l_ch, alpha, geom.t_wall_k, m, CLAUSING_N).map_err(kernel)?;
    let phi_eff = if geom.filter {
        eta_c *= geom.filter_open_frac * geom.filter_transmission.powf(0.5);
        k_back *= geom.filter_transmission;
        geom.phi * geom.filter_open_frac
    } else {
        geom.phi
    };
    let c_bar = pydiv(8.0 * K_B * geom.t_wall_k, PI * m, "the wall mean thermal speed")?.sqrt();
    let cr_passive = pydiv(eta_c * v, c_bar / 4.0 * phi_eff * py_max(k_back, 1e-6), "CR_passive")?;
    let n_cells = pydiv(geom.phi * geom.area_m2, PI * r_ch * r_ch, "the channel count")?;
    let wall_area = n_cells * (2.0 * PI * r_ch) * l_ch * 0.5;
    let m_sub = wall_area * geom.wall_thickness_mm * 1e-3 * geom.wall_density_kg_m3;
    let m_coat = (wall_area + geom.area_m2) * geom.coating_thickness_um * 1e-6 * geom.coating_density_kg_m3;
    let m_int = (m_sub + m_coat) * (1.0 + geom.support_mass_frac)
        + if geom.filter { geom.filter_mass_per_m2 * geom.area_m2 } else { 0.0 };
    let hits: i64 = res.hits.iter().sum();
    let unresolved = res.unresolved;
    let converged = unresolved <= UNRESOLVED_TOL;
    Ok(IntakeResponse {
        eta_c,
        c_d,
        k_back,
        cr_passive,
        eta_open,
        unresolved_fraction: unresolved,
        converged,
        scattering: if scat == Scattering::Cll { "cll" } else { "maxwell" },
        k_back_scattering: K_BACK_SCATTERING,
        mean_wall_hits: hits as f64 / nf,
        mass_kg: m_int,
        alpha,
        theta_deg,
        l_over_d: geom.l_over_d,
        phi: geom.phi,
        d_mm: geom.d_mm,
        status: if converged { EvalStatus::Evaluated } else { EvalStatus::ModelError },
    })
}

/// Reference `response_surface(atm, L_over_d, phis, alphas, thetas, n, area_m2, species, scattering)`: one
/// intake_response per point of the product (species, L/d, phi, alpha, theta), each with seed 0 as the reference
/// does. `species = None` (or empty) uses the mixture mass and labels the rows "mean".
#[allow(clippy::too_many_arguments)]
pub fn response_surface(
    fs: &FreeStream,
    l_over_d: &[f64],
    phis: &[f64],
    alphas: &[f64],
    thetas: &[f64],
    n: usize,
    area_m2: f64,
    species: Option<&[String]>,
    scattering: &str,
) -> AbepResult<Vec<SurfaceRowOut>> {
    check_scattering(scattering)?;
    let specs: Vec<(String, Option<f64>)> = match species {
        Some(list) if !list.is_empty() => list
            .iter()
            .map(|s| {
                species_mass(s).map(|m| (s.clone(), Some(m))).ok_or_else(|| {
                    refuse("UNKNOWN_SPECIES", format!("response_surface: no molecular mass for species {s:?}"))
                })
            })
            .collect::<AbepResult<_>>()?,
        _ => vec![("mean".to_string(), None)],
    };
    let mut rows = Vec::new();
    for (sp, msp) in &specs {
        for &ld in l_over_d {
            for &ph in phis {
                for &al in alphas {
                    for &th in thetas {
                        let g = IntakeGeometry { area_m2, l_over_d: ld, phi: ph, ..IntakeGeometry::default() };
                        let r = intake_response(&g, fs, al, th, n, 0, scattering, *msp)?;
                        rows.push(SurfaceRowOut { response: r, species: sp.clone() });
                    }
                }
            }
        }
    }
    Ok(rows)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::constants::AMU;
    use crate::message_key;

    fn fs() -> FreeStream {
        // a self-consistent free stream (n, rho = n m, V, T); not a frozen state
        let m = 28.0 * AMU;
        FreeStream {
            n: 1e16,
            rho: 1e16 * m,
            v: 7800.0,
            v_rel: None,
            t: 900.0,
            m_mean: m,
            f_o: 0.0,
            f_n2: 1.0,
            f_o2: 0.0,
            flux_kg_m2_s: 1e16 * m * 7800.0,
        }
    }

    #[test]
    fn refusals_carry_registered_keys() {
        let g = IntakeGeometry::default();
        let key = |r: AbepResult<IntakeResponse>| message_key(&r.unwrap_err()).unwrap().to_string();
        assert_eq!(key(intake_response(&g, &fs(), 0.5, 0.0, 100, 1, "Maxwell", None)), "UNKNOWN_SCATTERING");
        assert_eq!(key(intake_response(&g, &fs(), 1.5, 0.0, 100, 1, "maxwell", None)), "ACCOMMODATION_INVALID");
        assert_eq!(key(intake_response(&g, &fs(), f64::NAN, 0.0, 100, 1, "cll", None)), "ACCOMMODATION_INVALID");
        assert_eq!(key(intake_response(&g, &fs(), 0.5, 0.0, 0, 1, "cll", None)), "N_INVALID");
        assert_eq!(key(intake_response(&g, &fs(), 0.5, 0.0, 10, 1, "cll", Some(0.0))), "SPECIES_MASS_INVALID");
        let e = clausing_transmission(1, 0.005, 0.05, 2.0, 350.0, 28.0 * AMU, 100).unwrap_err();
        assert_eq!(e.status(), EvalStatus::OutOfDomain);
    }

    #[test]
    fn response_bookkeeping_and_determinism() {
        let g = IntakeGeometry { l_over_d: 5.0, ..IntakeGeometry::default() };
        let a = intake_response(&g, &fs(), 0.8, 2.0, 2000, 42, "maxwell", None).unwrap();
        let b = intake_response(&g, &fs(), 0.8, 2.0, 2000, 42, "maxwell", None).unwrap();
        assert_eq!(a, b);
        assert!((0.0..=1.0).contains(&a.eta_open) && a.eta_open + a.unresolved_fraction <= 1.0);
        assert_eq!(a.eta_c, g.phi * a.eta_open * 2f64.to_radians().cos());
        assert_eq!(a.converged, a.unresolved_fraction <= UNRESOLVED_TOL);
        assert_eq!(a.status == EvalStatus::Evaluated, a.converged);
        assert!(a.c_d > 0.0 && a.k_back > 0.0 && a.k_back <= 1.0 && a.cr_passive > 0.0 && a.mass_kg > 0.0);
    }

    #[test]
    fn forced_unresolved_is_model_error_not_a_value_substitute() {
        // very long channel, pure diffuse: the reference budget doubling stops at the cap with molecules still inside
        let g = IntakeGeometry { l_over_d: 300.0, ..IntakeGeometry::default() };
        let r = intake_response(&g, &fs(), 1.0, 0.0, 500, 3, "maxwell", None).unwrap();
        assert!(!r.converged);
        assert_eq!(r.status, EvalStatus::ModelError);
    }

    #[test]
    fn response_surface_rows_follow_product_order_with_seed_zero() {
        let sp = vec!["O".to_string(), "N2".to_string()];
        let rows =
            response_surface(&fs(), &[3.0, 20.0], &[0.8], &[0.0, 1.0], &[0.0], 300, 0.5, Some(&sp), "cll").unwrap();
        assert_eq!(rows.len(), 8);
        assert_eq!(rows[0].species, "O");
        assert_eq!(rows[4].species, "N2");
        assert_eq!((rows[1].response.l_over_d, rows[1].response.alpha), (3.0, 1.0));
        let g = IntakeGeometry { area_m2: 0.5, l_over_d: 20.0, phi: 0.8, ..IntakeGeometry::default() };
        let direct = intake_response(&g, &fs(), 1.0, 0.0, 300, 0, "cll", species_mass("N2")).unwrap();
        assert_eq!(rows[7].response, direct);
        let bad = vec!["Ar".to_string()];
        let e = response_surface(&fs(), &[3.0], &[0.8], &[0.0], &[0.0], 10, 0.5, Some(&bad), "cll").unwrap_err();
        assert_eq!(message_key(&e), Some("UNKNOWN_SPECIES"));
    }
}
