//! NP-ICP-NEUTRALIZER model_version 2 (prereg v2, lock `a180ceef…`; A9.31 secs. 7-10), added beside model_version 1.
//!
//! * PF-01 / PF-02 / GAP-01..05 are resolved as registered: per-collision wall recombination and tau-symmetric
//!   background inflow in EQ-02 v2, the three unweighted H members of GAP-04, the energy disposition ED-01..ED-09 by
//!   conservation and bounding vertices (no convenience split), and the CC-03 v2 current scale.
//! * INT-16 / INT-17 / INT-18 as approved: the registered-table T_e scan end, least-energy formation routes with the
//!   route excess booked in class X, `xs/` representations (abep-chem registry).
//! * Interfaces: IF-ICP-THERMAL-v2 (matched key table, sha256 `33e495ad…`), IF-ICP-BUS-v2 (plane-explicit, load-plane
//!   keys only, no efficiency applied) and CPL-HALL-ON-v1 (typed contract, NOT_EVALUATED while no Hall member is
//!   admitted; no beam / plume parameter exists in this crate).
//!
//! Raw output only: no ratio, margin, HC id, threshold or RFP label (AS-01); every output NOT_VALIDATED.

pub mod case;
pub mod cpl;
pub mod diagnostics;
pub mod evaluate;
pub mod formation;
pub mod partition;
pub mod result;
pub mod testkit;
pub mod validation;

pub use case::IcpCaseV2;
pub use result::IcpResultV2;

use crate::context::{IcpModel, ReadFile, PREREG_DIR};
use abep_provenance::{read_verified, sha256_hex};
use abep_types::{AbepError, AbepResult};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeSet;
use std::path::Path;

pub const MODEL_VERSION_V2: &str = "2";
/// sha256 of `prereg_lock_v2.json` (the anchor; it pins `prereg_v2.json` and `PREREG_v2.md`).
pub const PREREG_LOCK_V2_SHA256: &str = "a180ceef37223467687d7d245ab790a172e8dad9ea4e90aa463d434383142287";
/// Canonical sha256 of the IF-ICP-THERMAL-v2 key table (sorted-key compact JSON), equal on both sides.
pub const THERMAL_V2_KEY_TABLE_SHA256: &str = "33e495adadbe94a5113c5f6b9040156ec8309295cca15b812714038beaa51161";
pub const CONTRACT_ID_V2: &str = "NP-ICP-NEUTRALIZER/prereg_v2";
pub const THERMAL_INTERFACE_V2: &str = "IF-ICP-THERMAL-v2";
pub const BUS_INTERFACE_V2: &str = "IF-ICP-BUS-v2";
pub const CPL_HALL_ON: &str = "CPL-HALL-ON-v1";
pub const THERMAL_CONSUMER_V2: &str = "NP-THERMAL-CATHODELESS prereg v2 (2.0.0)";

/// One row of the IF-ICP-THERMAL-v2 key table (prereg v2 `system_coupling_interfaces.IF-ICP-THERMAL-v2.keys`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct KeyTableEntry {
    pub id: String,
    pub key: String,
    pub role: String,
    pub plane: String,
    pub powered_by: String,
    pub sign: String,
    pub receiver: String,
    pub meaning: String,
}

/// The CA-ICP-v1 screening state per mode (CS-01..CS-06): verdicts live under `data/chemistry/icp/audit/`; none is
/// recorded today (NOT_RUN). `unbounded_omissions` lists processes found UNBOUNDED_OMISSION (FC-25).
#[derive(Debug, Clone, PartialEq, Default)]
pub struct ChemistryScreen {
    pub unbounded_omissions: Vec<(String, String)>,
}

/// The model_version 2 context: the v1 context (every pin of v1 still verified) plus the v2 lock, the matched key
/// table and the governed registries v2 reads. The registries are empty today; tests may add synthetic entries.
#[derive(Debug, Clone)]
pub struct IcpModelV2 {
    pub v1: IcpModel,
    /// Files read by v2 in addition to the v1 pins (the v1 context is not modified).
    pub v2_files_read: BTreeSet<ReadFile>,
    pub prereg_lock_v2_sha256: String,
    pub prereg_v2_sha256: String,
    pub prereg_v2_md_sha256: String,
    pub key_table: Vec<KeyTableEntry>,
    pub key_table_sha256: String,
    /// DOM-14: upstream conductance / feed models ADMITTED for flight FLOW_BALANCE (none today).
    pub admitted_upstream_models: BTreeSet<String>,
    /// DOM-16: geometry ids with a REGISTERED_EFFECTIVE volume record (none today).
    pub registered_effective_volumes: BTreeSet<String>,
    /// DOM-17: registered flight exposure models (none today).
    pub flight_exposure_models: BTreeSet<String>,
    pub chemistry_screen: ChemistryScreen,
}

fn schema(path: &str, m: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.to_string(), message: m.into() }
}

/// Canonical sha256 of a key table: `json.dumps(keys, sort_keys=True, separators=(',', ':'), ensure_ascii=False)`.
pub fn canonical_sha256(v: &Value) -> String {
    // serde_json maps are ordered (no preserve_order feature): compact output with sorted keys.
    sha256_hex(serde_json::to_string(v).expect("serializable").as_bytes())
}

impl IcpModelV2 {
    pub fn load_workspace() -> AbepResult<Self> {
        Self::load(&abep_provenance::workspace_repo_root()?)
    }

    pub fn load(root: &Path) -> AbepResult<Self> {
        let v1 = IcpModel::load(root)?;
        let lock_rel = format!("{PREREG_DIR}/prereg_lock_v2.json");
        let lock_bytes = read_verified(&root.join(&lock_rel), PREREG_LOCK_V2_SHA256)?;
        let lock: Value = serde_json::from_slice(&lock_bytes).map_err(|e| schema(&lock_rel, e.to_string()))?;
        let pin = |k: &str| {
            lock.pointer(&format!("/files/{k}"))
                .and_then(Value::as_str)
                .map(String::from)
                .ok_or_else(|| schema(&lock_rel, format!("files.{k}")))
        };
        let (pj, pm) = (pin("prereg_v2.json")?, pin("PREREG_v2.md")?);
        if lock.pointer("/predecessor_lock/sha256").and_then(Value::as_str) != Some(v1.prereg_lock_sha256.as_str()) {
            return Err(schema(&lock_rel, "the v2 lock does not name the v1 lock as its predecessor"));
        }
        let prereg_rel = format!("{PREREG_DIR}/prereg_v2.json");
        let prereg_bytes = read_verified(&root.join(&prereg_rel), &pj)?;
        read_verified(&root.join(format!("{PREREG_DIR}/PREREG_v2.md")), &pm)?;
        let prereg: Value = serde_json::from_slice(&prereg_bytes).map_err(|e| schema(&prereg_rel, e.to_string()))?;
        for (ptr, want) in
            [("/id", "NP-ICP-NEUTRALIZER"), ("/model_version", MODEL_VERSION_V2), ("/target_crate", "abep-icp")]
        {
            if prereg.pointer(ptr).and_then(Value::as_str) != Some(want) {
                return Err(schema(&prereg_rel, format!("{ptr} is not {want}")));
            }
        }
        let keys = prereg
            .pointer("/system_coupling_interfaces/IF-ICP-THERMAL-v2/keys")
            .ok_or_else(|| schema(&prereg_rel, "IF-ICP-THERMAL-v2 keys"))?;
        let key_table_sha256 = canonical_sha256(keys);
        if key_table_sha256 != THERMAL_V2_KEY_TABLE_SHA256 {
            return Err(schema(
                &prereg_rel,
                format!("key table sha256 {key_table_sha256} != {THERMAL_V2_KEY_TABLE_SHA256}"),
            ));
        }
        let key_table: Vec<KeyTableEntry> =
            serde_json::from_value(keys.clone()).map_err(|e| schema(&prereg_rel, e.to_string()))?;
        let mut v2_files_read = BTreeSet::new();
        for (p, s, by) in [
            (lock_rel.clone(), PREREG_LOCK_V2_SHA256.to_string(), "abep-icp anchor (prereg lock v2)".to_string()),
            (prereg_rel, pj.clone(), lock_rel.clone()),
            (format!("{PREREG_DIR}/PREREG_v2.md"), pm.clone(), lock_rel),
        ] {
            v2_files_read.insert(ReadFile { path: p, sha256: s, pinned_by: by });
        }
        Ok(IcpModelV2 {
            v1,
            v2_files_read,
            prereg_lock_v2_sha256: PREREG_LOCK_V2_SHA256.into(),
            prereg_v2_sha256: pj,
            prereg_v2_md_sha256: pm,
            key_table,
            key_table_sha256,
            admitted_upstream_models: BTreeSet::new(),
            registered_effective_volumes: BTreeSet::new(),
            flight_exposure_models: BTreeSet::new(),
            chemistry_screen: ChemistryScreen::default(),
        })
    }

    /// The key-table row of an IF-ICP-THERMAL-v2 key.
    pub fn key_row(&self, key: &str) -> Option<&KeyTableEntry> {
        self.key_table.iter().find(|k| k.key == key)
    }
}
