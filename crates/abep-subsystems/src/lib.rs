//! ABEP subsystem physics (programme_v3_1 cargo_workspace_proposal: `abep-subsystems`).
//!
//! * [`thermal`]: NP-THERMAL-CATHODELESS v1, the cathodeless Hall + downstream RF/ICP neutralizer lumped thermal network
//!   (`docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/prereg_v1.json`). Raw physics only: no margin, limit or
//!   PASS / FAIL; every output carries `validation_status = NOT_VALIDATED`.
//! * [`mass`]: SC-WP-07 selected-flight mass accounting (K-MASS-RULES, the `mass_power_a9_v5` record, the wet-mass
//!   objective and the Xe sensitivity kernels), ported under preregistered parity contracts.
//! * [`power`]: SC-WP-05 electrical layer on `bus_power_boundary_a9_v2` (load ledger, bus demand, start-up /
//!   concurrent loads, RF power planes and matching kernels, magnet load model, system energy ledger). Raw power
//!   physics and bookkeeping only: no RFP limit or gate (A9.30 sec. 5).

pub mod mass;
pub mod power;
pub mod thermal;
