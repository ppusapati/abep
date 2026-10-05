# NP-THERMAL-CATHODELESS preregistration v1

**Status: `PREREGISTERED_NOT_IMPLEMENTED`.** Method `NEW_PHYSICS`. Lifecycle state `PREREG_MODEL`. Validation status
`NOT_VALIDATED`. Docs only: this record writes no Rust, Python or Julia code and changes no other file.

* Model: the cathodeless thermal model of the selected flight architecture `hall_icp_neutralizer`. That architecture is one
  Hall thruster plus one downstream 13.56 MHz RF/ICP electron source / neutralizer, with no hollow cathode.
* Work package SC-WP-06, execution step ES-4, lane D (A9.29 sec. 13). Target crate `abep-subsystems::thermal`.
* Base: `integration/simulation-complete` at `e5528bd`.
* Machine-readable record (authoritative): `prereg_v1.json`. Lock: `prereg_lock_v1.json`. Where this page and the JSON
  differ, the JSON governs and the difference is a defect, fixed only by a new version.
* **No implementation before review.** No Rust code is written before this record is committed (A9.29 sec. 13). The owner
  reviews it before any Rust code (ES-4; RM-OQ-08; new-physics lifecycle). Owner review state: `PENDING_OWNER_REVIEW`.

## 1. Governing records

The JSON pins every record by sha256 (`governing_records` GR-01..GR-26).

* A9.29 (`OD_2026_10_05_A9_29_*`):
  * sec. 4: couple the RF/ICP losses into the cathodeless thermal model, and keep raw physics free of assessment;
  * sec. 9: the Rust-era test rule;
  * sec. 13: lane D;
  * secs. 14 and 15: standards that speed must not weaken, and the full chain.
* A9.28 (`OD_2026_10_05_A9_28_*`):
  * msg 1 sec. 5, RM-OQ-08: no Python cathodeless model is built as a parity target. The model is preregistered,
    implemented directly in Rust and admitted by independent verification.
  * msg 2 secs. 7, 8, 10 and 14.
* The plan at `origin/lane-rustplan-v2` `1236f91`:
  * `SIMULATION_COMPLETION_PROGRAMME.md` and `simulation_completion_programme_v1.json` (SC-WP-06; ES-4);
  * `programme_v3.json` (new-physics lifecycle; workspace);
  * `CI_PLAN.md` (principles 6 and 9);
  * `parity_contract_template_v3.json` (the `new_physics_verification` block, which the JSON mirrors).
* CLAUDE.md rules 3, 4, 6 and 10. The A9 binding statuses: anode material OPEN; anode and coupled H-1/ICP thermal closure
  UNRESOLVED, never reported as PASS.
* The cathode-path audit AFI-03; `gate_thresholds_v1.json` (HC-06); `hardware_bounds_v1.json`; the architecture config;
  `bus_power_boundary_a9_v2.json`; `hall_map_schema_v1.json`; `transport_ensemble_v0.json` (members `[]`); `PINNED.toml`;
  the A9, A9.2, A9.12, A9.19, A9.20 and A9.24 decision records.

**Read as context, never ported** (CX-01..CX-17):

* P3 v1 / v2 (JSON + MD) and P4;
* `thermal.py`, `thermal_life.py`, `icp_thermal_lib.py` and `THERMAL_LIFE_FRAMEWORK.md`;
* `limits_v1.json`, the legacy thermal-rejection ledger, the H2-5 network, the ICP ICD, the ICP evidence record, the A9.21
  hardware programme, mission scenario v2 and the design-state reference.

Their ids name future input suppliers; nothing else is taken from them.

* SC-WP-06 also lists two sets of retained kernels with their own parity contracts: K-P3-RAYS and the `thermal_life`
  Hall-discharge / magnet kernels.
* This model ports neither set. Their outputs enter only as registered inputs (view factors, IF-HALL-THERMAL-v1 values).
* Admission of this model does not depend on them.

## 2. What this is not

* Not an implementation.
* Not a thermal result or a thermal PASS. Anode and coupled H-1/ICP thermal closure stay UNRESOLVED.
* Not a port of the P3 v2 `h25_coupled_network`, the H2-5 network or `thermal.py` `default_nodes`.
* Not a Hall performance prediction. The credible Hall transport set is EMPTY.
* Not an RF/ICP plasma model. RF/ICP heat comes from NP-ICP-NEUTRALIZER.
* Not an assessment. No margin, limit, PASS/FAIL, HC status or requirement threshold is computed or carried.
* Not a material or geometry selection.
* Not a change to any frozen dataset, golden, threshold, budget or decision record.

**Numbers policy.** The record holds no physical property, view factor, geometry, load, environment or limit value. The
numbers that do appear are of these kinds:

* preregistered numerical tolerances and solver settings;
* verification vectors labelled `SYNTHETIC_TEST_DATA_NOT_EVIDENCE`;
* the exact Stefan-Boltzmann constant;
* two literature criteria, each marked verify (Biot 0.1 and coverage factor 2);
* the 180–230 km band and repository identifiers;
* owner values quoted only to state that they stay out of the equations: HC-06 50 K, the 25 / 50 / 100 W mount allocations
  and the 1.20 heat-load factor.

## 3. Architecture scope

* **Configuration.** `hall_icp_neutralizer` only. Any other configuration, including `hall_c1_reference`, is refused with
  `MODEL_ERROR`.
* **Hardware.** One H-1 Hall accelerator and one downstream RF/ICP neutralizer.
  * The flight hollow cathode is NONE.
  * C1 is `GROUND_REFERENCE_ONLY`. It is never a node, a load, a boundary or a case configuration here.
* **Supply modes.** `AIR_PRIMARY` and `XE_CONTINGENCY` are both case inputs.
  * The equations are gas-agnostic; the mode changes the interface loads.
  * `NON_FIRING` covers standby and cold cases. Its zero loads are registered, never defaulted.
* **Place in the A9.29 sec. 15 chain:** power → cathodeless thermal → mass.
  * Consumes SC-WP-01 (environment), SC-WP-03 (incl. NP-ICP-NEUTRALIZER), SC-WP-05 and SC-WP-09.
  * Supplies raw temperatures and heat flows to SC-WP-07, SC-WP-08, SC-WP-09, SC-WP-10 and SC-WP-11.

## 4. Exclusions

* **EX-01. No cathode node.** The H2-5 C-1 nodes `CB` (cathode body + keeper), `CE` (LaB6 emitter) and `CK` (keeper) are
  excluded per **AFI-03**.
* **EX-02. No cathode terms.** No `Q_cath`, keeper, cathode-heater or emitter term appears in any equation, key, node, link
  or output.
  * Any such identifier is refused (`MODEL_ERROR`, FT-10).
  * The crate passes the CI_PLAN principle-6 forbidden-identifier scan.
* **EX-03. The HC-06 50 K margin is not in the equations.** HC-06 is assessment protection policy; assessment applies it to
  the raw temperatures.
* **EX-04. No material temperature limit is an input or a field.** Limits are assessment inputs.
* **EX-05. Not ported.** P3 v2 `h25_coupled_network`, the H2-5 network and `thermal.py` `default_nodes`.
* **EX-06. No pre-ionizer slot.** That campaign is historical.
* **EX-07. The 1.20 heat-load factor is not in the equations.** If assessment needs it, its case builder scales the
  dissipated loads and labels the case.
* **EX-08. No requirement parsing.** The crate reads nothing under `docs/requirements/**` or `docs/decisions/**`.
* **EX-09. No owner allocation enters the equations.** This covers the mount allocations, the temporary RF thermal
  allocation and the ICP-43 bounding rule.

## 5. Nodes

**Rules.**

* Nodes are lumped and isothermal.
* Every node and every link is registered. There is no default node, link, conductance or property.
* A **REQUIRED** node is present in every case.
* A **CONDITIONAL** node is present only when the registered design has the part. When it is absent, its loads need a
  registered re-mapping; otherwise the run is `INCOMPLETE_EVIDENCE`.

**Thermal mass.**

* C_i(T) = Σ_p m_p c_p,p(T).
* The stored-energy change H_i(T) − H_i(T_a) = ∫ C_i dT is evaluated exactly for the registered c_p form.
* Masses come from registered geometry / BOM records. c_p(T) comes from material records that carry a temperature validity
  range.
* Massless series nodes are allowed only where registered.

| id | group | represents | presence |
|---|---|---|---|
| `H1_ANODE` | Hall body | anode / gas distributor | REQUIRED |
| `H1_WALL_IN` | Hall body | inner channel wall (ceramic) | REQUIRED |
| `H1_WALL_OUT` | Hall body | outer channel wall (ceramic) | REQUIRED |
| `H1_POLE_IN` | Hall body | inner magnetic core + inner front pole piece | REQUIRED |
| `H1_POLE_OUT` | Hall body | outer magnetic shell + outer front pole (exterior surfaces) | REQUIRED |
| `H1_BACKPLATE` | Hall body | back pole / back plate; carries anode isolators, feed interface, mount | REQUIRED |
| `H1_COIL_IN` | magnet | inner winding (copper, insulation, bobbin lumped) | REQUIRED |
| `H1_COIL_OUT` | magnet | outer winding(s) | REQUIRED |
| `H1_COIL_TRIM` | magnet | trim winding | CONDITIONAL |
| `N_VESSEL` | ICP | discharge vessel (dielectric tube / chamber wall) | REQUIRED |
| `N_ANTENNA` | ICP | 13.56 MHz antenna / coil incl. in-vacuum leads | REQUIRED |
| `N_COLLECTOR` | ICP | ion-collecting electrode (ICD ICP-21) | CONDITIONAL |
| `N_HOUSING` | ICP | housing / RF shield / feedthrough body | CONDITIONAL |
| `N_MATCH` | ICP | local matching network, iff `match_colocated` (ICD ICP-13) | CONDITIONAL |
| `N_MOUNT` | ICP | neutralizer mounting structure (flight bracket; bench KC-1 carrier) | REQUIRED |
| `R_HALL` | radiator | dedicated Hall radiator (A9.12 OQ-A907-06) | CONDITIONAL |
| `R_ICP` | radiator | dedicated ICP radiator / outward panel | CONDITIONAL |

**Materials.**

* **Anode material is OPEN.** Each run selects one registered P4 candidate property set (`CAND-01`..`CAND-16`).
  * `CAND-01` (316L) is `REJECTED_AS_CURRENT_BASELINE` for the flight anode. It is allowed only in labelled bench /
    parametric engineering cases (FT-16).
  * An unpopulated candidate gives `INCOMPLETE_EVIDENCE`.
  * P4 records are datasheet bulk values (typical, no plasma); they carry that domain.
* **Collector material is OPEN.** It is handled the same way.
* No other material is selected here.

**Boundaries.**

* **`B_SC`.** The spacecraft mounting interface (§ 9).
* **`B_PPU_RF`.** The PPU / RF-generator interface. It is a booking boundary only.
  * Heat booked here is reported raw and not solved: the generator conversion loss, reflected power absorbed at the
    generator, line losses outside the module, supply losses, and the match loss when the match is not co-located.
  * An optional registered conductive link may be declared. There is none by default.
* **`B_FEED`.** An optional registered link to the feed line at a registered temperature.
* **`SPACE`.** A black sink at the registered `T_space`.
* **`ENV`.** Absorbed environment loads, given per surface. ENV is not a node.
* **`B_FACILITY`.** Ground walls, used only in bench replicas. Their temperature is measured per run (owner row 131).

**Excluded nodes.**

* H2-5 `CB`, `CE` and `CK` (AFI-03).
* H2-5 `PIM`, the historical pre-ionizer slot.
* H2-5 `COMP` and `GP` (upstream chain; only `B_FEED` links may connect).
* The H2-5 `PPU` node, which exists here only as `B_PPU_RF`.
* `thermal.py` `default_nodes`.

**Refinement.**

* Splitting a node into same-group sub-nodes is a registered discretization refinement. This is how Biot compliance is
  restored.
* A new node group, a new key or a new link type needs a new version.

## 6. Equations

Notation: T in K; Q in W, positive into the receiving node. σ = 5.670374419e-8 W m⁻² K⁻⁴ (CODATA 2022, exact; registered as
`nist_codata_sigma`).

* **E-01 Transient node balance (enthalpy form).**
  dH_i/dt = Q_src,i + Q_tc,i + Q_env,i + Σ_j Q_cond,j→i + Σ_b Q_bc,b→i + Q_rad,i.
  * Q_src is the interface deposition and Q_tc the registered `Q_thermal_control_W`.
  * Source: the lumped-capacitance method (Incropera & DeWitt, verify V-01).
* **E-02 Steady state.** dH_i/dt = 0 for every node.
* **E-03 Conduction through a material segment (Kirchhoff transform).**
  Q = S_ij [Θ(T_j) − Θ(T_i)], with Θ(T) = ∫ k(T′) dT′ and S = A/L or 2πL/ln(r_o/r_i).
  * It is exact for steady 1-D conduction with k(T) and antisymmetric, so the link conserves energy exactly.
  * Source: Carslaw & Jaeger (verify V-04).
* **E-04 Contact and lumped conductances.** Q = h_c A_c ΔT for a registered joint, or Q = G ΔT for a registered measured
  assembly. Series composites use registered massless nodes.
* **E-05 Radiation.** Gray, diffuse, opaque surfaces in the IR band, solved by the net-radiation (radiosity) method.
  * J_k = ε_k σT_k⁴ + (1 − ε_k) G_k, with G_k = Σ_l F_kl J_l.
  * q_k = A_k ε_k (σT_k⁴ − G_k). This form stays valid at ε = 1.
  * `SPACE` or `B_FACILITY` closes the enclosure as a black surface.
  * Summation and reciprocity are input checks (D-07).
  * An opening is not a surface: surfaces that see each other through it belong to one enclosure.
  * View factors are registered inputs, either closed forms or K-P3-RAYS under its own contract.
  * Sources: Modest (verify V-02); Siegel & Howell (verify V-03); the Howell catalog entries C-40, C-41, C-52, C-77, C-80
    and C-81 (registered).
* **E-06 Environment loads per external surface.**
  * Q_sol = α S A F_sun ν(t).
  * Q_alb = α a S A F_alb.
  * Q_ir = ε q_OLR A F_earth.
  * Q_aero = α_E ½ρV³ A_ram.
  * α is the solar-band absorptance and ε the IR-band emittance.
  * S, a and q_OLR are registered hot / cold values. The candidate source is NASA/TM-2001-211221 (registered; its
    applicability needs verification, V-09).
  * ν and the factors come from SC-WP-09 and the registered attitude. ρ and V come from the frozen design states.
  * Sources: Gilmore (verify V-05); the free-molecular heating relation (verify V-06).
* **E-07 Interface deposition.** Q_src,i = Σ_key w_key,i Q_key.
  * For each key, the weights to nodes, EXPORT and BOUNDARY sum to exactly 1.
  * The weights are registered or come from the producer. They are never fitted here.
* **E-08 Boundary conditions.**
  * SCI-A: G_sc (T_sc − T_a).
  * SCI-B: a prescribed q_sc(t).
  * SCI-C: spacecraft surfaces as enclosure members.
  * Optional links to `B_PPU_RF` and `B_FEED`.
* **E-09 Electromagnet windings.**
  * `FIXED_POWER`: the registered Q.
  * `CONSTANT_CURRENT_R_OF_T`: Q = I² R_ref r(T)/r(T_ref), with r taken from the registered NBS Handbook 100 copper relation
    inside its domain. Outside that domain the run is `OUT_OF_DOMAIN`.
* **E-10 Steady solution.** Newton–Raphson with an analytic Jacobian and a backtracking line search.
* **E-11 Transient solution.** Implicit Euler on the enthalpy form.
  * Every input breakpoint is a step boundary, and sources are zero-order-hold values, so the input energy is exact.
  * Newton runs within each step. Formal order p = 1.
* **E-12 Orbits.**
  * `ORBIT_TRANSIENT_PERIODIC` gives T(t) and the raw min / max / mean per orbit.
  * `ORBIT_AVERAGE_STEADY` is a steady state under orbit-averaged loads. It is never reported as the time mean or the
    extremes of the periodic solution.
* **E-13 Interface-derived raw quantities.** These are defined in § 7.
* **E-14 Global statement.** Σ dH_i/dt = the deposited heat + Q_tc + Q_env − the net radiation to the sink − the boundary
  outflows.

**Link types.** There are four: `CONDUCTION`, `CONTACT`, `LUMPED_G` and `RADIATION`.

* Conduction exists only where a link is registered. The hashed topology record is the complete declaration.
* A radiation-only pair shares an enclosure but has no registered solid link. Whether a pair is radiation-only is always a
  design registration, never a default. Typical cases:
  * the anode and the channel walls across the channel;
  * unbonded coil-to-pole gaps;
  * the H-1 front faces and the ICP;
  * the vessel and an unbonded antenna.

## 7. Heat sources and interfaces

**Energy-source rule (HS-00).** Each watt enters through the interface of the supply that powers it. No watt enters twice,
and the model creates none.

| supply | interface |
|---|---|
| Hall discharge supply | IF-HALL-THERMAL-v1 discharge keys, incl. heat at the neutralizer from the discharge-current return and plume interception |
| Hall magnet supplies | IF-HALL-THERMAL-v1 coil keys |
| RF/ICP chain | IF-ICP-THERMAL-v1 |
| thermal control | `Q_thermal_control_W` |
| environment | `ENV` inputs |

**Interface records.**

* Every key carries a complete value record: value, units, status, evidence class, source, uncertainty, applicability domain
  and validation status.
* A missing field is `MODEL_ERROR`.
* A key whose status is not `EVALUATED` passes its status to the run. Nothing is zero-filled.
* The producer owns the key definitions; this record registers how they are consumed. A mismatch at integration is
  `MODEL_ERROR` and needs a v2 interface, never a silent remap.

### IF-HALL-THERMAL-v1

**Admission gate.**

* A map-derived value is accepted only from an **admitted** ensemble member's Hall-map point. The point must be
  `trustworthy` and `wall_life_trustworthy` and carry the pinned HallThruster.jl commit. This is the same gate as
  `thermal_life` G11.
* A screening candidate gives `NOT_EVALUATED`. A non-pinned commit gives `MODEL_ERROR`.
* The credible set is EMPTY, so every map-derived key is `NOT_EVALUATED` today. Registered parametric values run the
  verification and parametric cases.

| id | key | to | basis |
|---|---|---|---|
| HK-01 | `P_hall_discharge_W` | reference | schema `discharge_power_W` |
| HK-02 | `P_hall_jet_W` | reference | `anode_eff × discharge_power_W` = T²/(2ṁ_anode); a lower bound of the beam kinetic power (Cauchy–Schwarz) |
| HK-03 | `Q_hall_anode_W` | `H1_ANODE` | measured, or 2 I_d T_e,anode (Goebel & Katz Eq. 7.3-53, registered); T_e,anode is not a schema field |
| HK-04 | `Q_hall_wall_inner_W` | `H1_WALL_IN` | e Γ ε A + e Γ 2T_e,w/(1 − γ) A (registered relations) from schema `wall_ion_flux_m2s`, `wall_ion_energy_eV`; T_e,w and γ are not schema fields; inner/outer split registered |
| HK-05 | `Q_hall_wall_outer_W` | `H1_WALL_OUT` | as HK-04 |
| HK-06 | `Q_hall_pole_W` | `H1_POLE_IN` / `H1_POLE_OUT` (registered split) | no schema field |
| HK-07 | `Q_hall_plasma_radiation_W` | registered split over H-1 nodes, ICP nodes facing the exit, EXPORT | no schema field |
| HK-08 | `Q_hall_return_to_icp_W` | `N_COLLECTOR` | ICD ICP-22 / ICP-43 Q_coll; powered by the discharge supply; no producer today |
| HK-09 | `Q_hall_plume_to_icp_W` | registered split over ICP nodes and `N_MOUNT`, or K-P3-RAYS interception with a measured plume distribution | ICP-29; A9.14 ICPQ-09 |
| HK-10 | `Q_hall_coil_{inner,outer,trim}_W` | `H1_COIL_*` | `FIXED_POWER` mode (SC-WP-05) |
| HK-11 | `I_hall_coil_X_A`, `R_hall_coil_X_ref_ohm`, `T_hall_coil_X_ref_K` | `H1_COIL_*` via E-09 | `CONSTANT_CURRENT_R_OF_T` mode |

**Derived raw quantities (E-13).** Σ_dep,H = anode + inner wall + outer wall + pole + the deposited share of plasma radiation
+ the return heating at the ICP.

* `P_hall_exported_W` = P_d − Σ_dep,H − `Q_hall_plume_to_icp_W`.
* `P_hall_unattributed_W` = P_d − P_jet − Σ_dep,H. It is reported raw and deposited on no node (OQ-NPT-09).

**Checks.**

* **IFH-1.** Every key is complete. A failure gives `MODEL_ERROR`, `INCOMPLETE_EVIDENCE` or `NOT_EVALUATED`.
* **IFH-2.** Every value is ≥ 0.
* **IFH-3.** Σ_dep,H ≤ P_d − P_jet + ε_if.
* **IFH-4.** Σ_dep,H + plume-to-ICP ≤ P_d + ε_if.
* A violation of IFH-2, IFH-3 or IFH-4 is `MODEL_ERROR` and is never tuned away.

### IF-ICP-THERMAL-v1 (producer NP-ICP-NEUTRALIZER)

| id | key | consumer meaning | to |
|---|---|---|---|
| IK-01 | `Q_icp_plasma_wall_W` | RF-sustained plasma heat to internal surfaces | NP-ICP per-surface split, else registered `f_pw` over `N_VESSEL`, `N_COLLECTOR`, `N_ANTENNA` (if exposed), `N_HOUSING` |
| IK-02 | `Q_icp_coil_ohmic_W` | ohmic loss in the antenna; induced losses in nearby conductors where declared | `N_ANTENNA`, with registered induced shares to `N_COLLECTOR` / `N_HOUSING` (context only: the analog reports electrode heating by eddy currents) |
| IK-03 | `Q_icp_match_W` | matching-network loss | `N_MATCH` if `match_colocated`, else booked at `B_PPU_RF` |
| IK-04 | `Q_icp_extraction_W` | power carried by extracted electrons into the Hall plume | **EXPORT.** Deposited on no node; reported raw in `P_exported_W`; re-deposition not modelled in v1 (A-05) |
| IK-05 | `Q_icp_radiation_W` | optical / UV emission of the ICP plasma (not solid IR emission) | registered split `f_rad` over ICP nodes, H-1 pole faces, EXPORT; never through the IR enclosure |
| IK-06 | `P_icp_rf_forward_W` | generator-side forward power (never plasma power) | reference only |
| IK-07 | `P_icp_bus_W` | ICP demand at the spacecraft DC boundary | reference; `Q_icp_boundary_W` = P_icp_bus − Σ_I is booked at `B_PPU_RF` |

Σ_I = plasma-wall + coil-ohmic + match + extraction + radiation.

**Checks.**

* **IFI-1.** All seven keys are complete.
* **IFI-2.** Every value is ≥ 0.
* **IFI-3.** P_forward ≤ P_bus + ε_if.
* **IFI-4.** Σ_I ≤ P_bus + ε_if.
* **IFI-5.** Σ_I ≤ P_forward + ε_if. This applies only when the producer declares that the five keys are RF-powered only.
* A violation is `MODEL_ERROR`.

**Alignment with NP-ICP is open (OQ-NPT-02).** The open points are:

* which slots P_bus includes;
* where the collector-bias power is carried;
* that Hall-powered heat stays out of the ICP keys;
* whether the line loss is inside `Q_icp_match_W`;
* who predicts the splits.

**Status today: `NOT_EVALUATED`.**

* NP-ICP is not implemented or admitted.
* There is no P1 / P2 evidence.
* ICP45 is `NOT_EVALUATED`.
* The RF ratings are `TBD_AFTER_IMPEDANCE_MAP`.

### Thermal control and environment

* **`Q_thermal_control_W`.** A registered schedule per node for the bus slot `thermal_control`. There is no control law in
  v1. The name avoids the forbidden load-name token "heater".
* **Environment.** S, a, q_OLR, the view factors, ν(t), ρ, V, α_E, A_ram and T_space are registered per surface and case.
  The 196 frozen design states cover 180–230 km. No value is set here.

## 8. Energy boundaries

* **Inside the control volume:** the solid parts of the H-1 body and coils, the ICP module (incl. a co-located match and
  the mount), the dedicated radiators and their links.
* **Outside:**
  * the Hall and ICP plasmas, which enter only as interface keys;
  * the plume and beam;
  * the PPU and RF generator;
  * the spacecraft;
  * the upstream chain (intake, filter, compressor, plenum, valves, Xe tank), connected only through registered `B_FEED`
    links;
  * the environment.
* **Crossing terms:**
  * In: deposited interface heat, thermal-control dissipation, absorbed environment, boundary-link inflow.
  * Out: net radiation to the sink, boundary-link outflow.
  * Exported, never deposited: `P_hall_exported_W` (incl. the jet), `Q_icp_extraction_W`, and the EXPORT shares of plasma
    radiation.
  * Booked at `B_PPU_RF`: `Q_icp_boundary_W`, and the match loss when the match is not co-located.
* There is no electrical model inside. Electrical powers are references for the interface identities only.
* The booked flows reconcile with the SC-WP-05 bus ledger in the system energy-ledger check (rule 4, < 2 %). That check
  sits outside the thermal equations.

## 9. Spacecraft interface

* **SCI-A, conductance to a fixed temperature.** Q = G_sc (T_sc − T_a) at each registered attachment node: `H1_BACKPLATE`
  through the isolated mount, `N_MOUNT`, and the radiators as registered.
* **SCI-B, prescribed flux.** Q = q_sc(t) is prescribed, for example from a host ICD. The attachment temperature is then an
  output.
* **SCI-C, radiative view.** Host spacecraft surfaces join an enclosure at a registered temperature and emittance.
* **Outputs.** `Q_sc_interface_W` and the temperature of each attachment node, raw.
* **Status today.** There is no host-spacecraft thermal ICD, so flight runs are `NOT_EVALUATED` for this interface.
  * The owner mount cases (row 85; A9.12 OQ-A907-06; P3-M-05) are candidate boundary cases, pending OQ-NPT-01.
  * The 25 / 50 / 100 W mount allocations are assessment allocations. They never enter the equations.

## 10. Registered inputs and case classes

**Record format** (rules 6 and 10): id, quantity, value / bounds / table, units, source (path + sha256 or citation +
locator), evidence class, uncertainty, applicability domain (incl. temperature range), validation status and status.

**Rules.**

* There is no default value.
* A missing field is `MODEL_ERROR`.
* A TBD / OPEN record that the case needs gives `INCOMPLETE_EVIDENCE`.
* A REFUSED upstream value is never reconstructed.
* Synthetic and evidence records never mix in one case.

**Input classes and their status today.**

* `RI-GEOM`: TBD.
* `RI-MAT`: the anode and collector materials are OPEN; nothing else is selected.
* `RI-OPT`: TBD.
* `RI-COND`: TBD.
* `RI-VF`: the geometry is TBD.
* `RI-ENV`: the flight attitude and view factors are TBD.
* `RI-SC`: `NOT_EVALUATED` (no ICD).
* `RI-PART`: TBD.
* `RI-LOAD`: `NOT_EVALUATED`.
* `RI-CASE`: defined here.
* `RI-NUM`: fixed here.

**Case classes.**

* `SYNTHETIC_VERIFICATION`: synthetic inputs only. Its outputs are never quoted as physical values.
* `PARAMETRIC`: registered parametric loads and geometry, labelled `PARAMETRIC_NOT_A_PREDICTION`. It never gives an
  absolute flight result.
* `BENCH_REPLICA`: the ground `hall_icp_neutralizer` article (never `hall_c1_reference`), with a measured facility sink.
  It is used only for calibration and validation.
* `FLIGHT_CONDITIONAL`: the flight configuration with every input registered. Today it is `NOT_EVALUATED`.

## 11. Outputs (raw only)

The outputs are:

* `run_status` and `status_reasons`;
* `T_node_K` (steady), `T_node_K_series` / `t_s` (transient) and `T_node_orbit_stats_K` (raw per-orbit min / max / mean);
* `dH_node_J`;
* heat flows: `Q_link_W`, `Q_rad_net_W`, `Q_env_abs_W` by component, `Q_to_sink_W`, `Q_boundary_W` (spacecraft,
  PPU/RF-booked, feed), `Q_source_node_W` and `P_exported_W`;
* `energy_balance`: per-node and global residuals, Q_scale and the transient energy-integral residual;
* `convergence`;
* `domain_diagnostics`: Biot number per node, property-domain checks and the internal-gradient estimate;
* `provenance`: the prereg sha256, `implementation = rust`, `rust_commit`, the input hashes, the architecture / config /
  model-set / design-state hashes, the case class, the supply mode, the design state, `ensemble_member_id` when a map is
  used, and `validation_status = NOT_VALIDATED`.

**What the outputs never carry.**

* No margin, limit, PASS/FAIL, compliance label, threshold or HC status.
* No key is named margin, limit, pass, fail, compliant or feasible, and no key is prefixed `chk_`, `rfp_` or `ic_`.
* Assessment applies the material limits and the HC-06 50 K margin to these raw temperatures.

**On refusal.**

* For `MODEL_ERROR`, `NOT_EVALUATED`, `INCOMPLETE_EVIDENCE` and `OUT_OF_DOMAIN`, no temperature or heat flow is emitted as a
  result. For `OUT_OF_DOMAIN`, `domain_diagnostics` names the node and the criterion.
* No half-converged or extrapolated state is ever emitted (rule 3).

## 12. Status vocabulary

| status | when |
|---|---|
| `MODEL_ERROR` | malformed record; interface identity violated; inconsistent view factors; floating node; forbidden identifier; refused configuration or candidate; non-convergence |
| `NOT_EVALUATED` | determining evidence absent by governance: no admitted Hall member, NP-ICP not admitted, no host ICD, a key `NOT_EVALUATED` |
| `INCOMPLETE_EVIDENCE` | a needed input is TBD / OPEN / REFUSED, or a conditional node is absent without a re-mapping |
| `OUT_OF_DOMAIN` | property or relation outside its range; Bi > 0.1; design state outside `design_states_v2`; variant `active_cooling` or `icp_assist_magnet` |
| `CONVERGED` | solved; every conservation and domain criterion met |

**Precedence.** The checks run in this order, and every reason is recorded:

1. record and topology validation;
2. evidence availability;
3. the solve;
4. the domain checks.

`run_status` is the first status reached, in the order `MODEL_ERROR`, `NOT_EVALUATED`, `INCOMPLETE_EVIDENCE`,
`OUT_OF_DOMAIN`, `CONVERGED`.

## 13. Assumptions

* **A-01.** Nodes are isothermal. Lumping is checked by Biot (D-02).
* **A-02.** Surfaces are opaque, gray and diffuse in the IR. Environment absorption uses the solar-band α (two-band
  treatment; verify V-05, V-15).
* **A-03.** The plasmas are IR-transparent. Their optical emission enters only as interface sources (verify V-17).
* **A-04.** There is no convection and no gas conduction. Propellant enthalpy flow is neglected in v1.
* **A-05.** Exported power is not re-deposited, except through `Q_hall_plume_to_icp_W`.
* **A-06.** Interface values are taken as given. The model derives and fits no plasma quantity.
* **A-07.** Time series are zero-order-hold.
* **A-08.** Properties are evaluated at the node temperature. A Kirchhoff link uses the node temperatures as its end
  temperatures.
* **A-09.** There is no thermostat in v1.
* **A-10.** The thermal design is passive only. `active_cooling` gives `OUT_OF_DOMAIN`.
* **A-11.** The geometry is fixed and view factors are registered. An opening is not a surface.
* **A-12.** Eclipse, Earth-IR and albedo factors come from SC-WP-09 and the registered attitude.
* **A-13.** `T_space` is registered (OQ-NPT-07).
* **A-14.** Isolation hardware enters only as registered conductances. The only electro-thermal coupling is the coil R(T).
* **A-15.** Contact conductances do not depend on temperature unless their record says so.
* **A-16.** There is no ageing, AO exposure or erosion of properties. End-of-life property sets are case inputs.
* **A-17.** DC magnets cause no eddy heating. RF-induced heating enters only through the `Q_icp_coil_ohmic_W` split.

## 14. Domains

* **D-01, property validity.** Each record has [T_min, T_max]. Outside it the run is `OUT_OF_DOMAIN`, with no extrapolation
  and no clamping.
* **D-02, lumped capacitance.** Bi_i = h_eff L_c / k ≤ 0.1, with L_c = V/A_s and h_eff = (Σ link G + Σ 4εσT³A)/A_s,
  evaluated at the solution.
  * A violation is `OUT_OF_DOMAIN`, and the remedy is a registered subdivision.
  * Synthetic verification cases are exempt and labelled `BIOT_NOT_APPLICABLE_SYNTHETIC`.
  * The 0.1 criterion needs verification (V-01).
* **D-03, radiation model.** ε / α records must cover the node temperatures. A record that is non-gray within a band is
  refused unless a two-band split is registered.
* **D-04, vacuum.** A bench replica registers the facility pressure, and the criterion under which A-04 holds, before any
  data.
* **D-05, operating domain.**
  * The configuration is `hall_icp_neutralizer`.
  * Flight supply modes are `AIR_PRIMARY`, `XE_CONTINGENCY` and `NON_FIRING`. Bench gases are allowed only in bench
    replicas.
  * The design state must be in `design_states_v2` (180–230 km, 196 states).
  * The `active_cooling` and `icp_assist_magnet` variants are outside v1.
* **D-06, interface values.** An interface value's `OUT_OF_DOMAIN` or `NOT_EVALUATED` status propagates to the run.
* **D-07, topology and view factors.**
  * A floating node is `MODEL_ERROR`.
  * Each enclosure needs |Σ_l F_kl − 1| ≤ 1e-9 and a relative reciprocity error ≤ 1e-9, else `MODEL_ERROR`.
  * Any symmetrization is the producer's registered step, never a silent one here.
* **D-08, steady convergence.** NUM-01 together with CONS-S1 and CONS-S2.
* **D-09, peaks and minima.** These come only from transient or periodic runs. The ratio of the largest node time constant
  to the orbit period is reported raw.
* **D-10, temperature range.** There is no global range. A run is valid within the intersection of the property ranges it
  uses.

## 15. Numerics and conservation (tolerances fixed now)

**Numerics.**

* **NUM-01.** The steady Newton solve stops when CONS-S1 and CONS-S2 hold and the last max |dT| ≤ 1e-8 K. After 100
  iterations it is `MODEL_ERROR`.
* **NUM-02.** The initial guess is the registered case input `T_init`.
* **NUM-03.** Each transient step's Newton solve stops when the last max |dT| ≤ 1e-9 K. After 50 iterations the step is
  halved. Stored energy is taken relative to the initial state.
* **NUM-04.** Step doubling enforces CONS-T2. After 20 successive halvings the run is `MODEL_ERROR`.
* **NUM-05.** A periodic run gets at most 200 orbits, then `MODEL_ERROR`.
* **NUM-06.** Arithmetic is IEEE-754 binary64. Reductions run in node-id order, and nothing depends on the thread count.
* **NUM-07.** Linear solves use dense LU with partial pivoting.
* **NUM-08.** Q_scale is the sum of the magnitudes of all source, environment, boundary and sink terms.
* **NUM-09.** ε_if = 1e-6 × the reference power + 1e-9 W.

**Conservation.**

| id | check | tolerance |
|---|---|---|
| CONS-S1 | steady per-node residual | ≤ 1e-9 Q_scale + 1e-9 W |
| CONS-S2 | steady global balance (sources + environment − sink radiation − boundary outflow) | ≤ 1e-9 Q_scale + 1e-9 W |
| CONS-T1 | transient energy integral: ΔH_total = Σ dt Q_net, per step and cumulative | ≤ 1e-8 max(Σ dt Q_abs, \|ΔH\|) + 1e-6 J |
| CONS-T2 | time-step refinement, \|T_dt − T_dt/2\| (reported as u_num,t) | ≤ 1e-2 K |
| CONS-T3 | periodic steady state, \|T(t+P) − T(t)\| | ≤ 1e-3 K |
| CONS-I1 | interface identities IFH-3/4, IFI-3/4/5 | ε_if |
| CONS-I2 | deposition bookkeeping: deposited + exported + booked = interface inputs | ≤ 1e-12 relative + 1e-12 W |
| CONS-L1 | system energy ledger vs the SC-WP-05 bus ledger (rule 4) | < 2 %, checked by the system ledger check |

## 16. Analytic limiting cases (verification pass criteria)

* These are software verification criteria (CI_PLAN principle 9). They are not model outputs and not gate statuses.
* Every vector is `SYNTHETIC_TEST_DATA_NOT_EVIDENCE`, and each case must also meet the conservation checks that apply to it.
* `VS-NET` is the synthetic full-topology network. It is registered with its sha256 before the first scored run.

| id | case | closed form | pass criterion |
|---|---|---|---|
| AL-01 | single isothermal radiator; Q {1, 100, 1000} W, ε {0.1, 0.5, 1.0}, A {0.01, 0.1, 1} m², T_s {0, 300} K | T = (Q/(εσA) + T_s⁴)^¼ | \|ΔT\| ≤ 1e-6 K, all 54 combinations |
| AL-02 | two-node series conduction; Q {1, 10, 50} W, G1, G2 {0.1, 1, 10} W/K, T_b {250, 300} K | T1 − T_b = Q (1/G1 + 1/G2) | \|ΔT\| ≤ 1e-6 K; link flows = Q within 1e-9 |
| AL-02b | linear k(T) slab (Kirchhoff); Q {1, 10}, S {0.1, 1} m, k0 {10, 100}, β {−1e-3, 0, 1e-3}, T0 300 K | Q = S k0 (x + βx²/2), x = T1 − T0 | \|ΔT\| ≤ 1e-6 K |
| AL-03 | first-order transient; C {100, 1000} J/K, G {0.5, 5} W/K, Q {0, 100} W, T0 {250, 350} K, T_b 300 K, to 10τ | T_∞ + (T0 − T_∞) e^(−t/τ), τ = C/G | max error ≤ 1e-3 \|T_∞ − T0\| at dt = τ/1000; observed order within ±0.1 of 1 at dt = τ/100; CONS-T1 |
| AL-04 | two-surface enclosure; ε1, ε2 {0.05, 0.5, 1.0}; concentric (F12 = 1, A1/A2 {0.1, 0.5, 1}) and sphere patches (F12 = A2/(A1 + A2)); prescribed (T1, T2) {(400, 300), (300, 400), (1000, 3)}; loaded Q {10, 100} W with T2 300 K | Q12 = σ(T1⁴ − T2⁴)/[(1 − ε1)/(ε1A1) + 1/(A1F12) + (1 − ε2)/(ε2A2)] | 1e-9 relative (prescribed); \|ΔT\| ≤ 1e-6 K (loaded) |
| AL-05 | zero load on VS-NET; all sinks at T_s {3, 250, 300} K | T_i = T_s; link flows 0 | \|ΔT\| ≤ 1e-6 K; \|flow\| ≤ 1e-9 W |
| AL-06 | step load on VS-NET from equilibrium at 250 K, to 30 τ_max | ΔH = ∫ Q_net dt; T(t_end) = steady solution | CONS-T1 every step; \|T − T_steady\| ≤ 1e-3 K |
| AL-07 | coaxial disks + SPACE (Howell C-41, registered); then F perturbed by 1e-6 | A_kF_kl = A_lF_lk; Σ F = 1 | accept; perturbed sets refused `MODEL_ERROR` |
| AL-08 | sphere in four patches (0.1, 0.2, 0.3, 0.4; F_kl = A_l/A); ε {0.05, 0.3, 0.7, 1.0} | isothermal at 300 K: q_k = 0; black at 300 to 600 K: Q_kl = σA_kF_kl(T_k⁴ − T_l⁴) | \|q_k\| ≤ 1e-12 σA_kT⁴; 1e-9 relative |
| AL-09 | one-sided plate, 1 m², 0 K sink; α {0.2, 0.9}, ε {0.1, 0.9}, S_syn {1000, 1400}, q_syn {0, 200}, F_e {0, 0.5}, q_aero,syn {0, 25} W/m² | T = ((αS + εqF_e + α_E q_aero)/(εσ))^¼ | \|ΔT\| ≤ 1e-6 K; components exact to 1e-12 |
| AL-10 | interface bookkeeping on VS-NET: consistent set; violations of IFH-2/3/4, IFI-2/3/4; missing key; TBD key; `NOT_EVALUATED` key | CONS-I2; extraction deposited nowhere; match on `N_MATCH` iff co-located | exact landing; `MODEL_ERROR` / `MODEL_ERROR` / `INCOMPLETE_EVIDENCE` / `NOT_EVALUATED` |
| AL-11 | winding R(T) = R_ref(1 + a(T − T_ref)), domain [200, 1000] K; R_ref 1 Ω, a {0, 0.004}, T_ref 293.15 K, I {1, 3} A, G {0.1, 1} W/K, T_b 300 K; runaway I 10 A, G 0.1, a 0.004 | T = (G T_b + I²R_ref(1 − aT_ref))/(G − I²R_ref a) | \|ΔT\| ≤ 1e-6 K (8 cases); runaway → `OUT_OF_DOMAIN` |

## 17. Fail-closed tests, determinism, independent verification

**Fail-closed tests.** Each is asserted, never skipped (A9.29 sec. 9).

* **FT-01.** A flight case whose Hall keys must come from the EMPTY credible set gives `NOT_EVALUATED`, reason
  `CREDIBLE_HALL_TRANSPORT_SET_EMPTY`. It is asserted, not xfailed.
* **FT-02.** A screening candidate gives `NOT_EVALUATED`. A non-pinned commit gives `MODEL_ERROR`.
* **FT-03.** A TBD or OPEN input gives `INCOMPLETE_EVIDENCE`.
* **FT-04.** A malformed record gives `MODEL_ERROR`.
* **FT-05.** Synthetic data in a non-synthetic case gives `MODEL_ERROR`.
* **FT-06.** A property used outside its range gives `OUT_OF_DOMAIN`.
* **FT-07.** Bi > 0.1 gives `OUT_OF_DOMAIN`.
* **FT-08.** A Newton, step-refinement or periodic cap gives `MODEL_ERROR`.
* **FT-09.** A floating node gives `MODEL_ERROR`.
* **FT-10.** A cathode, keeper, emitter, `Q_cath`, LaB6 or C1 identifier gives `MODEL_ERROR`.
* **FT-11.** A configuration other than `hall_icp_neutralizer` gives `MODEL_ERROR`.
* **FT-12.** The `active_cooling` or `icp_assist_magnet` variant gives `OUT_OF_DOMAIN`.
* **FT-13.** A violated interface identity gives `MODEL_ERROR`.
* **FT-14.** An inconsistent view-factor set gives `MODEL_ERROR`.
* **FT-15.** A design state outside the set gives `OUT_OF_DOMAIN`.
* **FT-16.** `CAND-01` in a flight case gives `MODEL_ERROR`.
* **FT-17.** A static scan finds no forbidden output key, and `validation_status` is present.
* **FT-18.** A `NOT_EVALUATED` key is never zero-filled.

**Determinism.**

* Outputs are byte-identical on a double run and across thread counts.
* Every output carries `implementation = rust`, `rust_commit`, the prereg sha256 and the input hashes.

**Independent verification.** All of it is non-authoritative.

* **IV-01. Python scratch cross-check.** It evaluates the closed forms independently, plus a VS-NET solve by different
  algorithms.
  * Tolerances: 1e-6 K steady, 1e-2 K transient, 1e-8 relative energy.
  * It is never a CI, reference or active-path dependency.
  * A disagreement blocks `VERIFIED` until the report explains it. Nothing is tuned.
* **IV-02. Howell C-40 / C-41.** Two gray coaxial disks closed by SPACE, solved by hand as a three-surface system. Tolerance
  1e-9 relative.
* **IV-03. Standard-text worked examples.** Verify V-01. The check is `NOT_PERFORMED` if the text cannot be accessed
  lawfully. No number is quoted here.

## 18. Validation plan

Validation is separate from verification.

* Until measured evidence meets the comparison criteria, every output is `NOT_VALIDATED`.
* Anode and coupled H-1/ICP closure stay UNRESOLVED.
* A validation outcome never sets a requirement or gate status.

**Evidence candidates.**

* **EV-01. The P3 / S1a coupled bench** on the ground `hall_icp_neutralizer` article.
  * Measurements: module temperatures (P1-M-21, P3-P1-07); the calorimetric collector balance (P3-P1-09, A9.8 P3Q-01
    option C); and the ICP-43 thermocouple map with RF on / off and discharge-current steps.
  * Programme step: COUPLED-H1-ICP → P3-THERMAL.
  * No data yet. The facility sink is measured per run.
* **EV-02. The P1 ICP bench, discharge OFF.** It validates the thermal structure only. Ar loads are never transferred to air.
  No data yet.
* **EV-03. Published Hall thermal data.** All three are registered with sha256 in the H2-5 sources:
  * Myers et al. 2016 (NTRS 20170000961);
  * Mazouffre et al., IEPC-2005-063;
  * Martinez, Dao & Walker, JPP 30(1) 2014.

  They are candidates, and their applicability needs verification (V-10). They are xenon, hollow-cathode-equipped articles
  with different geometry.
  * They are usable only as bench replicas, with the cathode outside the replica boundary. The cathode then enters only
    through published boundary data, never as a node or a `Q_cath` term.
  * Otherwise they are `NOT_APPLICABLE`. No number is taken from them here.
* **EV-04. Published RF/ICP source thermal data.**
  * Takahashi et al. 2024 (registered) reports electrode heating and thermal repeatability issues but no temperatures, so it
    is not quantitative validation.
  * Further candidates are RF ion-thruster thermal correlations and ICP / helicon wall or antenna temperature measurements.
    They are still to be located and need verification (V-11): published sources only, no author contact.
* **EV-05. Flight data.** None.

**Calibration / validation separation.**

* **CVS-01.** Calibration parameters may come only from this list:
  * contact / assembly conductances;
  * as-built effective emittances;
  * interface partitions;
  * an owner-registered bounding fraction for unattributed power.

  The list is registered with the dataset split before any data are seen.
* **CVS-02.** The two sets are disjoint by run id. Each validation set holds at least one operating point not used in
  calibration on every varied axis.
* **CVS-03.** The datasets are sha256-frozen before scoring, and scoring runs once.
* **CVS-04.** There is no refit after scoring. A re-calibration needs a new version and new validation data. A failure stays
  recorded and is never rewritten.
* **CVS-05.** The P3Q-02 correlation-plan slots (P3-C-01..05) are registered before any data are evaluated.

**Comparison criteria.**

* **VC-01.** The comparison quantities are the registered sensor temperatures and calorimetric heat flows (P3-C-03).
* **VC-02.** The comparison error is E_q = S_q − D_q, and the validation uncertainty is u_val = √(u_num² + u_input² + u_D²)
  (ASME V&V 20-2009, verify V-07).
  * u_num comes from CONS-T2 and the steady tolerances.
  * u_input comes from the registered input uncertainties.
  * u_D comes from the sensor uncertainty incl. placement / contact (P3-C-02, P3-C-05).
* **VC-03.** A quantity is `CONSISTENT` if |E_q| ≤ 2 u_val (coverage factor 2, GUM, verify V-08), else `INCONSISTENT`.
* **VC-04.** The owner residual band (P3-C-04, TBD) must also hold. Until it is registered, the outcome is `NOT_EVALUATED`.
* **VC-05.** If two sensors on one node differ by more than 2 √(u_D1² + u_D2²), the node has an `UNREPRESENTED_GRADIENT`. A
  finer multi-node model, in a new version, is then required before any LOCK-1 thermal closure (A9.12 P3Q-02).
* **VC-06.** The dataset outcome is one of three:
  * `VALIDATED_WITHIN_TESTED_DOMAIN`, if every quantity is `CONSISTENT`, VC-04 holds and VC-05 raises no gradient;
  * `VALIDATION_INCONSISTENT`, if any quantity is inconsistent (permanent for that dataset);
  * `NOT_EVALUATED` otherwise.

## 19. Admission rule

* **ADM-01, `PREREG_MODEL`.** This record is committed alone and locked. The owner reviews it before any Rust code.
* **ADM-02, `RUST_IMPL`.** The code goes in `abep-subsystems::thermal`. `cargo test --workspace --locked` is green, and
  outputs are `NOT_VALIDATED`.
* **ADM-03, `VERIFIED`.** This requires AL-01..AL-11, every CONS check, FT-01..FT-18, DET and IV-01 / IV-02 (plus IV-03
  when it is performed) to meet their criteria.
  * The report is committed whatever the verdict.
  * A failure gives `NOT_ADMITTED`. Only a code fix plus a new prereg version may follow, with no retuning.
* **ADM-04, `ADMITTED`.** This needs a ledger flip, a HISTORY entry and a CI job bound to this prereg's sha256.
* **ADM-05.** Admission is software verification. It is not validation and not a gate PASS. No thermal result is ever
  reported as PASS.
* **ADM-06.** The retained kernels are admitted under their own parity contracts. This admission does not depend on them.

## 20. Uncertainty

* **U-01.** Every input carries an uncertainty and an evidence class.
* **U-02.** The model is deterministic. Propagation happens outside it, in SC-WP-10, by corner / interval sweeps and sampled
  UQ with the registered RNG. Each member is a full raw run, and envelopes are reported raw with no margin formed.
* **U-03.** Each admitted Hall member gets one run, as an unweighted scenario set. Today there is no member.
* **U-04.** TBD partitions are carried as registered bounds, never fitted silently.
* **U-05.** u_num is reported.
* **U-06.** Model-form uncertainty is not quantified before validation. Outputs stay `NOT_VALIDATED`.
* **U-07.** Bounding-corner admissibility (A9.12 OQ-A907-03) and the search allowance (OQ-A907-10) are assessment-layer
  rules.
* **U-08.** Optional raw sensitivities dT/dx come from the converged Jacobian. No margin is formed.

## 21. NOT_EVALUATED today

| id | item | status |
|---|---|---|
| NE-01 | absolute Hall heat loads (credible set EMPTY; no admitted map; no measured H-1 data) | `NOT_EVALUATED` |
| NE-02 | absolute RF/ICP heat loads (NP-ICP not admitted; no P1 / P2; ICP45 not evaluated; RF ratings TBD) | `NOT_EVALUATED` |
| NE-03 | geometry (H-1 frozen geometry; P3-G-01..08; ICP drawing) | `INCOMPLETE_EVIDENCE` |
| NE-04 | optical properties (P3-R-01..04) | `INCOMPLETE_EVIDENCE` |
| NE-05 | conductances (P3-K-01..06; H-1 internal links analog / assumed) | `INCOMPLETE_EVIDENCE` |
| NE-06 | anode and collector materials (OPEN) | `INCOMPLETE_EVIDENCE` |
| NE-07 | spacecraft thermal interface (no host ICD) | `NOT_EVALUATED` |
| NE-08 | flight environment view factors and attitude | `NOT_EVALUATED` |
| NE-09 | measured thermal validation; anode / coupled closure UNRESOLVED, never PASS | `NOT_EVALUATED` |
| NE-10 | interface partitions | `INCOMPLETE_EVIDENCE` |
| NE-11 | Hall quantities with no schema field (T_e at anode / wall, SEE yield, radiation loss, pole flux) | `NOT_EVALUATED` |
| NE-12 | `FLIGHT_CONDITIONAL` run status today | `NOT_EVALUATED` (all reasons listed) |

## 22. Items to verify

* **V-01.** Incropera & DeWitt: lumped capacitance and Bi < 0.1, shape factors, contact resistance, the two-surface formula.
* **V-02.** Modest, *Radiative Heat Transfer*.
* **V-03.** Siegel & Howell, *Thermal Radiation Heat Transfer*.
* **V-04.** Carslaw & Jaeger, the Kirchhoff transformation.
* **V-05.** Gilmore, *Spacecraft Thermal Control Handbook* Vol. I: the environment-flux formulation and two-band practice.
* **V-06.** Free-molecular heating ½ρV³α_E (Schaaf & Chambré, or Bird). There is no registered source in the repository.
* **V-07.** ASME V&V 20-2009.
* **V-08.** JCGM 100:2008, coverage factor 2.
* **V-09.** Applicability of NASA/TM-2001-211221 to 180–230 km (90-minute tables; reference surface R_E + 30 km).
* **V-10.** Applicability of the Myers, Mazouffre and Martinez data as bench replicas.
* **V-11.** Published RF/ICP thermal measurements beyond Takahashi 2024.
* **V-12.** Whether the pinned HallThruster.jl discharge power spans the neutralizer coupling, i.e. whether
  `Q_hall_return_to_icp_W` lies inside `discharge_power_W`.
* **V-13.** Uniqueness of the steady state. This is not used as a criterion.
* **V-14.** Goebel & Katz publisher details, already marked verify in `limits_v1.json`.
* **V-15.** Room-temperature and band emittances used at operating temperature.
* **V-16.** The gray-diffuse treatment of ceramic walls.
* **V-17.** The IR transparency of the plasmas.
* **V-18.** The spherical-enclosure view factor F_ij = A_j/A_total, used only for synthetic vectors.

Each of V-01..V-08 and V-18 is recalled from memory; none is in the repository.

## 23. Open owner questions (listed, not resolved)

* **OQ-NPT-01. Spacecraft interface without an ICD.** Can the owner mount cases (row 85; A9.12 OQ-A907-06; P3-M-05) act as
  registered `B_SC` cases for labelled flight runs, and in which form (SCI-A or SCI-B)? Or does the flight case stay
  `NOT_EVALUATED` until a host ICD exists?
* **OQ-NPT-02. IF-ICP-THERMAL-v1 alignment with NP-ICP-NEUTRALIZER.** The points are:
  * which slots `P_icp_bus_W` includes;
  * where the collector-bias power is carried;
  * that Hall-powered heat at the neutralizer (ICP-43 Q_coll) and plume interception stay out of the ICP keys (carried as
    HK-08 / HK-09);
  * whether the line loss is inside `Q_icp_match_W`;
  * who predicts `f_pw` / `f_rad`.
* **OQ-NPT-03. LOCK-1 model class.** Does the A9.12 P3Q-02 acceptance of "lumped H2-5 network + P3 radiosity enclosure",
  with its correlation plan and finer-model escalation, transfer to this model?
* **OQ-NPT-04. The 1.20 factor.** Confirm that it is applied by the assessment / case-construction layer, never in the
  equations.
* **OQ-NPT-05. Flight topology.** Dedicated Hall and ICP radiators, or ICP outward surfaces as radiators? Is the neutralizer
  mounted to the H-1 back plate, to the spacecraft, or both?
* **OQ-NPT-06. Published validation data.** May hollow-cathode-equipped xenon Hall thermal data be used as bench replicas
  with the cathode outside the boundary, or are they excluded?
* **OQ-NPT-07. Sink and environment basis.** Is `T_space` 0 K or the cosmic background? Is NASA/TM-2001-211221 the accepted
  environment source for 180–230 km?
* **OQ-NPT-08. Forbidden identifiers.** "heater" is forbidden as a load name in `crates/**`. Confirm the name
  `Q_thermal_control_W`, or narrow the scan to cathode-heater terms.
* **OQ-NPT-09. Unattributed Hall power.** Is a registered bounding deposition case needed for design studies, and onto which
  nodes?
* **OQ-NPT-10. Ram heating.** Is free-molecular ram heating on propulsion and radiator surfaces in scope for flight cases?

## 24. Conflicts and notes

* **CF-01, base.** The worktree started at `b1e5b76` (main), not at the stated base `e5528bd`. The new branch was pointed at
  `e5528bd` before any work, and no other branch was touched.
* **CF-02, plan state.** Plan v3 (`1236f91`) is not merged into `integration/simulation-complete`.
  * No v3.1 plan exists yet, and `docs/rust_migration/` does not exist at the base.
  * The plan references are pinned to the `1236f91` blobs.
  * A9.29 runs lane D in parallel.
  * The integration branch has since moved to `30afe1d` (CLAUDE.md CA-01..CA-04, no physics), with no content conflict.
* **CF-03, retained kernels.** The kernels listed in SC-WP-06 (K-P3-RAYS, `thermal_life`) are not ported here. They have
  their own contracts and feed this model only as registered inputs.
* **CF-04, interface gap.** IF-ICP-THERMAL-v1 has no key for:
  * Hall-powered collector heating (ICP-43 Q_coll);
  * plume interception (ICP-29);
  * the collector-bias supply;
  * reflected power.

  The first two are carried as HK-08 / HK-09 and the rest are booked at `B_PPU_RF`. If NP-ICP puts Q_coll inside
  `Q_icp_plasma_wall_W`, the heat is counted twice, which is `MODEL_ERROR` at integration (OQ-NPT-02).
* **CF-05, naming.** "heater" is a forbidden load name. Thermal-control power is legitimate and is named
  `Q_thermal_control_W` (OQ-NPT-08).
* **CF-06, model class.** The owner-accepted P3Q-02 model class is built on the H2-5 network, which has the C-1 node
  (OQ-NPT-03).
* **CF-07, Hall-map schema.** `hall_map_schema_v1` has no anode-heat, wall-T_e, SEE-yield, plasma-radiation or pole-heat
  field.
  * HK-03, HK-06, HK-07 and parts of HK-04 / HK-05 have no producer today.
  * A schema extension would be a bridge change owned by SC-WP-03, with the pin unchanged.
* **CF-08, ICD margin.** ICD ICP-37 states the ≥ 50 K margin as an ICD requirement. This is consistent with HC-06: the
  requirement is assessed on these raw temperatures.
* **CF-09, legacy records.** The legacy ledger and `thermal.py` carry a cathode node and the historical architectures, and
  neither is used. Node limits indexed in `hardware_bounds_v1.json` stay assessment inputs.

## 25. Change control

* **CC-01.** Any change after the lock is a new version (`prereg_v2.json`, a PREREG.md revision and a new lock) or a dated
  addendum. This file is never edited.
* **CC-02.** A change to interface keys or their meaning is a new interface version, recorded on both sides.
* **CC-03.** Tolerances, criteria and the calibration / validation split are never relaxed after results are seen.
* **CC-04.** A registered node subdivision is a discretization refinement, not a version change.
