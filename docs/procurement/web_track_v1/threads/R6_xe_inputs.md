# R6 - evidence for TBD inputs of the parametric Xe ledger (2026-09-27)

Evidence only. No total Xe allocation is proposed; no scenario value is filled. Authoritative record: `R6_xe_inputs.json`.

## mdot_cathode (context for the A5 fixed 0.10 mg/s term; not changed)
- **0.2 mg/s** - MaSMi LUC (LaB6, sub-kW Hall class) 'normal cathode operation' after ignition with 2 A to a downstream anode; thruster runs used cathode flow fraction 2-7 % of anode flow, keeper off [CONVERSANO_US10919649, detailed description, heaterless-ignition and cathode I-V paragraphs; measured (test condition, not a minimum)]. Limits: a demonstration setpoint, not a spot-mode minimum; no 15,000 h demonstration at this flow
- **spot mode at I_D/mdot < ~1.5 A/sccm (i.e. <= ~15 A per mg/s); tested 2-6 sccm (0.197-0.590 mg/s), 1-4 A A/sccm** - AHC-3.2 heaterless featherweight BaO-type cathode, diode mode, Xe, ~1e-5 Torr [MOONEY_IEPC2019_695, Sec. III, p. 5-6, Fig. 3-4, Table 1; measured (lab)]. Limits: 0.10 mg/s (~1.02 sccm) is BELOW the tested range; applying 1.5 A/sccm at 0.10 mg/s (~1.5 A) is extrapolation, not evidence; BaO insert, not LaB6; diode, not thruster-coupled
- **0.02-0.1 of anode flow (range 2-7 % MaSMi; 5-10 % BHT-1500 datasheet text, verify locator) 1** - typical Hall-thruster cathode flow fractions [CONVERSANO_US10919649, thruster hot-fire paragraph; measured (practice)]. Limits: fraction-of-anode rules come from Xe-anode thrusters; ABEP cathode must also survive O-bearing plume
- Range/TBD: A5 0.10 mg/s stays the design target; open evidence for LaB6/BaO cathodes at 1-5 A places demonstrated normal/spot operation at >= ~0.2 mg/s; no located source demonstrates <= 0.10 mg/s spot mode at the multi-ampere current a 1-1.5 kW Hall needs
- Closes it: C-1 spot/plume boundary map (flow 0.05-0.3 mg/s x emission current at expected I_d) with thruster B-field and N2/air anode; then wear test at the chosen flow

## t_startup
- **360 s** - heated start: heater 5.5 A (<28 W) for 6 min, then 150 V keeper, 2 A limit ignites [CONVERSANO_US10919649, cathode I-V paragraph ('The heater was supplied with 5.5 A ... for 6 minutes'); measured (procedure)]. Limits: lab procedure; preheat for a flight profile may differ
- **[55, 120] s** - heaterless start: time from field emission to ignition, mean 82 s; 56 s at 300 mA keeper [CONVERSANO_US10919649, heaterless ignition paragraph; measured (30+ trials; 102 ignitions total)]. Limits: destructive to orifice plate; keeper 150-300 mA
- **240 s** - KM-5 life test: cathode heating time 4 min per cycle (W-Ba cathodes) [AKIMOV_KM5_EUCASS, Sec. 3.2 Life test; measured (procedure)]. Limits: Xe flow during heating not stated
- **[600, 200] s** - HC1 preheat ~600 s at ~45 W / ~200 s at ~60 W (already in repo AN-03) [MOONEY_IEPC2019_695, n/a - repo AN-03 pedrini_2017_iepc365; measured]. Limits: not new
- Range/TBD: heated LaB6 preheat 200-1200 s across sources (MaSMi 360 s, KM-5 240 s, HC1 200-600 s, JPL 1.5 cm 18-20 min); discharge-ignition dwell on Xe and duration before atmospheric transfer: NO SOURCE -> TBD
- Closes it: H-1/C-1 start sequence with logged per-phase Xe flow and time (preheat, keeper ignition, discharge ignition, dwell)

## mdot_startup
- **0.2 mg/s** - cathode Xe flow held during the 6 min heater preheat (MaSMi LUC) [CONVERSANO_US10919649, cathode I-V paragraph; measured (procedure)]. Limits: one lab procedure; 2x the A5 target
- **[2.0, 3.9] mg/s** - heaterless ignition flow (~10x normal), 0.98 mg/s steps [CONVERSANO_US10919649, heaterless ignition paragraph; measured]. Limits: big per-start cost
- **11 (10 anode + 1 cathode) mg/s** - HT5k ignition (already repo E09/AN-02) [CONVERSANO_US10919649, n/a - repo; measured]. Limits: not new; out of power class
- Range/TBD: derived per-start CATHODE Xe (arithmetic): heated preheat 360 s x 0.20 mg/s = 72 mg; at A5 0.10 mg/s = 36 mg; heaterless 55 s x 2.9 mg/s = 0.16 g to 120 s x 3.4 mg/s = 0.41 g (56 s x 2.5 = 0.14 g). ANODE ignition Xe for a ~1 kW-class thruster: TBD (Cifali/PPS1350 does not report it)
- Closes it: H-1 Xe discharge ignition flow and dwell measured at the H-1 accelerator; integrated Xe per start

## N_starts
- **4000 1** - KM-5 flight-unit requirement 'Number of on/off cycles' [AKIMOV_KM5_EUCASS, Table 1; requirement (developer spec)]. Limits: GEO station keeping, not VLEO duty
- **583 cycles in 1074 h (mean 1.84 h/cycle); QM 225 cycles / 554 h 1** - KM-5 in orbit to 2007-05-28; ground QM life+qual [AKIMOV_KM5_EUCASS, Sec. 4 / Sec. 3.2; measured]. Limits: not an ops concept for ABEP; ABEP firing 15,000 h at that rate would be ~8,100 starts (arithmetic only)
- **102 1** - MaSMi LUC heaterless ignitions without observable change [CONVERSANO_US10919649, detailed description; measured]. Limits: lab
- Range/TBD: TBD (ops concept + FDIR); published cycle counts 10^2-10^4 are hardware demonstrations/requirements, not mission start counts
- Closes it: VLEO ops concept (eclipse/duty cycling, anomaly restarts) and C-1 start-cycle qualification

## N_transitions / t_transition / mdot_transition
- Range/TBD: TBD - no open source reports a Xe-to-air transfer duration or Xe flow profile (Cifali 2011 'smooth transition', Andreussi IEPC-2022-435 'gradually'; ESA/SITAEL 2018 press: Xe 'replaced in stages' - no times)
- Closes it: H-1 Phase 1 transfer profile with logged Xe flow vs time

## t_fallback_max / mdot_fallback
- Range/TBD: TBD - no published ABEP concept found that specifies a Xe fallback duration or flow
- Closes it: owner/FDIR decision using SS-3; H-1 Xe reference point flow

## reserve_policy
- Range/TBD: TBD (owner, OD-XE-2); no new source; ESA 2 % residual already in mass_bom (OD-XE-4)
- Closes it: owner decision

## tank_model
- **<=3.5 kg dry for 1-7 L; Ti-6Al-4V shell; D 242 mm; L <=386 mm; MEOP NOT stated kg** - XS-XTA family, UNDER DEVELOPMENT [MTA_XS_XTA, datasheet; supplier datasheet (design, not qualified)]. Limits: MEOP blank so capacity is not derivable; dry mass is an upper bound
- **40/60/90/120 L: predicted structural mass 6.3/8.9/12.8/16.8 kg (table header 6.3-14.8 kg), max Xe 73/110/165/220 kg; MEOP 187 bar, burst x1.5 kg** - S-XTA family COPV (Ti liner, T800), UNDER DEVELOPMENT [MTA_S_XTA, datasheet drawing + table; supplier prediction]. Limits: internal inconsistency 14.8 vs 16.8 kg at 120 L kept
- **60 L, 11.7 kg dry, MEOP 187 bar, burst tested 456 bar kg** - S-XTA-60 COTS, flight heritage SGEO, AMOS 6 [MTA_S_XTA_60, datasheet; supplier datasheet (flight heritage)]. Limits: Xe capacity not on this sheet (family chart: 110 kg)
- **0.086 (40 L), 0.081 (60 L pred.) / 0.106 (60 L COTS 11.7/110), 0.078 (90 L), 0.067-0.076 (120 L) 1** - tankage fraction = dry/max Xe [MTA_S_XTA, derived here; inferred (arithmetic)]. Limits: out of applicability for 5-30 kg; fractions at full load only
- **2 L, 120 bar, CFRP on Al liner; system dry mass REQUIREMENT < 5 kg for ~3 kg Xe kg** - Satrec 300 W Hall XFS [KIM_IEPC2009_061, Sec. II requirements, Sec. II.D; requirement (design)]. Limits: requirement, not measured mass
- Range/TBD: TBD; the 5-30 kg Xe band (~3-18 L at 1.67-1.83 g/cm3) falls between XS-XTA (<=7 L, MEOP unknown) and S-XTA (>=40 L). Tankage fractions from 40-120 L tanks (0.067-0.106) are lower bounds in spirit, not transferable
- Closes it: supplier quotation for a ~5-20 L xenon tank at declared MEOP and max temperature, or a sourced sizing model

## m_regulator / m_valves / m_plumbing (integrated flow-control units)
- **< 0.974 kg** - Moog XFC: FCV + PFCV + latch valve, welded; 3-23 mg/s Xe; regulated inlet 2.4-2.8 bar (capability 186 bar); heritage AEHF, Psyche, PPE [MOOG_XFC, product page; supplier datasheet]. Limits: flow range 3-23 mg/s is far above 0.1 mg/s cathode; excludes the high-pressure regulator (PMU)
- **< 1.16 kg** - Bradford Flow Control Unit (proportional + solenoid isolation valves) [BRADFORD_FCU_SATSEARCH, listing; supplier listing]. Limits: flow range/pressure not stated
- **<= 0.8 kg incl. filter-getter; <= 23 W (filter-getter heater <= 17 W) kg** - KM-5 gas distribution unit: redundant lines, electromagnetic valves, thermal throttle, throttles, Ti filter-getter at ~750 C; inlet 2.5 bar [AKIMOV_KM5_EUCASS, Table 1, Sec. 2.3; developer spec (upper bound)]. Limits: needs upstream regulator (in the SK propulsion system)
- **450 x 380 x 220 mm module; dry < 5 kg incl. 2 L tank, bang-bang solenoid pairs, orifices, 3+ transducers, 240 cm3 accumulator, fill/vent valve kg** - Satrec XFS for 300 W Hall (anode 4-7 sccm, cathode 0-2 sccm) [KIM_IEPC2009_061, Sec. II; requirement]. Limits: no component masses
- Range/TBD: TBD; integrated flow control ~0.8-1.2 kg per unit (supplier upper bounds) but at higher flows; separate regulator, latch valves, transducers, filters and lines not found with masses in open sources
- Closes it: supplier data for a low-flow (0.05-15 mg/s) Xe feed: regulator/bang-bang PMU, latch valves, transducers, filter, fill/drain

## m_mounting_thermal
- Range/TBD: TBD; note supercritical Xe density is strongly temperature dependent, so tank thermal control is a sizing input (see NIST data)
- Closes it: thermal design + mount design

## Hardware mass data
- {"item": "Xe density (supercritical)", "values": {"293.15K": {"120bar": 1.9536, "150bar": 2.0455, "187bar(interp)": "~2.12"}, "300K": {"120bar": 1.858, "150bar": 1.9695, "190bar": 2.0725}, "323.15K": {"120bar": 1.4417, "150bar": 1.6735, "180bar": 1.8075, "190bar": 1.8424}}, "unit": "g/cm3", "source_id": "NIST_WEBBOOK_XE", "evidence_class": "model-derived (reference EOS)", "note": "the '1.6-1.9 g/cm3 at ~150 bar' band corresponds to 323 K vs 300 K; S-XTA 73 kg/40 L = 1.83 g/cm3 at 187 bar consistent with ~320-325 K design point (inferred). Volume for 5-30 kg at 1.67-1.83 g/cm3: ~2.7-18 L (arithmetic)."}
- {"item": "MT Aerospace XS-XTA 1-7 L", "mass_kg": "<=3.5", "status": "under development", "source_id": "MTA_XS_XTA"}
- {"item": "MT Aerospace S-XTA 40-120 L", "mass_kg": "6.3-16.8", "xe_max_kg": "73-220", "meop_bar": 187, "status": "under development", "source_id": "MTA_S_XTA"}
- {"item": "MT Aerospace S-XTA-60 COTS", "mass_kg": 11.7, "volume_L": 60, "meop_bar": 187, "status": "flight heritage", "source_id": "MTA_S_XTA_60"}
- {"item": "MT Aerospace L-XTA 600-900 L", "mass_kg": "68-85", "status": "under qualification", "source_id": "MTA_L_XTA", "note": "repo AN-05 ESA page: <104 kg for 900 L"}
- {"item": "Moog XFC", "mass_kg": "<0.974", "source_id": "MOOG_XFC"}
- {"item": "Bradford FCU", "mass_kg": "<1.16", "source_id": "BRADFORD_FCU_SATSEARCH"}
- {"item": "KM-5 GDU incl. filter-getter", "mass_kg": "<=0.8", "source_id": "AKIMOV_KM5_EUCASS"}
- {"item": "Busek BHT-1500 cathode", "mass_kg": 0.3, "source_id": "BUSEK_BHT1500_DS", "note": "cathode, not Xe-path hardware"}

## Unresolved
- No open source demonstrates <= 0.10 mg/s LaB6 spot mode at multi-ampere Hall current (C-1 must).
- Anode ignition Xe flow/dwell for a ~1 kW Hall, and any Xe-to-air transfer duration: not published in accessed sources.
- Fallback Xe durations in ABEP concepts: none found.
- No qualified xenon tank datasheet located in the 10-40 L range; XS-XTA MEOP blank.
- Separate masses of regulator, latch valves, pressure transducers, filters, lines: not found in open datasheets.
- Not retrieved (bot/captcha/403, not bypassed): Potrivitu et al. low-current LaB6 (ResearchGate; search snippet claims 0.03 mg/s Kr at 0.75 A - NOT entered), SITAEL hollow-cathode page (captcha), IOP JPCS 2292/012003 Xe COPV (bot check), Astra ASE datasheet (404).
- Patent text says 'conditioning of the BaO-W insert' in the heated-start paragraph although the LUC is described as LaB6 elsewhere - verify which insert the 6 min / 0.20 mg/s procedure used.

## Owner questions
- Heated vs heaterless C-1: heaterless per-start Xe (0.14-0.41 g cathode only) is 2-6x the heated preheat (0.036-0.072 g) - which does the owner baseline?
- Is Xe flow during preheat booked (MaSMi practice flows Xe during heating)? Affects OD-XE-1 overlap.
- Accept tank sizing at a stated max storage temperature (density 1.67 g/cm3 at 323 K/150 bar vs 1.97 at 300 K)?
- Is a filter-getter (KM-5 style, <=17 W) in the Xe cathode line in scope, given O-sensitivity of the emitter?
- Request supplier quotations (tank 5-20 L; low-flow PMU/FCU) - procurement contact is owner's call (no contact by this lane).

## Sources (accessed 2026-09-27)
- CONVERSANO_US10919649: R. W. Conversano, D. M. Goebel, I. Katz, R. R. Hofer, 'Low-power Hall thruster with an internally mounted low-current hollow cathode', US 10,919,649 B2 (Caltech/JPL; filed 2020-06-17) - MaSMi-DM and its low-current cathode (LUC) <https://patents.google.com/patent/US10919649B2/en> (open full text (Google Patents HTML; USPTO PDF is image-only))
- MOONEY_IEPC2019_695: M. M. Mooney, M. Baird, K. Lemmer, 'Featherweight Heaterless Hollow Cathode Characterization', IEPC-2019-695 <https://electricrocket.org/2019/695.pdf> (open full text)
- AKIMOV_KM5_EUCASS: V. N. Akimov et al., 'Development of KM-5 Hall effect thruster and its flight testing onboard GEO spacecraft Express-A4', 2nd EUCASS <https://www.eucass.eu/component/docindexer/?task=download&id=2724> (open full text)
- KIM_IEPC2009_061: Y. Kim et al. (Satrec Initiative / KAIST), 'Development of Xenon feed system for a 300-W Hall-Thruster', IEPC-2009-061 <https://electricrocket.org/IEPC/IEPC-2009-061.pdf> (open full text)
- MTA_XS_XTA: MT Aerospace, 'XS-XTA / 1-7 l Family Xenon Tank' datasheet (tank catalogue p. 11; PDF dated 2019-06-05), status UNDER DEVELOPMENT <https://www.mt-aerospace.de/files/mta/tankkatalog/XS-XTA.pdf> (open datasheet)
- MTA_S_XTA: MT Aerospace, 'S-XTA / 40-120 l Family Xenon Tank' datasheet (catalogue p. 12), status UNDER DEVELOPMENT <https://www.mt-aerospace.de/files/mta/tankkatalog/S-XTA.pdf> (open datasheet)
- MTA_S_XTA_60: MT Aerospace, 'S-XTA-60 Xenon Tank - COTS' datasheet (catalogue p. 8; heritage SGEO, AMOS 6) <https://www.mt-aerospace.de/files/mta/tankkatalog/S-XTA-60.pdf> (open datasheet)
- MTA_L_XTA: MT Aerospace, 'L-XTA / 300-900 Family' datasheet (catalogue p. 13) <https://www.mt-aerospace.de/files/mta/tankkatalog/L-XTA.pdf> (open datasheet)
- NIST_WEBBOOK_XE: NIST Chemistry WebBook, SRD 69, Thermophysical Properties of Fluid Systems, xenon (C7440633) isotherms 293.15/300/323.15 K, 60-200 bar (reference equation of state) <https://webbook.nist.gov/cgi/fluid.cgi?Action=Data&Wide=on&ID=C7440633&Type=IsoTherm&Digits=5&PLow=60&PHigh=200&PInc=10&T=300&TUnit=K&PUnit=bar&DUnit=g%2Fml> (open database)
- MOOG_XFC: Moog, 'Xenon Flow Controller (XFC)' product page <https://www.moog.com/products/propulsion/space-propulsion/spacecraft-propulsion/systems-and-subsystems/xenon-flow-controller.html> (open web page (via fetch-tool summary; quote verbatim before use))
- BRADFORD_FCU_SATSEARCH: Bradford Space, 'Flow Control Unit' listing on satsearch <https://satsearch.co/products/bradford-flow-control-unit> (open marketplace listing (datasheet behind request form, not requested))
- BUSEK_BHT1500_DS: Busek, BHT-1500 datasheet v1.0 (Aug 2021) <https://satcatalog.s3.amazonaws.com/components/941/SatCatalog_-_Busek_-_BHT-1500_-_Datasheet.pdf> (open datasheet)
