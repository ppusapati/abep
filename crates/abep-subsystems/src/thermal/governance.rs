//! Governed state read from the repository with sha256 verification: the flight configuration (GR-16), the pinned
//! HallThruster.jl commit (GR-20, rule 7), the transport ensemble (GR-19; credible set EMPTY today), the design-state
//! set v2 (config manifest + design_state_set_ref_v1), the P4 anode candidate ids (CX-05) and the bus variant
//! vocabulary (GR-17). The crate reads no requirement or decision record (EX-08).

use abep_provenance::run_record::parse_hallthruster_pin;
use abep_provenance::{read_verified, sha256_hex, ConfigManifest};
use abep_types::{AbepError, AbepResult};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use super::vocab;

pub const PREREG_PATH: &str = "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/prereg_v1.json";
pub const PREREG_MD_PATH: &str = "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/PREREG.md";
pub const PREREG_LOCK_PATH: &str = "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/prereg_lock_v1.json";
/// sha256 of prereg_v1.json and PREREG.md (prereg_lock_v1.json).
pub const PREREG_SHA256: &str = "e3e6859cf61703c27254e9c231ff4637f7d20ea743c8d881b9e55c8ba9d27c5c";
pub const PREREG_MD_SHA256: &str = "e3337c8fece492f40eea7452b9834c9678d6fd52696d018588f542a801cc28aa";

const ENSEMBLE_PATH: &str = "hallthruster_bridge/ensemble/transport_ensemble_v0.json";
const ENSEMBLE_SHA256: &str = "2d5069a3382ab667362befeeb5a737261f70a279d19cb89ee79cb61ae35ba08b";
const PINNED_PATH: &str = "hallthruster_bridge/PINNED.toml";
const PINNED_SHA256: &str = "26a00c8a156a5a5e9a58f9796f657ea12f59d87ac2da3d6507ac7347b4765280";
const P4_PATH: &str = "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json";
const P4_SHA256: &str = "f0d8bbfa6d3ec59a30910ef2ae1fd61f96fc3f725e6859dc8c6617b1cf6dd96b";
const BUS_PATH: &str = "schemas/interfaces/bus_power_boundary_a9_v2.json";
const BUS_SHA256: &str = "6c01742e3b1088a7aa9ed05674ba4cf83f2322259c80273ecccdfc032886f20a";
const ARCH_REL: &str = "architecture/hall_icp_neutralizer_v1.json";
const DESIGN_STATE_REF_REL: &str = "environment/design_state_set_ref_v1.json";
const MODEL_SET_REL: &str = "model_set/physics_model_set_v1.json";

/// Governed state consumed by the fail-closed gates. Fields are private: admission sets come only from the governed
/// records, never from a caller.
#[derive(Debug, Clone)]
pub struct GovernedContext {
    flight_configuration: String,
    hallthruster_commit: String,
    admitted_hall_members: BTreeSet<String>,
    screening_candidates: BTreeSet<String>,
    design_state_ids: BTreeSet<String>,
    anode_candidate_ids: BTreeSet<String>,
    admitted_icp_producers: BTreeSet<String>,
    spacecraft_thermal_icd_registered: bool,
    hashes: BTreeMap<String, String>,
}

fn schema_err(path: &str, message: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.to_string(), message: message.into() }
}

fn parse_json(path: &str, bytes: &[u8]) -> AbepResult<Value> {
    serde_json::from_slice(bytes).map_err(|e| schema_err(path, e.to_string()))
}

impl GovernedContext {
    /// Load and verify the governed records under `repo_root`. Any hash or schema mismatch is an error (MODEL_ERROR).
    pub fn load(repo_root: &Path) -> AbepResult<Self> {
        let mut hashes = BTreeMap::new();
        read_verified(&repo_root.join(PREREG_PATH), PREREG_SHA256)?;
        read_verified(&repo_root.join(PREREG_MD_PATH), PREREG_MD_SHA256)?;

        let manifest = ConfigManifest::load(repo_root)?;
        let arch_bytes = manifest.read_verified(repo_root, ARCH_REL)?;
        hashes.insert("architecture_config_sha256".to_string(), sha256_hex(&arch_bytes));
        let arch = parse_json(ARCH_REL, &arch_bytes)?;
        let flight_configuration = arch
            .pointer("/constants/flight_configuration")
            .and_then(Value::as_str)
            .ok_or_else(|| schema_err(ARCH_REL, "constants.flight_configuration missing"))?
            .to_string();
        let model_set = manifest.read_verified(repo_root, MODEL_SET_REL)?;
        hashes.insert("model_set_sha256".to_string(), sha256_hex(&model_set));
        let manifest_bytes = std::fs::read(repo_root.join("config").join("MANIFEST.json"))
            .map_err(|e| AbepError::Io { path: "config/MANIFEST.json".into(), message: e.to_string() })?;
        hashes.insert("config_manifest_sha256".to_string(), sha256_hex(&manifest_bytes));

        let dsr_bytes = manifest.read_verified(repo_root, DESIGN_STATE_REF_REL)?;
        let dsr = parse_json(DESIGN_STATE_REF_REL, &dsr_bytes)?;
        let ds_path =
            dsr.get("path").and_then(Value::as_str).ok_or_else(|| schema_err(DESIGN_STATE_REF_REL, "path"))?;
        let ds_sha =
            dsr.get("sha256").and_then(Value::as_str).ok_or_else(|| schema_err(DESIGN_STATE_REF_REL, "sha256"))?;
        let n_states =
            dsr.get("n_states").and_then(Value::as_u64).ok_or_else(|| schema_err(DESIGN_STATE_REF_REL, "n_states"))?;
        let ds_bytes = read_verified(&repo_root.join(ds_path), ds_sha)?;
        hashes.insert("design_state_set_sha256".to_string(), ds_sha.to_string());
        let ds = parse_json(ds_path, &ds_bytes)?;
        let states = ds.get("states").and_then(Value::as_array).ok_or_else(|| schema_err(ds_path, "states"))?;
        let mut design_state_ids = BTreeSet::new();
        for s in states {
            let id = s.get("state_id").and_then(Value::as_str).ok_or_else(|| schema_err(ds_path, "state_id"))?;
            design_state_ids.insert(id.to_string());
        }
        if design_state_ids.len() as u64 != n_states {
            return Err(schema_err(
                ds_path,
                format!("{} distinct state ids, reference pins {n_states}", design_state_ids.len()),
            ));
        }

        let ens_bytes = read_verified(&repo_root.join(ENSEMBLE_PATH), ENSEMBLE_SHA256)?;
        hashes.insert("transport_ensemble_sha256".to_string(), ENSEMBLE_SHA256.to_string());
        let ens = parse_json(ENSEMBLE_PATH, &ens_bytes)?;
        let members =
            ens.get("members").and_then(Value::as_array).ok_or_else(|| schema_err(ENSEMBLE_PATH, "members"))?;
        let mut admitted_hall_members = BTreeSet::new();
        for m in members {
            let id = m
                .get("ensemble_member_id")
                .and_then(Value::as_str)
                .ok_or_else(|| schema_err(ENSEMBLE_PATH, "member id"))?;
            admitted_hall_members.insert(id.to_string());
        }
        let mut screening_candidates = BTreeSet::new();
        for c in ens.get("screening_candidates").and_then(Value::as_array).into_iter().flatten() {
            if let Some(id) = c.get("ensemble_member_id").and_then(Value::as_str) {
                screening_candidates.insert(id.to_string());
            }
        }

        let pinned = read_verified(&repo_root.join(PINNED_PATH), PINNED_SHA256)?;
        hashes.insert("hallthruster_pin_sha256".to_string(), PINNED_SHA256.to_string());
        let pinned_text = std::str::from_utf8(&pinned).map_err(|e| schema_err(PINNED_PATH, e.to_string()))?;
        let (_, hallthruster_commit) = parse_hallthruster_pin(pinned_text)?;

        let p4 = parse_json(P4_PATH, &read_verified(&repo_root.join(P4_PATH), P4_SHA256)?)?;
        let mut anode_candidate_ids = BTreeSet::new();
        let mut cand01_is_316l = false;
        for c in p4.get("candidates").and_then(Value::as_array).ok_or_else(|| schema_err(P4_PATH, "candidates"))? {
            let id = c.get("id").and_then(Value::as_str).ok_or_else(|| schema_err(P4_PATH, "candidate id"))?;
            if id == vocab::REJECTED_FLIGHT_ANODE_CANDIDATE {
                cand01_is_316l = c.get("name").and_then(Value::as_str).is_some_and(|n| n.contains("316L"));
            }
            anode_candidate_ids.insert(id.to_string());
        }
        let rejected = p4.pointer("/fixed_statuses/316L_FLIGHT_ANODE/status").and_then(Value::as_str);
        if !cand01_is_316l || rejected != Some("REJECTED_AS_CURRENT_BASELINE") {
            return Err(schema_err(
                P4_PATH,
                "CAND-01 = 316L with 316L_FLIGHT_ANODE REJECTED_AS_CURRENT_BASELINE not found",
            ));
        }

        let bus = parse_json(BUS_PATH, &read_verified(&repo_root.join(BUS_PATH), BUS_SHA256)?)?;
        let enum_ok = bus
            .pointer("/properties/variant/items/enum")
            .and_then(Value::as_array)
            .map(|a| a.iter().filter_map(Value::as_str).collect::<BTreeSet<_>>())
            .is_some_and(|s| s == vocab::BUS_VARIANTS.iter().copied().collect());
        if !enum_ok {
            return Err(schema_err(BUS_PATH, "variant enum differs from the registered bus variant vocabulary"));
        }

        Ok(GovernedContext {
            flight_configuration,
            hallthruster_commit,
            admitted_hall_members,
            screening_candidates,
            design_state_ids,
            anode_candidate_ids,
            // No admission record of NP-ICP-NEUTRALIZER exists (NE-02): its prereg status is PREREGISTERED_NOT_IMPLEMENTED.
            admitted_icp_producers: BTreeSet::new(),
            // No host-spacecraft thermal ICD exists (NE-07).
            spacecraft_thermal_icd_registered: false,
            hashes,
        })
    }

    pub fn flight_configuration(&self) -> &str {
        &self.flight_configuration
    }
    pub fn hallthruster_commit(&self) -> &str {
        &self.hallthruster_commit
    }
    pub fn admitted_hall_members(&self) -> &BTreeSet<String> {
        &self.admitted_hall_members
    }
    pub fn screening_candidates(&self) -> &BTreeSet<String> {
        &self.screening_candidates
    }
    pub fn design_state_ids(&self) -> &BTreeSet<String> {
        &self.design_state_ids
    }
    pub fn anode_candidate_ids(&self) -> &BTreeSet<String> {
        &self.anode_candidate_ids
    }
    pub fn admitted_icp_producers(&self) -> &BTreeSet<String> {
        &self.admitted_icp_producers
    }
    pub fn spacecraft_thermal_icd_registered(&self) -> bool {
        self.spacecraft_thermal_icd_registered
    }
    pub fn hashes(&self) -> &BTreeMap<String, String> {
        &self.hashes
    }

    #[cfg(test)]
    pub(crate) fn with_admitted_hall_member_for_unit_test(mut self, id: &str) -> Self {
        self.admitted_hall_members.insert(id.to_string());
        self
    }
}

// ------------------------------------------------------------------------------------------------ model 2.0.0

pub const PREREG_V2_DIR: &str = "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS";
/// sha256 of prereg_lock_v2.json (the anchor of model 2.0.0; it pins prereg_v2.json and PREREG_v2.md).
pub const PREREG_LOCK_V2_SHA256: &str = "727689fee6bd003295c53abfbc4185c93fab80620329c75062a956dbbb9742de";
/// sha256 of prereg_lock_v1.json (named by the v2 lock as its predecessor).
pub const PREREG_LOCK_V1_SHA256: &str = "3421e28c959dc5ac7de600acd8e94d83b1ded605bcc6095a81fccd4905470fc7";
/// The producer anchor: NP-ICP-NEUTRALIZER prereg_lock_v2.json.
pub const PRODUCER_LOCK_PATH: &str = "docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_lock_v2.json";
pub const PRODUCER_LOCK_SHA256: &str = "a180ceef37223467687d7d245ab790a172e8dad9ea4e90aa463d434383142287";
/// Canonical sha256 of the matched IF-ICP-THERMAL-v2 key table (equal on both sides).
pub const KEY_TABLE_V2_SHA256: &str = "33e495adadbe94a5113c5f6b9040156ec8309295cca15b812714038beaa51161";

/// The model 2.0.0 context: the v1 governed context (unchanged, every v1 pin verified) plus the v2 lock, its predecessor,
/// the producer anchor and the matched key table, each sha256-verified. A v1 run never reads any of this.
#[derive(Debug, Clone)]
pub struct GovernedContextV2 {
    v1: GovernedContext,
    prereg_v2_sha256: String,
    prereg_v2_md_sha256: String,
    hashes_v2: BTreeMap<String, String>,
}

/// Canonical sha256 of a key table: sorted-key compact JSON (serde_json maps are ordered).
pub fn canonical_sha256(v: &Value) -> String {
    sha256_hex(serde_json::to_string(v).expect("serializable").as_bytes())
}

impl GovernedContextV2 {
    pub fn load(repo_root: &Path) -> AbepResult<Self> {
        let v1 = GovernedContext::load(repo_root)?;
        let mut hashes_v2 = BTreeMap::new();
        let lock_rel = format!("{PREREG_V2_DIR}/prereg_lock_v2.json");
        let lock: Value = parse_json(&lock_rel, &read_verified(&repo_root.join(&lock_rel), PREREG_LOCK_V2_SHA256)?)?;
        hashes_v2.insert(lock_rel.clone(), PREREG_LOCK_V2_SHA256.to_string());
        let pin =
            |p: &str| lock.pointer(p).and_then(Value::as_str).map(String::from).ok_or_else(|| schema_err(&lock_rel, p));
        let (pj, pm) = (pin("/files/prereg_v2.json")?, pin("/files/PREREG_v2.md")?);
        if pin("/model_version")? != vocab::MODEL_VERSION_V2 {
            return Err(schema_err(&lock_rel, "model_version is not 2.0.0"));
        }
        if pin("/predecessor_lock/sha256")? != PREREG_LOCK_V1_SHA256 {
            return Err(schema_err(&lock_rel, "the v2 lock does not name the v1 lock as its predecessor"));
        }
        let v1_lock = format!("{PREREG_V2_DIR}/prereg_lock_v1.json");
        read_verified(&repo_root.join(&v1_lock), PREREG_LOCK_V1_SHA256)?;
        hashes_v2.insert(v1_lock, PREREG_LOCK_V1_SHA256.into());
        if pin("/producer_anchor/path")? != PRODUCER_LOCK_PATH
            || pin("/producer_anchor/sha256")? != PRODUCER_LOCK_SHA256
        {
            return Err(schema_err(&lock_rel, "producer anchor differs from NP-ICP-NEUTRALIZER prereg_lock_v2.json"));
        }
        if pin("/matched_key_table_sha256")? != KEY_TABLE_V2_SHA256 {
            return Err(schema_err(&lock_rel, "matched_key_table_sha256 differs"));
        }
        // The producer anchor and the producer's key table.
        let producer_lock: Value =
            parse_json(PRODUCER_LOCK_PATH, &read_verified(&repo_root.join(PRODUCER_LOCK_PATH), PRODUCER_LOCK_SHA256)?)?;
        hashes_v2.insert(PRODUCER_LOCK_PATH.into(), PRODUCER_LOCK_SHA256.into());
        let producer_prereg_rel = "docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_v2.json";
        let producer_pin = producer_lock
            .pointer("/files/prereg_v2.json")
            .and_then(Value::as_str)
            .ok_or_else(|| schema_err(PRODUCER_LOCK_PATH, "files.prereg_v2.json"))?;
        let producer: Value =
            parse_json(producer_prereg_rel, &read_verified(&repo_root.join(producer_prereg_rel), producer_pin)?)?;
        hashes_v2.insert(producer_prereg_rel.into(), producer_pin.into());
        // This model's prereg v2 and its key table.
        let prereg_rel = format!("{PREREG_V2_DIR}/prereg_v2.json");
        let prereg: Value = parse_json(&prereg_rel, &read_verified(&repo_root.join(&prereg_rel), &pj)?)?;
        hashes_v2.insert(prereg_rel.clone(), pj.clone());
        let md_rel = format!("{PREREG_V2_DIR}/PREREG_v2.md");
        read_verified(&repo_root.join(&md_rel), &pm)?;
        hashes_v2.insert(md_rel, pm.clone());
        let ours = prereg
            .pointer("/matched_interface/keys")
            .ok_or_else(|| schema_err(&prereg_rel, "matched_interface.keys"))?;
        let theirs = producer
            .pointer("/system_coupling_interfaces/IF-ICP-THERMAL-v2/keys")
            .ok_or_else(|| schema_err(producer_prereg_rel, "IF-ICP-THERMAL-v2 keys"))?;
        for (who, t) in [(&prereg_rel, ours), (&producer_prereg_rel.to_string(), theirs)] {
            let h = canonical_sha256(t);
            if h != KEY_TABLE_V2_SHA256 {
                return Err(schema_err(who, format!("key table sha256 {h} != {KEY_TABLE_V2_SHA256}")));
            }
        }
        // Every vocabulary row names the same id and key as the locked table, in the same order.
        let rows = ours.as_array().ok_or_else(|| schema_err(&prereg_rel, "keys is not an array"))?;
        let table: Vec<(String, String)> = rows
            .iter()
            .map(|r| {
                (
                    r.get("id").and_then(Value::as_str).unwrap_or_default().to_string(),
                    r.get("key").and_then(Value::as_str).unwrap_or_default().to_string(),
                )
            })
            .collect();
        let vocab_rows: Vec<(String, String)> =
            vocab::ICP_V2_KEYS.iter().map(|k| (k.id.to_string(), k.key.to_string())).collect();
        if table != vocab_rows {
            return Err(schema_err(&prereg_rel, "the consumer vocabulary differs from the locked key table"));
        }
        Ok(GovernedContextV2 { v1, prereg_v2_sha256: pj, prereg_v2_md_sha256: pm, hashes_v2 })
    }

    pub fn v1(&self) -> &GovernedContext {
        &self.v1
    }
    pub fn prereg_v2_sha256(&self) -> &str {
        &self.prereg_v2_sha256
    }
    pub fn prereg_v2_md_sha256(&self) -> &str {
        &self.prereg_v2_md_sha256
    }
    /// The v1 governed hashes plus the v2 locks, preregistrations and the producer anchor.
    pub fn hashes(&self) -> BTreeMap<String, String> {
        let mut h = self.v1.hashes().clone();
        h.extend(self.hashes_v2.clone());
        h
    }
}
