//! Materials and atomic-oxygen kernels of the materials / life layer (SC-WP-08; programme_v3_1
//! `abep-subsystems::materials`), ported under preregistered parity contracts (`docs/rust_migration/contracts/`):
//!
//! * [`db`]: the materials property DB and its closed-form priors (C-ABEP_SIM_MATERIALS_PY).
//! * [`aochem`]: ram AO flux / fluence, Kapton-referenced erosion depth, wall recombination O -> O2
//!   (C-ABEP_SIM_AOCHEM_PY).
//! * [`sputter`]: the cited Yamamura-Tawara and APID yield formulas (C-DOCS_EVIDENCE_SPUTTER_YIELDS_V1-YIELD_KERNELS).
//! * [`pymath`]: the CPython float semantics the kernels reproduce.
//!
//! Every property value is a literature-class prior; nothing here is evidence, a life verdict or a threshold.

pub mod aochem;
pub mod db;
pub mod pymath;
pub mod sputter;
