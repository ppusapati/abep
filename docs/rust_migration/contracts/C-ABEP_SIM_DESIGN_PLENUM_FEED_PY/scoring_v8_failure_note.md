# Plenum / feed v8: PARITY_FAIL in one stable-stratum vector (P43-PROD-S-010); diagnosis

Contract v8 (`parity_prereg_v8.json`, sha256 `05192a43d1b5dadff79a0f82ebdf1fee71900a88820ec15a9d82a49eefad973b`,
`8943d26`), frozen record `transient_envelope_v8.json` (`29430be1…`, `7262ad2`), single scoring execution (seed
731905373), report `parity_report_v8.json` (`330bbdd`): **PARITY_FAIL / NOT_ADMITTED, 17 per-test failures, all in
P43-PROD-S-010.** The report stays as committed; nothing is re-scored, no tolerance is changed. This note is a
diagnosis after the fact (reproduce: `python3 scripts/rust_migration/plenum_v8_failure_probe.py OUT.json`, which reruns
only that held-out vector and reads the captured outputs).

## What passed

* Unstable stratum (the v8 change): the class of all 77 transient vectors agrees; 373 UNSAT equilibria of the 32 U
  vectors scored on re_lead / im_lead with 0 failures (largest used fraction of the bound 4.8e-3) and 0
  NOT_CONVERGENT; Jacobian entries 0 failures. Every U time-domain output is reported (ILL_POSED_UNSTABLE_EQUILIBRIUM).
* ST-P-01: 77 / 77 (36 EVALUATED, 32 UNSTABLE_EQUILIBRIUM, 4 REFUSED P43 records; the 4 P42 and 1 P45 dead-head
  vectors raise the same ValueError in the plain and the assessed request). The verdict counted it; the report writer did not print its detail (harness gap: the integrity section
  lists only NN / VS / EV / IMG keys). Recomputed from the captured Rust outputs by the probe script: identical.
* Every other stable vector, every non-transient entry, determinism, conservation (CONS-P-01..04), integrity
  (NN-P-01/02, VS-P-01, EV-P-01, IMG-CHECK), domain / error parity and the proximity limit.

## The failing vector

P43-PROD-S-010 (Kp 7.13, Ti 0.131 s, f_valve 1 Hz, authority 3.05, V 5.6e-3 m^3, r0 0.01 Pa) is stable at every
event equilibrium, but only lightly damped: the leading pair is -0.0011 +/- 2.018i (E5) to -0.0167 +/- 1.807i (E3);
decay time 1 / |Re lambda| = 60 to 900 s against a 60 s event window. The valve oscillates over most of its range
(P42 samples of the same inputs: u from 0.05 to 0.53 in the last third of E1), and the record carries
TRANSIENT_NOT_SETTLED_WITHIN_WINDOW in both implementations at every tolerance.

The observable is well posed: the converged answers of the two implementations agree (|x_rust,T2 - x_py,T2| / s_F
1.6e-8 to 2.4e-8 for F43.p and setpoint_frac, 2.2e-7 for F43.u, 1.5e-7 for F43.overshoot, 6.8e-7 for F43.mdot,
2.4e-5 for valve_travel_total). What exceeds the bound is the nominal-tolerance error, mostly the Python
reference's (LSODA rtol 1e-5):

| family (worst leaf) | e_python | E_py (v7 S) | e_rust | E_rust (v7 S) |
|---|---|---|---|---|
| F43.p (metrics/6/P_max_Pa) | 5.5e-5 | 3.6e-5 | 4.5e-6 | 5.1e-6 |
| F43.setpoint_frac | 5.5e-5 | 3.6e-5 | 4.5e-6 | 5.1e-6 |
| F43.mdot | 1.5e-3 | 1.0e-3 | 1.2e-4 | 9.0e-5 |
| F43.u | 4.8e-4 | 3.6e-4 | 3.8e-5 | 1.6e-5 |
| F43.overshoot | 5.5e-4 | 3.0e-4 | 4.7e-5 | 2.7e-5 |
| F43.valve_travel_total | 0.059 | 0.030 | 0.0044 | 0.0022 |

(e = (|x_N - x_T2| + |x_T1 - x_T2|) / s_F of the same implementation.) Both implementations' own estimators exceed
their frozen grid maxima on this vector; the cross-implementation difference |x_rust,N - x_py,N| then exceeds
(E_py + E_rust) s_F by 1.05x (F43.p) to 1.7x (valve_travel_total).

## Cause

The stable-stratum envelope is the maximum over the v7 refinement grid, and the grid hardly samples the near-neutral
tail of the stable stratum. Of the 640 P43 PROD S refinement vectors 15 have a decay time above the 60 s window and 1
above 300 s; none is as lightly damped as P43-PROD-S-010 (least damped: max Re lambda -0.0033). The nominal error of
a lightly damped oscillation grows as its damping goes to zero (the phase error accumulates over many cycles that do
not decay within the window), continuously toward the unstable stratum, where v8 declared the time-domain outputs
ill-posed. This is the registered exceedance risk of the grid maximum (exchangeability note: about 1.8 % per
implementation and family for P43 PROD S) materialising in a part of the input space the grid under-covers. It is
not a Rust defect (the Rust nominal error is 10x smaller than the reference's and both converge to the same answer)
and not an ill-posed observable.

Per the decision rules the verdict is PARITY_FAIL; no envelope is regenerated, extended or edited, and no tolerance
is changed. A new contract version for the stable stratum is a coordinator / owner decision (A9.31 sec. 1); the
coordinator ruled out a later version for the unstable stratum only.

## Options for the coordinator (nothing registered)

1. Keep v8 as the result: stable-stratum transients stay PYTHON_REFERENCE; the unstable-stratum treatment (class,
   eigenvalues, typed status) and the non-transient entries are validated in this execution but not admitted (an
   admission is all-or-nothing per contract).
2. A successor with an input-only damping sub-stratum of S (for example decay time 1 / |max Re lambda| above the event
   window, computed from the same equilibria as the class) with its own refinement draw and envelopes, so that the
   near-neutral tail is sampled; fresh seeds, the frozen v7 / v8 records unedited.
3. A successor that scores the near-neutral S tail like the unstable stratum (class and eigenvalues scored,
   time-domain reported), if the coordinator regards a decay time far beyond the window as practically ill-posed.
