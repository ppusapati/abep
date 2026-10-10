//! The run record captured on the repository carries the pinned hashes, and capture fails closed without git.

use abep_provenance::bid_guard::acceptance::TempDir;
use abep_provenance::run_record::{RunRecord, RUSTC_VERSION, THREAD_ENV_VARS};
use abep_provenance::{sha256_file, workspace_repo_root};
use abep_types::EvalStatus;

#[test]
fn captured_record_carries_the_pinned_hashes() {
    let root = workspace_repo_root().unwrap();
    let env = |k: &str| (k == "OMP_NUM_THREADS").then(|| "1".to_string());
    let r = RunRecord::capture_with_env(&root, Some("PARITY-EXAMPLE-V1"), &env).expect("capture");
    assert_eq!(r.implementation, "rust");
    assert_eq!(r.git_commit.len(), 40);
    assert!(RUSTC_VERSION.starts_with("rustc 1.94.1 "), "{RUSTC_VERSION}");
    assert_eq!(r.rustc, RUSTC_VERSION);
    assert_eq!(r.cargo_lock_sha256, sha256_file(&root.join("Cargo.lock")).unwrap());
    assert_eq!(r.config_manifest.sha256, sha256_file(&root.join("config/MANIFEST.json")).unwrap());
    // values pinned at the technical source (programme_v3_1 bid_boundary.other_pinned_at_technical_source)
    assert_eq!(r.model_set.sha256, "a7423d11b208a847ed4026d169ad04b6b10d0d72a5f90af1ce46bdcd8030a0c1");
    assert_eq!(r.architecture.sha256, "7ab04af49340bf24be316fe7cd83eca20f2aeb692b00a43c02fa44043a5825f3");
    assert_eq!(r.design_state_set.sha256, "60073e214cf5edb92d7eacf70be1491ad29ff72f19db0ef3b96a4b30da6f4049");
    assert_eq!(r.design_state_set.n_states, 196);
    assert_eq!(r.hallthruster.commit, "bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5");
    assert_eq!(r.hallthruster.version, "0.23.1");
    assert_eq!(r.threads.env.len(), THREAD_ENV_VARS.len());
    assert_eq!(r.threads.env["OMP_NUM_THREADS"].as_deref(), Some("1"));
    assert_eq!(r.threads.env["JULIA_NUM_THREADS"], None);
    assert_eq!(r.contract_id.as_deref(), Some("PARITY-EXAMPLE-V1"));
    let again = RunRecord::capture_with_env(&root, Some("PARITY-EXAMPLE-V1"), &env).unwrap();
    assert_eq!(r.to_json(), again.to_json());
}

#[test]
fn capture_outside_a_repository_is_incomplete_evidence() {
    let dir = TempDir::new("runrecord").unwrap();
    let e = RunRecord::capture(dir.path(), None).unwrap_err();
    assert_eq!(e.status(), EvalStatus::IncompleteEvidence, "{e}");
}
