#![allow(dead_code)]
//! Shared helpers of the abep-icp verification tests.

use abep_icp::IcpModel;
use std::sync::OnceLock;

/// The lock-verified model context, loaded once per test binary.
pub fn model() -> &'static IcpModel {
    static M: OnceLock<IcpModel> = OnceLock::new();
    M.get_or_init(|| IcpModel::load_workspace().expect("the frozen preregistration and its pinned data verify"))
}

pub fn rel(a: f64, b: f64) -> f64 {
    if a == b {
        0.0
    } else {
        (a - b).abs() / a.abs().max(b.abs())
    }
}

pub fn val(q: &abep_icp::Quantity) -> f64 {
    assert!(q.status.is_converged(), "not converged: {q:?}");
    q.value.unwrap_or_else(|| panic!("null value: {q:?}"))
}
