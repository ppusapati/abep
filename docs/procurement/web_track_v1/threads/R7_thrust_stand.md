# R7: thrust stand design basis (web track, 2026-09-27, repo c1ce3a5, read-only)

Companion to `R7_thrust_stand.json`, which holds the full source register, the per-design records with locators, and the evidence classes. Every value below is quoted from its source. Values derived in this thread are marked *model-derived here*. Values from memory, OCR or search snippets are marked *verify*.

## 1. What the repo requires (quoted)
- **INS-01 per-reading repeatability.** u_T,max = 0.0049836144 relative (1σ, per reading, Type A) at n = 4. That is **59.8034 µN at 12 mN** and **124.59 µN at 25 mN** (model-derived, lane 25 `minexp_numbers.py`). Repo feasibility status: **AT_RISK**.
- **Installation reproducibility.** u_inst,max = 0.0024918072 in ln(T/P_bus) per installation, measured by S1b (K = 6). HW-SVC-03 splits it into five equal RSS shares (c1 stand calibration and zero, c2 alignment, c3 B(z), c4 gas path, c5 service line, thermal and electrical).
- **Absolute gate.** I-U-ABS-T 1 % (1σ), PROPOSED.
- **Calibration.** At least 10 in-situ calibrations before and at least 10 after each sequence. The zero is taken with power and flow off. End-to-end calibration under vacuum is repeated after every configuration change (HW-SVC-02). HW-SVC-01 requires every line to be present in every configuration, with shams where needed.
- **Mass on the stand is not fixed by the repo.** INS-01 lists the range as TBD, pending "mass on stand incl. the RF/ECR modules (W3)". The 40 kg figure is the system-level RFP limit, with "no H-1/C-1 allocation". The 5–20 kg band used in this thread is an assumption.

## 2. Design-basis table: demonstrated performance against payload

| id | architecture | payload (kg) | thrust (mN) | demonstrated number | class | source |
|---|---|---|---|---|---|---|
| D-GRC-LOWPOWER-HALL | inverted pendulum (GRC) | 0.9 | 5–20 | 1.5 % est. uncertainty | review citing Manzella 1996 | Polk 2017 §III.B |
| D-MTU2023 | null inverted pendulum | n/s | 19 | 0.411 mN (2.16 %) overall; calibration 1.242 % | abstract | Kalkman 2023 |
| D-TOKYO-DUAL | dual pendulum (cancels thermal drift) | n/s | Hall | < 0.25 mN (1.4 %) | abstract | Nagao 2007 |
| D-SURREY-TORSION | torsional, water-cooled pivot hub, liquid-metal pots, wireless microwave | n/s | Hall 3–20; ECR 0.3–1.5 | "accurate and repeatable" (no number in abstract) | abstract | Masillo 2022 |
| D-ESA-ICL | hanging pendulum, self-compensating heating, voice coil + pulley | n/s | 1–600 (ESA); lin. 0.5–100 | ESA table: "±0.1 mN" in the Resolution column; paper: σ better than 0.27 mN at low thrust | facility-declared + abstract | ESA EPL page; Schwertheim 2021 |
| D-ESA-LOADCELL | modified commercial weighing load cell | ≤ 0.5 / 2.3 (capacity) | n/s | "±10 µN" (uncertainty, best practice); "0.1 mg ≡ 1 µN" | facility-declared | ESA EPL page |
| D-ESA-ALTA | inverted pendulums | n/s | 5–500; 0.2–10 | ±2 mN | facility-declared | ESA EPL page |
| D-AST-2KG | counter-balanced, voice-coil compensated | ≤ 2 | 0.1–250 | plateau stability "by far better than 0.1 mN" at 10 mN; drift < ±250 µN over 27 h (in air, no thruster) | full text | Harmann 2015 |
| D-VAHPER | hanging pendulum, gallium pots, water-cooled base | capacity 125 | CHT 4.8–6.2 | "ultimate resolution ... ~50 µN" without thruster (OCR, *verify*) | full text (OCR) | Polzin 2006 |
| D-MOELLER2010 | hanging pendulum variant | 12.1 / 90.7 | ~100 / ≥ 500 | 1 mN at 100 mN; ~2.5 mN at ≥ 0.5 N | full text | Moeller & Polzin 2010 |
| D-XU2009 | null inverted pendulum, active leveling and cooling | capacity 250 | ≤ 230 (3.4 kW Hall) | ±0.6 % | abstract | Xu & Walker 2009 |
| D-DLR-AST-40KG | inverted double pendulum, cable harp, voice coil + gravimetric calibration | ≤ 40 | 250 range | stated goal only: "0.1 % … well below 1 mN" | facility paper / abstract | JLSRF 2018 §4.4; Neumann 2021 |
| D-GRC-VF6 | null-coil inverted pendulum | 46.7 | 100–600 | ±6.9 mN (95 %), instrument bias; repeatability not addressed | full text | Mackey 2018 |
| D-SPRINGWIRE | inverted pendulum with spring-shaped lines | n/s | 1 kW MPD | normalised std 1.8e-3; thermal drift ~4.5e-3 mN/s | abstract | Yamasaki 2023 |
| D-BUSTLAB | double inverted pendulum | ≤ 80 | ~6–300 | ~100 µN resolution; example calibration ±2.32 mN (95 % PI) | full text | Kokal MS / IEPC-2017 |
| D-MEAS2024 | pendulum, two configurations | n/s | ranges 1.8 and 450 | 100.00 ± 0.19 mN in 1 min | snippet (*verify*) | Measurement 2024 |

n/s = not stated in the source that was read.

## 3. What is achievable at 12–25 mN with a 5–20 kg payload
- **Verdict.** The target has **not been demonstrated in open literature. It is plausible but unproven.** No source read reports ≤ ~60 µN (1σ) per-reading repeatability at 12–25 mN with a 5–20 kg payload.
- **Absolute uncertainty.** Published absolute uncertainties in the 5–25 mN Hall band are **1.4–2.2 %**: GRC 1.5 % at 0.9 kg, Tokyo 1.4 %, MTU 2.16 %.
- **Balances that carry multiple kilograms.** The best numbers found are:
  - ESA ICL: 0.1 mN resolution (facility-declared, payload not stated).
  - DLR/AST 40 kg balance: "well below 1 mN" (a goal).
  - MSFC: 1 mN at 100 mN with 12.1 kg.
- **ESA lead (re-assessment).** The "±10 µN" entries are weighing load cells with **0.5–2.3 kg capacity**, which cannot carry the H-1 stack. The ICL balance's 0.1 mN resolution would meet the 25 mN target (124.6 µN) but not the 12 mN target (59.8 µN) on a single reading. The original claim is therefore narrowed, not overturned.
- **The target is Type A repeatability, not absolute accuracy.** That is a weaker requirement than the published numbers. However, no source separates Type A repeatability at this thrust and mass class.
- **The proposed 1 % absolute gate is below every open absolute number found in this band.** The best found is 1.4 %.
- **Scaling (*model-derived here*).**
  - mg/T ranges from 4.1e3 (5 kg at 12 mN) to 1.6e4 (20 kg at 12 mN). The NASA VF-6 case, at 1023, already had inclination drift as a dominant term.
  - A base tilt γ acts roughly like a force m·g·γ (*verify* against Polk Eq. 16). On that basis, 60 µN corresponds to about 1.2 µrad at 5 kg and about 0.3 µrad at 20 kg.
  - A thermal drift of 4.5e-3 mN/s (1 kW MPD) equals 60 µN in about 13 s.
- **Consequence.** The target has to be proven by a pre-registered S1a capability demonstration before LOCK-2 fixes n. The demonstration should use a dummy payload at the heaviest configuration mass, all SVC-1 lines and shams, and a representative heat load. If u_T comes out above 0.5 %, the pre-registered lever is larger n, not relaxing the target post hoc.

## 4. Dominant error terms (in order, for this case)
1. **Inclination (tilt) drift.** It scales with mg/T and was one of the two dominant terms at GRC VF-6 (Mackey 2018). Inverted and hanging pendulums need active leveling. A torsional stand's response is independent of thruster mass (Polk 2017; INS-01).
2. **Thermal drift of zero and gain.** Compact inverted pendulums absorb heat from the thruster. Shrouds and active cooling are essential, and frequent recalibration is needed (Polk §III.B, §VI.B). MTU found temperature to be "a large factor" in drift. The Tokyo dual pendulum cancels it differentially, and the Surrey and ESA ICL designs regulate the pivot thermally.
3. **Service-line stiffness and tare (SVC-1).** Lead and tubing stiffness sets sensitivity. Stranded conductors give non-repeatable tares, and cables expand thermally. Published remedies:
   - liquid-metal pots (MSFC, Surrey);
   - cable harp or waterfall routing (DLR, BUSTLab), though BUSTLab still saw residual null drift;
   - spring-shaped lines (Yamasaki);
   - wireless microwave transfer (Surrey).

   Module exchange changes the stiffness unless every configuration carries the same line set, as HW-SVC-01 requires. Per-configuration calibration (HW-SVC-02) captures the stiffness change but not its drift.
4. **Payload mass change between HW-0, RF and ECR.** In a pendulum, sensitivity and natural frequency change with mass, so re-ballasting and re-calibration are needed.
5. **Electromagnetic interaction.** MC-1 and the ECR magnets can act on a null coil, voice coil or eddy damper. Mitigations: non-ferrous materials, distance, and a magnetic-tare map with the discharge off (Polk §VI.B).
6. **Calibration transfer.** Pulley friction, monofilament stiffness, alignment and local g all matter (Mackey Table 4). A voice coil is faster but can carry systematic error, while gravimetric calibration is traceable (DLR). The mass standard itself is negligible (E2).
7. **Facility vibration.** Polk gives an example: 0.025 mm of noise on a 2.5 mm full-scale deflection is 1 %.

## 5. Owner decisions
- **OD-TS-1: Stand principle.** The options are:
  - torsional (Surrey Hall + ECR precedent; response independent of mass; larger chamber);
  - null-type inverted pendulum with leveling and a water-cooled enclosure (GRC / Xu-Walker);
  - double or dual pendulum (DLR/AST 40 kg; Tokyo).

  This is INS-01 open decision 2.
- **OD-TS-2: Maximum moving mass and its spread across configurations (W3).** This sets mg/T, the tilt tolerance and the counterweights.
- **OD-TS-3: How lines cross the stand.** Options include liquid-metal pots for DC, a harp or spring-shaped routing for gas, and either a hard RF/microwave line with shams or wireless transfer.
- **OD-TS-4: Build, partner or buy.** Build from a published basis, or partner with a facility that already runs a multi-kg mN balance. Examples: DLR STG-ET (40 kg AST balance), ESA EPL Corona (ICL 1–600 mN; 80,000 L/s *Xe*), Surrey. Buying would mean a maker with a published balance, such as AST. No vendor or lab was contacted.
- **OD-TS-5: Calibration principle and traceability class.** INS-01 lists this as TBD.
- **OD-TS-6: Pre-registered S1a acceptance test for u_T at 12 mN.** It should run with the maximum payload and all lines installed.
- **OD-TS-7: Keep or revise I-U-ABS-T = 1 %.** Open literature in this band shows 1.4–2.2 %.

## 6. Notes and caveats
- **Commercial balances do exist.** Repo R4 says "no commercial mN EP thrust-balance located", which should be qualified. Neumann 2021 states that DLR runs a 40 kg / 250 mN balance "developed by the company AST", and ESA lists "modified commercial load-cell" balances. No datasheet was read that gives performance at 12 mN with a multi-kg payload.
- **A secondary source misattributes a drift figure.** The Kokal thesis credits Harmann 2015 with "thermal drift < 0.1 % per degree". Harmann 2015 does not say that; it states < ±0.1 % of full scale over 27 h. Do not propagate the thesis wording.
- **ESA pumping speeds are Xe values.** N₂ speeds are listed only for the small chambers. The coordinator adds that the 500,000 L/s quoted for UM LVTF is also Xe, and that only its 13 TM1200i pumps handle N₂/O₂. I did not verify that here.
- **Access limits.** These were not read in full: Masillo 2022 and Schwertheim 2021 (both CC BY; publisher challenge pages), Xu 2009, the Kalkman thesis (Cloudflare), Neumann 2013 and 2021, and Kodys 2006 (host down). They are listed as unresolved in the JSON. No challenge or paywall was bypassed.
