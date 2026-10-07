//! Statewise requirement assessment (contract E7-E10): the mapping of the admitted statewise quantifier's PASS / FAIL
//! onto the constraint vocabulary (`upstream_a9_13.statewise_envelope`), AG-13 / HC-08 statewise drag compensation,
//! AG-12 / HC-11 feed-state sufficiency and the HC-12 ripple feed-quality constraint (`design_gates.py`).
//!
//! The quantifier itself is abep_mission::statewise::statewise_quantifier (admitted, PARITY-C-ABEP_SIM_STATEWISE_PY-V1);
//! it is called, never re-implemented. HC-08 / HC-11 margins are formed against the configured limits.

use crate::error::{rule_error, AssessError, AssessResult};
use crate::py::{dget, dget_or, dict, eq_str, finite, float, get, in_strs, s, strs};
use crate::thresholds::Thresholds;
use abep_gaspath::upstream::{
    self as u13, combine_value_status, constraint_status, H1Tolerance, C_NOT_EVALUATED, FEED_STATE_FIELDS,
    H1_MAP_VALIDATED, SYNTHETIC, VALUE_REFERENCE, VALUE_STATUSES, VALUE_SYNTHETIC, VALUE_TBD,
};
use abep_mission::statewise::statewise_quantifier;
use abep_types::pyjson::{py_eq, py_repr, py_repr_tuple, py_str, Dict, Value};

pub fn rfp_clause(key: &str) -> &'static str {
    u13::RFP_CLAUSES.iter().find(|(k, _)| *k == key).map(|(_, v)| *v).expect("registered clause key")
}

/// `upstream_a9_13.cite(*keys)` (path + json sha256 + ids per decision, reference key order).
pub fn cite(keys: &[&str]) -> AssessResult<Value> {
    let mut out = Vec::new();
    for k in keys {
        let d = u13::DECISIONS.iter().find(|d| d.key == *k).ok_or_else(|| crate::error::key_error(k))?;
        out.push(dict(vec![
            ("decision", s(*k)),
            ("md", s(d.md)),
            ("json", s(d.json)),
            ("json_sha256", s(d.json_sha256)),
            ("ids", strs(d.ids)),
        ]));
    }
    Ok(Value::List(out))
}

fn value_statuses_repr() -> String {
    py_repr_tuple(&VALUE_STATUSES.iter().map(|x| s(*x)).collect::<Vec<_>>())
}

/// `statewise_envelope(requirement_id, states, margin_fn, value_status)`.
pub fn statewise_envelope(
    requirement_id: &str,
    states: &[Value],
    margin_fn: &mut dyn FnMut(&Value) -> Result<Value, String>,
    value_status: &Value,
) -> AssessResult<Value> {
    if !in_strs(value_status, &VALUE_STATUSES) {
        return Err(rule_error(format!("value_status {} not in {}", py_repr(value_status), value_statuses_repr())));
    }
    let vs = py_str(value_status);
    let q = statewise_quantifier(states, margin_fn, &s(requirement_id))?;
    let tbd = vs == VALUE_TBD;
    let st = if eq_str(get(&q, "verdict")?, "MODEL_ERROR") || tbd {
        C_NOT_EVALUATED
    } else {
        constraint_status(Some(eq_str(get(&q, "verdict")?, "PASS")), &vs)
    };
    let mut per = Vec::new();
    for p in crate::py::as_list(get(&q, "per_state")?)? {
        let pst = get(p, "status")?;
        let state_status = if eq_str(pst, "MODEL_ERROR") || tbd {
            C_NOT_EVALUATED
        } else {
            constraint_status(Some(eq_str(pst, "PASS")), &vs)
        };
        per.push(dict(vec![
            ("state_id", get(p, "state_id")?.clone()),
            ("margin", get(p, "margin")?.clone()),
            ("state_status", s(state_status)),
        ]));
    }
    let worst = match get(&q, "worst_state")? {
        Value::Null => Value::Null,
        w => dict(vec![("state_id", get(w, "state_id")?.clone()), ("margin", get(w, "margin")?.clone())]),
    };
    Ok(dict(vec![
        ("requirement_id", s(requirement_id)),
        ("status", s(st)),
        ("value_status", s(vs)),
        ("n_states", get(&q, "n_states")?.clone()),
        ("n_states_below_zero", get(&q, "n_fail")?.clone()),
        ("n_model_error", get(&q, "n_model_error")?.clone()),
        ("worst_state", worst),
        ("orbit_average_margin", get(&q, "orbit_average_margin")?.clone()),
        ("orbit_average_note", s("informational only; the statewise result governs (A9.14 S9.7, A9.13 S6.15)")),
        ("average_hides_violation", get(&q, "average_hides_violation")?.clone()),
        ("per_state", Value::List(per)),
        ("errors", get(&q, "errors")?.clone()),
        ("authority", cite(&["A9.14", "A9.13"])?),
    ]))
}

/// `_rec_value(rec, what)`: (value, status); a TBD record has value NaN.
pub fn rec_value(rec: &Value, what: &str) -> AssessResult<(f64, String)> {
    if !matches!(rec, Value::Dict(_)) {
        return Err(rule_error(format!("{what} record must be a mapping")));
    }
    let st = dget(rec, "status")?;
    if !in_strs(&st, &VALUE_STATUSES) {
        return Err(rule_error(format!("{what} status {} not in {}", py_repr(&st), value_statuses_repr())));
    }
    let v = dget(rec, "value_N")?;
    if eq_str(&st, VALUE_TBD) {
        return Ok((f64::NAN, VALUE_TBD.into()));
    }
    if !finite(&v) {
        return Err(rule_error(format!("{what} value_N must be finite")));
    }
    Ok((float(&v)?, py_str(&st)))
}

/// `combine_value_status(statuses)` with the reference refusal text (`unknown value status(es) [...]`, sorted).
pub fn combine(statuses: &[String]) -> AssessResult<&'static str> {
    let mut bad: Vec<String> = statuses.iter().filter(|x| !VALUE_STATUSES.contains(&x.as_str())).cloned().collect();
    bad.sort();
    bad.dedup();
    if !bad.is_empty() {
        let l = Value::List(bad.into_iter().map(Value::Str).collect());
        return Err(rule_error(format!("unknown value status(es) {}", py_repr(&l))));
    }
    let refs: Vec<&str> = statuses.iter().map(String::as_str).collect();
    Ok(combine_value_status(&refs)?)
}

/// Last-entry-wins lookup by state id (Python dict semantics).
struct ById<T> {
    entries: Vec<(Value, T)>,
}

impl<T> ById<T> {
    fn new() -> Self {
        ById { entries: Vec::new() }
    }
    fn insert(&mut self, k: Value, v: T) {
        match self.entries.iter_mut().find(|(x, _)| py_eq(x, &k)) {
            Some(slot) => slot.1 = v,
            None => self.entries.push((k, v)),
        }
    }
    fn get(&self, k: &Value) -> Option<&T> {
        self.entries.iter().find(|(x, _)| py_eq(x, k)).map(|(_, v)| v)
    }
}

fn sid_of(st: &Value) -> AssessResult<Value> {
    dget(st, "state_id")
}

/// `statewise_drag_compensation(states, thrust_fn, drag_fn, hall_admitted)` (AG-13 / HC-08). `thrust_fn` /
/// `drag_fn` are called once per state, in order. The margin is T - D - limit_HC08 (limit 0.0 in the frozen
/// configuration).
pub fn statewise_drag_compensation(
    t: &Thresholds,
    states: &[Value],
    thrust_fn: &mut dyn FnMut(usize, &Value) -> AssessResult<Value>,
    drag_fn: &mut dyn FnMut(usize, &Value) -> AssessResult<Value>,
    hall_admitted: bool,
) -> AssessResult<Value> {
    if states.is_empty() {
        return Err(rule_error("AG-13 needs the required state set (an empty set satisfies nothing)"));
    }
    let limit = t.limit("HC-08").ok_or_else(|| AssessError::new("ConfigurationError", "HC-08 limit missing"))?;
    let mut recs: ById<(f64, f64)> = ById::new();
    let mut statuses: Vec<String> = Vec::new();
    let mut refused = Vec::new();
    for (i, st) in states.iter().enumerate() {
        let sid = sid_of(st)?;
        let tr = thrust_fn(i, st)?;
        let dr = drag_fn(i, st)?;
        for (nm, r) in [("thrust", &tr), ("drag", &dr)] {
            let rs = dget(r, "state_id")?;
            if !py_eq(&rs, &sid) {
                return Err(rule_error(format!(
                    "{nm} record for state {} was evaluated at {}: thrust and drag must be paired at the same state \
                     (S6.15)",
                    py_repr(&sid),
                    py_repr(&rs)
                )));
            }
        }
        let (tv, mut ts) = rec_value(&tr, "thrust")?;
        let (dv, ds) = rec_value(&dr, "drag")?;
        if ts != VALUE_SYNTHETIC && ts != VALUE_TBD && !hall_admitted {
            refused.push(sid.clone());
            ts = VALUE_TBD.into();
        }
        recs.insert(sid, (tv, dv));
        statuses.push(ts);
        statuses.push(ds);
    }
    let vs = combine(&statuses)?;
    let mut out = vec![
        ("constraint", s("HC-08 / AG-13")),
        (
            "rule",
            s("T_available(state) - D_spacecraft(state) >= 0 at every required state (statewise hard constraint)"),
        ),
        ("rfp_clauses", strs(&[rfp_clause("altitude"), rfp_clause("thrust")])),
        ("authority", cite(&["A9.13", "A9.14"])?),
        ("value_status", s(vs)),
        ("n_required_states", Value::int(states.len() as i64)),
        ("thrust_refused_no_admitted_hall_member", Value::List(refused)),
    ];
    if vs == VALUE_TBD {
        out.extend([
            ("status", s(C_NOT_EVALUATED)),
            ("statewise", Value::Null),
            (
                "reason",
                s("thrust and / or spacecraft drag not evaluated at every required state (no admitted Hall member / \
                   host-spacecraft ICD); NOT_EVALUATED, never counted as satisfied"),
            ),
        ]);
        return Ok(dict(out));
    }
    let mut margin = |st: &Value| -> Result<Value, String> {
        let sid = sid_of(st).map_err(|e| e.to_string())?;
        let (tv, dv) = recs.get(&sid).ok_or_else(|| format!("KeyError: {}", py_repr(&sid)))?;
        Ok(Value::Float(tv - dv - limit))
    };
    let q = statewise_envelope("AG-13", states, &mut margin, &s(vs))?;
    out.extend([
        ("status", get(&q, "status")?.clone()),
        ("statewise", get(&q, "per_state")?.clone()),
        ("worst_state", get(&q, "worst_state")?.clone()),
        ("orbit_average_margin_N", get(&q, "orbit_average_margin")?.clone()),
        ("average_hides_violation", get(&q, "average_hides_violation")?.clone()),
    ]);
    if vs == VALUE_REFERENCE {
        out.push((
            "note",
            s("reference spacecraft drag (REFERENCE/PARAMETRIC, S6.18): an indication only; AG-13 closure needs the \
               host-spacecraft ICD"),
        ));
    }
    Ok(dict(out))
}

/// A per-state record source called once per state, in order (state position, state).
pub type StateFn<'a> = &'a mut dyn FnMut(usize, &Value) -> AssessResult<Value>;

/// A tabulated H-1 thrust-versus-feed map: its status and `min_feed_state(state, thrust_N, offered)` per state
/// position (None = outside the map domain).
pub struct H1Map<'a> {
    pub status: Value,
    pub min_feed_state: &'a mut dyn FnMut(usize, &Value, f64, &Value) -> AssessResult<Value>,
}

/// `feed_state_sufficiency(states, offered_fn, required_thrust_fn, h1_map, fixed_mass_flow_gate)` (AG-12 / HC-11).
/// The statewise margin is the minimum field margin minus limit_HC11 (0.0 in the frozen configuration).
pub fn feed_state_sufficiency(
    t: &Thresholds,
    states: &[Value],
    offered_fn: &mut dyn FnMut(usize, &Value) -> AssessResult<Value>,
    required_thrust_fn: Option<StateFn<'_>>,
    h1_map: Option<H1Map<'_>>,
    fixed_mass_flow_gate_supplied: bool,
) -> AssessResult<Value> {
    u13::refuse_fixed_mass_flow_gate(fixed_mass_flow_gate_supplied)?;
    let limit = t.limit("HC-11").ok_or_else(|| AssessError::new("ConfigurationError", "HC-11 limit missing"))?;
    let mut base = vec![
        ("gate", s("AG-12")),
        (
            "rule",
            s("statewise feed-state sufficiency (mass flow, pressure, temperature, composition, ripple quality) \
               against the requirement derived from the required thrust and a validated H-1 map"),
        ),
        ("fixed_mass_flow_gate", s("REMOVED (0.38-3.2 mg/s = characterization coverage only)")),
        ("rfp_clauses", strs(&[rfp_clause("thrust"), rfp_clause("altitude"), rfp_clause("intake_sizing")])),
        ("authority", cite(&["A9.13", "A9.14"])?),
    ];
    let map_status = h1_map.as_ref().map_or(Value::Null, |m| m.status.clone());
    let h1 = match h1_map {
        Some(m) if in_strs(&map_status, &[H1_MAP_VALIDATED, SYNTHETIC]) => m,
        _ => {
            let shown = if map_status.truthy() { map_status } else { s("NONE") };
            base.extend([
                ("status", s(C_NOT_EVALUATED)),
                ("h1_map_status", shown),
                ("reason", s("no validated H-1 thrust-versus-feed map exists (AG-12 NOT_EVALUATED until it does)")),
            ]);
            return Ok(dict(base));
        }
    };
    let Some(required_thrust_fn) = required_thrust_fn else {
        base.extend([
            ("status", s(C_NOT_EVALUATED)),
            ("h1_map_status", map_status),
            ("reason", s("required drag-compensation thrust per state not supplied (registered drag basis)")),
        ]);
        return Ok(dict(base));
    };
    let names = ["mdot", "P", "T", "composition", "ripple"];
    let mut rows = Dict::new();
    let mut margins: ById<f64> = ById::new();
    let mut statuses: Vec<Value> = Vec::new();
    for (i, st) in states.iter().enumerate() {
        let sid = sid_of(st)?;
        let key = match &sid {
            Value::Str(x) => x.clone(),
            other => return Err(AssessError::new("TypeError", format!("state_id {} is not a str", py_repr(other)))),
        };
        let off = offered_fn(i, st)?;
        let mut missing = Vec::new();
        for k in FEED_STATE_FIELDS {
            if matches!(dget(&off, k)?, Value::Null) {
                missing.push(s(k));
            }
        }
        let tr = required_thrust_fn(i, st)?;
        if !py_eq(&dget(&tr, "state_id")?, &sid) {
            return Err(rule_error("required thrust must be evaluated at the same state"));
        }
        let (tv, ts) = rec_value(&tr, "required thrust")?;
        let os = dget_or(&off, "status", s(VALUE_TBD))?;
        statuses.push(s(ts.clone()));
        statuses.push(os.clone());
        if !missing.is_empty() || ts == VALUE_TBD || eq_str(&os, VALUE_TBD) {
            rows.insert(
                key.as_str(),
                dict(vec![("margin", Value::Float(f64::NAN)), ("missing", Value::List(missing))]),
            );
            margins.insert(sid, f64::NAN);
            continue;
        }
        let req = (h1.min_feed_state)(i, st, tv, &off)?;
        if matches!(req, Value::Null) {
            rows.insert(
                key.as_str(),
                dict(vec![
                    ("margin", Value::Float(-1.0)),
                    ("reason", s("offered feed / required thrust outside the H-1 map domain")),
                ]),
            );
            margins.insert(sid, -1.0);
            continue;
        }
        let f = |v: &Value, k: &str| -> AssessResult<f64> { float(get(v, k)?) };
        let mut m =
            vec![f(&off, "mdot_kgps")? / f(&req, "mdot_kgps")? - 1.0, f(&off, "P_Pa")? / f(&req, "P_Pa")? - 1.0];
        let tr_k = crate::py::as_list(get(&req, "T_range_K")?)?;
        if tr_k.len() != 2 {
            return Err(AssessError::new("ValueError", "T_range_K must hold two values"));
        }
        let (tlo, thi, tk) = (float(&tr_k[0])?, float(&tr_k[1])?, f(&off, "T_K")?);
        m.push(if tlo <= tk && tk <= thi { 0.0 } else { -1.0 });
        m.push(if get(&req, "x_domain_ok")?.truthy() { 0.0 } else { -1.0 });
        let rf = f(&off, "ripple_frac")?;
        m.push(if rf > 0.0 { f(&req, "ripple_tolerance_frac")? / rf.max(1e-300) - 1.0 } else { 0.0 });
        let mut mn = m[0];
        for x in &m[1..] {
            if *x < mn {
                mn = *x;
            }
        }
        let mut fm = Dict::new();
        for (n, x) in names.iter().zip(&m) {
            fm.insert(*n, Value::Float(*x));
        }
        rows.insert(
            key.as_str(),
            dict(vec![("margin", Value::Float(mn)), ("field_margins", Value::Dict(fm)), ("required", req.clone())]),
        );
        margins.insert(sid, mn);
    }
    let mut sts: Vec<String> = Vec::new();
    for x in &statuses {
        match x {
            Value::Str(v) => sts.push(v.clone()),
            other => return Err(AssessError::new("TypeError", format!("status {} is not a str", py_repr(other)))),
        }
    }
    if eq_str(&map_status, SYNTHETIC) {
        sts.push(SYNTHETIC.into());
    }
    let vs = combine(&sts)?;
    if rows.values().any(|r| !get(r, "margin").and_then(float).map(f64::is_finite).unwrap_or(false)) {
        base.extend([
            ("status", s(C_NOT_EVALUATED)),
            ("h1_map_status", map_status),
            ("per_state", Value::Dict(rows)),
            ("reason", s("feed-state record or required thrust not evaluated at every state")),
        ]);
        return Ok(dict(base));
    }
    let mut margin = |st: &Value| -> Result<Value, String> {
        let sid = sid_of(st).map_err(|e| e.to_string())?;
        let m = margins.get(&sid).ok_or_else(|| format!("KeyError: {}", py_repr(&sid)))?;
        Ok(Value::Float(m - limit))
    };
    let q = statewise_envelope("AG-12", states, &mut margin, &s(vs))?;
    let mut fms = Dict::new();
    for (k, r) in rows.iter() {
        fms.insert(k.as_str(), dget(r, "field_margins")?);
    }
    base.extend([
        ("status", get(&q, "status")?.clone()),
        ("h1_map_status", map_status),
        ("value_status", s(vs)),
        ("per_state", get(&q, "per_state")?.clone()),
        ("field_margins", Value::Dict(fms)),
        ("worst_state", get(&q, "worst_state")?.clone()),
        ("average_hides_violation", get(&q, "average_hides_violation")?.clone()),
    ]);
    Ok(dict(base))
}

/// `ripple_feed_quality(ripple_frac, ripple_status, h1)` (HC-12; NOT_EVALUATED while the H-1 tolerance is TBD).
pub fn ripple_feed_quality(
    ripple_frac: &Value,
    ripple_status: &Value,
    h1: Option<&H1Tolerance>,
) -> AssessResult<Value> {
    if let Some(h) = h1 {
        if h.quantity != "ripple" {
            return Err(rule_error("ripple must be compared with the H-1 ripple tolerance"));
        }
    }
    let role = ("role", s("HARD_CONSTRAINT_NOT_OBJECTIVE"));
    let h1_tbd = h1.is_none_or(|h| h.status == VALUE_TBD);
    if h1_tbd || matches!(ripple_frac, Value::Null) || eq_str(ripple_status, VALUE_TBD) {
        return Ok(dict(vec![
            ("constraint", s("FEED_QUALITY_RIPPLE")),
            ("status", s(C_NOT_EVALUATED)),
            ("ripple_frac", ripple_frac.clone()),
            ("ripple_status", ripple_status.clone()),
            ("tolerance_frac", h1.and_then(|h| h.value_frac).map_or(Value::Null, Value::Float)),
            ("reason", s(if h1_tbd { "measured H-1 ripple tolerance TBD" } else { "ripple not evaluated" })),
            role,
        ]));
    }
    let h = h1.expect("not TBD");
    if !finite(ripple_frac) || float(ripple_frac)? < 0.0 {
        return Ok(dict(vec![
            ("constraint", s("FEED_QUALITY_RIPPLE")),
            ("status", s(C_NOT_EVALUATED)),
            ("ripple_frac", Value::Null),
            ("reason", s("ripple not finite")),
            role,
        ]));
    }
    let rs = match ripple_status {
        Value::Str(x) => x.as_str(),
        other => return Err(AssessError::new("TypeError", format!("ripple_status {} is not a str", py_repr(other)))),
    };
    let vs = combine(&[rs.to_string(), h.status.clone()])?;
    let tol = h.value_frac.ok_or_else(|| AssessError::new("TypeError", "tolerance value is None"))?;
    let rf = float(ripple_frac)?;
    Ok(dict(vec![
        ("constraint", s("FEED_QUALITY_RIPPLE")),
        ("status", s(constraint_status(Some(rf <= tol), vs))),
        ("ripple_frac", Value::Float(rf)),
        ("tolerance_frac", Value::Float(tol)),
        ("value_status", s(vs)),
        role,
    ]))
}
