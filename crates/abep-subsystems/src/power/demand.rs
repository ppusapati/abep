//! Bus demand of the flight configuration from typed upstream inputs (contract PARITY-C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY-V1,
//! rust_only_registered_interfaces).
//!
//! Loads that depend on models or evidence not yet admitted (Hall discharge power from an admitted Hall member, the
//! ICP demand, the compressor load of row 22, magnet power at a frozen coil) enter as explicit [`Upstream`] values.
//! An absent input becomes a TBD load whose `tbd_requires` names its status and reason, exactly the reference's TBD
//! semantics; no placeholder value is ever filled in. The demand status is the worst of the absent inputs and the
//! ledger's own status. No requirement threshold is applied.

use super::ledger::{ledger, Ledger, LedgerArgs};
use super::slots::{installed_slots, Slot, FLIGHT_CONFIGURATION, TBD};
use super::{PowerError, PowerResult};
use abep_types::pyjson::{Dict, Value};
use abep_types::EvalStatus;
use std::collections::BTreeMap;

/// One upstream load at a slot's load plane.
#[derive(Debug, Clone, PartialEq)]
pub enum Upstream {
    Evaluated {
        p_w: f64,
        evidence_class: String,
        source: String,
    },
    /// Not available: NOT_EVALUATED, INCOMPLETE_EVIDENCE, OUT_OF_DOMAIN or MODEL_ERROR with the reason.
    Absent {
        status: EvalStatus,
        reason: String,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SupplyPath {
    InternalBus,
    Direct,
}

impl SupplyPath {
    pub fn name(self) -> &'static str {
        match self {
            SupplyPath::InternalBus => "internal_bus",
            SupplyPath::Direct => "direct",
        }
    }
}

/// A supply efficiency (known with its evidence, or TBD with what it requires).
#[derive(Debug, Clone, PartialEq)]
pub enum Efficiency {
    Known { value: f64, evidence_class: String, source: String },
    Tbd { requires: String },
}

impl Efficiency {
    fn record(&self, path: Option<SupplyPath>) -> Value {
        let mut d = Dict::new();
        match self {
            Efficiency::Known { value, evidence_class, source } => {
                d.insert("value", Value::Float(*value));
                d.insert("evidence_class", Value::str(evidence_class.clone()));
                d.insert("source", Value::str(source.clone()));
            }
            Efficiency::Tbd { requires } => {
                d.insert("value", Value::str(TBD));
                d.insert("tbd_requires", Value::str(requires.clone()));
            }
        }
        if let Some(p) = path {
            d.insert("path", Value::str(p.name()));
        }
        Value::Dict(d)
    }
}

/// Inputs of one evaluated step of the flight configuration.
#[derive(Debug, Clone, PartialEq)]
pub struct FlightInputs {
    pub variant: Vec<Slot>,
    pub loads: BTreeMap<Slot, Upstream>,
    pub efficiencies: BTreeMap<Slot, (Efficiency, SupplyPath)>,
    pub front_end: Efficiency,
    pub label: String,
    pub power_basis: Option<String>,
}

/// Bus demand of one step.
#[derive(Debug, Clone, PartialEq)]
pub struct BusDemand {
    pub status: EvalStatus,
    pub p_bus_w: Option<f64>,
    pub p_bus_lower_bound_w: f64,
    pub reasons: Vec<String>,
    pub ledger: Ledger,
}

fn severity(s: EvalStatus) -> u8 {
    match s {
        EvalStatus::Evaluated => 0,
        EvalStatus::IncompleteEvidence => 1,
        EvalStatus::NotEvaluated => 2,
        EvalStatus::OutOfDomain => 3,
        EvalStatus::ModelError => 4,
    }
}

/// Flight ledger and bus demand of one step.
pub fn bus_demand(inp: &FlightInputs) -> PowerResult<BusDemand> {
    let variant = Value::List(inp.variant.iter().map(|s| Value::str(s.name())).collect());
    let inst = installed_slots(&Value::str(FLIGHT_CONFIGURATION), &variant)?;
    let mut loads = Dict::new();
    let mut status = EvalStatus::Evaluated;
    let mut reasons = Vec::new();
    for (slot, up) in &inp.loads {
        if !inst.contains(slot) {
            return Err(PowerError::new(
                "ModelError",
                format!("upstream load for {} which is not installed", slot.name()),
            ));
        }
        let mut d = Dict::new();
        match up {
            Upstream::Evaluated { p_w, evidence_class, source } => {
                d.insert("P_W", Value::Float(*p_w));
                d.insert("evidence_class", Value::str(evidence_class.clone()));
                d.insert("source", Value::str(source.clone()));
            }
            Upstream::Absent { status: s, reason } => {
                if *s == EvalStatus::Evaluated {
                    return Err(PowerError::new(
                        "ModelError",
                        format!("{}: an absent input cannot be EVALUATED", slot.name()),
                    ));
                }
                d.insert("P_W", Value::str(TBD));
                d.insert("tbd_requires", Value::str(format!("{s}: {reason}")));
                if severity(*s) > severity(status) {
                    status = *s;
                }
                reasons.push(format!("{}: {s}: {reason}", slot.name()));
            }
        }
        if *slot == Slot::IcpRfSource {
            d.insert("plane", Value::str("generator_dc_input"));
        }
        loads.insert(slot.name(), Value::Dict(d));
    }
    let mut effs = Dict::new();
    for (slot, (e, p)) in &inp.efficiencies {
        effs.insert(slot.name(), e.record(Some(*p)));
    }
    let mut args = LedgerArgs::new(Value::Dict(loads), Value::Dict(effs), inp.front_end.record(None));
    args.variant = variant;
    args.label = Value::str(inp.label.clone());
    args.power_basis = inp.power_basis.clone().map_or(Value::Null, Value::str);
    let led = ledger(&args)?;
    let ls = led.status.eval_status();
    if severity(ls) > severity(status) {
        status = ls;
    }
    if ls != EvalStatus::Evaluated {
        reasons.push(format!("ledger {} ({} TBD terms)", led.status.as_str(), led.tbd.len()));
    }
    Ok(BusDemand { status, p_bus_w: led.p_bus_w, p_bus_lower_bound_w: led.p_bus_lower_bound_w, reasons, ledger: led })
}
