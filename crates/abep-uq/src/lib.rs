//! Active F8 robust optimisation / UQ of the ABEP Rust simulator (SC-WP-10; `abep_sim/design/robust_optimizer.py`,
//! contract `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY/`).
//!
//! Uncertainty treatment (reference UQ_AXES): the atmosphere / design states, the surface accommodation and kernel and
//! the wall recombination are SCENARIO SETS (counts and worst cases only, no invented weights); the TPMC statistics are
//! the only quantified uncertainty (seeded Monte Carlo on the registered numpy stream, EXACT_STREAM); pointing is a
//! deterministic node; the compressor coefficients get local elasticities; feed state, Hall response, RF efficiency
//! and thermal parameters are NOT_EVALUATED. The robust set may be EMPTY: that is a valid output, and nothing here
//! retunes an input to make a member appear (A9.31 secs. 12, 21). uq6 / uq_modular / mission_uq are not ported.
#![allow(clippy::too_many_arguments, clippy::type_complexity, clippy::needless_range_loop)]

pub mod axes;
pub mod interp_sensitivity;
pub mod mc;
pub mod robust;
pub mod sens;
pub mod study;
