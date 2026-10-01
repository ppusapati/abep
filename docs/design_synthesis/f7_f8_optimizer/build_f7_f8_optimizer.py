#!/usr/bin/env python3
"""A9.7 F7 coupled architecture optimizer + F8 robust optimization study (follow-on fo_a9_7_f7_f8_coupled_optimizer).

Runs abep_sim/design/architecture_optimizer.py (F7) and abep_sim/design/robust_optimizer.py (F8) on the committed
lane deliverables (F1 IF-A1 records and species table, F2/F4 filter cases, F3 compressor front union, F4 plenum grid,
F5 x_Hall windows, F6 x_ICP definition, P1-P4 frameworks, mass/power v3, the A9-02 bus boundary, the RVM) and writes

  f7_f8_optimizer_v1.json         design-vector blocks, parameters, upstream Pareto summary, system evaluation
                                  (every system objective evaluated or refused with its unlock evidence), fail-closed
                                  constraints, full-system ranking status, F8 UQ axes / robustness / robust Pareto,
                                  architecture questions, interface demands, open owner questions, m16_impact
  f7_upstream_pareto_v1.json      every upstream Pareto member of every context (columns / rows)
  f8_robust_candidates_v1.json    per-survivor robustness records (scenario set, TPMC Monte Carlo)
  F7_F8_OPTIMIZER.md              generated from the JSON

What it is not: a design, a selection, a winner, a requirement, a PASS, a model change. No existing module is modified;
nothing is wired into archengine; goldens cannot move. Deterministic (seeded generators from stable ids), no Julia, no
TPMC; a few minutes of CPU.

Usage:
  python docs/design_synthesis/f7_f8_optimizer/build_f7_f8_optimizer.py           # (re)write outputs
  python docs/design_synthesis/f7_f8_optimizer/build_f7_f8_optimizer.py --check   # exit 1 unless reproduced
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from abep_sim.design import architecture_optimizer as ao  # noqa: E402
from abep_sim.design import plenum_feed as pf  # noqa: E402
from abep_sim.design import robust_optimizer as ro  # noqa: E402

OUT_DIR_REL = "docs/design_synthesis/f7_f8_optimizer"
SCRIPT_REL = f"{OUT_DIR_REL}/build_f7_f8_optimizer.py"
JSON_NAME = "f7_f8_optimizer_v1.json"
PARETO_NAME = "f7_upstream_pareto_v1.json"
ROBUST_NAME = "f8_robust_candidates_v1.json"
MD_NAME = "F7_F8_OPTIMIZER.md"
TEST_REL = "tests/test_design_f7_f8_optimizer.py"
BASE_COMMIT = "1bcfe0e4ba2242ebd8deaf1263fa98d85f75f631"
SIG = 7
N_MC = 100
OWNER_FLOW_RANGE_MGPS = (0.38, 3.2)       # characterization COVERAGE only (A9.13 S6.21; owner row 73 range), never a gate

PINNED = (
    "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md",
    "docs/decisions/OD_2026_10_01_A9_7_architecture_freeze_design_synthesis.json",
    ao.F1_REL, ao.F3_REL, ao.F3D_REL, ao.F4_REL, ao.F5_REL, ao.F6_REL,
)
REFERENCED_NOT_PINNED = (
    (ao.F2_REL, "F2 filter-stage deliverable (filter cases are built through abep_sim/design/filter_stage.py)"),
    (ao.MP_REL, "mass/power v3 (A9.15-applied): slot TBD texts, allocations, wet roll-ups (mutable package; "
                "identity checked)"),
    (ao.P1_REL, "P1 ICP bench (ICP-45 status, I_d,max,H1 TBD)"),
    (ao.P2_REL, "P2 impedance-map preparation (no data)"),
    (ao.P3_REL, "P3 coupled thermal framework (fail-closed evaluations, items)"),
    (ao.P4_REL, "P4 anode / collector materials (gate matrix, fixed statuses)"),
    (ao.RVM_REL, "RVM A9 (requirement rows behind HARD_CONSTRAINTS; hall_status)"),
    (ao.RFQ_REL, "RFQ v3 (RF chain procurement architecture, A9.15-applied)"),
    (ao.ENS_REL, "transport ensemble (admitted members: credible set)"),
    (ao.VAL_REL, "P5-N2 v1 validation release (decision)"),
    (ao.PARITY_REL, "abep_core parity report (TPMC backend policy only; no TPMC is run)"),
    ("abep_sim/design/architecture_optimizer.py", "the F7 module"),
    ("abep_sim/design/robust_optimizer.py", "the F8 module"),
    ("abep_sim/design/plenum_feed.py", "F4 physics (called)"),
    ("abep_sim/bus_boundary_a9.py", "A9-02 bus boundary (called, never modified)"),
    (ao.F5_BUILDER_REL, "F5 geometric_admissibility (imported by path, read-only)"),
)
IDENTITY = {ao.MP_REL: "mass_power_a9_v3", ao.P3_REL: "p3_coupled_thermal_v2", ao.P4_REL: "p4_anode_materials_v1",
            ao.RVM_REL: "rvm_a9_v1", ao.P1_REL: "p1_icp_bench_v1", ao.P2_REL: "p2_impedance_prep_v1"}


def sha256(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def rnd(x, sig=SIG):
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (float, np.floating)):
        x = float(x)
        if not math.isfinite(x):
            return None
        return float(f"{x:.{sig}g}")
    if isinstance(x, dict):
        return {str(k): rnd(v, sig) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v, sig) for v in x]
    if isinstance(x, np.ndarray):
        return [rnd(v, sig) for v in x.tolist()]
    return x


def mg(x):
    return None if x is None else x * 1e6


# ----------------------------------------------------------------------------------------------------- F7
def stage_f7(inp):
    ctxs, pars = {}, {}
    for wall in ao.WALL_CASES:
        for filt in inp.filters:
            for sc in inp.scenarios:
                ctx = ao.upstream_context(inp, sc, filt, wall)
                pars[(sc, filt, wall)] = ao.context_pareto(ctx)
                if filt == ro.NOMINAL_FILTER:
                    ctxs[(sc, filt, wall)] = ctx
    return ctxs, pars


PARETO_COLS = ("candidate", "compressor", "V_m3") + ao.OBJ_KEYS + (
    "mdot_captured_min_kgps", "mdot_delivered_design_kgps", "xO_flow_min", "xO_flow_max", "deadhead_margin_min",
    "kn_upper_min", "T_comp_max_K")
PARETO_SIG = 6


def pareto_rows(pars):
    out = []
    for (sc, filt, wall), par in sorted(pars.items()):
        for P, b in sorted(par.items()):
            if not b["members"]:
                continue
            out.append({"context_id": b["context_id"], "scenario": sc, "filter": filt, "wall": wall, "P_set_Pa": P,
                        "system_not_evaluated": list(ao.SYSTEM_NOT_EVALUATED_CODES),
                        "rows": [[rnd(m[c], PARETO_SIG) for c in PARETO_COLS] for m in b["members"]]})
    return out


def _f4_single_frontier() -> str:
    """F4-01 single-setpoint all-state frontier as stated by the committed F4 record (read, never hard-coded)."""
    import re
    f4 = json.loads((REPO / "docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json").read_text(encoding="utf-8"))
    txt = next(f["finding"] for f in f4["findings"] if f["id"] == "F4-01")
    m = re.search(r"WALL-G0\) is ([0-9.eE+-]+) mg/s", txt)
    if m is None:
        raise SystemExit("REFUSED: F4-01 no longer states the single-setpoint frontier")
    return m.group(1)


def pareto_summary(inp, pars):
    rows = []
    for (sc, filt, wall), par in sorted(pars.items()):
        for P, b in sorted(par.items()):
            best = max(b["members"], key=lambda m: m["mdot_delivered_min_kgps"]) if b["members"] else None
            rows.append([b["context_id"], sc, filt, wall, P, b["n_evaluated"], b["n_feasible"], b["n_pareto"],
                         rnd(mg(best["mdot_delivered_min_kgps"])) if best else None,
                         best["design_id"] if best else None,
                         sum(1 for m in b["members"] if m["mdot_delivered_min_kgps"] * 1e6 >= OWNER_FLOW_RANGE_MGPS[0])])
    cols = ["context_id", "scenario", "filter", "wall", "P_set_Pa", "n_evaluated", "n_feasible", "n_pareto",
            "frontier_mdot_delivered_min_mgps", "frontier_attained_by", "n_pareto_reaching_coverage_0.38_mgps"]
    return {"columns": cols, "rows": rows}


def reason_totals(pars):
    st, rs = Counter(), Counter()
    for par in pars.values():
        for b in par.values():
            st.update(b["status_counts"])
            rs.update(b["reason_counts"])
    return dict(sorted(st.items())), dict(sorted(rs.items()))


def stage_system(inp, pars):
    """Full system evaluation of every nominal (filter none, WALL-G0) Pareto member, every flight configuration
    (ao.CONFIGURATIONS; A9.19 / A9.20: hall_icp_neutralizer only), and the
    full-system ranking attempt."""
    evals = {c: [] for c in ao.CONFIGURATIONS}
    exemplar = None
    for (sc, filt, wall), par in sorted(pars.items()):
        if filt != ro.NOMINAL_FILTER or wall != ro.NOMINAL_WALL:
            continue
        for P, b in sorted(par.items()):
            for m in b["members"]:
                for cfg in ao.CONFIGURATIONS:
                    ev = ao.evaluate_system(m, cfg, design=inp.designs[m["compressor"]])
                    ev["design_id"] = f"{sc}|{m['design_id']}"
                    evals[cfg].append(ev)
                    if exemplar is None and cfg == "hall_icp_neutralizer":
                        exemplar = ev
    status = Counter()
    cons = Counter()
    for cfg, evs in evals.items():
        for ev in evs:
            for k, o in ev["objectives"].items():
                status[(cfg, k, o["status"])] += 1
            for c in ev["constraints"]:
                cons[(cfg, c["id"], c["status"])] += 1
    ranking = {cfg: ao.rank_full_system(evs) for cfg, evs in evals.items()}
    pel = [ev["objectives"]["P_bus_W"]["parametric_lower_bound_W"] for ev in evals["hall_icp_neutralizer"]]
    mcomp = [ev["objectives"]["m_wet_kg"]["lines"][1]["design_parametric"]["m_compressor_max_kg"]
             for ev in evals["hall_icp_neutralizer"]]
    return {"evaluations_by_configuration": {c: len(v) for c, v in evals.items()},
            "objective_status_counts": [[c, k, s, n] for (c, k, s), n in sorted(status.items())],
            "constraint_status_counts": [[c, k, s, n] for (c, k, s), n in sorted(cons.items())],
            "exemplar": exemplar, "ranking": {c: {k: v for k, v in r.items() if k != "unlock"}
                                              for c, r in ranking.items()},
            "parametric_P_bus_lower_bound_W_range": [min(pel), max(pel)],
            "parametric_m_compressor_kg_range": [min(mcomp), max(mcomp)],
            "n_m_compressor_above_AL02_allocation": sum(1 for x in mcomp if x > 5.5)}


# ----------------------------------------------------------------------------------------------------- F8
def stage_f8(inp, ctxs, pars):
    before = ro.gate_snapshot()
    surv = ro.survivors(pars)
    scen = ro.scenario_robustness(surv, ctxs, inp.scenarios, ro.NOMINAL_WALL)
    mc = ro.tpmc_monte_carlo(inp, surv, inp.scenarios, n=N_MC)
    allsc = [s for s in surv if scen[s["design_id"]]["worst_case_all_scenarios"] is not None]
    rp = ro.robust_pareto(allsc, scen, mc)
    mem_ids = sorted({m["design_id"] for b in rp.values() for m in b["members"]})
    mem = [s for s in surv if s["design_id"] in mem_ids]
    wall = ro.scenario_robustness(mem, ctxs, inp.scenarios, "WALL-TI64-DB")
    point = ro.pointing_sensitivity(inp, mem, inp.scenarios)
    elas = {m["design_id"]: ro.compressor_elasticities(inp, m, inp.scenarios) for m in mem}
    after = ro.gate_snapshot()
    tiers = Counter(scen[s["design_id"]]["n_scenarios_feasible"] for s in surv)
    return {"survivors": surv, "scenario": scen, "mc": mc, "all_scenario_feasible": allsc, "robust_pareto": rp,
            "members": mem, "wall": wall, "pointing": point, "elasticities": elas, "gates_before": before,
            "gates_after": after, "tiers": dict(sorted(tiers.items()))}


MC_COLS = ("P_feasible", "mdot_delivered_min_p05_kgps", "mdot_delivered_min_p50_kgps", "P_compressor_el_max_p95_W",
           "deadhead_margin_p05", "drag_intake_max_p95_N")


def robust_rows(f8):
    rows = []
    for s in f8["survivors"]:
        d = s["design_id"]
        sc = f8["scenario"][d]
        m = f8["mc"].get((s["candidate"], s["filter"], s["compressor"], s["P_set_Pa"]), {})
        rows.append({"design_id": d, "pareto_in": s["pareto_in"], "n_scen_feasible": sc["n_scenarios_feasible"],
                     "infeasible_in": sc["infeasible_in"],
                     "worst_case": rnd(sc["worst_case_all_scenarios"], 6),
                     "mc": {k: rnd([v[c] for c in MC_COLS], 6) for k, v in sorted(m.items())}})
    return rows


# ----------------------------------------------------------------------------------------------------- document parts
def parameters():
    P = []

    def p(pid, value, units, basis, source, ec, status):
        P.append({"id": pid, "value": value, "units": units, "basis": basis, "source": source,
                  "evidence_class": ec, "status": status})
    p("F78-P-01", list(ao.UPSTREAM_TARGETS_PA), "Pa", "plenum set pressures evaluated (F4 requirement sweep up to the "
      "0.1 Pa free-molecular domain cap; above it everything is NOT_EVALUATED_OUT_OF_DOMAIN in F3/F4, A9.13 S6.8)",
      f"{ao.F4_REL} requirement_sweep; F3 P-MOLECULAR-LIMIT", "TBD (requirement)", "CONTEXT_AXIS")
    p("F78-P-02", list(ao.VOLUMES_M3), "m^3", "plenum volume grid", f"{ao.F4_REL} search_variables x_plenum.V",
      "assumed", "SEARCHED (F4 grid)")
    p("F78-P-03", list(ao.WALL_CASES), "-", "wall O-recombination cases (gamma TBD)", f"{ao.F4_REL} items F4-P-06",
      "TBD", "CONTEXT_AXIS (WALL-G0 nominal)")
    p("F78-P-04", pf.RES_DEFAULTS["leak_area_m2"], "m^2", "plenum leak area: parametric case (Reservoir code default, "
      "uncited)", f"{ao.F4_REL} items F4-P-05", "TBD", "PARAMETRIC_SENSITIVITY")
    p("F78-P-05", pf.T_CHAIN_K, "K", "isothermal chain temperature (F1 wall temperature code default)",
      f"{ao.F4_REL} items F4-P-01", "assumed", "ASSUMED_ISOTHERMAL_CHAIN")
    p("F78-P-06", [o[0] for o in ao.UPSTREAM_OBJECTIVES], "-", "upstream Pareto objectives (directions in "
      "upstream_objectives); weak dominance, ties kept, infeasible / out-of-domain vectors never enter",
      "abep_sim/design/architecture_optimizer.py UPSTREAM_OBJECTIVES / pareto_mask", "definition", "DEFINITION")
    p("F78-P-07", "single setpoint for all five orbit states", "-", "a vector is feasible only if every orbit state is "
      "feasible at the one set pressure (F4 single-setpoint frontier; the scheduled alternative is F4 OQ-F4-01)",
      f"{ao.F4_REL} requirement_sweep.feasibility_rule", "definition", "DEFINITION")
    p("F78-P-08", N_MC, "-", "TPMC-statistics Monte Carlo draws per (candidate, scenario)", "this study",
      "numerical-setting", "STUDY_SETTING")
    p("F78-P-09", ro.SEED_BASE, "-", "seed base; generator per (candidate, scenario) = default_rng(stable_seed("
      "'tpmc', candidate, scenario))", "abep_sim/design/robust_optimizer.py", "numerical-setting", "STUDY_SETTING")
    p("F78-P-10", ro.ELASTICITY_STEP, "-", "relative central-difference step of the compressor elasticities "
      "(numerical setting, not an uncertainty)", "abep_sim/design/robust_optimizer.py", "numerical-setting",
      "STUDY_SETTING")
    p("F78-P-11", OWNER_FLOW_RANGE_MGPS, "mg/s", "characterization coverage range (A9.13 S6.21: 0.38 mg/s and "
      "~1.3 mg/s are not requirements; no fixed flight mass-flow gate) used only to COUNT Pareto members reaching its "
      "lower end (coverage, never PASS / FAIL)", f"{ao.F4_REL} requirement_sweep.mdot_req_basis "
      "(owner row 73; A9.13 S6.21)", "owner-allocation", "CHARACTERIZATION_COVERAGE_ONLY")
    p("F78-P-12", "TBD", "N", "spacecraft body / array drag D_body", "none (F1-ID-08)", "TBD", "TBD")
    p("F78-P-13", "TBD", "N", "thrust T of H-1 on the delivered feed", f"{ao.ENS_REL} (members = [])", "TBD",
      "NOT_EVALUATED (no admitted Hall response map)")
    return P


def interface_demands():
    D = []

    def d(i, direction, counterpart, content, status):
        D.append({"id": i, "direction": direction, "counterpart": counterpart, "content": content, "status": status})
    d("F78-ID-01", "F1 -> F7/F8", "abep_sim/design/intake_synthesis.py; " + ao.F1_REL, "IF-A1 records (mdot_fwd, "
      "p_passive, K_back, SEs), species table (C_D per state, theta 5 node), C-DRAG-RFP infeasibility", "CONSUMED")
    d("F78-ID-02", "F7 -> F1", "abep_sim/design/intake_synthesis.py (F1-ID-08)", "spacecraft frontal area / body drag "
      "and AOCS pointing budget: F7 cannot supply them (no spacecraft geometry in the repository); T - D stays "
      "NOT_EVALUATED", "DEMANDED (owner / spacecraft ICD)")
    d("F78-ID-03", "F2 -> F7", "abep_sim/design/filter_stage.py; " + ao.F2_REL, "filter cases through F4 "
      "filter_cases() (none, parametric tau, placeholder)", "CONSUMED (context axis)")
    d("F78-ID-04", "F7 -> F2", "abep_sim/design/filter_stage.py", "a quantified protection / contamination metric per "
      "evidenced filter concept: until it exists the filter is a context axis, never searched", "DEMANDED")
    d("F78-ID-05", "F3 -> F7", "abep_sim/design/compressor_synthesis.py; " + ao.F3D_REL, "compressor front union, "
      "fixed coefficients, gates", "CONSUMED")
    d("F78-ID-06", "F8 -> F3", "abep_sim/design/compressor_synthesis.py (compressor_downselect T-1..T-9)",
      "elasticity ranking of the uncited coefficients on the robust set (prioritises closing tests)", "PROVIDED")
    d("F78-ID-07", "F4 -> F7", "abep_sim/design/plenum_feed.py; " + ao.F4_REL, "steady_sweep gates, Plenum / "
      "CompressorPlant / filter cases, search grid", "CONSUMED")
    d("F78-ID-08", "F5 -> F7", ao.F5_REL + " x_hall_design_space; " + ao.F5_BUILDER_REL, "x_Hall windows and "
      "admissibility (IFS-F7-01)", "CONSUMED (bounded, not searched)")
    d("F78-ID-09", "F7 -> F5", ao.F5_REL + " (IFS-F7-02)", "Hall performance for any x_Hall (T, I_d, efficiency, heat "
      "shares): required before x_Hall can be searched", "DEMANDED (NOT_EVALUATED)")
    d("F78-ID-10", "F6 -> F7", "abep_sim/design/icp_geometry_synthesis.py; " + ao.F6_REL, "x_ICP definition and the "
      "fail-closed objective contract (F6-IF-S01)", "CONSUMED (bounds TBD, not searchable)")
    d("F78-ID-11", "P1 -> F7", ao.P1_REL, "ICP-45A result and registered I_d,max,H1 for I_e,cap - I_d,max",
      "DEMANDED (NOT_EVALUATED)")
    d("F78-ID-12", "P2 / RFQ v3 -> F7", f"{ao.P2_REL}; {ao.RFQ_REL}", "RF ratings, match loss, flight source "
      "efficiency (x_RF)", "DEMANDED (TBD_AFTER_IMPEDANCE_MAP)")
    d("F78-ID-13", "P3 -> F7", ao.P3_REL, "solved coupled network for Q_reject and the 50 K margin", "DEMANDED "
      "(INCOMPLETE_EVIDENCE)")
    d("F78-ID-14", "P4 -> F7", ao.P4_REL, "material gate evidence for life / material indicators", "DEMANDED")
    d("F78-ID-15", "mass/power v3 -> F7", ao.MP_REL, "A9-02 slot TBD texts, allocations, evidence floors, wet "
      "roll-ups; F7 returns design-parametric masses in a separate column (never merged)", "CONSUMED / PROVIDED")
    d("F78-ID-16", "F7/F8 -> F9", "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json (F9-ID-07)",
      "upstream Pareto sets per context, robust Pareto set, full-system ranking status REFUSED_INCOMPLETE with the "
      "unlock evidence map; F9 carries sets, never a silently selected point", "PROVIDED")
    d("F78-ID-17", "F7/F8 -> F0", "docs/performance/", "workload: F7 steady sweeps + F8 Monte Carlo (CPU printed by "
      "the builder; no Rust kernel needed: no TPMC runs here)", "PROVIDED")
    return D


def open_owner_questions():
    return [
        {"id": "OQ-F78-01", "question": "Is drag compensation T - D_spacecraft >= 0 (HC-08) a hard architecture "
         "constraint, and at which orbit states / averaging (instantaneous at every state, or orbit-averaged)? It "
         "is carried as a derived constraint, not an RVM row.", "proposed_answer": "none proposed",
         "needed_for": "HC-08 and the full-system ranking", "source": "A9.7 F7 objective list; RVM rows 02/03"},
        {"id": "OQ-F78-02", "question": "Should architecture robustness require feasibility in EVERY TBD surface "
         "scenario (alpha 0..1, Maxwell / CLL; current F8 rule, fail closed), or will a measured accommodation range "
         "(DI-1.3) narrow the scenario set first?", "proposed_answer": "none proposed",
         "needed_for": "F8 robust filter scope", "source": "F1-P-07 / F1-P-08"},
        {"id": "OQ-F78-03", "question": "Which upstream quantities enter the full-system ranking once T, P_bus and "
         "I_e,cap exist (e.g. ripple transfer as an objective or as a constraint with a TBD tolerance from H-1)?",
         "proposed_answer": "none proposed", "needed_for": "rank_full_system upstream_objectives",
         "source": "F5 IFD-F4-05 (transient tolerances TBD)"},
        {"id": "OQ-F78-04", "question": "Provide (or authorize sourcing of) the spacecraft frontal geometry / body and "
         "array drag basis for D_spacecraft (F1-ID-08).", "proposed_answer": "none proposed",
         "needed_for": "T - D_spacecraft", "source": "F1 interface demand F1-ID-08"},
    ]


def m16_impact():
    return [{"m16_row": r, "key": k, "state_change": "none: PARAMETRIC_SENSITIVITY design synthesis (no measurement, "
             "no CBE); provides Pareto / robust sets and the unlock map as inputs to the open decisions"}
            for r, k in ((1, "intake"), (2, "filter"), (3, "compressor"), (4, "buffer_plenum"))]


def findings(inp, f7sum, totals, sysd, f8, pars):
    F = []
    rows = [dict(zip(f7sum["columns"], r)) for r in f7sum["rows"]]
    nom = [r for r in rows if r["filter"] == ro.NOMINAL_FILTER and r["wall"] == ro.NOMINAL_WALL]
    best = max((r for r in nom if r["frontier_mdot_delivered_min_mgps"] is not None),
               key=lambda r: r["frontier_mdot_delivered_min_mgps"])
    n_par = sum(r["n_pareto"] for r in rows)
    n_ctx = sum(1 for r in rows if r["n_pareto"])
    F.append({"id": "F78-01", "evidence_class": "model-derived (PARAMETRIC_SENSITIVITY inputs)", "finding":
              f"upstream sub-problem F1 -> F2 -> F3 -> F4 searched over {len(inp.candidates)} d-collapsed intakes x "
              f"{len(inp.plants)} compressors x {len(ao.VOLUMES_M3)} volumes x {len(ao.UPSTREAM_TARGETS_PA)} set "
              f"pressures in {len(rows)} contexts (10 surface scenarios x 5 filter cases x 2 wall cases x 6 P_set): "
              f"{n_par} Pareto members in {n_ctx} non-empty contexts; vector statuses {totals[0]}"})
    F.append({"id": "F78-02", "evidence_class": "model-derived", "finding":
              f"nominal context (filter none, WALL-G0): the all-state delivered-flow frontier is "
              f"{best['frontier_mdot_delivered_min_mgps']} mg/s ({best['scenario']}, P_set {best['P_set_Pa']} Pa, "
              f"{best['frontier_attained_by']}); Pareto members reaching the lower end of the 0.38-3.2 mg/s "
              f"characterization coverage (A9.13 S6.21: coverage only, not a requirement or gate) at every state: "
              f"{sum(r['n_pareto_reaching_coverage_0.38_mgps'] for r in rows)} (all contexts). Compare F4-01 (single-setpoint "
              f"frontier {_f4_single_frontier()} mg/s)"})
    byP = Counter()
    for r in rows:
        if r["n_pareto"]:
            byP[r["P_set_Pa"]] += 1
    F.append({"id": "F78-03", "evidence_class": "model-derived", "finding":
              f"set pressures with any all-state-feasible vector (number of contexts): {dict(sorted(byP.items()))}; "
              "the others fail by dead-head (high P_set) or by leaving the Gaede characteristic domain (low P_set); "
              f"reason counts over all vectors {totals[1]}"})
    fr = {}
    for r in rows:
        if r["wall"] == ro.NOMINAL_WALL and r["frontier_mdot_delivered_min_mgps"] is not None:
            fr[r["filter"]] = max(fr.get(r["filter"], 0.0), r["frontier_mdot_delivered_min_mgps"])
    F.append({"id": "F78-04", "evidence_class": "model-derived (PARAMETRIC filter cases)", "finding":
              f"frontier by filter case (WALL-G0, max over scenarios and P_set, mg/s): {fr}; the filter is a context "
              "axis because its protection benefit is NOT_EVALUATED"})
    rk = sysd["ranking"]["hall_icp_neutralizer"]
    F.append({"id": "F78-05", "evidence_class": "inferred", "finding":
              f"system level: for all {sysd['evaluations_by_configuration']} nominal Pareto evaluations every system "
              "objective (T - D, P_bus, m_wet, Q_reject, I_e,cap - I_d,max, life) is NOT_EVALUATED and every RVM "
              "hard constraint except the intake-face drag bound HC-09 is NOT_EVALUATED (fail closed); full-system "
              f"ranking {rk['status']} for every flight configuration {list(ao.CONFIGURATIONS)} (A9.19 / A9.20: C1 is a "
              f"GROUND_REFERENCE, never evaluated as a flight candidate) (missing counts {rk.get('missing_counts')})"})
    F.append({"id": "F78-06", "evidence_class": "model-derived (code-default coefficients)", "finding":
              "P_bus: the official A9-02 ledger is PARTIAL_BOUNDARY (compressor load TBD, row 22) with lower bound "
              f"0 W; the parametric sensitivity ledger booking the F3/F4 compressor draw has lower bound "
              f"{rnd(sysd['parametric_P_bus_lower_bound_W_range'])} W on the nominal Pareto members (vs the 300 W "
              "common allocation, an allocation not a gate)"})
    F.append({"id": "F78-07", "evidence_class": "model-derived (code-default coefficients; allocation context)",
              "finding": f"compressor model mass on the nominal Pareto members {rnd(sysd['parametric_m_compressor_kg_range'])}"
              f" kg; {sysd['n_m_compressor_above_AL02_allocation']} member evaluations exceed the 5.5 kg AL-02 "
              "allocation (parametric value vs allocation; neither is a CBE; never merged)"})
    rp = f8["robust_pareto"]
    F.append({"id": "F8-01", "evidence_class": "model-derived", "finding":
              f"{len(f8['survivors'])} unique upstream survivors (nominal-context Pareto members over all scenarios "
              f"and P_set); feasible-scenario tiers (n scenarios feasible: count) {f8['tiers']}; feasible in all 10 "
              f"surface scenarios: {len(f8['all_scenario_feasible'])}; robust Pareto members per P_set "
              f"{ {P: len(b['members']) for P, b in rp.items()} }; worst-case (over the 10 scenarios) delivered flow "
              f"of the robust members {rnd([min(m['mdot_delivered_min_kgps'] for b in rp.values() for m in b['members']) * 1e6, max(m['mdot_delivered_min_kgps'] for b in rp.values() for m in b['members']) * 1e6]) if any(b['members'] for b in rp.values()) else None}"
              " mg/s (compare the best single-scenario frontier in F78-02: the price of requiring feasibility in "
              "every TBD surface scenario)"})
    pnom = []
    for sv in f8["survivors"]:
        m = f8["mc"][(sv["candidate"], sv["filter"], sv["compressor"], sv["P_set_Pa"])]
        per = f8["scenario"][sv["design_id"]]["per_scenario"]
        pnom += [m[sc]["P_feasible"] for sc in m if per[sc]["feasible"]]
    rmem = [(s["candidate"], s["filter"], s["compressor"], s["P_set_Pa"]) for s in f8["members"]]
    pmem = [min(v["P_feasible"] for v in f8["mc"][k].values()) for k in rmem]
    F.append({"id": "F8-02", "evidence_class": "model-derived (quantified TPMC statistics only)", "finding":
              f"seeded TPMC Monte Carlo ({N_MC} draws per candidate and scenario): over the {len(pnom)} (survivor, "
              f"scenario) pairs that are nominally feasible, P_feasible ranges {rnd([min(pnom), max(pnom)])} "
              f"({sum(1 for x in pnom if x < 1.0)} pairs below 1: candidates at a domain or dead-head boundary); on "
              f"the robust Pareto members the minimum over scenarios is {rnd([min(pmem), max(pmem)]) if pmem else None}"
              ". The F1 statistical SEs are ~1e-4 relative (e.g. mdot_fwd SE / value), so the TBD surface-scenario "
              "set, not TPMC statistics, dominates robustness"})
    rel = [v["rel_change"] for d in f8["pointing"].values() for v in d.values() if v["rel_change"] is not None]
    flips = sum(1 for d in f8["pointing"].values() for v in d.values() if v["status_theta0"] != v["status_theta5"])
    F.append({"id": "F8-03", "evidence_class": "model-derived (frozen surface node)", "finding":
              f"pointing node theta = 5 deg (design state only): delivered-flow change {rnd([min(rel), max(rel)]) if rel else None}"
              f" on the robust members, {flips} status changes; the corner states have no theta node (NOT_EVALUATED)"})
    wl = Counter(v["n_scenarios_feasible"] for v in f8["wall"].values())
    F.append({"id": "F8-04", "evidence_class": "model-derived (uncited DB gamma prior)", "finding":
              f"wall-recombination case WALL-TI64-DB: robust members feasible in n of 10 scenarios {dict(sorted(wl.items()))}"})
    agg = Counter()
    for e in f8["elasticities"].values():
        for coef, v in e.items():
            agg[coef] = max(agg[coef], v["max_abs_elasticity"]["mdot_min"])
    top = [(k, rnd(v)) for k, v in agg.most_common(3)]
    F.append({"id": "F8-05", "evidence_class": "model-derived (local elasticity, no range implied)", "finding":
              f"largest |d ln mdot_delivered / d ln c| over the robust members: {top}; drag-channel coefficients "
              "(h, w, L, xi, R_rotor) have zero effect because every front design has N_drag = 0 (F3-01): closing "
              "tests on the turbo-row coefficients (compressor_downselect T-1 / T-2) matter most"})
    F.append({"id": "F8-06", "evidence_class": "inferred", "finding":
              f"evidence gates unchanged by the robust filter: {f8['gates_before'] == f8['gates_after']} (credible "
              f"Hall set {f8['gates_after']['hall_credible_set']}, A9.2 statuses verbatim, H-1 article "
              f"{f8['gates_after']['h1_article_freeze_state'].split(' ')[0]})"})
    return F


def robust_section(f8):
    rp = {}
    for P, b in f8["robust_pareto"].items():
        rp[str(P)] = {"n_all_scenario_feasible": b["n_all_scenario_feasible"],
                      "members": [rnd(m) for m in b["members"]]}
    mem = {}
    for s in f8["members"]:
        d = s["design_id"]
        k = (s["candidate"], s["filter"], s["compressor"], s["P_set_Pa"])
        mem[d] = {"tpmc_mc": rnd({sc: {kk: vv for kk, vv in v.items() if kk != "n"}
                                  for sc, v in sorted(f8["mc"][k].items())}),
                  "wall_TI64_DB": {"n_scenarios_feasible": f8["wall"][d]["n_scenarios_feasible"],
                                   "infeasible_in": f8["wall"][d]["infeasible_in"]},
                  "pointing_theta5_design_state": rnd(f8["pointing"][d]),
                  "compressor_elasticities": rnd(f8["elasticities"][d])}
    return {"rule": "candidates nominally feasible in EVERY surface scenario (fail closed), compared on worst-case "
                    "objectives over the scenario set plus the minimum TPMC P_feasible; per set pressure; a set, "
                    "never a winner; evidence-gate statuses unchanged (gate_snapshot before == after)",
            "objectives": {k: ro.ROBUST_SENSE[k] for k in ro.ROBUST_OBJECTIVES},
            "survivors": len(f8["survivors"]), "feasible_scenario_tiers": f8["tiers"],
            "all_scenario_feasible": len(f8["all_scenario_feasible"]), "robust_pareto_by_P_set": rp,
            "robust_members_detail": mem, "gates_before": f8["gates_before"], "gates_after": f8["gates_after"],
            "evidence_gates_unchanged": f8["gates_before"] == f8["gates_after"]}


def assemble(inp, blocks, pars, f7sum, totals, sysd, f8):
    _f4 = json.loads((REPO / "docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json").read_text(encoding="utf-8"))
    n_union = len(next(v["value"] for v in _f4["search_variables"] if v["id"] == "x_compressor"))
    _f3d = json.loads((REPO / "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json").read_text(encoding="utf-8"))
    _inv = {v: k for k, v in _f3d["reason_codes"].items()}
    _indep = {_inv[r] for r in ("ROTOR_MATERIAL_ALLOWABLE_TBD", "ROTOR_STRESS_ABOVE_CITED_ALLOWABLE_WITH_SAFETY_FACTOR",
                                "TIP_SPEED_ABOVE_PUBLISHED_TMP_PRACTICE")}
    n_gate = sum(1 for i, x in enumerate(_f3d["design_grid"]) if x["N_drag"] == 0 and x["rotor_material"] == "Ti6Al4V"
                 and all(not (set(c["status_by_design"][i].split(",")) & _indep) for c in _f3d["cases"].values()))
    lim = [
        "INT-01 (consolidated verification round 1): x_compressor is searched only over the union of the F3 per-case "
        f"Pareto ids ({n_union} designs, as in F4), and those F3 fronts were built on the down-selection envelope "
        "inlets, not on the F1-coupled states coupled here. F3's inlet-independent gates (N_drag = 0, Ti-6Al-4V, cited "
        f"tip speed <= 305.5 m/s) admit {n_gate} designs (A9.16: hub-ratio coverage included). Every F7 upstream "
        "Pareto set and the F8 robust set are therefore 'Pareto within the F3 front-union subset': the A9.7 "
        "consolidated-verification evidence for INT-01 (a re-run over the then 48 gate-passing designs) reported 9 of "
        "the 10 nominal contexts changing (members added, and some committed members dominated by an excluded design, "
        f"e.g. T4-A0-U2-D0). Searching all {n_gate} designs is an open follow-up; no set here is a Pareto set over the "
        "admissible compressor space",
        "every upstream number inherits PARAMETRIC_SENSITIVITY inputs: uncited DragCompressor coefficients (F3), "
        "parametric filter cases (F2/F4), the assumed isothermal 350 K chain (F4-P-01), the parametric leak (F4-P-05)",
        "steady operating points only in the F7 search; transient quality enters as the open-loop ripple transfer "
        "bound at the shaft frequency (F4-P-17); event-sequence transients are F4's study",
        "single-channel TPMC intake model with Maxwell / CLL kernels at frozen-surface nodes (F1 limitations)",
        "masses: proxies (intake wall area, plenum volume) where TBD; the compressor mass is the DragCompressor "
        "model's (code defaults), never a CBE",
        "probabilities only over the quantified TPMC statistics; scenario sets carry counts and worst cases only",
    ]
    exemplar = sysd.pop("exemplar")
    return {
        "schema": "f7_f8_optimizer_v1", "version": ao.VERSION, "lane": ao.LANE_KEY, "follow_on": ao.LANE,
        "directive": {"path": ao.DIRECTIVE, "json": PINNED[1], "sections": "F7 - Full coupled architecture optimizer; "
                      "F8 - Robust optimization"},
        "status": "INVESTIGATION_HYPOTHESIS",
        "deliverable_status": "UPSTREAM_PARETO_COMPUTED_UNDER_PARAMETRIC_INPUTS; FULL_SYSTEM_RANKING_REFUSED_INCOMPLETE "
                              "(not a design, not a selection, no winner, no PASS)",
        "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL,
        "modules": ["abep_sim/design/architecture_optimizer.py", "abep_sim/design/robust_optimizer.py"],
        "test": TEST_REL, "regenerate": f"python {SCRIPT_REL}  (verify: --check)",
        "companions": {"upstream_pareto": PARETO_NAME, "robust_candidates": ROBUST_NAME, "md": MD_NAME},
        "what_this_is_not": ["not an architecture selection, design, optimum, winner, requirement or PASS",
                             "not a Hall performance prediction (T, I_d, efficiency NOT_EVALUATED everywhere)",
                             "not a CBE: no mass or power number here is a current best estimate",
                             "not a model change: no existing module modified, nothing wired into archengine"],
        "pins": {p: sha256(p) for p in PINNED},
        "referenced_not_pinned": [{"path": p, "use": u, **({"identity": IDENTITY[p]} if p in IDENTITY else {})}
                                  for p, u in REFERENCED_NOT_PINNED],
        "items": parameters(),
        "design_vector": {"block_order": list(ao.BLOCK_ORDER), "block_states": list(ao.BLOCK_STATES),
                          "blocks": blocks},
        "upstream_objectives": [{"key": k, "sense": s, "units": u, "definition": d}
                                for k, s, u, d in ao.UPSTREAM_OBJECTIVES],
        "upstream_pareto_summary": f7sum,
        "upstream_status_totals": totals[0], "upstream_reason_totals": totals[1],
        "system_objectives": [{"key": k, "sense": s} for k, s in ao.SYSTEM_OBJECTIVES] +
                             [{"key": "life_material", "sense": "indicator"}],
        "hard_constraints": list(ao.HARD_CONSTRAINTS),
        "constraint_rule": "fail closed: NOT_EVALUATED never counts as satisfied; MET / VIOLATED carry the status "
                           "label of the value they used (parametric / synthetic values are labelled, never evidence)",
        "system_evaluation": rnd(sysd), "system_evaluation_exemplar": rnd(exemplar),
        "unlock_evidence": dict(ao.UNLOCK),
        "uq_axes": list(ro.UQ_AXES),
        "robust": robust_section(f8),
        "architecture_questions": ao.architecture_questions(),
        "tpmc_backend_policy": ao.tpmc_backend_policy(),
        "findings": findings(inp, f7sum, totals, sysd, f8, pars),
        "interface_demands": interface_demands(),
        "open_owner_questions": open_owner_questions(),
        "m16_impact": m16_impact(),
        "limitations": lim,
        "compliance": {"existing_modules_modified": False, "frozen_data_modified": False,
                       "wired_into_archengine": False, "tbd_converted_to_assumed_for_optimum": False,
                       "single_optimum_or_winner_declared": False, "pass_declared": False, "julia_used": False,
                       "tpmc_run": False, "deterministic": True, "new_pytest_skips": 0},
    }


def build():
    t0 = time.process_time()
    inp = ao.load_upstream_inputs(REPO)
    for p, ident in IDENTITY.items():
        d = ao.read_json(p, REPO)
        if d.get("schema") != ident and d.get("id") != ident:
            raise RuntimeError(f"identity check failed for {p}")
    blocks = ao.design_vector_blocks(REPO)
    ctxs, pars = stage_f7(inp)
    f7sum = pareto_summary(inp, pars)
    totals = reason_totals(pars)
    sysd = stage_system(inp, pars)
    f8 = stage_f8(inp, ctxs, pars)
    doc = rnd(assemble(inp, blocks, pars, f7sum, totals, sysd, f8))
    pareto = {"schema": "f7_upstream_pareto_v1", "generated_by": SCRIPT_REL, "companion": JSON_NAME,
              "label": ao.LABEL_PARAMETRIC, "columns": list(PARETO_COLS),
              "system_not_evaluated_codes": list(ao.SYSTEM_NOT_EVALUATED_CODES),
              "rule": "every member carries system_not_evaluated (the system objectives NOT_EVALUATED for it); "
                      "design_id = candidate|filter|compressor|V{V:g}|P{P_set:g} (filter and P_set from the context)",
              "contexts": pareto_rows(pars)}
    robust = {"schema": "f8_robust_candidates_v1", "generated_by": SCRIPT_REL, "companion": JSON_NAME,
              "label": ao.LABEL_PARAMETRIC, "n_mc": N_MC, "mc_columns": list(MC_COLS),
              "rule": "mc: per surface scenario, TPMC-statistics Monte Carlo (quantified uncertainty only); "
                      "worst_case: over all 10 scenarios, null unless nominally feasible in every one",
              "rows": robust_rows(f8)}
    return doc, pareto, robust, time.process_time() - t0


def dump(o) -> str:
    return json.dumps(o, indent=1, ensure_ascii=False) + "\n"


def dump_compact(o, key) -> str:
    """Large row arrays one per line (diff-friendly, small)."""
    head = {k: v for k, v in o.items() if k != key}
    lines = [json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in o[key]]
    body = json.dumps(head, indent=1, ensure_ascii=False)[:-2]
    return body + f',\n "{key}": [\n' + ",\n".join(lines) + "\n ]\n}\n"


def _f(x, n=4):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{n}g}"
    return str(x)


def render_md(doc: dict) -> str:
    L = [f"# A9.7 F7 / F8 - coupled architecture optimizer and robust optimization",
         "",
         f"Generated by `{doc['generated_by']}` from `{JSON_NAME}` (do not edit by hand). Status: "
         f"**{doc['status']}**. Deliverable: **{doc['deliverable_status']}**.",
         "",
         "What this is not: " + "; ".join(doc["what_this_is_not"]) + ".",
         "", "## Design vector", "",
         "| block | lane | state | variables |", "|---|---|---|---|"]
    for b in doc["design_vector"]["blocks"]:
        L.append(f"| {b['block']} | {b['lane']} | {b['state']} | {len(b['variables'])} |")
    L += ["", "## Findings", ""]
    for f in doc["findings"]:
        L.append(f"- **{f['id']}** ({f['evidence_class']}): {f['finding']}")
    L += ["", "## Upstream objectives (Pareto, PARAMETRIC_SENSITIVITY)", "", "| key | sense | units | definition |",
          "|---|---|---|---|"]
    for o in doc["upstream_objectives"]:
        L.append(f"| {o['key']} | {o['sense']} | {o['units']} | {o['definition']} |")
    L += ["", "## Upstream Pareto summary (nominal context: filter none, WALL-G0)", "",
          "| scenario | P_set [Pa] | evaluated | feasible | Pareto | frontier [mg/s] | >= 0.38 mg/s (coverage only) |",
          "|---|---|---|---|---|---|---|"]
    cols = doc["upstream_pareto_summary"]["columns"]
    for r in doc["upstream_pareto_summary"]["rows"]:
        d = dict(zip(cols, r))
        if d["filter"] == "F4-FIL-NONE" and d["wall"] == "WALL-G0" and d["n_feasible"]:
            L.append(f"| {d['scenario']} | {d['P_set_Pa']} | {d['n_evaluated']} | {d['n_feasible']} | {d['n_pareto']} | "
                     f"{_f(d['frontier_mdot_delivered_min_mgps'])} | {d['n_pareto_reaching_coverage_0.38_mgps']} |")
    L += ["", "## System objectives (every vector)", "", "| objective | status | reason | unlock |", "|---|---|---|---|"]
    for k, o in doc["system_evaluation_exemplar"]["objectives"].items():
        L.append(f"| {k} | {o['status']} | {o['reason']} | {' / '.join(o['unlock'] or [])} |")
    L += ["", "## Hard constraints (fail closed; exemplar vector)", "", "| id | RVM | rule | status | basis |",
          "|---|---|---|---|---|"]
    for c in doc["system_evaluation_exemplar"]["constraints"]:
        L.append(f"| {c['id']} | {c['rvm']} | {c['quantity']} {c['rule']} | {c['status']} | {c['basis']} |")
    L += ["", "## Full-system ranking", ""]
    for cfg, r in doc["system_evaluation"]["ranking"].items():
        L.append(f"- {cfg}: **{r['status']}** - {r.get('reason')} (missing counts {r.get('missing_counts')})")
    L += ["", "## F8 uncertainty axes", "", "| axis | treatment | quantified | basis |", "|---|---|---|---|"]
    for a in doc["uq_axes"]:
        L.append(f"| {a['axis']} | {a['treatment']} | {a['quantified']} | {a['basis']} |")
    rb = doc["robust"]
    L += ["", "## F8 robust Pareto filter", "", rb["rule"], "",
          f"Survivors {rb['survivors']}; feasible-scenario tiers {rb['feasible_scenario_tiers']}; feasible in all "
          f"scenarios {rb['all_scenario_feasible']}; evidence gates unchanged: {rb['evidence_gates_unchanged']}.", "",
          "| P_set [Pa] | design | worst mdot [mg/s] | worst drag [mN] | worst P_el [W] | m_comp [kg] | P_feas,min |",
          "|---|---|---|---|---|---|---|"]
    for P, b in rb["robust_pareto_by_P_set"].items():
        for m in b["members"]:
            L.append(f"| {P} | {m['design_id'].replace('|', ' / ')} | {_f(m['mdot_delivered_min_kgps'] * 1e6)} | "
                     f"{_f(m['drag_intake_max_N'] * 1e3)} | {_f(m['P_compressor_el_max_W'])} | "
                     f"{_f(m['m_compressor_max_kg'])} | {_f(m['P_feasible_tpmc_min'])} |")
    L += ["", "## Architecture questions", "", "| id | question | answer state | basis |", "|---|---|---|---|"]
    for q in doc["architecture_questions"]:
        L.append(f"| {q['id']} | {q['question']} | {q['answer_state']} | {q['basis']} |")
    L += ["", "## Minimal evidence that unlocks each NOT_EVALUATED objective", ""]
    for k, v in doc["unlock_evidence"].items():
        L.append(f"- **{k}**: {v}")
    L += ["", "## Interface demands", "", "| id | direction | counterpart | content | status |", "|---|---|---|---|---|"]
    for d in doc["interface_demands"]:
        L.append(f"| {d['id']} | {d['direction']} | {d['counterpart']} | {d['content']} | {d['status']} |")
    L += ["", "## Open owner questions (new)", ""]
    for q in doc["open_owner_questions"]:
        L.append(f"- **{q['id']}**: {q['question']} (needed for: {q['needed_for']})")
    L += ["", "## Limitations", ""] + [f"- {x}" for x in doc["limitations"]]
    L += ["", "## m16 impact", ""] + [f"- row {m['m16_row']} {m['key']}: {m['state_change']}" for m in doc["m16_impact"]]
    return "\n".join(L) + "\n"


def check_pins(doc_on_disk: dict) -> list:
    return [p for p, h in doc_on_disk.get("pins", {}).items() if not (REPO / p).exists() or sha256(p) != h]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the committed outputs are reproduced")
    a = ap.parse_args(argv)
    doc, pareto, robust, cpu = build()
    texts = {JSON_NAME: dump(doc), PARETO_NAME: dump_compact(pareto, "contexts"),
             ROBUST_NAME: dump_compact(robust, "rows"), MD_NAME: render_md(doc)}
    out = REPO / OUT_DIR_REL
    print(f"build CPU {cpu:.1f} s")
    if a.check:
        ok = True
        for name, text in texts.items():
            if not (out / name).exists() or (out / name).read_text(encoding="utf-8") != text:
                print(f"MISMATCH: {name}")
                ok = False
        if ok:
            bad = check_pins(json.loads((out / JSON_NAME).read_text(encoding="utf-8")))
            if bad:
                print(f"PIN MISMATCH: {bad}")
                ok = False
        print("OK" if ok else "rerun the builder")
        return 0 if ok else 1
    out.mkdir(parents=True, exist_ok=True)
    for name, text in texts.items():
        (out / name).write_text(text, encoding="utf-8")
    print(f"wrote {OUT_DIR_REL}/" + ", ".join(texts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
