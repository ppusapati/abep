"""H-1 geometric admissibility against the declared H-1 geometric windows (A9.22 layer separation).

Verbatim library copy of ``geometric_admissibility`` and ``ROUNDING_REL`` from
docs/hardware/h1_freeze_candidate/build_h1_freeze_candidate.py (the F5 builder). Before A9.22 the F7 design layer
imported that builder by path; the builder and abep_sim/design/architecture_optimizer.py now both call this library.

One difference from the builder original: the window definition ``xdef`` has no in-library default. The builder
passes its own ``x_hall_definition()`` (built from the pinned H2-1 / A9-revision records); the F7 optimizer passes the
identical committed record ``x_hall_design_space.definition`` of docs/hardware/h1_freeze_candidate/
h1_freeze_candidate_v1.json (equality checked by tests/test_design_layer_separation.py). Never a PASS.
"""
from __future__ import annotations

import bisect
import math

# The H2-1 windows and corners are published to 4 significant figures; window edges are compared with this relative
# rounding allowance so that the published corners themselves are not rejected by their own rounding. It is a
# publication-rounding treatment, not a physical tolerance.
ROUNDING_REL = 1e-3


def geometric_admissibility(h_mm: float, d_mean_mm: float, L_mm: float, assumptions: str = "worst_case_assumptions",
                            xdef: dict | None = None) -> dict:
    """Check a candidate (h, d_mean, L) against the declared H-1 geometric windows only.

    Returns WITHIN_DECLARED_GEOMETRIC_WINDOWS or OUTSIDE_DECLARED_GEOMETRIC_WINDOWS (or OUT_OF_DOMAIN for an h outside
    the tabulated inner-coil floor). It is never a PASS: FEMM, thermal, supply, mass and every Hall performance
    quantity stay NOT_EVALUATED. Between tabulated h rows the larger (upper-row) floor is used (conservative)."""
    if xdef is None:
        raise ValueError("xdef (the declared H-1 geometric window definition) is required")
    c = xdef["constraints"]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (h_mm, d_mean_mm, L_mm)):
        return {"status": "OUT_OF_DOMAIN", "violations": ["non-finite or non-positive input"],
                "not_evaluated": xdef["not_evaluated"], "performance": "NOT_EVALUATED"}
    floors = c["inner_coil_solid_core_floor_mm"]
    if assumptions not in next(iter(floors.values())):
        raise ValueError(f"unknown assumption set {assumptions!r}")
    hs = sorted(float(k) for k in floors)
    if h_mm < hs[0] or h_mm > hs[-1]:
        return {"status": "OUT_OF_DOMAIN", "violations": [f"h {h_mm} mm outside the tabulated floor range "
                                                          f"[{hs[0]}, {hs[-1]}] mm"],
                "not_evaluated": xdef["not_evaluated"], "performance": "NOT_EVALUATED"}
    k = bisect.bisect_left(hs, h_mm)
    key = {float(kk): kk for kk in floors}[hs[k]]
    floor = floors[key][assumptions]
    viol = []
    area_cm2 = math.pi * h_mm * d_mean_mm / 100.0
    tol = ROUNDING_REL
    a0, a1 = c["area_window_cm2"]
    if not (a0 * (1 - tol) <= area_cm2 <= a1 * (1 + tol)):
        viol.append(f"area {area_cm2:.4g} cm^2 outside [{a0}, {a1}]")
    r0, r1 = c["d_over_h_window"]
    if not (r0 * (1 - tol) <= d_mean_mm / h_mm <= r1 * (1 + tol)):
        viol.append(f"d_mean/h {d_mean_mm / h_mm:.4g} outside [{r0}, {r1}]")
    l0, l1 = c["L_over_h_window"]
    if not (l0 * (1 - tol) <= L_mm / h_mm <= l1 * (1 + tol)):
        viol.append(f"L/h {L_mm / h_mm:.4g} outside [{l0}, {l1}]")
    if d_mean_mm < floor:
        viol.append(f"d_mean {d_mean_mm} mm below the inner-coil solid-core floor {floor} mm ({assumptions}, h row "
                    f"{key} mm)")
    return {"status": "OUTSIDE_DECLARED_GEOMETRIC_WINDOWS" if viol else "WITHIN_DECLARED_GEOMETRIC_WINDOWS",
            "violations": viol, "floor_row_h_mm": key, "floor_mm": floor, "assumptions": assumptions,
            "not_evaluated": xdef["not_evaluated"], "performance": "NOT_EVALUATED"}
