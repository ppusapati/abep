# RF ionization / pre-ionization source evidence audit (N₂, O, O₂, air), v1

Status: evidence audit, 2026-09-26. Non-gating. Lane "RF". Files in this directory:

| file | content |
|---|---|
| `rf_evidence_matrix.json` | 93 entries from 18 accessed sources: one quantity per entry, each with source and access label, evidence class and level, conditions and ABEP regime match |
| `rf_evidence_matrix.schema.json` | JSON Schema (draft 2020-12) for the matrix |
| `derive_rf_evidence.py` | the only producer of the 10 derived numbers (unit conversions, ratios, loose bounds). It is deterministic and reads `abep_sim/constants.py` by path |
| `tests/test_rf_source_evidence.py` | schema validation of every entry. Every numeric entry must have a source, an evidence class and an access label. Derived values must reproduce, and scope guards must hold |

Reproduce: `python docs/evidence/rf_source/derive_rf_evidence.py` (prints `OK`) and
`python -m pytest -q tests/test_rf_source_evidence.py`.

## 0. Scope: what this audit is and is not

**What it covers.** The audit looks at the open, published evidence on RF plasma sources on N₂, O₂, O and air. It covers
inductively coupled (ICP) sources, helicon or other B-assisted inductive sources, and the capacitive E-mode of ICPs. Each
source is considered as a pre-ionizer or ionization stage ahead of a Hall discharge, or as RF-based ABEP heritage. The
audit also lists what the literature does not settle, and states which ABEP-side densities are still TBD.

**What it does not do.** It builds no model, draws no architecture conclusion and admits no transport. **It makes no
statement that RF pre-ionization is or is not worth its power.** That question is decided later, on a common bus-power
boundary that includes RF generator, matching, antenna, magnet and thermal losses on the same footing as the Hall
discharge. The audit takes no position on the mechanism-level note in CLAUDE.md "Superseded / withdrawn" ("RF/helicon
pre-ionisers add nothing"). It neither supports nor withdraws that note.

**What it leaves untouched.** It touches none of the following: the P5-N₂ v1 result (permanent), the pre-registration,
the N₂/N chemistry set, the rate-validity limits, or any simulator prior. ECR/microwave sources are outside this lane.

## 1. Method and evidence conventions

- **Sources.** The audit used only published or openly accessible copies: arXiv, institutional repositories, IEPC
  proceedings, NASA NTRS, Europe PMC and open-access journals. It did not use LXCat and did not contact any person or
  lab. When a publisher page returned HTTP 403 or a bot challenge, the audit did not work around it and lists the source
  in section 8 instead. An abstract-only source is labelled `abstract_only`, and no number is taken from it.
- **Values** are preserved as reported, in the reported units. `conditions` are converted to SI by unit conversion only.
  No figure was digitized in v1. Where a quantity exists only in a figure, the entry says so.
- **evidence_class** is the docs/EVIDENCE.md quantity type:
  - *measured*: as reported by the experimenters, including setpoints, hardware specifications and observed events.
  - *inferred*: a ratio, bound or judgement computed from reported quantities. This includes all of our own arithmetic.
  - *model-derived*: a simulation output.
  - *assumed*: a model input or a design claim without validating evidence.
  - `null`: allowed only for `tbd` entries, where the source explicitly leaves the quantity unmeasured.
- **evidence_level** follows the EVIDENCE.md hierarchy, applied to the question "RF ionization stage for an ABEP Hall
  system":
  - 3: primary experimental report.
  - 4: evaluated data.
  - 5: secondary or summary claim whose primary data can't be inspected.
  - 6: model or correlation used outside its validated domain, for example Xe-fitted closures reused for air.
  - 7: bare assumption.
  Hardware and gas dissimilarity is carried in `applicability_to_abep`, not in the level.
- **regime_match** can't be `yes` for any entry yet, because the ABEP ionizer-inlet state is TBD (section 5). The test
  enforces this rule.

## 2. Evidence statements (what the accessed sources show, with entry IDs)

1. **No accessed open source measures an RF ionization stage feeding a Hall discharge on N₂, O₂ or air.** None reports
   ion production, ionization fraction or power transfer for that configuration. The only such experiment this audit
   identified is the Michigan helicon-Hall thruster on N₂ (Shabshelowitz, Gallimore, Peterson, J. Propul. Power,
   doi:10.2514/1.B35041). The audit could not read it (section 8). docs/HISTORY.md (line 81) cites it for the RF
   pre-ioniser prior. This lane could not verify that attribution.
2. **The SITAEL/ESA RAM-EP ground test was not RF-based, according to the accessed open sources.** It was a double-stage
   Hall thruster: the first stage ionizes and the second accelerates. The ionization stage is modelled with a DC voltage
   V_io plus magnet power (RF-SITA19-01, RF-ESA18-01). It is two-stage Hall heritage (thrust 6 ± 1 mN against 26 ± 1 mN
   of drag with a 4.7 mg/s N₂/O₂ flow source, RF-SITA19-02), not RF pre-ionizer evidence.
3. **Measured RF operation on air, N₂ or O₂ exists, but it is far from a characterized pre-ionizer:**
   - **IRS IPG6-S.** Operated at about 4 MHz, 0.5–3.5 kW active power, 0.2–120 mg/s and ≥ 26 Pa facility background
     (RF-IPG6S-01/02/07). Calorimetric "coupling efficiency" reached at most about 0.30 on O₂ and about 0.25 on air
     (RF-IPG6S-03/04). Ionization degree was not measured (RF-IPG6S-08). The supply tripped on reflected power at some
     operating points (RF-IPG6S-06).
   - **IPG6-S with an electromagnet.** About 5 mT triggered ignition in most cases (RF-IAC18-01). 18.2 mT raised the coil
     power on N₂ to 2.8 kW, "with high reflection" (RF-IAC18-02). 27.1 mT raised it on O₂ from 0.5 to 3.7 kW
     (RF-IAC18-03). Injector pressure was < 15 Pa (RF-IAC18-06). At the lowest flows the source did not ignite without
     the field (RF-IAC18-05).
   - **IRS IPT.** A 40.68 MHz birdcage antenna with a 70 mT solenoid (RF-IPT20-01/03). The measured no-plasma
     S11 = −6.0 dB, which means |Γ|² ≈ 0.25 (derived, RF-IPT20-D1). First ignition on N₂ was reported with no numbers
     (RF-IRS20-01/02).
   - **NewOrbit RF gridded ion engine and RF cathode on 50:50 N₂/O₂** (the most complete open air dataset accessed):
     - The RF generator is 92 % efficient bus-to-RF (nominal; RF-NO25-01).
     - The engine used 62–160 W of RFG input power to hold 100–300 mA of beam current at 6–14 sccm (RF-NO25-02/09).
       Those ranges give a loose bound of 207–1600 W per beam ampere (derived, RF-NO25-D1). The full air mapping covered
       5.8–14 sccm, which the source gives as 0.129–0.312 mg/s.
     - The RF cathode delivered 450 mA at 90 W, or 200 W/A (RF-NO25-03, RF-NO25-D2).
     - At low flow the RF generator had to be retuned to sustain the plasma (RF-NO25-04).
   - **TransMIT RIT experience on O₂, N₂ and air.** Available only in summarized form (RF-TMIT24-01…05).
4. **Unmagnetized air-like ICP physics.** These data come from an 80/20 N₂/O₂ mixture at 10–35 Pa and 13.56 MHz:
   - The E→H transition sits at about 200 W at 10 Pa and about 600 W at 35 Pa (RF-SCHU24-01/02).
   - n_e is above 3×10¹⁶ m⁻³ at 800 W and 10 Pa (RF-SCHU24-03), which gives an ionization fraction of about 1–4×10⁻⁵
     (derived, RF-SCHU24-D2).
   - The gas heats to about 1000 K in H-mode (RF-SCHU24-04).
   - NO forms in the discharge, and its density depends on the mode (RF-SCHU24-06).
   - Reflected power stays below 1 % with automatic matching (RF-SCHU24-05). Losses in the matchbox and coil are not
     separated from plasma power. The argon abstract RF-DALT08-01 shows why that matters: it suggests the apparent E-H
     hysteresis there came from ignoring power loss, primarily in the matching system.
5. **Power accounting is not comparable across sources.** Each source uses its own definition:

   | definition | value | gas | entry |
   |---|---|---|---|
   | calorimetric plume power / supply active power | ≤ 0.30 | O₂ | RF-IPG6S-03 |
   | calorimetric plume power / supply active power | ≤ 0.25 | air | RF-IPG6S-04 |
   | antenna R_p / R_total (excludes the generator) | ≈ 0.9 | Ar | RF-TAKA22-01 |
   | DC input to forwarded RF (generator + cable), low flow | 0.60–0.70 | Xe | RF-VOLK18-01/D1 |
   | bus to RF, nominal | 0.92 | air GIE | RF-NO25-01 |
   | assumed constant in a model | 0.8 | — | RF-ANDR24-01 |

   None of these is a measured bus-to-plasma-absorbed efficiency on air at ABEP flow. Two measurement problems add to
   this. A VI probe at the coil is limited by phase accuracy (RF-BELL22-01). The generator loses efficiency as the load
   resistance falls at low flow (RF-VOLK18-02), and a Class-E generator is nominal at one load impedance only
   (RF-BELL22-02).
6. **Magnetic field.** A field helps ignition, lowers reflection and raises absorbed power on N₂ and O₂ (RF-IAC18-08).
   No accessed source reports magnet power for an air RF stage.
   - The best-reported magnetic-nozzle RF thruster excludes its solenoid power (RF-TAKA22-04).
   - A third-party estimate puts that solenoid power at ≥ 1 kW (RF-TMIT24-03).
   - SITAEL's system model says ionization-stage magnet power "may be comparable to the discharge power"
     (RF-SITA19-03).
7. **Atomic-oxygen and wall interaction.** The accessed evidence is:
   - claims, such as "electrodeless, so erosion is eliminated" (RF-IPG6S-10, assumed; the quartz tube itself faces the
     plasma);
   - review judgements (RF-DUPP26-01);
   - second-hand RIT grid experience, where O₂ erodes the accelerator grid within 10 h and ≥ 60,000 h is claimed after a
     material change (RF-TMIT24-01/02; not inspectable);
   - a design rationale for RF cathodes (RF-NO25-06);
   - a model wall-recombination input, γ_O = 0.17 on BN (RF-ZHOU24-13);
   - LEO polymer erosion data, e.g. Kapton H 3.0×10⁻²⁴ cm³/atom at 4.5 eV (RF-DEGR19-01), which apply to insulation
     outside the discharge only.

   **No accessed source measures erosion, sputtering or contamination of the dielectric tube, antenna or Faraday shield
   under an air plasma.**
8. **Thermal loads and mass:**
   - IPG6-S: most of the power goes to cooling water, unquantified (RF-IPG6S-09).
   - IPT: the lab solenoid runs ≥ 30 min at 15 A (RF-IPT20-04).
   - NewOrbit: ohmic heating is a design driver (RF-NO25-08).
   - Gas heating reaches about 1000 K in H-mode (RF-SCHU24-04).
   - **No accessed source states the mass of RF-stage hardware** (RF-NO25-07).
9. **Model-only numbers rest on transferred closures (level 6):**
   - Zhou et al. 2024 reuse Xe-fitted anomalous transport for air (RF-ZHOU24-14). At 1 mg/s their model needs about
     1400 W absorbed on N₂ (700 W on O) for η_u ≈ 75 % (RF-ZHOU24-03/04). On N₂, 51–69 % of the absorbed power goes into
     inelastic collisions at 1.5–2 kW (RF-ZHOU24-06/08). The model operating points correspond to 435 and 580 eV of
     absorbed energy per injected N₂ molecule, and 249 eV per injected O atom (derived, RF-ZHOU24-D1…D3). These are
     plasma-absorbed figures, before any RF-chain loss.
   - Andrews et al. 2024 take two inputs from REGULUS work on xenon and iodine (RF-ANDR24-01/02). One is a constant
     η_RF = 0.8 "from previous measurements"; by title, the cited references are modelling papers. The other is a
     0.05 mg/s ignition minimum.
   - A 2026 review lists a thrust-to-power ratio for the IPT that no accessed primary source supports
     (RF-DUPP26-02). The matrix records it as a warning.

## 3. Source coverage table (per source × the quantities this lane was asked to record)

"—" means the source does not state the quantity. Entry IDs are in the matrix.

| source (access) | gas | pressure / density regime; mode limits | RF frequency | forward vs absorbed; coupling (incl. matching) | RFG DC→RF | ion cost / ionization fraction | B requirement | AO / wall interaction | thermal | RF hardware mass |
|---|---|---|---|---|---|---|---|---|---|---|
| Romano 2018, IPG6-S (open) | air, O₂ | ≥ 26 Pa background; reflected-power trips | ~4 MHz | calorimetric/active ≤ 0.25 (air), ≤ 0.30 (O₂) | — (tetrode oscillator) | ionization not measured | none used | claim only (assumed) | water-cooled; "cooling water absorbs most" | — |
| Romano IAC-18, IPG6-S + EM (open) | N₂, O₂, Ar | injector < 15 Pa; low-flow ignition needs B | 3.3 MHz | coil power up with B; reflection reduced (qualitative) | — | — | ~5 mT ignition; 18–27 mT raise power; HELIC: 20–60 mT | — | — | — |
| Romano 2020, IPT design (open) | (no plasma) | ≥ 27.12 MHz for low-pressure ignition (model rule) | 40.68 MHz | no-plasma S11 −6.0 dB (≈ 0.25 reflected); matching = protection | — | — | 70 mT solenoid | electrodeless by design | solenoid ≥ 30 min at 15 A | — |
| IRS news 2020, IPT ignition (open) | N₂ | — | — | "very good" (unquantified) | — | — | — | — | — | — |
| Zhou 2024, HYPHEN model (open) | N₂, O, O₂ | — (power deposition prescribed) | — | P_a only (plasma-absorbed) | — | η_u, P_inel/P_a (model) | 1200 G (model input) | γ_O 0.17, γ_N 0.07 (inputs) | — | — |
| Schücke 2024, N₂/O₂ ICP (open) | 80/20 N₂/O₂ | 10–35 Pa; E→H ~200–600 W | 13.56 MHz | reflected < 1 %; matchbox loss not separated | — | n_e > 3e16 m⁻³; n_e/n_n ~1–4e-5 (derived) | none | NO formation | T_g to ~1000 K | — |
| Takahashi 2022, MN RF thruster (open) | Ar | 28 mPa chamber | 13.56 MHz | η_p ≈ 0.9 (R method) | excluded | — | solenoid power not reported | — | antenna/matchbox water-cooled | — |
| TransMIT IEPC-2024-499 (open) | O₂, N₂, air | — | — | — | — | — | ≥ 1 kW magnet estimate (third party) | RIT grid O₂ erosion; ≥ 60,000 h claim | — | — |
| NewOrbit IEPC-2025-378 (open) | 50:50 N₂/O₂ | 0.13–0.31 mg/s; retuning at low flow | 1–5 MHz (thruster), 3–7 MHz (cathode) | — | 0.92 nominal | 62–160 W for 100–300 mA; cathode 200 W/A | none | RF cathode for oxidation tolerance; grid life TBD | ohmic heating a driver | not stated |
| Volkmar 2018, RIT power (open) | Xe | — | — | load R falls at low flow | 0.60–0.70 at low flow | — | — | — | loss map useful for thermal | — |
| Beller 2022, Class-E RFG (open) | Xe | — | 0.5–2 MHz | VI-probe phase limit | no absolute number; single-impedance design | — | — | — | — | — |
| Daltrini 2008 (abstract only) | Ar | E-H hysteresis traced to matching loss | — | plasma power vs applied power | — | — | — | — | — | — |
| de Groh & Banks 2019, NASA TM (open) | atomic O (LEO) | — | — | — | — | — | — | Kapton H 3.0e-24 cm³/atom | — | — |
| Ferrato 2019, SITAEL RAM-EP (open) | N₂/O₂ | — | not RF | — | — | — | magnet power "comparable" (model) | — | — | — |
| ESA 2018 release via phys.org (open) | Xe, N₂/O₂ | 200 km simulated | not RF | — | — | — | — | — | — | — |
| Andrews 2024, GSM (open) | air (model) | ignition ≥ 0.05 mg/s (assumed) | — | η_RF = 0.8 (assumed) | — | model | — | — | — | — |
| Duppada 2026, review (open) | air | — | — | — | — | — | — | helicon tube "Low" vulnerability (judgement) | — | — |
| Zheng 2023, ICP OES (abstract only) | N₂/O₂ | — | — | — | — | — | — | — | — | — |

## 4. What must be measured

These quantities are not settled for ABEP-relevant flow and density. Each item gives the reason.

1. **Ion production cost and ionization fraction of an RF stage on N₂, O, O₂ and air, at the ionizer-inlet density
   delivered by the Vyovrinda intake and compressor.**
   - IPG6-S did not measure ionization (RF-IPG6S-08). The IPT has no plasma data (RF-IRS20-02).
   - The only measured current-versus-power on air is through ion-extraction grids and includes RF generator loss. It
     gives only a loose bound (RF-NO25-D1).
   - The only measured n_e on an air-like ICP is at 10 Pa (RF-SCHU24-03/D2).
   - Model values rest on transferred closures (RF-ZHOU24-14).
2. **Minimum density or pressure for a sustained inductive (H) mode on air, and the extinction/hysteresis boundary, with
   and without an applied field, at the ICD pressure.**
   - Accessed data cover 10–35 Pa (RF-SCHU24-01/02) and a < 15 Pa injector with B-aided ignition (RF-IAC18-01/05/06).
   - Retuning was needed at low flow (RF-NO25-04). The only other figure is an ignition minimum transferred from other
     propellants (RF-ANDR24-02).
   - E-H thresholds quoted as generator power can include matching loss (argon evidence, RF-DALT08-01).
3. **Forward, reflected, matching-network, antenna and plasma-absorbed power on air across the ABEP flow range.**
   - Measured with one consistent method: the antenna-current / R_vac method (RF-TAKA22-01..03), or coil-side V/I with
     phase accuracy adequate for high-Q coils (RF-BELL22-01), cross-checked by calorimetry (RF-IPG6S-03).
   - Existing numbers use five different definitions (section 2, item 5).
4. **RF generator DC-to-RF efficiency over the load-impedance range that orbit-to-orbit flow and composition changes will
   produce.**
   - The 0.92 figure is nominal (RF-NO25-01).
   - Xe RIT data show a 30–40 % loss at low flow (RF-VOLK18-01).
   - Class-E designs are nominal at one impedance only (RF-BELL22-02).
5. **Magnet power, mass and heat for any B-assisted/helicon stage on air, and the interaction of its field with the Hall
   magnetic circuit.**
   - No accessed source reports magnet power for air (RF-TAKA22-04, RF-IPT20-03). There is only a third-party estimate
     (RF-TMIT24-03) and a model statement (RF-SITA19-03).
6. **Atomic-oxygen and plasma interaction with the plasma-facing dielectric (quartz, alumina, BN), the antenna, any
   Faraday shield, and matching-network parts.**
   - Needed: erosion and sputtering rate (including E-mode capacitive sheath bombardment), oxidation of metal parts, O
     wall recombination (O→O₂; RF-ZHOU24-13), and contamination carried downstream into the Hall channel (Si, B, metals).
   - Only claims, reviews and non-inspectable summaries exist (RF-IPG6S-10, RF-DUPP26-01, RF-TMIT24-01/02).
     Polymer yields at 4.5 eV (RF-DEGR19-01) do not describe sheath conditions.
7. **Heat split between coil, dielectric tube, matching network and generator for a radiatively or conductively cooled
   flight stage.**
   - Lab sources are water-cooled or short-duty (RF-IPG6S-09, RF-IPT20-04, RF-TAKA22-01), and gas heating reaches about
     1000 K (RF-SCHU24-04).
8. **Mass of RF hardware (generator, matching network, antenna, magnet, harness).** No accessed source states it
   (RF-NO25-07).
9. **Transport efficiency of pre-ionized plasma from the RF stage into the Hall channel.**
   - Needed: the interstage loss, and the ion charge and species mix handed over (N₂⁺, N⁺, O⁺, O₂⁺, NO⁺).
   - No accessed source measures either. NewOrbit's γ_ATM = 0.864 hints at monatomic ions but cannot separate them from
     divergence (RF-NO25-05). NO is produced in N₂/O₂ ICPs (RF-SCHU24-06). The helicon-Hall N₂ paper was not accessible
     (section 8).
10. **RF interference with the Hall discharge and its oscillations (EMC).** No accessed data exist. Beller 2022 treats
    RFG emissions only (RF-BELL22-02).
11. **Capacitively coupled (CCP) ionization stages on air.** No accessed source specific to CCP was found. The capacitive
    regime appears only as the E-mode of ICPs (RF-SCHU24-01/02).

## 5. Regime-match table: ABEP ionizer-inlet state (all TBD from the upstream ICD)

The ABEP-side values come from the upstream interface control document for the atmospheric path: intake → filter →
compressor → atmospheric gas chamber → valve → ionization/discharge (CLAUDE.md scope). **None is defined yet, so none is
invented here.** The frozen NRLMSIS dataset (`abep_sim/data/atmosphere_msis21_v1.*`) gives the *ambient* state at
180–230 km (RFP envelope). The ionizer-inlet state also depends on the intake and compressor, so it is not given here.

| quantity at the RF-stage inlet | ABEP value | status | range covered by the accessed literature (entry IDs) |
|---|---|---|---|
| neutral number density, total and per species (N₂, O, O₂) | TBD | needs ICD | 2.4–8.5×10²¹ m⁻³ (10–35 Pa at 300 K, derived; RF-SCHU24-D1); IPG6-S injector < 15 Pa (RF-IAC18-06); MN-RF chamber 28 mPa, Ar (RF-TAKA22-01) |
| static pressure | TBD | needs ICD | 28 mPa (Ar) … 35 Pa (N₂/O₂); IPG6-S background ≥ 26 Pa (RF-IPG6S-07) |
| gas temperature / accommodation after intake and compressor | TBD | needs ICD | 300–1000 K inside an H-mode ICP (RF-SCHU24-04) |
| mass flow into the RF stage | TBD | needs ICD | 0.0178 mg/s (RF cathode, RF-NO25-03) · 0.13–0.31 mg/s (RF-NO25-02) · 0.12–0.58 mg/s (RF-TMIT24-05) · 1 mg/s (model, RF-ZHOU24-01) · 1.29–4.36 mg/s (RF-IAC18-02/03) · 0.2–120 mg/s (RF-IPG6S-01) |
| composition: O vs O₂ after intake-wall recombination, N₂/O ratio | TBD | needs ICD | O₂ used as an O surrogate (IPG6-S); 50:50 N₂/O₂ by volume (NewOrbit); 80/20 N₂/O₂ (Schücke); N₂, O, O₂ separately (model) |
| flow and composition variability around the orbit and over the solar cycle | TBD | needs ICD and mission profile | matching and generator sensitivity to load (RF-VOLK18-02, RF-BELL22-02, RF-IPG6S-06) |
| downstream (Hall-anode-side) pressure and back-flow | TBD | needs ICD and Hall design | — |
| stray magnetic field from the Hall circuit at the RF stage | TBD | needs the Vyovrinda Hall design | fields of 5–70 mT used in RF sources (RF-IAC18-01, RF-IPT20-03) |
| power available to the RF stage | TBD | common bus-power boundary (system level) | 60–250 W (RF-NO25-01) … 0.5–3.7 kW (RF-IPG6S-02, RF-IAC18-03); RFP whole-system limit < 1.5 kW |

Consequently every matrix entry is `partial`, `no` or `TBD`. The test rejects `yes` until the ICD exists.

## 6. Simulator priors this audit bears on (read-only cross-reference)

These priors are **not modified** by this lane. Changing any of them is a model change under CLAUDE.md rules 1–2, and
that is the owner's call. The table records whether an accessed source supports each prior *as defined in the code*.

| prior (file:line) | value | cited source in code | accessed evidence on a matching definition |
|---|---|---|---|
| `archengine.py:116` Ionizer `rf_icp` (p_min_Pa, wall_factor, dc_eff, mass_kg) | 5e-2 Pa, 0.5, 0.8, 2.5 kg | none ("13.56 MHz inductive") | p_min: none at ABEP density (§4 item 2). dc_eff: definitions differ (§2 item 5). Mass: none (RF-NO25-07) |
| `archengine.py:117` Ionizer `helicon` | 3e-2 Pa, 0.3, 0.75, 3.0 kg | none ("helicon with axial B") | as above. Magnet power: none for air (§4 item 5) |
| `plasma_devices.py:42–54` `RFSource` (f, eta_dc_rf, R_coil, p_min, k_plasma_R) | 13.56 MHz, 0.80, 0.3 Ω, 5e-2 Pa, 6e-10 | "literature-class" (no citation) | R_vac 0.56 Ω for one Ar antenna circuit (RF-TAKA22-03). No air R_p law found |
| `plasma_devices.py:60–65` `Interstage` (B_axial_T, etc.) | 0.02 T | none | no transport-efficiency measurement found (§4 item 9) |
| `thruster.py:90–91` `_stage1("rf")` (p_min, P_fixed, P/ṁ, source_eff, η_u boost/cap, mass) | 5e-2 Pa, 50 W, 70 W per mg/s, 0.75, 0.25/0.60, 2.5 kg | module docstring: "Michigan Helicon-Hall (RF added: eta_u up slightly, T/P down)" | primary not accessible to this lane (§8) |
| `thruster.py:38` `Stage1.transport_eff` | 1.0 | none | none (§4 item 9) |
| docs/HISTORY.md:81 "RF pre-ioniser: Michigan Helicon-Hall (Shabshelowitz 2013)" | — | attribution | not verifiable from accessed sources (§8) |

## 7. Derived numbers (produced only by `derive_rf_evidence.py`)

| entry | function | inputs (from entries) | value |
|---|---|---|---|
| RF-IPT20-D1 | 10^(S11/10) | −6.0 dB (RF-IPT20-06) | 0.2512 |
| RF-SCHU24-D1 | p/(k_B T) | 10–35 Pa, T = 300 K assumed | 2.414e21 – 8.45e21 m⁻³ |
| RF-SCHU24-D2 | n_e/(p/k_B T) | n_e 3e16 (lower bound), 10 Pa, T 300–1000 K | 1.243e-5 – 4.142e-5 |
| RF-TAKA22-D1 | (R_tot − R_vac)/R_tot | 4.5–6 Ω, 0.56 Ω | 0.8756 – 0.9067 |
| RF-NO25-D1 | P/I corner bound | 62–160 W, 100–300 mA | 206.7 – 1600 W/A |
| RF-NO25-D2 | P/I | 90 W, 450 mA | 200 W/A |
| RF-VOLK18-D1 | 1 − loss | 0.30–0.40 | 0.60 – 0.70 |
| RF-ZHOU24-D1/D2/D3 | P_a/(ṁ/m)/e | 1500 or 2000 W, 1 mg/s; masses from `abep_sim/constants.py` (28/16 u) | 435.3, 580.4 eV per N₂; 248.7 eV per O |

Every numeric input traces to a number in the cited entries, or is declared under `assumed_inputs` with a reason. Unit
prefixes are allowed. The script checks this, and so does the test.

## 8. Identified but not accessed, or excluded (no numbers taken)

| source | reason |
|---|---|
| Shabshelowitz A., Gallimore A.D., Peterson P.Y., "Performance of a Helicon Hall Thruster Operating with Xenon, Argon, and Nitrogen", J. Propul. Power (2014), doi:10.2514/1.B35041 | The green open-access copy (Deep Blue hdl 2027.42/140449) sits behind a bot challenge. arc.aiaa.org returned HTTP 403. The Semantic Scholar metadata has no abstract. Not read. This is the key RF-stage-ahead-of-Hall experiment on N₂ and must be read before any quantitative use |
| Shabshelowitz A., PhD dissertation, University of Michigan (2013), "Study of RF Plasma Technology Applied to Air-Breathing Electric Propulsion" | Deep Blue bot challenge. Not read |
| Shabshelowitz A., Gallimore A.D., "Performance and probe measurements of a radio-frequency plasma thruster", J. Propul. Power 29 (2013) 919, doi:10.2514/1.B34720 | Primary not accessed. Only its re-tabulation in Takahashi 2022 is used (RF-TAKA22-05) |
| Zheng P. et al., "An atmosphere-breathing propulsion system using inductively coupled plasma source", Chinese J. Aeronautics (2023), doi:10.1016/j.cja.2023.03.003 (CC BY-NC-ND per Crossref) | Publisher host returned HTTP 403. Not read |
| Zheng P. et al., "Simulation investigation of inductively coupled plasma generator for ABEP", Acta Astronautica (2021), doi:10.1016/j.actaastro.2021.06.044 | Paywalled. Not read |
| Andreussi T., Ferrato E., Giannetti V., "A review of air-breathing electric propulsion: from mission studies to technology verification", J. Electr. Propuls. 1 (2022) 31, doi:10.1007/s44205-022-00024-9 | Open access, but the PDF endpoint served a JavaScript client challenge and only a lossy page summary was available. No numbers taken. It cites Cifali et al. for RIT-10 on N₂/O₂ (primary not accessed; verify) |
| Raitses, Ussenov (author surnames as listed by Crossref), "Characterization of Inductively Coupled RF Plasma Source Operating With Molecular Gases for Electric Propulsion", AIAA SciTech 2026, doi:10.2514/6.2026-2815 | Metadata only (no abstract). Not read |
| MDPI Aerospace 10 (2023) papers on atmosphere-breathing cathode-less thrusters (articles 100 and 389) | The host returned "Access Denied". Not read |
| esa.int RAM-EP press release | HTTP 403. The phys.org reprint was used instead (RF-ESA18-01) |
| Romano F., PhD thesis (University of Stuttgart) | Not located in the time available |
| ECR/microwave ionization stages (e.g. JAXA ABIE, listed in RF-SITA19-01's source Table 1) | Outside this lane's scope |

## 9. Accessed sources (18) and access labels

| # | source | doi_or_url | access |
|---|---|---|---|
| 1 | Romano et al., Acta Astronautica 147 (2018) 114–126 (read via arXiv:2103.02328) | https://doi.org/10.1016/j.actaastro.2018.03.031 | open |
| 2 | Romano et al., IAC-18.C4.6.4x46387 (accepted manuscript) | https://discovery.ucl.ac.uk/id/eprint/10118318/1/2018_Romano_et_al._Advances_on_the_Inductive_Plasma_Thruster_Design_for_an_Atmosphere_Breathing_EP_System.pdf | open |
| 3 | Romano et al., Acta Astronautica 176 (2020) 476–483 (read via arXiv:2007.06397) | https://doi.org/10.1016/j.actaastro.2020.07.008 | open |
| 4 | IRS news, IPT first ignition, 9 Apr 2020 | https://www.irs.uni-stuttgart.de/en/institute/news/A-breakthrough-First-Ignition-of-the-Helicon-based-Radio-Frequency-Inductive-Plasma-Thruster-IPT/ | open |
| 5 | Zhou, Taccogna, Fajardo, Ahedo, Propulsion and Power Research 13(4) (2024) 459–474 (read via arXiv:2407.19322) | https://doi.org/10.1016/j.jppr.2024.10.001 | open |
| 6 | Schücke et al., arXiv:2407.04441 (2024) | https://doi.org/10.48550/arXiv.2407.04441 | open |
| 7 | Takahashi, Sci. Rep. 12 (2022) 18618 (Europe PMC PMC9649674) | https://doi.org/10.1038/s41598-022-22789-7 | open |
| 8 | Smirnova, Mingo, Smirnov, Pessina, IEPC-2024-499 | https://iqm.transmit.de/images/iqm/pdf/iepc-2024-499_radio_frequency_atmosphere_breathing_ion_engine_development.pdf | open |
| 9 | Schwertheim et al., IEPC-2025-378 / Research Square preprint (CC BY 4.0) | https://doi.org/10.21203/rs.3.rs-9039885/v1 | open |
| 10 | Volkmar, Geile, Hannemann, J. Propul. Power 34(4) (2018) 1061–1069 (DLR preprint) | https://doi.org/10.2514/1.B36868 | open |
| 11 | Beller et al., J. Electr. Propuls. 1 (2022) 8 | https://doi.org/10.1007/s44205-022-00008-9 | open |
| 12 | Daltrini et al., Appl. Phys. Lett. 92 (2008) 061504 | https://doi.org/10.1063/1.2844885 | abstract_only |
| 13 | de Groh & Banks, NASA/TM-2019-219982 | https://ntrs.nasa.gov/api/citations/20190025445/downloads/20190025445.pdf | open |
| 14 | Ferrato et al., IEPC-2019-886 | https://electricrocket.org/2019/886.pdf | open |
| 15 | ESA press release 6 Mar 2018, via phys.org reprint | https://phys.org/news/2018-03-world-first-air-breathing-electric-thruster.html | open |
| 16 | Andrews et al., Acta Astronautica 225 (2024) 833–844 (UniBo accepted manuscript) | https://doi.org/10.1016/j.actaastro.2024.09.041 | open |
| 17 | Duppada et al., npj Microgravity 12 (2026) 47 (Europe PMC PMC13230546) | https://doi.org/10.1038/s41526-026-00573-5 | open |
| 18 | Zheng, Wu, Zhang, Zhao, Phys. Plasmas 30 (2023) 023503 | https://doi.org/10.1063/5.0130530 | abstract_only |

Licences: CC BY-NC-ND manuscripts (sources 1, 3 and 5) are cited for numbers only and not redistributed. No source text
or figure is copied into the repository beyond short quotations in the matrix.
