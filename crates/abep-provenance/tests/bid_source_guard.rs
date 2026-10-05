//! bid_source_guard on the repository and on every preregistered acceptance case (acceptance_v1.json).
//! Needs a full-history clone: in a shallow clone the guard reports history NOT_EVALUATED and these tests fail,
//! with that reason, instead of passing.

use abep_provenance::bid_guard::acceptance::{run_all, ACCEPTANCE_PATH};
use abep_provenance::bid_guard::{evaluate, GuardInputs, GuardStatus};
use abep_provenance::workspace_repo_root;

#[test]
fn current_repository_tree_passes_the_guard() {
    let root = workspace_repo_root().expect("repository root");
    let r = evaluate(&GuardInputs::repository(&root));
    assert_eq!(r.overall, GuardStatus::Pass, "{}", r.render());
    assert!(r.files.findings.is_empty() && r.history.findings.is_empty());
}

#[test]
fn every_preregistered_acceptance_case_holds() {
    let root = workspace_repo_root().expect("repository root");
    let outcomes = run_all(&root).expect("cases load (sha256-pinned) and run");
    assert_eq!(outcomes.len(), 25, "{ACCEPTANCE_PATH} registers 25 cases");
    let mut failed = Vec::new();
    for o in &outcomes {
        println!(
            "{:8} overall {:13} files {:13} history {:13} {:?} {:?}",
            o.case.id,
            o.report.overall.as_str(),
            o.report.files.status.as_str(),
            o.report.history.status.as_str(),
            o.report.files.codes(),
            o.report.history.codes()
        );
        if !o.problems.is_empty() {
            failed.push(format!("{}: {:?}\n{}", o.case.id, o.problems, o.report.render()));
        }
    }
    assert!(failed.is_empty(), "{}", failed.join("\n"));
    // every tamper case fails or is not evaluated; only the base and the bytecode control pass
    for o in &outcomes {
        if o.report.overall == GuardStatus::Pass {
            assert!(["BASE-00", "BASE-01", "CTRL-01"].contains(&o.case.id.as_str()), "{} passed", o.case.id);
        }
    }
}
