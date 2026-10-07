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
