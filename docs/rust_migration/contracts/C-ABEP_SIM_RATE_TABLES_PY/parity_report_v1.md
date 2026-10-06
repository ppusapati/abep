# Parity report v1: PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1

**Verdict: ADMITTED (PARITY_PASS)**, mode `scoring`, seed 1810061023, 2026-10-06T09:13:48Z.

- Contract `docs/rust_migration/contracts/C-ABEP_SIM_RATE_TABLES_PY/parity_prereg_v1.json`, sha256 `504be4d2386d27efa35d88d11b44e9b483cd2b39fa65d544d75da4dadada3372`, registered at `cdd24a208251fdd8e5e2c6888ad582549a92463f`.
- Python reference `abep_sim/rate_tables.py` sha256 `ea9880b0d5a474e93083346f29694f2fa820ffce01aca001ea4610893ac04909` at `6358af8b830e9e6b70b4e4eba85d80682ea3ffb8`; Python 3.11.15, numpy 2.4.4 (AVX512_SKX True).
- Rust `crates/abep-chem` at `75f86a322a7583f003851c77e8e8b398299a449c`; rustc 1.94.1 (e408947bf 2026-03-25).

## Per-test results

| entry point | passed / scored |
|---|---|
| maxwellian_rate | 2948 / 2948 |
| tail_sensitivity | 38 / 38 |
| step | 259 / 259 |
| write_table | 46 / 46 |
| render | 46 / 46 |

- Rate values compared: 14267; bit-identical 13792; max relative difference 5.709e-16 (registered bound 1e-13 or 1e-250 m^3/s); largest |Rust| where Python is 0: 0.000e+00 m^3/s.
- step_cross_section_rate: 259 / 259 bit-identical (bound 1 ulp).
- tail_sensitivity share: max |difference| 1.804e-16 (bound 4e-13).
- Table texts identical: 46; BOUNDARY_ROUNDING lines: 0.

## Domain / error parity

| case | divergence | Python | Rust | pass |
|---|---|---|---|---|
| DE-01 | - | ValueError: tail must be 'hold' or 'zero', got 'Hold' | ValueError: tail must be 'hold' or 'zero', got 'Hold' | True |
| DE-02 | - | ValueError: tail must be 'hold' or 'zero', got None | ValueError: tail must be 'hold' or 'zero', got None | True |
| DE-03 | - | ValueError: tail must be 'hold' or 'zero', got 'x' | ValueError: tail must be 'hold' or 'zero', got 'x' | True |
| DE-04 | - | value 0.0 | value 0.0 | True |
| DE-05 | - | value 0.0 | value 0.0 | True |
| DE-06 | - | value 0.0 | value 0.0 | True |
| DE-07 | - | value nan | value nan | True |
| DE-08 | - | value nan | value nan | True |
| DE-09 | - | value nan | value nan | True |
| DE-10 | - | ZeroDivisionError: 0.0 cannot be raised to a negative power | ZeroDivisionError: 0.0 cannot be raised to a negative power | True |
| DE-11 | - | OverflowError: (34, 'Numerical result out of range') | OverflowError: (34, 'Numerical result out of range') | True |
| DE-12 | - | value nan | value nan | True |
| DE-13 | - | value 0.0 | value 0.0 | True |
| DE-14 | - | value inf | value inf | True |
| DE-15 | - | value inf | value inf | True |
| DE-16 | - | value nan | value nan | True |
| DE-17 | - | ValueError: zero-size array to reduction operation maximum which has no identity | ValueError: zero-size array to reduction operation maximum which has no identity | True |
| DE-18 | - | value 0.0 | value 0.0 | True |
| DE-19 | - | IndexError: index -1 is out of bounds for axis 0 with size 0 | IndexError: index -1 is out of bounds for axis 0 with size 0 | True |
| DE-20 | - | ValueError: fp and xp are not of the same length. | ValueError: fp and xp are not of the same length. | True |
| DE-21 | - | IndexError: index -1 is out of bounds for axis 0 with size 0 | IndexError: index -1 is out of bounds for axis 0 with size 0 | True |
| DE-22 | - | ValueError: fp and xp are not of the same length. | ValueError: fp and xp are not of the same length. | True |
| DE-23 | - | ValueError: fp and xp are not of the same length. | ValueError: fp and xp are not of the same length. | True |
| DE-24 | - | value 0.0 | value 0.0 | True |
| DE-25 | DIV | value nan | refused OUT_OF_DOMAIN | True |
| DE-26 | DIV | value inf | refused OUT_OF_DOMAIN | True |
| DE-S1 | - | ZeroDivisionError: float division by zero | ZeroDivisionError: float division by zero | True |
| DE-S2 | - | ZeroDivisionError: float division by zero | ZeroDivisionError: float division by zero | True |
| DE-S3 | - | ValueError: math domain error | ValueError: math domain error | True |
| DE-S4 | - | value nan | value nan | True |
| DE-S5 | - | value inf | value inf | True |
| DE-S6 | - | value 0.0 | value 0.0 | True |
| DE-S7 | - | value inf | value inf | True |
| DE-S8 | - | OverflowError: math range error | OverflowError: math range error | True |
| DE-T1 | - | ValueError: zero-size array to reduction operation maximum which has no identity | ValueError: zero-size array to reduction operation maximum which has no identity | True |
| DE-W1 | - | ValueError: arange: cannot compute length | ValueError: arange: cannot compute length | True |
| DE-W2 | - | ValueError: Maximum allowed size exceeded | ValueError: Maximum allowed size exceeded | True |
| DE-W3 | - | ValueError: Maximum allowed size exceeded | ValueError: Maximum allowed size exceeded | True |
| DE-W4 | - | ValueError: Maximum allowed size exceeded | ValueError: Maximum allowed size exceeded | True |
| DE-W5 | - | ValueError: Maximum allowed size exceeded | ValueError: Maximum allowed size exceeded | True |
| DE-W6 | - | ValueError: tail must be 'hold' or 'zero', got 'bogus' | ValueError: tail must be 'hold' or 'zero', got 'bogus' | True |
| DE-W7 | DIV | MemoryError: Unable to allocate 7.11 PiB for an array with shape (1000000000000001,) and data type float64 | refused OUT_OF_DOMAIN | True |

## Invariants

- INV-01: pass {"stdout_sha256": "e3f51db6620f3bd8812bf22d1bdddddb1e7162d618608007e60c04f39dbea90e"}
- INV-02: pass {"n": 37, "reproduced": 37}
- INV-03: pass {}
- INV-04: pass {"pairs_checked": 3422}
- INV-05: pass {"values_checked": 28534}
- INV-06: pass {"checks": 210}

## Performance (reported, not a criterion)

PERF-WT (37 tables x 301 rows): median Python 4.98 s, Rust 6.54 s (CLI incl. start-up), speed-up 0.8x.

## Ledger update requested

- {"component": "C-ABEP_SIM_RATE_TABLES_PY", "requested_status": "ADMITTED", "scope": "maxwellian_rate (tails hold / zero), tail_sensitivity, step_cross_section_rate, write_hallthruster_table (rows, table text, sidecar text; file I/O excluded)", "authoritative_implementation": "rust: abep_chem::reference (parity behaviour, table rebuilds) and abep_chem::checked (fail-closed production API, IF-CHEM-REG-v1)", "contract": "PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1", "downstream": "NP-ICP-NEUTRALIZER prereg_v1 software_admission item (3) 'the abep-chem rate evaluator it uses is admitted' is satisfied by this admission (verification_report_v1 admission item 3 / NV-06 direct side can be evaluated once abep-icp is wired to abep_chem::checked by its own lane); no table, registry or validity entry is admitted by it"}

## What this is not

- not physics evidence or validation: parity shows the Rust code reproduces the Python reference, not that either is right
- not a change of any frozen dataset, golden, threshold or requirement; no table is rebuilt
- not an admission of any cross-section table, chemistry registry, validity entry or completeness claim (those belong to NP-ICP-CHEM-AIR and the rate_validity.toml governance)
- not authority before admission: until ADMITTED the Python reference is authoritative
- not a promotion of any provisional input (RM-R27)
- not a gate PASS: absent determining evidence stays NOT_EVALUATED / INCOMPLETE_EVIDENCE / OUT_OF_DOMAIN / MODEL_ERROR (RM-R31)
