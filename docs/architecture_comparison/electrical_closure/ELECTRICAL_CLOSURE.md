# Electrical closure v1: PPU conversion efficiencies, auxiliary loads and magnet power on the common bus-power boundary

| item | value |
|---|---|
| lane | PPUMAG (lane 20): PPU and magnet electrical closure |
| model | `abep_sim/magnet_power.py` (pure, standard library only, **not wired** into `archengine`) |
| data | `electrical_closure_data_v1.json` (schema `schemas/architecture_comparison/electrical_closure_v1.schema.json`) |
| worked example | `worked_example_v1.json` |
| generator | `tools/build_electrical_closure_data.py` (deterministic; `--check` compares with the committed files) |
| digitization | `tools/digitize_rhodes2024_slide11.py` → `sources/rhodes2024_slide11_discharge_efficiency.csv` |
| tests | `tests/test_electrical_closure.py` |
| boundary | `bus_power_boundary_v1` (module `abep_sim/arch_boundary.py`, built by another lane; referenced, never imported here) |
| written against | commit `c53b75aece86c91db48443761574b7bf07df6070`, 2026-09-26 |
| status | DRAFT for the owner. Evidence data and an equation model. It makes **no** architecture, transport or performance claim |

Gate 3 stays FAIL and the credible transport set is ∅, so every absolute Hall discharge power stays withdrawn. Nothing in
this lane supplies one. The lane supplies the other pieces a caller needs to turn a discharge-only number into a real
DC-bus draw once an admitted closure exists: the conversion efficiencies, the auxiliary loads and a physics model for
magnet power. Screening candidates and unadmitted closures are never used.

## 1. Milestones

- **Milestone A (conditional selection): supported.** The data file lists every boundary component with the evidence
  that exists today and an explicit TBD for everything else. A conditional statement ("architecture X is baseline
  provided conditions A/B/C are demonstrated") can use these TBDs as its conditions, for example "magnet-supply
  efficiency ≥ η at the operating point, demonstrated". This lane does not rank architectures.
- **Milestone B (physics-backed selection): not reached.** It needs the following:
  - an admitted Hall transport closure for the `hall_discharge` load;
  - measured supply efficiencies at the Vyovrinda operating points: magnet, keeper, heater, valve driver, and the RF or
    microwave chain including matching and isolator;
  - a sized compressor, with a sourced motor and drive efficiency, run through `abep_sim.compressor`;
  - thermal-control and housekeeping loads;
  - the Vyovrinda magnetic-circuit geometry and field, fed into `magnet_power`.
- **Milestone C (proposal/PDR freeze): not reached.** It needs a flight PPU design whose mass, thermal, life, start-up
  sequence and cathode policy are integrated with mission closure on this boundary.

## 2. How to assemble a full DC-bus ledger for one architecture

The boundary charges every architecture at the spacecraft DC-bus input to the propulsion subsystem. For each component
`c` in `REQUIRED_COMPONENTS[arch]`, the ledger needs a load-side power `P_load[c]` and a bus-to-load efficiency `η[c]`
at the operating point. Then `P_bus = Σ P_load[c] / η[c]`. The boundary module refuses a missing component, an extra
component or a missing efficiency. It never defaults one.

1. **Choose the mode**, for example steady firing, start-up, eclipse or Xe augmentation. Evaluate every load and
   efficiency in that mode. Components that are off in the mode are passed explicitly as 0 W, with efficiency 1.0 where
   the boundary convention says so.
2. **Loads.** Build them as follows:
   - `hall_discharge`: from an admitted Hall map only. TBD today.
   - `hall_magnet` / `ecr_magnet`: from `magnet_power.electromagnet(...)` for the caller's own circuit (§3). For a
     permanent-magnet circuit, pass 0 W with efficiency 1.0; the magnet mass goes to the mass ledger via
     `magnet_power.permanent_magnet(...)`.
   - `cathode_keeper` / `cathode_heater`: from the cathode policy of the mode. In steady mode the heater is normally off
     and the keeper is normally off (entries CH-G&K-STEADY-OFF, CK-G&K-OFF). The start-up heater brackets are 45–305 W
     across three LaB6 designs (CH-*).
   - `flow_control`: coil I²R of every energized valve. One Xe PFCV draws 0.419–1.46 W at 21 °C (FC-MOOG-I2R). The
     air-path valve is TBD.
   - `compressor`: `abep_sim.compressor.DragCompressor.run(...)['P_el_W']`, but only after its unsourced inputs
     (`eta_motor`, `P_ctrl_W`, `k_bear_W_per_rads`) are replaced by sourced ones. TBD today. Its flow comes from the
     upstream ICD, never from Hall-closure uncertainty.
   - `thermal_control`, `housekeeping`: TBD.
   - `rf_source` / `ecr_source`: net RF or microwave power at the coupling plane, from pre-ionizer physics. TBD.
3. **Efficiencies.** Pick the entry whose applicability matches the operating point: power class, bus voltage, output
   voltage and frequency. Record its `id`, `evidence_class`, `evidence_level` and uncertainty next to the value. If the
   chain has several stages (DC supply → generator → matching → cable), multiply only stages that the entries do not
   already include; each entry's `chain_stage` says what it covers. A stage-only value is an upper bound on the chain,
   never the chain value. Examples are the GaN drain efficiency and the magnetron tube efficiency.
4. **Call the boundary.** The module is resolved lazily; if the other lane's file is absent, this fails with a clear
   error and nothing here depends on it:

   ```python
   import importlib
   ab = importlib.import_module("abep_sim.arch_boundary")        # ModuleNotFoundError until that lane merges
   ledger = ab.bus_power_ledger("rf_hall", loads, efficiencies)  # both dicts exactly REQUIRED_COMPONENTS["rf_hall"]
   ```
5. **Carry the evidence.** Report the ledger together with the list of entry ids used and the TBD items still open. Any
   TBD that is replaced by an explicitly labelled assumption must be swept over a sensitivity range and reported that
   way, never as a single number.

## 3. Magnet power model (`abep_sim/magnet_power.py`)

The functions take every input explicitly and have no default arguments. Invalid or out-of-domain inputs raise
`ValueError`; the tests cover this.

| eq. | relation | source (accessed 2026-09-26) |
|---|---|---|
| E1 | Ampère: Σ MMF = N I. Gap MMF = B_g g / μ0. Core segment MMF = (k B_g A_g / A_i) l_i / (μ0 μ_r,i), with `leakage_factor` k ≥ 1 (core flux / gap flux, explicit) | Kirtley, MIT 6.007 notes, Sec. 3.2–3.5. Ignoring fringing "generally over-estimates the reluctance" (Sec. 3.5) |
| E2 | Permanent magnet on a linear recoil line B_m = B_r + μ0 μ_rec H_m, with flux continuity B_m A_m = k B_g A_g and H_m l_m + Σ MMF = 0, so l_m = MMF / (−H_m). Refused if B_m ≥ B_r or if −H_m exceeds the caller's knee field | Kirtley, MIT 6.061 ch. 12, Sec. 4.3 (unit-permeance form B_m = B0 P_u/(1+P_u), reproduced exactly in the tests for μ_rec = 1) |
| E3 | Wire resistance R(T) = R_20 [1 + 0.00393 (T − 20 °C)], for the resistance "between points fixed on a wire which is allowed to expand freely". IACS 0.017241 Ω mm²/m and 8.89 g/cm³ at 20 °C. Linear "up to 200 °C" | NBS Handbook 100 (1966), pp. 1–3. Checked against its Table 6 (p. 16), AWG 24 and 0000 rows at 0–200 °C, within one unit of the last tabulated digit |
| E4 | AWG: No. 0000 = 0.4600 in, No. 36 = 0.0050 in, 39 geometric steps | NBS Handbook 100, Sec. 2.2, p. 6 |
| E5 | Coil: N = ⌊k A_w / A_cu⌋, I = NI / N, R = ρ N l_mt / A_cu, P = I² R | derivation below |
| E6 | μ0 = 1.256 637 061 27 × 10⁻⁶ N A⁻² | CODATA 2022 (NIST) |

**Derivation of the gauge-independent form (E5).** With I = (NI)/N and R = ρ N l_mt / A_cu:
P = (NI)² ρ l_mt / (N A_cu). Copper fill gives N A_cu = k A_w, so **P = (NI)² ρ(T) l_mt / (k A_w)**. At a fixed winding
window the wire gauge only trades current for voltage. The dissipated power depends on the ampere-turns (∝ B_g for a
linear circuit, hence P ∝ B_g²), the copper temperature, the mean turn length, and the copper area k·A_w. The tests check
the B² scaling, the temperature factor (1.3144 at 100 °C and 1.7074 at 200 °C relative to 20 °C) and the equality of
integer-turn and continuous results when N is exact.

**Domain limits (refusals, never extrapolated).** The limits are:
- copper between 0 and 200 °C, the Handbook's stated linear range; its "probably −100 to +300 °C" is not used, and a
  caller who needs another range must build its own cited `ConductorMaterial`;
- core segments below the caller's declared `B_max_T`, since the model is linear and unsaturated;
- a permanent magnet only on the recoil line and short of the knee.

**Evidence class of outputs:** model-derived (level 6: a lumped engineering model). All geometry, field, leakage, fill,
core and magnet-material inputs carry the caller's own evidence. This module holds no magnet-material data.

## 4. Data by component (summary of `electrical_closure_data_v1.json`)

"Level" is the docs/EVIDENCE.md evidence level for a Vyovrinda < 1.5 kW ABEP PPU; 6 marks a transfer from a different
hardware class. "Class" is the quantity type. Every row's exact locator, transformation chain and uncertainty are in the
JSON.

| component | entry | value | class / level | applicability and limits |
|---|---|---|---|---|
| `hall_discharge` η | HD-RH24-* (6 series) | 28 V in: 86.14 % (249.6 W) … 90.14 % (800.1 W) … 89.93 % (1000.1 W) at 250 V out; 77.16 % (200.1 W) … 90.72 % (1000.2 W) at 400 V out; 25/34 V in also carried | digitized / 3 | NASA SSEP LCC breadboard, 24–34 V bus, 200–500 V, ≤ 1 kW. Harness and filters excluded; efficiency definition and measurement uncertainty not on the slide (TBD, full paper). Rhodes 2024 slide 11 |
| | HD-MANZELLA96-EST | 0.90 | assumed / 7 | 1996 study estimate: **context only** |
| `hall_magnet` load | HM-MODEL | `magnet_power.electromagnet` | model-derived / 6 | §3 |
| | HM-PM-OPTION | 0 W (η 1.0, explicit) | definition | permanent-magnet Hall thrusters exist at 100–250 W (SITAEL HT100, Pedrini 2017) |
| | HM-REPO-25W | 25 W | assumed / 7 | `archengine.py:627` constant: **context only, never evidence** |
| `hall_magnet` η | HM-SUPPLY-EFF | **TBD** | — | only a rating is published (Rhodes slide 3: 1–12 V, 1–5 A, 60 W max) |
| `cathode_keeper` | CK-G&K-OFF | normally off after ignition | qualitative / 5 | Goebel & Katz 2008 p. 337 |
| | CK-PEDRINI17-HC3 | 25–60 W (keeper-only discharge) | measured / 3 | LaB6, 1–3 A class, Xe, keeper as sole anode (upper bracket) |
| | CK-PEDRINI17-HC1 | 9–20 W (keeper only) | measured / 6 | LaB6, 0.3–1 A class |
| `cathode_keeper` η | CK-SUPPLY-EFF | **TBD** | — | rating only (Rhodes: 0.5–1 A, 5–40 V, 25 W max) |
| `cathode_heater` | CH-G&K-STEADY-OFF | off in steady mode (self-heating) | qualitative / 5 | Goebel & Katz 2008 p. 337 |
| | CH-PEDRINI17-HC3 / HC1 | ≈ 60 W / ≈ 45 W at ignition | measured / 3, 6 | LaB6, Xe |
| | CH-MONTERO24 | 267–305 W at ignition | measured / 6 | sub-1 A LaB6 (UC3M): the design spread is large |
| `cathode_heater` η | CH-SUPPLY-EFF | **TBD** | — | rating only (Rhodes: 1–8 A, 1–12 V, 80 W max) |
| `flow_control` | FC-MOOG-SPEC → FC-MOOG-I2R | 74.5 ± 2 Ω at 21 °C, 75–140 mA → **0.419–1.46 W per valve** | measured spec → inferred / 3 | Xe PFCV 51E339, 0–30 mg/s Xe typical. Coil tempco not stated. Driver loss and the air-path valve are TBD |
| `compressor` | CP-REPO-MODEL, CP-LOAD | model exists; **load TBD** | model-derived / 7 | `abep_sim/compressor.py` P_el uses unsourced η_motor 0.80, P_ctrl 8 W, k_bear 3e-4 |
| `thermal_control`, `housekeeping` | TC-*, HK-* | **TBD** | — | no source accessed; the repository's 8 W + 4 W (`ppu.py`) are unsourced |
| `rf_source` η | RF-NEWORBIT25 | 0.92 nominal, bus → RF | measured (nominal) / 3 | 26–32 V bus, 1–5 MHz, air-fed RF thruster (NewOrbit, IEPC-2025-378). Method, load range and matching inclusion not stated |
| | RF-VOLKMAR18 | 0.60–0.70 (DC in → forwarded RF, generator + cables, low flow) | inferred / 6 | RIT-10, Xe, ~2 MHz. Falls as load resistance drops at low flow |
| | RF-MATCH-LOSS | **TBD** | — | matchbox and cable loss at the pre-ionizer coil |
| `ecr_source` η | EC-HAYABUSA-TWTA | 40 W RF / 110 W DC = **0.3636** | inferred / 3 | flight TWT system, 4.2 GHz (Kuninaka 2009 Table 1) |
| | EC-NAKATANI15-GAN | drain 0.729, PAE 0.640 at 50.4 dBm (≈ 110 W), CW | measured / 6 | 2.45 GHz GaN **stage only**: an upper bound on the chain |
| | EC-KAZAKEVICH24-MAG | ≈ 0.54 | measured / 6 | 945 W 2.45 GHz magnetron **tube only**, filament excluded, ~3.7 kV anode |
| | EC-ISOLATOR-FEED | **TBD** | — | |
| `ecr_magnet` | EM-RESONANCE-B | 0.08752 T at 2.45 GHz; 0.15004 T at 4.2 GHz | model-derived / 4 | B = 2π f m_e / e, CODATA 2022 |
| | EM-MODEL / EM-PM-OPTION / EM-SUPPLY-EFF | model / 0 W / **TBD** | | |

The 16 external sources are all open (the 17th entry, `S-REPO`, is this repository and is not evidence). Each one's URL, access date and the sha256 of the file actually read are in the JSON's
`sources` block. One source was not used: the HAL copy of Joussot et al. 2017 (5 A LaB6 cathode) sits behind a bot
challenge, and bypassing it is not allowed. Its heater figure is therefore not used.

## 5. Which items dominate the uncertainty

The spreads below come from `worked_example_v1.json`, computed by the generator. A spread is the range of the accessed
evidence. It is not a probability.

1. **`hall_discharge` load.** This is the largest item on every architecture, and it is withdrawn (gate 3). Until a
   closure is admitted, nothing about the absolute bus draw of any architecture can be stated.
2. **Pre-ionizer source chain efficiency.**
   - `rf_source`: 0.60–0.92, so the bus draw per unit of delivered RF differs by a factor of **1.533** (109–167 W of bus
     per 100 W delivered).
   - `ecr_source`: the evidence runs from 0.3636 (the only system-level value) to 0.729 (stage only), a factor of
     **2.005** (137–275 W of bus per 100 W delivered).
   - These spreads come from generator, amplifier and tube technology and from load matching. They are not pre-ionizer
     physics. They bear directly on the rf_hall and ecr_hall rows and not on hall_only.
3. **`hall_discharge` conversion efficiency at part load.**
   - At 28 V in, over the measured 200–1000 W, the efficiency is 77.16–90.72 % (bus-draw factor 1.176).
   - Above 500 W it is 86.09–90.72 % (factor 1.054): about 100–112 W of conversion loss at a 1 kW discharge output
     (worked example, measured points only).
   - Above 1 kW there is no accessed measurement at a 28 V-class bus.
4. **`compressor`.** It is entirely TBD: the model exists, but its efficiency and overhead parameters are unsourced.
5. **Magnets.** The load is set by geometry and field, not by the supply.
   - P ∝ B_g² and ∝ [1 + 0.00393 (T − 20 °C)].
   - At an identical circuit and coil geometry, a 2.45 GHz ECR resonance field (0.0875 T) needs **34.0×** the coil power
     of a 0.015 T Hall field (worked example; analysis inputs).
   - An ECR electromagnet must therefore be sized on its own geometry, or replaced by a permanent magnet (0 W, mass
     instead). That is an owner design question (§7), not a result.
6. **Cathode.** It depends on the mode and the design.
   - Start-up heater evidence spans 45–305 W across three LaB6 designs.
   - The steady keeper is 0 W if it is off; the keeper-only bracket is 25–60 W. The steady policy on an ABEP background
     belongs to the cathode lane.
7. **Small items.** Flow control is ≈ 0.4–1.5 W per energized Xe PFCV (coil only). Housekeeping and thermal control are
   TBD, and their size is unknown, not "small".

## 6. Worked example (sourced numbers and labelled analysis inputs only; not predictions)

**(a) Discharge conversion at measured points** (28 V in, Rhodes 2024 slide 11; loads are the source's test points, so
there is no interpolation). P_bus = P_load / η.

| V_out | P_load [W] | η | P_bus [W] | P_loss [W] |
|---|---|---|---|---|
| 250 V | 249.6 | 0.8614 | 289.76 | 40.16 |
| 250 V | 600.1 | 0.8975 | 668.64 | 68.54 |
| 250 V | 1000.1 | 0.8993 | 1112.09 | 111.99 |
| 400 V | 200.1 | 0.7716 | 259.33 | 59.23 |
| 400 V | 599.9 | 0.8740 | 686.38 | 86.48 |
| 400 V | 1000.2 | 0.9072 | 1102.51 | 102.31 |

All 18 points at 28 V in are in `worked_example_v1.json`. These loads are test points of a breadboard supply. They are
not Vyovrinda discharge powers.

**(b) Magnet model exercise.** The inputs are:
- B_g = 0.015 T, the textbook's "typical radial magnetic field strength of 150 G" (Goebel & Katz p. 331, illustrative);
- every other input is an **assumed analysis input** chosen only to exercise the equations: gap 20 mm, gap area
  2 × 10⁻³ m², one iron return segment (0.2 m, 10⁻³ m², μ_r 1000, B_max 1 T), leakage 1.5, window 10⁻⁴ m², fill 0.5,
  l_mt 0.2 m, AWG 24.

Results: NI = 245.9 A, 244 turns, I = 1.008 A.

| coil T | R [Ω] | P_load [W] | continuous limit [W] |
|---|---|---|---|
| 20 °C | 4.110 | 4.174 | 4.170 |
| 100 °C | 5.402 | 5.486 | 5.481 |
| 200 °C | 7.017 | 7.126 | 7.120 |

The same geometry at the 2.45 GHz resonance field (0.08752 T) gives 142.1 W, 34.0× more. These numbers show the model
working. They are not a Vyovrinda magnet design, and the 25 W in `archengine` is neither confirmed nor refuted by them.

**(c) Ledger closure status.** Today `bus_power_ledger` cannot close any architecture:
- hall_only has efficiency evidence for `hall_discharge` only;
- rf_hall has it for `hall_discharge` and `rf_source`;
- ecr_hall has it for `hall_discharge` and `ecr_source`;
- the magnet, keeper and heater supplies, flow control, compressor, thermal control, housekeeping and the ECR magnet
  supply have no efficiency evidence;
- the discharge, RF/ECR source, thermal and housekeeping loads are TBD.

The lists are in `worked_example_v1.json → ledger_closure_status`. This is the honest state of the evidence. The
boundary module refusing to close is the intended behaviour.

## 7. Relation to repository code (read-only; nothing changed)

These code values are recorded so they are never mistaken for evidence:
- `archengine.py:627`: a fixed `P_mag = 25.0` W, independent of the magnetic design;
- `ppu.py`: a switching-loss converter model and controller 8 W + sensors 4 W, all unsourced;
- `plasma_devices.py`: generator and feed efficiencies 0.65 / 0.90 / 0.80, unsourced;
- `compressor.py`: the η_motor / P_ctrl / k_bear defaults, unsourced;
- `mass_bom.hall_magnetic_circuit`: sizes a permanent-magnet circuit with its own unsourced defaults.

Replacing any of these in `archengine` is a model change: goldens may move, it needs a HISTORY entry, and it is the
owner's decision. This lane does not do it.

The boundary lane's evidence table (`docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md` §8, in another
worktree at the time of writing) digitized the same Rhodes slide independently. This lane's extraction reproduces its
28 V values exactly: 86.14 / 88.93 / 90.14 / 89.93 % at 250 V and 77.16 / 86.09 / 88.50 / 90.72 % at 400 V.

## 8. Open questions for the owner

1. Which boundary does the RFP "< 1.5 kW" apply to? The boundary lane raises the same question.
2. What is the target bus voltage? The only sub-kW discharge-supply efficiency data found is for 24–34 V.
3. Should the Hall magnet be an electromagnet or a permanent magnet? And the ECR resonance field?
4. What is the cathode policy on an ABEP background: a steady keeper on or off, and the heater only at start-up?
5. Is a measured supply-efficiency campaign (magnet, keeper, heater, valve driver) at the Vyovrinda operating points
   acceptable as a Milestone B condition?

## 9. Reproduce

```bash
python -m pytest -q tests/test_electrical_closure.py
python docs/architecture_comparison/electrical_closure/tools/build_electrical_closure_data.py --check
python docs/architecture_comparison/electrical_closure/tools/digitize_rhodes2024_slide11.py --pdf <slides.pdf>
#   slides not redistributed; refused unless sha256 = 9f5a6c7bb36ac2ffc45026e004150304a592dadb1419284917341623588e21d9
#   (PyMuPDF; tested with 1.28.2; calibration residual <= 0.0072 %-pt and <= 0.2 W)
```
