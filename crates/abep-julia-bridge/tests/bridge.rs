//! Normal-CI tests of the bridge orchestration: pin constants and the repository pin, the committed launch manifests
//! reproduced byte for byte, launch specifications (argv, allow-list environment), the driver shard partition and
//! the sidecar field set. Nothing here spawns Julia (the real runs are registered platform tests, tests/platform.rs).

use abep_hall::py::{self, PyValue};
use abep_julia_bridge::jobs::{self, ThreadSettings, PASS_THROUGH, SMOKE_VAR, THREAD_VARS};
use abep_julia_bridge::sidecar::SIDECAR_FIELDS;
use abep_julia_bridge::{manifests, pin};
use abep_provenance::workspace_repo_root;
use std::collections::BTreeMap;

fn repo() -> String {
    workspace_repo_root().unwrap().to_string_lossy().into_owned()
}

fn boundary() -> PyValue {
    let p = py::load_json_file(&py::join(&repo(), "docs/rust_migration/simulation_completion_programme_v1_1.json"))
        .unwrap();
    py::getitem(&p, "hall_physics_boundary").unwrap().clone()
}

#[test]
fn pin_constants_are_the_hall_physics_boundary_pin_and_the_repository_verifies() {
    let b = boundary();
    let p = py::getitem(&b, "pin").unwrap();
    assert_eq!(py::py_str(py::getitem(p, "commit").unwrap()), pin::PIN_COMMIT);
    assert_eq!(py::py_str(py::getitem(p, "version").unwrap()), pin::PIN_VERSION);
    assert!(py::py_str(py::getitem(p, "julia").unwrap()).starts_with(pin::JULIA_VERSION));
    let got = pin::verify_pin(&repo()).expect("repository pin verifies");
    assert!(got.is_pinned());
    let report = pin::pin_report(&repo()).unwrap();
    assert!(matches!(py::getitem(&report, "verify_pin_ok").unwrap(), PyValue::Bool(true)));
}

#[test]
fn sidecar_is_exactly_the_hall_physics_boundary_list() {
    let labels: Vec<String> = py::iterate(py::getitem(&boundary(), "provenance_sidecar_per_run").unwrap())
        .unwrap()
        .iter()
        .map(py::py_str)
        .collect();
    let ours: Vec<String> = SIDECAR_FIELDS.iter().map(|(_, l)| l.to_string()).collect();
    assert_eq!(ours, labels);
}

#[test]
fn launch_manifests_reproduce_the_committed_files() {
    let r = repo();
    let built = manifests::build(&r).unwrap();
    let dir = py::join(&r, manifests::MANIFEST_DIR_REL);
    let mut committed: Vec<String> = std::fs::read_dir(&dir)
        .unwrap()
        .map(|e| e.unwrap().file_name().to_string_lossy().into_owned())
        .filter(|n| n.ends_with(".json"))
        .collect();
    committed.sort();
    let mut names: Vec<String> = built.iter().map(|m| format!("{}.json", manifests::name_of(m).unwrap())).collect();
    names.sort();
    assert_eq!(names, committed, "no orphan, nothing missing");
    for m in &built {
        let name = manifests::name_of(m).unwrap();
        let bytes = std::fs::read(py::join(&dir, &format!("{name}.json"))).unwrap();
        assert!(bytes == manifests::to_json_bytes(m), "{name} differs from the committed manifest");
    }
}

fn env_c() -> BTreeMap<&'static str, &'static str> {
    [
        ("PATH", "/usr/bin"),
        ("HOME", "/home/r"),
        ("SECRET_TOKEN", "x"),
        ("JULIA_NUM_THREADS", "4"),
        ("OPENBLAS_NUM_THREADS", "1"),
        ("P5N2_SMOKE", "1"),
        ("ABEP_ALLOW_HISTORICAL", "1"),
        ("JULIA_LOAD_PATH", "@:/elsewhere"),
        ("LD_PRELOAD", "/x.so"),
    ]
    .into_iter()
    .collect()
}

#[test]
fn launch_spec_follows_the_manifest_command_and_the_allow_list() {
    let r = repo();
    let parent = env_c();
    let lookup = |k: &str| parent.get(k).map(|v| v.to_string());
    let threads = ThreadSettings::from_parent(&lookup);
    let m = manifests::load_committed(&r, "staged_n2_n_rot_off").unwrap();
    for shard in 0..4 {
        let job = jobs::campaign_shard_job(&r, &m, shard, "/out", &threads, &lookup).unwrap();
        let cmd =
            py::py_str(&py::iterate(py::getitem(&m, "commands").unwrap()).unwrap()[shard]).replace("<out>", "/out");
        let want: Vec<String> = cmd.split_whitespace().map(str::to_string).collect();
        assert_eq!(job.argv(), want);
        assert_eq!(job.cwd, r);
        let c = job.command();
        assert!(c.get_program() == "julia");
        let keys: Vec<String> = job.env.keys().cloned().collect();
        assert_eq!(keys, ["HOME", "JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "PATH"]);
        for k in job.env.keys() {
            assert!(PASS_THROUGH.contains(&k.as_str()) || THREAD_VARS.contains(&k.as_str()), "{k}");
        }
        assert!(!job.env.contains_key(SMOKE_VAR), "a campaign job never inherits P5N2_SMOKE");
    }
    let smoke = jobs::smoke_job(&r, "/out/smoke.jsonl", &threads, &lookup).unwrap();
    assert_eq!(
        smoke.argv(),
        [
            "julia",
            "--project=hallthruster_bridge",
            "hallthruster_bridge/campaign/p5_n2_campaign.jl",
            "/out/smoke.jsonl",
            "vacuum",
            "0",
            "270",
            "n2_n.toml"
        ]
    );
    assert_eq!(smoke.env.get(SMOKE_VAR).map(String::as_str), Some("1"));
}

#[test]
fn shard_partition_covers_every_expected_key_once() {
    let r = repo();
    for m in manifests::build(&r).unwrap() {
        let expected: Vec<String> =
            py::iterate(py::getitem(&m, "expected_keys").unwrap()).unwrap().iter().map(py::py_str).collect();
        let shards: Vec<Vec<String>> = (0..4).map(|i| jobs::shard_keys(&r, &m, i, 4).unwrap()).collect();
        let mut all: Vec<String> = shards.iter().flatten().cloned().collect();
        all.sort();
        assert_eq!(all, expected, "{}", manifests::name_of(&m).unwrap());
        let sizes: Vec<usize> = shards.iter().map(Vec::len).collect();
        assert!(sizes.iter().max().unwrap() - sizes.iter().min().unwrap() <= 1);
    }
}

#[test]
fn a_moved_pin_is_model_error() {
    let d = std::env::temp_dir().join(format!("abep_bridge_pin_{}", std::process::id()));
    let b = d.join("hallthruster_bridge");
    std::fs::create_dir_all(&b).unwrap();
    for f in ["PINNED.toml", "Manifest.toml", "Project.toml"] {
        let text = std::fs::read_to_string(py::join(&repo(), &format!("hallthruster_bridge/{f}"))).unwrap();
        std::fs::write(b.join(f), text.replace(pin::PIN_COMMIT, &"1".repeat(40))).unwrap();
    }
    let root = d.to_string_lossy().into_owned();
    assert!(pin::manifest_consistent(&root), "consistent files on another commit");
    let e = pin::verify_pin(&root).unwrap_err();
    assert_eq!(e.status(), abep_types::EvalStatus::ModelError);
    let _ = std::fs::remove_dir_all(&d);
}
