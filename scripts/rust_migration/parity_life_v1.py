"""Parity campaigns of the seven SC-WP-08 materials / life contracts v1.

Python reference (read-only, imported from this checkout) vs the Rust example `life_eval`
(abep_subsystems::materials / ::life) on the preregistered calls of one contract.

  python scripts/rust_migration/parity_life_v1.py --contract C-ABEP_SIM_AOCHEM_PY --mode development --work DIR
  python scripts/rust_migration/parity_life_v1.py --contract C-ABEP_SIM_AOCHEM_PY --mode score --work DIR

Harness transport notes (no change of inputs): mutated committed records (the AO-register lane-32 database, the P4 /
F3 records of the life indicators) travel as {"$committed": rel, "$patch": [[path, value], ...]}; both sides apply the
same patch list to the committed file ({"$delete": true} deletes). The AO-register database text is
json.dumps(patched, indent=1, ensure_ascii=False) on both sides.
"""
from __future__ import annotations

import argparse
import copy
import csv
import dataclasses
import datetime
import gzip
import hashlib
import importlib.util
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_common as PC  # noqa: E402

ROOT = PC.ROOT
sys.path.insert(0, str(ROOT))
CARGO_ENV = dict(os.environ, CARGO_INCREMENTAL="0", CARGO_PROFILE_DEV_DEBUG="0")
PROVENANCE_SOURCES = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/abep-types/**",
                      "crates/abep-provenance/**", "crates/abep-data/**", "crates/abep-hall/**",
                      "crates/abep-subsystems/**"]
K_ULP, R_REL = 4, 1e-12
NAN, INF = float("nan"), float("inf")


def load_file_module(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def loguniform(rng, lo, hi):
    return 10 ** rng.uniform(math.log10(lo), math.log10(hi))


def jsonable(v):
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    return v


def py_result(fn) -> dict:
    try:
        v = fn()
    except Exception as e:  # noqa: BLE001 - every exception class is an observable
        return {"outcome": "RAISED", "class": type(e).__name__, "message": str(e)}
    return {"outcome": "RETURNED", "value": json.loads(json.dumps(jsonable(v)))}


def apply_patch(v, patch):
    v = copy.deepcopy(v)
    for path, val in patch:
        cur = v
        for k in path[:-1]:
            cur = cur[k]
        if isinstance(val, dict) and "$delete" in val:
            if isinstance(cur, dict):
                cur.pop(path[-1], None)
            else:
                del cur[path[-1]]
        else:
            cur[path[-1]] = val
    return v


def committed_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


# ============================================================================================== comparison
def ulp_ok(r: float, p: float) -> tuple[bool, float]:
    if math.isnan(p) or math.isnan(r):
        return (math.isnan(p) and math.isnan(r)), 0.0
    if math.isinf(p) or math.isinf(r):
        return r == p, 0.0
    d = abs(r - p)
    u = math.ulp(p) if p != 0 else math.ulp(0.0)
    return (d <= K_ULP * u or d <= R_REL * max(1.0, abs(p))), (d / u if u else 0.0)


def tree_diff(p, r, path="$", stats=None):
    stats = stats if stats is not None else {"max_ulp": 0.0, "floats": 0}
    if isinstance(p, bool) or isinstance(r, bool):
        return ([] if (type(p) is type(r) and p == r) else [f"{path}: {p!r} != {r!r}"]), stats
    if isinstance(p, float) and isinstance(r, float):
        ok, u = ulp_ok(r, p)
        stats["floats"] += 1
        stats["max_ulp"] = max(stats["max_ulp"], u)
        return ([] if ok else [f"{path}: float {p!r} != {r!r}"]), stats
    if type(p) is not type(r):
        return [f"{path}: type {type(p).__name__} != {type(r).__name__} ({p!r:.80} / {r!r:.80})"], stats
    if isinstance(p, dict):
        if list(p) != list(r):
            return [f"{path}: keys {list(p)} != {list(r)}"], stats
        out = []
        for k in p:
            out += tree_diff(p[k], r[k], f"{path}.{k}", stats)[0]
        return out, stats
    if isinstance(p, list):
        if len(p) != len(r):
            return [f"{path}: length {len(p)} != {len(r)}"], stats
        out = []
        for i, (a, b) in enumerate(zip(p, r)):
            out += tree_diff(a, b, f"{path}[{i}]", stats)[0]
        return out, stats
    return ([] if p == r else [f"{path}: {p!r:.160} != {r!r:.160}"]), stats


def compare(exp: dict, rs: dict, message_classes: set) -> tuple[list, dict]:
    stats = {"max_ulp": 0.0, "floats": 0}
    if exp["outcome"] != rs["outcome"]:
        return [f"outcome {exp['outcome']} != {rs['outcome']} (expected {exp.get('class')}: "
                f"{exp.get('message')!r:.300}; rust {rs.get('class')}: {rs.get('message')!r:.300}; rust value "
                f"{str(rs.get('value'))[:200]})"], stats
    if exp["outcome"] == "RETURNED":
        return tree_diff(exp["value"], rs["value"], "$", stats)
    out = []
    if exp["class"] != rs["class"]:
        out.append(f"class {exp['class']} != {rs['class']} (expected {exp['message']!r:.300}; rust "
                   f"{rs['message']!r:.300})")
    elif exp["class"] in message_classes and exp["message"] != rs["message"]:
        out.append(f"message differs: expected {exp['message']!r} | rust {rs['message']!r}")
    return out, stats


def returned(rows, who, fn=None):
    for r in rows:
        res = r[who]
        if res["outcome"] == "RETURNED" and (fn is None or r["fn"] == fn):
            yield r, res["value"]


# ============================================================================================== 1 aochem
from abep_sim import aochem as AO  # noqa: E402
from abep_sim import constants as K  # noqa: E402
from abep_sim import materials as MAT  # noqa: E402


def frozen_rows():
    with open(ROOT / "abep_sim/data/atmosphere_msis21_v1.csv", newline="") as f:
        for r in csv.DictReader(f):
            alt = float(r["alt_km"])
            yield {"rho": float(r["rho"]), "fO": float(r["fO"]), "fN2": float(r["fN2"]), "fO2": float(r["fO2"]),
                   "V": math.sqrt(K.MU_EARTH / (K.R_EARTH + alt * 1e3))}


def aochem_calls(contract, seed):
    calls = [("R-A00", "aochem.tables", {})]
    for i, atm in enumerate(frozen_rows()):
        calls.append((f"R-A01-{i}-flux", "aochem.ao_flux", {"atm": atm}))
        for h in (1.0, 1000.0, 15000.0, 26000.0, 26280.0):
            calls.append((f"R-A01-{i}-fl{h}", "aochem.fluence", {"atm": atm, "hours": h}))
        calls.append((f"R-A01-{i}-inlet", "aochem.inlet_composition", {"atm": atm}))
        calls.append((f"R-A01-{i}-report", "aochem.material_report", {"atm": atm, "hours": 26280.0}))
    for m in AO.EROSION_YIELD_CM3_PER_ATOM:
        for f in (1.0, 0.5, 0.0):
            calls.append((f"R-A02-{m}-{f}", "aochem.erosion_depth_um",
                          {"material": m, "fl_atoms_m2": 1.0e22, "exposure_factor": f}))
    for w in AO.RECOMB_GAMMA:
        for slot in ("intake_wall", "compressor_wall", "reservoir_wall"):
            calls.append((f"R-A02-{slot}-{w}", "aochem.recombination_fraction", {"ao": {"fields": {slot: w}}}))
    atm0 = {"rho": 2.5e-10, "fO": 0.6, "fN2": 0.35, "fO2": 0.05, "V": 7784.0}
    E = []
    E.append(("E-A01a", "aochem.erosion_depth_um", {"material": "nope", "fl_atoms_m2": 1e22}))
    E.append(("E-A01b", "aochem.material_report", {"atm": atm0, "hours": 1.0, "materials": ["kapton_HN", "nope"]}))
    for slot in ("intake_wall", "compressor_wall", "reservoir_wall"):
        E.append((f"E-A02-{slot}", "aochem.recombination_fraction", {"ao": {"fields": {slot: "nope"}}}))
    for k in ("rho", "fO", "V"):
        a = {x: v for x, v in atm0.items() if x != k}
        E.append((f"E-A03-flux-{k}", "aochem.ao_flux", {"atm": a}))
    for k in ("fN2", "fO2", "fO"):
        a = {x: v for x, v in atm0.items() if x != k}
        E.append((f"E-A03-inlet-{k}", "aochem.inlet_composition", {"atm": a}))
    E.append(("E-A04", "aochem.inlet_composition", {"atm": dict(atm0, fO=0.0, fN2=0.0, fO2=0.0)}))
    for n in (-1e5, 0.0, 1e9):
        E.append((f"E-A05-{n}", "aochem.recombination_fraction",
                  {"ao": {"fields": {"compressor_wall": "stainless_steel", "n_wall_collisions_compressor": n}}}))
    E.append(("E-A05-inlet", "aochem.inlet_composition",
              {"atm": atm0, "ao": {"fields": {"n_wall_collisions_compressor": -1e5}}}))
    E.append(("E-A06-h0", "aochem.fluence", {"atm": atm0, "hours": 0.0}))
    E.append(("E-A06-hneg", "aochem.fluence", {"atm": atm0, "hours": -1.0}))
    E.append(("E-A06-V0", "aochem.ao_flux", {"atm": dict(atm0, V=0.0)}))
    E.append(("E-A06-rho0", "aochem.ao_flux", {"atm": dict(atm0, rho=0.0)}))
    E.append(("E-A06-ef0", "aochem.erosion_depth_um", {"material": "kapton_HN", "fl_atoms_m2": 1e22, "exposure_factor": 0.0}))
    E.append(("E-A06-efneg", "aochem.erosion_depth_um", {"material": "kapton_HN", "fl_atoms_m2": 1e22, "exposure_factor": -1.0}))
    E.append(("E-A06-empty", "aochem.material_report", {"atm": atm0, "hours": 10.0, "materials": []}))
    E.append(("E-A06-none", "aochem.material_report", {"atm": atm0, "hours": 10.0, "materials": None}))
    for k, v in (("rho", NAN), ("fO", INF), ("V", NAN), ("V", -INF)):
        E.append((f"E-A07-flux-{k}-{v}", "aochem.ao_flux", {"atm": dict(atm0, **{k: v})}))
        E.append((f"E-A07-inlet-{k}-{v}", "aochem.inlet_composition", {"atm": dict(atm0, **{k: v})}))
    E.append(("E-A07-hours", "aochem.fluence", {"atm": atm0, "hours": NAN}))
    E.append(("E-A07-fl", "aochem.erosion_depth_um", {"material": "silver", "fl_atoms_m2": INF}))
    calls += E
    n = contract["inputs"]["randomized_domain"]["generators"]
    mats = list(AO.EROSION_YIELD_CM3_PER_ATOM)
    walls = list(AO.RECOMB_GAMMA)

    def atm(r):
        return {"rho": loguniform(r, 1e-13, 1e-8), "fO": r.uniform(0, 1), "fN2": r.uniform(0, 1),
                "fO2": r.uniform(0, 1), "V": r.uniform(6500, 8200)}

    def mat(r):
        return "nope" if r.random() < 0.03 else r.choice(mats)

    def wall(r):
        return "nope" if r.random() < 0.03 else r.choice(walls)

    def ao(r):
        return {"fields": {"intake_wall": wall(r), "compressor_wall": wall(r), "reservoir_wall": wall(r),
                           "n_wall_collisions_intake": r.uniform(0, 600), "n_wall_collisions_compressor":
                               r.uniform(0, 600), "n_wall_collisions_reservoir": r.uniform(0, 600)}}

    def mats_list(r):
        return None if r.random() < 0.3 else r.sample(mats, r.randint(1, len(mats)))

    gens = [("0 ao_flux", "aochem.ao_flux", lambda r: {"atm": atm(r)}),
            ("1 fluence", "aochem.fluence", lambda r: {"atm": atm(r), "hours": r.uniform(0, 30000)}),
            ("2 erosion_depth_um", "aochem.erosion_depth_um",
             lambda r: {"material": mat(r), "fl_atoms_m2": loguniform(r, 1e18, 1e26), "exposure_factor": r.uniform(0, 1)}),
            ("3 recombination_fraction", "aochem.recombination_fraction", lambda r: {"ao": ao(r)}),
            ("4 inlet_composition", "aochem.inlet_composition", lambda r: {"atm": atm(r), "ao": ao(r)}),
            ("5 material_report", "aochem.material_report",
             lambda r: {"atm": atm(r), "hours": r.uniform(0, 30000), "materials": mats_list(r),
                        "exposure_factor": r.uniform(0, 1)})]
    for k, (key, fn, gen) in enumerate(gens):
        rng = random.Random(seed * 1000 + k)
        for i in range(n[key]):
            calls.append((f"R{k}-{i}", fn, gen(rng)))
    return calls


def aochem_py(fn, a):
    def ao():
        return AO.AOParams(**a["ao"]["fields"]) if a.get("ao") else AO.AOParams()
    if fn == "aochem.tables":
        return py_result(lambda: {"EROSION_YIELD_CM3_PER_ATOM": dict(AO.EROSION_YIELD_CM3_PER_ATOM),
                                  "RECOMB_GAMMA": dict(AO.RECOMB_GAMMA),
                                  "AOParams": dataclasses.asdict(AO.AOParams())})
    if fn == "aochem.ao_flux":
        return py_result(lambda: AO.ao_flux(a["atm"]))
    if fn == "aochem.fluence":
        return py_result(lambda: AO.fluence(a["atm"], a["hours"]))
    if fn == "aochem.erosion_depth_um":
        return py_result(lambda: AO.erosion_depth_um(a["material"], a["fl_atoms_m2"], a.get("exposure_factor", 1.0)))
    if fn == "aochem.recombination_fraction":
        return py_result(lambda: AO.recombination_fraction(ao()))
    if fn == "aochem.inlet_composition":
        return py_result(lambda: AO.inlet_composition(a["atm"], ao()))
    if fn == "aochem.material_report":
        return py_result(lambda: AO.material_report(a["atm"], a["hours"], a.get("materials"),
                                                    a.get("exposure_factor", 1.0)))
    raise KeyError(fn)


def aochem_inv(rows):
    out = {}
    bad1, bad2 = {"py": [], "rs": []}, {"py": [], "rs": []}
    n1 = 0
    for who in ("py", "rs"):
        for r, v in returned(rows, who, "aochem.inlet_composition"):
            atm = r["args"]["atm"]
            vals = [atm["fO"], atm["fO2"], atm["fN2"], v["fO"], v["fO2"], v["fN2"], v["O_survival"]]
            if not all(math.isfinite(x) for x in vals):
                continue
            n1 += who == "py"
            s_in = atm["fO"] + atm["fO2"] + atm["fN2"]
            s_out = v["fO"] + v["fO2"] + v["fN2"]
            ok = abs(s_out - s_in) <= 1e-14 * max(1.0, abs(s_in))
            if 0.0 <= v["O_survival"] <= 1.0 and atm["fO"] >= 0:
                ok &= v["fO"] <= atm["fO"]
            if not ok:
                bad1[who].append(r["case"])
        for r, v in returned(rows, who, "aochem.material_report"):
            want = r["args"].get("materials") or list(AO.EROSION_YIELD_CM3_PER_ATOM)
            names = [x["material"] for x in v]
            fls = {json.dumps(x["fluence_atoms_m2"]) for x in v}
            if names != want or len(fls) > 1:
                bad2[who].append(r["case"])
    out["INV-A01"] = {"pass": not bad1["py"] and not bad1["rs"],
                      "detail": f"{n1} finite inlet_composition results per implementation: |sum out - sum in| <= "
                                f"1e-14 max(1, sum) and fO <= fO_in for 0 <= survival <= 1; violations py "
                                f"{bad1['py'][:5]} rust {bad1['rs'][:5]}"}
    out["INV-A02"] = {"pass": not bad2["py"] and not bad2["rs"],
                      "detail": f"material_report rows in requested order with one fluence; violations py "
                                f"{bad2['py'][:5]} rust {bad2['rs'][:5]}"}
    return out, {"CONS-A01 (Rust)": {"pass": not bad1["rs"], "detail": "inlet_composition mass split (INV-A01 rule)"},
                 "CONS-A01 (Python, recorded)": {"pass": not bad1["py"], "detail": "same rule on the Python outputs"}}


# ============================================================================================== 2 materials
def mat_fields_draw(r):
    def num(lo, hi):
        x = r.uniform(lo, hi)
        return int(round(x)) if r.random() < 0.1 else x
    f = {"name": f"rand-{r.randint(0, 10**6)}", "cls": r.choice(["metal", "ceramic", "coating", "polymer"]),
         "density": num(1000, 20000), "E_GPa": num(1, 400), "yield_MPa": num(0, 900), "cte_ppm_K": num(0.5, 25),
         "k_W_mK": num(0.1, 400), "cp_J_kgK": num(100, 1200), "emissivity": num(0.02, 0.9),
         "absorptivity": num(0.1, 0.9), "ao_yield_cm3_atom": r.choice([0.0, loguniform(r, 1e-26, 1e-23)]),
         "gamma_min": loguniform(r, 1e-4, 0.1), "gamma0": loguniform(r, 1e-3, 1.0), "gamma_Ea_eV": num(0.01, 0.3),
         "sputter_Eth_eV": num(10, 80), "sputter_Y300": num(0.1, 3), "see_Emax_eV": num(100, 700),
         "see_dmax": num(0.5, 7), "tml_pct": num(0, 1), "cvcm_pct": num(0, 0.1), "rad_tid_krad": num(1e5, 1e7),
         "T_max_K": num(300, 2500)}
    return f


def materials_calls(contract, seed):
    calls = [("R-M00", "materials.db", {})]
    for m in MAT.DB.values():
        spec = {"name": m.name}
        for T in (150.0, 293.15, 350.0, 600.0, 1200.0):
            calls.append((f"R-M01-{m.name}-g{T}", "materials.gamma_O", {"material": spec, "T_K": T}))
        for E in (0.0, 10.0, m.sputter_Eth_eV, m.sputter_Eth_eV + 1e-9, 50.0, 100.0, 300.0, 1000.0):
            calls.append((f"R-M01-{m.name}-s{E}", "materials.sputter_yield", {"material": spec, "E_eV": E}))
            calls.append((f"R-M01-{m.name}-e{E}", "materials.see_yield", {"material": spec, "E_eV": E}))
        calls.append((f"R-M01-{m.name}-rec", "materials.record", {"fields": dataclasses.asdict(m)}))
    for a0 in (0.0, 0.6, 0.8, 1.0):
        for F in (0.0, 1e24, 1e26, 1e27, 1e28):
            calls.append((f"R-M02-{a0}-{F}", "materials.surface_ageing_alpha", {"alpha0": a0, "fluence_atoms_m2": F}))
            calls.append((f"R-M02v-{a0}-{F}", "materials.surface_ageing_alpha",
                          {"alpha0": a0, "fluence_atoms_m2": F, "phi_c": 1e25, "alpha_inf": 0.9}))
    base = dataclasses.asdict(MAT.DB["SS316"])
    E = [("E-M01", "materials.gamma_O", {"material": {"name": "nope"}, "T_K": 300.0})]
    E.append(("E-M02a", "materials.record", {"fields": {k: v for k, v in base.items() if k != "density"}}))
    E.append(("E-M02b", "materials.record", {"fields": dict(base, bogus=1)}))
    for T in (0.0, -1.0, -1e-3, 0):
        E.append((f"E-M03-{T!r}", "materials.gamma_O", {"material": {"name": "SS316"}, "T_K": T}))
    for eth, e in ((0, 10.0), (0.0, 10.0), (0, 10), (300, 400.0), (300.0, 400.0), (400, 500.0), (30, NAN), (30, INF)):
        E.append((f"E-M04-{eth!r}-{e!r}", "materials.sputter_yield",
                  {"material": {"fields": dict(base, sputter_Eth_eV=eth)}, "E_eV": e}))
    E.append(("E-M05a", "materials.see_yield", {"material": {"fields": dict(base, see_Emax_eV=0)}, "E_eV": 10.0}))
    E.append(("E-M05b", "materials.see_yield", {"material": {"name": "SS316"}, "E_eV": -1e6}))
    E.append(("E-M06a", "materials.surface_ageing_alpha", {"alpha0": 0.5, "fluence_atoms_m2": 1e20, "phi_c": 0.0}))
    E.append(("E-M06b", "materials.surface_ageing_alpha", {"alpha0": 0.5, "fluence_atoms_m2": -1e30}))
    E.append(("E-M06c", "materials.surface_ageing_alpha", {"alpha0": NAN, "fluence_atoms_m2": 1e20}))
    E.append(("E-M07", "materials.record", {"fields": dict(base, density=8000, gamma0=1, see_Emax_eV=300)}))
    E.append(("E-M07b", "materials.gamma_O", {"material": {"fields": dict(base, gamma_Ea_eV=0, gamma0=1)}, "T_K": 300}))
    calls += E
    n = contract["inputs"]["randomized_domain"]["generators"]
    names = list(MAT.DB)

    def spec(r):
        return {"name": r.choice(names)} if r.random() < 0.5 else {"fields": mat_fields_draw(r)}

    gens = [("0 gamma_O", "materials.gamma_O", lambda r: {"material": spec(r), "T_K": r.uniform(100, 2500)}),
            ("1 sputter_yield", "materials.sputter_yield", lambda r: {"material": spec(r), "E_eV": r.uniform(0, 2000)}),
            ("2 see_yield", "materials.see_yield", lambda r: {"material": spec(r), "E_eV": r.uniform(0, 2000)}),
            ("3 surface_ageing_alpha", "materials.surface_ageing_alpha",
             lambda r: {"alpha0": r.uniform(0, 1), "fluence_atoms_m2": loguniform(r, 1e20, 1e29),
                        "phi_c": loguniform(r, 1e24, 1e28), "alpha_inf": r.uniform(0.5, 1.0)}),
            ("4 record", "materials.record", lambda r: {"fields": mat_fields_draw(r)})]
    for k, (key, fn, gen) in enumerate(gens):
        rng = random.Random(seed * 1000 + k)
        for i in range(n[key]):
            calls.append((f"R{k}-{i}", fn, gen(rng)))
    return calls


def materials_py(fn, a):
    def mat():
        s = a["material"]
        return MAT.DB[s["name"]] if "name" in s else MAT.Material(**s["fields"])
    if fn == "materials.db":
        return py_result(lambda: [dataclasses.asdict(m) for m in MAT.DB.values()])
    if fn == "materials.record":
        return py_result(lambda: dataclasses.asdict(MAT.Material(**a["fields"])))
    if fn == "materials.gamma_O":
        return py_result(lambda: mat().gamma_O(a["T_K"]))
    if fn == "materials.sputter_yield":
        return py_result(lambda: mat().sputter_yield(a["E_eV"]))
    if fn == "materials.see_yield":
        return py_result(lambda: mat().see_yield(a["E_eV"]))
    if fn == "materials.surface_ageing_alpha":
        kw = {k: a[k] for k in ("phi_c", "alpha_inf") if k in a}
        return py_result(lambda: MAT.surface_ageing_alpha(a["alpha0"], a["fluence_atoms_m2"], **kw))
    raise KeyError(fn)


def materials_inv(rows):
    bad1, bad2 = [], []
    for who in ("py", "rs"):
        for r, v in returned(rows, who, "materials.db"):
            if [x["name"] for x in v] != list(MAT.DB) or any(
                    x["fidelity"] != "literature" or x["source"] != "literature-class prior" for x in v):
                bad1.append(who)
        for r, v in returned(rows, who, "materials.sputter_yield"):
            s = r["args"]["material"]
            eth = MAT.DB[s["name"]].sputter_Eth_eV if "name" in s and s["name"] in MAT.DB else \
                s.get("fields", {}).get("sputter_Eth_eV")
            e = r["args"]["E_eV"]
            if isinstance(eth, (int, float)) and isinstance(e, (int, float)) and e <= eth and v != 0.0:
                bad2.append((who, r["case"]))
    return {"INV-M01": {"pass": not bad1, "detail": f"DB names in order, fidelity / source labels kept; violations {bad1}"},
            "INV-M02": {"pass": not bad2, "detail": f"sputter_yield 0.0 at or below Eth; violations {bad2[:10]}"}}, {}


# ============================================================================================== 3 sputter
SY = load_file_module("sputter_yields_ref", "docs/evidence/sputter_yields_v1/build_sputter_yields_v1.py")


def sputter_calls(contract, seed):
    captured = {"yt": [], "ap": []}
    oy, oa = SY.yamamura_tawara, SY.apid_fit

    def wy(*a, **k):
        captured["yt"].append(list(a))
        return oy(*a, **k)

    def wa(*a, **k):
        captured["ap"].append(list(a))
        return oa(*a, **k)
    SY.yamamura_tawara, SY.apid_fit = wy, wa
    try:
        SY.build(SY.load_inputs())
    finally:
        SY.yamamura_tawara, SY.apid_fit = oy, oa
    calls = [(f"R-S01-yt-{i}", "sputter.yamamura_tawara", {"args": a}) for i, a in enumerate(captured["yt"])]
    calls += [(f"R-S01-ap-{i}", "sputter.apid_fit", {"args": a}) for i, a in enumerate(captured["ap"])]
    inp = SY.load_inputs()
    aw, zn = inp["atomic_weights"]["values"], inp["atomic_numbers"]
    us, q, w, s = inp["nifs_table1"]["rows"]["Au"]
    yt0 = [1000.0, zn["He"], aw["He"], zn["Au"], aw["Au"], us, q, w, s]
    ap0 = [100.0, 1.6012e-02, 4.9256, 1.8338, 8.882e-07, 46.767]
    calls += [("R-S02-yt-worked", "sputter.yamamura_tawara", {"args": yt0}),
              ("R-S02-yt-us0", "sputter.yamamura_tawara", {"args": [100.0, 7, 14.007, 74, 183.84, 0.0, 0.72, 2.14, 2.8]}),
              ("R-S02-yt-nan", "sputter.yamamura_tawara", {"args": [NAN, 7, 14.007, 74, 183.84, 8.9, 0.72, 2.14, 2.8]}),
              ("R-S02-ap-100", "sputter.apid_fit", {"args": ap0}),
              ("R-S02-ap-40", "sputter.apid_fit", {"args": [40.0] + ap0[1:]}),
              ("R-S02-ap-lam0", "sputter.apid_fit", {"args": [100.0, 0.0] + ap0[2:]})]
    pool = [0, 0.0, -1.0, NAN, INF, -INF, None, "1.0", False, True, 7]
    for idx in (0, 2, 4, 5, 6, 7, 8):
        for j, x in enumerate(pool):
            a = list(yt0)
            a[idx] = x
            calls.append((f"E-S01-yt-{idx}-{j}", "sputter.yamamura_tawara", {"args": a}))
    for idx in range(6):
        for j, x in enumerate(pool):
            a = list(ap0)
            a[idx] = x
            calls.append((f"E-S01-ap-{idx}-{j}", "sputter.apid_fit", {"args": a}))
    for tag, z1, z2 in (("z1", 0, 79), ("z2", 2, 0), ("both", 0, 0)):
        a = list(yt0)
        a[1], a[3] = z1, z2
        calls.append((f"E-S02-{tag}", "sputter.yamamura_tawara", {"args": a}))
    eth = oy(1e9, *yt0[1:])["Eth_eV"]
    calls.append(("E-S03-yt", "sputter.yamamura_tawara", {"args": [eth] + yt0[1:]}))
    calls.append(("E-S03-ap", "sputter.apid_fit", {"args": [ap0[5]] + ap0[1:]}))
    calls.append(("E-S04-eq", "sputter.yamamura_tawara", {"args": [500.0, 8, 16.0, 8, 16.0, 2.6, 1.0, 2.0, 2.5]}))
    calls.append(("E-S04-gt", "sputter.yamamura_tawara", {"args": [500.0, 54, 131.3, 6, 12.011, 7.37, 1.7, 1.84, 2.5]}))
    n = contract["inputs"]["randomized_domain"]["generators"]

    def maybe(r, v):
        return r.choice(pool) if r.random() < 0.01 else v

    def yt(r):
        e = loguniform(r, 1, 1e5)
        e = int(round(e)) if r.random() < 0.3 and e >= 1 else e
        a = [e, r.randint(1, 92), r.uniform(1, 240), r.randint(1, 92), r.uniform(1, 240), r.uniform(1, 10),
             r.uniform(0.1, 3), r.uniform(0.5, 5), r.uniform(2, 3)]
        return {"args": [maybe(r, a[0]), a[1], maybe(r, a[2]), a[3]] + [maybe(r, x) for x in a[4:]]}

    def ap(r):
        e = loguniform(r, 1, 1e5)
        e = int(round(e)) if r.random() < 0.3 else e
        a = [e, r.uniform(0.01, 10), r.uniform(0.01, 10), r.uniform(0.5, 3), loguniform(r, 1e-7, 1e-3),
             r.uniform(1, 200)]
        return {"args": [maybe(r, x) for x in a]}
    for k, (key, fn, gen) in enumerate([("0 yamamura_tawara", "sputter.yamamura_tawara", yt),
                                         ("1 apid_fit", "sputter.apid_fit", ap)]):
        rng = random.Random(seed * 1000 + k)
        for i in range(n[key]):
            calls.append((f"R{k}-{i}", fn, gen(rng)))
    return calls


def sputter_py(fn, a):
    if fn == "sputter.yamamura_tawara":
        return py_result(lambda: SY.yamamura_tawara(*a["args"]))
    if fn == "sputter.apid_fit":
        return py_result(lambda: SY.apid_fit(*a["args"]))
    raise KeyError(fn)


def sputter_inv(rows):
    bad = []
    for who in ("py", "rs"):
        for r, v in returned(rows, who, "sputter.yamamura_tawara"):
            if list(v) != ["Y", "Eth_eV", "below_threshold"] or (v["below_threshold"] != (v["Y"] == 0.0)):
                bad.append((who, r["case"]))
    return {"INV-S01": {"pass": not bad, "detail": f"keys Y, Eth_eV, below_threshold; Y == 0.0 exactly when "
                                                   f"below_threshold; violations {bad[:10]}"}}, {}


# ============================================================================================== 4 AO register
AR = load_file_module("ao_register_ref", "docs/experiments/lifetime_ao/build_ao_lifetime_register.py")
EVEN_ALTS = list(range(150, 301, 2))


def db_mutation(r, db):
    """1..4 registered mutations of the lane-32 database: a patch list."""
    patch = []
    ents = len(db["entries"])
    for _ in range(r.randint(1, 4)):
        i = r.randrange(ents)
        op = r.randrange(9)
        if op == 0:
            patch.append([["entries", i, "data"], {"$delete": True}])
        elif op == 1:
            patch.append([["entries", i, "energy_range_eV"], {k: v for k, v in db["entries"][i]["energy_range_eV"].items()
                                                              if k != "max"}])
        elif op == 2:
            patch.append([["entries", i, "energy_range_eV"], dict(db["entries"][i]["energy_range_eV"], tbd="mutated")])
        elif op == 3:
            patch.append([["entries", i, "data"], r.choice([None, "text", 5, ["x"]])])
        elif op == 4:
            patch.append([["entries", i, "data"], {"rows": r.choice([None, "x", {"a": 1}, [1, 2, 3]])}])
        elif op == 5:
            patch.append([["entries", i, r.choice(["id", "projectile", "units", "source_locator", "values_status"])],
                          {"$delete": True}])
        elif op == 6:
            patch.append([["coverage_matrix", "Z+"], {"T": {"status": "mutated", "entries": ["e1"]}}])
        elif op == 7:
            patch.append([["coverage_matrix", "legend"], {"$delete": True}])
        else:
            j = r.randrange(ents)
            patch.append([["entries", i], db["entries"][j]])
    return patch


def aoreg_calls(contract, seed):
    sha = AR.ATMOSPHERE_CSV_SHA256
    calls = [("R-L01", "aoreg.environment", {"altitudes": [180, 200, 230], "csv_sha256": sha}),
             ("R-L02a", "aoreg.environment", {"altitudes": [150, 300], "csv_sha256": sha}),
             ("R-L02b", "aoreg.environment", {"altitudes": [200], "csv_sha256": sha}),
             ("R-L02c", "aoreg.environment", {"altitudes": EVEN_ALTS, "csv_sha256": sha}),
             ("R-L03", "aoreg.index", {"db_rel": AR.WALL_LIFE_DB_REL, "db_sha256": AR.WALL_LIFE_DB_SHA256,
                                       "db_text": None}),
             ("E-L01", "aoreg.environment", {"altitudes": [180, 200, 230], "csv_sha256": "0" * 64}),
             ("E-L02a", "aoreg.environment", {"altitudes": [181], "csv_sha256": sha}),
             ("E-L02b", "aoreg.environment", {"altitudes": [180, 181], "csv_sha256": sha}),
             ("E-L03", "aoreg.environment", {"altitudes": [], "csv_sha256": sha}),
             ("E-L04", "aoreg.index", {"db_rel": AR.WALL_LIFE_DB_REL, "db_sha256": "0" * 64, "db_text": None})]
    n = contract["inputs"]["randomized_domain"]["generators"]
    rng = random.Random(seed * 1000 + 0)
    for i in range(n["0 environment"]):
        alts = rng.sample(EVEN_ALTS, rng.randint(1, 6))
        if rng.random() < 0.05:
            alts.insert(rng.randrange(len(alts) + 1), rng.choice(range(151, 300, 2)))
        calls.append((f"R0-{i}", "aoreg.environment", {"altitudes": alts, "csv_sha256": sha}))
    rng = random.Random(seed * 1000 + 1)
    db = committed_json(AR.WALL_LIFE_DB_REL)
    for i in range(n["1 index"]):
        patch = db_mutation(rng, db)
        text = json.dumps(apply_patch(db, patch), indent=1, ensure_ascii=False)
        dsha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        calls.append((f"R1-{i}", "aoreg.index", {"db_rel": f"{AR_WORK['dir']}/R1-{i}.json", "db_sha256": dsha,
                                                 "db_text": None, "db_patch": patch}))
    return calls


AR_WORK = {"dir": None}


def aoreg_py(fn, a):
    if fn == "aoreg.environment":
        saved = (AR.ALTITUDES_KM, AR.ATMOSPHERE_CSV_SHA256)
        AR.ALTITUDES_KM, AR.ATMOSPHERE_CSV_SHA256 = tuple(a["altitudes"]), a["csv_sha256"]
        try:
            return py_result(AR.compute_ao_environment)
        finally:
            AR.ALTITUDES_KM, AR.ATMOSPHERE_CSV_SHA256 = saved
    if fn == "aoreg.index":
        saved = (AR.WALL_LIFE_DB_REL, AR.WALL_LIFE_DB_SHA256)
        rel = a["db_rel"]
        if "db_patch" in a:
            text = json.dumps(apply_patch(committed_json(AR.WALL_LIFE_DB_REL), a["db_patch"]), indent=1,
                              ensure_ascii=False)
            Path(rel).parent.mkdir(parents=True, exist_ok=True)
            Path(rel).write_bytes(text.encode("utf-8"))
        AR.WALL_LIFE_DB_REL, AR.WALL_LIFE_DB_SHA256 = rel, a["db_sha256"]
        try:
            return py_result(AR.compute_wall_sputter_index)
        finally:
            AR.WALL_LIFE_DB_REL, AR.WALL_LIFE_DB_SHA256 = saved
    raise KeyError(fn)


def aoreg_inv(rows):
    v5 = committed_json("docs/experiments/lifetime_ao/ao_lifetime_register_v5.json")["derived"]
    out = {}
    for inv, case, key in (("INV-L01", "R-L01", "ao_environment"), ("INV-L02", "R-L03", "wall_sputter_index")):
        row = [r for r in rows if r["case"] == case][0]
        diffs = []
        for who in ("py", "rs"):
            res = row[who]
            if res["outcome"] != "RETURNED":
                diffs.append(f"{who} raised")
            else:
                diffs += [f"{who}: {d}" for d in tree_diff(v5[key], res["value"])[0]]
        out[inv] = {"pass": not diffs, "detail": f"{case} equals the committed register v5 derived.{key} (both); "
                                                 f"differences {diffs[:5]}"}
    return out, {}


# ============================================================================================== 5 P4
P4S = load_file_module("p4_screening_ref", "docs/experiments/hall_icp/p4_anode_materials/p4_screening.py")
P4R = load_file_module("p4_rules_ref", "docs/experiments/hall_icp/p4_anode_materials/p4_a9_16_rules.py")
P4_REL = "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json"


def canon_sha(rec):
    return hashlib.sha256(json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def syn_req(kind="min", prop="P-SYN", value=10.0, unit="K", status="OWNER_GIVEN", domain=None):
    return {"id": "RQ-SYN", "criterion": "CR-SYN", "application": "APP-SYN", "property": prop, "kind": kind,
            "value": value, "unit": unit, "status": status, "source": "SYNTHETIC_TEST_DATA_NOT_EVIDENCE",
            "domain": domain or ["d1"]}


def syn_prop(prop="P-SYN", value=12.0, unit="K", domain=None, adm=True):
    return {"id": "PR-SYN", "candidate": "CAND-SYN", "property": prop, "value_si": value, "unit_si": unit,
            "condition": {}, "domain": domain or ["d1", "d2"], "source_id": "SYN", "locator": "SYN",
            "quantity_type": "measured", "evidence_level": "SYNTHETIC_TEST_DATA_NOT_EVIDENCE",
            "admissible_for_gate": adm, "synthetic": True}


def stage_records():
    s1 = {"basis": P4R.STAGE_1, "material": "MAT-SYN", "T_limit_K": 900.0, "source": "SYN",
          "preregistered_acceptance": "LOCK2-SYN", "criteria_met": True,
          "conditions": {c: "REG-SYN" for c in P4R.STAGE_1_CONDITIONS},
          "metrics": {m: "REG-SYN" for m in P4R.STAGE_1_METRICS},
          "preregistered_exposure_duration_h": 100.0, "exposure_duration_h": 120.0}
    s2 = {"basis": P4R.STAGE_2, "material": "MAT-SYN", "T_limit_K": 900.0, "source": "SYN",
          "preregistered_acceptance": "LOCK2-SYN", "criteria_met": True,
          "stage_1_record": {"stage": P4R.STAGE_1, "material": "MAT-SYN"}, "down_selected": True,
          "configuration": "REPLACEABLE_ANODE", "article": "H-1",
          "environment": {e: "REG-SYN" for e in P4R.STAGE_2_ENVIRONMENT},
          "at_intended_continuous_use_condition": True}
    s3 = {"basis": P4R.STAGE_3, "material": "MAT-SYN", "T_limit_K": 900.0, "source": "SYN",
          "preregistered_acceptance": "LOCK2-SYN", "criteria_met": True,
          "stage_2_record": {"stage": P4R.STAGE_2, "material": "MAT-SYN"}, "life_basis": "FULL_DURATION"}
    return s1, s2, s3


def tv_prop(rec, stage=None, value=900.0, material="MAT-SYN", sha=None):
    p = syn_prop(prop="T_validated_continuous", value=value, domain=["d1", "d2"])
    p.update({"material": material, "validation_stage": stage if stage is not None else rec.get("basis"),
              "validation_stage_record": rec, "validation_stage_record_id": "VSR-SYN",
              "validation_stage_record_sha256": sha if sha is not None else canon_sha(rec)})
    return p


T_OP = {"value_si": 800.0, "unit_si": "K", "evidence_class": "measured", "source": "SYN"}
POOL = [None, True, False, 0, 1, -1, 5.5, NAN, INF, "", " ", "x", "TBD", "PENDING-1", "NOT_SET", "OPEN",
        "OWNER_GIVEN", "DEFINED_FROM_EVIDENCE", "min", "max", "min_with_margin", "K", "degC", "CLOSED_BY_EVIDENCE",
        "UNRESOLVED", "measured", "assumed", "model-derived", "STAGE_1_COUPON_SCREENING",
        "STAGE_2_INTEGRATED_REPLACEABLE_COMPONENT_CONFIRMATION", "STAGE_3_QUALIFICATION_LIFE_EVIDENCE",
        "MELTING_POINT", [], ["d1"], ["d1", "d2", "d3"], ["d3"], [""], [1], "d1", {}, {"a": 1}, 900.0, 900, 850.0,
        50.0, 10.0, 12.0, "H-1", "REPLACEABLE_ANODE", "FULL_DURATION", "JUSTIFIED_ACCELERATED", "MAT-SYN",
        "MAT-OTHER", "T_validated_continuous", "P-SYN", "PASS"]


def gate(case, req, prop, tcs=None, top=None):
    return (case, "p4.evaluate_gate", {"req": req, "prop": prop, "thermal_closure_status": tcs,
                                       "operating_temperature": top})


def p4_calls(contract, seed):
    rec = committed_json(P4_REL)
    reqs = {r["id"]: r for r in rec["requirements"]}
    props = {p["id"]: p for p in rec["property_records"]}
    calls, per_cand = [], {}
    for k, g in enumerate(rec["gate_matrix"]):
        r = reqs[g["requirement"]]
        recs = [props[i] for i in g["property_records"]]
        adm = [x for x in recs if x["admissible_for_gate"] is True]
        prop = adm[0] if len(adm) == 1 else (recs[0] if recs else None)
        tcs = rec["fixed_statuses"][rec["applications"][g["application"]]["thermal_status_key"]]["status"] \
            if r["kind"] == "min_with_margin" else None
        calls.append(gate(f"R-P01-{k}", r, prop, tcs, None))
        per_cand.setdefault(f"{g['application']}|{g['candidate']}", []).append(g["outcome"])
    states = {}
    for key, outs in per_cand.items():
        calls.append((f"R-P02-state-{key}", "p4.candidate_screening_state", {"outcomes": outs}))
        states[key] = P4S.candidate_screening_state(outs)
    for app in rec["applications"]:
        calls.append((f"R-P02-final-{app}", "p4.final_material_status", {"states": states}))
    s1, s2, s3 = stage_records()
    mwm = syn_req("min_with_margin", prop="T_validated_continuous", value=50.0, domain=["d1"])
    walk = [
        gate("R-P03-min-sat", syn_req("min"), syn_prop(value=12.0)),
        gate("R-P03-min-vio", syn_req("min"), syn_prop(value=8.0)),
        gate("R-P03-max-sat", syn_req("max"), syn_prop(value=8.0)),
        gate("R-P03-max-vio", syn_req("max"), syn_prop(value=12.0)),
        gate("R-P03-ood", syn_req("min", domain=["d1", "d9"]), syn_prop()),
        gate("R-P03-unit", syn_req("min", unit="degC"), syn_prop()),
        gate("R-P03-noprop", syn_req("min"), None),
        gate("R-P03-req-tbd", syn_req("min", status="TBD"), syn_prop()),
        gate("R-P03-prop-inadm", syn_req("min"), syn_prop(adm=False)),
        gate("R-P03-propname", syn_req("min"), syn_prop(prop="P-OTHER")),
        gate("R-P03-mwm-s2-sat", mwm, tv_prop(s2), "CLOSED_BY_EVIDENCE", T_OP),
        gate("R-P03-mwm-s3-sat", mwm, tv_prop(s3), "CLOSED_BY_EVIDENCE", T_OP),
        gate("R-P03-mwm-s2-vio", mwm, tv_prop(s2), "CLOSED_BY_EVIDENCE", dict(T_OP, value_si=870.0)),
        gate("R-P03-mwm-unres", mwm, tv_prop(s2), "UNRESOLVED", T_OP),
        gate("R-P03-mwm-none", mwm, tv_prop(s2), None, T_OP),
        gate("R-P03-mwm-top-none", mwm, tv_prop(s2), "CLOSED_BY_EVIDENCE", None),
        gate("R-P03-mwm-top-list", mwm, tv_prop(s2), "CLOSED_BY_EVIDENCE", [800.0]),
        gate("R-P03-mwm-top-miss", mwm, tv_prop(s2), "CLOSED_BY_EVIDENCE", {"value_si": 800.0, "unit_si": "K"}),
        gate("R-P03-mwm-top-degC", mwm, tv_prop(s2), "CLOSED_BY_EVIDENCE", dict(T_OP, unit_si="degC")),
        gate("R-P03-mwm-top-zero", mwm, tv_prop(s2), "CLOSED_BY_EVIDENCE", dict(T_OP, value_si=0)),
        gate("R-P03-mwm-top-assumed", mwm, tv_prop(s2), "CLOSED_BY_EVIDENCE", dict(T_OP, evidence_class="assumed")),
        gate("R-P03-tv-s1", mwm, tv_prop(s1), "CLOSED_BY_EVIDENCE", T_OP),
        gate("R-P03-tv-s1-declared-s2", mwm, tv_prop(s1, stage=P4R.STAGE_2), "CLOSED_BY_EVIDENCE", T_OP),
        gate("R-P03-tv-noref", mwm, dict(tv_prop(s2), validation_stage_record_id=""), "CLOSED_BY_EVIDENCE", T_OP),
        gate("R-P03-tv-sha", mwm, tv_prop(s2, sha="0" * 64), "CLOSED_BY_EVIDENCE", T_OP),
        gate("R-P03-tv-stage-mismatch", mwm, tv_prop(s2, stage=P4R.STAGE_3), "CLOSED_BY_EVIDENCE", T_OP),
        gate("R-P03-tv-material", mwm, tv_prop(s2, material="MAT-OTHER"), "CLOSED_BY_EVIDENCE", T_OP),
        gate("R-P03-tv-value", mwm, tv_prop(s2, value=901.0), "CLOSED_BY_EVIDENCE", T_OP),
    ]
    refusals = {
        "nondict": "x", "nonval": dict(s2, basis="MELTING_POINT"), "unknown": dict(s2, basis="STAGE_X"),
        "noaccept": {k: v for k, v in s2.items() if k != "preregistered_acceptance"},
        "t0": dict(s2, T_limit_K=0.0), "tnan": dict(s2, T_limit_K=NAN), "ttrue": dict(s2, T_limit_K=True),
        "notmet": dict(s2, criteria_met=False), "s1cond": dict(s1, conditions={}),
        "s1short": dict(s1, exposure_duration_h=10.0), "s1condlist": dict(s1, conditions=["x"]),
        "s2nos1": dict(s2, stage_1_record=None), "s2mat": dict(s2, stage_1_record={"stage": P4R.STAGE_1, "material": "M2"}),
        "s2notdown": dict(s2, down_selected=False), "s2config": dict(s2, configuration="FIXED"),
        "s2env": dict(s2, environment={}), "s3nos2": dict(s3, stage_2_record={}),
        "s3accel": dict(s3, life_basis="JUSTIFIED_ACCELERATED"),
        "s3accelok": dict(s3, life_basis="JUSTIFIED_ACCELERATED", justification="SYN"),
    }
    for tag, r in refusals.items():
        stage = r.get("basis") if isinstance(r, dict) and r.get("basis") in (P4R.STAGE_2, P4R.STAGE_3) else P4R.STAGE_2
        p = tv_prop(r if isinstance(r, dict) else {}, stage=stage)
        p["validation_stage_record"] = r
        p["validation_stage_record_sha256"] = canon_sha(r)
        walk.append(gate(f"E-P07-{tag}", mwm, p, "CLOSED_BY_EVIDENCE", T_OP))
    calls += walk
    E = [gate("E-P01-req-list", [1], syn_prop()), gate("E-P01-prop-str", syn_req(), "x")]
    for f in P4S.REQUIREMENT_FIELDS:
        E.append(gate(f"E-P01-req-{f}", {k: v for k, v in syn_req().items() if k != f}, syn_prop()))
    for f in P4S.PROPERTY_FIELDS:
        E.append(gate(f"E-P01-prop-{f}", syn_req(), {k: v for k, v in syn_prop().items() if k != f}))
    for j, d in enumerate(["d1", [], ["", "x"], [1]]):
        E.append(gate(f"E-P02-req-{j}", syn_req(domain=None) | {"domain": d}, syn_prop()))
        E.append(gate(f"E-P02-prop-{j}", syn_req(), syn_prop() | {"domain": d}))
    for j, v in enumerate([True, NAN, INF, 12, "12"]):
        E.append(gate(f"E-P03-req-{j}", syn_req() | {"value": v}, syn_prop()))
        E.append(gate(f"E-P03-prop-{j}", syn_req(), syn_prop() | {"value_si": v}))
    E.append(gate("E-P04", mwm, tv_prop(s2), None, T_OP))
    E.append(("E-P06-empty", "p4.candidate_screening_state", {"outcomes": []}))
    E.append(("E-P06-pass", "p4.candidate_screening_state", {"outcomes": ["PASS"]}))
    calls += E
    n = contract["inputs"]["randomized_domain"]["generators"]
    bases = [lambda: (syn_req("min"), syn_prop(), None, None), lambda: (syn_req("max"), syn_prop(value=8.0), None, None),
             lambda: (copy.deepcopy(mwm), tv_prop(copy.deepcopy(s2)), "CLOSED_BY_EVIDENCE", dict(T_OP)),
             lambda: (copy.deepcopy(mwm), tv_prop(copy.deepcopy(s3)), "CLOSED_BY_EVIDENCE", dict(T_OP))]

    def mutate(r, obj):
        if not isinstance(obj, dict) or not obj:
            return
        k = r.choice(list(obj))
        if r.random() < 0.15:
            del obj[k]
        else:
            obj[k] = copy.deepcopy(r.choice(POOL))

    def gate_draw(r):
        req, prop, tcs, top = bases[r.randrange(len(bases))]()
        for _ in range(r.randint(0, 3)):
            t = r.randrange(7)
            if t == 0:
                mutate(r, req)
            elif t == 1:
                mutate(r, prop)
            elif t == 2:
                tcs = r.choice(POOL + ["CLOSED_BY_EVIDENCE"] * 5)
            elif t == 3:
                if r.random() < 0.2:
                    top = r.choice(POOL)
                else:
                    mutate(r, top)
            elif isinstance(prop, dict) and isinstance(prop.get("validation_stage_record"), dict):
                srec = prop["validation_stage_record"]
                target = srec
                for sub in ("stage_1_record", "stage_2_record", "conditions", "metrics", "environment"):
                    if sub in srec and isinstance(srec[sub], dict) and r.random() < 0.3:
                        target = srec[sub]
                mutate(r, target)
                if r.random() < 0.8:
                    prop["validation_stage_record_sha256"] = canon_sha(srec)
            else:
                mutate(r, prop)
        return {"req": req, "prop": prop, "thermal_closure_status": tcs, "operating_temperature": top}

    rng = random.Random(seed * 1000 + 0)
    for i in range(n["0 evaluate_gate"]):
        calls.append((f"R0-{i}", "p4.evaluate_gate", gate_draw(rng)))
    rng = random.Random(seed * 1000 + 1)
    for i in range(n["1 candidate_screening_state"]):
        outs = [rng.choice(P4S.GATE_OUTCOMES) if rng.random() > 0.02 else "PASS" for _ in range(rng.randint(0, 6))]
        calls.append((f"R1-{i}", "p4.candidate_screening_state", {"outcomes": outs}))
    rng = random.Random(seed * 1000 + 2)
    for i in range(n["2 final_material_status"]):
        calls.append((f"R2-{i}", "p4.final_material_status", {"states": rng.choice(POOL)}))
    rng = random.Random(seed * 1000 + 3)
    for i in range(n["3 requirement_evidenced"]):
        req = syn_req(rng.choice(["min", "max", "min_with_margin"]))
        for _ in range(rng.randint(0, 3)):
            mutate(rng, req)
        calls.append((f"R3-{i}", "p4.requirement_evidenced", {"req": req}))
    rng = random.Random(seed * 1000 + 4)
    for i in range(n["4 property_evidenced"]):
        prop = syn_prop()
        for _ in range(rng.randint(0, 3)):
            mutate(rng, prop)
        calls.append((f"R4-{i}", "p4.property_evidenced", {"prop": prop}))
    return calls


def p4_py(fn, a):
    if fn == "p4.evaluate_gate":
        return py_result(lambda: P4S.evaluate_gate(a["req"], a["prop"], thermal_closure_status=a["thermal_closure_status"],
                                                   operating_temperature=a["operating_temperature"]))
    if fn == "p4.candidate_screening_state":
        return py_result(lambda: P4S.candidate_screening_state(a["outcomes"]))
    if fn == "p4.final_material_status":
        return py_result(lambda: P4S.final_material_status(a["states"]))
    if fn == "p4.requirement_evidenced":
        return py_result(lambda: P4S.requirement_evidenced(a["req"]))
    if fn == "p4.property_evidenced":
        return py_result(lambda: P4S.property_evidenced(a["prop"]))
    raise KeyError(fn)


FORBIDDEN = ("PASS", "SELECTED", "WINNER", "QUALIFIED")


def has_forbidden(v):
    if isinstance(v, dict):
        return any(has_forbidden(x) for x in v.values())
    if isinstance(v, list):
        return any(has_forbidden(x) for x in v)
    return isinstance(v, str) and v.strip().upper() in FORBIDDEN


def p4_inv(rows):
    b1, b2, b3 = [], [], []
    for who in ("py", "rs"):
        for r, v in returned(rows, who):
            if has_forbidden(v):
                b1.append((who, r["case"]))
            if r["case"].startswith("R-P01-") and v[0] != "INCOMPLETE_EVIDENCE":
                b2.append((who, r["case"]))
            if r["fn"] == "p4.final_material_status" and v != "OPEN":
                b3.append((who, r["case"]))
    n01 = sum(1 for r in rows if r["case"].startswith("R-P01-"))
    return {"INV-P01": {"pass": not b1, "detail": f"no PASS / SELECTED / WINNER / QUALIFIED value; violations {b1[:10]}"},
            "INV-P02": {"pass": not b2 and n01 == 352, "detail": f"{n01} R-P01 cells, every outcome "
                                                                  f"INCOMPLETE_EVIDENCE; violations {b2[:10]}"},
            "INV-P03": {"pass": not b3, "detail": f"final_material_status OPEN; violations {b3[:10]}"}}, {}


# ============================================================================================== 6 indicators
from abep_sim.design import architecture_optimizer as AOPT  # noqa: E402

F3_REL = "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json"
ROTOR_REFUSAL = {"outcome": "RAISED", "class": "NotEvaluatedDependency",
                 "message": "life_material_indicators: the rotor indicator needs rotor_strength.qualify_rotor "
                            "(SC-WP-02), which is not admitted in Rust; NOT_EVALUATED"}
IND_WORK = {"dir": None, "n": 0}


def spec(rel, patch=None):
    return {"$committed": rel, "$patch": patch or []}


def indicators_calls(contract, seed):
    calls = [(f"R-I01-{j}", "indicators.life_material", {"design": d, "records": "REPO"})
             for j, d in enumerate([None, {}, {"u_tip_turbo_mps": None}, {"rpm": 1000.0}])]
    p4 = committed_json(P4_REL)
    E = [("E-I01-p4", "indicators.life_material", {"design": None, "records": {"p4": None, "f3": spec(F3_REL)}}),
         ("E-I01-f3", "indicators.life_material", {"design": None, "records": {"p4": spec(P4_REL), "f3": None}})]
    for k in ("final_material_status", "fixed_statuses", "gate_matrix"):
        E.append((f"E-I02-{k}", "indicators.life_material",
                  {"design": None, "records": {"p4": spec(P4_REL, [[[k], {"$delete": True}]]), "f3": spec(F3_REL)}}))
    first_fixed = list(p4["fixed_statuses"])[0]
    E.append(("E-I02-fixed-nostatus", "indicators.life_material",
              {"design": None, "records": {"p4": spec(P4_REL, [[["fixed_statuses", first_fixed], {"note": "x"}]]),
                                           "f3": spec(F3_REL)}}))
    E.append(("E-I02-f3-noparams", "indicators.life_material",
              {"design": None, "records": {"p4": spec(P4_REL), "f3": spec(F3_REL, [[["parameters"], {"$delete": True}]])}}))
    E.append(("E-I02-f3-param-noid", "indicators.life_material",
              {"design": None, "records": {"p4": spec(P4_REL), "f3": spec(F3_REL, [[["parameters", 0, "id"],
                                                                                     {"$delete": True}]])}}))
    E.append(("E-I03-status", "indicators.life_material",
              {"design": None, "records": {"p4": spec(P4_REL, [[["gate_matrix", 0, "outcome"], {"$delete": True}],
                                                               [["gate_matrix", 0, "status"], "INCOMPLETE_EVIDENCE"],
                                                               [["gate_matrix", 1, "outcome"], "OUT_OF_DOMAIN"]]),
                                           "f3": spec(F3_REL)}}))
    E.append(("E-I03-empty", "indicators.life_material",
              {"design": {}, "records": {"p4": spec(P4_REL, [[["gate_matrix"], []]]), "f3": spec(F3_REL)}}))
    E.append(("E-I04a", "indicators.life_material", {"design": {"u_tip_turbo_mps": 400.0}, "records": "REPO"}))
    E.append(("E-I04b", "indicators.life_material", {"design": {"u_tip_turbo_mps": 400.0, "rpm": 60000.0},
                                                      "records": "REPO"}))
    calls += E
    n = contract["inputs"]["randomized_domain"]["generators"]
    rng = random.Random(seed * 1000 + 0)
    cells = len(p4["gate_matrix"])
    fixed = list(p4["fixed_statuses"])
    for i in range(n["0 life_material_indicators"]):
        patch = []
        deleted = 0
        for _ in range(rng.randint(1, 3)):
            t = rng.randrange(6)
            c = rng.randrange(cells - deleted)
            if t == 0:
                patch.append([["gate_matrix", c, "outcome"], {"$delete": True}])
                patch.append([["gate_matrix", c, "status"], rng.choice(P4S.GATE_OUTCOMES)])
            elif t == 1:
                patch.append([["gate_matrix", c, "outcome"], rng.choice(P4S.GATE_OUTCOMES)])
            elif t == 2:
                patch.append([["gate_matrix", c], {"$delete": True}])
                deleted += 1
            elif t == 3:
                patch.append([["fixed_statuses", f"SYN_{i}"], {"status": rng.choice(["OPEN", "UNRESOLVED"])}])
            elif t == 4:
                patch.append([["fixed_statuses", rng.choice(fixed)], {"$delete": True}])
            else:
                patch.append([["final_material_status"], rng.choice(POOL)])
            if patch[-1][0][0] == "fixed_statuses" and patch[-1][1] == {"$delete": True}:
                fixed = [x for x in fixed if x != patch[-1][0][1]] or list(p4["fixed_statuses"])
        calls.append((f"R0-{i}", "indicators.life_material",
                      {"design": rng.choice([None, {}]), "records": {"p4": spec(P4_REL, patch), "f3": spec(F3_REL)}}))
        fixed = list(p4["fixed_statuses"])
    return calls


def indicators_py(fn, a):
    if a["records"] == "REPO":
        return py_result(lambda: AOPT.life_material_indicators(a["design"], ROOT))
    IND_WORK["n"] += 1
    d = Path(IND_WORK["dir"]) / f"repo{IND_WORK['n']}"
    for key, rel in (("p4", P4_REL), ("f3", F3_REL)):
        s = a["records"][key]
        if s is not None:
            v = apply_patch(committed_json(s["$committed"]), s["$patch"])
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_text(json.dumps(v), encoding="utf-8")
    d.mkdir(parents=True, exist_ok=True)
    return py_result(lambda: AOPT.life_material_indicators(a["design"], d))


def indicators_inv(rows):
    b1, b2 = [], []
    for who in ("py", "rs"):
        for r, v in returned(rows, who):
            if r["case"].startswith("E-I04"):
                continue
            wall = [x for x in v["indicators"] if x["indicator"] == "wall erosion / firing life > 15,000 h (RVM-12)"]
            if v["status"] != "NOT_EVALUATED" or len(wall) != 1 or wall[0]["value"] is not None or \
                    wall[0]["status"] != "NOT_EVALUATED":
                b1.append((who, r["case"]))
            if any(x.get("status") == "EVALUATED" for x in v["indicators"]):
                b2.append((who, r["case"]))
    return {"INV-I01": {"pass": not b1, "detail": f"status NOT_EVALUATED, Hall wall-erosion life indicator None / "
                                                  f"NOT_EVALUATED; violations {b1[:10]}"},
            "INV-I02": {"pass": not b2, "detail": f"no indicator EVALUATED; violations {b2[:10]}"}}, {}


def indicators_divergence(case, fn, args):
    if case.startswith("E-I04"):
        return "DIV-I01", ROTOR_REFUSAL
    return None, None


# ============================================================================================== 7 hall wall
from abep_sim import thermal_life as TL  # noqa: E402
from abep_sim import hall_ensemble as HE  # noqa: E402

FIXTURE = {"members": [{"ensemble_member_id": "adm-fixture-01"}],
           "screening_candidates": [{"ensemble_member_id": "sgb-screen-01"}]}
STMTS = {"uncertainty": "test fixture: unquantified", "applicability_domain": "test fixture only",
         "validation_status": "test fixture, not validated"}


def hw_base(member="adm-fixture-01", ensemble=None):
    pinned = TL._pinned_hall_commit()
    pt = {"trustworthy": True, "wall_life_trustworthy": True, "discharge_power_W": 900.0, "discharge_current_A": 3.0,
          "wall_ion_flux_m2s": 1e21, "wall_ion_energy_eV": 40.0, "hallthruster_commit": pinned}
    meta = {"schema": "hall_map_schema_v1", "ensemble_member_id": member, "hallthruster_commit": pinned,
            "ion_wall_losses": True}
    return dict({"point": pt, "member_id": member, "evidence_level": 6, "map_meta": meta, "schema": None,
                 "ensemble": ensemble if ensemble is not None else copy.deepcopy(FIXTURE)}, **STMTS)


def hw_calls(contract, seed):
    b = hw_base()
    pt, meta = b["point"], b["map_meta"]
    R = [("R-W01-valid", b),
         ("R-W01-wlt", dict(b, point=dict(pt, wall_life_trustworthy=False))),
         ("R-W01-trust", dict(b, point=dict(pt, trustworthy=False))),
         ("R-W01-commit", dict(b, point=dict(pt, hallthruster_commit="bfb3019"))),
         ("R-W01-empty-id", dict(b, member_id="")),
         ("R-W01-screen", dict(b, member_id="sgb-screen-01")),
         ("R-W01-unknown", dict(b, member_id="member-x")),
         ("R-W01-level0", dict(b, evidence_level=0)),
         ("R-W01-meta-id", dict(b, map_meta=dict(meta, ensemble_member_id="adm-other"))),
         ("R-W01-meta-commit", dict(b, map_meta=dict(meta, hallthruster_commit="x"))),
         ("R-W01-meta-iwl", dict(b, map_meta=dict(meta, ion_wall_losses=False))),
         ("R-W01-unc", dict(b, uncertainty=" "))]
    real_ids = sorted(HE.screening_ids(HE.load_ensemble())) + ["unknown-member"]
    for sid in real_ids:
        R.append((f"R-W02-{sid}", hw_base(member=sid, ensemble="REAL")))
    E = []
    for j, lv in enumerate([8, True, 6.0, None, "6"]):
        E.append((f"E-W01-{j}", dict(b, evidence_level=lv)))
    for k in ("trustworthy", "wall_life_trustworthy"):
        for j, v in enumerate([1, None]):
            E.append((f"E-W02-{k}-{j}", dict(b, point=dict(pt, **{k: v}))))
        E.append((f"E-W02-{k}-absent", dict(b, point={x: y for x, y in pt.items() if x != k})))
    E.append(("E-W02-commit-absent", dict(b, point={x: y for x, y in pt.items() if x != "hallthruster_commit"})))
    E.append(("E-W03-meta-list", dict(b, map_meta=[1])))
    for j, v in enumerate(["", " ", None, 5]):
        for k in ("uncertainty", "applicability_domain", "validation_status"):
            E.append((f"E-W04-{k}-{j}", dict(b, **{k: v})))
    for f in ("discharge_power_W", "wall_ion_flux_m2s"):
        E.append((f"E-W05-{f}-absent", dict(b, point={x: y for x, y in pt.items() if x != f})))
        for j, v in enumerate([True, "1e21", "abc", None, [1], " 2.5 "]):
            E.append((f"E-W05-{f}-{j}", dict(b, point=dict(pt, **{f: v}))))
    E.append(("E-W06-empty", dict(b, schema={})))
    E.append(("E-W06-nounit", dict(b, schema={"fields": {"discharge_power_W": {"unit": "W"}}})))
    calls = [(c, "hallwall.hallmap_wall_inputs", a) for c, a in R + E]
    n = contract["inputs"]["randomized_domain"]["generators"]
    pools = {"evidence_level": [1, 7, 0, 8, True, 6.0, None, "6"], "member_id": ["", "sgb-screen-01", "member-x",
                                                                                 "adm-fixture-01"],
             "stmt": ["", " ", None, 5, "ok", "\t"],
             "flag": [True, False, 1, None], "commit": ["bfb3019", None, "x"], "meta_iwl": [True, False, None, 1],
             "value": [True, "1e21", "abc", None, [1], "inf", "nan", 0, -1.0]}

    def draw(r):
        a = hw_base()
        a["point"]["discharge_power_W"] = loguniform(r, 1, 3000)
        a["point"]["discharge_current_A"] = loguniform(r, 0.1, 30)
        a["point"]["wall_ion_flux_m2s"] = loguniform(r, 1e17, 1e23)
        a["point"]["wall_ion_energy_eV"] = loguniform(r, 1, 300)
        for _ in range(r.randint(0, 3)):
            t = r.randrange(8)
            if t == 0:
                a["evidence_level"] = r.choice(pools["evidence_level"])
            elif t == 1:
                a["member_id"] = r.choice(pools["member_id"])
            elif t == 2:
                a[r.choice(["uncertainty", "applicability_domain", "validation_status"])] = r.choice(pools["stmt"])
            elif t == 3:
                a["point"][r.choice(["trustworthy", "wall_life_trustworthy"])] = r.choice(pools["flag"])
            elif t == 4:
                a["point"]["hallthruster_commit"] = r.choice(pools["commit"])
            elif t == 5:
                a["map_meta"][r.choice(["ion_wall_losses", "ensemble_member_id", "hallthruster_commit"])] = \
                    r.choice(pools["meta_iwl"] + pools["member_id"])
            elif t == 6:
                f = r.choice(list(TL.HALLMAP_FIELDS_USED))
                if r.random() < 0.3:
                    del a["point"][f]
                else:
                    a["point"][f] = r.choice(pools["value"])
            else:
                a["schema"] = r.choice([None, {}])
        return a
    rng = random.Random(seed * 1000 + 0)
    for i in range(n["0 fixture ensemble"]):
        calls.append((f"R0-{i}", "hallwall.hallmap_wall_inputs", draw(rng)))
    rng = random.Random(seed * 1000 + 1)
    for i in range(n["1 REAL ensemble"]):
        mid = rng.choice(real_ids + ["adm-fixture-01", f"rand-{rng.randint(0, 999)}"])
        a = hw_base(member=mid, ensemble="REAL")
        calls.append((f"R1-{i}", "hallwall.hallmap_wall_inputs", a))
    return calls


def hw_py(fn, a):
    saved = HE.load_ensemble
    if a["ensemble"] != "REAL":
        fixture = a["ensemble"]
        HE.load_ensemble = lambda *x, **k: fixture
    try:
        return py_result(lambda: TL.hallmap_wall_inputs(
            a["point"], a["member_id"], a["evidence_level"], map_meta=a["map_meta"], uncertainty=a["uncertainty"],
            applicability_domain=a["applicability_domain"], validation_status=a["validation_status"],
            schema=a["schema"]))
    finally:
        HE.load_ensemble = saved


def hw_inv(rows):
    b1, b2 = [], []
    n_real = 0
    for r in rows:
        if r["args"]["ensemble"] == "REAL":
            n_real += 1
            for who in ("py", "rs"):
                if r[who]["outcome"] != "RAISED" or r[who]["class"] != "ValueError":
                    b1.append((who, r["case"]))
    for who in ("py", "rs"):
        for r, v in returned(rows, who):
            for f, rec in v.items():
                ok = rec["quantity_type"] == "model-derived"
                if f in ("wall_ion_flux_m2s", "wall_ion_energy_eV"):
                    p = rec.get("wall_flux_provenance", {})
                    ok &= p.get("trustworthy") is True and p.get("wall_life_trustworthy") is True
                if not ok:
                    b2.append((who, r["case"], f))
    return {"INV-W01": {"pass": not b1 and n_real > 0,
                        "detail": f"{n_real} REAL-ensemble calls (credible set EMPTY): every call RAISED ValueError in "
                                  f"both, no Hall wall-flux input formed, Hall-erosion life NOT_EVALUATED; violations "
                                  f"{b1[:10]}"},
            "INV-W02": {"pass": not b2, "detail": f"returned records model-derived with trusted wall provenance; "
                                                  f"violations {b2[:10]}"}}, {}


# ============================================================================================== registry
def ledger(cid, scope, impl):
    return [{"component": cid, "status": "ADMITTED", "parity": "PARITY_PASS", "scope": scope,
             "authoritative_implementation": impl}]


CONTRACTS = {
    "C-ABEP_SIM_AOCHEM_PY": dict(
        calls=aochem_calls, py=aochem_py, inv=aochem_inv, msg=set(), div=None,
        perf=lambda rows: [("PERF-A01", "aochem.material_report", {"atm": {"rho": 2.5e-10, "fO": 0.6, "fN2": 0.35,
                                                                         "fO2": 0.05, "V": 7784.0},
                                                                 "hours": 26280.0}, 5000)],
        ledger=ledger("C-ABEP_SIM_AOCHEM_PY", "named function subset A0..A6 (every function, AOParams and the two "
                      "numeric tables); MATERIAL_CLASS (descriptive text, no consumer) stays Python reference text, "
                      "not ported", "rust: crates/abep-subsystems (abep_subsystems::materials::aochem)")),
    "C-ABEP_SIM_MATERIALS_PY": dict(
        calls=materials_calls, py=materials_py, inv=materials_inv, msg=set(), div=None,
        perf=lambda rows: [("PERF-M01", "materials.gamma_O", {"material": {"name": "SS316"}, "T_K": 350.0}, 20000)],
        ledger=ledger("C-ABEP_SIM_MATERIALS_PY", "named function subset M0..M5 (Material record and methods, DB rows, "
                      "surface_ageing_alpha); set_property / table() stay Python reference; inventory WP SC-WP-12 "
                      "(cross-WP registration by SC-WP-08, to reconcile)",
                      "rust: crates/abep-subsystems (abep_subsystems::materials::db)")),
    "C-DOCS_EVIDENCE_SPUTTER_YIELDS_V1-YIELD_KERNELS": dict(
        calls=sputter_calls, py=sputter_py, inv=sputter_inv, msg={"ValueError"}, div=None,
        perf=lambda rows: [("PERF-S01", "sputter.yamamura_tawara",
                            [r for r in rows if r["case"] == "R-S02-yt-worked"][0]["args"], 20000)],
        ledger=ledger("C-DOCS_EVIDENCE_SPUTTER_YIELDS_V1", "partial admission: kernels yamamura_tawara and apid_fit "
                      "(S1 / S2); the register builder stays Python reference",
                      "rust: crates/abep-subsystems (abep_subsystems::materials::sputter)")),
    "C-DOCS_EXPERIMENTS_LIFETIME_AO-AO_REGISTER_KERNELS": dict(
        calls=aoreg_calls, py=aoreg_py, inv=aoreg_inv, msg={"RuntimeError"}, div=None,
        perf=lambda rows: [("PERF-L01", "aoreg.environment", {"altitudes": [180, 200, 230],
                                                             "csv_sha256": AR.ATMOSPHERE_CSV_SHA256}, 20)],
        ledger=ledger("C-DOCS_EXPERIMENTS_LIFETIME_AO", "partial admission: kernels compute_ao_environment and "
                      "compute_wall_sputter_index (L1 / L2); the register builder stays Python reference",
                      "rust: crates/abep-subsystems (abep_subsystems::life::ao_register)")),
    "C-DOCS_EXPERIMENTS_HALL_ICP_P4_ANODE_MATERIALS-SCREENING_KERNELS": dict(
        calls=p4_calls, py=p4_py, inv=p4_inv, msg={"ScreeningError"}, div=None,
        perf=lambda rows: [("PERF-P01", "p4.evaluate_gate", [r for r in rows if r["case"] == "R-P01-0"][0]["args"],
                            352 * 50)],
        ledger=ledger("C-DOCS_EXPERIMENTS_HALL_ICP_P4_ANODE_MATERIALS", "partial admission: evaluate_gate (with "
                      "p4_a9_16_rules.validation_stage_record), candidate_screening_state, final_material_status, "
                      "requirement_evidenced, property_evidenced (P1..P5); the builder and the other rule functions "
                      "stay Python reference", "rust: crates/abep-subsystems (abep_subsystems::life::p4)")),
    "C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-LIFE_MATERIAL_KERNEL": dict(
        calls=indicators_calls, py=indicators_py, inv=indicators_inv, msg={"NotEvaluatedDependency"},
        div=indicators_divergence,
        perf=lambda rows: [("PERF-I01", "indicators.life_material", {"design": None, "records": "REPO"}, 2000)],
        ledger=ledger("C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY", "partial admission: life_material_indicators "
                      "without a rotor tip speed (I1); the rotor branch is NOT_EVALUATED in Rust (DIV-I01) until "
                      "rotor_strength (SC-WP-02) is admitted",
                      "rust: crates/abep-subsystems (abep_subsystems::life::indicators)")),
    "C-ABEP_SIM_THERMAL_LIFE_PY-HALLMAP_WALL_INPUTS": dict(
        calls=hw_calls, py=hw_py, inv=hw_inv, msg={"ValueError"}, div=None,
        perf=lambda rows: [("PERF-W01", "hallwall.hallmap_wall_inputs", hw_base(), 5000)],
        ledger=ledger("C-ABEP_SIM_THERMAL_LIFE_PY", "partial admission: hallmap_wall_inputs (W1); the other "
                      "thermal_life functions are SC-WP-06's",
                      "rust: crates/abep-subsystems (abep_subsystems::life::hall_wall)")),
}


# ============================================================================================== campaign
def cargo_build() -> Path:
    subprocess.run(["cargo", "build", "--release", "--locked", "-p", "abep-subsystems", "--example", "life_eval"],
                   cwd=ROOT, check=True, env=CARGO_ENV, capture_output=True)
    return ROOT / "target" / "release" / "examples" / "life_eval"


def rust_eval(binary: Path, calls: list, work: Path, tag: str) -> tuple[list, bytes]:
    p = work / f"calls_{tag}.json"
    p.write_text(json.dumps(calls, ensure_ascii=True), encoding="utf-8")
    r = subprocess.run([str(binary), str(p)], capture_output=True, check=True, cwd=ROOT)
    return json.loads(r.stdout), r.stdout


def git_state() -> dict:
    return {"git_head": PC.git("rev-parse", "HEAD"), "git_dirty": PC.git("status", "--porcelain") != ""}


def build_provenance() -> dict:
    src = PC.source_sha256(PROVENANCE_SOURCES)
    digest = hashlib.sha256(json.dumps(src, sort_keys=True).encode()).hexdigest()
    rustc = subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip()
    cargo = subprocess.run(["cargo", "--version"], capture_output=True, text=True).stdout.strip()
    return {"rustc": rustc, "cargo": cargo,
            "profile": "release (cargo build --release --locked -p abep-subsystems --example life_eval)",
            "cargo_lock_sha256": PC.sha_file(ROOT / "Cargo.lock"), "source_sha256": src, "source_sha256_digest": digest}


def write_reference_outputs(cdir: Path, files: dict, python_commit: str, git_head: str) -> dict:
    out = cdir / "reference_outputs"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"captured_at_python_commit": python_commit, "scoring_git_head": git_head,
                "format": "gzip (mtime 0) of json.dumps(obj, indent=None, ensure_ascii=True, allow_nan=True)",
                "files": {}}
    for name, obj in files.items():
        raw = json.dumps(obj, ensure_ascii=True).encode("utf-8")
        data = gzip.compress(raw, mtime=0)
        (out / name).write_bytes(data)
        manifest["files"][name] = {"sha256": PC.sha_bytes(data), "uncompressed_sha256": PC.sha_bytes(raw)}
    mp = out / "MANIFEST.json"
    mp.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return {"path": str(out.relative_to(ROOT)), "manifest_sha256": PC.sha_file(mp), "files": manifest["files"]}


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def md_report(r: dict) -> str:
    lines = [f"# Parity report {r['contract']['id']}", "",
             f"Generated from `parity_report_v1.json`. Verdict: **{r['verdict']}** (parity {r['parity']}).", "",
             f"* Contract: `{r['contract']['path']}` (sha256 `{r['contract']['sha256']}`)",
             f"* Python reference commit `{r['python_commit']}`; reference files unchanged at scoring: "
             f"{r['reference_unchanged_at_scoring']}",
             f"* Rust commit `{r['rust_commit']}` (tree dirty: {r['scoring_execution']['git_dirty']}), "
             f"{r['build_provenance']['rustc']}",
             f"* Scoring seed {r['scoring_execution']['master_seed']}; harness `{r['harness']['path']}` sha256 "
             f"`{r['harness']['sha256']}`", "", "## Calls", "", "| item | value |", "|---|---|"]
    for k, v in r["per_test"]["counts"].items():
        lines.append(f"| {k} | {v} |")
    lines += ["", f"Mismatches: {r['per_test']['mismatches']}. Largest float distance: "
                  f"{r['per_test']['max_ulp_distance']:.3g} ulp over {r['per_test']['floats_compared']} floats.", "",
              "## Invariants", "", "| id | pass | detail |", "|---|---|---|"]
    for k, v in r["invariants"].items():
        lines.append(f"| {k} | {v['pass']} | {v['detail']} |")
    lines += ["", "## Conservation", ""]
    if r["conservation"]:
        lines += ["| id | pass | detail |", "|---|---|---|"]
        for k, v in r["conservation"].items():
            lines.append(f"| {k} | {v['pass']} | {v['detail']} |")
    else:
        lines.append("Not applicable (contract conservation_checks.applicable false).")
    lines += ["", "## Domain and error parity", "", "| class | Python RAISED calls |", "|---|---|"]
    for k, v in r["domain_and_error"]["python_raised_by_class"].items():
        lines.append(f"| {k} | {v} |")
    if r["domain_and_error"]["divergences_observed"]:
        lines += ["", "Registered divergences (scored against the registered Rust outcome):", ""]
        for k, v in r["domain_and_error"]["divergences_observed"].items():
            lines.append(f"* {k}: {v}")
    lines += ["", "## Performance (reported, not a decision criterion)", "", "| workload | Python s | Rust s | note |",
              "|---|---|---|---|"]
    for k, v in r["performance"].items():
        lines.append(f"| {k} | {v['python_s']:.4g} | {v['rust_s']:.4g} | {v.get('note', '')} |")
    if r.get("findings"):
        lines += ["", "## Findings", ""] + [f"* {f}" for f in r["findings"]]
    lines += ["", "## Ledger update requested", "", "```json", json.dumps(r["ledger_update_requested"], indent=1),
              "```", "", "## What this is not", ""] + [f"* {w}" for w in r["what_this_is_not"]]
    if r["per_test"]["failures"]:
        lines += ["", "## Failures (first 40)", ""]
        for f in r["per_test"]["failures"][:40]:
            lines.append(f"* `{json.dumps(f, ensure_ascii=False)[:600]}`")
    return "\n".join(lines) + "\n"


def run(cid: str, mode: str, work: Path) -> dict:
    spec_ = CONTRACTS[cid]
    contract_path = ROOT / "docs/rust_migration/contracts" / cid / "parity_prereg_v1.json"
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes)
    seeds = contract["campaign_seeds"]
    seed = seeds["scoring_master_seed"] if mode == "score" else seeds["development_master_seed"]
    t0 = time.time()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    IND_WORK["dir"] = str(work / "repos")
    AR_WORK["dir"] = str(work / "lane32_db")
    changed = [f["path"] for f in contract["reference_implementation"]["files"]
               if PC.sha_file(ROOT / f["path"]) != f["sha256_at_registration"]]
    if changed:
        return {"verdict": "REFUSED_REFERENCE_CHANGED", "changed": changed}
    pinned_bad = [p for p, h in contract.get("pinned_inputs_sha256", {}).items() if PC.sha_file(ROOT / p) != h]
    gs = git_state()
    binary = cargo_build()
    calls = spec_["calls"](contract, seed)
    rows = [{"case": c, "fn": f, "args": a, "py": spec_["py"](f, copy.deepcopy(a))} for c, f, a in calls]
    rcalls = [{"fn": r["fn"], "args": r["args"]} for r in rows]
    rs, rbytes = rust_eval(binary, rcalls, work, "a")
    _, rbytes2 = rust_eval(binary, rcalls, work, "b")
    failures, max_ulp, floats, raised, divs = [], 0.0, 0, {}, {}
    for r, rr in zip(rows, rs):
        r["rs"] = rr
        exp = r["py"]
        if spec_["div"] is not None:
            did, registered = spec_["div"](r["case"], r["fn"], r["args"])
            if did:
                exp = registered
                divs.setdefault(did, []).append({"case": r["case"], "python_outcome": r["py"]["outcome"],
                                                 "rust_outcome": rr["outcome"], "rust_class": rr.get("class")})
        d, st = compare(exp, rr, spec_["msg"])
        max_ulp, floats = max(max_ulp, st["max_ulp"]), floats + st["floats"]
        if d:
            failures.append({"case": r["case"], "fn": r["fn"], "diff": d[:5]})
        if r["py"]["outcome"] == "RAISED":
            raised[r["py"]["class"]] = raised.get(r["py"]["class"], 0) + 1
    invariants = {"INV-DET": {"pass": rbytes == rbytes2, "detail": "Rust outputs of two separate processes "
                                                                   "byte-identical"}}
    inv, cons = spec_["inv"](rows)
    invariants.update(inv)
    perf = {}
    for pid, fn, a, n in spec_["perf"](rows):
        py_s = PC.timed(lambda: [spec_["py"](fn, copy.deepcopy(a)) for _ in range(n)])
        tt = []
        for _ in range(3):
            res, _b = rust_eval(binary, [{"fn": fn, "args": a, "repeat": n}], work, "perf")
            tt.append(res[0]["elapsed_s"])
        rust_s = sorted(tt)[1]
        perf[pid] = {"python_s": py_s, "rust_s": rust_s, "speedup": py_s / rust_s if rust_s else None,
                     "note": f"{n} evaluations; Rust timed inside life_eval (no process start)"}
    ok = not failures and all(v["pass"] for v in invariants.values()) and all(v["pass"] for v in cons.values()) \
        and not pinned_bad
    verdict = "ADMITTED" if ok else ("INPUT_MISMATCH" if pinned_bad else "NOT_ADMITTED")
    rnd = re.compile(r"^R\d+-")
    counts = {"calls_total": len(rows), "registered_calls": sum(1 for r in rows if not rnd.match(r["case"])),
              "randomized_calls": sum(1 for r in rows if rnd.match(r["case"])),
              "python_RETURNED": sum(r["py"]["outcome"] == "RETURNED" for r in rows),
              "python_RAISED": sum(r["py"]["outcome"] == "RAISED" for r in rows)}
    for fn in sorted({r["fn"] for r in rows}):
        counts[f"calls {fn}"] = sum(r["fn"] == fn for r in rows)
    summary = {"verdict": verdict, "mismatches": len(failures), "counts": counts, "max_ulp": max_ulp,
               "invariants": {k: v["pass"] for k, v in invariants.items()},
               "conservation": {k: v["pass"] for k, v in cons.items()}, "pinned_bad": pinned_bad,
               "wall_s": round(time.time() - t0, 1), "failures": failures[:30]}
    if mode != "score":
        return summary
    cdir = contract_path.parent
    ledger_req = copy.deepcopy(spec_["ledger"])
    if verdict != "ADMITTED":
        for x in ledger_req:
            x["status"], x["parity"] = "NOT_ADMITTED", "PARITY_FAIL"
    cap = write_reference_outputs(cdir, {
        "calls_v1.json.gz": [{"case": r["case"], "fn": r["fn"], "args": r["args"]} for r in rows],
        "python_results_v1.json.gz": [{"case": r["case"], "fn": r["fn"], "result": r["py"]} for r in rows],
    }, contract["reference_implementation"]["python_commit"], gs["git_head"])
    bp = build_provenance()
    rep_path = cdir / "parity_report_v1.json"
    prev = json.loads(rep_path.read_text())["campaign_history"] if rep_path.exists() else []
    hist = prev + [{"utc": utc(), "git_head": gs["git_head"], "git_dirty": gs["git_dirty"], "master_seed": seed,
                    "contract_sha256": PC.sha_bytes(contract_bytes), "source_sha256_digest": bp["source_sha256_digest"],
                    "verdict": verdict, "wall_s": summary["wall_s"]}]
    env = PC.environment()
    env["requirements_lock_sha256"] = PC.sha_file(ROOT / "requirements-lock.txt")
    harness = Path(__file__).resolve()
    report = {
        "report_schema": "abep_rust_parity_report_v3_1", "id": "PARITY-REPORT-" + cid + "-V1", "lane": "SC-WP-08",
        "contract": {"path": str(contract_path.relative_to(ROOT)), "sha256": PC.sha_bytes(contract_bytes),
                     "id": contract["id"]},
        "verdict": verdict, "parity": "PARITY_PASS" if verdict == "ADMITTED" else "PARITY_FAIL",
        "verdict_rule": contract["decision_rules"]["verdict"],
        "python_commit": contract["reference_implementation"]["python_commit"],
        "reference_sha256": {f["path"]: f["sha256_at_registration"] for f in contract["reference_implementation"]["files"]},
        "reference_unchanged_at_scoring": True, "pinned_inputs_verified": not pinned_bad,
        "rust_commit": gs["git_head"], "build_provenance": bp, "environment": env,
        "harness": {"path": str(harness.relative_to(ROOT)), "sha256": PC.sha_file(harness),
                    "common": {"scripts/rust_migration/parity_common.py":
                               PC.sha_file(ROOT / "scripts/rust_migration/parity_common.py")},
                    "transport_note": "mutated committed records travel as {$committed, $patch}; both sides apply the "
                                      "same patch list (module docstring)"},
        "scoring_execution": {"utc": utc(), "git_dirty": gs["git_dirty"], "master_seed": seed,
                              "rust_calls_sha256": PC.sha_bytes(json.dumps(rcalls, ensure_ascii=True).encode())},
        "per_test": {"counts": counts, "mismatches": len(failures), "failures": failures, "max_ulp_distance": max_ulp,
                     "floats_compared": floats,
                     "tolerance": "EXACT_VALUE structure / strings / ints / statuses; ULP_BOUNDED floats (4 ulp or "
                                  "1e-12 relative); messages for " + ", ".join(sorted(spec_["msg"]) or ["none"])},
        "aggregates": "NOT_APPLICABLE", "invariants": invariants, "conservation": cons,
        "domain_and_error": {"python_raised_by_class": raised,
                             "divergences_observed": {k: {"calls": len(v), "rows": v[:5]} for k, v in divs.items()},
                             "message_classes_scored": sorted(spec_["msg"])},
        "schema": {"pass": not failures, "detail": "field names, order and types compared on every returned value"},
        "performance": perf, "captured_reference_outputs": cap, "campaign_history": hist,
        "development_runs": f"development seed {seeds['development_master_seed']} runs were not scored or reported "
                            "(contract development_rule)",
        "findings": [], "ledger_update_requested": ledger_req,
        "meaning_of_ADMITTED": contract["decision_rules"]["meaning_of_ADMITTED"],
        "what_this_is_not": contract["what_this_is_not"],
    }
    PC.write_report(rep_path, report, md_report(report))
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--contract", choices=sorted(CONTRACTS), required=True)
    ap.add_argument("--mode", choices=["development", "score"], required=True)
    ap.add_argument("--work", required=True)
    a = ap.parse_args(argv)
    if a.mode == "score" and git_state()["git_dirty"]:
        print("refused: score mode needs a clean, committed tree")
        return 2
    summary = run(a.contract, a.mode, Path(a.work))
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str)[:8000])
    return 0 if summary["verdict"] == "ADMITTED" else 1


if __name__ == "__main__":
    sys.exit(main())
