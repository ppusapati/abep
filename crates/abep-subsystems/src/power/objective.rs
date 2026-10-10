//! The raw P_bus objective of the design layer (`bus_power` of `abep_sim/programme/design_synthesis.py`, without its
//! assessment field `gate_verdict`). EVALUATED only from supplied COMPLETE ledgers (steady + start-up steps) whose
//! every entering evidence class is rankable; PARAMETRIC_SENSITIVITY_ONLY on other classes; SYNTHETIC_TEST_ONLY on
//! synthetic ledgers; INCOMPLETE_EVIDENCE for an incomplete steady ledger; NOT_EVALUATED with the official ledger's
//! status and lower bound when nothing is supplied. The RFP gate verdict is an assessment (abep-assess, SC-WP-11).

use super::official::{official_ledger, MassPowerA9V5};
use super::slots::BOUNDARY_VERSION;
use super::{PowerError, PowerResult};
use abep_types::pyjson::{py_repr, Dict, Value};

pub const EVALUATED: &str = "EVALUATED";
pub const PARAMETRIC_ONLY: &str = "PARAMETRIC_SENSITIVITY_ONLY";
pub const INCOMPLETE: &str = "INCOMPLETE_EVIDENCE";
pub const NOT_EVALUATED: &str = "NOT_EVALUATED";
pub const SYNTHETIC_ONLY: &str = "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE";
pub const SYN_CLASS: &str = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE";
pub const RANKABLE_CLASSES: [&str; 5] = ["measured", "digitized", "inferred", "reconstructed", "model-derived"];
pub const UNLOCK_P_BUS: &str = "every installed A9-02 slot load and supply efficiency at a registered condition (Hall \
discharge from the registered H-1 envelope, coils from the frozen MC-1, RF generator DC input measured, compressor \
ICD row 22, valve drivers, thermal, housekeeping, front end) on the p_bus_1ms_max basis with a conformant gate \
measurement (A9.1 OQ-A902-01)";

fn key_error(k: &str) -> PowerError {
    PowerError::new("KeyError", format!("'{k}'"))
}

fn field<'a>(d: &'a Dict, k: &str) -> PowerResult<&'a Value> {
    d.get(k).ok_or_else(|| key_error(k))
}

/// Supplied ledgers must be a non-empty sequence of start-up ledgers plus a steady ledger of this boundary
/// (the structural preconditions of the reference's gate call, without the gate).
fn check_ledgers<'a>(steady: &'a Value, startup: &'a Value) -> PowerResult<(&'a Dict, Vec<&'a Dict>)> {
    let steps = match startup {
        Value::List(l) if !l.is_empty() => l,
        _ => {
            return Err(PowerError::boundary("bus_power needs a non-empty sequence of start-up step ledgers (row 108)"))
        }
    };
    let as_ledger = |v: &'a Value| -> PowerResult<&'a Dict> {
        match v {
            Value::Dict(d) if d.get("boundary_version").and_then(Value::as_str) == Some(BOUNDARY_VERSION) => Ok(d),
            other => {
                let r: String = py_repr(other).chars().take(80).collect();
                Err(PowerError::boundary(format!("not a {BOUNDARY_VERSION} ledger: {r}")))
            }
        }
    };
    let s = as_ledger(steady)?;
    let st = steps.iter().map(as_ledger).collect::<PowerResult<Vec<_>>>()?;
    Ok((s, st))
}

/// `_ledger_classes(led)`: every evidence class that enters P_bus (loads, slot efficiencies, front end).
fn ledger_classes(led: &Dict, out: &mut Vec<String>) -> PowerResult<()> {
    for c in field(led, "load_evidence_classes")?.as_list().unwrap_or(&[]) {
        if let Some(s) = c.as_str() {
            out.push(s.to_string());
        }
    }
    let items = field(led, "items")?.as_list().unwrap_or(&[]);
    for it in items.iter().filter_map(Value::as_dict) {
        let eff_known = it.get("efficiency").is_some_and(|v| *v != Value::Null);
        if let (true, Some(Value::Str(c))) = (eff_known, it.get("efficiency_evidence_class")) {
            if !c.is_empty() {
                out.push(c.clone());
            }
        }
    }
    let internal_on = items.iter().filter_map(Value::as_dict).any(|it| {
        it.get("path").and_then(Value::as_str) == Some("internal_bus")
            && it.get("state").and_then(Value::as_str) != Some("OFF")
    });
    if internal_on {
        let fe = field(led, "front_end")?.as_dict().ok_or_else(|| key_error("evidence_class"))?;
        out.push(match fe.get("evidence_class") {
            Some(Value::Str(s)) if !s.is_empty() => s.clone(),
            _ => "TBD".to_string(),
        });
    }
    Ok(())
}

fn obj(status: &str, value: Value, evidence_class: Value, source: Value, reason: Value, unlock: Value) -> Dict {
    let mut d = Dict::new();
    d.insert("objective", Value::str("P_bus_W"));
    d.insert("status", Value::str(status));
    d.insert("value", value);
    d.insert("units", Value::str("W"));
    d.insert("evidence_class", evidence_class);
    d.insert("source", source);
    d.insert("reason", reason);
    d.insert("unlock", unlock);
    d
}

/// Supplied ledgers of `bus_power` as Python-shaped values (`{'steady', 'startup', 'synthetic'?, 'source'?}`).
pub fn bus_power_supplied(supplied: &Dict) -> PowerResult<Value> {
    let steady = field(supplied, "steady")?;
    let startup = field(supplied, "startup")?;
    let (s, st) = check_ledgers(steady, startup)?;
    let mut classes = Vec::new();
    ledger_classes(s, &mut classes)?;
    for l in &st {
        ledger_classes(l, &mut classes)?;
    }
    classes.sort();
    classes.dedup();
    let unlock = Value::List(vec![Value::str(UNLOCK_P_BUS)]);
    let status = field(s, "status")?;
    if status.as_str() != Some("COMPLETE") {
        let reason = format!("supplied steady ledger {}", abep_types::pyjson::py_str(status));
        let mut d = obj(INCOMPLETE, Value::Null, Value::Null, Value::Null, Value::str(reason), unlock);
        d.insert("lower_bound_W", field(s, "P_bus_lower_bound_W")?.clone());
        return Ok(Value::Dict(d));
    }
    let syn = supplied.get("synthetic").is_some_and(Value::truthy);
    let st_label = if syn {
        SYNTHETIC_ONLY
    } else if classes.iter().all(|c| RANKABLE_CLASSES.contains(&c.as_str())) {
        EVALUATED
    } else {
        PARAMETRIC_ONLY
    };
    let ec = if syn { SYN_CLASS.to_string() } else { classes.join(",") };
    let source = supplied.get("source").cloned().unwrap_or_else(|| Value::str("supplied A9-02 ledgers"));
    let mut d = obj(st_label, field(s, "P_bus_W")?.clone(), Value::str(ec), source, Value::Null, Value::Null);
    d.insert("power_basis", field(s, "power_basis")?.clone());
    Ok(Value::Dict(d))
}

/// `bus_power(config, compressor_P_W)` without supplied ledgers: NOT_EVALUATED with the official ledger's status.
pub fn bus_power_official(mp: &MassPowerA9V5, config: &str, compressor_p_w: Option<f64>) -> PowerResult<Value> {
    let off = official_ledger(mp, config, None, "")?;
    let par = match compressor_p_w {
        Some(p) => Some(official_ledger(mp, config, Some(p), "")?),
        None => None,
    };
    let reason = format!(
        "A9-02 official ledger status {} ({} TBD terms; compressor load TBD per row 22); every Hall / ICP / C1 / valve \
         / thermal / housekeeping load and every supply efficiency is TBD",
        off.status.as_str(),
        off.tbd.len()
    );
    let mut d = obj(
        NOT_EVALUATED,
        Value::Null,
        Value::Null,
        Value::Null,
        Value::str(reason),
        Value::List(vec![Value::str(UNLOCK_P_BUS)]),
    );
    d.insert("official_status", Value::str(off.status.as_str()));
    d.insert("official_lower_bound_W", Value::Float(off.p_bus_lower_bound_w));
    d.insert("parametric_lower_bound_W", par.as_ref().map_or(Value::Null, |p| Value::Float(p.p_bus_lower_bound_w)));
    d.insert("parametric_status", par.as_ref().map_or(Value::Null, |p| Value::str(p.status.as_str())));
    let mut ctx = Dict::new();
    ctx.insert("design_allocation_W", Value::Float(super::allocation::DESIGN_ALLOCATION_W));
    ctx.insert("common_allocation_W", Value::Float(super::allocation::COMMON_ALLOCATION_W));
    ctx.insert("rule", Value::str("owner allocations (rows 109, 114), never gates or predictions"));
    d.insert("allocation_context", Value::Dict(ctx));
    Ok(Value::Dict(d))
}
