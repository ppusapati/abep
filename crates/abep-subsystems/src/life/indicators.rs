//! Life / material indicators of the selected architecture per block, with their evidence state (reference
//! `abep_sim/design/architecture_optimizer.py::life_material_indicators`, contract
//! `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-LIFE_MATERIAL_KERNEL/parity_prereg_v1.json`).
//!
//! No indicator is EVALUATED as life. Hall wall-erosion life needs an admitted Hall map with `wall_life_trustworthy`
//! (credible set EMPTY: NOT_EVALUATED); the anode / collector material is OPEN (P4 gate cells INCOMPLETE_EVIDENCE).
//! The parametric rotor stress branch (a design with a turbo tip speed) needs `rotor_strength.qualify_rotor`
//! (SC-WP-02), which is not admitted in Rust: it is refused as NOT_EVALUATED (registered divergence DIV-I01).

use crate::materials::pymath;
use abep_types::pyjson::{loads, py_eq, read_text_utf8, Dict, PyException, PyResult, Value};
use abep_types::EvalStatus;
use std::path::Path;

pub const P4_REL: &str = "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json";
pub const F3_REL: &str = "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json";
const NOT_EVALUATED: &str = "NOT_EVALUATED";
pub const UNLOCK_LIFE: &str =
    "Hall wall-erosion life (needs an admitted Hall map with wall_life_trustworthy) or a life \
                               test; anode / collector material with gate-admissible evidence (P4: all 352 gate cells \
                               INCOMPLETE_EVIDENCE); intake / plenum / filter AO compatibility (coupon programme, \
                               owner row 132)";
/// Class of the DIV-I01 refusal (status NOT_EVALUATED).
pub const NOT_EVALUATED_DEPENDENCY: &str = "NotEvaluatedDependency";
pub const ROTOR_REFUSAL: &str = "life_material_indicators: the rotor indicator needs rotor_strength.qualify_rotor \
                                 (SC-WP-02), which is not admitted in Rust; NOT_EVALUATED";

/// The fail-closed status of a refusal of this module.
pub fn refusal_status(e: &PyException) -> EvalStatus {
    if e.class == NOT_EVALUATED_DEPENDENCY {
        EvalStatus::NotEvaluated
    } else {
        EvalStatus::ModelError
    }
}

fn read_record(repo: &Path, rel: &str) -> PyResult<Value> {
    let p = repo.join(rel);
    let bytes = std::fs::read(&p).map_err(|_| {
        pymath::err("FileNotFoundError", format!("[Errno 2] No such file or directory: '{}'", p.display()))
    })?;
    loads(&read_text_utf8(&bytes)?)
}

/// `life_material_indicators(design, repo)`: reads the committed P4 and F3 records under `repo`.
pub fn life_material_indicators(design: &Value, repo: &Path) -> PyResult<Value> {
    let p4 = read_record(repo, P4_REL)?;
    let f3 = read_record(repo, F3_REL)?;
    life_material_indicators_from_records(design, &p4, &f3)
}

fn key_error(k: &str) -> PyException {
    pymath::err("KeyError", format!("'{k}'"))
}

fn item<'a>(v: &'a Value, k: &str) -> PyResult<&'a Value> {
    match v {
        Value::Dict(d) => d.get(k).ok_or_else(|| key_error(k)),
        Value::Str(_) => Err(pymath::err("TypeError", "string indices must be integers")),
        Value::List(_) => Err(pymath::err("TypeError", "list indices must be integers or slices, not str")),
        other => Err(pymath::err("TypeError", format!("'{}' object is not subscriptable", other.type_name()))),
    }
}

fn get<'a>(v: &'a Value, k: &str) -> PyResult<Option<&'a Value>> {
    match v {
        Value::Dict(d) => Ok(d.get(k)),
        other => Err(pymath::err("AttributeError", format!("'{}' object has no attribute 'get'", other.type_name()))),
    }
}

fn iterate(v: &Value) -> PyResult<Vec<Value>> {
    match v {
        Value::List(l) => Ok(l.clone()),
        Value::Dict(d) => Ok(d.keys().map(|k| Value::str(k.clone())).collect()),
        Value::Str(t) => Ok(t.chars().map(|c| Value::str(c.to_string())).collect()),
        other => Err(pymath::err("TypeError", format!("'{}' object is not iterable", other.type_name()))),
    }
}

fn indicator<const N: usize>(items: [(&str, Value); N]) -> Value {
    let mut d = Dict::new();
    for (k, v) in items {
        d.insert(k, v);
    }
    Value::Dict(d)
}

/// The same function on parsed P4 / F3 records (the reference reads them from the repository first).
pub fn life_material_indicators_from_records(design: &Value, p4: &Value, f3: &Value) -> PyResult<Value> {
    // par = {p["id"]: p for p in f3["parameters"]}: read for its refusals (the rotor branch alone uses it).
    for p in iterate(item(f3, "parameters")?)? {
        item(&p, "id")?;
    }
    match design {
        Value::Null => {}
        Value::Dict(d) => {
            if d.get("u_tip_turbo_mps").is_some_and(|v| !matches!(v, Value::Null)) {
                return Err(pymath::err(NOT_EVALUATED_DEPENDENCY, ROTOR_REFUSAL));
            }
        }
        other => {
            return Err(pymath::err("AttributeError", format!("'{}' object has no attribute 'get'", other.type_name())))
        }
    }
    let s = Value::str;
    let ne = || s(NOT_EVALUATED);
    let mut ind = vec![
        indicator([
            ("block", s("x_compressor")),
            (
                "indicator",
                s("rotor structural acceptance (registered basis only, A9.9 S2.3; the Ti-6Al-4V 827 MPa x 2.0 margin is \
                   the legacy PARAMETRIC_SENSITIVITY case)"),
            ),
            ("value", Value::Null),
            ("status", ne()),
        ]),
        indicator([
            ("block", s("x_compressor")),
            ("indicator", s("bearing / motor life")),
            ("value", Value::Null),
            ("status", ne()),
            ("unlock", s("compressor_downselect T-4 / life evidence")),
        ]),
        indicator([
            ("block", s("x_intake")),
            ("indicator", s("AO compatibility of the honeycomb wall / coating")),
            ("value", Value::Null),
            ("status", ne()),
            ("unlock", s("coating selection and AO coupon evidence (F1-P-03/04)")),
        ]),
        indicator([
            ("block", s("x_filter")),
            ("indicator", s("AO / material applicability")),
            ("value", Value::Null),
            ("status", ne()),
            ("unlock", s("F2 evidenced filter records (NO_ATOMIC_O surrogates never prove AO life, owner row 132)")),
        ]),
        indicator([
            ("block", s("x_plenum")),
            ("indicator", s("wall O recombination / material")),
            ("value", Value::Null),
            ("status", ne()),
            ("unlock", s("GP-D03 + coupon evidence (F4-P-06)")),
        ]),
    ];
    let final_status = item(p4, "final_material_status")?.clone();
    let mut fixed = Dict::new();
    let fs = item(p4, "fixed_statuses")?;
    let fsd = fs.as_dict().ok_or_else(|| {
        pymath::err("AttributeError", format!("'{}' object has no attribute 'items'", fs.type_name()))
    })?;
    for (k, v) in fsd.iter() {
        fixed.insert(k.clone(), item(v, "status")?.clone());
    }
    let gm = item(p4, "gate_matrix")?;
    let n_cells = match gm {
        Value::List(l) => l.len() as i64,
        Value::Dict(d) => d.len() as i64,
        Value::Str(t) => t.chars().count() as i64,
        other => return Err(pymath::err("TypeError", format!("object of type '{}' has no len()", other.type_name()))),
    };
    let mut n_incomplete = 0i64;
    for g in iterate(gm)? {
        let status = get(&g, "status")?.cloned().unwrap_or(Value::Null);
        let outcome = get(&g, "outcome")?.cloned().unwrap_or(status);
        if py_eq(&outcome, &s("INCOMPLETE_EVIDENCE")) {
            n_incomplete += 1;
        }
    }
    ind.push(indicator([
        ("block", s("x_Hall")),
        ("indicator", s("anode material")),
        ("value", final_status),
        ("status", ne()),
        ("fixed_statuses", Value::Dict(fixed)),
        ("gate_cells", Value::int(n_cells)),
        ("gate_cells_incomplete", Value::int(n_incomplete)),
    ]));
    ind.push(indicator([
        ("block", s("x_Hall")),
        ("indicator", s("wall erosion / firing life > 15,000 h (RVM-12)")),
        ("value", Value::Null),
        ("status", ne()),
        ("unlock", s(UNLOCK_LIFE)),
    ]));
    ind.push(indicator([
        ("block", s("x_ICP")),
        ("indicator", s("collector material")),
        ("value", s("OPEN")),
        ("status", ne()),
    ]));
    Ok(indicator([
        ("objective", s("life_material")),
        ("status", ne()),
        ("value", Value::Null),
        ("units", s("-")),
        ("evidence_class", Value::Null),
        ("source", Value::Null),
        (
            "reason",
            s("no life model or life evidence for any block; P4 gates all INCOMPLETE_EVIDENCE; the only number is a \
               parametric rotor stress margin"),
        ),
        ("unlock", Value::List(vec![s(UNLOCK_LIFE)])),
        ("indicators", Value::List(ind)),
    ]))
}
