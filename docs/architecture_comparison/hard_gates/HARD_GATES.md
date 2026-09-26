# Architecture hard gates, v1 (hall_only / rf_hall / ecr_hall)

**Status: DRAFT_PENDING_OWNER.** The thresholds are the RFP values as recorded in this repository. The RFP document itself
is not in the repository, so every gate says *verify against RFP document*. Interpretations, envelope states, coverage
lists, the evidence-sufficiency policy and the gates P1 and P2 are **PROPOSED** for the owner.

**Milestones supported:** A (conditional selection) fully today; B and C as the check that tells when they are reached.
**To reach the next milestone:** see [Milestones](#milestones-what-this-supports-and-what-the-next-one-needs).

## What this is, and what it is not
This is a set of hard pass/fail conditions, one per RFP requirement, that can **eliminate** a thrust architecture early
without subjective scoring. For each gate it states the metric, the threshold and its RFP source, the evidence that can
declare FAIL, the evidence that can declare PASS, and the decision milestone at which each verdict can be issued.

It is not a trade study. It ranks nothing, scores nothing and never declares a winner. With the current evidence every gate
is **UNDETERMINED** for all three architectures and nothing is eliminated.

The three architectures differ only in the pre-ionization method (none, RF, ECR). The downstream Hall accelerator, the
feed state, the cathode and the bus boundary are common. So a gate can eliminate one architecture only through evidence
about what differs: the pre-ionizer's own loads, mass, life and thermal state, or its effect on the discharge. A FAIL on
common evidence applies to all three.

## Files
| file | role |
|---|---|
| `docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json` | the matrix: gates, criteria, thresholds, RFP sources, evidence policy, open owner decisions |
| `schemas/architecture_comparison/hard_gates_v1.schema.json` | JSON Schema of the matrix, plus `$defs.evidence_item` / `evidence_bundle` (input) and `$defs.evaluation_result` / `evaluation_set` (output contract) |
| `abep_sim/hard_gates.py` | pure evaluator: `evaluate(architecture, evidence, admitted_members=())`, `evaluate_all(...)`; a built-in validator for the schema subset used (jsonschema is not a dependency) |
| `docs/architecture_comparison/hard_gates/evidence_register_v1.json` | the registered evidence (empty) |
| `docs/architecture_comparison/hard_gates/hard_gate_status_v1.json` | current status, generated: `python -m abep_sim.hard_gates status --out <that file>` |
| `tests/test_hard_gates.py` | tests (synthetic fixtures only) |

The module is not wired into `archengine`, so goldens do not move. It runs no simulation. Other lanes' contracts are
referenced by path and resolved only when asked (`resolve_contract`, `check_boundary_contract`), with a clear error if
missing: `abep_sim/arch_boundary.py` (bus_power_boundary_v1), `abep_sim/arch_compare.py`, `abep_sim/thermal_life.py`,
`docs/evidence/{rf_source,ecr_source,hall_sustainment,cathode,wall_life}/`,
`docs/architecture_comparison/experiment_protocol/`, `schemas/interfaces/`, `schemas/ledgers/`, `docs/hallmap/`.

## Verdict logic
- **UNDETERMINED** is the default. No evidence, insufficient evidence, incomplete coverage, a TBD threshold, or conflicting
  evidence all give UNDETERMINED. It is never read as PASS.
- **FAIL** needs verdict-bearing evidence on the failing side of the threshold. That means an upper bound below a floor, a
  lower bound above a ceiling, or an established false outcome. The evidence must be of **architecture scope** (it holds
  for every design of the architecture, with a written scope justification) and must cover the part of the envelope the
  criterion names in `fail_must_cover`. A failure shown for one point design is recorded as a design failure and never
  eliminates the architecture.
- **PASS** needs verdict-bearing evidence on the passing side over the **whole** envelope. It must hold for one design, or
  be of architecture scope. A gate passes only if every counted criterion passes for the same design.
- **ELIMINATED** means a binding gate (status RFP or OWNER_ADOPTED) is FAIL. PROPOSED gates and non-counting criteria
  (open interpretations, TBD thresholds) are evaluated and reported ("would eliminate if adopted") but never eliminate.
- **CONFLICT** means sufficient evidence exists on both sides. The verdict stays UNDETERMINED, nothing is eliminated, the
  conditional selection is withheld, and the owner resolves it.
- **Milestone tag:** each verdict carries the earliest milestone its evidence supports. A means the evidence is a hard
  bound or a hardware measurement. B means it needs a validated model or admitted-closure Hall maps.

## Gates
Generated from the matrix; the test checks that this table is current.

<!-- BEGIN GENERATED: python -m abep_sim.hard_gates render-table -->
| gate | gate status | criterion | counts | requirement | threshold status | FAIL may rest on | PASS may rest on | earliest FAIL / PASS |
|---|---|---|---|---|---|---|---|---|
| G1_thrust | RFP | G1.thrust_floor | yes | thrust_sustained_atmospheric_max_mN >= 12 mN | RFP_AS_RECORDED | A: hard bound, Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A: Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A / A (C: + integration) |
| G1_thrust | RFP | G1.thrust_ceiling | yes | thrust_min_stable_mN <= 25 mN | RFP_AS_RECORDED | A: hard bound, Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A: Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A / A (C: + integration) |
| G1_thrust | RFP | G1.peak_capability_25mN | no | thrust_peak_capability_mN >= 25 mN | RFP_AS_RECORDED | A: hard bound, Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A: Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A / A (C: + integration) |
| G2_bus_power | RFP | G2.bus_power_max | yes | bus_power_max_W < 1500 W | RFP_AS_RECORDED | A: hard bound, Vyovrinda hw, same hw; B: validated model (no Hall closure), admitted-closure Hall maps (every member) | A: Vyovrinda hw, same hw; B: validated model (no Hall closure), admitted-closure Hall maps (every member) | A / A (C: + integration) |
| G3_mass | RFP | G3.mass_mev | yes | mass_mev_kg < 40 kg | RFP_AS_RECORDED | A: hard bound, Vyovrinda hw, same hw; B: validated model (no Hall closure) | A: Vyovrinda hw, same hw; B: validated model (no Hall closure) | A / A (C: + integration) |
| G4_firing_life | RFP | G4.firing_life | yes | firing_life_h > 15000 h | RFP_AS_RECORDED | A: hard bound, Vyovrinda hw, same hw; B: validated model (no Hall closure), admitted-closure Hall maps (every member) | A: Vyovrinda hw, same hw; B: validated model (no Hall closure), admitted-closure Hall maps (every member) | A / A (C: + integration) |
| G5_mission | RFP | G5.mission_capability | yes | mission_capability_h >= 26000 h | RFP_AS_RECORDED | A: hard bound, Vyovrinda hw, same hw; B: validated model (no Hall closure), admitted-closure Hall maps (every member) | A: Vyovrinda hw, same hw; B: validated model (no Hall closure), admitted-closure Hall maps (every member) | A / A (C: + integration) |
| G6_ignition_sustainment | RFP | G6.sustainment | yes | sustained_discharge_atmospheric is true | NOT_APPLICABLE | A: hard bound, Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A: Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A / A (C: + integration) |
| G6_ignition_sustainment | RFP | G6.ignition | yes | ignition_from_off_atmospheric is true | NOT_APPLICABLE | A: hard bound, Vyovrinda hw, same hw | A: Vyovrinda hw, same hw | A / A (C: + integration) |
| G6_ignition_sustainment | RFP | G6.restart_count | no | ignition_cycles_capability >= TBD count | TBD | A: hard bound, Vyovrinda hw, same hw | A: Vyovrinda hw, same hw | A / A (C: + integration) |
| G7_air_xenon | RFP | G7.xenon_operation | yes | sustained_operation_xenon is true | NOT_APPLICABLE | A: hard bound, Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A: Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A / A (C: + integration) |
| G7_air_xenon | RFP | G7.feed_switching | no | feed_switchover_without_extinction is true | NOT_APPLICABLE | A: hard bound, Vyovrinda hw, same hw | A: Vyovrinda hw, same hw | A / A (C: + integration) |
| G7_air_xenon | RFP | G7.mixed_feed | no | sustained_operation_mixed_feed is true | NOT_APPLICABLE | A: hard bound, Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A: Vyovrinda hw, same hw; B: admitted-closure Hall maps (every member) | A / A (C: + integration) |
| P1_thermal | PROPOSED (non-binding) | P1.thermal_margin | yes | thermal_margin_min_K >= 0 K | PROPOSED | A: hard bound, Vyovrinda hw, same hw; B: validated model (no Hall closure), admitted-closure Hall maps (every member) | A: Vyovrinda hw, same hw; B: validated model (no Hall closure), admitted-closure Hall maps (every member) | A / A (C: + integration) |
| P2_cathode | PROPOSED (non-binding) | P2.cathode_life | yes | cathode_life_h > 15000 h | RFP_AS_RECORDED | A: hard bound, Vyovrinda hw, same hw; B: validated model (no Hall closure), admitted-closure Hall maps (every member) | A: Vyovrinda hw, same hw; B: validated model (no Hall closure), admitted-closure Hall maps (every member) | A / A (C: + integration) |
| P2_cathode | PROPOSED (non-binding) | P2.start_cycles | yes | cathode_start_cycles_capability >= TBD count | TBD | A: hard bound, Vyovrinda hw, same hw | A: Vyovrinda hw, same hw | A / A (C: + integration) |
<!-- END GENERATED -->

Each criterion in the matrix also carries its full definition, its interpretation, the envelope it must hold over, and the
text of the FAIL and PASS evidence it needs. Short form:

| gate | metric (what is compared) | envelope | notes |
|---|---|---|---|
| G1 thrust | steady thrust on the delivered atmospheric feed alone, within the G2 power limit (floor); minimum stable thrust (ceiling) | 180–230 km × atmosphere states low/mean/high | 25 mN peak with Xe is reported only (OD1) |
| G2 bus power | max over startup/steady/peak of the full bus_power_boundary_v1 ledger | 180–230 km × states × modes; every boundary component | a lower bound on a subset of loads is a valid FAIL bound |
| G3 mass | MEV = Σ CBE × (1 + MGA) including Xe load and tank | every in-scope mass item | closure-independent; Hall-closure evidence is rejected |
| G4 firing life | firing hours to loss of function, per element | every firing-limited element | any single element can FAIL the gate |
| G5 mission | calendar capability, per element | every calendar-limited element | not a drag-compensation requirement |
| G6 ignition / sustainment | steady sustainment on the delivered atmospheric composition; ignition from off | 180–230 km × states | pure N₂ never covers "atmospheric"; Hall maps are not accepted for ignition |
| G7 air + Xe | steady operation on the Xe feed within the power limit | Xe feed | switching and mixed feed reported only (OD6) |
| P1 thermal (PROPOSED) | allowable minus steady temperature, per element | steady/peak modes | 0 K margin PROPOSED; allowables TBD |
| P2 cathode (PROPOSED) | cathode firing life at this architecture's operating point; start cycles | atmospheric environment | start-cycle count TBD |

## Evidence that can decide a gate
The **basis** of an item says what kind of argument its number rests on. It sits next to the EVIDENCE.md quantity type and
evidence level, and the evaluator checks that the three are consistent.

| basis | verdict-bearing | earliest milestone | what it is |
|---|---|---|---|
| `hard_physical_bound` | yes | A | a closure-independent bound from conservation laws or first principles, computed by a committed deterministic script whose inputs are cited bounds or measurements (form of example: T ≤ √(2·ṁ_max·P_jet,max), from T = ∫v dm and P_jet = ½∫v² dm) |
| `measurement_vyovrinda` | yes | A | EVIDENCE.md level 1, stated as a bound including its uncertainty; a ground test must map its feed state to the envelope point (`conditions.feed_equivalence`, upstream ICD) |
| `measurement_same_hardware` | yes | A | level 2, e.g. a supplier's measured mass or power of the exact part |
| `model_closure_independent` | yes | B | a model with no Hall transport closure, declared validated for this use, run by a committed script |
| `model_admitted_closure` | yes | B | design Hall maps (Vyovrinda geometry and B(z)) of an **admitted** member at the pinned HallThruster.jl commit, with the required trust flags; it counts only as an envelope over **every** admitted member |
| `measurement_similar_hardware` | **no** | – | level 3 on different hardware; it can shape a condition or feed a hard bound, but it is never a verdict by itself |
| `model_unadmitted_closure` | **no** | – | screening candidates (`sgb-screen-*`) and any unadmitted closure: **never** a performance source |
| `engineering_estimate` | **no** | – | level 6, including life extrapolated with an unvalidated wear model |
| `assumption` | **no** | – | level 7 |

Point estimates without a stated bound are never verdict-bearing. A value computed from several inputs takes the basis
of its **weakest** input: a total that includes an admitted-closure load is `model_admitted_closure`, and anything touching
an unadmitted closure or an assumption is not verdict-bearing.

Trust flags for admitted-closure evidence follow the repository's definitions. `hall_map_trustworthy` and
`wall_life_trustworthy` (wall life, G4/G5) are the `HallMap` query flags. Extinction counts as FAIL-side evidence for
sustainment only if `numerically_valid` and `chemistry_trustworthy` hold (P5-N₂ run-status addendum 1). OUT_OF_DOMAIN
states are never evidence.

## Open readings are handled conservatively in both directions
Several requirements have more than one plausible reading (OD1–OD13 below). Until the owner decides:
- **Envelope quantifier (OD2).** PASS must hold at every point of 180–230 km × {low, mean, high}. FAIL must also be shown
  at every point. A failure only at 230 km / low solar activity is therefore UNDETERMINED, not FAIL.
- **Ignition start (OD5).** PASS needs an air-only start. FAIL must exclude both air-only and xenon-assisted starts.
- **"12–25 mN" (OD1).** The floor and the ceiling bind under both readings. The 25 mN peak capability with Xe is reported but
  not counted.
- **"air + Xe" (OD6).** Operation on each feed binds. Switching and mixed feed are reported but not counted.

So no verdict depends on an undecided reading.

## Rules this matrix enforces (errors, not warnings)
- P5 calibration nuisance (`p5_registration`, `p5_coil_shape`, `beam_efficiency_reading`,
  `facility_ingestion_interpretation`) anywhere in an evidence item raises an error. It is never a design variable, map axis
  or trade dimension.
- Hall-closure evidence on a closure-independent gate (G3 mass) raises an error. Hall-closure uncertainty must not leak
  into quantities that do not depend on the closure.
- A basis inconsistent with its `hall_closure.status`, a metric or unit that differs from the criterion's, an unknown
  gate or criterion, a duplicate id, a non-finite value or a missing provenance field (source, uncertainty, applicability
  domain, validation status, transformation chain) raises an error.
- Architecture ids are exactly `hall_only`, `rf_hall` and `ecr_hall`.

## RFP sources, and what is deliberately not a gate
The repository records the RFP only as summaries: CLAUDE.md ("What this is"), `abep_sim/constants.py` `RFPConstraints`
(docstring "Hard limits from Part III Para 2 of the RFP"), the opening constraint table of docs/HISTORY.md,
`abep_sim/transient.py`, `abep_sim/ppu.py`, and the RFP architecture blocks in the Hall-uncertainty scope rule. The matrix
quotes each one (R1–R7) and marks every gate *verify against RFP document*. The tests check that the thresholds equal
`abep_sim/constants.py`.

Recorded in the RFP summaries, but not elimination gates in v1 (owner decision OD12):
- indigenous content ≥ 75 % (programmatic; EVIDENCE.md has no evidence class for it);
- no single-point failure in electronics (its mass and power consequences are carried by G2 and G3);
- the AO-beam test recorded as RFP 4.1a (a test that supplies G5 evidence);
- "ionise nascent O" (carried by the definition of atmospheric propellant in G1 and G6).

Not gates:
- "Hall preferred" is a preference, and all three architectures share the Hall accelerator.
- Net drag compensation is "not stated" by the RFP (docs/HISTORY.md), and the spacecraft drag is not specified.
- The CLAUDE.md finding "RF/helicon pre-ionisers add nothing" is comparative. It can never eliminate rf_hall or ecr_hall
  here.
- Absolute Hall results of the withdrawn 0-D closure are never evidence.

## Open owner decisions
| id | topic | current handling |
|---|---|---|
| OD1 | reading of "12–25 mN": operating window vs 25 mN peak with Xe | floor and ceiling bind; peak reported only |
| OD2 | envelope quantifier: every point vs some altitude in the band | both verdicts need whole-envelope coverage |
| OD3 | atmosphere design states | PROPOSED low/mean/high = F10.7 70/150/230, ap 15 (frozen `atmosphere_msis21_v1` via `abep_sim/atmosphere.py`) |
| OD4 | 12 mN on atmospheric propellant alone vs with Xe | atmospheric alone (repository reading) |
| OD5 | ignition start sequence; restart count | PASS air-only, FAIL excludes both; count TBD |
| OD6 | meaning of "air + Xe" | each feed binds; switching and mixed reported only |
| OD7 | mass: strict "<" vs "≤"; 10 % margin vs item-class MGA | strict "<" on MEV with item-class MGA |
| OD8 | power limit in every mode vs steady only | every mode |
| OD9 | PROPOSED gates P1 thermal, P2 cathode: adopt or waive | reported, never eliminate |
| OD10 | PROPOSED element lists (mass, life, calendar, thermal) | used for PASS coverage |
| OD11 | evidence-sufficiency policy (bases, milestones, flags) | PROPOSED policy used |
| OD12 | recorded RFP items not gated | outside the matrix |
| OD13 | "> 15,000 h ignition" read as cumulative firing time | cumulative firing time |

The owner adopts a PROPOSED gate by setting its status to `OWNER_ADOPTED` (binding), and approves the matrix by setting its
status to `OWNER_APPROVED`, in a new matrix version.

## Current status (`hard_gate_status_v1.json`)
The evidence register is empty. No closure-independent hard bound has been computed by a committed script. The credible
Hall-transport set is empty (gate 3 FAIL), so no admitted-closure evidence exists. The repository holds no Vyovrinda
hardware data.

**All gates are UNDETERMINED for hall_only, rf_hall and ecr_hall, and nothing is eliminated.** Each architecture can
therefore be carried as a conditional (milestone A) candidate, but only subject to its nine conditions: every counted
binding criterion (G1.thrust_floor, G1.thrust_ceiling, G2.bus_power_max, G3.mass_mev, G4.firing_life,
G5.mission_capability, G6.sustainment, G6.ignition, G7.xenon_operation). This is not a selection.

While the credible set is empty, the only route to discharge the Hall-dependent conditions is a Vyovrinda or
same-hardware measurement, and G6.ignition needs a hardware demonstration in every case. The one route to an early
elimination that exists today is a committed hard-bound script. Any such bound needs an owner-fixed upper bound on the
deliverable mass flow (intake area), and that value is not recorded in the repository (TBD).

## Using it
```python
from abep_sim import hard_gates as hg
res = hg.evaluate("rf_hall", evidence_items, admitted_members=hg.admitted_member_ids())
res["gates"]["G1_thrust"]["verdict"]          # PASS / FAIL / UNDETERMINED (+ "milestone", "evidence_used")
res["eliminated"], res["elimination_basis"]   # binding gates only
res["milestones"]["A"]["conditions"]          # what a conditional selection would have to demonstrate
hg.evaluate_all(evidence_items)               # all three; lists eliminated / not_eliminated, ranks nothing
```
An evidence item (schema `$defs.evidence_item`) names the architectures it applies to, the gate, the criterion, and the
metric and unit. Its value is a lower bound, upper bound, interval, boolean or point estimate. It also carries its basis,
quantity type, evidence level, scope (architecture, with a justification, or point_design with a `design_id`), its
conditions (altitude interval, atmosphere states, modes, propellants, start sequences, elements, power boundary, feed
equivalence), its Hall-closure status, and the EVIDENCE.md provenance fields.

## Milestones: what this supports and what the next one needs
- **A — conditional selection (supported now).** It gives eliminations on sufficient evidence and, for each non-eliminated
  architecture, the conditions to demonstrate. **To reach B:** an admitted Hall transport closure (gate 3), Vyovrinda
  design Hall maps per admitted member (`docs/hallmap/`), validated common-boundary ledgers (bus_power_boundary_v1) or
  Vyovrinda hardware data that PASS every binding criterion, and owner approval of this matrix.
- **B — physics-backed selection.** `milestones.B.ready` when every binding gate passes and the matrix is approved.
  **To reach C:** one integrated design passing every binding gate, the owner's decision on P1/P2, and every TBD threshold
  and open reading resolved.
- **C — PDR freeze.** `milestones.C.ready` when the same design passes every binding gate and no owner item is open. After
  C comes hardware qualification, which is outside this matrix.
