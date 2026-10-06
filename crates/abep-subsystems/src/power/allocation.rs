//! Owner-allocation arithmetic on a finished ledger (`allocation_checks` and `icp_power_allocation_check` of
//! `abep_sim/bus_boundary_a9_v2.py`): the 1350 W design allocation (row 109), the A5 1300 W context value, the 300 W
//! common allocation with its 50 W controls / thermal allowance (row 114, A9.1 OQ-A902-02) and the ICP residual
//! P_ICP,available = 1350 - P_common - P_Hall - P_other,active (A9.1 OQ-A902-03).
//!
//! These are OWNER ALLOCATIONS, not gates and not predictions. Nothing in the ledger, the start-up sequence or the
//! bus demand reads them back. The RFP requirement is not here (abep-assess, SC-WP-11).

use super::ledger::{ItemState, Ledger};
use super::pyfmt::fsum;
use super::slots::{Group, Slot};
use super::PowerResult;
use abep_types::pyjson::{Dict, Value};

/// Internal design allocation (row 109).
pub const DESIGN_ALLOCATION_W: f64 = 1350.0;
/// A5 lower allocation value, context only.
pub const A5_LOWER_ALLOCATION_W: f64 = 1300.0;
/// Common allocation including the controls / thermal allowance (row 114).
pub const COMMON_ALLOCATION_W: f64 = 300.0;
pub const CONTROLS_THERMAL_ALLOWANCE_W: f64 = 50.0;

/// `_verdict_below(value, lower, limit, strict=False, ok, bad)`.
fn verdict_below(value: Option<f64>, lower: f64, limit: f64, ok: &'static str, bad: &'static str) -> &'static str {
    match value {
        Some(v) => {
            if v <= limit {
                ok
            } else {
                bad
            }
        }
        None if lower > limit => bad,
        None => "NOT_EVALUABLE",
    }
}

fn opt(x: Option<f64>) -> Value {
    x.map_or(Value::Null, Value::Float)
}

/// Known sum (None if any term is TBD) and lower-bound sum of installed items selected by `pick`.
fn group_sum(led: &Ledger, pick: impl Fn(Slot) -> bool) -> PowerResult<(Option<f64>, f64)> {
    let its: Vec<_> = led.items.iter().filter(|it| pick(it.slot) && it.state != ItemState::NotInstalled).collect();
    let known = its.iter().all(|it| it.p_bus_w.is_some());
    let val = if known { Some(fsum(its.iter().map(|it| it.p_bus_w.unwrap()))?) } else { None };
    Ok((val, fsum(its.iter().map(|it| it.lower_bound_w.unwrap_or(0.0)))?))
}

/// `allocation_checks(led)`.
pub fn allocation_checks(led: &Ledger) -> PowerResult<Value> {
    let (c_val, c_lb) = group_sum(led, Slot::common_allocation)?;
    let (t_val, t_lb) = group_sum(led, Slot::controls_thermal)?;
    let mut design = Dict::new();
    design.insert("limit_W", Value::Float(DESIGN_ALLOCATION_W));
    design.insert("row", Value::int(109));
    design.insert(
        "verdict",
        Value::str(verdict_below(
            led.p_bus_w,
            led.p_bus_lower_bound_w,
            DESIGN_ALLOCATION_W,
            "WITHIN_ALLOCATION",
            "EXCEEDS_ALLOCATION",
        )),
    );
    let mut a5 = Dict::new();
    a5.insert("limit_W", Value::Float(A5_LOWER_ALLOCATION_W));
    a5.insert("context_only", Value::Bool(true));
    a5.insert(
        "verdict",
        Value::str(verdict_below(
            led.p_bus_w,
            led.p_bus_lower_bound_w,
            A5_LOWER_ALLOCATION_W,
            "WITHIN_ALLOCATION",
            "EXCEEDS_ALLOCATION",
        )),
    );
    let mut common = Dict::new();
    common.insert("limit_W", Value::Float(COMMON_ALLOCATION_W));
    common.insert("row", Value::int(114));
    common.insert("P_bus_W", opt(c_val));
    common.insert("P_bus_lower_bound_W", Value::Float(c_lb));
    common.insert(
        "verdict",
        Value::str(verdict_below(c_val, c_lb, COMMON_ALLOCATION_W, "WITHIN_ALLOCATION", "EXCEEDS_ALLOCATION")),
    );
    let mut ct = Dict::new();
    ct.insert("allowance_W", Value::Float(CONTROLS_THERMAL_ALLOWANCE_W));
    ct.insert("row", Value::int(114));
    ct.insert("P_bus_W", opt(t_val));
    ct.insert("P_bus_lower_bound_W", Value::Float(t_lb));
    ct.insert(
        "verdict",
        Value::str(verdict_below(t_val, t_lb, CONTROLS_THERMAL_ALLOWANCE_W, "WITHIN_ALLOWANCE", "EXCEEDS_ALLOWANCE")),
    );
    let mut out = Dict::new();
    out.insert("kind", Value::str("OWNER_ALLOCATION_CHECK (not a gate, not a prediction)"));
    out.insert("design_allocation", Value::Dict(design));
    out.insert("a5_lower_allocation", Value::Dict(a5));
    out.insert("common_allocation", Value::Dict(common));
    out.insert("controls_thermal_allowance", Value::Dict(ct));
    Ok(Value::Dict(out))
}

#[derive(Clone, Copy, PartialEq)]
enum Part {
    Common,
    Hall,
    Icp,
    Other,
}

fn part(s: Slot) -> Part {
    if s.common_allocation() {
        Part::Common
    } else {
        match s.group() {
            Group::Hall => Part::Hall,
            Group::Icp => Part::Icp,
            _ => Part::Other,
        }
    }
}

/// `icp_power_allocation_check(led)` (the ledger is a `hall_icp_neutralizer` ledger by construction).
pub fn icp_power_allocation_check(led: &Ledger) -> PowerResult<Value> {
    let s = |p: Part| group_sum(led, move |slot| part(slot) == p);
    let (common, hall, icp, other) = (s(Part::Common)?, s(Part::Hall)?, s(Part::Icp)?, s(Part::Other)?);
    let avail = match (common.0, hall.0, other.0) {
        (Some(c), Some(h), Some(o)) => Some(DESIGN_ALLOCATION_W - c - h - o),
        _ => None,
    };
    let avail_ub = DESIGN_ALLOCATION_W - common.1 - hall.1 - other.1;
    let verdict = match (avail, icp.0) {
        (Some(a), Some(v)) => {
            if v <= a {
                "WITHIN_AVAILABLE"
            } else {
                "EXCEEDS_AVAILABLE"
            }
        }
        _ if icp.1 > avail_ub => "EXCEEDS_AVAILABLE",
        _ => "NOT_EVALUABLE",
    };
    let mut d = Dict::new();
    d.insert("kind", Value::str("OWNER_ALLOCATION_CHECK (A9.1 OQ-A902-03; not a gate, not a prediction)"));
    d.insert("relation", Value::str("P_ICP,available = 1350 - P_common - P_Hall - P_other,active"));
    d.insert("design_allocation_W", Value::Float(DESIGN_ALLOCATION_W));
    d.insert("P_common_W", opt(common.0));
    d.insert("P_Hall_W", opt(hall.0));
    d.insert("P_other_active_W", opt(other.0));
    d.insert("P_ICP_available_W", opt(avail));
    d.insert("P_ICP_available_upper_bound_W", Value::Float(avail_ub));
    d.insert("P_ICP_W", opt(icp.0));
    d.insert("P_ICP_lower_bound_W", Value::Float(icp.1));
    d.insert("verdict", Value::str(verdict));
    d.insert("label", led.label.clone());
    Ok(Value::Dict(d))
}
