# ABEP hall_icp_neutralizer — Architecture Closure Conclusion v2

Supersedes v1 (`ARCHITECTURE_CLOSURE_CONCLUSION_v1.md`, kept as history) per owner decision **A9.39**
(`docs/decisions/OD_2026_10_09_A9_39_*`). Governing analysis baseline: **DBF-1.1** (lock `257e141c…`).

## Status

**PHYSICS ARCHITECTURE CLOSED — DETAILED DESIGN / EM VERIFICATION OPEN**

Frozen architecture: atmospheric **variable-effective-capture intake** → active compressor / plenum / feed → H1 Hall
accelerator → 13.56 MHz RF/ICP neutralizer → thrust. Ambient O/N₂ is the primary propellant; Xe is the required secondary
capability (commissioning, restart, contingency, off-nominal operation). The architecture is not reopened unless evidence
shows a fundamental physical impossibility.

## 1. RFP requirement

- Functional orbit altitude 180–230 km.
- Air-intake specification decided by air density, based on solar activity and altitude.
- Thrust 12–25 mN; full-system power < 1,500 W; total system mass < 40 kg.
- Compatibility with ambient air and Xe.

## 2. Internal conservative verification set (196 states)

The 196-state set (altitude × solar / geomagnetic activity × location / season, frozen NRLMSIS) is a conservative
verification and design-state set. It is **not** a requirement to operate at every altitude under every atmospheric extreme with
one unchanged operating point. Over this set the admitted free-stream mass flux spans
1.86e-07 – 8.59e-06 kg m⁻² s⁻¹ (×46).

**Physics finding (conservation analysis, chemistry- and design-independent;** `fixed_intake_window_v1.py`**):**
a single fixed intake cannot span the complete conservative registered atmospheric-state set. Under ideal assumptions (capture
efficiency 1; all flow ionised to O⁺ through the full 350 V), 12 mN at the thinnest state needs ≥ 0.99 m² effective
capture, and the same area at the densest state carries ≥ 67 mN of capture drag; one fixed area can serve at most a
×17.4 flux span (≈ ×7–9 with realistic utilisation, estimate). The ~0.99 m² value is a lower bound at a single
state, not a sizing value.

## 3. Design operating window (selected concept)

The selected ABEP therefore uses **density-aware operating-point / altitude management within the RFP 180–230 km
functional-altitude range, with intake effective capture sized / modulated according to atmospheric density and solar activity**,
consistent with the RFP intake requirement.

- An AIR operating free-stream flux window is defined; altitude is selected / scheduled inside 180–230 km with solar activity /
  atmospheric density so the propulsion system remains inside it.
- The intake provides **variable effective capture** (aperture, bypass / spillage, variable throat / conductance, shutters /
  vanes or equivalent — mechanism selected by DCR-DBF1-001, without unnecessary complexity).
- DCR-DBF1-001 establishes the physical maximum aperture, the capture-area modulation range, intake geometry, capture
  efficiency, drag, compressor point and pressure ratio, plenum, delivered flow, mass, power, and the admissible flux window and
  altitude schedule. *(in progress)*
- Xe is not the routine solution for states outside an arbitrarily fixed window.

## 4. Supporting evidence (analysis, not measurement)

- **Hall (RP-1, DBF-1.1 geometry):** the HallThruster.jl non-convergence cause is identified (observable, averaging window,
  spatial order, collapse at high B / low flow; vendor SPT-100 case converges). A partial RP-1 Xe run set with the time-mean
  observable (unscored, PARAMETRIC / NOT_VALIDATED, credible transport set empty) gives 6–48 mN at 156–1,040 W
  (28–76 mN/kW), supporting the Xe secondary capability within the ≈ 911 W discharge ceiling.
- **Atmospheric Hall performance** is not an architecture blocker. Design estimates may use literature; they are never
  represented as measured or demonstrated H1 performance. A minimal local RP-1 atmospheric run package (6–12 cases, DBF-1.1 FE
  B(z)) is provided for preliminary operating-map evidence.
- **Magnetic field:** FE-derived H1 B(z) (DBF-1.1), not measured.
- **Power:** ledger closed except the Hall operating point; discharge ceiling ≈ 911 W under 1,500 W; 1,350 W internal design target.
- **Thermal:** all nodes within the 50 K / 1.2 rule except the co-located RF match (relocation / isolation, DCR-DBF1-003).
- **Materials:** no gate fails; open gates close by coupon / EM tests.
- **Host drag:** allowable host C_D·A envelope registered as interface requirement IR-HOST-DRAG-01 (subject to customer ICD).

## 5. EM verification items

- Atmospheric-mode Hall performance (thrust, Isp, efficiency, stability) on the H1 EM.
- Measured B(z) of the H1 electromagnet.
- RF/ICP coupling efficiency and electron-current capacity (bench), neutralization margin.
- Variable-capture intake effective-area modulation and capture efficiency.
- Compressor delivered flow, pressure ratio, mass and power.
- Materials coupon / wear tests (AO, sputtering, channel erosion, thermal cycling).
- Thermal balance with the host-spacecraft thermal ICD.

## 6. Open detailed-design work (A9.39 scope)

1. DCR-DBF1-001 intake / compressor finalization (variable effective capture, flux window, altitude schedule).
2. Minimal local Hall atmospheric run package.
3. ICP bench-design closure.
4. Mass / power / thermal roll-up on the finalized intake / compressor.
5. Submission documents.
