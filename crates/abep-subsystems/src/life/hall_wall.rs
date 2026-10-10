//! The Hall-map wall-flux gate of the life chain (reference `abep_sim/thermal_life.py::hallmap_wall_inputs`, contract
//! `docs/rust_migration/contracts/C-ABEP_SIM_THERMAL_LIFE_PY-HALLMAP_WALL_INPUTS/parity_prereg_v1.json`).
//!
//! Hall wall erosion and lifetime use Hall-map wall ion flux / energy only from an ADMITTED transport-ensemble
//! member's map point that is performance-trustworthy AND `wall_life_trustworthy` (ion_wall_losses = true,
//! WallSheath, unshielded) and carries the pinned HallThruster.jl commit (CLAUDE.md next-work 5). The credible
//! transport set is EMPTY (2026-09-26), so this gate refuses every member id today and every Hall-erosion-derived life
//! is NOT_EVALUATED ([`hall_wall_life_input_status`]). The admission gate and the pin are the admitted `abep-hall`
//! ones.

use crate::materials::pymath;
use abep_hall::py::PyValue;
use abep_types::pyjson::{
    dumps, py_eq, py_repr, py_repr_str, py_strip, Dict, DumpOptions, PyException, PyResult, Value,
};
use abep_types::EvalStatus;
use std::path::Path;

pub const HALL_MAP_SCHEMA_REL: &str = "hallthruster_bridge/hall_map_schema_v1.json";
pub const HALLMAP_FIELDS_USED: [&str; 4] =
    ["discharge_power_W", "discharge_current_A", "wall_ion_flux_m2s", "wall_ion_energy_eV"];
pub const WALL_FLUX_INPUTS: [&str; 2] = ["wall_ion_flux_m2s", "wall_ion_energy_eV"];
pub const WALL_FLUX_PROVENANCE_KEY: &str = "wall_flux_provenance";
pub const PROV_ADMITTED_HALLMAP: &str = "admitted_hallmap";

/// Which transport ensemble the admission gate reads.
#[derive(Debug, Clone)]
pub enum Ensemble {
    /// The repository ensemble (`hallthruster_bridge/ensemble/transport_ensemble_v0.json`, validated load).
    Real,
    /// An explicit ensemble document (a registered SYNTHETIC fixture in tests; never evidence).
    Given(Value),
}

/// The caller's explicit statements (no defaults; CLAUDE.md rule 10).
#[derive(Debug, Clone)]
pub struct Statements {
    pub uncertainty: Value,
    pub applicability_domain: Value,
    pub validation_status: Value,
}

fn value_error(message: impl Into<String>) -> PyException {
    pymath::err("ValueError", message)
}

/// Refusals that mean "no admitted, wall-life-trustworthy Hall map": NOT_EVALUATED; every other refusal is
/// MODEL_ERROR.
pub fn refusal_status(e: &PyException) -> EvalStatus {
    let m = e.message.as_str();
    let not_admitted = m.contains("is a SCREENING candidate")
        || m.contains("is not an admitted transport-ensemble member")
        || m.contains("is not wall_life_trustworthy")
        || m.contains("HallMap query is not trustworthy")
        || m.contains("ion_wall_losses is not true");
    if e.class == "ValueError" && not_admitted {
        EvalStatus::NotEvaluated
    } else {
        EvalStatus::ModelError
    }
}

fn to_pyvalue(v: &Value) -> PyValue {
    match v {
        Value::Null => PyValue::None,
        Value::Bool(b) => PyValue::Bool(*b),
        Value::Int(i) => i.as_i64().map(|x| PyValue::Int(i128::from(x))).unwrap_or(PyValue::Float(f64::NAN)),
        Value::Float(x) => PyValue::Float(*x),
        Value::Str(s) => PyValue::Str(s.clone()),
        Value::List(l) => PyValue::List(l.iter().map(to_pyvalue).collect()),
        Value::Dict(d) => PyValue::Dict(d.iter().map(|(k, v)| (PyValue::Str(k.clone()), to_pyvalue(v))).collect()),
    }
}

fn require_admitted(repo: &Path, member_id: &str, ensemble: &Ensemble) -> PyResult<()> {
    let repo_s = repo.to_string_lossy();
    let e = match ensemble {
        Ensemble::Real => abep_hall::ensemble::load_ensemble(&repo_s, None),
        Ensemble::Given(v) => Ok(to_pyvalue(v)),
    }
    .map_err(|e| value_error(e.message))?;
    abep_hall::ensemble::require_admitted(member_id, &e).map_err(|e| match e.kind {
        abep_hall::Kind::Key => pymath::err("KeyError", e.message),
        abep_hall::Kind::Type => pymath::err("TypeError", e.message),
        _ => value_error(e.message),
    })
}

/// `load_hall_map_schema()` (the repository schema file).
pub fn load_hall_map_schema(repo: &Path) -> PyResult<Value> {
    let p = repo.join(HALL_MAP_SCHEMA_REL);
    let bytes = std::fs::read(&p).map_err(|_| {
        pymath::err("FileNotFoundError", format!("[Errno 2] No such file or directory: '{}'", p.display()))
    })?;
    let s = abep_types::pyjson::loads(&abep_types::pyjson::read_text_utf8(&bytes)?)?;
    let path = p.display().to_string();
    if !s.as_dict().and_then(|d| d.get("schema")).is_some_and(|v| py_eq(v, &Value::str("hall_map_schema_v1"))) {
        return Err(value_error(format!("{path} is not hall_map_schema_v1")));
    }
    let fields = s.as_dict().and_then(|d| d.get("fields")).ok_or_else(|| pymath::err("KeyError", "'fields'"))?;
    let missing: Vec<&str> =
        HALLMAP_FIELDS_USED.iter().copied().filter(|f| !fields.as_dict().is_some_and(|d| d.contains_key(f))).collect();
    if !missing.is_empty() {
        let items: Vec<Value> = missing.iter().map(|m| Value::str(*m)).collect();
        return Err(value_error(format!(
            "hall_map_schema_v1 no longer defines {}: thermal_life must be updated",
            py_repr(&Value::List(items))
        )));
    }
    Ok(s)
}

/// `_check_evidence(level, "model-derived", where)`: an integer 1-7 (docs/EVIDENCE.md).
fn check_evidence(level: &Value) -> PyResult<()> {
    let ok = matches!(level, Value::Int(i) if i.as_i64().is_some_and(|x| (1..=7).contains(&x)));
    if !ok {
        return Err(value_error(format!(
            "hallmap_wall_inputs: evidence_level must be an integer 1-7 (docs/EVIDENCE.md), got {}",
            py_repr(level)
        )));
    }
    Ok(())
}

fn subscript<'a>(v: &'a Value, k: &str) -> PyResult<&'a Value> {
    match v {
        Value::Dict(d) => d.get(k).ok_or_else(|| pymath::err("KeyError", py_repr_str(k))),
        Value::Str(_) => Err(pymath::err("TypeError", "string indices must be integers")),
        Value::List(_) => Err(pymath::err("TypeError", "list indices must be integers or slices, not str")),
        other => Err(pymath::err("TypeError", format!("'{}' object is not subscriptable", other.type_name()))),
    }
}

/// Python `float(v)` of a map-point value.
fn py_float(v: &Value) -> PyResult<f64> {
    match v {
        Value::Str(s) => crate::power::pyfmt::py_float_from_str(s)
            .ok_or_else(|| value_error(format!("could not convert string to float: {}", py_repr_str(s)))),
        Value::Int(_) | Value::Float(_) | Value::Bool(_) => v.to_f64(),
        other => Err(pymath::err(
            "TypeError",
            format!("float() argument must be a string or a real number, not '{}'", other.type_name()),
        )),
    }
}

/// `hallmap_wall_inputs(point, ensemble_member_id, evidence_level, map_meta=..., uncertainty=...,
/// applicability_domain=..., validation_status=..., schema=None)`: the hall_discharge input records of one Hall-map
/// query, refused unless the member is ADMITTED and the point is trustworthy and wall_life_trustworthy with the pinned
/// commit. `schema` `None` or falsy reads the repository schema.
#[allow(clippy::too_many_arguments)]
pub fn hallmap_wall_inputs(
    repo: &Path,
    ensemble: &Ensemble,
    point: &Value,
    ensemble_member_id: &str,
    evidence_level: &Value,
    map_meta: &Value,
    stmts: &Statements,
    schema: &Value,
) -> PyResult<Value> {
    if ensemble_member_id.is_empty() {
        return Err(value_error("a HallMap point must name its admitted ensemble member"));
    }
    check_evidence(evidence_level)?;
    require_admitted(repo, ensemble_member_id, ensemble)?;
    let schema = if schema.truthy() { schema.clone() } else { load_hall_map_schema(repo)? };
    let pget = |k: &str| -> PyResult<Value> {
        match point {
            Value::Dict(d) => Ok(d.get(k).cloned().unwrap_or(Value::Null)),
            other => {
                Err(pymath::err("AttributeError", format!("'{}' object has no attribute 'get'", other.type_name())))
            }
        }
    };
    if !matches!(pget("trustworthy")?, Value::Bool(true)) {
        return Err(value_error("HallMap query is not trustworthy (convergence, sustainment or chemistry validity)"));
    }
    if !matches!(pget("wall_life_trustworthy")?, Value::Bool(true)) {
        return Err(value_error("HallMap query is not wall_life_trustworthy: wall flux/energy are diagnostic only"));
    }
    let commit = pget("hallthruster_commit")?;
    let pinned =
        abep_hall::hall_map::pinned_commit(&repo.to_string_lossy(), None).map_err(|e| value_error(e.message))?;
    if !py_eq(&commit, &Value::str(pinned.clone())) {
        return Err(value_error(format!(
            "HallMap query commit {} is not the pinned HallThruster.jl commit",
            py_repr(&commit)
        )));
    }
    let meta = map_meta.as_dict().ok_or_else(|| value_error("map_meta must be the queried HallMap's meta dict"))?;
    let meta_id = meta.get("ensemble_member_id").cloned().unwrap_or(Value::Null);
    if !py_eq(&meta_id, &Value::str(ensemble_member_id)) {
        return Err(value_error(format!(
            "map meta ensemble_member_id {} is not {}: the point must be labelled with the member that produced its map",
            py_repr(&meta_id),
            py_repr_str(ensemble_member_id)
        )));
    }
    if !py_eq(&meta.get("hallthruster_commit").cloned().unwrap_or(Value::Null), &commit) {
        return Err(value_error("map meta hallthruster_commit differs from the query commit"));
    }
    if !matches!(meta.get("ion_wall_losses"), Some(Value::Bool(true))) {
        return Err(value_error("map meta ion_wall_losses is not true: wall flux/energy are diagnostic only"));
    }
    let named = [
        ("uncertainty", &stmts.uncertainty),
        ("applicability_domain", &stmts.applicability_domain),
        ("validation_status", &stmts.validation_status),
    ];
    for (k, v) in named {
        let ok = matches!(v, Value::Str(s) if !py_strip(s).is_empty());
        if !ok {
            return Err(value_error(format!("hallmap_wall_inputs: {k} must be an explicit non-empty statement")));
        }
    }
    let meta_sha = abep_provenance::sha256_hex(
        dumps(
            map_meta,
            &DumpOptions { separators: Some((",".into(), ":".into())), sort_keys: true, ..DumpOptions::default() },
        )?
        .as_bytes(),
    );
    let mut prov = Dict::new();
    prov.insert("kind", Value::str(PROV_ADMITTED_HALLMAP));
    prov.insert("ensemble_member_id", Value::str(ensemble_member_id));
    prov.insert("trustworthy", Value::Bool(true));
    prov.insert("wall_life_trustworthy", Value::Bool(true));
    prov.insert("hallthruster_commit", commit.clone());
    prov.insert("map_meta_sha256", Value::str(meta_sha));
    let mut out = Dict::new();
    for f in HALLMAP_FIELDS_USED {
        let pd = point.as_dict().expect("point.get succeeded, so point is a dict");
        let raw = pd.get(f).ok_or_else(|| value_error(format!("HallMap query lacks {}", py_repr_str(f))))?;
        let value = py_float(raw)?;
        let unit = subscript(subscript(subscript(&schema, "fields")?, f)?, "unit")?.clone();
        let mut r = Dict::new();
        r.insert("value", Value::Float(value));
        r.insert("unit", unit);
        r.insert(
            "source",
            Value::str(format!(
                "HallMap query, ensemble member {ensemble_member_id}, hall_map_schema_v1 field {f}, HallThruster.jl {pinned}"
            )),
        );
        r.insert("evidence_level", evidence_level.clone());
        r.insert("quantity_type", Value::str("model-derived"));
        for (k, v) in named {
            r.insert(k, v.clone());
        }
        if WALL_FLUX_INPUTS.contains(&f) {
            r.insert(WALL_FLUX_PROVENANCE_KEY, Value::Dict(prov.clone()));
        }
        out.insert(f, Value::Dict(r));
    }
    Ok(Value::Dict(out))
}

/// Status of any Hall wall-erosion-derived life input for `member_id` against the repository ensemble: EVALUATED
/// only when the member is admitted (the point gates follow in [`hallmap_wall_inputs`]). With the credible set EMPTY
/// every id is NOT_EVALUATED.
pub fn hall_wall_life_input_status(repo: &Path, member_id: &str) -> EvalStatus {
    if member_id.is_empty() {
        return EvalStatus::ModelError;
    }
    match require_admitted(repo, member_id, &Ensemble::Real) {
        Ok(()) => EvalStatus::Evaluated,
        Err(e) => refusal_status(&e),
    }
}
