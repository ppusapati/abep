# Rust migration - component inventory v2 (four-class classification)

**Status: `PROPOSED_PLAN_V2_FOR_OWNER_REVIEW`.** Docs / plan only. Machine-readable: `component_inventory_v2.json` (authoritative; this page is a rendering). v1 (`component_inventory_v1.json` / `.md`) is kept unchanged as history. Programme: `PROGRAMME.md`; order: `migration_order_v2.json`. Inventoried at `2de86abefacb`. The Python tree there equals the bid technical source `5eee4b8`, except the bid-package builder files and one test.

Governing records: A9.24 items 1, 6, 7, 8, 13 and 14; A9.25 message 1 secs. 9, 13 and 14, message 2 secs. 5, 6, 8, 9 and 10, message 3 (the LaB6 rule, read in full), message 8 secs. 4 and 17; cathode-path audit v1 (`git show b8f39b7:docs/audits/a9_24_cathode_path_audit_v1.md`, branch `lane-a924-cathode`, not merged into the execution branch).

## The rule

**LaB6 / conventional hollow-cathode paths are NOT ported into the active Rust simulator.** A9.25 message 3 rejects the v1 rule "LaB6 paths are ported unchanged pending the audit" and replaces it with this one. Every component has one primary class:

| class | owner rule (A9.25 msg 3) | where it goes |
|---|---|---|
| `ACTIVE_SELECTED_ARCHITECTURE_PHYSICS` | migrate to Rust under pre-registered parity / admission | waves W0-W17 |
| `GROUND_REFERENCE_ONLY` | migrate only if the future active test / evidence toolchain genuinely requires it; never in flight execution | lane GR (on demand) |
| `HISTORICAL_LEGACY_REGRESSION` | do not port; keep the Python implementation and the historical commit / evidence | lane RET (RETIRE != DELETE) |
| `ACTIVE_FLIGHT_INCONSISTENCY` | do not port; resolve against `hall_icp_neutralizer` first, then migrate only the corrected implementation | lane AFI |

Class A means "belongs to the active selected architecture" (A9.25 msg 1 sec. 14 step 2). It therefore also covers that architecture's design, assessment, configuration, evidence and CI toolchain, which A9.24 item 1 makes Rust-owned.

These are not ported as active flight functionality, wherever they sit:

* `LaB6Cathode`;
* `lab6_xe`;
* Xe hollow-cathode heater / keeper logic;
* C1 flight-fallback logic;
* legacy Hall cards whose flight topology contains a hollow cathode;
* historical multi-family architecture-selection machinery that would be kept only for parity.

**Parity** is required only against the authoritative Python implementation of physics that the selected architecture retains: the class-A components and the extract-and-parity kernels listed below. It is never required against obsolete topology.

## Summary

* Python files: **451** (287 outside `tests/`); 262,642 physical lines (199,171 outside `tests/`).
* Components: **227** (224 Python-file components and 3 non-`.py` paths). New since v1: `docs/budgets/mass_power_a9_v4/`, `docs/budgets/mass_power_a9_v5/`, `docs/procurement/rfq_a9_v3_gas_rev1/`.
* Unclassified: **0**. Provisional, owner confirmation requested: **9**.

| class | components | lines | established | proposed | provisional |
|---|---:|---:|---:|---:|---:|
| `ACTIVE_SELECTED_ARCHITECTURE_PHYSICS` | 135 | 175,499 | 2 | 128 | 5 |
| `GROUND_REFERENCE_ONLY` | 7 | 12,502 | 7 | 0 | 0 |
| `HISTORICAL_LEGACY_REGRESSION` | 84 | 73,767 | 52 | 28 | 4 |
| `ACTIVE_FLIGHT_INCONSISTENCY` | 1 | 874 | 1 | 0 | 0 |
| **total** | 227 | 262,642 | | | |

The three non-`.py` paths carry no line count.

| port disposition | components |
|---|---:|
| `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | 84 |
| `MIGRATE_UNDER_PREREG_PARITY` | 114 |
| `RETIRE_AT_END_STATE_MIGRATION_TOOLING` | 3 |
| `ADMITTED_KERNEL_PLUS_MIGRATE_REMAINDER` | 1 |
| `MIGRATE_OR_FORMALLY_RETIRE` | 17 |
| `MIGRATE_ONLY_IF_ACTIVE_TOOLCHAIN_REQUIRES` | 7 |
| `NOT_PORTED_RESOLVE_AGAINST_HALL_ICP_FIRST` | 1 |

## Extract-and-parity kernels (retained physics inside non-class-A modules)

Only these function subsets are ported and parity-tested. The module around each one is not ported (A9.25 msg 3: "extract and parity-test only those architecture-independent physical kernels").

| kernel | source | wave | crate | active consumer | parity reference |
|---|---|---|---|---|---|
| `K-GASPATH` | abep_sim/system.py::physics_closure (collection / compress / AO inlet composition and the cfg.gaspath_physics branch: DragCompressor sizing+run, Reservoir.steady_state, orifice sizing; p_target_Pa supplied explicitly) | W2 | `abep-gaspath` | golden gas_path and the upstream keys of hall_icp_neutralizer_reference; archengine.gas_path_state; profiled workload system_evaluate_gas_path (PRE_RUST rank 4) | golden_v2 gas_path + hall_icp_neutralizer_reference upstream keys (read, never regenerated) and captured Python outputs on a registered grid; domain/error parity incl. the non-converged golden_v1 point (GASPATH_MODEL_NOT_CONVERGED) and golden.admissibility gas-path labels; the Python harness reaches the kernel through Config('hall_1stage') whose card fields are never read on this path (audit AFI-04: zero numeric effect) - the card, its Xe cathode and p_min_Pa default are NOT ported |
| `K-GAS-LIFE` | abep_sim/archengine.py::gas_path_state / make_gas_fn (gas-state wrapper only) + abep_sim/life.py::intake_life, blade_life | W2 | `abep-gaspath / abep-subsystems::life` | golden hall_icp_neutralizer_reference ao_exposure_mission block | golden_v2 hall_icp_neutralizer_reference ao_exposure_mission values + captured Python outputs |
| `K-MASS-RULES` | docs/budgets/mass_power_a9_v3/build_mass_power_a9_v3.py::line_mev_value, harness_row60, closure_state, _unresolved, rollup, system_margin, rk (imported unchanged by the v4 and v5 builders) | W11 | `abep-subsystems::mass` | mass_power_a9_v5 (and its AFI-02-resolved successor) | committed mass_power_a9_v4 / v5 JSON (EXACT_BYTES of the successor record once AFI-02-RA1 closes) |
| `K-P3-RAYS` | docs/experiments/hall_icp/p3_coupled_thermal/p3_thermal_lib.py::view_factors, trace, _first_hits, emit_zone, plume_interception, vf_annulus_to_parallel_coaxial_annulus, Body, h1_body, q_collector | W5 | `abep-subsystems::thermal` | ALREADY EXTRACTED verbatim into abep_sim/icp_thermal_lib.py (source-identity test tests/test_design_layer_separation.py); the port target is icp_thermal_lib (W5) | P3 closed-form verification (RES_VERIFY) + captured outputs; profiled workload p3_view_factors_verify (rank 8) |
| `K-GOLDEN-COMPARE` | abep_sim/golden.py::_compare, check (generic rtol comparison and report) | W16 | `abep-parity / abep-cli` | Rust `abep golden check` over the retained-kernel cases and the post-bid active hall_icp_neutralizer golden | golden_v2.json read byte-for-byte; same pass/fail on a seeded set of perturbed copies |

Candidate kernels are architecture-independent, but no active selected-architecture consumer exists at the inventory commit. One is extracted only when such a consumer appears (A9.25 msg 2 sec. 8):

* `abep_sim/thruster.py`: species_flows (air species split from the atmosphere record); per-species ideal electrostatic relations I_b, v_s, T (the performance() core without the card)
* `abep_sim/thermal.py`: aero_heating_W_m2 (ram aerodynamic heating); solve_network / size_radiator (generic steady lumped network) - only if the post-bid cathodeless successor thermal model (AFI-03) needs them
* `abep_sim/ppu.py`: Converter switching-loss efficiency map (no keeper / heater / stage-1 loads)
* `abep_sim/radiation.py`: RadEnv TID dose-depth, shielding_mass, uv_contamination_ageing, debris_puncture (literature-class parameterisations)
* `abep_sim/mass_bom.py`: xe_tank, thin_wall_sphere_min_mass_kg, reservoir_vessel, structure_mass, hall_magnetic_circuit, hall_channel_mass (geometry / pressure-vessel sizing)
* `abep_sim/life.py`: magnet_life, compressor_life, reliability (generic series / Weibull; without the R_26000h legacy key)
* `docs/architecture_comparison/hall_reference/`: voltage_envelope ideal-beam relations

## ACTIVE_FLIGHT_INCONSISTENCY (lane AFI)

| id | component | basis | rationale | notes |
|---|---|---|---|---|
| C-DOCS_BUDGETS_MASS_POWER_A9_V5 | `docs/budgets/mass_power_a9_v5/` | OD-A925-M2-S4-AFI-02-OPEN, AUDIT-AFI-02 | the active flight mass source (bid basis) carries AL-07 = 6.0 kg PROVISIONAL_CONSERVATIVE_ANALOG_FLOOR whose analog contains C1 heater / keeper / cathode supplies (CONTAINS_LEGACY_FUNCTIONS_NOT_PRESENT_IN_CURRENT_FLIGHT_ARCHITECTURE; REBASE_REQUIRED_FROM_CURRENT_LOAD/CONVERTER CBE; AFI-02-RA1 OPEN) | AFI-02 OPEN: resolve against hall_icp_neutralizer (AFI-02-RA1) first; then migrate only the corrected successor record builder in W11; no numerical change is made or implied here (owner: do not invent the reduction) |

## GROUND_REFERENCE_ONLY (lane GR)

| id | component | basis | rationale | notes |
|---|---|---|---|---|
| C-DOCS_HARDWARE_H2_H2_1_HALL_CHAMBER_MAGNET | `docs/hardware/h2/h2_1_hall_chamber_magnet/` | AUDIT-GR-06 | H2 v1 test article (H-1 + C-1): Hall chamber / magnetic circuit sizing |  |
| C-DOCS_HARDWARE_H2_H2_2_CATHODE_INTEGRATION | `docs/hardware/h2/h2_2_cathode_integration/` | AUDIT-GR-06 | H2-2 C-1 cathode integration (C1 = GROUND_REFERENCE_ONLY lab hardware) |  |
| C-DOCS_HARDWARE_H2_H2_3_GAS_PATH_PLENUM | `docs/hardware/h2/h2_3_gas_path_plenum/` | AUDIT-GR-06 | H2 v1 test article: gas path / plenum |  |
| C-DOCS_HARDWARE_H2_H2_4_PPU_BUS | `docs/hardware/h2/h2_4_ppu_bus/` | AUDIT-GR-06 | H2 v1 test article: PPU / bus allocation on bus_power_boundary_v1 |  |
| C-DOCS_HARDWARE_H2_H2_5_THERMAL_NETWORK | `docs/hardware/h2/h2_5_thermal_network/` | AUDIT-GR-06 | H2 v1 test article: thermal network incl. the C-1 heat node (source of AFI-03; never a flight thermal closure) |  |
| C-DOCS_HARDWARE_H2_H2_6_DIAGNOSTICS_FIXTURE | `docs/hardware/h2/h2_6_diagnostics_fixture/` | AUDIT-GR-06 | H2 v1 test article: diagnostics + H-1 fixture | KNOWN ACTIVE REQUIREMENT: scripts/ci_checks.py check h2_6_live_sources imports this builder's verify_sources() - W16 decides: port that function (class-2 migration because the active CI needs it) or retire the check with H2 v1 history |
| C-DOCS_HARDWARE_H2_H2_7_MECHANICAL_BOM | `docs/hardware/h2/h2_7_mechanical_bom/` | AUDIT-GR-06 | H2 v1 test article: mechanical envelope / mass model |  |

## HISTORICAL_LEGACY_REGRESSION (lane RET: not ported)

| id | component | conf. | basis | not ported (or rationale) | kernels extracted |
|---|---|---|---|---|---|
| C-ABEP_SIM_PACKAGE_ENTRY_POINTS | `abep_sim/(package entry points)` | E | AUDIT-HR-02 | legacy Hall cards whose flight topology contains a hollow cathode (thruster.CARDS, hall_1stage XE_CATHODE) | - |
| C-ABEP_SIM_ARCH_BOUNDARY_PY | `abep_sim/arch_boundary.py` | E | A5-MULTI-FAMILY-COMPARISON, AUDIT-HR-11 | historical multi-family architecture-selection machinery (archengine families lab6_xe, mw_air, rf_cathode, ECR-Hall, gridded / nozzle / MPD / PIT / thermal); LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper) | - |
| C-ABEP_SIM_ARCH_COMPARE_PY | `abep_sim/arch_compare.py` | E | OD-A925-M2-S10-SECTION-E, A5-MULTI-FAMILY-COMPARISON | historical multi-family architecture-selection machinery (archengine families lab6_xe, mw_air, rf_cathode, ECR-Hall, gridded / nozzle / MPD / PIT / thermal) | - |
| C-ABEP_SIM_ARCHENGINE_PY | `abep_sim/archengine.py` | E | OD-A925-M2-S10-SECTION-E, OD-A925-M2-S8-HISTORICAL-ARCH-TRADE, AUDIT-HR-04 | historical multi-family architecture-selection machinery (archengine families lab6_xe, mw_air, rf_cathode, ECR-Hall, gridded / nozzle / MPD / PIT / thermal); LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper); withdrawn 0-D Hall closure (plasma_devices Hall channel / source coupling; CLAUDE.md superseded results); close_architecture / propulsion_map / pareto / run_all / DesignConstraints / flight guard | `K-GAS-LIFE` |
| C-ABEP_SIM_ASSESSMENT_ARCH_CONSTRAINTS_PY | `abep_sim/assessment/arch_constraints.py` | P | A5-MULTI-FAMILY-COMPARISON | historical multi-family architecture-selection machinery (archengine families lab6_xe, mw_air, rf_cathode, ECR-Hall, gridded / nozzle / MPD / PIT / thermal) | - |
| C-ABEP_SIM_ASSESSMENT_CLOSURE_CHECKS_PY | `abep_sim/assessment/closure_checks.py` | P | AUDIT-HR-02 | legacy Hall cards whose flight topology contains a hollow cathode (thruster.CARDS, hall_1stage XE_CATHODE); LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper) | - |
| C-ABEP_SIM_BREAKEVEN_PY | `abep_sim/breakeven.py` | E | OD-A925-M2-S10-SECTION-E, A5-MULTI-FAMILY-COMPARISON | historical multi-family architecture-selection machinery (archengine families lab6_xe, mw_air, rf_cathode, ECR-Hall, gridded / nozzle / MPD / PIT / thermal); historical upstream RF / ECR pre-ionizer source logic | - |
| C-ABEP_SIM_CATHODE_INTEGRATION_PY | `abep_sim/cathode_integration.py` | E | OD-A925-M2-S10-SECTION-E, AUDIT-HR-11 | LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper); historical multi-family architecture-selection machinery (archengine families lab6_xe, mw_air, rf_cathode, ECR-Hall, gridded / nozzle / MPD / PIT / thermal) | - |
| C-ABEP_SIM_COMPRESSOR_TRANSITIONAL_PY | `abep_sim/compressor_transitional.py` | E | OD-A925-M2-S10-SECTION-E | owner-approved section-E retirement (CANDIDATE_NOT_ADMITTED transitional model; never imported by the F-chain) | - |
| C-ABEP_SIM_CONVERGENCE_PY | `abep_sim/convergence.py` | E | OD-A925-M2-S10-SECTION-E, AUDIT-HR-08 | withdrawn 0-D Hall closure (plasma_devices Hall channel / source coupling; CLAUDE.md superseded results); historical multi-family architecture-selection machinery (archengine families lab6_xe, mw_air, rf_cathode, ECR-Hall, gridded / nozzle / MPD / PIT / thermal) | - |
| C-ABEP_SIM_EXPLORER_PY | `abep_sim/explorer.py` | E | OD-A925-M2-S10-SECTION-E | owner-approved section-E retirement (explorer) | - |
| C-ABEP_SIM_GOLDEN_PY | `abep_sim/golden.py` | E | OD-A925-M2-S6-S9-GOLDEN-HISTORICAL-COMPAT, AUDIT-AFI-04, AUDIT-HR-05 | legacy Hall cards whose flight topology contains a hollow cathode (thruster.CARDS, hall_1stage XE_CATHODE); LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper); historical multi-family architecture-selection machinery (archengine families lab6_xe, mw_air, rf_cathode, ECR-Hall, gridded / nozzle / MPD / PIT / thermal); withdrawn 0-D Hall closure (plasma_devices Hall channel / source coupling; CLAUDE.md superseded results); design_point_selection rule (its 'closed' test uses the historical lab6_xe archengine closure) | `K-GOLDEN-COMPARE` |
| C-ABEP_SIM_HALL1D_PY | `abep_sim/hall1d.py` | E | OD-A925-M2-S10-SECTION-E, WITHDRAWN-0D-HALL | owner-approved section-E retirement (hall1d sanity model) | - |
| C-ABEP_SIM_HARD_GATES_PY | `abep_sim/hard_gates.py` | P | A5-MULTI-FAMILY-COMPARISON, AUDIT-HR-11 | historical multi-family architecture-selection machinery (archengine families lab6_xe, mw_air, rf_cathode, ECR-Hall, gridded / nozzle / MPD / PIT / thermal) | - |
| C-ABEP_SIM_INTERSTAGE_PY | `abep_sim/interstage.py` | E | OD-A925-M2-S10-SECTION-E, A9-HISTORICAL-UPSTREAM-CAMPAIGN | historical upstream RF / ECR pre-ionizer source logic | - |
| C-ABEP_SIM_LIFE_PY | `abep_sim/life.py` | P | AUDIT-HR-03, OD-A925-M3-LAB6-NOT-PORTED | LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper): cathode_life, LifeInputs.cathode_*; hall_channel_life (parametric 300 um/kh sputter-rate input; the selected architecture's wall life comes from Hall-map wall flux via thermal_life G11 or measured hardware); LEGACY_RELIABILITY_HORIZON_H R_26000h compatibility key | `K-GAS-LIFE` |
| C-ABEP_SIM_MASS_BOM_PY | `abep_sim/mass_bom.py` | P | A5-MULTI-FAMILY-COMPARISON, AUDIT-HR-11 | cathode BOM lines (HR-11); historical multi-family architecture-selection machinery (archengine families lab6_xe, mw_air, rf_cathode, ECR-Hall, gridded / nozzle / MPD / PIT / thermal) | - |
| C-ABEP_SIM_MISSION5_PY | `abep_sim/mission5.py` | E | AUDIT-HR-06, WITHDRAWN-CHAIN | run_mission_generic driver (its mission_env.propagate core migrates in W3) | - |
| C-ABEP_SIM_MISSION_UQ_PY | `abep_sim/mission_uq.py` | E | OD-A925-M2-S10-SECTION-E | legacy Hall cards whose flight topology contains a hollow cathode (thruster.CARDS, hall_1stage XE_CATHODE) | - |
| C-ABEP_SIM_ORBIT_ATM_PY | `abep_sim/orbit_atm.py` | P | SUPERSEDED-VERSION | Phase-1 Keplerian orbit atmosphere with live pymsis; superseded by atmosphere_orbit (frozen); no consumer | - |
| C-ABEP_SIM_PLASMA_CHEM_PY | `abep_sim/plasma_chem.py` | Q | WITHDRAWN-0D-HALL, A9-HISTORICAL-UPSTREAM-CAMPAIGN | withdrawn 0-D Hall closure (plasma_devices Hall channel / source coupling; CLAUDE.md superseded results); historical upstream RF / ECR pre-ionizer source logic | - |
| C-ABEP_SIM_PLASMA_DEVICES_PY | `abep_sim/plasma_devices.py` | E | OD-A925-M2-S10-SECTION-E, WITHDRAWN-0D-HALL, OD-A925-M3-LAB6-NOT-PORTED, AUDIT-HR-01 | LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper); withdrawn 0-D Hall closure (plasma_devices Hall channel / source coupling; CLAUDE.md superseded results) | - |
| C-ABEP_SIM_PPU_PY | `abep_sim/ppu.py` | P | OD-A925-M3-LAB6-NOT-PORTED, WITHDRAWN-CHAIN | Xe hollow-cathode heater / keeper load logic (owner A9.25 msg 3); historical upstream RF / ECR pre-ionizer source logic | - |
| C-ABEP_SIM_PROGRAMME_ARCH_COMPARE_PY | `abep_sim/programme/arch_compare.py` | E | OD-A925-M2-S10-SECTION-E, A5-MULTI-FAMILY-COMPARISON | programme layer of arch_compare | - |
| C-ABEP_SIM_PROGRAMME_CLOSURE_PY | `abep_sim/programme/closure.py` | P | AUDIT-HR-03 | legacy Hall cards whose flight topology contains a hollow cathode (thruster.CARDS, hall_1stage XE_CATHODE) | - |
| C-ABEP_SIM_PROGRAMME_SWEEP_PY | `abep_sim/programme/sweep.py` | E | AUDIT-HR-02 | legacy Hall cards whose flight topology contains a hollow cathode (thruster.CARDS, hall_1stage XE_CATHODE) | - |
| C-ABEP_SIM_PROGRAMME_UQ_MODULAR_PY | `abep_sim/programme/uq_modular.py` | E | OD-A925-M2-S10-SECTION-E | historical multi-family architecture-selection machinery (archengine families lab6_xe, mw_air, rf_cathode, ECR-Hall, gridded / nozzle / MPD / PIT / thermal) | - |
| C-ABEP_SIM_RADIATION_PY | `abep_sim/radiation.py` | P | WITHDRAWN-CHAIN | Phase-5 radiation / UV / debris parameterisations consumed only by mission5 | - |
| C-ABEP_SIM_SIZING_PY | `abep_sim/sizing.py` | E | OD-A925-M2-S10-SECTION-E | legacy Hall cards whose flight topology contains a hollow cathode (thruster.CARDS, hall_1stage XE_CATHODE) | - |
| C-ABEP_SIM_SYSTEM_PY | `abep_sim/system.py` | E | AUDIT-HR-03, AUDIT-AFI-04, OD-A925-M3-LAB6-NOT-PORTED | legacy Hall cards whose flight topology contains a hollow cathode (thruster.CARDS, hall_1stage XE_CATHODE); LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper); withdrawn 0-D Hall closure (plasma_devices Hall channel / source coupling; CLAUDE.md superseded results); engineering_physics branch (legacy thermal / PPU / BOM / life roll-up incl. cathode starts 541 -> 547); evaluate() legacy merge; Config / Budgets card selection; card p_min_Pa default for p_target | `K-GASPATH` |
| C-ABEP_SIM_THERMAL_PY | `abep_sim/thermal.py` | P | WITHDRAWN-CHAIN, OD-A925-M3-LAB6-NOT-PORTED | default_nodes topology with the cathode node and stage-1 source node | - |
| C-ABEP_SIM_THRESHOLDS_PY | `abep_sim/thresholds.py` | E | OD-A925-M2-S10-SECTION-E | owner-approved section-E retirement (thresholds) | - |
| C-ABEP_SIM_THRUSTER_PY | `abep_sim/thruster.py` | E | OD-A925-M2-S10-SECTION-E, AUDIT-HR-02, OD-A925-M3-LAB6-NOT-PORTED | legacy Hall cards whose flight topology contains a hollow cathode (thruster.CARDS, hall_1stage XE_CATHODE); Cathode / XE_CATHODE (Xe-fed LaB6) and xe_for_thrust card logic | - |
| C-ABEP_SIM_TRANSIENT_PY | `abep_sim/transient.py` | E | AUDIT-HR-02 | legacy Hall cards whose flight topology contains a hollow cathode (thruster.CARDS, hall_1stage XE_CATHODE) | - |
| C-ABEP_SIM_UNCERTAINTY_PY | `abep_sim/uncertainty.py` | E | OD-A925-M2-S10-SECTION-E | owner-approved section-E retirement (uncertainty) | - |
| C-ABEP_SIM_UQ6_PY | `abep_sim/uq6.py` | E | OD-A925-M2-S10-SECTION-E, AUDIT-HR-07 | owner-approved section-E retirement (uq6) | - |
| C-ABEP_SIM_UQ_MODULAR_PY | `abep_sim/uq_modular.py` | E | OD-A925-M2-S10-SECTION-E | owner-approved section-E retirement (uq_modular) | - |
| C-ABEP_SIM_VALIDATION_PY | `abep_sim/validation.py` | P | WITHDRAWN-0D-HALL | 0-D Hall validation harness (HISTORICAL_UNSUPPORTED anchor); gate-3 validation is the HallThruster.jl P5 tooling (W8) | - |
| C-ABEP_SIM_XE_LEDGER_PY | `abep_sim/xe_ledger.py` | E | SUPERSEDED-VERSION, AUDIT-HR-11 | LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper) | - |
| C-DOCS_ARCHITECTURE_COMPARISON_AUX_BUS | `docs/architecture_comparison/aux_bus/` | P | A5-MULTI-FAMILY-COMPARISON | aux / DC-bus comparison of hall_only / rf_hall / ecr_hall on bus_power_boundary_v1 | - |
| C-DOCS_ARCHITECTURE_COMPARISON_CATHODE_INTEGRATION | `docs/architecture_comparison/cathode_integration/` | E | OD-A925-M2-S10-SECTION-E, AUDIT-HR-11 | LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper) | - |
| C-DOCS_ARCHITECTURE_COMPARISON_COMPRESSOR_DOWNSELECT | `docs/architecture_comparison/compressor_downselect/` | Q | PIVOT-ERA-2026-09-27, SUPERSEDED-VERSION | pivot-era DI-1.4 compressor down-selection (loads the lane-16 feed envelope); superseded for design by F3 synthesis, which cites its findings CD-01 / CD-04 as frozen evidence | - |
| C-DOCS_ARCHITECTURE_COMPARISON_ELECTRICAL_CLOSURE_TOOLS | `docs/architecture_comparison/electrical_closure/tools/` | P | A5-MULTI-FAMILY-COMPARISON | PPUMAG electrical closure on bus_power_boundary_v1 | - |
| C-DOCS_ARCHITECTURE_COMPARISON_EXPERIMENT_PACKAGE | `docs/architecture_comparison/experiment_package/` | P | A5-MULTI-FAMILY-COMPARISON | experimental decision package of the multi-family comparison | - |
| C-DOCS_ARCHITECTURE_COMPARISON_EXPERIMENT_PROTOCOL | `docs/architecture_comparison/experiment_protocol/` | P | A9-HISTORICAL-UPSTREAM-CAMPAIGN | common-condition ionization-architecture comparison protocol (draft) | - |
| C-DOCS_ARCHITECTURE_COMPARISON_FAILURE_TREE | `docs/architecture_comparison/failure_tree/` | P | A5-MULTI-FAMILY-COMPARISON | per-architecture failure tree / evidence ranking | - |
| C-DOCS_ARCHITECTURE_COMPARISON_FEED_STATE_CLOSURE | `docs/architecture_comparison/feed_state_closure/` | Q | PIVOT-ERA-2026-09-27 | pivot-era W1 feed-state closure (system.evaluate lane-16 conventions); F1 / F4 / RVM cite its setpoint ladder as frozen evidence; the active feed synthesis is F4 | - |
| C-DOCS_ARCHITECTURE_COMPARISON_HALL_REFERENCE | `docs/architecture_comparison/hall_reference/` | P | A5-MULTI-FAMILY-COMPARISON | ideal-beam Hall reference consumed only by A5 machinery (bundle 1, pre-ionizer ICD) | - |
| C-DOCS_ARCHITECTURE_COMPARISON_LOCK1 | `docs/architecture_comparison/lock1/` | E | A9-HISTORICAL-UPSTREAM-CAMPAIGN | LOCK-1 decision brief (A9: historical) | - |
| C-DOCS_ARCHITECTURE_COMPARISON_MINIMUM_DECISIVE_EXPERIMENT | `docs/architecture_comparison/minimum_decisive_experiment/` | P | A5-MULTI-FAMILY-COMPARISON | lane-25 minimum decisive experiment (multi-family) | - |
| C-DOCS_ARCHITECTURE_COMPARISON_OVERLAYS_ECR | `docs/architecture_comparison/overlays/ecr/` | E | A9-HISTORICAL-UPSTREAM-CAMPAIGN | ECR evidence on break-even surfaces | - |
| C-DOCS_ARCHITECTURE_COMPARISON_OVERLAYS_HALL_SUSTAINMENT | `docs/architecture_comparison/overlays/hall_sustainment/` | P | A5-MULTI-FAMILY-COMPARISON, OD-A925-M2-S10-SECTION-E | Hall-only evidence overlaid on break-even surfaces | - |
| C-DOCS_ARCHITECTURE_COMPARISON_OVERLAYS_RF | `docs/architecture_comparison/overlays/rf/` | E | A9-HISTORICAL-UPSTREAM-CAMPAIGN | RF source evidence on break-even surfaces | - |
| C-DOCS_ARCHITECTURE_COMPARISON_POWER_BOUNDARY_TOOLS | `docs/architecture_comparison/power_boundary/tools/` | P | A5-MULTI-FAMILY-COMPARISON | bus_power_boundary_v1 evidence tooling (Rhodes 2024 digitisation, audit anchors over system / archengine); the extracted evidence stays frozen | - |
| C-DOCS_ARCHITECTURE_COMPARISON_POWER_BOUNDARY_A9 | `docs/architecture_comparison/power_boundary_a9/` | P | SUPERSEDED-VERSION | A9-02 boundary v1 builder; superseded by the v2 builder (the abep_sim/bus_boundary_a9.py module stays active because v2 wraps it) | - |
| C-DOCS_ARCHITECTURE_COMPARISON_VETO_LAYER | `docs/architecture_comparison/veto_layer/` | P | A5-MULTI-FAMILY-COMPARISON | mass / thermal / life / start-up veto layer of the multi-family comparison | - |
| C-DOCS_BUDGETS_MASS_A9 | `docs/budgets/mass_a9/` | E | SUPERSEDED-VERSION, AUDIT-HR-12 | superseded A9 mass reconciliation | - |
| C-DOCS_BUDGETS_MASS_POWER_A9_V2 | `docs/budgets/mass_power_a9_v2/` | E | SUPERSEDED-VERSION, AUDIT-HR-12 | superseded mass / power v2 | - |
| C-DOCS_BUDGETS_MASS_POWER_A9_V3 | `docs/budgets/mass_power_a9_v3/` | E | SUPERSEDED-VERSION, AUDIT-AFI-01 | AL-08 C1 cathode-feed branch (historical); retired C1 column | `K-MASS-RULES` |
| C-DOCS_BUDGETS_SUBSYSTEM_MATURITY | `docs/budgets/subsystem_maturity/` | E | SUPERSEDED-VERSION, AUDIT-HR-12 | M16 v2 (superseded by M16 v5) | - |
| C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V2 | `docs/budgets/xe_accounting_a9_v2/` | E | SUPERSEDED-VERSION, AUDIT-HR-12 | Xe accounting v2 (superseded by v3) | - |
| C-DOCS_BUDGETS_XE_LEDGER | `docs/budgets/xe_ledger/` | E | SUPERSEDED-VERSION, AUDIT-HR-12, A5-MULTI-FAMILY-COMPARISON | LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper) | - |
| C-DOCS_BUDGETS_XE_LEDGER_A9 | `docs/budgets/xe_ledger_a9/` | E | SUPERSEDED-VERSION | A9-08 Xe ledger (superseded by Xe accounting v2 -> v3) | - |
| C-DOCS_EVIDENCE_COMPRESSOR_TRANSITIONAL | `docs/evidence/compressor_transitional/` | E | OD-A925-M2-S10-SECTION-E | evidence package of the CANDIDATE_NOT_ADMITTED transitional model | - |
| C-DOCS_EVIDENCE_ECR_SOURCE | `docs/evidence/ecr_source/` | E | A9-HISTORICAL-UPSTREAM-CAMPAIGN | ECR source evidence matrix | - |
| C-DOCS_EVIDENCE_RF_SOURCE | `docs/evidence/rf_source/` | E | A9-HISTORICAL-UPSTREAM-CAMPAIGN | RF pre-ionizer source evidence (upstream; not the ICP neutralizer) | - |
| C-DOCS_EXPERIMENTS_CAPABILITY_DEMO | `docs/experiments/capability_demo/` | Q | PIVOT-ERA-2026-09-27 | pivot W4 capability-demonstration prep for HW-0 / HW-RF / HW-ECR; no A9 consumer | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_INTEGRATION_M16_V4 | `docs/experiments/hall_icp/integration/m16_v4/` | E | SUPERSEDED-VERSION, AUDIT-HR-12 | M16 v4 (superseded by v5) | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_P3_COUPLED_THERMAL | `docs/experiments/hall_icp/p3_coupled_thermal/` | E | OD-A925-M2-S5-M8-S4-AFI-03, AUDIT-AFI-03 | h25_coupled_network with the C-1 cathode-body node and Q_cath; C1 flight-fallback logic / CONTROL_FALLBACK reading (C1 = GROUND_REFERENCE_ONLY; labelled provenance only) | `K-P3-RAYS` |
| C-DOCS_EXPERIMENTS_PHASE1_PREREG_FRAMEWORK | `docs/experiments/phase1_prereg_framework/` | E | A9-HISTORICAL-UPSTREAM-CAMPAIGN | Phase-1 pre-registration framework (A9: historical) | - |
| C-DOCS_INTERFACES_PREIONIZER_MODULE | `docs/interfaces/preionizer_module/` | E | A9-HISTORICAL-UPSTREAM-CAMPAIGN | common pre-ionizer module ICD (upstream pre-ionizer: historical) | - |
| C-DOCS_MILESTONES_BUNDLE1 | `docs/milestones/bundle1/` | P | A5-MULTI-FAMILY-COMPARISON | Bundle 1 Milestone-A conditional selection among hall_only / rf_hall / ecr_hall | - |
| C-DOCS_PROCUREMENT_RFQ_A9 | `docs/procurement/rfq_a9/` | E | SUPERSEDED-VERSION, AUDIT-HR-12 | RFQ v1 (superseded) | - |
| C-DOCS_PROCUREMENT_RFQ_A9_V2 | `docs/procurement/rfq_a9_v2/` | E | SUPERSEDED-VERSION, AUDIT-HR-12 | RFQ v2 (superseded) | - |
| C-DOCS_TRACEABILITY | `docs/traceability/` | E | A5-MULTI-FAMILY-COMPARISON | RTM v1 (the RVM builder itself labels it 'historical requirement traceability matrix v1 (hall_only / rf_hall / ecr_hall)') | - |
| C-SCRIPTS_ARCHITECTURE_BUILD_BREAKEVEN_SURFACES_PY | `scripts/architecture/build_breakeven_surfaces.py` | E | A5-MULTI-FAMILY-COMPARISON, OD-A925-M2-S10-SECTION-E | break-even surfaces (section E breakeven) | - |
| C-SCRIPTS_ARCHITECTURE_BUILD_COMPARISON_GRID_PY | `scripts/architecture/build_comparison_grid.py` | P | A5-MULTI-FAMILY-COMPARISON | hall_only / rf_hall / ecr_hall comparison grid | - |
| C-SCRIPTS_ARCHITECTURE_BUILD_DECISION_DOSSIER_PY | `scripts/architecture/build_decision_dossier.py` | P | A5-MULTI-FAMILY-COMPARISON | lane-27 decision dossier (multi-family) | - |
| C-SCRIPTS_ARCHITECTURE_BUILD_FEED_ENVELOPE_PY | `scripts/architecture/build_feed_envelope.py` | P | A5-MULTI-FAMILY-COMPARISON | lane-16 feed envelope (multi-family; system.evaluate conventions) | - |
| C-SCRIPTS_ARCHITECTURE_SCALING_SIMILARITY_PY | `scripts/architecture/scaling_similarity.py` | P | A5-MULTI-FAMILY-COMPARISON | lane-22 P5 -> Vyovrinda scaling audit on bus_power_boundary_v1 (consumed only by H2-1, the veto layer and the dossier) | - |
| C-SCRIPTS_CONFIG_BUILD_RESULT_SCHEMAS_PY | `scripts/config/build_result_schemas.py` | E | AUDIT-HR-10 | raw_closure_v2 / closure_assessment schemas of the legacy card closure (cathode fields) | - |
| C-TESTS_FIXTURES | `tests/fixtures` | E | AUDIT-HR-15, AUDIT-HR-03 | generators of the legacy system.evaluate identity fixtures (cathode starts 541 -> 547 rows) | - |
| C-DOCS_BUDGETS_MASS_POWER_A9_V4 | `docs/budgets/mass_power_a9_v4/` | E | SUPERSEDED-VERSION | AFI-01 successor of v3, itself superseded by v5 (A9.26 bid mass policy); v5 loads this builder module as pinned code | - |
| C-DOCS_ORCHESTRATION_RUNNER_SCRIPTS_SH_INLINE_PYTHON | `docs/orchestration/runner_scripts/*.sh (inline python)` | P | EXECUTED-RUNNER | executed P5-N2 campaign runners; their execution records are immutable (v1 note: retire, do not port) | - |

Confidence: E = established (an owner record or an audit item names it), P = proposed (this lane's reading of the repository), Q = provisional.

## ACTIVE_SELECTED_ARCHITECTURE_PHYSICS (waves)

| id | component | wave | disposition | conf. | lines | not ported inside / ground-reference parts / AFI |
|---|---|---|---|---|---:|---|
| C-ABEP_SIM_ATMOSPHERE_PY | `abep_sim/atmosphere.py` | W1E | `MIGRATE_UNDER_PREREG_PARITY` | P | 171 | - |
| C-ABEP_SIM_CONFIGURATION_PY | `abep_sim/configuration.py` | W1E | `MIGRATE_UNDER_PREREG_PARITY` | P | 480 | - |
| C-ABEP_SIM_CONSTANTS_PY | `abep_sim/constants.py` | W1E | `MIGRATE_UNDER_PREREG_PARITY` | P | 37 | - |
| C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY | `abep_sim/design/a9_19_architecture.py` | W1E | `MIGRATE_UNDER_PREREG_PARITY` | P | 293 | - |
| C-ABEP_SIM_DESIGN_ENGINEERING_CONSTRAINTS_PY | `abep_sim/design/engineering_constraints.py` | W1E | `MIGRATE_UNDER_PREREG_PARITY` | P | 82 | - |
| C-ABEP_SIM_MATERIALS_PY | `abep_sim/materials.py` | W1E | `MIGRATE_UNDER_PREREG_PARITY` | P | 104 | - |
| C-ABEP_SIM_OPERATING_INPUTS_PY | `abep_sim/operating_inputs.py` | W1E | `MIGRATE_UNDER_PREREG_PARITY` | P | 53 | - |
| C-ABEP_SIM_INTAKE_TPMC_PY | `abep_sim/intake_tpmc.py` | W0+W1 | `ADMITTED_KERNEL_PLUS_MIGRATE_REMAINDER` | E | 475 | - |
| C-ABEP_SIM_ATMOSPHERE_ORBIT_PY | `abep_sim/atmosphere_orbit.py` | W1 | `MIGRATE_UNDER_PREREG_PARITY` | P | 1479 | - |
| C-ABEP_SIM_DESIGN_INTAKE_SYNTHESIS_PY | `abep_sim/design/intake_synthesis.py` | W1 | `MIGRATE_UNDER_PREREG_PARITY` | P | 1598 | - |
| C-ABEP_SIM_INTAKE_PY | `abep_sim/intake.py` | W1 | `MIGRATE_UNDER_PREREG_PARITY` | P | 130 | - |
| C-ABEP_SIM_INTAKE_SURFACE_V2_SPEC_PY | `abep_sim/intake_surface_v2_spec.py` | W1 | `MIGRATE_UNDER_PREREG_PARITY` | P | 189 | - |
| C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY | `abep_sim/spacecraft_reference_drag.py` | W1 | `MIGRATE_UNDER_PREREG_PARITY` | P | 560 | - |
| C-ABEP_SIM_STATEWISE_PY | `abep_sim/statewise.py` | W1 | `MIGRATE_UNDER_PREREG_PARITY` | P | 76 | - |
| C-ABEP_SIM_AOCHEM_PY | `abep_sim/aochem.py` | W2 | `MIGRATE_UNDER_PREREG_PARITY` | P | 113 | - |
| C-ABEP_SIM_COMPRESSOR_PY | `abep_sim/compressor.py` | W2 | `MIGRATE_UNDER_PREREG_PARITY` | P | 317 | - |
| C-ABEP_SIM_DESIGN_COMPRESSOR_SYNTHESIS_PY | `abep_sim/design/compressor_synthesis.py` | W2 | `MIGRATE_UNDER_PREREG_PARITY` | P | 995 | - |
| C-ABEP_SIM_DESIGN_FILTER_STAGE_PY | `abep_sim/design/filter_stage.py` | W2 | `MIGRATE_UNDER_PREREG_PARITY` | P | 1065 | - |
| C-ABEP_SIM_DESIGN_PLENUM_FEED_PY | `abep_sim/design/plenum_feed.py` | W2 | `MIGRATE_UNDER_PREREG_PARITY` | P | 1511 | - |
| C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY | `abep_sim/design/upstream_a9_13.py` | W2 | `MIGRATE_UNDER_PREREG_PARITY` | P | 818 | - |
| C-ABEP_SIM_RESERVOIR_PY | `abep_sim/reservoir.py` | W2 | `MIGRATE_UNDER_PREREG_PARITY` | P | 180 | - |
| C-ABEP_SIM_ROTOR_STRENGTH_PY | `abep_sim/rotor_strength.py` | W2 | `MIGRATE_UNDER_PREREG_PARITY` | P | 281 | - |
| C-ABEP_SIM_MISSION_ENV_PY | `abep_sim/mission_env.py` | W3 | `MIGRATE_UNDER_PREREG_PARITY` | P | 173 | - |
| C-ABEP_SIM_BUS_BOUNDARY_A9_PY | `abep_sim/bus_boundary_a9.py` | W4 | `MIGRATE_UNDER_PREREG_PARITY` | P | 956 | GR: C1 ground-reference slot (GROUND_REFERENCE_ONLY; never a flight slot) |
| C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY | `abep_sim/bus_boundary_a9_v2.py` | W4 | `MIGRATE_UNDER_PREREG_PARITY` | P | 122 | GR: C1 ground-reference slot inherited from v1 |
| C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY | `abep_sim/design/architecture_optimizer.py` | W4 | `MIGRATE_UNDER_PREREG_PARITY` | P | 1262 | AFI-01 RESOLVED (reads mass_power_a9_v5 with no C1 hardware in flight AL-08); AFI-02 OPEN (reads the labelled AL-07 PROVISIONAL_CONSERVATIVE_ANALOG_FLOOR; consumer only) |
| C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY | `abep_sim/design/robust_optimizer.py` | W4 | `MIGRATE_UNDER_PREREG_PARITY` | P | 453 | - |
| C-ABEP_SIM_H1_GEOMETRY_PY | `abep_sim/h1_geometry.py` | W4 | `MIGRATE_UNDER_PREREG_PARITY` | P | 64 | - |
| C-ABEP_SIM_ICP_THERMAL_LIB_PY | `abep_sim/icp_thermal_lib.py` | W5 | `MIGRATE_UNDER_PREREG_PARITY` | P | 509 | - |
| C-ABEP_SIM_ATMOSPHERE_ORBIT_V2_PY | `abep_sim/atmosphere_orbit_v2.py` | W6 | `MIGRATE_UNDER_PREREG_PARITY` | P | 1180 | - |
| C-ABEP_SIM_RATE_TABLES_PY | `abep_sim/rate_tables.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 66 | - |
| C-DOCS_CHEMISTRY_N2_DOMAIN_EXTENSION_DX5 | `docs/chemistry/n2_domain_extension/dx5/` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 509 | - |
| C-DOCS_CHEMISTRY_N2_DOMAIN_EXTENSION_DX5_ACQUISITION | `docs/chemistry/n2_domain_extension/dx5/acquisition/` | W7 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 335 | - |
| C-DOCS_CHEMISTRY_N2_DOMAIN_EXTENSION_DX5_CURATION | `docs/chemistry/n2_domain_extension/dx5/curation/` | W7 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 224 | - |
| C-DOCS_CHEMISTRY_O_O2_V0 | `docs/chemistry/o_o2/v0/` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 710 | - |
| C-SCRIPTS_AUDIT_N2_COMPLETENESS_FINAL_PY | `scripts/audit_n2_completeness_final.py` | W7 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 210 | - |
| C-SCRIPTS_AUDIT_N2_DISSOCIATIVE_IONIZATION_PY | `scripts/audit_n2_dissociative_ionization.py` | W7 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 126 | - |
| C-SCRIPTS_AUDIT_N2_VIBRATIONAL_EXCITATION_PY | `scripts/audit_n2_vibrational_excitation.py` | W7 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 183 | - |
| C-SCRIPTS_BUILD_MULTIPLY_CHARGED_TABLES_PY | `scripts/build_multiply_charged_tables.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 156 | - |
| C-SCRIPTS_BUILD_N2_DISSOCIATION_TABLE_PY | `scripts/build_n2_dissociation_table.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 65 | - |
| C-SCRIPTS_BUILD_N2_DISSOCIATIVE_IONIZATION_TABLE_PY | `scripts/build_n2_dissociative_ionization_table.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 97 | - |
| C-SCRIPTS_BUILD_N2_ELASTIC_SONG2023_TABLE_PY | `scripts/build_n2_elastic_song2023_table.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 78 | - |
| C-SCRIPTS_BUILD_N2_ELECTRONIC_EXCITATION_TABLES_PY | `scripts/build_n2_electronic_excitation_tables.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 147 | - |
| C-SCRIPTS_BUILD_N2_IONIZATION_SONG2023_TABLE_PY | `scripts/build_n2_ionization_song2023_table.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 69 | - |
| C-SCRIPTS_BUILD_N2_ROTATIONAL_TABLES_PY | `scripts/build_n2_rotational_tables.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 42 | - |
| C-SCRIPTS_BUILD_N2_TO_N_Z2PLUS_TABLE_PY | `scripts/build_n2_to_n_z2plus_table.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 62 | - |
| C-SCRIPTS_BUILD_N2_VIBRATIONAL_TABLES_PY | `scripts/build_n2_vibrational_tables.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 74 | - |
| C-SCRIPTS_BUILD_N_ELASTIC_TABLES_PY | `scripts/build_n_elastic_tables.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 125 | - |
| C-SCRIPTS_BUILD_N_IONIZATION_TABLE_PY | `scripts/build_n_ionization_table.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 66 | - |
| C-SCRIPTS_BUILD_N_Z1PLUS_TO_Z2PLUS_TABLE_PY | `scripts/build_n_z1plus_to_z2plus_table.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 66 | - |
| C-SCRIPTS_CHEMISTRY_N2_DOMAIN_EXTENSION_REQUIREMENTS_PY | `scripts/chemistry/n2_domain_extension_requirements.py` | W7 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 892 | - |
| C-SCRIPTS_MAKE_N2_VARIANT_CONFIGS_PY | `scripts/make_n2_variant_configs.py` | W7 | `MIGRATE_UNDER_PREREG_PARITY` | P | 98 | - |
| C-SCRIPTS_N2_CLOSURE_TABLE_PY | `scripts/n2_closure_table.py` | W7 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 136 | - |
| C-SCRIPTS_SUMMARIZE_BLIND_ENVELOPE_PY | `scripts/summarize_blind_envelope.py` | W7 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 79 | - |
| C-ABEP_SIM_HALL_ENSEMBLE_PY | `abep_sim/hall_ensemble.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 168 | - |
| C-ABEP_SIM_HALL_MAP_PY | `abep_sim/hall_map.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 99 | - |
| C-ABEP_SIM_HALLMAP_REGISTRY_PY | `abep_sim/hallmap_registry.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 572 | - |
| C-DOCS_O4_DISPOSITION_MATRIX | `docs/o4/disposition_matrix/` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 667 | - |
| C-DOCS_O4_JOHNSONLOW_ASSESSMENT | `docs/o4/johnsonlow_assessment/` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 739 | - |
| C-DOCS_V2_QUESTION_A | `docs/v2/question_a/` | W8 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 751 | - |
| C-DOCS_VALIDATION_HALL_TRANSPORT_V2_PREREG | `docs/validation/hall_transport_v2_prereg/` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 72 | - |
| C-SCRIPTS_AUDIT_P5_N2_CAMPAIGN_RECORDS_PY | `scripts/audit_p5_n2_campaign_records.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 61 | - |
| C-SCRIPTS_AUDIT_P5_N2_MEASUREMENTS_PY | `scripts/audit_p5_n2_measurements.py` | W8 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 187 | - |
| C-SCRIPTS_DIGITIZE_P5_BFIELD_PY | `scripts/digitize_p5_bfield.py` | W8 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 59 | - |
| C-SCRIPTS_FORENSICS_P5_N2_V1_EXB_PHYSICS_PY | `scripts/forensics/p5_n2_v1_exb_physics.py` | W8 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 604 | - |
| C-SCRIPTS_FORENSICS_P5_N2_V1_OOD_ATTRIBUTION_PY | `scripts/forensics/p5_n2_v1_ood_attribution.py` | W8 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 994 | - |
| C-SCRIPTS_FORENSICS_P5_N2_V1_SCOREABLE_SUBSET_PY | `scripts/forensics/p5_n2_v1_scoreable_subset.py` | W8 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 1386 | - |
| C-SCRIPTS_FREEZE_P5_N2_DATASET_PY | `scripts/freeze_p5_n2_dataset.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 141 | - |
| C-SCRIPTS_IDENTIFY_P5_TRANSPORT_PY | `scripts/identify_p5_transport.py` | W8 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 256 | - |
| C-SCRIPTS_MAKE_P5_N2_CASES_PY | `scripts/make_p5_n2_cases.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 68 | - |
| C-SCRIPTS_MAKE_P5_N2_LAUNCH_MANIFESTS_PY | `scripts/make_p5_n2_launch_manifests.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 80 | - |
| C-SCRIPTS_MAKE_P5_XENON_CASES_PY | `scripts/make_p5_xenon_cases.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 68 | - |
| C-SCRIPTS_MAKE_VALIDATION_RELEASE_PY | `scripts/make_validation_release.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 106 | - |
| C-SCRIPTS_ORCHESTRATION_LANE_STATUS_PY | `scripts/orchestration/lane_status.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 303 | - |
| C-SCRIPTS_ORCHESTRATION_O4_SCORE_DATASET_PY | `scripts/orchestration/o4_score_dataset.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 51 | - |
| C-SCRIPTS_ORCHESTRATION_TRIGGER_LEDGER_PY | `scripts/orchestration/trigger_ledger.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 167 | - |
| C-SCRIPTS_REPORT_P5_N2_CAMPAIGN_PY | `scripts/report_p5_n2_campaign.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 144 | - |
| C-SCRIPTS_RESCORE_P5_AXIAL_THRUST_PY | `scripts/rescore_p5_axial_thrust.py` | W8 | `MIGRATE_OR_FORMALLY_RETIRE` | P | 141 | - |
| C-SCRIPTS_SCORE_P5_N2_CAMPAIGN_PY | `scripts/score_p5_n2_campaign.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 235 | - |
| C-SCRIPTS_SCORE_P5_N2_FROZEN_PY | `scripts/score_p5_n2_frozen.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 95 | - |
| C-SCRIPTS_SCORE_P5_N2_STAGED_PY | `scripts/score_p5_n2_staged.py` | W8 | `MIGRATE_UNDER_PREREG_PARITY` | P | 169 | - |
| C-ABEP_SIM_DESIGN_ICP_GEOMETRY_SYNTHESIS_PY | `abep_sim/design/icp_geometry_synthesis.py` | W9 | `MIGRATE_UNDER_PREREG_PARITY` | P | 806 | - |
| C-ABEP_SIM_ICP_BENCH_LIB_PY | `abep_sim/icp_bench_lib.py` | W9 | `MIGRATE_UNDER_PREREG_PARITY` | P | 174 | - |
| C-ABEP_SIM_MAGNET_POWER_PY | `abep_sim/magnet_power.py` | W9 | `MIGRATE_UNDER_PREREG_PARITY` | P | 336 | ecr_resonance_field_T and the ecr_magnet component role (historical ECR family) |
| C-ABEP_SIM_THERMAL_LIFE_PY | `abep_sim/thermal_life.py` | W10 | `MIGRATE_UNDER_PREREG_PARITY` | P | 979 | LaB6 / conventional hollow-cathode logic (LaB6Cathode, cathode_life, Xe cathode flow / heater / keeper): richardson_current_density, emitter_temperature*, lab6_evaporation_*, _check_cathode, cathode_keeper / cathode_heater components; rf_source / ecr_source / ecr_magnet checks (historical upstream RF / ECR pre-ionizer source logic) |
| C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3 | `docs/budgets/xe_accounting_a9_v3/` | W11 | `MIGRATE_UNDER_PREREG_PARITY` | P | 1430 | GR: C1-GT-* ground-test Xe lines (GROUND_REFERENCE_ONLY); P-FL-C1 configuration-scope zero |
| C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY | `abep_sim/assessment/design_gates.py` | W12 | `MIGRATE_UNDER_PREREG_PARITY` | P | 506 | - |
| C-ABEP_SIM_PROGRAMME_DESIGN_SYNTHESIS_PY | `abep_sim/programme/design_synthesis.py` | W12 | `MIGRATE_UNDER_PREREG_PARITY` | P | 296 | - |
| C-SCRIPTS_CONFIG_BUILD_CONFIG_PY | `scripts/config/build_config.py` | W13 | `MIGRATE_UNDER_PREREG_PARITY` | P | 980 | - |
| C-DOCS_ARCHITECTURE_FREEZE_CANDIDATE | `docs/architecture/freeze_candidate/` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 3602 | - |
| C-DOCS_ARCHITECTURE_COMPARISON_POWER_BOUNDARY_A9_V2 | `docs/architecture_comparison/power_boundary_a9_v2/` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 1501 | - |
| C-DOCS_DESIGN_SYNTHESIS_F1_INTAKE | `docs/design_synthesis/f1_intake/` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 821 | - |
| C-DOCS_DESIGN_SYNTHESIS_F2_FILTER | `docs/design_synthesis/f2_filter/` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 708 | GR: FC-07 Xe cathode-line getter (out of scope; GROUND_REFERENCE_ONLY) |
| C-DOCS_DESIGN_SYNTHESIS_F3_COMPRESSOR | `docs/design_synthesis/f3_compressor/` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 561 | - |
| C-DOCS_DESIGN_SYNTHESIS_F4_PLENUM | `docs/design_synthesis/f4_plenum/` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 1423 | - |
| C-DOCS_DESIGN_SYNTHESIS_F6_ICP_GEOMETRY | `docs/design_synthesis/f6_icp_geometry/` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 607 | - |
| C-DOCS_DESIGN_SYNTHESIS_F7_F8_OPTIMIZER | `docs/design_synthesis/f7_f8_optimizer/` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 810 | - |
| C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG | `docs/design_synthesis/spacecraft_reference_drag/` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 157 | - |
| C-DOCS_HARDWARE_H1_FREEZE_CANDIDATE | `docs/hardware/h1_freeze_candidate/` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 1875 | - |
| C-SCRIPTS_EVIDENCE_EVIDENCE_ARCHIVE_PY | `scripts/evidence/evidence_archive.py` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 124 | - |
| C-SCRIPTS_EVIDENCE_F1_ARCHIVE_PY | `scripts/evidence/f1_archive.py` | W15a | `MIGRATE_UNDER_PREREG_PARITY` | P | 504 | - |
| C-DOCS_EVIDENCE_HALL_SUSTAINMENT | `docs/evidence/hall_sustainment/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | Q | 1531 | - |
| C-DOCS_EVIDENCE_ICP_NEUTRALIZER | `docs/evidence/icp_neutralizer/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 1222 | - |
| C-DOCS_EVIDENCE_SPUTTER_YIELDS_V1 | `docs/evidence/sputter_yields_v1/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 864 | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_INTEGRATION | `docs/experiments/hall_icp/integration/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 6623 | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_INTEGRATION_M16_V5 | `docs/experiments/hall_icp/integration/m16_v5/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 1135 | GR: row 'cathode' NOT_A_FLIGHT_SUBSYSTEM (C1 ground reference) |
| C-DOCS_EXPERIMENTS_HALL_ICP_P1_ICP_BENCH | `docs/experiments/hall_icp/p1_icp_bench/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 8197 | GR: C1 ground-reference bench items |
| C-DOCS_EXPERIMENTS_HALL_ICP_P2_IMPEDANCE_MAP | `docs/experiments/hall_icp/p2_impedance_map/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 6539 | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_P4_ANODE_MATERIALS | `docs/experiments/hall_icp/p4_anode_materials/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 2800 | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_PREREG_FRAMEWORK | `docs/experiments/hall_icp/prereg_framework/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 1171 | GR: C1 ground-reference arm |
| C-DOCS_EXPERIMENTS_HALL_ICP_PROGRAMME | `docs/experiments/hall_icp/programme/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 882 | GR: C1-REF ground reference |
| C-DOCS_EXPERIMENTS_HALL_ICP_UNCERTAINTY_BUDGET | `docs/experiments/hall_icp/uncertainty_budget/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 1899 | GR: C1 arm (GROUND_REFERENCE_ONLY lab hardware) |
| C-DOCS_EXPERIMENTS_HALL_ICP_VALIDATION_INPUTS | `docs/experiments/hall_icp/validation_inputs/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 945 | GR: C1 ground-reference inputs |
| C-DOCS_EXPERIMENTS_HARDWARE | `docs/experiments/hardware/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | Q | 266 | HW-RF / HW-ECR pre-ionizer hardware entries (historical upstream RF / ECR pre-ionizer source logic) |
| C-DOCS_EXPERIMENTS_INSTRUMENTATION | `docs/experiments/instrumentation/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | Q | 2006 | - |
| C-DOCS_EXPERIMENTS_LIFETIME_AO | `docs/experiments/lifetime_ao/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 2558 | - |
| C-DOCS_EXPERIMENTS_MAGNET_COIL | `docs/experiments/magnet_coil/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 1283 | - |
| C-DOCS_HARDWARE_H2_A9_REVISIONS | `docs/hardware/h2_a9_revisions/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 3493 | GR: C1 ground-reference test-article items |
| C-DOCS_INTERFACES_ICP_NEUTRALIZER | `docs/interfaces/icp_neutralizer/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 1550 | GR: IP-C1 / N-CC ground-reference interface items |
| C-DOCS_PROCUREMENT_RFQ_A9_V3 | `docs/procurement/rfq_a9_v3/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 3334 | GR: HE-L10..12, GAS-L05/06/15, GAS-O03 C1 ground lines (GROUND_ONLY_LAB_EQUIPMENT) |
| C-DOCS_PROCUREMENT_RFQ_A9_V3_GAS_REV1 | `docs/procurement/rfq_a9_v3_gas_rev1/` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | P | 471 | GR: C1 lines GROUND_ONLY_LAB_EQUIPMENT |
| C-SCRIPTS_EXPERIMENTS_S1_READINESS_PY | `scripts/experiments/s1_readiness.py` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | Q | 632 | - |
| C-SCRIPTS_EXPERIMENTS_S1A_READINESS_PY | `scripts/experiments/s1a_readiness.py` | W15b | `MIGRATE_UNDER_PREREG_PARITY` | Q | 774 | - |
| C-DOCS_BID_PACKAGE | `docs/bid/package/` | W15c | `MIGRATE_OR_FORMALLY_RETIRE` | P | 1506 | - |
| C-DOCS_BUDGETS_OWNER_DECISIONS | `docs/budgets/owner_decisions/` | W15c | `MIGRATE_UNDER_PREREG_PARITY` | P | 3844 | build_owner_questions_consolidated.py (v1; never run - it rewrites its xlsx); build_owner_questions_state_v2/v3/v4.py (superseded, HR-12); build_owner_decision_register.py / _sequenced.py / _triage_post_a9.py (A6 / A9 history) |
| C-DOCS_DECISIONS_APPLICATION | `docs/decisions/application/` | W15c | `MIGRATE_UNDER_PREREG_PARITY` | P | 1824 | - |
| C-DOCS_REQUIREMENTS_RFP_OFFICIAL | `docs/requirements/rfp_official/` | W15c | `MIGRATE_UNDER_PREREG_PARITY` | P | 351 | - |
| C-DOCS_REQUIREMENTS_RVM_A9 | `docs/requirements/rvm_a9/` | W15c | `MIGRATE_UNDER_PREREG_PARITY` | P | 4172 | AFI-05 RESOLVED (no flight keeper; RVM-16 basis untouched) |
| C-GITHUB_WORKFLOWS_YML_INLINE_PYTHON | `.github/workflows/*.yml (inline python)` | W16 | `MIGRATE_UNDER_PREREG_PARITY` | P | - | - |
| C-ABEP_SIM_DESIGN_TPMC_BACKEND_PY | `abep_sim/design/tpmc_backend.py` | W16 | `RETIRE_AT_END_STATE_MIGRATION_TOOLING` | P | 313 | - |
| C-SCRIPTS_CI_CHECKS_PY | `scripts/ci_checks.py` | W16 | `MIGRATE_UNDER_PREREG_PARITY` | P | 566 | - |
| C-SCRIPTS_PERF_PROFILE_BASELINE_PY | `scripts/perf/profile_baseline.py` | W16 | `MIGRATE_UNDER_PREREG_PARITY` | P | 1328 | legacy workloads uq_modular_run_uq, archengine_close_architecture, uq6_robust_design and the mission5 / archengine-map driver of mission_run_generic (HR-09) |
| C-SCRIPTS_VERIFY_ABEP_CORE_PY | `scripts/verify_abep_core.py` | W16 | `RETIRE_AT_END_STATE_MIGRATION_TOOLING` | P | 1189 | - |
| C-TESTS | `tests` | W16 | `MIGRATE_UNDER_PREREG_PARITY` | P | 63307 | - |
| C-ABEP_CORE_PYO3_MATURIN_BINDING_LAYER | `abep_core PyO3 / maturin binding layer` | W17 | `RETIRE_AT_END_STATE_MIGRATION_TOOLING` | E | - | - |

## Provisional classifications (RM-OQ-07)

* `abep_sim/plasma_chem.py` -> `HISTORICAL_LEGACY_REGRESSION`: 0-D global source model with unverified Arrhenius rates; every consumer is legacy (plasma_devices 0-D Hall, archengine pre-ionizer sources, system plasma branch, uq6, uq_modular, convergence, golden source_plasma / hall) (NOT in the owner's section-E list: confirmation requested. Hall-discharge chemistry is HallThruster.jl's (rate tables via rate_tables.py, W7); a future ICP-neutralizer global model would be a new governed model, not a port)
* `docs/architecture_comparison/compressor_downselect/` -> `HISTORICAL_LEGACY_REGRESSION`: pivot-era DI-1.4 compressor down-selection (loads the lane-16 feed envelope); superseded for design by F3 synthesis, which cites its findings CD-01 / CD-04 as frozen evidence
* `docs/architecture_comparison/feed_state_closure/` -> `HISTORICAL_LEGACY_REGRESSION`: pivot-era W1 feed-state closure (system.evaluate lane-16 conventions); F1 / F4 / RVM cite its setpoint ladder as frozen evidence; the active feed synthesis is F4
* `docs/evidence/hall_sustainment/` -> `ACTIVE_SELECTED_ARCHITECTURE_PHYSICS`: published Hall-discharge ignition / sustainment evidence (Hall accelerator) (pivot-era Hall-only register; no A9 consumer at the inventory commit)
* `docs/experiments/capability_demo/` -> `HISTORICAL_LEGACY_REGRESSION`: pivot W4 capability-demonstration prep for HW-0 / HW-RF / HW-ECR; no A9 consumer
* `docs/experiments/hardware/` -> `ACTIVE_SELECTED_ARCHITECTURE_PHYSICS`: common-hardware requirements (read by H-1 freeze candidate, A9 prereg / budget / validation inputs and the bid compliance data)
* `docs/experiments/instrumentation/` -> `ACTIVE_SELECTED_ARCHITECTURE_PHYSICS`: instrumentation / metrology definition (a 'verified deliverable' input of the A9 pre-registration framework)
* `scripts/experiments/s1_readiness.py` -> `ACTIVE_SELECTED_ARCHITECTURE_PHYSICS`: S1 readiness gate (conditions read by the A9 pre-registration framework)
* `scripts/experiments/s1a_readiness.py` -> `ACTIVE_SELECTED_ARCHITECTURE_PHYSICS`: S1a engineering-readiness gate (status read by M16 v5 and the A9 framework)

## Dependency findings (runtime imports and dynamic loads, re-derived at the inventory commit)

Class-A components that load a non-class-A component at run time (tests are counted separately below):

* `scripts/ci_checks.py` -> `docs/hardware/h2/h2_6_diagnostics_fixture/build_h2_6_diagnostics_fixture.py` (GROUND_REFERENCE_ONLY): check h2_6_live_sources loads the class-G H2-6 builder (verify_sources): W16 either ports that function as a class-G migration the active CI genuinely requires, or retires the check together with the immutable H2 v1 history (RM-OQ-09)
* `scripts/perf/profile_baseline.py` -> `abep_sim/archengine.py` (HISTORICAL_LEGACY_REGRESSION), `abep_sim/mission5.py` (HISTORICAL_LEGACY_REGRESSION), `abep_sim/programme/closure.py` (HISTORICAL_LEGACY_REGRESSION), `abep_sim/programme/uq_modular.py` (HISTORICAL_LEGACY_REGRESSION), `abep_sim/system.py` (HISTORICAL_LEGACY_REGRESSION), `abep_sim/uq6.py` (HISTORICAL_LEGACY_REGRESSION): legacy workloads (uq_modular, archengine, uq6, mission5 driver, system.evaluate wrapper) are timed for continuity only; abep-perf ports the active workloads, never these modules

Pulled-forward class-A dependencies (the dependency is scheduled in a later wave):

* `abep_sim/atmosphere_orbit.py` (W1) needs `abep_sim/mission_env.py` (W3): pull mission_env::{OMEGA_E, Spacecraft, sso_inclination_deg} into W1 under its own kernel contract
* `abep_sim/icp_bench_lib.py` (W9) needs `docs/experiments/hall_icp/p1_icp_bench/p1_reducer.py` (W15b): experiment_p1_reducer() loads the full P1 reducer (experiment code, 'not used by design computations'); port that reducer with icp_bench_lib in W9 or leave the function out of the W9 contract until W15b

Tests: 162 files. 98 import only class-A modules; they become cargo tests, through captured references, as their components are admitted. 64 import or load a class H / G / F module (audit HR-15 and successors) and stay with the retired Python.

## Cathode-audit AFI items: status at the inventory commit

| item | where | status | migration consequence |
|---|---|---|---|
| AFI-01 | AL-08 C1 cathode-feed valve branch (mass / power v3) | RESOLVED in mass / power v4 / v5 (AL-08 CBE floor 4.929 kg, MEV 5.9148 kg; AFI-01-S1 second series latch kept) | v3 kept as historical evidence (class H); its rule functions are `K-MASS-RULES` |
| AFI-02 | AL-07 6.0 kg PPU analog floor contains C1 heater / keeper / cathode supplies | **OPEN** (`PROVISIONAL_CONSERVATIVE_ANALOG_FLOOR`; AFI-02-RA1) | `docs/budgets/mass_power_a9_v5/` is class F and not ported until re-based; its consumers (F7 / F8, F9, bid package) only read the labelled floor |
| AFI-03 | P3 v2 inherits the H2-5 C-1 heat node | RESOLVED by owner labelling (`NOT_USABLE_FOR_FLIGHT_THERMAL_CLOSURE`; successor model post-bid) | P3 v2 package is class H; its ray kernels already live in `abep_sim/icp_thermal_lib.py` (W5) |
| AFI-04 | golden active reference computed through the LaB6-carded `hall_1stage` closure | owner-classified `HISTORICAL_REGRESSION_COMPATIBILITY` | `golden.py` and `system.py` are class H; `K-GASPATH` is extracted; the active golden comes post-bid (P-02) |
| AFI-05 | RVM-16 flight-keeper wording | RESOLVED (`OWNER_CONFIRMED_CURRENT_ARCHITECTURE_READING`) | RVM builder is class A |

