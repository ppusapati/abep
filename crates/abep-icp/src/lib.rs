//! NP-ICP-NEUTRALIZER v1: predictive steady-state 0-D model of the downstream 13.56 MHz RF/ICP electron source /
//! neutralizer of `hall_icp_neutralizer` (A9.29 sec. 4; SC-WP-03; lane C).
//!
//! Method NEW_PHYSICS: preregistered model -> Rust -> analytic / independent-evidence verification -> admission. The
//! binding contract is `docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_v1.json` (lock-verified on load),
//! with addendum 01 (A9.30), addendum 02 and the chemistry contract NP-ICP-CHEM-AIR v1, whose IF-CHEM-REG-v1 registry
//! (`data/chemistry/icp/`) and admitted rate integrator come from abep-chem. No Python reference exists or is used;
//! nothing is taken from `abep_sim/plasma_chem.py` (EX-01).
//!
//! What is evaluable today: configuration CFG-CAP-OFF in coupling mode CM-ABS (absorbed power as input), CM-CAL at a
//! registered P2 map point, every status path, the conservation checks and the analytic limiting cases. CM-PRED is a
//! status gate only (VER-03..05, VER-13). CFG-FLIGHT-HALL-ON is a NOT_EVALUATED contract. Every real-gas mode fails
//! closed until its chemistry, geometry and evidence are registered.
//!
//! Raw outputs never contain a requirement threshold, a margin verdict or a compliance label (EX-05); M_n and the gate
//! that uses it live in assessment.

pub mod case;
pub mod chemistry;
pub mod constants;
pub mod context;
pub mod coupling;
pub mod crosscheck;
pub mod evaluate;
pub mod evidence;
pub mod geometry;
pub mod physics;
pub mod result;
pub mod solver;
pub mod status;
pub mod testkit;
pub mod v2;

pub use case::IcpCase;
pub use context::IcpModel;
pub use result::IcpResult;
pub use status::{IcpStatus, Quantity, Reason};
