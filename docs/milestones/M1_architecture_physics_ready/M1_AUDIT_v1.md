# M1 ARCHITECTURE PHYSICS READY — milestone audit v1

Audited commit `6971637900fdac0cbf577c89aeac0a031f0c41b0` · governance A9.34 · decision: **M1 EXIT → M2 starts now**

## Exit criteria

| id | criterion | status |
|---|---|---|
| M1-EX-1 | the H1 Hall envelope has run | MET |
| M1-EX-2 | Hall AIR chemistry is available or explicitly bounded | MET (EXPLICITLY_BOUNDED) |
| M1-EX-3 | RF/ICP coupling is available | MET (layer (a), parametric) |
| M1-EX-4 | the 196-state closure harness can consume all required physics paths | MET |

## Readiness (harness v2)

| path | status | producer status |
|---|---|---|
| P-ENV | CONSUMED | ADMITTED |
| P-FLOW | CONSUMED | ADMITTED (PARAMETRIC_SENSITIVITY inputs); plenum / feed group PYTHON_REFERENCE |
| P-FEED-STABILITY | AWAITING_INPUT | PYTHON_REFERENCE authoritative (v8 PARITY_FAIL stands) |
| P-ICP | CONSUMED | NP-ICP-NEUTRALIZER model_version 2: IMPLEMENTED_UNVERIFIED; ledger RUST_IMPL; NOT_VALIDATED |
| P-CPL | CONSUMED | NP-ICP-NEUTRALIZER model_version 2: IMPLEMENTED_UNVERIFIED; ledger RUST_IMPL; NOT_VALIDATED |
| P-HALL-XE | CONSUMED | PARAMETRIC / NOT_VALIDATED |
| P-HALL-AIR | AWAITING_INPUT | A1 on this line |
| P-PBUS | CONSUMED | ADMITTED ledger function; loads from the evaluated paths |
| P-THERMAL | AWAITING_INPUT | NP-THERMAL-CATHODELESS 2.0.0: VERIFIED, NOT_VALIDATED, not admitted (ADM-04) |
| P-MASS | CONSUMED | ADMITTED |
| P-LIFE | CONSUMED | ADMITTED kernels |
| P-TD | CONSUMED | ADMITTED hook; host-spacecraft drag ICD absent |
| P-LAYER-B | CONSUMED | ADMITTED / ACCEPTED |

## Carried findings

- XE Hall: NUMERICS_NOT_CONVERGED (A3 + A6 STOP); layer (a) XE Hall tests cannot leave NOT_DETERMINABLE with HallThruster.jl v0.23.1 under the registered transport set at H1
- AIR Hall: chemistry EXPLICITLY_BOUNDED, information only; AIR A3 NOT_ADEQUATE
- AIR delivered flow: every registered intake / gas-path design short at the worst state (area x1.004, captured flow x1.14-1.35, delivered flow x3.67 for 12 mN) -> DESIGN_VARIABLE_LIMIT (A9.35); F8 robust set EMPTY (admitted)
- Conservation (A4): worst-state 12 mN needs >= 0.251 m2 effective collection area and >= 0.048 mg/s at the ideal 1.5 kW; A4-REG-01 OPEN (no area limit registered)
- Intake-face drag filter C-DRAG-RFP excludes grid areas above 0.25 m2 (0.5 m2: 26.7 mN at 180 km)
- Plenum / feed v8 PARITY_FAIL stands; governed Python reference used (A9.34)
- Credible Hall transport set EMPTY; layer (b) NOT_EVALUATED throughout

## Open owner / registration items

- A4-REG-01 maximum effective intake collection area (A9.35: stays open)
- host-spacecraft drag ICD (T-D, HC-08)
- H-1 B(z) registration (H1F-BZ-01)
- H-1 Xe flow (OQ-HPE-03)
- complete bus ledger (24 TBD terms)
- flight thermal case / spacecraft thermal ICD
- CBE wet mass; Xe load
- ICP geometry / RF input / neutral source registration
- Hall AIR tier-1 sources (OQ-HA-05)

Readiness record `m1_readiness_v1.json` sha256 `c1422e817e9660d073a85bfc9edba82edbf8445f25b9e7898d18bca7617cf855`. The classification is computed in M2 by the preregistered rule.
