//! NP-MISSION-INTEGRATION v1 (model version 1.0.0): mission integration of the selected architecture
//! `hall_icp_neutralizer` over `mission_scenario_v2` and the frozen 196-state environment, for AIR_PRIMARY and
//! XE_CONTINGENCY (`docs/rust_migration/new_physics/NP-MISSION-INTEGRATION/prereg_v1.json`, sha256 in
//! [`PREREG_SHA256`]; addendum 01).
//!
//! * [`model::integrate`] (IF-MIS-v1) assembles the per-state record from typed layer inputs, propagates fail-closed
//!   statuses, forms statewise envelopes and the PB-AO parametric bound, and integrates per-state rates over a
//!   registered schedule with exact time and propellant accounting ([`exact`]). It reads no file.
//! * [`today::run_admitted`] (IF-MIS-DECISIVE) builds those inputs from today's admitted layers and calls it: the hook
//!   of the decisive 196-state architecture run (A9.31 sec. 16).
//!
//! Raw bookkeeping only: no requirement threshold, margin or verdict; M_n is formed by assessment. A NOT_EVALUATED input
//! never becomes a number; a parametric result lives in its own layer. Every output carries
//! `validation_status = NOT_VALIDATED`.

pub mod exact;
pub mod model;
pub mod quantity;
pub mod testkit;
pub mod today;

pub use model::{integrate, MissionInputs, MissionRecord, Mode};
pub use quantity::{Field, Quantity, Reason};

pub const MODEL_ID: &str = "NP-MISSION-INTEGRATION";
pub const MODEL_VERSION: &str = "1.0.0";
pub const ARCHITECTURE: &str = "hall_icp_neutralizer";
pub const PREREG_REL: &str = "docs/rust_migration/new_physics/NP-MISSION-INTEGRATION/prereg_v1.json";
pub const PREREG_SHA256: &str = "9d3a72022ecb236f71a30ead5c31023d166a31e05f6a4f4579c589f62a5d4f79";
pub const PREREG_MD_REL: &str = "docs/rust_migration/new_physics/NP-MISSION-INTEGRATION/PREREG.md";
pub const PREREG_MD_SHA256: &str = "c1fbc1b963aa393aef6f7e0f2d8d061682e7091aec2bcb59e8f38d8ffcbf66cc";
pub const ADDENDUM_01_REL: &str = "docs/rust_migration/new_physics/NP-MISSION-INTEGRATION/addendum_01_ft10_scope.json";
pub const ADDENDUM_01_SHA256: &str = "6d8d9ddd6cdf9f87eedf9dc50020dc686b13a70ca11ca655c5ee480f8e447a12";
