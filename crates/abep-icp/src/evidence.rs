//! Per-input evidence registration (IN-22, `docs/EVIDENCE.md`): source, evidence level, quantity type, transformation
//! chain, uncertainty, applicability domain and validation status. A record missing any attribute is refused
//! (INCOMPLETE_EVIDENCE naming the input and the attribute).

use serde::{Deserialize, Serialize};

/// What a number is (`docs/EVIDENCE.md` quantity types), plus the two non-physical kinds the prereg uses: an owner
/// decision / definition (categorical inputs) and `SYNTHETIC_TEST_ONLY` (FC-15).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum QuantityType {
    Measured,
    Digitized,
    Inferred,
    Reconstructed,
    ModelDerived,
    Assumed,
    OwnerDecision,
    Definition,
    SyntheticTestOnly,
}

/// Uncertainty representation (UQ-01).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum UncertaintyRepr {
    /// Manufacturer / interval bound +/- a, rectangular: u = a / sqrt(3) (A9.1 UBQ-03).
    Interval { half_width: f64 },
    /// Normal with standard uncertainty u at coverage factor k.
    Normal { u: f64, k: f64 },
    /// A discrete, unweighted scenario set (UQ-02).
    ScenarioSet { label: String },
    /// A physical bound such as [0, 1] for a probability (IN-18 BOUNDED_BY_PHYSICAL_LIMITS).
    PhysicalBound { lo: f64, hi: f64 },
    /// Categorical input: no numeric uncertainty.
    Categorical,
}

impl UncertaintyRepr {
    /// Standard uncertainty where the representation defines one.
    pub fn standard_uncertainty(&self) -> Option<f64> {
        match self {
            UncertaintyRepr::Interval { half_width } => Some(half_width / 3f64.sqrt()),
            UncertaintyRepr::Normal { u, .. } => Some(*u),
            _ => None,
        }
    }
}

/// Evidence attributes of one input record. Every field is required; `None` or an empty string is a missing attribute.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct EvidenceRecord {
    pub source: Option<String>,
    /// "1".."7" (`docs/EVIDENCE.md` hierarchy) or "SYNTHETIC_TEST_ONLY".
    pub evidence_level: Option<String>,
    pub quantity_type: Option<QuantityType>,
    pub transformation_chain: Option<String>,
    pub uncertainty: Option<UncertaintyRepr>,
    pub applicability_domain: Option<String>,
    pub validation_status: Option<String>,
}

pub const SYNTHETIC_LABEL: &str = "SYNTHETIC_TEST_ONLY";

impl EvidenceRecord {
    /// A complete record for a synthetic verification input (FC-15). Never evidence.
    pub fn synthetic(what: &str) -> Self {
        EvidenceRecord {
            source: Some(format!("{SYNTHETIC_LABEL}: {what}")),
            evidence_level: Some(SYNTHETIC_LABEL.into()),
            quantity_type: Some(QuantityType::SyntheticTestOnly),
            transformation_chain: Some("none (synthetic verification input)".into()),
            uncertainty: Some(UncertaintyRepr::Categorical),
            applicability_domain: Some("analytic verification only; never evidence".into()),
            validation_status: Some("NOT_APPLICABLE_SYNTHETIC".into()),
        }
    }

    pub fn is_synthetic(&self) -> bool {
        self.quantity_type == Some(QuantityType::SyntheticTestOnly)
    }

    /// Names of missing or invalid attributes (empty when the record is complete).
    pub fn missing_attributes(&self) -> Vec<&'static str> {
        fn blank(s: &Option<String>) -> bool {
            s.as_deref().map(str::trim).is_none_or(str::is_empty)
        }
        let mut m = Vec::new();
        if blank(&self.source) {
            m.push("source");
        }
        match self.evidence_level.as_deref() {
            None => m.push("evidence_level"),
            Some(l) => {
                // Categorical owner decisions and definitions carry no hierarchy level (prereg IN-01..IN-03).
                let ok = match self.quantity_type {
                    Some(QuantityType::SyntheticTestOnly) => l == SYNTHETIC_LABEL,
                    Some(QuantityType::OwnerDecision) => l == "OWNER_DECISION",
                    Some(QuantityType::Definition) => l == "DEFINITION",
                    _ => matches!(l, "1" | "2" | "3" | "4" | "5" | "6" | "7"),
                };
                if !ok {
                    m.push("evidence_level (1..7; OWNER_DECISION / DEFINITION / SYNTHETIC_TEST_ONLY for those types)");
                }
            }
        }
        if self.quantity_type.is_none() {
            m.push("quantity_type");
        }
        if blank(&self.transformation_chain) {
            m.push("transformation_chain");
        }
        if self.uncertainty.is_none() {
            m.push("uncertainty");
        }
        if blank(&self.applicability_domain) {
            m.push("applicability_domain");
        }
        if blank(&self.validation_status) {
            m.push("validation_status");
        }
        m
    }
}

/// A value together with its evidence record.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Registered<T> {
    pub value: T,
    pub evidence: EvidenceRecord,
}

impl<T> Registered<T> {
    pub fn new(value: T, evidence: EvidenceRecord) -> Self {
        Registered { value, evidence }
    }

    pub fn synthetic(value: T, what: &str) -> Self {
        Registered { value, evidence: EvidenceRecord::synthetic(what) }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn synthetic_record_is_complete_and_labelled() {
        let r = EvidenceRecord::synthetic("x");
        assert!(r.missing_attributes().is_empty());
        assert!(r.is_synthetic());
    }

    #[test]
    fn missing_and_invalid_attributes_are_named() {
        let mut r = EvidenceRecord::synthetic("x");
        r.quantity_type = Some(QuantityType::Measured);
        r.source = Some("  ".into());
        r.uncertainty = None;
        let m = r.missing_attributes();
        assert!(m.contains(&"source"));
        assert!(m.contains(&"uncertainty"));
        assert!(m.iter().any(|a| a.starts_with("evidence_level")));
        assert_eq!(UncertaintyRepr::Interval { half_width: 3f64.sqrt() }.standard_uncertainty(), Some(1.0));
    }
}
