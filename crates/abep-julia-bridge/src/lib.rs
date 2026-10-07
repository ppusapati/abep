//! Orchestration of the pinned HallThruster.jl bridge across a process boundary (SC-WP-03; contract
//! `docs/rust_migration/contracts/C-JULIA-BRIDGE-LAUNCH/parity_prereg_v1.json`).
//!
//! HallThruster.jl v0.23.1 (commit bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5, Julia 1.11.7) stays authoritative for the
//! Hall discharge; no Hall physics is rewritten here. Rust owns job generation (launch manifests, shard job
//! specifications), the pre-launch pin check, the launch with a fixed argv / environment allow-list / pinned thread
//! settings, record reading (structural gate) and the per-run provenance sidecar. Normal tests never spawn Julia; the
//! real runs are registered platform tests (docs/rust_migration/test_register/platform_tests_v1.json).
//!
//! [`envelope_cases`] (NP-HALL-PARAMETRIC-ENVELOPE v1, A9.32) generates and dry-runs the H-1 parametric envelope case
//! file, launches its shards through [`launch::launch`] and freezes their outputs.

pub mod envelope_cases;
pub mod jobs;
pub mod launch;
pub mod manifests;
pub mod pin;
pub mod sidecar;

/// Contract id recorded in every sidecar written by this crate.
pub const CONTRACT_ID: &str = "PARITY-C-JULIA-BRIDGE-LAUNCH-V1";
