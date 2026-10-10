# Acceptance report v1 - ACCEPT-NI-ABEP-ASSESS-RFP-MATRIX-V1

Verdict: **ACCEPTED**. Generated from `acceptance_report_v1.json`.

* Prereg sha256 `ed5bf752da42387576547c79aedaa855ec37af6d74a99b67dd6ba49b5eda081a` (commit `7539c893e285`); HEAD `a7934e87fe0e`; rustc 1.94.1 (e408947bf 2026-03-25).
* Matrix record `docs/rust_migration/contracts/NI-ABEP-ASSESS-RFP-MATRIX/rfp_constraint_matrix_run_v1.json` sha256 `b03f03913ee5486b7436ed05b4ed250c82b5a55d092ce62a3a9fc6d65c0b1622`; two runs byte-identical: True.

## Cases

* AC-01 (ac01_four_separate_fields_and_no_assessment_word_in_raw): ok
* AC-02 (ac02_threshold_change_moves_assessment_never_raw_physics): ok
* AC-03 (ac03_todays_raw_results_are_fail_closed): ok
* AC-04 (ac04_hc05_rule_order): ok
* AC-05 (no_physics_crate_depends_on_abep_assess): ok
* AC-06 (ac06_no_requirement_parsing_in_raw_physics): ok
* AC-07 (ac07_ac08_deterministic_and_raw_unchanged): ok
* AC-08 (ac07_ac08_deterministic_and_raw_unchanged): ok
* AC-09 (ac09_non_determining_records_never_comply): ok
* AC-10 (ac10_tampered_records_fail_closed): ok

## The matrix on today's admitted raw results

| requirement | raw physics | evidence | RFP assessment |
|---|---|---|---|
| RFP-ALT | EVALUATED | NOT_EVALUATED | NOT_EVALUATED |
| RFP-ATM-PRIMARY | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED |
| RFP-XE-CONTINGENCY | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED |
| RFP-THRUST-12MN-SUSTAINED | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED |
| RFP-THRUST-25MN-CAPABILITY | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED |
| RFP-PBUS-LT-1500W | INCOMPLETE_EVIDENCE | INCOMPLETE_EVIDENCE | NOT_EVALUATED |
| RFP-WET-MASS-LT-40KG | INCOMPLETE_EVIDENCE | INCOMPLETE_EVIDENCE | DOES_NOT_CLOSE |
| RFP-ATM-XE-COMPATIBILITY | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED |

HC-05: NOT_EVALUATED; GNG-ICP-01: NOT_EVALUATED; RVM replay 60 / 60 cells reproduced.

## Ledger update requested

* NI-ABEP-ASSESS-RFP-MATRIX: ACCEPTED (lifecycle PREREG_ACCEPTANCE -> RUST_IMPL -> ACCEPTED) on this report; crate crates/abep-assess (abep_assess::{matrix, neutralization::hc05}); ADMITTED additionally needs the workspace CI run of the acceptance tests

Not an architecture verdict and not a relabelling of any raw status.
