# Common Hall accelerator reference (v1, DRAFT for owner review)

**What this is.** One downstream Hall accelerator, defined as an interface, that is identical in the three thrust
architectures `hall_only`, `rf_hall` and `ecr_hall`. The RF and ECR arms then differ from `hall_only` only in the
pre-ionization method upstream of the Hall inlet plane `HALL_INLET_Z0`. This describes Vyovrinda's own thruster, not P5.

**What this is not.** It contains no Hall performance prediction, no P5 or ECHT geometry or B(z) adopted as a design value,
no transport admission, and no architecture ranking, preference or elimination. The credible transport set is empty
(CLAUDE.md gate 3 FAIL), so every quantity that would need an admitted closure or hardware is **TBD**. Items that are not in
the RFP and not decided are marked **PROPOSED** for the owner.

| file | role |
|---|---|
| `docs/architecture_comparison/hall_reference/hall_reference_v1.json` | the reference (machine-readable, authoritative) |
| `schemas/architecture_comparison/hall_reference_v1.schema.json` | JSON Schema of the reference |
| `docs/architecture_comparison/hall_reference/voltage_envelope.py` | deterministic generator of the only computed numbers (ideal-beam table) |
| `tests/test_hall_reference.py` | schema validation, evidence discipline, contract consistency |

The reference is pure data. Nothing imports it, it is not wired into `abep_sim/archengine.py`, and goldens do not move.
Other lanes' contracts (bus-power boundary, comparison harness, thermal/life, evidence matrices, experiment protocol,
upstream ICD, Hall-map spec) are referenced by repository path only. Neither the reference nor its test needs them to exist.

Code baseline: `c53b75a`. It differs from `daa0e75` only in CLAUDE.md and docs/HISTORY.md text, so the code read for
this document is the same at both commits.

## 1. Milestones

| milestone | support | what this reference contributes |
|---|---|---|
| **Milestone A** (conditional selection) | YES | It fixes what is common to the arms. A conditional selection ("X is baseline provided A/B/C are demonstrated") can then be written entirely in terms of the inlet state at `HALL_INLET_Z0` and the arm-specific bus components. It needs no Hall performance number and not Physics Baseline 1.0. |
| **Milestone B** (physics-backed selection) | PARTIAL | It defines the fields, the trust semantics (`hall_map_schema_v1`) and the invariance checks that a physics-backed comparison must satisfy. It supplies no envelope. |
| **Milestone C** (proposal/PDR freeze) | PARTIAL | It provides the Hall-accelerator section of the interface control set. |

**Needed to go from A to B:**

- Owner approval (or change) of every PROPOSED item, including span rule VR-1 for the voltage range and the choice between
  its strict (180–305 V) and relaxed-(c) (180–350 V) readings (section 5).
- At least one admitted transport member. `transport_ensemble_v0.json` members is empty.
- A Vyovrinda geometry and B(z) design release.
- A solver capability for ion, electron and excited-state inflow at the anode plane (section 8; today it is a **GAP**).
- A chemistry set covering the injected species. N₂/N `abep-n2n-0.11` is scoped to P5-N₂ validation, and O/O₂ chemistry
  does not exist.
- Cathode values from the cathode lane.
- The wall-life settings and a cited sputter-yield model.
- Reconciliation of the inlet-state field names with the `interstage_v1` contract once it is merged. A provisional mapping,
  re-checked against commit `18d2bfb`, is recorded (section 8).

**Needed to go from B to C:**

- Hardware values for every TBD.
- A measured B(z) of the flight-like circuit.
- Cathode and wall life evidence against the > 15,000 h firing requirement.
- The start-up sequence in the bus ledger.
- Mass and power closure through `bus_power_boundary_v1`.

**C itself** means no TBD left, status `OWNER_APPROVED` and a version bump.

## 2. Conventions

- **Axial coordinate:** z runs from the anode face (z = 0) to the exit plane (z = L) and on to the end of the 1-D domain. In
  the 1-D model the cathode boundary sits at the domain end. This is the convention of `hallthruster_bridge/bridge_lib.jl`
  `run_case`.
- **Quantity statuses:** Every quantity object has one of four statuses:
  - **TBD:** the value is `null`, and `requires` starts with "TBD — requires".
  - **PROPOSED:** it carries a rationale, sources and an evidence class.
  - **SOURCED:** it carries sources, a locator (page, equation, table or file line) and an evidence class.
  - **OWNER_DECIDED:** it carries the decision record.
- **Numbers:** Every JSON number sits inside such a quantity (the test enforces this). Requirement values from the RFP carry
  the class `assumed`, with `abep_sim/constants.py` as their source. Verify them against the RFP text.
- **Evidence:** Evidence levels (1–7) and evidence classes follow docs/EVIDENCE.md. Open literature is pinned by URL and
  sha256 (section 13).

## 3. Geometry interface

All values are **TBD — requires a Vyovrinda thruster design release** (drawing id, revision, sha256).

| field | unit | maps to (bridge / HallThruster.jl) | status |
|---|---|---|---|
| `channel_mean_radius_m` R | m | `r_in_m = R − h/2`, `r_out_m = R + h/2` (Geometry1D) | TBD |
| `channel_width_m` h | m | `r_in_m`, `r_out_m` | TBD |
| `channel_length_m` L (anode face → exit plane) | m | `L_m` (Geometry1D channel_length) | TBD |
| `anode_axial_position` | m | z = 0 by definition | convention |
| `exit_plane_axial_position` | m | z = L by definition | convention |
| `domain_length_m` (1-D cathode boundary) | m | `domain_m` | TBD (needs the cathode position) |
| `anode_gas_distributor` | – | the plane `HALL_INLET_Z0` | TBD |
| `wall_material` | – | `WallSheath(material, loss_scale)`. The solver provides Alumina, BoronNitride, SiliconDioxide, BNSiO2 and SiliconCarbide (`src/physics/wall_losses.jl` lines 114–123). **Solver-supported, not wired in the bridge** (`SUPPORTED_NOT_WIRED`): `bridge_lib.jl` `run_case` never sets `wall_loss_model`, so every bridge run uses the solver default `WallSheath(BNSiO2, 1.0)` (`configuration.jl` line 218). Wiring needs a bridge change. | TBD |
| `magnetically_shielded` | – | `Thruster.shielded` (`thruster.jl` line 28, default false). **Solver-supported, not wired in the bridge** (`SUPPORTED_NOT_WIRED`): `run_case` builds `het.Thruster(name, geometry, magnetic_field)` without `shielded` (`bridge_lib.jl` line 224), so every bridge run is unshielded. | TBD. A shielded design has no wall fields under `hall_map_schema_v1`. |

**Sizing relations are evidence, not decisions.** They come from xenon literature. Transferring them to N₂/O/O₂ is a
hypothesis (evidence level 6 for the database correlations).

- **EV-G1:** A = π d h (Dannenmayer & Mazouffre 2008, Eq. 2.8, p. 7).
- **EV-G2:** Melikov–Morozov criterion λ_i ≪ L, with λ_i = v_n / (n_e⟨σ_i v_e⟩). The name and the criterion are from
  Dannenmayer & Mazouffre 2008, Eq. (2.1), p. 6; Goebel & Katz state the same condition without the name.
  - In the textbook example, 95 % ionization needs L ≈ 3 λ_i, so λ_i/L is below about 0.33 (Goebel & Katz 2008,
    Eqs. 7.2-14 to 7.2-17, pp. 334–335).
  - Propellants lighter than xenon need a longer ionization region (p. 336, Eq. 7.2-19).
- **EV-G3:** The channel depth is the magnetized plasma length plus a demagnetization length near the anode (Goebel & Katz
  p. 335).
- **EV-G4:** Across xenon thrusters, h ∝ d (Dannenmayer & Mazouffre 2011, p. 241). The coefficient is not given in DM2011
  (p. 242: "not given in this contribution as it is sensitive information").
- **EV-G5:** ṁ = n_n m_n v_n π d h, and a critical atom density of about 1.2 × 10¹⁹ m⁻³ applies to the xenon database, so
  h d ∝ ṁ.
  - Sources: Dannenmayer & Mazouffre 2008 Eq. 2.7 (p. 7) and p. 13; Dannenmayer & Mazouffre 2011 p. 241.
  - For ABEP, ṁ is the harvested flow at IF-A5, which is TBD.
- **EV-G6:** P = C_P h d. The xenon C_P is 1.1 × 10⁶ W m⁻² analytic and 1.2 × 10⁶ W m⁻² empirical (Dannenmayer & Mazouffre
  2008 Eq. 4.6, p. 14).
- **EV-G7:** In the SPT family, power, thrust, I_d and ṁ scale as R². The current density is typically 0.1–0.15 A cm⁻² for
  xenon (Goebel & Katz Eq. 7.2-20, pp. 336–337).
- **EV-G8:** The xenon SPT-50 has a 5 cm slot and delivers 20 mN at 350 W (Goebel & Katz Table 9-8, p. 441). Table 9-8 is
  a nominal performance summary with no stated measurement basis, so these values are classed inferred (reported), not
  measured. This is not transferable to air species.
- **EV-G9:** Flight Hall channels use BN or BN-SiO₂ (Goebel & Katz p. 325). The ECHT used BN and an extended channel for
  light neutrals (repository ECHT audit; Andreussi et al. 2022 p. 26).

**Forbidden as design-value sources:**

- the P5 case files (`cases/p5_xenon.json`, `p5_n2.json`, `p5_xenon_coil_sensitivity.json`)
- the ECHT case and audit geometry
- the superseded 0-D `HallChannel` defaults

## 4. B(z) interface

The bridge supports exactly two shape families, and Vyovrinda's field must use one of them:

| family | bridge function | case keys | limitation |
|---|---|---|---|
| `measured_or_computed_profile` | `measured_bfield` | `B_profile.{file, align, z_ref_in_file_mm, scale_to}`, `B_ref_T` | Rigid registration (shift only), scaled to B at the exit or its maximum. HallThruster.jl holds B constant beyond the ends of the data, so the profile must span [0, domain]. |
| `asymmetric_gaussian_exit_peaked` | `bfield_gaussian` | `B_max_T`, `B_sigma_in_m`, `B_sigma_out_m`, `L_m`, `domain_m` | The peak is fixed at z = L. It cannot represent plateau or upstream-peaked fields. |

**Fields:**

- These are all **TBD — requires the Vyovrinda magnetic-circuit computation or measurement**:
  - `shape_family`, `profile_file`, `profile_sha256` and `field_origin`
  - `B_max_T`, `peak_position_rel_exit_m` and `B_anode_over_B_max`
  - `registration_align`, `registration_z_ref_in_file_mm`, `scale_to` and `B_ref_T`
  - the Gaussian widths (only if that family is chosen)
  - `magnet_setting_schedule` (coil currents or B_ref versus V_d; it sets the `hall_magnet` bus load)
- `solver_magnetic_field_scale` = 1.0 (solver default, `configuration.jl` line 228). Amplitude changes go through
  `B_ref_T`, the path validation used.

**Design evidence (not decisions):**

- **EV-B1:** The radial field peaks near the exit and is essentially zero at the anode (Goebel & Katz pp. 329, 331).
- **EV-B2:** r_Le ≪ L ≪ r_Li (Goebel & Katz Eqs. 7.2-1 to 7.2-3, pp. 330–331; Dannenmayer & Mazouffre 2008 Eq. 2.11).
  - r_i ∝ √M, so the ion-Larmor margin is smaller for N⁺/O⁺/N₂⁺ than for Xe⁺.
  - The textbook examples are 0.13 cm (electrons, 25 eV, 150 G) and about 180 cm (xenon ions, 300 eV, 150 G).
- **EV-B3:** B ∝ 1/(h d). B ∝ ṁ/(h d) and B ∝ 1/L, or √U_d·ṁ/(h d) and √U_d/L with the low-assumption set (Dannenmayer &
  Mazouffre 2008 Eq. 2.15; 2011 Eqs. 44–45, p. 242).
- **EV-B4:** The xenon database operates at typically about 200 G (Dannenmayer & Mazouffre 2011 p. 242).
- **EV-B5:**
  - A field decreasing toward the anode gives higher efficiency (Goebel & Katz p. 335).
  - The optimal field has been found proportional to V_d (Hofer, cited by Goebel & Katz p. 333).
  - The exit field-line curvature (ion lens, p. 329) is outside a 1-D centreline model.
- **EV-B6:** The measured ECHT field is a flat plateau, not exit-peaked (repository ECHT audit). This is why the interface
  must accept an arbitrary profile.

**Forbidden as design-value sources:**

- `hallthruster_bridge/bfield/p5_vacuum_Br_centerline_1p6kW.csv` and `..._3p0kW.csv`
- the ECHT digitized field
- the P5 `B_ref_T` values
- the 0-D `HallChannel.B_max_T`

Calibration-nuisance keys (`p5_registration`, `p5_coil_shape`) are never Vyovrinda field variables.

## 5. Discharge-voltage interface

**Supply.** The discharge supply runs between the anode and cathode common. The thruster floats, and the beam voltage is
V_d minus the coupling voltage (Goebel & Katz Eqs. 7.2-21 and 7.2-22, pp. 337–339). In the solver this maps to
`Config.discharge_voltage` (bridge `Vd`) and `Config.cathode_coupling_voltage`.

**PROPOSED range: 180–305 V. PROPOSED evaluation set: 180, 200, 250, 300, 305 V.** The same set is used in every arm
(INV-V1). The set includes both range ends, so no comparison point needs extrapolation. The interior nodes are the multiples
of 50 V strictly inside the range, a design-of-experiment choice (assumed). This puts 300 V and 305 V only 5 V apart; the
owner may drop the 300 V node (Q1).

**Rationale and span rule VR-1.** The range is the span of the discharge voltages at which, in the open sources
consulted, an air-species Hall-channel device had a thrust that the source **states was measured**. The explicit rule (`span_rule` in the
JSON) counts an operating point only if all three criteria hold:

- **(a)** the device is an annular Hall-channel thruster (single- or two-stage);
- **(b)** the anode propellant is an air species or air simulant with no xenon admixture;
- **(c)** the source states that the thrust at that voltage was measured ("thrust was measured", a thrust stand or
  balance). An efficiency or other thrust-derived figure whose thrust basis is not stated does not qualify: ER-1 holds just
  as well for an estimated thrust, as the Dukhopelnikov et al. entry shows.

Points that fail a criterion stay in the table with the reason; none are dropped.

**Provenance of VR-1 (stated at repair, not pre-declared).** The first draft described the range as "the span of voltages at
which published Hall-channel devices were operated on air species". An adversarial review found that this left out the
Dukhopelnikov et al. sweep (air and 2:1 N₂/O₂ from "less than 100 V up to 350 V", Andreussi et al. 2022 p. 26), even
though the draft cited the same passage as EV-V1. It also found that the cusped-field MCFT-2139 was not recorded. VR-1 was
written down during the first repair. That version of criterion (c) also accepted "an anodic efficiency (which needs a
measured thrust)", and so kept the Busek BHT 350 V point as the upper end.

A second review found that premise false. An anodic efficiency can rest on an estimated thrust: the same review derives the
Dukhopelnikov et al. performance from a thrust "estimated assuming a fixed voltage utilization efficiency of 0.75" (p. 26).
For the BHT, the review reports only the 350 V, 2.94 mg/s point "with the anodic efficiency reaching about 27%" (p. 25). It
never states how the thrust was obtained, and the primary Busek report (Hruby, Hohman & Szabo, IEPC-2022-446, ref. [44] of the review) was
not accessed (no open copy found at the attempted URLs; verify). The BHT thrust basis is therefore **not stated**, and a
measured thrust would be an inference. The second repair applied (c) strictly. **The upper end moved from 350 V to 305 V**
(PPS1350-TSD, measured thrust 19–21 mN).

Spans on record for the owner (Q1):

| span | rule | range (V) |
|---|---|---|
| **proposed** | VR-1, strict (c) | **180–305** |
| alternative | VR-1 with (c) relaxed to accept an efficiency with unstated thrust basis (adds BHT); also follows if the primary Busek report shows a measured thrust at 350 V | 180–350 |
| unfiltered | criteria (a) and (b) only, any thrust basis | "<100"–350 |

| device | family | gas | reported V_d (V) | VR-1 span voltages (V) | thrust basis | role | source (evidence level) |
|---|---|---|---|---|---|---|---|
| ECHT (extended channel) | Hall channel | N₂ (Ar cathode) | 180–220 | 180–220 | measured (20–23 mN in the review; reduction ambiguity, see note) | **span-defining** | Andreussi et al. 2022 p. 26; repository ECHT audit (Marchioni thesis Table 6.1) (3) |
| P5 | Hall channel | N₂ (Xe cathode) | 231.9–278.6 | 231.9–278.6 | measured (`T_corr_mN`, N1–N5) | **span-defining** | `cases/p5_n2.json` (Brabston 2025 Table 2, Fig. 5) (3) |
| PPS1350-TSD | Hall channel | pure N₂ | 240–350 | 305 | measured at 305 V only (19–21 mN) | **span-defining** | Andreussi et al. 2022 p. 23 (5) |
| SITAEL HT5k (shielded) | Hall channel | 0.56 N₂ / 0.44 O₂ | 225–300 | 225–300 | measured (30–120 mN) | **span-defining** | Andreussi et al. 2022 p. 25 (5) |
| Busek BHT (2 kW nominal) | Hall channel | air simulant | 200–350 | — | **not stated** (anodic efficiency ≈ 27 % at 350 V reported; thrust basis inferred at most) | recorded, excluded (fails c, strict) | Andreussi et al. 2022 p. 25 (5); primary IEPC-2022-446 not accessed |
| helicon Hall thruster | Hall channel (two-stage) | N₂ | 200 | 200 | thrust stand | **span-defining** | Andreussi et al. 2022 p. 27 (5); its RF-stage evidence belongs to `docs/evidence/rf_source/` |
| Z-70 | Hall channel | N₂/Xe, air/Xe mixtures | 270 and 290 | — | not reported (plume composition) | context only: xenon admixture, no thrust (fails b, c) | Andreussi et al. 2022 p. 26 (5) |
| 38 mm Hall thruster (Dukhopelnikov et al.) | Hall channel | air; 2:1 N₂/O₂ | "<100"–350 | — | **estimated** (assumed η_v = 0.75) | recorded, excluded (fails c) | Andreussi et al. 2022 pp. 26–27 (5) |
| MCFT-2139 | **cusped field** | N₂ | 30–2000 | — | measured (13.3 mN at 997 W, 1000 V) | recorded, excluded (fails a) | Andreussi et al. 2022 p. 27 (5) |
| SPT family (xenon context) | Hall channel | Xe | 200–500 | — | — | context only: xenon (fails b) | Goebel & Katz p. 440 (5) |

Notes on the span-defining points and the exclusions:

- **ECHT.** The review quotes 20–23 mN. The repository ECHT audit (Marchioni thesis Tables 6.2/6.3) gives 20.6–23.4 mN with
  the one-side thrust reduction for 7 runs. Four runs also have an averaged reduction that is 6–18 % lower, down to
  17.29 mN (Run 5). Runs 1, 3 and 7 are flagged strongly unstable. The 180 V end rests on Run 2 (180 V, not flagged
  unstable): 22.76 mN one-side and 21.31 mN averaged (`echt_table_checks_v1.json`). Either reading is a measured thrust,
  so criterion (c) holds. The ambiguity affects the thrust value, not the voltage.
- **Busek BHT.** See the provenance paragraph above. Its 200–350 V tested range stays in the unfiltered span.
- **Dukhopelnikov et al.** The review states that "the thrust value was estimated assuming a fixed voltage utilization
  efficiency of 0.75". Its quantitative light/xenon ratios are reported "in the 200 V to 350 V voltage range" (p. 27),
  which overlaps the proposed range and extends above its 305 V end. With light propellants its I_d(V_d) plateau sits 50–100 V above xenon's (EV-V1), so
  the sub-200 V part of the sweep includes pre-plateau operation. That supports the lower end but does not define it.
- **MCFT-2139.** A cusped-field thruster is a different device family from the annular Hall channel defined here (lane
  brief; CLAUDE.md rule 8). It was considered because 13.3 mN at 997 W discharge power (1000 V, N₂) is inside the RFP
  12–25 mN band and under the 1.5 kW ceiling (discharge power only). It is not the only such light-propellant point in the
  review: PPS1350-TSD on N₂ at 305 V gave 19–21 mN at about 1 kW (p. 23). Whether Vyovrinda's channel should also be
  evaluated above the proposed 305 V end is part of Q1.

The envelope relations show why no single voltage can be chosen today:

- **ER-1:** η_a = T²/(2 ṁ_a P_d), so P_d = T v_eff/(2 η_a) with v_eff = T/ṁ_a (Goebel & Katz Eq. 7.3-16, p. 344).
- **ER-2:** v_eff = γ η_m √(2 e η_v V_d / M) for one singly charged species. This is our algebra from Goebel & Katz Eqs.
  7.3-9, 7.3-11, 7.3-13 and 7.3-14.
- **ER-3:** P_in = P_d + P_k + P_mag (Eq. 7.3-6). In `bus_power_boundary_v1` these are `hall_discharge`, `cathode_keeper`
  and `hall_magnet`, plus `cathode_heater` at start-up, and `rf_source` or `ecr_source` + `ecr_magnet` in their arms. The
  RFP ceiling (< 1.5 kW; `abep_sim/constants.py` `power_max_W`) applies to the bus total as the bus-boundary lane accounts it.
- **ER-4:** At fixed thrust and fixed γ, η_m, η_v and η_a, P_d ∝ √V_d. The power ceiling therefore favours the low end.
- **ER-5:** At fixed thrust, harvested flow and fixed efficiencies, the required voltage is V_d = (M/(2 e η_v))·(T/(γ η_m ṁ_a))²
  (an equality). For a beam of **singly charged** ions (γ ≤ 1 then covers divergence only; η_m, η_v ≤ 1), the floor is
  V_d ≥ (M/2e)·(T/ṁ_a)², independent of the efficiencies. The intake flow (IF-A5, TBD) therefore sets a floor. The floor
  holds only for a singly charged beam: with multiply charged ions T/ṁ_i can exceed √(2 e V_b/M), by up to √2 for a fully
  doubly charged beam, so the floor can be undercut by up to a factor 2 in V_d.
- **ER-6:** Published light-propellant data show efficiency rising with voltage, which opposes ER-4:
  - The I_d(V_d) plateau sits 50–100 V higher than with xenon (EV-V1, p. 26).
  - The best air-simulant anodic efficiency, about 27 %, came at the highest tested 350 V (EV-V2, p. 25; thrust basis not
    stated in the review, so this is evidence of a trend, not a span-defining point).

  The optimum therefore depends on the closure and the hardware (TBD), and the proposal is the filtered evidence span
  (VR-1, strict), not an optimum.

The superseded 0-D grid in `abep_sim/archengine.py` `_variables` (225–325 V) is **not** reused.

**Ideal-beam reference table.** These values are computed by `voltage_envelope.py` from `abep_sim/constants.py` and the
RFP requirements recorded in the JSON (12–25 mN, 1500 W). The JSON is authoritative, and the test recomputes the table.

- The table uses physics identities for a singly charged, monoenergetic, collimated beam accelerated through the full V_d:
  v_b = √(2 e V_d / m) and T/P_jet = 2/v_b.
- It is **not** a thruster prediction, **not** a bound on P_d, and not an input to any trade.
- P_jet here is the ideal-beam jet power. **An anodic efficiency must never be applied to it.** By ER-1 and ER-2,
  P_d = T v_eff/(2 η_a) with v_eff = γ η_m √η_v v_b, so P_jet/P_d = η* = η_a/(γ η_m √η_v), not η_a. Dividing P_jet by η_a
  overstates P_d by 1/(γ η_m √η_v).
- It only shows how the jet-power cost of thrust scales with V_d and ion mass, and how much of the RFP power ceiling an
  ideal beam alone would take.

T/P_jet of the ideal beam, in mN/kW:

| ion | 180 V | 200 V | 250 V | 300 V | 305 V |
|---|---|---|---|---|---|
| N2+ | 56.784 | 53.87 | 48.183 | 43.985 | 43.623 |
| N+ | 40.152 | 38.092 | 34.07 | 31.102 | 30.846 |
| O2+ | 60.705 | 57.59 | 51.51 | 47.022 | 46.635 |
| O+ | 42.925 | 40.722 | 36.423 | 33.249 | 32.976 |
| Xe+ | 122.965 | 116.655 | 104.339 | 95.248 | 94.464 |

The v_b values are in the JSON. For example, N₂⁺ reaches 45470.2 m/s at 300 V.

Ideal-beam jet power P_jet = T v_b / 2 at the upper RFP thrust end, 25 mN, in kW. The share of the 1.5 kW ceiling is in
parentheses:

| ion | 180 V | 200 V | 250 V | 300 V | 305 V |
|---|---|---|---|---|---|
| N2+ | 0.44 (29.4 %) | 0.464 (30.9 %) | 0.519 (34.6 %) | 0.568 (37.9 %) | 0.573 (38.2 %) |
| N+ | 0.623 (41.5 %) | 0.656 (43.8 %) | 0.734 (48.9 %) | 0.804 (53.6 %) | 0.81 (54.0 %) |
| O2+ | 0.412 (27.5 %) | 0.434 (28.9 %) | 0.485 (32.4 %) | 0.532 (35.4 %) | 0.536 (35.7 %) |
| O+ | 0.582 (38.8 %) | 0.614 (40.9 %) | 0.686 (45.8 %) | 0.752 (50.1 %) | 0.758 (50.5 %) |
| Xe+ | 0.203 (13.6 %) | 0.214 (14.3 %) | 0.24 (16.0 %) | 0.262 (17.5 %) | 0.265 (17.6 %) |

**Envelope tie (no performance prediction).** The tie to the power ceiling uses **measured** light-propellant (thrust,
discharge power) pairs of published devices, not an efficiency applied to the ideal beam. The points are in
`measured_discharge_power_check` in the JSON. They are the air-species Hall-channel points whose thrust is in or just below the
RFP band and whose V_d and I_d are both published. `voltage_envelope.py` computes P_d = V_d I_d, T/P_d, the share of the ceiling
and η* (N₂⁺ reference):

| point | V_d (V) | I_d (A) | thrust (mN) | P_d (W) | T/P_d (mN/kW) | P_d / 1.5 kW | η* (N₂⁺ ref.) |
|---|---|---|---|---|---|---|---|
| ECHT-Run2 | 180 | 3.0 | 21.31–22.76 | 540.0 | 39.46–42.15 | 36.0 % | 0.695–0.742 |
| ECHT-Run4 | 200 | 3.5 | 20.05–22.79 | 700.0 | 28.64–32.56 | 46.7 % | 0.532–0.604 |
| ECHT-Run5 | 200 | 2.7 | 17.29–20.85 | 540.0 | 32.02–38.61 | 36.0 % | 0.594–0.717 |
| ECHT-Run6 | 200 | 2.7 | 18.22–22.32 | 540.0 | 33.74–41.33 | 36.0 % | 0.626–0.767 |
| PPS1350-TSD-N2-305V | 305 | 3 | 19–21 | 915.0 | 20.77–22.95 | 61.0 % | 0.476–0.526 |

Sources: ECHT Runs 2, 4, 5 and 6 from the repository ECHT audit (`echt_table_checks_v1.json`, Marchioni Tables 6.1–6.3).
These are the runs with both thrust reductions (averaged–one-side) that are not flagged strongly unstable. I_d has 2
significant figures and may not be simultaneous with the thrust reading (audit assumption A11). PPS1350-TSD from Andreussi
et al. 2022 p. 23 ("A 305 V and 3 A pure nitrogen operating point", "measured thrust between 19 and 21 mN", "neighboring 1kW
of discharge power"). The 3 A is read as the discharge current (verify against the primary source). P5 N1–N5 (61–90 mN) and
the HT5k (30–120 mN at 1.2–5.2 kW) are outside the band and are not used.

These published points gave 17.29–22.79 mN, just below the 25 mN upper end, at a discharge power of 0.54–0.915 kW. That is
36.0–61.0 % of the 1.5 kW ceiling for the discharge alone, before cathode, magnet, pre-ionizer and other bus loads. Their
thrust per discharge power is 20.77–42.15 mN/kW.

The η* column shows why the anodic efficiency must not be applied to the ideal-beam jet power. For ECHT Run 2, η* is
0.695–0.742, while its reconstructed anodic efficiency is 0.23 (`echt_table_checks_v1.json`). The published light-propellant
anodic efficiencies (8–18 % for the HT5k, about 27 % for the BHT with thrust basis not stated (EV-V2), 13–23 % for the ECHT;
Andreussi et al. 2022 pp. 25–26) are therefore **not** P_jet/P_d ratios. η* depends on the beam composition, which is not
published: an N⁺ reference gives larger values.

The ideal-beam table gives the scaling. Across the air-species ions (N₂⁺, N⁺, O₂⁺, O⁺) and the proposed range, an ideal
beam alone at 25 mN needs 0.412 kW (O₂⁺, 180 V) to 0.81 kW (N⁺, 305 V). That is 27.5–54.0 % of the 1.5 kW ceiling, and it
rises as √V_d and as 1/√M. At fixed η*, P_d scales the same way. The ceiling therefore constrains the high-V_d, light-ion
corner most. This is the quantitative form of ER-4, and it is why the power ceiling favours the low end while ER-5 and ER-6
push the other way. The lower RFP thrust end (12 mN) is in the JSON (`jet_power_at_thrust_min_kW`).

## 6. Cathode interface

**PROPOSED (owner confirms):**

- A **hollow cathode** (Goebel & Katz pp. 327–328).
- A **LaB6** emitter:
  - The lane brief calls for Xe-fed LaB6 per the RFP context "air + Xe" (verify against the RFP text).
  - The repository's 0-D model is `LaB6Cathode` in `abep_sim/plasma_devices.py` (superseded 0-D context).
  - LaB6 tolerates feed impurities and air exposure better than BaO dispenser cathodes (Goebel & Katz p. 255).
- A **Xe** feed (IF-X2 `mdot_xe_cathode_kgps`), proposed from the RFP context "air + Xe". Most published light-propellant
  Hall tests fed the cathode with xenon: PPS1350-TSD (p. 23), Z-70 and Dukhopelnikov et al. (p. 26), MCFT-2139 and HHT
  (p. 27) of Andreussi et al. 2022. But not all did: the shielded HT5k moved its HC20 cathode from xenon to pure N₂ (p. 25),
  and the ECHT used an argon-fed cathode (p. 26) (EV-C6).

**TBD, requiring the cathode lane (`docs/evidence/cathode/`):**

- `cathode_mass_flow_kgps`. It never crosses `HALL_INLET_Z0`.
- `electron_emission_current_A`. It is ≈ I_d (Goebel & Katz Eq. 7.2-25) and comes from a map of an admitted member or from
  hardware.
- `max_emission_current_A`.
- `keeper_current_A`, `keeper_voltage_V` and `keeper_operating_mode`. Textbook practice is start-up only (EV-C2, p. 337).
- `heater_power_W` and `heater_preheat_time_s`.
- `coupling_voltage_V`. Xenon practice is about 20 V, or 5–10 % of V_d (EV-C3, p. 339). The solver currently runs with
  its default 0.0 V. That is a **placeholder solver setting, not a design value**; the TBD hardware value (or an
  owner-decided setting) replaces it, identically in all arms (INV-C2).
- `cathode_position`. It maps to the 1-D domain end.

The firing requirement is > 15,000 h (`abep_sim/constants.py` `ignition_hours`, requirement). The bus components are
`cathode_keeper` and `cathode_heater`.

The cathode-integration lane's data file (`docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json`)
was read on 2026-09-26 as uncommitted work in progress. At repair time it is still in no commit, so this cross-check **cannot
be reproduced from any commit**. Its baseline ("Xe-fed LaB6 hollow cathode") and its bus components agree with the
PROPOSED fields here. No value is taken from it.

## 7. Wall/life interface

Names and semantics come from `hallthruster_bridge/hall_map_schema_v1.json` and `abep_sim/hall_map.py`. None are
redefined here.

- **Fields:**
  - `wall_ion_flux_m2s` and `wall_ion_energy_eV`
  - `wall_life_trustworthy`
  - the inputs to those trust flags: `converged`, `sustained` and `chemistry_trustworthy`
- **Meta:** `ion_wall_losses`, `ensemble_member_id` and `facility_ingestion`. The bridge raw record also carries
  `wall_ion_basis`.
- **wall_life_trustworthy (node level):** converged ∧ sustained ∧ ion_wall_losses=true ∧ WallSheath ∧ unshielded ∧ both wall
  fields present.
- **wall_life_trustworthy (query level, `HallMap.__call__`):** all of the following:
  - the query is performance-trustworthy
  - `meta.ion_wall_losses is True`
  - every surrounding node is wall_life_trustworthy

  `map_ready` means schema-complete only.
- **Design inputs:** The wall material is TBD. `ion_wall_losses_setting` is TBD (owner decision per Hall-map spec section 7;
  the solver default is false). The sputter-yield model and the erosion allowance are TBD (wall-life lane,
  `abep_sim/thermal_life.py`). The firing requirement is > 15,000 h. `wall_loss_scale` = 1.0 is the software default.
- **Rule:** The wall flux is erosion-grade only where wall_life_trustworthy holds. Otherwise the life item is reported
  unavailable and never filled with a default.

**Evidence:**

- **EV-W1:** Hall life is usually of order 10,000 h with xenon. Wall sputtering near the exit sets life (Goebel & Katz
  pp. 325, 327, 336).
- **EV-W2:** A PPS1350 on N₂/O₂ with 10 % Xe at 305 V ran steadily for about 314 h. Anode oxidation then caused flame-outs.
  The authors judged the ceramic erosion compatible with 7000–9500 h (Andreussi et al. 2022 p. 24).

## 8. Pre-ionizer injection interface (`HALL_INLET_Z0`)

**Plane.** `HALL_INLET_Z0` is the anode/gas-distributor plane at z = 0.

- The pre-ionizer volume is upstream of it and outside this reference.
- The cathode flow never crosses it.

**What enters the plane in each arm:**

| arm | what enters `HALL_INLET_Z0` |
|---|---|
| `hall_only` | The delivered neutral anode feed (IF-A5 `mdot_anode_s_kgps`, IF-X2 `mdot_xe_anode_kgps`) at the gas-distributor state. Every ion and electron field is **exactly zero**. |
| `rf_hall` | The RF pre-ionizer output (interstage lane); bus component `rf_source`. |
| `ecr_hall` | The ECR pre-ionizer output (interstage lane); bus components `ecr_source` and `ecr_magnet`. Its field inside the Hall channel is constrained by INV-B3. |

**Representation (PROPOSED): `moments_v1`.** It is a set of drifting-Maxwellian moments. This is what a fluid inflow
condition of the 1-D solver would need. An optional tabulated axial velocity distribution may accompany any ion entry.

**Fields (the Hall-side requirement)** and their support in the pinned solver:

| field | indexing | pinned-solver support |
|---|---|---|
| `mdot_neutral_kgps` | per neutral species | PARTIALLY_WIRED: `Propellant.flow_rate_kg_s`. The bridge wires one propellant per case. |
| `T_neutral_K` | per neutral species | SUPPORTED_NOT_WIRED: `Propellant.temperature_K` |
| `u_neutral_axial_m_s` | per neutral species | SUPPORTED_NOT_WIRED: `Propellant.velocity_m_s` |
| `neutral_internal_state` | per neutral species | NOT_SUPPORTED: anode flow feeds the ground state only, and excited states have no anode inflow |
| `ion_current_A` | per ion species and charge | NOT_SUPPORTED |
| `u_ion_axial_m_s` | per ion species and charge | NOT_SUPPORTED |
| `T_ion_axial_eV` | per ion species and charge | NOT_SUPPORTED. `ion_temperature_K` is an isothermal-ion parameter of the anode Bohm condition, not an inflow temperature. |
| `ion_velocity_distribution_ref` | per ion species and charge | NOT_SUPPORTED |
| `electron_current_A` | per record | NOT_SUPPORTED: no anode-plane electron injection in `Config` |
| `T_e_inlet_eV` | per record | NOT_SUPPORTED |
| `plasma_potential_rel_anode_V` | per record | NOT_SUPPORTED. Ions arriving below anode potential meet a retarding potential. |
| `annular_nonuniformity` | per record | NOT_APPLICABLE in 1-D. It is required for hardware comparisons. |
| `injected_flux_oscillation` | per record | NOT_SUPPORTED: the feed is constant in time |
| `element_mass_flow_kgps` | per record | bookkeeping for CR-1 |

**Conservation rules:**

- **CR-1:** Element mass through the plane = the delivered anode flow minus reported losses. It must close exactly
  (CLAUDE.md rule 4).
- **CR-2:** Injected charge appears in the circuit accounting.
- **CR-3:** The energy invested in ionization, dissociation, excitation and heating is paid by `rf_source`/`ecr_source`
  power, and the ledger residual stays < 2 %.
- **CR-4:** The cathode flow never crosses the plane.
- **CR-5:** In `hall_only`, the inlet state equals the delivered neutral feed.

**Solver capability: GAP.** These findings come from the pinned HallThruster.jl v0.23.1 source, read but not executed:

- **SC-1:** At the anode, positive ions leave at the sheath-corrected Bohm speed, and their flux is returned as ground-state
  neutrals. There is no ion inflow (`heavy_species_update.jl` `apply_left_boundary!`, lines 303–429, line 395).
- **SC-2:** The anode feeds the ground state only, and excited states have no anode inflow (lines 337 and 422).
- **SC-3:** The neutral velocity and temperature exist in `Propellant`, but the bridge does not pass them.
- **SC-4:** The only user hook is `Config.source_heavy_species` (`configuration.jl` lines 200 and 240;
  `heavy_species_update.jl` line 149). Using it, or changing the boundary, is a **model change**.
- **SC-5:** The bridge runs one propellant per case, so a mixed air + Xe anode feed is not representable.

**Consequence.** `rf_hall` and `ecr_hall` cannot be evaluated through the pinned Hall model today. Their maps must be
refused, not run with the pre-ionization dropped (Hall-map spec section 12). Closing the gap is an owner-approved model
change with its own validation plan:

- It is applied to all arms.
- With zero injection it must reproduce `hall_only` (INV-S1).
- The pin is never moved automatically.

**Reconciliation with the interstage lane: PENDING.** The first draft read the interstage lane's model
`abep_sim/interstage.py` (`interstage_v1`) as uncommitted work in progress. The lane has since committed it as `18d2bfb`
on branch `worktree-wf_15f0f2f8-8d4-2`, together with `schemas/architecture_comparison/interstage_v1.schema.json`. That
commit is not merged into this branch. The mapped names below were re-checked against `18d2bfb`, so the mapping can be
reproduced from that commit only until it is merged. The provisional mapping is recorded field by field in
`interstage_field`:

| Hall field | interstage_v1 (commit `18d2bfb`, not merged) |
|---|---|
| `mdot_neutral_kgps` | `result.neutrals[s].to_hall_flow_s` × species mass |
| `ion_current_A` | `result.ions[i].delivered_to_hall_flow_s` × charge × e; fractions in `result.charge_state_fractions.delivered` |
| `u_ion_axial_m_s` | `result.ions[i].axial_speed_m_s` (constant along the duct, their assumption) |
| `T_neutral_K` | `SourceExitState.neutral_temperature` (a source-exit value, carried to the inlet by the isothermal-wall assumption) |
| `T_e_inlet_eV` | `SourceExitState.electron_temperature`: a **source-exit** value, not an inlet-plane value. The interstage model holds it constant along the duct (isothermal-electron closure, an interstage assumption); it does not compute T_e at `HALL_INLET_Z0` |
| `element_mass_flow_kgps` | derivable from the delivered flows; their element residuals are gated |

Not yet provided (TBD, to be covered by the interstage lane):

- `u_neutral_axial_m_s`
- `neutral_internal_state`
- `T_ion_axial_eV`
- `ion_velocity_distribution_ref`
- `electron_current_A`
- `plasma_potential_rel_anode_V`
- `annular_nonuniformity`
- `injected_flux_oscillation`

The interstage model refuses `hall_only`, which is consistent with the neutral-only `hall_only` rule here. The committed
interstage contract must provide every field, under the same name or through an explicit mapping table, or declare it
TBD. Hall-side names are not renamed silently.

## 9. Invariance rules (what may never differ between arms)

All rules are PROPOSED.

| id | category | rule |
|---|---|---|
| INV-G1 | geometry | Mean radius, width, length, anode origin, exit plane and domain length are identical. |
| INV-G2 | geometry | Wall material, wall model and loss scale, shielding and `ion_wall_losses` are identical. |
| INV-G3 | geometry | The anode/gas-distributor hardware at `HALL_INLET_Z0` is identical. The pre-ionizer attaches upstream. |
| INV-B1 | bfield | The Hall-channel B(z) is identical: family, file and sha256, origin, registration, B_ref, B_max, peak position, anode ratio, Gaussian widths and solver scale 1.0. |
| INV-B2 | bfield | The magnet-setting schedule is identical. Per-arm re-optimization is only a separately pre-registered sensitivity branch. |
| INV-B3 | bfield | In `ecr_hall`, the combined field in the channel (including any `ecr_magnet` fringe) equals the reference B(z) within an owner tolerance. Otherwise the arm is not comparable. |
| INV-V1 | discharge_voltage | The voltage range and evaluation set are identical, and compared points share V_d. |
| INV-V2 | discharge_voltage | The supply topology (anode to cathode common, floating) and its `hall_discharge` accounting are identical. |
| INV-C1 | cathode | Type, emitter, gas, flow, position, keeper mode and current, heater protocol and coupling treatment are identical. |
| INV-C2 | cathode | The solver boundary settings are identical: cathode coupling voltage 0.0 V default, cathode T_e 2.0 eV default, anode condition `:sheath` (`configuration.jl` lines 213–215). The 0.0 V coupling voltage is a placeholder solver setting, not a design value; the TBD cathode value (about 20 V in xenon practice, EV-C3) or an owner-decided setting replaces it, identically in every arm. |
| INV-T1 | transport | The same admitted member is used, with no retuning. Screening candidates are never used. |
| INV-T2 | chemistry | The same reaction-set label and variant are used, and f_out = 0 is never relaxed. A pre-ionizer species outside the set blocks the arm. |
| INV-N1 | numerics | The numerics are identical (admission numerics, Hall-map spec section 11). |
| INV-S1 | solver | The same pinned solver is used. Any injection extension goes to all arms and reproduces `hall_only` at zero injection. |
| INV-F1 | feed | The IF-A5 / IF-X2 feed is identical per compared point, and CR-1 to CR-5 close. |
| INV-P1 | bus | The same `bus_power_boundary_v1` and common components are used. Only `rf_source`, `ecr_source` and `ecr_magnet` differ. |
| INV-O1 | observables | The same `hall_map_schema_v1` fields and trust rules apply. No arm gets relaxed trust. |
| INV-U1 | nuisance | Calibration nuisance (P5 registration, coil shape, beam reading, facility interpretation) is never an arm setting. |
| INV-L1 | facility | Design runs are flight runs (`facility_ingestion = false`). Ground tests share the facility state. |

**Allowed differences:**

1. The inlet state at `HALL_INLET_Z0`.
2. The pre-ionizer hardware upstream and its bus components (subject to INV-B3).
3. Outputs, which are results and not settings.

The test checks that every geometry, B(z), voltage and cathode field is covered by a rule of the matching category.

## 10. Transport, chemistry, numerics

- **Transport member:** TBD. It requires an admitted member (`hall_ensemble.require_admitted`). The same member and
  parameters are used in every arm. Results across members are unweighted envelopes. Screening candidates and unadmitted
  closures are never performance sources.
- **Chemistry:** TBD. It needs an owner decision: `abep-n2n-0.11` is `COMPLETE_FOR_P5_N2_VALIDATION` over T_e 2–30 eV only,
  and O/O₂ chemistry does not exist. A rate-table validity limit is never extended merely because a design run reaches a
  higher T_e; an extension needs independent published evidence and a new pre-registration (CLAUDE.md, owner decision
  2026-09-26). A design run outside the declared domain is not `chemistry_trustworthy` in any arm.
- **Solver:** HallThruster.jl v0.23.1, commit `bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5` (`PINNED.toml`). Design runs use
  `facility_ingestion = false`.
- **Recorded solver defaults** (identical in all arms until the owner decides otherwise; `configuration.jl` lines 213–228):
  - `WallSheath(BNSiO2, 1.0)`
  - `ion_wall_losses = false`
  - anode `:sheath`
  - cathode coupling 0.0 V (placeholder solver setting, not a design value; see INV-C2) and cathode T_e 2.0 eV
  - `magnetic_field_scale` 1.0

## 11. Related contracts (by path; not required to exist)

- `abep_sim/arch_boundary.py` (`bus_power_boundary_v1`)
- `abep_sim/arch_compare.py`
- `abep_sim/thermal_life.py`
- `docs/evidence/{rf_source,ecr_source,hall_sustainment,cathode,wall_life}/`
- `docs/architecture_comparison/experiment_protocol/`
- `schemas/interfaces/upstream_icd_v1.json` (commit `ced4aa0` on the upstream-ICD lane's branches; not merged here)
- `abep_sim/interstage.py` (`interstage_v1`, commit `18d2bfb` on branch `worktree-wf_15f0f2f8-8d4-2`; not merged here)
- `docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json` (uncommitted work in progress; the
  cross-check is not reproducible from any commit)
- `schemas/ledgers/`
- `docs/hallmap/HALLMAP_PRODUCTION_SPEC.md` (commit `113fab5` on the Hall-map spec lane's branches; not merged here)

None of these commits is merged into this branch. Every mapping or cross-check against them is provisional (PENDING) until
they are merged.

## 12. Open decisions for the owner

1. The PROPOSED V_d range (180–305 V) and set, aligned with the PPU range, and whether to keep the 300 V node next to
   305 V. This includes span rule VR-1, which was stated at repair and not pre-declared; its criterion (c) was tightened at a
   second repair, which moved the upper end from 350 V to 305 V. The alternatives on record are VR-1 with relaxed (c)
   (180–350 V, adding the Busek BHT point whose thrust basis is not stated; it would also follow if the primary Busek report
   shows a measured thrust), the unfiltered Hall-channel span "<100"–350 V, and light-propellant operation far above 350 V
   in another device family (MCFT-2139, 1000 V). The evaluation-set rule (both range ends plus the multiples of 50 V strictly
   inside) is a design-of-experiment assumption; it yields 300 V and 305 V only 5 V apart, and a rule such as "drop an interior
   node closer than 10 V to a range end" would give 180, 200, 250 and 305 V. The owner chooses.
2. `hall_only` hardware: no pre-ionizer, or pre-ionizer installed but unpowered?
3. Per-arm magnet re-optimization as a sensitivity branch?
4. The solver-gap model change and the INV-S1 tolerance.
5. The INV-B3 tolerance.
6. Wall material and shielding.
7. `ion_wall_losses` for wall-life maps.
8. Cathode emitter, gas, position and keeper mode.
9. Mixed anode feed.
10. Design-map chemistry.
11. The `moments_v1` representation, together with the interstage lane.

## 13. Sources accessed (2026-09-26)

Open literature (no contact with authors or labs, no paywall bypass):

| id | citation | URL accessed | sha256 |
|---|---|---|---|
| SRC-GK2008 | Goebel & Katz, *Fundamentals of Electric Propulsion: Ion and Hall Thrusters*, JPL, March 2008 (printed page = PDF page − 10) | https://descanso.jpl.nasa.gov/SciTechBook/series1/Goebel__cmprsd_opt.pdf | a373c8a26137b7c7cd989880c303c4f6c1f84f20a11a02770047f6ba4c249e4e |
| SRC-DM2008 | Dannenmayer & Mazouffre, "Sizing of Hall effect thrusters with input power and thrust level: An empirical approach", arXiv:0810.3994v2 (journal version not accessed: verify) | https://arxiv.org/pdf/0810.3994 | 5fd9e6d03671a94cb26495e704af6a3cd628eb6758180e45d4852241661762bd |
| SRC-DM2011 | Dannenmayer & Mazouffre, "Elementary Scaling Relations for Hall Effect Thrusters", JPP 27(1), 236–245 (2011), doi:10.2514/1.48382 | https://www.aleph-zero.fr/blog/Documents/Articles/JPP_2011_Scaling%20Laws.pdf | 3c97e7cdcce0dc842e4b2b5e562b888a7ba48442dc83ced70cf0cfeb38589ccf |
| SRC-AFG2022 | Andreussi, Ferrato & Giannetti, "A review of air-breathing electric propulsion", J. Electr. Propuls. 1:31 (2022), doi:10.1007/s44205-022-00024-9, CC BY 4.0 | https://link.springer.com/content/pdf/10.1007/s44205-022-00024-9.pdf | 490ca6f6b763fe4ee1089d9815d4075a94223ec74d577f61d67986708c3ce3b7 |

The primary test reports summarized by the review (PPS1350-TSD, HT5k, BHT, Z-70, HHT, Dukhopelnikov et al., MCFT-2139) were **not**
accessed. Their values are evidence level 5, as reported.

**Software source.** The HallThruster.jl v0.23.1 source is installed locally for the bridge. It was read but not executed.
Its identity with the pinned commit: verify.

**Repository files:**

- `hallthruster_bridge/bridge_lib.jl`
- `hallthruster_bridge/hall_map_schema_v1.json`
- `abep_sim/hall_map.py`
- `hallthruster_bridge/PINNED.toml`
- `hallthruster_bridge/ensemble/transport_ensemble_v0.json`
- `abep_sim/constants.py`
- `CLAUDE.md`
- `hallthruster_bridge/cases/p5_n2.json`
- `hallthruster_bridge/identification/echt_n2/README.md`
- `hallthruster_bridge/identification/echt_n2/echt_table_checks_v1.json` (ECHT per-run V_d, I_d and thrust for the
  measured (T, P_d) pairs)
- `abep_sim/archengine.py`
- `abep_sim/plasma_devices.py` (`LaB6Cathode` only)
