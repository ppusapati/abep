# Parity report v1 - PARITY-C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract `docs/rust_migration/contracts/C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY/parity_prereg_v1.json` sha256 `0dfe17e2ed3f1ddf5bdd486e5772bc9c810841b2a21f24c319c7378b427d6d9f`, registered in `e923e492fcd0`.
* Python reference commit `0d8922cfe39b`; Rust commit `b1884ea5417a` (git_dirty: 0 path(s)); rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4.
* Scoring seed 2026100611; 5199 vectors; 0 per-test failures; 4260 returned values byte-identical; max ulp (E15) 0; 2 reference refusals outside the registered classes (outcome only, DIV-04 / DIV-R02).

## Calls per entry

* E1: 1
* E10: 309
* E11: 302
* E12: 309
* E13: 1
* E14: 900
* E15: 301
* E2: 665
* E3: 150
* E4: 150
* E5: 567
* E6: 151
* E7: 760
* E8: 324
* E9: 309

## Checks

* per_test: pass
* invariants: pass
* reference_unchanged: pass
* governing_hashes: pass
* all: pass

## Invariants

* INV-G-01 (no MET on non-evidence; no PASS / COMPLY status value in E2 / E7-E12): pass
* INV-G-02 (HC-05 MET / VIOLATED only with a VALIDATED_BENCH / MEASURED basis, Rust): pass
* INV-G-03 (inputs unchanged by every reference call; Rust borrows &Value immutably): pass
* INV-G-04 (no requirement literal in crates/abep-assess/src): pass
* INV-G-05 (statewise quantifier called, not re-implemented): pass
* INV-G-06 (two Rust runs byte-identical): pass

## Notes

* INV-G-01 is checked on status-valued fields (keys 'status' / 'state_status'): the reference's own basis texts quote gate verdicts (e.g. 'rfp_power_gate verdict PASS (EVALUATED)') and are compared for equality, not scanned for words
* DIV-01 (A9.31 sec. 10) applied to the reference output of every evaluate_constraints vector whose HC-05 record has an uncertainty basis without a VALIDATED_BENCH / MEASURED validation basis

## Ledger update requested

* C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY: PARTIAL admission on PARITY_PASS (contract PARITY-C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY-V1): HARD_CONSTRAINTS, evaluate_constraints (with DIV-01, A9.31 sec. 10), hard_constraint_partition, constraint_met_value_kinds, bus_power_gate, ripple_feed_quality, statewise_drag_compensation, feed_state_sufficiency, pareto_s6_17, propellant_paths_check, rvm_gate_snapshot, owner_state, status_label, apply_to_questions -> crates/abep-assess (abep_assess::{gates, power_gate, statewise, pareto, propellant, rvm, owner_state}); gate_snapshot stays PYTHON_REFERENCE (wraps the F8 robust_optimizer.design_gate_snapshot, SC-WP-10)
* C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY: the pending rfp_power_gate (and the transient_gate field it produces) admitted in abep-assess (abep_assess::power_gate::rfp_power_gate; limit from config p_bus_max_W): with the SC-WP-05 partial admission the row's flight scope is complete (GROUND_REFERENCE_TEST_METADATA stays GROUND_REFERENCE_ONLY)
* C-ABEP_SIM_PROGRAMME_DESIGN_SYNTHESIS_PY: the pending gate_verdict field of bus_power admitted in abep-assess (abep_assess::power_gate::bus_power_gate_verdict); every other function of design_synthesis stays with SC-WP-10
* C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY: partial admission of statewise_envelope and _rec_value (abep_assess::statewise; over the admitted abep_mission::statewise::statewise_quantifier)
* C-DOCS_EXPERIMENTS_HALL_ICP_P1_ICP_BENCH: partial admission of the kernel icp45a_margin (abep_assess::neutralization::icp45a_margin; A9.29 sec. 4: M_n in assessment only); the P1 reducer stays PYTHON_REFERENCE (SC-WP-03)

Parity is not physics validation, not a gate PASS and not a change of any threshold or frozen record.
