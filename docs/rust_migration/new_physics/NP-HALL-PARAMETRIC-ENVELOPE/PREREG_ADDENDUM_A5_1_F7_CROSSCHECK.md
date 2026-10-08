# NP-HALL-PARAMETRIC-ENVELOPE addendum A5.1 — F7 cross-check tolerance

`prereg_addendum_a5_1_f7_crosscheck.json` is authoritative; this page restates it. Status
**PREREGISTERED_BEFORE_EVALUATION**. Hash lock: `prereg_addendum_a5_1_lock.json`. It amends one A5 clause (the F7
cross-check); A5 and every other file are unchanged.

## What happened

- The first harness run under A5 refused with MODEL_ERROR while gathering its inputs. The first F7 member checked
  (`A0.25_Ld10_phi0.9|F4-FIL-T0.5|T6-A1-U2-D0-Ti6Al4V-H0.5|V0.001|P0.01`, context `cll_a0.2|F4-FIL-T0.5|WALL-G0`)
  gave a Rust statewise minimum of 1.614853955983687e-9 kg/s against the committed 1.6148539559836865e-9 kg/s, a
  difference of 1 ulp.
- Cause: the committed F7 Pareto blocks are the Python reference capture. The admitted F7 contract reproduces them
  within its ULP_BOUNDED class (k_ulp 4 or r_rel 1e-9), not bit for bit: 23401 of 23622 float leaves are
  bit-identical, and the maximum difference is 24 ulp. The A5 "bit for bit" clause was a registration error.
- Nothing was seen. The refusal came before any A5 evaluation: no flow, efficiency, comparison, multiplier, verdict or
  cell was computed.

## Rule

- Every state of the Rust rerun is still in domain; otherwise MODEL_ERROR, as before.
- The statewise minimum now has to agree with the committed value within max(4 ulp, 1e-9 relative); otherwise
  MODEL_ERROR. Both numbers are the F7 contract's tolerances, with r_rel applied relative to the committed value. That
  is stricter than the contract's max(1, |py|) form, which would be vacuous at flows near 1e-9 kg/s.
- A5 uses the Rust rerun values, because Rust is the authoritative implementation (A9.24 item 1). The committed Python
  capture serves only as the cross-check reference.
- The record reports, per member, the committed and rerun minimum and their ulp difference.
