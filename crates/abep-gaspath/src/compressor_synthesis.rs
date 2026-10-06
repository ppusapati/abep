//! F3 compressor geometry synthesis (`abep_sim/design/compressor_synthesis.py` computational subset; contract
//! PARITY-C-ABEP_SIM_COMPRESSOR_PY-V1): bounded design search over DragCompressor instances with explicit fail-closed
//! gates (rotor structural acceptance only through a registered basis, convergence re-check, Gaede characteristic,
//! 0.1 Pa free-molecular domain, drag-channel Kn >= 0.5 upper bound, thermal limit). MODE_STRICT refuses on the
//! uncited code defaults (NOT_EVALUATED); MODE_PARAMETRIC labels every output PARAMETRIC_SENSITIVITY. Pareto fronts,
//! never a selected optimum.

use crate::compressor::{Ctx, DragCompressor, SpMap, FIELDS};
use crate::error::{key_error, sie, PyClass, PyResult};
use crate::pyops::{self, py_max, py_repr};
use crate::rec::{as_f64, fnum, slist, Obj};
use crate::rotor_strength::{self as rs, Arg};
use crate::upstream as u13;
use crate::SPECIES;
use abep_types::constants::{species_mass, K_B};
use abep_types::EvalStatus;
use serde_json::{Map, Value};
use std::f64::consts::PI;

pub const MODE_STRICT: &str = "strict";
pub const MODE_PARAMETRIC: &str = "parametric_sensitivity";
pub const MODES: [&str; 2] = [MODE_STRICT, MODE_PARAMETRIC];
pub const LABEL_PARAMETRIC: &str = "PARAMETRIC_SENSITIVITY";
pub const LABEL_INTERFACE: &str = "F1_F2_INTERFACE_RECORD";
pub const INLET_LABELS: [&str; 2] = [LABEL_PARAMETRIC, LABEL_INTERFACE];
pub const EVIDENCE_CLASSES: [&str; 7] =
    ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation"];

pub const ST_FEASIBLE: &str = "FEASIBLE_UNDER_PARAMETRIC_SENSITIVITY_INPUTS";
pub const ST_FEASIBLE_STRICT: &str = "FEASIBLE_UNDER_SUPPLIED_EVIDENCE";
pub const ST_REJECTED: &str = "REJECTED";
pub const ST_NOT_EVALUATED: &str = "NOT_EVALUATED";
pub const ST_NOT_EVALUATED_OOD: &str = u13::NOT_EVALUATED_OOD;
pub const ST_NOT_EVALUATED_MATERIAL_BASIS: &str = rs::Q_NOT_EVALUATED_MATERIAL_BASIS;

pub const R_ALLOWABLE_TBD: &str = "ROTOR_MATERIAL_ALLOWABLE_TBD";
pub const R_STRESS: &str = "ROTOR_STRESS_ABOVE_CITED_ALLOWABLE_WITH_SAFETY_FACTOR";
pub const R_TIP_DOMAIN: &str = "TIP_SPEED_ABOVE_PUBLISHED_TMP_PRACTICE";
pub const R_INLET_DOMAIN: &str = "INLET_PRESSURE_OUTSIDE_FREE_MOLECULAR_DOMAIN";
pub const R_MODEL: &str = "MODEL_ERROR_NON_FINITE_OR_EXCEPTION";
pub const R_NONCONV: &str = "SELF_CONSISTENT_RUN_NOT_CONVERGED";
pub const R_CLIP: &str = "GAEDE_CHARACTERISTIC_CLIPPED_THROUGHPUT_ABOVE_STAGE_CAPACITY";
pub const R_DOMAIN_P: &str = "STAGE_PRESSURE_OUTSIDE_FREE_MOLECULAR_DOMAIN";
pub const R_DOMAIN_KN: &str = "DRAG_CHANNEL_KNUDSEN_BELOW_FREE_MOLECULAR_LIMIT";
pub const R_THERMAL: &str = "COMPRESSOR_TEMPERATURE_ABOVE_MATERIAL_SERVICE_LIMIT";
pub const R_ROTOR_QUAL_FAIL: &str = "ROTOR_QUALIFICATION_FAIL_REGISTERED_BASIS";
pub const R_ROTOR_QUAL_OOD: &str = "ROTOR_QUALIFICATION_OUTSIDE_REGISTERED_BASIS_DOMAIN";
pub const R_READMISSION_RECORDS: &str = "MATERIAL_READMISSION_RECORDS_MISSING";
pub const REASONS: [&str; 13] = [
    R_ALLOWABLE_TBD,
    R_STRESS,
    R_TIP_DOMAIN,
    R_INLET_DOMAIN,
    R_MODEL,
    R_NONCONV,
    R_CLIP,
    R_DOMAIN_P,
    R_DOMAIN_KN,
    R_THERMAL,
    R_ROTOR_QUAL_FAIL,
    R_ROTOR_QUAL_OOD,
    R_READMISSION_RECORDS,
];
pub const DOMAIN_REASONS: [&str; 3] = [R_INLET_DOMAIN, R_DOMAIN_P, R_DOMAIN_KN];
pub const INLET_INDEPENDENT_REASONS: [&str; 4] = [R_ALLOWABLE_TBD, R_STRESS, R_TIP_DOMAIN, R_ROTOR_QUAL_FAIL];

pub const HUB_RATIO_PARAMETRIC: [f64; 4] = [0.0, 0.25, 0.5, 0.75];
pub const HUB_ZERO_BOUND: &str = "ZERO_HUB_ANALYTICAL_BOUND_NOT_BUILDABLE";
pub const HUB_PARAMETRIC: &str = "PARAMETRIC_SENSITIVITY_HUB_RATIO_BOUNDS_TBD";
pub const HUB_BOUND_SOURCES: [&str; 5] = [
    "shaft / bearing geometry",
    "rotor structural analysis",
    "motor / interface geometry",
    "blade manufacturability",
    "pumping-performance model",
];
pub const STRESS_CASE_LEGACY: &str = "LEGACY_PARAMETRIC_SENSITIVITY";
pub const STRESS_CASE_REGISTERED: &str = "REGISTERED_BASIS_QUALIFY_ROTOR";
pub const AO_DISPOSITION_KEY: &str = "ao_disposition";
pub const CFRP_EXTRA_BASIS_KEYS: [&str; 5] = [
    "laminate_definition",
    "directional_allowables",
    "temperature_moisture_environment_basis",
    "manufacturing_inspection_basis",
    AO_DISPOSITION_KEY,
];

pub const P_MOLECULAR_LIMIT_PA: f64 = 0.1;
pub const KN_FREE_MOLECULAR_MIN: f64 = 0.5;
/// Chiggiato 2013 Table 6 (N2, O2); atomic O TBD.
pub const SIGMA_C_M2: [(&str, f64); 2] = [("N2", 0.43e-18), ("O2", 0.40e-18)];
pub const U_TIP_PUBLISHED_MAX_MPS: f64 = 500.0;
pub const TI64_FTY_A_BASIS_PA: f64 = 827e6;
pub const RECIRC_RTOL: f64 = 1e-4;
pub const MIRROR_RTOL: f64 = 1e-12;
pub const RPM_SEARCH_MIN: f64 = 5000.0;
pub const SIZE_FOR_MAX_TURBO_ROWS: i64 = 6;
pub const SIZE_FOR_MAX_DRAG_STAGES: i64 = 4;
pub const OWNER_MASS_ALLOCATION_KG: f64 = 5.5;
pub const LI2015_INLET_DIAMETER_M: f64 = 0.5;
pub const A_INLET_MIN_B025_RANGE_M2: (f64, f64) = (0.1128299365, 0.1137287437);
pub const CITED_ALLOWABLES_PA: [(&str, f64); 1] = [("Ti6Al4V", TI64_FTY_A_BASIS_PA)];
pub const MATERIALS_EXCLUDED: [(&str, &str); 2] = [
    (
        "Al6061",
        "allowable TBD: materials.DB yield 276 MPa is an uncited prior; no accessed A/B-basis source. Chiggiato names \
'high-strength aluminium alloys' for commercial rotors (alloy and temper not stated). Re-enters only through a \
registered rotor-strength basis (rotor_strength.register_basis) plus an AO disposition (A9.13 S6.9)",
    ),
    (
        "CFRP",
        "allowable TBD (materials.DB 600 MPa uncited prior; laminate-dependent); bare CFRP wetted parts recede \
0.48-15.9 mm over 26,000 h at the ram AO yield (compressor_downselect CD-07); owner OD-C3 PROPOSED metallic/coated a \
priori. Re-enters only through a registered basis plus laminate definition, directional allowables, temperature / \
moisture / environment basis, manufacturing / inspection basis and AO disposition of every exposed surface (A9.13 S6.9)",
    ),
];

pub const SEARCHED: &str = "SEARCHED";
pub const DERIVED: &str = "DERIVED";
pub const FIXED: &str = "FIXED_CODE_DEFAULT";
pub const FROM_INLET: &str = "FROM_INLET_RECORD";

/// (field, role, name, units, closing test) for every DragCompressor field.
pub const FIELD_ROLES: [(&str, &str, &str, &str, &str); 27] = [
    ("turbo_rows", SEARCHED, "N_turbo", "-", "T-1/T-2"),
    ("turbo_area_m2", SEARCHED, "A_turbo", "m^2", "T-2"),
    ("turbo_radius_m", DERIVED, "R_turbo (tip radius from A_turbo and hub ratio)", "m", "T-2 (hub-ratio bounds TBD)"),
    ("turbo_kS", FIXED, "turbo pumping-speed coefficient", "-", "T-2"),
    ("turbo_kK", FIXED, "turbo ln K0 coefficient per row", "-", "T-1"),
    ("turbo_blade_area_frac", FIXED, "blade area fraction (drag area, mass)", "-", "T-4/T-7"),
    ("turbo_disc_thickness_m", FIXED, "turbo disc thickness (mass)", "m", "T-7"),
    ("n_stages", SEARCHED, "N_drag", "-", "T-1"),
    ("rotor_radius_m", FIXED, "R_rotor (drag rotor radius)", "m", "T-1/T-7"),
    ("rpm", SEARCHED, "RPM (via turbo tip speed)", "rpm", "T-2"),
    ("h_mm", FIXED, "h (drag channel depth)", "mm", "T-1"),
    ("w_mm", FIXED, "w (drag channel width)", "mm", "T-1"),
    ("L_per_stage_m", FIXED, "L (unwrapped drag channel length per stage)", "m", "T-1"),
    (
        "xi",
        FIXED,
        "xi (drag-channel geometric efficiency; the module's equivalent of the helix-angle effect)",
        "-",
        "T-1",
    ),
    ("rotor_material", SEARCHED, "rotor material (restricted to cited allowables)", "-", "T-6"),
    ("stress_safety", FIXED, "stress safety factor", "-", "owner policy"),
    ("T_gas_K", FROM_INLET, "gas temperature for c_bar", "K", "T-5"),
    ("leak_conductance_m3_s", FIXED, "outlet-to-inlet leak conductance", "m^3/s", "T-8"),
    ("k_bear_W_per_rads", FIXED, "bearing loss coefficient", "W s/rad", "T-4"),
    ("eta_motor", FIXED, "motor efficiency (P_el = P_shaft / eta_motor + P_ctrl)", "-", "T-4"),
    ("P_ctrl_W", FIXED, "control power", "W", "T-4"),
    ("rotor_disc_thickness_m", FIXED, "drag rotor disc thickness (mass)", "m", "T-7"),
    ("stator_mass_factor", FIXED, "stator + housing mass relative to rotor", "-", "T-7"),
    ("motor_kg_per_Nm", FIXED, "motor mass per torque", "kg/(N m)", "T-7"),
    ("bearing_kg", FIXED, "bearing mass", "kg", "T-7"),
    ("conductance_to_sink_W_K", FIXED, "thermal conductance to sink", "W/K", "T-5"),
    ("T_sink_K", FIXED, "sink temperature", "K", "T-5"),
];

/// Definitional domain of the FIXED coefficients: 'pos' > 0, 'nonneg' >= 0, 'frac' in (0, 1].
pub const COEFFICIENT_DOMAIN: [(&str, &str); 20] = [
    ("turbo_kS", "pos"),
    ("turbo_kK", "pos"),
    ("turbo_blade_area_frac", "frac"),
    ("turbo_disc_thickness_m", "pos"),
    ("rotor_radius_m", "pos"),
    ("h_mm", "pos"),
    ("w_mm", "pos"),
    ("L_per_stage_m", "pos"),
    ("xi", "frac"),
    ("stress_safety", "pos"),
    ("leak_conductance_m3_s", "nonneg"),
    ("k_bear_W_per_rads", "nonneg"),
    ("eta_motor", "frac"),
    ("P_ctrl_W", "nonneg"),
    ("rotor_disc_thickness_m", "pos"),
    ("stator_mass_factor", "nonneg"),
    ("motor_kg_per_Nm", "nonneg"),
    ("bearing_kg", "nonneg"),
    ("conductance_to_sink_W_K", "pos"),
    ("T_sink_K", "pos"),
];

pub const PRIMARY_OBJECTIVES: [(&str, &str); 4] = [
    ("P_out_Pa", "max"),
    ("mdot_delivered_total_kgps", "max"),
    ("P_compressor_el_W", "min"),
    ("m_compressor_kg", "min"),
];
pub const SECONDARY_OBJECTIVES: [(&str, &str); 5] = [
    ("P_out_Pa", "max"),
    ("mdot_delivered_total_kgps", "max"),
    ("P_compressor_el_W", "min"),
    ("m_compressor_kg", "min"),
    ("S_turbo_m3_s", "max"),
];

/// evaluate_design / synthesize status -> EvalStatus (INV-C-03).
pub fn design_eval_status(status: &str, reasons: &[String]) -> EvalStatus {
    match status {
        ST_NOT_EVALUATED | ST_NOT_EVALUATED_MATERIAL_BASIS => EvalStatus::NotEvaluated,
        ST_NOT_EVALUATED_OOD => EvalStatus::OutOfDomain,
        ST_REJECTED if reasons.iter().any(|r| r == R_MODEL || r == R_NONCONV) => EvalStatus::ModelError,
        _ => EvalStatus::Evaluated,
    }
}

fn field_role(name: &str) -> Option<&'static (&'static str, &'static str, &'static str, &'static str, &'static str)> {
    FIELD_ROLES.iter().find(|f| f.0 == name)
}

fn cited_allowable(m: &str) -> Option<f64> {
    CITED_ALLOWABLES_PA.iter().find(|(k, _)| *k == m).map(|(_, v)| *v)
}

fn readmitted_keys(m: &str) -> &'static [&'static str] {
    match m {
        "Al6061" => &[AO_DISPOSITION_KEY],
        "CFRP" => &CFRP_EXTRA_BASIS_KEYS,
        _ => &[],
    }
}

/// Python `str(v)` of a JSON leaf.
/// Transported non-finite floats ("NaN", "+inf", "-inf") are Python floats: their str / repr is nan / inf / -inf.
fn nonfinite_text(s: &str) -> Option<&'static str> {
    match s {
        "NaN" => Some("nan"),
        "+inf" => Some("inf"),
        "-inf" => Some("-inf"),
        _ => None,
    }
}

fn py_str(v: &Value) -> String {
    match v {
        Value::Null => "None".into(),
        Value::Bool(b) => if *b { "True" } else { "False" }.into(),
        Value::String(s) if nonfinite_text(s).is_some() => nonfinite_text(s).unwrap_or_default().into(),
        Value::String(s) => s.clone(),
        Value::Number(n) => py_num_repr(n),
        other => other.to_string(),
    }
}

fn py_num_repr(n: &serde_json::Number) -> String {
    if n.is_f64() {
        py_repr(n.as_f64().expect("f64"))
    } else {
        n.to_string()
    }
}

/// Python `repr(v)` of a JSON leaf.
pub fn py_value_repr(v: &Value) -> String {
    match v {
        Value::String(s) if nonfinite_text(s).is_some() => py_str(v),
        Value::String(s) => rs::py_str_repr(s),
        other => py_str(other),
    }
}

/// `_real`: a finite number that is not a bool, else None.
fn real(v: Option<&Value>) -> Option<f64> {
    match v {
        Some(Value::Number(n)) => n.as_f64().filter(|x| x.is_finite()),
        _ => None,
    }
}

/// Admission status of a rotor material (A9.13 S6.9, A9.9 S2.3).
pub fn material_admission(ctx: Ctx, material: &str, extra: Option<&Map<String, Value>>) -> PyResult<Value> {
    if !ctx.materials.contains(material) {
        return Err(sie(format!("rotor material {} is not in materials.DB", rs::py_str_repr(material))));
    }
    let bases = ctx.registry.bases_for(material);
    let missing_extra: Vec<&str> = readmitted_keys(material)
        .iter()
        .copied()
        .filter(|k| extra.and_then(|e| e.get(*k)).map(|v| py_str(v).trim().is_empty()).unwrap_or(true))
        .collect();
    if !bases.is_empty() && missing_extra.is_empty() {
        return Ok(Obj::new()
            .s("material", material)
            .s("status", "ADMITTED_VIA_REGISTERED_BASIS")
            .set("bases", slist(&bases))
            .s("structural_acceptance", "rotor_strength.qualify_rotor only")
            .build());
    }
    if cited_allowable(material).is_some() {
        return Ok(Obj::new()
            .s("material", material)
            .s("status", STRESS_CASE_LEGACY)
            .set("bases", slist(&bases))
            .set("missing_extra", slist(&missing_extra))
            .s("structural_acceptance", ST_NOT_EVALUATED_MATERIAL_BASIS)
            .s("note", rs::LEGACY_SENSITIVITY_LABEL)
            .build());
    }
    let reason =
        MATERIALS_EXCLUDED.iter().find(|(k, _)| *k == material).map(|(_, v)| *v).unwrap_or("no registered basis");
    Ok(Obj::new()
        .s("material", material)
        .s("status", ST_NOT_EVALUATED_MATERIAL_BASIS)
        .set("bases", slist(&bases))
        .set("missing_extra", slist(&missing_extra))
        .s("reason", reason)
        .build())
}

/// `module_defaults()`: field -> default value.
pub fn module_defaults() -> Value {
    let d = DragCompressor::default();
    let mut m = Map::new();
    for f in FIELDS {
        m.insert(f.into(), d.field_value(f).expect("field"));
    }
    Value::Object(m)
}

// ------------------------------------------------------------------------------------------------ inlet record
/// Compressor inlet state (the F1 / F2 interface record).
#[derive(Debug, Clone, PartialEq)]
pub struct InletRecord {
    pub record_id: String,
    pub mdot_kgps: SpMap,
    pub p_total_pa: f64,
    pub t_k: f64,
    pub label: String,
    pub source: String,
    pub evidence_class: String,
    pub status: String,
    pub p_species_pa: Option<SpMap>,
    pub extra: Map<String, Value>,
}

fn sp(m: &SpMap, k: &str) -> f64 {
    m.iter().find(|(s, _)| s == k).map(|(_, v)| *v).unwrap_or(f64::NAN)
}

fn keyset(m: &SpMap) -> Vec<String> {
    let mut v: Vec<String> = m.iter().map(|(k, _)| k.clone()).collect();
    v.sort();
    v.dedup();
    v
}

fn species_set() -> Vec<String> {
    let mut v: Vec<String> = SPECIES.iter().map(|s| s.to_string()).collect();
    v.sort();
    v
}

impl InletRecord {
    pub fn validate(&self) -> PyResult<()> {
        if !INLET_LABELS.contains(&self.label.as_str()) {
            return Err(sie("inlet label must be one of INLET_LABELS"));
        }
        if keyset(&self.mdot_kgps) != species_set() {
            return Err(sie("inlet record must carry exactly SPECIES"));
        }
        for (s, v) in &self.mdot_kgps {
            if !(v.is_finite() && *v >= 0.0) {
                return Err(sie(format!("mdot[{s}] must be finite and >= 0")));
            }
        }
        if pyops::py_sum(self.mdot_kgps.iter().map(|(_, v)| *v)) <= 0.0 {
            return Err(sie("total inlet mass flow must be > 0"));
        }
        for (k, v) in [("p_total_Pa", self.p_total_pa), ("T_K", self.t_k)] {
            if !(v.is_finite() && v > 0.0) {
                return Err(sie(format!("{k} must be finite and > 0")));
            }
        }
        if !EVIDENCE_CLASSES.contains(&self.evidence_class.as_str()) {
            return Err(sie("evidence_class must be one of EVIDENCE_CLASSES"));
        }
        if self.source.trim().is_empty() {
            return Err(sie("inlet record needs a source"));
        }
        if let Some(ps) = &self.p_species_pa {
            let conv = self.module_partial_pressures()?;
            if keyset(ps) != species_set() {
                return Err(sie("p_species_Pa must carry exactly O, N2, O2"));
            }
            if (pyops::div(pyops::py_sum(ps.iter().map(|(_, v)| *v)), self.p_total_pa)? - 1.0).abs() > 1e-9 {
                return Err(sie("p_species_Pa does not sum to p_total_Pa"));
            }
            for s in SPECIES {
                if (sp(ps, s) - sp(&conv, s)).abs() > 1e-6 * self.p_total_pa {
                    return Err(sie(format!("p_species_Pa[{s}] differs from the DragCompressor convention")));
                }
            }
        }
        Ok(())
    }

    pub fn module_partial_pressures(&self) -> PyResult<SpMap> {
        let mut nflow = vec![];
        for s in SPECIES {
            nflow
                .push((s.to_string(), pyops::div(sp(&self.mdot_kgps, s), species_mass(s).map_err(|_| key_error(s))?)?));
        }
        let tot = pyops::py_sum(nflow.iter().map(|(_, v)| *v));
        let mut out = vec![];
        for (s, n) in nflow {
            out.push((s, pyops::div(self.p_total_pa * n, tot)?));
        }
        Ok(out)
    }

    /// The SPECIES-ordered mass flows (`{s: float(mdot[s]) for s in SPECIES}`).
    pub fn mdot_species_order(&self) -> SpMap {
        SPECIES.iter().map(|s| (s.to_string(), sp(&self.mdot_kgps, s))).collect()
    }

    pub fn as_dict(&self) -> Value {
        Obj::new()
            .s("record_id", &self.record_id)
            .s("label", &self.label)
            .set("mdot_kgps", crate::rec::fmap(self.mdot_kgps.iter().map(|(k, v)| (k.as_str(), *v))))
            .f("p_total_Pa", self.p_total_pa)
            .f("T_K", self.t_k)
            .s("source", &self.source)
            .s("evidence_class", &self.evidence_class)
            .s("status", &self.status)
            .set(
                "p_species_Pa",
                match &self.p_species_pa {
                    Some(p) if !p.is_empty() => crate::rec::fmap(p.iter().map(|(k, v)| (k.as_str(), *v))),
                    _ => Value::Null,
                },
            )
            .set("extra", Value::Object(self.extra.clone()))
            .build()
    }
}

// ------------------------------------------------------------------------------------------------ geometry / grid
/// Tip radius of an annulus of swept area A with hub ratio nu: sqrt(A / (pi (1 - nu^2))).
pub fn r_turbo_from_area(a_m2: f64, hub_ratio: f64) -> PyResult<f64> {
    if !(0.0 <= hub_ratio && hub_ratio < 1.0) {
        return Err(sie("hub ratio must be in [0, 1)"));
    }
    pyops::sqrt(pyops::div(a_m2, PI * (1.0 - pyops::pow(hub_ratio, 2.0)?))?)
}

/// Explicit hub geometry record of a turbo-row annulus (A9.13 S6.7).
pub fn hub_geometry(a_m2: f64, hub_ratio: f64) -> PyResult<Map<String, Value>> {
    let r = r_turbo_from_area(a_m2, hub_ratio)?;
    let mut m = Map::new();
    m.insert("hub_ratio".into(), fnum(hub_ratio));
    m.insert("R_hub_m".into(), fnum(hub_ratio * r));
    m.insert("blade_span_m".into(), fnum(r * (1.0 - hub_ratio)));
    m.insert(
        "hub_geometry_status".into(),
        Value::String(if hub_ratio == 0.0 { HUB_ZERO_BOUND } else { HUB_PARAMETRIC }.into()),
    );
    Ok(m)
}

pub fn rpm_from_tip(u_mps: f64, r_m: f64) -> PyResult<f64> {
    pyops::div(pyops::div(u_mps, r_m)? * 60.0, 2.0 * PI)
}

#[derive(Debug, Clone, PartialEq)]
pub struct SearchGrid {
    pub n_turbo: Vec<i64>,
    pub a_turbo_m2: Vec<f64>,
    pub n_tip_speeds: i64,
    pub n_drag: Vec<i64>,
    pub materials: Vec<String>,
    pub hub_ratios: Vec<Value>,
}

impl SearchGrid {
    pub fn default_grid() -> PyResult<SearchGrid> {
        let g = SearchGrid {
            n_turbo: (1..=SIZE_FOR_MAX_TURBO_ROWS).collect(),
            a_turbo_m2: vec![
                A_INLET_MIN_B025_RANGE_M2.0,
                PI * pyops::pow(LI2015_INLET_DIAMETER_M / 2.0, 2.0)?,
                A_INLET_MIN_B025_RANGE_M2.1,
            ],
            n_tip_speeds: 6,
            n_drag: (0..=SIZE_FOR_MAX_DRAG_STAGES).collect(),
            materials: vec!["Ti6Al4V".into()],
            hub_ratios: HUB_RATIO_PARAMETRIC.iter().map(|h| fnum(*h)).collect(),
        };
        Ok(g)
    }

    pub fn validate(&self, ctx: Ctx) -> PyResult<()> {
        for m in &self.materials {
            if cited_allowable(m).is_none() && ctx.registry.bases_for(m).is_empty() {
                return Err(sie(format!(
                    "search material {} has neither a registered rotor-strength basis nor the legacy cited \
sensitivity allowable (A9.13 S6.9 / A9.9 S2.3)",
                    rs::py_str_repr(m)
                )));
            }
        }
        if self.a_turbo_m2.iter().any(|a| *a <= 0.0) || self.n_tip_speeds < 2 {
            return Err(sie("bad grid"));
        }
        if self.hub_ratios.is_empty()
            || self.hub_ratios.iter().any(|h| !matches!(real(Some(h)), Some(x) if (0.0..1.0).contains(&x)))
        {
            return Err(sie("hub ratios must be finite and in [0, 1)"));
        }
        Ok(())
    }

    pub fn tip_speeds(&self, r_turbo_m: f64) -> Vec<f64> {
        let u_lo = r_turbo_m * RPM_SEARCH_MIN * 2.0 * PI / 60.0;
        let u_hi = U_TIP_PUBLISHED_MAX_MPS;
        if u_lo >= u_hi {
            return vec![];
        }
        let n = self.n_tip_speeds;
        (0..n).map(|i| u_lo + (u_hi - u_lo) * i as f64 / (n - 1) as f64).collect()
    }

    /// Design points; zero-hub ids keep the form T{n}-A{i}-U{j}-D{k}-{mat}, others get the suffix -H{nu}.
    pub fn designs(&self) -> PyResult<Vec<Map<String, Value>>> {
        let mut out = vec![];
        for (ia, a) in self.a_turbo_m2.iter().enumerate() {
            for nuv in &self.hub_ratios {
                let nu = real(Some(nuv)).expect("validated");
                let r = r_turbo_from_area(*a, nu)?;
                for (iu, u) in self.tip_speeds(r).into_iter().enumerate() {
                    for nt in &self.n_turbo {
                        for nd in &self.n_drag {
                            for mat in &self.materials {
                                let sfx =
                                    if nu == 0.0 { String::new() } else { format!("-H{}", pyops::py_format_g(nu)) };
                                let mut d = Map::new();
                                d.insert("id".into(), Value::String(format!("T{nt}-A{ia}-U{iu}-D{nd}-{mat}{sfx}")));
                                d.insert("N_turbo".into(), Value::from(*nt));
                                d.insert("A_turbo_m2".into(), fnum(*a));
                                d.insert("R_turbo_m".into(), fnum(r));
                                d.insert("u_tip_turbo_mps".into(), fnum(u));
                                d.insert("rpm".into(), fnum(rpm_from_tip(u, r)?));
                                d.insert("N_drag".into(), Value::from(*nd));
                                d.insert("rotor_material".into(), Value::String(mat.clone()));
                                for (k, v) in hub_geometry(*a, nu)? {
                                    d.insert(k, v);
                                }
                                out.push(d);
                            }
                        }
                    }
                }
            }
        }
        Ok(out)
    }
}

// ------------------------------------------------------------------------------------------------ strict mode
fn ev_get<'a>(ev: Option<&'a Map<String, Value>>, k: &str) -> Option<&'a Value> {
    ev.and_then(|e| e.get(k))
}

fn evidence_missing(e: Option<&Value>) -> bool {
    let Some(e) = e else { return true };
    let class = e.get("evidence_class");
    let bad_class = match class {
        None | Some(Value::Null) => true,
        Some(Value::String(s)) => s == "assumed" || s == "TBD",
        _ => false,
    };
    let src = e.get("source").map(py_str).unwrap_or_default();
    bad_class || src.trim().is_empty()
}

fn positive_finite(v: Option<&Value>) -> bool {
    match v {
        Some(Value::Number(n)) => n.as_f64().map(|x| x.is_finite() && x > 0.0).unwrap_or(false),
        Some(Value::String(s)) if nonfinite_text(s).is_some() => false,
        Some(Value::String(s)) => s.trim().parse::<f64>().map(|x| x.is_finite() && x > 0.0).unwrap_or(false),
        _ => false,
    }
}

fn blocker(id: &str, what: &str, status: &str, needs: &str) -> Value {
    Obj::new().s("id", id).s("what", what).s("status", status).s("needs", needs).build()
}

/// What MODE_STRICT needs before it may evaluate anything (empty = evaluable).
pub fn strict_blockers(ctx: Ctx, inlet: &InletRecord, ev: Option<&Map<String, Value>>) -> PyResult<Vec<Value>> {
    let mut out = vec![];
    for (f, role, name, _units, test) in FIELD_ROLES {
        if role != FIXED {
            continue;
        }
        let e = ev_get(ev, f);
        if evidence_missing(e) {
            out.push(blocker(
                &format!("C-{f}"),
                name,
                "CODE_DEFAULT_UNCITED (assumed)",
                &format!("non-assumed evidence (compressor_downselect test {test})"),
            ));
        } else if let Err(exc) = validate_coefficient(f, e.and_then(|x| x.get("value"))) {
            out.push(blocker(
                &format!("C-{f}"),
                name,
                "NON_FINITE_OR_OUT_OF_DOMAIN",
                &format!("a finite in-domain value ({})", exc.message),
            ));
        }
    }
    if inlet.label != LABEL_INTERFACE || inlet.evidence_class == "assumed" {
        out.push(blocker(
            "INLET",
            &format!("inlet record {}", inlet.record_id),
            &inlet.label,
            "an F1/F2 interface record (abep_sim/design/intake_synthesis.py F1-ID-03, abep_sim/design/filter_stage.py \
F2-IF-03) with non-assumed evidence",
        ));
    }
    let dens = ev_get(ev, "rotor_density");
    if evidence_missing(dens) {
        out.push(blocker("P-TI64-DENSITY", "rotor density", "UNCITED_DB_PRIOR", "cited density for the rotor alloy"));
    } else if !positive_finite(dens.and_then(|d| d.get("value"))) {
        out.push(blocker(
            "P-TI64-DENSITY",
            "rotor density",
            "NON_FINITE_OR_OUT_OF_DOMAIN",
            "a finite, positive cited density for the rotor alloy",
        ));
    } else {
        let dv = dens.and_then(|d| d.get("value")).expect("value");
        let x = match dv {
            Value::Number(n) => n.as_f64().unwrap_or(f64::NAN),
            Value::String(s) => s.trim().parse::<f64>().unwrap_or(f64::NAN),
            _ => f64::NAN,
        };
        let db = ctx.materials.get("Ti6Al4V")?.density;
        if (pyops::div(x, db)? - 1.0).abs() > 1e-9 {
            out.push(blocker(
                "P-TI64-DENSITY",
                "rotor density",
                "MODULE_CANNOT_REPRESENT",
                "the cited density differs from materials.DB, which DragCompressor reads; a materials change is a \
model change (CLAUDE.md rule 2), outside this lane",
            ));
        }
    }
    let bid = match ev_get(ev, "rotor_strength_basis_id") {
        Some(Value::Object(m)) => m.get("value").and_then(|v| v.as_str()).map(String::from),
        _ => None,
    };
    if ctx.registry.get_registered(bid.as_deref()).is_none() {
        out.push(blocker(
            "ROTOR-STRENGTH-BASIS",
            "registered rotor-strength basis (A9.9 S2.3 / MCC-03)",
            ST_NOT_EVALUATED_MATERIAL_BASIS,
            "an owner-registered basis in abep_sim.rotor_strength.REGISTRY (stock / product form, design temperature, \
yield AND ultimate allowables, factors, maximum speed, proof spin); supply its id as \
coefficient_evidence['rotor_strength_basis_id']",
        ));
    }
    Ok(out)
}

fn basis_id(design: &Map<String, Value>, ev: Option<&Map<String, Value>>) -> Option<String> {
    if let Some(v) = design.get("rotor_strength_basis_id") {
        let truthy = match v {
            Value::Null => false,
            Value::String(s) => !s.is_empty(),
            Value::Bool(b) => *b,
            _ => true,
        };
        if truthy {
            return v.as_str().map(String::from);
        }
    }
    match ev_get(ev, "rotor_strength_basis_id") {
        Some(Value::Object(m)) => m.get("value").and_then(|v| v.as_str()).map(String::from),
        _ => None,
    }
}

fn not_evaluated_status(blk: &[Value]) -> &'static str {
    if blk.iter().any(|b| b["id"] == "ROTOR-STRENGTH-BASIS") {
        ST_NOT_EVALUATED_MATERIAL_BASIS
    } else {
        ST_NOT_EVALUATED
    }
}

// ------------------------------------------------------------------------------------------------ mirror / Kn
/// Diagnostic mirror of DragCompressor.run_once's pressure cascade exposing the unclipped per-species K.
pub fn stage_trace(comp: &DragCompressor, p_in_pa: f64, mdot: &SpMap) -> PyResult<Value> {
    let u = comp.u();
    let h = comp.h_mm * 1e-3;
    let w = comp.w_mm * 1e-3;
    let l = comp.l_per_stage_m;
    let s0 = comp.xi * u * h * w / 2.0;
    let mut nflow: SpMap = vec![];
    for (s, m) in mdot {
        nflow.push((s.clone(), pyops::div(*m, species_mass(s).map_err(|_| key_error(s))?)?));
    }
    let mut ntot = pyops::py_sum(nflow.iter().map(|(_, v)| *v));
    if ntot == 0.0 {
        ntot = 1e-30;
    }
    let mut p_s: SpMap = vec![];
    for (s, n) in &nflow {
        p_s.push((s.clone(), pyops::div(p_in_pa * n, ntot)?));
    }
    let u_t = comp.u_turbo();
    let s_t = comp.turbo_k_s * u_t * comp.turbo_area_m2;
    let mut stages = vec![];
    let mut run_stage =
        |kind: &str, idx: i64, ln_k0: &dyn Fn(f64) -> PyResult<f64>, s_cap: f64, p_s: &mut SpMap| -> PyResult<()> {
            let mut k_raw = Map::new();
            for (s, n) in &nflow {
                let cb = comp.cbar(species_mass(s).map_err(|_| key_error(s))?)?;
                let k0 = pyops::exp(ln_k0(cb)?)?;
                let q = n * K_B * comp.t_gas_k;
                let ps = sp(p_s, s);
                let k = k0 - pyops::div((k0 - 1.0) * q, py_max(s_cap * ps, 1e-30))?;
                k_raw.insert(s.clone(), fnum(k));
                for (k2, v) in p_s.iter_mut() {
                    if k2 == s {
                        *v *= py_max(pyops::py_min(k, k0), 1.0);
                    }
                }
            }
            stages.push(
                Obj::new()
                    .s("kind", kind)
                    .set("index", idx)
                    .set("K_unclipped", Value::Object(k_raw))
                    .f("p_out_Pa", pyops::py_sum(p_s.iter().map(|(_, v)| *v)))
                    .set("p_species_out_Pa", crate::rec::fmap(p_s.iter().map(|(k, v)| (k.as_str(), *v))))
                    .build(),
            );
            Ok(())
        };
    for row in 0..comp.turbo_rows.max(0) {
        let kk = comp.turbo_k_k;
        run_stage("turbo", row, &move |cb| pyops::div(kk * u_t, cb), s_t, &mut p_s)?;
    }
    for st in 0..comp.n_stages.max(0) {
        let xi = comp.xi;
        run_stage("drag", st, &move |cb| Ok(pyops::div(2.0 * u * l, cb * h)? * xi), s0, &mut p_s)?;
    }
    Ok(Obj::new().set("stages", Value::Array(stages)).f("p_out_Pa", pyops::py_sum(p_s.iter().map(|(_, v)| *v))).build())
}

/// Kn = lambda / h with lambda = 1 / (sqrt(2) sum_k n_k sigma_k) over N2, O2 (O omitted: an upper bound).
pub fn drag_knudsen_upper(p_species_pa: &SpMap, t_k: f64, h_m: f64) -> PyResult<f64> {
    let mut denom = 0.0;
    for (s, sig) in SIGMA_C_M2 {
        let p = p_species_pa.iter().find(|(k, _)| k == s).map(|(_, v)| *v).unwrap_or(0.0);
        denom += pyops::div(p, K_B * t_k)? * sig;
    }
    if denom <= 0.0 {
        return Ok(f64::INFINITY);
    }
    pyops::div(pyops::div(1.0, 2.0f64.sqrt() * denom)?, h_m)
}

// ------------------------------------------------------------------------------------------------ validation
/// Refuse a non-finite or out-of-domain FIXED coefficient value.
pub fn validate_coefficient(name: &str, value: Option<&Value>) -> PyResult<f64> {
    if field_role(name).map(|f| f.1) != Some(FIXED) {
        return Err(sie(format!("only FIXED coefficients can be overridden, not {name}")));
    }
    let v = real(value);
    let dom = COEFFICIENT_DOMAIN.iter().find(|(k, _)| *k == name).map(|(_, d)| *d).unwrap_or("pos");
    let bad = match v {
        None => true,
        Some(x) => match dom {
            "pos" => !(x > 0.0),
            "nonneg" => !(x >= 0.0),
            _ => !(0.0 < x && x <= 1.0),
        },
    };
    if bad {
        let shown = value.map(py_value_repr).unwrap_or_else(|| "None".into());
        return Err(sie(format!("coefficient {name}={shown} is non-finite or outside its domain ({dom})")));
    }
    Ok(v.expect("checked"))
}

fn design_id(design: &Map<String, Value>) -> String {
    design.get("id").map(py_str).unwrap_or_else(|| "None".into())
}

/// Refuse a malformed design vector (SW-03).
pub fn validate_design(ctx: Ctx, design: &Map<String, Value>) -> PyResult<()> {
    let id = design_id(design);
    for k in ["rpm", "A_turbo_m2"] {
        if !matches!(real(design.get(k)), Some(x) if x > 0.0) {
            return Err(sie(format!("design {id}: {k} must be finite and > 0")));
        }
    }
    if design.contains_key("R_turbo_m") && !matches!(real(design.get("R_turbo_m")), Some(x) if x > 0.0) {
        return Err(sie(format!("design {id}: R_turbo_m must be finite and > 0")));
    }
    for k in ["N_turbo", "N_drag"] {
        let ok = match design.get(k) {
            Some(Value::Number(n)) => {
                n.as_f64().map(|x| x.is_finite() && x == x.trunc() && x.trunc() >= 0.0).unwrap_or(false)
            }
            _ => false,
        };
        if !ok {
            return Err(sie(format!("design {id}: {k} must be a non-negative integer")));
        }
    }
    let mat_ok = matches!(design.get("rotor_material"), Some(Value::String(m)) if ctx.materials.contains(m));
    if !mat_ok {
        return Err(sie(format!("design {id}: rotor_material is not in materials.DB")));
    }
    if design.contains_key("hub_ratio") {
        let nu = match real(design.get("hub_ratio")) {
            Some(x) if (0.0..1.0).contains(&x) => x,
            _ => return Err(sie(format!("design {id}: hub_ratio must be in [0, 1)"))),
        };
        if design.contains_key("R_turbo_m") {
            let a = real(design.get("A_turbo_m2")).expect("checked");
            let r_exp = r_turbo_from_area(a, nu)?;
            let r = real(design.get("R_turbo_m")).expect("checked");
            if (pyops::div(r, r_exp)? - 1.0).abs() > 1e-9 {
                return Err(sie(format!(
                    "design {id}: R_turbo_m inconsistent with A_turbo and hub_ratio (refused, not repaired)"
                )));
            }
        }
    }
    Ok(())
}

fn as_int(v: Option<&Value>) -> i64 {
    v.and_then(|x| x.as_f64()).map(|x| x as i64).unwrap_or(0)
}

/// The DragCompressor of one design point (FIXED coefficients optionally overridden).
pub fn build_compressor(
    ctx: Ctx,
    design: &Map<String, Value>,
    t_gas_k: f64,
    overrides: &[(String, Value)],
) -> PyResult<DragCompressor> {
    validate_design(ctx, design)?;
    let mut c = DragCompressor::default();
    for (f, v) in overrides {
        let x = validate_coefficient(f, Some(v))?;
        c.set_float(f, x);
    }
    let a = real(design.get("A_turbo_m2")).expect("validated");
    let hub = design.get("hub_ratio").and_then(|v| v.as_f64()).unwrap_or(0.0);
    let r_default = r_turbo_from_area(a, hub)?;
    let r = match design.get("R_turbo_m") {
        Some(v) => v.as_f64().unwrap_or(f64::NAN),
        None => r_default,
    };
    c.turbo_rows = as_int(design.get("N_turbo"));
    c.turbo_area_m2 = a;
    c.turbo_radius_m = r;
    c.n_stages = as_int(design.get("N_drag"));
    c.rpm = real(design.get("rpm")).expect("validated");
    c.rpm_is_int = false;
    c.rotor_material = design["rotor_material"].as_str().expect("validated").to_string();
    c.t_gas_k = t_gas_k;
    Ok(c)
}

fn finite_all(xs: &[f64]) -> bool {
    xs.iter().all(|x| x.is_finite())
}

fn catchable(class: PyClass) -> bool {
    matches!(class, PyClass::OverflowError | PyClass::ZeroDivisionError | PyClass::ValueError)
}

fn f64_of(m: &Map<String, Value>, k: &str) -> f64 {
    m.get(k).and_then(as_f64).unwrap_or(f64::NAN)
}

fn sub_f64(m: &Map<String, Value>, k: &str, s: &str) -> PyResult<f64> {
    m.get(k).and_then(|x| x.get(s)).and_then(as_f64).ok_or_else(|| key_error(s))
}

/// Evaluate one design point: status, reasons, diagnostics and (feasible only) outputs.
pub fn evaluate_design(
    ctx: Ctx,
    design: &Map<String, Value>,
    inlet: &InletRecord,
    mode: &str,
    ev: Option<&Map<String, Value>>,
) -> PyResult<Value> {
    if !MODES.contains(&mode) {
        return Err(sie("mode must be one of MODES"));
    }
    let id_val = design.get("id").cloned().unwrap_or(Value::Null);
    if mode == MODE_STRICT {
        let blk = strict_blockers(ctx, inlet, ev)?;
        if !blk.is_empty() {
            let rq = if ctx.registry.get_registered(basis_id(design, ev).as_deref()).is_none() {
                ST_NOT_EVALUATED_MATERIAL_BASIS
            } else {
                ST_NOT_EVALUATED
            };
            return Ok(Obj::new()
                .set("id", id_val)
                .s("status", not_evaluated_status(&blk))
                .set("reasons", Value::Array(vec![]))
                .set("blockers", Value::Array(blk))
                .set("outputs", Value::Null)
                .set("diagnostics", Value::Null)
                .s("rotor_qualification", rq)
                .build());
        }
    }
    let mut overrides: Vec<(String, Value)> = vec![];
    for (f, x) in ev.into_iter().flatten() {
        if field_role(f).map(|r| r.1) == Some(FIXED) {
            overrides.push((f.clone(), x.get("value").cloned().ok_or_else(|| key_error("value"))?));
        }
    }
    let comp = build_compressor(ctx, design, inlet.t_k, &overrides)?;
    let md = inlet.mdot_species_order();
    let mut reasons: Vec<&str> = vec![];
    let mut diag = Map::new();
    let mat = comp.rotor_material.clone();
    let u_t = comp.u_turbo();
    let u_d = comp.u();
    let u_max_tip = py_max(u_t, u_d);
    let rho = ctx.materials.get(&mat)?.density;
    let sigma = rho * pyops::pow(u_max_tip, 2.0)?;
    let hub = design.get("hub_ratio").and_then(|v| v.as_f64()).unwrap_or(0.0);
    diag.insert("u_tip_turbo_mps".into(), fnum(u_t));
    diag.insert("u_tip_drag_mps".into(), fnum(u_d));
    diag.insert("hoop_stress_Pa".into(), fnum(sigma));
    diag.insert("module_rotor_ok_uncited_db_yield".into(), Value::Null);
    diag.insert("hub_ratio".into(), fnum(hub));
    diag.insert(
        "hub_geometry_status".into(),
        design.get("hub_geometry_status").cloned().unwrap_or(Value::String(HUB_ZERO_BOUND.into())),
    );
    let bid = basis_id(design, ev);
    let registered = ctx.registry.get_registered(bid.as_deref()).is_some();
    let extra_v = match design.get("material_extra_basis") {
        Some(Value::Object(m)) if !m.is_empty() => Some(m.clone()),
        _ => match ev_get(ev, "material_extra_basis") {
            Some(Value::Object(m)) => Some(m.clone()),
            _ => None,
        },
    };
    let admission = material_admission(ctx, &mat, extra_v.as_ref())?;
    diag.insert("material_admission".into(), admission["status"].clone());
    let missing_extra =
        admission.get("missing_extra").and_then(|v| v.as_array()).map(|a| !a.is_empty()).unwrap_or(false);
    if registered && missing_extra {
        reasons.push(R_READMISSION_RECORDS);
        diag.insert("stress_case".into(), Value::String(ST_NOT_EVALUATED_MATERIAL_BASIS.into()));
    } else if registered {
        diag.insert("stress_case".into(), Value::String(STRESS_CASE_REGISTERED.into()));
    } else if let Some(allow) = cited_allowable(&mat) {
        let margin = pyops::div(allow, comp.stress_safety * sigma)? - 1.0;
        diag.insert("allowable_Pa".into(), fnum(allow));
        diag.insert("safety_factor".into(), fnum(comp.stress_safety));
        diag.insert("stress_margin".into(), fnum(margin));
        diag.insert("u_allow_with_sf_mps".into(), fnum(pyops::sqrt(pyops::div(allow, comp.stress_safety * rho)?)?));
        diag.insert("stress_case".into(), Value::String(STRESS_CASE_LEGACY.into()));
        diag.insert("stress_case_label".into(), Value::String(rs::LEGACY_SENSITIVITY_LABEL.into()));
        if !(margin >= 0.0) {
            reasons.push(R_STRESS);
        }
    } else {
        reasons.push(R_ALLOWABLE_TBD);
        diag.insert("stress_margin".into(), Value::Null);
        diag.insert("stress_case".into(), Value::String(ST_NOT_EVALUATED_MATERIAL_BASIS.into()));
    }
    if u_t > U_TIP_PUBLISHED_MAX_MPS * (1.0 + 1e-12) {
        reasons.push(R_TIP_DOMAIN);
    }
    if inlet.p_total_pa > P_MOLECULAR_LIMIT_PA {
        reasons.push(R_INLET_DOMAIN);
    }

    // self-consistent run, then the independent convergence re-check
    struct Ok_ {
        r: Map<String, Value>,
        again: Map<String, Value>,
        resid: f64,
        trace: Value,
    }
    let attempt = (|| -> PyResult<(Map<String, Value>, Option<Ok_>, bool)> {
        let r = comp.run(ctx, inlet.p_total_pa, &md, true)?;
        let inner = (|| -> PyResult<Ok_> {
            let mut through: SpMap = vec![];
            for s in SPECIES {
                through.push((s.to_string(), sp(&md, s) + sub_f64(&r, "recirculated_kgps", s)?));
            }
            let again = comp.run_once(ctx, inlet.p_total_pa, &through)?;
            let mut rv = vec![];
            for s in SPECIES {
                rv.push(pyops::div(
                    (py_max(sub_f64(&again, "leak_kgps", s)?, 0.0) - sub_f64(&r, "recirculated_kgps", s)?).abs(),
                    py_max(sp(&md, s), 1e-15),
                )?);
            }
            let resid = pyops::py_max_iter(rv).unwrap_or(f64::NAN);
            let trace = stage_trace(&comp, inlet.p_total_pa, &through)?;
            Ok(Ok_ { r: r.clone(), again, resid, trace })
        })();
        match inner {
            Ok(o) => {
                let fin = finite_all(&[
                    f64_of(&o.r, "p_out_Pa"),
                    f64_of(&o.r, "P_el_W"),
                    f64_of(&o.r, "mass_kg"),
                    f64_of(&o.r, "T_comp_K"),
                    o.resid,
                    as_f64(&o.trace["p_out_Pa"]).unwrap_or(f64::NAN),
                ]);
                Ok((r, Some(o), fin))
            }
            Err(e) => Err(e),
        }
    })();
    let mut r_opt: Option<Map<String, Value>> = None;
    let mut ok_opt: Option<Ok_> = None;
    let finite;
    match attempt {
        Ok((r, o, fin)) => {
            r_opt = Some(r);
            ok_opt = o;
            finite = fin;
        }
        Err(e) if catchable(e.class) => {
            reasons.push(R_MODEL);
            diag.insert("exception".into(), Value::String(e.py_text()));
            finite = false;
            // the reference keeps r when run() succeeded and a later step raised
            if let Ok(r) = comp.run(ctx, inlet.p_total_pa, &md, true) {
                r_opt = Some(r);
            }
        }
        Err(e) => return Err(e),
    }
    if r_opt.is_some() && !finite && !reasons.contains(&R_MODEL) {
        reasons.push(R_MODEL);
    }
    if !reasons.contains(&R_MODEL) {
        let o = ok_opt.as_ref().expect("evaluated");
        let r = &o.r;
        diag.insert("recirculation_residual".into(), fnum(o.resid));
        diag.insert("module_rotor_ok_uncited_db_yield".into(), Value::Bool(r["rotor_ok"] == Value::Bool(true)));
        if o.resid > RECIRC_RTOL {
            reasons.push(R_NONCONV);
        }
        let tp = as_f64(&o.trace["p_out_Pa"]).unwrap_or(f64::NAN);
        let ap = f64_of(&o.again, "p_out_Pa");
        if (pyops::div(tp, ap)? - 1.0).abs() > MIRROR_RTOL {
            reasons.push(R_MODEL);
            diag.insert(
                "exception".into(),
                Value::String("stage_trace mirror does not reproduce DragCompressor._run_once p_out".into()),
            );
        } else {
            let stages = o.trace["stages"].as_array().cloned().unwrap_or_default();
            let k_min = if stages.is_empty() {
                None
            } else {
                pyops::py_min_iter(stages.iter().map(|st| {
                    let ks: Vec<f64> = st["K_unclipped"]
                        .as_object()
                        .map(|m| SPECIES.iter().filter_map(|s| m.get(*s)).filter_map(as_f64).collect())
                        .unwrap_or_default();
                    pyops::py_min_iter(ks).unwrap_or(f64::NAN)
                }))
            };
            diag.insert("K_unclipped_min".into(), crate::rec::onum(k_min));
            if matches!(k_min, Some(k) if k < 1.0) {
                reasons.push(R_CLIP);
            }
            let p_stage_max = pyops::py_max_iter(
                std::iter::once(inlet.p_total_pa)
                    .chain(stages.iter().map(|st| as_f64(&st["p_out_Pa"]).unwrap_or(f64::NAN))),
            )
            .expect("non-empty");
            diag.insert("p_stage_max_Pa".into(), fnum(p_stage_max));
            if p_stage_max > P_MOLECULAR_LIMIT_PA {
                reasons.push(R_DOMAIN_P);
            }
            let drag: Vec<&Value> = stages.iter().filter(|st| st["kind"] == "drag").collect();
            if drag.is_empty() {
                diag.insert("drag_Kn_min_upper_bound_O_omitted".into(), Value::Null);
            } else {
                let mut kns = vec![];
                for st in &drag {
                    let ps: SpMap = st["p_species_out_Pa"]
                        .as_object()
                        .map(|m| {
                            SPECIES
                                .iter()
                                .filter_map(|s| m.get(*s).and_then(as_f64).map(|v| (s.to_string(), v)))
                                .collect()
                        })
                        .unwrap_or_default();
                    kns.push(drag_knudsen_upper(&ps, comp.t_gas_k, comp.h_mm * 1e-3)?);
                }
                let kn = pyops::py_min_iter(kns).expect("non-empty");
                diag.insert("drag_Kn_min_upper_bound_O_omitted".into(), fnum(kn));
                if kn < KN_FREE_MOLECULAR_MIN {
                    reasons.push(R_DOMAIN_KN);
                }
            }
            let t_lim = ctx.materials.get(&mat)?.t_max_k;
            let tc = f64_of(r, "T_comp_K");
            diag.insert("T_comp_K".into(), fnum(tc));
            if tc > t_lim {
                reasons.push(R_THERMAL);
            }
        }
    }

    // rotor qualification through the registered-basis gate
    let t_rotor = diag.get("T_comp_K").and_then(as_f64).unwrap_or(f64::NAN);
    let stock = match design.get("rotor_stock_thickness_m") {
        None | Some(Value::Null) => Arg::None,
        Some(Value::Number(n)) => Arg::Num(n.as_f64().unwrap_or(f64::NAN)),
        _ => Arg::Other,
    };
    let rq = rs::qualify_rotor(
        ctx.registry,
        bid.as_deref(),
        &mat,
        Arg::Num(u_max_tip),
        Arg::Num(comp.rpm),
        Arg::Num(t_rotor),
        stock,
    )?;
    let mut rq_diag = Map::new();
    for k in [
        "rotor_qualification",
        "rotor_ok",
        "rotor_strength_basis_id",
        "rotor_qualification_reasons",
        "margin_yield",
        "margin_ultimate",
    ] {
        rq_diag.insert(k.into(), rq[k].clone());
    }
    let mut rq_status = rq["rotor_qualification"].as_str().unwrap_or("").to_string();
    if registered && reasons.contains(&R_READMISSION_RECORDS) {
        rq_status = ST_NOT_EVALUATED_MATERIAL_BASIS.into();
        rq_diag.insert("rotor_qualification".into(), Value::String(ST_NOT_EVALUATED_MATERIAL_BASIS.into()));
        rq_diag.insert("rotor_ok".into(), Value::Bool(false));
    } else if registered {
        if rq_status == rs::Q_FAIL {
            reasons.push(R_ROTOR_QUAL_FAIL);
        } else if rq_status != rs::Q_PASS {
            reasons.push(R_ROTOR_QUAL_OOD);
        }
    }
    diag.insert("rotor_qualification".into(), Value::Object(rq_diag));
    let mut design_rec = design.clone();
    design_rec.remove("id");
    let mut rec = Obj::new()
        .set("id", id_val)
        .set("design", Value::Object(design_rec))
        .set("reasons", slist(&reasons))
        .set("diagnostics", Value::Object(diag))
        .set("outputs", Value::Null)
        .s("rotor_structural_acceptance", &rq_status)
        .s(
            "architecture_point_status",
            if reasons.iter().any(|x| DOMAIN_REASONS.contains(x)) { ST_NOT_EVALUATED_OOD } else { u13::DOMAIN_IN },
        );
    if mode == MODE_STRICT && !registered {
        return Ok(rec.s("status", ST_NOT_EVALUATED_MATERIAL_BASIS).build());
    }
    if !reasons.is_empty() {
        let st = if reasons.iter().any(|x| INLET_INDEPENDENT_REASONS.contains(x)) {
            ST_REJECTED
        } else if reasons.iter().any(|x| DOMAIN_REASONS.contains(x)) {
            ST_NOT_EVALUATED_OOD
        } else if reasons.contains(&R_ROTOR_QUAL_OOD) || reasons.contains(&R_READMISSION_RECORDS) {
            ST_NOT_EVALUATED_MATERIAL_BASIS
        } else {
            ST_REJECTED
        };
        return Ok(rec.s("status", st).build());
    }
    rec.insert("status", if mode == MODE_STRICT { ST_FEASIBLE_STRICT } else { ST_FEASIBLE });
    let r = r_opt.expect("evaluated");
    let mut delivered: SpMap = vec![];
    for s in SPECIES {
        delivered.push((s.to_string(), sub_f64(&r, "delivered_kgps", s)?));
    }
    let dtot = pyops::py_sum(delivered.iter().map(|(_, v)| *v));
    let mut nflow: SpMap = vec![];
    for (s, v) in &delivered {
        nflow.push((s.clone(), pyops::div(*v, species_mass(s).map_err(|_| key_error(s))?)?));
    }
    let ntot = pyops::py_sum(nflow.iter().map(|(_, v)| *v));
    let mut cr = vec![];
    let mut xo = vec![];
    let mut xd = vec![];
    for s in SPECIES {
        cr.push((s, sub_f64(&r, "CR_by_species", s)?));
        xo.push((s, sub_f64(&r, "composition_out", s)?));
        xd.push((s, pyops::div(sp(&nflow, s), ntot)?));
    }
    let f = |k: &str| f64_of(&r, k);
    let outputs = Obj::new()
        .f("P_out_Pa", f("p_out_Pa"))
        .f("CR_total", f("CR_active"))
        .set("CR_by_species", crate::rec::fmap(cr))
        .set("mdot_delivered_kgps", crate::rec::fmap(delivered.iter().map(|(k, v)| (k.as_str(), *v))))
        .f("mdot_delivered_total_kgps", dtot)
        .set("x_s_out_partial_pressure", crate::rec::fmap(xo))
        .set("x_s_delivered_flow_mole", crate::rec::fmap(xd))
        .f("P_compressor_el_W", f("P_el_W"))
        .f("P_shaft_W", f("P_gas_W") + f("P_bear_W"))
        .f("P_gas_drag_W", f("P_gas_W"))
        .f("P_bearing_W", f("P_bear_W"))
        .f("eta_motor", comp.eta_motor)
        .f("P_ctrl_W", comp.p_ctrl_w)
        .f("m_compressor_kg", f("mass_kg"))
        .f("T_compressor_K", f("T_comp_K"))
        .f("T_gas_K", comp.t_gas_k)
        .f("S_turbo_m3_s", f("S_turbo_m3_s"))
        .f("S0_drag_m3_s", f("S0_drag_m3_s"))
        .f("recirculation_frac", f("recirculation_frac"))
        .f("mass_allocation_margin_kg", OWNER_MASS_ALLOCATION_KG - f("mass_kg"))
        .s("rotor_structural_acceptance", &rq_status)
        .f("hub_ratio", hub)
        .f("blade_span_m", comp.turbo_radius_m * (1.0 - hub))
        .build();
    rec.insert("outputs", outputs);
    Ok(rec.build())
}

// ------------------------------------------------------------------------------------------------ Pareto
fn dominates(a: &Value, b: &Value, objectives: &[(&str, &str)]) -> bool {
    let mut better = false;
    for (k, sense) in objectives {
        let (x, y) = (as_f64(&a[*k]).unwrap_or(f64::NAN), as_f64(&b[*k]).unwrap_or(f64::NAN));
        let (x, y) = if *sense == "max" { (x, y) } else { (-x, -y) };
        if x < y {
            return false;
        }
        if x > y {
            better = true;
        }
    }
    better
}

fn truthy_obj(v: &Value) -> bool {
    match v {
        Value::Object(m) => !m.is_empty(),
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Array(a) => !a.is_empty(),
        _ => true,
    }
}

/// Ids of the non-dominated feasible records (weak dominance; ties kept; sorted by id).
pub fn pareto_front(records: &[Value], objectives: &[(&str, &str)]) -> Vec<String> {
    let mut feas: Vec<&Value> = records
        .iter()
        .filter(|r| {
            r.get("outputs").map(truthy_obj).unwrap_or(false)
                && objectives.iter().all(|(k, _)| matches!(r["outputs"].get(*k), Some(Value::Number(_))))
        })
        .collect();
    feas.sort_by(|a, b| a["id"].as_str().unwrap_or("").cmp(b["id"].as_str().unwrap_or("")));
    let mut out = vec![];
    for (i, a) in feas.iter().enumerate() {
        if !feas.iter().enumerate().any(|(j, b)| j != i && dominates(&b["outputs"], &a["outputs"], objectives)) {
            out.push(a["id"].as_str().unwrap_or("").to_string());
        }
    }
    out
}

pub fn is_dominated_by(outputs: &Value, front: &[Value], objectives: &[(&str, &str)]) -> bool {
    front.iter().any(|f| dominates(&f["outputs"], outputs, objectives))
}

/// Bounded design search for one inlet record. MODE_STRICT refuses (NOT_EVALUATED) while blockers remain.
pub fn synthesize(
    ctx: Ctx,
    inlet: &InletRecord,
    mode: &str,
    grid: Option<&SearchGrid>,
    ev: Option<&Map<String, Value>>,
) -> PyResult<Value> {
    if !MODES.contains(&mode) {
        return Err(sie("mode must be one of MODES"));
    }
    if mode == MODE_STRICT {
        let blk = strict_blockers(ctx, inlet, ev)?;
        if !blk.is_empty() {
            return Ok(Obj::new()
                .s("inlet", &inlet.record_id)
                .s("mode", mode)
                .s("status", not_evaluated_status(&blk))
                .set("blockers", Value::Array(blk))
                .set("designs", Value::Array(vec![]))
                .set("feasible_ids", Value::Array(vec![]))
                .set("pareto_ids", Value::Array(vec![]))
                .set("pareto_with_S_ids", Value::Array(vec![]))
                .set("domain", u13::classify_pressure_target(inlet.p_total_pa)?)
                .build());
        }
    } else if inlet.label != LABEL_PARAMETRIC && inlet.evidence_class == "assumed" {
        return Err(sie("an assumed inlet record must be labelled PARAMETRIC_SENSITIVITY"));
    }
    let default;
    let g = match grid {
        Some(g) => g,
        None => {
            default = SearchGrid::default_grid()?;
            &default
        }
    };
    g.validate(ctx)?;
    let mut recs = vec![];
    for d in g.designs()? {
        recs.push(evaluate_design(ctx, &d, inlet, mode, ev)?);
    }
    let feas: Vec<String> =
        recs.iter().filter(|r| truthy_obj(&r["outputs"])).map(|r| r["id"].as_str().unwrap_or("").to_string()).collect();
    let is_zero = |r: &&Value| {
        r["design"].get("hub_geometry_status").and_then(|v| v.as_str()).unwrap_or(HUB_ZERO_BOUND) == HUB_ZERO_BOUND
    };
    let hub: Vec<Value> = recs.iter().filter(|r| !is_zero(r)).cloned().collect();
    let bound: Vec<Value> = recs.iter().filter(|r| is_zero(r)).cloned().collect();
    let mut statuses: Vec<String> = recs.iter().map(|r| r["status"].as_str().unwrap_or("").to_string()).collect();
    statuses.sort();
    statuses.dedup();
    let mut counts = Map::new();
    for st in statuses {
        let n = recs.iter().filter(|r| r["status"] == st.as_str()).count();
        counts.insert(st, Value::from(n));
    }
    Ok(Obj::new()
        .s("inlet", &inlet.record_id)
        .s("mode", mode)
        .s("label", if mode == MODE_PARAMETRIC { LABEL_PARAMETRIC } else { LABEL_INTERFACE })
        .s("status", "EVALUATED")
        .set("designs", Value::Array(recs.clone()))
        .set("feasible_ids", slist(&feas))
        .set("pareto_ids", slist(pareto_front(&hub, &PRIMARY_OBJECTIVES)))
        .set("pareto_with_S_ids", slist(pareto_front(&hub, &SECONDARY_OBJECTIVES)))
        .set("zero_hub_bound_pareto_ids", slist(pareto_front(&bound, &PRIMARY_OBJECTIVES)))
        .set("status_counts", Value::Object(counts))
        .set("domain", u13::classify_pressure_target(inlet.p_total_pa)?)
        .set("transitional_model", u13::transitional_model())
        .build())
}

/// DragCompressor.size_for for the same inlet, passed through this module's gates and compared with a front.
pub fn size_for_comparison(
    ctx: Ctx,
    inlet: &InletRecord,
    cr_target: f64,
    a_turbo_m2: f64,
    front_records: &[Value],
    material: &str,
    mode: &str,
) -> PyResult<Value> {
    let r_t = r_turbo_from_area(a_turbo_m2, 0.0)?;
    let mut comp = DragCompressor {
        turbo_area_m2: a_turbo_m2,
        turbo_radius_m: r_t,
        rotor_material: material.into(),
        t_gas_k: inlet.t_k,
        ..Default::default()
    };
    let md = inlet.mdot_species_order();
    let base = Obj::new().f("a_turbo_m2", a_turbo_m2).s("material", material).f("cr_target", cr_target);
    let res = match comp.size_for(
        ctx,
        inlet.p_total_pa,
        &md,
        cr_target,
        90000.0,
        SIZE_FOR_MAX_TURBO_ROWS,
        SIZE_FOR_MAX_DRAG_STAGES,
    ) {
        Ok(r) => r,
        Err(e) if catchable(e.class) => {
            return Ok(base
                .set("size_for", Obj::new().s("exception", &e.py_text()).build())
                .s("gate_status", ST_REJECTED)
                .set("gate_reasons", slist([R_MODEL]))
                .b("on_front", false)
                .set("dominated_by_front", Value::Null)
                .build());
        }
        Err(e) => return Err(e),
    };
    let rpm = f64_of(&res, "rpm");
    let mut design = Map::new();
    design.insert("id".into(), Value::String("size_for".into()));
    design.insert("N_turbo".into(), Value::from(as_int(res.get("turbo_rows"))));
    design.insert("A_turbo_m2".into(), fnum(a_turbo_m2));
    design.insert("R_turbo_m".into(), fnum(r_t));
    design.insert("u_tip_turbo_mps".into(), fnum(r_t * rpm * 2.0 * PI / 60.0));
    design.insert("rpm".into(), fnum(rpm));
    design.insert("N_drag".into(), Value::from(as_int(res.get("n_stages"))));
    design.insert("rotor_material".into(), Value::String(material.into()));
    let ev = evaluate_design(ctx, &design, inlet, mode, None)?;
    let sized = res.get("sized") == Some(&Value::Bool(true));
    let mut out = base
        .set(
            "size_for",
            Obj::new()
                .b("sized", sized)
                .set("turbo_rows", as_int(res.get("turbo_rows")))
                .set("n_stages", as_int(res.get("n_stages")))
                .f("rpm", rpm)
                .f("p_out_Pa", f64_of(&res, "p_out_Pa"))
                .f("CR_active", f64_of(&res, "CR_active"))
                .f("P_el_W", f64_of(&res, "P_el_W"))
                .f("mass_kg", f64_of(&res, "mass_kg"))
                .b("rotor_ok_uncited_db_yield", res.get("rotor_ok") == Some(&Value::Bool(true)))
                .s("objective", "mass + 0.02 x P_el (size_for's hard-coded scalar)")
                .build(),
        )
        .set("gate_status", ev["status"].clone())
        .set("gate_reasons", ev["reasons"].clone());
    if truthy_obj(&ev["outputs"]) {
        let on = !is_dominated_by(&ev["outputs"], front_records, &PRIMARY_OBJECTIVES);
        out = out.b("on_front", on).b("dominated_by_front", !on);
    } else {
        out = out.b("on_front", false).set("dominated_by_front", Value::Null);
    }
    Ok(out.build())
}

/// The compressor slot of the A9-02 ledger (architecture_optimizer.official_ledger, compressor branch): the official
/// load is NOT_EVALUATED until the compressor ICD supplies it (row 22); a model-derived draw makes the ledger a
/// labelled PARAMETRIC_SENSITIVITY, never the official one.
pub fn compressor_ledger_slot(compressor_p_w: Option<f64>, compressor_source: &str) -> Value {
    match compressor_p_w {
        None => Obj::new()
            .set("P_W", Value::Null)
            .set("evidence_class", Value::Null)
            .set("source", Value::Null)
            .s("ledger_label", "OFFICIAL_A9_02_STATE")
            .s("status", EvalStatus::NotEvaluated.as_str())
            .build(),
        Some(p) => Obj::new()
            .f("P_W", p)
            .s("evidence_class", "model-derived")
            .s(
                "source",
                if compressor_source.is_empty() {
                    "F3/F4 DragCompressor cascade (code-default coefficients)"
                } else {
                    compressor_source
                },
            )
            .s("ledger_label", LABEL_PARAMETRIC)
            .s("status", EvalStatus::NotEvaluated.as_str())
            .build(),
    }
}
