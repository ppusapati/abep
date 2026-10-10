//! CONS-L1 system energy ledger (CLAUDE.md rule 4): SYS-01..SYS-08 give their registered statuses. The registered
//! LS-01 books thermal_control at 0 W while VS-NET deposits 3 W of thermal control, so SYS-01 closes with exactly that
//! -3 W mismatch on the THERMAL_CONTROL account (r = 0.37 %, below 2 %); every other account matches the thermal
//! model's booked flows to rounding. SYS-01b (not registered) adds the 3 W and closes to rounding.

mod power_sys;
mod support;

use abep_subsystems::power::official::MassPowerA9V5;
use abep_types::EvalStatus;

#[test]
fn system_cases_give_their_registered_statuses() {
    let root = abep_provenance::workspace_repo_root().unwrap();
    let mp = MassPowerA9V5::load(&root).unwrap();
    let cases = power_sys::system_cases(&mp);
    assert_eq!(cases.len(), 9);
    for (id, expected, s) in &cases {
        assert_eq!(s.status, *expected, "{id}: {:?}", s.reasons);
    }
    let sys01 = &cases[0].2;
    assert!((sys01.residual_w.unwrap() + 3.0).abs() < 1e-9);
    assert!(sys01.relative_residual.unwrap() < 0.02);
    for r in &sys01.rows {
        let expected = if r.account_id == "THERMAL_CONTROL" { -3.0 } else { 0.0 };
        assert!((r.mismatch_w - expected).abs() <= 1e-9, "{}: {}", r.account_id, r.mismatch_w);
    }
    let sys02 = &cases[1].2;
    assert!((sys02.residual_w.unwrap() - 37.0).abs() < 1e-9);
    assert!(sys02.reasons.iter().any(|r| r.starts_with("CONS-L1_RESIDUAL")));
    assert!(cases[3].2.reasons.iter().any(|r| r.starts_with("CONS-L1_UNCOVERED_LOAD")));
    assert!(cases[4].2.reasons.iter().any(|r| r.starts_with("CONS-L1_DOUBLE_COUNT")));
    assert_eq!(cases[5].2.status, EvalStatus::IncompleteEvidence);
    let sys01b = &cases[8].2;
    assert!(sys01b.relative_residual.unwrap() < 1e-12, "{:?}", sys01b.relative_residual);
    assert!(sys01b.rows.iter().all(|r| r.mismatch_w.abs() <= 1e-9));
}
