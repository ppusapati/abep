# NP-THERMAL-CATHODELESS 2.0.0 — verification report v1

Human-readable companion of `verification_report_model_v2_v1.json`, added on 2026-10-07 after that report. The JSON governs and is unchanged. Report v2 (`verification_report_model_v2_v2.json` / `.md`) re-evaluates the verdict under `admission_rule_v2` as written.

| item | value |
|---|---|
| model | `NP-THERMAL-CATHODELESS` 2.0.0, the consumer of the matched IF-ICP-THERMAL-v2 |
| prereg | lock `727689fe…`, prereg_v2.json `6828f3e2…`, producer anchor `a180ceef…`, key table `33e495ad…` |
| implementation | `a18ceb5` (AL-10 v2 record registered alone, sha256 `3419b518…`) and `2f4b7fc` |
| verdict stated | IMPLEMENTED_UNVERIFIED "pending the producer's verification". The rule has no such condition; report v2 corrects this. |
| validation status | NOT_VALIDATED |

## What was verified

- **AL-10 v2 consistent sets** (match co-located and not):
  - every key lands on its registered receivers with its weights;
  - TK-09 / TK-11 / TK-13 go to no node;
  - TK-01 / TK-02 are booked at B_PPU_RF RF_SOURCE;
  - TK-04 / TK-05 go to N_MATCH iff co-located, else RF_CHAIN;
  - TK-10 shares exactly f_up;
  - CONS-I2 and CONS-I3 hold, and no remainder key is booked.
- **Signed TK-12** with a positive node total converges.
- **Refusals:**
  - MODEL_ERROR: IFI2-02..IFI2-09, a missing key, a v1 record, `P_icp_bus_W`, a Hall-powered key, a negative node total;
  - INCOMPLETE_EVIDENCE: an INCOMPLETE_EVIDENCE key, a missing f_up, a missing TK-06 split;
  - NOT_EVALUATED: a NOT_EVALUATED key, CFG-FLIGHT-HALL-ON.
- **FT-19:** the two model versions never cross. **FT-23:** provenance carries the scenario member and the producer lock. **DET:** two runs give identical JSON.
- **v2 lock:** `GovernedContextV2` verifies the lock, its predecessor, the producer anchor and the key table on both preregistrations; a changed prereg byte is refused.
- **LC-18 (power lane):** IF-ICP-BUS-v2 BK-01..BK-03 enter the ledger exactly at the load planes; P_bus = P_W / (η_slot η_FE); the CONS-L1 v2 ICP account closes with the ledger P_loss outside the account.

The v1 paths (`run_case`, the IF-ICP-BUS-v1 consumer, CONS-L1 v1, `vs_net_v1.json`) are byte-identical to base `1c9e87f`.
