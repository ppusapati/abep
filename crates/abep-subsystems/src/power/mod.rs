//! SC-WP-05 electrical layer: the spacecraft-side DC bus-power boundary `bus_power_boundary_a9_v2` of the selected
//! architecture `hall_icp_neutralizer` (A9.22 G8; A9.30 sec. 5).
//!
//! Raw power physics and bookkeeping only. The module produces the load ledger and the bus demand; it holds no RFP
//! limit and no RFP gate (A9.30 sec. 5: the 1.5 kW limit is ASSESSMENT ONLY, abep-assess / SC-WP-11). Flight C1
//! loads are NONE: the GROUND_REFERENCE_ONLY C1 slots, events and start-up rule of the historical boundary tables
//! are not part of this module.
//!
//! * [`slots`], [`ledger`], [`sampling`], [`rf_planes`], [`sequence`], [`allocation`], [`official`], [`objective`]:
//!   parity port of `abep_sim/bus_boundary_a9_v2.py` and its rebound v1 functions, `architecture_optimizer.
//!   official_ledger` and the raw part of `design_synthesis.bus_power` (contract
//!   `docs/rust_migration/contracts/C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY/parity_prereg_v1.json`).
//! * [`magnet`]: `abep_sim/magnet_power.py` without the ECR field (contract C-ABEP_SIM_MAGNET_POWER_PY).
//! * [`cplx`], [`rf_match`]: RF-network kernels of the P2 framework / reducer and the P1 `P_mains` refusal (contract
//!   C-DOCS_EXPERIMENTS_HALL_ICP_P2_IMPEDANCE_MAP).
//! * [`system_ledger`] (CONS-L1, CLAUDE.md rule 4), [`icp_bus`] (IF-ICP-BUS-v1 consumer) and [`demand`] (typed
//!   upstream inputs to bus demand): Rust-only items registered in the bus-boundary contract.
//! * [`eval`]: the JSON call interface used by the parity harnesses (`examples/power_eval.rs`).

pub mod allocation;
pub mod cplx;
pub mod demand;
pub mod eval;
pub mod icp_bus;
pub mod ledger;
pub mod magnet;
pub mod objective;
pub mod official;
pub mod pyfmt;
pub mod rf_match;
pub mod rf_planes;
pub mod sampling;
pub mod sequence;
pub mod slots;
pub mod system_ledger;

use abep_types::pyjson::PyException;
use abep_types::{AbepError, EvalStatus};
use std::fmt;

/// A refusal of the power layer, named by the Python exception class of the reference it mirrors
/// (`BoundaryA9Error`, `ValueError`, `OverflowError`, `KeyError`, ...), with its fail-closed status.
#[derive(Debug, Clone, PartialEq)]
pub struct PowerError {
    pub class: &'static str,
    pub message: String,
    pub status: EvalStatus,
}

impl PowerError {
    pub fn new(class: &'static str, message: impl Into<String>) -> Self {
        PowerError { class, message: message.into(), status: EvalStatus::ModelError }
    }

    /// A refusal because an input lies outside the registered model domain.
    pub fn out_of_domain(class: &'static str, message: impl Into<String>) -> Self {
        PowerError { class, message: message.into(), status: EvalStatus::OutOfDomain }
    }

    /// The A9 boundary's `BoundaryA9Error` (malformed or refused input; no fallback, no default).
    pub fn boundary(message: impl Into<String>) -> Self {
        PowerError::new("BoundaryA9Error", message)
    }

    pub fn to_abep_error(&self) -> AbepError {
        let message = format!("{}: {}", self.class, self.message);
        match self.status {
            EvalStatus::OutOfDomain => AbepError::OutOfDomain { message },
            EvalStatus::IncompleteEvidence => AbepError::IncompleteEvidence { message },
            _ => AbepError::Model { message },
        }
    }
}

impl From<PyException> for PowerError {
    fn from(e: PyException) -> Self {
        PowerError::new(e.class, e.message)
    }
}

impl fmt::Display for PowerError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} ({}): {}", self.class, self.status, self.message)
    }
}

impl std::error::Error for PowerError {}

pub type PowerResult<T> = Result<T, PowerError>;
