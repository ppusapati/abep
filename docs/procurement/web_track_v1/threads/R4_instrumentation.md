# R4 - Instrumentation procurement research (H-1 S1a / S1-S1b / Phase 1)

Date 2026-09-27, repo commit 782f900. H-1 S1a / S1-S1b / Phase 1 instrument procurement research; published sources only; no supplier contact; no vendor preference implied by listing.

**Authority note.** A7 lists H3 procurement as PLANNED_NOT_REGISTERED; only the metrology specification is explicitly APPROVED_FOR_PROCUREMENT (A4). 'Safe' here is a technical classification, not an authorization.

Evidence classes: `datasheet_read` = datasheet/paper text extracted and read this session; `search_snippet_verify` = search-engine snippet only - verify against the document; `memory_verify` = memory - verify; `repo` = from repository; `model_derived_here` = derived here from the cited values

## sccm <-> mg/s

sccm at 0 C, 101325 Pa (MKS STP gas densities, SRC-MKS-GCF); 1 sccm = rho[g/L] mg/min. Alicat defaults to 25 C/1 atm 'STP' (factor 298.15/273.15 = 1.0915 on volume); Bronkhorst uses mln/min (normal conditions, verify). Every conversion must use the reference of the specific MFC.

mg/s per sccm: Xe 0.097633, N2 0.020833, O2 0.023783

| point | gas | mg/s | sccm |
|---|---|---|---|
| cathode Xe lower (task) | Xe | 0.05 | 0.512 |
| cathode Xe A5 design target | Xe | 0.1 | 1.024 |
| cathode Xe A5 upper test point | Xe | 0.15 | 1.536 |
| cathode Xe upper (task) | Xe | 0.2 | 2.048 |
| measured diode-mode minimum of other cathodes (xe_ledger AN-01, context) | Xe | 0.8 | 8.194 |
| A4 MFC envelope min (as N2) | N2 | 0.029548 | 1.418 |
| A4 MFC envelope max (as N2) | N2 | 3.14236 | 150.836 |
| W1 O2 component max | O2 | 1.39518 | 58.663 |
| HT5k ignition anode Xe (context only, 5 kW class) | Xe | 10.0 | 102.424 |

repo feed_state_closure uses M_N2 = 28.0 u and ideal molar volume (150.93 sccm at max); the MKS-density basis gives the value above; difference < 0.1 %.

## Procurement classification summary

| category | status | wait reason |
|---|---|---|
| 1a mass flow - anode N2 / O2 (air surrogate) | SAFE_TO_QUOTE_NOW (A4 fixes the 0.030-3.14 mg/s envelope and >= 3 ranges per gas path); final FS per range WAIT | exact FS per range follows the W1 registered test points / owner-released GROUND_QUALIFICATION_POINTs (S1A-C3) and CD-P-MFC-MINFRAC (PROPOSED); H3 procurement wave is PLANNED_NOT_REGISTERED (A7) - PO authority is the owner's |
| 1b mass flow - Xe cathode and Xe anode ignition/transition | cathode MFC SAFE_TO_QUOTE_NOW (A5 0.10/0.15 mg/s and A4 range rule); anode-Xe ignition MFC WAIT | C-1 flow range and start flows (W3 / LOCK-1 cathode operating point); H-1 Xe ignition/transition flows unknown (HT5k 10 mg/s is out of class, context only) |
| 1c primary flow calibrator (MFC calibration traceability) | SAFE_TO_QUOTE_NOW (needed by every S1a MFC procedure regardless of LOCK-1) | calibrator choice itself is an open item ('capability TBD - requires the calibrator choice', S1A-P-MFC-01) |
| 2a facility background pressure (ion gauges) | WAIT | facility not identified (S1A-C5); facility gauges and T-PB-MAX come with it |
| 2b feed / plenum pressure (capacitance manometers) | WAIT | W1 registered P_feed range/tolerance (INS-06 TBD) |
| 3 DC power metering (discharge ~180-350 V PROPOSED rating, I_d <= 8.33 A; auxiliaries) | SAFE_TO_PROCURE_NOW for the DC analyzer/shunt class (range-robust; traceability rule decided in A4); I_d(t) probe band WAIT | channel count and small-channel ranges follow the LOCK-1 allocation; oscillation band from the S1 spectrum |
| 4 RF / microwave net power (contingency modules) | WAIT | RF frequency (PMR-01) and ECR frequency (PME-01) not selected; P_hi_rf / P_hi_ecr TBD at LOCK-1; f_src allocation sets the required uncertainty |
| 5 B(z) mapping (Hall probe / teslameter + stage) | SAFE_TO_QUOTE_NOW for meter+probe (range-robust to PM or EM circuit); stage/fixture WAIT | fixture keyed to H-1 fiducials and probe path (HW-H1-08) need the H-1 design release; W5 B(z) tolerance |
| 6 temperatures (thermocouples, cathode tube, pyrometry) | TCs, feedthroughs, reference thermometer: SAFE_TO_PROCURE_NOW (generic, needed for CD-07 bench calibration); pyrometer WAIT | pyrometer depends on the HW-C1-09(b) view decision and C-1 emitter temperature band; TC positions follow W3 |
| 7 residual gas analyser (chamber and near-cathode INS-22) | WAIT | owner decision whether RGA is in the minimum set (INS-11 OPTIONAL; S1A-C1 optional); facility choice; near-cathode local pressure TBD |
| 8 thrust stand and force calibration | calibration mass set: SAFE_TO_PROCURE_NOW; stand: WAIT | owner decision on stand principle (INS-01 open decision 2), mass on stand incl. RF/ECR modules (W3), facility (S1A-C5); no commercial mN EP thrust-balance datasheet located in open sources this session |
| 0 external metrology lab (INS-19/INS-20, MS-M-01..05) | SAFE_TO_PROCURE_NOW (quotes / capability requests) | none for quotes; ranges TBD (W3 coupon masses) |

## 1a mass flow - anode N2 / O2 (air surrogate)

Requirement refs: INS-05, CD-04, S1A-C4 mass_flow_controllers, A4 MFC_ranges, HW-FS-01, HW-FS-07 (O2 cleanliness), I-FLOW-CONSERVATIVE, CD-P-MFC-MINFRAC 0.2

Required: one MFC per pure gas, calibrated on its own gas in final orientation (SRC-SNYDER2017); envelope 0.030-3.14 mg/s (~106:1), >= 3 overlapping ranges per gas path (A4); N2 1.42-150.9 sccm-equivalent, O2 component <= 58.6 sccm (W1); every registered point >= 0.2 FS (PROPOSED); O2-service cleaned; R_arch needs repeatability only, absolute gate needs expanded u at each registered point

**thermal-sensor MFC with laminar bypass (e.g. Bronkhorst EL-FLOW Select F-200CV/F-201CV)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| accuracy (incl. linearity, based on actual calibration) | ±(0.5 % Rd + 0.1 % FS); ±(0.8 % Rd + 0.2 % FS) for F-200CV-005; ±2 % FS for F-200CV-002 | - | SRC-BH-ELFLOW | datasheet_read |
| smallest air ranges F-200CV | min 0.014-0.7, max 0.06-9 | mln/min | SRC-BH-ELFLOW | datasheet_read |
| turndown | up to 1:187.5 (1:50 analog) | - | SRC-BH-ELFLOW | datasheet_read |
| repeatability | < 0.2 % Rd | - | SRC-BH-ELFLOW | datasheet_read |
| temperature sensitivity | zero < 0.05 % FS/°C; span < 0.05 % Rd/°C | - | SRC-BH-ELFLOW | datasheet_read |
| attitude sensitivity | max 0.2 % at 90° off horizontal, 1 bar, N2 | - | SRC-BH-ELFLOW | datasheet_read |

- Meets requirement: PARTIAL: at 0.2 FS the bound is 0.5 % + 0.5 % = 1.0 % of reading (standard ranges) — consistent with I-U planning but not the 0.5 % per-reading repeatability path unless S1a shows it; thermal principle needs own-gas calibration (O2 and N2 separately)
- Calibration route: factory calibration certificate (accreditation scope not verified here); own-gas verification against the S1a primary calibrator (item 1c)
- Limitations: gas-dependent sensor (GCF); orientation and temperature zero shifts; O2-service cleaning is an ordering option to confirm (not read)

**laminar differential-pressure MFC with gas property library (e.g. Alicat MC mid-range 10 sccm-20 slpm)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| accuracy standard / high | ±0.6 % Rd or ±0.1 % FS whichever greater / ±0.5 % Rd or ±0.1 % FS | - | SRC-ALICAT-MID | datasheet_read |
| repeatability (2σ) | ±(0.1 % Rd + 0.02 % FS) | - | SRC-ALICAT-MID | datasheet_read |
| control range | 0.01-100 % FS (10,000:1) | - | SRC-ALICAT-MID | datasheet_read |
| zero shift | ±0.01 % FS per °C; span ±0.01 % Rd per °C | - | SRC-ALICAT-MID | datasheet_read |
| mounting orientation sensitivity | None (vendor statement) | - | SRC-ALICAT-MID | datasheet_read |
| reference conditions | STP 25 °C/1 atm default, user-configurable | - | SRC-ALICAT-LOW | datasheet_read |

- Meets requirement: LIKELY for the upper two ranges on paper (0.6 % Rd bound); per-reading repeatability and own-gas calibration must be shown in CD-04
- Calibration route: vendor calibration (ISO/IEC 17025 claim not verified here - verify); own-gas check against primary calibrator
- Limitations: '98 gases' are property-based conversions (REFPROP), i.e. not an own-gas calibration in the Snyder 2017 sense unless calibrated on O2/N2; wetted FKM seals - confirm O2 service option

**Coriolis MFC (e.g. Bronkhorst mini CORI-FLOW ML120V21)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| mass flow accuracy gas | ±0.5 % of rate | - | SRC-BH-ML120 | datasheet_read |
| full scale | min 5 g/h (1.39 mg/s), max 200 g/h | g/h | SRC-BH-ML120 | datasheet_read |
| zero stability | < ±10 mg/h (= 0.0028 mg/s) | mg/h | SRC-BH-ML120 | datasheet_read |
| rangeability MFC | ≥ 1:100 | - | SRC-BH-ML120 | datasheet_read |
| pressure rating | 5 bara (higher on request) | bar | SRC-BH-ML120 | datasheet_read |
| mounting | any position; must be bolted to stiff mass for zero stability | - | SRC-BH-ML120 | datasheet_read |

- Meets requirement: PARTIAL: gas-independent (no GCF), good for 0.3-3.14 mg/s; at the 0.030 mg/s envelope minimum the zero stability alone is ~9 % of reading - not usable there
- Calibration route: gravimetric/any-fluid calibration transfers across gases (principle; verify certificate scope)
- Limitations: vibration-sensitive zero; low-end of envelope not covered


## 1b mass flow - Xe cathode and Xe anode ignition/transition

Requirement refs: INS-05, HW-FS-01 (separate Xe anode and Xe cathode MFCs), HW-FS-03, P1DQ-NOXE (zero band, valve seat leakage), P1DQ-IGN (integrated Xe per start), xe_ledger mdot_cathode 0.10 mg/s design, 0.15 test

Required: cathode: 0.05-0.20 mg/s = 0.51-2.05 sccm Xe (0 °C basis); range should also reach C-1 diode/start flows (other cathodes 0.6-0.8 mg/s = 6.1-8.2 sccm, context) - C-1 range TBD (W3); zero offset/drift inside the P1DQ-NOXE zero band; anode Xe ignition flow TBD (H-1 start sequence), Xe GCF not used where the MFC is calibrated on Xe

**low-range DP MFC on Xe (e.g. Alicat MC 0.5-5 sccm class)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| accuracy | ±0.8 % Rd ±0.2 % FS (high accuracy only for ≥5 sccm models) | - | SRC-ALICAT-LOW | datasheet_read |
| repeatability (2σ) | ±(0.2 % Rd ± 0.02 % FS) | - | SRC-ALICAT-LOW | datasheet_read |
| control range | 0.01-100 % FS | - | SRC-ALICAT-LOW | datasheet_read |
| temperature sensitivity | 0.02 % FS per °C from 25 °C | - | SRC-ALICAT-LOW | datasheet_read |
| derived: bound at 1.02 sccm (0.10 mg/s) on a 2 sccm FS | ±(0.8 % + 0.39 %) = ±1.2 % of reading | - | SRC-ALICAT-LOW | model_derived_here |

- Meets requirement: PLAUSIBLE on paper for 0.10-0.15 mg/s; Xe here is a property-library gas, so an own-gas Xe verification is required
- Calibration route: verify against primary calibrator on Xe (item 1c); accredited Xe calibration availability not found
- Limitations: no published Xe-specific calibration uncertainty read

**thermal MFC calibrated on N2 with Xe GCF**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| MKS theoretical GCF Xe (N2 = 1) | 1.32 | - | SRC-MKS-GCF | datasheet_read |
| MKS GCF O2 | 0.993 | - | SRC-MKS-GCF | datasheet_read |
| Xe density at 0 °C, 1 atm | 5.858 | g/L | SRC-MKS-GCF | datasheet_read |

- Meets requirement: NOT PREFERRED: MKS itself notes non-linearity between N2 calibration and process gas; INS-05/CD-04 require own-gas calibration or a measured factor
- Calibration route: measure actual factor against primary calibrator on Xe (CD-04 step 3)
- Limitations: theoretical GCF only

**Coriolis (ML120) as Xe check standard**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| zero stability vs 0.10 mg/s | 10 mg/h / 360 mg/h = 2.8 % | - | SRC-BH-ML120 | model_derived_here |

- Meets requirement: NO for 0.05-0.2 mg/s control; possibly a transfer check near 1 mg/s
- Calibration route: n/a
- Limitations: zero stability


## 1c primary flow calibrator (MFC calibration traceability)

Requirement refs: INS-05 calibration, CD-04, S1A-P-MFC-01/02, A4 force_DC_RF_traceability (SI-traceable, ISO/IEC 17025 scope)

Required: constant-volume rate-of-rise or constant-pressure primary calibrator, traceable, reaching the lower end of the smallest range (~0.5 sccm Xe, ~1.4 sccm N2) on N2, O2 and Xe; certificate + uncertainty budget + raw record (A4)

**in-house rate-of-rise (constant-volume) calibrator using a traceable capacitance manometer, volume and thermometry**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| principle | pressure-volume-temperature-time; gas-independent in principle | - | SRC-SNYDER2017 | repo |

- Meets requirement: TBD - uncertainty budget to be built (volume determination, temperature, pressure)
- Calibration route: traceable P, V, T, t sub-measurements (NABL scopes for pressure/volume/temperature)
- Limitations: design effort; low flows need long rise times

**commercial laminar/piston primary standards (e.g. Fluke molbloc-L/molbox, Mesa DryCal class)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| low-flow capability and uncertainty | not read in this session | - | SRC-MEMORY | memory_verify |

- Meets requirement: TBD (verify lowest range reaches ~0.5 sccm and Xe/O2 compatibility)
- Calibration route: vendor or NABL-accredited recalibration (verify scope)
- Limitations: specs not verified

**external NABL-accredited gas-flow lab (e.g. FCRI Palakkad, air media)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| accreditation | NABL-accredited flow labs for water, oil and air media; masters traceable to NPL New Delhi | - | SRC-FCRI | search_snippet_verify |

- Meets requirement: UNKNOWN: sccm-level and Xe/O2 scope not found
- Calibration route: NABL ISO/IEC 17025
- Limitations: MFC must also be verified installed in final orientation (SRC-SNYDER2017) - external cal alone is insufficient


## 2a facility background pressure (ion gauges)

Requirement refs: INS-08, REF-DANKANICH2017 placement, S1A-C2 background_pressure_max, A4 S1a interlock vacuum abort, P1DQ-TABS facility rule

Required: hot-cathode ion gauge(s) at exit plane per Dankanich 2017; calibrated on N2, O2 and the N2/O2 mixture (and Xe) - p_b_max TBD (T-PB-MAX, owner)

**Bayard-Alpert hot-cathode gauge + controller (generic; facility may already own)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| nominal relative sensitivity N2 / O2 / Xe | 1.00 / 1.01 / 2.87 | - | SRC-SRS-IGGCF | datasheet_read |
| vendor caveat | discrepancy <= 10 % common gases, a little above 20 % less common; pressure dependent, unreliable above 1e-5 Torr; calibrate individually on the specific gas | - | SRC-SRS-IGGCF | datasheet_read |

- Meets requirement: only with in-situ gas-specific calibration (nominal factors are not adequate)
- Calibration route: in-situ comparison against a spinning-rotor gauge or capacitance manometer (memory_verify) or NABL vacuum-gauge calibration with the specific gas (lab scope not searched)
- Limitations: mixture response not a simple sum at the 10 % level; O2 affects filament (memory_verify)


## 2b feed / plenum pressure (capacitance manometers)

Requirement refs: INS-06, HW-FS-04 manifold manometer, HW-ENV-04, S1A-C2 feed_pressure_max

Required: gas-independent force-per-area sensor at IF-A5 plane and module source chamber; range TBD (W1 P_feed)

**heated capacitance manometer (e.g. MKS 627F)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| accuracy | 0.12 % of reading | - | SRC-MKS-627F | search_snippet_verify |

- Meets requirement: TBD (no numeric P_feed tolerance yet)
- Calibration route: NABL pressure-scope calibration or vendor cert; zero at base vacuum in S1a
- Limitations: FS must be chosen from W1 P_feed; datasheet not read


## 3 DC power metering (discharge ~180-350 V PROPOSED rating, I_d <= 8.33 A; auxiliaries)

Requirement refs: INS-02, INS-04, CD-03, S1A-C4 power_channels, DQ-PBUS, I-U-ABS-P 1 % (PROPOSED), u_P <= 0.50 % per reading (n=4), I-U-ID-FLOOR, HW-ENV-01/02

Required: simultaneous V/I per bus_power_boundary_v1 channel, 4-wire sense; per-channel 0.50 % (1σ) repeatability, 1 % absolute; I_d(t) band TBD from S1 (Choueiri 2001: 1 kHz-60 MHz reviewed); pickup bounded with RF/µW into dummy loads

**precision power analyzer (e.g. Yokogawa WT5000)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| DC active power accuracy | ±(0.02 % of reading + 0.05 % of range) | - | SRC-YOKO-WT5000 | datasheet_read |
| DC voltage and current accuracy | ±(0.02 % of reading + 0.05 % of range) | - | SRC-YOKO-WT5000 | datasheet_read |
| voltage ranges | 1.5 ... 1000 V | V | SRC-YOKO-WT5000 | datasheet_read |
| current ranges 30 A element | 500 mA ... 30 A (CF3) | A | SRC-YOKO-WT5000 | datasheet_read |
| A/D | simultaneous V and I, 18 bit, 10 MS/s max | - | SRC-YOKO-WT5000 | datasheet_read |
| current 10-50 kHz accuracy | ±(0.3 % Rd + 0.1 % range) | - | SRC-YOKO-WT5000 | datasheet_read |
| derived: 8.33 A on 10 A range | ±0.07 % of reading bound | - | SRC-YOKO-WT5000 | model_derived_here |
| derived: 2 A on 10 A range | ±0.27 % of reading bound | - | SRC-YOKO-WT5000 | model_derived_here |

- Meets requirement: YES on paper for DC mean power at 1 % absolute and well inside 0.5 %; ranges robust to the unfrozen V_d set
- Calibration route: ISO/IEC 17025 DC V/I/power calibration (A4); NABL electrical scopes common in India (specific labs not searched)
- Limitations: aux channels at low power need appropriate small ranges; element count vs number of MEASURED components (up to 7 lab channels) to confirm

**zero-flux / fluxgate DC current transducer + precision shunt channels into DAQ (e.g. LEM IT 60-S ULTRASTAB)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| principle | closed-loop fluxgate, DC/AC/pulsed, galvanic isolation | - | SRC-LEM-IT60 | search_snippet_verify |

- Meets requirement: TBD (linearity/offset/bandwidth numbers not read)
- Calibration route: system calibration against traceable DC calibrator (CD-03)
- Limitations: datasheet numbers not retrieved

**wide-band current probe for I_d(t)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| band to capture | TBD from S1 HW-0 spectrum | - | SRC-REPO-INS | repo |

- Meets requirement: TBD
- Calibration route: gain/offset against calibrated DC channel (CD-03 step 5)
- Limitations: no product evaluated


## 4 RF / microwave net power (contingency modules)

Requirement refs: INS-03, CD-03 step 4, PMR-01/02/03/06, PME-01/05/06, u_src <= 3.5 % (f_src 0.1) ... 0.9 % (f_src 0.4), 1σ, DUMMY_LOAD_PICKUP

Required: forward/reflected at load plane or characterised chain; RF frequency not selected (published sources 0.5-7 MHz, 13.56, 27.12, 40.68 MHz); ECR 2.45 or 5.8 GHz candidates; P_hi TBD (LOCK-1)

**inline directional power sensor HF/VHF (e.g. R&S NRT-Z14)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| frequency | 25 MHz - 1 GHz | Hz | SRC-RS-NRTZ14 | search_snippet_verify |
| power | 6 mW - 120 W avg, 300 W peak | W | SRC-RS-NRTZ14 | search_snippet_verify |
| expanded uncertainty | ~6 % of reading (k=2) (snippet) | - | SRC-RS-NRTZ14 | search_snippet_verify |

- Meets requirement: NO for 13.56 MHz and below (range starts at 25 MHz); ~3 % (1σ) meets only the f_src = 0.1 scale
- Calibration route: vendor/NABL RF-power scope (verify)
- Limitations: frequency coverage

**element-based directional wattmeter (e.g. Bird 5010B)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| forward average accuracy | 5 % (0.2 dB) | - | SRC-BIRD-5010B | search_snippet_verify |
| frequency | element dependent, ~2 MHz upward | Hz | SRC-BIRD-5010B | search_snippet_verify |

- Meets requirement: NO at f_src >= 0.2 (±5 % bound ≈ 2.9 % 1σ rectangular)
- Calibration route: verify
- Limitations: accuracy class

**calorimetric / thermal sensor + characterised coupler and matched dummy load (method)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| achievable uncertainty | not established from an open source in this session | - | SRC-REPO-INS | repo |

- Meets requirement: TBD (INS-03 AT_RISK)
- Calibration route: ISO/IEC 17025 RF power scope (A4)
- Limitations: needs RF/µW design (W3)


## 5 B(z) mapping (Hall probe / teslameter + stage)

Requirement refs: INS-09, CD-05, S1A-C4 magnetic_field_Bz, HW-MC-03/04, HW-H1-08, INS-P-07

Required: axial and radial B at actual coil currents; typical Xe Hall ~200 G (20 mT) context, P5 N2 setpoint 130 G, ECR resonance 87.5 mT (2.45 GHz) / 207 mT (5.8 GHz); probe offset (zero-field chamber) and gain (reference field) each session; tolerance TBD (W5)

**3-axis Hall teslameter (e.g. Lake Shore F71 with 3-axis probe)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| DC accuracy | ±0.15 % of reading (standard probe, 350 mT-3.5 T range) | - | SRC-LS-F71 | search_snippet_verify |
| axis orthogonality | < 0.2° | deg | SRC-LS-F71 | search_snippet_verify |
| temperature coefficient | ±0.002 % Rd/°C beyond ±5 °C of cal temp | - | SRC-LS-F71 | search_snippet_verify |

- Meets requirement: TBD vs W5 tolerance; accuracy at 35 mT range not read (verify)
- Calibration route: vendor NIST-traceable calibration (verify accreditation); reference magnet check each session
- Limitations: snippet-level specs only


## 6 temperatures (thermocouples, cathode tube, pyrometry)

Requirement refs: INS-07, INS-17, INS-23, INS-24, CD-07, S1A-C4 temperature_channels, A3 cathode_temperature (tube TC mandatory; pyrometer only with defensible view; never labelled emitter)

Required: stand/thruster/coil TCs, cathode-tube TC (mandatory), optional emitter pyrometer; calibration by comparison (ASTM E220 cited, verify); resolution TBD (T-SETTLE, life limits)

**Type K / N mineral-insulated TCs + matched-alloy vacuum feedthroughs**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| IEC 60584-1 class 1 tolerance K/N | ±1.5 °C or ±0.004|t| (-40 to 1000 °C) | - | SRC-MEMORY | memory_verify |

- Meets requirement: TBD (requirement TBD)
- Calibration route: NABL temperature-scope comparison calibration of lot samples
- Limitations: K drift at high T; pickup in RF/coil fields (CD-07)

**Type R/S (Pt-Rh) or Type C (W-Re) for cathode tube above ~1000 °C**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| usable range | R/S to ~1600 °C in oxidizing; W-Re in vacuum/inert only | °C | SRC-MEMORY | memory_verify |

- Meets requirement: TBD
- Calibration route: NABL high-temperature comparison
- Limitations: W-Re embrittles/oxidizes with O2 present (memory_verify)

**two-colour (ratio) pyrometer through viewport**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| emissivity handling | ratio method reduces grey-body emissivity and window-attenuation sensitivity | - | SRC-MEMORY | memory_verify |

- Meets requirement: only if HW-C1-09(b) gives a view
- Calibration route: against TC on reference body (INS-23) or blackbody (NABL)
- Limitations: LaB6 emissivity and viewport coating/deposition


## 7 residual gas analyser (chamber and near-cathode INS-22)

Requirement refs: INS-11 (OPTIONAL), INS-22, A3 near_cathode_rga (quantitative for AO/life: O2/N2/H2O), open owner decision 6 (minimum instrument set)

Required: mass range covering H2O 18, N 14, O 16, N2 28, NO 30, O2 32 and Xe isotopes to m/z 136 (=> >= 200 amu model); species calibration or traceable sensitivity factors before score/life use; differential pumping if sampled pressure > operating limit

**open-ion-source quadrupole RGA 1-200 amu (e.g. SRS RGA200)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| mass range | 1-200 amu | amu | SRC-SRS-RGA | search_snippet_verify |
| min detectable partial pressure | 5e-11 Torr (FC), 5e-14 Torr (EM) | Torr | SRC-SRS-RGA | search_snippet_verify |
| max operating pressure | 1e-4 Torr (FC) | Torr | SRC-SRS-RGA | search_snippet_verify |
| resolution | < 0.5 amu at 10 % peak height | amu | SRC-SRS-RGA | search_snippet_verify |

- Meets requirement: mass range YES (Xe 124-136 inside 200); quantitative use only after calibration
- Calibration route: in-situ against known N2/O2 mixtures from calibrated MFCs and a calibrated gauge (INS-22); H2O method unidentified
- Limitations: m/z 16/14 fragments from O2/N2/H2O overlap atomic O/N; 100-amu models exclude Xe

**differentially pumped sampling RGA (vendor class, e.g. Hiden HPR / Inficon CPM)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| specs | not read | - | SRC-MEMORY | memory_verify |

- Meets requirement: TBD
- Calibration route: as above
- Limitations: not evaluated


## 8 thrust stand and force calibration

Requirement refs: INS-01, CD-01, CD-02, S1A-C4 thrust_stand, DQ-TABS/DQ-RARCH, I-U-ABS-T 1 % (PROPOSED), u_T <= 0.50 % per reading (≈60 µN 1σ at 12 mN, n=4), u_inst <= 0.25 % ln, A4 force traceability

Required: 12-25 mN (plus knee-scan low end), mass-change-robust between HW-0/RF/ECR (torsional or re-calibrate per configuration), in-situ calibration >= 10 before/after, thermal shrouds, inclination control (inverted pendulum); mass on stand TBD (W3)

**NASA GRC null-coil inverted pendulum (published analysis)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| absolute uncertainty VF-6 case | ±6.9 mN over span; 6.9-1.1 % over 100-600 mN (95 %) | - | SRC-MACKEY2018 | datasheet_read |

- Meets requirement: NO as-is at 12-25 mN (high-thrust class); design reference only
- Calibration route: in-situ weights
- Limitations: repeatability not addressed by the paper

**null-type inverted pendulum, Xu & Walker 2009**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| reported uncertainty | 0.6 % for thrust up to 230 mN (3.4 kW Hall); calibration mass uncertainty 0.002 g | - | SRC-XU2009 | search_snippet_verify |

- Meets requirement: UNKNOWN at 12-25 mN (1 mN-5 N range per repo REF-XU2009)
- Calibration route: weights
- Limitations: PDF not read

**mN inverted pendulum, BUSTLab (Kokal & Celik 2017)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| resolution | ~100 µN | N | SRC-KOKAL2017 | datasheet_read |
| initial uncertainty | around 10 % | - | SRC-KOKAL2017 | datasheet_read |
| calibration | pre-calibrated load cell 50 mV/mN on linear stage | - | SRC-KOKAL2017 | datasheet_read |

- Meets requirement: NO (resolution ~ requirement; uncertainty 10x)
- Calibration route: load cell
- Limitations: early development

**calibration masses OIML R111 class E2 (for dead-weight/pulley in-situ calibration)**

| quantity | value | unit | source | class |
|---|---|---|---|---|
| mass for 25 mN at g_n | 2.549 | g | SRC-POLK2017 | model_derived_here |
| E2 MPE 1 g | ±0.03 mg (3e-5 relative) | mg | SRC-REPO-MS | repo |

- Meets requirement: YES (mass term negligible vs 0.5 %); pulley friction/local g dominate
- Calibration route: NABL mass scope with OIML R111 certificates (A3/A4)
- Limitations: transfer mechanism uncertainty is stand-specific


## 0 external metrology lab (INS-19/INS-20, MS-M-01..05)

Requirement refs: A3 metrology_lab, A4 metrology_specification APPROVED as procurement specification, MS-G-01..08

Required: ISO/IEC 17025 (NABL) scope covering each MS-M measurand; E2 masses; ISO 25178-700; ASTM E1508; ISO 15472; k=2 planning

**NABL-accredited lab(s) selected against the spec**

- Meets requirement: TBD per scope
- Calibration route: NABL
- Limitations: no lab searched or contacted (A3 rule: spec first)

## Unresolved

- No open datasheet read for an accredited Xe-gas MFC calibration at 0.5-2 sccm; Xe on DP/thermal MFCs relies on property libraries or GCF 1.32 (theoretical).
- Primary flow calibrator reaching ~0.5 sccm Xe with a stated uncertainty not identified (commercial specs not read).
- Indian NABL scope for sccm-level gas flow (N2/O2/Xe) not found; FCRI scope found only for air media at unspecified range.
- RF net-power at 13.56 MHz and below with <= 1-2 % (1σ): no open-source sensor spec found; common inline sensors are 5-6 % class or start at 25 MHz.
- No commercial mN electric-propulsion thrust balance datasheet located; published stands are either high-thrust (NASA GRC: ±6.9 mN) or early mN designs (~10 %).
- MKS 627F, LEM IT 60-S, Lake Shore F71, SRS RGA200, R&S NRT-Z14, Bird 5010B values are snippet-level (verify).
- H2O calibration method for the near-cathode RGA (A3) still unidentified.
- Thermocouple tolerance classes and pyrometry statements are memory-based (verify IEC 60584-1 / ASTM E230 text).

## Owner questions

1. Does A4 MFC_ranges ('part of procurement planning') authorize purchase orders for the three-range N2/O2 sets and the cathode-Xe MFC, or only quotations until the H3 wave is registered?
2. MFC principle per gas path: thermal own-gas-calibrated vs DP with property library vs Coriolis (gas-independent but zero-stability-limited below ~0.3 mg/s)?
3. Cathode-Xe MFC range: cover only 0.05-0.2 mg/s, or also C-1 start/diode flows (other cathodes 0.6-0.8 mg/s) - one or two controllers?
4. Is an in-house rate-of-rise calibrator (traceable P/V/T/t) acceptable as the S1a primary flow standard under A4, or must MFC calibration be NABL-scope certified?
5. Thrust stand: build (published design basis) vs buy; torsional vs inverted pendulum given module mass change (INS-01 open decision 2)?
6. Is the RGA in the S1a minimum set; if yes, 200 or 300 amu and differential pumping for INS-22?
7. RF/ECR: select frequency and P_hi so INS-03 sensors/couplers can be specified; accept calorimetric load-plane method if inline sensors cannot reach u_src?

## Source register

| id | type | citation | access |
|---|---|---|---|
| SRC-REPO-INS | repo | docs/experiments/instrumentation/INSTRUMENTATION_DEFINITION.md + instrumentation_definition_v1.json (v1-r2) | read 2026-09-27 |
| SRC-REPO-MS | repo | docs/experiments/instrumentation/metrology_spec/METROLOGY_MEASUREMENT_SPEC.md | read |
| SRC-REPO-A3 | repo | docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json | read |
| SRC-REPO-A4 | repo | docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json (metrology_specification, force_DC_RF_traceability, MFC_ranges) | read |
| SRC-REPO-A7 | repo | docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json (H3 procurement wave PLANNED_NOT_REGISTERED) | read |
| SRC-REPO-CD | repo | docs/experiments/capability_demo/CAPABILITY_DEMO_PREP.md (CD-01..CD-07) + s1a_calibration_procedures_candidate_v1.json | read |
| SRC-REPO-S1A | repo | docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json (S1A-C1 required INS items, S1A-C4 categories) | read |
| SRC-REPO-P1 | repo | docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json (P1DQ measurement chains) | read |
| SRC-REPO-PIM | repo | docs/interfaces/preionizer_module/PREIONIZER_MODULE_ICD.md (PMR-01 RF freq not selected; PME-01 2.45/5.8 GHz candidates; P_hi TBD) | read |
| SRC-REPO-RFEV | repo | docs/evidence/rf_source/RF_SOURCE_EVIDENCE.md (0.5-7 MHz, 13.56, 27.12, 40.68 MHz in published sources) | read |
| SRC-REPO-XE | repo | docs/budgets/xe_ledger/XE_LEDGER.md (cathode 0.10 mg/s design, 0.15 test; diode-mode minima 0.6-0.8 mg/s of other cathodes) | read |
| SRC-REPO-HW | repo | docs/experiments/hardware/HARDWARE_DEFINITION.md (HW-ENV-01/02: 8.33 A at 180 V, rating to 350 V PROPOSED; HW-FS-01..07; B_res 2.45 GHz 87.5 mT, 5.8 GHz 207 mT) | read |
| SRC-REPO-FSC | repo | docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json mfc_range_requirement | read |
| SRC-ALICAT-LOW | datasheet | Alicat DOC-SPECS-MC-LOW Rev 5 Aug 2025, https://documents.alicat.com/specifications/DOC-SPECS-MC-LOW.pdf | full text extracted (pdftotext) 2026-09-27 |
| SRC-ALICAT-MID | datasheet | Alicat DOC-SPECS-MC-MID, https://documents.alicat.com/specifications/DOC-SPECS-MC-MID.pdf | full text extracted 2026-09-27 |
| SRC-BH-ELFLOW | datasheet | Bronkhorst EL-FLOW Select brochure, https://www.bronkhorst.com/getmedia/98668a82-8d1c-4b7f-af8e-995be25641b3/EL-FLOW-Select_en.pdf | full text extracted 2026-09-27 |
| SRC-BH-ML120 | datasheet | Bronkhorst mini CORI-FLOW ML120V21 datasheet (distributor copy), https://www.insatech.com/media/5vzhqbrc/gs_e_ml120v21-mini-cori-flow-specifications-reve.pdf | full text extracted 2026-09-27 |
| SRC-MKS-GCF | vendor table | MKS 'Gas Correction Factors for Thermal-based Mass Flow Controllers' (university-hosted copy of mks.com page), https://nfc.arizona.edu/sites/default/files/2022-02/mfc_correction.pdf | full text extracted 2026-09-27 |
| SRC-SRS-IGGCF | app note | SRS 'Gas Correction Factors for Bayard-Alpert Ionization Gauges', https://www.thinksrs.com/downloads/pdfs/applicationnotes/IG1BAgasapp.pdf | full text extracted 2026-09-27 |
| SRC-MKS-627F | datasheet | MKS 627F datasheet https://www.mks.com/mam/celum/celum_assets/resources/627F-DS.pdf | NOT read: site returned an embed/bot page; value from search-result snippet only (verify) |
| SRC-YOKO-WT5000 | datasheet | Yokogawa Bulletin WT5000-02EN specifications, https://cdn.tmi.yokogawa.com/1/7113/files/Specifications%20WT5000%20Precision%20Power%20Analyzers%20Yokogawa%20Test%20Measurement%20BUWT5000%2002EN.pdf | full text extracted 2026-09-27 |
| SRC-LEM-IT60 | datasheet | LEM IT 60-S ULTRASTAB, https://www.lem.com/sites/default/files/products_datasheets/it_60-s_ultrastab.pdf | NOT read: URL returned a product HTML page without numbers (verify) |
| SRC-RS-NRTZ14 | datasheet/manual | R&S NRT-Z14/44 directional power sensors (manual pages + distributor listings), https://www.rohde-schwarz.com/us/manual/r-s-nrt-z14-44-directional-power-sensors-user-manual-manuals_78701-1205888.html | search-result snippets only (verify) |
| SRC-BIRD-5010B | distributor listing | Bird 5010B directional power sensor, https://www.testequity.com/product/32113-1-5010B | search-result snippet only (verify) |
| SRC-LS-F71 | vendor spec page | Lake Shore F71/F41 teslameter specifications, https://www.lakeshore.com/products/categories/specification/magnetic-products/gaussmeters-teslameters/f71-and-f41-teslameters | search-result snippet only (verify) |
| SRC-SRS-RGA | vendor catalog | SRS RGA catalog / manual, https://www.thinksrs.com/downloads/pdfs/catalog/RGAc.pdf | search-result snippet only (verify) |
| SRC-MACKEY2018 | paper | J. Mackey, T. Haag, H. Kamhawi et al., 'Uncertainty in Inverted Pendulum Thrust Measurements', NASA GRC, NTRS 20190000300, https://ntrs.nasa.gov/api/citations/20190000300/downloads/20190000300.pdf | full text extracted 2026-09-27 (abstract and results lines) |
| SRC-XU2009 | paper | K. G. Xu, M. L. R. Walker, 'High-power, null-type, inverted pendulum thrust stand', RSI 80, 055103 (2009), https://hpepl.ae.gatech.edu/papers/RSI_V80_No5_May_2009.pdf | PDF not retrieved (HTML returned); values from search-result snippet (verify) |
| SRC-KOKAL2017 | paper | U. Kokal, M. Celik, 'Development of BUSTLab Thrust Stand for mili-Newton Level Thrust Measurements', IEPC-2017-317, https://bogazicispacetechlab.github.io/files/conferences/39.pdf | full text extracted 2026-09-27 |
| SRC-POLK2017 | paper | Polk et al., Recommended Practice for Thrust Measurement in EP Testing, JPP 33(3) 2017 (as cited in SRC-REPO-INS) | via repo |
| SRC-SNYDER2017 | paper | Snyder et al., Recommended Practice for Flow Control and Measurement in EP Testing, JPP 33(3) 2017 (as cited in SRC-REPO-INS) | via repo |
| SRC-FCRI | institute web/search | Fluid Control Research Institute, Palakkad, https://www.fcriindia.com/calibration/ | search-result snippet: NABL-accredited flow labs (water, oil, air); low-flow sccm capability NOT found (verify) |
| SRC-NABL | accreditation body | NABL India, https://nabl-india.org/ (as recorded in SRC-REPO-MS) | via repo; no lab searched or contacted |
| SRC-MEMORY | memory | Items marked evidence_class 'memory_verify' are from background knowledge, not read in this session | verify before use |
