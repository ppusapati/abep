//! Harness interface of the mass lane (`abep-mass eval <calls.json>`): one JSON call list in, one result per call out
//! ({outcome: RETURNED, value} or {outcome: RAISED, class, message}), with the Python keyword defaults of each entry
//! point. Used by `scripts/rust_migration/parity_mass_v1.py` and by the captured-reference replay tests.

use super::py::{self, err, f, s};
use super::{rules, v5, wet_mass, xe};
use abep_provenance::sha256_hex;
use abep_types::pyjson::{self, PyException, PyResult, Value};
use std::path::Path;

fn arg(args: &Value, name: &str, default: Option<Value>) -> PyResult<Value> {
    match py::get(args, name)? {
        Some(v) => Ok(v.clone()),
        None => default.ok_or_else(|| err("TypeError", format!("missing required argument: '{name}'"))),
    }
}

fn req(args: &Value, name: &str) -> PyResult<Value> {
    arg(args, name, None)
}

fn opt(args: &Value, name: &str) -> PyResult<Value> {
    arg(args, name, Some(Value::Null))
}

fn list_arg(args: &Value, name: &str) -> PyResult<Vec<Value>> {
    py::iter(&req(args, name)?)
}

fn split_arg(args: &Value) -> PyResult<rules::XeSplit> {
    let mut pairs = Vec::new();
    for p in list_arg(args, "xe_split")? {
        let kv = py::iter(&p)?;
        if kv.len() != 2 {
            return Err(err("ValueError", "xe_split entries are [case_kg, {loaded_kg, residual_kg}] pairs"));
        }
        pairs.push((kv[0].clone(), kv[1].clone()));
    }
    Ok(py::dict_pairs(pairs))
}

fn refs_arg(args: &Value) -> PyResult<rules::Refs> {
    let mut out = Vec::new();
    for r in list_arg(args, "refs")? {
        let t = py::iter(&r)?;
        if t.len() != 3 {
            return Err(err("ValueError", "refs entries are [name, reference_kg, strict] triples"));
        }
        out.push((t[0].clone(), t[1].clone(), t[2].clone()));
    }
    Ok(out)
}

fn repo_arg(args: &Value) -> PyResult<std::path::PathBuf> {
    match req(args, "repo")? {
        Value::Str(p) => Ok(Path::new(&p).to_path_buf()),
        _ => Err(err("TypeError", "repo must be a path string")),
    }
}

/// Evaluate one call.
pub fn call(name: &str, args: &Value) -> PyResult<Value> {
    match name {
        "rk" => rules::rk(&req(args, "x")?),
        "line_mev_value" => rules::line_mev_value(
            &opt(args, "allocation_kg")?,
            &opt(args, "cbe_kg")?,
            &opt(args, "floor_cbe_kg")?,
            &arg(args, "equipment_margin", Some(f(rules::EQUIPMENT_MARGIN)))?,
        ),
        "system_margin" => rules::system_margin(
            &req(args, "pre_margin_kg")?,
            &arg(args, "fraction", Some(f(rules::SYSTEM_MARGIN)))?,
            &arg(args, "reserve_kg", Some(f(0.0)))?,
        ),
        "system_margin_bid" => rules::system_margin_bid(
            &req(args, "pre_margin_kg")?,
            &arg(args, "fraction", Some(f(rules::SYSTEM_MARGIN_BID)))?,
            &arg(args, "reserve_kg", Some(f(0.0)))?,
        ),
        "harness_row60" => Ok(f(rules::harness_row60(
            &req(args, "other_nominal_kg")?,
            &arg(args, "fraction", Some(f(rules::HARNESS_FRACTION)))?,
        )?)),
        "closure_state" => Ok(s(rules::closure_state(
            &req(args, "known_kg")?,
            &req(args, "reference_kg")?,
            &req(args, "strict")?,
            &req(args, "all_resolved")?,
        )?)),
        "_unresolved" => Ok(Value::List(rules::unresolved(&req(args, "rec")?)?)),
        "assert_no_margin_relaxation" => {
            rules::assert_no_margin_relaxation(&req(args, "reading")?).map(|_| Value::Null)
        }
        "assert_bid_margin_reading" => rules::assert_bid_margin_reading(&req(args, "reading")?).map(|_| Value::Null),
        "rollup" => rules::rollup(&req(args, "cfg")?, &list_arg(args, "lines")?, &split_arg(args)?, &refs_arg(args)?),
        "rollup_v5" => v5::rollup_v5(
            &req(args, "cfg")?,
            &list_arg(args, "lines")?,
            &split_arg(args)?,
            &refs_arg(args)?,
            &req(args, "fraction")?,
        ),
        "unresolved_v5" => Ok(Value::List(v5::unresolved_v5(&req(args, "rec")?)?)),
        "set_al09" => v5::set_al09(&req(args, "line")?),
        "a9_26_message2" => v5::a9_26_message2(&repo_arg(args)?),
        "build_doc_v5" => {
            let (js, md) = v5::render(&repo_arg(args)?)?;
            Ok(py::dict(vec![
                ("json_sha256", s(sha256_hex(js.as_bytes()))),
                ("md_sha256", s(sha256_hex(md.as_bytes()))),
            ]))
        }
        "wet_mass" => wet_mass::wet_mass(
            &repo_arg(args)?,
            &req(args, "config")?,
            &opt(args, "design_masses")?,
            &opt(args, "supplied")?,
        ),
        "wet_mass_pinned" => wet_mass::wet_mass_pinned(
            &repo_arg(args)?,
            &req(args, "config")?,
            &opt(args, "design_masses")?,
            &opt(args, "supplied")?,
        ),
        "case_split_loaded" => xe::case_split_loaded(
            &req(args, "case_kg")?,
            &req(args, "f_reserve")?,
            &req(args, "f_residual")?,
            &arg(args, "reading", Some(s(xe::CASE_READING)))?,
        ),
        "ignition_booking_s" => Ok(f(xe::ignition_booking_s(
            &arg(args, "attempts", Some(Value::int(xe::IGN_ATTEMPTS_MAX)))?,
            &arg(args, "dwell_s", Some(f(xe::IGN_DWELL_CAP_S)))?,
            &opt(args, "evidence")?,
        )?)),
        "book_reserve_and_residual" => xe::book_reserve_and_residual(
            &list_arg(args, "evals")?,
            &req(args, "lines")?,
            &req(args, "f_reserve")?,
            &req(args, "f_residual")?,
        ),
        "ground_supply" => xe::ground_supply(
            &req(args, "calculated_kg")?,
            &req(args, "procedures_kg")?,
            &arg(args, "margin", Some(f(xe::GROUND_LOGISTICS_MARGIN)))?,
        ),
        "eval_line" => xe::eval_line(&req(args, "ln")?, &req(args, "items")?, &req(args, "done")?),
        "evaluate" => xe::evaluate(&list_arg(args, "lines")?, &req(args, "items")?, &list_arg(args, "scenarios")?),
        other => Err(err("NotImplementedError", format!("unknown entry point {other:?}"))),
    }
}

fn outcome(r: PyResult<Value>) -> Value {
    match r {
        Ok(v) => py::dict(vec![("outcome", s("RETURNED")), ("value", v)]),
        Err(PyException { class, message }) => {
            py::dict(vec![("outcome", s("RAISED")), ("class", s(class)), ("message", s(message))])
        }
    }
}

/// Evaluate a call list `[{fn, args}, ...]`.
pub fn eval_calls(calls: &Value) -> PyResult<Value> {
    let mut out = Vec::new();
    for c in py::iter(calls)? {
        let name = match py::gi(&c, "fn")? {
            Value::Str(n) => n.clone(),
            _ => return Err(err("TypeError", "call 'fn' must be a str")),
        };
        let args = py::get(&c, "args")?.cloned().unwrap_or_else(|| py::dict(vec![]));
        out.push(outcome(call(&name, &args)));
    }
    Ok(Value::List(out))
}

/// The call list evaluated twice; a difference is a determinism failure (INV-K01 / INV-V05 / INV-X01).
pub fn eval_calls_twice(calls: &Value) -> PyResult<(Value, bool)> {
    let a = eval_calls(calls)?;
    let b = eval_calls(calls)?;
    let same = pyjson::dumps(&a, &Default::default())? == pyjson::dumps(&b, &Default::default())?;
    Ok((a, same))
}
