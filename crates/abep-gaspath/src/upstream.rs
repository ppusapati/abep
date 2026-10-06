//! A9.13 S6 upstream-architecture rules (`abep_sim/design/upstream_a9_13.py` subset; contract
//! PARITY-C-ABEP_SIM_DESIGN_PLENUM_FEED_PY-V1): the 0.1 Pa free-molecular domain (S6.8 -> OUT_OF_DOMAIN), the
//! orbit-state-scheduled and fixed plenum setpoints on controller-available inputs only (S6.10), the provisional F4
//! transient framework (S6.12), the flow-gap order with NO_REQUIREMENT_RELAXATION (S6.13 / S6.21) and the robust Pareto
//! set that never yields a representative (S6.20 -> NOT_EVALUATED). Nothing here invents a number; no status is ever
//! PASS / SELECTED / WINNER / QUALIFIED.

use crate::error::{a913, GasPathError, PyClass, PyResult};
use crate::pyops::{self, py_repr};
use crate::rec::{fnum, slist, Obj};
use abep_types::EvalStatus;
use serde_json::{Map, Value};
use std::path::Path;

pub struct Decision {
    pub key: &'static str,
    pub md: &'static str,
    pub json: &'static str,
    pub json_sha256: &'static str,
    pub ids: &'static [&'static str],
}

pub const DECISIONS: [Decision; 5] = [
    Decision {
        key: "A9.9",
        md: "docs/decisions/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md",
        json: "docs/decisions/OD_2026_10_01_A9_9_s2_model_change_owner_decisions.json",
        json_sha256: "b6010d9d2856ab21b15d49e477ade8246b9d6e90d4dfa1cc07c4468c10a1e47b",
        ids: &["S2.3 / OQ-F3-01", "S2.5 MCC-03"],
    },
    Decision {
        key: "A9.13",
        md: "docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md",
        json: "docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json",
        json_sha256: "9afaca459efe27556033d836814f71bd03203711627899f3ffc494567d763b23",
        ids: &[
            "S6.3 / F2-OQ-01",
            "S6.4 / F2-OQ-02",
            "S6.5 / F2-OQ-03",
            "S6.6 / F2-OQ-04",
            "S6.7 / OQ-F3-02",
            "S6.8 / OQ-F3-03",
            "S6.9 / OQ-F3-04",
            "S6.10 / OQ-F4-01",
            "S6.11 / OQ-F4-02",
            "S6.12 / OQ-F4-03",
            "S6.15 / OQ-F78-01",
            "S6.16 / OQ-F78-02",
            "S6.17 / OQ-F78-03",
            "S6.18 / OQ-F78-04",
            "S6.19 / UPSTREAM_ICD-Q1",
            "S6.20 / F9-OQ-01",
            "S6.21 / F9-OQ-02",
            "S6.22 / F9-OQ-03",
        ],
    },
    Decision {
        key: "A9.14",
        md: "docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md",
        json: "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json",
        json_sha256: "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c",
        ids: &["S9.7 / OD2"],
    },
    Decision {
        key: "A9.15",
        md: "docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
        json: "docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
        json_sha256: "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
        ids: &["RFP-COMPLIANT PROPELLANT POLICY (governing_rule)"],
    },
    Decision {
        key: "A9.17",
        md: "docs/decisions/OD_2026_10_01_A9_17_DATA_ARTIFACT_OWNER_DECISIONS.md",
        json: "docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json",
        json_sha256: "9fd77c95c2f3142bb3e2faf68145e1225a29b307d22f86bf93a8cd562914c3ad",
        ids: &["RFP (registration of the official RFP as the requirement source)"],
    },
];

pub const RFP_CLAUSES: [(&str, &str); 10] = [
    ("chain", "RFP-P16-02"),
    ("density_increase", "RFP-P17-04"),
    ("n2_o_xe", "RFP-P17-05"),
    ("altitude", "RFP-P18-04"),
    ("intake_sizing", "RFP-P18-05"),
    ("thrust", "RFP-P18-06"),
    ("propellants", "RFP-P18-08"),
    ("power", "RFP-P18-10"),
    ("mass", "RFP-P18-11"),
    ("life", "RFP-P19-01"),
];

fn decision(key: &str) -> PyResult<&'static Decision> {
    DECISIONS.iter().find(|d| d.key == key).ok_or_else(|| crate::error::key_error(key))
}

/// Re-hash every cited decision JSON (immutable records): {decision: true/false}.
pub fn verify_decision_records(repo: &Path) -> Value {
    let mut m = Map::new();
    for d in &DECISIONS {
        let ok = abep_provenance::sha256_file(&repo.join(d.json)).map(|h| h == d.json_sha256).unwrap_or(false);
        m.insert(d.key.into(), Value::Bool(ok));
    }
    Value::Object(m)
}

/// Citation records (path + json sha256 + ids) for the given decision keys.
pub fn cite(keys: &[&str]) -> PyResult<Value> {
    let mut out = vec![];
    for k in keys {
        let d = decision(k)?;
        out.push(
            Obj::new()
                .s("decision", k)
                .s("md", d.md)
                .s("json", d.json)
                .s("json_sha256", d.json_sha256)
                .set("ids", slist(d.ids))
                .build(),
        );
    }
    Ok(Value::Array(out))
}

// ------------------------------------------------------------------------------------------------ vocabulary
pub const NOT_EVALUATED: &str = "NOT_EVALUATED";
pub const NOT_EVALUATED_OOD: &str = "NOT_EVALUATED_OUT_OF_DOMAIN";
pub const NOT_EVALUATED_MATERIAL_BASIS: &str = "NOT_EVALUATED_MATERIAL_BASIS";
pub const PARAMETRIC_SENSITIVITY: &str = "PARAMETRIC_SENSITIVITY";
pub const REFERENCE_PARAMETRIC: &str = "REFERENCE_PARAMETRIC_NOT_FLIGHT";
pub const SYNTHETIC: &str = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE";
pub const VALUE_EVIDENCE: &str = "EVIDENCE";
pub const VALUE_PARAMETRIC: &str = PARAMETRIC_SENSITIVITY;
pub const VALUE_REFERENCE: &str = REFERENCE_PARAMETRIC;
pub const VALUE_SYNTHETIC: &str = SYNTHETIC;
pub const VALUE_TBD: &str = "TBD";
pub const VALUE_STATUSES: [&str; 5] = [VALUE_EVIDENCE, VALUE_PARAMETRIC, VALUE_REFERENCE, VALUE_SYNTHETIC, VALUE_TBD];
pub const C_MET: &str = "MET_ON_SUPPLIED_VALUES";
pub const C_VIOLATED: &str = "VIOLATED";
pub const C_NOT_EVALUATED: &str = NOT_EVALUATED;
pub const C_MET_PARAMETRIC: &str = "MET_ON_PARAMETRIC_VALUES_SENSITIVITY_ONLY_NOT_MET";
pub const C_VIOLATED_PARAMETRIC: &str = "VIOLATED_ON_PARAMETRIC_VALUES_SENSITIVITY_ONLY";
pub const C_MET_SYNTHETIC: &str = "MET_ON_SYNTHETIC_TEST_DATA_NOT_EVIDENCE";
pub const C_VIOLATED_SYNTHETIC: &str = "VIOLATED_ON_SYNTHETIC_TEST_DATA_NOT_EVIDENCE";
pub const FORBIDDEN_STATUS_WORDS: [&str; 5] = ["PASS", "SELECTED", "WINNER", "QUALIFIED", "OPTIMUM"];

/// Domain status -> EvalStatus (INV-P-03: the SC-WP-02 gate 'feed state outside the registered pressure domain').
pub fn domain_eval_status(s: &str) -> EvalStatus {
    match s {
        DOMAIN_IN => EvalStatus::Evaluated,
        NOT_EVALUATED_OOD => EvalStatus::OutOfDomain,
        _ => EvalStatus::NotEvaluated,
    }
}

/// Weakest-link evidence status: TBD > SYNTHETIC > REFERENCE > PARAMETRIC > EVIDENCE.
pub fn combine_value_status(statuses: &[&str]) -> PyResult<&'static str> {
    let mut bad: Vec<&str> = statuses.iter().copied().filter(|s| !VALUE_STATUSES.contains(s)).collect();
    bad.sort();
    bad.dedup();
    if !bad.is_empty() {
        return Err(a913(format!("unknown value status(es) {bad:?}")));
    }
    for s in [VALUE_TBD, VALUE_SYNTHETIC, VALUE_REFERENCE, VALUE_PARAMETRIC] {
        if statuses.contains(&s) {
            return Ok(s);
        }
    }
    Ok(VALUE_EVIDENCE)
}

/// MET / VIOLATED only on determining evidence (S6.22).
pub fn constraint_status(ok: Option<bool>, value_status: &str) -> &'static str {
    match ok {
        None => C_NOT_EVALUATED,
        Some(_) if value_status == VALUE_TBD => C_NOT_EVALUATED,
        Some(o) if value_status == VALUE_EVIDENCE => {
            if o {
                C_MET
            } else {
                C_VIOLATED
            }
        }
        Some(o) if value_status == VALUE_SYNTHETIC => {
            if o {
                C_MET_SYNTHETIC
            } else {
                C_VIOLATED_SYNTHETIC
            }
        }
        Some(o) => {
            if o {
                C_MET_PARAMETRIC
            } else {
                C_VIOLATED_PARAMETRIC
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ S6.8 / S6.11
pub const P_FREE_MOLECULAR_LIMIT_PA: f64 = 0.1;
pub const DOMAIN_IN: &str = "IN_FREE_MOLECULAR_DOMAIN";
pub const DD_HIGHER_PRESSURE: &str = "DD-HP";
pub const DD_LOW_PRESSURE_FALLBACK: &str = "DD-LE0P1";

pub fn transitional_model() -> Value {
    Obj::new()
        .s("module", "abep_sim/compressor_transitional.py")
        .s("evidence_status", "CANDIDATE_NOT_ADMITTED")
        .b("consumed_as_evidence", false)
        .s(
            "rule",
            "A9.13 S6.8: no extrapolated > 0.1 Pa result is a valid architecture point until the transitional model \
has an admitted evidence basis and / or is validated against T-1 / T-2 hardware data",
        )
        .build()
}

pub fn design_directions() -> Value {
    Value::Array(vec![
        Obj::new()
            .s("id", DD_HIGHER_PRESSURE)
            .s(
                "name",
                "higher-pressure compression path (compressor / feed chain producing the H-1 pressure and mass-flow \
state)",
            )
            .s("role", "PRIMARY_DESIGN_DIRECTION")
            .s("evaluation_status", NOT_EVALUATED_OOD)
            .s(
                "basis",
                "A9.13 S6.11 (RFP-P17-04: the compressor / gas reservoir increase the collected density to a usable \
ionization level); evaluable only once the > 0.1 Pa domain is closed by admitted evidence (S6.8)",
            )
            .build(),
        Obj::new()
            .s("id", DD_LOW_PRESSURE_FALLBACK)
            .s("name", "<= 0.1 Pa high-conductance feed branch")
            .s("role", "SENSITIVITY_FALLBACK_STUDY_NOT_PRIMARY")
            .s("evaluation_status", PARAMETRIC_SENSITIVITY)
            .s(
                "basis",
                "A9.13 S6.11: continued as a sensitivity / fallback study; never frozen as the primary architecture \
merely because the current compressor model stops at 0.1 Pa",
            )
            .build(),
    ])
}

/// A pressure as the reference receives it: a number, or anything else (fail closed).
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Num {
    F(f64),
    Other,
}

/// IN_FREE_MOLECULAR_DOMAIN when every pressure touched is <= 0.1 Pa, else NOT_EVALUATED_OUT_OF_DOMAIN.
pub fn pressure_domain_status(p_max_pa: Num) -> &'static str {
    match p_max_pa {
        Num::F(p) if p.is_finite() && p >= 0.0 => {
            if p <= P_FREE_MOLECULAR_LIMIT_PA {
                DOMAIN_IN
            } else {
                NOT_EVALUATED_OOD
            }
        }
        _ => NOT_EVALUATED_OOD,
    }
}

/// Design direction and domain status of a plenum / compressor-outlet target pressure (S6.8 + S6.11).
pub fn classify_pressure_target(p_target_pa: f64) -> PyResult<Value> {
    if !p_target_pa.is_finite() || p_target_pa <= 0.0 {
        return Err(a913("target pressure must be finite and > 0"));
    }
    if p_target_pa <= P_FREE_MOLECULAR_LIMIT_PA {
        return Ok(Obj::new()
            .f("target_Pa", p_target_pa)
            .s("design_direction", DD_LOW_PRESSURE_FALLBACK)
            .s("role", "SENSITIVITY_FALLBACK_STUDY_NOT_PRIMARY")
            .s("domain_status", DOMAIN_IN)
            .s("label", PARAMETRIC_SENSITIVITY)
            .build());
    }
    Ok(Obj::new()
        .f("target_Pa", p_target_pa)
        .s("design_direction", DD_HIGHER_PRESSURE)
        .s("role", "PRIMARY_DESIGN_DIRECTION")
        .s("domain_status", NOT_EVALUATED_OOD)
        .s("label", NOT_EVALUATED_OOD)
        .s(
            "reason",
            "above the 0.1 Pa free-molecular domain; the transitional model is CANDIDATE_NOT_ADMITTED (A9.13 S6.8): \
no result is offered, none is extrapolated",
        )
        .s(
            "unlock",
            "admitted transitional-regime evidence (T-1 / T-2 compressor characterization or a pre-registered held-out \
published dataset; abep_sim/compressor_transitional.py admission plan)",
        )
        .build())
}

/// The object `refuse_candidate_evidence` inspects: a mapping, or an object with attributes.
#[derive(Debug, Clone, PartialEq)]
pub enum CandidateObj {
    Mapping { evidence_status: Option<String> },
    Object { evidence_status: Option<String>, valid_design_evidence: Option<bool> },
}

/// Refuse a result of the CANDIDATE_NOT_ADMITTED transitional model (S6.8).
pub fn refuse_candidate_evidence(obj: &CandidateObj) -> PyResult<()> {
    let (st, valid) = match obj {
        CandidateObj::Mapping { evidence_status } => (evidence_status.clone(), true),
        CandidateObj::Object { evidence_status, valid_design_evidence } => {
            (evidence_status.clone(), valid_design_evidence.unwrap_or(true))
        }
    };
    if st.as_deref() == Some("CANDIDATE_NOT_ADMITTED") || !valid {
        return Err(a913(
            "transitional-regime candidate results are CANDIDATE_NOT_ADMITTED and are never consumed as design \
evidence (A9.13 S6.8)",
        ));
    }
    Ok(())
}

// ------------------------------------------------------------------------------------------------ S6.10 setpoints
pub const CONTROL_MODE_SCHEDULED: &str = "ORBIT_STATE_SCHEDULED_SETPOINT";
pub const CONTROL_MODE_FIXED: &str = "FIXED_SETPOINT";
pub const SCHEDULE_STATUS: &str = "NOT_FROZEN";
pub const INPUT_KINDS: [&str; 4] =
    ["onboard_measurement", "onboard_estimate", "onboard_navigation_or_clock", "uplinked_command"];
pub const ORACLE_KEYS: [&str; 21] = [
    "rho_kg_m3",
    "n_O_m3",
    "n_N2_m3",
    "n_O2_m3",
    "n_He_m3",
    "n_Ar_m3",
    "n_N_m3",
    "x_O",
    "x_N2",
    "x_O2",
    "T_K",
    "f107",
    "f107a",
    "ap",
    "scenario",
    "mdot_fwd_kgps",
    "p_passive_Pa",
    "K_back",
    "flux_corot_kg_m2_s",
    "surface_scenario",
    "f1_status",
];

pub fn control_mode_role(mode: &str) -> &'static str {
    if mode == CONTROL_MODE_SCHEDULED {
        "BASELINE_CONTROL_MODE"
    } else {
        "FALLBACK_DEGRADED_MODE_AND_COMPARISON_REFERENCE"
    }
}

/// Ordered controller state (name -> value); values may be non-numbers.
pub type ControllerState = Vec<(String, Value)>;

fn oracle_check(cs: &ControllerState) -> PyResult<()> {
    let mut bad: Vec<&str> = cs.iter().map(|(k, _)| k.as_str()).filter(|k| ORACLE_KEYS.contains(k)).collect();
    bad.sort();
    bad.dedup();
    if !bad.is_empty() {
        return Err(a913(format!("controller state carries environment-truth keys {bad:?} (A9.13 S6.10)")));
    }
    Ok(())
}

/// One controller-available input (S6.10): its name, kind and source.
#[derive(Debug, Clone, PartialEq)]
pub struct ScheduleInput {
    pub name: String,
    pub kind: String,
    pub source: String,
}

impl ScheduleInput {
    pub fn new(name: &str, kind: &str, source: &str) -> PyResult<Self> {
        if !INPUT_KINDS.contains(&kind) {
            return Err(a913(format!("schedule input kind {kind:?} not in INPUT_KINDS")));
        }
        if name.trim().is_empty() || source.trim().is_empty() {
            return Err(a913("schedule input needs a name and a source"));
        }
        if ORACLE_KEYS.contains(&name) {
            return Err(a913(format!("{name:?} is an environment-model truth quantity, not controller-available")));
        }
        if name.starts_with("est:") && kind != "onboard_estimate" {
            return Err(a913("an 'est:' input must be of kind onboard_estimate"));
        }
        Ok(ScheduleInput { name: name.into(), kind: kind.into(), source: source.into() })
    }
}

/// A numeric value of the controller state as `_finite` sees it.
fn finite_num(v: &Value) -> Option<f64> {
    match v {
        Value::Number(n) => n.as_f64().filter(|x| x.is_finite()),
        _ => None,
    }
}

/// Orbit-state-scheduled plenum setpoint (BASELINE control mode): piecewise-linear in ONE controller-available input;
/// never frozen; no extrapolation.
#[derive(Debug, Clone, PartialEq)]
pub struct SetpointSchedule {
    pub schedule_id: String,
    pub input: ScheduleInput,
    pub breakpoints: Vec<(f64, f64)>,
    pub label: String,
    pub basis: String,
    pub status: String,
}

impl SetpointSchedule {
    pub fn new(
        schedule_id: &str,
        input: ScheduleInput,
        breakpoints: Vec<(f64, f64)>,
        label: &str,
        basis: &str,
        status: &str,
    ) -> PyResult<Self> {
        if status != SCHEDULE_STATUS {
            return Err(a913(
                "the setpoint schedule is never frozen before the compressor / feed / H-1 validated domains exist \
(A9.13 S6.10)",
            ));
        }
        if !label.contains(PARAMETRIC_SENSITIVITY) && !label.contains(SYNTHETIC) {
            return Err(a913(
                "a schedule is a PARAMETRIC_SENSITIVITY (or synthetic test) object until the validated \
domains exist; its label must say so",
            ));
        }
        if basis.trim().is_empty() {
            return Err(a913("schedule basis must be stated"));
        }
        if breakpoints.is_empty() {
            return Err(a913("schedule needs at least one breakpoint"));
        }
        if breakpoints.iter().any(|(x, p)| !(x.is_finite() && p.is_finite() && *p > 0.0)) {
            return Err(a913("breakpoints must be finite with setpoint > 0"));
        }
        let xs: Vec<f64> = breakpoints.iter().map(|b| b.0).collect();
        if xs.windows(2).any(|w| w[1] <= w[0]) {
            return Err(a913("breakpoint inputs must be strictly increasing"));
        }
        Ok(SetpointSchedule {
            schedule_id: schedule_id.into(),
            input,
            breakpoints,
            label: label.into(),
            basis: basis.into(),
            status: status.into(),
        })
    }

    pub fn mode(&self) -> &'static str {
        CONTROL_MODE_SCHEDULED
    }

    /// Setpoint for one controller state (ONLY controller-available inputs).
    pub fn setpoint(&self, cs: &ControllerState) -> PyResult<Value> {
        oracle_check(cs)?;
        let not_eval = |status: &str, reason: String| {
            Obj::new()
                .s("status", status)
                .set("setpoint_Pa", Value::Null)
                .s("mode", self.mode())
                .s("reason", &reason)
                .build()
        };
        let Some((_, xv)) = cs.iter().find(|(k, _)| *k == self.input.name) else {
            return Ok(not_eval(
                NOT_EVALUATED,
                format!("controller input {} missing", crate::rotor_strength::py_str_repr(&self.input.name)),
            ));
        };
        let Some(x) = finite_num(xv) else {
            return Ok(not_eval(NOT_EVALUATED, "input not finite".into()));
        };
        let bp = &self.breakpoints;
        let p = if bp.len() == 1 {
            if x != bp[0].0 {
                return Ok(not_eval(
                    NOT_EVALUATED_OOD,
                    "input outside the single tabulated point (no extrapolation)".into(),
                ));
            }
            bp[0].1
        } else {
            if !(bp[0].0 <= x && x <= bp[bp.len() - 1].0) {
                return Ok(not_eval(
                    NOT_EVALUATED_OOD,
                    format!(
                        "input {} outside the schedule range [{}, {}] (no extrapolation)",
                        py_repr(x),
                        py_repr(bp[0].0),
                        py_repr(bp[bp.len() - 1].0)
                    ),
                ));
            }
            let mut p = f64::NAN;
            for w in bp.windows(2) {
                let ((x0, p0), (x1, p1)) = (w[0], w[1]);
                if x0 <= x && x <= x1 {
                    p = p0 + (p1 - p0) * (x - x0) / (x1 - x0);
                    break;
                }
            }
            p
        };
        Ok(Obj::new()
            .s("status", "EVALUATED_SCHEDULE")
            .f("setpoint_Pa", p)
            .s("mode", self.mode())
            .s("label", &self.label)
            .s("schedule_status", &self.status)
            .set("domain", classify_pressure_target(p)?)
            .build())
    }

    pub fn to_dict(&self) -> Value {
        Obj::new()
            .s("schedule_id", &self.schedule_id)
            .s("mode", self.mode())
            .s("role", control_mode_role(self.mode()))
            .set(
                "input",
                Obj::new()
                    .s("name", &self.input.name)
                    .s("kind", &self.input.kind)
                    .s("source", &self.input.source)
                    .build(),
            )
            .set(
                "breakpoints",
                Value::Array(self.breakpoints.iter().map(|(x, p)| Value::Array(vec![fnum(*x), fnum(*p)])).collect()),
            )
            .s("label", &self.label)
            .s("basis", &self.basis)
            .s("status", &self.status)
            .build()
    }
}

/// Fixed plenum setpoint: fallback / degraded mode and the comparison reference (S6.10).
#[derive(Debug, Clone, PartialEq)]
pub struct FixedSetpoint {
    pub setpoint_pa: f64,
    pub label: String,
    pub basis: String,
}

impl FixedSetpoint {
    pub fn new(setpoint_pa: f64, label: &str, basis: &str) -> PyResult<Self> {
        if !(setpoint_pa.is_finite() && setpoint_pa > 0.0) {
            return Err(a913("fixed setpoint must be finite and > 0"));
        }
        if basis.trim().is_empty() {
            return Err(a913("fixed setpoint basis must be stated"));
        }
        Ok(FixedSetpoint { setpoint_pa, label: label.into(), basis: basis.into() })
    }

    pub fn mode(&self) -> &'static str {
        CONTROL_MODE_FIXED
    }

    pub fn setpoint(&self, cs: &ControllerState) -> PyResult<Value> {
        oracle_check(cs)?;
        Ok(Obj::new()
            .s("status", "EVALUATED_FIXED")
            .f("setpoint_Pa", self.setpoint_pa)
            .s("mode", self.mode())
            .s("label", &self.label)
            .set("domain", classify_pressure_target(self.setpoint_pa)?)
            .build())
    }

    pub fn to_dict(&self) -> Value {
        Obj::new()
            .s("mode", self.mode())
            .s("role", control_mode_role(self.mode()))
            .f("setpoint_Pa", self.setpoint_pa)
            .s("label", &self.label)
            .s("basis", &self.basis)
            .build()
    }
}

/// Either control mode.
#[derive(Debug, Clone, PartialEq)]
pub enum Control {
    Schedule(SetpointSchedule),
    Fixed(FixedSetpoint),
}

impl Control {
    pub fn mode(&self) -> &'static str {
        match self {
            Control::Schedule(s) => s.mode(),
            Control::Fixed(f) => f.mode(),
        }
    }
    pub fn setpoint(&self, cs: &ControllerState) -> PyResult<Value> {
        match self {
            Control::Schedule(s) => s.setpoint(cs),
            Control::Fixed(f) => f.setpoint(cs),
        }
    }
    pub fn to_dict(&self) -> Value {
        match self {
            Control::Schedule(s) => s.to_dict(),
            Control::Fixed(f) => f.to_dict(),
        }
    }
}

/// Project a simulator state onto the declared controller inputs (a truth key may feed only an 'est:' input).
pub fn controller_view(
    full_state: &[(String, Value)],
    inputs: &[ScheduleInput],
    mapping: &[(String, String)],
) -> PyResult<ControllerState> {
    let mut out = vec![];
    for inp in inputs {
        let Some((_, key)) = mapping.iter().find(|(k, _)| *k == inp.name) else {
            return Err(a913(format!("no source key mapped for controller input {:?}", inp.name)));
        };
        if ORACLE_KEYS.contains(&key.as_str()) && !inp.name.starts_with("est:") {
            return Err(a913(format!("{:?} would read environment truth {key:?} directly (A9.13 S6.10)", inp.name)));
        }
        let Some((_, v)) = full_state.iter().find(|(k, _)| k == key) else {
            return Err(a913(format!("state has no {key:?} for controller input {:?}", inp.name)));
        };
        out.push((inp.name.clone(), v.clone()));
    }
    Ok(out)
}

// ------------------------------------------------------------------------------------------------ S6.12
pub fn f4_transient_framework() -> Value {
    Obj::new()
        .s("status", "PROVISIONAL_PRE_LOCK2_ENGINEERING_CHARACTERIZATION")
        .f("settling_band_frac", 0.02)
        .f("observation_window_s", 60.0)
        .set(
            "events",
            slist([
                "E0_hold",
                "E1_setpoint_up",
                "E2_setpoint_down",
                "E3_feed_path_step",
                "E4_feed_path_restore",
                "E5_supply_down",
                "E6_supply_up",
                "E7_supply_restore",
            ]),
        )
        .set("outputs", slist(["settling_time_s", "peak_deviation_frac", "valve_travel", "ripple_transfer"]))
        .b("orbit_modulation_cases", true)
        .s(
            "rule",
            "A9.13 S6.12: retained for engineering development; not final H-1 tolerances. At LOCK-2 the measured H-1 \
feed sensitivity determines the allowable pressure / flow / composition bands; if it is tighter than the provisional F4 \
metric the H-1 limit governs (never relaxed to the F4 2 % band)",
        )
        .s("source", "abep_sim/design/plenum_feed.py SETTLE_BAND, WINDOW_S, event_sequence")
        .build()
}

/// Allowable H-1 feed disturbance band for one quantity (fraction of nominal); EVIDENCE only when measured.
#[derive(Debug, Clone, PartialEq)]
pub struct H1Tolerance {
    pub quantity: String,
    pub value_frac: Option<f64>,
    pub status: String,
    pub source: String,
}

impl H1Tolerance {
    pub fn new(quantity: &str, value_frac: Option<f64>, status: &str, source: &str) -> PyResult<Self> {
        if !["pressure", "mass_flow", "composition", "ripple"].contains(&quantity) {
            return Err(a913(format!("unknown H-1 tolerance quantity {quantity:?}")));
        }
        if !VALUE_STATUSES.contains(&status) {
            return Err(a913(format!("status {status:?} not in VALUE_STATUSES")));
        }
        if status == VALUE_TBD {
            if value_frac.is_some() {
                return Err(a913("a TBD tolerance carries no value"));
            }
        } else if !matches!(value_frac, Some(v) if v.is_finite() && v > 0.0) {
            return Err(a913("tolerance must be finite and > 0"));
        }
        if source.trim().is_empty() {
            return Err(a913("tolerance needs a source"));
        }
        Ok(H1Tolerance { quantity: quantity.into(), value_frac, status: status.into(), source: source.into() })
    }

    pub fn tbd(quantity: &str) -> PyResult<Self> {
        Self::new(quantity, None, VALUE_TBD, "H-1 measured feed sensitivity (LOCK-2; F5 IFD-F4-01..05): TBD")
    }
}

/// Which band governs (S6.12): acceptance is the measured H-1 tolerance (NOT_EVALUATED while TBD).
pub fn governing_band(quantity: &str, f4_provisional_frac: f64, h1: Option<&H1Tolerance>) -> PyResult<Value> {
    if !(f4_provisional_frac.is_finite() && f4_provisional_frac > 0.0) {
        return Err(a913("F4 provisional band must be finite and > 0"));
    }
    match h1 {
        Some(h) if h.status != VALUE_TBD => {
            let hv = h.value_frac.expect("validated");
            let tighter = hv < f4_provisional_frac;
            Ok(Obj::new()
                .s("quantity", quantity)
                .f("acceptance_limit_frac", hv)
                .s("acceptance_status", &h.status)
                .f("engineering_target_frac", pyops::py_min(hv, f4_provisional_frac))
                .s(
                    "governing",
                    if tighter {
                        "H1_MEASURED_TOLERANCE"
                    } else {
                        "H1_MEASURED_TOLERANCE (F4 band tighter: kept as engineering target only)"
                    },
                )
                .s("h1_source", &h.source)
                .build())
        }
        _ => Ok(Obj::new()
            .s("quantity", quantity)
            .set("acceptance_limit_frac", Value::Null)
            .s("acceptance_status", NOT_EVALUATED)
            .f("engineering_target_frac", f4_provisional_frac)
            .s("governing", "F4_PROVISIONAL_ENGINEERING_ONLY")
            .s("reason", "measured H-1 tolerance TBD (LOCK-2)")
            .build()),
    }
}

// ------------------------------------------------------------------------------------------------ S6.21 / S6.13
pub const CHARACTERIZATION_COVERAGE_MGPS: (f64, f64) = (0.38, 3.2);
pub const FEED_STATE_FIELDS: [&str; 5] = ["mdot_kgps", "P_Pa", "T_K", "x_mole", "ripple_frac"];
pub const H1_MAP_VALIDATED: &str = "VALIDATED";
pub const FLOW_GAP_AUTHORITY: &str = "A9.13 S6.13 / OQ-F4-04 (NO_REQUIREMENT_RELAXATION)";
pub const GROUND_CHARACTERIZATION_ONLY_MGPS: f64 = 0.38;
pub const DENSE_STATE_ONLY_ROLE: &str = "SENSITIVITY_ONLY_NOT_BASELINE";
pub const FULL_STATE_SET: &str = "FULL_REQUIRED_STATE_SET";
pub const STATE_SUBSET: &str = "STATE_SUBSET_SENSITIVITY_ONLY";
pub const FORBIDDEN_FEED_REQUIREMENT_BASES: [&str; 6] = [
    "GROUND_CHARACTERIZATION",
    "CHARACTERIZATION_COVERAGE",
    "DELIVERABLE_FRONTIER",
    "DENSE_STATE_ONLY",
    "STATE_SUBSET",
    "FIXED_MASS_FLOW_GATE",
];
pub const PERFORMANCE_DERIVED_BASIS: &str = "PERFORMANCE_DERIVED_VALIDATED_H1_MAP";
const A913_JSON: &str = "docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json";
const A913_SHA: &str = "9afaca459efe27556033d836814f71bd03203711627899f3ffc494567d763b23";
const RANK1_NEEDS: &str = "measured / validated H-1 thrust-versus-feed map (none exists)";

/// Where a delivered flow sits relative to the 0.38-3.2 mg/s ground-characterization range (coverage only).
pub fn characterization_coverage(mdot_kgps: Num) -> Value {
    let m = match mdot_kgps {
        Num::F(x) if x.is_finite() => x * 1e6,
        _ => {
            return Obj::new()
                .s("role", "CHARACTERIZATION_COVERAGE_NOT_A_REQUIREMENT")
                .set("mdot_mgps", Value::Null)
                .s("position", NOT_EVALUATED)
                .build()
        }
    };
    let (lo, hi) = CHARACTERIZATION_COVERAGE_MGPS;
    let pos = if m < lo {
        "BELOW_COVERAGE"
    } else if m > hi {
        "ABOVE_COVERAGE"
    } else {
        "WITHIN_COVERAGE"
    };
    Obj::new()
        .s("role", "CHARACTERIZATION_COVERAGE_NOT_A_REQUIREMENT")
        .f("mdot_mgps", m)
        .s("position", pos)
        .set("coverage_mgps", Value::Array(vec![fnum(lo), fnum(hi)]))
        .build()
}

/// S6.21: a fixed mg/s flight gate is never applied.
pub fn refuse_fixed_mass_flow_gate(gate_supplied: bool) -> PyResult<()> {
    if gate_supplied {
        return Err(a913(
            "A9.13 S6.21: no fixed mass-flow flight gate; AG-12 is a feed-state sufficiency gate derived from the \
required thrust and a validated H-1 thrust-versus-feed map",
        ));
    }
    Ok(())
}

pub fn flow_gap_order() -> Value {
    Value::Array(vec![
        Obj::new()
            .set("rank", 1)
            .s("lever", "PERFORMANCE_DERIVED_H1_FEED_REQUIREMENT")
            .s("authority", "A9.13 S6.21 / F9-OQ-02")
            .s(
                "what",
                "derive the minimum feed state from the required drag-compensation thrust at every required state \
through the measured / validated H-1 thrust-versus-feed map (AG-12)",
            )
            .s("status", "PENDING_EVIDENCE")
            .s("needs", RANK1_NEEDS)
            .build(),
        Obj::new()
            .set("rank", 2)
            .s("lever", "CAPTURE_COLLECTION")
            .s("authority", "A9.13 S6.13")
            .s("what", "raise capture / collection within the drag (S6.15 statewise), mass and pointing constraints")
            .s("status", "OPEN")
            .build(),
        Obj::new()
            .set("rank", 3)
            .s("lever", "COMPRESSOR_DOMAIN_PUMPING_FEED_EFFICIENCY")
            .s("authority", "A9.13 S6.13")
            .s("what", "compressor domain, pumping and feed efficiency")
            .s("status", "OPEN")
            .build(),
        Obj::new()
            .set("rank", 4)
            .s("lever", "SCHEDULED_SETPOINT")
            .s("authority", "A9.13 S6.10 / OQ-F4-01")
            .s("what", "orbit-state-scheduled plenum setpoint (baseline control mode, not frozen)")
            .s("status", "OPEN")
            .build(),
    ])
}

/// The flight feed requirement: performance-derived only; PENDING_EVIDENCE until a VALIDATED H-1 map exists.
pub fn flight_feed_requirement(h1_map_status: Option<&str>) -> Value {
    if h1_map_status != Some(H1_MAP_VALIDATED) {
        return Obj::new()
            .s("status", "PENDING_EVIDENCE")
            .set("value", Value::Null)
            .s("basis", PERFORMANCE_DERIVED_BASIS)
            .s("needs", RANK1_NEEDS)
            .set("authority", slist([FLOW_GAP_AUTHORITY, "A9.13 S6.21 / F9-OQ-02"]))
            .build();
    }
    Obj::new()
        .s("status", "DERIVE_PER_STATE_FROM_VALIDATED_MAP")
        .set("value", Value::Null)
        .s("basis", PERFORMANCE_DERIVED_BASIS)
        .s("rule", "per required state via feed_state_sufficiency (AG-12); never a single number")
        .build()
}

/// flight_feed_requirement status -> EvalStatus (PENDING_EVIDENCE is NOT_EVALUATED).
pub fn feed_requirement_eval_status(status: &str) -> EvalStatus {
    if status == "PENDING_EVIDENCE" {
        EvalStatus::NotEvaluated
    } else {
        EvalStatus::Evaluated
    }
}

/// The owner-ordered handling of the upstream flow gap (S6.13).
pub fn flow_gap_record() -> Value {
    Obj::new()
        .s("authority", FLOW_GAP_AUTHORITY)
        .set(
            "decision_record",
            Obj::new().s("json", A913_JSON).s("json_sha256", A913_SHA).s("id", "S6.13 / OQ-F4-04").build(),
        )
        .set("order", flow_gap_order())
        .s(
            "rule",
            "no requirement relaxation: the flight feed requirement is performance-derived (rank 1, S6.21) and is \
PENDING_EVIDENCE until a measured / validated H-1 thrust-versus-feed map exists; it is never lowered to a deliverable \
frontier, a state subset or a characterization value",
        )
        .f("ground_characterization_mgps", GROUND_CHARACTERIZATION_ONLY_MGPS)
        .s("ground_characterization_role", "GROUND_CHARACTERIZATION_ONLY_NEVER_A_FLIGHT_REQUIREMENT")
        .set(
            "dense_state_only_operation",
            Obj::new()
                .s("role", DENSE_STATE_ONLY_ROLE)
                .s(
                    "rule",
                    "operation restricted to higher-density states is a sensitivity; it cannot be baseline while it \
violates S6.15 (T - D >= 0 at EVERY required state); S6.15 is NOT_EVALUATED today, so it is never baseline-admissible",
                )
                .build(),
        )
        .set("flight_feed_requirement", flight_feed_requirement(None))
        .build()
}

/// S6.13 fail-closed guard: a flight feed requirement only from the performance-derived basis.
pub fn refuse_feed_requirement_lowering(basis: &str, value_mgps: Option<Num>) -> PyResult<()> {
    if basis == PERFORMANCE_DERIVED_BASIS {
        return Ok(());
    }
    let close =
        matches!(value_mgps, Some(Num::F(v)) if v.is_finite() && pyops::isclose(v, GROUND_CHARACTERIZATION_ONLY_MGPS));
    if FORBIDDEN_FEED_REQUIREMENT_BASES.contains(&basis) || close {
        return Err(a913(format!("{FLOW_GAP_AUTHORITY}: a flight feed requirement is never set from {basis:?}")));
    }
    Err(a913(format!(
        "{FLOW_GAP_AUTHORITY}: unknown feed-requirement basis {basis:?} (only {PERFORMANCE_DERIVED_BASIS})"
    )))
}

fn dedup_keep_order(xs: &[String]) -> Vec<String> {
    let mut out: Vec<String> = vec![];
    for x in xs {
        if !out.contains(x) {
            out.push(x.clone());
        }
    }
    out
}

/// S6.13 / S6.15: a result over a subset of the required states is a sensitivity, never baseline.
pub fn state_coverage(used_state_ids: &[String], required_state_ids: &[String]) -> PyResult<Map<String, Value>> {
    let used = dedup_keep_order(used_state_ids);
    let req = dedup_keep_order(required_state_ids);
    if req.is_empty() {
        return Err(a913("the required state set is empty"));
    }
    let missing: Vec<&String> = req.iter().filter(|s| !used.contains(s)).collect();
    let mut m = Map::new();
    if missing.is_empty() {
        m.insert("coverage".into(), Value::String(FULL_STATE_SET.into()));
        m.insert("baseline_admissible_by_coverage".into(), Value::Bool(true));
        m.insert("n_required".into(), Value::from(req.len()));
        m.insert("n_used_required".into(), Value::from(req.len()));
        m.insert("missing".into(), Value::Array(vec![]));
        return Ok(m);
    }
    m.insert("coverage".into(), Value::String(STATE_SUBSET.into()));
    m.insert("role".into(), Value::String(DENSE_STATE_ONLY_ROLE.into()));
    m.insert("baseline_admissible_by_coverage".into(), Value::Bool(false));
    m.insert("n_required".into(), Value::from(req.len()));
    m.insert("n_used_required".into(), Value::from(req.len() - missing.len()));
    m.insert("missing_count".into(), Value::from(missing.len()));
    m.insert(
        "rule".into(),
        Value::String(format!(
            "{FLOW_GAP_AUTHORITY}: operation on a state subset is a sensitivity; it cannot be baseline while S6.15 \
statewise drag compensation is violated or NOT_EVALUATED at any required state"
        )),
    );
    Ok(m)
}

/// Classify an operation restricted to a state subset (S6.13).
pub fn dense_state_only_operation(
    used_state_ids: &[String],
    required_state_ids: &[String],
    s615_status: Option<&str>,
) -> PyResult<Value> {
    let mut cov = state_coverage(used_state_ids, required_state_ids)?;
    let s615 = s615_status.unwrap_or(C_NOT_EVALUATED).to_string();
    let role = if cov["coverage"] != FULL_STATE_SET {
        DENSE_STATE_ONLY_ROLE
    } else if s615 == C_MET {
        "BASELINE_ELIGIBLE"
    } else {
        "BASELINE_BLOCKED_S6_15_NOT_MET"
    };
    cov.insert("s6_15_status".into(), Value::String(s615));
    cov.insert("role".into(), Value::String(role.into()));
    cov.insert("authority".into(), Value::String(FLOW_GAP_AUTHORITY.into()));
    Ok(Value::Object(cov))
}

// ------------------------------------------------------------------------------------------------ S6.20
pub const REGENERATION_TRIGGERS: [&str; 6] = [
    "S2 production-model corrections (A9.9)",
    "intake-surface v2",
    "filter implementation / evidence (S6.19)",
    "compressor search expanded beyond the inherited F3-front subset (hub ratio / blade span, S6.7)",
    "T-1 / T-2 compressor data",
    "DI-1.3 surface-accommodation evidence",
];

/// Versioned robust Pareto set carried to LOCK-1 (S6.20). Never reduced to a representative here.
#[derive(Debug, Clone, PartialEq)]
pub struct RobustParetoSet {
    pub set_id: String,
    pub version: String,
    pub members: Vec<String>,
    pub objectives: Vec<String>,
    pub label: String,
    pub provenance: String,
    pub regeneration_triggers: Vec<String>,
    pub regenerated_after: Vec<String>,
}

impl RobustParetoSet {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        set_id: &str,
        version: &str,
        members: Vec<String>,
        objectives: Vec<String>,
        label: &str,
        provenance: &str,
        regeneration_triggers: Option<Vec<String>>,
        regenerated_after: Vec<String>,
    ) -> PyResult<Self> {
        if set_id.trim().is_empty() || version.trim().is_empty() || provenance.trim().is_empty() {
            return Err(a913("set_id, version and provenance are required"));
        }
        if dedup_keep_order(&members).len() != members.len() {
            return Err(a913("duplicate member ids"));
        }
        if FORBIDDEN_STATUS_WORDS.iter().any(|w| label.contains(w)) {
            return Err(a913("the set label may not carry a selection word"));
        }
        Ok(RobustParetoSet {
            set_id: set_id.into(),
            version: version.into(),
            members,
            objectives,
            label: label.into(),
            provenance: provenance.into(),
            regeneration_triggers: regeneration_triggers
                .unwrap_or_else(|| REGENERATION_TRIGGERS.iter().map(|s| s.to_string()).collect()),
            regenerated_after,
        })
    }

    /// S6.20: no single upstream representative is selected before LOCK-1 (RepresentativeSelectionRefused ->
    /// NOT_EVALUATED).
    pub fn representative(&self) -> PyResult<Value> {
        Err(GasPathError::new(
            PyClass::RepresentativeSelectionRefused,
            "A9.13 S6.20: carry the versioned robust Pareto set; no representative is selected until the regeneration \
triggers close and a selection rule is proposed",
        ))
    }

    pub fn engineering_reference(&self, member_id: &str, purpose: &str) -> PyResult<Value> {
        if !self.members.iter().any(|m| m == member_id) {
            return Err(a913(format!("{member_id:?} is not a member of {} v{}", self.set_id, self.version)));
        }
        if purpose.trim().is_empty() {
            return Err(a913("state the downstream purpose"));
        }
        Ok(Obj::new()
            .s("member_id", member_id)
            .s("set_id", &self.set_id)
            .s("version", &self.version)
            .s("label", "ENGINEERING_REFERENCE_NOT_THE_FROZEN_ARCHITECTURE")
            .s("purpose", purpose)
            .s(
                "rule",
                "A9.13 S6.20: downstream studies evaluate all members or label a member an engineering reference",
            )
            .build())
    }

    pub fn pending_triggers(&self) -> Vec<String> {
        self.regeneration_triggers.iter().filter(|t| !self.regenerated_after.contains(t)).cloned().collect()
    }

    pub fn to_dict(&self) -> PyResult<Value> {
        Ok(Obj::new()
            .s("set_id", &self.set_id)
            .s("version", &self.version)
            .set("members", slist(&self.members))
            .set("n_members", self.members.len())
            .set("objectives", slist(&self.objectives))
            .s("label", &self.label)
            .s("provenance", &self.provenance)
            .s("representative", "NONE (S6.20)")
            .set("regeneration_triggers", slist(&self.regeneration_triggers))
            .set("pending_regeneration_triggers", slist(self.pending_triggers()))
            .set("authority", cite(&["A9.13"])?)
            .build())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn domain_gate_is_fail_closed_out_of_domain() {
        assert_eq!(pressure_domain_status(Num::F(0.1)), DOMAIN_IN);
        assert_eq!(pressure_domain_status(Num::F(0.1000001)), NOT_EVALUATED_OOD);
        assert_eq!(pressure_domain_status(Num::F(f64::NAN)), NOT_EVALUATED_OOD);
        assert_eq!(pressure_domain_status(Num::Other), NOT_EVALUATED_OOD);
        assert_eq!(domain_eval_status(NOT_EVALUATED_OOD), EvalStatus::OutOfDomain);
        assert_eq!(classify_pressure_target(0.0).unwrap_err().class, PyClass::A913RuleError);
    }

    #[test]
    fn robust_set_never_yields_a_representative() {
        let s = RobustParetoSet::new("S", "1", vec!["a".into()], vec![], "set", "prov", None, vec![]).unwrap();
        let e = s.representative().unwrap_err();
        assert_eq!(e.class, PyClass::RepresentativeSelectionRefused);
        assert_eq!(e.status(), EvalStatus::NotEvaluated);
        assert_eq!(s.pending_triggers().len(), 6);
    }

    #[test]
    fn feed_requirement_is_never_lowered() {
        assert!(refuse_feed_requirement_lowering(PERFORMANCE_DERIVED_BASIS, None).is_ok());
        for b in FORBIDDEN_FEED_REQUIREMENT_BASES {
            assert!(refuse_feed_requirement_lowering(b, None).is_err());
        }
        assert!(refuse_feed_requirement_lowering("OTHER", Some(Num::F(0.38))).is_err());
        let r = flight_feed_requirement(Some("SYNTHETIC"));
        assert_eq!(r["status"], "PENDING_EVIDENCE");
        assert_eq!(feed_requirement_eval_status("PENDING_EVIDENCE"), EvalStatus::NotEvaluated);
    }

    #[test]
    fn schedule_interpolates_and_refuses_oracle_keys() {
        let inp = ScheduleInput::new("nav:alt_km", "onboard_navigation_or_clock", "nav").unwrap();
        let s = SetpointSchedule::new(
            "S",
            inp,
            vec![(180.0, 0.02), (230.0, 0.01)],
            "PARAMETRIC_SENSITIVITY x",
            "b",
            SCHEDULE_STATUS,
        )
        .unwrap();
        let r = s.setpoint(&vec![("nav:alt_km".into(), Value::from(205.0))]).unwrap();
        assert_eq!(r["setpoint_Pa"].as_f64(), Some(0.015));
        let e = s.setpoint(&vec![("rho_kg_m3".into(), Value::from(1.0))]).unwrap_err();
        assert_eq!(e.class, PyClass::A913RuleError);
        let o = s.setpoint(&vec![("nav:alt_km".into(), Value::from(240.0))]).unwrap();
        assert_eq!(o["status"], NOT_EVALUATED_OOD);
    }
}
