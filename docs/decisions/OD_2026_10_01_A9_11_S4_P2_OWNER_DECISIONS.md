# S4 (BLOCKS P2) OWNER DECISIONS (A9.11) — verbatim record, 2026-10-01

Recorded verbatim from the owner's message of 2026-10-01 (session chat), answering group S4 (S4.1–S4.7) of
`docs/budgets/owner_decisions/OWNER_QUESTIONS_SEQUENCED_v1.md`. Machine-readable companion:
`OD_2026_10_01_A9_11_s4_p2_owner_decisions.json`. Immutable after commit; later amendments are new addenda.

---

1. S4.1 — P1Q-01 — FREEZE THE STABLE-REGION FORM NOW; REGISTER NUMERICAL LIMITS BEFORE THE FIRST P1-S5 HANDOFF DWELL IS EVALUATED.
Adopt the existing `p1_reducer.classify_stable_region` form for the P1 → P2 stable-region handoff.
The registered criteria shall contain:
   * `min_duration_s`;
   * `max_abs_drift_rel_I_e`;
   * `max_abs_drift_rel_P_refl`;
   * `max_step_over_std`;
   * `min_ignition_success_fraction`;
   * and, where the calibrated P2 impedance chain is available during P1, the corresponding Z/impedance stability information shall also be recorded and carried into the handoff.
Do not set these numerical values after examining the P1-S5 handoff dwells.
Instead:
   * derive the limits from prior commissioning/characterization evidence from P1-S2 through P1-S4, including instrument noise, repeatability, time-base resolution, ignition transients and stable operating traces;
   * use the independent re-ignition evidence required by S3.3;
   * create a versioned `criteria_id`;
   * freeze and hash the complete criteria record before the first P1-S5 dwell is classified for P2 handoff.
P1-S5 data may then be evaluated only against those frozen criteria.
If the criteria are not registered beforehand, the handoff result remains `NOT_EVALUATED`; the raw dwell data are retained and may not be used to choose retrospective limits.
Passing the stable-region criteria means only `WITHIN_OWNER_CRITERIA` for the engineering P2 handoff. It is not an architecture PASS or a flight qualification.
Decision: form frozen now; numerical values evidence-derived and preregistered before first P1-S5 handoff evaluation.
2. S4.2 — P2Q-01 — YES: ZM-A PRIMARY, ZM-B PER-POINT CROSS-CHECK, ZM-C INDEPENDENT RESISTANCE CROSS-CHECK.
Adopt:
   * ZM-A: phase-resolved V/I measurement at RP-VI, de-embedded to the antenna-terminal reference plane RP-ANT — primary bench measurement of complex `Z_antenna = R + jX`.
   * ZM-B: complex-reflection/S-parameter de-embedding from RP-CPL through the characterized line and matching network — mandatory cross-check at every valid P2 bench map point.
   * ZM-C: calibrated antenna RF-current measurement together with verified delivered power — independent resistance / power-loading cross-check, not the primary complex-impedance method.
ZM-A and ZM-B shall report their individual uncertainty budgets. Agreement shall be evaluated under S4.3.
A missing or invalid ZM-B cross-check shall not silently convert ZM-A into independently verified impedance evidence.
Decision: YES — ZM-A primary, ZM-B per-point cross-check, ZM-C independent R cross-check.
3. S4.3 — P2Q-03 — USE THE NORMALIZED COMBINED-UNCERTAINTY FORM WITH `k = 2.0`, BUT DISTINGUISH METHOD DISAGREEMENT FROM PHYSICAL HYSTERESIS.
Freeze a common comparison factor:
`k_agreement = 2.0`
ZM-A versus ZM-B
Compare the complex impedance at the same operating point using the combined uncertainty of the two methods.
The comparison shall be performed on the real and imaginary components, or an equivalent covariance-aware complex comparison implemented by the reducer.
Conceptually:
`z_R = |R_A - R_B| / u_c(R_A - R_B)`
`z_X = |X_A - X_B| / u_c(X_A - X_B)`
Agreement requires the applicable normalized statistics to be `<= 2.0`.
If the methods disagree:
   * flag `METHOD_DISAGREEMENT`;
   * retain both raw measurements;
   * do not average them merely to obtain an intermediate value;
   * do not qualify ZM-B for later stand-only use until the disagreement is resolved.
Up/down sweep comparison
Use the same normalized-statistic threshold of 2.0, but do not treat an up/down difference as an instrumentation failure.
At the same registered factor level:
`z_hyst = |Y_up - Y_down| / u_c(Y_up - Y_down)`
where `Y` is the relevant map quantity.
   * `z_hyst <= 2.0` → `NO_HYSTERESIS_RESOLVED_AT_REGISTERED_UNCERTAINTY`
   * `z_hyst > 2.0` → `RESOLVED_HYSTERESIS`
A resolved hysteresis loop is a physical P2 finding and shall be preserved in the map. It is not automatically a FAIL.
Report hysteresis against both `P_forward` and verified `P_delivered`, as already required by HM-R05.
Decision: normalized combined-uncertainty comparison with `k = 2.0`; method disagreement is a metrology issue, while resolved up/down difference is a physical hysteresis finding.
4. S4.4 — P2Q-04 — YES: RE-TUNE EACH PRIMARY HOT-MAP POINT AND ALSO RUN FIXED-TUNE SUB-SWEEPS.
For the primary P2 hot impedance map:
   * at each operating point, re-tune the local matching network to the registered minimum-reflected-power condition;
   * log the complete matching-state ID, element positions/encoder values, tune time and measured residual reflection;
   * use only characterized tuning states or the verified interpolation rule of CAL-P2-03/04.
In addition, perform fixed-tune sub-sweeps around pre-registered representative regions.
Representative regions should include, where available:
   * a stable nominal operating region;
   * an operating-envelope edge;
   * regions near a detected E/H or impedance transition;
   * any region important to the later flight matching-network design.
The representative-point selection rule shall be recorded before the fixed-tune sub-sweep data are interpreted.
Fixed-tune measurements are required because a flight matching implementation cannot be assumed to reproduce unlimited laboratory retuning at every instantaneous operating condition.
The fixed-tune sub-sweeps supplement the primary re-tuned map; they do not replace it.
Decision: YES — re-tuned primary hot map plus fixed-tune sub-sweeps for flight-match design evidence.
5. S4.5 — P2Q-07 — YES: ACCEPT AN IN-HOUSE V/I-PROBE PHASE CALIBRATION WHEN NO SUITABLE ACCREDITED SCOPE EXISTS, SUBJECT TO TRACEABILITY AND VALIDATION.
If no ISO/IEC 17025/NABL laboratory is available with an appropriate scope for the required V/I-probe magnitude and relative-phase calibration at 13.56 MHz, an in-house calibration is acceptable.
The in-house procedure shall be traceable through the calibrated VNA and calibration kit and shall include, at minimum:
   * VNA and calibration-kit certificates / traceability;
   * complex V/I gain calibration at 13.56 MHz;
   * short/open/known-load checks as applicable at low level;
   * a precision 50-ohm reference;
   * at least one VNA-characterized reactive reference appropriate to testing phase accuracy;
   * RP-VI → RP-ANT fixture characterization or a verified declaration that the planes coincide;
   * pre/post calibration checks;
   * probe/cable temperature and phase-drift contribution;
   * repeatability;
   * full uncertainty propagation for magnitude and relative phase;
   * configuration IDs, raw data and hashes.
Because resistance can be highly sensitive to phase error for a low-R/high-X antenna, relative phase uncertainty shall be explicitly included and never inferred from magnitude calibration alone.
The low-level calibration shall also be followed by the already planned CAL-P2-15 at-power validation using the calorimetric 50-ohm load and VNA-known antenna-simulator load.
The record shall be identified as an in-house traceable calibration, not represented as an accredited-laboratory certificate.
If the resulting uncertainty is inadequate for the required impedance discrimination, the affected measurement is `NOT_EVALUATED_INSTRUMENT`; the uncertainty shall not be reduced administratively.
Decision: YES — in-house VNA-traceable phase calibration accepted where accredited scope is unavailable, with documented uncertainty and at-power validation.
6. S4.6 — P2Q-08 — YES: ICPQ-06 APPLIES TO THE PRESSURE-SENSING LINE WHEN IT BRIDGES ISOLATED POTENTIALS.
The ICPQ-06 electrical-isolation rule applies to every ICP plumbing or pressure-sensing path that can electrically bridge two intended isolated potentials.
Therefore, when the ICP body is floating and/or the collector is biased, the ICP-34 pressure-sensing line shall be evaluated as part of the isolation boundary if it connects the ICP-side plumbing to:
   * a grounded pressure transducer;
   * chamber/facility ground;
   * grounded tubing/manifold;
   * DAQ/instrument chassis;
   * or another electrical reference.
Where such a bridge exists, provide an appropriately rated isolating section and qualify the complete installed pressure-sensing path, not merely the nominal insulating component.
Verification shall include, as applicable:
   * the isolator;
   * fittings;
   * tubing;
   * pressure transducer/interface;
   * feedthroughs;
   * mounting;
   * representative pressure/gas condition;
   * electrical configuration corresponding to the floating/bias state.
The qualification must demonstrate that the sensing line does not create an unintended current-return path or invalidate the registered single-point grounding/isolation topology.
A pressure line that is demonstrably non-conductive and does not bridge potentials shall have that condition documented rather than being automatically subjected to an unnecessary duplicate test.
Decision: YES — wherever ICP-34 bridges isolated potentials, it falls under ICPQ-06 isolation qualification.
7. S4.7 — P2Q-09 — USE THE HM-R06 NON-OPTICAL INDICATORS WITH A `2.0 ×` COMBINED-UNCERTAINTY TRANSITION THRESHOLD.
Retain the photodiode as the required independent optical indicator under A9.4 P2Q-05.
When the optical classification is `UNLIT`, simultaneously examine the registered non-optical transition indicators:
   * step in reflected power and/or `|Gamma|` at fixed tuning state;
   * step in `R_antenna` and/or `X_antenna` where valid impedance data exist;
   * antenna RF-current step;
   * collector/electron-current or other registered current-path response step;
   * chamber/local pressure step associated with the event.
For each applicable indicator calculate the adjacent-state difference relative to its combined uncertainty.
Freeze:
`k_transition = 2.0`
An applicable indicator constitutes statistically resolved transition evidence when:
`|Delta y| / u_c(Delta y) > 2.0`
where the two measurements' covariance/correlation is included when established.
Classification rule:
   * optical `UNLIT` and no statistically resolved non-optical transition evidence → may remain `UNLIT`;
   * optical `UNLIT` but one or more registered indicators show a resolved transition → `UNCERTAIN`;
   * optical line of sight lost, saturated, or threshold unavailable → `UNCERTAIN` regardless of electrical indicators;
   * optical lit evidence is classified under the registered E/H rule rather than overridden by the electrical channels.
The record shall identify exactly which indicator(s) caused the `UNCERTAIN` classification in `electrical_indicator_basis`.
The `2.0 ×` criterion is deliberately conservative here: it does not declare that plasma definitely ignited. It merely prevents a record with conflicting evidence from being used as a proven `UNLIT` cold reference.
The form and `k_transition = 2.0` shall be frozen before the first P2 hot-map reduction and shall not be adjusted after observing transition locations.
Decision: HM-R06 indicator set accepted; `k_transition = 2.0`; optical UNLIT plus resolved non-optical transition evidence becomes UNCERTAIN.
