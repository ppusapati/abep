"""Hall branch adapter (parallel RF || Hall investigation, v2).

Exposes the Hall thruster as an independent branch through the common ``BranchResult`` contract. It adds NO Hall
physics and duplicates none: performance comes only from explicitly acceptable evidence.

Sources
* ``TRANSPORT_CLOSURE`` - an ensemble member id. It goes through ``hall_ensemble.require_admitted``: screening
  candidates are refused in every use (CLAUDE.md: they never produce design maps and never enter the architecture
  trade or UQ), and so is any id that is not an admitted member. The credible set is empty today, so every such call
  raises ``HallEvidenceError``. A design Hall map for an admitted member would be read with ``hall_map.HallMap``
  (which re-checks admission); that path activates only once a member is admitted.
* ``POINT_EVIDENCE`` - explicit operating points (``HallPoint``: measured Vyovrinda hardware or published analog
  hardware), each with its own declared domain. A query must fall inside one point's domain; there is NO
  interpolation and NO scaling between points (that would be an unvalidated model). Outside every point:
  OUT_OF_DOMAIN.

Score-bearing rule
* analog hardware: never score-bearing;
* Vyovrinda hardware: score-bearing only when the evidence record's canonical sha256 is admitted by an owner
  decision file (``decided_by: owner``, ``admits_hall_evidence_sha256``), pinned by its own sha256.
* HALL_ATM and HALL_XE are kept distinct: a point's propellant family must match the routed anode feed.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

from .parallel_contracts import (BranchResult, ContractError, FeedState, Quantity, Status, TBD, nonempty,
                                 value_of)
from .propulsion_modes import IllegalModeError, mode_spec

TRANSPORT_CLOSURE = "TRANSPORT_CLOSURE"
POINT_EVIDENCE = "POINT_EVIDENCE"


class HallEvidenceError(ContractError):
    """The requested Hall evidence may not be used (unadmitted closure, screening candidate, non-admitted score use)."""


@dataclass(frozen=True)
class HallPoint:
    """One Hall operating point with evidence. ``domain`` gives inclusive [lo, hi] ranges for anode_mdot_kg_s,
    P_discharge_W and V_d_V inside which this point may be used (a stated applicability, not a model)."""
    point_id: str
    hardware: str                      # "vyovrinda:<article>" or "analog:<device>"
    propellant_family: str             # "xe" | "atmospheric"
    anode_mdot_kg_s: Quantity
    P_discharge_W: Quantity
    V_d_V: Quantity
    thrust_N: Quantity
    plume_divergence_deg: object       # Quantity | TBD
    domain: dict
    source: str

    def __post_init__(self):
        nonempty(self.point_id, "HallPoint.point_id")
        if not (self.hardware.startswith("vyovrinda:") or self.hardware.startswith("analog:")):
            raise ContractError("HallPoint.hardware must be 'vyovrinda:<article>' or 'analog:<device>'")
        if self.propellant_family not in ("xe", "atmospheric"):
            raise ContractError("HallPoint.propellant_family must be 'xe' or 'atmospheric'")
        for k in ("anode_mdot_kg_s", "P_discharge_W", "V_d_V"):
            r = self.domain.get(k)
            if not (isinstance(r, (list, tuple)) and len(r) == 2 and r[0] <= r[1]):
                raise ContractError(f"HallPoint.domain.{k} must be [lo, hi]")
        nonempty(self.source, "HallPoint.source")

    def canonical_sha256(self) -> str:
        body = {"point_id": self.point_id, "hardware": self.hardware, "propellant_family": self.propellant_family,
                "anode_mdot_kg_s": self.anode_mdot_kg_s.to_dict(), "P_discharge_W": self.P_discharge_W.to_dict(),
                "V_d_V": self.V_d_V.to_dict(), "thrust_N": self.thrust_N.to_dict(),
                "plume_divergence_deg": self.plume_divergence_deg.to_dict(), "domain": self.domain,
                "source": self.source}
        return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class HallBranchConfig:
    """Loads/efficiencies of the Hall electrical branch at the evaluated point (bus_power_v2 load planes), each a
    Quantity; the thrust axis; start-up evidence (Quantity or TBD)."""
    eta_discharge_supply: Quantity
    P_magnet_W: Quantity
    eta_magnet_supply: Quantity
    P_keeper_W: Quantity
    eta_keeper_supply: Quantity
    P_heater_W: Quantity
    eta_heater_supply: Quantity
    thrust_axis: tuple
    startup_energy_J: object
    startup_time_s: object


def check_transport_closure(member_id: str, ensemble: dict | None = None) -> None:
    """Refuse screening candidates and unadmitted ids in EVERY use (not only score-bearing)."""
    from .hall_ensemble import require_admitted
    try:
        require_admitted(member_id, ensemble)
    except ValueError as exc:
        raise HallEvidenceError(f"Hall transport closure {member_id!r} may not be used in v2: {exc}") from None


def _admitted(point: HallPoint, admission_file: str | None, root: str | None) -> bool:
    if admission_file is None:
        return False
    p = os.path.join(root or ".", admission_file)
    dec = json.load(open(p))
    return dec.get("decided_by") == "owner" and dec.get("admits_hall_evidence_sha256") == point.canonical_sha256()


def evaluate(feed: FeedState | None, mode, cathode_xe_kg_s: float, P_discharge_W: float, V_d_V: float,
             config: HallBranchConfig, *, source: str, points=(), member_id: str | None = None,
             ensemble: dict | None = None, score_bearing: bool = False, admission_file: str | None = None,
             root: str | None = None) -> BranchResult:
    spec = mode_spec(mode)
    if not spec.hall_enabled:
        raise IllegalModeError(f"mode {spec.mode.value} does not enable the Hall branch")
    if feed is None:
        raise ContractError("the Hall branch needs a routed anode feed")
    if cathode_xe_kg_s <= 0:
        raise IllegalModeError("the Hall cathode Xe flow must be booked (> 0)")
    family = "xe" if feed.is_pure_xe() else "atmospheric"
    if spec.hall_xe_allowed and family != "xe":
        raise IllegalModeError(f"{spec.mode.value}: the Hall anode feed must be pure Xe")
    if spec.hall_atm_allowed and (feed.has_xe() or family != "atmospheric"):
        raise IllegalModeError(f"{spec.mode.value}: the Hall anode feed must be atmospheric")

    if source == TRANSPORT_CLOSURE:
        if member_id is None:
            raise ContractError("TRANSPORT_CLOSURE needs member_id")
        check_transport_closure(member_id, ensemble)
        raise HallEvidenceError("an admitted member exists but no design Hall map was supplied for it; v2 reads "
                                "design maps only through hall_map.HallMap (not wired until a member is admitted)")
    if source != POINT_EVIDENCE:
        raise ContractError(f"unknown Hall source {source!r}")

    from .rf_branch import unit_vector
    axis = unit_vector(config.thrust_axis, "Hall thrust_axis")
    q = {"anode_mdot_kg_s": feed.mdot_total_kg_s, "P_discharge_W": P_discharge_W, "V_d_V": V_d_V}
    match = [p for p in points if p.propellant_family == family
             and all(p.domain[k][0] <= v <= p.domain[k][1] for k, v in q.items())]
    loads = {"hall_discharge": {"P_load_W": P_discharge_W, "efficiency": config.eta_discharge_supply.to_dict()},
             "hall_magnet": {"P_load_W": value_of(config.P_magnet_W, "P_magnet_W", "W"),
                             "efficiency": config.eta_magnet_supply.to_dict()},
             "cathode_keeper": {"P_load_W": value_of(config.P_keeper_W, "P_keeper_W", "W"),
                                "efficiency": config.eta_keeper_supply.to_dict()},
             "cathode_heater": {"P_load_W": value_of(config.P_heater_W, "P_heater_W", "W"),
                                "efficiency": config.eta_heater_supply.to_dict()}}
    P_bus = sum(v["P_load_W"] / e for v, e in (
        (loads["hall_discharge"], value_of(config.eta_discharge_supply, "eta_d", "1")),
        (loads["hall_magnet"], value_of(config.eta_magnet_supply, "eta_mag", "1")),
        (loads["cathode_keeper"], value_of(config.eta_keeper_supply, "eta_k", "1")),
        (loads["cathode_heater"], value_of(config.eta_heater_supply, "eta_h", "1"))))
    common = dict(branch_id="hall", operating_mode=spec.mode.value,
                  propellant_source="xe_tank" if family == "xe" else "atmosphere",
                  mdot_atm_kg_s=feed.mdot_total_kg_s if family == "atmospheric" else 0.0,
                  mdot_xe_kg_s=feed.mdot_total_kg_s if family == "xe" else 0.0,
                  mdot_cathode_xe_kg_s=cathode_xe_kg_s, P_loads=loads, P_bus_W=P_bus,
                  startup_energy_J=getattr(config.startup_energy_J, "value", config.startup_energy_J),
                  startup_time_s=getattr(config.startup_time_s, "value", config.startup_time_s),
                  heat_loads_W={}, utilization=TBD("utilization", "not part of the point evidence"))
    if not match:
        if score_bearing:
            raise HallEvidenceError("no admitted Hall evidence covers this operating point")
        t = TBD("thrust_N", "OUT_OF_DOMAIN: no Hall evidence point covers this anode flow / power / voltage")
        return BranchResult(thrust_vector_N=t, thrust_axial_N=t, Isp_s=TBD("Isp_s", "out of domain"),
                            plume_divergence_deg=TBD("plume_divergence_deg", "out of domain"),
                            status=Status.OUT_OF_DOMAIN, evidence_class="assumed",
                            applicability_domain="no matching Hall evidence point",
                            validation_status="NO_EVIDENCE", score_bearing=False,
                            provenance={"source": POINT_EVIDENCE, "query": q}, **common)
    if len(match) > 1:
        raise HallEvidenceError(f"ambiguous Hall evidence: {len(match)} points cover this query "
                                f"({[p.point_id for p in match]}); domains must not overlap")
    p = match[0]
    analog = p.hardware.startswith("analog:")
    admitted = (not analog) and _admitted(p, admission_file, root)
    if score_bearing and not admitted:
        raise HallEvidenceError(f"Hall point {p.point_id} ({p.hardware}) is not admitted Vyovrinda evidence; "
                                "it cannot be score-bearing" + (" (analog hardware never is)" if analog else ""))
    T = value_of(p.thrust_N, "thrust_N", "N")
    from .constants import G0
    return BranchResult(
        thrust_vector_N=tuple(T * a for a in axis), thrust_axial_N=T * axis[0],
        Isp_s=T / ((feed.mdot_total_kg_s + cathode_xe_kg_s) * G0),
        plume_divergence_deg=getattr(p.plume_divergence_deg, "value", p.plume_divergence_deg),
        status=Status.PASS, evidence_class=p.thrust_N.quantity_type,
        applicability_domain=f"point {p.point_id} domain {p.domain} ({p.hardware})",
        validation_status=("ADMITTED_VYOVRINDA_EVIDENCE" if admitted else
                           ("ANALOG_NOT_SCORE_BEARING" if analog else "VYOVRINDA_NOT_ADMITTED")),
        score_bearing=bool(score_bearing and admitted),
        provenance={"source": POINT_EVIDENCE, "point_id": p.point_id, "hardware": p.hardware,
                    "evidence_sha256": p.canonical_sha256(), "evidence_source": p.source,
                    "isp_basis": "anode + cathode flow"},
        limitations=("point evidence only; no interpolation or scaling between points",
                     "analog hardware is not Vyovrinda hardware" if analog else "measured Vyovrinda point"),
        **common)
