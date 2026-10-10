//! The F7 / F8 wet-mass objective `m_wet_kg`: Rust port of `abep_sim/design/architecture_optimizer.py::wet_mass`
//! (with `_obj`, `supplied_objective` and `intake_synthesis.require_f1q02_label`, which it calls). Contract
//! `docs/rust_migration/contracts/C-DOCS_BUDGETS_MASS_POWER_A9_V5/` (entry point E7).
//!
//! Fail closed: the objective is NOT_EVALUATED while no CBE or measured mass exists for any BOM line (it reports the
//! HARD_40_WET roll-up states of the record, never a compliance verdict); a supplied roll-up becomes EVALUATED only when
//! it is closed (all_terms_resolved) and of a rankable evidence class. Allocation, evidence floor, design-parametric
//! value and CBE stay in separate columns.

use super::py::{self, dict, err, f, list, s};
use super::v5::{RECORD_REL, RECORD_SHA256};
use abep_provenance::sha256_hex;
use abep_types::pyjson::{py_eq, py_repr, py_str, PyResult, Value};
use std::path::Path;

pub const EVALUATED: &str = "EVALUATED";
pub const PARAMETRIC_ONLY: &str = "PARAMETRIC_SENSITIVITY_ONLY";
pub const INCOMPLETE: &str = "INCOMPLETE_EVIDENCE";
pub const NOT_EVALUATED: &str = "NOT_EVALUATED";
pub const SYNTHETIC_ONLY: &str = "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE";
pub const SYN_CLASS: &str = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE";
pub const RANKABLE_CLASSES: [&str; 5] = ["measured", "digitized", "inferred", "reconstructed", "model-derived"];
pub const UNLOCK_M_WET: &str = "a CBE or measured mass for every mass/power v3 BOM line (no CBE exists) plus the Xe \
                                load case (XA9Q-01 / MQ-09) and the MQ-01 margin reading decided by the owner";
/// intake_synthesis F1Q-02 label (A9.13 S6.1): an intake structural mass is a budgeting sensitivity only.
pub const INTAKE_MASS_LINE: &str = "AL-01";
pub const F1Q02_LABEL: &str = "PARAMETRIC_SENSITIVITY";
pub const F1Q02_USE: &str = "BUDGETING_ONLY";
pub const F1Q02_LOCK1: &str = "SOURCED_STRUCTURAL_DEFINITION_REQUIRED_BEFORE_LOCK_1";

/// `_obj(name, status, value, units, evidence_class, source, reason, unlock, **extra)`.
fn obj(
    status: &str,
    value: Value,
    evidence_class: Value,
    source: Value,
    reason: Value,
    unlock: Value,
) -> Vec<(&'static str, Value)> {
    vec![
        ("objective", s("m_wet_kg")),
        ("status", s(status)),
        ("value", value),
        ("units", s("kg")),
        ("evidence_class", evidence_class),
        ("source", source),
        ("reason", reason),
        ("unlock", unlock),
    ]
}

/// `intake_synthesis.require_f1q02_label(rec)`.
pub fn require_f1q02_label(rec: &Value) -> PyResult<()> {
    let lab = match rec {
        Value::Dict(d) => d.get("f1q02").cloned().unwrap_or(Value::Null),
        _ => Value::Null,
    };
    let refused = !lab.truthy() || {
        let l = py::get_or_none(&lab, "label")?;
        let u = py::get_or_none(&lab, "use")?;
        let c = py::get_or_none(&lab, "lock1_condition")?;
        !py::eq_str(&l, F1Q02_LABEL) || !py::eq_str(&u, F1Q02_USE) || !py::eq_str(&c, F1Q02_LOCK1)
    };
    if refused {
        return Err(err(
            "IntakeMassUseError",
            "intake structural mass without the F1Q-02 PARAMETRIC_SENSITIVITY / BUDGETING_ONLY label (never a CBE, \
             frozen intake mass or structural qualification)",
        ));
    }
    Ok(())
}

/// `supplied_objective("m_wet_kg", rec, "kg")`.
fn supplied_objective(rec: &Value) -> PyResult<Value> {
    for k in ["value", "evidence_class", "source"] {
        if !py::as_dict(rec)?.contains_key(k) {
            return Err(err("OptimizerError", format!("supplied m_wet_kg: '{k}' missing")));
        }
    }
    let v = py::gi(rec, "value")?;
    let finite = py::is_real(v) && v.to_f64()?.is_finite();
    if !finite {
        return Err(err("OptimizerError", "supplied m_wet_kg: value must be a finite number (a TBD is not supplied)"));
    }
    let ec = py::gi(rec, "evidence_class")?.clone();
    let parametric = py::get_or_none(rec, "parametric")?.truthy();
    let st = if py::eq_str(&ec, SYN_CLASS) {
        SYNTHETIC_ONLY
    } else if parametric || !py::in_strs(&ec, &RANKABLE_CLASSES) {
        PARAMETRIC_ONLY
    } else {
        EVALUATED
    };
    let reason = if st == EVALUATED {
        Value::Null
    } else {
        s(format!(
            "supplied value of class {}{} is not rankable evidence",
            py_repr(&ec),
            if parametric { " (parametric)" } else { "" }
        ))
    };
    let mut d = obj(st, f(v.to_f64()?), ec, py::gi(rec, "source")?.clone(), reason, Value::Null);
    d.push(("supplied", Value::Bool(true)));
    Ok(dict(d))
}

/// `wet_mass(config, design_masses, supplied, repo)` on the record at `repo/RECORD_REL` (read as Python reads it).
pub fn wet_mass(repo: &Path, config: &Value, design_masses: &Value, supplied: &Value) -> PyResult<Value> {
    let mp = py::load_json(repo, RECORD_REL)?;
    wet_mass_of(&mp, config, design_masses, supplied)
}

/// `wet_mass` on a parsed record.
pub fn wet_mass_of(mp: &Value, config: &Value, design_masses: &Value, supplied: &Value) -> PyResult<Value> {
    if !py::is_none(supplied) {
        if !py::get_or_none(supplied, "all_terms_resolved")?.truthy() {
            return Ok(dict(obj(
                INCOMPLETE,
                Value::Null,
                Value::Null,
                Value::Null,
                s("supplied roll-up has unresolved terms"),
                list([s(UNLOCK_M_WET)]),
            )));
        }
        return supplied_objective(supplied);
    }
    let mut rolls = Vec::new();
    for r in py::iter(py::gi(mp, "rollups")?)? {
        if py_eq(py::gi(&r, "configuration")?, config) {
            rolls.push(r);
        }
    }
    let cfg = py_str(config);
    if rolls.len() != 1 {
        return Err(err(
            "RuntimeError",
            format!("mass/power v3: expected one owner-reading roll-up for {cfg}, got {}", rolls.len()),
        ));
    }
    let roll = &rolls[0];
    let mut wets = Vec::new();
    for w in py::iter(py::gi(roll, "wet")?)? {
        if py::eq_str(py::gi(&w, "reference")?, "HARD_40_WET") {
            wets.push(w);
        }
    }
    if wets.is_empty() {
        return Err(err("RuntimeError", format!("mass/power v3: no HARD_40_WET wet roll-up for {cfg}")));
    }
    let known: Vec<Value> = wets.iter().map(|w| py::gi(w, "wet_known_kg").cloned()).collect::<PyResult<_>>()?;
    let mut states: Vec<Value> = Vec::new();
    for w in &wets {
        let st = py::gi(w, "state")?;
        if !states.iter().any(|x| py_eq(x, st)) {
            states.push(st.clone());
        }
    }
    let states = py::sorted(&states)?;
    let mut by_xe = Vec::new();
    for w in &wets {
        by_xe.push(dict(vec![
            ("xe_case_kg", py::gi(w, "xe_case_kg")?.clone()),
            ("wet_known_kg", py::gi(w, "wet_known_kg")?.clone()),
            ("state", py::gi(w, "state")?.clone()),
            ("exceedance_kg", py::get_or_none(w, "exceedance_kg")?),
        ]));
    }
    let dm = if design_masses.truthy() { py::as_dict(design_masses)?.clone() } else { Default::default() };
    if let Some(rec) = dm.get(INTAKE_MASS_LINE) {
        require_f1q02_label(rec)?;
    }
    let mut lines = Vec::new();
    for ln in py::iter(py::gi(py::gi(mp, "lines")?, &cfg_key(config)?)?)? {
        let lid = py::gi(&ln, "line")?.clone();
        let val = py::get_or_none(&ln, "value")?;
        let val = if val.truthy() { val } else { dict(vec![]) };
        let design = match &lid {
            Value::Str(k) => dm.get(k).cloned().unwrap_or(Value::Null),
            _ => Value::Null,
        };
        lines.push(dict(vec![
            ("line", lid.clone()),
            ("name", py::gi(&ln, "name")?.clone()),
            ("allocation_kg", py::get_or_none(&ln, "row54_allocation_kg")?),
            ("evidence_floor_kg", py::get_or_none(&ln, "evidence_floor_cbe_kg")?),
            ("cbe_kg", py::get_or_none(&ln, "cbe_kg")?),
            ("measured_kg", py::get_or_none(&ln, "measured_kg")?),
            ("design_parametric", design),
            ("budget_value_kg", py::get_or_none(&val, "value_kg")?),
            ("budget_value_governs", py::get_or_none(&val, "governs")?),
        ]));
    }
    for x in &lines {
        if !py::is_none(py::gi(x, "cbe_kg")?) || !py::is_none(py::gi(x, "measured_kg")?) {
            return Err(err(
                "RuntimeError",
                "mass/power v3 now carries a CBE / measured line mass: m_wet needs re-evaluation",
            ));
        }
    }
    let mut lo = known[0].clone();
    let mut hi = known[0].clone();
    for k in &known[1..] {
        if py::py_lt(k, &lo)? {
            lo = k.clone();
        }
        if py::py_lt(&hi, k)? {
            hi = k.clone();
        }
    }
    let cases: Vec<Value> = wets.iter().map(|w| py::gi(w, "xe_case_kg").cloned()).collect::<PyResult<_>>()?;
    let reading = py::gi(roll, "reading")?.clone();
    let reason = format!(
        "no CBE or measured mass exists for any BOM line (mass/power v3); the wet roll-ups of the owner reading '{}' \
         against the 40 kg wet limit are {} for the Xe load cases {} kg",
        py_str(&reading),
        py_repr(&Value::List(states.clone())),
        py_repr(&Value::List(cases))
    );
    let mut d = obj(NOT_EVALUATED, Value::Null, Value::Null, Value::Null, s(reason), list([s(UNLOCK_M_WET)]));
    d.extend([
        ("wet_known_allocation_envelope_kg", list([lo, hi])),
        ("wet_rollup_states", Value::List(states)),
        ("wet_rollup_by_xe_case", Value::List(by_xe)),
        ("owner_reading", reading),
        ("budget_source", s(format!("{RECORD_REL} rollups[configuration={cfg}].wet[reference=HARD_40_WET]"))),
        ("lines", Value::List(lines)),
        ("rule", s("allocation / evidence floor / design-parametric / CBE never merged")),
    ]);
    Ok(dict(d))
}

fn cfg_key(config: &Value) -> PyResult<String> {
    match config {
        Value::Str(k) => Ok(k.clone()),
        other => Err(err("KeyError", py_repr(other))),
    }
}

/// The production entry (DIV-V03): the record is a frozen pinned input, verified by sha256 before it is read.
pub fn wet_mass_pinned(repo: &Path, config: &Value, design_masses: &Value, supplied: &Value) -> PyResult<Value> {
    let actual = sha256_hex(&py::read_bytes(repo, RECORD_REL)?);
    if actual != RECORD_SHA256 {
        return Err(err(
            "PinError",
            format!(
                "{RECORD_REL} sha256 {actual} != pinned {RECORD_SHA256} (frozen mass / power v5 record, read as a \
                 pinned input)"
            ),
        ));
    }
    wet_mass(repo, config, design_masses, supplied)
}
