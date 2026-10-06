//! ABEP intake (SC-WP-02, ES-3).
//!
//! The admitted Kernel-1 TPMC library `abep_core` (parity_report_v2) is called directly as a plain Rust library
//! (A9.29 secs. 5, 11: Rust simulator -> Rust TPMC library; no backend switch). Its consumption from this workspace is
//! covered by the registered build-equivalence addendum
//! (`docs/rust_migration/contracts/C-ABEP_CORE_BUILD_EQUIVALENCE/`, verdict EQUIVALENT).
//!
//! Python references (migration parity, `docs/rust_migration/contracts/`):
//! * `abep_sim/intake_tpmc.py` intake_response / response_surface / clausing_transmission / IntakeSurface
//!   -> [`tpmc_response`], [`surface`] (PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1);
//! * `abep_sim/intake.py` collection / compress / passive_compression -> [`collection`]
//!   (PARITY-C-ABEP_SIM_INTAKE_PY-V1).
//!
//! Raw physics only: no PASS / FAIL, no requirement threshold. Refusals are `AbepError::OutOfDomain` whose message
//! starts with a registered key (`KEY: text`); missing determining evidence is a status, never a value.

pub mod build_equivalence;
pub mod collection;
pub mod constants;
pub mod freestream;
pub mod frozen;
pub mod surface;
pub mod tpmc_response;

use abep_types::AbepError;

/// Refusal with a registered message key (`KEY: text`), status OUT_OF_DOMAIN.
pub(crate) fn refuse(key: &str, text: impl std::fmt::Display) -> AbepError {
    AbepError::OutOfDomain { message: format!("{key}: {text}") }
}

/// The registered message key of an error produced by this crate (text before the first ': ').
pub fn message_key(e: &AbepError) -> Option<&str> {
    match e {
        AbepError::OutOfDomain { message }
        | AbepError::Model { message }
        | AbepError::IncompleteEvidence { message } => message.split_once(": ").map(|(k, _)| k),
        _ => None,
    }
}

/// Python `max(a, b)`: returns `a` unless `b > a` (argument order matters for NaN).
#[inline]
pub(crate) fn py_max(a: f64, b: f64) -> f64 {
    if b > a {
        b
    } else {
        a
    }
}
