# Parity report v1 - PARITY-C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION/parity_prereg_v1.json` sha256 `89db4ba5bca298ff6c54f93ba165184dbda825dd5c4c1602dc9c8898d4b2a09a`, registered in `1a8101efc143`.
* Python reference commit `d25834deaa85` (registered 0d8922cfe39b); Rust commit `d25834deaa85`; rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, pandas 3.0.2, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Scoring seed 731909203; 1222 vectors; 0 per-test failures.

## Checks

* per_test: pass
* invariants: pass
* conservation: pass
* domain_error: pass
* schema: pass
* references_unchanged: pass

## Observables

| entry | observable | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|
| SOLAR_CONST | value | 1 | 0 | 1 | 0 | 0 | 0 |
| beta_angle | value | 406 | 0 | 406 | 0 | 0 | 0 |
| eclipse_fraction | value | 414 | 0 | 414 | 0 | 0 | 0 |
| worst_eclipse_fraction | value | 103 | 0 | 103 | 0 | 0 | 0 |
| array_area_for | value | 159 | 0 | 159 | 0 | 0 | 0 |
| propagate | rows.t_h | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | rows.alt_km | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | rows.raan_deg | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | rows.beta_deg | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | rows.eclipse_frac | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | rows.D_mN | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | rows.T_mN | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | rows.P_bus_W | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | rows.P_need_W | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | rows.P_avail_W | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | rows.power_margin_W | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | rows.rho | 20742 | 0 | 20742 | 0 | 0 | 0 |
| propagate | reentered | 126 | 0 | 126 | 0 | 0 | 0 |
| propagate | min_alt_km | 126 | 0 | 126 | 0 | 0 | 0 |
| propagate | mean_eclipse | 126 | 0 | 126 | 0 | 0 | 0 |
| propagate | min_power_margin_W | 126 | 0 | 126 | 0 | 0 | 0 |
| propagate | hours_power_short | 126 | 0 | 126 | 0 | 0 | 0 |
| propagate | raan_drift_deg_per_day | 126 | 0 | 126 | 0 | 0 | 0 |

## Domain / error parity

* DE-P-01 (beta_angle): Python RAISED ValueError, Rust RAISED ValueError - ok
* DE-P-02 (eclipse_fraction): Python RAISED ZeroDivisionError, Rust RAISED ZeroDivisionError - ok
* DE-P-03 (eclipse_fraction): Python RAISED OverflowError, Rust RAISED OverflowError - ok
* DE-P-04 (eclipse_fraction): Python RAISED ValueError, Rust RAISED ValueError - ok
* DE-P-05 (array_area_for): Python RAISED ZeroDivisionError, Rust RAISED ZeroDivisionError - ok
* DE-P-06 (propagate): Python RAISED AttributeError, Rust RAISED AttributeError - ok
* DE-P-07 (propagate): Python RAISED ZeroDivisionError, Rust RAISED ZeroDivisionError - ok
* DE-P-08 (propagate): Python RAISED ValueError, Rust RAISED ValueError - ok
* DE-P-09 (propagate): Python RAISED ValueError, Rust RAISED ValueError - ok
* DE-P-10 (eclipse_fraction): Python RETURNED , Rust RAISED DIV-P-01 - ok
* DE-P-11 (beta_angle): Python RETURNED , Rust RAISED DIV-P-01 - ok
* DE-P-12 (array_area_for): Python RETURNED , Rust RAISED DIV-P-01 - ok
* DE-P-13 (propagate): Python RETURNED , Rust RAISED DIV-P-01 - ok

## Not ported (recorded)

* spacecraft_drag (lane brief A9.31: unsourced defaults, class-H callers only)
* pointing_factors (AUDITED_NOT_PORTED: sole caller spacecraft_drag; owner question OQ-MI-03)
* plume_interaction, ARRAY_AREAL_KG_M2 (class-H callers; not in the SC-WP-09 list)

Performance (recorded, not gating): Python golden propagate 0.036 s, Rust incl. process start 0.011 s.
