"""Conservative propellant router of the parallel RF || Hall investigation (v2).

Given the available atmospheric feed, the Xe supply state, an operating mode and requested branch flows, the router
returns the RF and Hall feed states, the Hall-cathode Xe flow and the unallocated remainders. It enforces

    mdot_atm,in  = mdot_RF,atm + mdot_Hall,atm + mdot_atm,unused/loss
    mdot_Xe,tank = mdot_RF,Xe + mdot_Hall,Xe + mdot_cathode + mdot_Xe,unused

with no negative terms, no implicit extra propellant and no post-hoc repair. Over-allocation raises
``InfeasibleError(Status.INFEASIBLE_FLOW)``; a stream the mode does not permit raises ``IllegalModeError``; a
negative or non-finite request raises ``ContractError``.

Composition: the router splits the atmospheric stream by mass only; each branch receives the available stream's
composition, pressure and temperature (no implicit species separation). Any branch-specific inlet conditioning must
be an explicit model downstream. The Xe streams are pure Xe with the Xe supply's pressure and temperature.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .parallel_contracts import (BALANCE_REL_TOL, ContractError, FeedState, InfeasibleError, Status, nonempty,
                                 nonneg, positive, pure_xe_feed, evidence_class)
from .propulsion_modes import STREAMS, IllegalModeError, InstalledArchitecture, mode_spec

ROUTER_VERSION = "propellant_router_v1"


@dataclass(frozen=True)
class XeSupply:
    """State of the stored-Xe feed at the metering point. ``max_flow_kg_s`` is the deliverable flow capability of the
    Xe flow control; ``remaining_kg`` the usable Xe left. Both explicit."""
    max_flow_kg_s: float
    remaining_kg: float
    pressure_Pa: float
    temperature_K: float
    source: str
    evidence_class: str
    uncertainty: str
    applicability_domain: str
    validation_status: str

    def __post_init__(self):
        object.__setattr__(self, "max_flow_kg_s", nonneg(self.max_flow_kg_s, "XeSupply.max_flow_kg_s"))
        object.__setattr__(self, "remaining_kg", nonneg(self.remaining_kg, "XeSupply.remaining_kg"))
        object.__setattr__(self, "pressure_Pa", positive(self.pressure_Pa, "XeSupply.pressure_Pa"))
        object.__setattr__(self, "temperature_K", positive(self.temperature_K, "XeSupply.temperature_K"))
        nonempty(self.source, "XeSupply.source")
        evidence_class(self.evidence_class, "XeSupply.evidence_class")
        for f_ in ("uncertainty", "applicability_domain", "validation_status"):
            nonempty(getattr(self, f_), f"XeSupply.{f_}")


@dataclass(frozen=True)
class FlowRequest:
    """Requested flows per stream [kg/s]. Every stream is stated explicitly (zeros allowed); nothing is defaulted."""
    rf_atm: float
    rf_xe: float
    hall_atm: float
    hall_xe: float
    cathode_xe: float

    def __post_init__(self):
        for s in STREAMS:
            object.__setattr__(self, s, nonneg(getattr(self, s), f"requested {s} flow [kg/s]"))

    def as_dict(self) -> dict:
        return {s: getattr(self, s) for s in STREAMS}


@dataclass(frozen=True)
class RouterResult:
    mode: str
    rf_feed: FeedState | None
    hall_feed: FeedState | None
    cathode_xe_kg_s: float
    atm_in_kg_s: float
    xe_available_kg_s: float
    unallocated_atm_kg_s: float
    unallocated_xe_kg_s: float
    atm_balance_residual_kg_s: float
    xe_balance_residual_kg_s: float
    router_version: str = ROUTER_VERSION

    def to_dict(self) -> dict:
        return {"mode": self.mode, "rf_feed": self.rf_feed.to_dict() if self.rf_feed else None,
                "hall_feed": self.hall_feed.to_dict() if self.hall_feed else None,
                "cathode_xe_kg_s": self.cathode_xe_kg_s, "atm_in_kg_s": self.atm_in_kg_s,
                "xe_available_kg_s": self.xe_available_kg_s, "unallocated_atm_kg_s": self.unallocated_atm_kg_s,
                "unallocated_xe_kg_s": self.unallocated_xe_kg_s,
                "atm_balance_residual_kg_s": self.atm_balance_residual_kg_s,
                "xe_balance_residual_kg_s": self.xe_balance_residual_kg_s, "router_version": self.router_version}


def _tol(total: float) -> float:
    return BALANCE_REL_TOL * max(total, 1e-12)


def route(atm_feed: FeedState | None, xe_supply: XeSupply | None, mode, request: FlowRequest,
          architecture: InstalledArchitecture | None = None) -> RouterResult:
    """Route propellant for one operating point. ``atm_feed`` is the AVAILABLE atmospheric stream (after intake and
    compressor); it must contain no Xe. ``xe_supply`` is None when no Xe system is installed."""
    spec = architecture.check_mode(mode) if architecture is not None else mode_spec(mode)
    if not isinstance(request, FlowRequest):
        raise ContractError("request must be a FlowRequest")
    req = request.as_dict()
    allowed = set(spec.allowed_streams())

    # 1. stream legality: a stream the mode does not permit must be exactly zero
    illegal = {s: v for s, v in req.items() if s not in allowed and v != 0.0}
    if illegal:
        raise IllegalModeError(f"mode {spec.mode.value} does not permit streams {sorted(illegal)} "
                               f"(requested {illegal}); allowed {sorted(allowed)}")
    if spec.hall_cathode_required and req["cathode_xe"] <= 0.0:
        raise IllegalModeError(f"mode {spec.mode.value} runs the Hall branch, whose Xe-fed cathode must be booked: "
                               "cathode_xe must be > 0 (a measured/assumed value is required, never an implicit 0)")

    # 2. atmospheric balance
    atm_req = math.fsum([req["rf_atm"], req["hall_atm"]])
    if atm_feed is None:
        if atm_req > 0.0:
            raise InfeasibleError(Status.INFEASIBLE_FLOW, "atmospheric flow requested but no atmospheric feed")
        atm_in = 0.0
    else:
        if not isinstance(atm_feed, FeedState):
            raise ContractError("atm_feed must be a FeedState")
        if atm_feed.has_xe():
            raise ContractError("the available atmospheric feed contains Xe; Xe is routed only from the Xe supply")
        atm_in = atm_feed.mdot_total_kg_s
    if atm_req > atm_in + _tol(atm_in):
        raise InfeasibleError(Status.INFEASIBLE_FLOW,
                              f"atmospheric over-allocation: RF {req['rf_atm']!r} + Hall {req['hall_atm']!r} = "
                              f"{atm_req!r} kg/s > available {atm_in!r} kg/s")
    unalloc_atm = max(atm_in - atm_req, 0.0)
    atm_res = atm_in - (req["rf_atm"] + req["hall_atm"] + unalloc_atm)

    # 3. Xe balance
    xe_req = math.fsum([req["rf_xe"], req["hall_xe"], req["cathode_xe"]])
    if xe_supply is None:
        if xe_req > 0.0:
            raise InfeasibleError(Status.INFEASIBLE_FLOW, "Xe flow requested but no Xe system is installed")
        xe_avail = 0.0
    else:
        if not isinstance(xe_supply, XeSupply):
            raise ContractError("xe_supply must be an XeSupply")
        xe_avail = xe_supply.max_flow_kg_s
        if xe_req > 0.0 and xe_supply.remaining_kg <= 0.0:
            raise InfeasibleError(Status.INFEASIBLE_FLOW, "Xe requested but the Xe supply is exhausted")
    if xe_req > xe_avail + _tol(xe_avail):
        raise InfeasibleError(Status.INFEASIBLE_FLOW,
                              f"Xe over-allocation: {xe_req!r} kg/s requested > deliverable {xe_avail!r} kg/s")
    unalloc_xe = max(xe_avail - xe_req, 0.0)
    xe_res = xe_avail - (req["rf_xe"] + req["hall_xe"] + req["cathode_xe"] + unalloc_xe)
    for name, r, tot in (("atmospheric", atm_res, atm_in), ("Xe", xe_res, xe_avail)):
        if abs(r) > _tol(tot) * 10:
            raise RuntimeError(f"{name} mass-balance gate failed: residual {r!r} kg/s")

    # 4. branch feeds
    def xe_feed(mdot, who):
        return pure_xe_feed(mdot, pressure_Pa=xe_supply.pressure_Pa, temperature_K=xe_supply.temperature_K,
                            source=f"{xe_supply.source} | routed to {who}", evidence_class_=xe_supply.evidence_class,
                            uncertainty=xe_supply.uncertainty, applicability_domain=xe_supply.applicability_domain,
                            validation_status=xe_supply.validation_status)

    rf_feed = hall_feed = None
    if spec.rf_enabled:
        if spec.rf_atm_allowed:
            rf_feed = atm_feed.with_mdot(req["rf_atm"], source_suffix="routed to RF") if atm_feed else None
        elif spec.rf_xe_allowed:
            rf_feed = xe_feed(req["rf_xe"], "RF") if xe_supply is not None else None
    if spec.hall_enabled:
        if spec.hall_atm_allowed:
            hall_feed = atm_feed.with_mdot(req["hall_atm"], source_suffix="routed to Hall anode") if atm_feed else None
        elif spec.hall_xe_allowed:
            hall_feed = xe_feed(req["hall_xe"], "Hall anode") if xe_supply is not None else None
    return RouterResult(spec.mode.value, rf_feed, hall_feed, req["cathode_xe"], atm_in, xe_avail,
                        unalloc_atm, unalloc_xe, atm_res, xe_res)


# ------------------------------------------------------------------ rarefied-flow regime classification (sec. 33)

REGIME_THRESHOLDS = {"free_molecular_min_Kn": 10.0, "continuum_max_Kn": 0.01,
                     "source": ("conventional Knudsen-number regime boundaries of rarefied gas dynamics (e.g. Bird, "
                                "Molecular Gas Dynamics and the Direct Simulation of Gas Flows, 1994) - verify"),
                     "note": "the slip band 0.01-0.1 is grouped with TRANSITIONAL (flagged for DSMC validation)"}


def knudsen(mean_free_path_m: float, length_m: float) -> float:
    """Kn = lambda / L with both inputs explicit (no default molecular diameter or pressure)."""
    return positive(mean_free_path_m, "mean free path [m]") / positive(length_m, "characteristic length [m]")


def flow_regime(Kn: float) -> dict:
    """FREE_MOLECULAR (TPMC applicable) / TRANSITIONAL (flag for DSMC validation) / CONTINUUM_APPROX. No correction
    is applied: DSMC-derived corrections enter only as external, sha-pinned data."""
    k = positive(Kn, "Kn")
    if k >= REGIME_THRESHOLDS["free_molecular_min_Kn"]:
        r, action = "FREE_MOLECULAR", "TPMC applicable"
    elif k > REGIME_THRESHOLDS["continuum_max_Kn"]:
        r, action = "TRANSITIONAL", "flag for DSMC validation; no automatic correction"
    else:
        r, action = "CONTINUUM_APPROX", "continuum/viscous treatment; outside TPMC applicability"
    return {"Kn": k, "regime": r, "action": action, "thresholds": REGIME_THRESHOLDS}
