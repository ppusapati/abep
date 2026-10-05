//! Shared status and error vocabulary of the ABEP Rust simulator.
//!
//! Fail-closed evidence semantics (CLAUDE.md rules 3 and 9, A9.29 RM-OQ-05): a result that cannot be evaluated is
//! reported with an explicit status, never as a silently skipped or half-converged value.

use serde::{Deserialize, Serialize};
use std::fmt;

/// Evaluation status of a raw-physics or evidence result.
///
/// The serialized names are the repository vocabulary (`NOT_EVALUATED`, `INCOMPLETE_EVIDENCE`, `OUT_OF_DOMAIN`,
/// `MODEL_ERROR`). `Evaluated` means the quantity was computed inside its registered domain; it is never a gate
/// verdict (no PASS / FAIL in raw physics, A9.22 layer separation).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum EvalStatus {
    Evaluated,
    NotEvaluated,
    IncompleteEvidence,
    OutOfDomain,
    ModelError,
}

impl EvalStatus {
    /// Repository vocabulary string, identical to the serialized form.
    pub fn as_str(self) -> &'static str {
        match self {
            EvalStatus::Evaluated => "EVALUATED",
            EvalStatus::NotEvaluated => "NOT_EVALUATED",
            EvalStatus::IncompleteEvidence => "INCOMPLETE_EVIDENCE",
            EvalStatus::OutOfDomain => "OUT_OF_DOMAIN",
            EvalStatus::ModelError => "MODEL_ERROR",
        }
    }

    /// True only for `Evaluated`. Every other status is fail-closed.
    pub fn is_evaluated(self) -> bool {
        matches!(self, EvalStatus::Evaluated)
    }
}

impl fmt::Display for EvalStatus {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Errors that stop a computation. Each maps to exactly one fail-closed status.
#[derive(Debug, Clone, PartialEq)]
pub enum AbepError {
    /// A file could not be read.
    Io { path: String, message: String },
    /// A pinned sha256 does not match the bytes on disk (frozen data / config / evidence).
    HashMismatch { path: String, expected: String, actual: String },
    /// A document does not have the registered schema.
    Schema { path: String, message: String },
    /// An input lies outside the registered model domain.
    OutOfDomain { message: String },
    /// Required evidence is not registered.
    IncompleteEvidence { message: String },
    /// Any other model failure (non-convergence, invariant violation).
    Model { message: String },
}

impl AbepError {
    /// The fail-closed status this error is reported as.
    pub fn status(&self) -> EvalStatus {
        match self {
            AbepError::OutOfDomain { .. } => EvalStatus::OutOfDomain,
            AbepError::IncompleteEvidence { .. } => EvalStatus::IncompleteEvidence,
            AbepError::Io { .. }
            | AbepError::HashMismatch { .. }
            | AbepError::Schema { .. }
            | AbepError::Model { .. } => EvalStatus::ModelError,
        }
    }
}

impl fmt::Display for AbepError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AbepError::Io { path, message } => write!(f, "{}: cannot read {path}: {message}", self.status()),
            AbepError::HashMismatch { path, expected, actual } => {
                write!(f, "{}: sha256 mismatch for {path}: expected {expected}, found {actual}", self.status())
            }
            AbepError::Schema { path, message } => write!(f, "{}: schema error in {path}: {message}", self.status()),
            AbepError::OutOfDomain { message }
            | AbepError::IncompleteEvidence { message }
            | AbepError::Model { message } => write!(f, "{}: {message}", self.status()),
        }
    }
}

impl std::error::Error for AbepError {}

pub type AbepResult<T> = Result<T, AbepError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_strings_are_the_repository_vocabulary() {
        for (s, name) in [
            (EvalStatus::Evaluated, "EVALUATED"),
            (EvalStatus::NotEvaluated, "NOT_EVALUATED"),
            (EvalStatus::IncompleteEvidence, "INCOMPLETE_EVIDENCE"),
            (EvalStatus::OutOfDomain, "OUT_OF_DOMAIN"),
            (EvalStatus::ModelError, "MODEL_ERROR"),
        ] {
            assert_eq!(s.as_str(), name);
            assert_eq!(serde_json::to_string(&s).unwrap(), format!("\"{name}\""));
            assert_eq!(serde_json::from_str::<EvalStatus>(&format!("\"{name}\"")).unwrap(), s);
        }
    }

    #[test]
    fn only_evaluated_is_not_fail_closed() {
        assert!(EvalStatus::Evaluated.is_evaluated());
        for s in
            [EvalStatus::NotEvaluated, EvalStatus::IncompleteEvidence, EvalStatus::OutOfDomain, EvalStatus::ModelError]
        {
            assert!(!s.is_evaluated());
        }
    }

    #[test]
    fn errors_map_to_fail_closed_statuses() {
        let hm = AbepError::HashMismatch { path: "p".into(), expected: "a".into(), actual: "b".into() };
        assert_eq!(hm.status(), EvalStatus::ModelError);
        assert_eq!(AbepError::OutOfDomain { message: "x".into() }.status(), EvalStatus::OutOfDomain);
        assert_eq!(AbepError::IncompleteEvidence { message: "x".into() }.status(), EvalStatus::IncompleteEvidence);
        assert!(hm.to_string().starts_with("MODEL_ERROR: sha256 mismatch"));
    }
}
