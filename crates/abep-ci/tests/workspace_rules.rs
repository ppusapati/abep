//! Workspace rules on the real tree: the Rust-era test rule (A9.29 sec. 9), ground-test isolation (sec. 1) and the
//! governed empty Hall credible transport set (CLAUDE.md rule 9: asserted explicitly, never an xfail).

use abep_ci::groundtest::{self, FLIGHT_RUNTIME_CRATES, GROUNDTEST_CRATE};
use abep_ci::test_register;
use abep_provenance::workspace_repo_root;
use abep_types::EvalStatus;
use serde_json::Value;

fn json(rel: &str) -> Value {
    let root = workspace_repo_root().unwrap();
    serde_json::from_slice(&std::fs::read(root.join(rel)).unwrap()).unwrap()
}

#[test]
fn no_ignored_test_outside_the_platform_test_register() {
    let r = test_register::check(&workspace_repo_root().unwrap()).expect("register loads");
    assert!(r.violations.is_empty(), "{:#?}", r.violations);
    assert!(r.files_scanned > 0);
    assert_eq!(r.registered, r.ignore_attrs, "every ignored test is exactly one registered platform test");
}

#[test]
fn no_workspace_crate_depends_on_abep_groundtest() {
    let root = workspace_repo_root().unwrap();
    let meta = groundtest::cargo_metadata(env!("CARGO"), &root).expect("cargo metadata --locked --offline");
    let r = groundtest::check_metadata(&meta).expect("resolved graph");
    println!("{}", r.summary());
    assert!(r.violations.is_empty(), "{:#?}", r.violations);
    for m in ["abep-types", "abep-provenance", "abep-ci"] {
        assert!(r.members_checked.iter().any(|c| c == m), "{m} walked");
    }
    if !r.groundtest_present {
        assert!(r.summary().contains("VACUOUS"), "absence is stated, not hidden");
    }
}

#[test]
fn flight_runtime_list_matches_the_programme() {
    let p = json("docs/rust_migration/programme_v3_1.json");
    let rule = p.pointer("/cargo_workspace_proposal/groundtest_isolation_check").and_then(Value::as_str).unwrap();
    for c in FLIGHT_RUNTIME_CRATES {
        assert!(rule.contains(c), "{c} not in groundtest_isolation_check");
    }
    assert!(rule.contains(GROUNDTEST_CRATE));
}

/// The empty Hall credible transport set is an expected governed state (A9.29 sec. 9): no admitted member, the nine
/// screening candidates stay non-admitted, so any output needing Hall performance is NOT_EVALUATED.
#[test]
fn hall_credible_transport_set_is_empty() {
    let e = json("hallthruster_bridge/ensemble/transport_ensemble_v0.json");
    assert_eq!(e["schema"], "transport_ensemble_v0");
    assert_eq!(e["weighting"], "unweighted");
    let members = e["members"].as_array().expect("members is a list");
    assert!(members.is_empty(), "credible set is EMPTY until an evidence-based promotion is recorded");
    assert!(e["admission_rule_status"].as_str().unwrap().starts_with("Credible set is EMPTY"));
    let screening = e["screening_candidates"].as_array().expect("screening_candidates is a list");
    let ids: Vec<&str> = screening.iter().map(|c| c["ensemble_member_id"].as_str().unwrap()).collect();
    let want: Vec<String> = (1..=9).map(|i| format!("sgb-screen-{i:02}")).collect();
    assert_eq!(ids, want);
    for c in screening {
        assert_eq!(c["transport_family"], "ScaledGaussianBohm");
        assert!(c["transport_parameters"]["anom_scale"].as_f64().unwrap() <= 1.0 / 16.0);
    }
    let hall_performance = if members.is_empty() { EvalStatus::NotEvaluated } else { EvalStatus::Evaluated };
    assert_eq!(hall_performance, EvalStatus::NotEvaluated);
}
