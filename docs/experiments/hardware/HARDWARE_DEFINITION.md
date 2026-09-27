# W3 common-hardware definition: H-1, C-1, common magnetic circuit, removable RF and ECR modules

| | |
|---|---|
| status | **DRAFT for owner review** (`DRAFT_PENDING_OWNER`). Nothing is approved, pre-registered or ordered |
| lane | `fo_hardware_definition` (trigger `T_PIVOT_HARDWARE_DEFINITION`, owner disposition `od_hardware_pivot`, workstream W3) |
| register (authoritative) | [`hardware_requirements_v1.json`](hardware_requirements_v1.json) |
| derived numbers | [`build_hardware_definition.py`](build_hardware_definition.py) (`--check` recomputes, `--verify-pins` checks the inputs against their repository sources) |
| test | `tests/test_hardware_definition.py` |
| base commit | `7d37337` (A3 W3 integration review; C5 integration at `f61912e`; first version at `510e464`) |
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
- **H-1 carries the AO/lifetime and magnet/coil provisions from the start (control C5).** The merged AO/lifetime
  register (`AOL-*`) and magnet/coil qualification (`MCQ-*`) are integrated as 25 new requirements (section 4.8):
  - witness coupons: plume holder, anode, cathode, magnetic-circuit pair and a per-arm interstage set;
  - a replaceable, serialized anode and replaceable exit-region wall rings with fiducials;
  - cathode-exposure monitoring provisions and post-test metrology provisions;
  - coil insulation, hot-spot measurement, a permanent-magnet demagnetization test at the actual permeance
    coefficient, the soft-magnetic pole material and the ECR-magnet interaction.

  Every source requirement has a disposition (adopted / partially adopted / aligned / not adopted with the reason).
  No existing id or number changed.
- **The absolute gate sets numerical floors on thrust per bus watt.** Sustained ≥ 12 mN at P_bus < 1.5 kW requires
  T/P_bus > 8.0 mN/kW (≤ 125 W/mN). If the registered 25 mN capability must also hold inside 1.5 kW (HWQ-10), the floor
  is > 16.67 mN/kW (≤ 60 W/mN). Any bus-compliant point also bounds the discharge current: I_d ≤ 1500 W / V_d, which is
  8.33 A at 180 V. That bound sizes the discharge supply and the C-1 emission (HW-ENV-02, HW-C1-02). These floors are
  necessary conditions, not predictions.

## 1. Milestones

| milestone | support | what this register contributes | what the next milestone needs |
|---|---|---|---|
| **A** conditional selection | YES, as a precondition | It defines the common hardware that produces the paired R_arch classes (Phase 2) and the absolute gate (Phase 3). It makes the identity across arms checkable at every configuration change (section 6). | Owner decisions HWQ-01..HWQ-21; the C5 provisions designed in and baselined (section 4.8); LOCK-1 (W2, D-01..D-15); W1 test points; W4 instrument ranges and uncertainties; the H-1 design release (geometry, magnetic circuit, B(z)) and the module designs; the HRR before S1. |
| **B** physics-backed selection | PARTIAL | It requires the Hall-map inputs of the tested hardware: B(z) at the actual coil currents, as-built geometry, coil currents per reading, and module inlet diagnostics (docs/hallmap/). These are the held-out candidates that W5 may pre-register. | An admitted transport closure (credible set ∅, gate 3 FAIL); the W5 pre-registration before any data; O/O₂ chemistry (W7); the solver inflow capability at `HALL_INLET_Z0` for `rf_hall`/`ecr_hall` (lane 17 §8, GAP). |
| **C** proposal/PDR freeze | NO (inputs only) | Material and interface conditions that a flight design must also meet. | Flight mass allocation (lane 21; the RFP limit is < 40 kg for the whole system); wall and anode life against > 15,000 h (lane 32 H1–H9); cathode O-exposure qualification (lanes 10/19); flight PPU/generator efficiencies; mission closure; the coil EIS life basis at the measured hot spot and permanent-magnet irreversible-loss data (HW-MC-07, HW-MC-09); ground AO exposure results (AOL-EX-01..03). |

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

### 4.8 Control C5: AO/lifetime and magnet/coil provisions carried by H-1 from the start

The owner's execution directive (control C5) requires H-1 to carry witness coupons, replaceable channel and anode
components, cathode-exposure monitoring and post-test metrology provisions from the start. It also integrates the
magnet/coil qualification. The sources are the merged registers `docs/experiments/lifetime_ao/ao_lifetime_register_v1.json`
(sha256 `237c99aa…`) and `docs/experiments/magnet_coil/magnet_coil_qualification_v1.json` (sha256 `53e92f45…`).
The machine-readable disposition of every source item is `c5_integration.rows` in the register.

| id | item | status | requirement (short) | traces to |
|---|---|---|---|---|
| HW-H1-09 | H-1 | TBD | Anode-material witness at the distributor, only if it alters neither flow path nor anode area; otherwise the replaceable anode is the witness | AOL-WC-02, AOL-M01, AOL-M08 |
| HW-H1-10 | H-1 | PROPOSED | Replaceable, serialized anode with torque/alignment procedure and baseline metrology; each removal creates H-1′ (HW-H1-02) | AOL-RC-01, AOL-M01 |
| HW-H1-11 | H-1 | PROPOSED | Replaceable exit-region wall rings with profilometry fiducials; profile at S1 end, phase boundaries, campaign end | AOL-RC-03, AOL-PM-03, AOL-M02, AOL-M03 |
| HW-H1-12 | H-1 | PROPOSED | Thermocouples on anode, each wall ring and next to each witness coupon (extends HW-H1-07) | AOL-CX-07 |
| HW-H1-13 | H-1, C-1, MC-1, PIM-*, SVC-1 | PROPOSED | Serial numbers and position marks on every coupon and replaceable part; baseline before first ignition; removal only at pre-registered boundaries; sealed dry transfer with custody record (methods are W4's) | AOL-PM-01, AOL-PM-04, AOL-DC-01, AOL-PT-04 |
| HW-H1-14 | H-1, MC-1 | PROPOSED | Coupons cut from the same material lots as the installed parts (wall, anode, pole, magnet + coating, magnet-wire enamel) | AOL-EX-02, MCQ-AO-01, MCQ-QT-04, AOL-WC-01, AOL-WC-04 |
| HW-MC-06 | MC-1 | PROPOSED | Plume-exposed and shadowed pole-material coupons with thermocouples; B(z) map with/without them (the coupon is ferromagnetic); pole-face inspection access | AOL-WC-04, AOL-PM-08, AOL-M06, MCQ-AO-01 |
| HW-MC-07 | MC-1 | PROPOSED | Coil EIS with a stated thermal class and endurance basis, compared with the measured hot spot; life basis ≥ RFP 15,000 h + owner margin | MCQ-W3-01, MCQ-QT-01, MCQ-PT-04, MCQ-S1-01 |
| HW-MC-08 | MC-1, PS-C | TBD | Hot-spot limit = EIS class − owner margin; max coil current, hot-spot and magnet temperatures and abort rule on the S1 run sheet | MCQ-W3-02, MCQ-PT-01, MCQ-S1-08, MCQ-OQ-03 |
| HW-MC-09 | MC-1 | PROPOSED | Permanent magnets in MC-1 (if any): working point above the knee at the actual permeance coefficient incl. the opposing coil field; per-lot irreversible-loss test before S1 | MCQ-W3-03, MCQ-QT-02, MCQ-PT-02, MCQ-S1-05 |
| HW-MC-10 | MC-1 | PROPOSED | Magnet coating/encapsulation; outgassing screen of coil, potting, leads and coatings; bake-out of porous ceramic windings per the supplier instruction | MCQ-W3-04, MCQ-W3-05, MCQ-QT-03, MCQ-PT-03, MCQ-S1-04, AOL-M06 |
| HW-MC-11 | MC-1 | TBD | Turn/layer voltage below the wire rating with owner margin; ground insulation independent of the enamel | MCQ-W3-06, MCQ-QT-08 |
| HW-MC-12 | MC-1 | PROPOSED | No ferromagnetic conductor, fastener or structure near MC-1 unless model + M0/M0b map show it within INV-B3 | MCQ-W3-07 |
| HW-MC-13 | MC-1 | TBD | Soft-magnetic pole/core grade selected with sourced B-H, temperature, outgassing and O data (grade TBD, HWQ-18) | MCQ-OQ-05, MCQ-QT-07, AOL-WC-04 |
| HW-MC-14 | MC-1, PS-C | TBD | Per-coil 4-wire potential leads + hot-spot thermocouples; bench hot-spot/average offset before S1; coil I and V per reading; B(z) records carry temperatures | MCQ-W4-01, MCQ-W4-02, MCQ-W4-03, MCQ-QT-06, MCQ-S1-02 |
| HW-MC-15 | MC-1 | PROPOSED | Cold and heated-soak B(z) maps at actual coil currents before S1; hot reference sensor in S1 | MCQ-QT-07, MCQ-S1-06, AOL-PM-08 |
| HW-MC-16 | MC-1 | TBD | Sacrificial coil from the same lots, thermally cycled before S1 | MCQ-QT-05, MCQ-S1-03 |
| HW-C1-06 | C-1 | PROPOSED | Keeper-material, unheated LaB6 and insulator coupons on the C-1 mount (unheated LaB6 is not a poisoning witness) | AOL-WC-03, AOL-M04, AOL-M05 |
| HW-C1-07 | C-1 | PROPOSED | Cathode temperature provision (now HW-C1-09), gas-sampling port to the RGA, logged heater/keeper supplies, hot-emitter O-exposure log | AOL-CX-02, AOL-CX-03, AOL-CX-04, AOL-CX-05 |
| HW-C1-09 | C-1 | PROPOSED | Cathode-tube thermocouple (mandatory) + emitter pyrometer line of sight where mechanically possible; the tube reading is never called emitter temperature; if there is no view, emitter temperature is reported as unmeasured (owner addendum A3) | AOL-CX-04, INS-23 |
| HW-C1-08 | C-1 | PROPOSED | C-1 disassemblable for insert, orifice and keeper inspection at campaign end | AOL-PM-05, AOL-M04, AOL-M05 |
| HW-PIM-14 | PIM-0, PIM-RF, PIM-ECR | PROPOSED | Per-arm interstage witness set at an identical position in PIM-0/RF/ECR, on the module side of IP-DN; exchanged only at arm boundaries (HWQ-16) | AOL-WC-05, AOL-M01, AOL-M07, AOL-M10, AOL-OQ-01 |
| HW-PIM-15 | PIM-ECR | TBD | ECR magnet: fringe field in the channel and demagnetization exposure at max Hall coil current analysed before HWQ-05; PM ECR magnets meet HW-MC-09/10 | MCQ-W3-08, MCQ-QT-09, MCQ-W3-03, MCQ-W3-04, MCQ-OQ-06 |
| HW-ELEC-04 | H-1, PS-C | PROPOSED | Separate anode sense lead for 4-wire anode resistance between blocks | AOL-RC-02, AOL-PT-02 |
| HW-ELEC-05 | H-1, MC-1, FS-C | TBD | Insulation-resistance/withstand test access (anode isolator, coils, harness, gas isolator); one procedure shared with MCQ-QT-08 | AOL-PM-06, MCQ-QT-08, MCQ-AO-02, MCQ-S1-07 |
| HW-SVC-06 | SVC-1 | PROPOSED | Near-exit plume witness holder outside the beam core, never moved between arms; no effect on B(z), flow or stand tare | AOL-WC-01, AOL-WC-06, AOL-M02, AOL-M03, AOL-M08, AOL-M11 |

**Adopted / not-adopted table** (`c5_integration.rows`; A = adopted, AP = adopted in part, AL = aligned with an
existing requirement, NA = not adopted):

| source id | disposition | W3 requirement(s) | note / what is needed |
|---|---|---|---|
| AOL-WC-01 | AP | HW-SVC-06, HW-H1-14 | holder, positions and non-interference adopted; coupon metrology is W4's (AOL-WC-01 adopter W4 part) |
| AOL-WC-02 | A | HW-H1-09 | conditional on placement without altering flow path or anode area; fallback HW-H1-10 |
| AOL-WC-03 | A | HW-C1-06 | coupons and fixed positions adopted; metrology W4 |
| AOL-WC-04 | A | HW-MC-06, HW-H1-12 | with an added B(z) with/without-coupon check because the coupon is ferromagnetic |
| AOL-WC-05 | A | HW-PIM-14 | mounted on the module side of IP-DN so the exchange does not create H-1'; classification HWQ-16 |
| AOL-WC-06 | AP | HW-SVC-06 | shadowed control (c) is on the HW-SVC-06 holder — needed: controls (a) chamber wall, (b) beam-dump facing and (d) lab-stored are facility/W4 items, outside W3 hardware |
| AOL-RC-01 | A | HW-H1-10 | removal creates H-1' (HW-H1-02) |
| AOL-RC-02 | A | HW-ELEC-04 | lead and feedthrough adopted; instrument W4 |
| AOL-RC-03 | A | HW-H1-11 | ring geometry becomes part of the HW-H1-03 release |
| AOL-RC-04 | NA | — | owner decision (AOL-OQ-02) recorded as HWQ-17 — needed: owner approval before LOCK-1; if approved, a new HW-H1 requirement with the inserts identical in all arms |
| AOL-CX-01 | AL | HW-C1-03 | daily Xe reference check already in HW-C1-03 |
| AOL-CX-02 | AP | HW-C1-07, HW-C1-05 | metered heater/keeper supplies adopted; the start log is W4's DAQ |
| AOL-CX-03 | AP | HW-C1-07 | sampling port adopted; RGA is W4's |
| AOL-CX-04 | AP | HW-C1-07, HW-C1-09 | tube thermocouple mandatory + pyrometer view where possible (A3, HW-C1-09); sensor, calibration, DAQ W4 (INS-23) |
| AOL-CX-05 | AL | HW-C1-03, HW-C1-07 | interlock rule in HW-C1-03; log W4 |
| AOL-CX-06 | NA | — | data-logging requirement with no hardware provision beyond the existing I_d, feed and cathode metering (HW-C1-05, HW-FS-01) — needed: W4 DAQ (extinction records with feed composition and cathode state) |
| AOL-CX-07 | A | HW-H1-12 | extends HW-H1-07 |
| AOL-PM-01 | AP | HW-H1-13 | serialization, position marks and baseline-before-first-ignition adopted; methods W4 |
| AOL-PM-02 | NA | — | metrology procedure — needed: W4 / metrology lab |
| AOL-PM-03 | AL | HW-H1-04, HW-H1-11, HW-ENV-08 | erosion profile already required by HW-H1-04; fiducial rings added by HW-H1-11 |
| AOL-PM-04 | AP | HW-H1-13 | sealed dry transfer and custody adopted; analyses W4 |
| AOL-PM-05 | A | HW-C1-08 |  |
| AOL-PM-06 | A | HW-ELEC-05 | shared procedure with MCQ-QT-08 (MCQ-AO-02) |
| AOL-PM-07 | NA | — | facility-dependent SEE measurement; W3 only supplies same-lot coupons (HW-H1-14) — needed: owner facility choice (lane 32 H9) |
| AOL-PM-08 | AL | HW-MC-03, HW-MC-04, HW-MC-15, HW-MC-06 | B(z) re-map already required; pole-face inspection access added in HW-MC-06 |
| AOL-PM-09 | NA | — | optical-property measurement of exterior coupons — needed: owner lab (with AOL-EX-01) |
| AOL-EX-01 | NA | HW-H1-14 | ground AO exposure is off the S1 critical path; W3 supplies lot-traceable coupons — needed: owner facility and target fluence (AOL-OQ-05, control C4) |
| AOL-EX-02 | AP | HW-H1-14 | lot traceability adopted; the exposure is an owner/facility item — needed: owner facility |
| AOL-EX-03 | NA | — | heated-emitter exposure is an owner/facility item; the in-thruster alternative is HWQ-21 — needed: owner decision HWQ-21 (AOL-OQ-04) |
| AOL-DC-01 | AP | HW-H1-13 | serial numbers and position marks adopted; the register is W4 + W5 |
| AOL-DC-02 | NA | — | record format — needed: W4 (schemas/thermal_life/inputs_v1.json measured_hardware fields) |
| AOL-LF-01 | AL | — | compliance.no_life_extrapolation (control C6) |
| AOL-LF-02 | NA | — | pre-registration of endurance segments — needed: owner + W5 pre-registration; HW-ENV-08 gives the campaign-hours estimate |
| MCQ-W3-01 | A | HW-MC-07 |  |
| MCQ-W3-02 | A | HW-MC-08 | margin TBD (owner) |
| MCQ-W3-03 | A | HW-MC-09, HW-PIM-15 | demagnetization at the actual permeance coefficient incl. the opposing coil field |
| MCQ-W3-04 | A | HW-MC-10, HW-PIM-15 |  |
| MCQ-W3-05 | A | HW-MC-10 | conditional on a ceramic-insulated winding (HWQ-20); supplier bake values are cited in the MCQ register, not restated |
| MCQ-W3-06 | A | HW-MC-11 | margin TBD (owner) |
| MCQ-W3-07 | A | HW-MC-12 | extends HW-PIM-03 |
| MCQ-W3-08 | A | HW-PIM-15 | precondition for HWQ-05 |
| MCQ-W4-01 | AP | HW-MC-14 | leads and thermocouple points adopted; channel map W4 |
| MCQ-W4-02 | AL | HW-MC-02, HW-MC-14 |  |
| MCQ-W4-03 | AP | HW-MC-14 | content of the map record adopted; record schema W4 |
| MCQ-TL-01 | NA | — | adopter lane_15_thermal_life — needed: lane 15 limits_v1 update |
| MCQ-TL-02 | NA | — | adopter lane_15_thermal_life — needed: lane 15 EIS record semantics |
| MCQ-TL-03 | NA | HW-MC-14 | adopter lane_15_thermal_life; HW-MC-14 produces the measured offset it needs — needed: lane 15 |
| MCQ-TL-04 | NA | — | adopter lane_15_thermal_life — needed: lane 15, after HWQ-20 selects a conductor |
| MCQ-TL-05 | NA | — | adopter lane_15_thermal_life; this register keeps both magnet types open (HWQ-05, HWQ-19), so the lane-15 node gap stays open — needed: lane 15 permanent-magnet Hall node and ECR electromagnet node |
| MCQ-AO-01 | A | HW-MC-06, HW-H1-14 |  |
| MCQ-AO-02 | A | HW-ELEC-05 |  |
| MCQ-QT-01 | A | HW-MC-07 |  |
| MCQ-QT-02 | A | HW-MC-09, HW-PIM-15 |  |
| MCQ-QT-03 | A | HW-MC-10 |  |
| MCQ-QT-04 | A | HW-H1-14, HW-MC-06 |  |
| MCQ-QT-05 | A | HW-MC-16 |  |
| MCQ-QT-06 | A | HW-MC-14 |  |
| MCQ-QT-07 | A | HW-MC-15 |  |
| MCQ-QT-08 | A | HW-ELEC-05, HW-MC-11 |  |
| MCQ-QT-09 | A | HW-PIM-15 |  |
| MCQ-S1-01 | A | HW-MC-07 | HRR entry criterion |
| MCQ-S1-02 | A | HW-MC-14 | HRR entry criterion |
| MCQ-S1-03 | A | HW-MC-16 | HRR entry criterion |
| MCQ-S1-04 | A | HW-MC-10 | HRR entry criterion |
| MCQ-S1-05 | A | HW-MC-09, HW-PIM-15 | HRR entry criterion (only if a permanent magnet is installed) |
| MCQ-S1-06 | A | HW-MC-15 | HRR entry criterion |
| MCQ-S1-07 | A | HW-ELEC-05 | HRR entry criterion |
| MCQ-S1-08 | A | HW-MC-08 | HRR entry criterion |
| MCQ-OQ-01 | A | — | recorded as HWQ-19 |
| MCQ-OQ-02 | A | — | recorded as HWQ-20 |
| MCQ-OQ-03 | A | HW-MC-08 | recorded as HWQ-20 |
| MCQ-OQ-04 | NA | — | evidence-access route — needed: owner, under control C4 |
| MCQ-OQ-05 | A | HW-MC-13 | recorded as HWQ-18 |
| MCQ-OQ-06 | AL | HW-PIM-04, HW-PIM-15 | same decision as HWQ-05 |
| AOL-OQ-01 | A | HW-PIM-14 | recorded as HWQ-16 |
| AOL-OQ-02 | A | — | recorded as HWQ-17 |
| AOL-OQ-03 | AL | HW-H1-05, HW-H1-09 | anode material candidates remain an owner/design choice under HW-H1-05 |
| AOL-OQ-04 | A | HW-C1-06 | recorded as HWQ-21 |
| AOL-OQ-05 | NA | — | ground AO facility and fluence — needed: owner, control C4 |
| AOL-OQ-06 | NA | — | closed-access acquisition — needed: owner, control C4 |
| AOL-PT-01 | NA | — | run rule (stop and inspect after a flame-out); not a hardware requirement — needed: owner + W5; borescope access, if wanted, would be a new H-1 requirement |
| AOL-PT-02 | AL | HW-ELEC-04 | threshold TBD until S1 baseline (LOCK-2) |
| AOL-PT-03 | AL | HW-C1-03 | threshold TBD until S1 day-to-day scatter (LOCK-2) |
| AOL-PT-04 | AL | HW-H1-13 | removal cadence |
| MCQ-PT-01 | AL | HW-MC-08 | TBD owner |
| MCQ-PT-02 | AL | HW-MC-09 | TBD owner |
| MCQ-PT-03 | AL | HW-MC-10 | PROPOSED screen referenced, not restated |
| MCQ-PT-04 | AL | HW-MC-07 | RFP firing time + owner margin |

**Why some items are not adopted.** They are procedures, instruments or records owned by W4, W5, lane 15 or
the owner's facility channel (for example dehydrated-mass protocol, RGA, DAQ, ground AO exposure, lane-15 grade records).
W3 adopts only the hardware provision each one needs. Alternative wall inserts (AOL-RC-04) wait for the owner (HWQ-17).

**Re-verification of the AO register's unmerged W3 ids.** The AO register marked 15 W3 references as
UNVERIFIED_UNMERGED_DRAFT. All are confirmed against this register (HW-C1-05 is related, not identical: it covers keeper
metering, and keeper erosion is AOL-PM-05 / HW-C1-08). See `c5_integration.ao_register_unmerged_id_reverification`.

**What changed in existing requirements.** Nothing in text or value: only `traces_to` entries were added (HW-C1-03, HW-C1-05,
HW-H1-02, HW-H1-04, HW-H1-05, HW-H1-07, HW-MC-02..04, HW-PIM-03, HW-PIM-04, HW-ENV-08). No adopted item forced a numeric change.

### 4.9 Owner addendum A3: bounded W3 integration review (no H-1 redesign)

Owner addendum A3 (`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json`,
`next_execution.W3_integration_review`) asks for one bounded check. H-1 must carry ten named provisions, checked against
N1 (AO/lifetime register v3), N3 (magnet/coil qualification v1) and W4 (instrumentation v1-r2). The sha256 pins are in
`w3_integration_review.reviewed_against`.

| provision | status | HW ids | traces (AOL / MCQ / INS) |
|---|---|---|---|
| replaceable serialized anode / gas distributor | PRESENT | HW-H1-10, HW-H1-13 | AOL-RC-01, AOL-PM-01, INS-19, INS-20, INS-21 |
| 4-wire anode-resistance leads | PRESENT | HW-ELEC-04 | AOL-RC-02, INS-21, INS-P-06 |
| replaceable / fiducial exit wall rings | PRESENT | HW-H1-11 | AOL-RC-03, AOL-PM-03, INS-20 |
| witness-coupon locations | PRESENT | HW-H1-09, HW-MC-06, HW-C1-06, HW-PIM-14, HW-SVC-06 | AOL-WC-01..05, INS-19, INS-20, INS-P-12 |
| near-cathode RGA port | PRESENT | HW-C1-07 (b) | AOL-CX-03, INS-11, INS-22 |
| cathode temperature provision | **ADDED** | **HW-C1-09** (HW-C1-07 (a) now points to it) | AOL-CX-04, INS-23 |
| coil hot-spot thermocouples | PRESENT | HW-MC-14 | MCQ-W4-01, MCQ-QT-06, MCQ-S1-02, INS-24 |
| 4-wire winding-temperature measurement | PRESENT | HW-MC-14 | MCQ-W4-01, MCQ-W4-02, INS-24 |
| B(z) access | PRESENT | HW-H1-08, HW-MC-03, HW-MC-15 | AOL-PM-08, MCQ-W4-03, MCQ-QT-07, INS-09, INS-P-07 |
| AO-facing magnetic-material coupons | PRESENT | HW-MC-06, HW-SVC-06, HW-H1-14 | AOL-WC-04, MCQ-AO-01, INS-19, INS-20 |

**Why HW-C1-09 was added.** HW-C1-07 (a) left the choice between a thermocouple and a pyrometer to W4. A3 closes that
choice. A cathode-tube thermocouple is **mandatory**. An emitter pyrometer is added where there is a defensible line of
sight and emissivity treatment. The tube reading is never labelled emitter temperature. Without pyrometry, emitter
temperature is reported as unmeasured. W4 INS-23 already assumes this and asks W3 for the view decision. HW-C1-09 makes
the hardware provision explicit and puts the view decision in the C-1 design record. It sets no temperature value.

**Other A3 items.** A3 also sets:

- the ISO/IEC 17025 metrology scope;
- quantitative RGA calibration for the AO/lifetime programme (qualitative RGA only for S1a checkout);
- the k = 2 planning coverage factor for the INS-P-12 witness-holder check.

These are W4 measurement-specification items. They need no H-1, C-1 or MC-1 change beyond the provisions above.

**Other changes.**

- Five back-traces that the AO register v3 found missing or text-only were added as `traces_to` entries: HW-H1-12 to
  AOL-WC-04, HW-H1-14 to AOL-EX-01, HW-H1-09 to AOL-OQ-03, HW-C1-06 to AOL-OQ-04 and HW-C1-03 to AOL-PT-03.
- No existing id or numeric value changed. The C5 source pin SRC-AOL (v1) is unchanged; the requirement set of v3 is the
  same.
- Consumers that pin this register's bytes must re-pin: the AO register (`merged_inputs`), W4 (`pinned_inputs.json`)
  and the S1 readiness gate (its `requirements_basis`).

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
| witness coupon and holder positions, materials and lots; replaceable-part serials; life-mechanism thermocouples; cathode-exposure provisions | control C5 | HW-H1-09..14, HW-MC-06, HW-C1-06/07, HW-PIM-14, HW-SVC-06 |

**May differ:**

- the module and its off-module chain;
- the bus components `rf_source`, `ecr_source`, `ecr_magnet`;
- the inlet state at `HALL_INLET_Z0` (a result, not a setting);
- the instance of the per-arm interstage witness set (same position, material and lot; one set per arm, HW-PIM-14);
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
- the XE_HEALTH_CHECK, if D-15-B is adopted;
- the interstage witness-set exchange record and the coupon/part register entry (HW-PIM-14, HW-H1-13).

**Hardware readiness review (HRR, PROPOSED).** It sits after LOCK-1 and hardware delivery, before S1. Entry
criteria:

- the owner decisions are recorded;
- the H-1 design release is available;
- the IP-UP/IP-DN interface drawing is frozen;
- the P1 TBDs are resolved before Phase 1, and the P2 TBDs before the first module;
- the W4 instrument list exists;
- the W5 pre-registration is filed before any data;
- the C5 provisions are installed and baselined before first ignition (section 4.8);
- the magnet/coil S1 gate items MCQ-S1-01..08 are closed (HW-MC-07..16, HW-ELEC-05; HW-PIM-15 before Phase 2).

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
| HWQ-16 | Classify witness coupons and their holders (HW-PIM-14, HW-SVC-06) as non-functional exchangeable items that do not create H-1' when exchanged at arm boundaries, provided B(z) and the HW-0 reference are unchanged within the LOCK-2 repeatability? (AOL-OQ-01) |
| HWQ-17 | Approve alternative-grade wall sector inserts (AOL-RC-04)? They add comparative N/O wall data but change H-1 design-representativeness (HW-H1-01); not adopted until decided (AOL-OQ-02). |
| HWQ-18 | Soft-magnetic pole/core material grade for MC-1 (HW-MC-13; MCQ-OQ-05); needed by HW-MC-06, HW-H1-14 and HW-MC-15. |
| HWQ-19 | MC-1: electromagnet only (traceable B(z) versus coil current, needed for held-out B(z) evidence and the S_B scan HW-MC-05) or permanent-magnet assisted (then HW-MC-09 applies)? (MCQ-OQ-01) |
| HWQ-20 | Coil conductor/insulation family for S1 and the hot-spot margin policy (HW-MC-07, HW-MC-08, HW-MC-10; MCQ-OQ-02, MCQ-OQ-03), decided once the H-1 thermal model gives a hot-spot estimate. |
| HWQ-21 | Heated emitter witness near C-1 (adds a heater load that must be metered inside the bus boundary) or ground-only heated-emitter exposure (AOL-EX-03)? (AOL-OQ-04) |

## 8. Relation to parallel workstreams (by path; none is required by this register or its test)

| workstream | relation |
|---|---|
| W1 `fo_feed_state_closure` | Flows, P_feed, T_feed and x_s test points. Planned path `docs/architecture_comparison/feed_state_closure/`, not merged here; values are not copied. |
| W2 `fo_lock1_decision_brief` | Receives HWQ-01..21 and the proposed S1 addition HW-MC-05 |
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
- `fo_ao_lifetime_register` `docs/experiments/lifetime_ao/` (control C5)
- `fo_magnet_coil_qualification` `docs/experiments/magnet_coil/` (control C5)

## 9. Compliance

- No Hall closure, screening candidate (`sgb-screen-*`) or withdrawn 0-D number is used. No performance is predicted
  and no architecture is ranked or eliminated.
- Control C6 / AOL-LF-01: no H-1 or C-1 life number is computed from a Hall map, an unadmitted closure or a withdrawn
  0-D result. This register records inspection and metrology provisions only.
- P5 calibration nuisance is never a hardware variable. Hall-closure uncertainty does not reach the feed side.
- Literature is cited as recorded by the merged lanes; this lane re-read none of it. Each reference in the JSON says
  which lane recorded it. Every value that is neither sourced nor derived is PROPOSED or TBD.
- The register is pure data plus one standard-library generator. Nothing is wired into `archengine`, and no frozen
  data, golden, prereg, campaign or `hallthruster_bridge/` file is touched.
