# Plenum / feed v7: NON_VACUITY failed on the frozen record; scoring not run (STOP)

**Status (coordinator decision 2026-10-07): contract v7 REGISTERED_NEVER_SCORED, superseded: unstable-stratum
time-domain observables ill-posed (noise-seeded growth).** A run that starts at an unstable equilibrium stays there
in exact arithmetic, so the growth that findings 1-3 below show is seeded only by rounding and truncation noise. No
further step-control fix and no later version for the unstable stratum. The successor (contract v8) scores the
unstable stratum on its class and leading eigenvalues only and reports its time-domain outputs. The v7 contract and
its record stay unedited. Finding 2 is recorded as `div_p_ref_01_addendum_a1_tightened_runs.json` (DIV-P-REF-01-A1).

Contract v7 (`parity_prereg_v7.json`, sha256 `4f07529b88393291c737576a12d5dc3a2a401d919958fb5fd1c6ce8007e16083`,
registered in `bd11e5c`; harness `07ed905`). Frozen record `transient_envelope_v7.json` (sha256
`e4774be4927aebe91c4cf1692405f3c463e1d4de21fc62f406fe075d69c9855f`, committed in `60df0d4`, never edited).
The registered rule (transient_convergence_procedure_v7.non_vacuity) and the coordinator decision require a stop
before scoring when any family fails; the scoring run refuses the record. **No held-out (scoring_master_seed 731905363)
vector was drawn or run.**

Reproduce the per-vector values (refinement vectors only):
`python3 scripts/rust_migration/plenum_v7_nonvacuity_probe.py R45-PROD-U-061 R45-PROD-U-045 R45-PROD-U-119`.

## What passed

* 57 of 60 rows: every S row (P42 / P43 PROD and REF, P45) and every U row of P42 (PROD, REF) and P43 REF, and P43 PROD
  except F43.overshoot. E.g. U P42 PROD F42.p bound 2.8e-3 vs scale 0.357; S P45 F45.P_dev 5.7e-6 vs 5.3e-5.
* Stability class: 0 disagreements between the Python reference Jacobian (numpy) and Rust on the 2560 refinement
  vectors. Draws: 21 364 candidates classified (the record commit message 60df0d4 says 25 364 in error; the record is right); U shares PROD P42 3.6 %, P43 3.2 %, P45 3.2 %, REF P42 3.2 %, P43
  3.3 %. COMP-P-01 true.

## What failed (all U stratum, PROD)

| family | bound | comparison scale | set by |
|---|---|---|---|
| F45.P_dev (relative) | 98.8 | 1 | E_rust^U 86.4 at R45-PROD-U-061 + D_py^U 12.4 at R45-PROD-U-045 |
| F45.mdot | 1.05 | 0.868 (median range) | E_rust^U 0.874 at R45-PROD-U-119 |
| F43.overshoot | 7.43 | 1.98 (median magnitude) | E_rust^U 7.30 at R43-PROD-U-173 |

## Four findings

1. **Rust nominal still holds the setpoint on a weakly unstable loop (R45-PROD-U-119).** Max Re lambda over the 24
   phases 8.2e-3 (phase 0 3.5e-3). P_dev: Rust N 1.2e-4 (13 425 evaluations), Rust T1 / T2 0.2295 / 0.2293;
   Python N / T1 / T2 0.191 / 0.233 / 0.229. mdot_min: Rust N 3.91e-10 vs T2 1.34e-10 (both implementations). The v6
   growing-mode guard (361a197) prevents damping, but a mode started below the tolerance scale grows too slowly at
   the step sizes the guard allows (the residual property recorded in `rust_defect_v5_growing_mode_damping.md`), and
   for a weak instability it does not develop within the orbit. This is the outcome the coordinator required never
   to pass ("never held"): the check caught it.
2. **The Python reference's tightened runs also miss a growing mode (R45-PROD-U-061).** Max Re lambda 0.272 (phase 0
   3.6e-2; 13 of 24 phases positive). P_dev: Python N / T1 / T2 9.4e-6 / 8.2e-5 / 7.6e-5 (185 / 51 472 / 39 697
   evaluations); Rust N / T1 / T2 0.0245 / 0.0179 / 0.0217 (11-16 M evaluations). DIV-P-REF-01 (the nominal run) thus
   extends to T1 / T2: the converged Python answer is not a trustworthy comparison target on every unstable loop.
3. **A seeding-sensitive outcome (R45-PROD-U-045).** Max Re lambda 1.1e-2 at 9 of 24 phases, phase 0 stable. P_dev:
   Python N 0.048, Python T1 / T2 1.0e-4 / 7.6e-6, Rust N / T1 / T2 7.6e-6. Whether the excursion develops depends on
   how the growing phases are seeded; with the relative scale the T1 / T2 change of a tiny value is 12.4.
4. **F43.overshoot in U: the registered absolute scale (1) does not fit a heavy-tailed quantity.** overshoot_frac
   ranges from 1e-2 to 393 (R43-PROD-U-173: Rust N 386.0 vs T2 393.3, 1.9 %), so one large value sets the bound above
   the median magnitude.

## Options for the coordinator (nothing registered)

* Rust (finding 1): strengthen the guard from "never damp a growing mode" to "resolve it": limit the step so that the
  accepted update reproduces the growth of every Re lambda > 0 mode within the step's error tolerance, e.g.
  |R_acc(h lambda) - exp(h lambda)| <= rtol |exp(h lambda)| (more steps on unstable loops only). Needs a RUST_DEFECT
  fix, tests on the weakly unstable regression vectors (R45-PROD-U-119 and the v6 R45-192 / R45-331), a new version.
* Reference (findings 2, 3): for the U stratum the Python T2 run is not sufficient; a registered converged reference
  could be an independent high-accuracy integration of the reference right-hand side (scipy, e.g. Radau or DOP853 at
  tight tolerances with a step limit that resolves the growing modes), as the v3 / v4 analyses used, with
  cross-implementation T2 disagreement beyond both implementations' T1 / T2 changes as an additional
  NOT_CONVERGENT_REFERENCE criterion; or the U stratum is scored on the outcome only (excursion vs held, with the
  limit cycle's amplitude relative to the converged one) and its sampled values reported.
* F43.overshoot (finding 4): a relative scale in the U stratum (as F45.P_dev), registered before the next
  refinement.
