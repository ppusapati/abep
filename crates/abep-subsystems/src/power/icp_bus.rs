//! Consumer of the NP-ICP-NEUTRALIZER bus interface IF-ICP-BUS-v1 (crates/abep-icp `BusRecord`, read in its
//! serialized form so that this crate's provenance does not carry the not-yet-admitted ICP sources).
//!
//! Slot loads at the ledger's load planes: `icp_rf_source` <- `P_icp_rf_source_DC_W` (plane generator_dc_input),
//! `icp_matching_network` <- `P_icp_matching_DC_W`, `icp_collector_bias` <- `P_icp_collector_bias_W` (the bias-supply
//! output, the slot's load plane; the supply efficiency is the ledger's own record), and the variant slots
//! `icp_assist_magnet` / `flow_control_icp_feed` only when the ledger declares them. A key that is not CONVERGED
//! becomes an absent upstream input with its status and reasons (never a placeholder value).
//!
//! Interface finding (reported, not resolved here): the producer's `P_icp_bus_W` adds the bias-supply input
//! (P_bias / eta_bias) to the RF and match load-plane values, so it equals the ledger's ICP draw only when the RF /
//! match slot efficiencies and the front end are 1; NP-THERMAL IK-07 calls it the demand at the spacecraft DC
//! boundary. CONS-L1 therefore takes per-slot planes.

use super::demand::Upstream;
use super::slots::{Slot, BOUNDARY_VERSION, EVIDENCE_CLASSES};
use super::{PowerError, PowerResult};
use abep_types::EvalStatus;
use serde_json::Value as Json;

pub const INTERFACE_ID: &str = "IF-ICP-BUS-v1";

/// (slot, producer key) in slot order.
pub const KEY_MAP: [(Slot, &str); 5] = [
    (Slot::IcpRfSource, "P_icp_rf_source_DC_W"),
    (Slot::IcpMatchingNetwork, "P_icp_matching_DC_W"),
    (Slot::IcpCollectorBias, "P_icp_collector_bias_W"),
    (Slot::IcpAssistMagnet, "P_icp_assist_magnet_W"),
    (Slot::FlowControlIcpFeed, "P_icp_flow_control_W"),
];

fn me(m: String) -> PowerError {
    PowerError::new("ModelError", m)
}

fn producer_status(s: &str) -> Option<EvalStatus> {
    match s {
        "CONVERGED" => Some(EvalStatus::Evaluated),
        "NOT_EVALUATED" => Some(EvalStatus::NotEvaluated),
        "INCOMPLETE_EVIDENCE" => Some(EvalStatus::IncompleteEvidence),
        "OUT_OF_DOMAIN" => Some(EvalStatus::OutOfDomain),
        "MODEL_ERROR" => Some(EvalStatus::ModelError),
        _ => None,
    }
}

/// Upstream ICP loads of the installed ICP slots (`variant` = the ledger's declared variant options).
pub fn icp_upstream_loads(
    record: &Json,
    variant: &[Slot],
    evidence_class: &str,
    source: &str,
) -> PowerResult<Vec<(Slot, Upstream)>> {
    if record.get("interface").and_then(Json::as_str) != Some(INTERFACE_ID) {
        return Err(me(format!("not an {INTERFACE_ID} record (interface {:?})", record.get("interface"))));
    }
    if record.get("target_boundary").and_then(Json::as_str) != Some(BOUNDARY_VERSION) {
        return Err(me(format!(
            "{INTERFACE_ID} record targets {:?}, not the active boundary {BOUNDARY_VERSION}",
            record.get("target_boundary")
        )));
    }
    if !EVIDENCE_CLASSES.contains(&evidence_class) {
        return Err(me(format!("evidence_class {evidence_class:?} not in {EVIDENCE_CLASSES:?}")));
    }
    if source.trim().is_empty() {
        return Err(me("a source naming the producer record is required".into()));
    }
    let keys = record.get("keys").and_then(Json::as_object).ok_or_else(|| me(format!("{INTERFACE_ID}: no keys")))?;
    let mut out = Vec::new();
    for (slot, key) in KEY_MAP {
        if slot.group() == super::slots::Group::Variant && !variant.contains(&slot) {
            continue;
        }
        let q = keys.get(key).ok_or_else(|| me(format!("{INTERFACE_ID} key {key} missing")))?;
        let st = q
            .get("status")
            .and_then(Json::as_str)
            .and_then(producer_status)
            .ok_or_else(|| me(format!("{INTERFACE_ID} key {key}: unknown status {:?}", q.get("status"))))?;
        if st == EvalStatus::Evaluated {
            let v = q
                .get("value")
                .and_then(Json::as_f64)
                .ok_or_else(|| me(format!("{INTERFACE_ID} key {key}: CONVERGED without a value")))?;
            if !(v.is_finite() && v >= 0.0) {
                return Err(me(format!("{INTERFACE_ID} key {key}: value {v} is not a finite power >= 0")));
            }
            out.push((
                slot,
                Upstream::Evaluated {
                    p_w: v,
                    evidence_class: evidence_class.to_string(),
                    source: format!("{source}; {INTERFACE_ID} {key}"),
                },
            ));
        } else {
            let reasons: Vec<String> = q
                .get("reasons")
                .and_then(Json::as_array)
                .map(|a| a.iter().map(|r| r.as_str().map_or_else(|| r.to_string(), str::to_string)).collect())
                .unwrap_or_default();
            out.push((
                slot,
                Upstream::Absent {
                    status: st,
                    reason: format!("{INTERFACE_ID} {key}: {} ({})", st, reasons.join(", ")),
                },
            ));
        }
    }
    Ok(out)
}

// ------------------------------------------------------------------------------------------- IF-ICP-BUS-v2

/// The plane-explicit bus interface of NP-ICP-NEUTRALIZER model_version 2 (prereg v2 IF-ICP-BUS-v2). Added beside the
/// admitted v1 path, which is unchanged.
pub const INTERFACE_ID_V2: &str = "IF-ICP-BUS-v2";
/// BK-01..BK-05: (key id, slot, producer key); every one at plane LOAD (BUS2-01).
pub const KEY_MAP_V2: [(&str, Slot, &str); 5] = [
    ("BK-01", Slot::IcpRfSource, "P_icp_rf_source_DC_W"),
    ("BK-02", Slot::IcpMatchingNetwork, "P_icp_matching_DC_W"),
    ("BK-03", Slot::IcpCollectorBias, "P_icp_collector_bias_W"),
    ("BK-04", Slot::IcpAssistMagnet, "P_icp_assist_magnet_W"),
    ("BK-05", Slot::FlowControlIcpFeed, "P_icp_flow_control_W"),
];
/// The flight configuration of BUS2-04 (NOT_EVALUATED today: CPL-HALL-ON is gated).
pub const FLIGHT_CONFIGURATION_V2: &str = "CFG-FLIGHT-HALL-ON";

/// Upstream ICP loads from an IF-ICP-BUS-v2 record (one producer solve member). The slot load-plane values are taken
/// exactly as the producer gives them (no efficiency is applied: BUS2-02 / BUS2-03). Refused (ModelError): another
/// interface id or boundary; a retired `P_icp_bus_W`; a LOAD key without its slot or at another plane; an installed
/// variant the ledger does not declare. `flight_ledger` consumes CFG-FLIGHT-HALL-ON records only and never a
/// GROUND_FACILITY_ONLY supply (BUS2-04).
pub fn icp_upstream_loads_v2(
    record: &Json,
    variant: &[Slot],
    evidence_class: &str,
    source: &str,
    flight_ledger: bool,
) -> PowerResult<Vec<(Slot, Upstream)>> {
    let id = INTERFACE_ID_V2;
    if record.get("interface").and_then(Json::as_str) != Some(id) {
        return Err(me(format!("not an {id} record (interface {:?})", record.get("interface"))));
    }
    if record.get("target_boundary").and_then(Json::as_str) != Some(BOUNDARY_VERSION) {
        return Err(me(format!("{id} record targets {:?}, not {BOUNDARY_VERSION}", record.get("target_boundary"))));
    }
    if !EVIDENCE_CLASSES.contains(&evidence_class) {
        return Err(me(format!("evidence_class {evidence_class:?} not in {EVIDENCE_CLASSES:?}")));
    }
    if source.trim().is_empty() {
        return Err(me("a source naming the producer record is required".into()));
    }
    let keys = record.get("keys").and_then(Json::as_object).ok_or_else(|| me(format!("{id}: no keys")))?;
    if keys.contains_key("P_icp_bus_W") {
        return Err(me(format!("{id}: P_icp_bus_W is retired (mixed planes); its presence is MODEL_ERROR")));
    }
    let configuration = record.get("configuration").and_then(Json::as_str).unwrap_or_default();
    let ground = record
        .get("flags")
        .and_then(Json::as_array)
        .is_some_and(|f| f.iter().any(|x| x.as_str() == Some("INCLUDES_GROUND_FACILITY_SUPPLY")));
    if flight_ledger && configuration != FLIGHT_CONFIGURATION_V2 {
        return Err(me(format!(
            "BUS2-04: the flight ledger consumes {FLIGHT_CONFIGURATION_V2} records only (got {configuration:?})"
        )));
    }
    if flight_ledger && ground {
        return Err(me("BUS2-04: a GROUND_FACILITY_ONLY supply is never spacecraft bus power".into()));
    }
    let mut out = Vec::new();
    for (bk, slot, key) in KEY_MAP_V2 {
        let q = keys.get(key).ok_or_else(|| me(format!("{id} key {key} missing")))?;
        let field = |f: &str| q.get(f).and_then(Json::as_str);
        if field("id") != Some(bk) || field("plane") != Some("LOAD") || field("slot") != Some(slot.name()) {
            return Err(me(format!(
                "{id} key {key}: expected {bk} at plane LOAD on slot {} (BUS2-01), got {:?} / {:?} / {:?}",
                slot.name(),
                field("id"),
                field("plane"),
                field("slot")
            )));
        }
        if slot.group() == super::slots::Group::Variant && !variant.contains(&slot) {
            // BUS2-07: an undeclared variant is a NOT_INSTALLED record at exactly 0.
            let zero = q.get("value").and_then(Json::as_f64) == Some(0.0);
            if field("slot_state") != Some("NOT_INSTALLED") || !zero {
                return Err(me(format!("{id} key {key}: an installed variant the ledger does not declare")));
            }
            continue;
        }
        let st = q
            .get("status")
            .and_then(Json::as_str)
            .and_then(producer_status)
            .ok_or_else(|| me(format!("{id} key {key}: unknown status {:?}", q.get("status"))))?;
        if st == EvalStatus::Evaluated {
            let v = q
                .get("value")
                .and_then(Json::as_f64)
                .ok_or_else(|| me(format!("{id} key {key}: CONVERGED without a value")))?;
            if !(v.is_finite() && v >= 0.0) {
                return Err(me(format!("{id} key {key}: value {v} is not a finite power >= 0 (BUS2-08)")));
            }
            out.push((
                slot,
                Upstream::Evaluated {
                    p_w: v,
                    evidence_class: evidence_class.to_string(),
                    source: format!("{source}; {id} {bk} {key} (LOAD)"),
                },
            ));
        } else {
            let reasons: Vec<String> = q
                .get("reasons")
                .and_then(Json::as_array)
                .map(|a| a.iter().map(|r| r.as_str().map_or_else(|| r.to_string(), str::to_string)).collect())
                .unwrap_or_default();
            out.push((
                slot,
                Upstream::Absent { status: st, reason: format!("{id} {key}: {} ({})", st, reasons.join(", ")) },
            ));
        }
    }
    Ok(out)
}
