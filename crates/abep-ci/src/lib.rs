//! Workspace policy checks (A9.29 secs. 1, 3, 9; CI_PLAN.md §§ 3, 7, 8). Non-flight tooling: no simulator crate
//! depends on it. The `abep-ci` binary exposes the checks for CI steps until the `abep ci` CLI exists (W14 / W16).

pub mod acceptance_report;
pub mod groundtest;
pub mod test_register;
