"""Parallel RF || Hall system evaluator (v2).

One operating point:  propellant routing -> RF branch -> Hall branch -> vector thrust combination -> common power
ledger (bus_power_boundary_v2) -> propellant ledger -> thermal/life bookkeeping -> closure metrics.

Rules
* Status categories are collected, never converted: each stage's status is kept in ``statuses`` and
  ``failure_reasons``; ``status`` is the first non-PASS category in pipeline order.
* Collinear thrusters: T_axial = T_RF + T_H (x-components); vectors are kept so mounting angles can change later
  without changing the contract.
* Verdict: FEASIBLE only when the point passes AND every active branch is score-bearing (admitted evidence).
  A passing point on non-admitted evidence (reduced RF model, analog Hall point) is UNRESOLVED - v2 never declares
  an architecture viable from unvalidated evidence. OUT_OF_DOMAIN and INCOMPLETE_EVIDENCE stay what they are.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import bus_power_v2, hall_branch_adapter, rf_branch
from .parallel_contracts import (ContractError, FeasibilityVerdict, FeedState, InfeasibleError, Quantity, Status,
                                 SystemConstraints, TBD, real)
from .propellant_router import FlowRequest, XeSupply, route
from .propulsion_modes import InstalledArchitecture


@dataclass(frozen=True)
class RFCommand:
    P_dc_W: float
    config: rf_branch.RFBranchConfig
    source: str = rf_branch.REDUCED_RF_MODEL          # REDUCED_RF_MODEL | ADMITTED_RF_MAP
    rf_map: object = None


@dataclass(frozen=True)
class HallCommand:
    P_discharge_W: float
    V_d_V: float
    config: hall_branch_adapter.HallBranchConfig
    source: str
    points: tuple = ()
    member_id: str | None = None
    admission_file: str | None = None
    root: str | None = None


@dataclass(frozen=True)
class CommonState:
    """Common-component loads and efficiencies (bus_power_v2 load planes). Values: Quantity, number or TBD."""
    loads: dict
    efficiencies: dict


def _branch_ledger_entries(br, comps):
    loads, effs = {}, {}
    for c in comps:
        e = br.P_loads.get(c)
        if e is None:
            loads[c] = TBD(f"{c} load", "branch did not report it")
            effs[c] = TBD(f"{c} efficiency", "branch did not report it")
            continue
        loads[c] = e["P_load_W"]
        eff = e["efficiency"]
        effs[c] = eff["value"] if isinstance(eff, dict) and "value" in eff else eff
    return loads, effs


def evaluate(architecture: InstalledArchitecture, mode, *, atm_feed: FeedState | None, xe_supply: XeSupply | None,
             request: FlowRequest, rf: RFCommand | None, hall: HallCommand | None, common: CommonState,
             constraints: SystemConstraints, required_thrust_N: float, score_bearing: bool = False) -> dict:
    spec = architecture.check_mode(mode)
    req_T = real(required_thrust_N, "required_thrust_N")
    if req_T < 0:
        raise ContractError("required_thrust_N must be >= 0")
    out = {"architecture": architecture.kind.value, "mode": spec.mode.value, "statuses": [], "failure_reasons": []}

    def fail(status: Status, why: str):
        out["statuses"].append(status.value)
        out["failure_reasons"].append({"status": status.value, "reason": why})

    # 1. routing
    try:
        rr = route(atm_feed, xe_supply, spec.mode, request, architecture)
    except InfeasibleError as exc:
        fail(exc.status, str(exc))
        out.update(status=exc.status.value, mode_feasible=False, verdict=FeasibilityVerdict.INFEASIBLE.value)
        return out
    out["routing"] = rr.to_dict()
    out["mass_balance_residual_kg_s"] = {"atm": rr.atm_balance_residual_kg_s, "xe": rr.xe_balance_residual_kg_s}

    # 2. branches
    branches = {}
    if spec.rf_enabled:
        if rf is None:
            raise ContractError(f"mode {spec.mode.value} needs an RFCommand")
        branches["rf"] = rf_branch.evaluate(rr.rf_feed, spec.mode, rf.P_dc_W, rf.config, source=rf.source,
                                            rf_map=rf.rf_map, score_bearing=score_bearing)
    elif rf is not None and rf.P_dc_W != 0.0:
        raise ContractError(f"mode {spec.mode.value} does not run RF but an RF power command was given")
    if spec.hall_enabled:
        if hall is None:
            raise ContractError(f"mode {spec.mode.value} needs a HallCommand")
        branches["hall"] = hall_branch_adapter.evaluate(
            rr.hall_feed, spec.mode, rr.cathode_xe_kg_s, hall.P_discharge_W, hall.V_d_V, hall.config,
            source=hall.source, points=hall.points, member_id=hall.member_id, score_bearing=score_bearing,
            admission_file=hall.admission_file, root=hall.root)
    elif hall is not None and hall.P_discharge_W != 0.0:
        raise ContractError(f"mode {spec.mode.value} does not run Hall but a Hall power command was given")
    for b, br in branches.items():
        out[f"{b}_branch"] = br.to_dict()
        if br.status is not Status.PASS:
            fail(br.status, f"{b} branch: {br.status.value}")

    # 3. thrust combination
    vecs = [br.thrust_vector_N for br in branches.values()]
    if any(isinstance(v, TBD) for v in vecs):
        T_vec = TBD("T_total_vector_N", "an active branch has no thrust result")
        T_ax = TBD("T_total_axial_N", "an active branch has no thrust result")
    else:
        T_vec = tuple(math.fsum(v[i] for v in vecs) for i in range(3)) if vecs else (0.0, 0.0, 0.0)
        T_ax = T_vec[0]

    def thrust_of(b):
        return branches[b].thrust_axial_N if b in branches else 0.0

    # 4. power ledger (common + branch loads; disabled-branch components exactly 0 W / efficiency 1)
    loads, effs = dict(common.loads), dict(common.efficiencies)
    for grp, comps in (("rf", bus_power_v2.RF), ("hall", bus_power_v2.HALL)):
        present = architecture.has_rf if grp == "rf" else architecture.has_hall
        if not present:
            continue
        if grp in branches:
            l, e = _branch_ledger_entries(branches[grp], comps)
        else:
            l, e = {c: 0.0 for c in comps}, {c: 1.0 for c in comps}
        loads.update(l)
        effs.update(e)
    led = bus_power_v2.ledger(architecture, spec.mode, loads, effs)
    for b, br in branches.items():                       # a branch's own P_bus must equal its ledger group
        g = led["group_P_bus_W"].get(b)
        if g is not None and not isinstance(br.P_bus_W, TBD) and abs(br.P_bus_W - g) > 1e-6 * max(g, 1.0):
            fail(Status.MODEL_ERROR, f"{b} branch reports P_bus {br.P_bus_W:.6g} W but its load planes give "
                                     f"{g:.6g} W (inconsistent branch power evidence)")
    out["power_ledger"] = led
    out["power_balance_residual_W"] = led["residual_W"]
    if led["status"] == Status.INCOMPLETE_EVIDENCE.value:
        fail(Status.INCOMPLETE_EVIDENCE, f"power ledger incomplete: {led['missing_evidence']}")
    P_tot = led["P_bus_W"]
    if P_tot is not None and not constraints.power_hard_ok(P_tot):
        fail(Status.INFEASIBLE_POWER, f"P_bus {P_tot:.4g} W violates the RFP limit "
                                      f"{constraints.power_hard_max_W.value:g} W (strict)")

    # 5. propellant totals, heat
    mdot_atm = math.fsum(br.mdot_atm_kg_s for br in branches.values())
    mdot_xe = math.fsum(br.mdot_xe_kg_s + br.mdot_cathode_xe_kg_s for br in branches.values())
    heat = {f"{b}:{k}": v for b, br in branches.items() for k, v in br.heat_loads_W.items()}

    # 6. status, feasibility, verdict
    status = out["statuses"][0] if out["statuses"] else Status.PASS.value
    thrust_ok = (not isinstance(T_ax, TBD)) and T_ax >= req_T
    if not isinstance(T_ax, TBD) and T_ax > constraints.thrust_max_N.value:
        out["flags"] = [f"T_axial {T_ax:.4g} N above the RFP range maximum {constraints.thrust_max_N.value:g} N "
                        "(meaning of the 12-25 mN range is owner decision OD1; flagged, not failed)"]
    if not isinstance(T_ax, TBD) and not thrust_ok:
        out["failure_reasons"].append({"status": "THRUST_BELOW_REQUIREMENT",
                                       "reason": f"T_axial {T_ax:.4g} N < required {req_T:.4g} N"})
    feasible = status == Status.PASS.value and thrust_ok
    all_sb = bool(branches) and all(br.score_bearing for br in branches.values())
    if status in (Status.OUT_OF_DOMAIN.value,):
        verdict = FeasibilityVerdict.OUT_OF_DOMAIN
    elif status == Status.INCOMPLETE_EVIDENCE.value:
        verdict = FeasibilityVerdict.INCOMPLETE_EVIDENCE
    elif status.startswith("INFEASIBLE") or (status == Status.PASS.value and not thrust_ok and all_sb):
        verdict = FeasibilityVerdict.INFEASIBLE
    elif feasible and all_sb:
        verdict = FeasibilityVerdict.FEASIBLE
    else:
        verdict = FeasibilityVerdict.UNRESOLVED          # non-admitted evidence or model failure: not decidable
    P_rf = led["group_P_bus_W"].get("rf")
    P_h = led["group_P_bus_W"].get("hall")
    P_common = None if any(led["group_P_bus_W"].get(g) is None for g in ("common_feed", "common_controls_thermal")) \
        else led["group_P_bus_W"]["common_feed"] + led["group_P_bus_W"]["common_controls_thermal"]
    out.update(
        status=status, mode_feasible=feasible, verdict=verdict.value, score_bearing=all_sb,
        T_RF_N=thrust_of("rf"), T_H_N=thrust_of("hall"), T_total_vector_N=T_vec, T_total_axial_N=T_ax,
        P_RF_bus_W=P_rf, P_H_bus_W=P_h, P_common_bus_W=P_common, P_total_bus_W=P_tot,
        mdot_atm_total_kg_s=mdot_atm, mdot_xe_total_kg_s=mdot_xe,
        T_per_Pbus_N_W=(T_ax / P_tot) if (P_tot and not isinstance(T_ax, TBD)) else None,
        heat_loads_W=heat, active_components=[c["component"] for c in led["items"]
                                              if c["active"] and c["P_load_W"] not in (0.0,)],
    )
    return out
