//! F7 hard constraints HC-01..HC-12 (`abep_sim/assessment/design_gates.py`: HARD_CONSTRAINTS, evaluate_constraints,
//! hard_constraint_partition, constraint_met_value_kinds; PARITY-C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY-V1 E1-E4).
//!
//! Fail closed: MET / VIOLATED only on an EVALUATED or SYNTHETIC value; a PARAMETRIC value gives the sensitivity
//! statuses that never count as satisfied; anything else is NOT_EVALUATED. HC-05 follows A9.31 sec. 10 (DIV-01): a
//! record needs an uncertainty basis AND a validation basis VALIDATED_BENCH or MEASURED, else NOT_EVALUATED.

use crate::error::{AssessError, AssessResult};
use crate::py::{as_list, dget, dict, eq_str, fmt6g, fmt_g, get, in_strs, s};
use crate::thresholds::Thresholds;
use abep_gaspath::upstream as u13;
use abep_mission::objective::{EVALUATED, PARAMETRIC_ONLY, SYNTHETIC_ONLY};
use abep_types::pyjson::{py_str, Value};

pub use u13::{C_MET, C_MET_PARAMETRIC, C_NOT_EVALUATED, C_VIOLATED, C_VIOLATED_PARAMETRIC};

pub const PRE_EVALUATED_OBJECTIVES: [&str; 3] =
    ["statewise_T_minus_D", "feed_state_sufficiency", "ripple_feed_quality"];
/// A9.31 sec. 10: the validation bases under which HC-05 may be evaluated.
pub const HC05_VALIDATION_BASES: [&str; 2] = ["VALIDATED_BENCH", "MEASURED"];
pub const HC05_A9_31_BASIS: &str = "A9.31 sec. 10 (OQ-NPICP-02): a model-derived I_e,cap that is VERIFIED but not \
bench-validated does not satisfy HC-05; NOT_EVALUATED outside a VALIDATED_BENCH domain cell (a measured I_e,cap \
supersedes the model at the measured point); the record carries no qualifying validation_basis";

/// One row of HARD_CONSTRAINTS.
#[derive(Debug, Clone)]
pub struct HardConstraint {
    pub id: &'static str,
    pub rvm: &'static str,
    pub rfp: Option<&'static str>,
    pub quantity: String,
    pub comparator: &'static str,
    pub limit: Option<f64>,
    pub units: &'static str,
    pub objective: &'static str,
    pub category: &'static str,
    pub statewise: bool,
}

impl HardConstraint {
    pub fn to_value(&self) -> Value {
        let mut v = vec![("id", s(self.id)), ("rvm", s(self.rvm))];
        if let Some(r) = self.rfp {
            v.push(("rfp", s(r)));
        }
        v.extend([
            ("quantity", s(self.quantity.clone())),
            ("comparator", s(self.comparator)),
            ("limit", self.limit.map_or(Value::Null, Value::Float)),
            ("units", s(self.units)),
            ("objective", s(self.objective)),
            ("category", s(self.category)),
        ]);
        if self.statewise {
            v.push(("statewise", Value::Bool(true)));
        }
        dict(v)
    }

    /// `f"{comparator} {limit:g} {units}"`.
    fn rule(&self) -> AssessResult<String> {
        let l = self
            .limit
            .ok_or_else(|| AssessError::new("TypeError", "unsupported format string passed to NoneType.__format__"))?;
        Ok(format!("{} {} {}", self.comparator, fmt_g(l), self.units))
    }
}

/// HARD_CONSTRAINTS with the configured limits.
pub fn hard_constraints(t: &Thresholds) -> Vec<HardConstraint> {
    let hc03 = t.limit("HC-03").map_or("TBD".to_string(), fmt_g);
    #[allow(clippy::type_complexity)]
    let rows: [(&str, &str, Option<&str>, String, &str, &str, &str, &str, bool); 12] = [
        (
            "HC-01",
            "RVM-02",
            Some("RFP-P18-06"),
            "T (sustained, atmospheric propellant)".into(),
            ">=",
            "N",
            "thrust_N",
            "rfp_recorded",
            false,
        ),
        (
            "HC-02",
            "RVM-03",
            Some("RFP-P18-06; RFP-P18-10"),
            format!("demonstrated thrust capability at P_bus < {hc03} W"),
            ">=",
            "N",
            "thrust_capability_N",
            "rfp_recorded",
            false,
        ),
        (
            "HC-03",
            "RVM-04",
            Some("RFP-P18-10"),
            "P_bus,1ms,max (steady and start-up, A9-02 gate)".into(),
            "<",
            "W",
            "P_bus_W",
            "rfp_recorded",
            false,
        ),
        (
            "HC-04",
            "RVM-06",
            Some("RFP-P18-11"),
            "wet propulsion-system mass".into(),
            "<",
            "kg",
            "m_wet_kg",
            "rfp_recorded",
            false,
        ),
        (
            "HC-05",
            "RVM-15",
            None,
            "M_n,LB: lower uncertainty bound of M_n = I_e,cap / I_d,max,H1 - 1 (A9.24 item 5; the point difference \
I_e,cap - I_d,max is never the acceptance criterion; no lower bound -> NOT_EVALUATED)"
                .into(),
            ">",
            "-",
            "M_n_LB",
            "derived_from_owner_decision",
            false,
        ),
        (
            "HC-06",
            "RVM-17",
            None,
            "thermal margin below validated limits".into(),
            ">=",
            "K",
            "thermal_margin_K",
            "derived_project",
            false,
        ),
        (
            "HC-07",
            "RVM-12",
            Some("RFP-P19-01"),
            "cumulative firing time capability".into(),
            ">",
            "h",
            "firing_life_h",
            "rfp_recorded",
            false,
        ),
        (
            "HC-08",
            "AG-13 (owner decision A9.13 S6.15 / OQ-F78-01; A9.14 S9.7 statewise quantifier)",
            Some("RFP-P18-04; RFP-P18-06"),
            "T_available(state) - D_spacecraft(state) at EVERY required state (statewise; worst state governs; the \
orbit average never hides a deficit)"
                .into(),
            ">=",
            "N",
            "statewise_T_minus_D",
            "owner_decision_hard_statewise",
            true,
        ),
        (
            "HC-09",
            "F1 C-DRAG-RFP (RFP thrust max as recorded, F1-P-11)",
            None,
            "intake-face drag at every orbit state".into(),
            "<=",
            "N",
            "drag_intake_max_N",
            "upstream (evaluable now; necessary, not sufficient)",
            false,
        ),
        (
            "HC-10",
            "A9.15 RFP-compliant propellant policy",
            Some("RFP-P18-08; RFP-P17-05"),
            "ambient-air AND Xe operating capability with two separate propellant tanks / paths (1 = both \
demonstrated)"
                .into(),
            ">=",
            "-",
            "propellant_capability",
            "rfp_recorded",
            false,
        ),
        (
            "HC-11",
            "AG-12 (owner decision A9.13 S6.21 / F9-OQ-02)",
            Some("RFP-P18-06; RFP-P18-05"),
            "statewise feed-state sufficiency (mdot, P, T, composition, ripple) vs the requirement derived from the \
required thrust and a VALIDATED H-1 map (no fixed mg/s gate)"
                .into(),
            ">=",
            "-",
            "feed_state_sufficiency",
            "owner_decision_hard_statewise",
            true,
        ),
        (
            "HC-12",
            "A9.13 S6.17 / S6.12 feed-quality",
            Some("-"),
            "compressor / plenum ripple <= measured H-1 ripple tolerance".into(),
            "<=",
            "-",
            "ripple_feed_quality",
            "owner_decision_hard_constraint",
            false,
        ),
    ];
    rows.into_iter()
        .map(|(id, rvm, rfp, quantity, comparator, units, objective, category, statewise)| HardConstraint {
            id,
            rvm,
            rfp,
            quantity,
            comparator,
            limit: t.limit(id),
            units,
            objective,
            category,
            statewise,
        })
        .collect()
}

/// `_from_u13(status)`: upstream constraint status -> (constraint status, value status).
fn from_u13(st: &Value) -> (&'static str, Option<&'static str>) {
    let pairs = [
        (u13::C_MET, (C_MET, EVALUATED)),
        (u13::C_VIOLATED, (C_VIOLATED, EVALUATED)),
        (u13::C_MET_SYNTHETIC, (C_MET, SYNTHETIC_ONLY)),
        (u13::C_VIOLATED_SYNTHETIC, (C_VIOLATED, SYNTHETIC_ONLY)),
        (u13::C_MET_PARAMETRIC, (C_MET_PARAMETRIC, PARAMETRIC_ONLY)),
        (u13::C_VIOLATED_PARAMETRIC, (C_VIOLATED_PARAMETRIC, PARAMETRIC_ONLY)),
    ];
    for (k, (c, v)) in pairs {
        if eq_str(st, k) {
            return (c, Some(v));
        }
    }
    (C_NOT_EVALUATED, None)
}

/// `_cmp(v, comparator, limit)` on the numeric value.
fn cmp(v: f64, comparator: &str, limit: f64) -> bool {
    match comparator {
        ">=" => v >= limit,
        ">" => v > limit,
        "<" => v < limit,
        _ => v <= limit,
    }
}

fn row(c: &HardConstraint, rule: String, status: &str, value_status: Value, basis: String) -> Value {
    dict(vec![
        ("id", s(c.id)),
        ("rvm", s(c.rvm)),
        ("rfp", c.rfp.map_or(Value::Null, s)),
        ("quantity", s(c.quantity.clone())),
        ("rule", s(rule)),
        ("status", s(status)),
        ("value_status", value_status),
        ("basis", s(basis)),
    ])
}

fn value_status_of(rec: &Value) -> AssessResult<Value> {
    if matches!(rec, Value::Null) {
        Ok(Value::Null)
    } else {
        dget(rec, "status")
    }
}

/// `evaluate_constraints(values)`: `values` maps objective name -> objective record (or None / absent).
pub fn evaluate_constraints(t: &Thresholds, values: &Value) -> AssessResult<Value> {
    let mut out = Vec::new();
    for c in hard_constraints(t) {
        let rec = dget(values, c.objective)?;
        let present = !matches!(rec, Value::Null);
        if PRE_EVALUATED_OBJECTIVES.contains(&c.objective) {
            let (st, vst, basis) = if !present {
                let b = if c.statewise {
                    "no statewise record over the required state set (a single value never closes a statewise \
                     constraint; A9.13 S6.15 / S6.21 / A9.14 S9.7)"
                } else {
                    "measured H-1 tolerance / ripple not evaluated (A9.13 S6.17)"
                };
                (C_NOT_EVALUATED, Value::Null, b.to_string())
            } else {
                let status = dget(&rec, "status")?;
                let (st, vst) = from_u13(&status);
                let mut b = format!("upstream_a9_13 {} status {}", c.objective, py_str(&status));
                if dget(&rec, "average_hides_violation")?.truthy() {
                    b.push_str("; orbit average non-negative but a state is below zero (the statewise result governs)");
                }
                (st, vst.map_or(Value::Null, s), b)
            };
            out.push(row(&c, c.quantity.clone(), st, vst, basis));
            continue;
        }
        if c.id == "HC-05" {
            if !present || !dget(&rec, "uncertainty_basis")?.truthy() {
                out.push(row(
                    &c,
                    c.rule()?,
                    C_NOT_EVALUATED,
                    value_status_of(&rec)?,
                    "no lower uncertainty bound M_n,LB of M_n = I_e,cap / I_d,max,H1 - 1 with its uncertainty basis \
                     (fail closed: NOT_EVALUATED; a point difference I_e,cap - I_d,max never closes HC-05)"
                        .into(),
                ));
                continue;
            }
            // DIV-01 (A9.31 sec. 10): no VALIDATED_BENCH / MEASURED basis -> NOT_EVALUATED
            if !in_strs(&dget(&rec, "validation_basis")?, &HC05_VALIDATION_BASES) {
                out.push(row(&c, c.rule()?, C_NOT_EVALUATED, value_status_of(&rec)?, HC05_A9_31_BASIS.into()));
                continue;
            }
        }
        let mut st = C_NOT_EVALUATED;
        let mut basis = "no evaluable value (fail closed: never counted as satisfied)".to_string();
        let gv = if present && c.id == "HC-03" { dget(&rec, "gate_verdict")? } else { Value::Null };
        if present && c.id == "HC-03" && !matches!(gv, Value::Null) {
            let vst = dget(&rec, "status")?;
            let gvs = py_str(&gv);
            if in_strs(&vst, &[EVALUATED, SYNTHETIC_ONLY]) {
                st = if eq_str(&gv, "PASS") {
                    C_MET
                } else if eq_str(&gv, "FAIL") {
                    C_VIOLATED
                } else {
                    C_NOT_EVALUATED
                };
                basis = format!("bus_boundary_a9_v2.rfp_power_gate verdict {gvs} ({})", py_str(&vst));
            } else if eq_str(&vst, PARAMETRIC_ONLY) {
                st = if eq_str(&gv, "PASS") {
                    C_MET_PARAMETRIC
                } else if eq_str(&gv, "FAIL") {
                    C_VIOLATED_PARAMETRIC
                } else {
                    C_NOT_EVALUATED
                };
                basis = format!(
                    "bus_boundary_a9_v2.rfp_power_gate verdict {gvs} on {} ledger values: sensitivity comparison \
                     only, never counted as satisfied (fail closed)",
                    py_str(&vst)
                );
            } else {
                basis = format!(
                    "bus_boundary_a9_v2.rfp_power_gate verdict {gvs} but value status {}: not evaluable (fail closed)",
                    py_str(&vst)
                );
            }
        } else if present {
            let vst = dget(&rec, "status")?;
            let value = dget(&rec, "value")?;
            if in_strs(&vst, &[EVALUATED, PARAMETRIC_ONLY, SYNTHETIC_ONLY])
                && !matches!(value, Value::Null)
                && crate::py::float(&value)?.is_finite()
            {
                let limit = c.limit.ok_or_else(|| AssessError::new("TypeError", "limit is None"))?;
                let ok = cmp(crate::py::float(&value)?, c.comparator, limit);
                let v = fmt6g(&value)?;
                if eq_str(&vst, PARAMETRIC_ONLY) {
                    st = if ok { C_MET_PARAMETRIC } else { C_VIOLATED_PARAMETRIC };
                    basis = format!(
                        "value {v} {} ({}): sensitivity comparison only, never counted as satisfied (fail closed)",
                        c.units,
                        py_str(&vst)
                    );
                } else {
                    st = if ok { C_MET } else { C_VIOLATED };
                    basis = format!("value {v} {} ({})", c.units, py_str(&vst));
                }
            }
        }
        out.push(row(&c, c.rule()?, st, value_status_of(&rec)?, basis));
    }
    Ok(Value::List(out))
}

fn constraints_of(ev: &Value) -> AssessResult<&[Value]> {
    as_list(get(ev, "constraints")?)
}

/// `hard_constraint_partition(evaluations)` -> [admissible, excluded], each a list of [evaluation, ids not MET].
pub fn hard_constraint_partition(evaluations: &[Value]) -> AssessResult<Value> {
    let (mut adm, mut exc) = (Vec::new(), Vec::new());
    for ev in evaluations {
        let mut bad = Vec::new();
        for c in constraints_of(ev)? {
            if !eq_str(get(c, "status")?, C_MET) {
                bad.push(get(c, "id")?.clone());
            }
        }
        let pair = Value::List(vec![ev.clone(), Value::List(bad.clone())]);
        if bad.is_empty() {
            adm.push(pair);
        } else {
            exc.push(pair);
        }
    }
    Ok(Value::List(vec![Value::List(adm), Value::List(exc)]))
}

/// `constraint_met_value_kinds(evaluations)` as a sorted list.
pub fn constraint_met_value_kinds(evaluations: &[Value]) -> AssessResult<Vec<String>> {
    let mut kinds: Vec<String> = Vec::new();
    for ev in evaluations {
        for c in constraints_of(ev)? {
            if eq_str(get(c, "status")?, C_MET) {
                let vs = dget(c, "value_status")?;
                if in_strs(&vs, &[EVALUATED, SYNTHETIC_ONLY]) {
                    let k = py_str(&vs);
                    if !kinds.contains(&k) {
                        kinds.push(k);
                    }
                }
            }
        }
    }
    kinds.sort();
    Ok(kinds)
}
