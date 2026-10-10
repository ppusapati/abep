"""Plenum / feed contract v6: per-vector picture of the frozen P45 refinement envelopes (transient_envelope_v6.json).

Inspection only: it reruns the 512 P45 vectors of the v6 refinement grid (refinement_master_seed 731905553, already run
by the frozen record) in both implementations at the nominal, T1 and T2 rtol, never a held-out (scoring) vector. Per
vector it records the estimator terms |N - T2| + |T1 - T2| (family units), |T1 - T2| and the largest real part of the
eigenvalues of the dynamic block of the reference Jacobian at the steady start.

    python3 scripts/rust_migration/plenum_v6_p45_refinement_analysis.py OUT_ROWS.json
"""
import json
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import es3_gaspath_parity as H  # noqa: E402
from abep_sim.design import plenum_feed as pf  # noqa: E402

if len(sys.argv) != 2:
    sys.exit(__doc__)
contract, _, _ = H.load_contract("plenum")
proc = contract["transient_convergence_procedure_v3"]
V = [v for v in H.refinement_vectors(contract, contract["campaign_seeds"]["refinement_master_seed"],
                                     proc["step_1_refinement_grid"]["counts"]) if v["entry"] == "plenum.orbit_sim"]
lv = proc["tolerance_levels"]["PROD"]
H.build_rust()
runs = {"N": None, "T1": lv["T1_rtol"], "T2": lv["T2_rtol"]}
rs = {}
for r, rt in runs.items():
    out, _, _, _ = H.run_rust([H.rust_req_rtol(v, rt) for v in V])
    for x in out["results"]:
        rs.setdefault(x["id"], {})[r] = H.rust_outcome(x)
cap = {}
orig = pf.TransientRun.run


def grab(self, events, n_eval=150, y_start=None):
    cap.update(tr=self, ev=events[0], y=y_start)
    return orig(self, events, n_eval, y_start)


rows = []
for v in V:
    py = {}
    for r, rt in runs.items():
        cap.clear()
        pf.TransientRun.run = grab
        try:
            py[r] = H.py_run_rtol(v, rt)
        finally:
            pf.TransientRun.run = orig
        if r == "N" and "tr" in cap:
            rhs, jac = cap["tr"]._make(cap["ev"])
            re_max = float(max(np.linalg.eigvals(np.asarray(jac(0.0, cap["y"]))[:5, :5]).real))
        elif r == "N":
            re_max = None
    ok = lambda o: o[0] == "OK" and isinstance(o[1], dict) and o[1].get("ok")  # noqa: E731
    if not all(ok(py[r]) for r in runs) or not all(ok(rs[v["id"]][r]) for r in runs):
        continue
    s = H.mdot_scale_of(v)
    row = {"id": v["id"], "re_max": re_max}
    for impl, O in (("py", py), ("rs", rs[v["id"]])):
        for q, sc in (("P_dev_max_frac", 1.0), ("mdot_min_kgps", s), ("mdot_max_kgps", s)):
            x = {r: H.unj(O[r][1][q]) for r in runs}
            row[f"{impl}.{q}.e"] = (abs(x["N"] - x["T2"]) + abs(x["T1"] - x["T2"])) / sc
            row[f"{impl}.{q}.t12"] = abs(x["T1"] - x["T2"]) / sc
            row[f"{impl}.{q}.N"] = x["N"]
            row[f"{impl}.{q}.T2"] = x["T2"]
    rows.append(row)
if len(sys.argv) != 2:
    sys.exit(__doc__)
json.dump(rows, open(sys.argv[1], "w"))
print("rows", len(rows))
