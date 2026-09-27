# W3 common-hardware definition: H-1, C-1, common magnetic circuit, removable RF and ECR modules

| | |
|---|---|
| status | **DRAFT for owner review** (`DRAFT_PENDING_OWNER`). Nothing is approved, pre-registered or ordered |
| lane | `fo_hardware_definition` (trigger `T_PIVOT_HARDWARE_DEFINITION`, owner disposition `od_hardware_pivot`, workstream W3) |
| register (authoritative) | [`hardware_requirements_v1.json`](hardware_requirements_v1.json) |
| derived numbers | [`build_hardware_definition.py`](build_hardware_definition.py) (`--check` recomputes, `--verify-pins` checks the inputs against their repository sources) |
| test | `tests/test_hardware_definition.py` |
| base commit | `510e464` |
| milestone | supports **A** (as a precondition); what B and C need is in section 1 |

**What this is.** It is the requirements specification for the hardware of the owner's controlled common-hardware
experiment. That experiment has three configurations: HW-0 (`hall_only`), HW-RF (`rf_hall`) and HW-ECR (`ecr_hall`).
All three use **one** Hall accelerator H-1, **one** cathode C-1, **one** magnetic circuit MC-1 and **one** feed path.
Only a removable pre-ionizer module changes between them, and it mounts upstream of the same Hall inlet. The spec
covers:

- the operating envelope;
- materials for O, N₂ and O₂ service;
- Xe start and transfer to atmospheric feed;
- the interfaces: mechanical, gas, electrical, thermal, RF/microwave and magnetic;
- B(z) measurability at the actual coil currents;
- installation reproducibility;
- the list of what must be identical across arms and what may differ.

**What this is not.** It is not a thruster design and not a performance prediction. It uses no Hall closure and no
screening candidate. It is not a facility or supplier selection, and it does not rank architectures. Every number
falls into one of four kinds:

- an RFP value (`abep_sim/constants.py`);
- a value sourced from a merged lane or from open literature as recorded there, with a locator and an evidence class;
- a model-derived value from the committed script;
- a value marked **PROPOSED** or **TBD — requires …**.

No supplier, facility or lab was contacted.

## 0. Summary

- **The configuration change is confined to a module slot.** Two fixed interface planes bound the slot:
  - **IP-UP** is the end of the common feed line.
  - **IP-DN** is the H-1 rear inlet flange, just upstream of the lane-17 plane `HALL_INLET_Z0`.

  PIM-0 (the lane-25 flow-equivalent spacer), PIM-RF and PIM-ECR all fit that slot. Nothing downstream of IP-DN,
  upstream of IP-UP, on the stand or in the grounding changes between arms (HW-PIM-01).
- **Four hardware choices protect the installation budget.** Lane 25 limits installation reproducibility to
  u_inst ≤ 0.249 % at n = 4 (ln-ratio, 1σ), and that term does not average down. This register therefore proposes:
  - exchange only the module and leave H-1 on the stand (HW-SVC-04, owner choice);
  - install sham service lines, so the stand carries the same lines in every arm (HW-SVC-01);
  - calibrate in situ after every change (HW-SVC-02);
  - split the budget over five named contributors (HW-SVC-03).
- **Magnetic interaction is a first-order design question.** The ECR resonance field at 2.45 GHz is 0.0875 T, about
  4.4 × the ~200 G typical field of the xenon Hall database (context only; the denominator is not a Vyovrinda value).
  The register therefore requires four things:
  - non-ferromagnetic module structures (HW-PIM-03);
  - a B(z) map per configuration and control state at the operating coil currents (HW-MC-03);
  - an INV-B3 tolerance set by the owner (HW-PIM-06);
  - a proposed S1 coil-current scan. It measures the sensitivity S_B = d ln(T/P_bus)/d ln B, which converts that
    tolerance into a variance share (HW-MC-05).
- **Two contract and hardware gaps are found.**
  1. `bus_power_boundary_v1` has no slot for an RF assist magnet. Published air-species RF sources used about 5 mT to
     ignite O₂ and Ar at low flow (RF-IAC18-01). PIM-RF v1 is therefore proposed unmagnetized, unless the owner and the
     bus-boundary lane add a booking (HW-PIM-05, HWQ-06).
  2. A permanent-magnet ECR stage makes M0b = M0c, so the field effect H6 cannot be separated by switching (lane 37).
     The magnet type is an owner decision, and it has a flight-representativeness consequence (HW-PIM-04, HWQ-05).
- **Oxygen-related materials carry published warnings.**
  - Anode oxidation was named the main endurance concern after a PPS1350 N₂/O₂ test (Cifali et al. 2011, p. 5).
  - A PPS1350 on N₂/O₂ + 10 % Xe had flame-outs from anode oxidation after about 314 h (Andreussi et al. 2022,
    p. 24).
  - No N/O wall sputter yield exists for BN, BN-SiO₂ or SiC (lane 32).
  - LaB6 emission degrades at O₂ partial pressures in the 1e-5 Torr range below 1440 °C (Goebel & Katz Sec. 6.8.5, via
    lane 19).

  This experiment inspects the hardware; it does not qualify its life (HW-H1-04/05, HW-C1-03).
- **The absolute gate sets numerical floors on thrust per bus watt.** Sustained ≥ 12 mN at P_bus < 1.5 kW requires
  T/P_bus > 8.0 mN/kW (≤ 125 W/mN). If the registered 25 mN capability must also hold inside 1.5 kW (HWQ-10), the floor
  is > 16.67 mN/kW (≤ 60 W/mN). Any bus-compliant point also bounds the discharge current: I_d ≤ 1500 W / V_d, which is
  8.33 A at 180 V. That bound sizes the discharge supply and the C-1 emission (HW-ENV-02, HW-C1-02). These floors are
  necessary conditions, not predictions.

## 1. Milestones

| milestone | support | what this register contributes | what the next milestone needs |
|---|---|---|---|
| **A** conditional selection | YES, as a precondition | It defines the common hardware that produces the paired R_arch classes (Phase 2) and the absolute gate (Phase 3). It makes the identity across arms checkable at every configuration change (section 6). | Owner decisions HWQ-01..HWQ-15; LOCK-1 (W2, D-01..D-15); W1 test points; W4 instrument ranges and uncertainties; the H-1 design release (geometry, magnetic circuit, B(z)) and the module designs; the HRR before S1. |
| **B** physics-backed selection | PARTIAL | It requires the Hall-map inputs of the tested hardware: B(z) at the actual coil currents, as-built geometry, coil currents per reading, and module inlet diagnostics (docs/hallmap/). These are the held-out candidates that W5 may pre-register. | An admitted transport closure (credible set ∅, gate 3 FAIL); the W5 pre-registration before any data; O/O₂ chemistry (W7); the solver inflow capability at `HALL_INLET_Z0` for `rf_hall`/`ecr_hall` (lane 17 §8, GAP). |
| **C** proposal/PDR freeze | NO (inputs only) | Material and interface conditions that a flight design must also meet. | Flight mass allocation (lane 21; the RFP limit is < 40 kg for the whole system); wall and anode life against > 15,000 h (lane 32 H1–H9); cathode O-exposure qualification (lanes 10/19); flight PPU/generator efficiencies; mission closure. |

## 2. Configurations, control states and phases

| configuration | arm | module between IP-UP and IP-DN | control states |
|---|---|---|---|
| HW-0 | `hall_only` | PIM-0 flow-equivalent spacer (lane 25 HW-0) | M0: the only state reported as `hall_only` |
| HW-RF | `rf_hall` | PIM-RF (source + interstage); off-module chain: DC-fed generator, matching network, coupler at the load plane | M1 powered; M0b unpowered (control state, never `hall_only`) |
| HW-ECR | `ecr_hall` | PIM-ECR (source + interstage + ECR magnet); off-module chain: DC-fed generator, isolator, coupler, feed | M2 powered; M0b unpowered; M0c magnets on, microwaves off (electromagnet only) |
| OPTION-DIVERTER | `hall_only` | DIV-1, only if the owner selects package D-06-B | M0 inside the source installation, plus one true-HW-0 check |

**Phases** (owner disposition):

- **P1**, the Hall-only N₂ knee, needs only H-1, C-1, MC-1, FS-C, PIM-0, SVC-1 and PS-C.
- **P2** adds the modules.
- **P3** is the absolute demonstration on the delivered feed.

**PROPOSED (HWQ-15):** the IP-UP/IP-DN interface drawing and the service-line bundle are frozen *before* P1, even if the
modules arrive later. Otherwise the P1 HW-0 installation is not the one P2 compares against.

## 3. Operating envelope (HW-ENV-01..08)

| id | requirement (short) | status |
|---|---|---|
| HW-ENV-01 | Covers the owner-decided V_d set, identical in every arm (lane 17 INV-V1). PROPOSED rating up to the relaxed 350 V end, so that lane-17 Q1 needs no hardware change. V_hi is TBD. | PROPOSED |
| HW-ENV-02 | Discharge supply current ≥ the bus-compliance bound P_max / V_d,min (8.33 A at 180 V); transient margin TBD | PROPOSED |
| HW-ENV-03 | The MFC ranges cover every W1 valve-outlet test point, the knee scan and the Xe start flows. Values are by reference to W1 and lane 16 (TBD here). | TBD |
| HW-ENV-04 | P_feed and T_feed are measured at the manifold and in the module source chamber. Setpoints come from W1. A mismatch is reported, never corrected. | TBD |
| HW-ENV-05 | P_bus (`bus_power_boundary_v1` sum) < 1500 W at every P3 point. The hardware's own consumers are metered at their load planes; unmeasured common loads are LOCK-1 ledger inputs (package D-11). | RFP |
| HW-ENV-06 | H-1 designed for 12–25 mN on the delivered feed at P_bus < 1.5 kW (a design target; P3 measures it) | RFP |
| HW-ENV-07 | Gases: N₂, the N₂ + O₂ surrogate (O + O₂ supplied as O₂), and Xe. There is no atomic-O source, and that limitation is recorded with every P3 result (HWQ-11). | PROPOSED |
| HW-ENV-08 | Campaign firing hours estimated before LOCK-1. H-1 and C-1 inspected before S1, per configuration and after the campaign. Not a life demonstration. | TBD |

Flows and pressures are **never copied** here. W1 (`fo_feed_state_closure`) owns them; its planned path is
`docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json`, not merged at this base. Lane 16 and ICD
IF-A5/IF-X2 own the rest.

## 4. Configuration items and requirements

### 4.1 H-1 Hall accelerator (HW-H1-01..08)

- **HW-H1-01:** H-1 is the Vyovrinda design. This is package D-09-A, PROPOSED there. Only level-1 data serve milestone A
  without an admitted closure; a surrogate is level 3 and not verdict-bearing in lane 24. The register proposes a
  definition of *design-representative*: the channel geometry, the magnetic-circuit design, the anode/distributor and the
  wall grade of the design release. Lab structure is allowed if it is recorded and does not show in B(z).
- **HW-H1-02:** One serial unit is used throughout. Any repair or replacement downstream of IP-DN creates a new unit
  H-1′, which needs a new HW-0 reference and a new S1b. No comparison crosses it.
- **HW-H1-03:** Geometry is released with a drawing id and sha256 and measured as built before and after the campaign.
  P5, ECHT and the 0-D `HallChannel` defaults are forbidden as design-value sources (lane 17 §3).
- **HW-H1-04:** Wall grade. Flight practice is BN or BN-SiO₂ (Goebel & Katz p. 325, lane 17 EV-G9). No N/O yield exists
  on BN, BN-SiO₂ or SiC (lane 32). The grade is the owner's decision (lane 17 Q6), identical in all arms, with an
  erosion profile measured at each stage.
- **HW-H1-05:** The anode and gas distributor need oxidation evidence. After the PPS1350-TSD N₂/O₂ test the anode was
  "rusty", and anode oxidation was named the main endurance concern (Cifali et al. 2011 p. 5; hall-sustainment E06).
  About 314 h to anode-oxidation flame-outs was reported for a PPS1350 on N₂/O₂ + 10 % Xe (Andreussi et al. 2022 p. 24;
  lane 17 EV-W2). The anode is inspected after O-bearing operation, and O-bearing points run last in each block
  (package reconciliation).
- **HW-H1-06:** The distributor at `HALL_INLET_Z0` belongs to H-1 and is identical in every arm. No module part lies
  downstream of IP-DN (lane 17 INV-G3).
- **HW-H1-07:** Thermocouple points on the anode, the magnetic circuit and the body are fixed in position. T-SETTLE is
  TBD and comes from S1.
- **HW-H1-08:** The Hall-probe path reaches from beyond the exit plane down to the anode face with any module
  installed, so the map spans [0, domain]. HallThruster.jl holds B constant beyond the ends of the data (lane 17 §4).

### 4.2 MC-1 common magnetic circuit and B(z) measurability (HW-MC-01..05)

- **HW-MC-01:** One circuit and one pre-registered coil-current schedule (lane 17 INV-B1/B2). A per-arm re-trim is
  only a separately pre-registered sensitivity (lane 37 D7).
- **HW-MC-02:** The coil supplies run in current control. The coil current is recorded with every reading and
  published with the maps; this closes the P5 gap. A permanent-magnet circuit is booked as 0 W with η = 1.
- **HW-MC-03:** B(z) is mapped at the actual operating coil currents for every coil setting, configuration and control
  state (M0, M0b, M0c), before and after each configuration's block series. Each map carries its coil currents, probe
  calibration, registration (z = 0 at the anode face) and sha256. These maps are Hall-map inputs (docs/hallmap/ P6)
  and W5 held-out candidates.
- **HW-MC-04:** Hot state. Mapping is magnetostatic and cold, and the hot-state difference is TBD (lane 25 §12).
  PROPOSED: a fixed reference field sensor on MC-1, outside the plasma, logged during firing, plus a cold re-map after
  a thermal soak (HWQ-13).
- **HW-MC-05:** PROPOSED S1 addition, passed to W2. A coil-current scan on HW-0 gives S_B = d ln(T/P_bus)/d ln B. The
  owner's INV-B3 tolerance ε_B is then admissible only if |S_B|·ε_B stays within the variance share the owner assigns
  to it (HWQ-04).

### 4.3 C-1 cathode (HW-C1-01..05)

- **HW-C1-01:** A Xe-fed LaB6 hollow cathode (lane 17 §6 and lane 19, both PROPOSED; HWQ-09). One unit, mounted on H-1
  at a fixed position that does not move when a module is exchanged. Its settings are identical in every arm
  (INV-C1).
- **HW-C1-02:** The emission capability covers I_emit = I_d + I_keeper + I_interstage (lane 19; Goebel & Katz
  Eqs. 7.2-24..26) at the 8.33 A discharge-current bound. The keeper and interstage currents are TBD. The dossier's
  2–19 A Xe LaB6 lab range is context, not a rating.
- **HW-C1-03:** Poisoning protection.
  - The emitter is heated only under Xe, Xe flows whenever the emitter is hot and O₂ is present, and a purge comes
    first (lane 14).
  - Evidence: O₂ at about 1e-5 Torr degrades LaB6 below 1440 °C, and LaB6 at 1570 °C withstands up to 1e-4 Torr
    (Goebel & Katz Sec. 6.8.5, via lane 19; secondary statements of diode tests).
  - The emitter-region O partial pressure is not measurable and is TBD (lane 10 G02).
  - The RAM-HET cathode could not be ignited after two days of N₂/O₂ testing. The accessed text does not attribute
    this to poisoning (IEPC-2017-377 pp. 7-8, via lane 19).
  - C-1 is checked daily at a fixed Xe reference condition (keeper and coupling voltage), aligned with
    XE_HEALTH_CHECK (package D-15-B).
- **HW-C1-04:** The cathode gas has its own line and never crosses `HALL_INLET_Z0` (lane 17 CR-4). The air-fed cathode
  is excluded pending test (lane 14; IF-A5 `mdot_cathode_air_kgps` = 0).
- **HW-C1-05:** Keeper and heater power are metered at their load planes. The coupling voltage is recorded at every
  reading; ECHT lacks it.

### 4.4 FS-C common feed and Xe start/transfer (HW-FS-01..07)

- **HW-FS-01:** MFCs for N₂, O₂, Xe (anode) and Xe (cathode), each calibrated on its gas. Package REQ-HW-07 proposes a
  calibration interval of at most 12 months (PROPOSED there).
- **HW-FS-02:** One mixing point upstream of IP-UP, used in every arm. In the source arms all anode gas therefore passes
  the source, which can then be brought up on Xe before any atmosphere is admitted (lane 14 rationale 4).
- **HW-FS-03:** Start and transfer: ignite on Xe, move the anode smoothly from 100 % Xe to 100 % N₂ or N₂/O₂ with the
  cathode on Xe, and keep every step reversible. This order has direct published support: "The PPS1350-TSD was always
  ignited with xenon. After ignition, a smooth transition from 100% xenon to 100% nitrogen or N2/O2 mixture at the anode
  was carried out; the cathode continued to work with xenon" (Cifali et al. 2011, as quoted by lane 14). The ramp rates
  are lane-14 parameters and are TBD. The same capability re-ignites the discharge after every extinction in the P1
  knee scan.
- **HW-FS-04:** A manifold capacitance manometer in every configuration. Each module has a source-chamber port, and
  PIM-0 carries the same port.
- **HW-FS-05:** Flow equivalence of PIM-0: the same MFCs and setpoints and the same distributor. The cold manifold
  pressure is measured per configuration in S1a and reported as part of R_install, never corrected. The leak-rate
  limit is TBD.
- **HW-FS-06:** One gas isolator (voltage break) upstream of IP-UP, rated to HW-ENV-01 plus a margin (TBD).
- **HW-FS-07:** O₂ service cleanliness of FS-C and the modules. Facility O₂ compatibility is package REQ-FAC-04.

### 4.5 Removable modules (HW-PIM-01..13)

| id | requirement (short) | status |
|---|---|---|
| HW-PIM-01 | Same flange pattern, alignment features, seals and torque for every module. A module exchange changes nothing else. | PROPOSED |
| HW-PIM-02 | PIM-0 replicates the module envelope and gas path, with no source and no magnet. It is non-ferromagnetic and has the same potential at IP-DN. | PROPOSED |
| HW-PIM-03 | Module and spacer structures are non-ferromagnetic; the only magnet is the declared one. Checked by M0 vs M0b B(z). | PROPOSED |
| HW-PIM-04 | ECR magnet type is the owner's choice. An electromagnet gives M0c and is booked as coil power. A permanent magnet gives M0b = M0c at 0 W. The test type matches the flight intent, or the ledger carries the flight value. | PROPOSED |
| HW-PIM-05 | PIM-RF v1 unmagnetized, because the boundary has no RF-magnet slot. 5 mT assist field reported (RF-IAC18-01). | PROPOSED |
| HW-PIM-06 | Combined field in the channel = HW-0 B(z) within the owner's INV-B3 tolerance; otherwise the arm is not comparable | TBD |
| HW-PIM-07 | I_src Faraday access at the source exit (lane 25 M5); optional OES window | PROPOSED |
| HW-PIM-08 | Operable from P_lo to P_hi at W1 flows, on Xe and on the working gases (lane 25 G-SRC). P_hi is TBD (source allocation). | TBD |
| HW-PIM-09 | Module waste heat to H-1 is isolated or instrumented; anode temperature logged in every arm | PROPOSED |
| HW-PIM-10 | Plasma-facing module materials O₂-compatible. No accessed source measures RF tube, antenna or shield erosion. Inspected before and after; deposits on H-1 recorded. | TBD |
| HW-PIM-11 | Source frequencies not selected (RF evidence spans about 1–40.68 MHz; ECR candidates 2.45–5.8 GHz) | TBD |
| HW-PIM-12 | DC-fed generators; net power measured at the load plane or reconstructed from an S1a-characterised loss (lane 25 M3; `rf_source`/`ecr_source` load planes) | PROPOSED |
| HW-PIM-13 | DIV-1 (only if D-06-B): no-vent switch, flow-equivalent in both positions, non-ferromagnetic, one check against a true HW-0. Space for it is reserved at the interface planes. | PROPOSED |

### 4.6 Electrical interfaces (HW-ELEC-01..03)

- **HW-ELEC-01:** The discharge runs between the anode and cathode common, with the thruster floating (Goebel & Katz
  Eqs. 7.2-21/22, via lane 17 §5). Supply topology, grounding and routing are identical in every arm.
- **HW-ELEC-02:** The potential of each module body and of any interstage electrode is declared (HWQ-07) and is
  identical for PIM-0 at IP-DN. Any interstage current is measured, because it enters the lane-19 cathode current
  budget.
- **HW-ELEC-03:** RF and microwave returns are separated from the discharge return. Generator pickup on common
  diagnostics is quantified with matched dummy loads (lane 06 DUMMY_LOAD_PICKUP, adopted in S1a).

### 4.7 Installation reproducibility and service lines (HW-SVC-01..05)

- **HW-SVC-01:** Every line crossing the stand is present in every configuration. The arm-specific lines are shams in
  the other arms. This is an engineering rationale (assumed): the installation term G5 does not average down
  (lane 25 §6.4).
- **HW-SVC-02:** In-situ calibration under vacuum after every configuration change, with ≥ 10 calibrations before and
  ≥ 10 after operation (package REQ-HW-01; Polk et al. 2017 via lane 25 M1). Module mass differences change the stand
  load.
- **HW-SVC-03:** u_inst ≤ u_inst,max at the n fixed at LOCK-2 (package REQ-HW-04), unless D-06-B is adopted. The
  PROPOSED sub-allocation uses five equal root-sum-square shares:
  - c1: stand calibration and zero;
  - c2: thrust-axis alignment;
  - c3: magnetic circuit / B(z);
  - c4: gas path and leaks;
  - c5: service lines, thermal and electrical environment.

  Achievability is TBD and requires S1b.
- **HW-SVC-04:** PROPOSED procedure: H-1 stays on the stand and only the module is exchanged. S1b must replicate the
  adopted procedure; lane 25's current S1b text re-installs the thruster mount (HWQ-01).
- **HW-SVC-05:** Interaction of the module or MC-1 magnets with the stand's magnetic parts is checked by in-situ
  calibration with the ECR module installed. The details are TBD and belong to W4.

## 5. Derived numbers (model-derived; `build_hardware_definition.py`)

All values come from `derived_numbers.inputs`. Every input carries its source and evidence class, and
`--verify-pins` checks each one against the file it came from.

| quantity | value | basis |
|---|---|---|
| ECR resonance field, 2.45 GHz | 0.08752 T | 2πf m_e/e (CODATA 2022 as in the ECR matrix); cross-check ECR-D001 |
| ECR resonance field, 5.8 GHz | 0.2072 T | same |
| B_res(2.45 GHz) / 200 G | 4.376 | context only; 200 G is the xenon-database typical field (lane 17 EV-B4, inferred) |
| RF assist field / 200 G | 0.25 | context only; the 5 mT is on the RF-source axis (RF-IAC18-01) |
| T/P_bus floor at 12 mN | > 8.0 mN/kW (P_bus/T < 125 W/mN) | RFP ceiling; necessary, not sufficient |
| T/P_bus floor at 25 mN | > 16.67 mN/kW (< 60 W/mN) | only if HWQ-10 requires 25 mN inside 1.5 kW |
| I_d bound at 180 / 200 / 250 / 300 / 305 / 350 V | 8.333 / 7.5 / 6.0 / 5.0 / 4.918 / 4.286 A | I_d ≤ P_max/V_d at any bus-compliant point (η ≤ 1, loads ≥ 0, `arch_boundary.py`) |
| per-contributor installation share (n = 4 / 6 / 8) | 0.111 % / 0.114 % / 0.116 % (ln-ratio, 1σ) | lane-25 u_inst,max / √5 (PROPOSED equal shares) |
| alignment-angle reproducibility using one share (n = 4 / 6 / 8) | 2.70° / 2.74° / 2.76° | arccos(exp(−share)). First-order geometry; it shows that alignment alone is not the demanding term. It does not claim which term dominates. |

## 6. What must be identical, and what may differ

| must be identical across HW-0 / HW-RF / HW-ECR | rule | how it is checked |
|---|---|---|
| H-1 unit, geometry, anode/distributor, wall grade | lane 17 INV-G1..G3 | part log, profilometry |
| MC-1 and coil-current schedule | INV-B1, INV-B2 | B(z) map per configuration; coil currents per reading |
| C-1 unit, position, gas, flow, keeper, heater | INV-C1 | part log, daily Xe reference |
| V_d set, supply topology | INV-V1, INV-V2 | supply records |
| feed: MFCs, bottles, mixing point, isolator, line to IP-UP, setpoints | INV-F1; lane 25 FS-common | calibration, cold-flow manifold pressure |
| stand, mount, service lines (with shams), grounding, routing | lane 25 §2 | in-situ calibration |
| facility, gauges, diagnostics and positions | lane 25 §2; INV-L1 | W4 / facility records |
| ledger efficiencies of common components | INV-P1 | LOCK-1 |

**May differ:**

- the module and its off-module chain;
- the bus components `rf_source`, `ecr_source`, `ecr_magnet`;
- the inlet state at `HALL_INLET_Z0` (a result, not a setting);
- consequences that are recorded but never equalised: module waste heat, fringe field within the INV-B3 tolerance,
  module erosion products, and extra atomic O at H-1/C-1 from O₂ dissociation in the source (lane 19 §6).

**Never a hardware variable:** P5 calibration nuisance (registration, coil shape, beam-efficiency reading,
facility-ingestion interpretation).

**At every configuration change:**

- the part log;
- the IP torque and alignment record;
- a leak check and cold-flow check;
- a B(z) map;
- an in-situ calibration;
- a dummy-load pickup check (source arms);
- an anode and wall inspection after O-bearing operation;
- the XE_HEALTH_CHECK, if D-15-B is adopted.

**Hardware readiness review (HRR, PROPOSED).** It sits after LOCK-1 and hardware delivery, before S1. Entry
criteria:

- the owner decisions are recorded;
- the H-1 design release is available;
- the IP-UP/IP-DN interface drawing is frozen;
- the P1 TBDs are resolved before Phase 1, and the P2 TBDs before the first module;
- the W4 instrument list exists;
- the W5 pre-registration is filed before any data.

## 7. Owner questions

| id | question |
|---|---|
| HWQ-01 | Configuration-change procedure (module only vs H-1 re-mount) and D-06 (A spacer / B diverter / C CFG-A / D CFG-B) |
| HWQ-02 | D-09 Vyovrinda design vs surrogate, and the proposed definition of "design-representative" |
| HWQ-03 | Rate H-1, C-1, the supply and the isolator to 350 V |
| HWQ-04 | INV-B3 tolerance, and whether to add the S_B coil-current scan to LOCK-1 |
| HWQ-05 | ECR electromagnet vs permanent magnet, including flight representativeness |
| HWQ-06 | RF module unmagnetized vs a boundary slot for an RF assist magnet |
| HWQ-07 | Potential of the module body / interstage electrode |
| HWQ-08 | Anode/distributor material or coating, and the wall grade |
| HWQ-09 | C-1 type and emission rating |
| HWQ-10 | Does the 25 mN capability have to hold within P_bus < 1.5 kW? |
| HWQ-11 | Atomic-O representativeness of Phase 3 (surrogate with a stated limitation vs a dedicated O source) |
| HWQ-12 | Sham service lines |
| HWQ-13 | Hot-state B reference sensor |
| HWQ-14 | Spares policy (a replaced unit becomes a new unit) |
| HWQ-15 | Freeze the module interfaces before Phase 1 |

## 8. Relation to parallel workstreams (by path; none is required by this register or its test)

| workstream | relation |
|---|---|
| W1 `fo_feed_state_closure` | Flows, P_feed, T_feed and x_s test points. Planned path `docs/architecture_comparison/feed_state_closure/`, not merged here; values are not copied. |
| W2 `fo_lock1_decision_brief` | Receives HWQ-01..15 and the proposed S1 addition HW-MC-05 |
| W4 `fo_instrumentation_definition` | Instrument ranges and uncertainties (thrust stand, P_bus metering, B(z) probe, MFCs, gauges, thermocouples); HW-MC-03/04, HW-SVC-05 |
| W5 `fo_hall_validation_prereg_draft` | Decides which of B(z), geometry, I_d, T, species and more are held-out evidence, before any data |
| W7 `fo_o_o2_chemistry_v0` | Chemistry for the air surrogate |

Merged inputs:

- lane 25 `docs/architecture_comparison/minimum_decisive_experiment/`
- `fo_experiment_package` `docs/architecture_comparison/experiment_package/`
- lane 06 `docs/architecture_comparison/experiment_protocol/`
- lane 37 `docs/experiments/`
- lane 16 `docs/architecture_comparison/feed_envelope/`
- lane 33 `docs/interfaces/UPSTREAM_ICD.md`
- lane 14 `docs/controls/`
- lane 17 `docs/architecture_comparison/hall_reference/`
- lane 19 `docs/architecture_comparison/cathode_integration/`
- lane 10 `docs/evidence/cathode/`
- lane 32 `docs/evidence/wall_life/`
- lane 11 `abep_sim/arch_boundary.py`
- lane 24 `docs/architecture_comparison/hard_gates/`
- lane 35 `docs/hallmap/`
- lane 13 `docs/chemistry/o_o2/`
- D-X5 `docs/chemistry/n2_domain_extension/dx5/`
- Bundle 1 `docs/milestones/bundle1/` (NO_BASELINE_YET)

## 9. Compliance

- No Hall closure, screening candidate (`sgb-screen-*`) or withdrawn 0-D number is used. No performance is predicted
  and no architecture is ranked or eliminated.
- P5 calibration nuisance is never a hardware variable. Hall-closure uncertainty does not reach the feed side.
- Literature is cited as recorded by the merged lanes; this lane re-read none of it. Each reference in the JSON says
  which lane recorded it. Every value that is neither sourced nor derived is PROPOSED or TBD.
- The register is pure data plus one standard-library generator. Nothing is wired into `archengine`, and no frozen
  data, golden, prereg, campaign or `hallthruster_bridge/` file is touched.
