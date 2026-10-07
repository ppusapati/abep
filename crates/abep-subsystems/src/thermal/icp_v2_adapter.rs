//! Producer -> consumer adapter of IF-ICP-THERMAL-v2: one NP-ICP-NEUTRALIZER model_version 2 thermal member record
//! (abep-icp `ThermalRecordV2`, read in its serialized form like the bus interface, so this crate never links the
//! not-yet-admitted producer) -> the model 2.0.0 input record [`InterfaceRecordV2`].
//!
//! The mapping is fixed by the locked key table (both preregistrations, sha256 `33e495ad…`) and refuses everything it
//! cannot map; nothing is guessed:
//! * every key of the table exactly once (a dropped, extra or duplicated key is refused; duplicate JSON object keys are
//!   detected while parsing), and each key's id, role, plane and powered_by equal to its table row;
//! * the status vocabulary CONVERGED -> EVALUATED; NOT_EVALUATED, INCOMPLETE_EVIDENCE, OUT_OF_DOMAIN, MODEL_ERROR
//!   unchanged; any other status refused; a CONVERGED key without a finite value, or a withheld key with a value,
//!   refused (no zero-fill);
//! * the evidence attributes: evidence class SYNTHETIC_TEST_DATA_NOT_EVIDENCE for a producer record of configuration
//!   SYNTHETIC, otherwise model-derived (a model output); source = producer, lock, member and key id; uncertainty =
//!   the ED-08 member statement; applicability domain = the producer configuration and member; validation status
//!   NOT_VALIDATED (the producer is NOT_VALIDATED on every output);
//! * the producer per-node partitions of TK-07 / TK-12 in W, only for CONVERGED shares of a CONVERGED key.

use super::case::{InterfaceRecordV2, TimeBasis, ValueRecord};
use super::governance::{GovernedContextV2, KEY_TABLE_V2_SHA256, PRODUCER_LOCK_SHA256};
use super::vocab;
use serde::de::{Deserializer, MapAccess, Visitor};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::fmt;

pub const PRODUCER_STATUS_MAP: [(&str, &str); 5] = [
    ("CONVERGED", "EVALUATED"),
    ("NOT_EVALUATED", "NOT_EVALUATED"),
    ("INCOMPLETE_EVIDENCE", "INCOMPLETE_EVIDENCE"),
    ("OUT_OF_DOMAIN", "OUT_OF_DOMAIN"),
    ("MODEL_ERROR", "MODEL_ERROR"),
];

/// A JSON object read into an ordered map that refuses duplicate keys.
#[derive(Debug, Clone, PartialEq)]
pub struct StrictMap<T>(pub BTreeMap<String, T>);

impl<'de, T: Deserialize<'de>> Deserialize<'de> for StrictMap<T> {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V<T>(std::marker::PhantomData<T>);
        impl<'de, T: Deserialize<'de>> Visitor<'de> for V<T> {
            type Value = StrictMap<T>;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                f.write_str("a JSON object without duplicate keys")
            }
            fn visit_map<A: MapAccess<'de>>(self, mut m: A) -> Result<Self::Value, A::Error> {
                let mut out = BTreeMap::new();
                while let Some((k, v)) = m.next_entry::<String, T>()? {
                    if out.contains_key(&k) {
                        return Err(serde::de::Error::custom(format!("duplicated key {k:?}")));
                    }
                    out.insert(k, v);
                }
                Ok(StrictMap(out))
            }
        }
        d.deserialize_map(V(std::marker::PhantomData))
    }
}

#[derive(Debug, Clone, Deserialize)]
struct ProducerQuantity {
    value: Option<f64>,
    unit: String,
    status: String,
    #[serde(default)]
    reasons: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct ProducerKey {
    id: String,
    role: String,
    plane: String,
    powered_by: String,
    #[serde(flatten)]
    q: ProducerQuantity,
}

#[derive(Debug, Clone, Deserialize)]
struct ProducerMember {
    scenario_member_id: String,
    keys: StrictMap<ProducerKey>,
    node_shares_w: StrictMap<StrictMap<ProducerQuantity>>,
    coil_ohmic_split_w: StrictMap<ProducerQuantity>,
}

#[derive(Debug, Clone, Deserialize)]
struct ProducerRecord {
    interface: String,
    producer_lock_sha256: String,
    key_table_sha256: String,
    configuration: String,
    members: Vec<ProducerMember>,
}

/// The consumer case the record is written for (IFI2-01 case fields).
#[derive(Debug, Clone, PartialEq)]
pub struct AdapterContext {
    pub case_id: String,
    pub case_class: String,
    pub supply_mode: String,
    pub design_state_id: Option<String>,
    pub operating_point_id: String,
}

/// The adapted record and the producer's echoed TK-06 conductor split as weights (the consumer uses its own RI-PART
/// split; the caller compares the two: a registered split is required on both sides, CONF-15).
#[derive(Debug, Clone)]
pub struct AdaptedV2 {
    pub record: InterfaceRecordV2,
    pub producer_coil_split: Option<BTreeMap<String, f64>>,
}

fn err(m: impl Into<String>) -> String {
    format!("IF-ICP-THERMAL-v2 adapter: {}", m.into())
}

/// The scenario member ids of a producer record, in record order (refuses a malformed or duplicated record).
pub fn member_ids(bytes: &[u8]) -> Result<Vec<String>, String> {
    let r: ProducerRecord = serde_json::from_slice(bytes).map_err(|e| err(e.to_string()))?;
    let ids: Vec<String> = r.members.iter().map(|m| m.scenario_member_id.clone()).collect();
    let mut seen = std::collections::BTreeSet::new();
    for id in &ids {
        if !seen.insert(id) {
            return Err(err(format!("scenario member {id:?} appears twice")));
        }
    }
    Ok(ids)
}

/// Adapt member `scenario_member_id` of the serialized producer record `bytes`.
pub fn adapt(
    bytes: &[u8],
    scenario_member_id: &str,
    ctx: &AdapterContext,
    gov: &GovernedContextV2,
) -> Result<AdaptedV2, String> {
    let r: ProducerRecord = serde_json::from_slice(bytes).map_err(|e| err(e.to_string()))?;
    if r.interface != vocab::ICP_V2_INTERFACE_ID {
        return Err(err(format!("interface {:?} is not {}", r.interface, vocab::ICP_V2_INTERFACE_ID)));
    }
    if r.producer_lock_sha256 != PRODUCER_LOCK_SHA256 {
        return Err(err(format!("producer lock {} is not the anchor {PRODUCER_LOCK_SHA256}", r.producer_lock_sha256)));
    }
    if r.key_table_sha256 != KEY_TABLE_V2_SHA256 {
        return Err(err(format!("key table {} is not {KEY_TABLE_V2_SHA256}", r.key_table_sha256)));
    }
    let known_cfg =
        vocab::ICP_V2_CONFIGURATIONS.contains(&r.configuration.as_str()) || r.configuration == "CFG-FLIGHT-HALL-ON";
    if !known_cfg {
        return Err(err(format!("configuration {:?} is not a registered configuration", r.configuration)));
    }
    let found: Vec<&ProducerMember> = r.members.iter().filter(|m| m.scenario_member_id == scenario_member_id).collect();
    let m = match found.as_slice() {
        [m] => *m,
        [] => return Err(err(format!("no scenario member {scenario_member_id:?}"))),
        _ => return Err(err(format!("scenario member {scenario_member_id:?} appears {} times", found.len()))),
    };
    let synthetic = r.configuration == "SYNTHETIC";
    let evidence_class = if synthetic { vocab::SYNTHETIC } else { "model-derived" };
    let map_status = |s: &str| PRODUCER_STATUS_MAP.iter().find(|(p, _)| *p == s).map(|(_, c)| *c);
    // Every key of the locked table exactly once, with its row.
    let table = gov.key_table();
    for k in m.keys.0.keys() {
        if !table.iter().any(|row| &row.key == k) {
            return Err(err(format!("key {k:?} is not in the locked key table")));
        }
    }
    let mut keys = BTreeMap::new();
    let mut ids_seen = std::collections::BTreeSet::new();
    for row in table {
        let pk = m.keys.0.get(&row.key).ok_or_else(|| err(format!("key {} ({}) dropped", row.key, row.id)))?;
        if !ids_seen.insert(pk.id.clone()) {
            return Err(err(format!("key id {} appears twice", pk.id)));
        }
        if (pk.id.as_str(), pk.role.as_str(), pk.plane.as_str(), pk.powered_by.as_str())
            != (row.id.as_str(), row.role.as_str(), row.plane.as_str(), row.powered_by.as_str())
        {
            return Err(err(format!(
                "key {}: id / role / plane / powered_by differ from the locked row {}",
                row.key, row.id
            )));
        }
        if pk.q.unit != "W" {
            return Err(err(format!("key {}: unit {:?}, registered W", row.key, pk.q.unit)));
        }
        let status = map_status(&pk.q.status).ok_or_else(|| {
            err(format!("key {}: producer status {:?} has no registered mapping", row.key, pk.q.status))
        })?;
        let value = match (status, pk.q.value) {
            ("EVALUATED", Some(v)) if v.is_finite() => Some(json!(v)),
            ("EVALUATED", _) => return Err(err(format!("key {}: CONVERGED without a finite value", row.key))),
            (_, Some(_)) => return Err(err(format!("key {}: withheld status {} carries a value", row.key, status))),
            (_, None) => None,
        };
        keys.insert(
            row.key.clone(),
            ValueRecord {
                value,
                units: Some("W".into()),
                status: Some(status.into()),
                evidence_class: Some(evidence_class.into()),
                source: Some(format!(
                    "NP-ICP-NEUTRALIZER model_version 2 (prereg lock {PRODUCER_LOCK_SHA256}); scenario member {}; {} {}{}",
                    m.scenario_member_id,
                    row.id,
                    row.key,
                    if pk.q.reasons.is_empty() { String::new() } else { format!("; reasons {}", pk.q.reasons.join(", ")) }
                )),
                uncertainty: Some(json!(
                    "one member of the unweighted ED-08 scenario set (the envelope is over the members); sampled UQ NOT_EVALUATED (UQ-03)"
                )),
                applicability_domain: Some(json!({
                    "producer_configuration": r.configuration,
                    "scenario_member_id": m.scenario_member_id,
                })),
                validation_status: Some("NOT_VALIDATED".into()),
                hall_map: None,
            },
        );
    }
    // Producer per-node partitions (TK-07, TK-12).
    let mut node_shares_w = BTreeMap::new();
    for (k, shares) in &m.node_shares_w.0 {
        let row =
            table.iter().find(|row| &row.key == k).ok_or_else(|| err(format!("node shares of unknown key {k}")))?;
        if !matches!(vocab::icp_v2_key(k).map(|x| x.deposition), Some(vocab::DepositionV2::ProducerShares)) {
            return Err(err(format!(
                "node shares for {} ({}): only TK-07 / TK-12 are producer-partitioned",
                k, row.id
            )));
        }
        if keys[k].status.as_deref() != Some("EVALUATED") {
            continue;
        }
        let mut out: BTreeMap<String, Value> = BTreeMap::new();
        for (node, q) in &shares.0 {
            match (map_status(&q.status), q.value) {
                (Some("EVALUATED"), Some(v)) if v.is_finite() && q.unit == "W" => {
                    out.insert(node.clone(), json!(v));
                }
                _ => return Err(err(format!("{k} share {node}: not a CONVERGED value in W ({})", q.status))),
            }
        }
        node_shares_w.insert(k.clone(), out);
    }
    // TK-06 split echoed by the producer, as weights.
    let coil = keys.get("Q_icp_coil_ohmic_W").and_then(|v| v.value.as_ref()).and_then(Value::as_f64);
    let producer_coil_split = match coil {
        Some(total) if total > 0.0 => {
            let mut w = BTreeMap::new();
            for (node, q) in &m.coil_ohmic_split_w.0 {
                match (map_status(&q.status), q.value) {
                    (Some("EVALUATED"), Some(v)) => {
                        w.insert(node.clone(), v / total);
                    }
                    _ => {
                        w.clear();
                        break;
                    }
                }
            }
            (!w.is_empty()).then_some(w)
        }
        _ => None,
    };
    Ok(AdaptedV2 {
        record: InterfaceRecordV2 {
            interface_id: vocab::ICP_V2_INTERFACE_ID.into(),
            producer_id: vocab::ICP_PRODUCER_ID.into(),
            producer_version: "2".into(),
            producer_lock_sha256: r.producer_lock_sha256,
            key_table_sha256: r.key_table_sha256,
            case_id: ctx.case_id.clone(),
            case_class: ctx.case_class.clone(),
            supply_mode: ctx.supply_mode.clone(),
            design_state_id: ctx.design_state_id.clone(),
            operating_point_id: ctx.operating_point_id.clone(),
            configuration: r.configuration,
            scenario_member_id: m.scenario_member_id.clone(),
            time_basis: TimeBasis { kind: "STEADY".into(), breakpoints_s: None },
            keys,
            node_shares_w,
        },
        producer_coil_split,
    })
}
