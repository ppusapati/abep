# RUST_DEFECT found by the plenum / feed v5 refinement run: growing modes damped by the Rust transient integrator

Status: **contract v5 REGISTERED_NEVER_SCORED, superseded: Rust integrator accepts damped steps on unstable modes.**
Fixed in `abep_gaspath::transient` (commit `361a1970c0b6`); registered in contract v6. No held-out (scoring) vector of v5
was drawn or run.

## Evidence (kept, never edited)

* Contract v5: `parity_prereg_v5.json`, sha256 `1b382387491bef6c4a1669b27170dac42ae5a416fc43527f1c840e9d8aa2f092`,
  registered in `f44dbfe`.
* Frozen envelope record of the v5 refinement run (refinement seed 731905543, run once at `faa4c1d`):
  `transient_envelope_v5.json`, sha256 `c02452ebf2d6790c3e8d7fc511703d8e47e281c84b207431882d5a6a5c5d6642`, committed
  in `3eeb574` (+ `.md`). It stays the evidence of this defect; it is not used by any later version.

## What the record showed

Two P45 envelopes of the Rust implementation were far above the Python ones, both attained at R45-192:

| family (PROD, P45) | E_rust | E_python | argmax (rust) |
|---|---|---|---|
| F45.mdot (x mdot_scale) | 0.782 | 0.0465 | R45-192 mdot_max_kgps |
| F45.P_dev | 0.0311 | 0.00622 | R45-192 P_dev_max_frac |

Scored with these, the P45 bounds would be close to vacuous (P_dev values 0.03-0.19 against an absolute bound of
0.037) and would have hidden a qualitatively wrong Rust answer. The one-shot scoring was therefore not run.

## Diagnosis (refinement vectors only)

Reproduce with `python3 scripts/rust_migration/plenum_v5_growing_mode_diagnosis.py diagnose R45-192 R45-331` (the
Rust values it prints are those of the binary built from the working tree; the "before" column below was taken at
`3eeb574`).

orbit_sim records (P_dev_max_frac / mdot_min_kgps / mdot_max_kgps, RHS evaluations):

| vector | run | Rust before the fix | Rust after the fix | Python |
|---|---|---|---|---|
| R45-192 | nominal rtol 1e-5 | 1.246e-5 / 1.043e-10 / 1.767e-10, 3198 | 0.02942 / 3.088e-12 / 3.326e-10, 6 200 121 | 0.03171 / 4.774e-12 / 3.297e-10, 387 509 (LSODA) |
| R45-192 | T1 rtol 1e-8 | 0.031131 / 4.196e-12 / 3.3218e-10, 8 149 617 | unchanged (bit-identical) | 0.031070 / 4.110e-12 / 3.3230e-10 |
| R45-192 | T2 rtol 1e-10 | 0.031134 / 4.200e-12 / 3.3217e-10 | - | 0.031132 / 4.197e-12 / 3.3217e-10 |
| R45-331 | nominal rtol 1e-5 | 8.853e-6 / 1.549e-11 / 2.816e-11, 3204 | 0.03052 / 4.685e-13 / 5.359e-11, 5 556 720 | 0.03042 / 6.892e-13 / 5.161e-11, 277 204 |
| R45-331 | T1 rtol 1e-8 | 0.030146 / 6.695e-13 / 5.230e-11, 7 467 762 | unchanged (bit-identical) | 0.030136 / 7.006e-13 / 5.239e-11 |

Before the fix the Rust nominal run reported the setpoint held (P_dev about 1e-5) in about 3200 evaluations, one Radau
step per output interval, while every converged run (both implementations) shows a 3 % pressure excursion with the
valve flow falling to about 1/50-1/100 of its mean: a saturating limit cycle.

Cause. At the steady start both closed loops are unstable (eigenvalues of the dynamic 5 x 5 block of the reference
Jacobian, numpy):

* R45-192: 0.0508 +/- 2.423i, -0.09575, -0.1159, -6.487 (orbital period 5319 s)
* R45-331: 0.03652 +/- 2.259i, -0.0838, -0.09515, -6.45 (orbital period 5337 s)

Radau IIA is damping for large |z| in the right half-plane too: R(z) = (1 + 2z/5 + z^2/20) / (1 - 3z/5 + 3z^2/20 -
z^3/60) -> 0. The update the integrator accepts is the step-doubling solution with local extrapolation,
R_acc(z) = (32 R(z/2)^2 - R(z)) / 31. For the R45-192 mode one step damps it (|R(h lambda)| < 1) for h >= 1.26 s, the
accepted update for h >= 2.63 s (R45-331: 1.27 s / 2.66 s), although the exact flow grows (|exp(h lambda)| > 1). The
orbit output grid (150 geometric samples) has 56 of 150 intervals longer than that; over the last one (471 s) the
exact flow grows the mode 2.5e10-fold, the accepted update multiplies it by 8.9e-5. The step-doubling error estimate
compares two equally damped solutions of a mode started below the absolute tolerance (a steady start excited only by
the slow orbit forcing), so it sees no error and the steps grow to the output spacing: the instability is integrated
as a held setpoint, with `ok: true`.

Extent. Of the 512 P45 refinement vectors 366 ran (`ok`); 353 Rust nominal runs used < 5e4 evaluations, and of these
only R45-192 and R45-331 disagree with their T1 run (by more than 1e-3 relative). R45-054 (0.554 +/- 1.958i) and
R45-198 (0.101 +/- 0.820i) are also unstable at the start but grow fast enough to be resolved by the unmodified error
control. P42 / P43 were not affected in the refinement grid (see blast radius).

Classification: RUST_DEFECT (a silent qualitatively wrong trajectory reported as converged; CLAUDE.md rule 3, A9.29
sec. 14), not a contract defect: the v5 procedure measured it correctly.

## Fix (commit `361a1970c0b6`)

`abep_gaspath::transient::Integrator::integrate`: before every trial step, the eigenvalues of the dynamic 5 x 5 block
of the Jacobian at the step start are computed (the three cumulative-integral states have zero Jacobian columns, so the
full spectrum is this block's plus three zeros). While any eigenvalue with Re lambda > 0 has |R_acc(h lambda)| < 1 the
step is halved. No tunable constant: the condition is that no accepted step damps a mode the linearised flow grows.
The eigenvalues come from a hand-written routine for the 5 x 5 block (power-of-2 balancing, Hessenberg elimination,
Francis double-shift QR; the EISPACK balanc / elmhes / hqr algorithms). A non-finite Jacobian entry or a QR iteration
that does not converge within 30 iterations per eigenvalue fails closed: the run reports R_INTEGRATOR (MODEL_ERROR),
never a silent fallback. Error norm, rtol / atol, output grid, step body and records are unchanged.

Residual property (stated, not hidden): the guard guarantees that a growing mode is never damped; it does not make a
mode below the absolute tolerance accurate. In the analytic test (lambda = 0.05 +/- 2.4i started at 1e-13 < atol
1e-11) the amplitude grows at every sample, and once above the tolerance scale its growth rate matches Re lambda to
2.9e-5; the onset is late, so the final amplitude is 3.8e-4 of the exact value (before the fix: 4e-240). The same
holds for Python's nominal LSODA run in kind; both implementations' nominal errors are what the envelope procedure
measures.

## Tests

* `transient::tests::growing_mode_guard_resolves_an_unstable_oscillator`: lambda = 0.05 +/- 2.4i on the R45-192
  orbit output grid (5319 s, 150 samples) at the nominal tolerances. Fails on the code before the fix (growing mode
  damped between t = 29.6 s and 32.4 s), passes after.
* `transient::tests::growing_mode_guard_leaves_a_stable_oscillator_unchanged`: lambda = -0.05 +/- 2.4i; the guard
  never acts, nfev 14433 and the FNV-1a fingerprint of every sampled state equal those recorded before the fix.
* `transient::tests::radau_stability_function_matches_the_coefficients`, `eig_real_reproduces_known_spectra`,
  `eig_real_fails_closed_on_non_finite_entries`.
* `tests/transient_growing_mode_regression.rs`: R45-192 and R45-331 through the parity CLI at the nominal rtol, against
  their converged Rust T1 records, within the Python PROD P45 envelope E_py of the frozen v5 record (P_dev 0.00622,
  mdot 0.0465 x mdot_scale). Fails before the fix (|P_dev N - T1| = 0.0311), passes after. Fixture written by
  `plenum_v5_growing_mode_diagnosis.py fixture`.

## Blast radius

The integrator is private to `abep_gaspath::transient` and used only by `TransientRun::run` (transient_run,
transient_case, orbit_simulated); no other crate depends on abep-gaspath. The admitted abep-gaspath components
(compressor v2, filter stage v1 / v2) do not call it. Parity CLI replays, raw stdout before (`3eeb574`) and after the
fix:

| input set | requests | result |
|---|---|---|
| compressor v2 captured scoring inputs | 2368 | byte-identical |
| filter stage v1 / v2 captured scoring inputs | 1732 | byte-identical |
| plenum / feed v1 / v2 captured scoring inputs (incl. their transient vectors) | 3815 | byte-identical |
| v5 refinement grid at nominal rtol (Rust) | 2560 | 2557 byte-identical; R45-192, R45-331 (fixed) and R45-021 changed |

R45-021 is stable at the start (-7.3e-4 +/- 0.225i) but along the converged trajectory its lightly damped pair has
Re lambda > 0 on 41 % of the orbit (max 1.9e-3), where the guard acts: mdot_min_kgps changes by 2.2e-8 relative,
mass_residual_rel 1.3e-16 -> 1.2e-15, nfev 3168 -> 5478, P_dev and mdot_max unchanged. Every vector whose linearisation
stays stable is byte-identical. The admitted reports record the sha256 of every abep-gaspath source (provenance rule),
so the source change is recorded there as UNRECORDED_SOURCE_CHANGE until a scoring execution records it, as for
`a9dc2f5`; their outputs did not move.
