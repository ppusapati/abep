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
  * ``HARD_CONSTRAINT_LIMITS`` - the numeric limits of the F7 hard-constraint table (the table itself, with its
    RVM / RFP labels, is an assessment definition: abep_sim/assessment/design_gates.py).

Source: the frozen engineering-constraints snapshot config/requirements/rfp_constraints_v1.json (its
``rfp_constraints_compat`` values) and the mission domain of config/mission/mission_scenario_v1.json, read through
``abep_sim.configuration.load_engineering_constraints`` (sha256-checked against config/MANIFEST.json, fail closed, no
fallback). Values are identical to the pre-re-point ``abep_sim.constants.RFP`` values.
"""
from __future__ import annotations

from types import SimpleNamespace

from ..configuration import load_engineering_constraints as _load

PROVENANCE = ("requirements snapshot of RFP DTDF/06/13516/DSP/ABEP/X/L/M/01 as frozen in "
              "config/requirements/rfp_constraints_v1.json (A9.22 owner decisions items 2 and 5: frozen engineering "
              "inputs, no RFP parsing in design / physics)")


def _snapshot():
    """The frozen engineering-constraint record this seam reads (one place; fails closed)."""
    return SimpleNamespace(**_load())


_S = _snapshot()
SOURCE = _S.source + " via abep_sim.configuration.load_engineering_constraints"

# ------------------------------------------------------------------------------------------------ thrust envelope
THRUST_MIN_MN = _S.thrust_min_mN
THRUST_MAX_MN = _S.thrust_max_mN

# A9.22 G2: F1 C-DRAG-RFP generation filter (intake-face drag <= thrust maximum)
INTAKE_DRAG_GENERATION_LIMIT_MN = THRUST_MAX_MN
INTAKE_DRAG_GENERATION_LIMIT_N = INTAKE_DRAG_GENERATION_LIMIT_MN * 1e-3

# ------------------------------------------------------------------------------------------------ mission domain
# A9.22 G5: mission_domain.altitude_km = [180, 230] (frozen domain constraint, provenance: requirements snapshot)
MISSION_DOMAIN_ALTITUDE_KM = (_S.alt_min_km, _S.alt_max_km)
MISSION_DOMAIN = {"altitude_km": MISSION_DOMAIN_ALTITUDE_KM, "provenance": PROVENANCE, "source": SOURCE}

# ------------------------------------------------------------------------------------------------ hard-constraint limits
# Requirement-derived (frozen snapshot) limits
THRUST_SUSTAINED_MIN_N = THRUST_MIN_MN * 1e-3          # HC-01
THRUST_CAPABILITY_MIN_N = THRUST_MAX_MN * 1e-3         # HC-02
P_BUS_MAX_W = _S.power_max_W                           # HC-03
M_WET_MAX_KG = _S.mass_max_kg                          # HC-04
FIRING_LIFE_MIN_H = _S.ignition_hours                  # HC-07 (subsystem firing-life requirement)
INTAKE_DRAG_MAX_N = THRUST_MAX_MN * 1e-3               # HC-09 (same bound as the F1 generation filter)
# Owner-decision / project-derived limits (not requirement-snapshot values)
I_E_MARGIN_MIN_A = 0.0                                 # HC-05 I_e,cap - I_d,max,H1 > 0 (owner decision)
THERMAL_MARGIN_MIN_K = 50.0                            # HC-06 >= 50 K below validated limits (project)
STATEWISE_T_MINUS_D_MIN_N = 0.0                        # HC-08 AG-13 (owner decision A9.13 S6.15)
PROPELLANT_CAPABILITY_MIN = 1.0                        # HC-10 both propellant paths demonstrated
FEED_STATE_SUFFICIENCY_MIN = 0.0                       # HC-11 AG-12 (owner decision A9.13 S6.21)
RIPPLE_TOLERANCE = None                                # HC-12 measured H-1 ripple tolerance (TBD)

HARD_CONSTRAINT_LIMITS = {
    "HC-01": THRUST_SUSTAINED_MIN_N, "HC-02": THRUST_CAPABILITY_MIN_N, "HC-03": P_BUS_MAX_W, "HC-04": M_WET_MAX_KG,
    "HC-05": I_E_MARGIN_MIN_A, "HC-06": THERMAL_MARGIN_MIN_K, "HC-07": FIRING_LIFE_MIN_H,
    "HC-08": STATEWISE_T_MINUS_D_MIN_N, "HC-09": INTAKE_DRAG_MAX_N, "HC-10": PROPELLANT_CAPABILITY_MIN,
    "HC-11": FEED_STATE_SUFFICIENCY_MIN, "HC-12": RIPPLE_TOLERANCE,
}


def snapshot() -> dict:
    """The frozen engineering inputs of the design layer, with provenance."""
    return {"source": SOURCE, "provenance": PROVENANCE,
            "intake_drag_generation_limit_N": INTAKE_DRAG_GENERATION_LIMIT_N,
            "mission_domain": {"altitude_km": list(MISSION_DOMAIN_ALTITUDE_KM)},
            "hard_constraint_limits": dict(HARD_CONSTRAINT_LIMITS)}
