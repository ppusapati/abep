//! Refusals of the assessment layer, labelled with the Python exception class they mirror.
//!
//! Owner-rule and input refusals (`A913RuleError`, `BoundaryA9Error`, `OptimizerError`, `RvmError`, `ValueError`) are
//! OUT_OF_DOMAIN; anything else (a record outside the documented shapes, a pin that does not verify) is MODEL_ERROR.

use abep_types::pyjson::PyException;
use abep_types::{AbepError, EvalStatus};
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AssessError {
    pub class: String,
    pub message: String,
}

pub type AssessResult<T> = Result<T, AssessError>;

pub const INPUT_CLASSES: [&str; 6] =
    ["A913RuleError", "BoundaryA9Error", "OptimizerError", "RvmError", "ValueError", "IcpGateError"];

impl AssessError {
    pub fn new(class: &str, message: impl Into<String>) -> Self {
        AssessError { class: class.to_string(), message: message.into() }
    }

    pub fn status(&self) -> EvalStatus {
        if INPUT_CLASSES.contains(&self.class.as_str()) {
            EvalStatus::OutOfDomain
        } else {
            EvalStatus::ModelError
        }
    }
}

impl fmt::Display for AssessError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.class, self.message)
    }
}

impl std::error::Error for AssessError {}

impl From<AssessError> for AbepError {
    fn from(e: AssessError) -> AbepError {
        let message = e.to_string();
        match e.status() {
            EvalStatus::OutOfDomain => AbepError::OutOfDomain { message },
            _ => AbepError::Model { message },
        }
    }
}

impl From<PyException> for AssessError {
    fn from(e: PyException) -> Self {
        AssessError::new(e.class, e.message)
    }
}

impl From<abep_gaspath::GasPathError> for AssessError {
    fn from(e: abep_gaspath::GasPathError) -> Self {
        AssessError::new(e.class.name(), e.message)
    }
}

impl From<abep_config::ConfigError> for AssessError {
    fn from(e: abep_config::ConfigError) -> Self {
        AssessError::new(e.class, e.message)
    }
}

/// A refusal of an admitted crate whose message is `<Class>: <text>` (abep-mission convention); other errors keep
/// their status text as class.
impl From<AbepError> for AssessError {
    fn from(e: AbepError) -> Self {
        match &e {
            AbepError::OutOfDomain { message } | AbepError::Model { message } => match message.split_once(": ") {
                Some((k, rest)) if !k.is_empty() && k.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') => {
                    AssessError::new(k, rest)
                }
                _ => AssessError::new(e.status().as_str(), message.clone()),
            },
            other => AssessError::new(other.status().as_str(), other.to_string()),
        }
    }
}

pub fn rule_error(message: impl Into<String>) -> AssessError {
    AssessError::new("A913RuleError", message)
}

pub fn key_error(key: &str) -> AssessError {
    AssessError::new("KeyError", abep_types::pyjson::py_repr_str(key))
}

pub fn type_error(message: impl Into<String>) -> AssessError {
    AssessError::new("TypeError", message)
}

pub fn model_error(message: impl Into<String>) -> AssessError {
    AssessError::new("MODEL_ERROR", message)
}
