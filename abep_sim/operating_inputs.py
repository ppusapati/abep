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
# mission-integrated Xe accounting).
MISSION_HOURS: float = RFP.mission_hours
# Subsystem firing-life assumption (thruster / subsystem minimum firing life used as a life requirement). Never the
# mission duration.
FIRING_HOURS: float = RFP.ignition_hours

THRUST_MIN_mN: float = RFP.thrust_min_mN
THRUST_MAX_mN: float = RFP.thrust_max_mN          # thrust cap / upper constraint
P_BUS_MAX_W: float = RFP.power_max_W
MASS_MAX_KG: float = RFP.mass_max_kg


def as_dict() -> dict:
    """The current operating inputs with their source (for provenance blocks in outputs)."""
    return {"mission_hours": MISSION_HOURS, "firing_hours": FIRING_HOURS, "thrust_min_mN": THRUST_MIN_mN,
            "thrust_max_mN": THRUST_MAX_mN, "P_bus_max_W": P_BUS_MAX_W, "mass_max_kg": MASS_MAX_KG, "source": SOURCE}
