//! Environment physics of the ABEP Rust simulator (SC-WP-01; A9.29 sec. 6, RM-OQ-02).
//!
//! Production reads only the frozen, hash-pinned datasets (`abep-data`): the orbit-averaged NRLMSIS 2.1 scenario
//! table (`msis21`), the orbit-resolved NRLMSIS 2.1 grid (`orbit`), the HWM14 orbit winds (`wind`) and the frozen
//! 196-state design-state set (`design_state_set`, `execution`). There is no live NRLMSIS / HWM14 evaluation and no
//! Fortran FFI; a later regeneration is a separately governed native tool.
//!
//! Parity contracts: docs/rust_migration/contracts/{C-ABEP_SIM_ATMOSPHERE_PY, C-ABEP_SIM_MISSION_ENV_PY-CONSTANTS_KERNEL,
//! C-ABEP_SIM_ATMOSPHERE_ORBIT_PY}/parity_prereg_v1.json.

pub mod design_state_set;
pub mod design_states;
pub mod execution;
pub mod mission_env_kernel;
pub mod msis21;
pub mod orbit;
pub mod pyfloat;
pub mod weights;
pub mod wind;
