# Dual-feed (Xe + atmosphere) operational state machine — v1 (DRAFT)

Machine-readable specification: `schemas/controls/dual_feed_state_machine_v1.json`.
Structural checks: `tests/test_dual_feed_state_machine.py` (run `python -m pytest -q tests/test_dual_feed_state_machine.py`).

## Status and scope

- **Conceptual control-logic specification, not validated.** Every guard is symbolic. All 79 named parameters carry
  `value: "TBD — requires <model/test>"`; none has a sourced number yet. A parameter gets a value only together with a
  `source` and an `evidence_class` (measured / digitized / inferred / reconstructed / model-derived / assumed, per
  docs/EVIDENCE.md), and the test suite rejects any other numeric value anywhere in the file.
- **It asserts nothing about discharge physics.** Gate 3 is FAIL and the credible transport set is ∅ (CLAUDE.md), so no
  design Hall map exists. The simulator does **not** establish whether a Hall discharge can be ignited on Xe and then
  transferred to, sustained on, or throttled on atmospheric or mixed feed. HallThruster.jl reaction sets cover Xe
  and N₂/N only: no O/O₂ chemistry and no Xe + atmosphere mixture. The states below are the sequence a controller would
  need *if* those regimes exist. The guards that decide them (e.g. `I_d`, `Id_rms_rel`, `T_air_avail`) are marked gated.
- **RFP basis:** air + Xe propellants, Hall preferred, power < 1.5 kW, 12–25 mN (CLAUDE.md; `abep_sim.constants:RFPConstraints`,
  transcribed from RFP Part III Para 2. The RFP text is not in the repository, so verify). The RFP does not enumerate these
  states (verify). The state list is a Vyovrinda control-design proposal.
- **Architecture scope rule:** the atmospheric path is intake → filter → compressor → atmospheric gas chamber →
  atmospheric valve (`atm_anode`). The Xe path is Xe chamber → Xe valves (`xe_cathode`, `xe_anode`). Both feed the
  ionization/discharge → acceleration/thrust block. Hall transport-ensemble uncertainty belongs to that block only and is
  never used as an upstream guard quantity. Layer-1 calibration-nuisance variables (P5 registration, coil shape,
  beam-efficiency reading, facility ingestion) are never guard quantities or parameters. A test enforces this against
  `hallthruster_bridge/ensemble/transport_ensemble_v0.json`.

## Design rationale

1. **Ignite on Xe, then transfer.** The Xe path is independent of intake/compressor state, so the start sequence
   (`XE_PURGE` → `CATHODE_CONDITIONING` → `CATHODE_IGNITION` → `XE_DISCHARGE_IGNITION` → `WARM_UP`) never depends on the
   atmospheric path. Atmospheric species are admitted into an established discharge (`ATMOSPHERE_ADMISSION`). The
   anode feed is then transferred gradually (`MIXED_STABILIZATION` → `ATMOSPHERE_DOMINANT` → `AIR_ONLY_ANODE_XE_CATHODE`),
   so every step has a reversible exit to `XE_FALLBACK`.
2. **Xe-fed cathode throughout.** The repository's cathode model treats atomic O as an emitter poison
   (`abep_sim.plasma_devices:LaB6Cathode.coverage`; `abep_sim.aochem` material class notes LaB6 must be Xe-shielded).
   The air-cathode closure also did not close the discharge current at life (docs/HISTORY.md v1.1 item 3, model-derived: "a
   test, not a design choice"). Hence the machine purges before heating, heats only under Xe flow, and uses
   `AIR_ONLY_ANODE_XE_CATHODE` rather than a fully air-fed mode. Cathode Xe flow and cathode start count are therefore
   mission consumables.
3. **Warm-up overlaps the chamber fill.** `WARM_UP` spins up the compressor while the thruster soaks on Xe, so admission
   starts from a filled atmospheric chamber (`abep_sim.reservoir:startup_transient` gives the fill transient).
4. **Two safe sinks, one safing state.** `OFF` and `SAFE_MODE` are the safe states (de-energised, valves fail-closed).
   `CONTROLLED_SHUTDOWN` is the only safing state. It exits only to `OFF` (complete) or `SAFE_MODE` (fault or time-out).
   Every non-safe state has a direct `fault` transition to `SAFE_MODE`. Every operating and startup state has a
   `protective` transition to `CONTROLLED_SHUTDOWN` and a `command` stop.
5. **Bounded retries and counted restarts.** Keeper and anode-ignition retries are self-loops bounded by counters
   (`n_keeper_retry_max`, `n_ignite_retry_max`), and exhausting them is protective. `RESTART` is a checked eligibility
   decision (inhibit time, restart counter, Xe reserve, cathode starts), not a re-entry into the start sequence.
   `SAFE_MODE` exits only by ground command to `OFF`.
6. **Degrade before shutting down.** `DEGRADED_OPERATION` absorbs anomalies that throttling can handle, because a
   shutdown/restart costs Xe and a cathode start. `XE_FALLBACK` keeps the discharge lit when the atmospheric path is
   anomalous, with a bounded number of fallback/readmission cycles (`n_fallback_cycles_max`).
7. **Xe ledger.** Each state declares a symbolic Xe rate. Each transition declares `xe_consumed.in_source_state` and
   `xe_consumed.at_transition`. Summing along a path gives the Xe cost of a sequence. The reserve parameters
   (`m_Xe_reserve_startup`, `m_Xe_reserve_restart`, `m_Xe_reserve_fallback`, `m_Xe_reserve_shutdown`, ordered by
   `parameter_constraints`) must cover it. Their values are TBD: they require admitted design Hall maps and a Xe gauging method.

## Guard semantics

- Each transition has `guards` with the five required categories (`pressure`, `discharge_current`, `flows`, `timing`,
  `power`), plus optional `thermal`, `inventory`, `sequence` and `health`. An entry beginning `n/a:` imposes no condition
  and states why.
- `guard_logic: ALL`: every condition holds, together with `preconditions`. `t_condition` counts how long the full set
  has held (success confirmation). `ANY_PERSISTING`: fires when any triggering condition holds continuously for the
  timing entries (fault/protective persistence filters, e.g. `t_fault_confirm`).
- Priority in each control cycle: fault > protective > command > degradation > recovery > nominal > retry.
- Expressions use only declared quantities, parameters and external refs (`RFP_power_max`, `RFP_thrust_max`), plus the
  operators in `expression_grammar`. They contain no numeric literals.
- Each transition has `fault_behaviour` (`on_fault`, `fault_transition`, `on_guard_not_met`, `description`).
- Global invariants: `T_cmd <= RFP_thrust_max` and `P_prop <= P_prop_alloc` (with `P_prop_alloc <= RFP_power_max`).

## States

| state | category | Xe consumed (rate expression) | rationale |
|---|---|---|---|
| `OFF` | safe | `none: all Xe valves closed` | Initial and final state. Exits only on a start/restart command or on a fault latched while off. |
| `XE_PURGE` | startup | `mdot_Xe_purge` | The repository's cathode model treats atomic O as an emitter poison (abep_sim.plasma_devices:LaB6Cathode.coverage; abep_sim.aochem MATERIAL_CLASS 'LaB6 ... must be Xe-shielded'); purging before heating follows from that model. The need for, and duration of, a purge is TBD — requires cathode O-exposure test. |
| `CATHODE_CONDITIONING` | startup | `mdot_Xe_cathode` | Emitter heating under Xe flow so the emitter is not heated in an O-bearing environment without flow. |
| `CATHODE_IGNITION` | startup | `mdot_Xe_cathode` | Separates keeper coupling from anode ignition so that a keeper failure never reaches the anode supply. |
| `XE_DISCHARGE_IGNITION` | startup | `mdot_Xe_cathode + mdot_Xe_anode` | Ignition on Xe only: the Xe path is independent of the atmospheric path, so ignition does not depend on intake/compressor state. Whether a discharge on atmospheric feed could be ignited directly is not assumed. |
| `WARM_UP` | startup | `mdot_Xe_cathode + mdot_Xe_anode` | Overlaps thruster warm-up with the atmospheric chamber fill transient (abep_sim.reservoir:startup_transient) so that admission starts from a filled chamber and a thermally soaked thruster. |
| `ATMOSPHERE_ADMISSION` | operating | `mdot_Xe_cathode + mdot_Xe_anode` | Introduces atmospheric species into an established Xe discharge instead of igniting on atmospheric feed. Whether the discharge survives admission is not modelled (no admitted Hall member; no O/O2 chemistry; no Xe + atmosphere mixture) and is a test item. |
| `MIXED_STABILIZATION` | operating | `mdot_Xe_cathode + mdot_Xe_anode` | Transfers the discharge from Xe to atmospheric feed gradually so each step can be reversed to Xe fallback. |
| `ATMOSPHERE_DOMINANT` | operating | `mdot_Xe_cathode + mdot_Xe_anode` | Mirrors the Xe-topping policy structure of abep_sim.transient:run_mission (air first, Xe anode topping when air thrust is short). |
| `AIR_ONLY_ANODE_XE_CATHODE` | operating | `mdot_Xe_cathode` | Keeps an Xe-fed cathode because the repository's air-cathode closure did not close the current at life (docs/HISTORY.md v1.1 item 3, model-derived; 'a test, not a design choice'). Xe consumption in this state is the cathode flow only. |
| `DEGRADED_OPERATION` | degraded | `mdot_Xe_cathode + mdot_Xe_anode` | Avoids a shutdown/restart cycle (which costs Xe and cathode starts) for degradations that throttling can absorb. |
| `XE_FALLBACK` | degraded | `mdot_Xe_cathode + mdot_Xe_anode` | Keeps the discharge lit on the independent Xe path so that an atmospheric-path anomaly does not force a restart. |
| `CONTROLLED_SHUTDOWN` | safing | `mdot_Xe_cathode + mdot_Xe_anode` | The only exits are to OFF (sequence complete) or SAFE_MODE (fault or time-out), so a shutdown never re-enters operation. |
| `RESTART` | recovery | `none: all Xe valves closed while eligibility is evaluated` | Makes restart a checked, counted decision instead of a re-entry into the start sequence. |
| `SAFE_MODE` | safe | `none: all Xe valves closed` | Hard-fault sink. Leaves only by ground command to OFF; restart then goes through OFF and RESTART. |

## Transitions (summary; guards, actions, fault behaviour and Xe consumed are in the JSON)

| from | transition id | to | kind |
|---|---|---|---|
| `OFF` | OFF__start | `XE_PURGE` | command |
| `XE_PURGE` | XE_PURGE__done | `CATHODE_CONDITIONING` | nominal |
| `CATHODE_CONDITIONING` | CATHODE_CONDITIONING__hot | `CATHODE_IGNITION` | nominal |
| `CATHODE_IGNITION` | CATHODE_IGNITION__coupled | `XE_DISCHARGE_IGNITION` | nominal |
| `CATHODE_IGNITION` | CATHODE_IGNITION__retry | `CATHODE_IGNITION` | retry |
| `CATHODE_IGNITION` | CATHODE_IGNITION__exhausted | `CONTROLLED_SHUTDOWN` | protective |
| `XE_DISCHARGE_IGNITION` | XE_DISCHARGE_IGNITION__lit | `WARM_UP` | nominal |
| `XE_DISCHARGE_IGNITION` | XE_DISCHARGE_IGNITION__retry | `XE_DISCHARGE_IGNITION` | retry |
| `XE_DISCHARGE_IGNITION` | XE_DISCHARGE_IGNITION__exhausted | `CONTROLLED_SHUTDOWN` | protective |
| `WARM_UP` | WARM_UP__admit | `ATMOSPHERE_ADMISSION` | nominal |
| `WARM_UP` | WARM_UP__no_atm | `XE_FALLBACK` | degradation |
| `WARM_UP` | WARM_UP__low_xe | `CONTROLLED_SHUTDOWN` | protective |
| `WARM_UP` | WARM_UP__timeout | `CONTROLLED_SHUTDOWN` | protective |
| `ATMOSPHERE_ADMISSION` | ATMOSPHERE_ADMISSION__stable | `MIXED_STABILIZATION` | nominal |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__dominant | `ATMOSPHERE_DOMINANT` | nominal |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__air_only | `AIR_ONLY_ANODE_XE_CATHODE` | nominal |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY__topping | `ATMOSPHERE_DOMINANT` | nominal |
| `ATMOSPHERE_ADMISSION` | ATMOSPHERE_ADMISSION__fallback | `XE_FALLBACK` | degradation |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__fallback | `XE_FALLBACK` | degradation |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__fallback | `XE_FALLBACK` | degradation |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY_ANODE_XE_CATHODE__fallback | `XE_FALLBACK` | degradation |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__fallback | `XE_FALLBACK` | degradation |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__degrade | `DEGRADED_OPERATION` | degradation |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__degrade | `DEGRADED_OPERATION` | degradation |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY_ANODE_XE_CATHODE__degrade | `DEGRADED_OPERATION` | degradation |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__recover_atmosphere_dominant | `ATMOSPHERE_DOMINANT` | recovery |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__recover_mixed_stabilization | `MIXED_STABILIZATION` | recovery |
| `XE_FALLBACK` | XE_FALLBACK__readmit | `ATMOSPHERE_ADMISSION` | recovery |
| `WARM_UP` | WARM_UP__protect | `CONTROLLED_SHUTDOWN` | protective |
| `ATMOSPHERE_ADMISSION` | ATMOSPHERE_ADMISSION__protect | `CONTROLLED_SHUTDOWN` | protective |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__protect | `CONTROLLED_SHUTDOWN` | protective |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__protect | `CONTROLLED_SHUTDOWN` | protective |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY_ANODE_XE_CATHODE__protect | `CONTROLLED_SHUTDOWN` | protective |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__protect | `CONTROLLED_SHUTDOWN` | protective |
| `XE_FALLBACK` | XE_FALLBACK__protect | `CONTROLLED_SHUTDOWN` | protective |
| `XE_PURGE` | XE_PURGE__protect | `CONTROLLED_SHUTDOWN` | protective |
| `CATHODE_CONDITIONING` | CATHODE_CONDITIONING__timeout | `CONTROLLED_SHUTDOWN` | protective |
| `XE_PURGE` | XE_PURGE__stop | `CONTROLLED_SHUTDOWN` | command |
| `CATHODE_CONDITIONING` | CATHODE_CONDITIONING__stop | `CONTROLLED_SHUTDOWN` | command |
| `CATHODE_IGNITION` | CATHODE_IGNITION__stop | `CONTROLLED_SHUTDOWN` | command |
| `XE_DISCHARGE_IGNITION` | XE_DISCHARGE_IGNITION__stop | `CONTROLLED_SHUTDOWN` | command |
| `WARM_UP` | WARM_UP__stop | `CONTROLLED_SHUTDOWN` | command |
| `ATMOSPHERE_ADMISSION` | ATMOSPHERE_ADMISSION__stop | `CONTROLLED_SHUTDOWN` | command |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__stop | `CONTROLLED_SHUTDOWN` | command |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__stop | `CONTROLLED_SHUTDOWN` | command |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY_ANODE_XE_CATHODE__stop | `CONTROLLED_SHUTDOWN` | command |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__stop | `CONTROLLED_SHUTDOWN` | command |
| `XE_FALLBACK` | XE_FALLBACK__stop | `CONTROLLED_SHUTDOWN` | command |
| `CONTROLLED_SHUTDOWN` | CONTROLLED_SHUTDOWN__complete | `OFF` | nominal |
| `CONTROLLED_SHUTDOWN` | CONTROLLED_SHUTDOWN__timeout | `SAFE_MODE` | fault |
| `OFF` | OFF__restart | `RESTART` | command |
| `RESTART` | RESTART__cold | `XE_PURGE` | recovery |
| `RESTART` | RESTART__warm | `CATHODE_CONDITIONING` | recovery |
| `RESTART` | RESTART__ineligible | `OFF` | protective |
| `RESTART` | RESTART__abort | `OFF` | command |
| `SAFE_MODE` | SAFE_MODE__clear | `OFF` | command |
| `OFF` | OFF__fault | `SAFE_MODE` | fault |
| `XE_PURGE` | XE_PURGE__fault | `SAFE_MODE` | fault |
| `CATHODE_CONDITIONING` | CATHODE_CONDITIONING__fault | `SAFE_MODE` | fault |
| `CATHODE_IGNITION` | CATHODE_IGNITION__fault | `SAFE_MODE` | fault |
| `XE_DISCHARGE_IGNITION` | XE_DISCHARGE_IGNITION__fault | `SAFE_MODE` | fault |
| `WARM_UP` | WARM_UP__fault | `SAFE_MODE` | fault |
| `ATMOSPHERE_ADMISSION` | ATMOSPHERE_ADMISSION__fault | `SAFE_MODE` | fault |
| `MIXED_STABILIZATION` | MIXED_STABILIZATION__fault | `SAFE_MODE` | fault |
| `ATMOSPHERE_DOMINANT` | ATMOSPHERE_DOMINANT__fault | `SAFE_MODE` | fault |
| `AIR_ONLY_ANODE_XE_CATHODE` | AIR_ONLY_ANODE_XE_CATHODE__fault | `SAFE_MODE` | fault |
| `DEGRADED_OPERATION` | DEGRADED_OPERATION__fault | `SAFE_MODE` | fault |
| `XE_FALLBACK` | XE_FALLBACK__fault | `SAFE_MODE` | fault |
| `CONTROLLED_SHUTDOWN` | CONTROLLED_SHUTDOWN__fault | `SAFE_MODE` | fault |
| `RESTART` | RESTART__fault | `SAFE_MODE` | fault |

## Guard quantities and simulator suppliers

Each guard quantity names the `abep_sim` function(s) that could supply it (the test suite resolves them against the
source) and gives each one a status:

- `available`: the function exists and returns this output. Its coefficients may still be unsourced code priors (noted).
- `input_only`: the simulator takes this as an input; it does not compute it.
- `gated`: `abep_sim.hall_map:HallMap` loads admitted transport-ensemble members only. The credible set is ∅, so
  nothing can be supplied until a closure is admitted and design-specific Hall maps exist.
- `withdrawn_absolute`: the structure can be reused for control-logic prototyping, but absolute values are not
  quotable (e.g. the `abep_sim.thruster` cards are calibrated partly to the withdrawn Marchioni calibration, which used
  an invented geometry).
- `superseded_do_not_use`: the 0-D Hall closure (`abep_sim.plasma_devices:hall_run_coupled` and relatives). It is listed
  only so that nobody wires it in, and a test forbids any other status for it.

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
| `mdot_leak_est` | kg/s | estimated | `abep_sim.reservoir:Reservoir.steady_state` → mdot_leak [available] | TBD — requires a Xe feed-system leak specification and test |
| `p_O_cathode_est` | Pa | estimated | `abep_sim.plasma_devices:LaB6Cathode.operate` → p_O_at_emitter_Pa [available]<br>`abep_sim.atmosphere:atmosphere` → rho, fO (frozen NRLMSIS 2.1) [available]<br>`abep_sim.aochem:inlet_composition` → fO after wall recombination [available] | — |
| `T_emitter` | K | measured | `abep_sim.plasma_devices:LaB6Cathode.operate` → T_emitter_K [available] | TBD — requires the measurement method from cathode design |
| `P_heater` | W | measured | `abep_sim.ppu:load_modes` → startup (heater converter) [available]<br>`abep_sim.plasma_devices:LaB6Cathode.operate` → P_W [available] | — |
| `I_keeper` | A | measured | `abep_sim.ppu:load_modes` → I_keeper argument [input_only] | TBD — requires keeper discharge characterization test; no keeper model in abep_sim |
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
| `P_prop` | W | measured | `abep_sim.ppu:PPU.loads` → P_bus_W [available]<br>`abep_sim.compressor:DragCompressor.run` → P_el_W (compressor share) [available]<br>`abep_sim.intake:compress` → comp_power_W (compressor share, simple model) [available] | — |
| `P_prop_demand` | W | estimated | `abep_sim.ppu:load_modes` → steady/startup P_bus_W [available] | — |
| `P_avail_prop` | W | estimated | `abep_sim.mission_env:propagate` → P_avail_W, power_margin_W [available] | TBD — requires the spacecraft EPS interface (battery state of charge, array power) from the spacecraft prime |
| `V_bus` | V | measured | `abep_sim.ppu:PPU` → V_bus attribute [input_only] | TBD — requires the spacecraft EPS specification |
| `ppu_fault` | bool | flag | `abep_sim.ppu:PPU.loads` → rating_ok, violations [available] | TBD — requires PPU FDIR design |
| `hv_fault` | bool | flag | none | TBD — requires PPU FDIR design |
| `valve_fault` | bool | flag | none | TBD — requires feed-system FDIR design |
| `sensor_redundancy_lost` | bool | flag | none | TBD — requires sensor architecture and FDIR design |
| `watchdog_fault` | bool | flag | none | TBD — requires flight-software design |
| `T_cmd` | mN | setpoint | `abep_sim.transient:run_mission` → T_cmd_mN [available] | — |
| `T_air_avail` | mN | estimated | `abep_sim.thruster:performance` → T_N [withdrawn_absolute]<br>`abep_sim.hall_map:HallMap.__call__` → thrust_N [gated] | TBD — requires an on-board thrust estimator validated by thruster test on atmospheric feed |

## Parameters

All 79 parameters (thresholds, setpoints, timers, retry limits, reserves) are listed in the JSON. Each has a unit, a
description, `value: "TBD — requires <model/test>"`, `source: null` and `evidence_class: null`. Where applicable,
`determined_by` names simulator functions that could later help size it. `parameter_constraints` lists the ordering
relations that any future values must satisfy (e.g. `I_d_off_max < I_d_detect_min < I_d_overcurrent_max`,
`m_Xe_reserve_shutdown <= m_Xe_reserve_restart <= m_Xe_reserve_startup`, `P_prop_alloc <= RFP_power_max`,
`V_d_ign <= V_d_op`). No values are proposed here. In particular, none is derived from the withdrawn 0-D Hall results.

## What the tests check

- Every required state is present, and every state is reachable from `OFF`.
- Every non-terminal state has a path to a safe state (`SAFE_MODE`, or `OFF` via `CONTROLLED_SHUTDOWN`) and a direct
  fault exit to `SAFE_MODE`. The safing state exits only to safe states. Every `fault` transition ends in a safe state.
- Safe states are de-energised and fail-closed. Retry loops are bounded.
- Every transition has the required fields and all five guard categories. The Xe ledger matches the state rates.
- Every expression symbol is declared, and every declared symbol is used.
- No numeric literal appears in guards or actions, or anywhere outside sourced parameters. Parameter values are TBD, or
  sourced with an evidence class.
- Simulator references resolve to real code. The 0-D Hall closure is never an active supplier, and `HallMap` is gated
  while the credible set is empty. No calibration-nuisance variable leaks in.
- This document names every state and every guard quantity.

## Open items (all TBD)

- Xe feed-system design (regulator, plenum, purge path, leak spec), Xe gauging and a mission Xe budget.
- Cathode: keeper characterization, an O-exposure dose model and a start-count limit (the `abep_sim.life` limit is a
  code prior, verify).
- Discharge: ignition, admission, mixed and air-only behaviour. These require an admitted transport closure, O/O₂ and
  mixture chemistry, design Hall maps and thruster test. Oscillation limits (`Id_rms_rel_max`) require test.
- A transient thermal model for warm-up timing.
- Compressor, PPU, valve, sensor and watchdog FDIR designs.
- The spacecraft EPS interface (bus voltage, available power, eclipse-entry prediction).
