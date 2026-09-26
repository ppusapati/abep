# Engineering ledgers v1: power, thermal, mass, life, uncertainty

Status: **schemas only.** These files define field names, origins and closure rules. They carry no subsystem
numbers. They are not wired into `abep_sim`; wiring them in is a model change, and that is the owner's call.
Nothing here claims ABEP closure, an architecture winner or a transport admission.

| file | content |
|---|---|
| `schemas/ledgers/subsystem_ledger_v1.json` | common record for every subsystem: six blocks (performance, power, mass, rejected heat, life/degradation, uncertainty), value and evidence records, per-subsystem producers and gaps, and the archengine energy-ledger map |
| `schemas/ledgers/bus_power_ledger_v1.json` | P_bus terms at the spacecraft-side DC boundary, their origin module or TBD, and the residual-closure rule |
| `schemas/ledgers/thermal_rejection_ledger_v1.json` | heat disposition per subsystem (Q_int vs exported vs transferred vs absorbed environment), node map, electrical-to-thermal and radiator closure |
| `tests/test_ledger_schemas.py` | the schemas parse, every archengine energy-ledger term maps to a ledger field, every code reference resolves, and the bus ledger has a residual-closure rule |

## 1. Conventions

- **Value record.** Every number in a ledger instance has `value, unit, status, origin, evidence`. `status` is one of
  `computed | superseded | TBD | not_applicable`. The value is null unless the status is `computed`. `TBD` carries
  `requires`, `not_applicable` carries `reason` and `superseded` carries `superseded_by`. Missing fields are never
  filled with placeholders (CLAUDE.md item 5).
- **Evidence record.** This uses the docs/EVIDENCE.md attributes: source, evidence level 1–7, quantity type
  (measured / digitized / inferred / reconstructed / model-derived / assumed), uncertainty, applicability domain,
  validation status and transformation chain. A code constant with no cited source is `assumed`, level 7. A value
  recalled from memory is marked `verify`.
- **Power is booked at the load plane.** Converter losses go to `ppu`. Controller and sensor draw goes to `avionics`.
  The bus side is the sum of load-plane power and losses.
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
| `ppu_loss_control` | `ppu.py:PPU.loads` `P_loss_W` (converter losses + `controller_W` + `sensors_W`) | ppu + avionics | P_PPU_losses + P_avionics | node `ppu` |

The residual comes from `resid = (P_bus − Σ ledger) / P_bus`, where `P_bus = ppu.py:PPU.loads['P_bus_W']`. It is
exported as `ledger_resid`.

### 3.2 PPU converters (`abep_sim/ppu.py:default_ppu` plus the archengine additions)

`anode` goes to P_discharge (Hall) or P_accelerator_other (grids). `mpd_hc`, `cap_charger` and `heater_main` go to
P_accelerator_other. `hv_mw` and `rf_amp` go to P_preionizer. `keeper`, `heater` and `cathode_src` go to P_cathode.
`magnet` goes to P_magnets, `motor` to P_compressor and `aux` to P_aux_unallocated.

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

1. **Bus ledger.** P_bus = Σ terms, and |resid| ≤ 0.02 per mode. This is the same gate as archengine (CLAUDE.md
   rule 4). Near-zero residuals are compared with an absolute tolerance (gate 6). Each instance is reported with
   one completeness value:
   - `CLOSED_ALL_TERMS`
   - `CLOSED_MODELED_TERMS_ONLY`: some term is TBD. P_bus is then a lower bound for the RFP 1.5 kW cap.
   - `NOT_EVALUABLE`: a superseded term, such as P_discharge while the credible set is empty.
   - `OPEN`
2. **Thermal ledger.**
   - Per subsystem: P_in + P_received = Q_int + P_exported + P_transferred.
   - System: P_bus = Σ Q_int + Σ P_exported + P_unassigned, with |resid_th| ≤ 0.02.
   - Any P_unassigned > 0 is reported as `CLOSED_WITH_UNASSIGNED`. At present that means half of the cathode power
     (G1) and the aux term (G2).
   - Radiator balance (Q_int + Q_env − direct radiation = radiator rejection) is TBD at instance level until
     `solve_network` exposes per-node terms (G19).
3. **Mass.** MEV = CBE × (1 + MGA[class]) (`mass_bom.py:build_bom`, `MGA`). Consumables are reported separately.
   A combined BOM line is never split silently.
4. **Life.** Each life value declares its basis (firing hours, calendar hours or cycles). It is compared only with
   the matching RFP requirement (`constants.py:RFPConstraints` `ignition_hours` / `mission_hours`).
5. **Uncertainty.** Every value carries its own evidence uncertainty. Hall-derived quantities are reported as an
   unweighted envelope over admitted members, with no probabilities.

## 5. Gap register

| id | gap | requires |
|---|---|---|
| G1 | Cathode heat: `default_nodes` assigns only 0.5 × P_cath to the cathode node, and the other half has no node or export term | a cathode heat-disposition model with source |
| G2 | archengine `aux` 5 W term: the consumer is unnamed and it has no thermal node | definition of the aux consumer (valves/flow control or avionics) |
| G3 | Valve / flow-controller power, both propellant paths | valve and flow-controller selection with holding/actuation power data |
| G4 | Heater power (gas chamber, Xe tank/lines, electronics): the cold case is computed but not converted into heater power | heater set-points and a heater-power derivation |
| G5 | Magnet coil power is a code constant, and the magnetic-circuit mass is folded into `accelerator` | Vyovrinda magnetic-circuit design (own geometry and B(z)) |
| G6 | Cathode keeper/heater split exists only in `ppu.load_modes` startup | cathode operating data per mode |
| G7 | Only the steady mode is evaluated by archengine; startup and peak have no producer in the trade | wiring `ppu.load_modes` and a peak-case definition |
| G8 | `bus_power_boundary_v1` (CLAUDE.md admissibility) is not in the tree at base efc4a4e | re-map these term ids when it lands; its names take precedence |
| G9 | Filter: its function is not defined in code, and its mass exists only in `system.py:evaluate` | RFP filter definition and a design with test or published data |
| G10 | `reservoir_feed` is one combined constant for the gas chamber and feed/valves | a separate chamber and valve BOM |
| G11 | No Xe feed model (no Xe-to-anode path) and no atmospheric flow-control model | feed-system design |
| G12 | Life items that are flags or constants (`intake_coating`, `bearings`, `ppu`) or missing (filter, buffer, valves, xe_tank, preionizer, thermal_control) | mechanism-based life models with sources |
| G13 | The Hall discharge values come only from the superseded 0-D closure, and the credible set is ∅ | an admitted transport-ensemble member and its design Hall map |
| G14 | Uncertainty drivers are missing or not linked to the archengine path | priors with sources per subsystem |
| G15 | Harness resistive loss is not modeled | harness lengths, gauges and currents |
| G16 | Compressor gas work and gas-chamber recombination heat are not tracked to their final dissipation | a gas-path thermal model |
| G17 | Avionics (controller and sensors) are lumped into `ppu` power, loss and mass | a separate avionics line |
| G18 | The jet/plume/body split of accelerator power is fixed code constants (0.4 / 0.6; `default_nodes` 0.85, 0.6) | a device heat-flux model; for Hall, an admitted member's map |
| G19 | Per-node absorbed environment and direct radiation are computed in `solve_network` but not returned | exposing those terms from `thermal.py:solve_network` |

## 6. What this lane does not do

- It enters no subsystem numbers and changes no physics, thresholds, frozen data or chemistry.
- It does not interact with the running campaign.
- Wiring instances into `archengine` and the `uq_modular` outputs is future owner-approved work.
