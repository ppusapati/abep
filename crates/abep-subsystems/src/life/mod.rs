//! Materials / life layer of the selected architecture (SC-WP-08; programme_v3_1 `abep-subsystems::life`), ported
//! under preregistered parity contracts (`docs/rust_migration/contracts/`):
//!
//! * [`ao_register`]: the external ram AO environment from the frozen NRLMSIS 2.1 table and the lane-32 sputter-yield
//!   index (C-DOCS_EXPERIMENTS_LIFETIME_AO-AO_REGISTER_KERNELS).
//! * [`p4`]: the fail-closed P4 anode / collector gate kernels; the material stays OPEN
//!   (C-DOCS_EXPERIMENTS_HALL_ICP_P4_ANODE_MATERIALS-SCREENING_KERNELS).
//! * [`indicators`]: the life / material indicator set, no indicator EVALUATED as life
//!   (C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-LIFE_MATERIAL_KERNEL).
//! * [`hall_wall`]: the Hall-map wall-flux gate; with the credible Hall set EMPTY every Hall-erosion-derived life is
//!   NOT_EVALUATED (C-ABEP_SIM_THERMAL_LIFE_PY-HALLMAP_WALL_INPUTS).
//! * [`eval`]: the JSON call interface of the parity harness (`examples/life_eval.rs`).
//!
//! Raw quantities only: the 15,000 h firing and 26,280 h mission bases and the HC gates are assessment (SC-WP-11).
//! C1 / hollow-cathode life is GROUND_REFERENCE_ONLY and never part of flight life. Not ported (audits in
//! `docs/rust_migration/audits/SC-WP-08/`): K-GAS-LIFE and the class-H reliability / magnet / compressor life
//! functions; reliability is the preregistered new-physics item NP-RELIABILITY (not implemented here).

pub mod ao_register;
pub mod eval;
pub mod hall_wall;
pub mod indicators;
pub mod p4;
