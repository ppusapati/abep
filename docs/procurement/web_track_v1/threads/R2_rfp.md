# R2 - RFP requirement interpretation (access 2026-09-27)

**RFP obtained: NO.** The RFP document was NOT obtained. Official hosts: tdf.drdo.gov.in unreachable (503/reset); defproc.gov.in captcha-gated (not attempted); drdo.gov.in lists no current TDF projects and no ABEP announcement found; X blocked (402). Only two secondary news articles were read first-hand. No page/section/para of the RFP could be cited.

## Sources
- S1: https://www.indiandefensenews.in/2026/09/drdo-issues-rfp-for-indigenous-air.html - secondary news article (Indian Defence News, 09 Sep 2026, credited 'Agencies') - open; raw HTML read first-hand (r2_src/idn_article.html)
- S2: https://idrw.org/drdo-seeks-air-breathing-propulsion-for-vleo-satellites/ - secondary news article (idrw.org, 09 Sep 2026) - open; raw HTML read first-hand (r2_src/idrw_article.html)
- S3: https://drdo.gov.in/drdo/en/announcement/rfp-project-development-close-formation-flying-multiple-drones-be-executed-under-tdf - official DRDO announcement for a DIFFERENT TDF RFP (used only to establish the publication route) - open; read first-hand
- S4: https://drdo.gov.in/drdo/en/offerings/projects - official DRDO TDF projects listing - open; read; shows 'No Content. Kindly Visit Archives'
- S5: https://tdf.drdo.gov.in/project - official TDF project website - NOT ACCESSED: HTTP 503 (WebFetch) / connection reset (curl) on every attempt
- S6: https://defproc.gov.in/nicgep/app - Defence eProcurement Portal (where TDF RFP documents are published per S3) - NOT ATTEMPTED: tender search/document download is captcha-gated; not bypassed per rules
- S7: https://x.com/DrdoTdf - official TDF X account - NOT ACCESSED: HTTP 402; content known only through web-search summaries (not verified)

## Clauses (all from secondary sources; no RFP locator available)

| topic | quote | locator | readings | ambiguous | repo | discrepancy |
|---|---|---|---|---|---|---|
| RFP identifier | DTDF/06/13516/DSP/ABEP/XI/LM/01 | S2 para 2 (news; not the RFP) | S2 transcription 'XI/LM'; repo 'X/L/M' | True | DTDF/06/13516/DSP/ABEP/X/L/M/01 (CLAUDE.md, rtm_v1.json rfp_id) | Suffix differs ('XI/LM' vs 'X/L/M'); either may be a transcription error; verify against the RFP cover page. |
| Project title / route | “Air Breathing Space Based Propulsion (Electric) for VLEO” ... ‘Grant-in-Aid’ ... two-bid package | S2 para 2 | TDF grant-in-aid, two-bid (technical-commercial + price) via Defence Procurement Portal | False | not recorded | none (new information, secondary) |
| (a) Mass | maintain a total mass under 40 kg | S1 para 6 (news paraphrase; RFP clause not seen) | total propulsion-system mass < 40 kg; whether Xe/consumables, tank, intake, PPU are included is NOT stated in any accessed text | True | < 40 kg (R1); R3 reads incl. intake, compressor, PSE, Xe + tank, structure, 10 % margin; OD7 strict vs <= | R3 inclusion list (Xe + tank, 10 % margin) is not supported by any accessed text; 'total' in S1 is compatible but not decisive. Owner decision (OD7) remains; Xe inclusion unverified. |
| (b) Air + Xe | ambient atmospheric air supplemented with Xenon | S1 para 5 (news paraphrase) | Xe as supplementary/augmenting propellant to air (supports R3 'Xe topping' flavour); Xe as alternative/backup mode; Xe for startup/cathode only; mixed feed | True | 'air + Xe' (R1); 'Xe as propellant; Xe anode topping to 25 mN' (R3); OD6 open | 'supplemented' is news wording, not RFP text; no durations, no mode (nominal vs fallback) found. OD4/OD5/OD6 cannot be settled from accessed sources. Owner decision. |
| (c) Thrust | demonstrate sustained thrust levels between 12 mN and 25 mN | S1 para 4 (news paraphrase) | (i) operating window [12,25] mN, 25 as cap; (ii) throttle range to be covered 12..25 mN (both ends demonstrated); (iii) 12 mN floor, 25 mN peak (R3) | True | 12-25 mN (R1/R2); R3 '12 mN sustained on air, 25 mN peak with Xe topping'; OD1 open | 'sustained ... between 12 and 25' reads more like a sustained range than R3's 'peak with Xe'; altitude/power/propellant at which thrust applies not stated. Owner decision (OD1, OD4). |
| (d) Altitude | orbital altitudes ranging between 180 km and 230 km | S1 para 4 | every altitude in band (OD2); some altitude in band | True | 180-230 km | none in value; quantifier (OD2) unresolved |
| (d) Power | strict power budget of less than 1,500 W | S1 para 6 | total system power at spacecraft bus; PPU input only; steady vs every mode (OD8) | True | < 1.5 kW (R1), power_max_W 1500 (R2); R3 '< 1500 W total' | value agrees; boundary and mode scope not stated in accessed text (BUS_POWER_BOUNDARY rule 6, OD8 remain open) |
| (d) Life | mission life requirement has been set at three years | S1 para 7 | 3 years ~ 26,280 h calendar (repo 26,000 h) | True | 26,000 h mission; > 15,000 h firing/ignition (R1,R2,R3,R5) | S1 gives 'three years', not 26,000 h; NO accessed source mentions the > 15,000 h firing/ignition requirement (OD13 unverifiable). |
| (d) Hall preferred | preference for a Hall-effect thruster configuration | S1 para 5 | preference, not mandate | False | Hall preferred | none (secondary) |
| (d) Indigenous content | minimum of 75 percent | S1 para 8 | total IC >= 75 % | False | ic_total_min 0.75; subsystem minima 0.80/0.80/0.60/0.70 (R2) | total agrees (secondary); subsystem minima not found in any accessed source |
| (d) Deliverables / TRL / testing / facilities / AO test / redundancy / nascent O / ignition | - | not found in any accessed source | - | True | R6 'RFP 4.1a' AO-beam test, 'ionise nascent O'; R7 no single-point failure; 'Part III Para 2' (R2) | none of these clauses, nor the 'Part III Para 2' / '4.1a' locators, could be verified; all remain 'verify against RFP document' |
| Bid close / pre-bid | - | not read first-hand; web-search summaries attributed to @DrdoTdf give BOTH '05-Oct-2026 1700Hrs / pre-bid 15-Sep-2026 1100Hrs' AND '20-Oct-2026 1700Hrs / pre-bid 24-Sep-2026 1500Hrs' | 05 Oct 2026 (repo); 20 Oct 2026 (possible extension/corrigendum) | True | bid close 05 Oct 2026 | Possible corrigendum/extension to 20 Oct 2026 - NOT VERIFIED; check defproc/tdf site before relying on 05 Oct. |

## Discrepancies
- RFP number suffix: repo 'X/L/M/01' vs idrw 'XI/LM/01' (S2).
- Bid close: repo 05 Oct 2026; unverified search summaries also show 20 Oct 2026 with pre-bid 24 Sep 2026 (possible corrigendum).
- Mission life: S1 'three years' vs repo 26,000 h (3 y = 26,280 h); rounding origin unverified.
- > 15,000 h firing/ignition: not found in any accessed source.
- Mass inclusion list (Xe + tank, 10 % margin) in R3: not supported by any accessed text; S1 says only 'total mass under 40 kg'.
- Thrust: S1 'sustained thrust levels between 12 mN and 25 mN' does not mention the R3 split '12 mN on air / 25 mN peak with Xe topping'.
- Xe: S1 'air supplemented with Xenon' vs repo 'air + Xe'; mode (nominal/startup/backup/mixed) unstated.
- IC subsystem minima (R2), AO-beam test 'RFP 4.1a' (R6), 'ionise nascent O' (R6), no single-point failure (R7), 'Part III Para 2' (R2): none verifiable.

## Unresolved (owner)
- Obtain the RFP (defproc tender documents or tdf.drdo.gov.in project page) through legitimate owner access; captcha/login is the owner's action.
- OD1, OD2, OD4, OD5, OD6, OD7, OD8, OD13, OD14 and BUS_POWER_BOUNDARY rule 6: owner decisions; cannot be settled from accessed sources.
- Confirm RFP number suffix and bid-close date (possible corrigendum).
