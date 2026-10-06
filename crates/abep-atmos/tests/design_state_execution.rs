//! End to end: the frozen 196-state design-state set v2 is loaded and hash-verified, every state is executed, and the
//! run is deterministic (A9.29 sec. 6, RM-OQ-02; contract PARITY-C-ABEP_SIM_ATMOSPHERE_ORBIT_PY-V1 INV-D-02 / INV-D-03).

mod common;

use abep_atmos::design_state_set::{required_states, DesignState};
use abep_atmos::execution::{execute_states, run, run_design_state_set, Environment};
use abep_data::design_states::{DESIGN_STATE_DATASET_SHA256, DESIGN_STATE_SET_SHA256};
use abep_data::json::OValue;
use abep_provenance::{read_bytes, sha256_hex};
use abep_types::EvalStatus;

#[test]
fn all_196_states_execute_deterministically() {
    let root = common::repo_root();
    let file = root.join("abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json");
    let raw = read_bytes(&file).unwrap();
    assert_eq!(sha256_hex(&raw), DESIGN_STATE_SET_SHA256);
    let doc = OValue::parse(&raw, "design states v2").unwrap();
    let file_ids: Vec<String> = doc
        .get("states")
        .and_then(OValue::as_array)
        .unwrap()
        .iter()
        .map(|s| s.get("state_id").and_then(OValue::as_str).unwrap().to_string())
        .collect();
    assert_eq!(file_ids.len(), 196);

    let env = Environment::load(&root).expect("frozen environment loads and verifies");
    let a = run(&env).unwrap();
    assert_eq!(a.n_states, 196);
    assert_eq!(a.records.len(), 196);
    assert_eq!(a.n_evaluated, 196, "every state EVALUATED");
    assert_eq!((a.n_out_of_domain, a.n_model_error), (0, 0));
    assert_eq!(a.design_state_set_sha256, DESIGN_STATE_SET_SHA256);
    assert_eq!(a.dataset_sha256, DESIGN_STATE_DATASET_SHA256);
    let ids: Vec<&str> = a.records.iter().map(|r| r.state_id.as_str()).collect();
    assert_eq!(ids, file_ids.iter().map(String::as_str).collect::<Vec<_>>(), "file order");
    let mut uniq = ids.clone();
    uniq.sort();
    uniq.dedup();
    assert_eq!(uniq.len(), 196);
    for r in &a.records {
        assert_eq!(r.status, EvalStatus::Evaluated, "{}", r.state_id);
        let rep = r.frozen_dataset_reproduction.as_ref().unwrap();
        assert!(rep.reproduced && rep.max_abs_rel_diff <= 1e-12, "{} {}", r.state_id, rep.max_abs_rel_diff);
        let w = r.wind.as_ref().unwrap();
        assert_eq!(w.dataset_status, "DESIGN_ENVELOPE_PARAMETRIC");
        assert!(!w.used_in_free_stream_velocity);
        assert_eq!(w.wind.u_mer_m_s.to_bits(), (w.wind.u_mer_quiet_m_s + w.wind.u_mer_dist_m_s).to_bits());
        let e = r.environment.as_ref().unwrap();
        assert!((e.fO + e.fN2 + e.fO2 - 1.0).abs() <= 1e-14, "CONS-D-03");
        assert!((e.n * e.m_mean / e.rho - 1.0).abs() <= 1e-14, "CONS-D-03");
        assert!(e.V_basis.starts_with("V_ORB_INERTIAL_CIRCULAR"));
    }

    // Two runs, one from a fresh load: byte-identical serialized output.
    let b = run_design_state_set(&root).unwrap();
    let (sa, sb) = (serde_json::to_vec(&a).unwrap(), serde_json::to_vec(&b).unwrap());
    assert_eq!(sha256_hex(&sa), sha256_hex(&sb));
    assert_eq!(sa, sb);
    let c = serde_json::to_vec(&run(&env).unwrap()).unwrap();
    assert_eq!(sa, c);
}

#[test]
fn missing_or_altered_frozen_data_is_model_error() {
    let t = common::tree("exec_wind_missing");
    t.remove("atmosphere_msis21_hwm14_orbit_v2.csv.gz");
    assert_eq!(run_design_state_set(&t.root).unwrap_err().status(), EvalStatus::ModelError);

    let t = common::tree("exec_dist_altered");
    t.alter("atmosphere_msis21_hwm14_orbit_v2.disturbance.csv.gz", |b| b[4] ^= 1);
    assert_eq!(run_design_state_set(&t.root).unwrap_err().status(), EvalStatus::ModelError);

    let t = common::tree("exec_set_altered");
    t.alter("atmosphere_msis21_orbit_v1_design_states_v2.json", |b| {
        let i = b.windows(10).position(|w| w == b"python -m ").unwrap();
        b[i + 5] = b'N';
    });
    assert_eq!(run_design_state_set(&t.root).unwrap_err().status(), EvalStatus::ModelError);

    let t = common::tree("exec_set_missing");
    t.remove("atmosphere_msis21_orbit_v1_design_states_v2.json");
    assert_eq!(run_design_state_set(&t.root).unwrap_err().status(), EvalStatus::ModelError);

    let t = common::tree("exec_orbit_missing");
    t.remove("atmosphere_msis21_orbit_v1.csv.gz");
    assert_eq!(run_design_state_set(&t.root).unwrap_err().status(), EvalStatus::ModelError);
}

#[test]
fn a_state_outside_the_domain_is_out_of_domain_not_skipped() {
    let env = Environment::load(&common::repo_root()).unwrap();
    let states = required_states(&env.set).unwrap();
    let mut bad: DesignState = states[0].clone();
    bad.lat_deg = 95.0;
    let mut wrong: DesignState = states[1].clone();
    wrong.scenario = "ECSS_LT_MEDIUM".into();
    let recs = execute_states(&env, &[states[0].clone(), bad, wrong]);
    assert_eq!(recs.len(), 3);
    assert_eq!(recs[0].status, EvalStatus::Evaluated);
    assert_eq!(recs[1].status, EvalStatus::OutOfDomain);
    assert_eq!(recs[2].status, EvalStatus::OutOfDomain);
    assert!(recs[1].error.as_deref().unwrap().contains("lat_deg"));
}
