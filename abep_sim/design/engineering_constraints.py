"""Frozen engineering-constraint seam of the design layer (A9.22 layer separation, owner items 2 and 5).

The design layer reaches requirement-derived numbers ONLY through this module, as frozen engineering inputs. Design
code never parses or queries RFP clauses, the RFP registration, the RVM or owner-question state; clause / RVM ids may
appear in design records only as labels or provenance strings.

Values exposed (all identical to the values the design layer used before A9.22; tests/test_design_layer_separation.py
pins them):

  * ``INTAKE_DRAG_GENERATION_LIMIT_N`` - A9.22 G2 (Option 1): F1 C-DRAG-RFP stays a GENERATION filter on intake-face
    drag, sourced from the frozen engineering-constraints snapshot (thrust maximum 25 mN). Moving it to the assessment
    layer (Option 2) is a separately-approved semantic change (it changes F1-F8 populations).
  * ``MISSION_DOMAIN_ALTITUDE_KM`` - A9.22 G5: ``mission_domain.altitude_km = [180, 230]``, a frozen mission /
    design-state domain constraint (the design-state loader checks every state lies inside it), with provenance back
    to the requirements snapshot; not a runtime dependency on the RFP.
  * ``REQUIREMENT_LIMITS`` - the requirement-derived limits HC-01..HC-04 (thrust floor / capability, P_bus, wet
    mass) of the F7 hard-constraint table. The table itself, with its RVM / RFP labels, is an assessment definition
    (abep_sim/assessment/design_gates.py HARD_CONSTRAINT_LIMITS). A9.24 item 5 (owner decision 2026-10-04): the
    HC-05..HC-12 thresholds (electron-current margin, 50 K thermal protection margin, firing-life basis, statewise
    T - D, propellant capability, feed-state sufficiency, H-1 ripple) are assessment-layer values held in
    config/assessment/gate_thresholds_v1.json; this design module holds none of them. HC-09 stays the design-
    generation filter above (INTAKE_DRAG_GENERATION_LIMIT_N, frozen engineering configuration) and is also reported
    in assessment.

Source (A9.23 owner directive 2026-10-03, docs/decisions/OD_2026_10_03_A9_23_*): the frozen engineering-constraints
artefact config/constraints/engineering_constraints_v1.json ONLY (values), read through
``abep_sim.configuration.load_engineering_constraints`` (sha256-checked against config/MANIFEST.json, fail closed, no
fallback). This module never opens the requirements snapshot (config/requirements/) or the RVM; the constraints file
is derived from that snapshot by scripts/config/build_config.py and carries the requirement ids as provenance only.
Values are identical to the pre-re-point ``abep_sim.constants.RFP`` values.
"""
from __future__ import annotations

from types import SimpleNamespace

from ..configuration import load_engineering_constraints as _load

PROVENANCE = ("frozen engineering constraints config/constraints/engineering_constraints_v1.json, derived from the "
              "requirements snapshot of RFP DTDF/06/13516/DSP/ABEP/X/L/M/01 (A9.22 owner decisions items 2 and 5; "
              "A9.23: frozen engineering inputs, no RFP / RVM parsing in design / physics)")


def _snapshot():
    """The frozen engineering-constraint record this seam reads (one place; fails closed)."""
    return SimpleNamespace(**_load())


_S = _snapshot()
SOURCE = _S.source + " via abep_sim.configuration.load_engineering_constraints"

# ------------------------------------------------------------------------------------------------ thrust envelope
THRUST_MIN_MN = _S.thrust_min_mN
THRUST_MAX_MN = _S.thrust_max_mN

# A9.22 G2: F1 C-DRAG-RFP generation filter (intake-face drag <= thrust maximum; constraint
# intake_drag_generation_limit_mN, derived from the thrust capability in the constraints file)
INTAKE_DRAG_GENERATION_LIMIT_MN = _S.intake_drag_generation_limit_mN
INTAKE_DRAG_GENERATION_LIMIT_N = INTAKE_DRAG_GENERATION_LIMIT_MN * 1e-3

# ------------------------------------------------------------------------------------------------ mission domain
# A9.22 G5: mission_domain.altitude_km = [180, 230] (frozen domain constraint, provenance: requirements snapshot)
MISSION_DOMAIN_ALTITUDE_KM = (_S.alt_min_km, _S.alt_max_km)
MISSION_DOMAIN = {"altitude_km": MISSION_DOMAIN_ALTITUDE_KM, "provenance": PROVENANCE, "source": SOURCE}

# ------------------------------------------------------------------------------------------------ requirement limits
# Requirement-derived (frozen engineering-constraint) limits HC-01..HC-04. HC-05..HC-12 thresholds are assessment-layer
# values (A9.24 item 5): config/assessment/gate_thresholds_v1.json via abep_sim/assessment/design_gates.py.
THRUST_SUSTAINED_MIN_N = THRUST_MIN_MN * 1e-3          # HC-01
THRUST_CAPABILITY_MIN_N = THRUST_MAX_MN * 1e-3         # HC-02
P_BUS_MAX_W = _S.power_max_W                           # HC-03
M_WET_MAX_KG = _S.mass_max_kg                          # HC-04

REQUIREMENT_LIMITS = {"HC-01": THRUST_SUSTAINED_MIN_N, "HC-02": THRUST_CAPABILITY_MIN_N, "HC-03": P_BUS_MAX_W,
                      "HC-04": M_WET_MAX_KG}


def snapshot() -> dict:
    """The frozen engineering inputs of the design layer, with provenance."""
    return {"source": SOURCE, "provenance": PROVENANCE,
            "intake_drag_generation_limit_N": INTAKE_DRAG_GENERATION_LIMIT_N,
            "mission_domain": {"altitude_km": list(MISSION_DOMAIN_ALTITUDE_KM)},
            "requirement_limits": dict(REQUIREMENT_LIMITS)}
