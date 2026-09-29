# Cathode / neutralizer evidence dossier (v1)

**Status:** evidence dossier only, 2026-09-26, base commit `efc4a4e`. It changes no simulator parameter, threshold, frozen
dataset, chemistry table or campaign file. The authoritative record is
[`cathode_evidence_v1.json`](cathode_evidence_v1.json). Every number there carries a source, locator, evidence level,
quantity type (evidence class) and verification status, and `tests/test_cathode_dossier.py` checks this. This page
summarizes that record. Where the two differ, the JSON wins.

It follows `docs/EVIDENCE.md`. The evidence level (1–7) grades the source. The quantity type (measured / digitized /
inferred / reconstructed / model-derived / assumed) says what happened to the number. No Vyovrinda cathode exists, so no
value is level 1 or 2. Level 3 here means a primary experimental report on hardware of the same cathode concept. Level 5
means a textbook, review, second-hand quote, or a number known only from a document title. Level 7 means a repository
constant with no located source.

## 1. Decision and scope

- **System baseline: Xe-fed hollow cathode** (thermionic; LaB6 or BaO-W emitter).
- **Atmospheric-gas-fed cathode operation: UNRESOLVED** for the RFP use case.
  - No retrieved source shows a thermionic hollow cathode running on air, N2 or O2.
  - The air-fed plasma cathodes that have been demonstrated (AMPCAT microwave; NewOrbit RF) reach ≤ 0.9 A. Continuous
    operation is reported only up to 2 h (AMPCAT), and neither has a life test.
  - A Hall cathode must carry the full discharge current I_d (TBD) for > 15,000 h of firing.
- This dossier does not claim ABEP closure, an architecture winner, a cathode selection or any Hall transport admission.
  It proposes no retuning.

## 2. Required electron current: symbolic only

A Hall cathode supplies both the beam-neutralizing electrons and the electrons that enter the channel (Goebel & Katz
2008, book p. 248). With a keeper powered in steady state, the cathode emits the keeper current as well (NEXT
neutralizer: total emission = keeper + beam; Herman et al. 2009).

| | relation |
|---|---|
| E1 | I_emit = I_d + I_k (I_k = 0 if the keeper is off after ignition) |
| E2 | I_d = P_d / V_d |
| E3 | P_d = η_PPU,anode · (P_EP,max − Σ P_aux,j / η_PPU,j). P_EP,max is bounded by the RFP "< 1.5 kW" (which loads it covers is TBD against the RFP text) |
| E4 | I_b = η_b · I_d |
| E5 | I_emit,max / I_emit,min over the operating envelope. The minimum sets the flow-margin / plume-mode limit |
| E6 | m_Xe,cathode = ṁ_c · t_fire, with t_fire > 15,000 h |
| E7 | Air-fed plasma cathode only: ṁ_c,air = M_eff · I_emit / (e · U_i) and P_c = I_emit / C_e (definitions from Tisaev et al. 2024, Eq. 1) |
| E8 | J = I_emit / A_emit = A_R T² exp(−eφ/kT), with φ depending on O coverage. p_O,emitter = f_shield · p_O,local, and f_shield has no located source |
| E9 | t_life ≥ t_fire × margin (TBD). N_ignitions ≥ mission firing schedule (TBD) |

**Numeric evaluation: TBD.** It needs Vyovrinda V_d and P_d at the RFP points, which in turn need either an admitted
Hall closure or hardware data. Gate 3 is FAIL, the credible set is empty, and absolute Hall numbers are withdrawn. It
also needs the PPU efficiency, the auxiliary-power split inside 1.5 kW, and the keeper policy. No current is derived
here from thrust.

These context points are not requirements:
- a laboratory LaB6 cathode normally used with a 1.5 kW SPT-100-derived thruster runs at a 5 A nominal point;
- a heaterless LaB6 cathode for a sub-kW Hall thruster has a title-level 13,011 h demonstration;
- an RF plasma cathode delivering 3.3 A is claimed sufficient for a 1-kW-class Hall thruster.

## 3. Candidates at a glance

| candidate | status | best demonstrated current | longest duration located | O / air exposure evidence |
|---|---|---|---|---|
| Xe-fed LaB6 hollow cathode | **BASELINE candidate** | 2–19 A range (lab, diode, Xe) | 13,011 h heaterless LaB6 (title only, verify) | O2 must reach ~1e-5 Torr to degrade emission below 1440 °C. Tolerates up to 1e-4 Torr at 1570 °C. Ran in 1e-3 Torr O2 at > 1600 °C (textbook). Up to 12 % air mixed into the Xe feed caused sparking and erosion (secondary) |
| Xe-fed BaO-W hollow cathode | candidate, purity-sensitive | 12 A for 27,800 h; NEXT neutralizer 4.0–6.52 A total (inferred) | 51,184 h (NEXT LDT); 27,800 h (ISS life test) | ~1e-7 Torr O2 fully poisons at 1100 °C and ~1e-6 Torr H2O poisons below 1110 °C (diode tests). In a hollow-cathode plasma, poisoning appears only above 10 ppm O2 at low current (secondary). Purifier to 10 ppb |
| C12A7 electride | immature | ~1.4 A hollow insert (melts at ~2 A); 2.8 A (Rand) | ~1000 h planar on Kr (secondary); 17 h and > 60 h hollow on Xe | Stable in air at room temperature, but oxidizes to an insulating ceramic at temperature. Oxygen-resistance claims conflict |
| RF plasma cathode | not baseline | 3.3 A on Xe (140 W RF); ≤ 0.45 A on 50:50 N2/O2 (90 W) | none reported | no emitter to poison; design rationale only |
| Microwave plasma cathode | not baseline | 0.8 A for 2 × 120 min on air (AMPCAT); 0.54 A on Xe (μ20) | 2 h on air; μ10 on Xe: 48,000 h ground and > 6,500 h space (second-hand) | antenna erosion and MoOx deposition on air, mitigated by alumina; O⁻ fraction unknown |
| DC E×B plasma source | not baseline | 0.24 A on air (secondary) | none | none |
| Thermionic hollow cathode fed with air/N2/O2 | **UNRESOLVED** | none located | none | only adverse or indirect evidence |

### 3.1 Xe-fed LaB6 hollow cathode (baseline candidate)

- **Current.** Joussot et al. 2017 ran 2–19 A at 0.2–0.6 mg/s Xe in diode mode, with a 5 A / 0.4 mg/s nominal point.
  That laboratory cathode is normally used with the SPT-100-ML. Zschätzsch et al. 2022 extracted up to 2.5 A of anode
  current with 3–7 A keeper current. A tabulated "typical HCN LaB6" gives 4.0 A at 0.2 mg/s and 130 W (second-hand).
- **Start-up.**
  - Joussot: 184.5 W heater power at the ignition setting, emitter ~1420 °C. Ignition allowed above ~1300 °C.
  - Zschätzsch: up to 400 W heater power (non-optimized design) and at least 3 A keeper for self-heating.
  - A heaterless design reports 25,000 ignitions (title only, verify).
- **Steady heater.** Hollow cathodes normally self-heat with the heater off (textbook). Joussot's flat-disk laboratory
  cathode self-heats only from 5 A and otherwise needs ~185 W.
- **Emitter.**
  - More than 10 A/cm² needs about 1650 °C. Joussot measured about 1600 °C at 19 A.
  - Table 6-1 work functions range from 2.66 to 2.91 eV. The repository's 2.66 eV / 29 A/(cm² K²) matches the Lafferty
    row.
- **Purity.** LaB6 tolerates 99.99 % Xe (textbook).
- **Exposure.**
  - O2 thresholds as in the table above.
  - Hot LaB6 survived exposure to atmospheric-pressure air and water vapour and restarted normally (anecdotal).
  - **No atomic-O or N2 data.**
- **Recovery.** No activation or conditioning is needed. The mitigation for O2-bearing plasma is a higher emitter
  temperature; the life and power cost of that is not quantified.
- **Life.**
  - Evaporation model: "tens of thousands of hours" (model).
  - More than 300 Hall thrusters have flown with LaB6 cathodes (second-hand heritage count).
  - 13,011 h heaterless proto-flight test (title only; current and anomalies must be read from the paper).

### 3.2 Xe-fed BaO-W impregnated hollow cathode

- **Life.**
  - ISS plasma-contactor cathode: 27,800 h at 12 A on 4.2 → 4.7 sccm Xe. It ended when the cathode failed to ignite.
    Destructive analysis found two forms of barium tungstate over most of the emitter.
  - NEXT LDT: 51,184 h. The neutralizer ran at a 3 A fixed keeper plus 1.0–3.52 A beam. Both inserts re-ignited at low
    voltage after the test.
  - NSTAR ELT: 30,352 h in the chapter text and 30,152 h in a figure caption; the keeper was fully eroded.
  - Depletion model: > 100,000 h is achievable with a thick enough insert (model).
- **Keeper and heater.**
  - NEXT neutralizer keeper: 3 A at 10.7–11.2 V, so ≈ 32–34 W (inferred).
  - ECHT laboratory HCN-252: heater left on at 8 A × 8.5–9 V ≈ 68–72 W (inferred, from the repo audit). Keeper 15–20 V,
    with runaway to 30–40 V.
- **Purity and exposure.**
  - Propulsion-grade Xe is 99.9995 %.
  - Diode tests: ~1e-7 Torr O2 fully poisons at 1100 °C; ~1e-6 Torr H2O poisons below 1110 °C.
  - In a hollow cathode, poisoning appears only at low current and > 10 ppm O2 (textbook summary of Polk 2006; the
    primary was not read and its indexed abstract reads differently, see U07).
  - Oxygen contamination was the primary degradation cause in the NASA programme before the ISS life test.
- **Recovery.** A conditioning procedure after any suspected atmospheric exposure. Barium recycling in the plasma extends
  life.

### 3.3 C12A7:e- electride

- **Operation.**
  - Heaterless room-temperature start on Xe (Rand 2014): > 60 h over two months, 20 restarts, 11 vent cycles.
  - Giessen hollow insert: ~1.4 A for ~17 h at 5–7 sccm Xe. It needed ~110 W heater support and melts at ~2 A. Preheat
    was ~175 W; the first-generation insert needed ~900 V to ignite.
  - Planar heaterless cathode: nearly 1000 h on krypton (second-hand via Becke et al. 2026).
- **Material limits.**
  - Melting point 1230 °C (electride form).
  - Thermal conductivity ~4.5 W/(m K).
  - Work function 0.52 ± 0.03 eV (measured), 0.76 eV (measured), or 2.4–2.96 eV (quoted for thermionic emission), which
    makes emission predictions unusable (U09).
- **Oxygen.** Asserted to be far more O-resistant than BaO-W. Measured: oxidized at 1000 °C with residual O2, and turned
  into an insulating ceramic inside hollow cathodes with trace water in the iodine feed (U10). No air/N2/O2-fed
  operation located.

### 3.4 RF plasma cathode

- Watanabe et al. 2015: 3.3 A at 140 W RF, 0.3 mg/s Xe, 58 V. The electron cost is four times that of a hollow cathode.
- NewOrbit (IEPC-2025-378, preprint, not peer reviewed): up to 0.45 A at 25 W with 0.15 sccm Xe, or at 90 W with
  0.8 sccm 50:50 N2/O2 (0.018 mg/s). That is ≥ 200 W/A on air (inferred). It neutralized an air-fed RF gridded ion
  engine. The paper plans 300 h / 100-cycle tests (future). **No life data.**

### 3.5 Microwave plasma cathode

- **AMPCAT** (Tisaev et al. 2024, CC BY).
  - Two 120-min tests on 0.1 mg/s of 0.48 O2 + 0.52 N2: 0.79–0.80 A at 70 W input microwave power and 0.52–0.56 A at
    48 W.
  - Power cost 1/C_e = 144.8 and 142.1 W/A, anode bias excluded, so P_tot ≈ 114–116 W at 0.8 A (inferred).
  - Air maximum 0.90 A (Table 6).
  - The antenna eroded and MoOx deposited within ~1 h; alumina isolation mitigated both.
  - The extracted current may include O⁻ ions (unquantified).
  - The connector needed water cooling in test.
- **JAXA μ10 / μ20 on Xe.** μ10 nominal 0.18 A; 48,000 h ground and > 6,500 h in space (second-hand, single-unit vs
  cumulative unclear). The μ20 neutralizer neutralized a 0.54 A beam at < 30 V coupling with 1 sccm Xe.

### 3.6 Thermionic hollow cathode fed with air / N2 / O2: UNRESOLVED

The only direct datum is adverse. A LaB6 hollow cathode fed Xe with up to 12 % of a 0.48 O2 + 0.52 N2 mixture showed
plume sparking and internal erosion within a short test. This is quoted by Tisaev et al. from the AETHER paper, which was
not retrievable.

A LaB6 cathode run inside a 1e-3 Torr O2 background is not a gas-fed demonstration. A 2025 Vacuum study of O2 impurities
in a LaB6 hollow cathode coupled to a Hall thruster exists but could not be retrieved (lead, U06).

## 4. System-level precedents (anode on N2/air, cathode on noble gas)

| test | anode gas | cathode | duration | source |
|---|---|---|---|---|
| PPS1350 | N2; 1.27 N2 + O2 | Xe hollow cathode | 10 h per gas, stable; ≤ 350 V, ≤ 1.4 kW | Cifali et al. IEPC-2011-224 |
| P5 | N2 5.0–5.4 mg/s (also Ar, Xe) | EPL HCPEE 500 on Xe, 0.44 mg/s (4.5 sccm), ≈ 8.1–8.8 % of anode mass flow (inferred) | setpoint campaign | Brabston et al. IEPC-2024-297 (cathode description only; no P5-N2 campaign result used) |
| ECHT | N2 ~2 mg/s | IonTech HCN-252 (BaO) on Ar 0.15–0.74 mg/s; emitter believed degraded; keeper runaway | setpoint campaign, I_d 1.5–3.9 A | Marchioni 2020 thesis via repo audit |
| NewOrbit AURA | 50:50 N2/O2 (RF gridded ion) | RF cathode on 50:50 N2/O2 | thrust-balance campaign | Schwertheim et al. preprint |

## 5. Repository cross-check (documentation only; nothing changed)

Changing any of these is a model change for the owner: goldens may move, and the change must be logged in
`docs/HISTORY.md`.

- `plasma_devices.LaB6Cathode.phi0_eV = 2.66` and `A_richardson = 29 A/(cm² K²)` are **consistent** with Table 6-1
  (Lafferty row).
- **Unsourced** (level 7):
  - the coverage-model constants (`delta_phi_poison_eV`, `E_des_eV`, `nu_des_Hz`, `s0_stick`, `k_clean_nu_Hz`,
    `E_clean_eV`, `N_s`);
  - `shield_attenuation = 1e-3`;
  - the 0.1 plume O factor in `system.py:155` and `archengine.py:528,535`;
  - `heater_W = 30`, `keeper_W = 15`, and the Xe cathode power 40 W / 45 W;
  - the Xe cathode flow of 0.05 mg/s (literature Hall cathodes in the retrieved tests used 0.4–0.44 mg/s at different
    sizes);
  - the `12 A × ṁ/0.05` current scaling;
  - the evaporation constants;
  - `cathode_start_limit = 10,000`.
- **AMPCAT calibration ("0.8 A at 145 W, 0.1 mg/s air")** in `archengine.py:91,136`, `thruster.py:96` and HISTORY. The
  source gives 0.79–0.80 A at 70 W input microwave power with an average 1/C_e of **144.8 W/A**. "145" matches the W/A
  figure, not a total power. P_tot at 0.8 A is ≈ 114–116 W (inferred, anode bias excluded).
- `mw_air` validated ceiling 1.0 A vs 0.90 A tabulated. `MW_AIR_CATHODE.o_life_h = 3000 h` vs only 2 × 120 min of
  continuous tests reported.
- `rf_cathode` "no data" (0.5 A) vs the NewOrbit preprint's ≤ 0.45 A at 0.018 mg/s (the code assumes 0.05 mg/s).

## 6. Uncertainty register

| id | item | resolution |
|---|---|---|
| U01 | Required emission current: I_d unknown (gate 3 FAIL) | gate 3 or thruster test (G01) |
| U02 | Transfer of Xe-only vacuum life data to an N2/O-rich VLEO plume | G02, G04 |
| U03 | O / O2 partial pressure at the emitter in flight (unsourced repo factors) | G02 + validated plume model |
| U04 | Atomic O vs O2 poisoning: only O2/H2O data exist | G02 |
| U05 | N2 / N effects on LaB6 and BaO-W: no source | G03 |
| U06 | LaB6 O2 tolerance statements under different conditions | read Vacuum 2025 and AETHER primaries; G02 |
| U07 | BaO-W O2 tolerance: textbook summary vs indexed abstract of Polk 2006 | read primary |
| U08 | LaB6 work function / Richardson coefficient spread (2.66–2.91 eV) | G01 insert characterization |
| U09 | C12A7 work function spread (0.52 eV to 2.96 eV) | G08 |
| U10 | C12A7 oxygen resistance: assertion vs measured oxidation | G08 |
| U11 | AMPCAT electron fraction (O⁻), 2 h duration, antenna erosion, cooling | G07 |
| U12 | μ10 hours second-hand, single vs cumulative | read primary |
| U13 | Source-internal inconsistencies (30,152 vs 30,352 h; 27,800 vs ~28,000 h; 3.2 vs 3.76 A) | carried as reported |
| U14 | Heater and keeper power are design-specific; repo constants unsourced | G01, G05 |
| U15 | Ignition cycles: schedule undefined; 25,000 heaterless ignitions title-only; repo limit unsourced | profile + G04/G05 |
| U16 | Cathode Xe flow and mission Xe mass (0.05 mg/s in the repo vs 0.4–0.44 mg/s in retrieved tests) | G06 |
| U17 | Cathode coupling and wear in an N2/air Hall plume: short facility tests only | G01, G09 |
| U18 | Power cost of air-fed plasma cathodes (142–178 W/A; ≥ 200 W/A) vs ~33 W/A hollow cathode | only if the air-fed path is reopened |

## 7. Gaps that require hardware tests

- **G01** Cathode at the Vyovrinda I_d on the Vyovrinda Hall thruster with N2/O2/air anode flow. Measure coupling and
  keeper voltage, spot/plume margin vs flow, emitter temperature and the heater-off limit.
- **G02** Poisoning by atomic O, O2 and H2O at VLEO-representative partial pressures near the orifice and keeper, with an
  atomic-O source. Measure emission, temperature, work-function drift and recovery, for LaB6 vs BaO-W.
- **G03** N2 / N exposure of thermionic emitters, followed by surface analysis.
- **G04** Wear and life test in a representative mixed-gas background, with keeper, orifice and insert wear, a life-model
  validation plan against > 15,000 h firing, and ignition cycling per the mission profile. Duration and acceptance
  criteria are TBD and to be pre-registered.
- **G05** Heater cycling life, or heaterless ignition-count qualification, with exposure between starts.
- **G06** Minimum Xe cathode flow for spot-mode margin vs current and orifice erosion, to size the mission Xe.
- **G07** Air-fed plasma cathode viability, only if the UNRESOLVED path is reopened. Needs multi-ampere current at
  acceptable W/A, the electron vs O⁻ fraction, long-duration erosion, coupling to an air-fed Hall thruster, and flight
  thermal design.
- **G08** C12A7 material qualification, only if pursued. Needs the work function of the actual lot, oxidation at
  operating temperature, and a thermal design that stays below the melting point.
- **G09** Facility-to-flight transfer of background pressure and composition near the cathode.
- **G10** Ground handling and launch exposure: storage, purge and conditioning procedures.

## 8. Leads not entered (numbers seen only in search summaries, or primaries not retrievable)

The JSON `leads_not_entered` block lists what must be read before these studies are used:
- Polk 2006 (AIAA-2006-5153);
- Yang et al. 2025 (Vacuum, O2 in LaB6 hollow-cathode propellant);
- Conversano et al. 2022 (13,011 h, body);
- Drobny et al. 2024 (C12A7 endurance);
- Andreussi et al. 2022 (AETHER, LaB6 + air test);
- Tisaev et al. 2023 (AMPCAT coupled to a cylindrical Hall thruster, JAP);
- Plasma Sci. Technol. 2022 (C12A7 degradation);
- Lev et al. 2019 (hollow-cathode review).

## 9. Sources read (sha256 of the exact file is in the JSON)

- Goebel & Katz 2008, *Fundamentals of Electric Propulsion*, Ch. 6 "Hollow Cathodes" (JPL DESCANSO chapter PDF).
- Tisaev et al., Acta Astronautica 214 (2024) 722–736, doi:10.1016/j.actaastro.2023.11.028 (CC BY; Sant'Anna IRIS copy).
- Sarver-Verhey, NASA/CR-97-206231 (IEPC-97-168) and NASA/CR-1998-208678 (AIAA-98-3482), NTRS.
- Herman, Soulas, Patterson, NASA/TM-2009-215838 (IEPC-2009-154), NTRS.
- Mackey, Shastry, Soulas, NASA/TM-2017-219713 (IEPC-2017-304), NTRS.
- Joussot, Grimaud, Mazouffre, Vacuum 146 (2017) 52–62, doi:10.1016/j.vacuum.2017.09.021 (HAL hal-03546669).
- Zschätzsch et al., IEPC-2022-102; Reitemeyer et al., IEPC-2019-A-604.
- Rand, PhD dissertation, Colorado State University, 2014.
- Becke et al., J. Electr. Propuls. 5:17 (2026), doi:10.1007/s44205-026-00192-y (CC BY; Zenodo 21787452).
- Watanabe et al., IEPC-2015-194; Nishiyama et al., IEPC-2009-021; Cifali et al., IEPC-2011-224.
- Brabston et al., IEPC-2024-297 (cathode description only).
- Schwertheim et al., IEPC-2025-378 / Research Square rs-9039885 v1, doi:10.21203/rs.3.rs-9039885/v1 (CC BY, preprint).
- Bibliographic records only: Conversano et al. 2022 (title), Becatti et al. 2021 (OSTI 1660475, title).
- Repository audit record: Marchioni 2020 thesis via
  `hallthruster_bridge/identification/echt_n2/echt_n2_evidence_audit_v1.json`.

**Access notes.** Pages that returned a paywall, login redirect, bot challenge or human-verification page were not
bypassed and are recorded as not retrieved: ScienceDirect, AIP, AIAA, SSRN, ADS, the AETHER project site, a Fraunhofer
repository and a DTIC report. No author or lab was contacted. LXCat was not used. Source PDFs are not redistributed.
