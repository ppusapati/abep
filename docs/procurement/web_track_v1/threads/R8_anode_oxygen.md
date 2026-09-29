# R8 - Anode materials in oxygen-bearing plasma (web evidence pass, 2026-09-27)

Status: research evidence only. Nothing here selects a material or freezes a requirement (HW-H1-05 PROPOSED, HWQ-08 open, AOL-OQ-03 open).

## Key findings
- **The only direct O-plasma Hall-anode comparison is Imperial's WET-HET.** Bare W formed a non-conductive oxide in 20-30 min. Stainless steel kept its conductivity 'mostly'. It was used at low power, and oxidation became 'more pronounced' at higher power (Tejeda et al. 2024, Acta Astronautica 219, Sec. 3.5 p.550). The grade 316L and the Rh/Cr-coated-W statement come only from snippets of Tejeda & Knoll 2023 (verify).
- Cifali 2011 (IEPC-2011-224, p.5): the PPS1350 anode looked 'rusty' after 10 h of N2/O2. The authors name the rising electrical resistance as the main endurance concern. On the RIT-10 (p.10), graphite grids eroded noticeably more on O2 than on N2, and the authors attribute it to chemistry.
- Gabriel et al. 1993 (IEPC-93-167): O2 MPD work reports that ThW cathodes passivate, and that an insulating oxide on the anode extinguishes the discharge. Its suggested remedies are Inconel X-750/Hastelloy, an IrO2 (or RuO2) conductive-oxide anode coating, or an Ir anode. From the ion-source literature it quotes an SrO-on-Pt cathode lasting 63 h against 3-5 h for a Ta wire.
- The failure mode in every O-plasma report is **loss of electrical conduction (resistance rise, extinction)**, not mass loss. Coupons therefore need resistance metrology.
- Furnace data: Mo (TZM) loses mass through volatile MoO3 above 550 C. The Mo flux is 3.43 g/m2h at 650 C and 2.42e3 g/m2h at 800 C (Smolik 2000, Table 2). After 60 h in air at 1100 C, Ir lost 53.69 %, IrRh40 lost 0.63 % and Rh gained 2.73 % (Zhao 2019, verify). Graphite AO erosion yield on MISSE 2 was 4.15e-25 cm3/atom.

## Candidate matrix (summary)

| material | O-plasma evidence | status |
|---|---|---|
| Austenitic stainless 316L | YES - O2 Hall anode (Imperial WET-HET/AQUAHET; conductivity 'mostly preserved', worse at higher power) [TEJEDA2024, TEJEDA2023 snippet] | leading heritage candidate (lab-scale, hours) |
| Chromia-forming Ni superalloys (Inconel 600/625/X-750, Haynes 230, Hastelloy) | NO direct; suggested for O2 ion-source/MPD anodes [GABRIEL1993] | candidate, no plasma evidence |
| Alumina-forming alloys (Inconel 601, Haynes 214, FeCrAl) | NO | test only as hypothesis-control |
| Tungsten (bare) | YES - FAILED: non-conductive oxide in 20-30 min [TEJEDA2024]; ThW cathodes passivate in O2 MPD [GABRIEL1993] | REJECT as bare anode (evidence) |
| Molybdenum / TZM | NO (air furnace only) | REJECT for hot O-exposed parts |
| Copper | used as O2 HET anode up to 2880 W [SCHWERTHEIM2022], outcome not reported; Cu anode in O2 MPD [GABRIEL1993] | low priority unless actively cooled |
| Platinum (bulk or clad/plated) | indirect: Pt substrate for SrO cathode, 63 h in O2 ion source [GABRIEL1993/HENTSCHEL1992] | coupon candidate |
| Rhodium (plating) | NO; proposed by Imperial [IPPL_WEB, TEJEDA2023 snippet] | coupon candidate |
| Iridium | Ir/thoria-coated Ir emitters in O2 ion sources, ~1000+ h (second-hand) [GABRIEL1993] | low priority bulk; see IrO2 coating |
| Chromium (plating) | NO; proposed because 'conductive properties of its oxidation layer' [IPPL_WEB] | coupon candidate |
| Conductive-oxide coatings (IrO2, RuO2; e.g. mixed-metal-oxide on Ti) | suggested for O2 ion-source anodes [GABRIEL1993 citing GUARNIERI1988] | coupon candidate (novel) |
| Graphite (incl. pyrolytic) | YES - RIT-10 graphite grids eroded noticeably more on O2 [CIFALI2011] | reference coupon only |
| Titanium | Ti grids lower erosion than graphite on O2 (second-hand) [ANDREUSSI2022] | optional |
| TiN / ZrN coatings | NO | optional, only if anode T well below 600 C |
| ZrB2/HfB2 UHTC, SiC | NO (none found) | not recommended now |
| Hafnium / zirconium | industrial O2/air plasma-arc cathode inserts [HF_ARC_SNIPPET] | not an anode analogue |

## Proposed coupon candidates - PROPOSAL FOR OWNER, NOT A DECISION

| id | material | role | basis |
|---|---|---|---|
| R8-C01 | 316L (anode-lot, same heat as H-1 anode) | baseline / heritage (Imperial O2 HET) | TEJEDA2024 Sec.3.5; TEJEDA2023 |
| R8-C02 | Chromia-forming Ni alloy (one of Inconel 600, 625 or Haynes 230 - owner pick) | higher-T metallic alternative | GABRIEL1993 suggestion; SMC_IN600 |
| R8-C03 | Alumina-forming alloy (Inconel 601 or FeCrAl) | hypothesis control: does an Al2O3-forming alloy develop an insulating scale? | SMC_IN601; inference (verify) |
| R8-C04 | Rh electroplate on 316L (thickness TBD by owner/vendor) | Imperial-proposed coating | IPPL_WEB; ZHAO2019 |
| R8-C05 | Pt clad or plate on 316L | noble-metal coating | GABRIEL1993/HENTSCHEL1992; PGM1400_SNIPPET |
| R8-C06 | Cr electroplate on 316L | Imperial-proposed conductive-oxide former | IPPL_WEB |
| R8-C07 | IrO2- or RuO2-based conductive-oxide coating (e.g. commercial MMO on Ti) | pre-oxidized conductive surface | GABRIEL1993 citing GUARNIERI1988 |
| R8-C08 | Bare W | negative control (known insulating oxide in 20-30 min) to validate the resistance-rise measurement | TEJEDA2024 |
| R8-C09 | Graphite (isotropic grade) | optional mass-loss reference (volatile oxide) | CIFALI2011; BANKS2004 |

per coupon: 4-wire sheet/contact resistance before/after (the PPS1350 and WET-HET failure mode is resistance rise, not mass loss), mass (AOL-PM-02 protocol), oxide thickness/phase (SEM/XPS), adjacent thermocouple (AOL-CX-07); exposure in N2+O2 up to the delivered O2 mass fraction 0.60 plus atomic-O (AOL-EX-02); electron-collecting bias for at least one coupon of each material, since the anode role (electron current, sheath) differs from a floating witness - owner to decide

## Evidence (numbers with locators)

| material | result | source | locator | class |
|---|---|---|---|---|
| PPS1350-TSD anode (material not stated) | anode 'seems rusty'; 'anode oxidation with the consequent increase in electrical resistance is the main concern' for a future endurance test | CIFALI2011 | p.5, last paragraph | L3 primary, other device |
| PPS1350-TSD anode | pure O2 test replaced by 1.27N2+O2 'in order to limit anode oxidation' | CIFALI2011 | p.2 (Sec. II test plan) | L3 primary |
| RIT-10 grids (graphite) | grid erosion 'noticeably higher than after test with nitrogen'; attributed 'probably' to chemical processes between graphite and oxygen | CIFALI2011 | p.10 (after Fig. 17) | L3 primary, other device class |
| Tungsten anode plate | 'anode plates made out of tungsten quickly (20-30 min) develop an oxidation layer which is non-conductive'; 'imposes severe constraints' on endurance tests | TEJEDA2024 | Sec. 3.5 'Oxidation of the hardware', p.550 (reporting TEJEDA2023 [21]) | L3 primary (second statement of authors' own prior result) |
| Stainless steel anode plate (316L per snippet of TEJEDA2023; grade not stated in TEJEDA2024) | 'exhibit a prolonged resistance to oxidation, thereby preserving their electrical conductivity for longer periods of time, particularly during low-power testing. However ... when subjected to higher power levels the issue of surface oxidation becomes more pronounced.' | TEJEDA2024 | Sec. 3.5 p.550; Sec. 1 p.543; Table 1 (anode material: stainless steel) | L3 primary |
| Tungsten vs stainless steel anode | Abstract (snippet): W develops non-conductive layer 'after just a few hours'; stainless-steel oxidation layer 'still conductive and did not compromise the functionality of the thruster throughout the duration of the experimental campaigns'; W covered with rhodium and chromium layer named as suitable because of low oxidation rates | TEJEDA2023 | abstract (via search snippets; full text not accessed) | verify |
| Stainless steel anode plate + BN-SiO2 M26 walls | material selection retained from TEJEDA2023; test duration ~34 min | MUNOZTEJEDA2024 | Sec. II.A (Hall thrusters) and Sec. IV (stability range) | L3 primary |
| Copper anode | copper anode sections used; authors state 'most metals will oxidise in sustained contact with oxygen, particularly when heated'; no anode oxidation outcome reported in the read text | SCHWERTHEIM2022 | Sec. 2 (thruster design, Fig. 3 description); abstract | L3 primary |
| Stainless steel anode cap; Rh and Cr proposed | SS anode cap shows visible oxidation; 'Rhodium, due to its reduced oxidation rates at high temperatures, and chromium, due to the conductive properties of its oxidation layer, both emerge as potentially viable alternative surface materials'; ~10,000 h target without significant performance loss | IPPL_WEB | web page, Fig. 1 and text | L5 web summary / proposal |
| Thoriated-tungsten cathode / copper anode | ThW cathode oxidation 'will rapidly passivate the cathode extinguishing the discharge'; Southampton pure-O2 run-times 'of only a few seconds' (text extraction garbled -> verify) | GABRIEL1993 | p.4-5 'MPD Operation with Oxygen as the Propellant' | L3 primary (scan) |
| Anode (generic) in O2 ion sources | 'build-up of an insulating oxide on the surface of the anode which will quickly reduce the current and extinguish the discharge'; remedies suggested: oxidation-resistant alloy 'Inconel x750' or 'Hastealloy', or 'an anode coated with a conducting layer of IrO2 (or perhaps ruthenium oxide rhenium oxide)', or an iridium anode ('prohibitively expensive') | GABRIEL1993 | p.5 right column (citing Guarnieri et al. 1988) | L4 secondary/suggestion |
| SrO on Pt cathode vs Ta wire | lifetime 63 h for SrO-on-Pt cathode vs 3 to 5 h for 1.5 mm Ta wire | GABRIEL1993 | p.5 (citing Hentschel & Henke 1992) | L4 second-hand |
| Thoria-coated iridium filament | lifetimes 'of the order of 1000+ hours at 0.2 A/cm2' quoted | GABRIEL1993 | p.5 (citing Guarnieri et al. 1988) | L4 second-hand |
| RAM-HET (anode material not stated) | 'a certain amount of xenon (~1.5 mg/s) has always been necessary to prevent the flame out'; collector = stainless steel cone | SITAEL2017 | p.7 (Fig. 8 text); p.4 collector | L3 primary |
| PPS1350 anode | ~314 h before anode-oxidation flame-outs | ANDREUSSI2022 | p.24 (repo record) | L5 review, second-hand |
| Titanium vs graphite RIT grids | Ti grids lower erosion than graphite on O2 (repo record) | ANDREUSSI2022 | repo R3 thread | L5 second-hand |
| Pyrolytic graphite (PG) / HOPG / diamond | erosion yield PG 0.61-1.2 and 1.2 (x1e-24 cm3/atom); HOPG 1.04-1.2, 1.2-1.7, 1.2; diamond 0.0000+/-0.000023 and 0.021; 'erosion yield is not a meaningful number for ... most metals ... where the majority of the oxidation products are non-volatile' | BANKS2004 | Table 1 and text following Fig. 7 | L2 flight data compilation |
| Pyrolytic graphite | erosion yield 4.15 +/- 0.45 E-25 cm3/atom | MCCARTHY2010 | erosion-yield error table, PG row | L2 flight data |
| TZM (Mo alloy) | measured Mo mass flux 6.04E-5 (400 C, max), 4.10E-3/2.73E-3 (500 C), 3.62E-2 (550 C), 1.62E-1 (599 C, 24 h), 3.43 (650 C), 2.62E+1 (700 C), 3.82E+2 (750 C), 2.42E+3 (800 C) g/(m2 h); measured recession 3.85E-1 mm/h at 800 C; 'volatilization process is dominated by MoO3 above 550 C' | SMOLIK2000 | Table 2 p.4; Abstract | L2 primary lab data |
| Ir, IrRh10, IrRh25, IrRh40, Rh | weight loss: Ir 53.69 %, IrRh10 15.90 %, IrRh25 9.39 %, IrRh40 0.63 %; Rh mass gain 2.73 % | ZHAO2019 | Table 1 | verify |
| Rh, Pt, Ir, Ru, Os | linear weight-loss rates Rh 6.8e-3, Pt 9.6e-3, Ir 3.1, Ru 1.2e2, Os 1.2e3 | PGM1400_SNIPPET | snippet; original table not seen | verify |
| INCONEL alloy 601 (Ni-Cr-Al) | 'resistance to oxidation at temperatures up to 2200 F (1200 C)'; cyclic data in Figs. 9-11 (1095, 1150, 1200 C) | SMC_IN601 | p.8-9 'Oxidation', Figs. 9-11 | L2 manufacturer |
| INCONEL alloy 600 vs Type 304/309 | comparison of weight loss in cyclic oxidation (15 min heat / 5 min cool) in Fig. 11 | SMC_IN600 | 'High-Temperature Applications', Fig. 11 | L2 manufacturer |
| AISI 316L (wrought vs SLM) | parabolic constant 1.54e-12 (wrought) vs 1.73e-13 (SLM) g2 cm-4 s-1 | SS316L_SLM2020 | abstract (snippet) | verify |
| TiN (CVD powder) | oxidation onset temperature 640 C (highest of TiN, Ti(C,N), TiC) | TIN_CVD2020 | abstract (snippet) | verify |
| ZrN (CVD) | full oxidation of ZrN at ~670 C | ZRN_COAT2021 | abstract (snippet) | verify |
| Nuclear graphite | 400 and 500 C rates 'too low to measure confidently'; 0.51 (700 C), 2.89 (800 C), 8.8 (1000 C), 13.8 (1200 C) mg/min | THEODOSIOU2017 | Results section | verify |
| Hafnium cathode | distinct erosion features by gas; Hf/Zr chosen in O-containing plasma cutting because their oxides are stable/high-melting | HF_ARC_SNIPPET | abstract (snippet) | verify |

## Gaps
- No published anode temperature for any O-bearing Hall test (Cifali 2011, Imperial, SITAEL) - oxidation data cannot be mapped to temperature.
- No published anode-resistance or mass-change measurement vs hours for any O-bearing Hall anode; only qualitative ('rusty', 'mostly preserved', 20-30 min for W).
- PPS1350 anode material still unknown; 314 h flame-out datum remains second-hand (Andreussi 2022 of Cifali 2012; Cifali 2012 not accessed).
- TEJEDA2023 full text (anode section, test hours, Rh/Cr claim, 316L grade) not accessed (paywall/403).
- Bayliss & Knoll IEPC-2025 WET-HET plasma-material interaction study not accessed (may contain the best O2-anode data).
- No evidence for N2/O2 mixtures (nitridation + oxidation) on any candidate; all Imperial data are pure O2 (+ H2 cathode).
- No coating (Rh, Pt, Cr, IrO2) has been tested as a Hall anode in O plasma in any accessed source.
- Conductivity of oxide scales (Cr2O3, Al2O3, TiO2, NiO) at anode temperature not sourced (Wang et al. 1995 not accessed).
- PGM 1400 C loss rates and 316L/TiN/ZrN numbers are search-snippet level (verify).
- No Chinese, Japanese or Kurchatov/Dukhopelnikov anode-material data found (Dukhopelnikov AIP Conf Proc 2318, 040006 on TAL with air - abstract only, no material data seen).
- Haynes datasheets (230/214 oxidation tables) blocked (403); W oxidation numbers not sourced from a primary document.

## Owner questions
- OQ-R8-1: Accept 316L as the H-1 baseline anode with the recorded limitation (lab-scale, pure-O2, hours, degrades at higher power), pending coupon results?
- OQ-R8-2: Which of R8-C01..C09 go on AOL-EX-02 / AOL-WC-02 coupons, and should coupons be electron-collecting (biased) rather than floating?
- OQ-R8-3: Authorize acquisition (legitimate access, owner channel) of Tejeda & Knoll 2023 full text, Bayliss & Knoll IEPC-2025, Cifali 2012 (PPS1350 endurance) and Wang et al. 1995?
- OQ-R8-4: Set the anode thermal design target (H2-5 gives no sourced anode limit) so that oxidation evidence can be read at a temperature?
- OQ-R8-5: Include a bare-W negative control coupon to demonstrate that the resistance-rise measurement detects the known failure?

## Sources
- **CIFALI2011**: Cifali G., Misuri T., Rossetti P., Andrenucci M., et al., 'Experimental characterization of HET and RIT with atmospheric propellants', IEPC-2011-224, Wiesbaden, 2011. https://electricrocket.org/IEPC/IEPC-2011-224.pdf (full text read (open PDF))
- **TEJEDA2023**: Tejeda J.M., Knoll A., 'An oxygen-fuelled Hall Effect Thruster: Channel length, ceramic walls and anode material experimental analyses', Acta Astronautica 203 (2023) 268-279, doi:10.1016/j.actaastro.2022.11.055. https://ui.adsabs.harvard.edu/abs/2023AcAau.203..268T/abstract (full text NOT accessed (ScienceDirect/ResearchGate 403); abstract content only via search-engine snippets -> verify)
- **TEJEDA2024**: Tejeda J.M., Potrivitu G.-C., Rosati Azevedo E., Moloney R., Knoll A., 'Experimental demonstration of a water electrolysis Hall Effect Thruster (WET-HET) operating with a hydrogen cathode', Acta Astronautica 219 (2024) 542-554, doi:10.1016/j.actaastro.2024.03.043. https://www.imperial.ac.uk/bitstreams/ab3884e8-130c-4451-9d20-31b60b8607a9/download (full text read (Imperial Spiral open copy))
- **MUNOZTEJEDA2024**: Munoz Tejeda J.M., Schwertheim A., Moloney R., Knoll A., Saryczew J., 'First end-to-end technological demonstration of a water electrolysis Hall effect thruster operating with a water electrolyser', IEPC 2024, Toulouse. https://spiral.imperial.ac.uk/server/api/core/bitstreams/e2315fb4-4be7-45a4-a754-2d6433696df5/content (full text read (open))
- **SCHWERTHEIM2022**: Schwertheim A., Knoll A., 'Experimental investigation of a water electrolysis Hall effect thruster', Acta Astronautica 193 (2022) 607-618, doi:10.1016/j.actaastro.2021.11.002. https://spiral.imperial.ac.uk/server/api/core/bitstreams/656ff833-cdee-470c-b3fc-381134a67f96/content (accepted manuscript read (open))
- **IPPL_WEB**: Imperial Plasma Propulsion Laboratory, 'Oxidation and erosion reduction methods in water-fuelled HETs' (research web page; cites Bayliss F., Knoll A., IEPC 2025 plasma-material interaction study of WET-HET). https://www.imperial.ac.uk/a-z-research/plasma-propulsion-lab/research/oxidation-and-erosion-reduction-methods-in-water-fuelled-hets/ (web page read; Bayliss & Knoll IEPC-2025 paper NOT accessed)
- **GABRIEL1993**: Gabriel S.B., Wood N.J., Roberts G.T., Tatnall A.R.L., 'Atomic oxygen simulation using MPD thruster technology', IEPC-93-167. https://electricrocket.org/IEPC/IEPC1993-167.pdf (full text read (scan; two-column layout partly garbled in text extraction))
- **ANDREUSSI2022**: Andreussi T. et al. 2022 ABEP review (as recorded in repo lane 17 EV-W2 and docs/procurement/web_track_v1/threads/R3_materials.md). (repo record) (second-hand via repo; not re-read here)
- **SITAEL2017**: SITAEL/Andreussi et al., 'Development and experimental validation of a Hall effect thruster RAM-EP concept', IEPC-2017-377. https://electricrocket.org/IEPC/IEPC_2017_377.pdf (full text read (grep for anode/oxidation/material))
- **BANKS2004**: Banks B.A., de Groh K.K., Miller S.K., 'Low Earth Orbital Atomic Oxygen Interactions With Spacecraft Materials', NASA/TM-2004-213400. https://ntrs.nasa.gov/api/citations/20040191331/downloads/20040191331.pdf (full text read)
- **MCCARTHY2010**: McCarthy C.E. et al., 'MISSE 2 PEACE Polymers Experiment Atomic Oxygen Erosion Yield Error Analysis', NASA/TM-2010-216903. https://ntrs.nasa.gov/api/citations/20100040422/downloads/20100040422.pdf (full text read)
- **SMOLIK2000**: Smolik G.R., Petti D.A., Schuetz S.T., 'Oxidation, Volatilization, and Redistribution of Molybdenum from TZM Alloy in Air', INEEL/EXT-99-01353, Jan 2000. https://www.osti.gov/servlets/purl/752007 (full text read)
- **ZHAO2019**: Zhao S. et al., 'Microstructure and Isothermal Oxidation of Ir-Rh Spark Plug Electrodes', Materials 12(19) (2019) 3226, doi:10.3390/ma12193226. https://pmc.ncbi.nlm.nih.gov/articles/PMC6804067/ (read via fetch-tool summary of PMC full text; table values should be re-checked -> verify)
- **PGM1400_SNIPPET**: Linear weight-loss rates of Rh, Pt, Ir, Ru, Os at 1400 C in slowly moving air; origin appears to be Krier C.A., Jaffee R.I., 'Oxidation of the platinum-group metals', J. Less-Common Metals (1963) (ScienceDirect 0022508863900559) -> attribution verify. https://www.sciencedirect.com/science/article/abs/pii/0022508863900559 (search-engine snippet only; source page 403 -> verify)
- **SMC_IN601**: Special Metals, 'INCONEL alloy 601' technical bulletin. https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-601.pdf (read)
- **SMC_IN600**: Special Metals, 'INCONEL alloy 600' technical bulletin. https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-600.pdf (read)
- **SS316L_SLM2020**: 'Impact of Selective Laser Melting Additive Manufacturing on the High Temperature Behavior of AISI 316L Austenitic Stainless Steel', Oxidation of Metals / High Temperature Corrosion of Materials (2020), doi:10.1007/s11085-020-10005-8. https://link.springer.com/article/10.1007/s11085-020-10005-8 (search snippet of abstract only (Springer login redirect) -> verify)
- **TIN_CVD2020**: 'In-situ investigation of the oxidation behavior of powdered TiN, Ti(C,N) and TiC coatings grown by chemical vapor deposition', Surface & Coatings Technology (2020), pii S0257897220313037. https://www.sciencedirect.com/science/article/pii/S0257897220313037 (search snippet of abstract only (403) -> verify)
- **ZRN_COAT2021**: 'In-Situ Investigation of the Oxidation Behaviour of Chemical Vapour Deposited Zr(C,N) Hard Coatings Using Synchrotron X-ray Diffraction', Coatings 11(3) (2021) 264, doi:10.3390/coatings11030264. https://www.mdpi.com/2079-6412/11/3/264 (search snippet only (403) -> verify)
- **THEODOSIOU2017**: Theodosiou A., Jones A.N., Marsden B.J., 'Thermal oxidation of nuclear graphite: A large scale waste treatment option', PLoS One 12(8) (2017) e0182860, doi:10.1371/journal.pone.0182860. https://pmc.ncbi.nlm.nih.gov/articles/PMC5549958/ (read via fetch-tool summary -> values re-check recommended)
- **HF_ARC_SNIPPET**: 'Unique erosion features of hafnium cathode in atmospheric pressure arcs of air, nitrogen and oxygen' (ResearchGate 304479718) and related plasma-arc-cutting literature. https://www.researchgate.net/publication/304479718 (search snippet only -> verify)
- **WANG1995**: Wang C., Akbar S., Chen W., Patton V., 'Electrical properties of high-temperature oxides, borides, carbides, and nitrides', J. Mater. Sci. 30 (1995) 1627-1641 (cited by SCHWERTHEIM2022 ref [42]). (paywalled; not accessed) (not accessed)
- **GUARNIERI1988**: Guarnieri C.R. et al., J. Vac. Sci. Technol. A6(4) (1988) 2582-2583 (cited by GABRIEL1993 ref [13]). (not accessed) (second-hand via GABRIEL1993)
- **HENTSCHEL1992**: Hentschel R., Henke D., Rev. Sci. Instrum. 63(4) (1992) 2590-2594 (cited by GABRIEL1993 ref [14]). (not accessed) (second-hand via GABRIEL1993)
