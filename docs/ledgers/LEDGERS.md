# Engineering ledgers v1: power, thermal, mass, life, uncertainty

Status: **DRAFT — PROPOSED for owner decision; schemas only.** These files define field names, origins and closure
rules. They carry no subsystem numbers. They are not wired into `abep_sim`; wiring them in is a model change, and that
is the owner's call. Nothing here claims ABEP closure, an architecture winner or a transport admission.

Evaluated against the execution branch `e15f66f` (second-lens repair; the lane was first built on `daa0e75`). Lanes
merged since then and aligned here: `lane_11_bus_boundary` (`abep_sim/arch_boundary.py`,
`schemas/architecture_comparison/bus_power_boundary_v1.json`, `BUS_POWER_BOUNDARY.md`), lane PPUMAG
(`abep_sim/magnet_power.py`), `lane_19_cathode_integration` (`abep_sim/cathode_integration.py`),
`lane_15_thermal_life` (`abep_sim/thermal_life.py`, `schemas/thermal_life/`) and `lane_21_mass_bom` (`mass_bom_v1`
extension of `abep_sim/mass_bom.py`). They are read-only for this lane and resolved lazily; the tests skip the
cross-lane checks when a module is absent and never import one at collection time.

**Milestones.** Supports **A** (a common vocabulary, per architecture, in which conditions on P_bus, heat, mass and
life can be stated; no numbers) and is a listed **C** integration deliverable (`schemas/ledgers/` in
`docs/architecture_comparison/dossier/dossier.json`). To reach **B** it needs evidenced instances: loads and
efficiencies per boundary component (lane_20_ppu_magnet electrical closure), an admitted Hall transport closure for every
hall_discharge-derived field (the credible set is ∅), owner decisions OD-L1/OD-L2 (§6), and the second lens on this
single-lens-v1 lane. To reach **C** it needs instances from the integrated design for every mode (steady, startup,
peak) with every term computed.

**Architectures.** `hall_only`, `rf_hall`, `ecr_hall`. The RF/ECR arms change only the pre-ionization method; the Hall
accelerator, feed state, cathode and bus boundary are common. The pre-ionizer subsystem exists only in `rf_hall`
(`rf_source`) and `ecr_hall` (`ecr_source`; its resonance-field supply `ecr_magnet` is under `magnets`), matching
`arch_boundary.PREIONIZER_COMPONENTS`. archengine names that correspond: `hall_internal+hall+…`, `rf_icp+hall+…`,
`ecr+hall+…`; `helicon+hall` and `dc_discharge+hall` are not covered by bus_power_boundary_v1.

| file | content |
|---|---|
| `schemas/ledgers/subsystem_ledger_v1.json` | common record for every subsystem: six blocks (performance, power, mass, rejected heat, life/degradation, uncertainty), value and evidence records, per-subsystem producers and gaps, and the archengine energy-ledger map |
| `schemas/ledgers/bus_power_ledger_v1.json` | decomposition of the archengine/ppu P_bus into load-plane terms plus pooled losses, their origin module or TBD, the residual-closure rules, and the term-by-term crosswalk onto `bus_power_boundary_v1` (which is the admissibility authority; this file never redefines `arch_boundary.bus_power_ledger`) |
| `schemas/ledgers/thermal_rejection_ledger_v1.json` | heat disposition per subsystem (Q_int vs exported vs transferred vs absorbed environment), node map, electrical-to-thermal and radiator closure |
| `tests/test_ledger_schemas.py` | the schemas parse, every archengine energy-ledger term maps to a ledger field, every code reference resolves, the bus ledger has residual-closure rules whose tolerance equals the archengine gate, and (when the modules are present) the crosswalk covers `arch_boundary.REQUIRED_COMPONENTS` for every architecture, `thermal_life.THERMAL_COMPONENTS` and the `mass_bom_v1` catalog |

## 1. Conventions

- **Value record.** Every number in a ledger instance has `value, unit, status, origin, evidence`. `status` is one of
  `computed | superseded | TBD | not_applicable`. The value is null unless the status is `computed`. `TBD` carries
  `requires`, `not_applicable` carries `reason` and `superseded` carries `superseded_by`. Missing fields are never
  filled with placeholders (CLAUDE.md item 5).
- **Evidence record.** This uses the docs/EVIDENCE.md attributes: source, evidence level 1–7, quantity type
  (measured / digitized / inferred / reconstructed / model-derived / assumed), uncertainty, applicability domain,
  validation status and transformation chain. A code constant with no cited source is `assumed`, level 7. A value
  recalled from memory is marked `verify`.
- **Two booking views, one boundary plane.** The *decomposition view* (archengine / `ppu.py:PPU.loads`) books power
  at the load plane and pools converter losses in `P_PPU_losses` (and harness loss in `P_harness_losses`, TBD):
  P_bus = Σ load-plane terms + P_PPU_losses + P_harness_losses. The *boundary view* (`bus_power_boundary_v1`, the
  admissibility authority) books every loss per component: P_bus_c = P_load_c / efficiency_c, with the converter and
  the harness of that component inside efficiency_c. §3.4 gives the crosswalk and the allocation rules that keep each
  watt in exactly one place.
- **avionics = propulsion housekeeping.** The `avionics` subsystem and the `P_housekeeping` term are the boundary
  component `housekeeping` (controller, PPU control, sensors, TM/TC interface). Spacecraft avionics and spacecraft
  housekeeping loads are outside the boundary.
- **Rejected heat ≠ electrical input.** Electrical input is split into Q_int (to the thermal network), P_exported
  (jet, plume) and P_transferred (to another subsystem).
- **Hall transport roles** (CLAUDE.md, two-layer Hall uncertainty):
  - `carrier` is hall_discharge.
  - `downstream_consumer` covers cathode, ppu, thermal_control and structure.
  - `independent` covers magnets, preionizer and avionics.
  - `forbidden_upstream` covers intake, filter, compressor, buffer, valves and xe_tank. The transport ensemble never
    enters these, and layer-1 calibration nuisance never enters any ledger.
  - Screening candidates never appear in ledgers. Hall-derived values need an admitted member
    (`abep_sim/hall_ensemble.py:require_admitted`). The credible set is currently empty, so they are null.

## 2. Subsystems

The 13 requested subsystems are intake, filter, compressor, buffer (atmospheric gas chamber), valves, xe_tank,
cathode, magnets, preionizer, hall_discharge, ppu, thermal_control and avionics. Two more are added so that the
archengine mass and energy ledgers map completely:
- `structure`, because `mass_bom.structure_mass` is a BOM line.
- `accelerator_other_family`, for the non-Hall screening families. It carries the jet/plume/body terms and the
  `P_accelerator_other` bus term. It is not a new propulsion family (rule 8), because the families already exist in
  archengine.

Per-subsystem producers, BOM lines, thermal nodes, life items and uncertainty priors are listed in
`subsystem_ledger_v1.json` under `subsystems.<id>`. A test checks every `path.py:qualname` reference.

## 3. Mapping to existing archengine fields

### 3.1 Energy ledger: `abep_sim/archengine.py:close_architecture`, dict `ledger`

| archengine term | producer (file:function) | subsystem | bus term | thermal disposition |
|---|---|---|---|---|
| `jet` | `archengine.py:_propulsion` → `P_jet_W` (Hall: `plasma_devices.py:hall_run_coupled`, superseded), split into `from_acc` / `from_src` | hall_discharge / accelerator_other_family / preionizer | P_discharge / P_accelerator_other / P_preionizer | exported |
| `plume` | `close_architecture`: 0.4 × Q_dev (code constant) | hall_discharge / accelerator_other_family | P_discharge / P_accelerator_other | exported |
| `accelerator_body` | `close_architecture`: 0.6 × Q_dev (code constant) | hall_discharge / accelerator_other_family | P_discharge / P_accelerator_other | node `thruster` |
| `ionizer` | `archengine.py:_propulsion` `P_ion_W` − from_src | preionizer | P_preionizer | node `stage1_source` |
| `neutralizer` | `archengine.py:Neutralizer.operate` `P_W` (LaB6 via `plasma_devices.py:LaB6Cathode.operate`) | cathode | P_cathode | node `cathode` gets 0.5 × P_neut; the rest is unassigned (G1) |
| `magnets` | `close_architecture` `P_mag` (code constant) | magnets | P_magnets | node `magnets` |
| `compressor` | `archengine.py:gas_path_state` `comp_power` (← `system.py:evaluate`) | compressor | P_compressor | node `compressor` |
| `aux` | `close_architecture` 5.0 W constant (`demand['aux']` = 1 A at 5 V) | valves / avionics (unallocated) | P_aux_unallocated | no node (G2) |
| `ppu_loss_control` | `ppu.py:PPU.loads` `P_loss_W` (converter losses + `controller_W` + `sensors_W`) | ppu + avionics | P_PPU_losses + P_housekeeping | node `ppu` |

The residual comes from `resid = (P_bus − Σ ledger) / P_bus`, where `P_bus = ppu.py:PPU.loads['P_bus_W']`. It is
exported as `ledger_resid`.

### 3.2 PPU converters (`abep_sim/ppu.py:default_ppu` plus the archengine additions)

`anode` goes to P_discharge (Hall) or P_accelerator_other (grids). `mpd_hc`, `cap_charger` and `heater_main` go to
P_accelerator_other. `hv_mw` and `rf_amp` go to P_preionizer. `keeper`, `heater` and `cathode_src` go to P_cathode.
`magnet` goes to P_magnets, `motor` to P_compressor and `aux` to P_aux_unallocated.

### 3.4 Crosswalk to `bus_power_boundary_v1` (lane_11_bus_boundary)

Authority: `abep_sim/arch_boundary.py` (`COMMON_COMPONENTS`, `PREIONIZER_COMPONENTS`, `REQUIRED_COMPONENTS`,
`bus_power_ledger`) and `docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md` §3 and §6 (the archengine
discrepancy audit, whose statuses are quoted here). Machine-readable form: `bus_power_ledger_v1.json`
`boundary_crosswalk`.

| boundary component | architectures | decomposition term (load) | ppu converter(s) whose loss goes into its efficiency | archengine status (BUS_POWER_BOUNDARY §6) | producer on the execution branch |
|---|---|---|---|---|---|
| `hall_discharge` | all | P_discharge | `anode` | included | admitted member's design Hall map (TBD; credible set ∅) |
| `hall_magnet` | all | P_magnets | `magnet` | included, fixed 25 W constant | `abep_sim.magnet_power` (inputs TBD) |
| `cathode_keeper` | all | P_cathode | `keeper`, `cathode_src` | included | `abep_sim.cathode_integration` |
| `cathode_heater` | all | P_cathode | `heater` | lumped into keeper | `abep_sim.cathode_integration` (start-up) |
| `flow_control` | all | P_valves_control | — | excluded (unless in `aux`) | none (TBD) |
| `compressor` | all | P_compressor | `motor` | included, same load plane | `archengine.py:gas_path_state` |
| `thermal_control` | all | P_thermal | — | excluded | none (TBD, G4) |
| `housekeeping` | all | P_housekeeping | — (added at the bus with no conversion) | partly included, mis-classed | `ppu.py:PPU` constants |
| `rf_source` | `rf_hall` | P_preionizer | `rf_amp` | included at generator DC input | `archengine.py:_propulsion` P_ion_W (re-reference to net RF) |
| `ecr_source` | `ecr_hall` | P_preionizer | `hv_mw` | included at magnetron DC input | `archengine.py:_propulsion` P_ion_W (re-reference to net microwave) |
| `ecr_magnet` | `ecr_hall` | P_magnets | — | excluded / indistinguishable | `abep_sim.magnet_power` (OD: PM vs electromagnet, BND-Q3) |

Not on the boundary: `P_accelerator_other` (non-Hall families, outside v1), `P_aux_unallocated` (unattributed until
OD-L1), and the pooled `P_PPU_losses` / `P_harness_losses`, which are distributed, not carried.

Allocation rules (no double counting):
- **A1 converter losses.** The loss of converter k (`ppu.loads` detail[k]: P_in − P_out) goes entirely into the
  efficiency of the one boundary component that owns k (table above); efficiency_c = Σ_k P_out / Σ_k P_in over its
  converters. A converter without an owner (`aux` until OD-L1; `mpd_hc`, `cap_charger`, `heater_main`) makes the
  boundary instance NOT_EVALUABLE.
- **A2 harness losses.** A harness run's loss goes into its component's efficiency; `P_harness_losses` is therefore
  zero in a boundary instance by construction and is never added on top.
- **A3 housekeeping.** `controller_W + sensors_W` are the `housekeeping` load, not a loss. archengine adds them at the
  bus without conversion, so an archengine-derived crosswalk carries efficiency 1 for it: a statement about the code
  (evidence class *assumed*), not about hardware.
- **A4.** Each watt appears exactly once in a boundary instance, as P_load_c or inside P_loss_c of one component.

### 3.3 Other archengine outputs

| ledger field | archengine output key | producer |
|---|---|---|
| bus P_bus_W | `P_bus_W` | `ppu.py:PPU.loads` |
| bus resid | `ledger_resid` | `archengine.py:close_architecture` |
| ppu performance η | `ppu_eta` | `ppu.py:PPU.loads` `eta_overall` |
| hall_discharge / accelerator P_elec | `P_acc_W` | `archengine.py:_propulsion` |
| preionizer P_elec | `P_ion_W` | `archengine.py:_propulsion` |
| cathode P_elec | `P_neut_W`, `I_neut_req_A`, `I_neut_max_A` | `archengine.py:Neutralizer.operate` |
| thermal Σ Q_int | `Q_waste_W` | `thermal.py:size_radiator` `P_waste_W` |
| thermal_control performance | `A_rad_m2`, `T_hot_limiting` | `thermal.py:size_radiator` |
| mass CBE / MEV (system) | `CBE_kg`, `MEV_kg` | `mass_bom.py:build_bom` |
| xe_tank consumable | `xe_kg` | `close_architecture` (neutralizer Xe only; there is no Xe-to-anode path) |
| life (system minimum / limiting item) | `life_sys_h`, `life_limiting` | `close_architecture` life_items |
| intake performance | `eta_c`, `C_D`, `mdot_air_mgps` | `archengine.py:gas_path_state` |
| structure performance | `structure_first_mode_Hz` | `mass_bom.py:structure_mass` |

BOM lines (`close_architecture` `parts`) map to subsystems as follows:
- `intake` → intake
- `compressor` → compressor
- `reservoir_feed` → buffer + valves (combined; G10)
- `ionizer` → preionizer
- `accelerator` → hall_discharge + magnets for Hall (combined; G5), or accelerator_other_family
- `neutralizer` → cathode
- `xe` → xe_tank consumable
- `xe_tank` → xe_tank
- `ppu` → ppu + avionics (combined; G17)
- `thermal` → thermal_control
- `structure` → structure

Life items (`close_architecture` `life_items`) map to subsystems as follows:
- `hall_channel` → hall_discharge (superseded)
- `grids`, `nozzle_source`, `mpd_electrodes`, `pit_capacitors` and `heater_nozzle` → accelerator_other_family
- `neutralizer` → cathode
- `blade_coating` and `bearings` → compressor
- `intake_coating` → intake (a pass/fail flag; G12)
- `ppu` → ppu (a constant; G12)

## 4. Closure and residual rules

1. **Bus ledger, decomposition view.** P_bus = Σ load-plane terms + P_PPU_losses + P_harness_losses, and
   |resid| ≤ 0.02 per mode, with resid = (P_bus − Σ terms)/P_bus. This is the archengine gate (CLAUDE.md rule 4);
   the test reads the tolerance from `archengine.py`. It is **not** a completeness check: the archengine ledger closes
   by construction, so a missing consumer leaves resid at zero (BUS_POWER_BOUNDARY §6, point 1). Near-zero
   residuals are compared with an absolute tolerance (gate 6).
   **Boundary view.** P_bus = Σ_c P_load_c / efficiency_c with the absolute, rounding-level `residual_W` gate
   (|residual_W| ≤ 1e-12 × max(Σ P_bus_c, 1 W)) enforced by `arch_boundary.bus_power_ledger`, never recomputed here.
   Architecture comparison uses the boundary P_bus only. When both views exist for one point and mode, their
   difference is reported with its itemization; no tolerance is set (OD-L2). Each decomposition instance is
   reported with one completeness value:
   - `CLOSED_ALL_TERMS`
   - `CLOSED_MODELED_TERMS_ONLY`: some term is TBD. P_bus is then a lower bound for the RFP 1.5 kW cap.
   - `NOT_EVALUABLE`: a superseded term, such as P_discharge while the credible set is empty, or a blocked
     crosswalk (unattributed `aux`, a converter with no boundary owner).
   - `OPEN`
2. **Thermal ledger.**
   - Per subsystem: P_in + P_received = Q_int + P_exported + P_transferred.
   - System: P_bus = Σ Q_int + Σ P_exported + P_unassigned, with |resid_th| ≤ 0.02.
   - Any P_unassigned > 0 is reported as `CLOSED_WITH_UNASSIGNED`. At present that means half of the cathode power
     (G1) and the aux term (G2).
   - Radiator balance (Q_int + Q_env − direct radiation = radiator rejection) is TBD at instance level until
     `solve_network` exposes per-node terms (G19).
3. **Mass.** Legacy trade: MEV = CBE × (1 + MGA[class]) (`mass_bom.py:build_bom`, `MGA`). Architecture
   comparison: the `mass_bom_v1` catalog of the execution branch (ESA maturity categories, per-item
   `power_boundary_components`, `check_power_boundary_coverage`), whose items map to subsystems through
   `subsystems.*.execution_branch_mapping.mass_bom_v1_items`. Consumables are reported separately. A combined BOM
   line is never split silently.
4. **Life.** Each life value declares its basis (firing hours, calendar hours or cycles). It is compared only with
   the matching RFP requirement (`constants.py:RFPConstraints` `ignition_hours` / `mission_hours`).
5. **Uncertainty.** Every value carries its own evidence uncertainty. Hall-derived quantities are reported as an
   unweighted envelope over admitted members, with no probabilities.

## 5. Gap register

Statuses re-checked against `e15f66f`. "Legacy" means the gap remains in the archengine trade view; the named
execution-branch module is the producer for the architecture comparison but its inputs are still TBD.

| id | gap | requires |
|---|---|---|
| G1 | Legacy: cathode heat: `default_nodes` assigns only 0.5 × P_cath to the cathode node, and the other half has no node or export term. Execution branch: `abep_sim.thermal_life` models the cathode node (keeper fraction + heater duty + emitter heating), inputs TBD | sourced inputs for the thermal_life cathode node |
| G2 | archengine `aux` 5 W term: the consumer is unnamed and it has no thermal node | definition of the aux consumer (valves/flow control or avionics) |
| G3 | Valve / flow-controller power, both propellant paths | valve and flow-controller selection with holding/actuation power data |
| G4 | Heater power (boundary `thermal_control`: gas chamber, Xe tank/lines, PPU heaters): the cold case is computed but not converted into heater power; `abep_sim.thermal_life` does not cover it either | heater set-points and a heater-power derivation |
| G5 | Legacy: magnet coil power is one 25 W code constant (Hall and ECR alike) and the magnetic-circuit mass is folded into `accelerator`. Execution branch: `abep_sim.magnet_power` produces `hall_magnet` / `ecr_magnet` load power and `mass_bom_v1` has separate magnet items, all with TBD design inputs | Vyovrinda magnetic-circuit design (own geometry and B(z)); ECR PM-vs-electromagnet choice (BND-Q3) |
| G6 | Legacy: archengine routes the heater share through the keeper converter; the split exists only in `ppu.load_modes` startup. Execution branch: boundary components `cathode_keeper` / `cathode_heater` and `abep_sim.cathode_integration` (start-up transient) provide the split structurally, inputs TBD | cathode operating data per mode |
| G7 | Only the steady mode is evaluated by archengine; startup and peak have no producer in the trade | wiring `ppu.load_modes` and a peak-case definition |
| G8 | Resolved structurally: `bus_power_boundary_v1` is on the execution branch (a2a1396) and §3.4 / `boundary_crosswalk` map every term. Open: the `aux` allocation (OD-L1) and the re-referencing of P_ion_W (generator DC input) to net RF/microwave power | OD-L1; generator-chain efficiency evidence per BUS_POWER_BOUNDARY §8 |
| G9 | Filter: its function is not defined in code, and its mass exists only in `system.py:evaluate` | RFP filter definition and a design with test or published data |
| G10 | `reservoir_feed` is one combined constant for the gas chamber and feed/valves | a separate chamber and valve BOM |
| G11 | No Xe feed model (no Xe-to-anode path) and no atmospheric flow-control model | feed-system design |
| G12 | Life items that are flags or constants (`intake_coating`, `bearings`, `ppu`) or missing (filter, buffer, valves, xe_tank, preionizer, thermal_control) | mechanism-based life models with sources |
| G13 | The Hall discharge values come only from the superseded 0-D closure, and the credible set is ∅ | an admitted transport-ensemble member and its design Hall map |
| G14 | Uncertainty drivers are missing or not linked to the archengine path | priors with sources per subsystem |
| G15 | Harness resistive loss is not modeled | harness lengths, gauges and currents |
| G16 | Compressor gas work and gas-chamber recombination heat are not tracked to their final dissipation | a gas-path thermal model |
| G17 | Housekeeping (controller and sensors) is lumped into `ppu` loss and mass in archengine; the boundary books it as the `housekeeping` load | a separate housekeeping line in the code (model change) |
| G18 | The jet/plume/body split of accelerator power is fixed code constants (0.4 / 0.6; `default_nodes` 0.85, 0.6) | a device heat-flux model; for Hall, an admitted member's map |
| G19 | Per-node absorbed environment and direct radiation are computed in `solve_network` but not returned | exposing those terms from `thermal.py:solve_network` |

## 6. Open owner decisions (PROPOSED)

| id | question | proposal |
|---|---|---|
| OD-L1 | Which boundary component carries archengine's unnamed 5 W `aux` load (1 A at 5 V)? | `housekeeping` until a valve driver is specified (BUS_POWER_BOUNDARY §2 books otherwise unrepresentable standby draw there) |
| OD-L2 | Tolerance on the decomposition-vs-boundary P_bus difference | none; report only, until both views come from the same evidenced inputs |
| OD-L3 | Keep the schema id `bus_power_ledger_v1` (decomposition) next to `arch_boundary.bus_power_ledger` (boundary)? | keep, with the role statement in the schema; rename only in a v2 if confusion persists |

## 7. What this lane does not do

- It enters no subsystem numbers and changes no physics, thresholds, frozen data or chemistry.
- It does not interact with the running campaign.
- Wiring instances into `archengine` and the `uq_modular` outputs is future owner-approved work.
