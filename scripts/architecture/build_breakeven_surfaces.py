#!/usr/bin/env python3
"""Build the architecture break-even surfaces (breakeven_v1) over ANALYSIS RANGES. Not predictions.

Every surface is a deterministic function of abep_sim/breakeven.py and the analysis ranges declared below; no absolute
Hall prediction, no screening candidate, no Hall closure is used. Outputs (docs/architecture_comparison/breakeven/):
  breakeven_surfaces_v1.json          surfaces, inputs with source/status, self-checks, milestone statement
  fig_*.png                           plots if matplotlib is importable, otherwise surfaces_*.csv
  breakeven_evidence_overlay_prelim_v1.json (+ fig_evidence_overlay_prelim.png)
                                      ONLY with --evidence-matrix: published ion-cost points read READ-ONLY from RF/ECR
                                      evidence matrices, placed against the surfaces, labelled PRELIMINARY.

Usage:
  python scripts/architecture/build_breakeven_surfaces.py
  python scripts/architecture/build_breakeven_surfaces.py --evidence-matrix PATH [--evidence-matrix PATH ...]
  python scripts/architecture/build_breakeven_surfaces.py --check     # rebuild in memory, compare with the committed JSON
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from abep_sim import breakeven as b  # noqa: E402
from abep_sim.constants import RFP  # noqa: E402

OUT_DIR = os.path.join(ROOT, "docs", "architecture_comparison", "breakeven")
OUT_JSON = "breakeven_surfaces_v1.json"
OVERLAY_JSON = "breakeven_evidence_overlay_prelim_v1.json"
REL = lambda p: os.path.relpath(p, ROOT).replace(os.sep, "/")

# ------------------------------------------------------------------------------------------------ declared inputs
ATOMIC_WEIGHTS = {"N": 14.007, "O": 15.999, "Xe": 131.29}
ATOMIC_WEIGHTS_SOURCE = {
    "source": "CIAAW, Abridged Standard Atomic Weights 2024 (from Atomic Weights 2021 with 2024 revisions): "
              "N 14.007 +- 0.001, O 15.999 +- 0.001, Xe 131.29 +- 0.01",
    "url": "https://www.ciaaw.org/abridged-atomic-weights.htm (accessed 2026-09-26)",
    "evidence_class": "measured (standard atomic weight, evaluated)",
    "transformation": "ion mass = sum of atomic weights; electron mass (5.5e-4 u) neglected (relative effect <= 3.4e-5)",
}
SPECIES = {  # propellant species -> analysis beam mix (single species, singly charged): NOT a predicted composition
    "N2": ("N2+", 2 * ATOMIC_WEIGHTS["N"]),
    "O": ("O+", ATOMIC_WEIGHTS["O"]),
    "O2": ("O2+", 2 * ATOMIC_WEIGHTS["O"]),
    "Xe": ("Xe+", ATOMIC_WEIGHTS["Xe"]),
}
P_SOURCE_W = [25.0 * i for i in range(21)]                       # 0-500 W (figures)
P_SOURCE_W_DIM = [50.0 * i for i in range(11)]                   # 0-500 W (stored dimensional grid)
ETA_T = [round(0.1 * i, 1) for i in range(1, 11)]               # 0.1-1
V_D = [150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 450.0]
MDOT_MG_S = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
ETA_U0 = [0.3, 0.6, 0.9]
ETA_B = [0.5, 0.7, 0.9]
ETA_V_SET = [0.7, 0.8, 0.9, 1.0]
ETA_V_REF, GAMMA_REF, ETA_PPU_D = 0.9, 0.9, 0.9
OMEGA = [round(0.005 * i, 3) for i in range(191)]                # 0-0.95
OMEGA_FIXED = [0.0, 0.01, 0.02, 0.05, 0.1, 0.2]
CASES = {
    "add_only": {"alpha": 1.0, "chi": 0.0, "eta_v_delivered": "= eta_v",
                 "meaning": "delivered ions add to the beam and each costs the full Hall price V_d/eta_b"},
    "cost_offset": {"alpha": 1.0, "chi": 1.0, "eta_v_delivered": "= eta_v",
                    "meaning": "delivered ions add to the beam and avoid the Hall's per-ion electron-current overhead"},
    "optimistic_bound": {"alpha": 1.0, "chi": 1.0, "eta_v_delivered": 1.0,
                         "meaning": "most favourable corner of the declared box alpha, chi in [0,1], eta_v_S in "
                                    "[eta_v, 1] (self-check: dominates the box); elimination reference"},
}
PROPOSED = "PROPOSED analysis range (assumed; not a prediction, not a design value)"
CONTEXT = {
    "P5_N2_V_d": {"value": [231.9, 278.6], "unit": "V", "evidence_class": "measured", "evidence_level": 3,
                  "source": "Brabston et al., JPP 2025, doi:10.2514/1.B39623, Table 2 (N1-N5), via "
                            "hallthruster_bridge/identification/brabston_p5_n2_measurement_audit_v1.json",
                  "use": "context only: lies inside the V_d analysis range; P5 (3-5 kW, 5.0-5.4 mg/s) is outside the "
                         "RFP power class and is not an axis"},
    "NASA173Mv2_Xe_components": {
        "value": {"eta_v": [0.89, 0.97], "eta_m": [0.86, 0.90], "eta_b": [0.77, 0.81]}, "unit": "1",
        "evidence_class": "reconstructed (thrust-stand, ExB and RPA data reduced with the authors' model)",
        "evidence_level": 3, "source": "Hofer & Gallimore, AIAA-2004-3602, abstract (component ranges, 300-900 V) "
                                       "and Sec. IV.A (Xe, 10 mg/s anode flow), "
                                       "https://pepl.engin.umich.edu/pdf/AIAA-2004-3602.pdf (accessed 2026-09-26)",
        "definition_note": "Hofer's eta_v (Eq. 6) is the conversion of voltage into AXIALLY directed velocity, so it "
                           "absorbs divergence; in breakeven_v1 divergence is the separate factor gamma_div (G&K Eq. "
                           "2.3-15). Not directly comparable; context only.",
        "use": "context only: xenon, 5 kW class; shows the order of the components the analysis sets bracket"},
}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def g6(x):
    if x is None:
        return None
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return float(f"{x:.6g}")


def g5(x):
    return None if x is None or not math.isfinite(x) else float(f"{x:.5g}")


def g4(x):
    return None if x is None or not math.isfinite(x) else float(f"{x:.4g}")


def mix_of(species: str) -> b.IonMix:
    label, m = SPECIES[species]
    return b.IonMix((b.IonSpecies(label, m, 1, 1.0),))


def reference(species: str, V: float, mdot_kg_s: float, eta_u0: float, eta_b: float, eta_v: float, gamma: float,
              eta_ppu: float) -> b.HallReference:
    return b.HallReference(mdot_kg_s=mdot_kg_s, V_d_V=V, eta_u=eta_u0, eta_b=eta_b, eta_v=eta_v, gamma_div=gamma,
                           eta_ppu_discharge=eta_ppu, mix=mix_of(species))


def response(case: str, ref: b.HallReference) -> b.PreionResponse:
    c = CASES[case]
    evs = ref.eta_v if c["eta_v_delivered"] == "= eta_v" else c["eta_v_delivered"]
    return b.PreionResponse(alpha=c["alpha"], chi=c["chi"], eta_v_delivered=evs, mix_delivered=ref.mix)


def overhead(P: float) -> b.BusOverhead:
    # arch-agnostic algebra: O is the total bus overhead (see per_architecture); rf_hall container used for the numbers
    return b.BusOverhead(arch="rf_hall", source_bus_W={"rf_source": P},
                         delta_common_bus_W={k: 0.0 for k in b.COMMON_NON_DISCHARGE},
                         interstage_loss_bus_W=0.0, extra_ppu_bus_W=0.0)


# ------------------------------------------------------------------------------------------------ surfaces
def universal():
    """Dimensionless surfaces: x* = delta_eta_u*/eta_u0 and c* = C_del*/Pi_H versus omega = O/P_d_bus0."""
    req, vdr, cost = {}, {}, {}
    for case in CASES:
        evs = ETA_V_SET if case == "optimistic_bound" else [ETA_V_REF]
        for u0 in ETA_U0:
            for eb in ETA_B:
                for ev in evs:
                    ref = reference("N2", 300.0, 1e-6, u0, eb, ev, GAMMA_REF, ETA_PPU_D)
                    r = response(case, ref)
                    h = b.hall_only_state(ref)
                    xs, vs, cs = [], [], []
                    for w in OMEGA:
                        out = b.required_utilization_gain(ref, r, overhead(w * h["P_d_bus_W"]))
                        ok = out["status"].startswith("OK")
                        xs.append(g5(out["delta_eta_u_star"] / u0) if ok else None)
                        vs.append(g5(out["V_d_ratio_at_breakeven"]) if ok else None)
                        if not ok:
                            cs.append(None)
                        elif w == 0.0:
                            cs.append(g5(b.marginal_breakeven_delivered_cost(ref, r) / h["Pi_H_bus_W_per_A"]))
                        else:
                            cs.append(g5(w * h["P_d_bus_W"] / (out["delta_s_star"] * ref.mdot_kg_s
                                                                * r.mix_delivered.coulomb_per_kg)
                                         / h["Pi_H_bus_W_per_A"]))
                    key = f"{case}|eta_u0={u0}|eta_b={eb}|eta_v={ev}"
                    req[key], vdr[key], cost[key] = xs, vs, cs
    marginal, sup_fixed = {}, {}
    for case in CASES:
        evs = ETA_V_SET if case == "optimistic_bound" else [ETA_V_REF]
        for eb in ETA_B:
            for ev in evs:
                ref = reference("N2", 300.0, 1e-6, 0.6, eb, ev, GAMMA_REF, ETA_PPU_D)
                h = b.hall_only_state(ref)
                marginal[f"{case}|eta_b={eb}|eta_v={ev}"] = g6(
                    b.marginal_breakeven_delivered_cost(ref, response(case, ref)) / h["Pi_H_bus_W_per_A"])
                for u0 in ETA_U0:
                    ref = reference("N2", 300.0, 1e-6, u0, eb, ev, GAMMA_REF, ETA_PPU_D)
                    h = b.hall_only_state(ref)
                    row = []
                    for wf in OMEGA_FIXED:
                        s = b.supremum_breakeven_delivered_cost(ref, response(case, ref), wf * h["P_d_bus_W"], 256)
                        v = s["sup_W_per_A"] / h["Pi_H_bus_W_per_A"]
                        row.append(g6(0.0 if abs(v) < 1e-12 else v))    # <= 0: no source cost pays
                    sup_fixed[f"{case}|eta_u0={u0}|eta_b={eb}|eta_v={ev}"] = row
    return {"omega": OMEGA, "delta_eta_u_star_over_eta_u0": req, "V_d_ratio_at_breakeven": vdr,
            "C_del_star_over_Pi_H": cost, "marginal_C_del_star_over_Pi_H": marginal,
            "omega_fixed": OMEGA_FIXED, "sup_C_del_star_over_Pi_H_with_fixed_overhead": sup_fixed,
            "notes": {"omega": "O / P_d_bus0: total bus overhead over the Hall-only discharge bus power",
                      "C_del_star_over_Pi_H": "break-even bus cost per ampere delivered into the Hall beam when the "
                                              "whole overhead O = omega P_d_bus0 is spent in the generator; at omega "
                                              "= 0 the marginal (delta_s -> 0) value",
                      "sup_with_fixed_overhead": "sup over the delivered share of the break-even cost when a fixed "
                                                 "(non-ion-scaling) overhead omega_fixed P_d_bus0 is present; <= 0 "
                                                 "means that no positive source cost pays",
                      "keys": "case|eta_u0|eta_b|eta_v; add_only and cost_offset are independent of eta_v"}}


def dimensional():
    """delta_eta_u* over species x V_d x mdot x eta_u0 x eta_b x case x P_source (4 significant digits)."""
    table, d_eta = [], []
    cases = list(CASES)
    for sp in SPECIES:
        A = []
        for V in V_D:
            A1 = []
            for md in MDOT_MG_S:
                A2 = []
                for u0 in ETA_U0:
                    A3 = []
                    for eb in ETA_B:
                        ref = reference(sp, V, md * 1e-6, u0, eb, ETA_V_REF, GAMMA_REF, ETA_PPU_D)
                        h = b.hall_only_state(ref)
                        table.append([sp, V, md, u0, eb, g6(h["I_b_A"]), g6(h["P_d_bus_W"]),
                                      g6(h["Pi_H_bus_W_per_A"]), h["P_d_bus_W"] <= RFP.power_max_W])
                        A4 = []
                        for case in cases:
                            r = response(case, ref)
                            xs = []
                            for P in P_SOURCE_W_DIM:
                                out = b.required_utilization_gain(ref, r, overhead(P))
                                xs.append(g4(out["delta_eta_u_star"]) if out["status"].startswith("OK") else None)
                            A4.append(xs)
                        A3.append(A4)
                    A2.append(A3)
                A1.append(A2)
            A.append(A1)
        d_eta.append(A)
    return {"axes": {"species": list(SPECIES), "V_d_V": V_D, "mdot_mg_s": MDOT_MG_S, "eta_u0": ETA_U0,
                     "eta_b": ETA_B, "case": cases, "P_source_bus_W": P_SOURCE_W_DIM},
            "index_order": ["species", "V_d_V", "mdot_mg_s", "eta_u0", "eta_b", "case", "P_source_bus_W"],
            "delta_eta_u_star": d_eta,
            "C_del_star_bus_W_per_A": "exact, not stored: P_source * eta_u0 / (delta_eta_u_star * I_b0_A) for "
                                      "P_source > 0 (alpha = 1 in every case; I_b0_A from hall_reference_table); at "
                                      "P_source = 0 it is Pi_H_bus_W_per_A * universal.marginal_C_del_star_over_Pi_H",
            "C_src_star": "C_src*(eta_t) = eta_t * C_del_star_bus_W_per_A for every eta_t in inputs.eta_transport",
            "null_means": "no break-even: overhead >= Hall-only discharge bus power (omega >= 1) or the required gain "
                          "exceeds the utilization cap (eta_u <= 1)",
            "hall_reference_table": {
                "columns": ["species", "V_d_V", "mdot_mg_s", "eta_u0", "eta_b", "I_b0_A", "P_d_bus0_W",
                            "Pi_H_bus_W_per_A", "P_d_bus0_within_RFP_power_cap"], "rows": table}}


# ------------------------------------------------------------------------------------------------ self-checks
def self_checks(uni, dim):
    out = {}
    # (1) both conventions evaluated independently at delta_s* (sample of the dimensional grid)
    worst_T = worst_P = worst_L = worst_E = 0.0
    n = 0
    for i, sp in enumerate(SPECIES):
        for V in V_D[::3]:
            for md in MDOT_MG_S[::2]:
                for u0 in ETA_U0:
                    for eb in ETA_B:
                        ref = reference(sp, V, md * 1e-6, u0, eb, ETA_V_REF, GAMMA_REF, ETA_PPU_D)
                        for case in CASES:
                            r = response(case, ref)
                            for P in P_SOURCE_W[1::4]:
                                o = b.required_utilization_gain(ref, r, overhead(P))
                                if not o["status"].startswith("OK"):
                                    continue
                                e = b.evaluate_arm(ref, r, overhead(P), o["delta_s_star"])
                                worst_T = max(worst_T, abs(e["equal_thrust"]["net_bus_saving_W"]) / P)
                                worst_P = max(worst_P, abs(e["equal_bus_power"]["thrust_gain_fraction"]))
                                worst_L = max(worst_L, abs(e["equal_thrust"]["ledger_residual_W"]),
                                              abs(e["equal_bus_power"]["ledger_residual_W"]))
                                worst_E = max(worst_E, abs(e["equal_thrust"]["eta_a_residual"]),
                                              abs(e["equal_bus_power"]["eta_a_residual"]))
                                n += 1
    out["conventions_coincide_at_breakeven"] = {
        "samples": n, "max_abs_equal_thrust_net_saving_over_overhead": worst_T,
        "max_abs_equal_bus_power_thrust_gain": worst_P, "max_abs_ledger_residual_W": worst_L,
        "max_abs_eta_a_identity_residual": worst_E,
        "pass": worst_T < 1e-9 and worst_P < 1e-9 and worst_L < 1e-9 and worst_E < 1e-12}
    # (2) add-only closed form
    dev = 0.0
    for key, xs in uni["delta_eta_u_star_over_eta_u0"].items():
        if key.startswith("add_only"):
            for w, x in zip(uni["omega"], xs):
                if x is not None:
                    dev = max(dev, abs(x - w / (1.0 - w)) / max(1.0, w / (1.0 - w)))
    out["add_only_closed_form"] = {"formula": "delta_eta_u*/eta_u0 = omega/(1-omega)", "max_rel_dev": dev,
                                   "tolerance": "5e-5 (stored values rounded to 5 significant digits)",
                                   "pass": dev < 5e-5}
    # (3) eta_v, gamma and species independence of the same-mix cases (add_only, cost_offset)
    dev = 0.0
    for sp in SPECIES:
        for case in ("add_only", "cost_offset"):
            for P in (50.0, 200.0):
                a = reference(sp, 300.0, 1e-6, 0.6, 0.7, ETA_V_REF, GAMMA_REF, ETA_PPU_D)
                c = reference(sp, 300.0, 1e-6, 0.6, 0.7, 0.6, 0.6, ETA_PPU_D)
                xa = b.required_utilization_gain(a, response(case, a), overhead(P))["delta_eta_u_star"]
                xc = b.required_utilization_gain(c, response(case, c), overhead(P))["delta_eta_u_star"]
                if xa is not None:
                    dev = max(dev, abs(xa - xc) / xa)
    for case in ("add_only", "cost_offset"):
        for sp in ("O", "Xe"):
            a = reference("N2", 300.0, 1e-6, 0.6, 0.7, ETA_V_REF, GAMMA_REF, ETA_PPU_D)
            c = reference(sp, 300.0, 1e-6, 0.6, 0.7, ETA_V_REF, GAMMA_REF, ETA_PPU_D)
            wa = 0.1 * b.hall_only_state(a)["P_d_bus_W"]
            wc = 0.1 * b.hall_only_state(c)["P_d_bus_W"]
            xa = b.required_utilization_gain(a, response(case, a), overhead(wa))["delta_eta_u_star"]
            xc = b.required_utilization_gain(c, response(case, c), overhead(wc))["delta_eta_u_star"]
            dev = max(dev, abs(xa - xc) / xa)
    out["same_mix_independent_of_eta_v_gamma_species_at_fixed_omega"] = {"max_rel_dev": dev, "pass": dev < 1e-12}
    # (4) the optimistic corner dominates the declared box (sup of the delivered-ion break-even cost)
    worst = -math.inf
    for u0 in ETA_U0:
        for eb in ETA_B:
            for ev in ETA_V_SET[:-1]:
                ref = reference("N2", 300.0, 1e-6, u0, eb, ev, GAMMA_REF, ETA_PPU_D)
                corner = b.supremum_breakeven_delivered_cost(ref, response("optimistic_bound", ref), 0.0, 64)
                for al in (0.0, 0.5, 1.0):
                    for ch in (0.0, 0.5, 1.0):
                        for evs in (ev, 0.5 * (ev + 1.0), 1.0):
                            r = b.PreionResponse(alpha=al, chi=ch, eta_v_delivered=evs, mix_delivered=ref.mix)
                            s = b.supremum_breakeven_delivered_cost(ref, r, 0.0, 64)["sup_W_per_A"]
                            worst = max(worst, s / corner["sup_W_per_A"] - 1.0)
    out["optimistic_corner_dominates_box"] = {"box": "alpha, chi in {0, 0.5, 1}; eta_v_S in {eta_v, mid, 1}",
                                              "max_excess_over_corner": worst, "pass": worst <= 1e-9}
    # (5) limiting case P_source = 0 and monotonicity in P_source
    zero_ok, mono_ok = True, True

    def walk(node, depth):
        nonlocal zero_ok, mono_ok
        if depth == 6:
            if node[0] != 0.0:
                zero_ok = False
            seen_none = False
            prev = -1.0
            for x in node:
                if x is None:
                    seen_none = True
                    continue
                if seen_none or x < prev:
                    mono_ok = False
                prev = x
            return
        for child in node:
            walk(child, depth + 1)
    walk(dim["delta_eta_u_star"], 0)
    out["zero_source_power_needs_zero_gain"] = {"pass": zero_ok}
    out["monotone_in_P_source_and_infeasible_stays_infeasible"] = {"pass": mono_ok}
    out["all_pass"] = all(v["pass"] for v in out.values())
    return out


# ------------------------------------------------------------------------------------------------ evidence overlay
def load_overlay_points(paths):
    """Read RF/ECR evidence matrices READ-ONLY; select published ion-cost points by explicit rules."""
    matrices, points, excluded = [], [], []
    for p in paths:
        d = json.load(open(p))
        mid = d.get("matrix_id") or d.get("schema") or os.path.basename(p)
        ap = os.path.abspath(p).replace(os.sep, "/")
        k = ap.find("/docs/evidence/")
        repo_rel = ap[k + 1:] if k >= 0 else os.path.basename(ap)
        wt = re.search(r"/\.claude/worktrees/([^/]+)/", ap)
        matrices.append({"path": repo_rel, "read_from": ("unmerged worktree " + wt.group(1)) if wt else "this checkout",
                         "matrix_id": mid, "version": d.get("matrix_version"), "sha256": sha256_file(p)})
        for e in d.get("entries", []):
            q = str(e.get("quantity", ""))
            ql = q.lower()
            if e.get("units") != "W/A":
                continue
            gas = (e.get("conditions") or {}).get("gas")
            reason = None
            if "electron" in ql:
                reason = "electron current (cathode), not an ion production cost"
            elif "ion" not in ql and "beam current" not in ql:
                reason = "not an ion-current basis"
            elif gas is None:
                reason = "no gas/device condition (unit identity or definition)"
            v = e.get("value")
            if isinstance(v, (int, float)):
                lo = hi = float(v)
            elif isinstance(v, dict) and "min" in v and "max" in v:
                lo, hi = float(v["min"]), float(v["max"])
            elif isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v):
                lo, hi = float(min(v)), float(max(v))
            else:
                reason = reason or f"value not numeric ({type(v).__name__})"
            if reason:
                excluded.append({"id": e.get("id"), "reason": reason})
                continue
            src = e.get("source") or {}
            points.append({"id": e.get("id"), "matrix_id": mid, "quantity": q, "value_W_per_A": [lo, hi],
                           "evidence_class": e.get("evidence_class"), "evidence_level": e.get("evidence_level"),
                           "access": src.get("access"), "gas": gas, "uncertainty": e.get("uncertainty"),
                           "regime_match": (e.get("applicability_to_abep") or {}).get("regime_match"),
                           "citation": src.get("citation"), "doi_or_url": src.get("doi_or_url")})
    return matrices, points, excluded


REF_POINTS = [(V, eb) for V in (150.0, 300.0, 450.0) for eb in ETA_B]


AIR_GASES = ("N2", "O2", "O ", "air")


def gas_group(gas: str) -> str:
    g = f"{gas} "
    return "air_species" if any(k in g for k in AIR_GASES) else "noble_gas"


def overlay(paths):
    matrices, points, excluded = load_overlay_points(paths)
    placed = []
    for pt in points:
        rows = []
        for V, eb in REF_POINTS:
            ref = reference("N2", V, 1e-6, 0.6, eb, ETA_V_REF, GAMMA_REF, ETA_PPU_D)
            for case in CASES:
                sup = b.marginal_breakeven_delivered_cost(ref, response(case, ref))
                rows.append({"V_d_V": V, "eta_b": eb, "case": case, "sup_C_del_star_W_per_A": g6(sup),
                             "eta_t_needed_as_reported": [g6(pt["value_W_per_A"][0] / sup),
                                                          g6(pt["value_W_per_A"][1] / sup)],
                             "reported_value_above_sup": pt["value_W_per_A"][0] > sup})
        placed.append(dict(pt, gas_group=gas_group(pt["gas"]), placement=rows))
    return {"status": "PRELIMINARY - evidence matrices read READ-ONLY from other lanes' worktrees before they merged; "
                      "regenerate after merge. Indicative only: no elimination and no architecture conclusion is "
                      "drawn from this file.",
            "breakeven_version": b.BREAKEVEN_VERSION, "matrices": matrices,
            "selection_rules": ["units == 'W/A'", "quantity mentions an ion or beam current and not an electron current",
                                "a gas/device condition is stated", "numeric value, range or list"],
            "excluded": excluded,
            "placement_rule": "Reported values are placed as published: on the source's own power reference "
                              "(generator input, incident or transmitted microwave power, ...) and ion basis "
                              "(grid-extracted beam or plume current). Two conversions are missing (TBD): (a) referring "
                              "the power to the bus can only RAISE the cost (chain efficiency <= 1); (b) changing the "
                              "ion basis to ions leaving a gridless pre-ionizer can LOWER it (no grid interception, "
                              "e.g. division by the grid transparency). With both unknown, 'eta_t_needed_as_reported' "
                              "= reported / sup C_del* is neither an upper nor a lower bound, and "
                              "'reported_value_above_sup' is indicative only. Gas, device and regime transfer are "
                              "further limits (regime_match; noble-gas points do not describe the air arm).",
            "reference_points": {"species_mix": "N2+ (C_del* is per ampere and does not depend on the species when "
                                                "delivered and Hall ions share the mix)", "eta_u0": 0.6,
                                 "eta_v": ETA_V_REF, "eta_ppu_discharge": ETA_PPU_D, "fixed_overhead_W": 0.0},
            "points": placed}


# ------------------------------------------------------------------------------------------------ figures / CSV
STYLE = {"surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "grid": "#e4e3df",
         "ramp": ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"],
         "cat": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]}


def _axes_style(ax):
    ax.set_facecolor(STYLE["surface"])
    ax.grid(True, color=STYLE["grid"], lw=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(STYLE["ink2"])
    ax.tick_params(colors=STYLE["ink2"], labelsize=8)
    ax.xaxis.label.set_color(STYLE["ink"])
    ax.yaxis.label.set_color(STYLE["ink"])


def figures(uni, dim, ov=None):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return write_csv(uni, dim)
    plt.rcParams.update({"font.size": 9, "svg.hashsalt": "breakeven_v1"})
    files = []
    meta = {"Software": None}
    note = "breakeven_v1 - analysis ranges, not predictions"

    # F1 universal required gain
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=150)
    fig.patch.set_facecolor(STYLE["surface"])
    _axes_style(ax)
    w = uni["omega"]
    series = [("add_only|eta_u0=0.6|eta_b=0.7|eta_v=0.9", "add-only (any eta_b)", STYLE["ink2"], "--")]
    for i, eb in enumerate((0.9, 0.7, 0.5)):
        series.append((f"cost_offset|eta_u0=0.6|eta_b={eb}|eta_v=0.9", f"cost-offset, eta_b = {eb}",
                       STYLE["ramp"][i + 1], "-"))
    for key, lab, col, ls in series:
        ys = uni["delta_eta_u_star_over_eta_u0"][key]
        xs = [a for a, y in zip(w, ys) if y is not None]
        ax.plot(xs, [y for y in ys if y is not None], color=col, lw=1.6, ls=ls, label=lab)
    for u0 in ETA_U0:
        cap = (1 - u0) / u0
        ax.axhline(cap, color=STYLE["ink2"], lw=0.8, ls=":")
        ax.text(0.695, cap, f"utilization cap, eta_u0 = {u0} ", va="bottom", ha="right", fontsize=7,
                color=STYLE["ink2"])
    ax.set_xlim(0, 0.7)
    ax.set_ylim(0, 2.5)
    ax.set_xlabel("omega = bus overhead / Hall-only discharge bus power")
    ax.set_ylabel("required gain  delta_eta_u* / eta_u0")
    ax.set_title("Required utilization gain (both conventions; independent of eta_v, gamma, species)", fontsize=9,
                 color=STYLE["ink"], loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper center")
    fig.text(0.99, 0.01, note, ha="right", fontsize=6, color=STYLE["ink2"])
    fig.tight_layout()
    p = os.path.join(OUT_DIR, "fig_required_gain_universal.png")
    if ov is None:
        fig.savefig(p, metadata=meta, facecolor=STYLE["surface"])
        files.append(p)
    plt.close(fig)

    # F2 break-even source ion cost vs eta_t (marginal = supremum with no fixed overhead)
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=150)
    fig.patch.set_facecolor(STYLE["surface"])
    _axes_style(ax)
    et = [0.0] + ETA_T
    for i, V in enumerate((150.0, 300.0, 450.0)):
        ref = reference("N2", V, 1e-6, 0.6, 0.7, ETA_V_REF, GAMMA_REF, ETA_PPU_D)
        for case, ls in (("optimistic_bound", "-"), ("add_only", "--")):
            c = b.marginal_breakeven_delivered_cost(ref, response(case, ref))
            ax.plot(et, [x * c for x in et], color=STYLE["ramp"][i + 1], lw=1.6, ls=ls,
                    label=f"V_d = {V:.0f} V, {case.replace('_', ' ')}")
    if ov:                           # published points as reported (basis not converted): horizontal marks, labelled
        pts = sorted(ov["points"], key=lambda p: p["value_W_per_A"][0])
        y_lab = []
        for pt in pts:
            lo, hi = pt["value_W_per_A"]
            col = STYLE["cat"][1] if pt["gas_group"] == "air_species" else STYLE["ink2"]
            ls = ":" if pt["evidence_class"] == "model-derived" else "-"
            if hi > lo:
                ax.axhspan(lo, min(hi, 1100.0), xmin=0.0, xmax=1.0, color=col, alpha=0.08, lw=0)
            ax.axhline(lo, color=col, lw=0.9, ls=ls, alpha=0.9)
            y = lo if not y_lab else max(lo, y_lab[-1] + 24.0)
            y_lab.append(y)
            ax.annotate(f"{pt['id']} ({pt['gas'].split(',')[0].split(' by')[0]}"
                        f"{', to ' + format(hi, '.0f') if hi > lo else ''})", xy=(1.0, lo), xytext=(1.01, y),
                        textcoords="data", fontsize=6, color=col, va="center", annotation_clip=False,
                        arrowprops={"arrowstyle": "-", "color": col, "lw": 0.5})
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1100)
    ax.set_xlabel("eta_transport (source ions -> accelerated in the Hall beam)")
    ax.set_ylabel("max. source production cost C_src* [bus W per A]")
    ax.set_title("Break-even source ion cost: above a line the source cannot pay at that Hall point\n"
                 "(eta_b = 0.7, eta_v = 0.9, eta_ppu,d = 0.9, no fixed overhead)", fontsize=9, color=STYLE["ink"],
                 loc="left")
    ax.legend(frameon=False, fontsize=7, loc="upper left", ncol=2)
    if ov:
        fig.set_size_inches(8.6, 5.2)
        ax.set_title("PRELIMINARY overlay: published ion costs AS REPORTED (power reference and ion basis not converted;"
                     "\nindicative only). Orange: N2/O2/air; grey: noble gas; dotted: model-derived", fontsize=8,
                     color=STYLE["ink"], loc="left")
        fig.text(0.99, 0.01, note + "; overlay read from unmerged evidence lanes", ha="right", fontsize=6,
                 color=STYLE["ink2"])
        fig.tight_layout(rect=(0, 0, 0.84, 1))
    else:
        fig.text(0.99, 0.01, note, ha="right", fontsize=6, color=STYLE["ink2"])
        fig.tight_layout()
    p = os.path.join(OUT_DIR, "fig_evidence_overlay_prelim.png" if ov else "fig_breakeven_ion_cost.png")
    fig.savefig(p, metadata=meta, facecolor=STYLE["surface"])
    plt.close(fig)
    files.append(p)
    if ov:
        return files

    # F3 required gain vs P_source by species (slice)
    ax_i = dim["axes"]
    iV, im, iu, ib = ax_i["V_d_V"].index(300.0), ax_i["mdot_mg_s"].index(1.0), ax_i["eta_u0"].index(0.6), \
        ax_i["eta_b"].index(0.7)
    fig, axs = plt.subplots(1, 2, figsize=(9.0, 4.0), dpi=150, sharey=True)
    fig.patch.set_facecolor(STYLE["surface"])
    for k, case in enumerate(("add_only", "cost_offset")):
        ax = axs[k]
        _axes_style(ax)
        ic = ax_i["case"].index(case)
        for i, sp in enumerate(ax_i["species"]):
            ys = dim["delta_eta_u_star"][i][iV][im][iu][ib][ic]
            xs = [P for P, y in zip(ax_i["P_source_bus_W"], ys) if y is not None]
            ax.plot(xs, [y for y in ys if y is not None], color=STYLE["cat"][i], lw=1.6, marker="o", ms=3,
                    label=SPECIES[sp][0])
        ax.axhline(0.4, color=STYLE["ink2"], lw=0.8, ls=":")
        ax.text(5, 0.4, " cap: 1 - eta_u0", va="bottom", fontsize=7, color=STYLE["ink2"])
        ax.set_ylim(0, 0.45)
        ax.set_xlabel("pre-ionizer bus overhead O [W]")
        ax.set_title(case.replace("_", " "), fontsize=9, color=STYLE["ink"], loc="left")
    axs[0].set_ylabel("required delta_eta_u*")
    axs[0].legend(frameon=False, fontsize=8, loc="upper center")
    fig.suptitle("Required utilization gain by species (slice: V_d 300 V, mdot 1 mg/s, eta_u0 0.6, eta_b 0.7, "
                 "eta_ppu,d 0.9)", fontsize=9, x=0.01, ha="left", color=STYLE["ink"])
    fig.text(0.99, 0.01, note + "; line ends where no break-even exists", ha="right", fontsize=6, color=STYLE["ink2"])
    fig.tight_layout()
    p = os.path.join(OUT_DIR, "fig_required_gain_by_species.png")
    fig.savefig(p, metadata=meta, facecolor=STYLE["surface"])
    plt.close(fig)
    files.append(p)

    # F4 C_src*(eta_t, P_source) map, N2 slice
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue_seq", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.8), dpi=150, sharey=True)
    fig.patch.set_facecolor(STYLE["surface"])
    ref = reference("N2", 300.0, 1e-6, 0.6, 0.7, ETA_V_REF, GAMMA_REF, ETA_PPU_D)
    for k, case in enumerate(ax_i["case"]):
        ax = axs[k]
        _axes_style(ax)
        r = response(case, ref)
        cd = []                                   # C_del*(P_source), same function as the stored surfaces
        for P in P_SOURCE_W:
            o = b.required_utilization_gain(ref, r, overhead(P))
            if not o["status"].startswith("OK"):
                cd.append(None)
            elif P == 0.0:
                cd.append(b.marginal_breakeven_delivered_cost(ref, r))
            else:
                cd.append(P / (o["delta_s_star"] * ref.mdot_kg_s * r.mix_delivered.coulomb_per_kg))
        Z = np.array([[np.nan if c is None else e * c for c in cd] for e in ETA_T])
        mesh = ax.pcolormesh(P_SOURCE_W, ETA_T, Z, cmap=cmap, vmin=0, vmax=650, shading="nearest")
        cs = ax.contour(P_SOURCE_W, ETA_T, Z, levels=[100, 200, 300, 400, 500], colors=STYLE["ink"],
                        linewidths=0.6)
        ax.clabel(cs, fontsize=6, fmt="%d")
        ax.set_xlabel("pre-ionizer bus power [W]")
        ax.set_title(case.replace("_", " "), fontsize=9, color=STYLE["ink"], loc="left")
    axs[0].set_ylabel("eta_transport")
    cb = fig.colorbar(mesh, ax=axs, shrink=0.9)
    cb.set_label("C_src* [bus W per A produced]", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    fig.suptitle("Max. source production cost that still breaks even, N2+ (slice: V_d 300 V, mdot 1 mg/s, eta_u0 0.6, "
                 "eta_b 0.7)", fontsize=9, x=0.01, ha="left", color=STYLE["ink"])
    p = os.path.join(OUT_DIR, "fig_source_cost_map_N2.png")
    fig.savefig(p, metadata=meta, facecolor=STYLE["surface"])
    plt.close(fig)
    files.append(p)
    return files


def write_csv(uni, dim):
    files = []
    p = os.path.join(OUT_DIR, "surfaces_universal_required_gain.csv")
    with open(p, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["key", "omega", "delta_eta_u_star_over_eta_u0", "C_del_star_over_Pi_H"])
        for key, xs in uni["delta_eta_u_star_over_eta_u0"].items():
            for w, x, c in zip(uni["omega"], xs, uni["C_del_star_over_Pi_H"][key]):
                wr.writerow([key, w, x, c])
    files.append(p)
    return files


# ------------------------------------------------------------------------------------------------ assembly
def compact(text: str) -> str:
    """Put innermost numeric lists on one line (readability of the committed JSON)."""
    pat = re.compile(r"\[\s*((?:-?[0-9.eE+-]+|null|true|false)(?:,\s*(?:-?[0-9.eE+-]+|null|true|false))*)\s*\]")
    return pat.sub(lambda m: "[" + re.sub(r",\s*", ", ", m.group(1)) + "]", text)


def build():
    uni = universal()
    dim = dimensional()
    checks = self_checks(uni, dim)
    t_min, t_max, p_max = RFP.thrust_min_mN * 1e-3, RFP.thrust_max_mN * 1e-3, RFP.power_max_W
    mdot_abs_min = t_min ** 2 / (2.0 * p_max)
    eta_a_at_top = t_max ** 2 / (2.0 * MDOT_MG_S[-1] * 1e-6 * p_max)
    doc = {
        "id": "breakeven_surfaces_v1", "breakeven_version": b.BREAKEVEN_VERSION,
        "status": "Analysis surfaces over declared ranges. NOT predictions, NOT an architecture ranking; no Hall "
                  "closure, screening candidate or absolute Hall number is used. Hall-only efficiency components are "
                  "analysis parameters.",
        "milestones": b.MILESTONE_SUPPORT,
        "boundary": {"version": b.BOUNDARY_VERSION, "common_components": list(b.COMMON_COMPONENTS),
                     "source_components": b.SOURCE_COMPONENTS,
                     "note": "the common feed state (mdot, species) is identical for hall_only, rf_hall, ecr_hall; "
                             "Hall-closure uncertainty is confined to the ionization/acceleration block and never "
                             "enters intake, compressor, gas chambers or valves."},
        "per_architecture": {
            "rf_hall": {"overhead_O": "P_bus[rf_source] + sum over common components (P_bus,arm - P_bus,hall_only) "
                                      "except hall_discharge (+ interstage, extra PPU: 0 in a v1-conformant ledger)",
                        "ion_cost_split": "generator = rf_source; fixed = everything else"},
            "ecr_hall": {"overhead_O": "P_bus[ecr_source] + P_bus[ecr_magnet] + common deltas (+ interstage, extra "
                                       "PPU: 0 in a v1-conformant ledger)",
                         "ion_cost_split": "generator = ecr_source; fixed = ecr_magnet + everything else "
                                           "(an electromagnet lowers the payable cost: see "
                                           "sup_C_del_star_over_Pi_H_with_fixed_overhead)"},
            "reading": "the surfaces are functions of the total overhead O; read the P_source axis at O."},
        "cases": CASES,
        "inputs": {
            "species": {"values": {k: {"ion": v[0], "mass_amu": g6(v[1])} for k, v in SPECIES.items()},
                        "status": "analysis mixes: single species, singly charged (real beams mix N2+/N+/O+/NO+ and "
                                  "multiply charged ions; supported by the module, not scanned)",
                        "masses": ATOMIC_WEIGHTS_SOURCE},
            "P_source_bus_W": {"values_stored": P_SOURCE_W_DIM, "values_figures": P_SOURCE_W,
                               "status": PROPOSED + "; span requested by the owner (0-500 W); read as the total "
                                         "overhead O"},
            "eta_transport": {"values": ETA_T, "status": PROPOSED + "; span requested by the owner (0.1-1)"},
            "V_d_V": {"values": V_D, "status": PROPOSED, "context": CONTEXT["P5_N2_V_d"]},
            "mdot_mg_s": {"values": MDOT_MG_S, "status": PROPOSED,
                          "rfp_bracket": {"thrust_mN": [RFP.thrust_min_mN, RFP.thrust_max_mN],
                                          "power_max_W": p_max,
                                          "source": "RFP DTDF/06/13516 Part III Para 2 as encoded in "
                                                    "abep_sim/constants.py RFPConstraints",
                                          "mdot_absolute_min_mg_s": g6(mdot_abs_min * 1e6),
                                          "mdot_absolute_min_rule": "T_min^2 / (2 P_max) with eta_a <= 1 (definition)",
                                          "eta_a_needed_at_mdot_max_for_T_max_at_P_max": g6(eta_a_at_top),
                                          "reading": "the range starts above the definitional minimum and its top end "
                                                     "corresponds to eta_a ~ 4 % at 25 mN and 1.5 kW"}},
            "eta_u0": {"values": ETA_U0, "status": PROPOSED, "context": CONTEXT["NASA173Mv2_Xe_components"]},
            "eta_b": {"values": ETA_B, "status": PROPOSED},
            "eta_v": {"values_universal_optimistic": ETA_V_SET, "value_dimensional": ETA_V_REF,
                      "status": PROPOSED + "; add_only and cost_offset do not depend on eta_v (self-check 3)"},
            "gamma_div": {"value": GAMMA_REF, "status": PROPOSED + "; no break-even quantity depends on it "
                                                                   "(self-check 3)"},
            "eta_ppu_discharge": {"value": ETA_PPU_D,
                                  "status": PROPOSED + "; enters only via P_d_bus0 = P_d/eta and Pi_H = "
                                            "V_d/(eta_b eta): another value equals rescaling V_d by 0.9/eta"},
            "omega": {"values": "0 to 0.95 step 0.005", "status": "dimensionless axis"},
            "omega_fixed": {"values": OMEGA_FIXED, "status": PROPOSED},
        },
        "universal": uni,
        "dimensional": dim,
        "evidence_placement": {
            "procedure": ["convert the published cost to bus W per A with bus_referred_source_cost (power reference "
                          "absorbed/forward/bus; eV/ion / mean charge); every chain efficiency explicit",
                          "pair it with eta_transport on the SAME ion basis (produced / source-exit / extracted -> "
                          "accelerated in the Hall beam)",
                          "C_del = C_src / eta_t; compare with C_del* = Pi_H * c(omega) (universal) or the "
                          "dimensional C_del_star_bus_W_per_A; the supremum over any spend is the marginal value "
                          "Pi_H * marginal_C_del_star_over_Pi_H when there is no fixed overhead",
                          "C_del above the optimistic_bound supremum: cannot pay in power at that Hall point within "
                          "the model family (milestone-A elimination candidate, conditional on the assumptions)",
                          "place_evidence() returns the payable delivered-share interval and the minimum eta_t"],
            "overlay": "none in this file (reproducible from the repository alone); a PRELIMINARY overlay is "
                       "written to " + OVERLAY_JSON + " only when --evidence-matrix is given",
        },
        "mass_breakeven": {"inequality": "s_P * dP_bus_saved (equal thrust) or s_T * dT (equal bus power) - "
                                         "dm_propellant >= m_source_head + m_generator_PPU + m_magnets + "
                                         "m_interstage + m_thermal_added",
                           "inputs": {"s_P_kg_per_W": "TBD - requires power-system sizing (arrays, PCDU, thermal) at "
                                                      "the mission point (milestone C)",
                                      "s_T_kg_per_N": "TBD - requires mission/drag closure",
                                      "hardware masses": "TBD - requires source, PPU and magnet designs with evidence",
                                      "dm_propellant": "0 for the air arm by definition (no stored air); TBD for the "
                                                       "Xe mode"},
                           "surface": "none (no sourced sensitivities); function mass_breakeven() evaluates it once "
                                      "the inputs exist"},
        "life_breakeven": {"inequalities": ["min(arm limits) >= min(hall_only limits)  (life break-even)",
                                            "min(arm limits) >= k_q * t_fire,req  (requirement; t_fire,req = "
                                            f"{RFP.ignition_hours:.0f} h from the RFP, k_q PROPOSED/TBD)"],
                           "inputs": "Hall wall erosion life at both operating points (J_i Y(eps_i), G&K Eq. 7.5-1; "
                                     "needs wall_life_trustworthy Hall maps), source life limits (RF window/antenna "
                                     "erosion and coating, generator; ECR window, magnets, microwave generator), "
                                     "cathode, PPU: all TBD", "surface": "none"},
        "self_checks": checks,
        "provenance": {"script": REL(os.path.abspath(__file__)), "module": "abep_sim/breakeven.py",
                       "module_sha256": sha256_file(os.path.join(ROOT, "abep_sim", "breakeven.py")),
                       "derivation": "docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md",
                       "reading_guide": "docs/architecture_comparison/breakeven/BREAKEVEN_SURFACES.md"},
    }
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evidence-matrix", action="append", default=[],
                    help="RF/ECR evidence matrix JSON to overlay READ-ONLY (writes the PRELIMINARY overlay file)")
    ap.add_argument("--check", action="store_true", help="rebuild in memory and compare with the committed JSON")
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    text = compact(json.dumps(doc, indent=1, sort_keys=False)) + "\n"
    out = os.path.join(OUT_DIR, OUT_JSON)
    if a.check:
        same = open(out).read() == text
        print("breakeven_surfaces_v1.json reproduces" if same else "MISMATCH with the committed JSON")
        return 0 if same else 1
    if not doc["self_checks"]["all_pass"]:
        print(json.dumps(doc["self_checks"], indent=1))
        raise SystemExit("self-checks failed; nothing written")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out, "w") as f:
        f.write(text)
    print(f"wrote {REL(out)} ({len(text) / 1e3:.0f} kB)")
    if not a.no_figures:
        for p in figures(doc["universal"], doc["dimensional"]):
            print(f"wrote {REL(p)}")
    if a.evidence_matrix:
        ov = overlay(a.evidence_matrix)
        p = os.path.join(OUT_DIR, OVERLAY_JSON)
        with open(p, "w") as f:
            f.write(compact(json.dumps(ov, indent=1)) + "\n")
        print(f"wrote {REL(p)} (PRELIMINARY)")
        if not a.no_figures:
            for q in figures(doc["universal"], doc["dimensional"], ov):
                print(f"wrote {REL(q)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
