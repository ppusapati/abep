"""Compose the H-1 FE B(z) record (h1_bz_fe_v1.json / H1_BZ_FE_v1.md) and the HallThruster.jl profile files from the
stage outputs of build_h1_bz_fe.py, applying the preregistered evaluation rules (h1_bz_fe_prereg_v4.json) unchanged.

Usage: python emit_h1_bz_fe.py --work DIR [--check]
Pure composition: no FE solve. The stage outputs are copied into docs/hardware/h1_bz/runs/ (gzip-free JSON) so the record is
reproducible from repository content: python emit_h1_bz_fe.py --work docs/hardware/h1_bz/runs --check
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
PREREG = os.path.join(HERE, "h1_bz_fe_prereg_v4.json")
LOCK = os.path.join(HERE, "h1_bz_fe_prereg_lock_v4.json")
OUT_JSON = os.path.join(HERE, "h1_bz_fe_v1.json")
OUT_MD = os.path.join(HERE, "H1_BZ_FE_v1.md")
RUNS = os.path.join(HERE, "runs")
BF_REL = "hallthruster_bridge/bfield/h1_fe_v1"
BF = os.path.join(ROOT, BF_REL)
SURR_REL = "hallthruster_bridge/bfield/p5_vacuum_Br_centerline_1p6kW.csv"
B_SAT = {"hiperco": 2.30, "iron": 2.15}  # h2_1 /materials (SRC-HIPERCO50 p. 3, SRC-ARMCO p. 9)
KEYS = ["z_peak_minus_L_mm", "B_anode_over_B_peak", "B_exit_over_B_peak", "FWHM_mm", "L_up_mm", "L_down_mm",
        "B_at_L_plus_domain_over_B_peak", "NI_A"]


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def shab(b):
    return hashlib.sha256(b).hexdigest()


def r4(x):
    if x is None:
        return None
    if isinstance(x, float):
        return float(f"{x:.6g}")
    return x


def clean(d):
    if isinstance(d, dict):
        return {k: clean(v) for k, v in d.items()}
    if isinstance(d, list):
        return [clean(v) for v in d]
    return r4(d)


def surrogate(P, z):
    rows = [ln.strip().split(",") for ln in open(os.path.join(ROOT, SURR_REL)) if not ln.startswith("#") and ln.strip()][1:]
    zf = np.array([float(r[0]) for r in rows])
    bf = np.array([float(r[1]) for r in rows])
    reg = P["dcr_002_evaluation"]["surrogate_registration"]
    L = P["geometry"]["nominal"]["L_mm"]
    return np.interp(z, zf - reg["z_ref_in_file_mm"] + L, bf / bf.max())


def surrogate_descriptors(P):
    import build_h1_bz_fe as B
    L = P["geometry"]["nominal"]["L_mm"]
    z = np.arange(0.0, 2 * L + 1e-9, 0.1)
    return B.descriptors(z, surrogate(P, z) * 100.0, P)


def csv_text(P, prof, header):
    lines = ["# " + h for h in header] + ["z_from_anode_face_mm,Br_G"]
    for z, b in zip(prof["z_mm"], prof["Br_G"]):
        lines.append(f"{z:.2f},{b:.4f}")
    return "\n".join(lines) + "\n"


def build(work):
    P = json.load(open(PREREG))
    lock = json.load(open(LOCK))
    for rel, h in lock["files"].items():
        if sha(os.path.join(ROOT, rel)) != h:
            raise SystemExit(f"REFUSED: {rel} differs from the prereg lock")
    V = json.load(open(os.path.join(work, "verify.json")))
    C = json.load(open(os.path.join(work, "convergence.json")))
    import glob
    sweep_files = sorted(glob.glob(os.path.join(work, "sweep_*.json")))
    W = {"variants": {}, "exact": {}, "split": {}, "_meta": {}}
    for fp in sweep_files:
        part = json.load(open(fp))
        for k in ("variants", "exact", "split"):
            W[k].update(part.get(k, {}))
        W["_meta"][os.path.basename(fp)] = part.get("_meta")
    expected = ["NOM"] + [v["id"] for v in P["uncertainty"]["one_at_a_time"] + P["uncertainty"]["corners"]]
    missing = [v for v in expected if v not in W["exact"]]
    if missing:
        raise SystemExit(f"REFUSED: sweep results missing for {missing}")
    L = P["geometry"]["nominal"]["L_mm"]
    h = P["geometry"]["nominal"]["h_mm"]

    ver_pass = bool(V["all_pass"])
    conv = C["evaluation"]
    conv_pass = bool(conv["converged"])
    nom = W["variants"]["NOM"]
    ex = W["exact"]["NOM"]
    model_error = any(s.get("status") != "OK" for s in nom["sweep"]) or any(
        ex.get(k, {}).get("status") not in (None, "OK") for k in ("BP-LO", "BP-HI"))
    if not ver_pass:
        outcome = "FE_DERIVED_NOT_VERIFIED"
    elif not conv_pass:
        outcome = "NUMERICAL_CONVERGENCE_NOT_DEMONSTRATED"
    elif model_error:
        outcome = "MODEL_ERROR"
    else:
        outcome = "FE_DERIVED_VERIFIED"

    # numerical uncertainty (nominal |L2 - L3|, max over the convergence currents)
    num = {}
    for k in KEYS[:-1] + ["B_peak_G"]:
        dv = []
        for NI in P["convergence"]["NI_A"]:
            a, b = C["levels"]["L2"].get(str(NI), {}), C["levels"]["L3"].get(str(NI), {})
            if a.get(k) is not None and b.get(k) is not None:
                dv.append(abs(a[k] - b[k]) / (b["B_peak_G"] if k == "B_peak_G" else 1.0))
        num[k if k != "B_peak_G" else "B_peak_rel"] = max(dv) if dv else None

    # envelope at each level
    env = {}
    for lev in P["operating"]["B_peak_targets_G"]:
        rows = {vid: W["exact"][vid].get(lev, {}) for vid in W["exact"]}
        e = {}
        for k in KEYS:
            vals = [r[k] for r in rows.values() if r.get("status", "OK") == "OK" and r.get(k) is not None]
            if not vals:
                e[k] = None
                continue
            d = (num.get(k) or 0.0) if k != "NI_A" else (num.get("B_peak_rel") or 0.0) * max(vals)
            e[k] = {"min": min(vals) - d, "max": max(vals) + d, "nominal": rows["NOM"].get(k),
                    "argmin": min(rows, key=lambda v: rows[v].get(k, math.inf) if rows[v].get(k) is not None else math.inf),
                    "argmax": max(rows, key=lambda v: rows[v].get(k, -math.inf) if rows[v].get(k) is not None else -math.inf),
                    "numerical_widening": d}
        e["not_reached"] = [v for v, r in rows.items() if r.get("status") not in (None, "OK")]
        env[lev] = e

    # acceptance H1F-BZ-02
    A2 = P["acceptance"]["H1F-BZ-02"]
    import build_h1_bz_fe as B
    shape = {}
    for lev in ("BP-LO", "BP-HI", "CAP-403"):
        d = ex.get(lev, {})
        if d.get("status", "OK") == "OK" and "B_peak_G" in d:
            shape[lev] = B.shape_tests(d, P)
    s_ok = all(shape.get(l, {}).get("S1_monotonic_rise_to_peak") and shape.get(l, {}).get("S2_peak_at_or_just_downstream_of_L")
               for l in ("BP-LO", "BP-HI"))
    var_counts = {}
    for lev in ("BP-LO", "BP-HI"):
        n1 = n2 = n = 0
        for vid, rr in W["exact"].items():
            d = rr.get(lev, {})
            if d.get("status", "OK") == "OK" and "B_peak_G" in d:
                t = B.shape_tests(d, P)
                n += 1
                n1 += t["S1_monotonic_rise_to_peak"]
                n2 += t["S2_peak_at_or_just_downstream_of_L"]
        var_counts[lev] = {"variants": n, "S1_pass": n1, "S2_pass": n2}
    bz02 = {"outcome": "SHAPE_CONSISTENT" if s_ok else "SHAPE_INCONSISTENT", "per_level": shape,
            "envelope_counts": var_counts, "S2_window_mm": [A2["S2_peak_window_relative_to_L_in_h"][0] * h,
                                                           A2["S2_peak_window_relative_to_L_in_h"][1] * h]}

    # acceptance H1F-BZ-03
    R = P["operating"]["registered_ratings"]
    ni_hi = ex.get("BP-HI", {}).get("NI_A")
    ni_cap = ex.get("CAP-403", {}).get("NI_A")
    env_hi = env["BP-HI"]["NI_A"]
    bz03 = {
        "B1": {"NI_BP_HI_A": ni_hi, "limit_A": R["NI_total_RP1_fNI2_A"],
               "result": "BAND_REACHABLE_WITHIN_REGISTERED_COIL_NI" if (ni_hi and ni_hi <= R["NI_total_RP1_fNI2_A"]) else "NOT_MET"},
        "B2": {"NI_BP_HI_envelope_max_A": env_hi["max"] if env_hi else None, "limit_A": R["NI_total_RP1_fNI2_A"],
               "result": "BAND_REACHABLE_ACROSS_ENVELOPE" if (env_hi and not env["BP-HI"]["not_reached"]
                                                              and env_hi["max"] <= R["NI_total_RP1_fNI2_A"]) else "NOT_MET"},
        "B3": {"NI_CAP403_A": ni_cap, "limit_A": R["NI_total_RP1_worst_A"],
               "envelope_A": env["CAP-403"]["NI_A"], "not_reached_variants": env["CAP-403"]["not_reached"],
               "result": "CAPABILITY_WITHIN_REGISTERED_WORST_CASE_NI" if (ni_cap and ni_cap <= R["NI_total_RP1_worst_A"]) else "NOT_MET"},
    }
    coil_currents = {}
    for lev, d in ex.items():
        if d.get("NI_A"):
            ni = d["NI_A"]
            sp = P["operating"]["NI_split_inner"]
            ii, io = sp * ni / R["turns_fNI2"]["inner"], (1 - sp) * ni / R["turns_fNI2"]["outer"]
            coil_currents[lev] = {"NI_total_A": ni, "I_inner_A_at_357_turns": ii, "I_outer_A_at_157_turns": io,
                                  "inside_analog_1_5_A_window": bool(1.0 <= ii <= 5.0 and 1.0 <= io <= 5.0),
                                  "iron_Bmax_T": d.get("iron_Bmax_T"),
                                  "iron_Bmax_over_Bsat": {k: v / B_SAT[k] for k, v in (d.get("iron_Bmax_T") or {}).items()}}
    bz03["coil_currents_at_registered_turns"] = coil_currents

    # peak vs current (nominal L3 sweep)
    pvc = [{"NI_A": s["NI_A"], "B_peak_G": s.get("B_peak_G"), "z_peak_mm": s.get("z_peak_mm"),
            "B_anode_over_B_peak": s.get("B_anode_over_B_peak"), "G_per_A_turn": (s["B_peak_G"] / s["NI_A"]) if s.get("B_peak_G") else None,
            "iron_Bmax_T": s.get("iron_Bmax_T"), "status": s.get("status", "OK")} for s in nom["sweep"]]
    lin = pvc[0]["G_per_A_turn"]
    for row in pvc:
        row["linearity_vs_lowest_NI"] = (row["G_per_A_turn"] / lin) if (row["G_per_A_turn"] and lin) else None

    # surrogate comparison (DCR-002 evaluation)
    sd = surrogate_descriptors(P)
    zc = np.arange(0.0, L + P["outputs"]["domain_end_rule_mm_beyond_L"] + 1e-9, 0.5)
    comp = {}
    for lev in ("BP-LO", "BP-HI"):
        d = ex.get(lev)
        if not d or "profile" not in d:
            continue
        zf, bf = np.array(d["profile"]["z_mm"]), np.array(d["profile"]["Br_G"])
        fe_n = np.interp(zc, zf, bf) / d["B_peak_G"]
        su_n = surrogate(P, zc)
        diff = np.abs(fe_n - su_n)
        md = float(diff.max())
        comp[lev] = {"max_normalised_difference": md, "z_of_max_difference_mm": float(zc[int(np.argmax(diff))]),
                     "FE": {k: d.get(k) for k in ("B_anode_over_B_peak", "z_peak_minus_L_mm", "FWHM_mm", "L_up_mm", "L_down_mm",
                                                   "B_exit_over_B_peak")},
                     "surrogate_BZ_P5B16": {k: sd.get(k) for k in ("B_anode_over_B_peak", "z_peak_minus_L_mm", "FWHM_mm",
                                                                    "L_up_mm", "L_down_mm", "B_exit_over_B_peak")},
                     "delta_B_anode_over_B_peak": d["B_anode_over_B_peak"] - sd["B_anode_over_B_peak"],
                     "materiality_flag": "MATERIALLY_DIFFERENT" if (md > 0.10 or abs(d["B_anode_over_B_peak"] - sd["B_anode_over_B_peak"]) > 0.05)
                     else "NOT_MATERIALLY_DIFFERENT",
                     "flag_role": "informational only (prereg dcr_002_evaluation.materiality_flag)"}

    # HallThruster.jl profile files
    files = {}
    texts = {}
    meta_common = [
        "H-1 / MC-1 vacuum radial magnetic field on the channel centreline (r = 35 mm), FE-DERIVED (not measured, not FEMM).",
        "Solver: scikit-fem 10.0.2 axisymmetric nonlinear magnetostatics (docs/hardware/h1_bz/h1_bz_fe_solver.py);",
        "evaluation preregistered in docs/hardware/h1_bz/h1_bz_fe_prereg_v4.json (sha256 " + lock["files"]["docs/hardware/h1_bz/h1_bz_fe_prereg_v4.json"] + ");",
        "record docs/hardware/h1_bz/h1_bz_fe_v1.json. Geometry: registered H2-1 RP-1 MC-1 circuit (flat exit poles, solid core).",
        "z from the anode face (z = 0 = HALL_INLET_Z0), exit plane IP-EXIT at z = 103.2 mm. Cite with B_profile align = 'anode',",
        "z_ref_in_file_mm = 0.0, scale_to = 'max' (no rigid shift). Use requires DCR-002 approval + an envelope prereg addendum.",
    ]
    sel = []
    for lev in ("BP-LO", "BP-HI", "CAP-403"):
        d = ex.get(lev)
        if d and "profile" in d:
            sel.append((f"h1_fe_v1_Br_centerline_nominal_{lev}.csv", "NOM", lev, d, P["production"]["level"]))
    hi_rows = {v: W["exact"][v].get("BP-HI", {}) for v in W["exact"] if v != "NOM"}
    hi_ok = {v: r for v, r in hi_rows.items() if r.get("FWHM_mm") is not None and "profile" in r}
    if hi_ok:
        vmin = min(hi_ok, key=lambda v: hi_ok[v]["FWHM_mm"])
        vmax = max(hi_ok, key=lambda v: hi_ok[v]["FWHM_mm"])
        sel.append((f"h1_fe_v1_Br_centerline_envelope_minFWHM_{vmin}_BP-HI.csv", vmin, "BP-HI", hi_ok[vmin], P["uncertainty"]["level"]))
        sel.append((f"h1_fe_v1_Br_centerline_envelope_maxFWHM_{vmax}_BP-HI.csv", vmax, "BP-HI", hi_ok[vmax], P["uncertainty"]["level"]))
    for fname, vid, lev, d, mlev in sel:
        hdr = meta_common + [f"Variant {vid}, level {lev}: NI_total = {d['NI_A']:.2f} A-turns (inner/outer split 0.5), "
                             f"B_peak = {d['B_peak_G']:.2f} G at z = {d['z_peak_mm']:.2f} mm; mesh level {mlev}."]
        t = csv_text(P, d["profile"], hdr)
        texts[fname] = t
        files[fname] = {"sha256": shab(t.encode()), "variant": vid, "level": lev, "NI_total_A": d["NI_A"],
                        "B_peak_G": d["B_peak_G"], "z_peak_mm": d["z_peak_mm"], "mesh_level": mlev,
                        "role": "nominal" if vid == "NOM" else "uncertainty-envelope shape (prereg rule: min / max FWHM at BP-HI)"}
    manifest = {"schema": "abep_bfield_manifest_v1", "id": "h1_fe_v1", "evidence_class": "FE-DERIVED (scikit-fem 10.0.2); not measured; not FEMM",
                "field_outcome": outcome, "record": "docs/hardware/h1_bz/h1_bz_fe_v1.json",
                "prereg": {"path": "docs/hardware/h1_bz/h1_bz_fe_prereg_v4.json", "sha256": lock["files"]["docs/hardware/h1_bz/h1_bz_fe_prereg_v4.json"]},
                "citation": P["hall_citation_rule"], "files": files,
                "use_status": "NOT_FOR_HALL_RUNS_UNTIL_DCR_002_APPROVED_AND_ENVELOPE_ADDENDUM_REGISTERED",
                "p5_files_untouched": [SURR_REL, "hallthruster_bridge/bfield/p5_vacuum_Br_centerline_3p0kW.csv"]}

    rec = {
        "schema": "abep_h1_bz_fe_v1", "id": "h1_bz_fe_v1",
        "title": "H-1 / MC-1 FE-derived vacuum B(z) at the RP-1 anchor (A9.38 P3)",
        "date": "2026-10-08", "lane": "L-H1-BZ",
        "evidence_class": "FE-DERIVED (scikit-fem 10.0.2 axisymmetric nonlinear magnetostatics, FEMM-class per A9.14 F5-OQ-01); NOT measured; NOT FEMM",
        "label": "H1_FE_DERIVED_NOT_MEASURED",
        "field_outcome": outcome,
        "prereg": {"path": "docs/hardware/h1_bz/h1_bz_fe_prereg_v4.json", "sha256": lock["files"]["docs/hardware/h1_bz/h1_bz_fe_prereg_v4.json"],
                   "lock": {"path": "docs/hardware/h1_bz/h1_bz_fe_prereg_lock_v4.json", "sha256": sha(LOCK)}},
        "run_meta": {"verify": V.get("_meta"), "convergence": C.get("_meta"), "sweep": W["_meta"]},
        "stage_outputs": {f"docs/hardware/h1_bz/runs/{os.path.basename(fp)}": sha(fp) for fp in
                          [os.path.join(work, "verify.json"), os.path.join(work, "convergence.json")] + sweep_files},
        "prereg_history": {"v1": {"path": "docs/hardware/h1_bz/h1_bz_fe_prereg_v1.json", "status": "superseded before any scored result"},
                           "v2": {"path": "docs/hardware/h1_bz/h1_bz_fe_prereg_v2.json", "status": "verification run invalid (harness / formulation defects)",
                                  "record": "docs/hardware/h1_bz/runs/verify_v2_invalid_harness.json"},
                           "v3": {"path": "docs/hardware/h1_bz/h1_bz_fe_prereg_v3.json", "status": "verification failed (axis pollution, r = 0 NaN, line-search stall)",
                                  "record": "docs/hardware/h1_bz/runs/verify_v3_failed.json"},
                           "v4": {"path": "docs/hardware/h1_bz/h1_bz_fe_prereg_v4.json", "status": "governing"},
                           "rule": "no acceptance or verification criterion changed between versions; every result seen before each version is listed in its 'supersedes' block"},
        "verification": {"all_pass": ver_pass, "cases": {k: v for k, v in V.items() if k not in ("all_pass", "_meta")}},
        "convergence": conv,
        "numerical_uncertainty_L2_vs_L3": num,
        "geometry_nominal_dims_mm": nom["dims"],
        "peak_vs_current_nominal_L3": pvc,
        "exact_levels_nominal_L3": {lev: {k: v for k, v in d.items() if k not in ("profile",)} for lev, d in ex.items()},
        "uncertainty_envelope": env,
        "uncertainty_variants": {vid: {"variant": W["variants"][vid]["variant"], "level": W["variants"][vid]["level"],
                                       "dims": W["variants"][vid]["dims"],
                                       "exact": {lev: {k: d.get(k) for k in KEYS + ["B_peak_G", "status"]} for lev, d in W["exact"][vid].items()}}
                                 for vid in W["exact"]},
        "operating_split_sensitivity_at_nominal_BP_HI_NI_L2": W.get("split"),
        "acceptance": {"H1F-BZ-02": bz02, "H1F-BZ-03": bz03},
        "surrogate_comparison_DCR_002": {"surrogate": "BZ-P5B16 (" + SURR_REL + ", registered rigid per DBF1-BZ-04)",
                                         "surrogate_descriptors": {k: sd.get(k) for k in ("B_anode_over_B_peak", "FWHM_mm", "L_up_mm", "L_down_mm",
                                                                                         "z_peak_minus_L_mm", "B_exit_over_B_peak")},
                                         "per_level": comp},
        "hallthruster_files": {"dir": BF_REL, "manifest": BF_REL + "/MANIFEST.json", "files": files},
        "hall_citation_rule": P["hall_citation_rule"],
        "separation": "the P5 surrogate (BZ-P5B16 / P5B30, REFERENCE_FOR_P5_ONLY / SOURCED_SURROGATE_P5_SHAPE_NOT_H1_BZ) and this FE-derived field are separate evidence; no record computed under the surrogate is relabelled",
        "not_covered": P["uncertainty"]["not_covered"],
        "missing_registered_elements": P["geometry"]["missing_registered_elements"],
        "em_verification_items": ["measured B_r(z) along the channel mean radius from beyond IP-EXIT to the anode face (H1F-EX-08 probe path) vs this FE prediction, at the coil currents giving BP-LO / BP-HI",
                                  "hot-state B reference sensor traceable to coil current and temperature (H1F-MC-09)",
                                  "B-H of the procured FeCo-2V / pure-iron lots (HW-MC-13) and B_sat(T) (H1F-MA-03 / 04)",
                                  "stray field at IP-NEU / in the ICP volume (H1F-EX-05)"],
    }
    rec = clean(rec)
    return rec, manifest, texts


def md(rec):
    a2, a3 = rec["acceptance"]["H1F-BZ-02"], rec["acceptance"]["H1F-BZ-03"]
    ex = rec["exact_levels_nominal_L3"]
    L = []
    L.append("# H-1 / MC-1 FE-derived B(z) (A9.38 P3) — record v1\n")
    L.append("> Generated by `emit_h1_bz_fe.py` from `h1_bz_fe_v1.json`. Do not edit by hand.\n")
    L.append(f"- **Evidence class:** {rec['evidence_class']}.")
    L.append(f"- **Field outcome:** `{rec['field_outcome']}`.")
    L.append(f"- **Preregistration:** `{rec['prereg']['path']}` sha256 `{rec['prereg']['sha256']}` (lock `{rec['prereg']['lock']['sha256']}`).")
    L.append("- **Geometry:** registered H2-1 RP-1 MC-1 circuit (d 70 / h 12 / L 103.2 mm, gap 22 mm, flat exit poles 8 mm, solid FeCo-2V core r 13 mm, pure-iron return, body OD 122 mm); unregistered elements frozen as assumptions with ranges (prereg `missing_registered_elements`).\n")
    L.append("## Verification\n")
    L.append("| case | status | key error | pass |\n|---|---|---|---|")
    for k, v in rec["verification"]["cases"].items():
        err = {kk: vv for kk, vv in v.items() if "err" in kk}
        L.append(f"| {k} | {v.get('status')} | {', '.join(f'{kk} {vv:.3g}' for kk, vv in err.items())} | {v.get('pass')} |")
    L.append("\n## Mesh convergence (L2 vs L3)\n")
    L.append("| NI [A-t] | dB_peak rel | dz_peak [mm] | d anode ratio | profile max dB / B_peak | pass |\n|---|---|---|---|---|---|")
    for r in rec["convergence"]["rows"]:
        L.append(f"| {r['NI_A']} | {r.get('dB_peak_rel', 0):.3g} | {r.get('dz_peak_mm', 0):.3g} | {r.get('d_anode_ratio', 0):.3g} | {r.get('profile_max_dB_over_B_peak', 0):.3g} | {r.get('pass')} |")
    bx = rec["convergence"].get("box") or {}
    L.append(f"\nFar boundary (box x2): dB_peak rel {bx.get('dB_peak_rel')}, pass {bx.get('pass')}. Converged: **{rec['convergence']['converged']}**.\n")
    L.append("## Peak B_r vs total coil ampere-turns (nominal, L3, split 0.5)\n")
    L.append("| NI [A-t] | B_peak [G] | z_peak [mm] | B_anode/B_peak | G per A-t | linearity | iron B_max [T] |\n|---|---|---|---|---|---|---|")
    for r in rec["peak_vs_current_nominal_L3"]:
        L.append(f"| {r['NI_A']} | {r['B_peak_G']} | {r['z_peak_mm']} | {r['B_anode_over_B_peak']} | {r['G_per_A_turn']} | {r['linearity_vs_lowest_NI']} | {r['iron_Bmax_T']} |")
    L.append("\n## Band levels (nominal, exact NI)\n")
    L.append("| level | NI [A-t] | B_peak [G] | z_peak - L [mm] | B_anode/B_peak | B_exit/B_peak | FWHM [mm] | L_up [mm] | L_down [mm] |\n|---|---|---|---|---|---|---|---|---|")
    for lev, d in ex.items():
        if "B_peak_G" in d:
            L.append(f"| {lev} | {d['NI_A']} | {d['B_peak_G']} | {d['z_peak_minus_L_mm']} | {d['B_anode_over_B_peak']} | {d['B_exit_over_B_peak']} | {d['FWHM_mm']} | {d['L_up_mm']} | {d['L_down_mm']} |")
        else:
            L.append(f"| {lev} | {d.get('status')} | | | | | | | |")
    L.append("\n## Uncertainty envelope (OAT + corners at L2, nominal at L3, widened by |L2 - L3|)\n")
    L.append("| level | quantity | min | nominal | max | argmin | argmax |\n|---|---|---|---|---|---|---|")
    for lev, e in rec["uncertainty_envelope"].items():
        for k, v in e.items():
            if isinstance(v, dict):
                L.append(f"| {lev} | {k} | {v['min']} | {v['nominal']} | {v['max']} | {v['argmin']} | {v['argmax']} |")
        if e.get("not_reached"):
            L.append(f"| {lev} | not reached | {', '.join(e['not_reached'])} | | | | |")
    L.append("\n## Acceptance\n")
    L.append(f"- **H1F-BZ-02 (shape):** `{a2['outcome']}`; S2 window z_peak - L in {a2['S2_window_mm']} mm; per level {json.dumps(a2['per_level'])}; envelope counts {json.dumps(a2['envelope_counts'])}.")
    L.append(f"- **H1F-BZ-03 (band):** B1 `{a3['B1']['result']}` (NI {a3['B1']['NI_BP_HI_A']} vs {a3['B1']['limit_A']}); B2 `{a3['B2']['result']}` (max {a3['B2']['NI_BP_HI_envelope_max_A']}); B3 `{a3['B3']['result']}` (NI {a3['B3']['NI_CAP403_A']} vs {a3['B3']['limit_A']}).")
    L.append("- **Coil currents at the registered f_NI 2 turns (357 / 157):**")
    for lev, c in a3["coil_currents_at_registered_turns"].items():
        L.append(f"  - {lev}: inner {c['I_inner_A_at_357_turns']} A, outer {c['I_outer_A_at_157_turns']} A, inside 1-5 A window {c['inside_analog_1_5_A_window']}; iron B_max/B_sat {json.dumps(c['iron_Bmax_over_Bsat'])}")
    L.append("\n## Comparison with the surrogate BZ-P5B16 (DCR-002 evaluation, informational)\n")
    sc = rec["surrogate_comparison_DCR_002"]
    L.append(f"Surrogate descriptors: {json.dumps(sc['surrogate_descriptors'])}\n")
    for lev, c in sc["per_level"].items():
        L.append(f"- {lev}: max normalised difference {c['max_normalised_difference']} at z = {c['z_of_max_difference_mm']} mm; FE {json.dumps(c['FE'])}; flag `{c['materiality_flag']}`.")
    L.append("\n## HallThruster.jl profile files\n")
    for f, m in rec["hallthruster_files"]["files"].items():
        L.append(f"- `{rec['hallthruster_files']['dir']}/{f}` sha256 `{m['sha256']}` ({m['variant']}, {m['level']}, NI {m['NI_total_A']} A-t, {m['role']})")
    L.append(f"\nCitation: {rec['hall_citation_rule']['how']}. Requires: " + "; ".join(rec["hall_citation_rule"]["requires"]) + ".\n")
    L.append("## Not covered\n")
    for x in rec["not_covered"]:
        L.append(f"- {x}")
    L.append("\n## Engineering-model verification items\n")
    for x in rec["em_verification_items"]:
        L.append(f"- {x}")
    return "\n".join(L) + "\n"


def main():
    args = sys.argv[1:]
    work = args[args.index("--work") + 1]
    rec, manifest, texts = build(work)
    out = {OUT_JSON: json.dumps(rec, indent=1, ensure_ascii=False) + "\n", OUT_MD: md(rec),
           os.path.join(BF, "MANIFEST.json"): json.dumps(manifest, indent=1, ensure_ascii=False) + "\n"}
    for f, t in texts.items():
        out[os.path.join(BF, f)] = t
    if "--check" in args:
        bad = [p for p, t in out.items() if not os.path.exists(p) or open(p, encoding="utf-8").read() != t]
        print("OK" if not bad else "DIFFERS: " + ", ".join(bad))
        sys.exit(1 if bad else 0)
    os.makedirs(BF, exist_ok=True)
    os.makedirs(RUNS, exist_ok=True)
    if os.path.abspath(work) != os.path.abspath(RUNS):
        import glob
        for fp in [os.path.join(work, "verify.json"), os.path.join(work, "convergence.json")] + \
                sorted(glob.glob(os.path.join(work, "sweep_*.json"))):
            shutil.copyfile(fp, os.path.join(RUNS, os.path.basename(fp)))
    for p, t in out.items():
        with open(p, "w", encoding="utf-8") as f:
            f.write(t)
    print("wrote", len(out), "files; outcome", rec["field_outcome"])


if __name__ == "__main__":
    main()
