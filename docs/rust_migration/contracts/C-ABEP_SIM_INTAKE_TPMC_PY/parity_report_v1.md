# Parity report v1 — PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1: **ADMITTED**

Contract `docs/rust_migration/contracts/C-ABEP_SIM_INTAKE_TPMC_PY/parity_prereg_v1.json` (sha256 `1e6a80fbeb848b4e229ad35438f88f4d8f5041658ab71ade6a1d81aa87e66a6d`). Python reference and Rust at `ed6b27af8eba3702747e34d5d3286717d3642e96` (dirty: True). Generated from `parity_report_v1.json` by `scripts/rust_migration/parity_intake.py`.

| entry point | result | test counts | aggregate max abs(sum z)/sqrt(N) |
|---|---|---|---|
| E1_intake_response | PARITY_PASS | {'AGREE_EXACT': 114, 'WITHIN': 310, 'PASS': 159} | 2.221 |
| E2_clausing_transmission | PARITY_PASS | {'WITHIN': 11} | 0.074 |
| E3_response_surface | PARITY_PASS | {'PASS': 72} | - |
| E4_IntakeSurface | PARITY_PASS | {'PASS': 17143} | - |
| E5_surface_v2_gate | PARITY_PASS | {'PASS': 1} | - |

| check | held |
|---|---|
| invariant INV-09_rust_status | True |
| invariant INV-02 | True |
| invariant INV-06 | True |
| invariant INV-07 | True |
| invariant INV-03 | True |
| invariant INV-01_E4 | True |
| invariant INV-01_E1_E2 | True |
| invariant INV-04 | True |
| invariant INV-08 | True |
| invariant INV-05_frozen_unchanged | True |
| conservation CONS-01 | True |
| domain / error parity (25 cases) | True |
| schema parity | True |
| reference files and pinned inputs unchanged | True |

Performance (reported, never a criterion): intake_response_surface_reduced — Python median 4.984 s wall / 4.983 s CPU; Rust median 0.7884 s wall / 0.7880 s CPU; speed-up 6.3x wall. Python: OMP / OPENBLAS / MKL / NUMEXPR = 1 (as the baseline); Rust: single-threaded (no thread pool in abep-intake or abep_core).

## Deviation from the registered evaluation text

The Rust simplex selection deviates from the evaluation text registered in PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1. The observables, tolerances and seeds are unchanged (as are vector rules, n, decision rules and pinned inputs).

- registered: PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1 rust_implementation.interpolant_reproduction.rust_evaluation: the first non-degenerate simplex in captured order whose barycentric coordinates lie in [-eps, 1 + eps], Tinv from Gaussian elimination; it also stated that values on shared faces agree up to rounding
- finding: the development comparison (development seed 7, E4 face vector E4-F28; not a verdict) showed that the reference triangulation is non-conforming across some interior grid faces (Qhull 'Qt' triangulates a shared cospherical face differently on its two sides), so the reference value at such a face point depends on which containing simplex scipy's search reaches; the stated face continuity is false
- change before scoring: the Rust surface replicates scipy's _find_simplex (lifted-paraboloid walk from simplex 0, directed search, brute-force fallback) and barycentric arithmetic with the reference's captured search structures crates/abep-intake/data/intake_surface_v1_delaunay_v1_search.json (sha256 e6f254b3f089123b2c8eadaac7adf66b6d64f823540a4ed8cb4d86cba301b3fd, same capture script; the pinned triangulation capture 247601cf... is unchanged and still verified); the independent Gaussian-elimination inverse is kept as a load-time cross-check of the captured transforms (1e-10)
- applies to: E4 IntakeSurface of this contract
- unchanged: observables, tolerances, vector rules, n, seeds, decision rules and pinned inputs of both contracts

## Finding B2-OF-01 — a property of the frozen Python reference, not of the Rust port

the FROZEN PYTHON REFERENCE (abep_sim.intake_tpmc.IntakeSurface over abep_sim/data/intake_surface_v1.csv with scipy 1.17.1 LinearNDInterpolator / Qhull 8.0.2), NOT the Rust port; the Rust port reproduces it by replicating scipy's simplex search. the reference interpolant is discontinuous across interior grid faces: at a point on such a face its value is that of whichever containing simplex scipy's walk reaches. Classification: PYTHON_REFERENCE_DEFECT candidate (own governance; not resolved by the migration, RM-R11 / RM-R22). 2026-10-05: keep faithful parity for this migration; the interpolant is not changed; B2-OF-01 is carried to the owner as an open question.

Affected interior faces: L_over_d = 10, L_over_d = 5, alpha = 0.2, alpha = 0.5, alpha = 0.8, theta_deg = 2 (phi has no interior grid value).

| field | max relative jump between containing simplices | where |
|---|---|---|
| eta_c | 0.0377 | maxwell, N2, theta_deg = 2 |
| C_D | 0.00222 | cll, O, theta_deg = 2 |
| CR_passive | 0.173 | cll, N2, theta_deg = 2 |
| K_back | 0.0612 | cll, O2, theta_deg = 2 |
| mass_kg | 0.0373 | maxwell, N2, alpha = 0.2 |

Survey: `docs/rust_migration/contracts/C-ABEP_SIM_INTAKE_TPMC_PY/finding_B2-OF-01_face_survey_v1.json` (sha256 `4b30eaca5bbd2560426917c3c9ed11c447ef0ec4ce963e372dba4af98673e03f`), per scattering table and interior face (axis at an interior grid value), 60 points with the other axes uniform in the table range (numpy default_rng(0), draws in axis order); every non-degenerate reference simplex containing the rescaled point within eps = 100 DBL_EPSILON is evaluated; spread = (max - min) / |mean| of the interpolated row value per field and species; a point is non-conforming when any spread exceeds 1e-12. phi has no interior grid value (2 values), hence no interior face.
Owner question: keep the reference interpolant as is (parity), or replace it by a deliberate conforming interpolant (e.g. multilinear or a fixed Kuhn triangulation) as a registered intake-ROM model change (rule 1/2: new version, HISTORY, evidence that depends on it re-run)?

ADMITTED is software parity with the Python reference inside the registered domain, not physics validation and not a gate PASS.
