# Architecture mass BOM v1: CBE / MGA / MEV for `hall_only`, `rf_hall`, `ecr_hall`

**Status:** skeleton, 2026-09-26. **Milestone support:** A (conditional selection). It does not rank architectures.
**Data:** [`mass_bom_v1.json`](mass_bom_v1.json), built by `python -m abep_sim.mass_bom build` and checked with
`python -m abep_sim.mass_bom check`. **Schema:** `schemas/architecture_comparison/mass_bom_v1.schema.json`.
**Code:** `abep_sim/mass_bom.py`, section "Architecture mass BOM skeleton v1" (pure; not wired into `archengine`).
**Tests:** `tests/test_mass_bom.py`.

## Result in one paragraph
All three architectures use one mass accounting: the same item list and margin policy, with common items defined
identically. **No item has a sourced CBE or a sourced lower bound yet.** There is no Vyovrinda design, no selected part
and no declared Xe load. So the strict roll-up is **refused** for every architecture and lists 16 (`hall_only`),
19 (`rf_hall`) or 20 (`ecr_hall`) missing items: every item, including the xe_residual and harness items, which are scaling relations on missing inputs. The plausibility screen returns **LOWER_BOUNDS_UNAVAILABLE** for all
three. The only valid lower bound today is the trivial 0 kg, so **no architecture can be excluded on mass**. This is a
statement of missing evidence. It is not a finding that any architecture fits within 40 kg.

## Milestones
| milestone | what this deliverable gives | needed to reach it |
|---|---|---|
| **A** conditional selection | one mass accounting for the three architectures; a lower-bound screen that feeds the hard-gate G3 FAIL side; refusal of roll-ups with TBD items | done (skeleton). A mass-based elimination at A needs sourced lower bounds (see "What would make the screen bite") |
| **B** physics-backed selection | — | CBEs for every item from closure-independent design models or supplier data (Vyovrinda intake, compressor, Hall head and magnetic circuit, cathode, PPU, pre-ionizer hardware); a declared Xe allocation; owner decisions OD-M1 to OD-M7 |
| **C** proposal/PDR freeze | — | PDR design masses (measured or supplier-measured where possible), harness and structure from the configuration and launch loads, thermal hardware from the integrated thermal design, and integrated mass, power, thermal, life and mission closure |

## Accounting rules
- **MEV = Σ_dry CBE × (1 + MGA) + system margin + propellant**
  - The system margin is a fraction × nominal dry mass, where nominal dry = Σ_dry CBE × (1 + MGA).
  - Propellant (Xe load and residuals) carries no MGA and no system margin (ESA R-M1-3).
  - `rollup()` requires the system-margin fraction explicitly. It has no default.
- **Refusal.** `rollup()` raises `ValueError` if any item is TBD, depends on a TBD item, or has a TBD maturity category.
  The message lists every such item. A partial roll-up happens only with `allow_partial=True`. It returns
  `complete=false`, `mev_kg=null`, the missing items with reasons, and known-items-only sums labelled "NOT an MEV".
- **Every value is sourced or TBD.** A `sourced_value` CBE needs a source, an evidence class (measured / digitized /
  inferred / reconstructed / model-derived / assumed), an uncertainty and an applicability statement. A scaling relation
  needs sourced inputs of the form {value, unit, source, evidence_class}. Anything missing raises an error; nothing
  falls back to a default.
- **Common items are identical** across architectures. Two conventions, both PROPOSED, keep the common definitions
  identical:
  - The RF generator and the microwave source are booked as architecture-specific items, not inside the common PPU.
  - Each pre-ionizer item includes its own mounting, harness and thermal-control increments.

  The harness allocation (5 % of nominal dry mass) is one definition. Its value differs by architecture because the
  nominal dry mass differs.
- **Hall closure.** Mass is closure-independent (hard-gate G3). The Hall head and magnetic circuit stay TBD until a
  Vyovrinda design exists. `check_item()` rejects:
  - any item that carries a Hall-closure marker (`hall_closure_id`, `ensemble_member_id`, `screening_candidate_id`,
    `transport_closure`, or `depends_on_hall_closure: true`);
  - any P5 calibration-nuisance key (registration, coil shape, divergence / beam-efficiency reading, facility
    interpretation). These are never design variables.

  The credible set is ∅. Screening candidates are never a sizing source.
- **Legacy code is not used.** The v1.7 functions at the top of `abep_sim/mass_bom.py` stay byte-identical because
  `archengine.py` and `system.py` import them, and the goldens must not move. They are `xe_tank`, `hall_magnetic_circuit`,
  `hall_channel_mass`, `structure_mass`, `build_bom` and the `MGA` dict (new 30 %, modified 15 %, existing 5 %,
  calculated 10 %). Their constants carry no citation, and the v1 skeleton does not use them (OD-M3). Earlier repository
  mass figures are not CBE sources either (docs/HISTORY.md v0.5 and Phase 4 tables; the withdrawn 110–120 kg). They
  rest on the superseded 0-D Hall closure and on uncited defaults. Do not quote them.

## Margin policy (source: ESA SRE-PA/2011.097 Issue 1 Rev 3)
Source: ESA SRE-PA & D-TEC staff, *Margin philosophy for science assessment studies*, SRE-PA/2011.097/, Issue 1,
Revision 3, 15/06/2012. The copy is open and full text at
<https://sci.esa.int/documents/34375/36249/1567260131067-Margin_philosophy_for_science_assessment_studies_1.3.pdf>. It was
accessed 2026-09-26, and the PDF as fetched has sha256 `0ddc1b0116f96b2a4f26732dfe67ca682b7df397156c0ed6809c3c0392cc9501`.
The document is written for spacecraft-level assessment studies. **Applying it to a propulsion subsystem is this BOM's
proposal**, and the ESA document does not require it. The values below are quoted from §2.1.1 (pp. 5–6).

| category id | MGA | ESA text (quoted) | label as printed |
|---|---|---|---|
| `ecss_ab_off_the_shelf` | 5 % | "≥ 5 % for "Off-The-Shelf" items (ECSS Category: A / B, see ECSS-E-ST-10-02C)" | R-M1-41 |
| `ecss_c_minor_modification` | 10 % | "≥ 10 % for "Off-The-Shelf" items requiring minor modifications (ECSS Category: C …)" | R-M2-42 (printed under R-M1-4) |
| `ecss_d_new_or_major_modification` | 20 % | "≥ 20 % for new designed / developed items, or items requiring major modifications or re-design (ECSS Category: D …)" | R-M1-43 |
| `propellant_not_equipment` | 0 | inferred: maturity margins apply "at equipment level" (R-M1-4); the system margin shall "not include any propellant residuals or unused propellant" (R-M1-3) | inferred |
| `policy_allocation_nominal` | 0 | inferred: harness "at least 5 % of nominal dry mass" (R-M1-7), and nominal dry mass already includes maturity margins (R-M1-2) | inferred |

- ESA states these as minima ("≥"). The BOM applies them at the minimum.
- The ECSS category definitions themselves (ECSS-E-ST-10-02C) were not consulted.
- AIAA S-120A is **not used (TBD)**: no openly accessible reproduction was consulted.

Other ESA allocations used:
- **Propellant residuals: 2 % of the Xe load** (R-M1-6: "A 2% of propellant residuals shall be added to the propellant
  calculated").
- **Harness: ≥ 5 % of nominal dry mass** (R-M1-7). Until a harness design exists, harness = f/(1−f) × (nominal dry mass
  of the other dry items), which makes harness = f × total nominal dry mass, with f = 0.05.
- **Tank volume: propellant plus at least 10 %** (R-M1-10). This is an input to the tank lower bound.

**System margin: PROPOSED 20 % of nominal dry mass.** The basis is ESA R-M1-1, a spacecraft-level requirement: "an ESA
system level mass margin of 20 % of the nominal dry mass at launch". The recorded alternative is the RFP R3 "10 %
margin" (docs/HISTORY.md v0.1; verify against the RFP). It is unresolved whether R3 means a system margin, a growth
allowance or both (hard-gate OD7). Neither G3 verdict depends on this choice:
- G3 PASS uses Σ CBE × (1 + max(MGA, 10 %)). `rollup(..., g3_margin_floor=0.10)` reports it as `g3_bounding_mass_kg`.
- G3 FAIL uses the margin-free CBE lower bound.

## Items
Every dry item except the harness carries maturity **PROPOSED D (20 %)**. No design or selected part exists, so the
highest ESA category applies until one is identified. This choice is conservative on the PASS side and does not affect
the margin-free FAIL screen. The table maps each item to its gate element, as named in the hard-gate matrix G3 envelope
and cited by path (`docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json`), and to its
`bus_power_boundary_v1` component (`abep_sim/arch_boundary.py`). Both contracts are defined by other lanes and are
referenced lazily. When `arch_boundary` was present in another lane's checkout at creation, it was cross-checked: every
boundary component of every architecture is carried, and no unknown names are used.

| item | scope | gate element | power-boundary components | class | maturity (MGA) | CBE |
|---|---|---|---|---|---|---|
| `intake` | common | intake | — | dry | D (20 %) | TBD |
| `filter` | common | filter | — | dry | D (20 %) | TBD |
| `compressor` | common | compressor | compressor | dry | D (20 %) | TBD |
| `atmospheric_gas_chamber` | common | atmospheric_gas_chamber | — | dry | D (20 %) | TBD |
| `atmospheric_valve` | common | valves_and_flow_control | flow_control | dry | D (20 %) | TBD |
| `xe_valve_and_flow_control` | common | valves_and_flow_control | flow_control | dry | D (20 %) | TBD |
| `xe_tank` | common | xenon_chamber_and_xenon_load | — | dry | D (20 %) | TBD (lower-bound relation available once inputs are declared) |
| `xe_load` | common | xenon_chamber_and_xenon_load | — | propellant | propellant (0) | TBD (declared allocation, OD-M4) |
| `xe_residual` | common | xenon_chamber_and_xenon_load | — | propellant | propellant (0) | 0.02 × `xe_load` (ESA R-M1-6) |
| `hall_thruster_head` | common | hall_thruster | hall_discharge | dry | D (20 %) | TBD (own design; never from a closure) |
| `hall_magnets` | common | hall_thruster | hall_magnet | dry | D (20 %) | TBD (own B(z) design) |
| `cathode` | common | cathode | cathode_keeper, cathode_heater | dry | D (20 %) | TBD |
| `ppu` | common | power_processing | hall_discharge, hall_magnet, cathode_keeper, cathode_heater, flow_control, compressor, housekeeping | dry | D (20 %) | TBD |
| `harness` | common | harness_and_structure | — | dry | allocation (0) | 5 % of nominal dry (ESA R-M1-7) |
| `thermal_hardware` | common | thermal_control | thermal_control | dry | D (20 %) | TBD |
| `structure` | common | harness_and_structure | — | dry | D (20 %) | TBD |
| `rf_source` | rf_hall | rf_source | rf_source | dry | D (20 %) | TBD |
| `rf_generator` | rf_hall | rf_source | rf_source | dry | D (20 %) | TBD |
| `rf_matching_network` | rf_hall | rf_source | rf_source | dry | D (20 %) | TBD |
| `ecr_source` | ecr_hall | ecr_source | ecr_source | dry | D (20 %) | TBD |
| `microwave_source` | ecr_hall | ecr_source | ecr_source | dry | D (20 %) | TBD |
| `waveguide` | ecr_hall | ecr_source | ecr_source | dry | D (20 %) | TBD |
| `ecr_magnets` | ecr_hall | ecr_magnet | ecr_magnet | dry | D (20 %) | TBD |

What each TBD requires is recorded per item in `mass_bom_v1.json` (`cbe.requires`, `lower_bound.requires`). The item
list itself is PROPOSED (OD-M5). It follows three sources:
- the RFP architecture blocks as recorded: intake → filter → compressor → atmospheric gas chamber → valve; Xe chamber →
  valve; ionization/discharge → acceleration/thrust;
- the recorded R3 inclusion list: intake, compressor, PSE, Xe + tank, structure;
- the lane specification.

## Plausibility screen (milestone-A elimination tool for hard-gate G3)
`plausibility_screen()` uses **sourced lower bounds only**, and each bound must have one of the G3 fail bases:
`hard_physical_bound`, `measurement_vyovrinda`, `measurement_same_hardware` or `model_closure_independent`. Each bound
also needs a scope justification that no design of the architecture avoids it. For each architecture the screen
computes two quantities:
- **Margin-free CBE lower bound** = Σ item lower bounds. An item without a bound contributes its trivial floor of 0 kg,
  so the sum stays a valid lower bound.
- **MEV lower bound** = Σ_dry LB × (1 + MGA) × (1 + system margin) + Σ_propellant LB. A TBD MGA is taken as 0, its
  minimum.

The comparison is strict (> 40 kg), so a bound equal to 40 kg decides nothing. The 40 kg limit is
`abep_sim/constants.py RFP.mass_max_kg`, as recorded; verify it against the RFP. The verdicts are:

| verdict | meaning | usable for G3 FAIL? |
|---|---|---|
| `EXCEEDS_LIMIT_MARGIN_FREE` | margin-free lower bound > 40 kg | yes (flag `mass_margin_free_lower_bound`) |
| `EXCEEDS_LIMIT_MEV_ONLY` | only the margin-inclusive bound exceeds 40 kg | no, because it depends on the margin policy (OD7) |
| `NOT_EXCLUDED_PARTIAL_COVERAGE` / `_FULL_COVERAGE` | bounds exist and stay ≤ 40 kg | no |
| `LOWER_BOUNDS_UNAVAILABLE` | no item has a sourced lower bound | no |

The screen also reports the common-item and architecture-specific parts of the bound separately. The difference
between architectures therefore shows up only in the pre-ionizer items.

**Current result:** `LOWER_BOUNDS_UNAVAILABLE` for `hall_only`, `rf_hall` and `ecr_hall`. The lower bound is 0 kg for
all three, and no architecture is excluded.

### What would make the screen bite
- **Xe tank:** declared Xe load, storage pressure, burst factor, and wall strength and density (sourced). Together these
  give a hard physical bound through the relation below.
- **Xe load:** a sourced minimum Xe flow (for example, cathode flow) × the Xe-fed hours the RFP requires. The Xe-duty
  interpretation is open, so this needs a scope justification.
- **Pre-ionizer, cathode and PPU parts:** supplier-measured masses of the only parts available, with a scope
  justification. A published mass of *one* existing part is not a lower bound for every design of an architecture.
- **Intake:** a minimum frontal area, set by drag and flow requirements, × a sourced minimum areal mass.

### Tank lower-bound relation (`thin_wall_sphere_min_mass_kg`)
Take a spherical, monolithic, isotropic shell of internal volume V and radius r = (3V/4π)^{1/3}. At burst it must hold
p_b = burst_factor × MEOP. Membrane equilibrium of the sphere gives σ = p_b r / (2t), so σ ≤ σ_ult requires
t ≥ p_b r / (2 σ_ult). The shell mass therefore satisfies

m ≥ 4π r² t ρ ≥ 4π r² ρ p_b r / (2σ_ult) = (3/2) · p_b · V · ρ / σ_ult.

The relation excludes bosses, ports, liner and mounts. The exact thick-shell volume 4/3 π((r+t)³ − r³) ≥ 4π r² t, and
any thick-wall correction adds mass, so the expression stays a lower bound. It is valid only for a monolithic isotropic
metal shell. Composite-overwrapped vessels are **not** covered. It is used only as a `hard_physical_bound`, with every
input sourced and explicit; none has a default.

## Open owner decisions
| id | topic | current handling |
|---|---|---|
| OD-M1 | system margin: 20 % (ESA R-M1-1, PROPOSED) vs 10 % (RFP R3, verify) | PROPOSED 20 %; no G3 verdict depends on it |
| OD-M2 | maturity categories | PROPOSED D for every dry equipment item until parts or designs are selected |
| OD-M3 | legacy uncited `MGA` dict in `abep_sim/mass_bom.py`, referenced by hard-gate OD7 | unchanged (archengine imports it; retiring it is a model change: goldens, HISTORY); not used here |
| OD-M4 | declared Xe allocation | TBD; `xe_load`, `xe_residual` and the tank bound stay unresolved |
| OD-M5 | item list (cf. hard-gate OD10) | PROPOSED list used; an amendment is a new BOM version |
| OD-M6 | ESA 5 % harness allocation applied to a subsystem | used until a harness design exists |
| OD-M7 | whether the 40 kg includes the Xe load | included as propellant (R3 as recorded; verify against the RFP) |

## Sources
- ESA SRE-PA/2011.097 Issue 1 Rev 3 (2012), URL and hash above. This is a margin *policy*, not physical evidence.
- RFP mass limit as recorded: `abep_sim/constants.py` (`RFPConstraints.mass_max_kg`), CLAUDE.md, and docs/HISTORY.md
  v0.1. **Verify against the RFP document.**
- Hard-gate matrix G3 (`docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json`) and the bus-power boundary
  (`abep_sim/arch_boundary.py`) are shared contracts from other lanes. They are referenced by path, never imported at
  module load, and `check_power_boundary_coverage()` resolves them lazily with a clear error if they are absent.
