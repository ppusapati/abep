# Plenum / feed v6: what drives the frozen P45 envelopes (scoring held for a decision)

Contract v6 (`parity_prereg_v6.json`, sha256 `60f8bc2482e967b888f1b1421f8b7b7c907a92fed4b0a88f5d3e65ad30deab5a`,
registered in `aca62b3`); frozen record `transient_envelope_v6.json` (sha256
`439ae2dd1f5f935db7ad1e3538c538c0cad7a11af333752e4c9fedbbeaa7002c`, committed in `eec930a`, never edited). The
single scoring run (scoring_master_seed 731905353) has **not** been run: no held-out vector of v6 was drawn or run.

Reproduce: `python3 scripts/rust_migration/plenum_v6_p45_refinement_analysis.py OUT.json` (refinement vectors only).

## Frozen P45 envelopes (PROD)

| family | E_py | E_rust | combined bound |
|---|---|---|---|
| F45.P_dev (absolute) | 0.188 (R45-187) | 0.0373 (R45-187) | 0.225 |
| F45.mdot (x mdot_scale) | 0.496 (R45-265) | 0.229 (R45-034) | 0.725 |

P_dev_max_frac values of the grid lie between 8.6e-7 and 0.22 (stable vectors up to 0.15), so for P45 the combined bound is close to vacuous.

## Per vector (373 of 512 P45 vectors run in all six runs)

Split by the largest real part of the eigenvalues of the dynamic block of the reference Jacobian at the steady start
(an input property, the same for both implementations):

| estimator max of (abs(N - T2) + abs(T1 - T2)) / scale | stable (362) py | stable rust | unstable (11) py | unstable rust |
|---|---|---|---|---|
| P_dev_max_frac | 4.6e-6 | 9.2e-8 | 0.188 | 0.0373 |
| mdot_min_kgps | 2.9e-5 | 3.2e-6 | 0.213 | 0.229 |
| mdot_max_kgps | 4.6e-5 | 2.1e-8 | 0.496 | 0.113 |

* Every P45 envelope is set by the 11 vectors whose closed loop is unstable at the steady start; on the 362 stable
  vectors both implementations converge to 1e-5 or better.
* The **Python reference** shows the v5 failure mode itself: on R45-187 (Re lambda = 0.0024) its nominal LSODA run
  reports P_dev 7.5e-5 with `ok`, the converged runs 0.174 (T1) / 0.181 (T2). The reference is read-only (RM-R11);
  the procedure records this as the reference's own nominal-tolerance error (E_py).
* Rust after the growing-mode guard has no such case (no vector where nominal < T2 / 10 with T2 > 1e-3).
* On the two weakly unstable vectors R45-034 and R45-187 (Re lambda about 0.002) T1 and T2 disagree in both
  implementations (P_dev 0.0071 / 0.0131, mdot_min up to 0.14 mdot_scale): extrema sampled every few hundred seconds
  from a limit cycle of period about 2.6 s depend on its phase at the sample times, which is not resolved at these
  tolerances (the same kind of observable as the v5 cascade diagnostics).

## Decision needed before the v6 scoring run

Scored now, every held-out P45 vector (about 97 % stable, own convergence about 1e-6) is compared with a bound of
0.225 in P_dev and 0.725 mdot_scale in mdot: a near-vacuous P45 test. Options for the coordinator / owner:

1. Score v6 as registered (the bound is what the registered procedure produces; Rust has no known wrong answer).
2. Supersede v6 unscored by a v7 that registers a per-vector stability class (sign of max Re lambda of the reference
   Jacobian at the steady start, an input property) with separate envelopes per class, and treats the sampled extrema
   of an unstable loop (P_dev_max_frac, mdot_min / mdot_max) like the cascade diagnostics (reported with
   conditioning; the instability itself, i.e. the excursion above the tolerance scale, scored as an outcome).
   P42 / P43 may need the same check: their v6 Python envelopes also grew (F42.p 0.00655 at R42-PROD-018, F42.ucmd_end
   0.0197), not yet analysed per vector.
