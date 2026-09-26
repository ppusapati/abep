# Dual-feed (Xe + atmosphere) operational state machine — v1.1 (DRAFT)

Machine-readable specification: `schemas/controls/dual_feed_state_machine_v1.json` (version `1.1-draft`).
Structural checks: `tests/test_dual_feed_state_machine.py` (run `python -m pytest -q tests/test_dual_feed_state_machine.py`).

## Milestone, question and verification status

- **Operating-model question answered: (iii)**, what could overturn a conditional selection
  (`docs/orchestration/lane_registry_v1.json`, `lane_14_dual_feed`, `answers: iii`).
- **Supports Milestone A only.** The machine gives, for each architecture and start variant, the start / transfer /
  fallback / shutdown sequence that a conditional-selection statement can name as a condition set ("architecture X is
  baseline provided its start sequence, its Xe cost per start and its fault handling are demonstrated"). It supplies
  structure only. Every threshold, duration, flow and Xe mass is TBD.
- **Reaching Milestone B requires:**
  1. second-lens verification of this lane;
  2. an admitted Hall transport closure with design Hall maps (`I_d`, `Id_rms_rel`, thrust), plus O/O₂ and mixture
     chemistry for the atmospheric and mixed states;
  3. pre-ionizer ignition and detection evidence (`docs/evidence/rf_source/`, `docs/evidence/ecr_source/`,
     `lane_18_interstage`) that fixes or eliminates start variant V1 or V2 for each architecture;
  4. sourced values for the power parameters, from `abep_sim.arch_boundary:bus_power_ledger` with sourced loads and
     efficiencies.
- **Reaching Milestone C requires:** sourced values for every parameter (feed-system design, cathode qualification
  including O exposure, PPU and FDIR designs, spacecraft EPS interface); a mission Xe budget per architecture, summed
  along this machine's paths; and hardware start/transfer demonstrations.
- **What could overturn a selection** is listed in `milestone_support.what_could_overturn`:
  - a Xe-ignited discharge that cannot be transferred to mixed or atmospheric feed;
  - a pre-ionizer that cannot be ignited or held, or whose start-up peak `P_bus` exceeds `P_bus_alloc`;
  - cathode O-exposure evidence;
  - an air-fed cathode demonstrated by test;
  - a Xe cost per start or per fallback that the budget cannot carry.
- **Verification: single-lens-v1.** v1.1 is the second-lens repair. Until the second lens passes, this machine is not
  decisive evidence for Milestone B or C (`docs/orchestration/OPERATING_MODEL.md`).

## Status and scope

- **Conceptual control-logic specification, not validated.** Every guard is symbolic. All 83 named parameters carry
  `value: "TBD — requires <model/test>"`, and none has a sourced number yet. A parameter gets a value only together
  with a `source` and an `evidence_class` (measured / digitized / inferred / reconstructed / model-derived / assumed,
  per docs/EVIDENCE.md). The test suite rejects any other numeric value anywhere in the file.
- **It asserts nothing about discharge physics.** Gate 3 is FAIL and the credible transport set is ∅ (CLAUDE.md), so no
  design Hall map exists. The simulator does **not** establish whether a Hall discharge can be ignited on Xe and then
  transferred to, sustained on or throttled on atmospheric or mixed feed, with or without a pre-ionizer.
  HallThruster.jl reaction sets cover Xe and N₂/N only: there is no O/O₂ chemistry and no Xe + atmosphere mixture. The
  states below are the sequence a controller would need *if* those regimes exist. The guards that decide them (e.g.
  `I_d`, `Id_rms_rel`, `T_air_avail`, `preionizer_lit`) are gated or TBD.
- **RFP basis:** air + Xe propellants, Hall preferred, power < 1.5 kW, 12–25 mN (CLAUDE.md;
  `abep_sim.constants:RFPConstraints`, transcribed from RFP Part III Para 2). The RFP text is not in the repository, so
  verify it. The RFP does not enumerate these states (verify). The state list is a Vyovrinda control-design proposal.
- **Architecture scope rule:** the atmospheric path is intake → filter → compressor → atmospheric gas chamber →
  atmospheric valve (`atm_anode`). The Xe path is Xe chamber → Xe valves (`xe_cathode`, `xe_anode`). Both feed the
  ionization/discharge → acceleration/thrust block. Hall transport-ensemble uncertainty belongs to that block only and
  is never an upstream guard quantity. Layer-1 calibration-nuisance variables (P5 registration, coil shape,
  beam-efficiency reading, facility ingestion) are never guard quantities or parameters. A test enforces this against
  `hallthruster_bridge/ensemble/transport_ensemble_v0.json`.

## Architectures and configurations

The three thrust architectures use the exact ids `hall_only`, `rf_hall` and `ecr_hall`. The RF and ECR arms change
only the pre-ionization method. The downstream Hall accelerator, the feed state, the cathode and the bus boundary are
common. The machine therefore shares every state, guard and Xe-ledger entry, and the architectures differ only in:

- the `preionizer` output of each state (given per start variant; `absent` for `hall_only`). It maps to the
  bus_power_boundary_v1 components `rf_source` (`rf_hall`) and `ecr_source` + `ecr_magnet` (`ecr_hall`), with the
  electromagnet energised before the microwave source;
- two pre-ionizer states, `PREIONIZER_SEED` and `PREIONIZER_IGNITION`;
- pre-ionizer loss handling (`<state>__preionizer_loss` → `XE_FALLBACK`) and pre-ionizer hard faults
  (`preionizer_fault` in the `health` guard of the fault transitions → `SAFE_MODE`). `preionizer_fault` is false by
  construction for `hall_only`.

Where the pre-ionizer starts is **open**. `lane_19_cathode_integration` records two PROPOSED variants, and no accessed
source fixes the choice (`docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json`,
`startup_reference`):

- **V1, pre-ionizer after discharge:** the Xe Hall discharge starts exactly as in `hall_only`. `WARM_UP__preionize`
  then enters `PREIONIZER_IGNITION`, and atmosphere admission follows only with a confirmed pre-ionizer plasma.
- **V2, seed before discharge:** after keeper coupling, `CATHODE_IGNITION__seed` enters `PREIONIZER_SEED` (Xe seed
  flow, pre-ionizer ignited). The anode is ignited from there. `PREIONIZER_IGNITION` then only confirms or re-lights
  the pre-ionizer. V2 matches the order of the experiment-protocol draft. In V2 the heater may still be on while the
  pre-ionizer starts, so the heater/pre-ionizer overlap sets `P_startup_peak`.

This gives five configurations (`configurations` in the JSON): `hall_only`, `rf_hall/V1`, `rf_hall/V2`, `ecr_hall/V1`
and `ecr_hall/V2`. Each state and transition lists the configurations it `applies_to`. Every graph property is tested
per configuration. After a Xe fallback, `rf_hall` and `ecr_hall` re-admit atmosphere through `XE_FALLBACK__reionize` →
`PREIONIZER_IGNITION`, and `hall_only` re-admits through `XE_FALLBACK__readmit`. Two points are owner FDIR policy
items (TBD): whether exhausted pre-ionizer retries should shut down (as specified) or hold Xe-only Hall operation, and
whether a failed V2 seed should continue unseeded.

## Power boundary

All power guards use **`P_bus` of `bus_power_boundary_v1`**. `P_bus` is all electrical power crossing the
spacecraft-side DC boundary for the configuration's architecture: Σ P_load/η over `REQUIRED_COMPONENTS[arch]` =
`hall_discharge`, `hall_magnet`, `cathode_keeper`, `cathode_heater`, `flow_control`, `compressor`, `thermal_control`,
`housekeeping`, plus `rf_source` (`rf_hall`) or `ecr_source` + `ecr_magnet` (`ecr_hall`). The shared contract is
`abep_sim.arch_boundary:bus_power_ledger` (lane_11_bus_boundary), with the schema
`schemas/architecture_comparison/bus_power_boundary_v1.json`. The power symbols are `P_bus`, `P_bus_demand` (the
setpoint's `P_bus`), `P_bus_avail` (spacecraft power available at the boundary), `P_bus_alloc`, `P_bus_min_sustain`,
`P_bus_idle_max` and `P_startup_peak`. The global invariant is `P_bus <= P_bus_alloc`, with
`P_bus_alloc <= RFP_power_max`. Reading the RFP < 1.5 kW limit as `P_bus` at this boundary is the project's boundary
choice (verify against the RFP text).

v1.0 used `P_prop` ("PPU input incl. compressor motor and controller"). That definition did not explicitly include the
cathode heater and keeper, the magnets, thermal control or a pre-ionizer, so v1.1 removes it
(`docs/orchestration/OPERATING_MODEL.md` §3 forbids substituting subsystem or incompatible power definitions).
`abep_sim.ppu:PPU.loads` / `load_modes`, `abep_sim.compressor:DragCompressor.run` and `abep_sim.intake:compress` remain
listed with status `component_only`. They can supply component loads or efficiencies to the ledger, but never `P_bus`
itself. A test enforces this. When `abep_sim/arch_boundary.py` is present in the checkout, the test also checks that
its `BOUNDARY_VERSION`, `ARCHITECTURES` and `PREIONIZER_COMPONENTS` match this specification. The module is parsed and
never imported.

## Design rationale

1. **Ignite on Xe, then transfer.** The Xe path is independent of intake/compressor state, so the start sequence
   (`XE_PURGE` → `CATHODE_CONDITIONING` → `CATHODE_IGNITION` → [`PREIONIZER_SEED`, V2] → `XE_DISCHARGE_IGNITION` →
   `WARM_UP` → [`PREIONIZER_IGNITION`, rf_hall/ecr_hall]) never depends on the atmospheric path. Atmospheric species
   are admitted into an established discharge (`ATMOSPHERE_ADMISSION`). The anode feed is then transferred gradually
   (`MIXED_STABILIZATION` → `ATMOSPHERE_DOMINANT` → `AIR_ONLY_ANODE_XE_CATHODE`), so every step has a reversible exit
   to `XE_FALLBACK`. Lane 19 records, as a phase order only, that Cifali 2011 ignited on Xe and then moved the anode to
   N₂/O₂ (not accessed by this lane: verify).
2. **Xe-fed cathode throughout; the air-fed cathode is excluded by design choice pending test.** The repository's
   cathode model treats atomic O as an emitter poison (`abep_sim.plasma_devices:LaB6Cathode.coverage`; the
   `abep_sim.aochem` material-class note says LaB6 must be Xe-shielded). These are **unsourced code priors (verify)**.
   The literature pointers are the ones lane 19 records:
   - Gallagher 1969, doi:10.1063/1.1657092, not accessed;
   - Suzuki et al. 2024, doi:10.1063/5.0188080, abstract only, qualitative;
   - Andreussi et al. IEPC-2017-377: a Hall thruster on N₂–O₂ needed continuous cathode Xe flow to avoid flame-out.

   Lane 19 also records that the accessed sources give **no atomic-O or N₂ threshold for LaB6**
   (`NO_QUANTITATIVE_EVIDENCE`). The purge, its duration and `p_O_cathode_max` are therefore TBD. The air-cathode
   closure did not close the discharge current at life either (docs/HISTORY.md v1.1 item 3, model-derived: "a test,
   not a design choice"). So the machine purges before heating, heats only under Xe flow, and uses
   `AIR_ONLY_ANODE_XE_CATHODE` rather than a fully air-fed mode.

   `excluded_branches.air_fed_cathode` records this as a **design choice pending test, not a physics result**. The
   upstream ICD (`schemas/interfaces/upstream_icd_v1.json`, IF-A5) carries `mdot_cathode_air_kgps`, and this machine
   holds that interface at zero. Cathode Xe flow and cathode start count are mission consumables.
3. **Warm-up overlaps the chamber fill.** `WARM_UP` spins up the compressor while the thruster soaks on Xe, so
   admission starts from a filled atmospheric chamber (`abep_sim.reservoir:startup_transient` gives the fill transient).
4. **The pre-ionizer comes up on Xe, before any atmosphere.** Atmosphere is never admitted into an `rf_hall` or
   `ecr_hall` discharge without a confirmed pre-ionizer plasma (`preionizer_lit`) and an interstage current inside
   its limit (`abs(I_interstage) <= I_interstage_max`). Lane 19's current budget is
   `I_emit = I_d + I_keeper + I_interstage`. A pre-ionizer loss in operation reverts to `XE_FALLBACK` rather than
   shutting down.
5. **Two safe sinks, one safing state.** `OFF` and `SAFE_MODE` are the safe states (de-energised, valves fail-closed,
   pre-ionizer off). `CONTROLLED_SHUTDOWN` is the only safing state. It removes pre-ionizer power first and exits only
   to `OFF` (complete) or `SAFE_MODE` (fault or time-out). Every non-safe state has a direct `fault` transition to
   `SAFE_MODE`. Every operating and startup state has a `protective` transition to `CONTROLLED_SHUTDOWN` and a
   `command` stop.
6. **Bounded retries and counted restarts.** Keeper, anode-ignition and pre-ionizer retries are self-loops bounded by
   counters (`n_keeper_retry_max`, `n_ignite_retry_max`, `n_preion_retry_max`), and exhausting them is protective.
   `RESTART` is a checked eligibility decision (inhibit time, restart counter, Xe reserve, cathode starts), not a
   re-entry into the start sequence. `SAFE_MODE` exits only by ground command to `OFF`.
7. **Degrade before shutting down.** `DEGRADED_OPERATION` absorbs anomalies that throttling can handle, because a
   shutdown/restart costs Xe and a cathode start. `XE_FALLBACK` keeps the discharge lit when the atmospheric path or
   the pre-ionizer is anomalous. The number of fallback/readmission cycles is bounded (`n_fallback_cycles_max`).
8. **Xe ledger.** Each state declares a symbolic Xe rate. Each transition declares `xe_consumed.in_source_state` and
   `xe_consumed.at_transition`. Summing along a configuration's path gives the Xe cost of a sequence. V2 adds the
   seed flow `mdot_Xe_anode_seed_set` in `PREIONIZER_SEED`. The reserve parameters (`m_Xe_reserve_startup`,
   `m_Xe_reserve_restart`, `m_Xe_reserve_fallback`, `m_Xe_reserve_shutdown`, ordered by `parameter_constraints`)
   must cover it. Their values are TBD: they require admitted design Hall maps and a Xe gauging method.

## Guard semantics

- Each transition has `guards` with the five required categories (`pressure`, `discharge_current`, `flows`, `timing`,
  `power`), plus the optional `thermal`, `inventory`, `sequence` and `health`. An entry beginning `n/a:` imposes no
  condition and states why.
- `guard_logic: ALL`: every condition holds, together with `preconditions`. `t_condition` counts how long the full set
  has held (success confirmation).
- `guard_logic: ANY_PERSISTING`: fires when any triggering condition holds continuously for the timing entries. These
  are the fault/protective persistence filters, e.g. `t_fault_confirm`.
- Priority in each control cycle: fault > protective > command > degradation > recovery > nominal > retry. A transition
  is evaluated only in the configurations it `applies_to`.
- Expressions use only declared quantities, parameters and external refs (`RFP_power_max`, `RFP_thrust_max`), plus
  the operators in `expression_grammar`. They contain no numeric literals.
- Each transition has `fault_behaviour` (`on_fault`, `fault_transition`, `on_guard_not_met`, `description`).
- Global invariants: `T_cmd <= RFP_thrust_max` and `P_bus <= P_bus_alloc` (with `P_bus_alloc <= RFP_power_max`).

## States

| state | category | applies to | pre-ionizer output (V1 / V2) | Xe consumed (rate expression) | rationale |
|---|---|---|---|---|---|
| `OFF` | safe | all | off / off | `none: all Xe valves closed` | Initial and final state. Exits only on a start/restart command or on a fault latched while off. |
| `XE_PURGE` | startup | all | off / off | `mdot_Xe_purge` | The repository's cathode model treats atomic O as an emitter poison (abep_sim.plasma_devices:LaB6Cathode.coverage; abep_sim.aochem MATERIAL_CLASS 'LaB6 ... must be Xe-shielded'); purging before heating follows from that model. The need for, and duration of, a purge is TBD — requires cathode O-exposure test. |
| `CATHODE_CONDITIONING` | startup | all | off / off | `mdot_Xe_cathode` | Emitter heating under Xe flow so the emitter is not heated in an O-bearing environment without flow. |
| `CATHODE_IGNITION` | startup | all | off / off | `mdot_Xe_cathode` | Separates keeper coupling from anode ignition so that a keeper failure never reaches the anode supply. |
| `PREIONIZER_SEED` | startup | rf_hall/V2, ecr_hall/V2 | off / igniting | `mdot_Xe_cathode + mdot_Xe_anode` | Seed hypothesis (lane_19 startup_reference V2; experiment-protocol draft order heater, keeper, flows, pre-ionizer, discharge). PROPOSED: whether a seed helps anode ignition, and the heater/pre-ionizer overlap it causes in P_startup_peak, are TBD — requires pre-ionizer ignition test. |
| `XE_DISCHARGE_IGNITION` | startup | all | off / on (seed) | `mdot_Xe_cathode + mdot_Xe_anode` | Ignition on Xe only: the Xe path is independent of the atmospheric path, so ignition does not depend on intake/compressor state. Whether a discharge on atmospheric feed could be ignited directly is not assumed. |
| `WARM_UP` | startup | all | off / on (seed) | `mdot_Xe_cathode + mdot_Xe_anode` | Overlaps thruster warm-up with the atmospheric chamber fill transient (abep_sim.reservoir:startup_transient) so that admission starts from a filled chamber and a thermally soaked thruster. |
| `PREIONIZER_IGNITION` | startup | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 | igniting / igniting or on (confirm) | `mdot_Xe_cathode + mdot_Xe_anode` | Keeps the Hall stage on its demonstrated Xe state while the pre-ionizer is brought up, so that a pre-ionizer failure never coincides with the atmosphere transfer. PROPOSED ordering (lane_19 V1); TBD — requires pre-ionizer ignition test. |
| `ATMOSPHERE_ADMISSION` | operating | all | on / on | `mdot_Xe_cathode + mdot_Xe_anode` | Introduces atmospheric species into an established Xe discharge instead of igniting on atmospheric feed. Whether the discharge survives admission is not modelled (no admitted Hall member; no O/O2 chemistry; no Xe + atmosphere mixture) and is a test item. |
| `MIXED_STABILIZATION` | operating | all | on / on | `mdot_Xe_cathode + mdot_Xe_anode` | Transfers the discharge from Xe to atmospheric feed gradually so each step can be reversed to Xe fallback. |
| `ATMOSPHERE_DOMINANT` | operating | all | on / on | `mdot_Xe_cathode + mdot_Xe_anode` | Mirrors the Xe-topping policy structure of abep_sim.transient:run_mission (air first, Xe anode topping when air thrust is short). |
| `AIR_ONLY_ANODE_XE_CATHODE` | operating | all | on / on | `mdot_Xe_cathode` | Keeps an Xe-fed cathode because the repository's air-cathode closure did not close the current at life (docs/HISTORY.md v1.1 item 3, model-derived; 'a test, not a design choice'). Xe consumption in this state is the cathode flow only. |
| `DEGRADED_OPERATION` | degraded | all | on (possibly derated) / on (possibly derated) | `mdot_Xe_cathode + mdot_Xe_anode` | Avoids a shutdown/restart cycle (which costs Xe and cathode starts) for degradations that throttling can absorb. |
| `XE_FALLBACK` | degraded | all | as in the source state; off after a pre-ionizer loss / as in the source state; off after a pre-ionizer loss | `mdot_Xe_cathode + mdot_Xe_anode` | Keeps the discharge lit on the independent Xe path so that an atmospheric-path anomaly does not force a restart. |
| `CONTROLLED_SHUTDOWN` | safing | all | off first in the sequence / off first in the sequence | `mdot_Xe_cathode + mdot_Xe_anode` | The only exits are to OFF (sequence complete) or SAFE_MODE (fault or time-out), so a shutdown never re-enters operation. |
| `RESTART` | recovery | all | off / off | `none: all Xe valves closed while eligibility is evaluated` | Makes restart a checked, counted decision instead of a re-entry into the start sequence. |
| `SAFE_MODE` | safe | all | off / off | `none: all Xe valves closed` | Hard-fault sink. Leaves only by ground command to OFF; restart then goes through OFF and RESTART. |

## Transitions (summary; guards, actions, fault behaviour and Xe consumed are in the JSON)

| from | transition id | to | kind | applies to |
|---|---|---|---|---|
| `OFF` | OFF__start | `XE_PURGE` | command | all |
| `XE_PURGE` | XE_PURGE__done | `CATHODE_CONDITIONING` | nominal | all |
| `CATHODE_CONDITIONING` | CATHODE_CONDITIONING__hot | `CATHODE_IGNITION` | nominal | all |
| `CATHODE_IGNITION` | CATHODE_IGNITION__coupled | `XE_DISCHARGE_IGNITION` | nominal | hall_only, rf_hall/V1, ecr_hall/V1 |
| `CATHODE_IGNITION` | CATHODE_IGNITION__retry | `CATHODE_IGNITION` | retry | all |
| `CATHODE_IGNITION` | CATHODE_IGNITION__exhausted | `CONTROLLED_SHUTDOWN` | protective | all |
| `XE_DISCHARGE_IGNITION` | XE_DISCHARGE_IGNITION__lit | `WARM_UP` | nominal | all |
| `XE_DISCHARGE_IGNITION` | XE_DISCHARGE_IGNITION__retry | `XE_DISCHARGE_IGNITION` | retry | all |
| `XE_DISCHARGE_IGNITION` | XE_DISCHARGE_IGNITION__exhausted | `CONTROLLED_SHUTDOWN` | protective | all |
| `WARM_UP` | WARM_UP__admit | `ATMOSPHERE_ADMISSION` | nominal | hall_only |
| `WARM_UP` | WARM_UP__no_atm | `XE_FALLBACK` | degradation | all |
| `WARM_UP` | WARM_UP__low_xe | `CONTROLLED_SHUTDOWN` | protective | all |
| `WARM_UP` | WARM_UP__timeout | `CONTROLLED_SHUTDOWN` | protective | all |
| `ATMOSPHERE_ADMISSION` | ATMOSPHERE_ADMISSION__stable | `MIXED_STABILIZATION` | nominal | all |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__dominant | `ATMOSPHERE_DOMINANT` | nominal | all |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__air_only | `AIR_ONLY_ANODE_XE_CATHODE` | nominal | all |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY__topping | `ATMOSPHERE_DOMINANT` | nominal | all |
| `ATMOSPHERE_ADMISSION` | ATMOSPHERE_ADMISSION__fallback | `XE_FALLBACK` | degradation | all |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__fallback | `XE_FALLBACK` | degradation | all |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__fallback | `XE_FALLBACK` | degradation | all |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY_ANODE_XE_CATHODE__fallback | `XE_FALLBACK` | degradation | all |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__fallback | `XE_FALLBACK` | degradation | all |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__degrade | `DEGRADED_OPERATION` | degradation | all |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__degrade | `DEGRADED_OPERATION` | degradation | all |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY_ANODE_XE_CATHODE__degrade | `DEGRADED_OPERATION` | degradation | all |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__recover_atmosphere_dominant | `ATMOSPHERE_DOMINANT` | recovery | all |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__recover_mixed_stabilization | `MIXED_STABILIZATION` | recovery | all |
| `XE_FALLBACK` | XE_FALLBACK__readmit | `ATMOSPHERE_ADMISSION` | recovery | hall_only |
| `WARM_UP` | WARM_UP__protect | `CONTROLLED_SHUTDOWN` | protective | all |
| `ATMOSPHERE_ADMISSION` | ATMOSPHERE_ADMISSION__protect | `CONTROLLED_SHUTDOWN` | protective | all |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__protect | `CONTROLLED_SHUTDOWN` | protective | all |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__protect | `CONTROLLED_SHUTDOWN` | protective | all |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY_ANODE_XE_CATHODE__protect | `CONTROLLED_SHUTDOWN` | protective | all |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__protect | `CONTROLLED_SHUTDOWN` | protective | all |
| `XE_FALLBACK` | XE_FALLBACK__protect | `CONTROLLED_SHUTDOWN` | protective | all |
| `XE_PURGE` | XE_PURGE__protect | `CONTROLLED_SHUTDOWN` | protective | all |
| `CATHODE_CONDITIONING` | CATHODE_CONDITIONING__timeout | `CONTROLLED_SHUTDOWN` | protective | all |
| `XE_PURGE` | XE_PURGE__stop | `CONTROLLED_SHUTDOWN` | command | all |
| `CATHODE_CONDITIONING` | CATHODE_CONDITIONING__stop | `CONTROLLED_SHUTDOWN` | command | all |
| `CATHODE_IGNITION` | CATHODE_IGNITION__stop | `CONTROLLED_SHUTDOWN` | command | all |
| `XE_DISCHARGE_IGNITION` | XE_DISCHARGE_IGNITION__stop | `CONTROLLED_SHUTDOWN` | command | all |
| `WARM_UP` | WARM_UP__stop | `CONTROLLED_SHUTDOWN` | command | all |
| `ATMOSPHERE_ADMISSION` | ATMOSPHERE_ADMISSION__stop | `CONTROLLED_SHUTDOWN` | command | all |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__stop | `CONTROLLED_SHUTDOWN` | command | all |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__stop | `CONTROLLED_SHUTDOWN` | command | all |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY_ANODE_XE_CATHODE__stop | `CONTROLLED_SHUTDOWN` | command | all |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__stop | `CONTROLLED_SHUTDOWN` | command | all |
| `XE_FALLBACK` | XE_FALLBACK__stop | `CONTROLLED_SHUTDOWN` | command | all |
| `CONTROLLED_SHUTDOWN` | CONTROLLED_SHUTDOWN__complete | `OFF` | nominal | all |
| `CONTROLLED_SHUTDOWN` | CONTROLLED_SHUTDOWN__timeout | `SAFE_MODE` | fault | all |
| `OFF` | OFF__restart | `RESTART` | command | all |
| `RESTART` | RESTART__cold | `XE_PURGE` | recovery | all |
| `RESTART` | RESTART__warm | `CATHODE_CONDITIONING` | recovery | all |
| `RESTART` | RESTART__ineligible | `OFF` | protective | all |
| `RESTART` | RESTART__abort | `OFF` | command | all |
| `SAFE_MODE` | SAFE_MODE__clear | `OFF` | command | all |
| `OFF` | OFF__fault | `SAFE_MODE` | fault | all |
| `XE_PURGE` | XE_PURGE__fault | `SAFE_MODE` | fault | all |
| `CATHODE_CONDITIONING` | CATHODE_CONDITIONING__fault | `SAFE_MODE` | fault | all |
| `CATHODE_IGNITION` | CATHODE_IGNITION__fault | `SAFE_MODE` | fault | all |
| `XE_DISCHARGE_IGNITION` | XE_DISCHARGE_IGNITION__fault | `SAFE_MODE` | fault | all |
| `WARM_UP` | WARM_UP__fault | `SAFE_MODE` | fault | all |
| `ATMOSPHERE_ADMISSION` | ATMOSPHERE_ADMISSION__fault | `SAFE_MODE` | fault | all |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__fault | `SAFE_MODE` | fault | all |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__fault | `SAFE_MODE` | fault | all |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY_ANODE_XE_CATHODE__fault | `SAFE_MODE` | fault | all |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__fault | `SAFE_MODE` | fault | all |
| `XE_FALLBACK` | XE_FALLBACK__fault | `SAFE_MODE` | fault | all |
| `CONTROLLED_SHUTDOWN` | CONTROLLED_SHUTDOWN__fault | `SAFE_MODE` | fault | all |
| `RESTART` | RESTART__fault | `SAFE_MODE` | fault | all |
| `CATHODE_IGNITION` | CATHODE_IGNITION__seed | `PREIONIZER_SEED` | nominal | rf_hall/V2, ecr_hall/V2 |
| `PREIONIZER_SEED` | PREIONIZER_SEED__lit | `XE_DISCHARGE_IGNITION` | nominal | rf_hall/V2, ecr_hall/V2 |
| `PREIONIZER_SEED` | PREIONIZER_SEED__retry | `PREIONIZER_SEED` | retry | rf_hall/V2, ecr_hall/V2 |
| `PREIONIZER_SEED` | PREIONIZER_SEED__exhausted | `CONTROLLED_SHUTDOWN` | protective | rf_hall/V2, ecr_hall/V2 |
| `WARM_UP` | WARM_UP__preionize | `PREIONIZER_IGNITION` | nominal | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `PREIONIZER_IGNITION` | PREIONIZER_IGNITION__lit | `ATMOSPHERE_ADMISSION` | nominal | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `PREIONIZER_IGNITION` | PREIONIZER_IGNITION__retry | `PREIONIZER_IGNITION` | retry | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `PREIONIZER_IGNITION` | PREIONIZER_IGNITION__exhausted | `CONTROLLED_SHUTDOWN` | protective | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `PREIONIZER_IGNITION` | PREIONIZER_IGNITION__protect | `CONTROLLED_SHUTDOWN` | protective | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `PREIONIZER_SEED` | PREIONIZER_SEED__protect | `CONTROLLED_SHUTDOWN` | protective | rf_hall/V2, ecr_hall/V2 |
| `PREIONIZER_SEED` | PREIONIZER_SEED__stop | `CONTROLLED_SHUTDOWN` | command | rf_hall/V2, ecr_hall/V2 |
| `PREIONIZER_SEED` | PREIONIZER_SEED__fault | `SAFE_MODE` | fault | rf_hall/V2, ecr_hall/V2 |
| `PREIONIZER_IGNITION` | PREIONIZER_IGNITION__stop | `CONTROLLED_SHUTDOWN` | command | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `PREIONIZER_IGNITION` | PREIONIZER_IGNITION__fault | `SAFE_MODE` | fault | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `ATMOSPHERE_ADMISSION` | ATMOSPHERE_ADMISSION__preionizer_loss | `XE_FALLBACK` | degradation | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__preionizer_loss | `XE_FALLBACK` | degradation | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__preionizer_loss | `XE_FALLBACK` | degradation | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY_ANODE_XE_CATHODE__preionizer_loss | `XE_FALLBACK` | degradation | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__preionizer_loss | `XE_FALLBACK` | degradation | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |
| `XE_FALLBACK` | XE_FALLBACK__reionize | `PREIONIZER_IGNITION` | recovery | rf_hall/V1, rf_hall/V2, ecr_hall/V1, ecr_hall/V2 |

## Guard quantities and simulator suppliers

Each guard quantity names the `abep_sim` function(s) that could supply it, and the test suite resolves them against
the source. Each supplier has a status:

- `available`: the function exists and returns this output. Its coefficients may still be unsourced code priors
  (noted).
- `input_only`: the function takes this quantity as an input. It does not compute it.
- `component_only`: the function returns one component load of `P_bus`, or a differently defined power. It can feed
  `bus_power_ledger` but never substitutes for `P_bus`.
- `proxy_not_equivalent`: the function returns a related model quantity that is not this quantity. It is listed only
  for traceability. Example: `abep_sim.reservoir:Reservoir.steady_state` → `mdot_leak` is chamber outflow minus anode
  delivery, a model split, not an external leak.
- `gated`: `abep_sim.hall_map:HallMap` loads admitted transport-ensemble members only. The credible set is ∅, so
  nothing can be supplied until a closure is admitted and design-specific Hall maps exist.
- `withdrawn_absolute`: the structure can be reused for control-logic prototyping, but absolute values are not
  quotable. For example, the `abep_sim.thruster` cards are calibrated partly to the withdrawn Marchioni calibration,
  which used an invented geometry.
- `superseded_do_not_use`: the 0-D Hall closure (`abep_sim.plasma_devices:hall_run_coupled` and relatives). It is
  listed only so that nobody wires it in, and a test forbids any other status for it.

`lazy` marks a supplier in a module owned by another lane:
- `abep_sim.arch_boundary`: lane_11_bus_boundary;
- `abep_sim.cathode_integration`: lane_19_cathode_integration.

These modules are never imported. The tests resolve such a reference when the file is present and skip it when it is
absent.

Where no `available` supplier exists, the gap column states what is required (`TBD — requires …`) or why none is
needed (`n/a:` for flight-software timers, counters and commands).

| quantity | unit | kind | simulator supplier(s) — `module:function` → output [status] | gap |
|---|---|---|---|---|
| `t_in_state` | s | timer | none | n/a: flight-software timer/counter, not a physics quantity |
| `t_condition` | s | timer | none | n/a: flight-software timer/counter, not a physics quantity |
| `t_since_shutdown` | s | timer | none | n/a: flight-software timer/counter, not a physics quantity |
| `t_since_purge` | s | timer | none | n/a: flight-software timer/counter, not a physics quantity |
| `t_atm_exposure` | s | timer | `abep_sim.aochem:ao_flux` → ao_flux [available] | TBD — requires a cathode O-exposure dose model and test; the timer itself is controller-internal |
| `t_atm_healthy` | s | timer | none | n/a: flight-software timer/counter, not a physics quantity |
| `t_to_eclipse` | s | estimated | `abep_sim.mission_env:eclipse_fraction` → orbit-averaged eclipse fraction [available]<br>`abep_sim.mission_env:beta_angle` → beta angle [available] | TBD — requires an eclipse-entry-time predictor (abep_sim.mission_env gives orbit-averaged eclipse fraction only) |
| `n_keeper_retry` | - | counter | none | n/a: flight-software timer/counter, not a physics quantity |
| `n_ignite_retry` | - | counter | none | n/a: flight-software timer/counter, not a physics quantity |
| `n_restart_count` | - | counter | none | n/a: flight-software timer/counter, not a physics quantity |
| `n_fallback_cycles` | - | counter | none | n/a: flight-software timer/counter, not a physics quantity |
| `n_cathode_starts` | - | counter | `abep_sim.life:cathode_life` → cycles_ok [available] | — |
| `cmd_start` | bool | command | none | n/a: flight-software timer/counter, not a physics quantity |
| `cmd_stop` | bool | command | none | n/a: flight-software timer/counter, not a physics quantity |
| `cmd_restart` | bool | command | none | n/a: flight-software timer/counter, not a physics quantity |
| `cmd_ground_clear` | bool | command | none | n/a: flight-software timer/counter, not a physics quantity |
| `autonomy_restart_enabled` | bool | configuration | none | n/a: flight-software timer/counter, not a physics quantity |
| `restart_requested` | bool | flag | none | n/a: flight-software timer/counter, not a physics quantity |
| `p_Xe_tank` | Pa | measured | `abep_sim.mass_bom:xe_tank` → tank mass at a given storage pressure [input_only] | TBD — requires a Xe tank PVT/blow-down model and transducer specification |
| `p_Xe_line` | Pa | measured | none | TBD — requires a Xe feed-system (regulator/plenum) model; none exists in abep_sim |
| `m_Xe_remaining` | kg | estimated | `abep_sim.transient:run_mission` → xe_left_kg, xe_used_total_kg [withdrawn_absolute] | TBD — requires a Xe gauging method and a mission Xe budget from admitted design Hall maps |
| `mdot_Xe_cathode` | kg/s | measured | `abep_sim.plasma_devices:LaB6Cathode.operate` → xe_mgps [input_only]<br>`abep_sim.archengine:Neutralizer.operate` → xe_mgps attribute [input_only] | n/a: commanded flow, measured by the flow controller; the simulator consumes it as an input (setpoint mdot_Xe_cathode_set is TBD) |
| `mdot_Xe_anode` | kg/s | measured | `abep_sim.thruster:performance` → mdot_xe_anode argument [input_only]<br>`abep_sim.thruster:xe_for_thrust` → anode Xe flow for a thrust target [withdrawn_absolute] | n/a: commanded flow, measured by the flow controller; a thrust-based Xe topping flow needs admitted design Hall maps (TBD — requires an admitted transport-ensemble member) |
| `mdot_Xe_purge` | kg/s | measured | none | TBD — requires a purge procedure (flow path and setpoint) from feed-system design |
| `mdot_leak_est` | kg/s | estimated | `abep_sim.reservoir:Reservoir.steady_state` → mdot_leak [proxy_not_equivalent] | TBD — requires a feed-system leak specification and a leak-detection method (pressure decay / flow balance) for both the Xe and the atmospheric path |
| `p_O_cathode_est` | Pa | estimated | `abep_sim.plasma_devices:LaB6Cathode.operate` → p_O_at_emitter_Pa [available]<br>`abep_sim.atmosphere:atmosphere` → rho, fO (frozen NRLMSIS 2.1) [available]<br>`abep_sim.aochem:inlet_composition` → fO after wall recombination [available]<br>`abep_sim.cathode_integration:oxygen_poisoning_screen` → O2 screen status (NO_QUANTITATIVE_EVIDENCE for atomic O / N2) [available, lazy] | TBD — requires a sourced LaB6 atomic-O tolerance (lane_19 records NO_QUANTITATIVE_EVIDENCE for atomic O and N2 in the accessed sources) and a cathode O-exposure test; the estimate is a code-prior model (verify) |
| `T_emitter` | K | measured | `abep_sim.plasma_devices:LaB6Cathode.operate` → T_emitter_K [available] | TBD — requires the measurement method from cathode design |
| `P_heater` | W | measured | `abep_sim.ppu:load_modes` → startup (heater converter) [available]<br>`abep_sim.plasma_devices:LaB6Cathode.operate` → P_W [available]<br>`abep_sim.cathode_integration:startup_transient` → cathode_heater load per start-up phase and cathode energy [input_only, lazy] | — |
| `I_keeper` | A | measured | `abep_sim.ppu:load_modes` → I_keeper argument [input_only]<br>`abep_sim.cathode_integration:electron_current_budget` → I_keeper_A in I_emit = I_d + I_keeper + I_interstage [input_only, lazy]<br>`abep_sim.cathode_integration:steady_cathode_boundary_loads_W` → cathode_keeper load [input_only, lazy] | TBD — requires keeper discharge characterization test; abep_sim has keeper current/power bookkeeping (abep_sim.cathode_integration, lane_19) but no keeper discharge model |
| `V_keeper` | V | measured | none | TBD — requires keeper discharge characterization test |
| `I_d` | A | measured | `abep_sim.hall_map:HallMap.__call__` → discharge_current_A [gated]<br>`abep_sim.plasma_devices:hall_run_coupled` → 0-D discharge current [superseded_do_not_use] | TBD — requires an admitted transport-ensemble member with design-specific Hall maps and, for atmospheric or mixed feeds, O/O2 chemistry and Xe + atmosphere mixture support; ultimately a thruster test |
| `I_d_ref` | A | setpoint | none | TBD — requires a throttle table from admitted design Hall maps and thruster test |
| `Id_rms_rel` | - | measured | `abep_sim.hall_map:HallMap.__call__` → Id_rms_rel [gated] | TBD — requires thruster test (oscillation behaviour on mixed and atmospheric feed is not modelled) |
| `T_thruster` | K | measured | `abep_sim.thermal:solve_network` → T['thruster'] (steady state) [available] | TBD — requires a transient thermal model or thruster thermal test for warm-up timing |
| `thermal_warn` | bool | flag | `abep_sim.thermal:solve_network` → node temperatures [available]<br>`abep_sim.thermal:default_nodes` → node list and T_max_K [available] | — |
| `thermal_trip` | bool | flag | `abep_sim.thermal:solve_network` → node temperatures [available] | — |
| `compressor_speed` | rpm | measured | `abep_sim.compressor:DragCompressor.rpm_limit` → rotor-stress speed limit [available]<br>`abep_sim.compressor:DragCompressor.run` → rotor_ok, p_out_Pa at a given rpm [available] | — |
| `compressor_fault` | bool | flag | `abep_sim.compressor:DragCompressor.run` → rotor_ok, T_comp_K [available] | TBD — requires compressor FDIR design (bearing/motor telemetry) |
| `compressor_derated` | bool | flag | none | TBD — requires compressor FDIR design |
| `atm_path_fault` | bool | flag | none | TBD — requires intake/filter/valve FDIR design |
| `p_atm_chamber` | Pa | measured | `abep_sim.reservoir:Reservoir.steady_state` → p_total_Pa [available]<br>`abep_sim.reservoir:startup_transient` → t_ignite_s, history [available]<br>`abep_sim.compressor:DragCompressor.run` → p_out_Pa [available]<br>`abep_sim.intake:compress` → p_out_Pa [available] | — |
| `mdot_atm_anode` | kg/s | estimated | `abep_sim.reservoir:Reservoir.steady_state` → mdot_anode [available]<br>`abep_sim.intake:collection` → mdot_collected [available] | — |
| `x_atm_anode` | - | derived | none | n/a: derived from other declared quantities |
| `P_bus` | W | measured | `abep_sim.arch_boundary:bus_power_ledger` → P_bus_W [available, lazy]<br>`abep_sim.ppu:PPU.loads` → P_bus_W (PPU-internal definition) [component_only]<br>`abep_sim.compressor:DragCompressor.run` → P_el_W (compressor component load) [component_only]<br>`abep_sim.intake:compress` → comp_power_W (compressor component load, simple model) [component_only] | — |
| `P_bus_demand` | W | estimated | `abep_sim.arch_boundary:bus_power_ledger` → P_bus_W at the commanded loads [available, lazy]<br>`abep_sim.ppu:load_modes` → steady/startup P_bus_W (PPU-internal definition) [component_only]<br>`abep_sim.cathode_integration:startup_transient` → per-phase load profile on boundary components [component_only, lazy] | — |
| `V_bus` | V | measured | `abep_sim.ppu:PPU` → V_bus attribute [input_only] | TBD — requires the spacecraft EPS specification |
| `ppu_fault` | bool | flag | `abep_sim.ppu:PPU.loads` → rating_ok, violations [available] | TBD — requires PPU FDIR design |
| `hv_fault` | bool | flag | none | TBD — requires PPU FDIR design |
| `valve_fault` | bool | flag | none | TBD — requires feed-system FDIR design |
| `sensor_redundancy_lost` | bool | flag | none | TBD — requires sensor architecture and FDIR design |
| `watchdog_fault` | bool | flag | none | TBD — requires flight-software design |
| `T_cmd` | mN | setpoint | `abep_sim.transient:run_mission` → T_cmd_mN [available] | — |
| `T_air_avail` | mN | estimated | `abep_sim.thruster:performance` → T_N [withdrawn_absolute]<br>`abep_sim.hall_map:HallMap.__call__` → thrust_N [gated] | TBD — requires an on-board thrust estimator validated by thruster test on atmospheric feed |
| `P_bus_avail` | W | estimated | `abep_sim.mission_env:propagate` → P_avail_W, power_margin_W [available] | TBD — requires the spacecraft EPS interface (battery state of charge, array power) from the spacecraft prime |
| `I_interstage` | A | measured | `abep_sim.cathode_integration:electron_current_budget` → I_interstage_A (input) -> I_emit_A [input_only, lazy] | TBD — requires interstage circuit design and pre-ionizer test (lane_18_interstage) |
| `preionizer_lit` | bool | flag | none | TBD — requires a pre-ionizer plasma-detection method from source design and test (docs/evidence/rf_source/, docs/evidence/ecr_source/) |
| `preionizer_fault` | bool | flag | none | TBD — requires pre-ionizer FDIR design |
| `n_preion_retry` | - | counter | none | n/a: flight-software timer/counter, not a physics quantity |

## Parameters

All 83 parameters (thresholds, setpoints, timers, retry limits, reserves) are listed in the JSON. Each has:

- a unit and a description;
- `value: "TBD — requires <model/test>"`, `source: null` and `evidence_class: null`;
- where applicable, `determined_by`: simulator functions that could later help size it.

`parameter_constraints` lists the ordering relations that any future values must satisfy, e.g.:

- `I_d_off_max < I_d_detect_min < I_d_overcurrent_max`;
- `m_Xe_reserve_shutdown <= m_Xe_reserve_restart <= m_Xe_reserve_startup`;
- `P_startup_peak <= P_bus_alloc <= RFP_power_max`;
- `V_d_ign <= V_d_op`.

No values are proposed here. In particular, none is derived from the withdrawn 0-D Hall results.

## What the tests check

- The five configurations cover `hall_only`, `rf_hall` and `ecr_hall`, with the bus_power_boundary_v1 pre-ionizer
  components.
- Per configuration:
  - every required state is present and reachable from `OFF`;
  - every non-terminal state has a path to a safe state (`SAFE_MODE`, or `OFF` via `CONTROLLED_SHUTDOWN`) and a
    direct fault exit to `SAFE_MODE`.
- `hall_only` never enters a pre-ionizer state. `rf_hall` and `ecr_hall` reach atmosphere admission only through
  `PREIONIZER_IGNITION`, and V2 reaches anode ignition only through `PREIONIZER_SEED`.
- Every state that energises a pre-ionizer has a pre-ionizer fault exit to `SAFE_MODE`. Every operating/degraded state
  with the pre-ionizer on has a loss exit to `XE_FALLBACK`.
- The safing state exits only to safe states. Every `fault` transition ends in a safe state. Safe states are
  de-energised and fail-closed. Retry loops are bounded.
- Every transition has the required fields, all five guard categories and a valid `applies_to`. The Xe ledger matches
  the state rates.
- Power guards use only the `P_bus` family. `P_bus` and `P_bus_demand` are supplied by `bus_power_ledger`, and every
  other supplier is `component_only` or `input_only`. When `abep_sim/arch_boundary.py` is present, it agrees with this
  specification.
- Every expression symbol is declared, and every declared symbol is used.
- No numeric literal appears in guards or actions, or anywhere outside sourced parameters. Parameter values are TBD, or
  sourced with an evidence class.
- Simulator references resolve to real code (other-lane modules lazily). The 0-D Hall closure is never an active
  supplier, and `HallMap` is gated while the credible set is empty. No calibration-nuisance variable leaks in.
- Milestone, verification, air-cathode exclusion and literature-pointer records are present. This document names every
  state and every guard quantity.

## Open items (all TBD)

- Pre-ionizer: start variant V1 or V2 per architecture, the plasma-detection method (`preionizer_lit`), the interstage
  circuit (`I_interstage`), pre-ionizer FDIR, and the policy on exhausted pre-ionizer retries.
- Xe feed system: design (regulator, plenum, purge path, leak specification and detection for both paths), Xe gauging,
  and a mission Xe budget per architecture.
- Cathode:
  - keeper characterization;
  - a sourced atomic-O tolerance and an O-exposure test;
  - a start-count limit (the `abep_sim.life` limit is a code prior: verify);
  - an air-fed cathode test if that branch is to be reopened.
- Discharge: ignition, admission, mixed and air-only behaviour. These require an admitted transport closure, O/O₂ and
  mixture chemistry, design Hall maps and thruster test. The oscillation limit (`Id_rms_rel_max`) requires test.
- Thermal: a transient thermal model for warm-up timing.
- FDIR designs for the compressor, PPU, valves, sensors and watchdog.
- Spacecraft EPS interface: bus voltage, available power at the boundary (`P_bus_avail`) and eclipse-entry prediction.
