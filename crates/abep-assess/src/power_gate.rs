//! The RFP bus-power gate P_bus,1ms,max < limit on the steady ledger AND every start-up step
//! (`abep_sim/bus_boundary_a9_v2.py::rfp_power_gate`, the v1 code object rebound to bus_power_boundary_a9_v2; and
//! the `gate_verdict` field of `abep_sim/programme/design_synthesis.py::bus_power`; contract E5 / E6).
//!
//! A9.30 sec. 5: the limit is assessment only. It is read from the engineering constraint p_bus_max_W (HC-03); the
//! raw ledgers come from abep-subsystems::power (admitted) and are only read here.

use crate::error::{AssessError, AssessResult};
use crate::py::{dget, dget_or, dict, eq_str, float, fmt_g, get, repr_trunc, s, strs};
use crate::thresholds::Thresholds;
use abep_subsystems::power::slots::{
    BOUNDARY_VERSION, GATE_MEASUREMENT_KEYS, GATE_MIN_BANDWIDTH_HZ, GATE_MIN_SAMPLE_RATE_SA_S, GATE_WINDOW_S,
    P1MS_DEFINITION,
};
use abep_types::pyjson::{py_repr, Value};

pub const PASS_BASES: [&str; 1] = ["p_bus_1ms_max"];
pub const FAIL_BASES: [&str; 3] = ["p_bus_1ms_max", "step_average", "steady_state"];

fn boundary_error(message: impl Into<String>) -> AssessError {
    AssessError::new("BoundaryA9Error", message)
}

/// The frozen gate texts, rendered with the configured limit (W and kW).
pub struct GateTexts {
    pub limit_w: f64,
    w: String,
    kw: String,
}

impl GateTexts {
    pub fn new(limit_w: f64) -> Self {
        GateTexts { limit_w, w: fmt_g(limit_w), kw: fmt_g(limit_w / 1000.0) }
    }

    pub fn fail_basis_assumption() -> &'static str {
        "step_average / steady_state bound P_bus,1ms,max from below only when the averaging duration is a whole \
         multiple of 1 ms (exact) or much longer than 1 ms (approximate); an unstated basis gives NOT_EVALUABLE. A \
         ledger is a SUM of per-slot values: on the p_bus_1ms_max basis that sum is a rigorous bound for FAIL only when \
         the slot values are simultaneous (taken in the same 1 ms window, e.g. one system-level bus channel split by \
         slot); a sum of per-slot 1 ms maxima taken at different times is an UPPER bound (conservative for PASS) but \
         not a lower bound, so a FAIL on it must be confirmed by the system-level (bus-channel) 1 ms maximum \
         (P1MS_SUM_RULE)"
    }

    pub fn p1ms_sum_rule() -> &'static str {
        "p_bus_1ms_max ledger: FAIL requires slot values from one common 1 ms window (system-level bus-channel \
         maximum); summed non-simultaneous per-slot maxima support PASS (upper bound) but a FAIL on them is only an \
         indication until the system-level 1 ms maximum confirms it"
    }

    pub fn peak_sampled_rule(&self) -> String {
        format!(
            "an unaveraged sampled peak is a protection-analysis record, not the {} kW gate (A9.1 OQ-A902-01): \
             NOT_EVALUABLE in both directions; whether a conformant sampled peak below {} W may bound P_bus,1ms,max is \
             the OPEN owner question OQ-A910-03 (not implemented before the owner rules)",
            self.kw, self.w
        )
    }

    /// `TRANSIENT_WINDOW` (= GATE_DEFINITION).
    pub fn transient_window(&self) -> Value {
        dict(vec![
            ("status", s("FROZEN_A9_ENGINEERING_DEFINITION")),
            ("decision", s("A9.1 OQ-A902-01 (docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json)")),
            ("quantity", s(P1MS_DEFINITION)),
            (
                "requirement",
                s(format!(
                    "P_bus,1ms,max < {} W for start-up as well as steady state, unless the official RFP later \
                     explicitly provides a different transient exception",
                    self.w
                )),
            ),
            ("window_s", Value::Float(GATE_WINDOW_S)),
            (
                "measurement",
                strs(&[
                    "spacecraft-DC propulsion boundary",
                    "all required channels synchronized",
                    "effective measurement bandwidth >= 20 kHz",
                    "sample rate >= 100 kSa/s per relevant channel or an equivalent direct spacecraft-bus power channel",
                    "anti-alias filtering documented",
                    "no step-average may be substituted for this gate",
                ]),
            ),
            ("min_bandwidth_Hz", Value::Float(GATE_MIN_BANDWIDTH_HZ)),
            ("min_sample_rate_Sa_s", Value::Float(GATE_MIN_SAMPLE_RATE_SA_S)),
            (
                "diagnostics_only",
                Value::List(vec![
                    s(format!(
                        "unaveraged sampled peak (hardware/current/voltage protection analysis; not the {} kW \
                         system-power gate)",
                        self.kw
                    )),
                    s("100 ms and 1 s averages (diagnostic/energy metrics, not substitutes)"),
                ]),
            ),
            ("pass_requires_power_basis", strs(&PASS_BASES)),
            (
                "pass_requires_gate_measurement",
                dict(vec![
                    ("keys", strs(&GATE_MEASUREMENT_KEYS)),
                    (
                        "rule",
                        s("sample_rate_Sa_s >= 100e3, bandwidth_Hz >= 20e3, anti_alias_documented and synchronized \
                           True, non-empty source"),
                    ),
                ]),
            ),
            ("fail_bases", strs(&FAIL_BASES)),
            ("fail_basis_assumption", s(Self::fail_basis_assumption())),
            ("p1ms_sum_rule", s(Self::p1ms_sum_rule())),
            ("peak_sampled_rule", s(self.peak_sampled_rule())),
            (
                "note",
                s("an A9 engineering definition pending authoritative RFP wording; the 1 ms window is not an ECSS \
                   requirement (A9.1 preamble); replaces the interim 'PASS only if peak_sampled' rule (a peak_sampled \
                   ledger no longer PASSes)"),
            ),
            ("item", s("A902-03")),
            ("owner_question", s("OQ-A902-01 (ANSWERED_BY_A9_1)")),
            ("freeze_point", s("NOW")),
        ])
    }
}

/// `_verdict_below(value, lower, limit, strict=True, "PASS", "FAIL")`.
fn verdict_below(value: &Value, lower: &Value, limit: f64) -> AssessResult<&'static str> {
    if !matches!(value, Value::Null) {
        return Ok(if float(value)? < limit { "PASS" } else { "FAIL" });
    }
    Ok(if float(lower)? >= limit { "FAIL" } else { "NOT_EVALUABLE" })
}

/// `rfp_power_gate(steady, startup_steps)` with the configured HC-03 limit.
pub fn rfp_power_gate(t: &Thresholds, steady: &Value, startup_steps: &Value) -> AssessResult<Value> {
    let limit = t.limit("HC-03").ok_or_else(|| AssessError::new("ConfigurationError", "HC-03 limit missing"))?;
    rfp_power_gate_with_limit(limit, steady, startup_steps)
}

pub fn rfp_power_gate_with_limit(limit: f64, steady: &Value, startup_steps: &Value) -> AssessResult<Value> {
    let tx = GateTexts::new(limit);
    let steps = match startup_steps {
        Value::List(l) if !l.is_empty() => l,
        _ => {
            return Err(boundary_error(format!(
                "rfp_power_gate needs a non-empty sequence of start-up step ledgers (row 108: start-up transients stay \
                 below {} kW unless the official RFP allows an exception)",
                tx.kw
            )))
        }
    };
    let mut rows = Vec::new();
    let all: Vec<(&str, &Value)> =
        std::iter::once(("steady", steady)).chain(steps.iter().map(|x| ("startup", x))).collect();
    for (role, led) in all {
        if !matches!(led, Value::Dict(_)) || !eq_str(&dget(led, "boundary_version")?, BOUNDARY_VERSION) {
            return Err(boundary_error(format!("not a {BOUNDARY_VERSION} ledger: {}", repr_trunc(led, 80))));
        }
        let p = get(led, "P_bus_W")?;
        let lower = get(led, "P_bus_lower_bound_W")?;
        let mut v = verdict_below(p, lower, limit)?;
        let basis = dget(led, "power_basis")?;
        let in_bases = |xs: &[&str]| xs.iter().any(|b| eq_str(&basis, b));
        let mut note = Value::Null;
        if eq_str(&basis, "peak_sampled") && (v == "PASS" || v == "FAIL") {
            v = "NOT_EVALUABLE";
            note = s(tx.peak_sampled_rule());
        } else if v == "PASS" && !in_bases(&PASS_BASES) {
            v = "NOT_EVALUABLE";
            note = s(format!(
                "value basis {} is not P_bus,1ms,max: no step average is substituted for the gate (A9.1 OQ-A902-01)",
                py_repr(&basis)
            ));
        } else if v == "PASS" && !dget(led, "gate_measurement_conformant")?.truthy() {
            v = "NOT_EVALUABLE";
            note = s("declared p_bus_1ms_max without a conformant gate_measurement record (>= 100 kSa/s, >= 20 kHz, \
                      anti-alias documented, synchronized channels; A9.1 OQ-A902-01)");
        } else if v == "FAIL" && eq_str(&basis, "p_bus_1ms_max") {
            note = s(GateTexts::p1ms_sum_rule());
        } else if v == "FAIL" && !in_bases(&FAIL_BASES) {
            v = "NOT_EVALUABLE";
            note = s("unstated power basis: the value is not shown to bound P_bus,1ms,max from below (it could be an \
                      unaveraged peak, A9.1 OQ-A902-01)");
        }
        let booked = match dget_or(led, "booked_tbd_slots", Value::List(vec![]))? {
            Value::List(l) => Value::List(l),
            other => return Err(AssessError::new("TypeError", format!("booked_tbd_slots is {}", other.type_name()))),
        };
        rows.push(dict(vec![
            ("role", s(role)),
            ("label", get(led, "label")?.clone()),
            ("status", get(led, "status")?.clone()),
            ("power_basis", basis.clone()),
            ("gate_measurement_conformant", Value::Bool(dget(led, "gate_measurement_conformant")?.truthy())),
            ("P_bus_W", p.clone()),
            ("P_bus_lower_bound_W", lower.clone()),
            ("verdict", s(v)),
            ("note", note),
            ("measured_only", get(led, "measured_only")?.clone()),
            ("booked_tbd_slots", booked),
        ]));
    }
    let verdicts: Vec<String> = rows.iter().map(|r| crate::py::py_str(&dget(r, "verdict").unwrap())).collect();
    let overall = if verdicts.iter().any(|v| v == "FAIL") {
        "FAIL"
    } else if verdicts.iter().all(|v| v == "PASS") {
        "PASS"
    } else {
        "NOT_EVALUABLE"
    };
    let measured = rows.iter().all(|r| dget(r, "measured_only").map(|v| v.truthy()).unwrap_or(false));
    Ok(dict(vec![
        ("gate", s(format!("RFP P_bus,1ms,max < {} W (steady and start-up; A9.1 OQ-A902-01)", tx.w))),
        ("limit_W", Value::Float(limit)),
        ("strict", Value::Bool(true)),
        ("verdict", s(overall)),
        ("evidence_basis", s(if measured { "measured" } else { "includes non-measured loads (not a demonstration)" })),
        ("transient_window_frozen", Value::Bool(true)),
        ("transient_window", tx.transient_window()),
        (
            "caveat",
            s("gate definition frozen as an A9 engineering definition pending authoritative RFP wording (A9.1 \
               OQ-A902-01); a PASS on non-measured loads is not a demonstration"),
        ),
        ("rows", Value::List(rows)),
    ]))
}

/// The `gate_verdict` field of `design_synthesis.bus_power(config, compressor_P_W, supplied)`: the gate verdict of
/// the supplied ledgers ({'steady', 'startup', ...}); NOT_EVALUABLE on the official (unsupplied) path.
pub fn bus_power_gate_verdict(t: &Thresholds, supplied: &Value) -> AssessResult<Value> {
    if matches!(supplied, Value::Null) {
        return Ok(s("NOT_EVALUABLE"));
    }
    let g = rfp_power_gate(t, get(supplied, "steady")?, get(supplied, "startup")?)?;
    get(&g, "verdict").cloned()
}
