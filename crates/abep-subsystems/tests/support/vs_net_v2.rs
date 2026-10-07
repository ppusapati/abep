//! Model 2.0.0 (NP-THERMAL-CATHODELESS prereg v2) verification support: the registered VS-NET (vs_net_v1.json,
//! unchanged) transformed to consume IF-ICP-THERMAL-v2, and the synthetic IF-ICP-THERMAL-v2 record of AL-10 v2. All
//! values are SYNTHETIC_TEST_DATA_NOT_EVIDENCE. The committed record file `verification/al10_v2_icp_record_v1.json` is
//! this builder's byte-identical output and is sha256-registered (al10_v2_registration_v1.json) before the scored
//! run, like VS-NET itself.

use super::*;
use abep_subsystems::thermal::governance::{KEY_TABLE_V2_SHA256, PRODUCER_LOCK_SHA256};
use abep_subsystems::thermal::output::ThermalOutput;
use abep_subsystems::thermal::{run_case_v2, GovernedContextV2};

pub const RECORD_REL_PATH: &str =
    "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/verification/al10_v2_icp_record_v1.json";
pub const REGISTRATION_REL_PATH: &str =
    "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/verification/al10_v2_registration_v1.json";
pub const SCENARIO_MEMBER: &str = "SYNTHETIC/P:AL-10-v2";

/// The consistent key set [W]: RF-S 45 = 5 + 40; RF 40 = 3 + 0.5 + 2.5 + 7 + 27; PL 27 = 15 + 2 + 4 + 3 + 3;
/// B 6.4 = 2.4 + 4.0; S 53.4 = 45 + 2 + 6.4 (the LS-01 ICP slot loads); CONS-I3 53.4.
pub const KEYS: [(&str, f64); 20] = [
    ("P_icp_slot_load_sum_W", 53.4),
    ("P_icp_rf_source_DC_W", 45.0),
    ("P_icp_rf_forward_W", 40.0),
    ("P_icp_abs_W", 27.0),
    ("P_icp_collector_bias_W", 6.4),
    ("Q_icp_rf_conversion_loss_W", 5.0),
    ("P_icp_rf_reflected_W", 3.0),
    ("Q_icp_line_W", 0.5),
    ("Q_icp_match_W", 2.5),
    ("P_icp_matching_DC_W", 2.0),
    ("Q_icp_coil_ohmic_W", 7.0),
    ("Q_icp_plasma_wall_W", 15.0),
    ("Q_icp_radiation_W", 2.0),
    ("Q_icp_extraction_W", 4.0),
    ("Q_icp_outflow_upstream_W", 3.0),
    ("Q_icp_outflow_downstream_W", 3.0),
    ("Q_icp_bias_collector_W", 2.4),
    ("Q_icp_bias_export_W", 4.0),
    ("P_icp_flow_control_W", 0.0),
    ("P_icp_assist_magnet_W", 0.0),
];

/// Producer per-node partitions [W] (TK-07 sums to 15, TK-12 to 2.4).
pub const SHARES_TK07: [(&str, f64); 4] =
    [("N_VESSEL", 8.0), ("N_COLLECTOR", 4.0), ("N_ANTENNA", 1.5), ("N_HOUSING", 1.5)];
pub const SHARES_TK12: [(&str, f64); 1] = [("N_COLLECTOR", 2.4)];

/// RX-H1-FACE f_up (registered partition record PART.f_up; weights sum to 1).
pub const F_UP: [(&str, f64); 8] = [
    ("H1_POLE_IN", 0.25),
    ("H1_POLE_OUT", 0.25),
    ("H1_WALL_IN", 0.125),
    ("H1_WALL_OUT", 0.125),
    ("H1_ANODE", 0.0625),
    ("N_MOUNT", 0.0625),
    ("N_HOUSING", 0.0625),
    ("EXPORT", 0.0625),
];

/// Interface keys added to the VS-NET node declarations for model 2.0.0 (each is a registered receiver of the key in
/// prereg v2 nodes_receives_interface_keys).
pub const RECEIVES_ADDED: [(&str, &[&str]); 9] = [
    ("N_COLLECTOR", &["Q_icp_bias_collector_W"]),
    ("N_HOUSING", &["Q_icp_outflow_upstream_W"]),
    ("N_MATCH", &["P_icp_matching_DC_W"]),
    ("N_MOUNT", &["Q_icp_outflow_upstream_W"]),
    ("H1_POLE_IN", &["Q_icp_outflow_upstream_W"]),
    ("H1_POLE_OUT", &["Q_icp_outflow_upstream_W"]),
    ("H1_WALL_IN", &["Q_icp_outflow_upstream_W"]),
    ("H1_WALL_OUT", &["Q_icp_outflow_upstream_W"]),
    ("H1_ANODE", &["Q_icp_outflow_upstream_W"]),
];

pub fn gov_v2() -> &'static GovernedContextV2 {
    static G: OnceLock<GovernedContextV2> = OnceLock::new();
    G.get_or_init(|| {
        GovernedContextV2::load(&workspace_repo_root().expect("repo root")).expect("v2 governed records verify")
    })
}

pub fn run_v2(case: &ThermalCase) -> ThermalOutput {
    run_case_v2(case, gov_v2(), &run_ctx())
}

pub fn vr(v: Option<f64>, status: &str) -> ValueRecord {
    ValueRecord {
        value: v.map(|x| json!(x)),
        units: Some("W".into()),
        status: Some(status.into()),
        evidence_class: Some(SYN.into()),
        source: Some(SYN_SOURCE.into()),
        uncertainty: Some(json!("none: synthetic verification input")),
        applicability_domain: Some(json!("synthetic verification domain")),
        validation_status: Some("NOT_APPLICABLE_SYNTHETIC".into()),
        hall_map: None,
    }
}

/// The consistent AL-10 v2 record (its bytes are registered).
pub fn build_record() -> InterfaceRecordV2 {
    let shares =
        |s: &[(&str, f64)]| -> BTreeMap<String, Value> { s.iter().map(|(n, w)| (n.to_string(), json!(w))).collect() };
    InterfaceRecordV2 {
        interface_id: "IF-ICP-THERMAL-v2".into(),
        producer_id: "NP-ICP-NEUTRALIZER".into(),
        producer_version: "2".into(),
        producer_lock_sha256: PRODUCER_LOCK_SHA256.into(),
        key_table_sha256: KEY_TABLE_V2_SHA256.into(),
        case_id: vs_net::CASE_ID.into(),
        case_class: "SYNTHETIC_VERIFICATION".into(),
        supply_mode: "AIR_PRIMARY".into(),
        design_state_id: None,
        operating_point_id: "VS-NET-OP-1".into(),
        configuration: "SYNTHETIC".into(),
        scenario_member_id: SCENARIO_MEMBER.into(),
        time_basis: TimeBasis { kind: "STEADY".into(), breakpoints_s: None },
        keys: KEYS.iter().map(|(k, v)| (k.to_string(), vr(Some(*v), "EVALUATED"))).collect(),
        node_shares_w: [
            ("Q_icp_plasma_wall_W".to_string(), shares(&SHARES_TK07)),
            ("Q_icp_bias_collector_W".to_string(), shares(&SHARES_TK12)),
        ]
        .into(),
    }
}

pub fn record_bytes(r: &InterfaceRecordV2) -> Vec<u8> {
    let mut s = serde_json::to_string_pretty(r).expect("serializable");
    s.push('\n');
    s.into_bytes()
}

pub fn load_registered_record() -> InterfaceRecordV2 {
    let root = workspace_repo_root().expect("repo root");
    serde_json::from_slice(&std::fs::read(root.join(RECORD_REL_PATH)).expect("AL-10 v2 record")).expect("parses")
}

/// VS-NET (registered bytes) consuming the registered IF-ICP-THERMAL-v2 record: model_version 2.0.0, the v1 ICP record
/// removed, the RECEIVES_ADDED declarations, PART.f_up registered for Q_icp_outflow_upstream_W (TK-06 split = the
/// registered PART.ohmic, f_rad = PART.icp_rad, both unchanged), sinks at `ts`.
pub fn vs_net_v2(case_id: &str, colocated: bool, ts: f64) -> ThermalCase {
    let mut c = vs_net::load_registered();
    c.model_version = Some("2.0.0".into());
    c.interfaces.icp = None;
    for (node, keys) in RECEIVES_ADDED {
        let n = c.nodes.iter_mut().find(|n| n.id == node).expect("VS-NET node");
        n.receives_interface_keys.extend(keys.iter().map(|k| k.to_string()));
    }
    let mut cb = Cb { c, evidence_class: SYN.into() };
    let weights: BTreeMap<&str, f64> = F_UP.iter().copied().collect();
    let fup = cb.record("PART.f_up", "partition", json!({ "weights": weights }), None);
    cb.c.partitions.insert("Q_icp_outflow_upstream_W".into(), fup);
    let mut c = cb.c;
    c.match_colocated = Some(colocated);
    if !colocated {
        // As v1 AL-10 (registered transformation): N_MATCH is present iff match_colocated.
        c.nodes.retain(|n| n.id != "N_MATCH");
        c.links.retain(|l| l.id != "L_MA_MO");
        c.solver.t_init_k.remove("N_MATCH");
    }
    c.interfaces.icp_v2 = Some(load_registered_record());
    vs_net::set_case_id(&mut c, case_id);
    if let Some(r) = c.interfaces.icp_v2.as_mut() {
        r.case_id = case_id.into();
    }
    vs_net::set_sinks(&mut c, ts);
    c
}

pub fn key_mut<'a>(c: &'a mut ThermalCase, k: &str) -> &'a mut ValueRecord {
    c.interfaces.icp_v2.as_mut().unwrap().keys.get_mut(k).unwrap()
}

pub fn set_key(c: &mut ThermalCase, k: &str, v: f64) {
    key_mut(c, k).value = Some(json!(v));
}

pub fn set_share(c: &mut ThermalCase, key: &str, node: &str, v: f64) {
    c.interfaces.icp_v2.as_mut().unwrap().node_shares_w.get_mut(key).unwrap().insert(node.into(), json!(v));
}
