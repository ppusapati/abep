# DBF-1 Design Baseline Freeze 1 - hall_icp_neutralizer

Authoritative record: `dbf1_v1.json` (this page restates it). Governing decision A9.37 (`docs/decisions/OD_2026_10_08_A9_37_DBF_1_DESIGN_BASELINE_FREEZE.md`). Machine-readable subset: `dbf1_config_v1.json` (read by the closure harness through `abep_config::baseline`). Hash lock: `dbf1_lock_v1.json`. Change control: `DCR_PROCESS.md`.

Every value comes from a sha256-pinned repository record. Where the evidence is incomplete, the selected engineering assumption is frozen with its evidence class and uncertainty; nothing is left open.

## Statuses

- **FROZEN**: the value is frozen as the design value; its evidence supports it at the stated class
- **FROZEN_ASSUMPTION**: the value is frozen as the selected engineering assumption; the evidence is incomplete and the class / uncertainty say how (A9.37: never left open)
- **REFERENCE_PENDING_ICD**: a frozen reference value standing in for a customer / host ICD that does not exist; replaced only by that ICD through a DCR
- **BASELINE_DEFICIENCY**: the value is frozen (it is the design) and a registered closure condition is known not to be met by it; the deficiency record gives the numbers. Not a reason to keep trading (A9.37)

Hardware configuration (envelope terms): geometry `G-RP1`, B shape `BZ-P5B16`.

## Frozen items

| id | item | value | units | evidence (class / type / level) | uncertainty | status |
|---|---|---|---|---|---|---|
| DBF1-H1-01 | channel mean diameter d_mean | 70.0 | mm | owner-fixed design value / owner-allocation / OWNER_DECISION | design value (owner-fixed); manufacturing tolerance TBD with the design release (H1F-CH-11 'tolerance TBD') | FROZEN |
| DBF1-H1-02 | channel width h | 12.0 | mm | owner-fixed design value / owner-allocation / OWNER_DECISION | design value (owner-fixed); manufacturing tolerance TBD with the design release (H1F-CH-11 'tolerance TBD') | FROZEN |
| DBF1-H1-03 | channel length L (HALL_INLET_Z0 to IP-EXIT) | 103.2 | mm | owner-fixed design value / owner-allocation / OWNER_DECISION | design value (owner-fixed); manufacturing tolerance TBD with the design release (H1F-CH-11 'tolerance TBD') | FROZEN |
| DBF1-H1-04 | derived radii r_in = (d_mean - h) / 2, r_out = (d_mean + h) / 2 | {"r_in_mm": 29.0, "r_out_mm": 41.0, "A_channel_mm2": 2638.937829} | mm; mm^2 | derived arithmetic / model-derived / DEFINITION | exact arithmetic on DBF1-H1-01 / 02 | FROZEN |
| DBF1-H1-05 | discharge-voltage operating band (operating variable, not a design value) | [180.0, 350.0] | V | owner allocation / owner-allocation / OWNER_DECISION | band ends as registered | FROZEN |
| DBF1-H1-06 | discharge-power band (H2-1) | [650.0, 1350.0] | W | owner allocation / owner-allocation / OWNER_DECISION | band ends as registered | FROZEN |
| DBF1-BZ-01 | B_r(z) shape target (design target) | monotonic rise toward the exit, peak at or just downstream of z = L; field near the anode as low as the circuit allows (numeric B_anode/B_peak TBD) | - | inferred design target / inferred / 5 | shape tolerance TBD (FEMM + owner tolerance, H1F-BZ-05) | FROZEN_ASSUMPTION |
| DBF1-BZ-02 | peak centreline B_r target band at / near IP-EXIT | [69.93, 268.6] | G | model-derived design target / model-derived / 6 | a window, not a point (r_Le <= 0.1 h over T_e 10-30 eV); point tolerance set at design release | FROZEN_ASSUMPTION |
| DBF1-BZ-03 | B_peak operating levels used by the simulation | {"BP-LO": 69.93, "BP-HI": 268.6} | G | model-derived design target / model-derived / 6 | the two band ends; no interior level registered | FROZEN_ASSUMPTION |
| DBF1-BZ-04 | simulation B(z) shape (surrogate) | BZ-P5B16 | - | digitized literature shape (surrogate) / digitized / 3 | P5 shape, not an H-1 field: SOURCED_SURROGATE_P5_SHAPE_NOT_H1_BZ (H1F-BZ-01 TBD); gradient, width and anode-to-peak ratio are P5 properties | FROZEN_ASSUMPTION |
| DBF1-BZ-05 | MC-1 field capability (necessary design capability) | 403.0 | G | model-derived / model-derived / 6 | B headroom 1.5 x the band upper end; FEMM pending | FROZEN_ASSUMPTION |
| DBF1-RF-01 | RF frequency | 13.56 | MHz | owner-fixed / owner-allocation / OWNER_DECISION | exact (ISM frequency) | FROZEN |
| DBF1-RF-02 | RF forward-power operating envelope at the generator / 50-ohm reference plane | [0.0, 500.0] | W | owner allocation (investigation capability) / owner-allocation / OWNER_DECISION | envelope ends as registered; P_fwd is never P_plasma (A9.2; Takahashi eta_p ~ 0.1, TK-26) | FROZEN_ASSUMPTION |
| DBF1-RF-03 | matching architecture | adjustable local match, on / immediately adjacent to the ICP module (match_colocated = true) | - | owner decision / owner-allocation / OWNER_DECISION | categorical | FROZEN |
| DBF1-RF-04 | RF component ratings (generator, coupler, coax, match, feedthrough) | >= the DBF1-RF-02 envelope upper end (500 W forward) | W | engineering assumption / assumed / 7 | ratings TBD_AFTER_IMPEDANCE_MAP (P2); RF peak voltage / current not registered (ICD ICP-44) | FROZEN_ASSUMPTION |
| DBF1-ICP-01 | ICP topology | open-tube coaxial downstream ICP, unmagnetized, CFG-CAP-OFF electron extraction topology per P1-IT-36 when registered | - | owner decision / owner-allocation / OWNER_DECISION | categorical | FROZEN |
| DBF1-ICP-02 | module geometry vector (L_standoff, r_aperture, r_module, L_module, tau_support) | {"L_standoff": 0.05, "r_aperture": 0.06, "r_module": 0.09, "L_module": 0.15, "tau_support": 0.0} | m; - | engineering assumption / assumed / 7 | a P3 grid point registered as the F6 state probe; F6 search not run (P1 / P2 evidence absent) | FROZEN_ASSUMPTION |
| DBF1-ICP-03 | NP-ICP v2 volume model | ASSUMED_GEOMETRIC_TUBE (V = pi R^2 L with R = r_aperture 0.06 m, L = L_module 0.15 m) | - | declared unvalidated modelling assumption / assumed / 7 | A9.31 sec. 10: not bench validation; a REGISTERED_EFFECTIVE volume supersedes it | FROZEN_ASSUMPTION |
| DBF1-ICP-04 | ion-collecting electrode (collector) | C-type electrode on the inner wall of the bore, 0.10 m axial length, axial slit for RF penetration; separately biased and metered, ICP body floating | m | literature topology precedent / as-reported / 3 | anchor axial length as reported (Takahashi Fig. 1b); the flight collector (ICD ICP-21) is TBD | FROZEN_ASSUMPTION |
| DBF1-ICP-05 | ICP neutral source / gas routing | G-REUSE (Hall exhaust -> ICP; mdot_ICP,dedicated = 0); capped dedicated port retained; declared variant G-XE | - | owner decision / owner-allocation / OWNER_DECISION | categorical | FROZEN |
| DBF1-ICP-06 | ICP body / collector isolation class | 350.0 | V | owner decision / owner-allocation / OWNER_DECISION | design withstand >= 525 V (P1-IT-43) | FROZEN |
| DBF1-ICP-07 | dielectric bore (vessel) material | borosilicate glass (pyrex class) | - | literature topology precedent / as-reported / 3 | flight dielectric not selected (P3-R-03 emittance TBD); AO / sputter compatibility not evidenced | FROZEN_ASSUMPTION |
| DBF1-IN-01 | upstream design vector (intake, filter, compressor, plenum, P_set) | A0.25_Ld20_phi0.9\|F4-FIL-T0.9\|T6-A1-U2-D0-Ti6Al4V-H0.5\|V0.001\|P0.02 | - | model-derived (F7 chain, PARAMETRIC_SENSITIVITY inputs) / model-derived / 6 | compressor coefficients code-default (PARAMETRIC_SENSITIVITY); surface accommodation TBD (10-scenario set); see DBF1-BD-01 / BD-02 | BASELINE_DEFICIENCY |
| DBF1-IN-02 | intake geometry (F1 candidate, d collapsed) | {"area_m2": 0.25, "L_over_d": 20.0, "phi": 0.9, "candidate": "A0.25_Ld20_phi0.9", "channel_diameter": "collapsed: every TPMC output is d-invariant at fixed L... | m^2; -; - | model-derived (F1 TPMC synthesis) / model-derived / 6 | TPMC statistical SE per state (F1); surface scenario TBD | FROZEN_ASSUMPTION |
| DBF1-IN-03 | TPMC surface-scenario basis | ["maxwell_a0", "maxwell_a0.2", "maxwell_a0.5", "maxwell_a0.8", "maxwell_a1", "cll_a0", "cll_a0.2", "cll_a0.5", "cll_a0.8", "cll_a1"] | - | model-derived scenario set / model-derived / 6 | accommodation unmeasured (DI-1.3); every admitted scenario is carried, none chosen (A9.13 S6.16) | FROZEN_ASSUMPTION |
| DBF1-IN-04 | filter case | F4-FIL-T0.9 | - | parametric sensitivity (loss-free species-independent screen, tau = 0.9) / assumed / 7 | filter material / geometry undefined (F2-IF-08); tau 0.7 / 0.5 and the placeholder law are the registered alternatives | FROZEN_ASSUMPTION |
| DBF1-IN-05 | compressor design (F3 design grid) | {"id": "T6-A1-U2-D0-Ti6Al4V-H0.5", "N_turbo": 6, "A_turbo_m2": 0.1963495408, "R_turbo_m": 0.2886751346, "u_tip_turbo_mps": 290.6899682, "rpm": 9615.946745, "... | -; m^2; m; m/s; rpm | model-derived (F3) / model-derived / 6 | turbo-row coefficients code-default (T-1 / T-2 open); hub geometry PARAMETRIC_SENSITIVITY | BASELINE_DEFICIENCY |
| DBF1-IN-06 | plenum volume / wall / target pressure | {"V_m3": 0.001, "wall_case": "WALL-G0", "P_set_Pa": 0.02} | m^3; -; Pa | parametric design value / assumed / 7 | V from the F4 decade grid; WALL-G0 = inert lining bound (gamma = 0, owner H1F-IN-02) | FROZEN_ASSUMPTION |
| DBF1-IN-07 | feed-loop controller (normalized PI on plenum pressure) | {"Kp": 0.3, "Ti_s": 3.0, "f_valve_hz": 1.0, "authority": 3.0} | -; s; Hz; - | definition / parametric / assumed / 7 | Kp, Ti one-decade definition grid; f_valve, authority PARAMETRIC_SENSITIVITY (H2-3 H23-18 / H23-07) | FROZEN_ASSUMPTION |
| DBF1-IN-08 | registered F7 performance of the frozen design (per covered scenario) | {"cll_a0.5": {"mdot_delivered_min_kg_s": 1.084126071518558e-08, "mdot_captured_min_kg_s": 4.08271125e-08, "P_compressor_el_max_W": 11.125100048512362, "drag_... | kg/s; W; N; kg; - | model-derived / model-derived / 6 | PARAMETRIC_SENSITIVITY | FROZEN |
| DBF1-PWR-01 | design power allocation (all flight loads at the spacecraft-side DC boundary) | 1350.0 | W | owner-fixed / owner-allocation / OWNER_DECISION | allocation (not a gate, not a CBE) | FROZEN |
| DBF1-PWR-02 | RFP bus-power gate (assessment only) | 1500.0 | W | frozen requirement / owner-allocation / OWNER_DECISION | strict '<' on P_bus,1ms,max (bus_power_boundary_a9_v2 gate) | FROZEN |
| DBF1-PWR-03 | common-load allocation (compressor + flow control + filter/getter + thermal control + housekeeping) | 300.0 | W | owner-fixed / owner-allocation / OWNER_DECISION | upper design value (row 114); controls / thermal allowance 50 W inside it | FROZEN |
| DBF1-PWR-04 | mapping to bus_power_boundary_a9_v2 | {"boundary": "bus_power_boundary_a9_v2 (flight configuration hall_icp_neutralizer; flight C1 loads NONE)", "slots_by_group": {"hall": ["hall_discharge", "hal... | - | owner allocation arithmetic / owner-allocation / OWNER_DECISION | exact arithmetic on owner allocations | FROZEN |
| DBF1-MASS-01 | system mass-margin policy | 0.1 | fraction of nominal dry | owner-fixed / owner-allocation / OWNER_DECISION | policy | FROZEN |
| DBF1-MASS-02 | nominal-dry mass target | 34.0 | kg (<=) | owner-fixed design target / owner-allocation / OWNER_DECISION | design target, not achieved evidence | FROZEN |
| DBF1-MASS-03 | reference Xe load | 2.0 | kg | owner-fixed reference / owner-allocation / OWNER_DECISION | planning / reference case; 5 / 10 kg sensitivities carried; not the selected flight Xe load | FROZEN |
| DBF1-MASS-04 | wet-mass target at the reference Xe load (arithmetic) | 39.4 | kg | arithmetic on owner values / owner-allocation / OWNER_DECISION | 34 x 1.10 + 2 = 39.4 kg | FROZEN |
| DBF1-TH-01 | thermal network topology (NP-THERMAL-CATHODELESS 2.0.0) | {"solved_nodes": ["H1_ANODE", "H1_WALL_IN", "H1_WALL_OUT", "H1_POLE_IN", "H1_POLE_OUT", "H1_BACKPLATE", "H1_COIL_IN", "H1_COIL_OUT", "H1_COIL_TRIM", "N_VESSE... | - | registered model topology / model-derived / 6 | lumped isothermal nodes (Biot check D-02); property / conductance / view-factor records TBD | FROZEN_ASSUMPTION |
| DBF1-TH-02 | spacecraft interface form | SCI-A conductance to a fixed spacecraft temperature at H1_BACKPLATE (isolated mount), N_MOUNT and R_HALL; values from the host thermal ICD | - | reference pending ICD / assumed / 7 | G_sc,a and T_sc not registered (OQ-NPT-01 open; no spacecraft thermal ICD) | REFERENCE_PENDING_ICD |
| DBF1-TH-03 | thermal design margin rule | {"margin_K": 50.0, "heat_load_factor": 1.2} | K; - | owner decision / owner-allocation / OWNER_DECISION | rule | FROZEN |
| DBF1-MAT-01 | H-1 anode / gas distributor material (primary) | INCONEL alloy 600 (chromia-forming Ni alloy) | - | datasheet bulk properties only / as-reported / 5 | every P4 gate cell INCOMPLETE_EVIDENCE (no gate-admissible property; no plasma / O exposure evidence) | FROZEN_ASSUMPTION |
| DBF1-MAT-02 | H-1 anode / gas distributor material (backup) | INCONEL alloy 601 (alumina-forming Ni-Cr-Al alloy) | - | datasheet bulk properties only / as-reported / 5 | every P4 gate cell INCOMPLETE_EVIDENCE (no gate-admissible property; no plasma / O exposure evidence) | FROZEN_ASSUMPTION |
| DBF1-MAT-03 | ICP ion-collecting electrode material (primary / backup) | {"primary": "INCONEL alloy 600 (chromia-forming Ni alloy)", "backup": "INCONEL alloy 601 (alumina-forming Ni-Cr-Al alloy)"} | - | datasheet bulk properties only / as-reported / 5 | every P4 gate cell INCOMPLETE_EVIDENCE (no gate-admissible property; no plasma / O exposure evidence); 316L permitted only for the Ar engineering reproductio... | FROZEN_ASSUMPTION |
| DBF1-MAT-04 | H-1 channel wall ceramic (primary / backup) | {"primary": "BN-SiO2 (borosil class)", "backup": "BN"} | - | flight practice (literature) / model setting / as-reported / 5 | no N+/N2+/O+/O2+ sputter yield on BN or BN-SiO2 in open sources; BN inner wall thermal UNRESOLVED against the 850 degC ceiling | FROZEN_ASSUMPTION |
| DBF1-DRAG-01 | reference host-spacecraft body (drag case) | {"case_id": "RC-DIAMANT", "record_id": "REF-T1-DIAMANT", "a_ref_m2": 0.5, "cd": 2.2, "cd_a_m2": 1.1, "shape": "not stated by the source (body frontal area on... | m^2; - | reference pending customer ICD (secondary literature) / as-reported / 5 | C_D as reported (secondary; GSI / accommodation basis not stated); SRD-03 spread C_D A 0.32-3.7 m^2 across declared cases; A_ref scope 'unstated' -> INTAKE_O... | REFERENCE_PENDING_ICD |
| DBF1-DRAG-02 | drag model | D(state) = q (C_D A_ref)_body + D_intake(state, scenario), q = 1/2 rho v^2 at the frozen orbit-resolved state (F1 envelope atmospheres); D_intake = F1 intake... | - | model-derived (Romano 2018 Eq. 1 form + F1 TPMC) / model-derived / 5 | body term C_D constant (no GSI); intake term per scenario (10 admitted, none chosen); attitude: flow-aligned, arrays parallel to flight (not stated by the bo... | REFERENCE_PENDING_ICD |
| DBF1-DRAG-03 | surface accommodation basis | body: as stated by the case source (not stated: C_D 2.2 is a literature-typical value); intake: the 10 admitted TPMC scenarios (Maxwell / CLL, alpha 0-1), re... | - | reference pending ICD / assumed / 7 | accommodation unmeasured (DI-1.3) | REFERENCE_PENDING_ICD |

Sources (path, sha256, pointer) and the rationale of every item are in the JSON.

## Selection rules (executed by the builder on registered candidates)

### SR-INTAKE-01 -> `A0.25_Ld20_phi0.9|F4-FIL-T0.9|T6-A1-U2-D0-Ti6Al4V-H0.5|V0.001|P0.02`

Pool: DS-F7-PARETO members (admitted F7 Pareto blocks, f7_pareto_blocks_v1) with context_role ARCHITECTURE_CONTEXT (an actual filter element; FC00 contexts are reference bounds only, A9.13 S6.5) whose F1 intake candidate is in DS-F1-ADMISSIBLE for that context's surface scenario (FEASIBLE_AT_STATE at every required state under F1 C-CONV and the intake-face drag filter C-DRAG-RFP <= 25 mN)

- 1. maximise n_s = the number of admitted surface scenarios in which the design vector is an F7 Pareto member (scenario robustness first: A9.13 S6.16, no favourable surface scenario is chosen)
- 2. maximise the worst-state delivered flow in its worst covered scenario: min over covered scenarios of the committed statewise-minimum mdot_delivered_min_kgps
- 3. tie-break: minimise the maximum compressor electrical power P_compressor_el_max_W
- 4. tie-break: minimise the compressor mass m_compressor_max_kg
- 5. tie-break: lexicographic design_id

### SR-MAT-01 -> `CAND-02A`

Pool: P4 candidate register (p4_anode_materials_v1 candidates) with Q0-matrix role CANDIDATE, a bulk (uncoated) material and an assigned R8 coupon; 316L excluded (REJECTED_AS_CURRENT_BASELINE for the flight anode; Q0 role ENGINEERING_REFERENCE_CONTROL_ONLY); reference / negative controls, reserve and non-Q0 entries excluded; coatings excluded (coating thickness / record TBD)

- 1. maximise the number of populated datasheet properties (P4 evidence_coverage)
- 2. a family whose R8 status is 'test only as hypothesis-control' (alumina formers: possible insulating scale on an electron- / ion-collecting electrode) ranks after the others
- 3. lexicographic candidate id
- backup: the highest-ranked candidate of a different oxide-former family than the primary (common-mode independence)
- result: primary `CAND-02A`, backup `CAND-03A`

### SR-DRAG-01 -> `RC-DIAMANT`

Pool: the declared reference drag cases of spacecraft_reference_drag_v1 (register crates/abep-mission/data/spacecraft_reference_register_v1.json) whose reference area does not already include the intake (SRD-04: the DBF-1 intake-face drag is a separate term)

- 1. applicability: the source spacecraft's altitude range overlaps 180-230 km AND its stated propulsion power class is <= 1.5 kW (cases without a stated power are not applicable)
- 2. among applicable cases the largest C_D A_ref (conservative: the frozen reference never favours T - D)
- 3. lexicographic case id

## Baseline deficiencies

| id | items | closure condition | finding | category |
|---|---|---|---|---|
| DBF1-BD-01 | DBF1-IN-01 | flow (A9.35 / A4 carry-forward): worst-state 12 mN needs >= 0.251 m^2 effective collection area and >= 0.048 mg/s at the ideal 1.5 kW limit | drag closes (intake-face drag <= 17.59 mN <= 25 mN) but flow does not: the frozen design delivers 1.428e-09 kg/s at its worst state in its worst covered scen... | DESIGN_VARIABLE_LIMIT (A9.35: A4-REG-01 open, no registered envelope bound) |
| DBF1-BD-02 | DBF1-IN-01 | robust feasibility in every admitted surface scenario (A2 NH-FLOW; A9.13 S6.16) | the design is an F7 Pareto member in 6 of 10 admitted scenarios; its FC00 twin is infeasible in the other four (compressor characteristic / dead-head); no re... | DESIGN_VARIABLE_LIMIT |
| DBF1-BD-03 | DBF1-IN-05 | compressor + drive within its line allocation (AL-02, row 54) | the F3 model mass of the selected compressor exceeds the AL-02 allocation; the registered candidates within 5.5 kg (T4 compressors) cover 2 scenarios at ~5x ... | DESIGN_VARIABLE_LIMIT |
| DBF1-BD-04 | DBF1-MASS-02 | nominal dry <= 34.0 kg; wet < 40 kg at the 2 kg reference Xe load | the current provisional planning roll-up (owner MEV lines + evidence floors; not a CBE) is above the 34 kg nominal-dry target and the 40 kg wet limit at 2 kg... | MISSING_EVIDENCE (no CBE) / DESIGN_VARIABLE_LIMIT (mass-closure actions MCA) |
| DBF1-BD-05 | DBF1-BZ-04 | an H-1 B(z) from FEMM of MC-1 or a measured map (H1F-BZ-01) | the simulated field is a P5-shape surrogate scaled into the H1F-BZ-03 band: a Hall non-closure under it is never eligible (envelope prereg bz_family classifi... | MISSING_EVIDENCE |
| DBF1-BD-06 | DBF1-ICP-02, DBF1-ICP-04 | ICP I_e,cap evaluable (NP-ICP v2 inputs registered and the AIR / Xe rate sets admitted) | with the frozen geometry and RF, I_e,cap stays NOT_EVALUATED: the remaining inputs are operating points or evidence, not design values | MISSING_EVIDENCE |

Numbers of each deficiency are in the JSON (`baseline_deficiencies[].numbers`).

## Change control

after DBF-1 no design value changes merely to improve M2 performance; any change needs a formal DCR naming the physical / evidence reason, approved before rerun (A9.37). Supplying converged Hall envelope data is an input completion, not a design change, and needs no DCR.

## Configuration registration

config/MANIFEST.json is pinned (sha256 3a85581e...) inside immutable committed records that tests regenerate byte for byte (NP-HALL-PARAMETRIC-ENVELOPE closure_run_today_v1.json, closure_run_m1_dryrun_v1.json, closure_run_m1_dryrun_v2.json); listing a new file there would change that pin and break their reproduction. DBF-1 is therefore pinned like the operating scenario (a code pin in abep-config), not through config/MANIFEST.json.

## Not

- not a performance prediction
- not a PASS / qualification / flight baseline approval
- not a change to any RFP requirement, owner decision or admitted / scored record
- not an M2 or M3 result
