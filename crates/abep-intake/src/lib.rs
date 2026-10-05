//! ABEP intake (SC-WP-02, ES-3).
//!
//! The admitted Kernel-1 TPMC library `abep_core` (parity_report_v2) is called directly as a plain Rust library
//! (A9.29 secs. 5, 11: Rust simulator -> Rust TPMC library; no backend switch). Its consumption from this workspace is
//! covered by the registered build-equivalence addendum
//! (`docs/rust_migration/contracts/C-ABEP_CORE_BUILD_EQUIVALENCE/`).

pub mod build_equivalence;
