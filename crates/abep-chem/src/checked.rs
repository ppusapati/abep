//! Fail-closed rate evaluation for production consumers (IF-CHEM-REG-v1: abep-chem integrator, abep-icp consumer;
//! NP-ICP-NEUTRALIZER EQ-06 / DOM-01 / DOM-03, NP-ICP-CHEM-AIR IX-04..IX-06, CLAUDE.md next-work 5).
//!
//! The value is the admitted reference integral ([`crate::reference::maxwellian_rate`], bit for bit). What the reference
//! does silently is refused here (contract DIV-03):
//!
//! | condition | status |
//! |---|---|
//! | no `rate_validity.toml` entry, or a malformed one | MODEL_ERROR |
//! | entry `unresolved` | INCOMPLETE_EVIDENCE |
//! | T_e not finite or not > 0 | OUT_OF_DOMAIN |
//! | 3/2 T_e above the entry's `max_mean_energy_eV` (the held tail is only verified below it) | OUT_OF_DOMAIN |
//! | representation empty, of unequal lengths, non-finite, negative, or with decreasing energies | MODEL_ERROR |
//! | T_e so small or large that the integral or its prefactor is not representable | OUT_OF_DOMAIN |
//!
//! The validity limit is a table property; the chemistry-set T_e domain (e.g. DOM-02, 2-30 eV for the N2/N set) and the
//! activity-weighted `chemistry_trustworthy` rule belong to the consumer.

use crate::reference::{self, Tail};
use abep_types::pyjson::float_repr;
use abep_types::{AbepError, AbepResult};

/// A registered cross-section representation: energies [eV] non-decreasing and >= 0, cross sections [m^2] >= 0, all
/// finite, with the table's tail convention.
#[derive(Debug, Clone, PartialEq)]
pub struct CrossSection {
    energies_ev: Vec<f64>,
    sigma_m2: Vec<f64>,
    tail: Tail,
}

fn model(message: String) -> AbepError {
    AbepError::Model { message }
}

impl CrossSection {
    /// Validate a representation; any defect is MODEL_ERROR (an invalid registration, never a default).
    pub fn new(energies_ev: Vec<f64>, sigma_m2: Vec<f64>, tail: Tail) -> AbepResult<Self> {
        if energies_ev.is_empty() {
            return Err(model("cross-section representation is empty".into()));
        }
        if energies_ev.len() != sigma_m2.len() {
            return Err(model(format!(
                "cross-section representation has {} energies and {} cross sections",
                energies_ev.len(),
                sigma_m2.len()
            )));
        }
        for (i, (&e, &s)) in energies_ev.iter().zip(&sigma_m2).enumerate() {
            if !e.is_finite() || !s.is_finite() {
                return Err(model(format!("point {i}: non-finite energy or cross section")));
            }
            if e < 0.0 || s < 0.0 {
                return Err(model(format!("point {i}: negative energy or cross section")));
            }
            if i > 0 && e < energies_ev[i - 1] {
                return Err(model(format!(
                    "point {i}: energies decrease ({} after {})",
                    float_repr(e),
                    float_repr(energies_ev[i - 1])
                )));
            }
        }
        Ok(CrossSection { energies_ev, sigma_m2, tail })
    }

    pub fn energies_ev(&self) -> &[f64] {
        &self.energies_ev
    }

    pub fn sigma_m2(&self) -> &[f64] {
        &self.sigma_m2
    }

    pub fn tail(&self) -> Tail {
        self.tail
    }
}

/// A table's `rate_validity.toml` entry (CLAUDE.md next-work 5).
#[derive(Debug, Clone, PartialEq)]
pub enum Validity {
    /// `status = "verified"`: valid up to this mean electron energy 3/2 T_e [eV].
    Verified { max_mean_energy_ev: f64 },
    /// `status = "unresolved"`: domain not audited.
    Unresolved,
    /// No entry: a driver error, never a default.
    MissingEntry,
}

/// A rate evaluated inside its registered domain.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct RateEvaluation {
    /// Maxwellian rate coefficient [m^3/s].
    pub k_m3_s: f64,
    pub t_e_ev: f64,
    /// 3/2 T_e [eV], the axis of the validity limit and of the HallThruster tables.
    pub mean_energy_ev: f64,
}

/// Check a validity entry and T_e against each other; Ok(mean energy) when the evaluation is admissible.
pub fn admissible(t_e_ev: f64, validity: &Validity) -> AbepResult<f64> {
    let limit = match validity {
        Validity::MissingEntry => return Err(model("no rate_validity.toml entry for this table".into())),
        Validity::Unresolved => {
            return Err(AbepError::IncompleteEvidence {
                message: "rate_validity.toml entry is 'unresolved': the table's domain is not audited".into(),
            })
        }
        Validity::Verified { max_mean_energy_ev } => *max_mean_energy_ev,
    };
    if !(limit.is_finite() && limit > 0.0) {
        return Err(model(format!("verified entry with invalid max_mean_energy_eV {}", float_repr(limit))));
    }
    if !(t_e_ev.is_finite() && t_e_ev > 0.0) {
        return Err(AbepError::OutOfDomain { message: format!("T_e {} eV is not finite and > 0", float_repr(t_e_ev)) });
    }
    let mean = 1.5 * t_e_ev;
    if mean > limit {
        return Err(AbepError::OutOfDomain {
            message: format!(
                "mean electron energy {} eV (T_e {} eV) is above the table's verified limit {} eV",
                float_repr(mean),
                float_repr(t_e_ev),
                float_repr(limit)
            ),
        });
    }
    Ok(mean)
}

/// The Maxwellian rate of `xs` at `t_e_ev`, or the fail-closed status of the table above.
pub fn maxwellian_rate(xs: &CrossSection, t_e_ev: f64, validity: &Validity) -> AbepResult<RateEvaluation> {
    let mean = admissible(t_e_ev, validity)?;
    let k = reference::maxwellian_rate(&xs.energies_ev, &xs.sigma_m2, t_e_ev, xs.tail).map_err(AbepError::from)?;
    if !k.is_finite() {
        return Err(AbepError::OutOfDomain {
            message: format!("T_e {} eV: the integral is not representable ({})", float_repr(t_e_ev), float_repr(k)),
        });
    }
    if k < 0.0 {
        return Err(model(format!("negative rate {} from a non-negative cross section", float_repr(k))));
    }
    Ok(RateEvaluation { k_m3_s: k, t_e_ev, mean_energy_ev: mean })
}

#[cfg(test)]
mod tests {
    use super::*;
    use abep_types::EvalStatus;

    fn step() -> CrossSection {
        CrossSection::new(vec![0.0, 14.99, 15.0, 1000.0], vec![0.0, 0.0, 1e-20, 1e-20], Tail::Hold).unwrap()
    }

    #[test]
    fn inside_the_limit_is_the_reference_value() {
        let v = Validity::Verified { max_mean_energy_ev: 45.0 };
        let r = maxwellian_rate(&step(), 30.0, &v).unwrap();
        let k = reference::maxwellian_rate(step().energies_ev(), step().sigma_m2(), 30.0, Tail::Hold).unwrap();
        assert_eq!(r.k_m3_s.to_bits(), k.to_bits());
        assert_eq!(r.mean_energy_ev, 45.0);
    }

    #[test]
    fn refusals_carry_the_registered_statuses() {
        let v = Validity::Verified { max_mean_energy_ev: 45.0 };
        let st = |r: AbepResult<RateEvaluation>| r.unwrap_err().status();
        assert_eq!(st(maxwellian_rate(&step(), 30.0f64.next_up(), &v)), EvalStatus::OutOfDomain);
        assert_eq!(st(maxwellian_rate(&step(), 3.0, &Validity::MissingEntry)), EvalStatus::ModelError);
        assert_eq!(st(maxwellian_rate(&step(), 3.0, &Validity::Unresolved)), EvalStatus::IncompleteEvidence);
        for te in [0.0, -1.0, f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            assert_eq!(st(maxwellian_rate(&step(), te, &v)), EvalStatus::OutOfDomain, "T_e {te}");
        }
        assert_eq!(st(maxwellian_rate(&step(), 1e-200, &v)), EvalStatus::OutOfDomain);
        assert_eq!(st(maxwellian_rate(&step(), 1e-186, &v)), EvalStatus::OutOfDomain);
        let bad = Validity::Verified { max_mean_energy_ev: f64::NAN };
        assert_eq!(st(maxwellian_rate(&step(), 3.0, &bad)), EvalStatus::ModelError);
    }

    #[test]
    fn invalid_representations_are_model_errors() {
        let cases: [(Vec<f64>, Vec<f64>); 6] = [
            (vec![], vec![]),
            (vec![1.0, 2.0], vec![1e-20]),
            (vec![1.0, f64::NAN], vec![1e-20, 1e-20]),
            (vec![1.0, 2.0], vec![1e-20, f64::INFINITY]),
            (vec![-1.0, 2.0], vec![1e-20, 1e-20]),
            (vec![2.0, 1.0], vec![1e-20, 1e-20]),
        ];
        for (e, s) in cases {
            assert_eq!(CrossSection::new(e, s, Tail::Zero).unwrap_err().status(), EvalStatus::ModelError);
        }
        assert_eq!(
            CrossSection::new(vec![1.0, 2.0], vec![1e-20, -1e-21], Tail::Zero).unwrap_err().status(),
            EvalStatus::ModelError
        );
        assert!(CrossSection::new(vec![10.0, 10.0, 20.0], vec![0.0, 1e-20, 1e-20], Tail::Hold).is_ok());
    }
}
