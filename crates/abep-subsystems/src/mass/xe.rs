//! Xe sensitivity / booking kernels of the Xe accounting v3 builder
//! (`docs/budgets/xe_accounting_a9_v3/build_xe_accounting_a9_v3.py`: case_split_loaded, ignition_booking_s,
//! book_reserve_and_residual, ground_supply, eval_line, evaluate). Contract
//! `docs/rust_migration/contracts/C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3/` (function subset; the record regeneration is
//! not ported here).
//!
//! Owner rules: A9.14 XA9Q-01 / MQ-09 / OQ-A910-01 (the 2 / 5 / 10 kg cases are LOADED Xe = mission usable, reserve
//! and residual, each once; the residual is a sub-line inside the case), XA9Q-02 / OQ-A907-01 (at most 3 attempts x
//! 120 s = 360 s per start; a shorter dwell only with evidence), XA9Q-03 (every flight line inside the reserve base),
//! XA9Q-04 (ground supply = (calculated + explicit procedure lines) x 1.20). The mission Xe load is not an input: the
//! cases are planning / sensitivity cases, and every total with a TBD line stays REFUSED_TBD_INPUTS.

use super::py::{self, dict, err, f, list, s};
use super::pyfmt;
use abep_types::pyjson::{py_eq, py_repr, py_str, PyException, PyResult, Value};

pub const CASE_READING: &str = "LOADED";
pub const RETIRED_CASE_READINGS: [&str; 1] = ["USABLE_RESIDUAL_ON_TOP"];
pub const IGN_ATTEMPTS_MAX: i64 = 3;
pub const IGN_DWELL_CAP_S: f64 = 120.0;
pub const IGN_BOOKING_MAX_S: f64 = 360.0;
pub const GROUND_LOGISTICS_MARGIN: f64 = 0.2;
pub const ZERO_STATES: [&str; 4] =
    ["EXACT_ZERO_BY_OWNER_DECISION", "ABSENT_BY_OWNER_DECISION", "ZERO_BY_SCOPE", "ZERO_XE_BY_OWNER_DECISION"];
pub const PENDING_STATES: [&str; 1] = ["CONDITIONAL_ON_C1_FLIGHT_SELECTION"];
pub const RETIRED_PRESENCE: [&str; 1] = ["ABSENT_UNDER_READING"];
/// A9.19 / A9.20: the retired flight column (history only; ground reference, never flight).
pub const RETIRED_FLIGHT_CONFIGS: [&str; 1] = ["hall_c1_reference"];
pub const PROCEDURES: [&str; 4] = ["purge", "conditioning", "line_fill", "vendor_procedures"];
const UNIT_SI: [(&str, f64); 5] = [("mg/s", 1e-6), ("h", 3600.0), ("s", 1.0), ("1", 1.0), ("kg", 1.0)];

fn booking(message: impl Into<String>) -> PyException {
    err("BookingError", message)
}

/// `_num(v, what)`: a finite number >= 0 as float (bool refused).
pub fn num(v: &Value, what: &str) -> PyResult<f64> {
    let ok = py::is_real(v) && {
        let x = v.to_f64()?;
        x.is_finite() && x >= 0.0
    };
    if !ok {
        return Err(booking(format!("{what} = {} must be a finite number >= 0 (no NaN / negative Xe)", py_repr(v))));
    }
    v.to_f64()
}

fn rk(x: f64) -> Value {
    f(pyfmt::rk(x))
}

/// `case_split_loaded(case_kg, f_reserve, f_residual, reading="LOADED")`: case = mission usable + reserve + residual.
pub fn case_split_loaded(case: &Value, f_reserve: &Value, f_residual: &Value, reading: &Value) -> PyResult<Value> {
    if py::in_strs(reading, &RETIRED_CASE_READINGS) {
        return Err(booking(format!(
            "case reading {} retired: the residual is never added on top of a loaded case (A9.14 MQ-09 / OQ-A910-01)",
            py_str(reading)
        )));
    }
    if !py::eq_str(reading, CASE_READING) {
        return Err(booking(format!("unknown case reading {}", py_str(reading))));
    }
    let c = num(case, "case_kg")?;
    let fr = num(f_reserve, "f_reserve")?;
    let fs = num(f_residual, "f_residual")?;
    let usable = c / (1.0 + fs);
    let residual = fs * usable;
    let mission_usable = usable / (1.0 + fr);
    let reserve = fr * mission_usable;
    let bound = 1e-12 * if c > 1.0 { c } else { 1.0 };
    // NaN never closes, as Python's `not abs(...) <= bound`
    let closes = (mission_usable + reserve + residual - c).abs() <= bound;
    if !closes {
        return Err(booking("loaded-case split does not close (double counting)"));
    }
    Ok(dict(vec![
        ("case_kg", f(c)),
        ("reading", s(CASE_READING)),
        ("loaded_kg", f(c)),
        ("mission_usable_kg", f(mission_usable)),
        ("reserve_kg", f(reserve)),
        ("residual_kg", f(residual)),
        ("usable_incl_reserve_kg", f(usable)),
    ]))
}

/// `ignition_booking_s(attempts=3, dwell_s=120.0, evidence=None)`: at most 3 x 120 s = 360 s per start.
pub fn ignition_booking_s(attempts: &Value, dwell: &Value, evidence: &Value) -> PyResult<f64> {
    let n = match attempts {
        Value::Int(i) => i.as_i64().filter(|n| (1..=IGN_ATTEMPTS_MAX).contains(n)),
        _ => None,
    };
    let Some(n) = n else {
        return Err(booking(format!(
            "attempts {} outside 1..{IGN_ATTEMPTS_MAX} (one initial + at most two retries)",
            py_repr(attempts)
        )));
    };
    let d = num(dwell, "dwell_s")?;
    if d <= 0.0 || d > IGN_DWELL_CAP_S {
        return Err(booking(format!(
            "dwell {} s outside (0, {}] s (row 93 / XA9Q-02)",
            py::repr_f(d),
            py::repr_f(IGN_DWELL_CAP_S)
        )));
    }
    let has_evidence = matches!(evidence, Value::Str(t) if !abep_types::pyjson::py_strip(t).is_empty());
    if d < IGN_DWELL_CAP_S && !has_evidence {
        return Err(booking("a dwell below the 120 s cap needs an evidence source (tightened by evidence only)"));
    }
    let t = n as f64 * d;
    if t > IGN_BOOKING_MAX_S {
        return Err(booking("ignition booking exceeds the 360 s maximum"));
    }
    Ok(t)
}

/// `book_reserve_and_residual(evals, lines, f_reserve, f_residual)`: reserve and residual exactly once per flight
/// evaluation; every line inside the reserve base; a total with a TBD line is REFUSED_TBD_INPUTS.
pub fn book_reserve_and_residual(
    evals: &[Value],
    lines: &Value,
    f_reserve: &Value,
    f_residual: &Value,
) -> PyResult<Value> {
    if py::is_none(f_reserve) || py::is_none(f_residual) {
        return Err(booking("reserve/residual fraction missing (no default)"));
    }
    let ids: Vec<Value> = evals.iter().map(|e| py::gi(e, "line").cloned()).collect::<PyResult<_>>()?;
    for (i, a) in ids.iter().enumerate() {
        if ids[..i].iter().any(|b| py_eq(a, b)) {
            return Err(booking("duplicate ledger line (double counting)"));
        }
    }
    for e in evals {
        let lid = py::gi(e, "line")?;
        let reserved = py::in_strs(lid, &["RESERVE", "RESIDUAL"]) || {
            let ln = py::gi_val(lines, lid)?;
            py::in_strs(py::gi(ln, "phase")?, &["reserve", "residual"])
        };
        if reserved {
            return Err(booking("reserve/residual already present: booking twice is refused"));
        }
        if !matches!(py::gi(py::gi_val(lines, lid)?, "reserve_base")?, Value::Bool(true)) {
            return Err(booking(format!("{}: every v3 flight line is inside the reserve base (XA9Q-03)", py_str(lid))));
        }
    }
    let mut tbd = Vec::new();
    let mut terms = Vec::new();
    for e in evals {
        let kg = py::gi(e, "kg")?;
        if py::is_none(kg) {
            tbd.push(py::gi(e, "line")?.clone());
        }
        terms.push(if kg.truthy() { kg.clone() } else { f(0.0) });
    }
    let base = py::sum(&terms)?;
    let reserve = py::num(f_reserve)? * base;
    let usable = base + reserve;
    let residual = py::num(f_residual)? * usable;
    let floors = dict(vec![
        ("mission_usable_kg", rk(base)),
        ("reserve_kg", rk(reserve)),
        ("usable_incl_reserve_kg", rk(usable)),
        ("residual_sub_line_kg", rk(residual)),
        ("loaded_kg", rk(usable + residual)),
    ]);
    if !tbd.is_empty() {
        return Ok(dict(vec![
            ("status", s("REFUSED_TBD_INPUTS")),
            ("tbd_lines", Value::List(tbd)),
            ("totals", Value::Null),
            ("floors_closed_terms_only", floors),
        ]));
    }
    let status = if usable + residual == 0.0 { "COMPUTED_EXACT_ZERO" } else { "COMPUTED" };
    Ok(dict(vec![
        ("status", s(status)),
        ("tbd_lines", list([])),
        ("totals", floors.clone()),
        ("floors_closed_terms_only", floors),
    ]))
}

/// `ground_supply(calculated_kg, procedures_kg, margin=0.20)`: (calculated + explicit procedures) x 1.20.
pub fn ground_supply(calculated: &Value, procedures: &Value, margin: &Value) -> PyResult<Value> {
    if !py_eq(margin, &f(GROUND_LOGISTICS_MARGIN)) {
        return Err(booking(format!("ground logistics margin {} is not the owner's 0.20 (XA9Q-04)", py_repr(margin))));
    }
    let procs = py::as_dict(procedures)?;
    let same_set = procs.len() == PROCEDURES.len() && PROCEDURES.iter().all(|k| procs.contains_key(k));
    if !same_set {
        return Err(booking(
            "procedure bookings must name exactly ('purge', 'conditioning', 'line_fill', 'vendor_procedures') \
             (booked explicitly before the margin)",
        ));
    }
    let mut tbd: Vec<Value> = Vec::new();
    for k in PROCEDURES {
        if py::is_none(procs.get(k).expect("checked key")) {
            tbd.push(s(k));
        }
    }
    let calc = py::as_dict(calculated)?;
    for (k, v) in calc.iter() {
        if py::is_none(v) {
            tbd.push(s(k.clone()));
        }
    }
    let mut vals: Vec<(Value, Value)> = Vec::new();
    for (k, v) in calc.iter().chain(procs.iter()) {
        if !py::is_none(v) {
            vals.push((s(k.clone()), f(num(v, k)?)));
        }
    }
    let vals = py::dict_pairs(vals);
    let terms: Vec<Value> = vals.into_iter().map(|(_, v)| v).collect();
    if !tbd.is_empty() {
        return Ok(dict(vec![
            ("status", s("REFUSED_TBD_INPUTS")),
            ("tbd", Value::List(py::sorted(&tbd)?)),
            ("supply_kg", Value::Null),
            ("floor_closed_terms_only_kg", rk(py::sum(&terms)?)),
        ]));
    }
    let base = py::sum(&terms)?;
    let m = GROUND_LOGISTICS_MARGIN;
    Ok(dict(vec![
        ("status", s("COMPUTED")),
        ("tbd", list([])),
        ("calculated_kg", rk(base)),
        ("margin_kg", rk(m * base)),
        ("supply_kg", rk(base * (1.0 + m))),
    ]))
}

fn unit_si(unit: &Value) -> PyResult<f64> {
    UNIT_SI.iter().find(|(u, _)| py::eq_str(unit, u)).map(|(_, x)| *x).ok_or_else(|| err("KeyError", py_repr(unit)))
}

/// `eval_line(ln, items, done)`: one ledger line; absence propagates (kg None with the missing fields).
pub fn eval_line(ln: &Value, items: &Value, done: &Value) -> PyResult<Value> {
    let pres = py::gi(ln, "presence")?;
    let id = py::gi(ln, "id")?;
    if py::in_strs(pres, &RETIRED_PRESENCE) {
        return Err(booking(format!("{}: retired presence {}", py_str(id), py_str(pres))));
    }
    let mut missing: Vec<Value> = Vec::new();
    let out = |kg: Value, missing: Vec<Value>| {
        dict(vec![("line", id.clone()), ("presence", pres.clone()), ("kg", kg), ("missing", Value::List(missing))])
    };
    if py::in_strs(pres, &ZERO_STATES) {
        return Ok(out(f(0.0), missing));
    }
    if py::in_strs(pres, &PENDING_STATES) {
        if !py::in_strs(py::gi(ln, "configuration")?, &RETIRED_FLIGHT_CONFIGS) {
            return Err(booking(format!(
                "{}: a C1 flight pending term outside the retired C1 flight column (A9.19)",
                py_str(id)
            )));
        }
        missing.push(dict(vec![
            ("field", s("flight C1 selection / selected C1 Xe requirement (pre-A9.19 history)")),
            ("item", s("XV3-01, XV3-02")),
            (
                "requires",
                s("NONE - hall_c1_reference was retired as a flight configuration by A9.19 and C1 is ground-only \
                   (A9.20); the pre-A9.19 state was PENDING_C1_NOT_SELECTED (neither assumed nor excluded, A9.15)"),
            ),
        ]));
        return Ok(out(Value::Null, missing));
    }
    let kind = py::gi(ln, "kind")?;
    if py::in_strs(kind, &["product", "mass"]) {
        let mut val = 1.0_f64;
        for fl in py::iter(py::gi(ln, "fields")?)? {
            let item_id = py::gi(&fl, "item")?;
            let it = py::gi_val(items, item_id)?;
            let v = py::gi(it, "value")?;
            if py::is_none(v) {
                let fallback = py::get_or_none(it, "value_display")?;
                let requires = py::get(it, "requires")?.cloned().unwrap_or(fallback);
                missing.push(dict(vec![
                    ("field", py::gi(&fl, "name")?.clone()),
                    ("item", item_id.clone()),
                    ("requires", requires),
                ]));
                continue;
            }
            let what = format!("{}.{}", py_str(id), py_str(py::gi(&fl, "name")?));
            let x = num(v, &what)?;
            val *= x * unit_si(py::gi(&fl, "unit")?)?;
        }
        let kg = if missing.is_empty() { rk(val) } else { Value::Null };
        return Ok(out(kg, missing));
    }
    if py::eq_str(kind, "fraction_of_lines") {
        let fields = py::iter(py::gi(ln, "fields")?)?;
        let fl = fields.first().ok_or_else(|| err("IndexError", "list index out of range"))?;
        let item_id = py::gi(fl, "item")?;
        let u = py::gi(py::gi_val(items, item_id)?, "value")?.clone();
        if py::is_none(&u) {
            missing.push(dict(vec![
                ("field", py::gi(fl, "name")?.clone()),
                ("item", item_id.clone()),
                ("requires", py::get_or_none(py::gi_val(items, item_id)?, "requires")?),
            ]));
        }
        let of = py::iter(py::gi(ln, "of_lines")?)?;
        let mut parts = Vec::new();
        for x in &of {
            parts.push(py::gi(py::gi_val(done, x)?, "kg")?.clone());
        }
        if parts.iter().any(py::is_none) {
            let mut tbd = Vec::new();
            for x in &of {
                if py::is_none(py::gi(py::gi_val(done, x)?, "kg")?) {
                    tbd.push(x.clone());
                }
            }
            missing.push(dict(vec![("field", s("sum of")), ("lines", Value::List(tbd))]));
        }
        if !missing.is_empty() {
            return Ok(out(Value::Null, missing));
        }
        let name = py_str(py::gi(fl, "name")?);
        let kg = rk(num(&u, &name)? * py::sum(&parts)?);
        return Ok(out(kg, missing));
    }
    Err(booking(format!("{}: unknown kind {}", py_str(id), py_str(kind))))
}

const GROUND_RULE: &str = "supply = (calculated test consumption + explicit procedure lines) x 1.20 (A9.14 XA9Q-04); \
                           no reserve / residual rule for ground-test Xe";

/// `evaluate(lines, items, scenarios)`: every scenario's ledger evaluation and booking.
pub fn evaluate(lines: &[Value], items: &Value, scenarios: &[Value]) -> PyResult<Value> {
    let mut ld = abep_types::pyjson::Dict::new();
    for ln in lines {
        match py::gi(ln, "id")? {
            Value::Str(k) => ld.insert(k.clone(), ln.clone()),
            other => return Err(err("TypeError", format!("ledger line id {} is not a str", py_repr(other)))),
        }
    }
    let ld = Value::Dict(ld);
    let f_rsv = py::gi(py::gi(items, "XV2-23")?, "value")?.clone();
    let f_res = py::gi(py::gi(items, "XV2-24")?, "value")?.clone();
    let mut out = Vec::new();
    for sc in scenarios {
        let sc_lines = py::iter(py::gi(sc, "lines")?)?;
        let mut keyed = Vec::new();
        for lid in &sc_lines {
            let frac = py::eq_str(py::gi(py::gi_val(&ld, lid)?, "kind")?, "fraction_of_lines");
            keyed.push((frac, lid.clone()));
        }
        let mut order: Vec<Value> = keyed.iter().filter(|k| !k.0).map(|k| k.1.clone()).collect();
        order.extend(keyed.iter().filter(|k| k.0).map(|k| k.1.clone()));
        let mut done = abep_types::pyjson::Dict::new();
        for lid in &order {
            let r = eval_line(py::gi_val(&ld, lid)?, items, &Value::Dict(done.clone()))?;
            done.insert(py_str(lid), r);
        }
        let done = Value::Dict(done);
        let evals: Vec<Value> = sc_lines.iter().map(|lid| py::gi_val(&done, lid).cloned()).collect::<PyResult<_>>()?;
        let mut rec = vec![("scenario", py::gi(sc, "id")?.clone()), ("lines", Value::List(evals.clone()))];
        if py::eq_str(py::gi(sc, "ledger")?, "FLIGHT") {
            rec.push(("booking", book_reserve_and_residual(&evals, &ld, &f_rsv, &f_res)?));
        } else {
            let mut calc = Vec::new();
            let mut procs = Vec::new();
            for e in &evals {
                let lid = py::gi(e, "line")?;
                let ln = py::gi_val(&ld, lid)?;
                if !py::eq_str(py::gi(ln, "phase")?, "procedure") {
                    calc.push((lid.clone(), py::gi(e, "kg")?.clone()));
                }
            }
            for e in &evals {
                let lid = py::gi(e, "line")?;
                let ln = py::gi_val(&ld, lid)?;
                if py::eq_str(py::gi(ln, "phase")?, "procedure") {
                    procs.push((py::gi(ln, "procedure_category")?.clone(), py::gi(e, "kg")?.clone()));
                }
            }
            let to_dict = |pairs: Vec<(Value, Value)>| -> PyResult<Value> {
                let mut d = abep_types::pyjson::Dict::new();
                for (k, v) in py::dict_pairs(pairs) {
                    match k {
                        Value::Str(t) => d.insert(t, v),
                        other => return Err(err("TypeError", format!("key {} is not a str", py_repr(&other)))),
                    }
                }
                Ok(Value::Dict(d))
            };
            let mut g = ground_supply(&to_dict(calc)?, &to_dict(procs)?, &f(GROUND_LOGISTICS_MARGIN))?;
            let mut tbd = Vec::new();
            for e in &evals {
                if py::is_none(py::gi(e, "kg")?) {
                    tbd.push(py::gi(e, "line")?.clone());
                }
            }
            let gd = py::as_dict_mut(&mut g);
            gd.insert("tbd_lines", Value::List(tbd));
            gd.insert("rule", s(GROUND_RULE));
            rec.push(("booking", g));
        }
        out.push(dict(rec));
    }
    Ok(Value::List(out))
}

#[cfg(test)]
mod tests {
    use super::*;
    use abep_types::pyjson::loads;

    #[test]
    fn registered_test_vectors() {
        let n = Value::Null;
        assert_eq!(ignition_booking_s(&Value::int(3), &f(120.0), &n).unwrap(), 360.0);
        for bad in [Value::int(4), Value::int(0), f(2.5), Value::Bool(true)] {
            assert_eq!(ignition_booking_s(&bad, &f(120.0), &n).unwrap_err().class, "BookingError");
        }
        assert!(ignition_booking_s(&Value::int(3), &f(100.0), &n).is_err());
        assert_eq!(ignition_booking_s(&Value::int(3), &f(100.0), &s("measured H-1 start log")).unwrap(), 300.0);
        let ld = loads(
            r#"{"A": {"phase": "xe_mode", "reserve_base": true}, "B": {"phase": "transition", "reserve_base": true}}"#,
        )
        .unwrap();
        let ev = [loads(r#"{"line": "A", "kg": 1.0}"#).unwrap(), loads(r#"{"line": "B", "kg": 0.5}"#).unwrap()];
        let b = book_reserve_and_residual(&ev, &ld, &f(0.2), &f(0.02)).unwrap();
        assert_eq!(py::gi(py::gi(&b, "totals").unwrap(), "reserve_kg").unwrap(), &f(0.3));
        let procs =
            loads(r#"{"purge": 0.1, "conditioning": 0.2, "line_fill": 0.05, "vendor_procedures": 0.15}"#).unwrap();
        let g = ground_supply(&loads(r#"{"ref": 1.5}"#).unwrap(), &procs, &f(0.2)).unwrap();
        assert_eq!(py::gi(&g, "supply_kg").unwrap(), &f(2.4));
        let sp = case_split_loaded(&f(2.0), &f(0.2), &f(0.02), &s("LOADED")).unwrap();
        assert_eq!(pyfmt::sig6(py::num(py::gi(&sp, "residual_kg").unwrap()).unwrap()), 0.0392157);
        assert!(case_split_loaded(&f(2.0), &f(0.2), &f(0.02), &s("USABLE_RESIDUAL_ON_TOP")).is_err());
    }
}
