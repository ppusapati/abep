//! GNG-ICP-01, the mandatory ICP go / no-go gate before LOCK-1 (A9.21 item 4; `docs/requirements/rvm_a9/
//! a9_21_icp_gate.py` evaluate / lock1_release_reportable; contract R7 / R8). Fail closed: NOT_EVALUATED unless
//! owner-accepted criteria (an owner decision citation that verifies by sha256) AND registered evidence for every
//! criterion exist; GO only when every criterion is MET. The recorder proposal RP-A919-01 is never a criterion.

use crate::error::AssessResult;
use crate::py::{dget, dict, eq_str, in_strs, s};
use abep_provenance::sha256_hex;
use abep_types::pyjson::{py_eq, py_isspace, py_lower, py_repr, py_str, py_strip, Value};
use std::path::Path;

pub const GATE_ID: &str = "GNG-ICP-01";
pub const PROPOSAL_ID: &str = "RP-A919-01";
pub const GO: &str = "GO";
pub const NO_GO: &str = "NO_GO";
pub const NOT_EVALUATED: &str = "NOT_EVALUATED";
pub const CRITERIA_PENDING: &str = "PENDING_OWNER_ACCEPTANCE";
pub const CRITERIA_ACCEPTED: &str = "OWNER_ACCEPTED";
pub const RESULTS: [&str; 2] = ["MET", "NOT_MET"];

/// `" ".join(str(s).split())`.
fn norm(x: &str) -> String {
    x.split(py_isspace).filter(|w| !w.is_empty()).collect::<Vec<_>>().join(" ")
}

/// `^[0-9a-f]{64}$` with Python `re.match` semantics (`$` also matches before one trailing newline).
fn hex64(x: &str) -> bool {
    let body = x.strip_suffix('\n').unwrap_or(x);
    body.len() == 64 && body.bytes().all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
}

/// `criteria.get("items") or []` as a list of values; text lookups use `.get("text", "")` semantics.
fn items_of(criteria: &Value) -> AssessResult<Vec<Value>> {
    let v = dget(criteria, "items")?;
    if !v.truthy() {
        return Ok(vec![]);
    }
    Ok(match v {
        Value::List(l) => l.into_iter().collect(),
        Value::Dict(d) => d.keys().map(|k| s(k.as_str())).collect(),
        Value::Str(t) => t.chars().map(|c| s(c.to_string())).collect(),
        other => {
            return Err(crate::error::AssessError::new(
                "TypeError",
                format!("'{}' object is not iterable", other.type_name()),
            ))
        }
    })
}

/// `i.get("text", "")`.
fn text_of(i: &Value) -> AssessResult<Value> {
    crate::py::dget_or(i, "text", s(""))
}

/// `_pinned_file_ok(ref, root)`: ref = {'path', 'sha256'} names a regular file strictly inside root whose sha256
/// equals the pin.
pub fn pinned_file_ok(r: &Value, root: &Path) -> AssessResult<bool> {
    let path = dget(r, "path")?;
    let sha = match r.as_dict().and_then(|d| d.get("sha256")) {
        Some(v) => py_str(v),
        None => String::new(),
    };
    let Value::Str(path) = path else { return Ok(false) };
    if py_strip(&path).is_empty() || !hex64(&sha) {
        return Ok(false);
    }
    let Ok(base) = std::fs::canonicalize(root) else { return Ok(false) };
    let Ok(p) = std::fs::canonicalize(base.join(&path)) else { return Ok(false) };
    if p == base || !p.starts_with(&base) || !p.is_file() {
        return Ok(false);
    }
    let Ok(bytes) = std::fs::read(&p) else { return Ok(false) };
    Ok(sha256_hex(&bytes) == sha)
}

fn result(status: &str, reason: String, extra: Option<(&str, Vec<Value>)>) -> Value {
    let mut v = vec![("status", s(status)), ("reason", s(reason))];
    if let Some((k, l)) = extra {
        v.push((k, Value::List(l)));
    }
    dict(v)
}

/// `evaluate(criteria, evidence, root)`; `proposal` is the preserved RP-A919-01 text (from the committed RVM).
pub fn evaluate(criteria: &Value, evidence: &Value, root: &Path, proposal: &str) -> AssessResult<Value> {
    if !matches!(criteria, Value::Dict(_)) || !eq_str(&dget(criteria, "status")?, CRITERIA_ACCEPTED) {
        return Ok(result(
            NOT_EVALUATED,
            format!("no owner-accepted GO / NO-GO criterion (criteria {CRITERIA_PENDING}); fail closed (A9.21)"),
            None,
        ));
    }
    if uses_proposal(criteria, proposal)? {
        return Ok(result(
            NOT_EVALUATED,
            format!(
                "the recorder proposal {PROPOSAL_ID} is preserved for owner review only and is never GO / NO-GO \
                 criteria"
            ),
            None,
        ));
    }
    let dec = {
        let d = dget(criteria, "owner_decision")?;
        if d.truthy() {
            d
        } else {
            dict(vec![])
        }
    };
    let dsha = match dec.as_dict().and_then(|d| d.get("sha256")) {
        Some(v) => py_str(v),
        None => String::new(),
    };
    if !dget(&dec, "path")?.truthy() || !hex64(&dsha) {
        return Ok(result(NOT_EVALUATED, "criteria carry no owner decision citation (path + sha256)".into(), None));
    }
    if !pinned_file_ok(&dec, root)? {
        return Ok(result(
            NOT_EVALUATED,
            "owner decision citation does not verify (file missing or sha256 mismatch)".into(),
            None,
        ));
    }
    let items = items_of(criteria)?;
    let ids: Vec<Value> =
        items.iter().filter(|i| matches!(i, Value::Dict(_))).map(|i| dget(i, "id")).collect::<AssessResult<_>>()?;
    let unique = ids.iter().enumerate().all(|(n, a)| ids[..n].iter().all(|b| !py_eq(a, b)));
    if ids.is_empty() || ids.len() != items.len() || ids.iter().any(|i| !i.truthy()) || !unique {
        return Ok(result(
            NOT_EVALUATED,
            "owner-accepted criteria list empty or ids missing / not unique".into(),
            None,
        ));
    }
    let mut by: Vec<(Value, Vec<String>)> = Vec::new();
    let ev = if evidence.truthy() { evidence.clone() } else { Value::List(vec![]) };
    let entries: Vec<Value> = match ev {
        Value::List(l) => l,
        Value::Dict(d) => d.keys().map(|k| s(k.as_str())).collect(),
        other => {
            return Err(crate::error::AssessError::new(
                "TypeError",
                format!("'{}' object is not iterable", other.type_name()),
            ))
        }
    };
    for e in &entries {
        if !matches!(e, Value::Dict(_)) {
            continue;
        }
        let src = {
            let x = dget(e, "source")?;
            if x.truthy() {
                x
            } else {
                dict(vec![])
            }
        };
        let res = dget(e, "result")?;
        if in_strs(&res, &RESULTS) && matches!(src, Value::Dict(_)) && pinned_file_ok(&src, root)? {
            let cid = dget(e, "criterion_id")?;
            match by.iter_mut().find(|(k, _)| py_eq(k, &cid)) {
                Some((_, l)) => l.push(py_str(&res)),
                None => by.push((cid, vec![py_str(&res)])),
            }
        }
    }
    let got = |i: &Value| by.iter().find(|(k, _)| py_eq(k, i)).map(|(_, l)| l.clone()).unwrap_or_default();
    let join = |xs: &[Value]| xs.iter().map(py_str).collect::<Vec<_>>().join(", ");
    let missing: Vec<Value> = ids.iter().filter(|i| got(i).is_empty()).cloned().collect();
    if !missing.is_empty() {
        return Ok(result(
            NOT_EVALUATED,
            format!("registered evidence missing for criteria {}", join(&missing)),
            Some(("missing", missing)),
        ));
    }
    let failed: Vec<Value> = ids.iter().filter(|i| got(i).iter().any(|r| r == "NOT_MET")).cloned().collect();
    if !failed.is_empty() {
        return Ok(result(NO_GO, format!("criteria not met: {}", join(&failed)), Some(("not_met", failed))));
    }
    Ok(result(GO, "every owner-accepted criterion MET on registered evidence".into(), None))
}

fn uses_proposal(criteria: &Value, proposal: &str) -> AssessResult<bool> {
    let text = py_lower(&norm(&py_str(criteria)));
    let prop = py_lower(&norm(proposal));
    if text.contains(&py_lower(PROPOSAL_ID)) || text.contains("recorder_proposal") || text.contains("recorder proposal")
    {
        return Ok(true);
    }
    let items = items_of(criteria)?;
    for i in &items {
        let bad = match i {
            Value::Dict(_) => norm(&py_str(&text_of(i)?)).is_empty(),
            _ => true,
        };
        if bad {
            return Ok(true);
        }
    }
    for i in &items {
        if prop.contains(&py_lower(&norm(&py_str(&text_of(i)?)))) {
            return Ok(true);
        }
    }
    Ok(false)
}

/// `lock1_release_reportable(gates)`: every mandatory gate is GO (fail closed on an empty list).
pub fn lock1_release_reportable(gates: &Value) -> AssessResult<bool> {
    let list = match gates {
        Value::List(l) => l.clone(),
        Value::Null => vec![],
        other if !other.truthy() => vec![],
        other => {
            return Err(crate::error::AssessError::new("TypeError", format!("gates {} is not a list", py_repr(other))))
        }
    };
    let mut mandatory = Vec::new();
    for g in &list {
        let m = match g.as_dict().and_then(|d| d.get("mandatory")) {
            Some(v) => v.truthy(),
            None => {
                dget(g, "mandatory")?;
                true
            }
        };
        if m {
            mandatory.push(g);
        }
    }
    Ok(!mandatory.is_empty() && mandatory.iter().all(|g| eq_str(&dget(g, "status").unwrap_or(Value::Null), GO)))
}
