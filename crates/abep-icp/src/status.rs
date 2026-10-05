//! Raw-output status vocabulary of NP-ICP-NEUTRALIZER v1 (prereg `status_vocabulary`, output rules 1-4).
//!
//! The prereg names the evaluated state `CONVERGED`; it maps one-to-one onto `abep_types::EvalStatus::Evaluated`. No
//! other state exists in raw output: no PASS / FAIL / OK / PARTIAL / half-converged value.

use abep_types::EvalStatus;
use serde::{Deserialize, Serialize};
use std::fmt;

/// Status of one raw output or of a whole case.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum IcpStatus {
    Converged,
    NotEvaluated,
    IncompleteEvidence,
    OutOfDomain,
    ModelError,
}

impl IcpStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            IcpStatus::Converged => "CONVERGED",
            IcpStatus::NotEvaluated => "NOT_EVALUATED",
            IcpStatus::IncompleteEvidence => "INCOMPLETE_EVIDENCE",
            IcpStatus::OutOfDomain => "OUT_OF_DOMAIN",
            IcpStatus::ModelError => "MODEL_ERROR",
        }
    }

    pub fn is_converged(self) -> bool {
        matches!(self, IcpStatus::Converged)
    }

    /// Severity used when several statuses meet in one output. Input registration ranks INCOMPLETE_EVIDENCE above
    /// NOT_EVALUATED (prereg NE-01 / NE-06: a missing geometry dominates an absent external record).
    pub fn severity(self) -> u8 {
        match self {
            IcpStatus::Converged => 0,
            IcpStatus::NotEvaluated => 1,
            IcpStatus::IncompleteEvidence => 2,
            IcpStatus::OutOfDomain => 3,
            IcpStatus::ModelError => 4,
        }
    }

    pub fn worst<I: IntoIterator<Item = IcpStatus>>(it: I) -> IcpStatus {
        it.into_iter().max_by_key(|s| s.severity()).unwrap_or(IcpStatus::Converged)
    }
}

impl From<IcpStatus> for EvalStatus {
    fn from(s: IcpStatus) -> EvalStatus {
        match s {
            IcpStatus::Converged => EvalStatus::Evaluated,
            IcpStatus::NotEvaluated => EvalStatus::NotEvaluated,
            IcpStatus::IncompleteEvidence => EvalStatus::IncompleteEvidence,
            IcpStatus::OutOfDomain => EvalStatus::OutOfDomain,
            IcpStatus::ModelError => EvalStatus::ModelError,
        }
    }
}

impl fmt::Display for IcpStatus {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// A named reason. `code` is a stable identifier (prereg ids where one exists); `detail` is free text.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct Reason {
    pub code: String,
    pub status: IcpStatus,
    pub detail: String,
}

impl Reason {
    pub fn new(code: &str, status: IcpStatus, detail: impl Into<String>) -> Self {
        Reason { code: code.to_string(), status, detail: detail.into() }
    }
}

/// Status of a reason list under the registered evaluation order (prereg status_vocabulary.evaluation_order): a
/// registration failure (NOT_EVALUATED / INCOMPLETE_EVIDENCE, or a refused registration as MODEL_ERROR) precedes a
/// domain verdict, so OUT_OF_DOMAIN decides only when nothing else is pending. CONVERGED when empty.
pub fn worst_of(reasons: &[Reason]) -> IcpStatus {
    let pending = IcpStatus::worst(reasons.iter().map(|r| r.status).filter(|s| *s != IcpStatus::OutOfDomain));
    if pending.is_converged() {
        IcpStatus::worst(reasons.iter().map(|r| r.status))
    } else {
        pending
    }
}

/// One raw output value with its own status (output rule 1). A non-CONVERGED value is always null (rule 2).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Quantity {
    pub value: Option<f64>,
    pub unit: String,
    pub status: IcpStatus,
    pub reasons: Vec<String>,
}

impl Quantity {
    /// A computed value. Non-finite values are refused here as MODEL_ERROR with a null value (NV-05).
    pub fn value(v: f64, unit: &str) -> Self {
        if v.is_finite() {
            // + 0.0 maps -0.0 (an empty f64 sum) to +0.0 and changes no other value.
            Quantity { value: Some(v + 0.0), unit: unit.to_string(), status: IcpStatus::Converged, reasons: vec![] }
        } else {
            Quantity::withheld(unit, IcpStatus::ModelError, vec!["NV-05_NON_FINITE_VALUE".into()])
        }
    }

    /// A withheld value: null with the given status and reason codes.
    pub fn withheld(unit: &str, status: IcpStatus, reasons: Vec<String>) -> Self {
        Quantity { value: None, unit: unit.to_string(), status, reasons }
    }

    /// Withheld with the codes of a reason list and its worst status.
    pub fn withheld_by(unit: &str, reasons: &[Reason]) -> Self {
        let status = worst_of(reasons);
        let status = if status.is_converged() { IcpStatus::ModelError } else { status };
        Quantity::withheld(unit, status, reasons.iter().map(|r| r.code.clone()).collect())
    }

    /// A converged case where the quantity is not defined (e.g. T_e when plasma_state = NOT_SUSTAINED).
    pub fn undefined(unit: &str, reason: &str) -> Self {
        Quantity { value: None, unit: unit.to_string(), status: IcpStatus::Converged, reasons: vec![reason.into()] }
    }

    pub fn is_converged_value(&self) -> bool {
        self.status.is_converged() && self.value.is_some()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vocabulary_and_mapping() {
        for (s, name, e) in [
            (IcpStatus::Converged, "CONVERGED", EvalStatus::Evaluated),
            (IcpStatus::NotEvaluated, "NOT_EVALUATED", EvalStatus::NotEvaluated),
            (IcpStatus::IncompleteEvidence, "INCOMPLETE_EVIDENCE", EvalStatus::IncompleteEvidence),
            (IcpStatus::OutOfDomain, "OUT_OF_DOMAIN", EvalStatus::OutOfDomain),
            (IcpStatus::ModelError, "MODEL_ERROR", EvalStatus::ModelError),
        ] {
            assert_eq!(s.as_str(), name);
            assert_eq!(serde_json::to_string(&s).unwrap(), format!("\"{name}\""));
            assert_eq!(EvalStatus::from(s), e);
        }
    }

    #[test]
    fn registration_precedes_the_domain_verdict() {
        let ood = Reason::new("DOM-11", IcpStatus::OutOfDomain, "");
        let ie = Reason::new("IN-10", IcpStatus::IncompleteEvidence, "");
        let me = Reason::new("X", IcpStatus::ModelError, "");
        assert_eq!(worst_of(&[ood.clone(), ie.clone()]), IcpStatus::IncompleteEvidence);
        assert_eq!(worst_of(std::slice::from_ref(&ood)), IcpStatus::OutOfDomain);
        assert_eq!(worst_of(&[ood, ie, me]), IcpStatus::ModelError);
        assert_eq!(worst_of(&[]), IcpStatus::Converged);
    }

    #[test]
    fn non_finite_is_withheld() {
        let q = Quantity::value(f64::NAN, "W");
        assert_eq!(q.status, IcpStatus::ModelError);
        assert!(q.value.is_none());
        assert!(Quantity::value(f64::INFINITY, "W").value.is_none());
    }
}
