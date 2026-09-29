# External-evidence package v1.1 (web track)

> **v1.1 (2026-09-27)** adds R7 (thrust-stand design basis), R8 (anode materials in oxygen) and R9 (verification pass: 39 flagged values, 18 confirmed, 5 corrected, 16 still unverified; 20 arithmetic checks, all reproduce). Corrections are marked inline. It builds on repository commit c1ce3a5 and uses nothing from the CLI track.

- **Date:** 2026-09-27.
- **Repository basis:** `782f900`, read-only. This package uses nothing the CLI track produced after that commit.
- **Authority:** frozen owner decisions A1–A7 and the committed deliverables.
- **Status:** evidence and recommendations for the owner. Nothing here is a decision, a purchase or a freeze.

**Rules applied.**
- Published and open sources only.
- No contact with suppliers, labs or authors.
- No paywall, captcha or bot-challenge bypass; TLS settings never changed.
- Third-party PDFs used during research are not committed, for copyright reasons. Citations, URLs and, where recorded, sha256 hashes are in `source_register_v1.json` (196 entries in v1.1) and in the six thread files in `threads/`.

**Evidence classes.** Every value in the thread files carries its source, evidence class, applicability and limitations. Values taken from a search snippet or from memory are marked **verify**.

| Thread | File | Scope |
|---|---|---|
| R1 | `threads/R1_compressor.*` | DI-1.4 / Li 2015 primary evidence |
| R2 | `threads/R2_rfp.*` | RFP wording |
| R3 | `threads/R3_materials.*` | H-1 materials and hardware |
| R4 | `threads/R4_instrumentation.*` | Instrumentation and calibration |
| R5 | `threads/R5_facilities.*` | Facilities and metrology labs |
| R6 | `threads/R6_xe_inputs.*` | Xe-ledger inputs |
| R7 | `threads/R7_thrust_stand.*` | Thrust-stand design basis (v1.1) |
| R8 | `threads/R8_anode_oxygen.*` | Anode materials in oxygen (v1.1) |
| R9 | `threads/R9_verify.*` | Verification of flagged values (v1.1) |

## 1. Verified external findings

**RFP (R2).**
- **The RFP document could not be obtained.** tdf.drdo.gov.in returned 503 or reset the connection. defproc.gov.in is captcha-gated and was not attempted.
- The only first-hand texts are two news articles dated 9 Sep 2026, indiandefensenews.in and idrw.org. The quotes below were checked against the saved pages:
  - "total mass under 40 kg"
  - "ambient atmospheric air supplemented with Xenon"
  - "sustained thrust levels between 12 mN and 25 mN"
  - "less than 1,500 W"
  - "three years" (26,280 h, against 26,000 h in the repo)
- **RFP number discrepancy.** The article gives `DTDF/06/13516/DSP/ABEP/XI/LM/01`; the repo has `…/X/L/M/01`.
- The following repo requirements attributed to the RFP appear in neither article: > 15,000 h firing, "Part III Para 2", the "RFP 4.1a" atomic-oxygen beam test, and no single-point failure. They are **unverified**, not refuted.
- **Close date unverified.** Search summaries of @DrdoTdf posts show both 05 Oct 2026 and 20 Oct 2026 17:00 (the latter with a 24 Sep pre-bid meeting).

**Compressor (R1).**
- No legitimate full text of Li 2015 exists (ScienceDirect 403; listed as closed by OpenAlex, Unpaywall and Semantic Scholar).
- The abstract, seen through search excerpts and marked verify, describes a 500 mm inlet and a four-stage chain.
- The capture efficiency is **simulated** (DSMC 56–58 % at high rotor speed, 42–43 % at low speed), not measured.
- **CR ≥ 3500 appears only in Moon 2025, a secondary source.** Its species, stage and pressures are unknown.
- The throat-scale rotor, which is the C1 element, appears to be simulation-only. No independent rotor-compressor data for ABEP were found.

**Xe inputs (R6).**
- No open source shows LaB6 spot mode at ≤ 0.10 mg/s at Hall-thruster current. **v1.1 correction (R9):** the MaSMi point (0.20 mg/s at 2 A, US 10,919,649) uses a **BaO-W** insert, not LaB6, so no open LaB6 point exists near this flow at all. The 0.10 mg/s target rests entirely on measuring C-1.
- Per-start cathode Xe: heated start about 72 mg (36 mg at 0.10 mg/s, arithmetic from the preheat flow); heaterless start 0.14–0.41 g.
- KM-5 flight record: 583 cycles in 1,074 h, against a 4,000-cycle requirement.
- Xe density at 150 bar (NIST): 2.05 / 1.97 / 1.67 g/cm³ at 293 / 300 / 323 K.
- Published tank-mass fractions are 0.067–0.106, but only for 40–120 L tanks. No qualified datasheet covers 2.7–18 L.
- Flow-control units: Moog < 0.97 kg (verify), Bradford < 1.16 kg, KM-5 ≤ 0.8 kg.

**Materials (R3).**
- Pole and core candidates: ARMCO 2.15 T; Hiperco 50A 2.4 T (Curie 938 °C); VACOFLUX 50 2.30 T (Curie 950 °C); 430F 1.56 T.
- The best ceramic-insulated magnet wire found is rated 500 °C for only 2,500 h.
- BN wall: M26 is rated for use above 1000 °C in air; AX05 only 850 °C.
- **Anode in oxygen:** the only evidence is of failure (Cifali 2011; Andreussi 2022, about 314 h). No open oxidation data exist for Mo, W, Ni alloys or platinum-group coatings.
- LaB6 cannot touch bare metal, because boron diffusion embrittles it.
- VCR fittings with ASTM G93 Level C cleaning, and a 13 kV alumina gas break, are available.

**Anode in oxygen (R8, v1.1).**
- No anode material is proven for an oxygen-bearing Hall thruster.
- The only direct comparison is Imperial's WET-HET on O₂ (Tejeda et al. 2024, Acta Astronautica 219, Sec. 3.5): bare W formed an insulating oxide in 20–30 min, while stainless steel "mostly" kept conducting at low power. No hours, anode temperature or resistance data were published.
- The failure mode in every oxygen-plasma report is **loss of conduction**, not mass loss (Cifali 2011; Gabriel 1993 oxygen MPD). Coupons therefore need 4-wire resistance measurement.
- **Rejected:** bare W; Mo/TZM (volatile MoO₃ above about 550 °C, Smolik 2000).
- **Leading heritage candidate:** 316L.
- **Untested in oxygen plasma:** chromia-forming Ni alloys, Pt, Rh, Cr plating, IrO₂/RuO₂ coatings.
- **Not recommended now:** graphite, which oxygen erodes chemically.

**Instrumentation (R4).**
- Flow-unit conversions are recorded, including the reference-temperature trap (0 °C versus 25 °C, a factor of 1.0915).
- The best cathode Xe flow-controller class gives about ±1.2 % at 0.10 mg/s (1.16 % on the controller's own 25 °C reference, R9). Its Xe correction factor is theoretical and needs checking on real Xe.
- The DC power-analyser class meets the 0.5–1 % targets.
- Inline RF power sensors are 5–6 % class, against a 0.9–3.5 % target.
- Ion-gauge sensitivities for N₂ / O₂ / Xe are 1.00 / 1.01 / 2.87 and can be off by 10–20 %, so each gauge needs a per-gas calibration.
- **Thrust stand (v1.1, R7).** INS-01 requires per-reading repeatability u_T ≤ 0.00498 (1σ): 59.8 µN at 12 mN and 124.6 µN at 25 mN. Published absolute uncertainties in the 5–25 mN Hall band are 1.4–2.2 %: NASA GRC 1.5 % with a 0.9 kg payload, a Tokyo balance at 1.4 %, and a Michigan Tech thesis at 2.16 %. Stands that carry many kilograms are coarser (Moeller & Polzin: 1 mN at 12.1 kg).
  - ESA's ±10 µN entries are commercial load cells rated 0.5–2.3 kg, too small for H-1.
  - ESA's ICL balance is ±0.1 mN and meets 25 mN but not 12 mN.
  - DLR's 40 kg balance is described as developed by AST; its sub-mN performance is stated as a goal, not demonstrated.
  - **Conclusion:** no open source demonstrates the requirement at 12–25 mN on a 5–20 kg payload. The stand must be proven in the S1a capability demonstration. The dominant error terms are tilt drift (about 0.3–1.2 µrad corresponds to 60 µN; verify), thermal drift, and the stiffness of service lines across the stand.

**Facilities (R5).**
- Screening pumping speed: about 208–214 k L/s at 1e-5 Torr for 3.2 mg/s N₂. The two ends of the range are the same case at 293 K and 300 K (independently recomputed).
- **v1.1 corrections (R9).**
  - ESA EPL: up to 80,000 L/s **Xe** per chamber (not 200,000).
  - Michigan LVTF: 500,000 L/s is **Xe only**; its PEPL cryopumps do not pump N₂ or O₂ (only the 13 TM1200i pumps do).
  - CSIR-NPL: the "1 mg–2000 kg" range is not on the NPL page.
  - Cathode flow split: Moog gives 5 %, or 9 % with its valve open; the "5–10 %" figure is not in the source.
  - Mooney's 2–6 sccm is 0.195–0.586 mg/s on the 0 °C basis.
  - The AIP 2016 paper is by IRS Stuttgart.
- SITAEL IV10 is the best published match: N₂/O₂ Hall operation below 2.5e-5 mbar. Its thrust stand is only ±3 mN, and access, export and custody are open questions.
- ISRO LPSC and IIST have published capabilities but no chamber specifications and no evidence that third parties can use them.
- CSIR-NPL is the Indian mass-traceability root (CIPM MRA).
- For CMTI profilometry, only an expired NABL directory entry (CC-2153) was found. No NABL scope was found for ASTM E1508 light-element EDS or ISO 15472 XPS.
- No candidate publishes an oxygen-service safety case for cryopumping.

## 2. Procurement actions safe now

These are technical judgements that each item is independent of LOCK-1 and the H-1 freeze. **Placing any order is an owner action.** Only the metrology specification is approved for procurement (A4), and wave H3 is not registered.

1. **External metrology lab.** Procure against the A4-approved metrology specification.
2. **OIML E2 calibration masses** (25 mN ≈ 2.55 g), traceable through CSIR-NPL.
3. **Precision DC power analyser**, WT5000 class. Its ranges cover any likely V_d and I_d.
4. **Cathode Xe mass-flow controller**, 0.5–5 sccm class, **quote only**. The quote must state Xe accuracy at about 1–2 sccm and the sccm reference convention.
5. **Anode N₂/O₂ mass-flow controllers**, **quote only**. The ranges are fixed by A4; the full-scale value of each range waits for the W1 test points.
6. **Primary low-flow calibrator**, quote. No Indian accredited sccm-level scope was found.
7. **3-axis teslameter**, quote. The probe stage waits for the H-1 design.
8. **Generic thermocouples, feedthroughs and reference thermometer.** Tolerance figures are marked verify.

## 3. Facility and lab options

| Need | Options (published claims only) | Score-bearing potential | To confirm |
|---|---|---|---|
| Hall vacuum testing, N₂/O₂ | SITAEL IV10 (best published match); ESA EPL, Michigan PEPL (strong, low access realism); ISRO LPSC, Bellatrix, IITs/IISc (no published specs) | unknown in every case | pumping speed on N₂/O₂, O₂ safety case, access, custody and IP (Bellatrix may be a competitor) |
| Thrust at 12–25 mN | none demonstrated at the needed resolution | — | stand design or partner (see §4) |
| Mass metrology | CSIR-NPL (NMI, CIPM MRA) | possible | service scope and lead time |
| Profilometry (ISO 25178-700) | CMTI Bengaluru | possible if its current scope covers areal measurands | current NABL certificate |
| SEM/EDS for light elements, XPS | none with a matching accredited scope found | engineering-only for now | NABL lookup by hand |
| RGA, ExB, B-field mapping | none published at candidate facilities | — | own equipment likely |

## 4. Items still blocked

- **RFP clauses**, until someone obtains the document (see §5).
- **Thrust stand:** no commercial or published option meets the resolution needed, so it has to be a design-and-build or a facility-partner item, **on the critical path**.
- **Anode material:** no proven material. R8 proposes a coupon set for the owner to decide: 316L; a chromia-forming Ni alloy; an alumina-former (control); Rh plate; Pt; Cr plate; an IrO₂/RuO₂ coating; bare W (negative control); graphite (optional). Coupons should be biased to collect electron current and measured by 4-wire resistance.
- **Magnet-wire and pole material:** waiting on HWQ-18, HWQ-19 and HWQ-20.
- **BN grade:** HWQ-08 and HWQ-17, plus the manufacturer's datasheet.
- **LaB6 cathode assembly:** no open commercial catalogue; waiting on C-1 selection.
- **Xe tank model for 2.7–18 L:** no datasheet in that range.
- **Anode ignition Xe, transfer time and fallback durations:** only H-1 Phase 1 can supply these.
- **Waiting on LOCK-1 or the facility choice:** ion gauges (facility), feed-pressure manometer (W1), discharge-oscillation probe (S1 spectrum), RF and microwave power sensors (LOCK-1), pyrometer (HW-C1-09), RGA (minimum-set decision).
- **Compressor DI-1.4:** Li 2015 not yet read first-hand. It is not on the H-1 path.

## 5. Owner decisions required

Listed by thread; the full wording is in each thread file's `owner_questions` or `open_questions`.

**Access actions (owner only):**
1. Obtain the RFP document from defproc or tdf.drdo.gov.in; the captcha needs a person.
2. Verify the RFP number (XI/LM vs X/L/M) and the close date (05 Oct vs 20 Oct).
3. Acquire Li 2015 legitimately: library, interlibrary loan or purchase.

**RFP readings (unchanged; the news text does not resolve them):**
- OD-XE-8: is Xe inside the 40 kg?
- OD-XE-6: what does "supplemented with Xenon" mean operationally?
- OD1: the meaning of the 12–25 mN range.
- 26,000 h vs "three years" (26,280 h).

**Xe:**
- Heated or heaterless C-1?
- Is Xe flowing during preheat booked to the ledger?
- Maximum Xe storage temperature for tank sizing.
- Is a filter-getter in scope?

**Materials:**
- Pole material.
- Ceramic magnet-wire trade-off.
- Which anode coupon candidates to test.
- Adopt ASTM G93 Level C cleaning?
- Get blocked datasheets through owner channels.

**Instrumentation:**
- Thrust-stand type and the mass it must carry.
- Is an RGA in the minimum set?
- C-1 pyrometer view (HW-C1-09(b)).
- Plus four further questions in R4.

**Facilities:**
- Are foreign facilities admissible?
- Make an official request for the LPSC specifications?
- Fallback if T-PB-MAX cannot be met.
- Force-traceability class.
- Accreditation rule for XPS and EDS.
- Split the engineering S1a facility from the score-bearing facility?

**Thrust stand (R7, OD-TS-1..7):**
- Stand type: torsional, null inverted pendulum, or double pendulum.
- Maximum moving mass (W3).
- How service lines cross the stand, including RF/microwave shams versus wireless transfer.
- Build vs partner (DLR, ESA, Surrey) vs buy (AST).
- Calibration traceability.
- A pre-registered S1a u_T test at 12 mN with maximum payload and all lines installed.
- Whether to keep the 1 % absolute gate, which is below every published number found.

**Anode (R8, OQ-R8-1..5):**
- 316L as the H-1 baseline anode, with its limitation recorded.
- Which coupon candidates to test.
- Biased or floating coupons.
- An anode temperature target.
- Legitimate acquisition of Tejeda 2023, Bayliss & Knoll 2025, Cifali 2012 and Wang 1995.

**Suppliers:** whether to request supplier quotes at all. That means contacting suppliers, so it is your call.

## 6. Repository artifacts to update later

These are not edited here. The CLI track or a later reviewed lane should make the changes.

| Artifact | Change |
|---|---|
| `docs/traceability/rtm_v1.json` and hard-gate RFP records R1–R7 | Record the news-article wording as secondary evidence. Flag the RFP-number discrepancy, 26,000 vs 26,280 h, and the requirements not found (> 15,000 h, Part III Para 2, RFP 4.1a). |
| `CLAUDE.md` "What this is" (bid close, RFP number) | Only after the document is obtained. |
| `docs/architecture_comparison/compressor_downselect/` EV-08 | ~60 % is model-derived; CR ≥ 3500 is unverified and comes via Moon 2025; the rotor is not experimentally demonstrated. C1 status unchanged. |
| `docs/budgets/xe_ledger/xe_ledger_v1.json` | Add R6 analogue evidence (per-start Xe, tank fractions, density versus temperature) as illustrative inputs. Parameters stay TBD. |
| `docs/experiments/hardware/hardware_requirements_v1.json` (HW-MC-13, HW-H1-05, HWQ-08, 17, 18, 19, 20) | Candidate materials with sourced properties. |
| `docs/experiments/magnet_coil/magnet_coil_qualification_v1.json` | Schupp KD500 rating (2,500 h at 500 °C, 150 V AC). |
| `docs/experiments/lifetime_ao/` | Anode-oxidation evidence gap; propose anode coupon candidates. |
| `docs/experiments/instrumentation/` and `metrology_spec/` | Flow-convention rule, per-gas ion-gauge calibration, thrust-stand gap, RF-sensor accuracy gap. Also fix the metrology spec file status, which still says DRAFT although A4 approved it. |
| `docs/architecture_comparison/lock1/` (D-12, T-PB-MAX) | Facility screening numbers and candidate list. |
| `docs/experiments/instrumentation/` INS-01 | Record the R7 literature basis; qualify "no commercial mN balance" (AST built DLR's balance; ESA uses modified load cells). |
| `docs/experiments/lifetime_ao/` coupon plan | R8 candidate set; resistance-based failure criterion. |
| `docs/budgets/owner_decisions/` (the register in the CLI track) | Add the owner questions from §5. |
