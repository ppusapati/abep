# Architecture-specific failure trees (v1, DRAFT for owner review)

This lane (FTREE, lane 26) lists how each candidate thrust architecture could fail the programme. It also says which single
piece of evidence would settle the most of those failure paths. It is track-2 work (architecture comparison preparation)
and is built to run **without absolute Hall predictions**.

| file | role |
|---|---|
| `failure_trees_v1.json` | the trees: nodes, failure classes, hard gates, sources, resolving actions, ranking rule; generated derived values and ranking |
| `../../../schemas/architecture_comparison/failure_tree_v1.schema.json` | JSON Schema for the file |
| `derive_failure_tree.py` | deterministic generator of the derived values, the ranking and the generated tables below (`--check` verifies) |
| `../../../tests/test_failure_tree.py` | schema, status rule, gate links, class coverage, ranking and generator checks |

**No winner.** No architecture is eliminated or preferred. Every node is `decision_state = open`. *Evidence status* says
whether published evidence makes a failure path **credible**. It is not a verdict on any Vyovrinda design. The ranking
orders *evidence to acquire*, not architectures.

## Milestones this supports
- **Supports A (conditional selection).** Each open node carries a `milestone_A_condition` sentence. For any architecture,
  the list of its open nodes is the condition list that a statement like "architecture X is baseline provided that ..."
  must carry.
- **To reach B (physics-backed selection),** every `resolve_by_milestone = B` node of the selected architecture must be
  resolved. Nodes marked *analysis needs admitted Hall closure* can be resolved by analysis only on design Hall maps from
  **admitted** closures. The credible set is empty today, so for now they can only be resolved by measurement.
  Common-boundary performance comes from `abep_sim/arch_boundary.py` and `abep_sim/arch_compare.py`.
- **To reach C (proposal/PDR freeze),** every `resolve_by_milestone = C` node must be resolved: cathode, thermal, erosion,
  mass, start/restart and transition. The owner must also fix the restart count, the allowed Xe roles and the Xe
  allocation, so that the TBD thresholds become numbers.

## Structure
- **Architectures** `hall_only`, `rf_hall`, `ecr_hall`. The RF and ECR arms change only the pre-ionization method. Nodes on
  the common Hall accelerator, feed state, cathode and bus boundary therefore carry all three ids. Each architecture's
  tree is its set of nodes under the top event "architecture fails the programme". All links are OR: any node that
  resolves to fail on a hard gate fails the architecture. No probabilities are attached.
- **Failure classes.** Nine are generic and apply to all three architectures: ignition, sustainment/extinction,
  utilization, cathode limit, thermal limit (Hall magnetic circuit, channel walls and anode, RF coil/coupler, ECR
  magnets/resonator), erosion/wall life, power limit, mass limit and control/startup. Three are
  architecture-specific: interstage loss (`rf_hall`, `ecr_hall`), RF-source modes (`rf_hall`: E–H transition,
  matching, magnetized-source field interaction, RF interference) and ECR modes (`ecr_hall`: cutoff/overdense limit,
  ECR–Hall magnetic interaction, microwave power chain).
- **Hard gates** (ids used by `decision_quantity.gates`):
  - `thrust`: 12–25 mN.
  - `bus_power`: < 1.5 kW.
  - `mass`: < 40 kg.
  - `firing_life`: > 15,000 h.
  - `mission_life`: 26,000 h.
  - `restart_sustainment`: the count is TBD.
  - `air_xe`: the allowed Xe roles are TBD.

  The numbers come from `abep_sim/constants.py` `RFPConstraints` (RFP Part III Para 2); the test checks them. Each gate
  also names the existing `abep_sim/system.py` check it corresponds to.

  Each gate also carries `matrix_gate_id`, its one-to-one link to the hard-gate matrix
  (`docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json`, built by another lane and still a draft):

  | this file | hard-gate matrix |
  |---|---|
  | `thrust` | `G1_thrust` |
  | `bus_power` | `G2_bus_power` |
  | `mass` | `G3_mass` |
  | `firing_life` | `G4_firing_life` |
  | `mission_life` | `G5_mission` |
  | `restart_sustainment` | `G6_ignition_sustainment` |
  | `air_xe` | `G7_air_xenon` |

  Thermal and cathode nodes also list the matrix's PROPOSED, non-binding gates `P1_thermal` and `P2_cathode` in
  `proposed_gate_links`. These never count as gates in the ranking. The owner should confirm the mapping once the matrix
  is merged.
- **Node fields:**
  - `mechanism` and `physical_cause`.
  - `evidence`: each item gives a source, a direction (`supports` / `contradicts` / `context`), the EVIDENCE.md quantity
    type (`evidence_class`), an evidence level, a quoted or paraphrased statement, a verified locator and its
    applicability.
  - `evidence_status`, and `evidence_gap` when nothing decides.
  - `decision_quantity`: a quantity, a threshold, and a threshold status (`RFP`, `PROPOSED`, `TBD` or `physics_bound`),
    with gate links. `requires_actions` lists every other action whose output the threshold comparison needs (for
    example A-ELEC for "within 1500 W minus all other loads"). `requires_owner_inputs` lists the owner-fixed inputs
    (thresholds, margins, allocations, allowed Xe roles, operations assumptions).
  - `actions`: each is `decides`, `contributes` or `informs`, as defined in `action_effects`:
    - **decides**: the action's output alone settles the node, given only owner-fixed and design-fixed inputs
      (component ratings, datasheet limits).
    - **contributes**: a necessary member of a jointly sufficient set, and not sufficient alone. A node therefore has
      either no contributing action or at least two.
    - **informs**: narrows, prioritises or cross-checks the node but is not needed to settle it. Examples are a
      literature search, an unvalidated model or a blocked Hall-map analysis.

    If `requires_actions` names an action, no other action may decide the node. Every required action contributes and
    appears in `cheapest_resolution`. The test enforces all of this, so the ranking counts cannot be inflated by
    labelling.
  - `cheapest_resolution`.
  - `resolve_by_milestone`.
  - `analysis_requires_admitted_hall_closure`.
  - `decision_state`.

## Evidence-status rule (deterministic; the test enforces it)
- **supported** means at least one `supports` item and no `contradicts` item.
- **contradicted** means at least one `contradicts` item and no `supports` item.
- **unknown** covers everything else: no evidence, context only, or conflicting evidence. A node with nothing decisive
  must state an `evidence_gap`.

A `contradicted` status is only as broad as the evidence behind it. For example, N-PWR-01 is contradicted by laboratory
N₂ measurements taken in a ground facility with a noble-gas cathode. That does not show that a Vyovrinda design meets the
gate.

## Ranking rule for "what evidence to acquire next" (stated in the JSON as `decisiveness_lexicographic_v1`)
For each architecture, and only over its open nodes and unblocked actions, actions are sorted by these keys in order:
1. The number of nodes the action **decides**.
2. The number of distinct hard gates linked by those decided nodes.
3. The number of nodes it **contributes** to (needed jointly with other actions).
4. The number of nodes it **informs**.
5. The cost class, cheapest first: literature < analysis < measurement.
6. The action id.

No weights, probabilities or expert scores are used. A blocked action is listed but not ranked. Today the only blocked
action is `A-HALLMAP`, which is blocked by the empty credible set and the incomplete O4 dispositions.

`cheapest_resolution` is either a single `decides` action or a jointly sufficient set of `contributes` actions. Its
cost class is never above that of the cheapest `decides` action.

**How to read the ranking.** The ranking counts labels and nothing else. Most performance nodes (utilization, bus
power, interstage transmission, break-even) compare a measurement with another lane's analysis, so they have no single
deciding action. There, the common-condition test M-PREION *contributes* together with A-ELEC or A-BREAKEVEN. Actions
that settle several nodes on their own, such as the thermal balance test and the cathode test, can therefore rank above
M-PREION on key 1. M-PREION has the largest contributes count (key 3) for `rf_hall` and `ecr_hall`. The ranking orders
evidence within one architecture's tree. It says nothing about which architecture is better.

## Per-architecture trees (generated)
<!-- BEGIN GENERATED:trees -->
### `hall_only` (18 nodes: 8 supported, 1 contradicted, 9 unknown; all decision_state = open)

| class | node | failure path | evidence status | gates | cheapest resolution | resolve by | analysis needs admitted Hall closure |
|---|---|---|---|---|---|---|---|
| ignition | N-IGN-01 | Hall-stage cold start on atmospheric anode flow fails; start needs Xe | unknown | restart_sustainment, air_xe | A-OPS + M-IGN | C | no |
| sustainment_extinction | N-SUS-01 | Hall stage extinguishes or runs unstably on N2/O2 within the needed window | unknown | restart_sustainment, thrust, air_xe | A-FLOWENV + M-SUSWIN | B | yes |
| sustainment_extinction | N-SUS-02 | Delivered-flow range over altitude and solar activity exceeds the sustainment range | supported | restart_sustainment, thrust | A-FLOWENV + M-SUSWIN | B | yes |
| utilization | N-UTL-01 | Low ion utilization of N2/O2 in the Hall stage prevents 12 mN within the bus power | supported | thrust, bus_power | A-ELEC + M-PREION | B | yes |
| cathode_limit | N-CAT-01 | Emitter poisoning by oxygen from the feed, plume backflow or ram exposure | supported | firing_life, mission_life, restart_sustainment | A-FLOWENV + M-CATHODE | C | no |
| cathode_limit | N-CAT-02 | Cathode Xe consumption over the firing life exceeds the Xe allocation in the mass gate | supported | mass, air_xe | A-MASS + M-CATHODE | C | yes |
| cathode_limit | N-CAT-03 | Cathode flow minimized for mass drives plume mode and energetic-ion erosion | supported | firing_life, mass | M-CATHODE | C | yes |
| cathode_limit | N-CAT-04 | Air-fed cathode route: electron current or coupling insufficient at the discharge current (conditional) | unknown | thrust, restart_sustainment, air_xe | M-CATHODE | C | yes |
| thermal_limit | N-THM-01 | Hall magnetic circuit (coils or permanent magnets) exceeds its temperature limit | supported | firing_life, bus_power, mass | M-THERMAL | C | yes |
| thermal_limit | N-THM-04 | Hall channel wall or anode exceeds its temperature limit | unknown | firing_life, bus_power | M-THERMAL | C | yes |
| erosion_wall_life | N-ERO-01 | Channel-wall erosion (physical and chemical) by N/O species limits firing life | supported | firing_life | A-THERMAL + M-EROSION | C | yes |
| erosion_wall_life | N-ERO-02 | Anode oxidation raises electrical resistance | supported | firing_life | A-THERMAL + M-EROSION | C | no |
| power_limit | N-PWR-01 | Hall-stage discharge power per unit thrust on air leaves no room in the 1.5 kW bus | contradicted | bus_power, thrust | A-ELEC + M-PREION | B | yes |
| power_limit | N-PWR-04 | Non-thruster loads consume the bus margin | unknown | bus_power | A-ELEC + M-PREION | B | no |
| mass_limit | N-MAS-01 | Total propulsion-system mass exceeds 40 kg | unknown | mass | A-MASS | C | no |
| control_startup | N-CTL-01 | Xe -> mixed -> atmosphere transition loses the discharge or leaves the operating window | unknown | restart_sustainment, air_xe | M-TRANS | C | no |
| control_startup | N-CTL-02 | Restart count exceeds cathode heater/ignition cycles or the Xe start budget | unknown | restart_sustainment, firing_life, mission_life, mass | A-OPS + M-IGN + M-CATHODE | C | no |
| control_startup | N-CTL-03 | Feed-system start transient too slow or overshoots after start or eclipse | unknown | restart_sustainment | A-FLOWENV | C | no |

### `rf_hall` (31 nodes: 13 supported, 1 contradicted, 17 unknown; all decision_state = open)

| class | node | failure path | evidence status | gates | cheapest resolution | resolve by | analysis needs admitted Hall closure |
|---|---|---|---|---|---|---|---|
| ignition | N-IGN-01 | Hall-stage cold start on atmospheric anode flow fails; start needs Xe | unknown | restart_sustainment, air_xe | A-OPS + M-IGN | C | no |
| ignition | N-IGN-02 | RF pre-ionizer does not break down on N2/O2 at the delivered pressure | supported | restart_sustainment, air_xe | A-FLOWENV + M-IGN | C | no |
| ignition | N-IGN-04 | Pre-ionizer seed plasma does not lower the Hall-stage start requirement | unknown | restart_sustainment, air_xe | A-FLOWENV + M-IGN | C | no |
| sustainment_extinction | N-SUS-01 | Hall stage extinguishes or runs unstably on N2/O2 within the needed window | unknown | restart_sustainment, thrust, air_xe | A-FLOWENV + M-SUSWIN | B | yes |
| sustainment_extinction | N-SUS-02 | Delivered-flow range over altitude and solar activity exceeds the sustainment range | supported | restart_sustainment, thrust | A-FLOWENV + M-SUSWIN | B | yes |
| sustainment_extinction | N-SUS-03 | Two-stage coupling: excess acceleration-stage current or unstable interaction limits the Hall stage | supported | thrust, bus_power, restart_sustainment | M-PREION | B | yes |
| utilization | N-UTL-01 | Low ion utilization of N2/O2 in the Hall stage prevents 12 mN within the bus power | supported | thrust, bus_power | A-ELEC + M-PREION | B | yes |
| utilization | N-UTL-02 | RF pre-ionization gains less utilization than its power costs (thrust-to-power falls) | supported | thrust, bus_power | A-BREAKEVEN + A-ELEC + M-PREION | B | yes |
| cathode_limit | N-CAT-01 | Emitter poisoning by oxygen from the feed, plume backflow or ram exposure | supported | firing_life, mission_life, restart_sustainment | A-FLOWENV + M-CATHODE | C | no |
| cathode_limit | N-CAT-02 | Cathode Xe consumption over the firing life exceeds the Xe allocation in the mass gate | supported | mass, air_xe | A-MASS + M-CATHODE | C | yes |
| cathode_limit | N-CAT-03 | Cathode flow minimized for mass drives plume mode and energetic-ion erosion | supported | firing_life, mass | M-CATHODE | C | yes |
| cathode_limit | N-CAT-04 | Air-fed cathode route: electron current or coupling insufficient at the discharge current (conditional) | unknown | thrust, restart_sustainment, air_xe | M-CATHODE | C | yes |
| thermal_limit | N-THM-01 | Hall magnetic circuit (coils or permanent magnets) exceeds its temperature limit | supported | firing_life, bus_power, mass | M-THERMAL | C | yes |
| thermal_limit | N-THM-02 | RF coil/antenna, matching network or discharge tube overheats | unknown | bus_power, firing_life | M-THERMAL | C | no |
| thermal_limit | N-THM-04 | Hall channel wall or anode exceeds its temperature limit | unknown | firing_life, bus_power | M-THERMAL | C | yes |
| erosion_wall_life | N-ERO-01 | Channel-wall erosion (physical and chemical) by N/O species limits firing life | supported | firing_life | A-THERMAL + M-EROSION | C | yes |
| erosion_wall_life | N-ERO-02 | Anode oxidation raises electrical resistance | supported | firing_life | A-THERMAL + M-EROSION | C | no |
| erosion_wall_life | N-ERO-03 | RF source window/tube erosion or conductive coating degrades coupling | unknown | firing_life | A-THERMAL + M-EROSION | C | no |
| power_limit | N-PWR-01 | Hall-stage discharge power per unit thrust on air leaves no room in the 1.5 kW bus | contradicted | bus_power, thrust | A-ELEC + M-PREION | B | yes |
| power_limit | N-PWR-02 | RF source power plus generator loss pushes the bus above 1.5 kW at 12 mN | supported | bus_power, thrust | A-ELEC + M-PREION | B | yes |
| power_limit | N-PWR-04 | Non-thruster loads consume the bus margin | unknown | bus_power | A-ELEC + M-PREION | B | no |
| mass_limit | N-MAS-01 | Total propulsion-system mass exceeds 40 kg | unknown | mass | A-MASS | C | no |
| mass_limit | N-MAS-02 | RF generator, matching network, coil and shielding exceed the mass margin | unknown | mass | A-MASS | C | no |
| control_startup | N-CTL-01 | Xe -> mixed -> atmosphere transition loses the discharge or leaves the operating window | unknown | restart_sustainment, air_xe | M-TRANS | C | no |
| control_startup | N-CTL-02 | Restart count exceeds cathode heater/ignition cycles or the Xe start budget | unknown | restart_sustainment, firing_life, mission_life, mass | A-OPS + M-IGN + M-CATHODE | C | no |
| control_startup | N-CTL-03 | Feed-system start transient too slow or overshoots after start or eclipse | unknown | restart_sustainment | A-FLOWENV | C | no |
| interstage_loss | N-ISL-RF | Ions made in the RF stage are lost before the Hall acceleration zone | unknown | thrust, bus_power | A-BREAKEVEN + M-PREION | B | yes |
| rf_source_specific | N-RF-01 | E-H (or helicon) mode transition with hysteresis drops the RF stage to a low-density mode | supported | restart_sustainment, bus_power, thrust | A-FLOWENV + M-RFSRC | B | no |
| rf_source_specific | N-RF-02 | Impedance mismatch (reflected power) across ignition, Xe <-> air change and flow envelope | unknown | bus_power, restart_sustainment | A-ELEC + M-RFSRC | C | no |
| rf_source_specific | N-RF-03 | Magnetized RF (helicon) source field interacts with the Hall magnetic circuit (conditional) | unknown | thrust, restart_sustainment | A-BFIELD | B | no |
| rf_source_specific | N-RF-04 | RF interference coupling into the Hall discharge circuit, cathode or PPU sensing | unknown | restart_sustainment | M-PREION | C | no |

### `ecr_hall` (30 nodes: 12 supported, 1 contradicted, 17 unknown; all decision_state = open)

| class | node | failure path | evidence status | gates | cheapest resolution | resolve by | analysis needs admitted Hall closure |
|---|---|---|---|---|---|---|---|
| ignition | N-IGN-01 | Hall-stage cold start on atmospheric anode flow fails; start needs Xe | unknown | restart_sustainment, air_xe | A-OPS + M-IGN | C | no |
| ignition | N-IGN-03 | ECR pre-ionizer does not break down on air at the delivered pressure | unknown | restart_sustainment, air_xe | A-FLOWENV + M-ECRSRC | C | no |
| ignition | N-IGN-04 | Pre-ionizer seed plasma does not lower the Hall-stage start requirement | unknown | restart_sustainment, air_xe | A-FLOWENV + M-IGN | C | no |
| sustainment_extinction | N-SUS-01 | Hall stage extinguishes or runs unstably on N2/O2 within the needed window | unknown | restart_sustainment, thrust, air_xe | A-FLOWENV + M-SUSWIN | B | yes |
| sustainment_extinction | N-SUS-02 | Delivered-flow range over altitude and solar activity exceeds the sustainment range | supported | restart_sustainment, thrust | A-FLOWENV + M-SUSWIN | B | yes |
| sustainment_extinction | N-SUS-03 | Two-stage coupling: excess acceleration-stage current or unstable interaction limits the Hall stage | supported | thrust, bus_power, restart_sustainment | M-PREION | B | yes |
| utilization | N-UTL-01 | Low ion utilization of N2/O2 in the Hall stage prevents 12 mN within the bus power | supported | thrust, bus_power | A-ELEC + M-PREION | B | yes |
| utilization | N-UTL-03 | ECR pre-ionization gains less utilization on air than its power costs | supported | thrust, bus_power | A-BREAKEVEN + A-ELEC + M-PREION | B | yes |
| cathode_limit | N-CAT-01 | Emitter poisoning by oxygen from the feed, plume backflow or ram exposure | supported | firing_life, mission_life, restart_sustainment | A-FLOWENV + M-CATHODE | C | no |
| cathode_limit | N-CAT-02 | Cathode Xe consumption over the firing life exceeds the Xe allocation in the mass gate | supported | mass, air_xe | A-MASS + M-CATHODE | C | yes |
| cathode_limit | N-CAT-03 | Cathode flow minimized for mass drives plume mode and energetic-ion erosion | supported | firing_life, mass | M-CATHODE | C | yes |
| cathode_limit | N-CAT-04 | Air-fed cathode route: electron current or coupling insufficient at the discharge current (conditional) | unknown | thrust, restart_sustainment, air_xe | M-CATHODE | C | yes |
| thermal_limit | N-THM-01 | Hall magnetic circuit (coils or permanent magnets) exceeds its temperature limit | supported | firing_life, bus_power, mass | M-THERMAL | C | yes |
| thermal_limit | N-THM-03 | ECR magnets lose remanence or the resonator/coupler overheats | supported | firing_life, bus_power | M-THERMAL | C | no |
| thermal_limit | N-THM-04 | Hall channel wall or anode exceeds its temperature limit | unknown | firing_life, bus_power | M-THERMAL | C | yes |
| erosion_wall_life | N-ERO-01 | Channel-wall erosion (physical and chemical) by N/O species limits firing life | supported | firing_life | A-THERMAL + M-EROSION | C | yes |
| erosion_wall_life | N-ERO-02 | Anode oxidation raises electrical resistance | supported | firing_life | A-THERMAL + M-EROSION | C | no |
| erosion_wall_life | N-ERO-04 | ECR antenna/window erosion or coating in air plasma | unknown | firing_life | A-THERMAL + M-EROSION | C | no |
| power_limit | N-PWR-01 | Hall-stage discharge power per unit thrust on air leaves no room in the 1.5 kW bus | contradicted | bus_power, thrust | A-ELEC + M-PREION | B | yes |
| power_limit | N-PWR-03 | Microwave source power plus conversion loss (and electromagnet power) pushes the bus above 1.5 kW at 12 mN | unknown | bus_power, thrust | A-ELEC + M-PREION | B | yes |
| power_limit | N-PWR-04 | Non-thruster loads consume the bus margin | unknown | bus_power | A-ELEC + M-PREION | B | no |
| mass_limit | N-MAS-01 | Total propulsion-system mass exceeds 40 kg | unknown | mass | A-MASS | C | no |
| mass_limit | N-MAS-03 | Microwave generator, waveguide/coupler and ECR magnets exceed the mass margin | unknown | mass | A-MASS | C | no |
| control_startup | N-CTL-01 | Xe -> mixed -> atmosphere transition loses the discharge or leaves the operating window | unknown | restart_sustainment, air_xe | M-TRANS | C | no |
| control_startup | N-CTL-02 | Restart count exceeds cathode heater/ignition cycles or the Xe start budget | unknown | restart_sustainment, firing_life, mission_life, mass | A-OPS + M-IGN + M-CATHODE | C | no |
| control_startup | N-CTL-03 | Feed-system start transient too slow or overshoots after start or eclipse | unknown | restart_sustainment | A-FLOWENV | C | no |
| interstage_loss | N-ISL-ECR | Ions made in the ECR stage are trapped or lost before the Hall acceleration zone | supported | thrust, bus_power | A-BREAKEVEN + M-PREION | B | yes |
| ecr_source_specific | N-ECR-01 | Cutoff (overdense) limit: ECR-stage density saturates below the Hall-stage feed need | unknown | thrust, bus_power | A-INTERSTAGE + M-ECRSRC | B | yes |
| ecr_source_specific | N-ECR-02 | ECR resonance field interacts with the Hall magnetic circuit | unknown | thrust, restart_sustainment | A-BFIELD | B | no |
| ecr_source_specific | N-ECR-03 | Microwave power chain (generator, transmission, coupler) efficiency or life insufficient | unknown | bus_power, firing_life, mission_life | A-ELEC + A-THERMAL | C | no |
<!-- END GENERATED:trees -->

## What evidence to acquire next, per architecture (generated)
<!-- BEGIN GENERATED:ranking -->
### `hall_only` (18 open nodes)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | M-CATHODE (Cathode integration test) | measurement | 2 | 5 (thrust, mass, firing_life, restart_sustainment, air_xe) | 3 | 0 |
| 2 | M-THERMAL (Thermal balance test) | measurement | 2 | 3 (bus_power, mass, firing_life) | 0 | 0 |
| 3 | M-TRANS (Xe -> mixed -> air transition) | measurement | 1 | 2 (restart_sustainment, air_xe) | 0 | 0 |
| 4 | A-FLOWENV (Delivered-feed envelope and start transient (upstream only)) | analysis | 1 | 1 (restart_sustainment) | 3 | 0 |
| 5 | A-MASS (Mass ledger) | analysis | 1 | 1 (mass) | 1 | 0 |
| 6 | A-ELEC (Electrical closure on the common bus boundary) | analysis | 0 | 0 (-) | 3 | 0 |
| 7 | M-PREION (Common-condition pre-ionizer A/B/C test) | measurement | 0 | 0 (-) | 3 | 0 |
| 8 | A-THERMAL (Thermal/life analysis) | analysis | 0 | 0 (-) | 2 | 2 |
| 9 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 2 | 0 |
| 10 | M-EROSION (Short erosion/oxidation test on air) | measurement | 0 | 0 (-) | 2 | 0 |
| 11 | M-IGN (Ignition and restart on the atmospheric feed) | measurement | 0 | 0 (-) | 2 | 0 |
| 12 | M-SUSWIN (Sustainment-window map) | measurement | 0 | 0 (-) | 2 | 0 |
| 13 | L-CATHODE (Cathode oxygen tolerance and plume-mode records) | literature | 0 | 0 (-) | 0 | 4 |
| 14 | L-SITAEL (SITAEL / AETHER air-operation records) | literature | 0 | 0 (-) | 0 | 4 |
| 15 | L-WALL (Wall and anode erosion/oxidation with N and O) | literature | 0 | 0 (-) | 0 | 3 |
| 16 | L-THERMAL (Thermal limits of magnets and couplers) | literature | 0 | 0 (-) | 0 | 2 |
| blocked | A-HALLMAP (Design Hall maps from admitted closures) | not ranked | - | - | - | touches 4 |

### `rf_hall` (31 open nodes)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | M-THERMAL (Thermal balance test) | measurement | 3 | 3 (bus_power, mass, firing_life) | 0 | 0 |
| 2 | M-CATHODE (Cathode integration test) | measurement | 2 | 5 (thrust, mass, firing_life, restart_sustainment, air_xe) | 3 | 0 |
| 3 | M-PREION (Common-condition pre-ionizer A/B/C test) | measurement | 2 | 3 (thrust, bus_power, restart_sustainment) | 7 | 1 |
| 4 | A-MASS (Mass ledger) | analysis | 2 | 1 (mass) | 1 | 0 |
| 5 | M-TRANS (Xe -> mixed -> air transition) | measurement | 1 | 2 (restart_sustainment, air_xe) | 0 | 1 |
| 6 | A-BFIELD (Magnetic-field superposition) | analysis | 1 | 2 (thrust, restart_sustainment) | 0 | 0 |
| 7 | A-FLOWENV (Delivered-feed envelope and start transient (upstream only)) | analysis | 1 | 1 (restart_sustainment) | 6 | 0 |
| 8 | A-ELEC (Electrical closure on the common bus boundary) | analysis | 0 | 0 (-) | 6 | 1 |
| 9 | M-IGN (Ignition and restart on the atmospheric feed) | measurement | 0 | 0 (-) | 4 | 0 |
| 10 | A-THERMAL (Thermal/life analysis) | analysis | 0 | 0 (-) | 3 | 3 |
| 11 | M-EROSION (Short erosion/oxidation test on air) | measurement | 0 | 0 (-) | 3 | 0 |
| 12 | M-RFSRC (RF source standalone on N2/O2) | measurement | 0 | 0 (-) | 3 | 0 |
| 13 | A-BREAKEVEN (Break-even surfaces) | analysis | 0 | 0 (-) | 2 | 1 |
| 14 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 2 | 0 |
| 15 | M-SUSWIN (Sustainment-window map) | measurement | 0 | 0 (-) | 2 | 0 |
| 16 | L-HHT (Helicon-Hall two-stage records) | literature | 0 | 0 (-) | 0 | 5 |
| 17 | L-SITAEL (SITAEL / AETHER air-operation records) | literature | 0 | 0 (-) | 0 | 5 |
| 18 | L-CATHODE (Cathode oxygen tolerance and plume-mode records) | literature | 0 | 0 (-) | 0 | 4 |
| 19 | L-WALL (Wall and anode erosion/oxidation with N and O) | literature | 0 | 0 (-) | 0 | 4 |
| 20 | L-THERMAL (Thermal limits of magnets and couplers) | literature | 0 | 0 (-) | 0 | 3 |
| 21 | A-INTERSTAGE (Interstage transport model) | analysis | 0 | 0 (-) | 0 | 3 |
| 22 | L-RFMODE (RF mode transitions in N2/O2/air) | literature | 0 | 0 (-) | 0 | 2 |
| 23 | L-ECRHALL (ECR-stage and ECR-ABEP records) | literature | 0 | 0 (-) | 0 | 1 |
| blocked | A-HALLMAP (Design Hall maps from admitted closures) | not ranked | - | - | - | touches 4 |

### `ecr_hall` (30 open nodes)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | M-THERMAL (Thermal balance test) | measurement | 3 | 3 (bus_power, mass, firing_life) | 0 | 0 |
| 2 | M-CATHODE (Cathode integration test) | measurement | 2 | 5 (thrust, mass, firing_life, restart_sustainment, air_xe) | 3 | 0 |
| 3 | A-MASS (Mass ledger) | analysis | 2 | 1 (mass) | 1 | 0 |
| 4 | M-PREION (Common-condition pre-ionizer A/B/C test) | measurement | 1 | 3 (thrust, bus_power, restart_sustainment) | 7 | 0 |
| 5 | A-BFIELD (Magnetic-field superposition) | analysis | 1 | 2 (thrust, restart_sustainment) | 0 | 1 |
| 6 | M-TRANS (Xe -> mixed -> air transition) | measurement | 1 | 2 (restart_sustainment, air_xe) | 0 | 0 |
| 7 | A-FLOWENV (Delivered-feed envelope and start transient (upstream only)) | analysis | 1 | 1 (restart_sustainment) | 5 | 0 |
| 8 | A-ELEC (Electrical closure on the common bus boundary) | analysis | 0 | 0 (-) | 6 | 0 |
| 9 | A-THERMAL (Thermal/life analysis) | analysis | 0 | 0 (-) | 4 | 3 |
| 10 | M-IGN (Ignition and restart on the atmospheric feed) | measurement | 0 | 0 (-) | 4 | 0 |
| 11 | M-EROSION (Short erosion/oxidation test on air) | measurement | 0 | 0 (-) | 3 | 0 |
| 12 | A-BREAKEVEN (Break-even surfaces) | analysis | 0 | 0 (-) | 2 | 1 |
| 13 | M-ECRSRC (ECR source standalone on air) | measurement | 0 | 0 (-) | 2 | 1 |
| 14 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 2 | 0 |
| 15 | M-SUSWIN (Sustainment-window map) | measurement | 0 | 0 (-) | 2 | 0 |
| 16 | A-INTERSTAGE (Interstage transport model) | analysis | 0 | 0 (-) | 1 | 3 |
| 17 | L-ECRHALL (ECR-stage and ECR-ABEP records) | literature | 0 | 0 (-) | 0 | 10 |
| 18 | L-SITAEL (SITAEL / AETHER air-operation records) | literature | 0 | 0 (-) | 0 | 5 |
| 19 | L-CATHODE (Cathode oxygen tolerance and plume-mode records) | literature | 0 | 0 (-) | 0 | 4 |
| 20 | L-THERMAL (Thermal limits of magnets and couplers) | literature | 0 | 0 (-) | 0 | 3 |
| 21 | L-WALL (Wall and anode erosion/oxidation with N and O) | literature | 0 | 0 (-) | 0 | 3 |
| 22 | L-HHT (Helicon-Hall two-stage records) | literature | 0 | 0 (-) | 0 | 1 |
| blocked | A-HALLMAP (Design Hall maps from admitted closures) | not ranked | - | - | - | touches 4 |
<!-- END GENERATED:ranking -->

## Derived values (generated; model-derived arithmetic on cited inputs)
<!-- BEGIN GENERATED:derived -->
| id | quantity | value | unit | cross-check |
|---|---|---|---|---|
| D-ECR-B-2.45GHZ | ECR resonance field |B| = 2 pi f m_e / e | 0.0875235 | T | 0.0875 (S-TISAEV2023A pdf p. 4: 87.5 mT); rel. diff 0.0002683 |
| D-ECR-NC-2.45GHZ | Cutoff (critical) electron density n_c = epsilon_0 m_e (2 pi f)^2 / e^2 | 7.44576e+16 | m^-3 | 7.4e+16 (S-TISAEV2023A pdf p. 4: 7.4e16 m^-3); rel. diff 0.006183 |
| D-ECR-NC-5.8GHZ | Cutoff (critical) electron density n_c = epsilon_0 m_e (2 pi f)^2 / e^2 | 4.17285e+17 | m^-3 | 4e+17 (S-DIAMANT2009 Sec. V pdf p. 4: 4x10^17 m^-3); rel. diff 0.04321 |
| D-ECR-B-5.85GHZ | ECR resonance field |B| = 2 pi f m_e / e | 0.208985 | T | - |
| D-ECR-NC-5.85GHZ | Cutoff (critical) electron density n_c = epsilon_0 m_e (2 pi f)^2 / e^2 | 4.2451e+17 | m^-3 | - |
| D-RATIO-BECR-P5N2 | Ratio of the 2.45 GHz ECR resonance field to the P5 peak radial field | 6.733 | 1 | - |
| D-RATIO-BECR-P5XE | Ratio of the 2.45 GHz ECR resonance field to the P5 peak radial field | 5.386 | 1 | - |
| D-XE-PER-0.1MGPS-15000H | Xe mass consumed per 0.1 mg/s of cathode flow over the RFP firing hours | 5.4 | kg | - |
| D-XE-DIAMANT-CHECK | Xe mass for 0.5 sccm continuous cathode flow over 5 years (reproduces the source's estimate) | 7.70262 | kg | 8.0 (S-DIAMANT2009 Sec. V pdf p. 4: 'about 8 kg'); rel. diff -0.03717 |
| D-RFP-FIRING-FRACTION | Firing hours / mission hours | 0.5769 | 1 | - |
<!-- END GENERATED:derived -->

The resonance-field and cutoff values reproduce the numbers the sources state (Tisaev 2023: 87.5 mT and 7.4e16 m⁻³ at
2.45 GHz; Diamant 2009: 4e17 m⁻³ at 5.8 GHz), and the recomputed Xe mass reproduces Diamant's "about 8 kg". The
frequencies are those the cited sources used. The P5 field ratio is an illustrative scale comparison. None of these is a
Vyovrinda design value.

## Evidence discipline
- **Sources.** Open literature only, with no author contact. Every source records how it was retrieved and when. Full
  texts that were read carry the sha256 of the file read; the PDFs are not committed. Abstract-only sources are labelled
  as such. Nothing was retrieved past a paywall, cookie redirect or bot challenge. Where one blocked access, the source is
  marked `abstract_only` or `identified_not_read`, and it is never cited as evidence in the latter case.
- **Locators** give the section and the PDF page index of the downloaded file (`pdf p.`). They were checked by text
  search.
- **Hashes.** Some publisher PDFs are stamped at each download, so their bytes differ between downloads. IOP stamps
  S-TISAEV2023A with a download timestamp and a fresh trailer `/ID`. For such a source the recorded sha256 identifies
  the copy that was read. The source's `notes` say so, and the quoted text was re-found in a fresh download.
- **Unstated regime.** If an abstract-only item does not state the gas, it is `context` for a node specific to air or
  N₂/O₂, whatever it reports. The test enforces this. S-STASTNY2026 (ECR ignition at VLEO pressures) is therefore context
  for N-IGN-03 until its full text gives the composition.
- **Repository evidence.** Brabston 2025 (P5 on N₂) and Marchioni 2020 (ECHT) enter only through the repository's frozen
  audits (`hallthruster_bridge/identification/...`). They are not re-read here.
- **Hall results.** No Hall transport closure, screening candidate (`sgb-screen-*`) or withdrawn 0-D Hall result is used
  as a performance source anywhere.
- **Upstream nodes.** Nodes in the gas-supply block (`N-SUS-02`, `N-CTL-03`) carry `upstream_hall_independent = true`. Their
  upstream quantities come from the ICD lane without Hall input, so Hall-closure uncertainty does not leak upstream.
  `N-SUS-02` also carries `analysis_requires_admitted_hall_closure = true`, and the two flags do not conflict because
  they cover different halves of the node. The delivered-flow envelope (maximum/minimum flow at IF-A5) is the upstream
  half, which A-FLOWENV produces with no Hall input. The sustained flow range of the Hall stage is the downstream half.
  Only measurement (M-SUSWIN) can give it today; analysis could do so only on design Hall maps from admitted closures.
  No Hall quantity feeds the upstream half.
- **Other lanes.** Their deliverables are referenced by path only. Nothing here imports them, and the tests do not need
  them. They are:
  - `abep_sim/arch_boundary.py`, `abep_sim/arch_compare.py` and `abep_sim/thermal_life.py`;
  - `abep_sim/breakeven.py` with `docs/architecture_comparison/breakeven/`;
  - `abep_sim/interstage.py` with `schemas/architecture_comparison/interstage_v1.schema.json`;
  - `abep_sim/cathode_integration.py` with `docs/architecture_comparison/cathode_integration/`;
  - `docs/architecture_comparison/feed_envelope/`, `docs/architecture_comparison/minimum_decisive_experiment/`,
    `docs/architecture_comparison/experiment_protocol/` and `docs/architecture_comparison/hard_gates/`;
  - `docs/evidence/*`, `schemas/interfaces/`, `schemas/ledgers/` and `docs/hallmap/`.

  Where the path was taken from a draft in another lane's worktree, the `lanes` entry says so.

## Changes in 1.1.0 (review round 1)
- **Evidence directions.** These items were relabelled `contradicts`/`supports` → `context` because the cited text does
  not show the node's regime: S-STASTNY2026 on N-IGN-03 (gas not stated), S-DIAMANT2010 on N-UTL-03 (no gas,
  utilization or power trade), S-ZHOU2024 on N-PWR-02 (standalone thruster simulation), S-SUZUKI2024 on N-CAT-01 (work
  function attributed mainly to lanthanum carbide; oxygen only detected) and S-RABUNAL2024 on N-ERO-03 (oxidation, not
  conductive films; short campaign). The resulting status changes are N-IGN-03 and N-ERO-03 contradicted → unknown,
  and N-UTL-03 unknown → supported.
- **Resolving-action labels.** `requires_actions` and `action_effects` were added. Nodes whose threshold needs another
  action's output no longer have a lone decider:
  - ignition: N-IGN-01…04;
  - sustainment and utilization: N-SUS-01, N-UTL-01…03;
  - interstage: N-ISL-RF/ECR;
  - RF and ECR sources: N-RF-01/02, N-ECR-01;
  - cathode: N-CAT-01;
  - erosion (the short test needs A-THERMAL's life extrapolation): N-ERO-02…04;
  - power: N-PWR-01…04.

  Lone contributors next to a decider became `informs`: A-THERMAL on the thermal nodes, M-ECRSRC on N-ECR-02,
  A-INTERSTAGE on the interstage nodes (an unvalidated model), A-BREAKEVEN on N-PWR-02/03 and M-TRANS on N-RF-02. The
  ranking was regenerated from these labels.
- **New node.** N-THM-04 covers channel-wall and anode temperature on all three architectures. It is unknown, and its
  evidence gap is stated.
- **Wording.**
  - The ECR cutoff n_c is now called the O-mode cutoff. The low-field-side X-mode R-cutoff lies at lower density. The
    numbers are unchanged.
  - The off periods and restarts now follow from the repository's modelling choice (firing = the RFP lower bound
    15,000 h), not strictly from the RFP.
  - The S-TISAEV2023A hash note explains the per-download stamping.

## Open questions for the owner
See `open_questions_for_owner` in the JSON. In short:
- Confirm the gate-id mapping to the hard-gate matrix, and decide whether `P1_thermal` / `P2_cathode` become binding.
- Set the restart count, the allowed Xe roles and the Xe allocation.
- Accept or replace the PROPOSED thresholds and the PROPOSED elimination rule.
- Confirm the lane deliverable paths that were taken from other lanes' drafts.
- Assign a lane for the operations analysis.

## Reproduce
```
python docs/architecture_comparison/failure_tree/derive_failure_tree.py          # regenerate
python docs/architecture_comparison/failure_tree/derive_failure_tree.py --check  # verify
python -m pytest -q tests/test_failure_tree.py
```
