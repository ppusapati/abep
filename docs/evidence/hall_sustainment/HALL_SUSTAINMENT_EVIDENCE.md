# Hall-discharge ignition and sustainment on N2, O2 and air: published evidence (v1, 2026-09-26)

**Status: evidence audit only.** Nothing was simulated, scored, tuned or admitted, and no simulator input changed. This
file does not draw an architecture conclusion. It does not say whether Vyovrinda's ABEP needs a pre-ionizer. It records what
each accessible piece of evidence shows on that question, how strong that evidence is, and where it stops applying.

Files in this directory:

- `hall_sustainment_matrix.json`: the matrix. One entry per observed condition, with sources and access, evidence
  level and class, thruster, gas, flow, voltage, B, geometry, outcome, quantities with units and uncertainty, and a
  per-entry implication for the pre-ionization question.
- `hall_sustainment_matrix.schema.json`: the JSON Schema for the matrix.
- `build_hall_sustainment_matrix.py`: the deterministic builder. It recomputes every repository-derived value from the
  frozen audit files, carries the transcribed literature values and the arithmetic checks, and regenerates the
  generated section of this file. Run `python docs/evidence/hall_sustainment/build_hall_sustainment_matrix.py --check`
  to confirm that the committed files are current.
- `tests/test_hall_sustainment_evidence.py`: checks the schema, the sourcing and evidence classes, that the
  repository-derived values match the repository files, and that the builder reproduces these files.

## The question and the terms

**Question:** can a Hall discharge ignite and stay lit on atmospheric propellant (N2, O2, air or their mixtures)
*without a pre-ionizer*? If so, under which conditions: ignition with or without a Xe start, minimum anode flow,
voltage and B ranges, channel geometry, oscillations and extinction, cathode flow and gas, erosion, and thrust and current?

- **Pre-ionizer.** A dedicated ionization stage separate from the Hall acceleration discharge, for example an
  RF/helicon/ECR stage or the first stage of a two-stage device. The hollow cathode is *not* counted as a pre-ionizer.
  Its gas (Xe, Ar or N2) and its flow fraction are still recorded for every entry, because a cathode on xenon also
  supplies xenon to the discharge.
- **Ignition modes:** `direct_on_atmospheric_gas`, `xenon_start_then_transition`, `xenon_admixture_required`,
  `not_reported`.
- **Outcomes:** `sustained`, `extinguished` (could not be sustained, ceased or flamed out), `unstable`, `not_reported`.
- **Evidence level:** the `docs/EVIDENCE.md` hierarchy. Primary experimental literature on similar hardware is level 3.
  Anything known only second-hand through a review is level 5.
- **Evidence class** of every number: measured / digitized / inferred / reconstructed / model-derived / assumed. A value
  that is not available is written as "not reported" or "TBD - requires ...". It is never filled in.

## Rules followed

- **Sources.** Only published or openly accessible sources were used. No person or lab was contacted and LXCat was not
  used. Paywalls and bot challenges were not bypassed: the aether-h2020.eu captcha was not passed, and ScienceDirect and
  Southampton ePrints both returned 403. Material read only as an abstract is labelled `abstract_only`, and material known
  only through the Andreussi et al. 2022 review is labelled `not_accessed` and marked level 5. The last "Access log"
  section lists every URL used.
- **Restrictive licences.** The ECHT MSc thesis (CC BY-NC-ND 3.0) and the Gurciullo PhD thesis (CC BY-NC-SA 4.0) are
  cited for numbers and short factual statements only. No text, figure or file from either is redistributed.
- **Repository evidence.** P5-N2 and ECHT-N2 values come from the frozen repository audits
  (`hallthruster_bridge/identification/brabston_p5_n2_measurement_audit_v1.json`, `.../p5_n2_measurement_audit_findings_v1.json`,
  `.../echt_n2/echt_n2_evidence_audit_v1.json`, `.../echt_n2/echt_table_checks_v1.json`). Their original sources are
  Brabston et al., JPP 2025 (doi:10.2514/1.B39623) and Marchioni's 2020 MSc thesis. The builder recomputes each value
  from those files, and their sha256 hashes are recorded in `meta.repository_inputs`.
- **Simulation results are not evidence.** The P5-N2 v1 vacuum simulation campaign is not used as evidence that a
  discharge physically sustains. v1 is INCONCLUSIVE. Its status counts appear only under `context_not_evidence`: 1080
  records, and among the 2160 run × reading evaluations, 1428 OUT_OF_DOMAIN, 700 FAIL_VALIDATION and 32 PASS.
- **Scope.** The audit covers Hall discharges only. Excluded items and the reasons are in `excluded`: cusped-field MCFT,
  RIT-10, ABIE, IPT and other non-Hall devices.
- **ABEP regime.** Every entry states that the ABEP flow and density regime is *TBD - requires the upstream ICD*. No
  test condition here is compared with the delivered ABEP condition.

<!-- BEGIN GENERATED: build_hall_sustainment_matrix.py -->

### Summary matrix

| id | thruster (family) | anode gas / cathode gas | ignition | flow | voltage | B | outcome | level | pre-ionization implication |
|---|---|---|---|---|---|---|---|---|---|
| E01 | P5 (5 kW-class laboratory Hall thruster) (single-stage Hall (SPT-type)) | N2 (pure) / Xe | not_reported | 5-5.4 mg/s | 231.9-278.6 V | 130 G | **sustained** | 3 | operation_without_preionizer_demonstrated |
| E02 | P5 (5 kW-class laboratory Hall thruster) (single-stage Hall (SPT-type)) | N2 (pure) / Xe | not_reported | n/r | 225-275 V | 130 G | **extinguished** | 3 | operation_bounded_extinction_observed |
| E03 | ECHT (Stanford extended-channel Hall thruster) (single-stage Hall (SPT-type, extended channel)) | N2 (pure) / Ar | direct_on_atmospheric_gas | 2.06 mg/s | 180-220 V | 85.3 G | **sustained** | 3 | operation_without_preionizer_demonstrated |
| E04 | ECHT (Stanford extended-channel Hall thruster) (single-stage Hall (SPT-type, extended channel)) | N2 (pure) / Ar | direct_on_atmospheric_gas | 1.6 mg/s | n/r | n/r | **extinguished** | 3 | operation_bounded_extinction_observed |
| E05 | Snecma PPS1350-TSD (reconverted to PPS1350 configuration) (single-stage Hall (SPT-type)) | N2 (pure) / Xe | xenon_start_then_transition | 2.3-2.85 mg/s | n/r | n/r | **sustained** | 3 | operation_without_preionizer_demonstrated_xenon_start |
| E06 | Snecma PPS1350-TSD (reconverted to PPS1350 configuration) (single-stage Hall (SPT-type)) | N2/O2, 1.27N2 + O2 (molecular composition) / Xe | xenon_start_then_transition | 2.1 mg/s | 220-350 V | n/r | **sustained** | 3 | operation_without_preionizer_demonstrated_xenon_start |
| E07 | Snecma PPS1350-TSD (reconverted to PPS1350 configuration) (single-stage Hall (SPT-type)) | N2/O2 mixture with a 10 % xenon mass-flow addition / not reported | not_reported | 2.75 mg/s | 305 V | n/r | **extinguished** | 5 | not_informative |
| E08 | SITAEL HT5k (first development model) (single-stage Hall (SPT-type)) | 0.56N2/0.44O2 (= 1.27N2 + O2) / Xe | not_reported | 4.3-4.7 mg/s | 225 V | n/r | **sustained** | 5 | operation_without_preionizer_demonstrated |
| E09 | SITAEL HT5k DM2 with HC20h hollow cathode (magnetically shielded Hall) | 0.56N2 + 0.44O2 / N2 (after transition from Xe) | xenon_start_then_transition | 5-7 mg/s | 225-300 V | n/r | **sustained** | 3 | operation_without_preionizer_demonstrated_xenon_start |
| E10 | Simplified CAMILA (ASRI Technion) (single-stage Hall with coaxial anodes extending into the channel (low power)) | N2 (pure) / Xe | direct_on_atmospheric_gas | 1.144-1.568 mg/s | 180-250 V | 1.48 ratio to Xe/Kr field | **sustained** | 3 | operation_without_preionizer_demonstrated |
| E11 | Simplified CAMILA (ASRI Technion) (single-stage Hall with coaxial anodes extending into the channel (low power)) | N2 (pure) / Xe | direct_on_atmospheric_gas | n/r | n/r | n/r | **extinguished** | 3 | operation_bounded_extinction_observed |
| E12 | MaSHEKT-100 (Southampton) (magnetically shielded Hall (low power)) | N2 (pure) / not accessed | direct_on_atmospheric_gas | n/r | n/r | n/r | **sustained** | 3 | operation_without_preionizer_demonstrated |
| E13 | Z-70 (Stanford, refurbished) (single-stage Hall (SPT-type)) | Xe/N2 mixtures (Xe mass fraction down to about 10 %); pure N2 not sustained / Xe | xenon_admixture_required | 0.16 mg/s | 290 V | 135 G | **extinguished** | 3 | xenon_admixture_required_in_tested_regime |
| E14 | Z-70 (Stanford, refurbished) (single-stage Hall (SPT-type)) | Xe/air mixtures (Xe mass fraction 48-96 % per ANDREUSSI2022 p.26) / Xe | xenon_admixture_required | 0.78-0.83 mg/s | 290 V | 135-160 G | **sustained** | 3 | xenon_admixture_required_in_tested_regime |
| E15 | TsNIIMASH anode-layer thrusters, 27 mm and 55 mm (D-55) anode diameter (anode-layer Hall (TAL)) | Xe + air mixtures (fractions not legible in the accessed scan) / not reported | xenon_admixture_required | n/r | n/r | n/r | **sustained** | 3 | xenon_admixture_required_in_tested_regime |
| E16 | Busek BHT (2 kW nominal) (single-stage Hall (SPT-type)) | air simulant 68.3 % N2, 6.7 % O2, 25 % Ar (Ar as surrogate for atomic O) / not reported | not_reported | 2.94 mg/s | 200-350 V | n/r | **sustained** | 5 | operation_without_preionizer_demonstrated |
| E17 | Busek ABHET LX2 prototype (single-stage Hall (open-ended, extended channel per patent; details unpublished)) | air simulant in an inlet duct, or collected flow from an RF Hall source / not reported (the RF Hall source used a Xe cathode) | not_reported | n/r | n/r | n/r | **sustained** | 5 | not_informative |
| E18 | SITAEL RAM-EP prototype (two-stage Hall (ionization stage + Hall-like acceleration stage)) | intake-collected flow from the HT5k PFG (4.7 mg/s 1.27N2 + O2 at the PFG); PFG also run on Xe / Xe (hollow cathode neutralizer) | not_reported | 4.7 mg/s | n/r | n/r | **sustained** | 3 | preionization_stage_present_effect_not_isolated |
| E19 | Helicon Hall thruster (HHT) (two-stage Hall (helicon RF first stage + Hall stage)) | N2 (pure) / Xe | not_reported | 2.6 mg/s | 200 V | n/r | **sustained** | 5 | preionization_stage_tested_no_net_benefit_reported |
| E20 | laboratory model, Moscow State Technical University per review Table 3 (xenon design) (anode-layer / closed-drift Hall (title: 'thruster with anode layer')) | air; N2/O2 2:1 / Xe | not_reported | 0.8-1 mg/s | n/r | n/r | **sustained** | 5 | operation_without_preionizer_demonstrated |
| E21 | ABCHT prototype (two-stage Hall (ECR ionization + cylindrical Hall acceleration)) | xenon only (no atmospheric gas test reported) / not reported (1 % thoriated W filament selected for the concept, review p.38) | not_reported | n/r | n/r | n/r | **not_reported** | 5 | not_informative |

n/r = not reported in the accessed text (or TBD); ranges are min-max over the reported points.

### Per-item statements

#### E01 - P5 on pure N2, five setpoints N1-N5 (GT VTF-1)

- Sources / access: REPO_P5_N2_AUDIT (repository_audit_file), BRABSTON2025 (licensed_full_text_sha_pinned), BRABSTON_IEPC2024 (open_full_text). Evidence level 3; outcome evidence class: measured; repository-derived values recomputed by the builder.
- Pre-ionizer: none. Ignition (not_reported, measured): The start-up / ignition procedure (gas at ignition) is not described in the accessed text (verify in the full paper if needed).
- Outcome: **sustained**. All five N2 setpoints were operated and measured (thrust, plume probes at N1-N3). Coils were tuned at N3 to minimise I_d and its peak-to-peak oscillation, then held fixed. The Xe cathode flow (4.5 sccm) was chosen as the lowest that kept stable operation on all propellants.
- Observations: oscillations: qualitative only: B tuned to minimise I_d peak-to-peak oscillation; no amplitudes or spectra published (repository findings F6; BRABSTON2025 p.6); extinction: see E02 (voltage window); erosion: not reported; cathode: Xe hollow cathode at 0.44 mg/s; paper assumes the Xe contribution negligible (no resolvable Xe in E x B spectra; findings F5).
- **Implication for 'is pre-ionization required?'** (operation_without_preionizer_demonstrated): A single-stage Hall discharge without a dedicated pre-ionization stage sustained on a pure N2 anode flow of 5.0-5.4 mg/s at 232-279 V and 130 G in this thruster and facility.
  - Uncertainty: Electron supply and possibly ionization are assisted by a Xe cathode flow of 8.1-8.8 % of the anode mass flow, and by ingested background N2 (2.0-3.4 % of the anode flow, Eq. (13) correlation). The start-up gas is not reported, so this entry says nothing about Xe-free ignition.
  - Applicability limits: 5 kW-class channel (32 or 38 mm long), 3.1-4.8 kW, 1.1-2.1e-5 Torr facility background, Xe cathode; not a flight or intake-fed condition.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | anode N2 mass flow (N1-N5) | 5-5.4 | mg/s | measured | MFC 1 % of setpoint (max 0.05 mg/s) | REPO_P5_N2_AUDIT, Table 2 via audit points.*.table2 |
  | cathode Xe mass flow | 0.44 | mg/s | measured | MFC 1 % of setpoint | REPO_P5_N2_AUDIT, Table 2 (4.5 sccm) |
  | cathode Xe / anode N2 mass-flow ratio | 0.0815-0.088 | 1 | inferred | propagated from MFC 1 % (each) | REPO_P5_N2_AUDIT, our arithmetic on Table 2 |
  | discharge voltage | 231.9-278.6 | V | measured | not stated | REPO_P5_N2_AUDIT, Table 2 |
  | discharge power | 3.08-4.81 | kW | measured | rounding 0.005 kW (3 s.f.) | REPO_P5_N2_AUDIT, Table 2 |
  | discharge current, raw = P_d/V_d | 13.2816-17.4465 | A | inferred | P_d rounding 0.10-0.16 %; no I_d uncertainty stated by the source | REPO_P5_N2_AUDIT, audit points.*.I_d_raw_A |
  | peak radial B at channel centre, exit plane | 130 | G | measured | not stated; B(z) shape and coil currents unpublished (layer-1 hypotheses) | REPO_P5_N2_AUDIT, Table 2 |
  | chamber pressure (N2-corrected ion gauge) | 1.14e-05-2.14e-05 | Torr | measured | not stated | REPO_P5_N2_AUDIT, Table 2 |
  | ingested background N2 flow, Eq. (13) | 0.0992-0.1861 | mg/s | inferred | engineering correlation (evidence level 6) | REPO_P5_N2_AUDIT, audit points.*.mdot_ingested_eq13_mg_s |
  | ingested / anode flow | 0.0198-0.0345 | 1 | inferred | inherits Eq. (13) uncertainty | REPO_P5_N2_AUDIT, our arithmetic |
  | thrust, ingestion-corrected (N1..N5) | 61.4-90 | mN | reconstructed | 2.6 | REPO_P5_N2_AUDIT, abstract end-points (N1, N5); Fig. 5 digitized (N2-N4) |
  | discharge channel length | 32-38 | mm | measured | conflicting sources; carried as hypotheses | REPO_P5_N2_AUDIT, docs/EVIDENCE.md register: 32 mm (Brabston 2025) vs 38 mm (Peterson 2001, Hofer 2004) |

#### E02 - P5 on pure N2 outside about 225-275 V (operating-window statement)

- Sources / access: REPO_P5_N2_AUDIT (repository_audit_file), BRABSTON2025 (licensed_full_text_sha_pinned), BRABSTON_IEPC2024 (open_full_text). Evidence level 3; outcome evidence class: measured; repository-derived values recomputed by the builder.
- Pre-ionizer: none. Ignition (not_reported, measured): not described in the accessed text
- Outcome: **extinguished**. The paper states that above 275 V and below 225 V the thruster becomes unstable and cannot sustain a discharge on nitrogen (text statement, no boundary data). qualitative: all five setpoints ran; the text says the discharge cannot be sustained above 275 V or below 225 V (N3-N5 are at 275.7-278.6 V)
- Observations: oscillations: not quantified; extinction: loss of discharge outside the window; erosion: not reported; cathode: Xe hollow cathode 0.44 mg/s.
- **Implication for 'is pre-ionization required?'** (operation_bounded_extinction_observed): Without a pre-ionizer, sustained N2 operation of this thruster was confined to a narrow voltage window at about 5 mg/s and fixed B.
  - Uncertainty: Boundary is a text statement (no data, no B or flow scan at the boundary); whether a pre-ionizer, a different B, or more flow widens the window is not tested.
  - Applicability limits: same as E01
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | discharge voltage | 231.9-278.6 | V | measured | not stated | REPO_P5_N2_AUDIT, Table 2 |

#### E03 - ECHT on pure N2 with an argon cathode, 180-220 V (SPPL LVF)

- Sources / access: REPO_ECHT_AUDIT (repository_audit_file), MARCHIONI2020 (open_full_text_restrictive_license), MARCHIONI2021 (abstract_only). Evidence level 3; outcome evidence class: measured; repository-derived values recomputed by the builder.
- Pre-ionizer: none. Ignition (direct_on_atmospheric_gas, measured): S2 pp.84-85 give an ignition procedure with N2 set on the anode and Ar on the cathode (cathode puff, low B at ignition, B applied after the anode stabilises); S2 p.97 states a stable discharge was maintained on 100 % nitrogen with no xenon present.
- Outcome: **sustained**. 13 operating points (Table 6.1) and 7 thrust runs (Table 6.2) on pure N2 at 2.06 mg/s. Runs 1, 3, 7 are flagged 'strong instability during calibration'; mode changes and quenching were attributed by the author to a degraded BaO cathode.
- Observations: oscillations: qualitative only: mode changes during calibration (Fig. 6.12 LVDT trace), quenching, keeper runaway; discharge unstable/quenches below ~80 sccm (1.6 mg/s). No I_d time traces, spectra, or oscillation amplitudes.; extinction: quenching linked to keeper-voltage runaway (30-40 V) of a degraded emitter; cathode flow raised ad hoc to keep the cathode running (repository audit, cathode.flow_mgps note; S2 p.98); erosion: not reported; cathode: argon, 0.15-0.74 mg/s (Table 6.1).
- **Implication for 'is pre-ionization required?'** (operation_without_preionizer_demonstrated): The only accessed Hall case that both ignited and ran on a pure N2 anode flow with no xenon anywhere (Ar cathode) and no pre-ionization stage, at about 2 mg/s in an 86 mm channel.
  - Uncertainty: Argon cathode flow was large (7.3-35.9 % of anode mass) and co-varied with the best points; facility background 8.1e-05-2.2e-04 Torr (inferred ingestion 2.0-6.0 % of anode flow, repository audit); 3 of 7 thrust runs strongly unstable; per-point I_d to 2 s.f.; no oscillation data.
  - Applicability limits: 0.27-0.77 kW, 180-220 V only (300 V supply limit, no data above 220 V), one flow (2.06 mg/s), elevated facility pressure; MSc-thesis measurement with fit-only thrust uncertainty.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | anode N2 mass flow | 2.06 | mg/s | measured | 1 % ambiguity (99 vs 100 sccm = 2.06 vs 2.083 mg/s); possible feed-line leakage | REPO_ECHT_AUDIT, S2 Table 6.1 p.98 |
  | discharge voltage | 180-220 | V | measured | not stated | REPO_ECHT_AUDIT, S2 Table 6.1 |
  | discharge current | 1.5-3.9 | A | measured | 2 s.f. (rounding +-0.05 A) | REPO_ECHT_AUDIT, S2 Table 6.1 |
  | magnet coil current | 0.8-3 | A | measured | not stated | REPO_ECHT_AUDIT, S2 Table 6.1 |
  | measured centreline B plateau at 2 A coil current | 85.3 | G | digitized | reading +-0.2 G; probe uncertainty not stated | REPO_ECHT_AUDIT, S2 Fig. 4.7 p.66 (digitized by the repository audit) |
  | cathode Ar mass flow | 0.15-0.74 | mg/s | measured | not stated | REPO_ECHT_AUDIT, S2 Table 6.1 |
  | cathode Ar / anode N2 mass-flow ratio | 0.0728-0.3592 | 1 | inferred | inherits the 2.06/2.083 mg/s ambiguity | REPO_ECHT_AUDIT, our arithmetic on Table 6.1 |
  | chamber pressure (ion gauge) | 8.1e-05-0.00022 | Torr | measured | gauge location and gas correction not stated | REPO_ECHT_AUDIT, S2 Table 6.1 |
  | anode power, thrust runs | 270-770 | W | inferred | from 2 s.f. I_d | REPO_ECHT_AUDIT, V_d x I_d, S2 Table 6.2 |
  | thrust, one-side reduction (7 runs) | 20.62-23.41 | mN | measured | published +- are calibration-fit only (0.02-2.66 mN) | REPO_ECHT_AUDIT, S2 Table 6.2 p.101 |
  | thrust, averaged reduction (4 runs) | 17.29-21.31 | mN | measured | published +- 2.68-4.56 mN; 6-18 % below one-side | REPO_ECHT_AUDIT, S2 Table 6.3 p.108 |
  | channel length | 86 | mm | measured | not stated (design dimension) | REPO_ECHT_AUDIT, S2 Sec. 4.1.1 p.63 |
  | channel height | 10 | mm | measured | not stated (design dimension) | REPO_ECHT_AUDIT, S2 Sec. 4.1.1 p.63 |

#### E04 - ECHT on pure N2 below about 80 sccm (1.6 mg/s)

- Sources / access: REPO_ECHT_AUDIT (repository_audit_file), MARCHIONI2020 (open_full_text_restrictive_license), MARCHIONI2021 (abstract_only). Evidence level 3; outcome evidence class: measured; repository-derived values recomputed by the builder.
- Pre-ionizer: none. Ignition (direct_on_atmospheric_gas, measured): as E03
- Outcome: **extinguished**. Qualitative: the discharge was unstable / quenched below about 80 sccm (1.6 mg/s) N2.
- Observations: oscillations: not quantified; extinction: flow floor about 1.6 mg/s; erosion: not reported; cathode: Ar, degraded BaO emitter.
- **Implication for 'is pre-ionization required?'** (operation_bounded_extinction_observed): Even with an 86 mm channel, pure-N2 operation without a pre-ionizer had a flow floor near 1.6 mg/s in this set-up.
  - Uncertainty: Single approximate statement; voltage, B and cathode state at the boundary not given; the degraded cathode may have set the floor.
  - Applicability limits: as E03
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

#### E05 - PPS1350-TSD on pure N2 (Alta IV10, ESA contract)

- Sources / access: CIFALI2011 (open_full_text), ANDREUSSI2022 (open_full_text). Evidence level 3; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (xenon_start_then_transition, measured): Always ignited with xenon, then a smooth anode transition from 100 % Xe to 100 % N2; the cathode stayed on xenon (CIFALI2011 p.2).
- Outcome: **sustained**. Operated over 2.3-2.85 mg/s N2; 10 h long firing at 305 V, 3 A 'very stable', thrust always 19-21 mN; Xe performance afterwards substantially unaffected.
- Observations: oscillations: not reported; extinction: none reported; erosion: visual inspection after the campaign (see E06); cathode: Xe hollow cathode throughout.
- **Implication for 'is pre-ionization required?'** (operation_without_preionizer_demonstrated_xenon_start): Steady single-stage operation on pure N2 without a pre-ionizer, once lit on xenon and with a Xe cathode.
  - Uncertainty: Ignition on N2 itself was not attempted/reported; B, oscillations and plume not measured; performance only from the stand.
  - Applicability limits: about 1 kW, 2.3-2.85 mg/s, facility < 6e-6 mbar, Xe cathode.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | reference point: voltage | 305 | V | measured | not stated | CIFALI2011, p.3 |
  | reference point: discharge current | 3.48 | A | measured | not stated | CIFALI2011, p.3 |
  | reference point: power-to-thrust | 41.6 | W/mN | inferred | not stated | CIFALI2011, p.3 |
  | long firing: discharge current | 3 | A | measured | not stated | CIFALI2011, p.4 |
  | long firing: duration | 10 | h | measured | not stated | CIFALI2011, p.4 |
  | long firing: thrust band | 19-21 | mN | measured | stand accuracy 1 % of full scale (range 5-300 mN), resolution 1 mN (p.2) | CIFALI2011, p.4 |
  | long firing: anode N2 flow | 2.65 | mg/s | measured | not stated | CIFALI2011, p.5 |
  | chamber pressure during N2 long firing | < 6.0e-6 | mbar | measured | upper bound as stated | CIFALI2011, p.2 |

#### E06 - PPS1350-TSD on N2/O2 mixture 1.27N2 + O2 (200 km-representative)

- Sources / access: CIFALI2011 (open_full_text), ANDREUSSI2022 (open_full_text). Evidence level 3; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (xenon_start_then_transition, measured): as E05 (always ignited with xenon, CIFALI2011 p.2)
- Outcome: **sustained**. Stable operation down to 2.1 mg/s; 10 h stable test at 305 V, 2.75 mg/s, thrust 24 mN.
- Observations: oscillations: flow-controller perturbations 'induced by oscillations on the main discharge circuit' mentioned for the Xe re-check after the mixture test (p.5); not quantified; extinction: none reported; erosion: anode 'rusty' (oxidation) and signs of oxygen operation on the ceramics after the test; anode oxidation named the main concern for endurance (p.5); cathode: Xe.
- **Implication for 'is pre-ionization required?'** (operation_without_preionizer_demonstrated_xenon_start): Steady operation on an N2/O2 anode flow without a pre-ionizer after a xenon start; O2 addition did not degrade sustainment at low flow in this test (stable to 2.1 mg/s).
  - Uncertainty: Xe start and Xe cathode; no B data; oxidation of the anode is a separate life issue (E07).
  - Applicability limits: about 1 kW, 2.1-4 mg/s, 220-350 V, facility-fed gas, no atomic oxygen.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | long firing: flow | 2.75 | mg/s | measured | not stated | CIFALI2011, p.5 / Fig. 7 caption |
  | long firing: voltage | 305 | V | measured | not stated | CIFALI2011, Fig. 7 caption p.4 |
  | long firing: thrust | 24 | mN | measured | stand accuracy 1 % of full scale | CIFALI2011, p.5 |
  | long firing: duration | 10 | h | measured | not stated | CIFALI2011, p.5 |
  | N2 mole fraction of 1.27N2 + O2 | 0.5595 | 1 | inferred | exact for the stated ratio | CIFALI2011, our arithmetic |

#### E07 - PPS1350 endurance on N2/O2 + 10 % Xe (secondary report)

- Sources / access: ANDREUSSI2022 (open_full_text), CIFALI2012 (not_accessed). Evidence level 5; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (not_reported, measured): not reported in the review
- Outcome: **extinguished**. Steady for about 314 h at 3.8-4 A; then severe anode oxidation produced anomalous discharge behaviour and a spontaneous flame-out; after refurbishment, several flame-outs in the next 75 h and the test was stopped early.
- Observations: oscillations: anomalous discharge behaviour (not quantified); extinction: flame-outs attributed to anode oxidation; erosion: ceramic erosion reported compatible with 7000-9500 h lifetime; anode oxidation life-limiting; cathode: not reported.
- **Implication for 'is pre-ionization required?'** (not_informative): Says nothing on pre-ionization; shows that with oxygen in the anode flow, sustainment over hundreds of hours was limited by anode oxidation (flame-outs), with 10 % Xe already added.
  - Uncertainty: Second-hand (primary SP2012 paper not accessed).
  - Applicability limits: PPS1350, 305 V, 2.75 mg/s, facility-fed N2/O2 + Xe.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | steady duration before first flame-out | 314 | h | measured | 'about' | ANDREUSSI2022, Page 24 of 57 |
  | discharge current during steady phase | 3.8-4 | A | measured | not stated | ANDREUSSI2022, Page 24 of 57 |
  | subsequent firing with several flame-outs | 75 | h | measured | not stated | ANDREUSSI2022, Page 24 of 57 |
  | ceramic-erosion-compatible lifetime (authors' estimate) | 7000-9500 | h | model-derived | extrapolation method not given in the review | ANDREUSSI2022, Page 24 of 57 |
  | effect of the 10 % Xe addition on I_d (characterization) | 17-40 | % | measured | not stated | ANDREUSSI2022, Page 23 of 57 |
  | effect of the 10 % Xe addition on thrust (characterization) | 4-40 | % | measured | not stated | ANDREUSSI2022, Page 23 of 57 |

#### E08 - SITAEL HT5k (first development model) as particle-flow generator on N2/O2 (2017)

- Sources / access: ANDREUSSI2022 (open_full_text), FERRATO2019_IEPC886 (open_full_text), ANDREUSSI2017_IEPC377 (not_accessed). Evidence level 5; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (not_reported, measured): not reported
- Outcome: **sustained**. Stable operation verified at 225 V, 4.3-4.7 mg/s; 64 mN at 2.4 kW; plume half-angle divergence 52 deg (review p.43).
- Observations: oscillations: not reported; extinction: not reported; erosion: not reported; cathode: Xe.
- **Implication for 'is pre-ionization required?'** (operation_without_preionizer_demonstrated): Single-stage operation on an N2/O2 anode flow without a pre-ionizer at 4.3-4.7 mg/s.
  - Uncertainty: Second-hand for the performance values (IEPC-2017-377 not accessed); ignition gas not reported; Xe cathode.
  - Applicability limits: 5 kW-class, 225 V, facility-fed gas.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | thrust | 64 | mN | measured | not stated | ANDREUSSI2022, Page 24 of 57 |
  | discharge power | 2.4 | kW | measured | not stated | ANDREUSSI2022, Page 24 of 57 |
  | plume half-angle divergence | 52 | deg | measured | not stated | ANDREUSSI2022, Page 43 of 57 |

#### E09 - SITAEL HT5k DM2 (magnetically shielded), AETHER particle-flow generator, N2/O2 anode and N2 cathode (Nov 2021)

- Sources / access: ANDREUSSI2022_IEPC435 (open_full_text), FERRATO2022_PSST (abstract_only), ANDREUSSI2022 (open_full_text). Evidence level 3; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (xenon_start_then_transition, measured): Ignited at 225 V on 10 mg/s Xe (anode) + 1 mg/s Xe (cathode); anode switched gradually to 6 mg/s N2/O2; then cathode Xe reduced to 0 while N2 raised to 0.6 mg/s (p.3).
- Outcome: **sustained**. Discharge and thermal stability demonstrated at 225 V and 300 V, 5-7 mg/s, with the N2-fed cathode (xenon-free steady state after the xenon start); six operating conditions; cumulative 10 h on atmospheric propellant; Xe reference tests before/after repeatable.
- Observations: oscillations: I_d acquired at 10 MHz; the review reports the discharge current signal stable in all points (Page 25 of 57); no spectra published; extinction: none reported; erosion: magnetic shielding 'seems effective'; plasma detachment from channel walls visible (p.5); no PFG critical damage after the air test; cathode: HC20h (LaB6) on N2 0.5-0.7 mg/s (PSST abstract); N2 cathode reduced I_d, thrust and efficiency vs Xe cathode at the same V_d and anode flow (p.5). The review reports severe erosion/embrittlement of the HC20h after tests with the N2/O2 mixture (Page 38 of 57).
- **Implication for 'is pre-ionization required?'** (operation_without_preionizer_demonstrated_xenon_start): After a xenon start, a single-stage magnetically shielded Hall discharge was sustained with no xenon anywhere (N2/O2 anode, N2 cathode) and no pre-ionizer at 5-7 mg/s.
  - Uncertainty: Ignition itself used xenon; B and geometry not published; only 10 h; efficiency range differs between the two SITAEL sources.
  - Applicability limits: 5 kW class, 1.2-5.2 kW, 225-300 V, facility < 2.5e-5 mbar, lab-fed gas (no atomic O).
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | thrust range | 30-120 | mN | measured | stand accuracy +-3 mN (p.3) | ANDREUSSI2022_IEPC435, p.5 |
  | discharge power range | 1.2-5.2 | kW | measured | not stated | ANDREUSSI2022_IEPC435, p.5 |
  | anodic efficiency range | 10-20 | % | inferred | FERRATO2022_PSST abstract gives 8-18 % (discrepancy not resolved) | ANDREUSSI2022_IEPC435, p.5 |
  | specific impulse range | 600-1600 | s | inferred | not stated | ANDREUSSI2022_IEPC435, p.5 |
  | cathode N2 flow | 0.5-0.7 | mg/s | measured | not stated | FERRATO2022_PSST, abstract |
  | cathode/anode flow ratio (held during the scan) | 0.1 | 1 | measured | not stated | ANDREUSSI2022_IEPC435, p.3 |
  | facility pressure (ITR90, 3 m downstream) | < 2.5e-5 | mbar | measured | upper bound | ANDREUSSI2022_IEPC435, p.2 |
  | cumulative firing on atmospheric propellant | 10 | h | measured | not stated | ANDREUSSI2022_IEPC435, p.5 |

#### E10 - Simplified CAMILA low-power Hall thruster on pure N2 (inside its operating envelope)

- Sources / access: MOSKOVITZ2026 (open_full_text). Evidence level 3; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (direct_on_atmospheric_gas, inferred): The thruster was ignited at known stable points and re-ignited after shutdowns with a higher flow (p.9); the gas at ignition is not stated explicitly, read here as direct ignition on the N2 anode flow with a Xe cathode (inferred, verify).
- Outcome: **sustained**. Operated on N2 within an envelope (stability = discharge sustained > 5 min); the authors call N2 the narrowest envelope and note numerous spontaneous shutdowns with light gases.
- Observations: oscillations: not quantified; I_d/I_b described as highly sensitive to changes (p.9); extinction: see E11; erosion: not measured (endurance recommended as future work, p.21); cathode: Xe only, 0.15 or 0.20 mg/s; 2.00 sccm for Ar/CO2/N2 vs 1.50 sccm for Xe/Kr (p.6, p.14).
- **Implication for 'is pre-ionization required?'** (operation_without_preionizer_demonstrated): A low-power single-stage Hall thruster sustained pure-N2 discharges without a pre-ionizer at 1.1-1.6 mg/s, but only with about 1.48x the Xe magnetic field and within a narrow, voltage-dependent flow envelope.
  - Uncertainty: Ignition gas inferred, not stated; Xe cathode; facility pressure effect addressed only in an appendix; envelope minima are in a figure only (TBD digitization).
  - Applicability limits: 0.2-0.45 kW, 180-250 V, coaxial-anode geometry (not a conventional SPT).
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | power range | 212-452 | W | measured | not stated | MOSKOVITZ2026, Table 5 p.8 |
  | peak anode efficiency point: voltage | 250 | V | measured | not stated | MOSKOVITZ2026, Table 6 p.11 |
  | peak anode efficiency point: flow | 1.144 | mg/s | measured | not stated | MOSKOVITZ2026, Table 6 p.11 |
  | peak anode efficiency point: power | 400 | W | measured | not stated | MOSKOVITZ2026, Table 6 p.11 |
  | peak anode efficiency point: thrust | 8.2 | mN | measured | stand accuracy stated per range on p.7 (symbols lost in text layer) | MOSKOVITZ2026, Table 6 p.11 |
  | peak anode efficiency | 7.35 | % | inferred | not stated | MOSKOVITZ2026, Table 6 p.11 |
  | fixed-power points: N2 flow at 350/400/450 W | 1.34, 1.475, 1.543 | mg/s | measured | not stated | MOSKOVITZ2026, Table 7 p.16 |
  | fixed-power points: thrust at 350/400/450 W | 7.25, 8.6, 9.7 | mN | measured | not stated | MOSKOVITZ2026, Table 7 p.16 |
  | fixed-power points: mass utilization | 24, 25, 27 | % | inferred | Faraday probe 10 % | MOSKOVITZ2026, Table 7 p.16 |
  | channel mean diameter | 49 | mm | measured | not stated | MOSKOVITZ2026, Table 3 p.6 |
  | channel width | 12 | mm | measured | not stated | MOSKOVITZ2026, Table 3 p.6 |
  | N2 flow conversion check 55.0 sccm | 1.1457 | mg/s | inferred | reference conditions of the paper not stated | MOSKOVITZ2026, our arithmetic |

#### E11 - Simplified CAMILA on pure N2 below its minimum voltage/flow envelope

- Sources / access: MOSKOVITZ2026 (open_full_text). Evidence level 3; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (direct_on_atmospheric_gas, inferred): as E10
- Outcome: **extinguished**. Below the minimum voltage/flow combination the discharge shut down spontaneously; lower voltages required more flow, and the boundary slope is steepest for light gases.
- Observations: oscillations: not quantified; extinction: spontaneous shutdowns; restart needed a more stable parameter set; erosion: not measured; cathode: Xe.
- **Implication for 'is pre-ionization required?'** (operation_bounded_extinction_observed): Without a pre-ionizer, pure-N2 sustainment in this thruster has a voltage-dependent minimum flow.
  - Uncertainty: Boundary values need digitization; 5-min stability criterion only.
  - Applicability limits: as E10
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | boundary probe step in voltage | 0.5-5 | V | measured | not stated | MOSKOVITZ2026, p.9 |

#### E12 - MaSHEKT-100 low-power magnetically shielded Hall thruster on N2 (abstract only)

- Sources / access: MUNRO2023 (abstract_only), MOSKOVITZ2026 (open_full_text). Evidence level 3; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (direct_on_atmospheric_gas, measured): Second-hand: MOSKOVITZ2026 p.4 reports that the thruster could 'eventually' be ignited with pure N2, and that only three N2 data points were collected because of a component failure (verify in the primary).
- Outcome: **sustained**. The abstract states that the thruster was operated on diatomic nitrogen successfully (neon: unstable).
- Observations: oscillations: not accessed; extinction: not accessed; erosion: not accessed; cathode: not accessed.
- **Implication for 'is pre-ionization required?'** (operation_without_preionizer_demonstrated): Indicates direct N2 ignition and operation of a ~100 W single-stage Hall thruster without a pre-ionizer, but with few points.
  - Uncertainty: Abstract plus second-hand statements only; flow, voltage, cathode gas and stability not accessed.
  - Applicability limits: about 0.1 kW class; unknown flow regime.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | peak thrust on N2 | 5.7 | mN | measured | not stated | MUNRO2023, abstract |
  | peak anode efficiency on N2 | 5.4 | % | inferred | not stated | MUNRO2023, abstract |
  | peak specific impulse on N2 | 1000 | s | inferred | not stated | MUNRO2023, abstract |

#### E13 - Z-70 on Xe/N2 mixtures: xenon needed to sustain the discharge at <= about 0.7 kW

- Sources / access: GURCIULLO2020 (open_full_text_restrictive_license), GURCIULLO2019 (abstract_only), ANDREUSSI2022 (open_full_text). Evidence level 3; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (xenon_admixture_required, measured): A share of xenon was used because the discharge could not be sustained at the anode power investigated, which was limited by the 300 V supply (p.126).
- Outcome: **extinguished**. With Xe reduced below 0.16 mg/s at this power range the discharge became unstable and eventually ceased (p.177); pure N2 was not operated at the available power.
- Observations: oscillations: not reported; extinction: loss of discharge below 0.16 mg/s Xe; erosion: not reported; cathode: IonTech HC-252 (BaO) on Xe, 0.46 mg/s (p.148).
- **Implication for 'is pre-ionization required?'** (xenon_admixture_required_in_tested_regime): In a short (23 mm) xenon-optimized channel at <= 0.7 kW and 290 V, pure-N2 operation without a pre-ionizer was not achieved; about 10 % Xe by mass was the lowest admixture that sustained.
  - Uncertainty: The author attributes the limit to available power (supply voltage), and states pure N2/air would be possible at higher power (citing CIFALI2011); not tested here.
  - Applicability limits: 0.4-0.75 kW, 270-290 V, 23 mm channel, facility 6.5e-5 Torr on Xe (p.147).
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | anode power at the lowest-Xe points | 603.2-681.5 | W | measured | not stated | GURCIULLO2020, Tables 4.6/4.7 captions |
  | anode current at the lowest-Xe points | 2.08-2.35 | A | measured | not stated | GURCIULLO2020, Tables 4.6/4.7 captions |
  | Xe mass fraction of anode flow at the lowest-Xe points | 0.1032-0.1074 | 1 | inferred | not stated | GURCIULLO2020, our arithmetic on p.177 values |
  | cathode Xe flow | 0.46 | mg/s | measured | not stated | GURCIULLO2020, p.148 |
  | anode supply voltage limit | 300 | V | measured | not stated | GURCIULLO2020, p.147 |

#### E14 - Z-70 on Xe/air mixtures (sustained with xenon admixture)

- Sources / access: GURCIULLO2020 (open_full_text_restrictive_license), GURCIULLO2019 (abstract_only), ANDREUSSI2022 (open_full_text). Evidence level 3; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (xenon_admixture_required, measured): as E13
- Outcome: **sustained**. Operated on Xe/air mixtures down to about 48 % Xe (review) / 0.78 mg/s Xe with 0.83 mg/s air (thesis); the author reports better performance with air than with N2.
- Observations: oscillations: not reported; extinction: not reported for air; erosion: not reported; cathode: Xe 0.46 mg/s.
- **Implication for 'is pre-ionization required?'** (xenon_admixture_required_in_tested_regime): Air operation in this thruster was only shown with substantial xenon admixture; no pre-ionizer was used and pure air was not attempted at the available power.
  - Uncertainty: Minimum Xe share for air not reported in the thesis text read here.
  - Applicability limits: as E13
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | anode current XeAir-3 (135 G) | 2.57 | A | measured | not stated | GURCIULLO2020, Table 4.10 p.201 |
  | anode current XeAir-4 (160 G) | 2.45 | A | measured | not stated | GURCIULLO2020, Table 4.10 p.201 |

#### E15 - TsNIIMASH anode-layer thrusters on Xe + air mixtures (1995)

- Sources / access: SEMENKIN1995 (open_full_text), ANDREUSSI2022 (open_full_text). Evidence level 3; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (xenon_admixture_required, measured): Xe addition to light propellants changed the operating mode and enabled the 'acceleration mode' (pp.3-4); pure-air operation is not characterized in the text.
- Outcome: **sustained**. Volt-ampere characteristics for Xe + air were measured; Xe additions allowed an effective 'acceleration mode' (p.4).
- Observations: oscillations: not reported; extinction: not reported; erosion: not reported; cathode: not reported.
- **Implication for 'is pre-ionization required?'** (xenon_admixture_required_in_tested_regime): Early evidence that a heavy-gas (Xe) discharge acts as the ionizer for light gases in a TAL; it does not test pure air or a separate pre-ionizer.
  - Uncertainty: Qualitative; figures illegible; mixture ratios for air unknown.
  - Applicability limits: TAL geometry, 1995 laboratory conditions.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

#### E16 - Busek 2 kW-class BHT on 'air simulant' 68.3 % N2 / 6.7 % O2 / 25 % Ar (2005; secondary)

- Sources / access: ANDREUSSI2022 (open_full_text), HRUBY2022 (not_accessed). Evidence level 5; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (not_reported, measured): not reported in the review
- Outcome: **sustained**. Tested over 200-350 V and 1-5.5 kW; best anodic efficiency about 27 % at 350 V, 2.94 mg/s.
- Observations: oscillations: not reported; extinction: not reported; erosion: not reported; cathode: not reported.
- **Implication for 'is pre-ionization required?'** (operation_without_preionizer_demonstrated): A conventional Hall thruster ran on an N2-rich simulant without a pre-ionizer.
  - Uncertainty: Second-hand; 25 % argon (not atomic O) in the feed eases ionization; ignition and cathode gas unknown.
  - Applicability limits: 2 kW class, 1-5.5 kW, lab-fed gas.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | discharge power range | 1-5.5 | kW | measured | not stated | ANDREUSSI2022, Page 25 of 57 |
  | best anodic efficiency | 27 | % | inferred | 'about' | ANDREUSSI2022, Page 25 of 57 |

#### E17 - Busek ABHET prototype fed by duct / RF-Hall-generated flow (secondary)

- Sources / access: ANDREUSSI2022 (open_full_text), HRUBY2022 (not_accessed). Evidence level 5; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (not_reported, measured): not reported
- Outcome: **sustained**. The review states the ABHET was able to operate with the simulated VLEO flow; no performance data (stand impingement, facility > 1e-4 Torr).
- Observations: oscillations: not reported; extinction: not reported; erosion: not reported; cathode: not reported.
- **Implication for 'is pre-ionization required?'** (not_informative): Qualitative operation with a pre-ionized upstream flow source; cannot separate the role of the incoming ions from the thruster's own ionization.
  - Uncertainty: Second-hand, qualitative, high facility pressure.
  - Applicability limits: unknown
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | facility pressure during operation | > 1e-4 | Torr | measured | not stated | ANDREUSSI2022, Page 35 of 57 |

#### E18 - SITAEL RAM-EP double-stage thruster, end-to-end with intake and PFG (2017)

- Sources / access: FERRATO2019_IEPC886 (open_full_text), ANDREUSSI2022 (open_full_text), ANDREUSSI2017_IEPC377 (not_accessed). Evidence level 3; outcome evidence class: measured.
- Pre-ionizer: yes - dedicated first (ionization) stage of a double-stage device. Ignition (not_reported, measured): 'first ignition and stable operation' of the full system is claimed (IEPC-2019-886 p.3); procedure not given
- Outcome: **sustained**. The integrated system operated on the collected flow; 'good ionization capability', acceleration stage below expectations.
- Observations: oscillations: not reported; extinction: not reported; erosion: not reported; cathode: conventional Xe-fed hollow cathode.
- **Implication for 'is pre-ionization required?'** (preionization_stage_present_effect_not_isolated): The only accessed intake-fed Hall-type operation used a dedicated ionization stage; it does not show whether that stage was necessary.
  - Uncertainty: Inlet density/flow not measured; upstream source partly ionized; Xe cathode; no single-stage control case.
  - Applicability limits: ground end-to-end test at 500 mm from a Hall-thruster flow source.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | thrust produced by the system on the collected flow | 6 | mN | measured | 1 | FERRATO2019_IEPC886, Fig. 1b caption and text p.3 |
  | drag on system with thruster off | 26 | mN | measured | 1 | FERRATO2019_IEPC886, Fig. 1b caption and text p.3 |
  | PFG-to-intake distance | 500 | mm | measured | not stated | FERRATO2019_IEPC886, Fig. 2 caption p.3 |

#### E19 - Michigan helicon Hall thruster on N2: single-stage vs RF-assisted (secondary)

- Sources / access: ANDREUSSI2022 (open_full_text), SHABSHELOWITZ2014 (not_accessed). Evidence level 5; outcome evidence class: measured.
- Pre-ionizer: yes - helicon RF stage (0-302 W). Ignition (not_reported, measured): not reported in the review
- Outcome: **sustained**. Operated on N2 in single-stage mode (RF off) and with RF up to 302 W. RF produced a minor thrust increase while thrust-to-power and anode efficiency decreased consistently.
- Observations: oscillations: not reported; extinction: not reported; erosion: not reported; cathode: Xe 1 mg/s (38.4 % cathode flow fraction per the review).
- **Implication for 'is pre-ionization required?'** (preionization_stage_tested_no_net_benefit_reported): The single-stage Hall mode sustained on N2 without the RF stage; adding RF pre-ionization raised utilization slightly but did not pay for its power in this device.
  - Uncertainty: Second-hand (primary not accessible); very large Xe cathode fraction (about 38 %) may have assisted sustainment.
  - Applicability limits: one flow (2.6 mg/s), 200 V, laboratory facility.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | RF power range | 0-302 | W | measured | not stated | ANDREUSSI2022, Page 27 of 57 |
  | cathode Xe flow | 1 | mg/s | measured | not stated | ANDREUSSI2022, Page 27 of 57 |
  | cathode/anode flow ratio | 0.3846 | 1 | inferred | not stated | ANDREUSSI2022, our arithmetic |
  | single-stage propellant utilization | 0.1 | 1 | inferred | '~' | ANDREUSSI2022, Page 28 of 57 |
  | single-stage beam divergence efficiency | 0.6 | 1 | inferred | '~' | ANDREUSSI2022, Page 28 of 57 |

#### E20 - Laboratory closed-drift thruster (38 mm mean channel diameter) on air and 2:1 N2/O2

- Sources / access: DUKHOPELNIKOV2021 (abstract_only), ANDREUSSI2022 (open_full_text). Evidence level 5; outcome evidence class: measured.
- Pre-ionizer: none. Ignition (not_reported, measured): not reported
- Outcome: **sustained**. Operated on air and N2/O2; I_d-V plateau 50-100 V higher than Xe; I_d 2.1-2.4x (air) and 1.9-2.7x (N2/O2) the Xe value at 200-350 V; mass utilization on average 2.3x lower than Xe.
- Observations: oscillations: not reported; extinction: not reported; erosion: not reported; cathode: Xe 0.19 mg/s.
- **Implication for 'is pre-ionization required?'** (operation_without_preionizer_demonstrated): A small xenon-design closed-drift thruster operated on air and N2/O2 at about 1 mg/s without a pre-ionizer (Xe cathode).
  - Uncertainty: Abstract + review only; thrust inferred with an assumed voltage utilization; ignition not reported.
  - Applicability limits: small TAL-type device, 0.8-1.0 mg/s.
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

  | quantity | value | unit | class | uncertainty | source, locator |
  |---|---|---|---|---|---|
  | cathode Xe flow | 0.19 | mg/s | measured | not stated | ANDREUSSI2022, Page 26 of 57 |
  | I_d ratio air/Xe (200-350 V) | 2.1-2.4 | 1 | measured | not stated | ANDREUSSI2022, Page 27 of 57 |
  | thrust estimate basis: assumed voltage utilization | 0.75 | 1 | assumed | not stated | ANDREUSSI2022, Page 26 of 57 |

#### E21 - Aerospace Corp. 2-stage air-breathing cylindrical Hall thruster (ECR + CHT) - xenon only

- Sources / access: ANDREUSSI2022 (open_full_text), DIAMANT2010 (not_accessed). Evidence level 5; outcome evidence class: measured.
- Pre-ionizer: yes - ECR stage. Ignition (not_reported, measured): not reported
- Outcome: **not_reported**. Prototype assembled but only tested with xenon (review p.37).
- Observations: oscillations: not reported; extinction: not reported; erosion: not reported; cathode: filament.
- **Implication for 'is pre-ionization required?'** (not_informative): No atmospheric-gas evidence; a pre-ionizer concept without a test on N2/O2/air.
  - Uncertainty: Second-hand; no atmospheric-gas data exist in the accessed record.
  - Applicability limits: none for N2/O2/air (xenon tests only).
  - ABEP flow/density regime: TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, number density and composition at the thruster inlet, including transients). No comparison of this test regime with the ABEP delivered regime is made here.

<!-- END GENERATED -->

## Cross-cutting observations

These are observations about the evidence set, not conclusions. Each one points to entries above and inherits their
limits.

1. **Operation without a pre-ionizer is documented, but only under laboratory conditions.** Single-stage Hall
   discharges without a pre-ionizer were sustained on pure N2 or on N2/O2 anode flows in:
   - the 5 kW-class P5 (E01);
   - the 86 mm-channel ECHT (E03);
   - the PPS1350 (E05, E06);
   - the HT5k, first development model and DM2 (E08, E09);
   - the low-power CAMILA and MaSHEKT-100 (E10, E12);
   - a small closed-drift laboratory model (E20).

   Every one of these was fed from laboratory mass-flow controllers at 1.1-7 mg/s, in facilities with background
   pressures from < 6e-6 mbar to 2.2e-4 Torr. None was fed through an intake at orbital density.
2. **Xenon is present in most cases.** Most cases use xenon in the cathode (E01, E05, E06, E08, E10, E19, E20), for
   ignition (E05, E06, E09) or in the anode flow (E07, E13-E15). The accessed record shows only two xenon-free cases:
   - **E03 (ECHT).** The discharge was ignited directly on N2 with an argon cathode. Argon was 7-36 % of the anode mass
     flow.
   - **E09 (HT5k DM2).** The discharge ran xenon-free in steady state (N2/O2 anode, N2 cathode), but only after a
     xenon start.

   E10 points to direct N2 ignition with a Xe cathode, but that reading is our inference. E12 points to direct N2
   ignition, but the statement is second-hand and its cathode gas was not accessed.
3. **Extinction boundaries are reported, but mostly qualitatively.** Four entries give a boundary:
   - **E02:** P5 had a narrow voltage window of about 225-275 V at 5 mg/s and fixed B.
   - **E04:** ECHT had a flow floor near 1.6 mg/s.
   - **E11:** CAMILA's minimum flow depends on voltage, and the values are available only in Fig. 6 (TBD digitization).
   - **E13:** the Z-70 did not sustain at 290 V and ≤ 0.7 kW once xenon fell below about 10 % of the anode mass.

   E06 gives a stable minimum of 2.1 mg/s for the PPS1350 on N2/O2. None of these sources publishes an ignition threshold
   (breakdown voltage or pressure) for atmospheric gas.
4. **Magnetic field.** CAMILA needed about 1.48× the xenon field on molecular gases (E10). P5-N2 instead ran at a lower
   peak field than P5-Xe (130 G vs 162.5 G, BRABSTON2025 Tables 2 and 4). In both P5 cases the coils were tuned to minimise I_d and its oscillation
   (E01), so the two observations are not directly comparable. The Z-70 on Xe/air did worse at 160 G than at 135 G (E14).
   B(z) shapes are published only for ECHT: a flat plateau with 85.3 G measured at 2 A.
5. **Channel length.** Channel lengths in the set are 23 mm (Z-70), 32 or 38 mm (P5) and 86 mm (ECHT). Only the
   longest channel ran pure N2 at about 2 mg/s with no xenon anywhere. The short Z-70 did not run pure N2 at ≤ 0.7 kW.
   The source attributes that limit to available power, not to the channel. There is no controlled comparison, so this
   is not a geometry effect established by the evidence.
6. **Oscillations.** No accessed source publishes oscillation amplitudes or spectra for Hall operation on N2, O2 or air:
   - P5 tuned B for minimum oscillation (E01).
   - HT5k DM2 acquired I_d at 10 MHz and describes the signal only as "stable" (E09).
   - ECHT reports mode changes and quenching tied to a degraded cathode (E03).
   - CAMILA reports numerous spontaneous shutdowns (E10, E11).
7. **Oxygen and life.** On N2/O2 the anode oxidised within 10 h (E06). With 10 % Xe added, flame-outs appeared after
   about 314 h and were attributed to anode oxidation (E07, second-hand). The HC20h cathode eroded on an N2/O2 mixture
   (E09 observations, second-hand). Ceramic erosion was reported as compatible with 7000-9500 h, but that figure is an
   extrapolation in the source (E07).
8. **Pre-ionization stages tested on atmospheric gas.** Two devices had one:
   - **E19 (helicon Hall).** In the second-hand report, RF raised utilization slightly and lowered thrust-to-power; the
     single-stage mode also sustained on N2.
   - **E18 (RAM-EP).** This is the only intake-fed Hall-type operation accessed. It had a dedicated ionization stage,
     and its necessity was not isolated.

   A third device, E21 (ECR + cylindrical Hall), was tested only on xenon.

## What this evidence does not establish

- It does not show ignition or sustainment at the number densities, flows and compositions an intake would deliver in
  orbit (including atomic O). That regime is **TBD - requires the upstream ICD**, and no entry is scaled to it.
- It does not isolate facility effects. Background pressure is between about 1e-5 and 2e-4 Torr, and inferred ingestion
  is about 2-3.4 % of the anode flow at P5 and 2-6 % at ECHT, both from correlations. That ingested flow may assist
  sustainment in ground tests.
- For the cases that used a xenon cathode, it does not separate the cathode's xenon from the atmospheric gas.
- Long-duration xenon-free operation is not covered. The longest xenon-free duration found is 10 h cumulative (E09).
- It provides no validated threshold (flow, voltage, B or channel length) that could be carried into a design. Every
  boundary above is specific to one device and one facility.
- It does not settle the pre-ionization question for Vyovrinda hardware. Under `docs/EVIDENCE.md`, only component and
  thruster tests of that hardware in its own operating domain can do that.

## Gaps (TBD)

- MOSKOVITZ2026 Fig. 6, the minimum voltage and flow for more than 5 min of operation: TBD - requires vector or raster
  digitization with an axis-calibration record.
- Primary texts that were not accessed, so their content is known only second-hand or from abstracts:
  - Hruby et al., IEPC-2022-446 (Busek BHT and ABHET)
  - Cifali et al., SP2012 (500 h endurance)
  - Andreussi et al., IEPC-2017-377 (HT5k PFG and RAM-EP)
  - Shabshelowitz et al., JPP 2014 (helicon Hall; Deep Blue returned 403)
  - Munro-O'Brien & Ryan, Acta Astronaut. 2023 (CC BY, but 403 to automated access)
  - Dukhopelnikov et al., AIP CP 2021
  - Ferrato et al., PSST 2022
  - Marchioni & Cappelli, JAP 2021
  - Diamant, AIAA 2010-6522
- Tejeda & Knoll: O2 and air in a HET at about 1.5-1.6 kW, as cited in BRABSTON2025 Section I. Not located in this audit.
  **verify** the reference before any use.
- The measurement basis of "0.56N2 + 0.44O2" in the SITAEL papers is not stated. It reads as mole fractions (see
  `derived_checks`; verify).
- P5 ignition procedure on N2: not in the accessed text.

## Access log (URLs actually accessed, 2026-09-26)

| source id | URL | result |
|---|---|---|
| CIFALI2011 | https://electricrocket.org/IEPC/IEPC-2011-224.pdf | PDF, sha256 44b0fc26… |
| FERRATO2019_IEPC886 | https://electricrocket.org/2019/886.pdf | PDF, sha256 cba16dc5… |
| ANDREUSSI2022_IEPC435 | https://www.jotform.com/uploads/electricrocket/220994246997171/5305264492529551410/IEPC_2022_AETHER_final.pdf | PDF, sha256 525d3ad2… |
| ANDREUSSI2022_IEPC435 | https://aether-h2020.eu/wp-content/uploads/2023/11/IEPC-2022-435.pdf | captcha page; not bypassed |
| ANDREUSSI2022 | https://www.iris.sssup.it/retrieve/ea75eb42-2e80-462b-be1e-588ed43871e3/Andreussi%20et.al.%202022.pdf | PDF, sha256 092befad… |
| ANDREUSSI2022 | https://link.springer.com/content/pdf/10.1007/s44205-022-00024-9.pdf | PDF (same article) |
| BRABSTON_IEPC2024 | https://hpepl.ae.gatech.edu/sites/default/files/gbb-uploads/IEPC-24-297.pdf | PDF, sha256 ea9e763b… |
| MOSKOVITZ2026 | https://link.springer.com/content/pdf/10.1007/s44205-026-00199-5.pdf | PDF (CC BY 4.0), sha256 44954c17… |
| SEMENKIN1995 | https://electricrocket.org/IEPC/IEPC1995-78.pdf | PDF (scan), sha256 b566bb80… |
| GURCIULLO2020 | https://doi.org/10.15126/thesis.00850793 (resolves to Surrey Open Research) | landing page; the PDF read is a copy obtained from that repository on 2026-09-26 (cover-page stamp), sha256 085e514c…, CC BY-NC-SA 4.0 |
| MUNRO2023 | https://api.openalex.org/works/doi:10.1016/j.actaastro.2023.01.033 | abstract + licence metadata |
| MUNRO2023 | https://www.sciencedirect.com/science/article/pii/S0094576523000449 ; https://eprints.soton.ac.uk/475781 | 403 (not bypassed) |
| SHABSHELOWITZ2014 | https://hdl.handle.net/2027.42/140449 | 403 (not bypassed) |
| HRUBY2022 | https://electricrocket.org/2022/446.pdf | 404 |
| MARCHIONI2020 / MARCHIONI2021 / BRABSTON2025 | see the repository audits (`echt_n2/README.md`, `scripts/audit_p5_n2_measurements.py`) | read from sha256-pinned copies; not redistributed |
| GURCIULLO2019, FERRATO2022_PSST, MARCHIONI2021 | https://api.crossref.org/works/{doi} | abstract / metadata |
| DUKHOPELNIKOV2021 | https://api.semanticscholar.org/graph/v1/paper/DOI:10.1063/5.0036251?fields=title,abstract | abstract |
