# P6 Power: submission-safe statement

Item: A9.38 Priority 6, power closure. Closure state: **BLOCKED BY SPECIFIC MISSING EVIDENCE**. The missing evidence
is the Hall discharge power at the 12 mN and 25 mN points, which needs the converged Hall envelope (P2,
HALL_NUMERICS_NOT_CONVERGED). Every other bus-power term is closed.

Evidence: `docs/closure/power/power_ledger_v1.json` / `.md`, the term register
`docs/closure/power/power_closure_inputs_v1.json`, and the closure record `docs/closure/power/p6_closure_state_v1.json`.

---

## Proposal text

**Electrical power architecture.** The propulsion system takes all of its electrical power from the spacecraft DC bus
through one propulsion power processing unit (PPU). A configurable front end converts the spacecraft bus to a regulated
internal propulsion bus. Its input stage is fixed once the spacecraft bus is defined in the spacecraft ICD.

The PPU has dedicated outputs for:
- the Hall discharge;
- each Hall electromagnet coil, with current control per coil;
- the 13.56 MHz RF generator of the RF/ICP neutralizer, with its adjustable local matching network;
- the neutralizer collector bias supply;
- the atmospheric-path and Xe-path flow-control valves;
- the compressor drive;
- thermal control;
- the propulsion controller, including FDIR and telemetry/telecommand.

The flight configuration has no hollow cathode and no heater or keeper supply. One reserved DC port is unpowered in the
baseline.

**Power requirement and design allocation.** The requirement is a propulsion-system input power below 1.5 kW. It is
measured at the spacecraft-side DC interface and includes every conversion and harness loss. Start-up transients are
also held below this limit.

The design baseline sets an internal allocation of 1,350 W for all flight loads. The 150 W between that allocation and
the requirement is margin and is not used in nominal operation. Inside the 1,350 W:
- the common loads (compressor, flow control, thermal control and controls) have a 300 W allocation;
- controls and thermal control together have a 50 W allowance within it.

There is no fixed split between the Hall thruster and the neutralizer. The neutralizer RF power and the Hall discharge
power share the remaining allocation.

**Design power budget.** The budget below is at the design reference operating point, in air-breathing mode. All
values are at the spacecraft DC interface.

| group | design budget |
|---|---|
| Hall thruster (discharge supply and electromagnets, incl. conversion and harness) | ~960 W |
| RF/ICP neutralizer (RF generator at the reference forward power, matching, collector bias) | ~320 W |
| common loads (compressor drive, valves, thermal control, controls / FDIR / telemetry) | ~65 W |
| **total** | **1,350 W design allocation** |

How the budget was built:
- Every power-conversion stage is booked with its efficiency inside the bus figure, as is every harness run.
- Supply efficiencies come from published flight-class Hall PPU data and sub-kW PPU breadboard measurements.
- The magnet coil loads come from the H-1 magnetic-circuit sizing at the hot coil temperature.
- The valve loads come from flight proportional-flow-control-valve data.
- The compressor load comes from the selected compressor design model.
- Where no published value applies, a conservative engineering value is used, and its uncertainty range is carried.

**How the Hall operating point fits the budget.** The power available to the Hall discharge follows from the budget:
- About 0.78 kW of discharge power fits the 1,350 W design allocation.
- About 0.91 kW of discharge power stays below the 1.5 kW requirement.

The thruster is therefore operated at a thrust-to-discharge-power ratio that keeps the 12 mN sustained point within the
design allocation. The 25 mN capability point is held below the 1.5 kW requirement. Discharge power at each thrust level
will be established by the Hall performance analysis and verified on the engineering model. Neutralizer RF power and
Hall discharge power are traded within the same allocation.

**Xe contingency mode.** In Xe contingency mode the compressor and the atmospheric flow path are off, and the Xe flow
path is powered instead. Bus power at the same discharge power is slightly lower than in air-breathing mode.

**Verification.** Verification is by analysis now and by test later:
- The power budget is verified by analysis at PDR. Measured supply efficiencies replace the reference values: from the
  flight-representative breadboard discharge supply, the flight-representative RF source and the magnet supplies.
- The total propulsion bus power, including start-up transients, is verified by engineering-model test at the
  spacecraft DC interface. That test uses a 1 ms averaging window and a measurement bandwidth and sampling rate defined
  in the test plan.
- The budget will be finalized at PDR/CDR together with the spacecraft electrical ICD.

---

## Recorder notes (not for the proposal)

- The approximate figures in the table and the 0.78 / 0.91 kW discharge figures are rounded design-ledger values.
  They are not acceptance criteria, and the discharge power is DESIGN_ALLOCATION_NOT_PREDICTED.
- The registered DBF-1 discharge band upper end (1,350 W) does not fit the bus once the other loads are added.
  - At the 25 mN point with P_d = 1,350 W, the ledger gives about 2.0 kW.
  - The flight operating ceiling is P_d,max: 0.91 kW at 1.5 kW in the reference case, 0.68 kW in the conservative
    corner.
  - The derived Hall requirement is T/P_d >= 27.4 mN/kW at 25 mN (reference) and >= 15.3 mN/kW at 12 mN within
    1,350 W. These are inputs to P2.
- The housekeeping load (30 W) is the analog PPU's auxiliary-supply rating. With the 0.70 supply efficiency it takes
  ~46 W of the 50 W controls/thermal allowance, so only ~4 W is left for heaters while firing.
  - If P7 finds more heater power is needed, it comes from the common-allocation residual, which is about 234 W.
  - That changes the allowance check, not the 1,350 W total.
- Pending updates:
  - compressor (DCR-001);
  - RF forward power and collector bias (P4 / ICP-45, P1-IT-18);
  - matching actuators (P2 impedance map);
  - magnet loads (P3 FEMM);
  - front end (spacecraft bus ICD).
