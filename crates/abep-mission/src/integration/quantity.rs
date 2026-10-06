//! Quantities of the mission record (prereg quantity_representation, Q-1..Q-4) and the status precedence (SP-01).

use abep_types::{AbepError, AbepResult, EvalStatus};
use serde::Serialize;

/// Parametric labels (Q-2). A parametric value never enters `value`, an evidence integral, an envelope or a status.
pub const PARAMETRIC_SENSITIVITY_ONLY: &str = "PARAMETRIC_SENSITIVITY_ONLY";
pub const PARAMETRIC_BOUND: &str = "PARAMETRIC_BOUND";
pub const PARAMETRIC_PLANNING_CASE: &str = "PARAMETRIC_PLANNING_CASE";
pub const PARAMETRIC: &str = "PARAMETRIC";
pub const PARAMETRIC_LABELS: [&str; 4] =
    [PARAMETRIC_SENSITIVITY_ONLY, PARAMETRIC_BOUND, PARAMETRIC_PLANNING_CASE, PARAMETRIC];

/// Evidence classes (rule 10 vocabulary plus `structural` and the synthetic-test class).
pub const EVIDENCE_CLASSES: [&str; 10] = [
    "measured",
    "digitized",
    "inferred",
    "reconstructed",
    "model-derived",
    "assumed",
    "owner-allocation",
    "structural",
    "SYNTHETIC_TEST_DATA_NOT_EVIDENCE",
    "none",
];

/// Severity of SP-01: MODEL_ERROR > OUT_OF_DOMAIN > NOT_EVALUATED > INCOMPLETE_EVIDENCE > EVALUATED.
pub fn severity(s: EvalStatus) -> u8 {
    match s {
        EvalStatus::Evaluated => 0,
        EvalStatus::IncompleteEvidence => 1,
        EvalStatus::NotEvaluated => 2,
        EvalStatus::OutOfDomain => 3,
        EvalStatus::ModelError => 4,
    }
}

/// The most severe of `a` and `b` (SP-01).
pub fn worst(a: EvalStatus, b: EvalStatus) -> EvalStatus {
    if severity(b) > severity(a) {
        b
    } else {
        a
    }
}

/// The most severe status of an iterator (EVALUATED when empty).
pub fn worst_of<I: IntoIterator<Item = EvalStatus>>(it: I) -> EvalStatus {
    it.into_iter().fold(EvalStatus::Evaluated, worst)
}

/// A named reason, tagged with where it came from.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Reason {
    pub code: String,
    pub status: EvalStatus,
    pub detail: String,
}

impl Ord for Reason {
    fn cmp(&self, o: &Self) -> std::cmp::Ordering {
        (&self.code, severity(self.status), &self.detail).cmp(&(&o.code, severity(o.status), &o.detail))
    }
}

impl PartialOrd for Reason {
    fn partial_cmp(&self, o: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(o))
    }
}

impl Reason {
    pub fn new(code: &str, status: EvalStatus, detail: impl Into<String>) -> Self {
        Reason { code: code.to_string(), status, detail: detail.into() }
    }

    /// The same reason with a location prefix on its detail (`state/mode/field: ...`).
    pub fn tagged(&self, tag: &str) -> Self {
        Reason { code: self.code.clone(), status: self.status, detail: format!("{tag}: {}", self.detail) }
    }
}

/// A physical bound / parametric / planning result (Q-2).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Parametric {
    pub value: f64,
    pub label: String,
    pub basis: String,
}

/// Registered uncertainty of a Quantity.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Uncertainty {
    NotQuantified,
    Bounds { lo: f64, hi: f64 },
}

/// One quantity of the mission record.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Quantity {
    pub units: String,
    pub status: EvalStatus,
    pub value: Option<f64>,
    pub parametric: Option<Parametric>,
    pub evidence_class: String,
    pub uncertainty: Uncertainty,
    pub source: String,
    pub reasons: Vec<Reason>,
}

fn model(msg: impl Into<String>) -> AbepError {
    AbepError::Model { message: msg.into() }
}

impl Quantity {
    /// An evidence-qualified value (status EVALUATED).
    pub fn evaluated(units: &str, value: f64, evidence_class: &str, source: impl Into<String>) -> AbepResult<Self> {
        let q = Quantity {
            units: units.to_string(),
            status: EvalStatus::Evaluated,
            value: Some(value),
            parametric: None,
            evidence_class: evidence_class.to_string(),
            uncertainty: Uncertainty::NotQuantified,
            source: source.into(),
            reasons: Vec::new(),
        };
        q.validate()?;
        Ok(q)
    }

    /// A fail-closed quantity without a value. `reason.status` must not be EVALUATED.
    pub fn absent(units: &str, reason: Reason) -> AbepResult<Self> {
        let q = Quantity {
            units: units.to_string(),
            status: reason.status,
            value: None,
            parametric: None,
            evidence_class: "none".into(),
            uncertainty: Uncertainty::NotQuantified,
            source: String::new(),
            reasons: vec![reason],
        };
        q.validate()?;
        Ok(q)
    }

    /// A structural zero (Q-4): created only by the registered routing / applicability cells.
    pub fn structural_zero(units: &str, code: &str) -> Self {
        Quantity {
            units: units.to_string(),
            status: EvalStatus::Evaluated,
            value: Some(0.0),
            parametric: None,
            evidence_class: "structural".into(),
            uncertainty: Uncertainty::NotQuantified,
            source: code.to_string(),
            reasons: Vec::new(),
        }
    }

    /// Attach a parametric layer (the evidence status and value are untouched).
    pub fn with_parametric(mut self, value: f64, label: &str, basis: impl Into<String>) -> AbepResult<Self> {
        self.parametric = Some(Parametric { value, label: label.to_string(), basis: basis.into() });
        self.validate()?;
        Ok(self)
    }

    pub fn with_source(mut self, source: impl Into<String>) -> Self {
        self.source = source.into();
        self
    }

    pub fn with_uncertainty(mut self, u: Uncertainty) -> Self {
        self.uncertainty = u;
        self
    }

    /// Q-1, Q-3 and the label / class vocabularies; a violation is MODEL_ERROR (FT-14).
    pub fn validate(&self) -> AbepResult<()> {
        match (self.status, self.value) {
            (EvalStatus::Evaluated, None) => return Err(model("Q-1: EVALUATED quantity without a value")),
            (s, Some(_)) if s != EvalStatus::Evaluated => {
                return Err(model(format!("Q-1: a value with status {s} (only EVALUATED carries a value)")))
            }
            _ => {}
        }
        if let Some(v) = self.value {
            if !v.is_finite() {
                return Err(model("Q-3: non-finite value"));
            }
        }
        if let Some(p) = &self.parametric {
            if !p.value.is_finite() {
                return Err(model("Q-3: non-finite parametric value"));
            }
            if !PARAMETRIC_LABELS.contains(&p.label.as_str()) {
                return Err(model(format!("Q-2: unknown parametric label {:?}", p.label)));
            }
        }
        if !EVIDENCE_CLASSES.contains(&self.evidence_class.as_str()) {
            return Err(model(format!("unknown evidence class {:?}", self.evidence_class)));
        }
        if self.status != EvalStatus::Evaluated && self.reasons.is_empty() {
            return Err(model(format!("a {} quantity needs a reason", self.status)));
        }
        if let Uncertainty::Bounds { lo, hi } = self.uncertainty {
            if !(lo.is_finite() && hi.is_finite() && lo <= hi) {
                return Err(model("uncertainty bounds must be finite with lo <= hi"));
            }
        }
        Ok(())
    }

    /// The value used by the parametric layer: the evidence value, else the parametric value.
    pub fn value_or_parametric(&self) -> Option<f64> {
        self.value.or(self.parametric.as_ref().map(|p| p.value))
    }

    pub fn is_evaluated(&self) -> bool {
        self.status.is_evaluated()
    }
}

/// A field of the record: a Quantity, or NOT_APPLICABLE by the registered applicability table.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(untagged)]
pub enum Field {
    NotApplicable { not_applicable: String },
    Q(Quantity),
}

impl Field {
    pub fn quantity(&self) -> Option<&Quantity> {
        match self {
            Field::Q(q) => Some(q),
            Field::NotApplicable { .. } => None,
        }
    }
}

/// A label-valued input (the Hall state): a label when EVALUATED, else a status with reasons.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Label {
    pub status: EvalStatus,
    pub label: Option<String>,
    pub source: String,
    pub reasons: Vec<Reason>,
}

impl Label {
    pub fn validate(&self) -> AbepResult<()> {
        match (self.status, &self.label) {
            (EvalStatus::Evaluated, None) => Err(model("Q-1: EVALUATED label without a value")),
            (s, Some(_)) if s != EvalStatus::Evaluated => Err(model(format!("Q-1: a label with status {s}"))),
            (s, None) if self.reasons.is_empty() => Err(model(format!("a {s} label needs a reason"))),
            _ => Ok(()),
        }
    }
}

/// DR-01 / DR-02: a derived quantity from `operands` combined by `op` (registered order). Status = worst operand;
/// value only if every operand is EVALUATED; parametric layer only if every operand has a value or a parametric value
/// and at least one is parametric.
pub fn derive(units: &str, source: &str, operands: &[&Quantity], op: impl Fn(&[f64]) -> f64) -> AbepResult<Quantity> {
    let status = worst_of(operands.iter().map(|q| q.status));
    let mut reasons: Vec<Reason> = operands.iter().flat_map(|q| q.reasons.iter().cloned()).collect();
    reasons.sort();
    reasons.dedup();
    let all_eval = operands.iter().all(|q| q.is_evaluated());
    let value = if all_eval {
        Some(op(&operands.iter().map(|q| q.value.unwrap_or(f64::NAN)).collect::<Vec<_>>()))
    } else {
        None
    };
    let any_par = operands.iter().any(|q| q.value.is_none() && q.parametric.is_some());
    let parametric = if !all_eval && any_par && operands.iter().all(|q| q.value_or_parametric().is_some()) {
        let vals: Vec<f64> = operands.iter().map(|q| q.value_or_parametric().unwrap_or(f64::NAN)).collect();
        let mut labels: Vec<&str> = operands
            .iter()
            .filter(|q| q.value.is_none())
            .filter_map(|q| q.parametric.as_ref())
            .map(|p| p.label.as_str())
            .collect();
        labels.sort();
        labels.dedup();
        let label = if labels.len() == 1 { labels[0] } else { PARAMETRIC };
        Some(Parametric {
            value: op(&vals),
            label: label.to_string(),
            basis: format!("derived from {}", labels.join(", ")),
        })
    } else {
        None
    };
    let evidence_class = if all_eval {
        let mut c: Vec<&str> =
            operands.iter().map(|q| q.evidence_class.as_str()).filter(|c| *c != "structural").collect();
        c.sort();
        c.dedup();
        match c.as_slice() {
            [] => "structural".to_string(),
            [one] => one.to_string(),
            _ => "model-derived".to_string(),
        }
    } else {
        "none".to_string()
    };
    let q = Quantity {
        units: units.to_string(),
        status,
        value,
        parametric,
        evidence_class,
        uncertainty: Uncertainty::NotQuantified,
        source: source.to_string(),
        reasons,
    };
    q.validate()?;
    Ok(q)
}

#[cfg(test)]
mod tests {
    use super::*;

    const ALL: [EvalStatus; 5] = [
        EvalStatus::Evaluated,
        EvalStatus::IncompleteEvidence,
        EvalStatus::NotEvaluated,
        EvalStatus::OutOfDomain,
        EvalStatus::ModelError,
    ];

    #[test]
    fn al06_severity_table() {
        for (i, a) in ALL.iter().enumerate() {
            for (j, b) in ALL.iter().enumerate() {
                assert_eq!(worst(*a, *b), ALL[i.max(j)], "{a} {b}");
            }
        }
    }

    #[test]
    fn ft14_malformed_quantities_are_model_errors() {
        let mut q = Quantity::evaluated("N", 1.0, "measured", "s").unwrap();
        q.value = None;
        assert_eq!(q.validate().unwrap_err().status(), EvalStatus::ModelError);
        let mut q = Quantity::absent("N", Reason::new("X", EvalStatus::NotEvaluated, "x")).unwrap();
        q.value = Some(0.0);
        assert_eq!(q.validate().unwrap_err().status(), EvalStatus::ModelError);
        assert!(Quantity::evaluated("N", f64::NAN, "measured", "s").is_err());
        assert!(Quantity::absent("N", Reason::new("X", EvalStatus::Evaluated, "x")).is_err());
    }
}
