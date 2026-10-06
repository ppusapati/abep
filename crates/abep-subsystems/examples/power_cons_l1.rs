//! CONS-L1 system energy-ledger cases SYS-01..SYS-08 (contract PARITY-C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY-V1): prints
//! one JSON record per case (status, expected status, residual, per-account reconciliation). Verification tooling
//! for the parity report; synthetic inputs only.

#[path = "../tests/power_sys/mod.rs"]
mod power_sys;
#[path = "../tests/support/mod.rs"]
mod support;

use abep_subsystems::power::official::MassPowerA9V5;

fn main() {
    let root = abep_provenance::workspace_repo_root().expect("repository root");
    let mp = MassPowerA9V5::load(&root).expect("pinned mass/power record");
    let cases: Vec<serde_json::Value> =
        power_sys::system_cases(&mp).iter().map(|(id, exp, s)| power_sys::to_json(id, *exp, s)).collect();
    println!("{}", serde_json::to_string_pretty(&cases).expect("serializable"));
}
