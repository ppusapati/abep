"""Plenum / feed contract v6: per-vector picture of the frozen P42 / P43 refinement envelopes
(transient_envelope_v6.json).

Inspection only: it reruns the 2048 P42 / P43 vectors of the v6 refinement grid (refinement_master_seed 731905553,
already run by the frozen record) in both implementations at the nominal, T1 and T2 rtol of their level, never a
held-out (scoring) vector.

    python3 scripts/rust_migration/plenum_v6_p4243_refinement_analysis.py rows ROWS.json
        per vector and implementation: max over leaves of (|N - T2| + |T1 - T2|) / s_F and |T1 - T2| / s_F per family,
        and the largest Re lambda of the dynamic block of the reference Jacobian at the design steady start
    python3 scripts/rust_migration/plenum_v6_p4243_refinement_analysis.py classes ROWS.json CLASSES.json
        event-wise class (reference Jacobian at every event's equilibrium; events without a reachable unsaturated
        equilibrium counted: the valve closes or would exceed full opening) and the per-stratum envelope maxima
        (stable with every equilibrium reachable / stable with such an event / unstable)
"""
import json
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import es3_gaspath_parity as H  # noqa: E402
from abep_sim.design import plenum_feed as pf  # noqa: E402


def rows_mode(OUT):
    contract, _, _ = H.load_contract("plenum")
    proc = contract["transient_convergence_procedure_v3"]
    levels = proc["tolerance_levels"]
    V = [v for v in H.refinement_vectors(contract, contract["campaign_seeds"]["refinement_master_seed"],
                                         proc["step_1_refinement_grid"]["counts"]) if v["entry"] != "plenum.orbit_sim"]
    fam_scale = H.v3_families()
    H.build_rust()
    lv = {v["id"]: H.level_of(v) for v in V}
    rt = {v["id"]: {"N": None, "T1": levels[lv[v["id"]]]["T1_rtol"], "T2": levels[lv[v["id"]]]["T2_rtol"]} for v in V}
    runs = ("N", "T1", "T2")
    rs = {v["id"]: {} for v in V}
    for r in runs:
        out, _, _, _ = H.run_rust([H.rust_req_rtol(v, rt[v["id"]][r]) for v in V])
        for x in out["results"]:
            rs[x["id"]][r] = H.rust_outcome(x)

    def design_re_max(v):
        a = v["args"]
        try:
            fc, pl, pn = H.py_filter_case(a["filter"]), H.py_plant(a["plant"]), H.py_plenum_obj(a["plenum"])
            ct, des = H.py_controller(a["controller"]), H.py_intake_state(a["intake"])
            tr = pf.TransientRun(fc, pl, pn, ct, des, a["r0"])
            y0, u_ss = tr.steady_start(des, a["r0"])
            if y0 is None:
                return None, "NO_STEADY_START"
            ev = pf.event_sequence(des, a["r0"], a["window_s"])[0]
            rhs, jac = tr._make(ev)
            lam = np.linalg.eigvals(np.asarray(jac(0.0, y0))[:5, :5])
            return float(max(lam.real)), ("u_ss>1" if u_ss > 1 else "ok")
        except Exception as e:  # noqa: BLE001
            return None, type(e).__name__

    rows = []
    for v in V:
        vid, e = v["id"], v["entry"]
        py = {r: H.py_run_rtol(v, rt[vid][r]) for r in runs}
        H.TAP.clear()
        row = {"id": vid, "entry": e, "level": lv[vid]}
        row["re_max"], row["start"] = design_re_max(v)
        for impl, O in (("py", py), ("rs", rs[vid])):
            if not all(H.run_ok(e, O[r]) for r in runs):
                row[impl] = "excluded"
                continue
            L = {r: H.family_leaves(e, O[r][1]) for r in runs}
            fams = {}
            for fam in L["T2"]:
                em = tm = 0.0
                for pth, x2 in L["T2"][fam].items():
                    xN, x1 = L["N"].get(fam, {}).get(pth), L["T1"].get(fam, {}).get(pth)
                    if xN is None or x1 is None:
                        continue
                    s = H.family_scale(fam_scale[fam], v, x2)
                    if not s:
                        continue
                    em = max(em, (abs(xN - x2) + abs(x1 - x2)) / s)
                    tm = max(tm, abs(x1 - x2) / s)
                fams[fam] = [em, tm]
            row[impl] = fams
        rows.append(row)
    json.dump(rows, open(OUT, "w"))
    print("rows", len(rows))


def classes_mode(rows_path, out_path):
    rows = {r["id"]: r for r in json.load(open(rows_path))}
    contract, _, _ = H.load_contract("plenum")
    proc = contract["transient_convergence_procedure_v3"]
    grid = H.refinement_vectors(contract, contract["campaign_seeds"]["refinement_master_seed"],
                                proc["step_1_refinement_grid"]["counts"])
    V = {v["id"]: v for v in grid if v["id"] in rows}
    SP = list(pf.SPECIES)

    def classify(v):
        a = v["args"]
        fc, pl, pn = H.py_filter_case(a["filter"]), H.py_plant(a["plant"]), H.py_plenum_obj(a["plenum"])
        ct, des = H.py_controller(a["controller"]), H.py_intake_state(a["intake"])
        try:
            tr = pf.TransientRun(fc, pl, pn, ct, des, a["r0"])
        except Exception as e:  # noqa: BLE001
            return {"class": "no_run", "why": type(e).__name__}
        res = []
        for ev in pf.event_sequence(des, a["r0"], a["window_s"]):
            co = pf.Chain(ev.intake, tr.filt, tr.plant, tr.plenum).node_coefficients(ev.density)
            leak_d, fc_d = dict(zip(SP, tr.leak)), dict(zip(SP, tr.fc))
            ar, _, _, ok = pf.area_for_pressure(co, ev.setpoint_Pa, tr.k_rec, leak_d, fc_d)
            if not bool(ok):
                res.append(("no_eq", None))
                continue
            u = float(ar) / (tr.a_max * ev.feed_factor)
            if u > 1.0:
                res.append(("sat_eq", None))
                continue
            p3, _ = pf.solve_pressures(co, float(ar), tr.k_rec, leak_d, fc_d)
            i_int = (u / tr.u_ff - 1.0) * tr.ctrl.Ti_s / tr.ctrl.Kp
            y = [float(p3[s]) / tr.r0 for s in SP] + [u, i_int, 0.0, 0.0, 0.0]
            rhs, jac = tr._make(ev)
            res.append(("eq", float(max(np.linalg.eigvals(np.asarray(jac(0.0, y))[:5, :5]).real))))
        re = [x for k, x in res if k == "eq"]
        return {"class": "U" if any(x > 0 for x in re) else "S", "re_max": max(re) if re else None,
                "no_eq_events": sum(1 for k, _ in res if k != "eq"), "design_re": res[0][1]}

    out = {}
    for vid, v in V.items():
        out[vid] = classify(v)
    json.dump(out, open(out_path, "w"))
    fams = sorted({f for r in rows.values() for impl in ("py", "rs") if isinstance(r.get(impl), dict) for f in r[impl]})
    for lvl in ("PROD", "REF"):
        print(lvl, {c: sum(1 for k, r in rows.items() if r["level"] == lvl and out[k]["class"] == c)
                    for c in ("S", "U", "no_run")})
        for f in fams:
            line = []
            for impl in ("py", "rs"):
                for c, noeq in (("S", False), ("S", True), ("U", None)):
                    vals = [(r[impl][f][0], k) for k, r in rows.items() if r["level"] == lvl and out[k]["class"] == c
                            and (noeq is None or (out[k]["no_eq_events"] > 0) == noeq)
                            and isinstance(r.get(impl), dict) and f in r[impl]]
                    m = max(vals) if vals else (0, "-")
                    tag = {False: "S-alleq", True: "S-closed", None: "U"}[noeq]
                    line.append(f"{impl}{tag} {m[0]:.2g} {m[1]}")
            print(" ", f.ljust(22), " | ".join(line))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "rows":
        rows_mode(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "classes":
        classes_mode(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
