//! NP-THERMAL-CATHODELESS model 2.0.0 (prereg v2, lock 727689fe): the matched IF-ICP-THERMAL-v2 consumer. AL-10 v2
//! (consistent sets and every refusal), CONS-I3, FT-19..FT-23, determinism, the v2 lock, and the power lane's LC-18
//! (IF-ICP-BUS-v2 consumer and the CONS-L1 v2 ICP account). Every input is SYNTHETIC_TEST_DATA_NOT_EVIDENCE.

mod power_sys;
mod support;

use abep_provenance::{sha256_hex, workspace_repo_root};
use abep_subsystems::power::icp_bus::{icp_upstream_loads, icp_upstream_loads_v2};
use abep_subsystems::power::ledger::{ledger, LedgerArgs};
use abep_subsystems::power::slots::Slot;
use abep_subsystems::power::system_ledger::{accounts_from_thermal_v2, system_energy_ledger, Plane};
use abep_subsystems::thermal::output::{RunStatus, ThermalOutput};
use abep_subsystems::thermal::{run_case, GovernedContextV2};
use abep_types::pyjson::{Dict, Value as PyValue};
use abep_types::EvalStatus;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::path::Path;
use support::vs_net_v2::{self as v2, *};
use support::{has_code, SYN};

fn status(o: &ThermalOutput) -> RunStatus {
    o.run_status
}

fn rel(a: f64, b: f64) -> f64 {
    if a == b {
        0.0
    } else {
        (a - b).abs() / a.abs().max(b.abs())
    }
}

fn close(a: f64, b: f64) -> bool {
    (a - b).abs() <= 1e-12 * a.abs().max(b.abs()) + 1e-12
}

fn src(o: &ThermalOutput, node: &str, key: &str) -> f64 {
    o.results.as_ref().unwrap().q_source_node_w.get(node).and_then(|m| m.get(key)).copied().unwrap_or(0.0)
}

#[test]
fn al10_v2_record_file_is_the_registered_builder_output() {
    let root = workspace_repo_root().unwrap();
    let bytes = std::fs::read(root.join(v2::RECORD_REL_PATH)).unwrap();
    let reg: Value = serde_json::from_slice(&std::fs::read(root.join(v2::REGISTRATION_REL_PATH)).unwrap()).unwrap();
    assert_eq!(reg["record_sha256"].as_str().unwrap(), sha256_hex(&bytes));
    assert_eq!(reg["evidence_class"], SYN);
    assert_eq!(bytes, v2::record_bytes(&v2::build_record()), "the builder no longer reproduces the registered record");
    let vs = std::fs::read(root.join(support::vs_net::VS_NET_REL_PATH)).unwrap();
    assert_eq!(reg["network"]["vs_net_sha256"].as_str().unwrap(), sha256_hex(&vs), "VS-NET is unchanged");
}

#[test]
fn the_v2_context_verifies_its_lock_the_producer_anchor_and_the_matched_key_table() {
    let g = gov_v2();
    assert_eq!(g.prereg_v2_sha256(), "6828f3e257e38a588c9513f2531658035fa904b6c51e3b28831681d871adfa78");
    let h = g.hashes();
    assert_eq!(
        h["docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_lock_v2.json"],
        "a180ceef37223467687d7d245ab790a172e8dad9ea4e90aa463d434383142287"
    );
    // A changed byte of the v2 prereg is refused (copied root).
    let src_root = workspace_repo_root().unwrap();
    let dst = Path::new(env!("CARGO_TARGET_TMPDIR")).join("np_thermal_v2_tamper");
    let _ = std::fs::remove_dir_all(&dst);
    // Every governed input of the v1 and v2 contexts (directories copied whole).
    fn copy(from: &Path, to: &Path) {
        if from.is_dir() {
            for e in std::fs::read_dir(from).unwrap() {
                let e = e.unwrap();
                copy(&e.path(), &to.join(e.file_name()));
            }
        } else {
            std::fs::create_dir_all(to.parent().unwrap()).unwrap();
            std::fs::copy(from, to).unwrap();
        }
    }
    for rel in [
        "config",
        "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS",
        "docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER",
        "hallthruster_bridge/ensemble/transport_ensemble_v0.json",
        "hallthruster_bridge/PINNED.toml",
        "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
        "schemas/interfaces/bus_power_boundary_a9_v2.json",
        "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json",
    ] {
        copy(&src_root.join(rel), &dst.join(rel));
    }
    let _ = &h;
    GovernedContextV2::load(&dst).expect("the copied root loads");
    let p = dst.join("docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/prereg_v2.json");
    let mut b = std::fs::read(&p).unwrap();
    let i = b.iter().position(|c| *c == b'2').unwrap();
    b[i] = b'3';
    std::fs::write(&p, b).unwrap();
    assert!(GovernedContextV2::load(&dst).is_err(), "a changed prereg_v2 byte must be refused");
}

fn consistent(colocated: bool) -> ThermalOutput {
    run_v2(&vs_net_v2(&format!("AL-10-v2/consistent/colocated={colocated}"), colocated, 250.0))
}

#[test]
fn al10_v2_consistent_sets_land_every_key_on_its_receivers_and_close_cons_i2_i3() {
    for colocated in [true, false] {
        let o = consistent(colocated);
        assert_eq!(status(&o), RunStatus::Converged, "{:#?}", o.status_reasons);
        assert_eq!(o.model_version, "2.0.0");
        let r = o.results.as_ref().unwrap();
        let checks: BTreeMap<&str, bool> = r.energy_balance.checks.iter().map(|c| (c.id.as_str(), c.met)).collect();
        assert_eq!(checks.get("CONS-I2"), Some(&true));
        assert_eq!(checks.get("CONS-I3"), Some(&true), "{checks:?}");
        let d = r.interface_derived.as_ref().unwrap().icp_v2.as_ref().unwrap();
        assert!(d.cons_i3_residual_w.unwrap() <= 1e-12 * 53.4);
        // TK-07 / TK-12 producer shares; TK-06 = 7 x PART.ohmic; TK-08 = 2 x PART.icp_rad; TK-10 = 3 x f_up.
        for (n, w) in SHARES_TK07 {
            assert!(close(src(&o, n, "Q_icp_plasma_wall_W"), w), "{n}");
        }
        assert!(close(src(&o, "N_COLLECTOR", "Q_icp_bias_collector_W"), 2.4));
        for (n, w) in [("N_ANTENNA", 0.7), ("N_COLLECTOR", 0.2), ("N_HOUSING", 0.1)] {
            assert!(close(src(&o, n, "Q_icp_coil_ohmic_W"), 7.0 * w), "{n}");
        }
        for (n, w) in [
            ("N_VESSEL", 0.3),
            ("N_ANTENNA", 0.1),
            ("N_COLLECTOR", 0.1),
            ("N_HOUSING", 0.1),
            ("H1_POLE_IN", 0.1),
            ("H1_POLE_OUT", 0.1),
        ] {
            assert!(close(src(&o, n, "Q_icp_radiation_W"), 2.0 * w), "{n}");
        }
        for (n, w) in F_UP.iter().filter(|x| x.0 != "EXPORT") {
            assert!(close(src(&o, n, "Q_icp_outflow_upstream_W"), 3.0 * w), "TK-10 shares exactly f_up: {n}");
        }
        // Exported, deposited on no node: TK-09, TK-11, TK-13 and the EXPORT shares.
        let e = &r.p_exported_w;
        assert_eq!(e["Q_icp_extraction_W"], [4.0]);
        assert_eq!(e["Q_icp_outflow_downstream_W"], [3.0]);
        assert_eq!(e["Q_icp_bias_export_W"], [4.0]);
        assert!(close(e["Q_icp_radiation_W.EXPORT"][0], 0.4));
        assert!(close(e["Q_icp_outflow_upstream_W.EXPORT"][0], 3.0 * 0.0625));
        for k in ["Q_icp_extraction_W", "Q_icp_outflow_downstream_W", "Q_icp_bias_export_W"] {
            assert!(r.q_source_node_w.values().all(|m| !m.contains_key(k)), "{k} deposited on a node");
        }
        // B_PPU_RF booking by key and sub-account; no remainder key.
        let b = &r.q_boundary_w.b_ppu_rf_booked;
        assert!(!b.contains_key("Q_icp_boundary_W"));
        assert_eq!(b["RF_SOURCE:Q_icp_rf_conversion_loss_W"], [5.0]);
        assert_eq!(b["RF_SOURCE:P_icp_rf_reflected_W"], [3.0]);
        assert_eq!(b["RF_CHAIN:Q_icp_line_W"], [0.5]);
        if colocated {
            assert!(close(src(&o, "N_MATCH", "Q_icp_match_W"), 2.5));
            assert!(close(src(&o, "N_MATCH", "P_icp_matching_DC_W"), 2.0));
            assert!(!b.contains_key("RF_CHAIN:Q_icp_match_W"));
            assert!(close(d.b_ppu_rf_sub_account_w["RF_CHAIN"][0], 0.5));
        } else {
            assert_eq!(src(&o, "N_MATCH", "Q_icp_match_W"), 0.0);
            assert_eq!(b["RF_CHAIN:Q_icp_match_W"], [2.5]);
            assert_eq!(b["RF_CHAIN:P_icp_matching_DC_W"], [2.0]);
            assert!(close(d.b_ppu_rf_sub_account_w["RF_CHAIN"][0], 5.0));
        }
        assert!(close(d.b_ppu_rf_sub_account_w["RF_SOURCE"][0], 8.0));
        // FT-23 / O-17 v2.
        assert_eq!(o.provenance.scenario_member_id.as_deref(), Some(SCENARIO_MEMBER));
        assert_eq!(o.provenance.model_version, "2.0.0");
        assert!(o.provenance.interface_record_sha256.contains_key("IF-ICP-THERMAL-v2"));
        assert_eq!(
            o.provenance.producer_lock_sha256.as_deref(),
            Some("a180ceef37223467687d7d245ab790a172e8dad9ea4e90aa463d434383142287")
        );
    }
}

#[test]
fn al10_v2_signed_tk12_with_positive_node_totals_converges() {
    let mut c = vs_net_v2("AL-10-v2/signed-tk12", true, 250.0);
    set_key(&mut c, "Q_icp_bias_collector_W", -1.0);
    set_key(&mut c, "Q_icp_bias_export_W", 7.4);
    set_share(&mut c, "Q_icp_bias_collector_W", "N_COLLECTOR", -1.0);
    let o = run_v2(&c);
    assert_eq!(status(&o), RunStatus::Converged, "{:#?}", o.status_reasons);
    let d = o.results.as_ref().unwrap().interface_derived.as_ref().unwrap().icp_v2.clone().unwrap();
    assert!(close(d.node_total_w["N_COLLECTOR"][0], 3.0));
}

fn refused(c: &ThermalCase, want: RunStatus, code: &str) {
    let o = run_v2(c);
    assert_eq!(status(&o), want, "{}: {:#?}", c.case_id, o.status_reasons);
    assert!(has_code(&o, code), "{}: {code} missing in {:#?}", c.case_id, o.status_reasons);
    assert!(o.results.is_none());
}

use abep_subsystems::thermal::case::ThermalCase;

#[test]
fn al10_v2_violations_and_refusals_give_their_registered_statuses() {
    let me = RunStatus::ModelError;
    let base = || vs_net_v2("AL-10-v2/edit", true, 250.0);
    // IFI2-02: an unsigned key < 0 (with its identities kept).
    let mut c = base();
    set_key(&mut c, "Q_icp_line_W", -0.5);
    refused(&c, me, "IFI2-02_VIOLATED");
    // IFI2-03..IFI2-07: one identity broken at a time.
    for (k, v, code) in [
        ("Q_icp_rf_conversion_loss_W", 6.0, "IFI2-03_VIOLATED"),
        ("P_icp_abs_W", 28.0, "IFI2-04_VIOLATED"),
        ("Q_icp_extraction_W", 5.0, "IFI2-05_VIOLATED"),
        ("Q_icp_bias_export_W", 4.5, "IFI2-06_VIOLATED"),
        ("P_icp_slot_load_sum_W", 54.0, "IFI2-07_VIOLATED"),
    ] {
        let mut c = base();
        set_key(&mut c, k, v);
        refused(&c, me, code);
    }
    // IFI2-08: a producer partition that does not sum to its key; a negative N_COLLECTOR total (FT-22).
    let mut c = base();
    set_share(&mut c, "Q_icp_plasma_wall_W", "N_VESSEL", 9.0);
    refused(&c, me, "IFI2-08_VIOLATED");
    let mut c = base();
    set_key(&mut c, "Q_icp_bias_collector_W", -5.0);
    set_key(&mut c, "Q_icp_bias_export_W", 11.4);
    set_share(&mut c, "Q_icp_bias_collector_W", "N_COLLECTOR", -5.0);
    refused(&c, me, "IFI2-08_VIOLATED");
    // IFI2-09: a registered partition whose weights do not sum to 1.
    let mut c = base();
    let r = c.records.iter_mut().find(|r| r.id.as_deref() == Some("PART.f_up")).unwrap();
    r.value.as_mut().unwrap()["weights"]["EXPORT"] = json!(0.1);
    refused(&c, me, "PARTITION_WEIGHTS_SUM");
    // A missing key (IFI2-01); a key INCOMPLETE_EVIDENCE; a key NOT_EVALUATED (no zero-fill, FT-18).
    let mut c = base();
    c.interfaces.icp_v2.as_mut().unwrap().keys.remove("Q_icp_match_W");
    refused(&c, me, "INTERFACE_KEY_MISSING");
    for (st, want, code) in [
        ("INCOMPLETE_EVIDENCE", RunStatus::IncompleteEvidence, "INTERFACE_KEY_INCOMPLETE_EVIDENCE"),
        ("NOT_EVALUATED", RunStatus::NotEvaluated, "INTERFACE_KEY_NOT_EVALUATED"),
    ] {
        let mut c = base();
        let k = key_mut(&mut c, "Q_icp_radiation_W");
        k.status = Some(st.into());
        k.value = None;
        refused(&c, want, code);
    }
    // FT-19: an IF-ICP-THERMAL-v1 record; a retired key; a Hall-powered key.
    let mut c = base();
    c.interfaces.icp = support::vs_net::load_registered().interfaces.icp;
    c.interfaces.icp.as_mut().unwrap().case_id = c.case_id.clone();
    refused(&c, me, "INTERFACE_VERSION_MISMATCH");
    let mut c = base();
    c.interfaces.icp_v2.as_mut().unwrap().keys.insert("P_icp_bus_W".into(), vr(Some(55.0), "EVALUATED"));
    refused(&c, me, "RETIRED_KEY");
    let mut c = base();
    c.interfaces.icp_v2.as_mut().unwrap().keys.insert("Q_hall_return_to_icp_W".into(), vr(Some(8.0), "EVALUATED"));
    refused(&c, me, "ENERGY_SOURCE_RULE");
    // FT-20: TK-10 > 0 without f_up; no TK-06 split.
    let mut c = base();
    c.partitions.remove("Q_icp_outflow_upstream_W");
    refused(&c, RunStatus::IncompleteEvidence, "RX-H1-FACE_PARTITION_NOT_REGISTERED");
    let mut c = base();
    c.partitions.remove("Q_icp_coil_ohmic_W");
    refused(&c, RunStatus::IncompleteEvidence, "TK-06_SPLIT_NOT_REGISTERED");
    // TK-10 = 0 exactly needs no partition.
    let mut c = base();
    c.partitions.remove("Q_icp_outflow_upstream_W");
    set_key(&mut c, "Q_icp_outflow_upstream_W", 0.0);
    set_key(&mut c, "Q_icp_outflow_downstream_W", 6.0);
    let o = run_v2(&c);
    assert_eq!(status(&o), RunStatus::Converged, "{:#?}", o.status_reasons);
    // FT-21: CFG-FLIGHT-HALL-ON.
    let mut c = base();
    c.interfaces.icp_v2.as_mut().unwrap().configuration = "CFG-FLIGHT-HALL-ON".into();
    refused(&c, RunStatus::NotEvaluated, "CPL_HALL_ON_CONSUMER_VERSION_NOT_REGISTERED");
    // The producer anchor and key table hashes are checked (IFI2-01).
    let mut c = base();
    c.interfaces.icp_v2.as_mut().unwrap().key_table_sha256 = "0".repeat(64);
    refused(&c, me, "IFI2-01_KEY_TABLE_MISMATCH");
    // Variants: installed flow control -> INCOMPLETE_EVIDENCE; installed assist magnet -> OUT_OF_DOMAIN.
    let mut c = base();
    set_key(&mut c, "P_icp_flow_control_W", 1.0);
    set_key(&mut c, "P_icp_slot_load_sum_W", 54.4);
    let o = run_v2(&c);
    assert!(has_code(&o, "VARIANT_RECEIVER_NOT_REGISTERED"));
}

#[test]
fn ft19_model_versions_never_cross() {
    // The v1 entry point refuses a 2.0.0 case; the v2 entry point refuses a v1 case.
    let c = vs_net_v2("FT-19/v1-entry", true, 250.0);
    let o = run_case(&c, support::gov(), &support::run_ctx());
    assert_eq!(o.run_status, RunStatus::ModelError);
    assert!(has_code(&o, "MODEL_VERSION_MISMATCH") && has_code(&o, "INTERFACE_VERSION"));
    assert_eq!(o.model_version, "1.0.0");
    let mut v1 = support::vs_net::load_registered();
    support::vs_net::set_sinks(&mut v1, 250.0);
    let o = run_v2(&v1);
    assert_eq!(o.run_status, RunStatus::ModelError);
    assert!(has_code(&o, "MODEL_VERSION_MISMATCH") && has_code(&o, "INTERFACE_VERSION_MISMATCH"));
}

#[test]
fn det_v2_runs_are_deterministic() {
    let a = consistent(true).to_json();
    let b = consistent(true).to_json();
    assert_eq!(a, b);
}

// ------------------------------------------------------------------------------------------------------- LC-18

/// A synthetic IF-ICP-BUS-v2 record in the producer's serialized form (abep-icp BusRecordV2).
fn bus_v2_record() -> Value {
    let k = |id: &str, plane: &str, slot: Option<&str>, state: &str, v: f64| {
        json!({"id": id, "plane": plane, "plane_definition": "synthetic", "slot": slot, "slot_state": state,
               "value": v, "unit": "W", "status": "CONVERGED", "reasons": []})
    };
    json!({
        "interface": "IF-ICP-BUS-v2",
        "target_boundary": "bus_power_boundary_a9_v2",
        "configuration": "SYNTHETIC",
        "solve_member_id": "SYNTHETIC",
        "flags": ["SYNTHETIC_TEST_ONLY"],
        "keys": {
            "P_icp_rf_source_DC_W": k("BK-01", "LOAD", Some("icp_rf_source"), "INSTALLED", 45.0),
            "P_icp_matching_DC_W": k("BK-02", "LOAD", Some("icp_matching_network"), "INSTALLED", 2.0),
            "P_icp_collector_bias_W": k("BK-03", "LOAD", Some("icp_collector_bias"), "INSTALLED", 6.4),
            "P_icp_assist_magnet_W": k("BK-04", "LOAD", Some("icp_assist_magnet"), "NOT_INSTALLED", 0.0),
            "P_icp_flow_control_W": k("BK-05", "LOAD", Some("flow_control_icp_feed"), "NOT_INSTALLED", 0.0),
            "P_icp_slot_load_sum_W": k("BK-06", "LOAD_PLANE_SUM", None, "-", 53.4),
            "P_icp_rf_forward_W": k("BK-07", "RF_FORWARD", None, "-", 40.0),
            "P_icp_rf_reflected_W": k("BK-08", "RF_REFLECTED", None, "-", 3.0),
            "P_icp_delivered_W": k("BK-09", "RF_DELIVERED", None, "-", 37.0),
            "Q_icp_rf_conversion_loss_W": k("BK-10", "INSIDE_LOAD", None, "-", 5.0)
        },
        "checks": [], "status": "CONVERGED", "reasons": []
    })
}

const ETA: [(Slot, f64); 3] =
    [(Slot::IcpRfSource, 0.9), (Slot::IcpMatchingNetwork, 0.85), (Slot::IcpCollectorBias, 0.8)];
const ETA_FE: f64 = 0.96;

#[test]
fn lc18_bus_v2_plane_identity_ledger_and_cons_l1_v2_icp_account() {
    let rec = bus_v2_record();
    let loads = icp_upstream_loads_v2(&rec, &[], "assumed", "SYNTHETIC LC-18", false).unwrap();
    assert_eq!(loads.len(), 3, "undeclared variants are NOT_INSTALLED records and are not loads");
    // The bus ledger with eta_slot < 1 and eta_front_end < 1; NP-ICP values enter at the load planes exactly.
    let mut l = Dict::new();
    let mut e = Dict::new();
    for (s, p, eff) in power_sys::LS_01 {
        let p = match (s, loads.iter().find(|(x, _)| *x == s)) {
            (_, Some((_, abep_subsystems::power::demand::Upstream::Evaluated { p_w, .. }))) => *p_w,
            (Slot::ThermalControl, _) => power_sys::VS_NET_THERMAL_CONTROL_W,
            _ => p,
        };
        let eff = ETA.iter().find(|x| x.0 == s).map_or(eff, |x| x.1);
        let mut d = Dict::new();
        d.insert("P_W", PyValue::Float(p));
        d.insert("evidence_class", PyValue::str("assumed"));
        d.insert("source", PyValue::str(power_sys::SYN));
        if s == Slot::IcpRfSource {
            d.insert("plane", PyValue::str("generator_dc_input"));
        }
        l.insert(s.name(), PyValue::Dict(d));
        let mut f = Dict::new();
        f.insert("value", PyValue::Float(eff));
        f.insert("evidence_class", PyValue::str("assumed"));
        f.insert("source", PyValue::str(power_sys::SYN));
        f.insert("path", PyValue::str("internal_bus"));
        e.insert(s.name(), PyValue::Dict(f));
    }
    let mut fe = Dict::new();
    fe.insert("value", PyValue::Float(ETA_FE));
    fe.insert("evidence_class", PyValue::str("assumed"));
    fe.insert("source", PyValue::str(power_sys::SYN));
    let mut a = LedgerArgs::new(PyValue::Dict(l), PyValue::Dict(e), PyValue::Dict(fe));
    a.label = PyValue::str("LC-18");
    let led = ledger(&a).expect("valid ledger");
    for (s, up) in &loads {
        let abep_subsystems::power::demand::Upstream::Evaluated { p_w, .. } = up else { panic!("evaluated") };
        let it = led.item(*s);
        assert_eq!(it.p_w, Some(*p_w), "{}: the NP-ICP value equals the slot load-plane value exactly", s.name());
        let eta = ETA.iter().find(|x| x.0 == *s).unwrap().1;
        assert!(rel(it.p_bus_w.unwrap(), p_w / (eta * ETA_FE)) <= 1e-12, "{}: P_bus = P_W / (eta eta_FE)", s.name());
    }
    // CONS-L1 with the v2 ICP account from the model 2.0.0 thermal output of the same loads.
    let out = consistent(true);
    let mut accounts = accounts_from_thermal_v2(&out);
    accounts.extend(power_sys::externals());
    let icp = accounts.iter().find(|a| a.account_id == "ICP").unwrap();
    assert_eq!(icp.status, EvalStatus::Evaluated, "{}", icp.source);
    assert_eq!(icp.slots, abep_subsystems::power::system_ledger::ICP_V2_PLANES.to_vec());
    assert!(icp.slots.iter().all(|(_, p)| *p == Plane::Load));
    let s = system_energy_ledger(&led, &accounts);
    assert_eq!(s.status, EvalStatus::Evaluated, "{:?}", s.reasons);
    let row = s.rows.iter().find(|r| r.account_id == "ICP").unwrap();
    assert!(close(row.ledger_w, 53.4), "load-plane sum {}", row.ledger_w);
    assert!(row.mismatch_w.abs() <= 1e-9, "ICP account closes: {}", row.mismatch_w);
    let loss: f64 = ETA
        .iter()
        .map(|(sl, eta)| {
            let p = led.item(*sl).p_w.unwrap();
            p / (eta * ETA_FE) - p
        })
        .sum();
    assert!(rel(row.supply_loss_outside_w, loss) <= 1e-12, "the ledger P_loss is the supply loss outside the account");
    assert!(s.relative_residual.unwrap() < 1e-12, "{:?}", s.relative_residual);
}

#[test]
fn lc18_bus_v2_refusals() {
    let ok = bus_v2_record();
    // The v1 consumer refuses a v2 record and the v2 consumer refuses a v1 record.
    assert!(icp_upstream_loads(&ok, &[], "assumed", "x").is_err());
    let mut v1 = ok.clone();
    v1["interface"] = json!("IF-ICP-BUS-v1");
    assert!(icp_upstream_loads_v2(&v1, &[], "assumed", "x", false).is_err());
    // P_icp_bus_W present is MODEL_ERROR; a LOAD key off its plane / slot is refused.
    let mut bus = ok.clone();
    bus["keys"]["P_icp_bus_W"] = json!({"value": 53.4, "status": "CONVERGED"});
    assert!(icp_upstream_loads_v2(&bus, &[], "assumed", "x", false).is_err());
    let mut plane = ok.clone();
    plane["keys"]["P_icp_matching_DC_W"]["plane"] = json!("SUPPLY_INPUT");
    assert!(icp_upstream_loads_v2(&plane, &[], "assumed", "x", false).is_err());
    // BUS2-04: the flight ledger consumes CFG-FLIGHT-HALL-ON only and never a ground-facility supply.
    assert!(icp_upstream_loads_v2(&ok, &[], "assumed", "x", true).is_err());
    let mut ground = ok.clone();
    ground["configuration"] = json!("CFG-FLIGHT-HALL-ON");
    ground["flags"] = json!(["INCLUDES_GROUND_FACILITY_SUPPLY"]);
    assert!(icp_upstream_loads_v2(&ground, &[], "assumed", "x", true).is_err());
    // An installed variant the ledger does not declare.
    let mut var = ok.clone();
    var["keys"]["P_icp_assist_magnet_W"]["slot_state"] = json!("INSTALLED_VARIANT");
    var["keys"]["P_icp_assist_magnet_W"]["value"] = json!(3.0);
    assert!(icp_upstream_loads_v2(&var, &[], "assumed", "x", false).is_err());
    // A key that is not CONVERGED is an absent upstream input with its status (never a placeholder).
    let mut ne = ok;
    ne["keys"]["P_icp_rf_source_DC_W"]["status"] = json!("NOT_EVALUATED");
    ne["keys"]["P_icp_rf_source_DC_W"]["value"] = Value::Null;
    let l = icp_upstream_loads_v2(&ne, &[], "assumed", "x", false).unwrap();
    assert!(matches!(
        l[0].1,
        abep_subsystems::power::demand::Upstream::Absent { status: EvalStatus::NotEvaluated, .. }
    ));
    // A model 1.0.0 output has no v2 ICP account.
    let v1_out = power_sys::vs_net_steady();
    let a = accounts_from_thermal_v2(&v1_out);
    assert_eq!(a.iter().find(|x| x.account_id == "ICP").unwrap().status, EvalStatus::ModelError);
}
