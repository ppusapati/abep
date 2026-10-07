//! Plenum / feed contract v8: the typed fail-closed status of a transient result (additive library entries
//! `transient_run_assessed`, `transient_case_assessed`, `orbit_simulated_assessed` and the parity CLI entries of the
//! same names, plus `plenum.stability_spectrum`).
//!
//! A loop that starts at an unstable equilibrium stays there in exact arithmetic; its excursion is seeded only by
//! rounding and truncation noise, so its time-domain outputs are ill-posed. They must never be readable as a result:
//! the assessed record carries UNSTABLE_EQUILIBRIUM and the record only under "ill_posed_result". Fixture: the plants
//! and controllers of R45-192 / R45-331 (`data/r45_growing_mode_regression.json`). As event-sequence requests at the
//! design intake, R45-192 is unstable at every event (max Re lambda 0.045) and R45-331 stable (-0.17); the detuned
//! R45-192 orbit (Kp 0.5, Ti 3 s) is stable at every phase.

use serde_json::{json, Value};
use std::io::Write;
use std::process::{Command, Stdio};

fn cli(payload: &Value) -> Vec<Value> {
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
    res["results"].as_array().expect("results").clone()
}

fn fixture() -> Value {
    serde_json::from_str(include_str!("data/r45_growing_mode_regression.json")).expect("fixture parses")
}

fn case_args(fx: &Value, id: &str) -> Value {
    fx["cases"].as_array().expect("cases").iter().find(|c| c["id"] == id).expect("case")["request"]["args"].clone()
}

/// P42 / P43 request with the plant / controller of an orbit case at its design intake.
fn event_args(orbit: &Value) -> Value {
    json!({"filter": orbit["filter"], "plant": orbit["plant"], "plenum": orbit["plenum"],
           "controller": orbit["controller"], "r0": orbit["r0"], "intake": orbit["design"], "window_s": 60.0,
           "orbit_check": null})
}

#[test]
fn unstable_loop_time_domain_outputs_are_never_a_result() {
    let fx = fixture();
    let u = event_args(&case_args(&fx, "R45-192"));
    let s = event_args(&case_args(&fx, "R45-331"));
    let mut detuned = case_args(&fx, "R45-192");
    detuned["controller"]["Kp"] = json!(0.5);
    detuned["controller"]["Ti_s"] = json!(3.0);
    let reqs = json!([
        {"id": "u-case", "entry": "plenum.transient_case", "args": u},
        {"id": "u-case-a", "entry": "plenum.transient_case_assessed", "args": u},
        {"id": "u-run", "entry": "plenum.transient_run", "args": u},
        {"id": "u-run-a", "entry": "plenum.transient_run_assessed", "args": u},
        {"id": "u-class", "entry": "plenum.stability_class", "args": u},
        {"id": "u-spec", "entry": "plenum.stability_spectrum", "args": u},
        {"id": "s-case", "entry": "plenum.transient_case", "args": s},
        {"id": "s-case-a", "entry": "plenum.transient_case_assessed", "args": s},
        {"id": "d-orbit", "entry": "plenum.orbit_sim", "args": detuned},
        {"id": "d-orbit-a", "entry": "plenum.orbit_sim_assessed", "args": detuned},
    ]);
    let res = cli(&json!({"repo_root": concat!(env!("CARGO_MANIFEST_DIR"), "/../.."), "materials": fx["materials"],
                          "requests": reqs}));
    let by: std::collections::HashMap<&str, &Value> = res
        .iter()
        .map(|r| {
            assert_eq!(r["outcome"].as_str(), Some("OK"), "{r}");
            (r["id"].as_str().expect("id"), &r["value"])
        })
        .collect();
    for (plain, assessed) in [("u-case", "u-case-a"), ("u-run", "u-run-a")] {
        let a = by[assessed];
        assert_eq!(a["transient_status"], "UNSTABLE_EQUILIBRIUM", "{assessed}");
        assert_eq!(a["stability_class"], "U");
        assert_eq!(a["time_domain_label"], "ILL_POSED_UNSTABLE_EQUILIBRIUM");
        assert!(a.get("result").is_none(), "{assessed}: an unstable loop has no 'result'");
        assert_eq!(&a["ill_posed_result"], by[plain], "{assessed}: the labelled record is the plain record");
        assert!(a["re_lambda_max"].as_f64().expect("re") > 0.0);
    }
    for (plain, assessed, class) in [("s-case", "s-case-a", "S"), ("d-orbit", "d-orbit-a", "S")] {
        let a = by[assessed];
        assert_eq!(a["transient_status"], "EVALUATED", "{assessed}");
        assert_eq!(a["stability_class"], class);
        assert_eq!(a["time_domain_label"], Value::Null);
        assert!(a.get("ill_posed_result").is_none());
        assert_eq!(&a["result"], by[plain], "{assessed}: the result is the plain record, unchanged");
        assert!(a["re_lambda_max"].as_f64().expect("re") < 0.0);
    }
    // the spectrum entry reports the classified equilibria with their Jacobian blocks
    let (cl, sp) = (by["u-class"], by["u-spec"]);
    assert_eq!(cl["class"], sp["class"]);
    let (ev, eq) = (cl["events"].as_array().expect("events"), sp["equilibria"].as_array().expect("equilibria"));
    assert_eq!(ev.len(), 8);
    assert_eq!(ev.len(), eq.len());
    for (e, q) in ev.iter().zip(eq) {
        assert_eq!(e["eq"], q["eq"]);
        if q["eq"] == "UNSAT" {
            let re = q["eigenvalues"].as_array().expect("lam").iter().map(|z| z[0].as_f64().expect("re"));
            assert_eq!(re.fold(f64::NEG_INFINITY, f64::max), e["re_max"].as_f64().expect("re_max"));
            assert_eq!(q["jacobian"].as_array().expect("jac").len(), 5);
        }
    }
    assert_eq!(by["u-run-a"]["re_lambda_max"], by["u-case-a"]["re_lambda_max"]);
}

/// Downstream-consumer guard (contract v8): no crate outside abep-gaspath calls the plain transient entry points,
/// whose records carry no stability status. A future consumer goes through the `*_assessed` entries, which refuse the
/// time-domain outputs of an unstable loop (`Assessed::trusted`).
#[test]
fn no_crate_outside_gaspath_reads_plain_transient_records() {
    let crates = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
    let plain = ["transient_case(", "orbit_simulated(", "TransientRun", "transient::"];
    let mut hits = vec![];
    let mut stack = vec![];
    for e in std::fs::read_dir(&crates).expect("crates dir") {
        let p = e.expect("entry").path();
        if p.is_dir() && p.file_name().and_then(|n| n.to_str()) != Some("abep-gaspath") {
            stack.push(p);
        }
    }
    let mut n_files = 0;
    while let Some(d) = stack.pop() {
        for e in std::fs::read_dir(&d).expect("dir") {
            let p = e.expect("entry").path();
            let name = p.file_name().and_then(|n| n.to_str()).unwrap_or("");
            if p.is_dir() {
                if name != "target" {
                    stack.push(p);
                }
            } else if name.ends_with(".rs") {
                n_files += 1;
                let text = std::fs::read_to_string(&p).expect("source readable");
                for k in plain {
                    if text.contains(k) {
                        hits.push(format!("{}: {k}", p.display()));
                    }
                }
            }
        }
    }
    assert!(n_files > 50, "the workspace scan found only {n_files} sources");
    assert!(hits.is_empty(), "plain transient entry points used outside abep-gaspath: {hits:?}");
}
