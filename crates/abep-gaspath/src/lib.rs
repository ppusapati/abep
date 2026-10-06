//! Upstream gas path of the ABEP Rust simulator (SC-WP-02, ES-3): the AIR_PRIMARY chain intake IF-A1 record -> F2
//! filter -> F3 molecular-drag compressor -> F4 plenum / feed -> H-1 inlet, plus the A9.13 setpoint / domain rules.
//!
//! Ported from the Python reference under three preregistered parity contracts
//! (`docs/rust_migration/contracts/{C-ABEP_SIM_DESIGN_FILTER_STAGE_PY, C-ABEP_SIM_COMPRESSOR_PY,
//! C-ABEP_SIM_DESIGN_PLENUM_FEED_PY}/parity_prereg_v1.json`). Intake outputs (F1 IF-A1 records) and the materials
//! database enter as explicit plain data; nothing here reads the RFP or applies a requirement threshold.
//!
//! Records that the reference returns as dicts are returned as `serde_json::Value` objects with the reference keys;
//! non-finite floats are carried as the strings `"NaN"`, `"+inf"`, `"-inf"` (see [`rec::fnum`]).
//!
//! Lint policy: comparisons are written exactly as the reference writes them, because the NaN behaviour of
//! `not (x > 0)` differs from `x <= 0` and from a range test; index loops keep the reference summation order.
#![allow(clippy::neg_cmp_op_on_partial_ord, clippy::needless_range_loop, clippy::manual_range_contains)]

pub mod compressor;
pub mod compressor_synthesis;
pub mod error;
pub mod filter;
pub mod materials;
pub mod plenum_feed;
pub mod pyops;
pub mod rec;
pub mod reservoir;
pub mod rotor_strength;
pub mod transient;
pub mod upstream;

pub use error::{GasPathError, PyClass, PyResult};

/// Species carried by the F3 / F4 chain, in the reference order.
pub const SPECIES: [&str; 3] = ["O", "N2", "O2"];
