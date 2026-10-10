# S7–S10 OWNER DECISIONS (A9.14) — verbatim record, 2026-10-01

Recorded verbatim from the owner's message of 2026-10-01 (session chat), answering groups S7–S10 (61 questions) of
`docs/budgets/owner_decisions/OWNER_QUESTIONS_SEQUENCED_v1.md`. "RFP(1)" markers cite the official RFP held by the owner (not
yet registered in the repository, AG-15). Machine-readable companion: `OD_2026_10_01_A9_14_s7_s10_owner_decisions.json`.
Immutable after commit; later amendments are new addenda. **Amended by A9.15** (`OD_2026_10_01_A9_15_*`, RFP-compliant
propellant policy): the 'Xe contingency-only for C1' wording in S8.17, S8.21, S8.33, S8.35, S9.3 and S9.10 below is superseded.

---

I reviewed the remaining register. S7–S10 contain 61 unanswered questions: 9 in S7, 35 in S8, 13 in S9 and 4 in S10. OWNER_QUESTIONS_REMAINING_S7_S10 The decisions below are written so they can be recorded as the next owner-decision addenda without inventing missing test evidence.
S7 — H-1 and downstream ICP design
The nine open S7 questions are the H-1/F5 and downstream-ICP/F6 design decisions. OWNER_QUESTIONS_REMAINING_S7_S10

1. S7.1 — F5-OQ-01 — YES: AUTHORISE FEMM ANALYSIS POINTS.
Run FEMM-class axisymmetric magnetostatics at the RP-1 anchor and admissible window corners. These are `ANALYSIS_POINTS`, not selected designs. Use actual/sourced B-H data when available, preserve geometry IDs and solver configuration, and do not infer Hall performance from magnetic feasibility alone.
Decision code: `YES_FEMM_ANALYSIS_POINTS_NOT_SELECTION`.
2. S7.2 — F5-OQ-02 — SELECT AN ENGINEERING CHANNEL POINT NOW ON NON-PERFORMANCE CRITERIA.
Do not wait for a Hall transport model that is presently not admitted. Select a buildable engineering point using FEMM feasibility, thermal margin, packaging, mass, manufacturability and the existing adjustable-anode/insert capability. Keep it `ENGINEERING_FREEZE_CANDIDATE`; thrust remains determined by Phase-1/Phase-3 measurement.
Decision code: `SELECT_ENGINEERING_POINT_NONPERFORMANCE`.
3. S7.3 — F5-OQ-03 — USE 754 °C AS THE CONSERVATIVE NECESSARY CEILING FOR NOW.
Use the lower 754 °C value until the exact iron grade has sourced temperature-dependent magnetic data. This is only a necessary ceiling, not the usable operating-temperature limit; `B_sat(T)`, permeability and validated material behavior govern the actual design limit.
Decision code: `USE_754C_NECESSARY_CEILING_PENDING_GRADE_DATA`.
4. S7.4 — F5-OQ-04 — ACCEPT THE FREEZE_CANDIDATE DEFINITION AS THE LOCK-1 RELEASE BASIS.
Every item marked `OPEN`, `TBD`, `TBD_AFTER_EVIDENCE` or equivalent remains an explicit release blocker. The released H-1 design must have drawing ID, revision and content hash. No OPEN item is silently promoted merely because surrounding geometry is frozen.
Decision code: `ACCEPT_FREEZE_CANDIDATE_WITH_EXPLICIT_BLOCKERS`.
5. S7.5 — F5-OQ-05 — ACCEPT THE EXISTING `r_Le <= 0.1 h` TARGET BAND FOR FEMM.
Use the present model-derived field target over the registered 10–30 eV electron-temperature sensitivity range as a magnetic-design target, not a transport optimum. Narrow it only after measured H-1 magnetic/performance evidence exists.
Decision code: `ACCEPT_EXISTING_FEMM_FIELD_TARGET_BAND`.
6. S7.6 — F6-OQ-01 — APPROVE ALL EIGHT F6 OBJECTIVES AND FAIL-CLOSED PARETO SEMANTICS.
Approve electron-current capacity, plume interception, RF-match loss, RF delivered power, Hall-field disturbance, view-factor obstruction, collector heating and module mass with the directions already defined. No ranking from an incomplete subset; missing required objectives keep the Pareto result `REFUSED_INCOMPLETE`.
Decision code: `APPROVE_F6_OBJECTIVES_FAIL_CLOSED`.
7. S7.7 — F6-OQ-02 — DRAWING ENVELOPE DEFINES HARD BOUNDS; BENCH MATRIX DEFINES EVIDENCED GEOMETRIES.
The KC-1/ICP LOCK-1 drawing envelope defines the permissible mechanical design-variable bounds. The registered P1/P2 geometry matrix defines which points inside that envelope have experimental evidence. A test matrix shall never enlarge a mechanical envelope without a drawing revision.
Decision code: `DRAWING_HARD_BOUNDS_BENCH_EVIDENCE_POINTS`.
8. S7.8 — F6-OQ-03 — USE A MULTI-GEOMETRY BENCH MATRIX FIRST.
Use modular/replaceable ICP geometry variants in P1/P2 and measure each registered geometry. A geometry-response surrogate/model may later be used between measured configurations only after separate predictive validation. Until then, F6 evaluates built geometries rather than pretending to perform a continuous validated search.
Decision code: `MULTI_GEOMETRY_BENCH_FIRST_MODEL_AFTER_VALIDATION`.
9. S7.9 — F6-OQ-04 — DEFINE A 5% PROVISIONAL HALL-FIELD-DISTURBANCE LIMIT.
Use
`δB_acc = max_ROI |B_H1+ICP − B_H1| / max_ROI |B_H1|`
over the preregistered H-1 acceleration-region ROI and relevant magnet operating states. Set the provisional design requirement δB_acc ≤ 0.05. Also report absolute stray field at IP-EXIT and through the ICP volume. The 5% value is an owner engineering allocation, not experimental proof; later H-1 sensitivity evidence may tighten it, but it shall not be relaxed post-hoc merely to admit a design.
Decision code: `DELTA_B_ACC_MAX_5_PERCENT_PROVISIONAL`.

S8 — Blocks LOCK-1
The register contains 35 S8 questions covering ICP integration, mass/Xe accounting, RFQs and LOCK-1 interfaces. OWNER_QUESTIONS_REMAINING_S7_S10

1. S8.1 — ICPQ-03 — YES. Both interchangeable downstream modules and their representative mounting hardware belong on the moving thrust platform so module/plume forces remain inside the measured system boundary.
`YES_BOTH_MODULES_ON_MOVING_PLATFORM`.
2. S8.2 — ICPQ-08 — YES. Map B(z) energized when the gaussmeter chain has demonstrated RF immunity; otherwise map immediately after RF-off using a preregistered delay whose field decay/repeatability has been characterized.
`ENERGIZED_IF_RF_IMMUNE_ELSE_REGISTERED_RF_OFF_DELAY`.
3. S8.3 — ICPQ-09 — YES. Plume interception by the downstream ICP structure is a real system force/energy interaction. Keep it inside the boundary; do not numerically “correct it away.”
`PLUME_INTERCEPTION_INSIDE_SYSTEM_BOUNDARY`.
4. S8.4 — ICPQ-11 — SET `k_RF = 1.5`. Antenna-circuit voltage rating shall be at least `1.5 × V_ant,peak` at the worst measured P2 mismatch/operating point. This does not replace Paschen, creepage/clearance or combined RF+DC-stress qualification; any more stringent supplier/qualification requirement governs.
`K_RF_1_5`.
5. S8.5 — OQ-VI-04 — PROVISIONAL ICP LIFE BASIS: ≥15,000 h; CYCLES MISSION-DERIVED.
The RFP literally shows a 3-year mission and an entry labelled “Ignition Time” of more than 15,000 h; because that label is unusual, preserve the literal wording in the requirements record while using ≥15,000 h cumulative energized operating life as the conservative design basis pending clarification. RFP(1) Restart/cycle count comes from the frozen mission-mode profile and shall not be invented now.
`LIFE_15000H_MIN_CYCLES_FROM_MISSION_PROFILE`.
6. S8.6 — MQ-01 — ROW-54 ALLOCATIONS ARE MEV-LEVEL BUDGETS. Equipment margin is already inside the line allocation; do not add the row-57 margin a second time to an owner MEV allocation. Actual CBE/evidence floors still override allocations when heavier.
`MQ01_MEV_LEVEL`.
7. S8.7 — MQ-02 — THE 20% SYSTEM MARGIN REPLACES THE FIXED 4 kg RESERVE. Do not add both. With the present 24 kg pre-system-margin owner allocation, the formula gives 4.8 kg, hence 28.8 kg; if line allocations change, recalculate 20% rather than freezing 4.8 kg forever.
`SYSTEM_MARGIN_20_PERCENT_REPLACES_4KG_RESERVE`.
8. S8.8 — MQ-03 — REBASE AL-04; DO NOT PATCH ONLY THE 0.504 kg GAP. Under the MEV reading, the currently known 3.504 kg magnetic-parts floor already implies 4.2048 kg MEV, before channel/anode/body/fasteners. Use `AL-04 >= 1.20 × actual H-1 CBE` once the design exists; 4.2048 kg is only today's incomplete planning floor.
`REBASE_AL04_FROM_H1_CBE_NO_RESERVE_PATCH`.
9. S8.9 — MQ-04 — REBASE AL-07 FROM REAL PPU EVIDENCE. Use the present lowest 5.0 kg admissible analog as a provisional CBE floor, giving a 6.0 kg MEV planning floor under the selected margin convention. Replace it with the selected flight PPU CBE when available. Do not consume system margin to disguise an under-allocated PPU.
`REBASE_AL07_PPU_MIN_6KG_MEV_PLANNING_FLOOR`.
10. S8.10 — MQ-05 — AL-08 INCLUDES THE COMPLETE Xe STORAGE/FLOW HARDWARE. Scope includes Xe tank, regulator, valves, plumbing, mounting and thermal hardware. The current 5.044 kg incomplete CBE floor implies 6.0528 kg MEV planning floor; quotations/design replace this value.
 `AL08_FULL_XE_SYSTEM_REBASE_FROM_CBE`.
11. S8.11 — MQ-06 — YES, SPLIT CONTROLS AND HARNESS. Harness is its own mass line governed by the row-60 percentage rule; electronics/controls/valve drivers form a separate allocation/CBE line.
 `SPLIT_CONTROLS_AND_HARNESS`.
12. S8.12 — MQ-07 — ACCEPT THE PROPOSED MAPPING, clarified as: collector/bias electrode → AL-05; collector/bias supply → AL-07; RF feedthrough/coax/local match → AL-06; flight sensors/valve drivers → controls portion of AL-09; Xe mounting/thermal/plumbing → AL-08.
 `ACCEPT_MQ07_MAPPING`.
13. S8.13 — MQ-09 — NO RESIDUAL ON TOP OF A LOADED CASE. Define each 2/5/10 kg case as total loaded Xe:
 `M_loaded = M_mission_usable + M_reserve + M_residual`.
 Residual may appear as an accounting sub-line but is not added a second time.
 `LOADED_CASE_INCLUDES_RESERVE_AND_RESIDUAL`.
14. S8.14 — MQ-10 — DO NOT RELAX THE MARGIN READING TO MAKE 40 kg PASS. If evidence-based mass exceeds the RFP limit, reduce actual subsystem CBE through redesign, integration or lighter qualified parts. Allocation bookkeeping cannot override real evidence.
 `MASS_CLOSURE_REQUIRES_REDESIGN_NOT_MARGIN_RELAXATION`.
15. S8.15 — OQ-A907-01 — THREE ATTEMPTS. One initial C1 ignition attempt plus at most two retries = maximum three dwells per start.
 `THREE_ATTEMPTS_ONE_PLUS_TWO_RETRIES`.
16. S8.16 — OQ-A907-04 — PLAIN CERAMIC-INSULATED COPPER IS THE BASELINE. Ni-clad/Kulgrid remains a contingency variant only if oxidation, supplier availability or manufacturing demands it; if used it requires measured resistance and magnetic perturbation evidence.
 `PLAIN_COPPER_BASELINE_NICLAD_CONTINGENCY`.
17. S8.17 — OQ-A907-07 — DEFER FLIGHT C1 INTEGRATION. Do not burden the baseline flight article with C1 until C1 is actually selected as a flight fallback. Development/reference C1 work continues separately.
 `DEFER_FLIGHT_C1_UNTIL_SELECTED`.
18. S8.18 — XA9Q-01 — 2/5/10 kg ARE LOADED-Xe CASES. Reserve and residual are carved out within each total loaded mass.
 `LOADED_XE_CASES`.
19. S8.19 — XA9Q-03 — YES. Keep the flow-class term additive and inside the non-reserve base until hardware evidence establishes a lower class.
 `FLOW_CLASS_ADDITIVE_INSIDE_RESERVE_BASE`.
20. S8.20 — XA9Q-06 — YES, RETIRE THE 75-bar PLACEHOLDER. Request tank/regulator solutions against the 323 K volume/pressure cases. Select MEOP only from the actual design case, supplier qualification basis and applicable pressure-vessel practice.
 `QUOTE_DERIVED_MEOP_AT_323K`.
21. S8.21 — XA9Q-07 — YES, Xe CAPABILITY APPLIES TO `hall_icp_neutralizer`. The RFP requires compatibility with both ambient air and Xenon and explicitly mentions separate ambient-air and Xe propellant storage. RFP(1) This is distinct from C1: Xe remains contingency-only for the C1 electron source unless C1 is actually required.
 `YES_XE_PROPULSION_CAPABILITY_BOTH_CONFIGURATIONS`.
22. S8.22 — OQ-RFQ-01 — SPARES: one spare set of stand flexures; one spare of each breakable ICP dielectric/feedthrough item; for C1, one development unit + one spare only if the C1 campaign is activated; a sacrificial O/AO unit only where the planned test is destructive.
 `ONE_SPARE_BREAKABLE_CONSUMABLE_C1_CONDITIONAL`.
23. S8.23 — OQ-RFQ-03 — GET INDICATIVE Xe-MFC QUOTES NOW. Request sufficient range options to cover the prospective reference/C1 envelope; freeze the range only after the actual Xe reference point is registered.
 `QUOTE_NOW_FREEZE_RANGE_AFTER_REFERENCE_POINT`.
24. S8.24 — OQ-RFQ-04 — DO NOT FREEZE 0.6–0.8 mg/s AS A REQUIREMENT. Quote the second/start controller as an option capable of that provisional region, but final start/diode flow comes from the selected C1 vendor procedure and characterization.
 `C1_START_FLOW_OPTIONAL_QUOTE_NOT_FROZEN`.
25. S8.25 — OQ-RFQ-08 — YES, REQUEST OPTION-B COMPLETE-STAND COMPARISON QUOTE. It is a commercial/architecture comparator, never the sole procurement path.
 `YES_OPTION_B_COMPARISON_QUOTE`.
26. S8.26 — OQ-RFQ-09 — LET SUPPLIERS PROPOSE MEOP AND DESIGN/PROOF FACTORS. Give them the 323 K design cases and required usable/loaded quantities; then select the basis after comparing compliant certified solutions.
 `SUPPLIER_PROPOSES_MEOP_FINAL_AFTER_QUOTATIONS`.
27. S8.27 — OQ-A910-01 — ONE ACCOUNTING READING GOVERNS BOTH LEDGERS: LOADED Xe. The 2/5/10 kg case includes usable mission quantity, reserve and residual. Do not add residual again in the mass BOM.
 `UNIFY_BOTH_LEDGERS_LOADED_XE`.
28. S8.28 — OQ-A910-02 — ASSIGN PRODUCING STAGE AND DECISION QUANTITY AT LOCK-1. Use the frozen A9-01 stage map and the decision-quantity consumer table. No stage assignment is inferred simply to eliminate a TBD.
 `ASSIGN_FROM_STAGE_MAP_AND_DQ_TABLE_AT_LOCK1`.
29. S8.29 — OQ-A910-03 — YES, `peak_sampled < 1500 W` MAY BE A ONE-SIDED SUFFICIENT PASS CONDITION. Only when the record satisfies the declared ≥100 kSa/s, ≥20 kHz measurement bandwidth, anti-alias filtering, synchronized channels, no saturation and total-bus-power reconstruction requirements. Since every conformant sample is below 1500 W, its 1 ms mean cannot exceed 1500 W. Conversely, `peak_sampled >=1500 W` does not fail the 1 ms gate; calculate the proper 1 ms maximum.
 `PEAK_SAMPLED_BELOW_LIMIT_SUFFICIENT_PASS_NOT_FAILURE_METRIC`.
30. S8.30 — OQ-A910-05 — YES: MATCHED SHAM MUST REPRODUCE THE LOCAL-MATCH PARASITICS. Provide mass/stiffness/thermal/service-line equivalent as necessary for force-system equivalence. Book the local matching hardware on AL-06 RF generator/matching, not AL-05.
 `SHAM_MATCH_EQUIVALENT_LOCAL_MATCH_AL06`.
31. S8.31 — P1Q-12 — YES. Define the reusable IP-NEU electrical/mechanical/connector/harness interface in the LOCK-1 ICD revision. P1 may use a controlled interim harness drawing until that revision exists.
 `YES_IP_NEU_LOCK1_ICD_INTERFACE`.
32. S8.32 — P2Q-06 — YES, USE ZM-B ON THE THRUST STAND AFTER BENCH AGREEMENT IS DEMONSTRATED. Do not route an unnecessary V/I probe line across the moving stage. ZM-A remains the bench reference and periodic/after-change cross-check.
 `ZM_B_THRUST_STAND_AFTER_ZM_A_AGREEMENT`.
33. S8.33 — MPQ-01 — USE OPTION (c). C1 heater/keeper/control electronics belong inside AL-07; the C1 Xe branch belongs inside AL-08; create a separate AL-C1 only for the cathode module, shield/mount and any C1-specific getter/filter. Do not invent a fixed kg allocation now: set `AL-C1 = selected C1 module CBE × 1.20` under the chosen MEV convention when C1 is actually selected.
 `C1_OPTION_C_NEW_AL_C1_MODULE_ONLY`.
34. S8.34 — MPQ-02 — ACCEPT THE PROPOSED MAPPING: ICP isolation hardware → AL-05; RF protection/sensing electronics → AL-06; anode heat-removal hardware → AL-04; ICP open-frame support/spacer → AL-10.
 `ACCEPT_MPQ02_MAPPING`.
35. S8.35 — XV2Q-01 — NOT APPLICABLE BECAUSE XA9Q-07 = YES. `hall_icp_neutralizer` retains the RFP-required Xe propulsion capability. It is not Xe-free. Again, this does not make Xe mandatory for C1.
 `NOT_APPLICABLE_PARENT_XA9Q07_YES`.

S9 — Nothing immediate
These 13 questions are lower urgency, but there is no reason to leave their interpretation ambiguous. OWNER_QUESTIONS_REMAINING_S7_S10

1. S9.1 — XA9Q-02 — THREE DWELLS / 360 s MAXIMUM BOOKING. One attempt + two retries, each capped at 120 s. Final operating dwell may later be tightened by evidence.
`THREE_DWELLS_MAX_360S`.
2. S9.2 — XA9Q-04 — BOOK A 20% GROUND-TEST Xe LOGISTICS MARGIN. Apply it to calculated test consumption. Purges, conditioning, line-fill and known vendor procedures are booked explicitly before this margin rather than hidden within it.
`GROUND_XE_20_PERCENT_LOGISTICS_MARGIN`.
3. S9.3 — XA9Q-05 — NO DEFAULT FILTER/GETTER FOR G-XE ICP. Add one only if the selected ICP/material/process or Xe purity specification demonstrates the need. C1 getter requirements remain separate.
`NO_ICP_XE_GETTER_UNLESS_REQUIRED_BY_SPEC`.
4. S9.4 — M16-V3-Q-01 — ACCEPT THE PROPOSED BLOCKING-ITEM / FUNCTIONAL-ROLE / DECISION-POINT MAPPING. Do not fabricate individual engineer names. The source contains no staffing roster. Named-person assignments shall be populated from the actual project staffing ledger before the corresponding work package starts; functional-role ownership remains binding in the meantime.
`ACCEPT_ROLE_MAP_NAMES_FROM_STAFFING_LEDGER`.
5. S9.5 — P1Q-17 — REVERIFICATION = 700 V DC / 60 s. Use a current-limited controlled DC test at representative pressure/gas, record leakage, disconnect sensitive electronics as required and apply the per-path leakage criterion. This is not a routine pre-run test: use after repair, insulation-path modification, suspected fault or other defined requalification trigger. The initial 1.05 kV qualification test remains separate. Do not attribute 700 V to an unverified ECSS clause; it is an owner development acceptance level.
`REVERIFICATION_700V_DC_60S_TRIGGERED_ONLY`.
6. S9.6 — P2Q-10 — USE STRESS-CLASS-SPECIFIC RF MARGINS, NOT ONE UNIVERSAL FACTOR.
   * RF voltage: 1.5× measured envelope maximum (`k_RF`).
   * Continuous RF power/current carrying capability: 1.25× measured envelope maximum.
   * Thermal dissipation: existing 1.20 heat-load margin.
   * Start-up/reflected-power/transient stress: remain below the manufacturer's documented transient/peak rating.
A more stringent supplier/qualification derating governs. Do not multiply independent margins twice onto the same physical stress.
`RF_RATING_POLICY_V1_5_PI_1_25_THERMAL_1_20`.
7. S9.7 — OD2 — USE A STATEWISE ENVELOPE QUANTIFIER. Every required state of the frozen 180–230 km mission/environment dataset must satisfy the applicable hard requirements; an orbit-average cannot conceal a statewise violation. Report worst state and orbit-average additionally.
`EVERY_REQUIRED_ENVIRONMENT_STATE_FAIL_CLOSED`.
8. S9.8 — OD3 — ATMOSPHERE DESIGN STATES COME FROM THE VERSIONED ORBIT-RESOLVED DATASET. Do not invent a few convenient F10.7/density points manually. The design set must include the mission-relevant nominal states and physical extrema of density/species/temperature/local-time/solar activity represented in the frozen dataset, with provenance and hashes.
`DESIGN_STATES_FROM_FROZEN_ORBIT_RESOLVED_ATMOSPHERE`.
9. S9.9 — OD5 — BASELINE ATMOSPHERIC START SEQUENCE: establish gas/plenum/feed state → set H-1 magnet state → ignite/stabilize ICP → verify electron-source/current condition → apply Hall discharge voltage → verify sustained Hall discharge. Maximum one initial attempt + two retries under registered dwell/thermal limits. A C1-selected variant uses its separately qualified heater/keeper sequence.
`ICP_FIRST_HALL_SECOND_MAX_3_ATTEMPTS`.
10. S9.10 — OD6 — “AIR + Xe” MEANS DUAL-PROPELLANT CAPABILITY, NOT A REQUIRED PREMIX. The RFP requires compatibility with ambient air in the 180–230 km operating range and with Xe, with separate storage paths. RFP(1) Treat them as separate selectable operating modes unless a later experiment intentionally studies mixing.
 `DUAL_PROPELLANT_SEPARATE_MODES_NOT_PREMIX`.
11. S9.11 — OD12 — PROMOTE THE RECORDED RFP ITEMS INTO EXPLICIT COMPLIANCE GATES.
   * Indigenous content: the RFP contains a >60% statement on one page and then a more specific minimum 75% project-deliverable target with subsystem targets of >80% thruster, >80% intake, >60% compressor/storage and >70% power electronics. Use the stricter/more specific 75% project target and subsystem targets internally, while recording the source discrepancy for DRDO clarification. RFP(1)
   * Single-point failure: compliance/FMEA gate for electronics and sensors.
   * N2 + nascent/atomic O: qualification evidence that the same propulsion architecture can ionize/operate on the required atmospheric species rather than only Ar/Xe.
 `GATE_IC_REDUNDANCY_AND_ATOMIC_O_REQUIREMENTS`.
12. S9.12 — OD14 — ATMOSPHERIC OFF-STATE IGNITION IS NOT EXPLICITLY AN RFP REQUIREMENT. Keep it as a project-derived operability/restart requirement because the flight architecture needs it, but label it `DERIVED_PROJECT_REQUIREMENT`, not `RFP_EXPLICIT`. Do not claim DRDO specified an ignition/restart clause when it did not.
 `ATMOSPHERIC_IGNITION_DERIVED_NOT_RFP_EXPLICIT`.
13. S9.13 — RVMQ-01 — REBASE RVM-19 ON THE OFFICIAL RFP REDUNDANCY CLAUSE. The RFP says the system must cater to single-point failure for electronics and separately calls for redundancy at electronics and sensor level. RFP(1) Therefore:
   * redundant/independent critical control, power-switching, telemetry and sensor paths are required where an individual failure would defeat the mission/safe state;
   * the single-point-failure analysis must prove the implementation;
   * the text does not by itself require duplicate thrusters, duplicate ICP modules or duplicate complete mechanical propulsion chains.

Row-55 limited redundancy may therefore remain for the physical thruster/ICP hardware, but not as a waiver of electronics/sensor redundancy.
 `REBASE_ELECTRONICS_SENSOR_REDUNDANCY_NO_FULL_THRUSTER_DUPLICATION`.
S10 — Tooling / performance / Rust
The final four open questions concern profiling and the optional Rust acceleration path. OWNER_QUESTIONS_REMAINING_S7_S10

1. S10.1 — F0-OQ-01 — ACCEPT THE PREREGISTERED THRESHOLDS. `PORT_CANDIDATE >= 60 s`; `MARGINAL >= 10 s` interpreter time for the reference workload. They are development-priority thresholds, not physics/evidence gates.
`ACCEPT_60S_10S_PORT_THRESHOLDS`.
2. S10.2 — F0-OQ-02 — YES, RE-MEASURE ON A DEDICATED UNLOADED MACHINE BEFORE PERFORMANCE ADMISSION. Record CPU, OS, Python version, compiler/toolchain, thermal/power state, thread settings and workload hash. The shared-machine A9.7 result remains historical evidence, not the admission baseline.
`DEDICATED_BASELINE_REQUIRED_BEFORE_RUST_PERFORMANCE_ADMISSION`.
3. S10.3 — RUST-OQ-01 — PYTHON REMAINS AUTHORITATIVE FOR FROZEN AND SCORE-BEARING OUTPUTS. An admitted Rust kernel may accelerate exploration, CI parity checks and non-authoritative runs, but frozen datasets, golden/reference rebuilds and score-bearing evidence must be produced or independently reproduced by the Python reference implementation.
`PYTHON_CANONICAL_FOR_FROZEN_AND_SCORE_BEARING`.
4. S10.4 — RUST-OQ-02 — YES, ADD OPTIONAL RUST CI, WITH MANDATORY PARITY ON RUST CHANGES. Normal CI may remain runnable without a Rust toolchain, but when `abep_core` is built the parity suite should run. Any change to Rust kernels, bindings or numerical logic requires the full preregistered parity campaign before the kernel remains `ADMITTED`.
`OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES`.

That closes the technical owner decisions for all 61 S7–S10 questions. The only thing I deliberately did not fabricate is the personal engineer-name roster in S9.4; the decision fixes the functional ownership and requires actual names from the staffing ledger before execution.
One especially important consistency point across these decisions: the RFP itself requires ambient-air and Xe propulsion capability, while your separate C1 policy remains Xe for C1 only if C1 is actually required. Those are two different requirements and should stay separate in the code, mass ledger and RFQs.
