//! Regression of the plenum / feed contract v5 RUST_DEFECT (growing-mode damping, fixed by the growing-mode guard of
//! `abep_gaspath::transient`): the two refinement vectors that exposed it, R45-192 and R45-331 of the frozen v5
//! refinement grid (refinement seed 731905543; fixture `data/r45_growing_mode_regression.json`, written by
//! `scripts/rust_migration/plenum_v5_growing_mode_diagnosis.py fixture`).
//!
//! Both have an unstable closed loop at the steady start (0.0508 +/- 2.423i, 0.0365 +/- 2.259i). Before the guard the
//! nominal orbit_sim (rtol 1e-5) returned ok with the setpoint held (P_dev 1.2e-5 / 8.9e-6, ~3200 evaluations) while
//! the converged answer is P_dev 0.031 / 0.030 with the valve saturating. The nominal run must now reproduce the
//! converged Rust T1 record (rtol 1e-8) within the registered bound: the Python PROD P45 envelope E_py of the frozen
//! v5 record, i.e. the reference implementation's own measured nominal-tolerance error (no tolerance is invented here).
//! The request goes through the parity CLI so that the production request parsing is exercised as scored.

use serde_json::{json, Value};
use std::io::Write;
use std::process::{Command, Stdio};

fn num(v: &Value) -> f64 {
    match v {
        Value::Number(n) => n.as_f64().expect("f64"),
        other => panic!("not a finite number: {other}"),
    }
}

#[test]
fn nominal_orbit_sim_reproduces_the_converged_unstable_loop() {
    let fx: Value =
        serde_json::from_str(include_str!("data/r45_growing_mode_regression.json")).expect("fixture parses");
    let cases = fx["cases"].as_array().expect("cases");
    let requests: Vec<Value> = cases.iter().map(|c| c["request"].clone()).collect();
    let payload = json!({
        "repo_root": concat!(env!("CARGO_MANIFEST_DIR"), "/../.."),
        "materials": fx["materials"],
        "requests": requests,
    });
    let mut child = Command::new(env!("CARGO_BIN_EXE_abep-gaspath-parity"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("parity CLI starts");
    child.stdin.take().expect("stdin").write_all(payload.to_string().as_bytes()).expect("request written");
    let out = child.wait_with_output().expect("parity CLI runs");
    assert!(out.status.success(), "parity CLI exit {:?}", out.status);
    let res: Value = serde_json::from_slice(&out.stdout).expect("CLI output parses");
    let results = res["results"].as_array().expect("results");
    assert_eq!(results.len(), cases.len());
    let b_pdev = num(&fx["bound"]["F45.P_dev"]);
    let b_mdot = num(&fx["bound"]["F45.mdot"]);
    for (c, r) in cases.iter().zip(results) {
        let id = c["id"].as_str().expect("id");
        assert_eq!(r["id"].as_str(), Some(id));
        assert_eq!(r["outcome"].as_str(), Some("OK"), "{id}: {r}");
        let v = &r["value"];
        let t1 = &c["converged_rust_T1"];
        assert_eq!(v["ok"].as_bool(), Some(true), "{id}: {v}");
        let scale = num(&c["mdot_scale"]);
        let dp = (num(&v["P_dev_max_frac"]) - num(&t1["P_dev_max_frac"])).abs();
        assert!(dp <= b_pdev, "{id}: |P_dev N - T1| = {dp:e} > E_py {b_pdev:e}");
        for k in ["mdot_min_kgps", "mdot_max_kgps"] {
            let d = (num(&v[k]) - num(&t1[k])).abs() / scale;
            assert!(d <= b_mdot, "{id}: |{k} N - T1| / mdot_scale = {d:e} > E_py {b_mdot:e}");
        }
    }
}

fn cli(payload: &Value) -> Value {
    let mut child = Command::new(env!("CARGO_BIN_EXE_abep-gaspath-parity"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("parity CLI starts");
    child.stdin.take().expect("stdin").write_all(payload.to_string().as_bytes()).expect("request written");
    let out = child.wait_with_output().expect("parity CLI runs");
    assert!(out.status.success(), "parity CLI exit {:?}", out.status);
    serde_json::from_slice(&out.stdout).expect("CLI output parses")
}

/// Contract v7 input-only stability class (plenum.stability_class): R45-192 / R45-331 are unstable at the steady start
/// (phase 0 of the 24 quasi-static orbit phases: 0.0508 +/- 2.423i, 0.0365 +/- 2.259i, numpy on the reference
/// Jacobian); the same plants under a detuned controller (Kp 0.5, Ti 3 s) are stable at every phase (reference: max
/// Re lambda -0.065 / -0.071).
#[test]
fn stability_class_of_the_regression_vectors() {
    let fx: Value =
        serde_json::from_str(include_str!("data/r45_growing_mode_regression.json")).expect("fixture parses");
    let mut requests = vec![];
    for c in fx["cases"].as_array().expect("cases") {
        let id = c["id"].as_str().expect("id");
        let args = c["request"]["args"].clone();
        requests.push(json!({"id": id, "entry": "plenum.stability_class", "args": args.clone()}));
        let mut detuned = args;
        detuned["controller"]["Kp"] = json!(0.5);
        detuned["controller"]["Ti_s"] = json!(3.0);
        requests.push(json!({"id": format!("{id}-detuned"), "entry": "plenum.stability_class", "args": detuned}));
    }
    let res = cli(&json!({
        "repo_root": concat!(env!("CARGO_MANIFEST_DIR"), "/../.."),
        "materials": fx["materials"],
        "requests": requests,
    }));
    let want_re0 = [("R45-192", 0.0508), ("R45-331", 0.0365)];
    for r in res["results"].as_array().expect("results") {
        let id = r["id"].as_str().expect("id");
        assert_eq!(r["outcome"].as_str(), Some("OK"), "{id}: {r}");
        let v = &r["value"];
        let events = v["events"].as_array().expect("events");
        assert_eq!(events.len(), 24, "{id}: one equilibrium per quasi-static orbit phase");
        let res_max: Vec<f64> = events.iter().filter_map(|e| e["re_max"].as_f64()).collect();
        if id.ends_with("-detuned") {
            assert_eq!(v["class"].as_str(), Some("S"), "{id}: {v}");
            assert!(res_max.iter().all(|x| *x < 0.0), "{id}: {res_max:?}");
        } else {
            assert_eq!(v["class"].as_str(), Some("U"), "{id}: {v}");
            let want = want_re0.iter().find(|(k, _)| *k == id).expect("known id").1;
            assert!((res_max[0] - want).abs() < 5e-4, "{id}: phase-0 max Re lambda {} vs {want}", res_max[0]);
        }
    }
}
