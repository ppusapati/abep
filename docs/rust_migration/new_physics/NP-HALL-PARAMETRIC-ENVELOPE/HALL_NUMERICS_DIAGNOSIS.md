# Hall numerical-method investigation (A9.36): Phase 1 diagnosis

`hall_numerics_diagnosis_v1.json` is authoritative; this page restates it. **DIAGNOSTIC ONLY, never score-bearing.**
PARAMETRIC / NOT_VALIDATED. Lane `lane-hall-numerics`, 2026-10-08. A3 (A3_NOT_ADEQUATE), the A6 STOP
(STOP_NO_LEVEL_CONVERGED) and every frozen record stay unchanged.

## Cause, in short

HallThruster.jl is not failing to converge in general. Under the same bridge numerics, its own SPT-100 regression case
passes the A6 2 % rules already at 0.5 mm cells. The H1 non-convergence has four separable causes:

1. **Observable (C1).** The v1 / A6 thrust is the thrust of the time-averaged state, m⟨nu⟩²/⟨n⟩. On oscillating
   discharges it is a biased, phase-sensitive statistic: 0.48–1.00 of the time-mean of the instantaneous thrust, and the
   ratio itself changes with resolution. This alone produced the A6 39 % thrust "failure": the time-mean thrust is
   49.0 / 51.1 / 50.6 mN at L0 / L1 / L2, while the A6 statistic gives 24.6 / 34.1 / 34.9 mN.
2. **Window (C2).** The v1 window (half of 2 ms × L-scaling) holds 1–30 oscillation periods. Same-numerics, longer
   runs (A6 D(k)) therefore differ by up to 14 %.
3. **Spatial order (C3).** The pinned scheme is first-order limited: upwind / backward-Euler electron energy and
   van Leer-limited MUSCL with Rusanov fluxes. Quiet H1 cases converge monotonically at observed order 0.63–0.69:
   - L0 → L1 differs by 1.3–2.6 %, so L0 (the v1 / A6 production level) cannot meet 2 %;
   - L1 → L2 differs by 0.8–1.75 %.
4. **Collapse (C4).** The persistent failures are discharge collapses at high B_peak and low flow:
   - I_d falls by orders of magnitude within microseconds;
   - n_e,min falls to 1e9–1e12 m⁻³ and T_e,max runs away to 25–165 eV;
   - the explicit heavy-species update then returns NaN.

   Every v1 BP-HI × MF-LO case fails.

The time step is converged (CFL 0.799 → 0.4 changes nothing beyond statistics), and the escape hatch is not involved.

## Hypotheses

| id | verdict | key evidence |
|---|---|---|
| H-OSC | **confirmed** (primary for thrust) | m⟨nu⟩²/⟨n⟩ ≤ ⟨m nu²/n⟩. Ratio 0.48–1.00 on runs with I_d RMS ≥ 0.1. The vendor regression test uses the per-frame mean. Low-frequency modes (0.5–1.5 kHz) have 1–2 periods per v1 window. |
| H-STEP | refuted | CFL 0.4 vs 0.799 at L1: quiet ≤ 0.01 %, oscillating 0.3–1.7 % (inside 2σ). Failures are bit-identical with the escape hatch disabled. |
| H-SCHEME | contributing (sets the order) | First-order-limited scheme, observed order 0.63–0.69: L0 is out of 2 %, L1 vs L2 is in. Reconstruction-off and Crank–Nicolson variants are in the run table. |
| H-FAIL | identified | Collapse to an extinct discharge, then NaN in the bulk (not at a boundary). Failure times 0.1–3 ms (one case at 15 ms). 10× initial plasma density does not ignite. CFL 0.2 sometimes survives the collapse as an extinct (I_d ~ 0) discharge. |
| H-TRANSPORT | not candidate-specific | Failure rate is flat across sgb-screen-01..09 (0.34–0.44) but varies with B_peak (0.12 → 0.66) and flow (0.19 → 0.69). The SGB profile is analytic and resolved (≥ 13 v1 cells across the narrowest width). |
| H-BENCH | H1-regime-specific | SPT-100 tutorial case at 160 / 320 / 640 cells: G(0) 0.57 / 0.87 %, G(1) 0.44 / 0.47 %, D(k) ≤ 0.01 %. |
| H-MODE | one resolution-dependent attractor | The A6 209 % case: L0 is oscillating and non-stationary (28.4 mN); L1 / L2 are quiet (70.3 / 70.9 mN, 0.9 % apart); A6 L3 (1× duration) is oscillating (38.0 mN). |

## Cause classification (A9.38)

| class | finding | evidence |
|---|---|---|
| solver / numerical | **yes — primary** | C1, C2, C3, C4 (NaN after collapse). The same numerics converge on the vendor benchmark. |
| transport-coefficient / model-domain | contributing, not candidate-specific | Rates are flat across the nine candidates. The failing corners lie farthest from the P5 identification domain. |
| boundary-condition | not indicated | Failures are bulk collapses. The vendor case with the same boundary conditions converges. |
| magnetic-field input | contributing through the regime | BP-HI: 66 % failures, 96 % oscillating. On the DBF-1 hardware (G-RP1, BZ-P5B16), BP-HI × MF-LO fails 27/27 and BP-LO × MF-HI is quiet 27/27. The P5 surrogate is not an H1 field, so an FE H1 B(z) (L-H1-BZ) can move these regime boundaries. |
| operating point | yes, with B_peak | MF-LO: 69 % failures. Low-flow quiet cases carry the largest discretization error. |
| genuine physical non-closure | **not established** | Extinction from the default start cannot be separated from a solver start-up limitation. These points stay unknowns. A non-closure under the surrogate B(z) is never eligible. |

## What A7 takes from this

- Observables: time-means of the per-frame instantaneous thrust and I_d over 1×–4× the v1 duration, with batch-means
  standard errors (C1, C2).
- Unknowns: statistically unresolved and non-stationary runs are unknowns, as are extinct and failed runs (C2, C4).
- Levels: production at L1 (0.25 mm), checked against L2 (0.125 mm) (C3).
- Demonstration: first on the RP-1 subset, then on the A6 study cases and fresh seeded cases the method was not
  selected on.

Raw per-frame outputs stay outside the repository; their sha256 values, the drivers and the bridge version are recorded in
the JSON.
