# R3 — H-1 materials and components: procurement / manufacturability research

Date 2026-09-27, repo base 782f900 (read-only). Status: **RESEARCH_INPUT_NOT_A_SELECTION**.

## Hard statements
- No supplier contacted; published open sources only; no paywall/bot-challenge bypassed; TLS never altered.
- Nothing is 'safe to procure now': every relevant HW requirement is PROPOSED/TBD in hardware_requirements_v1.json (status DRAFT_PENDING_OWNER), the H2 preliminary hardware freeze has not happened (A7) and the H3 procurement wave is PLANNED_NOT_REGISTERED.
- Evidence classes follow docs/EVIDENCE.md levels; supplier datasheets are L5 (measured-typical, procedure unpublished); maximum-use temperatures are L5 assumed (manufacturer recommendation).
- Values marked 'verify' are not from an accessed source.

## 1a magnetic pole/core materials (MC-1)
Requirements: HW-MC-13 (TBD; grade not selected, HWQ-18), HW-MC-06, HW-H1-14, HW-MC-12, HW-MC-15, AOL-M06, MCQ-OQ-05
**Procurement status: WAIT** — HWQ-18 (grade) and HWQ-19 (electromagnet vs PM) open; HW-MC-13 TBD; H2-1 Hall chamber + magnetic-circuit sizing and preliminary hardware freeze (A7) not done; H3 procurement wave PLANNED_NOT_REGISTERED.

### ARMCO Pure Iron (Grade 2 / Grade 4) (AK Steel International / Cleveland-Cliffs (ARMCO is a trade name; comparable low-carbon magnetic irons exist under ASTM A848, not read))
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| Fe content | min 99.85 | % | CLF-ARMCO | L5 supplier datasheet / measured-typical (procedure unpublished) |
| C max (Grade 2 / 4) | 0.010 / 0.010 | wt% | CLF-ARMCO | L5 supplier datasheet / measured-typical (procedure unpublished) |
| saturation (max intrinsic induction) | 2.15 | T | CLF-ARMCO | L5 supplier datasheet / measured-typical (procedure unpublished) |
| B at 24 kA/m (all anneal states) | 2.05-2.10 | T | CLF-ARMCO | L5 supplier datasheet / measured-typical (procedure unpublished) |
| Hc after SRA/recrystallization anneal | 16-120 | A/m | CLF-ARMCO | L5 supplier datasheet / measured-typical (procedure unpublished) |
| Hc after normalization/special anneal | 24-45 | A/m | CLF-ARMCO | L5 supplier datasheet / measured-typical (procedure unpublished) |
| mu_max after SRA/recryst. anneal | 5000-19000 | - | CLF-ARMCO | L5 supplier datasheet / measured-typical (procedure unpublished) |
| resistivity 0 / 400 / 800 C | 9.6 / 43.1 / 105.5 | uOhm cm | CLF-ARMCO | L5 supplier datasheet / measured-typical (procedure unpublished) |
| CTE 20-399 C | 13.7 | um/m/C | CLF-ARMCO | L5 supplier datasheet / measured-typical (procedure unpublished) |
| recommended magnetic anneal | 820 +/- 20 (reducing or inert atmosphere; dry N2, Ar or vacuum acceptable) | C | CLF-ARMCO | L5 supplier datasheet / measured-typical (procedure unpublished) |
| magnetic ageing maximum rate | 100-150 C (bake 177-260 C after anneal to stabilise) | C | CLF-ARMCO | L5 supplier datasheet / measured-typical (procedure unpublished) |
| Curie temperature | not stated in accessed source (textbook ~770 C: verify) | C | CLF-ARMCO | not sourced |
- Requirement: No requirement frozen yet (HW-MC-13 TBD). Candidate data cover HW-MC-13's 'sourced B-H and saturation' item only at room temperature; temperature dependence, outgassing and O-exposure data NOT in the source.
- Oxygen: Bulletin claims 'adhering, protective layers of scale' vs normal steel (qualitative, air, no temperature/time); 'excessive oxidation is injurious to the magnetic qualities'. No O/O-plasma data. Needs AOL-EX-02 / HW-MC-06 coupons and likely a coating (open).
- Availability: Bulletin lists hot-rolled sheet samples (2 and 3 mm) and forged/bar use; no lead times published.
- Limitations: Machining stresses degrade permeability -> anneal after machining (bulletin). Tends to smear in turning. Bs vs temperature not given. Ferromagnetic coupon affects B(z) (HW-MC-06).

### Hiperco 50A (FeCo-2V) (Carpenter Technology; ASTM A801 Alloy Type 1, MIL A 47182 (datasheet statement))
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| composition | Fe bal, Co 48.5, V 2.00, Nb 0.01, C 0.001 | wt% | CARP-H50A | L5 supplier datasheet / measured-typical (procedure unpublished) |
| saturation | 24 (2.4) | kG (T) | CARP-H50A | L5 supplier datasheet / measured-typical (procedure unpublished) |
| B at 16 kA/m, bar, std magnetic anneal | 2.30 | T | CARP-H50A | L5 supplier datasheet / measured-typical (procedure unpublished) |
| Hc bar / 0.355 mm strip | 209 / 30 | A/m | CARP-H50A | L5 supplier datasheet / measured-typical (procedure unpublished) |
| mu_max bar / strip | 3350 / 22000 | - | CARP-H50A | L5 supplier datasheet / measured-typical (procedure unpublished) |
| Curie temperature | 938 (1720 F) | C | CARP-H50A | L5 supplier datasheet / measured-typical (procedure unpublished) |
| resistivity 21 C | 40.1e-8 | Ohm m | CARP-H50A | L5 supplier datasheet / measured-typical (procedure unpublished) |
| CTE 25-400 C | 10.1e-6 | 1/C | CARP-H50A | L5 supplier datasheet / measured-typical (procedure unpublished) |
| anneal | 857-871 C, 4 h, dry H2 or vacuum | - | CARP-H50A | L5 supplier datasheet / measured-typical (procedure unpublished) |
| elongation after magnetic anneal (strip) | 6.7 | % | CARP-H50A | L5 supplier datasheet / measured-typical (procedure unpublished) |
- Requirement: No requirement frozen yet (HW-MC-13 TBD).
- Oxygen: Datasheet: laminations deliberately oxidised in O-bearing atmosphere at 300-500 C to grow an insulating oxide -> the alloy oxidises readily in that range (inferred from the datasheet coating note). No plasma/AO data.
- Availability: Forms manufactured: strip, plate, bar, billet. Lead times not published. Export-control: none stated in the accessed sheet.
- Limitations: Bar properties markedly softer-magnetically than strip (Hc 209 vs 30 A/m). Low ductility; must be annealed in H2/vacuum after machining. Cost/Co supply not published here.

### VACOFLUX 50 (49Co-49Fe-2V) (VACUUMSCHMELZE; IEC 60404-8-6 F11)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| Js | 2.30 | T | VAC-VF50 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| Bs at 40 kA/m | 2.35 | T | VAC-VF50 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| Hc (solid) | ~100 | A/m | VAC-VF50 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| mu_max | ~7000 | - | VAC-VF50 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| Curie temperature | 950 | C | VAC-VF50 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| resistivity | 0.42 | uOhm m | VAC-VF50 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| CTE 20-100 C | 9.4e-6 | 1/K | VAC-VF50 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| final anneal | H2, 820 C, 10 h, 100-200 K/h | - | VAC-VF50 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| elongation (final annealed) | <3 | % | VAC-VF50 | L5 supplier datasheet / measured-typical (procedure unpublished) |
- Requirement: No requirement frozen yet (HW-MC-13 TBD).
- Oxygen: Not stated in the source.
- Availability: Solid rods 12.5-182 mm diameter; others on request. No lead time published.
- Limitations: Brittle (<3 % elongation); H2 anneal required; same Co-alloy supply considerations as Hiperco (not quantified).

### 430F Solenoid Quality (ferritic 17Cr free-machining) (Carpenter; ASTM A838, A314, A581, A473, A582 (listed))
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| Cr | 17.25-18.25 | wt% | CARP-430FSQ | L5 supplier datasheet / measured-typical (procedure unpublished) |
| S | 0.250-0.400 | wt% | CARP-430FSQ | L5 supplier datasheet / measured-typical (procedure unpublished) |
| Bs | 1.56 (15.6 kG) | T | CARP-430FSQ | L5 supplier datasheet / measured-typical (procedure unpublished) |
| Curie temperature | 671 | C | CARP-430FSQ | L5 supplier datasheet / measured-typical (procedure unpublished) |
| Hc full anneal (845 C, dry H2) | 120-200 | A/m | CARP-430FSQ | L5 supplier datasheet / measured-typical (procedure unpublished) |
| mu_max full anneal | 1100-2400 | - | CARP-430FSQ | L5 supplier datasheet / measured-typical (procedure unpublished) |
| resistivity | 60 | uOhm cm | CARP-430FSQ | L5 supplier datasheet / measured-typical (procedure unpublished) |
| CTE 0-649 C | 13.0e-6 (sheet prints 12.996) | 1/C | CARP-430FSQ | L5 supplier datasheet / measured-typical (procedure unpublished) |
- Requirement: No requirement frozen yet (HW-MC-13 TBD).
- Oxygen: Corrosion rating 'Humidity: Excellent' (room-temperature aqueous scale); no high-temperature oxidation or plasma data.
- Availability: Bar rounds, billet, wire; annealed ground bar >= 9.53 mm dia.
- Limitations: Bs ~1.56 T (~27 % below pure iron) -> more ampere-turns. 0.25-0.40 % S free-machining additive: vacuum suitability (sulfide outgassing) is not addressed by the source (verify). Not recommended for welding (datasheet).

## 1b electromagnet hardware: high-temperature magnet wire and bobbins
Requirements: HW-MC-07, HW-MC-08 (TBD), HW-MC-10, HW-MC-11 (TBD), HW-MC-12, HW-MC-16 (TBD), HWQ-20, MCQ-EM-01..06, MCQ-QT-01..08
**Procurement status: WAIT** — HWQ-20 (conductor/insulation family and hot-spot margin) decided only after the H-1 thermal model hot-spot estimate; HWQ-19; MCQ-S1-01 open; H2-1/H2-5 preliminary sizing and hardware freeze pending. Exception worth an owner decision: a small sacrificial-coil lot (HW-MC-16) could be bought early for MCQ-QT-05/08 screening once HWQ-20 names a family.

### Polyimide-enamelled copper MW 16-C (Remington (distributor) per MCQ-EM-01)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| thermal class (material) | 240 | C | REMINGTON-MW16C | L5 supplier statement / assumed (manufacturer recommendation) |
- Requirement: No requirement frozen (HW-MC-07 PROPOSED; EIS family is HWQ-20).
- Oxygen: Polyimide (Kapton H) ram-AO erosion yield 3.00E-24 cm3/atom (DEGROH2006, L3, ISS exterior) -> organic enamel is AO-susceptible if exposed; no in-thruster data.
- Availability: Already in MCQ register; no lead time published.
- Limitations: Material class, not EIS class; E595 not retrieved (MCQ).

### Ceramic-insulated Ni-plated copper KD500 (Karl Schupp AG (CH))
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| conductor | Cu with 27 % Ni plating | - | SCHUPP-KD500 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| insulation thickness | 5-20 | um | SCHUPP-KD500 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| continuous temperature | -90 to +500 (2500 h min.) | C | SCHUPP-KD500 | L5 supplier statement / assumed (manufacturer recommendation) |
| short term | up to 800 (240 h tested) | C | SCHUPP-KD500 | L5 supplier statement / assumed (manufacturer recommendation) |
| test voltage / breakdown | 150 V AC (212 V DC) / >150 V AC | V | SCHUPP-KD500 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| diameter range | 0.07-1.0 (AWG 41-18) | mm | SCHUPP-KD500 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| min bend radius | 5x outer diameter | - | SCHUPP-KD500 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| outgassing | 'None' (supplier statement, no E595 value) | - | SCHUPP-KD500 | L5 supplier statement / assumed (manufacturer recommendation) |
- Requirement: No requirement frozen. Low turn voltage rating directly constrains HW-MC-11 (TBD).
- Oxygen: Ceramic insulation; Ni plating oxidises at temperature (not quantified in source).
- Availability: Catalogue item; no lead time published.
- Limitations: Ni cladding is ferromagnetic -> HW-MC-12 check. 'Ceramic is sensitive to moisture... may need to be impregnated'; dry storage. 2500 h basis is far below 15,000 h (not a life basis). Values read via page summary (no hash) -> re-read before any decision.

### Ceramawire HT (Kulgrid 28 27 % Ni-clad Cu / all-Ni) (Ceramawire (MCQ-EM-03/04))
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| continuous | -267.8 to 537.8 | C | CERAMAWIRE-HT | L5 supplier statement / assumed (manufacturer recommendation) |
| dielectric rating | 150 V DC (<= #32) / 200 V DC | V | CERAMAWIRE-HT | L5 supplier datasheet / measured-typical (procedure unpublished) |
- Requirement: No requirement frozen.
- Oxygen: vitreous enamel; Ni migration above 600 F (MCQ).
- Availability: manufacturer host 502 in MCQ lane; distributor copy.
- Limitations: See MCQ register; life '>2500 h' not a 15,000 h basis.

### Anodized-aluminium strip/wire (generic (MCQ-EM-05))
- Requirement: No requirement frozen.
- Oxygen: Al2O3 insulation (inherently oxidised) - no sourced data.
- Availability: Energies 15:5362 (2022) thermal-ageing study found but HTTP 403; no value taken.
- Limitations: NOT_SOURCED_FOR_SELECTION

### Bobbin / coil former: BN, alumina or machinable glass-ceramic (see category 2 for BN grade data)
- Requirement: No requirement exists for the bobbin.
- Oxygen: see category 2
- Availability: not published
- Limitations: Bobbin must be non-ferromagnetic (HW-MC-12). No bobbin-specific source accessed.

## 2 discharge-channel wall ceramics (BN, BN-SiO2, alumina)
Requirements: HW-H1-04 (TBD; owner decision lane 17 Q6 / HWQ-08), HW-H1-11, HW-H1-14, HWQ-17, AOL-M02, AOL-M03, HW-PIM-14
**Procurement status: WAIT** — Wall grade is an owner decision (HWQ-08, lane 17 Q6); HWQ-17 (alternative sector inserts); H-1 geometry release (HW-H1-03 TBD) and wall-ring design (HW-H1-11) needed to size billets; coupons must share the installed lot (HW-H1-14), so coupon stock cannot be bought ahead of the wall lot.

### BN-SiO2 composite, Grade M26 (Combat-type; historical P5 wall per repo) (Saint-Gobain Combat M26 (manufacturer sheet 403, not read); values from Precision Ceramics sheet)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| density | 2.1 | g/cm3 | PC-BN-MM26 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| thermal conductivity par / perp | 11 / 29 | W/mK | PC-BN-MM26 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| CTE 25-400 C par / perp | 3 / 0.4 | 1e-6/K | PC-BN-MM26 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| flexural strength par / perp | 62 / 34 | MPa | PC-BN-MM26 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| max temperature air / inert | 1000+ / 1000+ | C | PC-BN-MM26 | L5 supplier statement / assumed (manufacturer recommendation) |
| dielectric strength DC | 66 | kV/mm | PC-BN-MM26 | L5 supplier datasheet / measured-typical (procedure unpublished) |
- Requirement: No requirement frozen (HW-H1-04 TBD).
- Oxygen: Air rating 1000+ C (thermal, no plasma/AO). No N+/O+ sputter yield on BN-SiO2 exists (lane 32). Cifali 2011: 'signs of operation with oxygen ... visible on the ceramics' (L3, visual, 10 h).
- Availability: Hydrophobic (passes MIL-I-10A L542 48 h immersion). No lead time published. Manufacturer sheet blocked.
- Limitations: Conflict: an AZoM article snippet attributes 12/14 W/mK to M26 and 11/29 to M; the rendered Precision Ceramics sheet shows the reverse (M=12/14, M26=11/29). Resolve from the manufacturer sheet before use.

### BN Grade M (BN + silica) (Saint-Gobain Combat M via Precision Ceramics)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| density | 2.3 | g/cm3 | PC-BN-MM26 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| thermal conductivity par / perp | 12 / 14 | W/mK | PC-BN-MM26 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| flexural par/perp | 103 / 76 | MPa | PC-BN-MM26 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| max temperature air | 1000+ | C | PC-BN-MM26 | L5 supplier statement / assumed (manufacturer recommendation) |
- Requirement: No requirement frozen.
- Oxygen: as M26 (thermal air rating only)
- Availability: not published
- Limitations: not a flight Hall wall grade in accessed sources

### High-purity diffusion-bonded hBN Grade AX05 (Saint-Gobain Combat AX05 via Precision Ceramics)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| density | 1.9 | g/cm3 | PC-BN-AX05 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| thermal conductivity par / perp | 78 / 130 | W/mK | PC-BN-AX05 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| max temperature air / inert | 850 / 2000 | C | PC-BN-AX05 | L5 supplier statement / assumed (manufacturer recommendation) |
| flexural par / perp | 22 / 21 | MPa | PC-BN-AX05 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| dielectric strength DC | 79 | kV/mm | PC-BN-AX05 | L5 supplier datasheet / measured-typical (procedure unpublished) |
- Requirement: No requirement frozen.
- Oxygen: Lowest air rating (850 C) of the grades read; binder-free, so no B2O3/SiO2 phase (source), but pure BN oxidises to B2O3 (lane 32, model-level).
- Availability: not published
- Limitations: Low strength; moisture behaviour not stated.

### HeBoSint PL/CL/CL-S 200 (BN+SiO2)/CL-Z/SL-A grades (Henze BNP AG)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| use temperature max, oxidizing | ~900 (all grades) | C | HENZE-HEBOSINT | L5 supplier statement / assumed (manufacturer recommendation) |
| use temperature max, inert/vacuum | 1500-2000 (grade-dependent) | C | HENZE-HEBOSINT | L5 supplier statement / assumed (manufacturer recommendation) |
- Requirement: No requirement frozen.
- Oxygen: ~900 C oxidizing guide; no plasma/AO coverage (repo lane 15).
- Availability: repo record reused
- Limitations: CL-S 200 is BN-SiO2 but not M26.

### High-purity alumina (e.g. 99.5 %) (CoorsTek AD-995 etc.)
- Requirement: No requirement frozen.
- Oxygen: fully oxidised ceramic; Espy 1993 O+ yields on Al2O3 exist but not accessed (lane 32).
- Availability: CoorsTek PDF: TLS failure / HTTP 503; no value recorded.
- Limitations: Not a flight Hall wall material per HW-H1-04 context; unsourced here.

## 3 anode / gas-distributor materials for O2-bearing feed
Requirements: HW-H1-05 (PROPOSED), HW-H1-09 (TBD), HW-H1-10, HWQ-08, AOL-M01, AOL-M08, AOL-OQ-03, HW-ELEC-04
**Procurement status: WAIT** — HWQ-08 (anode/distributor material or coating) and AOL-OQ-03 (candidate list) open; HW-H1-09 TBD; H-1 design release; H2-1 sizing. Candidate coupon materials could be listed now but none is fixed by a requirement.

### Literature evidence (no material named) (n/a)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| PPS1350-TSD anode after 10 h N2/O2 | 'seems rusty'; oxidation 'main concern' for endurance | - | CIFALI2011 | L3 primary literature, other device (NOT transferred to H-1) |
| pure-O2 test replaced by 1.27N2+O2 | 'in order to limit anode oxidation' | - | CIFALI2011 | L3 primary literature, other device (NOT transferred to H-1) |
| PPS1350 N2/O2+10 % Xe steady before first oxidation flame-out | ~314 | h | ANDREUSSI2022 | L5 review (second-hand of CIFALI2012) |
| authors' remedy | 'alternative, oxidation-resistant anode materials' (none named) | - | ANDREUSSI2022 | L5 assumed |
| RIT10 graphite grids on pure O2 | erosion 'noticeably higher' than N2; Ti grids lower | - | ANDREUSSI2022 | L5, other device class |
- Requirement: Supports HW-H1-05 evidence basis; does not select a material.
- Oxygen: see specs
- Availability: Anode material of the PPS1350 not stated in accessed text.
- Limitations: Other device; not transferred to H-1.

### Austenitic stainless 316L (fitting/bar grade) (generic; Swagelok 316L fittings rated 537 C (SWG-MS-01-24))
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| 316L fitting temperature rating | 1000 F (537 C) | C | SWG-MS-01-24 | L5 supplier statement / assumed (manufacturer recommendation) |
- Requirement: No requirement frozen.
- Oxygen: No sourced oxidation data at anode temperature in O/O2 plasma (verify). Non-magnetic in annealed state (general knowledge, verify) - relevant to HW-MC-12.
- Availability: commodity
- Limitations: Only a pressure-fitting temperature rating was sourced, not an oxidation limit.

### Ni-base alloys (e.g. Inconel 600/625, Haynes 214/230) (not sourced this pass)
- Requirement: No requirement frozen.
- Oxygen: unsourced (verify from Special Metals/Haynes datasheets)
- Availability: not published
- Limitations: Ni-rich alloys can be ferromagnetic depending on grade/temperature (verify) -> HW-MC-12.

### Mo / W (Plansee page read (no oxidation statement))
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| Mo melting point | 2620 | C | (plansee.com molybdenum page, not hashed) | L5 supplier datasheet / measured-typical (procedure unpublished) |
- Requirement: No requirement frozen.
- Oxygen: Volatile-oxide behaviour in O2 is common knowledge but NOT sourced here (verify). Lane 10: AMPCAT microwave cathode on O2/N2 showed MoOx deposition within ~1 h (L3, other device).
- Availability: not published
- Limitations: Evidence of MoOx deposition makes Mo unattractive for O-wetted surfaces pending sourced data.

### Platinum-group coatings (Pt, Ir) on anode (not sourced)
- Requirement: No requirement frozen.
- Oxygen: unsourced
- Availability: not published
- Limitations: Coupon pairs coated/uncoated required by AOL-M08 if pursued.

## 4 high-temperature vacuum wiring and insulation
Requirements: HW-ELEC-04 (insulation to HW-ENV-01 rating), HW-ELEC-05 (TBD), HW-MC-14 (TBD), HW-H1-12, HW-C1-09, HW-ENV-01 (V_d rating, PROPOSED up to 350 V, HWQ-03), AOL-M07
**Procurement status: WAIT** — Harness temperature zones depend on H-1 thermal model (H2-5) and coil hot-spot (HWQ-20); HW-ELEC-05 test voltage TBD (MCQ-QT-08, owner); V_d rating HWQ-03 open; W4 channel map. Generic Kapton/PEEK UHV wire for cold facility runs is low-risk but still not fixed by a requirement.

### Kapton-insulated UHV wire (standard 311-KAP series) (allectra)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| max voltage in vacuum (e.g. 311-KAP-100, AWG18) | 10,000 | V DC | ALLECTRA-311 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| voltage rating condition | pressure < 1e-3 mbar; 'not recommended for air use' | - | ALLECTRA-311 | L5 supplier datasheet / measured-typical (procedure unpublished) |
- Requirement: No requirement frozen; ratings far above the 350 V PROPOSED envelope.
- Oxygen: Kapton H AO erosion yield 3.00E-24 cm3/atom (DEGROH2006, L3); keep out of plume/O-rich line of sight.
- Availability: catalogue item
- Limitations: Standard-grade max temperature not extracted from the sheet (only radiation-resistant grades carry 300 C); DuPont Kapton HN sheet not retrieved (404).

### Radiation-resistant Kapton wire (301-KAP/KAPM series) (allectra)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| max temperature | 300 | C | ALLECTRA-311 | L5 supplier statement / assumed (manufacturer recommendation) |
| radiation resistance | 1e9 | rad | ALLECTRA-311 | L5 supplier datasheet / measured-typical (procedure unpublished) |
- Requirement: No requirement frozen.
- Oxygen: as Kapton
- Availability: not published
- Limitations: —

### PEEK-insulated UHV wire / ribbon (allectra)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| max temperature (ribbon / wire rows) | 260 / 250 | C | ALLECTRA-311 | L5 supplier statement / assumed (manufacturer recommendation) |
- Requirement: No requirement frozen.
- Oxygen: organic; no AO data sourced
- Availability: not published
- Limitations: —

### Bare conductor on alumina fish-spine/ceramic beads (generic)
- Requirement: No requirement frozen.
- Oxygen: inorganic; unsourced
- Availability: not published
- Limitations: Not sourced this pass (verify).

### MgO mineral-insulated cable / thermocouple (generic)
- Requirement: No requirement frozen.
- Oxygen: unsourced
- Availability: not published
- Limitations: MCQ-EM-06 NOT_SOURCED (403 in MCQ lane); not sourced here either.

## 5 LaB6 hollow-cathode support materials and commercial cathodes (C-1)
Requirements: HW-C1-01 (PROPOSED; HWQ-09), HW-C1-02, HW-C1-03, HW-C1-06, HW-C1-08, HW-C1-09, AOL-M04, AOL-M05
**Procurement status: WAIT** — HWQ-09 (C-1 type and emission rating) open; keeper/interstage currents TBD (HW-C1-02); H2-2 cathode integration lane not done. Note A4 allows a C-1 diode in S1a, which makes C-1 an early S1a long-lead item once HWQ-09 closes.

### Graphite (insert sleeves/contact) (grade not named in source)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| reason for graphite | LaB6 'cannot be touched by metals during operation due to boron diffusion causing embrittlement issues in high-temperature refractory materials' | - | NASA-TB-LAB6 | L5 NASA tech brief (design statement) |
| general statement | LaB6 must be supported/contacted by 'materials that inhibit boron diffusion at the operating temperatures' | - | GK2008-CH6 | L4/5 textbook |
- Requirement: No requirement frozen (C-1 type is HWQ-09).
- Oxygen: Graphite reacts with O (RIT10 graphite grids eroded faster on O2, ANDREUSSI2022, L5); C-1 is Xe-fed but exposed to O back-flow (HW-C1-03).
- Availability: not published
- Limitations: Original all-graphite tube 'difficult to machine and ... subject to vibration-induced fracturing' (NASA-TB-LAB6).

### Mo or Mo-Re cathode tube with graphite sleeves, W spring, BN/AlN heater former (JPL design (NASA-TB-LAB6))
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| tube material | molybdenum or molybdenum-rhenium | - | NASA-TB-LAB6 | L5 |
| heater insulator | boron nitride or aluminum nitride | - | NASA-TB-LAB6 | L5 |
- Requirement: No requirement frozen.
- Oxygen: Mo in O environment: MoOx deposition seen on AMPCAT (lane 10, L3); HC20h LaB6 cathode FED with N2/O2 showed 'severe erosion and embrittlement of the cathode tube' (ANDREUSSI2022 p.38, L5) - C-1 is Xe-fed, so partially mitigated.
- Availability: Design reference, not a product.
- Limitations: —

### Tantalum / rhenium (n/a)
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| Ta work function / Richardson const (as emitter) | 4.1 eV / 37 | - | GK2008-CH6 | L4 |
- Requirement: No requirement frozen.
- Oxygen: unsourced
- Availability: not published
- Limitations: No sourced LaB6-compatibility statement for Ta/Re accessed this pass (verify).

### Commercial LaB6 hollow-cathode assemblies / inserts (none found in an open published catalogue this pass)
- Requirement: HW-C1-02 emission rating not checkable without a datasheet.
- Oxygen: —
- Availability: Search returned research designs (JPL, MEERCAT, IEPC-2015-47) not catalogues. Export control of flight-derived cathodes: not published in accessed sources (verify before any foreign procurement).
- Limitations: unresolved

## 6 vacuum-compatible fittings, feedthroughs and gas-line electrical breaks
Requirements: HW-FS-06 (PROPOSED; margin TBD), HW-FS-07 (TBD; O2 cleaning standard TBD at HRR), HW-PIM-01, PMI-02 (o2_cleaning_standard TBD), PMI-06 (isolator_margin TBD), HW-ENV-01 / HWQ-03, HW-MC-12 / HW-PIM-03 (non-ferromagnetic)
**Procurement status: WAIT** — HW-FS-07 O2 cleaning standard TBD (facility safety case, closes at HRR); isolator_margin TBD (S1a hipot); HWQ-03 (350 V rating); IP-UP/IP-DN drawing (HWQ-15) and H2-3 gas path/plenum lane. Standard VCR/SC-11 parts are commodity and low-risk, but no requirement fixes them yet.

### VCR metal gasket face seal fittings (Swagelok (316L / 316L VAR))
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| He leak rate max, Ag-plated/Cu gasket | 4e-9 | std cm3/s | SWG-MS-01-24 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| He leak rate max, unplated gasket | 4e-11 | std cm3/s | SWG-MS-01-24 | L5 supplier datasheet / measured-typical (procedure unpublished) |
| temperature rating 316L fittings | 537 (1000 F) | C | SWG-MS-01-24 | L5 supplier statement / assumed (manufacturer recommendation) |
| gasket temperature Ni / Cu | 315 / 204 | C | SWG-MS-01-24 | L5 supplier statement / assumed (manufacturer recommendation) |
- Requirement: No requirement frozen (leak_rate_max TBD, PMI-02).
- Oxygen: Available with SC-11 cleaning to ASTM G93 Level C: NVR <= 66 mg/m2 (6 mg/ft2), non-hydrocarbon lubricant (SWG-SC11).
- Availability: catalogue; traceability to raw material stated in catalogue.
- Limitations: Ni gaskets ferromagnetic (verify) -> keep away from MC-1 (HW-MC-12).

### Ceramic gas-line electrical break (1/4 VCR) (Solid Sealing Technology 13 kV (also 30 kV variant listed); alternatives MDC, Accu-Glass, Kurt J. Lesker (pages not read))
| quantity | value | unit | source | evidence |
|---|---|---|---|---|
| voltage rating | 13,000 | V | SST-13KV | L5 supplier statement / assumed (manufacturer recommendation) |
| temperature rating | -200 to 450 | C | SST-13KV | L5 supplier statement / assumed (manufacturer recommendation) |
| ceramic | alumina | - | SST-13KV | L5 supplier datasheet / measured-typical (procedure unpublished) |
| pressure rating | 900 | psig | SST-13KV | L5 supplier datasheet / measured-typical (procedure unpublished) |
- Requirement: Rating >> 350 V PROPOSED V_d (HW-FS-06) but isolator_margin is TBD, so not formally satisfied.
- Oxygen: O2 cleaning not addressed on page -> would need SC-11-type cleaning order (HW-FS-07).
- Availability: catalogue part; rating conditions (vacuum/atmosphere side) not stated on page.
- Limitations: Kovar-type sleeves in similar products are ferromagnetic (search snippet, verify); leak rate not stated.

### CF/KF flanges and multi-pin UHV feedthroughs (not sourced this pass)
- Requirement: No requirement frozen (flange pattern HW-PIM-01 PROPOSED; interface_dimensions TBD).
- Oxygen: —
- Availability: not published
- Limitations: Choice waits for IP-UP/IP-DN interface drawing (HWQ-15).

## Unresolved
- Saint-Gobain Combat M26/AX05/HP manufacturer datasheets (403/bot challenge); M vs M26 thermal-conductivity column conflict (Precision Ceramics sheet vs AZoM snippet).
- Temperature dependence of Bs/permeability for any pole grade up to the (unknown) pole temperature (HW-MC-13 needs it).
- Pure-iron Curie temperature not in the ARMCO bulletin.
- Mo/W/Ni-alloy/Pt-coating oxidation data in O2 at anode temperature: not sourced.
- DuPont Kapton HN temperature/outgassing sheet not retrieved; ASTM E595 values for any wire/enamel not retrieved.
- MgO mineral-insulated cable and ceramic-bead wiring: no open datasheet read.
- No open commercial LaB6 hollow-cathode catalogue with emission rating found; export-control status unknown.
- CoorsTek alumina properties not read (TLS/503).
- Anodized-Al wire (Energies 15:5362) not read (403).
- ASTM A848/A801/A838 scopes not read (403).

## Owner questions
- OQ-R3-1 (HWQ-18/19): Pole material - pure iron (Bs 2.15 T, cheap, anneal after machining) vs FeCo-2V (2.3-2.4 T, Curie 938-950 C, brittle, H2 anneal) vs 430F SQ (1.56 T, corrosion-resistant, S-bearing)? Decide with the H2-1 flux-density estimate.
- OQ-R3-2 (HWQ-20/HW-MC-11): If ceramic-insulated Ni-plated wire is chosen, accept ~150 V AC turn rating and Ni ferromagnetism near MC-1?
- OQ-R3-3 (HWQ-08): Which anode candidates go on AOL-EX-02 coupons (e.g. 316L, a Ni-base alloy, Pt/Ir coating)? None is sourced as O-plasma-resistant.
- OQ-R3-4 (HW-FS-07/PMI-02): Adopt ASTM G93 Level C (e.g. Swagelok SC-11 equivalent) as the O2 cleaning standard?
- OQ-R3-5: Authorise acquisition of manufacturer datasheets through the owner channel (control C4) for Combat BN grades and C-1 cathode candidates?

## Source register
- **CARP-H50A** — Carpenter Technology / Carpenter Electrification, Hiperco 50A data sheet (E199), v 05-20, (c) 2020. https://f.hubspotusercontent20.net/hubfs/7407327/carpenter_electrification/Resources/Datasheets/Hiperco_50A_Alloy_(E199).pdf (accessed 2026-09-27; open manufacturer datasheet; 'typical or average values, not a guarantee'; sha256 `210b476850f30cbf…`)
- **VAC-VF50** — VACUUMSCHMELZE GmbH & Co. KG, VACOFLUX 50 datasheet, July 2022. https://vacuumschmelze.com/03_Documents/Brochures/Datasheet%20%20VACOFLUX%2050.pdf (accessed 2026-09-27; open manufacturer datasheet; 'typical values'; sha256 `dddfac04d6165f6e…`)
- **CLF-ARMCO** — AK Steel International (Cleveland-Cliffs), ARMCO Pure Iron - High Purity Iron, Product Data Bulletin (Euro, 07/2022; PDF created 2022-10-13). https://www.aksteel.nl/files/downloads/clf_productdata__armco_pure_iron_pdb_euro_final_072022_92.pdf (accessed 2026-09-27; open manufacturer bulletin; mechanical values 'for information only'; sha256 `b3306c48e295f80a…`)
- **CARP-430FSQ** — Carpenter Electrification, 430F Solenoid Quality Stainless data sheet (file 20200717). https://www.carpenterelectrification.com/hubfs/Resources/Datasheets/20200717-CT-430F-Solenoid-Quality-Electrification-Datasheet_F.pdf (accessed 2026-09-27; open manufacturer datasheet; sha256 `e35c1bcfdc9e6921…`)
- **PC-BN-MM26** — Precision Ceramics (UK/USA/EU), Material Datasheet Boron Nitride (BN) Grades M & M26 (2018 upload). https://precision-ceramics.com/wp-content/uploads/2018/07/Boron-Nitride-Grade-M-M26-Technical-Data-Sheet-en.pdf (accessed 2026-09-27; open distributor/machinist datasheet (not the powder/billet manufacturer); 'mean and typical ... not guaranteed'; sha256 `ee28f3f08b899515…`)
- **PC-BN-AX05** — Precision Ceramics, Material Datasheet Boron Nitride (BN) Grade AX05 (2018 upload). https://precision-ceramics.com/wp-content/uploads/2018/07/Boron-Nitride-Grade-AX05-Technical-Data-Sheet-en.pdf (accessed 2026-09-27; open distributor datasheet; typical values; sha256 `bb917555389e881c…`)
- **HENZE-HEBOSINT** — Henze Boron Nitride Products AG, HeBoSint qualities datasheet 08.2021 (as recorded in repo schemas/thermal_life/limits_v1.json, accessed 2026-09-26 by lane 15). https://nitrid.eu/files/henze/en/HS_Qualities_en.pdf (accessed 2026-09-27; open manufacturer datasheet; NOT re-read by this lane (repo record reused))
- **SCHUPP-KD500** — Karl Schupp AG, 'KD500 high temperature winding wires with ceramic insulation (500 °C)' product web page. https://schupp.ch/en/p/kd500-winding-wires-with-ceramic-insulation-500c/ (accessed 2026-09-27; open manufacturer web page (values read via fetch summary; no PDF hash))
- **CERAMAWIRE-HT** — Ceramawire HT technical specification (repo MCQ source ceramawire_ht, distributor copy). https://www.motionsensors.com/wp-content/uploads/2022/07/ceramaTechspec.pdf (accessed 2026-09-27; as recorded in docs/experiments/magnet_coil/magnet_coil_qualification_v1.json; not re-read)
- **REMINGTON-MW16C** — Remington Industries, polyimide MW 16-C data sheet (repo MCQ source remington_mw16c). https://www.remingtonindustries.com/content/Polyimide%20Magnet%20Wire%20Data%20Sheet.pdf (accessed 2026-09-27; as recorded in the MCQ register; not re-read)
- **NASA-TB-LAB6** — NASA Tech Briefs, 'Improved Rare-Earth Emitter Hollow Cathode' (JPL; NTRS 20110012226). https://ntrs.nasa.gov/api/citations/20110012226/downloads/20110012226.pdf (accessed 2026-09-27; open NASA technical brief; sha256 `ba0f3085b7c2e4d5…`)
- **GK2008-CH6** — D. M. Goebel and I. Katz, Fundamentals of Electric Propulsion, JPL 2008, Chapter 6 Hollow Cathodes (separate chapter PDF). https://descanso.jpl.nasa.gov/SciTechBook/series1/Goebel_06_Chap6_cathodes.pdf (accessed 2026-09-27; open (JPL DESCANSO); sha256 `61ea4e1069e9beaa…`)
- **ALLECTRA-311** — allectra GmbH, 'Kapton and PEEK insulated wires for UHV use' overview (file 311-Kaptonwires-overview-2023-10). https://www.allectra.com/wp-content/uploads/2025/02/311-Kaptonwires-overview-2023-10.pdf (accessed 2026-09-27; open manufacturer catalogue sheet; sha256 `7031cb0330785ced…`)
- **SWG-MS-01-24** — Swagelok, VCR Metal Gasket Face Seal Fittings catalog MS-01-24. https://www.swagelok.com/downloads/webcatalogs/en/ms-01-24.pdf (accessed 2026-09-27; open manufacturer catalogue; sha256 `8025dc1284cfa31b…`)
- **SWG-SC11** — Swagelok, Special Cleaning and Packaging (SC-11), specification SCS-00011, MS-06-63. https://www.swagelok.com/downloads/webcatalogs/en/ms-06-63.pdf (accessed 2026-09-27; open manufacturer specification; sha256 `9862eb882bbf9576…`)
- **SST-13KV** — Solid Sealing Technology, 13 kV Ceramic Vacuum Break, Electrical Isolator, 0.25 in ID, -200 to 450 °C, 1/4 VCR (product page 203). https://www.solidsealing.com/products/203/13kV-Ceramic-Vacuum-Break-Electrical-Isolator-0-25-Inch-Insulator-ID-Rated-from-200-C-to-450-C-1-4-VCR-Break/ (accessed 2026-09-27; open manufacturer web page (fetch summary; no hash))
- **CIFALI2011** — G. Cifali et al., 'Experimental characterization of HET and RIT with atmospheric propellants', IEPC-2011-224 (as recorded and verified by the AO register v5, CIFALI2011, p. 2 and p. 5). https://electricrocket.org/IEPC/IEPC-2011-224.pdf (accessed 2026-09-27; open; repo record reused, not re-read)
- **ANDREUSSI2022** — T. Andreussi, E. Ferrato, V. Giannetti, J. Electr. Propuls. 1:31 (2022), doi:10.1007/s44205-022-00024-9 (as recorded by AO register v5, Page 24 and 38 of 57). https://link.springer.com/content/pdf/10.1007/s44205-022-00024-9.pdf (accessed 2026-09-27; open CC BY; repo record reused, not re-read)
- **DEGROH2006** — de Groh et al., NASA/TM-2006-214482, MISSE PEACE polymers (as recorded by AO register v5; Kapton H erosion yield 3.00E-24 cm3/atom, Table 4 p.17). https://ntrs.nasa.gov/api/citations/20070002707/downloads/20070002707.pdf (accessed 2026-09-27; open; repo record reused)

## Access failures (not bypassed)
- https://www.bn.saint-gobain.com/sites/hps-mac3-cma-boron-nitride/files/2022-06/combat-bn-solids-ds.pdf: HTTP 403 (WAF page) on 2026-09-27; also bot-challenged 2026-09-26 per lane 15; not bypassed
- https://www.professionalplastics.com/professionalplastics/content/downloads/Combat-BoronNitrideData.pdf: Incapsula bot challenge (HTML); not bypassed
- https://www.astm.org/a0848-17.html: HTTP 403; ASTM A848 scope not read
- https://www.mdpi.com/1996-1073/15/15/5362: HTTP 403 (Energies 15:5362 anodized-Al strip wire ageing study); not read, no value taken
- https://www.coorstek.com/media/4235/advanced-alumina.pdf: curl TLS verify failure; WebFetch HTTP 503; TLS not altered; no CoorsTek value taken (search-snippet values deliberately NOT used)
- https://www.dupont.com/.../EI-10142-Kapton-Summary-of-Properties.pdf: HTTP 404 (guessed URL); DuPont Kapton HN temperature limits not sourced here
- https://www.plansee.com/en/materials/molybdenum.html: accessed; contains no oxidation statement (melting point 2620 °C only); Mo/W oxidation remains unsourced
