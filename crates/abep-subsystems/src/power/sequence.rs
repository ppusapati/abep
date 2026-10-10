//! Start-up / concurrent-load sequence rules of the flight configuration (`check_startup_sequence` and
//! `_peak_rises` of `abep_sim/bus_boundary_a9_v2.py`; revised SEQ-1, row 112; A9.1 SEQ-peaks).
//!
//! Each step is a full ledger of the loads that are on together in that step (the concurrent-load case). The rules:
//! at most one peak-class event per step, at most one peak-class load commanded to rise per step (checked on the
//! loads, a declared dependent rise excepted), and the enforced orderings. Violations are reported, TBD transitions
//! that may rise make a rule NOT_EVALUABLE, malformed input is refused. The result carries no RFP verdict (the
//! transient gate is an assessment, SC-WP-11) and no allocation verdict; the C1 start-up rule of the ground
//! reference is not part of the flight configuration.

use super::ledger::{ledger, Ledger, LedgerArgs};
use super::pyfmt::{nonempty, repr_str_list};
use super::slots::{
    installed_slots, peak_event_slot, Slot, DEPENDENT_RISES, DEPENDENT_RISE_RULE, ENFORCED_ORDER, PEAK_EVENTS,
};
use super::{PowerError, PowerResult};
use abep_types::pyjson::{py_eq, py_repr, py_repr_str, Dict, Value};

pub const PEAK_RULE: &str = "at most one peak-class slot load commanded to rise per step (row 112; A9.1 SEQ-peaks \
baseline rule; checked by load, independent of event labels, except a declared dependent rise (DEPENDENT_RISES) of \
the step's own event)";
pub const ONE_EVENT_RULE: &str = "one peak-class event per step (row 112; A9.1 SEQ-peaks)";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SequenceStatus {
    RulesSatisfied,
    RulesNotEvaluable,
    SequenceRuleViolation,
}

impl SequenceStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            SequenceStatus::RulesSatisfied => "RULES_SATISFIED",
            SequenceStatus::RulesNotEvaluable => "RULES_NOT_EVALUABLE",
            SequenceStatus::SequenceRuleViolation => "SEQUENCE_RULE_VIOLATION",
        }
    }
}

/// Result of [`check_startup_sequence`]: the rule findings and one ledger per step (the last is the steady step).
#[derive(Debug, Clone, PartialEq)]
pub struct SequenceResult {
    pub variant: Vec<Value>,
    pub sequence_status: SequenceStatus,
    pub violations: Vec<Value>,
    pub not_evaluable: Vec<Value>,
    pub dependent_rises: Vec<Value>,
    pub ledgers: Vec<Ledger>,
}

impl SequenceResult {
    pub fn steady(&self) -> &Ledger {
        self.ledgers.last().expect("a sequence has at least two steps")
    }

    /// Per-step summary records (`steps` of the reference result).
    pub fn steps_value(&self) -> Value {
        Value::List(
            self.ledgers
                .iter()
                .map(|l| {
                    let mut d = Dict::new();
                    d.insert("step_id", l.label.clone());
                    d.insert("status", Value::str(l.status.as_str()));
                    d.insert("power_basis", super::ledger::opt_s(&l.power_basis));
                    d.insert("P_bus_W", super::ledger::opt_f(l.p_bus_w));
                    d.insert("P_bus_lower_bound_W", Value::Float(l.p_bus_lower_bound_w));
                    Value::Dict(d)
                })
                .collect(),
        )
    }
}

fn slot_list(slots: &[Slot]) -> Value {
    Value::List(slots.iter().map(|s| Value::str(s.name())).collect())
}

fn record(step_id: &Value, rule: &str, detail: Value) -> Value {
    let mut d = Dict::new();
    d.insert("step_id", step_id.clone());
    d.insert("rule", Value::str(rule));
    d.insert("detail", detail);
    Value::Dict(d)
}

/// `_peak_rises(prev, cur, peak_slots)`: slots whose load certainly rises (a known increase, or exactly 0 W -> TBD)
/// and those that may rise (any other transition involving TBD, except TBD -> exactly 0 W).
pub fn peak_rises(prev: &[(Slot, Option<f64>)], cur: &[(Slot, Option<f64>)], peak: &[Slot]) -> (Vec<Slot>, Vec<Slot>) {
    let get = |m: &[(Slot, Option<f64>)], s: Slot| m.iter().find(|(x, _)| *x == s).and_then(|(_, v)| *v);
    let (mut sure, mut maybe) = (Vec::new(), Vec::new());
    for &s in peak {
        let (a, b) = (get(prev, s), get(cur, s));
        match (a, b) {
            (Some(a), Some(b)) => {
                if b > a {
                    sure.push(s);
                }
            }
            (Some(0.0), None) => sure.push(s),
            (_, None) => maybe.push(s),
            (None, Some(b)) => {
                if b > 0.0 {
                    maybe.push(s);
                }
            }
        }
    }
    (sure, maybe)
}

/// `check_startup_sequence(config, steps, front_end, variant)` on JSON values, without the transient gate.
pub fn check_startup_sequence(
    config: &Value,
    steps: &Value,
    front_end: &Value,
    variant: &Value,
) -> PowerResult<SequenceResult> {
    let inst = installed_slots(config, variant)?;
    let steps = match steps {
        Value::List(l) if l.len() >= 2 => l,
        _ => {
            return Err(PowerError::boundary(
                "a start-up sequence needs at least one start-up step and a final steady step",
            ))
        }
    };
    let peak: Vec<Slot> =
        Slot::ALL.into_iter().filter(|s| PEAK_EVENTS.iter().any(|(_, p)| p == s) && inst.contains(s)).collect();
    let mut ledgers = Vec::new();
    let (mut violations, mut not_evaluable, mut dependent_rises) = (Vec::new(), Vec::new(), Vec::new());
    let mut seen: Vec<(&'static str, usize)> = Vec::new();
    let mut ids: Vec<String> = Vec::new();
    let mut prev_p: Option<Vec<(Slot, Option<f64>)>> = None;
    let n = steps.len();
    for (i, st) in steps.iter().enumerate() {
        let Value::Dict(sd) = st else {
            return Err(PowerError::boundary(format!("step {i} must be a mapping")));
        };
        let sid = nonempty(sd, "step_id", &format!("step {i}"), "BoundaryA9Error")?;
        if ids.contains(&sid) {
            return Err(PowerError::boundary(format!("duplicate step_id {}", py_repr_str(&sid))));
        }
        ids.push(sid.clone());
        let steady = sd.get("phase").is_some_and(|p| py_eq(p, &Value::str("steady")));
        if steady != (i == n - 1) {
            return Err(PowerError::boundary("exactly the last step must carry phase 'steady'"));
        }
        let events: Vec<Value> = match sd.get("event") {
            None | Some(Value::Null) => vec![],
            Some(Value::List(l)) => l.clone(),
            Some(other) => vec![other.clone()],
        };
        let mut step_events: Vec<&'static str> = Vec::new();
        for e in &events {
            if matches!(e, Value::List(_) | Value::Dict(_)) {
                return Err(PowerError::new("TypeError", format!("unhashable type: '{}'", e.type_name())));
            }
            let known = e.as_str().and_then(|s| PEAK_EVENTS.iter().find(|(n, _)| *n == s));
            let Some(&(name, slot)) = known else {
                let mut allowed: Vec<&str> = PEAK_EVENTS.iter().map(|(n, _)| *n).collect();
                allowed.sort_unstable();
                return Err(PowerError::boundary(format!(
                    "step {}: unknown event {}; allowed {}",
                    py_repr_str(&sid),
                    py_repr(e),
                    repr_str_list(&allowed)
                )));
            };
            if !inst.contains(&slot) {
                return Err(PowerError::boundary(format!(
                    "step {}: event {} needs slot {}, not installed in 'hall_icp_neutralizer'",
                    py_repr_str(&sid),
                    py_repr(e),
                    py_repr_str(slot.name())
                )));
            }
            if !seen.iter().any(|(n, _)| *n == name) {
                seen.push((name, i));
            }
            step_events.push(name);
        }
        let sid_v = Value::str(sid.clone());
        if events.len() > 1 {
            violations.push(record(&sid_v, ONE_EVENT_RULE, Value::List(events.clone())));
        }
        let led = ledger(&LedgerArgs {
            config: config.clone(),
            loads: sd.get("loads").cloned().unwrap_or(Value::Null),
            efficiencies: sd.get("efficiencies").cloned().unwrap_or(Value::Null),
            front_end: front_end.clone(),
            variant: variant.clone(),
            label: sid_v.clone(),
            power_basis: sd.get("power_basis").cloned().unwrap_or(Value::Null),
            gate_measurement: sd.get("gate_measurement").cloned().unwrap_or(Value::Null),
        })?;
        let cur: Vec<(Slot, Option<f64>)> = led.items.iter().map(|it| (it.slot, it.p_w)).collect();
        if let Some(prev) = &prev_p {
            let (sure, maybe) = peak_rises(prev, &cur, &peak);
            let mut dep_ok: Vec<Slot> = Vec::new();
            for e in &step_events {
                for (de, ds) in DEPENDENT_RISES {
                    if de == *e {
                        dep_ok.extend_from_slice(ds);
                    }
                }
            }
            let dep: Vec<Slot> = sure.iter().chain(maybe.iter()).copied().filter(|x| dep_ok.contains(x)).collect();
            if !dep.is_empty() {
                let mut d = Dict::new();
                d.insert("step_id", sid_v.clone());
                d.insert("events", Value::List(events.clone()));
                d.insert("dependent_slots", slot_list(&dep));
                d.insert("rule", Value::str(DEPENDENT_RISE_RULE));
                dependent_rises.push(Value::Dict(d));
            }
            let sure: Vec<Slot> = sure.into_iter().filter(|x| !dep_ok.contains(x)).collect();
            let maybe: Vec<Slot> = maybe.into_iter().filter(|x| !dep_ok.contains(x)).collect();
            if sure.len() > 1 {
                violations.push(record(&sid_v, PEAK_RULE, slot_list(&sure)));
            } else if sure.len() + maybe.len() > 1 {
                let mut d = Dict::new();
                d.insert("rising", slot_list(&sure));
                d.insert("TBD_may_rise", slot_list(&maybe));
                not_evaluable.push(record(&sid_v, PEAK_RULE, Value::Dict(d)));
            }
        }
        prev_p = Some(cur);
        ledgers.push(led);
    }
    let seen_at = |e: &str| seen.iter().find(|(n, _)| *n == e).map(|(_, i)| *i);
    for (a, b) in ENFORCED_ORDER {
        let step_id_of = |i: usize| steps[i].as_dict().and_then(|d| d.get("step_id")).cloned().unwrap_or(Value::Null);
        if let (Some(ia), Some(ib)) = (seen_at(a), seen_at(b)) {
            if ia >= ib {
                let mut d = Dict::new();
                d.insert(a, Value::int(ia as i64));
                d.insert(b, Value::int(ib as i64));
                violations.push(record(&step_id_of(ib), &format!("{a} before {b}"), Value::Dict(d)));
            }
        }
        if let (Some(ib), None) = (seen_at(b), seen_at(a)) {
            violations.push(record(&step_id_of(ib), &format!("{a} before {b}"), Value::str(format!("{a} missing"))));
        }
    }
    let status = if !violations.is_empty() {
        SequenceStatus::SequenceRuleViolation
    } else if !not_evaluable.is_empty() {
        SequenceStatus::RulesNotEvaluable
    } else {
        SequenceStatus::RulesSatisfied
    };
    let _ = peak_event_slot;
    Ok(SequenceResult {
        variant: variant.as_list().map(|l| l.to_vec()).unwrap_or_default(),
        sequence_status: status,
        violations,
        not_evaluable,
        dependent_rises,
        ledgers,
    })
}
