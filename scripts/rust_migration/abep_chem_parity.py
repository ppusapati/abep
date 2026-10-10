#!/usr/bin/env python3
"""Parity harness of contract PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1: abep_sim/rate_tables.py (read-only Python reference)
against crates/abep-chem (CLI abep-chem-parity).

Usage:
  python3 scripts/rust_migration/abep_chem_parity.py dev [--out DIR]
      development seed; runs both sides and prints a summary. Never a verdict; writes nothing into the contract
      directory (with --out, the report pipeline writes into DIR, which must lie outside the contract directory).
  python3 scripts/rust_migration/abep_chem_parity.py score
      scoring seed, once. Refuses when parity_report_v1.json exists, a reference or input pin differs, the reference
      environment differs, or a Rust / harness provenance source is uncommitted. Writes parity_report_v1.json / .md and
      reference_outputs/ next to the contract, whatever the verdict.

Both implementations receive identical binary64 inputs (JSON shortest round-trip repr; non-finite as "NaN",
"Infinity", "-Infinity"). The Python reference runs with OMP / OpenBLAS threads 1.
"""
import os

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import argparse  # noqa: E402
import datetime  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import tomllib  # noqa: E402
from decimal import Decimal, getcontext  # noqa: E402

import numpy as np  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from abep_sim.rate_tables import maxwellian_rate, step_cross_section_rate, tail_sensitivity, write_hallthruster_table  # noqa: E402,E501

COMPONENT = "C-ABEP_SIM_RATE_TABLES_PY"
CONTRACT_DIR = os.path.join(ROOT, "docs", "rust_migration", "contracts", COMPONENT)
CONTRACT = os.path.join(CONTRACT_DIR, "parity_prereg_v1.json")
REPORT = os.path.join(CONTRACT_DIR, "parity_report_v1.json")
HARNESS_REL = "scripts/rust_migration/abep_chem_parity.py"
CLI = os.path.join(ROOT, "target", "release", "abep-chem-parity")
PROP = "hallthruster_bridge/propellants"
RATE_VALIDITY = f"{PROP}/rate_validity.toml"

# registered tolerances (contract observables / tolerance_basis)
R_REL = 1e-13
A_ABS = 1e-250
SHARE_ABS = 4e-13
STEP_ULP = 1
WRITER_ENV = {"python": "3.11.15", "numpy": "2.4.4"}
PROVENANCE_PATHS = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/abep-chem", "crates/abep-types/src"]

ION, EXC, MOM = "Ionization energy", "Excitation energy", "Momentum transfer, no inelastic energy loss"


def sha256_file(rel):
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_script(name):
    spec = importlib.util.spec_from_file_location("rtp_" + name, os.path.join(ROOT, "scripts", name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------------------------------------- registered inputs

def registered_tables():
    """TAB-01..TAB-37: each table's representation exactly as its build script passes it to write_hallthruster_table."""
    t = []
    b = load_script("build_n2_dissociation_table")
    t.append((f"{PROP}/dissociation_N2.dat", np.array([e for e, _ in b.TABLE9], float),
              np.array([s for _, s in b.TABLE9], float) * 1e-20, b.ENERGY_LOSS_EV, b.TAIL, "Dissociation energy loss"))
    b = load_script("build_n2_ionization_song2023_table")
    t.append((f"{PROP}/ionization_N2_song2023.dat", np.array([r[0] for r in b.TABLE10], float),
              np.array([r[1] for r in b.TABLE10], float) * 1e-20, b.THRESHOLD_EV, b.TAIL, ION))
    b = load_script("build_n2_elastic_song2023_table")
    t.append((f"{PROP}/elastic_N2_song2023.dat", np.array([r[0] for r in b.TABLE5], float),
              np.array([r[1] for r in b.TABLE5], float) * 1e-20, 0.0, b.TAIL, MOM))
    b = load_script("build_n2_dissociative_ionization_table")
    for v, f in b.FILES.items():
        E, s = b.cross_section(v)
        t.append((f"{PROP}/{f}", E, s, round(b.E_TH, 3), b.TAIL, ION))
    b = load_script("build_n2_to_n_z2plus_table")
    E, s = b.cross_section()
    t.append((f"{PROP}/dissociative_ionization_N2_to_N_Z2plus.dat", E, s, b.E_TH, b.TAIL, ION))
    b = load_script("build_n_z1plus_to_z2plus_table")
    E = b.grid()
    t.append((f"{PROP}/ionization_N_Z1plus_to_N_Z2plus.dat", E, b.bell_sigma_m2(E), b.HEADER_EV, b.TAIL, ION))
    b = load_script("build_n_elastic_tables")
    for v, f in b.FILES.items():
        E, s = b.cross_section(v)
        t.append((f"{PROP}/{f}", E, s, 0.0, b.TAIL, MOM))
    b = load_script("build_n2_electronic_excitation_tables")
    for key, (_, col, dE, tag) in b.STATES.items():
        E, S = b.cross_section(key)
        t.append((f"{PROP}/{b.fname(key)}", E, S, dE, "zero", EXC))
        E, S = b.cross_section(key, variant="johnsonlow")
        t.append((f"{PROP}/{b.fname(key, 'johnsonlow')}", E, S, dE, "zero", EXC))
    b = load_script("build_n2_rotational_tables")
    for col, f in b.FILES.items():
        E, s = b.cross_section(col)
        t.append((f"{PROP}/{f}", E, s, round(b.aud.ROT_DE_SPECTRO_EV[col], 7), "hold", EXC))
    b = load_script("build_multiply_charged_tables")
    for d, name, E, s, th, src in b.tables():
        rel = os.path.relpath(os.path.join(d, name), ROOT)
        t.append((rel, np.asarray(E, float), np.asarray(s, float), th, "hold", ION))
    out = []
    for i, (f, E, s, th, tail, label) in enumerate(t, 1):
        out.append({"id": f"TAB-{i:02d}", "file": f, "tail": tail, "threshold_eV": float(th), "header_label": label,
                    "eps_max": 300.0, "E_eV": [float(x) for x in np.asarray(E, float).tolist()],
                    "sigma_m2": [float(x) for x in np.asarray(s, float).tolist()]})
    return out


def representation_set_sha256(reps):
    canon = json.dumps(reps, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    return hashlib.sha256(canon).hexdigest()


EDGE_TABLES = {
    "E-01": ([0.0, 14.99, 15.0, 1000.0], [0.0, 0.0, 1e-20, 1e-20]),
    "E-02": ([15.0], [1e-20]),
    "E-03": ([15.0, 100.0], [1e-20, 2e-20]),
    "E-04": ([10.0, 30.0, 20.0, 40.0, 35.0, 50.0, 45.0, 60.0], [1e-20, 2e-20, 3e-20, 4e-20, 5e-20, 6e-20, 7e-20, 8e-20]),
    "E-05": ([10.0, 30.0, 20.0, 40.0], [1e-20, 3e-20, 2e-20, 4e-20]),
    "E-06": ([10.0, 10.0, 20.0, 20.0, 30.0], [0.0, 1e-20, 1e-20, 2e-20, 2e-20]),
    "E-07": ([0.0, 10.0, 100.0], [0.0, 0.0, 0.0]),
    "E-08": ([5.0, 50.0, 20.0], [1e-20, 3e-20, 2e-20]),
    "E-09": ([100.0, 50.0, 20.0, 10.0, 5.0], [1e-20, 2e-20, 3e-20, 4e-20, 5e-20]),
    "E-10": ([1.0, 1000000.0], [1e-19, 1e-21]),
    "E-11": ([53.885, 70.0, 1000.0], [0.0, 1e-21, 1e-20]),
    "E-12": ([60.0, 100.0], [1e-20, 1e-20]),
}
EDGE_TE = [0.01, 0.05, 0.2, 1.0, 3.0, 10.0, 30.0, 100.0, 1000.0]
EDGE_TE_E11 = [0.075, 0.08, 0.085, 0.09, 0.1, 0.2]
TE_ANCHOR = [0.2, 2.0, 30.0, 170.0, 1000.0]
TS_FIXED = [3.0, 15.0, 45.0, 90.0, 150.0, 255.0, 300.0]
ST_FIXED = [(1e-20, 15.0, 3.0), (1e-20, 15.0, 10.0), (1e-20, 15.0, 30.0)]
NAN, INF = float("nan"), float("inf")

WT_EDGE = [
    ("WT-E01", "E-01", "hold", 15.0, ION, 10.5, ""),
    ("WT-E02", "E-01", "zero", 0.0, MOM, 0.0, "s"),
    ("WT-E03", "E-01", "hold", 1e-05, EXC, 0.4, ""),
    ("WT-E04", "E-01", "hold", 1e+16, ION, -1.0, "x y"),
    ("WT-E05", "E-01", "zero", -0.0, "Dissociation energy loss", -5.0, ""),
    ("WT-E06", "E-01", "hold", 1.2345678901234568e+17, "L", 3.0, "line one\nline two"),
    ("WT-E07", "E-11", "hold", 53.885, ION, 40.0, ""),
    ("WT-E08", "E-04", "zero", 10.0, EXC, 120.0, ""),
    ("WT-E09", "E-01", "bogus", 15.0, ION, 0.0, ""),
]

STEP_E, STEP_S = EDGE_TABLES["E-01"]


def de_cases():
    """domain_and_error_parity.cases; 'div' marks the documented divergences (Rust must refuse)."""
    mr = lambda i, te, tail="hold", table="E-01", E=None, s=None, div=False: (  # noqa: E731
        i, dict({"op": "maxwellian_rate", "te": te, "tail": tail},
                **({"table": table} if E is None else {"E": E, "sigma": s})), div)
    c = [
        mr("DE-01", 3.0, "Hold"), mr("DE-02", 3.0, None), mr("DE-03", 0.0, "x"), mr("DE-04", 0.0), mr("DE-05", -1.0),
        mr("DE-06", -INF), mr("DE-07", NAN), mr("DE-08", INF), mr("DE-09", INF, "zero"), mr("DE-10", 1e-310),
        mr("DE-11", 1e-200), mr("DE-12", 1e-186), mr("DE-13", 1e-40), mr("DE-14", 1e200), mr("DE-15", 1e225),
        mr("DE-16", 1e300),
        mr("DE-17", 3.0, E=[], s=[]), mr("DE-18", 0.0, E=[], s=[]), mr("DE-19", 3.0, E=[1.0], s=[]),
        mr("DE-20", 3.0, "zero", E=[1.0], s=[]), mr("DE-21", 3.0, E=[1000.0], s=[]),
        mr("DE-22", 3.0, E=[1.0, 2.0, 1000.0], s=[1e-20, 1e-20]), mr("DE-23", 3.0, E=[1.0, 2.0], s=[1e-20, 1e-20, 1e-20]),
        mr("DE-24", 0.0, E=[1.0, 2.0, 1000.0], s=[1e-20, 1e-20]),
        mr("DE-25", 3.0, E=[0.0, NAN, 15.0, 1000.0], s=[0.0, 0.0, 1e-20, 1e-20], div=True),
        mr("DE-26", 3.0, E=[0.0, 14.99, 15.0, 1000.0], s=[0.0, 0.0, INF, 1e-20], div=True),
    ]
    for i, (s0, eth, te) in zip(["DE-S1", "DE-S2", "DE-S3", "DE-S4", "DE-S5", "DE-S6", "DE-S7", "DE-S8"],
                                [(1e-20, 15.0, 0.0), (1e-20, 15.0, -0.0), (1e-20, 15.0, -1.0), (1e-20, 15.0, NAN),
                                 (1e-20, 15.0, INF), (1e-20, 15.0, 1e-300), (1e-20, 15.0, 1e300), (1e-20, -50.0, 0.05)]):
        c.append((i, {"op": "step", "sigma0": s0, "e_th": eth, "te": te}, False))
    c.append(("DE-T1", {"op": "tail_sensitivity", "E": [], "sigma": [], "eps": [45.0]}, False))
    wt = lambda i, em, tail="hold", div=False: (i, {"op": "write_table", "table": "E-01", "tail": tail, "threshold": 15.0,  # noqa: E731
                                                    "header_label": ION, "eps_max": em, "source": ""}, div)
    c += [wt("DE-W1", NAN), wt("DE-W2", INF), wt("DE-W3", -INF), wt("DE-W4", -1e300), wt("DE-W5", 1e19),
          wt("DE-W6", 300.0, "bogus"), wt("DE-W7", 1e15, div=True)]
    return c


# ------------------------------------------------------------------------------------------------------- vectors

def draws(master, n_tables):
    te_rand, ts_rand = {}, {}
    for t in range(n_tables):
        for k, tail in enumerate(("hold", "zero")):
            rng = np.random.default_rng(np.random.SeedSequence([master, 1, t, k]))
            te_rand[(t, tail)] = [float(x) for x in np.exp(rng.uniform(math.log(0.01), math.log(1e4), 32))]
        rng = np.random.default_rng(np.random.SeedSequence([master, 2, t, 0]))
        ts_rand[t] = [float(x) for x in np.exp(rng.uniform(math.log(3.0), math.log(3000.0), 5))]
    rng = np.random.default_rng(np.random.SeedSequence([master, 3, 0, 0]))
    st = []
    for _ in range(256):
        s0 = float(math.exp(rng.uniform(math.log(1e-22), math.log(1e-18))))
        eth = float(rng.uniform(0.0, 60.0))
        te = float(math.exp(rng.uniform(math.log(0.05), math.log(1e3))))
        st.append((s0, eth, te))
    return te_rand, ts_rand, st


def build_calls(master, reps):
    """Scored calls (observables), invariant calls (INV-04, INV-06) and DE calls, in a fixed order."""
    te_rand, ts_rand, st = draws(master, len(reps))
    scored, inv = [], []
    for t, r in enumerate(reps):
        for tail in ("hold", "zero"):
            for j, te in enumerate(te_rand[(t, tail)]):
                scored.append({"id": f"MR-RAND-{r['id']}-{tail}-{j:02d}", "op": "maxwellian_rate", "table": r["id"],
                               "te": te, "tail": tail})
            for te in TE_ANCHOR:
                scored.append({"id": f"MR-ANCH-{r['id']}-{tail}-{te!r}", "op": "maxwellian_rate", "table": r["id"],
                               "te": te, "tail": tail})
    for tid, (E, s) in EDGE_TABLES.items():
        for tail in ("hold", "zero"):
            for te in (EDGE_TE_E11 if tid == "E-11" else EDGE_TE):
                scored.append({"id": f"MR-EDGE-{tid}-{tail}-{te!r}", "op": "maxwellian_rate", "table": tid, "te": te,
                               "tail": tail})
    for t, r in enumerate(reps):
        scored.append({"id": f"TS-{r['id']}", "op": "tail_sensitivity", "table": r["id"], "eps": TS_FIXED + ts_rand[t]})
    scored.append({"id": "TS-EDGE", "op": "tail_sensitivity", "table": "E-01", "eps": [0.0, -3.0, NAN, 45.0]})
    for j, (s0, eth, te) in enumerate(st):
        scored.append({"id": f"ST-RAND-{j:03d}", "op": "step", "sigma0": s0, "e_th": eth, "te": te})
    for s0, eth, te in ST_FIXED:
        scored.append({"id": f"ST-FIXED-{te!r}", "op": "step", "sigma0": s0, "e_th": eth, "te": te})
    for r in reps:
        scored.append({"id": f"WT-{r['id']}", "op": "write_table", "table": r["id"], "tail": r["tail"],
                       "threshold": r["threshold_eV"], "header_label": r["header_label"], "eps_max": r["eps_max"],
                       "source": ""})
    for i, tid, tail, th, label, em, src in WT_EDGE:
        scored.append({"id": i, "op": "write_table", "table": tid, "tail": tail, "threshold": th, "header_label": label,
                       "eps_max": em, "source": src})
    # INV-04: the other tail at every no-extension TE-RAND vector (TE-ANCHOR already has both)
    for t, r in enumerate(reps):
        emax = max(r["E_eV"])
        for tail, other in (("hold", "zero"), ("zero", "hold")):
            for j, te in enumerate(te_rand[(t, tail)]):
                if 60 * te <= emax:
                    inv.append({"id": f"INV04-{r['id']}-{tail}-{j:02d}-{other}", "op": "maxwellian_rate",
                                "table": r["id"], "te": te, "tail": other})
    # INV-06: checked API (Rust only)
    validity = tomllib.load(open(os.path.join(ROOT, RATE_VALIDITY), "rb"))
    for r in reps:
        entry = validity.get(os.path.basename(r["file"])) if r["file"].startswith(PROP + "/") else None
        if entry is None:
            inv.append({"id": f"CK-{r['id']}-missing", "op": "checked", "table": r["id"], "tail": r["tail"], "te": 2.0,
                        "validity": {"kind": "missing"}, "expect": "MODEL_ERROR"})
            continue
        if entry["status"] != "verified":
            inv.append({"id": f"CK-{r['id']}-unresolved", "op": "checked", "table": r["id"], "tail": r["tail"],
                        "te": 2.0, "validity": {"kind": "unresolved"}, "expect": "INCOMPLETE_EVIDENCE"})
            continue
        lim = float(entry["max_mean_energy_eV"])
        for te in dict.fromkeys(TE_ANCHOR + [lim / 1.5, math.nextafter(lim / 1.5, INF)]):
            ref_id = f"CKREF-{r['id']}-{te!r}"
            inv.append({"id": ref_id, "op": "maxwellian_rate", "table": r["id"], "te": te, "tail": r["tail"]})
            inv.append({"id": f"CK-{r['id']}-{te!r}", "op": "checked", "table": r["id"], "tail": r["tail"], "te": te,
                        "validity": {"kind": "verified", "max_mean_energy_ev": lim},
                        "expect": ("VALUE:" + ref_id) if 1.5 * te <= lim else "OUT_OF_DOMAIN"})
    v45 = {"kind": "verified", "max_mean_energy_ev": 45.0}
    inv.append({"id": "CK-unresolved", "op": "checked", "table": "TAB-01", "tail": "hold", "te": 2.0,
                "validity": {"kind": "unresolved"}, "expect": "INCOMPLETE_EVIDENCE"})
    for j, te in enumerate([0.0, -1.0, NAN, INF, -INF]):
        inv.append({"id": f"CK-te-{j}", "op": "checked", "table": "TAB-01", "tail": "hold", "te": te, "validity": v45,
                    "expect": "OUT_OF_DOMAIN"})
    for j, (E, s) in enumerate([([], []), ([1.0, 2.0], [1e-20]), ([1.0, NAN], [1e-20, 1e-20]), ([1.0, 2.0], [1e-20, INF]),
                                ([-1.0, 2.0], [1e-20, 1e-20]), ([1.0, 2.0], [1e-20, -1e-21]), ([2.0, 1.0], [1e-20, 1e-20])]):
        inv.append({"id": f"CK-repr-{j}", "op": "checked", "E": E, "sigma": s, "tail": "hold", "te": 2.0,
                    "validity": v45, "expect": "MODEL_ERROR"})
    de = []
    for i, call, div in de_cases():
        de.append(dict(call, id=i, div=div))
    return scored, inv, de


# --------------------------------------------------------------------------------------------------- execution

def enc(x):
    if isinstance(x, float) and not math.isfinite(x):
        return "NaN" if math.isnan(x) else ("Infinity" if x > 0 else "-Infinity")
    return x


def enc_tree(v):
    if isinstance(v, dict):
        return {k: enc_tree(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [enc_tree(x) for x in v]
    return enc(v)


def dec(x):
    if isinstance(x, str):
        return {"NaN": NAN, "Infinity": INF, "-Infinity": -INF}[x]
    return float(x)


def table_of(call, tables):
    if "E" in call:
        return np.array(call["E"], float), np.array(call["sigma"], float)
    E, s = tables[call["table"]]
    return np.array(E, float), np.array(s, float)


def py_call(call, tables, tmp):
    """Run one call through the Python reference; outcome in the CLI's shape (values already decoded)."""
    op = call["op"]
    try:
        if op == "maxwellian_rate":
            E, s = table_of(call, tables)
            return {"outcome": "value", "value": float(maxwellian_rate(E, s, float(call["te"]), call["tail"]))}
        if op == "tail_sensitivity":
            E, s = table_of(call, tables)
            return {"outcome": "value", "value": [[float(a), float(b)] for a, b in
                                                  tail_sensitivity(E, s, [float(x) for x in call["eps"]])]}
        if op == "step":
            return {"outcome": "value", "value": float(step_cross_section_rate(float(call["sigma0"]), float(call["e_th"]),
                                                                              float(call["te"])))}
        if op == "write_table":
            E, s = table_of(call, tables)
            path = os.path.join(tmp, "table.dat")
            for p in (path, path + ".source"):
                if os.path.exists(p):
                    os.remove(p)
            rows = write_hallthruster_table(path, E, s, float(call["threshold"]), eps_max=float(call["eps_max"]),
                                            source=call["source"], tail=call["tail"], header_label=call["header_label"])
            text = open(path, "rb").read().decode("utf-8")
            src = open(path + ".source", "rb").read().decode("utf-8") if os.path.exists(path + ".source") else None
            return {"outcome": "value", "value": {"rows": [[float(a), float(b)] for a, b in rows], "text": text,
                                                  "source_text": src}}
    except Exception as e:  # noqa: BLE001 -- every reference exception is an observable
        return {"outcome": "python_exception", "class": type(e).__name__, "message": str(e)}
    raise ValueError(f"no Python reference for op {op}")


def decode_rust(r, op):
    """Decode the CLI's number encoding by entry point (a render value is text, every other scalar a number)."""
    if r.get("outcome") != "value":
        return r
    v = r["value"]
    if op == "write_table":
        v = dict(v, rows=[[dec(a), dec(b)] for a, b in v["rows"]])
    elif op == "tail_sensitivity":
        v = [[dec(a), dec(b)] for a, b in v]
    elif op != "render":
        v = dec(v)
    return dict(r, value=v)


def build_cli():
    subprocess.run(["cargo", "build", "--release", "--locked", "-q", "-p", "abep-chem", "--bin", "abep-chem-parity"],
                   cwd=ROOT, check=True, env=dict(os.environ, PATH=os.environ.get("PATH", "") + ":/root/.cargo/bin"))


def rust_run(request_bytes):
    p = subprocess.run([CLI], input=request_bytes, capture_output=True, check=True)
    return p.stdout


def strip_meta(call):
    return {k: v for k, v in call.items() if k not in ("expect", "div")}


# -------------------------------------------------------------------------------------------------- comparison

def rate_ok(py, rs):
    if not (math.isfinite(py) and math.isfinite(rs)):
        return (math.isnan(py) and math.isnan(rs)) or py == rs
    d = abs(rs - py)
    return d <= R_REL * abs(py) or d <= A_ABS


def track(stats, py, rs):
    """Difference statistics of a rate pair (reported; the decision uses rate_ok)."""
    stats["rate_n"] += 1
    stats["rate_bit_identical"] += same_bits(py, rs)
    if math.isfinite(py) and math.isfinite(rs) and py != rs:
        if py != 0:
            stats["rate_max_rel"] = max(stats["rate_max_rel"], abs(rs - py) / abs(py))
        else:
            stats["rate_max_abs_where_py_zero"] = max(stats["rate_max_abs_where_py_zero"], abs(rs))


def same_bits(a, b):
    return (math.isnan(a) and math.isnan(b)) or (a == b and math.copysign(1, a) == math.copysign(1, b))


def boundary(kp):
    getcontext().prec = 1200
    d = Decimal(kp)
    tol = max(abs(d) * Decimal(R_REL), Decimal(A_ABS))
    return format(d - tol, ".6e") != format(d + tol, ".6e")


def compare_text(py_text, rs_text, py_rows, rs_rows):
    """Table text: strict except BOUNDARY_ROUNDING rate lines. Returns (ok, n_boundary, first_problem)."""
    pl, rl = py_text.split("\n"), rs_text.split("\n")
    if len(pl) != len(rl):
        return False, 0, f"line count {len(pl)} vs {len(rl)}"
    nb = 0
    for n, (a, b) in enumerate(zip(pl, rl)):
        if a == b:
            continue
        i = n - 2
        if n < 2 or not (0 <= i < len(py_rows)) or a.split("\t")[0] != b.split("\t")[0]:
            return False, nb, f"line {n}: {a!r} vs {b!r}"
        kp, kr = py_rows[i][1], rs_rows[i][1]
        if boundary(kp) and rate_ok(kp, kr) and b == f"{rs_rows[i][0]:.1f}\t{kr:.6e}":
            nb += 1
        else:
            return False, nb, f"line {n}: {a!r} vs {b!r}"
    return True, nb, None


def compare(call, py, rs, stats):
    """Per-test comparison under the registered tolerance classes; returns (ok, detail)."""
    if py["outcome"] != rs["outcome"]:
        return False, f"outcome {py['outcome']} vs {rs['outcome']}"
    if py["outcome"] == "python_exception":
        ok = (py["class"], py["message"]) == (rs["class"], rs["message"])
        return ok, None if ok else f"{py['class']}: {py['message']} vs {rs['class']}: {rs['message']}"
    op, pv, rv = call["op"], py["value"], rs["value"]
    if op == "maxwellian_rate":
        track(stats, pv, rv)
        return rate_ok(pv, rv), None if rate_ok(pv, rv) else f"{pv!r} vs {rv!r}"
    if op == "step":
        ok = (same_bits(pv, rv) if not (math.isfinite(pv) and math.isfinite(rv))
              else abs(rv - pv) <= STEP_ULP * math.ulp(pv))
        stats["step_bit_identical"] += same_bits(pv, rv)
        stats["step_n"] += 1
        return ok, None if ok else f"{pv!r} vs {rv!r}"
    if op == "tail_sensitivity":
        if len(pv) != len(rv):
            return False, f"length {len(pv)} vs {len(rv)}"
        for (pe, ps), (re_, rs_) in zip(pv, rv):
            if not same_bits(pe, re_):
                return False, f"eps {pe!r} vs {re_!r}"
            if math.isfinite(ps) and math.isfinite(rs_):
                stats["share_max_abs"] = max(stats["share_max_abs"], abs(rs_ - ps))
                if abs(rs_ - ps) > SHARE_ABS:
                    return False, f"share {ps!r} vs {rs_!r}"
            elif not same_bits(ps, rs_):
                return False, f"share {ps!r} vs {rs_!r}"
        return True, None
    if op == "write_table":
        if len(pv["rows"]) != len(rv["rows"]):
            return False, f"n_rows {len(pv['rows'])} vs {len(rv['rows'])}"
        for (pe, pk), (re_, rk) in zip(pv["rows"], rv["rows"]):
            if not same_bits(pe, re_):
                return False, f"row eps {pe!r} vs {re_!r}"
            track(stats, pk, rk)
            if not rate_ok(pk, rk):
                return False, f"row k {pk!r} vs {rk!r} at eps {pe!r}"
        ok, nb, why = compare_text(pv["text"], rv["text"], pv["rows"], rv["rows"])
        stats["boundary_rounding_lines"] += nb
        stats["text_identical"] += pv["text"] == rv["text"]
        if not ok:
            return False, why
        if pv["source_text"] != rv["source_text"]:
            return False, f"sidecar {pv['source_text']!r} vs {rv['source_text']!r}"
        return True, None
    return False, f"no comparison for op {op}"


# ------------------------------------------------------------------------------------------------------ campaign

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def environment():
    from numpy._core._multiarray_umath import __cpu_baseline__, __cpu_dispatch__, __cpu_features__
    return {"python": platform.python_version(), "numpy": np.__version__,
            "numpy_simd_baseline": list(__cpu_baseline__), "numpy_simd_dispatch": list(__cpu_dispatch__),
            "numpy_avx512_skx_available": bool(__cpu_features__.get("AVX512_SKX")),
            "cpu": next((ln.split(":", 1)[1].strip() for ln in open("/proc/cpuinfo") if ln.startswith("model name")), "?"),
            "platform": platform.platform(), "glibc": "-".join(platform.libc_ver()),
            "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
            "requirements_lock_sha256": sha256_file("requirements-lock.txt")}


def provenance_files():
    out = {}
    for p in PROVENANCE_PATHS + [HARNESS_REL]:
        full = os.path.join(ROOT, p)
        if os.path.isdir(full):
            for d, _, fs in sorted(os.walk(full)):
                for f in sorted(fs):
                    rel = os.path.relpath(os.path.join(d, f), ROOT)
                    out[rel] = sha256_file(rel)
        else:
            out[p] = sha256_file(p)
    return dict(sorted(out.items()))


def check_pins(contract, reps):
    problems = []
    for f in contract["reference_implementation"]["files"]:
        if sha256_file(f["path"]) != f["sha256_at_registration"]:
            problems.append(("REFUSED_REFERENCE_CHANGED", f["path"]))
    for p, h in contract["pinned_inputs_sha256"].items():
        if os.path.exists(os.path.join(ROOT, p)) and sha256_file(p) != h:
            problems.append(("INPUT_MISMATCH", p))
    for t in contract["inputs"]["registered_tables"]["tables"]:
        if sha256_file(t["file"]) != t["sha256"]:
            problems.append(("INPUT_MISMATCH", t["file"]))
    if representation_set_sha256(reps) != contract["governing_hashes"]["representation_set_sha256"]:
        problems.append(("INPUT_MISMATCH", "representation_set_sha256"))
    if sha256_file("config/MANIFEST.json") != contract["governing_hashes"]["config_manifest"]["sha256"]:
        problems.append(("INPUT_MISMATCH", "config/MANIFEST.json"))
    return problems


def run_campaign(master):
    contract = json.load(open(CONTRACT))
    reps = registered_tables()
    pin_problems = check_pins(contract, reps)
    tables = {r["id"]: (r["E_eV"], r["sigma_m2"]) for r in reps}
    tables.update({k: (list(E), list(s)) for k, (E, s) in EDGE_TABLES.items()})
    scored, inv, de = build_calls(master, reps)
    py_calls = [c for c in scored + inv + de if c["op"] != "checked"]
    tmp = tempfile.mkdtemp(prefix="abep_chem_parity_")
    try:
        t0 = time.perf_counter()
        py_out = {c["id"]: py_call(strip_meta(c), tables, tmp) for c in py_calls}
        py_seconds = time.perf_counter() - t0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # render-only calls from Python's successful tables
    render = []
    for c in scored:
        if c["op"] == "write_table" and py_out[c["id"]]["outcome"] == "value":
            render.append({"id": "RD-" + c["id"], "op": "render", "threshold": c["threshold"],
                           "header_label": c["header_label"], "rows": py_out[c["id"]]["value"]["rows"]})
    all_calls = scored + inv + de + render
    request = {"tables": {k: {"E": E, "sigma": s} for k, (E, s) in tables.items()},
               "calls": [strip_meta(c) for c in all_calls]}
    request_bytes = json.dumps(enc_tree(request), separators=(",", ":"), allow_nan=False).encode()
    t0 = time.perf_counter()
    out1 = rust_run(request_bytes)
    rust_seconds = time.perf_counter() - t0
    out2 = rust_run(request_bytes)
    rs_raw = json.loads(out1)["results"]
    ops = {c["id"]: c["op"] for c in all_calls}
    rs_out = {r["id"]: decode_rust(r, ops[r["id"]]) for r in rs_raw}

    stats = {"rate_max_rel": 0.0, "rate_max_abs_where_py_zero": 0.0, "rate_bit_identical": 0, "rate_n": 0,
             "step_bit_identical": 0, "step_n": 0, "share_max_abs": 0.0, "boundary_rounding_lines": 0,
             "text_identical": 0}
    per_test, failures = {}, []
    for c in scored:
        ok, why = compare(c, py_out[c["id"]], rs_out[c["id"]], stats)
        entry = per_test.setdefault(c["op"], {"n": 0, "passed": 0})
        entry["n"] += 1
        entry["passed"] += ok
        if not ok:
            failures.append({"id": c["id"], "detail": why})
    rd = {"n": 0, "passed": 0}
    for c in render:
        rd["n"] += 1
        ok = rs_out[c["id"]]["outcome"] == "value" and rs_out[c["id"]]["value"] == py_out[c["id"][3:]]["value"]["text"]
        rd["passed"] += ok
        if not ok:
            failures.append({"id": c["id"], "detail": "rendered text differs"})
    per_test["render"] = rd

    # domain / error parity
    de_rows = []
    for c in de:
        p, r = py_out[c["id"]], rs_out[c["id"]]
        if c["div"]:
            ok = r["outcome"] == "refused" and r["status"] == "OUT_OF_DOMAIN"
        else:
            ok, _ = compare(c, p, r, dict(stats)) if p["outcome"] == r["outcome"] == "value" else (
                p["outcome"] == r["outcome"] and (p.get("class"), p.get("message")) == (r.get("class"), r.get("message")),
                None)
        py_view = {k: v for k, v in p.items() if k != "value"}
        if p["outcome"] == "value" and not isinstance(p["value"], (dict, list)):
            py_view["value"] = repr(p["value"])
        rs_view = {k: v for k, v in r.items() if k not in ("value", "id")}
        if r["outcome"] == "value" and not isinstance(r["value"], (dict, list)):
            rs_view["value"] = repr(r["value"])
        de_rows.append({"id": c["id"], "documented_divergence": c["div"], "python": py_view, "rust": rs_view,
                        "pass": bool(ok)})
        if not ok:
            failures.append({"id": c["id"], "detail": f"python {py_view} rust {rs_view}"})

    # invariants
    inv_res = {}
    inv_res["INV-01"] = {"pass": out1 == out2, "statement": "two Rust CLI runs byte-identical",
                         "stdout_sha256": hashlib.sha256(out1).hexdigest()}
    reg_ok = []
    for r in reps:
        pv = py_out[f"WT-{r['id']}"]
        text_sha = hashlib.sha256(pv["value"]["text"].encode()).hexdigest() if pv["outcome"] == "value" else None
        reg_ok.append(text_sha == sha256_file(r["file"]))
    inv_res["INV-02"] = {"pass": all(reg_ok), "n": len(reg_ok), "reproduced": sum(reg_ok),
                         "statement": "Python reproduces every frozen table byte for byte (input precondition)"}
    i3 = []
    for te in (3.0, 10.0, 30.0):
        for side, out in (("python", py_out), ("rust", rs_out)):
            k = out[f"MR-EDGE-E-01-hold-{te!r}"]["value"]
            ks = out[f"ST-FIXED-{te!r}"]["value"]
            i3.append({"te": te, "side": side, "ratio_minus_1": k / ks - 1, "pass": abs(k / ks - 1) < 0.01})
    inv_res["INV-03"] = {"pass": all(x["pass"] for x in i3), "rows": i3}
    i4n, i4ok = 0, True
    for c in inv:
        if not c["id"].startswith("INV04-"):
            continue
        base = c["id"][len("INV04-"):].rsplit("-", 1)[0]
        tid, tail, j = base.rsplit("-", 2)
        src = f"MR-RAND-{tid}-{tail}-{j}"
        for out in (py_out, rs_out):
            i4n += 1
            i4ok &= same_bits(out[src]["value"], out[c["id"]]["value"])
    for r in reps:
        emax = max(r["E_eV"])
        for te in TE_ANCHOR:
            if 60 * te <= emax:
                for out in (py_out, rs_out):
                    i4n += 1
                    i4ok &= same_bits(out[f"MR-ANCH-{r['id']}-hold-{te!r}"]["value"],
                                      out[f"MR-ANCH-{r['id']}-zero-{te!r}"]["value"])
    inv_res["INV-04"] = {"pass": bool(i4ok) and i4n > 0, "pairs_checked": i4n}
    i5n, i5ok = 0, True
    for c in scored:
        for side, out in (("python", py_out), ("rust", rs_out)):
            o = out[c["id"]]
            if o["outcome"] != "value":
                continue
            vals = ([o["value"]] if c["op"] == "maxwellian_rate" else
                    [k for _, k in o["value"]["rows"]] if c["op"] == "write_table" else [])
            for v in vals:
                if math.isfinite(v):
                    i5n += 1
                    i5ok &= v >= 0
    inv_res["INV-05"] = {"pass": bool(i5ok), "values_checked": i5n}
    i6, i6ok = 0, True
    i6_fail = []
    for c in inv:
        if c["op"] != "checked":
            continue
        r = rs_out[c["id"]]
        exp = c["expect"]
        if exp.startswith("VALUE:"):
            ok = r["outcome"] == "value" and same_bits(r["value"], rs_out[exp[6:]]["value"])
        else:
            ok = r["outcome"] == "refused" and r["status"] == exp
        i6 += 1
        i6ok &= ok
        if not ok:
            i6_fail.append({"id": c["id"], "expect": exp, "rust": {k: v for k, v in r.items() if k != "id"}})
    inv_res["INV-06"] = {"pass": bool(i6ok), "checks": i6, "failures": i6_fail}
    for k in ("INV-01", "INV-03", "INV-04", "INV-05", "INV-06"):
        if not inv_res[k]["pass"]:
            failures.append({"id": k, "detail": "invariant failed"})

    return {"contract": contract, "reps": reps, "pin_problems": pin_problems, "request": request,
            "request_bytes": request_bytes, "py_out": py_out, "rs_stdout": out1, "per_test": per_test,
            "failures": failures, "de": de_rows, "invariants": inv_res, "stats": stats,
            "timing": {"python_reference_all_calls_s": py_seconds, "rust_cli_all_calls_s": rust_seconds},
            "counts": {"scored": len(scored), "invariant_calls": len(inv), "de": len(de), "render": len(render)}}


def performance(reps, repeats=3):
    tables = {r["id"]: (r["E_eV"], r["sigma_m2"]) for r in reps}
    calls = [{"id": f"WT-{r['id']}", "op": "write_table", "table": r["id"], "tail": r["tail"],
              "threshold": r["threshold_eV"], "header_label": r["header_label"], "eps_max": r["eps_max"], "source": ""}
             for r in reps]
    req = json.dumps(enc_tree({"tables": {k: {"E": E, "sigma": s} for k, (E, s) in tables.items()}, "calls": calls}),
                     separators=(",", ":"), allow_nan=False).encode()
    py_t, rs_t = [], []
    tmp = tempfile.mkdtemp(prefix="abep_chem_perf_")
    try:
        for _ in range(repeats):
            t0 = time.perf_counter()
            for c in calls:
                py_call(c, tables, tmp)
            py_t.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            rust_run(req)
            rs_t.append(time.perf_counter() - t0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    mp, mr = sorted(py_t)[len(py_t) // 2], sorted(rs_t)[len(rs_t) // 2]
    return {"workload": "PERF-WT", "repeats": repeats, "python_s": py_t, "rust_s": rs_t, "median_python_s": mp,
            "median_rust_s": mr, "speed_up": mp / mr, "status": "reported, not a decision criterion"}


def summary(res):
    print("counts", res["counts"])
    for op, v in res["per_test"].items():
        print(f"  {op:18s} {v['passed']}/{v['n']}")
    print("  DE", sum(r["pass"] for r in res["de"]), "/", len(res["de"]))
    for k, v in res["invariants"].items():
        print(f"  {k} pass={v['pass']}")
    print("stats", res["stats"])
    print("pin problems", res["pin_problems"])
    print("failures", len(res["failures"]), res["failures"][:10])


def gz(obj):
    return gzip.compress(json.dumps(obj, separators=(",", ":"), allow_nan=False, sort_keys=True).encode(), mtime=0)


def write_outputs(res, outdir, mode, master, env, perf, verdict, parity, contract_sha, reg_commit, rust_commit):
    os.makedirs(os.path.join(outdir, "reference_outputs"), exist_ok=True)
    files = {
        "inputs.json.gz": gz({"contract": "PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1", "registered_tables": res["reps"],
                              "request": enc_tree(res["request"])}),
        "python_outputs.json.gz": gz(enc_tree(res["py_out"])),
        "rust_outputs_at_scoring.json.gz": gzip.compress(res["rs_stdout"], mtime=0),
    }
    ref_commit = json.load(open(CONTRACT))["reference_implementation"]["python_commit"]
    manifest = {"contract": "PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1", "captured_at_python_commit": ref_commit,
                "repository_head_at_capture": git("rev-parse", "HEAD"),
                "python_reference": "abep_sim/rate_tables.py sha256 " + sha256_file("abep_sim/rate_tables.py"),
                "files": {}}
    for name, data in files.items():
        with open(os.path.join(outdir, "reference_outputs", name), "wb") as fh:
            fh.write(data)
        manifest["files"][name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    manifest["note"] = ("inputs: registered representations and the full request (non-finite numbers as strings); "
                        "python_outputs: outcome per call id; rust_outputs_at_scoring: the CLI stdout of the scoring run")
    with open(os.path.join(outdir, "reference_outputs", "MANIFEST.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    toolchain = {k: subprocess.run([k, "--version"], capture_output=True, text=True,
                                   env=dict(os.environ, PATH=os.environ.get("PATH", "") + ":/root/.cargo/bin")).stdout.strip()
                 for k in ("rustc", "cargo")}
    report = {
        "schema": "abep_rust_parity_report_v3_1",
        "contract": {"id": "PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1",
                     "path": os.path.relpath(CONTRACT, ROOT), "sha256": contract_sha, "registration_commit": reg_commit},
        "date_utc": now,
        "mode": mode,
        "contract_sha256": contract_sha,
        "python_commit": ref_commit,
        "python_commit_note": "registered reference commit; the reference file is unchanged at the repository head of "
                              "the run (reference_sha256 equals sha256_at_registration, checked before any call)",
        "repository_head_at_run": git("rev-parse", "HEAD"),
        "reference_sha256": {"abep_sim/rate_tables.py": sha256_file("abep_sim/rate_tables.py")},
        "rust_commit": rust_commit,
        "rust_sources_last_changed_in": git("log", "-1", "--format=%H", "--", "crates/abep-chem", "Cargo.lock"),
        "build_provenance": dict(toolchain, cargo_lock_sha256=sha256_file("Cargo.lock"), source_sha256=provenance_files()),
        "environment": env,
        "scoring_master_seed": master,
        "n_vectors": res["counts"],
        "pins": {"problems": res["pin_problems"], "representation_set_sha256": representation_set_sha256(res["reps"])},
        "per_test": res["per_test"],
        "statistics": res["stats"],
        "aggregates": "NOT_APPLICABLE (no STATISTICAL entry point)",
        "domain_error": res["de"],
        "invariants": res["invariants"],
        "conservation": "NOT_APPLICABLE (contract conservation_checks.applicable = false)",
        "schema": {"render_exact_bytes": res["per_test"]["render"], "table_text": {
            "identical": res["stats"]["text_identical"], "boundary_rounding_lines": res["stats"]["boundary_rounding_lines"]}},
        "performance": perf,
        "timing_full_campaign": res["timing"],
        "failures": res["failures"],
        "verdict": verdict,
        "parity_verdict": parity,
        "campaign_history": [{"date_utc": now, "mode": mode, "seed": master, "verdict": parity, "executions": 1}],
        "reference_outputs": {"path": os.path.relpath(os.path.join(outdir, "reference_outputs"), ROOT),
                              "manifest": manifest["files"]},
        "ledger_update_requested": [],
        "what_this_is_not": json.load(open(CONTRACT))["what_this_is_not"],
    }
    if verdict == "ADMITTED":
        report["ledger_update_requested"] = [{
            "component": COMPONENT, "requested_status": "ADMITTED",
            "scope": "maxwellian_rate (tails hold / zero), tail_sensitivity, step_cross_section_rate, "
                     "write_hallthruster_table (rows, table text, sidecar text; file I/O excluded)",
            "authoritative_implementation": "rust: abep_chem::reference (parity behaviour, table rebuilds) and "
                                            "abep_chem::checked (fail-closed production API, IF-CHEM-REG-v1)",
            "contract": "PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1",
            "downstream": "NP-ICP-NEUTRALIZER prereg_v1 software_admission item (3) 'the abep-chem rate evaluator it "
                          "uses is admitted' is satisfied by this admission (verification_report_v1 admission item 3 / "
                          "NV-06 direct side can be evaluated once abep-icp is wired to abep_chem::checked by its own lane); "
                          "no table, registry or validity entry is admitted by it"}]
    with open(os.path.join(outdir, "parity_report_v1.json"), "w") as fh:
        json.dump(report, fh, indent=1, allow_nan=False)
        fh.write("\n")
    with open(os.path.join(outdir, "parity_report_v1.md"), "w") as fh:
        fh.write(markdown(report))
    return report


def markdown(r):
    s = r["statistics"]
    lines = [
        f"# Parity report v1: {r['contract']['id']}",
        "",
        f"**Verdict: {r['verdict']} ({r['parity_verdict']})**, mode `{r['mode']}`, seed {r['scoring_master_seed']}, "
        f"{r['date_utc']}.",
        "",
        f"- Contract `{r['contract']['path']}`, sha256 `{r['contract']['sha256']}`, registered at "
        f"`{r['contract']['registration_commit']}`.",
        f"- Python reference `abep_sim/rate_tables.py` sha256 `{r['reference_sha256']['abep_sim/rate_tables.py']}` at "
        f"`{r['python_commit']}`; Python {r['environment']['python']}, numpy {r['environment']['numpy']} "
        f"(AVX512_SKX {r['environment']['numpy_avx512_skx_available']}).",
        f"- Rust `crates/abep-chem` at `{r['rust_commit']}`; {r['build_provenance']['rustc']}.",
        "",
        "## Per-test results",
        "",
        "| entry point | passed / scored |",
        "|---|---|",
    ]
    for op, v in r["per_test"].items():
        lines.append(f"| {op} | {v['passed']} / {v['n']} |")
    lines += [
        "",
        f"- Rate values compared: {s['rate_n']}; bit-identical {s['rate_bit_identical']}; max relative difference "
        f"{s['rate_max_rel']:.3e} (registered bound 1e-13 or 1e-250 m^3/s); largest |Rust| where Python is 0: "
        f"{s['rate_max_abs_where_py_zero']:.3e} m^3/s.",
        f"- step_cross_section_rate: {s['step_bit_identical']} / {s['step_n']} bit-identical (bound 1 ulp).",
        f"- tail_sensitivity share: max |difference| {s['share_max_abs']:.3e} (bound 4e-13).",
        f"- Table texts identical: {s['text_identical']}; BOUNDARY_ROUNDING lines: {s['boundary_rounding_lines']}.",
        "",
        "## Domain / error parity",
        "",
        "| case | divergence | Python | Rust | pass |",
        "|---|---|---|---|---|",
    ]
    for d in r["domain_error"]:
        fmt = lambda o: (f"{o.get('class')}: {o.get('message')}" if o["outcome"] == "python_exception" else  # noqa: E731
                         f"refused {o.get('status')}" if o["outcome"] == "refused" else f"value {o.get('value', '')}")
        lines.append(f"| {d['id']} | {'DIV' if d['documented_divergence'] else '-'} | {fmt(d['python'])} | "
                     f"{fmt(d['rust'])} | {d['pass']} |")
    lines += ["", "## Invariants", ""]
    for k, v in r["invariants"].items():
        extra = {kk: vv for kk, vv in v.items() if kk not in ("pass", "rows", "failures", "statement")}
        lines.append(f"- {k}: {'pass' if v['pass'] else 'FAIL'} {json.dumps(extra)}")
    p = r["performance"]
    lines += ["", "## Performance (reported, not a criterion)", "",
              f"PERF-WT (37 tables x 301 rows): median Python {p['median_python_s']:.2f} s, Rust {p['median_rust_s']:.2f} s "
              f"(CLI incl. start-up), speed-up {p['speed_up']:.1f}x.", ""]
    if r["failures"]:
        lines += ["## Failures", ""] + [f"- {f['id']}: {f['detail']}" for f in r["failures"][:50]] + [""]
    lines += ["## Ledger update requested", ""]
    lines += [f"- {json.dumps(x)}" for x in r["ledger_update_requested"]] or ["- none"]
    lines += ["", "## What this is not", ""] + [f"- {x}" for x in r["what_this_is_not"]] + [""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["dev", "score"])
    ap.add_argument("--out", help="dev mode: write the report pipeline into this directory (outside the contract dir)")
    a = ap.parse_args()
    contract = json.load(open(CONTRACT))
    seeds = contract["campaign_seeds"]
    env = environment()
    if a.mode == "score":
        if os.path.exists(REPORT):
            sys.exit("refused: parity_report_v1.json exists (score once)")
        dirty = git("status", "--porcelain", "--", *PROVENANCE_PATHS, HARNESS_REL, os.path.relpath(CONTRACT, ROOT))
        if dirty:
            sys.exit("refused: uncommitted Rust / harness / contract sources:\n" + dirty)
        if env["python"] != WRITER_ENV["python"] or env["numpy"] != WRITER_ENV["numpy"] or not env["numpy_avx512_skx_available"]:
            sys.exit(f"INPUT_MISMATCH: reference environment {env}")
        master = seeds["scoring_master_seed"]
    else:
        master = seeds["development_master_seed"]
        if a.out and os.path.abspath(a.out).startswith(CONTRACT_DIR):
            sys.exit("dev --out must lie outside the contract directory")
    build_cli()
    res = run_campaign(master)
    summary(res)
    if res["pin_problems"]:
        kinds = {k for k, _ in res["pin_problems"]}
        verdict = "REFUSED_REFERENCE_CHANGED" if "REFUSED_REFERENCE_CHANGED" in kinds else "INPUT_MISMATCH"
        print("verdict", verdict, "(not scored)")
        if a.mode == "score":
            sys.exit(1)
    if not res["invariants"]["INV-02"]["pass"]:
        print("INPUT_MISMATCH: INV-02 representation identity failed")
        if a.mode == "score":
            sys.exit(1)
    parity = "PARITY_PASS" if not res["failures"] else "PARITY_FAIL"
    verdict = "ADMITTED" if parity == "PARITY_PASS" else "NOT_ADMITTED"
    if a.mode == "dev" and not a.out:
        print(f"development run (seed {master}): {parity} -- never a verdict")
        return
    perf = performance(res["reps"])
    contract_sha = hashlib.sha256(open(CONTRACT, "rb").read()).hexdigest()
    reg_commit = git("log", "--diff-filter=A", "--format=%H", "--", os.path.relpath(CONTRACT, ROOT))
    rust_commit = git("rev-parse", "HEAD")
    outdir = CONTRACT_DIR if a.mode == "score" else a.out
    mode = "scoring" if a.mode == "score" else "development"
    if mode == "development":
        verdict, parity = "NOT_A_VERDICT (development seed)", f"DEVELOPMENT_{parity}"
    report = write_outputs(res, outdir, mode, master, env, perf, verdict, parity, contract_sha, reg_commit, rust_commit)
    print(f"{mode}: {report['verdict']} ({report['parity_verdict']}) -> {os.path.relpath(outdir, ROOT)}")


if __name__ == "__main__":
    main()
