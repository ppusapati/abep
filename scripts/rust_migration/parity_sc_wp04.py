#!/usr/bin/env python3
"""SC-WP-04 parity harness (spacecraft interaction: reference spacecraft drag, statewise quantifier, record builder,
intake-drag / T - D kernel).

Implements the vector generators, reference calls, tolerance classes and decision rules registered in

* docs/rust_migration/contracts/C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY/parity_prereg_v1.json                  (a)
* docs/rust_migration/contracts/C-ABEP_SIM_STATEWISE_PY/parity_prereg_v1.json                                  (b)
* docs/rust_migration/contracts/C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG/parity_prereg_v1.json       (c)
* docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL/parity_prereg_v1.json (d)

The Python reference is called read-only; the Rust side is the abep-mission binaries (abep-mission-parity,
abep-reference-drag-record). Case trees live in a scratch directory; the repository is never modified.

    python3 scripts/rust_migration/parity_sc_wp04.py dev   a|b|c|d   # development seed; never a verdict; writes nothing
    python3 scripts/rust_migration/parity_sc_wp04.py score a|b|c|d   # scoring seed, ONCE: report + captured references

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

for _k in ("ABEP_ATMOSPHERE", "ABEP_ALLOW_TABLE_ATMOSPHERE"):
    os.environ.pop(_k, None)

import copy  # noqa: E402
import datetime  # noqa: E402
import gzip  # noqa: E402
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
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_common as C  # noqa: E402

ROOT = C.ROOT
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402

from abep_sim import spacecraft_reference_drag as SRD  # noqa: E402
from abep_sim import statewise as SW  # noqa: E402
from abep_sim.design import architecture_optimizer as ao  # noqa: E402
from abep_sim.design import intake_synthesis as isy  # noqa: E402

CDIR = ROOT / "docs" / "rust_migration" / "contracts"
CONTRACT_DIRS = {"a": "C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY", "b": "C-ABEP_SIM_STATEWISE_PY",
                 "c": "C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG",
                 "d": "C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL"}
BIN_PARITY = ROOT / "target" / "release" / "abep-mission-parity"
BIN_RECORD = ROOT / "target" / "release" / "abep-reference-drag-record"
RUST_SOURCES = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/abep-types/src/**",
                "crates/abep-provenance/src/lib.rs", "crates/abep-data/src/**", "crates/abep-atmos/src/**",
                "crates/abep-mission/Cargo.toml", "crates/abep-mission/src/**", "crates/abep-mission/data/**"]
BUILDER_REL = "docs/design_synthesis/spacecraft_reference_drag/build_spacecraft_reference_drag.py"
OUT_JSON_REL = "docs/design_synthesis/spacecraft_reference_drag/spacecraft_reference_drag_v1.json"
OUT_MD_REL = "docs/design_synthesis/spacecraft_reference_drag/SPACECRAFT_REFERENCE_DRAG.md"
DS_ID = "atmosphere_msis21_orbit_v1_design_states_v2"
DS_SHA = "60073e214cf5edb92d7eacf70be1491ad29ff72f19db0ef3b96a4b30da6f4049"
EXC = {"RuntimeError": RuntimeError, "ValueError": ValueError, "ZeroDivisionError": ZeroDivisionError}


# ----------------------------------------------------------------------------------------------------------------------
# transport, Python calls, Rust calls
# ----------------------------------------------------------------------------------------------------------------------
def enc(v):
    if isinstance(v, float) and not math.isfinite(v):
        return "NaN" if math.isnan(v) else ("+inf" if v > 0 else "-inf")
    if isinstance(v, dict):
        return {k: enc(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [enc(x) for x in v]
    return v


def norm(v):
    """JSON-normal form of a Python value (tuples -> lists), non-finite floats as transport strings."""
    return json.loads(json.dumps(enc(v), allow_nan=False))


def py_call(fn, *a, **kw) -> dict:
    try:
        v = fn(*a, **kw)
    except Exception as e:  # noqa: BLE001 - every exception class is an observable
        return {"outcome": "RAISED", "class": type(e).__name__, "message": str(e)}
    return {"outcome": "RETURNED", "value": norm(v)}


def cargo_env() -> dict:
    return dict(os.environ, PATH=f"/root/.cargo/bin:{os.environ.get('PATH', '')}", CARGO_INCREMENTAL="0",
                CARGO_PROFILE_DEV_DEBUG="0")


def build_rust() -> None:
    subprocess.run(["cargo", "build", "--release", "--locked", "-p", "abep-mission", "--bins"], cwd=ROOT, check=True,
                   env=cargo_env(), capture_output=True)


def run_rust(requests: list, repo_root: Path = ROOT) -> tuple[list, bytes, float]:
    payload = json.dumps({"repo_root": str(repo_root), "requests": requests}, ensure_ascii=False,
                         allow_nan=False).encode()
    t0 = time.perf_counter()
    p = subprocess.run([str(BIN_PARITY)], input=payload, capture_output=True, check=True)
    wall = time.perf_counter() - t0
    return json.loads(p.stdout)["results"], p.stdout, wall


def rng(master: int, entry: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([master, entry]))


# ----------------------------------------------------------------------------------------------------------------------
# comparison (tolerance classes of the contracts)
# ----------------------------------------------------------------------------------------------------------------------
def bits(x: float) -> int:
    return struct.unpack("<q", struct.pack("<d", x))[0]


class Stats:
    def __init__(self):
        self.d = {}

    def add(self, key, py, rs, ok):
        s = self.d.setdefault(key, {"n": 0, "fail": 0, "bit_identical": 0, "max_abs_diff": 0.0, "max_rel_diff": 0.0,
                                    "max_ulp": 0.0})
        s["n"] += 1
        s["fail"] += 0 if ok else 1
        if isinstance(py, float) and isinstance(rs, float):
            if bits(py) == bits(rs):
                s["bit_identical"] += 1
            d = abs(rs - py)
            s["max_abs_diff"] = max(s["max_abs_diff"], d)
            if py != 0.0:
                s["max_rel_diff"] = max(s["max_rel_diff"], d / abs(py))
            s["max_ulp"] = max(s["max_ulp"], d / math.ulp(py))
        elif py == rs:
            s["bit_identical"] += 1


def walk(py, rs, rules: dict, path: tuple, entry: str, stats: Stats, diffs: list):
    """EXACT_VALUE everywhere (types, keys, order, bit-equal floats) except the registered ULP paths."""
    if type(py) is not type(rs):
        diffs.append(f"{'/'.join(path)}: type {type(py).__name__} != {type(rs).__name__} (py {py!r} rust {rs!r})")
        return
    if isinstance(py, dict):
        if list(py) != list(rs):
            diffs.append(f"{'/'.join(path)}: keys {list(py)} != {list(rs)}")
            return
        for k in py:
            walk(py[k], rs[k], rules, path + (k,), entry, stats, diffs)
        return
    if isinstance(py, list):
        if len(py) != len(rs):
            diffs.append(f"{'/'.join(path)}: length {len(py)} != {len(rs)}")
            return
        for x, y in zip(py, rs):
            walk(x, y, rules, path + ("*",), entry, stats, diffs)
        return
    if isinstance(py, float):
        rule = rules.get(path)
        if rule is None:
            ok = bits(py) == bits(rs)
            stats.add((entry, "copied floats (EXACT_VALUE)"), py, rs, ok)
        else:
            d = abs(rs - py)
            ok = bits(py) == bits(rs) or d <= rule["k_ulp"] * math.ulp(py) or (
                "r_rel" in rule and d <= rule["r_rel"] * abs(py))
            stats.add((entry, "/".join(path) + " (ULP_BOUNDED)"), py, rs, ok)
        if not ok:
            diffs.append(f"{'/'.join(path)}: py {py!r} rust {rs!r}")
        return
    if py != rs:
        diffs.append(f"{'/'.join(path)}: py {py!r} rust {rs!r}")


def compare(vec: dict, py: dict, rs: dict, stats: Stats) -> list:
    entry = vec["entry"]
    diffs: list = []
    div = vec.get("div")
    if div is not None:
        ok = (py["outcome"] == div["python_outcome"] and rs["outcome"] == "RAISED" and rs.get("status") == div["status"]
              and rs.get("class") == div["class"] and rs.get("message", "").startswith(div["message_prefix"]))
        stats.add((entry, "registered divergence outcome"), 0, 0 if ok else 1, ok)
        return [] if ok else [f"registered divergence {div['id']} not met: py {py} rust {rs}"]
    if py["outcome"] != rs["outcome"]:
        diffs.append(f"outcome py {py['outcome']} ({py.get('class')}: {py.get('message')}) rust {rs['outcome']} "
                     f"({rs.get('class')}: {rs.get('message')})")
        stats.add((entry, "outcome"), 0, 1, False)
        return diffs
    stats.add((entry, "outcome"), 0, 0, True)
    if py["outcome"] == "RAISED":
        ok = py["class"] == rs["class"] and py["message"] == rs["message"] and rs.get("status") == vec.get(
            "status", "OUT_OF_DOMAIN")
        stats.add((entry, "error class / message / status"), 0, 0 if ok else 1, ok)
        if not ok:
            diffs.append(f"error py {py['class']}: {py['message']!r} rust {rs.get('class')}: {rs.get('message')!r} "
                         f"({rs.get('status')})")
        return diffs
    walk(py["value"], rs["value"], vec.get("rules", {}), (), entry, stats, diffs)
    return diffs


def ulp_rules(paths, k_ulp=4, r_rel=None) -> dict:
    r = {"k_ulp": k_ulp}
    if r_rel is not None:
        r["r_rel"] = r_rel
    return {tuple(p): r for p in paths}


# ----------------------------------------------------------------------------------------------------------------------
# contract a: reference spacecraft drag
# ----------------------------------------------------------------------------------------------------------------------
RD_RULES = ulp_rules([("q_Pa",), ("reference_term", "D_N"), ("intake_term", "D_N"), ("D_total_N",), ("D_total_mN",)])
SM_RULES = ulp_rules([("margin_N",)])
INTAKE_TERMS = [(0.5, 2.0), (0.25, 2.05), (0.0, 0.0)]
SRC_A = "parity vector (numerical domain only; not an F1 record)"
E_DEF = dict(rho_kg_m3=2.5e-10, v_rel_m_s=7800.0, intake_projected_area_m2=0.1, intake_cd=2.0,
             intake_source="F1 test stub", atmosphere_state={"source": "test-orbit-resolved-stub", "state_id": "s0"},
             intake_accounting="separate_term")
RD_KEYS = ("rho_kg_m3", "v_rel_m_s", "intake_projected_area_m2", "intake_cd", "intake_source", "atmosphere_state",
           "intake_accounting")


def design_states():
    return [(s.state_id, s.rho_kg_m3, s.atm()["V"]) for s in isy.required_states()]


def rd_call(case, kw):
    return SRD.reference_drag(case, **copy.deepcopy(kw))


def rd_vec(vid, case, kw, div=None):
    req = {"id": vid, "entry": "reference_drag", "case": case, **{k: kw[k] for k in RD_KEYS}}
    return {"id": vid, "entry": "reference_drag", "request": enc(req),
            "py": (lambda: py_call(rd_call, case, kw)), "rules": RD_RULES, "div": div, "kind": "rd"}


def sm_vec(vid, drag_case, drag_kw, t, state, source, drag_result=None):
    req = {"id": vid, "entry": "statewise_margin", "thrust_available_N": t, "thrust_state": state,
           "thrust_source": source}
    if drag_result is None:
        req["drag"] = {"case": drag_case, **{k: drag_kw[k] for k in RD_KEYS}}
    else:
        req["drag_result"] = drag_result

    def py():
        def f():
            d = rd_call(drag_case, drag_kw) if drag_result is None else copy.deepcopy(drag_result)
            return SRD.statewise_margin(t, d, thrust_state=copy.deepcopy(state), thrust_source=source)
        return py_call(f)
    return {"id": vid, "entry": "statewise_margin", "request": enc(req), "py": py, "rules": SM_RULES,
            "div": None, "kind": "sm"}


def gen_a(master: int) -> list:
    vecs = []
    sts = design_states()
    cases = [c.case_id for c in SRD.CASES]
    golden_kw = {}
    for i, (sid, rho, v) in enumerate(sts):
        a, cd = INTAKE_TERMS[i % 3]
        for c in cases:
            for acc in SRD.INTAKE_ACCOUNTING:
                kw = dict(rho_kg_m3=rho, v_rel_m_s=v, intake_projected_area_m2=a, intake_cd=cd, intake_source=SRC_A,
                          atmosphere_state={"source": DS_ID, "state_id": sid}, intake_accounting=acc)
                golden_kw[(i, c, acc)] = kw
                vecs.append(rd_vec(f"RD-G-{i:03d}-{c}-{acc}", c, kw))
    g0 = rng(master, 0)
    rd_r = []
    for k in range(600):
        c = cases[int(g0.integers(0, 8))]
        acc = SRD.INTAKE_ACCOUNTING[int(g0.integers(0, 2))]
        rho = float(10.0 ** g0.uniform(-13.0, -8.0))
        v = float(g0.uniform(6000.0, 8500.0))
        a = float(g0.uniform(0.0, 2.0))
        cd = float(g0.uniform(0.0, 5.0))
        kw = dict(rho_kg_m3=rho, v_rel_m_s=v, intake_projected_area_m2=a, intake_cd=cd, intake_source=SRC_A,
                  atmosphere_state={"source": "parity-random", "state_id": f"r{k}"}, intake_accounting=acc)
        rd_r.append((c, kw))
        vecs.append(rd_vec(f"RD-R-{k:03d}", c, kw))
    edges = [("E-A-01", "RC-DIAMANT", dict(intake_projected_area_m2=0.0, intake_cd=0.0)),
             ("E-A-02", "RC-SCHONHERR", dict(rho_kg_m3=5e-324, v_rel_m_s=1.0)),
             ("E-A-03", "RC-NISHIYAMA", dict(rho_kg_m3=1e-300, v_rel_m_s=1e-10)),
             ("E-A-04", "RC-DICARA-ESA", dict(atmosphere_state={"source": "x", "state_id": "s0", "alt_km": 200.0,
                                                                  "scenario": "ECSS_LT_MODERATE"})),
             ("E-A-05", "RC-TISAEV-LOW", dict(rho_kg_m3=1, v_rel_m_s=7800, intake_projected_area_m2=1, intake_cd=2)),
             ("E-A-06", "RC-TISAEV-HIGH", dict(intake_source="  F1 record  ")),
             ("E-A-07", "RC-VAIDYA-GOCELIKE", dict(intake_accounting="contained_in_reference"))]
    for eid, c, over in edges:
        vecs.append(rd_vec(eid, c, {**E_DEF, **over}))
    nan, inf = float("nan"), float("inf")
    div = {"python_outcome": "RETURNED", "status": "OUT_OF_DOMAIN", "class": "ValueError",
           "message_prefix": "non-finite drag result"}
    des = [("DE-A-01", "RC-DIAMANT", dict(rho_kg_m3=None)), ("DE-A-02", "RC-DIAMANT", dict(rho_kg_m3=0.0)),
           ("DE-A-03", "RC-DIAMANT", dict(rho_kg_m3=-1.0)), ("DE-A-04", "RC-DIAMANT", dict(rho_kg_m3=nan)),
           ("DE-A-05", "RC-DIAMANT", dict(rho_kg_m3=inf)), ("DE-A-06", "RC-DIAMANT", dict(v_rel_m_s=None)),
           ("DE-A-07", "RC-DIAMANT", dict(v_rel_m_s=0.0)),
           ("DE-A-08", "RC-DIAMANT", dict(intake_projected_area_m2=None)),
           ("DE-A-09", "RC-DIAMANT", dict(intake_projected_area_m2=-0.5)),
           ("DE-A-10", "RC-DIAMANT", dict(intake_cd=None)), ("DE-A-11", "RC-DIAMANT", dict(intake_cd=True)),
           ("DE-A-12", "RC-DIAMANT", dict(rho_kg_m3="1e-10")), ("DE-A-13", "RC-DIAMANT", dict(intake_source="")),
           ("DE-A-14", "RC-DIAMANT", dict(intake_source="   ")),
           ("DE-A-15", "RC-DIAMANT", dict(intake_source=None)),
           ("DE-A-16", "RC-DIAMANT", dict(atmosphere_state={})),
           ("DE-A-17", "RC-DIAMANT", dict(atmosphere_state={"source": "x"})),
           ("DE-A-18", "RC-DIAMANT", dict(atmosphere_state={"source": "x", "state_id": ""})),
           ("DE-A-19", "RC-DIAMANT", dict(atmosphere_state="s0")),
           ("DE-A-20", "RC-DIAMANT", dict(intake_accounting=None)),
           ("DE-A-21", "RC-DIAMANT", dict(intake_accounting="maybe")), ("DE-A-22", "RC-FLIGHT", {}),
           ("DE-A-23", None, {}), ("DE-A-24", "RC-ROMANO2018", dict(intake_accounting="separate_term")),
           ("DE-A-25", "RC-VAIDYA-GOCELIKE", dict(intake_accounting="separate_term"))]
    for eid, c, over in des:
        vecs.append(rd_vec(eid, c, {**E_DEF, **over}))
    for eid, over in [("DE-A-26", dict(rho_kg_m3=1e300, v_rel_m_s=1e200, intake_projected_area_m2=0.0, intake_cd=0.0)),
                      ("DE-A-27", dict(rho_kg_m3=1e300, v_rel_m_s=1e10)),
                      ("DE-A-28", dict(intake_projected_area_m2=10.0, intake_cd=1e308, rho_kg_m3=1e-8,
                                       v_rel_m_s=8000.0))]:
        vecs.append(rd_vec(eid, "RC-DIAMANT", {**E_DEF, **over}, div={**div, "id": "DIV-A-01"}))
    vecs.append(rd_vec("DE-A-29", "RC-X", {**E_DEF, "rho_kg_m3": None}))
    vecs.append(rd_vec("DE-A-30", "RC-DIAMANT", {**E_DEF, "rho_kg_m3": None, "v_rel_m_s": None, "intake_source": ""}))
    # statewise_margin
    thr = [0.0, 0.006, 0.012, 0.018, 0.024]
    for i, (sid, _, _) in enumerate(sts):
        kw = golden_kw[(i, "RC-DIAMANT", "separate_term")]
        vecs.append(sm_vec(f"SM-G1-{i:03d}", "RC-DIAMANT", kw, thr[i % 5], {"source": DS_ID, "state_id": sid},
                           "parity vector"))
    for i, (sid, _, _) in enumerate(sts):
        kw = golden_kw[(i, "RC-ROMANO2018", "contained_in_reference")]
        t = rd_call("RC-ROMANO2018", kw)["D_total_N"]
        vecs.append(sm_vec(f"SM-G2-{i:03d}", "RC-ROMANO2018", kw, t, {"source": DS_ID, "state_id": sid},
                           "parity vector"))
    g1 = rng(master, 1)
    n = 0
    for k, (c, kw) in enumerate(rd_r):
        if n == 300:
            break
        if py_call(rd_call, c, kw)["outcome"] != "RETURNED":
            continue
        t = float(g1.uniform(0.0, 0.05))
        vecs.append(sm_vec(f"SM-R-{n:03d}", c, kw, t, dict(kw["atmosphere_state"]), "parity vector"))
        n += 1
    st0 = dict(E_DEF["atmosphere_state"])
    dm = [("DE-M-01", dict(t=None)), ("DE-M-02", dict(t=-0.001)), ("DE-M-03", dict(t=nan)),
          ("DE-M-04", dict(t=True)), ("DE-M-05", dict(t=0.0)), ("DE-M-06", dict(source="")),
          ("DE-M-07", dict(source=None)), ("DE-M-08", dict(drag_result={"status": "FLIGHT"})),
          ("DE-M-09", dict(drag_result="x")), ("DE-M-10", dict(state={"source": "x", "state_id": "s1"})),
          ("DE-M-11", dict(state={**st0, "extra": 1})), ("DE-M-12", dict(state=dict(reversed(list(st0.items()))))),
          ("DE-M-13", dict(state="s0")), ("DE-M-14", dict(t=1))]
    for eid, o in dm:
        vecs.append(sm_vec(eid, "RC-DIAMANT", E_DEF, o.get("t", 0.012), o.get("state", dict(st0)),
                           o.get("source", "test"), drag_result=o.get("drag_result")))
    vecs.append({"id": "DFT", "entry": "density_free_table", "request": {"id": "DFT", "entry": "density_free_table"},
                 "py": lambda: py_call(SRD.density_free_table), "rules": {}, "div": None, "kind": "dft"})
    vecs.append({"id": "DOC", "entry": "build_document", "request": {"id": "DOC", "entry": "build_document"},
                 "py": lambda: py_call(lambda: {"text": json.dumps(SRD.build_document(), indent=1,
                                                                   ensure_ascii=False)}),
                 "rules": {}, "div": None, "kind": "doc"})
    for cid in cases + ["RC-FLIGHT", "", "rc-diamant"]:
        vecs.append({"id": f"CASE-{cid or 'EMPTY'}", "entry": "case",
                     "request": {"id": f"CASE-{cid or 'EMPTY'}", "entry": "case", "case_id": cid},
                     "py": (lambda cid=cid: py_call(lambda: (dict(SRD.case(cid).__dict__) if SRD.case(cid) else None))),
                     "rules": {}, "div": None, "kind": "case"})
    return vecs


def invariants_a(vecs, pys, rss) -> dict:
    ok01 = ok02 = True
    for v, p, r in zip(vecs, pys, rss):
        for out in (p, r):
            if v["kind"] in ("rd", "sm") and out["outcome"] == "RETURNED" and v.get("div") is None:
                x = out["value"]
                if x["status"] != SRD.STATUS or x["freeze_status"] != "NOT_EVALUATED" or x["label"] != SRD.LABEL:
                    ok02 = False
                if v["kind"] == "rd":
                    add = x["intake_term"]["D_N"] if x["intake_term"]["added_to_total"] else 0.0
                    if bits(x["D_total_N"]) != bits(x["reference_term"]["D_N"] + add):
                        ok01 = False
    src = (ROOT / "crates/abep-mission/src/reference_drag.rs").read_text()
    code = "\n".join(line for line in src.splitlines() if not line.strip().startswith("//"))
    ok05 = not any(t in code for t in ("std::fs", "read_verified", "read_bytes", "File::", "nonnegative"))
    try:
        SRD._integrity()
        ok03 = True
    except Exception:  # noqa: BLE001
        ok03 = False
    ok03 = ok03 and not any(r["outcome"] == "RAISED" and "not stated together" in r.get("message", "") for r in rss)
    return {"INV-A-01": ok01, "INV-A-02": ok02, "INV-A-03": ok03, "INV-A-05": ok05}


# ----------------------------------------------------------------------------------------------------------------------
# contract b: statewise quantifier
# ----------------------------------------------------------------------------------------------------------------------
QS_RULES = ulp_rules([("orbit_average_margin",)])


def quant(states, margins, rid):
    it = iter(margins)

    def fn(_st):
        m = next(it)
        if isinstance(m, dict) and "raise" in m:
            cls, msg = m["raise"]
            raise EXC[cls](msg)
        return m
    return SW.statewise_quantifier(copy.deepcopy(states), fn, rid)


def qs_vec(vid, states, margins, rid, kind="qs"):
    req = {"id": vid, "entry": "statewise_quantifier", "states": states, "margins": margins, "requirement_id": rid}
    return {"id": vid, "entry": "statewise_quantifier", "request": enc(req),
            "py": (lambda: py_call(quant, states, margins, rid)), "rules": QS_RULES, "div": None, "kind": kind,
            "states": states, "margins": margins, "rid": rid}


def mk_states(ids, weights=None):
    out = []
    for j, sid in enumerate(ids):
        d = {"state_id": sid}
        if weights is not None and weights[j] is not ...:
            d["weight"] = weights[j]
        out.append(d)
    return out


def gen_b(master: int) -> list:
    vecs = []
    ds = isy.required_states()
    ids = [s.state_id for s in ds]
    rho = [s.rho_kg_m3 for s in ds]
    tk = [s.T_K for s in ds]
    med = statistics.median(rho)
    vecs.append(qs_vec("QS-G1", mk_states(ids), [r - min(rho) for r in rho], "PARITY-RHO-MIN"))
    vecs.append(qs_vec("QS-G2", mk_states(ids), [r - med for r in rho], "PARITY-RHO-MED"))
    vecs.append(qs_vec("QS-G3", mk_states(ids), [r - max(rho) for r in rho], "PARITY-RHO-MAX"))
    vecs.append(qs_vec("QS-G4", mk_states(ids), [t < 1700.0 for t in tk], "PARITY-T-1700"))
    vecs.append(qs_vec("QS-G5", mk_states(ids), [t < 1000.0 for t in tk], "PARITY-T-1000"))
    vecs.append(qs_vec("QS-G6", mk_states(ids, [1.0] * len(ids)), [r - med for r in rho], "PARITY-RHO-MED-W1"))
    vecs.append(qs_vec("QS-G7", mk_states(ids, [s.alt_km for s in ds]), [r - med for r in rho], "PARITY-RHO-MED-WALT"))
    nan, inf = float("nan"), float("inf")

    def ids_n(n):
        return [f"s{j}" for j in range(n)]
    edges = [("E-B-01", ids_n(1), None, [0.0]), ("E-B-02", ids_n(1), None, [-0.0]),
             ("E-B-03", ids_n(4), None, [0.5, -0.2, -0.2, 0.1]), ("E-B-04", ids_n(2), None, [False, False]),
             ("E-B-05", ids_n(3), [1, 2, 3], [1.0, -1.0, 0.5]), ("E-B-06", ids_n(2), [None, 0.0], [1.0, 2.0]),
             ("E-B-07", [7, "s1"], None, [1.0, 2.0]), ("E-B-08", ids_n(1), None, [0]),
             ("E-B-09", ids_n(3), None, [-1.0, {"raise": ["RuntimeError", "boom"]}, 2.0]),
             ("E-B-10", ids_n(2), None, [{"raise": ["ValueError", "bad"]}, nan]),
             ("E-B-11", ids_n(2), [1.0, 1.0], [1.0, inf]),
             ("E-B-12", ids_n(3), [0.0, 0.0, 5.0], [True, 3, -2.5])]
    for eid, sids, w, m in edges:
        vecs.append(qs_vec(eid, mk_states(sids, w), m, "PARITY-EDGE"))
    d2 = ids_n(2)
    des = [("DE-B-01", [], [], "PARITY-DE"), ("DE-B-02", mk_states(d2), [1.0, 2.0], ""),
           ("DE-B-03", mk_states(d2), [1.0, 2.0], None),
           ("DE-B-04", mk_states(d2, [1.0, True]), [1.0, 2.0], "PARITY-DE"),
           ("DE-B-05", mk_states(d2, [-1.0, 1.0]), [1.0, 2.0], "PARITY-DE"),
           ("DE-B-06", mk_states(d2, [nan, 1.0]), [1.0, 2.0], "PARITY-DE"),
           ("DE-B-07", mk_states(d2, ["1", 1.0]), [1.0, 2.0], "PARITY-DE"),
           ("DE-B-08", mk_states(d2, [0.0, 0.0]), [1.0, 2.0], "PARITY-DE"),
           ("DE-B-09", [{"state_id": "s0"}, {}], [1.0, 2.0], "PARITY-DE"),
           ("DE-B-10", [{"state_id": "s0"}, {"state_id": None}], [1.0, 2.0], "PARITY-DE"),
           ("DE-B-11", mk_states(d2, [1.0, inf]), [1.0, 2.0], "PARITY-DE"),
           ("DE-B-12", mk_states(d2), [1.0, "x"], "PARITY-DE"),
           ("DE-B-13", mk_states(d2), [1.0, None], "PARITY-DE")]
    for eid, st, m, rid in des:
        vecs.append(qs_vec(eid, st, m, rid))
    g = rng(master, 0)
    for k in range(400):
        n = int(g.integers(1, 41))
        mode = int(g.integers(0, 4))
        states, margins = [], []
        for j in range(n):
            st = {"state_id": f"s{j}"}
            if mode == 1:
                st["weight"] = float(g.uniform(0.0, 10.0))
            elif mode == 2:
                if g.uniform() < 0.5:
                    st["weight"] = float(g.uniform(0.0, 10.0))
            elif mode == 3:
                st["weight"] = 0.0 if g.uniform() < 0.3 else float(g.uniform(0.0, 10.0))
            kind = int(g.integers(0, 20))
            if kind <= 14:
                m = float(g.uniform(-1.0, 1.0))
            elif kind <= 16:
                m = bool(g.integers(0, 2) == 1)
            elif kind == 17:
                m = int(g.integers(-3, 4))
            elif kind == 18:
                m = [nan, inf, -inf][int(g.integers(0, 3))]
            else:
                m = {"raise": [("RuntimeError", f"boom {j}"), ("ValueError", f"bad {j}"),
                               ("ZeroDivisionError", "float division by zero")][int(g.integers(0, 3))]}
                m = {"raise": list(m["raise"])}
            states.append(st)
            margins.append(m)
        vecs.append(qs_vec(f"QS-R-{k:03d}", states, margins, f"REQ-R{k}"))
    return vecs


def stripped(v):
    st = [{k: x for k, x in s.items() if k != "weight"} for s in v["states"]]
    return qs_vec(v["id"] + "-NOW", st, v["margins"], v["rid"], kind="strip")


def invariants_b(vecs, pys, rss, extra_pairs) -> dict:
    ok1 = ok4 = True
    for v, p, r in zip(vecs, pys, rss):
        for out in (p, r):
            if out["outcome"] != "RETURNED":
                continue
            x = out["value"]
            per = x["per_state"]
            if x["n_states"] != len(per) or x["n_fail"] != sum(q["status"] == "FAIL" for q in per) or \
                    x["n_model_error"] != len(x["errors"]) or \
                    x["n_model_error"] != sum(q["status"] == "MODEL_ERROR" for q in per) or \
                    (x["verdict"] == "PASS") != (x["n_fail"] == 0 and x["n_model_error"] == 0):
                ok1 = False
            for q, m in zip(per, v["margins"]):
                bad = (isinstance(m, dict) and "raise" in m) or (isinstance(m, float) and not math.isfinite(m))
                if bad and q["status"] != "MODEL_ERROR":
                    ok4 = False
    ok2 = True
    for (pv, pw), (rv, rw) in extra_pairs:
        for a, b in ((pv, pw), (rv, rw)):
            if a["outcome"] == "RETURNED" and (b["outcome"] != "RETURNED" or a["value"]["verdict"] !=
                                               b["value"]["verdict"]):
                ok2 = False
    return {"INV-B-01": ok1, "INV-B-02": ok2, "INV-B-04": ok4}


# ----------------------------------------------------------------------------------------------------------------------
# contract d: drag kernel
# ----------------------------------------------------------------------------------------------------------------------
DT_RULE = {"k_ulp": 4, "r_rel": 1e-12}
TD_RULES = ulp_rules([("value",), ("drag_total_N",)])
SW_RULES = ulp_rules([("*", "objectives", "*", "partial", "D_intake_N")], r_rel=1e-12)
SCEN = ["maxwell_a0", "maxwell_a0.2", "maxwell_a0.5", "maxwell_a0.8", "maxwell_a1", "cll_a0", "cll_a0.2",
        "cll_a0.5", "cll_a0.8", "cll_a1"]
SW_POINTS = [(A, L, phi, sc) for sc in SCEN for (A, L, phi) in ((0.25, 3.0, 0.8), (0.5, 10.0, 0.9), (1.5, 20.0, 0.9))]
HS_DOCS = {"HS-01": ({"schema": "transport_ensemble_v0", "members": [{"ensemble_member_id": "HYPOTHETICAL-1"}]}, True),
           "HS-02": ({"schema": "transport_ensemble_v0", "members": []}, False),
           "HS-03": ({"schema": "transport_ensemble_v0"}, False),
           "HS-04": ({"schema": "transport_ensemble_v0", "members": [{"ensemble_member_id": "HYPOTHETICAL-1"},
                                                                        {"ensemble_member_id": "HYPOTHETICAL-2"}]},
                     False)}


def M(v):
    return {"value": v, "evidence_class": "measured", "source": "parity M"}


def A_(v):
    return {"value": v, "evidence_class": "assumed", "source": "parity A"}


def P(v):
    return {"value": v, "evidence_class": "model-derived", "source": "parity P", "parametric": True}


def S(v):
    return {"value": v, "evidence_class": ao.SYN_CLASS, "source": "parity S"}


def hs_tree(work: Path, name: str, tag: str = "") -> Path:
    doc, keep_val = HS_DOCS[name]
    t = C.make_repo(work / f"hs_{name}{tag}", {ao.ENS_REL, ao.VAL_REL})
    (t / ao.ENS_REL).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    if not keep_val:
        (t / ao.VAL_REL).unlink()
    return t


def hall_spec(name: str):
    if name == "HS-REPO":
        return "repo"
    doc, keep_val = HS_DOCS[name]
    val = json.loads((ROOT / ao.VAL_REL).read_text(encoding="utf-8")) if keep_val else None
    return {"ensemble": doc, "validation": val}


def td_vec(vid, kw, hall, trees):
    repo = ROOT if hall == "HS-REPO" else trees[hall]
    req = {"id": vid, "entry": "thrust_minus_drag", "hall": hall_spec(hall),
           **{k: kw.get(k) for k in ("drag_intake_N", "drag_intake_se_N", "thrust", "spacecraft_drag",
                                     "intake_drag")}}

    def py():
        return py_call(ao.thrust_minus_drag, kw.get("drag_intake_N"), kw.get("drag_intake_se_N"),
                       copy.deepcopy(kw.get("thrust")), copy.deepcopy(kw.get("spacecraft_drag")), repo,
                       intake_drag=copy.deepcopy(kw.get("intake_drag")))
    return {"id": vid, "entry": "thrust_minus_drag", "request": enc(req), "py": py, "rules": TD_RULES, "div": None,
            "kind": "td", "hall": hall}


def so_vec(vid, name, rec):
    req = {"id": vid, "entry": "supplied_objective", "name": name, "rec": rec, "units": "N"}
    return {"id": vid, "entry": "supplied_objective", "request": enc(req),
            "py": (lambda: py_call(ao.supplied_objective, name, copy.deepcopy(rec), "N")), "rules": {}, "div": None,
            "kind": "so"}


def gen_d(master: int, work: Path) -> tuple[list, dict]:
    vecs = []
    trees = {h: hs_tree(work, h) for h in HS_DOCS}
    # DT
    vecs.append({"id": "DT", "entry": "drag_table", "request": {"id": "DT", "entry": "drag_table"},
                 "py": (lambda: py_call(lambda: [{"scenario": k[0], "L_over_d": k[1], "phi": k[2], "state_id": k[3],
                                                  "D_per_area_N_m2": v[0], "SE_per_area_N_m2": v[1]}
                                                 for k, v in ao.drag_table(ao.read_f1()).items()])),
                 "rules": {("*", "D_per_area_N_m2"): DT_RULE, ("*", "SE_per_area_N_m2"): DT_RULE}, "div": None,
                 "kind": "dt"})
    # HS
    vecs.append({"id": "HS-REPO", "entry": "hall_response_status",
                 "request": {"id": "HS-REPO", "entry": "hall_response_status", "hall": "repo"},
                 "py": (lambda: py_call(ao.hall_response_status, ROOT)), "rules": {}, "div": None, "kind": "hs"})
    for h in HS_DOCS:
        vecs.append({"id": h, "entry": "hall_response_status",
                     "request": {"id": h, "entry": "hall_response_status", "hall": hall_spec(h)},
                     "py": (lambda h=h: py_call(ao.hall_response_status, trees[h])), "rules": {}, "div": None,
                     "kind": "hs"})
    # SO
    classes = ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "TBD", "allocation",
               ao.SYN_CLASS, None, 3]
    params = [..., True, False, 1, "", "yes"]
    for name in ("T", "D_body", "D_intake"):
        vecs.append(so_vec(f"SO-{name}-None", name, None))
        for i, ec in enumerate(classes):
            for j, p in enumerate(params):
                for val in (0.03, 2):
                    rec = {"value": val, "evidence_class": ec, "source": "parity source"}
                    if p is not ...:
                        rec["parametric"] = p
                    vecs.append(so_vec(f"SO-{name}-{i}-{j}-{val}", name, rec))
    vecs.append(so_vec("E-D-04", "T", {"value": 0.03, "evidence_class": "measured", "source": None}))
    vecs.append(so_vec("E-D-05", "T", {"value": 0.03, "evidence_class": ["measured"], "source": "x"}))
    nan, inf = float("nan"), float("inf")
    for eid, rec in [("DE-D-01", {"evidence_class": "measured", "source": "x"}),
                     ("DE-D-02", {"value": 0.03, "source": "x"}),
                     ("DE-D-03", {"value": 0.03, "evidence_class": "measured"}),
                     ("DE-D-04", {"value": None, "evidence_class": "measured", "source": "x"}),
                     ("DE-D-05", {"value": True, "evidence_class": "measured", "source": "x"}),
                     ("DE-D-06", {"value": "0.03", "evidence_class": "measured", "source": "x"}),
                     ("DE-D-07", {"value": nan, "evidence_class": "measured", "source": "x"}),
                     ("DE-D-08", {"value": inf, "evidence_class": "measured", "source": "x"}),
                     ("DE-D-09", {"value": -inf, "evidence_class": "measured", "source": "x"}),
                     ("DE-D-10", {"value": [1], "evidence_class": "measured", "source": "x"})]:
        vecs.append(so_vec(eid, "T", rec))
    # TD grid
    tf = [None, M(0.03), A_(0.03), P(0.03), S(0.03)]
    df = [None, M(0.002), A_(0.002), S(0.002)]
    inf_ = [None, M(0.005), P(0.005), S(0.005)]
    k = 0
    for di in (None, 0.004, 0):
        for se in (None, 1e-05):
            for t in tf:
                for db in df:
                    for idr in inf_:
                        for hall in ("HS-REPO", "HS-01"):
                            kw = dict(drag_intake_N=di, drag_intake_se_N=se, thrust=t, spacecraft_drag=db,
                                      intake_drag=idr)
                            vecs.append(td_vec(f"TD-{k:03d}", kw, hall, trees))
                            k += 1
    base = dict(drag_intake_N=0.004, drag_intake_se_N=1e-05, thrust=None, spacecraft_drag=None, intake_drag=None)
    for eid, over in [("E-D-01", dict(drag_intake_N=0, thrust=S(0.03), spacecraft_drag=S(0.002))),
                      ("E-D-02", dict(drag_intake_N=None, thrust=S(0.03), spacecraft_drag=S(0.002))),
                      ("E-D-03", dict(thrust=S(-0.01), spacecraft_drag=S(0.0), drag_intake_N=0.004))]:
        vecs.append(td_vec(eid, {**base, **over}, "HS-REPO", trees))
    g = rng(master, 0)
    for k in range(300):
        di = None if g.uniform() < 0.2 else float(g.uniform(0.0, 0.05))
        se = None if g.uniform() < 0.5 else float(g.uniform(0.0, 1e-3))
        recs = []
        for which in ("thrust", "spacecraft_drag", "intake_drag"):
            kinds = (None, M, A_, P, S) if which != "intake_drag" else (None, M, P, S)
            kind = kinds[int(g.integers(0, len(kinds)))]
            recs.append(None if kind is None else kind(float(g.uniform(0.0, 0.05))))
        hall = ("HS-REPO", "HS-01")[int(g.integers(0, 2))]
        kw = dict(drag_intake_N=di, drag_intake_se_N=se, thrust=recs[0], spacecraft_drag=recs[1], intake_drag=recs[2])
        vecs.append(td_vec(f"TD-R-{k:03d}", kw, hall, trees))
    for eid, over in [("DE-D-14", dict(thrust={"value": 0.03, "evidence_class": "measured"})),
                      ("DE-D-15", dict(intake_drag={"value": nan, "evidence_class": "measured", "source": "x"},
                                       thrust={"value": True, "evidence_class": "measured", "source": "x"})),
                      ("DE-D-16", dict(thrust={"value": True, "evidence_class": "measured", "source": "x"})),
                      ("DE-D-17", dict(spacecraft_drag={"value": "x", "evidence_class": "measured", "source": "x"})),
                      ("DE-D-18", dict(drag_intake_N=0.004, spacecraft_drag={"value": 0.002,
                                                                             "evidence_class": "measured"}))]:
        vecs.append(td_vec(eid, {**base, **over}, "HS-REPO", trees))
    # SW

    def sw_py():
        dt = ao.drag_table(ao.read_f1())
        out = []
        req_ids = list(ao.required_state_ids())
        for (A, L, phi, sc) in SW_POINTS:
            objs = []
            for sid in req_ids:
                rec = {"value": A * dt[(sc, L, phi, sid)][0], "evidence_class": "model-derived",
                       "source": f"F1 intake-face drag (drag_table) scenario {sc} L/d {L:g} phi {phi:g} A {A:g} m^2 "
                                 f"state {sid}", "parametric": True}
                objs.append(ao.thrust_minus_drag(None, None, None, None, ROOT, intake_drag=rec))
            out.append({"state_ids": req_ids, "objectives": objs})
        return out
    vecs.append({"id": "SW", "entry": "statewise_t_minus_d",
                 "request": {"id": "SW", "entry": "statewise_t_minus_d", "points": [list(p) for p in SW_POINTS]},
                 "py": (lambda: py_call(sw_py)), "rules": SW_RULES, "div": None, "kind": "sw"})
    return vecs, trees


def invariants_d(vecs, pys, rss) -> dict:
    out = {}
    dt_p = next(p for v, p in zip(vecs, pys) if v["kind"] == "dt")
    dt_r = next(r for v, r in zip(vecs, rss) if v["kind"] == "dt")
    ok1 = True
    for x in (dt_p, dt_r):
        if x["outcome"] != "RETURNED" or len(x["value"]) != 15760 or not all(
                isinstance(e["D_per_area_N_m2"], float) and isinstance(e["SE_per_area_N_m2"], float)
                and math.isfinite(e["D_per_area_N_m2"]) and math.isfinite(e["SE_per_area_N_m2"]) for e in x["value"]):
            ok1 = False
    out["INV-D-01"] = ok1
    ok2 = ok3 = True
    for v, p, r in zip(vecs, pys, rss):
        for x in (p, r):
            if v["kind"] == "td" and x["outcome"] == "RETURNED":
                val = x["value"]
                t = v["request"].get("thrust")
                if v["hall"] == "HS-REPO" and isinstance(t, dict) and t.get("evidence_class") == "measured" and \
                        val["value"] is not None:
                    ok2 = False
                if val["value"] is not None:
                    if bits(val["value"]) != bits(val["thrust_N"] - val["drag_total_N"]):
                        ok3 = False
            if v["kind"] == "sw" and x["outcome"] == "RETURNED":
                for pt in x["value"]:
                    if len(pt["objectives"]) != 196 or any(o["status"] != "NOT_EVALUATED" for o in pt["objectives"]):
                        ok2 = False
    out["INV-D-02"] = ok2
    out["INV-D-03"] = ok3
    src = (ROOT / "crates/abep-mission/src/statewise_td.rs").read_text()
    code = "\n".join(line.split("//")[0] for line in src.splitlines())
    flat = re.sub(r"\s+", "", code)
    out["INV-D-05"] = (not re.search(r"(>=|<=|[<>])\s*-?\d", code)) and flat.count("thrust_minus_drag(") == 1 and \
        "thrust_minus_drag(&Value::Null,&Value::Null,&Value::Null,&Value::Null,hall,&record)" in flat
    return out


def case_trees_d(work: Path) -> list:
    """DE-D-11..13: Python and Rust on modified case trees."""
    res = []
    t11 = C.make_repo(work / "de_d_11", {isy.F1_CORE_REL})
    core = json.loads((t11 / isy.F1_CORE_REL).read_text(encoding="utf-8"))
    core["encoded"]["species_table"]["rows"][0][9] = core["encoded"]["species_table"]["rows"][0][9] + 0.001
    (t11 / isy.F1_CORE_REL).write_text(json.dumps(core), encoding="utf-8")
    t12 = C.make_repo(work / "de_d_12", {isy.F1_CORE_REL})
    (t12 / isy.F1_CORE_REL).unlink()
    t13 = hs_tree(work, "HS-01", "_de_d_13")
    for cid, tree, entry, req in [("DE-D-11", t11, "drag_table", {"entry": "drag_table"}),
                                  ("DE-D-12", t12, "drag_table", {"entry": "drag_table"}),
                                  ("DE-D-13", t13, "hall_response_status",
                                   {"entry": "hall_response_status", "hall": "repo"})]:
        if entry == "drag_table":
            py = py_call(lambda tree=tree: len(ao.drag_table(isy.load_f1_view(tree))))
        else:
            py = py_call(lambda tree=tree: ao.hall_response_status(tree)["credible_set"])
        rs, _, _ = run_rust([{"id": cid, **req}], repo_root=tree)
        rs = rs[0]
        expect = {"DE-D-11": ("RETURNED", "MODEL_ERROR", "sha256 mismatch"),
                  "DE-D-12": ("RAISED", "MODEL_ERROR", "f1_intake_synthesis_v1_core.json"),
                  "DE-D-13": ("RETURNED", "MODEL_ERROR", "sha256 mismatch")}[cid]
        ok = py["outcome"] == expect[0] and rs["outcome"] == "RAISED" and rs["status"] == expect[1] and \
            expect[2] in rs["message"] and (cid != "DE-D-12" or py.get("class") == "FileNotFoundError")
        res.append({"id": cid, "python": py, "rust": rs, "pass": ok,
                    "registered": "DIV-D-01" if cid != "DE-D-12" else "FileNotFoundError -> MODEL_ERROR (I/O)"})
    return res


# ----------------------------------------------------------------------------------------------------------------------
# contract c: record builder (case trees)
# ----------------------------------------------------------------------------------------------------------------------
def py_builder(tree: Path, *args) -> dict:
    p = subprocess.run([sys.executable, str(tree / BUILDER_REL), *args], cwd=tree, capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return {"exit": p.returncode, "stdout": p.stdout.strip().splitlines(), "stderr_last": (p.stderr.strip().splitlines()
                                                                                          or [""])[-1]}


def py_build_json_error(tree: Path) -> dict:
    snippet = ("import importlib.util,json,sys\n"
               f"spec=importlib.util.spec_from_file_location('b', {str(tree / BUILDER_REL)!r})\n"
               "m=importlib.util.module_from_spec(spec)\n"
               "try:\n spec.loader.exec_module(m); m.build_json(); print(json.dumps({'outcome':'RETURNED'}))\n"
               "except Exception as e:\n print(json.dumps({'outcome':'RAISED','class':type(e).__name__,"
               "'message':str(e)}))\n")
    p = subprocess.run([sys.executable, "-c", snippet], cwd=tree, capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {"outcome": "CRASH",
                                                                                     "stderr": p.stderr[-500:]}


def rs_builder(tree: Path, *args) -> dict:
    p = subprocess.run([str(BIN_RECORD), *args, "--repo", str(tree)], capture_output=True, text=True)
    return {"exit": p.returncode, "stdout": p.stdout.strip().splitlines(),
            "stderr_last": (p.stderr.strip().splitlines() or [""])[-1]}


def tree_hashes(tree: Path) -> dict:
    return {r: (C.sha_file(tree / r) if (tree / r).exists() else None) for r in (OUT_JSON_REL, OUT_MD_REL)}


def run_c(work: Path) -> dict:
    res = {"golden": [], "domain_error": [], "invariants": {}}
    committed = {OUT_JSON_REL: C.sha_file(ROOT / OUT_JSON_REL), OUT_MD_REL: C.sha_file(ROOT / OUT_MD_REL)}
    # B-01 check on the checkout
    p, r = py_builder(ROOT, "--check"), rs_builder(ROOT, "--check")
    ok = p["exit"] == r["exit"] == 0 and p["stdout"] == r["stdout"] == [
        "OK: spacecraft reference drag outputs reproduced"]
    res["golden"].append({"id": "B-01", "python": p, "rust": r, "pass": ok})
    # B-02 write in case trees
    trees = {}
    for side in ("P", "R", "R2"):
        t = C.make_repo(work / f"b02_{side}", {BUILDER_REL, OUT_JSON_REL, OUT_MD_REL})
        (t / OUT_JSON_REL).unlink()
        (t / OUT_MD_REL).unlink()
        trees[side] = t
    p = py_builder(trees["P"])
    r = rs_builder(trees["R"])
    r2 = rs_builder(trees["R2"])
    hp, hr, hr2 = tree_hashes(trees["P"]), tree_hashes(trees["R"]), tree_hashes(trees["R2"])
    ok = p["exit"] == r["exit"] == 0 and p["stdout"] == r["stdout"] and hp == hr == committed
    res["golden"].append({"id": "B-02", "python": p, "rust": r, "python_sha256": hp, "rust_sha256": hr,
                          "committed_sha256": committed, "pass": ok})
    res["invariants"]["INV-C-01"] = hr == hr2 and r2["exit"] == 0
    # B-03 in-memory Python texts vs Rust outputs
    spec = __import__("importlib.util").util.spec_from_file_location("srd_builder", ROOT / BUILDER_REL)
    mod = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc = mod.build_json()
    pj, pm = mod.render_json(doc).encode(), mod.render_md(doc).encode()
    rj, rm = (trees["R"] / OUT_JSON_REL).read_bytes(), (trees["R"] / OUT_MD_REL).read_bytes()
    res["golden"].append({"id": "B-03", "python_sha256": [C.sha_bytes(pj), C.sha_bytes(pm)],
                          "rust_sha256": [C.sha_bytes(rj), C.sha_bytes(rm)], "pass": pj == rj and pm == rm})
    # domain / error case trees
    a913_md = "docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md"
    a915_json = "docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json"
    a914_md = "docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md"
    mod_rel = "abep_sim/spacecraft_reference_drag.py"

    def append(t, rel, b=b"x"):
        with open(t / rel, "ab") as f:
            f.write(b)

    def edit_json(t):
        txt = (t / OUT_JSON_REL).read_text(encoding="utf-8")
        (t / OUT_JSON_REL).write_text(txt.replace("REFERENCE_PARAMETRIC_NOT_FLIGHT", "REFERENCE_PARAMETRIC_NOT_FLIGHX",
                                                  1), encoding="utf-8")

    cases = [("DE-C-01", {a913_md}, lambda t: append(t, a913_md), "check"),
             ("DE-C-02", {a915_json}, lambda t: append(t, a915_json), "check"),
             ("DE-C-03", {a914_md}, lambda t: (t / a914_md).unlink(), "check"),
             ("DE-C-04", {mod_rel}, lambda t: append(t, mod_rel, b"# x\n"), "check"),
             ("DE-C-05", {mod_rel}, lambda t: (t / mod_rel).unlink(), "check"),
             ("DE-C-06", set(), edit_json, "check"),
             ("DE-C-07", set(), lambda t: (t / OUT_MD_REL).unlink(), "check"),
             ("DE-C-08", set(), lambda t: (edit_json(t), append(t, OUT_MD_REL)), "check"),
             ("DE-C-09", {a913_md}, lambda t: append(t, a913_md), "write")]
    for cid, edits, mutate, mode in cases:
        tp = C.make_repo(work / f"{cid}_P", {BUILDER_REL, OUT_JSON_REL, OUT_MD_REL} | edits)
        tr = C.make_repo(work / f"{cid}_R", {BUILDER_REL, OUT_JSON_REL, OUT_MD_REL} | edits)
        mutate(tp)
        mutate(tr)
        before_p, before_r = tree_hashes(tp), tree_hashes(tr)
        args = ("--check",) if mode == "check" else ()
        p = py_builder(tp, *args)
        r = rs_builder(tr, *args)
        perr = py_build_json_error(tp)
        after_p, after_r = tree_hashes(tp), tree_hashes(tr)
        rec = {"id": cid, "python": p, "python_build_json": perr, "rust": r,
               "outputs_untouched": before_p == after_p and before_r == after_r}
        if cid in ("DE-C-01", "DE-C-02", "DE-C-03", "DE-C-09"):
            ok = p["exit"] == r["exit"] == 1 and perr["outcome"] == "RAISED" and \
                r["stderr_last"] == f"{perr['class']}: {perr['message']}" and rec["outputs_untouched"]
        elif cid == "DE-C-04":
            ok = p["exit"] == 1 and p["stdout"] == [
                "CHECK FAILED (not reproduced): spacecraft_reference_drag_v1.json"] and r["exit"] == 1 and \
                r["stderr_last"].startswith("RuntimeError: reference module changed")
        elif cid == "DE-C-05":
            ok = p["exit"] != 0 and r["exit"] == 0 and r["stdout"] == [
                "OK: spacecraft reference drag outputs reproduced"]
        else:
            ok = p["exit"] == r["exit"] == 1 and p["stdout"] == r["stdout"] and p["stdout"][0].startswith(
                "CHECK FAILED") and rec["outputs_untouched"]
        rec["pass"] = ok
        res["domain_error"].append(rec)
    # INV-C-02: --check writes nothing (B-01 on the checkout and every check case tree)
    res["invariants"]["INV-C-02"] = all(d["outputs_untouched"] for d in res["domain_error"] if d["id"] != "DE-C-09") \
        and tree_hashes(ROOT) == committed
    res["invariants"]["INV-C-03"] = next(d for d in res["domain_error"] if d["id"] == "DE-C-09")["outputs_untouched"]
    return res


# ----------------------------------------------------------------------------------------------------------------------
# provenance / reports
# ----------------------------------------------------------------------------------------------------------------------
def git(*a) -> str:
    return C.git(*a)


def load_contract(key: str):
    p = CDIR / CONTRACT_DIRS[key] / "parity_prereg_v1.json"
    return json.loads(p.read_text(encoding="utf-8")), C.sha_file(p), p


def reference_check(contract: dict) -> list:
    bad = []
    for f in contract["reference_implementation"]["files"]:
        got = C.sha_file(ROOT / f["path"])
        if got != f["sha256_at_registration"]:
            bad.append({"path": f["path"], "registered": f["sha256_at_registration"], "found": got})
    for f in contract["reference_implementation"].get("committed_outputs", []):
        got = C.sha_file(ROOT / f["path"])
        if got != f["sha256_at_registration"]:
            bad.append({"path": f["path"], "registered": f["sha256_at_registration"], "found": got})
    return bad


def environment() -> dict:
    env = C.environment()
    try:
        env["cpu"] = next(line.split(":", 1)[1].strip() for line in open("/proc/cpuinfo") if
                          line.startswith("model name"))
    except (OSError, StopIteration):
        env["cpu"] = platform.processor()
    env["blas"] = "scipy-openblas 0.3.31.188.0 (numpy bundle; not used by the scored code)"
    return env


def build_provenance() -> dict:
    lock = C.sha_file(ROOT / "Cargo.lock")
    return {"rustc": C.environment()["rustc"], "cargo_lock_sha256": lock,
            "source_sha256": C.source_sha256(RUST_SOURCES)}


def write_refs(cdir: Path, requests, py_results, rs_results, extra: dict | None = None) -> dict:
    rd = cdir / "reference_outputs"
    rd.mkdir(parents=True, exist_ok=True)
    files = {}

    def put(name, obj):
        b = gzip.compress(json.dumps(obj, ensure_ascii=False, allow_nan=False).encode(), mtime=0)
        (rd / name).write_bytes(b)
        files[name] = C.sha_bytes(b)
    put("requests.json.gz", requests)
    put("python_outputs.json.gz", py_results)
    put("rust_outputs_at_scoring.json.gz", rs_results)
    for k, v in (extra or {}).items():
        put(k, v)
    man = {"captured_at_python_commit": git("rev-parse", "HEAD"), "files": files}
    (rd / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return man


def render_md(rep: dict) -> str:
    L = [f"# Parity report v1 - {rep['contract']['id']}", "",
         f"Verdict: **{rep['parity']}** ({rep['verdict']}). Generated from `parity_report_v1.json`.", "",
         f"* Contract: `{rep['contract']['path']}` sha256 `{rep['contract']['sha256']}`, registered in "
         f"`{rep['contract']['registered_in_commit'][:12]}`.",
         f"* Python reference commit `{rep['python_commit'][:12]}`; Rust commit `{rep['rust_commit'][:12]}` "
         f"(git_dirty: {rep['git_dirty'] or 'none'}); {rep['build_provenance']['rustc']}.",
         f"* Environment: Python {rep['environment']['python']}, numpy {rep['environment']['numpy']}, "
         f"{rep['environment'].get('cpu', '')}.",
         f"* Scoring seed: {rep['seed']}; {rep['n_vectors']} vectors; {rep['n_failures']} per-test failures.", "",
         "## Checks", ""]
    for k, v in rep["checks"].items():
        L.append(f"* {k}: {'pass' if v else 'FAIL'}")
    if rep.get("observables"):
        L += ["", "## Observables", "",
              "| entry | observable | n | fail | bit-identical | max abs diff | max rel diff | max ulp |",
              "|---|---|---|---|---|---|---|---|"]
        for o in rep["observables"]:
            L.append(f"| {o['entry']} | {o['observable']} | {o['n']} | {o['fail']} | {o['bit_identical']} | "
                     f"{o['max_abs_diff']:.3g} | {o['max_rel_diff']:.3g} | {o['max_ulp']:.3g} |")
    if rep.get("domain_error"):
        L += ["", "## Domain / error parity", ""]
        for d in rep["domain_error"]:
            L.append(f"* {d['id']}: {d['summary']} - {'ok' if d['pass'] else 'MISMATCH'}")
    L += ["", "## Invariants", ""]
    for k, v in rep["invariants"].items():
        L.append(f"* {k}: {'pass' if v else 'FAIL'}")
    if rep.get("failures"):
        L += ["", "## Failures (first 20)", ""]
        for f in rep["failures"][:20]:
            L.append(f"* {f}")
    if rep.get("performance"):
        L += ["", "## Performance (reported, never a criterion)", ""]
        for k, v in rep["performance"].items():
            L.append(f"* {k}: {v}")
    if rep.get("notes"):
        L += ["", "## Notes", ""]
        for n in rep["notes"]:
            L.append(f"* {n}")
    L += ["", "## Ledger update requested", ""]
    for x in rep["ledger_update_requested"]:
        L.append(f"* {x['component']}: {x['request']}")
    L += ["", "Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.", ""]
    return "\n".join(L)


# ----------------------------------------------------------------------------------------------------------------------
# campaign
# ----------------------------------------------------------------------------------------------------------------------
LEDGER = {
    "a": [{"component": "C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY", "request":
           "status ADMITTED (whole module) on PARITY_PASS; authoritative_implementation rust: crates/abep-mission "
           "(abep_mission::reference_drag, abep_mission::statewise::statewise_margin, register data "
           "crates/abep-mission/data/spacecraft_reference_register_v1.json); contract "
           "PARITY-C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY-V1; disclosures DIV-A-01 (non-finite results refused)"}],
    "b": [{"component": "C-ABEP_SIM_STATEWISE_PY", "request":
           "status ADMITTED (whole module) on PARITY_PASS; authoritative_implementation rust: "
           "abep_mission::statewise::statewise_quantifier; contract PARITY-C-ABEP_SIM_STATEWISE_PY-V1"}],
    "c": [{"component": "C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG", "request":
           "status ADMITTED on PARITY_PASS; authoritative_implementation rust: binary abep-reference-drag-record "
           "(crates/abep-mission/src/bin/abep_reference_drag_record.rs), `--check` reproduces the committed v1 record; "
           "contract PARITY-C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG-V1; disclosures DIV-C-01 / DIV-C-02"}],
    "d": [{"component": "C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY", "request":
           "partial_admissions += named function subset (RM-R17) drag_table, hall_response_status, supplied_objective, "
           "_obj, thrust_minus_drag -> abep-mission (abep_mission::intake_drag, abep_mission::objective) plus the Rust "
           "statewise T - D record abep_mission::statewise_td, status ADMITTED on PARITY_PASS; module stays "
           "PYTHON_REFERENCE; contract PARITY-C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL-V1; disclosures "
           "DIV-D-01 (pinned governed inputs), findings F-D-01 / F-D-02"}],
}


def evaluate_vectors(vecs: list, repo_root: Path = ROOT):
    pys = [v["py"]() for v in vecs]
    rss, out_bytes, wall = run_rust([v["request"] for v in vecs], repo_root)
    return pys, rss, out_bytes, wall


def run_contract(key: str, mode: str) -> int:
    contract, csha, cpath = load_contract(key)
    cdir = cpath.parent
    seeds = contract["campaign_seeds"]
    seed = seeds.get("scoring_master_seed") if mode == "score" else seeds.get("development_master_seed")
    if mode == "score":
        if (cdir / "parity_report_v1.json").exists():
            print("REFUSED: parity_report_v1.json exists (the scoring seed is spent once)")
            return 2
        dirty = [line for line in git("status", "--porcelain").splitlines() if line[3:].startswith(
            ("crates/", "Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "scripts/rust_migration/parity_sc_wp04.py",
             "scripts/rust_migration/parity_common.py"))]
        if dirty:
            print(f"REFUSED: uncommitted Rust provenance sources: {dirty}")
            return 2
    bad = reference_check(contract)
    if bad:
        print(f"REFUSED_REFERENCE_CHANGED: {bad}")
        return 2
    build_rust()
    work = Path(tempfile.mkdtemp(prefix=f"wp04_{key}_"))
    stats = Stats()
    failures: list = []
    notes: list = []
    perf: dict = {}
    domain: list = []
    try:
        if key == "c":
            res = run_c(work)
            checks = {"golden": all(g["pass"] for g in res["golden"]),
                      "domain_error": all(d["pass"] for d in res["domain_error"]),
                      "invariants": all(res["invariants"].values())}
            for d in res["domain_error"]:
                pb = d["python_build_json"]
                rust_line = d["rust"]["stdout"][:1] or [d["rust"]["stderr_last"][:80]]
                domain.append({"id": d["id"], "pass": d["pass"],
                               "summary": f"Python exit {d['python']['exit']} {d['python']['stdout'][:1] or ''} "
                                          f"build_json {pb.get('class', pb['outcome'])}; "
                                          f"Rust exit {d['rust']['exit']} {rust_line}"})
            n_vec = len(res["golden"]) + len(res["domain_error"])
            n_fail = sum(not x["pass"] for x in res["golden"] + res["domain_error"])
            invariants = res["invariants"]
            requests = py_out = rs_out = None
            detail = res
        else:
            if key == "a":
                vecs = gen_a(seed)
            elif key == "b":
                vecs = gen_b(seed)
            else:
                vecs, _trees = gen_d(seed, work)
            pys, rss, out_bytes, wall = evaluate_vectors(vecs)
            for v, p, r in zip(vecs, pys, rss):
                diffs = compare(v, p, r, stats)
                if diffs:
                    failures.append(f"{v['id']}: {'; '.join(diffs[:3])}")
                if v["id"].startswith("DE-") or v.get("div"):
                    domain.append({"id": v["id"], "pass": not diffs,
                                   "summary": f"Python {p['outcome']} {p.get('class', '')}; Rust {r['outcome']} "
                                              f"{r.get('class', '')} {r.get('status', '')}".strip()})
            # determinism (second Rust process, second Python evaluation)
            _, out2, _ = run_rust([v["request"] for v in vecs])
            pys2 = [v["py"]() for v in vecs]
            det = out2 == out_bytes and json.dumps(pys2) == json.dumps(pys)
            if key == "a":
                invariants = invariants_a(vecs, pys, rss)
                invariants["INV-A-04"] = det
                golden = [v for v in vecs if v["id"].startswith("RD-G")]
                tp = []
                for _ in range(3):
                    t0 = time.perf_counter()
                    for v in golden:
                        v["py"]()
                    tp.append(time.perf_counter() - t0)
                tr = [run_rust([v["request"] for v in golden])[2] for _ in range(3)]
                perf = {"RD-G python median s": statistics.median(tp), "RD-G rust median s (one process)":
                        statistics.median(tr), "speed-up": statistics.median(tp) / statistics.median(tr)}
            elif key == "b":
                strip = [stripped(v) for v in vecs]
                sp = [v["py"]() for v in strip]
                sr, _, _ = run_rust([v["request"] for v in strip])
                invariants = invariants_b(vecs, pys, rss, list(zip(zip(pys, sp), zip(rss, sr))))
                invariants["INV-B-03"] = det
            else:
                invariants = invariants_d(vecs, pys, rss)
                invariants["INV-D-04"] = det
                for d in case_trees_d(work):
                    domain.append({"id": d["id"], "pass": d["pass"], "summary": f"Python {d['python']['outcome']} "
                                   f"{d['python'].get('class', '')}; Rust {d['rust']['outcome']} {d['rust']['status']} "
                                   f"({d['registered']})"})
                    if not d["pass"]:
                        failures.append(f"{d['id']} (case tree): python {d['python']} rust {d['rust']}")
                code = ("import sys; sys.path.insert(0, %r); from abep_sim.design import architecture_optimizer as ao; "
                        "ao.drag_table(ao.read_f1())" % str(ROOT))
                tp, tr = [], []
                for _ in range(3):
                    t0 = time.perf_counter()
                    subprocess.run([sys.executable, "-c", code], capture_output=True, check=True)
                    tp.append(time.perf_counter() - t0)
                    tr.append(run_rust([{"id": "DT", "entry": "drag_table"}])[2])
                perf = {"DT python median s (cold process incl. imports)": statistics.median(tp),
                        "DT rust median s (cold process incl. load + sha256)": statistics.median(tr),
                        "speed-up": statistics.median(tp) / statistics.median(tr)}
            n_vec = len(vecs)
            n_fail = len(failures)
            checks = {"per_test": n_fail == 0,
                      "domain_error": all(d["pass"] for d in domain),
                      "invariants": all(invariants.values())}
            requests = [v["request"] for v in vecs]
            py_out = [{"id": v["id"], **p} for v, p in zip(vecs, pys)]
            rs_out = rss
            detail = None
        checks["governing"] = reference_check(contract) == []
        checks["all"] = all(checks.values())
        if mode == "dev":
            print(json.dumps({"contract": CONTRACT_DIRS[key], "mode": "dev (not a verdict)", "seed": seed,
                              "vectors": n_vec, "failures": failures[:20], "checks": checks,
                              "invariants": invariants, "observables": {"/".join(k): s for k, s in stats.d.items()},
                              "performance": perf}, indent=1, default=str))
            return 0
        parity = "PARITY_PASS" if checks["all"] else "PARITY_FAIL"
        rep = {
            "schema": "abep_rust_parity_report_v1",
            "contract": {"id": contract["id"], "path": str(cpath.relative_to(ROOT)), "sha256": csha,
                         "registered_in_commit": git("log", "--diff-filter=A", "--format=%H", "--",
                                                     str(cpath.relative_to(ROOT))).splitlines()[-1]},
            "parity": parity, "verdict": "ADMITTED" if checks["all"] else "NOT_ADMITTED",
            "python_commit": contract["reference_implementation"]["python_commit"],
            "python_commit_at_scoring_head": git("rev-parse", "HEAD"),
            "reference_sha256": {f["path"]: C.sha_file(ROOT / f["path"]) for f in
                                 contract["reference_implementation"]["files"]},
            "rust_commit": git("rev-parse", "HEAD"),
            "git_dirty": [line for line in git("status", "--porcelain").splitlines()],
            "build_provenance": build_provenance(), "environment": environment(), "seed": seed,
            "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "n_vectors": n_vec, "n_failures": n_fail, "checks": checks, "invariants": invariants,
            "observables": [{"entry": k[0], "observable": k[1], **s} for k, s in stats.d.items()],
            "domain_error": domain, "failures": failures, "performance": perf, "notes": notes,
            "campaign_history": [{"execution": "scoring", "seed": seed, "date_utc": datetime.datetime.now(
                datetime.timezone.utc).isoformat(timespec="seconds"), "parity": parity,
                "development_runs": "development-seed runs only, never reported (contract development_rule)"}],
            "ledger_update_requested": LEDGER[key] if checks["all"] else [
                {"component": LEDGER[key][0]["component"], "request": "NONE (parity failed: stays PYTHON_REFERENCE; "
                                                                       "a code fix needs a new contract version)"}],
        }
        if detail is not None:
            rep["case_results"] = detail
            man = write_refs(cdir, [], [], [], {"case_results.json.gz": detail})
        else:
            man = write_refs(cdir, requests, py_out, rs_out)
        rep["captured_reference_outputs"] = man
        C.write_report(cdir / "parity_report_v1.json", rep, render_md(rep))
        print(f"{contract['id']}: {parity} ({n_vec} vectors, {n_fail} failures)")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv) -> int:
    if len(argv) != 3 or argv[1] not in ("dev", "score") or argv[2] not in CONTRACT_DIRS:
        print(__doc__)
        return 2
    return run_contract(argv[2], argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
