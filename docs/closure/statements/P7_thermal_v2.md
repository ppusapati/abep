# P7 Thermal: submission-safe statement (v2)

Item P7 (A9.38 Priority 7). Supersedes `P7_thermal.md` (v1, kept as history). Closure state: **REFERENCE/ICD
DEPENDENT**. Every node with a temperature limit meets the design rule, including the RF matching network. Every other
node carries a defined verification requirement. The remaining dependency is the heat conducted into the host
spacecraft, which is set by the customer spacecraft thermal ICD.

Engineering evidence:

- `docs/closure/thermal/thermal_closure_v2.json` / `.md`: frozen-topology P7 closure (lane L-THERMAL).
- `docs/closure/thermal/dcr003_evaluation_v1.json` / `.md`, sha256
  `1a2773df5b8f5586cce9833001b1eb02b7024c72b9d1dd50c31af185bc534ee9`: the match-installation evaluation (lane
  L-DCR003-MATCH).
- Preregistrations: `docs/closure/thermal/thermal_cases_prereg_v1.json` (lock `ac2010a9...`) and
  `docs/baseline/DCR-003/dcr003_eval_prereg_v1.json` (sha256 `13b27c04...`, lock `57f94f7c...`, committed before
  either route was evaluated).
- Resolution: `docs/baseline/DCR-003/dcr003_resolution_v1.json`. DCR-DBF1-003 is resolved as WITHDRAWN; registering
  that is the coordinator's action.
- Design baseline: DBF-1 (`docs/baseline/DBF-1/dbf1_v1.json`, items DBF1-TH-01..03, DBF1-RF-03), unchanged.

## Proposal text

**Thermal design baseline.** The propulsion system uses a passive thermal design with one fixed thermal topology for
the atmospheric (primary) and xenon (contingency) supply modes:

- The Hall thruster is mounted on a thermally isolated interface. Its heat is rejected by radiation from the
  high-emittance exterior of the magnetic circuit, and by a dedicated Hall radiator joined to the back plate through a
  heat-path doubler.
- The RF/ICP neutralizer rejects its heat from high-emittance outward surfaces of its housing.
- The adjustable RF matching network is mounted next to the neutralizer, as the RF design requires, but is thermally
  isolated from it:
  - it sits on low-conductance titanium-alloy standoffs;
  - it is connected to the antenna through a thermal-break RF lead;
  - it rejects its heat through its own small zenith-facing radiator;
  - a thermostatic heater holds its lower temperature limit in the coldest operating and non-operating conditions.
- The power-processing and RF-generation electronics, and the compressor drive, reject their heat to dedicated
  radiators or to the host spacecraft. This is subject to the customer spacecraft ICD.

There is no cathode heater, and there is no active cooling loop.

**Design rule.** Every part is designed to operate at least 50 K below its continuous-use temperature limit. This holds
with all internal heat loads increased by 20 %.

**Analysis basis.** The thermal model is a lumped-node network. It covers:

- the Hall anode, inner and outer channel walls, magnetic poles, back plate and three electromagnet windings;
- the neutralizer vessel, antenna, ion collector, housing, matching network and mount;
- the Hall radiator.

The model was verified against analytic cases. It is run for the 180-230 km orbit set:

- **Hot cases:** continuous-sun and maximum-eclipse orbits at 180 km, with hot-case solar, albedo and Earth-infrared
  fluxes and 120 % internal loads, at the upper end of the RF forward-power envelope.
- **Cold cases:** a maximum-eclipse orbit at 230 km, with cold-case fluxes, operating at reduced load and also
  non-operating.

The heat loads come from the system power allocation, using published Hall-thruster heat-deposition fractions and a
published RF/ICP neutralizer analog. The matching-network installation is assessed at the unfavourable end of its
standoff and lead conductances and with the RF lead loss included.

**What analysis establishes now.** At the reference operating point, analysis indicates the following:

- **Channel walls.** The walls stay well below the oxidizing-atmosphere use limit of the BN-SiO2 wall class.
- **Magnetic circuit.** The poles and back plate stay far below the magnetic-material ceilings.
- **Electromagnet windings.** The ceramic-insulated windings stay within the supplier continuous rating, with the
  required 50 K margin. The inner winding is the limiting Hall component.
- **Anode and ion collector.** Both stay within the supplier oxidation-data domain of the selected nickel alloys.
  This supports retaining the primary alloy.
- **Neutralizer dielectric vessel.** The vessel stays within its assumed service limit.
- **RF matching network.** With the isolated installation, the matching network stays within its derated electronics
  limit with the required 50 K margin in every hot case. It keeps that margin even if the matching-network loss is
  about twice the design assumption.
- **Radiators and interface.** The required Hall and matching-network radiators are small. The heat conducted into the
  host spacecraft is defined as an interface value. The Hall radiator area is the design parameter that sets it,
  and it is finalized against the customer spacecraft ICD.
- **Electronics.** The heat to be rejected by the power-processing and RF-generation electronics is defined, together
  with the corresponding radiator and survival-heater needs, as an interface requirement on the host spacecraft.

The thruster and neutralizer architecture, and the frozen design baseline, are unchanged.

**Verification approach.** Thermal design is verified by analysis now. It is to be verified by test at engineering
model (EM) level:

- **Component data.** Conductances (including the match standoffs and RF lead), emittances and coating temperature
  capability are measured on procured parts.
- **EM thermal balance.** A thermal-balance test of the integrated Hall thruster and neutralizer, with its matching
  network, runs in vacuum at hot- and cold-case loads, with the measured heat-deposition fractions on nitrogen and
  air-representative propellant. The model is then correlated to the test.
- **Materials.** Stage-2 material temperature limits for the anode and collector, and thermal cycling to the
  registered mission cycle count (P8).

Interface temperatures, allowable heat flows to the spacecraft and survival-heater power are subject to the customer
spacecraft thermal ICD and are to be finalized at PDR/CDR.

## Internal notes (not proposal text)

- **Model basis.** The case class is PARAMETRIC, because FLIGHT_CONDITIONAL is NOT_EVALUATED: there is no host thermal
  ICD, the credible Hall set is empty, and NP-ICP is not admitted. Model validation status is NOT_VALIDATED. The loads
  are the P6 power-ledger terms (inputs v2) plus registered assumptions. The compressor is still the DBF-1 compressor.
  When DCR-001 lands, the record reruns with `thermal_load_inputs_v3`.
- **DCR-DBF1-003 outcome.** The preregistered selection rule chose R-1, so no DBF-1 value changes:
  - Isolator standoffs: 4 x Ti-6Al-4V, 0.012-0.04 W/K.
  - Match radiator: 0.15 m^2.
  - RF lead pair: plated 304 stainless, 0.010-0.025 W/K.
  - R-1 network: one new link between existing nodes; the DBF1-TH-01 node set is unchanged.
  - R-2 (remote match) is not admissible. The line between a generator-side match and the antenna (X_A ~ 164 Ohm,
    R_A 0.5-5 Ohm) runs at VSWR 60-1900. Delivering the 200 W anchor then needs 878 W forward power at the reference
    corner, and 214-9044 W across the corners. This is outside the 500 W DBF1-RF-02 envelope and the P6 margin.
  - The P7 v2 record and the P7 preregistration v1 stay as history. A P7 record that carries the R-1 values as its
    own network needs a P7 preregistration v2 (P7 rerun_rule).
- **Reference values** (from `thermal_closure_v2.json` and `dcr003_evaluation_v1.json`; never acceptance criteria):
  - N_MATCH (R-1, HOT corner):
    - 54.4 degC at TC4, against a 60 degC ceiling (margin 5.6 K);
    - 21.8 degC at the nominal corner in TC3;
    - match-loss allowable 0.107 of P_fwd, against the 0.06 used.
  - N_MATCH cold, without a heater: -40.5 degC (TC5) and -80.1 degC (TC6). Heaters: 11.5 W operating and 17.2 W
    survival.
  - Inner winding 446 degC against a 488 degC design ceiling.
  - Anode 513 degC; the required stage-2 capability is 563 degC, against the P8 ceilings of 930 / 1150 degC (no
    trigger).
  - Collector 507-510 degC.
  - Walls 455 / 434 degC against 850 degC.
  - N_MOUNT 214 degC (requirement 264 degC).
  - R_HALL 0.02 m^2 node-limited.
  - Heat into the spacecraft 90.5 W, against the 50 W provisional allocation. This is the REFERENCE/ICD dependency.
    In v2, 0.15 m^2 at 5 W/K held TC1 / TC3 within 50 W.
  - PPU 225 W (0.62 m^2 at 30 degC).
  - RF generator 400 W (1.10 m^2).
  - Compressor 13.4 W (DBF1-IN-08 basis, flagged for DCR-001).
- **P6 consequences** (for the L-POWER-ICD ledger owner):
  - RF lead loss: +1.9 to +3.9 W forward power for the same delivered power, which is 2.9-5.9 W bus.
  - Operating heater: 12.6 W bus, against the 4.0 W thermal_control slot.
  - Conservative total: +14.5 W bus (-12.4 W P_d,max), against the 150 W P-NOM margin to 1,500 W.
  - Mass: +0.61 kg (P5).
- **Inner-winding allowable.** The inner winding limits the continuous discharge power to about 1114 W under the rule.
  The 1350 W P_d band end exceeds it (S1, non-governing).
