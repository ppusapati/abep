//! Refusals of the design / UQ functions. Each carries the Python exception class of the reference (EXACT_VALUE
//! parity) and maps to one fail-closed status: input refusals (OptimizerError, ValueError, KeyError, IntakeInputError)
//! OUT_OF_DOMAIN; owner-rule refusals (A913RuleError, RepresentativeSelectionRefused) NOT_EVALUATED; everything else
//! (RuntimeError, arithmetic, I/O, a changed pinned input) MODEL_ERROR.

use abep_gaspath::GasPathError;
use abep_types::{AbepError, EvalStatus};
use std::fmt;

#[derive(Debug, Clone, PartialEq)]
pub struct DesignError {
    /// Python exception class name of the reference
    pub class: String,
    pub message: String,
}

pub type DResult<T> = Result<T, DesignError>;

impl DesignError {
    pub fn new(class: &str, message: impl Into<String>) -> Self {
        DesignError { class: class.to_string(), message: message.into() }
    }

    pub fn status(&self) -> EvalStatus {
        match self.class.as_str() {
            "OptimizerError"
            | "ValueError"
            | "KeyError"
            | "IntakeInputError"
            | "SynthesisInputError"
            | "FilterStageError" => EvalStatus::OutOfDomain,
            "A913RuleError" | "RepresentativeSelectionRefused" | "ArchitectureRuleError" => EvalStatus::NotEvaluated,
            "IncompleteEvidence" => EvalStatus::IncompleteEvidence,
            _ => EvalStatus::ModelError,
        }
    }
}

impl fmt::Display for DesignError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {} ({})", self.class, self.message, self.status())
    }
}

impl std::error::Error for DesignError {}

/// `OptimizerError(message)` (ValueError subclass of the reference).
pub fn opt_err(message: impl Into<String>) -> DesignError {
    DesignError::new("OptimizerError", message)
}

/// A model failure; a leading `Class: ` prefix in the message names the reference class.
pub fn model(message: impl Into<String>) -> DesignError {
    let m: String = message.into();
    if let Some((cls, rest)) = m.split_once(": ") {
        if !cls.is_empty() && cls.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') && cls.ends_with("Error") {
            return DesignError::new(cls, rest);
        }
    }
    DesignError::new("RuntimeError", m)
}

pub fn schema(path: &str, what: &str) -> DesignError {
    DesignError::new("RuntimeError", format!("{path}: schema: {what}"))
}

impl From<GasPathError> for DesignError {
    fn from(e: GasPathError) -> Self {
        DesignError::new(e.class.name(), e.message)
    }
}

impl From<AbepError> for DesignError {
    fn from(e: AbepError) -> Self {
        match e {
            AbepError::Io { path, message } => DesignError::new("FileNotFoundError", format!("{path}: {message}")),
            AbepError::HashMismatch { path, expected, actual } => DesignError::new(
                "RuntimeError",
                format!("pinned input changed: {path} sha256 {actual} != registered {expected}"),
            ),
            AbepError::Schema { path, message } => DesignError::new("RuntimeError", format!("{path}: {message}")),
            AbepError::OutOfDomain { message } => {
                let d = model(message);
                if d.class == "RuntimeError" {
                    DesignError::new("ValueError", d.message)
                } else {
                    d
                }
            }
            AbepError::IncompleteEvidence { message } => DesignError::new("IncompleteEvidence", message),
            AbepError::Model { message } => model(message),
        }
    }
}
