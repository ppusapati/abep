//! Assessment layer of the ABEP Rust simulator (SC-WP-11; A9.22 / A9.23 layer separation, A9.24 items 4-5, A9.29
//! sec. 4, A9.30 sec. 5, A9.31 secs. 10, 12, 17).
//!
//! Raw physics emits quantities with statuses; this crate compares them with requirement-derived limits read from the
//! frozen configuration through abep-config, and never modifies them. No physics crate depends on this crate
//! (crate-graph test). Missing evidence stays NOT_EVALUATED / INCOMPLETE_EVIDENCE; no COMPLY / PASS is manufactured.
//!
//! Ported under preregistered parity (`docs/rust_migration/contracts/`):
//! * PARITY-C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY-V1: [`gates`] (HC-01..HC-12), [`power_gate`] (the RFP P_bus gate and
//!   the bus_power gate verdict), [`statewise`] (statewise_envelope over the admitted abep-mission quantifier, HC-08,
//!   HC-11, HC-12), [`pareto`], [`propellant`] (HC-10 structure), [`rvm`] snapshot, [`owner_state`] and the P1-IT-29
//!   M_n kernel in [`neutralization`];
//! * PARITY-C-DOCS_REQUIREMENTS_RVM_A9-RULES_AND_ICP_GATE-V1: [`rvm`] rules and replay, [`icp_gate`] (GNG-ICP-01).
//!
//! New, under acceptance ACCEPT-NI-ABEP-ASSESS-RFP-MATRIX-V1: the HC-05 evaluator ([`neutralization::hc05`]) and the
//! RFP constraint matrix ([`matrix`]).
//!
//! New, under preregistration NP-HALL-PARAMETRIC-ENVELOPE v1 (A9.32): the decisive 196-state two-layer closure run and
//! the A9.32 classification ([`closure`]); its addendum A2 harness v2 consuming every required physics path of the M1
//! exit item ([`closure_m1`]).

pub mod closure;
pub mod closure_icp;
pub mod closure_m1;
pub mod envelope_summary;
pub mod error;
pub mod gates;
pub mod icp_gate;
pub mod matrix;
pub mod neutralization;
pub mod owner_state;
pub mod pareto;
pub mod parity;
pub mod power_closure;
pub mod power_gate;
pub mod propellant;
pub mod py;
pub mod rvm;
pub mod statewise;
pub mod thresholds;

pub use error::{AssessError, AssessResult};
pub use thresholds::Thresholds;
