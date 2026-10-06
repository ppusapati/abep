//! Hall response status and the governed Hall-performance gate.
//!
//! `hall_response_status` ports abep_sim/design/architecture_optimizer.py::hall_response_status (admitted members, the
//! credible-set state and the P5-N2 v1 decision, read only). `HallGate` is the Rust gate every output needing Hall
//! performance passes through: while the credible transport set is EMPTY it is NOT_EVALUATED with the reason
//! "credible Hall transport set EMPTY" (simulation_completion_programme_v1_1.json hall_physics_boundary; A9.29 sec. 9).
//! It is not a parity observable and never a PASS.

use crate::ensemble;
use crate::error::HallResult;
use crate::py::{self, PyValue};
use abep_types::{AbepError, AbepResult, EvalStatus};

pub const ENS_REL: &str = "hallthruster_bridge/ensemble/transport_ensemble_v0.json";
pub const VAL_REL: &str = "hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json";
pub const CREDIBLE_SET_EMPTY_REASON: &str = "credible Hall transport set EMPTY";

fn read_json(repo: &str, rel: &str) -> HallResult<PyValue> {
    let p = py::join(repo, rel);
    std::fs::metadata(&p).map_err(|e| py::os_error(&e, &p))?;
    py::load_json_file(&p)
}

/// `hall_response_status(repo)`: {admitted_members, credible_set, p5_n2_v1_decision, sources}.
pub fn hall_response_status(repo: &str) -> HallResult<PyValue> {
    let ens = read_json(repo, ENS_REL)?;
    let members = PyValue::List(py::iterate(&py::get(&ens, "members")?.cloned().unwrap_or(PyValue::List(Vec::new())))?);
    let decision = match read_json(repo, VAL_REL) {
        Ok(val) => py::get(&val, "decision")?.cloned().unwrap_or(PyValue::None),
        Err(e) if e.kind == crate::error::Kind::FileNotFound => PyValue::None,
        Err(e) => return Err(e),
    };
    let state = if members.truthy() { "NON_EMPTY" } else { "EMPTY" };
    Ok(py::dict([
        ("admitted_members", members),
        ("credible_set", py::s(state)),
        ("p5_n2_v1_decision", decision),
        ("sources", py::list_of_strs(&[ENS_REL, VAL_REL])),
    ]))
}

/// A value that needs Hall performance, with its fail-closed status.
#[derive(Debug, Clone, PartialEq)]
pub struct Gated<T> {
    pub status: EvalStatus,
    pub reason: Option<String>,
    pub value: Option<T>,
}

/// The credible-set gate, built from the validated repository ensemble.
#[derive(Debug, Clone, PartialEq)]
pub struct HallGate {
    /// NOT_EVALUATED while no member is admitted; EVALUATED means only that the gate does not block (each map's own
    /// trust rules still apply).
    pub status: EvalStatus,
    pub reason: Option<String>,
    pub admitted_members: Vec<String>,
}

impl HallGate {
    /// Gate of the repository at `repo`: load_ensemble (validated, admission and O4 evidence re-checked); an invalid
    /// ensemble is MODEL_ERROR, never an empty-but-open gate.
    pub fn from_repository(repo: &str) -> AbepResult<Self> {
        let e = ensemble::load_ensemble(repo, None).map_err(AbepError::from)?;
        Self::from_ensemble(&e)
    }

    pub fn from_ensemble(e: &PyValue) -> AbepResult<Self> {
        let ids = ensemble::member_ids(e).map_err(AbepError::from)?;
        let mut admitted: Vec<String> = ids.iter().map(py::py_str).collect();
        admitted.sort();
        Ok(if admitted.is_empty() {
            HallGate {
                status: EvalStatus::NotEvaluated,
                reason: Some(CREDIBLE_SET_EMPTY_REASON.into()),
                admitted_members: admitted,
            }
        } else {
            HallGate { status: EvalStatus::Evaluated, reason: None, admitted_members: admitted }
        })
    }

    /// Run `f` only when the gate is open; otherwise the gate's status and reason, with no value.
    pub fn gate<T>(&self, f: impl FnOnce() -> T) -> Gated<T> {
        if self.status.is_evaluated() {
            Gated { status: EvalStatus::Evaluated, reason: None, value: Some(f()) }
        } else {
            Gated { status: self.status, reason: self.reason.clone(), value: None }
        }
    }
}
