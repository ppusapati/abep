"""Operating inputs: the ONE seam through which owner-supplied engineering inputs reach the physics / mission modules.

Owner directive A9.22 (2026-10-03, docs/decisions/OD_2026_10_03_A9_22_*): physics never reads or interprets RFP / RVM /
clause ids; requirements reach physics only as frozen engineering inputs. Physics functions therefore take explicit
parameters (mission_hours, firing_hours, thrust_cap_mN, P_bus_max_W, mass limits as DesignConstraints, ...) that their
callers supply. Where no caller supplies one yet, the default comes from this module, and only from this module.

Today the values are read from abep_sim.constants.RFP (the recorded engineering-constraint snapshot). The integrator will
later re-point this seam to the frozen engineering configuration (config/mission/mission_scenario_v1.json) without
touching any physics module. Nothing here is an RFP parser: these are plain numbers with a provenance string.
"""
from __future__ import annotations

from .constants import RFP

SOURCE = "abep_sim.constants.RFP (recorded engineering-constraint snapshot); seam to be re-pointed to " \
         "config/mission/mission_scenario_v1.json by the integrator"

# Mission duration basis for mission-integrated quantities (mission propagation length, AO fluence / life exposure,
# mission-integrated Xe accounting). GOVERNED BASELINE CHANGE A9.22 G1 (owner decision 2026-10-03,
# docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json, G1_MISSION_LIFE = MISSION_DURATION_26280_H):
# 26,280 h (3 years of 8,760 h) replaces the earlier 26,000 h (constants.RFP.mission_hours, kept there unchanged as the
# recorded value until the integrator re-points this seam). Applied once, logged in docs/HISTORY.md 'A9.22 G1 governed
# baseline change' with every moved golden value.
MISSION_DURATION_BASIS_H: float = 26280.0
MISSION_HOURS: float = MISSION_DURATION_BASIS_H
# SUBSYSTEM_FIRING_LIFE_ASSUMPTION (A9.22 G1: 15,000 h kept ONLY as an explicitly labelled thruster/subsystem
# firing-life assumption, i.e. a required firing life). Never the mission duration, never a mission-integration basis.
SUBSYSTEM_FIRING_LIFE_ASSUMPTION_H: float = RFP.ignition_hours
FIRING_HOURS: float = SUBSYSTEM_FIRING_LIFE_ASSUMPTION_H
FIRING_HOURS_LABEL = "SUBSYSTEM_FIRING_LIFE_ASSUMPTION"
# The superseded mission basis, named only so that immutable history (golden_v1 and the golden_v2 non-converged
# reference fixture) can be recomputed exactly as it was generated. Never a default for new work.
HISTORICAL_MISSION_HOURS_PRE_A9_22: float = 26000.0

THRUST_MIN_mN: float = RFP.thrust_min_mN
THRUST_MAX_mN: float = RFP.thrust_max_mN          # thrust cap / upper constraint
P_BUS_MAX_W: float = RFP.power_max_W
MASS_MAX_KG: float = RFP.mass_max_kg


def as_dict() -> dict:
    """The current operating inputs with their source (for provenance blocks in outputs)."""
    return {"mission_hours": MISSION_HOURS, "mission_hours_basis": "A9.22 G1 MISSION_DURATION_26280_H",
            "firing_hours": FIRING_HOURS, "firing_hours_label": FIRING_HOURS_LABEL, "thrust_min_mN": THRUST_MIN_mN,
            "thrust_max_mN": THRUST_MAX_mN, "P_bus_max_W": P_BUS_MAX_W, "mass_max_kg": MASS_MAX_KG, "source": SOURCE}
