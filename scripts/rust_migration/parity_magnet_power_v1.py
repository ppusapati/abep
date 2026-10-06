"""Parity campaign of contract C-ABEP_SIM_MAGNET_POWER_PY v1 (SC-WP-05 magnet load model).

Python reference abep_sim/magnet_power.py (without ecr_resonance_field_T) vs the Rust example `power_eval`
(abep_subsystems::power::magnet) on the preregistered calls.

  python scripts/rust_migration/parity_magnet_power_v1.py --mode development --work DIR
  python scripts/rust_migration/parity_magnet_power_v1.py --mode score --work DIR
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_power_common as P  # noqa: E402

ROOT = P.ROOT
sys.path.insert(0, str(ROOT))
from abep_sim import magnet_power as MP  # noqa: E402

CID = "C-ABEP_SIM_MAGNET_POWER_PY"
CONTRACT = ROOT / "docs/rust_migration/contracts" / CID / "parity_prereg_v1.json"
ARGS = {
    "resistance_factor": ["material", "T_C"],
    "wire_resistance_ohm": ["length_m", "area_m2", "material", "T_C"],
    "awg_diameter_m": ["gauge"],
    "ampere_turns": ["B_gap_T", "gap_length_m", "gap_area_m2", "core_segments", "leakage_factor"],
    "coil_power_continuous_W": ["NI_A", "window_area_m2", "fill_factor", "mean_turn_length_m", "material", "T_C"],
    "coil_design": ["NI_A", "window_area_m2", "fill_factor", "mean_turn_length_m", "wire_diameter_m", "material",
                    "T_C"],
    "electromagnet": ["B_gap_T", "gap_length_m", "gap_area_m2", "core_segments", "leakage_factor", "window_area_m2",
                      "fill_factor", "mean_turn_length_m", "wire_diameter_m", "material", "T_C"],
    "remanence_at_T": ["B_r_ref_T", "alpha_Br_per_K", "T_ref_C", "T_C"],
    "permanent_magnet": ["B_gap_T", "gap_length_m", "gap_area_m2", "core_segments", "leakage_factor",
                         "magnet_area_m2", "B_r_T", "mu_rec", "H_knee_A_per_m", "magnet_density_kg_m3"],
}


def decode(v):
    v = P.decode(v)
    if isinstance(v, dict) and set(v) == {"expr"}:
        return float(eval(v["expr"], {"math": math}))  # noqa: S307 - registered constant expression
    if isinstance(v, dict) and "raw" not in v and "fields" not in v and "segment" not in v and "ref" not in v:
        return {k: decode(x) for k, x in v.items()}
    return v


def material(spec):
    if "ref" in spec:
        return MP.ANNEALED_COPPER_IACS
    if "fields" in spec:
        return MP.ConductorMaterial(**spec["fields"])
    return spec["raw"]


def segments(spec):
    if isinstance(spec, dict):
        return spec["raw"]
    return [MP.CoreSegment(**e["segment"]) if "segment" in e else e["raw"] for e in spec]


def py_call(fn, a):
    a = copy.deepcopy(a)
    if fn == "magnet.constants":
        return P.py_result(lambda: {"MU0_N_PER_A2": MP.MU0_N_PER_A2, "MAGNET_POWER_VERSION": MP.MAGNET_POWER_VERSION,
                                    "ANNEALED_COPPER_IACS": dataclasses.asdict(MP.ANNEALED_COPPER_IACS)})
    if fn == "magnet.material":
        return P.py_result(lambda: dataclasses.asdict(material(a["material"])))
    if fn == "magnet.segment":
        return P.py_result(lambda: dataclasses.asdict(MP.CoreSegment(**a["segment"]["segment"])))
    name = fn.split(".", 1)[1]

    def call():
        kw = {}
        if "core_segments" in a:
            kw["core_segments"] = segments(a["core_segments"])
        if "material" in a:
            kw["material"] = material(a["material"])
        args = [kw[k] if k in kw else a[k] for k in ARGS[name]]
        return getattr(MP, name)(*args)
    return P.py_result(call)


def mat_draw(rng):
    if rng.random() < 0.6:
        return {"ref": "ANNEALED_COPPER_IACS"}
    return {"fields": {"name": "rand conductor", "rho_ref_ohm_m": P.loguniform(rng, 1e-8, 1e-7), "T_ref_C": 20.0,
                       "alpha_ref_per_K": rng.uniform(0.003, 0.0045), "T_min_C": -50.0, "T_max_C": 250.0,
                       "density_kg_m3": rng.uniform(2700, 9000), "source": "synthetic"}}


def seg_draw(rng, j):
    mu = 1.0 if rng.random() < 0.2 else rng.uniform(1, 5000)
    return {"segment": {"name": f"seg{j}", "length_m": P.loguniform(rng, 1e-3, 0.2),
                        "area_m2": P.loguniform(rng, 1e-5, 1e-2), "mu_r": mu, "B_max_T": rng.uniform(0.3, 2.0)}}


def circuit_draw(rng):
    return {"B_gap_T": rng.uniform(0.005, 0.5), "gap_length_m": P.loguniform(rng, 1e-3, 3e-2),
            "gap_area_m2": P.loguniform(rng, 1e-5, 1e-2),
            "core_segments": [seg_draw(rng, j) for j in range(rng.randint(0, 3))],
            "leakage_factor": rng.uniform(1.0, 2.0)}


def coil_draw(rng, with_ni=True):
    d = {"NI_A": P.loguniform(rng, 10, 1e4)} if with_ni else {}
    d.update({"window_area_m2": P.loguniform(rng, 1e-6, 1e-3), "fill_factor": rng.uniform(0.05, 0.95),
              "mean_turn_length_m": P.loguniform(rng, 0.01, 1.0), "material": mat_draw(rng),
              "T_C": rng.uniform(-10, 210)})
    return d


def build_calls(contract, seed):
    calls = []
    for c in contract["inputs"]["registered_cases"]:
        calls.append((c["id"], "magnet." + c["fn"], decode(c["args"])))
    n = contract["inputs"]["randomized_domain"]["count"]
    gens = {
        "M2": (2, "resistance_factor", lambda r: {"material": mat_draw(r), "T_C": r.uniform(-60, 260)}),
        "M3": (3, "wire_resistance_ohm", lambda r: {"length_m": P.loguniform(r, 1e-3, 1e3),
                                                    "area_m2": P.loguniform(r, 1e-9, 1e-4), "material": mat_draw(r),
                                                    "T_C": r.uniform(-10, 210)}),
        "M4": (4, "awg_diameter_m", lambda r: {"gauge": r.randint(-5, 60)}),
        "M6": (6, "ampere_turns", circuit_draw),
        "M7": (7, "coil_power_continuous_W", coil_draw),
        "M8": (8, "coil_design", lambda r: dict(coil_draw(r), wire_diameter_m=P.loguniform(r, 5e-5, 5e-3))),
        "M9": (9, "electromagnet", lambda r: dict(circuit_draw(r), **coil_draw(r, with_ni=False),
                                                  wire_diameter_m=P.loguniform(r, 5e-5, 5e-3))),
        "M10": (10, "remanence_at_T", lambda r: {"B_r_ref_T": r.uniform(0.2, 1.4), "alpha_Br_per_K":
                                                 r.uniform(-0.0015, 0.0), "T_ref_C": r.choice([20.0, 25.0]),
                                                 "T_C": r.uniform(-60, 360)}),
        "M11": (11, "permanent_magnet", lambda r: dict(circuit_draw(r), magnet_area_m2=P.loguniform(r, 1e-5, 1e-2),
                                                       B_r_T=r.uniform(0.8, 1.4), mu_rec=r.uniform(1.0, 1.2),
                                                       H_knee_A_per_m=r.uniform(2e5, 2e6),
                                                       magnet_density_kg_m3=r.uniform(7000, 8500))),
    }
    for key, (k, fn, gen) in gens.items():
        rng = random.Random(seed * 1000 + k)
        for i in range(n[key]):
            calls.append((f"R{k}-{i}", "magnet." + fn, gen(rng)))
    return calls


def coil_records(rows, who):
    for r in rows:
        res = r["py"] if who == "py" else r["rs"]
        if res["outcome"] != "RETURNED":
            continue
        v = res["value"]
        if r["fn"] == "magnet.coil_design":
            yield r["case"], v, None
        if r["fn"] == "magnet.electromagnet":
            yield r["case"], v["coil"], v["circuit"]


def circuits(rows, who):
    for r in rows:
        res = r["py"] if who == "py" else r["rs"]
        if res["outcome"] != "RETURNED":
            continue
        v = res["value"]
        if r["fn"] == "magnet.ampere_turns":
            yield r["case"], v, True
        if r["fn"] in ("magnet.electromagnet", "magnet.permanent_magnet"):
            yield r["case"], v["circuit"], r["fn"] == "magnet.electromagnet"


def invariants(rows):
    b2, b3, b4 = [], [], []
    for r in rows:
        for who in ("py", "rs"):
            res = r[who]
            if res["outcome"] != "RETURNED":
                continue
            v = res["value"]
            if r["fn"] in ("magnet.electromagnet", "magnet.permanent_magnet"):
                if v.get("evidence_class") != "model-derived" or v.get("version") != "magnet_power_v1":
                    b2.append(r["case"])
            if r["fn"] == "magnet.permanent_magnet" and v.get("P_load_W") != 0.0:
                b3.append(r["case"])
            if r["fn"] == "magnet.constants" and v["ANNEALED_COPPER_IACS"] != dataclasses.asdict(
                    MP.ANNEALED_COPPER_IACS):
                b4.append(who)
    return {"INV-B02": {"pass": not b2, "detail": f"electromagnet / permanent_magnet records model-derived, "
                                                  f"magnet_power_v1 (both); violations {b2[:10]}"},
            "INV-B03": {"pass": not b3, "detail": f"permanent_magnet P_load_W exactly 0.0 (both); violations {b3[:10]}"},
            "INV-B04": {"pass": not b4, "detail": f"ANNEALED_COPPER_IACS equals the module object (both); "
                                                  f"violations {b4}"}}


def conservation(rows):
    out = {}
    for who, tag in (("rs", "Rust"), ("py", "Python, recorded")):
        bad1, bad2, bad3, n1, n3 = [], [], [], 0, 0
        for case, coil, circ in coil_records(rows, who):
            n1 += 1
            if abs(coil["P_W"] - coil["I_A"] * coil["V_V"]) > 1e-12 * coil["P_W"]:
                bad1.append(case)
            if circ is not None and abs(coil["N_turns"] * coil["I_A"] - circ["NI_A"]) > 1e-12 * circ["NI_A"]:
                bad2.append(case)
        for case, c, has_ni in circuits(rows, who):
            n3 += 1
            core = 0.0
            for s in c["segments"]:
                core += s["mmf_A"]
            ok = core == c["mmf_core_A"] and c["phi_core_Wb"] == c["leakage_factor"] * c["phi_gap_Wb"]
            if has_ni:
                ok &= abs(c["NI_A"] - (c["mmf_gap_A"] + c["mmf_core_A"])) <= 1e-12 * c["NI_A"]
            if not ok:
                bad3.append(case)
        out[f"CONS-B1 ({tag})"] = {"pass": not bad1, "detail": f"{n1} coils: |P - I V| <= 1e-12 P; violations "
                                                               f"{bad1[:10]}"}
        out[f"CONS-B2 ({tag})"] = {"pass": not bad2, "detail": f"N I = NI of the circuit; violations {bad2[:10]}"}
        out[f"CONS-B3 ({tag})"] = {"pass": not bad3, "detail": f"{n3} circuits: NI = mmf_gap + mmf_core, mmf_core = "
                                                               f"sum of segments, phi_core = k phi_gap; violations "
                                                               f"{bad3[:10]}"}
    return out


def perf_specs(rows):
    em = [r for r in rows if r["case"] == "EM-01"][0]
    return [("PERF-B01", "magnet.electromagnet", em["args"], 10000)]


LEDGER_REQUEST = [{"component": CID, "status": "ADMITTED", "parity": "PARITY_PASS",
                   "scope": "named function subset (RM-R17): every function and constant of abep_sim/magnet_power.py "
                            "except ecr_resonance_field_T (not ported: historical ECR family)",
                   "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::power::magnet)",
                   "python": "ecr_resonance_field_T stays in the module as history (inventory not_ported_parts); the "
                             "module retires from active execution with this admission"}]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=["development", "score"], required=True)
    ap.add_argument("--work", required=True)
    a = ap.parse_args(argv)
    if a.mode == "score" and P.git_state()["git_dirty"]:
        print("refused: score mode needs a clean, committed tree")
        return 2
    summary, _ = P.run_campaign(cid=CID, contract_path=CONTRACT, harness=Path(__file__).resolve(), mode=a.mode,
                                work=Path(a.work), build_calls=build_calls, py_call=py_call,
                                message_classes={"ValueError"}, invariants_fn=invariants,
                                conservation_fn=conservation, perf_specs=perf_specs, ledger_request=LEDGER_REQUEST)
    print(json.dumps(summary, indent=1, ensure_ascii=False)[:6000])
    return 0 if summary["verdict"] == "ADMITTED" else 1


if __name__ == "__main__":
    sys.exit(main())
