# R9 verification of web-track package v1

Date 2026-09-27; repo c1ce3a5 (read-only). Primary pages/PDFs fetched with curl (TLS unchanged, no captcha/paywall bypass, no contact); text extracted locally; quotes are verbatim from extracted text. Search-engine summaries used only to locate URLs.

## Checked values

| thread | item | status | verified value | locator / source |
|---|---|---|---|---|
| R6 | Moog XFC mass | **CONFIRMED** | < 974 g (< 2.2 lbm) | product page, spec table 'Mass'; https://www.moog.com/products/propulsion/space-propulsion/spacecraft-propulsion/systems-and-subsystems/xenon-flow-controller.html |
| R6 | Moog XFC flow range / inlet pressure / heritage | **CONFIRMED** | 3-23 mg/s GXe; 2.4-2.8 bar operating, MEOP 3.45 bar, 186 bar capable; heritage AEHF, Psyche, PPE, D2S2 | product page spec table; same as above |
| R6 | MaSMi LUC insert material (package: 'MaSMi LUC (LaB6...)'; 'lowest open LaB6 point is MaSMi 0.20 mg/s') | **CORRECTED** | Detailed description: LUC insert is BaO-W (OD 4 mm, ID 2 mm, L 7.25 mm); the heated-start 6 min / 0.20 mg/s procedure followed 'conditioning of the BaO-W insert'. LaB6 appears only in the life-model section (FIG. 14, Lafferty evaporation) - the patent is internally inconsistent. | US 10,919,649 B2 detailed description (LUC paragraph; cathode I-V paragraph); FIG. 14 caption for LaB6; https://patents.google.com/patent/US10919649B2/en (HTML sha256 f41c615c...) |
| R6 | MaSMi numbers: 0.20 mg/s normal operation, 2 A, 2-7 % flow fraction, 102 heaterless ignitions, 2.0-3.9 mg/s in 0.98 mg/s steps | **CONFIRMED** | as package | US 10,919,649 B2 detailed description; https://patents.google.com/patent/US10919649B2/en |
| R6 | BHT-1500 5-10 % cathode fraction ('verify locator') | **STILL_UNVERIFIED** | not in US 10,919,649 (patent mentions BHT-200 only) | patent full text searched for 'BHT', '5-10'; https://patents.google.com/patent/US10919649B2/en |
| R6 | Xe density at 150 bar (NIST) | **CONFIRMED** | identical (1.8580 @120, 1.9695 @150, 2.0725 @190 bar, 300 K) | NIST Webbook fluid isotherm tables, Xe C7440633; https://webbook.nist.gov/cgi/fluid.cgi?ID=C7440633&Type=IsoTherm ... |
| R3 | Schupp KD500 rating | **CONFIRMED** | as package | product page 'Heat resistance'/'Electrical values'; also product PDF KD500-Ceramic-Wires.pdf (sha256 5bd18a3f...); https://schupp.ch/en/p/kd500-winding-wires-with-ceramic-insulation-500c/ ; https://schupp.ch/wp-content/uploads/2026/09/KD500-Ceramic-Wires.pdf |
| R4 | Lake Shore F71 DC accuracy | **CONFIRMED** | single axis standard probe: ±0.15 % rdg on 3.5 T, 350 mT and 35 mT ranges (±0.2 % on 35 T); 3-axis MAGNITUDE ±0.30 % rdg (35 mT-3.5 T) | F71/F41 specification page, 'DC field measurement performance'; https://www.lakeshore.com/products/categories/specification/magnetic-products/gaussmeters-teslameters/f71-and-f41-teslameters |
| R4 | Lake Shore F71 temperature coefficient | **CONFIRMED** | as package | spec page footnote; same |
| R4 | Lake Shore F71 axis orthogonality | **STILL_UNVERIFIED** | not on the instrument spec page (probably on probe spec page, not fetched) | F71 spec page searched; same |
| R4 | MKS 627F accuracy | **STILL_UNVERIFIED** | - | datasheet 627F-DS.pdf; https://www.mks.com/mam/celum/celum_assets/resources/627F-DS.pdf |
| R4 | Xu & Walker 2009 thrust-stand uncertainty | **CONFIRMED** | ±0.6 %; 3.4 kW Hall up to 230 mN; range 1 mN-5 N; mass up to 250 kg | abstract, Rev. Sci. Instrum. 80, 055103 (2009), doi:10.1063/1.3125626, PMID 19485530; https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=19485530&rettype=abstract |
| R4 | IEC 60584-1 class 1 K/N | **CONFIRMED** | K/N class 1: -40...+1000 °C, ±1.5 °C or 0.0040·|t| (greater applies); class 2 -40...+1200 °C ±2.5 °C or 0.0075|t|; ASTM E230 Special K/N 0...1260 °C ±1.1 °C or ±0.4 %, Standard ±2.2 °C or ±0.75 % | WIKA data sheet IN 00.23 tolerance table (reproduces IEC 60584-1 / ASTM E230); IEC Table 12 itself is not in the open iTeh sample; https://www.wika.com/media/Technical-information/English/ds_in0023_en_co.pdf (sha256 677b5fc4...) |
| R4 | R/S usable range | **CONFIRMED** | R and S: continuous use oxidising or inert up to 1600 °C; 'Beware of embrittlement due to contamination' | WIKA IN 00.23, type descriptions; same WIKA PDF |
| R4 | W-Re vacuum/inert only; embrittles with O2 | **STILL_UNVERIFIED** | - | not found in WIKA IN 00.23; - |
| R4 | two-colour pyrometer emissivity/window handling | **CONFIRMED** | qualitatively, with the condition that attenuation/emissivity be equal at both wavelengths | Optris knowledge library, ratio method article; https://optris.com/us/knowledge-library/ratio-dual-two-colour-pyrometer/ (sha256 a09e92da...) |
| R4 | SRS RGA200 specs | **CONFIRMED** | as package | SRS RGA catalog, specifications table; https://www.thinksrs.com/downloads/pdfs/catalog/RGAc.pdf (sha256 c7bd8f93...) |
| R4 | Bird 5010B accuracy / frequency | **CONFIRMED** | ±5 % of reading (15-35 °C), ±7 % (-10-50 °C); peak ±8 % FS; 2 MHz-2.7 GHz element dependent | Bird 5010B/5014 specification sheet; https://testequipment.center/Product_Documents/Bird-5010B-Specifications-95309.pdf (distributor-hosted Bird sheet, sha256 61dacc8d...) |
| R4 | R&S NRT-Z14 frequency | **CONFIRMED** | 25 MHz to 1 GHz | NRT-Z14 operating manual 1171.6121.35; https://www.farnell.com/datasheets/2362740.pdf (sha256 ae0373c3...) |
| R4 | R&S NRT-Z14 power range and ~6 % (k=2) | **STILL_UNVERIFIED** | manual gives 120 W nominal and 'max. 300 W average forward' overrange; 6 % k=2 not in manual (datasheet not read) | manual searched; same |
| R4 | LEM IT 60-S principle | **STILL_UNVERIFIED** | - | datasheet URL returns HTML page without specs; https://www.lem.com/sites/default/files/products_datasheets/it_60-s_ultrastab.pdf |
| R4 | FCRI accreditation | **CONFIRMED** | as package | FCRI calibration page; https://www.fcriindia.com/calibration/ |
| R5 | CSIR-NPL CFCT | **CORRECTED** | 17025:2017 and CIPM-MRA confirmed; the '1 mg - 2000 kg' range is NOT on the page | CFCT page; https://www.nplindia.org/index.php/commercial-services/calibration-testing/ |
| R5 | ESA EPL pumping speed | **CORRECTED** | official lab page: 7 chambers, per-chamber pumping speeds 5,000 (N2), 23,600 (Xe), 53,400 (Xe), 80,000 (Xe), 260 (N2), 500 (N2), 25,000 (Xe) L/s; largest Ø2 x 5 m (Corona); pressure range 1e-5 to 1e-9 mbar confirmed | EPL page, 'Instruments & technical parameters' chamber table; https://technology.esa.int/lab/tec-m-epl-esa-propulsion-laboratory |
| R5 | UM LVTF | **CORRECTED** | 13 PHPK TM1200i + 6 PEPL cryopumps; 500,000 l/s Xe operating / 600,000 cold flow; Kr 600,000/660,000; previous ~190,000 l/s Xe (7 TM1200i). Only the 13 TM1200i pump N2/O2. | IEPC-2019-653 abstract and Sec. II.C; https://pepl.engin.umich.edu/pdf/IEPC-2019-653.pdf (sha256 f866e956...) |
| R5 | SITAEL IV4/IV10 figures (tools page) | **STILL_UNVERIFIED** | - | -; https://www.sitael.com/electric-propulsion/tools-services/ |
| R5 | UM APTF | **STILL_UNVERIFIED** | - | -; https://aero.engin.umich.edu/2025/11/17/... |
| R5 | CMTI NABL / roughness | **STILL_UNVERIFIED** | - | -; https://cmti.res.in/precision-metrology-calibration/ |
| R2 | RFP close date | **STILL_UNVERIFIED** | - | -; tdf.drdo.gov.in (connection reset x2); x.com/DrdoTdf (login-walled; search summary again says 20-Oct-2026 1700 h, pre-bid 24-Sep-2026); defproc captcha not attempted; both news articles (idrw, indiandefensenews) contain no date |
| R2 | RFP number | **STILL_UNVERIFIED** | news text re-confirmed 'XI/LM'; RFP cover not accessible | idrw.org article; https://idrw.org/drdo-seeks-air-breathing-propulsion-for-vleo-satellites/ |
| R1 | Li 2015 abstract values (500 mm, 56.47-57.85 %, 41.67-42.60 %, stage roles) | **STILL_UNVERIFIED** | bibliography confirmed: Vacuum 120 (2015) 89-95; abstract elided by publisher in OpenAlex and Semantic Scholar; ScienceDirect not accessed | -; https://api.openalex.org/works/doi:10.1016/j.vacuum.2015.06.011 |
| R1 | Romano 2021 volume/pages | **CONFIRMED** | 187, 225-235 | OpenAlex record; https://api.openalex.org/works/doi:10.1016/j.actaastro.2021.06.033 |
| R1 | Moon 2025 published version | **CONFIRMED** | AST vol 176, art. 112138 (2026); Moon, Ko, Yi, Jun | OpenAlex record; https://api.openalex.org/works/doi:10.1016/j.ast.2026.112138 |
| R1 | TAES2023 authors | **CONFIRMED** | Zuo, Xu, Huang, Li, Peng; IEEE TAES 59(5) 6863-6877 (2023) | OpenAlex record; https://api.openalex.org/works/doi:10.1109/TAES.2023.3282611 |
| R1 | AIP2016 authors ('possibly same group' as Li 2015) | **CORRECTED** | Binder, Boldini, Romano, Herdrich, Fasoulas (IRS Stuttgart group); AIP Conf. Proc. 1786, 190011 (2016) | OpenAlex record; https://api.openalex.org/works/doi:10.1063/1.4967689 |
| R1 | US 12,286,943 bibliographic data | **STILL_UNVERIFIED** | - | -; USPTO ppubs 403 earlier; not retried |
| R3 | other R3 'verify' items: ARMCO Curie ~770 C; 430F sulfide outgassing; Inconel/Ni-alloy oxidation and magnetism; Mo volatile oxide; Ta/Re LaB6 compatibility; Ni gaskets ferromagnetic; Kovar sleeve; Combat M vs M26 conductivity conflict; CoorsTek alumina; Kapton | **STILL_UNVERIFIED** | - | -; - |
| R4 | other R4 memory items: molbloc/DryCal low-flow specs; Hiden/Inficon RGA; ASTM E220 citation; spinning-rotor gauge route; O2 filament effect | **STILL_UNVERIFIED** | - | -; - |
| R5 | other R5 snippet items: RAM-EP phys.org, ABEP review, ULVAC cryo O2, ASTM E1508 scope, NABL CC-2153/CC-2704 | **STILL_UNVERIFIED** | - | -; - |

## Verbatim quotes (confirmed/corrected)

- R6 Moog XFC mass: "Mass < 2.2 lbm (<974 g)"
- R6 Moog XFC flow range / inlet pressure / heritage: "Operating Pressure / MEOP 2.4-2.8 / 3.45 bar (35-40 / 50 psia); 186 bar (2700 psia) capable ... Flow 3– 23 mg/sec GXe. Flow Split Ratio C:A = 5% (LV closed) or 9% (LV open)"
- R6 MaSMi LUC insert material (package: 'MaSMi LUC (LaB6...)'; 'lowest open LaB6 point is MaSMi 0.20 mg/s'): "At the core of MaSMi's LUC is a barium oxide impregnated tungsten (BaO—W) cathode insert with an outer diameter of 4 mm, an inner diameter of 2 mm, and a length of 7.25 mm. / ...following conditioning of the BaO—W insert. The heater was supplied with 5.5 A ... for 6 minutes. During the heating process, a 0.20 mg/s xenon flow rate was established"
- R6 MaSMi numbers: 0.20 mg/s normal operation, 2 A, 2-7 % flow fraction, 102 heaterless ignitions, 2.0-3.9 mg/s in 0.98 mg/s steps: "reduction of propellant flow to 0.20 mg/s to demonstrate normal cathode operation / cathode flow fraction ... of between 2-7% / 102 heaterless ignitions / 2.0-3.9 mg/s in increments of 0.98 mg/s"
- R6 Xe density at 150 bar (NIST): "293.15 150.00 2.0455 / 300.00 150.00 1.9695 / 323.15 150.00 1.6735"
- R3 Schupp KD500 rating: "Heat resistance: Permanent -90°C to +500°C (2500 hours min.) Short-term up to 800°C (tested for 10 days or 240 hours) and peaks up to 1000°C. Electrical values: Test voltage 150V AC, corresponding to 212V DC"
- R4 Lake Shore F71 DC accuracy: "35 mT (350 G) range ±0.15% of rdg ... 3-axis magnitude accuracy ... 35 mT (350 G) standard range ±0.30% of rdg"
- R4 Lake Shore F71 temperature coefficient: "Temperature coefficient of ±0.002% of rdg/°C beyond ±5 °C of instrument calibration temperature applies to all accuracy specifications."
- R4 Xu & Walker 2009 thrust-stand uncertainty: "The thrust of a 3.4 kW Hall thruster is measured for thrust levels up to 230 mN. The uncertainty of the thrust measurements in this experiment is +/-0.6%, determined by examination of the hysteresis, drift of the zero offset and calibration slope variation."
- R4 IEC 60584-1 class 1 K/N: "K NiCr-NiAl (NiCr-Ni) IEC 60584-1 1 -40 ... +1000 °C ±1.5 °C or 0.0040 ∙ | t |"
- R4 R/S usable range: "Type S thermocouples are suitable for continuous use in oxidizing or inert atmospheres at temperatures up to 1600 °C."
- R4 two-colour pyrometer emissivity/window handling: "a ratio pyrometer will only cancel out those losses if the attenuation is equal at both wavelengths ... if the transmittance of the path differs with wavelength, like non-grey attenuation, it effectively alters the measured emissivity ratio and introduces error"
- R4 SRS RGA200 specs: "RGA200 1 to 200 amu ... Resolution Better than 0.5 amu @ 10 % peak height ... Minimum detectable partial pressure 5 × 10–11 Torr (FC), 5 × 10–14 Torr (EM) ... Operating range 10–4 Torr to UHV (FC) 10–6 Torr to UHV (EM)"
- R4 Bird 5010B accuracy / frequency: "Accuracy True Average Power , ± 5% of reading (15 °C to 35°C), ± 7% of reading (-10 °C to 50°C), Peak Power, ±8% of full scale"
- R4 R&S NRT-Z14 frequency: "25 MHz to 1 GHz (R&S NRT-Z14)"
- R4 FCRI accreditation: "FCRI has full-fledged NABL accredited laboratories for the calibration of flow meters in water , oil and air media ... All our master instruments are traceable to National Physical Laboratory at New Delhi."
- R5 CSIR-NPL CFCT: "India is also a signatory of International Bureau of Weights & Measures (BIPM) and Mutual Recognition Arrangement (CIPM-MRA) ... Quality System as per ISO/IEC 17025:2017 and ISO 17034:2016"
- R5 ESA EPL pumping speed: "Pumping Speed [L/s] 5,000 (N2) 23,600 (Xe) 53,400 (Xe) 80,000 (Xe) 260 (N2) 500 (N2) 25,000 (Xe) / dedicated pumping system to reach pressure range from 10-5 mbar down to 10-9 mbar"
- R5 UM LVTF: "The upgraded facility has thirteen PHPK-TM1200i and six PEPL-developed-cryopumps ... measured effective pumping speed of 500,000 l/s for xenon for operating high power thrusters and 600,000 l/s for xenon cold flow / The PEPL cryopumps are not designed to reach temperatures low enough to cryopump nitrogen, oxygen ... only the thirteen TM1200i cryopumps will be relevant for such propellants."
- R2 RFP number: "The RPF, bearing the reference number, DTDF/06/13516/DSP/ABEP/XI/LM/01"
- R1 Romano 2021 volume/pages: "biblio volume 187, first_page 225, last_page 235"

## Arithmetic re-checks (r9_arith.py)

| check | package | recomputed | status |
|---|---|---|---|
| sccm->mg/s factors (MKS 0 C densities Xe 5.858, N2 1.250, O2 1.427 g/L) | Xe 0.097633, N2 0.020833, O2 0.023783 mg/s per sccm | 0.097633 / 0.020833 / 0.023783 | OK |
| R4 conversion table (9 rows) | 0.512/1.024/1.536/2.048/8.194/1.418/150.836/58.663/102.424 sccm | all within 0.03 % | OK |
| repo M_N2=28.0 ideal basis at max | 150.93 sccm, diff <0.1 % | 150.927 | OK |
| Alicat 25 C factor | 1.0915 | 1.09152 | OK |
| Alicat bound at 0.10 mg/s on 2 sccm FS | ±(0.8+0.39)=±1.2 % | 1.19 % on 0 C basis; on Alicat 25 C basis 0.10 mg/s = 1.118 sccm -> 0.8+0.36 = 1.16 % | OK (note basis) |
| Mooney 2-6 sccm in mg/s (R6) | 0.197-0.590 mg/s | 0.195-0.586 mg/s (MKS 0 C basis) | MINOR DISCREPANCY (+0.7-0.9 %; basis not stated) |
| 0.10 mg/s Xe in sccm; 1.5 A/sccm in A per mg/s | ~1.02 sccm; <=~15 A per mg/s | 1.024 sccm; 15.36 A per mg/s | OK |
| S_eff per mg/s at 1e-5 / 5e-5 Torr, 300 K | N2 66,818 / 13,364; O2 58,466 / 11,693 L/s | 66,818 / 13,364; 58,466 / 11,693 (M=28.0/32.0, 300 K) | OK |
| 3.2 mg/s N2 at 1e-5 Torr | ~214,000 L/s (R5); '208-214 k' (package §1) | 213,716 L/s at 300 K (M=28.0134); 208,836 at 293.15 K; 42,764 at 5e-5 Torr | OK - but the 208 k lower end is only the 293 K case; the package does not state the temperature spread |
| 2.5e-5 mbar in Torr | ~1.9e-5 Torr | 1.875e-5 | OK |
| 25 mN as mass | 2.55 g | 2.549 g (g0=9.80665); 12 mN = 1.224 g; 60 uN = 6.1 mg | OK |
| 0.5 % of 12 mN | ~60 uN | 60 uN | OK |
| per-start cathode Xe | 72 mg / 36 mg; heaterless 0.16-0.41 g (0.14 g) | 72.0 / 36.0 mg; 0.1595 / 0.408 / 0.140 g | OK |
| KM-5 cycle mean and 15,000 h starts | 1.84 h/cycle; ~8,100 starts | 1.842 h; 8,142 | OK |
| three years in hours | 26,280 h | 26,280 (365 d); 26,298 (365.25 d) | OK |
| tankage fractions | 0.086/0.081/0.106/0.078/0.067-0.076 | 0.0863/0.0809/0.1064/0.0776/0.0673-0.0764 | OK |
| 5-30 kg Xe volume | ~3-18 L at 1.67-1.83 g/cm3 (summary 2.7-18 L) | 2.73 L (5 kg @1.83) to 17.96 L (30 kg @1.67); 2.54-15.2 L at 1.97 | OK |
| ECR resonance B | 87.5 mT (2.45 GHz) / 207 mT (5.8 GHz) | 87.52 / 207.2 mT | OK |
| I_d <= 8.33 A | 8.33 A | 1500 W / 180 V = 8.333 A | OK |
| NIST Xe density values | 2.0455/1.9695/1.6735 g/cm3 @150 bar | identical from NIST Webbook today | OK |

## Corrections needed

1. R6 + package §1 (Xe): MaSMi LUC insert is BaO-W per US 10,919,649 detailed description (LaB6 only in life-model section/FIG. 14). The 0.20 mg/s @ 2 A point is not LaB6 evidence; rephrase 'No open source shows LaB6 spot mode...; lowest open point is MaSMi' accordingly.
2. R6: '5-10 % BHT-1500' is not in US 10,919,649 - remove the locator or mark unsourced; add Moog XFC primary datum 'Flow Split Ratio C:A = 5% (LV closed) or 9% (LV open)'.
3. R6/package: Moog XFC now read first-hand: '< 2.2 lbm (<974 g)', '3– 23 mg/sec GXe'; drop 'verify'; add D2S2 heritage.
4. R5: ESA EPL official page gives per-chamber speeds max 80,000 L/s (Xe); the 200,000 l/s claim is unsupported. Also note the published EPL balances (XP2004S load cell ±10 µN / 1 µN resolution; ICL balance 1-600 mN ±0.1 mN) - the package claim 'No published or commercial thrust stand demonstrates ~60 µN' should be re-examined against these (ranges/uncertainty definitions differ; verify applicability).
5. R5: UM LVTF - 13 TM1200i + 6 PEPL cryopumps; 500/600 kl/s is Xe; PEPL pumps do not pump N2/O2 (only the 13 TM1200i); previous config ~190 kl/s Xe.
6. R5: CSIR-NPL mass range '1 mg - 2000 kg' not on the CFCT page; keep as verify (KCDB).
7. R1: AIP2016 authors are Binder, Boldini, Romano, Herdrich, Fasoulas (IRS) - not 'possibly same group' as Li 2015; TAES2023 authors Zuo, Xu, Huang, Li, Peng, 59(5) 6863-6877; Moon AST vol 176, 112138; Romano 187, 225-235 confirmed.
8. R4: Lake Shore F71 35 mT range = ±0.15 % rdg single-axis (now read); 3-axis magnitude ±0.30 % rdg - use this for |B|. Orthogonality <0.2° still unverified.
9. R4: Bird 5010B accuracy ±5 % rdg only at 15-35 °C (±7 % at -10-50 °C); frequency 2 MHz-2.7 GHz.
10. R4: Xu & Walker 0.6 % confirmed from abstract; 0.002 g calibration-mass figure remains unverified.
11. R4: thermocouple class limits confirmed via WIKA IN 00.23 (secondary reproduction of IEC 60584-1/ASTM E230); add ASTM E230 Special K/N ±1.1 °C or ±0.4 %.
12. R4: two-colour pyrometry - add Optris caveat that cancellation holds only for equal attenuation at both wavelengths (non-grey viewport deposition introduces error).
13. R3: Schupp KD500 values confirmed from page and product PDF (sha256 5bd18a3f...); add nickel-migration >315 °C caveat and 20x-diameter test bend radius.
14. Package §1 facilities: state that 208 k L/s is the 293 K and 214 k the 300 K value (same 3.2 mg/s, 1e-5 Torr).
15. R6: Mooney 2-6 sccm = 0.195-0.586 mg/s on the MKS 0 °C basis (package 0.197-0.590); state basis or correct.
16. Still open (owner access): MKS 627F (403), LEM IT 60-S, R&S 6 % (k=2), SITAEL (captcha), APTF (403), CMTI (TLS failure), Li 2015 abstract (publisher-elided), RFP close date and number (tdf.drdo.gov.in reset, X login, defproc captcha).
