# DBF-1.1 Design Baseline Freeze 1.1 - hall_icp_neutralizer (DCR-DBF1-002: FE-derived H-1 B(z))

Authoritative record: `dbf1_1_v1.json` (this page restates it). Machine-readable subset: `dbf1_1_config_v1.json` (read through `abep_config::baseline::load_dbf1_1`). Hash lock: `dbf1_1_lock_v1.json`. Change control: `docs/baseline/DBF-1/DCR_PROCESS.md`.

## Lineage

- parent: DBF-1, lock `517e0cf693712ec6d355c4b23791b9ae8626577fd338e3030563eb027e86b907` (immutable; never edited)
- change: DCR-DBF1-002, request `docs/baseline/DCR-002/dcr002_request_v1.json` (`ab55635ac29e2900e4baa459bfbaae9e4334412066bebc1cc03f77f765fcfca9`), approval `docs/baseline/DCR-002/dcr002_approval_v1.json` (`1718ac8061720959ea52e66e18723c23c3ece8d8c44fcfa41249d4f852c9bb55`), register `docs/baseline/DBF-1/dcr_register_v3.json`
- authority: coordinator ruling under owner delegation A9.34 (lane-level calls between milestones; this DCR changes no architecture item, no RFP requirement and no admitted / scored result); the owner may overrule, in which case DBF-1.1 is withdrawn and DBF-1 stays governing
- only change of value: DBF1-BZ-04 `BZ-P5B16` -> `BZ-H1FE-V1`; DBF1-BD-05 closed; every other item, selection rule and deficiency equals DBF-1

Approval conditions:

- DBF-1.1 is built as new files with its own lock; DBF-1 and every record computed on it stay immutable history
- surrogate and FE-field Hall records are never pooled
- a Hall run citing the FE field needs a new NP-HALL-PARAMETRIC-ENVELOPE addendum committed before the run
- measured B(z) on the engineering model remains an EM verification item

Hardware configuration (envelope terms): geometry `G-RP1`, B shape `BZ-H1FE-V1`.

## DBF1-BZ-04 (changed)

- value `BZ-H1FE-V1` (H1_FE_DERIVED_NOT_MEASURED); evidence: FE-derived (scikit-fem 10.0.2 axisymmetric nonlinear magnetostatics of the registered MC-1 circuit; FEMM-class per A9.14 F5-OQ-01); not measured, not FEMM
- uncertainty: shape envelope over the registered assumption ranges (wall thickness, pole thickness, coil placement, B-H bracket; prereg v4): FWHM 31.96-54.74 mm (nominal 36.79), z_peak - L -5.5 to -2.57 mm, B_anode/B_peak -0.0043 to -0.00065; shape bounds = CORNER-A / CORNER-B profiles; not covered: shielded pole contour (H1F-MC-05), hot B-H, procured-lot B-H; measured B(z) = EM verification item
- registration: rigid, no shift: B_profile = {file, align: 'anode', z_ref_in_file_mm: 0.0, scale_to: 'max'}, B_ref_T = B_peak_G x 1e-4; the file z is the H-1 z (z = 0 anode face, IP-EXIT at 103.2 mm)
- use: a Hall run citing this field needs a new NP-HALL-PARAMETRIC-ENVELOPE addendum committed before the run (approval condition)
- superseded DBF-1 value: `BZ-P5B16` (SOURCED_SURROGATE_P5_SHAPE_NOT_H1_BZ)

| role | id | file | sha256 | NI total [A-turns] | B_peak [G] |
|---|---|---|---|---|---|
| nominal | BP-LO | `hallthruster_bridge/bfield/h1_fe_v1/h1_fe_v1_Br_centerline_nominal_BP-LO.csv` | `1d3930d78921986f9acb6132de09f08bbe435b3df3b7216cd17dc2ddc8f996cc` | 153.7 | 69.91 |
| nominal | BP-HI | `hallthruster_bridge/bfield/h1_fe_v1/h1_fe_v1_Br_centerline_nominal_BP-HI.csv` | `ab86134579ce64d1802d85230376be17b613e1e48e8b2306d3ff94ab67690e62` | 587.1 | 268.6 |
| envelope | CORNER-A | `hallthruster_bridge/bfield/h1_fe_v1/h1_fe_v1_Br_centerline_envelope_maxFWHM_CORNER-A_BP-HI.csv` | `8fb762c381446fe2b9f614bdcac403a9b18e76dfd92401a64edb0786e1ef8702` | 783.4 | 268.6 |
| envelope | CORNER-B | `hallthruster_bridge/bfield/h1_fe_v1/h1_fe_v1_Br_centerline_envelope_minFWHM_CORNER-B_BP-HI.csv` | `c6bcf7beabfb80ee3a9867c0e5fab37c778282551ed19bad0f94097f676b2b84` | 497.5 | 268.6 |

## Frozen items

| id | item | value | units | evidence (class / type / level) | status |
|---|---|---|---|---|---|
| DBF1-H1-01 | channel mean diameter d_mean | 70.0 | mm | owner-fixed design value / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-H1-02 | channel width h | 12.0 | mm | owner-fixed design value / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-H1-03 | channel length L (HALL_INLET_Z0 to IP-EXIT) | 103.2 | mm | owner-fixed design value / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-H1-04 | derived radii r_in = (d_mean - h) / 2, r_out = (d_mean + h) / 2 | {"r_in_mm": 29.0, "r_out_mm": 41.0, "A_channel_mm2": 2638.937829} | mm; mm^2 | derived arithmetic / model-derived / DEFINITION | FROZEN |
| DBF1-H1-05 | discharge-voltage operating band (operating variable, not a design value) | [180.0, 350.0] | V | owner allocation / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-H1-06 | discharge-power band (H2-1) | [650.0, 1350.0] | W | owner allocation / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-BZ-01 | B_r(z) shape target (design target) | monotonic rise toward the exit, peak at or just downstream of z = L; field near the anode as low as the circuit allows (numeric B_anode/B_peak TBD) | - | inferred design target / inferred / 5 | FROZEN_ASSUMPTION |
| DBF1-BZ-02 | peak centreline B_r target band at / near IP-EXIT | [69.93, 268.6] | G | model-derived design target / model-derived / 6 | FROZEN_ASSUMPTION |
| DBF1-BZ-03 | B_peak operating levels used by the simulation | {"BP-LO": 69.93, "BP-HI": 268.6} | G | model-derived design target / model-derived / 6 | FROZEN_ASSUMPTION |
| DBF1-BZ-04 | simulation B(z) shape (H-1 FE-derived field) | BZ-H1FE-V1 | - | FE-derived (scikit-fem 10.0.2 axisymmetric nonlinear magnetostatics of the registered MC-1 circuit; FEMM-class per A9.14 F5-OQ-01); not measured, not FEMM / model-derived / 6 | FROZEN_ASSUMPTION |
| DBF1-BZ-05 | MC-1 field capability (necessary design capability) | 403.0 | G | model-derived / model-derived / 6 | FROZEN_ASSUMPTION |
| DBF1-RF-01 | RF frequency | 13.56 | MHz | owner-fixed / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-RF-02 | RF forward-power operating envelope at the generator / 50-ohm reference plane | [0.0, 500.0] | W | owner allocation (investigation capability) / owner-allocation / OWNER_DECISION | FROZEN_ASSUMPTION |
| DBF1-RF-03 | matching architecture | adjustable local match, on / immediately adjacent to the ICP module (match_colocated = true) | - | owner decision / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-RF-04 | RF component ratings (generator, coupler, coax, match, feedthrough) | >= the DBF1-RF-02 envelope upper end (500 W forward) | W | engineering assumption / assumed / 7 | FROZEN_ASSUMPTION |
| DBF1-ICP-01 | ICP topology | open-tube coaxial downstream ICP, unmagnetized, CFG-CAP-OFF electron extraction topology per P1-IT-36 when registered | - | owner decision / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-ICP-02 | module geometry vector (L_standoff, r_aperture, r_module, L_module, tau_support) | {"L_standoff": 0.05, "r_aperture": 0.06, "r_module": 0.09, "L_module": 0.15, "tau_support": 0.0} | m; - | engineering assumption / assumed / 7 | FROZEN_ASSUMPTION |
| DBF1-ICP-03 | NP-ICP v2 volume model | ASSUMED_GEOMETRIC_TUBE (V = pi R^2 L with R = r_aperture 0.06 m, L = L_module 0.15 m) | - | declared unvalidated modelling assumption / assumed / 7 | FROZEN_ASSUMPTION |
| DBF1-ICP-04 | ion-collecting electrode (collector) | C-type electrode on the inner wall of the bore, 0.10 m axial length, axial slit for RF penetration; separately biased and metered, ICP body floating | m | literature topology precedent / as-reported / 3 | FROZEN_ASSUMPTION |
| DBF1-ICP-05 | ICP neutral source / gas routing | G-REUSE (Hall exhaust -> ICP; mdot_ICP,dedicated = 0); capped dedicated port retained; declared variant G-XE | - | owner decision / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-ICP-06 | ICP body / collector isolation class | 350.0 | V | owner decision / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-ICP-07 | dielectric bore (vessel) material | borosilicate glass (pyrex class) | - | literature topology precedent / as-reported / 3 | FROZEN_ASSUMPTION |
| DBF1-IN-01 | upstream design vector (intake, filter, compressor, plenum, P_set) | A0.25_Ld20_phi0.9\|F4-FIL-T0.9\|T6-A1-U2-D0-Ti6Al4V-H0.5\|V0.001\|P0.02 | - | model-derived (F7 chain, PARAMETRIC_SENSITIVITY inputs) / model-derived / 6 | BASELINE_DEFICIENCY |
| DBF1-IN-02 | intake geometry (F1 candidate, d collapsed) | {"area_m2": 0.25, "L_over_d": 20.0, "phi": 0.9, "candidate": "A0.25_Ld20_phi0.9", "channel_diameter": "collapsed: every TPMC output is d-invariant at fixed L... | m^2; -; - | model-derived (F1 TPMC synthesis) / model-derived / 6 | FROZEN_ASSUMPTION |
| DBF1-IN-03 | TPMC surface-scenario basis | ["maxwell_a0", "maxwell_a0.2", "maxwell_a0.5", "maxwell_a0.8", "maxwell_a1", "cll_a0", "cll_a0.2", "cll_a0.5", "cll_a0.8", "cll_a1"] | - | model-derived scenario set / model-derived / 6 | FROZEN_ASSUMPTION |
| DBF1-IN-04 | filter case | F4-FIL-T0.9 | - | parametric sensitivity (loss-free species-independent screen, tau = 0.9) / assumed / 7 | FROZEN_ASSUMPTION |
| DBF1-IN-05 | compressor design (F3 design grid) | {"id": "T6-A1-U2-D0-Ti6Al4V-H0.5", "N_turbo": 6, "A_turbo_m2": 0.1963495408, "R_turbo_m": 0.2886751346, "u_tip_turbo_mps": 290.6899682, "rpm": 9615.946745, "... | -; m^2; m; m/s; rpm | model-derived (F3) / model-derived / 6 | BASELINE_DEFICIENCY |
| DBF1-IN-06 | plenum volume / wall / target pressure | {"V_m3": 0.001, "wall_case": "WALL-G0", "P_set_Pa": 0.02} | m^3; -; Pa | parametric design value / assumed / 7 | FROZEN_ASSUMPTION |
| DBF1-IN-07 | feed-loop controller (normalized PI on plenum pressure) | {"Kp": 0.3, "Ti_s": 3.0, "f_valve_hz": 1.0, "authority": 3.0} | -; s; Hz; - | definition / parametric / assumed / 7 | FROZEN_ASSUMPTION |
| DBF1-IN-08 | registered F7 performance of the frozen design (per covered scenario) | {"cll_a0.5": {"mdot_delivered_min_kg_s": 1.084126071518558e-08, "mdot_captured_min_kg_s": 4.08271125e-08, "P_compressor_el_max_W": 11.125100048512362, "drag_... | kg/s; W; N; kg; - | model-derived / model-derived / 6 | FROZEN |
| DBF1-PWR-01 | design power allocation (all flight loads at the spacecraft-side DC boundary) | 1350.0 | W | owner-fixed / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-PWR-02 | RFP bus-power gate (assessment only) | 1500.0 | W | frozen requirement / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-PWR-03 | common-load allocation (compressor + flow control + filter/getter + thermal control + housekeeping) | 300.0 | W | owner-fixed / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-PWR-04 | mapping to bus_power_boundary_a9_v2 | {"boundary": "bus_power_boundary_a9_v2 (flight configuration hall_icp_neutralizer; flight C1 loads NONE)", "slots_by_group": {"hall": ["hall_discharge", "hal... | - | owner allocation arithmetic / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-MASS-01 | system mass-margin policy | 0.1 | fraction of nominal dry | owner-fixed / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-MASS-02 | nominal-dry mass target | 34.0 | kg (<=) | owner-fixed design target / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-MASS-03 | reference Xe load | 2.0 | kg | owner-fixed reference / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-MASS-04 | wet-mass target at the reference Xe load (arithmetic) | 39.4 | kg | arithmetic on owner values / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-TH-01 | thermal network topology (NP-THERMAL-CATHODELESS 2.0.0) | {"solved_nodes": ["H1_ANODE", "H1_WALL_IN", "H1_WALL_OUT", "H1_POLE_IN", "H1_POLE_OUT", "H1_BACKPLATE", "H1_COIL_IN", "H1_COIL_OUT", "H1_COIL_TRIM", "N_VESSE... | - | registered model topology / model-derived / 6 | FROZEN_ASSUMPTION |
| DBF1-TH-02 | spacecraft interface form | SCI-A conductance to a fixed spacecraft temperature at H1_BACKPLATE (isolated mount), N_MOUNT and R_HALL; values from the host thermal ICD | - | reference pending ICD / assumed / 7 | REFERENCE_PENDING_ICD |
| DBF1-TH-03 | thermal design margin rule | {"margin_K": 50.0, "heat_load_factor": 1.2} | K; - | owner decision / owner-allocation / OWNER_DECISION | FROZEN |
| DBF1-MAT-01 | H-1 anode / gas distributor material (primary) | INCONEL alloy 600 (chromia-forming Ni alloy) | - | datasheet bulk properties only / as-reported / 5 | FROZEN_ASSUMPTION |
| DBF1-MAT-02 | H-1 anode / gas distributor material (backup) | INCONEL alloy 601 (alumina-forming Ni-Cr-Al alloy) | - | datasheet bulk properties only / as-reported / 5 | FROZEN_ASSUMPTION |
| DBF1-MAT-03 | ICP ion-collecting electrode material (primary / backup) | {"primary": "INCONEL alloy 600 (chromia-forming Ni alloy)", "backup": "INCONEL alloy 601 (alumina-forming Ni-Cr-Al alloy)"} | - | datasheet bulk properties only / as-reported / 5 | FROZEN_ASSUMPTION |
| DBF1-MAT-04 | H-1 channel wall ceramic (primary / backup) | {"primary": "BN-SiO2 (borosil class)", "backup": "BN"} | - | flight practice (literature) / model setting / as-reported / 5 | FROZEN_ASSUMPTION |
| DBF1-DRAG-01 | reference host-spacecraft body (drag case) | {"case_id": "RC-DIAMANT", "record_id": "REF-T1-DIAMANT", "a_ref_m2": 0.5, "cd": 2.2, "cd_a_m2": 1.1, "shape": "not stated by the source (body frontal area on... | m^2; - | reference pending customer ICD (secondary literature) / as-reported / 5 | REFERENCE_PENDING_ICD |
| DBF1-DRAG-02 | drag model | D(state) = q (C_D A_ref)_body + D_intake(state, scenario), q = 1/2 rho v^2 at the frozen orbit-resolved state (F1 envelope atmospheres); D_intake = F1 intake... | - | model-derived (Romano 2018 Eq. 1 form + F1 TPMC) / model-derived / 5 | REFERENCE_PENDING_ICD |
| DBF1-DRAG-03 | surface accommodation basis | body: as stated by the case source (not stated: C_D 2.2 is a literature-typical value); intake: the 10 admitted TPMC scenarios (Maxwell / CLL, alpha 0-1), re... | - | reference pending ICD / assumed / 7 | REFERENCE_PENDING_ICD |

Sources, uncertainty and rationale of every item are in the JSON.

## Baseline deficiencies

| id | items | category | status |
|---|---|---|---|
| DBF1-BD-01 | DBF1-IN-01 | DESIGN_VARIABLE_LIMIT (A9.35: A4-REG-01 open, no registered envelope bound) | OPEN |
| DBF1-BD-02 | DBF1-IN-01 | DESIGN_VARIABLE_LIMIT | OPEN |
| DBF1-BD-03 | DBF1-IN-05 | DESIGN_VARIABLE_LIMIT | OPEN |
| DBF1-BD-04 | DBF1-MASS-02 | MISSING_EVIDENCE (no CBE) / DESIGN_VARIABLE_LIMIT (mass-closure actions MCA) | OPEN |
| DBF1-BD-05 | DBF1-BZ-04 | MISSING_EVIDENCE | CLOSED_BY_DCR-DBF1-002 |
| DBF1-BD-06 | DBF1-ICP-02, DBF1-ICP-04 | MISSING_EVIDENCE | OPEN |

## Not

- not a performance prediction
- not a PASS / qualification / flight baseline approval
- not a change to any RFP requirement, owner decision or admitted / scored record
- not an M2 or M3 result
