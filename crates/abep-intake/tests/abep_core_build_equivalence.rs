//! Regression guard of ADDENDUM-ABEP-CORE-BUILD-EQUIVALENCE-V1 (verdict EQUIVALENT, result_v1.json): this build of
//! abep_core, under whichever profile the test runs in, must reproduce the recorded extension's (B0) per-case sha256 on
//! all 493 registered cases, and the abep_core sources must still be those parity_report_v2 admitted.

use abep_intake::build_equivalence::{load_cases, read_json, run_all, total_digest};
use abep_provenance::{read_verified, sha256_file, workspace_repo_root};

const RESULT_PATH: &str = "docs/rust_migration/contracts/C-ABEP_CORE_BUILD_EQUIVALENCE/result_v1.json";
const RESULT_SHA256: &str = "0ad402fc19a30f135e0f8e27170bed206112aef2ead458c0fc0cbac15ba5ccf4";
const PARITY_REPORT_V2: &str = "docs/performance/abep_core/parity_report_v2.json";
const PARITY_REPORT_V2_SHA256: &str = "ed3867776bb8c21a108e6de94cf86ade7adce0ea5695bc6bb4da023b9a52ae45";

#[test]
fn abep_core_sources_are_the_admitted_kernel1_sources() {
    let root = workspace_repo_root().unwrap();
    let bytes = read_verified(&root.join(PARITY_REPORT_V2), PARITY_REPORT_V2_SHA256).unwrap();
    let report: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
    let src = report["build_provenance"]["source_sha256"].as_object().unwrap();
    let core: Vec<_> = src.iter().filter(|(p, _)| p.starts_with("abep_core/")).collect();
    assert_eq!(core.len(), 6);
    for (path, sha) in core {
        assert_eq!(
            sha256_file(&root.join(path)).unwrap(),
            sha.as_str().unwrap(),
            "{path} differs from parity_report_v2 build_provenance: abep_core must stay byte-identical (never run \
             `cargo fmt --all`)"
        );
    }
}

#[test]
fn workspace_build_reproduces_recorded_extension_bitwise() {
    let root = workspace_repo_root().unwrap();
    read_verified(&root.join(RESULT_PATH), RESULT_SHA256).unwrap();
    let result = read_json(&root.join(RESULT_PATH)).unwrap();
    assert_eq!(result["verdict"], "EQUIVALENT");
    let b0 = result["per_case_sha256_B0"].as_object().unwrap();
    let file = load_cases(&root).unwrap();
    let digests = run_all(&file).unwrap();
    assert_eq!(digests.len(), 493);
    assert_eq!(b0.len(), digests.len());
    let differing: Vec<&str> = digests
        .iter()
        .filter(|d| b0.get(&d.id).and_then(|v| v.as_str()) != Some(d.sha256.as_str()))
        .map(|d| d.id.as_str())
        .collect();
    assert!(differing.is_empty(), "cases differing from the recorded extension: {differing:?}");
    assert_eq!(total_digest(&digests), result["B0_reference_recorded_extension"]["total_sha256"].as_str().unwrap());
}
