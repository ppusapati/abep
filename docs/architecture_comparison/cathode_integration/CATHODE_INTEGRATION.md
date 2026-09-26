# Cathode / neutralizer system integration: Hall-only, RF + Hall, ECR + Hall (CATHINT, lane 19)

| | |
|---|---|
| status | **DRAFT for the owner.** Integration relations and conditional statements. No Hall prediction, no operating point, no architecture ranking |
| module | [`abep_sim/cathode_integration.py`](../../../abep_sim/cathode_integration.py): pure, explicit inputs, no defaults, not wired into `archengine` |
| sourced data | [`cathode_integration_data_v1.json`](cathode_integration_data_v1.json): every value has a source, locator, evidence level, quantity type, uncertainty, applicability, validation status and transformation chain |
| derived statements | [`cathode_integration_derived_v1.json`](cathode_integration_derived_v1.json), written by [`derive_cathode_integration_v1.py`](derive_cathode_integration_v1.py) (`--check` reproduces it byte for byte) |
| test | `tests/test_cathode_integration.py`: hand calculations, current conservation, refusal paths, data-file validation |
| cathode evidence authority | `docs/evidence/cathode/` (cathode dossier lane; read-only, referenced, not duplicated; see section 9) |
| bus boundary | `bus_power_boundary_v1` (`abep_sim/arch_boundary.py`, another lane): this lane books **load-side** power on `cathode_keeper` and `cathode_heater` |
| milestone support | **A** (conditional selection) now. What B and C need: section 11 |
| base commit | `c53b75a` |

Architectures use the ids `hall_only`, `rf_hall` and `ecr_hall`. The RF and ECR arms change only the pre-ionization.
The Hall accelerator, feed state, cathode and bus boundary are common. The cathode is a Xe-fed LaB6 hollow cathode, as
in the RFP context (air + Xe, Hall preferred). The dossier covers alternative cathodes as evidence only; this lane adds
no propulsion family.

Gate 3 is FAIL and the credible transport set is ∅, so no discharge current I_d or beam current I_beam is available for
any Vyovrinda operating point. Every statement below is therefore of the form **"IF these inputs, THEN this cathode
consequence"**. Screening candidates (`sgb-screen-*`) are refused as a source of I_d, and so is any closure that has not
been admitted. The refusal is enforced by `evaluate_architecture` through `hall_ensemble.require_admitted`.

## 1. What the module computes

`evaluate_architecture(arch, CathodeIntegrationInputs)` returns, for one architecture:

| output | relation | source of the relation |
|---|---|---|
| electron current: `I_emit`, plume neutralization, keeper, interstage | Kirchhoff: `I_emit = I_d + I_keeper + I_interstage`, with `I_beam <= I_d + I_interstage` | Goebel & Katz 2008, Eqs. 7.2-24 to 7.2-26, p. 339 (+ circuit identity) |
| Hall-closure-free `I_d` envelope | `(T²/(2ṁ) − P_other)/V_d <= I_d <= P_avail/V_d`, i.e. total efficiency <= 1 | G&K Eq. 7.3-3, p. 341 (rearranged) |
| cathode Xe flow and mission Xe mass | `m = ṁ_c t_fire + ṁ_ign t_ign N_starts + ṁ_sb t_sb` | mass balance; flow split G&K Eqs. 7.3-4/5, pp. 341-342 |
| steady load-side power on `cathode_keeper` and `cathode_heater` | `P_k = I_k V_k` if the keeper is on, else 0; heater power as declared | G&K Eq. 7.3-6, p. 342; Sec. 7.2.3, p. 337 |
| start-up bus-power transient | piecewise-constant phases on the boundary components: peak, duration, energy, cathode share | phase order: IEPC-2017-276 pp. 3-4, IEPC-2015-43 p. 4, G&K p. 337 |
| emitter temperature and evaporation-limited life | Richardson-Dushman `J = A T² exp(−e(φ0+αT)/kT)`; Lafferty `W = 10^(C−B/T)/√T`; life `= ρ w / (W(T+ΔT)(1−f_redep))` | G&K Eqs. 6.3-1..3, p. 251, Table 6-1 p. 252; IEPC-2017-276 Eq. 2, p. 5; G&K Sec. 6.8.4 pp. 302-303 |
| O2 poisoning screen | lookup against the reported LaB6 O2 statements at the coldest emitter region | G&K Sec. 6.8.5, pp. 304-306 |

Every scenario input is a `Sourced(value, unit, source, evidence_class)`. A quantity that is genuinely unknown is passed
as `TBD("requires …")`, and only where the output can carry the gap: the `I_d` envelope and the emitter O2 pressure.
Anywhere else a TBD raises. The result lists every input with its evidence class, the `assumed` inputs and the TBD
inputs. It sets `milestone_support` to `["A"]` unless the basis is an admitted closure or a hardware measurement and no
input is assumed or TBD.

`compare_architectures(results, rel_tol, xe_budget_kg, bus_power_limit_W, dominance_fraction)` puts the three results
side by side and reports which quantities differ. It flags a quantity as "could dominate" when it exceeds a fraction of
its budget, and it labels a flag held by all three architectures **common-mode, not a discriminator**. It never ranks
(`ranking: None`). The thresholds are explicit inputs; the data file carries **PROPOSED** values for the owner.

## 2. Electron-current requirement

**The Hall cathode emits the discharge current, and beam neutralization is inside it.** The discharge-supply current is
essentially the cathode's electron emission: I_d = I_e + I_ic ≈ I_e (G&K Eq. 7.2-25, p. 339). The beam leaves charge
neutral. Of the emitted current, I_beam neutralizes the plume and I_d − I_beam crosses into the channel. A Hall cathode
never has to supply I_d + I_beam; that sum would count the neutralizing electrons twice.

The module states the budget as current continuity at the plasma. The conventional currents into the plasma from the
anode (+I_d), a powered keeper (+I_k), an interstage electrode (+I_x) and the cathode (−I_emit) sum to zero, and the
plume carries no net current. Hence:

```
I_emit = I_d + I_k + I_x          and          I_beam <= I_d + I_x   (else refused: the plume could not be current-free)
```

| architecture | I_x (interstage) | when the cathode requirement differs from `hall_only` |
|---|---|---|
| `hall_only` | none; an interstage input is refused | reference |
| `rf_hall`, `ecr_hall` | **topology must be declared.** `floating`: 0 by Kirchhoff. `discharge_circuit_referenced`: already inside the measured I_d. `separately_biased`: the net electron current it collects, which must be given | (a) I_d at the operating point differs (Hall block, TBD); (b) a separately biased pre-ionizer electrode returns current to cathode common; (c) the keeper must stay on because I_d is below the cathode's self-heating current (section 4) |

Ions made in the pre-ionizer leave in the beam. Their electrons reach the anode, so they are inside I_d, or they reach
a floating wall that draws no net current. Neither case changes I_emit for a given I_d. The RAM-HET double-stage test
(Andreussi et al. IEPC-2017-377, p. 7) had two current-limited supplies, 1 A ionization and 3.7 A acceleration. The text
read does not say where the first-stage current returns. If it returns through cathode common, it is an I_x term.

**Envelope without a Hall closure.** Total efficiency cannot exceed 1: T² <= 2 ṁ P_in (G&K Eq. 7.3-3, p. 341), with
P_in = I_d V_d + P_other. That gives `I_d >= (T²/(2ṁ) − P_other)/V_d`, and power gives `I_d <= P_avail/V_d`. An
operating point outside this envelope is refused. At a fixed bus limit a pre-ionizer lowers P_avail. Its power can also
end up in the jet, which raises P_other. **IF** V_d, ṁ and the bus split are equal, **THEN** both bounds on the cathode
current are lower for `rf_hall`/`ecr_hall` than for `hall_only`. V_d, ṁ and the split are design inputs (TBD), so no
number is given.

## 3. Xe flow and mission Xe mass

Cathode Xe is injected outside the channel's ionization region and is "largely lost" to thrust (G&K p. 341). The mass
is set by the cathode's flow, not by the anode gas. The Xe-thruster rule "cathode flow 7–10 % of anode flow"
(IEPC-2017-365 p. 2, citing Goebel, Jameson & Hofer 2012) is recorded but **not transferable** to an air-fed anode. The
module accepts it only as an explicit bookkeeping law (`fraction_of_anode_flow`).

From the RFP values alone, a constant cathode flow of **0.7407 mg/s uses the entire 40 kg system-mass limit in the
15,000 h minimum firing**. A fraction f of the limit corresponds to f × 0.7407 mg/s. Reference flows from the sources,
evaluated by the derive script:

| reference flow (source, evidence) | mg/s | Xe over 15,000 h | share of 40 kg | if also flowing the 11,000 non-firing h |
|---|---|---|---|---|
| P5 setpoint at I_d 7.4–17.4 A (Brabston 2025 Tables 2/4, measured; dossier `sys.p5.cathode_xe_flow`) | 0.44 | 23.76 kg | 59.4 % | 41.18 kg |
| SITAEL HC1/HC3 design range, low end (IEPC-2017-365, developer statement) | 0.08 | 4.32 kg | 10.8 % | 7.49 kg |
| HC3 150 h endurance at 4 A, diode (p. 9, measured) | 0.5 | 27.00 kg | 67.5 % | 46.80 kg |
| HC3 **minimum for spot mode** at 2.5–4 A, diode, floating keeper (p. 9, measured) | 0.6 | 32.40 kg | 81.0 % | 56.16 kg |
| HC1 diode at 1.25–1.5 A; plume mode below this (p. 7, measured) | 0.8 | 43.20 kg | 108 % | 74.88 kg |
| HC3 design range, high end (p. 8; the abstract says 0.5) | 1.0 | 54.00 kg | 135 % | 93.60 kg |

Conditional statements:
- **IF** the cathode needs the flow its class needed in diode tests (0.6 mg/s at 2.5–4 A for HC3), **THEN** cathode Xe
  alone is about 81 % of the 40 kg system limit. That excludes the tank, any anode Xe and any Xe used for thruster
  ignition. The flag would hold in every architecture: **common-mode**, not a discriminator.
- **IF** the cathode holds spot mode near the low end of the developer ranges (≈ 0.08 mg/s) with the thruster's magnetic
  field and an air-fed anode, **THEN** cathode Xe is about 11 % of the limit. The accessed sources do not demonstrate
  such a flow at multi-ampere current in a thruster (dossier U16, G06).
- **IF** the cathode must keep flowing between firings, for example to shield the emitter, **THEN** multiply by
  26,000/15,000 = 1.73.
- **Where it can discriminate.** Too low a flow at a given emission current drives a hollow cathode into plume mode (G&K
  p. 311). The minimum flow therefore rises with I_emit. **IF** an architecture needs a lower I_emit for the same thrust
  and the selected cathode's ṁ_c,min(I) curve is known, **THEN** its cathode Xe can be lower. Both inputs are TBD
  (admitted Hall closure; measured ṁ_c,min(I)).
- Higher cathode flow also lowers the coupling voltage (G&K p. 311). The coupling voltage, about 20 V (G&K p. 339),
  comes off the beam voltage. The flow therefore trades against Hall performance as well as Xe mass. This lane records
  the coupling but does not quantify it.

Flow unit conversion: 1 sccm Xe = 0.0983009 mg/s = 0.0722399 A-equivalent (G&K Appendix B, Eq. B-5, p. 464).

## 4. Heater and keeper power at the bus boundary

**Steady state.** Hollow cathodes self-heat: the heater is switched off once the discharge supply is on. The keeper is
normally used only during start-up, so P_k is normally zero in operation (G&K p. 337, Eq. 7.3-6 p. 342). Both steady
loads are therefore explicit inputs that may be 0 W. The cathode is not always self-heating at low current:

| evidence | value | locator |
|---|---|---|
| 1.5-cm LaB6 (sized for 7.5–40 A) | stable without keeper down to 7.5 A; below 5 A it stopped unless the keeper ran > 2 A | IEPC-2015-43 pp. 4-5 |
| SITAEL HC1 on a 100 W Hall thruster (MSHT100) | 350 h endurance **with keeper current 0.5 A** | IEPC-2017-365 p. 8 |
| keeper-only operation (keeper as the only anode) | HC1 9–20 W at 0.3–1.5 A; HC3 25–60 W at 14–35 V | IEPC-2017-365 pp. 7-8 |

**IF** the discharge current of an architecture falls below the self-heating current of the selected cathode, **THEN** a
steady `cathode_keeper` load P_k = I_k V_k is charged to that architecture and I_k is added to I_emit. At a fixed bus
limit the pre-ionized architectures leave less power for the discharge, so they reach this condition first. The
self-heating current of the selected cathode is TBD (dossier G01).

**Start-up.** Reported heater power and keeper ignition levels: LaB6 needs a hotter preheat than BaO-W.

| cathode (source) | heater | preheat | keeper at ignition |
|---|---|---|---|
| SITAEL HC1, 0.3–1 A (IEPC-2017-365 pp. 5-7) | about 45 W / about 60 W | about 600 s / about 200 s to an emitter of about 1460 K | 45–50 V with the 45 W heater; up to 800 V heaterless (1 mg/s) |
| SITAEL HC3, 1–3 A (p. 8) | about 60 W | not stated | < 300 V at 0.4–0.8 mg/s; heaterless up to 700 V at 1–2 mg/s |
| JPL 0.63-cm LaB6, H6 (IEPC-2015-43 p. 3) | 120 W routinely, > 1000 starts | not stated | not stated |
| JPL 1.5-cm LaB6 (IEPC-2017-276 p. 3; IEPC-2015-43 p. 4) | up to 300 W capability, 13 A heater current | 18–20 min | 150 V applied, current regulated to 2 A, then 5–15 V; keeper off above 10 A anode current |
| further LaB6 points (Joussot 184.5 W; Zschätzsch up to 400 W) | see the dossier, `lab6.start.*` | | |

Derived energies (SITAEL HC1 pairs): **7.50 Wh per start at 45 W × 600 s** and **3.33 Wh at 60 W × 200 s** on
`cathode_heater`. The mission total scales with the number of starts. That number depends on the operations concept
(eclipse and duty cycling) and is TBD (dossier U15, G05).

## 5. Emitter temperature and insert life

The required current density is J = I_emit / A_emit. Tabulated points use the current densities that the sources quote
(G&K pp. 254 and 306). No Vyovrinda value is implied.

| J (A/cm²) | T, Lafferty A = 29, φ = 2.67 eV | T, G&K Table 6-1 A = 120, φ = 2.66 + 1.23e-4 T | Lafferty evaporation | evaporated in 15,000 h, no redeposition |
|---|---|---|---|---|
| 5 | 1844.5 K | 1839.1 K | 2.45e-9 g cm⁻² s⁻¹ | 0.132 g/cm² |
| 10 | 1915.0 K | 1909.4 K | 1.31e-8 g cm⁻² s⁻¹ | 0.706 g/cm² |

- Consistency check: the Lafferty constants give 10.8 A/cm² at 1650 °C. That agrees with the source statement "over
  10 A/cm² at 1650 °C" (G&K p. 254).
- **IF** a uniform insert emits J over the 15,000 h minimum firing, **THEN** its usable areal mass (density × usable
  thickness) must exceed the evaporated mass in the table. Density, usable thickness and emitting area are hardware
  inputs (TBD). Doubling J from 5 to 10 A/cm² raises the evaporated mass 5.3×.
- The life estimate uses constant temperature and constant area. That is conservative against bore growth (G&K
  pp. 302-303) but not against axial temperature peaking: the non-uniform profile of a 3-mm orifice shortened the
  projected life of a 1.5-cm cathode to > 50 kh, against > 100 kh with a 5-mm orifice (IEPC-2017-276 pp. 7-8). The
  module therefore evaluates evaporation at T_uniform + ΔT_peak, with ΔT_peak an explicit input.
- IEPC-2017-276 (pp. 6-7) inferred that 60 % of the evaporated material is redeposited. That comes from one 4000 h wear
  test of a 1.5-cm cathode at 25 A; it is recorded, not transferred. The module takes `redeposition_fraction`
  explicitly, and 0 is the conservative value.
- Life margin = life / required firing hours. A PROPOSED minimum (1.5×, not in the RFP) waits for the owner.
- Architecture difference: only through I_emit, since the emitter is common. **IF** an architecture needs a higher
  I_emit, **THEN** its emitter runs hotter and its life falls steeply.

## 6. Poisoning and contamination: O, O2, N2 and ambient atomic oxygen

The screen evaluates the O2 partial pressure at the emitter at the **coldest** emitter region, T_uniform − ΔT_cold, an
explicit input. Cooler regions accumulate contaminants and raise the work function (Suzuki et al. 2024, abstract via
Crossref).

| evidence point (G&K Sec. 6.8.5, from Goebel, Watkins & Jameson 2007; dossier ref) | condition | status |
|---|---|---|
| O2 "in the 1e-5 torr range" degrades LaB6 emission below 1440 °C (`lab6.env.o2_degrade_1e-5`) | T <= 1713.15 K and p_O2 >= 1e-5 Torr (lower edge of the decade, the conservative reading) | IN_REPORTED_DEGRADATION_RANGE |
| the same sentence read as "below that range, no degradation"; higher T tolerates more (**inferred** by this lane) | T >= 1713.15 K and p_O2 < 1e-5 Torr | WITHIN_REPORTED_NO_DEGRADATION |
| LaB6 at 1570 °C withstands O2 "up to 1e-4 torr" without degradation (`lab6.env.o2_withstand_1570C`) | T >= 1843.15 K and p_O2 <= 1e-4 Torr | WITHIN_REPORTED_NO_DEGRADATION |
| anything else | | NO_EVIDENCE_AT_THIS_STATE |

- **Atomic O and N2: `NO_QUANTITATIVE_EVIDENCE`.** No accessed source gives a LaB6 threshold for either (dossier U04,
  U05; tests G02, G03). IEPC-2017-276 (p. 2) states only that LaB6 cathodes have been used in O2 and N2 plasma
  discharges above 20 A/cm², and that an 1800 h run with 10 ppm O2 in the Xe feed was normal. The internal pressure is
  not given, so no partial pressure follows.
- **Scale of the ambient atomic oxygen** (frozen NRLMSIS 2.1, ram-facing external surface, directed flux; expressed as
  the pressure of a 300 K gas with the same one-sided flux, with 300 K an **assumed** diode-test gas temperature):

  | altitude | solar low | mean | high |
  |---|---|---|---|
  | 180 km | 7.6e-6 Torr | 1.17e-5 Torr | 1.65e-5 Torr |
  | 230 km | 2.1e-6 Torr | 4.1e-6 Torr | 6.5e-6 Torr |

  These are atomic O and are **not** compared with the O2 thresholds. They show that the direct AO flux is of the same
  order as the pressures at which O2 affects LaB6. The attenuation by the cathode Xe flow, orifice and keeper therefore
  decides the emitter environment. That attenuation has no source (TBD, dossier U03). `required_attenuation(p_ext,
  p_tol)` gives the factor once a tolerated value exists.
- **Plume back-flow.** Unionized air leaving the channel reaches the cathode. **IF** a pre-ionizer dissociates O2 so that
  the back-flow carries more atomic O, **THEN** the cathode environment differs between architectures. No model or
  measurement of this exists here (TBD). The experiment protocol holds the cathode invariant between arms (INV-CATH), so
  a measured difference would isolate this effect.
- **Poisoning couples to Xe consumption.** A contaminated emitter enlarged the plume-mode region (Suzuki et al. 2024).
  **IF** poisoning raises the spot-mode minimum flow, **THEN** the Xe mass of section 3 rises with it.
- The dossier holds further exposure evidence (`lab6.env.o2_plasma_background`, `lab6.claim.temperature_margin`, the
  air-exposure and purity statements). The only adverse air-in-feed datum, a LaB6 cathode with up to 12 % air in the Xe
  feed, is secondary. The RAM-HET cathode (Kaufman & Robinson SHC 1000) could not be ignited after two days of N2/O2
  testing, and its emitter was damaged. The accessed text lists "no insulation between keeper and emitter" and does not
  attribute the failure to poisoning (IEPC-2017-377 pp. 7-8).

## 7. Start-up sequence per architecture and bus-power transient

Phase order sourced for a Hall/LaB6 start (G&K p. 337; IEPC-2017-276 pp. 3-4; IEPC-2015-43 p. 4):

| phase | boundary components on | note |
|---|---|---|
| preheat | `cathode_heater`, `housekeeping` | emitter to emission temperature |
| cathode ignition | `cathode_heater`, `cathode_keeper`, `flow_control`, `housekeeping` | cathode Xe on; keeper voltage, then current regulation |
| discharge ignition | `hall_discharge`, `hall_magnet`, `cathode_keeper`, `flow_control`, `housekeeping` | heater off when the discharge starts |
| keeper off | `hall_discharge`, `hall_magnet`, `flow_control`, `compressor`, `thermal_control`, `housekeeping` | keeper off/floating at nominal current, unless below the self-heating current |

Open for ABEP: the order of magnet and discharge, and the anode gas at ignition. Cifali et al. 2011 always ignited the
PPS1350 on Xe before moving the anode to N2/O2 (dossier `sys.pps1350.claim`). **IF** that is adopted, **THEN** the
ignition anode Xe belongs to the Xe budget, not to the cathode.

Pre-ionized architectures (**PROPOSED** variants; no accessed source fixes where the pre-ionizer starts):

| architecture | V1: pre-ionizer after the discharge is established | V2: pre-ionizer before discharge ignition (seed hypothesis) |
|---|---|---|
| `rf_hall` | `rf_source` after keeper-off; never overlaps the heater | `rf_source` during cathode/discharge ignition |
| `ecr_hall` | `ecr_magnet`, then `ecr_source`, after keeper-off | `ecr_magnet` and `ecr_source` before discharge ignition |

The experiment-protocol draft orders ignition as heater → keeper → flows → pre-ionizer → discharge, which is V2. An
electromagnet ECR field is energized before `ecr_source`, since resonance needs the field. A permanent-magnet design
books `ecr_magnet` = 0 W.

`startup_transient(arch, phases)` refuses components outside the architecture's boundary. It also refuses an
`rf_hall`/`ecr_hall` start-up that never powers its pre-ionizer. It returns the peak and its phase, the duration, the
energy by component and the cathode share of the peak. **IF** the pre-ionizer overlaps the heater phase (V2 with the
heater still on), **THEN** the start-up peak of `rf_hall`/`ecr_hall` exceeds the Hall-only preheat level by the
pre-ionizer power. The cathode loads themselves are identical across architectures. Whether the RFP "< 1.5 kW" also
bounds transients is an owner interpretation (PROPOSED `startup_peak_limit`).

## 8. Does the cathode penalty differ between architectures, and when could it dominate?

| cathode quantity | differs between architectures only if … | could dominate if … |
|---|---|---|
| emission current I_emit | I_d differs (Hall closure, TBD), a separately biased interstage electrode exists, or the keeper must stay on | never on its own; it drives the rows below |
| cathode Xe flow and mass | the selected cathode's minimum spot-mode flow depends on I_emit and the architectures' I_emit differ, or poisoning differs | ṁ_c >= f × 0.7407 mg/s uses a fraction f of the 40 kg limit over 15,000 h. At the reported diode minimum for this current class (0.6 mg/s), f = 0.81. **Common-mode** unless ṁ_c,min(I) differs |
| steady keeper / heater power | I_d of an architecture drops below the self-heating current | P_k is comparable with the margin inside 1.5 kW; low-power Hall cathodes "can reach 20 %" of the available power (IEPC-2017-365 p. 2, secondary) |
| start-up peak and energy | the pre-ionizer is scheduled while the heater is on (V2) | the peak exceeds the bus limit (PROPOSED interpretation), or starts × Wh per start matters for the energy budget |
| insert life | I_emit differs (same emitter) | life margin < the PROPOSED 1.5× at the highest-I_emit architecture |
| poisoning | pre-ionizer dissociation changes the O content of the back-flow at the cathode | the emitter environment is in or beyond the O2 degradation range, or atomic-O evidence shows a lower threshold |

`compare_architectures` turns these into statements once the inputs exist. A flag present in all three architectures is
reported as common-mode.

## 9. Relation to the cathode evidence dossier

`docs/evidence/cathode/` (`CATHODE_DOSSIER.md`, `cathode_evidence_v1.json`) belongs to the cathode dossier lane. It was
read read-only in that lane's worktree on 2026-09-26 (dossier base `efc4a4e`). It is not in this lane's base commit.
It is the **evidence authority** for cathode candidates and alternatives, exposure statements, purity, system
precedents, the uncertainty register U01–U18, the hardware-test gaps G01–G10 and the leads not read. That includes the
2025 Vacuum study of O2 in a LaB6 cathode propellant (`lead.yang_2025`), which is directly relevant and must be read
before milestone B.

This lane does not repeat that material. Its data file keeps two kinds of value, both carrying `dossier_ref` where a
value overlaps:
- the values the module computes with: Lafferty Richardson constants, the O2 evidence points and the P5 flow;
- integration-specific values that the dossier does not hold: the Lafferty evaporation fit, SITAEL HC1/HC3 flows and
  heater powers, the JPL start-up procedure and self-heating limit, the Xe flow-unit conversion, the RAM-HET cathode
  report and the Suzuki 2024 abstract.

`cathode_dossier_path()` resolves the dossier lazily and raises if it is absent.

## 10. Interfaces to the other lanes

- **Bus boundary.** `abep_sim/arch_boundary.py`, `bus_power_boundary_v1`. `to_boundary_ledger(arch, cathode_loads,
  other_loads, efficiencies)` checks the following:
  - the cathode loads are exactly `cathode_keeper` and `cathode_heater`;
  - nothing is booked twice;
  - the union is the architecture's full component set.

  It then imports the boundary module lazily, checks its version and calls `ledger` (the naming contract) or, failing
  that, `bus_power_ledger` (the name that lane uses). A one-off check against that lane's module, run read-only and not
  committed, closed for all three architectures.
- **Upstream ICD.** In `schemas/interfaces/upstream_icd_v1.json`, `mdot_xe_kgps` is defined as "anode + cathode".
  `xe.cathode_flow_mg_s` is the cathode term.
- **Hall-map spec.** The Hall-map bridge models no cathode flow, so the cathode budget stays here.
- **Thermal/life framework.** `abep_sim/thermal_life.py` receives the heater and emitter temperature.
- **Experiment protocol.** INV-CATH keeps the cathode identical across arms. Each arm should also log I_beam and any
  interstage electrode current, so this current budget closes per arm.

## 11. Milestones

- **A, conditional selection: supported now.** These can be written into an "X is baseline provided …" statement:
  - (i) the cathode sustains the architecture's I_emit in spot mode at ṁ_c <= f × 0.7407 mg/s, where f is the share of
    the 40 kg limit the owner allots to cathode Xe;
  - (ii) the emitter O and O2 environment is demonstrated inside the no-degradation range, or an atomic-O threshold is
    measured;
  - (iii) the insert life is >= the PROPOSED margin × 15,000 h at the architecture's I_emit;
  - (iv) the start-up peak with the chosen pre-ionizer ordering stays within the bus limit;
  - (v) for `rf_hall`/`ecr_hall`, the interstage topology is floating or discharge-referenced, or its current is
    measured.
- **B, physics-backed selection: needs**
  - I_d and I_beam per architecture from an admitted closure or hardware;
  - the declared interstage topology and current;
  - the selected cathode, with its measured ṁ_c,min(I);
  - the atomic-O threshold and the emitter partial pressures (dossier G01, G02, G06);
  - the Vacuum 2025 lead read.
- **C, proposal/PDR freeze: needs**
  - the measured heater and keeper profile of the selected cathode;
  - start-cycle qualification (G05);
  - a wear/life test at the ABEP point (G04);
  - thermal integration;
  - mission Xe closure with the tank and ignition Xe.

## 12. Evidence handling and limits

- Sources read in full are listed with URL and sha256 in the data file:
  - Goebel & Katz 2008 (open JPL PDF);
  - IEPC-2017-276;
  - IEPC-2015-43;
  - IEPC-2017-365;
  - IEPC-2017-377;
  - the P5 values frozen in this repository.
- Primaries that are cited but were not read (Lafferty 1951, Gallagher 1969, Goebel/Watkins/Jameson 2007, Goebel/Jameson/
  Hofer 2012) supply no values. Their DOIs are copied from the reference lists of the papers that were read.
- Suzuki et al. 2024 was used from its Crossref abstract only, because the publisher page returned HTTP 403. Nothing was
  bypassed.
- No figure was digitized. Values are read from text and tables.
- The 300 K flux-equivalence temperature is **assumed**. The inferred O2 point is **inferred** by this lane, and the data
  file labels both as such.
- Thresholds that are not in the RFP carry status **PROPOSED**:
  - life margin 1.5×;
  - dominance fraction 0.25;
  - difference tolerance 1 %;
  - start-up peak limit;
  - start-cycle factor.
- Reproduce:

  ```
  python docs/architecture_comparison/cathode_integration/derive_cathode_integration_v1.py --check
  python -m pytest -q tests/test_cathode_integration.py
  ```
