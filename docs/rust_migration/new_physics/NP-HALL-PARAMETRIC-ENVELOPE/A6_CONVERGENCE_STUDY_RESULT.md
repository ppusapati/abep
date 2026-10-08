# NP-HALL-PARAMETRIC-ENVELOPE addendum A6: convergence study result (XE)

`a6_convergence_study_result_v1.json` is authoritative. PARAMETRIC / NOT_VALIDATED. Scored once from the frozen study (manifest sha256 `07f52f7916bc1c49a7f20a87069f8fc59a0446d2cd9cfc1ff487f061b8af1a6d`, raw `b7f3adc30176f531a5a9c79353be3cb6b6e43fe9f40c6a5bd0f5cb57801fe868`).

**Outcome: STOP_NO_LEVEL_CONVERGED.**

| comparison | levels | failures |
|---|---|---|
| G(0) | A6-L0 vs A6-L1 | 11 of 22 fail |
| D(0) | A6-L0 vs A6-L0D | 7 of 22 fail |
| G(1) | A6-L1 vs A6-L2 | 6 of 22 fail |
| D(1) | A6-L1 vs A6-L1D | 4 of 22 fail |
| G(2) | A6-L2 vs A6-L3 | 6 of 22 fail |
| D(2) | A6-L2 vs A6-L2D | 5 of 22 fail |

Pass(k) needs every case to pass G(k) and D(k) (status, quiet class, thrust and I_d within 2 %). Production level = coarsest passing k in {0, 1, 2}; none: STOP.
