//! System-objective records of the F7 optimizer used by the drag balance: `abep_sim/design/architecture_optimizer.py`
//! _obj, supplied_objective, hall_response_status and thrust_minus_drag
//! (PARITY-C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL-V1).
//!
//! T - D_spacecraft with D = D_intake (F1) + D_body. Refused (NOT_EVALUATED) unless T comes from a supplied record
//! that survives the admitted-Hall-member gate and D_body is supplied; a thrust record of status EVALUATED is refused
//! while the credible Hall transport set is EMPTY. The value is a raw difference with its evidence status; no
//! comparison with zero or with a requirement happens here (HC-08 is an assessment, SC-WP-11).
//!
//! The governed Hall status is read from hallthruster_bridge with sha256 verification (contract DIV-D-01): an admitted
//! member changes the ensemble file and needs a re-registered pin, never a silent read.

use crate::pyval::{get, get_or_null, is_number, key_error, py_err, py_float};
use abep_provenance::read_verified;
use abep_types::pyjson::{loads, py_eq, py_repr, py_str, read_text_utf8, Dict, Value};
use abep_types::{AbepError, AbepResult, EvalStatus};
use std::path::Path;

pub const EVALUATED: &str = "EVALUATED";
pub const PARAMETRIC_ONLY: &str = "PARAMETRIC_SENSITIVITY_ONLY";
pub const INCOMPLETE: &str = "INCOMPLETE_EVIDENCE";
pub const NOT_EVALUATED: &str = "NOT_EVALUATED";
pub const SYNTHETIC_ONLY: &str = "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE";
pub const OBJECTIVE_STATUSES: [&str; 5] = [EVALUATED, PARAMETRIC_ONLY, INCOMPLETE, NOT_EVALUATED, SYNTHETIC_ONLY];
pub const RANKABLE_CLASSES: [&str; 5] = ["measured", "digitized", "inferred", "reconstructed", "model-derived"];
pub const SYN_CLASS: &str = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE";

pub const UNLOCK_T: &str = "an ADMITTED Hall transport member (credible set non-empty: a screening candidate promoted by \
pre-registered predictive evidence, CLAUDE.md next-work 1/3) AND a design-specific Hall map (own H-1 geometry and B(z), \
HallMap trustworthy, chemistry_trustworthy) whose domain contains the offered feed state; or a measured H-1 thrust on \
the delivered feed (hardware pivot Phase 1-3, thrust stand RFQ-01)";
pub const UNLOCK_D_SPACECRAFT: &str = "spacecraft frontal area / body + array drag model (F1-ID-08: no spacecraft \
geometry in the repository) at the same orbit states";

pub const ENS_REL: &str = "hallthruster_bridge/ensemble/transport_ensemble_v0.json";
pub const VAL_REL: &str = "hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json";
pub const ENS_SHA256: &str = "2d5069a3382ab667362befeeb5a737261f70a279d19cb89ee79cb61ae35ba08b";
pub const VAL_SHA256: &str = "0a57a397883141be20196853b7d722404dc3cb20c72fba666121fd43507dc97c";

const INTAKE_BASIS_F1: &str = "F1 intake-face drag (frozen TPMC surface / direct TPMC; surface scenario is a TBD \
context axis), max over the five orbit states";

/// EvalStatus of an objective status string (vocabulary of the reference): EVALUATED -> Evaluated; parametric /
/// incomplete -> IncompleteEvidence; NOT_EVALUATED and synthetic test values -> NotEvaluated (never evidence).
pub fn eval_status(objective_status: &str) -> EvalStatus {
    match objective_status {
        EVALUATED => EvalStatus::Evaluated,
        PARAMETRIC_ONLY | INCOMPLETE => EvalStatus::IncompleteEvidence,
        _ => EvalStatus::NotEvaluated,
    }
}

fn opt_err(text: impl std::fmt::Display) -> AbepError {
    py_err("OptimizerError", text)
}

/// `_obj(name, status, value, units, evidence_class, source, reason, unlock, **extra)`.
#[allow(clippy::too_many_arguments)]
pub fn obj(
    name: &str,
    status: &str,
    value: Value,
    units: &str,
    evidence_class: Value,
    source: Value,
    reason: Value,
    unlock: Value,
    extra: Vec<(&str, Value)>,
) -> AbepResult<Value> {
    if !OBJECTIVE_STATUSES.contains(&status) {
        return Err(opt_err(format!("objective status {}", py_repr(&Value::str(status)))));
    }
    let mut d = Dict::new();
    d.insert("objective", Value::str(name));
    d.insert("status", Value::str(status));
    d.insert("value", value);
    d.insert("units", Value::str(units));
    d.insert("evidence_class", evidence_class);
    d.insert("source", source);
    d.insert("reason", reason);
    d.insert("unlock", unlock);
    for (k, v) in extra {
        d.insert(k, v);
    }
    Ok(Value::Dict(d))
}

/// `"k" not in rec` for the shapes the reference accepts as a record.
fn missing_key(rec: &Value, k: &str) -> AbepResult<bool> {
    match rec {
        Value::Dict(d) => Ok(!d.contains_key(k)),
        Value::Str(s) => Ok(!s.contains(k)),
        Value::List(l) => Ok(!l.iter().any(|x| py_eq(x, &Value::str(k)))),
        other => Err(py_err("TypeError", format!("argument of type '{}' is not iterable", other.type_name()))),
    }
}

fn index<'a>(rec: &'a Value, k: &str) -> AbepResult<&'a Value> {
    match rec {
        Value::Dict(d) => get(d, k),
        Value::Str(_) => Err(py_err("TypeError", "string indices must be integers, not 'str'")),
        _ => Err(py_err("TypeError", format!("{} indices must be integers or slices, not str", rec.type_name()))),
    }
}

/// `supplied_objective(name, rec, units)`: admit a caller-supplied objective record {value, evidence_class, source,
/// parametric?}. `rec` Null is None (returns Null). Synthetic data is SYNTHETIC_TEST_ONLY_NOT_EVIDENCE; parametric /
/// non-rankable classes never become EVALUATED.
pub fn supplied_objective(name: &str, rec: &Value, units: &str) -> AbepResult<Value> {
    if matches!(rec, Value::Null) {
        return Ok(Value::Null);
    }
    for k in ["value", "evidence_class", "source"] {
        if missing_key(rec, k)? {
            return Err(opt_err(format!("supplied {name}: '{k}' missing")));
        }
    }
    let v = index(rec, "value")?;
    if !is_number(v) || !py_float(v)?.is_finite() {
        return Err(opt_err(format!("supplied {name}: value must be a finite number (a TBD is not supplied)")));
    }
    let ec = index(rec, "evidence_class")?;
    let parametric = match rec {
        Value::Dict(d) => get_or_null(d, "parametric").truthy(),
        _ => false,
    };
    let st = if py_eq(ec, &Value::str(SYN_CLASS)) {
        SYNTHETIC_ONLY
    } else if parametric || !RANKABLE_CLASSES.iter().any(|c| py_eq(ec, &Value::str(*c))) {
        PARAMETRIC_ONLY
    } else {
        EVALUATED
    };
    let reason = if st == EVALUATED {
        Value::Null
    } else {
        let p = if parametric { " (parametric)" } else { "" };
        Value::Str(format!("supplied value of class {}{p} is not rankable evidence", py_repr(ec)))
    };
    obj(
        name,
        st,
        Value::Float(py_float(v)?),
        units,
        ec.clone(),
        index(rec, "source")?.clone(),
        reason,
        Value::Null,
        vec![("supplied", Value::Bool(true))],
    )
}

/// Admitted Hall transport members (credible set) and the P5-N2 v1 decision (`hall_response_status`).
#[derive(Debug, Clone, PartialEq)]
pub struct HallResponseStatus {
    pub admitted_members: Vec<Value>,
    pub p5_n2_v1_decision: Value,
}

impl HallResponseStatus {
    /// Production read: the governed ensemble and validation release, sha256-verified (DIV-D-01). A missing
    /// validation release gives a null decision, as the reference.
    pub fn load(repo_root: &Path) -> AbepResult<Self> {
        let parse = |rel: &str, b: &[u8]| -> AbepResult<Value> {
            let text = read_text_utf8(b).map_err(|e| AbepError::Schema { path: rel.into(), message: e.to_string() })?;
            loads(&text).map_err(|e| AbepError::Schema { path: rel.into(), message: e.to_string() })
        };
        let ens = parse(ENS_REL, &read_verified(&repo_root.join(ENS_REL), ENS_SHA256)?)?;
        let val_path = repo_root.join(VAL_REL);
        let val = if val_path.exists() { Some(parse(VAL_REL, &read_verified(&val_path, VAL_SHA256)?)?) } else { None };
        Self::from_records(&ens, val.as_ref())
    }

    /// Pure parse of the two documents (`list(ens.get('members', []))`, `val.get('decision')`).
    pub fn from_records(ensemble: &Value, validation: Option<&Value>) -> AbepResult<Self> {
        let ens = ensemble.as_dict().ok_or_else(|| AbepError::Schema {
            path: ENS_REL.into(),
            message: "the transport ensemble is not an object".into(),
        })?;
        let admitted_members = match ens.get("members") {
            None => Vec::new(),
            Some(Value::List(l)) => l.clone(),
            Some(_) => {
                return Err(AbepError::Schema { path: ENS_REL.into(), message: "members is not a list".into() });
            }
        };
        let p5_n2_v1_decision = match validation {
            None => Value::Null,
            Some(Value::Dict(d)) => get_or_null(d, "decision").clone(),
            Some(_) => {
                return Err(AbepError::Schema {
                    path: VAL_REL.into(),
                    message: "the validation release is not an object".into(),
                })
            }
        };
        Ok(HallResponseStatus { admitted_members, p5_n2_v1_decision })
    }

    /// "EMPTY" while no transport member is admitted.
    pub fn credible_set(&self) -> &'static str {
        if self.admitted_members.is_empty() {
            "EMPTY"
        } else {
            "NON_EMPTY"
        }
    }

    pub fn to_value(&self) -> Value {
        abep_types::pydict! {
            "admitted_members" => self.admitted_members.clone(),
            "credible_set" => self.credible_set(),
            "p5_n2_v1_decision" => self.p5_n2_v1_decision.clone(),
            "sources" => vec![Value::str(ENS_REL), Value::str(VAL_REL)],
        }
    }
}

fn field<'a>(o: &'a Value, k: &str) -> AbepResult<&'a Value> {
    match o {
        Value::Dict(d) => get(d, k),
        _ => Err(key_error(k)),
    }
}

fn status_of(o: &Value) -> AbepResult<&str> {
    field(o, "status")?.as_str().ok_or_else(|| AbepError::Model { message: "objective status is not a string".into() })
}

/// `thrust_minus_drag(drag_intake_N, drag_intake_se_N, thrust, spacecraft_drag, repo, intake_drag)`.
///
/// Records are admitted in the reference order D_intake, T, D_body. A supplied `intake_drag` record replaces the F1
/// intake drag (its SE is then None). The composite is EVALUATED only when T, D_body and D_intake all are; any
/// synthetic term makes it SYNTHETIC_TEST_ONLY_NOT_EVIDENCE; otherwise PARAMETRIC_SENSITIVITY_ONLY.
pub fn thrust_minus_drag(
    drag_intake_n: &Value,
    drag_intake_se_n: &Value,
    thrust: &Value,
    spacecraft_drag: &Value,
    hall: &HallResponseStatus,
    intake_drag: &Value,
) -> AbepResult<Value> {
    let di = supplied_objective("D_intake", intake_drag, "N")?;
    let (drag_intake, drag_intake_se) = if matches!(di, Value::Null) {
        (drag_intake_n.clone(), drag_intake_se_n.clone())
    } else {
        (field(&di, "value")?.clone(), Value::Null)
    };
    let mut t = supplied_objective("T", thrust, "N")?;
    let db = supplied_objective("D_body", spacecraft_drag, "N")?;
    let mut missing: Vec<String> = Vec::new();
    if matches!(t, Value::Null) {
        missing.push(format!("T: no admitted Hall response map (credible set {})", hall.credible_set()));
    } else if status_of(&t)? == EVALUATED && hall.admitted_members.is_empty() {
        missing.push(
            "T: a non-synthetic thrust record was supplied but the credible Hall set is EMPTY (no admitted transport \
             member: refused)"
                .to_string(),
        );
        t = Value::Null;
    }
    if matches!(db, Value::Null) {
        missing.push("D_spacecraft: spacecraft body / array drag TBD (F1-ID-08)".to_string());
    }
    let di_status = if !matches!(di, Value::Null) {
        status_of(&di)?.to_string()
    } else if !matches!(drag_intake, Value::Null) {
        PARAMETRIC_ONLY.to_string()
    } else {
        NOT_EVALUATED.to_string()
    };
    let basis = if matches!(di, Value::Null) {
        INTAKE_BASIS_F1.to_string()
    } else {
        format!("supplied intake-drag record ({})", py_str(field(&di, "source")?))
    };
    let partial = abep_types::pydict! {
        "D_intake_N" => drag_intake.clone(),
        "D_intake_se_N" => drag_intake_se,
        "D_intake_status" => di_status.as_str(),
        "D_intake_basis" => basis,
    };
    let unlock_t = Value::str(UNLOCK_T);
    if !missing.is_empty() {
        return obj(
            "T_minus_D_spacecraft_N",
            NOT_EVALUATED,
            Value::Null,
            "N",
            Value::Null,
            Value::Null,
            Value::Str(missing.join("; ")),
            Value::List(vec![unlock_t, Value::str(UNLOCK_D_SPACECRAFT)]),
            vec![("partial", partial)],
        );
    }
    if matches!(drag_intake, Value::Null) {
        return obj(
            "T_minus_D_spacecraft_N",
            NOT_EVALUATED,
            Value::Null,
            "N",
            Value::Null,
            Value::Null,
            Value::str("intake drag not evaluated"),
            Value::List(vec![unlock_t]),
            vec![("partial", partial)],
        );
    }
    let sts = [status_of(&t)?, status_of(&db)?, di_status.as_str()];
    let st = if sts.contains(&SYNTHETIC_ONLY) {
        SYNTHETIC_ONLY
    } else if sts.iter().all(|s| *s == EVALUATED) {
        EVALUATED
    } else {
        PARAMETRIC_ONLY
    };
    let t_value = py_float(field(&t, "value")?)?;
    let di_value = match &drag_intake {
        Value::Int(_) | Value::Float(_) | Value::Bool(_) => py_float(&drag_intake)?,
        other => {
            return Err(py_err(
                "TypeError",
                format!("unsupported operand type(s) for +: '{}' and 'float'", other.type_name()),
            ))
        }
    };
    let d_total = di_value + py_float(field(&db, "value")?)?;
    let source = format!(
        "T: {}; D_body: {}; D_intake: {}",
        py_str(field(&t, "source")?),
        py_str(field(&db, "source")?),
        if matches!(di, Value::Null) { "F1".to_string() } else { py_str(field(&di, "source")?) }
    );
    obj(
        "T_minus_D_spacecraft_N",
        st,
        Value::Float(t_value - d_total),
        "N",
        Value::str(if st == SYNTHETIC_ONLY { SYN_CLASS } else { "model-derived" }),
        Value::Str(source),
        Value::Null,
        Value::Null,
        vec![("partial", partial), ("thrust_N", Value::Float(t_value)), ("drag_total_N", Value::Float(d_total))],
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(v: f64, ec: &str) -> Value {
        abep_types::pydict! { "value" => v, "evidence_class" => ec, "source" => "x" }
    }

    fn empty() -> HallResponseStatus {
        HallResponseStatus { admitted_members: vec![], p5_n2_v1_decision: Value::Null }
    }

    fn admitted() -> HallResponseStatus {
        HallResponseStatus { admitted_members: vec![Value::str("HYPOTHETICAL")], p5_n2_v1_decision: Value::Null }
    }

    fn status(o: &Value) -> &str {
        o.as_dict().unwrap().get("status").unwrap().as_str().unwrap()
    }

    #[test]
    fn evidence_thrust_is_refused_while_the_credible_set_is_empty() {
        let o = thrust_minus_drag(
            &Value::Float(0.01),
            &Value::Float(1e-5),
            &rec(0.03, "measured"),
            &rec(0.002, "measured"),
            &empty(),
            &Value::Null,
        )
        .unwrap();
        assert_eq!(status(&o), NOT_EVALUATED);
        let reason = o.as_dict().unwrap().get("reason").unwrap().as_str().unwrap();
        assert!(reason.contains("credible Hall set is EMPTY"), "{reason}");
        assert_eq!(eval_status(status(&o)), EvalStatus::NotEvaluated);
    }

    #[test]
    fn composite_status_follows_the_reference() {
        let t = rec(0.03, "measured");
        let db = rec(0.002, "measured");
        let o =
            thrust_minus_drag(&Value::Float(0.01), &Value::Float(1e-5), &t, &db, &admitted(), &Value::Null).unwrap();
        assert_eq!(status(&o), PARAMETRIC_ONLY);
        let o = thrust_minus_drag(&Value::Null, &Value::Null, &t, &db, &admitted(), &rec(0.005, "measured")).unwrap();
        assert_eq!(status(&o), EVALUATED);
        let v = o.as_dict().unwrap().get("value").unwrap();
        assert_eq!(v, &Value::Float(0.03 - (0.005 + 0.002)));
        let o = thrust_minus_drag(&Value::Null, &Value::Null, &t, &db, &admitted(), &rec(0.005, SYN_CLASS)).unwrap();
        assert_eq!(status(&o), SYNTHETIC_ONLY);
    }

    #[test]
    fn supplied_objective_refusals() {
        let e = supplied_objective("T", &abep_types::pydict! { "value" => 1.0, "source" => "x" }, "N").unwrap_err();
        assert!(e.to_string().ends_with("OptimizerError: supplied T: 'evidence_class' missing"));
        let bad = abep_types::pydict! { "value" => true, "evidence_class" => "measured", "source" => "x" };
        let e = supplied_objective("T", &bad, "N").unwrap_err();
        assert!(e.to_string().ends_with("value must be a finite number (a TBD is not supplied)"));
        assert_eq!(supplied_objective("T", &Value::Null, "N").unwrap(), Value::Null);
    }
}
