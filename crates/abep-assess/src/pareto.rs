//! S6.17 system comparison (`design_gates.pareto_s6_17`, contract E11): hard constraints first (a VIOLATED row is
//! excluded; NOT_EVALUATED constraints make the set CONDITIONAL), then a Pareto filter over the declared objectives.
//! No weighted scalar score.

use crate::error::{rule_error, AssessError, AssessResult};
use crate::py::{dget, dget_or, dict, eq_str, finite, float, get, s, strs};
use abep_gaspath::upstream::{C_MET, C_VIOLATED};
use abep_types::pyjson::{py_str, Dict, Value};

pub const PARETO_OBJECTIVES_S6_17: [(&str, &str, &str); 6] = [
    (
        "worst_state_margin",
        "max",
        "worst-state thrust / feed margin (AG-12 / AG-13); NOT_EVALUATED until a validated H-1 map and the spacecraft \
         drag basis exist; the worst-state delivered flow is the upstream proxy",
    ),
    ("drag_N", "min", "spacecraft / intake drag (worst state)"),
    ("P_upstream_W", "min", "upstream electrical power (worst state)"),
    ("mass_kg", "min", "hardware mass (or a declared monotone proxy)"),
    ("volume_m3", "min", "required volume (or a declared monotone proxy)"),
    ("Q_reject_W", "min", "thermal-rejection burden"),
];

pub const HARD_CONSTRAINTS_FIRST: [&str; 7] = [
    "AG-12 feed-state / thrust sufficiency",
    "AG-13 statewise drag compensation",
    "power",
    "mass",
    "thermal",
    "material / life",
    "H-1 feed-quality tolerances (ripple)",
];

/// `_dominates(a, b, senses)`.
fn dominates(a: &[f64], b: &[f64], senses: &[&str]) -> bool {
    let mut better = false;
    for ((x, y), sn) in a.iter().zip(b).zip(senses) {
        let (x, y) = if *sn == "max" { (-x, -y) } else { (*x, *y) };
        if x > y {
            return false;
        }
        if x < y {
            better = true;
        }
    }
    better
}

fn id_str(v: &Value) -> AssessResult<String> {
    match v {
        Value::Str(x) => Ok(x.clone()),
        other => Err(AssessError::new("TypeError", format!("row id {} is not a str", py_str(other)))),
    }
}

/// `pareto_s6_17(rows, objectives=PARETO_OBJECTIVES_S6_17, weights=None)`.
pub fn pareto_s6_17(rows: &[Value], weights_supplied: bool) -> AssessResult<Value> {
    if weights_supplied {
        return Err(rule_error("A9.13 S6.17: no arbitrary weighted scalar score; system comparison is Pareto-based"));
    }
    let keys: Vec<&str> = PARETO_OBJECTIVES_S6_17.iter().map(|o| o.0).collect();
    let senses: Vec<&str> = PARETO_OBJECTIVES_S6_17.iter().map(|o| o.1).collect();
    let (mut excluded, mut cand, mut incomplete) = (Vec::new(), Vec::<(String, Vec<f64>)>::new(), Vec::new());
    let mut conditional: Vec<String> = Vec::new();
    for r in rows {
        let cons = dget_or(r, "constraints", Value::Dict(Dict::new()))?;
        let cons = cons.as_dict().ok_or_else(|| AssessError::new("AttributeError", "constraints has no items"))?;
        let mut viol: Vec<String> =
            cons.iter().filter(|(_, v)| eq_str(v, C_VIOLATED)).map(|(k, _)| k.clone()).collect();
        viol.sort();
        if !viol.is_empty() {
            excluded.push(dict(vec![
                ("id", get(r, "id")?.clone()),
                ("violated", Value::List(viol.into_iter().map(Value::Str).collect())),
            ]));
            continue;
        }
        for (k, v) in cons.iter() {
            if !eq_str(v, C_MET) && !conditional.contains(k) {
                conditional.push(k.clone());
            }
        }
        let objs = dget_or(r, "objectives", Value::Dict(Dict::new()))?;
        let mut vals = Vec::new();
        for k in &keys {
            vals.push(dget(&objs, k)?);
        }
        if vals.iter().any(|v| !finite(v)) {
            let ne: Vec<Value> = keys.iter().zip(&vals).filter(|(_, v)| !finite(v)).map(|(k, _)| s(*k)).collect();
            incomplete.push(dict(vec![("id", get(r, "id")?.clone()), ("objectives_not_evaluated", Value::List(ne))]));
            continue;
        }
        let fv: AssessResult<Vec<f64>> = vals.iter().map(float).collect();
        cand.push((id_str(get(r, "id")?)?, fv?));
    }
    let mut members: Vec<String> = cand
        .iter()
        .filter(|(i, v)| !cand.iter().any(|(j, w)| j != i && dominates(w, v, &senses)))
        .map(|(i, _)| i.clone())
        .collect();
    members.sort();
    conditional.sort();
    let status = if members.is_empty() {
        "EMPTY"
    } else if conditional.is_empty() {
        "CONSTRAINTS_MET_ON_SUPPLIED_VALUES"
    } else {
        "CONDITIONAL_ON_NOT_EVALUATED_CONSTRAINTS"
    };
    let objectives = PARETO_OBJECTIVES_S6_17
        .iter()
        .map(|(k, sn, d)| dict(vec![("key", s(*k)), ("sense", s(*sn)), ("definition", s(*d))]))
        .collect();
    Ok(dict(vec![
        ("objectives", Value::List(objectives)),
        ("hard_constraints_first", strs(&HARD_CONSTRAINTS_FIRST)),
        ("members", Value::List(members.into_iter().map(Value::Str).collect())),
        ("status", s(status)),
        ("conditional_on", Value::List(conditional.into_iter().map(Value::Str).collect())),
        ("excluded_violating", Value::List(excluded)),
        ("not_ranked_incomplete_objectives", Value::List(incomplete)),
        ("weighted_scalar", s("REFUSED (S6.17)")),
    ]))
}
