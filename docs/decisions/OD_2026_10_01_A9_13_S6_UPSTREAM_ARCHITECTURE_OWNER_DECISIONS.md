# S6 (UPSTREAM ARCHITECTURE) OWNER DECISIONS (A9.13) — verbatim record, 2026-10-01

Recorded verbatim from the owner's message of 2026-10-01 (session chat), answering group S6 (S6.1–S6.22) of
`docs/budgets/owner_decisions/OWNER_QUESTIONS_SEQUENCED_v1.md`. The same message approved the checkpoint-6 merge
(PR ppusapati/abep#36). "RFP(1)" markers are the owner's citations of the official RFP document; that document is not yet
registered in the repository (see S6.22 / AG-15). Machine-readable companion:
`OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json`. Immutable after commit; later amendments are new addenda.

---

Checkpoint-6 merge is approved. You may merge the A9.7 verified design-synthesis checkpoint together with the A9.8–A9.12 decision records into `main`. The S1–S5 decisions remain text-only at that checkpoint; applying them to code/artifacts and implementing S2 should remain subsequent controlled changes.
For S6, I would close all 22 as follows. The most important correction is S6.21: the official RFP does not establish 0.38 mg/s or 1.3 mg/s as a flight requirement. It specifies 180–230 km operation, intake sizing based on density/solar activity, and 12–25 mN thrust for drag compensation. RFP(1)
Owner Answers — S6 Upstream Architecture

1. S6.1 — F1Q-02 — LABELLED STRUCTURAL ASSUMPTION FOR BUDGETING ONLY; SOURCED DESIGN REQUIRED BEFORE LOCK-1.
Until the actual intake structure is designed, wall material, wall thickness, AO coating system/density and support fraction may be carried as explicitly labelled `PARAMETRIC_SENSITIVITY` / budgeting assumptions.
They shall not generate a CBE, frozen intake mass or structural qualification statement.
Before LOCK-1 the intake requires a sourced/buildable structural definition including material, wall thickness, manufacturing method, support/frame geometry, AO protection, coating thickness/density, tolerances, mass calculation and applicable structural/thermal evidence.
Decision: assumptions permitted for budgeting only; sourced design mandatory before LOCK-1.
2. S6.2 — F1Q-03 — DO NOT DECLARE 0–5° ADEQUATE WITHOUT THE AOCS POINTING BUDGET.
The intake pointing envelope shall be an explicit spacecraft/AOCS interface requirement.
The existing 0°, 2°, 5° data may remain as the current sensitivity set, but 5° shall not be treated as the validated maximum pointing error merely because the existing frozen surface stops there.
For intake-surface v2:
   * first register the required relative-wind pointing envelope from the spacecraft/AOCS design;
   * build the frozen surface over that complete registered envelope;
   * use direct TPMC during development for required angles not yet represented by the frozen surface;
   * never extrapolate silently beyond the frozen angular domain.
Decision: 0–5° is sensitivity only; v2 must cover the eventual registered AOCS pointing envelope.
3. S6.3 — F2-OQ-01 — FILTER BASELINE = NON-PROPELLANT CONTAMINATION/DEBRIS PROTECTION WHILE PRESERVING THE ATMOSPHERIC PROPELLANT.
The baseline filter shall protect the compressor/upstream gas chain primarily against:
   * intake-borne particulate contamination;
   * foreign debris;
   * manufacturing/released particulates that can reach the compressor.
Atomic oxygen is not a contaminant to be intentionally removed in the baseline architecture. The RFP explicitly requires the propulsion system to handle N2 and nascent/atomic oxygen. RFP(1)
Ambient charged-particle removal is not a baseline filter requirement unless a later hazard analysis demonstrates a need.
Compressor wear products are downstream-generated; the intake filter shall not be credited with removing them unless actual backstream transport is demonstrated. If downstream wear debris needs interception, provide a separately defined downstream guard/trap.
Quantitative filter acceptance shall be pre-registered before LOCK-1 in terms of:
   * capture efficiency versus registered contaminant/particle class;
   * species-resolved propellant transmission;
   * pressure-loss/conductance penalty;
   * O recombination/conversion probability;
   * retained contaminant capacity;
   * AO erosion/material durability;
   * effect on AG-12 feed-state closure.
Numerical values shall come from the defined contamination environment, H-1 feed requirement and measured filter material/geometry—not arbitrary defaults.
Decision: particulate/debris protection with high propellant transmission and low O recombination; quantitative limits evidence-derived before LOCK-1.
4. S6.4 — F2-OQ-02 — CATALYTIC O→O₂ FILTER IS NOT THE BASELINE.
The baseline filter shall use an inert/low-recombination approach intended to preserve the representative atmospheric O fraction.
A deliberately catalytic O→O₂ element may be retained only as a separately labelled experimental/contingency architecture.
It may not silently replace the baseline atmospheric composition or be used to make downstream materials testing easier.
Any catalytic variant requires its own:
   * species-conversion measurement;
   * flow/conductance measurement;
   * thermal/material qualification;
   * H-1 performance map on the converted composition.
Decision: catalytic filter excluded from baseline; separately identified research variant only.
5. S6.5 — F2-OQ-03 — `NO FILTER` IS REFERENCE-BOUND ONLY.
Keep FC-00/no-filter in analysis only as an ideal/reference bound to quantify the cost of the filter in mass, pressure loss and collected flow.
It shall not be an admissible frozen flight architecture while the applicable RFP architecture contains an explicit intake → filter → compressor chain. RFP(1)
Decision: no-filter = analytical reference only, not baseline flight candidate.
6. S6.6 — F2-OQ-04 — PLACE THE BASELINE FILTER BETWEEN THE INTAKE AND COMPRESSOR; ADD `APP-FILTER` TO P4.
Baseline placement:
intake/channel array → filter → compressor inlet
Place it downstream of the primary intake/collimator and upstream of the compressor so it protects the compressor without becoming the primary hyperthermal capture surface.
The exact axial location, area and thermal state remain design variables until geometry is frozen.
Add `APP-FILTER` to the P4 materials programme with applicable:
   * AO/O exposure;
   * erosion;
   * catalytic/recombination behavior;
   * particulate retention;
   * thermal cycling;
   * transmission/conductance effects.
Decision: compressor-inlet filter; YES to `APP-FILTER`.
7. S6.7 — OQ-F3-02 — HUB RATIO SHALL BE AN EXPLICIT PHYSICAL DESIGN VARIABLE.
Do not treat the zero-hub relation `R = sqrt(A/pi)` as a buildable rotor geometry.
Add hub ratio / hub radius and blade span explicitly to the compressor geometry.
The present zero-hub case may remain as an ideal upper-area/lower-radius analytical bound only.
Final bounds shall come from:
   * shaft/bearing geometry;
   * rotor structural analysis;
   * motor/interface geometry;
   * blade manufacturability;
   * pumping-performance model.
Do not invent numerical hub-ratio bounds before those interfaces exist.
Decision: explicit hub ratio/blade span; zero hub = bound only.
8. S6.8 — OQ-F3-03 — DEVELOP THE TRANSITIONAL-REGIME MODEL AND T-1 EVIDENCE IN PARALLEL; FAIL CLOSED ABOVE 0.1 Pa UNTIL VALIDATED.
Do both.
Commission an open-literature transitional-regime compressor model now so architecture work does not wait entirely for hardware.
In parallel, perform T-1/T-2 compressor characterization.
However, until the transitional model has an admitted evidence basis and/or has been validated against the project hardware:
   * production/design evidence above the current 0.1 Pa free-molecular domain remains `NOT_EVALUATED_OUT_OF_DOMAIN`;
   * no extrapolated >0.1 Pa result may be treated as a valid architecture point.
Decision: model + test in parallel; no valid >0.1 Pa architecture result until evidence closes the domain.
9. S6.9 — OQ-F3-04 — YES, RE-ADMIT ALUMINIUM AND CFRP ONLY THROUGH THE S2.3 STRENGTH-BASIS GATE.
Aluminium-alloy and CFRP rotors may re-enter the design search when an admissible material basis exists.
Aluminium requires the applicable product-form, temperature-dependent structural allowable and rotor qualification basis.
CFRP additionally requires:
   * laminate definition;
   * directional allowables;
   * temperature/moisture/environment basis;
   * manufacturing/inspection basis;
   * AO disposition/protection for every exposed surface.
No material is admitted simply because a handbook strength number exists.
Decision: YES, conditional on S2.3 and applicable AO qualification.
10. S6.10 — OQ-F4-01 — SCHEDULED PLENUM SETPOINT IS THE BASELINE; FIXED SETPOINT REMAINS THE FALLBACK/REFERENCE.

Use an orbit-state-scheduled plenum pressure as the baseline control architecture because atmospheric density and intake supply vary substantially across the mission envelope.
The schedule may depend only on measurable/estimable flight state variables available to the controller.
Retain:

* a fixed-setpoint operating mode as a robustness/degraded-mode fallback; and
* fixed-setpoint results as the comparison baseline.

The schedule itself is not frozen until the compressor/feed/H-1 validated domains exist.
Decision: scheduled setpoint baseline; fixed setpoint retained as fallback/reference.

11. S6.11 — OQ-F4-02 — PRIMARY DIRECTION: DEVELOP THE HIGHER-PRESSURE COMPRESSION PATH; RETAIN ≤0.1 Pa HIGH-CONDUCTANCE FEED ONLY AS A REFERENCE/FALLBACK STUDY.

The baseline architecture shall pursue a compressor/feed chain capable of producing the pressure and mass-flow state required by H-1 rather than attempting to make the entire downstream system operate from a ≤0.1 Pa source through an extremely large equivalent molecular conductance.
This is consistent with the RFP architecture, which explicitly describes the compressor and gas reservoir as increasing collected atmospheric density to a usable ionization level. RFP(1)
Therefore:

* extend compressor modelling/testing into the necessary transitional/higher-pressure regime under S6.8;
* determine the actual H-1 inlet pressure requirement experimentally;
* design valve, line, isolator and distributor around that admitted feed state.

Continue the ≤0.1 Pa/high-conductance branch as a sensitivity/fallback study until the higher-pressure solution is experimentally established, but do not freeze it as the primary architecture merely because the current compressor model stops at 0.1 Pa.
Decision: higher-pressure compression is the primary design direction.

12. S6.12 — OQ-F4-03 — ACCEPT THE CURRENT F4 TRANSIENT METRIC FRAMEWORK PROVISIONALLY.

Retain for engineering development:

* 2% settling band;
* 60 s observation window;
* E0–E7 event sequence;
* orbit-modulation cases;
* settling time, peak deviation, valve travel and ripple-transfer outputs.

These are the pre-LOCK-2 engineering characterization framework, not yet final H-1 tolerances.
At LOCK-2, H-1 measured feed sensitivity shall determine the actual allowable pressure/flow/composition disturbance bands.
If measured H-1 tolerance is tighter than the provisional F4 metric, the H-1 limit governs. Do not relax H-1 because F4 was designed around 2%.
Decision: YES, provisionally; final tolerances come from H-1 evidence at LOCK-2.

13. S6.13 — OQ-F4-04 — DO NOT ARBITRARILY LOWER THE FEED REQUIREMENT TO MAKE THE CURRENT CHAIN PASS.

Pursue the flow gap in this order:

1. establish the actual performance-derived H-1 feed requirement under S6.21;
2. improve atmospheric capture/collection within the drag, mass and pointing constraints;
3. improve compressor operating domain, pumping performance and downstream feed efficiency;
4. exploit the scheduled setpoint/control policy of S6.10.

Operation only in higher-density parts of the orbit may be investigated as a mission-control sensitivity, but it shall not be the baseline if it violates the statewise drag-compensation requirement of S6.15.
The 0.38 mg/s ground-characterization lower bound shall not be treated as a flight requirement.
Decision: performance-derived requirement first; then capture/compression/feed improvements. No arbitrary requirement relaxation.

14. S6.14 — OQ-F4-05 — AUTHORISE AN ORBIT-RESOLVED FROZEN ATMOSPHERE DATASET.

Authorise a rule-1 rebuild/versioned dataset for orbit-resolved atmospheric conditions.
Preserve the existing orbit-averaged dataset unchanged for reproducibility.
The new dataset shall carry, as applicable:

* altitude/orbit state;
* density;
* species composition;
* temperature;
* relative flow/wind state;
* solar-activity inputs;
* geomagnetic/atmospheric inputs;
* local-time/orbit position dependence;
* source/model/version;
* provenance and hashes.

Do not invent an arbitrary density-modulation amplitude when an orbit-resolved producer can supply the physical variation.
Decision: YES — versioned orbit-resolved frozen atmosphere dataset.

15. S6.15 — OQ-F78-01 — `T - D_spacecraft >= 0` IS A HARD STATEWISE ARCHITECTURE CONSTRAINT.

Require:
`T_available(state) - D_spacecraft(state) >= 0`
at every required evaluated flight/environment state in the 180–230 km mission envelope.
Use thrust and spacecraft drag evaluated at the same atmospheric/orbit state.
Also report:

* instantaneous/statewise margin;
* worst-state margin;
* orbit-integrated/orbit-averaged margin.

The orbit-average value is useful mission information but shall not hide a statewise deficit in the baseline architecture.
A future mission/GNC analysis may explicitly authorize controlled negative intervals if orbital-energy management supports them, but that would be a new owner decision.
Decision: hard statewise constraint; orbit-average reported additionally.

16. S6.16 — OQ-F78-02 — REQUIRE ALL CURRENTLY ADMITTED SURFACE SCENARIOS UNTIL DI-1.3 NARROWS THEM.

Before accommodation/surface evidence exists, the robust architecture must remain feasible across every presently admitted Maxwell/CLL and accommodation scenario.
Once DI-1.3 provides measured, applicable surface-accommodation evidence:

* preregister the mapping from measurement to admitted scenario range;
* narrow the robustness set to the evidence-supported range;
* preserve the previous full-range cases as sensitivity records.

Do not select a favorable surface model simply because it produces better intake performance.
Decision: all admitted scenarios now; measurement may narrow them later.

17. S6.17 — OQ-F78-03 — RIPPLE IS A CONSTRAINT, NOT A FULL-SYSTEM OBJECTIVE; KEEP SYSTEM SELECTION PARETO-BASED.

Once the required evidence exists, upstream feasibility shall first enforce:

* feed-state/thrust sufficiency under AG-12;
* statewise drag compensation under AG-13;
* power;
* mass;
* thermal;
* material/life;
* H-1 feed-quality tolerances.

Compressor/plenum ripple shall be compared with a measured H-1 allowable tolerance and treated as a hard feed-quality constraint, not rewarded indefinitely as an optimization objective.
Among feasible architectures, retain a Pareto comparison over quantities such as:

* worst-state thrust/feed margin — maximize;
* spacecraft/intake drag — minimize;
* upstream electrical power — minimize;
* hardware mass — minimize;
* required volume — minimize;
* thermal-rejection burden — minimize.

Do not introduce an arbitrary weighted scalar score.
Decision: ripple = constraint; system comparison remains Pareto-based after hard constraints.

18. S6.18 — OQ-F78-04 — AUTHORISE SOURCING FOR PARAMETRIC STUDIES; FINAL DRAG CLOSURE REQUIRES THE ACTUAL SPACECRAFT ICD.

Authorise use of documented/public/official spacecraft geometry information for interim parametric drag studies.
Such sourced reference geometry shall be explicitly labelled `REFERENCE/PARAMETRIC`, not the flight spacecraft.
AG-13 final closure requires the actual host-spacecraft basis including:

* body frontal geometry;
* intake projected area;
* arrays/deployed surfaces;
* attitude/pointing states;
* drag-coefficient/model basis;
* relevant accommodation/surface state.

Until that ICD exists, `D_spacecraft` and `T-D` remain `NOT_EVALUATED` for freeze purposes.
Decision: sourcing authorised for sensitivity; actual spacecraft ICD mandatory for closure.

19. S6.19 — UPSTREAM_ICD-Q1 — FILTER SHALL BE A SEPARATE PRODUCTION-PATH ELEMENT.

Implement the filter as a distinct element between IF-A1 and IF-A2.
It shall expose its own:

* species-resolved forward transmission;
* reverse/backflow transmission where relevant;
* conductance/pressure effect;
* species conversion/recombination;
* retained contaminant inventory;
* thermal load;
* material state;
* validity/domain flags.

Do not hide the filter's effect inside the intake efficiency.
Intake TPMC remains responsible for intake physics; the filter owns filter physics.
Decision: separate production element.

20. S6.20 — F9-OQ-01 — CARRY THE ROBUST PARETO SET TO LOCK-1; DO NOT SELECT ONE REPRESENTATIVE YET.

Carry a versioned robust Pareto set rather than a single upstream representative.
The currently reported nine-member set shall not be frozen verbatim because it must be regenerated after:

* S2 production-model corrections;
* intake-surface v2;
* filter implementation/evidence;
* the compressor search is expanded beyond the currently inherited F3-front subset;
* T-1/T-2 data;
* DI-1.3 surface evidence.

Only after those closures may an explicit representative-selection rule be proposed.
Until then downstream studies that require a single point shall either evaluate all remaining Pareto members or explicitly label a selected member as an engineering reference, not the frozen architecture.
Decision: carry the set; defer representative selection.

21. S6.21 — F9-OQ-02 — DO NOT SET A FIXED FLIGHT MASS-FLOW REQUIREMENT; DERIVE IT FROM THE MEASURED H-1 THRUST MAP AND THE RFP DRAG-COMPENSATION REQUIREMENT.

There is no basis for setting `0.38 mg/s` as the flight requirement. Likewise, the existing approximately `1.3 mg/s` sizing value shall not become a flight requirement merely because it appears in an earlier design basis.
The official RFP instead defines the functional orbit and thrust requirement: 180–230 km, intake specification dependent on air density/solar activity, and 12–25 mN thrust for expected drag compensation. RFP(1)
Redefine AG-12 as a feed-state sufficiency gate, not a fixed-number mass-flow gate.
For each required orbit/environment state:

1. determine the required drag-compensation thrust from the registered spacecraft drag basis;
2. use the measured/validated H-1 map for the actual atmospheric composition to determine the minimum feed state required to produce that thrust within the admitted power/thermal envelope;
3. require the upstream chain to deliver at least that feed state.

The feed-state record shall include at least:

* mass flow;
* pressure;
* temperature;
* species composition;
* applicable transient/ripple quality.

Until the validated H-1 thrust-versus-feed map exists, AG-12 remains `NOT_EVALUATED`.
The 0.38–3.2 mg/s ground range remains useful for characterization coverage but not as an architecture PASS/FAIL requirement.
Decision: performance-derived, state-specific feed requirement; no arbitrary fixed mg/s flight gate.

22. S6.22 — F9-OQ-03 — APPROVE AG-01…AG-15, WITH DETERMINING-EVIDENCE CLOSURE AND FOUR CLARIFICATIONS.

Approve the architecture gate set AG-01 through AG-15 as the gate structure for moving from `INVESTIGATION_HYPOTHESIS` toward `FROZEN_REFERENCE_FLIGHT_ARCHITECTURE`.
A gate closes only on determining evidence appropriate to that gate:

* measured/test evidence for performance quantities;
* correlated/validated analysis where the accepted methodology explicitly permits it;
* inspected/weighed/certified configuration evidence for hardware/mass/material items;
* official source documentation for requirements.

Assumptions, parametric sensitivities, analog values, code defaults, supplier marketing values or "evidence seems sufficient" are not determining closure evidence.
Apply these clarifications:
AG-03:
 Do not attempt to rewrite the immutable P5-N2 v1 `INCONCLUSIVE` result. That historical result stays unchanged. Closure requires a separately preregistered successor held-out predictive validation that admits a Hall-transport member.
AG-12:
 Use the S6.21 performance-derived feed-state sufficiency rule, not 0.38 mg/s.
AG-13:
 Use the S6.15 statewise `T - D_spacecraft >= 0` criterion.
AG-15:
 The official RFP is now available to the project, but before this gate closes it must be placed/registered in the repository evidence system with immutable provenance/hash and the RVM requirements re-based against it. The repository may not continue relying only on secondary transcriptions.
All 15 gates must be closed before the architecture is labelled `FROZEN_REFERENCE_FLIGHT_ARCHITECTURE`; unresolved gates remain explicit blockers.
Decision: AG-01…AG-15 APPROVED with the determining-evidence standard and clarifications above.
A particularly important consequence of these decisions is that the current statement "we only deliver 0.10–0.14 mg/s against a 0.38 mg/s requirement" should no longer be interpreted as a demonstrated requirement failure. It is a serious engineering warning because the present flow is low relative to the ground-characterization envelope, but the actual architecture question becomes: can that delivered ambient feed, after S2 corrections and the compressor redesign, make the measured H-1 produce the required 12–25 mN drag-compensation performance within <1.5 kW and <40 kg? That is the physically correct gate.
Also, the official RFP explicitly expects both ambient-air operation and Xenon capability. RFP(1) That does not change our C1 rule: Xe remains contingency-only for C1, while the overall propulsion system still needs the RFP-required Xe capability.

what do you do with these answers? are you implementing?
