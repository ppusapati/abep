//! Validation gating of model_version 2 (VC-01..VC-08 as replaced / added; A9.31 OQ-NPICP-07, -13, -14). This layer
//! compares a model point with a measurement record; it never edits a raw output, and no raw output becomes
//! VALIDATED_BENCH here. No P1 / P2 data exist: every real comparison is NOT_EVALUATED today.
//!
//! * VC-06 / IN-27: a comparison needs a partition record frozen (sha256) before any value was examined, naming the
//!   record, its planned operating point and its CAL / VAL role. Every repeat of one operating point is in one role.
//! * VC-07 / DOM-15: measured p_ICP is determining; a point without it is NOT_EVALUATED.
//! * VC-01: z = (y_model - y_meas) / sqrt(u_input^2 + u_meas^2); CONSISTENT if |z| <= 2. VC-03: r_u reported, no
//!   threshold. VC-04 / VC-08: a cell is VALIDATED_BENCH only when every point of its frozen VAL set is CONSISTENT and
//!   none is NOT_EVALUATED; calibration records never validate the quantity they calibrated.

use abep_provenance::sha256_hex;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Role {
    Cal,
    Val,
}

/// IN-27: the frozen calibration / validation partition of a campaign.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PartitionRecord {
    pub partition_id: String,
    /// Planned record id -> (planned operating point id, role).
    pub records: BTreeMap<String, (String, Role)>,
    pub measurands_calibrated: BTreeSet<String>,
    pub measurands_validated: BTreeSet<String>,
    /// Frozen custody list (who holds which raw files; the statement that no value was examined).
    pub custody: Vec<String>,
    pub no_value_examined_before_freeze: bool,
}

impl PartitionRecord {
    /// sha256 of the canonical JSON of the record (the freeze hash).
    pub fn sha256(&self) -> String {
        sha256_hex(serde_json::to_string(self).expect("serializable").as_bytes())
    }

    /// Structural violations: an operating point split across roles, an empty custody list, a measurand both
    /// calibrated and validated, or the freeze statement missing.
    pub fn violations(&self) -> Vec<String> {
        let mut v = Vec::new();
        let mut roles: BTreeMap<&str, BTreeSet<Role>> = BTreeMap::new();
        for (op, role) in self.records.values() {
            roles.entry(op.as_str()).or_default().insert(*role);
        }
        for (op, r) in roles {
            if r.len() > 1 {
                v.push(format!("operating point {op} is split across CAL and VAL (VC-06)"));
            }
        }
        if self.custody.is_empty() {
            v.push("custody list empty".into());
        }
        if !self.no_value_examined_before_freeze {
            v.push("freeze statement missing: values examined before the partition was frozen".into());
        }
        for m in self.measurands_calibrated.intersection(&self.measurands_validated) {
            v.push(format!("measurand {m} is both calibrated and validated"));
        }
        v
    }
}

/// One model-vs-measurement comparison point.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ComparisonPoint {
    pub record_id: String,
    pub operating_point_id: String,
    pub measurand: String,
    pub cell_id: String,
    /// Measured p_ICP is part of the record (VC-07).
    pub p_icp_measured: bool,
    pub y_model: f64,
    pub u_input: f64,
    pub y_meas: f64,
    pub u_meas: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PointStatus {
    NotEvaluated,
    Consistent,
    Inconsistent,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ComparisonOutcome {
    pub record_id: String,
    pub status: PointStatus,
    pub z: Option<f64>,
    /// VC-03: r_u = u_input / u_meas (reported; no threshold).
    pub r_u: Option<f64>,
    pub reasons: Vec<String>,
}

/// VC-01 with the VC-06 / VC-07 gates. `frozen_sha256` is the sha256 committed when the partition was frozen.
pub fn compare(
    pt: &ComparisonPoint,
    partition: Option<&PartitionRecord>,
    frozen_sha256: Option<&str>,
) -> ComparisonOutcome {
    let mut reasons = Vec::new();
    match (partition, frozen_sha256) {
        (None, _) => reasons.push("IN-27_PARTITION_NOT_FROZEN".to_string()),
        (Some(p), f) => {
            if f != Some(p.sha256().as_str()) {
                reasons.push("IN-27_PARTITION_HASH_MISMATCH".into());
            }
            for v in p.violations() {
                reasons.push(format!("VC-06_PARTITION_INVALID: {v}"));
            }
            match p.records.get(&pt.record_id) {
                None => reasons.push("FC-22_RECORD_OUTSIDE_PARTITION".into()),
                Some((op, role)) => {
                    if *op != pt.operating_point_id {
                        reasons.push("FC-22_OPERATING_POINT_DIFFERS_FROM_PLAN".into());
                    }
                    if *role != Role::Val {
                        reasons.push("VC-08_CALIBRATION_RECORD_NOT_A_VALIDATION_POINT".into());
                    }
                    if p.measurands_calibrated.contains(&pt.measurand) {
                        reasons.push("VC-08_CALIBRATED_MEASURAND".into());
                    }
                }
            }
        }
    }
    if !pt.p_icp_measured {
        reasons.push("DOM-15_P_ICP_NOT_MEASURED".into());
    }
    let r_u = (pt.u_meas > 0.0).then(|| pt.u_input / pt.u_meas);
    if !reasons.is_empty() {
        return ComparisonOutcome {
            record_id: pt.record_id.clone(),
            status: PointStatus::NotEvaluated,
            z: None,
            r_u,
            reasons,
        };
    }
    let den = (pt.u_input * pt.u_input + pt.u_meas * pt.u_meas).sqrt();
    let z = (pt.y_model - pt.y_meas) / den;
    let status = if !z.is_finite() {
        reasons.push("VC-01_UNCERTAINTY_ZERO".into());
        PointStatus::NotEvaluated
    } else if z.abs() <= 2.0 {
        PointStatus::Consistent
    } else {
        PointStatus::Inconsistent
    };
    ComparisonOutcome { record_id: pt.record_id.clone(), status, z: z.is_finite().then_some(z), r_u, reasons }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CellStatus {
    NotValidated,
    Inconsistent,
    ValidatedBench,
}

/// VC-04 / VC-08: the status of one cell from its comparisons. Every VAL record of the frozen partition in the cell
/// must have been compared.
pub fn cell_status(
    cell_id: &str,
    partition: &PartitionRecord,
    outcomes: &[(ComparisonPoint, ComparisonOutcome)],
) -> CellStatus {
    let val: Vec<&String> = partition.records.iter().filter(|(_, (_, r))| *r == Role::Val).map(|(k, _)| k).collect();
    let in_cell: Vec<&(ComparisonPoint, ComparisonOutcome)> =
        outcomes.iter().filter(|(p, _)| p.cell_id == cell_id).collect();
    if in_cell.iter().any(|(_, o)| o.status == PointStatus::Inconsistent) {
        return CellStatus::Inconsistent;
    }
    let all_val_seen = !val.is_empty()
        && val.iter().all(|id| in_cell.iter().any(|(p, o)| &&p.record_id == id && o.status == PointStatus::Consistent));
    if all_val_seen && in_cell.iter().all(|(_, o)| o.status == PointStatus::Consistent) {
        CellStatus::ValidatedBench
    } else {
        CellStatus::NotValidated
    }
}
