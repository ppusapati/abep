//! The admitted v1 paths read the v1 keys byte-identically after the 2.0.0 / IF-ICP-BUS-v2 work: the VS-NET steady
//! thermal output (IF-ICP-THERMAL-v1), the CONS-L1 system cases and the IF-ICP-BUS-v1 consumer give exactly the bytes
//! they gave at base 1c9e87f (sha256 pinned below).

mod power_sys;
mod support;

use abep_provenance::sha256_hex;
use abep_subsystems::power::icp_bus::icp_upstream_loads;
use abep_subsystems::power::official::MassPowerA9V5;
use abep_subsystems::power::slots::Slot;
use abep_subsystems::thermal::{run_case, RunContext};
use serde_json::json;

const PINNED_VS_NET_STEADY: &str = "5b4dc9466940e84e140201e496de7f333a5d3cce78243dc99bcead4202f31d2c";
const PINNED_CONS_L1: &str = "29627f702524abb8ad8c7d8fea19a4d39d0090c48389efc7b30ce09b13a2d9de";
const PINNED_ICP_BUS_V1: &str = "03888e912487b1f47c808c9cd6a396b5425bb55f95fb3a5641d300e884c12aea";

fn fixed_ctx() -> RunContext {
    RunContext { rust_commit: "V1_BYTE_IDENTITY".into(), rust_tree_dirty: false }
}

#[test]
fn thermal_v1_vs_net_steady_output_is_byte_identical() {
    let mut c = support::vs_net::load_registered();
    support::vs_net::set_case_id(&mut c, "V1-BYTE-IDENTITY");
    support::vs_net::set_sinks(&mut c, 250.0);
    let o = run_case(&c, support::gov(), &fixed_ctx());
    let h = sha256_hex(serde_json::to_string(&o).unwrap().as_bytes());
    assert_eq!(h, PINNED_VS_NET_STEADY);
}

#[test]
fn cons_l1_system_cases_are_byte_identical() {
    let root = abep_provenance::workspace_repo_root().unwrap();
    let mp = MassPowerA9V5::load(&root).unwrap();
    let rows: Vec<serde_json::Value> =
        power_sys::system_cases(&mp).iter().map(|(id, e, s)| power_sys::to_json(id, *e, s)).collect();
    let h = sha256_hex(serde_json::to_string(&rows).unwrap().as_bytes());
    assert_eq!(h, PINNED_CONS_L1);
}

#[test]
fn icp_bus_v1_consumer_is_byte_identical() {
    let q = |v: f64| json!({"value": v, "unit": "W", "status": "CONVERGED", "reasons": []});
    let rec = json!({
        "interface": "IF-ICP-BUS-v1",
        "target_boundary": "bus_power_boundary_a9_v2",
        "keys": {
            "P_icp_rf_source_DC_W": q(45.0), "P_icp_matching_DC_W": q(2.0), "P_icp_collector_bias_W": q(5.12),
            "P_icp_assist_magnet_W": q(0.0), "P_icp_flow_control_W": q(0.0),
            "P_icp_bus_W": q(53.4)
        }
    });
    let out = icp_upstream_loads(&rec, &[Slot::IcpAssistMagnet], "assumed", "SYNTHETIC v1 byte identity").unwrap();
    let h = sha256_hex(format!("{out:?}").as_bytes());
    assert_eq!(h, PINNED_ICP_BUS_V1);
    let v2 = json!({"interface": "IF-ICP-BUS-v2", "target_boundary": "bus_power_boundary_a9_v2", "keys": {}});
    assert!(icp_upstream_loads(&v2, &[], "assumed", "x").is_err(), "the v1 path refuses an IF-ICP-BUS-v2 record");
}
