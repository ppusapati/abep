"""Programme layer: the F7 / F8 design-synthesis runners that apply the design-gate assessment (A9.22 layer separation).

The design modules (abep_sim/design/) compute design quantities and never import the assessment layer. The functions
below combine them with abep_sim.assessment.design_gates (HC-12 ripple status, the A9-02 RFP power-gate verdict, the
fail-closed hard-constraint evaluation and exclusion, the AG-13 statewise record, the HC-10 propellant-path check).
They are verbatim moves of the former abep_sim.design.architecture_optimizer / plenum_feed functions (module globals
of those modules are referenced through ``ao.`` / ``pf.``); outputs are identical.

  context_pareto        (was architecture_optimizer.context_pareto)     F7 upstream Pareto set per set pressure
  bus_power             (was architecture_optimizer.bus_power)          P_bus objective with the A9-02 gate verdict
  evaluate_system       (was architecture_optimizer.evaluate_system)    system objectives + hard constraints
  rank_full_system      (was architecture_optimizer.rank_full_system)   fail-closed full-system ranking
  statewise_T_minus_D   (was architecture_optimizer.statewise_T_minus_D) HC-08 / AG-13 statewise record
  feed_quality          (was plenum_feed.feed_quality)                  S6.12 / S6.17 feed-quality constraints

The former pure re-exports architecture_optimizer.evaluate_constraints / system_pareto / HARD_CONSTRAINTS /
PRE_EVALUATED_OBJECTIVES, upstream_a9_13.<MOVED_TO_ASSESSMENT> and robust_optimizer.gate_snapshot (no-argument form)
are reached directly in abep_sim.assessment.design_gates (evaluate_constraints, pareto_s6_17, HARD_CONSTRAINTS,
PRE_EVALUATED_OBJECTIVES, ripple_feed_quality, ..., gate_snapshot).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .. import bus_boundary_a9_v2 as bb
from ..design import a9_19_architecture as a919
from ..design import architecture_optimizer as ao
from ..design import plenum_feed as pf
from ..design import upstream_a9_13 as u13


def context_pareto(ctx: dict, objectives=ao.OBJ_KEYS) -> dict:
    """Pareto set per set pressure of one evaluated context. Returns {P_set: {n_evaluated, n_feasible, status counts,
    reason counts, members: [row dicts]}}; every member carries the NOT_EVALUATED system objectives."""
    from ..assessment import design_gates as dg   # A9.22: HC-12 ripple assessment (assessment layer)
    arr = ctx["arrays"]
    cands, comps, vols, tgs = ctx["candidates"], ctx["compressors"], ctx["volumes"], ctx["targets"]
    res = {}
    for ti, P in enumerate(tgs):
        sl = (slice(None), slice(None), slice(None), ti)
        feas = ctx["feasible"][sl]
        bits = ctx["bits"][sl]
        idx = np.argwhere(feas)
        F = np.column_stack([arr[k][sl][feas] for k in objectives]) if len(idx) else np.zeros((0, len(objectives)))
        mask = ao.pareto_mask(F, [ao.OBJ_SENSE[k] for k in objectives]) if len(idx) else np.zeros(0, bool)
        status_counts: dict = {}
        reason_counts: dict = {}
        for b in bits.ravel():
            rs = pf.reasons_from_bits(int(b))
            st = pf.status_from_reasons(rs)
            status_counts[st] = status_counts.get(st, 0) + 1
            for r in rs:
                reason_counts[r] = reason_counts.get(r, 0) + 1
        members = []
        for (ci, ki, vi), m in zip(idx, mask):
            if not m:
                continue
            g = (ci, ki, vi, ti)
            row = {"design_id": ao.design_id(cands[ci], ctx["filter"], comps[ki], vols[vi], P),
                   "candidate": cands[ci], "compressor": comps[ki], "V_m3": vols[vi], "P_set_Pa": P}
            for k in objectives:
                row[k] = float(arr[k][g])
            for k in ("mdot_captured_min_kgps", "drag_intake_max_se_N", "mdot_delivered_design_kgps", "xO_flow_min",
                      "xO_flow_max", "deadhead_margin_min", "kn_upper_min", "T_comp_max_K", "a_eq_design_m2"):
                row[k] = float(arr[k][g])
            for k in ao.REPORTED_CONSTRAINT_COLUMNS:
                if k in arr:
                    row[k] = float(arr[k][g])
            row["ripple_feed_quality"] = dg.ripple_feed_quality(row.get("ripple_transfer_shaft"), u13.VALUE_PARAMETRIC,
                                                                u13.h1_tolerance_tbd("ripple"))["status"]
            row["characterization_coverage"] = u13.characterization_coverage(row["mdot_delivered_min_kgps"])["position"]
            row["context_role"] = ctx.get("context_role", "ARCHITECTURE_CONTEXT")
            row["system_not_evaluated"] = list(ao.SYSTEM_NOT_EVALUATED_CODES)
            members.append(row)
        members.sort(key=lambda r: r["design_id"])
        res[P] = {"context_id": ao.context_id(ctx["scenario"], ctx["filter"], ctx["wall"], P),
                  "n_evaluated": int(bits.size), "n_feasible": int(feas.sum()), "status_counts": status_counts,
                  "reason_counts": reason_counts, "n_pareto": len(members), "members": members}
    return res


def bus_power(config: str, compressor_P_W: float | None, supplied: Mapping | None = None, repo: Path = ao.REPO) -> dict:
    """P_bus objective. EVALUATED only from supplied COMPLETE ledgers (steady + start-up steps) whose loads are all of
    a rankable class; the RFP gate verdict of bus_boundary_a9_v2.rfp_power_gate is carried for the hard constraint.
    Otherwise NOT_EVALUATED with the official ledger status and the parametric lower bound."""
    if supplied is not None:
        steady, startup = supplied["steady"], supplied["startup"]
        from ..assessment import design_gates as dg   # A9.22: the RFP power-gate verdict is an assessment
        gate = dg.bus_power_gate(steady, startup)
        def _ledger_classes(led):
            # every evidence class that enters P_bus: loads, slot efficiencies, front-end efficiency (PR #36 review)
            c = set(led["load_evidence_classes"])
            c |= {it["efficiency_evidence_class"] for it in led["items"]
                  if it.get("efficiency") is not None and it.get("efficiency_evidence_class")}
            if any(it.get("path") == "internal_bus" and it.get("state") != "OFF" for it in led["items"]):
                c.add(led["front_end"]["evidence_class"] or "TBD")
            return c
        classes = _ledger_classes(steady)
        for s in startup:
            classes |= _ledger_classes(s)
        if steady["status"] != "COMPLETE":
            return ao._obj("P_bus_W", ao.INCOMPLETE, None, "W", reason=f"supplied steady ledger {steady['status']}",
                        unlock=[ao.UNLOCK["P_bus"]], gate_verdict=gate["verdict"],
                        lower_bound_W=steady["P_bus_lower_bound_W"])
        syn = supplied.get("synthetic", False)
        st = ao.SYNTHETIC_ONLY if syn else (ao.EVALUATED if classes <= set(ao.RANKABLE_CLASSES) else ao.PARAMETRIC_ONLY)
        return ao._obj("P_bus_W", st, steady["P_bus_W"], "W", evidence_class=ao.SYN_CLASS if syn else
                    ",".join(sorted(classes)), source=supplied.get("source", "supplied A9-02 ledgers"),
                    gate_verdict=gate["verdict"], power_basis=steady["power_basis"])
    off = ao.official_ledger(config, repo)
    par = ao.official_ledger(config, repo, compressor_P_W) if compressor_P_W is not None else None
    return ao._obj("P_bus_W", ao.NOT_EVALUATED, None, "W",
                reason=f"A9-02 official ledger status {off['status']} ({len(off['tbd'])} TBD terms; compressor load "
                       "TBD per row 22); every Hall / ICP / C1 / valve / thermal / housekeeping load and every supply "
                       "efficiency is TBD", unlock=[ao.UNLOCK["P_bus"]],
                official_status=off["status"], official_lower_bound_W=off["P_bus_lower_bound_W"],
                parametric_lower_bound_W=None if par is None else par["P_bus_lower_bound_W"],
                parametric_status=None if par is None else par["status"],
                gate_verdict="NOT_EVALUABLE",
                allocation_context={"design_allocation_W": bb.DESIGN_ALLOCATION_W,
                                    "common_allocation_W": bb.COMMON_ALLOCATION_W,
                                    "rule": "owner allocations (rows 109, 114), never gates or predictions"})


def evaluate_system(upstream_row: Mapping | None, config: str, design: Mapping | None = None,
                    supplied: Mapping | None = None, repo: Path = ao.REPO) -> dict:
    """Every system objective of one design vector (upstream sub-vector from an F7 row; x_Hall / x_ICP / x_RF /
    x_thermal through the supplied records) and the fail-closed hard constraints. ``supplied`` keys: thrust,
    thrust_capability, spacecraft_drag, bus (ledgers), m_wet, Q_reject, I_e_margin, thermal_margin, firing_life,
    life_material (a record {value, evidence_class, source} standing for a closed life / material assessment),
    drag_intake_max (a record replacing the row's parametric F1 intake-drag value for HC-09), statewise_T_minus_D
    (upstream_a9_13.statewise_drag_compensation result, HC-08), feed_state_sufficiency (upstream_a9_13.
    feed_state_sufficiency result, HC-11), ripple_feed_quality (upstream_a9_13.ripple_feed_quality result, HC-12),
    propellant_capability (a record, 1 = air AND Xe operation demonstrated, HC-10) and propellant_paths (the
    modelled paths; default MODELLED_PROPELLANT_PATHS, checked structurally against A9.15)."""
    if config in ao.GROUND_REFERENCE_CONFIGURATIONS:
        raise ao.OptimizerError(f"REFUSED: {config!r} is not a flight configuration (A9.19: no conventional hollow "
                             "cathode; A9.20: C1 is a GROUND-ONLY laboratory reference)")
    if config not in ao.CONFIGURATIONS:
        raise ao.OptimizerError(f"unknown configuration {config!r}")
    from ..assessment import design_gates as dg   # A9.22: hard-constraint assessment (assessment layer)
    hc = a919.refuse_hollow_cathode_elements(config, ao.flight_configuration_elements(config, repo))
    s = dict(supplied or {})
    row = dict(upstream_row or {})
    pel = row.get("P_compressor_el_max_W")
    objs = {
        "T_minus_D_spacecraft_N": ao.thrust_minus_drag(row.get("drag_intake_max_N"), row.get("drag_intake_max_se_N"),
                                                    s.get("thrust"), s.get("spacecraft_drag"), repo,
                                                    intake_drag=s.get("drag_intake_max")),
        "P_bus_W": bus_power(config, pel, s.get("bus"), repo),
        "m_wet_kg": ao.wet_mass(config, {"AL-02": {"m_compressor_max_kg": row.get("m_compressor_max_kg"),
                                                 "status": ao.LABEL_PARAMETRIC, "allocation_kg": 5.5}}
                             if row.get("m_compressor_max_kg") is not None else None, s.get("m_wet"), repo),
        "Q_reject_W": ao.heat_rejection(pel, s.get("Q_reject"), repo),
        "I_e_cap_minus_I_d_max_A": ao.electron_margin(config, s.get("I_e_margin"), repo),
        "life_material": ao._life_material(design, s.get("life_material"), repo),
    }
    cvals = dict(objs)
    for k, name, units in (("thrust", "thrust_N", "N"), ("thrust_capability", "thrust_capability_N", "N"),
                           ("thermal_margin", "thermal_margin_K", "K"), ("firing_life", "firing_life_h", "h")):
        cvals[name] = ao.supplied_objective(name, s.get(k), units)
        if k in ("thrust", "thrust_capability"):
            cvals[name] = ao.hall_gated_thrust(name, cvals[name], repo)
    if row.get("drag_intake_max_N") is not None:
        cvals["drag_intake_max_N"] = ao._obj("drag_intake_max_N", ao.PARAMETRIC_ONLY, row["drag_intake_max_N"], "N",
                                          "model-derived", "F1 (TPMC) at a TBD surface scenario")
    if s.get("drag_intake_max") is not None:     # a supplied (e.g. measured / synthetic) intake-drag record
        cvals["drag_intake_max_N"] = ao.supplied_objective("drag_intake_max_N", s["drag_intake_max"], "N")
    # A9.13 S6.15 / S6.21 / S6.17 pre-evaluated statewise / feed-quality records (never recomputed from one number)
    for k in dg.PRE_EVALUATED_OBJECTIVES:
        cvals[k] = s.get(k)
    if cvals["ripple_feed_quality"] is None and row.get("ripple_transfer_shaft") is not None:
        cvals["ripple_feed_quality"] = dg.ripple_feed_quality(row["ripple_transfer_shaft"], u13.VALUE_PARAMETRIC,
                                                              u13.h1_tolerance_tbd("ripple"))
    prop = dg.propellant_paths_check(s.get("propellant_paths", ao.MODELLED_PROPELLANT_PATHS))
    cvals["propellant_capability"] = ao.supplied_objective("propellant_capability", s.get("propellant_capability"), "-")
    cons = dg.evaluate_constraints(cvals)
    ne = [ao.SYSTEM_OBJECTIVE_CODE[k] for k, v in objs.items() if v["status"] != ao.EVALUATED]
    return {"configuration": config, "design_id": row.get("design_id"), "objectives": objs, "constraints": cons,
            "propellant_paths": prop, "hollow_cathode_check": hc["check"],
            "c1_provisions_flagged": [e["id"] for e in hc["c1_provisions_flagged"]],
            "c1_absence_statements": [e["id"] for e in hc["c1_absence_statements"]],
            "system_not_evaluated": ne,
            "constraints_not_evaluated": [c["id"] for c in cons if c["status"] == ao.C_NOT_EVALUATED],
            "constraints_violated": [c["id"] for c in cons if c["status"] == ao.C_VIOLATED]}


def rank_full_system(evaluations: Sequence[Mapping], upstream_objectives: Sequence[str] = ()) -> dict:
    """Full-system ranking over evaluated design vectors: non-dominated sorting layers of the system objectives (plus
    optional upstream objective keys present in each record's 'upstream'), after removing vectors that VIOLATE a hard
    constraint or have one not MET on rankable values (fail closed). REFUSED_INCOMPLETE when ANY record has a system
    objective that is not EVALUATED / synthetic, including the life / material indicator set (no subset ranking:
    ranking only what happens to be measurable would bias the set); REFUSED_MIXED when synthetic and evidence records
    meet, in the objectives OR in the values a hard constraint was met on; REFUSED_PARAMETRIC_UPSTREAM when a ranked
    upstream objective is not EVALUATED / synthetic (the committed upstream values are PARAMETRIC_SENSITIVITY). A
    synthetic-only ranking is labelled SYNTHETIC_TEST_ONLY_NOT_EVIDENCE. Never a winner: layer 1 is a set.

    life_material is a gate, not a Pareto axis: it is an indicator set with no scalar (its life scalar is HC-07,
    firing life > 15,000 h); the ranking refuses until it is EVALUATED (or synthetic in a synthetic-only test)."""
    if not evaluations:
        return {"status": ao.RANK_REFUSED_NO_FEASIBLE, "reason": "no candidate supplied", "layers": {}}
    missing = {}
    kinds = set()
    for ev in evaluations:
        for name in [n for n, _ in ao.SYSTEM_OBJECTIVES] + ["life_material"]:
            o = ev["objectives"][name]
            ok_value = name == "life_material" or o["value"] is not None
            if o["status"] not in (ao.EVALUATED, ao.SYNTHETIC_ONLY) or not ok_value:
                missing.setdefault(name, 0)
                missing[name] += 1
            else:
                kinds.add(o["status"])
    if missing:
        return {"status": ao.RANK_REFUSED_INCOMPLETE,
                "reason": "system objectives (incl. the life / material indicator gate) not EVALUATED for some or "
                          "all candidates (fail closed, no subset ranking)", "missing_counts": missing,
                "n_candidates": len(evaluations), "unlock": {k: v for k, v in ao.UNLOCK.items()}, "layers": {}}
    bad_up = {}
    for ev in evaluations:
        for k in upstream_objectives:
            v, st = ao._upstream_value(ev, k)
            if st not in (ao.EVALUATED, ao.SYNTHETIC_ONLY) or v is None or not math.isfinite(float(v)):
                bad_up.setdefault(k, set()).add(str(st))
            else:
                kinds.add(st)
    if bad_up:
        return {"status": ao.RANK_REFUSED_PARAMETRIC_UPSTREAM,
                "reason": "a ranked upstream objective is not EVALUATED / synthetic (PARAMETRIC_SENSITIVITY or "
                          "unlabelled values never enter an evidence ranking; rank them in the labelled F7 upstream "
                          "Pareto sets instead)", "upstream_statuses": {k: sorted(v) for k, v in bad_up.items()},
                "layers": {}}
    from ..assessment import design_gates as dg   # A9.22: hard-constraint exclusion is an assessment
    kinds |= dg.constraint_met_value_kinds(evaluations)
    if kinds == {ao.EVALUATED, ao.SYNTHETIC_ONLY}:
        return {"status": ao.RANK_REFUSED_MIXED, "reason": "synthetic test data and evidence never meet in one ranking "
                "(objectives, ranked upstream values and the values hard constraints were met on)", "layers": {}}
    synthetic = kinds == {ao.SYNTHETIC_ONLY}
    admissible, excluded = dg.hard_constraint_partition(evaluations)
    if not admissible:
        return {"status": ao.RANK_REFUSED_NO_FEASIBLE, "reason": "every candidate violates a hard constraint or has one "
                "not met on rankable values (NOT_EVALUATED or parametric only; fail closed)",
                "excluded": [{"design_id": e["design_id"], "constraints": b} for e, b in excluded], "layers": {}}
    keys = [k for k, _ in ao.SYSTEM_OBJECTIVES] + list(upstream_objectives)
    senses = [s for _, s in ao.SYSTEM_OBJECTIVES] + [ao.OBJ_SENSE[k] for k in upstream_objectives]
    F = np.array([[ev["objectives"][k]["value"] for k, _ in ao.SYSTEM_OBJECTIVES] +
                  [ao._upstream_value(ev, k)[0] for k in upstream_objectives] for ev, _ in admissible], dtype=float)
    lay = ao.nondominated_layers(F, senses)
    layers: dict = {}
    for (ev, _), l in zip(admissible, lay):
        layers.setdefault(int(l), []).append(ev["design_id"])
    for l in layers:
        layers[l].sort()
    return {"status": ao.RANK_COMPUTED_SYNTHETIC if synthetic else ao.RANK_COMPUTED,
            "label": ao.SYNTHETIC_ONLY if synthetic else "NOT_A_SELECTION (Pareto layers; no winner)",
            "objectives": keys, "senses": senses, "layers": layers,
            "life_material": "gate only (indicator set, no scalar axis; its life scalar is HC-07)",
            "excluded": [{"design_id": e["design_id"], "constraints": b} for e, b in excluded]}


def statewise_T_minus_D(states, thrust_fn, drag_fn, repo: Path = ao.REPO) -> dict:
    """HC-08 / AG-13 statewise record (A9.13 S6.15) with the admitted-Hall-member gate read from the repository."""
    from ..assessment import design_gates as dg
    return dg.statewise_drag_compensation(states, thrust_fn, drag_fn,
                                           hall_admitted=bool(ao.hall_response_status(repo)["admitted_members"]))


def feed_quality(case_result: Mapping, tolerances: Mapping[str, "u13.H1Tolerance"] | None = None) -> dict:
    """Feed-quality constraints of one transient case against measured H-1 tolerances (S6.12 / S6.17): pressure
    peak deviation and ripple. With a TBD tolerance the constraint is NOT_EVALUATED; F4's provisional 2 % band never
    replaces a tighter measured H-1 limit. Values from this model are PARAMETRIC_SENSITIVITY."""
    from ..assessment import design_gates as dg     # A9.22: HC-12 ripple assessment lives in the assessment layer
    tol = dict(tolerances or {})
    obj = case_result.get("objectives") or {}
    pk = obj.get("peak_deviation_max")
    rip = obj.get("ripple_transfer_shaft")
    p_tol = tol.get("pressure") or u13.h1_tolerance_tbd("pressure")
    r_tol = tol.get("ripple") or u13.h1_tolerance_tbd("ripple")
    band = u13.governing_band("pressure", pf.SETTLE_BAND, p_tol)
    if p_tol.status == u13.VALUE_TBD or pk is None:
        p_status = u13.C_NOT_EVALUATED
    else:
        p_status = u13.constraint_status(pk <= p_tol.value_frac, u13.combine_value_status([u13.VALUE_PARAMETRIC,
                                                                                         p_tol.status]))
    return {"framework": pf.TRANSIENT_FRAMEWORK["status"], "pressure_band": band,
            "pressure_peak_deviation": {"value_frac": pk, "status": p_status},
            "ripple": dg.ripple_feed_quality(rip, u13.VALUE_PARAMETRIC if rip is not None else u13.VALUE_TBD, r_tol),
            "authority": u13.cite("A9.13")}
