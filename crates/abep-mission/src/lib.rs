//! Spacecraft interaction of the ABEP Rust simulator (SC-WP-04): the reference spacecraft drag interface, the F1
//! intake-face drag per design state and the statewise T - D raw record, plus the statewise quantifier. Mission layer
//! (SC-WP-09): [`propagation`] (mission_env state propagation, PARITY-C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION-V1) and
//! [`integration`] (NP-MISSION-INTEGRATION v1, new physics, preregistered).
//!
//! Python references (migration parity, `docs/rust_migration/contracts/`):
//! * `abep_sim/spacecraft_reference_drag.py` -> [`reference_drag`], `statewise_margin` in [`statewise`]
//!   (PARITY-C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY-V1); its record builder -> binary `abep-reference-drag-record`
//!   (PARITY-C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG-V1);
//! * `abep_sim/statewise.py` -> [`statewise`] (PARITY-C-ABEP_SIM_STATEWISE_PY-V1);
//! * `abep_sim/design/architecture_optimizer.py` drag_table / hall_response_status / supplied_objective /
//!   thrust_minus_drag -> [`intake_drag`], [`objective`]; the statewise T - D record -> [`statewise_td`]
//!   (PARITY-C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL-V1).
//!
//! Raw physics carries no requirement threshold and no PASS / FAIL: thrust and drag are computed independently and
//! T - D is a raw difference with its evidence status (A9.24 item 5). Thrust is never constructed here: it exists
//! only from an ADMITTED Hall transport member with a design-specific Hall map, or from a measured H-1 thrust, and the
//! credible set is EMPTY, so every statewise T - D is NOT_EVALUATED. The reference spacecraft drag stays
//! REFERENCE/PARAMETRIC with freeze_status NOT_EVALUATED (S6.18: no host-spacecraft drag ICD). Refusals mirror the
//! reference exception class in the message (`ValueError: ...`), status OUT_OF_DOMAIN.

pub mod intake_drag;
pub mod integration;
pub mod objective;
pub mod parity;
pub mod propagation;
pub(crate) mod pyval;
pub mod reference_drag;
pub mod statewise;
pub mod statewise_td;

pub use pyval::error_class;
