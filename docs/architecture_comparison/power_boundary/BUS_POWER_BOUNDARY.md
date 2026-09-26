# Common bus-power boundary for Hall-only / RF+Hall / ECR+Hall — `bus_power_boundary_v1`

| item | value |
|---|---|
| module | `abep_sim/arch_boundary.py` (pure, standard library only, **not wired** into `archengine`) |
| schema | `schemas/architecture_comparison/bus_power_boundary_v1.json` (JSON Schema 2020-12: inputs and ledger) |
| tests | `tests/test_arch_boundary.py` |
| written against | commit `daa0e759e26416847f200a4781194f266be27c5c` (main after PR #30), 2026-09-26 |
| status | DRAFT for the owner. Accounting definition only: it makes no physics, transport or architecture claim |

**Scope.** This boundary accounts for electrical power. It does not rank architectures and it doesn't admit or reject
any Hall transport closure. Gate 3 stays FAIL and the credible transport set stays ∅. Every absolute Hall number remains
withdrawn (CLAUDE.md), so a harness that feeds Hall discharge loads from the superseded 0-D closure inherits that
withdrawal. The boundary only makes sure that, whatever loads are supplied, `hall_only`, `rf_hall` and `ecr_hall` are
charged on the same electrical boundary. No architecture can then be selected on discharge-only power.

## 1. Why one boundary

A pre-ionizer can lower the discharge power a Hall channel needs, but it draws power of its own through its own
conversion chain (RF generator or microwave source, HV supply, matching network, isolator, possibly a magnet). Comparing
architectures on discharge power, or on discharge plus the pre-ionizer's absorbed plasma power, would credit the
pre-ionized architectures with the conversion losses they cause. This boundary charges every architecture at the same
place, the spacecraft DC bus input to the propulsion subsystem. It uses the same eight common components and adds
exactly the pre-ionizer components.

## 2. The boundary

```
 spacecraft power system            | BOUNDARY: propulsion-subsystem DC bus input terminal(s)
 (arrays, battery, PCDU, bus        |   P_bus_W = Σ_components P_load / efficiency
  regulation, bus harness)          |
            OUTSIDE                 |   INSIDE: every conversion stage between the bus terminal and each
                                    |   component's load-side reference plane (converters, RF/microwave
                                    |   generators, HV supplies, magnet supplies, filters, matching networks,
                                    |   isolators, PPU-to-thruster harness)  ->  P_loss_W
                                    |   INSIDE: the loads themselves (discharge, coils, cathode, valves,
                                    |   compressor drive, heaters, controller, pre-ionizer coupling structure) -> P_load_W
```

**Outside (never booked here).** Solar arrays, batteries and their charge/discharge loss, spacecraft power conditioning
and distribution upstream of the propulsion input terminal, and spacecraft-level housekeeping (avionics, ADCS,
communications, payload). In the repository these upstream terms are `mission_env.Spacecraft.eps_eff` (battery/PCDU
round trip and distribution, `mission_env.py:33`) and `bus_housekeeping_W` (`mission_env.py:34`). The mission model adds
them on top of the propulsion bus draw (`mission_env.py:161`), which is consistent with this boundary.

**Several input buses.** A PPU may take power from more than one spacecraft bus. For example, Piñero et al. 2015 feed the
keeper and heater from the 28 V bus and the discharge from 120 V (§8, E2). The boundary is then the set of all
propulsion input terminals, and `P_bus_W` is the sum over them. Each component's efficiency is referenced to the bus
that feeds it.

**Operating mode.** A ledger describes one operating mode: steady firing, start-up, eclipse, Xe augmentation, and so on.
The component set is the same in every mode. Only the loads and efficiencies differ, and components that are off in a
mode are passed explicitly as 0 W. Architectures are compared mode by mode, never across modes.

**Load vs efficiency.** `P_load_W` is the time-averaged power delivered at the component's load-side reference plane
(§3). `efficiency` is the end-to-end ratio P_load / P_bus from the bus terminal to that plane, **at the operating
point**. It includes fixed overheads such as drive/bias/filament power, controller standby of that supply and part-load
penalties. A nameplate or peak efficiency applied at part load breaks the boundary. The module has no efficiency
maps. The caller evaluates the chain at the operating point and records its evidence (§8).

**v1 limitation.** Because `P_bus = P_load / efficiency`, a supply with zero delivered load draws zero bus power. Idle or
standby draw of a supply that delivers nothing in the evaluated mode (for example, a pre-ionizer HV supply held ready)
can't be represented on its own component in v1. It must be booked under `housekeeping` and declared. Whether v1.1
should add explicit standby terms is an open question (§9).

## 3. Components

`REQUIRED_COMPONENTS[arch] = COMMON_COMPONENTS + PREIONIZER_COMPONENTS[arch]`:

| architecture | components |
|---|---|
| `hall_only` | the eight common components |
| `rf_hall` | the eight common components + `rf_source` |
| `ecr_hall` | the eight common components + `ecr_source`, `ecr_magnet` |

| component | in | load-side reference plane (`P_load_W`) | inside the efficiency (bus → plane) | zero-power case |
|---|---|---|---|---|
| `hall_discharge` | all | anode–cathode terminals at the thruster, time-averaged V_d·I_d | bus input filter, discharge converter, output filter, harness | never 0 while firing |
| `hall_magnet` | all | Hall coil terminals (I²R). A coil in series with the discharge is booked here with its voltage drop × I_d, **not** under `hall_discharge` | magnet supply (or the discharge supply for a series coil), harness | permanent magnets: 0 W, efficiency 1, explicit |
| `cathode_keeper` | all | keeper (sustaining-discharge) terminals. For a plasma-bridge (RF/microwave) neutralizer, the RF/microwave power at its coupling structure | keeper supply; for a plasma-bridge cathode, its generator chain | explicit 0 W if the keeper is off in the mode |
| `cathode_heater` | all | heater terminals in the evaluated mode | heater supply, harness | heater off in the mode, or heaterless cathode: 0 W, efficiency 1, explicit |
| `flow_control` | all | terminals of every propellant-feed actuator: the atmospheric-path valve (after the gas chamber), the Xe-path valve (after the Xe chamber), proportional/latch valves, thermothrottles, mass-flow-controller electronics | valve drivers / converters | none |
| `compressor` | all | electrical input of the compressor motor drive; motor, bearing and drive losses are **part of the load** (as `compressor.py:137` `P_el`) | motor-bus converter, harness | none while air-fed |
| `thermal_control` | all | terminals of propulsion-subsystem heaters and active thermal hardware on the bus: Xe tank/line/valve heaters, gas-chamber heaters, PPU heaters. Passive radiators draw nothing | heater switches / converters | explicit 0 W if none are on |
| `housekeeping` | all | propulsion controller and PPU control electronics, sensors (pressure, temperature, current), telemetry/command interface. **Not** spacecraft housekeeping | their converters | never 0 |
| `rf_source` | `rf_hall` | **net RF power** (forward − reflected) at the RF pre-ionizer coil/antenna feed terminals. Coil ohmic loss and plasma coupling are part of the load (ionization-block physics) | DC supply, RF generator (incl. drive/auxiliary draw), matching network, RF cable | a pre-ionizer at 0 W is idle hardware (see §5) |
| `ecr_source` | `ecr_hall` | **net microwave power** at the ECR coupling-structure input (waveguide/antenna). Absorption in the plasma is part of the load | HV/DC supply, magnetron or solid-state amplifier (incl. filament/driver/bias), isolator/circulator, feed line | as `rf_source` |
| `ecr_magnet` | `ecr_hall` | ECR resonance-field coil terminals | magnet supply, harness | permanent-magnet ECR circuit: 0 W, efficiency 1, **explicit** |

Justification of the common set from open PPU descriptions (component taxonomy only, no numbers transferred):
- The Northrop Grumman 1 kW Hall string PPU runs from a 24–34 V unregulated bus. Its internal supplies are "discharge
  supply module; heater-ignitor-keeper supply; magnet supply; PFCV supply; microcontroller; and AUX supply" (Nikrant et
  al., IEPC-2022-303).
- The Mitsubishi Electric 250 mN-class PPU has seven power-conditioner types: "discharge power supply, cathode keeper
  power supply, cathode heater power supply, two magnet power supplies, mass flow controller power supply and house
  keeping power supply" (Osuga et al., IEPC-2009-117).
- The NASA SSEP sub-kW PPU has separate keeper, electromagnet, heater and discharge supplies on a 24–34 V input (Rhodes
  et al., IEPC 2024 slides, slide 3).

The compressor and the propulsion-subsystem thermal control come from the RFP architecture of this repository: the
atmospheric path has a compressor and the gas chambers need thermal management.

**Not covered by v1 (a new boundary version is needed, never an ad-hoc extra key).** A helicon pre-ionizer with its own
axial-field magnet (`archengine` `helicon`, `archengine.py:117`), a DC-discharge pre-ionizer, grids, magnetic nozzles
and every other family (CLAUDE.md rule 8: no new propulsion families). A powered filter, or any other electrical
consumer on the atmospheric path that none of the definitions above covers.

## 4. Interface contract

```python
from abep_sim.arch_boundary import BOUNDARY_VERSION, ARCHITECTURES, REQUIRED_COMPONENTS, bus_power_ledger
ledger = bus_power_ledger(arch, loads, efficiencies)
# -> {'boundary_version': 'bus_power_boundary_v1', 'architecture': arch, 'P_bus_W': float,
#     'items': [{'component', 'P_load_W', 'efficiency', 'P_bus_W', 'P_loss_W'}, ...],   # REQUIRED_COMPONENTS[arch] order
#     'residual_W': float}
```

- `loads[c]` must be a finite real ≥ 0 [W]. `efficiencies[c]` must be a real in (0, 1]. Both mappings must contain
  **exactly** `REQUIRED_COMPONENTS[arch]`: a missing key, or an extra key in either mapping, raises `ValueError`. An extra
  efficiency means the caller's boundary differs from v1, so a superset efficiency dict shared across architectures is
  refused. Build it per architecture. Bool, string, complex, NaN and ±inf values, non-mapping inputs, unknown
  architectures and bus draws that overflow also raise `ValueError`.
- **No defaults.** The function has no default arguments. The module has no numeric constants for loads or
  efficiencies. A permanent-magnet `ecr_magnet` is passed as `0.0` W with efficiency `1.0`.
- Per item: `P_bus_W = P_load_W / efficiency` and `P_loss_W = P_bus_W − P_load_W` (≥ 0).
- `P_bus_W` (ledger) is the destination-side total, Σ P_load + Σ P_loss. `residual_W` is `P_bus_W − Σ items[].P_bus_W`,
  the source-side total. Conservation is a gate (CLAUDE.md rule 4): if |residual| > 1e-12 × max(Σ items P_bus, 1 W),
  the module raises `RuntimeError` instead of returning a ledger.
- `REQUIRED_COMPONENTS` is a plain `dict` (the contract type), but v1 is frozen. If a caller mutates it at run time,
  the ledger raises `RuntimeError`. A different component set needs a new `BOUNDARY_VERSION`.
- `COMPONENT_DEFINITIONS` holds a one-paragraph text definition of every component and restates §3. It has no numbers.

## 5. Rules for callers (fair comparison)

1. Compare architectures only on `ledger['P_bus_W']` from this boundary, in the same operating mode, with the same
   common-component definitions. A discharge-only or plasma-absorbed-power comparison is outside this boundary.
2. Common loads may differ between architectures. For example, pre-ionization may change the discharge power, and the
   compressor load follows the flow. The component set may not differ.
3. Every efficiency is evaluated at its operating point and carries source, evidence level, quantity type, uncertainty
   and applicability (docs/EVIDENCE.md). Evidence table: §8. An efficiency marked TBD there stays TBD. Give such a case
   an explicitly labelled assumed value with a sensitivity range, never an unlabelled number.
4. An `rf_hall` or `ecr_hall` ledger with 0 W pre-ionizer source power describes Hall hardware with an idle pre-ionizer.
   It is a valid power statement, but a harness must label it that way. It is not evidence for the pre-ionized
   architecture.
5. The ledger checks bookkeeping and completeness against v1. It checks no physics. Hall-block loads stay conditional on
   gate 3.
6. Whether the RFP's "< 1.5 kW" limit (`constants.RFP.power_max_W`) refers to this boundary is **TBD**. Settling it
   requires the RFP text of Part III Para 2. `archengine` applies it at the PPU bus input (`archengine.py:641`).

**Mapping from `archengine` quantities (informational for a harness, not implemented here).** Under this boundary the
RF/microwave generator efficiency moves from `archengine`'s load into the efficiency. The bus total is unchanged:

| boundary | from `archengine` / `plasma_devices` | note |
|---|---|---|
| `rf_source` load | `P_ion × eta_dc_rf` (`plasma_devices.py:45`) | the remaining factor `gate·R_p/(R_p+R_coil)` (`plasma_devices.py:53`) is coil/plasma coupling, inside the load |
| `rf_source` efficiency | `eta_conv(rf_amp) × eta_dc_rf` | `eta_conv` from `ppu.Converter.efficiency` (`ppu.py:28-38`); P_bus = P_ion / eta_conv as in `archengine` |
| `ecr_source` load | `P_ion × eta_dc_mw × eta_feed` (`plasma_devices.py:24-25`) | whether unabsorbed power (pressure gate / overdense factor) is reflected (a chain loss) or dissipated in the source (a load loss) is not stated by the model. The P_bus total is the same either way. The split is **TBD** |
| `ecr_source` efficiency | `eta_conv(hv_mw) × eta_dc_mw × eta_feed` | as above |
| all generator parameters | `0.65`, `0.90`, `0.80` in code | unsourced in the code: evidence class *assumed* (§8, R-rows) |

## 6. DISCREPANCY AUDIT — `abep_sim/archengine.py` energy ledger vs `bus_power_boundary_v1`

This is read-only code reading at `daa0e75`. `archengine.py` is **not modified**: changing it would be a model change
(goldens may move, HISTORY entry, owner decision). `tools/verify_audit_anchors.py` checks every file:line reference in
this document against the quoted code. At `daa0e75`, 75/75 anchors matched and none of the document's references was
left without an anchor.

**How `archengine` forms bus power (design point).** `close_architecture` builds a PPU (`archengine.py:616`) and a
converter-output demand (`archengine.py:627-636`). `ppu.loads` then returns
`P_bus = controller_W + sensors_W + Σ P_out/η_conv` (`ppu.py:61`, `ppu.py:75`, `ppu.py:78`), and the design constraint
compares that P_bus with `P_bus_max_W` (`archengine.py:637-641`). The location is the same as this boundary: a 28 V DC
bus is assumed (`ppu.py:47`). The contents differ:

| boundary component | `archengine` consumer | anchor | status |
|---|---|---|---|
| `hall_discharge` | "anode" converter, demand `P_acc_W / V_conv` with `P_acc = hr["P_d_W"] = I_d·V_d` | `archengine.py:484`, `:615`, `:629`; `plasma_devices.py:551`; `ppu.py:94` | **included** |
| `hall_magnet` | "magnet" converter, fixed `P_mag = 25.0` W at 12 V, independent of the magnetic design | `archengine.py:627-628`; `ppu.py:95` | **included, fixed constant** (assumed, unsourced) |
| `cathode_keeper` | "keeper" converter at 30 V, demand `P_neut_W / 30` (LaB6 only); plasma-bridge cathodes via "cathode_src" | `archengine.py:631`, `:636`; `ppu.py:96` | **included** |
| `cathode_heater` | LaB6 `P_W = heater_W·(T/1700)^4·0.6 + keeper_W` is routed through the **keeper** converter. The "heater" converter exists but gets no steady demand. `load_modes` (the only heater demand, `ppu.py:115`) is imported but never called in `archengine` | `plasma_devices.py:266-267`, `:298`; `ppu.py:97`; `archengine.py:582` | **lumped into keeper**; its conversion efficiency is the keeper converter's |
| `flow_control` | no consumer ("reservoir_feed" is mass only) | `archengine.py:673` | **excluded** (unless inside the unattributed 5 W "aux") |
| `compressor` | "motor" converter at 48 V, demand `comp_power / 48`, with `comp_power` = compressor `P_el` (motor + control inside the load) | `archengine.py:628`, `:888`; `compressor.py:137`; `ppu.py:98` | **included**; same load plane as §3 |
| `thermal_control` | no consumer; thermal appears only as waste heat for radiator sizing (`nodes[…]`) | `archengine.py:665` | **excluded** |
| `housekeeping` | `controller_W = 8.0` + `sensors_W = 4.0` added directly at the bus with no conversion loss, then booked inside "ppu_loss_control"; plus an **unattributed** "aux" load of 1 A × 5 V = 5 W | `ppu.py:52`, `:54`, `:61`, `:78`, `:99`; `archengine.py:628`, `:657-658` | **partly included, mis-classed** (control electronics counted as "loss"; 5 W aux not attributable) |
| `rf_source` | "rf_amp" converter at 50 V, demand `P_ion / 50`, only if `P_ion > 0` | `archengine.py:614`, `:635`; `ppu.py:105` | **included at the generator DC input**; RF generation efficiency is inside the source physics (`plasma_devices.py:45`, `:53`) |
| `ecr_source` | "hv_mw" converter at 4000 V, demand `P_ion / 4000`, only if `P_ion > 0` | `archengine.py:614`, `:635`; `ppu.py:103` | **included at the magnetron DC input**; magnetron and feed efficiency inside the source physics (`plasma_devices.py:24-25`) |
| `ecr_magnet` | no separate consumer. For a Hall accelerator `P_mag` is 25 W whether or not an ECR source is present, so the ECR resonance field costs nothing extra in `ecr+hall` | `archengine.py:627` | **excluded / indistinguishable** |

**Findings.**
1. **The ledger closes by construction, so it is not a completeness check.** The ledger (`archengine.py:656-658`) sums
   jet + plume + accelerator body + (P_ion − from_src) + P_neut + P_mag + compressor + 5 W + PPU loss/control. With
   `from_acc = min(P_jet, P_acc)` (`archengine.py:653`), that is exactly
   `P_acc + P_ion + P_neut + P_mag + comp_power + 5 + P_loss`. `ppu.loads` returns `Σ P_out + P_loss` over the same
   demands (`ppu.py:61-78`). For the Hall family every demand's `P_out` equals its ledger term, so the residual checked
   against 2 % (`archengine.py:659-660`) is zero up to rounding. That is consistent with the near-zero `ledger_resid`
   of the golden benchmarks (CLAUDE.md gate 6). A consumer absent from both lists (flow control, thermal control,
   a separate heater, an ECR magnet) leaves the residual at zero. `bus_power_boundary_v1` supplies the missing
   completeness check through `REQUIRED_COMPONENTS`.
2. **Pre-ionizer power is on the bus at the design point.** `P_ion` has a converter and a demand (`archengine.py:614`,
   `:635`), sits in P_bus, and is booked as ionizer heat. For the Hall family
   `P_jet = I_beam·V_d·eta_v_base ≤ I_d·V_d = P_d`, because `I_d = I_beam + I_e` with `I_e ≥ 0` and
   `eta_v_base = 0.85` by default (`plasma_devices.py:133`, `:527`, `:551`). So `from_src = 0`
   (`archengine.py:653`, `:656`, `:665`). `archengine` therefore does **not** select on discharge-only power at the
   design point. The reference plane is the generator/magnetron DC input, and the generator efficiencies (`0.65`,
   `0.90`, `0.80`) are unsourced model parameters.
3. **Pre-ionized architectures can close at zero pre-ionizer power.** The Hall-family search grid includes
   `P_ion = 0.0` (`archengine.py:557`). With `P_ion = 0`, `has_s1` is false (`archengine.py:614`), so there is no
   pre-ionizer converter, no standby draw and no pre-ionizer ledger term, but `io.mass_kg` is still carried
   (`archengine.py:673`). An `rf_icp+hall` or `ecr+hall` result may be Hall-only operation with idle pre-ionizer
   hardware. §5 rule 4 applies.
4. **ECR magnet and resonance.** No ECR-field power is charged in the Hall pairing (`archengine.py:627`). The
   0.0875 T resonance requirement is enforced only for the nozzle family (`archengine.py:456-458`). v1 requires
   `ecr_magnet` explicitly, as 0 W only for a declared permanent-magnet circuit.
5. **Cathode heater lumped.** Steady heater power travels through the keeper converter (`archengine.py:631`,
   `plasma_devices.py:298`). The start-up mode, the only place the heater converter is used (`ppu.py:115`), is not
   evaluated in `archengine` (`archengine.py:582` import only).
6. **Missing consumers.** No flow-control or thermal-control electrical load exists. The 5 W "aux"
   (`archengine.py:628`, `:657`) is not attributable to any component.
7. **Off-design and mission paths use a different, approximate boundary.** The mission-envelope check
   (`archengine.py:708`) and `propulsion_map` (`archengine.py:815`, `:819`) use
   `(P_acc + P_ion + P_neut + P_mag + comp + 5) / max(η_overall, 0.5) + 12`. That is the design-point overall PPU
   efficiency applied uniformly, with a 0.5 floor. A dark channel is charged a hard-coded 45 W "keeper/cathode"
   (`archengine.py:818`). None of this passes through `ppu.loads`, so off-design and design-point bus powers are on
   different boundaries.
8. **Converter efficiencies are model parameters.** `ppu.Converter.efficiency` uses a switching-loss model
   (`P_fixed`, `k_cond`, `k_sw`) clamped to [0.3, 0.985] (`ppu.py:28-38`). No source is cited in the module, so its
   evidence class is *assumed / model-derived*. The same holds for the 28 V bus (`ppu.py:47`).

**Other bus-power paths (outside `archengine`, listed so they are not mistaken for this boundary).** The card path in
`system.py` applies one `ppu_eff = 0.90` to thruster + compressor + `p_ctrl_valves_sensors_W = 30` W
(`system.py:15-16`, `:193`). Its physics path uses `load_modes` with a fixed 1.5 A keeper (`system.py:278`) and
multiplies the valves/sensors term by `0.0` (`system.py:285`). These are different boundaries again. Reconciling them
is a model change for the owner.

## 7. What this lane does not do

It does not wire the boundary into `archengine`, `hall_ensemble` or `hall_map`. It does not set any efficiency or load.
It does not rerun the architecture trade or gate-4 UQ, and it does not change any golden. Any of these is a model change
under CLAUDE.md rules 1–2 and is the owner's decision.

## 8. Evidence table — conversion efficiencies (data for callers, **not defaults**)

Sources were accessed openly on 2026-09-26. None was obtained through a paywall. The Springer article was fetched after
Springer's standard cookie redirect, which is open access under CC BY 4.0. "Level" is the docs/EVIDENCE.md evidence
level *for a Vyovrinda < 1.5 kW ABEP PPU*: 3 = primary measurement on closely similar-class hardware; 6 = transfer from
a different hardware class (extrapolation outside its validated domain). "Type" is the quantity type. Values are quoted
from the source text unless marked *digitized*. Nothing here is validated for Vyovrinda hardware (EVIDENCE.md
closure path).

| # | chain stage / component | value(s) as reported | conditions | source | level | type | limitations |
|---|---|---|---|---|---|---|---|
| E1 | `hall_discharge`: discharge supply, 28 V-class input | 28 Vin, 250 V out: 86.14 % at 249.6 W; 88.93 % at 500.1 W; 90.14 % at 800.1 W; 89.93 % at 1000.1 W. 28 Vin, 400 V out: 77.16 % at 200.1 W; 86.09 % at 500.1 W; 88.50 % at 800.1 W; 90.72 % at 1000.2 W. All 54 points (25/28/34 Vin): `evidence/rhodes2024_lcc_discharge_supply_efficiency.csv` | LCC resonant discharge supply, breadboard bench test, input 24–34 V, output 200–500 V, ≤ 1 kW | Rhodes, Benavides, Piñero, "Sub-kW Class Hall-Effect Thruster PPU for Wide Output Range Applications", 38th IEPC 2024, slides (NASA NTRS 20240006846), slide 11: https://ntrs.nasa.gov/api/citations/20240006846/downloads/Rhodes%20-%20IEPC%202024%20Presentation_v2.pdf | 3 | measured → digitized (vector marker centres; axis-calibration residual ≤ 0.007 %-pt, ≤ 0.2 W) | breadboard; efficiency definition, load type and measurement uncertainty are not stated on the slide (**TBD**, requires the full paper); excludes harness/filters to the thruster; strong part-load dependence (compare the 200 W and 1 kW rows) |
| E2 | whole PPU incl. magnet + keeper supplies, high power | "total efficiencies of almost 98% at 12 kW and 500 V discharge voltage"; "better than 96.5% for the entire range" (300 V SiC brassboard). 120 V PPU: "in excess of 95% above 10 kW"; "above 93% for most of the operating range" | total PPU efficiency = "ratio of all power outputs to all power inputs"; resistive loads; magnet and keeper supplies "at levels representative of the thruster"; 300 V / 120 V input, 12.5–15 kW class | Piñero, Bozak, Santiago, Scheidegger, Birchenough, "Development of High-Power Hall Thruster Power Processing Units at NASA GRC", AIAA/SAE/ASEE JPC, Orlando, July 2015 (NTRS 20150023095): https://ntrs.nasa.gov/api/citations/20150023095/downloads/20150023095.pdf | 6 | measured (reported) | high-voltage bus and 10× the power class; not transferable to a 28 V < 1.5 kW PPU. Also shows a two-bus PPU (keeper and heater from 28 V, discharge from 120 V), see §2 |
| E3 | whole PPU and anode conditioner, 100 V bus | anode conditioner "more than 95%" over 1.8–4.5 kW (250–350 V out); "peak power efficiency of the EM2 PPU had been 96.2%" (stated in the anode-conditioner paragraph; scope ambiguous, **verify**); PPU total "more than 94%"; 94.1 % at 4630 W PPU input with the thruster | Mitsubishi Electric EM2 PPU, regulated 100 V ± 3 V bus, 250 mN-class Hall thruster | Osuga et al., "Performance of Power Processing Unit for 250mN-class Hall Thruster", IEPC-2009-117: https://electricrocket.org/IEPC/IEPC-2009-117.pdf | 6 | measured (reported) | 100 V bus, ≥ 1.8 kW; auxiliary-supply efficiencies not given separately |
| E4 | `rf_source`: RF generator + feed cable (DC input of the RFG → RF power forwarded at the thruster coil) | η = P_RF/P_DC. At low mass flow the authors report "a difference of about 30 − 40 % between DC input and forwarded RF power", read here as η ≈ 0.60–0.70 (*inferred*, an interpretation of the wording). The Fig. 11b coupling-efficiency axis spans 60–75 % (not digitized) | RIT-10/37, xenon 1–10 sccm (mode 1; 1–8 sccm mode 2), RFG in resonant zero-current-switching operation, load "driven at around 2 MHz"; VI sensor "voltage, current, and power measurement accuracy of ±1 %" | Volkmar, Geile, Hannemann, "Radio-Frequency Ion Thrusters—Power Measurement and Power Distribution Modeling", J. Propulsion and Power, DOI 10.2514/1.B36868. Accessed as the DLR elib preprint: https://elib.dlr.de/120608/1/Volkmar_JPP_preprint.pdf | 6 | measured → inferred (η from the stated difference) | gridded RIT at ~2 MHz, not a 13.56 MHz ICP pre-ionizer; excludes the bus-to-RFG DC supply; η falls as the load resistance drops at low flow (impedance-bridge mismatch), so η is operating-point dependent. Digitizing Fig. 11b is **TBD** |
| E5 | `rf_source`: RFG design sensitivity | no absolute efficiency; compared with an analog PLL RFG, the new resonant RFG "is able to provide the same output power with 17 % less input power" at an output frequency of 3 MHz (the relation symbol is lost in text extraction, **verify**) and 0.75 sccm xenon; "auxiliary power consumption is not included" | RIM-4 RF ion thruster, FPGA-controlled resonant half-bridge | Simon, Probst, Klar, "Development of a Radio-Frequency Generator for RF Ion Thrusters", Trans. JSASS Aerospace Tech. Japan 14 (ists30), Pb_33–Pb_39, 2016: https://www.jstage.jst.go.jp/article/tastj/14/ists30/14_Pb_33/_pdf/-char/en | 6 | measured (relative, reported) | relative only; absolute bus → coil efficiency **TBD**. Shows that generator design alone moves pre-ionizer bus power by double-digit percent, and that published RFG figures may exclude auxiliary draw |
| E6 | `rf_source`: Class-E vs half-bridge RFG | no absolute DC-to-RF efficiency reported. The RFGs are compared through the DC input needed for equal beam current. VI-probe active-power measurement "can be inaccurate due to high phase angles" (phase accuracy ±1 deg) | RIT-10, xenon | Beller, Roessler, Probst, Thueringer, Volkmar, "A radio-frequency generator for ion thrusters based on a Class-E power circuit", J. Electric Propulsion 1:8 (2022), DOI 10.1007/s44205-022-00008-9 (CC BY 4.0) | — | — | **TBD**. Shows that the coil-plane RF power, and so the `rf_source` load/efficiency split, is a measurement problem in its own right |
| E7 | `ecr_source`: solid-state microwave amplifier stage | drain efficiency 72.9 %, PAE 64.0 % at 50.4 dBm output, 2.45 GHz, CW | GaN-HEMT amplifier, 100 W class, laboratory | Nakatani & Ishizaki, "A 2.4 GHz-Band 100 W GaN-HEMT High-Efficiency Power Amplifier for Microwave Heating", J. Electromagn. Eng. Sci. 15(2), 82–88, 2015, DOI 10.5515/JKIEES.2015.15.2.82 (CC BY-NC 3.0): https://www.jees.kr/upload/pdf/jees-15-2-82.pdf | 6 | measured (reported) | amplifier stage only: excludes driver stage DC, bias, the bus DC-DC, isolator and feed; not space-qualified; bus → coupling-plane chain **TBD** |
| E8 | `ecr_source`: magnetron tube | "conversion efficiency of 70%" for the 2450 MHz, 700 W-average oven magnetron (W. C. Brown, quoted); "Nominal Efficiency" 77.3 % (800 W cooker) and 69.1 % (1200 W cooker) in a design-parameter table | 2.45 GHz, 0.5–1.2 kW class | Dexter, "Magnetrons for accelerators", EnEfficient RF Sources Workshop, Daresbury, June 2014 (slides): https://indico.cern.ch/event/297025/contributions/1658266/attachments/557200/767680/Magnetrons_Daresbury2014.pdf | 5 (secondary; basis of the table values not stated, **verify**) | reported (secondary) | tube only: excludes the HV supply (anode voltage 4000 V in the same table), filament, isolator and feed; kW-class tubes, whereas a pre-ionizer runs at tens to hundreds of W. Kazakevich et al. (arXiv:1709.04526, https://arxiv.org/pdf/1709.04526) define absolute efficiency as "the ratio of the measured magnetron RF power to the output power of the magnetron HV power supply". For power control they report *relative* average efficiencies "of about 50%-70%" (vector methods) and "more than 80%" (current control); their absolute values (Fig. 12) are not digitized (**TBD**) |
| E9 | `hall_magnet`, `cathode_keeper`, `cathode_heater` supply efficiencies | **TBD**: requires per-supply efficiency data. The sources accessed give ratings only: 24–34 V input; max output keeper 25 W, electromagnets 60 W, heater 80 W (Rhodes 2024 slide 3); magnets 200 W, keeper 90 W, heater 324 W (Piñero 2015 Table 1). E2 and E3 give totals that include these supplies | — | E1 / E2 sources | — | — | do not back out per-supply efficiencies from totals |
| E10 | `flow_control`, `thermal_control`, `housekeeping` | **TBD**: requires valve-driver / heater-switch / controller supply data | — | none accessed | — | — | often switched directly from the bus, but no source accessed |
| E11 | `ecr_magnet` | permanent magnet: 0 W, efficiency 1 by definition (explicit input); electromagnet: **TBD** | — | — | — | definition | — |
| E12 | microwave isolator / feed loss | **TBD** | — | none accessed | — | — | `plasma_devices.py:25` uses 0.90 (unsourced) |

**Repository values currently in code (R-rows, context only; evidence class *assumed*, none cites a source).**
Converter model: `ppu.py:28-38`, clamp [0.3, 0.985]. Generator/feed: `eta_dc_mw = 0.65`, `eta_feed = 0.90`
(`plasma_devices.py:24-25`); `eta_dc_rf = 0.80` (`plasma_devices.py:45`). Card path: `ppu_eff = 0.90` (`system.py:15`).
Fixed loads: `P_mag = 25` W (`archengine.py:627`), controller + sensors 12 W (`ppu.py:52-54`), aux 5 W
(`archengine.py:628`), dark-channel 45 W (`archengine.py:818`). They are recorded here so a harness never mistakes them
for evidence.

## 9. Open questions for the owner

1. Which boundary does the RFP's "< 1.5 kW" refer to: this propulsion-subsystem bus input, or something else? (§5 rule 6)
2. Should v1.1 add explicit standby/idle terms (for example, a pre-ionizer supply held ready), or is booking them under
   `housekeeping` acceptable? (§2)
3. Is the ECR resonance field to be permanent-magnet (0 W, explicit) or electromagnet for Vyovrinda? The ledger requires
   the choice either way.
4. Should `archengine` adopt this boundary (a model change: goldens may move, HISTORY entry)? The findings in §6 are
   what would change.
5. Which bus voltage should the evidence table target? `ppu.py:47` assumes 28 V. E1 is the only 28 V-class,
   ≤ 1 kW measurement found.

## 10. Reproduce

```bash
python -m pytest -q tests/test_arch_boundary.py
python docs/architecture_comparison/power_boundary/tools/verify_audit_anchors.py        # 75/75 anchors, 0 unanchored references at daa0e75
python docs/architecture_comparison/power_boundary/tools/extract_rhodes2024_discharge_efficiency.py --pdf <slides.pdf>
#   the slides PDF is not redistributed; the script refuses any file whose sha256 is not
#   9f5a6c7bb36ac2ffc45026e004150304a592dadb1419284917341623588e21d9 (needs PyMuPDF; tested with 1.28.2)
```
