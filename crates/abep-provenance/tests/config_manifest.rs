//! The repository's configuration manifest verifies on the real tree, and a tampered copy is refused.

use abep_provenance::{read_verified, workspace_repo_root, ConfigManifest};
use abep_types::{AbepError, EvalStatus};

#[test]
fn config_manifest_verifies_on_the_repository_tree() {
    let root = workspace_repo_root().expect("repository root");
    let m = ConfigManifest::load(&root).expect("manifest loads");
    let n = m.verify_all(&root).expect("every pinned config file matches its sha256");
    assert_eq!(n, m.files.len());
    assert!(m.files.contains_key("mission/mission_scenario_v2.json"));
}

#[test]
fn unpinned_and_tampered_files_are_refused() {
    let root = workspace_repo_root().unwrap();
    let m = ConfigManifest::load(&root).unwrap();
    let e = m.read_verified(&root, "not/pinned.json").unwrap_err();
    assert_eq!(e.status(), EvalStatus::ModelError);

    let path = root.join("config").join("MANIFEST.json");
    let wrong = "0".repeat(64);
    match read_verified(&path, &wrong) {
        Err(AbepError::HashMismatch { expected, .. }) => assert_eq!(expected, wrong),
        other => panic!("expected HashMismatch, got {other:?}"),
    }
}
