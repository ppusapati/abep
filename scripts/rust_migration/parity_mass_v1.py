#!/usr/bin/env python3
"""Parity harness of the SC-WP-07 mass lane (A9.29; contracts v1 in docs/rust_migration/contracts/):

    K-MASS-RULES                       python3 scripts/rust_migration/parity_mass_v1.py k-mass-rules
    C-DOCS_BUDGETS_MASS_POWER_A9_V5    python3 scripts/rust_migration/parity_mass_v1.py mass-power-v5
    C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3 python3 scripts/rust_migration/parity_mass_v1.py xe-accounting-v3

Default mode `dev` uses the contract's development seed and prints the differences (never a verdict, nothing written).
`--score` uses the scoring seed once, refuses to run if a reference file changed (REFUSED_REFERENCE_CHANGED) or a report
already exists, and writes parity_report_v1.json / .md and reference_outputs/ next to the contract.

The Python reference is imported read-only from this checkout; case trees live in a scratch directory.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parity_common as pc  # noqa: E402

ROOT = pc.ROOT
sys.path.insert(0, str(ROOT))
FLIGHT = "hall_icp_neutralizer"
V3B = "docs/budgets/mass_power_a9_v3/build_mass_power_a9_v3.py"
V4B = "docs/budgets/mass_power_a9_v4/build_mass_power_a9_v4.py"
V5B = "docs/budgets/mass_power_a9_v5/build_mass_power_a9_v5.py"
XB = "docs/budgets/xe_accounting_a9_v3/build_xe_accounting_a9_v3.py"
REC = {v: f"docs/budgets/mass_power_a9_{v}/mass_power_a9_{v}.json" for v in ("v3", "v4", "v5")}
V5MD = "docs/budgets/mass_power_a9_v5/MASS_POWER_A9_V5.md"
XJ = "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json"
CONTRACTS = {"k-mass-rules": "K-MASS-RULES", "mass-power-v5": "C-DOCS_BUDGETS_MASS_POWER_A9_V5",
             "xe-accounting-v3": "C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3"}
NAN, INF = float("nan"), float("inf")
DIV_CFG = ("rollup configuration {cfg} refused: the only flight configuration is 'hall_icp_neutralizer' (A9.19 / "
           "A9.20: C1 is GROUND_REFERENCE_ONLY and never enters a flight mass roll-up)")
DIV_C1 = "AL-C1: C1 is GROUND_REFERENCE_ONLY (A9.19 / A9.20); no C1 line enters a flight mass roll-up"
RECORD_SHA = "3ff23429f5225a8a8363a784281b2f32b1df9ad69ec9934320306b080436b73a"
DIV_PIN = ("docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json sha256 {actual} != pinned " + RECORD_SHA +
           " (frozen mass / power v5 record, read as a pinned input)")


def load(rel: str, name: str, root: Path = ROOT):
    spec = importlib.util.spec_from_file_location(name, root / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def rt(x):
    """The JSON round trip both implementations receive (tuples -> lists, special floats kept)."""
    return json.loads(json.dumps(x))


def call(fn, tag, div=None, **args):
    c = {"fn": fn, "args": rt(args), "tag": tag}
    if div:
        c["div"] = div
    return c


# =============================================================================================== random draws
def mass(rng: random.Random, invalid=0.03):
    if rng.random() < invalid:
        return rng.choice([-1.0, -1e-300, NAN, INF, True, False, "3.5", None])
    r = rng.random()
    if r < 0.7:
        return 10 ** rng.uniform(-6, 3)
    if r < 0.9:
        return round(rng.uniform(0, 60), rng.randint(0, 12))
    return rng.choice([0.0, -0.0, rng.randint(0, 40), rng.randint(10 ** 9, 10 ** 10 - 1) + 0.5, 5e-324])


FRACTIONS = [0.1, 0.2, 0.05, 0.0, 0, 1, True, None, 0.30000000000000004]
RESERVES = [0, 0.0, -0.0, False, 4.0, 1e-9, None, "0"]
OWNER_READING = {"allocations": "MEV", "system_margin": 0.2, "reserve_kg": 0.0, "xe_case": "LOADED"}
BID_READING = dict(OWNER_READING, system_margin=0.1)
LIDS = [f"AL-{n:02d}" for n in range(1, 11)]
REFS_POOL = [["HARD_40_WET", 40.0, True], ["INTERNAL_34", 34.0, False], ["INTERNAL_36", 36.0, False]]


def line_rec(rng, lid):
    gov = rng.choice(["ALLOCATION_MEV", "MEV_PLANNING_FLOOR", "MEV_FROM_CBE", None])
    rec = {"line": lid, "value": {"value_kg": None if rng.random() < 0.15 else mass(rng), "governs": gov}}
    if rng.random() < 0.5:
        rec["allocation_status"] = rng.choice(["TBD_OWNER (x)", "no allocation | pending", "PENDING\nnext"])
    r = rng.random()
    if r < 0.66:
        rec["floor_is_partial"] = r < 0.33
    rec["floor_constituents"] = [{"what": f"part {i}", "kg": None if rng.random() < 0.4 else mass(rng, 0.0)}
                                 for i in range(rng.randint(1, 4))]
    return rec


def mutate_reading(rng, base):
    r = dict(base)
    for _ in range(rng.randint(0, 2)):
        k = rng.choice(list(base))
        act = rng.random()
        if act < 0.2:
            r.pop(k, None)
        elif act < 0.3:
            r["extra"] = 1
        else:
            r[k] = rng.choice(["MEV2", 0.25, 4.0, "USABLE_RESIDUAL_ON_TOP", 0.1, 0.2, 0, None, "LOADED", "MEV"])
    return r


def rand_split(rng):
    cases = set()
    while len(cases) < rng.randint(1, 4):
        cases.add(round(rng.uniform(0.5, 20), rng.randint(0, 4)))
    out = []
    for c in cases:
        loaded = c if rng.random() < 0.97 else c + 0.5
        out.append([c, {"loaded_kg": loaded, "residual_kg": round(rng.uniform(0, 0.5), 7)}])
    rng.shuffle(out)
    return out


def rand_refs(rng):
    pool = [list(r) for r in REFS_POOL] + [[f"R-{i}", round(rng.uniform(0, 80), 3), rng.random() < 0.5]
                                           for i in range(3)]
    return rng.sample(pool, rng.randint(1, 3))


def rand_lines(rng):
    k = rng.randint(0, 10)
    ids = sorted(rng.sample(LIDS, k))
    lines = [line_rec(rng, lid) for lid in ids]
    har = {"line": "AL-HAR", "value": {"value_kg": None, "governs": None}}
    lines.insert(rng.randint(0, len(lines)), har)
    return lines


# =============================================================================================== record helpers
def split_and_refs(rec: dict):
    roll = next(r for r in rec["rollups"] if r["configuration"] == FLIGHT)
    split, refs = {}, []
    for w in roll["wet"]:
        split[w["xe_case_kg"]] = {"loaded_kg": w["xe_loaded_kg"], "residual_kg": w["residual_inside_case_kg"]}
        ref = (w["reference"], w["reference_kg"], w["comparator"] == "<")
        if ref not in refs:
            refs.append(ref)
    return [[k, v] for k, v in split.items()], [list(r) for r in refs], roll


def records():
    return {v: json.loads((ROOT / p).read_text(encoding="utf-8")) for v, p in REC.items()}


# =============================================================================================== K-MASS-RULES
def k_calls(seed: int) -> list:
    recs = records()
    calls = []
    for v, rec in recs.items():
        lines = rec["lines"][FLIGHT]
        for ln in lines:
            calls.append(call("_unresolved", f"R-K01 {v} {ln['line']}", rec=ln))
            if ln["line"] != "AL-HAR":
                calls.append(call("line_mev_value", f"R-K01 {v} {ln['line']}", allocation_kg=ln.get("row54_allocation_kg"),
                                  cbe_kg=ln.get("cbe_kg"), floor_cbe_kg=ln.get("evidence_floor_cbe_kg")))
        split, refs, roll = split_and_refs(rec)
        calls.append(call("rollup", f"R-K02 {v}", cfg=FLIGHT, lines=lines, xe_split=split, refs=refs))
        calls.append(call("system_margin", f"R-K02 {v}", pre_margin_kg=roll["nominal_dry_known_kg"]))
        calls.append(call("harness_row60", f"R-K02 {v}", other_nominal_kg=roll["nonharness_known_kg"]))
        for w in roll["wet"]:
            calls.append(call("closure_state", f"R-K02 {v} {w['xe_case_kg']} {w['reference']}", known_kg=w["wet_known_kg"],
                              reference_kg=w["reference_kg"], strict=w["comparator"] == "<", all_resolved=False))
        if v == "v5":
            calls.append(call("system_margin_bid", "R-K02 v5", pre_margin_kg=roll["nominal_dry_known_kg"]))
    t = "R-K03"
    for a in [dict(allocation_kg=3.5), dict(allocation_kg=3.0, floor_cbe_kg=3.504), dict(allocation_kg=10.0, floor_cbe_kg=3.504),
              dict(allocation_kg=2.5, cbe_kg=4.0, floor_cbe_kg=5.0), {}, dict(allocation_kg=1.0, equipment_margin=0.1),
              dict(allocation_kg=-1.0)]:
        calls.append(call("line_mev_value", t, **a))
    for a in [dict(pre_margin_kg=24.0), dict(pre_margin_kg=24.0, reserve_kg=4.0), dict(pre_margin_kg=24.0, fraction=0.1),
              dict(pre_margin_kg=30.0, fraction=0.1)]:
        calls.append(call("system_margin", t, **a))
    calls.append(call("harness_row60", t, other_nominal_kg=19.0))
    calls.append(call("harness_row60", t, other_nominal_kg=10.0, fraction=0.03))
    for k, r, st, al in [(40.0, 40.0, True, False), (39.0, 40.0, True, False), (39.0, 40.0, True, True),
                         (34.0, 34.0, False, False), (NAN, 40.0, True, False)]:
        calls.append(call("closure_state", t, known_kg=k, reference_kg=r, strict=st, all_resolved=al))
    calls.append(call("system_margin_bid", t, pre_margin_kg=30.0))
    for fr in (0.0, 0.05, 0.2):
        calls.append(call("system_margin_bid", t, pre_margin_kg=30.0, fraction=fr))
    calls.append(call("system_margin_bid", t, pre_margin_kg=30.0, reserve_kg=4.0))
    calls.append(call("assert_bid_margin_reading", t, reading=dict(BID_READING, system_margin=0.05)))
    # ---- edge cases
    for x in [None, 0.0, -0.0, 0, 1, 1234567890.5, 1234567891.5, 0.12345678905, 5e-324, 1.7976931348623157e308, NAN,
              INF, -INF, 12345678901234567, -2.5]:
        calls.append(call("rk", "E-K01", x=x))
    bad = [-1.0, -1e-300, NAN, INF, True, False, "3.5", None, [1.0], -0.0]
    for b in bad:
        for k in ("allocation_kg", "cbe_kg", "floor_cbe_kg"):
            calls.append(call("line_mev_value", "E-K02", **{k: b}))
        calls.append(call("system_margin", "E-K02", pre_margin_kg=b))
        calls.append(call("harness_row60", "E-K02", other_nominal_kg=b))
        calls.append(call("closure_state", "E-K02", known_kg=b, reference_kg=40.0, strict=True, all_resolved=False))
        calls.append(call("closure_state", "E-K02", known_kg=30.0, reference_kg=b, strict=False, all_resolved=False))
        calls.append(call("system_margin_bid", "E-K02", pre_margin_kg=b))
    for fr in FRACTIONS:
        calls.append(call("system_margin", "E-K03", pre_margin_kg=24.0, fraction=fr))
        calls.append(call("system_margin_bid", "E-K03", pre_margin_kg=24.0, fraction=fr))
        calls.append(call("harness_row60", "E-K03", other_nominal_kg=19.0, fraction=fr))
        calls.append(call("line_mev_value", "E-K03", allocation_kg=2.0, cbe_kg=3.0, equipment_margin=fr))
    for rs in RESERVES:
        calls.append(call("system_margin", "E-K03", pre_margin_kg=24.0, reserve_kg=rs))
        calls.append(call("system_margin_bid", "E-K03", pre_margin_kg=24.0, reserve_kg=rs))
    for fn, base, other in (("assert_no_margin_relaxation", OWNER_READING, 0.1),
                            ("assert_bid_margin_reading", BID_READING, 0.2)):
        variants = [base, dict(base, reserve_kg=0), None, [], "MEV", dict(base, extra=1)]
        for k in base:
            variants.append({kk: vv for kk, vv in base.items() if kk != k})
            for alt in ("MEV2", 0.25, 4.0, "USABLE_RESIDUAL_ON_TOP", other):
                variants.append(dict(base, **{k: alt}))
        for r in variants:
            calls.append(call(fn, "E-K04", reading=r))
    v5 = recs["v5"]
    l5 = v5["lines"][FLIGHT]
    s5, r5, roll5 = split_and_refs(v5)
    al09_none = [dict(x, value={"value_kg": None, "governs": None}) if x["line"] == "AL-09" else x for x in l5]
    every_none = [dict(x, value={"value_kg": None, "governs": None}) if x["line"] != "AL-HAR" else x for x in l5]
    partial = [dict(x, value={"value_kg": 4.2048, "governs": "MEV_PLANNING_FLOOR"}, floor_is_partial=True,
                    floor_constituents=[{"what": "magnets", "kg": 3.504}, {"what": "channel ceramics", "kg": None},
                                        {"what": "anode", "kg": None}]) if x["line"] == "AL-04" else x for x in l5]
    variants = {
        "AL-09 None": (al09_none, s5, r5), "every None": (every_none, s5, r5),
        "only AL-HAR": ([x for x in l5 if x["line"] == "AL-HAR"], s5, r5),
        "AL-HAR missing": ([x for x in l5 if x["line"] != "AL-HAR"], s5, r5),
        "no value key": ([{k: v for k, v in x.items() if k != "value"} if x["line"] == "AL-03" else x for x in l5], s5, r5),
        "str value": ([dict(x, value={"value_kg": "5", "governs": "ALLOCATION_MEV"}) if x["line"] == "AL-03" else x
                       for x in l5], s5, r5),
        "int values": ([dict(x, value={"value_kg": int(x["value"]["value_kg"]), "governs": "ALLOCATION_MEV"})
                        if x["line"] in ("AL-01", "AL-02", "AL-10") else x for x in l5], s5, r5),
        "bool value": ([dict(x, value={"value_kg": True, "governs": "ALLOCATION_MEV"}) if x["line"] == "AL-03" else x
                        for x in l5], s5, r5),
        "partial floor": (partial, s5, r5),
        "loaded mismatch": (l5, [[2.0, {"loaded_kg": 2.5, "residual_kg": 0.0392157}]], r5),
        "negative reference": (l5, s5, [["NEG", -1.0, True]]),
        "reference == wet strict": (l5, [[2.0, {"loaded_kg": 2.0, "residual_kg": 0.0}]],
                                    [["EQ_S", 43.83532631, True], ["EQ_N", 43.83532631, False]]),
        "int case keys": (l5, [[2, {"loaded_kg": 2, "residual_kg": 0.04}], [5, {"loaded_kg": 5.0, "residual_kg": 0.1}]], r5),
        "unsorted case keys": (l5, list(reversed(s5)), r5),
    }
    for name, (ls, sp, rf) in variants.items():
        calls.append(call("rollup", f"E-K05 {name}", cfg=FLIGHT, lines=ls, xe_split=sp, refs=rf))
    c1_none = {"line": "AL-C1", "value": {"value_kg": None, "governs": None}}
    c1_val = {"line": "AL-C1", "value": {"value_kg": 0.5, "governs": "ALLOCATION_MEV"}}
    calls.append(call("rollup", "E-K06 cfg C1", "DIV-K01", cfg="hall_c1_reference", lines=l5, xe_split=s5, refs=r5))
    calls.append(call("rollup", "E-K06 cfg X", "DIV-K01", cfg="X", lines=l5, xe_split=s5, refs=r5))
    calls.append(call("rollup", "E-K06 AL-C1 None", "DIV-K02", cfg=FLIGHT, lines=l5[:-1] + [c1_none] + l5[-1:], xe_split=s5,
                      refs=r5))
    calls.append(call("rollup", "E-K06 AL-C1 0.5", "DIV-K02", cfg=FLIGHT, lines=l5[:-1] + [c1_val] + l5[-1:], xe_split=s5,
                      refs=r5))
    # ---- randomized domain
    gens = {
        0: ("rk", 2000, lambda r: dict(x=mass(r))),
        1: ("line_mev_value", 1200, lambda r: dict(
            allocation_kg=None if r.random() < 0.3 else mass(r), cbe_kg=None if r.random() < 0.3 else mass(r),
            floor_cbe_kg=None if r.random() < 0.3 else mass(r),
            equipment_margin=0.2 if r.random() < 0.9 else r.choice(FRACTIONS))),
        2: ("system_margin", 600, lambda r: dict(pre_margin_kg=mass(r), fraction=0.2 if r.random() < 0.9 else
                                                 r.choice(FRACTIONS), reserve_kg=0.0 if r.random() < 0.9 else
                                                 r.choice(RESERVES))),
        3: ("harness_row60", 600, lambda r: dict(other_nominal_kg=mass(r), fraction=0.05 if r.random() < 0.9 else
                                                 r.choice(FRACTIONS))),
        4: ("closure_state", 800, lambda r: (lambda k: dict(known_kg=k, reference_kg=k if r.random() < 0.2 else mass(r),
                                                            strict=r.random() < 0.5,
                                                            all_resolved=r.random() < 0.5))(mass(r))),
        5: ("_unresolved", 600, lambda r: dict(rec=line_rec(r, r.choice(LIDS + ["AL-HAR"])))),
        6: ("rollup", 1000, lambda r: dict(cfg=FLIGHT, lines=rand_lines(r), xe_split=rand_split(r), refs=rand_refs(r))),
        7: ("system_margin_bid", 600, lambda r: dict(pre_margin_kg=mass(r), fraction=0.1 if r.random() < 0.9 else
                                                     r.choice(FRACTIONS), reserve_kg=0.0 if r.random() < 0.9 else
                                                     r.choice(RESERVES))),
        8: ("assert_no_margin_relaxation", 500, lambda r: dict(reading=mutate_reading(r, OWNER_READING))),
        9: ("assert_bid_margin_reading", 500, lambda r: dict(reading=mutate_reading(r, BID_READING))),
    }
    for k, (fn, n, gen) in gens.items():
        rng = random.Random(seed * 100 + k)
        for i in range(n):
            calls.append(call(fn, f"RND {fn} {i}", **gen(rng)))
    return calls


def k_python(c: dict, mods: dict):
    m3, m5 = mods["m3"], mods["m5"]
    a = copy.deepcopy(c["args"])
    fn = c["fn"]
    if fn == "rk":
        return pc.py_result(m3.rk, a["x"])
    if fn == "_unresolved":
        return pc.py_result(m3._unresolved, a["rec"])
    if fn in ("assert_no_margin_relaxation", "assert_bid_margin_reading"):
        f = m3.assert_no_margin_relaxation if fn == "assert_no_margin_relaxation" else m5.assert_bid_margin_reading
        return pc.py_result(f, a["reading"])
    if fn == "rollup":
        return pc.py_result(m3.rollup, a["cfg"], a["lines"], {k: v for k, v in a["xe_split"]}, [tuple(r) for r in a["refs"]])
    if fn == "system_margin_bid":
        return pc.py_result(m5.system_margin_bid, m3, **a)
    return pc.py_result(getattr(m3, fn), **a)


# =============================================================================================== mass / power v5
PIN_FILES = ["docs/budgets/mass_power_a9_v4/mass_power_a9_v4.json", "docs/budgets/mass_power_a9_v4/MASS_POWER_A9_V4.md",
             V4B, V3B, "docs/decisions/OD_2026_10_05_A9_26_MASS_BUDGET_OWNER_DECISIONS.md",
             "docs/decisions/OD_2026_10_05_A9_26_mass_budget_owner_decisions.json"]
A926_MD, A926_JS = PIN_FILES[4], PIN_FILES[5]


TREE_SPECS = {"CT-00": [], **{f"CT-0{i}": [("APPEND_NL", p)] for i, p in enumerate(PIN_FILES, 1)},
              "CT-07": [("APPEND_NL", PIN_FILES[0]), ("APPEND_NL", A926_MD)], "CT-08": [("DELETE", V3B)],
              "CT-11": [("MD_DUP_HEADING",)], "CT-12": [("MD_SHA_TOKEN",)], "CT-13": [("MD_TEXT",)],
              "CT-14": [("JSON_MSG2_SHA",)], "CT-15": [("JSON_VERBATIM_SHA",)]}
W_SPECS = {"W0": "the committed record", "RT-01": "AL-03 cbe_kg = 1.0", "RT-02": "AL-05 measured_kg = 2.0",
           "RT-03": "every HARD_40_WET wet row of rollups[0] removed", "RT-04": "rollups[0] duplicated",
           "RT-05": "lines['hall_icp_neutralizer'] removed",
           "RT-06": "the 2 kg HARD_40_WET row state set to 'CLOSES'"}


def make_tree(base: Path, name: str, edits: list) -> Path:
    t = base / name
    for rel in [V5B] + PIN_FILES:
        (t / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, t / rel)
    for e in edits:
        kind, *arg = e
        if kind == "APPEND_NL":
            with open(t / arg[0], "ab") as fh:
                fh.write(b"\n")
        elif kind == "DELETE":
            (t / arg[0]).unlink()
        elif kind in ("MD_DUP_HEADING", "MD_SHA_TOKEN", "MD_TEXT"):
            p = t / A926_MD
            md = p.read_bytes().decode("utf-8")
            head_line = next(x for x in md.split("\n") if x.startswith("## Message 2 — "))
            if kind == "MD_DUP_HEADING":
                md = md + "\n" + head_line + "\n"
            elif kind == "MD_SHA_TOKEN":
                assert md.count("text sha256 `c240fca3") == 1
                md = md.replace("text sha256 `c240fca3", "text sha256 `c240fca4")
            else:
                i = md.index(head_line)
                j = md.index("SYSTEM-LEVEL MASS MARGIN = 10%", i)
                md = md[:j] + "SYSTEM-LEVEL MASS MARGIN = 11%" + md[j + len("SYSTEM-LEVEL MASS MARGIN = 10%"):]
            p.write_bytes(md.encode("utf-8"))
        elif kind in ("JSON_MSG2_SHA", "JSON_VERBATIM_SHA"):
            p = t / A926_JS
            js = json.loads(p.read_text(encoding="utf-8"))
            if kind == "JSON_MSG2_SHA":
                next(m for m in js["messages"] if m["n"] == 2)["text_sha256"] = "0" * 64
            else:
                js["verbatim"]["sha256"] = "0" * 64
            p.write_text(json.dumps(js, indent=1, ensure_ascii=False), encoding="utf-8")
        else:
            raise ValueError(kind)
    return t


def w_tree(base: Path, name: str, edit=None) -> Path:
    t = base / name
    p = t / REC["v5"]
    p.parent.mkdir(parents=True, exist_ok=True)
    if edit is None:
        shutil.copy2(ROOT / REC["v5"], p)
    else:
        d = json.loads((ROOT / REC["v5"]).read_text(encoding="utf-8"))
        edit(d)
        p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return t


def _set_line(d, lid, **kv):
    next(x for x in d["lines"][FLIGHT] if x["line"] == lid).update(kv)


RT_EDITS = {
    "RT-01": lambda d: _set_line(d, "AL-03", cbe_kg=1.0),
    "RT-02": lambda d: _set_line(d, "AL-05", measured_kg=2.0),
    "RT-03": lambda d: d["rollups"][0].update(wet=[w for w in d["rollups"][0]["wet"] if w["reference"] != "HARD_40_WET"]),
    "RT-04": lambda d: d.update(rollups=d["rollups"] + [copy.deepcopy(d["rollups"][0])]),
    "RT-05": lambda d: d["lines"].pop(FLIGHT),
    "RT-06": lambda d: next(w for w in d["rollups"][0]["wet"] if w["reference"] == "HARD_40_WET"
                            and w["xe_case_kg"] == 2.0).update(state="CLOSES"),
}


def wet_pools():
    isy = importlib.import_module("abep_sim.design.intake_synthesis")
    labelled = {"f1q02": isy.f1q02_label(), "m_intake_kg": 1.2}
    designs = [None, {}, {"AL-02": {"m": 1.0}}, {"AL-01": labelled}, {"AL-01": {"f1q02": {"label": "PARAMETRIC_SENSITIVITY"}}},
               {"AL-01": 3.0}]
    good = {"all_terms_resolved": True, "value": 39.0, "evidence_class": "measured", "source": "s"}
    supplied = [None, {}, {"all_terms_resolved": False}, good, dict(good, parametric=True),
                dict(good, evidence_class="allocation"), dict(good, evidence_class="SYNTHETIC_TEST_DATA_NOT_EVIDENCE"),
                dict(good, value=39), dict(good, value=True), dict(good, value="39"), dict(good, value=NAN),
                dict(good, value=None), {k: v for k, v in good.items() if k != "source"},
                {k: v for k, v in good.items() if k != "evidence_class"}, {k: v for k, v in good.items() if k != "value"}]
    return designs, supplied


def v5_calls(seed: int, tmp: Path) -> tuple[list, dict]:
    recs = records()
    v4, v5 = recs["v4"], recs["v5"]
    l4, l5 = v4["lines"][FLIGHT], v5["lines"][FLIGHT]
    s4, r4, _ = split_and_refs(v4)
    calls, trees = [], {}
    for name, edits in TREE_SPECS.items():
        trees[name] = make_tree(tmp, name, edits)
    for name in ["CT-00"] + [f"CT-0{i}" for i in range(1, 9)]:
        calls.append(call("build_doc_v5", f"R-V02 {name}", repo=str(trees[name])))
    for name in ("CT-00", "CT-11", "CT-12", "CT-13", "CT-14", "CT-15"):
        calls.append(call("a9_26_message2", f"R-V03 {name}", repo=str(trees[name])))
    for lines, fr, tag in ((l4, 0.2, "v4 0.20"), (l5, 0.1, "v5 0.10"), (l5, 0.2, "v5 0.20"), (l4, 0.1, "v4 0.10")):
        calls.append(call("rollup_v5", f"R-V04 {tag}", cfg=FLIGHT, lines=lines, xe_split=s4, refs=r4, fraction=fr))
    for v, ls in (("v4", l4), ("v5", l5)):
        for ln in ls:
            calls.append(call("unresolved_v5", f"R-V05 {v} {ln['line']}", rec=ln))
            calls.append(call("set_al09", f"R-V06 {v} {ln['line']}", line=ln))
    w0 = w_tree(tmp, "W0")
    trees["W0"] = w0
    designs, supplied = wet_pools()
    for cfg in (FLIGHT, "hall_c1_reference", "X"):
        calls.append(call("wet_mass", f"R-V07 cfg {cfg}", repo=str(w0), config=cfg))
    for i, dm in enumerate(designs):
        calls.append(call("wet_mass", f"R-V07 design {i}", repo=str(w0), config=FLIGHT, design_masses=dm))
    for i, sp in enumerate(supplied):
        calls.append(call("wet_mass", f"R-V07 supplied {i}", repo=str(w0), config=FLIGHT, supplied=sp))
    for name, ed in RT_EDITS.items():
        trees[name] = w_tree(tmp, name, ed)
        calls.append(call("wet_mass", f"R-V08 {name}", repo=str(trees[name]), config=FLIGHT))
    for name in ["W0"] + list(RT_EDITS):
        calls.append(call("wet_mass_pinned", f"DIV-V03 {name}", "DIV-V03", repo=str(trees[name]), config=FLIGHT))
    # ---- edge cases
    for fr in (0.1, 0.2, 0.05, 0.0, 0.30000000000000004, True, None):
        calls.append(call("rollup_v5", "E-V01", cfg=FLIGHT, lines=l5, xe_split=s4, refs=r4, fraction=fr))
    al09_none = [dict(x, value={"value_kg": None, "governs": None}) if x["line"] == "AL-09" else x for x in l5]
    ev2 = {"AL-09 None 0.10": (al09_none, s4, 0.1), "loaded mismatch": (l5, [[2.0, {"loaded_kg": 3.0, "residual_kg": 0.1}]], 0.1),
           "only AL-HAR": ([x for x in l5 if x["line"] == "AL-HAR"], s4, 0.1),
           "AL-HAR missing": ([x for x in l5 if x["line"] != "AL-HAR"], s4, 0.1),
           "int values": ([dict(x, value={"value_kg": int(x["value"]["value_kg"]), "governs": "ALLOCATION_MEV"})
                           if x["line"] in ("AL-01", "AL-02") else x for x in l5], s4, 0.1)}
    for name, (ls, sp, fr) in ev2.items():
        calls.append(call("rollup_v5", f"E-V02 {name}", cfg=FLIGHT, lines=ls, xe_split=sp, refs=r4, fraction=fr))
    calls.append(call("rollup_v5", "E-V02 cfg C1", "DIV-V01", cfg="hall_c1_reference", lines=l5, xe_split=s4, refs=r4,
                      fraction=0.1))
    calls.append(call("rollup_v5", "E-V02 AL-C1", "DIV-V02", cfg=FLIGHT, lines=l5[:-1] + [
        {"line": "AL-C1", "value": {"value_kg": 0.5, "governs": "ALLOCATION_MEV"}}] + l5[-1:], xe_split=s4, refs=r4,
                      fraction=0.1))
    base09 = next(x for x in l5 if x["line"] == "AL-09")
    for v in (1.0, 1, 0.5, 2.5e-07, 1234567.0, True, None, "x"):
        calls.append(call("unresolved_v5", "E-V03", rec=dict(base09, value={"value_kg": v, "governs": "ALLOCATION_MEV"})))
    v409 = next(x for x in l4 if x["line"] == "AL-09")
    ev4 = [dict(v409, row54_combined_allocation_kg=1), dict(v409, row54_combined_allocation_kg=2.0),
           {k: v for k, v in v409.items() if k != "row54_combined_allocation_kg"},
           dict(v409, value={"value_kg": 0.0, "governs": None}), dict(v409, line="AL-9"),
           {k: v for k, v in v409.items() if k != "allocation_status"},
           {k: v for k, v in v409.items() if k != "owner_answers_applied"}]
    for ln in ev4:
        calls.append(call("set_al09", "E-V04", line=ln))
    # ---- randomized domain
    rng = random.Random(seed * 100 + 2)
    for i in range(600):
        fr = 0.1 if (u := rng.random()) < 0.45 else 0.2 if u < 0.9 else rng.choice([0.05, 0.0, 0.30000000000000004, True, None])
        calls.append(call("rollup_v5", f"RND rollup_v5 {i}", cfg=FLIGHT, lines=rand_lines(rng), xe_split=rand_split(rng),
                          refs=rand_refs(rng), fraction=fr))
    rng = random.Random(seed * 100 + 3)
    for i in range(400):
        lid = "AL-09" if rng.random() < 0.5 else rng.choice(LIDS + ["AL-HAR"])
        calls.append(call("unresolved_v5", f"RND unresolved_v5 {i}", rec=line_rec(rng, lid)))
    rng = random.Random(seed * 100 + 4)
    muts = {"row54_combined_allocation_kg": [1.0, 1, 2.0, None, "ABSENT"], "value": [{"value_kg": None, "governs": None},
                                                                               {"value_kg": 0.0, "governs": None},
                                                                               {"value_kg": 1.0, "governs": "ALLOCATION_MEV"}],
            "line": ["AL-09", "AL-9", "AL-08"], "allocation_status": ["ABSENT", "TBD"],
            "owner_answers_applied": ["ABSENT", [], ["x"], "str"]}
    for i in range(300):
        ln = copy.deepcopy(v409)
        for _ in range(rng.randint(0, 2)):
            k = rng.choice(list(muts))
            val = rng.choice(muts[k])
            if val == "ABSENT":
                ln.pop(k, None)
            else:
                ln[k] = val
        calls.append(call("set_al09", f"RND set_al09 {i}", line=ln))
    rng = random.Random(seed * 100 + 7)
    for i in range(300):
        u = rng.random()
        cfg = FLIGHT if u < 0.8 else "hall_c1_reference" if u < 0.9 else "X"
        calls.append(call("wet_mass", f"RND wet_mass {i}", repo=str(w0), config=cfg, design_masses=rng.choice(designs),
                          supplied=rng.choice(supplied)))
    return calls, trees


def v5_python(c: dict, mods: dict):
    a = copy.deepcopy(c["args"])
    fn = c["fn"]
    m3, m5, ao = mods["m3"], mods["m5"], mods["ao"]
    if fn == "rollup_v5":
        return pc.py_result(m5.rollup_v5, m3, a["cfg"], a["lines"], {k: v for k, v in a["xe_split"]},
                            [tuple(r) for r in a["refs"]], a["fraction"])
    if fn == "unresolved_v5":
        return pc.py_result(m5.unresolved_v5, m3, a["rec"])
    if fn == "set_al09":
        return pc.py_result(m5.set_al09, a["line"], m3)
    if fn in ("build_doc_v5", "a9_26_message2"):
        tree = Path(a["repo"])
        mod = load(V5B, f"build_v5_tree_{tree.name}_{fn}", tree)
        if fn == "a9_26_message2":
            return pc.py_result(mod.a9_26_message2)

        def build():
            d = mod.build_doc()
            js = json.dumps(d, indent=1, ensure_ascii=False) + "\n"
            md = mod.render_md(d)
            return {"json_sha256": pc.sha_bytes(js.encode("utf-8")), "md_sha256": pc.sha_bytes(md.encode("utf-8"))}
        return pc.py_result(build)
    if fn in ("wet_mass", "wet_mass_pinned"):
        return pc.py_result(ao.wet_mass, a["config"], a.get("design_masses"), a.get("supplied"), repo=Path(a["repo"]))
    raise ValueError(fn)


# =============================================================================================== Xe accounting v3
def xe_inputs(mx):
    v2 = mx._load(mx.V2["V2_JSON"][0])
    s = mx.S()
    items = mx.build_items(v2, s)
    lines = mx.build_lines(v2, s)
    scen = mx.build_scenarios(v2)
    return items, lines, scen


PRESENCE = ["EXACT_ZERO_BY_OWNER_DECISION", "ABSENT_BY_OWNER_DECISION", "ZERO_BY_SCOPE", "ZERO_XE_BY_OWNER_DECISION",
            "PRESENT", "CONDITIONAL", "PRESENT_WHEN_ACTIVATED"]


def xe_calls(seed: int, mx) -> list:
    items, lines, scen = xe_inputs(mx)
    idx = {i["id"]: i for i in items}
    ld = {ln["id"]: ln for ln in lines}
    calls = [call("evaluate", "R-X01", lines=lines, items=idx, scenarios=scen)]
    f_rsv, f_res = idx["XV2-23"]["value"], idx["XV2-24"]["value"]
    for sc in scen:
        done = {}
        for lid in sorted(sc["lines"], key=lambda x: ld[x]["kind"] == "fraction_of_lines"):
            calls.append(call("eval_line", f"R-X01 {sc['id']} {lid}", ln=ld[lid], items=idx, done=done))
            done[lid] = mx.eval_line(ld[lid], idx, done)
        evals = [done[lid] for lid in sc["lines"]]
        if sc["ledger"] == "FLIGHT":
            calls.append(call("book_reserve_and_residual", f"R-X01 {sc['id']}", evals=evals, lines=ld, f_reserve=f_rsv,
                              f_residual=f_res))
        else:
            calc = {e["line"]: e["kg"] for e in evals if ld[e["line"]]["phase"] != "procedure"}
            procs = {ld[e["line"]]["procedure_category"]: e["kg"] for e in evals if ld[e["line"]]["phase"] == "procedure"}
            calls.append(call("ground_supply", f"R-X01 {sc['id']}", calculated_kg=calc, procedures_kg=procs))
    for c in idx["XV2-30"]["value"]:
        calls.append(call("case_split_loaded", f"R-X02 {c}", case_kg=c, f_reserve=f_rsv, f_residual=f_res))
    calls.append(call("case_split_loaded", "R-X02", case_kg=2.0, f_reserve=0.2, f_residual=0.02, reading="USABLE_RESIDUAL_ON_TOP"))
    calls.append(call("case_split_loaded", "R-X02", case_kg=NAN, f_reserve=0.2, f_residual=0.02))
    calls.append(call("ignition_booking_s", "R-X03"))
    for bad in (4, 0, 2.5, True):
        calls.append(call("ignition_booking_s", "R-X03", attempts=bad))
    calls.append(call("ignition_booking_s", "R-X03", attempts=3, dwell_s=121.0))
    calls.append(call("ignition_booking_s", "R-X03", attempts=3, dwell_s=100.0))
    calls.append(call("ignition_booking_s", "R-X03", attempts=3, dwell_s=100.0, evidence="measured H-1 start log"))
    tl = {"A": {"phase": "xe_mode", "reserve_base": True}, "B": {"phase": "transition", "reserve_base": True}}
    for ev, lm in (([{"line": "A", "kg": 1.0}, {"line": "B", "kg": 0.5}], tl),
                   ([{"line": "A", "kg": 1.0}, {"line": "A", "kg": 1.0}], tl),
                   ([{"line": "RESIDUAL", "kg": 1.0}], dict(tl, RESIDUAL={"phase": "residual", "reserve_base": True})),
                   ([{"line": "A", "kg": None}], tl),
                   ([{"line": "A", "kg": 1.0}], {"A": {"phase": "xe_mode", "reserve_base": "RA-FLOWUNC"}})):
        calls.append(call("book_reserve_and_residual", "R-X04", evals=ev, lines=lm, f_reserve=0.2, f_residual=0.02))
    procs = {"purge": 0.1, "conditioning": 0.2, "line_fill": 0.05, "vendor_procedures": 0.15}
    calls.append(call("ground_supply", "R-X05", calculated_kg={"ref": 1.5}, procedures_kg=procs))
    calls.append(call("ground_supply", "R-X05", calculated_kg={"ref": 1.0}, procedures_kg=procs, margin=0.1))
    calls.append(call("ground_supply", "R-X05", calculated_kg={"ref": 1.0}, procedures_kg={"purge": 0.1}))
    calls.append(call("ground_supply", "R-X05", calculated_kg={"ref": 1.0}, procedures_kg=dict(procs, line_fill=None)))
    # ---- edge cases
    for v in (0.0, -0.0, -1.0, NAN, INF, True, "2", None, 0, 1e-300, 1e300):
        calls.append(call("case_split_loaded", "E-X01 case", case_kg=v, f_reserve=0.2, f_residual=0.02))
        calls.append(call("case_split_loaded", "E-X01 f_reserve", case_kg=5.0, f_reserve=v, f_residual=0.02))
        calls.append(call("case_split_loaded", "E-X01 f_residual", case_kg=5.0, f_reserve=0.2, f_residual=v))
    for rd in ("LOADED", "USABLE_RESIDUAL_ON_TOP", "loaded", 1, None):
        calls.append(call("case_split_loaded", "E-X01 reading", case_kg=5.0, f_reserve=0.2, f_residual=0.02, reading=rd))
    for at in (1, 2, 3, 0, 4, -1, 3.0, True, False, "3", None):
        calls.append(call("ignition_booking_s", "E-X02 attempts", attempts=at))
    for dw in (120.0, 120, 60.0, 0.0, -1.0, 120.0000001, 1e-300, NAN, INF, True, None):
        for evd in (None, "", "   ", "\t\n", "log", 5):
            calls.append(call("ignition_booking_s", "E-X02 dwell", attempts=2, dwell_s=dw, evidence=evd))
    lmap = {"A": {"phase": "xe_mode", "reserve_base": True}, "B": {"phase": "start", "reserve_base": True},
            "R": {"phase": "reserve", "reserve_base": True}, "N1": {"phase": "xe_mode", "reserve_base": 1},
            "N2": {"phase": "xe_mode", "reserve_base": None}, "N3": {"phase": "xe_mode", "reserve_base": False}}
    ex3 = [([{"line": "A", "kg": 1.0}], None, 0.02), ([{"line": "A", "kg": 1.0}], 0.2, None),
           ([{"line": "A", "kg": 0.0}, {"line": "B", "kg": 0.0}], 0.2, 0.02), ([{"line": "A", "kg": 0}], 0.2, 0.02),
           ([{"line": "A", "kg": None}, {"line": "B", "kg": 2.5}], 0.2, 0.02), ([{"line": "R", "kg": 1.0}], 0.2, 0.02),
           ([{"line": "RESERVE", "kg": 1.0}], 0.2, 0.02), ([{"line": "N1", "kg": 1.0}], 0.2, 0.02),
           ([{"line": "N2", "kg": 1.0}], 0.2, 0.02), ([{"line": "N3", "kg": 1.0}], 0.2, 0.02),
           ([{"line": "ZZ", "kg": 1.0}], 0.2, 0.02), ([{"line": "A", "kg": 1.0}], 0, 0.02), ([], 0.2, 0.02)]
    for ev, fr, fs in ex3:
        calls.append(call("book_reserve_and_residual", "E-X03", evals=ev, lines=lmap, f_reserve=fr, f_residual=fs))
    for mg in (0.2, 0.20000000000000001, 0.1, 0, None):
        calls.append(call("ground_supply", "E-X04 margin", calculated_kg={"ref": 1.0}, procedures_kg=procs, margin=mg))
    for pr in ({k: procs[k] for k in ("purge", "conditioning", "line_fill")}, dict(procs, extra=0.1),
               {k: procs[k] for k in reversed(list(procs))}):
        calls.append(call("ground_supply", "E-X04 keys", calculated_kg={"ref": 1.0}, procedures_kg=pr))
    for calc, pr in (({"ref": None}, procs), ({"ref": 1.0}, dict(procs, purge=0.0)), ({"ref": -1.0}, procs),
                     ({"ref": NAN}, procs), ({}, procs), ({"purge": 9.0, "x": 1.0}, procs)):
        calls.append(call("ground_supply", "E-X04 values", calculated_kg=calc, procedures_kg=pr))
    base = next(x for x in lines if x["kind"] == "product")
    frac = next(x for x in lines if x["kind"] == "fraction_of_lines")
    mass_ln = next(x for x in lines if x["kind"] == "mass")
    for p in PRESENCE + ["CONDITIONAL_ON_C1_FLIGHT_SELECTION", "ABSENT_UNDER_READING"]:
        calls.append(call("eval_line", f"E-X05 presence {p}", ln=dict(base, presence=p), items=idx, done={}))
    c1 = next((x for x in lines if x["configuration"] == "hall_c1_reference" and x["ledger"] == "FLIGHT"), base)
    calls.append(call("eval_line", "E-X05 pending retired", ln=dict(c1, presence="CONDITIONAL_ON_C1_FLIGHT_SELECTION"),
                      items=idx, done={}))
    calls.append(call("eval_line", "E-X05 unknown kind", ln=dict(base, kind="other"), items=idx, done={}))
    vals = {f["item"]: idx[f["item"]] for f in base["fields"]}
    for v in (None, "x", -1.0, 3.0, 0, True):
        it2 = dict(idx, **{k: dict(i, value=v) for k, i in vals.items()})
        calls.append(call("eval_line", f"E-X05 item value {v!r}", ln=base, items=it2, done={}))
    calls.append(call("eval_line", "E-X05 unknown unit", ln=dict(base, fields=[dict(base["fields"][0], unit="lb")]),
                      items=dict(idx, **{base["fields"][0]["item"]: dict(idx[base["fields"][0]["item"]], value=1.0)}),
                      done={}))
    calls.append(call("eval_line", "E-X05 unknown item", ln=dict(base, fields=[dict(base["fields"][0], item="XV9-99")]),
                      items=idx, done={}))
    calls.append(call("eval_line", "E-X05 mass line", ln=mass_ln, items=idx, done={}))
    done_tbd = {x: {"line": x, "kg": None} for x in frac["of_lines"]}
    done_ok = {x: {"line": x, "kg": 0.5} for x in frac["of_lines"]}
    fi = frac["fields"][0]["item"]
    for dn, iv in ((done_tbd, None), (done_ok, None), (done_ok, 0.05), (done_tbd, 0.05)):
        it2 = dict(idx, **{fi: dict(idx[fi], value=iv)})
        calls.append(call("eval_line", "E-X05 fraction", ln=frac, items=it2, done=dn))
    # ---- randomized domain
    rng = random.Random(seed * 100 + 1)

    def xnum(r, lo, hi):
        if r.random() < 0.03:
            return r.choice([-1.0, NAN, INF, True, "2", None])
        return 10 ** r.uniform(math.log10(lo), math.log10(hi)) if r.random() < 0.7 else round(r.uniform(0, 20), r.randint(0, 6))

    def frac_draw(r):
        if r.random() < 0.03:
            return r.choice([-1.0, NAN, INF, True, "2", None])
        u = r.random()
        return 0.0 if u < 0.1 else r.uniform(0, 1e3) if u < 0.15 else r.uniform(0, 1)

    for i in range(1000):
        calls.append(call("case_split_loaded", f"RND case_split {i}", case_kg=xnum(rng, 1e-3, 1e3), f_reserve=frac_draw(rng),
                          f_residual=frac_draw(rng)))
    rng = random.Random(seed * 100 + 2)
    for i in range(600):
        at = rng.choice([1, 2, 3]) if rng.random() < 0.8 else rng.choice([0, 4, -1, 3.0, True, False, "3", None])
        dw = 120.0 if rng.random() < 0.2 else rng.uniform(0, 150)
        calls.append(call("ignition_booking_s", f"RND ignition {i}", attempts=at, dwell_s=dw,
                          evidence=rng.choice([None, "", "   ", "\t\n", "log", 5])))
    rng = random.Random(seed * 100 + 3)
    for i in range(600):
        lm = {f"L{j}": {"phase": rng.choice(["xe_mode", "transition", "start", "reserve", "residual"]),
                        "reserve_base": rng.random() < 0.9} for j in range(8)}
        ev = [{"line": f"L{j}", "kg": rng.choice([None, 0.0, xnum(rng, 1e-4, 10)])} for j in rng.sample(range(8), rng.randint(0, 8))]
        fr, fs = (0.2, 0.02) if rng.random() < 0.8 else (rng.uniform(0, 1), rng.uniform(0, 1))
        calls.append(call("book_reserve_and_residual", f"RND book {i}", evals=ev, lines=lm, f_reserve=fr, f_residual=fs))
    rng = random.Random(seed * 100 + 4)
    for i in range(600):
        calc = {f"c{j}": rng.choice([None, 0.0, xnum(rng, 1e-4, 10)]) for j in range(rng.randint(0, 5))}
        pr = {k: rng.choice([None, 0.0, xnum(rng, 1e-4, 1)]) for k in ("purge", "conditioning", "line_fill", "vendor_procedures")}
        if rng.random() > 0.9:
            pr.pop(rng.choice(list(pr)))
        calls.append(call("ground_supply", f"RND ground {i}", calculated_kg=calc, procedures_kg=pr,
                          margin=0.2 if rng.random() < 0.9 else rng.choice([0.1, 0.25, 0, None])))
    rng = random.Random(seed * 100 + 6)
    for i in range(500):
        u = rng.random()
        it2 = {}
        for k, it in idx.items():
            w = rng.random()
            nv = it["value"] if w < 0.5 else None if w < 0.75 else xnum(rng, 1e-3, 1e4)
            it2[k] = dict(it, value=nv)
        ls2 = [dict(x) for x in lines]
        if u >= 0.6:
            for x in ls2:
                if u < 0.9 and rng.random() < 0.1:
                    x["presence"] = rng.choice(PRESENCE)
            if u >= 0.9:
                rng.choice(ls2)["presence"] = rng.choice(["CONDITIONAL_ON_C1_FLIGHT_SELECTION", "ABSENT_UNDER_READING"])
        calls.append(call("evaluate", f"RND evaluate {i}", lines=ls2, items=it2, scenarios=scen))
    return calls


def xe_python(c: dict, mods: dict):
    mx = mods["mx"]
    a = copy.deepcopy(c["args"])
    fn = c["fn"]
    if fn == "evaluate":
        return pc.py_result(mx.evaluate, a["lines"], a["items"], a["scenarios"])
    if fn == "eval_line":
        return pc.py_result(mx.eval_line, a["ln"], a["items"], a["done"])
    return pc.py_result(getattr(mx, fn), **a)


# =============================================================================================== runner
def rust_binary() -> Path:
    env = dict(os.environ, PATH=f"/root/.cargo/bin:{os.environ.get('PATH', '')}", CARGO_INCREMENTAL="0",
               CARGO_PROFILE_RELEASE_DEBUG="0")
    subprocess.run(["cargo", "build", "--release", "--locked", "-p", "abep-subsystems", "--bin", "abep-mass"], cwd=ROOT,
                   check=True, env=env, capture_output=True)
    return ROOT / "target" / "release" / "abep-mass"


def rust_eval(binary: Path, calls: list, work: Path, tag: str) -> list:
    p = work / f"calls_{tag}.json"
    p.write_text(json.dumps([{"fn": c["fn"], "args": c["args"]} for c in calls]), encoding="utf-8")
    r = subprocess.run([str(binary), "eval", str(p)], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"abep-mass eval failed ({r.returncode}): {r.stderr.decode()[:2000]}")
    return json.loads(r.stdout)


def expected_div(c: dict, tree_sha=None):
    if c["div"] in ("DIV-K01", "DIV-V01"):
        return {"outcome": "RAISED", "class": "MassError", "message": DIV_CFG.format(cfg=repr(c["args"]["cfg"]))}
    if c["div"] in ("DIV-K02", "DIV-V02"):
        return {"outcome": "RAISED", "class": "MassError", "message": DIV_C1}
    if c["div"] == "DIV-V03":
        repo = Path(c["args"]["repo"])
        actual = pc.sha_file(repo / REC["v5"])
        if actual == RECORD_SHA:
            return None  # equals wet_mass: compared against Python
        return {"outcome": "RAISED", "class": "PinError", "message": DIV_PIN.format(actual=actual)}
    raise ValueError(c["div"])


def compare_all(calls, py, rs, message_classes):
    fails, div_obs = [], []
    by_fn = {}
    for c, p, r in zip(calls, py, rs):
        st = by_fn.setdefault(c["fn"], {"n": 0, "pass": 0, "fail": 0})
        st["n"] += 1
        want = p
        if c.get("div"):
            exp = expected_div(c)
            if exp is not None:
                want = exp
                div_obs.append({"div": c["div"], "tag": c["tag"], "python": p, "rust": r,
                                "rust_matches_registered": r == exp})
        d = pc.compare(want, r, message_classes)
        if d:
            st["fail"] += 1
            fails.append({"fn": c["fn"], "tag": c["tag"], "diff": d[0][:1500]})
        else:
            st["pass"] += 1
    return by_fn, fails, div_obs


def returned(results):
    return [r["value"] for r in results if r["outcome"] == "RETURNED"]


def cons_rollups(calls, results):
    """CONS-K01..K03 / CONS-V01..V02 on every returned roll-up."""
    bad, n = [], 0
    for c, r in zip(calls, results):
        if c["fn"] not in ("rollup", "rollup_v5") or r["outcome"] != "RETURNED":
            continue
        v = r["value"]
        n += 1
        nh, har, nom, sm, dry = (v[k] for k in ("nonharness_known_kg", "harness_kg", "nominal_dry_known_kg",
                                                "system_margin_kg", "dry_known_kg"))
        tol = 2e-9 * max(1.0, abs(nom))
        if not (abs(nom - (nh + har)) <= tol and abs(nom - nh / 0.95) <= tol):
            bad.append(("CONS-01", c["tag"]))
        if not abs(sm + nom - dry) <= 2e-9 * max(1.0, abs(dry)):
            bad.append(("CONS-02", c["tag"]))
        for w in v["wet"]:
            if w["residual_added_on_top_kg"] != 0.0 or w["wet_known_kg"] != float(f"{dry + w['xe_loaded_kg']:.10g}"):
                bad.append(("CONS-03", c["tag"]))
    return n, bad


def inv_rollup_identity(calls, results, mods):
    m3 = mods["m3"]
    bad = []
    for c, r in zip(calls, results):
        if c["fn"] != "rollup" or r["outcome"] != "RETURNED":
            continue
        v = r["value"]
        known = [p["kg"] for p in v["parts"] if p["line"] != "AL-HAR" and p["kg"] is not None]
        nh = m3.rk(sum(known))
        ok = (v["nonharness_known_kg"] == nh and v["harness_kg"] == m3.rk(nh * 0.05 / 0.95)
              and v["nominal_dry_known_kg"] == m3.rk(nh + v["harness_kg"])
              and v["dry_known_kg"] == m3.rk(v["nominal_dry_known_kg"] * 1.2)
              and v["system_margin_kg"] == m3.rk(0.2 * v["nominal_dry_known_kg"]))
        if not ok:
            bad.append(c["tag"])
    return bad


def no_pass(results):
    s = json.dumps(returned(results))
    states = {"CLOSES", "DOES_NOT_CLOSE", "NOT_EVALUABLE"}
    bad = '"PASS"' in s
    for v in returned(results):
        if isinstance(v, dict) and "wet" in v:
            bad |= v["all_terms_resolved"] is not False
            bad |= any(w["state"] not in states or (w["reference"] == "HARD_40_WET" and w["state"] == "CLOSES")
                       for w in v["wet"])
    return not bad


def provenance(paths):
    return pc.source_sha256(paths)


RUST_SOURCES = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/abep-types/**", "crates/abep-provenance/**",
                "crates/abep-subsystems/Cargo.toml", "crates/abep-subsystems/src/lib.rs",
                "crates/abep-subsystems/src/mass/**", "crates/abep-subsystems/src/bin/abep-mass.rs"]


def contract_of(key):
    cid = CONTRACTS[key]
    p = ROOT / "docs/rust_migration/contracts" / cid / "parity_prereg_v1.json"
    return cid, p, json.loads(p.read_text(encoding="utf-8"))


def reference_check(contract):
    return {f["path"]: {"registered": f["sha256_at_registration"], "now": pc.sha_file(ROOT / f["path"])}
            for f in contract["reference_implementation"]["files"]}


def pinned_check(contract):
    return {p: {"registered": s, "now": pc.sha_file(ROOT / p) if (ROOT / p).exists() else None}
            for p, s in contract["pinned_inputs_sha256"].items()}


def median_time(fn, repeats=3):
    return pc.timed(fn, repeats)


def run(key: str, score: bool, dry_dir: Path | None = None) -> int:
    cid, cpath, contract = contract_of(key)
    seed = contract["campaign_seeds"]["scoring_master_seed" if score else "development_master_seed"]
    refs = reference_check(contract)
    changed = [p for p, v in refs.items() if v["registered"] != v["now"]]
    if changed:
        print(f"REFUSED_REFERENCE_CHANGED: {changed}")
        return 2
    pins = pinned_check(contract)
    pin_bad = [p for p, v in pins.items() if v["registered"] != v["now"]]
    if pin_bad:
        print(f"INPUT_MISMATCH: {pin_bad}")
        return 2
    out_dir = dry_dir if dry_dir is not None else cpath.parent
    if score and (out_dir / "parity_report_v1.json").exists():
        print("refused: parity_report_v1.json exists (the scoring seed is spent once per contract version)")
        return 2
    binary = rust_binary()
    mods = {"m3": load(V3B, "k_v3"), "m5": load(V5B, "k_v5")}
    tmp = Path(tempfile.mkdtemp(prefix=f"parity_{key}_"))
    extra = {}
    v5_trees = None
    t0 = time.time()
    if key == "k-mass-rules":
        calls = k_calls(seed)
        pyf, msg = k_python, {"MassError", "MassPolicyError"}
    elif key == "mass-power-v5":
        mods["ao"] = importlib.import_module("abep_sim.design.architecture_optimizer")
        calls, v5_trees = v5_calls(seed, tmp)
        pyf, msg = v5_python, {"MassError", "MassPolicyError", "PinError", "RuntimeError", "OptimizerError",
                               "IntakeMassUseError"}
    else:
        mods["mx"] = load(XB, "x_v3")
        calls = xe_calls(seed, mods["mx"])
        pyf, msg = xe_python, {"BookingError"}
    py1 = [pyf(c, mods) for c in calls]
    py2 = [pyf(c, mods) for c in calls]
    py_det = pc.canon(py1) == pc.canon(py2)
    rs = rust_eval(binary, calls, tmp, key)
    by_fn, fails, div_obs = compare_all(calls, py1, rs, msg)
    inv, cons = {}, {}
    inv["determinism"] = {"python_twice_identical": py_det, "rust_twice_identical": True,
                          "note": "abep-mass eval evaluates the call list twice and exits 3 on a difference"}
    if key in ("k-mass-rules", "mass-power-v5"):
        n_r, bad_r = cons_rollups(calls, rs)
        n_p, bad_p = cons_rollups(calls, py1)
        cons = {"rollups_checked_rust": n_r, "violations_rust": bad_r, "rollups_checked_python": n_p,
                "violations_python": bad_p, "pass": not bad_r}
        inv["no_pass_rust"] = no_pass(rs)
        inv["no_pass_python"] = no_pass(py1)
    if key == "k-mass-rules":
        inv["INV-K02_rollup_identity_rust_failures"] = inv_rollup_identity(calls, rs, mods)
        inv["INV-K02_rollup_identity_python_failures"] = inv_rollup_identity(calls, py1, mods)
        v5r = next(r for c, r in zip(calls, rs) if c["tag"] == "R-K02 v5" and c["fn"] == "rollup")
        al07p = [p for p in v5r["value"]["parts"] if p["line"] == "AL-07"]
        al07t = [t for t in v5r["value"]["tbd"] if t.startswith("AL-07")]
        inv["VS-K01"] = {"part": al07p, "tbd": al07t,
                         "pass": al07p == [{"line": "AL-07", "used": "MEV_PLANNING_FLOOR", "kg": 6.0}]
                         and al07t == ["AL-07: MEV planning floor from an analog / preliminary-design floor, not a CBE"]}
        e3 = [(c, p, r) for c, p, r in zip(calls, py1, rs) if c["tag"] == "E-K03"]
        inv["INV-K04"] = {"cases": len(e3),
                          "pass_rust": all((r["outcome"] == "RETURNED") == _admitted(c) for c, _p, r in e3),
                          "pass_python": all((p["outcome"] == "RETURNED") == _admitted(c) for c, p, _r in e3)}
        inv["INV-K04"]["pass"] = inv["INV-K04"]["pass_rust"] and inv["INV-K04"]["pass_python"]
    if key == "mass-power-v5":
        extra.update(v5_record_checks(binary, tmp, mods))
        inv.update(extra.pop("invariants"))
    if key == "xe-accounting-v3":
        inv.update(xe_invariants(calls, rs, py1))
        cons = xe_conservation(calls, rs)
    t_run = time.time() - t0
    total = sum(v["n"] for v in by_fn.values())
    n_fail = sum(v["fail"] for v in by_fn.values())
    inv_ok = all(_truthy_inv(k, v) for k, v in inv.items())
    cons_ok = cons.get("pass", True) if cons else True
    e1_ok = extra.get("E1", {}).get("pass", True)
    div_ok = all(d["rust_matches_registered"] for d in div_obs)
    verdict = "ADMITTED" if (n_fail == 0 and inv_ok and cons_ok and e1_ok and div_ok) else "NOT_ADMITTED"
    print(f"{cid}: {total} calls, {n_fail} failing; invariants {'ok' if inv_ok else 'FAIL'}; conservation "
          f"{'ok' if cons_ok else 'FAIL'}; E1 {'ok' if e1_ok else 'FAIL'}; DIV {'ok' if div_ok else 'FAIL'} "
          f"({'SCORING' if score else 'development'} seed {seed}) -> {verdict if score else '(development, no verdict)'}")
    for f in fails[:25]:
        print("  FAIL", f["fn"], f["tag"], f["diff"][:600])
    if not score and dry_dir is None:
        shutil.rmtree(tmp, ignore_errors=True)
        return 0 if n_fail == 0 and inv_ok and cons_ok and e1_ok and div_ok else 1
    if not score:
        verdict = "DEVELOPMENT_DRY_RUN_NOT_A_VERDICT"
        out_dir.mkdir(parents=True, exist_ok=True)
    perf = performance(key, binary, tmp, mods, calls)
    report = make_report(key, cid, cpath, contract, seed, calls, py1, rs, by_fn, fails, div_obs, inv, cons, extra,
                         verdict, perf, t_run, refs, pins)
    base = specs = None
    if key == "xe-accounting-v3":
        items, lines, scen = xe_inputs(mods["mx"])
        idx = {i["id"]: i for i in items}
        base = rt({"BASE_ITEMS": idx, "BASE_LINES": lines, "BASE_SCENARIOS": scen,
                   "BASE_LINE_MAP": {ln["id"]: ln for ln in lines}})
    if key == "mass-power-v5":
        specs = {"case_trees": {k: [list(e) for e in v] for k, v in TREE_SPECS.items()}, "w_trees": W_SPECS}
    write_reference_outputs(out_dir, cid, calls, py1, report, base, v5_trees, specs)
    pc.write_report(out_dir / "parity_report_v1.json", report, report_md(report))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"wrote {out_dir / 'parity_report_v1.json'}")
    return 0


def _admitted(c):
    """INV-K04: the registered margin reading only (Python ==, reserve in (0, 0.0))."""
    a, fn = c["args"], c["fn"]
    want = {"system_margin": 0.2, "system_margin_bid": 0.1, "harness_row60": 0.05, "line_mev_value": 0.2}[fn]
    fr = a.get("equipment_margin" if fn == "line_mev_value" else "fraction", want)
    rs = a.get("reserve_kg", 0.0)
    return fr == want and rs in (0, 0.0)


def _truthy_inv(k, v):
    if isinstance(v, bool):
        return v
    if isinstance(v, list):
        return not v
    if isinstance(v, dict):
        if "pass" in v:
            return bool(v["pass"])
        return all(_truthy_inv(kk, vv) for kk, vv in v.items() if kk != "note")
    return True


def v5_record_checks(binary, tmp, mods):
    m5 = load(V5B, "rec_v5")
    js_py, md_py = m5.render()
    out = tmp / "rust_build"
    r = subprocess.run([str(binary), "build-v5", str(ROOT), str(out)], capture_output=True, text=True)
    js_rs = (out / "mass_power_a9_v5.json").read_bytes() if r.returncode == 0 else b""
    md_rs = (out / "MASS_POWER_A9_V5.md").read_bytes() if r.returncode == 0 else b""
    r2 = subprocess.run([str(binary), "build-v5", str(ROOT), str(tmp / "rust_build2")], capture_output=True, text=True)
    det = r2.returncode == 0 and (tmp / "rust_build2" / "mass_power_a9_v5.json").read_bytes() == js_rs and \
        (tmp / "rust_build2" / "MASS_POWER_A9_V5.md").read_bytes() == md_rs
    sha = pc.sha_bytes
    e1 = {"json": {"python": sha(js_py.encode()), "rust": sha(js_rs), "committed": pc.sha_file(ROOT / REC["v5"])},
          "md": {"python": sha(md_py.encode()), "rust": sha(md_rs), "committed": pc.sha_file(ROOT / V5MD)},
          "rust_build_twice_identical": det}
    e1["pass"] = all(len(set(v.values())) == 1 for k, v in e1.items() if k in ("json", "md")) and det
    rec = json.loads(js_rs.decode()) if js_rs else {}
    roll = rec.get("rollups", [{}])[0]
    hard = {w["xe_case_kg"]: w for w in roll.get("wet", []) if w["reference"] == "HARD_40_WET"}
    want = {"nonharness_known_kg": 33.1196, "harness_kg": 1.743136842, "nominal_dry_known_kg": 34.86273684,
            "system_margin_kg": 3.486273684, "dry_known_kg": 38.34901052}
    inv01 = {"rollup": {k: roll.get(k) for k in want},
             "hard_40_wet": {str(c): (w["wet_known_kg"], w["state"]) for c, w in sorted(hard.items())},
             "mass_status": rec.get("mass_status", {}).get("status")}
    inv01["pass"] = (inv01["rollup"] == want and inv01["hard_40_wet"] == {
        "2.0": (40.34901052, "DOES_NOT_CLOSE"), "5.0": (43.34901052, "DOES_NOT_CLOSE"),
        "10.0": (48.34901052, "DOES_NOT_CLOSE")} and roll.get("lines_without_value") == []
        and inv01["mass_status"] == "MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED"
        and all(abs(roll.get(k, 0) - v) <= 6e-5 for k, v in {"dry_known_kg": 38.3490}.items()))
    inv01["hard_40_wet"] = {k: list(v) for k, v in inv01["hard_40_wet"].items()}
    m3 = mods["m3"]
    nh = roll.get("nonharness_known_kg", 0.0)
    lines = {x["line"]: x for x in rec.get("lines", {}).get(FLIGHT, [])}
    inv02 = {"dry_identity": roll.get("dry_known_kg") == m3.rk(m3.rk(nh + m3.rk(nh * 0.05 / 0.95)) * 1.1),
             "dry_vs_nh_over_095_x_1p1": abs(roll.get("dry_known_kg", 0) - nh / 0.95 * 1.1),
             "line_factors": {lid: lines[lid]["value"]["value_kg"] == m3.rk(lines[lid]["evidence_floor_cbe_kg"] * 1.2)
                              for lid in ("AL-04", "AL-07", "AL-08")} if lines else {},
             "effective_factor": rec.get("margin_audit", {}).get("effective_factor_floor_lines")}
    inv02["pass"] = bool(inv02["dry_identity"] and inv02["dry_vs_nh_over_095_x_1p1"] <= 5e-9 * 38.35
                         and all(inv02["line_factors"].values()) and inv02["effective_factor"] == 1.32)
    flight_ids = [x for x in lines] + [p["line"] for r_ in rec.get("rollups", []) for p in r_["parts"]]
    inv03 = {"flight_ids_without_AL_C1": "AL-C1" not in flight_ids,
             "one_rollup_flight": [r_["configuration"] for r_ in rec.get("rollups", [])] == [FLIGHT],
             "c1_history_equals_v4": all(rec.get(k) == records()["v4"].get(k) for k in (
                 "retired_flight_configuration_history", "c1_mass_check", "ground_article_only", "statuses"))}
    inv03["pass"] = all(inv03.values())
    ms = rec.get("mass_status", {})
    texts = json.dumps([rec.get("closure_vs_40kg"), rec.get("flight_rollup_vs_40kg"), ms.get("status")])
    inv04 = {"pass": "PASS" not in texts.replace("no PASS", "") and all(
        w["state"] != "CLOSES" for w in hard.values())}
    vs = subprocess.run([str(binary), "value-status", str(ROOT)], capture_output=True, text=True)
    vs_got = json.loads(vs.stdout) if vs.returncode == 0 else {"error": vs.stderr}
    vs_want = {"line": "AL-07", "value_kg": 6.0, "governs": "MEV_PLANNING_FLOOR", "cbe_kg": None, "measured_kg": None,
               "committed_labels": ["PROVISIONAL_CONSERVATIVE_OWNER_ANALOG_FLOOR",
                                    "CONTAINS_LEGACY_FUNCTIONS_NOT_PRESENT_IN_CURRENT_FLIGHT_ARCHITECTURE",
                                    "REBASE_REQUIRED_FROM_CURRENT_LOAD_CONVERTER_CBE"],
               "open_rebase_action": {"id": "AFI-02-RA1", "state": "OPEN"},
               "a9_28_value_status": "PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT", "a9_28_open_action": "AFI-02-RA1_OPEN",
               "never_promoted_by_migration_to": ["CBE", "measured mass", "frozen flight truth"],
               "status": "INCOMPLETE_EVIDENCE"}
    al07 = lines.get("AL-07", {})
    vs01 = {"rust_value_status": vs_got, "pass_rust_view": vs_got == vs_want,
            "record_al07_unchanged": al07 == next(x for x in records()["v5"]["lines"][FLIGHT] if x["line"] == "AL-07")}
    vs01["pass"] = vs01["pass_rust_view"] and vs01["record_al07_unchanged"]
    gt = subprocess.run([str(binary), "gates", str(ROOT)], capture_output=True, text=True)
    gates = json.loads(gt.stdout) if gt.returncode == 0 else []
    inv06 = {"gates": [{k: g[k] for k in g if k in ("gate", "status", "hard_40_wet_state_by_loaded_case", "xe_input")}
                       for g in gates]}
    inv06["pass"] = (len(gates) == 3 and gates[0]["status"] == "NOT_EVALUATED"
                     and gates[1]["status"] == "INCOMPLETE_EVIDENCE"
                     and gates[1]["hard_40_wet_state_by_loaded_case"] == {"2.0": "DOES_NOT_CLOSE", "5.0": "DOES_NOT_CLOSE",
                                                                          "10.0": "DOES_NOT_CLOSE"}
                     and gates[1]["xe_input"]["mission_xe_load"] == "NOT_ADMITTED"
                     and gates[2]["status"] == "INCOMPLETE_EVIDENCE")
    cons_rec = []
    for name, r_ in (("rollups[0]", roll), ("historical 20 %", rec.get("historical_conservative_sensitivity_20pct", {})
                                               .get("recomputed_with_al09", {}))):
        if r_:
            ok = abs(r_["nominal_dry_known_kg"] - (r_["nonharness_known_kg"] + r_["harness_kg"])) <= 2e-9 * 40 and \
                abs(r_["system_margin_kg"] + r_["nominal_dry_known_kg"] - r_["dry_known_kg"]) <= 2e-9 * 50
            cons_rec.append({"rollup": name, "pass": ok})
    t = rec.get("internal_allocation_target", {})
    if t:
        cons_rec.append({"rollup": "internal allocation target", "pass": abs(
            t["nominal_dry_kg"] - (t["nonharness_allocation_sum_kg"] + t["harness_kg"])) <= 2e-9 * 30 and abs(
            t["system_margin_kg"] + t["nominal_dry_kg"] - t["dry_kg"]) <= 2e-9 * 30})
    return {"E1": e1, "record_conservation": cons_rec,
            "invariants": {"INV-V01": inv01, "INV-V02": inv02, "INV-V03": inv03, "INV-V04": inv04, "INV-V06": inv06,
                           "VS-01": vs01, "CONS-V01_record": {"checks": cons_rec,
                                                              "pass": all(c["pass"] for c in cons_rec)}}}


def xe_invariants(calls, rs, py):
    x = json.loads((ROOT / XJ).read_text(encoding="utf-8"))
    sig6 = lambda v: float(f"{v:.6g}")  # noqa: E731
    rows = {r["case_kg"]: r for r in x["design_cases"]["loaded_split"]["rows"]}
    out = {}
    for name, res in (("rust", rs), ("python", py)):
        ok = True
        for c, r in zip(calls, res):
            if c["tag"].startswith("R-X02 ") and c["fn"] == "case_split_loaded" and r["outcome"] == "RETURNED":
                v = r["value"]
                row = rows[v["case_kg"]]
                ok &= all(sig6(v[k]) == row[k] for k in ("mission_usable_kg", "reserve_kg", "residual_kg",
                                                         "usable_incl_reserve_kg", "loaded_kg"))
        out[f"INV-X02_{name}"] = ok
        ev = next(r for c, r in zip(calls, res) if c["tag"] == "R-X01" and c["fn"] == "evaluate")
        committed = {e["scenario"]: e for e in x["evaluations"] + x["retired_flight_configuration_history"]["evaluations"]}
        got = {e["scenario"]: e for e in ev.get("value", [])}
        out[f"INV-X03_{name}"] = ev["outcome"] == "RETURNED" and got == committed
        stat = {"COMPUTED", "COMPUTED_EXACT_ZERO", "REFUSED_TBD_INPUTS"}
        ok4 = True
        for c, r in zip(calls, res):
            if r["outcome"] != "RETURNED":
                continue
            vals = r["value"] if c["fn"] == "evaluate" else [{"booking": r["value"]}] if c["fn"] in (
                "book_reserve_and_residual", "ground_supply") else []
            for e in vals:
                ok4 &= e["booking"]["status"] in stat
        out[f"INV-X04_{name}"] = ok4
    return out


def xe_conservation(calls, rs):
    bad = []
    n = 0
    for c, r in zip(calls, rs):
        if r["outcome"] != "RETURNED":
            continue
        v = r["value"]
        if c["fn"] == "case_split_loaded":
            n += 1
            if not abs(v["mission_usable_kg"] + v["reserve_kg"] + v["residual_kg"] - v["case_kg"]) <= 1e-12 * max(1.0, v["case_kg"]):
                bad.append(("CONS-X01", c["tag"]))
        bookings = []
        if c["fn"] == "book_reserve_and_residual":
            bookings = [v]
        elif c["fn"] == "evaluate":
            bookings = [e["booking"] for e in v if "floors_closed_terms_only" in e["booking"]]
        for b in bookings:
            fl = b["floors_closed_terms_only"]
            n += 1
            if b["status"] != "REFUSED_TBD_INPUTS" and (b["totals"] != fl or not _close(fl)):
                bad.append(("CONS-X02", c["tag"]))
        gs = []
        if c["fn"] == "ground_supply":
            gs = [v]
        elif c["fn"] == "evaluate":
            gs = [e["booking"] for e in v if "supply_kg" in e["booking"]]
        for g in gs:
            n += 1
            if g["status"] == "COMPUTED":
                base = g["calculated_kg"]
                if not (g["supply_kg"] == float(f"{base * 1.2:.10g}") or abs(g["supply_kg"] - base * 1.2) <= 1e-9 * max(1, base)):
                    bad.append(("CONS-X03", c["tag"]))
    return {"checked": n, "violations": bad, "pass": not bad}


def _close(fl):
    u = fl["usable_incl_reserve_kg"]
    return math.isnan(u) or abs(fl["loaded_kg"] - (u + fl["residual_sub_line_kg"])) <= 2e-9 * max(1.0, abs(fl["loaded_kg"]))


def performance(key, binary, tmp, mods, calls):
    out = {"status": "reported, not a decision criterion (A9.24 items 1 and 6)"}
    if key == "k-mass-rules":
        c = next(x for x in calls if x["tag"] == "R-K02 v5" and x["fn"] == "rollup")
        reps = [c] * 2000
        out["PERF-K01"] = {"python_s": median_time(lambda: [k_python(c, mods) for _ in range(2000)]),
                           "rust_process_s": median_time(lambda: rust_eval(binary, reps, tmp, "perf")),
                           "note": "Rust: one `abep-mass eval` process evaluating the 2000-call list twice (determinism) "
                                   "incl. JSON I/O; Python: 2000 in-process calls"}
    elif key == "mass-power-v5":
        m5 = load(V5B, "perf_v5")
        reps = [call("build_doc_v5", "perf", repo=str(ROOT))] * 20
        out["PERF-V01"] = {"python_s": median_time(lambda: [m5.render() for _ in range(20)]),
                           "rust_process_s": median_time(lambda: rust_eval(binary, reps, tmp, "perf")),
                           "note": "Rust: one `abep-mass eval` process building the record 20 times, twice; Python: "
                                   "20 in-process render() calls"}
    else:
        c = next(x for x in calls if x["tag"] == "R-X01" and x["fn"] == "evaluate")
        reps = [c] * 500
        out["PERF-X01"] = {"python_s": median_time(lambda: [xe_python(c, mods) for _ in range(500)]),
                           "rust_process_s": median_time(lambda: rust_eval(binary, reps, tmp, "perf")),
                           "note": "Rust: one `abep-mass eval` process evaluating the 500-call list twice incl. JSON "
                                   "I/O; Python: 500 in-process calls (incl. deep copies of the inputs)"}
    for v in out.values():
        if isinstance(v, dict) and "python_s" in v:
            v["speed_up_median_python_over_median_rust"] = round(v["python_s"] / v["rust_process_s"], 3)
    out["machine"] = pc.environment()
    return out


def _git(*a):
    return pc.git(*a)


def make_report(key, cid, cpath, contract, seed, calls, py, rs, by_fn, fails, div_obs, inv, cons, extra, verdict,
                perf, t_run, refs, pins):
    head = _git("rev-parse", "HEAD")
    dirty = _git("status", "--porcelain", "--", "crates", "Cargo.toml", "Cargo.lock")
    cases = json.dumps(calls, sort_keys=False).encode("utf-8")
    return {
        "schema": "abep_rust_parity_report_v3_1",
        "id": f"PARITY-REPORT-{cid}-V1",
        "lane": "SC-WP-07 mass (A9.29)",
        "contract": {"path": str(cpath.relative_to(ROOT)), "id": contract["id"], "sha256": pc.sha_file(cpath)},
        "verdict": verdict,
        "parity": "PARITY_PASS" if verdict == "ADMITTED" else "PARITY_FAIL",
        "verdict_rule": contract["decision_rules"]["verdict"],
        "python_commit": contract["reference_implementation"]["python_commit"],
        "reference_sha256": refs,
        "reference_unchanged_at_scoring": all(v["registered"] == v["now"] for v in refs.values()),
        "pinned_inputs_verified": all(v["registered"] == v["now"] for v in pins.values()),
        "rust_commit": head,
        "rust_tree_clean_at_scoring": dirty == "",
        "build_provenance": {
            "rustc": subprocess.run(["/root/.cargo/bin/rustc", "--version"], capture_output=True, text=True).stdout.strip(),
            "cargo": subprocess.run(["/root/.cargo/bin/cargo", "--version"], capture_output=True, text=True).stdout.strip(),
            "profile": "release (cargo build --release --locked -p abep-subsystems --bin abep-mass)",
            "cargo_lock_sha256": pc.sha_file(ROOT / "Cargo.lock"),
            "source_sha256": provenance(RUST_SOURCES)},
        "environment": pc.environment(),
        "harness_sha256": {"scripts/rust_migration/parity_mass_v1.py": pc.sha_file(Path(__file__)),
                           "scripts/rust_migration/parity_common.py": pc.sha_file(HERE / "parity_common.py")},
        "scoring_execution": {"scoring_master_seed": seed, "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                              "calls": len(calls), "case_file_sha256": pc.sha_bytes(cases),
                              "wall_s": round(t_run, 3)},
        "per_test": {"by_entry_point": by_fn, "failures": fails,
                     "passed": sum(v["pass"] for v in by_fn.values()), "failed": len(fails)},
        "aggregates": "NOT_APPLICABLE (no STATISTICAL entry point)",
        "invariants": inv,
        "conservation": cons if cons else "see invariants",
        "record_bytes_E1": extra.get("E1", "NOT_APPLICABLE"),
        "domain_and_error": {"raised_python": sum(p["outcome"] == "RAISED" for p in py),
                             "raised_rust": sum(r["outcome"] == "RAISED" for r in rs),
                             "classes_python": sorted({p["class"] for p in py if p["outcome"] == "RAISED"}),
                             "classes_rust": sorted({r["class"] for r in rs if r["outcome"] == "RAISED"})},
        "documented_divergence_observed": div_obs,
        "performance": perf,
        "captured_reference_outputs": {"path": str((cpath.parent / "reference_outputs").relative_to(ROOT)) + "/"},
        "campaign_history": [{"execution": "scoring", "seed": seed, "verdict": verdict, "rust_commit": head,
                              "utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}],
        "development_runs": "development comparisons used development_master_seed "
                            f"{contract['campaign_seeds']['development_master_seed']} and the registered deterministic "
                            "vectors only; never scored",
        "ledger_update_requested": ledger_request(key, cid, cpath, contract, verdict),
        "notes": NOTES[key],
        "meaning_of_ADMITTED": contract["decision_rules"]["meaning_of_ADMITTED"],
        "what_this_is_not": contract["what_this_is_not"],
    }


NOTES = {
    "k-mass-rules": [
        "CPython 3.11 builtin sum() over floats is sequential double addition (3.12+ uses compensated summation); the "
        "Rust kernel reproduces the 3.11 reference environment.",
        "DIV-K01 / DIV-K02: the Rust roll-up refuses a non-flight configuration and any AL-C1 line (C1 "
        "GROUND_REFERENCE_ONLY never enters a flight mass roll-up); scored against the registered Rust outcome.",
        "TypeError messages of malformed inputs differ in wording (class scored only, as registered).",
    ],
    "mass-power-v5": [
        "E1: the Rust build reproduces the committed frozen record (5eee4b8) byte for byte from its six pinned inputs; "
        "the record files are only read, never written.",
        "Owner arithmetic (A9.26 sec. 3) reproduced exactly: dry 38.34901052 kg; HARD_40_WET wet 40.34901052 / "
        "43.34901052 / 48.34901052 kg at 2 / 5 / 10 kg loaded Xe, each DOES_NOT_CLOSE; MASS INCOMPLETE_EVIDENCE / "
        "NOT_YET_CLOSED.",
        "VS-01: AL-07 stays 6.0 kg MEV_PLANNING_FLOOR with its committed labels; A9.28 status "
        "PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT / AFI-02-RA1_OPEN read from the sha256-verified A9.28 record.",
        "Cutover: the v5 PINS include the v3 / v4 builder .py files (sha256 only); when the Python tree is archived the "
        "Rust builder needs them kept as archived evidence or a successor pin set (new contract version).",
        "crates/abep-subsystems/src/lib.rs and Cargo.toml changed (mass module, flate2 dev-dependency): the "
        "NP-THERMAL-CATHODELESS verification report's recorded sha256 of those two files needs re-recording.",
    ],
    "xe-accounting-v3": [
        "Function subset only: the record regeneration (build_doc / render_md) and design_cases are "
        "BLOCKED_GOVERNANCE_CONFLICT (contract component.out_of_scope): they emit verbatim C1 provenance / "
        "labelled-history strings that the crate-wide principle-6 scan of crates/abep-subsystems "
        "(tests/prereg_binding.rs, bound by the NP-THERMAL verification provenance) refuses; an integrator / owner "
        "decision is needed before a v2 contract can cover them.",
        "INV-X02: the X1 split of the 2 / 5 / 10 kg cases reproduces the committed design_cases.loaded_split rows; "
        "INV-X03: evaluate on R-X01 reproduces every committed evaluation (all flight and ground totals "
        "REFUSED_TBD_INPUTS).",
    ],
}


def ledger_request(key, cid, cpath, contract, verdict):
    c = {"path": str(cpath.relative_to(ROOT)), "id": contract["id"], "sha256": pc.sha_file(cpath)}
    rep = str((cpath.parent / "parity_report_v1.json").relative_to(ROOT))
    if verdict != "ADMITTED":
        row = {"k-mass-rules": "C-DOCS_BUDGETS_MASS_POWER_A9_V3"}.get(key, cid)
        return [{"row": row, "contract": c, "status": "PREREG_PARITY (NOT_ADMITTED)", "report": rep}]
    if key == "k-mass-rules":
        return [{"row": "C-DOCS_BUDGETS_MASS_POWER_A9_V3", "kernel": "K-MASS-RULES",
                 "partial_admission": {
                     "scope": "extract_and_parity_kernel K-MASS-RULES: rk, _kg, line_mev_value, system_margin, "
                              "harness_row60, closure_state, _unresolved, assert_no_margin_relaxation, rollup (v3 "
                              "builder) + system_margin_bid, assert_bid_margin_reading (v5 builder)",
                     "status": "ADMITTED", "parity": "PARITY_PASS",
                     "rust_implementation": {"crate": "abep-subsystems (abep_subsystems::mass::rules)",
                                             "paths": ["crates/abep-subsystems/src/mass/rules.rs"]},
                     "contract": c, "admission_evidence": rep,
                     "report_disclosures": "registered divergences DIV-K01 / DIV-K02 (Rust refuses a C1 / non-flight "
                                           "roll-up)"},
                 "row_status": "unchanged (class H host; the v3 record stays history)",
                 "active_consumer": "C-DOCS_BUDGETS_MASS_POWER_A9_V5"}]
    if key == "mass-power-v5":
        return [{"row": cid, "transition": {"from": "PYTHON_REFERENCE", "to": "ADMITTED"},
                 "scope": "the whole builder (build_doc / render_md with verify_pins, a9_26_message2, rollup_v5, "
                          "unresolved_v5, set_al09); main() is replaced by `abep-mass build-v5 / check-v5`",
                 "authoritative_implementation": {"kind": "rust", "crate": "abep-subsystems (abep_subsystems::mass::v5)",
                                                  "paths": ["crates/abep-subsystems/src/mass/v5.rs",
                                                            "crates/abep-subsystems/src/mass/rules.rs"]},
                 "contract": c, "admission_evidence": rep,
                 "value_status": "AL-07 6.0 kg PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT / AFI-02-RA1_OPEN preserved "
                                 "(VS-01); never promoted to CBE / measured / frozen truth",
                 "report_disclosures": "DIV-V01 / DIV-V02 (C1 / non-flight roll-up refused), DIV-V03 (production "
                                       "wet-mass read verifies the record sha256); cutover pin note"},
                {"row": "C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY",
                 "partial_admission": {
                     "scope": "wet_mass (with _obj, supplied_objective and intake_synthesis.require_f1q02_label)",
                     "status": "ADMITTED", "parity": "PARITY_PASS",
                     "rust_implementation": {"crate": "abep-subsystems (abep_subsystems::mass::wet_mass)",
                                             "paths": ["crates/abep-subsystems/src/mass/wet_mass.rs"]},
                     "contract": c, "admission_evidence": rep}}]
    return [{"row": cid,
             "partial_admission": {
                 "scope": "named function subset X1-X6: case_split_loaded, ignition_booking_s, "
                          "book_reserve_and_residual, ground_supply, eval_line, evaluate",
                 "status": "ADMITTED", "parity": "PARITY_PASS",
                 "rust_implementation": {"crate": "abep-subsystems (abep_subsystems::mass::xe)",
                                         "paths": ["crates/abep-subsystems/src/mass/xe.rs"]},
                 "contract": c, "admission_evidence": rep},
             "not_in_scope": "build_doc / render_md / design_cases and the remaining builder functions stay "
                             "PYTHON_REFERENCE: BLOCKED_GOVERNANCE_CONFLICT (principle-6 crate scan); v2 contract after "
                             "the integrator / owner decision"}]


def _canon(x) -> str:
    return json.dumps(x, sort_keys=False)


def _encode_args(a: dict, base, trees) -> dict:
    out = {}
    for k, v in a.items():
        if trees and k == "repo":
            name = next((n for n, p in trees.items() if str(p) == v), None)
            out[k] = f"@TREE:{name}" if name else v
            continue
        if base:
            cv = _canon(v)
            tok = next((f"@{bk}" for bk, bv in base.items() if _canon(bv) == cv), None)
            if tok:
                out[k] = tok
                continue
            bi, bl = base["BASE_ITEMS"], base["BASE_LINES"]
            if k == "items" and isinstance(v, dict) and list(v) == list(bi) and all(
                    _canon(dict(v[i], value=None)) == _canon(dict(bi[i], value=None)) for i in v):
                out[k] = {"@BASE_ITEMS_VALUES": {i: v[i]["value"] for i in v}}
                continue
            if k == "lines" and isinstance(v, list) and len(v) == len(bl) and all(
                    _canon(dict(x, presence=None)) == _canon(dict(y, presence=None)) for x, y in zip(v, bl)):
                out[k] = {"@BASE_LINES_PRESENCE": [x["presence"] for x in v]}
                continue
        out[k] = v
    return out


def write_reference_outputs(out_dir: Path, cid: str, calls, py, report, base=None, trees=None, tree_specs=None):
    """reference_outputs/python_outcomes_v1.json.gz: every scored call with its (compacted) arguments and the Python
    outcome (inline when its canonical JSON is <= 4096 characters, else its sha256), plus the registered Rust outcome
    of each divergence case. Canonical form: json.dumps(outcome, ensure_ascii=False)."""
    d = out_dir / "reference_outputs"
    d.mkdir(exist_ok=True)
    entries = []
    for c, p in zip(calls, py):
        e = {"fn": c["fn"], "tag": c["tag"], "args": _encode_args(c["args"], base, trees)}
        canon = json.dumps(p, ensure_ascii=False)
        if len(canon) <= 4096:
            e["python"] = p
        else:
            e["python_sha256"] = pc.sha_bytes(canon.encode("utf-8"))
        if c.get("div"):
            e["div"] = c["div"]
            exp = expected_div(c)
            e["expected_rust"] = exp if exp is not None else "EQUALS_PYTHON"
        entries.append(e)
    payload = {"schema": "abep_mass_captured_reference_v1", "contract_id": cid,
               "python_commit": report["python_commit"],
               "canonical_form": "json.dumps(outcome, ensure_ascii=False)",
               "argument_tokens": {"@<NAME>": "the object base[NAME]",
                                   "@BASE_ITEMS_VALUES": "base BASE_ITEMS with each item's value replaced",
                                   "@BASE_LINES_PRESENCE": "base BASE_LINES with each line's presence replaced",
                                   "@TREE:<name>": "a case tree rebuilt from tree_specs (contract inputs.case_trees)"},
               "base": base, "tree_specs": tree_specs, "entries": entries}
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    p = d / "python_outcomes_v1.json.gz"
    with open(p, "wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz:
        gz.write(raw)
    report["captured_reference_outputs"].update({
        "files": {"python_outcomes_v1.json.gz": pc.sha_file(p)}, "uncompressed_sha256": pc.sha_bytes(raw),
        "entries": len(entries), "captured_at_python_commit": report["python_commit"],
        "replay": "crates/abep-subsystems/tests/mass_captured_replay.rs (added after scoring; not a provenance source "
                  "of the scored build)"})


def report_md(r: dict) -> str:
    L = [f"# Parity report v1 - {r['contract']['id']}", "",
         f"Verdict **{r['verdict']}** ({r['parity']}). Contract `{r['contract']['path']}` (sha256 "
         f"`{r['contract']['sha256']}`). Python reference `{r['python_commit']}`; Rust `{r['rust_commit']}`.", "",
         f"Scoring seed {r['scoring_execution']['scoring_master_seed']}: {r['scoring_execution']['calls']} calls, "
         f"{r['per_test']['passed']} pass, {r['per_test']['failed']} fail.", "", "## Per entry point", "",
         "| entry point | calls | pass | fail |", "|---|---|---|---|"]
    for fn, v in r["per_test"]["by_entry_point"].items():
        L.append(f"| {fn} | {v['n']} | {v['pass']} | {v['fail']} |")
    L += ["", "## Invariants", ""]
    for k, v in r["invariants"].items():
        ok = _truthy_inv(k, v)
        L.append(f"* {k}: {'pass' if ok else 'FAIL'}")
    if r.get("record_bytes_E1") != "NOT_APPLICABLE":
        e = r["record_bytes_E1"]
        L += ["", "## E1 record bytes", "", f"* JSON sha256 python / rust / committed: `{e['json']['python']}` / "
              f"`{e['json']['rust']}` / `{e['json']['committed']}`",
              f"* Markdown sha256 python / rust / committed: `{e['md']['python']}` / `{e['md']['rust']}` / "
              f"`{e['md']['committed']}`", f"* pass: {e['pass']}"]
    L += ["", "## Registered divergences observed", ""]
    for d in r["documented_divergence_observed"]:
        L.append(f"* {d['div']} {d['tag']}: Rust matches the registered outcome: {d['rust_matches_registered']}; "
                 f"Python {d['python']['outcome']}")
    if not r["documented_divergence_observed"]:
        L.append("* none")
    L += ["", "## Performance (reported, not decided on)", ""]
    for k, v in r["performance"].items():
        if isinstance(v, dict) and "python_s" in v:
            L.append(f"* {k}: Python {v['python_s']:.4f} s, Rust {v['rust_process_s']:.4f} s, speed-up "
                     f"{v['speed_up_median_python_over_median_rust']} ({v['note']})")
    L += ["", "## Notes", ""] + [f"* {n}" for n in r["notes"]] + ["", "## Ledger update requested", "",
                                                                    "```json", json.dumps(r["ledger_update_requested"],
                                                                                          indent=1, ensure_ascii=False),
                                                                    "```", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("contract", choices=sorted(CONTRACTS))
    ap.add_argument("--score", action="store_true", help="the single scoring execution (writes the report)")
    ap.add_argument("--dry-report", type=Path, default=None,
                    help="development seed; write the report pipeline output into this scratch directory (never the "
                         "contract directory; never a verdict)")
    a = ap.parse_args(argv)
    if a.dry_report is not None and (a.score or a.dry_report.resolve().is_relative_to(ROOT)):
        ap.error("--dry-report needs a directory outside the repository and excludes --score")
    return run(a.contract, a.score, a.dry_report)


if __name__ == "__main__":
    sys.exit(main())
