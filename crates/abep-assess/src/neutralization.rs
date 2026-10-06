//! Neutralization assessment: the P1-IT-29 margin arithmetic (`p1_reducer.icp45a_margin`, contract E15) and the HC-05
//! evaluator of acceptance ACCEPT-NI-ABEP-ASSESS-RFP-MATRIX-V1 (rules H-01..H-07).
//!
//! A9.29 sec. 4: M_n = I_e,cap / I_d,max,H1 - 1 is formed here only, never in raw RF/ICP physics. A9.31 sec. 10: a
//! model-derived I_e,cap that is VERIFIED but not bench-validated does not satisfy HC-05 (NOT_EVALUATED outside a
//! VALIDATED_BENCH domain cell containing the point); a measured I_e,cap supersedes the model at the measured point.
//! OQ-NPICP-03: no Hall-parameter / gyroradius threshold is invented; a raw INCOMPLETE_EVIDENCE capacity is propagated.

use crate::error::AssessResult;
use crate::gates::{C_MET, C_NOT_EVALUATED, C_VIOLATED};
use crate::py::{dict, s};
use crate::thresholds::Thresholds;
use abep_icp::result::HallRecord;
use abep_icp::status::IcpStatus;
use abep_mission::objective::EVALUATED;
use abep_types::pyjson::Value;

/// One-sided alpha of the margin gate (P1-IT-29; A9.1 UBQ-02 / UBQ-07).
pub const MARGIN_ALPHA_ONE_SIDED: f64 = 0.05;
/// Phi^-1(1 - 0.05), the standard normal one-sided quantile; a registered k may not be smaller.
pub const MARGIN_K_MIN: f64 = 1.6448536269514722;
/// A k quoted to 4-5 significant figures (1.6449 / 1.64485) is the same quantile.
pub const MARGIN_K_ROUNDING_TOL: f64 = 5e-5;

/// `icp45a_margin(i_e_cap_A, idm, k, ue, ud)`: M_n, u_M_n and M_n_lower = M_n - k u_M_n.
pub fn icp45a_margin(i_e_cap_a: f64, idm: f64, k: f64, ue: f64, ud: f64) -> (f64, f64, f64) {
    // `x ** 2` of the reference is libm pow (not x * x): py_pow keeps the exponent opaque
    let sq = |x: f64| abep_atmos::pyfloat::py_pow(x, 2.0);
    let m_n = i_e_cap_a / idm - 1.0;
    let u_m = (sq(ue / idm) + sq(i_e_cap_a * ud / sq(idm))).sqrt();
    (m_n, u_m, m_n - k * u_m)
}

pub fn icp45a_margin_value(i: f64, idm: f64, k: f64, ue: f64, ud: f64) -> Value {
    let (m, u, lo) = icp45a_margin(i, idm, k, ue, ud);
    dict(vec![("M_n", Value::Float(m)), ("u_M_n", Value::Float(u)), ("M_n_lower", Value::Float(lo))])
}

/// Basis of the electron-current capacity.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CapacityBasis {
    /// NP-ICP-NEUTRALIZER model output (needs a VALIDATED_BENCH cell containing the point).
    Model,
    /// A registered measured I_e,cap at the evaluated point (supersedes the model there).
    Measured,
    /// Synthetic test data: never evidence.
    Synthetic,
}

/// A current with its standard uncertainty and raw status.
#[derive(Debug, Clone, PartialEq)]
pub struct Current {
    pub value_a: Option<f64>,
    pub u_a: Option<f64>,
    pub status: IcpStatus,
    pub reasons: Vec<String>,
}

/// The validation domain cell (NP-ICP prereg VC-04) that would contain the evaluated point.
#[derive(Debug, Clone, PartialEq)]
pub struct ValidationCell {
    pub cell_id: String,
    pub status: String,
    pub contains_point: bool,
}

/// The registered one-sided margin rule (P1-IT-29).
#[derive(Debug, Clone, PartialEq)]
pub struct MarginRule {
    pub k_one_sided: f64,
    pub alpha_one_sided: f64,
    pub k_basis: String,
}

/// Inputs of HC-05 at one registered point.
#[derive(Debug, Clone, PartialEq)]
pub struct NeutralizationInputs {
    pub point_id: Option<String>,
    pub capacity_basis: CapacityBasis,
    pub i_e_cap: Current,
    /// I_d,max,H1: None when not registered.
    pub i_d_max_h1: Option<Current>,
    pub validation_cell: Option<ValidationCell>,
    pub margin_rule: Option<MarginRule>,
}

impl NeutralizationInputs {
    /// From an IF-ICP-HALL-v1 record (raw I_e,cap and I_d,max,H1; the record's validation_status is the cell status
    /// unless a registered cell is supplied).
    pub fn from_hall_record(
        r: &HallRecord,
        basis: CapacityBasis,
        u_i_e_a: Option<f64>,
        u_i_d_a: Option<f64>,
        cell: Option<ValidationCell>,
        rule: Option<MarginRule>,
    ) -> Self {
        let id = if r.i_d_max_h1_a.status.is_converged() && r.i_d_max_h1_a.value.is_some() {
            Some(Current {
                value_a: r.i_d_max_h1_a.value,
                u_a: u_i_d_a,
                status: r.i_d_max_h1_a.status,
                reasons: r.i_d_max_h1_a.reasons.clone(),
            })
        } else {
            None
        };
        NeutralizationInputs {
            point_id: r.h1_point_id.clone(),
            capacity_basis: basis,
            i_e_cap: Current {
                value_a: r.i_e_cap_a.value,
                u_a: u_i_e_a,
                status: r.i_e_cap_a.status,
                reasons: r.i_e_cap_a.reasons.clone(),
            },
            i_d_max_h1: id,
            validation_cell: cell.or(Some(ValidationCell {
                cell_id: "IF-ICP-HALL-v1 record".into(),
                status: r.validation_status.clone(),
                contains_point: false,
            })),
            margin_rule: rule,
        }
    }
}

fn verdict(
    status: &str,
    value_status: Value,
    code: &str,
    reason: &str,
    quantities: Option<(f64, f64, f64)>,
    limit: Option<f64>,
) -> Value {
    let q = |i: usize| quantities.map_or(Value::Null, |t| Value::Float([t.0, t.1, t.2][i]));
    dict(vec![
        ("gate", s("HC-05")),
        (
            "rule",
            s("M_n,LB > HC-05 threshold (config/assessment/gate_thresholds_v1.json), M_n = I_e,cap / I_d,max,H1 - 1"),
        ),
        ("status", s(status)),
        ("value_status", value_status),
        ("reason_code", s(code)),
        ("reason", s(reason)),
        ("M_n", q(0)),
        ("u_M_n", q(1)),
        ("M_n_LB", q(2)),
        ("threshold", limit.map_or(Value::Null, Value::Float)),
        ("authority", s("A9.24 item 5; A9.29 sec. 4; A9.31 sec. 10; P1-IT-29")),
    ])
}

/// HC-05 by the registered rule order H-01..H-07. The point difference and the point M_n never decide.
pub fn hc05(t: &Thresholds, inputs: Option<&NeutralizationInputs>) -> AssessResult<Value> {
    let limit = t.limit("HC-05");
    let ne = |code: &str, reason: &str| verdict(C_NOT_EVALUATED, Value::Null, code, reason, None, limit);
    let Some(x) = inputs else {
        return Ok(ne("NO_NEUTRALIZATION_RECORD", "no IF-ICP-HALL-v1 record at a registered point (H-01)"));
    };
    if x.capacity_basis == CapacityBasis::Synthetic {
        return Ok(ne("SYNTHETIC_NOT_EVIDENCE", "synthetic test data is never evidence (H-02)"));
    }
    let id =
        match &x.i_d_max_h1 {
            Some(c) if c.status.is_converged() && c.value_a.is_some_and(|v| v.is_finite() && v > 0.0) => c,
            _ => return Ok(ne(
                "I_D_MAX_H1_NOT_REGISTERED",
                "I_d,max,H1 not registered / not evaluated (admitted Hall member or measured H-1 registration needed; \
                 H-03)",
            )),
        };
    let ie = &x.i_e_cap;
    if !ie.status.is_converged() || ie.value_a.is_none() {
        let st = if ie.status.is_converged() { IcpStatus::NotEvaluated } else { ie.status };
        return Ok(verdict(
            st.as_str(),
            Value::Null,
            "I_E_CAP_NOT_EVALUATED",
            &format!("raw I_e,cap status {} propagated (H-04): {}", st.as_str(), ie.reasons.join(", ")),
            None,
            limit,
        ));
    }
    if x.capacity_basis == CapacityBasis::Model {
        let validated = x.validation_cell.as_ref().is_some_and(|c| c.status == "VALIDATED_BENCH" && c.contains_point);
        if !validated {
            return Ok(ne(
                "MODEL_NOT_VALIDATED_IN_DOMAIN",
                "A9.31 sec. 10: a model-derived I_e,cap is not enough; NOT_EVALUATED outside a VALIDATED_BENCH domain \
                 cell containing the point (H-05)",
            ));
        }
    }
    let rule_ok = match &x.margin_rule {
        Some(r) => {
            r.alpha_one_sided == MARGIN_ALPHA_ONE_SIDED
                && r.k_one_sided.is_finite()
                && r.k_one_sided >= MARGIN_K_MIN - MARGIN_K_ROUNDING_TOL
                && !r.k_basis.trim().is_empty()
        }
        None => false,
    };
    let pos = |u: Option<f64>| u.is_some_and(|v| v.is_finite() && v > 0.0);
    if !rule_ok || !pos(ie.u_a) || !pos(id.u_a) {
        return Ok(ne(
            "MARGIN_RULE_NOT_ADMISSIBLE",
            "the registered one-sided margin rule (alpha 0.05, k >= 1.6449, k basis) and both standard \
             uncertainties > 0 are required (P1-IT-29; H-06)",
        ));
    }
    let Some(limit_v) = limit else {
        return Ok(ne("THRESHOLD_TBD", "HC-05 threshold not registered"));
    };
    let r = x.margin_rule.as_ref().expect("checked");
    let q = icp45a_margin(
        ie.value_a.expect("checked"),
        id.value_a.expect("checked"),
        r.k_one_sided,
        ie.u_a.expect("checked"),
        id.u_a.expect("checked"),
    );
    let st = if q.2 > limit_v { C_MET } else { C_VIOLATED };
    Ok(verdict(
        st,
        s(EVALUATED),
        "EVALUATED",
        if x.capacity_basis == CapacityBasis::Measured {
            "measured I_e,cap at the point (supersedes the model); one-sided lower bound M_n,LB (H-07)"
        } else {
            "model I_e,cap inside a VALIDATED_BENCH cell containing the point; one-sided lower bound M_n,LB (H-07)"
        },
        Some(q),
        limit,
    ))
}

/// A9.31 sec. 18 Q3: I_d, I_e,cap and the point M_n as raw / model quantities where legitimately available; never a
/// gate verdict.
pub fn neutralization_quantities(inputs: Option<&NeutralizationInputs>) -> Value {
    let cur = |c: Option<&Current>| match c {
        Some(c) if c.status.is_converged() && c.value_a.is_some() => {
            dict(vec![("value_A", Value::Float(c.value_a.unwrap())), ("status", s(EVALUATED))])
        }
        Some(c) => dict(vec![("value_A", Value::Null), ("status", s(c.status.as_str()))]),
        None => dict(vec![("value_A", Value::Null), ("status", s(C_NOT_EVALUATED))]),
    };
    let ie = inputs.map(|x| &x.i_e_cap);
    let id = inputs.and_then(|x| x.i_d_max_h1.as_ref());
    let m_n = match (ie, id) {
        (Some(a), Some(b)) if a.status.is_converged() && b.status.is_converged() => match (a.value_a, b.value_a) {
            (Some(i), Some(d)) if d > 0.0 => Value::Float(i / d - 1.0),
            _ => Value::Null,
        },
        _ => Value::Null,
    };
    dict(vec![
        ("I_d_max_H1", cur(id)),
        ("I_e_cap", cur(ie)),
        ("M_n_point", m_n),
        ("M_n_point_role", s("MODEL_QUANTITY_NOT_A_GATE (A9.31 sec. 18 Q3; HC-05 uses M_n,LB only)")),
    ])
}
