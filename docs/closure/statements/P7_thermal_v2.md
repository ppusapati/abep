# P7 Thermal: submission-safe statement

Item P7 (A9.38 Priority 7), statement v2. Closure state: **REFERENCE/ICD DEPENDENT** (every limited node meets the design
rule or carries a defined verification requirement; the heat conducted into the host spacecraft depends on the customer
ICD). The RF matching-network item is closed without a design change (DCR-DBF1-003 withdrawn, route R-1). Engineering evidence:
`docs/closure/thermal/thermal_closure_v2.json` / `.md` (lane L-THERMAL; load inputs v2 from the P6 power ledger; v1 on
the registered-assumption inputs is kept as history), preregistration
`docs/closure/thermal/thermal_cases_prereg_v1.json` (lock `thermal_cases_prereg_lock_v1.json`), DCR request
`docs/closure/thermal/dcr_request_P7_match_v1.json`, its evaluation `docs/closure/thermal/dcr003_evaluation_v3.json` / `.md`
under preregistration `docs/baseline/DCR-003/dcr003_eval_prereg_v3.json` and the resolution
`docs/baseline/DCR-003/dcr003_resolution_v3.json`. `P7_thermal.md` is kept as history. Design baseline: DBF-1 (`docs/baseline/DBF-1/dbf1_v1.json`, items
DBF1-TH-01..03).

## Proposal text

**Thermal design baseline.** The propulsion system uses a passive thermal design with one fixed thermal topology for
the atmospheric (primary) and xenon (contingency) supply modes:

- The Hall thruster is mounted on a thermally isolated interface. Its heat is rejected by radiation from the
  high-emittance exterior of the magnetic circuit, and by a dedicated Hall radiator joined to the back plate through a
  heat-path doubler.
- The RF/ICP neutralizer rejects its heat from high-emittance outward surfaces of its housing.
- The power-processing and RF-generation electronics, and the compressor drive, reject their heat to dedicated
  radiators or to the host spacecraft. This is subject to the customer spacecraft ICD.

There is no cathode heater, and there is no active cooling loop.

**Design rule.** Every part is designed to operate at least 50 K below its continuous-use temperature limit. This holds
with all internal heat loads increased by 20 %.

**Analysis basis.** The thermal model is a lumped-node network. It covers:

- the Hall anode, inner and outer channel walls, magnetic poles, back plate and three electromagnet windings;
- the neutralizer vessel, antenna, ion collector, housing, mount, and the matching network on its own isolated mounting
  with a dedicated radiator and its RF lead to the antenna;
- the Hall radiator.

The model was verified against analytic cases. It is run for the 180-230 km orbit set:

- **Hot cases:** continuous-sun and maximum-eclipse orbits at 180 km, with hot-case solar, albedo and Earth-infrared
  fluxes and 120 % internal loads.
- **Cold cases:** a maximum-eclipse orbit at 230 km, with cold-case fluxes, operating at reduced load and also
  non-operating.

The heat loads come from the system power allocation, using published Hall-thruster heat-deposition fractions and a
published RF/ICP neutralizer analog.

**What analysis establishes now.** At the reference operating point, analysis indicates the following:

- **Channel walls.** The walls stay well below the oxidizing-atmosphere use limit of the BN-SiO2 wall class.
- **Magnetic circuit.** The poles and back plate stay far below the magnetic-material ceilings.
- **Electromagnet windings.** The ceramic-insulated windings stay within the supplier continuous rating, with the
  required 50 K margin. The inner winding is the limiting Hall component.
- **Anode and ion collector.** Both stay within the supplier oxidation-data domain of the selected nickel alloys.
  This supports retaining the primary alloy.
- **Neutralizer dielectric vessel.** The vessel stays within its assumed service limit.
- **Radiator and interface.** The required Hall radiator is small. A modest increase in radiator area keeps the heat
  conducted into the host spacecraft within the provisional interface allocation.
- **Electronics.** The heat to be rejected by the power-processing and RF-generation electronics is defined, together
  with the corresponding radiator and survival-heater needs, as an interface requirement on the host spacecraft.

**RF matching network.** The matching network stays next to the neutralizer, as in the frozen topology. It is
mounted on low-conductance titanium-alloy isolator standoffs and rejects its heat through its own small zenith radiator.
Its RF lead to the antenna is included as a heat path, with the lead loss shared between both ends. With the full set of
hot cases and 120 % loads, the matching network then meets the 50 K design rule. No other node gets worse, and the
thruster and neutralizer architecture is unchanged. A small operating heater keeps the matching network above its lower
limit in the cold case.

**Verification approach.** Thermal design is verified by analysis now. It is to be verified by test at engineering
model (EM) level:

- **Component data.** Conductances, emittances and coating temperature capability are measured on procured parts.
- **EM thermal balance.** A thermal-balance test of the integrated Hall thruster and neutralizer runs in vacuum at
  hot- and cold-case loads, with the measured heat-deposition fractions on nitrogen and air-representative propellant.
  The model is then correlated to the test.
- **Materials.** Stage-2 material temperature limits for the anode and collector, and thermal cycling to the
  registered mission cycle count (P8).

Interface temperatures and allowable heat flows to the spacecraft are subject to the customer spacecraft thermal ICD
and are to be finalized at PDR/CDR.

## Internal notes (not proposal text)

- **Model basis.** The case class is PARAMETRIC, because FLIGHT_CONDITIONAL is NOT_EVALUATED: there is no host thermal
  ICD, the credible Hall set is empty, and NP-ICP is not admitted. Model validation status is NOT_VALIDATED. The loads
  are the P6 power-ledger terms (inputs v2) plus registered assumptions. The compressor is still the DBF-1 compressor.
  When DCR-001 lands, the record reruns unchanged with `thermal_load_inputs_v3`.
- **Reference values** (from `thermal_closure_v2.json`; never acceptance criteria):
  - inner winding 446 degC against a 488 degC design ceiling;
  - anode 512 degC: the required stage-2 capability is 562 degC, and the P8 ceilings are 930 / 1150 degC (no trigger);
  - collector 510 degC;
  - walls 454 / 434 degC against 850 degC;
  - N_MATCH 55.2 degC against the 60 degC design ceiling, 4.8 K inside the 50 K rule (P7 v2: 183.5 degC,
    FAIL), with A_MA 0.15 m^2 (0.6 kg at 4 kg/m^2) and Ti-6Al-4V standoffs (11.7 g),
    hot corner G_iso 0.04 W/K, G_lead 0.025 W/K, Q_match_frac 0.06, lead loss
    f_lead 0.019 split match / antenna at the same delivered power (prereg v3); allowable Q_match_frac 0.100;
  - R-1 power penalties against P6: operating heater 11.5 W (12.6 W bus) against the 4.0 W thermal-control slot,
    RF-lead loss dP_bus 3.0 W (R_A 1 Ohm) / 6.0 W (R_A 0.5 Ohm), non-operating survival heater
    17.2 W (outside the firing bus allocation);
  - heat into the spacecraft 90.6 W (P7 v2 89.6 W) against the 50 W governing allocation;
  - R_HALL 0.02 m^2 node-limited; 0.15 m^2 at 5 W/K holds the TC1 / TC3 heat into the spacecraft within 50 W
    (90 W at 0.02 m^2);
  - PPU 225 W (0.62 m^2 at 30 degC);
  - RF generator 400 W (1.0987 m^2). R-2 (match at the generator) was not admissible: R2-b, R2-c and R2-d (generator
    radiator area 122.7 m^2 at the conservative corner against the 1.0987 m^2 allocation) fail;
  - compressor 13.4 W (DBF1-IN-08 basis, flagged for DCR-001).
- **Inner-winding allowable.** The inner winding limits the continuous discharge power to about 1114 W under the rule.
  The 1350 W P_d band end exceeds it (S1, non-governing).
