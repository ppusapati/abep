//! A9.7 F4 plenum / feed synthesis, steady part (`abep_sim/design/plenum_feed.py`; contract
//! PARITY-C-ABEP_SIM_DESIGN_PLENUM_FEED_PY-V1).
//!
//! intake (F1 IF-A1 record, explicit input) -> filter (F2 gap-reflection series) -> compressor (Gaede cascade, linear
//! characteristic p_out = A_c p_in - B_c Q per species) -> plenum (Reservoir physics, O -> O2 wall recombination) ->
//! feed orifice (molecular law, orifice-equivalent area A_eq) -> H-1 inlet. The free-molecular network is linear and
//! solved in closed form; A_eq holding a target pressure by a 90-step log bisection whose failure is reported
//! (R_BISECTION -> MODEL_ERROR), never half-converged. Every pressure above 0.1 Pa is NOT_EVALUATED_OUT_OF_DOMAIN
//! (A9.13 S6.8) and nothing is offered from it.

use crate::compressor::{Ctx, DragCompressor};
use crate::compressor_synthesis as cs;
use crate::error::{fse, key_error, value_error, PyResult};
use crate::filter::{self as fs, FilterStage, InletState, SensitivityCase};
use crate::materials::MaterialsView;
use crate::pyops::{self, np_maximum, np_minimum, py_max, py_min};
use crate::rec::{fmap, fnum, onum, slist, Obj};
use crate::reservoir::Reservoir;
use crate::upstream as u13;
use crate::SPECIES;
use abep_types::constants::{species_mass, K_B, MU_EARTH, R_EARTH};
use abep_types::EvalStatus;
use serde_json::{Map, Value};
use std::f64::consts::PI;

pub const MODE_STRICT: &str = "strict";
pub const MODE_PARAMETRIC: &str = "parametric_sensitivity";
pub const LABEL_PARAMETRIC: &str = "PARAMETRIC_SENSITIVITY";
pub const ST_FEASIBLE: &str = "FEASIBLE_UNDER_PARAMETRIC_SENSITIVITY_INPUTS";
pub const ST_INFEASIBLE: &str = "INFEASIBLE";
pub const ST_OOD: &str = u13::NOT_EVALUATED_OOD;
pub const ST_MODEL_ERROR: &str = "MODEL_ERROR";
pub const ST_NOT_EVALUATED: &str = "NOT_EVALUATED";

pub const R_TARGET_ABOVE_DOMAIN: &str = "PLENUM_TARGET_ABOVE_COMPRESSOR_ADMISSIBLE_OUTLET";
pub const R_STAGE_DOMAIN: &str = "COMPRESSOR_STAGE_OR_INLET_PRESSURE_ABOVE_FREE_MOLECULAR_LIMIT";
pub const R_CHARACTERISTIC: &str = "GAEDE_CHARACTERISTIC_OUTSIDE_K_1_TO_K0";
pub const R_KN_FEED: &str = "FEED_ORIFICE_KNUDSEN_UPPER_BOUND_BELOW_FREE_MOLECULAR_LIMIT";
pub const R_THERMAL: &str = "COMPRESSOR_TEMPERATURE_ABOVE_MATERIAL_SERVICE_LIMIT";
pub const R_DEADHEAD: &str = "TARGET_AT_OR_ABOVE_DEAD_HEAD_PRESSURE";
pub const R_FLOW: &str = "DELIVERED_FLOW_BELOW_REQUIREMENT";
pub const R_UPSTREAM_F1: &str = "F1_INTAKE_INFEASIBLE_AT_STATE";
pub const R_NOT_SETTLED: &str = "TRANSIENT_NOT_SETTLED_WITHIN_WINDOW";
pub const R_SATURATED: &str = "VALVE_SATURATED_SETPOINT_NOT_MAINTAINED";
pub const R_TRAJ_DOMAIN: &str = "TRAJECTORY_PLENUM_PRESSURE_ABOVE_DOMAIN";
pub const R_INTEGRATOR: &str = "INTEGRATOR_FAILED";
pub const R_CONSERVATION: &str = "MASS_CONSERVATION_RESIDUAL_ABOVE_TOLERANCE";
pub const R_BISECTION: &str = "ORIFICE_AREA_BISECTION_RESIDUAL_ABOVE_TOLERANCE_OR_BRACKET_SATURATED";
pub const OOD_REASONS: [&str; 5] = [R_TARGET_ABOVE_DOMAIN, R_STAGE_DOMAIN, R_CHARACTERISTIC, R_KN_FEED, R_TRAJ_DOMAIN];
pub const MODEL_ERROR_REASONS: [&str; 3] = [R_INTEGRATOR, R_CONSERVATION, R_BISECTION];
pub const REASONS: [&str; 14] = [
    R_TARGET_ABOVE_DOMAIN,
    R_STAGE_DOMAIN,
    R_CHARACTERISTIC,
    R_KN_FEED,
    R_THERMAL,
    R_DEADHEAD,
    R_FLOW,
    R_UPSTREAM_F1,
    R_NOT_SETTLED,
    R_SATURATED,
    R_TRAJ_DOMAIN,
    R_INTEGRATOR,
    R_CONSERVATION,
    R_BISECTION,
];

pub const P_DOMAIN_PA: f64 = cs::P_MOLECULAR_LIMIT_PA;
pub const KN_MIN: f64 = cs::KN_FREE_MOLECULAR_MIN;
pub const K_TOL: f64 = 1e-9;
pub const SETTLE_BAND: f64 = 0.02;
pub const RTOL: f64 = 1e-5;
pub const RTOL_REFERENCE: f64 = 1e-8;
pub const ATOL_SCALED: f64 = 1e-11;
pub const MASS_TOL: f64 = 1e-6;
pub const BISECT_ITERS: usize = 90;
pub const A_EQ_BRACKET_M2: (f64, f64) = (1e-12, 1e2);
pub const BISECT_RTOL: f64 = 1e-6;
pub const INTEGRATOR_METHOD: &str = "LSODA";
pub const INTEGRATOR_REFERENCE: &str = "BDF";
pub const T_CHAIN_K: f64 = 350.0;
/// Reservoir.leak_area_m2 code default (uncited parametric case value).
pub const RES_DEFAULT_LEAK_AREA_M2: f64 = 5.0e-8;

/// MODEL_ERROR beats OUT_OF_DOMAIN beats INFEASIBLE; no reasons = feasible under parametric inputs.
pub fn status_from_reasons<S: AsRef<str>>(reasons: &[S]) -> &'static str {
    if reasons.is_empty() {
        return ST_FEASIBLE;
    }
    if reasons.iter().any(|r| MODEL_ERROR_REASONS.contains(&r.as_ref())) {
        return ST_MODEL_ERROR;
    }
    if reasons.iter().any(|r| OOD_REASONS.contains(&r.as_ref())) {
        return ST_OOD;
    }
    ST_INFEASIBLE
}

/// Status -> EvalStatus (INV-P-03).
pub fn status_eval(status: &str) -> EvalStatus {
    match status {
        ST_FEASIBLE | ST_INFEASIBLE => EvalStatus::Evaluated,
        ST_OOD => EvalStatus::OutOfDomain,
        ST_MODEL_ERROR => EvalStatus::ModelError,
        _ => EvalStatus::NotEvaluated,
    }
}

pub fn reason_bit(r: &str) -> i64 {
    REASONS.iter().position(|x| *x == r).map(|i| 1i64 << i).unwrap_or(0)
}

pub fn reasons_from_bits(bits: i64) -> Vec<&'static str> {
    REASONS.iter().copied().filter(|r| bits & reason_bit(r) != 0).collect()
}

/// Circular Kepler period at the state altitude.
pub fn orbital_period_s(alt_km: f64) -> PyResult<f64> {
    let a = R_EARTH + alt_km * 1e3;
    Ok(2.0 * PI * pyops::sqrt(pyops::div(pyops::pow(a, 3.0)?, MU_EARTH)?)?)
}

pub fn cbar(species: &str, t_k: f64) -> PyResult<f64> {
    fs::mean_speed_m_s(species, t_k)
}

pub fn kt_over_m(species: &str, t_k: f64) -> PyResult<f64> {
    pyops::div(K_B * t_k, species_mass(species).map_err(|_| key_error(species))?)
}

fn m_of(s: &str) -> f64 {
    species_mass(s).expect("chain species")
}

/// Per-species triple in SPECIES order.
pub type Sp3 = [f64; 3];

fn sp3_obj(v: &Sp3) -> Value {
    fmap(SPECIES.iter().copied().zip(v.iter().copied()))
}

// ------------------------------------------------------------------------------------------------ intake
/// F1 IF-A1 record scaled to an intake area (explicit plain-data input from the intake layer).
#[derive(Debug, Clone, PartialEq)]
pub struct IntakeState {
    pub candidate: String,
    pub area_m2: f64,
    pub state: String,
    pub scenario: String,
    pub t_k: f64,
    pub mdot_fwd_kgps: Sp3,
    pub p_passive_pa: Sp3,
    pub k_back: Sp3,
    pub f1_status: String,
    pub source: String,
    /// intake_synthesis.state_alt_km(state), carried explicitly
    pub alt_km: f64,
}

impl IntakeState {
    pub fn q_fwd(&self) -> PyResult<Sp3> {
        let mut q = [0.0; 3];
        for (i, s) in SPECIES.iter().enumerate() {
            q[i] = pyops::div(self.mdot_fwd_kgps[i], m_of(s))? * K_B * self.t_k;
        }
        Ok(q)
    }

    /// F1 escape conductance [m^3/s]: e = q_fwd / p_passive.
    pub fn e_f1(&self) -> PyResult<Sp3> {
        let q = self.q_fwd()?;
        let mut e = [0.0; 3];
        for i in 0..3 {
            e[i] = pyops::div(q[i], self.p_passive_pa[i])?;
        }
        Ok(e)
    }

    /// a_s = e_s / (A cbar_s / 4).
    pub fn escape_probability(&self) -> PyResult<Sp3> {
        let e = self.e_f1()?;
        let mut a = [0.0; 3];
        for (i, s) in SPECIES.iter().enumerate() {
            a[i] = pyops::div(e[i], self.area_m2 * cbar(s, self.t_k)? / 4.0)?;
        }
        Ok(a)
    }
}

pub fn f1_candidate_id(area_m2: f64, l_over_d: f64, phi: f64) -> String {
    format!("A{}_Ld{}_phi{}", pyops::py_format_g(area_m2), pyops::py_format_g(l_over_d), pyops::py_format_g(phi))
}

// ------------------------------------------------------------------------------------------------ filter cases
/// Per-species fractions of the F2 stage used by the gap-reflection series model.
#[derive(Debug, Clone, PartialEq)]
pub struct FilterCase {
    pub case_id: String,
    pub label: String,
    pub stage_id: String,
    pub t_f: Sp3,
    pub r_f: Sp3,
    pub t_b: Sp3,
    pub r_b: Sp3,
    pub t_u: Sp3,
    pub r_u: Sp3,
    pub areal_mass_kg_m2: Option<f64>,
    pub overrides: Vec<(String, f64)>,
    pub note: String,
    pub role: String,
}

impl FilterCase {
    pub fn reference_bound_only(&self) -> bool {
        self.role == fs::ROLE_REFERENCE_BOUND
    }

    /// (D_s, E_s): delivered fraction of the forward ram flow and net backflow factor per incident molecule.
    pub fn coefficients(&self, a: &Sp3) -> PyResult<(Sp3, Sp3)> {
        let (mut d, mut e) = ([0.0; 3], [0.0; 3]);
        for i in 0..3 {
            let den = 1.0 - (1.0 - a[i]) * self.r_u[i];
            d[i] = self.t_f[i] + pyops::div(self.t_u[i] * (1.0 - a[i]) * self.r_f[i], den)?;
            e[i] = self.r_b[i] + pyops::div(self.t_u[i] * (1.0 - a[i]) * self.t_b[i], den)? - 1.0;
        }
        Ok((d, e))
    }

    pub fn to_dict(&self) -> Value {
        Obj::new()
            .s("case_id", &self.case_id)
            .s("label", &self.label)
            .s("stage_id", &self.stage_id)
            .set("t_f", sp3_obj(&self.t_f))
            .set("r_f", sp3_obj(&self.r_f))
            .set("t_b", sp3_obj(&self.t_b))
            .set("r_b", sp3_obj(&self.r_b))
            .set("t_u", sp3_obj(&self.t_u))
            .set("r_u", sp3_obj(&self.r_u))
            .set("areal_mass_kg_m2", onum(self.areal_mass_kg_m2))
            .set(
                "overrides",
                Value::Array(
                    self.overrides
                        .iter()
                        .map(|(k, v)| Value::Array(vec![Value::String(k.clone()), fnum(*v)]))
                        .collect(),
                ),
            )
            .s("note", &self.note)
            .s("role", &self.role)
            .b("reference_bound_only", self.reference_bound_only())
            .build()
    }
}

fn unit_inlet() -> InletState {
    let one: Vec<(String, f64)> = SPECIES.iter().map(|s| (s.to_string(), 1.0)).collect();
    InletState {
        mdot_forward_kgps: one.clone(),
        mdot_back_incident_kgps: one,
        back_incident_basis: "normalized unit back-incident flow (fractions only)".into(),
        t_gas_k: Some(T_CHAIN_K),
        incidence: "diffuse_thermal".into(),
        knudsen_number: None,
        label: "NORMALIZED_UNIT_INPUT".into(),
        provenance: "F4 fraction extraction (NORMALIZED_UNIT_INPUT)".into(),
        incident_power_w: None,
        incident_power_source: String::new(),
    }
}

/// Extract the F2 fractions through F2's public API; refuses when F2 refuses.
pub fn filter_case_from_stage(
    case_id: &str,
    stage: &FilterStage,
    case: Option<&SensitivityCase>,
    note: &str,
) -> PyResult<FilterCase> {
    let res = stage.apply(&unit_inlet(), case)?;
    if !res.numeric() {
        return Err(fse(format!("F2 refused ({})", res.status.as_str())));
    }
    let bc = stage.backflow_coupling(Some(T_CHAIN_K), case)?;
    if bc["status"] != "NUMERIC" {
        return Err(fse("F2 backflow coupling refused"));
    }
    let (mut t_f, mut r_f, mut t_b, mut r_b) = ([0.0; 3], [0.0; 3], [0.0; 3], [0.0; 3]);
    for (i, s) in SPECIES.iter().enumerate() {
        let fr = |k: &str| res.species_f64(s, &["fractions_forward", k]).ok_or_else(|| key_error(s));
        let b = bc["species"].get(*s).ok_or_else(|| key_error(s))?;
        let bv = |k: &str| crate::rec::as_f64(&b[k]).unwrap_or(f64::NAN);
        t_f[i] = fr("transmitted")?;
        r_f[i] = fr("reflected")?;
        t_b[i] = bv("to_upstream");
        r_b[i] = bv("reflected_to_plenum");
        if fr("captured")? != 0.0 || fr("converted")? != 0.0 || bv("captured") != 0.0 || bv("converted") != 0.0 {
            return Err(fse("F4 gap model carries loss-free filter cases only (capture / conversion TBD)"));
        }
    }
    let areal =
        if stage.kind == "none" { None } else { case.and_then(|c| fs::sp_get(&c.overrides, "areal_mass_kg_m2")) };
    let mut ov: Vec<(String, f64)> = res
        .overrides_used
        .iter()
        .map(|o| {
            (o["parameter"].as_str().unwrap_or("").to_string(), crate::rec::as_f64(&o["value"]).unwrap_or(f64::NAN))
        })
        .collect();
    ov.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal)));
    Ok(FilterCase {
        case_id: case_id.into(),
        label: res.label.clone(),
        stage_id: stage.stage_id.clone(),
        t_f,
        r_f,
        t_b,
        r_b,
        t_u: t_b,
        r_u: r_b,
        areal_mass_kg_m2: areal,
        overrides: ov,
        note: note.into(),
        role: stage.role.clone(),
    })
}

pub fn filter_none() -> PyResult<FilterCase> {
    filter_case_from_stage(
        "F4-FIL-NONE",
        &FilterStage::none(&SPECIES),
        None,
        "F2 'none' definitional identity: FC-00 REFERENCE BOUND only, never an admissible flight architecture (A9.13 \
S6.5)",
    )
}

/// Species-independent loss-free element with transmission tau both ways (diffuse incidence, reciprocity).
pub fn filter_parametric(tau: f64) -> PyResult<FilterCase> {
    let g = pyops::py_format_g(tau);
    let stage = FilterStage::tbd(
        &format!("F4-PARAM-T{g}"),
        "FC-PARAMETRIC",
        &SPECIES,
        "diffuse_thermal",
        "F4 parametric loss-free screen",
        vec![],
        vec![],
        fs::ROLE_BASELINE,
    )?;
    let mut ov: Vec<(String, f64)> = vec![("face_area_m2".into(), 1.0), ("areal_mass_kg_m2".into(), 1.0)];
    for s in SPECIES {
        for (k, v) in [
            ("tau_f", tau),
            ("tau_b", tau),
            ("alpha_conductance", tau),
            ("capture_f", 0.0),
            ("capture_b", 0.0),
            ("conversion_f", 0.0),
            ("conversion_b", 0.0),
        ] {
            ov.push((format!("{k}.{s}"), v));
        }
    }
    let case = SensitivityCase {
        case_id: format!("SC-F4-T{g}"),
        label: format!("PARAMETRIC_SENSITIVITY (F4 loss-free screen tau={g})"),
        overrides: ov,
        rationale: "F4 bounding case: filter transmission TBD (F2); face area / areal mass placeholders 1 (not used \
by F4 except as a label)"
            .into(),
        regime_assumption: Some("free_molecular".into()),
        temperature_override_k: None,
    };
    case.validate()?;
    let mut fc = filter_case_from_stage(
        &format!("F4-FIL-T{g}"),
        &stage,
        Some(&case),
        "PARAMETRIC_SENSITIVITY: loss-free, species-independent, reciprocal (t_u = t_b)",
    )?;
    fc.areal_mass_kg_m2 = None;
    Ok(fc)
}

pub fn filter_placeholder() -> PyResult<FilterCase> {
    let stage = FilterStage::tbd(
        "F4-PLACEHOLDER",
        "FC-REPO-PLACEHOLDER",
        &SPECIES,
        "diffuse_thermal",
        "repository placeholder filter law",
        vec![],
        vec![],
        fs::ROLE_BASELINE,
    )?;
    let case = fs::placeholder_sensitivity_case(&stage)?;
    filter_case_from_stage(
        "F4-FIL-PLACEHOLDER",
        &stage,
        Some(&case),
        "PLACEHOLDER_NOT_A_FLIGHT_DESIGN via F2 placeholder_sensitivity_case; diffuse intake-side transmission taken = \
tau_b (reciprocity assumption)",
    )
}

/// FC-00 'none' (reference bound only) plus the inert parametric screens and the repository placeholder.
pub fn filter_cases(taus: &[f64]) -> PyResult<Vec<FilterCase>> {
    let mut v = vec![filter_none()?];
    for t in taus {
        v.push(filter_parametric(*t)?);
    }
    v.push(filter_placeholder()?);
    Ok(v)
}

pub fn element_filter_cases(taus: &[f64]) -> PyResult<Vec<FilterCase>> {
    Ok(filter_cases(taus)?.into_iter().filter(|f| !f.reference_bound_only()).collect())
}

// ------------------------------------------------------------------------------------------------ compressor plant
#[derive(Debug, Clone, PartialEq)]
pub struct Stage {
    pub kind: &'static str,
    pub s: f64,
    pub u: f64,
    pub a_term: f64,
    pub k0: Sp3,
}

#[derive(Debug, Clone, PartialEq)]
pub struct CompressorPlant {
    pub design_id: String,
    pub design: Map<String, Value>,
    pub comp: DragCompressor,
}

/// Cascade record (scalar or numpy twin).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Cascade {
    pub p_out: Sp3,
    pub k_min: f64,
    pub k_over_k0_max: f64,
    pub p_stage_max: f64,
    pub p_gas_w: f64,
    pub p_bear_w: f64,
    pub p_el_w: f64,
    pub torque_nm: f64,
    pub mass_kg: f64,
    pub t_comp_k: f64,
}

impl CompressorPlant {
    pub fn from_design(ctx: Ctx, design: &Map<String, Value>, t_k: f64) -> PyResult<CompressorPlant> {
        cs::validate_design(ctx, design)?;
        let a = design["A_turbo_m2"].as_f64().expect("validated");
        let r_default = cs::r_turbo_from_area(a, 0.0)?;
        let comp = DragCompressor {
            turbo_rows: design["N_turbo"].as_f64().expect("validated") as i64,
            turbo_area_m2: a,
            turbo_radius_m: match design.get("R_turbo_m") {
                Some(v) => v.as_f64().unwrap_or(f64::NAN),
                None => r_default,
            },
            n_stages: design["N_drag"].as_f64().expect("validated") as i64,
            rpm: design["rpm"].as_f64().expect("validated"),
            rotor_material: design["rotor_material"].as_str().expect("validated").into(),
            t_gas_k: t_k,
            ..Default::default()
        };
        let id = match design.get("id") {
            Some(Value::String(s)) => s.clone(),
            Some(v) => v.to_string(),
            None => return Err(key_error("id")),
        };
        Ok(CompressorPlant { design_id: id, design: design.clone(), comp })
    }

    /// Stages in flow order, exactly as DragCompressor.run_once builds them.
    pub fn stages(&self) -> PyResult<Vec<Stage>> {
        let c = &self.comp;
        let u_t = c.u_turbo();
        let s_t = c.turbo_k_s * u_t * c.turbo_area_m2;
        let u = c.u();
        let (h, w, l) = (c.h_mm * 1e-3, c.w_mm * 1e-3, c.l_per_stage_m);
        let s0 = c.xi * u * h * w / 2.0;
        let mut out = vec![];
        for _ in 0..c.turbo_rows.max(0) {
            let mut k0 = [0.0; 3];
            for (i, s) in SPECIES.iter().enumerate() {
                k0[i] = pyops::exp(pyops::div(c.turbo_k_k * u_t, c.cbar(m_of(s))?)?)?;
            }
            out.push(Stage {
                kind: "turbo",
                s: s_t,
                u: u_t,
                a_term: c.turbo_area_m2 * c.turbo_blade_area_frac * 2.0,
                k0,
            });
        }
        for _ in 0..c.n_stages.max(0) {
            let mut k0 = [0.0; 3];
            for (i, s) in SPECIES.iter().enumerate() {
                k0[i] = pyops::exp(pyops::div(2.0 * u * l, c.cbar(m_of(s))? * h)? * c.xi)?;
            }
            out.push(Stage { kind: "drag", s: s0, u, a_term: 2.0 * l * w, k0 });
        }
        Ok(out)
    }

    /// Per species (A_c, B_c): p_out = A_c p_in - B_c Q for the whole cascade.
    pub fn characteristic(&self) -> PyResult<[(f64, f64); 3]> {
        let stages = self.stages()?;
        let mut out = [(1.0, 0.0); 3];
        for (i, o) in out.iter_mut().enumerate() {
            let (mut a, mut b) = (1.0, 0.0);
            for st in &stages {
                let k0 = st.k0[i];
                let na = k0 * a;
                let nb = k0 * b + pyops::div(k0 - 1.0, st.s)?;
                a = na;
                b = nb;
            }
            *o = (a, b);
        }
        Ok(out)
    }

    pub fn leak_m3_s(&self) -> f64 {
        self.comp.leak_conductance_m3_s
    }

    pub fn shaft_hz(&self) -> f64 {
        self.comp.rpm / 60.0
    }

    fn drive(&self, mats: &MaterialsView, p_gas: f64, numpy: bool) -> PyResult<(f64, f64, f64, f64, f64)> {
        let c = &self.comp;
        let omega = c.rpm * 2.0 * PI / 60.0;
        let p_bear = c.k_bear_w_per_rads * omega;
        let dv = |a: f64, b: f64| -> PyResult<f64> {
            if numpy {
                Ok(a / b)
            } else {
                pyops::div(a, b)
            }
        };
        let p_el = dv(p_gas + p_bear, c.eta_motor)? + c.p_ctrl_w;
        let torque = dv(p_gas + p_bear, omega)?;
        let rm = mats.get(&c.rotor_material)?;
        let m_rotor = PI
            * pyops::pow(c.rotor_radius_m, 2.0)?
            * c.rotor_disc_thickness_m
            * rm.density
            * c.n_stages as f64
            * 0.7
            + c.turbo_area_m2 * c.turbo_disc_thickness_m * rm.density * c.turbo_rows as f64 * c.turbo_blade_area_frac
            + 0.15 * c.turbo_rows as f64;
        let mass = if numpy {
            m_rotor * (1.0 + c.stator_mass_factor) + c.motor_kg_per_nm * np_maximum(torque, 0.01) + 0.25 + c.bearing_kg
        } else {
            let m_motor = c.motor_kg_per_nm * py_max(torque, 0.01) + 0.25;
            m_rotor * (1.0 + c.stator_mass_factor) + m_motor + c.bearing_kg
        };
        let t = c.t_sink_k + dv(p_gas + p_bear * 0.5 + p_el - (p_gas + p_bear), c.conductance_to_sink_w_k)?;
        Ok((p_bear, p_el, torque, mass, t))
    }

    /// Forward mirror of DragCompressor.run_once at given inlet partial pressures and throughputs (no clipping).
    /// `numpy` selects the vectorized twin's semantics (cascade_arrays): NaN-propagating min / max, IEEE division,
    /// and its mass association.
    pub fn cascade_impl(&self, mats: &MaterialsView, p_in: &Sp3, q: &Sp3, numpy: bool) -> PyResult<Cascade> {
        let c = &self.comp;
        let mut p = *p_in;
        let mut p_gas = 0.0;
        let two_sqrt_pi = 2.0 / PI.sqrt();
        let (mut k_min, mut k_max_rel) = (f64::INFINITY, f64::NEG_INFINITY);
        let mut p_stage_max = pyops::py_sum(p);
        if numpy {
            p_stage_max += 0.0 * p_gas;
        }
        for st in self.stages()? {
            for (i, s) in SPECIES.iter().enumerate() {
                let k0 = st.k0[i];
                let cb = c.cbar(m_of(s))?;
                let denom = if numpy { np_maximum(st.s * p[i], 1e-30) } else { py_max(st.s * p[i], 1e-30) };
                let k = k0 - (k0 - 1.0) * q[i] / denom;
                if numpy {
                    k_min = np_minimum(k_min, k);
                    k_max_rel = np_maximum(k_max_rel, k / k0);
                } else {
                    k_min = py_min(k_min, k);
                    k_max_rel = py_max(k_max_rel, k / k0);
                }
                p_gas += 0.5 * p[i] * (1.0 + k) * (st.u / cb) * st.a_term * two_sqrt_pi * st.u;
                p[i] *= k;
            }
            let tot = pyops::py_sum(p);
            p_stage_max = if numpy { np_maximum(p_stage_max, tot) } else { py_max(p_stage_max, tot) };
        }
        let (p_bear, p_el, torque, mass, t) = self.drive(mats, p_gas, numpy)?;
        Ok(Cascade {
            p_out: p,
            k_min,
            k_over_k0_max: k_max_rel,
            p_stage_max,
            p_gas_w: p_gas,
            p_bear_w: p_bear,
            p_el_w: p_el,
            torque_nm: torque,
            mass_kg: mass,
            t_comp_k: t,
        })
    }

    pub fn cascade(&self, mats: &MaterialsView, p_in: &Sp3, q: &Sp3) -> PyResult<Cascade> {
        self.cascade_impl(mats, p_in, q, false)
    }

    pub fn cascade_record(c: &Cascade) -> Value {
        Obj::new()
            .set("p_out", sp3_obj(&c.p_out))
            .f("p_out_total", c.p_out[0] + c.p_out[1] + c.p_out[2])
            .f("K_min", c.k_min)
            .f("K_over_K0_max", c.k_over_k0_max)
            .f("p_stage_max", c.p_stage_max)
            .f("P_gas_W", c.p_gas_w)
            .f("P_bear_W", c.p_bear_w)
            .f("P_el_W", c.p_el_w)
            .f("torque_Nm", c.torque_nm)
            .f("mass_kg", c.mass_kg)
            .f("T_comp_K", c.t_comp_k)
            .build()
    }
}

// ------------------------------------------------------------------------------------------------ plenum
#[derive(Debug, Clone, PartialEq)]
pub struct Plenum {
    pub volume_m3: f64,
    pub gamma_wall: f64,
    pub wall_case: String,
    pub leak_area_m2: f64,
    pub t_k: f64,
}

impl Plenum {
    /// Refuse a malformed plenum (SW-06): V > 0, 0 <= gamma <= 1, leak >= 0, T > 0, all finite (ValueError).
    pub fn new(volume_m3: f64, gamma_wall: f64, wall_case: &str, leak_area_m2: f64, t_k: f64) -> PyResult<Plenum> {
        for (n, v) in
            [("volume_m3", volume_m3), ("gamma_wall", gamma_wall), ("leak_area_m2", leak_area_m2), ("T_K", t_k)]
        {
            if !v.is_finite() {
                return Err(value_error(format!("Plenum.{n} must be a finite number")));
            }
        }
        if !(volume_m3 > 0.0) {
            return Err(value_error("Plenum.volume_m3 must be > 0"));
        }
        if !(0.0..=1.0).contains(&gamma_wall) {
            return Err(value_error("Plenum.gamma_wall must be in [0, 1]"));
        }
        if !(leak_area_m2 >= 0.0) {
            return Err(value_error("Plenum.leak_area_m2 must be >= 0"));
        }
        if !(t_k > 0.0) {
            return Err(value_error("Plenum.T_K must be > 0"));
        }
        Ok(Plenum { volume_m3, gamma_wall, wall_case: wall_case.into(), leak_area_m2, t_k })
    }

    pub fn wall_area_m2(&self) -> PyResult<f64> {
        let r = pyops::pow(self.volume_m3 / (2.0 * PI), 1.0 / 3.0)?;
        Ok(6.0 * PI * r * r)
    }

    pub fn reservoir(&self, a_eq_m2: f64) -> PyResult<Reservoir> {
        Ok(Reservoir {
            volume_m3: self.volume_m3,
            wall_area_m2: self.wall_area_m2()?,
            wall_material: "Ti6Al4V".into(),
            t_k: self.t_k,
            anode_orifice_area_m2: a_eq_m2,
            anode_orifice_k: 1.0,
            leak_area_m2: self.leak_area_m2,
            upstream_collisions: 0.0,
            upstream_material: "Ti6Al4V".into(),
        })
    }

    pub fn k_rec_m3_s(&self) -> PyResult<f64> {
        Ok(self.gamma_wall * cbar("O", self.t_k)? / 4.0 * self.wall_area_m2()?)
    }

    pub fn leak_m3_s(&self, s: &str) -> PyResult<f64> {
        self.reservoir(1e-6)?.conductance(s, self.leak_area_m2, 1.0)
    }

    pub fn feed_c(&self, s: &str) -> PyResult<f64> {
        self.reservoir(1e-6)?.conductance(s, 1.0, 1.0)
    }

    pub fn leak3(&self) -> PyResult<Sp3> {
        Ok([self.leak_m3_s("O")?, self.leak_m3_s("N2")?, self.leak_m3_s("O2")?])
    }

    pub fn feed3(&self) -> PyResult<Sp3> {
        Ok([self.feed_c("O")?, self.feed_c("N2")?, self.feed_c("O2")?])
    }
}

// ------------------------------------------------------------------------------------------------ chain
/// Node coefficients of one species.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Node {
    pub f: f64,
    pub e: f64,
    pub alpha: f64,
    pub beta: f64,
    pub a_c: f64,
    pub b_c: f64,
    pub d: f64,
    pub e_fac: f64,
    pub a: f64,
}

pub type Coeffs = [Node; 3];

#[derive(Debug, Clone, PartialEq)]
pub struct Chain {
    pub intake: IntakeState,
    pub filt: FilterCase,
    pub plant: CompressorPlant,
    pub plenum: Plenum,
}

impl Chain {
    pub fn node_coefficients(&self, density_factor: f64) -> PyResult<Coeffs> {
        let a = self.intake.escape_probability()?;
        let (d, e) = self.filt.coefficients(&a)?;
        let q = self.intake.q_fwd()?;
        let ch = self.plant.characteristic()?;
        let cl = self.plant.leak_m3_s();
        let mut out =
            [Node { f: 0.0, e: 0.0, alpha: 0.0, beta: 0.0, a_c: 0.0, b_c: 0.0, d: 0.0, e_fac: 0.0, a: 0.0 }; 3];
        for (i, s) in SPECIES.iter().enumerate() {
            let (ac, bc) = ch[i];
            out[i] = Node {
                f: q[i] * d[i] * density_factor,
                e: -e[i] * self.intake.area_m2 * cbar(s, self.intake.t_k)? / 4.0,
                alpha: pyops::div(ac, bc)? + cl,
                beta: pyops::div(1.0, bc)? + cl,
                a_c: ac,
                b_c: bc,
                d: d[i],
                e_fac: e[i],
                a: a[i],
            };
        }
        Ok(out)
    }

    pub fn coeffs_record(co: &Coeffs) -> Value {
        let mut m = Map::new();
        for (i, s) in SPECIES.iter().enumerate() {
            let c = co[i];
            m.insert(
                s.to_string(),
                Obj::new()
                    .f("f", c.f)
                    .f("e", c.e)
                    .f("alpha", c.alpha)
                    .f("beta", c.beta)
                    .f("A_c", c.a_c)
                    .f("B_c", c.b_c)
                    .f("D", c.d)
                    .f("E", c.e_fac)
                    .f("a", c.a)
                    .build(),
            );
        }
        Value::Object(m)
    }
}

/// Steady per-species plenum (p3) and compressor-inlet (p2) partial pressures for orifice-equivalent area a_eq.
/// `checked` = the reference's Python-float operations (q0, k) raise ZeroDivisionError; the rest is numpy-typed.
pub fn solve_pressures(
    co: &Coeffs,
    a_eq: f64,
    k_rec: f64,
    leak: &Sp3,
    feed_c: &Sp3,
    checked: bool,
) -> PyResult<(Sp3, Sp3)> {
    let (mut p3, mut p2) = ([0.0; 3], [0.0; 3]);
    let order = [0usize, 1, 2]; // O, N2, O2
    for i in order {
        let c = co[i];
        let den_n = c.e + c.alpha;
        let (q0, k) = if checked {
            (pyops::div(c.alpha * c.f, den_n)?, pyops::div(c.e * c.beta, den_n)?)
        } else {
            (c.alpha * c.f / den_n, c.e * c.beta / den_n)
        };
        let g = feed_c[i] * a_eq + leak[i];
        p3[i] = match i {
            0 => q0 / (k + g + k_rec),
            2 => (q0 + k_rec * p3[0] * m_of("O") / m_of("O2")) / (k + g),
            _ => q0 / (k + g),
        };
        p2[i] = (c.f + c.beta * p3[i]) / den_n;
    }
    Ok((p3, p2))
}

/// Result of the orifice-area bisection at one point.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AreaSolution {
    pub a_eq: f64,
    pub p_dead: f64,
    pub resid: f64,
    pub ok: bool,
}

/// Orifice-equivalent area holding the plenum at target (log bisection; p3_total decreases with a_eq). A non-finite or
/// non-positive target is refused (ValueError).
pub fn area_for_pressure(
    co: &Coeffs,
    target: f64,
    k_rec: f64,
    leak: &Sp3,
    feed_c: &Sp3,
    checked: bool,
) -> PyResult<AreaSolution> {
    if !target.is_finite() || target <= 0.0 {
        return Err(value_error("plenum target pressure must be finite and > 0"));
    }
    let tot = |p: Sp3| 0.0 + p[0] + p[1] + p[2];
    let p_dead = tot(solve_pressures(co, 0.0, k_rec, leak, feed_c, checked)?.0);
    let ok = target < p_dead;
    let mut lo = A_EQ_BRACKET_M2.0.ln();
    let mut hi = A_EQ_BRACKET_M2.1.ln();
    for _ in 0..BISECT_ITERS {
        let mid = 0.5 * (lo + hi);
        let p = tot(solve_pressures(co, mid.exp(), k_rec, leak, feed_c, checked)?.0);
        if p > target {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    let a = (0.5 * (lo + hi)).exp();
    let p = tot(solve_pressures(co, a, k_rec, leak, feed_c, checked)?.0);
    let resid = (p / target - 1.0).abs();
    Ok(AreaSolution { a_eq: a, p_dead, resid, ok })
}

/// True where the bisection did not converge to BISECT_RTOL or saturated at the bracket (fail closed, SW-06).
pub fn bisection_failed(a_eq: f64, resid: f64) -> bool {
    let sat = a_eq >= A_EQ_BRACKET_M2.1 * (1.0 - 1e-9) || a_eq <= A_EQ_BRACKET_M2.0 * (1.0 + 1e-9);
    !(resid <= BISECT_RTOL) || sat
}

pub fn lambda_upper_m(p3: &Sp3, t_k: f64) -> PyResult<f64> {
    let mut denom = 0.0;
    for (s, sig) in cs::SIGMA_C_M2 {
        let i = SPECIES.iter().position(|x| *x == s).expect("species");
        denom += pyops::div(p3[i], K_B * t_k)? * sig;
    }
    if denom <= 0.0 {
        return Ok(f64::INFINITY);
    }
    pyops::div(1.0, 2.0f64.sqrt() * denom)
}

// ------------------------------------------------------------------------------------------------ steady point
/// The record offered to H-1 and the full operating record at one orifice area.
fn operating_record(
    chain: &Chain,
    mats: &MaterialsView,
    co: &Coeffs,
    a_eq: f64,
    k_rec: f64,
    leak: &Sp3,
    fc: &Sp3,
) -> PyResult<(Map<String, Value>, Vec<&'static str>)> {
    let t = chain.intake.t_k;
    let (p3, p2) = solve_pressures(co, a_eq, k_rec, leak, fc, true)?;
    let mut reasons = vec![];
    let cl = chain.plant.leak_m3_s();
    let (mut q, mut l, mut km) = ([0.0; 3], [0.0; 3], [0.0; 3]);
    for (i, s) in SPECIES.iter().enumerate() {
        q[i] = pyops::div(co[i].a_c * p2[i] - p3[i], co[i].b_c)?;
        l[i] = cl * (p3[i] - p2[i]);
        km[i] = pyops::div(1.0, kt_over_m(s, t)?)?;
    }
    let (mut h1, mut lk, mut comp, mut back, mut net) = ([0.0; 3], [0.0; 3], [0.0; 3], [0.0; 3], [0.0; 3]);
    for i in 0..3 {
        h1[i] = fc[i] * a_eq * p3[i] * km[i];
        lk[i] = leak[i] * p3[i] * km[i];
        comp[i] = q[i] * km[i];
        back[i] = l[i] * km[i];
        net[i] = (co[i].f - co[i].e * p2[i]) * km[i];
    }
    let rec_mass = k_rec * p3[0] * km[0];
    let res_in = pyops::py_max_iter((0..3).map(|i| (net[i] - (comp[i] - back[i])).abs())).expect("3");
    let conv = [-rec_mass, 0.0, rec_mass];
    let res_pl = pyops::py_max_iter((0..3).map(|i| (comp[i] - back[i] - h1[i] - lk[i] + conv[i]).abs())).expect("3");
    let scale = py_max(pyops::py_sum(comp), 1e-300);
    let cas = chain.plant.cascade(mats, &p2, &q)?;
    let mut cr = vec![];
    for i in 0..3 {
        cr.push((pyops::div(cas.p_out[i], p3[i])? - 1.0).abs());
    }
    let cas_res = pyops::py_max_iter(cr).expect("3");
    if cas.k_min < 1.0 - K_TOL || cas.k_over_k0_max > 1.0 + K_TOL {
        reasons.push(R_CHARACTERISTIC);
    }
    let p2t = pyops::py_sum(p2);
    if cas.p_stage_max > P_DOMAIN_PA * (1.0 + 1e-12) || p2t > P_DOMAIN_PA {
        reasons.push(R_STAGE_DOMAIN);
    }
    let p3t = pyops::py_sum(p3);
    let lam = lambda_upper_m(&p3, t)?;
    let d_eq = pyops::sqrt(4.0 * a_eq / PI)?;
    let kn = pyops::div(lam, d_eq)?;
    if kn < KN_MIN {
        reasons.push(R_KN_FEED);
    }
    if cas.t_comp_k > mats.get(&chain.plant.comp.rotor_material)?.t_max_k {
        reasons.push(R_THERMAL);
    }
    let mt = pyops::py_sum(h1);
    let mut nmol = [0.0; 3];
    for (i, s) in SPECIES.iter().enumerate() {
        nmol[i] = pyops::div(h1[i], m_of(s))?;
    }
    let nt = pyops::py_sum(nmol);
    let frac = |v: &Sp3, d: f64| -> PyResult<Value> {
        let mut o = [0.0; 3];
        for i in 0..3 {
            o[i] = pyops::div(v[i], d)?;
        }
        Ok(sp3_obj(&o))
    };
    let offered = Obj::new()
        .set("mdot_s_kgps", sp3_obj(&h1))
        .f("mdot_total_kgps", mt)
        .f("P_Pa", p3t)
        .set("p_s_Pa", sp3_obj(&p3))
        .f("T_K", t)
        .set("x_s_flow_mole", if nt > 0.0 { frac(&nmol, nt)? } else { Value::Null })
        .set("w_s_flow_mass", if mt > 0.0 { frac(&h1, mt)? } else { Value::Null })
        .set("x_s_plenum_mole", frac(&p3, p3t)?)
        .build();
    let mut m = Map::new();
    m.insert("offered".into(), offered);
    m.insert("compressor_inlet_p_s_Pa".into(), sp3_obj(&p2));
    m.insert("compressor_inlet_P_Pa".into(), fnum(p2t));
    m.insert("mdot_compressor_gross_kgps".into(), sp3_obj(&comp));
    m.insert("mdot_compressor_backleak_kgps".into(), sp3_obj(&back));
    m.insert("mdot_plenum_leak_kgps".into(), sp3_obj(&lk));
    m.insert("mdot_recombined_O_kgps".into(), fnum(rec_mass));
    m.insert("mdot_intake_net_kgps".into(), sp3_obj(&net));
    m.insert(
        "conservation_residual_rel".into(),
        Obj::new().f("inlet_node", res_in / scale).f("plenum", res_pl / scale).f("cascade_p_out", cas_res).build(),
    );
    m.insert(
        "compressor".into(),
        Obj::new()
            .f("P_el_W", cas.p_el_w)
            .f("P_gas_W", cas.p_gas_w)
            .f("mass_kg", cas.mass_kg)
            .f("T_comp_K", cas.t_comp_k)
            .f("K_min", cas.k_min)
            .f("K_over_K0_max", cas.k_over_k0_max)
            .f("p_stage_max_Pa", cas.p_stage_max)
            .build(),
    );
    m.insert(
        "feed".into(),
        Obj::new().f("a_eq_m2", a_eq).f("d_eq_m", d_eq).f("Kn_upper_O_omitted", kn).f("lambda_upper_m", lam).build(),
    );
    Ok((m, reasons))
}

/// Fully gated steady state with the plenum held at target (pressure regulation). Never returns flows for a target
/// or a touched pressure above the free-molecular domain (A9.13 S6.8).
pub fn steady_operating_point(
    chain: &Chain,
    mats: &MaterialsView,
    target_pa: f64,
    density_factor: f64,
    feed_factor: f64,
) -> PyResult<Value> {
    let mut reasons: Vec<&str> = vec![];
    if chain.intake.f1_status != "FEASIBLE_AT_STATE" {
        reasons.push(R_UPSTREAM_F1);
    }
    if target_pa > P_DOMAIN_PA {
        reasons.push(R_TARGET_ABOVE_DOMAIN);
        return Ok(Obj::new()
            .s("status", status_from_reasons(&reasons))
            .set("reasons", slist(&reasons))
            .f("target_Pa", target_pa)
            .set("offered", Value::Null)
            .build());
    }
    let co = chain.node_coefficients(density_factor)?;
    let pl = &chain.plenum;
    let leak = pl.leak3()?;
    let feed = pl.feed3()?;
    let fc = [feed[0] * feed_factor, feed[1] * feed_factor, feed[2] * feed_factor];
    let k_rec = pl.k_rec_m3_s()?;
    let sol = area_for_pressure(&co, target_pa, k_rec, &leak, &fc, true)?;
    let mut rec = Obj::new()
        .f("target_Pa", target_pa)
        .f("p_deadhead_Pa", sol.p_dead)
        .f("a_eq_m2", sol.a_eq)
        .f("bisection_residual_rel", sol.resid);
    if !sol.ok {
        reasons.push(R_DEADHEAD);
        return Ok(rec
            .s("status", status_from_reasons(&reasons))
            .set("reasons", slist(&reasons))
            .set("offered", Value::Null)
            .build());
    }
    if bisection_failed(sol.a_eq, sol.resid) {
        reasons.push(R_BISECTION);
        return Ok(rec
            .s("status", status_from_reasons(&reasons))
            .set("reasons", slist(&reasons))
            .set("offered", Value::Null)
            .build());
    }
    let (op, rs) = operating_record(chain, mats, &co, sol.a_eq, k_rec, &leak, &fc)?;
    reasons.extend(rs);
    let status = status_from_reasons(&reasons);
    for (k, v) in op.clone() {
        rec.insert(&k, v);
    }
    if status == ST_OOD || status == ST_MODEL_ERROR {
        let comp = &op["compressor"];
        let diag = Obj::new()
            .set("compressor_K_min", comp["K_min"].clone())
            .set("compressor_K_over_K0_max", comp["K_over_K0_max"].clone())
            .set("compressor_p_stage_max_Pa", comp["p_stage_max_Pa"].clone())
            .set("compressor_inlet_P_Pa", op["compressor_inlet_P_Pa"].clone())
            .set("feed_Kn_upper_O_omitted", op["feed"]["Kn_upper_O_omitted"].clone())
            .build();
        return Ok(Obj::new()
            .f("target_Pa", target_pa)
            .f("p_deadhead_Pa", sol.p_dead)
            .f("a_eq_m2", sol.a_eq)
            .f("bisection_residual_rel", sol.resid)
            .set("reasons", slist(&reasons))
            .s("status", status)
            .set("offered", Value::Null)
            .set("domain_diagnostics", diag)
            .build());
    }
    Ok(rec.set("reasons", slist(&reasons)).s("status", status).build())
}

/// Intake-side coefficients f_s [Pa m^3/s] and e_s [m^3/s] over intake records.
pub fn intake_side(intakes: &[IntakeState], filt: &FilterCase, density_factor: f64) -> PyResult<(Vec<Sp3>, Vec<Sp3>)> {
    let (mut f, mut e) = (vec![], vec![]);
    for it in intakes {
        let a = it.escape_probability()?;
        let (d, ee) = filt.coefficients(&a)?;
        let q = it.q_fwd()?;
        let (mut fr, mut er) = ([0.0; 3], [0.0; 3]);
        for (i, s) in SPECIES.iter().enumerate() {
            fr[i] = q[i] * d[i] * density_factor;
            er[i] = -ee[i] * it.area_m2 * cbar(s, it.t_k)? / 4.0;
        }
        f.push(fr);
        e.push(er);
    }
    Ok((f, e))
}

/// steady_sweep result (rows x targets), row-major; masked values NaN.
#[derive(Debug, Clone, PartialEq)]
pub struct Sweep {
    pub n: usize,
    pub m: usize,
    pub bits: Vec<i64>,
    pub in_domain: Vec<bool>,
    pub mdot_total_kgps: Vec<f64>,
    pub mdot_s_kgps: [Vec<f64>; 3],
    pub x_s_flow_mole: [Vec<f64>; 3],
    pub p_el_w: Vec<f64>,
    pub m_compressor_kg: Vec<f64>,
    pub t_comp_k: Vec<f64>,
    pub a_eq_m2: Vec<f64>,
    pub p_deadhead_pa: Vec<f64>,
    pub bisection_residual_rel: Vec<f64>,
    pub kn_upper: Vec<f64>,
}

fn rows_value(v: &[f64], n: usize, m: usize) -> Value {
    Value::Array((0..n).map(|i| crate::rec::flist(&v[i * m..(i + 1) * m])).collect())
}

impl Sweep {
    pub fn to_value(&self) -> Value {
        let (n, m) = (self.n, self.m);
        let sp = |a: &[Vec<f64>; 3]| -> Value {
            let mut o = Map::new();
            for (i, s) in SPECIES.iter().enumerate() {
                o.insert(s.to_string(), rows_value(&a[i], n, m));
            }
            Value::Object(o)
        };
        Obj::new()
            .set(
                "bits",
                Value::Array(
                    (0..n)
                        .map(|i| Value::Array(self.bits[i * m..(i + 1) * m].iter().map(|b| Value::from(*b)).collect()))
                        .collect(),
                ),
            )
            .set(
                "in_domain",
                Value::Array(
                    (0..n)
                        .map(|i| {
                            Value::Array(self.in_domain[i * m..(i + 1) * m].iter().map(|b| Value::Bool(*b)).collect())
                        })
                        .collect(),
                ),
            )
            .set("mdot_total_kgps", rows_value(&self.mdot_total_kgps, n, m))
            .set("mdot_s_kgps", sp(&self.mdot_s_kgps))
            .set("x_s_flow_mole", sp(&self.x_s_flow_mole))
            .set("P_el_W", rows_value(&self.p_el_w, n, m))
            .set("m_compressor_kg", rows_value(&self.m_compressor_kg, n, m))
            .set("T_comp_K", rows_value(&self.t_comp_k, n, m))
            .set("a_eq_m2", rows_value(&self.a_eq_m2, n, m))
            .set("p_deadhead_Pa", rows_value(&self.p_deadhead_pa, n, m))
            .set("bisection_residual_rel", rows_value(&self.bisection_residual_rel, n, m))
            .set("Kn_upper", rows_value(&self.kn_upper, n, m))
            .build()
    }
}

/// Gated steady operating points for many intake records (rows) x plenum targets (columns): the study path; the
/// elementwise twin of steady_operating_point (numpy semantics, T = T_CHAIN_K).
pub fn steady_sweep(
    side: &(Vec<Sp3>, Vec<Sp3>),
    plant: &CompressorPlant,
    plenum: &Plenum,
    mats: &MaterialsView,
    targets_pa: &[f64],
    f1_ok: Option<&[bool]>,
) -> PyResult<Sweep> {
    let (fv, ev) = side;
    let n = fv.len();
    let m = targets_pa.len();
    let ch = plant.characteristic()?;
    let cl = plant.leak_m3_s();
    let mut base =
        [Node { f: 0.0, e: 0.0, alpha: 0.0, beta: 0.0, a_c: 0.0, b_c: 0.0, d: f64::NAN, e_fac: f64::NAN, a: f64::NAN };
            3];
    for i in 0..3 {
        base[i].a_c = ch[i].0;
        base[i].b_c = ch[i].1;
        base[i].alpha = pyops::div(ch[i].0, ch[i].1)? + cl;
        base[i].beta = pyops::div(1.0, ch[i].1)? + cl;
    }
    let leak = plenum.leak3()?;
    let fc = plenum.feed3()?;
    let k_rec = plenum.k_rec_m3_s()?;
    let tmax = mats.get(&plant.comp.rotor_material)?.t_max_k;
    for t in targets_pa {
        let tg = if *t > P_DOMAIN_PA { P_DOMAIN_PA } else { *t };
        if !tg.is_finite() || tg <= 0.0 {
            return Err(value_error("plenum target pressure must be finite and > 0"));
        }
    }
    let nm = n * m;
    let nanv = || vec![f64::NAN; nm];
    let mut sw = Sweep {
        n,
        m,
        bits: vec![0; nm],
        in_domain: vec![false; nm],
        mdot_total_kgps: nanv(),
        mdot_s_kgps: [nanv(), nanv(), nanv()],
        x_s_flow_mole: [nanv(), nanv(), nanv()],
        p_el_w: nanv(),
        m_compressor_kg: nanv(),
        t_comp_k: nanv(),
        a_eq_m2: nanv(),
        p_deadhead_pa: nanv(),
        bisection_residual_rel: nanv(),
        kn_upper: nanv(),
    };
    let km: Sp3 = [
        1.0 / (K_B * T_CHAIN_K / m_of("O")),
        1.0 / (K_B * T_CHAIN_K / m_of("N2")),
        1.0 / (K_B * T_CHAIN_K / m_of("O2")),
    ];
    for i in 0..n {
        let mut co = base;
        for k in 0..3 {
            co[k].f = fv[i][k];
            co[k].e = ev[i][k];
        }
        for (j, t) in targets_pa.iter().enumerate() {
            let idx = i * m + j;
            let mut bits = 0i64;
            if let Some(ok) = f1_ok {
                if !ok[i] {
                    bits |= reason_bit(R_UPSTREAM_F1);
                }
            }
            let above = *t > P_DOMAIN_PA;
            if above {
                bits |= reason_bit(R_TARGET_ABOVE_DOMAIN);
            }
            let tgt = if above { P_DOMAIN_PA } else { *t };
            let sol = area_for_pressure(&co, tgt, k_rec, &leak, &fc, false)?;
            if !above && !sol.ok {
                bits |= reason_bit(R_DEADHEAD);
            }
            let bis_bad = bisection_failed(sol.a_eq, sol.resid);
            if !above && sol.ok && bis_bad {
                bits |= reason_bit(R_BISECTION);
            }
            let (p3, p2) = solve_pressures(&co, sol.a_eq, k_rec, &leak, &fc, false)?;
            let mut q = [0.0; 3];
            for k in 0..3 {
                q[k] = (co[k].a_c * p2[k] - p3[k]) / co[k].b_c;
            }
            let cas = plant.cascade_impl(mats, &p2, &q, true)?;
            let char_bad = cas.k_min < 1.0 - K_TOL || cas.k_over_k0_max > 1.0 + K_TOL;
            let stage_bad = cas.p_stage_max > P_DOMAIN_PA * (1.0 + 1e-12) || pyops::py_sum(p2) > P_DOMAIN_PA;
            let mut denom = 0.0;
            for (s, sig) in cs::SIGMA_C_M2 {
                let k = SPECIES.iter().position(|x| *x == s).expect("species");
                denom += p3[k] / (K_B * T_CHAIN_K) * sig;
            }
            let kn = (1.0 / (2.0f64.sqrt() * denom)) / (4.0 * sol.a_eq / PI).sqrt();
            let live = !above && sol.ok && !bis_bad;
            if live && char_bad {
                bits |= reason_bit(R_CHARACTERISTIC);
            }
            if live && stage_bad {
                bits |= reason_bit(R_STAGE_DOMAIN);
            }
            if live && kn < KN_MIN {
                bits |= reason_bit(R_KN_FEED);
            }
            if live && cas.t_comp_k > tmax {
                bits |= reason_bit(R_THERMAL);
            }
            let mut md = [0.0; 3];
            for k in 0..3 {
                md[k] = fc[k] * sol.a_eq * p3[k] * km[k];
            }
            let in_domain = live && !char_bad && !stage_bad && kn >= KN_MIN;
            let nanf = if in_domain { 1.0 } else { f64::NAN };
            let mt = pyops::py_sum(md);
            let nmol = [md[0] / m_of("O"), md[1] / m_of("N2"), md[2] / m_of("O2")];
            let nt = pyops::py_sum(nmol);
            sw.bits[idx] = bits;
            sw.in_domain[idx] = in_domain;
            sw.mdot_total_kgps[idx] = mt * nanf;
            for k in 0..3 {
                sw.mdot_s_kgps[k][idx] = md[k] * nanf;
                sw.x_s_flow_mole[k][idx] = nmol[k] / nt * nanf;
            }
            sw.p_el_w[idx] = cas.p_el_w * nanf;
            sw.m_compressor_kg[idx] = cas.mass_kg * nanf;
            sw.t_comp_k[idx] = cas.t_comp_k * nanf;
            sw.a_eq_m2[idx] = sol.a_eq * nanf;
            sw.p_deadhead_pa[idx] = sol.p_dead * 1.0;
            sw.bisection_residual_rel[idx] = sol.resid * nanf;
            sw.kn_upper[idx] = kn * nanf;
        }
    }
    Ok(sw)
}

/// Open-loop plenum attenuation of a compressor flow perturbation at f_hz (least attenuated species reported).
pub fn ripple_transfer(chain: &Chain, a_eq: f64, f_hz: f64) -> PyResult<Value> {
    let co = chain.node_coefficients(1.0)?;
    let pl = &chain.plenum;
    let (mut tau, mut tr) = ([0.0; 3], [0.0; 3]);
    let mut sp = Map::new();
    for (i, s) in SPECIES.iter().enumerate() {
        let c = co[i];
        let k = pyops::div(c.e * c.beta, c.e + c.alpha)?;
        let g = pl.feed_c(s)? * a_eq + pl.leak_m3_s(s)? + if *s == "O" { pl.k_rec_m3_s()? } else { 0.0 };
        tau[i] = pyops::div(pl.volume_m3, k + g)?;
        tr[i] = pyops::div(1.0, pyops::sqrt(1.0 + pyops::pow(2.0 * PI * f_hz * tau[i], 2.0)?)?)?;
        sp.insert(s.to_string(), Obj::new().f("tau_s", tau[i]).f("transfer", tr[i]).build());
    }
    let mut worst = 0;
    for i in 1..3 {
        if tr[i] > tr[worst] {
            worst = i;
        }
    }
    Ok(Obj::new()
        .f("f_hz", f_hz)
        .set("species", Value::Object(sp))
        .f("transfer_max", tr[worst])
        .s("worst_species", SPECIES[worst])
        .f("tau_min_s", pyops::py_min_iter(tau).expect("3"))
        .f("tau_max_s", pyops::py_max_iter(tau).expect("3"))
        .build())
}

/// Compressor-inlet node time constant per m^3 of (TBD) inlet volume.
pub fn inlet_node_tau_per_m3(chain: &Chain) -> PyResult<f64> {
    let co = chain.node_coefficients(1.0)?;
    let mut v = vec![];
    for c in co {
        v.push(pyops::div(1.0, c.e + c.alpha)?);
    }
    Ok(pyops::py_max_iter(v).expect("3"))
}

// ------------------------------------------------------------------------------------------------ strict / Pareto
/// MODE_STRICT refuses while any of these is TBD / an uncited default (they all are today).
pub fn strict_blockers() -> Value {
    let b = |id: &str, what: &str, status: &str, needs: &str| {
        Obj::new().s("id", id).s("what", what).s("status", status).s("needs", needs).build()
    };
    Value::Array(vec![
        b(
            "F3-STRICT",
            "compressor coefficients",
            "F3 MODE_STRICT NOT_EVALUATED (22 blockers)",
            "compressor_downselect T-1..T-9 evidence",
        ),
        b(
            "F2-FILTER",
            "filter stage",
            "every real concept TBD; 'none' (FC-00) is a reference bound only (A9.13 S6.5)",
            "evidenced inert / low-recombination filter records (A9.13 S6.3 / S6.19)",
        ),
        b("F4-P-01", "chain gas temperature", "assumed (code default)", "H2-5 thermal"),
        b("F4-P-05", "plenum leak", "TBD", "leak specification / test"),
        b("F4-P-06", "plenum wall gamma_O", "TBD", "GP-D03 + coupon evidence"),
        b("F4-P-08", "valve bandwidth", "TBD", "metering-valve class (H3)"),
        b("F4-P-09", "valve authority", "TBD", "metering-valve sizing"),
        b("F4-P-10", "H-1 required inlet state", "TBD", "F5 IFD-F4-01..05 / Phase 1"),
        b(
            "F4-P-11",
            "orbit-scale density modulation",
            "TBD",
            "registered inclination / LTAN (mission ICD) to sample a revolution of the orbit-resolved dataset",
        ),
        b("F4-P-18", "compressor-inlet node volume", "TBD", "duct geometry"),
        b(
            "F4-H1-TOL",
            "measured H-1 feed tolerances (pressure, flow, composition, ripple)",
            "TBD",
            "LOCK-2 H-1 feed-sensitivity measurement (A9.13 S6.12 / S6.17)",
        ),
        b(
            "F4-SCHEDULE",
            "orbit-state setpoint schedule (baseline control mode)",
            "NOT_FROZEN",
            "validated compressor / feed / H-1 domains (A9.13 S6.10)",
        ),
    ])
}

/// Public entry point: MODE_STRICT refuses; MODE_PARAMETRIC returns the labelled steady operating point.
pub fn evaluate(chain: &Chain, mats: &MaterialsView, target_pa: f64, mode: &str) -> PyResult<Value> {
    if mode != MODE_STRICT && mode != MODE_PARAMETRIC {
        return Err(value_error("mode must be one of MODES"));
    }
    if mode == MODE_STRICT {
        return Ok(Obj::new()
            .s("status", ST_NOT_EVALUATED)
            .set("blockers", strict_blockers())
            .set("offered", Value::Null)
            .build());
    }
    let mut rec = steady_operating_point(chain, mats, target_pa, 1.0, 1.0)?;
    rec.as_object_mut().expect("object").insert("label".into(), Value::String(LABEL_PARAMETRIC.into()));
    Ok(rec)
}

pub fn dominates(a: &Value, b: &Value, objectives: &[&str]) -> bool {
    let mut better = false;
    for k in objectives {
        let (x, y) = (crate::rec::as_f64(&a[*k]).unwrap_or(f64::NAN), crate::rec::as_f64(&b[*k]).unwrap_or(f64::NAN));
        if x > y {
            return false;
        }
        if x < y {
            better = true;
        }
    }
    better
}

/// Non-dominated feasible rows (all objectives minimized; ties kept; sorted by id).
pub fn pareto_ids(rows: &[Value], objectives: &[&str]) -> Vec<String> {
    let mut feas: Vec<&Value> = rows
        .iter()
        .filter(|r| {
            r["status"] == ST_FEASIBLE
                && objectives.iter().all(|k| matches!(r["objectives"].get(*k), Some(Value::Number(_))))
        })
        .collect();
    feas.sort_by(|a, b| a["id"].as_str().unwrap_or("").cmp(b["id"].as_str().unwrap_or("")));
    feas.iter()
        .enumerate()
        .filter(|(i, r)| {
            !feas.iter().enumerate().any(|(j, o)| j != *i && dominates(&o["objectives"], &r["objectives"], objectives))
        })
        .map(|(_, r)| r["id"].as_str().unwrap_or("").to_string())
        .collect()
}

// ------------------------------------------------------------------------------------------------ S6.10 control
pub fn nav_altitude_input() -> u13::ScheduleInput {
    u13::ScheduleInput::new(
        "nav:alt_km",
        "onboard_navigation_or_clock",
        "onboard orbit determination (navigation solution); availability per the spacecraft ICD (TBD)",
    )
    .expect("valid input")
}

/// Controller-available view of an F1 orbit state (altitude from navigation only).
pub fn intake_controller_state(intake: &IntakeState, inputs: &[u13::ScheduleInput]) -> PyResult<u13::ControllerState> {
    let full = vec![("alt_km".to_string(), fnum(intake.alt_km))];
    let mapping: Vec<(String, String)> = inputs
        .iter()
        .map(|i| (i.name.clone(), i.name.split_once(':').map(|(_, b)| b.to_string()).unwrap_or_else(|| i.name.clone())))
        .collect();
    u13::controller_view(&full, inputs, &mapping)
}

/// Steady operation at every orbit state under one control mode (A9.13 S6.10). `required_state_ids` = the frozen
/// design-state set's required ids (explicit input).
#[allow(clippy::too_many_arguments)]
pub fn scheduled_operation(
    filt: &FilterCase,
    plant: &CompressorPlant,
    plenum: &Plenum,
    mats: &MaterialsView,
    intakes: &[IntakeState],
    control: &u13::Control,
    controller_states: Option<&[(String, u13::ControllerState)]>,
    required_state_ids: &[String],
) -> PyResult<Value> {
    let mut rows = vec![];
    let use_given = controller_states.map(|c| !c.is_empty()).unwrap_or(false);
    for it in intakes {
        let cst = if use_given {
            controller_states.expect("given").iter().find(|(k, _)| *k == it.state).map(|(_, v)| v.clone())
        } else {
            Some(intake_controller_state(it, &[nav_altitude_input()])?)
        };
        let Some(cst) = cst else {
            return Err(value_error(format!("no controller state for {}", it.state)));
        };
        let sp = control.setpoint(&cst)?;
        let mut cmap = Map::new();
        for (k, v) in &cst {
            cmap.insert(k.clone(), v.clone());
        }
        let mut row = Obj::new()
            .s("state", &it.state)
            .s("scenario", &it.scenario)
            .s("candidate", &it.candidate)
            .s("mode", control.mode())
            .s("mode_role", u13::control_mode_role(control.mode()))
            .set("controller_state", Value::Object(cmap))
            .set("setpoint", sp.clone());
        match crate::rec::as_f64(&sp["setpoint_Pa"]) {
            None => {
                row = row
                    .set("status", sp["status"].clone())
                    .set("reasons", Value::Array(vec![]))
                    .set("offered", Value::Null);
            }
            Some(p) => {
                let chain =
                    Chain { intake: it.clone(), filt: filt.clone(), plant: plant.clone(), plenum: plenum.clone() };
                let op = steady_operating_point(&chain, mats, p, 1.0, 1.0)?;
                row = row
                    .set("status", op["status"].clone())
                    .set("reasons", op["reasons"].clone())
                    .set("offered", op.get("offered").cloned().unwrap_or(Value::Null))
                    .set("a_eq_m2", op.get("a_eq_m2").cloned().unwrap_or(Value::Null))
                    .set(
                        "P_compressor_el_W",
                        op.get("compressor").and_then(|c| c.get("P_el_W")).cloned().unwrap_or(Value::Null),
                    )
                    .set("domain", sp["domain"].clone());
            }
        }
        rows.push(row.build());
    }
    let ok: Vec<&Value> = rows.iter().filter(|r| r["status"] == ST_FEASIBLE).collect();
    let md: Vec<f64> =
        ok.iter().map(|r| crate::rec::as_f64(&r["offered"]["mdot_total_kgps"]).unwrap_or(f64::NAN)).collect();
    let used: Vec<String> = intakes.iter().map(|i| i.state.clone()).collect();
    let cov = u13::state_coverage(&used, required_state_ids)?;
    let admissible = cov["baseline_admissible_by_coverage"] == Value::Bool(true);
    let all = ok.len() == rows.len();
    Ok(Obj::new()
        .s("mode", control.mode())
        .s("mode_role", u13::control_mode_role(control.mode()))
        .set("control", control.to_dict())
        .s("label", LABEL_PARAMETRIC)
        .set("state_coverage", Value::Object(cov))
        .s(
            "operation_role",
            if admissible { "ELIGIBLE_BY_COVERAGE (S6.15 still governs)" } else { u13::DENSE_STATE_ONLY_ROLE },
        )
        .s("orbit_basis", "BROAD_ENVELOPE_ALL_INCLINATIONS_ALL_LTAN_NOT_MISSION_ICD")
        .set("n_states", rows.len())
        .set("n_feasible", ok.len())
        .b("all_states_feasible", all)
        .set(
            "worst_state_mdot_kgps",
            if all && !md.is_empty() { fnum(pyops::py_min_iter(md).expect("non-empty")) } else { Value::Null },
        )
        .set("authority", u13::cite(&["A9.13"])?)
        .set("rows", Value::Array(rows))
        .build())
}

/// Baseline (scheduled) and fallback / reference (fixed) side by side; no mode is selected (S6.10).
#[allow(clippy::too_many_arguments)]
pub fn compare_control_modes(
    filt: &FilterCase,
    plant: &CompressorPlant,
    plenum: &Plenum,
    mats: &MaterialsView,
    intakes: &[IntakeState],
    schedule: &u13::SetpointSchedule,
    fixed: &u13::FixedSetpoint,
    controller_states: Option<&[(String, u13::ControllerState)]>,
    required_state_ids: &[String],
) -> PyResult<Value> {
    let a = scheduled_operation(
        filt,
        plant,
        plenum,
        mats,
        intakes,
        &u13::Control::Schedule(schedule.clone()),
        controller_states,
        required_state_ids,
    )?;
    let b = scheduled_operation(
        filt,
        plant,
        plenum,
        mats,
        intakes,
        &u13::Control::Fixed(fixed.clone()),
        controller_states,
        required_state_ids,
    )?;
    Ok(Obj::new()
        .set("baseline", a)
        .set("fallback_reference", b)
        .s("schedule_status", &schedule.status)
        .s(
            "rule",
            "A9.13 S6.10: scheduled setpoint = baseline control mode; fixed setpoint = fallback / degraded mode and \
comparison reference; the schedule is not frozen",
        )
        .build())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_and_bits_vocabulary() {
        assert_eq!(status_from_reasons::<&str>(&[]), ST_FEASIBLE);
        assert_eq!(status_from_reasons(&[R_THERMAL, R_KN_FEED]), ST_OOD);
        assert_eq!(status_from_reasons(&[R_KN_FEED, R_BISECTION]), ST_MODEL_ERROR);
        assert_eq!(status_eval(ST_OOD), EvalStatus::OutOfDomain);
        assert_eq!(status_eval(ST_MODEL_ERROR), EvalStatus::ModelError);
        assert_eq!(status_eval(ST_INFEASIBLE), EvalStatus::Evaluated);
        let all: i64 = (1 << 14) - 1;
        assert_eq!(reasons_from_bits(all).len(), 14);
        assert_eq!(reason_bit(R_BISECTION), 1 << 13);
    }

    #[test]
    fn bisection_failure_is_fail_closed() {
        assert!(bisection_failed(1e2, 0.0));
        assert!(bisection_failed(1e-12, 0.0));
        assert!(bisection_failed(1e-6, 2e-6));
        assert!(bisection_failed(1e-6, f64::NAN));
        assert!(!bisection_failed(1e-6, 1e-9));
    }

    #[test]
    fn plenum_refuses_malformed_input() {
        assert!(Plenum::new(0.0, 0.0, "W", 0.0, 350.0).is_err());
        assert!(Plenum::new(1e-3, 1.5, "W", 0.0, 350.0).is_err());
        assert!(Plenum::new(1e-3, 0.0, "W", -1.0, 350.0).is_err());
        assert!(Plenum::new(1e-3, 0.0, "W", 0.0, f64::NAN).is_err());
        assert!(Plenum::new(1e-3, 0.0, "W", 5e-8, 350.0).is_ok());
    }

    #[test]
    fn filter_cases_build() {
        let cases = filter_cases(&[0.9, 0.7, 0.5]).unwrap();
        assert_eq!(cases.len(), 5);
        assert!(cases[0].reference_bound_only());
        let a = [0.3, 0.4, 0.5];
        let (d, e) = cases[0].coefficients(&a).unwrap();
        for i in 0..3 {
            assert_eq!(d[i], 1.0);
            assert!((e[i] + a[i]).abs() < 1e-15);
        }
    }
}
