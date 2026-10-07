# NP-THERMAL-CATHODELESS preregistration v2

**Status: `PREREGISTERED_NOT_IMPLEMENTED`.** Method `NEW_PHYSICS`. Lifecycle state `PREREG_MODEL`. Model version `2.0.0`.
Validation status `NOT_VALIDATED`. Docs only.

* **What changes.** v2 is the consumer side of the matched interface `IF-ICP-THERMAL-v2` (A9.31 sec. 7). It changes only
  what that interface requires. Every other v1 criterion applies unchanged, by id (`inheritance_rule` in the JSON).
* **v1 stays immutable history.** That covers `prereg_v1.json`, `PREREG.md`, `prereg_lock_v1.json`, verification report
  v1 and VS-NET v1. The admitted v1 implementation (`abep-subsystems::thermal` 1.0.0) is not changed; v2 is added beside
  it.
* **Producer.** NP-ICP-NEUTRALIZER `prereg_v2.json`, committed alone before this record (`7a26d39`, lock
  `a180ceef37223467687d7d245ab790a172e8dad9ea4e90aa463d434383142287`).
* **Machine-readable record.** `prereg_v2.json` is authoritative. Lock: `prereg_lock_v2.json`.
* **Implementation gate.** No 2.0.0 code before this record and its lock are committed.

## 1. Matched interface

The key table below is the producer's table byte for byte. Canonical sha256 (sorted-key compact JSON of the table):
`33e495adadbe94a5113c5f6b9040156ec8309295cca15b812714038beaa51161`. A record whose producer table hashes differently, or that names `IF-ICP-THERMAL-v1`, is refused.

| id | key | role | plane | powered by | sign | receiver (producer text) |
|---|---|---|---|---|---|---|
| TK-R1 | `P_icp_slot_load_sum_W` | REFERENCE | LOAD_PLANE_SUM | - | >= 0 | none (closure reference IFI2-07, CONS-I3) |
| TK-R2 | `P_icp_rf_source_DC_W` | REFERENCE | LOAD (icp_rf_source) | RF_SOURCE | >= 0 | none (closure reference IFI2-03) |
| TK-R3 | `P_icp_rf_forward_W` | REFERENCE | RF_FORWARD | RF_SOURCE | >= 0 | none (closure reference IFI2-03 / IFI2-04) |
| TK-R4 | `P_icp_abs_W` | REFERENCE | PLASMA | RF_SOURCE | >= 0 | none (closure reference IFI2-04 / IFI2-05) |
| TK-R5 | `P_icp_collector_bias_W` | REFERENCE | LOAD (icp_collector_bias) | ICP_BIAS_SUPPLY (+ GROUND_FACILITY_ONLY supplies in a bench case, flagged) | >= 0 (a sinking supply is OUT_OF_DOMAIN, BUS2-08) | none (closure reference IFI2-06) |
| TK-01 | `Q_icp_rf_conversion_loss_W` | BOOKED | inside the RF source (load side of the slot plane) | RF_SOURCE | >= 0 | B_PPU_RF sub-account RF_SOURCE (or a registered electronics node) |
| TK-02 | `P_icp_rf_reflected_W` | BOOKED | RF_REFLECTED | RF_SOURCE | >= 0 | B_PPU_RF sub-account RF_SOURCE (or a registered electronics node) |
| TK-03 | `Q_icp_line_W` | BOOKED_OR_DEPOSITED | RF line | RF_SOURCE | >= 0 | B_PPU_RF sub-account RF_CHAIN, or N_MATCH for a registered co-located segment |
| TK-04 | `Q_icp_match_W` | BOOKED_OR_DEPOSITED | RF match | RF_SOURCE | >= 0 | N_MATCH iff match_colocated (ICD ICP-13), else B_PPU_RF sub-account RF_CHAIN |
| TK-05 | `P_icp_matching_DC_W` | BOOKED_OR_DEPOSITED | LOAD (icp_matching_network) | ICP_MATCH_ACTUATOR | >= 0 | N_MATCH iff match_colocated, else B_PPU_RF sub-account RF_CHAIN |
| TK-06 | `Q_icp_coil_ohmic_W` | DEPOSITED | RP-ANT | RF_SOURCE | >= 0 | registered conductor split over {N_ANTENNA, N_COLLECTOR, N_HOUSING, N_MOUNT}, weights summing to 1 (a registration may state N_ANTENNA 1.0 with its evidence); unregistered -> INCOMPLETE_EVIDENCE on both sides (no default split) |
| TK-07 | `Q_icp_plasma_wall_W` | DEPOSITED | PLASMA -> surfaces | RF_SOURCE | >= 0 | producer per-surface partition over the IN-10 v2 surface -> node map {N_VESSEL, N_ANTENNA (if exposed), N_MOUNT, N_COLLECTOR, N_HOUSING}; always emitted with the key |
| TK-08 | `Q_icp_radiation_W` | DEPOSITED_OR_EXPORTED | PLASMA | RF_SOURCE | >= 0 | consumer-registered partition f_rad over ICP nodes, H-1 pole faces and EXPORT (unchanged from v1 IK-05) |
| TK-09 | `Q_icp_extraction_W` | EXPORTED | PLASMA -> electron sink | RF_SOURCE | >= 0 | EXPORT |
| TK-10 | `Q_icp_outflow_upstream_W` | DEPOSITED_OR_EXPORTED | PLASMA -> OPEN_UPSTREAM | RF_SOURCE | >= 0 | RX-H1-FACE: registered H-1-facing receiver interface (consumer partition f_up) |
| TK-11 | `Q_icp_outflow_downstream_W` | EXPORTED | PLASMA -> OPEN_DOWNSTREAM | RF_SOURCE | >= 0 | EXPORT (never internal heat) |
| TK-12 | `Q_icp_bias_collector_W` | DEPOSITED | bias circuit -> surfaces | ICP_BIAS_SUPPLY | signed (per-surface Q_j check IFI2-08) | N_COLLECTOR (producer per-surface partition; another bias-connected module surface only through its IN-10 v2 node) |
| TK-13 | `Q_icp_bias_export_W` | EXPORTED | bias circuit -> electron sink | ICP_BIAS_SUPPLY | signed | EXPORT |
| TK-14 | `P_icp_flow_control_W` | VARIANT | LOAD (flow_control_icp_feed) | ICP_FEED_VALVE_DRIVER | >= 0 | installed variant -> INCOMPLETE_EVIDENCE until its receiver node is registered |
| TK-15 | `P_icp_assist_magnet_W` | VARIANT | LOAD (icp_assist_magnet) | ICP_ASSIST_MAGNET_SUPPLY | >= 0 | installed variant -> OUT_OF_DOMAIN (thermal D-05; NP-ICP DOM-06) |

**Consumer deposition (E-07 v2).**

| key | receiving |
|---|---|
| TK-R1..TK-R5 | References only: closures IFI2-03..IFI2-07 and CONS-I3. Never deposited. |
| TK-01, TK-02 | B_PPU_RF, sub-account RF_SOURCE (generator conversion loss; reflected power absorbed in the generator). Never on a neutralizer node; never counted twice. |
| TK-03 | B_PPU_RF RF_CHAIN, or N_MATCH for a registered co-located segment. |
| TK-04, TK-05 | N_MATCH iff `match_colocated`, else B_PPU_RF RF_CHAIN. |
| TK-06 | Registered split over N_ANTENNA, N_COLLECTOR, N_HOUSING and N_MOUNT. Unregistered → INCOMPLETE_EVIDENCE. The v1 implicit "all to N_ANTENNA" is retired. |
| TK-07 | The producer's per-node partition. The v1 consumer fallback f_pw is retired. |
| TK-08 | The registered f_rad (v1 IK-05, unchanged). |
| TK-09, TK-11, TK-13 | EXPORT, reported raw in `P_exported_W`. Never internal heat. |
| TK-10 | **RX-H1-FACE** (§ 2). |
| TK-12 | N_COLLECTOR (the producer's per-node partition of the signed C_j). |
| TK-14, TK-15 | Full NOT_INSTALLED records with value exactly 0. If installed: TK-14 → INCOMPLETE_EVIDENCE (no receiver registered); TK-15 → OUT_OF_DOMAIN (D-05, FT-12). |

**Checks** (all within ε_if, NUM-09).

| id | check | on failure |
|---|---|---|
| IFI2-01 | All 20 keys are present with complete value records and the producer lock matches | MODEL_ERROR; a non-EVALUATED key propagates its status (no zero-fill) |
| IFI2-02 | Every key ≥ 0 except TK-12 and TK-13 | MODEL_ERROR |
| IFI2-03 | RF-S: `P_icp_rf_source_DC_W` = `Q_icp_rf_conversion_loss_W` + `P_icp_rf_forward_W` | MODEL_ERROR |
| IFI2-04 | RF: `P_icp_rf_forward_W` = reflected + line + match + coil + `P_icp_abs_W` | MODEL_ERROR |
| IFI2-05 | PL: `P_icp_abs_W` = plasma_wall + radiation + extraction + outflow_upstream + outflow_downstream | MODEL_ERROR |
| IFI2-06 | B: `P_icp_collector_bias_W` = bias_collector + bias_export | MODEL_ERROR |
| IFI2-07 | S: `P_icp_slot_load_sum_W` = rf_source_DC + matching_DC + collector_bias (+ installed variants) | MODEL_ERROR |
| IFI2-08 | Per node: TK-07 share + TK-12 share ≥ −ε_if (the producer guarantees Q_j = L_j + F_j + W_j + C_j ≥ 0 per surface); partitions sum to their keys | MODEL_ERROR |
| IFI2-09 | Every partition used sums to exactly 1 | MODEL_ERROR |
| IFI2-10 | A v1 record, a retired key (`P_icp_bus_W`, `Q_icp_boundary_W`, `Q_icp_rf_generator_loss_W`, `Q_icp_bias_supply_loss_W`), a CPL-HALL-ON circuit key or a Hall-powered key | MODEL_ERROR |
| IFI2-11 | The configuration is CFG-CAP-OFF, SYNTHETIC or PARAMETRIC | CFG-FLIGHT-HALL-ON → NOT_EVALUATED (`CPL_HALL_ON_CONSUMER_VERSION_NOT_REGISTERED`) |

**Scenario members.**
- The thermal model makes one run per producer scenario member (NP-ICP ED-08).
- At minimum it runs the members the producer flags as extreme per key and per node.
- For TK-08 and TK-10, every member is combined with the registered f_rad and f_up.
- Temperatures are reported raw, per member and as the envelope. No member is a nominal.

## 2. RX-H1-FACE: the registered H-1-facing receiver interface

- **What it is.** A registered partition record `f_up`, not a node. It spreads `Q_icp_outflow_upstream_W` over
  H1_POLE_IN, H1_POLE_OUT, H1_WALL_IN, H1_WALL_OUT, H1_ANODE, N_MOUNT, N_HOUSING and EXPORT. The weights sum to exactly 1.
- **Why no new node.** v1 already registers every H-1 node that faces the ICP's upstream end, plus the ICP mount and
  housing. No node group, link type or property value is added.
- **Input.** An RI-PART record carrying the source (a view-factor / particle-interception computation under its own
  contract, e.g. K-P3-RAYS, or bench evidence), evidence class, uncertainty, applicability domain and validation status.
  It is registered per configuration and geometry id.
- **No default.** If TK-10 > 0 and no `f_up` is registered, the result is INCOMPLETE_EVIDENCE (FT-20).

## 3. Replaced items

- **HS-00.** Each watt enters once, through the interface of the supply that powers it:
  - RF chain → TK-01..TK-04 and TK-06..TK-11;
  - matching actuator → TK-05;
  - ICP bias supply → TK-12, TK-13;
  - Hall supplies → IF-HALL-THERMAL-v1;
  - PPU supply conversion loss of every slot → the bus ledger's `P_loss_W`, never an interface key here.
- **B_PPU_RF.** A booking boundary, reported raw by key and sub-account:
  - RF_SOURCE = TK-01 + TK-02;
  - RF_CHAIN = TK-03 / TK-04 / TK-05 when not co-located.

  Nothing is booked as a remainder. The true PPU conversion loss is the power model's PPU heat; it is not booked here a
  second time.
- **E-07.** Weights come from the producer partitions (TK-07, TK-12), the registered RI-PART partitions (TK-06, f_rad,
  f_up, Hall shares) or the fixed receivers above. Signed keys are allowed only for TK-12 and TK-13, under IFI2-08.
- **Node receive lists.** N_COLLECTOR gains TK-12. N_MATCH gains TK-05 and a co-located TK-03. N_MOUNT gains TK-06 and
  f_up shares. N_HOUSING gains f_up shares. The H-1 face nodes gain f_up shares. The full lists are in the JSON.
- **EB-03 / EB-04.** Exported: TK-09, TK-11, TK-13 and the EXPORT shares of f_rad and f_up. The electrical references
  are TK-R1..TK-R5; none of them is a spacecraft-side draw.
- **CONS-I1.** IFH-3, IFH-4 and IFI2-03..IFI2-08.
- **CONS-L1.** The v2 ICP account takes slots icp_rf_source, icp_matching_network and icp_collector_bias at `Plane::Load`:
  - deposited = node deposits of TK-03..TK-08, TK-10 and TK-12;
  - exported = TK-08 / TK-10 EXPORT shares, TK-09, TK-11 and TK-13;
  - booked = RF_SOURCE + RF_CHAIN;
  - the ledger `P_loss` of those slots is the supply loss outside the account.

  The residual must be < 2 %, evaluated by the SC-WP-05 system check.
- **AL-10.** Re-specified for IF-ICP-THERMAL-v2 on the unchanged VS-NET v1:
  - consistent sets with and without a co-located match;
  - every identity violated in turn;
  - a missing key, an INCOMPLETE_EVIDENCE key and a NOT_EVALUATED key;
  - a v1 record and a retired key;
  - a missing f_up and a missing TK-06 split;
  - a Hall-ON record;
  - a negative node total.

  The synthetic interface records are registered alone, with their sha256, before the scored run.
- **FT-13.** Violation of IFH-3, IFH-4 or IFI2-02..IFI2-09 → MODEL_ERROR.
- **Outputs.**
  - O-11: B_PPU_RF heat by key and sub-account.
  - O-13: adds TK-11, TK-13 and the f_up EXPORT share.
  - O-17: adds the interface ids, the producer lock, `scenario_member_id` and the partition-record sha256.
- **RI-PART.** Adds f_up and the TK-06 split. f_pw is retired.

## 4. Added and retired

**Added.**
- CONS-I3: the sum of TK-01..TK-13 destinations equals `P_icp_slot_load_sum_W`, so every ICP slot-load watt has exactly
  one destination.
- FT-19 (v1 / retired / Hall-powered key → MODEL_ERROR), FT-20 (missing f_up / TK-06 split → INCOMPLETE_EVIDENCE), FT-21
  (Hall-ON record → NOT_EVALUATED), FT-22 (negative node total → MODEL_ERROR) and FT-23 (`scenario_member_id`, no nominal).

**Retired.**
- The IK-07 remainder `Q_icp_boundary_W`.
- `P_icp_bus_W` as a reference.
- IFI-3..IFI-5, which were bounds and are replaced by exact identities.
- The f_pw fallback.
- The implicit 100 % N_ANTENNA coil split.

**Owner questions.**
- Resolved by A9.31 sec. 7: OQ-NPT-02, CF-04 and verification-report Q-01.
- Still open, unchanged: OQ-NPT-01, OQ-NPT-03..10 and Q-02.

**Not evaluated today.**
- RF/ICP heat loads: NOT_EVALUATED (NP-ICP 2 not implemented).
- f_up and the TK-06 split: INCOMPLETE_EVIDENCE.
- Hall-ON coupling heat: NOT_EVALUATED (credible set EMPTY; no consumer version of the coupling keys).
- Everything else as v1.

## 5. Admission

ADM-01..ADM-06 apply with v2 ids. VERIFIED requires:
- AL-01..AL-11 (with AL-10 v2);
- every CONS criterion, including CONS-I3;
- FT-01..FT-23;
- DET, IV-01 and IV-02;
- the producer key-table hash equal to `key_table_sha256`.

## 6. Scope traceability (A9.31 secs. 7-10)

The JSON quotes each bullet and maps it to field ids. Summary:

| A9.31 | fields |
|---|---|
| sec. 7: matched v2, keys, Q_j = L_j + C_j, the six mappings, no loss, no double count, v1 history, versioned v2 | matched_interface, consumer_deposition, IFI2-01..11, rx_h1_face, HS-00 v2, B_PPU_RF v2, E-07 v2, CONS-I3, CONS-L1 v2, retired_items, predecessor |
| sec. 8: bus_power_boundary_a9_v2, IF-ICP-BUS-v2, no flight cathode load, physical loads, 1.5 kW in assessment | CONS-L1 v2 slot planes, TK-R1..R5, EB-04 v2, EX-01 / EX-02 / EX-08 / FT-10 (inherited) |
| sec. 9: NP-ICP v2 defects | producer resolutions and energy_disposition; consumer scenario members; retired convenience splits |
| sec. 10: OQ-NPICP-08 / -15 / -11 | matched_interface, OQ-NPT-02 resolved, IFI2-11, FT-21; the other sec. 10 items are producer-only |
