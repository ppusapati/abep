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

Implementation change since registration: the development comparison (development seed 7, E4 face vector E4-F28; not a verdict) showed that the reference triangulation is non-conforming across some interior grid faces (Qhull 'Qt' triangulates a shared cospherical face differently on its two sides), so the reference value at such a face point depends on which containing simplex scipy's search reaches; the stated face continuity is false; the Rust surface replicates scipy's _find_simplex (lifted-paraboloid walk from simplex 0, directed search, brute-force fallback) and barycentric arithmetic with the reference's captured search structures crates/abep-intake/data/intake_surface_v1_delaunay_v1_search.json (sha256 e6f254b3f089123b2c8eadaac7adf66b6d64f823540a4ed8cb4d86cba301b3fd, same capture script; the pinned triangulation capture 247601cf... is unchanged and still verified); the independent Gaussian-elimination inverse is kept as a load-time cross-check of the captured transforms (1e-10). Unchanged: observables, tolerances, vector rules, n, seeds, decision rules and pinned inputs of both contracts.

Owner finding B2-OF-01 (PYTHON_REFERENCE_DEFECT candidate (own governance; not resolved by the migration, RM-R11 / RM-R22)): abep_sim.intake_tpmc.IntakeSurface (scipy LinearNDInterpolator over the Qhull triangulation of the degenerate v1 tensor grid) is discontinuous across interior grid faces: points with L/d = 5 or 10, alpha = 0.2 / 0.5 / 0.8 or theta = 2 deg get the value of whichever containing simplex scipy's walk reaches. A Python-only survey (60 random points per interior face, N2 rows) found jumps between containing simplices up to 1.7e-1 relative in CR_passive (theta = 2 deg), 6e-2 in K_back, 3.8e-2 in eta_c, 3.7e-2 in mass_kg (alpha faces) and 1.3e-3 in C_D. The active default points checked ((10, 0.85, 0.5, 0), (5, 0.85, 0.8, 0), (10, 0.85, 0.95, 0), (3, 0.85, 0.5, 0), (5, 0.85, 0.8, 2)) agree to rounding. Question: keep the reference interpolant as is (parity), or replace it by a deliberate conforming interpolant (e.g. multilinear or a fixed Kuhn triangulation) as a registered intake-ROM model change (rule 1/2: new version, HISTORY, evidence that depends on it re-run)?

ADMITTED is software parity with the Python reference inside the registered domain, not physics validation and not a gate PASS.
