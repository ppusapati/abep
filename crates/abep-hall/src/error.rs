//! Refusal type of the crate. `kind` names the Python exception class the reference raises on the same input
//! (contract `outcome_identity`); `code` classifies the refusal for the fail-closed status; `message` is the text.

use abep_types::{AbepError, EvalStatus};
use std::fmt;

/// numpy ValueError families (contract `outcome_identity`, NUMPY_VALUE_ERROR:<sub>).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NumpySub {
    Ragged,
    Reshape,
    Convert,
    Truth,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    /// ValueError raised by the module itself.
    Value,
    /// hallmap_registry.RegistryError.
    Registry,
    /// KeyError; the message is the repr of the key.
    Key,
    FileNotFound,
    /// JSON / TOML / UTF-8 decoding.
    Decode,
    /// Any other OS-level or gzip read error.
    Os,
    /// TypeError / AttributeError.
    Type,
    Index,
    /// ValueError raised inside scipy's RegularGridInterpolator.
    ScipyValue,
    Numpy(NumpySub),
}

impl Kind {
    pub fn name(self) -> &'static str {
        match self {
            Kind::Value => "VALUE_ERROR",
            Kind::Registry => "REGISTRY_ERROR",
            Kind::Key => "KEY_ERROR",
            Kind::FileNotFound => "FILE_NOT_FOUND",
            Kind::Decode => "DECODE_ERROR",
            Kind::Os => "OS_ERROR",
            Kind::Type => "TYPE_ERROR",
            Kind::Index => "INDEX_ERROR",
            Kind::ScipyValue => "SCIPY_VALUE_ERROR",
            Kind::Numpy(NumpySub::Ragged) => "NUMPY_VALUE_ERROR:RAGGED",
            Kind::Numpy(NumpySub::Reshape) => "NUMPY_VALUE_ERROR:RESHAPE",
            Kind::Numpy(NumpySub::Convert) => "NUMPY_VALUE_ERROR:CONVERT",
            Kind::Numpy(NumpySub::Truth) => "NUMPY_VALUE_ERROR:TRUTH",
        }
    }

    /// The Python `except ValueError` clause catches these (JSON / Unicode decode errors are ValueErrors).
    pub fn is_value_error(self) -> bool {
        matches!(self, Kind::Value | Kind::Registry | Kind::Decode | Kind::ScipyValue | Kind::Numpy(_))
    }

    /// The Python `except OSError` clause catches these.
    pub fn is_os_error(self) -> bool {
        matches!(self, Kind::FileNotFound | Kind::Os)
    }
}

/// Refusal codes that are not MODEL_ERROR.
pub const NOT_ADMITTED_CODES: [&str; 3] = ["HM_NOT_ADMITTED", "REQ_SCREENING", "REQ_NOT_ADMITTED"];
pub const OUT_OF_DOMAIN_CODES: [&str; 2] = ["HM_QUERY_OUTSIDE", "RGI_OUT_OF_BOUNDS"];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HallError {
    pub kind: Kind,
    pub code: &'static str,
    pub message: String,
}

impl HallError {
    pub fn new(kind: Kind, code: &'static str, message: impl Into<String>) -> Self {
        HallError { kind, code, message: message.into() }
    }

    pub fn value(code: &'static str, message: impl Into<String>) -> Self {
        Self::new(Kind::Value, code, message)
    }

    pub fn registry(message: impl Into<String>) -> Self {
        Self::new(Kind::Registry, "REGISTRY", message)
    }

    pub fn type_error(message: impl Into<String>) -> Self {
        Self::new(Kind::Type, "TYPE", message)
    }

    pub fn index(message: impl Into<String>) -> Self {
        Self::new(Kind::Index, "INDEX", message)
    }

    pub fn decode(message: impl Into<String>) -> Self {
        Self::new(Kind::Decode, "DECODE", message)
    }

    pub fn scipy(code: &'static str, message: impl Into<String>) -> Self {
        Self::new(Kind::ScipyValue, code, message)
    }

    pub fn numpy(sub: NumpySub, message: impl Into<String>) -> Self {
        Self::new(Kind::Numpy(sub), "NUMPY", message)
    }

    /// The fail-closed status this refusal is reported as.
    pub fn status(&self) -> EvalStatus {
        if NOT_ADMITTED_CODES.contains(&self.code) {
            EvalStatus::NotEvaluated
        } else if OUT_OF_DOMAIN_CODES.contains(&self.code) {
            EvalStatus::OutOfDomain
        } else {
            EvalStatus::ModelError
        }
    }
}

impl fmt::Display for HallError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} ({}): {}", self.status(), self.kind.name(), self.message)
    }
}

impl std::error::Error for HallError {}

impl From<HallError> for AbepError {
    fn from(e: HallError) -> Self {
        let message = format!("{}: {}", e.kind.name(), e.message);
        match e.status() {
            EvalStatus::OutOfDomain => AbepError::OutOfDomain { message },
            EvalStatus::NotEvaluated => AbepError::IncompleteEvidence { message },
            _ => AbepError::Model { message },
        }
    }
}

pub type HallResult<T> = Result<T, HallError>;
