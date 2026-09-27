# H-1 magnet/coil qualification basis (fo_magnet_coil_qualification), v1 — DRAFT for owner review

| item | value |
|---|---|
| lane | `fo_magnet_coil_qualification`, trigger `T_PIVOT_MAGNET_COIL_QUALIFICATION`, owner disposition `od_hardware_pivot` (`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json`, including `controls_addendum_2026_09_27` and `execution_directive_2026_09_27`) |
| data | `magnet_coil_qualification_v1.json` (generated), schema `magnet_coil_qualification_v1.schema.json` |
| builder | `build_magnet_coil_qualification.py` (`--check` verifies the committed JSON) |
| test | `tests/test_magnet_coil_qualification.py` |
| status | **DRAFT_FOR_OWNER_REVIEW**. No candidate is qualified, selected, passed or failed. |

**Hard statements.**
- No lifetime verdict is produced; every candidate carries `lifetime_verdict = null`.
- Generic MIL class-C derating (NASA EEE-INST-002) and generic MMPA family values are **reference evidence only**
  (MCQ-REF-01, MCQ-REF-02). They never produce a lifetime verdict.
- Thresholds that are not in the RFP are **PROPOSED** (MCQ-PT-01..04).
- No Hall transport closure, screening candidate or P5 value is used as a design or performance value. P5 calibration
  nuisance (registration, coil shape) is never a magnet variable.
- No architecture winner is declared. The magnet/coil set is common to `hall_only`, `rf_hall` and `ecr_hall`; only the
  `ecr_magnet` is arm-specific.
- No 15,000 h extrapolation from an unadmitted Hall closure (control C6).

## 0. Milestones
- **A (conditional selection):** supported only as a **condition list**: "architecture X is baseline provided H-1 (and,
  for `ecr_hall`, the PIM-ECR magnet) passes MCQ-QT-01..09 at the measured temperatures". The set does not
  discriminate architectures. It gates S1 readiness (§7) on the path S1 → LOCK-2 → HW-0 / HW-RF / HW-ECR.
- **B (physics-backed selection):** not supported directly. B(z) at the actual coil currents and temperatures
  (MCQ-W4-03) is a W5 held-out candidate. No Hall closure is used here.
- **C (proposal/PDR freeze):** supports the magnet/coil life and thermal items (lane 15 `hall_magnet` and `ecr_magnet`
  nodes).
- **To reach the next step:**
  - S1: all MCQ-S1-* items delivered, plus owner answers to MCQ-OQ-01..03 and MCQ-OQ-06.
  - Milestone C: the MCQ-QT-01 life basis at the measured hot spot, the MCQ-QT-04 AO results, lane 15 adoption of
    MCQ-TL-*, and an H-1 thermal model correlated to S1 data.

## 1. H-1 requirement basis
**B(z) magnitude class.** No Vyovrinda B_max exists: lane 17 lists `B_max_T` and `magnet_setting_schedule` as TBD. The
magnet and coil options are screened against published orders of magnitude only:
- about 150 G, an illustrative textbook value (lane 17 EV-B2);
- about 200 G, typical of the xenon database (lane 17 EV-B4);
- 0.08752 T, the ECR fundamental resonance at 2.45 GHz (lane 20 EM-RESONANCE-B).

The ECR resonance field is **4.4–5.8×** the Hall magnitude class (derived MCQ-D-06). An ECR magnet is therefore the
strongest local field source near MC-1. Its fringe field in the channel falls under lane 17 INV-B3 and lane 06
INV-MAG / CONFOUNDED_MAGNETIC. Its own demagnetization exposure is covered by MCQ-QT-09.

**Operating temperatures are all TBD.** They require the H-1 thermal model with the lane 15 `hall_magnet` inputs
(`coil_current_A`, `coil_resistance_ref_ohm`, `external_heat_W`, `rejection_paths`, `copper_model`) and the
`ecr_magnet` inputs, followed by the S1 measurement (MCQ-W4-01).
- Reference context only (MCQ-REF-05, MCQ-D-05): on NASA-300M/300MS (10–20 kW, xenon), the inner-coil outer-layer
  downstream thermocouples read **374.8–535.6 °C** (Kamhawi et al. IEPC-2013-444, Table 4, p. 21). That is at least
  134.8 K above the MW 16-C polyimide class.
- These readings come from a different power class and are surface, not hot-spot, readings. They motivate measurement;
  they set no limit for H-1.

## 2. Candidate matrix (actual products; all values are supplier-typical, level 5 unless stated)
| id | product | key sourced data | limitation | status |
|---|---|---|---|---|
| MCQ-PM-01 | Arnold **Recoma 33E** (Sm₂Co₁₇) | Br 1.16 T nom. (min 1.14); HcJ min 1750 kA/m; α(Br) −0.035, α(HcJ) −0.25 %/°C (20–200 °C); max. recommended use 350 °C; T_c 825 °C; demag curves 20–350 °C (graphical) | max temperature "may be considerably lower" with strong demag fields or a low load line (p. 2, fn 3); curves not digitized | CANDIDATE |
| MCQ-PM-02 | Arnold **Recoma 35E** | lane 15 record `pm_sm2co17_recoma35e`; summary-table max. operating temp 300 °C (agrees) | as PM-01 | CANDIDATE |
| MCQ-PM-03 | Arnold **Recoma HT360/420/470/520** | Br typ 1.06/1.02/0.97/0.94 T; HcJ min 1600 kA/m; max. operating temp 360/420/470/520 °C; RTC(HcJ) of HT520 0.14 %/K (vs 0.26 for 28HE); each batch qualified by irreversible loss at the nominal temperature | maxima are "operating at a very low load line" (p. 4, fn 1); coating needed above 400 °C in an oxidizing atmosphere (p. 7) | CANDIDATE |
| MCQ-PM-04 | **EEC UHT SmCo** | "for use at temperatures up to 550 °C"; DS1 ion-engine heritage (manufacturer claim, verify) | no grade datasheet or curves accessed | CANDIDATE_INCOMPLETE_DATA |
| MCQ-PM-05 | Arnold **N42SH** | lane 15 record; catalog "Tw max" 150 | "Tw" undefined in the accessed text (verify) | CANDIDATE |
| MCQ-PM-06 | Arnold **N35EH** | Br 1.20 T nom.; HcJ min 2388 kA/m; α(Br) −0.12, α(HcJ) −0.47 %/°C (20–200 °C); T_c 310 °C; catalog Tw max 200; curves −40…220 °C with Pc lines | curves show **minimum** HcJ; coating required | CANDIDATE |
| MCQ-PM-07 | Arnold **N38AH** | Br typ 1.24 T; HcJ min 2626 kA/m; α(HcJ) −0.393; catalog Tw max 220 | grade datasheet and curves not accessed | CANDIDATE_INCOMPLETE_DATA |
| MCQ-EM-01 | **Cu + polyimide MW 16-C** (Remington) | Class 240 °C (ASTM D 2307); NEMA MW 16-C ↔ IEC 60317-46; cut-through 500 °C+ | a **material** class, not an EIS class; E595 value not retrieved | CANDIDATE |
| MCQ-EM-02 | Cu + glass fiber/silicone varnish MW 44-C | NEMA class 200 | no supplier datasheet; silicone outgassing to verify | CANDIDATE_INCOMPLETE_DATA |
| MCQ-EM-03 | **Ceramawire HT, Kulgrid 28 (27 % Ni-clad Cu)** | −450 to +1000 °F continuous (−267.8 to 537.8 °C), 1500 °F short term; 150 V DC (≤ #32) / 200 V DC dielectric rating; porous (bake 125 °C, 12 h); Ni migration above 600 °F; life "> 2500 h at 1000 °F and above" | life statement has no end point; not a 15,000 h basis | CANDIDATE |
| MCQ-EM-04 | Ceramawire HT, all-nickel | 138 / 228 Ω·cmil/ft at 500 / 1000 °F, i.e. **5.13× / 5.39×** Kulgrid (MCQ-D-02) | ferromagnetic conductor (verify its effect with the MC-1 model); high I²R | CANDIDATE |
| MCQ-EM-05 | anodized-Al wire in a high-CTE ceramic body (US 9,508,486 B2) | construction only (abstract) | no temperature rating read | NOT_SOURCED_FOR_SELECTION |
| MCQ-EM-06 | mineral-insulated (MgO) conductor | none | the only open source found returned HTTP 403 | NOT_SOURCED_FOR_SELECTION |
| MCQ-EIS-01 | ceramic-potted winding (NASA HERMeS practice) | potting reduces hot spots, but cracks under startup gradients and CTE mismatch (Myers et al. 2016 p. 5) | compound not named | CANDIDATE_INCOMPLETE_DATA |

**Load-line / permeance constraint.** Every supplier maximum temperature is an upper bound for the **grade**, not a limit
at the H-1 permeance coefficient. The MMPA glossary (p. 26) defines the operating slope B_d/H_d, also called the
permeance coefficient or load line. The design check is lane 15 `irreversible_loss_criterion` with the knee field
H_knee(T) read from the curve at ≥ the magnet temperature. The linear-RTC HcJ estimates MCQ-D-04 are consistency checks,
**never knee fields**:
- Recoma 33E: 962.5 kA/m at 200 °C;
- N35EH: 367.8 kA/m at 200 °C;
- N42SH: 453.7 kA/m at 150 °C.

The reversible Br factors at the top of each coefficient range (MCQ-D-03) are 0.937 (33E), 0.784 (N35EH) and 0.844
(N42SH).

**Vacuum and outgassing.** Arnold (RECOMA HT pp. 1, 8) states that coated Sm₂Co₁₇ is preferred for space and in-vacuum
use. No ASTM E595 value was retrieved for any candidate enamel, potting or coating; all of them are TBD (MCQ-QT-03).

## 3. Qualification tests (what each candidate needs)
| id | test | phase |
|---|---|---|
| MCQ-QT-01 | EIS thermal endurance / coil life basis: IEC 60216-1 TI/HIC for materials, then a system evaluation (UL 1446, or IEC 61857 — verify) or a coil life test in vacuum at ≥ the measured hot spot | material data before S1; system test in parallel with S1; done before C |
| MCQ-QT-02 | PM demagnetization exposure: per-lot irreversible loss at T_max,design + margin at the design permeance coefficient | before S1 for any PM on H-1 / PIM-ECR |
| MCQ-QT-03 | vacuum bake-out and outgassing screen; the TML/VCM criterion reported by Scialdone et al. p. 1 is PROPOSED (MCQ-PT-03) | before S1 |
| MCQ-QT-04 | O₂ / atomic-O exposure, run through AO lane AOL-EX-02 and AOL-WC-04 | coupons with S1; witnesses from S1 on |
| MCQ-QT-05 | thermal cycling of a potted sacrificial coil | before S1 |
| MCQ-QT-06 | coil temperature: 4-wire resistance (average) plus hot-spot thermocouples; the offset is measured | bench before S1; confirmed in S1 |
| MCQ-QT-07 | B(z) versus temperature and coil current (cold map + heated soak; W3 draft HW-MC-03/04) | before and during S1 |
| MCQ-QT-08 | insulation resistance / dielectric withstand baseline and trend (AOL-PM-06) | baseline before S1 |
| MCQ-QT-09 | ECR magnet ↔ Hall circuit: fringe field (INV-B3) and PM demagnetization exposure at the maximum Hall coil current | before the LOCK-1 input on HWQ-05 |

**Coil temperature measurement.** The resistance method gives the **average** winding temperature. It uses potential
probes at the winding (Jankovsky 1999, NASA/TM-1999-209075, p. 4) and R = R₀[1 + a(T − T₀)]: NBS α₂₀ = 0.00393/K in the
lane 15 records; HERMeS used a = 0.00386 (Myers et al. p. 7). Thermocouples on the coil give local values: NASA-300MS
used type-K on the inner electromagnet (Kamhawi et al. p. 11). The insulation class applies to the **hot spot**, so the
hot-spot/average offset is measured on the built coil (MCQ-QT-06). It replaces the EEE-INST-002 +10 °C convention,
which is reference only.

## 4. Requirements that other lanes can adopt directly (all PROPOSED)
- **W3 (hardware definition):**
  - MCQ-W3-01: EIS selected with a stated class and an endurance basis; compared with the measured hot spot.
  - MCQ-W3-02: the hot-spot margin is an owner decision.
  - MCQ-W3-03: PM record (grade, coating, lot, permeance coefficient) plus the knee check at ≥ T_magnet.
  - MCQ-W3-04: PMs coated or encapsulated.
  - MCQ-W3-05: ceramic-wire bake-out and storage.
  - MCQ-W3-06: turn and layer voltage below the wire's dielectric rating; independent ground insulation.
  - MCQ-W3-07: no ferromagnetic parts near MC-1 unless mapped.
  - MCQ-W3-08: ECR magnet choice taken with MCQ-QT-09 in hand.
- **W4 (instrumentation):**
  - MCQ-W4-01: 4-wire resistance plus hot-spot thermocouples on every coil.
  - MCQ-W4-02: coil current and voltage recorded per reading.
  - MCQ-W4-03: B(z) maps carry coil currents and temperatures.
- **Lane 15 (`thermal_life`):**
  - MCQ-TL-01: add the candidate grade records.
  - MCQ-TL-02: separate a material class from an EIS class and carry the life basis.
  - MCQ-TL-03: hot-spot allowance from the MCQ-QT-06 measurement.
  - MCQ-TL-04: a non-copper R(T) only from a sourced table, with no extrapolation.
  - MCQ-TL-05: nodes for a PM Hall circuit and an ECR electromagnet.
- **AO lane:**
  - MCQ-AO-01: AOL-WC-04 and AOL-EX-02 use the selected grades and enamel.
  - MCQ-AO-02: one insulation-resistance procedure shared with MCQ-QT-08.

## 5. Lane 15 open questions
| id | question | status | answer |
|---|---|---|---|
| MCQ-L15-01 | N42SH maximum use temperature | PARTIAL | Arnold catalog Rev. 181031, p. 1: "Tw max" 150. "Tw" is undefined in the text (verify) and no load line is given |
| MCQ-L15-02 | MMPA `**` footnote on the NdFeB 150 °C | REMAINS_TBD | p. 20 was rendered and inspected. The markers `*` and `**` are printed, but **no footnote text exists** in the accessed copy, so the problem is absence, not legibility. The value stays gated |
| MCQ-L15-03 | IEC 60085 life basis | REMAINS_TBD | needs MCQ-QT-01. IEC 60216-1 TI/HIC are material properties; MW 16-C 240 °C is a material class |
| MCQ-L15-04 | IEC 60085 edition currency | REMAINS_TBD | no later edition found; the history page returned HTTP 403 (verify) |
| MCQ-L15-05 | EEE-INST-002 inferences | UNCHANGED_REFERENCE_ONLY | measured alternatives are MCQ-QT-01 and MCQ-QT-06 |
| MCQ-L15-06 | node coverage | GAP_REPORTED | `ecr_magnet` is 0 W (PM only) and `hall_magnet` is electromagnet-only, yet W3 allows an ECR electromagnet and lane 20 a PM Hall circuit → MCQ-TL-05 |
| MCQ-L15-07 | load line of the grade maxima | PARTIAL | supplier maxima assume an unstated or very low load line; MCQ-QT-02 closes this per design |

## 6. Coordination (planned paths, referenced only)
The following parallel workstreams are referenced by path only; nothing is imported and no test depends on them:
- W3 `docs/experiments/hardware/`, W4 `docs/experiments/instrumentation/`, W5
  `docs/validation/hall_transport_v2_prereg/` and the AO lane `docs/experiments/lifetime_ao/`.
- The IDs HW-MC-01..05, HW-PIM-03/04, HWQ-05 and AOL-* were read from sibling-worktree drafts. They are drafts and may
  change.
- W1, W2 and W7 are not used, except that the MCQ-OQ-* questions are candidate LOCK-1 items for W2.

## 7. S1-readiness items (for `fo_s1_readiness_gate`; all MISSING today)
- MCQ-S1-01: EIS selected, with supplier data on file.
- MCQ-S1-02: coil temperature instrumentation installed and the hot-spot offset measured.
- MCQ-S1-03: sacrificial-coil thermal cycling done.
- MCQ-S1-04: bake-out / outgassing screen done.
- MCQ-S1-05: per-lot PM irreversible-loss test done.
- MCQ-S1-06: cold and heated-soak B(z) maps done.
- MCQ-S1-07: insulation-resistance baseline taken.
- MCQ-S1-08: coil and magnet safety/operational limits defined for the S1 run sheet (execution-directive condition
  "safety / operational limits defined").

## 8. Owner questions
- MCQ-OQ-01: Is the Hall circuit electromagnet-only (traceable B(z) versus current, needed for W5 and the HW-MC-05
  S_B scan) or PM-assisted?
- MCQ-OQ-02: Which S1 coil family: polyimide/Cu or vitreous-enamel Ni-clad Cu?
- MCQ-OQ-03: What hot-spot margin policy applies?
- MCQ-OQ-04: How are ASTM E595 records and supplier coating data obtained (owner's channel for supplier contact)?
- MCQ-OQ-05: Which pole/core material?
- MCQ-OQ-06: Which ECR magnet type (HWQ-05)?

## 9. Evidence notes and access record
- **Evidence levels.** Supplier datasheets are level 5, and their coefficients are `measured` with the procedure
  unpublished. Maximum-use temperatures and ratings are `assumed` (manufacturer recommendations). The NASA large-thruster
  coil temperatures are level 6 when applied to H-1. Unit conversions and ratios (MCQ-D-01/02) are `inferred`. RTC
  factors and the ECR ratio (MCQ-D-03/04/06) are `model-derived`.
- **Provenance.** Every source carries the sha256 of the file accessed on 2026-09-27.
- **Values not taken** because they came from search snippets rather than the accessed documents:
  - per-conductor Ceramawire temperature limits;
  - the anodized-Al temperature statements attributed to the Honeywell patent description.
- **Access failures** (recorded in `access_failures`; none was bypassed): Ceramawire host (502, distributor copy used),
  Fermilab MI paper (403), Google Patents (503), NASA outgassing database (interactive, no records retrieved),
  IEC 60085 history (403).
