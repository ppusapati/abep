# A9.24 item 13: cathode-path audit (v1)

Audit only. No code, data, budget, golden, test or configuration was changed. No builder or simulator was run. Every
numeric impact below is an estimate made by reading committed values and code.
Machine-readable record: `docs/audits/a9_24_cathode_path_audit_v1.json`.

- Base: `claude/nifty-ramanujan-w68f9z` at `4b5563b643aa2103d999484ce4ccf5e2eca040e3`, branch `lane-a924-cathode`.
- Governing records:
  - A9.24 item 13 (`docs/decisions/OD_2026_10_04_A9_24_RUST_MIGRATION_AND_OPEN_ITEMS_OWNER_DECISIONS.md`).
  - A9.19: one Hall accelerator, one RF/ICP neutralizer, no conventional hollow cathode.
  - A9.20: C1 is `GROUND_ONLY_LAB_REFERENCE`.
  - A9.22 G4: cathodeless golden baseline; LaB6 is `HISTORICAL_NON_FLIGHT_REGRESSION`.
  - Active architecture: `config/architecture/hall_icp_neutralizer_v1.json`.

## Headline

**No active `hall_icp_neutralizer` code path instantiates `LaB6Cathode`.** Only two places reach the class:

- the legacy card closure, `abep_sim/system.py:257` (`plasma_physics` branch);
- the archengine `lab6_xe` neutralizer, `abep_sim/archengine.py:79`.

Both are `HISTORICAL_REGRESSION`. The `hall_icp_neutralizer` architecture is not a `thruster.CARDS` card and not an
archengine architecture. The active chain is made of:

- the F1–F8 design-synthesis modules (`abep_sim/design/*`, `abep_sim/programme/design_synthesis.py`);
- `bus_boundary_a9_v2`;
- the golden case `hall_icp_neutralizer_reference`;
- the budgets: mass/power v3, Xe accounting v3, RFQ v3;
- the RVM, M16 v5, F9 and the bid package.

The active chain has five inconsistencies:

- two budget floors (AL-08 and AL-07) whose analog values include conventional-cathode hardware;
- the P3 v2 coupled-thermal adapter, which inherits the H2-5 C-1 heat node;
- the golden active case, which is computed through the LaB6-carded `hall_1stage` closure (no numeric effect);
- the RVM-16 wording, which still names a flight keeper.

## Summary table

| id | class | severity | path (file:line) | numbers fed | numeric impact if removed (estimate) |
|---|---|---|---|---|---|
| AFI-01 | ACTIVE_FLIGHT_INCONSISTENCY | NUMERIC | `docs/budgets/mass_power_a9_v3/build_mass_power_a9_v3.py:140`, `mass_power_a9_v3.json` AL-08 floor constituent "Xe valves 2 x (latch + PFCV)" 0.57 kg; surfaced by `abep_sim/design/architecture_optimizer.py:1078-1103` | AL-08 MEV 6.0528 kg; dry known 40.746 kg; wet 42.75 / 45.75 / 50.75 kg (bid R-07, F7/F8, F9, RFQ3-GAS) | AL-08 CBE −0.115 to −0.285 kg, MEV −0.138 to −0.342 kg. Dry known 40.57 to 40.31 kg; wet at 2 kg Xe 42.57 to 42.31 kg. Hard-40 verdict unchanged (DOES_NOT_CLOSE). Owner already recorded this as provisional (A9.21 AL08). |
| AFI-02 | ACTIVE_FLIGHT_INCONSISTENCY | NUMERIC | `build_mass_power_a9_v3.py:19,140,491`; AL-07 floor = SETS PPU analog 5.0 kg. Retired AL-C1 text: "C1 supplies (A9B-C03) inside the AL-07 PPU analogs". | AL-07 MEV 6.0 kg → same roll-up | Cannot be quantified from the repository: no split of the analog exists. Direction: lower. It may be offset by the RF generator / matching (~1.5 kg) that the analogs do not contain. Each 0.1 kg of CBE is 0.152 kg of dry known mass. Not flagged by the F7/F8 refusal. |
| AFI-03 | ACTIVE_FLIGHT_INCONSISTENCY | LATENT | `docs/experiments/hall_icp/p3_coupled_thermal/p3_thermal_lib.py:988` (`h25_coupled_network`) imports `build_h2_5_thermal_network.py:321,491,501,575,602,635`: Q_cath 9–101 W into cathode-body node CB, labelled FLIGHT_REPRESENTATIVE. `build_p3_coupled_thermal_v2.py:1100` also carries "C1 = CONTROL_FALLBACK" with no A9.20 supersession. | Now: reproduction check only, no temperatures reported | Now: none. In a future flight coupled closure it would add 9–101 W (midpoint 55 W) of non-existent cathode heat at the H-1 back-plate path. |
| AFI-04 | ACTIVE_FLIGHT_INCONSISTENCY | LATENT | `abep_sim/golden.py:190-197,410-455` and `abep_sim/archengine.py:990-998` call `system.physics_closure(Config("hall_1stage"))`. That card carries `XE_CATHODE`, the "Xe-fed LaB6 cathode" (`thruster.py:96,106-111,193-194`). | golden_v2 `hall_icp_neutralizer_reference`, `gas_path`, `design_point_selection` (gas-path keys only) | Zero. Every key read is computed independently of `card.cathode`; LaB6Cathode and cathode_life are not instantiated. The risk is a Rust port carrying the LaB6 card in the active upstream reference. |
| AFI-05 | ACTIVE_FLIGHT_INCONSISTENCY | LABEL | `docs/requirements/rvm_a9/rvm_a9_rows.py:398-402` (RVM-16 "...keeper..."; "no graphite flight keeper"), `rfp_rebase.py:336`, `rvm_a9_v1.json` rows[15] m16 mapping to the "cathode" row. RVM-16 is missing from the A9.19 amend list (`a9_19_rvm.py:351,360`). | none (text); appears in F9 gates and `docs/bid/OWNER_DECISION_BRIEF_P0_P1.md:123` | none |
| GR-01 | GROUND_REFERENCE | | `abep_sim/bus_boundary_a9.py:161-180,232,277-297`; `bus_boundary_a9_v2.py:50-67` | no flight slot | – |
| GR-02 | GROUND_REFERENCE | | `docs/budgets/xe_accounting_a9_v3/*`: C1-GT-* ground lines; P-FL-C1 = configuration-scope zero | flight cathode Xe = 0 | – |
| GR-03 | GROUND_REFERENCE | | `docs/procurement/rfq_a9_v3/*`: HE-L10..12, GAS-L05/06/15, GAS-O03 | quotation only | – |
| GR-04 | GROUND_REFERENCE | | mass/power v3 retired C1 column, AL-C1, A9B-C01..C07 | flight unchanged | – |
| GR-05 | GROUND_REFERENCE | | hall_icp prereg framework (`:475`), uncertainty budget, validation inputs, P1 bench, `hw_programme_a9_21` C1-REF, `a9_10_overlay` | planning | – |
| GR-06 | GROUND_REFERENCE | | H2-1..H2-7 builders (H-1 + C-1 test article), `h2_a9_revisions` | only via AFI-01 / AFI-03 | – |
| GR-07 | GROUND_REFERENCE | | ICP neutralizer ICD / evidence (IP-C1, N-CC) | none | – |
| GR-08 | GROUND_REFERENCE | | M16 v5 row "cathode" (v4 label NOT_A_FLIGHT_SUBSYSTEM); counted among the 20 BLOCKED rows | programme count | – |
| GR-09 | GROUND_REFERENCE | | F2 FC-07 Xe cathode-line getter (`build_f2_filter.py:270-271,464`); out of scope, no A9.20 tag | none | – |
| GR-10 | GROUND_REFERENCE | | `config/architecture/hall_icp_neutralizer_v1.json` c1_role; `config/requirements/rfp_constraints_v1.json:439-481` | none | – |
| HR-01 | HISTORICAL_REGRESSION | | `abep_sim/plasma_devices.py:251-300` LaB6Cathode | – | – |
| HR-02 | HISTORICAL_REGRESSION | | `abep_sim/thruster.py:43-49,96-97,106-155,193-194`; `programme/sweep.py:29-58`; `transient.py:139`; `assessment/closure_checks.py:111-113,161` | legacy cards | – |
| HR-03 | HISTORICAL_REGRESSION | | `abep_sim/system.py:231,257,260,303,327-328,347,368-373,378,386,417,453`; `life.py:38-40,98-104` (**cathode starts 541→547**) | identity fixtures, HISTORY G1, `raw_closure_v2` schema | – |
| HR-04 | HISTORICAL_REGRESSION | | `abep_sim/archengine.py:28,64-120,135-140,166-185,549-565,701-712,749-756,921,976-986` (lab6_xe; mw_air / rf_cathode) | golden historical cases | – |
| HR-05 | HISTORICAL_REGRESSION | | `abep_sim/golden.py:99-133,214-226,310-321,349-372,460-501` | golden_v2 historical cases; `accelerators.ecr_hall.P_neut_W` 34.554 W | – |
| HR-06 | HISTORICAL_REGRESSION | | `abep_sim/mission5.py:96,190` | – | – |
| HR-07 | HISTORICAL_REGRESSION | | `abep_sim/uq6.py:120,168,227,240,285`; mission_uq, sizing, thresholds, uncertainty | – | – |
| HR-08 | HISTORICAL_REGRESSION | | `abep_sim/convergence.py:76-82,95-101` | gate 5 | – |
| HR-09 | HISTORICAL_REGRESSION | | `scripts/perf/profile_baseline.py:171-178,311-316,321-328,334-350`; `docs/performance/*` | timings (A9.24 items 6–7 migration order) | – |
| HR-10 | HISTORICAL_REGRESSION | | `scripts/config/build_result_schemas.py:38,109` → `schemas/results/raw_closure_v2.json` cathode fields | – | – |
| HR-11 | HISTORICAL_REGRESSION | | A5-era lanes: `cathode_integration.py`, `arch_boundary.py:34-61`, `breakeven.py:40`, `hard_gates.py`, `thermal_life.py:67-69,832-928`, `mass_bom.py:131,308-314`, `xe_ledger.py`, plus their docs/scripts builders | – | – |
| HR-12 | HISTORICAL_REGRESSION | | superseded mass_a9 v1, mass_power v2, xe_ledger_a9, xe_accounting v2, RFQ v1/v2, M16 v1–v4, owner-question v2–v4 builders | – | – |
| HR-13 | HISTORICAL_REGRESSION | | Upstream ICD v1 / dual-feed state machine cathode fields | – | – |
| HR-14 | HISTORICAL_REGRESSION | | `hallthruster_bridge/cases/p5_*.json`: P5 cathode Xe 0.44 mg/s recorded, not modelled | – | – |
| HR-15 | HISTORICAL_REGRESSION | | tests exercising HR-01..HR-13 (`tests/test_sim.py:245-246,311-404,515-545`, identity fixtures, golden, gas-path refusal tests, lane tests) | – | – |

## ACTIVE_FLIGHT_INCONSISTENCY (for owner decision before any baseline change)

### AFI-01: AL-08 embeds the C1 cathode-feed valve branch (NUMERIC, already owner-recorded as provisional)

**What the line contains.** The flight AL-08 floor (5.044 kg CBE → 6.0528 kg MEV, owner rule MQ-05) includes the H2-7
H27-12 two-branch valve set, 2 × (latch + PFCV) = 0.57 kg. The repository's own retired AL-C1 line says "the C1 cathode
Xe branch 0.285 kg (A9B-C04) is already inside the AL-08 floor". A9.21 decided
KEEP_6_05KG_PROVISIONAL_WAIT_FOR_QUOTES_TO_REBASE_AL08.

**Caller chain.**

1. `build_mass_power_a9_v3.py` `OWNER_MEV_FLOORS`
2. AL-08 6.0528 kg
3. roll-up: dry known 40.7464 kg, wet 42.75 / 45.75 / 50.75 kg
4. `architecture_optimizer.flight_configuration_elements`
5. `programme/design_synthesis.py:146`
6. F7/F8 `hollow_cathode_check = ..._C1_PROVISIONS_FLAGGED_PENDING_BUDGET_REFRESH`

**Documents that carry it.**

- mass/power v3
- F7/F8 and F9
- RFQ v3 `packages[1].line_items[9]`
- bid `02_TECHNICAL_APPROACH.md` sec. 2.2 / 5 and `04_RISK_REGISTER.md` R-07

**Estimate.** The roll-up rule is dry = non-harness × (1/0.95) × 1.20.

| case | Δ CBE | Δ MEV | AL-08 MEV | dry known | wet (2 kg Xe) |
|---|---|---|---|---|---|
| A9 single-branch reading (0.455 kg valves) | −0.115 kg | −0.138 kg | 5.915 kg | 40.572 kg | 42.572 kg |
| full 0.285 kg C1 branch removed | −0.285 kg | −0.342 kg | 5.711 kg | 40.314 kg | 42.314 kg |

No verdict changes. Wet 40 kg at 2 kg Xe would need a dry reduction of at least 2.75 kg.

**Decision.** Re-base AL-08 now, or keep the A9.21 provisional floor until the split quotations arrive.

### AFI-02: AL-07 PPU floor is an analog that contains the cathode supplies (NUMERIC, not flagged)

**What the line contains.** Flight AL-07 states "no C1 electronics". Its value, however, is the lowest Hall-thruster PPU
analog (SETS 5.0 kg → 6.0 kg MEV, MQ-04). The repository says the C1 heater / keeper / cathode-common supplies are inside
those analogs. The F7/F8 refusal books AL-07 as DECLARED_ABSENT from its name text and never inspects the analog basis.

**Estimate.** The repository holds no split, so the size cannot be quantified. The direction is downward, possibly
offset by the RF generator / matching (~1.5 kg) that the analogs lack. Sensitivity: 0.1 kg CBE = 0.12 kg MEV = 0.152 kg
dry known. Dry known reaches 40 kg only if at least 0.49 kg CBE comes out of AL-07 alone. The wet case cannot close from
this item.

**Decision.** Re-base on a cathodeless PPU analog or quotation (RFQ3-HALLEL), or keep the floor with an explicit
embedded-cathode flag like AL-08.

### AFI-03: P3 v2 coupled thermal inherits the H2-5 C-1 heat node (LATENT)

**What the path does.** `p3_thermal_lib.h25_coupled_network` couples ICP bodies to the pinned H2-5 v1 network
unchanged. That network includes:

- `CB` "cathode body + keeper";
- `Q_cath_W` of 9–101 W, conducted to the back plate;
- the label FLIGHT_REPRESENTATIVE.

**What P3 v2 reports today.** A method-reproduction check (temperatures not reported) and geometry-only view factors.
No reported number depends on `Q_cath`.

**Why it matters.** The future flight coupled H-1/ICP closure (A9 status UNRESOLVED) would include a non-existent
9–101 W cathode load unless `Q_cath` is zeroed and `CB` is dropped for the flight case. P3 v2 also carries "C1 =
CONTROL_FALLBACK" without the A9.20 supersession.

**Decision.** For the flight coupled case, zero or drop the C-1 node (keep it for the C1 ground-reference case). Add the
A9.20 supersession to P3 v2's carried statuses.

### AFI-04: golden active reference computed through the LaB6-carded `hall_1stage` card (LATENT, zero effect)

**What the path does.** Three callers use `system.physics_closure(Config("hall_1stage", ...))`:

- `golden.case_hall_icp_neutralizer_reference`;
- `golden.case_gas_path` and `admissibility` (through `_gas_record`);
- `archengine.gas_path_state`.

Inside, `thruster.performance` adds the card's Xe cathode (40 W, 0.05 mg/s), and `xe_cathode_kg` is computed.

**Why there is no numeric effect.** Only gas-path / AO / intake / compressor keys are read. They are computed before
the card's cathode is touched, and `p_target_Pa` is passed, so `card.p_min_Pa` is unused. `plasma_physics` and
`engineering_physics` are False, so neither `LaB6Cathode` nor `cathode_life` runs. The golden_v2 active case contains no
cathode value.

**Decision.** Compute the active upstream reference through a cathode-free upstream entry, especially before the
migration ports `physics_closure`.

### AFI-05: RVM-16 still names a flight keeper (LABEL)

**What the record says.** The RVM-16 title is "(AO-beam test; anode, collector, keeper, gas path)". Its text says "no
graphite flight keeper". It maps to the M16 "cathode" row, and A9.19 never amended it (unlike RVM-04).

**Where it appears.** F9 architecture gates and `docs/bid/OWNER_DECISION_BRIEF_P0_P1.md:123`. The bid package files
01–05 do not carry it.

**Effect.** No number.

## Cathode starts 541 → 547

| | |
|---|---|
| Producer | `abep_sim/system.py:369` `LifeInputs(cathode_starts=int(mission_h / 24 * 0.5))` → `abep_sim/life.py:98-104` `cathode_life()["starts"]` → `system.py:417` `eng_cathode_starts` |
| Arithmetic | int(26000/48) = 541 → int(26280/48) = int(547.5) = 547 (A9.22 G1) |
| When | Only with `engineering_physics=True` on a legacy `thruster.CARDS` architecture (hall_1stage, …). There is no hall_icp_neutralizer card. |
| Consumers | `programme.closure.evaluate` / `system.evaluate`, `uq6.monte_carlo6` / `robust_design`, identity fixtures rows 119–121, `tests/test_raw_assessment_split.py` |
| Carried by | `tests/fixtures/evaluate_identity_g1.json`, `docs/HISTORY.md` (G1 table), `schemas/results/raw_closure_v2.json` (field). No budget, F-chain, M16, RVM or bid document carries it (searched). |
| Related | `abep_sim/mission5.py:96` sets starts too, but its reliability call omits the cathode, so no output depends on it. |
| Classification | **HISTORICAL_REGRESSION**: not part of the active flight chain. |

## Guards (refusals, not cathode uses)

- `abep_sim/design/a9_19_architecture.py:157-237`: `refuse_hollow_cathode_elements`.
- `abep_sim/design/architecture_optimizer.py:1044-1120`: surfaces AFI-01.
- `abep_sim/programme/design_synthesis.py:142-146`.
- `abep_sim/assessment/design_gates.py:385-387`: HC-10 refuses a Xe → C1 branch.
- `abep_sim/archengine.py:166-185,976-986`: flight guard.
- `abep_sim/golden.py:99-133`.
- `scripts/config/build_config.py:126,156`.
- The corresponding tests.

## Observations for the owner

- **O-1.** `config/model_set/physics_model_set_v1.json` hashes every `abep_sim` module with no active/historical role.
  The A9.24 bid freeze records this model-set hash, and A9.24 item 7 migrates "the whole active Python stack" (system
  closure, architecture engine, sweep, …). Nothing machine-readable marks HR-01..HR-08 as historical, so the migration
  could port the LaB6 paths as active. Item 13 says not to fix this silently inside the migration. A labelling or
  retirement decision is needed first.
- **O-2.** The archengine flight guard excludes only `lab6_xe`. The air-fed plasma-bridge cathodes `mw_air` and
  `rf_cathode` stay flight-eligible, and `golden.py:392` states that `rf_cathode` does not represent the ICP. No active
  caller uses `flight=True`, so no number is affected.
- **O-3.** golden_v2 `accelerators` (role CANONICAL) contains `ecr_hall.P_neut_W` = 34.554 W from the LaB6 neutralizer.
  It is the only cathode-dependent key in that case, and the case is not labelled historical.
- **O-4.** The stale A9.2 status "C1 conventional reference = CONTROL_FALLBACK" is carried verbatim in F7/F8, F9, H-1
  and P3 v2. Only P3 v2 lacks an A9.20 supersession (see AFI-03).
