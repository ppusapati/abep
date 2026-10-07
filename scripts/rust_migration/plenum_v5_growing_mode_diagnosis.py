"""Plenum / feed contract v5 RUST_DEFECT (growing-mode damping): reproducible diagnosis and regression fixture.

Inspection only: it runs refinement vectors of the frozen v5 grid (refinement_master_seed 731905543, already run by
the frozen record transient_envelope_v5.json) and never a held-out (scoring) vector.

    python3 scripts/rust_migration/plenum_v5_growing_mode_diagnosis.py diagnose [R45-192 R45-331 ...]
        per vector: the closed-loop eigenvalues of the dynamic block of the reference Jacobian at the steady start,
        the Radau IIA critical step and damping factor on the orbit output grid, and the Python / Rust orbit_sim
        records at the nominal, T1 and T2 rtol (the Rust binary as built from the working tree)
    python3 scripts/rust_migration/plenum_v5_growing_mode_diagnosis.py fixture OUT.json
        writes the regression fixture of crates/abep-gaspath/tests/transient_growing_mode_regression.rs: the nominal
        requests of R45-192 / R45-331, their converged Rust T1 records, mdot_scale and the registered bound (the
        Python PROD P45 envelopes E_py of the frozen v5 record)
"""
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import es3_gaspath_parity as H  # noqa: E402
from abep_sim.design import plenum_feed as pf  # noqa: E402

CDIR = os.path.join(H.ROOT, "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY")
V5 = os.path.join(CDIR, "parity_prereg_v5.json")
REC = os.path.join(CDIR, "transient_envelope_v5.json")
KEYS = ("ok", "P_dev_max_frac", "mdot_min_kgps", "mdot_max_kgps", "nfev")


def v5_p45():
    c = json.load(open(V5))
    proc = c["transient_convergence_procedure_v3"]
    V = H.refinement_vectors(c, c["campaign_seeds"]["refinement_master_seed"], proc["step_1_refinement_grid"]["counts"])
    return {v["id"]: v for v in V if v["entry"] == "plenum.orbit_sim"}, proc["tolerance_levels"]["PROD"]


def radau_r(z):
    return (1 + 2 * z / 5 + z * z / 20) / (1 - 3 * z / 5 + 3 * z * z / 20 - z ** 3 / 60)


def r_acc(z):
    return (32 * radau_r(z / 2) ** 2 - radau_r(z)) / 31


def steady_start_jacobian(v):
    cap = {}
    orig = pf.TransientRun.run

    def grab(self, events, n_eval=150, y_start=None):
        cap.update(tr=self, ev=events[0], y=y_start)
        raise RuntimeError("captured")

    pf.TransientRun.run = grab
    try:
        H.py_plenum(v)
    except Exception:
        pass
    finally:
        pf.TransientRun.run = orig
    rhs, jac = cap["tr"]._make(cap["ev"])
    return np.asarray(jac(0.0, cap["y"]))[:5, :5], cap["ev"].duration_s


def record(o):
    return {k: H.unj(o[1].get(k)) if k != "ok" else o[1].get(k) for k in KEYS} if o[0] == "OK" else list(o)


def run_both(v, lv):
    out = {}
    for name, rt in (("N", None), ("T1", lv["T1_rtol"]), ("T2", lv["T2_rtol"])):
        rs, _, _, _ = H.run_rust([H.rust_req_rtol(v, rt)])
        out[name] = {"python": record(H.py_run_rtol(v, rt)), "rust": record(H.rust_outcome(rs["results"][0]))}
    return out


def diagnose(ids):
    V, lv = v5_p45()
    H.build_rust()
    for vid in ids:
        v = V[vid]
        J, T = steady_start_jacobian(v)
        lam = sorted(np.linalg.eigvals(J), key=lambda z: -z.real)
        te = np.unique(np.concatenate([[0.0], np.geomspace(1e-6 * max(T, 1.0), T, 150)]))
        dt = np.diff(te)
        print(f"== {vid}  orbital period {T:.0f} s")
        print("  eigenvalues:", ", ".join(f"{z.real:.4g}{z.imag:+.4g}i" for z in lam))
        for z in lam:
            if z.real > 0 and z.imag >= 0:
                hs = np.logspace(-3, 3, 60001)
                hc = hs[np.argmax(np.abs(radau_r(hs * z)) < 1)]
                hca = hs[np.argmax(np.abs(r_acc(hs * z)) < 1)]
                print(f"  growing mode {z.real:.4g}{z.imag:+.4g}i: Radau |R(h lambda)| < 1 for h >= {hc:.3g} s "
                      f"(accepted step-doubling update: h >= {hca:.3g} s); output intervals >= that: "
                      f"{int((dt >= hc).sum())} of {len(dt)}; |R| at the last interval ({dt[-1]:.0f} s) = "
                      f"{abs(radau_r(dt[-1] * z)):.2g}")
        for name, d in run_both(v, lv).items():
            print(f"  {name:2s} python {d['python']}")
            print(f"  {name:2s} rust   {d['rust']}")


def fixture(out_path):
    V, lv = v5_p45()
    H.build_rust()
    rec = json.load(open(REC))
    e_py = rec["envelopes"]["python"]["PROD"]["P45"]
    cases = []
    for vid in ("R45-192", "R45-331"):
        v = V[vid]
        rs, _, _, _ = H.run_rust([H.rust_req_rtol(v, lv["T1_rtol"])])
        t1 = record(H.rust_outcome(rs["results"][0]))
        cases.append({"id": vid, "request": H.rust_req_rtol(v, None), "converged_rust_T1": t1,
                      "T1_rtol": lv["T1_rtol"], "mdot_scale": H.mdot_scale_of(v)})
    fx = {
        "schema": "abep_gaspath_growing_mode_regression_v1",
        "what": "R45-192 / R45-331 of the frozen plenum / feed v5 refinement grid (refinement seed 731905543): "
                "the Rust nominal orbit_sim must reproduce the converged (T1) answer within the registered Python "
                "PROD P45 envelope E_py of the frozen v5 record (the reference's own nominal-tolerance error). "
                "Before the growing-mode guard the nominal run held the setpoint (P_dev 1.2e-5 / 8.9e-6).",
        "contract_v5_sha256": hashlib.sha256(open(V5, "rb").read()).hexdigest(),
        "record_v5_sha256": hashlib.sha256(open(REC, "rb").read()).hexdigest(),
        "bound": {"F45.P_dev": e_py["F45.P_dev"]["E"], "F45.mdot": e_py["F45.mdot"]["E"],
                  "units": "F45.P_dev absolute (scale 1); F45.mdot in units of the vector's mdot_scale"},
        "materials": H.MATERIALS,
        "cases": cases,
    }
    with open(out_path, "w") as f:
        f.write(json.dumps(fx, indent=1, allow_nan=False) + "\n")
    print("written", out_path)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "diagnose":
        diagnose(sys.argv[2:] or ["R45-192", "R45-331"])
    elif len(sys.argv) == 3 and sys.argv[1] == "fixture":
        fixture(sys.argv[2])
    else:
        sys.exit(__doc__)
