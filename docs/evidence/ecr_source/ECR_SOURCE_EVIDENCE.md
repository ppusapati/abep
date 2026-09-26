# ECR ionization / pre-ionization sources: evidence audit (N₂, O, O₂, air, Xe)

**Lane:** ECR source evidence audit · **Date:** 2026-09-26 · **Status:** evidence only.

This audit does not implement a model or reach an architecture conclusion. It does not rank ECR against RF or any
other ionization technology, and it does not change any simulator parameter. The ABEP operating conditions
(chamber neutral density, pressure, composition, flow, power allocation) are **TBD — requires the upstream ICD**
(intake → filter → compressor → atmospheric gas chamber → valve, and the Xe chamber → valve path). They are never
filled in here.

| file | role |
|---|---|
| `ecr_evidence_matrix.json` | the matrix: 130 literature entries (`ECR-E###`) and 35 derived entries (`ECR-D###`), with sources, access mode, locators and leads that were not admitted |
| `ecr_evidence_matrix.schema.json` | JSON Schema (draft 2020-12) for the matrix |
| `build_ecr_evidence_matrix.py` | deterministic builder. Literature entries are transcribed by hand; derived entries are computed from CODATA 2022 and from the transcribed entries |
| `tests/test_ecr_source_evidence.py` | schema validation, source/class completeness, independent recomputation of every derived value, and cross-checks against the constants the sources state |

Reproduce with `python docs/evidence/ecr_source/build_ecr_evidence_matrix.py --check` and
`python -m pytest -q tests/test_ecr_source_evidence.py`.

## 1. Main findings (evidence statements only)

1. **Only xenon has flight heritage for ECR ion and neutralizer sources.** The JAXA μ10 flew on Hayabusa: 4.2 GHz TWT
   amplifiers, 32 W to each ion source and 8 W to each neutralizer, and 35,000 h·unit by August 2009 (ECR-E040,
   E041, E121). The μ20 passed a 5,000 h ground endurance test on Xe (ECR-E126). No air, N₂, O₂ or O endurance data
   were found in any accessed source (§4.8, ECR-E157).
2. **Thruster-scale ECR ion-source data on N₂ exist only as abstracts.** A 10 cm N₂ ECR gridded source extracted
   258 mA at 55 W "input microwave power", 10 sccm (ECR-E088). A 2 cm N₂ ECR ion source reports 596.2 W/A in
   experiment (ECR-E081). Neither abstract states the frequency or the power basis. **No O₂-only, atomic-O or
   N₂/O₂-mixture ion-source measurement was found.** The only ECR ion-beam data that include atomic oxygen are
   secondary: the JAXA ABIE gave 16 mA at 200 V on hyperthermal N₂ + AO beams, as summarized by a review (ECR-E097).
3. **Air-fed ECR evidence is from a cathode (electron source), not an ion source.** A 2.45 GHz ECR microwave
   cathode on 0.48 O₂ + 0.52 N₂ runs overdense (n_e/n_c = 18.53–49.83 from densities measured without an applied field; ECR-D009, D010).
   On xenon an applied ECR field raised the extracted current about fourfold, but on air at nominal density it
   **suppressed** the current (0.06 → 0.01 A). The field helped on air only at reduced neutral density (ECR-E104 to
   E106).
4. **Overdense operation is documented in several small ECR sources:** the μ10 neutralizer (> n_c at
   4.2 GHz, ECR-E013), the ONERA ECRA exit plane (≈ 1.343 × n_c, ECR-D012; source interior estimated at ≈ 13.43 × n_c, ECR-D014),
   the 5.8 GHz cavity cathode (2.396–23.96 × n_c, inferred, ECR-D013) and the air cathode above. The μ20 ion source was
   instead **designed** below cutoff (ECR-E019). The accessed sources name two mechanisms: near-antenna heating in a
   2–5 mm skin-depth region (ECR-E020), and high-field-side launch so that the wave meets the ECR before the R-cutoff
   (ECR-E021).
5. **Power bases are inconsistent across the literature, so W/A figures do not compare directly.** Reported powers
   are variously generator/forward, "transmitted" (forward − reflected at a coupler upstream of ≥ 2 dB of line loss),
   incident, net (Pi − Pr) or "input". Measured line transmission is 0.78–0.80 (ECR-D016), and ≤ 0.631 behind a ≥ 2 dB
   chain (ECR-D015). Measured coupling into the plasma is 0.90–0.99 at 30 W and 0.78–0.89 at 200 W (ECR-E030, E031).
6. **For 2.45–4.2 GHz microwave sources at 5–945 W, reported efficiencies span 0.3636 to 0.785:** 0.3636 for the Hayabusa TWT amplifier as a
   system (inferred, ECR-D017), ≈ 0.54 for a 945 W 2.45 GHz magnetron in free run (ECR-E046), > 0.70 for a 5 W
   2.45 GHz SSPA breadboard (ECR-E042), and 0.785 PAE for a 24 W GaN device (ECR-E045, device level only). None of
   these is a flight 2.45 GHz sub-kW unit characterized over temperature and life.
7. **Magnet temperature limits:** Sm₂Co₁₇ 350 °C and SmCo₅ 250 °C (manufacturer recommendation), NdFeB 80–230 °C
   depending on grade. The μ20 ran its NdFeB magnets at 135 °C against a 190 °C rating (ECR-E050, E051, E053, E057,
   E060, E061). The reversible Br temperature coefficient of NdFeB is 2.571–3.429 times that of Sm₂Co₁₇ (ECR-D034, from
   ECR-E055, E062), so the ECR surface drifts more with temperature (ECR-D031, D032). **No open source gives the magnet mass or
   main-field electromagnet power of a relevant ECR stage.**

## 2. Method, evidence classes and access

- **Sources:** only published or openly accessible documents; no contact with authors or labs; no LXCat. Sources
  behind paywalls or bot challenges were not bypassed. Where only the abstract could be read (through Crossref
  metadata), the entry is `access: abstract_only`. Anything cited from memory is marked "verify". Only one item is:
  the textbook form of the O-mode cutoff, which is also checked numerically against three source-stated values.
- **Evidence class** (docs/EVIDENCE.md quantity type): *measured*, *digitized* (none in this audit), *inferred*
  (ratios or estimates from reported values, by the source or by this audit), *reconstructed* (the source's own
  integration or correction model applied to measurements, e.g. probe-integrated plume current), *model-derived*
  (a formula or model), *assumed* (assumption, target or claim).
- **Evidence level** (docs/EVIDENCE.md hierarchy 1–7) is **not** assigned. "Same or closely similar hardware" cannot
  be judged until a Vyovrinda ECR design exists. The `source_kind` field instead records whether each value is
  primary, a secondary citation, a review, a datasheet, an abstract or a preprint.
- **Derived numbers** (`ECR-D###`) are all produced by `build_ecr_evidence_matrix.py` and stored to 4 significant
  figures. The test recomputes each one independently.
- **Unit identity:** 1 W/A ≡ 1 eV per singly charged ion (ECR-D025). Every "ion production cost" below is also an
  energy per ion under that identity. Multiply charged or molecular-fragment ions change the conversion.
- **Regime match** (`applicability_to_abep.regime_match`):
  - *yes* is used only for unit identities.
  - *partial* means at least one of gas, power class, frequency class or device type matches the RFP envelope.
  - *no* means a clear mismatch.
  - *TBD* means the answer depends on ABEP quantities that are not fixed yet: the ICD chamber conditions, the ECR
    frequency, or the magnetic-circuit design.

## 3. Resonance field and cutoff density (model-derived, recomputed in the test)

Formulas: fundamental ECR, 2πf = eB/mₑ → **B_res = 2πf·mₑ/e**. Cold O-mode cutoff, ω = ω_pe →
**n_c = ε₀·mₑ·(2πf)²/e²**. The f_ce form is written in Jarrige et al. 2013, Eq. (1), and in Tisaev et al. 2023,
Eq. (2). The n_c form is the textbook relation (verify); it reproduces all three cutoffs that the sources state.
Constants are CODATA 2022 (NIST).

| f | B_res (this audit) | B_res as stated in sources | n_c (this audit) | n_c as stated in sources |
|---|---|---|---|---|
| 2.45 GHz | 0.08752 T (ECR-D001) | 875 G / 87.5 mT (ECR-E001, E002) | 7.446e16 m⁻³ (ECR-D005) | 7.4e16 m⁻³ (ECR-E004) |
| 4.2 GHz | 0.1500 T (ECR-D002) | 150 mT (μ10 neutralizer, ECR-E003) | 2.188e17 m⁻³ (ECR-D006) | 2.2e17 m⁻³ (ECR-E005) |
| 4.25 GHz | 0.1518 T (ECR-D003) | n/a | 2.241e17 m⁻³ (ECR-D007) | n/a |
| 5.8 GHz | 0.2072 T (ECR-D004) | n/a | 4.173e17 m⁻³ (ECR-D008) | 4e17 m⁻³ (ECR-E006) |

A lower frequency lowers both B_res and n_c (n_c ∝ f²). One accessed abstract reports a **MHz-range** ECR source
for ABEP (ECR-E144). Its frequency, and therefore its B_res and n_c, is **TBD — requires the full text** of
Šťastný et al. 2026.

## 4. Evidence by topic

### 4.1 Microwave coupling, frequency and antenna

- Frequencies in the evidence base:
  - 2.45 GHz: ONERA ECRA, the Kyushu 10 cm thruster and the AMPCAT air cathode.
  - 4.2 / 4.25–4.4 GHz: JAXA μ10 and μ20 (ECR-E040, E048).
  - 5.8 GHz: the Diamant cavity cathode.
  - MHz range: Šťastný 2026, from the abstract only.
  - The N₂ ion-source abstracts do not state a frequency (ECR-E081, E088).
- Coupling structures: coaxial antenna in the plasma (ONERA, AMPCAT, μ10 neutralizer), a tuned cavity with a sliding
  short (Diamant, ECR-E035), a radial waveguide feeding receiving antennas (Kyushu), and a birdcage resonator
  (Šťastný, abstract).
- Antenna and dielectric in plasma contact:
  - Mo L-antenna in a BN sleeve (ECR-E157).
  - BN coating tested after "impacts on antenna" were seen (ECR-E159).
  - Sapphire or fused-silica vacuum break; alumina was dropped over porosity concerns (ECR-E158).

### 4.2 Overdense operation

| device | gas | f | n_e | n_e/n_c | class | entries |
|---|---|---|---|---|---|---|
| AMPCAT air cathode, 40 V, **no applied B** | 0.48 O₂ + 0.52 N₂ | 2.45 GHz | 1.38e18 ± 0.04e18 m⁻³ | 18.53 | measured / model-derived ratio | ECR-E010, D009 |
| same, 80 V | same | 2.45 GHz | 3.71e18 ± 0.10e18 m⁻³ | 49.83 | measured / ratio | ECR-E011, D010 |
| same, Xe, 40 V | Xe | 2.45 GHz | 7.11e18 ± 0.98e18 m⁻³ | 95.49 | measured / ratio | ECR-E012, D011 |
| JAXA μ10 neutralizer | Xe | 4.2 GHz | "significantly larger than" 2.2e17 m⁻³ | > 1 | measured (secondary) | ECR-E013 |
| ONERA ECRA, source exit plane | Xe | 2.45 GHz | ≈ 1e17 m⁻³ | ≈ 1.343 | measured (secondary) / ratio | ECR-E014, D012 |
| ONERA ECRA, inside source | Xe | 2.45 GHz | ≈ 1e18 m⁻³ (estimate) | ≈ 13.43 | inferred / ratio | ECR-E015, D014 |
| Diamant 5.8 GHz cavity | Xe | 5.8 GHz | 1e18–1e19 m⁻³ (Te = 1 eV assumed) | 2.396–23.96 | inferred / ratio | ECR-E016, D013 |
| JAXA μ20 ion source | Xe | 4.25–4.4 GHz | "below cutoff" (design intent) | < 1 (intent) | assumed | ECR-E019 |

Caveat on the air row: the AMPCAT Langmuir-probe densities were taken on a diagnostic prototype with a straight λ/4
antenna and **no applied magnetic field**. They show that the air plasma is overdense, but the plasma is not
ECR-heated (ECR-E010). Mechanisms the sources name for overdense sources: heating confined to a 2–5 mm skin-depth
region around the antenna (ECR-E020), and high-field-side launch that reaches the ECR before the R-cutoff (ECR-E021).
**No accessed source quantifies how absorbed power degrades with n_e/n_c.**

### 4.3 Absorbed vs forward power

| power basis | evidence | entries |
|---|---|---|
| generator → device input (line loss) | Pin/P0 = 0.8, 0.8, 0.7778 at 30/60/90 W, coax, measured without plasma | ECR-E033, D016 |
| "transmitted" at an upstream coupler | ≥ 2 dB of chain loss downstream, so ≤ 0.631 of the reported power reaches the thruster | ECR-E032, D015 |
| reflected | < 1 W with a stub tuner; within 10 W uncertainty in a tuned cavity; "sufficiently small" without tuners (μ20) | ECR-E034, E035, E037 |
| coupling into plasma | 0.90–0.99 (30 W ECRA), 0.78–0.89 (200 W ECRA); expected to fall with size/power | ECR-E030, E031 |
| absorbed | 115 ± 10 W (tuned cavity) | ECR-E035 |
| net definition in use | εc = (Pi − Pr)/Ib | ECR-E075 |

These factors multiply any W/A figure derived from a reported power, so the ion-production costs in §4.6 carry
their power basis, and any ABEP W/A must state its own.

### 4.4 Microwave source DC-to-RF efficiency

| technology | f | output power | efficiency | class | entries |
|---|---|---|---|---|---|
| TWT amplifier as a system (Hayabusa; both outputs / DC in) | 4.2 GHz | 40 W RF from 110 W DC | 0.3636 | inferred | ECR-E040, E041, D017 |
| solid-state breadboard (TMI, MINOTOR), 48 V input | 2.45 GHz | 5 W | > 0.70 | measured | ECR-E042 (mass 100 g, ECR-E043) |
| GaN HEMT PA, single stage, device level | 2.45 GHz | 23.71 W CW | 0.785 (PAE) | measured | ECR-E045 |
| CW magnetron 2M219G, free run, filament excluded | 2.45 GHz | 945 W nominal | ≈ 0.54 | measured | ECR-E046 |
| CW industrial magnetron (regime *no*) | 915 MHz | 75 kW | > 0.90 (not yet calorimetric) | measured (indirect) | ECR-E047 |
| programme target | 2.45 GHz | n/a | > 0.80 | assumed | ECR-E044 |

Missing: system-level (bus to antenna) efficiency, including DC-DC conversion, driver, isolator/circulator and
thermal control; its temperature dependence; and its life. **TBD — requires measurement on the candidate flight
microwave chain.**

### 4.5 Magnets: temperature limits, mass, electromagnet power

| item | value | class | entries |
|---|---|---|---|
| Sm₂Co₁₇ (Recoma 26) max. recommended use temperature / Curie temperature | 350 °C / 825 °C | inferred (rating) / measured (nominal) | ECR-E053, E054 |
| SmCo₅ (Recoma 18) max. recommended use temperature / Curie temperature | 250 °C / 725 °C | inferred / measured | ECR-E057, E058 |
| NdFeB standard N grades / VH-AH grades | +80 °C / +230 °C | inferred (guideline) | ECR-E060, E061 |
| α(Br): Sm₂Co₁₇ / SmCo₅ / NdFeB | −0.035 / −0.045 / −0.120 to −0.090 %/°C | measured (nominal) | ECR-E055, E059, E062 |
| reversible Br change 20 → 100 °C: Sm₂Co₁₇ / NdFeB | −2.8 % / −9.6 to −7.2 % | model-derived (linear) | ECR-D031, D032 |
| μ20 NdFeB: rating vs operating temperature | 190 °C vs 135 °C (margin 55 °C) | inferred / measured | ECR-E050, E051, D033 |
| SmCo density (magnet mass = density × volume) | 8.3 g/cm³ | measured (nominal) | ECR-E056 |
| AMPCAT electromagnet: current for the 87.5 mT ECR layer | 2 A, 650 turns of 0.8 mm Cu (power not reported) | measured | ECR-E067 |
| ONERA steering coil pair: 14 G on axis | 5 W (text) vs 5.5 W (figure) | measured | ECR-E066 |

- Heritage magnet choices:
  - SmCo: μ10 ion source (two rings; Tsukizaki 2015), μ10 neutralizer (Tisaev 2023, citing JAXA work), μ20
    nominal configuration, and the Kyushu 10 cm thruster.
  - NdFeB: μ20 thrust-enhanced configuration (all rows except the innermost), ONERA coaxial source, Diamant cavity.
  - Electromagnet: AMPCAT.
- Corrosion guidance is terrestrial only. NdFeB should always be coated; SmCo can usually run uncoated (ECR-E063,
  E064). Behaviour under atomic oxygen is not addressed.
- **Gaps:**
  - Permanent-magnet **mass** for an ABEP ECR stage: TBD — requires a magnetic-circuit design (magnet volume and
    resonance-surface geometry).
  - Main-field **electromagnet power**: TBD — requires coil resistance at operating temperature. No accessed source
    reports it for an ECR main field.

### 4.6 Ion production cost and usable ion current

Every cost below is in W/A (≡ eV per singly charged ion) and carries its power basis.

| device | gas | f | power basis | P | current | cost | class | entries |
|---|---|---|---|---|---|---|---|---|
| JAXA μ20, 20 cm gridded | Xe, 10 sccm | 4.25–4.4 GHz | microwave (basis not stated) | 100 W | 0.500 A | 200.0 | inferred | ECR-E070, D018 |
| JAXA μ10 improved (lab) | Xe, 3.3 sccm | 4.25 GHz | "microwave input" | 34 W | 0.191–0.195 A (source inconsistent) | 174.4–178.0 | inferred | ECR-E079, D019 |
| JAXA μ10 (flight design) | Xe | 4.2 GHz | microwave | > 30 W | saturates at 0.150 A | n/a | measured | ECR-E072 |
| Kyushu 10 cm | Xe, 2.28 sccm | 2.45 GHz | incident (Pr not subtracted) | 32 W | 0.085 A | ≤ 376.5 | inferred | ECR-E077, D023 |
| 10 cm N₂ ECR gridded (abstract) | **N₂**, 10 sccm | not stated | "input microwave" | 55 W | 0.258 A | 213.2 | inferred | ECR-E088, D020 |
| 2 cm N₂ ECR ion source (abstract) | **N₂**, 0.8 ml/min | not stated | "input" | 8 W | n/a | 596.2 (exp.), 443.9 (source's model) | inferred / model-derived | ECR-E081, E083 |
| ONERA coaxial ECR, magnetic nozzle (2013) | Xe, 0.2 mg/s | 2.45 GHz | "transmitted" incl. ≥ 2 dB loss | 51 W | 0.0654 A plume ion current | 779.8 | inferred (on reconstructed current) | ECR-E091, D021 |
| JAXA ABIE (review summary) | **N₂ + atomic O** beams | not stated | not stated | not stated | 0.016 A at 200 V (space-charge limited) | TBD | measured (secondary) | ECR-E097 |

Out of gas scope and kept only for the power-basis comparison: Kyushu argon, 440 W/A on the net-power basis
(ECR-E075), and ONERA argon, 704.6 W/A (ECR-D022). In the 10 cm N₂ source the beam current over the flow-equivalent
current is 0.3596 (ECR-D030). That is a proxy, not a utilization, because N₂⁺ and N⁺ are not separated. It uses the
sccm reference state 0 °C / 101325 Pa (assumed, ECR-D028). In the 2 cm source the model and the experiment differ by
2–32 % (ECR-E087).

Cathode (electron-source) figures, which are not ion production costs:

- Diamant 5.8 GHz cavity: 10.3 A on Xe at 115 W absorbed (90 mA/W; ECR-E099). A magnet raises the current about
  threefold (ECR-E101). The cold-flow cavity pressure is 4–80 mTorr, i.e. 0.5333–10.67 Pa (ECR-E102, D035).
- μ10 neutralizer: 0.18 A at 8 W (ECR-E112).
- μ20 neutralizer: 0.5 A at 20 W, or 0.50 A at 15 W. The two sources conflict (ECR-E113, E114).
- Kamhawi cathode: 2.6 A at 98 W/A (ECR-E115).
- AMPCAT on air: 0.36 → 0.45 A at 48 W, 120 V, after relaxing the orifice field (ECR-E107).

### 4.7 Heritage

| heritage | key facts | entries |
|---|---|---|
| JAXA μ10 (Hayabusa, Hayabusa2) | 8 mN, 3000 s, 350 W rating. 4 units; 35,000 h·unit by Aug 2009; "39,600 h" total by 2015 (unit convention differs). IES thrust 4.5–25 mN at 250 W–1.1 kW. Hayabusa2 10 mN. IES dry mass 59 kg (system) | ECR-E120–E125 |
| JAXA μ20 | 500 mA at 100 W on Xe; utilization 0.667 → 0.824 with ion-machined grid; 5,000 h endurance | ECR-E070, E073, E126 |
| JAXA ECR neutralizers | μ10 0.18 A at 8 W (4.2 GHz); μ20 0.5 A | ECR-E112–E114 |
| ONERA ECRA (MINOTOR) | Xe only; about 16 % total efficiency at 30 W (2019); about 20 → 45 % over MINOTOR; best 12.5 % for ECR-PM-V1 (2017). Needs facility pressure < 1e-3 Pa. Te up to 40–60 eV. TRL 4 (self-assessed, 2019) | ECR-E127–E132 |
| ECR compatibility with oxygen (claim) | ECRA "a priori compatible with any propellant"; oxygen compatibility listed as a *potential* advantage. Not demonstrated in the accessed sources | ECR-E133, E134 |

### 4.8 Air-breathing ECR work in open sources

- **JAXA ABIE** (Nishiyama 2003 concept): ECR ion engine fed directly from the intake. The laboratory test with
  hyperthermal N₂ + atomic-O beams gave 16 mA / 0.13 mN, space-charge limited. Source: a review (secondary); the
  primary paper is closed (ECR-E097, E098).
- **Diamant 2009:** 5.8 GHz ECR cavity cathode, Xe/Ar only; N₂–O₂ "not attempted yet" (ECR-E140). The same paper
  *assumes* an ECR ion engine at ~1e18 m⁻³ neutral density, with thruster efficiency 0.25 and utilization 0.50
  "without justification" (ECR-E141, E146). It estimates that passive compression reaches ~1e3 against the ~1e5
  needed for 1e20 m⁻³ (ECR-E142).
- **Diamant 2010**, 2-stage ECR + cylindrical Hall (review summary): assumes compression ratio 500 → 0.01 Pa
  (ECR-E143).
- **AMPCAT** (air-breathing ECR microwave cathode), the fullest open data set on air:
  - Overdense on air (ECR-E010, E011).
  - ECR field suppresses the current at nominal density and helps at reduced density (ECR-E105, E106).
  - Coupled to a cylindrical Hall thruster running on Xe, the cathode ran stably on air (ECR-E116, abstract).
  - Continuous air operation and erosion are future work (ECR-E157).
- **Tan et al. 2023 / 2026:** N₂-fed 2 cm and 10 cm ECR ion sources (abstracts; ECR-E081 to E090). No O₂ or O data.
- **Šťastný et al. 2026:** ECR ignition sustained at pressures representative of post-intake VLEO conditions
  (~200 km) with a MHz-range birdcage resonator. Resonator heating limits the power. The abstract gives no numbers
  (ECR-E144, E173).
- Not admitted: a 2026 AST paper on an ECR-based atmosphere-breathing thruster (publisher 403; unverifiable
  numbers). See §8.

### 4.9 Material interactions with atomic oxygen

- **LEO ram-AO erosion yields** (MISSE 2, about 4 years on the ISS): pyrolytic graphite 4.15e-25 cm³/atom; Kapton H
  reference 3.0e-24 cm³/atom; fluence 8.43e21 atoms/cm² (ECR-E150 to E152). These apply to *directed ram AO in
  orbit*, **not** to the thermal O/O₂ and energetic O⁺ inside an ECR discharge chamber. Chamber-side rates are TBD.
- **Carbon parts in ECR ion sources:** μ10 carbon-carbon grids (ECR-E153). Carbon sputtered from the μ20 grids
  deposited on the chamber walls and had to be cleaned (ECR-E154). How that carbon behaves with oxygen in an air-fed
  source is TBD.
- **Oxygen and thermionic cathodes:** a LaB₆ hollow cathode running on Xe with 12 % air showed significant erosion
  (secondary, ECR-E155). That result is the stated reason for the electrodeless microwave cathodes. Flight μ10 also
  gives oxygen contamination as a reason for cathode-less ECR (ECR-E153).
- **Plasma-facing materials in the ECR sources:**
  - 304 stainless steel, chosen partly for oxidation resistance, with a Mo antenna in a BN sleeve (ECR-E157).
  - BN back plate (ECR-E160) and BN antenna coating (ECR-E159).
  - Sapphire or fused-silica window (ECR-E158).
- **No erosion rate under O/O⁺ was found for any of these materials in ECR conditions.**

### 4.10 Thermal loads

- Microwave line and component heating capped the transmitted power at 51 W on a lab ECR thruster (ECR-E170).
- Resonator heating limits power scaling of a MHz-range ECR ABEP source (abstract, ECR-E173).
- μ20 magnets ran at 135 °C (ECR-E051).
- The AMPCAT wall temperature is reported as about 373 K; the operating point is not stated, and the device was
  tested at 24–70 W input (ECR-E171, E033).
- ONERA used ≥ 1 h warm-up to reach a stationary regime (ECR-E172).
- Heat flux to the walls, window, antenna and magnets of an ABEP ECR stage: **TBD — requires a thermal model with a
  measured power partition**.

## 5. Regime match (ABEP column TBD from the upstream ICD)

| dimension | evidence range (entries) | ABEP value | status |
|---|---|---|---|
| gas composition | Xe (flight); N₂ (abstracts); 0.48 O₂ + 0.52 N₂ in a cathode; N₂ + AO beams (secondary) | TBD — requires ICD chamber composition (O/N₂/O₂ fractions after intake, filter and compressor) | O₂-only and atomic-O data for ion sources are missing |
| chamber neutral density / pressure | μ20 ≈ 0.01 Pa, i.e. 1.207e18–2.414e18 m⁻³ at an assumed 300–600 K (ECR-E071, D026). ONERA source 0.08–0.41 Pa modelled, 1.931e19–9.899e19 m⁻³ at 300 K (ECR-E096, D027). AMPCAT 1.0e21 m⁻³ modelled (ECR-E109). Diamant cavity 0.5333–10.67 Pa cold flow (ECR-E102, D035) | **TBD — requires ICD chamber pressure/density and gas temperature** | cannot be judged |
| electron density vs cutoff | ≈ 1.343 to 95.49 × n_c in small sources (ECR-D009–D014); μ20 designed below n_c (§4.2) | TBD — requires ABEP ECR frequency and target n_e | cannot be judged |
| frequency / resonance field | 2.45 GHz (0.08752 T) to 5.8 GHz (0.2072 T); MHz range (abstract) | TBD — not selected | cannot be judged |
| microwave power class | sources 5 W – 945 W (ECR-E042, E046); ECR devices 8 W – 200 W (ECR-E081, E031) | TBD — requires the power allocation within the RFP < 1.5 kW (repository summary of the RFP; not re-verified here) | partial |
| ion current needed | 0.016 A (N₂ + AO beams, secondary) to 0.500 A (Xe, μ20 nominal); N₂ 0.258 A (abstract) (ECR-E097, E070, E088) | TBD — follows from the thrust requirement (RFP 12–25 mN, repository summary) and the accelerator design | cannot be judged |
| life | Xe: 5,000 h ground (μ20); 35,000 h·unit flight (4 units). Air/N₂/O: none | TBD — RFP > 15,000 h firing (repository summary) | gap |
| facility background | ECRA needs < 1e-3 Pa; AMPCAT tests at 2.2–4.8e-2 Pa (ECR-E130, E110) | ground-test planning item | partial |

## 6. What must be measured

1. **Absorbed power at the source.** Forward, reflected and line-loss-corrected power at the source flange
   (calorimetric or de-embedded couplers), on N₂, O₂, a representative N₂/O₂/O mixture and Xe, at the ICD chamber
   pressures. Report W/A on a stated basis (DC bus, forward, absorbed).
2. **n_e and T_e in the ECR zone vs n_c at the chosen frequency** (curling/hairpin probe or interferometry, with the
   applied field on). This establishes under- or overdense operation and the coupling mode.
3. **Species-resolved ion production cost vs neutral density** (N₂⁺, N⁺, O⁺, O₂⁺, NO⁺; E×B or mass spectrometry),
   including an atomic-O source. Today only N₂ abstracts and one secondary AO + N₂ beam result exist.
4. **Ignition and sustainment minimum pressure** for each gas at ICD conditions. The only VLEO-representative
   report is an abstract without numbers.
5. **System-level DC-to-RF efficiency, mass and thermal behaviour** of the candidate flight microwave chain (source,
   driver, isolator, DC-DC) at the chosen frequency and power, over temperature and life.
6. **Magnetic circuit:**
   - B map and resonance-surface location vs magnet temperature.
   - Magnet operating temperature.
   - Irreversible loss after thermal cycling.
   - Magnet mass.
   - Main-coil power if an electromagnet is used.
7. **Material exposure under O/O⁺ at chamber conditions** for the window (sapphire, quartz, BN, alumina), the
   antenna (Mo, W) and its coating, the chamber walls, any carbon grid, and the magnet coatings. Measure erosion,
   oxidation and metallization of the window, and the drift they cause in coupling. Use a Kapton H witness for fluence
   referencing (ECR-E151).
8. **Endurance on air.** No ECR source has any published air/N₂/O endurance. The RFP asks > 15,000 h firing
   (repository summary).
9. **Dissociation fraction and ion mix delivered downstream** (for a pre-ionizer), plus interstage ion transport into
   the accelerator.
10. **ECR neutralizer on air**, if one is used: current per W and life. Today there are only Xe flight data and
    short-duration air cathode data.
11. **Facility effects:** operating-point sensitivity to background pressure (ECRA needs < 1e-3 Pa; ECR-E130).

## 7. Cross-reference: existing simulator ECR priors (read-only; no change proposed)

The table only records which evidence bears on each existing prior. Any change is an owner decision and a model
change (goldens move, docs/HISTORY.md entry).

| prior (location) | value in code | evidence in this audit | traced to a source? |
|---|---|---|---|
| `ECRSource.eta_dc_mw` (`abep_sim/plasma_devices.py`); `source_eff` / `dc_eff` (`thruster.py`, `archengine.py`) | 0.65 | measured range 0.3636–0.785 (§4.4) | no specific source for 0.65 identified |
| `ECRSource.eta_feed` | 0.90 | coax line 0.78–0.80 (ECR-D016); ≤ 0.631 behind ≥ 2 dB (ECR-D015); plasma coupling 0.78–0.99 (ECR-E030, E031); these are different quantities | not traced |
| `ECRSource.B_res_T` | 0.0875 | 0.08752 T at 2.45 GHz (ECR-D001) | yes (physics) |
| `ECRSource.p_min_Pa` / `Stage1.p_min_Pa` / `Ionizer.p_min_Pa` | 2e-3 Pa | μ20 typical 0.01 Pa (ECR-E071); ONERA 0.08–0.41 Pa modelled (ECR-E096); VLEO-representative ignition, numbers not public (ECR-E144) | not traced |
| `ECRSource.overdense_penalty` | 0.35 per decade of n_e/n_c | overdense operation documented (§4.2); no source quantifies a penalty | not traced |
| `Stage1` ECR `mass_kg` / `Ionizer` ECR `mass_kg` | 3.0 kg | magnet and microwave-chain masses are TBD (§4.5, ECR-E043 is a 5 W breadboard) | not traced |
| `archengine` magnet power `P_mag` when an ECR source is present | 25 W | no main-field electromagnet power found (§4.5) | not traced |
| `ppu` `hv_mw` converter for an ECR stage | 4000 V output | a 945 W 2.45 GHz magnetron self-excites at ≈ 3.69 kV anode voltage (ECR-E046) | kV class of magnetron supplies consistent with ECR-E046; no flight source |
| `MW_AIR_CATHODE` (`thruster.py`) | 0.10 mg/s air, 145 W, 3000 h | AMPCAT J. Phys. D (S11): "extracted current in the order of 1 A with 0.1 mg/s of air" (abstract statement); B-field study at 24–70 W input; no life data. The Acta Astronautica 2024 AMPCAT paper was not accessible (§8) | not traced |

## 8. Sources

| id | source | access |
|---|---|---|
| S01 | Diamant, IEPC-2009-015 | open |
| S02 | Kuninaka et al., IEPC-2009-267 | open |
| S03 | Tsukizaki et al., IEPC-2015-332 | open |
| S04 | Hosoda et al., IEPC-2009-155 (μ20) | open |
| S05 | Miyoshi, Yamamoto, Nakashima, IEPC-2007-205 | open |
| S06 | Jarrige et al., IEPC-2013-420 | open |
| S07 | Packan et al., IEPC-2019-875 (MINOTOR) | open |
| S08 | Desangles et al., EUCASS2023-761 | open |
| S09 | Vialis, Jarrige, Packan, IEPC-2017-378 | open |
| S10 | Porto, Elias, Ciardi, arXiv:2301.11411 | open (preprint) |
| S11 | Tisaev, Karadag, Lucca Fabris, J. Phys. D 56 (2023) 465203, CC BY | open |
| S12 | Tan et al., JNWPU 41(2) (2023) 274–281 | abstract_only (Crossref; publisher HTTP 403) |
| S13 | Tan et al., Aerosp. Sci. Technol. 178 (2026) 113204 | abstract_only (Crossref record of SSRN preprint) |
| S14 | Šťastný et al., CEAS Space J. 18 (2026) 497–505 | abstract_only (bot challenge not bypassed) |
| S15 | Zheng et al., Int. J. Aerosp. Eng. 2020, 8811847 (review) | open |
| S16 | de Groh et al., NASA/TM-2006-214482 (MISSE PEACE) | open |
| S17 | Arnold Magnetic Technologies, Recoma datasheet | open |
| S18 | Eclipse Magnetics, NdFeB datasheet | open |
| S19 | Kazakevich et al., arXiv:2404.16249 | open (preprint) |
| S20 | Li et al., Micromachines 15 (2024) 1354, CC BY | open |
| S21 | Wang et al., NAPAC2022-WEZD3, CC BY | open |
| S22 | CODATA 2022 (NIST) and standard formulas | open |
| S24 | Tisaev et al., J. Appl. Phys. 134 (2023) 193302 | abstract_only (Crossref) |

The full citations, DOIs and URLs are in `ecr_evidence_matrix.json` → `sources`. **Leads not admitted** (closed,
blocked, bot-challenged, out of scope, or unverifiable), each with its reason, are in `leads_not_admitted`:

- Nishiyama & Kuninaka 2008, on the microwave power absorption coefficient: directly relevant, closed.
- Tagawa et al. 2013 (ABIE): closed; used only through the review.
- Nishiyama 2003 (ABIE concept).
- Diamant 2010 (2-stage).
- Barquero et al. 2023 (μ10 on Kr).
- Tompkins et al. 2026.
- Tisaev et al. 2024 (AMPCAT, Acta Astronautica).
- Andreussi et al. 2022 review.
- ONERA HAL papers: bot challenge.
- Wang et al. 2026 (AST): unverifiable.
- Zhou et al. 2024: not an ECR source.

## 9. Reproduce

```
python docs/evidence/ecr_source/build_ecr_evidence_matrix.py          # rewrite the matrix
python docs/evidence/ecr_source/build_ecr_evidence_matrix.py --check  # verify the committed matrix is current
python -m pytest -q tests/test_ecr_source_evidence.py
```
