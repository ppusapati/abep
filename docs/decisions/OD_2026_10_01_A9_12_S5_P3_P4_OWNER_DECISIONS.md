# S5 (BLOCKS P3 / P4) OWNER DECISIONS (A9.12) — verbatim record, 2026-10-01

Recorded verbatim from the owner's message of 2026-10-01 (session chat), answering group S5 (S5.1–S5.14) of
`docs/budgets/owner_decisions/OWNER_QUESTIONS_SEQUENCED_v1.md`. Machine-readable companion:
`OD_2026_10_01_A9_12_s5_p3_p4_owner_decisions.json`. Immutable after commit; later amendments are new addenda.

---

1. S5.1 — ICPQ-10 — USE `1.20 × (P_fwd,max + P_d,max)` AS THE ICP-43 TOTAL-MODULE BOUND.
Select alternative A:
`Q_ICP,bound = 1.20 × (P_fwd,max + P_d,max)`
where:
   * `P_fwd,max` is the maximum admitted RF forward-power operating point from the registered ICP/P2 envelope; and
   * `P_d,max` is the applicable registered H-1 discharge-power bound.
Do not use `1.20 × 1.5 kW` merely because 1.5 kW is the spacecraft/bus ceiling.
The laboratory RF investigation capability is not automatically constrained inside that bus-power number, and the 1.5 kW value shall therefore not silently become an ICP thermal bound.
This expression is deliberately conservative. It is a thermal bounding rule, not a statement that all electrical input power is deposited in one ICP component.
Once measured P1/P2/P3 deposition and loss terms exist, replace the bounding decomposition with the measured coupled heat terms rather than relaxing the 20% margin.
Decision: alternative A — `1.20 × (P_fwd,max + P_d,max)`.
2. S5.2 — OQ-A907-03 — USE THE ADVERSE BOUNDING CORNER FOR DESIGN CLOSURE.
Evaluate the ≥50 K temperature-margin rule at the worst admissible combined thermal corner.
The bounding evaluation shall combine adverse values only where those values are physically and operationally capable of occurring together.
Do not create an impossible artificial corner by combining mutually exclusive states or known correlated extremes.
For each admissible bounding case:
   * apply the registered dissipated-load margin;
   * apply the appropriate environmental hot/cold boundary;
   * evaluate every temperature-limited node;
   * require at least 50 K margin below its applicable validated continuous-use temperature.
When Phase-1/P1/P2/P3 measured heat-deposition fractions become available, replace the current analog/assumed ranges with those measurements.
The 50 K requirement itself shall not be relaxed to accommodate later results.
Decision: bounding-corner method, restricted to physically admissible joint states.
3. S5.3 — OQ-A907-05 — ACCEPT SUPPLIER RATINGS AS PROVISIONAL LIMITS ONLY.
Supplier continuous-use ratings such as the present BN guide value and ceramic-wire rating may be used as provisional development limits until project-specific validation exists.
They may be used for:
   * preliminary thermal screening;
   * equipment protection;
   * design sensitivity;
   * procurement down-selection.
They shall not independently establish `T_validated,continuous` for flight/design closure.
Any thermal result whose margin depends on such an unvalidated supplier value remains `UNRESOLVED` / conditional.
Replace each provisional value with the applicable qualified material/component limit once P4, supplier qualification data or project testing provides it.
Decision: YES — provisional only; no flight/design closure from provisional ratings.
4. S5.4 — OQ-A907-06 — PURSUE THE THERMALLY ISOLATED MOUNT + DEDICATED RADIATOR; USE 50 W AS THE PROVISIONAL DESIGN REQUIREMENT.
Proceed with a thermally isolated H-1 mounting architecture and a dedicated thruster/module radiator or equivalent dedicated rejection path.
Until the spacecraft thermal ICD supplies the actual allowable interface heat, adopt the following owner allocation:
   * 50 W — provisional governing design requirement for steady heat conducted into the spacecraft mounting interface;
   * 100 W — contingency/sensitivity ceiling only;
   * 25 W — stretch case, not presently a mandatory design requirement.
Therefore, a design that meets only the 100 W case shall not yet be considered thermally closed against the provisional spacecraft interface.
The 50 W value is an owner design allocation, not a claimed spacecraft requirement. It shall be replaced by the actual spacecraft thermal ICD when that interface is available.
Continue to report the 25/50/100 W sensitivity cases so the impact of the eventual spacecraft requirement remains visible.
The dedicated radiator shall reject heat directly to the intended radiative environment as far as practicable rather than solving the thruster thermal problem by increasing spacecraft-interface conduction.
Decision: isolated mount + dedicated radiator; provisional governing mount-heat allocation = 50 W.
5. S5.5 — OQ-A907-08 — YES: THE EXTERIOR COATING GETS ITS OWN NODE TEMPERATURE LIMIT.
Once the selected Z-93-class or alternative exterior coating has a sourced or experimentally validated continuous-use temperature, treat it as an independent thermal node/material limit under the same rule:
`T_operating <= T_validated,continuous - 50 K`
The coating limit shall be based on the actual selected coating/substrate/application system, not merely the generic coating family name.
Until such evidence exists:
   * the coating-temperature limit stays OPEN;
   * no configuration relying on that coating for thermal closure receives a final thermal PASS;
   * sensitivity results may still be retained as engineering information.
Decision: YES — independent coating node limit with the same 50 K rule once evidence exists.
6. S5.6 — OQ-A907-09 — DO NOT APPLY A BLANKET 20% MULTIPLIER TO ENVIRONMENTAL LOADS.
Apply the 20% heat-load design margin to internally generated/dissipated loads, including the applicable discharge, RF/match, coil, cathode and other dissipative terms.
Do not automatically multiply solar, albedo and outgoing-IR/environmental terms by another 1.20 when those environmental cases are already represented by registered hot/cold bounding environments.
Environmental uncertainty shall instead be handled by:
   * the registered hot/cold environmental envelope;
   * applicable uncertainty/range in absorptivity/emissivity and geometry;
   * the physically adverse joint environmental case.
This avoids double-counting conservatism.
If a particular environmental quantity later proves not to contain its uncertainty/bounding allowance, explicitly enlarge that input's registered bound rather than applying an indiscriminate global 20%.
Decision: 20% margin applies to dissipated/internal heat loads; environmental loads use their registered bounding envelope and uncertainty treatment.
7. S5.7 — OQ-A907-10 — ACCEPT THE 10 K `SEARCH_SENSITIVE` SCREEN.
A thermal result whose remaining margin to the applicable design ceiling, after the existing search allowance, is less than 10 K shall be labelled:
`SEARCH_SENSITIVE`
The 10 K value is a numerical screening threshold only. It:
   * does not change PASS/FAIL/UNRESOLVED status;
   * does not replace the 50 K material margin;
   * does not create an additional 10 K thermal requirement.
Before any `SEARCH_SENSITIVE` result is used for LOCK-1 closure, independently verify the worst case using a stronger method, such as:
   * global optimization;
   * interval/bounding analysis;
   * exhaustive admissible-grid evaluation where tractable;
   * or another method demonstrated to bound the relevant search space.
If the independent analysis finds a more adverse condition, use that result; do not increase the search allowance after seeing the outcome.
Decision: YES — 10 K search-sensitivity flag + independent bound check before LOCK-1.
8. S5.8 — OQ-A910-06 — RETAIN 600 W AS A TEMPORARY RF-PATH HEAT ALLOCATION; REPLACE IT AFTER P2.
Retain:
`Q_RF,allocation = 500 W × 1.20 = 600 W`
as the present ICP RF-path thermal allocation.
Explicitly label 600 W as:
   * not a component rating;
   * not a demonstrated flight operating point;
   * not the ICP-43 total-module bound;
   * not a substitute for measured delivered RF power.
`P_line/match,loss` remains additional where applicable.
After the P2 impedance/matching map exists, re-derive the RF thermal input from the measured/verified envelope of:
   * `P_delivered`;
   * line/matching losses;
   * antenna/plasma loading;
   * associated uncertainty.
Apply the existing 20% design margin to the resulting admitted RF thermal basis.
Decision: YES — retain 600 W temporarily, then supersede it with the P2-derived RF thermal envelope.
9. S5.9 — P3Q-02 — ACCEPT MODEL CLASS A FOR LOCK-1, CONDITIONALLY.
Accept the current lumped H2-5 thermal network coupled through the P3 radiosity enclosure as the initial LOCK-1 thermal model class.
However, closure requires correlation against the integrated test article.
Use thermocouple/temperature measurements at the registered nodes and operating conditions to compare predicted and measured temperatures and thermal responses.
Before the correlation data are evaluated, pre-register:
   * sensor locations;
   * measurement uncertainty;
   * model-to-test comparison quantities;
   * admissible correlation residual/band;
   * treatment of sensor placement/contact uncertainty.
If the lumped model cannot reproduce the measured temperature distribution within the pre-registered correlation requirements, or if testing demonstrates important gradients/hot spots that the lumped nodes cannot represent, escalate to a finer multi-node / finite-element thermal model before claiming LOCK-1 thermal closure.
A finer model may also be introduced earlier for local component design without invalidating the lumped system-energy-balance model.
Decision: A — lumped network + test correlation; mandatory escalation to finer modelling if correlation is inadequate.
10. S5.10 — P4-OQ-01 — USE A STAGED VALIDATION STANDARD FOR `T_validated,continuous`.

Adopt a staged evidence hierarchy.
Stage 1 — coupon screening
Test each candidate under the applicable service-representative combination of:

* atmosphere/species;
* temperature;
* electrical bias/current condition;
* exposure duration;
* thermal cycling where applicable.

Acceptance metrics shall be pre-registered and include the applicable electrical, oxidation/recession, mass-loss and surface/material criteria.
The highest temperature satisfying the pre-registered criteria for the pre-registered coupon exposure may be recorded as a coupon-supported provisional continuous-use limit for design screening.
It is not by itself a flight-life qualification.
Stage 2 — integrated replaceable-component confirmation
Confirm the down-selected material in a replaceable anode/collector configuration on the H-1/ICP article under the applicable plasma, electrical and thermal environment.
The test shall demonstrate that the candidate remains within the pre-registered acceptance criteria at the intended continuous-use condition.
Only after this stage may the value be used as `T_validated,continuous` for the P3/LOCK-1 material-temperature closure.
Stage 3 — qualification/life evidence
Full-duration or justified accelerated-life qualification remains separately required before a final flight-life claim.
Therefore, do not equate melting point, short vendor exposure, generic air-use temperature or a brief coupon test with continuous-use validation.
Decision: staged coupon screening → integrated replaceable-component confirmation → later flight/life qualification.

11. S5.11 — P4-OQ-02 — USE A BROAD Q0 SCREEN, THEN DOWN-SELECT FOR Q1.

Do not put every material variant through the full electrically loaded Q1 campaign.
Q0 screening matrix:
Include the R8-C01..C09 families with these dispositions:

* R8-C01: 316L — engineering/reference control only.
* R8-C02 chromia-forming Ni alloys: IN600, IN625 and Haynes 230. Include X-750 as an additional Q0 comparison if readily available. Do not test unspecified generic “Hastelloy”; an exact grade must be declared before admission.
* R8-C03 alumina-forming candidates: IN601, Haynes 214 and one explicitly specified FeCrAl grade.
* R8-C04: Rh-coated 316L candidate.
* R8-C05: Pt-clad/plated 316L candidate.
* R8-C06: Cr-plated 316L candidate.
* R8-C07: IrO2/RuO2-type conductive-oxide/MMO candidate with the exact coating system and substrate declared.
* R8-C08: bare tungsten retained only as a negative/reference-control material where useful; not restored as the baseline anode candidate.
* R8-C09: specified isotropic graphite retained as a reference/control coupon.

Do not add Ti, TiN/ZrN, bulk Cu or bulk Ir to the baseline Q0/Q1 campaign now. Keep them as reserve candidates that require a specific hypothesis/need before activation.
Q1:
Advance only the Q0 survivors that meet the pre-registered screening criteria. Q1 then performs electrically loaded plasma exposure under the applicable biased/floating configurations.
Each coating candidate shall record coating composition, thickness, deposition process, substrate, surface preparation and lot/process provenance. A coating family name alone is insufficient.
Decision: broad R8-C01..C09 Q0 screening with the named variants above; evidence-based down-selection before Q1.

12. S5.12 — P4-OQ-03 — FREEZE NUMERICAL ACCEPTANCE THRESHOLDS AT LOCK-2 AFTER METROLOGY COMMISSIONING, BEFORE ACCEPTANCE-BEARING EXPOSURE.

Select the LOCK-2 alternative.
First establish the actual Q0/Q1 measurement capability, including:

* resistance repeatability/resolution;
* mass-change detection limit;
* profilometry/recession resolution;
* SEM/XPS capability where applicable;
* coupon-to-coupon/process repeatability;
* AO/ion exposure dosimetry capability.

This metrology commissioning may use standards, blanks, controls or sacrificial commissioning coupons.
Then, before any acceptance-bearing candidate exposure is performed, freeze:

* allowable resistance-rise threshold;
* mass-loss/recession limits;
* sputtering/erosion acceptance;
* required exposure duration/fluence;
* applicable uncertainty treatment;
* acceptance/rejection logic.

Do not use the performance of the candidate coupons themselves to choose thresholds that they subsequently have to pass.
If the metrology capability is inadequate to resolve the desired acceptance criterion, return `NOT_EVALUATED_METROLOGY`; do not widen the material acceptance criterion simply to fit the instrument.
Decision: LOCK-2 after metrology commissioning, but before acceptance-bearing coupon exposure.

13. S5.13 — P4-OQ-04 — DO BOTH: ACQUIRE THE BEST AVAILABLE SPECIES-RESOLVED DATA AND MEASURE PROJECT CANDIDATES.

Authorize lawful acquisition through:

* library access;
* inter-library loan;
* publisher purchase;
* institutional subscriptions;
* other legitimate licensed routes

of species-resolved sputtering-yield information for the relevant N+, N2+, O+ and O2+ interactions where available.
In parallel, use the project ion-beam/materials test route for the down-selected candidate materials/coatings where published evidence is absent, non-representative or insufficient.
Literature data shall be used for:

* prior bounds;
* test-matrix selection;
* comparison;
* model initialization.

Project measurements shall provide candidate-specific evidence under the relevant ion species/energy/angle/material condition.
Do not silently substitute elemental-target literature yields for an alloy/coating where composition or surface chemistry materially changes the interaction.
Decision: BOTH — lawful data acquisition plus candidate-specific measurement.

14. S5.14 — P4-OQ-05 — ADD THE NEGATIVE-BIAS COLLECTOR SET AND RETAIN A FLOATING CONTROL.

The collector material coupon programme shall include the actual service polarity:

* negative-biased collector coupons, representing the ion-collecting collector condition; and
* floating coupons as the matched control/reference.

The polarity is therefore frozen now.
Do not invent the numerical collector-bias voltage for the material test campaign.
The bias magnitude and relevant ion-energy exposure shall be derived from the measured P1 collector operating envelope and associated plasma/sheath evidence before the acceptance-bearing biased exposure is run.
Where Q0 screening needs an electrical-bias capability before P1 is complete, it may verify the fixture/process, but such exposure shall remain engineering-only and shall not be represented as the final service-condition qualification.
Decision: negative-bias + floating collector coupon sets; numerical bias from P1 evidence.
