# SIMULATION ARCHITECTURE OWNER DIRECTIVE (A9.23) — verbatim record, 2026-10-03

Recorded verbatim from the owner's message of 2026-10-03 (session chat). Companion:
`OD_2026_10_03_A9_23_simulation_architecture_owner_directive.json`. Immutable after commit.

---

We have already decided the simulation architecture principle. Please stop treating the RFP itself as a simulation dependency.

The simulator must NOT read, parse, interpret, or depend on the RFP/RVM during physics execution.

The correct structure is:

FROZEN ARCHITECTURE
+
FROZEN ENGINEERING CONSTRAINTS
+
FROZEN DESIGN-STATE / ENVIRONMENT SET
+
PHYSICS MODELS
        ↓
SIMULATION
        ↓
RAW PHYSICAL RESULTS
        ↓
ASSESSMENT / COMPLIANCE

The RFP is only the provenance/source for some frozen engineering constraints. Once those constraints are extracted, reviewed, approved and frozen, the physics simulator consumes the frozen values, not the RFP text or clause IDs.

For example:

RFP
  ↓
requirements extraction
  ↓
engineering_constraints_v1
  ↓
simulation

NOT:

RFP
  ↓
simulation

For our ABEP work, the simulation inputs should be treated as independent authoritative artefacts:

1. architecture_frozen_v1
   - rarefied intake
   - filter
   - active compressor
   - plenum/feed
   - Hall accelerator
   - RF/ICP electron source / neutralizer
   - ambient atmosphere primary
   - Xe contingency/emergency capability
   - no flight hollow cathode
   - C1 ground reference only, if retained

2. engineering_constraints_v1
   Examples:
   - altitude band
   - mass limit
   - power limit
   - thrust requirement/envelope
   - mission life = 26,280 h
   - ambient + Xe capability
   - other frozen numerical/operational limits

   These may carry provenance such as source requirement IDs, but the physics code must only consume the frozen values.

3. vleo_design_states_v2
   - the frozen 196 environmental/orbital states

4. physics_model_set_vN
   - atmosphere
   - intake
   - gas-surface interaction
   - compressor
   - gas path
   - chemistry
   - ionisation
   - Hall
   - ICP
   - neutralisation
   - drag
   - power
   - thermal
   - mass
   - lifetime

The physics layer should calculate raw quantities such as:

rho
composition
mdot
pressure
thrust
drag
Isp
efficiency
power
temperature
mass
erosion/life
T-D

It should NOT calculate or expose RFP compliance as part of the physical model.

Example:

physics output:
P_bus = 1.37 kW

assessment:
1.37 kW < frozen 1.5 kW limit
=> compliant

Similarly:

physics output:
T = 22.1 mN
D = 20.8 mN

assessment:
T - D = +1.3 mN
=> drag closure

So from now on:

- do not discuss “RFP simulation”
- do not introduce new RFP dependencies into physics/design code
- do not pass RFP objects or RVM objects into physics functions
- do not make physics decisions from clause IDs
- do not hard-code compliance labels inside raw physics outputs unless retained temporarily for backward compatibility in a wrapper layer

RFP/RVM belongs only in:
- requirements/provenance
- compliance mapping
- verification reporting
- bid/document traceability

The simulation itself belongs to:
- architecture
- constraints
- design states
- physics

Please continue the current separation lane with this principle as the governing rule.

For the 13 remaining allowlisted physics/design -> assessment calls:

1. move requirement/compliance logic outward into the runner/assessment layer;
2. preserve numerical physics exactly;
3. preserve merged/final outputs for compatibility where possible;
4. do not alter equations, coefficients, states, models, thresholds or golden values;
5. if any raw output schema must change, version the schema explicitly;
6. if any numerical result changes, STOP and report before merging.

Also create or identify the authoritative source-of-truth artefacts for:

- frozen architecture
- frozen engineering constraints
- frozen design-state set
- physics model/version set
- raw simulation result
- assessment/compliance result

Do not create duplicate sources of truth if equivalent authoritative files already exist.

The dependency rule we want enforced by tests is:

requirements/provenance
        ↓
frozen constraints

architecture + frozen constraints + design states + physics
        ↓
raw results

raw results + frozen constraints
        ↓
assessment/compliance

And importantly:

changing a requirement threshold must be able to change compliance WITHOUT changing raw physics.

changing a physics model may change raw physics WITHOUT changing the requirements snapshot.

changing the design-state set must not rewrite the architecture.

This is now the agreed simulation architecture. Proceed on that basis.
