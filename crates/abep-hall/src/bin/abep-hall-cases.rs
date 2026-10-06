//! `abep-hall-cases`: executes one registered step of contract C-HALL-MAP-ENSEMBLE-REGISTRY (JSON on stdin:
//! `{"repo": "<abs path>", "step": {...}}`, every path and placeholder already resolved by the harness) and prints its
//! outcome: `{"ok": value}` or `{"err": {"kind": ..., "message": ...}}`. Migration tooling of the parity campaign.

use abep_hall::py::{self, Dump, PyValue};
use abep_hall::registry::{self, RegistrationArgs};
use abep_hall::{ensemble, hall_map, schema, status, HallError, HallResult};
use std::io::Read;
use std::process::ExitCode;

fn outcome(r: HallResult<PyValue>) -> PyValue {
    match r {
        Ok(v) => py::dict([("ok", v)]),
        Err(e) => err_value(&e),
    }
}

fn err_value(e: &HallError) -> PyValue {
    py::dict([("err", py::dict([("kind", py::s(e.kind.name())), ("message", py::s(e.message.as_str()))]))])
}

fn arg<'a>(step: &'a PyValue, k: &str) -> &'a PyValue {
    static NONE: PyValue = PyValue::None;
    py::get(step, k).ok().flatten().unwrap_or(&NONE)
}

fn opt_str(v: &PyValue) -> Option<&str> {
    py::as_str(v)
}

fn need_str<'a>(step: &'a PyValue, k: &str) -> HallResult<&'a str> {
    opt_str(arg(step, k)).ok_or_else(|| HallError::type_error(format!("step argument {k} is not a string")))
}

fn sorted_ids(v: Vec<PyValue>) -> HallResult<PyValue> {
    Ok(PyValue::List(py::sorted(v)?))
}

/// Override document of a registry / map step: null, {"raw": path} or {"file": path} (json.load, unvalidated).
fn raw_override(v: &PyValue) -> HallResult<Option<PyValue>> {
    for k in ["raw", "file"] {
        if let Some(PyValue::Str(p)) = py::get(v, k).ok().flatten() {
            return py::load_json_file(p).map(Some);
        }
    }
    Ok(None)
}

fn query_value(v: &PyValue) -> HallResult<f64> {
    match v {
        PyValue::Int(i) => Ok(*i as f64),
        PyValue::Float(f) => Ok(*f),
        PyValue::Bool(b) => Ok(f64::from(u8::from(*b))),
        PyValue::Str(s) if s == "nan" => Ok(f64::NAN),
        PyValue::Str(s) if s == "inf" => Ok(f64::INFINITY),
        PyValue::Str(s) if s == "-inf" => Ok(f64::NEG_INFINITY),
        other => Err(HallError::type_error(format!("query value {} (DIV-04)", py::repr(other)))),
    }
}

fn hallmap(repo: &str, step: &PyValue) -> HallResult<PyValue> {
    let ens = raw_override(arg(step, "ensemble"))?;
    let m = hall_map::HallMap::load(repo, need_str(step, "path")?, opt_str(arg(step, "bridge_dir")), ens.as_ref())?;
    let mut queries = Vec::new();
    for q in py::iterate(arg(step, "queries"))? {
        let PyValue::Dict(entries) = &q else { return Err(HallError::type_error("query is not an object")) };
        let mut pairs = Vec::new();
        for (k, v) in entries {
            pairs.push((py::py_str(k), query_value(v)?));
        }
        queries.push(outcome(m.query(&pairs).map(|out| {
            PyValue::List(out.into_iter().map(|(k, v)| PyValue::List(vec![py::s(k), v.to_py()])).collect())
        })));
    }
    Ok(py::dict([
        ("names", py::list_of_strs(&m.names)),
        ("shape", PyValue::List(m.shape.iter().map(|n| PyValue::Int(*n as i128)).collect())),
        ("queries", PyValue::List(queries)),
    ]))
}

fn require_admitted(repo: &str, step: &PyValue) -> HallResult<PyValue> {
    let e = arg(step, "ensemble");
    let doc = match py::get(e, "loaded").ok().flatten() {
        Some(PyValue::Str(p)) => ensemble::load_ensemble(repo, Some(p))?,
        _ => match raw_override(e)? {
            Some(d) => d,
            None => ensemble::load_ensemble(repo, None)?,
        },
    };
    ensemble::require_admitted(need_str(step, "member_id")?, &doc)?;
    Ok(PyValue::None)
}

fn run(repo: &str, step: &PyValue) -> HallResult<PyValue> {
    let op = need_str(step, "op")?;
    let ens = || raw_override(arg(step, "ensemble"));
    match op {
        "required_fields" => {
            let s = schema::repo_schema(repo)?;
            Ok(py::dict([("fields", py::list_of_strs(&s.fields)), ("meta", py::list_of_strs(&s.meta))]))
        }
        "missing_fields" => {
            let s = schema::repo_schema(repo)?;
            Ok(py::list_of_strs(&schema::missing_fields(&s, arg(step, "record"))?))
        }
        "pinned_commit" => Ok(py::s(hall_map::pinned_commit(repo, opt_str(arg(step, "bridge_dir")))?)),
        "load_schema_v2" => registry::load_hall_map_schema_v2(need_str(step, "root")?, None),
        "hallmap" => hallmap(repo, step),
        "load_ensemble" => {
            let e = ensemble::load_ensemble(repo, opt_str(arg(step, "path")))?;
            Ok(py::dict([
                ("member_ids", sorted_ids(ensemble::member_ids(&e)?)?),
                ("screening_ids", sorted_ids(ensemble::screening_ids(&e)?)?),
            ]))
        }
        "require_admitted" => require_admitted(repo, step),
        "hall_response_status" => status::hall_response_status(need_str(step, "repo")?),
        "register" => {
            let e = ens()?;
            let sha = registry::register(
                need_str(step, "registry")?,
                need_str(step, "root")?,
                &RegistrationArgs(arg(step, "kw").clone()),
                e.as_ref(),
            )?;
            Ok(py::s(sha))
        }
        "withdraw" => {
            let e = ens()?;
            let sha = registry::withdraw(
                need_str(step, "registry")?,
                need_str(step, "root")?,
                need_str(step, "record_sha256")?,
                arg(step, "reason"),
                arg(step, "decision_file"),
                arg(step, "registered_by"),
                arg(step, "registered_utc"),
                e.as_ref(),
            )?;
            Ok(py::s(sha))
        }
        "verify" => {
            let e = ens()?;
            registry::verify(need_str(step, "registry")?, need_str(step, "root")?, e.as_ref())
        }
        "lookup_map_meta" => {
            let e = ens()?;
            registry::lookup_map_meta(
                need_str(step, "registry")?,
                need_str(step, "root")?,
                arg(step, "map_meta_sha256"),
                e.as_ref(),
            )
        }
        "build_registration" => {
            let seq = match arg(step, "seq") {
                PyValue::Int(i) => *i,
                _ => 1,
            };
            registry::build_registration(
                need_str(step, "root")?,
                &RegistrationArgs(arg(step, "kw").clone()),
                seq,
                arg(step, "prev_record_sha256").clone(),
            )
        }
        "validate_record" => registry::validate_record(arg(step, "record")).map(|()| PyValue::None),
        "read_records" => Ok(PyValue::List(
            registry::read_records(need_str(step, "registry")?)?
                .into_iter()
                .map(|(n, s, r)| PyValue::List(vec![py::s(n), py::s(s), r]))
                .collect(),
        )),
        "canonical_json_sha256" => Ok(py::s(registry::canonical_json_sha256(arg(step, "value")))),
        "sha256_canonical_jsonl" => Ok(py::s(registry::sha256_canonical_jsonl(need_str(step, "path")?)?)),
        other => Err(HallError::type_error(format!("unknown step op {other:?}"))),
    }
}

fn main() -> ExitCode {
    let mut input = String::new();
    if std::io::stdin().read_to_string(&mut input).is_err() {
        eprintln!("abep-hall-cases: cannot read stdin");
        return ExitCode::from(2);
    }
    let request = match py::load_json_bytes(input.as_bytes()) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("abep-hall-cases: bad request: {e}");
            return ExitCode::from(2);
        }
    };
    let Some(repo) = py::get(&request, "repo").ok().flatten().and_then(py::as_str).map(str::to_string) else {
        eprintln!("abep-hall-cases: request has no repo");
        return ExitCode::from(2);
    };
    let step = arg(&request, "step").clone();
    println!("{}", py::dumps(&outcome(run(&repo, &step)), &Dump::DEFAULT));
    ExitCode::SUCCESS
}
