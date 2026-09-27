# Parametric Xe ledger and stored-Xe subsystem ledger v1

**Follow-on:** `fo_xe_system_ledger` (trigger `T_A5_XE_LEDGER`, owner addendum A6). **Status:** PARAMETRIC_LEDGER — total Xe mass and stored-Xe subsystem mass REFUSED (TBD inputs); nothing frozen. **Milestone support:** A (conditional selection); see the milestone statement.
**Data:** [`xe_ledger_v1.json`](xe_ledger_v1.json), written by `python docs/budgets/xe_ledger/build_xe_ledger.py` and checked with `--check`. **Code:** `abep_sim/xe_ledger.py` (pure; not wired into `archengine`). **Tests:** `tests/test_xe_ledger.py`. This file is generated; edit the builder, not this file.

**Owner basis (immutable, sha256-pinned):**

| file | sha256 |
|---|---|
| `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json` | `5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac` |
| `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json` | `0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621` |
| `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json` | `aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180` |
| `docs/decisions/verification/A5_BASELINE_VERIFICATION.json` | `4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523` |

G0 precondition: verdict **CLEAN** at `23b79c843528656f21333fd44bdf02c2e9e3e3b8` (downstream artifacts may pin A5 by the sha256 above).

## Result in one paragraph
Only the A5 cathode design term is fixed: 0.10 mg/s over 15,000 firing hours = **5.4 kg** (13.50 % of the 40 kg requirement, 15.00 % / 15.88 % of the 36 / 34 kg A5 allocation). The 0.15 mg/s upper test point would take 8.1 kg (20.25 % / 22.50 % / 23.82 %). Startup, transition, fallback, reserve, tank, regulator, valves, plumbing and mounting/thermal are TBD, so **m_Xe_total and m_Xe_subsystem are refused** (14 inputs TBD). The scenarios and surfaces show what the TBD inputs must satisfy. Three findings follow from them:
- At the PROPOSED 25 % share of 34 kg (8.5 kg), the 0.15 mg/s cathode alone takes 8.1 kg; the cathode flow that alone fills that share is 0.157 mg/s. At 0.10 mg/s, 3.1 kg remain for the tank, feed hardware, starts, transfers, fallback and reserve.
- A Xe-fed discharge burns its allowance fast: 1 kg lasts 277.8 / ṁ[mg/s] hours (25.3 h at the 11 mg/s ignition flow of the HT5k analogue). With SC-1 restarts, the SC-1 reserve and no tank or feed hardware (bounding), the longest cumulative fallback inside 25 % of 34 kg is 32.2 h. That is tens of hours, about three orders of magnitude below the 15,000 firing hours, so a Xe fallback can never be a sustained mode (consistent with the A5 rule).
- Restart frequency dominates the non-cathode Xe. Per-orbit restarts (17,737 over 26,000 h at 180 km) with the SC-1 per-cycle Xe need 26.5 kg of Xe (scenario 10 % reserve included) before any tank or feed hardware. Per-orbit cycling fits only if each start + transfer uses tens of milligrams to a few tenths of a gram (SS-5), which is a candidate H-1/C-1 test requirement, not a prediction.

## Ledger equations (A6, implemented exactly)

| term | definition |
|---|---|
| `m_cathode` | mdot_cathode x t_firing |
| `m_startup` | N_starts x t_startup x mdot_startup |
| `m_transition` | N_transitions x t_transition x mdot_transition |
| `m_fallback` | t_fallback_max x mdot_fallback |
| `m_reserve` | explicit policy term, one of: fraction_of_other_terms: m_reserve = f_reserve x (m_cathode + m_startup + m_transition + m_fallback); f_reserve dimensionless ('1'), >= 0 OR absolute_mass: m_reserve = m_reserve_abs (mass unit), >= 0 |
| `m_Xe_total` | m_cathode + m_startup + m_transition + m_fallback + m_reserve |
| `m_tank` | explicit tank model, one of: tankage_fraction: m_tank = f_tank x m_Xe_total (the loaded Xe, all five terms); f_tank dimensionless ('1'), >= 0 OR tank_mass: m_tank = m_tank_abs (mass unit), >= 0, for the tank selected for the declared Xe load |
| `m_Xe_subsystem` | m_Xe_total + m_tank + m_regulator + m_valves + m_plumbing + m_mounting_thermal |

The reserve is always its own term. The tankage fraction applies to the loaded Xe (all five terms). No default exists for any input: a missing or TBD input makes `evaluate` raise `LedgerIncomplete` and list every blocker, and a partial evaluation returns `null` for every total it cannot close.

**Accounting convention (explicit input, OD-XE-1):**
- `PHASE_TOTAL_FLOW`: Each phase term (startup, transition, fallback) carries the TOTAL Xe flow during that phase (anode-side Xe plus cathode Xe). m_cathode carries the cathode flow over t_firing only. Phase hours are booked in their own terms. Where a phase's hours are also counted inside t_firing, the cathode flow over those hours is booked twice, at most mdot_cathode x overlap hours (conservative).
- `CATHODE_CONTINUOUS_INCREMENTAL`: m_cathode carries the cathode flow over every hour the cathode flows (t_firing must then include startup, transition and fallback hours). Each phase term carries only the Xe ABOVE that cathode flow (anode-side Xe plus any cathode flow above mdot_cathode). If t_firing is held at the RFP firing hours, the cathode flow during phases outside those hours is missing (non-conservative).

## The fixed term: cathode Xe (A5)

| case | ṁ (mg/s) | t_firing (h) | m_cathode (kg) | A5 reference (kg) | share of 40 / 36 / 34 kg | status |
|---|---|---|---|---|---|---|
| design term | 0.1 | 15,000 | 5.4 | 5.4 | 13.50 % / 15.00 % / 15.88 % | FIXED_DESIGN_TERM (A5 allocation; not a demonstrated flow) |
| upper test point | 0.15 | 15,000 | 8.1 | 8.1 | 20.25 % / 22.50 % / 23.82 % | A5 experimental upper test point only; never the allocation |

- Arithmetic: 0.10e-6 kg/s x 15,000 h x 3600 s/h = 5.4 kg; 0.15e-6 kg/s x 5.4e7 s = 8.1 kg.
- A5 rejection illustration: the flow that consumes 40 kg in 15,000 h is 0.7407 mg/s (0.74 mg/s gives 39.96 kg). This illustrates rejection only.
- Firing-hours sensitivity (sensitivity only; A5 fixes the cathode term at 15,000 h (OD-XE-5)): at 18,000 h the term is 6.48 kg (0.10 mg/s) or 9.72 kg (0.15 mg/s).

Context: the cathode flows of other cathodes over 15,000 h (AN-01, level 3). These are never a Vyovrinda value. The veto layer carries them as RI-MASS-CATHODE-XE, which straddles the limit and is not verdict-bearing.

| flow | ṁ (mg/s) | m over 15,000 h (kg) | share of 40 / 36 / 34 kg |
|---|---|---|---|
| HC1/HC3 design range, lower end | 0.08 | 4.32 | 10.80 % / 12.00 % / 12.71 % |
| A5 design target | 0.1 | 5.4 | 13.50 % / 15.00 % / 15.88 % |
| A5 experimental upper test point | 0.15 | 8.1 | 20.25 % / 22.50 % / 23.82 % |
| P5 cathode setpoint | 0.44 | 23.8 | 59.40 % / 66.00 % / 69.88 % |
| HC1 upper design / HC3 endurance flow | 0.5 | 27 | 67.50 % / 75.00 % / 79.41 % |
| HC3 minimum spot-mode flow (diode) | 0.6 | 32.4 | 81.00 % / 90.00 % / 95.29 % |
| HC1 diode plume-mode onset | 0.8 | 43.2 | 108.00 % / 120.00 % / 127.06 % |
| HC3 upper design flow | 1.0 | 54 | 135.00 % / 150.00 % / 158.82 % |

Cathode flow that alone fills a share of a reference over 15,000 h:

| reference | share | cap (kg) | ṁ (mg/s) |
|---|---|---|---|
| RFP_40kg | 0.25 | 10 | 0.1852 |
| RFP_40kg | 0.5 | 20 | 0.3704 |
| RFP_40kg | 1.0 | 40 | 0.7407 |
| A5_alloc_36kg | 0.25 | 9 | 0.1667 |
| A5_alloc_36kg | 0.5 | 18 | 0.3333 |
| A5_alloc_36kg | 1.0 | 36 | 0.6667 |
| A5_alloc_34kg | 0.25 | 8.5 | 0.1574 |
| A5_alloc_34kg | 0.5 | 17 | 0.3148 |
| A5_alloc_34kg | 1.0 | 34 | 0.6296 |

## Parameters

| id | term | unit | status | value (source, evidence class) | what closes it | milestone | analogues |
|---|---|---|---|---|---|---|---|
| `mdot_cathode` | m_cathode | mg/s | FIXED_DESIGN_TERM — A5 design target, not a demonstrated flow | 0.1 (docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json xe_mass_allocation.cathode_flow_design_target_mg_s (owner allocation: design target); assumed) | C-1 measured spot-mode minimum Xe flow at the required emission current, with the thruster magnetic field and an air-fed anode (cathode_integration tbd 'cathode_min_flow'; cathode dossier G06; A5 architecture-closing risk rank 3) | B | AN-01 |
| `t_firing` | m_cathode | h | FIXED — A5 books the cathode term over the RFP 15,000 firing hours | 15,000 (RFP '> 15,000 h firing' used as the minimum (abep_sim/constants.py RFPConstraints.ignition_hours; A5 xe_mass_allocation.reference_arithmetic_15000h); assumed) | fixed by A5/RFP; the owner may rebase it on the design-life target (OD-XE-5) | A | — |
| `N_starts` | m_startup | 1 | TBD — requires the mission operations concept (eclipse/duty cycling, anomaly restarts) and FDIR | — | operations concept + FDIR restart policy (cathode_integration tbd 'starts', milestone C); start-cycle qualification of C-1 (cathode dossier G05) | C | AN-04 |
| `t_startup` | m_startup | s | TBD — requires H-1/C-1 measurement of the start sequence (Xe-flowing preheat/conditioning + Xe discharge ignition dwell) | — | H-1/C-1 start-sequence test with Xe flow logged per phase | B | AN-03 |
| `mdot_startup` | m_startup | mg/s | TBD — requires H-1/C-1 measurement (time-averaged Xe flow over t_startup, per the accounting convention) | — | H-1/C-1 start-sequence test (integrated Xe per start = t_startup x mdot_startup) | B | AN-02 |
| `N_transitions` | m_transition | 1 | TBD — requires the operations concept (one per start plus one per recovery from Xe fallback) and FDIR | — | operations concept + FDIR | C | — |
| `t_transition` | m_transition | s | TBD — requires H-1 measurement of the Xe-to-atmosphere transfer ('brief transition support', A5) | — | H-1 Phase 1 transfer profile (no accessed source reports a transition duration) | B | AN-02 |
| `mdot_transition` | m_transition | mg/s | TBD — requires H-1 measurement (time-averaged Xe flow during the transfer) | — | H-1 Phase 1 transfer profile | B | AN-02 |
| `t_fallback_max` | m_fallback | h | TBD — requires the owner/FDIR maximum cumulative Xe-contingency duration (A5: every Xe-consuming mode carries an explicit maximum duration) | — | owner decision informed by sensitivity surface SS-3; FDIR design | B | — |
| `mdot_fallback` | m_fallback | mg/s | TBD — requires H-1 measurement of the Xe-fed discharge flow at the fallback operating point | — | H-1 Xe reference/fallback point on the H-1 accelerator | B | AN-02 |
| `reserve_policy` | m_reserve | 1 or kg | TBD — requires the owner's reserve policy: form (fraction_of_other_terms / absolute_mass) and value | — | owner decision OD-XE-2 | B | — |
| `tank_model` | m_tank | 1 or kg | TBD — requires procurement selection (supplier tank mass at the declared Xe load and MEOP) or a sourced tank sizing model (form tankage_fraction / tank_mass) | — | tank selection; mass_bom xe_tank item (G3 lower-bound relation thin_wall_sphere_min_mass_kg exists there for FAIL screening only) | B | AN-05 |
| `m_regulator` | hardware | kg | TBD — requires procurement selection (supplier mass of the selected part at the declared Xe load, MEOP and flow) | — | Xe regulator selection (upstream ICD gap G-12: no regulator model) | B | — |
| `m_valves` | hardware | kg | TBD — requires procurement selection (supplier mass of the selected part at the declared Xe load, MEOP and flow) | — | Xe isolation/metering valve selection (A5 Xe branch: metering splits to ignition/transition feed and cathode feed) | B | — |
| `m_plumbing` | hardware | kg | TBD — requires procurement selection (supplier mass of the selected part at the declared Xe load, MEOP and flow) | — | Xe feed-line layout (filters, lines, fittings, fill/drain, pressure transducers) | B | — |
| `m_mounting_thermal` | hardware | kg | TBD — requires procurement selection (supplier mass of the selected part at the declared Xe load, MEOP and flow) | — | tank mounts/brackets and Xe-path thermal hardware (heaters, insulation); boundary with mass_bom structure/thermal_hardware is OD-XE-7 | B | — |

## Ledger state today

m_cathode = 5.4 kg. The other terms, m_Xe_total and m_Xe_subsystem are **null (refused)**. There are 14 blocking inputs: `N_starts`, `t_startup`, `mdot_startup`, `N_transitions`, `t_transition`, `mdot_transition`, `t_fallback_max`, `mdot_fallback`, `reserve_policy`, `tank_model`, `m_regulator`, `m_valves`, `m_plumbing`, `m_mounting_thermal`.

REFUSED: m_Xe_subsystem is not closed, so no share of 40 / 36 / 34 kg is reported for it. Shares are reported for the fixed cathode term (cathode_term.design_term.shares) and, per scenario, for the propellant with the hardware headroom left inside each share (scenarios[*].results).

## Scenarios

*Label:* scenario / illustrative: not an allocation, not a prediction, not frozen (A6 not_authorized).

All scenarios use `PHASE_TOTAL_FLOW`, the A5 cathode design term and all three branches. Per-event Xe for SC-1 to SC-3 is derived below; each row gives its source and evidence class.

| quantity | value | unit | evidence class | source |
|---|---|---|---|---|
| t_preheat | 600 | s | measured | AN-03: HC1 preheat 'about 600 s at about 45 W' (docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json parameters.hc1_heating_time_s) |
| mdot during preheat/conditioning | 0.1 | mg/s | assumed | A5 cathode design target applied during conditioning (booking per docs/controls/DUAL_FEED_STATES.md CATHODE_CONDITIONING, a design proposal) |
| mdot at Xe discharge ignition | 11 | mg/s | measured | AN-02: E09 ignition 10 mg/s anode + 1 mg/s cathode Xe (docs/evidence/hall_sustainment/hall_sustainment_matrix.json E09, ANDREUSSI2022_IEPC435 p. 3; 5 kW class, out of the A5 power class) |
| t_ignition_dwell | 60 | s | assumed | scenario assumption of this ledger (no source fixes it; H-1/C-1 or the owner replaces it) |
| t_startup = t_preheat + t_ignition_dwell | 660 | s | model-derived | arithmetic on the rows above |
| Xe per start = t_preheat x mdot_pre + t_ign x mdot_ign | 0.72 | g | model-derived | arithmetic on the rows above |
| mdot_startup = Xe per start / t_startup (time average) | 1.091 | mg/s | model-derived | arithmetic on the rows above |
| t_transition | 60 | s | assumed | scenario assumption of this ledger (no source fixes it; H-1/C-1 or the owner replaces it) |
| mdot_transition = (mdot_ign + mdot_pre)/2 | 5.55 | mg/s | model-derived | linear ramp from the ignition flow to the A5 nominal cathode flow (ramp shape assumed) |
| Xe per transition | 0.333 | g | model-derived | arithmetic |

| id | name | N_starts | m_cathode | m_startup | m_transition | m_fallback | m_reserve | m_Xe_total (scenario) | share of 40 / 36 / 34 kg |
|---|---|---|---|---|---|---|---|---|---|
| SC-0 | `cathode_only_minimum` | 0 | 5.4 | 0 | 0 | 0 | 0 | 5.4 | 13.50 % / 15.00 % / 15.88 % |
| SC-1 | `nominal_restart` | 1,000 | 5.4 | 0.72 | 0.333 | 0 | 0.645 | 7.1 | 17.75 % / 19.72 % / 20.88 % |
| SC-2 | `heavy_restart` | 17,737 | 5.4 | 12.8 | 5.91 | 0 | 2.41 | 26.5 | 66.21 % / 73.57 % / 77.90 % |

- **SC-0 `cathode_only_minimum`**: Isolates the A5 fixed term: no start, transition, fallback or reserve. Not an operating scenario (at least one Xe start is needed); a floor under the A5 design target, not a lower bound on flight Xe.
- **SC-1 `nominal_restart`**: 1000 starts, each followed by one transfer; N anchored on the > 1000 heater starts demonstrated on the JPL H6 LaB6 cathode (AN-04: a demonstrated cycle count of another cathode, NOT a mission start count). Fallback evaluated separately (SC-3).
- **SC-2 `heavy_restart`**: One start per orbit over the whole mission (eclipse/duty cycling every orbit, assumed ops concept): N = floor(mission hours / orbital period at 180 km). Same per-event Xe as SC-1, so only N changes.
- **SC-3 `fallback_limited`**: SC-1 restarts plus the LONGEST cumulative Xe fallback the cap allows, at the E09 analogue flow (11 mg/s, out of power class). Regulator, valves, plumbing and mounting are set to 0 kg (bounding: a real part only shortens the allowance). The result is an upper bound on t_fallback_max for these inputs, never a frozen value; SS-3 covers other flows.

Hardware headroom is the largest tank + regulator + valves + plumbing + mounting/thermal mass that keeps the subsystem within the share. Hardware masses are TBD, and none is assumed.

| scenario | reference | share | cap (kg) | headroom (kg) | status |
|---|---|---|---|---|---|
| SC-0 | RFP_40kg | 0.25 | 10 | 4.6 | HEADROOM |
| SC-0 | RFP_40kg | 0.5 | 20 | 14.6 | HEADROOM |
| SC-0 | RFP_40kg | 1.0 | 40 | 34.6 | HEADROOM |
| SC-0 | A5_alloc_36kg | 0.25 | 9 | 3.6 | HEADROOM |
| SC-0 | A5_alloc_36kg | 0.5 | 18 | 12.6 | HEADROOM |
| SC-0 | A5_alloc_36kg | 1.0 | 36 | 30.6 | HEADROOM |
| SC-0 | A5_alloc_34kg | 0.25 | 8.5 | 3.1 | HEADROOM |
| SC-0 | A5_alloc_34kg | 0.5 | 17 | 11.6 | HEADROOM |
| SC-0 | A5_alloc_34kg | 1.0 | 34 | 28.6 | HEADROOM |
| SC-1 | RFP_40kg | 0.25 | 10 | 2.9 | HEADROOM |
| SC-1 | RFP_40kg | 0.5 | 20 | 12.9 | HEADROOM |
| SC-1 | RFP_40kg | 1.0 | 40 | 32.9 | HEADROOM |
| SC-1 | A5_alloc_36kg | 0.25 | 9 | 1.9 | HEADROOM |
| SC-1 | A5_alloc_36kg | 0.5 | 18 | 10.9 | HEADROOM |
| SC-1 | A5_alloc_36kg | 1.0 | 36 | 28.9 | HEADROOM |
| SC-1 | A5_alloc_34kg | 0.25 | 8.5 | 1.4 | HEADROOM |
| SC-1 | A5_alloc_34kg | 0.5 | 17 | 9.9 | HEADROOM |
| SC-1 | A5_alloc_34kg | 1.0 | 34 | 26.9 | HEADROOM |
| SC-2 | RFP_40kg | 0.25 | 10 | — | PROPELLANT_ALONE_EXCEEDS_SHARE |
| SC-2 | RFP_40kg | 0.5 | 20 | — | PROPELLANT_ALONE_EXCEEDS_SHARE |
| SC-2 | RFP_40kg | 1.0 | 40 | 13.5 | HEADROOM |
| SC-2 | A5_alloc_36kg | 0.25 | 9 | — | PROPELLANT_ALONE_EXCEEDS_SHARE |
| SC-2 | A5_alloc_36kg | 0.5 | 18 | — | PROPELLANT_ALONE_EXCEEDS_SHARE |
| SC-2 | A5_alloc_36kg | 1.0 | 36 | 9.52 | HEADROOM |
| SC-2 | A5_alloc_34kg | 0.25 | 8.5 | — | PROPELLANT_ALONE_EXCEEDS_SHARE |
| SC-2 | A5_alloc_34kg | 0.5 | 17 | — | PROPELLANT_ALONE_EXCEEDS_SHARE |
| SC-2 | A5_alloc_34kg | 1.0 | 34 | 7.52 | HEADROOM |

SC-3 `fallback_limited` gives the longest cumulative Xe fallback at 11 mg/s (E09 analogue), with SC-1 restarts, the SC-1 reserve and zero non-tank hardware. It is an upper bound for these inputs, never a frozen value.

| reference | share | cap (kg) | f_tank (axis) | status | t_fallback_max allowable (h) | Xe allowance (kg) |
|---|---|---|---|---|---|---|
| RFP_40kg | 0.25 | 10 | 0.0 | ALLOWANCE | 66.6 | 2.64 |
| RFP_40kg | 0.25 | 10 | 0.1 | ALLOWANCE | 45.7 | 1.81 |
| RFP_40kg | 0.25 | 10 | 0.25 | ALLOWANCE | 20.7 | 0.82 |
| RFP_40kg | 0.5 | 20 | 0.0 | ALLOWANCE | 296 | 11.7 |
| RFP_40kg | 0.5 | 20 | 0.1 | ALLOWANCE | 254 | 10.1 |
| RFP_40kg | 0.5 | 20 | 0.25 | ALLOWANCE | 204 | 8.09 |
| RFP_40kg | 1.0 | 40 | 0.0 | ALLOWANCE | 755 | 29.9 |
| RFP_40kg | 1.0 | 40 | 0.1 | ALLOWANCE | 672 | 26.6 |
| RFP_40kg | 1.0 | 40 | 0.25 | ALLOWANCE | 572 | 22.6 |
| A5_alloc_36kg | 0.25 | 9 | 0.0 | ALLOWANCE | 43.7 | 1.73 |
| A5_alloc_36kg | 0.25 | 9 | 0.1 | ALLOWANCE | 24.9 | 0.985 |
| A5_alloc_36kg | 0.25 | 9 | 0.25 | ALLOWANCE | 2.33 | 0.0925 |
| A5_alloc_36kg | 0.5 | 18 | 0.0 | ALLOWANCE | 250 | 9.91 |
| A5_alloc_36kg | 0.5 | 18 | 0.1 | ALLOWANCE | 213 | 8.42 |
| A5_alloc_36kg | 0.5 | 18 | 0.25 | ALLOWANCE | 168 | 6.64 |
| A5_alloc_36kg | 1.0 | 36 | 0.0 | ALLOWANCE | 663 | 26.3 |
| A5_alloc_36kg | 1.0 | 36 | 0.1 | ALLOWANCE | 588 | 23.3 |
| A5_alloc_36kg | 1.0 | 36 | 0.25 | ALLOWANCE | 498 | 19.7 |
| A5_alloc_34kg | 0.25 | 8.5 | 0.0 | ALLOWANCE | 32.2 | 1.27 |
| A5_alloc_34kg | 0.25 | 8.5 | 0.1 | ALLOWANCE | 14.4 | 0.572 |
| A5_alloc_34kg | 0.25 | 8.5 | 0.25 | EXCEEDED_WITHOUT_THIS_TERM | — | -0.271 |
| A5_alloc_34kg | 0.5 | 17 | 0.0 | ALLOWANCE | 227 | 9 |
| A5_alloc_34kg | 0.5 | 17 | 0.1 | ALLOWANCE | 192 | 7.6 |
| A5_alloc_34kg | 0.5 | 17 | 0.25 | ALLOWANCE | 149 | 5.91 |
| A5_alloc_34kg | 1.0 | 34 | 0.0 | ALLOWANCE | 618 | 24.5 |
| A5_alloc_34kg | 1.0 | 34 | 0.1 | ALLOWANCE | 547 | 21.6 |
| A5_alloc_34kg | 1.0 | 34 | 0.25 | ALLOWANCE | 461 | 18.3 |

Share axis: 0.25 = lane-19 PROPOSED 'dominance_fraction' (cathode_integration_data_v1.json proposed_thresholds.dominance_fraction; not in the RFP; owner decides); 0.5 = axis value; 1.0 = the whole reference (the subsystem can never exceed the whole system). The owner's share threshold is OD-XE-3 (PROPOSED).

## Sensitivity surfaces

### SS-1: Xe sum cap S_max and non-cathode headroom H
`S_max = (share x M - m_hw_nontank) / ((1 + f_tank) (1 + f_reserve));  H = S_max - m_cathode (tankage-fraction tank model, reserve as a fraction of the other four terms; other forms: abep_sim.xe_ledger.xe_sum_cap_kg)`

S_max = the largest m_cathode + m_startup + m_transition + m_fallback that keeps m_Xe_subsystem <= share x M. H = what remains for startup + transition + fallback after the cathode term (5.4 kg at 0.10 mg/s, 8.1 kg at 0.15 mg/s). Negative H: the cathode term with that tank, hardware and reserve already exceeds the cap.

The table below is a subset: no reserve, and the A5 34 kg allocation. All 243 rows are in the JSON.

| share | f_tank | m_hw non-tank (kg) | S_max (kg) | H at 0.10 mg/s (kg) | H at 0.15 mg/s (kg) |
|---|---|---|---|---|---|
| 0.25 | 0.0 | 0 | 8.5 | 3.1 | 0.4 |
| 0.25 | 0.0 | 2 | 6.5 | 1.1 | -1.6 |
| 0.25 | 0.0 | 4 | 4.5 | -0.9 | -3.6 |
| 0.25 | 0.1 | 0 | 7.73 | 2.33 | -0.373 |
| 0.25 | 0.1 | 2 | 5.91 | 0.509 | -2.19 |
| 0.25 | 0.1 | 4 | 4.09 | -1.31 | -4.01 |
| 0.25 | 0.25 | 0 | 6.8 | 1.4 | -1.3 |
| 0.25 | 0.25 | 2 | 5.2 | -0.2 | -2.9 |
| 0.25 | 0.25 | 4 | 3.6 | -1.8 | -4.5 |
| 0.5 | 0.0 | 0 | 17 | 11.6 | 8.9 |
| 0.5 | 0.0 | 2 | 15 | 9.6 | 6.9 |
| 0.5 | 0.0 | 4 | 13 | 7.6 | 4.9 |
| 0.5 | 0.1 | 0 | 15.5 | 10.1 | 7.35 |
| 0.5 | 0.1 | 2 | 13.6 | 8.24 | 5.54 |
| 0.5 | 0.1 | 4 | 11.8 | 6.42 | 3.72 |
| 0.5 | 0.25 | 0 | 13.6 | 8.2 | 5.5 |
| 0.5 | 0.25 | 2 | 12 | 6.6 | 3.9 |
| 0.5 | 0.25 | 4 | 10.4 | 5 | 2.3 |
| 1.0 | 0.0 | 0 | 34 | 28.6 | 25.9 |
| 1.0 | 0.0 | 2 | 32 | 26.6 | 23.9 |
| 1.0 | 0.0 | 4 | 30 | 24.6 | 21.9 |
| 1.0 | 0.1 | 0 | 30.9 | 25.5 | 22.8 |
| 1.0 | 0.1 | 2 | 29.1 | 23.7 | 21 |
| 1.0 | 0.1 | 4 | 27.3 | 21.9 | 19.2 |
| 1.0 | 0.25 | 0 | 27.2 | 21.8 | 19.1 |
| 1.0 | 0.25 | 2 | 25.6 | 20.2 | 17.5 |
| 1.0 | 0.25 | 4 | 24 | 18.6 | 15.9 |

*Axes:* sensitivity axis value (not evidence, not a threshold); f_tank = 0 and m_hw = 0 are bounding (physically unattainable) values.

### SS-2: maximum starts for a given headroom and Xe per start+transition cycle
`N_starts_max = floor(H_s / (t_startup mdot_startup + t_transition mdot_transition)), with N_transitions = N_starts and H_s = H - m_fallback`

SC-1 per-cycle Xe for reference: 1.053 g.

| H (kg) | 0.03 g/cycle | 0.1 g/cycle | 0.3 g/cycle | 1.0 g/cycle | 3.0 g/cycle |
|---|---|---|---|---|---|
| 0.5 | 16,666 | 5,000 | 1,666 | 500 | 166 |
| 1.0 | 33,333 | 10,000 | 3,333 | 1,000 | 333 |
| 2.0 | 66,666 | 20,000 | 6,666 | 2,000 | 666 |
| 4.0 | 133,333 | 40,000 | 13,333 | 4,000 | 1,333 |
| 8.0 | 266,666 | 80,000 | 26,666 | 8,000 | 2,666 |

*Axes:* sensitivity axis value (not evidence, not a threshold).

### SS-3: maximum cumulative Xe fallback duration for a given headroom and fallback flow
`t_fallback_max_allowable = H_f / mdot_fallback, with H_f = H - m_startup - m_transition; hours per kg = 277.78 / mdot_fallback[mg/s]`

| H (kg) | 0.5 mg/s | 1.0 mg/s | 2.0 mg/s | 5.0 mg/s | 11.0 mg/s |
|---|---|---|---|---|---|
| 0.5 | 278 h | 139 h | 69.4 h | 27.8 h | 12.6 h |
| 1.0 | 556 h | 278 h | 139 h | 55.6 h | 25.3 h |
| 2.0 | 1,111 h | 556 h | 278 h | 111 h | 50.5 h |
| 4.0 | 2,222 h | 1,111 h | 556 h | 222 h | 101 h |
| 8.0 | 4,444 h | 2,222 h | 1,111 h | 444 h | 202 h |

Hours of Xe-fed discharge per kg: 0.5 mg/s → 556 h; 1.0 mg/s → 278 h; 2.0 mg/s → 139 h; 5.0 mg/s → 55.6 h; 11.0 mg/s → 25.3 h

*Axes:* sensitivity axis value (not evidence, not a threshold); 11 mg/s = AN-02 E09 ignition flow (5 kW class, out of power class).

### SS-4: combined start / fallback trade line
`N_starts x (Xe per start+transition cycle) + t_fallback_max x mdot_fallback <= H  (linear; every point on the line spends the same headroom)`

exchange rate: fallback hours that cost the same Xe as 1000 start+transition cycles at the SC-1 per-cycle Xe (scenario value)

| ṁ_fallback (mg/s) | fallback hours ≡ 1000 cycles |
|---|---|
| 0.5 | 585 h |
| 1.0 | 292 h |
| 2.0 | 146 h |
| 5.0 | 58.5 h |
| 11.0 | 26.6 h |

*Axes:* sensitivity axis value (not evidence, not a threshold).

### SS-5: Xe-per-cycle ceiling for a planned number of start+transition cycles
`xe_per_cycle_max = H / N_cycles`

a candidate H-1/C-1 test requirement (PROPOSED, owner decides), not a prediction: the start and transfer Xe per cycle that the ops concept can afford

| H (kg) | N = 1,000 | N = 17,737 |
|---|---|---|
| 0.5 | 0.5 g | 0.0282 g |
| 1.0 | 1 g | 0.0564 g |
| 2.0 | 2 g | 0.113 g |
| 4.0 | 4 g | 0.226 g |
| 8.0 | 8 g | 0.451 g |

*Axes:* sensitivity axis value (not evidence, not a threshold); N = 1000 (SC-1) and the SC-2 per-orbit count.

## Illustrative analogues (never the allocation)

**AN-01 — cathode Xe flows of other cathodes (context for the fixed cathode term).** The A5 design target 0.10 mg/s sits at the low end of the developer design ranges (0.08 mg/s) and below every measured diode-mode minimum flow (0.6-0.8 mg/s). The veto layer carries this as RI-MASS-CATHODE-XE (straddles the 40 kg limit; not verdict-bearing). The 5.4 kg term therefore rests on a design target that C-1 must demonstrate.

| quantity | value | unit | evidence class (level) | source / pointer |
|---|---|---|---|---|
| P5 cathode Xe flow setpoint | 0.44 | mg/s | measured (3) | brabston_2025_repo (Brabston et al., JPP 2025, Tables 2/4, as frozen in the repository); `docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json parameters.p5_cathode_xe_flow_mg_s.value` |
| SITAEL HC1 design flow range | 0.08 – 0.5 | mg/s | measured (3) | pedrini_2017_iepc365 (IEPC-2017-365), abstract p. 1 and Sec. IV.A p. 5; `docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json parameters.hc1_design_flow_range_mg_s.value` |
| SITAEL HC3 design flow range | 0.08 – 1 | mg/s | measured (3) | pedrini_2017_iepc365, Sec. V p. 8 (abstract states 0.08-0.5; inconsistency kept); `docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json parameters.hc3_design_flow_range_mg_s.value` |
| HC3 minimum spot-mode flow (diode, 2.5-4 A) | 0.6 | mg/s | measured (3) | pedrini_2017_iepc365, Sec. V p. 9; `docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json parameters.hc3_diode_spot_mode_min_flow_mg_s.value` |
| HC1 diode flow below which plume mode appeared | 0.8 | mg/s | measured (3) | pedrini_2017_iepc365, Sec. IV.B p. 7; `docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json parameters.hc1_diode_flow_mg_s.value` |

**AN-02 — Xe flow at discharge ignition (start-then-transition).** The only ignition Xe flows recorded in the base. The PPS1350 (E05/E06, ~1 kW class, the closest class) also ignited on Xe and then transitioned the anode to N2 or N2/O2 (CIFALI2011 p. 2), but the Xe flow and the duration of the Xe phase are not reported in the accessed text. No accessed source reports an ignition dwell or a transition duration.

| quantity | value | unit | evidence class (level) | source / pointer |
|---|---|---|---|---|
| HT5k DM2 ignition: anode Xe | 10 | mg/s | measured (3) | ANDREUSSI2022_IEPC435 (IEPC-2022-435) p. 3; `docs/evidence/hall_sustainment/hall_sustainment_matrix.json entries[id=E09].ignition.statement` |
| HT5k DM2 ignition: cathode Xe | 1 | mg/s | measured (3) | ANDREUSSI2022_IEPC435 p. 3; `docs/evidence/hall_sustainment/hall_sustainment_matrix.json entries[id=E09].ignition.statement` |

**AN-03 — cathode preheat durations (start sequence).** Heater durations, not Xe quantities: whether and how much Xe flows during preheat is not stated in these sources. The repository dual-feed state machine (docs/controls/DUAL_FEED_STATES.md, CATHODE_CONDITIONING) books mdot_Xe_cathode during conditioning; that is a design proposal, not evidence.

| quantity | value | unit | evidence class (level) | source / pointer |
|---|---|---|---|---|
| HC1 preheat to ~1460 K | 600 (at ~45 W) / 200 (at ~60 W) | s | measured (3) | pedrini_2017_iepc365, Sec. IV.A p. 5; `docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json parameters.hc1_heating_time_s.value` |
| JPL 1.5-cm LaB6 preheat | 18 – 20 | min | measured (3) | goebel_2017_iepc276 (IEPC-2017-276) p. 3; `docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json parameters.jpl_1p5cm_preheat_min.value` |

**AN-04 — demonstrated start/ignition counts of other cathodes.** Qualification-type cycle counts of other hardware, not mission start counts. The mission start count comes from the operations concept (cathode_integration tbd 'starts', milestone C); the start-cycle qualification is cathode dossier gap G05.

| quantity | value | unit | evidence class (level) | source / pointer |
|---|---|---|---|---|
| JPL H6 LaB6 cathode heater starts (lower bound) | 1,000 | 1 | measured (3) | goebel_polk_2015_iepc43 (IEPC-2015-43) Sec. 4 p. 3 ('over 1000 starts to date'); `docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json parameters.jpl_h6_heater_starts_min.value` |
| SITAEL HC1 ignitions | 120-ignition test and > 350 ignitions | 1 | measured (3) | pedrini_2017_iepc365 Sec. IV.B pp. 6-7; `docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json parameters.hc1_ignition_keeper_voltage_V.validation_status` |
| heaterless LaB6 ignitions | 25,000 (title only, verify) | 1 | measured (5) | cathode dossier (title-level record; primary not read); `docs/evidence/cathode/CATHODE_DOSSIER.md section 3.1 'A heaterless design reports 25,000 ignitions (title only, verify)'` |

**AN-05 — Xe tank mass vs Xe capacity (tankage fraction).** OUT OF APPLICABILITY: these tanks carry 516-1548 kg Xe, 30-300 times the Xe loads in this ledger. On this one family the fraction rises as the tank shrinks (0.085 at 300 L vs < 0.067 at 900 L), so it is not transferable to a ~5-30 kg load. Scale context only; the tank mass stays TBD (procurement selection).

| quantity | value | unit | evidence class (level) | source / pointer |
|---|---|---|---|---|
| ESA L-XTA 300 L: tank mass | 44 | kg | measured (5) | https://resilience.esa.int/archives/projects/l-xta-large-xenon-tank-assembly; `web: see source` |
| ESA L-XTA 300 L: Xe carried | 516 | kg | measured (5) | https://resilience.esa.int/archives/projects/l-xta-large-xenon-tank-assembly; `web: see source` |
| ESA L-XTA 900 L: empty tank mass (upper bound) | < 104 | kg | measured (5) | https://resilience.esa.int/archives/projects/l-xta-large-xenon-tank-assembly; `web` |
| ESA L-XTA 900 L: Xe carried | 1,548 | kg | measured (5) | https://resilience.esa.int/archives/projects/l-xta-large-xenon-tank-assembly; `web` |
| tankage fraction, 300 L | 0.0853 | 1 | inferred (5) | https://resilience.esa.int/archives/projects/l-xta-large-xenon-tank-assembly; `derived here` |
| tankage fraction, 900 L (upper bound) | < 0.0671835 | 1 | inferred (5) | https://resilience.esa.int/archives/projects/l-xta-large-xenon-tank-assembly; `derived` |

Source: ESA, 'L-XTA - Large Xenon Tank Assembly' project page (status date 02/09/2021), <https://resilience.esa.int/archives/projects/l-xta-large-xenon-tank-assembly> (open web page (project summary), accessed 2026-09-27).

## Open owner decisions

- **OD-XE-1** (accounting convention of the phase terms): PHASE_TOTAL_FLOW (conservative: overlap with t_firing books the cathode flow twice, at most mdot_cathode x overlap hours); every scenario declares it explicitly
- **OD-XE-2** (reserve policy (form and value)): none; the reserve is always its own term (A6); scenarios use explicit assumed values
- **OD-XE-3** (share of the mass reference the stored-Xe subsystem may take): PROPOSED screening level 0.25 (lane-19 dominance_fraction); the surfaces carry 0.25 / 0.5 / 1.0
- **OD-XE-4** (residual (unusable) Xe): A5/A6 define no residual term. docs/architecture_comparison/mass_bom/MASS_BOM.md books xe_residual = 0.02 x xe_load (ESA R-M1-6, a margin policy) as its own propellant item. The owner decides whether it enters this ledger as a separate term in a revision or stays in mass_bom only; it is never folded silently into m_reserve or any other term, and it must not be booked twice.
- **OD-XE-5** (firing-hours basis of the cathode term): A5 fixes 15,000 h (5.4 kg at 0.10 mg/s); the A5 internal design life target of 18,000 h would give 6.48 kg (sensitivity only)
- **OD-XE-6** (RFP 'air + Xe' Xe-mode operation): The hard-gate matrix carries G7.xenon_operation and a 25 mN peak with Xe (OD1 reading ii). If the RFP requires Xe-mode operation for a duration that consumes stored Xe beyond ignition, cathode and contingency, it becomes a new explicit ledger term (owner decision); it is never folded into m_fallback.
- **OD-XE-7** (hardware boundary with mass_bom): m_regulator / m_valves / m_plumbing map to mass_bom xe_valve_and_flow_control, m_tank to xe_tank, m_mounting_thermal to parts of structure and thermal_hardware (PROPOSED mapping). Hardware inputs here are margin-free (CBE) unless their source says otherwise; MGA and system margin stay in mass_bom (G3 roll-up).
- **OD-XE-8** (whether the 40 kg includes the Xe load): mass_bom OD-M7: included as propellant (R3 as recorded; verify against the RFP). This ledger reports shares of 40 kg on that reading.

## A6 `not_authorized`: how it is respected

- *freezing total Xe mass*: ledger_state.m_Xe_total_kg is null (REFUSED); scenario totals carry the label 'scenario / illustrative' and are never an allocation.
- *freezing startup/transition/fallback quantities without evidence*: all eight inputs are TBD in the parameter table; scenario values are labelled assumptions or analogues.
- *freezing Phase-1 numeric thresholds*: not touched (the share axis is PROPOSED for the owner; no Phase-1 threshold is set).
- *changing Bundle 1 from NO_BASELINE_YET*: not touched; Bundle 1 stays NO_BASELINE_YET.
- *further broad Hall-transport sensitivity research*: none; no Hall closure enters the Xe path.
- *another facility simulation campaign*: none.

## Milestone statement
- **A (supported):** Conditional-selection support: one Xe ledger and stored-Xe subsystem structure common to hall_only, rf_hall and ecr_hall, with the conditions (surfaces SS-1..SS-5) under which the stored-Xe subsystem stays within a stated share of the 40 kg requirement or the A5 34-36 kg allocation. No total is frozen; Bundle 1 stays NO_BASELINE_YET.
- **To reach B:** C-1 measured cathode flow at <= 0.10 mg/s (or the owner re-books the term); H-1/C-1 measured Xe per start and per transfer and the Xe-fallback flow; owner reserve policy and share (OD-XE-2/3); tank, regulator, valves and plumbing selected with supplier masses.
- **To reach C:** operations concept (N_starts, N_transitions), FDIR maximum fallback duration, qualified hardware masses, cathode start-cycle qualification (dossier G05) and integrated mass closure through mass_bom (MGA, system margin, residual per OD-XE-4).

## Scope and neutrality
- COMMON_MODE: hall_only, rf_hall and ecr_hall draw on the one A5 Xe allocation with the same ledger. A branch can modulate the ledger only through measured per-event startup/transition Xe (e.g. whether a pre-ionizer changes the Xe ignition need): TBD, H-1 Phase 1. Nothing here ranks or eliminates a branch.
- The Xe path is upstream of the discharge: no Hall-transport closure, ensemble member, screening candidate or P5 calibration-nuisance variable enters it (abep_sim.xe_ledger.reject_forbidden_keys). Credible set: empty.

## Reproduction
`python docs/budgets/xe_ledger/build_xe_ledger.py` rewrites both files. `--check` exits 1 unless both are reproduced byte for byte. The run is deterministic, uses the standard library only and takes well under a second. Base commit: `302e1c94b3bddeb005f17bb189407f2e4641519a`.
