# Parity report v1 - PARITY-C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY/parity_prereg_v1.json` sha256 `22c0aca107f44f24fae48671addf1823a0f361dcc47302f782fc23c9209a64c7`, registered in `7a86e3144dd7`.
* Python reference commit `fa4fcb3bd21f`; Rust commit `57914de17b77` (git_dirty: none); rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Scoring seed: 2026100641; 4492 vectors; 0 per-test failures.

## Checks

* per_test: pass
* domain_error: pass
* invariants: pass
* governing: pass
* all: pass

## Observables

| entry | observable | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|
| reference_drag | outcome | 3770 | 0 | 3770 | 0 | 0 | 0 |
| reference_drag | error class / message / status | 493 | 0 | 493 | 0 | 0 | 0 |
| reference_drag | copied floats (EXACT_VALUE) | 26217 | 0 | 26217 | 0 | 0 | 0 |
| reference_drag | q_Pa (ULP_BOUNDED) | 3277 | 0 | 3277 | 0 | 0 | 0 |
| reference_drag | reference_term/D_N (ULP_BOUNDED) | 3277 | 0 | 3277 | 0 | 0 | 0 |
| reference_drag | intake_term/D_N (ULP_BOUNDED) | 3277 | 0 | 3277 | 0 | 0 | 0 |
| reference_drag | D_total_N (ULP_BOUNDED) | 3277 | 0 | 3277 | 0 | 0 | 0 |
| reference_drag | D_total_mN (ULP_BOUNDED) | 3277 | 0 | 3277 | 0 | 0 | 0 |
| reference_drag | registered divergence outcome | 3 | 0 | 3 | 0 | 0 | 0 |
| statewise_margin | outcome | 706 | 0 | 706 | 0 | 0 | 0 |
| statewise_margin | copied floats (EXACT_VALUE) | 1390 | 0 | 1390 | 0 | 0 | 0 |
| statewise_margin | margin_N (ULP_BOUNDED) | 695 | 0 | 695 | 0 | 0 | 0 |
| statewise_margin | error class / message / status | 11 | 0 | 11 | 0 | 0 | 0 |
| density_free_table | outcome | 1 | 0 | 1 | 0 | 0 | 0 |
| density_free_table | copied floats (EXACT_VALUE) | 40 | 0 | 40 | 0 | 0 | 0 |
| build_document | outcome | 1 | 0 | 1 | 0 | 0 | 0 |
| case | outcome | 11 | 0 | 11 | 0 | 0 | 0 |
| case | copied floats (EXACT_VALUE) | 16 | 0 | 16 | 0 | 0 | 0 |

## Domain / error parity

* DE-A-01: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-02: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-03: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-04: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-05: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-06: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-07: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-08: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-09: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-10: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-11: Python RAISED TypeError; Rust RAISED TypeError OUT_OF_DOMAIN - ok
* DE-A-12: Python RAISED TypeError; Rust RAISED TypeError OUT_OF_DOMAIN - ok
* DE-A-13: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-14: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-15: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-16: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-17: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-18: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-19: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-20: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-21: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-22: Python RAISED KeyError; Rust RAISED KeyError OUT_OF_DOMAIN - ok
* DE-A-23: Python RAISED KeyError; Rust RAISED KeyError OUT_OF_DOMAIN - ok
* DE-A-24: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-25: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-26: Python RETURNED ; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-27: Python RETURNED ; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-28: Python RETURNED ; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-A-29: Python RAISED KeyError; Rust RAISED KeyError OUT_OF_DOMAIN - ok
* DE-A-30: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-M-01: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-M-02: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-M-03: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-M-04: Python RAISED TypeError; Rust RAISED TypeError OUT_OF_DOMAIN - ok
* DE-M-05: Python RETURNED ; Rust RETURNED - ok
* DE-M-06: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-M-07: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-M-08: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-M-09: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-M-10: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-M-11: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-M-12: Python RETURNED ; Rust RETURNED - ok
* DE-M-13: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-M-14: Python RETURNED ; Rust RETURNED - ok

## Invariants

* INV-A-01: pass
* INV-A-02: pass
* INV-A-03: pass
* INV-A-05: pass
* INV-A-04: pass

## Performance (reported, never a criterion)

* RD-G python median s: 0.13196850399981486
* RD-G rust median s (one process): 0.08603128800041304
* speed-up: 1.5339594125242118

## Ledger update requested

* C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY: status ADMITTED (whole module) on PARITY_PASS; authoritative_implementation rust: crates/abep-mission (abep_mission::reference_drag, abep_mission::statewise::statewise_margin, register data crates/abep-mission/data/spacecraft_reference_register_v1.json); contract PARITY-C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY-V1; disclosures DIV-A-01 (non-finite results refused)

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
