"""Operating inputs: the ONE seam through which owner-supplied engineering inputs reach the physics / mission modules.

Owner directive A9.22 (2026-10-03, docs/decisions/OD_2026_10_03_A9_22_*): physics never reads or interprets RFP / RVM /
clause ids; requirements reach physics only as frozen engineering inputs. Physics functions therefore take explicit
parameters (mission_hours, firing_hours, thrust_cap_mN, P_bus_max_W, mass limits as DesignConstraints, ...) that their
callers supply. Where no caller supplies one, the default comes from this module, and only from this module.

Source (A9.23; A9.24 item 4; owner ruling 2026-10-04): the operating-scenario choices of
config/mission/mission_scenario_v2.json ONLY (mission-integration horizon, firing / integration duration, Xe-sizing
thrust target, commanded-thrust cap, P_bus throttling cap: explicit, independently versioned frozen values with
initial_basis provenance, never copied from or read from the engineering constraints; a changed choice needs a new
scenario version). The wet-mass limit and the altitude band are engineering / assessment / domain constraints and are not
operating inputs (the frozen design-state set is the physics environment). Read through
abep_sim.configuration.load_operating_inputs (sha256-checked against config/MANIFEST.json and OPERATING_SCENARIO_PIN;
fails closed, no fallback, CLAUDE.md rule 3). This module never opens the requirements snapshot (config/requirements/)
or anything under docs/requirements/; nothing here is an RFP parser: these are plain numbers with a provenance string.
The values are identical to the pre-re-point values (tests/test_a9_22_operating_inputs.py pins them).
"""
from __future__ import annotations

from .configuration import load_operating_inputs as _load

_V = _load()

SOURCE = _V["source"] + " via abep_sim.configuration.load_operating_inputs"

# Mission duration basis for mission-integrated quantities (mission propagation length, AO fluence / life exposure,
# mission-integrated Xe accounting, cathode start count, mission reliability horizon). GOVERNED BASELINE CHANGE A9.22 G1
# (owner decision 2026-10-03, docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json,
# G1_MISSION_LIFE = MISSION_DURATION_26280_H): 26,280 h (3 years of 8,760 h) replaces the earlier 26,000 h
# (constants.RFP.mission_hours, immutable, HISTORICAL_CONSTANT_NOT_CONSUMED). Logged in docs/HISTORY.md 'A9.22 G1
# governed baseline change' and '... (system.py completion)'.
MISSION_DURATION_BASIS_H: float = _V["mission_hours"]
MISSION_HOURS: float = MISSION_DURATION_BASIS_H
# SUBSYSTEM_FIRING_LIFE_ASSUMPTION (A9.22 G1: 15,000 h kept ONLY as an explicitly labelled thruster/subsystem
# firing-life assumption, i.e. a required firing life / firing-integrated basis). Never the mission duration.
SUBSYSTEM_FIRING_LIFE_ASSUMPTION_H: float = _V["firing_hours"]
FIRING_HOURS: float = SUBSYSTEM_FIRING_LIFE_ASSUMPTION_H
FIRING_HOURS_LABEL = _V["firing_hours_label"]
# The superseded mission basis, named only so that immutable history (golden_v1 and the golden_v2 non-converged
# reference fixture) can be recomputed exactly as it was generated. Never a default for new work.
HISTORICAL_MISSION_HOURS_PRE_A9_22: float = _V["historical_mission_hours"]

THRUST_MIN_mN: float = _V["thrust_min_mN"]
THRUST_MAX_mN: float = _V["thrust_max_mN"]          # thrust cap / upper constraint
P_BUS_MAX_W: float = _V["P_bus_max_W"]


def as_dict() -> dict:
    """The current operating inputs with their source (for provenance blocks in outputs)."""
    return {"mission_hours": MISSION_HOURS, "mission_hours_basis": "A9.22 G1 MISSION_DURATION_26280_H",
            "firing_hours": FIRING_HOURS, "firing_hours_label": FIRING_HOURS_LABEL, "thrust_min_mN": THRUST_MIN_mN,
            "thrust_max_mN": THRUST_MAX_mN, "P_bus_max_W": P_BUS_MAX_W, "source": SOURCE}
