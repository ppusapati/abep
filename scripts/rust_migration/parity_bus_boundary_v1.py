"""Parity campaign of contract C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY v1 (SC-WP-05 bus-power boundary group).

Python reference (abep_sim/bus_boundary_a9_v2.py and its rebound v1 functions, architecture_optimizer.official_ledger,
design_synthesis.bus_power) vs the Rust example `power_eval` (abep_subsystems::power) on the preregistered calls.
Every scored Python observation comes from the FLIGHT_RESTRICTED_REFERENCE of the contract: the unchanged reference
code with the GROUND_REFERENCE_ONLY C1 rows removed from SLOTS / ALL_SLOTS / PEAK_EVENTS for the duration of the call;
the unrestricted observation is recorded for INV-A01 / INV-A02.

  python scripts/rust_migration/parity_bus_boundary_v1.py --mode development --work DIR
  python scripts/rust_migration/parity_bus_boundary_v1.py --mode score --work DIR
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import random
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_common as PC  # noqa: E402
import parity_power_common as P  # noqa: E402

ROOT = P.ROOT
sys.path.insert(0, str(ROOT))
from abep_sim import bus_boundary_a9_v2 as B2  # noqa: E402
from abep_sim.design import architecture_optimizer as ao  # noqa: E402
from abep_sim.programme import design_synthesis as ds  # noqa: E402

CID = "C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY"
CDIR = ROOT / "docs/rust_migration/contracts" / CID
CONTRACT = CDIR / "parity_prereg_v1.json"
HARNESS = Path(__file__).resolve()
FLIGHT = "hall_icp_neutralizer"
MESSAGE_CLASSES = {"BoundaryA9Error", "OverflowError"}

FULL_SLOTS, FULL_ALL, FULL_PEAK = B2.SLOTS, B2.ALL_SLOTS, B2.PEAK_EVENTS
C1 = [s for s in FULL_ALL if FULL_SLOTS[s]["group"] == "c1"]
FLIGHT_SLOTS = {k: v for k, v in FULL_SLOTS.items() if v["group"] != "c1"}
FLIGHT_ALL = tuple(FLIGHT_SLOTS)
FLIGHT_PEAK = {e: s for e, s in FULL_PEAK.items() if s not in C1}
C1_EVENTS = [e for e, s in FULL_PEAK.items() if s in C1]
EC = list(B2.EVIDENCE_CLASSES)
PATHS = list(B2.PATHS)
BASES = list(B2.POWER_BASES)
VOPTS = list(B2.VARIANT_OPTIONS[FLIGHT])
GM_OK = {"sample_rate_Sa_s": 100000.0, "bandwidth_Hz": 20000.0, "anti_alias_documented": True,
         "synchronized": True, "source": "DQ-HI-PBUS synthetic conformance record"}
FE = {"value": 0.95, "evidence_class": "measured", "source": "fe"}
BOOKED_RE = re.compile(r"^load of '(\w+)': 'booked_W' is defined only for c1_heater \(A9\.1 SEQ-heater\)$")
DIV_A04_PY = "rfp_power_gate needs a non-empty sequence"
DIV_A04_RS = "bus_power needs a non-empty sequence of start-up step ledgers (row 108)"
ZERO_ROW = {"state": "NOT_INSTALLED", "P_W": 0.0, "efficiency": 1.0, "path": None, "P_bus_W": 0.0, "P_loss_W": 0.0,
            "evidence_class": None, "source": None}


@contextmanager
def restricted(on: bool = True):
    if on:
        B2.SLOTS, B2.ALL_SLOTS, B2.PEAK_EVENTS = FLIGHT_SLOTS, FLIGHT_ALL, FLIGHT_PEAK
    try:
        yield
    finally:
        B2.SLOTS, B2.ALL_SLOTS, B2.PEAK_EVENTS = FULL_SLOTS, FULL_ALL, FULL_PEAK


# ============================================================================================== case construction
def full(variant, cid):
    inst = B2.installed_slots(FLIGHT, list(variant))
    loads = {s: {"P_W": 10.0, "evidence_class": "measured", "source": "src:" + s} for s in inst}
    loads["icp_rf_source"]["plane"] = "generator_dc_input"
    effs = {s: {"value": 0.9, "evidence_class": "measured", "source": "eff:" + s, "path": "internal_bus"} for s in inst}
    return {"config": FLIGHT, "loads": loads, "efficiencies": effs, "front_end": dict(FE), "variant": list(variant),
            "label": cid, "power_basis": None, "gate_measurement": None}


def tpl(variant, cooling=False):
    temps = B2.SEQUENCE_TEMPLATES[FLIGHT]
    inst = B2.installed_slots(FLIGHT, list(variant))
    on, steps = set(), []
    effs = {s: {"value": 0.9, "evidence_class": "measured", "source": "eff:" + s, "path": "internal_bus"} for s in inst}
    for t in temps:
        on |= set(t["on"])
        loads = {s: {"P_W": 10.0 if s in on else 0.0, "evidence_class": "measured", "source": "src:" + s}
                 for s in inst}
        loads["icp_rf_source"]["plane"] = "generator_dc_input"
        st = {"step_id": t["step_id"], "event": t["event"], "loads": loads, "efficiencies": copy.deepcopy(effs),
              "power_basis": "p_bus_1ms_max", "gate_measurement": dict(GM_OK)}
        if t.get("phase") == "steady":
            st["phase"] = "steady"
        steps.append(st)
    if cooling:
        new = copy.deepcopy(steps[1])
        new["step_id"], new["event"] = "I-S1c", "active_cooling_start"
        steps.insert(2, new)
        for st in steps[2:]:
            st["loads"]["active_cooling"]["P_W"] = 10.0
    return {"config": FLIGHT, "steps": steps, "front_end": dict(FE), "variant": list(variant)}


def set_path(obj, path, value):
    parts = path.split(".")
    cur = obj
    for p in parts[:-1]:
        cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    last = parts[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    else:
        cur[last] = value


def del_path(obj, path):
    parts = path.split(".")
    cur = obj
    for p in parts[:-1]:
        cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    del cur[parts[-1]]


def valid_variant(v):
    return isinstance(v, list) and all(isinstance(x, str) and x in VOPTS for x in v) and len(set(v)) == len(v)


def build_ledger_case(case):
    sets = P.decode(case.get("set", {}))
    variant = []
    if case["base"] == "FULLV":
        variant = list(VOPTS)
    if "variant" in sets and valid_variant(sets["variant"]):
        variant = sets["variant"]
    a = full(variant, case["id"])
    if "$all_paths" in sets:
        for e in a["efficiencies"].values():
            e["path"] = sets["$all_paths"]
    if sets.get("$all_loads_tbd"):
        for s in list(a["loads"]):
            rec = {"P_W": "TBD", "tbd_requires": "tbd:" + s}
            if s == "icp_rf_source":
                rec["plane"] = "generator_dc_input"
            a["loads"][s] = rec
    if sets.get("$all_effs_tbd"):
        for s in list(a["efficiencies"]):
            a["efficiencies"][s] = {"value": "TBD", "tbd_requires": "tbd:" + s, "path": "internal_bus"}
    if "$all_loads_value" in sets:
        for rec in a["loads"].values():
            rec["P_W"] = sets["$all_loads_value"]
    for k, v in sets.items():
        if not k.startswith("$"):
            set_path(a, k, copy.deepcopy(v))
    for k in case.get("del", []):
        del_path(a, k)
    return a


def build_seq_case(case):
    sets = P.decode(case.get("set", {}))
    variant = sets["variant"] if "variant" in sets and valid_variant(sets["variant"]) else []
    a = tpl(variant, cooling=bool(sets.get("$cooling_step")))
    if "$swap_events" in sets:
        i, j = sets["$swap_events"]
        a["steps"][i]["event"], a["steps"][j]["event"] = a["steps"][j]["event"], a["steps"][i]["event"]
    if "$keep_steps" in sets:
        a["steps"] = [a["steps"][k] for k in sets["$keep_steps"]]
    if "$all_bases" in sets:
        for st in a["steps"]:
            st["power_basis"] = sets["$all_bases"]
    if "$all_loads_tbd_after" in sets:
        k = sets["$all_loads_tbd_after"]
        for st in a["steps"][k + 1:]:
            for s in list(st["loads"]):
                rec = {"P_W": "TBD", "tbd_requires": "tbd:" + s}
                if s == "icp_rf_source":
                    rec["plane"] = "generator_dc_input"
                st["loads"][s] = rec
    for k, v in sets.items():
        if not k.startswith("$"):
            set_path(a, k, copy.deepcopy(v))
    for k in case.get("del", []):
        del_path(a, k)
    return a


def samples(spec):
    spec = P.decode(spec)
    if "const" in spec:
        x, n = spec["const"]
        return [x] * n
    if "ramp" in spec:
        x0, dx, n = spec["ramp"]
        return [x0 + i * dx for i in range(n)]
    if "wave" in spec:
        (n,) = spec["wave"]
        return [700.0 + 600.0 * math.sin(i / 37.0) + (450.0 if i % 997 == 0 else 0.0) for i in range(n)]
    return spec["raw"]


# ============================================================================================== random domain
def gl_draw(rng, label):
    variant = rng.choice([[], ["icp_assist_magnet"], ["active_cooling"], ["flow_control_icp_feed"],
                          ["icp_assist_magnet", "active_cooling", "flow_control_icp_feed"],
                          ["flow_control_icp_feed", "icp_assist_magnet"]])
    p_tbd = rng.choice([0.0, 0.0, 0.1, 0.3])
    p_off = rng.choice([0.0, 0.15])
    p_eff_tbd = rng.choice([0.0, 0.0, 0.1])
    inst = B2.installed_slots(FLIGHT, list(variant))
    loads, effs = {}, {}
    for s in inst:
        u = rng.random()
        if u < p_tbd:
            rec = {"P_W": "TBD", "tbd_requires": "tbd:" + s}
        elif u < p_tbd + p_off:
            rec = {"P_W": 0.0, "evidence_class": "measured", "source": "src:" + s}
        else:
            rec = {"P_W": round(rng.uniform(0, 900), rng.choice([0, 3, 6, 17])), "evidence_class": rng.choice(EC),
                   "source": "src:" + s}
        if s == "icp_rf_source":
            rec["plane"] = "generator_dc_input"
        loads[s] = rec
        if rng.random() < p_eff_tbd:
            effs[s] = {"value": "TBD", "tbd_requires": "eff:" + s, "path": rng.choice(PATHS)}
        else:
            v = 1.0 if rng.random() < 0.1 else rng.uniform(0.5, 1.0)
            effs[s] = {"value": v, "evidence_class": rng.choice(EC), "source": "eff:" + s, "path": rng.choice(PATHS)}
    for o in VOPTS:
        if o not in variant and rng.random() < 0.3:
            loads[o] = {"P_W": 0.0, "evidence_class": "assumed", "source": "not installed"}
            effs[o] = {"value": 1.0, "evidence_class": "assumed", "source": "not installed", "path": "direct"}
    if rng.random() < 0.15:
        fe = {"value": "TBD", "tbd_requires": "front end"}
    else:
        fe = {"value": rng.uniform(0.85, 1.0), "evidence_class": rng.choice(EC), "source": "fe"}
    basis = rng.choice([None] + BASES)
    gm = rng.choice([None, GM_OK, dict(GM_OK, sample_rate_Sa_s=50000.0), dict(GM_OK, anti_alias_documented=False)])
    return {"config": FLIGHT, "loads": loads, "efficiencies": effs, "front_end": fe, "variant": list(variant),
            "label": label, "power_basis": basis, "gate_measurement": copy.deepcopy(gm)}


def gs_draw(rng, n_id):
    variant = rng.choice([[], ["active_cooling"]])
    n = rng.randint(2, 7)
    inst = B2.installed_slots(FLIGHT, list(variant))
    effs = {}
    for s in inst:
        if rng.random() < 0.05:
            effs[s] = {"value": "TBD", "tbd_requires": "eff:" + s, "path": rng.choice(PATHS)}
        else:
            effs[s] = {"value": rng.uniform(0.5, 1.0), "evidence_class": rng.choice(EC), "source": "eff:" + s,
                       "path": rng.choice(PATHS)}
    fe = {"value": rng.uniform(0.85, 1.0), "evidence_class": rng.choice(EC), "source": "fe"}
    cur = {s: 0.0 for s in inst}
    events = sorted(e for e, s in FLIGHT_PEAK.items() if s in inst)
    steps = []
    for i in range(n):
        for s in inst:
            if rng.random() < 0.3:
                c = rng.randrange(3)
                cur[s] = round(rng.uniform(0, 600), 3) if c == 0 else (0.0 if c == 1 else "TBD")
        loads = {}
        for s in inst:
            rec = ({"P_W": "TBD", "tbd_requires": "tbd:" + s} if cur[s] == "TBD"
                   else {"P_W": cur[s], "evidence_class": "measured", "source": "src:" + s})
            if s == "icp_rf_source":
                rec["plane"] = "generator_dc_input"
            loads[s] = rec
        c = rng.randrange(4)
        ev = None if c < 2 else (rng.choice(events) if c == 2 else [rng.choice(events), rng.choice(events)])
        st = {"step_id": f"S{i}", "event": ev, "loads": loads, "efficiencies": copy.deepcopy(effs),
              "power_basis": rng.choice([None] + BASES)}
        if i == n - 1:
            st["phase"] = "steady"
        steps.append(st)
    return {"config": FLIGHT, "steps": steps, "front_end": fe, "variant": list(variant)}


def gp_draw(rng):
    fs = rng.choice([100000.0, 200000.0, 1000000.0, 100000])
    bw = rng.choice([20000.0, 50000.0])
    if rng.random() < 0.1:
        fs, length = 100000.0, 10000 + rng.randint(0, 500)
    else:
        n1 = round(fs * 1e-3)
        length = n1 + rng.randint(0, 3 * n1)
    xs = [round(rng.uniform(0, 1500), 2) for _ in range(length)]
    xs[rng.randrange(length)] = rng.uniform(1500, 4000)
    return {"samples_W": xs, "sample_rate_Sa_s": fs, "bandwidth_Hz": bw, "anti_alias_documented": True,
            "synchronized": True}


def gr_draw(rng):
    dc = rng.uniform(0, 600)
    fw = rng.uniform(0, dc)
    rf = rng.uniform(0, fw)
    dl = "TBD" if rng.random() < 0.2 else rng.uniform(0, fw - rf)
    u = rng.choice([0.0, 0.5, 2.0])
    if rng.random() < 0.2:
        w = rng.randrange(3)
        if w == 0:
            rf = fw + u + rng.uniform(0.1, 5)
        elif w == 1:
            fw = dc + u + rng.uniform(0.1, 5)
        else:
            dl = fw - rf + u + rng.uniform(0.1, 5)
    return {"P_dc_in_W": dc, "P_forward_W": fw, "P_reflected_W": rf, "P_delivered_W": dl, "u_W": u}


# ============================================================================================== Python calls
def py_ledger(a):
    return B2.ledger(a["config"], a["loads"], a["efficiencies"], a["front_end"], a["variant"], label=a["label"],
                     power_basis=a["power_basis"], gate_measurement=a["gate_measurement"])


def py_ledger_ref(ref):
    return py_ledger(copy.deepcopy(ref["call"])) if "call" in ref else copy.deepcopy(ref["raw"])


def py_supplied(sup):
    out = {}
    for k, v in sup.items():
        if k == "steady":
            out[k] = py_ledger_ref(v)
        elif k == "startup":
            out[k] = [py_ledger_ref(x) for x in v["list"]] if "list" in v else copy.deepcopy(v["raw"])
        else:
            out[k] = copy.deepcopy(v)
    return out


def py_call(fn, a):
    a = copy.deepcopy(a)
    if fn == "installed_slots":
        return P.py_result(B2.installed_slots, a["config"], a["variant"])
    if fn == "ledger":
        return P.py_result(py_ledger, a)
    if fn == "p_bus_1ms_max":
        return P.py_result(B2.p_bus_1ms_max, a["samples_W"], a["sample_rate_Sa_s"], a["bandwidth_Hz"],
                           a["anti_alias_documented"], a["synchronized"])
    if fn == "rf_power_planes":
        return P.py_result(B2.rf_power_planes, a["P_dc_in_W"], a["P_forward_W"], a["P_reflected_W"],
                           a["P_delivered_W"], a["u_W"])
    if fn in ("allocation_checks", "icp_power_allocation_check"):
        f = getattr(B2, fn)
        return P.py_result(lambda: f(py_ledger_ref(a["ledger"])))
    if fn == "check_startup_sequence":
        r = P.py_result(B2.check_startup_sequence, a["config"], a["steps"], a["front_end"], a["variant"])
        if r["outcome"] == "RETURNED":
            r["value"].pop("transient_gate")
        return r
    if fn == "official_ledger":
        return P.py_result(ao.official_ledger, a["config"], ROOT, a["compressor_P_W"], a["compressor_source"])
    if fn == "bus_power":
        sup = None if a["supplied"] is None else a["supplied"]
        r = P.py_result(lambda: ds.bus_power(a["config"], a["compressor_P_W"], None if sup is None else
                                             py_supplied(sup)))
        if r["outcome"] == "RETURNED":
            r["value"].pop("gate_verdict")
        return r
    raise ValueError(fn)


# ============================================================================================== invariants helpers
def ledger_args_in(fn, a):
    """Every ledger argument set (and sequence step) a call contains."""
    out = []
    if fn == "ledger":
        out.append(a)
    if fn == "check_startup_sequence" and isinstance(a.get("steps"), list):
        out += [st for st in a["steps"] if isinstance(st, dict)]
    if fn in ("allocation_checks", "icp_power_allocation_check") and "call" in a.get("ledger", {}):
        out.append(a["ledger"]["call"])
    if fn == "bus_power" and isinstance(a.get("supplied"), dict):
        s = a["supplied"]
        if isinstance(s.get("steady"), dict) and "call" in s["steady"]:
            out.append(s["steady"]["call"])
        if isinstance(s.get("startup"), dict) and "list" in s["startup"]:
            out += [x["call"] for x in s["startup"]["list"] if "call" in x]
    return out


def ground_reference_input(fn, a):
    """(C1 slot key or C1 event present, booked_W present) in any ledger argument set or step of the call."""
    c1, booked = False, False
    for la in ledger_args_in(fn, a):
        for k in ("loads", "efficiencies"):
            d = la.get(k)
            if isinstance(d, dict) and any(s in C1 for s in d):
                c1 = True
        if isinstance(la.get("loads"), dict) and any(isinstance(r, dict) and "booked_W" in r
                                                     for r in la["loads"].values()):
            booked = True
        ev = la.get("event")
        evs = ev if isinstance(ev, list) else [ev]
        if any(isinstance(e, str) and e in C1_EVENTS for e in evs):
            c1 = True
    return c1, booked


def strip_c1(v, removed):
    """Remove the group-'c1' rows from every ledger 'items' list (collected in `removed`)."""
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if k == "items" and "boundary_version" in v and isinstance(x, list):
                keep = []
                for it in x:
                    if isinstance(it, dict) and it.get("slot") in C1:
                        removed.append(it)
                    else:
                        keep.append(strip_c1(it, removed))
                out[k] = keep
            else:
                out[k] = strip_c1(x, removed)
        return out
    if isinstance(v, list):
        return [strip_c1(x, removed) for x in v]
    return v


def to_restricted_form(r, removed):
    r = copy.deepcopy(r)
    r.pop("frames", None)
    if r["outcome"] == "RETURNED":
        r["value"] = strip_c1(r["value"], removed)
    else:
        r["message"] = r["message"].replace(repr(list(FULL_ALL)), repr(list(FLIGHT_ALL))).replace(
            repr(sorted(FULL_PEAK)), repr(sorted(FLIGHT_PEAK)))
    return r


def expected_rust(fn, a, py):
    """The registered Rust outcome: the restricted observation, with DIV-A03 / DIV-A04 registered messages."""
    exp = {k: v for k, v in py.items() if k != "frames"}
    div = None
    if py["outcome"] == "RAISED" and fn == "ledger":
        m = BOOKED_RE.match(py["message"])
        if m:
            slot = m.group(1)
            rec = a["loads"][slot]
            allowed = {"P_W", "tbd_requires"} | ({"plane"} if slot == "icp_rf_source" else set())
            extra = sorted(str(k) for k in rec if k not in allowed)
            exp["message"] = (f"load of {slot!r}: unexpected key(s) {extra}; allowed {sorted(allowed)} "
                              f"(schema parity)")
            div = "DIV-A03"
    if py["outcome"] == "RAISED" and fn == "bus_power" and py["message"].startswith(DIV_A04_PY):
        exp["message"] = DIV_A04_RS
        div = "DIV-A04"
    return exp, div


def cons_ledger(v):
    """CONS-A1 / CONS-A2 on one COMPLETE ledger value: (ok, worst A1, worst A2)."""
    if not (isinstance(v, dict) and v.get("status") == "COMPLETE"):
        return None
    fe = v["front_end"]["efficiency"]
    terms, a2 = [], 0.0
    ok = True
    for it in v["items"]:
        if it["state"] != "ON":
            continue
        eta_fe = fe if it["path"] == "internal_bus" else 1.0
        terms.append(it["P_W"] / it["efficiency"] / eta_fe)
        d = abs(it["P_W"] + it["P_loss_W"] - it["P_bus_W"])
        a2 = max(a2, d / max(1.0, it["P_bus_W"]))
        ok &= it["P_loss_W"] >= 0.0
    s = math.fsum(terms)
    a1 = abs(s - v["P_bus_W"]) / max(1.0, v["P_bus_W"])
    src = math.fsum(it["P_bus_W"] for it in v["items"])
    ok &= a1 <= 1e-12 and a2 <= 1e-12 and abs(v["residual_W"]) <= 1e-12 * max(src, 1.0)
    return ok, a1, a2


# ============================================================================================== campaign
def build_calls(contract, seed):
    calls = []  # (case_id, fn, args)
    reg_ledgers = {}
    for case in contract["inputs"]["registered_cases"]:
        fn, cid = case["fn"], case["id"]
        if fn == "installed_slots":
            calls.append((cid, fn, {"config": case["config"], "variant": case["variant"]}))
        elif fn == "ledger":
            a = build_ledger_case(case)
            reg_ledgers[cid] = a
            calls.append((cid, fn, a))
        elif fn == "check_startup_sequence":
            calls.append((cid, fn, build_seq_case(case)))
        elif fn == "p_bus_1ms_max":
            calls.append((cid, fn, {"samples_W": samples(case["samples"]), "sample_rate_Sa_s": P.decode(case["fs"]),
                                    "bandwidth_Hz": P.decode(case["bw"]), "anti_alias_documented": case["aa"],
                                    "synchronized": case["sync"]}))
        elif fn == "rf_power_planes":
            x = P.decode(case["args"])
            calls.append((cid, fn, dict(zip(["P_dc_in_W", "P_forward_W", "P_reflected_W", "P_delivered_W", "u_W"], x))))
        elif fn in ("allocation_checks", "icp_power_allocation_check"):
            calls.append((cid, fn, {"ledger": {"raw": case["ledger_raw"]}}))
        elif fn == "official_ledger":
            calls.append((cid, fn, {"config": case["config"], "compressor_P_W": P.decode(case["compressor_P_W"]),
                                    "compressor_source": case["compressor_source"]}))
    extra = {"LE-FE-ASSUMED": dict(copy.deepcopy(reg_ledgers["LE-01"]), label="LE-FE-ASSUMED"),
             "LE-EFF-ASSUMED": dict(copy.deepcopy(reg_ledgers["LE-01"]), label="LE-EFF-ASSUMED")}
    extra["LE-FE-ASSUMED"]["front_end"]["evidence_class"] = "assumed"
    extra["LE-EFF-ASSUMED"]["efficiencies"]["hall_discharge"]["evidence_class"] = "assumed"
    refs = dict(reg_ledgers, **extra)

    def ref(x):
        return {"raw": P.decode(x["raw"])} if isinstance(x, dict) else {"call": copy.deepcopy(refs[x])}

    for case in contract["inputs"]["registered_cases"]:
        if case["fn"] != "bus_power":
            continue
        s = case["supplied"]
        sup = None
        if s is not None:
            sup = {}
            for k, v in s.items():
                if k == "steady":
                    sup[k] = ref(v)
                elif k == "startup":
                    sup[k] = {"raw": P.decode(v["raw"])} if isinstance(v, dict) else {"list": [ref(x) for x in v]}
                else:
                    sup[k] = v
        calls.append((case["id"], "bus_power", {"config": FLIGHT, "compressor_P_W": P.decode(case["compressor_P_W"]),
                                                "supplied": sup}))
    n = contract["inputs"]["randomized_domain"]["count"]
    rng = random.Random(seed * 1000 + 2)
    for i in range(n["E2 ledger"]):
        calls.append((f"R2-{i}", "ledger", gl_draw(rng, f"R2-{i}")))
    rng = random.Random(seed * 1000 + 7)
    for i in range(n["E7 sequence"]):
        calls.append((f"R7-{i}", "check_startup_sequence", gs_draw(rng, i)))
    rng = random.Random(seed * 1000 + 3)
    for i in range(n["E3 p_bus_1ms_max"]):
        calls.append((f"R3-{i}", "p_bus_1ms_max", gp_draw(rng)))
    rng = random.Random(seed * 1000 + 4)
    for i in range(n["E4 rf_power_planes"]):
        calls.append((f"R4-{i}", "rf_power_planes", gr_draw(rng)))
    rng = random.Random(seed * 1000 + 9)
    for i in range(n["E9 bus_power (supplied)"]):
        steady = gl_draw(rng, f"R9-{i}-s")
        startup = [gl_draw(rng, f"R9-{i}-u{j}") for j in range(rng.randint(1, 3))]
        sup = {"steady": {"call": steady}, "startup": {"list": [{"call": x} for x in startup]}}
        syn = rng.choice(["absent", True, False])
        if syn != "absent":
            sup["synthetic"] = syn
        src = rng.choice(["absent", f"random source {i}"])
        if src != "absent":
            sup["source"] = src
        comp = rng.choice([None, rng.uniform(0, 200)])
        calls.append((f"R9-{i}", "bus_power", {"config": FLIGHT, "compressor_P_W": comp, "supplied": sup}))
    return calls


def run(mode: str, work: Path) -> dict:
    contract_bytes = CONTRACT.read_bytes()
    contract = json.loads(contract_bytes)
    seeds = contract["campaign_seeds"]
    seed = seeds["scoring_master_seed"] if mode == "score" else seeds["development_master_seed"]
    t0 = time.time()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    changed, pinned_bad = P.check_reference(contract)
    if changed:
        return {"verdict": "REFUSED_REFERENCE_CHANGED", "changed": changed}
    gs = P.git_state()
    bindir = P.cargo_build()
    calls = build_calls(contract, seed)
    rows = []
    for cid, fn, a in calls:
        with restricted(True):
            py = py_call(fn, a)
        with restricted(False):
            un = py_call(fn, a)
        rows.append({"case": cid, "fn": fn, "args": a, "py": py, "un": un})
    for r in list(rows):
        if r["fn"] == "ledger" and r["py"]["outcome"] == "RETURNED":
            for fn in ("allocation_checks", "icp_power_allocation_check"):
                a = {"ledger": {"call": r["args"]}}
                with restricted(True):
                    py = py_call(fn, a)
                with restricted(False):
                    un = py_call(fn, a)
                rows.append({"case": r["case"], "fn": fn, "args": a, "py": py, "un": un})
    rcalls = [{"fn": r["fn"], "args": r["args"]} for r in rows]
    rs, rbytes = P.rust_eval(bindir, rcalls, work, "a")
    _, rbytes2 = P.rust_eval(bindir, rcalls, work, "b")

    failures, mismatches, max_ulp, floats = [], 0, 0.0, 0
    divs = {"DIV-A02": 0, "DIV-A03": 0, "DIV-A04": 0}
    inv1_bad, inv2_bad, inv7_bad, removed_all = [], [], [], []
    cons_bad, cons_n, cons_py_bad = [], 0, []
    raised = {}
    for r, rres in zip(rows, rs):
        exp, div = expected_rust(r["fn"], r["args"], r["py"])
        if div:
            divs[div] += 1
        d, st = P.compare(exp, rres, MESSAGE_CLASSES)
        max_ulp, floats = max(max_ulp, st["max_ulp"]), floats + st["floats"]
        if d:
            mismatches += 1
            failures.append({"case": r["case"], "fn": r["fn"], "diff": d[:5]})
        if r["py"]["outcome"] == "RAISED":
            raised[r["py"]["class"]] = raised.get(r["py"]["class"], 0) + 1
        c1_in, booked_in = ground_reference_input(r["fn"], r["args"])
        if c1_in:
            divs["DIV-A02"] += 1
        if not (c1_in or booked_in):
            removed = []
            un = to_restricted_form(r["un"], removed)
            pyc = {k: v for k, v in r["py"].items() if k != "frames"}
            if json.dumps(un, sort_keys=False) != json.dumps(pyc, sort_keys=False):
                inv1_bad.append(r["case"] + "/" + r["fn"])
            for it in removed:
                if {k: it.get(k) for k in ZERO_ROW} != ZERO_ROW or it.get("group") != "c1":
                    inv2_bad.append(r["case"])
            removed_all += removed
        if r["fn"] in ("check_startup_sequence", "bus_power") and r["py"]["outcome"] == "RAISED":
            if "rfp_power_gate" in r["py"]["frames"]:
                m = r["py"]["message"]
                if not (m.startswith(DIV_A04_PY) or m.startswith("not a bus_power_boundary_a9_v2 ledger")):
                    inv7_bad.append(r["case"])
        if r["fn"] in ("ledger", "official_ledger"):
            for who, res, sink in (("rust", rres, cons_bad), ("python", r["py"], cons_py_bad)):
                if res["outcome"] == "RETURNED":
                    c = cons_ledger(res["value"])
                    if c is not None:
                        if who == "rust":
                            cons_n += 1
                        if not c[0]:
                            sink.append({"case": r["case"], "a1": c[1], "a2": c[2]})
    cons_l1 = json.loads(subprocess.run([str(bindir / "power_cons_l1")], capture_output=True, check=True,
                                        cwd=ROOT).stdout)
    registered = [c for c in cons_l1 if "not registered" not in c["case"]]
    invariants = {
        "INV-A01": {"pass": not inv1_bad, "detail": f"restriction inert on {sum(1 for _ in rows) - divs['DIV-A02']} "
                                                    f"calls without ground-reference input; violations {inv1_bad[:10]}"},
        "INV-A02": {"pass": not inv2_bad, "detail": f"{len(removed_all)} removed group-'c1' rows, every one the "
                                                    f"registered NOT_INSTALLED zero row; violations {inv2_bad[:10]}"},
        "INV-A03": {"pass": rbytes == rbytes2, "detail": "Rust outputs of two separate processes byte-identical"},
        "INV-A04": {"pass": True, "detail": "cargo test -p abep-subsystems --test power "
                                            "flight_taxonomy_equals_the_boundary_record (part of the scored tree's "
                                            "test run, see test_run)"},
        "INV-A05": {"pass": True, "detail": "cargo test -p abep-subsystems --test power "
                                            "rfp_gate_is_not_in_the_physics_crate"},
        "INV-A06": {"pass": True, "detail": "cargo test -p abep-subsystems --test prereg_binding "
                                            "forbidden_identifier_scan_of_this_crate"},
        "INV-A07": {"pass": not inv7_bad, "detail": "no restricted-reference E7 / E9 refusal raised inside "
                                                    "rfp_power_gate other than the two structural input refusals "
                                                    f"named in DIV-A04; violations {inv7_bad[:10]}"},
    }
    tests = subprocess.run(["cargo", "test", "--release", "--locked", "-p", "abep-subsystems", "--test", "power",
                            "--test", "prereg_binding", "--test", "power_system_ledger"], cwd=ROOT, env=P.CARGO_ENV,
                           capture_output=True, text=True)
    test_ok = tests.returncode == 0
    for k in ("INV-A04", "INV-A05", "INV-A06"):
        invariants[k]["pass"] = test_ok
    conservation = {
        "CONS-A1/CONS-A2 (Rust)": {"pass": not cons_bad, "detail": f"{cons_n} COMPLETE Rust ledgers; violations "
                                                                   f"{cons_bad[:10]}"},
        "CONS-A1/CONS-A2 (Python, recorded)": {"pass": not cons_py_bad, "detail": f"violations {cons_py_bad[:10]}"},
        "CONS-L1": {"pass": all(c["met"] for c in registered) and len(registered) == 8,
                    "detail": "; ".join(f"{c['case']} {c['status']} (expected {c['expected_status']}, r "
                                        f"{c['relative_residual']})" for c in cons_l1)},
    }
    lmeas = [r for r in rows if r["case"] == "LE-01" and r["fn"] == "ledger"][0]["args"]
    pe15 = [r for r in rows if r["case"] == "PE-15"][0]["args"]
    perf = {}
    for pid, fn, a, n in (("PERF-A01", "ledger", lmeas, 1000), ("PERF-A02", "p_bus_1ms_max", pe15, 10)):
        py_s = PC.timed(lambda: [py_call(fn, a) for _ in range(n)])
        rr = []
        for _ in range(3):
            res, _ = P.rust_eval(bindir, [{"fn": fn, "args": a, "repeat": n}], work, "perf")
            rr.append(res[0]["elapsed_s"])
        rust_s = sorted(rr)[1]
        perf[pid] = {"python_s": py_s, "rust_s": rust_s, "speedup": py_s / rust_s if rust_s else None,
                     "note": f"{n} evaluations; Rust timed inside power_eval (no process start)"}
    ok = (not failures and all(v["pass"] for v in invariants.values()) and all(v["pass"] for v in
          conservation.values()) and not pinned_bad)
    rnd = re.compile(r"^R\d-")
    counts = {"calls_total": len(rows), "registered_calls": sum(1 for r in rows if not rnd.match(r["case"])),
              "randomized_calls": sum(1 for r in rows if rnd.match(r["case"])),
              "python_RETURNED": sum(r["py"]["outcome"] == "RETURNED" for r in rows),
              "python_RAISED": sum(r["py"]["outcome"] == "RAISED" for r in rows)}
    for fn in ("installed_slots", "ledger", "p_bus_1ms_max", "rf_power_planes", "allocation_checks",
               "icp_power_allocation_check", "check_startup_sequence", "official_ledger", "bus_power"):
        counts[f"calls {fn}"] = sum(r["fn"] == fn for r in rows)
    return {"contract_bytes": contract_bytes, "contract": contract, "seed": seed, "mode": mode, "git": gs,
            "verdict": "ADMITTED" if ok else ("INPUT_MISMATCH" if pinned_bad else "NOT_ADMITTED"),
            "pinned_bad": pinned_bad, "counts": counts, "mismatches": mismatches, "failures": failures,
            "max_ulp": max_ulp, "floats": floats, "invariants": invariants, "conservation": conservation,
            "cons_l1": cons_l1, "divergences": divs, "raised": raised, "perf": perf, "rows": rows, "calls": rcalls,
            "test_run": {"command": "cargo test --release --locked -p abep-subsystems --test power --test "
                                    "prereg_binding --test power_system_ledger", "passed": test_ok,
                         "tail": tests.stdout.strip().splitlines()[-3:]},
            "wall_s": round(time.time() - t0, 1)}


LEDGER_REQUEST = [
    {"component": "C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY", "status": "ADMITTED", "parity": "PARITY_PASS",
     "scope": "whole module for the flight configuration except rfp_power_gate (abep-assess, SC-WP-11) and "
              "GROUND_REFERENCE_TEST_METADATA (GROUND_REFERENCE_ONLY): installed_slots, ledger, p_bus_1ms_max, "
              "rf_power_planes, allocation_checks, icp_power_allocation_check, check_startup_sequence (without the "
              "transient_gate field)",
     "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::power)",
     "python": "rfp_power_gate stays PYTHON_REFERENCE until abep-assess admits it (SC-WP-11)"},
    {"component": "C-ABEP_SIM_BUS_BOUNDARY_A9_PY", "status": "PARTIAL_ADMISSION",
     "scope": "the v1 functions as rebound by v2 for hall_icp_neutralizer (same code objects); the v1 boundary "
              "module itself (bus_power_boundary_a9_v1, hall_c1_reference) is immutable history and is not ported "
              "for the active line (A9.30 sec. 5)"},
    {"component": "C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY", "status": "PARTIAL_ADMISSION",
     "scope": "official_ledger only (row stays SC-WP-10)"},
    {"component": "C-ABEP_SIM_PROGRAMME_DESIGN_SYNTHESIS_PY", "status": "PARTIAL_ADMISSION",
     "scope": "bus_power without its gate_verdict field (row stays SC-WP-10; the gate verdict is SC-WP-11)"},
]


def finalize(res: dict) -> dict:
    contract = res["contract"]
    verdict = res["verdict"]
    if verdict != "ADMITTED":
        for x in LEDGER_REQUEST:
            x["status"] = "NOT_ADMITTED"
    cap = P.write_reference_outputs(CDIR, {
        "calls_v1.json.gz": [{"case": r["case"], "fn": r["fn"], "args": r["args"]} for r in res["rows"]],
        "python_results_v1.json.gz": [{"case": r["case"], "fn": r["fn"], "restricted": {k: v for k, v in
                                       r["py"].items() if k != "frames"}, "unrestricted": {k: v for k, v in
                                       r["un"].items() if k != "frames"}} for r in res["rows"]],
    }, contract["reference_implementation"]["python_commit"], res["git"]["git_head"])
    prev = []
    rep_path = CDIR / "parity_report_v1.json"
    if rep_path.exists():
        prev = json.loads(rep_path.read_text())["campaign_history"]
    bp = P.build_provenance()
    hist = prev + [{"utc": P.utc(), "git_head": res["git"]["git_head"], "git_dirty": res["git"]["git_dirty"],
                    "master_seed": res["seed"], "contract_sha256": PC.sha_bytes(res["contract_bytes"]),
                    "source_sha256_digest": bp["source_sha256_digest"], "verdict": verdict, "wall_s": res["wall_s"]}]
    report = {
        "report_schema": "abep_rust_parity_report_v3_1", "id": "PARITY-REPORT-" + CID + "-V1", "lane": "SC-WP-05",
        "contract": {"path": str(CONTRACT.relative_to(ROOT)), "sha256": PC.sha_bytes(res["contract_bytes"]),
                     "id": contract["id"]},
        "verdict": verdict, "parity": "PARITY_PASS" if verdict == "ADMITTED" else "PARITY_FAIL",
        "verdict_rule": contract["decision_rules"]["verdict"],
        "python_commit": contract["reference_implementation"]["python_commit"],
        "reference_sha256": {f["path"]: f["sha256_at_registration"] for f in
                             contract["reference_implementation"]["files"]},
        "reference_unchanged_at_scoring": True, "pinned_inputs_verified": not res["pinned_bad"],
        "rust_commit": res["git"]["git_head"], "build_provenance": bp, "environment": P.environment(),
        "harness": {"path": str(HARNESS.relative_to(ROOT)), "sha256": PC.sha_file(HARNESS),
                    "common": {"scripts/rust_migration/parity_power_common.py": PC.sha_file(
                        ROOT / "scripts/rust_migration/parity_power_common.py"),
                        "scripts/rust_migration/parity_common.py": PC.sha_file(
                        ROOT / "scripts/rust_migration/parity_common.py")}},
        "scoring_execution": {"utc": P.utc(), "git_dirty": res["git"]["git_dirty"], "master_seed": res["seed"],
                              "comparison_reference": "FLIGHT_RESTRICTED_REFERENCE (contract "
                                                      "reference_implementation.comparison_reference)",
                              "rust_calls_sha256": PC.sha_bytes(json.dumps(res["calls"], ensure_ascii=True).encode())},
        "per_test": {"counts": res["counts"], "mismatches": res["mismatches"], "failures": res["failures"],
                     "max_ulp_distance": res["max_ulp"], "floats_compared": res["floats"],
                     "tolerance": "EXACT_VALUE structure / strings / ints / statuses; ULP_BOUNDED floats (4 ulp or "
                                  "1e-12 relative)"},
        "aggregates": "NOT_APPLICABLE", "invariants": res["invariants"], "conservation": res["conservation"],
        "cons_l1_cases": res["cons_l1"],
        "domain_and_error": {"python_raised_by_class": res["raised"], "divergences_observed": res["divergences"],
                             "message_classes_scored": sorted(MESSAGE_CLASSES)},
        "schema": {"pass": res["mismatches"] == 0, "detail": "field names, order and types compared on every "
                                                             "returned value (value_structure observable)"},
        "test_run": res["test_run"], "performance": res["perf"], "captured_reference_outputs": cap,
        "campaign_history": hist, "development_runs": "development seed 5051 runs were not scored or reported "
                                                      "(contract development_rule)",
        "findings": [
            "CONS-L1 SYS-01 as registered (LS-01 thermal_control 0.0 W) closes with a -3.0 W mismatch on the "
            "THERMAL_CONTROL account because VS-NET deposits Q_thermal_control_W = 3.0 W; r = 0.37 % < 2 % "
            "(EVALUATED, the registered status). The contract text's 'r of order 1e-15' assumed no thermal control "
            "in VS-NET; the registered case is unchanged. SYS-01b (not registered, LS-01 with 3.0 W) closes to "
            "rounding; SYS-02's residual is 37 W (r 4.3 %, MODEL_ERROR as registered) for the same reason",
            "IF-ICP-BUS-v1 plane finding (contract rust_only_registered_interfaces): the NP-ICP producer's "
            "P_icp_bus_W is a supply-input sum for the bias slot and a load-plane value for the RF and match slots, "
            "while NP-THERMAL IK-07 calls it the demand at the spacecraft DC boundary; alignment is for the owner / "
            "NP-ICP lane (IF-ICP-BUS-v2 / IF-ICP-THERMAL-v2)",
            "INV-A07 exception set read as the two structural input refusals named in DIV-A04 (non-empty start-up "
            "sequence; 'not a bus_power_boundary_a9_v2 ledger'), the second scored with the reference text",
        ],
        "ledger_update_requested": LEDGER_REQUEST,
        "meaning_of_ADMITTED": contract["decision_rules"]["meaning_of_ADMITTED"],
        "what_this_is_not": contract["what_this_is_not"],
    }
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=["development", "score"], required=True)
    ap.add_argument("--work", required=True)
    a = ap.parse_args(argv)
    if a.mode == "score" and P.git_state()["git_dirty"]:
        print("refused: score mode needs a clean, committed tree")
        return 2
    res = run(a.mode, Path(a.work))
    if res["verdict"] == "REFUSED_REFERENCE_CHANGED":
        print(json.dumps(res))
        return 1
    print(json.dumps({"verdict": res["verdict"], "mismatches": res["mismatches"], "counts": res["counts"],
                      "max_ulp": res["max_ulp"], "invariants": {k: v["pass"] for k, v in res["invariants"].items()},
                      "conservation": {k: v["pass"] for k, v in res["conservation"].items()},
                      "divergences": res["divergences"], "wall_s": res["wall_s"]}, indent=1))
    for f in res["failures"][:30]:
        print(json.dumps(f, ensure_ascii=False)[:900])
    if a.mode == "score":
        report = finalize(res)
        P.write_report(CDIR, report, P.md_report(report, "Parity report " + CID + " v1"))
    return 0 if res["verdict"] == "ADMITTED" else 1


if __name__ == "__main__":
    sys.exit(main())
