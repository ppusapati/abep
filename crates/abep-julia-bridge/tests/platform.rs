//! Registered platform tests (docs/rust_migration/test_register/platform_tests_v1.json, PT-01 / PT-02): they need the
//! pinned Julia 1.11.7 with HallThruster.jl installed from hallthruster_bridge/Manifest.toml, which normal CI does not
//! have. Run with `cargo test -p abep-julia-bridge --test platform -- --ignored` in .github/workflows/julia-smoke.yml
//! (manual) or on a workstation with the pinned toolchain. They write only outside the checkout.

use abep_hall::py::{self, PyValue};
use abep_julia_bridge::jobs::{self, ThreadSettings};
use abep_julia_bridge::sidecar::{JuliaRunSidecar, SIDECAR_FIELDS};
use abep_julia_bridge::{launch, pin, CONTRACT_ID};
use abep_provenance::workspace_repo_root;

const TARGET_FIELDS: [&str; 9] = [
    "measured",
    "Id_target_A",
    "Id_target_kind",
    "T_target_N",
    "T_target_kind",
    "Id_err_rel",
    "T_err_rel",
    "T_err_sigma",
    "Id_raw_A",
];

fn out_dir(tag: &str) -> std::path::PathBuf {
    let d = std::env::temp_dir().join(format!("abep_julia_{tag}_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

fn records(path: &str) -> Vec<PyValue> {
    std::fs::read_to_string(path)
        .unwrap()
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| py::load_json_bytes(l.as_bytes()).unwrap())
        .collect()
}

#[test]
#[ignore = "REGISTERED_PLATFORM_TEST:PT-01"]
fn smoke_job_runs_with_the_pinned_toolchain_and_writes_its_sidecar() {
    let repo = workspace_repo_root().unwrap().to_string_lossy().into_owned();
    pin::verify_pin(&repo).expect("pinned HallThruster.jl");
    let env = |k: &str| std::env::var(k).ok();
    let d = out_dir("pt01");
    let out = d.join("smoke.jsonl").to_string_lossy().into_owned();
    let job = jobs::smoke_job(&repo, &out, &ThreadSettings::from_parent(&env), &env).unwrap();
    let sidecar = launch::launch(&repo, &job, CONTRACT_ID).expect("smoke run");
    let recs = records(&out);
    assert_eq!(recs.len(), 1, "exactly one construction job");
    let r = &recs[0];
    assert!(matches!(py::getitem(r, "smoke").unwrap(), PyValue::Bool(true)));
    assert_eq!(py::py_str(py::getitem(r, "retcode").unwrap()), "success");
    for f in TARGET_FIELDS {
        assert!(py::get(r, f).unwrap().is_none(), "target field {f} in a smoke record");
    }
    assert_eq!(sidecar.hallthruster_commit, pin::PIN_COMMIT);
    assert_eq!(sidecar.julia_version, pin::JULIA_VERSION);
    let written = std::fs::read_to_string(JuliaRunSidecar::path_for(&out)).unwrap();
    for (k, _) in SIDECAR_FIELDS {
        assert!(written.contains(&format!("\"{k}\"")), "{k}");
    }
    let _ = std::fs::remove_dir_all(&d);
}

#[test]
#[ignore = "REGISTERED_PLATFORM_TEST:PT-02"]
fn rust_and_reference_launch_lines_give_byte_identical_smoke_records() {
    let repo = workspace_repo_root().unwrap().to_string_lossy().into_owned();
    let env = |k: &str| std::env::var(k).ok();
    let threads = ThreadSettings::from_parent(&env);
    let d = out_dir("pt02");
    let a = d.join("rust.jsonl").to_string_lossy().into_owned();
    let b = d.join("reference.jsonl").to_string_lossy().into_owned();
    let job = jobs::smoke_job(&repo, &a, &threads, &env).unwrap();
    launch::launch(&repo, &job, CONTRACT_ID).expect("Rust-launched smoke");
    // The reference launch line: the workflow's shell command from the checkout root with the same environment values.
    let reference = jobs::smoke_job(&repo, &b, &threads, &env).unwrap();
    let line = reference.argv().iter().map(|x| format!("'{x}'")).collect::<Vec<_>>().join(" ");
    let status = std::process::Command::new("bash")
        .arg("-c")
        .arg(line)
        .current_dir(&repo)
        .env_clear()
        .envs(&reference.env)
        .status()
        .expect("bash");
    assert!(status.success());
    assert_eq!(std::fs::read(&a).unwrap(), std::fs::read(&b).unwrap(), "run records byte-identical");
    let _ = std::fs::remove_dir_all(&d);
}
