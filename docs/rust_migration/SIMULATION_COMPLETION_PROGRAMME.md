# ABEP simulation completion programme v1 (A9.28)

**Status: `PROPOSED_PLAN_V3_FOR_OWNER_REVIEW`.** Docs / plan only. It changes no Python, Rust, CI workflow,
configuration, frozen data or number. Machine-readable companion (authoritative):
`simulation_completion_programme_v1.json`. Migration rules, classes and lifecycle: `PROGRAMME.md` / `programme_v3.json`.
Component schedule: `migration_order_v3.json`. Inventory: `component_inventory_v3.json`.

Governing record: `docs/decisions/OD_2026_10_05_A9_28_RUST_PLAN_RULINGS_AND_SIMULATION_COMPLETION_DIRECTIVE.md`, read in
full (message 1 = Rust plan v2 rulings; message 2 = simulation completion directive). Also read: A9.24, A9.25, A9.27 and
the cathode-path audit `docs/audits/a9_24_cathode_path_audit_v1.md`.

**Priority (A9.28 message 2).** Complete the ABEP simulator, then integrate it cleanly into main. RFP-form / Part-IV
work is stopped unless the owner returns to it.

---

## 1. Protected bid record and the integration line

**Protected bid record** (message 2 sec. 1). It is immutable historical evidence:

| role | SHA |
|---|---|
| technical source | `5eee4b8c82a9403b6bb82d5f8d324526f5d6399b` |
| package / freeze record | `2de86abefacbd36ce7516d3cf017f6258bd7e7a2` |

* The package lineage is `b5849af` (the A9.25 message 8 package / freeze-record commit, named again by A9.27), then
  `2de86ab` (the A9.27 package-level post-source bid text). Both pin `5eee4b8`. A9.28 names `2de86ab` as the
  package / freeze record.
* Later simulation development never rewrites these records. It never makes a later commit appear to have been the
  submitted technical source. `bid_source_guard` (SC-WP-12) enforces this.

**Integration branch: `integration/simulation-complete`** (message 2 secs. 3, 5, 16, 17).

* It is based on the development line `claude/nifty-ramanujan-w68f9z` at `dcab602`.
* main's six checkpoint commits #31-#36 (`15981ae`, `7caaf13`, `20f14d8`, `eef8b85`, `98fbbb9`, `b1e5b76`) were
  reconciled into it once. The record is `docs/integration/main_reconciliation_2026_10_05.json` (sha256 `2eae9810…`):
  * 53 conflicts, every one resolved to the later governed development side on per-file evidence;
  * main's blobs were all earlier development-line states, and there is no main-unique content;
  * main's commits are preserved as merge parents.
* This plan revision is based on `lane-rustplan-v2` at `e01716d`, merged with the integration branch at `ea1a598`
  (no conflicts). After owner review it merges into `integration/simulation-complete`, **not** into main.
* main stays untouched until the complete simulator is admitted. There are no incremental merges into main.
* The integration branch is kept up to date with main, so another large divergence is avoided.
* The final step is a **new** PR `integration/simulation-complete → main`. PR #37 is not reused. PR #37 is eventually
  closed as `SUPERSEDED_BY_SIMULATION_INTEGRATION`, once the integration branch holds all governed history.

## 2. Active architecture (message 2 sec. 4)

The only active flight simulation architecture is **`hall_icp_neutralizer`**
(`config/architecture/hall_icp_neutralizer_v1.json`). The flight topology is:

rarefied atmospheric intake → filter → compressor → plenum / feed → Hall accelerator + downstream 13.56 MHz RF/ICP
electron source / neutralizer.

* Propellant modes: `AIR_PRIMARY`, `XE_CONTINGENCY`.
* Flight conventional hollow cathode: `NONE`. C1: `GROUND_REFERENCE_ONLY`.
* Broad architecture-family selection is not reopened. Obsolete families are not ported because Python holds them.
  Historical LaB6 / hollow-cathode functionality is not ported into active Rust.

## 3. What "simulation complete" means

**Software completion** (message 2 sec. 6) is an **admitted** active implementation of every applicable
selected-architecture layer. These are the seventeen work packages of § 5.

**Hardware evidence is not software** (message 2 sec. 14).

* The software is not held back for unavailable hardware evidence, and that evidence is never fabricated.
* Where determining evidence is absent, the complete simulator **fails closed**: `NOT_EVALUATED`,
  `INCOMPLETE_EVIDENCE`, `OUT_OF_DOMAIN` or `MODEL_ERROR`.
* "Software complete" never turns those gates into PASS. Each WP lists its fail-closed gates.

**Methods** (message 1 sec. 5; message 2 secs. 8, 9, 10):

| method | path |
|---|---|
| `EXISTING_PHYSICS_PARITY` | Python reference → preregistered parity contract (own commit, before any comparison) → Rust → parity / conservation / domain / determinism tests → admission → Python removed from the active execution path. The Python reference is never modified to make Rust pass. |
| `NEW_PHYSICS` | preregistered model (nodes, equations, boundaries, assumptions, domains, conservation, analytic limiting cases, evidence plan) → Rust → analytic and independent-evidence verification → admission. No synthetic Python reference is created. A Python scratch calculation may only be an independent, non-authoritative cross-check. |
| `NEW_INFRASTRUCTURE_ACCEPTANCE` | new infrastructure with no Python behaviour to reproduce (the `abep` CLI, the active golden, the zero-Python CI runner, clean install): preregistered acceptance checks → Rust → acceptance run → admission. It never relabels a gate status. |
| `AUDIT_THEN_EXTRACT_ONLY_IF_NEEDED` | a class-H legacy module (`plasma_chem.py`; the class-H `life.py` reliability functions). Its architecture-independent kernels are audited first. Only those the selected architecture needs are extracted, each with provenance, applicability domain and preregistered parity / verification. The module itself is never ported. |

Admission is software admission. A `NEW_PHYSICS` model is admitted as *verified*. Its outputs carry
`validation_status = NOT_VALIDATED` until measured evidence exists.

## 4. Order of the work packages

The ordering key (A9.27 sec. 4; A9.28 message 1 sec. 7, message 2 sec. 15) is:

1. architecture relevance **first**;
2. evidence / admission eligibility **second**;
3. `PRE_RUST_REFERENCE_BASELINE` measured runtime **third**.

The baseline only orders active retained components. These are retired, not ported, however slow they are:

* `uq_modular_run_uq`: 94.86 s, rank 1;
* `archengine_close_architecture`: 16.28 s, rank 3;
* `uq6_robust_design`: 1.26 s, rank 7.

The intake response surface (88.98 s, rank 2) is the largest active runtime target.

The order below is the **layer admission order**. It respects every WP dependency, and the generator checks this. An
element can be admitted before its WP. For example, the SC-WP-09 propagation element (wave W3, PRE_RUST rank 5) is
admitted as soon as its contract passes. Component waves (`migration_order_v3.json`) keep the item-7 scheduling.

| rank | WP | layer | methods | target crates | depends on (SC-WP-) | components | Python lines to migrate / migrate-or-retire | indicative engineer-weeks | size |
|---:|---|---|---|---|---|---:|---|---|---|
| 1 | SC-WP-12 | configuration / hash / provenance | parity + new infrastructure | abep-types, abep-provenance, abep-config, abep-data | – | 7 | 2,029 / 0 | 5.4–10.8 | M |
| 2 | SC-WP-01 | environment | parity | abep-data, abep-atmos | 12 | 3 | 2,830 / 0 | 4.7–9.4 | M |
| 3 | SC-WP-02 | upstream | parity | abep-intake, abep-gaspath | 12, 01 | 11 | 7,559 / 0 | 12.6–25.2 | L |
| 4 | SC-WP-03 | propulsion | parity + audit (+ new physics only if RM-OQ-12) | abep-julia-bridge, abep-hall, abep-chem, abep-icp | 12, 01, 02 | 55 | 15,676 / 6,563 | 32.1–64.3 | XL |
| 5 | SC-WP-04 | spacecraft interaction | parity | abep-intake, abep-mission | 12, 01, 02, 03 | 3 | 793 / 0 | 1.3–2.6 | S |
| 6 | SC-WP-05 | electrical | parity | abep-subsystems::power, abep-icp | 12, 02, 03 | 6 | 10,737 / 0 | 17.9–35.8 | L |
| 7 | SC-WP-07 | mass | parity (value status preserved) | abep-subsystems::mass | 12, 03, 05 | 2 | 2,304 / 0 | 3.8–7.7 | M |
| 8 | SC-WP-06 | thermal | **new physics** + parity of retained kernels | abep-subsystems::thermal | 12, 02, 03, 05 | 2 | 1,488 / 0 | 8.5–17.0 | L |
| 9 | SC-WP-08 | materials / life | parity + audit | abep-subsystems::life, ::materials | 12, 01, 02, 03, 06 | 4 | 6,335 / 0 | 12.6–25.1 | L |
| 10 | SC-WP-09 | mission | parity + **new physics** | abep-mission | 12, 01, 03, 04, 05, 07, 08 | 1 | 173 / 0 | 3.3–6.6 | M |
| 11 | SC-WP-10 | uncertainty / design | parity | abep-design, abep-uq, abep-rng | 12, 01–09 | 3 | 2,011 / 0 | 3.4–6.7 | M |
| 12 | SC-WP-11 | assessment | parity | abep-assess | 12, 03–10 | 3 | 5,029 / 0 | 8.4–16.8 | L |
| 13 | SC-WP-14 | active builders / evidence (incl. ground-test tooling) | parity | abep-evidence, abep-groundtest | 01–12 | 31 | 45,186 / 4,555 | 75.3–150.6 | XL |
| 14 | SC-WP-13 | deterministic CLI | new infrastructure | abep-cli | 12 | 0 | – | 2.0–4.0 | S |
| 15 | SC-WP-15 | active canonical golden | new infrastructure + comparator parity | abep-parity, abep-cli | 01–13 | 0 | – | 2.0–3.0 | S |
| 16 | SC-WP-16 | CI | parity + new infrastructure | abep-cli, abep-parity, abep-perf | 12, 13 | 7 | 1,894 / 0 | 6.2–11.3 | M |
| 17 | SC-WP-17 | clean-install reproducibility | new infrastructure | abep-cli | 12, 13, 15, 16 | 0 | – | 1.0–2.0 | S |

**About the size column.** It is an indicative planning heuristic, not evidence: 300–600 migrated Python lines per
engineer-week, covering the contract, the Rust code, the tests and the report, plus the stated new-physics or
infrastructure weeks. Three things are left out of the range:

* `MIGRATE_OR_FORMALLY_RETIRE` builders, which may simply be retired;
* kernels inside class-H modules;
* the 63,307 test lines, which are replaced by contract tests and captured references, not ported line by line.

**Coverage.** Every class-A and class-T component of `component_inventory_v3.json` (132 + 6 = 138) belongs to exactly
one WP. Classes G and H belong to no WP; their kernels are referenced by the WP that needs them.

## 5. Work packages

Every WP below is spelled out in full in the JSON:

* every Python file / function, with its symbol verified;
* the data pins;
* the inventory components;
* the gates, the admission criteria and the excluded legacy paths.

Each "Python reference" line names the principal files / functions. The generator verified **388 references, all
present** at this revision (paths exist; `::Symbol` is a top-level def / class / assignment of the `.py` file, or a
`function` of the `.jl` file).

### SC-WP-01 Environment: atmosphere, orbit / design states (rank 2)

* **Python reference.**
  * `abep_sim/atmosphere.py` (`atmosphere`, `_interp_frozen`, `_frozen`).
  * `abep_sim/atmosphere_orbit.py` (`load`, `state`, `orbit_states`, `design_states_v2`, `load_design_states`,
    `Domain`, `check`).
  * `abep_sim/atmosphere_orbit_v2.py` (`HWM14Runner`, `wind`, `relative_flow`, `flow_state`).
  * `abep_sim/design/intake_synthesis.py::load_design_state_set`.
  * The `mission_env` constants kernel (`Spacecraft`, `sso_inclination_deg`), pulled forward.
  * Frozen data: `atmosphere_msis21_v1.*`, `atmosphere_msis21_orbit_v1*`, and the 196-state set v2 (sha256 `60073e21…`).
* **Relevance.** Every layer consumes the frozen atmosphere and the 196 design states.
* **Method.** `EXISTING_PHYSICS_PARITY`. ULP-bounded fields; exact statuses / state ids. HWM14 stays a Fortran
  executable launched by Rust.
* **Fail closed.**
  * `OUT_OF_DOMAIN` outside the frozen grid.
  * `MODEL_ERROR` on missing data or a hash mismatch.
  * `MODEL_ERROR` when HWM14 is unavailable. There is no silent zero-wind fallback.
* **Admission.**
  * Contracts reach PARITY_PASS.
  * Frozen-data hashes equal `config/MANIFEST.json`.
  * Domain / error parity holds, and outputs are deterministic.
  * golden_v2 `atmosphere` is an optional development vector only; it is historical, not an end-state case.

### SC-WP-02 Upstream: TPMC intake, filter, compressor, plenum, feed dynamics (rank 3)

* **Python reference.**
  * Intake:
    * `abep_sim/intake_tpmc.py`. Kernel 1 (`trace_channel` …) is already ADMITTED. The response layer is
      `intake_response`, `response_surface`, `IntakeSurface`.
    * `abep_sim/intake.py` (`collection`, `compress`).
    * `abep_sim/design/intake_synthesis.py` (`Evaluator`, `run_study`, `candidate_state_metrics`, `pareto_filter`).
  * Filter: `abep_sim/design/filter_stage.py` (`FilterStage`, `cole_transmission_probability`,
    `perforated_plate_alpha`).
  * Compressor:
    * `abep_sim/compressor.py::DragCompressor`;
    * `abep_sim/design/compressor_synthesis.py` (`evaluate_design`, `synthesize`, `stage_trace`);
    * `abep_sim/rotor_strength.py::qualify_rotor`.
  * Plenum: `abep_sim/design/plenum_feed.py` (`Plenum`, `Chain`, `steady_operating_point`, `steady_sweep`) and
    `abep_sim/reservoir.py`.
  * Feed dynamics:
    * `plenum_feed` (`TransientRun`, `Controller`, `event_sequence`, `ripple_transfer`, `orbit_simulated`);
    * `reservoir.startup_transient`;
    * `abep_sim/design/upstream_a9_13.py` (`SetpointSchedule`, `FixedSetpoint`, `classify_pressure_target`).
* **Relevance.** This is the `AIR_PRIMARY` flight path. Intake response-surface work is a genuine active target (A9.27
  sec. 4; A9.28 msg 1 sec. 7).
* **Method.** `EXISTING_PHYSICS_PARITY`.
  * Parity classes: STATISTICAL / EXACT_STREAM for TPMC-driven outputs, SOLVER_TOLERANCE for the plenum and
    transients.
  * `K-GASPATH` (the gas-path subset of `system.physics_closure`) is extracted **only if an active consumer is
    confirmed**. This is a v3 finding: its golden_v2 consumers are historical. If it is extracted, it pulls
    `aochem.inlet_composition` forward under its own kernel contract.
  * The compressor down-select is HISTORICAL. The feed-state closure is ground-test only.
* **Fail closed.**
  * `MODEL_ERROR`: non-converged TPMC / gas path.
  * `NOT_EVALUATED`:
    * the compressor load (ICD row 22);
    * code-default F3 coefficients, or an unregistered rotor basis;
    * the unregistered intake surface v2;
    * the robust upstream set, which stays EMPTY and visible.
  * `INCOMPLETE_EVIDENCE`: filter species transport (TBD).
  * `OUT_OF_DOMAIN`: a feed state outside the registered pressure domain.
* **Admission.**
  * Contracts reach PARITY_PASS.
  * The source mass balance closes exactly (rule 4).
  * Domain / error parity holds, including the HC-09 Option-1 filter. It is read from the frozen engineering
    configuration, never parsed from the RFP.
  * The RM-R20 harness-independence check passes for K-GASPATH.

### SC-WP-03 Propulsion: gas state, RF/ICP, HallThruster.jl bridge, Hall acceleration, neutralization, coupled thrust / flow (rank 4)

* **Python reference.**
  * Gas state:
    * `upstream_a9_13` (`flight_feed_requirement`, `pressure_domain_status`, `flow_gap_record`);
    * `plenum_feed.IntakeState`;
    * `a9_19_architecture` (`classify_gas`, `check_supply_mode`, `propellant_path_roles`);
    * `xe_accounting_a9_v3::xe_system_capability`.
  * RF/ICP:
    * `abep_sim/design/icp_geometry_synthesis.py` (`evaluate`, `capacity_objective`, `rf_power_objective`,
      `plume_objective`, `collector_objective`, `geometric_screening`, `pareto_filter`);
    * `abep_sim/icp_bench_lib.py`;
    * P1 `p1_reducer.py` (`derive_rf`, `classify_stable_region`, `reduce`).
  * Bridge:
    * `hall_map.py` (`HallMap`, `pinned_commit`, `missing_fields`);
    * `hall_ensemble.py` (`require_admitted`, `screening_ids`, `_check_o4`);
    * `hallmap_registry.py` (`verify`, `register`, `validate_record`);
    * `rate_tables.py`;
    * `scripts/make_p5_n2_launch_manifests.py`, `scripts/identify_p5_transport.py`;
    * `hallthruster_bridge/bridge_lib.jl::check_pin`, `run_cases.jl`, `identify_worker.jl`,
      `campaign/p5_n2_campaign.jl`, `checks/chemistry_validity_check.jl`, `checks/wall_flux_consistency.jl`.
  * Hall acceleration: `architecture_optimizer` (`hall_admissibility`, `hall_response_status`, `hall_gated_thrust`) and
    `h1_geometry.geometric_admissibility`.
  * Neutralization: `architecture_optimizer.electron_margin` and `p1_reducer` (`icp45a_evaluate`, `i_e_cap_signed`,
    `kirchhoff_closure`, `neutralization_consistency`).
  * Coupled thrust / flow: `architecture_optimizer.thrust_minus_drag`, `design_synthesis` (`evaluate_system`,
    `feed_quality`) and `upstream_a9_13.refuse_feed_requirement_lowering`.
  * Chemistry support: the W7 rate-table builders and closed N2 audits. Hall-transport validation: the W8 O4 tooling.
* **Relevance.** This is the propulsion core of the selected architecture.
* **Method.**
  * The evidence-gated framework, the bridge and the reducers use `EXISTING_PHYSICS_PARITY`.
  * The bridge parity is launch equivalence plus EXACT_BYTES run records. The Julia code is unchanged.
  * `plasma_chem.py` is `AUDIT_THEN_EXTRACT_ONLY_IF_NEEDED` (message 1 sec. 3, message 2 sec. 9).
    * Candidate kernels: the cross-section-table rate branch, the Bohm wall flux, the effusion conductance and the
      particle / power balance structure.
    * The unverified Arrhenius fits are not extracted.
    * No `system.py` / `LaB6Cathode` path is ported.
  * A **predictive** ICP neutralizer plasma model would be `NEW_PHYSICS`. Its scope is **RM-OQ-12**.
* **Fail closed.**
  * `NOT_EVALUATED`:
    * the credible Hall transport set is EMPTY, so there is no absolute thrust;
    * there is no measured H-1 map and no design-specific Hall map;
    * ICP45 is not evaluated until `I_d,max,H1` is registered (ICP capacity `PENDING_ICP45`);
    * there are no P1 / P2 data (`TBD_AFTER_IMPEDANCE_MAP`);
    * an Ar result is never transferred to air;
    * an admission record needs the O4 dispositions.
  * `OUT_OF_DOMAIN`: chemistry beyond its validity limit (T_e > 30 eV for the 45 eV-capped family).
  * `MODEL_ERROR`: a Hall map from a non-pinned commit.
* **Admission.**
  * Bridge: launch equivalence, plus the pin checked in both Rust and Julia.
  * HallMap / ensemble / registry: semantics EXACT_VALUE (admitted members only; screening candidates rejected).
  * Reducers: parity on SYNTHETIC_TEST_ONLY vectors and on the committed records.
  * `plasma_chem`: a committed audit record exists before any extraction.
  * Credible-set emptiness is visible in every output that needs Hall performance.

### SC-WP-04 Spacecraft interaction: intake drag, reference drag interface, statewise T − D (rank 5)

* **Python reference.**
  * Intake drag:
    * `intake_synthesis.candidate_state_metrics` / `_c_solid_row`;
    * `intake_tpmc.intake_response` (C_D);
    * `architecture_optimizer.drag_table`.
  * Reference drag interface:
    * `abep_sim/spacecraft_reference_drag.py` (`reference_drag`, `ReferenceCase`, `statewise_margin`,
      `density_free_table`, `build_document`);
    * its builder `docs/design_synthesis/spacecraft_reference_drag/`;
    * `mission_env.spacecraft_drag`.
  * Statewise T − D:
    * `statewise.statewise_quantifier`;
    * `upstream_a9_13` (`statewise_envelope`, `reference_drag_fn`);
    * `architecture_optimizer.thrust_minus_drag`;
    * `design_synthesis.statewise_T_minus_D`.
* **Relevance.** The sustainment balance at every design state.
* **Method.** `EXISTING_PHYSICS_PARITY`. Physics computes T and D independently. HC-08 is assessment.
* **Fail closed.**
  * `NOT_EVALUATED`: there is no host-spacecraft drag ICD (D_body, F1-ID-08).
  * `NOT_EVALUATED`: T comes from no admitted Hall member.
  * `INCOMPLETE_EVIDENCE`: the intake-drag surface scenario is TBD (PARAMETRIC_ONLY).
* **Admission.**
  * Parity on all 196 states.
  * No requirement value is parsed in the statewise physics.
  * The C-DRAG-RFP Option 1 filter comes from the frozen engineering configuration. Option 2 is not approved.

### SC-WP-05 Electrical: PPU / load model, RF generator / matching, bus power, start-up / concurrent loads (rank 6)

* **Python reference.**
  * Loads:
    * `abep_sim/bus_boundary_a9.py` (`installed_slots`, `ledger`, `allocation_checks`) and `bus_boundary_a9_v2.py`;
    * `architecture_optimizer.official_ledger`;
    * `abep_sim/magnet_power.py` (`coil_design`, `electromagnet`, `coil_power_continuous_W`, `permanent_magnet`);
    * the builders `power_boundary_a9_v2/` and `magnet_coil/`.
  * RF generator / matching:
    * `p2_framework.py` (`ladder_abcd`, `dissipated_fraction_matched`, `verify_line_match_loss`,
      `vi_power_and_impedance`, `sol_correct`, `parse_touchstone`) and `p2_impedance_reducer.py`;
    * `bus_boundary_a9` (`rf_power_planes`, `icp_power_allocation_check`);
    * `p1_reducer.p_bus_from_generator_input`.
  * Bus power: `bus_boundary_a9` (`ledger`, `p_bus_1ms_max`) and `design_synthesis.bus_power`.
  * Start-up / concurrent loads: `bus_boundary_a9` (`check_startup_sequence`, `_peak_rises`).
* **Relevance.** The P_bus < 1.5 kW full-system gate, on one spacecraft-side DC boundary.
* **Method.** `EXISTING_PHYSICS_PARITY`, on the `hall_icp_neutralizer` configuration only.
  * **v3 finding:** `check_startup_sequence` applies the C1 heater / keeper rule (`_heater_rule`) when the
    `c1_heater` slot is installed. That happens only in `hall_c1_reference`. The rule, the `c1_*` slots and the C1
    peak events are `GROUND_REFERENCE_ONLY` and are not ported into flight crates.
  * `rfp_power_gate` is a requirement check. It moves to `abep-assess`.
  * A converter-efficiency kernel (`ppu.py::Converter`, class H) is extracted only if the preregistered load model
    needs it.
* **Fail closed.**
  * `NOT_EVALUATED`: no measured RF impedance (`TBD_AFTER_IMPEDANCE_MAP`).
  * `INCOMPLETE_EVIDENCE`: slot loads / efficiencies TBD.
  * `NOT_EVALUATED`: no conformant gate measurement (p_bus_1ms_max basis).
  * `NOT_EVALUATED`: start-up rules not classifiable with TBD loads.
* **Admission.**
  * Contracts reach PARITY_PASS.
  * The ledger closure is exact, and the energy-ledger residual is below 2 %.
  * A crate-graph test shows the RFP gate lives in `abep-assess`.
  * The forbidden-identifier scan is green: no `keeper` / `heater` load names in flight crates.

### SC-WP-07 Mass: selected-flight mass accounting, margin / accounting rules, Xe sensitivity (rank 7)

* **Python reference.**
  * `mass_power_a9_v5/build_mass_power_a9_v5.py` (`build_doc`, `rollup_v5`, `unresolved_v5`, `set_al09`,
    `system_margin_bid`, `assert_bid_margin_reading`).
  * `K-MASS-RULES` = `mass_power_a9_v3/build_mass_power_a9_v3.py` (`line_mev_value`, `harness_row60`,
    `closure_state`, `_unresolved`, `rollup`, `system_margin`, `rk`).
  * `architecture_optimizer.wet_mass`.
  * Xe sensitivity: `xe_accounting_a9_v3` (`case_split_loaded`, `design_cases`, `evaluate`, `ignition_booking_s`,
    `book_reserve_and_residual`), with the 2 / 5 / 10 kg planning cases.
* **Relevance.** The < 40 kg wet full-system gate.
* **Method.** `EXISTING_PHYSICS_PARITY`, with value-status preservation (RM-R27).
  * A9.28: `mass_power_a9_v5` = `ACTIVE_SELECTED_ARCHITECTURE_ENGINEERING_ASSESSMENT`.
  * AL-07 6.0 kg = `PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT`, `AFI-02-RA1_OPEN`.
  * The generic logic migrates.
  * AL-07 is never promoted to CBE, measured mass or frozen flight truth. The committed labels are reproduced
    byte-exactly. AFI-02-RA1 is the only rebase path.
* **Fail closed.**
  * `NOT_EVALUATED`: there is no CBE or measured mass for any BOM line.
  * `INCOMPLETE_EVIDENCE`: mass compliance (`DOES_NOT_CLOSE` stays visible) and the AL-07 status.
  * `NOT_EVALUATED`: the Xe load is not frozen (sensitivity cases only).
* **Admission.**
  * EXACT_BYTES regeneration of the v5 / Xe v3 records.
  * The VS-xx value-status test passes.
  * The roll-up arithmetic is exact.

### SC-WP-06 Thermal: NEW cathodeless Hall + RF/ICP thermal model (rank 8)

* **Python reference.**
  * **None for the new model.** RM-OQ-08 is OWNER_DECIDED A9.28: no Python model is built merely to create a parity
    target.
  * Retained kernels with parity:
    * `K-P3-RAYS` in `abep_sim/icp_thermal_lib.py` (`view_factors`, `trace`, `emit_zone`, `plume_interception`,
      `q_collector`, `h1_body`, `Body`, `vf_annulus_to_parallel_coaxial_annulus`);
    * the Hall-discharge / magnet kernels of `abep_sim/thermal_life.py` (`hall_wall_ion_heat_W`,
      `hall_wall_electron_heat_W`, `hall_anode_heat_W`, `hallmap_wall_inputs`, `rejected_heat_W`,
      `solve_node_temperature`, the coil / winding / insulation functions);
    * `architecture_optimizer.heat_rejection`.
* **Relevance.** The anode and the coupled H-1 / ICP thermal closure are UNRESOLVED. The P3 / H2-5 network carries a
  C-1 cathode node (AFI-03, `NOT_USABLE_FOR_FLIGHT_THERMAL_CLOSURE`).
* **Method.** `NEW_PHYSICS`, directly in Rust.
  * The preregistration covers: nodes, equations, heat sources, radiative / conductive boundaries, spacecraft
    interface, RF/ICP waste heat, Hall waste heat, assumptions, domains, conservation checks, analytic limiting cases
    and the evidence / validation plan.
  * Admission is by independent verification.
  * The retained kernels use `EXISTING_PHYSICS_PARITY`.
  * Not ported: the P3 v2 `h25_coupled_network` (node CB, `Q_cath`), the H2-5 network (class G) and the
    `thermal.py` `default_nodes`.
* **Fail closed.**
  * `NOT_EVALUATED`:
    * there is no measured thermal validation (validation status `NOT_VALIDATED`);
    * Hall waste heat needs an admitted Hall map;
    * there is no spacecraft thermal interface.
  * `INCOMPLETE_EVIDENCE`:
    * anode / coupled closure, UNRESOLVED and never PASS;
    * P3-G / R / K inputs TBD.
  * `OUT_OF_DOMAIN`: outside the preregistered domain.
* **Admission.**
  * The prereg is committed first and reviewed by the owner.
  * Analytic limiting cases pass: isothermal radiator, two-node conduction, zero-source equilibrium, view-factor
    reciprocity / enclosure.
  * The heat balance closes within the preregistered residual.
  * The independent cross-check is non-authoritative.
  * HC-06 (50 K) is applied only in assessment.
  * There is no hollow-cathode node.

### SC-WP-08 Materials / life: AO exposure, erosion, firing / mission life, reliability (rank 9)

* **Python reference.**
  * AO exposure:
    * `abep_sim/aochem.py` (`ao_flux`, `fluence`, `erosion_depth_um`, `recombination_fraction`, `inlet_composition`,
      `material_report`);
    * `materials.py` (owned by SC-WP-12 as a shared enabler);
    * `K-GAS-LIFE` = `life.py` (`intake_life`, `blade_life`) plus the gas-state wrapper only. It is extracted only if
      an active consumer is confirmed.
    * `lifetime_ao/build_ao_lifetime_register.py::compute_ao_environment`.
  * Erosion:
    * `sputter_yields_v1` (`yamamura_tawara`, `apid_fit`);
    * `compute_wall_sputter_index`;
    * `thermal_life.hallmap_wall_inputs`.
  * Firing / mission life: `architecture_optimizer.life_material_indicators` and `p4_screening.py` (`evaluate_gate`,
    `candidate_screening_state`, `final_material_status`).
  * Reliability: there is **no active implementation**. Candidate kernels are `life.py` (`reliability`, `magnet_life`,
    `compressor_life`).
* **Relevance.** The life basis: 26,280 h mission, > 15,000 h firing (HC-07 is assessment).
* **Method.**
  * `EXISTING_PHYSICS_PARITY`.
  * Reliability uses `AUDIT_THEN_EXTRACT_ONLY_IF_NEEDED`, otherwise a preregistered `NEW_PHYSICS` element. It never
    uses the `R_26000h` legacy key.
* **Fail closed.**
  * `INCOMPLETE_EVIDENCE`:
    * P4: all 352 gate cells INCOMPLETE_EVIDENCE; anode material OPEN; 316L REJECTED;
    * there is no AO coupon / material test evidence.
  * `NOT_EVALUATED`:
    * Hall wall erosion needs an admitted map with `wall_life_trustworthy`;
    * bearing / motor life;
    * reliability without evidence.
* **Admission.**
  * Contracts reach PARITY_PASS.
  * No life quantity is EVALUATED without its evidence.

### SC-WP-09 Mission: state propagation and mission integration (rank 10)

* **Python reference.**
  * Propagation: `abep_sim/mission_env.py` (`propagate`, `Spacecraft`, `eclipse_fraction`, `beta_angle`,
    `worst_eclipse_fraction`, `array_area_for`, `pointing_factors`), `configuration.load_mission_scenario` and
    `mission_scenario_v2` (immutable).
  * Mission integration: **none active**. `mission5` and the archengine driver are class H.
* **Relevance.** The 26,280 h mission basis and the Xe contingency consumption.
* **Method.**
  * Propagation: `EXISTING_PHYSICS_PARITY` (W3, PRE_RUST rank 5, `propagate` only).
  * Integration: `NEW_PHYSICS`. It integrates statewise T − D, feed, P_bus, Xe use, firing hours and AO fluence over
    `mission_scenario_v2`.
* **Fail closed.**
  * `NOT_EVALUATED`: T − D not evaluated (this propagates).
  * `NOT_EVALUATED`: the Xe load is not frozen.
  * `OUT_OF_DOMAIN`: a scenario outside v2 (a change is `mission_scenario_v3`).
* **Admission.**
  * Propagation: parity with orbit / eclipse invariants.
  * Integration: the prereg is committed first; analytic constant-rate cases and Xe / energy-ledger conservation pass;
    NOT_EVALUATED inputs are never zero-filled.

### SC-WP-10 Uncertainty / design: F7/F8 synthesis, robust optimisation, UQ (rank 11)

* **Python reference.**
  * F7/F8 synthesis:
    * `abep_sim/design/architecture_optimizer.py` (`design_vector_blocks`, `upstream_context`, `pareto_mask`,
      `nondominated_layers`, `flight_configuration_elements`, `architecture_questions`);
    * `abep_sim/programme/design_synthesis.py` (`context_pareto`, `evaluate_system`, `rank_full_system`).
  * Robust optimisation:
    * `robust_optimizer.py` (`scenario_robustness`, `robust_pareto`, `carried_robust_set`, `survivors`,
      `stable_seed`);
    * `architecture_optimizer` (`robust_pareto_set`, `require_all_admitted_scenarios`);
    * `upstream_a9_13` (`robust_over_scenarios`, `RobustParetoSet`).
  * UQ: `robust_optimizer` (`tpmc_monte_carlo`, `pointing_sensitivity`, `compressor_elasticities`, `perturbed`).
* **Relevance.** The active design / UQ driver. F8 is active and may migrate (message 1 sec. 7).
* **Method.**
  * `EXISTING_PHYSICS_PARITY`. The parity class is EXACT_STREAM (a numpy PCG64 port) or STATISTICAL, per **RM-OQ-03**.
  * `uq6`, `uq_modular`, `mission_uq`, `uncertainty` and Sobol are retired, not ported.
* **Fail closed.**
  * `NOT_EVALUATED`: the robust upstream set is EMPTY.
  * `NOT_EVALUATED`: unrankable objectives (Pareto `REFUSED_INCOMPLETE`).
  * `NOT_EVALUATED`: non-admitted scenarios.
* **Admission.**
  * Contracts reach PARITY_PASS.
  * The F7/F8 study is reproduced from captured references.
  * 196-state robust / UQ execution runs end to end in Rust.

### SC-WP-11 Assessment: raw physics vs requirement assessment, HC gates, RVM mapping (rank 12)

* **Python reference.**
  * `configuration.physics_configuration` / `assessment_configuration`, plus the tests `test_raw_assessment_split.py`,
    `test_layer_separation_physics.py` and `test_design_layer_separation.py`.
  * `abep_sim/assessment/design_gates.py` (`evaluate_constraints`, `hard_constraint_partition`, `gate_snapshot`,
    `bus_power_gate`, `ripple_feed_quality`, `statewise_drag_compensation`, `feed_state_sufficiency`,
    `propellant_paths_check`, `pareto_s6_17`, `rvm_gate_snapshot`).
  * `bus_boundary_a9.rfp_power_gate`.
  * `docs/requirements/rvm_a9/` (`build_rvm_a9.build_doc` / `evaluate_rows`, `rvm_rules.assign_status` /
    `assert_no_pass_without_measurement`, `a9_21_icp_gate.evaluate` / `gate_record` = GNG-ICP-01).
* **Relevance.** Physics emits raw quantities; assessment evaluates thresholds (A9.22 / A9.23; A9.24 items 3–5).
* **Method.** `EXISTING_PHYSICS_PARITY`, plus a crate-graph rule: physics crates never depend on `abep-assess`.
* **Fail closed.**
  * `NOT_EVALUATED`:
    * HC-12;
    * HC-05 without M_n,LB evidence;
    * HC-11 without the measured / validated H-1 basis (never lowered);
    * GNG-ICP-01 unless C1–C3 are all MET.
  * `INCOMPLETE_EVIDENCE`: an RVM PASS without measurement.
* **Admission.**
  * Contracts reach PARITY_PASS.
  * The threshold-only-change invariant (A9.24 item 4) holds on 196 states.
  * There is no requirement parsing in raw physics.

### SC-WP-12 Configuration / hash / provenance (rank 1)

* **Python reference.**
  * `abep_sim/configuration.py` (`load_manifest`, `load_verified`, the loaders, `model_set_drift`,
    `SimulationConfiguration`).
  * `scripts/config/build_config.py` (`build_all` and the `build_*` functions).
  * Shared enablers: `constants.py`, `materials.py` (`Material`, `DB`, `table`, `surface_ageing_alpha`),
    `operating_inputs.py` and `design/engineering_constraints.py`.
  * Architecture identity: `design/a9_19_architecture.py` (`require_flight_configuration`,
    `refuse_hollow_cathode_elements`, `hollow_cathode_elements`, `ground_reference`, `verify_decision_records`).
  * Check semantics for the generic provenance verifier:
    * `scripts/ci_checks.py::check_h2_6_live_sources`, which calls the H2-6 builder's `verify_sources`;
    * also `verify_sha_map`, `check_prereg_lock`, `check_audit_manifest` and `check_hallthruster_pin` in
      `scripts/ci_checks.py`.
* **Relevance.**
  * Every result carries the architecture / config / model-set / design-state-set hashes.
  * The architecture identity invariant is a pre-PR item.
* **Method.**
  * `EXISTING_PHYSICS_PARITY` for the loaders, builders, identity and verifier.
  * `NEW_INFRASTRUCTURE_ACCEPTANCE` for `bid_source_guard` + `bid_source_manifest_v1` and the migration-state ledger.
  * **RM-OQ-09** is OWNER_DECIDED A9.28.
    * Port the CHECK SEMANTICS: source hashes, provenance, pinned owner decisions, expected values and deterministic
      source verification.
    * Do not port obsolete H2-6 architecture assumptions.
    * Retire the Python check from active CI only after the verifier is admitted and CI is re-pointed.
    * H2-6 evidence stays immutable.
* **Fail closed.** `MODEL_ERROR` in each of these cases:
  * a hash mismatch;
  * a hollow-cathode element in a flight configuration;
  * a change to `mission_scenario_v2`.
* **Admission.**
  * `abep config build --check` is byte-identical.
  * The verifier gives the same pass / fail as the Python checks, on the current tree and on a preregistered seeded
    set of corrupted trees.
  * Identity refusal parity holds.
  * The guard fails on every preregistered tamper case.

### SC-WP-13 Deterministic CLI (rank 14)

* **Python reference.** There is no active entry point to port.
  * `python -m abep_sim` (`abep_sim/__main__.py`) runs the class-H legacy card sweep and is retired.
  * The script CLIs (`atmosphere_orbit.main`, `build_config.main`, `ci_checks.main`) map onto subcommands.
* **Method.** `NEW_INFRASTRUCTURE_ACCEPTANCE`. The `abep` binary has these subcommands: `run --states`, `sweep`,
  `robust`, `assess`, `golden check`, `build <id> --check`, `config`, `hall pin-check|smoke|schema-check`, `parity`,
  `ci` and `perf`.
* **Fail closed.** `NOT_EVALUATED` / refusal when a subcommand reaches a non-admitted component. There is never a
  silent Python fallback.
* **Admission.**
  * Outputs are byte-identical on a double run and across thread counts.
  * Every output carries `implementation = rust`, `rust_commit`, `contract_id` and the four hashes.

### SC-WP-14 Active builders / evidence generation, incl. ground-test programme tooling (rank 13)

* **Python reference.**
  * W15a: the F1–F4, F6, F7/F8, F9 freeze-candidate and H-1 freeze-candidate builders, plus
    `scripts/evidence/{evidence_archive,f1_archive}.py`.
  * W15b: M16 v5, the uncertainty budget, the ICP neutralizer ICD / evidence, `hall_sustainment`, RFQ v3, the hall_icp
    integration / prereg / programme / validation inputs, and the H2 A9 revisions.
  * W15c: the bid package, owner decisions and decisions application.
  * **Class `GROUND_TEST_PROGRAMME_ONLY` (A9.28):**
    * `scripts/experiments/s1_readiness.py` and `s1a_readiness.py` (`ACTIVE_GATE_TOOLING`);
    * `docs/experiments/capability_demo/` (`ACTIVE_EVIDENCE_TOOLING`);
    * `docs/experiments/hardware/` and `instrumentation/` (migrate where retained);
    * `docs/architecture_comparison/feed_state_closure/` (retained until successor feed-qualification records exist,
      RM-OQ-10).
* **Method.** `EXISTING_PHYSICS_PARITY`: `abep build <id> --check` is byte-identical, or the builder is
  FORMALLY_RETIRED_NOT_PORTED where its disposition allows.
  * Hall sustainment is `REFERENCE_EVIDENCE_ONLY`: its outputs are immutable.
  * Class-T tooling lives in `abep-groundtest`. No flight crate may depend on it.
  * The bid package stays pinned to `5eee4b8`.
  * The stale owner-question state v5 is repaired by a successor record.
* **Fail closed.**
  * `MODEL_ERROR` on a changed pin / reference.
  * A builder never turns `NOT_EVALUATED` / `INCOMPLETE_EVIDENCE` into PASS.
* **Admission.** Per builder, as above, plus a crate-graph isolation test for class T.

### SC-WP-15 Active canonical golden (rank 15)

* **Python reference.**
  * Comparator: `K-GOLDEN-COMPARE` = `abep_sim/golden.py` (`_compare`, `check`).
  * golden_v1 / v2 are **historical**. RM-OQ-06 is OWNER_DECIDED A9.28:
    * they are immutable and reproducible from the historical Python environment;
    * they are not Rust end-state parity cases;
    * they are never deleted or rewritten.
* **Method.** `NEW_INFRASTRUCTURE_ACCEPTANCE`. The `hall_icp_neutralizer` golden is generated **only from the admitted
  active chain** (message 1 secs. 4–5, message 2 sec. 12). It covers:
  * deterministic input configuration;
  * raw physics;
  * conservation;
  * architecture identity;
  * no conventional hollow cathode;
  * applicable statewise outputs;
  * assessment separation.
* **Fail closed.**
  * `NOT_EVALUATED` until the active chain is sufficiently admitted.
  * Golden values carry the chain's statuses as computed. They are never PASS by construction.
* **Admission.**
  * Two clean-install generations are byte-identical.
  * There is an owner golden-change governance record.
  * The CLAUDE.md rule-2 update is its own commit (CA-01).

### SC-WP-16 CI (rank 16)

* **Python reference.**
  * `scripts/ci_checks.py`: `CHECKS` and its eleven checks.
  * `.github/workflows/{ci,julia-smoke,rust-parity}.yml` (inline Python).
  * `scripts/perf/profile_baseline.py`, `scripts/verify_abep_core.py` and `abep_sim/design/tpmc_backend.py`.
  * `tests/`.
* **Method.**
  * Each check is ported once and run against both implementations on seeded corrupted trees. Then the Python check
    is retired.
  * Tests become cargo tests through captured references.
  * The zero-Python runner is `NEW_INFRASTRUCTURE_ACCEPTANCE`.
  * The historical-reproduction job runs outside the simulator CI (RM-OQ-06).
* **Fail closed.** `UNRECORDED_SOURCE_CHANGE` for an admitted component.
* **Admission.** Identical pass / fail per check, a Python-free image green, and GitHub CI green.

### SC-WP-17 Clean-install reproducibility (rank 17)

* **Python reference.**
  * Today's gate 1 (pass for Python): `requirements-lock.txt`, `hallthruster_bridge/setup.jl`, `Manifest.toml`.
  * `atmosphere_orbit_v2.fetch_hwm14`: the HWM14 source, pinned by sha256.
* **Method.** `NEW_INFRASTRUCTURE_ACCEPTANCE`. Two independent clean installs, with no `python3` on PATH, using:
  * the pinned rust-toolchain and `Cargo.lock --locked`;
  * Julia 1.11.7 with HallThruster.jl `bfb3019f…`;
  * the frozen data, verified by sha256.
* **Fail closed.** `MODEL_ERROR` when a pinned artefact is missing. Network-unavailable fetches are recorded
  `NOT_RERUN_NETWORK_UNAVAILABLE` and never fabricated.
* **Admission.** Byte-identical outputs for the config check, the 196-state run, robust / UQ, assessment, the active
  golden and every `abep build --check`.

## 6. Hall physics boundary (message 2 sec. 7)

* **HallThruster.jl stays authoritative** for Hall-discharge physics. No Hall physics is rewritten in Rust merely to
  remove Julia.
* **The pin.** HallThruster.jl v0.23.1, commit `bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5`
  (`hallthruster_bridge/PINNED.toml`), Julia 1.11.7 (`Manifest.toml`). The pin is never moved automatically: an
  upgrade is a physics-model change.
* **What Rust owns.** Orchestration only:
  * case / job generation;
  * launch, sharding and resumption;
  * reading run records;
  * Hall-map typing (generated from `hall_map_schema_v1.json`);
  * admission gating;
  * provenance.
* **The process boundary is deterministic.**
  * Rust launches `julia --project=hallthruster_bridge <script>.jl <in> <out>` through `std::process::Command`.
    There is no in-process embedding.
  * argv and an environment allow-list are fixed per job. The thread / BLAS environment is pinned and recorded.
  * Inputs are canonical JSON with a sha256. Outputs are JSON / JSONL with a sha256.
  * The pin is checked on both sides: Rust parses `PINNED.toml` / `Manifest.toml`, and Julia runs `check_pin()`
    (`bridge_lib.jl`).
  * The same inputs, pin and thread environment give byte-identical run records. Launch equivalence with the
    Python-launched job holds while both exist.
* **Provenance sidecar per run.** It records:
  * the Julia version and the HallThruster commit;
  * threads / BLAS, host and argv;
  * the input and output sha256;
  * `rust_commit` and `contract_id`.
* **The credible transport set is EMPTY** (`transport_ensemble_v0.json` members `[]`). Every output that needs Hall
  performance shows `NOT_EVALUATED` with reason "credible Hall transport set EMPTY". This absence of determining Hall
  calibration evidence stays visible.
* **Screening candidates** (`sgb-screen-01..09`) are never admitted, never produce design Hall maps, and never enter
  the trade or UQ without the governed validation process. That process needs:
  * pre-registered predictive evidence not used in selection;
  * no retuning;
  * a ≤ 1/16;
  * complete O4 dispositions.
* **Unchanged rules.**
  * `HallMap` loads admitted members only, and non-pinned maps are rejected.
  * `chemistry_trustworthy` / `rate_validity.toml` apply: no silent chemistry extrapolation.
  * `wall_life_trustworthy` stays separate from performance `trustworthy`.
  * The P5-N2 v1 outcome stays INCONCLUSIVE permanently.

## 7. First execution sequence

**Gate: P-01.** The owner reviews plan v3 and it merges into `integration/simulation-complete` (message 1 sec. 8 and
message 2 sec. 5: no Rust implementation work before the review).

"Immediately" means as soon as P-01 holds, with no further owner decision and no hardware evidence. ES-2 and ES-3 need
ES-1's workspace / `abep-types` / `abep-provenance`. ES-4 is docs-only and independent.

**ES-1 · SC-WP-12 foundation slice.**

* `Cargo.toml` workspace + `rust-toolchain.toml` (rustc 1.94.1, the parity_report_v2 build toolchain). `abep_core/` is
  untouched and stays outside the workspace.
* `crates/abep-types`: the status / error enums, including `NOT_EVALUATED`, `INCOMPLETE_EVIDENCE`, `OUT_OF_DOMAIN` and
  `MODEL_ERROR`, and a Python-compatible JSON float formatter.
* `crates/abep-provenance`: sha256, the MANIFEST / model-set / design-state-set hashes and the run-record sidecar.
* `docs/rust_migration/migration_state_v1.json`: one row per `component_inventory_v3.json` component.
* `docs/bid/bid_source_manifest_v1.json` + the `bid_source_guard` check (in `ci_checks.py` while Python CI exists). It
  protects `5eee4b8` / `b5849af` → `2de86ab` and the `mission_scenario_v2` sha256.
* `contracts/C-PROVENANCE-VERIFIER/parity_prereg_v1.json`, in its own commit. It covers the H2-6 check semantics
  (RM-OQ-09) and the prereg-lock / audit-manifest / pin semantics, with a preregistered seeded set of corrupted trees.
* `contracts/C-ABEP_SIM_CONFIGURATION_PY/parity_prereg_v1.json`, in its own commit.

**ES-2 · SC-WP-01 environment slice.**

* Contracts for `atmosphere.py`, `constants.py` and the `mission_env` constants kernel, each in its own commit before
  any comparison.
* `crates/abep-data` (frozen readers, sha256 against `config/MANIFEST.json`) and `crates/abep-atmos`.
* A contract for `atmosphere_orbit.py` (`load` / `state` / `orbit_states` / `load_design_states`, 196 states).
* Parity reports committed whatever the verdict; a ledger flip and a HISTORY entry on admission.

**ES-3 · SC-WP-02 intake TPMC response layer on the admitted Kernel 1.**

* A contract for `intake_tpmc` (`intake_response` / `response_surface` / `IntakeSurface`) and `intake`
  (`collection` / `compress`), STATISTICAL or EXACT_STREAM on the Kernel-1 stream. `intake_surface_v1` is reproduced,
  never regenerated.
* `crates/abep-intake`, consuming `abep_core` by path after a registered build-equivalence addendum.
* The PRE_RUST workload `intake_response_surface_reduced` re-timed on the Rust path (reported, never a criterion).
* RM-OQ-01 (the `DEFAULT_BACKEND` flip) put to the owner with the admission report.

**ES-4 · SC-WP-06 cathodeless thermal preregistration (docs only).**

* `docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/prereg_v1.json` + `PREREG.md`. It covers: nodes, equations,
  heat sources, radiative / conductive boundaries, spacecraft interface, RF/ICP waste heat, Hall waste heat,
  assumptions, domains, conservation checks, analytic limiting cases and the evidence / validation plan.
* An explicit exclusion of the H2-5 C-1 node / `Q_cath` (AFI-03), and of the 50 K margin from the equations (HC-06 is
  assessment).
* Owner review before any Rust code.

**Next candidates:**

* the SC-WP-03 `plasma_chem` kernel-audit record (docs only);
* the SC-WP-03 HallThruster.jl bridge contract (launch equivalence);
* the SC-WP-09 mission-integration preregistration (docs only).

## 8. Exit criteria

### 8.1 Main-merge pre-PR checklist (message 2 sec. 16)

Before any final PR to main, every item below must hold. Each has a mechanical check and an owning WP (JSON
`exit_criteria.main_merge_pre_pr_checklist`).

| # | item | mechanical check | WP |
|---:|---|---|---|
| 1 | all active production execution uses Rust + HallThruster.jl only | Python-free container run of `abep` over the active chain (E1); no `Command::new("python…")`, no `pyo3` in `cargo tree` | 13, 16 |
| 2 | no active LaB6 / hollow-cathode path | forbidden-identifier scan + static import scan (no class-H module reachable) | 16 |
| 3 | selected architecture identity invariant | architecture hash pin; `refuse_hollow_cathode_elements` parity; flight hollow cathode NONE, C1 GROUND_REFERENCE_ONLY in every output | 12 |
| 4 | all retained Python components migrated or explicitly historical | `migration_state_v1.json` complete (E7) | 12, 16 |
| 5 | clean install | SC-WP-17 acceptance | 17 |
| 6 | deterministic outputs | double-run and thread-count byte identity | 13, 16 |
| 7 | conservation checks | rule-4 gates; thermal balance within its preregistered residual | 02, 05, 06, 09 |
| 8 | config / hash integrity | `abep config build --check`, `config verify`, prereg locks, audit manifests, validation-release links, `bid_source_guard` | 12 |
| 9 | active golden green | `abep golden check` (hall_icp_neutralizer) | 15 |
| 10 | full Rust tests | `cargo test --locked --workspace`, incl. the Rust-era rule-9 contract (RM-OQ-05) | 16 |
| 11 | Hall interface tests | `abep hall pin-check` / `smoke` / `schema-check`; non-pinned maps rejected; credible set EMPTY visible | 03 |
| 12 | 196-state execution | `abep run --states design_states_v2`, all 196 states, fail-closed statuses recorded | 01, 04, 10 |
| 13 | robust / UQ execution | F7 / F8 robust optimisation + UQ end to end in Rust | 10 |
| 14 | assessment separation tests | threshold-only change moves assessment, never raw physics; crate graph | 11 |
| 15 | no silent fallbacks | domain / error parity cases; CLI refusal tests | 13, 16 |
| 16 | no requirement parsing in raw physics | crate graph + static scan for RFP clause reads in physics crates | 11, 12 |
| 17 | GitHub CI green | all required jobs on the integration head | 16 |
| 18 | no uncommitted / generated drift | working-tree-unchanged guard; every `abep build --check` byte-identical | 14, 16 |

### 8.2 Completion report A–N (message 2 sec. 18)

"Simulation complete" is never claimed from a test count. At completion, report:

* **A.** The exact integration SHA.
* **B.** The execution dependency graph: cargo metadata plus the bridge launch graph.
* **C.** The active-language inventory: the inventory re-run at the completion SHA.
* **D.** Proof that normal execution has zero Python dependency: the E1 / E6 / E10 runs.
* **E.** The HallThruster.jl integration and pin.
* **F.** The selected-architecture invariant proof.
* **G.** The active golden result.
* **H.** The full 196-state result.
* **I.** The robust / UQ result.
* **J.** The unresolved hardware-evidence gates: every fail-closed gate still `NOT_EVALUATED` / `INCOMPLETE_EVIDENCE`
  / `OUT_OF_DOMAIN` / `MODEL_ERROR`, listed.
* **K.** The clean-install result.
* **L.** The CI result: GitHub run ids.
* **M.** A comparison against the frozen bid technical source `5eee4b8`, per observable. Differences are explained, and
  the bid record is untouched.
* **N.** The exact main-merge plan: a new PR `integration/simulation-complete → main`, with PR #37 closed
  `SUPERSEDED_BY_SIMULATION_INTEGRATION`.

Only then is owner authorization requested to merge the completed simulator into main.

### 8.3 Zero-Python end state (message 2 sec. 13)

**The target is ZERO PYTHON ACTIVE EXECUTION DEPENDENCY.** It covers normal:

* simulation;
* design sweeps;
* mission propagation;
* UQ;
* assessment;
* gates;
* configuration / hash handling;
* the evidence / provenance builders that remain operational;
* normal CI.

Python may remain only for archived historical reproduction, after the corresponding active Rust components are
admitted.

**RETIRE** (message 2 sec. 11) means four things:

* not imported by active production execution;
* not required by the normal simulator CLI;
* not required by normal CI, except explicit historical-regression jobs;
* not ported merely for completeness.

Historical evidence is never deleted. The mechanical checks are E1–E10 (`programme_v3.json`) and CI_PLAN.md § 5.

## 9. Open questions and actions

**Open owner questions** (`programme_v3.json`):

* RM-OQ-01..05 are unchanged and open.
* **RM-OQ-10:** the feed-state closure at the end state, if no successor feed-qualification record exists. Port it, or
  freeze its outputs?
* **RM-OQ-11:** confirm that `2de86ab` is the terminal package state for `bid_source_guard`. The lineage guarded is
  `b5849af` → `2de86ab`.
* **RM-OQ-12:** the scope of "active RF/ICP physics". Is the evidence-gated framework plus the audited kernels enough,
  or is a predictive ICP neutralizer model part of "simulation complete"?

**Actions not done in this record:**

* **CA-01:** CLAUDE.md rule 2 → the ACTIVE canonical golden set, with the historical-golden distinction. This is a
  separate later commit.
* **CA-02:** the CLAUDE.md execution-baseline paragraph → `integration/simulation-complete`.
* **CA-03:** the A9.25 msg 1 sec. 16 staleness update.
* **CA-04:** the Rust-era rule 9 (after RM-OQ-05).
