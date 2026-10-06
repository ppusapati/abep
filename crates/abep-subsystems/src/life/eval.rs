//! JSON call interface of the SC-WP-08 parity harness (`examples/life_eval.rs`): one call `{"fn": name, "args":
//! {...}}` in, one outcome `{"outcome": "RETURNED", "value": v}` or `{"outcome": "RAISED", "class": c, "message": m}`
//! out, with the argument encodings registered in the seven SC-WP-08 contracts. A call outside them is answered with
//! class `HarnessError` (never a value).

use super::{ao_register, hall_wall, indicators, p4};
use crate::materials::pymath::{self, Num};
use crate::materials::{aochem, db, sputter};
use abep_types::pyjson::{Dict, PyException, PyResult, Value};
use std::path::Path;

fn harness(m: impl Into<String>) -> PyException {
    pymath::err("HarnessError", m)
}

fn arg<'a>(a: &'a Dict, k: &str) -> &'a Value {
    static NONE: Value = Value::Null;
    a.get(k).unwrap_or(&NONE)
}

fn dict_arg<'a>(a: &'a Dict, k: &str) -> PyResult<&'a Dict> {
    arg(a, k).as_dict().ok_or_else(|| harness(format!("argument {k} must be an object")))
}

fn number(a: &Dict, k: &str, default: Option<f64>) -> PyResult<f64> {
    match (a.get(k), default) {
        (None, Some(d)) => Ok(d),
        (None, None) => Err(harness(format!("argument {k} missing"))),
        (Some(v), _) => Ok(Num::from_value(v, k)?.f()),
    }
}

fn num_arg(a: &Dict, k: &str, default: Option<Num>) -> PyResult<Num> {
    match (a.get(k), default) {
        (None, Some(d)) => Ok(d),
        (None, None) => Err(harness(format!("argument {k} missing"))),
        (Some(v), _) => Num::from_value(v, k),
    }
}

fn ao_params(a: &Dict) -> PyResult<aochem::AoParams> {
    match a.get("ao") {
        None | Some(Value::Null) => Ok(aochem::AoParams::default()),
        Some(Value::Dict(d)) => match d.get("fields") {
            Some(Value::Dict(f)) => aochem::AoParams::from_fields(f),
            _ => Err(harness("ao must be {'fields': {...}}")),
        },
        _ => Err(harness("ao must be {'fields': {...}}")),
    }
}

fn material(a: &Dict) -> PyResult<db::Material> {
    let m = dict_arg(a, "material")?;
    if let Some(name) = m.get("name") {
        return db::lookup(name).cloned();
    }
    match m.get("fields") {
        Some(Value::Dict(f)) => db::Material::from_fields(f),
        _ => Err(harness("material must be {'name': n} or {'fields': {...}}")),
    }
}

fn list_arg(a: &Dict, k: &str) -> PyResult<Vec<Value>> {
    match arg(a, k) {
        Value::Null => Ok(Vec::new()),
        Value::List(l) => Ok(l.clone()),
        _ => Err(harness(format!("argument {k} must be a list or null"))),
    }
}

fn text_arg(a: &Dict, k: &str) -> PyResult<String> {
    arg(a, k).as_str().map(str::to_string).ok_or_else(|| harness(format!("argument {k} must be a string")))
}

/// Apply a registered patch `[[path, value], ...]` (path of dict keys / list indices; value `{"$delete": true}`
/// deletes) to a committed record (harness transport of the mutated records; Python applies the same list).
fn apply_patch(mut v: Value, patch: &Value) -> PyResult<Value> {
    let ops = patch.as_list().ok_or_else(|| harness("$patch must be a list"))?;
    for op in ops {
        let (path, val) = match op.as_list() {
            Some([p, x]) => (p.as_list().ok_or_else(|| harness("patch path must be a list"))?, x),
            _ => return Err(harness("a patch op is [path, value]")),
        };
        let (last, parents) = path.split_last().ok_or_else(|| harness("empty patch path"))?;
        let mut cur = &mut v;
        for k in parents {
            cur = match (cur, k) {
                (Value::Dict(d), Value::Str(s)) => d.get_mut(s).ok_or_else(|| harness("patch path"))?,
                (Value::List(l), Value::Int(i)) => {
                    l.get_mut(i.as_i64().unwrap_or(-1) as usize).ok_or_else(|| harness("patch path"))?
                }
                _ => return Err(harness("patch path")),
            };
        }
        let delete = val.as_dict().is_some_and(|d| d.get("$delete").is_some());
        match (cur, last) {
            (Value::Dict(d), Value::Str(s)) => {
                if delete {
                    d.remove(s);
                } else {
                    d.insert(s.clone(), val.clone());
                }
            }
            (Value::List(l), Value::Int(i)) => {
                let i = i.as_i64().unwrap_or(-1) as usize;
                if i >= l.len() {
                    return Err(harness("patch index"));
                }
                if delete {
                    l.remove(i);
                } else {
                    l[i] = val.clone();
                }
            }
            _ => return Err(harness("patch target")),
        }
    }
    Ok(v)
}

/// A committed repository JSON record, optionally patched: `{"$committed": rel, "$patch": [...]}`.
fn committed(spec: &Dict, root: &Path) -> PyResult<Value> {
    let rel = spec.get("$committed").and_then(Value::as_str).ok_or_else(|| harness("$committed rel"))?;
    let bytes = std::fs::read(root.join(rel)).map_err(|e| harness(format!("{rel}: {e}")))?;
    let v = abep_types::pyjson::loads(&abep_types::pyjson::read_text_utf8(&bytes)?)?;
    match spec.get("$patch") {
        None => Ok(v),
        Some(p) => apply_patch(v, p),
    }
}

fn call(name: &str, a: &Dict, root: &Path) -> PyResult<Value> {
    match name {
        "aochem.tables" => Ok(aochem::tables()),
        "aochem.ao_flux" => aochem::ao_flux(dict_arg(a, "atm")?),
        "aochem.fluence" => Ok(Value::Float(aochem::fluence(dict_arg(a, "atm")?, number(a, "hours", None)?)?)),
        "aochem.erosion_depth_um" => Ok(Value::Float(aochem::erosion_depth_um(
            arg(a, "material"),
            number(a, "fl_atoms_m2", None)?,
            number(a, "exposure_factor", Some(1.0))?,
        )?)),
        "aochem.recombination_fraction" => Ok(Value::Float(aochem::recombination_fraction(&ao_params(a)?)?)),
        "aochem.inlet_composition" => aochem::inlet_composition(dict_arg(a, "atm")?, &ao_params(a)?),
        "aochem.material_report" => aochem::material_report(
            dict_arg(a, "atm")?,
            number(a, "hours", None)?,
            &list_arg(a, "materials")?,
            number(a, "exposure_factor", Some(1.0))?,
        ),
        "materials.db" => Ok(Value::List(db::db().iter().map(db::Material::to_value).collect())),
        "materials.record" => Ok(db::Material::from_fields(dict_arg(a, "fields")?)?.to_value()),
        "materials.gamma_O" => Ok(Value::Float(material(a)?.gamma_o(num_arg(a, "T_K", None)?)?)),
        "materials.sputter_yield" => Ok(Value::Float(material(a)?.sputter_yield(num_arg(a, "E_eV", None)?)?)),
        "materials.see_yield" => Ok(Value::Float(material(a)?.see_yield(num_arg(a, "E_eV", None)?)?)),
        "materials.surface_ageing_alpha" => Ok(Value::Float(db::surface_ageing_alpha(
            num_arg(a, "alpha0", None)?,
            num_arg(a, "fluence_atoms_m2", None)?,
            num_arg(a, "phi_c", Some(Num::Float(1.0e26)))?,
            num_arg(a, "alpha_inf", Some(Num::Float(0.95)))?,
        )?)),
        "sputter.yamamura_tawara" => {
            let v = list_arg(a, "args")?;
            if v.len() != 9 {
                return Err(harness("yamamura_tawara takes 9 arguments"));
            }
            sputter::yamamura_tawara(&v[0], &v[1], &v[2], &v[3], &v[4], &v[5], &v[6], &v[7], &v[8])
        }
        "sputter.apid_fit" => {
            let v = list_arg(a, "args")?;
            if v.len() != 6 {
                return Err(harness("apid_fit takes 6 arguments"));
            }
            Ok(Value::Float(sputter::apid_fit(&v[0], &v[1], &v[2], &v[3], &v[4], &v[5])?))
        }
        "aoreg.environment" => {
            let alts = list_arg(a, "altitudes")?
                .iter()
                .map(|v| match v {
                    Value::Int(i) => i.as_i64().map(ao_register::Altitude::Int).ok_or_else(|| harness("altitude")),
                    Value::Float(x) => Ok(ao_register::Altitude::Float(*x)),
                    _ => Err(harness("altitudes must be numbers")),
                })
                .collect::<PyResult<Vec<_>>>()?;
            ao_register::compute_ao_environment(root, &text_arg(a, "csv_sha256")?, &alts)
        }
        "aoreg.index" => {
            let text = match (arg(a, "db_text"), a.get("db_patch")) {
                (Value::Str(t), None) => Some(t.as_bytes().to_vec()),
                (Value::Null, None) => None,
                (Value::Null, Some(p)) => {
                    let mut spec = Dict::new();
                    spec.insert("$committed", Value::str(ao_register::WALL_LIFE_DB_REL));
                    spec.insert("$patch", p.clone());
                    let v = committed(&spec, root)?;
                    let opts = abep_types::pyjson::DumpOptions {
                        indent: Some(1),
                        ensure_ascii: false,
                        ..abep_types::pyjson::DumpOptions::default()
                    };
                    Some(abep_types::pyjson::dumps(&v, &opts)?.into_bytes())
                }
                _ => return Err(harness("db_text / db_patch")),
            };
            ao_register::compute_wall_sputter_index(
                root,
                &text_arg(a, "db_rel")?,
                &text_arg(a, "db_sha256")?,
                text.as_deref(),
            )
        }
        "p4.evaluate_gate" => p4::evaluate_gate(
            arg(a, "req"),
            arg(a, "prop"),
            arg(a, "thermal_closure_status"),
            arg(a, "operating_temperature"),
        ),
        "p4.candidate_screening_state" => Ok(Value::str(p4::candidate_screening_state(&list_arg(a, "outcomes")?)?)),
        "p4.final_material_status" => Ok(Value::str(p4::final_material_status(arg(a, "states")))),
        "p4.requirement_evidenced" => Ok(Value::Bool(p4::requirement_evidenced(arg(a, "req"))?)),
        "p4.property_evidenced" => Ok(Value::Bool(p4::property_evidenced(arg(a, "prop"))?)),
        "indicators.life_material" => match arg(a, "records") {
            Value::Str(s) if s == "REPO" => indicators::life_material_indicators(arg(a, "design"), root),
            Value::Dict(r) => {
                let absent = |k: &str, rel: &str| -> PyResult<Value> {
                    match r.get(k) {
                        None | Some(Value::Null) => Err(pymath::err(
                            "FileNotFoundError",
                            format!("[Errno 2] No such file or directory: '{rel}'"),
                        )),
                        Some(Value::Dict(spec)) if spec.contains_key("$committed") => committed(spec, root),
                        Some(v) => Ok(v.clone()),
                    }
                };
                let p4v = absent("p4", indicators::P4_REL)?;
                let f3v = absent("f3", indicators::F3_REL)?;
                indicators::life_material_indicators_from_records(arg(a, "design"), &p4v, &f3v)
            }
            _ => Err(harness("records must be 'REPO' or {p4, f3}")),
        },
        "hallwall.hallmap_wall_inputs" => {
            let ensemble = match arg(a, "ensemble") {
                Value::Str(s) if s == "REAL" => hall_wall::Ensemble::Real,
                v @ Value::Dict(_) => hall_wall::Ensemble::Given(v.clone()),
                _ => return Err(harness("ensemble must be 'REAL' or an ensemble object")),
            };
            let stmts = hall_wall::Statements {
                uncertainty: arg(a, "uncertainty").clone(),
                applicability_domain: arg(a, "applicability_domain").clone(),
                validation_status: arg(a, "validation_status").clone(),
            };
            hall_wall::hallmap_wall_inputs(
                root,
                &ensemble,
                arg(a, "point"),
                &text_arg(a, "member_id")?,
                arg(a, "evidence_level"),
                arg(a, "map_meta"),
                &stmts,
                arg(a, "schema"),
            )
        }
        other => Err(harness(format!("unknown function {other}"))),
    }
}

/// Evaluate one harness call against the repository at `root`.
pub fn eval_call(c: &Value, root: &Path) -> Value {
    let mut out = Dict::new();
    let res = match c.as_dict() {
        Some(d) => match (d.get("fn").and_then(Value::as_str), d.get("args").and_then(Value::as_dict)) {
            (Some(name), Some(a)) => call(name, a, root),
            _ => Err(harness("a call is {'fn': name, 'args': {...}}")),
        },
        None => Err(harness("a call is {'fn': name, 'args': {...}}")),
    };
    match res {
        Ok(v) => {
            out.insert("outcome", Value::str("RETURNED"));
            out.insert("value", v);
        }
        Err(e) => {
            out.insert("outcome", Value::str("RAISED"));
            out.insert("class", Value::str(e.class));
            out.insert("message", Value::str(e.message));
        }
    }
    Value::Dict(out)
}
