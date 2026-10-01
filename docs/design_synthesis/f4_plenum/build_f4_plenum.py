#!/usr/bin/env python3
"""A9.7 F4 plenum / feed synthesis study (follow-on fo_a9_7_f4_plenum_feed).

Runs abep_sim/design/plenum_feed.py on the committed F1 IF-A1 records (every candidate x area x surface scenario x
orbit state), the F2 filter cases ('none' plus labelled parametric cases), the F3 compressor set (union of the F3
per-case Pareto fronts) and a plenum / feed-control search, and writes

  f4_plenum_feed_v1.json     parameters, requirement sweep, steady feasibility regions, transient study, Pareto sets
                             (infeasible points kept with reasons), sensitivities, checks, findings, interface demands,
                             open owner questions, m16_impact
  f4_plenum_chains_v1.json   chain-level steady table (filter none): best deliverable flow vs P_req per chain
  F4_PLENUM_FEED.md          generated from the JSON

What it is not: a plenum design, a valve specification, a selected requirement, a winner, a PASS or a model change.
No existing module is modified; nothing is wired into archengine; goldens cannot move. Deterministic (no random
numbers), no Julia; a few minutes of CPU.

Usage:
  python docs/design_synthesis/f4_plenum/build_f4_plenum.py           # (re)write outputs
  python docs/design_synthesis/f4_plenum/build_f4_plenum.py --check   # exit 1 unless reproduced and pins hold
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

from abep_sim.design import plenum_feed as pf  # noqa: E402
from abep_sim.materials import DB  # noqa: E402
from abep_sim.reservoir import size_orifice_for_pressure  # noqa: E402

OUT_DIR_REL = "docs/design_synthesis/f4_plenum"
SCRIPT_REL = f"{OUT_DIR_REL}/build_f4_plenum.py"
JSON_NAME = "f4_plenum_feed_v1.json"
CHAINS_NAME = "f4_plenum_chains_v1.json"
TRANSIENTS_NAME = "f4_plenum_transients_v1.json"
MD_NAME = "F4_PLENUM_FEED.md"
TEST_REL = "tests/test_design_f4_plenum.py"
BASE_COMMIT = "de6bb89a208c66a41cc57757772b2dece69a2d53"
SIG = 8

F1_REL = "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json"
F3_REL = "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json"
F3D_REL = "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json"
F5_REL = "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json"
H23_REL = "docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json"
PINNED = (
    "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md",
    "docs/decisions/OD_2026_10_01_A9_7_architecture_freeze_design_synthesis.json",
    "docs/decisions/OD_2026_09_29_owner_answers_147.json",
    F1_REL, F3_REL, F3D_REL, F5_REL, H23_REL,
)
REFERENCED_NOT_PINNED = (
    ("abep_sim/design/plenum_feed.py", "the F4 module"),
    ("abep_sim/design/intake_synthesis.py", "F1 producer of the IF-A1 records (read through the committed JSON)"),
    ("abep_sim/design/filter_stage.py", "F2 FilterStage / SensitivityCase (called)"),
    ("abep_sim/design/compressor_synthesis.py", "F3 constants (domain cap, Kn, cross sections) and module defaults"),
    ("abep_sim/compressor.py", "DragCompressor (instantiated; characteristic mirrored and cross-checked)"),
    ("abep_sim/reservoir.py", "Reservoir.conductance, wall recombination, leak path, size_orifice_for_pressure"),
    ("abep_sim/materials.py", "gamma_O(T), T_max_K (uncited priors)"),
    ("abep_sim/constants.py", "K_B, M_SPECIES, MU_EARTH, R_EARTH"),
    ("docs/interfaces/UPSTREAM_ICD.md", "IF-A2..IF-A5, gaps G-04, G-05, G-06, G-07, G-09"),
    ("docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json", "rows 4 buffer_plenum, 5 metering valve"),
)

# ----------------------------------------------------------------------------------------------------- study grid
TARGETS_PA = (0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 1.0, 10.0)
MDOT_REQ_MGPS = (0.03, 0.1, 0.2, 0.38, 0.6, 1.0, 1.3, 2.0, 3.2)
VOLUMES_M3 = (1e-3, 1e-2, 1e-1)
KP = (0.3, 3.0)
TI_S = (0.3, 3.0)
F_VALVE_NOMINAL_HZ = 1.0
F_VALVE_SENSITIVITY_HZ = (0.1, 10.0)
AUTHORITY = 3.0
ORBIT_AMPLITUDES = (0.1, 0.2)
PARAM_FILTER_TAUS = (0.9, 0.7, 0.5)
V_STEADY_REF = 1e-2
TRANSIENT_WALL = "WALL-G0"          # owner H1F-IN-02 "inert / low-recombination lining": the gamma = 0 bound
SENS_CAP = 24
ORBIT_VERIFY_CAP = 3
CONVERGENCE_CAP = 4
SIZE_ORIFICE_BRACKET_M2 = (1e-8, 3e-2)   # reservoir.size_orifice_for_pressure lo, hi (read from its source)


def sha256(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def rnd(x, sig=SIG):
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        x = float(x)
        if not math.isfinite(x):
            return None if math.isnan(x) else ("inf" if x > 0 else "-inf")
        return float(f"{x:.{sig}g}")
    if isinstance(x, dict):
        return {str(k): rnd(v, sig) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v, sig) for v in x]
    if isinstance(x, np.ndarray):
        return [rnd(v, sig) for v in x.tolist()]
    return x


def mg(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else x * 1e6


# ----------------------------------------------------------------------------------------------------- inputs
def load_inputs():
    f1 = pf.load_f1(REPO)
    areas = tuple(float(a) for a in f1["design_space"]["variables"]["area_m2"])
    states = tuple(f1["coverage_rule"]["orbit_states"])
    scenarios = tuple(f1["pareto"]["envelope"].keys())
    recs = pf.load_f1_records(f1, areas)
    order = {s: i for i, s in enumerate(states)}
    recs.sort(key=lambda r: (scenarios.index(r.scenario), r.candidate, order[r.state]))
    groups = []
    for i in range(0, len(recs), len(states)):
        g = recs[i:i + len(states)]
        if [r.state for r in g] != list(states) or len({(r.candidate, r.scenario) for r in g}) != 1:
            raise RuntimeError("F1 records do not form complete state groups")
        groups.append((g[0].candidate, g[0].scenario))
    s3 = json.loads((REPO / F3_REL).read_text())
    d3 = json.loads((REPO / F3D_REL).read_text())
    ids = sorted({i for c in s3["cases"] for i in c["pareto_ids"]})
    grid = {x["id"]: x for x in d3["design_grid"]}
    plants = [pf.CompressorPlant.from_design(grid[i]) for i in ids]
    filters = [pf.filter_none()] + [pf.filter_parametric(t) for t in PARAM_FILTER_TAUS] + [pf.filter_placeholder()]
    return {"f1": f1, "areas": areas, "states": states, "scenarios": scenarios, "recs": recs, "groups": groups,
            "plants": plants, "filters": filters, "f3_ids": ids}


def leak_area() -> float:
    return pf.RES_DEFAULTS["leak_area_m2"]


def walls() -> dict:
    return {"WALL-G0": 0.0, "WALL-TI64-DB": DB["Ti6Al4V"].gamma_O(pf.T_CHAIN_K)}


# ----------------------------------------------------------------------------------------------------- stage A
def group_reduce(sw: dict, n_states: int) -> dict:
    """Per (candidate, scenario) group: all-state feasibility and min-over-states flow per target, then the best
    deliverable flow for every P_req (max over admissible P_set >= P_req on the target grid)."""
    bits = sw["bits"].reshape(-1, n_states, len(TARGETS_PA))
    md = sw["mdot_total_kgps"].reshape(-1, n_states, len(TARGETS_PA))
    pel = sw["P_el_W"].reshape(-1, n_states, len(TARGETS_PA))
    xo = sw["x_s_flow_mole"]["O"].reshape(-1, n_states, len(TARGETS_PA))
    ok5 = (bits == 0).all(axis=1)
    md5 = np.where(ok5, np.nanmin(np.where(bits == 0, md, np.inf), axis=1), np.nan)
    pel5 = np.where(ok5, np.nanmax(np.where(bits == 0, pel, -np.inf), axis=1), np.nan)
    xo_lo = np.where(ok5, np.nanmin(np.where(bits == 0, xo, np.inf), axis=1), np.nan)
    xo_hi = np.where(ok5, np.nanmax(np.where(bits == 0, xo, -np.inf), axis=1), np.nan)
    nT = len(TARGETS_PA)
    best = np.full(md5.shape, np.nan)
    arg = np.full(md5.shape, -1, dtype=int)
    for i in range(nT):
        sub = md5[:, i:]
        has = np.isfinite(sub).any(axis=1)
        k = np.where(has, np.nanargmax(np.where(np.isfinite(sub), sub, -np.inf), axis=1), -1)
        best[:, i] = np.where(has, sub[np.arange(len(sub)), np.maximum(k, 0)], np.nan)
        arg[:, i] = np.where(has, k + i, -1)
    # scheduled setpoint: each orbit state may use its own admissible P_set >= P_req (the setpoint follows the slowly
    # varying orbit state); deliverable flow = min over states of the per-state best
    okm = np.where(bits == 0, md, np.nan)
    sched = np.full(md5.shape, np.nan)
    for i in range(nT):
        sub = okm[:, :, i:]
        with np.errstate(all="ignore"):
            per_state = np.where(np.isfinite(sub).any(axis=2), np.nanmax(np.where(np.isfinite(sub), sub, -np.inf),
                                                                          axis=2), np.nan)
        sched[:, i] = np.where(np.isfinite(per_state).all(axis=1), np.min(per_state, axis=1), np.nan)
    return {"bits": bits, "ok5": ok5, "md5": md5, "pel5": pel5, "best": best, "arg": arg, "xo_lo": xo_lo,
            "xo_hi": xo_hi, "md": md, "sched": sched}


def stage_steady(inp: dict) -> dict:
    recs, plants, filters = inp["recs"], inp["plants"], inp["filters"]
    nS = len(inp["states"])
    f1_ok = np.array([r.f1_status == "FEASIBLE_AT_STATE" for r in recs])
    gam = walls()
    cases = [(f, "WALL-G0", V_STEADY_REF) for f in filters] + \
            [(filters[0], "WALL-TI64-DB", V) for V in VOLUMES_M3]
    out = {}
    for filt, wall, V in cases:
        side = pf.intake_side(recs, filt)
        pl = pf.Plenum(V, gam[wall], wall, leak_area())
        per_comp = {}
        for pc in plants:
            sw = pf.steady_sweep(side, pc, pl, TARGETS_PA, f1_ok)
            red = group_reduce(sw, nS)
            red["comp_mass"] = sw["m_compressor_kg"].reshape(-1, nS, len(TARGETS_PA))
            per_comp[pc.design_id] = red
        out[(filt.case_id, wall, V)] = per_comp
    return out


def aggregate_steady(inp: dict, st: dict) -> dict:
    groups, scenarios = inp["groups"], inp["scenarios"]
    gidx = {sc: [i for i, g in enumerate(groups) if g[1] == sc] for sc in scenarios}
    res = {}
    for (fid, wall, V), per_comp in st.items():
        key = f"{fid}|{wall}|V{V:g}"
        fr = {}
        hist = Counter()
        for comp, red in per_comp.items():
            b = red["bits"]
            for k in range(len(TARGETS_PA)):
                vals, cnts = np.unique(b[:, :, k], return_counts=True)
                for v, c in zip(vals, cnts):
                    for r in (pf.reasons_from_bits(int(v)) or ["FEASIBLE_POINT_NO_REASON"]):
                        hist[(TARGETS_PA[k], r)] += int(c)
        for sc in scenarios:
            rows = gidx[sc]
            frontier = []
            for i, preq in enumerate(TARGETS_PA):
                best_v, best_id = -1.0, None
                counts = [0] * len(MDOT_REQ_MGPS)
                n_any = 0
                for comp, red in per_comp.items():
                    bv = red["best"][rows, i]
                    for gi, v in zip(rows, bv):
                        if not np.isfinite(v):
                            continue
                        n_any += 1
                        for j, req in enumerate(MDOT_REQ_MGPS):
                            if v * 1e6 >= req:
                                counts[j] += 1
                        if v > best_v:
                            k = int(red["arg"][gi, i])
                            best_v, best_id = v, {"candidate": groups[gi][0], "compressor": comp,
                                                  "P_set_Pa": TARGETS_PA[k],
                                                  "P_compressor_el_max_W": float(red["pel5"][gi, k]),
                                                  "xO_flow_range": [float(red["xo_lo"][gi, k]), float(red["xo_hi"][gi, k])]}
                sbest, sid, scounts, s_any = -1.0, None, [0] * len(MDOT_REQ_MGPS), 0
                for comp, red in per_comp.items():
                    for gi, v in zip(rows, red["sched"][rows, i]):
                        if not np.isfinite(v):
                            continue
                        s_any += 1
                        for j, req in enumerate(MDOT_REQ_MGPS):
                            if v * 1e6 >= req:
                                scounts[j] += 1
                        if v > sbest:
                            sbest, sid = v, {"candidate": groups[gi][0], "compressor": comp}
                frontier.append({"P_req_Pa": preq, "frontier_mdot_mgps": mg(best_v) if best_id else None,
                                 "attained_by": best_id, "n_chains_all_state_feasible": n_any,
                                 "n_chains_meeting_mdot_req": dict(zip([str(x) for x in MDOT_REQ_MGPS], counts)),
                                 "scheduled_setpoint": {
                                     "frontier_mdot_mgps": mg(sbest) if sid else None, "attained_by": sid,
                                     "n_chains_all_state_feasible": s_any,
                                     "n_chains_meeting_mdot_req": dict(zip([str(x) for x in MDOT_REQ_MGPS], scounts))}})
            fr[sc] = frontier
        res[key] = {"filter": fid, "wall": wall, "V_m3": V, "per_scenario": fr,
                    "reason_histogram": [{"target_Pa": t, "reason": r, "count": c}
                                         for (t, r), c in sorted(hist.items(), key=lambda x: (x[0][0], x[0][1]))]}
    return res


def per_state_frontier(inp: dict, st: dict) -> dict:
    """Filter none, WALL-G0: single-state best flow per target (which orbit states bind)."""
    per_comp = st[("F4-FIL-NONE", "WALL-G0", V_STEADY_REF)]
    groups, states = inp["groups"], inp["states"]
    out = {}
    for sc in inp["scenarios"]:
        rows = [i for i, g in enumerate(groups) if g[1] == sc]
        d = {}
        for si, stn in enumerate(states):
            vals = []
            for k in range(len(TARGETS_PA)):
                best = np.nan
                for red in per_comp.values():
                    m = red["md"][rows, si, k]
                    ok = red["bits"][rows, si, k] == 0
                    if ok.any():
                        best = np.nanmax([best, np.nanmax(np.where(ok, m, np.nan))])
                vals.append(mg(best) if np.isfinite(best) else None)
            d[stn] = vals
        out[sc] = d
    return out


def chain_table(inp: dict, st: dict, key) -> dict:
    per_comp = st[key]
    rows = []
    for comp, red in per_comp.items():
        for gi, (cand, sc) in enumerate(inp["groups"]):
            best = red["best"][gi]
            if not np.isfinite(best).any():
                continue
            rows.append([cand, sc, comp] + [mg(v) if np.isfinite(v) else None for v in best] +
                        [[TARGETS_PA[int(k)] if k >= 0 else None for k in red["arg"][gi]]])
    rows.sort(key=lambda r: (r[1], r[0], r[2]))
    return {"filter": key[0], "wall": key[1], "V_m3": key[2],
            "columns": ["candidate", "scenario", "compressor"] + [f"best_mdot_mgps_at_P_req_{p:g}" for p in TARGETS_PA]
                       + ["P_set_used_per_P_req"],
            "rows_with_any_feasible_P_req": rows}


# ----------------------------------------------------------------------------------------------------- stage B
def nondominated(items, keys):
    """items: list of (id, {k: value}); keys: [(k, 'max'|'min')]. Weak dominance; ties all kept."""
    out = []
    for i, (a, va) in enumerate(items):
        dom = False
        for j, (b, vb) in enumerate(items):
            if i == j:
                continue
            ge = all((vb[k] >= va[k]) if s == "max" else (vb[k] <= va[k]) for k, s in keys)
            gt = any((vb[k] > va[k]) if s == "max" else (vb[k] < va[k]) for k, s in keys)
            if ge and gt:
                dom = True
                break
        if not dom:
            out.append(a)
    return out


def transient_basis(inp: dict, st: dict, steady_agg: dict) -> dict:
    """Rule: (1) scenarios = the F1 surface scenarios with the lowest and the highest maximum frontier flow (filter none,
    WALL-G0, single setpoint); (2) per basis scenario and in-domain P_set with all-state-feasible chains (filter none,
    TRANSIENT_WALL): the chains non-dominated over the F4 steady objectives (min-over-states delivered flow max,
    compressor electrical power min, compressor mass min); intake area / mass / drag stay F1 objectives; (3) the orbit
    check (orbit_quasi_static) at every amplitude; chains failing it at the SMALLEST amplitude are infeasible at every
    amplitude evaluated and are not simulated (kept with their reasons). Steady-dominated chains are not transient-
    evaluated (counted, reason STEADY_DOMINATED_NOT_TRANSIENT_EVALUATED)."""
    key = f"F4-FIL-NONE|WALL-G0|V{V_STEADY_REF:g}"
    peak = {}
    for sc, fr in steady_agg[key]["per_scenario"].items():
        vals = [x["frontier_mdot_mgps"] for x in fr if x["frontier_mdot_mgps"] is not None]
        peak[sc] = max(vals) if vals else -1.0
    order = sorted(peak, key=lambda s: (peak[s], s))
    basis_sc = [order[0], order[-1]] if order[0] != order[-1] else [order[0]]
    per_comp = st[("F4-FIL-NONE", TRANSIENT_WALL, V_STEADY_REF)]
    groups = inp["groups"]
    by = {(r.candidate, r.scenario, r.state): r for r in inp["recs"]}
    plants = {p.design_id: p for p in inp["plants"]}
    filt = inp["filters"][0]
    pl = pf.Plenum(V_STEADY_REF, walls()[TRANSIENT_WALL], TRANSIENT_WALL, leak_area())
    leak = {s: pl.leak_m3_s(s) for s in pf.SPECIES}
    fc = {s: pl.feed_c(s) for s in pf.SPECIES}
    contexts = []
    for sc in basis_sc:
        rows = [i for i, g in enumerate(groups) if g[1] == sc]
        for k, P in enumerate(TARGETS_PA):
            if P > pf.P_DOMAIN_PA:
                continue
            items = []
            for comp, red in per_comp.items():
                for gi in rows:
                    if red["ok5"][gi, k]:
                        items.append((f"{groups[gi][0]}|{comp}",
                                      {"mdot": float(red["md5"][gi, k]), "pel": float(red["pel5"][gi, k]),
                                       "mass": float(np.nanmax(red["comp_mass"][gi, :, k]))}))
            if not items:
                continue
            nd = sorted(nondominated(items, [("mdot", "max"), ("pel", "min"), ("mass", "min")]))
            orbit = {}
            for chain_id in nd:
                cand, comp = chain_id.split("|")
                design = by[(cand, sc, inp["states"][0])]
                states = [by[(cand, sc, s)] for s in inp["states"]]
                co = pf.Chain(design, filt, plants[comp], pl).node_coefficients()
                a, _, _, _ = pf.area_for_pressure(co, P, pl.k_rec_m3_s(), leak, fc)
                orbit[chain_id] = {str(amp): pf.orbit_quasi_static(filt, plants[comp], pl, states, P, amp,
                                                                     AUTHORITY * float(a))
                                   for amp in ORBIT_AMPLITUDES}
            amin = str(min(ORBIT_AMPLITUDES))
            sim = [c for c in nd if not orbit[c][amin]["reasons"]]
            contexts.append({"scenario": sc, "P_set_Pa": P, "n_all_state_feasible_chains": len(items),
                             "steady_nondominated": nd,
                             "steady_dominated_not_transient_evaluated": len(items) - len(nd),
                             "orbit_check": orbit, "simulated_chains": sim,
                             "not_simulated_orbit_infeasible_at_smallest_amplitude": [c for c in nd if c not in sim]})
    return {"rule": " ".join(transient_basis.__doc__.split()), "scenario_peak_frontier_mgps": peak,
            "basis_scenarios": basis_sc, "contexts": contexts}


def stage_transient(inp: dict, basis: dict) -> dict:
    recs = inp["recs"]
    by = {(r.candidate, r.scenario, r.state): r for r in recs}
    plants = {p.design_id: p for p in inp["plants"]}
    filt = inp["filters"][0]
    gam = walls()[TRANSIENT_WALL]
    design_state = inp["states"][0]
    rows = []
    for ctx in basis["contexts"]:
        sc, P = ctx["scenario"], ctx["P_set_Pa"]
        for chain_id in ctx["steady_nondominated"]:
            cand, comp = chain_id.split("|")
            oc = ctx["orbit_check"][chain_id]
            if chain_id not in ctx["simulated_chains"]:
                per_amp = {amp: {"status": pf.status_from_reasons(oc[amp]["reasons"]), "reasons": oc[amp]["reasons"]}
                           for amp in oc}
                rows.append({"id": f"{sc}|P{P:g}|{chain_id}|NOT_SIMULATED", "scenario": sc, "P_set_Pa": P,
                             "candidate": cand, "compressor": comp, "V_m3": None, "controller": None,
                             "event_sequence_status": "NOT_SIMULATED_ORBIT_INFEASIBLE_AT_SMALLEST_AMPLITUDE",
                             "event_sequence_reasons": [], "by_orbit_amplitude": per_amp, "objectives": None,
                             "summary": None, "events": []})
                continue
            plant = plants[comp]
            design = by[(cand, sc, design_state)]
            for V in VOLUMES_M3:
                pl = pf.Plenum(V, gam, TRANSIENT_WALL, leak_area())
                for Kp in KP:
                    for Ti in TI_S:
                        ctrl = pf.Controller(Kp, Ti, F_VALVE_NOMINAL_HZ, AUTHORITY)
                        r = pf.transient_case(filt, plant, pl, ctrl, design, P, None)
                        base = r["reasons"]
                        per_amp = {}
                        for amp in oc:
                            rs = sorted(set(base + oc[amp]["reasons"]), key=pf.REASONS.index)
                            per_amp[amp] = {"status": pf.status_from_reasons(rs), "reasons": rs}
                        rows.append({"id": f"{sc}|P{P:g}|{chain_id}|V{V:g}|{ctrl.id}", "scenario": sc,
                                     "P_set_Pa": P, "candidate": cand, "compressor": comp, "V_m3": V,
                                     "controller": {"Kp": Kp, "Ti_s": Ti, "f_valve_hz": F_VALVE_NOMINAL_HZ,
                                                    "authority": AUTHORITY},
                                     "event_sequence_status": r["status"], "event_sequence_reasons": base,
                                     "by_orbit_amplitude": per_amp, "objectives": r["objectives"],
                                     "summary": r["summary"],
                                     "events": [{k: m[k] for k in EVENT_KEYS} for m in r["metrics"]]})
    return {"rows": rows}


EVENT_KEYS = ("event", "settling_time_s", "flow_recovery_s", "overshoot_frac", "peak_deviation_frac", "valve_travel",
              "P_min_Pa", "P_max_Pa", "mdot_min_kgps", "mdot_max_kgps", "xO_min", "xO_max", "saturated_end")


def pareto_sets(tr: dict) -> list:
    out = []
    ctx = sorted({(r["scenario"], r["P_set_Pa"]) for r in tr["rows"]})
    for sc, P in ctx:
        rr = [r for r in tr["rows"] if r["scenario"] == sc and r["P_set_Pa"] == P]
        for amp in ORBIT_AMPLITUDES:
            rows = [{"id": r["id"], "status": r["by_orbit_amplitude"][str(amp)]["status"],
                     "objectives": r["objectives"]} for r in rr]
            ids = pf.pareto_ids(rows, pf.OBJECTIVES)
            counts = Counter(r["status"] for r in rows)
            reasons = Counter(x for r in rr for x in r["by_orbit_amplitude"][str(amp)]["reasons"])
            out.append({"scenario": sc, "P_set_Pa": P, "orbit_amplitude": amp, "n_evaluated": len(rows),
                        "status_counts": dict(sorted(counts.items())), "reason_counts": dict(sorted(reasons.items())),
                        "pareto_ids": ids})
    return out


def stage_sensitivity(inp: dict, tr: dict, par: list) -> list:
    """Valve-bandwidth sensitivity (F4-P-08 TBD): re-run Pareto members (orbit amplitude 0.2) at 0.1 and 10 Hz."""
    recs = inp["recs"]
    by = {(r.candidate, r.scenario, r.state): r for r in recs}
    plants = {p.design_id: p for p in inp["plants"]}
    rowmap = {r["id"]: r for r in tr["rows"]}
    ids = []
    for p in par:
        if p["orbit_amplitude"] == max(ORBIT_AMPLITUDES):
            ids += p["pareto_ids"]
    ids = sorted(set(ids))[:SENS_CAP]
    gam = walls()[TRANSIENT_WALL]
    out = []
    for rid in ids:
        r = rowmap[rid]
        pl = pf.Plenum(r["V_m3"], gam, TRANSIENT_WALL, leak_area())
        design = by[(r["candidate"], r["scenario"], inp["states"][0])]
        res = {}
        for fv in F_VALVE_SENSITIVITY_HZ:
            ctrl = pf.Controller(r["controller"]["Kp"], r["controller"]["Ti_s"], fv, AUTHORITY)
            x = pf.transient_case(inp["filters"][0], plants[r["compressor"]], pl, ctrl, design, r["P_set_Pa"], None)
            res[str(fv)] = {"status": x["status"], "reasons": x["reasons"],
                            "settling_max_s": x["objectives"]["settling_max_s"] if x["objectives"] else None,
                            "peak_deviation_max": x["objectives"]["peak_deviation_max"] if x["objectives"] else None,
                            "valve_travel": x["objectives"]["valve_travel"] if x["objectives"] else None}
        out.append({"id": rid, "nominal_f_valve_hz": F_VALVE_NOMINAL_HZ,
                    "nominal": {"status": r["event_sequence_status"],
                                "settling_max_s": r["objectives"]["settling_max_s"],
                                "peak_deviation_max": r["objectives"]["peak_deviation_max"],
                                "valve_travel": r["objectives"]["valve_travel"]},
                    "by_f_valve_hz": res})
    return out


def stage_orbit_verification(inp: dict, basis: dict) -> list:
    """Verify the quasi-static orbit check against the full transient (one orbital period, solve_ivp) on up to
    ORBIT_VERIFY_CAP chain-states that pass the largest amplitude (first in deterministic order)."""
    by = {(r.candidate, r.scenario, r.state): r for r in inp["recs"]}
    plants = {p.design_id: p for p in inp["plants"]}
    gam = walls()[TRANSIENT_WALL]
    amp = max(ORBIT_AMPLITUDES)
    out = []
    for ctx in basis["contexts"]:
        for chain_id in ctx["simulated_chains"]:
            if len(out) >= ORBIT_VERIFY_CAP:
                return out
            rows = [x for x in ctx["orbit_check"][chain_id][str(amp)]["rows"] if not x["reasons"]]
            if not rows:
                continue
            cand, comp = chain_id.split("|")
            pl = pf.Plenum(V_STEADY_REF, gam, TRANSIENT_WALL, leak_area())
            ctrl = pf.Controller(KP[0], TI_S[0], F_VALVE_NOMINAL_HZ, AUTHORITY)
            design = by[(cand, ctx["scenario"], inp["states"][0])]
            q = rows[0]
            stt = by[(cand, ctx["scenario"], q["state"])]
            sim = pf.orbit_simulated(inp["filters"][0], plants[comp], pl, ctrl, design, stt, ctx["P_set_Pa"], amp)
            if not sim["ok"]:
                out.append({"chain": chain_id, "scenario": ctx["scenario"], "P_set_Pa": ctx["P_set_Pa"],
                            "state": q["state"], "simulated": sim})
                continue
            out.append({"scenario": ctx["scenario"], "P_set_Pa": ctx["P_set_Pa"], "chain": chain_id,
                        "V_m3": V_STEADY_REF, "state": q["state"], "controller": ctrl.id, "amplitude": amp,
                        "quasi_static": {"mdot_min_kgps": q["mdot_min_kgps"], "mdot_max_kgps": q["mdot_max_kgps"]},
                        "simulated": sim,
                        "rel_diff_mdot_min": abs(sim["mdot_min_kgps"] / q["mdot_min_kgps"] - 1.0),
                        "rel_diff_mdot_max": abs(sim["mdot_max_kgps"] / q["mdot_max_kgps"] - 1.0)})
    return out


def stage_convergence(inp: dict, tr: dict) -> list:
    """Numerical convergence (CLAUDE.md gate 5 style): the first CONVERGENCE_CAP simulated rows re-run at
    RTOL_REFERENCE; status and objective differences reported."""
    by = {(r.candidate, r.scenario, r.state): r for r in inp["recs"]}
    plants = {p.design_id: p for p in inp["plants"]}
    gam = walls()[TRANSIENT_WALL]
    out = []
    for r in [x for x in tr["rows"] if x["objectives"] is not None][:CONVERGENCE_CAP]:
        pl = pf.Plenum(r["V_m3"], gam, TRANSIENT_WALL, leak_area())
        ctrl = pf.Controller(r["controller"]["Kp"], r["controller"]["Ti_s"], F_VALVE_NOMINAL_HZ, AUTHORITY)
        design = by[(r["candidate"], r["scenario"], inp["states"][0])]
        x = pf.transient_case(inp["filters"][0], plants[r["compressor"]], pl, ctrl, design, r["P_set_Pa"], None,
                              rtol=pf.RTOL_REFERENCE, method=pf.INTEGRATOR_REFERENCE)
        diffs = {}
        for k in ("settling_max_s", "peak_deviation_max", "valve_travel"):
            a, b = r["objectives"][k], x["objectives"][k]
            diffs[k] = None if a is None or b is None else abs(a / b - 1.0) if b else abs(a - b)
        out.append({"id": r["id"], "status_rtol": r["event_sequence_status"], "status_reference": x["status"],
                    "same_status": r["event_sequence_status"] == x["status"], "rel_diff": diffs,
                    "method": pf.INTEGRATOR_METHOD, "rtol": pf.RTOL, "reference_method": pf.INTEGRATOR_REFERENCE,
                    "rtol_reference": pf.RTOL_REFERENCE})
    return out


# ----------------------------------------------------------------------------------------------------- checks
def stage_checks(inp: dict) -> dict:
    """Cross-checks against the called modules at one feasible operating point (filter none, WALL-TI64-DB)."""
    recs = inp["recs"]
    plants = inp["plants"]
    gam = walls()["WALL-TI64-DB"]
    pl = pf.Plenum(V_STEADY_REF, gam, "WALL-TI64-DB", leak_area())
    found = None
    for r in recs:
        if r.state != inp["states"][0] or r.f1_status != "FEASIBLE_AT_STATE":
            continue
        for pc in plants:
            ch = pf.Chain(r, inp["filters"][0], pc, pl)
            for P in (0.01, 0.02, 0.005):
                op = pf.steady_operating_point(ch, P)
                # inside the size_orifice_for_pressure bracket [1e-8, 3e-2] m^2 (outside it that routine returns a
                # bracket end with no flag: ICD G-05)
                if op["status"] == pf.ST_FEASIBLE and op["a_eq_m2"] < SIZE_ORIFICE_BRACKET_M2[1]:
                    found = (ch, P, op)
                    break
            if found:
                break
        if found:
            break
    ch, P, op = found
    # (1) Reservoir.steady_state with the compressor net inflow reproduces the plenum pressure and species flows
    res = pl.reservoir(op["a_eq_m2"])
    mdot_in = {s: op["mdot_compressor_gross_kgps"][s] - op["mdot_compressor_backleak_kgps"][s] for s in pf.SPECIES}
    rs = res.steady_state(mdot_in)
    c1 = abs(rs["p_total_Pa"] / P - 1.0)
    c1b = max(abs(rs["mdot_anode"][s] / op["offered"]["mdot_s_kgps"][s] - 1.0) for s in pf.SPECIES)
    # (2) size_orifice_for_pressure (bisection in [1e-8, 3e-2] m^2, 60 steps, no residual returned: ICD G-05)
    res2 = pl.reservoir(1e-6)
    a2 = size_orifice_for_pressure(res2, mdot_in, P)
    c2 = abs(a2 / op["a_eq_m2"] - 1.0)
    # (3) cascade mirror vs DragCompressor._run_once at the module convention (p_in split by number flow)
    pc = ch.plant
    through = op["mdot_compressor_gross_kgps"]
    p_in = op["compressor_inlet_P_Pa"]
    r1 = pc.comp._run_once(p_in, dict(through))
    nflow = {s: through[s] / pf.M_SPECIES[s] for s in pf.SPECIES}
    ntot = sum(nflow.values())
    p_conv = {s: p_in * nflow[s] / ntot for s in pf.SPECIES}
    Q = {s: through[s] / pf.M_SPECIES[s] * pf.K_B * pc.comp.T_gas_K for s in pf.SPECIES}
    cas = pc.cascade(p_conv, Q)
    c3 = max(abs(cas["p_out_total"] / r1["p_out_Pa"] - 1.0), abs(cas["P_el_W"] / r1["P_el_W"] - 1.0),
             abs(cas["mass_kg"] / r1["mass_kg"] - 1.0), abs(cas["T_comp_K"] / r1["T_comp_K"] - 1.0))
    # (4) F1 law reproduction for the 'none' filter: dead-head with the compressor replaced by an ideal closed wall
    it = ch.intake
    a_esc = it.escape_probability()
    c4 = max(abs(a_esc[s] / (float(it.candidate.split("phi")[1]) * it.K_back[s]) - 1.0) for s in pf.SPECIES)
    return {"operating_point": {"candidate": it.candidate, "scenario": it.scenario, "state": it.state,
                                "compressor": pc.design_id, "P_set_Pa": P},
            "reservoir_steady_state_p_rel_diff": c1, "reservoir_steady_state_species_flow_rel_diff": c1b,
            "reservoir_steady_state_note": "Reservoir.steady_state (damped fixed point, no convergence flag: ICD G-04) "
                                           "with the compressor net inflow, feed orifice A_eq (K = 1), the plenum "
                                           "geometry and Ti6Al4V DB gamma: reproduces the F4 closed form",
            "size_orifice_for_pressure_rel_diff": c2,
            "size_orifice_note": "reservoir.size_orifice_for_pressure (60-step bisection in [1e-8, 3e-2] m^2, no "
                                 "residual: ICD G-05) vs the F4 90-step log bisection (residual reported). At low plenum "
                                 "targets the F4 A_eq exceeds 3e-2 m^2 and that routine would silently return the "
                                 "bracket end: F4 does not use it for sizing",
            "a_eq_m2_at_check_point": op["a_eq_m2"],
            "cascade_vs_run_once_rel_diff_max": c3,
            "f1_escape_probability_vs_phi_Kback_rel_diff_max": c4,
            "f1_escape_note": "a_s recovered from the F1 record (e = q_fwd / p_passive) equals phi K_back,s up to the "
                              "rounding of the committed F1 JSON"}


# ----------------------------------------------------------------------------------------------------- doc
def offered_records(inp: dict, tr: dict, par: list) -> list:
    """The record offered to H-1 for every Pareto member of each (scenario, P_set) context at the LARGEST orbit
    amplitude whose Pareto set is non-empty (contexts with no feasible member get no record): mdot_s, P, T, x_s at the design state plus the orbit-check ranges and the transient quality."""
    by = {(r.candidate, r.scenario, r.state): r for r in inp["recs"]}
    plants = {p.design_id: p for p in inp["plants"]}
    rowmap = {r["id"]: r for r in tr["rows"]}
    gam = walls()[TRANSIENT_WALL]
    out = []
    chosen = []
    for ctx in sorted({(p["scenario"], p["P_set_Pa"]) for p in par}):
        sets = [p for p in par if (p["scenario"], p["P_set_Pa"]) == ctx and p["pareto_ids"]]
        if sets:
            chosen.append(max(sets, key=lambda p: p["orbit_amplitude"]))
    for p in chosen:
        for rid in p["pareto_ids"]:
            r = rowmap[rid]
            pl = pf.Plenum(r["V_m3"], gam, TRANSIENT_WALL, leak_area())
            ch = pf.Chain(by[(r["candidate"], r["scenario"], inp["states"][0])], inp["filters"][0],
                          plants[r["compressor"]], pl)
            op = pf.steady_operating_point(ch, r["P_set_Pa"])
            o = op["offered"]
            out.append({"id": rid, "orbit_amplitude": p["orbit_amplitude"], "label": pf.LABEL_PARAMETRIC,
                        "plane": "IF-A4 plenum (valve upstream); HALL_INLET_Z0 state = this state minus the TBD "
                                 "feed-path drop (H1F-IN-04)",
                        "design_state": inp["states"][0],
                        "mdot_s_mgps": {s: o["mdot_s_kgps"][s] * 1e6 for s in pf.SPECIES},
                        "mdot_total_mgps": o["mdot_total_kgps"] * 1e6, "P_Pa": o["P_Pa"], "T_K": o["T_K"],
                        "T_status": "ASSUMED_ISOTHERMAL_CHAIN (F4-P-01)",
                        "x_s_flow_mole": o["x_s_flow_mole"], "x_s_plenum_mole": o["x_s_plenum_mole"],
                        "transient_quality": {k: r["objectives"][k] for k in ("settling_max_s", "peak_deviation_max",
                                                                             "valve_travel", "ripple_transfer_shaft")}
                        | {"overshoot_max": r["summary"]["overshoot_max"],
                           "P_min_Pa": r["summary"]["P_min_Pa"], "P_max_Pa": r["summary"]["P_max_Pa"],
                           "mdot_min_mgps": r["summary"]["mdot_min_kgps"] * 1e6,
                           "mdot_max_mgps": r["summary"]["mdot_max_kgps"] * 1e6,
                           "ride_through_s": r["summary"].get("ride_through_s"),
                           "plenum_tau_s": r["summary"]["plenum_tau_s"]},
                        "compressor_P_el_W": op["compressor"]["P_el_W"], "a_eq_m2": op["a_eq_m2"],
                        "feed_Kn_upper": op["feed"]["Kn_upper_O_omitted"]})
    return out


def conductance_demand() -> list:
    """Minimum molecular conductance of the whole downstream feed path (valve + line + isolator + distributor + H-1)
    that passes mdot at an upstream pressure equal to the compressor's admissible outlet (0.1 Pa), for an N2 / O2 / O
    bracket of the gas (q = mdot k T / m at 350 K). Derived (model-derived), not a requirement."""
    out = []
    for m in (0.03, 0.38, 1.3, 3.2):
        row = {"mdot_mgps": m}
        for s in pf.SPECIES:
            q = m * 1e-6 * pf.kT_over_m(s, pf.T_CHAIN_K)
            C = q / pf.P_DOMAIN_PA
            row[f"C_min_m3_s_if_all_{s}"] = C
            row[f"orifice_equivalent_area_m2_if_all_{s}"] = C / (pf.cbar(s, pf.T_CHAIN_K) / 4.0)
        out.append(row)
    return out


def findings(inp, agg, psf, basis, tr, par, sens, ov, conv, checks) -> list:
    key = f"F4-FIL-NONE|WALL-G0|V{V_STEADY_REF:g}"
    fr = agg[key]["per_scenario"]
    single = [(sc, x["P_req_Pa"], x["frontier_mdot_mgps"]) for sc, v in fr.items() for x in v
              if x["frontier_mdot_mgps"] is not None]
    sched = [(sc, x["P_req_Pa"], x["scheduled_setpoint"]["frontier_mdot_mgps"]) for sc, v in fr.items() for x in v
             if x["scheduled_setpoint"]["frontier_mdot_mgps"] is not None]
    smax = max(single, key=lambda t: t[2])
    shmax = max(sched, key=lambda t: t[2])
    owner_lo = 0.38
    n_owner = sum(x["scheduled_setpoint"]["n_chains_meeting_mdot_req"][str(owner_lo)] for v in fr.values() for x in v)
    pmax_feasible = max(t[1] for t in single)
    # per-state frontier: binding state
    bind = Counter()
    for sc, d in psf.items():
        for k, P in enumerate(TARGETS_PA):
            vals = {stn: v[k] for stn, v in d.items() if v[k] is not None}
            if len(vals) == len(d):
                bind[min(vals, key=vals.get)] += 1
    psmax = max((v for d in psf.values() for vv in d.values() for v in vv if v is not None))
    hist = Counter()
    for h in agg[key]["reason_histogram"]:
        if h["target_Pa"] <= pf.P_DOMAIN_PA:
            hist[h["reason"]] += h["count"]
    char_low = sum(h["count"] for h in agg[key]["reason_histogram"]
                   if h["reason"] == pf.R_CHARACTERISTIC and h["target_Pa"] == TARGETS_PA[0])
    pts_low = len(inp["recs"]) * len(inp["plants"])
    wall_counts = {}
    for V in VOLUMES_M3:
        k2 = f"F4-FIL-NONE|WALL-TI64-DB|V{V:g}"
        wall_counts[f"{V:g}"] = sum(x["n_chains_all_state_feasible"] for v in agg[k2]["per_scenario"].values()
                                    for x in v if x["P_req_Pa"] == 0.01)
    g0_count = sum(x["n_chains_all_state_feasible"] for v in fr.values() for x in v if x["P_req_Pa"] == 0.01)
    filt_eff = {}
    for f in inp["filters"]:
        k3 = f"{f.case_id}|WALL-G0|V{V_STEADY_REF:g}"
        vals = [x["scheduled_setpoint"]["frontier_mdot_mgps"] for v in agg[k3]["per_scenario"].values() for x in v
                if x["scheduled_setpoint"]["frontier_mdot_mgps"] is not None]
        filt_eff[f.case_id] = round(float(max(vals)), 6) if vals else None
    sim_rows = [r for r in tr["rows"] if r["objectives"] is not None]
    taus = [r["summary"]["plenum_tau_s"] for r in sim_rows]
    rides = [r["summary"].get("ride_through_s") for r in sim_rows if r["summary"].get("ride_through_s")]
    rip = {f"{V:g}": [r["objectives"]["ripple_transfer_shaft"] for r in sim_rows if r["V_m3"] == V] for V in VOLUMES_M3}
    feas = {str(a): sum(1 for r in sim_rows if r["by_orbit_amplitude"][str(a)]["status"] == pf.ST_FEASIBLE)
            for a in ORBIT_AMPLITUDES}
    nd_counts = {str(a): sum(len(p["pareto_ids"]) for p in par if p["orbit_amplitude"] == a) for a in ORBIT_AMPLITUDES}
    sens_changed = sum(1 for s in sens for fv, x in s["by_f_valve_hz"].items() if x["status"] != s["nominal"]["status"])
    ov_max = max([max(o["rel_diff_mdot_min"], o["rel_diff_mdot_max"]) for o in ov if "rel_diff_mdot_min" in o],
                 default=None)
    ov_pdev = max([o["simulated"]["P_dev_max_frac"] for o in ov if "rel_diff_mdot_min" in o], default=None)
    conv_max = max([v for c in conv for v in c["rel_diff"].values() if v is not None], default=None)
    conv_same = all(c["same_status"] for c in conv)
    cd = conductance_demand()
    f = [
        {"id": "F4-01", "evidence_class": "model-derived (PARAMETRIC_SENSITIVITY inputs)",
         "finding": f"all-orbit-state deliverable flow is small: with one plenum setpoint for all five F1 orbit states "
                    f"the frontier (max over the 48 F1 intake candidates x 32 F3 compressors, filter none, WALL-G0) is "
                    f"{smax[2]:.4g} mg/s ({smax[0]}, P_req {smax[1]:g} Pa); with a setpoint scheduled per orbit state it "
                    f"is {shmax[2]:.4g} mg/s ({shmax[0]}, P_req {shmax[1]:g} Pa). Chains meeting the lower end of the "
                    f"owner ground characterization range ({owner_lo} mg/s, row 73) at every state: {n_owner}. "
                    f"Single-state values reach {psmax:.4g} mg/s"},
        {"id": "F4-02", "evidence_class": "model-derived",
         "finding": f"the lowest-supply orbit state binds: the min-over-states flow is set by {bind.most_common(1)[0][0] if bind else 'n/a'} "
                    f"in {bind.most_common(1)[0][1] if bind else 0} of {sum(bind.values())} (scenario, P_req) cells "
                    f"with all states in domain (per_state_frontier)"},
        {"id": "F4-03", "evidence_class": "inferred (domain) + model-derived",
         "finding": f"domain: every P_req > {pf.P_DOMAIN_PA:g} Pa is INFEASIBLE_OUT_OF_DOMAIN (F3 cap propagated); the "
                    f"highest P_req with an all-state-feasible chain is {pmax_feasible:g} Pa. The H2-3 analog IF-A5 "
                    f"pressure 5.74-1216 Pa (H23-06, ECHT-size illustration) lies entirely above the cap. To accept the "
                    f"feed at <= 0.1 Pa the whole downstream path must have a molecular conductance >= "
                    f"{cd[2]['C_min_m3_s_if_all_N2']:.3g} m^3/s for 1.3 mg/s of N2 (orifice-equivalent "
                    f"{cd[2]['orifice_equivalent_area_m2_if_all_N2'] * 1e4:.3g} cm^2), see conductance_demand"},
        {"id": "F4-04", "evidence_class": "model-derived",
         "finding": f"a lower pressure bound exists too: at P_set = {TARGETS_PA[0]:g} Pa, {char_low} of {pts_low} "
                    f"chain-state points leave the Gaede characteristic domain (K < 1: the throughput exceeds the turbo "
                    f"row's S p capacity when the plenum is drawn down; points counted over every F1 record x F3 design, "
                    f"one point may carry several reasons). Each chain has an admissible plenum window "
                    f"[characteristic limit, min(dead-head, 0.1 Pa)]; reasons over in-domain targets: "
                    f"{dict(sorted(hist.items()))}"},
        {"id": "F4-05", "evidence_class": "model-derived",
         "finding": f"the plenum is not an orbit-scale buffer at <= 0.1 Pa: plenum time constants "
                    f"{min(t[0] for t in taus):.3g}-{max(t[1] for t in taus):.3g} s and inventory ride-through "
                    f"{min(rides):.3g}-{max(rides):.3g} s over V = {VOLUMES_M3[0]:g}-{VOLUMES_M3[-1]:g} m^3 (orbital "
                    f"period ~5.3e3 s); orbit-scale supply changes pass to the delivered flow (quasi-static) and the "
                    f"volume trades mass against high-frequency attenuation: ripple transfer at the compressor shaft "
                    f"frequency (upper bound) {min(rip[f'{VOLUMES_M3[0]:g}']):.3g}-{max(rip[f'{VOLUMES_M3[0]:g}']):.3g} "
                    f"at {VOLUMES_M3[0]:g} m^3 vs {min(rip[f'{VOLUMES_M3[-1]:g}']):.3g}-"
                    f"{max(rip[f'{VOLUMES_M3[-1]:g}']):.3g} at {VOLUMES_M3[-1]:g} m^3"},
        {"id": "F4-06", "evidence_class": "model-derived (uncited DB prior gamma)",
         "finding": f"plenum wall O recombination couples volume to deliverable pressure: O + O -> O2 halves the number "
                    f"of O particles, lowering the dead-head pressure. All-state-feasible chains at P_req 0.01 Pa (all "
                    f"scenarios): WALL-G0 {g0_count}; WALL-TI64-DB (gamma {walls()['WALL-TI64-DB']:.3g}) by V: "
                    f"{wall_counts}"},
        {"id": "F4-07", "evidence_class": "model-derived (PARAMETRIC_SENSITIVITY filter cases)",
         "finding": f"filter effect on the scheduled-setpoint frontier (max over scenarios, mg/s): {filt_eff} "
                    f"(gap-reflection series model; every filter number is a labelled parametric case)"},
        {"id": "F4-08", "evidence_class": "model-derived",
         "finding": f"transient study: {len(sim_rows)} simulated cases; feasible at orbit amplitude "
                    f"{', '.join(f'{a}: {feas[a]}' for a in feas)}; Pareto members {nd_counts}. Larger orbit "
                    f"amplitudes fail mostly by valve saturation (authority r = {AUTHORITY:g}) or by leaving the "
                    f"characteristic domain at the high-density states"},
        {"id": "F4-09", "evidence_class": "model-derived",
         "finding": f"valve-bandwidth sensitivity (F4-P-08 TBD): {sens_changed} status changes in "
                    f"{len(sens) * len(F_VALVE_SENSITIVITY_HZ)} re-runs of Pareto members at "
                    f"{list(F_VALVE_SENSITIVITY_HZ)} Hz"},
        {"id": "F4-10", "evidence_class": "model-derived (numerics)",
         "finding": f"numerics: quasi-static orbit check vs full transient max relative flow difference {ov_max} "
                    f"(plenum pressure held within {ov_pdev}); {pf.INTEGRATOR_METHOD} rtol {pf.RTOL:g} vs "
                    f"{pf.INTEGRATOR_REFERENCE} rtol {pf.RTOL_REFERENCE:g}: same status "
                    f"{conv_same}, max objective difference {conv_max}; mass-conservation residual max "
                    f"{max(r['summary']['mass_residual_rel'] for r in sim_rows):.3g} (gate {pf.MASS_TOL:g})"},
        {"id": "F4-11", "evidence_class": "model-derived",
         "finding": "coupled compressor inlet: F3 evaluated every design at p_in = p_passive (the F1 zero-net-flow "
                    "pressure, where the F1 net flow is zero); in the coupled solution p_in < p_passive and the "
                    "delivered flow follows mdot_fwd (1 - p_in / p_passive) minus the compressor back-leak: closes "
                    "F1-ID-04 / IFD-F3-05 for the parametric inputs"},
        {"id": "F4-12", "evidence_class": "inferred",
         "finding": f"MODE_STRICT returns NOT_EVALUATED ({len(pf.strict_blockers())} blockers); every number here is "
                    "PARAMETRIC_SENSITIVITY: not a plenum design, not a valve specification, not a requirement, no PASS"},
    ]
    return f


def interface_demands() -> list:
    return [
        {"id": "F4-ID-01", "direction": "F1 -> F4", "counterpart": "abep_sim/design/intake_synthesis.py (F1)",
         "content": "IF-A1 records per unit area (mdot_fwd, p_passive, T, K_back per species) and per-state F1 "
                    "feasibility; consumed through the committed JSON", "status": "CONSUMED"},
        {"id": "F4-ID-02", "direction": "F4 -> F1", "counterpart": "abep_sim/design/intake_synthesis.py (F1-ID-04, F1-ID-05)",
         "content": "achieved compressor-inlet partial pressures (p2_s; b_s = p2_s / p_passive,s) at every coupled "
                    "operating point (steady_operating_point()['compressor_inlet_p_s_Pa']); the feed pressure is "
                    "returned as a feasibility region over P_req, never a value", "status": "PROVIDED (PARAMETRIC_SENSITIVITY)"},
        {"id": "F4-ID-03", "direction": "F2 -> F4", "counterpart": "abep_sim/design/filter_stage.py (F2-IF-05)",
         "content": "forward fractions (apply) and backflow fractions (backflow_coupling) per species; F4 combines them "
                    "with the intake escape probability in a gap-reflection series (diffuse intake-side transmission = "
                    "t_b by reciprocity for loss-free elements); capture / conversion cases are refused (TBD)",
         "status": "CONSUMED (none + PARAMETRIC_SENSITIVITY cases)"},
        {"id": "F4-ID-04", "direction": "F4 -> F2", "counterpart": "abep_sim/design/filter_stage.py",
         "content": "back-incident flux on the filter outlet face Gamma_b,s = p2,s A cbar_s / 4 at every operating point "
                    "(the InletState.mdot_back_incident_kgps definition); demand: evidenced capture / conversion / "
                    "transmission records (F2 all TBD)", "status": "DEFINED / DEMANDED"},
        {"id": "F4-ID-05", "direction": "F3 -> F4", "counterpart": "abep_sim/design/compressor_synthesis.py (IFD-F3-04)",
         "content": "the compressor set = union of the F3 per-case Pareto ids (32 designs) from "
                    "f3_compressor_designs_v1.json; F3 domain cap 0.1 Pa, Kn limit and cross sections",
         "status": "CONSUMED"},
        {"id": "F4-ID-06", "direction": "F4 -> F3", "counterpart": "abep_sim/design/compressor_synthesis.py (IFD-F3-05)",
         "content": "coupled operating points (p_in, p_out, throughput, P_el, K range) and the admissible plenum window "
                    "per design; demands: a characteristic below K = 1 (start-up / draw-down) and a transitional-regime "
                    "stage model or T-1 data before any outlet above 0.1 Pa (OQ-F3-03)", "status": "PROVIDED / DEMANDED"},
        {"id": "F4-ID-07", "direction": "F4 -> F5", "counterpart": "docs/hardware/h1_freeze_candidate/ (IFD-F4-01..05)",
         "content": "offered state records (mdot_s, P, T, x_s, transient quality with metric definitions) for the "
                    "Pareto members, and feasibility regions over the parametric requirement sweep", "status": "PROVIDED (PARAMETRIC_SENSITIVITY)"},
        {"id": "F4-ID-08", "direction": "F5 -> F4", "counterpart": "docs/hardware/h1_freeze_candidate/ (IFS-F4-02, H1F-IN-04)",
         "content": "H-1 inlet conductance / back-pressure law; F4 derives the minimum downstream conductance compatible "
                    "with the compressor domain (conductance_demand)", "status": "DEMANDED (TBD)"},
        {"id": "F4-ID-09", "direction": "F5 -> F4", "counterpart": "docs/hardware/h1_freeze_candidate/ (IFD-F4-06, IFD-F4-07)",
         "content": "Xe anode-feed mode and the contamination limit: NOT_EVALUATED here (Xe path not modelled; filter "
                    "'none' carries no protection function)", "status": "NOT_EVALUATED"},
        {"id": "F4-ID-10", "direction": "F4 -> F7/F8", "counterpart": "abep_sim/design/architecture_optimizer.py; "
         "abep_sim/design/robust_optimizer.py (F78-ID-07)",
         "content": "x_plenum = (V, Kp, Ti, f_valve, authority) and the API steady_operating_point / steady_sweep / "
                    "transient_case / orbit_quasi_static; MODE_STRICT refuses until the blockers close", "status": "AVAILABLE"},
        {"id": "F4-ID-11", "direction": "F4 -> F0", "counterpart": "docs/performance/",
         "content": "workload: vectorized steady sweeps (seconds) and the LSODA transient cases (~0.1 s each); candidate "
                    "Rust hotspot only if profiling shows it", "status": "INFORMATIONAL"},
        {"id": "F4-ID-12", "direction": "F4 <-> H2-3", "counterpart": "docs/hardware/h2/h2_3_gas_path_plenum/",
         "content": "plenum volume, metering-valve bandwidth / authority, wall recombination class (GP-D03), compressor "
                    "ripple (H23-17); F4 evaluates them parametrically", "status": "DEMANDED (TBD)"},
        {"id": "F4-ID-13", "direction": "F4 -> F9", "counterpart": "docs/architecture/freeze_candidate/"
         "architecture_freeze_candidate_v1.json (F9-ID-04)",
         "content": "plenum / valve / feed rows: VALUE TBD, PARAMETRIC_SENSITIVITY ranges only", "status": "INFORMATIONAL"},
    ]


def open_owner_questions() -> list:
    return [
        {"id": "OQ-F4-01", "question": "Plenum setpoint across orbit states: one fixed setpoint (single-setpoint "
         "frontier) or a setpoint scheduled with the slowly varying orbit state (scheduled frontier)? The all-state "
         "deliverable flow differs between them (F4-01).", "proposed_answer": "none proposed",
         "needed_by": "F7 coupled vector; control / start sequence (F9)"},
        {"id": "OQ-F4-02", "question": "The compressor's evidence domain caps the plenum at 0.1 Pa while the H2-3 analog "
         "feed path needs 5.7-1216 Pa at IF-A5. Either the downstream path (valve + line + isolator + distributor + "
         "H-1) is designed for a molecular conductance >= the conductance_demand values, or a compressor regime above "
         "0.1 Pa is pursued (transitional model / T-1 data, OQ-F3-03). Which is the design direction?",
         "proposed_answer": "none proposed", "needed_by": "LOCK-1 (H1F-IN-04, IFS-F4-02)"},
        {"id": "OQ-F4-03", "question": "Confirm the F4 transient-quality metric definitions (2 % band, 60 s window, the "
         "E0..E7 event sequence, orbit-modulation amplitude cases) as the basis on which H-1 tolerances are set at "
         "LOCK-2 (F5 IFD-F4-05)?", "proposed_answer": "none proposed", "needed_by": "LOCK-2"},
        {"id": "OQ-F4-04", "question": "The all-state deliverable flow of every evaluated chain is below the lower end of "
         "the owner ground characterization range (0.38 mg/s, row 73). Which lever is to be studied: larger capture "
         "(F1 drag-limited at h180_f230), operation restricted to the higher-density states, or a different feed "
         "requirement?", "proposed_answer": "none proposed", "needed_by": "F7 / F9"},
        {"id": "OQ-F4-05", "question": "Orbit-scale density modulation: the frozen atmosphere is orbit-averaged. Supply an "
         "amplitude basis or authorize an orbit-resolved frozen dataset (CLAUDE.md rule 1 rebuild)?",
         "proposed_answer": "none proposed", "needed_by": "next F4 revision"},
    ]


def m16_impact() -> list:
    return [{"row": 4, "key": "buffer_plenum", "state_before": "BLOCKED", "state_after": "BLOCKED",
             "change": "none: PARAMETRIC_SENSITIVITY screening; chamber volume and operating pressure remain unset (the "
                       "study gives feasibility regions and Pareto sets, not a value)"},
            {"row": 5, "key": "atm_metering_valve", "state_before": "BLOCKED", "state_after": "BLOCKED",
             "change": "none: released ground-qualification feed points still do not exist; F4 adds a valve-law / PI "
                       "framework and parametric bandwidth / authority sensitivities"}]


def metric_definitions() -> dict:
    return {
        "settling_time_s": f"time after an event until |P - P_final| <= {pf.SETTLE_BAND:g} P_final for the rest of the "
                           f"{pf.WINDOW_S:g} s window (sampled on a log grid; upper bound at sampling resolution); null = "
                           "NOT settled -> TRANSIENT_NOT_SETTLED_WITHIN_WINDOW",
        "flow_recovery_s": "same rule on the delivered total flow mdot_H1",
        "overshoot_frac": "setpoint events: max(0, max sign(dP)(P - P_final)) / |P_final - P_previous|",
        "peak_deviation_frac": "disturbance events (feed path, supply): max |P - r| / r",
        "ripple_pp_frac_mdot": "orbit check: (max - min) / mean of the delivered flow over one orbit at each state",
        "ripple_transfer_shaft": "open-loop plenum attenuation 1/sqrt(1 + (2 pi f tau_s)^2) at the compressor shaft "
                                 "frequency (the lowest possible ripple frequency), least-attenuated species: an upper "
                                 "bound on the fraction of a compressor flow ripple that reaches the plenum pressure",
        "valve_travel": "sum |du| over the event sequence (fraction of full stroke): controller effort",
        "min_max_over_scenario": "P, mdot, x_O min / max over the event sequence (summary) and over the orbit at every "
                                 "F1 state (orbit check rows)",
        "recovery_after_disturbance": "settling_time_s / flow_recovery_s of E3..E7",
        "saturation": "valve command outside [0, 1] at the end of an event, or u > 1 needed at any orbit phase -> "
                      "VALVE_SATURATED_SETPOINT_NOT_MAINTAINED",
        "event_sequence": [e.name for e in pf.event_sequence(None, 1.0)] if False else
        ["E0_hold (10 s)", "E1_setpoint_up (+10 %)", "E2_setpoint_down", "E3_feed_path_step (x0.8)",
         "E4_feed_path_restore", "E5_supply_down (x0.9)", "E6_supply_up (x1.1)", "E7_supply_restore"],
    }


def assemble(inp, agg, psf, basis, tr, par, sens, ov, conv, checks, offered) -> dict:
    sim_rows = [r for r in tr["rows"] if r["objectives"] is not None]
    rowmap = {r["id"]: r for r in tr["rows"]}
    pareto = []
    for p in par:
        pareto.append({**p, "members_objectives": {i: rowmap[i]["objectives"] for i in p["pareto_ids"]},
                       "member_records_in": f"{TRANSIENTS_NAME}#rows (by id)"})
    return {
        "schema": pf.SCHEMA, "version": pf.VERSION, "lane": "A9_7_F4", "follow_on": "fo_a9_7_f4_plenum_feed",
        "directive": {"path": "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md",
                      "json": "docs/decisions/OD_2026_10_01_A9_7_architecture_freeze_design_synthesis.json",
                      "section": "F4 - Plenum/feed synthesis"},
        "status": "INVESTIGATION_HYPOTHESIS",
        "deliverable_status": "PARAMETRIC_SENSITIVITY_SCREENING (not a design, not a requirement, no PASS, no winner)",
        "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL, "module": "abep_sim/design/plenum_feed.py",
        "test": TEST_REL, "regenerate": f"python {SCRIPT_REL}  (verify: --check)",
        "companions": {"chains": CHAINS_NAME, "transients": TRANSIENTS_NAME, "md": MD_NAME},
        "what_this_is_not": [
            "not a plenum design, valve specification, selected requirement, optimum, winner or PASS",
            "not a model change: no existing module or frozen dataset is modified; not wired into archengine",
            "not a Hall prediction: the H-1 inlet demand is TBD and is swept parametrically",
            "not evidence: every input with an uncited / assumed / TBD value is a labelled PARAMETRIC_SENSITIVITY case"],
        "pins": {p: sha256(p) for p in PINNED},
        "referenced_not_pinned": [{"path": p, "use": u} for p, u in REFERENCED_NOT_PINNED],
        "references": pf.REFERENCES,
        "model": {
            "balance": "dm_s/dt = mdot_s,compressor - mdot_s,Hall - mdot_s,losses (+ R_s): compressor = gross Gaede "
                       "through-flow; Hall = feed-valve molecular orifice flow (K = 1, A_eq = u A_eq,max x feed-path "
                       "factor); losses = compressor back-leak (DragCompressor leak conductance; the backflow toward the "
                       "filter / intake) + external plenum leak (Reservoir leak path); R_s = Reservoir wall "
                       "recombination O -> O2 (mass-conserving)",
            "compressor_inlet_node": pf.QUASI_STEADY_NOTE,
            "intake_filter": "F1 net-flow law q = f - e p2 with the F2 stage folded in by the gap-reflection series "
                             "(module docstring); F2 'none' reproduces the F1 law exactly",
            "controller": " ".join(pf.Controller.__doc__.split()),
            "integrator": f"scipy.integrate.solve_ivp {pf.INTEGRATOR_METHOD} (stiff-safe), rtol {pf.RTOL:g} "
                          f"(convergence check: {pf.INTEGRATOR_REFERENCE} at rtol {pf.RTOL_REFERENCE:g}), atol {pf.ATOL_SCALED:g} on scaled states, analytic Jacobian, restarted "
                          "at every event; mass conservation gate "
                          f"{pf.MASS_TOL:g} (linear invariants are preserved by linear multistep methods up to the nonlinear-solve tolerance)",
            "orbit_check": " ".join(pf.orbit_quasi_static.__doc__.split()),
            "fail_closed": "targets above 0.1 Pa -> INFEASIBLE_OUT_OF_DOMAIN with no flow reported; any stage K outside "
                           "[1, K0], stage / inlet pressure above 0.1 Pa or feed Kn upper bound below 0.5 -> "
                           "INFEASIBLE_OUT_OF_DOMAIN (also along transient trajectories); compressor T above the DB "
                           "service limit, dead-head, valve saturation, non-settling -> INFEASIBLE; integrator failure / "
                           "conservation residual -> MODEL_ERROR",
            "statuses": [pf.ST_FEASIBLE, pf.ST_INFEASIBLE, pf.ST_OOD, pf.ST_MODEL_ERROR, pf.ST_NOT_EVALUATED],
            "reasons": list(pf.REASONS),
        },
        "items": pf.parameter_registry(),
        "search_variables": [
            {"id": "x_plenum.V", "value": list(VOLUMES_M3), "units": "m^3", "basis": "decades around the H2-3 H23-14 "
             "upper minimum-volume value 6.2e-3 m^3", "source": "SRC-H23 H23-13/14", "evidence_class": "assumed",
             "status": "SEARCHED (parametric grid)"},
            {"id": "x_plenum.Kp", "value": list(KP), "units": "-", "basis": "normalized PI gain (one decade)",
             "source": "definition", "evidence_class": "definition", "status": "SEARCHED"},
            {"id": "x_plenum.Ti", "value": list(TI_S), "units": "s", "basis": "integral time (one decade)",
             "source": "definition", "evidence_class": "definition", "status": "SEARCHED"},
            {"id": "x_plenum.f_valve", "value": F_VALVE_NOMINAL_HZ, "units": "Hz", "basis": "F4-P-08 nominal parametric; "
             f"sensitivity {list(F_VALVE_SENSITIVITY_HZ)}", "source": "SRC-H23 H23-18", "evidence_class": "TBD",
             "status": "PARAMETRIC_SENSITIVITY"},
            {"id": "x_plenum.authority", "value": AUTHORITY, "units": "-", "basis": "F4-P-09", "source": "SRC-H23 H23-07",
             "evidence_class": "TBD", "status": "PARAMETRIC_SENSITIVITY"},
            {"id": "x_compressor", "value": inp["f3_ids"], "units": "-", "basis": "union of the F3 per-case Pareto ids "
             "(a subset of the 48 designs passing F3's inlet-independent gates; INT-01 limitation)",
             "source": "SRC-F3", "evidence_class": "model-derived (PARAMETRIC_SENSITIVITY)", "status": "INPUT_SET"},
            {"id": "x_intake", "value": {"area_m2": list(inp["areas"]), "candidates_d_collapsed": 48,
                                         "scenarios": list(inp["scenarios"]), "states": list(inp["states"])},
             "units": "-", "basis": "every F1 candidate (d-invariant, F1-02) x F1 surface scenario x F1 orbit state",
             "source": "SRC-F1", "evidence_class": "model-derived", "status": "INPUT_SET"},
        ],
        "requirement_sweep": {
            "P_req_Pa": list(TARGETS_PA),
            "P_req_definition": "minimum plenum (valve-upstream, IF-A4) pressure demanded by the downstream path; the "
                                "plenum setpoint P_set >= P_req on the grid; feasible P_set maximizes the delivered flow",
            "P_req_basis": "log grid from below the F1 passive pressures to above the F3 domain cap; includes the W1 "
                           "PROPOSED setpoint ladder values 0.05, 0.1, 0.2, 1 Pa (feed_state_closure) and 10 Pa (inside the "
                           "H2-3 analog IF-A5 range)",
            "mdot_req_mgps": list(MDOT_REQ_MGPS),
            "mdot_req_basis": "spans H23-02 delivered-flow range 0.0296-3.14 mg/s (model-derived) and owner row 73 ground "
                              "characterization range 0.38-3.2 mg/s with nominal sizing 1.3 mg/s (context only, not a "
                              "flight requirement)",
            "status": "PARAMETRIC (the H-1 demand is TBD: F5 IFD-F4-01..05); feasibility regions, never a chosen value",
            "feasibility_rule": "single setpoint: exists P_set >= P_req on the grid with every one of the five F1 orbit "
                                "states FEASIBLE and min-over-states mdot >= mdot_req; scheduled setpoint: per state its "
                                "own admissible P_set >= P_req, min over states of the per-state best flow >= mdot_req",
        },
        "metric_definitions": metric_definitions(),
        "inputs": {
            "f1_records": len(inp["recs"]), "f1_groups": len(inp["groups"]), "compressors": len(inp["plants"]),
            "filter_cases": [{"case_id": f.case_id, "label": f.label, "stage_id": f.stage_id, "note": f.note,
                              "t_f": f.t_f, "r_f": f.r_f, "t_b": f.t_b, "r_b": f.r_b, "overrides": list(f.overrides)}
                             for f in inp["filters"]],
            "walls": {k: {"gamma_O": v, "basis": "definitional non-catalytic bound" if v == 0 else
                          "materials.DB['Ti6Al4V'].gamma_O(350 K), literature-class prior (uncited)"}
                      for k, v in walls().items()},
            "leak_area_m2": leak_area(), "leak_area_basis": "Reservoir.leak_area_m2 code default (PARAMETRIC, F4-P-05)",
            "transient_wall": TRANSIENT_WALL, "transient_wall_basis": "owner H1F-IN-02 'inert / low-recombination "
                                                                      "lining' (allocation); gamma = 0 bound",
        },
        "steady": {"feasibility_regions": agg, "per_state_frontier_filter_none_wall_g0": psf,
                   "per_state_frontier_note": "single-state best delivered flow [mg/s] per P_set (columns = P_req grid)",
                   "conductance_demand": conductance_demand(),
                   "conductance_demand_note": " ".join(conductance_demand.__doc__.split())},
        "transient": {"basis": {k: v for k, v in basis.items() if k != "contexts"},
                      "contexts": [{k: v for k, v in c.items() if k != "orbit_check"} | {
                          "orbit_check_reasons": {cid: {a: oc[a]["reasons"] for a in oc}
                                                  for cid, oc in c["orbit_check"].items()},
                          "orbit_check_rows": {cid: oc for cid, oc in c["orbit_check"].items()
                                               if cid in c["simulated_chains"]}} for c in basis["contexts"]],
                      "n_rows": len(tr["rows"]), "n_simulated": len(sim_rows),
                      "rows_in": f"{TRANSIENTS_NAME}#rows",
                      "objectives": list(pf.OBJECTIVES),
                      "pareto_rule": "all objectives minimized; weak dominance over FEASIBLE rows of one (scenario, "
                                     "P_set, orbit amplitude); ties kept; no weights, no single optimum"},
        "pareto": pareto,
        "offered_to_h1": offered,
        "sensitivity_valve_bandwidth": sens,
        "orbit_quasi_static_verification": ov,
        "numerical_convergence": conv,
        "checks": checks,
        "findings": findings(inp, agg, psf, basis, tr, par, sens, ov, conv, checks),
        "interface_demands": interface_demands(),
        "open_owner_questions": open_owner_questions(),
        "m16_impact": m16_impact(),
        "strict_mode": {"status": pf.ST_NOT_EVALUATED, "blockers": pf.strict_blockers()},
        "limitations": [
            "INT-01 (consolidated verification round 1): the compressor search set is the union of the F3 per-case Pareto ids (32 designs), and those F3 fronts were built on the down-selection envelope inlets, not on the F1-coupled operating points used here. F3's inlet-independent gates (N_drag = 0, Ti-6Al-4V, cited tip speed <= 305.5 m/s) admit 48 designs; the 16 others are never evaluated. Every F4 Pareto set is therefore 'Pareto within the F3 front-union subset', not over the admissible compressor space: a design outside the subset can be non-dominated (or dominate a member) at the F1-coupled states",
            "isothermal chain at the F1 wall temperature (no gas energy balance; ICD G-07)",
            "free-molecular linear Gaede characteristic only (no transitional regime, no K < 1 branch, so no start-up "
            "from an empty plenum: start-up / Xe-to-air transition NOT_EVALUATED, IFD-F4-05 part)",
            "compressor-inlet node quasi-steady (inlet volume TBD); compressor speed constant (no rpm control)",
            "valve + downstream path lumped into one molecular orifice; downstream back-pressure neglected",
            "frozen atmosphere orbit-averaged; orbit modulation is a labelled parametric sinusoid",
            "no wall recombination in the compressor or the inlet node (DragCompressor carries none)",
            "settling times resolved on a log sample grid (upper bounds at sampling resolution)",
            "transients simulated only on the documented transient basis; other chains carry steady results only"],
        "compliance": {"existing_modules_modified": False, "frozen_data_modified": False, "wired_into_archengine": False,
                       "tbd_converted_to_assumed_for_optimum": False, "single_optimum_or_winner_declared": False,
                       "pass_declared": False, "julia_used": False, "deterministic": True, "new_pytest_skips": 0},
    }


def build():
    t0 = time.process_time()
    inp = load_inputs()
    st = stage_steady(inp)
    agg = aggregate_steady(inp, st)
    psf = per_state_frontier(inp, st)
    chains = chain_table(inp, st, ("F4-FIL-NONE", "WALL-G0", V_STEADY_REF))
    basis = transient_basis(inp, st, agg)
    tr = stage_transient(inp, basis)
    par = pareto_sets(tr)
    sens = stage_sensitivity(inp, tr, par)
    ov = stage_orbit_verification(inp, basis)
    conv = stage_convergence(inp, tr)
    checks = stage_checks(inp)
    offered = offered_records(inp, tr, par)
    doc = assemble(inp, agg, psf, basis, tr, par, sens, ov, conv, checks, offered)
    chains_doc = {"schema": "f4_plenum_chains_v1", "generated_by": SCRIPT_REL, "companion": JSON_NAME,
                  "label": pf.LABEL_PARAMETRIC,
                  "definition": "best deliverable total flow [mg/s] at the feed for every P_req of the sweep with ONE "
                                "setpoint for all five F1 orbit states: max over admissible P_set >= P_req on the grid of "
                                "the minimum over the states (every state in domain and feasible); null = no admissible "
                                "P_set. Rows without any feasible P_req are omitted (their reasons are in the main "
                                "JSON reason_histogram)",
                  "targets_Pa": list(TARGETS_PA), **chains}
    trans_doc = {"schema": "f4_plenum_transients_v1", "generated_by": SCRIPT_REL, "companion": JSON_NAME,
                 "label": pf.LABEL_PARAMETRIC, "metric_definitions": metric_definitions(), "rows": tr["rows"]}
    cpu = time.process_time() - t0
    return rnd(doc), rnd(chains_doc), rnd(trans_doc), cpu


def dump(o) -> str:
    return json.dumps(o, indent=1, ensure_ascii=False) + "\n"


def dump_rows(o, key) -> str:
    head = {k: v for k, v in o.items() if k != key}
    lines = ["{"]
    for k, v in head.items():
        lines.append(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},")
    rows = o[key]
    lines.append(f' {json.dumps(key)}: [')
    lines += [f"  {json.dumps(x, separators=(',', ':'), ensure_ascii=False)}{',' if i < len(rows) - 1 else ''}"
              for i, x in enumerate(rows)]
    lines.append(" ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _f(x, n=4):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{n}g}"
    return str(x)


def render_md(doc: dict) -> str:
    L = []
    A = L.append
    A("# F4 — Plenum / feed synthesis (A9.7)")
    A("")
    A(f"> Generated by `{SCRIPT_REL}` from `{JSON_NAME}` (companions `{CHAINS_NAME}`, `{TRANSIENTS_NAME}`). "
      "Do not edit by hand; `--check` verifies.")
    A("")
    A(f"**Status: {doc['status']} / {doc['deliverable_status']}.** Module `{doc['module']}`, test `{doc['test']}`, "
      f"base `{doc['base_commit'][:7]}`.")
    A("")
    A("The study couples the F1 intake records, the F2 filter stage, the F3 compressor designs, a species-resolved "
      "plenum and a feed valve under PI control. It solves dm_s/dt = mdot_s,compressor − mdot_s,Hall − mdot_s,losses. "
      "The H-1 inlet demand is TBD, so the study sweeps it as a parameter and reports feasibility regions instead of a "
      "chosen requirement. Every number is PARAMETRIC_SENSITIVITY: the compressor coefficients are uncited code "
      "defaults, every filter number is TBD, and the valve, wall and orbit inputs are labelled cases. MODE_STRICT "
      f"returns {doc['strict_mode']['status']}.")
    A("")
    A("## Model")
    A("")
    for k, v in doc["model"].items():
        if isinstance(v, str):
            A(f"- **{k}**: {v}")
    A("")
    A("## Inputs and parameters")
    A("")
    A("| id | value | units | basis | source | evidence class | status |")
    A("|---|---|---|---|---|---|---|")
    for p in doc["items"]:
        A(f"| {p['id']} | {p['value']} | {p['units']} | {p['basis']} | {p['source']} | {p['evidence_class']} | "
          f"{p['status']} |")
    A("")
    A("Filter cases (F2 API):")
    A("")
    A("| case | label | t_f (O) | r_f (O) | t_b (O) | r_b (O) | note |")
    A("|---|---|---|---|---|---|---|")
    for f in doc["inputs"]["filter_cases"]:
        A(f"| {f['case_id']} | {f['label']} | {_f(f['t_f']['O'])} | {_f(f['r_f']['O'])} | {_f(f['t_b']['O'])} | "
          f"{_f(f['r_b']['O'])} | {f['note']} |")
    A("")
    A("## Search variables")
    A("")
    A("| id | value | units | basis | status |")
    A("|---|---|---|---|---|")
    for v in doc["search_variables"]:
        val = v["value"] if v["id"] != "x_compressor" else f"{len(v['value'])} F3 designs"
        A(f"| {v['id']} | {val} | {v['units']} | {v['basis']} | {v['status']} |")
    A("")
    rs = doc["requirement_sweep"]
    A("## Requirement sweep (parametric)")
    A("")
    A(f"P_req = {rs['P_req_Pa']} Pa; mdot_req = {rs['mdot_req_mgps']} mg/s. {rs['P_req_definition']}. "
      f"{rs['feasibility_rule']}.")
    A("")
    A("## Steady feasibility regions")
    A("")
    A("The frontier is the largest mdot_req that is feasible at each P_req, taking the best chain over the 48 F1 "
      "candidates and 32 F3 compressors. A requirement cell (P_req, mdot_req) is feasible only when mdot_req is at or "
      "below the frontier. The table gives flows in mg/s for a single setpoint (S) and for a scheduled setpoint (Sch). "
      "'-' means no chain is feasible at every state.")
    A("")
    fr = doc["steady"]["feasibility_regions"]
    for key, v in fr.items():
        A(f"### {key}")
        A("")
        A("| scenario | " + " | ".join(f"{p:g} Pa" for p in rs["P_req_Pa"]) + " |")
        A("|---|" + "---|" * len(rs["P_req_Pa"]))
        for sc, rows in v["per_scenario"].items():
            A(f"| {sc} | " + " | ".join(f"S {_f(x['frontier_mdot_mgps'], 3)} / Sch "
                                        f"{_f(x['scheduled_setpoint']['frontier_mdot_mgps'], 3)}" for x in rows) + " |")
        A("")
    A("### Single-state best flow (filter none, WALL-G0) [mg/s]")
    A("")
    for sc, d in doc["steady"]["per_state_frontier_filter_none_wall_g0"].items():
        A(f"- {sc}: " + "; ".join(f"{stn} {[_f(x, 3) for x in vals]}" for stn, vals in d.items()))
    A("")
    A("### Downstream conductance compatible with the 0.1 Pa domain cap")
    A("")
    A("| mdot mg/s | C_min if all N2 (m³/s) | orifice-equivalent area if all N2 (cm²) | C_min if all O (m³/s) |")
    A("|---|---|---|---|")
    for c in doc["steady"]["conductance_demand"]:
        A(f"| {_f(c['mdot_mgps'])} | {_f(c['C_min_m3_s_if_all_N2'])} | "
          f"{_f(c['orifice_equivalent_area_m2_if_all_N2'] * 1e4)} | {_f(c['C_min_m3_s_if_all_O'])} |")
    A("")
    A("## Transient study")
    A("")
    A(f"Basis rule: {doc['transient']['basis']['rule']}")
    A("")
    A(f"Basis scenarios: {doc['transient']['basis']['basis_scenarios']}. Rows: {doc['transient']['n_rows']}, "
      f"simulated: {doc['transient']['n_simulated']}.")
    A("")
    A("| scenario | P_set Pa | all-state chains | steady ND | simulated | orbit-infeasible (smallest amplitude) |")
    A("|---|---|---|---|---|---|")
    for c in doc["transient"]["contexts"]:
        A(f"| {c['scenario']} | {_f(c['P_set_Pa'])} | {c['n_all_state_feasible_chains']} | "
          f"{len(c['steady_nondominated'])} | {len(c['simulated_chains'])} | "
          f"{len(c['not_simulated_orbit_infeasible_at_smallest_amplitude'])} |")
    A("")
    A("Metric definitions:")
    A("")
    for k, v in doc["metric_definitions"].items():
        A(f"- **{k}**: {v}")
    A("")
    A("## Pareto sets")
    A("")
    A(f"Objectives (all minimized): {doc['transient']['objectives']}. {doc['transient']['pareto_rule']}.")
    A("")
    A("| scenario | P_set Pa | orbit amp. | evaluated | status counts | Pareto members |")
    A("|---|---|---|---|---|---|")
    for p in doc["pareto"]:
        A(f"| {p['scenario']} | {_f(p['P_set_Pa'])} | {p['orbit_amplitude']} | {p['n_evaluated']} | "
          f"{p['status_counts']} | {len(p['pareto_ids'])} |")
    A("")
    A("### Offered to H-1 (Pareto members, design state; PARAMETRIC_SENSITIVITY)")
    A("")
    A("| member | amp. | mdot mg/s | P Pa | T K | x_O / x_N2 / x_O2 (flow) | settle s | peak dev | travel | "
      "ripple xfer | P_el W |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for o in doc["offered_to_h1"]:
        x = o["x_s_flow_mole"]
        q = o["transient_quality"]
        A(f"| `{o['id']}` | {o['orbit_amplitude']} | {_f(o['mdot_total_mgps'])} | {_f(o['P_Pa'])} | {_f(o['T_K'])} | "
          f"{_f(x['O'], 3)} / {_f(x['N2'], 3)} / {_f(x['O2'], 3)} | {_f(q['settling_max_s'])} | "
          f"{_f(q['peak_deviation_max'])} | {_f(q['valve_travel'])} | {_f(q['ripple_transfer_shaft'])} | "
          f"{_f(o['compressor_P_el_W'])} |")
    A("")
    A("## Sensitivity, verification, checks")
    A("")
    A(f"- Valve bandwidth sensitivity: {len(doc['sensitivity_valve_bandwidth'])} Pareto members re-run at "
      f"{F_VALVE_SENSITIVITY_HZ} Hz (rows in the JSON).")
    for o in doc["orbit_quasi_static_verification"]:
        if "rel_diff_mdot_min" in o:
            A(f"- Orbit quasi-static vs transient ({o['chain']}, {o['state']}, P {o['P_set_Pa']} Pa): rel. diff "
              f"min/max flow {_f(o['rel_diff_mdot_min'])} / {_f(o['rel_diff_mdot_max'])}; plenum pressure deviation "
              f"{_f(o['simulated']['P_dev_max_frac'])}.")
    for c in doc["numerical_convergence"]:
        A(f"- Convergence {c['id']}: same status {c['same_status']}, rel. diff {c['rel_diff']}.")
    ch = doc["checks"]
    A(f"- Reservoir.steady_state cross-check: p rel. diff {_f(ch['reservoir_steady_state_p_rel_diff'])}, species flow "
      f"{_f(ch['reservoir_steady_state_species_flow_rel_diff'])}; size_orifice_for_pressure {_f(ch['size_orifice_for_pressure_rel_diff'])}; "
      f"cascade vs DragCompressor._run_once {_f(ch['cascade_vs_run_once_rel_diff_max'])}; F1 escape probability vs "
      f"phi K_back {_f(ch['f1_escape_probability_vs_phi_Kback_rel_diff_max'])}.")
    A("")
    A("## Findings")
    A("")
    for f in doc["findings"]:
        A(f"- **{f['id']}** ({f['evidence_class']}): {f['finding']}")
    A("")
    A("## Interface demands")
    A("")
    A("| id | direction | counterpart | content | status |")
    A("|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        A(f"| {d['id']} | {d['direction']} | {d['counterpart']} | {d['content']} | {d['status']} |")
    A("")
    A("## Open owner questions (new)")
    A("")
    for q in doc["open_owner_questions"]:
        A(f"- **{q['id']}**: {q['question']} Proposed: {q['proposed_answer']}. Needed by: {q['needed_by']}.")
    A("")
    A("## M16 impact")
    A("")
    for m in doc["m16_impact"]:
        A(f"- row {m['row']} `{m['key']}`: {m['state_before']} → {m['state_after']}. {m['change']}")
    A("")
    A("## Limitations")
    A("")
    for x in doc["limitations"]:
        A(f"- {x}")
    A("")
    A("## Strict-mode blockers")
    A("")
    for b in doc["strict_mode"]["blockers"]:
        A(f"- {b['id']} ({b['what']}): {b['status']}; needs {b['needs']}")
    A("")
    return "\n".join(L)


def check_pins(doc_on_disk: dict) -> list:
    return [p for p, h in doc_on_disk.get("pins", {}).items() if not (REPO / p).exists() or sha256(p) != h]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the committed outputs are reproduced")
    a = ap.parse_args(argv)
    doc, chains, trans, cpu = build()
    texts = {JSON_NAME: dump(doc), CHAINS_NAME: dump_rows(chains, "rows_with_any_feasible_P_req"),
             TRANSIENTS_NAME: dump_rows(trans, "rows"), MD_NAME: render_md(doc)}
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
