//! Active F7 design synthesis of the ABEP Rust simulator (SC-WP-10; selected architecture `hall_icp_neutralizer`).
//!
//! Python references (migration parity, `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY/`):
//! `abep_sim/design/architecture_optimizer.py` (upstream contexts, Pareto machinery) and the design part of
//! `abep_sim/programme/design_synthesis.py`. Already admitted functions are reused, never duplicated: the gas path
//! (abep-gaspath steady sweep), intake drag / supplied objectives / T - D (abep-mission), wet mass and the official
//! ledger (abep-subsystems). Every upstream number is PARAMETRIC_SENSITIVITY; no status is PASS / SELECTED / WINNER;
//! the system objectives (T - D, P_bus, m_wet, Q_reject, I_e margin, life) stay NOT_EVALUATED until their
//! determining evidence exists. Layer rule: design never depends on the assessment or evidence crates.
#![allow(clippy::too_many_arguments, clippy::type_complexity, clippy::needless_range_loop)]

pub mod err;
pub mod f1view;
pub mod inputs;
pub mod optimizer;
pub mod pv;
pub mod records;
pub mod synthesis;
