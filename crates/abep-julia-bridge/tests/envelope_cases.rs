//! NP-HALL-PARAMETRIC-ENVELOPE v1: case generation, bridge dry run, shard job and freeze -> ingestion round trip.
//! No test spawns Julia. The raw records of the round trip are SYNTHETIC_TEST_DATA_NOT_EVIDENCE: they live only in the
//! test's temporary directory and never in a record.

use abep_hall::envelope::{self as env, Family, RunStatus, LOCK_SHA256};
use abep_julia_bridge::envelope_cases::{
    check, freeze, shard_job, B_PROFILE_FIELDS, N_SHARDS, RUN_CASE_FIELDS, TRANSPORT_FIELDS,
};
use abep_provenance::workspace_repo_root;
use abep_types::pyjson::{self, Dict, Value};
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};

fn repo() -> PathBuf {
    workspace_repo_root().unwrap()
}

#[test]
fn committed_case_file_reproduces_and_passes_the_bridge_dry_run() {
    assert_eq!(check(&repo()).unwrap(), 4536);
}

#[test]
fn case_grid_is_the_preregistered_grid() {
    let cs = env::load_case_set(&repo()).unwrap();
    assert_eq!(cs.bz_family_kind, env::BzFamilyKind::SourcedSurrogate);
    for f in Family::ALL {
        assert_eq!(cs.cases.iter().filter(|c| c.family == f).count(), 2268, "{}", f.as_str());
    }
    let axis = |g: &dyn Fn(&env::CaseInfo) -> String| cs.cases.iter().map(g).collect::<BTreeSet<_>>().len();
    assert_eq!(axis(&|c| c.geometry_id.clone()), 7);
    assert_eq!(axis(&|c| c.bz_shape_id.clone()), 2);
    assert_eq!(axis(&|c| c.b_peak_id.clone()), 2);
    assert_eq!(axis(&|c| c.vd_id.clone()), 3);
    assert_eq!(axis(&|c| c.mdot_id.clone()), 3);
    assert_eq!(axis(&|c| c.transport_id.clone()), 9);
    let vds: BTreeSet<String> = cs.cases.iter().map(|c| format!("{}", c.vd_v)).collect();
    assert_eq!(vds, ["180", "265", "350"].iter().map(|s| s.to_string()).collect());
    let bps: BTreeSet<String> = cs.cases.iter().map(|c| format!("{:e}", c.b_peak_t)).collect();
    assert_eq!(bps.len(), 2);
}

#[test]
fn every_case_uses_the_registered_bridge_inputs() {
    let text = std::fs::read_to_string(repo().join(env::CASES_REL)).unwrap();
    let doc = pyjson::loads(&text).unwrap();
    let cases = doc.as_dict().unwrap().get("cases").unwrap().as_list().unwrap();
    for c in cases {
        let d = c.as_dict().unwrap();
        let bp = d.get("B_profile").unwrap().as_dict().unwrap();
        assert_eq!(bp.get("align").unwrap().as_str(), Some("exit"));
        assert_eq!(bp.get("scale_to").unwrap().as_str(), Some("max"));
        let zref = bp.get("z_ref_in_file_mm").unwrap().to_f64().unwrap();
        let file = bp.get("file").unwrap().as_str().unwrap();
        assert!(
            (file.ends_with("1p6kW.csv") && zref == 28.23) || (file.ends_with("3p0kW.csv") && zref == 30.4),
            "peak-at-exit registration {file} {zref}"
        );
        let tr = d.get("transport").unwrap().as_dict().unwrap();
        assert_eq!(tr.get("model").unwrap().as_str(), Some("ScaledGaussianBohm"));
        assert!(tr.get("anom_scale").unwrap().to_f64().unwrap() <= 1.0 / 16.0, "no super-Bohm set");
        assert!(!d.contains_key("background_pressure_Torr"), "vacuum only");
        assert!(!d.contains_key("measured"), "no target in a parametric case");
    }
}

#[test]
fn run_case_fields_are_the_fields_bridge_lib_reads() {
    let lib = std::fs::read_to_string(repo().join("hallthruster_bridge/bridge_lib.jl")).unwrap();
    for f in RUN_CASE_FIELDS {
        assert!(lib.contains(&format!("c.{f}")), "bridge_lib.jl does not read c.{f}");
    }
    for f in B_PROFILE_FIELDS {
        assert!(lib.contains(&format!("bp.{f}")), "bridge_lib.jl does not read bp.{f}");
    }
    for f in TRANSPORT_FIELDS {
        assert!(lib.contains(&format!("tr.{f}")), "bridge_lib.jl does not read tr.{f}");
    }
}

#[test]
fn driver_checks_the_pin_lock_and_manifest() {
    let d = std::fs::read_to_string(repo().join(env::DRIVER_REL)).unwrap();
    for needle in
        ["check_pin()", "launch_manifest_v1.json", "prereg_lock_v1.json", "pinned_inputs", "run_case(c, \"vacuum\")"]
    {
        assert!(d.contains(needle), "driver lacks {needle}");
    }
}

#[test]
fn shard_job_is_pinned_and_not_spawned() {
    let r = repo();
    let job = shard_job(&r, 3, "XE", "/out", &|k| (k == "PATH").then(|| "/usr/bin".to_string())).unwrap();
    assert_eq!(job.program, "julia");
    assert_eq!(job.args, vec!["--project=hallthruster_bridge", env::DRIVER_REL, "/out/s03.jsonl", "3", "64", "XE"]);
    for k in ["JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"] {
        assert_eq!(job.env.get(k).map(String::as_str), Some("1"), "{k}");
    }
    let rels: BTreeSet<&str> = job.inputs.iter().map(|(p, _)| p.as_str()).collect();
    for p in [env::DRIVER_REL, env::CASES_REL, env::LOCK_REL, env::PREREG_REL, "hallthruster_bridge/bridge_lib.jl"] {
        assert!(rels.contains(p), "{p} not hash-checked at launch");
    }
    for (p, sha) in &job.inputs {
        abep_provenance::read_verified(&r.join(p), sha).unwrap();
    }
    assert!(shard_job(&r, N_SHARDS, "XE", "/out", &|_| None).is_err());
    assert!(shard_job(&r, 0, "AIR", "/out", &|_| None).is_err());
}

fn synthetic_record(c: &env::CaseInfo, commit: &str, cases_sha: &str, i: usize) -> String {
    let mut d = Dict::new();
    let put = |d: &mut Dict, k: &str, v: Value| d.insert(k, v);
    put(&mut d, "key", Value::str(c.key.as_str()));
    put(&mut d, "family", Value::str(c.family.as_str()));
    put(&mut d, "case_sha256", Value::str(c.case_sha256.as_str()));
    put(&mut d, "cases_file_sha256", Value::str(cases_sha));
    put(&mut d, "prereg_lock_sha256", Value::str(LOCK_SHA256));
    put(&mut d, "hallthruster_commit", Value::str(commit));
    put(&mut d, "evidence_class", Value::str("SYNTHETIC_TEST_DATA_NOT_EVIDENCE"));
    put(&mut d, "retcode", Value::str(if i.is_multiple_of(11) { "failure" } else { "success" }));
    put(&mut d, "converged", Value::Bool(true));
    put(&mut d, "finite", Value::Bool(true));
    put(&mut d, "sustained", Value::Bool(!i.is_multiple_of(7)));
    put(&mut d, "thrust_N", Value::Float(1e-3 * (i % 40) as f64));
    put(&mut d, "discharge_current_A", Value::Float(1.0));
    put(&mut d, "discharge_power_W", Value::Float(c.vd_v));
    if c.family == Family::N2Proxy {
        put(&mut d, "chemistry_unresolved_rate_files", Value::List(vec![]));
        let mut r = Dict::new();
        r.insert("file", Value::str("x.dat"));
        r.insert("extrapolated_fraction", Value::Float(if i.is_multiple_of(5) { 0.01 } else { 0.0 }));
        put(&mut d, "chemistry_per_reaction", Value::List(vec![Value::Dict(r)]));
    }
    pyjson::dumps(&Value::Dict(d), &pyjson::DumpOptions::default()).unwrap()
}

fn write_shards(dir: &Path, lines: &[String], n: usize) -> Vec<PathBuf> {
    std::fs::create_dir_all(dir).unwrap();
    (0..n)
        .map(|s| {
            let p = dir.join(format!("s{s:02}.jsonl"));
            let body: String = lines.iter().skip(s).step_by(n).map(|l| format!("{l}\n")).collect();
            std::fs::write(&p, body).unwrap();
            p
        })
        .collect()
}

#[test]
fn freeze_then_ingest_round_trip_with_synthetic_records() {
    let r = repo();
    let cs = env::load_case_set(&r).unwrap();
    let commit = abep_hall::hall_map::pinned_commit(&r.to_string_lossy(), None).unwrap();
    let lines: Vec<String> =
        cs.cases.iter().enumerate().map(|(i, c)| synthetic_record(c, &commit, &cs.sha256, i)).collect();
    let base = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("np_hpe_roundtrip");
    let _ = std::fs::remove_dir_all(&base);
    let shards = write_shards(&base.join("shards"), &lines, 4);
    let (manifest, sha) = freeze(&r, "synthetic", &shards, &base.join("frozen")).unwrap();
    let e = env::ingest(&r, &manifest, &sha).unwrap();
    assert_eq!(e.points.len(), 4536);
    let n = |f: Family, s: RunStatus| e.points.iter().filter(|p| p.case.family == f && p.status == s).count();
    assert!(n(Family::Xe, RunStatus::NumericalFailure) > 0 && n(Family::N2Proxy, RunStatus::OutOfDomain) > 0);
    assert_eq!(n(Family::Xe, RunStatus::OutOfDomain), 0, "Xe chemistry never makes a run OUT_OF_DOMAIN");
    assert!(e.points.iter().filter(|p| p.status != RunStatus::Pass).all(|p| p.thrust_n.is_none()));
    // Deterministic freeze.
    let (_, sha2) = freeze(&r, "synthetic", &shards, &base.join("frozen2")).unwrap();
    assert_eq!(sha, sha2);
    // A wrong manifest pin, a tampered record, a missing record and a duplicate are refused.
    assert!(env::ingest(&r, &manifest, &"0".repeat(64)).is_err());
    let mut bad = lines.clone();
    bad[5] = bad[5].replace(&cs.cases[5].case_sha256, &"f".repeat(64));
    let (m2, s2) = freeze(&r, "tampered", &write_shards(&base.join("t"), &bad, 2), &base.join("tf")).unwrap();
    assert!(env::ingest(&r, &m2, &s2).is_err());
    let short = &lines[..lines.len() - 1];
    let (m3, s3) = freeze(&r, "short", &write_shards(&base.join("m"), short, 2), &base.join("mf")).unwrap();
    assert!(env::ingest(&r, &m3, &s3).is_err());
    let mut dup = lines.clone();
    dup.push(lines[0].clone());
    assert!(freeze(&r, "dup", &write_shards(&base.join("d"), &dup, 3), &base.join("df")).is_err());
    let mut other = lines.clone();
    other[9] = other[9].replace(&commit, &"a".repeat(40));
    let (m4, s4) = freeze(&r, "pin", &write_shards(&base.join("p"), &other, 2), &base.join("pf")).unwrap();
    assert!(env::ingest(&r, &m4, &s4).is_err(), "another HallThruster.jl commit is refused");
    let _ = std::fs::remove_dir_all(&base);
}

#[test]
fn a_family_filtered_envelope_ingests_complete_families_only() {
    let r = repo();
    let cs = env::load_case_set(&r).unwrap();
    let commit = abep_hall::hall_map::pinned_commit(&r.to_string_lossy(), None).unwrap();
    let lines: Vec<String> = cs
        .cases
        .iter()
        .enumerate()
        .filter(|(_, c)| c.family == Family::Xe)
        .map(|(i, c)| synthetic_record(c, &commit, &cs.sha256, i))
        .collect();
    let base = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("np_hpe_xe_only");
    let _ = std::fs::remove_dir_all(&base);
    let (m, s) = freeze(&r, "xe", &write_shards(&base.join("s"), &lines, 3), &base.join("f")).unwrap();
    let e = env::ingest(&r, &m, &s).unwrap();
    assert_eq!(e.family_points(Family::Xe).count(), 2268);
    assert_eq!(e.family_points(Family::N2Proxy).count(), 0, "a family that was not run is absent");
    // A partial family is refused.
    let (m2, s2) = freeze(&r, "xe_short", &write_shards(&base.join("p"), &lines[1..], 3), &base.join("pf")).unwrap();
    assert!(env::ingest(&r, &m2, &s2).is_err());
    let _ = std::fs::remove_dir_all(&base);
}

#[test]
fn workflow_is_dispatch_only_and_freezes_with_the_rust_tool() {
    let w = std::fs::read_to_string(repo().join(".github/workflows/h1-parametric-envelope.yml")).unwrap();
    assert!(w.contains("on:\n  workflow_dispatch:"), "workflow_dispatch trigger");
    for t in ["\n  push:", "\n  pull_request:", "\n  schedule:", "\n  workflow_run:"] {
        assert!(!w.contains(t), "the envelope workflow must never run on{t}");
    }
    for needle in ["abep-h1-envelope-cases check", "run-shard", "freeze --name", "Pkg.instantiate()", "check_pin()"] {
        assert!(w.contains(needle), "workflow lacks {needle}");
    }
}
