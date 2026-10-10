"""Plenum / feed contract v7: the refinement vectors behind the failed NON_VACUITY rows (refinement seed 731905563;
inspection only, never a held-out vector). Re-draws the P45 refinement stratum (the registered stratified draw) and
runs the named vectors in both implementations at N / T1 / T2, with the 24-phase spectrum of the class.

    python3 scripts/rust_migration/plenum_v7_nonvacuity_probe.py R45-PROD-U-061 R45-PROD-U-045 R45-PROD-U-119
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import es3_gaspath_parity as H  # noqa: E402

c, _, _ = H.load_contract("plenum")
sp = c["transient_convergence_procedure_v7"]
lv = c["transient_convergence_procedure_v3"]["tolerance_levels"]["PROD"]
vs, _ = H.stratified_draw(c["campaign_seeds"]["refinement_master_seed"], 45, "plenum.orbit_sim",
                          sp["stratified_draws"]["refinement"]["P45"], "R",
                          sp["stratified_draws"]["max_candidates_per_level"])
V = {v["id"]: v for v in vs}
H.build_rust()
KEYS = ("P_dev_max_frac", "mdot_min_kgps", "mdot_max_kgps", "nfev")
for vid in sys.argv[1:]:
    v = V[vid]
    cl = H.CLS[vid]
    res = [e["re_max"] for e in cl["events"] if e["re_max"] is not None]
    print(f"== {vid}: max Re lambda over the 24 phases {max(res):.4g} (phase 0 {res[0]:.4g}; "
          f"{sum(1 for x in res if x > 0)}/24 positive)")
    for r, rt in (("N", None), ("T1", lv["T1_rtol"]), ("T2", lv["T2_rtol"])):
        p = H.py_run_rtol(v, rt)
        o, _, _, _ = H.run_rust([H.rust_req_rtol(v, rt)])
        q = H.rust_outcome(o["results"][0])
        f = (lambda x: {k: x[1].get(k) for k in KEYS} if x[0] == "OK" else x)
        print(f"  {r:2s} python {json.dumps(f(p))}")
        print(f"  {r:2s} rust   {json.dumps(f(q))}")
