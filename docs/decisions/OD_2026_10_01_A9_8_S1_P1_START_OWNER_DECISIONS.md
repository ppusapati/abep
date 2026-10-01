# S1 (BLOCKS P1 START) OWNER DECISIONS (A9.8) — verbatim record, 2026-10-01

Recorded verbatim from the owner's message of 2026-10-01 (session chat), answering group S1 (S1.1–S1.16) of
`docs/budgets/owner_decisions/OWNER_QUESTIONS_SEQUENCED_v1.md`. Machine-readable companion:
`OD_2026_10_01_A9_8_s1_p1_start_owner_decisions.json`. Immutable after commit; later amendments are new addenda.

---

1. S1.1 — P1Q-04 — YES.
Apply the UBQ-06 thermal abort rule to all P1 operation, including non-scoring engineering runs. Abort/derate when the relevant component reaches its validated continuous-use temperature limit minus 50 K. Engineering hardware should not be permitted to exceed a protection rule simply because the run is non-scoring.
2. S1.2 — P1Q-09 — DEDICATED ISOLATED TARGET; DO NOT USE THE CHAMBER WALL.
Use a dedicated, isolated, instrumented electron-collecting target for both ICP45_CAPACITY and the corresponding engineering-surface measurements so that the electrical topology remains comparable.
For the P1 engineering article, use a planar/annular isolated target centred on the ICP axis, perpendicular to the axis and positioned immediately downstream of the ICP outlet on a mechanically registered/adjustable axial datum. Final diameter, axial distance and support dimensions shall be taken from the actual ICP module drawing and registered at P1-G0; do not invent dimensions before the module geometry exists. 316L is acceptable for the Ar engineering article only; this does not freeze the flight collector material.
Define the electrical reference so that the ICP ion-collecting electrode is biased negative with respect to the dedicated electron-collecting target. Record the collector/reference potential explicitly. Meter all intentional current paths/terminals: `collector_supply`, `icp_body`, `facility_ground`, `electron_collector`, `h1_body`, and `hall_anode`; a terminal may be declared `OPEN_CIRCUIT_BY_CONSTRUCTION` only where that physical state is verified.
The grounded chamber wall shall not be used as the electron collector, including for the comparable P1-S4 engineering-surface records.
3. S1.3 — P1Q-11 — DERIVE THE PRESSURE-MATCH TOLERANCE FROM THE ACTUAL GAUGE.
Do not invent a fixed pressure percentage now. Determine pressure repeatability/uncertainty from the installed chamber gauge during P1-S2/P1-S3 commissioning and pre-register the RF-ON/RF-OFF pressure-match tolerance before the first P1-S4 matched pair. It must thereafter remain fixed for that campaign and must not be widened after seeing the results. An unmatched pair is excluded as already defined by P1-IT-51.
4. S1.4 — P1Q-18 — CONFIRMED.
Apply the full instrument-adequacy criterion
`3 u_R > 0.02 |I_e,collector|`
to the RF-ON ICP45_CAPACITY candidate record.
For the matched RF-OFF/background record, use the existing floor-based statistical/fractional closure treatment with `I_scale,min`. A fractional-only RF-OFF resolution failure becomes `NOT_EVALUATED_INSTRUMENT`; it is not automatically an exclusion.
5. S1.5 — P1Q-20 — YES.
Do not automatically assign `u(I_anode) = 0` merely because the anode is open/floating by construction. The measured insulation leakage from P1-S0/DWV shall be carried into the uncertainty budget as the zero-offset/leakage contribution whenever it is non-negligible compared with the calibrated current-channel uncertainty.
Only when the measured/qualified leakage upper bound is demonstrably negligible relative to the measurement uncertainty may the open-circuit term effectively contribute zero uncertainty. Never silently default a measurable leakage to zero.
6. S1.6 — P2Q-02 — CREATE A SEPARATE RF-METROLOGY PACKAGE.
Keep the RF power-generation/matching hardware separate from the measurement equipment. Put the V/I probe, VNA, calibration kits, fixed attenuators, antenna-simulator load, antenna current probe, phase-stable VNA cables and associated calibration accessories in a dedicated RF-metrology package under the common interface specification.
This preserves supplier specialisation and prevents the RF source vendor from implicitly defining the measurement chain used to validate its own equipment.
7. S1.7 — P3Q-01 — OPTION C: BOTH, WITH CALORIMETRY AS PRIMARY HEAT-LOAD EVIDENCE.
Provide both collector calorimetry and plasma diagnostics. Use the calorimetric collector energy balance as the primary evidence for `Q_collector`: calibrated temperature measurements, registered thermal conductances/thermal mass, RF-ON/RF-OFF comparisons and collector-current/bias steps.
Add a Langmuir-probe diagnostic near the collector for the Ar P1 development campaign to estimate electron temperature and plasma potential and provide an independent sheath-model cross-check. Probe measurements should preferably be taken in matched diagnostic runs; they must not contaminate an ICP45 capacity record unless probe perturbation has first been shown negligible.
Therefore: C — both; calorimetry primary, probe/sheath calculation cross-check.
8. S1.8 — OQ-RFQV2-01 — NABL/ISO-17025 CERTIFICATE NOT MANDATORY FOR THE P1 Ar MFC.
Accept the manufacturer's Ar-specific calibration certificate plus our in-house rate-of-rise/transfer verification for the P1 Ar engineering campaign. An ISO/IEC 17025/NABL certificate is desirable but not mandatory because Ar is being used here for engineering/non-scoring development. Score-bearing gas/flow measurements remain subject to their stricter traceability requirements.
9. S1.9 — OQ-RFQV2-02 — REQUEST PUMPING QUOTATIONS. DO NOT ASSUME PUMPING EXISTS.
RFQ2-VAC shall include the P1 pumping train/pumping capability in the quotation scope. We have no registered, qualified existing pumping system on which the P1 campaign can presently rely.
If IIST or another test facility later provides a suitable chamber and pumping train, it can be accepted only after its pumping speed, pressure range, gas compatibility, instrumentation and conductance at the P1 interface have been documented and verified. Until then the project shall treat pumping as a required infrastructure item.
10. S1.10 — OQ-RFQV2-03 — YES.
One physical 50-ohm calorimetric RF dummy load may serve both purposes, provided the supplier separately certifies/documentes:
its RF load function and rating/return loss at 13.56 MHz, and its calorimetric measurement method, calibration and uncertainty.
The same device may therefore be RF-L08/RF-L09 functionally, but the two acceptance functions remain separately verified in the evidence record.
11. S1.11 — OQ-RFQV2-04 — YES, ACCEPT THE PROPOSED PACKAGE PLACEMENT.
Accept the RFQ-v2 supplier-speciality allocation:
collector/bias supply and C1 cathode/keeper/heater hardware under Hall electrical; Xe tank/PMU/FCU under gas/metrology; power analyser and RF metrology under RF; and facility/calibration items distributed between vacuum/facility and thrust/metrology as already mapped.
No architecture meaning should be inferred from the procurement-package boundary.
12. S1.12 — OQ-RFQV2-05 — INCLUDE THE MAGNET SUPPLY IN THE P1 QUOTATION SET.
Do not assume an existing laboratory magnet supply is available. Include HE-L02/the required MC-1 laboratory magnet supply channel(s) in the P1 quotation package.
They shall be current-controlled, floating where required, with 4-wire remote voltage sensing and recorded current/voltage, with final V/I ratings following the MC-1 coil design. If a suitable laboratory supply is subsequently identified and verified against these requirements, it may replace the quoted unit.
This remains quotation/specification only, not authorization to purchase.
13. S1.13 — OQ-RFQV2-06 — YES.
Apply the same 350 V operating-class isolation basis, ≥525 V design withstand and 1.05 kV DC / 60 s initial DWV to the H-1 anode/discharge-supply isolation and feedthrough paths that can experience the corresponding potential difference.
This closes the present row-81 transient/qualification-margin question for that DC isolation class. It does not close RF antenna/matching-network insulation, Paschen-risk gas paths or combined RF+DC stress; those remain separately qualified.
14. S1.14 — OQ-RFQV2-08 — BOTH SUPPLIER AND IN-HOUSE.
Require a supplier/factory DWV certificate wherever the component/feedthrough rating permits the 1.05 kV / 60 s test, and then perform an in-house current-limited 1.05 kV DC / 60 s DWV test on the assembled insulation configuration before first HV/RF operation.
Sensitive electronics may be disconnected where necessary. Record test voltage, duration, leakage current, pressure/gas condition where relevant, insulation path ID, configuration and pass/fail observations. Supplier testing does not replace the assembled-system test because assembly, cabling, feedthrough installation and grounding can create new failure paths.
15. S1.15 — P1-IT-52 — REGISTER STAGE-SPECIFIC DOMAINS FROM REAL HARDWARE; DO NOT INVENT NUMBERS NOW.
Owner decision: every P1 stage shall have its operating domain frozen before the first record of that stage, using the procured/calibrated hardware capability, P1-G0 safety limits and the pre-registered run matrix.
Register, as applicable, `P_fwd_W`, `p_chamber_Pa`, `mdot_Ar_H1_mg_s` and `V_collector_V` as explicit `[min,max]` ranges under a unique `domain_id`.
The existing 0–500 W figure is only the laboratory RF investigation capability, not permission to declare every P1 stage as 0–500 W. Pressure limits must come from the qualified chamber/gauge/pumping system; flow limits from the calibrated Ar MFC and gas path; collector-voltage limits from the selected bias supply and verified isolation configuration.
No result outside its registered stage domain may be interpreted as a test failure; it remains `OUT_OF_DOMAIN`.
Therefore no fabricated numerical pressure, flow or collector-bias limits are authorized at this point.
16. S1.16 — P1-IT-55 — USE A PER-PATH DOCUMENTED LEAKAGE LIMIT; DO NOT CREATE A UNIVERSAL ARBITRARY µA VALUE.
At 1.05 kV DC / 60 s, every insulation path shall satisfy: no flashover, breakdown, tracking, disruptive discharge or protective trip, and measured leakage must remain below a pre-registered numerical limit for that specific insulation path.
That numerical limit shall be taken from the most restrictive applicable documented component/feedthrough/insulator qualification or supplier acceptance specification, with the assembled-system measurement uncertainty included. The limit must be registered before the DWV test and may not be changed after seeing the result.
If an insulation path has no documented allowable leakage/insulation-resistance basis from its selected hardware, that path remains `G0_NOT_EVALUATED_TBD`; it shall not be declared qualified by inventing a generic leakage-current limit.
The measured leakage from the accepted DWV/isolation configuration shall also feed P1Q-20/P1-IT-49 as the relevant zero-offset/leakage uncertainty contribution.
