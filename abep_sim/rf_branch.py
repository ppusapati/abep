"""Standalone RF propulsion branch (parallel RF || Hall investigation, v2).

Wraps one RF performance source behind the common ``BranchResult`` contract:

* ``REDUCED_RF_MODEL`` - ``rf_reduced.run`` (model-derived, UNVALIDATED, never score-bearing);
* ``ADMITTED_RF_MAP``  - an admitted RF response map (``rf_map``), the only path that may be score-bearing, and only
  inside its admitted domain (added in P4).

Score-bearing rule (spec sec. 14): ``score_bearing=True`` with the reduced model raises ``ScoreBearingError``. The
reduced model may generate hypotheses, grids and experiment plans; it never declares an architecture viable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import rf_reduced
from .parallel_contracts import (BranchResult, ContractError, FeedState, Quantity, Status, TBD, real, value_of)
from .propulsion_modes import IllegalModeError, mode_spec

REDUCED_RF_MODEL = "REDUCED_RF_MODEL"
ADMITTED_RF_MAP = "ADMITTED_RF_MAP"


class ScoreBearingError(ContractError):
    """A score-bearing evaluation was requested from a source that may not be score-bearing."""


def unit_vector(v, what: str) -> tuple:
    if len(v) != 3:
        raise ContractError(f"{what} must have 3 components")
    x = tuple(real(c, what) for c in v)
    n = math.sqrt(sum(c * c for c in x))
    if abs(n - 1.0) > 1e-9:
        raise ContractError(f"{what} must be a unit vector (|v| = {n!r})")
    return x


@dataclass(frozen=True)
class RFBranchConfig:
    chamber: rf_reduced.RFChamberSpec
    coupling: rf_reduced.RFCoupling
    nozzle: rf_reduced.RFNozzleSpec
    P_magnet_W: Quantity                  # RF coil load (0 W for a permanent magnet, stated with evidence)
    eta_magnet_supply: Quantity           # bus -> magnet-coil efficiency (1 for a permanent magnet, stated)
    thrust_axis: tuple                    # unit vector in the spacecraft frame (+x = flight direction)
    startup_energy_J: object              # Quantity | TBD
    startup_time_s: object                # Quantity | TBD


def _ev(q):
    return q.value if isinstance(q, Quantity) else q


def evaluate(feed: FeedState | None, mode, P_dc_W: float, config: RFBranchConfig, *, source=REDUCED_RF_MODEL,
             score_bearing: bool = False, rf_map=None) -> BranchResult:
    spec = mode_spec(mode)
    if not spec.rf_enabled:
        raise IllegalModeError(f"mode {spec.mode.value} does not enable the RF branch")
    if feed is None:
        raise ContractError("the RF branch needs a routed feed")
    if spec.rf_atm_allowed and (feed.has_xe() or not feed.has_atmospheric()):
        raise IllegalModeError(f"{spec.mode.value}: the RF feed must be atmospheric (no Xe)")
    if spec.rf_xe_allowed and not feed.is_pure_xe():
        raise IllegalModeError(f"{spec.mode.value}: the RF feed must be pure Xe")
    axis = unit_vector(config.thrust_axis, "RF thrust_axis")

    if source == ADMITTED_RF_MAP:
        if rf_map is None:
            raise ContractError("ADMITTED_RF_MAP requested without an rf_map")
        return rf_map.branch_result(feed, spec, P_dc_W, config, axis, score_bearing=score_bearing)
    if source != REDUCED_RF_MODEL:
        raise ContractError(f"unknown RF source {source!r}")
    if score_bearing:
        raise ScoreBearingError("the reduced RF model can never be score-bearing: RF absolute thrust for a "
                                "score-bearing evaluation must come from measured hardware or an ADMITTED_RF_MAP")

    o = rf_reduced.run(feed, P_dc_W, config.chamber, config.coupling, config.nozzle, config.P_magnet_W)
    status = Status(o["model_status"])
    eta_mag = value_of(config.eta_magnet_supply, "eta_magnet_supply", "1")
    if not 0.0 < eta_mag <= 1.0:
        raise ContractError("eta_magnet_supply must be in (0, 1]")
    P_mag = o["magnet_power_W"]
    P_bus = o["P_dc_W"] + P_mag / eta_mag
    T = o.get("thrust_N")
    if isinstance(T, float):
        vec = tuple(T * a for a in axis)
        T_ax = vec[0]
    else:
        T = T if isinstance(T, TBD) else TBD("thrust_N", o.get("reason", "reduced model produced no thrust"))
        vec, T_ax = T, T
    atm = feed.mdot_total_kg_s if spec.rf_atm_allowed else 0.0
    xe = feed.mdot_total_kg_s if spec.rf_xe_allowed else 0.0
    heat = {"rf_generator_matching_W": o["P_dc_W"] - o["P_net_feed_W"],
            "rf_antenna_W": o["P_net_feed_W"] - o["P_absorbed_W"],
            "rf_magnet_W": P_mag / eta_mag}
    if "power_partition_W" in o:
        heat["rf_chamber_walls_W"] = o["power_partition_W"]["wall"]
    loads = {"rf_source": {"P_load_W": o["P_net_feed_W"], "efficiency": config.coupling.eta_bus_to_feed.to_dict()},
             "rf_magnet": {"P_load_W": P_mag, "efficiency": config.eta_magnet_supply.to_dict()}}
    return BranchResult(
        branch_id="rf", operating_mode=spec.mode.value,
        propellant_source="atmosphere" if spec.rf_atm_allowed else "xe_tank",
        thrust_vector_N=vec, thrust_axial_N=T_ax, P_loads=loads, P_bus_W=P_bus,
        mdot_atm_kg_s=atm, mdot_xe_kg_s=xe, mdot_cathode_xe_kg_s=0.0,
        Isp_s=o.get("Isp_s", TBD("Isp_s", "no thrust result")),
        utilization=o.get("utilization", TBD("utilization", "no plasma solution")),
        heat_loads_W=heat,
        plume_divergence_deg=o.get("plume_divergence_deg", TBD("plume_divergence_deg", "no plasma solution")),
        startup_energy_J=_ev(config.startup_energy_J), startup_time_s=_ev(config.startup_time_s),
        status=status, evidence_class=rf_reduced.EVIDENCE_CLASS,
        applicability_domain=("reduced 0-D RF model; chemistry and nozzle unvalidated; hypothesis generation and "
                              "experiment planning only"),
        validation_status=rf_reduced.VALIDATION_STATUS, score_bearing=False,
        provenance={"source": REDUCED_RF_MODEL, "model_id": rf_reduced.MODEL_ID, "reduced_outputs": o},
        limitations=rf_reduced.UNRESOLVED_PHYSICS)
