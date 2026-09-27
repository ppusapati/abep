# Thermal / life accounting framework (THL lane), v1

Status: **framework only**. `abep_sim/thermal_life.py` is a pure module and is **not wired into `archengine`**. It
produces no thermal or life number for any Vyovrinda architecture today. Every design input is TBD. The credible Hall
transport set is empty (gate 3 FAIL, P5-N₂ v1 INCONCLUSIVE), so no admitted HallMap exists to supply wall heat. This
document claims no thermal closure, no architecture ranking and no hardware qualification.

Files:
| file | role |
|---|---|
| `abep_sim/thermal_life.py` | heat-source accounting, lumped steady-state node temperatures, margins, refusal logic |
| `schemas/thermal_life/limits_v1.json` | sourced limits and relations (evidence attributes per `docs/EVIDENCE.md`), or explicit `TBD` records |
| `schemas/thermal_life/inputs_v1.json` | input contract: every required input per component, its unit, and the lane or module expected to produce it |
| `tests/test_thermal_life_framework.py` | hand-calculation checks, refusal paths, "every limit sourced" check |
| `hallthruster_bridge/hall_map_schema_v1.json` | read only; the source of the HallMap field names and units |
| `abep_sim/hall_ensemble.py`, `abep_sim/hall_map.py` | read only, imported lazily; `require_admitted` and `pinned_commit` gate the Hall wall-flux inputs (§2.3) |

## 1. Scope
**Question answered.** Once an architecture closes on power at the bus-power boundary, are its heat loads and
life-limited parts feasible against sourced limits? The answer is given per component as margins.

**Components.** Thermal nodes use the bus-power boundary component names. That module is *not imported*; the names are
duplicated in `thermal_life.BUS_POWER_COMPONENTS` and in `inputs_v1.json`, and a test checks them.

| thermal node | bus-power components feeding it | node represents |
|---|---|---|
| `hall_discharge` | `hall_discharge` | Hall channel walls (lumped). Anode heat is accounted but has no limit in v1 |
| `hall_magnet` | `hall_magnet` | electromagnet winding (lumped, plus a hot-spot allowance) |
| `cathode` | `cathode_keeper`, `cathode_heater` | cathode assembly, plus emitter temperature and life |
| `rf_source` | `rf_source` | RF source structure (antenna, coupler, dielectric) |
| `ecr_source` | `ecr_source` | ECR source structure (coupler, window) |
| `ecr_magnet` | `ecr_magnet` | ECR permanent-magnet assembly (bus allocation must be 0 W) |

**Outcomes.** Each check returns `PASS`, `FAIL` or `NOT_DEMONSTRATED`. `NOT_DEMONSTRATED` means the inputs are complete
but the sourced evidence cannot decide, for example a temperature outside a coefficient's measured range. The overall
status is `FAIL`, `NOT_DEMONSTRATED` or `PASS_CHECKED_ITEMS`. `PASS_CHECKED_ITEMS` is **not** a thermal qualification:
the result always lists `not_covered`, and it inherits the evidence levels of its inputs.

**Refusals (ValueError, never a default).** The module refuses:
- a missing or unknown input;
- a unit string different from the contract (no unit conversion is done);
- an input without a source, or without evidence level 1–7 and a quantity type;
- a TBD limit record or TBD value;
- a copper, magnet or evaporation relation evaluated outside its sourced domain;
- non-physical inputs: heat fractions summing above 1, accounted discharge heat above the discharge power, or
  inconsistent ECR power between `ecr_source` and `ecr_magnet`.

**Steady state only.** There are no transients or eclipse cycling. Each node rejects heat only through the paths it
declares. The radiator and rejection capability is an **input**, TBD from thermal geometry.

## 2. Equations and sources
Page and table locators below are the printed ones. Each source was downloaded and its text compared on 2026-09-26; URLs
are in `limits_v1.json` → `sources`.

### 2.1 Heat rejection (all nodes)
- Conductance path: Q = G (T − T_sink).
- Radiation path: Q = ε σ A F (T⁴ − T_sink⁴), with σ = 5.670374419×10⁻⁸ W m⁻² K⁻⁴ (exact, NIST CODATA).
- Node temperature: solve Σ_paths Q(T) = Q_in(T) by bisection. Q_in may rise with T (the coil). When a model domain is
  given, Q_in is never evaluated outside it. A balance outside the domain returns a one-sided bound
  (`{'T_K': None, 'bound': ('above'|'below', T_edge)}`), not an extrapolated number.

### 2.2 Hall electromagnet (`hall_magnet`)
- P_coil(T) = I² R_ref · r(T)/r(T_ref) + Q_ext. The drive is constant-current, and T is solved self-consistently.
- Copper r(T), NBS Handbook 100 (1966):
  - `copper_iacs_linear`: R(T) = R₂₀[1 + α₂₀(T − 20 °C)], with α₂₀ = 0.00393 K⁻¹ and ρ₂₀ = 1.7241 µΩ·cm (pp. 3–4).
    The domain is 0–200 °C. The upper bound is the source's "linear up to 200 °C". The lower bound, 0 °C, is our choice
    and is marked `assumed`.
  - `copper_roeser_ratio`: Roeser's unpublished NBS R_t/R₀ table, −100 to 500 °C (p. 4), interpolated piecewise-linearly
    and used as a ratio only. Because the curve is convex above 300 °C, this interpolation overestimates R, which is
    conservative for heating.
  - Coil resistance from geometry: R₂₀ = ρ₂₀ ℓ / A.
- Insulation limit: IEC 60085:2007 thermal classes (Table 1, p. 7; publisher preview only). A class is the recommended
  maximum continuous use temperature of the electrical insulation system (EIS) and carries **no life basis** (3.11 NOTE 1).
- Optional derating (an owner decision; applying it to a thruster coil is an analogy): NASA EEE-INST-002, Section M1,
  Table 4 and notes (p. 10 of 11):
  - Class C: "Max. Temp. − 20 °C" with a 50,000 h life basis (note 1/b).
  - Custom devices: 0.75 × the maximum operating temperature (note 1/c). Carrying the 50,000 h basis over to this factor
    is our **inference (verify)**. Applying 0.75 in °C is our reading (verify).
  - Note 1/a also gives the hot-spot allowance convention (+10 °C) and the MIL-PRF-27 resistance-rise formula
    ΔT = (R − r)/r (t + 234.5) − (T − t), available as `winding_temperature_rise_mil_prf_27`.
- Checks:
  - winding hot-spot temperature against the allowable;
  - coil power against the `hall_magnet` bus allocation;
  - insulation life against the RFP firing hours. This check stays `NOT_DEMONSTRATED` unless the policy carries a
    *stated* life basis.

### 2.3 Hall walls (`hall_discharge`)
- Wall ion heat: Q_i = e Γ_i ε_i A_wall.
  - Γ_i is HallMap `wall_ion_flux_m2s`: the channel-averaged (z ≤ L), time-averaged WallSheath Bohm flux.
  - ε_i is HallMap `wall_ion_energy_eV`: the flux-weighted Zφ_s + T_e/2.
- Wall electron heat: Q_e = e Γ_i · 2T_e,w/(1 − γ) · A_wall. This combines Goebel & Katz 2008 Ch. 7 Eq. (7.3-28)
  (p. 348), zero net wall current I_iw = I_ew(1 − γ), with Eqs. (7.3-43) and (7.3-45) (p. 354), under which each
  electron deposits 2T_e. Secondary-electron cooling is neglected, as in the source.
- Anode heat: P_a = 2 I_d T_e(anode), from Eq. (7.3-53) (p. 358). It is accounted only; the anode has no node or limit in v1.
- **Conservation gate:** Q_i + Q_e + Q_additional + P_a ≤ P_d, otherwise ValueError.
- Wall limit: Henze HeBoSint datasheet (08.2021), "Use Temperature max." in oxidizing (~900 °C) or inert/vacuum
  (~1500–2000 °C) atmosphere, per grade. This is a manufacturer guide value; it does not cover plasma bombardment or
  atomic oxygen. The P5 wall grade, Saint-Gobain Combat M26 (Schinder 2016 dissertation p. 30: 60 % BN / 40 % silica by
  mass), is **TBD**: its datasheet sat behind a bot challenge that was not bypassed.
- Erosion life: life = d_allow / (Γ_i · (peak/avg) · Y_v) against the RFP firing hours. d_allow, peak/avg and the
  volumetric sputter yield Y_v are all inputs; no sputter yield is sourced in v1.
- **Wall-flux provenance gate (gap G11 of `docs/evidence/wall_life/`, repaired 2026-09-27).** Γ_i and ε_i feed both the
  wall heat and the erosion life, so `check_feasibility` accepts `hall_discharge.wall_ion_flux_m2s` and
  `wall_ion_energy_eV` only when both records carry the same `wall_flux_provenance` of one of two kinds
  (`inputs_v1.json` → `wall_flux_provenance`):
  - `admitted_hallmap`: `ensemble_member_id`, `trustworthy`, `wall_life_trustworthy`, `hallthruster_commit`. At check time
    the member id is re-verified with `abep_sim.hall_ensemble.require_admitted` (read-only, imported lazily). That call
    refuses screening candidates (`sgb-screen-*`) and unknown ids. Both trust flags must be `true`, the commit must equal
    the `PINNED.toml` commit, and the record's quantity type must be `model-derived`.
  - `measured_hardware`: an `evidence_record` with non-empty `test_article`, `facility`, `document`,
    `measurement_method`, `uncertainty`, `operating_point` and `applicability_domain`; quantity type `measured`.
  - Anything else raises `ValueError`: a missing provenance (hand-entered flux), a screening candidate, an unadmitted or
    unknown member, or mixed sources for flux and energy. No PASS, FAIL or NOT_DEMONSTRATED is produced from such
    input. The credible set is ∅ and no hardware measurement exists, so **every wall-flux input is refused today**. The
    wall-temperature and erosion-life checks of `hall_discharge` therefore cannot run for any architecture yet.
- `thermal_life.hallmap_wall_inputs(point, member_id, evidence_level)` builds the input records from a HallMap query.
  It refuses unless `member_id` passes `require_admitted`, the query is `trustworthy` **and** `wall_life_trustworthy`,
  and it carries the pinned HallThruster.jl commit. It attaches the `admitted_hallmap` provenance, which
  `check_feasibility` verifies again. There is no default evidence level: the caller states it (Vyovrinda geometry is
  outside any P5-validated domain).
- Still open from G11 (not part of this gate): carrying the sputter-yield extrapolation flags of
  `docs/evidence/wall_life/sputter_yield_db_v1.json` into the result and mapping OUT_OF_DOMAIN to NOT_DEMONSTRATED.
  `volumetric_sputter_yield_m3_per_ion` is still a plain sourced input.

### 2.4 RF and ECR sources (`rf_source`, `ecr_source`)
- Q = P_RF · (f_antenna_copper + f_coupler_dielectric + f_plasma_to_structure). All three fractions are **inputs** from
  source design or test, and their sum must be ≤ 1.
- The structure limit record is TBD: antenna insulation, dielectric window or tube, and matching network.

### 2.5 ECR permanent magnets (`ecr_magnet`)
- Q = f_to_magnets · P_ECR. The input fraction is shared with `ecr_source`, and the combined fractions must be ≤ 1.
- Maximum use temperature per grade. Sources, typical values:
  - Arnold Recoma 35E datasheet;
  - MMPA 0100-00 Table IV-4 (p. 20) family values;
  - Arnold RTC slides (Constantinides, slide 14) for Sm₂Co₁₇ 27 MGOe, SmCo₅ 20 MGOe, N38UJ, L-38UHT and N48M.
  N42SH has no maximum-use row on its datasheet, so its maximum use temperature is TBD and the check refuses.
- Reversible loss: Br(T)/Br(20 °C) = 1 + α(T − 20)/100 (Arnold RTC slides 11–12). It is applied **only** inside the
  grade's coefficient range and is otherwise `NOT_DEMONSTRATED`. The slides state this is approximate except at the
  calibration temperature.
- Irreversible loss: |H_demag,max| < H_knee(T), per the VAC VACODYM/VACOMAX brochure (p. 34: the working point stays in
  the linear section over the whole temperature range; p. 16: H_K,90 / H_D5).
  - The knee field must be quoted at a temperature ≥ the magnet temperature, otherwise `NOT_DEMONSTRATED`.
  - Hcj(T) from the datasheet is used as a consistency check (knee field ≤ Hcj) and a necessary condition. It is not a
    substitute for a knee field.

### 2.6 Cathode (`cathode`, LaB₆)
- Assembly heat: f_keeper · P_keeper + duty · P_heater + P_emitter,plasma. All terms are inputs from the cathode dossier.
- Emitter temperature: Richardson–Dushman J = P T² exp(−e(φ₀ + αT)/kT), Goebel & Katz 2008 Ch. 6 Eqs. (6.3-1)–(6.3-3)
  (p. 251). All four LaB₆ sets of Table 6-1 (p. 252) are carried as an envelope; none is selected:
  - Lafferty D = 29, φ = 2.66;
  - Jacobson & Storms D = 110, φ = 2.87;
  - Storms & Mueller A = 120, φ = 2.91;
  - Kohl A = 120, φ = 2.66 + 1.23×10⁻⁴ T.
  The Schottky term is neglected, which is conservative for evaporation.
- Evaporation-limited life = f_usable · m_insert / (G_evap(T_max,envelope) · A_emit). The form follows sec. 6.8.4
  (pp. 302–303), with f_usable = 0.9 (p. 303, the source's assumption). **G_evap(T) is TBD.** No sourced table is in
  the repository: Goebel & Katz Fig. 6-8 is graphical and would need digitizing plus a J→T mapping.
- O₂ poisoning screen. The only reported no-degradation point is T ≥ 1570 °C with p_O₂ ≤ 10⁻⁴ Torr (p. 306). Anything
  outside that point is `NOT_DEMONSTRATED`. Atomic oxygen and O⁺ exposure on the ABEP air path are **not covered** by
  any source.
- Heater cycles: qualified cycles minus required cycles. Both are inputs from the cathode dossier and operations.
- The assembly temperature limit record is TBD (cathode dossier).

## 3. Inputs: what each component needs and where it will come from
The full list, with units, is in `inputs_v1.json`. None is available today except the mission firing hours (RFP > 15,000 h).

| input group | producer (lane / module) | state 2026-09-26 |
|---|---|---|
| component electrical powers: `hall_discharge`, `hall_magnet`, `cathode_keeper`, `cathode_heater`, `rf_source`, `ecr_source`, `ecr_magnet` | bus-power boundary lane (`bus_power_boundary_v1`) | TBD (other lane) |
| discharge power and current, wall ion flux and energy | admitted HallMap (`abep_sim/hall_map.py`, schema v1) via `hallmap_wall_inputs`; wall flux/energy alternatively measured hardware data with an evidence record (provenance gate, §2.3) | TBD: credible set ∅, no admitted map, no hardware data (wall flux refused) |
| wall T_e, SEE yield γ, anode-side T_e | solver outputs **not in hall_map_schema_v1** | TBD; a schema extension is an owner decision |
| channel wall area, erodible depth, peak/average flux profile | Vyovrinda thruster geometry; axial flux profile | TBD |
| sputter yield of the wall material for the ion mix | sourced sputter data (not in v1) | TBD |
| coil current, R_ref, magnet-wire class, external heat to coil | Vyovrinda magnetic-circuit design and thruster thermal model | TBD (P5 coil currents unpublished) |
| RF and ECR heat fractions, ECR heat-to-magnet fraction, demag field, knee field | RF/ECR source design, magnetostatics, manufacturer demag curves | TBD |
| cathode: keeper fraction, heater duty, emitter plasma heating, emitting area, insert mass, emitter p_O₂, heater cycles | cathode dossier; operations concept | TBD |
| rejection paths (G, ε, A, F, T_sink) for every node | thermal geometry and radiator design; orbit thermal environment | TBD |
| derating policy, wall environment, copper model | owner decisions | TBD |

## 4. What remains TBD (limits)
| limit record | requires |
|---|---|
| `bn_combat_m26` | Combat M26 maximum-use temperatures (manufacturer datasheet; not reached without bypassing a bot challenge) |
| `lab6_evaporation_rate` | sourced LaB₆ G_evap(T) table (`T_K`, `rate_kg_m2s`) |
| `cathode_assembly_temperature_limit` | cathode dossier limiting temperature (`T_max_C`) |
| `rf_source_structure_limit` | sourced RF source material limit (`T_max_C`) |
| `ecr_source_structure_limit` | sourced ECR window or coupler limit (`T_max_C`) |
| `pm_ndfeb_n42sh_arnold.T_max_use_C` | manufacturer maximum-use statement for N42SH |
| `iec60085_thermal_classes.life_basis_h` | thermal-endurance evaluation of the actual EIS (IEC 60216) or a coil life test |

Other open items, all verify:
- the IEC 60085 edition currency;
- the MMPA 0100-00 publication year, and its Table IV-4 footnotes `*` and `**`, which are not legible in the PDF text layer;
- the Goebel & Katz publisher details;
- the inference that the EEE-INST-002 note 1/c factor carries the 50,000 h life basis.

## 5. Not covered in v1
The following are not covered (see also `thermal_life.NOT_COVERED`):
- transients and eclipse cycling;
- an anode node;
- inter-node coupling (heat one node passes to another must be supplied as an input, e.g. `hall_magnet.external_heat_W`);
- PPU losses (bus-power lane);
- radiation dose, atomic-oxygen and outgassing effects;
- keeper erosion;
- heater failure modes other than the cycle count.

## 6. Evidence notes
- Every sourced limit has evidence level 4–6. None is a Vyovrinda hardware measurement (levels 1–2 are absent).
  Manufacturer values are *typical*, not guaranteed.
- Quantity types follow `docs/EVIDENCE.md`:
  - normative or recommended limits (IEC classes, maximum-use temperatures, the Henze "~" values) are `assumed`;
  - datasheet coefficients are `measured` (the procedure is unpublished);
  - Richardson fit parameters are `inferred`.
- Test fixtures in `tests/test_thermal_life_framework.py` are hand-calculation inputs, not design values. Its
  `SYNTHETIC` limit records exist only in an in-memory copy, to exercise code paths whose real limit is TBD. The
  admitted-member path is tested against a monkeypatched ensemble with one synthetic member (`adm-fixture-01`); no real
  admission exists. The real ensemble is used to show that every screening candidate and unknown id is refused.
