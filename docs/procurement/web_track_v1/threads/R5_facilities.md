# R5 - Candidate facilities and metrology labs for the H-1 programme (published information only)

Generated 2026-09-27 against repo commit 782f900. No lab or person was contacted. No captcha or login was bypassed. Values that come only from a search snippet are marked *verify*. Nothing here asserts that any facility is available or accessible.

## Requirement context

- Repository planning numbers (REQ-FAC-01, model-derived): S_eff = 66,818 (N2) / 58,466 (O2) L/s per mg/s at 1.0e-5 Torr; 13,364 / 11,693 at 5.0e-5 Torr. At 3.2 mg/s total: ~214,000 L/s (N2, 1e-5 Torr) to ~42,800 L/s (N2, 5e-5 Torr); cathode flow adds load. T-PB-MAX is TBD (owner, LOCK-1).
- Test gas: N2/O2 (O2 mass fraction up to 0.60) up to ~3.2 mg/s plus Xe; P_d ~1-1.35 kW; T 12-25 mN
- Thrust: REQ-HW-01: 0.50 % per-reading repeatability (n=4) ~60 uN at 12 mN; absolute 1 % (1 sigma) for the gate

## Screening table

| facility | country | categories | accreditation | score-bearing potential |
|---|---|---|---|---|
| ISRO LPSC electric-propulsion test facility (Valiamala and/or Bengaluru) | India | vacuum_facility, thrust_measurement, plume_diagnostics | not found: not found | unknown |
| IIST plasma / ionospheric-plasma-simulator facility | India | vacuum_facility, plume_diagnostics | not found: not found | unknown |
| Bellatrix Aerospace Spacecraft Propulsion Research Laboratory (SID-IISc) and Peenya facility | India | vacuum_facility | not found: not found | unknown |
| Institute for Plasma Research (IPR) / FCIPT | India | vacuum_facility | not found: not found | unknown |
| IIT Kanpur / IIT Madras / IIT Bombay / IISc departmental labs | India | vacuum_facility | not found: not found | unknown |
| SITAEL IV10 (and IV4) vacuum facilities | Italy | vacuum_facility, thrust_measurement, plume_diagnostics, air_breathing_heritage | not found: not found | unknown |
| ESA Propulsion Laboratory (EPL), ESTEC | Netherlands (ESA) | vacuum_facility, thrust_measurement, plume_diagnostics | not found: not found | unknown |
| University of Michigan PEPL: LVTF and Alternative Propellant Test Facility | USA | vacuum_facility, thrust_measurement, plume_diagnostics | not found: not found | unknown |
| Stanford (Cappelli group) ECHT and PPPL HTX (Raitses) air-breathing ExB work | USA | air_breathing_heritage | not found: not found | unknown |
| IRS Stuttgart (ABEP IPT) and Chinese/Japanese/Russian ABEP groups | Germany / China / Japan / Russia | air_breathing_heritage | not found: not found | unknown |
| CSIR-National Physical Laboratory (NMI of India) - Mass Metrology Section / CFCT | India | mass_metrology, thrust_calibration_traceability | CIPM-MRA (NMI; KCDB CMCs) - NABL certificate not applicable/not found: not found | score_bearing_possible |
| CMTI Metrology Laboratory (Central Manufacturing Technology Institute) | India | surface_profilometry, dimensional_metrology | NABL: CC-2153 (2018-2020, historical - verify current) | score_bearing_possible |
| CSIR-NAL Metrology and Calibration Lab (APMF) | India | dimensional_metrology | NABL: CC-2704 (historical - verify) | unknown |
| Commercial NABL testing labs offering SEM-EDS / XPS (unidentified) | India | sem_eds, xps | NABL: not found | unknown |

## Facilities

### ISRO LPSC electric-propulsion test facility (Valiamala and/or Bengaluru) (Thiruvananthapuram (Valiamala) / Bengaluru, India)

- Claimed: large vacuum chamber established under the High Thrust Electric Propulsion project. Value: no dimensions/pumping published. Source: [S-LPSC-ADV]
- Claimed: Thrust Measurement System and Laser Induced Fluorescence system for plume analysis 'being developed'. Value: no specs. Source: [S-LPSC-ADV]
- Claimed: 1000 h life test of 300 mN SPT at 5.4 kW in a chamber simulating space vacuum (Xe); liner erosion monitored. Value: completed 27 Mar 2025; test site and p_b not stated. Source: [S-ISRO-1000H]
- Claimed: thrust-measurement replacement tender exists on ISRO e-procurement. Value: title only; content not accessible. Source: [S-ISRO-EPROC]
- Claimed: in-house modelling of chamber/background-pressure effects on Hall plumes. Value: project description only. Source: [S-ISTI-LPSC]
- Accreditation: not found. Scope: not found. Certificate: not found.
- Gas / O2 notes: Only Xe operation published. A 5.4 kW Xe-capable chamber is likely large, but N2/O2 pumping speed, cryopanel temperature and O2-service (regeneration, ozone, backing-pump oil) are unpublished.
- Needs confirmation: chamber size, pumping type and speed for N2, O2 and Xe; base and operating p_b at 3.2 mg/s N2/O2 (+ cathode flow); gauge type/position/gas calibration (REQ-FAC-03); O2 compatibility and safety case (REQ-FAC-04); thrust stand range/resolution, in-situ calibration and traceability; ability to hold 0.5 % per-reading repeatability at 12-25 mN (REQ-HW-01); ExB/RPA/Faraday/RGA availability; whether a non-ISRO programme (DRDO TDF bidder) can use the facility at all
- Potential: **unknown**. Highest-capability Indian Hall facility by inference (5.4 kW SPT life test), but no published specification, no accreditation evidence and no evidence of third-party access.
- Access realism: Strategic ISRO facility; access for a private DRDO-TDF bidder is unestablished (owner's channel only; no contact made). No export-control barrier (domestic).

### IIST plasma / ionospheric-plasma-simulator facility (Thiruvananthapuram, India)

- Claimed: collaborates in LPSC-led HTEP on design/testing of diagnostic tools for SPT characterisation. Value: -. Source: [S-IIST-WEB]
- Claimed: 'India's only ionospheric plasma simulator'; in-house back-diffusion plasma source and ion-beam source; ion-beam deflector for probe calibration. Value: no chamber dimensions, pumping or p_b. Source: [S-IIST-WEB]
- Accreditation: not found. Scope: not found. Certificate: not found.
- Gas / O2 notes: Unknown; gas lines mentioned only generically.
- Needs confirmation: whether any chamber can take a ~1-1.35 kW Hall thruster at 3.2 mg/s N2/O2; pumping speed per gas and p_b; thrust stand existence; diagnostics inventory (DISCRIMINATING_EXPERIMENTS.md Sec. 10 question list)
- Potential: **unknown**. Diagnostic-development role published; no evidence of a Hall-on thrust facility meeting REQ-FAC-01. Plausible for probe calibration / S3 source bench (engineering) subject to specs.
- Access realism: Academic (DoS institute); the repository already carries an IIST discussion package (lane_37). Access is the owner's channel.

### Bellatrix Aerospace Spacecraft Propulsion Research Laboratory (SID-IISc) and Peenya facility (Bengaluru, India)

- Claimed: 'ultra-high vacuum facility' at the Spacecraft Propulsion Research Laboratory set up at SID-IISc; Hall thruster test 'according to ISRO and ESA standards' (Xe). Value: no specs. Source: [S-INC42-BELLATRIX]
- Claimed: vacuum-chamber thruster testing facilities at Peenya; founder claim 'We and ISRO are the only two people to have testing facilities for thrusters in India'. Value: no specs. Source: [S-PRINT-BELLATRIX]
- Claimed: ARKA Hall thrusters; Project 200 ultra-low-orbit satellite. Value: -. Source: [S-WIKI-BELLATRIX]
- Accreditation: not found. Scope: not found. Certificate: not found.
- Gas / O2 notes: Xe only published; low-power (microsatellite) thrusters imply chamber sizing for ~1 mg/s-class Xe - likely far below 3.2 mg/s N2/O2 needs (inference, verify).
- Needs confirmation: chamber size/pumping/p_b per gas; thrust stand specs; O2 service; conflict of interest: Bellatrix announced a VLEO 'Project 200' satellite (potential competitor) - data custody / blinding (MS-G-05) and IP implications
- Potential: **unknown**. Private facility, no published specs or accreditation.
- Access realism: Commercial; possible competitor in VLEO. Owner's channel only.

### Institute for Plasma Research (IPR) / FCIPT (Gandhinagar, India)

- Claimed: 'Plasma Thruster Technology' listed among plasma applications; UHV core competence. Value: no specs. Source: [S-IPR-FAC]
- Accreditation: not found. Scope: not found. Certificate: not found.
- Gas / O2 notes: Unknown.
- Needs confirmation: any Hall-capable chamber, pumping, thrust stand; low-energy ion-beam erosion facility (search snippet claim for VSSC materials; unverified)
- Potential: **unknown**. Only a capability heading found. A search-engine summary claiming IPR develops the TDS-01 300 mN thruster contradicts Wikipedia/ISRO (LPSC is the developer) and is NOT used.
- Access realism: DAE institute; owner's channel.

### IIT Kanpur / IIT Madras / IIT Bombay / IISc departmental labs (various, India)

- Claimed: IIT Kanpur propulsion lab lists a pulsed plasma thruster facility only. Value: no specs. Source: [S-IITK-PROP]
- Accreditation: not found. Scope: not found. Certificate: not found.
- Gas / O2 notes: Unknown.
- Needs confirmation: no published Hall-capable chamber found for IIT Madras, IIT Bombay or IISc departments (search 2026-09-27)
- Potential: **unknown**. No published Hall-on facility evidence found.
- Access realism: Academic.

### SITAEL IV10 (and IV4) vacuum facilities (Pisa, Italy)

- Claimed: IV10: inner diameter 5.4 m, internal length 6 m, pumping capability 4.2e5 l/s (gas not stated). Value: p_b below 2.5e-5 mbar (Leybold ITR90, 3 m downstream) throughout N2/O2 testing. Source: [S-AETHER-IEPC2022]
- Claimed: Nov 2021 test of HT5k DM2 on 0.56N2+0.44O2 at 5-7 mg/s anode flow, 225-375 V; cathode on Xe or pure N2. Value: thermal and discharge stability demonstrated. Source: [S-AETHER-IEPC2022]
- Claimed: single-axis double-pendulum thrust stand, load cells, electromagnetic calibrator, calibration >= twice daily hot and cold. Value: estimated accuracy +/-3 mN. Source: [S-AETHER-IEPC2022]
- Claimed: 18 Faraday probes on a movable rack at 0.9 m, RPA (filter up to 600 V), movable triple Langmuir probe; 10 MHz I_d acquisition. Value: -. Source: [S-AETHER-IEPC2022]
- Claimed: IV4: diameter 2 m, length 4.2 m, thrusters up to 7 kW; thrust balance 1-200 mN, 0.1 mN resolution, 0.5 mN declared accuracy; RPA-Faraday rake, Langmuir, telemicroscopy for erosion, thermal cameras. Value: from search snippet of captcha-protected page - verify. Source: [S-SITAEL-TOOLS]
- Claimed: IV10 xenon pumped on ~30 K cryopanels; LN2 shroud; up to 35 kW; ~3e5 l/s order (another snippet). Value: verify. Source: [S-SITAEL-TOOLS]
- Claimed: RAM-EP (ESA) first air-breathing Hall firing 2018 with particle flow generator. Value: RAM-HET thrust 6+/-1 mN vs drag 26+/-1 mN. Source: [S-ABEP-REVIEW]
- Accreditation: not found. Scope: not found. Certificate: not found.
- Gas / O2 notes: Only facility found with published multi-hour N2/O2 Hall operation (O2 mass fraction 0.44 at 5-7 mg/s) at ~2.5e-5 mbar (~1.9e-5 Torr; gauge gas correction not stated). O2 fraction up to 0.60 and the regeneration/safety case need confirmation.
- Needs confirmation: pumping speed per gas (N2, O2, Xe) and p_b at 3.2 mg/s + cathode flow with gas-corrected gauges; O2 fraction 0.60 acceptance; thrust stand repeatability vs the 0.5 % per-reading / ~60 uN (12 mN) target; the published +/-3 mN accuracy of the IV10 stand is far coarser than needed; ExB and RGA availability (not listed); ISO/IEC 17025 or other accreditation; data release/raw data terms (MS-G-04)
- Potential: **unknown**. Best published match for gas and background pressure; thrust stand as published (+/-3 mN) is engineering-grade for the R_arch target; no accreditation found. Could become score-bearing only if its stand meets REQ-HW-01 in S1b and traceability is documented.
- Access realism: Commercial test services are marketed (page title). EU dual-use export rules and Italian/ESA programme priorities apply to foreign hardware/data; H-1 would be exported from India for test (Indian export control, DRDO TDF confidentiality) - owner/legal check. SITAEL is also an ABEP competitor (RAM-EP/AETHER) - custody/IP concern.

### ESA Propulsion Laboratory (EPL), ESTEC (Noordwijk, Netherlands (ESA))

- Claimed: modular cryopumping 200,000 l/s continuous Xe; facilities 1e-5 to 1e-9 mbar; Faraday probes, RPAs, customised thrust balances. Value: search snippet - verify. Source: [S-ESA-EPL]
- Accreditation: not found. Scope: not found. Certificate: not found.
- Gas / O2 notes: Xe-rated; N2/O2 speed not found.
- Needs confirmation: N2/O2 pumping and O2 service; eligibility of non-ESA-programme users
- Potential: **unknown**. Serves ESA's own division per its page; no route for a non-member-state commercial bidder found.
- Access realism: Low realism: EPL provides services to the ESA Propulsion division; India is not an ESA member state.

### University of Michigan PEPL: LVTF and Alternative Propellant Test Facility (Ann Arbor, MI, USA)

- Claimed: LVTF 6 m x 9 m, 13 cryopumps; upgraded effective Xe speed 500,000 l/s operating (600,000 cold flow); earlier configuration >100,000 l/s N2. Value: search snippet - verify. Source: [S-UM-LVTF]
- Claimed: Alternative Propellant Test Facility (2025): large charcoal-arrayed cryopump for high speed on N2, O2, H2; 'defense-relevant propellants'. Value: no numbers. Source: [S-UM-APTF]
- Accreditation: not found. Scope: not found. Certificate: not found.
- Gas / O2 notes: New facility explicitly targets N2/O2; charcoal arrays pumping O2 raise regeneration/ozone hazards (S-ULVAC-CRYO) - facility practice unknown.
- Needs confirmation: APTF numbers; O2 fraction limits; US export-control applicability for foreign Hall hardware and resulting data (EAR/ITAR classification - verify)
- Potential: **unknown**. Technically the most directly purpose-built N2/O2 facility found; access for a foreign defence-funded bidder is doubtful.
- Access realism: Low: US university with defence sponsors; export control and DRDO confidentiality - owner/legal only.

### Stanford (Cappelli group) ECHT and PPPL HTX (Raitses) air-breathing ExB work (Stanford CA / Princeton NJ, USA)

- Claimed: Extended-channel Hall thruster for air-breathing EP (ECHT). Value: J. Appl. Phys. 130, 053306 (2021). Source: [S-MARCHIONI2021]
- Claimed: e-beam generated ExB plasma for air-breathing. Value: IEPC-2022-443. Source: [S-PPPL-RAITSES]
- Accreditation: not found. Scope: not found. Certificate: not found.
- Gas / O2 notes: Facility specs not read.
- Needs confirmation: facility specs
- Potential: **unknown**. Listed for heritage only; the repository already uses the ECHT geometry (CLAUDE.md).
- Access realism: Low (US; export control).

### IRS Stuttgart (ABEP IPT) and Chinese/Japanese/Russian ABEP groups (Stuttgart / Lanzhou / Japan / Russia, Germany / China / Japan / Russia)

- Claimed: IRS: RF helicon IPT for ABEP (not Hall); no chamber pumping data found in the paper. Value: -. Source: [S-IRS-IPT]
- Claimed: Lanzhou Institute of Space Technology Physics: ABEP intake (2015); PPS1350 N2/O2 tests (ESA 2011-12); JAXA ABIE (ECR ion engine). Value: -. Source: [S-ABEP-REVIEW]
- Accreditation: not found. Scope: not found. Certificate: not found.
- Gas / O2 notes: Not established.
- Needs confirmation: IRS chamber specs (Hall-capable?)
- Potential: **unknown**. Heritage only; no Hall-on N2/O2 facility specification located.
- Access realism: China: unrealistic for a DRDO-TDF bid. Russia: sanctions/payment constraints (verify). Japan/Germany: possible only through formal collaboration; owner's channel.

### CSIR-National Physical Laboratory (NMI of India) - Mass Metrology Section / CFCT (New Delhi, India)

- Claimed: custodian of NPK-57; mass value transferred to weights 1 mg - 2000 kg. Value: -. Source: [S-NPL-MASS]
- Claimed: comparators: 1 kg vacuum (0.1 ug), robotic 6.1 g (0.1 ug readability), 1 kg (1 ug), 50 kg (0.1 mg). Value: -. Source: [S-NPL-MASS]
- Claimed: CMCs peer-reviewed and published in BIPM KCDB; quality system ISO/IEC 17025:2017 and ISO 17034; CIPM-MRA signatory; commercial calibration via CFCT. Value: -. Source: [S-NPL-CFCT]
- Accreditation: CIPM-MRA (NMI; KCDB CMCs) - NABL certificate not applicable/not found. Scope: mass 1 mg - 2000 kg (per page); E2 class specifically: verify KCDB entries. Certificate: not found.
- Gas / O2 notes: n/a
- Needs confirmation: KCDB CMC lines for the mass range of coupons/parts and for E2 weights; whether NPL calibrates the lab's microbalance on site or only the reference weights; turnaround
- Potential: **score_bearing_possible**. Top of the Indian traceability chain for OIML R111 E2 reference masses (MS-M-01) and for the thrust-stand calibration masses (REQ-HW-01 force traceability). It calibrates standards; the coupon weighing itself still needs a lab with the measurement in scope.
- Access realism: Public calibration service (CFCT). No contact made.

### CMTI Metrology Laboratory (Central Manufacturing Technology Institute) (Bengaluru, India)

- Claimed: NABL-accredited (ISO/IEC 17025) in dimensional metrology; calibrates roughness masters, optical flats, step gauges, gauge blocks. Value: search snippet of 503 page - verify. Source: [S-CMTI-MET]
- Claimed: nano-metrology facility: surface roughness and 3D topography by scanning probe microscopy. Value: verify. Source: [S-CMTI-MET]
- Claimed: listed in NABL 500 (31-Mar-2020) as 'Metrology Laboratory, CMTI', CC-2153, Mechanical, 31.08.2018-30.08.2020. Value: historical; current certificate not verified. Source: [S-NABL500-2020]
- Accreditation: NABL. Scope: Mechanical/dimensional (2020 directory); areal (ISO 25178) scope not found. Certificate: CC-2153 (2018-2020, historical - verify current).
- Gas / O2 notes: n/a
- Needs confirmation: current certificate and scope lines for roughness/areal topography and whether verification follows ISO 25178-700; step-height/fiducial profile measurement on wall rings as a TESTING service (not only calibration); C-1 orifice-diameter optical measurement (MS-M-05)
- Potential: **score_bearing_possible**. Government NABL-accredited dimensional lab with roughness-master capability: best Indian candidate found for MS-M-02 / MS-M-05, conditional on the scope covering the measurand.
- Access realism: Public-sector institute offering services.

### CSIR-NAL Metrology and Calibration Lab (APMF) (Bengaluru, India)

- Claimed: NABL 500 (2020): CC-2704, Mechanical, 28.05.2018-27.05.2020. Value: historical. Source: [S-NABL500-2020]
- Accreditation: NABL. Scope: Mechanical (details not read). Certificate: CC-2704 (historical - verify).
- Gas / O2 notes: n/a
- Needs confirmation: current scope; any SEM/EDS/XPS testing accreditation at NAL materials divisions
- Potential: **unknown**. Accredited calibration lab of unknown relevant scope.
- Access realism: CSIR lab; aerospace.

### Commercial NABL testing labs offering SEM-EDS / XPS (unidentified) (India, India)

- Accreditation: NABL. Scope: no scope document found listing ASTM E1508, light-element EDS/WDS or XPS (ISO 15472). Certificate: not found.
- Gas / O2 notes: n/a
- Needs confirmation: NABL directory search by discipline 'Chemical/Mechanical' with SEM-EDS / XPS scope lines; light-element method (windowless/thin-window SDD or WDS/EPMA) and its uncertainty for N, O, B, C; XPS energy-scale calibration per ISO 15472 (Cu 2p3/2, Au 4f7/2), sealed dry transfer
- Potential: **unknown**. Accredited XPS and quantitative light-element EDS are rare in any accreditation scheme; academic central facilities (IISc, IITs) have instruments but typically no ISO/IEC 17025 scope (verify). Without scope the data are engineering-only or 'semi-quantitative' per MS-M-03.
- Access realism: Procurement by owner after specification (A3).

## Gaps

- No Indian Hall-capable facility publishes chamber size, pumping speed per gas, or background pressure; REQ-FAC-01 cannot be screened for any Indian site from public data.
- No published N2/O2 pumping speed for any Indian chamber; cryopanel N2/O2 speed differs from Xe (lighter molecules; 20 K-class panels needed; charcoal arrays and O2 regeneration/ozone hazard per S-ULVAC-CRYO) - facility-specific data required.
- SITAEL IV10 is the only facility with published N2/O2 Hall operation near the needed flow and pressure; its published thrust accuracy (+/-3 mN) does not meet REQ-HW-01 as published.
- No ExB probe or calibrated RGA was found in any published facility description relevant here.
- No accredited (ISO/IEC 17025) scope found for XPS (ISO 15472) or quantitative light-element EDS (N, O, B) in India; ASTM E1508 excludes elements lighter than Na from routine quantification.
- NABL certificate numbers found are from the 2020 directory (expired dates); current status needs a manual NABL directory lookup (automated form query did not return a parsable record).
- No published B-field mapping (Hall-probe on stage) capability found at any candidate; gaussmeter calibration traceability source (NABL magnetic-field scope or NPL) not identified.
- Georgia Tech HPEPL, NASA GRC, ICARE/PIVOINE, JAXA and Chinese chambers not researched to source level (memory only - not recorded as facts).

## Owner questions

1. Is a foreign facility (e.g. SITAEL IV10) admissible for score-bearing Phase 2/3 data under DRDO TDF rules, export of H-1, and data custody given SITAEL/Bellatrix are ABEP/VLEO competitors?
2. Should the owner request ISRO LPSC facility specifications (chamber, per-gas pumping speed, O2 service, thrust stand) through official channels before T-PB-MAX is fixed at LOCK-1?
3. Which T-PB-MAX is acceptable if no reachable facility meets ~1e-5 Torr at 3.2 mg/s (~214,000 L/s N2)? Would 5e-5 Torr (~43,000 L/s) with the S5 slope reported be accepted?
4. Is Xe-only accreditation evidence acceptable, or must thrust-stand calibration masses be traced to CSIR-NPL/NABL E2 certificates (REQ-HW-01 'traceable calibration class' TBD)?
5. For XPS and light-element EDS, is an accredited-scope lab mandatory (then possibly a foreign accredited lab), or may an academic facility be used with results labelled semi-quantitative / engineering-only?
6. Should the engineering-only S1a checkout use a smaller domestic chamber (Bellatrix/IIST/academic) while score-bearing stages go to one facility meeting REQ-FAC-05?

## Source register

- **REPO-EXPPKG**: repository @782f900. <docs/architecture_comparison/experiment_package/experiment_package_v1.json (REQ-FAC-01..05, REQ-HW-01..08) and lock1_decision_brief_v1.json D-12>. Access: read.
- **REPO-METSPEC**: repository @782f900. <docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json + A3 decision OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json>. Access: read.
- **REPO-MINEXP-IIST**: repository @782f900. <docs/architecture_comparison/minimum_decisive_experiment/MINIMUM_DECISIVE_EXPERIMENT_DRAFT.md Sec. 12 (IIST published info) and docs/experiments/DISCRIMINATING_EXPERIMENTS.md Sec. 10>. Access: read.
- **S-LPSC-ADV**: LPSC official page. <https://www.lpsc.gov.in/advpropulsionsystems.html>. Access: full page read via fetch tool.
- **S-ISRO-1000H**: ISRO press release (1000 h life test, 300 mN SPT, 5.4 kW, 27 Mar 2025). <https://www.isro.gov.in/ISRO_successfully_conducts_1000hrs_life_test_of_SPT.html>. Access: full page read.
- **S-ISRO-EPROC**: ISRO e-procurement tender titled 'Tender for REPLACEMENT OF THRUST MEASUREMENT ...' (title from search result only). <https://eproc.isro.gov.in/viewDocumentPT?tenderId=LB202600003501>. Access: page returned 'Unauthorized Access' - not bypassed; title only.
- **S-ISTI-LPSC**: ISTI portal: LPSC Valiamala project on Hall thruster plume / chamber / background-pressure modelling. <https://www.indiascienceandtechnology.gov.in/research/modelling-plasma-and-its-interaction-vacuum-chamber-during-hall-thruster-firing>. Access: read.
- **S-IIST-WEB**: IIST Space Research page. <https://iist.ac.in/space-research>. Access: read.
- **S-INC42-BELLATRIX**: news, 28 May 2021. <https://inc42.com/buzz/bellatrix-aerospace-test-fires-indias-first-commercial-hall-thruster/>. Access: read.
- **S-PRINT-BELLATRIX**: news, 18 Sep 2024. <https://theprint.in/ground-reports/bellatrix-aerospace-is-rising-with-isro-nano-thrusters-are-its-big-game-now/2272660/>. Access: read.
- **S-WIKI-BELLATRIX**: Wikipedia (secondary). <https://en.wikipedia.org/wiki/Bellatrix_Aerospace>. Access: read.
- **S-IPR-FAC**: IPR research facilities page. <https://www.ipr.res.in/research-facilities>. Access: read (lists 'Plasma Thruster Technology', no specs).
- **S-IITK-PROP**: IIT Kanpur propulsion lab page. <https://www.iitk.ac.in/aero/propulsion-lab>. Access: read (pulsed plasma thruster only).
- **S-AETHER-IEPC2022**: Andreussi, Ferrato et al. (SITAEL), 'Characterization of an Atmospheric Propellant-fed Hall ...', IEPC-2022-435. <https://aether-h2020.eu/wp-content/uploads/2023/11/IEPC-2022-435.pdf>. Access: PDF text extracted and read (facility paragraph, diagnostics).
- **S-SITAEL-TOOLS**: SITAEL tools & testing services page. <https://www.sitael.com/electric-propulsion/tools-services/>. Access: NOT read: site served a captcha challenge (not bypassed); facility figures quoted from the search-engine snippet only - verify.
- **S-PHYS-RAMEP**: ESA/phys.org news on RAM-EP firing (2018). <https://phys.org/news/2018-03-world-first-air-breathing-electric-thruster.html>. Access: search snippet.
- **S-UM-LVTF**: Viges, Jorns, Gallimore, Sheehan, 'University of Michigan's Upgraded Large Vacuum Test Facility', IEPC-2019-653. <https://pepl.engin.umich.edu/pdf/IEPC-2019-653.pdf>. Access: search snippet only (numbers verify against the PDF).
- **S-UM-APTF**: UM Aerospace news 17 Nov 2025: PEPL Alternative Propellant Test Facility. <https://aero.engin.umich.edu/2025/11/17/the-plasmadynamics-and-electric-propulsion-laboratory-unveils-new-alternative-propellant-test-facility/>. Access: page 403 to fetch tool; content from search snippet only.
- **S-ESA-EPL**: ESA Propulsion Laboratory page (+ academia/researchgate 'ESA Propulsion Lab at ESTEC'). <https://technology.esa.int/lab/tec-m-epl-esa-propulsion-laboratory>. Access: search snippet only.
- **S-MARCHIONI2021**: Marchioni & Cappelli, J. Appl. Phys. 130, 053306 (2021) (ECHT, Stanford). <https://pubs.aip.org/aip/jap/article/130/5/053306/1079086/Extended-channel-Hall-thruster-for-air-breathing>. Access: metadata via search; publisher page 403.
- **S-PPPL-RAITSES**: Raitses et al., IEPC-2022-443, e-beam ExB plasma for air-breathing (PPPL). <https://htx.pppl.gov/publication/Conference/2022-06-IEPC-2022-%20443_Raitses_Electron-Beam%20Generated%20ExB%20Plasma%20for%20Air-Breathing.pdf>. Access: title only (search).
- **S-ABEP-REVIEW**: Review of air-breathing EP (J. Electric Propulsion 2022): PPS1350 on N2/O2 (ESA 2011-12), RAM-HET 6+/-1 mN, Lanzhou intake. <https://link.springer.com/article/10.1007/s44205-022-00024-9>. Access: search snippet.
- **S-IRS-IPT**: Romano et al., RF helicon IPT for ABEP (IRS Stuttgart). <https://arxiv.org/abs/2007.06397>. Access: PDF grepped: no chamber pumping data found.
- **S-NPL-MASS**: CSIR-NPL Mass Metrology section. <https://www.nplindia.in/index.php/science-technology/physico-mechanical-metrology/mass-metrology-section/>. Access: read.
- **S-NPL-CFCT**: CSIR-NPL Centre for Calibration & Testing (via search snippet: ISO/IEC 17025:2017, CIPM-MRA, weights 1 mg - 2000 kg). <https://www.nplindia.org/index.php/commercial-services/calibration-testing/>. Access: search snippet.
- **S-CMTI-MET**: CMTI Precision Metrology & Calibration page. <https://cmti.res.in/precision-metrology-calibration/>. Access: HTTP 503 to fetch tool; content from search snippet (NABL accreditation in dimensional metrology; roughness masters).
- **S-NABL500-2020**: NABL 500 Directory of Accredited Calibration Laboratories as on 31-Mar-2020 (historical). <https://nabl-india.org/wp-content/uploads/2020/04/Calibration-directory-2-dtd-22.04.2020-1-1.pdf>. Access: PDF downloaded and grepped.
- **S-NABL-SEARCH**: NABL public laboratory search (ASP.NET form, no captcha observed). <https://nablwp.qci.org.in/laboratorysearchone>. Access: reachable; one automated name query returned no parsable record - manual lookup needed.
- **S-ULVAC-CRYO**: ULVAC cryopump safety instructions (O2/ozone during regeneration). <https://showcase.ulvac.co.jp/en/how-to/trouble-shooting/cryo-pump-safety.html>. Access: search snippet.
- **S-ASTM-E1508**: ASTM E1508-12a(2019) scope (elements >= Na, > 0.1 wt%). <https://store.astm.org/e1508-12ar19.html>. Access: search snippet (consistent with REPO-METSPEC).
