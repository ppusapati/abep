//! Hall-map typing, the two-layer transport-ensemble admission gate, the append-only Hall-map registry and the Hall
//! response status of the ABEP Rust simulator (SC-WP-03; contract
//! `docs/rust_migration/contracts/C-HALL-MAP-ENSEMBLE-REGISTRY/parity_prereg_v1.json`).
//!
//! HallThruster.jl (pinned, `hallthruster_bridge/PINNED.toml`) stays the authoritative Hall solver: this crate computes
//! no discharge quantity. It reads frozen maps, gates them on admitted transport members, interpolates them and keeps
//! their provenance. The credible transport set is EMPTY: every output needing Hall performance goes through
//! `status::HallGate` and is NOT_EVALUATED with the reason "credible Hall transport set EMPTY".
//!
//! [`envelope`] (NP-HALL-PARAMETRIC-ENVELOPE v1, A9.32) reads the frozen case set and ingests the frozen raw
//! HallThruster.jl parametric envelope of H-1: PARAMETRIC / NOT_VALIDATED, separate from HallMap and the gate.

pub mod ensemble;
pub mod envelope;
mod error;
pub mod hall_map;
pub mod py;
pub mod registry;
pub mod schema;
pub mod status;

pub use error::{HallError, HallResult, Kind, NumpySub};
