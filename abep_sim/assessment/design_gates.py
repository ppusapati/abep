"""Design-gate ASSESSMENT layer (A9.22 layer separation, owner directive of 2026-10-03; decisions G1-G9).

Requirement / compliance assessment that used to live inside the design package (abep_sim/design/) is defined here.
Design / physics code produces physical and design quantities; this module compares them with requirement-derived
limits, carries the RVM / RFP clause labels, and reads requirement / owner-question state (RVM, owner-question state
v5). Behaviour is identical to the pre-A9.22 design-layer code: every function below is a verbatim move (the HARD
CONSTRAINT limits now come from the engineering-constraints seam abep_sim/design/engineering_constraints.py with the
same values). The old locations keep deprecated import shims so existing builders keep working.

Moved here (old location -> this module):
  * abep_sim/design/architecture_optimizer.py: HARD_CONSTRAINTS, PRE_EVALUATED_OBJECTIVES, evaluate_constraints (+ its
    helpers _from_u13 / _cmp), the rank_full_system hard-constraint exclusion (``hard_constraint_partition``,
    ``constraint_met_value_kinds``) and the A9-02 RFP power-gate call (``bus_power_gate``);
  * abep_sim/design/upstream_a9_13.py: ripple_feed_quality (HC-12), statewise_drag_compensation (AG-13 / HC-08),
    feed_state_sufficiency (AG-12 / HC-11), pareto_s6_17 (S6.17 system comparison), propellant_paths_check (HC-10,
    RFP-P18-08 structural refusal);
  * abep_sim/design/robust_optimizer.py gate_snapshot: the RVM read (``rvm_gate_snapshot``; ``gate_snapshot`` passes
    it into robust_optimizer.design_gate_snapshot);
  * abep_sim/design/owner_state.py: the owner-question state v5 reader (owner_state, status_label,
    apply_to_questions). Builders pass the resulting question-status text into their records; design code never reads
    docs state.
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .. import bus_boundary_a9_v2 as bb
from ..configuration import load_gate_thresholds
from ..design import a9_19_architecture as a919
from ..design import architecture_optimizer as ao
from ..design import engineering_constraints as ec
from ..design.architecture_optimizer import (C_MET, C_MET_PARAMETRIC, C_NOT_EVALUATED, C_VIOLATED,
                                             C_VIOLATED_PARAMETRIC, EVALUATED, PARAMETRIC_ONLY, SYNTHETIC_ONLY)
from ..design import upstream_a9_13 as u13
from ..design.upstream_a9_13 import (FEED_STATE_FIELDS, H1_MAP_VALIDATED, HARD_CONSTRAINTS_FIRST,
                                     PARETO_OBJECTIVES_S6_17, PROPELLANT_POLICY, RFP_CLAUSES, SYNTHETIC, VALUE_REFERENCE,
                                     VALUE_SYNTHETIC, VALUE_TBD, A913RuleError, H1Tolerance, _dominates, _finite,
                                     _rec_value, cite, combine_value_status, constraint_status,
                                     refuse_fixed_mass_flow_gate, statewise_envelope)

REPO = Path(__file__).resolve().parents[2]




# ================================================================================================= F7 hard constraints
# (moved from abep_sim/design/architecture_optimizer.py). Limits: HC-01..HC-04 from the engineering-constraints seam
# (abep_sim/design/engineering_constraints.py REQUIREMENT_LIMITS); HC-05..HC-12 from the assessment-layer threshold
# artefact config/assessment/gate_thresholds_v1.json (A9.24 item 5, owner decision 2026-10-04): HC-05 M_n,LB > 0,
# HC-06 50 K protection margin against hardware-bound limits (never in thermal equations), HC-07 15,000 h firing-life
# basis (mission 26,280 h separate), HC-08 T - D >= 0, HC-10 capability evidence, HC-11 feed_available - feed_required
# >= 0, HC-12 TBD -> NOT_EVALUATED (no default). HC-09 stays the design-generation filter (engineering constraints,
# A9.22 G2 Option 1) and is reported here as well. Values identical to the former design-module literals.
GATE_THRESHOLDS = load_gate_thresholds()
HARD_CONSTRAINT_LIMITS = {**ec.REQUIREMENT_LIMITS, **GATE_THRESHOLDS["limits"]}


HARD_CONSTRAINTS = (
    {"id": "HC-01", "rvm": "RVM-02", "rfp": "RFP-P18-06", "quantity": "T (sustained, atmospheric propellant)",
     "comparator": ">=", "limit": HARD_CONSTRAINT_LIMITS["HC-01"], "units": "N", "objective": "thrust_N", "category": "rfp_recorded"},
    {"id": "HC-02", "rvm": "RVM-03", "rfp": "RFP-P18-06; RFP-P18-10",
     "quantity": "demonstrated thrust capability at P_bus < 1500 W", "comparator": ">=",
     "limit": HARD_CONSTRAINT_LIMITS["HC-02"], "units": "N", "objective": "thrust_capability_N", "category": "rfp_recorded"},
    {"id": "HC-03", "rvm": "RVM-04", "rfp": "RFP-P18-10", "quantity": "P_bus,1ms,max (steady and start-up, A9-02 gate)",
     "comparator": "<", "limit": HARD_CONSTRAINT_LIMITS["HC-03"], "units": "W", "objective": "P_bus_W", "category": "rfp_recorded"},
    {"id": "HC-04", "rvm": "RVM-06", "rfp": "RFP-P18-11", "quantity": "wet propulsion-system mass", "comparator": "<",
     "limit": HARD_CONSTRAINT_LIMITS["HC-04"], "units": "kg", "objective": "m_wet_kg", "category": "rfp_recorded"},
    {"id": "HC-05", "rvm": "RVM-15",
     "quantity": "M_n,LB: lower uncertainty bound of M_n = I_e,cap / I_d,max,H1 - 1 (A9.24 item 5; the point "
                 "difference I_e,cap - I_d,max is never the acceptance criterion; no lower bound -> NOT_EVALUATED)",
     "comparator": ">", "limit": HARD_CONSTRAINT_LIMITS["HC-05"], "units": "-", "objective": "M_n_LB",
     "category": "derived_from_owner_decision"},
    {"id": "HC-06", "rvm": "RVM-17", "quantity": "thermal margin below validated limits", "comparator": ">=",
     "limit": HARD_CONSTRAINT_LIMITS["HC-06"], "units": "K", "objective": "thermal_margin_K", "category": "derived_project"},
    {"id": "HC-07", "rvm": "RVM-12", "rfp": "RFP-P19-01", "quantity": "cumulative firing time capability",
     "comparator": ">", "limit": HARD_CONSTRAINT_LIMITS["HC-07"], "units": "h", "objective": "firing_life_h", "category": "rfp_recorded"},
    {"id": "HC-08", "rvm": "AG-13 (owner decision A9.13 S6.15 / OQ-F78-01; A9.14 S9.7 statewise quantifier)",
     "rfp": "RFP-P18-04; RFP-P18-06",
     "quantity": "T_available(state) - D_spacecraft(state) at EVERY required state (statewise; worst state governs; "
                 "the orbit average never hides a deficit)", "comparator": ">=", "limit": HARD_CONSTRAINT_LIMITS["HC-08"], "units": "N",
     "objective": "statewise_T_minus_D", "category": "owner_decision_hard_statewise", "statewise": True},
    {"id": "HC-09", "rvm": "F1 C-DRAG-RFP (RFP thrust max as recorded, F1-P-11)",
     "quantity": "intake-face drag at every orbit state", "comparator": "<=", "limit": HARD_CONSTRAINT_LIMITS["HC-09"], "units": "N",
     "objective": "drag_intake_max_N", "category": "upstream (evaluable now; necessary, not sufficient)"},
    {"id": "HC-10", "rvm": "A9.15 RFP-compliant propellant policy", "rfp": "RFP-P18-08; RFP-P17-05",
     "quantity": "ambient-air AND Xe operating capability with two separate propellant tanks / paths "
                 "(1 = both demonstrated)", "comparator": ">=", "limit": HARD_CONSTRAINT_LIMITS["HC-10"], "units": "-",
     "objective": "propellant_capability", "category": "rfp_recorded"},
    {"id": "HC-11", "rvm": "AG-12 (owner decision A9.13 S6.21 / F9-OQ-02)", "rfp": "RFP-P18-06; RFP-P18-05",
     "quantity": "statewise feed-state sufficiency (mdot, P, T, composition, ripple) vs the requirement derived from "
                 "the required thrust and a VALIDATED H-1 map (no fixed mg/s gate)", "comparator": ">=", "limit": HARD_CONSTRAINT_LIMITS["HC-11"],
     "units": "-", "objective": "feed_state_sufficiency", "category": "owner_decision_hard_statewise",
     "statewise": True},
    {"id": "HC-12", "rvm": "A9.13 S6.17 / S6.12 feed-quality", "rfp": "-",
     "quantity": "compressor / plenum ripple <= measured H-1 ripple tolerance", "comparator": "<=", "limit": HARD_CONSTRAINT_LIMITS["HC-12"],
     "units": "-", "objective": "ripple_feed_quality", "category": "owner_decision_hard_constraint"},
)


PRE_EVALUATED_OBJECTIVES = ("statewise_T_minus_D", "feed_state_sufficiency", "ripple_feed_quality")


def _from_u13(status: str) -> tuple[str, str | None]:
    """Map an upstream_a9_13 constraint status onto this module's (constraint status, value status)."""
    return {u13.C_MET: (C_MET, EVALUATED), u13.C_VIOLATED: (C_VIOLATED, EVALUATED),
            u13.C_MET_SYNTHETIC: (C_MET, SYNTHETIC_ONLY), u13.C_VIOLATED_SYNTHETIC: (C_VIOLATED, SYNTHETIC_ONLY),
            u13.C_MET_PARAMETRIC: (C_MET_PARAMETRIC, PARAMETRIC_ONLY),
            u13.C_VIOLATED_PARAMETRIC: (C_VIOLATED_PARAMETRIC, PARAMETRIC_ONLY)}.get(status, (C_NOT_EVALUATED, None))


def _cmp(v: float, comparator: str, limit: float) -> bool:
    return {">=": v >= limit, ">": v > limit, "<": v < limit, "<=": v <= limit}[comparator]


def evaluate_constraints(values: Mapping) -> list[dict]:
    """Fail-closed hard constraints. ``values``: objective name -> objective record (status + value) or None.
    A constraint is MET_ON_SUPPLIED_VALUES or VIOLATED only on an EVALUATED or SYNTHETIC numeric value (the label
    travels with it; rank_full_system never lets synthetic and evidence meet). On a PARAMETRIC_SENSITIVITY_ONLY value
    (assumed, owner-allocation, code-default or parametric inputs) the comparison is reported as
    MET_ON_PARAMETRIC_VALUES_SENSITIVITY_ONLY_NOT_MET / VIOLATED_ON_PARAMETRIC_VALUES_SENSITIVITY_ONLY and never
    counts as satisfied (A9.7: a TBD is never converted to an assumed value to obtain an optimum). Anything else is
    NOT_EVALUATED. HC-03 uses the A9-02 gate verdict when one is carried (PASS -> met, FAIL -> violated,
    NOT_EVALUABLE -> not evaluated) only on an EVALUATED or SYNTHETIC ledger; on a PARAMETRIC_SENSITIVITY_ONLY ledger the
    verdict maps to the parametric sensitivity statuses, and on any other status to NOT_EVALUATED."""
    out = []
    for c in HARD_CONSTRAINTS:
        rec = values.get(c["objective"])
        st, basis = C_NOT_EVALUATED, "no evaluable value (fail closed: never counted as satisfied)"
        if c["objective"] in PRE_EVALUATED_OBJECTIVES:
            if rec is None:
                basis = ("no statewise record over the required state set (a single value never closes a statewise "
                         "constraint; A9.13 S6.15 / S6.21 / A9.14 S9.7)" if c.get("statewise") else
                         "measured H-1 tolerance / ripple not evaluated (A9.13 S6.17)")
                vst = None
            else:
                st, vst = _from_u13(rec.get("status"))
                basis = f"upstream_a9_13 {c['objective']} status {rec.get('status')}"
                if rec.get("average_hides_violation"):
                    basis += "; orbit average non-negative but a state is below zero (the statewise result governs)"
            out.append({"id": c["id"], "rvm": c["rvm"], "rfp": c.get("rfp"), "quantity": c["quantity"],
                        "rule": c["quantity"], "status": st, "value_status": vst, "basis": basis})
            continue
        if c["id"] == "HC-05" and (rec is None or not rec.get("uncertainty_basis")):
            # A9.24 item 5 (owner correction 2026-10-04): HC-05 is evaluated only on the lower uncertainty bound of
            # M_n = I_e,cap / I_d,max,H1 - 1; without uncertainty evidence it is NOT_EVALUATED (fail closed)
            out.append({"id": c["id"], "rvm": c["rvm"], "rfp": c.get("rfp"), "quantity": c["quantity"],
                        "rule": f"{c['comparator']} {c['limit']:g} {c['units']}", "status": C_NOT_EVALUATED,
                        "value_status": None if rec is None else rec.get("status"),
                        "basis": "no lower uncertainty bound M_n,LB of M_n = I_e,cap / I_d,max,H1 - 1 with its "
                                 "uncertainty basis (fail closed: NOT_EVALUATED; a point difference I_e,cap - "
                                 "I_d,max never closes HC-05)"})
            continue
        if rec is not None and c["id"] == "HC-03" and rec.get("gate_verdict") is not None:
            gv = rec["gate_verdict"]
            vst = rec.get("status")
            if vst in (EVALUATED, SYNTHETIC_ONLY):
                st = {"PASS": C_MET, "FAIL": C_VIOLATED}.get(gv, C_NOT_EVALUATED)
                basis = f"bus_boundary_a9_v2.rfp_power_gate verdict {gv} ({vst})"
            elif vst == PARAMETRIC_ONLY:
                # the gate ignores evidence class: on assumed / parametric loads its verdict is a sensitivity
                # comparison only and never counts as satisfied (fail closed; OPT-04)
                st = {"PASS": C_MET_PARAMETRIC, "FAIL": C_VIOLATED_PARAMETRIC}.get(gv, C_NOT_EVALUATED)
                basis = (f"bus_boundary_a9_v2.rfp_power_gate verdict {gv} on {vst} ledger values: sensitivity "
                         "comparison only, never counted as satisfied (fail closed)")
            else:
                st = C_NOT_EVALUATED
                basis = (f"bus_boundary_a9_v2.rfp_power_gate verdict {gv} but value status {vst}: "
                         "not evaluable (fail closed)")
        elif rec is not None and rec.get("status") in (EVALUATED, PARAMETRIC_ONLY, SYNTHETIC_ONLY) and \
                rec.get("value") is not None and math.isfinite(float(rec["value"])):
            ok = _cmp(rec["value"], c["comparator"], c["limit"])
            if rec["status"] == PARAMETRIC_ONLY:
                st = C_MET_PARAMETRIC if ok else C_VIOLATED_PARAMETRIC
                basis = (f"value {rec['value']:.6g} {c['units']} ({rec['status']}): sensitivity comparison only, "
                         "never counted as satisfied (fail closed)")
            else:
                st = C_MET if ok else C_VIOLATED
                basis = f"value {rec['value']:.6g} {c['units']} ({rec['status']})"
        out.append({"id": c["id"], "rvm": c["rvm"], "rfp": c.get("rfp"), "quantity": c["quantity"],
                    "rule": f"{c['comparator']} {c['limit']:g} {c['units']}", "status": st,
                    "value_status": None if rec is None else rec.get("status"), "basis": basis})
    return out


def hard_constraint_partition(evaluations: Sequence[Mapping]) -> tuple[list, list]:
    """rank_full_system exclusion (moved from architecture_optimizer): (admissible, excluded) lists of (evaluation,
    ids of the hard constraints not MET) - a vector with any constraint not MET on rankable values is excluded."""
    admissible, excluded = [], []
    for ev in evaluations:
        bad = [c["id"] for c in ev["constraints"] if c["status"] != C_MET]
        (excluded if bad else admissible).append((ev, bad))
    return admissible, excluded


def constraint_met_value_kinds(evaluations: Sequence[Mapping]) -> set:
    """Evidence kinds (EVALUATED / SYNTHETIC) of the values hard constraints were MET on (rank_full_system mixing
    check; moved from architecture_optimizer)."""
    kinds = set()
    for ev in evaluations:
        for c in ev["constraints"]:
            if c["status"] == C_MET and c.get("value_status") in (EVALUATED, SYNTHETIC_ONLY):
                kinds.add(c["value_status"])
    return kinds


def bus_power_gate(steady: Mapping, startup) -> dict:
    """A9-02 RFP power gate verdict on supplied ledgers (bus_boundary_a9_v2.rfp_power_gate; HC-03 assessment)."""
    return bb.rfp_power_gate(steady, startup)


# ================================================================================================= A9.13 assessments
# (moved from abep_sim/design/upstream_a9_13.py; vocabulary and helpers stay there)


def ripple_feed_quality(ripple_frac: float | None, ripple_status: str, h1: H1Tolerance | None) -> dict:
    """S6.17: compressor / plenum ripple as a HARD feed-quality constraint against a measured H-1 tolerance (never an
    objective). NOT_EVALUATED while the tolerance is TBD or the ripple is not evaluated."""
    if h1 is not None and h1.quantity != "ripple":
        raise A913RuleError("ripple must be compared with the H-1 ripple tolerance")
    if h1 is None or h1.status == VALUE_TBD or ripple_frac is None or ripple_status == VALUE_TBD:
        return {"constraint": "FEED_QUALITY_RIPPLE", "status": C_NOT_EVALUATED, "ripple_frac": ripple_frac,
                "ripple_status": ripple_status, "tolerance_frac": None if h1 is None else h1.value_frac,
                "reason": "measured H-1 ripple tolerance TBD" if (h1 is None or h1.status == VALUE_TBD)
                else "ripple not evaluated", "role": "HARD_CONSTRAINT_NOT_OBJECTIVE"}
    if not _finite(ripple_frac) or ripple_frac < 0:
        return {"constraint": "FEED_QUALITY_RIPPLE", "status": C_NOT_EVALUATED, "ripple_frac": None,
                "reason": "ripple not finite", "role": "HARD_CONSTRAINT_NOT_OBJECTIVE"}
    vs = combine_value_status([ripple_status, h1.status])
    ok = ripple_frac <= h1.value_frac
    return {"constraint": "FEED_QUALITY_RIPPLE", "status": constraint_status(ok, vs), "ripple_frac": float(ripple_frac),
            "tolerance_frac": h1.value_frac, "value_status": vs, "role": "HARD_CONSTRAINT_NOT_OBJECTIVE"}


def statewise_drag_compensation(states: Sequence[Mapping], thrust_fn: Callable[[Mapping], Mapping],
                                drag_fn: Callable[[Mapping], Mapping], hall_admitted: bool) -> dict:
    """AG-13 / HC-08 (A9.13 S6.15): T_available(state) - D_spacecraft(state) >= 0 at EVERY required state, thrust and
    drag evaluated at the same state.

    ``thrust_fn(state)`` / ``drag_fn(state)`` return {value_N, status, source, state_id}. Thrust from a Hall
    prediction counts only with an admitted Hall transport member (``hall_admitted``); otherwise every thrust record
    except a synthetic test record is refused and the constraint is NOT_EVALUATED. A REFERENCE_PARAMETRIC drag (S6.18)
    never closes AG-13: its statewise margins are reported as a reference indication only."""
    states = list(states)
    if not states:
        raise A913RuleError("AG-13 needs the required state set (an empty set satisfies nothing)")
    recs, statuses, refused = {}, [], []
    for st in states:
        sid = st.get("state_id")
        t, d = thrust_fn(st), drag_fn(st)
        for nm, r in (("thrust", t), ("drag", d)):
            if r.get("state_id") != sid:
                raise A913RuleError(f"{nm} record for state {sid!r} was evaluated at {r.get('state_id')!r}: thrust and "
                                    "drag must be paired at the same state (S6.15)")
        tv, ts = _rec_value(t, "thrust")
        dv, ds = _rec_value(d, "drag")
        if ts not in (VALUE_SYNTHETIC, VALUE_TBD) and not hall_admitted:
            refused.append(sid)
            ts = VALUE_TBD
        recs[sid] = (tv, ts, dv, ds)
        statuses += [ts, ds]
    vs = combine_value_status(statuses)
    out = {"constraint": "HC-08 / AG-13", "rule": "T_available(state) - D_spacecraft(state) >= 0 at every required "
           "state (statewise hard constraint)", "rfp_clauses": [RFP_CLAUSES["altitude"], RFP_CLAUSES["thrust"]],
           "authority": cite("A9.13", "A9.14"), "value_status": vs, "n_required_states": len(states),
           "thrust_refused_no_admitted_hall_member": refused}
    if vs == VALUE_TBD:
        out.update({"status": C_NOT_EVALUATED, "statewise": None,
                    "reason": "thrust and / or spacecraft drag not evaluated at every required state (no admitted "
                              "Hall member / host-spacecraft ICD); NOT_EVALUATED, never counted as satisfied"})
        return out
    q = statewise_envelope("AG-13", states, lambda s: recs[s["state_id"]][0] - recs[s["state_id"]][2], vs)
    out.update({"status": q["status"], "statewise": q["per_state"], "worst_state": q["worst_state"],
                "orbit_average_margin_N": q["orbit_average_margin"],
                "average_hides_violation": q["average_hides_violation"]})
    if vs == VALUE_REFERENCE:
        out["note"] = ("reference spacecraft drag (REFERENCE/PARAMETRIC, S6.18): an indication only; AG-13 closure needs "
                       "the host-spacecraft ICD")
    return out


def feed_state_sufficiency(states: Sequence[Mapping], offered_fn: Callable[[Mapping], Mapping],
                           required_thrust_fn: Callable[[Mapping], Mapping] | None, h1_map=None,
                           fixed_mass_flow_gate=None) -> dict:
    """AG-12 (A9.13 S6.21) statewise feed-state sufficiency.

    Per required state: required thrust (from the registered spacecraft drag basis, ``required_thrust_fn``) -> the
    minimum feed state from a VALIDATED H-1 map for the actual composition (``h1_map.min_feed_state(state, thrust_N,
    offered)`` returning {mdot_kgps, P_Pa, T_range_K, x_domain_ok, ripple_tolerance_frac} or None outside its domain)
    -> the offered feed state (``offered_fn``: {mdot_kgps, P_Pa, T_K, x_mole, ripple_frac, status}) must meet it in
    every field. NOT_EVALUATED until a validated H-1 map exists (a synthetic map is labelled synthetic)."""
    refuse_fixed_mass_flow_gate(fixed_mass_flow_gate)
    base = {"gate": "AG-12", "rule": "statewise feed-state sufficiency (mass flow, pressure, temperature, composition, "
            "ripple quality) against the requirement derived from the required thrust and a validated H-1 map",
            "fixed_mass_flow_gate": "REMOVED (0.38-3.2 mg/s = characterization coverage only)",
            "rfp_clauses": [RFP_CLAUSES["thrust"], RFP_CLAUSES["altitude"], RFP_CLAUSES["intake_sizing"]],
            "authority": cite("A9.13", "A9.14")}
    map_status = None if h1_map is None else getattr(h1_map, "status", None)
    if h1_map is None or map_status not in (H1_MAP_VALIDATED, SYNTHETIC):
        base.update({"status": C_NOT_EVALUATED, "h1_map_status": map_status or "NONE",
                     "reason": "no validated H-1 thrust-versus-feed map exists (AG-12 NOT_EVALUATED until it does)"})
        return base
    if required_thrust_fn is None:
        base.update({"status": C_NOT_EVALUATED, "h1_map_status": map_status,
                     "reason": "required drag-compensation thrust per state not supplied (registered drag basis)"})
        return base
    rows, statuses = {}, []
    for st in states:
        sid = st.get("state_id")
        off = offered_fn(st)
        missing = [k for k in FEED_STATE_FIELDS if off.get(k) is None]
        tr = required_thrust_fn(st)
        if tr.get("state_id") != sid:
            raise A913RuleError("required thrust must be evaluated at the same state")
        tv, ts = _rec_value(tr, "required thrust")
        os_ = off.get("status", VALUE_TBD)
        statuses += [ts, os_]
        if missing or ts == VALUE_TBD or os_ == VALUE_TBD:
            rows[sid] = {"margin": float("nan"), "missing": missing}
            continue
        req = h1_map.min_feed_state(st, tv, off)
        if req is None:
            rows[sid] = {"margin": -1.0, "reason": "offered feed / required thrust outside the H-1 map domain"}
            continue
        m = [off["mdot_kgps"] / req["mdot_kgps"] - 1.0, off["P_Pa"] / req["P_Pa"] - 1.0]
        tlo, thi = req["T_range_K"]
        m.append(0.0 if tlo <= off["T_K"] <= thi else -1.0)
        m.append(0.0 if req["x_domain_ok"] else -1.0)
        m.append(req["ripple_tolerance_frac"] / max(off["ripple_frac"], 1e-300) - 1.0 if off["ripple_frac"] > 0 else 0.0)
        rows[sid] = {"margin": min(m), "field_margins": dict(zip(("mdot", "P", "T", "composition", "ripple"), m)),
                     "required": req}
    vs = combine_value_status(statuses + ([VALUE_SYNTHETIC] if map_status == SYNTHETIC else []))
    if any(not math.isfinite(r["margin"]) for r in rows.values()):
        base.update({"status": C_NOT_EVALUATED, "h1_map_status": map_status, "per_state": rows,
                     "reason": "feed-state record or required thrust not evaluated at every state"})
        return base
    q = statewise_envelope("AG-12", list(states), lambda s: rows[s["state_id"]]["margin"], vs)
    base.update({"status": q["status"], "h1_map_status": map_status, "value_status": vs, "per_state": q["per_state"],
                 "field_margins": {k: v.get("field_margins") for k, v in rows.items()},
                 "worst_state": q["worst_state"], "average_hides_violation": q["average_hides_violation"]})
    return base


def pareto_s6_17(rows: Sequence[Mapping], objectives=PARETO_OBJECTIVES_S6_17, weights=None) -> dict:
    """S6.17 system comparison: hard constraints first (a row with any VIOLATED constraint is excluded; NOT_EVALUATED
    constraints make the set CONDITIONAL), then a Pareto filter over the declared objectives. No weighted scalar:
    passing ``weights`` is refused. A row whose objective is missing / non-finite never enters dominance."""
    if weights is not None:
        raise A913RuleError("A9.13 S6.17: no arbitrary weighted scalar score; system comparison is Pareto-based")
    keys = [o[0] for o in objectives]
    senses = [o[1] for o in objectives]
    excluded, cand, conditional, incomplete = [], [], set(), []
    for r in rows:
        cons = r.get("constraints", {})
        viol = sorted(k for k, v in cons.items() if v in (C_VIOLATED,))
        if viol:
            excluded.append({"id": r["id"], "violated": viol})
            continue
        ne = sorted(k for k, v in cons.items() if v != C_MET)
        if ne:
            conditional.update(ne)
        vals = [r.get("objectives", {}).get(k) for k in keys]
        if any(not _finite(v) for v in vals):
            incomplete.append({"id": r["id"], "objectives_not_evaluated":
                               [k for k, v in zip(keys, vals) if not _finite(v)]})
            continue
        cand.append((r["id"], [float(v) for v in vals]))
    members = sorted(i for i, v in cand if not any(_dominates(w, v, senses) for j, w in cand if j != i))
    return {"objectives": [{"key": k, "sense": s, "definition": d} for k, s, d in objectives],
            "hard_constraints_first": list(HARD_CONSTRAINTS_FIRST), "members": members,
            "status": ("CONDITIONAL_ON_NOT_EVALUATED_CONSTRAINTS" if conditional else "CONSTRAINTS_MET_ON_SUPPLIED_VALUES")
            if members else "EMPTY", "conditional_on": sorted(conditional), "excluded_violating": excluded,
            "not_ranked_incomplete_objectives": incomplete, "weighted_scalar": "REFUSED (S6.17)"}


def propellant_paths_check(paths: Mapping[str, Sequence[str]] | None) -> dict:
    """Structural check of a modelled architecture's propellant paths against A9.15 / RFP-P18-08. Refuses a model with
    a single shared tank or a missing path. The CAPABILITY itself (Xe operation, air operation) stays NOT_EVALUATED
    until demonstrated: a declared path is not determining evidence."""
    if paths is None:
        return {"constraint": "HC-10 dual propellant capability", "structure": "NOT_MODELLED",
                "status": C_NOT_EVALUATED, "reason": "the architecture model declares no propellant paths",
                "policy": PROPELLANT_POLICY, "authority": cite("A9.15", "A9.17")}
    air, xe = list(paths.get("air", ())), list(paths.get("xe", ()))
    problems = []
    if not air:
        problems.append("no ambient-air path")
    if not xe:
        problems.append("no Xe path (Xe capability is RFP-required, A9.15)")
    if air and air[0] != "intake":
        problems.append("air path must start at the intake")
    if xe and not xe[0].startswith("xe_tank"):
        problems.append("Xe path must start at a dedicated Xe tank")
    tanks_air = {n for n in air if "tank" in n or "chamber" in n}
    tanks_xe = {n for n in xe if "tank" in n or "chamber" in n}
    if tanks_air & tanks_xe:
        problems.append(f"shared tank(s) {sorted(tanks_air & tanks_xe)}: RFP-P18-08 requires two separate tanks")
    if "filter" in air and not ("intake" in air and "compressor" in air
                                and air.index("intake") < air.index("filter") < air.index("compressor")):
        problems.append("filter must sit between the intake and the compressor (S6.6 / S6.19)")
    if "filter" not in air and air:
        problems.append("air path lacks the filter element (RFP-P16-02 chain; FC-00 is a reference bound only)")
    if any(n == "c1" or n.startswith(("c1_", "hollow_cathode", "cathode_")) for n in xe):
        problems.append("Xe path feeds a hollow-cathode / C1 branch: no hollow cathode in flight (A9.19; C1 ground-only "
                        "A9.20)")
    if problems:
        raise A913RuleError("; ".join(problems))
    roles = a919.propellant_path_roles({"air": air, "xe": xe})
    return {"constraint": "HC-10 dual propellant capability", "structure": "TWO_SEPARATE_PATHS_DECLARED",
            "status": C_NOT_EVALUATED, "reason": "air and Xe operating capability not yet demonstrated (a declared "
            "path is not determining evidence, S6.22)", "air_path": air, "xe_path": xe,
            "supply_modes": {"air": roles["air"]["supply_mode"], "xe": roles["xe"]["supply_mode"]},
            "path_roles": {"air": roles["air"]["role"], "xe": roles["xe"]["role"]},
            "policy": PROPELLANT_POLICY, "authority": cite("A9.15", "A9.17") + a919.cite("A9.19")}


# ================================================================================================= F8 gate snapshot
def rvm_gate_snapshot(repo=REPO) -> dict:
    """RVM-derived part of the F8 evidence-gate snapshot (moved from robust_optimizer.gate_snapshot). A9.19 / A9.20:
    only the flight configuration's RVM counts are an evidence gate; the RVM's hall_c1_reference column is the
    labelled ground / laboratory reference and is carried only as such."""
    rvm = ao.read_json(ao.RVM_REL, repo)
    counts = rvm["status_counts"]
    snap = {"rvm_hall_status": dict(rvm["hall_status"]),
            "rvm_status_counts": {c: counts[c] for c in ao.CONFIGURATIONS}}
    ground = {c: counts[c] for c in ao.GROUND_REFERENCE_CONFIGURATIONS if c in counts}
    if ground:
        snap["ground_reference_rvm_status_counts"] = {
            "label": "GROUND_ONLY_LAB_REFERENCE (A9.20): RVM cells of the C1 ground / laboratory reference; never a "
                     "flight configuration (A9.19) and never flight compliance evidence",
            "counts": ground}
    return snap


def gate_snapshot(repo=REPO) -> dict:
    """Evidence-gate statuses the robust filter must never change: design-side statuses
    (robust_optimizer.design_gate_snapshot) plus the RVM-derived snapshot read here."""
    from ..design import robust_optimizer as ro
    return ro.design_gate_snapshot(repo, rvm_gate_snapshot(repo))


# ================================================================================================= owner-question state
# (moved from abep_sim/design/owner_state.py, review finding RVF-02: the F-lane builders print each owner
# question's current answered status from owner_questions_state_v5.json; never fabricated)


OQ5_REL = "docs/budgets/owner_decisions/owner_questions_state_v5.json"


TBD_OWNER = "TBD_OWNER"


_CODE = re.compile(r"decision code ([A-Z0-9_]+)")


_DEC = re.compile(r"\((A9\.\d+ S[\d.]+)")


@lru_cache(maxsize=4)
def _rows(repo: str) -> dict:
    doc = json.loads((Path(repo) / OQ5_REL).read_text())
    out: dict[str, dict] = {}
    for r in doc["rows"]:
        prev = out.get(r["id"])
        # an answered row wins over a TBD_OWNER row of the same id (split questions carry both)
        if prev is None or (prev["status"] == TBD_OWNER and r["status"] != TBD_OWNER):
            out[r["id"]] = r
    return out


def owner_state(qid: str, repo: Path = REPO) -> dict:
    """{id, status, answered, decision, decision_code, status_detail, source} for one owner question."""
    r = _rows(str(repo)).get(qid)
    if r is None or r["status"] == TBD_OWNER:
        return {"id": qid, "status": TBD_OWNER, "answered": False, "decision": None, "decision_code": None,
                "status_detail": TBD_OWNER if r is None else r.get("status_detail", TBD_OWNER),
                "source": f"{OQ5_REL} rows[id={qid}]" + ("" if r is not None else " (absent)")}
    detail = r.get("status_detail") or r["status"]
    code = _CODE.search(detail)
    dec = _DEC.search(detail)
    return {"id": qid, "status": r["status"], "answered": True, "decision": dec.group(1) if dec else None,
            "decision_code": code.group(1) if code else None, "status_detail": detail,
            "source": f"{OQ5_REL} rows[id={qid}]"}


def status_label(qid: str, repo: Path = REPO) -> str:
    """Short label for record text: 'ANSWERED A9.13 S6.4 CATALYTIC_NOT_BASELINE' or 'TBD_OWNER'."""
    s = owner_state(qid, repo)
    if not s["answered"]:
        return TBD_OWNER
    return " ".join(x for x in ("ANSWERED", s["decision"], s["decision_code"]) if x)


def apply_to_questions(questions: list[dict], repo: Path = REPO) -> list[dict]:
    """Lane open-question list with the as-raised status kept as history and the current v5 state applied."""
    out = []
    for q in questions:
        s = owner_state(q["id"], repo)
        out.append({**q, "status_as_raised": q.get("status", TBD_OWNER), "status": s["status_detail"]
                    if s["answered"] else TBD_OWNER, "owner_decision": s["decision"],
                    "decision_code": s["decision_code"], "owner_state_source": s["source"]})
    return out
