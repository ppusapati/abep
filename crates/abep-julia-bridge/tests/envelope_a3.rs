//! NP-HALL-PARAMETRIC-ENVELOPE addendum A3: the committed A3 case file reproduces from the locked addendum, the seeded
//! check set is the registered one, and the shard job pins every input. No test spawns Julia.

use abep_julia_bridge::envelope_a3::{self as a3, A3_SHARDS, R0, R1, R3};
use abep_provenance::workspace_repo_root;
use abep_types::pyjson::{self, Value};
use std::path::PathBuf;

fn repo() -> PathBuf {
    workspace_repo_root().unwrap()
}

#[test]
fn committed_a3_case_file_reproduces() {
    assert_eq!(a3::check(&repo()).unwrap(), 51);
}

fn field(c: &Value, k: &str) -> Value {
    c.as_dict().unwrap().get(k).unwrap().clone()
}

fn cells(c: &Value) -> i64 {
    match field(c, "cells") {
        Value::Int(i) => i.as_i64().unwrap(),
        other => panic!("cells {other:?}"),
    }
}

fn num(c: &Value, k: &str) -> f64 {
    field(c, k).to_f64().unwrap()
}

#[test]
fn refinements_change_only_the_registered_numerics() {
    let text = std::fs::read_to_string(repo().join(a3::A3_CASES_REL)).unwrap();
    let doc = pyjson::loads(&text).unwrap();
    let cases = doc.as_dict().unwrap().get("cases").unwrap().as_list().unwrap();
    assert_eq!(cases.len(), 51);
    for t in cases.chunks(3) {
        let r: Vec<String> = t.iter().map(|c| field(c, "a3_refinement").as_str().unwrap().to_string()).collect();
        assert_eq!(r, [R0, R1, R3]);
        assert_eq!(cells(&t[1]), 2 * cells(&t[0]));
        assert_eq!(cells(&t[2]), cells(&t[0]));
        assert_eq!(num(&t[2], "duration_s"), 2.0 * num(&t[0], "duration_s"));
        assert_eq!(num(&t[2], "average_start_s"), num(&t[0], "duration_s"));
        assert_eq!(num(&t[1], "duration_s"), num(&t[0], "duration_s"));
        for c in &t[1..] {
            for k in ["dt_s", "Vd", "mdot_kgps", "B_ref_T", "L_m", "r_in_m", "r_out_m", "domain_m"] {
                assert_eq!(num(c, k), num(&t[0], k), "{k}");
            }
            for k in ["transport", "B_profile", "v1_key", "v1_case_sha256"] {
                assert_eq!(field(c, k), field(&t[0], k), "{k}");
            }
        }
    }
}

#[test]
fn committed_xe_result_reproduces_from_the_frozen_runs() {
    let r = repo();
    let dir = r.join("docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE");
    let m = dir.join("runs/a3_numerics_v1_XE/h1_parametric_envelope_a3_numerics_v1_XE_raw_manifest.json");
    let sha = "6ff25d22ebb6f7419827fc5d2ab51472a87e44c2ce2826ceedbb831eeff0d296";
    let (v, md) = a3::score(&r, &m, sha, "e58502a2").unwrap();
    let mut t = pyjson::dumps(&v, &pyjson::DumpOptions::config_writer()).unwrap();
    t.push('\n');
    let (jf, mf) = a3::result_files("XE");
    assert_eq!(t, std::fs::read_to_string(dir.join(jf)).unwrap());
    assert_eq!(md, std::fs::read_to_string(dir.join(mf)).unwrap());
    assert_eq!(v.as_dict().unwrap().get("outcome").unwrap().as_str(), Some("A3_NOT_ADEQUATE"));
    // A tampered manifest pin is refused.
    assert!(a3::score(&r, &m, &"0".repeat(64), "x").is_err());
}

#[test]
fn shard_job_pins_the_a3_inputs() {
    let job = a3::shard_job(&repo(), 1, "/tmp/out", &|_| None).unwrap();
    assert_eq!(job.args[1], a3::A3_DRIVER_REL);
    assert_eq!(job.args[4], A3_SHARDS.to_string());
    let ins: Vec<&str> = job.inputs.iter().map(|x| x.0.as_str()).collect();
    for r in [a3::A3_DRIVER_REL, a3::A3_CASES_REL, a3::A3_LOCK_REL, a3::ADDENDUM_REL] {
        assert!(ins.contains(&r), "{r}");
    }
    assert!(a3::shard_job(&repo(), A3_SHARDS, "/tmp/out", &|_| None).is_err());
}
