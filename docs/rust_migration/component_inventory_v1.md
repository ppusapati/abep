# Rust migration — component inventory v1

Governing record: `docs/decisions/OD_2026_10_04_A9_24_RUST_MIGRATION_AND_OPEN_ITEMS_OWNER_DECISIONS.md` items 1, 7, 14. Machine-readable: `component_inventory_v1.json` (the authoritative list; this page is a rendering). Inventoried at `4b5563b643aa`. Programme: `PROGRAMME.md`; order: `migration_order_v1.json`.

## Summary

* Python files: **442** (283 outside `tests/`); **257,604** physical lines (226,221 non-blank non-comment); 195,421 lines outside `tests/`.
* Components: **224** (221 Python-file components + 3 non-`.py` execution paths). ADMITTED: **1** (Kernel 1 TPMC, partial file). Historical/superseded candidates for formal retirement: 17 (proposal).
* Julia-driving Python components: `scripts/identify_p5_transport.py`, `scripts/make_p5_n2_launch_manifests.py`, `tests`.
* Kept non-Python runtime: HallThruster.jl bridge (`hallthruster_bridge/*.jl`), `abep_core/` (Rust).

### By top-level location

| location | components | lines |
|---|---:|---:|
| `abep_sim` | 80 | 33,973 |
| `docs` | 86 | 141,196 |
| `scripts` | 53 | 20,252 |
| `tests` | 2 | 62,183 |

### By wave

| wave | scope | components | lines |
|---|---|---:|---:|
| W0 | TPMC intake kernel (Kernel 1) - ADMITTED | 1 | 475 |
| W1E | Wave-1 enablers pulled forward (constants, frozen-data readers, operating inputs, config loading needed by W1-W5 Rust code) | 5 | 752 |
| W1 | intake / design-state geometry sweep | 5 | 2,952 |
| W2 | compressor design search / gaspath | 7 | 4,838 |
| W3 | mission propagation | 5 | 749 |
| W4 | UQ / Monte Carlo driver | 6 | 1,277 |
| W5 | P3 ray sampling (view factors) and coupled-thermal library | 2 | 5,436 |
| W6 | atmosphere / orbit wrappers | 2 | 2,659 |
| W7 | chemistry / support calculations (incl. rate-table builders and chemistry audits) | 22 | 3,211 |
| W8 | system closure | 11 | 5,249 |
| W9 | power | 5 | 1,704 |
| W10 | thermal | 4 | 1,315 |
| W11 | mass | 1 | 880 |
| W12 | lifetime | 1 | 139 |
| W13 | architecture engine and design synthesis (incl. Hall-map consumers) | 15 | 7,358 |
| W14 | sweep generation and CLI entry points | 2 | 251 |
| W15 | assessment | 4 | 880 |
| W16 | hard gates | 1 | 1,054 |
| W17 | configuration builders / loaders and hash verification | 2 | 1,032 |
| W18 | evidence builders and campaign / scoring / forensics / orchestration scripts | 115 | 149,635 |
| W19 | CI / check / parity / performance utilities and the test infrastructure | 8 | 66,233 |
| W20 | final: retire the abep_core PyO3 binding layer and every remaining Python entry point | 1 | 0 |

W0/W1 both count `abep_sim/intake_tpmc.py` (split component). Non-`.py` paths carry no line count.

### External Python dependencies (number of components)

`numpy` 63, `pandas` 26, `scipy` 15, `pymupdf` 7, `pymsis` 4, `matplotlib` 3, `yaml` 2, `jsonschema` 2, `docx` 1, `openpyxl` 1, `fitz` 1, `PIL` 1, `zstandard` 1, `abep_core` 1, `pytest` 1, `setuptools` 1

Rust equivalents per dependency are in each component's `rust_equivalents_needed`. `pymsis` is build-time only (the frozen NRLMSIS dataset is the runtime path; CLAUDE.md gate 1).

## Components

| id | component | wave | status | activity | files | lines | external deps | RNG/clock |
|---|---|---|---|---|---:|---:|---|---|
| C-ABEP_SIM_PACKAGE_ENTRY_POINTS | `abep_sim/(package entry points)` | W14 | PYTHON_REFERENCE | ACTIVE | 5 | 56 | - | - |
| C-ABEP_SIM_AOCHEM_PY | `abep_sim/aochem.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 113 | - | - |
| C-ABEP_SIM_ARCH_BOUNDARY_PY | `abep_sim/arch_boundary.py` | W8 | PYTHON_REFERENCE | ACTIVE | 1 | 158 | - | - |
| C-ABEP_SIM_ARCH_COMPARE_PY | `abep_sim/arch_compare.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 890 | - | - |
| C-ABEP_SIM_ARCHENGINE_PY | `abep_sim/archengine.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 1,014 | numpy, pandas | - |
| C-ABEP_SIM_ASSESSMENT_ARCH_CONSTRAINTS_PY | `abep_sim/assessment/arch_constraints.py` | W15 | PYTHON_REFERENCE | ACTIVE | 1 | 93 | - | - |
| C-ABEP_SIM_ASSESSMENT_CLOSURE_CHECKS_PY | `abep_sim/assessment/closure_checks.py` | W15 | PYTHON_REFERENCE | ACTIVE | 1 | 209 | - | - |
| C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY | `abep_sim/assessment/design_gates.py` | W15 | PYTHON_REFERENCE | ACTIVE | 1 | 484 | - | - |
| C-ABEP_SIM_ATMOSPHERE_PY | `abep_sim/atmosphere.py` | W1E | PYTHON_REFERENCE | ACTIVE | 1 | 171 | numpy, pandas, pymsis | - |
| C-ABEP_SIM_ATMOSPHERE_ORBIT_PY | `abep_sim/atmosphere_orbit.py` | W6 | PYTHON_REFERENCE | ACTIVE | 1 | 1,479 | numpy, pymsis | RNG |
| C-ABEP_SIM_ATMOSPHERE_ORBIT_V2_PY | `abep_sim/atmosphere_orbit_v2.py` | W6 | PYTHON_REFERENCE | ACTIVE | 1 | 1,180 | numpy | RNG |
| C-ABEP_SIM_BREAKEVEN_PY | `abep_sim/breakeven.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 746 | - | - |
| C-ABEP_SIM_BUS_BOUNDARY_A9_PY | `abep_sim/bus_boundary_a9.py` | W9 | PYTHON_REFERENCE | ACTIVE | 1 | 956 | - | - |
| C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY | `abep_sim/bus_boundary_a9_v2.py` | W9 | PYTHON_REFERENCE | ACTIVE | 1 | 122 | - | - |
| C-ABEP_SIM_CATHODE_INTEGRATION_PY | `abep_sim/cathode_integration.py` | W8 | PYTHON_REFERENCE | ACTIVE | 1 | 1,065 | - | - |
| C-ABEP_SIM_COMPRESSOR_PY | `abep_sim/compressor.py` | W2 | PYTHON_REFERENCE | ACTIVE | 1 | 317 | - | - |
| C-ABEP_SIM_COMPRESSOR_TRANSITIONAL_PY | `abep_sim/compressor_transitional.py` | W2 | PYTHON_REFERENCE | ACTIVE | 1 | 489 | - | - |
| C-ABEP_SIM_CONFIGURATION_PY | `abep_sim/configuration.py` | W1E | PYTHON_REFERENCE | ACTIVE | 1 | 405 | - | - |
| C-ABEP_SIM_CONSTANTS_PY | `abep_sim/constants.py` | W1E | PYTHON_REFERENCE | ACTIVE | 1 | 37 | - | - |
| C-ABEP_SIM_CONVERGENCE_PY | `abep_sim/convergence.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 124 | pandas | -+clock |
| C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY | `abep_sim/design/a9_19_architecture.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 293 | - | - |
| C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY | `abep_sim/design/architecture_optimizer.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 1,237 | numpy | - |
| C-ABEP_SIM_DESIGN_COMPRESSOR_SYNTHESIS_PY | `abep_sim/design/compressor_synthesis.py` | W2 | PYTHON_REFERENCE | ACTIVE | 1 | 995 | - | - |
| C-ABEP_SIM_DESIGN_ENGINEERING_CONSTRAINTS_PY | `abep_sim/design/engineering_constraints.py` | W1E | PYTHON_REFERENCE | ACTIVE | 1 | 88 | - | - |
| C-ABEP_SIM_DESIGN_FILTER_STAGE_PY | `abep_sim/design/filter_stage.py` | W2 | PYTHON_REFERENCE | ACTIVE | 1 | 1,065 | - | - |
| C-ABEP_SIM_DESIGN_ICP_GEOMETRY_SYNTHESIS_PY | `abep_sim/design/icp_geometry_synthesis.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 806 | - | - |
| C-ABEP_SIM_DESIGN_INTAKE_SYNTHESIS_PY | `abep_sim/design/intake_synthesis.py` | W1 | PYTHON_REFERENCE | ACTIVE | 1 | 1,598 | numpy, pandas | - |
| C-ABEP_SIM_DESIGN_PLENUM_FEED_PY | `abep_sim/design/plenum_feed.py` | W2 | PYTHON_REFERENCE | ACTIVE | 1 | 1,511 | numpy, scipy.integrate | - |
| C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY | `abep_sim/design/robust_optimizer.py` | W4 | PYTHON_REFERENCE | ACTIVE | 1 | 451 | numpy | RNG |
| C-ABEP_SIM_DESIGN_TPMC_BACKEND_PY | `abep_sim/design/tpmc_backend.py` | W19 | PYTHON_REFERENCE | ACTIVE | 1 | 313 | numpy | RNG |
| C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY | `abep_sim/design/upstream_a9_13.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 818 | - | - |
| C-ABEP_SIM_EXPLORER_PY | `abep_sim/explorer.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 111 | pandas | - |
| C-ABEP_SIM_GOLDEN_PY | `abep_sim/golden.py` | W19 | PYTHON_REFERENCE | ACTIVE | 1 | 654 | numpy, pandas, scipy | - |
| C-ABEP_SIM_H1_GEOMETRY_PY | `abep_sim/h1_geometry.py` | W8 | PYTHON_REFERENCE | ACTIVE | 1 | 64 | - | - |
| C-ABEP_SIM_HALL1D_PY | `abep_sim/hall1d.py` | W8 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 189 | numpy | - |
| C-ABEP_SIM_HALL_ENSEMBLE_PY | `abep_sim/hall_ensemble.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 168 | - | - |
| C-ABEP_SIM_HALL_MAP_PY | `abep_sim/hall_map.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 99 | numpy, scipy.interpolate | - |
| C-ABEP_SIM_HALLMAP_REGISTRY_PY | `abep_sim/hallmap_registry.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 572 | - | - |
| C-ABEP_SIM_HARD_GATES_PY | `abep_sim/hard_gates.py` | W16 | PYTHON_REFERENCE | ACTIVE | 1 | 1,054 | - | - |
| C-ABEP_SIM_ICP_BENCH_LIB_PY | `abep_sim/icp_bench_lib.py` | W9 | PYTHON_REFERENCE | ACTIVE | 1 | 174 | - | - |
| C-ABEP_SIM_ICP_THERMAL_LIB_PY | `abep_sim/icp_thermal_lib.py` | W5 | PYTHON_REFERENCE | ACTIVE | 1 | 509 | numpy | - |
| C-ABEP_SIM_INTAKE_PY | `abep_sim/intake.py` | W1 | PYTHON_REFERENCE | ACTIVE | 1 | 130 | pandas | - |
| C-ABEP_SIM_INTAKE_SURFACE_V2_SPEC_PY | `abep_sim/intake_surface_v2_spec.py` | W1 | PYTHON_REFERENCE | ACTIVE | 1 | 189 | - | - |
| C-ABEP_SIM_INTAKE_TPMC_PY | `abep_sim/intake_tpmc.py` | W0+W1 | PARTIAL: kernels ADMITTED / remainder PYTHON_REFERENCE | ACTIVE | 1 | 475 | numpy, pandas, scipy.interpolate | RNG |
| C-ABEP_SIM_INTERSTAGE_PY | `abep_sim/interstage.py` | W8 | PYTHON_REFERENCE | ACTIVE | 1 | 1,917 | numpy | - |
| C-ABEP_SIM_LIFE_PY | `abep_sim/life.py` | W12 | PYTHON_REFERENCE | ACTIVE | 1 | 139 | - | - |
| C-ABEP_SIM_MAGNET_POWER_PY | `abep_sim/magnet_power.py` | W9 | PYTHON_REFERENCE | ACTIVE | 1 | 336 | - | - |
| C-ABEP_SIM_MASS_BOM_PY | `abep_sim/mass_bom.py` | W11 | PYTHON_REFERENCE | ACTIVE | 1 | 880 | - | - |
| C-ABEP_SIM_MATERIALS_PY | `abep_sim/materials.py` | W10 | PYTHON_REFERENCE | ACTIVE | 1 | 104 | pandas | - |
| C-ABEP_SIM_MISSION5_PY | `abep_sim/mission5.py` | W3 | PYTHON_REFERENCE | ACTIVE | 1 | 195 | numpy, pandas | - |
| C-ABEP_SIM_MISSION_ENV_PY | `abep_sim/mission_env.py` | W3 | PYTHON_REFERENCE | ACTIVE | 1 | 173 | numpy, pandas | RNG |
| C-ABEP_SIM_MISSION_UQ_PY | `abep_sim/mission_uq.py` | W4 | PYTHON_REFERENCE | ACTIVE | 1 | 120 | numpy, pandas | RNG |
| C-ABEP_SIM_OPERATING_INPUTS_PY | `abep_sim/operating_inputs.py` | W1E | PYTHON_REFERENCE | ACTIVE | 1 | 51 | - | - |
| C-ABEP_SIM_ORBIT_ATM_PY | `abep_sim/orbit_atm.py` | W3 | PYTHON_REFERENCE | ACTIVE | 1 | 100 | numpy, pandas, pymsis | - |
| C-ABEP_SIM_PLASMA_CHEM_PY | `abep_sim/plasma_chem.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 261 | numpy | - |
| C-ABEP_SIM_PLASMA_DEVICES_PY | `abep_sim/plasma_devices.py` | W8 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 553 | numpy | - |
| C-ABEP_SIM_PPU_PY | `abep_sim/ppu.py` | W9 | PYTHON_REFERENCE | ACTIVE | 1 | 116 | - | - |
| C-ABEP_SIM_PROGRAMME_ARCH_COMPARE_PY | `abep_sim/programme/arch_compare.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 78 | - | - |
| C-ABEP_SIM_PROGRAMME_CLOSURE_PY | `abep_sim/programme/closure.py` | W8 | PYTHON_REFERENCE | ACTIVE | 1 | 64 | pandas | - |
| C-ABEP_SIM_PROGRAMME_DESIGN_SYNTHESIS_PY | `abep_sim/programme/design_synthesis.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 291 | numpy | - |
| C-ABEP_SIM_PROGRAMME_SWEEP_PY | `abep_sim/programme/sweep.py` | W14 | PYTHON_REFERENCE | ACTIVE | 1 | 195 | matplotlib, pandas, yaml | - |
| C-ABEP_SIM_PROGRAMME_UQ_MODULAR_PY | `abep_sim/programme/uq_modular.py` | W4 | PYTHON_REFERENCE | ACTIVE | 1 | 57 | numpy, pandas, scipy.stats | RNG |
| C-ABEP_SIM_RADIATION_PY | `abep_sim/radiation.py` | W10 | PYTHON_REFERENCE | ACTIVE | 1 | 94 | - | - |
| C-ABEP_SIM_RATE_TABLES_PY | `abep_sim/rate_tables.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 66 | numpy | - |
| C-ABEP_SIM_RESERVOIR_PY | `abep_sim/reservoir.py` | W2 | PYTHON_REFERENCE | ACTIVE | 1 | 180 | numpy | - |
| C-ABEP_SIM_ROTOR_STRENGTH_PY | `abep_sim/rotor_strength.py` | W2 | PYTHON_REFERENCE | ACTIVE | 1 | 281 | - | - |
| C-ABEP_SIM_SIZING_PY | `abep_sim/sizing.py` | W8 | PYTHON_REFERENCE | ACTIVE | 1 | 92 | pandas | - |
| C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY | `abep_sim/spacecraft_reference_drag.py` | W1 | PYTHON_REFERENCE | ACTIVE | 1 | 560 | - | - |
| C-ABEP_SIM_STATEWISE_PY | `abep_sim/statewise.py` | W3 | PYTHON_REFERENCE | ACTIVE | 1 | 76 | numpy | - |
| C-ABEP_SIM_SYSTEM_PY | `abep_sim/system.py` | W8 | PYTHON_REFERENCE | ACTIVE | 1 | 476 | - | - |
| C-ABEP_SIM_THERMAL_PY | `abep_sim/thermal.py` | W10 | PYTHON_REFERENCE | ACTIVE | 1 | 138 | numpy | - |
| C-ABEP_SIM_THERMAL_LIFE_PY | `abep_sim/thermal_life.py` | W10 | PYTHON_REFERENCE | ACTIVE | 1 | 979 | - | - |
| C-ABEP_SIM_THRESHOLDS_PY | `abep_sim/thresholds.py` | W15 | PYTHON_REFERENCE | ACTIVE | 1 | 94 | numpy, pandas | RNG |
| C-ABEP_SIM_THRUSTER_PY | `abep_sim/thruster.py` | W8 | PYTHON_REFERENCE | ACTIVE | 1 | 211 | - | - |
| C-ABEP_SIM_TRANSIENT_PY | `abep_sim/transient.py` | W3 | PYTHON_REFERENCE | ACTIVE | 1 | 205 | matplotlib, numpy, pandas | - |
| C-ABEP_SIM_UNCERTAINTY_PY | `abep_sim/uncertainty.py` | W4 | PYTHON_REFERENCE | ACTIVE | 1 | 256 | numpy, pandas, scipy.stats | RNG |
| C-ABEP_SIM_UQ6_PY | `abep_sim/uq6.py` | W4 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 293 | numpy, pandas, scipy.stats | RNG |
| C-ABEP_SIM_UQ_MODULAR_PY | `abep_sim/uq_modular.py` | W4 | PYTHON_REFERENCE | ACTIVE | 1 | 100 | numpy | - |
| C-ABEP_SIM_VALIDATION_PY | `abep_sim/validation.py` | W13 | PYTHON_REFERENCE | ACTIVE | 1 | 111 | pandas | - |
| C-ABEP_SIM_XE_LEDGER_PY | `abep_sim/xe_ledger.py` | W8 | PYTHON_REFERENCE | ACTIVE | 1 | 460 | - | - |
| C-DOCS_ARCHITECTURE_FREEZE_CANDIDATE | `docs/architecture/freeze_candidate/` | W18 | PYTHON_REFERENCE | ACTIVE | 6 | 3,555 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_AUX_BUS | `docs/architecture_comparison/aux_bus/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,162 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_CATHODE_INTEGRATION | `docs/architecture_comparison/cathode_integration/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 65 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_COMPRESSOR_DOWNSELECT | `docs/architecture_comparison/compressor_downselect/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,315 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_ELECTRICAL_CLOSURE_TOOLS | `docs/architecture_comparison/electrical_closure/tools/` | W18 | PYTHON_REFERENCE | ACTIVE | 2 | 864 | pymupdf | - |
| C-DOCS_ARCHITECTURE_COMPARISON_EXPERIMENT_PACKAGE | `docs/architecture_comparison/experiment_package/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,766 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_EXPERIMENT_PROTOCOL | `docs/architecture_comparison/experiment_protocol/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 509 | scipy.stats | RNG |
| C-DOCS_ARCHITECTURE_COMPARISON_FAILURE_TREE | `docs/architecture_comparison/failure_tree/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 314 | scipy.constants | - |
| C-DOCS_ARCHITECTURE_COMPARISON_FEED_STATE_CLOSURE | `docs/architecture_comparison/feed_state_closure/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,518 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_HALL_REFERENCE | `docs/architecture_comparison/hall_reference/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 414 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_LOCK1 | `docs/architecture_comparison/lock1/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 1,461 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_MINIMUM_DECISIVE_EXPERIMENT | `docs/architecture_comparison/minimum_decisive_experiment/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 821 | scipy | - |
| C-DOCS_ARCHITECTURE_COMPARISON_OVERLAYS_ECR | `docs/architecture_comparison/overlays/ecr/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 1,994 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_OVERLAYS_HALL_SUSTAINMENT | `docs/architecture_comparison/overlays/hall_sustainment/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 2,248 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_OVERLAYS_RF | `docs/architecture_comparison/overlays/rf/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 1,509 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_POWER_BOUNDARY_TOOLS | `docs/architecture_comparison/power_boundary/tools/` | W18 | PYTHON_REFERENCE | ACTIVE | 2 | 312 | pymupdf | - |
| C-DOCS_ARCHITECTURE_COMPARISON_POWER_BOUNDARY_A9 | `docs/architecture_comparison/power_boundary_a9/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,049 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_POWER_BOUNDARY_A9_V2 | `docs/architecture_comparison/power_boundary_a9_v2/` | W18 | PYTHON_REFERENCE | ACTIVE | 3 | 1,501 | - | - |
| C-DOCS_ARCHITECTURE_COMPARISON_VETO_LAYER | `docs/architecture_comparison/veto_layer/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,478 | - | - |
| C-DOCS_BID_PACKAGE | `docs/bid/package/` | W18 | PYTHON_REFERENCE | ACTIVE | 2 | 713 | docx | - |
| C-DOCS_BUDGETS_MASS_A9 | `docs/budgets/mass_a9/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 1,844 | - | - |
| C-DOCS_BUDGETS_MASS_POWER_A9_V2 | `docs/budgets/mass_power_a9_v2/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 1,767 | - | - |
| C-DOCS_BUDGETS_MASS_POWER_A9_V3 | `docs/budgets/mass_power_a9_v3/` | W18 | PYTHON_REFERENCE | ACTIVE | 2 | 1,421 | - | - |
| C-DOCS_BUDGETS_OWNER_DECISIONS | `docs/budgets/owner_decisions/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 8 | 3,828 | openpyxl | - |
| C-DOCS_BUDGETS_SUBSYSTEM_MATURITY | `docs/budgets/subsystem_maturity/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 2 | 2,745 | - | - |
| C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V2 | `docs/budgets/xe_accounting_a9_v2/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 1,510 | - | - |
| C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3 | `docs/budgets/xe_accounting_a9_v3/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,430 | - | - |
| C-DOCS_BUDGETS_XE_LEDGER | `docs/budgets/xe_ledger/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 1,088 | - | - |
| C-DOCS_BUDGETS_XE_LEDGER_A9 | `docs/budgets/xe_ledger_a9/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,400 | - | - |
| C-DOCS_CHEMISTRY_N2_DOMAIN_EXTENSION_DX5 | `docs/chemistry/n2_domain_extension/dx5/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 509 | - | - |
| C-DOCS_CHEMISTRY_N2_DOMAIN_EXTENSION_DX5_ACQUISITION | `docs/chemistry/n2_domain_extension/dx5/acquisition/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 335 | - | - |
| C-DOCS_CHEMISTRY_N2_DOMAIN_EXTENSION_DX5_CURATION | `docs/chemistry/n2_domain_extension/dx5/curation/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 224 | - | - |
| C-DOCS_CHEMISTRY_O_O2_V0 | `docs/chemistry/o_o2/v0/` | W18 | PYTHON_REFERENCE | ACTIVE | 3 | 710 | fitz, numpy, pymupdf | - |
| C-DOCS_DECISIONS_APPLICATION | `docs/decisions/application/` | W18 | PYTHON_REFERENCE | ACTIVE | 3 | 1,822 | - | - |
| C-DOCS_DESIGN_SYNTHESIS_F1_INTAKE | `docs/design_synthesis/f1_intake/` | W18 | PYTHON_REFERENCE | ACTIVE | 2 | 821 | - | - |
| C-DOCS_DESIGN_SYNTHESIS_F2_FILTER | `docs/design_synthesis/f2_filter/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 708 | - | - |
| C-DOCS_DESIGN_SYNTHESIS_F3_COMPRESSOR | `docs/design_synthesis/f3_compressor/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 561 | - | - |
| C-DOCS_DESIGN_SYNTHESIS_F4_PLENUM | `docs/design_synthesis/f4_plenum/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,423 | numpy | - |
| C-DOCS_DESIGN_SYNTHESIS_F6_ICP_GEOMETRY | `docs/design_synthesis/f6_icp_geometry/` | W18 | PYTHON_REFERENCE | ACTIVE | 2 | 607 | - | - |
| C-DOCS_DESIGN_SYNTHESIS_F7_F8_OPTIMIZER | `docs/design_synthesis/f7_f8_optimizer/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 810 | numpy | RNG |
| C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG | `docs/design_synthesis/spacecraft_reference_drag/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 157 | - | - |
| C-DOCS_EVIDENCE_COMPRESSOR_TRANSITIONAL | `docs/evidence/compressor_transitional/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 494 | - | - |
| C-DOCS_EVIDENCE_ECR_SOURCE | `docs/evidence/ecr_source/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,184 | - | - |
| C-DOCS_EVIDENCE_HALL_SUSTAINMENT | `docs/evidence/hall_sustainment/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,531 | - | - |
| C-DOCS_EVIDENCE_ICP_NEUTRALIZER | `docs/evidence/icp_neutralizer/` | W18 | PYTHON_REFERENCE | ACTIVE | 2 | 1,222 | PIL, numpy | - |
| C-DOCS_EVIDENCE_RF_SOURCE | `docs/evidence/rf_source/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 218 | - | - |
| C-DOCS_EVIDENCE_SPUTTER_YIELDS_V1 | `docs/evidence/sputter_yields_v1/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 864 | - | - |
| C-DOCS_EXPERIMENTS_CAPABILITY_DEMO | `docs/experiments/capability_demo/` | W18 | PYTHON_REFERENCE | ACTIVE | 2 | 2,080 | scipy | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_INTEGRATION | `docs/experiments/hall_icp/integration/` | W18 | PYTHON_REFERENCE | ACTIVE | 3 | 6,623 | - | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_INTEGRATION_M16_V4 | `docs/experiments/hall_icp/integration/m16_v4/` | W18 | PYTHON_REFERENCE | ACTIVE | 4 | 1,332 | - | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_INTEGRATION_M16_V5 | `docs/experiments/hall_icp/integration/m16_v5/` | W18 | PYTHON_REFERENCE | ACTIVE | 2 | 1,133 | - | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_P1_ICP_BENCH | `docs/experiments/hall_icp/p1_icp_bench/` | W18 | PYTHON_REFERENCE | ACTIVE | 7 | 8,189 | jsonschema, numpy | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_P2_IMPEDANCE_MAP | `docs/experiments/hall_icp/p2_impedance_map/` | W18 | PYTHON_REFERENCE | ACTIVE | 6 | 6,531 | - | RNG |
| C-DOCS_EXPERIMENTS_HALL_ICP_P3_COUPLED_THERMAL | `docs/experiments/hall_icp/p3_coupled_thermal/` | W5 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 5 | 4,927 | numpy | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_P4_ANODE_MATERIALS | `docs/experiments/hall_icp/p4_anode_materials/` | W18 | PYTHON_REFERENCE | ACTIVE | 4 | 2,793 | - | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_PREREG_FRAMEWORK | `docs/experiments/hall_icp/prereg_framework/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,171 | - | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_PROGRAMME | `docs/experiments/hall_icp/programme/` | W18 | PYTHON_REFERENCE | ACTIVE | 2 | 882 | - | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_UNCERTAINTY_BUDGET | `docs/experiments/hall_icp/uncertainty_budget/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,899 | scipy.stats | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_VALIDATION_INPUTS | `docs/experiments/hall_icp/validation_inputs/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 945 | - | - |
| C-DOCS_EXPERIMENTS_HARDWARE | `docs/experiments/hardware/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 266 | - | - |
| C-DOCS_EXPERIMENTS_INSTRUMENTATION | `docs/experiments/instrumentation/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 2,006 | - | - |
| C-DOCS_EXPERIMENTS_LIFETIME_AO | `docs/experiments/lifetime_ao/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 2,558 | - | - |
| C-DOCS_EXPERIMENTS_MAGNET_COIL | `docs/experiments/magnet_coil/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,283 | - | - |
| C-DOCS_EXPERIMENTS_PHASE1_PREREG_FRAMEWORK | `docs/experiments/phase1_prereg_framework/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 1,702 | - | - |
| C-DOCS_HARDWARE_H1_FREEZE_CANDIDATE | `docs/hardware/h1_freeze_candidate/` | W18 | PYTHON_REFERENCE | ACTIVE | 3 | 1,868 | - | - |
| C-DOCS_HARDWARE_H2_H2_1_HALL_CHAMBER_MAGNET | `docs/hardware/h2/h2_1_hall_chamber_magnet/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,649 | - | - |
| C-DOCS_HARDWARE_H2_H2_2_CATHODE_INTEGRATION | `docs/hardware/h2/h2_2_cathode_integration/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,775 | - | - |
| C-DOCS_HARDWARE_H2_H2_3_GAS_PATH_PLENUM | `docs/hardware/h2/h2_3_gas_path_plenum/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 2,147 | - | - |
| C-DOCS_HARDWARE_H2_H2_4_PPU_BUS | `docs/hardware/h2/h2_4_ppu_bus/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,663 | - | - |
| C-DOCS_HARDWARE_H2_H2_5_THERMAL_NETWORK | `docs/hardware/h2/h2_5_thermal_network/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,434 | numpy | RNG |
| C-DOCS_HARDWARE_H2_H2_6_DIAGNOSTICS_FIXTURE | `docs/hardware/h2/h2_6_diagnostics_fixture/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 2,286 | - | - |
| C-DOCS_HARDWARE_H2_H2_7_MECHANICAL_BOM | `docs/hardware/h2/h2_7_mechanical_bom/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,548 | - | - |
| C-DOCS_HARDWARE_H2_A9_REVISIONS | `docs/hardware/h2_a9_revisions/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 3,493 | numpy | RNG |
| C-DOCS_INTERFACES_ICP_NEUTRALIZER | `docs/interfaces/icp_neutralizer/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,550 | - | - |
| C-DOCS_INTERFACES_PREIONIZER_MODULE | `docs/interfaces/preionizer_module/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 1,439 | - | - |
| C-DOCS_MILESTONES_BUNDLE1 | `docs/milestones/bundle1/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 2,165 | - | - |
| C-DOCS_O4_DISPOSITION_MATRIX | `docs/o4/disposition_matrix/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 667 | - | - |
| C-DOCS_O4_JOHNSONLOW_ASSESSMENT | `docs/o4/johnsonlow_assessment/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 739 | - | - |
| C-DOCS_PROCUREMENT_RFQ_A9 | `docs/procurement/rfq_a9/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 1,919 | - | - |
| C-DOCS_PROCUREMENT_RFQ_A9_V2 | `docs/procurement/rfq_a9_v2/` | W18 | PYTHON_REFERENCE | HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE | 1 | 3,707 | - | - |
| C-DOCS_PROCUREMENT_RFQ_A9_V3 | `docs/procurement/rfq_a9_v3/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 3,108 | - | - |
| C-DOCS_REQUIREMENTS_RFP_OFFICIAL | `docs/requirements/rfp_official/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 351 | - | - |
| C-DOCS_REQUIREMENTS_RVM_A9 | `docs/requirements/rvm_a9/` | W18 | PYTHON_REFERENCE | ACTIVE | 7 | 4,040 | - | - |
| C-DOCS_TRACEABILITY | `docs/traceability/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 704 | - | - |
| C-DOCS_V2_QUESTION_A | `docs/v2/question_a/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 751 | - | - |
| C-DOCS_VALIDATION_HALL_TRANSPORT_V2_PREREG | `docs/validation/hall_transport_v2_prereg/` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 72 | - | - |
| C-SCRIPTS_ARCHITECTURE_BUILD_BREAKEVEN_SURFACES_PY | `scripts/architecture/build_breakeven_surfaces.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 790 | matplotlib, numpy | - |
| C-SCRIPTS_ARCHITECTURE_BUILD_COMPARISON_GRID_PY | `scripts/architecture/build_comparison_grid.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,017 | - | - |
| C-SCRIPTS_ARCHITECTURE_BUILD_DECISION_DOSSIER_PY | `scripts/architecture/build_decision_dossier.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,036 | - | -+clock |
| C-SCRIPTS_ARCHITECTURE_BUILD_FEED_ENVELOPE_PY | `scripts/architecture/build_feed_envelope.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,668 | pandas | - |
| C-SCRIPTS_ARCHITECTURE_SCALING_SIMILARITY_PY | `scripts/architecture/scaling_similarity.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,759 | - | - |
| C-SCRIPTS_AUDIT_N2_COMPLETENESS_FINAL_PY | `scripts/audit_n2_completeness_final.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 210 | numpy | - |
| C-SCRIPTS_AUDIT_N2_DISSOCIATIVE_IONIZATION_PY | `scripts/audit_n2_dissociative_ionization.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 126 | numpy | - |
| C-SCRIPTS_AUDIT_N2_VIBRATIONAL_EXCITATION_PY | `scripts/audit_n2_vibrational_excitation.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 183 | numpy | - |
| C-SCRIPTS_AUDIT_P5_N2_CAMPAIGN_RECORDS_PY | `scripts/audit_p5_n2_campaign_records.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 61 | - | - |
| C-SCRIPTS_AUDIT_P5_N2_MEASUREMENTS_PY | `scripts/audit_p5_n2_measurements.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 187 | numpy, pymupdf, scipy | - |
| C-SCRIPTS_BUILD_MULTIPLY_CHARGED_TABLES_PY | `scripts/build_multiply_charged_tables.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 156 | numpy | - |
| C-SCRIPTS_BUILD_N2_DISSOCIATION_TABLE_PY | `scripts/build_n2_dissociation_table.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 65 | numpy | - |
| C-SCRIPTS_BUILD_N2_DISSOCIATIVE_IONIZATION_TABLE_PY | `scripts/build_n2_dissociative_ionization_table.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 97 | numpy | - |
| C-SCRIPTS_BUILD_N2_ELASTIC_SONG2023_TABLE_PY | `scripts/build_n2_elastic_song2023_table.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 78 | numpy | - |
| C-SCRIPTS_BUILD_N2_ELECTRONIC_EXCITATION_TABLES_PY | `scripts/build_n2_electronic_excitation_tables.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 147 | numpy | - |
| C-SCRIPTS_BUILD_N2_IONIZATION_SONG2023_TABLE_PY | `scripts/build_n2_ionization_song2023_table.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 69 | numpy | - |
| C-SCRIPTS_BUILD_N2_ROTATIONAL_TABLES_PY | `scripts/build_n2_rotational_tables.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 42 | numpy | - |
| C-SCRIPTS_BUILD_N2_TO_N_Z2PLUS_TABLE_PY | `scripts/build_n2_to_n_z2plus_table.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 62 | numpy | - |
| C-SCRIPTS_BUILD_N2_VIBRATIONAL_TABLES_PY | `scripts/build_n2_vibrational_tables.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 74 | numpy | - |
| C-SCRIPTS_BUILD_N_ELASTIC_TABLES_PY | `scripts/build_n_elastic_tables.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 125 | numpy, pymupdf | - |
| C-SCRIPTS_BUILD_N_IONIZATION_TABLE_PY | `scripts/build_n_ionization_table.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 66 | numpy | - |
| C-SCRIPTS_BUILD_N_Z1PLUS_TO_Z2PLUS_TABLE_PY | `scripts/build_n_z1plus_to_z2plus_table.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 66 | numpy | - |
| C-SCRIPTS_CHEMISTRY_N2_DOMAIN_EXTENSION_REQUIREMENTS_PY | `scripts/chemistry/n2_domain_extension_requirements.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 892 | numpy, pymupdf | - |
| C-SCRIPTS_CI_CHECKS_PY | `scripts/ci_checks.py` | W19 | PYTHON_REFERENCE | ACTIVE | 1 | 566 | - | - |
| C-SCRIPTS_CONFIG_BUILD_CONFIG_PY | `scripts/config/build_config.py` | W17 | PYTHON_REFERENCE | ACTIVE | 1 | 871 | - | - |
| C-SCRIPTS_CONFIG_BUILD_RESULT_SCHEMAS_PY | `scripts/config/build_result_schemas.py` | W17 | PYTHON_REFERENCE | ACTIVE | 1 | 161 | - | - |
| C-SCRIPTS_DIGITIZE_P5_BFIELD_PY | `scripts/digitize_p5_bfield.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 59 | numpy, pymupdf | - |
| C-SCRIPTS_EVIDENCE_EVIDENCE_ARCHIVE_PY | `scripts/evidence/evidence_archive.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 124 | zstandard | - |
| C-SCRIPTS_EVIDENCE_F1_ARCHIVE_PY | `scripts/evidence/f1_archive.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 251 | - | - |
| C-SCRIPTS_EXPERIMENTS_S1_READINESS_PY | `scripts/experiments/s1_readiness.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 632 | - | - |
| C-SCRIPTS_EXPERIMENTS_S1A_READINESS_PY | `scripts/experiments/s1a_readiness.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 774 | - | - |
| C-SCRIPTS_FORENSICS_P5_N2_V1_EXB_PHYSICS_PY | `scripts/forensics/p5_n2_v1_exb_physics.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 604 | - | - |
| C-SCRIPTS_FORENSICS_P5_N2_V1_OOD_ATTRIBUTION_PY | `scripts/forensics/p5_n2_v1_ood_attribution.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 994 | - | - |
| C-SCRIPTS_FORENSICS_P5_N2_V1_SCOREABLE_SUBSET_PY | `scripts/forensics/p5_n2_v1_scoreable_subset.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 1,386 | - | - |
| C-SCRIPTS_FREEZE_P5_N2_DATASET_PY | `scripts/freeze_p5_n2_dataset.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 141 | - | -+clock |
| C-SCRIPTS_IDENTIFY_P5_TRANSPORT_PY | `scripts/identify_p5_transport.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 256 | - | - |
| C-SCRIPTS_MAKE_N2_VARIANT_CONFIGS_PY | `scripts/make_n2_variant_configs.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 98 | - | - |
| C-SCRIPTS_MAKE_P5_N2_CASES_PY | `scripts/make_p5_n2_cases.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 68 | - | - |
| C-SCRIPTS_MAKE_P5_N2_LAUNCH_MANIFESTS_PY | `scripts/make_p5_n2_launch_manifests.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 80 | - | - |
| C-SCRIPTS_MAKE_P5_XENON_CASES_PY | `scripts/make_p5_xenon_cases.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 68 | - | - |
| C-SCRIPTS_MAKE_VALIDATION_RELEASE_PY | `scripts/make_validation_release.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 106 | - | - |
| C-SCRIPTS_N2_CLOSURE_TABLE_PY | `scripts/n2_closure_table.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 136 | - | - |
| C-SCRIPTS_ORCHESTRATION_LANE_STATUS_PY | `scripts/orchestration/lane_status.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 303 | - | -+clock |
| C-SCRIPTS_ORCHESTRATION_O4_SCORE_DATASET_PY | `scripts/orchestration/o4_score_dataset.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 51 | - | - |
| C-SCRIPTS_ORCHESTRATION_TRIGGER_LEDGER_PY | `scripts/orchestration/trigger_ledger.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 167 | - | -+clock |
| C-SCRIPTS_PERF_PROFILE_BASELINE_PY | `scripts/perf/profile_baseline.py` | W19 | PYTHON_REFERENCE | ACTIVE | 1 | 1,328 | numpy, pandas, scipy | RNG |
| C-SCRIPTS_REPORT_P5_N2_CAMPAIGN_PY | `scripts/report_p5_n2_campaign.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 144 | - | - |
| C-SCRIPTS_RESCORE_P5_AXIAL_THRUST_PY | `scripts/rescore_p5_axial_thrust.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 141 | - | - |
| C-SCRIPTS_SCORE_P5_N2_CAMPAIGN_PY | `scripts/score_p5_n2_campaign.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 235 | - | - |
| C-SCRIPTS_SCORE_P5_N2_FROZEN_PY | `scripts/score_p5_n2_frozen.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 95 | - | -+clock |
| C-SCRIPTS_SCORE_P5_N2_STAGED_PY | `scripts/score_p5_n2_staged.py` | W18 | PYTHON_REFERENCE | ACTIVE | 1 | 169 | - | -+clock |
| C-SCRIPTS_SUMMARIZE_BLIND_ENVELOPE_PY | `scripts/summarize_blind_envelope.py` | W7 | PYTHON_REFERENCE | ACTIVE | 1 | 79 | - | - |
| C-SCRIPTS_VERIFY_ABEP_CORE_PY | `scripts/verify_abep_core.py` | W19 | PYTHON_REFERENCE | ACTIVE | 1 | 1,189 | numpy, pandas | RNG+clock |
| C-TESTS | `tests` | W19 | PYTHON_REFERENCE | ACTIVE | 157 | 62,019 | abep_core, jsonschema, numpy, pandas, pymsis, pytest, scipy.stats, setuptools, yaml | RNG+clock |
| C-TESTS_FIXTURES | `tests/fixtures` | W19 | PYTHON_REFERENCE | ACTIVE | 2 | 164 | numpy | - |
| C-GITHUB_WORKFLOWS_YML_INLINE_PYTHON | .github/workflows/*.yml (inline python) | W19 | PYTHON_REFERENCE | ACTIVE | 3 | - | - | - |
| C-DOCS_ORCHESTRATION_RUNNER_SCRIPTS_SH_INLINE_PYTHON | docs/orchestration/runner_scripts/*.sh (inline python) | W18 | PYTHON_REFERENCE | ACTIVE | 12 | - | - | - |
| C-ABEP_CORE_PYO3_MATURIN_BINDING_LAYER | abep_core PyO3 / maturin binding layer | W20 | RUST_BINDING_TO_RETIRE | ACTIVE | 2 | - | - | - |

Per-component role, internal dependencies, Rust equivalents, determinism notes and parity-reference candidates: see the JSON. The inventory is mechanical; each parity contract re-verifies its component's facts at the reference commit.

