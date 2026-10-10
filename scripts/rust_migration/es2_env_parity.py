#!/usr/bin/env python3
"""ES-2 environment parity harness (lane B1; A9.29 sec. 6, SC-WP-01).

Implements the vector generators, reference calls, tolerance classes and decision rules registered in

* docs/rust_migration/contracts/C-ABEP_SIM_ATMOSPHERE_PY/parity_prereg_v1.json                     (contract a)
* docs/rust_migration/contracts/C-ABEP_SIM_CONSTANTS_PY/parity_prereg_v1.json                      (contract b)
* docs/rust_migration/contracts/C-ABEP_SIM_MISSION_ENV_PY-CONSTANTS_KERNEL/parity_prereg_v1.json   (contract c)
* docs/rust_migration/contracts/C-ABEP_SIM_ATMOSPHERE_ORBIT_PY/parity_prereg_v1.json               (contract d)

The Python reference is called read-only; the Rust side is the `abep-env-parity` binary of crates/abep-atmos.

    python3 scripts/rust_migration/es2_env_parity.py dev   a|b|c|d   # development seed; never a verdict; writes nothing
    python3 scripts/rust_migration/es2_env_parity.py score a|b|c|d   # scoring seed, ONCE: report + captured references

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
for _k in ("ABEP_ATMOSPHERE", "ABEP_ALLOW_TABLE_ATMOSPHERE"):
    os.environ.pop(_k, None)

import dataclasses  # noqa: E402
import datetime  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import statistics  # noqa: E402
import struct  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

CDIR = os.path.join(ROOT, "docs", "rust_migration", "contracts")
CONTRACT_DIRS = {"a": "C-ABEP_SIM_ATMOSPHERE_PY", "b": "C-ABEP_SIM_CONSTANTS_PY",
                 "c": "C-ABEP_SIM_MISSION_ENV_PY-CONSTANTS_KERNEL", "d": "C-ABEP_SIM_ATMOSPHERE_ORBIT_PY"}
BIN = os.path.join(ROOT, "target", "release", "abep-env-parity")
DATA = os.path.join(ROOT, "abep_sim", "data")
SC = ["ECSS_LT_LOW", "ECSS_LT_MODERATE", "ECSS_LT_HIGH", "ECSS_ST_HIGH"]
THERMO = ["rho_kg_m3", "n_N2_m3", "n_O2_m3", "n_O_m3", "n_He_m3", "n_Ar_m3", "n_N_m3", "n_total_m3", "T_K", "x_O",
          "x_N2", "x_O2", "x_N", "x_He", "x_Ar"]
WIND_KEYS = ["u_mer_quiet_m_s", "u_zon_quiet_m_s", "u_mer_dist_m_s", "u_zon_dist_m_s", "u_mer_m_s", "u_zon_m_s"]
ULP4 = {"k_ulp": 4}
REL12 = {"k_ulp": 4, "r_rel": 1e-12}
REL10 = {"k_ulp": 4, "r_rel": 1e-10}
WIND = {"k_ulp": 4, "a_abs": 1e-9}


def sha_file(p: str) -> str:
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_contract(key: str) -> tuple[dict, str, str]:
    p = os.path.join(CDIR, CONTRACT_DIRS[key], "parity_prereg_v1.json")
    return json.load(open(p)), sha_file(p), p


def jnum(x: float):
    """JSON transport of a float (non-finite values as the registered strings)."""
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "+inf" if x > 0 else "-inf"
    return float(x)


def unj(x):
    if x == "NaN":
        return float("nan")
    if x == "+inf":
        return float("inf")
    if x == "-inf":
        return float("-inf")
    return x


def rng(master: int, entry: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([master, entry]))


# ----------------------------------------------------------------------------------------------------------------------
# Rust runner
# ----------------------------------------------------------------------------------------------------------------------
def build_rust() -> None:
    subprocess.run(["cargo", "build", "--release", "--locked", "-p", "abep-atmos", "--bin", "abep-env-parity"],
                   cwd=ROOT, check=True, env={**os.environ, "PATH": "/root/.cargo/bin:" + os.environ.get("PATH", "")})


def run_rust(requests: list, repo_root: str = ROOT) -> tuple[dict, bytes, list, float]:
    payload = json.dumps({"repo_root": repo_root, "requests": requests}, allow_nan=False).encode()
    t0 = time.perf_counter()
    p = subprocess.run([BIN], input=payload, capture_output=True, check=True)
    wall = time.perf_counter() - t0
    out = json.loads(p.stdout)
    timing = [json.loads(line) for line in p.stderr.decode().splitlines() if line.startswith("{")]
    return out, p.stdout, timing, wall


# ----------------------------------------------------------------------------------------------------------------------
# Tolerance classes
# ----------------------------------------------------------------------------------------------------------------------
def exact_equal(a, b) -> bool:
    """EXACT_VALUE: equal value; booleans only equal booleans; numbers compare by value (-0.0 == 0.0)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(exact_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return list(a) == list(b) and all(exact_equal(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


class Tally:
    """Per-entry, per-observable accounting."""

    def __init__(self):
        self.obs: dict = {}
        self.failures: list = []

    def _o(self, entry, name, cls):
        k = f"{entry}::{name}"
        if k not in self.obs:
            self.obs[k] = {"entry": entry, "observable": name, "tolerance_class": cls, "n": 0, "n_fail": 0,
                           "n_bit_identical": 0, "max_abs_diff": 0.0, "max_rel_diff": 0.0, "max_ulp": 0.0}
        return self.obs[k]

    def exact(self, entry, name, rust, py, vid):
        o = self._o(entry, name, "EXACT_VALUE")
        o["n"] += 1
        same = exact_equal(rust, py)
        if same:
            o["n_bit_identical"] += 1
        else:
            o["n_fail"] += 1
            self.failures.append({"vector": vid, "entry": entry, "observable": name, "rust": repr(rust)[:200],
                                  "python": repr(py)[:200]})
        return same

    def ulp(self, entry, name, rust, py, tol, vid):
        cls = "ULP_BOUNDED"
        o = self._o(entry, name, cls)
        o["tolerance"] = tol
        o["n"] += 1
        ok = False
        if isinstance(rust, (int, float)) and not isinstance(rust, bool) and isinstance(py, (int, float)):
            rust, py = float(rust), float(py)
            if rust == py:
                ok = True
                o["n_bit_identical"] += 1 if struct.pack("<d", rust) == struct.pack("<d", py) else 0
            elif math.isfinite(rust) and math.isfinite(py):
                d = abs(rust - py)
                u = math.ulp(py)
                o["max_abs_diff"] = max(o["max_abs_diff"], d)
                o["max_ulp"] = max(o["max_ulp"], d / u)
                if py != 0.0:
                    o["max_rel_diff"] = max(o["max_rel_diff"], d / abs(py))
                ok = (("k_ulp" in tol and d <= tol["k_ulp"] * u) or ("r_rel" in tol and d <= tol["r_rel"] * abs(py))
                      or ("a_abs" in tol and d <= tol["a_abs"]))
        if not ok:
            o["n_fail"] += 1
            self.failures.append({"vector": vid, "entry": entry, "observable": name, "rust": repr(rust),
                                  "python": repr(py), "tolerance": tol})
        return ok

    def display(self, entry, name, rust, py, vid):
        o = self._o(entry, name, "ULP_BOUNDED (display unit)")
        o["n"] += 1
        unit = 10.0 ** (math.floor(math.log10(abs(py))) - 3) if py else 0.0
        ok = abs(rust - py) <= unit
        o["max_abs_diff"] = max(o["max_abs_diff"], abs(rust - py))
        o["n_bit_identical"] += 1 if rust == py else 0
        if not ok:
            o["n_fail"] += 1
            self.failures.append({"vector": vid, "entry": entry, "observable": name, "rust": rust, "python": py})
        return ok

    def summary(self):
        return {"observables": list(self.obs.values()), "n_failures": len(self.failures),
                "failures_first_50": self.failures[:50]}


def compare_dict(t: Tally, entry: str, vid: str, rust: dict, py: dict, classes: dict) -> None:
    """classes: key -> 'EXACT' | tolerance dict. Every key of both dicts must be classified."""
    t.exact(entry, "key order", list(rust.keys()), list(py.keys()), vid)
    for k, cls in classes.items():
        if k not in py or k not in rust:
            continue
        if cls == "EXACT":
            t.exact(entry, k, rust[k], py[k], vid)
        else:
            t.ulp(entry, k, rust[k], py[k], cls, vid)
    unclassified = (set(py) | set(rust)) - set(classes)
    if unclassified:
        t.exact(entry, "unclassified keys", sorted(unclassified), [], vid)


# ----------------------------------------------------------------------------------------------------------------------
# Python reference access
# ----------------------------------------------------------------------------------------------------------------------
from abep_sim import atmosphere as atm  # noqa: E402
from abep_sim import atmosphere_orbit as ao  # noqa: E402
from abep_sim import atmosphere_orbit_v2 as v2  # noqa: E402
from abep_sim import constants as cst  # noqa: E402
from abep_sim import mission_env as me  # noqa: E402
from abep_sim.design import intake_synthesis as isy  # noqa: E402

ao._pymsis_version = lambda: None          # check() in its registered pymsis-absent configuration (DIV-D-03)

MAP_A = {"ValueError": "OUT_OF_DOMAIN", "KeyError": "OUT_OF_DOMAIN", "ZeroDivisionError": "OUT_OF_DOMAIN",
         "FileNotFoundError": "MODEL_ERROR"}
MAP_C = {"ValueError": "OUT_OF_DOMAIN", "ZeroDivisionError": "OUT_OF_DOMAIN", "OverflowError": "OUT_OF_DOMAIN"}
MAP_D = {"JSONDecodeError": "MODEL_ERROR", "ValueError": "OUT_OF_DOMAIN", "KeyError": "OUT_OF_DOMAIN",
         "IndexError": "OUT_OF_DOMAIN", "OverflowError": "OUT_OF_DOMAIN", "FileNotFoundError": "MODEL_ERROR",
         "RuntimeError": "MODEL_ERROR", "DesignStateSetError": "MODEL_ERROR"}


def map_exception(e: BaseException, mapping: dict) -> str:
    for cls in type(e).__mro__:
        if cls.__name__ in mapping:
            return mapping[cls.__name__]
    return "UNMAPPED_" + type(e).__name__


def py_call(fn, mapping):
    """(status, value, exception class name)."""
    try:
        return "EVALUATED", fn(), None
    except Exception as e:  # noqa: BLE001 - every exception class is mapped explicitly
        return map_exception(e, mapping), None, type(e).__name__


SAVE = {m: {k: getattr(m, k) for k in ks} for m, ks in (
    (ao, ["DATA_DIR", "GZ_PATH", "LEGACY_CSV_PATH", "JSON_PATH", "DESIGN_PATH", "DESIGN_V2_PATH"]),
    (v2, ["DATA_DIR", "GZ_PATH", "DIST_GZ_PATH", "JSON_PATH"]), (isy, ["DATA_DIR"]))}
ATM_FILE = atm.__file__


def reset_caches():
    ao._CACHE.clear()
    v2._CACHE.clear()
    isy.load_design_state_set.cache_clear()
    isy.required_states.cache_clear()
    isy.state_index.cache_clear()
    atm._FROZEN.clear()
    atm._MSIS_CACHE.clear()


def point_reference(tree: str | None) -> None:
    for m, ks in SAVE.items():
        for k, val in ks.items():
            if tree is None:
                setattr(m, k, val)
            else:
                dd = os.path.join(tree, "abep_sim", "data")
                setattr(m, k, dd if k == "DATA_DIR" else os.path.join(dd, os.path.basename(val)))
    atm.__file__ = ATM_FILE if tree is None else os.path.join(tree, "abep_sim", "atmosphere.py")
    reset_caches()


def make_tree(mutations) -> str:
    t = tempfile.mkdtemp(prefix="es2_tree_")
    shutil.copytree(os.path.join(ROOT, "config"), os.path.join(t, "config"))
    dd = os.path.join(t, "abep_sim", "data")
    os.makedirs(dd)
    for f in os.listdir(DATA):
        if os.path.isfile(os.path.join(DATA, f)):
            os.symlink(os.path.join(DATA, f), os.path.join(dd, f))
    for m in mutations:
        m(t, dd)
    return t


def m_remove(name):
    return lambda t, dd: os.remove(os.path.join(dd, name))


def m_bytes(name, fn):
    def f(t, dd):
        p = os.path.join(dd, name)
        b = bytearray(open(os.path.join(DATA, name), "rb").read())
        os.remove(p)
        open(p, "wb").write(bytes(fn(b)))
    return f


def flip_mtime(b):
    b[4] ^= 0x01
    return b


def alter_producer(b):
    nb = bytes(b).replace(b'"producer": "python -m', b'"producer": "pythoN -m', 1)
    assert nb != bytes(b)
    return nb


def alter_msis_rho(b):
    lines = bytes(b).decode().split("\n")
    for i, line in enumerate(lines):
        if line.startswith("2.00000000e+02,1.50000000e+02,"):
            f = line.split(",")
            r = f[2]
            f[2] = r[:9] + str((int(r[9]) + 1) % 10) + r[10:]
            lines[i] = ",".join(f)
            break
    return "\n".join(lines).encode()


def m_repin_sidecar(t, dd):
    n = "atmosphere_msis21_orbit_v1_design_states_v2.json"
    nb = open(os.path.join(dd, n), "rb").read()
    j = os.path.join(dd, "atmosphere_msis21_orbit_v1.json")
    m = json.load(open(os.path.join(DATA, "atmosphere_msis21_orbit_v1.json")))
    os.remove(j)
    m["design_states_file_v2"]["sha256"] = hashlib.sha256(nb).hexdigest()
    with open(j, "w") as f:
        json.dump(m, f, indent=1)
        f.write("\n")


def m_model_set(t, dd):
    p = os.path.join(t, "config", "model_set", "physics_model_set_v1.json")
    b = open(p, "rb").read()
    nb = b.replace(b'"id": "physics_model_set_v1"', b'"id": "physics_model_set_vX"', 1)
    assert nb != b
    open(p, "wb").write(nb)


# ----------------------------------------------------------------------------------------------------------------------
# Contract a: atmosphere.py frozen reader
# ----------------------------------------------------------------------------------------------------------------------
A_CLASSES = {**{k: REL12 for k in ("rho", "fO", "fN2", "fO2", "T", "m_mean", "n", "flux_kg_m2_s", "p_ambient_Pa",
                                   "n_O")},
             "V": ULP4, **{k: "EXACT" for k in ("alt_km", "solar", "f107", "f107a", "ap", "epoch", "source")}}


def vectors_a(master: int) -> list:
    v = []
    for f in (70.0, 100.0, 150.0, 190.0, 230.0):
        for i in range(76):
            v.append({"id": f"G-A-{len(v):03d}", "entry": "atmosphere", "args": {"alt_km": 150.0 + 2 * i, "solar": f}})
    edges = [("E-A-01", 200.0, "low"), ("E-A-02", 200.0, "mean"), ("E-A-03", 200.0, "high"),
             ("E-A-04", 180.0, "mean"), ("E-A-05", 230.0, "mean"), ("E-A-06", 150.0, 70.0), ("E-A-07", 300.0, 230.0),
             ("E-A-08", 150.0, 230.0), ("E-A-09", 300.0, 70.0), ("E-A-10", 205.5, 110.0),
             ("E-A-11", 299.999999, 229.999999), ("E-A-12", 150.000001, 70.000001), ("E-A-13", 200.0000001, 150.0)]
    v += [{"id": i, "entry": "atmosphere", "args": {"alt_km": a, "solar": s}} for i, a, s in edges]
    r0 = rng(master, 0)
    alt, f107 = r0.uniform(150.0, 300.0, 800), r0.uniform(70.0, 230.0, 800)
    v += [{"id": f"R-A-0-{i:03d}", "entry": "atmosphere", "args": {"alt_km": float(alt[i]), "solar": float(f107[i])}}
          for i in range(800)]
    r1 = rng(master, 1)
    alt, k = r1.uniform(150.0, 300.0, 200), r1.integers(0, 3, 200)
    v += [{"id": f"R-A-1-{i:03d}", "entry": "atmosphere",
           "args": {"alt_km": float(alt[i]), "solar": ("low", "mean", "high")[int(k[i])]}} for i in range(200)]
    de = [("DE-A-01", 149.999, "mean"), ("DE-A-02", 300.001, "mean"), ("DE-A-03", 200.0, 69.999),
          ("DE-A-04", 200.0, 230.001), ("DE-A-05", "NaN", "mean"), ("DE-A-06", "+inf", "mean"),
          ("DE-A-07", "-inf", 150.0), ("DE-A-08", 200.0, "NaN"), ("DE-A-09", 200.0, "medium"), ("DE-A-10", 200.0, "")]
    v += [{"id": i, "entry": "atmosphere", "args": {"alt_km": a, "solar": s}, "expected": "OUT_OF_DOMAIN"}
          for i, a, s in de]
    v += [{"id": f"G-A-OV-{i:02d}", "entry": "orbital_velocity", "args": {"alt_km": 10.0 * i}} for i in range(41)]
    v += [{"id": i, "entry": "orbital_velocity", "args": {"alt_km": a}} for i, a in
          (("E-A-14", 0.0), ("E-A-15", 200.0), ("E-A-16", -6370.999), ("E-A-17", 1.0e6))]
    r2 = rng(master, 2)
    alt = r2.uniform(-6000.0, 40000.0, 300)
    v += [{"id": f"R-A-2-{i:03d}", "entry": "orbital_velocity", "args": {"alt_km": float(alt[i])}} for i in range(300)]
    v += [{"id": "DE-A-11", "entry": "orbital_velocity", "args": {"alt_km": -6371.0}, "expected": "OUT_OF_DOMAIN"},
          {"id": "DE-A-12", "entry": "orbital_velocity", "args": {"alt_km": -6400.0}, "expected": "OUT_OF_DOMAIN"}]
    v += [{"id": i, "entry": "orbital_velocity", "args": {"alt_km": a}, "divergence": "DIV-A-04",
           "expected_python": "EVALUATED", "expected": "OUT_OF_DOMAIN"}
          for i, a in (("DE-A-13", "NaN"), ("DE-A-14", "+inf"), ("DE-A-15", "-inf"))]
    v.append({"id": "L-A-01", "entry": "msis21_load", "args": {}})
    return v


def py_a(vec):
    a = {k: unj(x) for k, x in vec["args"].items()}
    if vec["entry"] == "atmosphere":
        def f():
            atm._MSIS_CACHE.clear()
            r = atm.atmosphere(a["alt_km"], a["solar"])
            if not str(r["source"]).startswith("NRLMSIS 2.1 frozen scenario"):
                raise AssertionError("reference left the frozen branch")
            return r
        return py_call(f, MAP_A)
    if vec["entry"] == "orbital_velocity":
        return py_call(lambda: atm.orbital_velocity(a["alt_km"]), MAP_A)
    if vec["entry"] == "msis21_load":
        def f():
            fz = atm._frozen()
            df = fz["df"]
            return {"sha256_16": fz["meta"]["sha256_16"], "alt_km": [float(x) for x in np.sort(df.alt_km.unique())],
                    "f107": [float(x) for x in np.sort(df.f107.unique())]}
        return py_call(f, MAP_A)
    raise KeyError(vec["entry"])


def compare_a(t, vec, rust_v, py_v):
    e = vec["entry"]
    if e == "atmosphere":
        compare_dict(t, e, vec["id"], rust_v, py_v, A_CLASSES)
        if rust_v:
            t.ulp(e, "CONS-A-01 |n m_mean / rho - 1| (Rust)", rust_v["n"] * rust_v["m_mean"] / rust_v["rho"], 1.0,
                  {"a_abs": 1e-14}, vec["id"])
            t.ulp(e, "CONS-A-02 |p / (n K_B T) - 1| (Rust)", rust_v["p_ambient_Pa"] / (rust_v["n"] * cst.K_B *
                                                                                      rust_v["T"]), 1.0,
                  {"a_abs": 1e-14}, vec["id"])
    elif e == "orbital_velocity":
        t.ulp(e, "V", rust_v, py_v, ULP4, vec["id"])
    elif e == "msis21_load":
        for k in ("sha256_16", "alt_km", "f107"):
            t.exact(e, k, rust_v[k], py_v[k], vec["id"])


def trees_a():
    return [("RF-A-01", [m_remove("atmosphere_msis21_v1.csv")], "MODEL_ERROR", "MODEL_ERROR"),
            ("RF-A-02", [m_remove("atmosphere_msis21_v1.json")], "MODEL_ERROR", "MODEL_ERROR"),
            ("RF-A-03", [m_bytes("atmosphere_msis21_v1.csv", alter_msis_rho)], "EVALUATED", "MODEL_ERROR")]


def tree_entries_a():
    return [{"id": "msis21_load", "entry": "msis21_load", "args": {}},
            {"id": "atmosphere", "entry": "atmosphere", "args": {"alt_km": 200.0, "solar": "mean"}}]


def py_tree_a(entry):
    # fresh reference state per entry: _frozen() keeps a half-filled cache (df without meta) after a failed JSON read,
    # which would turn a later call's FileNotFoundError into a KeyError (recorded as a reference observation)
    atm._FROZEN.clear()
    atm._MSIS_CACHE.clear()
    if entry == "msis21_load":
        return py_a({"entry": "msis21_load", "args": {}})
    return py_a({"entry": "atmosphere", "args": {"alt_km": 200.0, "solar": "mean"}})


# ----------------------------------------------------------------------------------------------------------------------
# Contract b: constants
# ----------------------------------------------------------------------------------------------------------------------
def vectors_b(master):
    return [{"id": "G-B-01", "entry": "constants", "args": {}}]


def py_b(vec):
    def f():
        he = py_call(lambda: cst.M_SPECIES["He"], {"KeyError": "OUT_OF_DOMAIN"})[0]
        return {"G0": cst.G0, "E_CHARGE": cst.E_CHARGE, "AMU": cst.AMU, "K_B": cst.K_B, "MU_EARTH": cst.MU_EARTH,
                "R_EARTH": cst.R_EARTH, "M_O": cst.M_SPECIES["O"], "M_N2": cst.M_SPECIES["N2"],
                "M_O2": cst.M_SPECIES["O2"], "M_XE": cst.M_SPECIES["Xe"], "species_He": he,
                "M_SPECIES keys": list(cst.M_SPECIES)}
    return py_call(f, {})


def bits(x):
    return struct.pack("<d", float(x)).hex()


def compare_b(t, vec, rust_v, py_v):
    for k in ("G0", "E_CHARGE", "AMU", "K_B", "MU_EARTH", "R_EARTH", "M_O", "M_N2", "M_O2", "M_XE"):
        t.exact("constants", k + " (bits)", bits(rust_v[k]), bits(py_v[k]), vec["id"])
    t.exact("constants", "DE-B-01 species He", rust_v["species_He"], py_v["species_He"], vec["id"])
    t.exact("constants", "INV-B-02 species keys", ["O", "N2", "O2", "Xe"], py_v["M_SPECIES keys"], vec["id"])


# ----------------------------------------------------------------------------------------------------------------------
# Contract c: mission_env constants kernel
# ----------------------------------------------------------------------------------------------------------------------
def vectors_c(master):
    v = [{"id": "G-C-01", "entry": "mission_env_constants", "args": {}},
         {"id": "G-C-02", "entry": "spacecraft_defaults", "args": {}}]
    alts = [180.0, 195.0, 200.0, 215.0, 230.0] + [50.0 * i for i in range(21)]
    v += [{"id": f"G-C-S-{i:02d}", "entry": "sso_inclination_deg", "args": {"alt_km": a}} for i, a in enumerate(alts)]
    v += [{"id": i, "entry": "sso_inclination_deg", "args": {"alt_km": a}} for i, a in
          (("E-C-01", -6370.0), ("E-C-02", 3000.0), ("E-C-03", -100.0))]
    alt = rng(master, 0).uniform(-1000.0, 4000.0, 400)
    v += [{"id": f"R-C-0-{i:03d}", "entry": "sso_inclination_deg", "args": {"alt_km": float(alt[i])}}
          for i in range(400)]
    v += [{"id": i, "entry": "sso_inclination_deg", "args": {"alt_km": a}, "expected": "OUT_OF_DOMAIN"} for i, a in
          (("DE-C-01", 10000.0), ("DE-C-02", 1.0e6), ("DE-C-03", -6371.0), ("DE-C-04", -7000.0),
           ("DE-C-05", 1.0e103), ("DE-C-06", "+inf"), ("DE-C-07", "-inf"))]
    v.append({"id": "DE-C-08", "entry": "sso_inclination_deg", "args": {"alt_km": "NaN"}, "divergence": "DIV-C-01",
              "expected_python": "EVALUATED", "expected": "OUT_OF_DOMAIN"})
    return v


def py_c(vec):
    e = vec["entry"]
    if e == "mission_env_constants":
        return py_call(lambda: {"J2": me.J2, "OMEGA_E": me.OMEGA_E}, MAP_C)
    if e == "spacecraft_defaults":
        return py_call(lambda: {f.name: f.default for f in dataclasses.fields(me.Spacecraft)}, MAP_C)
    if e == "sso_inclination_deg":
        return py_call(lambda: me.sso_inclination_deg(unj(vec["args"]["alt_km"])), MAP_C)
    raise KeyError(e)


def compare_c(t, vec, rust_v, py_v):
    e = vec["entry"]
    if e == "mission_env_constants":
        for k in ("J2", "OMEGA_E"):
            t.exact(e, k + " (bits)", bits(rust_v[k]), bits(py_v[k]), vec["id"])
    elif e == "spacecraft_defaults":
        t.exact(e, "field names and order", list(rust_v), list(py_v), vec["id"])
        for k in py_v:
            if isinstance(py_v[k], bool):
                t.exact(e, k, rust_v.get(k), py_v[k], vec["id"])
            else:
                t.exact(e, k + " (bits)", bits(rust_v.get(k, float("nan"))), bits(py_v[k]), vec["id"])
    else:
        t.ulp(e, "inclination_deg", rust_v, py_v, ULP4, vec["id"])


# ----------------------------------------------------------------------------------------------------------------------
# Contract d: orbit atmosphere, winds, design-state set, 196-state execution
# ----------------------------------------------------------------------------------------------------------------------
STATE_CLASSES = {**{k: "EXACT" for k in ("alt_km", "lat_deg", "doy", "scenario", "f107", "f107a", "ap", "source",
                                         "evaluation", "interp_max_rel_err_rho", "lst_h", "lon_deg")},
                 **{k: REL10 for k in THERMO}}
ORBIT_CLASSES = {**STATE_CLASSES,
                 **{k: "EXACT" for k in ("inclination_deg", "ltan_h", "orbit_inputs_status", "wind_included",
                                         "wind_open_item", "state_id", "geometry")},
                 **{k: ULP4 for k in ("lat_deg", "lst_h", "lon_deg", "t_s", "u_deg", "ut_h", "v_orb_m_s",
                                      "v_rel_corot_m_s", "weight")},
                 "flux_corot_kg_m2_s": REL10}
WIND_CLASSES = {**{k: WIND for k in WIND_KEYS},
                **{k: "EXACT" for k in ("ap_hwm", "wind_model", "wind_source", "wind_interp_max_abs_err_m_s")}}
V2_CLASSES = {**STATE_CLASSES, **WIND_CLASSES, "dataset_id": "EXACT", "dataset_status": "EXACT"}
ATM_ULP = ("fO", "fN2", "fO2", "m_mean", "n", "V", "flux_kg_m2_s", "p_ambient_Pa", "n_O")
ATM_CLASSES = {**{k: ULP4 for k in ATM_ULP},
               **{k: "EXACT" for k in ("alt_km", "f107", "f107a", "ap", "rho", "T", "state_id", "source", "V_basis",
                                       "orbit_basis")}}
DS_FIELDS = ["state_id", "alt_km", "scenario", "f107", "f107a", "ap", "lat_deg", "lst_h", "lon_deg", "doy",
             "rho_kg_m3", "n_O_m3", "n_N2_m3", "n_O2_m3", "T_K", "labels", "evaluation", "interp_max_rel_err_rho",
             "nominal_mission_scenario", "required"]


def st(alt, lat, lst, lon, doy, s):
    return [jnum(alt), jnum(lat), jnum(lst), jnum(lon), jnum(doy), s]


def vectors_d(master):
    v = []
    r0 = rng(master, 0)
    for s in SC:
        alt, lat = r0.uniform(180.0, 230.0, 400), r0.uniform(-90.0, 90.0, 400)
        lst, lon, doy = r0.uniform(0.0, 24.0, 400), r0.uniform(-180.0, 360.0, 400), r0.uniform(1.0, 365.0, 400)
        v += [{"id": f"R-D-0-{s}-{i:03d}", "entry": "orbit_state",
               "args": {"state": st(alt[i], lat[i], lst[i], lon[i], doy[i], s)}} for i in range(400)]
    r1 = rng(master, 1)
    idx = [r1.integers(0, n, 200) for n in (8, 4, 19, 6, 8, 4)]
    for i in range(200):
        d, a, la, lo, ls, s = (int(x[i]) for x in idx)
        v.append({"id": f"R-D-1-{i:03d}", "entry": "orbit_state",
                  "args": {"state": st(ao.ALT_KM[a], ao.LAT_DEG[la], ao.LST_H[ls], ao.LON_DEG[lo], ao.DOY[d], SC[s])}})
    r2 = rng(master, 2)
    idx = [r2.integers(0, n, 200) for n in (8, 4, 19, 6, 8, 4)]
    for i in range(200):
        d, a, la, lo, ls, s = (int(x[i]) for x in idx)
        v.append({"id": f"R-D-2-{i:03d}", "entry": "orbit_node_state",
                  "args": {"idx": [d, a, la, lo, ls], "scenario": SC[s]}})
    r3 = rng(master, 3)
    alt, inc, ltan = r3.uniform(180.0, 230.0, 40), r3.uniform(0.0, 180.0, 40), r3.uniform(0.0, 24.0, 40)
    i_s, doy, ut0, n = r3.integers(0, 4, 40), r3.integers(1, 365, 40), r3.uniform(0.0, 24.0, 40), r3.integers(4, 49, 40)
    v += [{"id": f"R-D-3-{i:02d}", "entry": "orbit_states",
           "args": {"alt_km": float(alt[i]), "inclination_deg": float(inc[i]), "ltan_h": float(ltan[i]),
                    "scenario": SC[int(i_s[i])], "doy": float(doy[i]), "ut_start_h": float(ut0[i]),
                    "n_samples": float(n[i])}} for i in range(40)]
    r4 = rng(master, 4)
    for s in SC:
        alt, lat = r4.uniform(180.0, 230.0, 300), r4.uniform(-90.0, 90.0, 300)
        lst, lon, doy = r4.uniform(0.0, 24.0, 300), r4.uniform(-180.0, 360.0, 300), r4.uniform(1.0, 365.0, 300)
        for i in range(300):
            args = {"state": st(alt[i], lat[i], lst[i], lon[i], doy[i], s)}
            v.append({"id": f"R-D-4-{s}-{i:03d}", "entry": "wind", "args": args})
            if i < 100:
                v.append({"id": f"R-D-4-{s}-{i:03d}-v2", "entry": "state_v2", "args": args})
    edges = [("E-D-01", [180.0, -90.0, 0.0, -180.0, 1.0, SC[0]]), ("E-D-02", [230.0, 90.0, 24.0, 360.0, 365.0, SC[3]]),
             ("E-D-03", [200.0, 0.0, 24.0, 0.0, 172.0, SC[1]]), ("E-D-04", [200.0, 45.0, 12.0, 359.999999, 300.0, SC[2]]),
             ("E-D-05", [215.0, -37.5, 7.25, -179.5, 364.5, SC[1]]), ("E-D-06", [195.0, 89.99, 5.0, 100.0, 1.0, SC[0]]),
             ("E-D-07", [180.0, 37.0, 21.0, 240.0, 47.0, SC[2]]), ("E-D-08", [230.0, 0.0, 0.0, 0.0, 365.0, SC[3]])]
    for i, s in edges:
        for e in ("orbit_state", "wind", "state_v2"):
            v.append({"id": f"{i}-{e}", "entry": e, "args": {"state": s}})
    ob = {"alt_km": 200.0, "inclination_deg": 97.0, "ltan_h": 10.5, "scenario": SC[1], "doy": 100.0,
          "ut_start_h": 0.0, "n_samples": 8.0}
    oe = [("E-D-O-01", dict(alt_km=200.0, inclination_deg=96.33, ltan_h=6.0, scenario=SC[1], doy=80.0,
                            ut_start_h=0.0, n_samples=16.0)),
          ("E-D-O-02", dict(alt_km=180.0, inclination_deg=0.0, ltan_h=12.0, scenario=SC[0], doy=1.0, ut_start_h=0.0,
                            n_samples=8.0)),
          ("E-D-O-03", dict(alt_km=230.0, inclination_deg=180.0, ltan_h=0.0, scenario=SC[3], doy=200.0,
                            ut_start_h=12.0, n_samples=8.0)),
          ("E-D-O-04", dict(alt_km=210.0, inclination_deg=90.0, ltan_h=18.0, scenario=SC[2], doy=150.0,
                            ut_start_h=5.0, n_samples=4.0)),
          ("E-D-O-05", dict(ob, inclination_deg=97.0, doy=365.0)), ("E-D-O-06", dict(ob, ut_start_h=30.0))]
    v += [{"id": i, "entry": "orbit_states", "args": a} for i, a in oe]
    for s in SC:
        for k, ix in enumerate(([0, 0, 0, 0, 0], [7, 3, 18, 5, 7])):
            v.append({"id": f"E-D-N-01-{s}-{k}", "entry": "orbit_node_state", "args": {"idx": ix, "scenario": s}})
    v += [{"id": "E-D-L-01", "entry": "load_design_states", "args": {"version": "v2"}},
          {"id": "E-D-L-02", "entry": "load_design_states", "args": {"version": "v1"}},
          {"id": "E-D-S-01", "entry": "design_state_set", "args": {"lookup": ["ds2:bogus", "h200_f150", ""]}},
          {"id": "G-D-LOAD", "entry": "orbit_load", "args": {}},
          {"id": "G-D-DSV2", "entry": "design_states_v2", "args": {}},
          {"id": "G-D-EXEC", "entry": "execution", "args": {}},
          {"id": "G-D-CHECK", "entry": "check", "args": {}}]
    de = [("DE-D-01", [179.999, 0.0, 0.0, 0.0, 100.0, SC[1]]), ("DE-D-02", [230.001, 0.0, 0.0, 0.0, 100.0, SC[1]]),
          ("DE-D-03", [200.0, -90.001, 0.0, 0.0, 100.0, SC[1]]), ("DE-D-04", [200.0, 90.001, 0.0, 0.0, 100.0, SC[1]]),
          ("DE-D-05", [200.0, 0.0, -1e-9, 0.0, 100.0, SC[1]]), ("DE-D-06", [200.0, 0.0, 24.000001, 0.0, 100.0, SC[1]]),
          ("DE-D-07", [200.0, 0.0, 0.0, -180.001, 100.0, SC[1]]), ("DE-D-08", [200.0, 0.0, 0.0, 360.001, 100.0, SC[1]]),
          ("DE-D-09", [200.0, 0.0, 0.0, 0.0, 0.999, SC[1]]), ("DE-D-10", [200.0, 0.0, 0.0, 0.0, 365.001, SC[1]]),
          ("DE-D-11", ["NaN", 0.0, 0.0, 0.0, 100.0, SC[1]]), ("DE-D-12", [200.0, "+inf", 0.0, 0.0, 100.0, SC[1]]),
          ("DE-D-13", [200.0, 0.0, 0.0, 0.0, 100.0, "ECSS_LT_MEDIUM"]), ("DE-D-14", [200.0, 0.0, 0.0, 0.0, 100.0, ""])]
    for i, s in de:
        for e in ("orbit_state", "wind", "state_v2"):
            v.append({"id": f"{i}-{e}", "entry": e, "args": {"state": s}, "expected": "OUT_OF_DOMAIN"})
    v += [{"id": i, "entry": "orbit_node_state", "args": a, "expected": "OUT_OF_DOMAIN"} for i, a in (
        ("DE-D-15", {"idx": [0, 0, 19, 0, 0], "scenario": SC[0]}), ("DE-D-16", {"idx": [8, 0, 0, 0, 0], "scenario": SC[0]}),
        ("DE-D-17", {"idx": [0, 0, 0, 0, 0], "scenario": "X"}))]
    bad = [("DE-D-18", {"n_samples": 3.0}), ("DE-D-19", {"n_samples": 4.5}), ("DE-D-20", {"doy": 10.5}),
           ("DE-D-21", {"doy": 0.0}), ("DE-D-22", {"doy": 366.0}), ("DE-D-23", {"inclination_deg": -0.1}),
           ("DE-D-24", {"inclination_deg": 180.1}), ("DE-D-25", {"alt_km": 250.0}),
           ("DE-D-26", {"doy": 365.0, "ut_start_h": 23.5}), ("DE-D-27", {"scenario": "ECSS_LT_MEDIUM"}),
           ("DE-D-28", {"ut_start_h": "NaN"}), ("DE-D-29", {"ltan_h": "NaN"}), ("DE-D-30", {"inclination_deg": "NaN"}),
           ("DE-D-31", {"ut_start_h": "+inf"}), ("DE-D-32", {"n_samples": "NaN"}), ("DE-D-33", {"n_samples": "+inf"}),
           ("DE-D-34", {"doy": "+inf"})]
    v += [{"id": i, "entry": "orbit_states", "args": {**ob, **kw}, "expected": "OUT_OF_DOMAIN"} for i, kw in bad]
    v += [{"id": i, "entry": "load_design_states", "args": {"version": ver}, "expected": "OUT_OF_DOMAIN"}
          for i, ver in (("DE-D-35", "v3"), ("DE-D-36", ""))]
    return v


def py_state_args(a):
    return [unj(x) for x in a["state"]]


def py_composite_execution():
    st_ = isy.required_states()
    ao.load()
    v2.load()
    raw = {x["state_id"]: x for x in isy.load_design_state_set()["states"]}
    recs = []
    for i, s in enumerate(st_):
        rec = {"index": i, "state_id": s.state_id, "status": "EVALUATED", "environment": None, "reproduction": None,
               "wind": None}
        try:
            rec["environment"] = s.atm()
            if s.evaluation == "grid_node":
                fresh = ao.node_state(ao.DOY.index(s.doy), ao.ALT_KM.index(s.alt_km), ao.LAT_DEG.index(s.lat_deg),
                                      ao.LON_DEG.index(s.lon_deg), ao.LST_H.index(s.lst_h), s.scenario)
            else:
                fresh = ao.state(s.alt_km, s.lat_deg, s.lst_h, s.lon_deg, s.doy, s.scenario)
            stored = raw[s.state_id]
            d = max(0.0 if stored[k] == fresh[k] else abs(stored[k] - fresh[k]) / max(abs(stored[k]), abs(fresh[k]))
                    for k in THERMO)
            rec["reproduction"] = {"evaluation": fresh["evaluation"], "max_abs_rel_diff": d,
                                   "reproduced": d <= ao.DESIGN_V2_REL_TOL}
            rec["wind"] = v2.wind(s.alt_km, s.lat_deg, s.lst_h, s.lon_deg, s.doy, s.scenario)
            if not rec["reproduction"]["reproduced"]:
                rec["status"] = "MODEL_ERROR"
        except Exception as e:  # noqa: BLE001
            rec["status"] = map_exception(e, MAP_D)
        recs.append(rec)
    return {"n_states": len(st_), "records": recs}


def py_design_state_set(lookup):
    d = isy.load_design_state_set()
    states = isy.required_states()
    ids = {s.state_id for s in states}
    return {"n_states": d["n_states"], "ids": [s.state_id for s in states],
            "states": [{"state": {f: (list(getattr(s, f)) if f == "labels" else getattr(s, f)) for f in DS_FIELDS},
                        "atm": s.atm(), "record": s.record()} for s in states],
            "lookup": [[s.state_id, s.state_id in ids] for s in states] + [[x, x in ids] for x in lookup]}


def py_d(vec):
    e, a = vec["entry"], vec["args"]
    if e == "orbit_state":
        return py_call(lambda: ao.state(*py_state_args(a)), MAP_D)
    if e == "orbit_node_state":
        return py_call(lambda: ao.node_state(*a["idx"], a["scenario"]), MAP_D)
    if e == "orbit_states":
        kw = {k: unj(x) for k, x in a.items()}
        return py_call(lambda: ao.orbit_states(**kw), MAP_D)
    if e == "wind":
        return py_call(lambda: v2.wind(*py_state_args(a)), MAP_D)
    if e == "state_v2":
        return py_call(lambda: v2.state(*py_state_args(a)), MAP_D)
    if e == "orbit_load":
        def f():
            L = ao.load()
            return {"dataset_sha256": L["meta"]["sha256"], "row_count": L["meta"]["row_count"],
                    "shape": list(L["shape"]), "scenario_order": list(ao.SCENARIO_ORDER),
                    "grid": {k: [float(x) for x in ao.AXES[k]] for k in ("alt_km", "lat_deg", "lst_h", "lon_deg", "doy")}}
        return py_call(f, MAP_D)
    if e == "design_states_v2":
        return py_call(ao.design_states_v2, MAP_D)
    if e == "load_design_states":
        return py_call(lambda: ao.load_design_states(a["version"]), MAP_D)
    if e == "design_state_set":
        return py_call(lambda: py_design_state_set(a["lookup"]), MAP_D)
    if e == "execution":
        return py_call(py_composite_execution, MAP_D)
    if e == "check":
        return py_call(ao.check, MAP_D)
    raise KeyError(e)


def walk_doc(t, entry, vid, r, p, path=""):
    """design_states_v2 document: structure / non-float leaves EXACT; registered float classes."""
    if isinstance(p, dict):
        t.exact(entry, "key order", list(r.keys()) if isinstance(r, dict) else None, list(p.keys()), vid + path)
        if isinstance(r, dict):
            for k in p:
                if k in r:
                    walk_doc(t, entry, vid, r[k], p[k], f"{path}.{k}")
        return
    if isinstance(p, list):
        t.exact(entry, "list length", len(r) if isinstance(r, list) else None, len(p), vid + path)
        if isinstance(r, list):
            for i, (x, y) in enumerate(zip(r, p)):
                walk_doc(t, entry, vid, x, y, f"{path}[{i}]")
        return
    leaf = path.rsplit(".", 1)[-1]
    if isinstance(p, float) and ".states[" in path and leaf in THERMO:
        t.ulp(entry, "states[*]." + leaf, r, p, REL10, vid + path)
    elif isinstance(p, float) and ".max_abs_rel_change_of_extrema." in path:
        t.display(entry, "lat_refinement_sensitivity." + leaf, r, p, vid + path)
    else:
        name = ("states[*]." + leaf) if ".states[" in path else path.lstrip(".")
        t.exact(entry, re.sub(r"\[\d+\]$", "", name), r, p, vid + path)


def compare_d(t, vec, rust_v, py_v):
    e, vid = vec["entry"], vec["id"]
    if e in ("orbit_state", "orbit_node_state"):
        compare_dict(t, e, vid, rust_v, py_v, STATE_CLASSES)
        x = sum(rust_v[k] for k in ("x_O", "x_N2", "x_O2", "x_N", "x_He", "x_Ar"))
        t.ulp(e, "CONS-D-01 |sum x - 1| (Rust)", x, 1.0, {"a_abs": 1e-14}, vid)
        s = 0
        for k in ("n_N2_m3", "n_O2_m3", "n_O_m3", "n_He_m3", "n_Ar_m3", "n_N_m3"):
            s = s + rust_v[k]
        t.exact(e, "CONS-D-02 n_total bits (Rust)", bits(s), bits(rust_v["n_total_m3"]), vid)
    elif e == "orbit_states":
        t.exact(e, "number of states", len(rust_v), len(py_v), vid)
        for i, (r, p) in enumerate(zip(rust_v, py_v)):
            compare_dict(t, e, f"{vid}[{i}]", r, p, ORBIT_CLASSES)
    elif e == "wind":
        compare_dict(t, e, vid, rust_v, py_v, WIND_CLASSES)
        for c in ("mer", "zon"):
            t.exact(e, f"CONS-D-04 u_{c} = quiet + dist bits (Rust)", bits(rust_v[f"u_{c}_m_s"]),
                    bits(rust_v[f"u_{c}_quiet_m_s"] + rust_v[f"u_{c}_dist_m_s"]), vid)
    elif e == "state_v2":
        compare_dict(t, e, vid, rust_v, py_v, V2_CLASSES)
    elif e == "orbit_load":
        for k in ("dataset_sha256", "row_count", "shape", "scenario_order", "grid"):
            t.exact(e, k, rust_v[k], py_v[k], vid)
    elif e == "design_states_v2":
        walk_doc(t, e, vid, rust_v["document"], py_v)
        fc = rust_v["frozen_comparison"]
        t.exact(e, "INV-D-01 Rust vs frozen file within DESIGN_V2_REL_TOL", fc["ok"], True, vid)
        frozen = json.load(open(os.path.join(DATA, "atmosphere_msis21_orbit_v1_design_states_v2.json")))
        t.exact(e, "INV-D-01 Python re-derivation byte-identical to the frozen file",
                json.dumps(py_v, indent=1) + "\n" == open(os.path.join(
                    DATA, "atmosphere_msis21_orbit_v1_design_states_v2.json")).read(), True, vid)
        t.exact(e, "INV-D-01 frozen ids == Rust ids", [s["state_id"] for s in rust_v["document"]["states"]],
                [s["state_id"] for s in frozen["states"]], vid)
    elif e == "load_design_states":
        t.exact(e, "document (every leaf, key order)", json.dumps(rust_v), json.dumps(py_v), vid)
    elif e == "design_state_set":
        t.exact(e, "n_states", rust_v["n_states"], py_v["n_states"], vid)
        t.exact(e, "required state ids in file order", rust_v["ids"], py_v["ids"], vid)
        t.exact(e, "selection lookup", rust_v["lookup"], py_v["lookup"], vid)
        for i, (r, p) in enumerate(zip(rust_v["states"], py_v["states"])):
            compare_dict(t, e + ".state", f"{vid}[{i}]", r["state"], p["state"], {k: "EXACT" for k in DS_FIELDS})
            compare_dict(t, e + ".atm", f"{vid}[{i}]", r["atm"], p["atm"], ATM_CLASSES)
            t.exact(e + ".record", "record()", json.dumps(r["record"]), json.dumps(p["record"]), f"{vid}[{i}]")
            a_ = r["atm"]
            t.ulp(e, "CONS-D-03 |fO + fN2 + fO2 - 1| (Rust)", a_["fO"] + a_["fN2"] + a_["fO2"], 1.0, {"a_abs": 1e-14},
                  f"{vid}[{i}]")
            t.ulp(e, "CONS-D-03 |n m_mean / rho - 1| (Rust)", a_["n"] * a_["m_mean"] / a_["rho"], 1.0,
                  {"a_abs": 1e-14}, f"{vid}[{i}]")
    elif e == "execution":
        t.exact(e, "n_states", rust_v["n_states"], py_v["n_states"], vid)
        t.exact(e, "INV-D-02 n_states == 196 == records", [rust_v["n_states"], len(rust_v["records"])], [196, 196], vid)
        t.exact(e, "INV-D-02 hashes", [rust_v["design_state_set_sha256"], rust_v["dataset_sha256"]],
                ["60073e214cf5edb92d7eacf70be1491ad29ff72f19db0ef3b96a4b30da6f4049",
                 "c0ce282e99695be8cae0834270c5b9ff7853033255665abda7ec18c307566164"], vid)
        t.exact(e, "per-state state_id (file order)", [r["state_id"] for r in rust_v["records"]],
                [r["state_id"] for r in py_v["records"]], vid)
        t.exact(e, "per-state status", [r["status"] for r in rust_v["records"]],
                [r["status"] for r in py_v["records"]], vid)
        t.exact(e, "INV-D-02 every state EVALUATED", rust_v["n_evaluated"], 196, vid)
        for r, p in zip(rust_v["records"], py_v["records"]):
            sid = f"{vid}:{p['state_id']}"
            compare_dict(t, e + ".environment", sid, r["environment"], p["environment"], ATM_CLASSES)
            t.exact(e, "reproduction.evaluation", r["frozen_dataset_reproduction"]["evaluation"],
                    p["reproduction"]["evaluation"], sid)
            t.exact(e, "reproduction.reproduced", r["frozen_dataset_reproduction"]["reproduced"],
                    p["reproduction"]["reproduced"], sid)
            rw = {k: r["wind"][k] for k in WIND_CLASSES}
            compare_dict(t, e + ".wind", sid, rw, p["wind"], WIND_CLASSES)
            t.exact(e, "VS-D-04 wind labels (Rust)", [r["wind"]["dataset_status"], r["wind"]["used_in_free_stream_velocity"]],
                    ["DESIGN_ENVELOPE_PARAMETRIC", False], sid)
    elif e == "check":
        t.exact(e, "ok", rust_v["ok"], py_v["ok"], vid)
    else:
        raise KeyError(e)


RF_ENTRIES = ["orbit_load", "wind_load", "load_design_states(v2)", "design_state_set", "execution", "check"]


def trees_d(contract):
    out = []
    muts = {"RF-D-01": [m_remove("atmosphere_msis21_orbit_v1.csv.gz")],
            "RF-D-02": [m_bytes("atmosphere_msis21_orbit_v1.csv.gz", flip_mtime)],
            "RF-D-03": [m_remove("atmosphere_msis21_orbit_v1.json")],
            "RF-D-04": [m_bytes("atmosphere_msis21_orbit_v1_design_states_v2.json", alter_producer)],
            "RF-D-05": [m_remove("atmosphere_msis21_orbit_v1_design_states_v2.json")],
            "RF-D-06": [m_remove("atmosphere_msis21_hwm14_orbit_v2.csv.gz")],
            "RF-D-07": [m_bytes("atmosphere_msis21_hwm14_orbit_v2.disturbance.csv.gz", flip_mtime)],
            "RF-D-08": [m_remove("atmosphere_msis21_hwm14_orbit_v2.json")],
            "RF-D-09": [m_bytes("atmosphere_msis21_orbit_v1_design_states_v2.json", alter_producer), m_repin_sidecar],
            "RF-D-10": [m_model_set]}
    reg = {c["id"]: c["expected"] for c in contract["domain_and_error_parity"]["cases"] if c["id"].startswith("RF-D")}
    for rid, m in muts.items():
        exp = {k.split(" ")[0]: v for k, v in reg[rid].items()}
        out.append((rid, m, exp))
    return out


def tree_requests_d():
    return [{"id": "orbit_load", "entry": "orbit_load", "args": {}},
            {"id": "wind_load", "entry": "wind_load", "args": {}},
            {"id": "load_design_states(v2)", "entry": "load_design_states", "args": {"version": "v2"}},
            {"id": "design_state_set", "entry": "design_state_set", "args": {"lookup": []}},
            {"id": "execution", "entry": "execution", "args": {}},
            {"id": "check", "entry": "check", "args": {}}]


def py_tree_outcome(entry):
    fns = {"orbit_load": ao.load, "wind_load": v2.load,
           "load_design_states(v2)": lambda: ao.load_design_states("v2"),
           "design_state_set": isy.load_design_state_set,
           "execution": lambda: (isy.required_states(), ao.load(), v2.load()), "check": ao.check}
    try:
        r = fns[entry]()
        return f"ok={r['ok']}" if entry == "check" else "returns"
    except Exception as e:  # noqa: BLE001
        return type(e).__name__


def norm_registered_py(s):
    if s.startswith("returns ok="):
        return s.split()[1]
    if s.startswith("returns"):
        return "returns"
    return s.split()[0]


def rust_outcome(res):
    if res["status"] == "EVALUATED" and res["entry"] == "check":
        return f"ok={res['value']['ok']}"
    return res["status"]


# ----------------------------------------------------------------------------------------------------------------------
# Campaign
# ----------------------------------------------------------------------------------------------------------------------
SPEC = {"a": (vectors_a, py_a, compare_a), "b": (vectors_b, py_b, compare_b), "c": (vectors_c, py_c, compare_c),
        "d": (vectors_d, py_d, compare_d)}


def tojson(x):
    if isinstance(x, dict):
        return {str(k): tojson(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [tojson(v) for v in x]
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def equal_values(a, b):
    return json.dumps(tojson(a), sort_keys=False, allow_nan=True) == json.dumps(tojson(b), sort_keys=False, allow_nan=True)


def environment():
    from numpy._core._multiarray_umath import __cpu_baseline__, __cpu_dispatch__, __cpu_features__
    import pandas
    import scipy
    cpu = ""
    try:
        cpu = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
    except (OSError, StopIteration):
        pass
    cfg = np.show_config(mode="dicts")
    return {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
            "pandas": pandas.__version__, "numpy_simd_baseline": list(__cpu_baseline__),
            "numpy_simd_dispatch": list(__cpu_dispatch__),
            "numpy_simd_avx512f_enabled": bool(__cpu_features__.get("AVX512F")),
            "blas": cfg.get("Build Dependencies", {}).get("blas", {}).get("name", "") + " "
            + str(cfg.get("Build Dependencies", {}).get("blas", {}).get("version", "")),
            "cpu": cpu, "platform": platform.platform(),
            "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
            "requirements_lock_sha256": sha_file(os.path.join(ROOT, "requirements-lock.txt"))}


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def provenance(contract):
    files = []
    for pat in contract["rust_implementation"]["provenance_sources"]:
        base = pat.replace("/**", "")
        p = os.path.join(ROOT, base)
        if os.path.isdir(p):
            for dp, _, fs in sorted(os.walk(p)):
                files += [os.path.relpath(os.path.join(dp, f), ROOT) for f in sorted(fs)]
        elif os.path.isfile(p):
            files.append(base)
    rustc = subprocess.run(["/root/.cargo/bin/rustc", "-V"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    cargo = subprocess.run(["/root/.cargo/bin/cargo", "-V"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"rustc": rustc, "cargo": cargo, "cargo_lock_sha256": sha_file(os.path.join(ROOT, "Cargo.lock")),
            "source_sha256": {f: sha_file(os.path.join(ROOT, f)) for f in sorted(set(files))},
            "harness": {"path": "scripts/rust_migration/es2_env_parity.py",
                        "sha256": sha_file(os.path.abspath(__file__))},
            "binary": "target/release/abep-env-parity (cargo build --release --locked)"}


def run_campaign(key: str, mode: str, capture: bool = False) -> dict:
    contract, contract_sha, cpath = load_contract(key)
    cdir = os.path.dirname(cpath)
    report_path = os.path.join(cdir, "parity_report_v1.json")
    if mode == "score" and os.path.exists(report_path):
        sys.exit(f"REFUSED: {report_path} exists; the scoring comparison runs once per contract version")
    changed = [f["path"] for f in contract["reference_implementation"]["files"]
               if sha_file(os.path.join(ROOT, f["path"])) != f["sha256_at_registration"]]
    if changed:
        return {"verdict": "REFUSED_REFERENCE_CHANGED", "changed": changed}
    if mode == "score":
        dirty = git("status", "--porcelain", "--", "crates", "Cargo.toml", "Cargo.lock", "rust-toolchain.toml",
                    "scripts/rust_migration")
        if dirty:
            sys.exit("REFUSED: uncommitted Rust / harness sources (would be an UNRECORDED_SOURCE_CHANGE):\n" + dirty)
    seeds = contract.get("campaign_seeds", {})
    master = seeds.get("scoring_master_seed" if mode == "score" else "development_master_seed", 0)
    build_rust()
    vec_fn, py_fn, cmp_fn = SPEC[key]
    vectors = vec_fn(master)
    point_reference(None)

    t_py0 = time.perf_counter()
    py_out = {v["id"]: py_fn(v) for v in vectors}
    t_py = time.perf_counter() - t_py0
    reset_caches()
    py_out2 = {v["id"]: py_fn(v) for v in vectors}
    py_det = all(py_out[k][0] == py_out2[k][0] and equal_values(py_out[k][1], py_out2[k][1]) for k in py_out)

    reqs = [{"id": v["id"], "entry": v["entry"], "args": v["args"]} for v in vectors]
    rust, raw1, timing, wall = run_rust(reqs)
    _, raw2, _, _ = run_rust(reqs)
    rres = {r["id"]: r for r in rust["results"]}

    t = Tally()
    status_rows = []
    for v in vectors:
        ps, pv, pexc = py_out[v["id"]]
        r = rres[v["id"]]
        exp_rust = v.get("expected")
        exp_py = v.get("expected_python", exp_rust)
        row = {"vector": v["id"], "entry": v["entry"], "python": ps, "python_exception": pexc, "rust": r["status"]}
        if "divergence" in v:
            row["documented_divergence"] = v["divergence"]
            ok = ps == exp_py and r["status"] == exp_rust
        else:
            ok = ps == r["status"] and (exp_rust is None or ps == exp_rust)
        row["ok"] = ok
        if exp_rust is not None or not ok or ps != "EVALUATED":
            status_rows.append(row)
        t.exact(v["entry"], "status", r["status"], ps if "divergence" not in v else exp_rust, v["id"])
        if ps == "EVALUATED" and r["status"] == "EVALUATED" and "divergence" not in v:
            cmp_fn(t, v, r["value"], pv)

    trees = []
    if key in ("a", "d"):
        tree_list = trees_a() if key == "a" else trees_d(contract)
        for item in tree_list:
            if key == "a":
                rid, muts, exp_py, exp_rust = item
                tdir = make_tree(muts)
                try:
                    point_reference(tdir)
                    pres = {"msis21_load": py_tree_a("msis21_load")[0], "atmosphere": py_tree_a("atmosphere")[0]}
                    point_reference(None)
                    rr, _, _, _ = run_rust(tree_entries_a(), tdir)
                finally:
                    point_reference(None)
                    shutil.rmtree(tdir)
                for res in rr["results"]:
                    ok = pres[res["id"]] == exp_py and res["status"] == exp_rust
                    trees.append({"tree": rid, "entry": res["id"], "python": pres[res["id"]], "rust": res["status"],
                                  "expected_python": exp_py, "expected_rust": exp_rust, "ok": ok})
            else:
                rid, muts, exp = item
                tdir = make_tree(muts)
                try:
                    point_reference(tdir)
                    pres = {e: py_tree_outcome(e) for e in RF_ENTRIES}
                    point_reference(None)
                    rr, _, _, _ = run_rust(tree_requests_d(), tdir)
                finally:
                    point_reference(None)
                    shutil.rmtree(tdir)
                for res in rr["results"]:
                    e = res["id"]
                    ep, er = exp[e]
                    ro = rust_outcome(res)
                    ok = pres[e] == norm_registered_py(ep) and ro == er
                    trees.append({"tree": rid, "entry": e, "python": pres[e], "rust": ro,
                                  "expected_python": ep, "expected_rust": er, "ok": ok})

    gov_py = {"config_manifest_sha256": sha_file(os.path.join(ROOT, "config", "MANIFEST.json")),
              "model_set_sha256": sha_file(os.path.join(ROOT, "config", "model_set", "physics_model_set_v1.json")),
              "design_state_set_ref_sha256": sha_file(os.path.join(ROOT, "config", "environment",
                                                                   "design_state_set_ref_v1.json")),
              "design_state_set_sha256": isy.DESIGN_STATE_SET_SHA256}
    gh = contract["governing_hashes"]
    gov_ok = rust["governing"] == gov_py and gov_py["config_manifest_sha256"] == gh["config_manifest"]["sha256"]

    summ = t.summary()
    per_test_ok = summ["n_failures"] == 0 and all(r["ok"] for r in status_rows)
    tree_ok = all(x["ok"] for x in trees)
    det_ok = raw1 == raw2 and py_det
    verdict_ok = per_test_ok and tree_ok and det_ok and gov_ok
    out = {
        "contract_id": contract["id"], "contract_sha256": contract_sha, "mode": mode, "master_seed": master,
        "n_vectors": len(vectors), "per_test": summ, "status_rows": status_rows, "refusal_trees": trees,
        "determinism": {"rust_two_processes_byte_identical": raw1 == raw2,
                        "rust_stdout_sha256": hashlib.sha256(raw1).hexdigest(), "python_two_evaluations_equal": py_det},
        "governing_hashes": {"python": gov_py, "rust": rust["governing"], "equal_and_registered": gov_ok},
        "timing": {"python_reference_s": t_py, "rust_cli_wall_s": wall,
                   "rust_per_request_s_sum": sum(x["elapsed_s"] for x in timing)},
        "pass": {"per_test": per_test_ok, "refusal_trees": tree_ok, "determinism": det_ok, "governing": gov_ok,
                 "all": verdict_ok},
    }
    if mode == "score" or capture:
        out["_capture"] = {"vectors": vectors, "python": {k: [s, tojson(v), e] for k, (s, v, e) in py_out.items()},
                           "rust_raw": raw1.decode()}
        out["_timing_detail"] = timing
    return out


def perf(key, vectors_by_id):
    """Performance workloads (reported, never a criterion)."""
    res = []

    def med(fn, n=3):
        ts = []
        for _ in range(n):
            t0 = time.perf_counter()
            fn()
            ts.append(time.perf_counter() - t0)
        return statistics.median(ts), ts

    if key == "a":
        vs = [v for v in vectors_by_id if v["id"].startswith("R-A-0") or v["id"].startswith("R-A-1")]
        atm._frozen()
        py_m, py_t = med(lambda: [py_a(v) for v in vs])
        rs_m, rs_t = med(lambda: run_rust([{"id": v["id"], "entry": v["entry"], "args": v["args"]} for v in vs]))
        res.append({"id": "PERF-A-01", "python_median_s": py_m, "rust_median_s": rs_m, "python_s": py_t, "rust_s": rs_t,
                    "speedup": py_m / rs_m, "note": "Rust = one CLI process including the verified load"})
    if key == "d":
        ao.load()
        v2.load()
        py_m, py_t = med(ao.design_states_v2)
        rs_m, rs_t = med(lambda: run_rust([{"id": "x", "entry": "design_states_v2", "args": {}}]))
        res.append({"id": "PERF-D-01", "python_median_s": py_m, "rust_median_s": rs_m, "python_s": py_t,
                    "rust_s": rs_t, "speedup": py_m / rs_m,
                    "note": "Python: dataset loaded; Rust: CLI process including the verified load"})

        def py_exec():
            reset_caches()
            py_composite_execution()
        py_m, py_t = med(py_exec)
        rs_m, rs_t = med(lambda: run_rust([{"id": "x", "entry": "execution", "args": {}}]))
        res.append({"id": "PERF-D-02", "python_median_s": py_m, "rust_median_s": rs_m, "python_s": py_t,
                    "rust_s": rs_t, "speedup": py_m / rs_m, "note": "both include the verified loads"})
        vs = [v for v in vectors_by_id if v["id"].startswith("R-D-0-")]
        ao.load()
        py_m, py_t = med(lambda: [py_d(v) for v in vs])
        rs_m, rs_t = med(lambda: run_rust([{"id": v["id"], "entry": v["entry"], "args": v["args"]} for v in vs]))
        res.append({"id": "PERF-D-03", "python_median_s": py_m, "rust_median_s": rs_m, "python_s": py_t,
                    "rust_s": rs_t, "speedup": py_m / rs_m,
                    "note": "Python: dataset loaded; Rust: CLI process including the verified load"})
    return res


def write_gz_json(path, obj):
    raw = json.dumps(obj, separators=(",", ":"), allow_nan=True).encode()
    with open(path, "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", mtime=0, filename="") as g:
            g.write(raw)
    return sha_file(path)


LEDGER = {
    "a": [{"component": "C-ABEP_SIM_ATMOSPHERE_PY", "requested_status": "ADMITTED",
           "scope": "frozen-scenario reader: atmosphere (frozen branch), _interp_frozen, _frozen, orbital_velocity",
           "not_ported": "live NRLMSIS branch, ABEP_ALLOW_TABLE_ATMOSPHERE table branch, `build` (RM-OQ-02, A9.29 "
                         "sec. 6): proposed FORMALLY_RETIRED_NOT_PORTED with the module",
           "authoritative_implementation": "rust: abep_atmos::msis21 + abep_data::msis21_v1"}],
    "b": [{"component": "C-ABEP_SIM_CONSTANTS_PY", "requested_status": "ADMITTED",
           "scope": "G0, E_CHARGE, AMU, K_B, MU_EARTH, R_EARTH, M_SPECIES",
           "not_ported": "RFPConstraints / RFP: requirement data, assessment layer (RM-R14); stays with its "
                         "assessment-layer successor",
           "authoritative_implementation": "rust: abep_types::constants"}],
    "c": [{"component": "C-ABEP_SIM_MISSION_ENV_PY", "requested_status": "KERNEL_ADMITTED (RM-R17); module stays "
                                                                           "PYTHON_REFERENCE",
           "scope": "J2, OMEGA_E, Spacecraft defaults, sso_inclination_deg",
           "authoritative_implementation": "rust: abep_atmos::mission_env_kernel"}],
    "d": [{"component": "C-ABEP_SIM_ATMOSPHERE_ORBIT_PY", "requested_status": "ADMITTED",
           "scope": "load, state, node_state, orbit_states, design_states_v2, load_design_states, Domain, check "
                    "(frozen-data part)",
           "not_ported": "build / msis_points / correct-metadata / write_design_states_v2 / producer re-run (rule-1 "
                         "regeneration, live NRLMSIS: RM-OQ-02), v1 design_states() selection rule (immutable "
                         "traceability set), orbit_coverage / mission_env_orbit_assumption (metadata helpers)",
           "authoritative_implementation": "rust: abep_atmos::{orbit, design_states} + abep_data::{orbit_v1, "
                                           "design_states}"},
          {"component": "C-ABEP_SIM_ATMOSPHERE_ORBIT_V2_PY", "requested_status": "PARTIAL (load, wind, state "
                                                                                   "admitted)",
           "pending": "relative_flow, flow_state, orbit_states (v2): own contract or owner retirement before SC-WP-01 "
                      "completion", "not_ported": "HWM14Runner / build / fetch / check re-run (RM-OQ-02)",
           "authoritative_implementation": "rust: abep_atmos::wind + abep_data::hwm14_v2"},
          {"component": "C-ABEP_SIM_DESIGN_INTAKE_SYNTHESIS_PY", "requested_status": "KERNEL_ADMITTED (RM-R17) for "
                                                                                       "load_design_state_set, "
                                                                                       "DesignState.atm / record, "
                                                                                       "required_states; module stays "
                                                                                       "PYTHON_REFERENCE (SC-WP-02)",
           "authoritative_implementation": "rust: abep_data::design_states + abep_atmos::{design_state_set, "
                                           "execution}"}],
}


HARNESS_NOTE = ("harness: the contracts say the harness is committed 'after this contract and before any comparison'. It "
                "was developed with development-seed comparisons (never scored, no report) and committed before the "
                "single scoring run; every scored generator, tolerance and decision rule is the registered one. "
                "Recorded as a disclosure, not a change of the contract")
NOTES = {
    "a": [HARNESS_NOTE,
          "PYTHON_REFERENCE observation (DIV-A-03, CLAUDE.md rule 5): atmosphere() memoizes on round(alt_km, 3) but "
          "evaluates at the unrounded altitude, so a later call within 1e-3 km returns the earlier result; the harness "
          "clears _MSIS_CACHE before every reference call. For the reference's own governance; not changed here",
          "PYTHON_REFERENCE observation: when atmosphere_msis21_v1.json is missing, _frozen() stores the CSV before the "
          "JSON read fails, so a second call in the same process sees a half-filled cache and raises KeyError instead "
          "of FileNotFoundError (both fail closed); the harness evaluates every refusal-tree entry from a fresh "
          "reference state, as registered. For the reference's own governance; not changed here"],
    "b": [HARNESS_NOTE],
    "c": [HARNESS_NOTE],
    "d": [HARNESS_NOTE,
          "out of scope and still PYTHON_REFERENCE: atmosphere_orbit_v2 relative_flow / flow_state / orbit_states "
          "(not needed by the 196-state execution); SC-WP-01 admission needs their own contract or an owner "
          "retirement"],
}


def write_report(key, res, perf_rows, out_dir=None):
    contract, contract_sha, cpath = load_contract(key)
    cdir = out_dir or os.path.dirname(cpath)
    cap = res.pop("_capture")
    timing_detail = res.pop("_timing_detail")
    rdir = os.path.join(cdir, "reference_outputs")
    os.makedirs(rdir, exist_ok=True)
    man = {"schema": "abep_rust_parity_reference_outputs_v1", "contract_id": contract["id"],
           "captured_at_python_commit": contract["reference_implementation"]["python_commit"],
           "captured_at_head": git("rev-parse", "HEAD"), "files": {}}
    man["files"]["inputs.json.gz"] = write_gz_json(os.path.join(rdir, "inputs.json.gz"), cap["vectors"])
    man["files"]["python_outputs.json.gz"] = write_gz_json(os.path.join(rdir, "python_outputs.json.gz"), cap["python"])
    man["files"]["rust_outputs_at_scoring.json.gz"] = write_gz_json(os.path.join(rdir, "rust_outputs_at_scoring.json.gz"),
                                                                    json.loads(cap["rust_raw"]))
    man["format"] = ("deterministic gzip (mtime 0) of compact JSON (Python json: non-finite floats as NaN / Infinity "
                     "tokens); python_outputs: id -> [status, value, exception class]")
    with open(os.path.join(rdir, "MANIFEST.json"), "w") as f:
        json.dump(man, f, indent=1)
        f.write("\n")
    passed = res["pass"]["all"]
    report = {
        "schema": "abep_rust_parity_report_v1",
        "contract": {"id": contract["id"], "path": os.path.relpath(cpath, ROOT), "sha256": contract_sha,
                     "registration_commit": git("log", "-n1", "--format=%H", "--", os.path.relpath(cpath, ROOT))},
        "date_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python_commit": contract["reference_implementation"]["python_commit"],
        "reference_sha256": {f["path"]: {"registered": f["sha256_at_registration"],
                                         "at_scoring": sha_file(os.path.join(ROOT, f["path"]))}
                             for f in contract["reference_implementation"]["files"]},
        "rust_commit": git("rev-parse", "HEAD"),
        "build_provenance": provenance(contract),
        "environment": environment(),
        "mode": "scoring" if res["mode"] == "score" else "DEVELOPMENT (not a verdict)",
        "scoring_master_seed": res["master_seed"],
        "n_vectors": res["n_vectors"],
        "per_test": res["per_test"],
        "aggregates": "NOT_APPLICABLE (no STATISTICAL entry point)",
        "domain_error": {"vectors": res["status_rows"], "refusal_trees": res["refusal_trees"]},
        "invariants": {"determinism": res["determinism"], "governing_hashes": res["governing_hashes"]},
        "conservation": [o for o in res["per_test"]["observables"] if o["observable"].startswith("CONS-")],
        "schema": [o for o in res["per_test"]["observables"] if o["observable"] in ("key order", "list length")],
        "performance": {"status": "reported, never a decision criterion", "workloads": perf_rows,
                        "campaign_timing": res["timing"], "rust_per_request_timing_top10": sorted(
                            timing_detail, key=lambda x: -x["elapsed_s"])[:10]},
        "checks": res["pass"],
        "verdict": "ADMITTED" if passed else "NOT_ADMITTED",
        "parity_verdict": "PARITY_PASS" if passed else "PARITY_FAIL",
        "campaign_history": [{"date_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "mode": "scoring", "seed": res["master_seed"],
                              "verdict": "PARITY_PASS" if passed else "PARITY_FAIL", "executions": 1}],
        "reference_outputs": {"path": os.path.relpath(rdir, ROOT), "manifest_sha256": sha_file(
            os.path.join(rdir, "MANIFEST.json"))},
        "ledger_update_requested": LEDGER[key] if passed else [],
        "notes": NOTES[key],
        "what_this_is_not": contract["what_this_is_not"],
    }
    with open(os.path.join(cdir, "parity_report_v1.json"), "w") as f:
        json.dump(report, f, indent=1, allow_nan=False)
        f.write("\n")
    with open(os.path.join(cdir, "parity_report_v1.md"), "w") as f:
        f.write(render_md(report))
    return report


def render_md(r):
    L = [f"# Parity report v1 - {r['contract']['id']}", "",
         f"Verdict: **{r['parity_verdict']}** ({r['verdict']}). Generated from `parity_report_v1.json`.", "",
         f"* Contract: `{r['contract']['path']}` sha256 `{r['contract']['sha256']}`, registered in "
         f"`{r['contract']['registration_commit'][:12]}`.",
         f"* Python reference commit `{r['python_commit'][:12]}`; Rust commit `{r['rust_commit'][:12]}`; "
         f"{r['build_provenance']['rustc']}.",
         f"* Environment: Python {r['environment']['python']}, numpy {r['environment']['numpy']}, "
         f"{r['environment']['blas'].strip()}, {r['environment']['cpu']}.",
         f"* Master seed {r['scoring_master_seed']} ({r['mode']}); {r['n_vectors']} vectors; "
         f"{r['per_test']['n_failures']} per-test failures.", "",
         "## Checks", ""]
    L += [f"* {k}: {'pass' if v else 'FAIL'}" for k, v in r["checks"].items()]
    L += ["", "## Observables", "",
          "| entry | observable | class | n | fail | bit-identical | max abs diff | max rel diff | max ulp |",
          "|---|---|---|---|---|---|---|---|---|"]
    for o in r["per_test"]["observables"]:
        L.append(f"| {o['entry']} | {o['observable'].replace('|', '/')} | {o['tolerance_class']} | {o['n']} | "
                 f"{o['n_fail']} | {o['n_bit_identical']} | {o['max_abs_diff']:.3g} | {o['max_rel_diff']:.3g} | "
                 f"{o['max_ulp']:.3g} |")
    L += ["", "## Domain / error parity", ""]
    bad = [x for x in r["domain_error"]["vectors"] if not x["ok"]]
    L.append(f"{len(r['domain_error']['vectors'])} status-relevant vectors, {len(bad)} mismatches.")
    for x in r["domain_error"]["vectors"]:
        if "documented_divergence" in x or x["python"] != "EVALUATED":
            L.append(f"* {x['vector']} ({x['entry']}): Python {x['python']}"
                     f"{' (' + x['python_exception'] + ')' if x['python_exception'] else ''}, Rust {x['rust']}"
                     f"{', ' + x['documented_divergence'] if 'documented_divergence' in x else ''} - "
                     f"{'ok' if x['ok'] else 'MISMATCH'}")
    if r["domain_error"]["refusal_trees"]:
        L += ["", "| tree | entry | Python | Rust | registered Python | registered Rust | ok |", "|---|---|---|---|---|---|---|"]
        for x in r["domain_error"]["refusal_trees"]:
            L.append(f"| {x['tree']} | {x['entry']} | {x['python']} | {x['rust']} | {x['expected_python']} | "
                     f"{x['expected_rust']} | {'yes' if x['ok'] else 'NO'} |")
    d = r["invariants"]["determinism"]
    L += ["", "## Invariants", "",
          f"* Rust two processes byte-identical: {d['rust_two_processes_byte_identical']} (stdout sha256 "
          f"`{d['rust_stdout_sha256'][:16]}...`); Python two evaluations equal: {d['python_two_evaluations_equal']}.",
          f"* Governing hashes equal and registered: {r['invariants']['governing_hashes']['equal_and_registered']}.",
          "", "## Performance (reported, never a criterion)", ""]
    for w in r["performance"]["workloads"]:
        L.append(f"* {w['id']}: Python {w['python_median_s']:.3f} s, Rust {w['rust_median_s']:.3f} s (median of 3; "
                 f"speed-up {w['speedup']:.1f}x; {w['note']}).")
    if r["per_test"]["failures_first_50"]:
        L += ["", "## Failures (first 50)", ""] + [f"* `{json.dumps(x)[:300]}`" for x in r["per_test"]["failures_first_50"]]
    L += ["", "## Notes", ""] + [f"* {n}" for n in r["notes"]]
    L += ["", "## Ledger update requested", ""]
    L += [f"* {x['component']}: {x['requested_status']}" for x in r["ledger_update_requested"]] or ["* none"]
    L += ["", "Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.", ""]
    return "\n".join(L)


def main():
    if len(sys.argv) not in (3, 4) or sys.argv[1] not in ("dev", "dev-report", "score") or sys.argv[2] not in SPEC:
        sys.exit(__doc__)
    mode, key = sys.argv[1], sys.argv[2]
    if mode == "dev-report":
        # development seed, report pipeline exercised into a directory OUTSIDE the contract directory; not a verdict
        out_dir = os.path.abspath(sys.argv[3])
        if out_dir.startswith(CDIR):
            sys.exit("dev-report must not write into the contract directory")
        os.makedirs(out_dir, exist_ok=True)
        res = run_campaign(key, "dev", capture=True)
        rep = write_report(key, res, perf(key, res["_capture"]["vectors"]), out_dir)
        print("DEVELOPMENT REPORT (not a verdict):", rep["parity_verdict"], rep["per_test"]["n_failures"], out_dir)
        return
    res = run_campaign(key, mode)
    if res.get("verdict") == "REFUSED_REFERENCE_CHANGED":
        print(json.dumps(res, indent=1))
        sys.exit(2)
    if mode == "dev":
        for o in res["per_test"]["observables"]:
            print(f"{o['entry']:28s} {o['observable'][:52]:52s} n={o['n']:5d} fail={o['n_fail']:3d} "
                  f"bitid={o['n_bit_identical']:5d} max_ulp={o['max_ulp']:.3g} max_rel={o['max_rel_diff']:.3g}")
        for x in res["status_rows"]:
            if not x["ok"]:
                print("STATUS MISMATCH", x)
        for x in res["refusal_trees"]:
            print("TREE", x["tree"], x["entry"], x["python"], x["rust"], "ok" if x["ok"] else "MISMATCH")
        for f in res["per_test"]["failures_first_50"][:20]:
            print("FAIL", json.dumps(f)[:400])
        print(json.dumps({k: res[k] for k in ("determinism", "timing", "pass")}, indent=1))
        print("DEVELOPMENT RUN - not a verdict")
        return
    perf_rows = perf(key, res["_capture"]["vectors"])
    rep = write_report(key, res, perf_rows)
    print(rep["parity_verdict"], rep["contract"]["id"], "failures:", rep["per_test"]["n_failures"])


if __name__ == "__main__":
    main()
