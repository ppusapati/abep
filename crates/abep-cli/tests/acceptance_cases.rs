//! Development regression of the NI-ABEP-CLI acceptance cases (acceptance_v2 `decision_rules.development`): every
//! registered command, refusal, determinism and static case, run against the `abep` binary of this build. This is not
//! the acceptance report.

use abep_cli::acceptance::{run, Config, Mode};
use abep_provenance::workspace_repo_root;
use std::path::PathBuf;

#[test]
fn every_registered_case_meets_its_expectation() {
    // Outside the repository: the CLI refuses an output location inside it (REF-15).
    let work = std::env::temp_dir().join(format!("abep_cli_acceptance_dev_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&work);
    let cfg = Config {
        repo: workspace_repo_root().unwrap(),
        abep: PathBuf::from(env!("CARGO_BIN_EXE_abep")),
        work: work.clone(),
        mode: Mode::Development,
    };
    let (body, problems) = run(&cfg).unwrap();
    let _ = std::fs::remove_dir_all(&work);
    assert!(problems.is_empty(), "{problems:#?}");
    assert_eq!(body["verdict"], "ACCEPTED");
    assert_eq!(body["counts"]["cases"], 26);
}

#[test]
fn threaded_design_state_run_equals_the_crate_run() {
    let root = workspace_repo_root().unwrap();
    let crate_run = serde_json::to_string(&abep_atmos::execution::run_design_state_set(&root).unwrap()).unwrap();
    for threads in [1, 3, 7] {
        let (run, used) = abep_cli::commands::env_design_state_run(&root, threads).unwrap();
        assert_eq!(serde_json::to_string(&run).unwrap(), crate_run, "threads {threads}");
        assert_eq!(used, threads);
    }
}
