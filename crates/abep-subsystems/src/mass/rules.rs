//! K-MASS-RULES: the fail-closed mass roll-up rules of the pinned mass / power v3 builder
//! (`docs/budgets/mass_power_a9_v3/build_mass_power_a9_v3.py`: rk, _kg, line_mev_value, system_margin, harness_row60,
//! closure_state, _unresolved, assert_no_margin_relaxation, rollup) and the A9.26 bid-margin rules of the v5 builder
//! (system_margin_bid, assert_bid_margin_reading). Contract `docs/rust_migration/contracts/K-MASS-RULES/`.
//!
//! Owner rules: A9.14 MQ-01 (owner allocations are MEV; a CBE or CBE-level floor is raised by the row-57 0.20 equipment
//! margin and governs when heavier; no input -> TBD, never 0), MQ-02 (20 % system margin of the current pre-margin sum,
//! never together with the 4 kg reserve), MQ-06 / row 60 (harness 5 % of the nominal dry mass incl. harness), MQ-09
//! (LOADED Xe cases: the residual is inside the case), MQ-10 (no margin relaxation); A9.26 sec. 1 (10 % system margin
//! for the bid basis). A9.19 / A9.20: C1 is GROUND_REFERENCE_ONLY and never enters a flight roll-up (DIV-K01 / K02).
//!
//! The rules take JSON-shaped Python values so that int / float / bool / None inputs, key order and `repr()` in refusal
//! messages are reproduced exactly. No rule returns PASS: closure states are CLOSES / DOES_NOT_CLOSE / NOT_EVALUABLE
//! and every roll-up has `all_terms_resolved = false`.

use super::py::{self, dict, err, f, s};
use super::pyfmt;
use abep_types::pyjson::{py_eq, py_repr, PyException, PyResult, Value};

pub const SYSTEM_MARGIN: f64 = 0.2;
pub const EQUIPMENT_MARGIN: f64 = 0.2;
pub const HARNESS_FRACTION: f64 = 0.05;
pub const SYSTEM_MARGIN_BID: f64 = 0.1;
pub const FLIGHT: &str = "hall_icp_neutralizer";
pub const CLOSURE_STATES: [&str; 3] = ["CLOSES", "DOES_NOT_CLOSE", "NOT_EVALUABLE"];
pub const OWNER_READING: &str = "MEV_LEVEL_EVIDENCE_BASED (the single owner reading)";
const RULE_MQ10: &str = "MQ-10: reduce actual subsystem CBE (redesign, integration, lighter qualified parts); the \
                         margin reading is not relaxed; the lines without a value add to this need when known";

pub fn mass_error(message: impl Into<String>) -> PyException {
    err("MassError", message)
}

pub fn policy_error(message: impl Into<String>) -> PyException {
    err("MassPolicyError", message)
}

/// `rk(x) = None if x is None else float(f"{x:.10g}")`.
pub fn rk(x: &Value) -> PyResult<Value> {
    match x {
        Value::Null => Ok(Value::Null),
        Value::Int(_) | Value::Float(_) | Value::Bool(_) => Ok(f(pyfmt::rk(py::num(x)?))),
        Value::Str(_) => Err(err("ValueError", "Unknown format code 'g' for object of type 'str'")),
        other => Err(err("TypeError", format!("unsupported format string passed to {}.__format__", other.type_name()))),
    }
}

/// `rk` on a computed float.
pub fn rkf(x: f64) -> Value {
    f(pyfmt::rk(x))
}

/// `_kg(v, what)`: a finite mass >= 0 kg as float (bool refused), else MassError.
pub fn kg(v: &Value, what: &str) -> PyResult<f64> {
    let ok = py::is_real(v) && {
        let x = v.to_f64()?;
        x.is_finite() && x >= 0.0
    };
    if !ok {
        return Err(mass_error(format!("{what} = {} must be a finite mass >= 0 kg", py_repr(v))));
    }
    v.to_f64()
}

/// `line_mev_value(allocation_kg, cbe_kg, floor_cbe_kg, equipment_margin)` (A9.14 MQ-01).
pub fn line_mev_value(allocation: &Value, cbe: &Value, floor: &Value, equipment_margin: &Value) -> PyResult<Value> {
    if !py_eq(equipment_margin, &f(EQUIPMENT_MARGIN)) {
        return Err(mass_error(
            "equipment margin other than the row-57 0.20 default needs a selected-part maturity record",
        ));
    }
    let em = EQUIPMENT_MARGIN;
    let mut cands: Vec<(&str, f64)> = Vec::new();
    if !py::is_none(allocation) {
        cands.push(("ALLOCATION_MEV", kg(allocation, "allocation")?));
    }
    if !py::is_none(cbe) {
        cands.push(("MEV_FROM_CBE", pyfmt::rk(kg(cbe, "CBE")? * (1.0 + em))));
    } else if !py::is_none(floor) {
        cands.push(("MEV_PLANNING_FLOOR", pyfmt::rk(kg(floor, "evidence floor")? * (1.0 + em))));
    }
    if cands.is_empty() {
        return Ok(dict(vec![("value_kg", Value::Null), ("governs", Value::Null)]));
    }
    let mut best = 0;
    for (i, c) in cands.iter().enumerate() {
        if c.1 > cands[best].1 {
            best = i;
        }
    }
    let (g, v) = cands[best];
    Ok(dict(vec![
        ("value_kg", f(v)),
        ("governs", s(g)),
        ("candidates", py::list(cands.iter().map(|(b, k)| dict(vec![("basis", s(*b)), ("kg", f(*k))])))),
    ]))
}

fn reserve_is_zero(reserve: &Value) -> bool {
    py::in_tuple(reserve, &[Value::int(0), f(0.0)])
}

/// `system_margin(pre_margin_kg, fraction=0.2, reserve_kg=0.0)` (A9.14 MQ-02).
pub fn system_margin(pre: &Value, fraction: &Value, reserve: &Value) -> PyResult<Value> {
    if !py_eq(fraction, &f(SYSTEM_MARGIN)) {
        return Err(mass_error("the system margin is 0.20 (MQ-02); relaxing it to pass 40 kg is refused (MQ-10)"));
    }
    if !reserve_is_zero(reserve) {
        return Err(mass_error(
            "the fixed 4 kg reserve is replaced by the 20 % system margin: adding both is refused (MQ-02)",
        ));
    }
    let p = kg(pre, "pre-margin sum")?;
    Ok(margin_record(p, SYSTEM_MARGIN))
}

fn margin_record(p: f64, fraction: f64) -> Value {
    dict(vec![
        ("pre_margin_kg", rkf(p)),
        ("system_margin_kg", rkf(fraction * p)),
        ("total_kg", rkf(p * (1.0 + fraction))),
    ])
}

/// `system_margin_bid(m, pre_margin_kg, fraction=0.1, reserve_kg=0.0)` (A9.26 sec. 1).
pub fn system_margin_bid(pre: &Value, fraction: &Value, reserve: &Value) -> PyResult<Value> {
    if !py_eq(fraction, &f(SYSTEM_MARGIN_BID)) {
        return Err(policy_error(
            "the active bid system margin is 0.10 (A9.26 section 1); the 0.20 reading is the historical / \
             conservative sensitivity (pinned v3 rules) and nothing else is admitted",
        ));
    }
    if !reserve_is_zero(reserve) {
        return Err(policy_error("no fixed reserve on top of the system margin (A9.14 MQ-02 rule kept)"));
    }
    let p = kg(pre, "pre-margin sum")?;
    Ok(margin_record(p, SYSTEM_MARGIN_BID))
}

/// `harness_row60(other_nominal_kg, fraction=0.05)` (row 60 / A9.14 MQ-06): f / (1 - f) x the other nominal lines.
pub fn harness_row60(other: &Value, fraction: &Value) -> PyResult<f64> {
    if !py_eq(fraction, &f(HARNESS_FRACTION)) {
        return Err(mass_error("harness fraction is the row-60 0.05 until a routed harness exists"));
    }
    let fr = HARNESS_FRACTION;
    Ok(pyfmt::rk(kg(other, "other nominal dry")? * fr / (1.0 - fr)))
}

/// `closure_state(known_kg, reference_kg, strict, all_resolved)`.
pub fn closure_state(known: &Value, reference: &Value, strict: &Value, all_resolved: &Value) -> PyResult<&'static str> {
    let k = kg(known, "known mass")?;
    let r = kg(reference, "reference")?;
    let exceeds = if strict.truthy() { k >= r } else { k > r };
    Ok(if exceeds {
        "DOES_NOT_CLOSE"
    } else if all_resolved.truthy() {
        "CLOSES"
    } else {
        "NOT_EVALUABLE"
    })
}

/// `_unresolved(rec)`: the TBD / not-a-CBE statements of one line record.
pub fn unresolved(rec: &Value) -> PyResult<Vec<Value>> {
    let lid = py::gi(rec, "line")?;
    let v = py::gi(rec, "value")?;
    let l = py::pstr(lid);
    if py::eq_str(lid, "AL-HAR") {
        return Ok(vec![s(format!("{l}: harness by the row-60 rule until a routed harness exists (not a CBE)"))]);
    }
    if py::is_none(py::gi(v, "value_kg")?) {
        let why = py::get(rec, "allocation_status")?.cloned().unwrap_or_else(|| s("no value"));
        return Ok(vec![s(format!("{l}: NO VALUE - {} (excluded from the known part)", py::pstr(&why)))]);
    }
    let governs = py::gi(v, "governs")?;
    let mut out = Vec::new();
    if py::eq_str(governs, "ALLOCATION_MEV") {
        out.push(s(format!("{l}: owner MEV allocation, not a CBE (row 54; MQ-01)")));
    } else if py::eq_str(governs, "MEV_PLANNING_FLOOR") {
        out.push(s(format!("{l}: MEV planning floor from an analog / preliminary-design floor, not a CBE")));
        if py::get(rec, "floor_is_partial")?.is_some_and(Value::truthy) {
            let mut whats = Vec::new();
            for c in py::iter(py::gi(rec, "floor_constituents")?)? {
                if py::get(&c, "kg")?.is_none_or(py::is_none) {
                    whats.push(py::gi(&c, "what")?.clone());
                }
            }
            out.push(s(format!("{l}: floor INCOMPLETE - {}", py::join_strs("; ", &whats)?)));
        }
    }
    Ok(out)
}

fn owner_reading(fraction: Value) -> Value {
    dict(vec![("allocations", s("MEV")), ("system_margin", fraction), ("reserve_kg", f(0.0)), ("xe_case", s("LOADED"))])
}

/// `assert_no_margin_relaxation(reading)` (A9.14 MQ-10 / MQ-01 / MQ-02).
pub fn assert_no_margin_relaxation(reading: &Value) -> PyResult<()> {
    let want = owner_reading(f(SYSTEM_MARGIN));
    if !py_eq(reading, &want) {
        return Err(mass_error(format!(
            "closure reading {} refused: only {} (A9.14 MQ-01 / MQ-02 / MQ-09 / MQ-10)",
            py_repr(reading),
            py_repr(&want)
        )));
    }
    Ok(())
}

/// `assert_bid_margin_reading(reading)` (A9.26 sec. 1).
pub fn assert_bid_margin_reading(reading: &Value) -> PyResult<()> {
    let want = owner_reading(f(SYSTEM_MARGIN_BID));
    if !py_eq(reading, &want) {
        return Err(policy_error(format!(
            "bid closure reading {} refused: only {} (A9.26 section 1)",
            py_repr(reading),
            py_repr(&want)
        )));
    }
    Ok(())
}

/// A Python Xe-case split `{case_kg: {loaded_kg, residual_kg}}` as ordered (key, value) pairs.
pub type XeSplit = Vec<(Value, Value)>;
/// `(reference name, reference kg, strict)` tuples.
pub type Refs = Vec<(Value, Value, Value)>;

/// The flight-only guard of DIV-K01 / DIV-K02 (A9.19 / A9.20: C1 GROUND_REFERENCE_ONLY never enters a flight roll-up).
pub fn require_flight_rollup(cfg: &Value, lines: &[Value]) -> PyResult<()> {
    if !py::eq_str(cfg, FLIGHT) {
        return Err(mass_error(format!(
            "rollup configuration {} refused: the only flight configuration is 'hall_icp_neutralizer' (A9.19 / \
             A9.20: C1 is GROUND_REFERENCE_ONLY and never enters a flight mass roll-up)",
            py_repr(cfg)
        )));
    }
    let c1 = lines.iter().any(|r| r.as_dict().and_then(|d| d.get("line")).is_some_and(|l| py::eq_str(l, "AL-C1")));
    if c1 {
        return Err(mass_error(
            "AL-C1: C1 is GROUND_REFERENCE_ONLY (A9.19 / A9.20); no C1 line enters a flight mass roll-up",
        ));
    }
    Ok(())
}

/// The margin variant of a roll-up: the v3 rule (0.20, MQ-02) or the A9.26 bid basis (0.10).
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Margin {
    V3Historical,
    Bid,
}

pub(crate) struct RollupSpec<'a> {
    pub margin: Margin,
    pub fraction: f64,
    pub reading: &'a str,
    pub rule: &'a str,
    pub loaded_error: fn() -> PyException,
    pub unresolved: fn(&Value) -> PyResult<Vec<Value>>,
}

/// The roll-up arithmetic shared by v3 `rollup` and v5 `rollup_v5`.
pub(crate) fn rollup_core(
    cfg: &Value,
    lines: &[Value],
    split: &XeSplit,
    refs: &Refs,
    spec: &RollupSpec,
) -> PyResult<Value> {
    require_flight_rollup(cfg, lines)?;
    let mut parts = Vec::new();
    let mut tbd = Vec::new();
    let mut missing = Vec::new();
    let mut known = Vec::new();
    for rec in lines {
        let lid = py::gi(rec, "line")?;
        if py::eq_str(lid, "AL-HAR") {
            continue;
        }
        let value = py::gi(rec, "value")?;
        let v = py::gi(value, "value_kg")?.clone();
        let line = py::gi(rec, "line")?.clone();
        let used = py::gi(py::gi(rec, "value")?, "governs")?.clone();
        parts.push(dict(vec![("line", line.clone()), ("used", used), ("kg", v.clone())]));
        tbd.extend((spec.unresolved)(rec)?);
        if py::is_none(&v) {
            missing.push(line);
        } else {
            known.push(v);
        }
    }
    let nh = pyfmt::rk(py::sum(&known)?);
    let har = harness_row60(&f(nh), &f(HARNESS_FRACTION))?;
    let partial = !missing.is_empty();
    parts.push(dict(vec![
        ("line", s("AL-HAR")),
        ("used", s("HARNESS_POLICY_ROW60")),
        ("kg", f(har)),
        ("partial", Value::Bool(partial)),
        ("note", if partial { s("computed on the known non-harness part only") } else { Value::Null }),
    ]));
    let mut har_rec = None;
    for r in lines {
        if py::eq_str(py::gi(r, "line")?, "AL-HAR") {
            har_rec = Some(r);
            break;
        }
    }
    let har_rec = har_rec.ok_or_else(|| err("StopIteration", ""))?;
    tbd.extend(unresolved(har_rec)?);
    let nominal = pyfmt::rk(nh + har);
    let sm = match spec.margin {
        Margin::V3Historical => system_margin(&f(nominal), &f(SYSTEM_MARGIN), &f(0.0))?,
        Margin::Bid => system_margin_bid(&f(nominal), &f(spec.fraction), &f(0.0))?,
    };
    let dry = py::num(py::gi(&sm, "total_kg")?)?;
    let mut wet_rows = Vec::new();
    let mut cases: Vec<&(Value, Value)> = split.iter().collect();
    sort_cases(&mut cases)?;
    for (case_kg, sp) in cases {
        let loaded = py::gi(sp, "loaded_kg")?;
        if !py_eq(loaded, case_kg) {
            return Err((spec.loaded_error)());
        }
        let wet = pyfmt::rk(dry + py::num(loaded)?);
        for (name, reference, strict) in refs {
            let st = closure_state(&f(wet), reference, strict, &Value::Bool(false))?;
            let mut row = vec![
                ("xe_case_kg", case_kg.clone()),
                ("xe_loaded_kg", loaded.clone()),
                ("residual_inside_case_kg", py::gi(sp, "residual_kg")?.clone()),
                ("residual_added_on_top_kg", f(0.0)),
                ("wet_known_kg", f(wet)),
                ("reference", name.clone()),
                ("reference_kg", reference.clone()),
                ("comparator", s(if strict.truthy() { "<" } else { "<=" })),
                ("state", s(st)),
            ];
            let r = py::num(reference)?;
            if st == "DOES_NOT_CLOSE" {
                let nh_max = (r - py::num(loaded)?) * (1.0 - HARNESS_FRACTION) / (1.0 + spec.fraction);
                row.push(("exceedance_kg", rkf(wet - r)));
                row.push((
                    "redesign_need",
                    dict(vec![
                        ("nonharness_nominal_reduction_kg_at_least", rkf(nh - nh_max)),
                        ("nonharness_nominal_max_kg", rkf(nh_max)),
                        ("rule", s(spec.rule)),
                    ]),
                ));
            } else {
                row.push(("margin_to_reference_kg", rkf(r - wet)));
            }
            wet_rows.push(dict(row));
        }
    }
    Ok(dict(vec![
        ("configuration", cfg.clone()),
        ("reading", s(spec.reading)),
        ("parts", Value::List(parts)),
        ("nonharness_known_kg", f(nh)),
        ("harness_kg", f(har)),
        ("nominal_dry_known_kg", f(nominal)),
        ("system_margin_kg", py::gi(&sm, "system_margin_kg")?.clone()),
        ("reserve_kg", f(0.0)),
        ("dry_known_kg", f(dry)),
        ("lines_without_value", Value::List(missing)),
        ("tbd", Value::List(tbd)),
        ("all_terms_resolved", Value::Bool(false)),
        ("wet", Value::List(wet_rows)),
    ]))
}

/// `sorted(xe_split.items())` (keys are distinct numbers; Python orders by key).
fn sort_cases(cases: &mut [&(Value, Value)]) -> PyResult<()> {
    let keys: Vec<Value> = cases.iter().map(|(k, _)| k.clone()).collect();
    let order = py::sorted(&keys)?;
    let mut out = Vec::with_capacity(cases.len());
    for k in &order {
        let i = cases.iter().position(|(ck, _)| py_eq(ck, k) && ck == k).expect("sorted key present");
        out.push(cases[i]);
    }
    cases.copy_from_slice(&out);
    Ok(())
}

fn v3_loaded_error() -> PyException {
    mass_error("Xe v3 case is not LOADED (the residual would be counted twice)")
}

/// v3 `rollup(cfg, lines, xe_split, refs)`: the single owner reading (MEV, 20 % system margin, no reserve, LOADED Xe).
pub fn rollup(cfg: &Value, lines: &[Value], split: &XeSplit, refs: &Refs) -> PyResult<Value> {
    assert_no_margin_relaxation(&owner_reading(f(SYSTEM_MARGIN)))?;
    rollup_core(
        cfg,
        lines,
        split,
        refs,
        &RollupSpec {
            margin: Margin::V3Historical,
            fraction: SYSTEM_MARGIN,
            reading: OWNER_READING,
            rule: RULE_MQ10,
            loaded_error: v3_loaded_error,
            unresolved,
        },
    )
}

pub(crate) const RULE_MQ10_TEXT: &str = RULE_MQ10;

#[cfg(test)]
mod tests {
    use super::*;
    use abep_types::pyjson::loads;

    fn v(t: &str) -> Value {
        loads(t).unwrap()
    }

    #[test]
    fn registered_test_vectors() {
        let n = Value::Null;
        let em = f(0.2);
        let r = line_mev_value(&f(3.0), &n, &f(3.504), &em).unwrap();
        assert_eq!(py::gi(&r, "value_kg").unwrap(), &f(4.2048));
        let r = line_mev_value(&f(2.5), &f(4.0), &f(5.0), &em).unwrap();
        assert_eq!(py::gi(&r, "value_kg").unwrap(), &f(4.8));
        assert_eq!(py::gi(&line_mev_value(&n, &n, &n, &em).unwrap(), "value_kg").unwrap(), &Value::Null);
        assert_eq!(line_mev_value(&f(1.0), &n, &n, &f(0.1)).unwrap_err().class, "MassError");
        let e = line_mev_value(&f(-1.0), &n, &n, &em).unwrap_err();
        assert_eq!(e.message, "allocation = -1.0 must be a finite mass >= 0 kg");
        assert_eq!(
            system_margin(&f(24.0), &f(0.2), &f(0.0)).unwrap(),
            v(r#"{"pre_margin_kg": 24.0, "system_margin_kg": 4.8, "total_kg": 28.8}"#)
        );
        assert!(system_margin(&f(24.0), &f(0.2), &f(4.0)).is_err());
        assert!(system_margin(&f(24.0), &f(0.1), &f(0.0)).is_err());
        assert!((harness_row60(&f(19.0), &f(0.05)).unwrap() - 1.0).abs() < 1e-12);
        assert_eq!(
            closure_state(&f(40.0), &f(40.0), &Value::Bool(true), &Value::Bool(false)).unwrap(),
            "DOES_NOT_CLOSE"
        );
        assert_eq!(closure_state(&f(39.0), &f(40.0), &Value::Bool(true), &Value::Bool(true)).unwrap(), "CLOSES");
        assert_eq!(
            closure_state(&f(34.0), &f(34.0), &Value::Bool(false), &Value::Bool(false)).unwrap(),
            "NOT_EVALUABLE"
        );
        assert_eq!(system_margin_bid(&f(30.0), &f(0.2), &f(0.0)).unwrap_err().class, "MassPolicyError");
        let bad = v(r#"{"allocations": "MEV", "system_margin": 0.05, "reserve_kg": 0.0, "xe_case": "LOADED"}"#);
        assert_eq!(
            assert_bid_margin_reading(&bad).unwrap_err().message,
            "bid closure reading {'allocations': 'MEV', 'system_margin': 0.05, 'reserve_kg': 0.0, 'xe_case': 'LOADED'} \
             refused: only {'allocations': 'MEV', 'system_margin': 0.1, 'reserve_kg': 0.0, 'xe_case': 'LOADED'} (A9.26 \
             section 1)"
        );
    }

    #[test]
    fn c1_never_enters_a_flight_rollup() {
        let lines = vec![
            v(r#"{"line": "AL-C1", "value": {"value_kg": 0.5, "governs": "ALLOCATION_MEV"}}"#),
            v(r#"{"line": "AL-HAR", "value": {"value_kg": null, "governs": null}}"#),
        ];
        let e = rollup(&s(FLIGHT), &lines, &vec![], &vec![]).unwrap_err();
        assert!(e.message.starts_with("AL-C1: C1 is GROUND_REFERENCE_ONLY"));
        let e = rollup(&s("hall_c1_reference"), &lines[1..], &vec![], &vec![]).unwrap_err();
        assert!(e.message.starts_with("rollup configuration 'hall_c1_reference' refused"));
    }
}
