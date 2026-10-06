#!/usr/bin/env python3
"""Parity harness of PARITY-C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION-V1 (SC-WP-09, lane mission; A9.31 sec. 12).

Implements the vector generators, reference calls, tolerance classes and decision rules registered in
docs/rust_migration/contracts/C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION/parity_prereg_v1.json. The Python reference is
called read-only; the Rust side is the `abep-mission-env-parity` binary of crates/abep-mission.

    python3 scripts/rust_migration/parity_mission_env_propagation_v1.py dev     # development seed; never a verdict
    python3 scripts/rust_migration/parity_mission_env_propagation_v1.py score   # scoring seed, ONCE: report + references

A scoring run refuses to start when parity_report_v1.json exists, when a reference file differs from its registered
sha256 (REFUSED_REFERENCE_CHANGED) or when a Rust provenance source has uncommitted changes.
"""
from __future__ import annotations

import os
import sys

if os.environ.get("OMP_NUM_THREADS") != "1" or os.environ.get("OPENBLAS_NUM_THREADS") != "1":
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.execv(sys.executable, [sys.executable] + sys.argv)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import datetime  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

CDIR = os.path.join(ROOT, "docs", "rust_migration", "contracts", "C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION")
CONTRACT = os.path.join(CDIR, "parity_prereg_v1.json")
REPORT = os.path.join(CDIR, "parity_report_v1.json")
BIN = os.path.join(ROOT, "target", "release", "abep-mission-env-parity")
ROW_KEYS = ["t_h", "alt_km", "raan_deg", "beta_deg", "eclipse_frac", "D_mN", "T_mN", "P_bus_W", "P_need_W", "P_avail_W",
            "power_margin_W", "rho"]
SUMMARY_KEYS = ["reentered", "min_alt_km", "mean_eclipse", "min_power_margin_W", "hours_power_short",
                "raan_drift_deg_per_day"]
TOL = {
    "beta_angle": {"k_ulp": 4, "a_abs": 1e-13},
    "eclipse_fraction": {"k_ulp": 4, "a_abs": 1e-15},
    "worst_eclipse_fraction": {"k_ulp": 4, "a_abs": 1e-15},
    "array_area_for": {"k_ulp": 4, "r_rel": 1e-13},
    "row": {"k_ulp": 4, "r_rel": 1e-12, "a_abs": 1e-12},
    "raan": {"k_ulp": 4, "r_rel": 1e-12, "a_abs": 1e-9},
    "summary": {"k_ulp": 4, "r_rel": 1e-12, "a_abs": 1e-12},
    "raan_drift": {"k_ulp": 4, "r_rel": 1e-9, "a_abs": 1e-9},
}
PY_CLASSES_OOD = {"ValueError", "ZeroDivisionError", "OverflowError", "AttributeError", "IndexError"}


def sha_file(p: str) -> str:
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def jnum(x):
    if isinstance(x, float):
        if math.isnan(x):
            return "NaN"
        if math.isinf(x):
            return "+inf" if x > 0 else "-inf"
    return x


def deep_j(x):
    """JSON transport of nested values (non-finite floats as the registered strings)."""
    if isinstance(x, dict):
        return {k: deep_j(v) for k, v in x.items()}
    if isinstance(x, list):
        return [deep_j(v) for v in x]
    return jnum(x)


def unj(x):
    if isinstance(x, str):
        return {"NaN": float("nan"), "+inf": float("inf"), "-inf": float("-inf")}[x]
    return x


# ------------------------------------------------------------------------------------------------ vectors

def spacecraft_args(**kw) -> dict:
    return {k: jnum(float(v)) if not isinstance(v, bool) else v for k, v in kw.items()}


def vectors(master_seed: int) -> list[dict]:
    """Every registered vector: {id, entry, args, kind, divergent?}."""
    V = []

    def add(vid, entry, args, kind, **extra):
        V.append({"id": vid, "entry": entry, "args": {k: jnum(v) for k, v in args.items()}, "kind": kind, **extra})

    add("G-SOLAR", "SOLAR_CONST", {}, "golden")
    for i, (inc, raan, sl, dec) in enumerate([(96.33, 0.0, 0.0, 0.0), (96.33, 90.0, 0.0, 0.0),
                                              (96.33, 270.0, 80.0, 23.44 * math.sin(math.radians(80.0))),
                                              (0.0, 0.0, 0.0, 0.0), (90.0, 45.0, 30.0, -23.44),
                                              (180.0, 10.0, 350.0, 10.0)]):
        add(f"G-B-{i}", "beta_angle", {"inc": inc, "raan": raan, "sun_lon": sl, "dec": dec}, "golden")
    eg = [(200.0, b) for b in (0.0, 30.0, 60.0, 70.0, 75.0, 80.0, 89.9)] + [(180.0, 0.0), (230.0, 0.0), (1000.0, 0.0),
                                                                           (1000.0, 50.0)]
    for i, (alt, b) in enumerate(eg):
        add(f"G-E-{i}", "eclipse_fraction", {"alt": alt, "beta": b}, "golden")
    for i, alt in enumerate((180.0, 200.0, 230.0)):
        add(f"G-W-{i}", "worst_eclipse_fraction", {"alt": alt}, "golden")
    k = 0
    for p in (700.0, 1000.0, 1500.0, 5000.0):
        for cap in (None, 1500.0):
            add(f"G-A-{k}", "array_area_for", {"P": p, "alt": 200.0, "years": 3.0, "rho_ratio": 1.39, "cap": cap}, "golden")
            k += 1
    drag1 = {"family": "DF-EXP", "rho0": 2.5e-10, "h0": 200.0, "H": 40.0, "CdA": 0.3}
    prop1 = {"alt0": 200.0, "hours": 240.0, "dt_h": 1.0, "drag": drag1, "raan0": None, "epoch_day": 80.0}
    add("G-PROP-1", "propagate", {**prop1, "thrust": {"family": "TF-CONST", "T0": 0.012, "P0": 900.0}}, "golden")
    add("G-PROP-2", "propagate", {**prop1, "thrust": {"family": "TF-POWER", "k": 2e-5, "Pmax": 1400.0}}, "golden")
    add("G-PROP-3", "propagate", {**prop1, "thrust": {"family": "TF-TRACK", "f": 1.0, "CdA": 0.3, "P0": 900.0}},
        "golden")
    tc = {"family": "TF-CONST", "T0": 0.012, "P0": 900.0}
    add("E-P-01", "eclipse_fraction", {"alt": 200.0, "beta": 90.0}, "edge")
    add("E-P-02", "eclipse_fraction", {"alt": 200.0, "beta": 120.0}, "edge")
    add("E-P-03", "eclipse_fraction", {"alt": -100.0, "beta": 0.0}, "edge")
    add("E-P-04", "propagate", {"alt0": 200.0, "hours": 5000.0, "dt_h": 2.0, "raan0": None, "epoch_day": 80.0,
                                "drag": {"family": "DF-EXP", "rho0": 5e-9, "h0": 200.0, "H": 30.0, "CdA": 1.0},
                                "thrust": {"family": "TF-CONST", "T0": 0.0, "P0": 0.0}}, "edge")
    add("E-P-05", "propagate", {**prop1, "hours": 2.0, "dt_h": 1.0, "thrust": tc}, "edge")
    add("E-P-06", "propagate", {**prop1, "raan0": 123.0, "epoch_day": 355.5, "thrust": tc}, "edge")
    add("E-P-07", "array_area_for", {"P": 1000.0, "alt": 200.0, "years": 0.0, "rho_ratio": 0.0, "cap": 1500.0}, "edge")

    def rng(e):
        return np.random.default_rng(np.random.SeedSequence([master_seed, e]))

    r = rng(0)
    a = [r.uniform(0, 180, 400), r.uniform(-720, 720, 400), r.uniform(-720, 720, 400), r.uniform(-23.44, 23.44, 400)]
    for i in range(400):
        add(f"R-B-{i}", "beta_angle", {"inc": float(a[0][i]), "raan": float(a[1][i]), "sun_lon": float(a[2][i]),
                                       "dec": float(a[3][i])}, "random")
    r = rng(1)
    a = [r.uniform(-100, 3000, 400), r.uniform(-120, 120, 400)]
    for i in range(400):
        add(f"R-E-{i}", "eclipse_fraction", {"alt": float(a[0][i]), "beta": float(a[1][i])}, "random")
    r = rng(2)
    a = [r.uniform(0, 180, 100), r.uniform(0, 24, 100), r.uniform(150, 1000, 100)]
    for i in range(100):
        add(f"R-W-{i}", "worst_eclipse_fraction", {"alt": float(a[2][i]),
                                                   "sc": spacecraft_args(inc_deg=a[0][i], ltan_h=a[1][i])}, "random")
    r = rng(3)
    n = 150
    a = {k: r.uniform(lo, hi, n) for k, lo, hi in [("P", 0, 5000), ("alt", 150, 400), ("years", 0, 10),
                                                  ("rho_ratio", 0.5, 2), ("cap", 100, 3000), ("cap_none", 0, 1),
                                                  ("array_eff", 0.1, 0.4), ("array_deg_per_yr", 0, 0.05),
                                                  ("eps_eff", 0.5, 1), ("bus_housekeeping_W", 0, 300),
                                                  ("inc_deg", 0, 180), ("ltan_h", 0, 24)]}
    for i in range(n):
        sc = spacecraft_args(**{k: a[k][i] for k in ("array_eff", "array_deg_per_yr", "eps_eff", "bus_housekeeping_W",
                                                      "inc_deg", "ltan_h")})
        add(f"R-A-{i}", "array_area_for", {"P": float(a["P"][i]), "alt": float(a["alt"][i]),
                                           "years": float(a["years"][i]), "rho_ratio": float(a["rho_ratio"][i]),
                                           "cap": None if a["cap_none"][i] < 0.2 else float(a["cap"][i]), "sc": sc},
            "random")
    r = rng(4)
    for i in range(120):
        fam = ["TF-CONST", "TF-POWER", "TF-TRACK"][i % 3]
        u = lambda lo, hi: float(r.uniform(lo, hi))  # noqa: E731
        alt0 = u(180, 230)
        dt_h = u(0.25, 12)
        steps = int(r.integers(1, 400))
        hours = dt_h * steps + u(0, 1) * dt_h
        mass, inc, ltan, area = u(50, 300), u(0, 180), u(0, 24), u(0.5, 6)
        flag = u(0, 1)
        raan_v = u(0, 360)
        raan0 = raan_v if flag < 0.5 else None
        epoch = u(0, 365)
        rho0 = 10 ** u(-11, -9)
        h0, hh, cda = u(180, 230), u(20, 60), u(0.05, 1.0)
        t0, p0, kk, pmax, f = u(0, 0.05), u(0, 2000), u(0, 5e-5), u(0, 2000), u(0, 2)
        thrust = {"TF-CONST": {"family": fam, "T0": t0, "P0": p0}, "TF-POWER": {"family": fam, "k": kk, "Pmax": pmax},
                  "TF-TRACK": {"family": fam, "f": f, "CdA": cda, "P0": p0}}[fam]
        add(f"R-P-{i}", "propagate", {"alt0": alt0, "hours": hours, "dt_h": dt_h, "raan0": raan0, "epoch_day": epoch,
                                      "sc": spacecraft_args(mass_kg=mass, inc_deg=inc, ltan_h=ltan, array_area_m2=area),
                                      "drag": {"family": "DF-EXP", "rho0": rho0, "h0": h0, "H": hh, "CdA": cda},
                                      "thrust": thrust}, "random")
    nan = float("nan")
    add("DE-P-01", "beta_angle", {"inc": float("inf"), "raan": 0.0, "sun_lon": 0.0, "dec": 0.0}, "domain")
    add("DE-P-02", "eclipse_fraction", {"alt": -6371.0, "beta": 0.0}, "domain")
    add("DE-P-03", "eclipse_fraction", {"alt": 1e160, "beta": 0.0}, "domain")
    add("DE-P-04", "eclipse_fraction", {"alt": 200.0, "beta": float("inf")}, "domain")
    add("DE-P-05", "array_area_for", {"P": 1000.0, "alt": 200.0, "years": 10.0, "rho_ratio": 1.39, "cap": 1500.0,
                                      "sc": spacecraft_args(array_deg_per_yr=0.1)}, "domain")
    add("DE-P-06", "propagate", {**prop1, "hours": 0.5, "dt_h": 1.0, "thrust": tc}, "domain")
    add("DE-P-07", "propagate", {**prop1, "dt_h": 0.0, "thrust": tc}, "domain")
    add("DE-P-08", "propagate", {**prop1, "alt0": -7000.0, "thrust": tc}, "domain")
    add("DE-P-09", "propagate", {**prop1, "hours": nan, "thrust": tc}, "domain")
    add("DE-P-10", "eclipse_fraction", {"alt": 200.0, "beta": nan}, "domain", divergent=True)
    add("DE-P-11", "beta_angle", {"inc": nan, "raan": 0.0, "sun_lon": 0.0, "dec": 0.0}, "domain", divergent=True)
    add("DE-P-12", "array_area_for", {"P": nan, "alt": 200.0, "years": 3.0, "rho_ratio": 1.39, "cap": 1500.0},
        "domain", divergent=True)
    add("DE-P-13", "propagate", {**prop1, "thrust": {"family": "TF-CONST", "T0": nan, "P0": 900.0}}, "domain",
        divergent=True)
    return V


# ------------------------------------------------------------------------------------------------ Python reference

def py_sc(args):
    from abep_sim.mission_env import Spacecraft
    return Spacecraft(**{k: (unj(v) if not isinstance(v, bool) else v) for k, v in (args.get("sc") or {}).items()})


def py_closures(args):
    from abep_sim.constants import MU_EARTH, R_EARTH
    d, t = args["drag"], args["thrust"]
    rho0, h0, hh, cda = (unj(d[k]) for k in ("rho0", "h0", "H", "CdA"))

    def drag_fn(alt, t_h):
        a = R_EARTH + alt * 1e3
        rho = rho0 * math.exp(-(alt - h0) / hh)
        V = math.sqrt(MU_EARTH / a)
        D = 0.5 * rho * V ** 2 * cda
        return D, {"rho": rho}

    fam = t["family"]

    def thrust_fn(alt, t_h, atm):
        if fam == "TF-CONST":
            return unj(t["T0"]), unj(t["P0"])
        if fam == "TF-POWER":
            P = min(unj(t["Pmax"]), atm["_P_avail"])
            return unj(t["k"]) * P, P
        a = R_EARTH + alt * 1e3
        V = math.sqrt(MU_EARTH / a)
        D = 0.5 * atm["rho"] * V ** 2 * unj(t["CdA"])
        return unj(t["f"]) * D, unj(t["P0"])
    return drag_fn, thrust_fn


def py_call(v):
    from abep_sim import mission_env as me
    a = {k: (unj(x) if not isinstance(x, (dict, type(None))) else x) for k, x in v["args"].items()}
    try:
        e = v["entry"]
        if e == "SOLAR_CONST":
            val = me.SOLAR_CONST
        elif e == "beta_angle":
            val = me.beta_angle(a["inc"], a["raan"], a["sun_lon"], a["dec"])
        elif e == "eclipse_fraction":
            val = me.eclipse_fraction(a["alt"], a["beta"])
        elif e == "worst_eclipse_fraction":
            val = me.worst_eclipse_fraction(py_sc(v["args"]), a["alt"])
        elif e == "array_area_for":
            val = me.array_area_for(a["P"], py_sc(v["args"]), a["alt"], a["years"], a["rho_ratio"], P_cap_W=a["cap"])
        elif e == "propagate":
            dfn, tfn = py_closures(v["args"])
            p = me.propagate(py_sc(v["args"]), a["alt0"], a["hours"], a["dt_h"], dfn, tfn,
                             raan0_deg=a["raan0"], epoch_day=a["epoch_day"])
            df = p["df"]
            val = {"columns": list(df.columns), "rows": [{k: float(r[k]) for k in df.columns} for _, r in df.iterrows()],
                   **{k: (bool(p[k]) if k == "reentered" else float(p[k])) for k in SUMMARY_KEYS},
                   "summary_keys": [k for k in p if k != "df"]}
        else:
            raise KeyError(e)
        return {"outcome": "RETURNED", "value": val}
    except Exception as ex:  # noqa: BLE001 - every exception class is an observable
        return {"outcome": "RAISED", "class": type(ex).__name__, "message": str(ex)}


# ------------------------------------------------------------------------------------------------ Rust

def rust_run(V, tag: str) -> tuple[list, bytes]:
    calls = [{"entry": v["entry"], "args": deep_j(v["args"])} for v in V]
    req = json.dumps({"repo_root": ROOT, "calls": calls}).encode()
    r = subprocess.run([BIN], input=req, capture_output=True, check=True)
    return json.loads(r.stdout)["results"], r.stdout


# ------------------------------------------------------------------------------------------------ comparison

def ulp(x: float) -> float:
    return math.ulp(x) if x != 0 else math.ulp(0.0)


def close(py: float, rs: float, tol: dict, circle: bool = False) -> bool:
    if isinstance(py, bool) or isinstance(rs, bool):
        return py == rs
    py, rs = unj(py), unj(rs)
    if math.isnan(py) or math.isnan(rs):
        return math.isnan(py) and math.isnan(rs)
    if math.isinf(py) or math.isinf(rs):
        return py == rs
    d = abs(rs - py)
    if circle:
        d = min(d, 360.0 - d)
    if d <= tol.get("k_ulp", 0) * ulp(py):
        return True
    if "r_rel" in tol and d <= tol["r_rel"] * abs(py):
        return True
    return "a_abs" in tol and d <= tol["a_abs"]


def compare(v, py, rs, stats) -> list[str]:
    e = v["entry"]
    if py["outcome"] == "RAISED":
        if py["class"] not in PY_CLASSES_OOD:
            return [f"python raised unmapped {py['class']}: {py['message']}"]
    if v.get("divergent"):
        ok = py["outcome"] == "RETURNED" and rs["outcome"] == "RAISED" and rs.get("class") == "DIV-P-01" \
            and rs.get("status") == "OUT_OF_DOMAIN"
        return [] if ok else [f"divergent vector: py {py['outcome']} rust {rs}"]
    if py["outcome"] != rs["outcome"]:
        return [f"outcome py {py['outcome']} ({py.get('class')}: {py.get('message')}) != rust {rs.get('outcome')} "
                f"({rs.get('message')})"]
    if py["outcome"] == "RAISED":
        out = []
        if rs.get("status") != "OUT_OF_DOMAIN":
            out.append(f"status {rs.get('status')}")
        if rs.get("class") != py["class"]:
            out.append(f"class py {py['class']} != rust {rs.get('class')}")
        return out
    pv, rv = py["value"], rs["value"]
    if e == "propagate":
        out = []
        if rv.get("columns") != ROW_KEYS or rv.get("summary_keys") != SUMMARY_KEYS:
            out.append(f"rust columns / summary keys {rv.get('columns')} {rv.get('summary_keys')}")
        rv = {**rv, "rows": [dict(zip(rv["columns"], row)) for row in rv["rows"]]}
        if pv["columns"] != ROW_KEYS:
            out.append(f"python columns {pv['columns']}")
        if len(pv["rows"]) != len(rv["rows"]):
            return out + [f"n_rows py {len(pv['rows'])} != rust {len(rv['rows'])}"]
        for i, (a, b) in enumerate(zip(pv["rows"], rv["rows"])):
            for k in ROW_KEYS:
                if k == "t_h":
                    okk = a[k] == unj(b[k])
                else:
                    okk = close(a[k], b[k], TOL["raan" if k == "raan_deg" else "row"], circle=(k == "raan_deg"))
                stats.append((e, f"rows.{k}", a[k], unj(b[k]), okk))
                if not okk:
                    out.append(f"row {i} {k}: py {a[k]!r} rust {b[k]!r}")
        for k in SUMMARY_KEYS:
            if k in ("reentered", "hours_power_short"):
                okk = pv[k] == unj(rv[k])
            else:
                okk = close(pv[k], rv[k], TOL["raan_drift" if k == "raan_drift_deg_per_day" else "summary"])
            stats.append((e, k, pv[k], unj(rv[k]), okk))
            if not okk:
                out.append(f"{k}: py {pv[k]!r} rust {rv[k]!r}")
        return out
    if e == "SOLAR_CONST":
        okk = pv == unj(rv) and struct_bits(pv) == struct_bits(unj(rv))
    else:
        okk = close(pv, rv, TOL[e])
    stats.append((e, "value", pv, unj(rv), okk))
    return [] if okk else [f"value py {pv!r} rust {rv!r}"]


def struct_bits(x: float) -> int:
    import struct
    return struct.unpack("<Q", struct.pack("<d", x))[0]


# ------------------------------------------------------------------------------------------------ invariants

def inv_rows(val, sc_hk: float) -> list[str]:
    out = []
    rows = val["rows"]
    prev = None
    for i, r in enumerate(rows):
        g = lambda k: unj(r[k])  # noqa: E731
        if prev is not None and not g("t_h") > prev:
            out.append(f"t_h not increasing at {i}")
        prev = g("t_h")
        if not (0.0 <= g("eclipse_frac") <= 1.0):
            out.append(f"eclipse_frac out of [0, 1] at {i}")
        if g("P_need_W") != g("P_bus_W") + sc_hk:
            out.append(f"P_need != P_bus + hk at {i}")
        if g("power_margin_W") != g("P_avail_W") - g("P_need_W"):
            out.append(f"margin identity at {i}")
        if not (0.0 <= g("raan_deg") < 360.0):
            out.append(f"raan out of [0, 360) at {i}")
    return out


def cons_p01(args, val) -> list[str]:
    """Each altitude increment equals dadt dt_h 3600 / 1e3 recomputed from the previous altitude and T_mN / D_mN."""
    from abep_sim.constants import MU_EARTH, R_EARTH
    mass = unj((args.get("sc") or {}).get("mass_kg", 150.0))
    dt = unj(args["dt_h"])
    alt = unj(args["alt0"])
    out = []
    for i, r in enumerate(val["rows"]):
        a = R_EARTH + alt * 1e3
        dadt = 2.0 * a ** 1.5 * (unj(r["T_mN"]) / 1e3 - unj(r["D_mN"]) / 1e3) / (mass * math.sqrt(MU_EARTH))
        inc = dadt * dt * 3600 / 1e3
        got = unj(r["alt_km"]) - alt
        if abs(got - inc) > 1e-9 * abs(inc) + 1e-12:
            out.append(f"row {i}: increment {got!r} vs recomputed {inc!r}")
            break
        alt = unj(r["alt_km"])
    return out


# ------------------------------------------------------------------------------------------------ main

def main(mode: str) -> int:
    contract = json.load(open(CONTRACT))
    contract_sha = sha_file(CONTRACT)
    seed = contract["campaign_seeds"]["scoring_master_seed" if mode == "score" else "development_master_seed"]
    refs = {f["path"]: f["sha256_at_registration"] for f in contract["reference_implementation"]["files"]}
    ref_now = {p: sha_file(os.path.join(ROOT, p)) for p in refs}
    if mode == "score":
        if os.path.exists(REPORT):
            print("REFUSED: parity_report_v1.json exists (scoring runs once)")
            return 2
        if ref_now != refs:
            print("REFUSED_REFERENCE_CHANGED", {p: (refs[p], ref_now[p]) for p in refs if refs[p] != ref_now[p]})
            return 2
        srcs = contract["rust_implementation"]["provenance_sources"]
        dirty = git("status", "--porcelain", "--", *[s.replace("/**", "") for s in srcs])
        if dirty:
            print("REFUSED: uncommitted Rust provenance sources:\n" + dirty)
            return 2
    subprocess.run(["/root/.cargo/bin/cargo", "build", "--release", "--locked", "-p", "abep-mission", "--bin",
                    "abep-mission-env-parity"], cwd=ROOT, check=True, capture_output=True,
                   env=dict(os.environ, PATH="/root/.cargo/bin:" + os.environ.get("PATH", ""),
                            CARGO_INCREMENTAL="0"))
    V = vectors(seed)
    t0 = time.perf_counter()
    PY = [py_call(v) for v in V]
    t_py = time.perf_counter() - t0
    PY2 = [py_call(v) for v in V]
    RS, raw1 = rust_run(V, "1")
    _, raw2 = rust_run(V, "2")
    stats, per_test = [], []
    for v, p, r in zip(V, PY, RS):
        fails = compare(v, p, r, stats)
        per_test.append({"id": v["id"], "entry": v["entry"], "kind": v["kind"], "python_outcome": p["outcome"],
                         "python_class": p.get("class"), "rust_outcome": r["outcome"], "rust_class": r.get("class"),
                         "failures": fails})
    # invariants
    inv = {"INV-P-01": {"rust_bytes_identical": raw1 == raw2,
                        "python_repeat_identical": json.dumps(PY, default=str) == json.dumps(PY2, default=str)}}
    inv_fail = [] if all(inv["INV-P-01"].values()) else ["INV-P-01"]
    for r in RS:
        if r["outcome"] == "RETURNED" and isinstance(r["value"], dict) and "columns" in r["value"]:
            r["value"]["rows"] = [dict(zip(r["value"]["columns"], row)) for row in r["value"]["rows"]]
    p02 = []
    for v, p, r in zip(V, PY, RS):
        if v["entry"] == "propagate" and p["outcome"] == "RETURNED" and r["outcome"] == "RETURNED":
            hk = unj((v["args"].get("sc") or {}).get("bus_housekeeping_W", 120.0))
            for side, val in (("python", p["value"]), ("rust", r["value"])):
                p02 += [f"{v['id']} {side}: {m}" for m in inv_rows(val, hk)]
    inv["INV-P-02"] = {"violations": p02}
    if p02:
        inv_fail.append("INV-P-02")
    # INV-P-03: the worst eclipse is the running maximum of its own scan (both implementations).
    from abep_sim import mission_env as me
    p03, scan_calls, scan_owner = [], [], []
    for v, p, r in zip(V, PY, RS):
        if v["entry"] != "worst_eclipse_fraction" or p["outcome"] != "RETURNED":
            continue
        sc = py_sc(v["args"])
        alt = unj(v["args"]["alt"])
        for day in range(0, 366, 2):
            sl = (day / 365.25 * 360.0) % 360
            dec = 23.44 * math.sin(math.radians(sl))
            raan = (sl + (sc.ltan_h - 12.0) * 15.0) % 360
            b = me.beta_angle(sc.inc_deg, raan, sl, dec)
            if me.eclipse_fraction(alt, b) > p["value"]:
                p03.append(f"{v['id']} python day {day}")
            scan_calls.append({"entry": "eclipse_fraction", "args": {"alt": alt, "beta": b}})
            scan_owner.append((v["id"], unj(r["value"]) if r["outcome"] == "RETURNED" else None))
    if scan_calls:
        req = json.dumps({"repo_root": ROOT, "calls": deep_j(scan_calls)}).encode()
        res = json.loads(subprocess.run([BIN], input=req, capture_output=True, check=True).stdout)["results"]
        for (vid, worst), x in zip(scan_owner, res):
            if worst is None or x["outcome"] != "RETURNED" or unj(x["value"]) > worst:
                p03.append(f"{vid} rust")
    inv["INV-P-03"] = {"violations": p03[:20], "n": len(p03)}
    if p03:
        inv_fail.append("INV-P-03")
    # conservation
    c01, c02 = [], []
    for v, p, r in zip(V, PY, RS):
        if v["entry"] == "propagate" and p["outcome"] == "RETURNED" and r["outcome"] == "RETURNED":
            for side, val in (("python", p["value"]), ("rust", r["value"])):
                c01 += [f"{v['id']} {side}: {m}" for m in cons_p01(v["args"], val)]
            if v["id"] == "G-PROP-3":
                for side, val in (("python", p["value"]), ("rust", r["value"])):
                    if any(unj(x["alt_km"]) != 200.0 for x in val["rows"]):
                        c02.append(side)
    conservation = {"CONS-P-01": {"violations": c01}, "CONS-P-02": {"violations": c02}}
    # domain / error
    de = [t for t in per_test if t["id"].startswith("DE-")]
    domain_fail = [t["id"] for t in de if t["failures"]]
    # schema
    schema_fail = []
    for v, p, r in zip(V, PY, RS):
        if v["entry"] == "propagate" and p["outcome"] == "RETURNED":
            if p["value"]["summary_keys"] != SUMMARY_KEYS:
                schema_fail.append(f"{v['id']} python summary keys {p['value']['summary_keys']}")
            if r["outcome"] == "RETURNED" and (r["value"]["summary_keys"] != SUMMARY_KEYS
                                               or r["value"]["columns"] != ROW_KEYS):
                schema_fail.append(f"{v['id']} rust summary keys / columns")
    per_fail = [t for t in per_test if t["failures"]]
    # observables summary
    obs = {}
    for e, name, a, b, okk in stats:
        o = obs.setdefault(f"{e}|{name}", {"entry": e, "observable": name, "n": 0, "fail": 0, "bit_identical": 0,
                                           "max_abs_diff": 0.0, "max_rel_diff": 0.0, "max_ulp": 0.0})
        o["n"] += 1
        o["fail"] += 0 if okk else 1
        if isinstance(a, bool) or isinstance(b, bool):
            o["bit_identical"] += int(a == b)
            continue
        if (math.isnan(a) and math.isnan(b)) or a == b:
            o["bit_identical"] += 1 if (a == b and struct_bits(a) == struct_bits(b)) or (math.isnan(a) and math.isnan(b)) else 0
            continue
        d = abs(a - b)
        o["max_abs_diff"] = max(o["max_abs_diff"], d)
        if a != 0:
            o["max_rel_diff"] = max(o["max_rel_diff"], d / abs(a))
        o["max_ulp"] = max(o["max_ulp"], d / ulp(a))
    checks = {"per_test": not per_fail, "invariants": not inv_fail, "conservation": not (c01 or c02),
              "domain_error": not domain_fail, "schema": not schema_fail,
              "references_unchanged": ref_now == refs}
    verdict_ok = all(checks.values())
    summary = {"n_vectors": len(V), "n_failures": len(per_fail), "checks": checks,
               "first_failures": [{"id": t["id"], "failures": t["failures"][:3]} for t in per_fail[:15]],
               "observables": list(obs.values())}
    if mode == "dev":
        print(json.dumps(summary, indent=1)[:12000])
        print("DEVELOPMENT RUN (seed %d): not a verdict" % seed)
        return 0
    # performance (recorded, not gating): the three golden propagate runs
    gold = [v for v in V if v["id"].startswith("G-PROP")]
    t_py_g = sorted(timeit(lambda: [py_call(v) for v in gold]) for _ in range(3))[1]
    t_rs_g = sorted(timeit(lambda: rust_run(gold, "perf")) for _ in range(3))[1]
    import numpy
    import pandas
    rust_commit = git("rev-parse", "HEAD")
    srcs = {}
    for s in contract["rust_implementation"]["provenance_sources"]:
        if s.endswith("/**"):
            base = os.path.join(ROOT, s[:-3])
            for dp, _, fs in os.walk(base):
                for f in sorted(fs):
                    p = os.path.join(dp, f)
                    srcs[os.path.relpath(p, ROOT)] = sha_file(p)
        else:
            srcs[s] = sha_file(os.path.join(ROOT, s))
    rustc = subprocess.run(["/root/.cargo/bin/rustc", "--version"], capture_output=True, text=True).stdout.strip()
    cpu = ""
    try:
        cpu = [x for x in open("/proc/cpuinfo").read().splitlines() if x.startswith("model name")][0].split(":", 1)[1].strip()
    except Exception:  # noqa: BLE001
        pass
    verdict = "ADMITTED" if verdict_ok else "NOT_ADMITTED"
    report = {
        "schema": "abep_rust_parity_report_v1",
        "contract_id": contract["id"],
        "contract_path": os.path.relpath(CONTRACT, ROOT),
        "contract_sha256": contract_sha,
        "contract_registered_in": git("log", "--format=%H", "--diff-filter=A", "--", os.path.relpath(CONTRACT, ROOT)),
        "date": datetime.date.today().isoformat(),
        "verdict": verdict,
        "parity": "PARITY_PASS" if verdict_ok else "PARITY_FAIL",
        "python_commit": git("rev-parse", "HEAD"),
        "python_reference_registered_commit": contract["reference_implementation"]["python_commit"],
        "reference_sha256": ref_now,
        "rust_commit": rust_commit,
        "build_provenance": {"rustc": rustc, "cargo_lock_sha256": sha_file(os.path.join(ROOT, "Cargo.lock")),
                             "source_sha256": srcs},
        "environment": {"python": platform.python_version(), "numpy": numpy.__version__, "pandas": pandas.__version__,
                        "cpu": cpu, "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
                        "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")}},
        "scoring_master_seed": seed,
        "summary": summary,
        "per_test": per_test,
        "invariants": inv,
        "conservation": conservation,
        "domain_error": {"vectors": de, "failures": domain_fail},
        "schema": {"failures": schema_fail},
        "performance": {"status": "RECORDED_NOT_GATING", "python_golden_propagate_s": t_py_g,
                        "rust_golden_propagate_s_incl_process": t_rs_g, "python_all_vectors_s": t_py},
        "campaign_history": [{"execution": "score", "seed": seed, "verdict": verdict,
                              "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}],
        "ledger_update_requested": {
            "component": "C-ABEP_SIM_MISSION_ENV_PY",
            "contract": contract["id"],
            "requested_status": "ADMITTED (function subset: SOLAR_CONST, beta_angle, eclipse_fraction, "
                                "worst_eclipse_fraction, array_area_for, propagate)" if verdict_ok else "NOT_ADMITTED",
            "not_ported": ["spacecraft_drag (lane brief A9.31: unsourced defaults, class-H callers only)",
                           "pointing_factors (AUDITED_NOT_PORTED: sole caller spacecraft_drag; owner question OQ-MI-03)",
                           "plume_interaction, ARRAY_AREAL_KG_M2 (class-H callers; not in the SC-WP-09 list)"],
        },
    }
    os.makedirs(os.path.join(CDIR, "reference_outputs"), exist_ok=True)
    ref_path = os.path.join(CDIR, "reference_outputs", "python_outputs_v1.json.gz")
    payload = json.dumps(deep_j({"seed": seed, "vectors": V, "python": PY}), default=str, sort_keys=True).encode()
    with gzip.GzipFile(ref_path, "wb", mtime=0) as f:
        f.write(payload)
    json.dump({"python_outputs_v1.json.gz": sha_file(ref_path), "captured_at_python_commit": report["python_commit"]},
              open(os.path.join(CDIR, "reference_outputs", "MANIFEST.json"), "w"), indent=1)
    with open(REPORT, "w") as f:
        f.write(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    with open(REPORT.replace(".json", ".md"), "w") as f:
        f.write(report_md(report))
    print(verdict, summary["checks"])
    return 0


def timeit(fn) -> float:
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t


def report_md(r: dict) -> str:
    s = r["summary"]
    lines = [f"# Parity report v1 - {r['contract_id']}", "",
             f"Verdict: **{r['parity']}** ({r['verdict']}). Generated from `parity_report_v1.json`.", "",
             f"* Contract: `{r['contract_path']}` sha256 `{r['contract_sha256']}`, registered in `{r['contract_registered_in'][:12]}`.",
             f"* Python reference commit `{r['python_commit'][:12]}` (registered {r['python_reference_registered_commit'][:12]}); "
             f"Rust commit `{r['rust_commit'][:12]}`; {r['build_provenance']['rustc']}.",
             f"* Environment: Python {r['environment']['python']}, numpy {r['environment']['numpy']}, pandas "
             f"{r['environment']['pandas']}, {r['environment']['cpu']}.",
             f"* Scoring seed {r['scoring_master_seed']}; {s['n_vectors']} vectors; {s['n_failures']} per-test failures.",
             "", "## Checks", ""]
    lines += [f"* {k}: {'pass' if v else 'FAIL'}" for k, v in s["checks"].items()]
    lines += ["", "## Observables", "", "| entry | observable | n | fail | bit-identical | max abs diff | max rel diff | max ulp |",
              "|---|---|---|---|---|---|---|---|"]
    for o in s["observables"]:
        lines.append(f"| {o['entry']} | {o['observable']} | {o['n']} | {o['fail']} | {o['bit_identical']} | "
                     f"{o['max_abs_diff']:.3g} | {o['max_rel_diff']:.3g} | {o['max_ulp']:.3g} |")
    lines += ["", "## Domain / error parity", ""]
    for t in r["domain_error"]["vectors"]:
        lines.append(f"* {t['id']} ({t['entry']}): Python {t['python_outcome']} {t['python_class'] or ''}, Rust "
                     f"{t['rust_outcome']} {t['rust_class'] or ''} - {'ok' if not t['failures'] else t['failures']}")
    if s["first_failures"]:
        lines += ["", "## First failures", ""] + [f"* {f['id']}: {f['failures']}" for f in s["first_failures"]]
    lines += ["", "## Not ported (recorded)", ""] + [f"* {x}" for x in r["ledger_update_requested"]["not_ported"]]
    lines += ["", f"Performance (recorded, not gating): Python golden propagate {r['performance']['python_golden_propagate_s']:.3f} s, "
              f"Rust incl. process start {r['performance']['rust_golden_propagate_s_incl_process']:.3f} s.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "dev"))
