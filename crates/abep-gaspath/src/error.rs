//! Refusals of the gas-path functions. Each carries the Python exception class of the reference (EXACT_VALUE parity)
//! and maps to exactly one fail-closed `EvalStatus` (contracts' domain_and_error_parity.mapping).

use abep_types::{AbepError, EvalStatus};
use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PyClass {
    FilterStageError,
    SynthesisInputError,
    A913RuleError,
    RepresentativeSelectionRefused,
    ValueError,
    KeyError,
    ZeroDivisionError,
    OverflowError,
    RuntimeError,
}

impl PyClass {
    pub fn name(self) -> &'static str {
        match self {
            PyClass::FilterStageError => "FilterStageError",
            PyClass::SynthesisInputError => "SynthesisInputError",
            PyClass::A913RuleError => "A913RuleError",
            PyClass::RepresentativeSelectionRefused => "RepresentativeSelectionRefused",
            PyClass::ValueError => "ValueError",
            PyClass::KeyError => "KeyError",
            PyClass::ZeroDivisionError => "ZeroDivisionError",
            PyClass::OverflowError => "OverflowError",
            PyClass::RuntimeError => "RuntimeError",
        }
    }

    /// Registered mapping: input refusals are OUT_OF_DOMAIN, arithmetic failures MODEL_ERROR, owner-rule refusals
    /// NOT_EVALUATED (nothing is evaluated).
    pub fn status(self) -> EvalStatus {
        match self {
            PyClass::FilterStageError | PyClass::SynthesisInputError | PyClass::ValueError | PyClass::KeyError => {
                EvalStatus::OutOfDomain
            }
            PyClass::ZeroDivisionError | PyClass::OverflowError | PyClass::RuntimeError => EvalStatus::ModelError,
            PyClass::A913RuleError | PyClass::RepresentativeSelectionRefused => EvalStatus::NotEvaluated,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct GasPathError {
    pub class: PyClass,
    pub message: String,
}

pub type PyResult<T> = Result<T, GasPathError>;

impl GasPathError {
    pub fn new(class: PyClass, message: impl Into<String>) -> Self {
        GasPathError { class, message: message.into() }
    }
    pub fn status(&self) -> EvalStatus {
        self.class.status()
    }
    /// `"<class>: <message>"`, the text the reference records for a caught exception.
    pub fn py_text(&self) -> String {
        format!("{}: {}", self.class.name(), self.message)
    }
}

impl fmt::Display for GasPathError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} ({}): {}", self.status(), self.class.name(), self.message)
    }
}

impl std::error::Error for GasPathError {}

impl From<GasPathError> for AbepError {
    fn from(e: GasPathError) -> AbepError {
        let message = e.py_text();
        match e.status() {
            EvalStatus::OutOfDomain => AbepError::OutOfDomain { message },
            EvalStatus::IncompleteEvidence => AbepError::IncompleteEvidence { message },
            _ => AbepError::Model { message },
        }
    }
}

pub fn fse(msg: impl Into<String>) -> GasPathError {
    GasPathError::new(PyClass::FilterStageError, msg)
}
pub fn sie(msg: impl Into<String>) -> GasPathError {
    GasPathError::new(PyClass::SynthesisInputError, msg)
}
pub fn a913(msg: impl Into<String>) -> GasPathError {
    GasPathError::new(PyClass::A913RuleError, msg)
}
pub fn value_error(msg: impl Into<String>) -> GasPathError {
    GasPathError::new(PyClass::ValueError, msg)
}
/// Python `KeyError(key)`: the message is the repr of the key.
pub fn key_error(key: &str) -> GasPathError {
    GasPathError::new(PyClass::KeyError, format!("'{key}'"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_class_maps_to_one_fail_closed_status() {
        for (c, s) in [
            (PyClass::FilterStageError, EvalStatus::OutOfDomain),
            (PyClass::SynthesisInputError, EvalStatus::OutOfDomain),
            (PyClass::ValueError, EvalStatus::OutOfDomain),
            (PyClass::KeyError, EvalStatus::OutOfDomain),
            (PyClass::ZeroDivisionError, EvalStatus::ModelError),
            (PyClass::OverflowError, EvalStatus::ModelError),
            (PyClass::RuntimeError, EvalStatus::ModelError),
            (PyClass::A913RuleError, EvalStatus::NotEvaluated),
            (PyClass::RepresentativeSelectionRefused, EvalStatus::NotEvaluated),
        ] {
            assert_eq!(c.status(), s, "{}", c.name());
            assert!(!c.status().is_evaluated());
        }
        let e: AbepError = key_error("He").into();
        assert_eq!(e.status(), EvalStatus::OutOfDomain);
        assert_eq!(key_error("He").message, "'He'");
    }
}
