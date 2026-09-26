# Upstream gas-chain interface control document (ICD) v1

| | |
|---|---|
| machine-readable schema | [`schemas/interfaces/upstream_icd_v1.json`](../../schemas/interfaces/upstream_icd_v1.json) (JSON Schema Draft 2020-12, ICD version 1.0.0) |
| checks | [`tests/test_upstream_icd.py`](../../tests/test_upstream_icd.py) |
| status | **Draft for owner review**, 2026-09-26. Code baseline: commit `7b219ba` |
| what it is | An interface definition. It records what crosses each boundary of the upstream gas chain, in which unit, which existing function produces and consumes it, and what is missing |
| what it is not | Not a physics model, not a model change, not a validation claim, not a statement that ABEP closes and not an architecture ranking. It adds no numbers: every value in a record comes from a named producer, or it's null with evidence class `TBD` |

"Upstream" here means the gas-supply chain upstream of the thruster. It does **not** refer to `hallthruster_bridge/upstream/`,
which is about the HallThruster.jl upstream project (the ingestion-units issue).

## 1. Scope and chain

The chain follows the RFP architecture recorded in CLAUDE.md (Next work 1, "Scope"): atmospheric path intake → filter →
compressor → atmospheric gas chamber → valve; Xe path Xe chamber → valve; both feed ionization/discharge →
acceleration/thrust.

```
 ambient ─IF-A0─▶ intake ─IF-A1─▶ filter ─IF-A2─▶ compressor ─IF-A3─▶ atm. gas chamber ─IF-A4─▶ atm. valve ─IF-A5─┐
                                                                                                                   ├─▶ ionization/discharge → acceleration/thrust
                                             Xe chamber (tank) ─IF-X1─▶ Xe valve ─IF-X2────────────────────────────┘
 controller ─commands─▶ atm. valve, Xe valve                          (thruster boundary = IF-A5 + IF-X2)
```

| id | from → to | path | thruster boundary |
|---|---|---|---|
| IF-A0 | free stream → intake aperture | atmospheric | no |
| IF-A1 | intake → filter | atmospheric | no |
| IF-A2 | filter → compressor | atmospheric | no |
| IF-A3 | compressor → atmospheric gas chamber | atmospheric | no |
| IF-A4 | atmospheric gas chamber → atmospheric valve | atmospheric | no |
| IF-A5 | atmospheric valve → thruster (air port) | atmospheric | **yes** |
| IF-X1 | Xe chamber (tank) → Xe valve | xenon | no |
| IF-X2 | Xe valve → thruster (Xe port) | xenon | **yes** |
| commands | controller → valves (flow setpoints) | both | no |

Out of scope (listed in `x-icd.out_of_scope`): intake drag and C_D (they go to the spacecraft/mission model through
`mission_env.spacecraft_drag`, not down the gas chain); masses, BOM and indigenous content; thruster-side injector
properties such as the neutral injection velocity; thruster electrical inputs and every Hall output (those belong to
`hallthruster_bridge/hall_map_schema_v1.json`); facility background pressure (a ground-test facility interface, never a
flight upstream field).

## 2. The closure-independence rule: Hall calibration nuisance never leaks upstream

The Hall uncertainty has two layers (CLAUDE.md Next work 1; `abep_sim/hall_ensemble.py`;
`hallthruster_bridge/ensemble/transport_ensemble_v0.json`):

* **Layer 1, calibration nuisance.** P5 registration, historical coil shape, beam-efficiency reading and
  facility-ingestion interpretation. These describe what the P5 experiment *was*. They are marginalized when closures are
  admitted and are never a Vyovrinda design variable, map axis or trade dimension.
* **Layer 2, transferable.** The credible set of transport closures. It's an unweighted scenario set, and it's currently
  empty (project decision 2026-09-26), so no design Hall map exists yet.

The ICD fixes the upstream side so that it does not depend on either layer:

1. **The thruster boundary (IF-A5, IF-X2) is the same record for every closure.** It carries only gas-supply state:
   species mass flow, feed pressure, gas temperature, composition, contamination and quality flags. It carries no
   transport parameter, no `ensemble_member_id` and no calibration-nuisance variable. A Hall map is *queried with* this
   state. It never writes into it.
2. **Calibration nuisance must never leak upstream.** No field of any interface (IF-A0 to IF-X2, commands) may be
   named after, parameterised by, or produced from a layer-1 variable. That covers intake, filter, compressor, gas
   chambers and valves, and it also covers Vyovrinda's own thruster geometry, which is not an upstream field at all.
   `facility_ingestion_interpretation` is layer-1 and facility background pressure is a facility interface, so neither
   appears here.
3. **Upstream models are identical in every member evaluation.** When whole-system UQ later runs across admitted members,
   the intake, compressor, chamber and valve models and their inputs don't change between members. Only downstream
   quantities are reported as envelopes across members.
4. **Hall modules never produce an upstream value.** No upstream field may name a producer in `abep_sim.hall_map`,
   `abep_sim.hall_ensemble`, `abep_sim.hall1d`, `abep_sim.plasma_devices`, `abep_sim.plasma_chem` or
   `hallthruster_bridge/`. Those modules may appear only as *consumers* at the thruster boundary.

How this is enforced mechanically (`x-icd.closure_independence` and the tests):

* Every interface object and the record root have `additionalProperties: false`, so a record that adds
  `ensemble_member_id`, `transport` or any nuisance key is **invalid** (`test_thruster_boundary_rejects_closure_and_nuisance_fields`).
* `x-icd.closure_independence.identifiers` lists the forbidden identifiers. The test reads the `calibration_nuisance`
  keys from `transport_ensemble_v0.json` and fails if a nuisance key is missing from that list, or if any field name
  contains a forbidden identifier (`test_calibration_nuisance_never_appears_upstream`).
* `test_supplied_fields_point_at_upstream_code` fails if a producer lies under a forbidden prefix.

Command setpoints (section 4) are demand signals. Their *definition* is member-independent. Whether a per-member
setpoint schedule is acceptable in whole-system UQ, or whether the schedule must be fixed independently of the member,
is left to the owner (open question 2).

## 3. Record structure and conventions

**Record.** One record = `{icd: "upstream_icd", icd_version: "1.0.0", record_provenance, interfaces: {IF-…: {...}},
commands: {...}}`. An interface that doesn't exist in the operating mode is simply absent from the record (for example
IF-X1/IF-X2 in air-only operation). Fields are not `required`, because many are gaps today. Undeclared fields are
rejected.

**Quantity objects.** Every field is one of four shapes defined in `$defs`:

| shape | members | notes |
|---|---|---|
| `scalar_quantity` | `value` (number or null), `unit`, `evidence_class`, `uncertainty`, optional `source`, `validity_domain`, `in_domain` | a non-null `value` must carry one of the six evidence classes (schema `anyOf`) |
| `species_quantity` | `values` {species → number or null}, `unit`, `evidence_class`, `uncertainty`, optional as above | keys restricted to the ICD species set |
| `flag` | `value` (bool or null), `unit` `-`, `source`, optional `reason` | state-quality flags |
| `label` | `value` (string or null), `unit` `-`, `source` | e.g. the atmosphere provenance string |

Each field's schema pins its unit with `const`, so a record in another unit is invalid. **Units are present on every
field**, flags included (`-`).

**Evidence class** (quantity type, docs/EVIDENCE.md): `measured`, `digitized`, `inferred`, `reconstructed`,
`model-derived`, `assumed`, plus `TBD` only for a null value. Today every upstream value is `model-derived` (a code model
output) or `assumed` (a code default parameter with no cited source). Nothing upstream is measured yet.

**Uncertainty.** `uncertainty.kind` ∈ {`TBD`, `not_applicable`, `standard_abs_1sigma`, `standard_rel_1sigma`, `interval`,
`scenario_set`}. No upstream producer emits an uncertainty today. The only upstream uncertainty in code is the
accommodation prior `uq_modular.PRIORS["accommodation"]`, which is sampled in `uq_modular` and not carried as a field.
Each field's `x-field.uncertainty` says this.

**Annotations (`x-field`, per field).** `variable_class`, `unit`, `shape`, `definition`, `status`, `producers`,
`consumers`, `validity_domain` (an id, below), `evidence_class_current`, `uncertainty`, and where relevant
`derivation`, `note`, `requires`. A producer or consumer is one of:

* `python`: module + attribute (+ `output_key`, `key_source`, `native_unit`). The test imports it, resolves the
  attribute, and finds the key in its source.
* `repo_file`: an in-repo file + token. The test checks that the token is in the file.
* `external`: a reference outside the repo, such as HallThruster.jl source. It's cited, not tested.
* `TBD`: no code, with the reason.

**Status values.**

| status | meaning |
|---|---|
| supplied | an existing function/attribute returns it (in the ICD unit or a stated `native_unit`) |
| derivable | no function returns it, but it follows from supplied quantities by the stated `derivation` |
| partial | produced only on a non-production path, only in part, or under a stated simplifying assumption. `requires` says what is missing |
| gap | no producer. `requires` = "TBD - requires …" |

**Variable classes.** Every interface covers all 13, either with at least one field or with an explicit
not-applicable reason (`x-interface.not_applicable`, tested): `mdot_s`, `p`, `T`, `x_s`, `dmdot_dt`, `inventory`,
`residence_time`, `conductance`, `pressure_loss`, `shaft_power`, `rejected_heat`, `contamination`, `quality`.

**Species.** `O`, `N2`, `O2`, `Xe`, which equals `abep_sim/constants.py:M_SPECIES` (tested). The atmospheric path carries
O/N2/O2 and the Xe path carries Xe. Adding a species (e.g. N, NO, Ar, He) is a major version change.

**Composition basis.** The code carries **mass** fractions (`fO`, `fN2`, `fO2`; `composition_anode_mass`). The one
exception is the compressor's `composition_out`, which is a partial-pressure (**mole**) fraction. The ICD has both `w_s`
(mass) and `x_s` (mole) wherever it can, with the derivation stated. `hall_map.py`'s docstring names a composition axis
such as `x_O` without a basis. That basis has to be fixed before an air Hall map is queried from IF-A5 (open question 3).

**Native units.** Some producers return non-SI or non-ICD units: `mg s^-1` (`mdot_air_mgps`, `air_mgps`, `xe_mgps`,
`xe_flow_mgps`), `um` (`coating_erosion_um`), `um per 1000 h` (`coating_rate_um_per_kh`), `MPa` (`p_MPa`), `L` (`V_L`),
`W m^-2` (`aero_heating_W_m2`). The `native_unit` annotation records each one. A record always carries the ICD unit.

**Versioning.** Removing or renaming a field, changing a unit or changing the species set is a major change (new file
`upstream_icd_v2.json`). Adding a field or an interface is a minor change. Annotation, status or producer updates are
patches. A record's `icd_version` must equal the schema's.

### Unit vocabulary and validity domains

| id | domain |
|---|---|
| `D-ATM-FROZEN` | Frozen NRLMSIS 2.1 scenario dataset abep_sim/data/atmosphere_msis21_v1.{csv,json}: altitude 150-300 km, F10.7 = F10.7A in {70, 100, 150, 190, 230}, ap 15, orbit-averaged (atmosphere.ATM_VERSION: lat -60..60 x 4 LST sectors), epoch 2028-03-21T12:00. Outside the grid atmosphere() raises ValueError (_interp_frozen). Composition carried: O, N2, O2 only (He/H/Ar/N dropped, per the atmosphere.py code comment: verify). RFP operating envelope 180-230 km (constants.RFP alt_min_km/alt_max_km). |
| `D-TPMC-FROZEN` | Frozen TPMC response surface abep_sim/data/intake_surface_v1.{csv,json}: L/d {3,5,10,20}, phi {0.8,0.9}, alpha {0,0.2,0.5,0.8,1.0}, theta {0,2,5} deg, species O/N2/O2, scattering maxwell or cll, built at 200 km, F10.7 150. IntakeSurface.__call__ raises ValueError outside the grid (no extrapolation). The surface has no filter column: response_surface() builds IntakeGeometry without a filter. |
| `D-TPMC-DIRECT` | Direct TPMC (intake_tpmc.intake_response): free-molecular (Kn >> 1) honeycomb of circular channels, Maxwell or CLL wall scattering; converged when unresolved_fraction <= 1e-3. Not used on the production path (system.evaluate uses the frozen surface). |
| `D-INTAKE-PARAM` | Parametric intake/compressor (intake.IntakeParams/CompressorParams with use_tpmc=False): eta_c is a blend of two code priors times cos^2(off-axis); compress() uses a total number-density ratio. Code defaults, evidence class assumed. |
| `D-DRAGCOMP` | compressor.DragCompressor: free-molecular turbomolecular rows + Holweck/Gaede drag stages with a linear Gaede throughput characteristic, per-species K clipped to [1, K0]; rotor_ok requires tip speed <= u_max (materials DB yield / (stress_safety x density)); size_for() searches turbo rows 1-6, drag stages 0-4, rpm 5000..min(rpm_max, stress limit) in 2500 steps. No Knudsen-number check. Coefficients are code defaults. |
| `D-RESERVOIR` | reservoir.Reservoir: isothermal lumped volume, species O/O2/N2 only, molecular-flow orifice conductance K*A*c_bar/4, O wall recombination gamma(T) from the materials DB (literature-class priors per materials.py). size_orifice_for_pressure() bisects the anode-feed area in [1e-8, 3e-2] m^2. No Knudsen-number check. |
| `D-SYSTEM-BUDGET` | system.Budgets / system.evaluate parametric budget values (code defaults, evidence class assumed). |
| `D-CARD` | thruster.py card model (module docstring: every card number is a prior to be replaced by test data). Used by system.evaluate and transient.run_mission; not the HallThruster.jl path. |
| `D-ARCH` | archengine.gas_path_state -> archengine._propulsion hand-off (gas-path variables area and reservoir pressure are search variables of close_architecture). |
| `D-AO` | aochem.py / life.py / materials.py AO and erosion relations: literature-class priors (aochem.py and materials.py docstrings) to be replaced by coupon / AO-beam test data. |
| `D-THERMAL` | thermal.py lumped node network (default_nodes / solve_network / size_radiator); code defaults. |
| `D-MISSION` | transient.run_mission quasi-static time stepping (dt_h, default 1 h); no valve or line dynamics. |
| `D-TBD` | No producer, so no validity domain is defined. TBD with the producer. |

| unit | meaning |
|---|---|
| `kg s^-1` | mass flow |
| `kg s^-2` | rate of change of mass flow |
| `Pa` | pressure |
| `K` | temperature |
| `-` | dimensionless (fraction, ratio, probability, count, flag) |
| `kg` | mass |
| `s` | time |
| `m^3` | volume |
| `m^3 s^-1` | volumetric conductance / pumping speed |
| `W` | power / heat flow |
| `W m^-2` | heat flux |
| `m^-2 s^-1` | number flux |
| `m^-2` | number fluence |
| `eV` | particle energy |
| `kg m^-3` | mass density |
| `m^-3` | number density |
| `m s^-1` | speed or recession rate |
| `m` | length / depth |
| `kg m^-2 s^-1` | mass flux |
| `N m` | torque |

## 4. Interfaces

For each field the tables give the variable class, the ICD unit, the status, the producing code (`file:function → output
key`, with its native unit if that differs), the consumer, and what is missing. Every file/function/key named here as
existing code is checked by `test_existing_code_references_resolve`.

### IF-A0: free stream -> intake aperture

Free-molecular free-stream state presented to the ram aperture. Producer: abep_sim.atmosphere.atmosphere() (frozen NRLMSIS by default, live MSIS only when asked, CLAUDE.md rule 3); consumer: abep_sim.intake.collection().

| field | class | unit | status | producer (file:function → key) | consumer | notes / what is missing |
|---|---|---|---|---|---|---|
| `mdot_incident_s_kgps` | mdot_s | kg s^-1 | **derivable** | `abep_sim/intake.py:collection` → `mdot_incident`; `abep_sim/atmosphere.py:atmosphere` → `fO` | `abep_sim/intake.py:collection` | derive: mdot_incident (total, collection) x w_s (atmosphere fO/fN2/fO2) |
| `mass_flux_kgpm2ps` | mdot_s | kg m^-2 s^-1 | **supplied** | `abep_sim/atmosphere.py:atmosphere` → `flux_kg_m2_s` | `abep_sim/intake.py:collection` |  |
| `rho_kgpm3` | mdot_s | kg m^-3 | **supplied** | `abep_sim/atmosphere.py:atmosphere` → `rho` | `abep_sim/intake.py:collection` |  |
| `n_total_m3` | mdot_s | m^-3 | **supplied** | `abep_sim/atmosphere.py:atmosphere` → `n` | `abep_sim/intake.py:compress` |  |
| `V_mps` | mdot_s | m s^-1 | **partial** | `abep_sim/atmosphere.py:atmosphere` → `V` | `abep_sim/intake.py:collection` | Consumers read atm.get('V_rel', atm['V']), but atmosphere() does not return 'V_rel' (co-rotation, winds), so the relative speed equals the orbital speed on every current path. TBD - requires a relative-velocity producer (atmosphere co-rotation and winds) if V_rel is to differ from V |
| `p_ambient_Pa` | p | Pa | **supplied** | `abep_sim/atmosphere.py:atmosphere` → `p_ambient_Pa` | — |  |
| `T_ambient_K` | T | K | **supplied** | `abep_sim/atmosphere.py:atmosphere` → `T` | `abep_sim/intake_tpmc.py:intake_response` |  |
| `w_s` | x_s | - | **supplied** | `abep_sim/atmosphere.py:atmosphere` → `fO`; `abep_sim/atmosphere.py:atmosphere` → `fN2`; `abep_sim/atmosphere.py:atmosphere` → `fO2` | `abep_sim/intake.py:collection` |  |
| `x_s` | x_s | - | **derivable** | `abep_sim/atmosphere.py:atmosphere` → `fO`; `abep_sim/constants.py:M_SPECIES` | — | derive: x_s = (w_s / M_s) / sum_k (w_k / M_k), M_s from constants.M_SPECIES |
| `m_mean_kg` | x_s | kg | **supplied** | `abep_sim/atmosphere.py:atmosphere` → `m_mean` | `abep_sim/intake.py:passive_compression` |  |
| `dmdot_dt_kgps2` | dmdot_dt | kg s^-2 | **gap** | — | — | TBD - requires an orbit-resolved (non-averaged) density/composition producer; transient.run_mission only steps the orbit-averaged state at dt_h |
| `ao_number_flux_m2s` | contamination | m^-2 s^-1 | **supplied** | `abep_sim/aochem.py:ao_flux` → `ao_flux` | `abep_sim/life.py:intake_life`; `abep_sim/life.py:blade_life` |  |
| `ao_energy_eV` | contamination | eV | **supplied** | `abep_sim/aochem.py:ao_flux` → `ao_energy_eV` | — |  |
| `atmosphere_source` | quality | - | **supplied** | `abep_sim/atmosphere.py:atmosphere` → `source` | `abep_sim/system.py:evaluate` → `atm_source`; `abep_sim/archengine.py:gas_path_state` → `atmosphere` |  |
| `atmosphere_in_domain` | quality | - | **derivable** | `abep_sim/atmosphere.py:_interp_frozen` | — | derive: flag = atmosphere() returned without ValueError |

Not applicable here: inventory (free stream holds no inventory); residence_time (free stream); conductance (free stream); pressure_loss (free stream); shaft_power (free stream); rejected_heat (free stream (aero heating is booked on IF-A1)).

### IF-A1: intake -> filter

Gas collected by the intake and delivered to the filter inlet. In the code the filter is lumped into the intake: the production path (intake.collection with use_tpmc=True) interpolates the frozen TPMC surface, which has no filter, so this record is what the code actually delivers downstream.

| field | class | unit | status | producer (file:function → key) | consumer | notes / what is missing |
|---|---|---|---|---|---|---|
| `mdot_total_kgps` | mdot_s | kg s^-1 | **supplied** | `abep_sim/intake.py:collection` → `mdot_collected` | `abep_sim/intake.py:compress` |  |
| `mdot_s_kgps` | mdot_s | kg s^-1 | **partial** | `abep_sim/system.py:evaluate` → `md_in` | `abep_sim/compressor.py:DragCompressor.run` | system.evaluate splits the total by the free-stream mass fractions (md_in = mdot x atm fO/fN2/fO2). The frozen surface is species-resolved, but IntakeSurface.__call__ returns only the mass-weighted mean eta_c, so species-selective collection is not propagated. TBD - requires IntakeSurface to return per-species eta_c (code change outside this ICD) |
| `eta_c` | mdot_s | - | **supplied** | `abep_sim/intake.py:collection` → `eta_c`; `abep_sim/intake_tpmc.py:IntakeSurface.__call__` → `eta_c` | `abep_sim/intake.py:compress` |  |
| `p_plenum_Pa` | p | Pa | **supplied** | `abep_sim/intake.py:compress` → `p_passive_Pa` | `abep_sim/compressor.py:DragCompressor.run` | evaluated with CompressorParams.T_out_K as the gas temperature |
| `passive_compression_ratio` | p | - | **supplied** | `abep_sim/intake.py:collection` → `passive_override`; `abep_sim/intake.py:compress` → `passive_ratio` | `abep_sim/intake.py:compress` |  |
| `T_gas_K` | T | K | **partial** | `abep_sim/intake_tpmc.py:IntakeGeometry` → `T_wall_K`; `abep_sim/intake.py:CompressorParams` → `T_out_K` | `abep_sim/intake.py:compress` | two code parameters, no energy balance: TPMC CR_passive uses IntakeGeometry.T_wall_K, compress() uses CompressorParams.T_out_K TBD - requires an intake/plenum thermal state from the thermal network |
| `w_s` | x_s | - | **partial** | `abep_sim/system.py:evaluate` → `md_in` | `abep_sim/compressor.py:DragCompressor.run` | set equal to the free-stream mass fractions (see mdot_s_kgps) TBD - requires per-species eta_c from IntakeSurface |
| `x_s` | x_s | - | **derivable** | `abep_sim/system.py:evaluate` → `md_in`; `abep_sim/constants.py:M_SPECIES` | — | derive: x_s = (mdot_s / M_s) / sum_k (mdot_k / M_k) |
| `dmdot_dt_kgps2` | dmdot_dt | kg s^-2 | **gap** | — | — | TBD - requires an orbit-resolved free stream (IF-A0) and intake dynamics |
| `plenum_inventory_kg` | inventory | kg | **gap** | — | — | TBD - requires plenum geometry (volume) and state |
| `mean_wall_hits` | residence_time | - | **partial** | `abep_sim/intake_tpmc.py:intake_response` → `mean_wall_hits` | — | direct TPMC only; the frozen CSV has the column but IntakeSurface does not interpolate it |
| `residence_time_s` | residence_time | s | **gap** | — | — | TBD - requires plenum volume and outflow (residence = inventory / throughput) |
| `K_back` | conductance | - | **supplied** | `abep_sim/intake_tpmc.py:IntakeSurface.__call__` → `K_back` | — |  |
| `rejected_heat_W` | rejected_heat | W | **partial** | `abep_sim/thermal.py:aero_heating_W_m2` (W m^-2); `abep_sim/thermal.py:default_nodes` → `intake` | `abep_sim/thermal.py:solve_network` | only a flux 0.5 rho V^3 x accommodation is produced; the intake node's internal power is 0 and the flux enters through its ram_view area inside solve_network TBD - requires the integrated intake heat load as an output |
| `contaminant_mass_flow_kgps` | contamination | kg s^-1 | **gap** | — | — | TBD - requires an erosion-product and outgassing transport model (materials.Material tml_pct/cvcm_pct exist only as properties) |
| `coating_erosion_depth_m` | contamination | m | **supplied** | `abep_sim/life.py:intake_life` → `coating_erosion_um` (um) | `abep_sim/system.py:evaluate` |  |
| `intake_rom_in_bounds` | quality | - | **supplied** | `abep_sim/intake_tpmc.py:IntakeSurface.in_bounds` | `abep_sim/intake_tpmc.py:IntakeSurface.__call__` |  |
| `tpmc_max_unresolved` | quality | - | **supplied** | `abep_sim/intake_tpmc.py:IntakeSurface.__init__` → `max_unresolved` | — |  |

Not applicable here: pressure_loss (passive ram compression raises pressure; represented by passive_compression_ratio); shaft_power (passive element).

### IF-A2: filter -> compressor

Filtered gas presented to the compressor inlet. The filter has no separate model: only the direct TPMC (intake_tpmc.intake_response with IntakeGeometry.filter=True) applies filter transmission; the production path adds filter mass only (intake.collection: 0.8 x area). The compressor consumes compress()['p_passive_Pa'] and the species split md_in (system.evaluate).

| field | class | unit | status | producer (file:function → key) | consumer | notes / what is missing |
|---|---|---|---|---|---|---|
| `mdot_total_kgps` | mdot_s | kg s^-1 | **partial** | `abep_sim/intake.py:compress` → `mdot_net`; `abep_sim/intake_tpmc.py:intake_response` → `eta_c` | `abep_sim/compressor.py:DragCompressor.run` | production path: mdot_collected x (1 - CompressorParams.backflow_frac); filter transmission not applied TBD - requires the filter transmission on the production path (frozen surface has no filter) |
| `mdot_s_kgps` | mdot_s | kg s^-1 | **partial** | `abep_sim/system.py:evaluate` → `md_in` | `abep_sim/compressor.py:DragCompressor.run` | same record as IF-A1 (filter not modelled on this path) TBD - requires a species-resolved filter transmission |
| `p_inlet_Pa` | p | Pa | **partial** | `abep_sim/intake.py:compress` → `p_passive_Pa` | `abep_sim/compressor.py:DragCompressor.size_for` | no filter pressure change is applied |
| `T_gas_K` | T | K | **partial** | `abep_sim/compressor.py:DragCompressor` → `T_gas_K` | `abep_sim/compressor.py:DragCompressor._run_once` | compressor parameter, not a propagated state TBD - requires a propagated gas temperature from IF-A1 |
| `w_s` | x_s | - | **partial** | `abep_sim/system.py:evaluate` → `md_in` | `abep_sim/compressor.py:DragCompressor.run` | free-stream fractions (see IF-A1) TBD - requires per-species eta_c and filter transmission |
| `x_s` | x_s | - | **derivable** | `abep_sim/compressor.py:DragCompressor._run_once` → `nflow` | `abep_sim/compressor.py:DragCompressor._run_once` | derive: x_s = nflow_s / sum nflow (inside _run_once: p_s_in = p_in x nflow_s / ntot) |
| `dmdot_dt_kgps2` | dmdot_dt | kg s^-2 | **gap** | — | — | TBD - requires IF-A1 dynamics and a filter model |
| `filter_inventory_kg` | inventory | kg | **gap** | — | — | TBD - requires filter geometry |
| `residence_time_s` | residence_time | s | **gap** | — | — | TBD - requires filter geometry |
| `filter_transmission` | conductance | - | **partial** | `abep_sim/intake_tpmc.py:IntakeGeometry` → `filter_transmission` | `abep_sim/intake_tpmc.py:intake_response` | code default; used only by the direct TPMC TBD - requires a filter design and a source for its transmission |
| `pressure_loss_Pa` | pressure_loss | Pa | **gap** | — | — | TBD - requires a filter flow model |
| `rejected_heat_W` | rejected_heat | W | **gap** | — | — | TBD - requires a filter thermal model |
| `contaminant_mass_flow_kgps` | contamination | kg s^-1 | **gap** | — | — | TBD - requires a filter capture model and IF-A1 contaminant input |
| `filter_retained_mass_rate_kgps` | contamination | kg s^-1 | **gap** | — | — | TBD - requires a filter capture model |
| `filter_flow_effect_applied` | quality | - | **gap** | — | — | TBD - requires the path to report whether IntakeGeometry.filter was applied (production path: never) |

Not applicable here: shaft_power (passive element).

### IF-A3: compressor -> atmospheric gas chamber

Compressed gas delivered to the atmospheric gas chamber. Physics path: compressor.DragCompressor.run/size_for (system.evaluate with gaspath_physics=True). Parametric path: intake.compress.

| field | class | unit | status | producer (file:function → key) | consumer | notes / what is missing |
|---|---|---|---|---|---|---|
| `mdot_s_kgps` | mdot_s | kg s^-1 | **supplied** | `abep_sim/compressor.py:DragCompressor.run` → `delivered_kgps` | `abep_sim/reservoir.py:Reservoir.steady_state`; `abep_sim/reservoir.py:size_orifice_for_pressure` |  |
| `mdot_total_kgps` | mdot_s | kg s^-1 | **derivable** | `abep_sim/compressor.py:DragCompressor.run` → `delivered_kgps`; `abep_sim/intake.py:compress` → `mdot_net` | `abep_sim/reservoir.py:Reservoir.steady_state` | derive: sum of delivered_kgps (physics) or compress mdot_net (parametric) |
| `recirculated_s_kgps` | mdot_s | kg s^-1 | **supplied** | `abep_sim/compressor.py:DragCompressor.run` → `recirculated_kgps` | — |  |
| `p_out_Pa` | p | Pa | **supplied** | `abep_sim/compressor.py:DragCompressor._run_once` → `p_out_Pa`; `abep_sim/intake.py:compress` → `p_out_Pa` | `abep_sim/system.py:evaluate` |  |
| `p_s_Pa` | p | Pa | **derivable** | `abep_sim/compressor.py:DragCompressor._run_once` → `composition_out` | — | derive: p_s = composition_out[s] x p_out_Pa |
| `compression_ratio_s` | p | - | **supplied** | `abep_sim/compressor.py:DragCompressor._run_once` → `CR_by_species` | `abep_sim/system.py:evaluate` |  |
| `T_gas_K` | T | K | **partial** | `abep_sim/compressor.py:DragCompressor` → `T_gas_K` | — | parameter (isothermal compression assumed) TBD - requires a gas energy balance through the compressor |
| `T_machine_K` | T | K | **supplied** | `abep_sim/compressor.py:DragCompressor._run_once` → `T_comp_K` | `abep_sim/system.py:evaluate` | system.evaluate sets the reservoir T_K = clamp(T_comp_K, 300, 500) K |
| `x_s` | x_s | - | **supplied** | `abep_sim/compressor.py:DragCompressor._run_once` → `composition_out` | — |  |
| `w_s` | x_s | - | **derivable** | `abep_sim/compressor.py:DragCompressor.run` → `delivered_kgps` | — | derive: w_s = delivered_s / sum delivered |
| `dmdot_dt_kgps2` | dmdot_dt | kg s^-2 | **partial** | `abep_sim/reservoir.py:startup_transient` → `spinup_s` | `abep_sim/reservoir.py:startup_transient` | spin-up only: delivered fraction f(t) = min(t / spinup_s, 1), so dmdot/dt = mdot / spinup_s during the ramp; no throttling dynamics TBD - requires compressor speed/throttle dynamics |
| `compressor_inventory_kg` | inventory | kg | **gap** | — | — | TBD - requires channel volumes and the internal pressure distribution |
| `upstream_wall_collisions` | residence_time | - | **partial** | `abep_sim/system.py:evaluate` → `upstream_collisions` | `abep_sim/reservoir.py:Reservoir.steady_state` | system.evaluate sets 10 x turbo_rows + 50 x n_stages (heuristic in code, no cited source) TBD - requires a computed collision count or residence time for the compressor |
| `pumping_speed_turbo_m3ps` | conductance | m^3 s^-1 | **supplied** | `abep_sim/compressor.py:DragCompressor._run_once` → `S_turbo_m3_s` | — |  |
| `pumping_speed_drag_m3ps` | conductance | m^3 s^-1 | **supplied** | `abep_sim/compressor.py:DragCompressor._run_once` → `S0_drag_m3_s` | — |  |
| `leak_conductance_m3ps` | conductance | m^3 s^-1 | **supplied** | `abep_sim/compressor.py:DragCompressor` → `leak_conductance_m3_s` | `abep_sim/compressor.py:DragCompressor._run_once` | parameter (code default) |
| `shaft_power_W` | shaft_power | W | **derivable** | `abep_sim/compressor.py:DragCompressor._run_once` → `P_gas_W`; `abep_sim/compressor.py:DragCompressor._run_once` → `P_bear_W` | — | derive: P_gas_W + P_bear_W (= torque_Nm x omega) |
| `electrical_power_W` | shaft_power | W | **supplied** | `abep_sim/compressor.py:DragCompressor._run_once` → `P_el_W`; `abep_sim/intake.py:compress` → `comp_power_W` | `abep_sim/system.py:evaluate`; `abep_sim/archengine.py:close_architecture` |  |
| `torque_Nm` | shaft_power | N m | **supplied** | `abep_sim/compressor.py:DragCompressor._run_once` → `torque_Nm` | — |  |
| `rejected_heat_W` | rejected_heat | W | **partial** | `abep_sim/thermal.py:default_nodes` → `compressor` | `abep_sim/thermal.py:solve_network` | consumer-side assumption: the compressor node's internal heat equals the full electrical input P_comp_W; archengine books gas['comp_power'] as the 'compressor' ledger line TBD - requires the compressor to report its own heat split (motor, bearings, gas work) |
| `contaminant_mass_flow_kgps` | contamination | kg s^-1 | **gap** | — | — | TBD - requires converting blade erosion rates to a mass flow and an outgassing model |
| `blade_coating_recession_mps` | contamination | m s^-1 | **supplied** | `abep_sim/life.py:blade_life` → `coating_rate_um_per_kh` (um per 1000 h) | `abep_sim/archengine.py:gas_path_state` |  |
| `rotor_ok` | quality | - | **supplied** | `abep_sim/compressor.py:DragCompressor._run_once` → `rotor_ok` | `abep_sim/system.py:evaluate` |  |
| `sized` | quality | - | **supplied** | `abep_sim/compressor.py:DragCompressor.size_for` → `sized` | `abep_sim/system.py:evaluate` |  |
| `comp_feasible` | quality | - | **supplied** | `abep_sim/intake.py:compress` → `comp_feasible`; `abep_sim/system.py:evaluate` → `comp_feasible` | `abep_sim/system.py:evaluate` |  |
| `recirculation_converged` | quality | - | **gap** | — | — | TBD - requires DragCompressor.run to report convergence (CLAUDE.md rule 3; code change outside this ICD) |

Not applicable here: pressure_loss (the compressor raises pressure; represented by compression_ratio_s).

### IF-A4: atmospheric gas chamber -> atmospheric valve

Chamber outflow toward the valve. The code has no valve model: Reservoir.anode_orifice_area_m2 x anode_orifice_K lumps valve, feed line and anode distributor into one molecular-flow restriction, and size_orifice_for_pressure() chooses its area to hit the target chamber pressure.

| field | class | unit | status | producer (file:function → key) | consumer | notes / what is missing |
|---|---|---|---|---|---|---|
| `mdot_s_kgps` | mdot_s | kg s^-1 | **supplied** | `abep_sim/reservoir.py:Reservoir.steady_state` → `mdot_anode` | `abep_sim/system.py:evaluate` |  |
| `mdot_leak_s_kgps` | mdot_s | kg s^-1 | **supplied** | `abep_sim/reservoir.py:Reservoir.steady_state` → `mdot_leak` | — |  |
| `p_total_Pa` | p | Pa | **supplied** | `abep_sim/reservoir.py:Reservoir.steady_state` → `p_total_Pa` | `abep_sim/system.py:evaluate` |  |
| `p_s_Pa` | p | Pa | **supplied** | `abep_sim/reservoir.py:Reservoir.steady_state` → `p_species_Pa` | — |  |
| `T_gas_K` | T | K | **supplied** | `abep_sim/reservoir.py:Reservoir.steady_state` → `T_K` | — | set by system.evaluate from the compressor machine temperature, clamped to 300-500 K |
| `w_s` | x_s | - | **supplied** | `abep_sim/reservoir.py:Reservoir.steady_state` → `composition_anode_mass` | `abep_sim/system.py:evaluate` |  |
| `x_s` | x_s | - | **derivable** | `abep_sim/reservoir.py:Reservoir.steady_state` → `n_species` | — | derive: x_s = n_s / sum n_k |
| `O_survival` | x_s | - | **supplied** | `abep_sim/reservoir.py:Reservoir.steady_state` → `O_survival`; `abep_sim/aochem.py:inlet_composition` → `O_survival` | `abep_sim/system.py:evaluate` |  |
| `dmdot_dt_kgps2` | dmdot_dt | kg s^-2 | **partial** | `abep_sim/reservoir.py:startup_transient` → `tau_s` | — | startup_transient returns the time constant V/C and a (t, p) history only; outflow is proportional to p at fixed conductance, so dmdot/dt follows from dp/dt TBD - requires a species-resolved outflow history |
| `inventory_s_kg` | inventory | kg | **derivable** | `abep_sim/reservoir.py:Reservoir.steady_state` → `n_species`; `abep_sim/reservoir.py:Reservoir.steady_state` → `volume_m3` | — | derive: m_s = n_s x M_s x volume_m3 |
| `chamber_volume_m3` | inventory | m^3 | **supplied** | `abep_sim/reservoir.py:Reservoir.steady_state` → `volume_m3` | — | parameter (code default) |
| `residence_time_s` | residence_time | s | **supplied** | `abep_sim/reservoir.py:Reservoir.steady_state` → `residence_time_s` | `abep_sim/system.py:evaluate` |  |
| `wall_collisions` | residence_time | - | **supplied** | `abep_sim/reservoir.py:Reservoir.steady_state` → `wall_collisions_reservoir` | `abep_sim/system.py:evaluate` |  |
| `feed_conductance_s_m3ps` | conductance | m^3 s^-1 | **supplied** | `abep_sim/reservoir.py:Reservoir.conductance` | `abep_sim/reservoir.py:Reservoir.steady_state` |  |
| `pressure_loss_Pa` | pressure_loss | Pa | **gap** | — | — | TBD - requires a feed-line flow model (the lumped orifice has no separate line drop) |
| `rejected_heat_W` | rejected_heat | W | **gap** | — | — | TBD - requires a chamber thermal node |
| `contaminant_mass_flow_kgps` | contamination | kg s^-1 | **gap** | — | — | TBD - requires IF-A3 contaminant input and chamber wall model |
| `steady_state_converged` | quality | - | **gap** | — | — | TBD - requires Reservoir.steady_state to report convergence (CLAUDE.md rule 3; code change outside this ICD) |
| `orifice_sizing_converged` | quality | - | **gap** | — | — | TBD - requires the sizing routine to return its pressure residual |
| `molecular_flow_regime_ok` | quality | - | **gap** | — | — | TBD - requires a Knudsen-number check against a stated regime limit |

Not applicable here: shaft_power (passive element).

### IF-A5: atmospheric valve -> thruster (air port)

THRUSTER BOUNDARY, atmospheric port. The only record the thruster block receives from the atmospheric chain. It is independent of which Hall transport closure is admitted: it carries no transport parameter, no ensemble member id and no calibration-nuisance variable (see x-icd.closure_independence). Current producers: archengine.gas_path_state (architecture engine) and system.evaluate (single configuration); consumers: archengine._propulsion and, when wired, HallThruster.jl Propellant inputs via hallthruster_bridge (bridge_lib.jl).

| field | class | unit | status | producer (file:function → key) | consumer | notes / what is missing |
|---|---|---|---|---|---|---|
| `mdot_total_kgps` | mdot_s | kg s^-1 | **supplied** | `abep_sim/archengine.py:gas_path_state` → `mdot_air`; `abep_sim/system.py:evaluate` → `mdot_air_mgps` (mg s^-1) | `abep_sim/archengine.py:_propulsion` → `mdot_air` |  |
| `mdot_s_kgps` | mdot_s | kg s^-1 | **derivable** | `abep_sim/archengine.py:gas_path_state` → `mdot_air`; `abep_sim/archengine.py:gas_path_state` → `fO` | `abep_sim/archengine.py:_propulsion` → `flows`; `hallthruster_bridge/bridge_lib.jl` (`flow_rate_kg_s`) | derive: mdot_air x w_s (as archengine._propulsion does) |
| `mdot_cathode_air_kgps` | mdot_s | kg s^-1 | **supplied** | `abep_sim/archengine.py:Neutralizer` → `air_mgps` (mg s^-1); `abep_sim/thruster.py:Cathode` → `air_flow_mgps` (mg s^-1) | `abep_sim/archengine.py:_propulsion` → `air_mgps` | neutralizer parameter; archengine._propulsion subtracts it from mdot_air before the anode |
| `mdot_anode_s_kgps` | mdot_s | kg s^-1 | **derivable** | `abep_sim/archengine.py:_propulsion` → `flows` | `abep_sim/archengine.py:_propulsion` | derive: (mdot_air - air_mgps x 1e-6) x w_s (archengine._propulsion) |
| `p_feed_Pa` | p | Pa | **supplied** | `abep_sim/archengine.py:gas_path_state` → `p_in`; `abep_sim/system.py:evaluate` → `p_in_Pa` | `abep_sim/archengine.py:_propulsion` → `p_in`; `abep_sim/archengine.py:P_ion_envelope_violation` | off-design, archengine scales p_in with mdot at fixed conductance (propulsion_map, close_architecture envelope) |
| `T_gas_K` | T | K | **partial** | `abep_sim/reservoir.py:Reservoir.steady_state` → `T_K` | external: HallThruster.jl v0.23.1 src/physics/gas.jl, struct Propellant field temperature_K; `hallthruster_bridge/propellants/n2_n.toml` (`temperature_K`) | the chamber temperature exists but gas_path_state does not pass it on; the Hall-side neutral temperature comes from the solver default or the propellant config, never from the upstream chain TBD - requires gas_path_state to carry T and the bridge to pass it (code change outside this ICD) |
| `w_s` | x_s | - | **supplied** | `abep_sim/archengine.py:gas_path_state` → `fO`; `abep_sim/archengine.py:gas_path_state` → `fN2`; `abep_sim/archengine.py:gas_path_state` → `fO2`; `abep_sim/system.py:evaluate` → `fO_inlet` | `abep_sim/archengine.py:_propulsion` → `fO` | fN2 is formed as 1 - fO - fO2 in gas_path_state |
| `x_s` | x_s | - | **derivable** | `abep_sim/archengine.py:gas_path_state` → `fO`; `abep_sim/constants.py:M_SPECIES` | — | derive: x_s = (w_s / M_s) / sum_k (w_k / M_k) |
| `dmdot_dt_kgps2` | dmdot_dt | kg s^-2 | **gap** | — | — | TBD - requires valve and feed-line dynamics |
| `feed_line_inventory_kg` | inventory | kg | **gap** | — | — | TBD - requires feed-line geometry |
| `feed_line_residence_time_s` | residence_time | s | **gap** | — | — | TBD - requires feed-line geometry |
| `valve_conductance_s_m3ps` | conductance | m^3 s^-1 | **partial** | `abep_sim/reservoir.py:Reservoir.conductance` | `abep_sim/reservoir.py:Reservoir.steady_state` | only as part of the lumped reservoir anode-feed orifice TBD - requires a separate valve model (flow coefficient, position) |
| `pressure_loss_Pa` | pressure_loss | Pa | **gap** | — | — | TBD - requires a valve/line flow model |
| `valve_rejected_heat_W` | rejected_heat | W | **partial** | `abep_sim/system.py:Budgets` → `p_ctrl_valves_sensors_W` | `abep_sim/system.py:evaluate` | one lumped budget for valves, sensors and control (both paths); not a valve model TBD - requires a valve power model |
| `contaminant_mass_flow_kgps` | contamination | kg s^-1 | **gap** | — | — | TBD - requires contaminant transport through IF-A1..IF-A4 |
| `feed_pressure_envelope_ok` | quality | - | **supplied** | `abep_sim/archengine.py:P_ion_envelope_violation` | `abep_sim/archengine.py:_propulsion` | computed by the consumer; flag = not violation |
| `upstream_state_trustworthy` | quality | - | **gap** | — | — | TBD - requires the upstream convergence/domain flags listed as gaps in IF-A2..IF-A4 |

Not applicable here: shaft_power (passive element).

### IF-X1: Xe chamber (tank) -> Xe valve

Xenon storage outflow. The code sizes the tank mass (mass_bom.xe_tank) and books Xe consumption (thruster.xe_for_thrust, cathode/neutralizer Xe flows, transient.run_mission Xe budget); it has no storage thermodynamic state or regulator model.

| field | class | unit | status | producer (file:function → key) | consumer | notes / what is missing |
|---|---|---|---|---|---|---|
| `mdot_xe_kgps` | mdot_s | kg s^-1 | **derivable** | `abep_sim/thruster.py:xe_for_thrust`; `abep_sim/thruster.py:Cathode` → `xe_flow_mgps` (mg s^-1); `abep_sim/archengine.py:Neutralizer` → `xe_mgps` (mg s^-1) | `abep_sim/transient.py:run_mission` | derive: xe_for_thrust (anode topping) + cathode/neutralizer Xe flow |
| `p_storage_Pa` | p | Pa | **partial** | `abep_sim/mass_bom.py:xe_tank` → `p_MPa` (MPa) | — | design pressure used only for wall sizing (code default), not an operating state TBD - requires a storage equation of state (Xe is near-critical at storage conditions: verify) |
| `T_storage_K` | T | K | **gap** | — | — | TBD - requires a tank thermal node |
| `xe_purity` | x_s | - | **gap** | — | — | TBD - requires a propellant purity specification |
| `dmdot_dt_kgps2` | dmdot_dt | kg s^-2 | **gap** | — | — | TBD - requires regulator/valve dynamics |
| `xe_inventory_kg` | inventory | kg | **partial** | `abep_sim/transient.py:run_mission` → `xe_left_kg` | `abep_sim/transient.py:run_mission` | topping budget only; cathode Xe is accounted separately (transient.py) TBD - requires a single tank inventory including cathode Xe |
| `tank_volume_m3` | inventory | m^3 | **supplied** | `abep_sim/mass_bom.py:xe_tank` → `V_L` (L) | — |  |
| `regulator_conductance_m3ps` | conductance | m^3 s^-1 | **gap** | — | — | TBD - requires a regulator model |
| `pressure_loss_Pa` | pressure_loss | Pa | **gap** | — | — | TBD - requires a regulator model |
| `rejected_heat_W` | rejected_heat | W | **gap** | — | — | TBD - requires a tank thermal model |
| `contaminant_mass_flow_kgps` | contamination | kg s^-1 | **gap** | — | — | TBD - requires a purity specification |
| `xe_topping_exhausted` | quality | - | **supplied** | `abep_sim/transient.py:run_mission` → `xe_topping_exhausted` | — |  |

Not applicable here: residence_time (storage element; residence time is not a meaningful interface variable); shaft_power (passive element).

### IF-X2: Xe valve -> thruster (Xe port)

THRUSTER BOUNDARY, xenon port. Same closure-independence rule as IF-A5. Current producers are the card model (thruster.xe_for_thrust for anode topping) and the neutralizer/cathode Xe parameters; the Hall-physics branch of archengine has no anode Xe flow, and the HallThruster bridge takes one propellant per case.

| field | class | unit | status | producer (file:function → key) | consumer | notes / what is missing |
|---|---|---|---|---|---|---|
| `mdot_xe_anode_kgps` | mdot_s | kg s^-1 | **supplied** | `abep_sim/thruster.py:xe_for_thrust` | `abep_sim/thruster.py:performance` → `mdot_xe_anode`; `abep_sim/transient.py:run_mission` | card model only |
| `mdot_xe_cathode_kgps` | mdot_s | kg s^-1 | **supplied** | `abep_sim/thruster.py:Cathode` → `xe_flow_mgps` (mg s^-1); `abep_sim/archengine.py:Neutralizer` → `xe_mgps` (mg s^-1) | `abep_sim/archengine.py:close_architecture` → `xe_mgps`; `abep_sim/system.py:evaluate` | parameters (code defaults) |
| `p_feed_Pa` | p | Pa | **gap** | — | — | TBD - requires a regulator/valve model |
| `T_gas_K` | T | K | **gap** | — | external: HallThruster.jl v0.23.1 src/physics/gas.jl, struct Propellant field temperature_K | TBD - requires a feed thermal state |
| `xe_purity` | x_s | - | **gap** | — | — | TBD - requires a purity specification |
| `dmdot_dt_kgps2` | dmdot_dt | kg s^-2 | **gap** | — | — | TBD - requires valve dynamics |
| `feed_line_inventory_kg` | inventory | kg | **gap** | — | — | TBD - requires feed-line geometry |
| `feed_line_residence_time_s` | residence_time | s | **gap** | — | — | TBD - requires feed-line geometry |
| `valve_conductance_m3ps` | conductance | m^3 s^-1 | **gap** | — | — | TBD - requires a valve model |
| `pressure_loss_Pa` | pressure_loss | Pa | **gap** | — | — | TBD - requires a valve/line model |
| `valve_rejected_heat_W` | rejected_heat | W | **partial** | `abep_sim/system.py:Budgets` → `p_ctrl_valves_sensors_W` | `abep_sim/system.py:evaluate` | same single lumped budget as IF-A5 (not additive) TBD - requires a valve power model |
| `contaminant_mass_flow_kgps` | contamination | kg s^-1 | **gap** | — | — | TBD - requires a purity specification |
| `xe_feed_state_trustworthy` | quality | - | **gap** | — | — | TBD - requires a Xe feed model with a declared domain |

Not applicable here: shaft_power (passive element).

### Commands (controller → valves)

Demand signals from the propulsion controller to the valves. The definitions below are the same for every Hall transport-ensemble member; the member id is never an input to an upstream element.

| field | class | unit | status | producer (file:function → key) | consumer | notes / what is missing |
|---|---|---|---|---|---|---|
| `atm_mdot_setpoint_kgps` | command | kg s^-1 | **partial** | `abep_sim/transient.py:run_mission` → `frac` | — | transient.run_mission throttles by scaling the collected flow by frac = T_cmd / T_air (quasi-static) TBD - requires a valve model and a controller definition |
| `xe_mdot_setpoint_kgps` | command | kg s^-1 | **partial** | `abep_sim/transient.py:run_mission` → `xe_rate` | — | xe_rate = thruster.xe_for_thrust(...) when air thrust is short and the Xe policy allows TBD - requires a valve model and a controller definition |

## 5. Mapping at the thruster boundary (consumer side)

The ICD stops at IF-A5/IF-X2. On the other side, HallThruster.jl v0.23.1 (pinned, `hallthruster_bridge/PINNED.toml`)
takes `propellants::Vector{Propellant}`. Each `Propellant` has `gas`, `flow_rate_kg_s`, `velocity_m_s`, `temperature_K`
and `ion_temperature_K` (read from `src/physics/gas.jl` of the installed package; its `Project.toml` says version 0.23.1,
and `hallthruster_bridge/Manifest.toml` pins repo-rev `bfb3019…`). In the same package's `src/physics/constants.jl`, the
defaults when a field is unset are `DEFAULT_NEUTRAL_TEMPERATURE_K = 500.0` and `DEFAULT_NEUTRAL_VELOCITY_M_S = 150.0`.
The docstring says the velocity is computed from `temperature_K` (one-sided Maxwellian flux) when that is set. These are
solver defaults (evidence class: assumed), not upstream data.

| ICD field | HallThruster.jl input | wired today? |
|---|---|---|
| IF-A5 `mdot_anode_s_kgps` (per species) | `Propellant(gas, flow_rate_kg_s=…)`, one per gas | no. `bridge_lib.jl` builds one propellant from the case file's `mdot_kgps` |
| IF-A5 `T_gas_K` | `Propellant.temperature_K` | no. `bridge_lib.jl` doesn't pass it. The N2/N propellant config `hallthruster_bridge/propellants/n2_n.toml` declares its own per-species `temperature_K`, and otherwise the solver default applies. Neither comes from the upstream chain |
| IF-X2 `mdot_xe_anode_kgps` | `Propellant("Xe", flow_rate_kg_s=…)` | no (Xe cases come from case files) |
| IF-A5 `mdot_cathode_air_kgps`, IF-X2 `mdot_xe_cathode_kgps` | no mapping in the current bridge | TBD |
| IF-A5 `p_feed_Pa` | none (it's used by `archengine._propulsion`'s ionizer envelope check) | n/a |

None of these inputs is a transport-closure or calibration-nuisance quantity. That's why the boundary is
closure-independent. The transport model, `ensemble_member_id` and every facility setting stay in the Hall map's own
`meta` (`hall_map_schema_v1.json`), on the thruster side.

## 6. Coverage

Each cell lists the distinct statuses of that interface's fields in that variable class. The per-field tables above
have the details.

| variable class | IF-A0 | IF-A1 | IF-A2 | IF-A3 | IF-A4 | IF-A5 | IF-X1 | IF-X2 |
|---|---|---|---|---|---|---|---|---|
| mdot_s | supplied + derivable + partial | supplied + partial | partial | supplied + derivable | supplied | supplied + derivable | derivable | supplied |
| p | supplied | supplied | partial | supplied + derivable | supplied | supplied | partial | gap |
| T | supplied | partial | partial | supplied + partial | supplied | partial | gap | gap |
| x_s | supplied + derivable | derivable + partial | derivable + partial | supplied + derivable | supplied + derivable | supplied + derivable | gap | gap |
| dmdot_dt | gap | gap | gap | partial | partial | gap | gap | gap |
| inventory | n/a | gap | gap | gap | supplied + derivable | gap | supplied + partial | gap |
| residence_time | n/a | partial + gap | gap | partial | supplied | gap | n/a | gap |
| conductance | n/a | supplied | partial | supplied | supplied | partial | gap | gap |
| pressure_loss | n/a | n/a | gap | n/a | gap | gap | gap | gap |
| shaft_power | n/a | n/a | n/a | supplied + derivable | n/a | n/a | n/a | n/a |
| rejected_heat | n/a | partial | gap | partial | gap | partial | gap | partial |
| contamination | supplied | supplied + gap | gap | supplied + gap | gap | gap | gap | gap |
| quality | supplied + derivable | supplied | gap | supplied + gap | gap | supplied + gap | supplied | gap |


Interface fields by status: 53 supplied, 15 derivable, 23 partial, 45 gap (136 total; commands not counted).

## 7. Gap register

Code findings made while aligning the ICD with the code at `7b219ba`. They're stated, not fixed: fixing them is code
work outside this ICD. Where a fix would move golden benchmarks, it's a model change under CLAUDE.md rule 2. None of them
is a tuning suggestion.

| # | finding | evidence (file:function) | ICD fields affected |
|---|---|---|---|
| G-01 | **The filter's flow effect is absent on the production path.** The frozen TPMC surface has no filter (`response_surface` builds `IntakeGeometry` without one). With `IntakeParams.filter=True`, `intake.collection` only adds filter mass. The filter transmission (`filter_open_frac`, `filter_transmission`) is applied only by a direct `intake_tpmc.intake_response` call | `abep_sim/intake.py:collection`; `abep_sim/intake_tpmc.py:intake_response`, `response_surface` | IF-A2 `mdot_total_kgps`, `mdot_s_kgps`, `filter_transmission`, `filter_flow_effect_applied` |
| G-02 | **Species-selective collection is lost.** The frozen surface is species-resolved, but `IntakeSurface.__call__` returns only the mass-weighted mean `eta_c`. `system.evaluate` then splits the collected flow by free-stream mass fractions (`md_in`) | `abep_sim/intake_tpmc.py:IntakeSurface.__call__`; `abep_sim/system.py:evaluate` | IF-A1/IF-A2 `mdot_s_kgps`, `w_s` |
| G-03 | **No convergence flag from the compressor leak fixed point.** `DragCompressor.run` iterates up to 40 times and returns the last iterate either way (CLAUDE.md rule 3) | `abep_sim/compressor.py:DragCompressor.run` | IF-A3 `recirculation_converged` |
| G-04 | **No convergence flag from the chamber balance.** `Reservoir.steady_state` iterates up to 200 times and returns the last iterate either way | `abep_sim/reservoir.py:Reservoir.steady_state` | IF-A4 `steady_state_converged` |
| G-05 | **Orifice sizing returns no residual.** `size_orifice_for_pressure` bisects in [1e-8, 3e-2] m² for 60 steps and returns the area. If the target is unreachable inside the bracket, the result sits at a bracket end with no flag | `abep_sim/reservoir.py:size_orifice_for_pressure` | IF-A4 `orifice_sizing_converged` |
| G-06 | **No valve model.** Valve, feed line and anode distributor are one molecular-flow orifice (`Reservoir.anode_orifice_area_m2 × anode_orifice_K`), sized by G-05 to hit the target chamber pressure. Valve power is part of one lumped budget `Budgets.p_ctrl_valves_sensors_W` shared by valves, sensors and control | `abep_sim/reservoir.py`; `abep_sim/system.py:Budgets` | IF-A4/IF-A5/IF-X2 conductance, pressure loss, valve heat, commands |
| G-07 | **Gas temperature is not a propagated state.** Plenum: two unrelated parameters (`IntakeGeometry.T_wall_K` for CR_passive, `CompressorParams.T_out_K` for `p_passive_Pa`). Compressor: parameter `DragCompressor.T_gas_K`. Chamber: `T_K` set from the compressor machine temperature, clamped to 300–500 K. `gas_path_state` doesn't pass T to the thruster, and the Hall-side neutral temperature comes from the solver default or the N2/N propellant config, never from upstream (section 5) | `abep_sim/intake_tpmc.py:IntakeGeometry`; `abep_sim/intake.py:CompressorParams`; `abep_sim/compressor.py:DragCompressor`; `abep_sim/system.py:evaluate`; `abep_sim/archengine.py:gas_path_state`; `hallthruster_bridge/bridge_lib.jl` | IF-A1..IF-A5 `T_gas_K` |
| G-08 | **No pressure-loss model** for the filter, feed line, valve or Xe regulator | none | every `pressure_loss_Pa` |
| G-09 | **Flow dynamics are mostly absent.** The frozen atmosphere is orbit-averaged by construction. `transient.run_mission` is quasi-static (it scales mdot per time step). The only rate is the spin-up ramp in `reservoir.startup_transient`, and its history is (t, p) only | `abep_sim/atmosphere.py:atmosphere`; `abep_sim/transient.py:run_mission`; `abep_sim/reservoir.py:startup_transient` | every `dmdot_dt_kgps2` |
| G-10 | **`V_rel` is never produced.** Consumers read `atm.get("V_rel", atm["V"])`, but `atmosphere()` returns only the orbital speed `V` | `abep_sim/atmosphere.py:atmosphere`; `abep_sim/intake.py:collection` | IF-A0 `V_mps` |
| G-11 | **No contamination transport.** Code has AO flux/energy/fluence and erosion depths and rates (`aochem`, `life`), and outgassing properties (`materials.Material.tml_pct`, `cvcm_pct`), but no non-propellant mass flow in any stream | `abep_sim/aochem.py`; `abep_sim/life.py`; `abep_sim/materials.py` | every `contaminant_mass_flow_kgps`, `filter_retained_mass_rate_kgps` |
| G-12 | **Xe path has no storage state.** `mass_bom.xe_tank` sizes the wall from a design pressure parameter. There's no tank p/T state and no regulator. `transient.run_mission` tracks the topping budget (`xe_left_kg`) separately from cathode Xe | `abep_sim/mass_bom.py:xe_tank`; `abep_sim/transient.py:run_mission` | IF-X1, IF-X2 |
| G-13 | **No upstream uncertainty is produced.** The only upstream prior is `uq_modular.PRIORS["accommodation"]`, which is sampled and not carried | `abep_sim/uq_modular.py` | every `uncertainty` |
| G-14 | **Species and propellant scope.** The chamber models O/O2/N2 only (`Reservoir.steady_state` species tuple). The Hall bridge takes one propellant per case. Multi-species air or mixed air + Xe anode feed isn't wired (CLAUDE.md Next work 4 gates intake-delivered mixtures behind items 1–3) | `abep_sim/reservoir.py`; `hallthruster_bridge/bridge_lib.jl` | IF-A4, IF-A5, IF-X2 |
| G-15 | **Chamber volume isn't linked to the vessel mass.** `system.evaluate` calls `mass_bom.reservoir_vessel` with a literal volume instead of `Reservoir.volume_m3` | `abep_sim/system.py:evaluate` | IF-A4 `chamber_volume_m3` |
| G-16 | **Wall-collision counts are heuristics without a source.** Physics path: `upstream_collisions = 10 × turbo_rows + 50 × n_stages` (`system.evaluate`). Parametric path: `AOParams` collision counts (`aochem.recombination_fraction`) | `abep_sim/system.py:evaluate`; `abep_sim/aochem.py:AOParams` | IF-A3 `upstream_wall_collisions`; IF-A4 `O_survival` |
| G-17 | **Compressor heat split is assumed.** `thermal.default_nodes` books the full compressor electrical input as compressor-node heat. The compressor doesn't report its own split | `abep_sim/thermal.py:default_nodes` | IF-A3 `rejected_heat_W` |

## 8. How the checks work

`python -m pytest -q tests/test_upstream_icd.py` covers the following. jsonschema isn't a project dependency, so the
test carries a small validator for the keyword subset the schema uses, and one test keeps the schema inside that subset.

* The schema parses, is Draft 2020-12, is versioned (`x-icd.version` = `icd_version` const, major = file suffix), and
  every `$ref` resolves.
* Every field has a unit from `x-icd.units`, the schema enforces it (`const`), and a record with a wrong or missing unit
  is rejected.
* A non-null scalar needs one of the six evidence classes.
* Every interface covers all 13 variable classes (field or not-applicable reason).
* Status semantics hold. Gaps say "TBD - requires …" and name no producer. Supplied/partial/derivable fields name
  existing code. Derivable fields state their derivation.
* **Every `python` producer/consumer imports and its attribute exists. Every `output_key` appears in that function's
  source. Every `repo_file` exists and contains its token.**
* Closure independence: sections 2 and 7 above. Forbidden identifiers include the ensemble's calibration-nuisance keys,
  no field or producer violates them, and the thruster-boundary records reject such fields.
* This document names every interface and field.

The fixture record in the test carries null values only. The test introduces no data.

## 9. Open questions for the owner

1. **Filter (G-01).** Should the filter become a separate element with its own transmission on the production path, or
   stay lumped in the intake? Applying it on the production path would be a model change and could move goldens.
2. **Per-member setpoints.** In whole-system UQ, may the controller's flow setpoints differ per admitted Hall member, or
   must the setpoint schedule be fixed independently of the member? The ICD defines them member-independently either way.
3. **Composition basis at the Hall boundary.** Should Hall maps take species-resolved flows (one propellant per species)
   or total flow plus a composition axis? If an axis, is it mole or mass fraction?
4. **Gas temperature into the Hall solver (G-07).** Should future bridge runs pass IF-A5 `T_gas_K` to
   `Propellant.temperature_K`? That's a bridge change for future maps only, never for the running or pre-registered
   campaigns.
5. **Contamination scope (G-11).** Which contaminants must be tracked (erosion products, outgassing, particulates), and
   from which cited sources?
6. **Xe path scope (G-12).** Tank equation of state, regulator model, and one shared inventory for topping and cathode Xe?
7. **Convergence flags (G-03 to G-05).** Adding flags doesn't change values, but it touches the gas-path modules. The
   owner decides when.
8. **Upstream uncertainty (G-13).** Which upstream quantities should carry uncertainty fields first, and with what evidence?

The owner integrates any docs/HISTORY.md or CLAUDE.md entry for this ICD.
