# P3 — Hall thruster magnetic field B(z): submission-safe statement

**Closure state: FROZEN FOR EM** (design baseline field by analysis; verification by test on the engineering model).

## Statement for the technical proposal

The Hall thruster uses an electromagnet circuit: a single inner coil and a single outer coil on a solid FeCo-2V inner
core, with a high-purity-iron outer return path and exit pole pieces. Coil currents are controlled independently and
recorded in telemetry, so the field level is an operating variable and the channel geometry does not change.

The radial magnetic field along the channel mean radius has been derived by analysis for the reference geometry
(70 mm mean diameter, 12 mm channel width, 103.2 mm channel length). The analysis uses an axisymmetric nonlinear
magnetostatic finite-element model with the suppliers' published B-H data. The model was checked against analytic
solenoid fields, an exact iron image solution and an exact nonlinear-core solution. The mesh is converged.

- **Field shape.** The field rises monotonically from a near-zero value at the anode to a maximum in the exit pole gap.
  This matches the design target of a low anode-region field and a peak at the channel exit.
- **Field level.** The design field band of 70–269 G at the channel exit is reached at about 150–590 total ampere-turns.
  The 403 G capability level is reached at about 880 ampere-turns. Both are inside the coil ampere-turn ratings of the
  design baseline. Over the analysed assembly and material tolerance range, the band upper end needs at most about
  785 ampere-turns.

The field level and shape will be finalised at PDR/CDR together with the shielded pole-piece contour. Verification is by
test: B(z) is mapped on the engineering model along the channel mean radius at the operating coil currents, with a
hot-state reference field sensor.

## What this statement does not claim

- The field is analysis-derived. It is not measured, and it is not a FEMM result.
- No thruster performance is inferred from the magnetic field.
- The analysed circuit has flat exit pole pieces. The magnetically shielded pole contour, the trim coil, the
  hot-temperature B-H data and the procured material lots are open design or verification items. They are not covered
  by the present analysis.
- The project's earlier Hall simulations used a field-shape surrogate taken from a different thruster. They remain
  surrogate results. Adopting the analysis-derived field in the controlled baseline needs a design change request
  (DCR-DBF1-002), which is awaiting owner approval.

## Governing evidence

| record | path | sha256 |
|---|---|---|
| FE record | `docs/hardware/h1_bz/h1_bz_fe_v1.json` | see `docs/closure/P3_h1_magnetic_field_closure_v1.json` |
| preregistration (governing) | `docs/hardware/h1_bz/h1_bz_fe_prereg_v4.json` | `98fab01d030918e9385fce417a085e580e7c355973e9adf4bcab0e05b5434e9e` |
| B-H data | `docs/hardware/h1_bz/bh_curves_v1.json` | `6f940f88bf672e0d4e29b109081a5c6e1506e8f566a9b2e56c54361971f22747` |
| profile files | `hallthruster_bridge/bfield/h1_fe_v1/MANIFEST.json` | per file in the manifest |
| design change request | `docs/baseline/DCR-002/dcr002_request_v1.json` | REQUESTED_PENDING_OWNER_APPROVAL |

Internal numbers above, such as ampere-turns and B_anode/B_peak, are analysis results at the reference operating point.
They are not contractual acceptance criteria.
