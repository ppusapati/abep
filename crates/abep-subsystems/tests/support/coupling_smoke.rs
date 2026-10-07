//! The registered SYNTHETIC coupling smoke case of the model-v2 chain: NP-ICP-NEUTRALIZER model_version 2 ->
//! IF-ICP-THERMAL-v2 adapter -> NP-THERMAL-CATHODELESS 2.0.0 -> IF-ICP-BUS-v2 consumer -> CONS-L1 v2. Every value is
//! SYNTHETIC_TEST_DATA_NOT_EVIDENCE. The committed file `verification/coupling_smoke_v2_case_v1.json` is this
//! builder's byte-identical output, sha256-registered (coupling_smoke_v2_registration_v1.json) and committed alone
//! before its scored run; the run reads every input from the committed file.
//!
//! Compiled by the abep-mission test crate (crates/abep-mission/tests/coupling_smoke_v2.rs), which depends on both
//! abep-icp and abep-subsystems; abep-subsystems itself never links the producer (INV-A05 dependency set unchanged).

use crate::support::vs_net_v2::{F_UP, RECEIVES_ADDED};
use crate::support::{vs_net, SYN};
use abep_provenance::workspace_repo_root;
use serde_json::{json, Value};
use std::collections::BTreeMap;

pub const CASE_REL_PATH: &str =
    "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/verification/coupling_smoke_v2_case_v1.json";
pub const REGISTRATION_REL_PATH: &str =
    "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/verification/coupling_smoke_v2_registration_v1.json";
pub const ID: &str = "COUPLING-SMOKE-v2";

pub fn build() -> Value {
    let mut icp = abep_icp::v2::testkit::cal_case_v2(30.0, 3.0, 0.0, 30.0);
    icp.case_id = format!("{ID}/ICP");
    json!({
        "id": ID,
        "label": "SYNTHETIC",
        "evidence_class": SYN,
        "chain": [
            "NP-ICP-NEUTRALIZER model_version 2 (abep_icp::v2, CM-CAL, CFG-CAP-OFF, SYNTHETIC_TEST_ONLY)",
            "IF-ICP-THERMAL-v2 adapter (abep_subsystems::thermal::icp_v2_adapter), every producer scenario member",
            "NP-THERMAL-CATHODELESS 2.0.0 (run_case_v2) on the registered VS-NET",
            "IF-ICP-BUS-v2 consumer (icp_upstream_loads_v2) of the member's solve member",
            "CONS-L1 v2 (accounts_from_thermal_v2 + the LS-01 external accounts)"
        ],
        "icp_case": icp,
        "thermal": {
            "network_path": vs_net::VS_NET_REL_PATH,
            "network_sha256": "64c4bf335354bd9ffc7e4de602156d3ca26b1b6ee614e30558ccc94c897ec9a9",
            "case_id": format!("{ID}/THERMAL"),
            "operating_point_id": format!("{ID}/OP-1"),
            "sinks_K": 250.0,
            "match_colocated": true,
            "receives_added": RECEIVES_ADDED.iter().map(|(n, k)| (n.to_string(), k.to_vec())).collect::<BTreeMap<String, Vec<&str>>>(),
            "f_up": F_UP.iter().copied().collect::<BTreeMap<&str, f64>>(),
            "tk06_split": {"N_ANTENNA": 0.75, "N_HOUSING": 0.25},
            "f_rad": "PART.icp_rad of VS-NET (unchanged)"
        },
        "bus_ledger": {
            "rows": "LS-01 (tests/power_sys LS_01) with the ICP slot loads taken from the IF-ICP-BUS-v2 record and thermal_control = 3.0 W (VS-NET)",
            "eta_slot": {"icp_rf_source": 0.9, "icp_matching_network": 0.85, "icp_collector_bias": 0.8},
            "eta_front_end": 0.96,
            "thermal_control_W": 3.0
        },
        "closure_tolerances": {
            "producer": "CC-05 / CC-06 / CONS-I3 v2: 1e-10 relative to P_fwd + P_collector_bias (NP-ICP prereg v2)",
            "per_key_exactly_once": "CONS-I2: 1e-12 relative + 1e-12 W (NP-THERMAL E-07 v2)",
            "slot_load_sum": "CONS-I3: eps_if = 1e-6 x P_icp_slot_load_sum_W + 1e-9 W (NUM-09) and the producer's 1e-10",
            "system": "CONS-L1: |R| / P_bus < 2 % (CLAUDE.md rule 4); the ICP account mismatch within the producer's 1e-10"
        }
    })
}

pub fn to_bytes(v: &Value) -> Vec<u8> {
    let mut s = serde_json::to_string_pretty(v).expect("serializable");
    s.push('\n');
    s.into_bytes()
}

pub fn load_registered() -> Value {
    let root = workspace_repo_root().expect("repo root");
    serde_json::from_slice(&std::fs::read(root.join(CASE_REL_PATH)).expect("smoke case")).expect("parses")
}
