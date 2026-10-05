//! The generic provenance verifier passes on the repository tree and fails closed, with the registered identity, on
//! tampered copies (temporary directories; the repository is only read).

use abep_provenance::verifier::{run_checks, CheckName, CheckReport, FindingKind, H2_6_SPEC_PATH, H2_6_SPEC_SHA256};
use abep_provenance::{sha256_file, workspace_repo_root};
use abep_types::EvalStatus;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

const RECORD: &str = "docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json";
const W1: &str = "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json";

fn copy_dir(src: &Path, dst: &Path) {
    fs::create_dir_all(dst).unwrap();
    for e in fs::read_dir(src).unwrap() {
        let e = e.unwrap();
        let to = dst.join(e.file_name());
        if e.file_type().unwrap().is_dir() {
            copy_dir(&e.path(), &to);
        } else {
            fs::copy(e.path(), to).unwrap();
        }
    }
}

fn copy_file(root: &Path, dst: &Path, rel: &str) {
    let to = dst.join(rel);
    fs::create_dir_all(to.parent().unwrap()).unwrap();
    fs::copy(root.join(rel), to).unwrap();
}

/// A temporary tree holding every file the four checks read.
struct Tree(PathBuf);

impl Drop for Tree {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

static N: AtomicUsize = AtomicUsize::new(0);

fn tree() -> Tree {
    let root = workspace_repo_root().unwrap();
    let dst = std::env::temp_dir().join(format!(
        "abep-provenance-verifier-{}-{}",
        std::process::id(),
        N.fetch_add(1, Ordering::SeqCst)
    ));
    let _ = fs::remove_dir_all(&dst);
    for d in ["prereg", "cases", "identification", "ensemble", "propellants", "audit"] {
        copy_dir(&root.join("hallthruster_bridge").join(d), &dst.join("hallthruster_bridge").join(d));
    }
    let mut files: Vec<String> = [
        "hallthruster_bridge/PINNED.toml",
        "hallthruster_bridge/Manifest.toml",
        "hallthruster_bridge/Project.toml",
        "abep_sim/constants.py",
        RECORD,
        W1,
        "docs/experiments/instrumentation/instrumentation_definition_v1.json",
        "docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json",
    ]
    .map(String::from)
    .to_vec();
    let record: serde_json::Value = serde_json::from_slice(&fs::read(root.join(RECORD)).unwrap()).unwrap();
    for list in ["authority_pins", "deliverable_pins"] {
        for p in record[list].as_array().unwrap() {
            files.push(p["path"].as_str().unwrap().to_string());
        }
    }
    for f in &files {
        copy_file(&root, &dst, f);
    }
    Tree(dst)
}

fn one(root: &Path, check: CheckName) -> CheckReport {
    run_checks(root, &[check]).remove(0)
}

fn identities(r: &CheckReport) -> Vec<(FindingKind, String, String)> {
    let mut v: Vec<_> = r.findings.iter().map(|f| (f.kind, f.file.clone(), f.key.clone())).collect();
    v.sort();
    v
}

fn id(kind: FindingKind, file: &str, key: &str) -> (FindingKind, String, String) {
    (kind, file.to_string(), key.to_string())
}

fn edit(t: &Tree, rel: &str, from: &str, to: &str) {
    let p = t.0.join(rel);
    let s = fs::read_to_string(&p).unwrap();
    assert_eq!(s.matches(from).count(), 1, "{rel}: {from:?}");
    fs::write(p, s.replacen(from, to, 1)).unwrap();
}

#[test]
fn repository_tree_verifies() {
    let root = workspace_repo_root().unwrap();
    let reports = run_checks(&root, &CheckName::ALL);
    assert_eq!(reports.len(), 4);
    for r in &reports {
        assert!(r.verified(), "{}: {:?}", r.check, r.findings);
        assert_eq!(r.status, EvalStatus::Evaluated);
    }
    assert_eq!(sha256_file(&root.join(H2_6_SPEC_PATH)).unwrap(), H2_6_SPEC_SHA256);
    assert_eq!(run_checks(&root, &CheckName::ALL), reports, "deterministic");
}

#[test]
fn copied_tree_verifies() {
    let t = tree();
    assert!(run_checks(&t.0, &CheckName::ALL).iter().all(CheckReport::verified));
}

#[test]
fn byte_flip_in_a_pinned_chemistry_config_is_a_sha_mismatch() {
    let t = tree();
    let rel = "hallthruster_bridge/propellants/n2_n_rot_off.toml";
    let mut b = fs::read(t.0.join(rel)).unwrap();
    b[10] ^= 0x04;
    fs::write(t.0.join(rel), b).unwrap();
    let r = one(&t.0, CheckName::PreregLock);
    assert_eq!(r.status, EvalStatus::ModelError);
    assert_eq!(identities(&r), [id(FindingKind::Sha256Mismatch, rel, "criteria chemistry_configs_sha256")]);
    assert!(one(&t.0, CheckName::AuditManifest).verified());
}

#[test]
fn missing_lock_aborts_with_one_raised_finding() {
    let t = tree();
    let rel = "hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json";
    fs::remove_file(t.0.join(rel)).unwrap();
    assert_eq!(identities(&one(&t.0, CheckName::PreregLock)), [id(FindingKind::Raised, rel, "FILE_MISSING")]);
}

#[test]
fn wrong_pin_commit_is_a_value_mismatch() {
    let t = tree();
    edit(&t, "hallthruster_bridge/Manifest.toml", "repo-rev = \"bfb3019f", "repo-rev = \"0fb3019f");
    assert_eq!(
        identities(&one(&t.0, CheckName::HallthrusterPin)),
        [id(FindingKind::ValueMismatch, "hallthruster_bridge/Manifest.toml", "repo-rev")]
    );
}

#[test]
fn audit_snapshot_rate_file_change_is_sha_and_set_mismatch() {
    let t = tree();
    let rel = "hallthruster_bridge/audit/configs/n2_n_0p9_pre_rotation.toml";
    edit(&t, rel, "rate_coeff_file = \"elastic_N2_song2023.dat\"", "rate_coeff_file = \"x_unlisted.dat\"");
    let r = one(&t.0, CheckName::AuditManifest);
    assert_eq!(
        identities(&r),
        [
            id(FindingKind::Sha256Mismatch, rel, "audit snapshot"),
            id(FindingKind::SetMismatch, rel, r#"["elastic_N2_song2023.dat","x_unlisted.dat"]"#),
        ]
    );
}

#[test]
fn live_source_value_and_group_failures() {
    let t = tree();
    edit(&t, "abep_sim/constants.py", "K_B = 1.380649e-23", "K_B = 1.380649e-22");
    edit(&t, "abep_sim/constants.py", "thrust_min_mN: float = 12.0", "thrust_min_mN: float = float(12.0)");
    let w1 = fs::read_to_string(t.0.join(W1)).unwrap().replacen("\"mdot_max_kgps\"", "\"mdot_max_kgps_renamed\"", 1);
    fs::write(t.0.join(W1), w1).unwrap();
    let r = one(&t.0, CheckName::H26LiveSources);
    assert_eq!(
        identities(&r),
        [
            id(FindingKind::ValueMismatch, "abep_sim/constants.py", "K_B"),
            id(FindingKind::ValueMismatch, "abep_sim/constants.py", "thrust_min_mN"),
            id(FindingKind::SourceKeyMissing, W1, "mdot_max_kgps"),
        ]
    );
    fs::remove_file(t.0.join(W1)).unwrap();
    let r = one(&t.0, CheckName::H26LiveSources);
    assert!(r.findings.iter().any(|f| f.identity() == (FindingKind::SourceMissing, W1, "W1")));
}

#[test]
fn sub_tolerance_change_passes_and_a_larger_one_fails() {
    let t = tree();
    edit(&t, "abep_sim/constants.py", "AMU = 1.66053906660e-27", "AMU = 1.6605390666016605e-27");
    assert!(one(&t.0, CheckName::H26LiveSources).verified(), "relative change 1e-12 is inside rel_tol 1e-9");
    edit(&t, "abep_sim/constants.py", "AMU = 1.6605390666016605e-27", "AMU = 1.6605390832e-27");
    let r = one(&t.0, CheckName::H26LiveSources);
    assert_eq!(identities(&r), [id(FindingKind::ValueMismatch, "abep_sim/constants.py", "AMU")]);
}

#[test]
fn changed_evidence_record_fails_closed() {
    let t = tree();
    let mut b = fs::read(t.0.join(RECORD)).unwrap();
    b.push(b'\n');
    fs::write(t.0.join(RECORD), b).unwrap();
    assert_eq!(
        identities(&one(&t.0, CheckName::H26LiveSources)),
        [id(FindingKind::Sha256Mismatch, RECORD, "consumed record")]
    );
}

#[test]
fn pinned_path_turned_directory_raises() {
    let t = tree();
    let rel = "docs/experiments/s1_readiness/s1_readiness_conditions_v1.json";
    fs::remove_file(t.0.join(rel)).unwrap();
    fs::create_dir(t.0.join(rel)).unwrap();
    assert_eq!(
        identities(&one(&t.0, CheckName::H26LiveSources)),
        [id(FindingKind::Raised, "", "OTHER:IsADirectoryError")]
    );
}
