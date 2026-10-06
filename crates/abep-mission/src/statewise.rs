//! Statewise envelope quantifier (A9.14 S9.7 / OD2), `abep_sim/statewise.py` (PARITY-C-ABEP_SIM_STATEWISE_PY-V1), and
//! the reference margin indication `statewise_margin` of `abep_sim/spacecraft_reference_drag.py`
//! (PARITY-C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY-V1).
//!
//! The quantifier is a pure function over caller-supplied states and margins: it holds no requirement value and reads
//! no requirement record; the criterion is the caller's margin function (margin >= 0 passes). Its PASS / FAIL is the
//! quantifier's own vocabulary, mapped onto constraint statuses only by the design and assessment layers (HC-08 lives in
//! SC-WP-11). No raw-physics record of this crate calls it. `statewise_margin` sits here, not in
//! [`crate::reference_drag`], so the raw drag module never compares a thrust with a drag; its result is a REFERENCE
//! indication with freeze_status NOT_EVALUATED, never a gate verdict.

use crate::pyval::{get, get_or_null, nonblank_str, operand, py_err, py_float, req_pos};
use crate::reference_drag::{FREEZE_STATUS, LABEL, SCHEMA, STATUS};
use abep_types::pyjson::{py_eq, py_repr, Dict, Value};
use abep_types::AbepResult;

pub const A9_14_JSON: &str = "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json";
pub const A9_14_SHA256: &str = "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c";

const NOTE_AVERAGE: &str = "informational only; verdict is statewise (A9.14 S9.7 OD2, A9.13 S6.15)";
const NOTE_NO_AVERAGE: &str = "not reported: states carry no time weights";

/// Outcome of one margin evaluation: the margin value, or the error text `<ExceptionClass>: <message>` of a raising
/// margin function.
pub type MarginOutcome = Result<Value, String>;

fn state_dict(st: &Value) -> AbepResult<&Dict> {
    st.as_dict().ok_or_else(|| py_err("AttributeError", format!("'{}' object has no attribute 'get'", st.type_name())))
}

fn check_weight(st: &Dict, w: &Value) -> AbepResult<()> {
    let bad = match w {
        Value::Int(_) => false,
        Value::Float(f) => !f.is_finite() || *f < 0.0,
        _ => true,
    } || matches!(w, Value::Int(i) if i.is_negative());
    if bad {
        return Err(py_err(
            "ValueError",
            format!(
                "state {}: weight must be a finite number >= 0, got {}",
                py_repr(get_or_null(st, "state_id")),
                py_repr(w)
            ),
        ));
    }
    Ok(())
}

struct PerState {
    state_id: Value,
    margin: Option<f64>,
    pass: bool,
    status: &'static str,
}

impl PerState {
    fn to_value(&self) -> Value {
        abep_types::pydict! {
            "state_id" => self.state_id.clone(),
            "margin" => self.margin.map_or(Value::Null, Value::Float),
            "pass" => self.pass,
            "status" => self.status,
        }
    }
}

/// `statewise_quantifier(states, margin_fn, requirement_id)`: evaluate `margin_fn(state)` (>= 0 passes; a bool margin
/// passes when true) at every state. Verdict PASS only if every state passes; a raising or non-finite evaluation is
/// MODEL_ERROR (reported separately from FAIL). The worst state (minimum margin) is always reported; an orbit average
/// only when every state carries a time weight and no evaluation failed - informational, never in the verdict.
pub fn statewise_quantifier(
    states: &[Value],
    margin_fn: &mut dyn FnMut(&Value) -> MarginOutcome,
    requirement_id: &Value,
) -> AbepResult<Value> {
    if states.is_empty() {
        return Err(py_err(
            "ValueError",
            "statewise_quantifier: no states supplied; an empty set cannot satisfy a requirement",
        ));
    }
    if !requirement_id.truthy() {
        return Err(py_err("ValueError", "requirement_id is required"));
    }
    let mut weights = Vec::with_capacity(states.len());
    for st in states {
        weights.push(get_or_null(state_dict(st)?, "weight").clone());
    }
    let all_weighted = weights.iter().all(|w| !matches!(w, Value::Null));
    if weights.iter().any(|w| !matches!(w, Value::Null)) {
        for (st, w) in states.iter().zip(&weights) {
            if matches!(w, Value::Null) {
                continue;
            }
            check_weight(state_dict(st)?, w)?;
        }
        if all_weighted {
            let mut sum = 0.0;
            for w in &weights {
                sum += py_float(w)?;
            }
            // `not sum > 0.0` of the reference: a NaN sum is refused too
            if sum.partial_cmp(&0.0) != Some(std::cmp::Ordering::Greater) {
                return Err(py_err(
                    "ValueError",
                    "statewise_quantifier: state weights sum to 0; no orbit average can be formed",
                ));
            }
        }
    }
    let mut per: Vec<PerState> = Vec::with_capacity(states.len());
    let mut errors: Vec<Value> = Vec::new();
    for st in states {
        let sid = get_or_null(state_dict(st)?, "state_id").clone();
        if matches!(sid, Value::Null) {
            return Err(py_err("ValueError", "every state needs a state_id"));
        }
        let m = match margin_fn(st) {
            Ok(m) => m,
            Err(e) => {
                errors.push(abep_types::pydict! { "state_id" => sid.clone(), "error" => e });
                per.push(PerState { state_id: sid, margin: None, pass: false, status: "MODEL_ERROR" });
                continue;
            }
        };
        let (val, ok) = match m {
            Value::Bool(b) => (if b { 0.0 } else { -1.0 }, b),
            other => {
                let val = py_float(&other)?;
                if !val.is_finite() {
                    errors.push(abep_types::pydict! { "state_id" => sid.clone(), "error" => "non-finite margin" });
                    per.push(PerState { state_id: sid, margin: None, pass: false, status: "MODEL_ERROR" });
                    continue;
                }
                (val, val >= 0.0)
            }
        };
        per.push(PerState { state_id: sid, margin: Some(val), pass: ok, status: if ok { "PASS" } else { "FAIL" } });
    }
    let mut worst: Option<&PerState> = None;
    for p in per.iter().filter(|p| p.margin.is_some()) {
        if worst.is_none_or(|w| p.margin < w.margin) {
            worst = Some(p);
        }
    }
    let n_fail = per.iter().filter(|p| p.status == "FAIL").count();
    let verdict = if !errors.is_empty() {
        "MODEL_ERROR"
    } else if n_fail == 0 {
        "PASS"
    } else {
        "FAIL"
    };
    let mut orbit_avg = None;
    if errors.is_empty() && all_weighted {
        let mut w_sum = 0.0;
        for w in &weights {
            w_sum += py_float(w)?;
        }
        let mut num = 0.0;
        for (w, p) in weights.iter().zip(&per) {
            num += py_float(w)? * p.margin.expect("no error: every margin is finite");
        }
        orbit_avg = Some(num / w_sum);
    }
    Ok(abep_types::pydict! {
        "requirement_id" => requirement_id.clone(),
        "verdict" => verdict,
        "n_states" => per.len() as i64,
        "n_fail" => n_fail as i64,
        "n_model_error" => errors.len() as i64,
        "worst_state" => worst.map_or(Value::Null, PerState::to_value),
        "orbit_average_margin" => orbit_avg.map_or(Value::Null, Value::Float),
        "orbit_average_note" => if orbit_avg.is_some() { NOTE_AVERAGE } else { NOTE_NO_AVERAGE },
        "average_hides_violation" => orbit_avg.is_some_and(|a| a >= 0.0 && verdict != "PASS"),
        "per_state" => per.iter().map(PerState::to_value).collect::<Vec<_>>(),
        "errors" => errors,
        "authority" => abep_types::pydict! {
            "A9.14 S9.7 OD2" => abep_types::pydict! { "path" => A9_14_JSON, "sha256" => A9_14_SHA256 },
        },
    })
}

/// `statewise_margin(thrust_available_N, drag_result, thrust_state, thrust_source)` of spacecraft_reference_drag:
/// the S6.15 margin T_available(state) - D(state) for ONE state against a REFERENCE drag only (`drag_result` is the
/// dict of [`crate::reference_drag::ReferenceDrag::to_value`]). Thrust and drag from different atmospheric / orbit
/// states are refused. Never a gate verdict: freeze_status stays NOT_EVALUATED until the host-spacecraft ICD exists.
pub fn statewise_margin(
    thrust_available_n: &Value,
    drag_result: &Value,
    thrust_state: &Value,
    thrust_source: &Value,
) -> AbepResult<Value> {
    let t = req_pos("thrust_available_N", thrust_available_n, true)?;
    if !nonblank_str(thrust_source) {
        return Err(py_err("ValueError", "thrust_source is required"));
    }
    let drag = match drag_result {
        Value::Dict(d) if py_eq(get_or_null(d, "status"), &Value::str(STATUS)) => d,
        _ => return Err(py_err("ValueError", "drag_result must come from reference_drag()")),
    };
    let state = match thrust_state {
        Value::Dict(s) if py_eq(thrust_state, get(drag, "atmosphere_state")?) => s,
        _ => {
            return Err(py_err(
                "ValueError",
                "thrust and drag must be evaluated at the same atmospheric/orbit state (S6.15)",
            ))
        }
    };
    let d_total = get(drag, "D_total_N")?;
    let m = t - operand(d_total, '-', "float")?;
    Ok(abep_types::pydict! {
        "schema" => SCHEMA,
        "status" => STATUS,
        "freeze_status" => FREEZE_STATUS,
        "label" => LABEL,
        "case_id" => get(drag, "case_id")?.clone(),
        "state" => state.clone(),
        "thrust_source" => thrust_source.clone(),
        "T_available_N" => t,
        "D_N" => d_total.clone(),
        "margin_N" => m,
        "nonnegative_against_reference" => m >= 0.0,
        "note" => "reference/parametric indication only; AG-13 closure needs the host-spacecraft ICD (S6.18)",
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn st(id: &str, w: Option<Value>) -> Value {
        let mut d = Dict::new();
        d.insert("state_id", Value::str(id));
        if let Some(w) = w {
            d.insert("weight", w);
        }
        Value::Dict(d)
    }

    fn run(states: &[Value], margins: Vec<MarginOutcome>) -> AbepResult<Value> {
        let mut it = margins.into_iter();
        statewise_quantifier(states, &mut |_| it.next().expect("one margin per state"), &Value::str("REQ"))
    }

    #[test]
    fn verdicts_worst_state_and_average() {
        let s = [st("a", Some(Value::int(1))), st("b", Some(Value::int(2))), st("c", Some(Value::int(3)))];
        let r = run(&s, vec![Ok(Value::Float(1.0)), Ok(Value::Float(-1.0)), Ok(Value::Float(0.5))]).unwrap();
        let d = r.as_dict().unwrap();
        assert_eq!(d.get("verdict").unwrap().as_str(), Some("FAIL"));
        // (1 * 1.0 + 2 * -1.0 + 3 * 0.5) / (1 + 2 + 3)
        let avg = 0.5 / 6.0;
        assert_eq!(d.get("orbit_average_margin"), Some(&Value::Float(avg)));
        assert_eq!(d.get("average_hides_violation"), Some(&Value::Bool(true)));
        let w = d.get("worst_state").unwrap().as_dict().unwrap();
        assert_eq!(w.get("state_id").unwrap().as_str(), Some("b"));
    }

    #[test]
    fn errors_are_model_error_never_pass() {
        let s = [st("a", None), st("b", None)];
        let r = run(&s, vec![Err("RuntimeError: boom".into()), Ok(Value::Float(f64::NAN))]).unwrap();
        let d = r.as_dict().unwrap();
        assert_eq!(d.get("verdict").unwrap().as_str(), Some("MODEL_ERROR"));
        assert_eq!(d.get("n_model_error"), Some(&Value::int(2)));
        assert_eq!(d.get("worst_state"), Some(&Value::Null));
    }

    #[test]
    fn input_refusals() {
        let e = statewise_quantifier(&[], &mut |_| Ok(Value::Float(1.0)), &Value::str("R")).unwrap_err();
        assert!(e.to_string().ends_with(
            "ValueError: statewise_quantifier: no states supplied; an empty set cannot satisfy a requirement"
        ));
        let s = [st("a", Some(Value::Float(0.0))), st("b", Some(Value::Float(0.0)))];
        let e = run(&s, vec![]).unwrap_err().to_string();
        assert!(e.ends_with("state weights sum to 0; no orbit average can be formed"), "{e}");
        let s = [st("a", Some(Value::Bool(true)))];
        let e = run(&s, vec![]).unwrap_err().to_string();
        assert!(e.ends_with("ValueError: state 'a': weight must be a finite number >= 0, got True"), "{e}");
    }
}
