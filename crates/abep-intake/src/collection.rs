//! Intake collection, drag and the first-order compression step: `abep_sim/intake.py` collection / compress /
//! passive_compression (PARITY-C-ABEP_SIM_INTAKE_PY-V1).
//!
//! The parametric branch and the compressor are first-order, parameter-driven models whose default coefficients keep
//! their committed status (no promotion, RM-R27). The TPMC branch evaluates the frozen intake surface v1.

use crate::constants::K_B;
use crate::freestream::FreeStream;
use crate::surface::FrozenIntakeSurfaces;
use crate::tpmc_response::pydiv;
use crate::{py_max, refuse};
use abep_types::{AbepError, AbepResult};
use std::collections::BTreeMap;
use std::f64::consts::PI;

/// Reference `IntakeParams` (defaults identical).
#[derive(Debug, Clone, PartialEq)]
pub struct IntakeParams {
    pub area_m2: f64,
    pub eta_c_specular: f64,
    pub eta_c_diffuse: f64,
    pub accommodation: f64,
    pub off_axis_deg: f64,
    pub cd: f64,
    pub body_area_m2: f64,
    pub mass_per_m2: f64,
    pub mass_fixed: f64,
    pub use_tpmc: bool,
    pub scattering: String,
    pub l_over_d: f64,
    pub phi: f64,
    pub d_mm: f64,
    pub filter: bool,
}

impl Default for IntakeParams {
    fn default() -> Self {
        IntakeParams {
            area_m2: 1.0,
            eta_c_specular: 0.45,
            eta_c_diffuse: 0.25,
            accommodation: 0.5,
            off_axis_deg: 0.0,
            cd: 2.2,
            body_area_m2: 0.0,
            mass_per_m2: 2.5,
            mass_fixed: 1.0,
            use_tpmc: false,
            scattering: "maxwell".into(),
            l_over_d: 10.0,
            phi: 0.85,
            d_mm: 10.0,
            filter: false,
        }
    }
}

/// Reference `CompressorParams` (defaults identical). `None` stands for the reference's unset (`None`) values.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CompressorParams {
    pub ratio: f64,
    pub area_ratio: f64,
    pub t_out_k: f64,
    pub p_base_w: f64,
    pub p_per_mgps_per_ln: f64,
    pub max_ratio: f64,
    pub anode_conductance_m3_s: Option<f64>,
    pub backflow_frac: f64,
    pub mass_base_kg: f64,
    pub mass_per_ln: f64,
}

impl Default for CompressorParams {
    fn default() -> Self {
        CompressorParams {
            ratio: 500.0,
            area_ratio: 10.0,
            t_out_k: 350.0,
            p_base_w: 40.0,
            p_per_mgps_per_ln: 12.0,
            max_ratio: 5000.0,
            anode_conductance_m3_s: None,
            backflow_frac: 0.0,
            mass_base_kg: 3.0,
            mass_per_ln: 0.6,
        }
    }
}

/// Reference `collection` output dict.
#[derive(Debug, Clone, PartialEq)]
pub struct Collection {
    pub eta_c: f64,
    pub mdot_incident: f64,
    pub mdot_collected: f64,
    pub c_d: f64,
    pub drag_n: f64,
    pub intake_mass_kg: f64,
    /// passive compression ratio of the TPMC surface (None in the parametric branch)
    pub passive_override: Option<f64>,
    /// collected mass flow per species, table order (None in the parametric branch)
    pub mdot_collected_species: Option<Vec<(String, f64)>>,
}

/// Reference `compress` output dict.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Compression {
    pub p_out_pa: f64,
    pub p_passive_pa: f64,
    pub passive_ratio: f64,
    pub active_ratio: f64,
    pub ratio_effective: f64,
    pub mdot_net: f64,
    pub n_out: f64,
    pub comp_power_w: f64,
    pub comp_mass_kg: f64,
    /// the reference's raw flag `active_ratio <= max_ratio` (not an assessment)
    pub comp_feasible: bool,
}

/// Reference `collection(intake, atm)`. The TPMC branch needs the frozen surfaces (reference: the module cache filled
/// from intake_surface_v1); without them it is INCOMPLETE_EVIDENCE, never the parametric fallback.
pub fn collection(
    intake: &IntakeParams,
    fs: &FreeStream,
    surfaces: Option<&FrozenIntakeSurfaces>,
) -> AbepResult<Collection> {
    let (eta_c, cd, m_int, passive_override, species) = if intake.use_tpmc {
        let surfaces = surfaces.ok_or_else(|| AbepError::IncompleteEvidence {
            message: "SURFACE_REQUIRED: use_tpmc needs the frozen intake surface v1 (FrozenIntakeSurfaces::load)"
                .into(),
        })?;
        let fr: BTreeMap<String, f64> =
            [("O".to_string(), fs.f_o), ("N2".to_string(), fs.f_n2), ("O2".to_string(), fs.f_o2)].into_iter().collect();
        // no clamping (A9.13 S6.2 / FE-01): accommodation and pointing go to the frozen surface as given
        let r = surfaces.get(&intake.scattering)?.eval(
            intake.l_over_d,
            intake.phi,
            intake.accommodation,
            intake.off_axis_deg,
            Some(&fr),
        )?;
        let mut m_int = r.mass_kg * (intake.area_m2 / 0.5); // the surface was built at 0.5 m2
        if intake.filter {
            m_int += 0.8 * intake.area_m2;
        }
        (r.eta_c, r.c_d, m_int, Some(r.cr_passive), Some(r.species))
    } else {
        let mut eta_c =
            (1.0 - intake.accommodation) * intake.eta_c_specular + intake.accommodation * intake.eta_c_diffuse;
        eta_c *= intake.off_axis_deg.to_radians().cos().powf(2.0);
        (eta_c, intake.cd, intake.mass_per_m2 * intake.area_m2 + intake.mass_fixed, None, None)
    };
    let mdot_inc = fs.flux_kg_m2_s * intake.area_m2;
    let mdot_col = eta_c * mdot_inc;
    let mdot_col_sp = species
        .filter(|s| !s.is_empty())
        .map(|s| s.into_iter().map(|(name, v)| (name, v.eta_c * v.mass_fraction * mdot_inc)).collect::<Vec<_>>());
    let a_front = py_max(intake.area_m2, 0.0) + intake.body_area_m2;
    let v = fs.v_rel_or_v();
    let drag = 0.5 * fs.rho * v.powf(2.0) * cd * a_front;
    Ok(Collection {
        eta_c,
        mdot_incident: mdot_inc,
        mdot_collected: mdot_col,
        c_d: cd,
        drag_n: drag,
        intake_mass_kg: m_int,
        passive_override,
        mdot_collected_species: mdot_col_sp,
    })
}

/// Reference `passive_compression(comp, atm, eta_c)`: free-molecular ram compression of a passive intake,
/// n_p / n = 4 eta_c V / c_bar x A_in / A_throat.
pub fn passive_compression(comp: &CompressorParams, fs: &FreeStream, eta_c: f64) -> AbepResult<f64> {
    let c_bar = pydiv(8.0 * K_B * comp.t_out_k, PI * fs.m_mean, "the reservoir mean thermal speed")?.sqrt();
    Ok(pydiv(4.0 * eta_c * fs.v, c_bar, "the passive ratio")? * comp.area_ratio)
}

/// Reference `compress(comp, atm, mdot_col, eta_c, passive_override)`: total ratio = passive (free) x active.
/// `passive_override` and `comp.anode_conductance_m3_s` must be finite and > 0 when given (contract DIV-01 / DIV-02).
pub fn compress(
    comp: &CompressorParams,
    fs: &FreeStream,
    mdot_col: f64,
    eta_c: f64,
    passive_override: Option<f64>,
) -> AbepResult<Compression> {
    let passive = match passive_override {
        Some(p) if p.is_finite() && p > 0.0 => p,
        Some(p) => {
            return Err(refuse(
                "PASSIVE_OVERRIDE_INVALID",
                format!("compress: passive_override must be finite and > 0, got {p}"),
            ))
        }
        None => passive_compression(comp, fs, eta_c)?,
    };
    let by_passive = |a: f64| -> AbepResult<f64> {
        if passive == 0.0 {
            return Err(refuse("PASSIVE_ZERO", "compress: float division by zero (passive compression ratio 0)"));
        }
        Ok(a / passive)
    };
    let mdot_net = mdot_col * (1.0 - comp.backflow_frac);
    let (p_out, ratio_eff, active) = match comp.anode_conductance_m3_s {
        Some(c) if c.is_finite() && c > 0.0 => {
            // molecular-flow network: Q = (mdot/m) k T = p_res C
            let p_out = pydiv(mdot_net, fs.m_mean, "the throughput")? * K_B * comp.t_out_k / c;
            let ratio_eff = py_max(pydiv(p_out, fs.n * K_B * comp.t_out_k, "the effective ratio")?, passive);
            let p_out = fs.n * ratio_eff * K_B * comp.t_out_k;
            (p_out, ratio_eff, py_max(by_passive(ratio_eff)?, 1.0))
        }
        Some(c) => {
            return Err(refuse(
                "CONDUCTANCE_INVALID",
                format!("compress: anode_conductance_m3_s must be finite and > 0, got {c}"),
            ))
        }
        None => {
            let active = py_max(by_passive(comp.ratio)?, 1.0);
            let ratio_eff = py_max(comp.ratio, passive); // the passive stage cannot be "un-compressed"
            (fs.n * ratio_eff * K_B * comp.t_out_k, ratio_eff, active)
        }
    };
    let n_out = fs.n * ratio_eff;
    let p_passive = fs.n * passive * K_B * comp.t_out_k;
    let ln_a = active.ln();
    let power = (if active > 1.0 { comp.p_base_w } else { 0.0 }) + comp.p_per_mgps_per_ln * (mdot_net * 1e6) * ln_a;
    let mass = (if active > 1.0 { comp.mass_base_kg } else { 0.5 }) + comp.mass_per_ln * ln_a;
    Ok(Compression {
        p_out_pa: p_out,
        p_passive_pa: p_passive,
        passive_ratio: passive,
        active_ratio: active,
        ratio_effective: ratio_eff,
        mdot_net,
        n_out,
        comp_power_w: power,
        comp_mass_kg: mass,
        comp_feasible: active <= comp.max_ratio,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::constants::AMU;
    use crate::message_key;

    fn fs() -> FreeStream {
        let m = 26.0 * AMU;
        FreeStream {
            n: 8e15,
            rho: 8e15 * m,
            v: 7790.0,
            v_rel: None,
            t: 950.0,
            m_mean: m,
            f_o: 0.46,
            f_n2: 0.51,
            f_o2: 0.03,
            flux_kg_m2_s: 8e15 * m * 7790.0,
        }
    }

    #[test]
    fn parametric_collection_balances_mass() {
        let c = collection(&IntakeParams::default(), &fs(), None).unwrap();
        assert_eq!(c.mdot_collected, c.eta_c * c.mdot_incident);
        assert_eq!(c.eta_c, 0.5 * 0.45 + 0.5 * 0.25);
        assert!(c.passive_override.is_none() && c.mdot_collected_species.is_none());
        assert_eq!(c.intake_mass_kg, 2.5 + 1.0);
    }

    #[test]
    fn tpmc_branch_without_frozen_surface_is_incomplete_evidence() {
        let p = IntakeParams { use_tpmc: true, ..IntakeParams::default() };
        let e = collection(&p, &fs(), None).unwrap_err();
        assert_eq!(e.status(), abep_types::EvalStatus::IncompleteEvidence);
    }

    #[test]
    fn compress_branches_and_refusals() {
        let comp = CompressorParams::default();
        let r = compress(&comp, &fs(), 1e-6, 0.35, None).unwrap();
        assert!(r.active_ratio >= 1.0 && r.ratio_effective >= r.passive_ratio);
        assert_eq!(r.comp_feasible, r.active_ratio <= comp.max_ratio);
        assert_eq!(r.mdot_net, 1e-6);
        let small = CompressorParams { ratio: 1.0, ..comp };
        let r = compress(&small, &fs(), 1e-6, 0.35, None).unwrap();
        assert_eq!((r.active_ratio, r.comp_power_w, r.comp_mass_kg), (1.0, 0.0, 0.5));
        let k = |r: AbepResult<Compression>| message_key(&r.unwrap_err()).unwrap().to_string();
        assert_eq!(k(compress(&comp, &fs(), 1e-6, 0.0, None)), "PASSIVE_ZERO");
        assert_eq!(k(compress(&comp, &fs(), 1e-6, 0.35, Some(0.0))), "PASSIVE_OVERRIDE_INVALID");
        let bad = CompressorParams { anode_conductance_m3_s: Some(-1.0), ..comp };
        assert_eq!(k(compress(&bad, &fs(), 1e-6, 0.35, None)), "CONDUCTANCE_INVALID");
        let cond = CompressorParams { anode_conductance_m3_s: Some(1e-4), backflow_frac: 0.3, ..comp };
        let r = compress(&cond, &fs(), 1e-6, 0.35, Some(60.0)).unwrap();
        assert!((r.mdot_net + 1e-6 * 0.3 - 1e-6).abs() <= 1e-18);
    }
}
