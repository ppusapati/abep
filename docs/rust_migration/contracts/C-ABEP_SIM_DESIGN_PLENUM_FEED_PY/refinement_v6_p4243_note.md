# Plenum / feed v6: P42 / P43 refinement envelopes per vector; a second cause found, v7 not registered (STOP)

Status of contract v6 (`parity_prereg_v6.json`, sha256
`60f8bc2482e967b888f1b1421f8b7b7c907a92fed4b0a88f5d3e65ad30deab5a`, registered in `aca62b3`):
**REGISTERED_NEVER_SCORED, superseded (coordinator decision 2026-10-07): P45 envelope dominated by an unstable-start
stratum and a silent reference defect.** Its frozen record `transient_envelope_v6.json` (sha256
`439ae2dd1f5f935db7ad1e3538c538c0cad7a11af333752e4c9fedbbeaa7002c`, `eec930a`) stays unedited as evidence
(`refinement_v6_p45_note.md`). The reference defect is recorded in `div_p_ref_01_lsoda_unstable_loops.json`
(DIV-P-REF-01). The successor v7 is **not registered**: the per-vector analysis of P42 / P43 required before it found
a second, different cause (below), and the decision rule for that case is to stop and report.

Reproduce (refinement vectors only, never a scoring vector):
`python3 scripts/rust_migration/plenum_v6_p4243_refinement_analysis.py rows ROWS.json`, then
`... classes ROWS.json CLASSES.json`.

## Classification used for the analysis

Per vector, the reference Jacobian's dynamic 5 x 5 block at the equilibrium of every event of the fixed sequence
(E0 hold, E1/E2 setpoint +10 % and back, E3/E4 feed path x0.8 and back, E5/E6/E7 supply x0.9, x1.1, back):

* U: some event equilibrium has an eigenvalue with Re lambda > 0;
* S-alleq: stable, every event has a reachable unsaturated equilibrium;
* S-closed: stable, at least one event has no reachable unsaturated equilibrium (the valve closes to u = 0 or would
  exceed full opening).

The design point alone is not enough: R43-PROD-033 is stable at E0 (-0.0033 +/- 4.65i) but unstable at E1 / E5
(+0.0115 / +0.013 +/- 4.65i), and its trajectory has Re lambda > 0 on 36-60 % of most events.

Counts: PROD S 1340, U 51, not run (dead-head refusals) 145; REF S 446, U 13, not run 53.

## Result (max over vectors of (|N - T2| + |T1 - T2|) / s_F)

**Same cause as P45 (unstable loops), explained by the class:** every grown P42 envelope and the grown P43 PROD
envelopes sit in U:

| family (PROD) | py S-alleq | py U | rust S-alleq | rust U |
|---|---|---|---|---|
| F42.p | 8.6e-5 | 6.5e-3 (R42-PROD-018) | 5.1e-6 | 2.3e-4 |
| F42.ucmd_end | 2.7e-4 | 2.0e-2 (R42-PROD-018) | 2.2e-5 | 9.0e-4 |
| F43.valve_travel_total | 2.9e-2 | 0.18 (R43-PROD-033) | 2.4e-3 | 9.5e-3 |
| F43.overshoot | 2.8e-3 | 0.31 | 9.2e-5 | 0.26 |

**A different cause: xO extrema of segments in which the valve closes.** In S-closed vectors the xO family alone is
4-5 orders above S-alleq. For the four vectors that attain these maxima (R43-PROD-338, R43-PROD-307, R43-REF-846,
R43-REF-809) the loop is stable throughout: no Re lambda > 0 at any event equilibrium nor along the converged reference
trajectory (4001 points per event), with u at rounding level (|u| down to 1e-11 ... 1e-41) in the closing events E1 /
E5 / E6. The converged runs of the two implementations disagree:

| F43.xO | S-alleq | S-closed |
|---|---|---|
| PROD python / rust | 1.6e-6 / 5.0e-7 | 3.2e-4 (R43-PROD-338) / 1.6e-4 (R43-PROD-307) |
| REF python / rust | 1.2e-8 / 1.6e-10 | 6.8e-4 (R43-REF-846) / 1.2e-3 (R43-REF-809) |

Mechanism: both implementations define xO = NaN where the molar flow is not positive (u <= 0), and xO_min / xO_max are
nanmin / nanmax over the samples of a segment. In a segment where the valve closes, u sits at rounding level
(-1e-20 ... -1e-41, or exactly 0): whether a sample enters the extremum is the sign of rounding noise in u, while the
plenum composition drifts with the valve shut. Example R43-REF-809, segment 6 xO_min: Rust N 0.5171633, T1 0.5159402,
T2 0.5171633; Python T2 0.5160670. The v3 procedure already treats the None-ness of single xO samples by a proximity
rule (|u_py,j| within the F42.u envelope) but not the extrema built from them, so the effect enters the F43.xO
envelopes directly (REF combined bound 1.9e-3 against a family convergence of 1e-8 to 1e-10).

## What v7 would need (for the decision; nothing registered)

1. Event-wise stability class (as above), computed by both implementations; the instability treatment the
   coordinator specified for P45 then applies to P42 / P43 too.
2. A rule for xO extrema of segments with a closing valve (input-defined: an event without a reachable unsaturated
   equilibrium), e.g. reported with their sign sensitivity and not scored, as the v5 cascade diagnostics, with xO
   scored through the P42 samples under the existing None-ness proximity rule.
3. Held-out coverage of the unstable stratum: the registered held-out sets are P42 16, P43 16, P45 4 vectors; with
   about 3 % (P45) to 4 % (P42 / P43) unstable vectors the stratum would almost surely be empty, so its rules would go
   unexercised. A registered class-stratified held-out draw (and enough unstable refinement vectors, at about 5-10 s
   of Rust and 10-30 s of Python per unstable run) is needed for the unstable rules to be non-vacuous.
