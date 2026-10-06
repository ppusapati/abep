//! Statewise T - D raw record over the required design states (SC-WP-04; contract
//! PARITY-C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL-V1, statewise_t_minus_d_definition).
//!
//! For a design point of the F1 design space and every required state of the frozen design-state set v2: the F1
//! intake-face drag D_intake(state) = A * drag_table D/A (PARAMETRIC_SENSITIVITY_ONLY), the host-spacecraft body drag
//! (NOT_EVALUATED: no drag ICD, F1-ID-08 / S6.18), the thrust (NOT_EVALUATED) and T - D through the admitted
//! [`thrust_minus_drag`] objective. Thrust is never constructed here: it exists only from an ADMITTED Hall transport
//! member with a design-specific Hall map, or from a measured H-1 thrust record, and neither is registered. The record
//! carries raw quantities with statuses only; it compares nothing with zero or with a requirement (HC-08, SC-WP-11).

use crate::intake_drag::{DragTable, INTAKE_DRAG_LABEL, INTAKE_DRAG_STATUS};
use crate::objective::{eval_status, thrust_minus_drag, HallResponseStatus, ENS_REL};
use abep_atmos::pyfloat::py_format_g;
use abep_types::pyjson::Value;
use abep_types::{AbepError, AbepResult, EvalStatus};

/// Reason keys of the fail-closed terms.
pub const CREDIBLE_HALL_TRANSPORT_SET_EMPTY: &str = "CREDIBLE_HALL_TRANSPORT_SET_EMPTY";
pub const HALL_MAP_NOT_REGISTERED: &str = "HALL_MAP_NOT_REGISTERED";
pub const HOST_SPACECRAFT_DRAG_ICD_ABSENT: &str = "HOST_SPACECRAFT_DRAG_ICD_ABSENT";

/// One point of the F1 design space (frontal area, channel aspect ratio, open fraction) under one surface scenario.
#[derive(Debug, Clone, PartialEq)]
pub struct DesignPoint {
    pub area_m2: f64,
    pub l_over_d: f64,
    pub phi: f64,
    /// `<scattering>_a<alpha:g>` (a TBD context axis, never chosen)
    pub scenario: String,
}

/// A term that is not evaluated, with its reason.
#[derive(Debug, Clone, PartialEq)]
pub struct NotEvaluatedTerm {
    pub status: EvalStatus,
    pub reason_key: &'static str,
    pub reason: String,
}

/// The F1 intake-face drag at one state.
#[derive(Debug, Clone, PartialEq)]
pub struct IntakeDragTerm {
    pub value_n: f64,
    pub se_n: f64,
    pub status: EvalStatus,
    pub label: &'static str,
    pub source: String,
}

/// One state of the record.
#[derive(Debug, Clone, PartialEq)]
pub struct StateTMinusD {
    pub state_id: String,
    pub thrust: NotEvaluatedTerm,
    pub drag_intake: IntakeDragTerm,
    pub drag_body: NotEvaluatedTerm,
    /// EvalStatus of T - D (from the objective status)
    pub t_minus_d_status: EvalStatus,
    /// the thrust_minus_drag objective record (reference shape)
    pub objective: Value,
}

/// The statewise record of one design point.
#[derive(Debug, Clone, PartialEq)]
pub struct StatewiseTMinusD {
    pub design_point: DesignPoint,
    pub credible_set: &'static str,
    pub n_states: usize,
    pub n_t_minus_d_evaluated: usize,
    pub states: Vec<StateTMinusD>,
}

/// The intake-drag record source text (registered in the contract).
pub fn intake_record_source(p: &DesignPoint, state_id: &str) -> String {
    format!(
        "F1 intake-face drag (drag_table) scenario {} L/d {} phi {} A {} m^2 state {state_id}",
        p.scenario,
        py_format_g(p.l_over_d),
        py_format_g(p.phi),
        py_format_g(p.area_m2)
    )
}

fn thrust_term(hall: &HallResponseStatus) -> NotEvaluatedTerm {
    if hall.admitted_members.is_empty() {
        NotEvaluatedTerm {
            status: EvalStatus::NotEvaluated,
            reason_key: CREDIBLE_HALL_TRANSPORT_SET_EMPTY,
            reason: format!("credible Hall transport set EMPTY ({ENS_REL} members = [])"),
        }
    } else {
        NotEvaluatedTerm {
            status: EvalStatus::NotEvaluated,
            reason_key: HALL_MAP_NOT_REGISTERED,
            reason: "no design-specific Hall map of an admitted transport member is registered for this design".into(),
        }
    }
}

/// Evaluate the statewise record of `point` over `state_ids` (the required states, in order).
pub fn statewise_t_minus_d(
    table: &DragTable,
    hall: &HallResponseStatus,
    point: &DesignPoint,
    state_ids: &[String],
) -> AbepResult<StatewiseTMinusD> {
    if state_ids.is_empty() {
        return Err(AbepError::Model { message: "statewise T - D needs the required state set (empty)".into() });
    }
    let mut states = Vec::with_capacity(state_ids.len());
    for sid in state_ids {
        let e = table.get(&point.scenario, point.l_over_d, point.phi, sid).ok_or_else(|| AbepError::OutOfDomain {
            message: format!(
                "design point {} L/d {} phi {} at state {sid} is not in the F1 drag table",
                point.scenario, point.l_over_d, point.phi
            ),
        })?;
        let value_n = point.area_m2 * e.drag_per_area_n_m2;
        let source = intake_record_source(point, sid);
        let record = abep_types::pydict! {
            "value" => value_n,
            "evidence_class" => "model-derived",
            "source" => source.as_str(),
            "parametric" => true,
        };
        let objective = thrust_minus_drag(&Value::Null, &Value::Null, &Value::Null, &Value::Null, hall, &record)?;
        let status = objective.as_dict().and_then(|d| d.get("status")).and_then(Value::as_str).unwrap_or_default();
        states.push(StateTMinusD {
            state_id: sid.clone(),
            thrust: thrust_term(hall),
            drag_intake: IntakeDragTerm {
                value_n,
                se_n: point.area_m2 * e.drag_se_per_area_n_m2,
                status: INTAKE_DRAG_STATUS,
                label: INTAKE_DRAG_LABEL,
                source,
            },
            drag_body: NotEvaluatedTerm {
                status: EvalStatus::NotEvaluated,
                reason_key: HOST_SPACECRAFT_DRAG_ICD_ABSENT,
                reason: "host-spacecraft drag ICD absent (F1-ID-08; S6.18: the REFERENCE/PARAMETRIC spacecraft drag \
                         never closes D_spacecraft)"
                    .into(),
            },
            t_minus_d_status: eval_status(status),
            objective,
        });
    }
    let n_eval = states.iter().filter(|s| s.t_minus_d_status.is_evaluated()).count();
    Ok(StatewiseTMinusD {
        design_point: point.clone(),
        credible_set: hall.credible_set(),
        n_states: states.len(),
        n_t_minus_d_evaluated: n_eval,
        states,
    })
}
