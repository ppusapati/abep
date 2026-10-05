"""Parity harness of PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1 and PARITY-C-ABEP_SIM_INTAKE_PY-V1 (ES-3, SC-WP-02).

Runs the Python reference (read only, at this commit) and the Rust implementation (crates/abep-intake, through the
release example `intake_parity`) on the vectors the contracts register, and applies their decision rules.

    python3 scripts/rust_migration/parity_intake.py --contract intake_tpmc|intake --mode dev   --scratch DIR
    python3 scripts/rust_migration/parity_intake.py --contract intake_tpmc|intake --mode score --scratch DIR

dev   : development master seed; only the randomized-domain draws (and, for intake_tpmc, E1 replicates seeded from
        it). Prints counts to the console; never writes a report and never states a verdict.
score : scoring master seed; the full registered vector set, once per contract version. Writes parity_report_v1.json
        (+ .md) and reference_outputs/ next to the contract whatever the verdict, and appends campaign_history.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import scipy  # noqa: E402

CARGO_BIN = "/root/.cargo/bin"
CONTRACTS = {
    "intake_tpmc": "docs/rust_migration/contracts/C-ABEP_SIM_INTAKE_TPMC_PY",
    "intake": "docs/rust_migration/contracts/C-ABEP_SIM_INTAKE_PY",
}
STATES = [(alt, sol) for alt in (180.0, 200.0, 230.0) for sol in ("low", "mean", "high")]
GRID = {"L_over_d": [3.0, 5.0, 10.0, 20.0], "phi": [0.8, 0.9], "alpha": [0.0, 0.2, 0.5, 0.8, 1.0],
        "theta_deg": [0.0, 2.0, 5.0]}
AXES = ("L_over_d", "phi", "alpha", "theta_deg")
Z, AGG, ZERO_SE_REL = 5.0, 4.0, 1e-12


def sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def rel(p: str) -> str:
    return os.path.join(ROOT, p)


# --- numbers --------------------------------------------------------------------------------------------------------

def enc(x):
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)) and not isinstance(x, bool):
        return int(x)
    if isinstance(x, (float, np.floating)):
        x = float(x)
        if math.isnan(x):
            return "NaN"
        if math.isinf(x):
            return "Infinity" if x > 0 else "-Infinity"
        return x
    if isinstance(x, dict):
        return {k: enc(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [enc(v) for v in x]
    return x


def dec(x):
    if x == "NaN":
        return float("nan")
    if x == "Infinity":
        return float("inf")
    if x == "-Infinity":
        return float("-inf")
    return x


def ulp_ok(r, p, k_ulp: float, r_rel: float) -> tuple[bool, float]:
    r, p = dec(r), dec(p)
    if r is None or p is None:
        return (r is None and p is None), float("nan")
    r, p = float(r), float(p)
    if math.isnan(r) or math.isnan(p):
        return (math.isnan(r) and math.isnan(p)), float("nan")
    if r == p:
        return True, 0.0
    d = abs(r - p)
    return (d <= k_ulp * float(np.spacing(abs(p))) or d <= r_rel * max(1.0, abs(p))), d / max(1.0, abs(p))


def bits_equal(a, b) -> bool:
    a, b = dec(a), dec(b)
    if isinstance(a, float) or isinstance(b, float):
        try:
            return np.float64(a).tobytes() == np.float64(b).tobytes()
        except (TypeError, ValueError):
            return False
    return a == b


# --- reference side helpers -----------------------------------------------------------------------------------------

def freestream(atm: dict) -> dict:
    fs = {k: float(atm[k]) for k in ("n", "rho", "V", "T", "m_mean", "fO", "fN2", "fO2", "flux_kg_m2_s")}
    if "V_rel" in atm:
        fs["V_rel"] = float(atm["V_rel"])
    return fs


_ATM = {}


def atm_of(alt, sol):
    from abep_sim.atmosphere import atmosphere
    key = (float(alt), sol)
    if key not in _ATM:
        _ATM[key] = atmosphere(float(alt), sol, use_msis=False)
    return dict(_ATM[key])


SUBSTRINGS = [("unknown wall-scattering model", "UNKNOWN_SCATTERING"),
              ("must be finite and inside [0, 1]", "ACCOMMODATION_INVALID"),
              ("must be a finite real number in [0, 1]", "ACCOMMODATION_INVALID"),
              ("intake ROM extrapolation", "OUT_OF_BOUNDS"),
              ("needs explicit free-stream mass fractions", "FRACTIONS_REQUIRED"),
              ("mass fractions must be finite and >= 0", "FRACTION_INVALID"),
              ("are not in the frozen table", "FOREIGN_SPECIES"),
              ("all mass fractions are zero", "ALL_ZERO"),
              ("needs m_mean_build_kg", "M_MEAN_BUILD_REQUIRED"),
              ("non-finite", "NON_FINITE_ROW")]


def classify(exc: BaseException) -> str:
    from abep_sim.intake_surface_v2_spec import IntakeSurfaceV2Blocked
    if isinstance(exc, IntakeSurfaceV2Blocked):
        return "V2_BLOCKED"
    if isinstance(exc, KeyError):
        return "UNKNOWN_SPECIES"
    if isinstance(exc, ZeroDivisionError):
        return "PASSIVE_ZERO"
    msg = str(exc)
    for sub, key in SUBSTRINGS:
        if sub in msg:
            return key
    return "UNCLASSIFIED:" + type(exc).__name__


def py_call(fn):
    try:
        return {"ok": fn()}
    except Exception as e:  # noqa: BLE001 - every reference failure is classified and compared
        return {"err": {"class": type(e).__name__, "key": classify(e), "message": str(e)[:300]}}


def plain(v):
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return v


# --- Rust side ------------------------------------------------------------------------------------------------------

class Rust:
    def __init__(self, scratch: str):
        self.scratch = scratch
        env = dict(os.environ)
        env["PATH"] = CARGO_BIN + os.pathsep + env.get("PATH", "")
        self.env = env
        r = subprocess.run(["cargo", "build", "--release", "--locked", "-p", "abep-intake", "--example", "intake_parity"],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("NOT_RUN_RUST_UNAVAILABLE: " + r.stderr[-2000:])
        self.exe = os.path.join(ROOT, "target", "release", "examples", "intake_parity")
        self.exe_sha256 = sha(self.exe)
        self.n = 0

    def run(self, calls: list[dict], m_mean_build=None) -> list[dict]:
        self.n += 1
        req = os.path.join(self.scratch, f"req_{self.n}.json")
        resp = os.path.join(self.scratch, f"resp_{self.n}.json")
        body = {"calls": [dict(c, id=i) for i, c in enumerate(calls)]}
        if m_mean_build is not None:
            body["m_mean_build_kg"] = m_mean_build
        with open(req, "w") as f:
            json.dump(enc(body), f)
        r = subprocess.run([self.exe, req, resp], cwd=ROOT, env=self.env, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("Rust CLI failed: " + r.stderr[-2000:])
        out = json.load(open(resp))["results"]
        return [{k: v for k, v in o.items() if k != "id"} for o in out]


# --- statistics -----------------------------------------------------------------------------------------------------

def zstat(mp, sp, mr, sr):
    se = math.sqrt(sp * sp + sr * sr)
    if se == 0.0:
        ok = abs(mr - mp) <= ZERO_SE_REL * max(1.0, abs(mp))
        return None, ("AGREE_EXACT" if ok else "DISAGREE_EXACT")
    z = (mr - mp) / se
    return z, ("WITHIN" if abs(z) <= Z else "OUTSIDE")


def aggregate(tests: list[dict]) -> dict:
    out = {}
    for t in tests:
        if t.get("z") is not None:
            out.setdefault(t["observable"], []).append(t["z"])
    return {k: {"N": len(v), "abs_sum_z_over_sqrtN": abs(sum(v)) / math.sqrt(len(v)),
                "within": abs(sum(v)) / math.sqrt(len(v)) <= AGG} for k, v in out.items()}


# ====================================================================================================================
# Contract A: intake_tpmc
# ====================================================================================================================

E1_STAT = ("eta_c", "C_D", "K_back", "CR_passive", "eta_open", "unresolved_fraction", "mean_wall_hits", "converged")
E1_ECHO = ("alpha", "theta_deg", "L_over_d", "phi", "d_mm")
E1_KEYS = ["eta_c", "C_D", "K_back", "CR_passive", "eta_open", "unresolved_fraction", "converged", "scattering",
           "K_back_scattering", "mean_wall_hits", "mass_kg", "alpha", "theta_deg", "L_over_d", "phi", "d_mm"]
SURF_MIX = ("eta_c", "C_D", "K_back", "CR_passive", "mass_kg")
SURF_SP = ("eta_c", "C_D_row", "C_D_species", "CR_passive", "K_back", "mass_fraction", "mole_fraction",
           "collected_mass_fraction", "collected_mole_fraction")


def e1_vectors(master: int, dev: bool) -> list[dict]:
    from abep_sim.constants import M_SPECIES
    v = []
    if not dev:
        for ld in (3.0, 5.0, 10.0, 20.0):
            for al in (0.0, 0.5, 1.0):
                for sc in ("maxwell", "cll"):
                    v.append({"id": f"E1-G-L{ld:g}-a{al}-{sc}", "group": "golden",
                              "geom": {"area_m2": 0.5, "L_over_d": ld, "phi": 0.85}, "atm": (200.0, "mean"),
                              "alpha": al, "theta_deg": 0.0, "n": 4000, "scattering": sc, "species": "N2"})
        for sp in ("O", "O2", "mean"):
            for th in (2.0, 5.0):
                v.append({"id": f"E1-G-{sp}-th{th:g}", "group": "golden",
                          "geom": {"area_m2": 0.5, "L_over_d": 10.0, "phi": 0.8}, "atm": (200.0, "mean"),
                          "alpha": 0.8, "theta_deg": th, "n": 4000, "scattering": "maxwell", "species": sp})
        base = {"geom": {"area_m2": 0.5}, "atm": (200.0, "mean"), "n": 4000, "species": "N2", "theta_deg": 0.0}
        edges = [
            ("E1-E01", {"filter": True, "L_over_d": 5.0, "phi": 0.85}, {"alpha": 0.5, "scattering": "maxwell"}),
            ("E1-E02", {"L_over_d": 5.0, "phi": 0.85}, {"alpha": 0.8, "scattering": "maxwell", "theta_deg": 30.0}),
            ("E1-E03", {"L_over_d": 0.5, "phi": 0.85}, {"alpha": 1.0, "scattering": "cll"}),
            ("E1-E04", {"T_wall_K": 100.0, "L_over_d": 5.0, "phi": 0.85}, {"alpha": 0.5, "scattering": "maxwell"}),
            ("E1-E05", {"L_over_d": 10.0, "phi": 0.85}, {"atm": (180.0, "low"), "species": "mean", "alpha": 0.5,
                                                         "scattering": "maxwell"}),
            ("E1-E06", {"L_over_d": 10.0, "phi": 0.85}, {"atm": (230.0, "high"), "species": "mean", "alpha": 0.5,
                                                         "scattering": "cll"}),
            ("E1-E07", {"area_m2": 1.0, "d_mm": 5.0, "phi": 0.5, "L_over_d": 8.0},
             {"alpha": 0.3, "scattering": "maxwell", "theta_deg": 1.0}),
        ]
        for eid, g, kw in edges:
            vec = copy.deepcopy(base)
            vec["geom"].update(g)
            vec.update(kw)
            vec.update({"id": eid, "group": "edge"})
            v.append(vec)
    rng = np.random.default_rng(np.random.SeedSequence([master, 1, 0, 3]))
    for i in range(16):
        ld = float(np.exp(rng.uniform(np.log(1.0), np.log(30.0))))
        phi = float(rng.uniform(0.5, 0.95))
        al = float(rng.uniform(0.0, 1.0))
        th = float(rng.uniform(0.0, 10.0))
        sc = "maxwell" if rng.uniform() < 0.5 else "cll"
        sp = ("O", "N2", "O2", "mean")[int(rng.integers(0, 4))]
        alt = (180.0, 200.0, 230.0)[int(rng.integers(0, 3))]
        sol = ("low", "mean", "high")[int(rng.integers(0, 3))]
        tw = float(rng.uniform(250.0, 450.0))
        flt = bool(rng.uniform() < 0.25)
        v.append({"id": f"E1-R{i:02d}", "group": "randomized",
                  "geom": {"area_m2": 0.5, "L_over_d": ld, "phi": phi, "T_wall_K": tw, "filter": flt},
                  "atm": (alt, sol), "alpha": al, "theta_deg": th, "n": 4000, "scattering": sc, "species": sp})
    for vec in v:
        vec["species_mass"] = None if vec["species"] == "mean" else float(M_SPECIES[vec["species"]])
    return v


def e2_vectors() -> list[dict]:
    from abep_sim.constants import M_SPECIES
    v = []
    for ld in (3.0, 10.0, 20.0):
        for al in (0.0, 0.5, 1.0):
            v.append({"id": f"E2-G-L{ld:g}-a{al}", "group": "golden", "r": 0.005, "l": ld * 0.01, "alpha": al,
                      "t_w": 350.0, "m": float(M_SPECIES["N2"]), "n": 20000})
    v.append({"id": "E2-E01", "group": "edge", "r": 0.005, "l": 5.0 * 0.01, "alpha": 0.8, "t_w": 100.0,
              "m": float(M_SPECIES["O"]), "n": 20000})
    v.append({"id": "E2-E02", "group": "edge", "r": 0.005, "l": 0.5 * 0.01, "alpha": 0.2, "t_w": 350.0,
              "m": float(M_SPECIES["O2"]), "n": 20000})
    return v


def e4_evaluations(master: int, dev: bool, capture: dict) -> list[dict]:
    a200 = atm_of(200.0, "mean")
    f200 = {"O": a200["fO"], "N2": a200["fN2"], "O2": a200["fO2"]}
    ev = []
    if not dev:
        for sc in ("maxwell", "cll"):
            for k, p in enumerate(capture["points"]):
                ev.append({"id": f"E4-N-{sc}-{k:03d}", "group": "golden_nodes", "scattering": sc, "point": p,
                           "fractions": f200})
        fsets = []
        for alt, sol in STATES:
            a = atm_of(alt, sol)
            fsets.append((f"{alt:g}{sol}", {"O": a["fO"], "N2": a["fN2"], "O2": a["fO2"]}))
        fsets += [("pureO", {"O": 1.0}), ("pureN2", {"N2": 1.0}), ("pureO2", {"O2": 1.0}),
                  ("N2O", {"N2": 1.0, "O": 1.0}), ("O2O_Xe0", {"O2": 0.3, "O": 0.7, "Xe": 0.0})]
        for pi_, p in enumerate(((10.0, 0.85, 0.5, 0.0), (5.0, 0.85, 0.8, 0.0))):
            for sc in ("maxwell", "cll"):
                for name, fr in fsets:
                    ev.append({"id": f"E4-P{pi_}-{sc}-{name}", "group": "golden_points", "scattering": sc,
                               "point": list(p), "fractions": fr})
    rng = np.random.default_rng(np.random.SeedSequence([master, 4, 0, 4]))
    for i in range(32):
        p = [float(rng.uniform(3.0, 20.0)), float(rng.uniform(0.8, 0.9)), float(rng.uniform(0.0, 1.0)),
             float(rng.uniform(0.0, 5.0))]
        for j, ax in enumerate(AXES):
            if rng.uniform() < 0.5:
                p[j] = GRID[ax][int(rng.integers(0, len(GRID[ax])))]
        sc = "maxwell" if rng.uniform() < 0.5 else "cll"
        ev.append({"id": f"E4-F{i:02d}", "group": "faces", "scattering": sc, "point": p, "fractions": f200})
    rng = np.random.default_rng(np.random.SeedSequence([master, 4, 0, 3]))
    for i in range(200):
        p = [float(rng.uniform(3.0, 20.0)), float(rng.uniform(0.8, 0.9)), float(rng.uniform(0.0, 1.0)),
             float(rng.uniform(0.0, 5.0))]
        sc = "maxwell" if rng.uniform() < 0.5 else "cll"
        w = [float(rng.uniform(0.0, 1.0)) for _ in range(3)]
        for j in range(3):
            if rng.uniform() < 0.1:
                w[j] = 0.0
        if w == [0.0, 0.0, 0.0]:
            w[1] = 1.0
        ev.append({"id": f"E4-R{i:03d}", "group": "randomized", "scattering": sc, "point": p,
                   "fractions": {"O": w[0], "N2": w[1], "O2": w[2]}})
    return ev


def py_surface(sc):
    from abep_sim.intake import _tpmc_surface
    return _tpmc_surface(atm_of(200.0, "mean"), sc)


def py_surface_eval(e):
    s = py_surface(e["scattering"])
    return plain(s(*e["point"], fractions=e["fractions"]))


def compare_surface(pid, py, rs, k_ulp=4, r_rel=1e-11):
    """E4 comparison of one evaluation; returns a list of test records."""
    tests = []
    if "err" in py or "err" in rs:
        tests.append({"vector": pid, "observable": "error", "py": py.get("err"), "rust": rs.get("err"),
                      "status": "FAIL_UNEXPECTED_ERROR"})
        return tests
    p, r = py["ok"], rs["ok"]
    for k in SURF_MIX:
        ok, d = ulp_ok(r[k], p[k], k_ulp, r_rel)
        tests.append({"vector": pid, "observable": k, "py": p[k], "rust": dec(r[k]), "rel_diff": d,
                      "status": "PASS" if ok else "FAIL"})
    order_ok = list(p["species"].keys()) == r["species_order"]
    tests.append({"vector": pid, "observable": "species keys/order", "py": list(p["species"].keys()),
                  "rust": r["species_order"], "status": "PASS" if order_ok else "FAIL"})
    tests.append({"vector": pid, "observable": "recombination", "py": p["recombination"], "rust": r["recombination"],
                  "status": "PASS" if p["recombination"] == r["recombination"] else "FAIL"})
    if order_ok:
        for s in p["species"]:
            for k in SURF_SP:
                ok, d = ulp_ok(r["species"][s][k], p["species"][s][k], k_ulp, r_rel)
                tests.append({"vector": pid, "observable": f"species.{s}.{k}", "py": p["species"][s][k],
                              "rust": dec(r["species"][s][k]), "rel_diff": d, "status": "PASS" if ok else "FAIL"})
    return tests


def cons01(out: dict) -> bool:
    sp = out["species"]
    ok = abs(sum(float(dec(v["mass_fraction"])) for v in sp.values()) - 1.0) <= 1e-12
    ok &= abs(sum(float(dec(v["mole_fraction"])) for v in sp.values()) - 1.0) <= 1e-12
    if float(dec(out["eta_c"])) > 0:
        ok &= abs(sum(float(dec(v["collected_mass_fraction"])) for v in sp.values()) - 1.0) <= 1e-12
        ok &= abs(sum(float(dec(v["collected_mole_fraction"])) for v in sp.values()) - 1.0) <= 1e-12
    return bool(ok)


def run_intake_tpmc(contract: dict, mode: str, rust: Rust, scratch: str) -> dict:
    from abep_sim.intake_tpmc import (IntakeGeometry, intake_response, clausing_transmission, response_surface,
                                      frozen_surface_build_atmosphere)
    from abep_sim.constants import K_B, AMU, M_SPECIES
    dev = mode == "dev"
    seeds = contract["campaign_seeds"]
    master = seeds["development_master_seed"] if dev else seeds["scoring_master_seed"]
    mb = float(frozen_surface_build_atmosphere()["m_mean"])
    capture = json.load(open(rel("crates/abep-intake/data/intake_surface_v1_delaunay_v1.json")))
    res: dict = {"entry_points": {}, "invariants": {}, "conservation": {}, "domain_error": [], "schema": {}}
    timings = {}

    # ---------------- E1 intake_response ----------------
    t0 = time.perf_counter()
    vecs = e1_vectors(master, dev)
    e1_tests, inv02, inv06, inv07, schema_e1, raw_e1 = [], {"python": True, "rust": True}, \
        {"python": True, "rust": True}, {"python": True, "rust": True}, True, []
    calls, pyruns = [], []
    for k, v in enumerate(vecs):
        atm = atm_of(*v["atm"])
        for r in range(16):
            s_py = int(np.random.SeedSequence([master, 1, k, 10 + 2 * r]).generate_state(1, np.uint64)[0])
            s_rs = int(np.random.SeedSequence([master, 1, k, 11 + 2 * r]).generate_state(1, np.uint64)[0])
            pyruns.append(py_call(lambda: plain(intake_response(IntakeGeometry(**v["geom"]), atm, v["alpha"],
                                                                v["theta_deg"], n=v["n"], seed=s_py,
                                                                scattering=v["scattering"],
                                                                species_mass=v["species_mass"]))))
            calls.append({"fn": "intake_response", "geom": v["geom"], "fs": freestream(atm), "alpha": v["alpha"],
                          "theta_deg": v["theta_deg"], "n": v["n"], "seed": s_rs, "scattering": v["scattering"],
                          "species_mass": v["species_mass"]})
    rsruns = rust.run(calls)
    for k, v in enumerate(vecs):
        P = pyruns[16 * k:16 * k + 16]
        R = rsruns[16 * k:16 * k + 16]
        if any("err" in x for x in P + R):
            e1_tests.append({"vector": v["id"], "observable": "error", "status": "FAIL_UNEXPECTED_ERROR",
                             "py": [x.get("err") for x in P if "err" in x][:1],
                             "rust": [x.get("err") for x in R if "err" in x][:1]})
            continue
        P = [x["ok"] for x in P]
        R = [x["ok"] for x in R]
        raw_e1.append({"vector": v, "python": P, "rust": R})
        for obs in E1_STAT:
            xp = np.array([float(dec(x[obs])) for x in P])
            xr = np.array([float(dec(x[obs])) for x in R])
            mp, mr = float(xp.mean()), float(xr.mean())
            sp, sr = float(xp.std(ddof=1) / 4.0), float(xr.std(ddof=1) / 4.0)
            z, st = zstat(mp, sp, mr, sr)
            e1_tests.append({"vector": v["id"], "observable": obs, "mean_py": mp, "se_py": sp, "mean_rust": mr,
                             "se_rust": sr, "z": z, "status": st})
        for r_i in range(16):
            ok, d = ulp_ok(R[r_i]["mass_kg"], P[r_i]["mass_kg"], 4, 1e-12)
            if not ok:
                e1_tests.append({"vector": v["id"], "observable": f"mass_kg[r{r_i}]", "py": P[r_i]["mass_kg"],
                                 "rust": R[r_i]["mass_kg"], "status": "FAIL"})
        e1_tests.append({"vector": v["id"], "observable": "mass_kg (16 replicates)", "status": "PASS" if all(
            ulp_ok(R[i]["mass_kg"], P[i]["mass_kg"], 4, 1e-12)[0] for i in range(16)) else "FAIL"})
        echo_ok = all(bits_equal(R[i][k2], P[i][k2]) for i in range(16) for k2 in E1_ECHO)
        lab_ok = all(R[i]["scattering"] == P[i]["scattering"] and R[i]["K_back_scattering"] ==
                     P[i]["K_back_scattering"] for i in range(16))
        e1_tests.append({"vector": v["id"], "observable": "echo fields", "status": "PASS" if echo_ok else "FAIL"})
        e1_tests.append({"vector": v["id"], "observable": "labels", "status": "PASS" if lab_ok else "FAIL"})
        schema_e1 &= all(list(P[i].keys()) == E1_KEYS and R[i]["fields"] == E1_KEYS and
                         set(R[i].keys()) - {"status", "fields"} == set(E1_KEYS) for i in range(16))
        for side, X in (("python", P), ("rust", R)):
            inv02[side] &= len({np.float64(float(dec(x["mass_kg"]))).tobytes() for x in X}) == 1
            for x in X:
                eo, un = float(dec(x["eta_open"])), float(dec(x["unresolved_fraction"]))
                th = math.radians(v["theta_deg"])
                g = IntakeGeometry(**v["geom"])
                expect = g.phi * eo * math.cos(th)
                if g.filter:
                    expect *= g.filter_open_frac * g.filter_transmission ** 0.5
                inv06[side] &= (0 <= eo <= 1 and 0 <= un <= 1 and eo + un <= 1 + 1e-15 and
                                abs(float(dec(x["eta_c"])) - expect) <= 1e-12 * max(abs(expect), 1e-300))
                inv07[side] &= bool(x["converged"]) == (un <= 1e-3)
        res["invariants"].setdefault("INV-09_rust_status", True)
        res["invariants"]["INV-09_rust_status"] &= all(
            (x["status"] == "MODEL_ERROR") == (not x["converged"]) for x in R)
    res["entry_points"]["E1_intake_response"] = {"tests": e1_tests, "aggregate": aggregate(e1_tests),
                                                 "n_vectors": len(vecs)}
    res["invariants"]["INV-02"] = inv02
    res["invariants"]["INV-06"] = inv06
    res["invariants"]["INV-07"] = inv07
    res["schema"]["E1_key_set"] = schema_e1
    timings["E1_s"] = round(time.perf_counter() - t0, 1)

    if dev:
        e4 = e4_evaluations(master, True, capture)
        rs = rust.run([{"fn": "surface_eval", "scattering": e["scattering"], "point": e["point"],
                        "fractions": e["fractions"]} for e in e4], m_mean_build=mb)
        e4_tests = []
        for e, r in zip(e4, rs):
            e4_tests += compare_surface(e["id"], py_call(lambda: py_surface_eval(e)), r)
        res["entry_points"]["E4_IntakeSurface"] = {"tests": e4_tests}
        res["timings"] = timings
        return res

    # ---------------- E2 clausing_transmission ----------------
    e2 = e2_vectors()
    e2_tests = []
    calls, py2 = [], []
    for k, v in enumerate(e2):
        g = np.random.default_rng(np.random.SeedSequence([master, 2, k, 0]))
        py2.append(py_call(lambda: float(clausing_transmission(g, v["r"], v["l"], v["alpha"], v["t_w"], v["m"],
                                                               n=v["n"]))))
        calls.append({"fn": "clausing_transmission",
                      "seed": int(np.random.SeedSequence([master, 2, k, 1]).generate_state(1, np.uint64)[0]),
                      **{x: v[x] for x in ("r", "l", "alpha", "t_w", "m", "n")}})
    rs2 = rust.run(calls)
    for v, p, r in zip(e2, py2, rs2):
        if "err" in p or "err" in r:
            e2_tests.append({"vector": v["id"], "observable": "K_back", "status": "FAIL_UNEXPECTED_ERROR"})
            continue
        kp, kr, n = p["ok"], float(dec(r["ok"]["K_back"])), v["n"]
        sp, sr = math.sqrt(kp * (1 - kp) / n), math.sqrt(kr * (1 - kr) / n)
        z, st = zstat(kp, sp, kr, sr)
        e2_tests.append({"vector": v["id"], "observable": "K_back", "mean_py": kp, "se_py": sp, "mean_rust": kr,
                         "se_rust": sr, "z": z, "status": st})
    res["entry_points"]["E2_clausing_transmission"] = {"tests": e2_tests, "aggregate": aggregate(e2_tests),
                                                       "n_vectors": len(e2)}

    # ---------------- E3 response_surface ----------------
    a200 = atm_of(200.0, "mean")
    rs_calls = {
        "RS-1": dict(L_over_d=(3.0, 20.0), phis=(0.8, 0.9), alphas=(0.0, 1.0), thetas=(0.0, 5.0), n=1000, area_m2=0.5,
                     species=("O", "N2"), scattering="cll"),
        "RS-2": dict(L_over_d=(5.0,), phis=(0.85,), alphas=(0.5,), thetas=(0.0, 2.0), n=1000, area_m2=0.5,
                     species=None, scattering="maxwell"),
    }
    e3_tests, inv03 = [], {"python": True, "rust": True}
    e3_raw = {}
    for name, kw in rs_calls.items():
        df = response_surface(a200, **kw)
        pcols = list(df.columns)
        prows = [plain(r) for r in df.to_dict("records")]
        rr = rust.run([{"fn": "response_surface", "fs": freestream(a200),
                        **{k: (list(v) if isinstance(v, tuple) else v) for k, v in kw.items()}}])[0]
        if "err" in rr:
            e3_tests.append({"vector": name, "observable": "error", "status": "FAIL_UNEXPECTED_ERROR", "rust": rr})
            continue
        rcols, rrows = rr["ok"]["columns"], rr["ok"]["rows"]
        e3_raw[name] = {"python_rows": prows, "rust_rows": rrows}
        e3_tests.append({"vector": name, "observable": "row count", "py": len(prows), "rust": len(rrows),
                         "status": "PASS" if len(prows) == len(rrows) else "FAIL"})
        e3_tests.append({"vector": name, "observable": "column order", "py": pcols, "rust": rcols,
                         "status": "PASS" if pcols == rcols else "FAIL"})
        key = ("species", "L_over_d", "phi", "alpha", "theta_deg")
        for i, (p, r) in enumerate(zip(prows, rrows)):
            det_ok = all(bits_equal(r[c], p[c]) for c in ("species", "alpha", "theta_deg", "L_over_d", "phi", "d_mm",
                                                           "scattering", "K_back_scattering"))
            ok, _ = ulp_ok(r["mass_kg"], p["mass_kg"], 4, 1e-12)
            e3_tests.append({"vector": f"{name}[{i}]", "observable": "row key / deterministic columns",
                             "py": [p[c] for c in key], "rust": [dec(r[c]) for c in key],
                             "status": "PASS" if det_ok else "FAIL"})
            e3_tests.append({"vector": f"{name}[{i}]", "observable": "mass_kg", "status": "PASS" if ok else "FAIL"})
        # INV-03: each row is intake_response(..., seed 0)
        sp_list = kw["species"] or (None,)
        direct_calls, direct_py = [], []
        for sp in sp_list:
            for ld in kw["L_over_d"]:
                for ph in kw["phis"]:
                    for al in kw["alphas"]:
                        for th in kw["thetas"]:
                            msp = None if sp is None else float(M_SPECIES[sp])
                            g = {"area_m2": kw["area_m2"], "L_over_d": ld, "phi": ph}
                            direct_py.append(plain(intake_response(IntakeGeometry(**g), a200, al, th, n=kw["n"],
                                                                   scattering=kw["scattering"], species_mass=msp)))
                            direct_calls.append({"fn": "intake_response", "geom": g, "fs": freestream(a200),
                                                 "alpha": al, "theta_deg": th, "n": kw["n"], "seed": 0,
                                                 "scattering": kw["scattering"], "species_mass": msp})
        direct_rs = [x["ok"] for x in rust.run(direct_calls)]
        inv03["python"] &= all(all(bits_equal(prows[i][c], direct_py[i][c]) for c in E1_KEYS)
                               for i in range(len(prows)))
        inv03["rust"] &= all(all(bits_equal(rrows[i][c], direct_rs[i][c]) for c in E1_KEYS)
                             for i in range(len(rrows)))
    res["entry_points"]["E3_response_surface"] = {"tests": e3_tests}
    res["invariants"]["INV-03"] = inv03

    # ---------------- E4 IntakeSurface ----------------
    e4 = e4_evaluations(master, False, capture)
    rcalls = [{"fn": "surface_eval", "scattering": e["scattering"], "point": e["point"], "fractions": e["fractions"]}
              for e in e4]
    rs4 = rust.run(rcalls + rcalls[:20], m_mean_build=mb)
    py4 = [py_call(lambda: py_surface_eval(e)) for e in e4]
    py4_again = [py_call(lambda: py_surface_eval(e)) for e in e4[:20]]
    e4_tests, cons = [], {"python": True, "rust": True}
    e4_capture = []
    for e, p, r in zip(e4, py4, rs4[:len(e4)]):
        e4_tests += compare_surface(e["id"], p, r)
        if "ok" in p:
            cons["python"] &= cons01(p["ok"])
        if "ok" in r:
            cons["rust"] &= cons01(r["ok"])
        e4_capture.append({"id": e["id"], "inputs": enc(e), "python": enc(p)})
    res["invariants"]["INV-01_E4"] = {"python": json.dumps(enc(py4[:20])) == json.dumps(enc(py4_again)),
                                      "rust": json.dumps(rs4[:20]) == json.dumps(rs4[len(e4):])}
    res["conservation"]["CONS-01"] = cons
    # in_bounds, domain, max_unresolved
    ib_cases = contract["inputs"]["in_bounds_cases"]
    ib_calls, ib_py = [], []
    for sc in ("maxwell", "cll"):
        s = py_surface(sc)
        for case in ib_cases:
            args = [dec(x) for x in case if x != "default"]
            ib_py.append(bool(s.in_bounds(*[float(a) for a in args])))
            ib_calls.append({"fn": "surface_in_bounds", "scattering": sc, "point": [float(a) for a in args]})
    ib_rs = rust.run(ib_calls, m_mean_build=mb)
    for i, (p, r) in enumerate(zip(ib_py, ib_rs)):
        e4_tests.append({"vector": f"in_bounds[{i}]", "observable": "in_bounds", "py": p,
                         "rust": r.get("ok", {}).get("in_bounds"),
                         "status": "PASS" if r.get("ok", {}).get("in_bounds") == p else "FAIL"})
    dom_rs = rust.run([{"fn": "surface_domain", "scattering": sc} for sc in ("maxwell", "cll")], m_mean_build=mb)
    for sc, r in zip(("maxwell", "cll"), dom_rs):
        s = py_surface(sc)
        d = s.domain()
        ro = r["ok"]
        ax_ok = all(bits_equal(ro["axes"][k][0], d["axes"][k][0]) and bits_equal(ro["axes"][k][1], d["axes"][k][1])
                    for k in AXES)
        ok = ax_ok and ro["species"] == d["species"] and ro["atmosphere_state"] == d["atmosphere_state"] and \
            ro["outside_domain"] == d["outside_domain"]
        e4_tests.append({"vector": f"domain[{sc}]", "observable": "domain()", "py": plain(d),
                         "rust": ro, "status": "PASS" if ok else "FAIL"})
        okm, _ = ulp_ok(ro["max_unresolved"], s.max_unresolved, 4, 1e-12)
        e4_tests.append({"vector": f"max_unresolved[{sc}]", "observable": "max_unresolved", "py": s.max_unresolved,
                         "rust": dec(ro["max_unresolved"]), "status": "PASS" if okm else "FAIL"})
    res["entry_points"]["E4_IntakeSurface"] = {"tests": e4_tests, "n_evaluations": len(e4)}

    # ---------------- E5 v2 gate ----------------
    from abep_sim.intake_surface_v2_spec import v2_build_status, build_intake_surface_v2
    st = v2_build_status()
    pyg = py_call(build_intake_surface_v2)
    rg = rust.run([{"fn": "surface_v2_gate"}])[0]["ok"]
    gate_ok = (pyg.get("err", {}).get("key") == "V2_BLOCKED" and rg["status"] == "NOT_EVALUATED"
               and rg["label"] == st["status"] and rg["primary_blocker"] == st["primary_blocker"]
               and rg["unregistered"] == st["unregistered"])
    res["entry_points"]["E5_surface_v2_gate"] = {"tests": [{"vector": "DE-15", "observable": "v2 gate",
                                                            "py": {"status": st, "build": pyg.get("err")},
                                                            "rust": rg, "status": "PASS" if gate_ok else "FAIL"}]}

    # ---------------- domain / error ----------------
    res["domain_error"] = domain_error_tpmc(rust, mb, a200, contract)

    # ---------------- invariants ----------------
    v0 = vecs[0]
    s0 = int(np.random.SeedSequence([master, 1, 0, 10]).generate_state(1, np.uint64)[0])
    s0r = int(np.random.SeedSequence([master, 1, 0, 11]).generate_state(1, np.uint64)[0])
    f1 = lambda: plain(intake_response(IntakeGeometry(**v0["geom"]), a200, v0["alpha"], v0["theta_deg"],  # noqa
                                       n=v0["n"], seed=s0, scattering=v0["scattering"],
                                       species_mass=v0["species_mass"]))
    c1 = {"fn": "intake_response", "geom": v0["geom"], "fs": freestream(a200), "alpha": v0["alpha"],
          "theta_deg": v0["theta_deg"], "n": v0["n"], "seed": s0r, "scattering": v0["scattering"],
          "species_mass": v0["species_mass"]}
    rr = rust.run([c1, c1])
    v2_0 = e2[0]

    def f2():
        return clausing_transmission(np.random.default_rng(np.random.SeedSequence([master, 2, 0, 0])), v2_0["r"],
                                     v2_0["l"], v2_0["alpha"], v2_0["t_w"], v2_0["m"], n=v2_0["n"])
    c2 = {"fn": "clausing_transmission", "seed": 12345, **{x: v2_0[x] for x in ("r", "l", "alpha", "t_w", "m", "n")}}
    rr2 = rust.run([c2, c2])
    res["invariants"]["INV-01_E1_E2"] = {"python": json.dumps(enc(f1())) == json.dumps(enc(f1())) and
                                         bits_equal(f2(), f2()),
                                         "rust": rr[0] == rr[1] and rr2[0] == rr2[1]}
    # INV-04: the capture equals the reference triangulation recomputed now
    res["invariants"]["INV-04"] = inv04(capture)
    # INV-08 constants
    rc = rust.run([{"fn": "constants"}])[0]["ok"]
    res["invariants"]["INV-08"] = {
        "held": bits_equal(rc["K_B"], K_B) and bits_equal(rc["AMU"], AMU) and bits_equal(rc["K_B_abep_core"], K_B)
        and all(bits_equal(rc["M_SPECIES"][s], M_SPECIES[s]) for s in M_SPECIES),
        "rust": rc}
    # defaults of IntakeGeometry
    dflt = rust.run([{"fn": "defaults"}])[0]["ok"]["IntakeGeometry"]
    g = IntakeGeometry()
    res["schema"]["IntakeGeometry_defaults"] = all(bits_equal(dflt[k], getattr(g, k)) for k in dflt)

    # captured reference outputs (deterministic parts)
    res["captured"] = {"E4_evaluations": e4_capture, "E3": e3_raw, "domain_error": res["domain_error"],
                       "m_mean_build_kg": mb}
    res["raw_E1"] = raw_e1
    res["timings"] = timings
    return res


def inv04(capture: dict) -> dict:
    from scipy.interpolate import LinearNDInterpolator
    from abep_sim.intake_tpmc import frozen_surface_path
    df = pd.read_csv(frozen_surface_path())
    ok = True
    n = 0
    for sc in ("maxwell", "cll"):
        sdf = df[df.scattering == sc].reset_index(drop=True)
        for sp in sorted(sdf["species"].unique()):
            d = sdf[sdf["species"] == sp]
            for col in ("eta_c", "C_D", "CR_passive", "K_back", "mass_kg"):
                ip = LinearNDInterpolator(d[list(AXES)].values, d[col].values, rescale=True)
                ok &= (np.array_equal(np.asarray(d[list(AXES)].values, dtype=np.float64), np.array(capture["points"]))
                       and np.array_equal(ip.offset, np.array(capture["rescale"]["offset"]))
                       and np.array_equal(ip.scale, np.array(capture["rescale"]["scale"]))
                       and np.array_equal(ip.tri.simplices, np.array(capture["simplices"]))
                       and np.array_equal(np.isnan(ip.tri.transform[:, 0, 0]), np.array(capture["degenerate"])))
                n += 1
    return {"held": bool(ok), "interpolators_checked": n}


def de_record(cid, py, rs, py_key, rs_key, rs_status="OUT_OF_DOMAIN"):
    pk = py.get("err", {}).get("key") if isinstance(py, dict) else None
    rk = rs.get("err", {}).get("key")
    rst = rs.get("err", {}).get("status")
    ok = pk == py_key and rk == rs_key and rst == rs_status
    return {"id": cid, "python": py.get("err") if isinstance(py, dict) else py, "rust": rs.get("err", rs.get("ok")),
            "expected_python_key": py_key, "expected_rust": [rs_key, rs_status], "status": "PASS" if ok else "FAIL"}


def domain_error_tpmc(rust: Rust, mb: float, a200: dict, contract: dict) -> list[dict]:
    from abep_sim.intake_tpmc import IntakeGeometry, intake_response, clausing_transmission, response_surface
    from abep_sim.intake_tpmc import IntakeSurface, frozen_surface_path
    out = []
    f200 = {"O": a200["fO"], "N2": a200["fN2"], "O2": a200["fO2"]}
    s = py_surface("maxwell")
    surf_cases = [
        ("DE-01", [2.999, 0.85, 0.5, 0.0], f200, "OUT_OF_BOUNDS"),
        ("DE-02", [10.0, 0.95, 0.5, 0.0], f200, "OUT_OF_BOUNDS"),
        ("DE-03", [10.0, 0.85, -0.01, 0.0], f200, "OUT_OF_BOUNDS"),
        ("DE-04", [10.0, 0.85, 1.0000001, 0.0], f200, "OUT_OF_BOUNDS"),
        ("DE-05", [10.0, 0.85, 0.5, 5.5], f200, "OUT_OF_BOUNDS"),
        ("DE-06", [10.0, 0.85, 0.5, float("nan")], f200, "OUT_OF_BOUNDS"),
        ("DE-07", [10.0, 0.85, 0.5, 0.0], None, "FRACTIONS_REQUIRED"),
        ("DE-08", [10.0, 0.85, 0.5, 0.0], {}, "FRACTIONS_REQUIRED"),
        ("DE-09", [10.0, 0.85, 0.5, 0.0], {"O": -0.1, "N2": 1.0}, "FRACTION_INVALID"),
        ("DE-10", [10.0, 0.85, 0.5, 0.0], {"O": float("nan"), "N2": 1.0}, "FRACTION_INVALID"),
        ("DE-11", [10.0, 0.85, 0.5, 0.0], {"O": float("inf"), "N2": 1.0}, "FRACTION_INVALID"),
        ("DE-12", [10.0, 0.85, 0.5, 0.0], {"N2": 0.5, "Ar": 0.5}, "FOREIGN_SPECIES"),
        ("DE-13", [10.0, 0.85, 0.5, 0.0], {"O": 0.0, "N2": 0.0, "O2": 0.0}, "ALL_ZERO"),
    ]
    rs = rust.run([{"fn": "surface_eval", "scattering": "maxwell", "point": p, "fractions": f}
                   for _, p, f, _ in surf_cases], m_mean_build=mb)
    for (cid, p, f, key), r in zip(surf_cases, rs):
        out.append(de_record(cid, py_call(lambda: s(*p, fractions=f)), r, key, key))
    df = pd.read_csv(frozen_surface_path())
    dmx = df[df.scattering == "maxwell"].reset_index(drop=True)
    vals = [0.0, -1.0, float("nan"), float("inf")]
    rs = rust.run([{"fn": "surface_load", "m_mean_build_kg": v} for v in vals])
    for v, r in zip(vals, rs):
        out.append(de_record(f"DE-14[{v}]", py_call(lambda: IntakeSurface(dmx, m_mean_build_kg=v)), r,
                             "M_MEAN_BUILD_REQUIRED", "M_MEAN_BUILD_REQUIRED"))
    g0 = {"area_m2": 0.5, "L_over_d": 3.0, "phi": 0.85}
    e1_cases = [("DE-20", "specular", 0.0, "UNKNOWN_SCATTERING"), ("DE-21", "Maxwell", 0.0, "UNKNOWN_SCATTERING"),
                ("DE-22", "maxwell", 1.5, "ACCOMMODATION_INVALID"), ("DE-23", "cll", -0.1, "ACCOMMODATION_INVALID"),
                ("DE-24", "maxwell", float("nan"), "ACCOMMODATION_INVALID")]
    from abep_sim.constants import M_SPECIES
    mN2 = float(M_SPECIES["N2"])
    rs = rust.run([{"fn": "intake_response", "geom": g0, "fs": freestream(a200), "alpha": al, "theta_deg": 0.0,
                    "n": 4000, "seed": 0, "scattering": sc, "species_mass": mN2} for _, sc, al, _ in e1_cases])
    for (cid, sc, al, key), r in zip(e1_cases, rs):
        out.append(de_record(cid, py_call(lambda: intake_response(IntakeGeometry(**g0), a200, al, 0.0, n=4000,
                                                                  scattering=sc, species_mass=mN2)), r, key, key))
    rs2 = dict(L_over_d=[5.0], phis=[0.85], alphas=[0.5], thetas=[0.0, 2.0], n=1000, area_m2=0.5)
    rcases = [("DE-25", {"species": None, "scattering": "diffuse"}, "UNKNOWN_SCATTERING"),
              ("DE-26", {"species": ["Ar"], "scattering": "maxwell"}, "UNKNOWN_SPECIES")]
    rs = rust.run([{"fn": "response_surface", "fs": freestream(a200), **rs2, **kw} for _, kw, _ in rcases])
    for (cid, kw, key), r in zip(rcases, rs):
        pykw = {k: tuple(v) for k, v in rs2.items() if isinstance(v, list)}
        pykw.update({"n": 1000, "area_m2": 0.5, "species": tuple(kw["species"]) if kw["species"] else None,
                     "scattering": kw["scattering"]})
        out.append(de_record(cid, py_call(lambda: response_surface(a200, **pykw)), r, key, key))
    r = rust.run([{"fn": "clausing_transmission", "seed": 0, "r": 0.005, "l": 0.03, "alpha": 2.0, "t_w": 350.0,
                   "m": mN2, "n": 20000}])[0]
    out.append(de_record("DE-27", py_call(lambda: clausing_transmission(np.random.default_rng(0), 0.005, 0.03, 2.0,
                                                                         350.0, mN2, n=20000)), r,
                         "ACCOMMODATION_INVALID", "ACCOMMODATION_INVALID"))
    return out


# ====================================================================================================================
# Contract B: intake
# ====================================================================================================================

COMP_KEYS = ["p_out_Pa", "p_passive_Pa", "passive_ratio", "active_ratio", "ratio_effective", "mdot_net", "n_out",
             "comp_power_W", "comp_mass_kg", "comp_feasible"]
COLL_KEYS = ["eta_c", "mdot_incident", "mdot_collected", "C_D", "drag_N", "intake_mass_kg", "passive_override",
             "mdot_collected_species"]


def atm_random(rng):
    return ((180.0, 200.0, 230.0)[int(rng.integers(0, 3))], ("low", "mean", "high")[int(rng.integers(0, 3))])


def intake_vectors(master: int, dev: bool) -> dict:
    V = {"F1": [], "F2": [], "F3P": [], "F3T": []}
    if not dev:
        for alt, sol in STATES:
            for eta in (0.25, 0.45):
                V["F1"].append({"id": f"F1-G-{alt:g}{sol}-eta{eta}", "comp": {}, "atm": (alt, sol), "eta_c": eta})
        base = {"comp": {}, "atm": (200.0, "mean"), "mdot_col": 1e-6, "eta_c": 0.35, "passive_override": None}
        for cid, kw in [("C-01", {}), ("C-02", {"passive_override": 60.0}), ("C-03", {"comp": {"ratio": 10.0}}),
                        ("C-04", {"comp": {"anode_conductance_m3_s": 1e-4}}),
                        ("C-05", {"comp": {"anode_conductance_m3_s": 1e-2}, "mdot_col": 1e-8}),
                        ("C-06", {"comp": {"backflow_frac": 0.3}}), ("C-07", {"comp": {"max_ratio": 10.0}}),
                        ("C-08", {"atm": (180.0, "low"), "comp": {"T_out_K": 300.0, "area_ratio": 20.0}}),
                        ("C-09", {"passive_override": 1e6}), ("C-10", {"mdot_col": 0.0}),
                        ("E-03", {"comp": {"ratio": 1000000.0}})]:
            v = copy.deepcopy(base)
            v.update(kw)
            v["id"] = f"F2-{cid}"
            V["F2"].append(v)
        for cid, kw in [("P-01", {}), ("P-02", {"accommodation": 0.0, "off_axis_deg": 3.0}),
                        ("P-03", {"accommodation": 1.0, "off_axis_deg": 10.0, "body_area_m2": 0.3}),
                        ("P-04", {"area_m2": 2.0, "accommodation": 0.8}), ("P-05", {"__vrel": 1.01}),
                        ("P-06", {"__atm": (230.0, "high")}), ("E-01", {"off_axis_deg": 30.0})]:
            atm = kw.pop("__atm", (200.0, "mean"))
            vrel = kw.pop("__vrel", None)
            V["F3P"].append({"id": f"F3-{cid}", "intake": dict(kw, use_tpmc=False), "atm": atm, "vrel_factor": vrel})
        # T-01..T-06 in golden.py case_intake order: scattering outer, (a, ld) inner
        t = [({"area_m2": 0.7, "accommodation": a, "L_over_d": ld, "scattering": sc}, (200.0, "mean"))
             for sc in ("maxwell", "cll") for a, ld in ((0.8, 5.0), (0.95, 10.0), (0.5, 3.0))]
        t += [({"area_m2": 0.7, "accommodation": 0.8, "L_over_d": 5.0, "scattering": "maxwell"}, st) for st in STATES]
        t.append(({"area_m2": 0.7, "accommodation": 0.5, "L_over_d": 10.0, "phi": 0.85, "scattering": "cll",
                   "filter": True}, (200.0, "mean")))
        t.append(({"area_m2": 0.7, "accommodation": 0.8, "L_over_d": 5.0, "scattering": "maxwell",
                   "off_axis_deg": 4.0}, (200.0, "mean")))
        t.append(({"phi": 0.9, "L_over_d": 20.0, "accommodation": 1.0, "scattering": "maxwell"}, (200.0, "mean")))
        for i, (kw, st) in enumerate(t):
            V["F3T"].append({"id": f"F3-T-{i + 1:02d}", "intake": dict(kw, use_tpmc=True), "atm": st,
                             "vrel_factor": None})
        V["F3T"].append({"id": "F3-E-02", "intake": {"use_tpmc": True, "accommodation": 0.0, "off_axis_deg": 5.0,
                                                     "L_over_d": 3.0, "phi": 0.8}, "atm": (200.0, "mean"),
                         "vrel_factor": None})
    rng = np.random.default_rng(np.random.SeedSequence([master, 1, 0, 3]))
    for i in range(40):
        comp = {"T_out_K": float(rng.uniform(250, 450)), "area_ratio": float(rng.uniform(1, 50))}
        eta = float(rng.uniform(0, 1))
        V["F1"].append({"id": f"F1-R{i:02d}", "comp": comp, "eta_c": eta, "atm": atm_random(rng)})
    rng = np.random.default_rng(np.random.SeedSequence([master, 2, 0, 3]))
    for i in range(60):
        comp = {"ratio": float(np.exp(rng.uniform(np.log(1.0), np.log(1e4)))), "area_ratio": float(rng.uniform(1, 50)),
                "T_out_K": float(rng.uniform(250, 450)), "p_base_W": float(rng.uniform(0, 100)),
                "p_per_mgps_per_ln": float(rng.uniform(0, 30)),
                "max_ratio": float(np.exp(rng.uniform(np.log(10.0), np.log(1e4))))}
        comp["anode_conductance_m3_s"] = None if rng.uniform() < 0.5 else float(
            np.exp(rng.uniform(np.log(1e-5), np.log(1e-1))))
        comp["backflow_frac"] = 0.0 if rng.uniform() < 0.5 else float(rng.uniform(0.0, 0.5))
        comp["mass_base_kg"] = float(rng.uniform(1, 5))
        comp["mass_per_ln"] = float(rng.uniform(0, 1))
        mdot = float(np.exp(rng.uniform(np.log(1e-8), np.log(1e-5))))
        eta = float(rng.uniform(0.05, 0.9))
        ov = None if rng.uniform() < 0.5 else float(np.exp(rng.uniform(np.log(1.0), np.log(1000.0))))
        V["F2"].append({"id": f"F2-R{i:02d}", "comp": comp, "mdot_col": mdot, "eta_c": eta, "passive_override": ov,
                        "atm": atm_random(rng)})
    rng = np.random.default_rng(np.random.SeedSequence([master, 3, 0, 3]))
    for i in range(30):
        kw = {"area_m2": float(rng.uniform(0.2, 1.5)), "body_area_m2": float(rng.uniform(0, 0.5)),
              "accommodation": float(rng.uniform(0, 1)), "off_axis_deg": float(rng.uniform(0, 20)),
              "eta_c_specular": float(rng.uniform(0.3, 0.6)), "eta_c_diffuse": float(rng.uniform(0.1, 0.3)),
              "cd": float(rng.uniform(2.0, 2.6)), "mass_per_m2": float(rng.uniform(1, 4)),
              "mass_fixed": float(rng.uniform(0, 2)), "use_tpmc": False}
        V["F3P"].append({"id": f"F3-PR{i:02d}", "intake": kw, "atm": atm_random(rng), "vrel_factor": None})
    rng = np.random.default_rng(np.random.SeedSequence([master, 4, 0, 3]))
    for i in range(60):
        kw = {"area_m2": float(rng.uniform(0.2, 1.5)), "body_area_m2": float(rng.uniform(0, 0.5)),
              "accommodation": float(rng.uniform(0, 1)), "off_axis_deg": float(rng.uniform(0, 5)),
              "scattering": "maxwell" if rng.uniform() < 0.5 else "cll", "L_over_d": float(rng.uniform(3, 20)),
              "phi": float(rng.uniform(0.8, 0.9)), "filter": bool(rng.uniform() < 0.25), "use_tpmc": True}
        st = atm_random(rng)
        vrel = float(rng.uniform(0.98, 1.02)) if rng.uniform() < 0.3 else None
        V["F3T"].append({"id": f"F3-TR{i:02d}", "intake": kw, "atm": st, "vrel_factor": vrel})
    return V


def atm_for(v) -> dict:
    a = atm_of(*v["atm"])
    if v.get("vrel_factor") is not None:
        a["V_rel"] = a["V"] * v["vrel_factor"]
    return a


def py_comp(kw):
    from abep_sim.intake import CompressorParams
    return CompressorParams(**kw)


def py_intake(kw):
    from abep_sim.intake import IntakeParams
    return IntakeParams(**kw)


def norm_collection(d: dict) -> dict:
    d = plain(d)
    sp = d.get("mdot_collected_species")
    d["mdot_collected_species"] = None if sp is None else [[k, v] for k, v in sp.items()]
    return d


def cmp_fields(vid, p, r, keys, k_ulp, r_rel_of):
    tests = []
    if "err" in p or "err" in r:
        return [{"vector": vid, "observable": "error", "py": p.get("err"), "rust": r.get("err"),
                 "status": "FAIL_UNEXPECTED_ERROR"}]
    p, r = p["ok"], r["ok"]
    tests.append({"vector": vid, "observable": "key set", "status": "PASS" if set(p) == set(r) else "FAIL"})
    for k in keys:
        pv, rv = p.get(k), r.get(k)
        if isinstance(pv, bool) or isinstance(rv, bool):
            ok = pv == rv
        elif k == "mdot_collected_species":
            ok = (pv is None and rv is None) or (pv is not None and rv is not None and [x[0] for x in pv] ==
                                                [x[0] for x in rv] and all(ulp_ok(b[1], a[1], k_ulp, r_rel_of(k))[0]
                                                                           for a, b in zip(pv, rv)))
        elif pv is None or rv is None:
            ok = pv is None and rv is None
        else:
            ok = ulp_ok(rv, pv, k_ulp, r_rel_of(k))[0]
        tests.append({"vector": vid, "observable": k, "py": pv, "rust": rv, "status": "PASS" if ok else "FAIL"})
    return tests


def run_intake(contract: dict, mode: str, rust: Rust, scratch: str) -> dict:
    from abep_sim.intake import collection, compress, passive_compression, IntakeParams, CompressorParams
    from abep_sim.intake_tpmc import frozen_surface_build_atmosphere
    dev = mode == "dev"
    seeds = contract["campaign_seeds"]
    master = seeds["development_master_seed"] if dev else seeds["scoring_master_seed"]
    mb = float(frozen_surface_build_atmosphere()["m_mean"])
    V = intake_vectors(master, dev)
    res: dict = {"entry_points": {}, "invariants": {}, "conservation": {}, "domain_error": [], "schema": {}}
    cap = {}

    # F1
    py1 = [py_call(lambda: float(passive_compression(py_comp(v["comp"]), atm_for(v), v["eta_c"]))) for v in V["F1"]]
    rs1 = rust.run([{"fn": "passive_compression", "comp": v["comp"], "fs": freestream(atm_for(v)),
                     "eta_c": v["eta_c"]} for v in V["F1"]])
    t1 = []
    for v, p, r in zip(V["F1"], py1, rs1):
        if "err" in p or "err" in r:
            t1.append({"vector": v["id"], "observable": "error", "status": "FAIL_UNEXPECTED_ERROR"})
            continue
        ok, d = ulp_ok(r["ok"]["passive"], p["ok"], 4, 1e-12)
        t1.append({"vector": v["id"], "observable": "passive", "py": p["ok"], "rust": dec(r["ok"]["passive"]),
                   "rel_diff": d, "status": "PASS" if ok else "FAIL"})
    res["entry_points"]["F1_passive_compression"] = {"tests": t1}
    cap["F1"] = [{"inputs": enc(v), "python": enc(p)} for v, p in zip(V["F1"], py1)]

    # F2
    py2 = [py_call(lambda: plain(compress(py_comp(v["comp"]), atm_for(v), v["mdot_col"], eta_c=v["eta_c"],
                                          passive_override=v["passive_override"]))) for v in V["F2"]]
    rs2 = rust.run([{"fn": "compress", "comp": v["comp"], "fs": freestream(atm_for(v)), "mdot_col": v["mdot_col"],
                     "eta_c": v["eta_c"], "passive_override": v["passive_override"]} for v in V["F2"]])
    t2 = []
    cons2 = {"python": True, "rust": True}
    inv03 = {"python": True, "rust": True}
    for v, p, r in zip(V["F2"], py2, rs2):
        t2 += cmp_fields(v["id"], p, r, COMP_KEYS, 4, lambda k: 1e-12)
        for side, x in (("python", p), ("rust", r)):
            if "ok" not in x:
                continue
            o = {k: dec(val) for k, val in x["ok"].items()}
            bf = py_comp(v["comp"]).backflow_frac
            lhs, rhs = o["mdot_net"] + v["mdot_col"] * bf, v["mdot_col"]
            cons2[side] &= abs(lhs - rhs) <= 1e-12 * max(abs(rhs), 0.0) if rhs != 0 else lhs == 0
            inv03[side] &= (o["active_ratio"] >= 1 and o["ratio_effective"] >= o["passive_ratio"] and
                            o["comp_feasible"] == (o["active_ratio"] <= py_comp(v["comp"]).max_ratio))
    res["entry_points"]["F2_compress"] = {"tests": t2}
    res["conservation"]["CONS-02"] = cons2
    res["invariants"]["INV-03"] = inv03
    cap["F2"] = [{"inputs": enc(v), "python": enc(p)} for v, p in zip(V["F2"], py2)]

    # F3
    allv = V["F3P"] + V["F3T"]
    py3 = [py_call(lambda: norm_collection(collection(py_intake(v["intake"]), atm_for(v)))) for v in allv]
    rs3 = rust.run([{"fn": "collection", "intake": v["intake"], "fs": freestream(atm_for(v))} for v in allv],
                   m_mean_build=mb)
    t3 = []
    cons1 = {"python": True, "rust": True}
    inv02 = {"python": True, "rust": True}
    for v, p, r in zip(allv, py3, rs3):
        tp = v["intake"]["use_tpmc"]
        t3 += cmp_fields(v["id"], p, r, COLL_KEYS, 4,
                         (lambda k: 1e-12 if k == "mdot_incident" else 1e-11) if tp else (lambda k: 1e-12))
        for side, x in (("python", p), ("rust", r)):
            if "ok" not in x:
                continue
            o = x["ok"]
            eta, mi, mc = float(dec(o["eta_c"])), float(dec(o["mdot_incident"])), float(dec(o["mdot_collected"]))
            ok = abs(mc - eta * mi) <= 1e-12 * abs(mc) if mc else eta * mi == 0
            if tp:
                sp = sum(float(dec(s[1])) for s in o["mdot_collected_species"])
                ok &= abs(sp - mc) <= 1e-12 * abs(mc)
                inv02[side] &= (o["passive_override"] is not None and
                                [s[0] for s in o["mdot_collected_species"]] == [s for s in ("N2", "O", "O2")
                                                                             if atm_for(v)[{"N2": "fN2", "O": "fO",
                                                                                            "O2": "fO2"}[s]] > 0])
            else:
                inv02[side] &= o["passive_override"] is None and o["mdot_collected_species"] is None
            cons1[side] &= bool(ok)
    res["entry_points"]["F3_collection"] = {"tests": t3}
    res["conservation"]["CONS-01"] = cons1
    res["invariants"]["INV-02"] = inv02
    cap["F3"] = [{"inputs": enc(v), "python": enc(p)} for v, p in zip(allv, py3)]
    if dev:
        return res

    # INV-01 determinism (first 10 vectors of each entry point)
    r1 = rust.run([{"fn": "passive_compression", "comp": v["comp"], "fs": freestream(atm_for(v)), "eta_c": v["eta_c"]}
                   for v in V["F1"][:10]])
    r2 = rust.run([{"fn": "compress", "comp": v["comp"], "fs": freestream(atm_for(v)), "mdot_col": v["mdot_col"],
                    "eta_c": v["eta_c"], "passive_override": v["passive_override"]} for v in V["F2"][:10]])
    r3 = rust.run([{"fn": "collection", "intake": v["intake"], "fs": freestream(atm_for(v))}
                   for v in V["F3P"][:10] + V["F3T"][:10]], m_mean_build=mb)
    p1 = [py_call(lambda: float(passive_compression(py_comp(v["comp"]), atm_for(v), v["eta_c"]))) for v in V["F1"][:10]]
    p2 = [py_call(lambda: plain(compress(py_comp(v["comp"]), atm_for(v), v["mdot_col"], eta_c=v["eta_c"],
                                         passive_override=v["passive_override"]))) for v in V["F2"][:10]]
    p3 = [py_call(lambda: norm_collection(collection(py_intake(v["intake"]), atm_for(v))))
          for v in V["F3P"][:10] + V["F3T"][:10]]
    res["invariants"]["INV-01"] = {
        "python": json.dumps(enc(p1 + p2 + p3)) == json.dumps(enc(py1[:10] + py2[:10] + py3[:10] +
                                                                  py3[len(V["F3P"]):len(V["F3P"]) + 10])),
        "rust": json.dumps(r1 + r2 + r3) == json.dumps(rs1[:10] + rs2[:10] + rs3[:10] +
                                                        rs3[len(V["F3P"]):len(V["F3P"]) + 10])}
    # INV-05 defaults
    d = rust.run([{"fn": "defaults"}])[0]["ok"]
    ip, cp = IntakeParams(), CompressorParams()
    res["invariants"]["INV-05"] = {"held": all(bits_equal(d["IntakeParams"][k], getattr(ip, k))
                                               for k in d["IntakeParams"]) and
                                   all(bits_equal(d["CompressorParams"][k], getattr(cp, k))
                                       for k in d["CompressorParams"])}
    # domain / error
    a200 = atm_of(200.0, "mean")
    t07 = {"area_m2": 0.7, "accommodation": 0.8, "L_over_d": 5.0, "scattering": "maxwell", "use_tpmc": True}
    cases = [("DE-01", dict(t07, off_axis_deg=6.0), None, "OUT_OF_BOUNDS", "OUT_OF_BOUNDS"),
             ("DE-02", dict(t07, accommodation=1.2), None, "OUT_OF_BOUNDS", "OUT_OF_BOUNDS"),
             ("DE-03", dict(t07, L_over_d=2.5), None, "OUT_OF_BOUNDS", "OUT_OF_BOUNDS"),
             ("DE-04", dict(t07, scattering="specular"), None, "OUT_OF_BOUNDS", "UNKNOWN_SCATTERING"),
             ("DE-05", t07, {"fO": 0.0, "fN2": 0.0, "fO2": 0.0}, "ALL_ZERO", "ALL_ZERO"),
             ("DE-06", t07, {"fO": 0.5, "fN2": -0.1, "fO2": 0.6}, "FRACTION_INVALID", "FRACTION_INVALID")]
    rs = rust.run([{"fn": "collection", "intake": kw, "fs": freestream(dict(a200, **(fr or {})))}
                   for _, kw, fr, _, _ in cases], m_mean_build=mb)
    for (cid, kw, fr, pk, rk), r in zip(cases, rs):
        res["domain_error"].append(de_record(cid, py_call(lambda: collection(py_intake(kw), dict(a200, **(fr or {})))),
                                             r, pk, rk))
    ccases = [("DE-07", {}, None), ("DE-08", {"anode_conductance_m3_s": 1e-4}, None)]
    rs = rust.run([{"fn": "compress", "comp": c, "fs": freestream(a200), "mdot_col": 1e-6, "eta_c": 0.0,
                    "passive_override": ov} for _, c, ov in ccases])
    for (cid, c, ov), r in zip(ccases, rs):
        res["domain_error"].append(de_record(cid, py_call(lambda: compress(py_comp(c), a200, 1e-6, eta_c=0.0,
                                                                           passive_override=ov)),
                                             r, "PASSIVE_ZERO", "PASSIVE_ZERO"))
    res["captured"] = dict(cap, m_mean_build_kg=mb, domain_error=res["domain_error"])
    return res


# ====================================================================================================================
# report
# ====================================================================================================================

def entry_pass(ep: dict) -> bool:
    tests = ep.get("tests", [])
    bad = [t for t in tests if t["status"] not in ("PASS", "WITHIN", "AGREE_EXACT")]
    agg = ep.get("aggregate", {})
    return not bad and all(a["within"] for a in agg.values())


def counts(ep: dict) -> dict:
    c = {}
    for t in ep.get("tests", []):
        c[t["status"]] = c.get(t["status"], 0) + 1
    return c


def inv_held(v) -> bool:
    if isinstance(v, bool):
        return v
    if "held" in v:
        return bool(v["held"])
    return all(bool(x) for x in v.values() if isinstance(x, bool))


def build_provenance() -> dict:
    files = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/abep-intake/Cargo.toml",
             "crates/abep-intake/data/intake_surface_v1_delaunay_v1.json",
             "crates/abep-intake/examples/intake_parity.rs"]
    src = sorted(os.path.join("crates/abep-intake/src", f) for f in os.listdir(rel("crates/abep-intake/src")))
    core = ["abep_core/Cargo.toml", "abep_core/Cargo.lock", "abep_core/src/lib.rs", "abep_core/src/rng.rs",
            "abep_core/src/tpmc.rs"]
    env = dict(os.environ, PATH=CARGO_BIN + os.pathsep + os.environ.get("PATH", ""))
    return {"source_sha256": {p: sha(rel(p)) for p in files + src + core},
            "rustc": subprocess.run(["rustc", "--version"], cwd=ROOT, env=env, capture_output=True,
                                    text=True).stdout.strip(),
            "cargo": subprocess.run(["cargo", "--version"], cwd=ROOT, env=env, capture_output=True,
                                    text=True).stdout.strip(),
            "build_profile": "release (workspace [profile.release]: opt-level 3)",
            "harness": {"path": "scripts/rust_migration/parity_intake.py",
                        "sha256": sha(os.path.abspath(__file__))}}


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def machine() -> dict:
    mem = {}
    try:
        for ln in open("/proc/meminfo"):
            if ln.startswith(("MemTotal", "MemAvailable")):
                k, v = ln.split(":")
                mem[k] = v.strip()
    except OSError:
        pass
    cpu = None
    try:
        cpu = next(ln.split(":", 1)[1].strip() for ln in open("/proc/cpuinfo") if ln.startswith("model name"))
    except (OSError, StopIteration):
        pass
    return {"utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "platform": platform.platform(), "cpu": cpu, "logical_cpus": os.cpu_count(), "memory": mem,
            "loadavg": list(os.getloadavg()),
            "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                                          "NUMEXPR_NUM_THREADS", "RAYON_NUM_THREADS")}}


def perf(rust: Rust) -> dict:
    """PRE_RUST workload intake_response_surface_reduced: reported, never a criterion."""
    from abep_sim.atmosphere import atmosphere
    from abep_sim.intake_tpmc import response_surface
    p = {"L_over_d": [3, 5, 10, 20], "phis": [0.8], "alphas": [0.0, 0.5, 1.0], "thetas": [0.0], "species": ["N2"],
         "n": 20000}
    atm = atmosphere(200.0, "mean")

    def run():
        return response_surface(atm, L_over_d=tuple(p["L_over_d"]), phis=tuple(p["phis"]),
                                alphas=tuple(p["alphas"]), thetas=tuple(p["thetas"]), n=p["n"],
                                species=tuple(p["species"]))
    before = machine()
    run()
    wall, cpu = [], []
    for _ in range(3):
        t0, c0 = time.perf_counter(), time.process_time()
        df = run()
        wall.append(time.perf_counter() - t0)
        cpu.append(time.process_time() - c0)
    rr = rust.run([{"fn": "perf_response_surface", "fs": freestream(atm), "L_over_d": [float(x) for x in p["L_over_d"]],
                    "phis": p["phis"], "alphas": p["alphas"], "thetas": p["thetas"], "n": p["n"], "area_m2": 0.5,
                    "species": p["species"], "scattering": "maxwell", "repeats": 3}])[0]["ok"]
    after = machine()
    mp, mr = float(np.median(wall)), float(np.median(rr["wall_s"]))
    cp, cr = float(np.median(cpu)), float(np.median(rr["cpu_s"]))
    return {"status": "reported, not a decision criterion (RM-R09)", "workload": "intake_response_surface_reduced",
            "definition": "scripts/perf/profile_baseline.py w_response_surface with rs_full (12 points, n 20000)",
            "params": p, "points": {"python": int(len(df)), "rust": rr["points"]},
            "python": {"wall_s": wall, "cpu_s": cpu, "median_wall_s": mp, "median_cpu_s": cp,
                       "clock": "time.perf_counter / time.process_time"},
            "rust": {"wall_s": rr["wall_s"], "cpu_s": rr["cpu_s"], "median_wall_s": mr, "median_cpu_s": cr,
                     "clock": "std::time::Instant / " + rr["cpu_clock"], "build": "release example intake_parity"},
            "speedup_wall": mp / mr, "speedup_cpu": cp / cr if cr > 0 else None,
            "warm_up": "one untimed call per implementation", "repeats": 3,
            "baseline_reference": {"path": "docs/performance/pre_rust_reference_baseline_5eee4b8/baseline.json",
                                   "recorded_python_median_wall_s_at_5eee4b8": 5.023,
                                   "note": "quoted, not reused; the Python timing above is this session's"},
            "threads": "Python: OMP / OPENBLAS / MKL / NUMEXPR = 1 (as the baseline); Rust: single-threaded (no "
                       "thread pool in abep-intake or abep_core)",
            "machine_before": before, "machine_after": after}


def write_report(cname: str, cdir: str, contract: dict, res: dict, rust: Rust, started: str, ref_ok: dict,
                 pinned_ok: dict, frozen_before: dict, perf_rec) -> dict:
    eps = {k: {"result": "PARITY_PASS" if entry_pass(v) else "PARITY_FAIL", "counts": counts(v),
               "aggregate": v.get("aggregate", {})} for k, v in res["entry_points"].items()}
    frozen_after = {p: sha(rel(p)) for p in ("abep_sim/data/intake_surface_v1.csv", "abep_sim/data/intake_surface_v1.json")}
    res["invariants"]["INV-05_frozen_unchanged" if cname == "intake_tpmc" else "INV-04_frozen_unchanged"] = {
        "held": frozen_before == frozen_after and all(
            frozen_after[p] == contract["pinned_inputs_sha256"][p] for p in frozen_after)}
    inv_ok = all(inv_held(v) for v in res["invariants"].values())
    cons_ok = all(inv_held(v) for v in res["conservation"].values())
    de_ok = all(d["status"] == "PASS" for d in res["domain_error"])
    schema_ok = all(bool(v) for v in res["schema"].values())
    refs_ok = all(ref_ok.values()) and all(pinned_ok.values())
    if not refs_ok:
        verdict = "REFUSED_REFERENCE_CHANGED"
    else:
        verdict = "ADMITTED" if (all(e["result"] == "PARITY_PASS" for e in eps.values()) and inv_ok and cons_ok and
                                 de_ok and schema_ok) else "NOT_ADMITTED"
    # captured reference outputs
    rdir = os.path.join(cdir, "reference_outputs")
    os.makedirs(rdir, exist_ok=True)
    manifest = {}
    for k, v in res.pop("captured").items():
        path = os.path.join(rdir, f"{k}.json")
        with open(path, "w") as f:
            json.dump(enc(v), f, indent=None, separators=(",", ":"))
            f.write("\n")
        manifest[os.path.relpath(path, ROOT)] = sha(path)
    raw_e1 = res.pop("raw_E1", None)
    if raw_e1 is not None:
        path = os.path.join(rdir, "E1_replicates.json")
        with open(path, "w") as f:
            json.dump(enc(raw_e1), f, separators=(",", ":"))
            f.write("\n")
        manifest[os.path.relpath(path, ROOT)] = sha(path)
    cpath = os.path.join(cdir, "parity_prereg_v1.json")
    report = {
        "schema": "abep_rust_parity_report_v3_1",
        "contract": {"id": contract["id"], "path": os.path.relpath(cpath, ROOT), "sha256": sha(cpath)},
        "contract_sha256": sha(cpath),
        "verdict": verdict,
        "entry_points": eps,
        "invariants": res["invariants"],
        "conservation": res["conservation"],
        "domain_error": {"all_pass": de_ok, "cases": res["domain_error"]},
        "schema_parity": {"all_pass": schema_ok, "checks": res["schema"]},
        "python_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")),
        "rust_commit": git("rev-parse", "HEAD"),
        "reference_sha256": ref_ok,
        "pinned_inputs_verified": pinned_ok,
        "build_provenance": dict(build_provenance(), executable_sha256=rust.exe_sha256),
        "environment": {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
                        "pandas": pd.__version__,
                        "requirements_lock_sha256": sha(rel("requirements-lock.txt")),
                        "machine": machine()},
        "scoring_master_seed": contract["campaign_seeds"]["scoring_master_seed"],
        "performance": perf_rec,
        "captured_reference_outputs": {"sha256_manifest": manifest,
                                       "captured_at_python_commit": git("rev-parse", "HEAD")},
        "per_test_results": per_test_file(cdir, res),
        "timings": res.get("timings"),
        "campaign_history": [{"utc": started, "git_head": git("rev-parse", "HEAD"),
                              "git_dirty": bool(git("status", "--porcelain")), "mode": "score",
                              "scoring_master_seed": contract["campaign_seeds"]["scoring_master_seed"],
                              "verdict": verdict}],
        "what_this_is_not": contract["what_this_is_not"],
    }
    report["implementation_change_since_registration"] = IMPLEMENTATION_CHANGE
    report["owner_finding"] = OWNER_FINDING
    report["ledger_update_requested"] = ledger(cname, contract, verdict, report)
    with open(os.path.join(cdir, "parity_report_v1.json"), "w") as f:
        json.dump(enc(report), f, indent=1)
        f.write("\n")
    write_md(cdir, report)
    return report


IMPLEMENTATION_CHANGE = {
    "what": "IntakeSurface simplex selection",
    "registered_description": "PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1 rust_implementation.interpolant_reproduction."
                              "rust_evaluation: the first non-degenerate simplex in captured order whose barycentric "
                              "coordinates lie in [-eps, 1 + eps], Tinv from Gaussian elimination; it also stated that "
                              "values on shared faces agree up to rounding",
    "finding": "the development comparison (development seed 7, E4 face vector E4-F28; not a verdict) showed that the "
               "reference triangulation is non-conforming across some interior grid faces (Qhull 'Qt' triangulates a "
               "shared cospherical face differently on its two sides), so the reference value at such a face point "
               "depends on which containing simplex scipy's search reaches; the stated face continuity is false",
    "change_before_scoring": "the Rust surface replicates scipy's _find_simplex (lifted-paraboloid walk from simplex "
                             "0, directed search, brute-force fallback) and barycentric arithmetic with the "
                             "reference's captured search structures crates/abep-intake/data/"
                             "intake_surface_v1_delaunay_v1_search.json (sha256 e6f254b3f089123b2c8eadaac7adf66b6d64f"
                             "823540a4ed8cb4d86cba301b3fd, same capture script; the pinned triangulation capture "
                             "247601cf... is unchanged and still verified); the independent Gaussian-elimination "
                             "inverse is kept as a load-time cross-check of the captured transforms (1e-10)",
    "unchanged": "observables, tolerances, vector rules, n, seeds, decision rules and pinned inputs of both contracts",
}

OWNER_FINDING = {
    "id": "B2-OF-01",
    "classification": "PYTHON_REFERENCE_DEFECT candidate (own governance; not resolved by the migration, RM-R11 / "
                      "RM-R22)",
    "statement": "abep_sim.intake_tpmc.IntakeSurface (scipy LinearNDInterpolator over the Qhull triangulation of the "
                 "degenerate v1 tensor grid) is discontinuous across interior grid faces: points with L/d = 5 or 10, "
                 "alpha = 0.2 / 0.5 / 0.8 or theta = 2 deg get the value of whichever containing simplex scipy's walk "
                 "reaches. A Python-only survey (60 random points per interior face, N2 rows) found jumps between "
                 "containing simplices up to 1.7e-1 relative in CR_passive (theta = 2 deg), 6e-2 in K_back, 3.8e-2 in "
                 "eta_c, 3.7e-2 in mass_kg (alpha faces) and 1.3e-3 in C_D. The active default points checked "
                 "((10, 0.85, 0.5, 0), (5, 0.85, 0.8, 0), (10, 0.85, 0.95, 0), (3, 0.85, 0.5, 0), (5, 0.85, 0.8, 2)) "
                 "agree to rounding",
    "rust_behaviour": "reproduces the reference including this path dependence (scipy walk replication)",
    "owner_question": "keep the reference interpolant as is (parity), or replace it by a deliberate conforming "
                      "interpolant (e.g. multilinear or a fixed Kuhn triangulation) as a registered intake-ROM model "
                      "change (rule 1/2: new version, HISTORY, evidence that depends on it re-run)?",
}


def per_test_file(cdir: str, res: dict) -> dict:
    """Every per-test record, in a compact companion file (the report keeps counts and failures)."""
    path = os.path.join(cdir, "parity_report_v1_tests.json")
    tests = {k: v.get("tests", []) for k, v in res["entry_points"].items()}
    with open(path, "w") as f:
        json.dump(enc(tests), f, separators=(",", ":"))
        f.write("\n")
    failures = {k: [t for t in v if t["status"] not in ("PASS", "WITHIN", "AGREE_EXACT")] for k, v in tests.items()}
    return {"path": os.path.relpath(path, ROOT), "sha256": sha(path), "failures": failures}


def ledger(cname, contract, verdict, report) -> dict:
    comp = contract["component"]["inventory_id"]
    return {"component": comp, "requested_status": "ADMITTED" if verdict == "ADMITTED" else "PREREG_PARITY",
            "contract_id": contract["id"], "contract_sha256": report["contract_sha256"],
            "report": f"{CONTRACTS[cname]}/parity_report_v1.json", "verdict": verdict,
            "scope": contract["component"]["scope"],
            "note": "requested for docs/rust_migration/migration_state_v1.json (owned by lane A1); not edited here"}


def write_md(cdir: str, rep: dict) -> None:
    L = [f"# Parity report v1 — {rep['contract']['id']}: **{rep['verdict']}**", "",
         f"Contract `{rep['contract']['path']}` (sha256 `{rep['contract_sha256']}`). Python reference and Rust at "
         f"`{rep['python_commit']}` (dirty: {rep['git_dirty']}). Generated from `parity_report_v1.json` by "
         "`scripts/rust_migration/parity_intake.py`.", "",
         "| entry point | result | test counts | aggregate max abs(sum z)/sqrt(N) |", "|---|---|---|---|"]
    for k, e in rep["entry_points"].items():
        agg = max((a["abs_sum_z_over_sqrtN"] for a in e["aggregate"].values()), default=None)
        L.append(f"| {k} | {e['result']} | {e['counts']} | {'-' if agg is None else round(agg, 3)} |")
    L += ["", "| check | held |", "|---|---|"]
    for k, v in rep["invariants"].items():
        L.append(f"| invariant {k} | {inv_held(v)} |")
    for k, v in rep["conservation"].items():
        L.append(f"| conservation {k} | {inv_held(v)} |")
    L.append(f"| domain / error parity ({len(rep['domain_error']['cases'])} cases) | {rep['domain_error']['all_pass']} |")
    L.append(f"| schema parity | {rep['schema_parity']['all_pass']} |")
    L.append(f"| reference files and pinned inputs unchanged | "
             f"{all(rep['reference_sha256'].values()) and all(rep['pinned_inputs_verified'].values())} |")
    p = rep.get("performance")
    if p:
        L += ["", f"Performance (reported, never a criterion): {p['workload']} — Python median "
              f"{p['python']['median_wall_s']:.3f} s wall / {p['python']['median_cpu_s']:.3f} s CPU; Rust median "
              f"{p['rust']['median_wall_s']:.4f} s wall / {p['rust']['median_cpu_s']:.4f} s CPU; speed-up "
              f"{p['speedup_wall']:.1f}x wall. {p['threads']}."]
    L += ["", f"Implementation change since registration: {rep['implementation_change_since_registration']['finding']}"
          f"; {rep['implementation_change_since_registration']['change_before_scoring']}. Unchanged: "
          f"{rep['implementation_change_since_registration']['unchanged']}.",
          "", f"Owner finding {rep['owner_finding']['id']} ({rep['owner_finding']['classification']}): "
          f"{rep['owner_finding']['statement']}. Question: {rep['owner_finding']['owner_question']}"]
    L += ["", "ADMITTED is software parity with the Python reference inside the registered domain, not physics "
          "validation and not a gate PASS.", ""]
    with open(os.path.join(cdir, "parity_report_v1.md"), "w") as f:
        f.write("\n".join(L))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", choices=sorted(CONTRACTS), required=True)
    ap.add_argument("--mode", choices=("dev", "score"), required=True)
    ap.add_argument("--scratch", required=True)
    a = ap.parse_args()
    cdir = rel(CONTRACTS[a.contract])
    contract = json.load(open(os.path.join(cdir, "parity_prereg_v1.json")))
    started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ref_ok = {f["path"]: sha(rel(f["path"])) == f["sha256_at_registration"]
              for f in contract["reference_implementation"]["files"]}
    pinned_ok = {p: sha(rel(p)) == h for p, h in contract["pinned_inputs_sha256"].items()}
    if a.mode == "score" and os.path.exists(os.path.join(cdir, "parity_report_v1.json")):
        raise SystemExit("a v1 scoring report exists: the scoring seed is spent; a new execution needs contract v2")
    if not (all(ref_ok.values()) and all(pinned_ok.values())):
        print("REFUSED_REFERENCE_CHANGED", ref_ok, pinned_ok)
        if a.mode == "dev":
            return 1
    os.makedirs(a.scratch, exist_ok=True)
    rust = Rust(a.scratch)
    frozen_before = {p: sha(rel(p)) for p in ("abep_sim/data/intake_surface_v1.csv",
                                             "abep_sim/data/intake_surface_v1.json")}
    t0 = time.perf_counter()
    try:
        res = (run_intake_tpmc if a.contract == "intake_tpmc" else run_intake)(contract, a.mode, rust, a.scratch)
    except Exception:  # noqa: BLE001 - a harness failure during scoring is recorded, never discarded
        if a.mode == "dev":
            raise
        import traceback
        rep = {"schema": "abep_rust_parity_report_v3_1", "contract": {"id": contract["id"]},
               "contract_sha256": sha(os.path.join(cdir, "parity_prereg_v1.json")), "verdict": "NOT_ADMITTED",
               "harness_error": traceback.format_exc(), "python_commit": git("rev-parse", "HEAD"),
               "campaign_history": [{"utc": started, "git_head": git("rev-parse", "HEAD"), "mode": "score",
                                     "verdict": "NOT_ADMITTED", "note": "harness error; no result discarded"}]}
        with open(os.path.join(cdir, "parity_report_v1.json"), "w") as f:
            json.dump(rep, f, indent=1)
            f.write("\n")
        print("NOT_ADMITTED (harness error)")
        return 1
    if a.mode == "dev":
        for k, ep in res["entry_points"].items():
            print("DEV (not a verdict)", k, counts(ep), {o: round(x["abs_sum_z_over_sqrtN"], 2)
                                                         for o, x in ep.get("aggregate", {}).items()})
            bad = [t for t in ep["tests"] if t["status"] not in ("PASS", "WITHIN", "AGREE_EXACT")][:5]
            for t in bad:
                print("   ", t)
        print("DEV invariants", {k: inv_held(v) for k, v in res["invariants"].items()},
              "conservation", {k: inv_held(v) for k, v in res["conservation"].items()})
        print("wall", round(time.perf_counter() - t0, 1), "s")
        return 0
    try:
        perf_rec = perf(rust) if a.contract == "intake_tpmc" else None
        rep = write_report(a.contract, cdir, contract, res, rust, started, ref_ok, pinned_ok, frozen_before, perf_rec)
    except Exception:  # noqa: BLE001 - keep the computed results whatever happens while reporting
        import traceback
        with open(os.path.join(cdir, "parity_report_v1_raw.json"), "w") as f:
            json.dump(enc({"harness_error": traceback.format_exc(), "results": res}), f, separators=(",", ":"))
        print("REPORTING FAILED; raw results kept in parity_report_v1_raw.json")
        return 1
    print(rep["verdict"], {k: v["result"] for k, v in rep["entry_points"].items()},
          "wall", round(time.perf_counter() - t0, 1), "s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
