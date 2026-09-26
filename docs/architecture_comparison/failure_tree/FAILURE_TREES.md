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
  must carry: the core nodes plus the nodes of the design-branch options the statement assumes (cathode feed; for
  `rf_hall`, the RF source type). A conditional selection names the options it assumes.
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
- **Design branches** (`design_branches`). Some failure paths exist only under a design choice whose options are
  mutually exclusive:
  - `cathode_feed` (all three architectures): `xe_fed_thermionic` (Xe-fed LaB6/BaO-W hollow cathode; nodes N-CAT-01,
    -02, -03, -05, -06, -07) or `air_fed_plasma` (air-fed microwave/RF plasma cathode; N-CAT-04, -08, -09).
  - `rf_source_type` (`rf_hall`): `magnetized_helicon` (N-RF-03) or `unmagnetized` (no specific node).

  A node specific to one option carries `branch` and a `condition` sentence. Neither cathode option is a baseline in v1:
  the laboratory air tests cited used Xe-fed thermionic cathodes, which describes those tests, not a Vyovrinda choice.
  The cathode test is split accordingly into M-CATHXE (Xe-fed) and M-CATHAIR (air-fed); each carries its option in
  `branch` and may be credited only with nodes of that option.
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

  The generated trees table shows each link with its matrix number, for example `restart_sustainment (G6)`. One
  semantic difference is flagged for the owner: the matrix's G6 is "Ignition and sustainment on atmospheric propellant"
  (criteria G6.sustainment, G6.ignition and G6.restart_count). The local `restart_sustainment` covers the same three,
  and also restarts that use a Xe start the RFP may allow (N-IGN-01). The matrix leaves that open as well (its OD5).

  Each gate carries `links_when`, which says what a node's threshold must compare to link it (see *Node rules*).
  Thermal and cathode nodes also list the matrix's PROPOSED, non-binding gates `P1_thermal` (thermal margin) and
  `P2_cathode` (cathode life and start cycles) in `proposed_gate_links`. A node lists `P2_cathode` only for cathode life
  or start cycles, never for Xe mass or current. These never count as gates in the ranking. The owner should confirm
  the mapping once the matrix is merged.
- **Node fields:**
  - `air_specific`: true when the decision quantity is evaluated on the atmospheric (air / N₂ / O₂) feed, or the
    mechanism depends on N/O species. Evidence whose source does not state the gas cannot decide such a node (see
    Evidence discipline).
  - `sub_cause_of` (optional): the node repeats a parent node's threshold comparison (`node_rules.sub_cause_rule`). It
    takes the parent's `comparison_id`, gates, `requires_actions`, `cheapest_resolution` and deciding or contributing
    actions, its threshold names the parent, and it is **not counted** in the ranking. The sub-causes are:
    - N-MAS-02 (`rf_hall` RF chain) and N-MAS-03 (`ecr_hall` microwave chain and ECR magnets), under N-MAS-01 (total
      < 40 kg). No subsystem mass allocation exists; if the owner sets one, the node becomes a comparison of its own.
    - N-UTL-01 (low utilization of air in the Hall stage), N-PWR-02 (RF source power), N-PWR-03 (microwave and
      ECR-magnet power) and N-PWR-04 (non-thruster loads), under N-PWR-01. All of them compare the discharge power for
      12 mN on air with what the 1.5 kW bus leaves after all other loads, which is N-PWR-01's inequality.
    - N-CTL-02 (restart count against the demonstrated starts and the start Xe), under N-IGN-01, which compares the
      same start count and start Xe.

    A sub-cause keeps its own class, mechanism and evidence in the tree.
  - `mechanism`, `physical_cause` and `physical_cause_basis`. The basis says what carries the cause: `cited` (the cause
    names the source or derived-value ids that state it), `definition` (a ledger or budget identity) or `hypothesis`
    (the failure hypothesis, marked "verify").
  - `evidence`: each item gives a source, a direction (`supports` / `contradicts` / `context`), the EVIDENCE.md quantity
    type (`evidence_class`), an evidence level, a quoted or paraphrased statement, a verified locator and its
    applicability. On an air-specific node each item also declares its gas (`gas_stated` or `gas_not_stated`, see
    Evidence discipline).
  - `evidence_status`, `evidence_gap` when nothing decides, and `status_note` where the status needs a caveat.
    N-CAT-05, N-CAT-08 and N-ERO-04 carry one. There, `supported` means the mechanism operates; it is not a life
    verdict.
  - `decision_quantity`: a `comparison_id`, a quantity, a threshold, and a threshold status (`RFP`, `PROPOSED`, `TBD` or
    `physics_bound`), with gate links. `requires_actions` lists every other action whose output the threshold
    comparison needs (for example A-ELEC for "within 1500 W minus all other loads"). `requires_owner_inputs` lists the
    owner-fixed inputs (thresholds, margins, allocations, allowed Xe roles, operations assumptions).
  - `actions`: each is `decides`, `contributes` or `informs`, as defined in `action_effects`:
    - **decides**: the action's output alone settles the node, given only owner-fixed and design-fixed inputs
      (component ratings, datasheet limits).
    - **contributes**: a necessary member of a jointly sufficient set, and not sufficient alone. A node therefore has
      either no contributing action or at least two.
    - **informs**: narrows, prioritises or cross-checks the node but is not needed to settle it. Examples are a
      literature search, an unvalidated model or a blocked Hall-map analysis.

    If `requires_actions` names an action, no other action may decide the node. Every required action contributes and
    appears in `cheapest_resolution`. The test enforces all of this.
  - `cheapest_resolution`, and `alternative_resolutions` where another jointly sufficient set exists (N-IGN-02,
    N-IGN-03, N-IGN-04).
  - Each action names the `lane` that would produce it. Work that no lane produces is not hidden behind a lane that
    cannot deliver it: it sits in an unassigned lane whose deliverable starts `TBD - no lane assigned`, and the owner
    is asked about it. The unassigned lanes are `mission_ops` (A-OPS), `magnetic_interaction` (A-BFIELD),
    `cathode_oxygen_exposure` (A-OXEXPO) and `hardware_test`. Every measurement action is executed by `hardware_test`,
    because no lane at base c53b75a executes hardware tests. `specified_by` names the lanes that only specify the
    protocol or the requirement (for example the experiment protocol, the minimum decisive experiment, the cathode
    integration lane or the thermal/life framework).
  - `resolve_by_milestone`.
  - `analysis_requires_admitted_hall_closure`.
  - `decision_state`.

## Node rules (`node_rules` in the JSON; the test checks each one)
- **One comparison, counted once.** `comparison_id` names the threshold comparison. A counted node's id is `CMP-` plus
  its node id; a sub-cause carries its parent's. Take any architecture and any one choice of design-branch options: no
  two counted nodes share a `comparison_id` or a threshold text, and only N-PWR-01 states the RFP bus inequality at
  12 mN. A node whose threshold has its own basis is counted. Such a basis is a physics bound (N-ECR-01), a component
  rating or allowance (N-RF-02, N-ECR-03), a design tolerance (N-RF-03, N-ECR-02) or its own RFP number (the life
  nodes).
- **Gate links.** A node links the gates whose criterion fails directly when its threshold is not met
  (`hard_gates[].links_when`). The test checks that each linked gate's vocabulary appears in the node's quantity or
  threshold. A temperature limit links `firing_life`, not `bus_power` or `mass`. The power and mass of any mitigation
  are booked in N-PWR-01 and N-MAS-01. A start-count threshold links `restart_sustainment` only (N-CAT-07, N-CAT-09).
  A Xe budget (Xe consumed against Xe loaded: N-CAT-02, N-IGN-01) links `mission_life`, because the hard-gate matrix's
  G5 names xenon consumable depletion, and `air_xe` for the Xe role. It does not link `mass`: the mass of the loaded Xe
  is compared once, in N-MAS-01.
- **Delivered feed.** A node whose quantity or threshold is evaluated on the delivered feed needs that feed from
  A-FLOWENV. This covers the state, composition, pressure or flow envelope at IF-A5, including the atmospheric end state
  of a transition. A-FLOWENV is then required, or it decides the node. A node evaluated at a design setpoint takes the
  setpoint as a design input; the thermal nodes are an example.
- **Cheapest resolution.** `cheapest_resolution` is the minimum over three kinds of candidate: the node's unblocked
  single deciding actions, the set itself, and its `alternative_resolutions`. The key is, in order, the highest cost
  class in the set, the number of actions, and the sorted action ids. Every contributing action belongs to one listed
  set. This settles equal-cost ties mechanically. For example, N-IGN-02 takes A-FLOWENV + M-IGN over
  A-FLOWENV + M-RFSRC, and N-IGN-03 takes A-FLOWENV + M-ECRSRC over A-FLOWENV + M-IGN, both on the id order.
- **Thermal nodes.** A ground thermal-vacuum balance test (M-THERMAL) predicts flight temperatures only through the
  correlated thermal network (A-THERMAL). A chamber does not reproduce the orbital thermal environment, for example
  free-molecular aeroheating, Earth albedo and infrared, and eclipse cycling. So both actions contribute to every
  thermal node, and neither decides it alone.
- **Unvalidated models inform.** The interstage transport model (A-INTERSTAGE) informs every node it touches. On
  N-ECR-01 the required ion flux comes from the common-condition test (M-PREION), and the achieved density comes from
  the standalone source test (M-ECRSRC).

## Evidence-status rule (deterministic; the test enforces it)
- **supported** means at least one `supports` item and no `contradicts` item.
- **contradicted** means at least one `contradicts` item and no `supports` item.
- **unknown** covers everything else: no evidence, context only, or conflicting evidence. A node with nothing decisive
  must state an `evidence_gap`.

A `contradicted` status is only as broad as the evidence behind it. For example, N-PWR-01 and its sub-cause N-UTL-01 are
contradicted by laboratory N₂ operating points (S-CIFALI2011: 305 V, 3.48 A at 41.6 W/mN, i.e. about 25.5 mN,
D-CIFALI-THRUST-N2; S-MARCHIONI2020: 17–22 mN at 500–800 W). These were taken in ground facilities with a noble-gas
cathode and controller-set flow. They do not show that a Vyovrinda design meets the gate. A source is never `supports`
on one node and `contradicts` on another node that makes the same comparison; the test enforces this.

A failure path stated as a disjunction is contradicted only by evidence that covers every leg. N-RF-02, for example, is
a mismatch at ignition, at the Xe <-> air change or across the flow envelope. An item that covers only some legs is
`context`. S-RABUNAL2024 shows matched operation over an air flow range, but neither ignition nor a gas change, so it is
context on N-RF-02.

## Ranking rule for "what evidence to acquire next" (stated in the JSON as `decisiveness_lexicographic_v2`)
For each architecture, and only over its counted open nodes and unblocked actions, actions are sorted by these keys in
order:
1. The number of nodes the action **decides**.
2. The number of distinct hard gates linked by those decided nodes.
3. The number of nodes it **contributes** to (needed jointly with other actions).
4. The number of nodes it **informs**.
5. The cost class, cheapest first: literature < analysis < measurement.
6. The action id.

No weights, probabilities or expert scores are used. A blocked action is listed but not ranked. Today the only blocked
action is `A-HALLMAP`, which is blocked by the empty credible set and the incomplete O4 dispositions. Sub-cause nodes
(`sub_cause_of`) are not counted.

The rule is applied separately to two kinds of node set (`branch_rule`):
- the **core** set: the nodes that apply whatever design branches are chosen. The core ranking never counts a
  branch-specific node.
- each **design-branch option**'s own set, ranked in `branch_rankings`. Options of one decision are alternatives, so
  their nodes are not added to each other or to the core.

Version 1 counted conditional nodes (N-CAT-04, N-RF-03) in the core ranking, while the Xe-fed cathode nodes were not
marked conditional, and one cathode test was credited with both cathode options. Version 2 removes both inflations.

`cheapest_resolution` is either a single `decides` action or a jointly sufficient set of `contributes` actions. Its
cost class is never above that of the cheapest `decides` action.

**How to read the ranking.** The ranking counts labels and nothing else. Few nodes have a single deciding action:

- Most failure paths compare a measurement with another lane's analysis. Examples are bus power (A-ELEC), break-even
  and interstage transmission (A-BREAKEVEN), and life extrapolation (A-THERMAL).
- Every node evaluated on the delivered feed also needs that feed (A-FLOWENV).
- The thermal balance test needs the correlated thermal network.

So the core lists are ordered mainly by key 1 among a few deciders, then by the contributes count:

- `hall_only`: A-FLOWENV ranks first. It decides the feed-system start transient (N-CTL-03) and contributes to 7 of the
  11 counted nodes. A-MASS is second: it decides the mass total.
- `rf_hall`: A-FLOWENV, then M-PREION, then A-MASS. M-PREION decides the RF-interference node N-RF-04 and contributes to
  5 nodes.
- `ecr_hall`: A-BFIELD ranks first. It is the only deciding action for the ECR–Hall field interaction (2 gates) and
  has no lane. A-FLOWENV and A-MASS follow.

In each cathode-branch list, the option's own cathode test ranks first: M-CATHXE on the Xe-fed branch, M-CATHAIR on the
air-fed branch. A-BFIELD ranks first on the magnetized-helicon branch. The measurement actions have no executing lane
yet (`hardware_test`).

The order depends on the labels. With the v1.3.0 labels, M-THERMAL decided the thermal nodes alone and ranked first in
all three core lists. It now contributes, together with A-THERMAL (see *Node rules*). The ranking orders evidence
within one architecture's tree (core, or one branch option). It says nothing about which architecture, or which
cathode option, is better.

## Per-architecture trees (generated)
<!-- BEGIN GENERATED:trees -->
### `hall_only` (23 nodes, 3 sub-cause(s), 9 branch-specific: 7 supported, 2 contradicted, 14 unknown; all decision_state = open)

| class | node | failure path | evidence status | gates (matrix id) | cheapest resolution | resolve by | analysis needs admitted Hall closure |
|---|---|---|---|---|---|---|---|
| ignition | N-IGN-01 | Hall-stage cold start on atmospheric anode flow fails; start needs Xe | unknown | restart_sustainment (G6), air_xe (G7), mission_life (G5) | A-FLOWENV + A-OPS + M-IGN | C | no |
| sustainment_extinction | N-SUS-01 | Hall stage extinguishes or runs unstably on N2/O2 within the needed window | unknown | restart_sustainment (G6), thrust (G1), air_xe (G7) | A-FLOWENV + M-SUSWIN | B | yes |
| sustainment_extinction | N-SUS-02 | Delivered-flow range over altitude and solar activity exceeds the sustainment range | unknown | restart_sustainment (G6), thrust (G1) | A-FLOWENV + M-SUSWIN | B | yes |
| utilization | N-UTL-01 | Low ion utilization of N2/O2 in the Hall stage prevents 12 mN within the bus power (sub-cause of N-PWR-01; not counted) | contradicted | bus_power (G2), thrust (G1) | A-ELEC + A-FLOWENV + M-PREION | B | yes |
| cathode_limit | N-CAT-01 | Emitter poisoning by oxygen from the feed, plume backflow or ram exposure (branch cathode_feed = xe_fed_thermionic) | supported | firing_life (G4), mission_life (G5), restart_sustainment (G6) | A-FLOWENV + A-OXEXPO + M-CATHXE | C | no |
| cathode_limit | N-CAT-02 | Cathode Xe consumption over the firing life exceeds the Xe loaded for the cathode (branch cathode_feed = xe_fed_thermionic) | supported | mission_life (G5), air_xe (G7) | A-MASS + M-CATHXE | C | yes |
| cathode_limit | N-CAT-03 | Cathode flow minimized for mass drives plume mode and energetic-ion erosion (branch cathode_feed = xe_fed_thermionic) | supported | firing_life (G4) | M-CATHXE | C | yes |
| cathode_limit | N-CAT-04 | Air-fed cathode route: electron current or coupling insufficient at the discharge current (branch cathode_feed = air_fed_plasma) | unknown | thrust (G1), restart_sustainment (G6) | M-CATHAIR | C | yes |
| cathode_limit | N-CAT-05 | Intrinsic cathode life: emitter evaporation at the required emission current ends insert life before the firing hours (branch cathode_feed = xe_fed_thermionic) | supported | firing_life (G4) | A-CATHODE + M-CATHXE | C | no |
| cathode_limit | N-CAT-06 | Xe-fed cathode current range does not cover the required emission current (branch cathode_feed = xe_fed_thermionic) | unknown | thrust (G1), restart_sustainment (G6) | A-CATHODE + M-CATHXE | C | no |
| cathode_limit | N-CAT-07 | Restart count exceeds the thermionic cathode's heater/ignition cycle capability (branch cathode_feed = xe_fed_thermionic) | unknown | restart_sustainment (G6) | A-OPS + M-CATHXE | C | no |
| cathode_limit | N-CAT-08 | Air-fed plasma cathode wears out before the firing hours (branch cathode_feed = air_fed_plasma) | supported | firing_life (G4) | A-THERMAL + M-CATHAIR | C | no |
| cathode_limit | N-CAT-09 | Restart count exceeds the air-fed plasma cathode's ignition cycle capability (branch cathode_feed = air_fed_plasma) | unknown | restart_sustainment (G6) | A-OPS + M-CATHAIR | C | no |
| thermal_limit | N-THM-01 | Hall magnetic circuit (coils or permanent magnets) exceeds its temperature limit | unknown | firing_life (G4) | A-THERMAL + M-THERMAL | C | yes |
| thermal_limit | N-THM-04 | Hall channel wall or anode exceeds its temperature limit | unknown | firing_life (G4) | A-THERMAL + M-THERMAL | C | yes |
| erosion_wall_life | N-ERO-01 | Channel-wall erosion (physical and chemical) by N/O species limits firing life | supported | firing_life (G4) | A-FLOWENV + A-THERMAL + M-EROSION | C | yes |
| erosion_wall_life | N-ERO-02 | Anode oxidation raises electrical resistance | supported | firing_life (G4) | A-FLOWENV + A-THERMAL + M-EROSION | C | no |
| power_limit | N-PWR-01 | Hall-stage discharge power per unit thrust on air leaves no room in the 1.5 kW bus | contradicted | bus_power (G2), thrust (G1) | A-ELEC + A-FLOWENV + M-PREION | B | yes |
| power_limit | N-PWR-04 | Non-thruster loads consume the bus margin (sub-cause of N-PWR-01; not counted) | unknown | bus_power (G2), thrust (G1) | A-ELEC + A-FLOWENV + M-PREION | B | no |
| mass_limit | N-MAS-01 | Total propulsion-system mass exceeds 40 kg | unknown | mass (G3) | A-MASS | C | no |
| control_startup | N-CTL-01 | Xe -> mixed -> atmosphere transition loses the discharge or exceeds the supply transient limits | unknown | restart_sustainment (G6), air_xe (G7) | A-FLOWENV + M-TRANS | C | no |
| control_startup | N-CTL-02 | Restart count exceeds the demonstrated Hall-stage starts or the Xe start budget (sub-cause of N-IGN-01; not counted) | unknown | restart_sustainment (G6), air_xe (G7), mission_life (G5) | A-FLOWENV + A-OPS + M-IGN | C | no |
| control_startup | N-CTL-03 | Feed-system start transient too slow or overshoots after start or eclipse | unknown | restart_sustainment (G6) | A-FLOWENV | C | no |

### `rf_hall` (36 nodes, 5 sub-cause(s), 10 branch-specific: 9 supported, 2 contradicted, 25 unknown; all decision_state = open)

| class | node | failure path | evidence status | gates (matrix id) | cheapest resolution | resolve by | analysis needs admitted Hall closure |
|---|---|---|---|---|---|---|---|
| ignition | N-IGN-01 | Hall-stage cold start on atmospheric anode flow fails; start needs Xe | unknown | restart_sustainment (G6), air_xe (G7), mission_life (G5) | A-FLOWENV + A-OPS + M-IGN | C | no |
| ignition | N-IGN-02 | RF pre-ionizer does not break down on N2/O2 at the delivered pressure | supported | restart_sustainment (G6), air_xe (G7) | A-FLOWENV + M-IGN | C | no |
| ignition | N-IGN-04 | Pre-ionizer seed plasma does not lower the Hall-stage start requirement | unknown | restart_sustainment (G6) | A-FLOWENV + M-IGN | C | no |
| sustainment_extinction | N-SUS-01 | Hall stage extinguishes or runs unstably on N2/O2 within the needed window | unknown | restart_sustainment (G6), thrust (G1), air_xe (G7) | A-FLOWENV + M-SUSWIN | B | yes |
| sustainment_extinction | N-SUS-02 | Delivered-flow range over altitude and solar activity exceeds the sustainment range | unknown | restart_sustainment (G6), thrust (G1) | A-FLOWENV + M-SUSWIN | B | yes |
| sustainment_extinction | N-SUS-03 | Two-stage coupling: excess acceleration-stage current or unstable interaction limits the Hall stage | unknown | thrust (G1), restart_sustainment (G6) | A-FLOWENV + M-PREION | B | yes |
| utilization | N-UTL-01 | Low ion utilization of N2/O2 in the Hall stage prevents 12 mN within the bus power (sub-cause of N-PWR-01; not counted) | contradicted | bus_power (G2), thrust (G1) | A-ELEC + A-FLOWENV + M-PREION | B | yes |
| utilization | N-UTL-02 | RF pre-ionization gains less utilization than its power costs (thrust-to-power falls) | unknown | thrust (G1), bus_power (G2) | A-BREAKEVEN + A-ELEC + M-PREION | B | yes |
| cathode_limit | N-CAT-01 | Emitter poisoning by oxygen from the feed, plume backflow or ram exposure (branch cathode_feed = xe_fed_thermionic) | supported | firing_life (G4), mission_life (G5), restart_sustainment (G6) | A-FLOWENV + A-OXEXPO + M-CATHXE | C | no |
| cathode_limit | N-CAT-02 | Cathode Xe consumption over the firing life exceeds the Xe loaded for the cathode (branch cathode_feed = xe_fed_thermionic) | supported | mission_life (G5), air_xe (G7) | A-MASS + M-CATHXE | C | yes |
| cathode_limit | N-CAT-03 | Cathode flow minimized for mass drives plume mode and energetic-ion erosion (branch cathode_feed = xe_fed_thermionic) | supported | firing_life (G4) | M-CATHXE | C | yes |
| cathode_limit | N-CAT-04 | Air-fed cathode route: electron current or coupling insufficient at the discharge current (branch cathode_feed = air_fed_plasma) | unknown | thrust (G1), restart_sustainment (G6) | M-CATHAIR | C | yes |
| cathode_limit | N-CAT-05 | Intrinsic cathode life: emitter evaporation at the required emission current ends insert life before the firing hours (branch cathode_feed = xe_fed_thermionic) | supported | firing_life (G4) | A-CATHODE + M-CATHXE | C | no |
| cathode_limit | N-CAT-06 | Xe-fed cathode current range does not cover the required emission current (branch cathode_feed = xe_fed_thermionic) | unknown | thrust (G1), restart_sustainment (G6) | A-CATHODE + M-CATHXE | C | no |
| cathode_limit | N-CAT-07 | Restart count exceeds the thermionic cathode's heater/ignition cycle capability (branch cathode_feed = xe_fed_thermionic) | unknown | restart_sustainment (G6) | A-OPS + M-CATHXE | C | no |
| cathode_limit | N-CAT-08 | Air-fed plasma cathode wears out before the firing hours (branch cathode_feed = air_fed_plasma) | supported | firing_life (G4) | A-THERMAL + M-CATHAIR | C | no |
| cathode_limit | N-CAT-09 | Restart count exceeds the air-fed plasma cathode's ignition cycle capability (branch cathode_feed = air_fed_plasma) | unknown | restart_sustainment (G6) | A-OPS + M-CATHAIR | C | no |
| thermal_limit | N-THM-01 | Hall magnetic circuit (coils or permanent magnets) exceeds its temperature limit | unknown | firing_life (G4) | A-THERMAL + M-THERMAL | C | yes |
| thermal_limit | N-THM-02 | RF coil/antenna, matching network or discharge tube overheats | unknown | firing_life (G4) | A-THERMAL + M-THERMAL | C | no |
| thermal_limit | N-THM-04 | Hall channel wall or anode exceeds its temperature limit | unknown | firing_life (G4) | A-THERMAL + M-THERMAL | C | yes |
| erosion_wall_life | N-ERO-01 | Channel-wall erosion (physical and chemical) by N/O species limits firing life | supported | firing_life (G4) | A-FLOWENV + A-THERMAL + M-EROSION | C | yes |
| erosion_wall_life | N-ERO-02 | Anode oxidation raises electrical resistance | supported | firing_life (G4) | A-FLOWENV + A-THERMAL + M-EROSION | C | no |
| erosion_wall_life | N-ERO-03 | RF source window/tube erosion or conductive coating degrades coupling | unknown | firing_life (G4) | A-FLOWENV + A-THERMAL + M-EROSION | C | no |
| power_limit | N-PWR-01 | Hall-stage discharge power per unit thrust on air leaves no room in the 1.5 kW bus | contradicted | bus_power (G2), thrust (G1) | A-ELEC + A-FLOWENV + M-PREION | B | yes |
| power_limit | N-PWR-02 | RF source power plus generator loss pushes the bus above 1.5 kW at 12 mN (sub-cause of N-PWR-01; not counted) | unknown | bus_power (G2), thrust (G1) | A-ELEC + A-FLOWENV + M-PREION | B | yes |
| power_limit | N-PWR-04 | Non-thruster loads consume the bus margin (sub-cause of N-PWR-01; not counted) | unknown | bus_power (G2), thrust (G1) | A-ELEC + A-FLOWENV + M-PREION | B | no |
| mass_limit | N-MAS-01 | Total propulsion-system mass exceeds 40 kg | unknown | mass (G3) | A-MASS | C | no |
| mass_limit | N-MAS-02 | RF generator, matching network, coil and shielding push the total propulsion mass above 40 kg (sub-cause of N-MAS-01; not counted) | unknown | mass (G3) | A-MASS | C | no |
| control_startup | N-CTL-01 | Xe -> mixed -> atmosphere transition loses the discharge or exceeds the supply transient limits | unknown | restart_sustainment (G6), air_xe (G7) | A-FLOWENV + M-TRANS | C | no |
| control_startup | N-CTL-02 | Restart count exceeds the demonstrated Hall-stage starts or the Xe start budget (sub-cause of N-IGN-01; not counted) | unknown | restart_sustainment (G6), air_xe (G7), mission_life (G5) | A-FLOWENV + A-OPS + M-IGN | C | no |
| control_startup | N-CTL-03 | Feed-system start transient too slow or overshoots after start or eclipse | unknown | restart_sustainment (G6) | A-FLOWENV | C | no |
| interstage_loss | N-ISL-RF | Ions made in the RF stage are lost before the Hall acceleration zone | unknown | thrust (G1), bus_power (G2) | A-BREAKEVEN + M-PREION | B | yes |
| rf_source_specific | N-RF-01 | E-H (or helicon) mode transition with hysteresis drops the RF stage to a low-density mode | supported | restart_sustainment (G6), bus_power (G2), thrust (G1) | A-FLOWENV + M-RFSRC | B | no |
| rf_source_specific | N-RF-02 | Impedance mismatch (reflected power) across ignition, Xe <-> air change and flow envelope | unknown | bus_power (G2), restart_sustainment (G6) | A-ELEC + A-FLOWENV + M-RFSRC | C | no |
| rf_source_specific | N-RF-03 | Magnetized RF (helicon) source field interacts with the Hall magnetic circuit (branch rf_source_type = magnetized_helicon) | unknown | thrust (G1), restart_sustainment (G6) | A-BFIELD | B | no |
| rf_source_specific | N-RF-04 | RF interference coupling into the Hall discharge circuit, cathode or PPU sensing | unknown | restart_sustainment (G6) | M-PREION | C | no |

### `ecr_hall` (35 nodes, 5 sub-cause(s), 9 branch-specific: 9 supported, 2 contradicted, 24 unknown; all decision_state = open)

| class | node | failure path | evidence status | gates (matrix id) | cheapest resolution | resolve by | analysis needs admitted Hall closure |
|---|---|---|---|---|---|---|---|
| ignition | N-IGN-01 | Hall-stage cold start on atmospheric anode flow fails; start needs Xe | unknown | restart_sustainment (G6), air_xe (G7), mission_life (G5) | A-FLOWENV + A-OPS + M-IGN | C | no |
| ignition | N-IGN-03 | ECR pre-ionizer does not break down on air at the delivered pressure | unknown | restart_sustainment (G6), air_xe (G7) | A-FLOWENV + M-ECRSRC | C | no |
| ignition | N-IGN-04 | Pre-ionizer seed plasma does not lower the Hall-stage start requirement | unknown | restart_sustainment (G6) | A-FLOWENV + M-IGN | C | no |
| sustainment_extinction | N-SUS-01 | Hall stage extinguishes or runs unstably on N2/O2 within the needed window | unknown | restart_sustainment (G6), thrust (G1), air_xe (G7) | A-FLOWENV + M-SUSWIN | B | yes |
| sustainment_extinction | N-SUS-02 | Delivered-flow range over altitude and solar activity exceeds the sustainment range | unknown | restart_sustainment (G6), thrust (G1) | A-FLOWENV + M-SUSWIN | B | yes |
| sustainment_extinction | N-SUS-03 | Two-stage coupling: excess acceleration-stage current or unstable interaction limits the Hall stage | unknown | thrust (G1), restart_sustainment (G6) | A-FLOWENV + M-PREION | B | yes |
| utilization | N-UTL-01 | Low ion utilization of N2/O2 in the Hall stage prevents 12 mN within the bus power (sub-cause of N-PWR-01; not counted) | contradicted | bus_power (G2), thrust (G1) | A-ELEC + A-FLOWENV + M-PREION | B | yes |
| utilization | N-UTL-03 | ECR pre-ionization gains less utilization on air than its power costs | unknown | thrust (G1), bus_power (G2) | A-BREAKEVEN + A-ELEC + M-PREION | B | yes |
| cathode_limit | N-CAT-01 | Emitter poisoning by oxygen from the feed, plume backflow or ram exposure (branch cathode_feed = xe_fed_thermionic) | supported | firing_life (G4), mission_life (G5), restart_sustainment (G6) | A-FLOWENV + A-OXEXPO + M-CATHXE | C | no |
| cathode_limit | N-CAT-02 | Cathode Xe consumption over the firing life exceeds the Xe loaded for the cathode (branch cathode_feed = xe_fed_thermionic) | supported | mission_life (G5), air_xe (G7) | A-MASS + M-CATHXE | C | yes |
| cathode_limit | N-CAT-03 | Cathode flow minimized for mass drives plume mode and energetic-ion erosion (branch cathode_feed = xe_fed_thermionic) | supported | firing_life (G4) | M-CATHXE | C | yes |
| cathode_limit | N-CAT-04 | Air-fed cathode route: electron current or coupling insufficient at the discharge current (branch cathode_feed = air_fed_plasma) | unknown | thrust (G1), restart_sustainment (G6) | M-CATHAIR | C | yes |
| cathode_limit | N-CAT-05 | Intrinsic cathode life: emitter evaporation at the required emission current ends insert life before the firing hours (branch cathode_feed = xe_fed_thermionic) | supported | firing_life (G4) | A-CATHODE + M-CATHXE | C | no |
| cathode_limit | N-CAT-06 | Xe-fed cathode current range does not cover the required emission current (branch cathode_feed = xe_fed_thermionic) | unknown | thrust (G1), restart_sustainment (G6) | A-CATHODE + M-CATHXE | C | no |
| cathode_limit | N-CAT-07 | Restart count exceeds the thermionic cathode's heater/ignition cycle capability (branch cathode_feed = xe_fed_thermionic) | unknown | restart_sustainment (G6) | A-OPS + M-CATHXE | C | no |
| cathode_limit | N-CAT-08 | Air-fed plasma cathode wears out before the firing hours (branch cathode_feed = air_fed_plasma) | supported | firing_life (G4) | A-THERMAL + M-CATHAIR | C | no |
| cathode_limit | N-CAT-09 | Restart count exceeds the air-fed plasma cathode's ignition cycle capability (branch cathode_feed = air_fed_plasma) | unknown | restart_sustainment (G6) | A-OPS + M-CATHAIR | C | no |
| thermal_limit | N-THM-01 | Hall magnetic circuit (coils or permanent magnets) exceeds its temperature limit | unknown | firing_life (G4) | A-THERMAL + M-THERMAL | C | yes |
| thermal_limit | N-THM-03 | ECR magnets lose remanence or the resonator/coupler overheats | supported | firing_life (G4) | A-THERMAL + M-THERMAL | C | no |
| thermal_limit | N-THM-04 | Hall channel wall or anode exceeds its temperature limit | unknown | firing_life (G4) | A-THERMAL + M-THERMAL | C | yes |
| erosion_wall_life | N-ERO-01 | Channel-wall erosion (physical and chemical) by N/O species limits firing life | supported | firing_life (G4) | A-FLOWENV + A-THERMAL + M-EROSION | C | yes |
| erosion_wall_life | N-ERO-02 | Anode oxidation raises electrical resistance | supported | firing_life (G4) | A-FLOWENV + A-THERMAL + M-EROSION | C | no |
| erosion_wall_life | N-ERO-04 | ECR antenna/window erosion or coating in air plasma | supported | firing_life (G4) | A-FLOWENV + A-THERMAL + M-EROSION | C | no |
| power_limit | N-PWR-01 | Hall-stage discharge power per unit thrust on air leaves no room in the 1.5 kW bus | contradicted | bus_power (G2), thrust (G1) | A-ELEC + A-FLOWENV + M-PREION | B | yes |
| power_limit | N-PWR-03 | Microwave source power plus conversion loss (and electromagnet power) pushes the bus above 1.5 kW at 12 mN (sub-cause of N-PWR-01; not counted) | unknown | bus_power (G2), thrust (G1) | A-ELEC + A-FLOWENV + M-PREION | B | yes |
| power_limit | N-PWR-04 | Non-thruster loads consume the bus margin (sub-cause of N-PWR-01; not counted) | unknown | bus_power (G2), thrust (G1) | A-ELEC + A-FLOWENV + M-PREION | B | no |
| mass_limit | N-MAS-01 | Total propulsion-system mass exceeds 40 kg | unknown | mass (G3) | A-MASS | C | no |
| mass_limit | N-MAS-03 | Microwave generator, waveguide/coupler and ECR magnets push the total propulsion mass above 40 kg (sub-cause of N-MAS-01; not counted) | unknown | mass (G3) | A-MASS | C | no |
| control_startup | N-CTL-01 | Xe -> mixed -> atmosphere transition loses the discharge or exceeds the supply transient limits | unknown | restart_sustainment (G6), air_xe (G7) | A-FLOWENV + M-TRANS | C | no |
| control_startup | N-CTL-02 | Restart count exceeds the demonstrated Hall-stage starts or the Xe start budget (sub-cause of N-IGN-01; not counted) | unknown | restart_sustainment (G6), air_xe (G7), mission_life (G5) | A-FLOWENV + A-OPS + M-IGN | C | no |
| control_startup | N-CTL-03 | Feed-system start transient too slow or overshoots after start or eclipse | unknown | restart_sustainment (G6) | A-FLOWENV | C | no |
| interstage_loss | N-ISL-ECR | Ions made in the ECR stage are trapped or lost before the Hall acceleration zone | unknown | thrust (G1), bus_power (G2) | A-BREAKEVEN + M-PREION | B | yes |
| ecr_source_specific | N-ECR-01 | Cutoff (overdense) limit: ECR-stage density saturates below the Hall-stage feed need | unknown | thrust (G1) | M-ECRSRC + M-PREION | B | yes |
| ecr_source_specific | N-ECR-02 | ECR resonance field interacts with the Hall magnetic circuit | unknown | thrust (G1), restart_sustainment (G6) | A-BFIELD | B | no |
| ecr_source_specific | N-ECR-03 | Microwave power chain (generator, transmission, coupler) efficiency or life insufficient | unknown | bus_power (G2), firing_life (G4), mission_life (G5) | A-ELEC + M-MWCHAIN | C | no |
<!-- END GENERATED:trees -->

## What evidence to acquire next, per architecture (generated)
<!-- BEGIN GENERATED:ranking -->
### `hall_only` core (11 open nodes counted; 3 sub-cause(s) and 9 branch-specific node(s) not counted)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | A-FLOWENV (Delivered-feed envelope and start transient (upstream only)) | analysis | 1 | 1 (restart_sustainment) | 7 | 0 |
| 2 | A-MASS (Mass ledger) | analysis | 1 | 1 (mass) | 0 | 0 |
| 3 | A-THERMAL (Thermal/life analysis) | analysis | 0 | 0 (-) | 4 | 0 |
| 4 | M-EROSION (Short erosion/oxidation test on air) | measurement | 0 | 0 (-) | 2 | 0 |
| 5 | M-SUSWIN (Sustainment-window map) | measurement | 0 | 0 (-) | 2 | 0 |
| 6 | M-THERMAL (Thermal balance test) | measurement | 0 | 0 (-) | 2 | 0 |
| 7 | A-ELEC (Electrical closure on the common bus boundary) | analysis | 0 | 0 (-) | 1 | 0 |
| 8 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 1 | 0 |
| 9 | M-IGN (Ignition and restart on the atmospheric feed) | measurement | 0 | 0 (-) | 1 | 0 |
| 10 | M-PREION (Common-condition pre-ionizer A/B/C test) | measurement | 0 | 0 (-) | 1 | 0 |
| 11 | M-TRANS (Xe -> mixed -> air transition) | measurement | 0 | 0 (-) | 1 | 0 |
| 12 | L-SITAEL (SITAEL / AETHER air-operation records) | literature | 0 | 0 (-) | 0 | 4 |
| 13 | L-WALL (Wall and anode erosion/oxidation with N and O) | literature | 0 | 0 (-) | 0 | 3 |
| 14 | L-THERMAL (Thermal limits of magnets and couplers) | literature | 0 | 0 (-) | 0 | 2 |
| blocked | A-HALLMAP (Design Hall maps from admitted closures) | not ranked | - | - | - | touches 3 |

#### `hall_only` branch `cathode_feed = xe_fed_thermionic` (6 open nodes counted; applies only if this option is chosen)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | M-CATHXE (Xe-fed thermionic cathode integration test) | measurement | 1 | 1 (firing_life) | 5 | 0 |
| 2 | A-CATHODE (Cathode integration analysis) | analysis | 0 | 0 (-) | 2 | 3 |
| 3 | A-FLOWENV (Delivered-feed envelope and start transient (upstream only)) | analysis | 0 | 0 (-) | 1 | 0 |
| 4 | A-MASS (Mass ledger) | analysis | 0 | 0 (-) | 1 | 0 |
| 5 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 1 | 0 |
| 6 | A-OXEXPO (Oxygen exposure at the cathode emitter) | analysis | 0 | 0 (-) | 1 | 0 |
| 7 | L-CATHODE (Cathode oxygen tolerance and plume-mode records) | literature | 0 | 0 (-) | 0 | 6 |

#### `hall_only` branch `cathode_feed = air_fed_plasma` (3 open nodes counted; applies only if this option is chosen)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | M-CATHAIR (Air-fed plasma cathode integration test) | measurement | 1 | 2 (thrust, restart_sustainment) | 2 | 0 |
| 2 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 1 | 0 |
| 3 | A-THERMAL (Thermal/life analysis) | analysis | 0 | 0 (-) | 1 | 0 |
| 4 | L-CATHODE (Cathode oxygen tolerance and plume-mode records) | literature | 0 | 0 (-) | 0 | 3 |

### `rf_hall` core (21 open nodes counted; 5 sub-cause(s) and 10 branch-specific node(s) not counted)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | A-FLOWENV (Delivered-feed envelope and start transient (upstream only)) | analysis | 1 | 1 (restart_sustainment) | 13 | 0 |
| 2 | M-PREION (Common-condition pre-ionizer A/B/C test) | measurement | 1 | 1 (restart_sustainment) | 5 | 0 |
| 3 | A-MASS (Mass ledger) | analysis | 1 | 1 (mass) | 0 | 0 |
| 4 | A-THERMAL (Thermal/life analysis) | analysis | 0 | 0 (-) | 6 | 0 |
| 5 | A-ELEC (Electrical closure on the common bus boundary) | analysis | 0 | 0 (-) | 3 | 1 |
| 6 | M-EROSION (Short erosion/oxidation test on air) | measurement | 0 | 0 (-) | 3 | 0 |
| 7 | M-IGN (Ignition and restart on the atmospheric feed) | measurement | 0 | 0 (-) | 3 | 0 |
| 8 | M-RFSRC (RF source standalone on N2/O2) | measurement | 0 | 0 (-) | 3 | 0 |
| 9 | M-THERMAL (Thermal balance test) | measurement | 0 | 0 (-) | 3 | 0 |
| 10 | A-BREAKEVEN (Break-even surfaces) | analysis | 0 | 0 (-) | 2 | 0 |
| 11 | M-SUSWIN (Sustainment-window map) | measurement | 0 | 0 (-) | 2 | 0 |
| 12 | M-TRANS (Xe -> mixed -> air transition) | measurement | 0 | 0 (-) | 1 | 1 |
| 13 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 1 | 0 |
| 14 | L-SITAEL (SITAEL / AETHER air-operation records) | literature | 0 | 0 (-) | 0 | 5 |
| 15 | L-WALL (Wall and anode erosion/oxidation with N and O) | literature | 0 | 0 (-) | 0 | 4 |
| 16 | L-HHT (Helicon-Hall two-stage records) | literature | 0 | 0 (-) | 0 | 3 |
| 17 | L-THERMAL (Thermal limits of magnets and couplers) | literature | 0 | 0 (-) | 0 | 3 |
| 18 | A-INTERSTAGE (Interstage transport model) | analysis | 0 | 0 (-) | 0 | 3 |
| 19 | L-RFMODE (RF mode transitions in N2/O2/air) | literature | 0 | 0 (-) | 0 | 2 |
| 20 | L-ECRHALL (ECR-stage and ECR-ABEP records) | literature | 0 | 0 (-) | 0 | 1 |
| blocked | A-HALLMAP (Design Hall maps from admitted closures) | not ranked | - | - | - | touches 3 |

#### `rf_hall` branch `cathode_feed = xe_fed_thermionic` (6 open nodes counted; applies only if this option is chosen)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | M-CATHXE (Xe-fed thermionic cathode integration test) | measurement | 1 | 1 (firing_life) | 5 | 0 |
| 2 | A-CATHODE (Cathode integration analysis) | analysis | 0 | 0 (-) | 2 | 3 |
| 3 | A-FLOWENV (Delivered-feed envelope and start transient (upstream only)) | analysis | 0 | 0 (-) | 1 | 0 |
| 4 | A-MASS (Mass ledger) | analysis | 0 | 0 (-) | 1 | 0 |
| 5 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 1 | 0 |
| 6 | A-OXEXPO (Oxygen exposure at the cathode emitter) | analysis | 0 | 0 (-) | 1 | 0 |
| 7 | L-CATHODE (Cathode oxygen tolerance and plume-mode records) | literature | 0 | 0 (-) | 0 | 6 |

#### `rf_hall` branch `cathode_feed = air_fed_plasma` (3 open nodes counted; applies only if this option is chosen)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | M-CATHAIR (Air-fed plasma cathode integration test) | measurement | 1 | 2 (thrust, restart_sustainment) | 2 | 0 |
| 2 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 1 | 0 |
| 3 | A-THERMAL (Thermal/life analysis) | analysis | 0 | 0 (-) | 1 | 0 |
| 4 | L-CATHODE (Cathode oxygen tolerance and plume-mode records) | literature | 0 | 0 (-) | 0 | 3 |

#### `rf_hall` branch `rf_source_type = magnetized_helicon` (1 open nodes counted; applies only if this option is chosen)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | A-BFIELD (Magnetic-field superposition) | analysis | 1 | 2 (thrust, restart_sustainment) | 0 | 0 |
| 2 | L-HHT (Helicon-Hall two-stage records) | literature | 0 | 0 (-) | 0 | 1 |
| 3 | M-PREION (Common-condition pre-ionizer A/B/C test) | measurement | 0 | 0 (-) | 0 | 1 |

#### `rf_hall` branch `rf_source_type = unmagnetized` (0 open nodes counted; applies only if this option is chosen)

No node is specific to this option.

### `ecr_hall` core (21 open nodes counted; 5 sub-cause(s) and 9 branch-specific node(s) not counted)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | A-BFIELD (Magnetic-field superposition) | analysis | 1 | 2 (thrust, restart_sustainment) | 0 | 1 |
| 2 | A-FLOWENV (Delivered-feed envelope and start transient (upstream only)) | analysis | 1 | 1 (restart_sustainment) | 11 | 0 |
| 3 | A-MASS (Mass ledger) | analysis | 1 | 1 (mass) | 0 | 0 |
| 4 | A-THERMAL (Thermal/life analysis) | analysis | 0 | 0 (-) | 6 | 1 |
| 5 | M-PREION (Common-condition pre-ionizer A/B/C test) | measurement | 0 | 0 (-) | 6 | 0 |
| 6 | A-ELEC (Electrical closure on the common bus boundary) | analysis | 0 | 0 (-) | 3 | 0 |
| 7 | M-EROSION (Short erosion/oxidation test on air) | measurement | 0 | 0 (-) | 3 | 0 |
| 8 | M-IGN (Ignition and restart on the atmospheric feed) | measurement | 0 | 0 (-) | 3 | 0 |
| 9 | M-THERMAL (Thermal balance test) | measurement | 0 | 0 (-) | 3 | 0 |
| 10 | M-ECRSRC (ECR source standalone on air) | measurement | 0 | 0 (-) | 2 | 1 |
| 11 | A-BREAKEVEN (Break-even surfaces) | analysis | 0 | 0 (-) | 2 | 0 |
| 12 | M-SUSWIN (Sustainment-window map) | measurement | 0 | 0 (-) | 2 | 0 |
| 13 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 1 | 0 |
| 14 | M-MWCHAIN (Microwave power-chain efficiency and life test) | measurement | 0 | 0 (-) | 1 | 0 |
| 15 | M-TRANS (Xe -> mixed -> air transition) | measurement | 0 | 0 (-) | 1 | 0 |
| 16 | L-ECRHALL (ECR-stage and ECR-ABEP records) | literature | 0 | 0 (-) | 0 | 9 |
| 17 | L-SITAEL (SITAEL / AETHER air-operation records) | literature | 0 | 0 (-) | 0 | 5 |
| 18 | A-INTERSTAGE (Interstage transport model) | analysis | 0 | 0 (-) | 0 | 4 |
| 19 | L-THERMAL (Thermal limits of magnets and couplers) | literature | 0 | 0 (-) | 0 | 3 |
| 20 | L-WALL (Wall and anode erosion/oxidation with N and O) | literature | 0 | 0 (-) | 0 | 3 |
| 21 | L-HHT (Helicon-Hall two-stage records) | literature | 0 | 0 (-) | 0 | 1 |
| blocked | A-HALLMAP (Design Hall maps from admitted closures) | not ranked | - | - | - | touches 3 |

#### `ecr_hall` branch `cathode_feed = xe_fed_thermionic` (6 open nodes counted; applies only if this option is chosen)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | M-CATHXE (Xe-fed thermionic cathode integration test) | measurement | 1 | 1 (firing_life) | 5 | 0 |
| 2 | A-CATHODE (Cathode integration analysis) | analysis | 0 | 0 (-) | 2 | 3 |
| 3 | A-FLOWENV (Delivered-feed envelope and start transient (upstream only)) | analysis | 0 | 0 (-) | 1 | 0 |
| 4 | A-MASS (Mass ledger) | analysis | 0 | 0 (-) | 1 | 0 |
| 5 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 1 | 0 |
| 6 | A-OXEXPO (Oxygen exposure at the cathode emitter) | analysis | 0 | 0 (-) | 1 | 0 |
| 7 | L-CATHODE (Cathode oxygen tolerance and plume-mode records) | literature | 0 | 0 (-) | 0 | 6 |

#### `ecr_hall` branch `cathode_feed = air_fed_plasma` (3 open nodes counted; applies only if this option is chosen)

| rank | action | kind | decides | gates decided | contributes | informs |
|---|---|---|---|---|---|---|
| 1 | M-CATHAIR (Air-fed plasma cathode integration test) | measurement | 1 | 2 (thrust, restart_sustainment) | 2 | 0 |
| 2 | A-OPS (Restart count from the operations concept) | analysis | 0 | 0 (-) | 1 | 0 |
| 3 | A-THERMAL (Thermal/life analysis) | analysis | 0 | 0 (-) | 1 | 0 |
| 4 | L-CATHODE (Cathode oxygen tolerance and plume-mode records) | literature | 0 | 0 (-) | 0 | 3 |
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
| D-ECR-B-PER-100MHZ | ECR resonance field per 100 MHz of source frequency |B| = 2 pi f m_e / e | 0.00357239 | T | - |
| D-RATIO-BECR-P5N2 | Ratio of the 2.45 GHz ECR resonance field to the P5 peak radial field | 6.733 | 1 | - |
| D-RATIO-BECR-P5XE | Ratio of the 2.45 GHz ECR resonance field to the P5 peak radial field | 5.386 | 1 | - |
| D-XE-PER-0.1MGPS-15000H | Xe mass consumed per 0.1 mg/s of cathode flow over the RFP firing hours | 5.4 | kg | - |
| D-XE-DIAMANT-CHECK | Xe mass for 0.5 sccm continuous cathode flow over 5 years (reproduces the source's estimate) | 7.70262 | kg | 8.0 (S-DIAMANT2009 Sec. V pdf p. 4: 'about 8 kg'); rel. diff -0.03717 |
| D-CIFALI-THRUST-N2 | Thrust implied by the S-CIFALI2011 pure-N2 operating point, V_d I_d / (W/mN) | 25.5144 | mN | - |
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
  marked `abstract_only` or `identified_not_read`, and it is never cited as evidence in the latter case. An open
  repository copy is used only when it is the licensed version: S-TISAEV2024 was read from the CC BY version of record
  deposited in the Scuola Superiore Sant'Anna repository, located through OpenAlex.
- **Locators** give the section and the PDF page index of the downloaded file (`pdf p.`). They were checked by text
  search.
- **Hashes.** Some publisher PDFs are stamped at each download, so their bytes differ between downloads. IOP stamps
  S-TISAEV2023A with a download timestamp and a fresh trailer `/ID`. For such a source the recorded sha256 identifies
  the copy that was read. The source's `notes` say so, and the quoted text was re-found in a fresh download.
- **Gas of the cited result (unstated or different regime).** Every evidence item on an `air_specific` node declares
  the gas of its cited result. It carries either `gas_stated` or `gas_not_stated = true`
  (`evidence_status_rule.gas_rule`). The test checks the substance of each item, not only the applicability wording:
  - A `gas_not_stated` item is `context` there, whatever it reports.
  - A decisive item carries `gas_stated`, and that gas must appear in the item's own statement or applicability.
  - If the stated gas names no atmospheric species (for example xenon only), the item must also carry a
    `gas_independent_rationale`.
  - An applicability text that says the gas is not stated must carry the flag, on any node.

  A further test requires the `air_specific` flag on every node whose title, quantity or threshold names air, N₂/O₂,
  the atmospheric or delivered feed, N/O species, oxygen or oxidation. Consequences:
  - S-SIMMONDS2022 and S-MYERS2016 state no gas, so they are context on N-THM-01 and N-THM-04. N-THM-01 becomes
    `unknown`.
  - S-TURNER1999 and S-ROMANO2020's general statements state no gas: context on N-RF-01 and N-RF-02.
  - S-STASTNY2026 is context for N-IGN-03.
  - S-SHABSHELOWITZ2014 is context for N-UTL-02 and N-PWR-02, because the abstract does not state the two-stage gas.
  - The xenon items on the ECR cutoff node N-ECR-01 stay decisive only because the O-mode cutoff density depends on
    frequency alone, and each says so.
  - S-SHABSHELOWITZ2014's N-UTL-01 item names argon and nitrogen, but says only that utilization is low, not that
    12 mN is out of reach within the bus, so it is `context` there too (1.3.0).
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

## Changes in 1.2.0 (review round 2)
- **Unstated gas, applied consistently.** Nodes carry an explicit `air_specific` flag and evidence items a
  `gas_not_stated` flag (see Evidence discipline). S-SHABSHELOWITZ2014 became `context` on N-UTL-02 and N-PWR-02, so both
  moved supported → unknown, with the gap stated.
- **Weak or generic support relabelled `context`.** S-TISAEV2023A on N-UTL-03 (an electron-source current measurement,
  not a pre-ionizer utilization per watt) and S-ANDREUSSI2017 on N-SUS-02 (flow varies with conditions; no envelope
  against a sustainment range). N-UTL-03 and N-SUS-02 moved supported → unknown.
- **Jointly sufficient sets.** N-CAT-01 now needs A-OXEXPO (plume back-flow and attenuated ram exposure at the emitter;
  no lane) together with A-FLOWENV and M-CATHODE. N-ECR-03 needs M-MWCHAIN (microwave-chain efficiency and life test)
  with A-ELEC. A-THERMAL only informs it, because a thermal analysis gives temperature, not wear-out life.
- **Lanes that cannot deliver.** A-BFIELD moved from the interstage lane to the unassigned `magnetic_interaction` lane:
  the interstage draft takes the axial field as one input and computes no superposition, Hall B(z) deviation or
  resonance surface. All measurement actions moved to the unassigned `hardware_test` lane, with the specifying lanes in
  `specified_by`.
- **No double counting.** N-MAS-02/03 are sub-causes of N-MAS-01 and are not counted, so A-MASS decides one node in every
  architecture. N-SUS-03 no longer links `bus_power`, and the thermal nodes and N-CAT-03 link only `firing_life`,
  because their thresholds compare no power or mass.
- **Cathode life and current.** New nodes N-CAT-05 (intrinsic life: insert evaporation at the required emission
  current, independent of oxygen; supported by S-GOEBEL2017, IEPC-2017-276, read in full) and N-CAT-06 (the baseline
  Xe-fed cathode's current range against the required emission; unknown). They are resolved jointly by A-CATHODE (the
  cathode-integration analysis, new action) and M-CATHODE. S-GOEBEL2017's 1800-h run with 10 ppm O₂ in the Xe feed was
  added to N-CAT-01 as context.
- **Frequency-conditional ECR field.** N-ECR-02's physical cause now says that the resonance field exceeds Hall-channel
  fields only at GHz frequencies. A MHz-range source (S-STASTNY2026) needs a field of the order of, or below,
  Hall-channel fields (35.7 G per 100 MHz, derived D-ECR-B-PER-100MHZ).
- **Tests.** The schema validator now checks schema-valued `additionalProperties`. The threshold test now checks what
  its docstring says: RFP numbers appear only with an RFP label, and no other number with a unit appears in a
  threshold.

## Changes in 1.3.0 (review round 3)
- **Design branches, ranked separately.** The cathode feed and the RF source type are explicit `design_branches`.
  N-CAT-01/02/03/05/06 are now conditional on `xe_fed_thermionic`, as N-CAT-04 was on the air-fed option, and N-RF-03
  is conditional on `magnetized_helicon`. Branch-specific nodes leave the core ranking and are ranked per option
  (rule `decisiveness_lexicographic_v2`). With v1 counting, M-CATHODE ranked first in `hall_only` (2 decides, 4 gates).
  That rank depended on counting the Xe-fed and air-fed alternatives together.
- **Cathode test split.** M-CATHODE bundled the Xe-fed hollow-cathode test and the air-fed plasma-cathode alternative.
  It is now M-CATHXE and M-CATHAIR, each tied to its option.
- **Cathode branches completed.** The cathode start cycles moved out of N-CTL-02, which now covers only Hall-stage
  starts and start Xe (A-OPS + M-IGN). The new N-CAT-07 covers Xe-fed heater/ignition cycles. The new N-CAT-08 covers
  air-fed cathode wear life (M-CATHAIR + A-THERMAL extrapolation), and N-CAT-09 air-fed ignition cycles. All three
  are `unknown`, with their gaps stated. Their physical causes are hypotheses marked "verify".
- **N-UTL-01.** Its two `supports` items were relative-to-Xe or generic statements, so they are now `context`. It
  now carries the measured N₂ operating points that already contradicted N-PWR-01 (S-CIFALI2011, S-MARCHIONI2020), so
  its status moved supported → contradicted. It became a sub-cause of N-PWR-01, which removes the double count of one
  comparison for A-ELEC and M-PREION. New derived value D-CIFALI-THRUST-N2 = 305 V × 3.48 A / 41.6 W/mN ≈ 25.5 mN. It
  assumes that the W/mN figure is discharge power per thrust (verify against the source).
- **Out-of-regime support relabelled `context`.** S-FOSTER2006 on N-ISL-ECR is a xenon gridded-ion ECR design remark
  with no transfer into a Hall stage. S-ANDREUSSI2017 on N-SUS-03 has a DC first stage, not an RF or ECR one. Both
  nodes moved supported → unknown, with the gap stated.
- **N-THM-01.** The unsourced claim of a "higher fraction of power lost on molecular propellants" was removed. The
  physical cause now says that the propellant dependence is not shown by the cited items, and marks it "verify".
- **Tests.** New tests check that conditional nodes carry a declared branch, and that branch-specific actions touch
  only their option. They check that no core ranking row names a branch or sub-cause node, and that every branch
  combination covers every generic class and gate. A further test checks that a source never both supports and
  contradicts one comparison.

## Changes in 1.4.0 (review round 4)
- **One comparison counted once.** N-PWR-02, N-PWR-03 and N-PWR-04 state N-PWR-01's inequality, the discharge power
  for 12 mN within what the bus leaves after all other loads. So they are now sub-causes of N-PWR-01, like N-UTL-01.
  N-CTL-02 repeats N-IGN-01's comparison of start count and start Xe, so it is a sub-cause of N-IGN-01.
  - N-UTL-02 and N-UTL-03 no longer restate the RFP inequality. Their distinct comparison is the PROPOSED break-even
    against the hall_only arm (an open question for the owner).
  - N-ECR-03 compares the chain efficiency against the value booked in the ledger, not the ledger total.
  - New fields back this up: `comparison_id` on every node and a test on every architecture and branch choice.
    Counted nodes never share a comparison or a threshold text, and only N-PWR-01 states the bus inequality at 12 mN.
    The sub-cause test no longer hard-codes a node list.
- **Thermal nodes.** M-THERMAL no longer decides the thermal nodes. It is now specified at the air and Xe setpoints,
  including the peak-thrust setpoint. It predicts flight temperatures only through the correlated thermal network, so
  A-THERMAL and M-THERMAL both contribute to N-THM-01…04. M-THERMAL therefore no longer ranks first. See *How to read
  the ranking*.
- **Delivered feed, applied everywhere.** Every node evaluated on the delivered feed now requires A-FLOWENV. This adds
  A-FLOWENV to N-IGN-01, N-SUS-03, N-PWR-01 (and its sub-causes), N-RF-02, N-ERO-01…04 and N-CTL-01, and it is a test.
  M-TRANS no longer decides N-CTL-01 alone. N-CTL-01's title now matches its threshold: "exceeds the supply transient
  limits" replaces "leaves the operating window".
- **Gas of the cited result.** Every item on an air-specific node declares its gas, and the test checks the gas
  against the item's text.
  - S-SIMMONDS2022 and S-MYERS2016 state no gas, so they are context on both thermal nodes. N-THM-01 moved from
    supported to unknown, with the gap stated.
  - S-ROMANO2020's general impedance statement is context on N-RF-02. S-RABUNAL2024 covers one leg of that
    disjunction only, so it is context too, and N-RF-02 stays unknown.
  - S-TURNER1999 is context on N-RF-01, which stays supported through S-WANG2026 (N₂–O₂) and S-ZHANG2024 (N₂–Ar).
  - S-TISAEV2023A's general overdense statement is context on N-ECR-01. The xenon items there carry the frequency-only
    rationale.
- **S-MYERS2016 corrected.** The paraphrase now keeps the parenthetical "(primarily the magnet coils and the discharge
  channel)". "NASA-JPL xenon Hall thruster" was from memory: the NTRS abstract names NASA GRC with JPL and states
  neither the thruster nor the propellant (verify).
- **New evidence.** S-CIFALI2011 Sec. II.B (pdf p. 4) kept the pure-N₂ discharge power near 1 kW "avoiding thruster
  overheating for larger powers". It is context on N-THM-01 and N-THM-04, because it names no component.
  S-TISAEV2024 was read in full: the CC BY version of record in the Scuola Superiore Sant'Anna repository, found
  through OpenAlex.
  - It is `supports` on N-CAT-08 and N-ERO-04. An exposed antenna was sputtered by air species, and an oxide coating
    lowered the extracted current within about 1 h.
  - Its mitigated, water-cooled design ran two two-hour tests without coating. That is `context`: hours, not
    15,000 h.
  - It is `supports` on N-THM-03: a microwave connector overheated.
  - It is `context` on N-CAT-04.

  N-CAT-08 and N-ERO-04 moved from unknown to supported, each with a `status_note`.
- **Direction labels made consistent.** The S-TISAEV2023A and S-TISAEV2023B items on N-CAT-04 are magnitude or
  relative-to-Xe statements at an unknown required current, so both are `context`, as on N-UTL-01. N-CAT-05 gains a
  `status_note`: `supported` is not a life verdict, and its one quantitative item (above 50,000 h at 20–25 A) points
  the other way.
- **Gate links.** Start-count thresholds (N-CAT-07, N-CAT-09) link `restart_sustainment` only. N-CAT-05 and N-CAT-08
  link `firing_life`. The Xe budgets (N-CAT-02, N-IGN-01) link `mission_life` (consumable depletion) and `air_xe`, not
  `mass`. N-CAT-02, N-CAT-04 and N-CAT-06 no longer list `P2_cathode`, which covers cathode life and start cycles. A
  test checks each gate's vocabulary against the threshold text.
- **Physical causes.** Every node declares `physical_cause_basis`. The unsourced causes of N-RF-04, N-ECR-03, N-THM-02,
  N-ERO-03, N-IGN-03, N-IGN-04, N-ISL-RF, N-UTL-03 and N-CTL-03 are marked as hypotheses ("verify").
- **Cheapest resolution.** The tie-break is now stated and tested (*Node rules*), and `alternative_resolutions` lists
  the other jointly sufficient sets. A-INTERSTAGE informs N-ECR-01 as it does elsewhere. The required ion flux comes
  from M-PREION.
- **Citations.**
  - The L-SITAEL follow-up is AIAA 2019-3995 (Andreussi et al., 10.2514/6.2019-3995, new source S-ANDREUSSI2019,
    identified, not read). Crossref resolves 10.2514/6.2019-3996 to an iodine feeding-system paper.
  - S-BRABSTON2025 now has its title, "Hall Thruster Performance and Efficiency Analysis of a Molecular Propellant",
    41(6), 676–689.
  - S-GOEBEL2007 now has 2007, 23(3).
  - S-ROMANO2020 now has its journal DOI, 10.1016/j.actaastro.2020.07.008.

  All four were checked on Crossref.
- **Generated table.** The trees table shows each gate link with its hard-gate matrix number.

## Open questions for the owner
See `open_questions_for_owner` in the JSON. In short:
- Confirm the gate-id mapping to the hard-gate matrix, and decide whether `P1_thermal` / `P2_cathode` become binding.
- Set the restart count, the allowed Xe roles and the Xe allocation.
- Choose the cathode feed (`xe_fed_thermionic` / `air_fed_plasma`) and the `rf_hall` RF source type, or keep both
  open. A conditional selection must name the options it assumes.
- Accept or replace the PROPOSED thresholds and the PROPOSED elimination rule.
- Confirm the lane deliverable paths that were taken from other lanes' drafts.
- Assign lanes, or accept the gaps, for the operations analysis (A-OPS), the magnetic-field superposition (A-BFIELD),
  the cathode oxygen exposure (A-OXEXPO) and the execution of every measurement (`hardware_test`).
- Say whether subsystem mass allocations exist (they would turn N-MAS-02/03 into nodes of their own).
- Accept that microwave-chain life needs a test (M-MWCHAIN), or name a rated component.
- Adopt or reject the PROPOSED break-even criterion. If it is rejected, N-UTL-02/03 and N-ISL-RF/ECR become
  sub-causes of N-PWR-01 and leave the ranking.
- Confirm the Xe-budget gate mapping: `mission_life` for consumable depletion and `air_xe`; the loaded Xe mass is
  counted in N-MAS-01 only.
- Say whether a calendar-degradation node is needed for the Hall stage, pre-ionizer or air-fed cathode. Only N-CAT-01,
  N-ECR-03 and the Xe budgets compare a calendar-time quantity today.
- Confirm the thermal verification route (A-THERMAL correlated with M-THERMAL), or name a flight-environment test.

## Reproduce
```
python docs/architecture_comparison/failure_tree/derive_failure_tree.py          # regenerate
python docs/architecture_comparison/failure_tree/derive_failure_tree.py --check  # verify
python -m pytest -q tests/test_failure_tree.py
```
