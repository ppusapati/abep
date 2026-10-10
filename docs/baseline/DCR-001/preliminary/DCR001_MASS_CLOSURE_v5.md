# DCR-DBF1-001 — compressor / feed mass-closure design v5

**Label:** PROPOSAL-LEVEL / PARAMETRIC / NOT_VALIDATED.

- **Source:** deterministic, `dcr001_mass_closure_v5.py` → `.json` (< 1 s).
- **What it builds on:** v4 (`c68fdca`) is the accepted baseline. This v5 changes only the AIR sizing flow, the feed chain and the compressor.
  Every other mass line is carried over from v4 unchanged.
- **What it does not do:** no simulation, no change to the H1 channel, no change to the intake retention design (S_eff = 2 C_back = 11.25 m³/s).
  DBF-1.2 is not built.

## 1. AIR sizing flow
| reading | source | result |
|---|---|---|
| mandatory atmospheric point | RFP-P18-06 lower bound; A9.40 power gate "AIR 12 mN" | 12 mN AIR inside the admissible density / altitude window |
| nominal drag compensation | RFP-P18-05; A9.40 operating concept | T ≥ D in the AIR window; at host C_D·A 0.50 m² the window is scheduled where 12 mN covers drag |
| system 12–25 mN | RFP-P18-06 gives no propellant split (DISC-07) | met as a system: 12 mN AIR + 25 mN capability |
| Xe / 25 mN | RFP-P17-05 / P18-08; A9.40 | 25 mN in Xe, compressor OFF, ≤ 1,450 W |

**Sizing flow the compressor must guarantee: 0.448 mg/s.**
- It is 12 mN at the A9.40 design basis of 26.8 km/s.
- It is Hall anode flow only; the ICP dedicated flow is 0 (DBF1-ICP-05).
- 0.545 mg/s (the 22 km/s case) and 1.33 mg/s are carried as sensitivities only.

## 2. Feed co-design (H1 frozen)
Elements in series:
- plenum
- isolation valve (40 mm, transmission 0.6)
- metering valve (full-open conductance 0.10 m³/s)
- manifold (40 mm × 100 mm)
- equal-path branch tree 2 × 28 / 4 × 22 / 8 × 18 mm
- annular distributor ring (12 × 20 mm, 8 inlets)
- 186 outlet holes of 3 mm (50 % of the channel base open)
- H1 channel (exit conductance 0.131 m³/s)

Rules:
- Series ducts are combined Santeler-style: duct resistance plus an entrance penalty only at a contraction.
- The arbitrary p_dist ≥ 3 p_anode rule is replaced by a physical uniformity check:
  - the outlet holes' Δp must be ≥ 10 × the ring's azimuthal Δp, which gives ±5 % anode-flux uniformity (achieved ratio 12.7);
  - the 50 % open-area cap on the anode face sets the outlet conductance.
- Minimum controllable plenum = 1.25 × the requirement with the valve fully open (25 % flow authority). The setpoint adds a −5 % band edge.

| Δp with the valve fully open (Pa) | 0.448 mg/s (sizing) | 0.545 mg/s (22 km/s) | 1.33 mg/s |
|---|---|---|---|
| channel (= p_anode) | 0.590 | 0.719 | 1.753 |
| distributor outlet holes | 0.533 | 0.649 | 1.583 |
| distributor ring (azimuthal) | 0.042 | 0.051 | 0.124 |
| branch tree (incl. contraction) | 1.171 | 1.426 | 3.477 |
| manifold | 0.540 | 0.658 | 1.604 |
| isolation valve | 0.480 | 0.585 | 1.426 |
| metering valve | 0.465 | 0.567 | 1.382 |
| **plenum required, valve fully open** | **3.82** | 4.65 | 11.35 |
| minimum controllable (+25 % authority) | **4.78** | 5.82 | 14.19 |

**Selected plenum: setpoint 5.03 Pa (band 4.78–5.28 Pa), volume 9.3 L (1 s residence).**
- The 22 km/s flow is still delivered at this setpoint (valve 60 % open) but with little authority margin. A 6.1 Pa setpoint restores it, and that is inside the Holweck domain.
- 1.33 mg/s needs 14.2 Pa. That is above the Holweck's Kn ≥ 0.5 domain limit of 6.8 Pa, so it is **not supported**.

## 3. Integrated contra-rotating compressor
- **Rotor arrangement:** two coaxial shafts at ±8,603 rpm. The rows alternate between shafts, so there are no stators in the blade section.
- **Blade rows:** every row keeps the tip radius at 0.333 m, so the tip speed stays at 300 m/s; the hub rises as the volume flow falls.
  The rows never step inward.
- **Holweck section:** grooves on the outer skin of the shaft-A drum, facing a stationary grooved aluminium band in the housing.
  It uses the same rotor and drives. There is no separate pump.
- **Row model:** the repository model (abep_sim/compressor.py / abep-gaspath):
  - ln K0 = 1.2 u_rel / c̄;
  - S = 0.2 u_rel A;
  - loaded K = K0 − (K0 − 1) Q/(S p_in).
- **Relative speed:** u_rel is the speed relative to the previous row's swirl. Row 1 sees no swirl.
- **Transitional derating:** above 0.1 Pa, ln K0 is multiplied by Kn/(1+Kn). This derating is an assumption and is not admitted.
- **Throughput:** 0.0468 Pa·m³/s in every stage.

| stage | shaft | r_tip / r_hub (m) | blade height (mm) | u_tip / u_mean / u_rel (m/s) | p_in → p_out (Pa) | K | Kn (in → out) | domain / evidence |
|---|---|---|---|---|---|---|---|---|
| F1 inlet-speed row | A | 0.333 / 0.133 | 200 | 300 / 210 / 210 | 0.0041 → 0.0044 | 1.05 | 8 → 8 | free molecular, admitted; row coefficients T-1, not measured |
| F2 | B | 0.333 / 0.200 | 133 | 300 / 240 / 450 | 0.0044 → 0.0081 | 1.87 | 12 → 6 | same |
| F3 | A | 0.333 / 0.279 | 54 | 300 / 276 / 516 | 0.0081 → 0.0170 | 2.09 | 16 → 7 | same |
| F4 | B | 0.333 / 0.310 | 23.5 | 300 / 289 / 565 | 0.0170 → 0.0396 | 2.33 | 17 → 7 | same |
| F5 | A | 0.333 / 0.323 | 9.6 | 300 / 296 / 585 | 0.0396 → 0.0965 | 2.44 | 18 → 7 | same |
| F6 | B | 0.333 / 0.328 | 5.0 | 300 / 298 / 593 | 0.0965 → 0.272 | 2.82 | 14 → 5 | crosses 0.1 Pa: **not admitted** above 0.1 Pa |
| B7 booster | A | 0.333 / 0.328 | 5.0 | 300 / 298 / 595 | 0.272 → 0.784 | 2.88 | 5 → 1.7 | transitional booster, **not admitted** (derated) |
| H Holweck | A (drum skin) | 0.337 drum | groove 2.0, helix 45°, 40 mm long | 304 / channel 215 | 0.784 → 5.03 | needs 6.4 (loading 0.36) | 4.3 → 0.68 | drag form (EV-02); Kn ≥ 0.5 bound met up to 6.8 Pa; coefficients uncited |

Kinematic checks:
- Outer-drum hoop stress is 144 MPa from self-loading, plus about 63 MPa from blade loading at 1 mm CFRP.
- Drum growth is 0.34–0.36 mm, which is larger than the 0.3 mm running clearance. The cold clearance has to compensate, and this is an EM item.

### Compressor component CBE
| component | CBE kg | MEV kg (+20 %) | evidence |
|---|---|---|---|
| 7 bladed rows (annulus 0.707 m² × 1.74 kg/m²) | 1.230 | 1.476 | model-derived (v3 areal basis) |
| rotating drums (shaft-A outer 1 mm CFRP, shaft-B inner cone) + 2 Ti web discs | 1.013 | 1.216 | model-derived |
| stators: none in the blade section; Holweck grooved Al band (replaces the CFRP shell locally) | 0.812 | 0.974 | model-derived |
| Holweck rotor: local +2 mm CFRP hoop on the shared drum | 0.271 | 0.325 | model-derived |
| coaxial Ti shafts | 0.418 | 0.501 | model-derived |
| 4 hybrid-ceramic bearings, preload, dampers | 0.360 | 0.432 | assumed |
| 2 frameless BLDC motors | 0.400 | 0.480 | assumed |
| housing (CFRP 0.8 mm, aft closure, flanges) | 0.989 | 1.187 | model-derived |
| one dual-axis drive | 0.350 | 0.420 | assumed |
| isolation hardware (launch lock / caging, isolators) | 0.300 | 0.360 | assumed |
| sensors | 0.080 | 0.096 | assumed |
| mounts | 0.250 | 0.300 | assumed |
| **total** | **6.473** | **7.767** | — target was ≤ ~6.5 kg MEV; not met |

**Power** is built up as:
- free-molecular shear: rows 2.1 W and Holweck 19.2 W;
- gas work: 0.3 W;
- bearings: 4 W.

Shaft power is 25.6 W. Dividing by motor 0.85 × drive 0.90 and adding 5 W quiescent gives **38.5 W** (estimate). The allowance is 2× = **77 W**.
The AIR 12 mN bus is 1,158 W (reference, estimate) or 1,209 W (conservative: 22 km/s and the allowance).

## 4. Complete mass (MEV kg)
The figures are: intake 4.629, **compressor 7.767**, **plenum/feed 1.734**, Hall 4.205, ICP 1.583, RF 1.5, PPU 6.0, Xe hardware 3.143,
controls 1.0, structure/thermal 2.5.
- Non-harness 34.061 + harness 1.793 = **nominal dry 35.854**.
- Adding the 10 % system margin gives **39.439**.
- Adding **2 kg Xe gives 41.439 kg wet**.
- **Margin −1.439 kg.**

Mass-closure candidates if the shortfall stands (ranked; values not changed):
1. PPU (6.0 kg, owner floor);
2. Xe hardware (3.14 kg);
3. intake structure (4.63 kg; the shroud could share the compressor housing);
4. structure/thermal (2.5 kg, owner allocation).

## Classification
**DCR-DBF1-001 NOT READY — MASS SHORTFALL 1.44 kg.**
