//! Spacecraft-side DC bus-power ledger of one configuration in one evaluated step (`ledger` of
//! `abep_sim/bus_boundary_a9_v2.py`, v1 code rebound to v2).
//!
//! Every load and efficiency is a caller record carrying an evidence class and a source, or an explicit `"TBD"` with
//! what it requires; there is no default load or efficiency. P_bus = P_W / (eta_slot * eta_front_end) for
//! `internal_bus` slots and P_W / eta_slot for `direct` slots. A slot at exactly 0 W draws exactly 0 W. Status:
//! `COMPLETE`, `PARTIAL_BOUNDARY` (compressor load TBD, row 22) or `INCOMPLETE_EVIDENCE` (any other TBD); when not
//! complete, P_bus is unknown and only the rigorous lower bound (TBD loads 0 W, TBD efficiencies 1) is reported.
//!
//! The record checks run on the Python-shaped JSON values, in the reference order and with its refusal texts, so a
//! malformed record is refused exactly as the reference refuses it (CLAUDE.md rule 3).

use super::pyfmt::{check_keys, fsum, is_real, nonempty, real, repr_str_list};
use super::slots::{
    installed_slots, Group, Slot, BOUNDARY_VERSION, EVIDENCE_CLASSES, GATE_MEASUREMENT_KEYS, GATE_MIN_BANDWIDTH_HZ,
    GATE_MIN_SAMPLE_RATE_SA_S, INTERNAL_BUS_V, PATHS, POWER_BASES, TBD,
};
use super::{PowerError, PowerResult};
use abep_types::pyjson::{float_repr, py_repr, py_repr_str, Dict, Value};
use abep_types::EvalStatus;

const REL_TOL: f64 = 1e-12;

fn berr(m: String) -> PowerError {
    PowerError::boundary(m)
}

/// Ledger status (reference vocabulary).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LedgerStatus {
    Complete,
    PartialBoundary,
    IncompleteEvidence,
}

impl LedgerStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            LedgerStatus::Complete => "COMPLETE",
            LedgerStatus::PartialBoundary => "PARTIAL_BOUNDARY",
            LedgerStatus::IncompleteEvidence => "INCOMPLETE_EVIDENCE",
        }
    }

    /// Fail-closed status of the bus demand the ledger represents: only a COMPLETE ledger is EVALUATED.
    pub fn eval_status(self) -> EvalStatus {
        match self {
            LedgerStatus::Complete => EvalStatus::Evaluated,
            LedgerStatus::PartialBoundary | LedgerStatus::IncompleteEvidence => EvalStatus::IncompleteEvidence,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ItemState {
    NotInstalled,
    Off,
    On,
}

impl ItemState {
    pub fn as_str(self) -> &'static str {
        match self {
            ItemState::NotInstalled => "NOT_INSTALLED",
            ItemState::Off => "OFF",
            ItemState::On => "ON",
        }
    }
}

/// A validated load record at the slot's load plane.
#[derive(Debug, Clone, PartialEq)]
pub enum LoadRecord {
    Known { p_w: f64, evidence_class: String, source: String },
    Tbd { requires: String },
}

/// A validated supply-efficiency record (front end: `path` None).
#[derive(Debug, Clone, PartialEq)]
pub struct EfficiencyRecord {
    pub value: Option<f64>,
    pub path: Option<String>,
    pub tbd_requires: Option<String>,
    pub evidence_class: Option<String>,
    pub source: Option<String>,
}

/// The validated gate-measurement conformance record (A9.1 OQ-A902-01).
#[derive(Debug, Clone, PartialEq)]
pub struct GateMeasurement {
    pub sample_rate_sa_s: f64,
    pub bandwidth_hz: f64,
    pub anti_alias_documented: bool,
    pub synchronized: bool,
    pub source: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct TbdTerm {
    pub slot: Slot,
    pub what: &'static str,
    pub requires: String,
}

/// One slot row of a ledger.
#[derive(Debug, Clone, PartialEq)]
pub struct Item {
    pub slot: Slot,
    pub state: ItemState,
    /// Load-plane power; `None` when TBD.
    pub p_w: Option<f64>,
    pub efficiency: Option<f64>,
    pub path: Option<String>,
    /// Spacecraft-side draw; `None` when a load or an efficiency on its path is TBD.
    pub p_bus_w: Option<f64>,
    pub p_loss_w: Option<f64>,
    /// Lower bound of the spacecraft-side draw (installed slots only).
    pub lower_bound_w: Option<f64>,
    pub evidence_class: Option<String>,
    pub source: Option<String>,
    pub efficiency_evidence_class: Option<String>,
    pub efficiency_source: Option<String>,
    /// Front-end efficiency applied to this slot (1 for direct slots); `None` when the front end is TBD.
    pub eta_front_end: Option<f64>,
}

impl Item {
    pub fn installed(&self) -> bool {
        self.state != ItemState::NotInstalled
    }

    pub fn to_value(&self) -> Value {
        let mut d = Dict::new();
        d.insert("slot", Value::str(self.slot.name()));
        d.insert("group", Value::str(self.slot.group().name()));
        d.insert("state", Value::str(self.state.as_str()));
        if self.state == ItemState::NotInstalled {
            d.insert("P_W", Value::Float(0.0));
            d.insert("efficiency", Value::Float(1.0));
            d.insert("path", Value::Null);
            d.insert("P_bus_W", Value::Float(0.0));
            d.insert("P_loss_W", Value::Float(0.0));
            d.insert("evidence_class", Value::Null);
            d.insert("source", Value::Null);
            return Value::Dict(d);
        }
        d.insert("P_W", opt_f(self.p_w));
        d.insert("efficiency", opt_f(self.efficiency));
        d.insert("path", opt_s(&self.path));
        d.insert("P_bus_W", opt_f(self.p_bus_w));
        d.insert("P_loss_W", opt_f(self.p_loss_w));
        d.insert("lower_bound_W", opt_f(self.lower_bound_w));
        d.insert("evidence_class", opt_s(&self.evidence_class));
        d.insert("source", opt_s(&self.source));
        d.insert("efficiency_evidence_class", opt_s(&self.efficiency_evidence_class));
        d.insert("efficiency_source", opt_s(&self.efficiency_source));
        // The A9.1 conservative-booking rule exists only for the ground-reference C1 slot; a flight slot is never
        // booked.
        d.insert("booked_conservative", Value::Bool(false));
        d.insert("booked_tbd_requires", Value::Null);
        Value::Dict(d)
    }
}

pub(crate) fn opt_f(x: Option<f64>) -> Value {
    x.map_or(Value::Null, Value::Float)
}

pub(crate) fn opt_s(x: &Option<String>) -> Value {
    x.as_ref().map_or(Value::Null, |s| Value::str(s.clone()))
}

/// A bus_power_boundary_a9_v2 ledger of one evaluated step.
#[derive(Debug, Clone, PartialEq)]
pub struct Ledger {
    pub configuration: String,
    /// `list(variant)` as passed.
    pub variant: Vec<Value>,
    pub label: Value,
    pub power_basis: Option<String>,
    pub gate_measurement: Option<GateMeasurement>,
    pub gate_measurement_conformant: bool,
    pub status: LedgerStatus,
    /// Known spacecraft-side total (COMPLETE only).
    pub p_bus_w: Option<f64>,
    pub p_bus_lower_bound_w: f64,
    pub residual_w: Option<f64>,
    pub tbd: Vec<TbdTerm>,
    pub load_evidence_classes: Vec<String>,
    pub measured_only: bool,
    pub front_end: EfficiencyRecord,
    pub items: Vec<Item>,
}

impl Ledger {
    pub fn item(&self, slot: Slot) -> &Item {
        self.items.iter().find(|i| i.slot == slot).expect("every flight slot has an item")
    }

    pub fn to_value(&self) -> Value {
        let mut d = Dict::new();
        d.insert("boundary_version", Value::str(BOUNDARY_VERSION));
        d.insert("configuration", Value::str(self.configuration.clone()));
        d.insert("variant", Value::List(self.variant.clone()));
        d.insert("label", self.label.clone());
        d.insert("power_basis", opt_s(&self.power_basis));
        d.insert(
            "gate_measurement",
            match &self.gate_measurement {
                None => Value::Null,
                Some(g) => {
                    let mut m = Dict::new();
                    m.insert("sample_rate_Sa_s", Value::Float(g.sample_rate_sa_s));
                    m.insert("bandwidth_Hz", Value::Float(g.bandwidth_hz));
                    m.insert("anti_alias_documented", Value::Bool(g.anti_alias_documented));
                    m.insert("synchronized", Value::Bool(g.synchronized));
                    m.insert("source", Value::str(g.source.clone()));
                    Value::Dict(m)
                }
            },
        );
        d.insert("gate_measurement_conformant", Value::Bool(self.gate_measurement_conformant));
        d.insert("status", Value::str(self.status.as_str()));
        d.insert("P_bus_W", opt_f(self.p_bus_w));
        d.insert("P_bus_lower_bound_W", Value::Float(self.p_bus_lower_bound_w));
        d.insert("residual_W", opt_f(self.residual_w));
        d.insert(
            "tbd",
            Value::List(
                self.tbd
                    .iter()
                    .map(|t| {
                        let mut m = Dict::new();
                        m.insert("slot", Value::str(t.slot.name()));
                        m.insert("what", Value::str(t.what));
                        m.insert("requires", Value::str(t.requires.clone()));
                        Value::Dict(m)
                    })
                    .collect(),
            ),
        );
        d.insert(
            "load_evidence_classes",
            Value::List(self.load_evidence_classes.iter().map(|c| Value::str(c.clone())).collect()),
        );
        d.insert("booked_tbd_slots", Value::List(vec![]));
        d.insert("measured_only", Value::Bool(self.measured_only));
        let mut fe = Dict::new();
        fe.insert("efficiency", opt_f(self.front_end.value));
        fe.insert("evidence_class", opt_s(&self.front_end.evidence_class));
        fe.insert("source", opt_s(&self.front_end.source));
        fe.insert("internal_bus_V", Value::Float(INTERNAL_BUS_V));
        d.insert("front_end", Value::Dict(fe));
        d.insert("items", Value::List(self.items.iter().map(Item::to_value).collect()));
        Value::Dict(d)
    }
}

/// `_gate_measurement(rec)`: (record, conformant).
pub fn gate_measurement(rec: &Value) -> PowerResult<(Option<GateMeasurement>, bool)> {
    let d = match rec {
        Value::Null => return Ok((None, false)),
        Value::Dict(d) => d,
        _ => return Err(berr("gate_measurement must be a mapping".into())),
    };
    check_keys(d, &GATE_MEASUREMENT_KEYS, "gate_measurement", "BoundaryA9Error")?;
    let missing: Vec<&str> = GATE_MEASUREMENT_KEYS.iter().copied().filter(|k| !d.contains_key(k)).collect();
    if !missing.is_empty() {
        return Err(berr(format!("gate_measurement lacks {} (no default)", repr_str_list(&missing))));
    }
    let fs = real(d.get("sample_rate_Sa_s").unwrap(), "gate_measurement.sample_rate_Sa_s", "BoundaryA9Error")?;
    let bw = real(d.get("bandwidth_Hz").unwrap(), "gate_measurement.bandwidth_Hz", "BoundaryA9Error")?;
    let mut flags = [false; 2];
    for (i, k) in ["anti_alias_documented", "synchronized"].iter().enumerate() {
        match d.get(k) {
            Some(Value::Bool(b)) => flags[i] = *b,
            _ => return Err(berr(format!("gate_measurement.{k} must be a bool"))),
        }
    }
    let source = nonempty(d, "source", "gate_measurement", "BoundaryA9Error")?;
    let ok = fs >= GATE_MIN_SAMPLE_RATE_SA_S && bw >= GATE_MIN_BANDWIDTH_HZ && flags[0] && flags[1];
    Ok((
        Some(GateMeasurement {
            sample_rate_sa_s: fs,
            bandwidth_hz: bw,
            anti_alias_documented: flags[0],
            synchronized: flags[1],
            source,
        }),
        ok,
    ))
}

fn evidence_class(rec: &Dict, what: &str) -> PowerResult<String> {
    match rec.get("evidence_class") {
        Some(Value::Str(s)) if EVIDENCE_CLASSES.contains(&s.as_str()) => Ok(s.clone()),
        other => Err(berr(format!(
            "{what}: evidence_class must be one of {}, got {}",
            repr_str_list(&EVIDENCE_CLASSES),
            other.map_or("None".to_string(), py_repr)
        ))),
    }
}

/// `_load_record(slot, rec)`. The ground-reference booked-power branch (A9.1, C1 only) does not exist
/// here: a `booked_W` key is an unexpected key (contract DIV-A03).
pub fn load_record(slot: Slot, rec: &Value) -> PowerResult<LoadRecord> {
    let what = format!("load of {}", py_repr_str(slot.name()));
    let d = match rec {
        Value::Dict(d) => d,
        other => {
            return Err(berr(format!(
                "{what} must be a record {{'P_W', 'evidence_class', 'source'}} or {{'P_W': 'TBD', 'tbd_requires'}}, \
                 got {}",
                other.type_name()
            )))
        }
    };
    let Some(p) = d.get("P_W") else {
        return Err(berr(format!("{what}: 'P_W' missing (no default)")));
    };
    let rf = slot == Slot::IcpRfSource;
    if rf {
        let plane = d.get("plane");
        if plane.and_then(Value::as_str) != Some("generator_dc_input") {
            return Err(berr(format!(
                "{what}: plane must be 'generator_dc_input' (got {}); only the RF generator DC input crosses the bus \
                 boundary, forward/reflected/delivered RF power are measurement quantities (row 72)",
                plane.map_or("None".to_string(), py_repr)
            )));
        }
    } else if d.contains_key("plane") {
        return Err(berr(format!("{what}: 'plane' is defined only for icp_rf_source")));
    }
    if let Value::Str(s) = p {
        if s != TBD {
            return Err(berr(format!("{what}: string value must be exactly 'TBD', got {}", py_repr_str(s))));
        }
        let allowed: &[&str] = if rf { &["P_W", "tbd_requires", "plane"] } else { &["P_W", "tbd_requires"] };
        check_keys(d, allowed, &what, "BoundaryA9Error")?;
        return Ok(LoadRecord::Tbd { requires: nonempty(d, "tbd_requires", &what, "BoundaryA9Error")? });
    }
    let allowed: &[&str] =
        if rf { &["P_W", "evidence_class", "source", "plane"] } else { &["P_W", "evidence_class", "source"] };
    check_keys(d, allowed, &what, "BoundaryA9Error")?;
    let x = real(p, &what, "BoundaryA9Error")?;
    if x < 0.0 {
        return Err(berr(format!("{what} must be >= 0 W, got {}", float_repr(x))));
    }
    let ec = evidence_class(d, &what)?;
    Ok(LoadRecord::Known { p_w: x, evidence_class: ec, source: nonempty(d, "source", &what, "BoundaryA9Error")? })
}

/// `_eff_record(what, rec, need_path)`.
pub fn efficiency_record(what: &str, rec: &Value, need_path: bool) -> PowerResult<EfficiencyRecord> {
    let d = match rec {
        Value::Dict(d) => d,
        other => {
            return Err(berr(format!(
                "{what} must be a record {{'value', 'evidence_class', 'source', 'path'}}, got {}",
                other.type_name()
            )))
        }
    };
    let path = d.get("path");
    let path_s = path.and_then(Value::as_str).filter(|p| PATHS.contains(p)).map(str::to_string);
    if need_path && path_s.is_none() {
        return Err(berr(format!(
            "{what}: path must be one of {}, got {}",
            repr_str_list(&PATHS),
            path.map_or("None".to_string(), py_repr)
        )));
    }
    let Some(v) = d.get("value") else {
        return Err(berr(format!("{what}: 'value' missing (no default)")));
    };
    let path_out = if need_path { path_s } else { None };
    if let Value::Str(s) = v {
        if s != TBD {
            return Err(berr(format!("{what}: string value must be exactly 'TBD', got {}", py_repr_str(s))));
        }
        let allowed: &[&str] = if need_path { &["value", "tbd_requires", "path"] } else { &["value", "tbd_requires"] };
        check_keys(d, allowed, what, "BoundaryA9Error")?;
        return Ok(EfficiencyRecord {
            value: None,
            path: path_out,
            tbd_requires: Some(nonempty(d, "tbd_requires", what, "BoundaryA9Error")?),
            evidence_class: None,
            source: None,
        });
    }
    let allowed: &[&str] =
        if need_path { &["value", "evidence_class", "source", "path"] } else { &["value", "evidence_class", "source"] };
    check_keys(d, allowed, what, "BoundaryA9Error")?;
    let x = real(v, what, "BoundaryA9Error")?;
    if !(0.0 < x && x <= 1.0) {
        return Err(berr(format!("{what} must be in (0, 1], got {}", float_repr(x))));
    }
    let ec = evidence_class(d, what)?;
    Ok(EfficiencyRecord {
        value: Some(x),
        path: path_out,
        tbd_requires: None,
        evidence_class: Some(ec),
        source: Some(nonempty(d, "source", what, "BoundaryA9Error")?),
    })
}

/// `float(p) != 0.0` style check of a not-installed record value: refused unless an exact real `target`.
fn exact_real(v: Option<&Value>, target: f64) -> PowerResult<bool> {
    match v {
        Some(x) if is_real(x) => Ok(x.to_f64().map_err(PowerError::from)? == target),
        _ => Ok(false),
    }
}

/// `_not_installed_ok(slot, loads, effs, config)`: a not-installed slot is omitted, or passed as a full schema-valid
/// record with exactly 0 W / efficiency 1.
fn not_installed_ok(slot: Slot, loads: &Dict, effs: &Dict) -> PowerResult<()> {
    let name = py_repr_str(slot.name());
    if let Some(rec) = loads.get(slot.name()) {
        let p = match rec {
            Value::Dict(d) => d.get("P_W"),
            other => Some(other),
        };
        if !exact_real(p, 0.0)? {
            return Err(berr(format!(
                "slot {name} is not installed in 'hall_icp_neutralizer' with this variant; it may only be omitted or \
                 passed as exactly 0 W (got {}) - no hidden consumption",
                p.map_or("None".to_string(), py_repr)
            )));
        }
        load_record(slot, rec)?;
    }
    if let Some(rec) = effs.get(slot.name()) {
        let v = match rec {
            Value::Dict(d) => d.get("value"),
            other => Some(other),
        };
        if !exact_real(v, 1.0)? {
            return Err(berr(format!(
                "slot {name} is not installed in 'hall_icp_neutralizer'; its efficiency may only be omitted or \
                 exactly 1 (got {})",
                v.map_or("None".to_string(), py_repr)
            )));
        }
        efficiency_record(&format!("efficiency of {name}"), rec, true)?;
    }
    Ok(())
}

/// The arguments of `ledger(config, loads, efficiencies, front_end, variant, label, power_basis, gate_measurement)`
/// as Python-shaped JSON values.
#[derive(Debug, Clone)]
pub struct LedgerArgs {
    pub config: Value,
    pub loads: Value,
    pub efficiencies: Value,
    pub front_end: Value,
    pub variant: Value,
    pub label: Value,
    pub power_basis: Value,
    pub gate_measurement: Value,
}

impl LedgerArgs {
    /// Arguments with the reference defaults (variant (), label "", no basis, no gate measurement).
    pub fn new(loads: Value, efficiencies: Value, front_end: Value) -> Self {
        LedgerArgs {
            config: Value::str(super::slots::FLIGHT_CONFIGURATION),
            loads,
            efficiencies,
            front_end,
            variant: Value::List(vec![]),
            label: Value::str(""),
            power_basis: Value::Null,
            gate_measurement: Value::Null,
        }
    }
}

/// `ledger(...)` of the active boundary.
pub fn ledger(a: &LedgerArgs) -> PowerResult<Ledger> {
    let power_basis = match &a.power_basis {
        Value::Null => None,
        Value::Str(s) if POWER_BASES.contains(&s.as_str()) => Some(s.clone()),
        other => {
            return Err(berr(format!(
                "power_basis must be one of {} or None, got {}",
                repr_str_list(&POWER_BASES),
                py_repr(other)
            )))
        }
    };
    let (gm, gm_ok) = gate_measurement(&a.gate_measurement)?;
    let inst = installed_slots(&a.config, &a.variant)?;
    let loads = match &a.loads {
        Value::Dict(d) => d,
        other => return Err(berr(format!("loads must be a mapping slot -> record, got {}", other.type_name()))),
    };
    let effs = match &a.efficiencies {
        Value::Dict(d) => d,
        other => return Err(berr(format!("efficiencies must be a mapping slot -> record, got {}", other.type_name()))),
    };
    let mut unknown: Vec<&String> = loads.keys().chain(effs.keys()).filter(|k| Slot::from_name(k).is_none()).collect();
    unknown.sort();
    unknown.dedup();
    if !unknown.is_empty() {
        return Err(berr(format!(
            "unknown slot(s) {}; {BOUNDARY_VERSION} slots are {}",
            repr_str_list(&unknown),
            repr_str_list(&super::slots::slot_names())
        )));
    }
    let missing_l: Vec<&str> = inst.iter().filter(|s| !loads.contains_key(s.name())).map(|s| s.name()).collect();
    let missing_e: Vec<&str> = inst.iter().filter(|s| !effs.contains_key(s.name())).map(|s| s.name()).collect();
    let variant: Vec<Value> = a.variant.as_list().map(|l| l.to_vec()).unwrap_or_default();
    if !missing_l.is_empty() || !missing_e.is_empty() {
        return Err(berr(format!(
            "'hall_icp_neutralizer'{}: installed slots need an explicit load and efficiency (no default); missing \
             loads {}, missing efficiencies {}",
            py_repr(&Value::List(variant.clone())),
            repr_str_list(&missing_l),
            repr_str_list(&missing_e)
        )));
    }
    let fe = efficiency_record("front_end efficiency", &a.front_end, false)?;

    let mut items = Vec::with_capacity(Slot::ALL.len());
    let mut tbd = Vec::new();
    for slot in Slot::ALL {
        if !inst.contains(&slot) {
            not_installed_ok(slot, loads, effs)?;
            items.push(Item {
                slot,
                state: ItemState::NotInstalled,
                p_w: Some(0.0),
                efficiency: Some(1.0),
                path: None,
                p_bus_w: Some(0.0),
                p_loss_w: Some(0.0),
                lower_bound_w: None,
                evidence_class: None,
                source: None,
                efficiency_evidence_class: None,
                efficiency_source: None,
                eta_front_end: Some(1.0),
            });
            continue;
        }
        let l = load_record(slot, loads.get(slot.name()).unwrap())?;
        let e = efficiency_record(
            &format!("efficiency of {}", py_repr_str(slot.name())),
            effs.get(slot.name()).unwrap(),
            true,
        )?;
        let internal = e.path.as_deref() == Some("internal_bus");
        let eta_fe = if internal { fe.value } else { Some(1.0) };
        let (p_w, ec, src) = match &l {
            LoadRecord::Known { p_w, evidence_class, source } => {
                (Some(*p_w), Some(evidence_class.clone()), Some(source.clone()))
            }
            LoadRecord::Tbd { requires } => {
                tbd.push(TbdTerm { slot, what: "load", requires: requires.clone() });
                (None, None, None)
            }
        };
        if e.value.is_none() && p_w != Some(0.0) {
            tbd.push(TbdTerm { slot, what: "efficiency", requires: e.tbd_requires.clone().unwrap() });
        }
        if internal && fe.value.is_none() && p_w.is_some_and(|p| p != 0.0) {
            tbd.push(TbdTerm { slot, what: "front_end efficiency", requires: fe.tbd_requires.clone().unwrap() });
        }
        let (p_bus, lb, state) = match p_w {
            Some(0.0) => (Some(0.0), 0.0, ItemState::Off),
            None => (None, 0.0, ItemState::On),
            Some(p) => {
                let lb = p / e.value.unwrap_or(1.0) / eta_fe.unwrap_or(1.0);
                let pb = match (e.value, eta_fe) {
                    (Some(v), Some(f)) => Some(p / v / f),
                    _ => None,
                };
                if !lb.is_finite() {
                    return Err(berr(format!("bus draw of {} overflows", py_repr_str(slot.name()))));
                }
                (pb, lb, ItemState::On)
            }
        };
        items.push(Item {
            slot,
            state,
            p_w,
            efficiency: e.value,
            path: e.path.clone(),
            p_bus_w: p_bus,
            p_loss_w: match (p_bus, p_w) {
                (Some(b), Some(p)) => Some(b - p),
                _ => None,
            },
            lower_bound_w: Some(lb),
            evidence_class: ec,
            source: src,
            efficiency_evidence_class: e.evidence_class.clone(),
            efficiency_source: e.source.clone(),
            eta_front_end: eta_fe,
        });
    }

    let lower = fsum(items.iter().map(|it| it.lower_bound_w.unwrap_or(0.0)))?;
    if !lower.is_finite() {
        return Err(berr("total bus draw overflows".into()));
    }
    let status = if tbd.iter().any(|t| t.slot == Slot::Compressor && t.what == "load") {
        LedgerStatus::PartialBoundary
    } else if !tbd.is_empty() {
        LedgerStatus::IncompleteEvidence
    } else {
        LedgerStatus::Complete
    };
    let (mut p_total, mut residual) = (None, None);
    if status == LedgerStatus::Complete {
        let source_total = fsum(items.iter().map(|it| it.p_bus_w.unwrap()))?;
        let dest_total = fsum(items.iter().filter_map(|it| it.p_w.filter(|p| *p != 0.0)))?
            + fsum(items.iter().map(|it| it.p_loss_w.unwrap()))?;
        let r = dest_total - source_total;
        if r.abs() > REL_TOL * source_total.max(1.0) {
            return Err(PowerError::new(
                "RuntimeError",
                format!("bookkeeping identity failed: residual {} W ({BOUNDARY_VERSION})", float_repr(r)),
            ));
        }
        p_total = Some(dest_total);
        residual = Some(r);
    }
    let mut classes: Vec<String> = items.iter().filter_map(|it| it.evidence_class.clone()).collect();
    classes.sort();
    classes.dedup();
    let measured_only = classes.len() == 1 && classes[0] == "measured";
    let _ = Group::Hall;
    Ok(Ledger {
        configuration: super::slots::FLIGHT_CONFIGURATION.to_string(),
        variant,
        label: a.label.clone(),
        power_basis,
        gate_measurement: gm,
        gate_measurement_conformant: gm_ok,
        status,
        p_bus_w: p_total,
        p_bus_lower_bound_w: lower,
        residual_w: residual,
        tbd,
        load_evidence_classes: classes,
        measured_only,
        front_end: fe,
        items,
    })
}
