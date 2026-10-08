//! NP-HALL-PARAMETRIC-ENVELOPE addendum A6: the committed study case file reproduces, the committed study result
//! reproduces from the frozen runs, and the grid case file is refused while the result is STOP. No test spawns Julia.

use abep_julia_bridge::envelope_a6::{self as a6, Kind};
use abep_provenance::workspace_repo_root;
use abep_types::pyjson;
use std::path::PathBuf;

fn repo() -> PathBuf {
    workspace_repo_root().unwrap()
}

#[test]
fn committed_study_case_file_reproduces() {
    assert_eq!(a6::check(&repo(), Kind::Study).unwrap(), 154);
}

#[test]
fn committed_study_result_reproduces_and_stops_the_grid() {
    let r = repo();
    let dir = r.join(a6::NP);
    let m = dir.join("runs/a6_study_v1/h1_parametric_envelope_a6_study_v1_raw_manifest.json");
    let sha = "07f52f7916bc1c49a7f20a87069f8fc59a0446d2cd9cfc1ff487f061b8af1a6d";
    let (v, md) = a6::score_study(&r, &m, sha, "0ef6bb5").unwrap();
    let mut t = pyjson::dumps(&v, &pyjson::DumpOptions::config_writer()).unwrap();
    t.push('\n');
    assert_eq!(t, std::fs::read_to_string(dir.join("a6_convergence_study_result_v1.json")).unwrap());
    assert_eq!(md, std::fs::read_to_string(dir.join("A6_CONVERGENCE_STUDY_RESULT.md")).unwrap());
    assert_eq!(a6::production_level(&r).unwrap(), None, "STOP_NO_LEVEL_CONVERGED");
    assert!(a6::generate(&r, Kind::Grid).is_err(), "no A6 grid case file under STOP");
}
