# NP-HALL-PARAMETRIC-ENVELOPE addendum A3: numerics adequacy result (AIR)

`a3_numerics_result_air_v1.json` is authoritative; this page restates it. PARAMETRIC / NOT_VALIDATED. Scored once from the frozen A3 raw envelope (manifest sha256 `d4ae65827fdefb75e84c69d304626a82cb450f2cb3a700c3c5552d4d8f06acaf`, raw `2556d20d68590d16124fe1fe4af6c106d2a6d4c31350eaabae20e290c8f190ba`).

**Outcome: A3_NOT_ADEQUATE**. delta_T = 32437818425450008.00 % at `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-LO|VD-180|MF-HI|CP-YLO-DIS|sgb-screen-09|A3-R1`; delta_I = 28673442433770048.00 % at `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-LO|VD-180|MF-HI|CP-YLO-DIS|sgb-screen-09|A3-R1`.

| v1 key | ref | status R0 / Rk | dT | dI | C-STATUS | C-QUIET | C-T | C-ID |
|---|---|---|---|---|---|---|---|---|
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-LO|VD-180|MF-LO|CP-YHI-REC|sgb-screen-02` | A3-R1 | PASS / PASS | 1433.49 % | 3079.39 % | ok | ok | FAIL | FAIL |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-LO|VD-180|MF-LO|CP-YHI-REC|sgb-screen-02` | A3-R3 | PASS / PASS | 27253.90 % | 25926.53 % | ok | ok | FAIL | FAIL |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B16|BP-LO|VD-180|MF-HI|CP-YLO-DIS|sgb-screen-03` | A3-R1 | PASS / PASS | 0.99 % | 1.14 % | ok | ok | ok | ok |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B16|BP-LO|VD-180|MF-HI|CP-YLO-DIS|sgb-screen-03` | A3-R3 | PASS / PASS | 0.11 % | 0.17 % | ok | ok | ok | ok |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-LO|VD-350|MF-LO|CP-YLO-DIS|sgb-screen-03` | A3-R1 | PASS / PASS | 1.14 % | 1.13 % | ok | ok | ok | ok |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-LO|VD-350|MF-LO|CP-YLO-DIS|sgb-screen-03` | A3-R3 | PASS / PASS | 2.26 % | 2.23 % | ok | ok | FAIL | FAIL |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-LO|VD-350|MF-HI|CP-YHI-DIS|sgb-screen-04` | A3-R1 | PASS / PASS | 0.49 % | 0.44 % | ok | ok | ok | ok |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-LO|VD-350|MF-HI|CP-YHI-DIS|sgb-screen-04` | A3-R3 | PASS / PASS | 0.21 % | 0.19 % | ok | ok | ok | ok |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B16|BP-HI|VD-180|MF-LO|CP-YLO-DIS|sgb-screen-01` | A3-R1 | NUMERICAL_FAILURE / NUMERICAL_FAILURE | - | - | ok | - | - | - |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B16|BP-HI|VD-180|MF-LO|CP-YLO-DIS|sgb-screen-01` | A3-R3 | NUMERICAL_FAILURE / NUMERICAL_FAILURE | - | - | ok | - | - | - |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-HI|VD-180|MF-HI|CP-YHI-REC|sgb-screen-06` | A3-R1 | PASS / OUT_OF_DOMAIN | - | - | FAIL | FAIL | FAIL | FAIL |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-HI|VD-180|MF-HI|CP-YHI-REC|sgb-screen-06` | A3-R3 | PASS / NOT_SUSTAINED | - | - | FAIL | ok | FAIL | FAIL |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-HI|VD-350|MF-LO|CP-YLO-REC|sgb-screen-08` | A3-R1 | NUMERICAL_FAILURE / OUT_OF_DOMAIN | - | - | FAIL | - | - | - |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-HI|VD-350|MF-LO|CP-YLO-REC|sgb-screen-08` | A3-R3 | NUMERICAL_FAILURE / NUMERICAL_FAILURE | - | - | ok | - | - | - |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-HI|VD-350|MF-HI|CP-YHI-REC|sgb-screen-06` | A3-R1 | OUT_OF_DOMAIN / NUMERICAL_FAILURE | - | - | FAIL | - | - | - |
| `AIR|G-AMINDHMAX-LH8603|BZ-P5B30|BP-HI|VD-350|MF-HI|CP-YHI-REC|sgb-screen-06` | A3-R3 | OUT_OF_DOMAIN / OUT_OF_DOMAIN | - | - | ok | ok | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-LO|VD-180|MF-LO|CP-YLO-REC|sgb-screen-05` | A3-R1 | OUT_OF_DOMAIN / OUT_OF_DOMAIN | - | - | ok | FAIL | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-LO|VD-180|MF-LO|CP-YLO-REC|sgb-screen-05` | A3-R3 | OUT_OF_DOMAIN / OUT_OF_DOMAIN | - | - | ok | ok | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-LO|VD-180|MF-HI|CP-YLO-DIS|sgb-screen-09` | A3-R1 | PASS / PASS | 32437818425450008.00 % | 28673442433770048.00 % | ok | ok | FAIL | FAIL |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-LO|VD-180|MF-HI|CP-YLO-DIS|sgb-screen-09` | A3-R3 | PASS / PASS | 16.65 % | 1.23 % | ok | ok | FAIL | ok |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-LO|VD-350|MF-LO|CP-YLO-REC|sgb-screen-08` | A3-R1 | OUT_OF_DOMAIN / OUT_OF_DOMAIN | - | - | ok | ok | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-LO|VD-350|MF-LO|CP-YLO-REC|sgb-screen-08` | A3-R3 | OUT_OF_DOMAIN / OUT_OF_DOMAIN | - | - | ok | ok | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-LO|VD-350|MF-HI|CP-YHI-REC|sgb-screen-03` | A3-R1 | OUT_OF_DOMAIN / OUT_OF_DOMAIN | - | - | ok | ok | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-LO|VD-350|MF-HI|CP-YHI-REC|sgb-screen-03` | A3-R3 | OUT_OF_DOMAIN / OUT_OF_DOMAIN | - | - | ok | ok | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-HI|VD-180|MF-LO|CP-YHI-DIS|sgb-screen-06` | A3-R1 | NUMERICAL_FAILURE / NUMERICAL_FAILURE | - | - | ok | - | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-HI|VD-180|MF-LO|CP-YHI-DIS|sgb-screen-06` | A3-R3 | NUMERICAL_FAILURE / NUMERICAL_FAILURE | - | - | ok | - | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-HI|VD-180|MF-HI|CP-YLO-DIS|sgb-screen-05` | A3-R1 | PASS / PASS | 60.29 % | 11.19 % | ok | ok | FAIL | FAIL |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B30|BP-HI|VD-180|MF-HI|CP-YLO-DIS|sgb-screen-05` | A3-R3 | PASS / OUT_OF_DOMAIN | - | - | FAIL | FAIL | FAIL | FAIL |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B16|BP-HI|VD-350|MF-LO|CP-YLO-DIS|sgb-screen-08` | A3-R1 | NUMERICAL_FAILURE / NUMERICAL_FAILURE | - | - | ok | - | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B16|BP-HI|VD-350|MF-LO|CP-YLO-DIS|sgb-screen-08` | A3-R3 | NUMERICAL_FAILURE / NUMERICAL_FAILURE | - | - | ok | - | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B16|BP-HI|VD-350|MF-HI|CP-YLO-REC|sgb-screen-02` | A3-R1 | OUT_OF_DOMAIN / OUT_OF_DOMAIN | - | - | ok | ok | - | - |
| `AIR|G-AMAXDHMIN-LH12|BZ-P5B16|BP-HI|VD-350|MF-HI|CP-YLO-REC|sgb-screen-02` | A3-R3 | OUT_OF_DOMAIN / OUT_OF_DOMAIN | - | - | ok | ok | - | - |
| `AIR|G-RP1|BZ-P5B16|BP-LO|VD-265|MF-MID|CP-YHI-REC|sgb-screen-06` | A3-R1 | NOT_SUSTAINED / PASS | - | - | FAIL | ok | - | - |
| `AIR|G-RP1|BZ-P5B16|BP-LO|VD-265|MF-MID|CP-YHI-REC|sgb-screen-06` | A3-R3 | NOT_SUSTAINED / PASS | - | - | FAIL | ok | - | - |

Criteria (addendum): C-STATUS v1 run status identical; C-QUIET quiet class (Id_rms_rel < 0.5) identical; C-T / C-ID relative thrust / I_d change <= 2 % when R0 is PASS. The consequence of the outcome is the addendum's, copied into the JSON; v1 records and numerics are unchanged.
