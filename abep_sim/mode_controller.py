"""Mode feasibility controller (parallel RF || Hall investigation, v2).

Given the required thrust, the available atmospheric feed, available bus power, Xe supply, thermal limits and
component availability, and a set of CANDIDATE operating commands supplied by the caller (the controller never
invents powers or flows), it returns:

* feasible candidates with their metrics (thrust, P_bus, T/P_bus, Xe rate, atmospheric consumption, heat, active
  components as the life-consumption proxy),
* infeasible candidates with their reasons (status categories kept),
* the Pareto (non-dominated) set over (P_bus min, Xe rate min, heat min, thrust max). Heat is the KNOWN lower bound;
  ``heat_complete`` says whether any branch heat is TBD (Hall point evidence carries no heat).

It never selects a mode and never ranks architectures with weights. A selection is made only by an owner
PREREGISTERED policy (``PreregisteredPolicy``: a sha-pinned owner decision file), which this module does not
provide. ``proposed_topology`` exposes the spec sec. 25 topology as PROPOSED_POLICY_NOT_ARCHITECTURE_DECISION: it
orders the questions and eliminates nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

from . import parallel_system
from .parallel_contracts import ContractError, Status, SystemConstraints, TBD, real
from .propellant_router import FlowRequest
from .propulsion_modes import InstalledArchitecture, Mode

TOPOLOGY_STATUS = "PROPOSED_POLICY_NOT_ARCHITECTURE_DECISION"


@dataclass(frozen=True)
class Candidate:
    label: str
    mode: Mode
    request: FlowRequest
    rf: object = None          # parallel_system.RFCommand | None
    hall: object = None        # parallel_system.HallCommand | None


@dataclass(frozen=True)
class PreregisteredPolicy:
    """An owner-approved, preregistered selection rule. ``decision_file`` must contain decided_by 'owner' and
    'preregistered_mode_policy_sha256' equal to the sha256 of ``rule_file``; ``choose`` is the implementation of
    that rule (supplied with the decision, never invented here)."""
    decision_file: str
    rule_file: str
    choose: object

    def verify(self, root: str = ".") -> None:
        rule_sha = hashlib.sha256(open(os.path.join(root, self.rule_file), "rb").read()).hexdigest()
        dec = json.load(open(os.path.join(root, self.decision_file)))
        if dec.get("decided_by") != "owner" or dec.get("preregistered_mode_policy_sha256") != rule_sha:
            raise ContractError("mode policy is not an owner-preregistered rule (decision file / rule sha mismatch)")


def _dominates(a: dict, b: dict) -> bool:
    ka = (a["P_total_bus_W"], a["mdot_xe_total_kg_s"], a["heat_total_W"], -a["T_total_axial_N"])
    kb = (b["P_total_bus_W"], b["mdot_xe_total_kg_s"], b["heat_total_W"], -b["T_total_axial_N"])
    return all(x <= y for x, y in zip(ka, kb)) and any(x < y for x, y in zip(ka, kb))


def evaluate_candidates(architecture: InstalledArchitecture, candidates, *, required_thrust_N: float,
                        atm_feed, xe_supply, common, constraints: SystemConstraints, available_bus_W: float,
                        branch_available: dict, thermal_limits_W: dict | None = None,
                        policy: PreregisteredPolicy | None = None, root: str = ".") -> dict:
    avail = real(available_bus_W, "available_bus_W")
    if set(branch_available) != {"rf", "hall"}:
        raise ContractError("branch_available must state availability for both 'rf' and 'hall' explicitly")
    feasible, infeasible = [], []
    for c in candidates:
        spec = architecture.check_mode(c.mode)
        reasons = [f"{b} branch unavailable" for b, on in (("rf", spec.rf_enabled), ("hall", spec.hall_enabled))
                   if on and not branch_available[b]]
        if reasons:
            infeasible.append({"label": c.label, "mode": spec.mode.value, "status": "COMPONENT_UNAVAILABLE",
                               "reasons": reasons})
            continue
        o = parallel_system.evaluate(architecture, c.mode, atm_feed=atm_feed, xe_supply=xe_supply, request=c.request,
                                     rf=c.rf, hall=c.hall, common=common, constraints=constraints,
                                     required_thrust_N=required_thrust_N)
        reasons = [r["reason"] for r in o.get("failure_reasons", [])]
        statuses = list(o.get("statuses", []))
        P = o.get("P_total_bus_W")
        if P is not None and P > avail:
            statuses.append(Status.INFEASIBLE_POWER.value)
            reasons.append(f"P_bus {P:.4g} W > available {avail:.4g} W")
        heat = o.get("heat_loads_W", {})
        heat_tot = sum(v for v in heat.values() if isinstance(v, (int, float))) if heat else 0.0
        heat_complete = not any(isinstance(v, TBD) for v in heat.values())
        if thermal_limits_W:
            for key, lim in thermal_limits_W.items():
                if key not in heat:
                    active = [b for b in ("rf", "hall") if (b == "rf" and spec.rf_enabled) or (b == "hall" and spec.hall_enabled)]
                    if key.split(":")[0] in active:
                        raise ContractError(f"thermal limit on unknown heat key {key!r}; known keys {sorted(heat)}")
                    continue
                v = heat[key]
                if isinstance(v, TBD):
                    statuses.append(Status.INCOMPLETE_EVIDENCE.value)
                    reasons.append(f"heat {key} is TBD; its thermal limit cannot be checked")
                elif v > lim:
                    statuses.append(Status.INFEASIBLE_THERMAL.value)
                    reasons.append(f"heat {key} {v:.4g} W > limit {lim:.4g} W")
        rec = {"label": c.label, "mode": o["mode"], "status": statuses[0] if statuses else o.get("status"),
               "statuses": statuses, "verdict": o.get("verdict"), "reasons": reasons}
        if o.get("mode_feasible") and not statuses:
            T = o["T_total_axial_N"]
            rec.update(T_total_axial_N=T, P_total_bus_W=P, T_per_Pbus_N_W=o["T_per_Pbus_N_W"],
                       mdot_xe_total_kg_s=o["mdot_xe_total_kg_s"], mdot_atm_total_kg_s=o["mdot_atm_total_kg_s"],
                       heat_total_W=heat_tot, heat_complete=heat_complete, active_components=o["active_components"],
                       score_bearing=o["score_bearing"])
            feasible.append(rec)
        else:
            infeasible.append(rec)
    pareto = [a["label"] for a in feasible if not any(_dominates(b, a) for b in feasible if b is not a)]
    selection = None
    if policy is not None:
        policy.verify(root)
        selection = policy.choose(feasible)
    return {"required_thrust_N": required_thrust_N, "available_bus_W": avail, "feasible": feasible,
            "infeasible": infeasible, "pareto_labels": pareto, "selection": selection,
            "selection_rule": "owner preregistered policy" if policy else "NONE (no automatic selection)",
            "note": "feasible means the evaluated point passes; the verdict field says whether the evidence is "
                    "admitted (FEASIBLE) or not (UNRESOLVED)."}


def proposed_topology(result: dict) -> dict:
    """Spec sec. 25 decision topology applied to a candidate evaluation, as a report. Eliminates nothing."""
    modes = {r["mode"] for r in result["feasible"]}
    rf_alone = Mode.RF_ATM.value in modes
    boost = Mode.RF_ATM_HALL_XE.value in modes
    return {"status": TOPOLOGY_STATUS,
            "q1_rf_atm_satisfies_required_thrust": rf_alone,
            "q2_rf_atm_plus_hall_xe_satisfies": None if rf_alone else boost,
            "q3_other_permitted_modes_feasible": sorted(modes - {Mode.RF_ATM.value, Mode.RF_ATM_HALL_XE.value}),
            "candidate_class": ("RF_ATM feasible candidate" if rf_alone else
                                ("boost candidate" if boost else "evaluate other explicitly permitted modes")),
            "note": "does not eliminate Hall or RF; not an architecture decision"}
