# M1 ARCHITECTURE PHYSICS READY — milestone audit v2

Audited commit `5c926829c091817627b035049fe56fadd00e659e` · governance A9.34, A9.36 · supersedes audit v1 (`m1_audit_v1.json`, sha256 `a3c497fc74e1d882e2776b2f1bbe3397c6b57e91a4b09cd778f6dcb22e635cd2`, kept unedited)

## Part 1 — all software paths connected: **YES**

The 196-state closure harness consumes all 13 required physics paths; none is BLOCKED (`m1_readiness_v1.json`, sha256 `c1422e817e9660d073a85bfc9edba82edbf8445f25b9e7898d18bca7617cf855`). Three paths await registered inputs: P-FEED-STABILITY, P-HALL-AIR, P-THERMAL. RF/ICP coupling is connected in layer (a).

## Part 2 — physics ready for architecture closure: **NOT READY FOR DECISIVE M2 HALL CLOSURE**

**Single critical blocker: HALL_NUMERICS_NOT_CONVERGED.**

- The XE v1 envelope ran (2268 records) but A3 is A3_NOT_ADEQUATE for XE and AIR, and the A6 convergence study is STOP_NO_LEVEL_CONVERGED: no level up to 4× cells (checked against 8×) or doubled duration agrees to 2 %; observed order 0.6–0.7 or non-monotone; 8 of 22 study cases fail numerically at every level.
- Every XE Hall point is an unknown. No Hall thrust value enters M2 while A6 remains STOP (A9.36).

Recorded, not critical: Hall AIR chemistry EXPLICITLY_BOUNDED (information only); AIR delivered flow DESIGN_VARIABLE_LIMIT; A4 conservation bound ≥ 0.251 m² / ≥ 0.048 mg/s with A4-REG-01 open; credible Hall set EMPTY.

## AIR chemistry audit at close

CA-HALL-AIR-v1 (576 cases) was still running when this audit closed (229 / 576). It cannot complete the AIR set (tier-1 sources not acquired) and is reported by the AIR chemistry lane.

## Decision

M1 NOT EXITED; M2 not started. Next: a narrow Hall numerical-method investigation (why HallThruster.jl is non-convergent at H1). After a converged Hall subset is demonstrated: rerun the registered envelope under a new addendum, then M2 directly.
