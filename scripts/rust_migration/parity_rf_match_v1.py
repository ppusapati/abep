"""Parity campaign of contract C-DOCS_EXPERIMENTS_HALL_ICP_P2_IMPEDANCE_MAP v1 (SC-WP-05 RF generator / matching).

Python reference: the RF-network kernels of docs/experiments/hall_icp/p2_impedance_map/p2_framework.py, the basic RF
relations of p2_impedance_reducer.py and p1_reducer.p_bus_from_generator_input (all loaded by file path), vs the Rust
example `power_eval` (abep_subsystems::power::{cplx, rf_match}) on the preregistered calls.

  python scripts/rust_migration/parity_rf_match_v1.py --mode development --work DIR
  python scripts/rust_migration/parity_rf_match_v1.py --mode score --work DIR
"""
from __future__ import annotations

import argparse
import cmath
import copy
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_power_common as P  # noqa: E402

ROOT = P.ROOT
CID = "C-DOCS_EXPERIMENTS_HALL_ICP_P2_IMPEDANCE_MAP"
CONTRACT = ROOT / "docs/rust_migration/contracts" / CID / "parity_prereg_v1.json"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FW = _load("p2_framework_parity_wp05", "docs/experiments/hall_icp/p2_impedance_map/p2_framework.py")
RED = FW.RED
P1 = _load("p1_reducer_parity_wp05", "docs/experiments/hall_icp/p1_icp_bench/p1_reducer.py")

# contract inputs.encoding: arguments converted from [re, im] to complex (all others are passed as given)
CONVERTED = {"sol_correct": {"gamma_measured"}, "dissipated_fraction_matched": {"s11", "s21"},
             "gamma_from_z": {"z"}, "z_from_gamma": {"g"}, "s_to_abcd": {"s11", "s12", "s21", "s22"},
             "correct_reflection": {"m_raw", "e00", "e11", "e10e01"}, "z_in": {"z_load"},
             "deembed_load": {"z_input"}, "transfer_efficiency": {"z_load"}, "fixture_to_plane": {"v_p", "i_p"}}
ABCD_ARGS = {"abcd", "abcd_fix", "m1", "m2"}
ARGS = {
    "gamma_from_z": ["z", "z0"], "z_from_gamma": ["g", "z0"], "vswr": ["gmag"],
    "gamma_mag_from_powers": ["p_fwd", "p_ref"], "s_to_abcd": ["s11", "s12", "s21", "s22", "z0"],
    "abcd_to_s": ["abcd", "z0"], "cascade": ["m1", "m2"], "z_in": ["abcd", "z_load"],
    "deembed_load": ["abcd", "z_input"], "transfer_efficiency": ["abcd", "z_load"],
    "correct_reflection": ["m_raw", "e00", "e11", "e10e01"], "fixture_to_plane": ["abcd_fix", "v_p", "i_p"],
    "line_peak_stress": ["p_fwd", "gmag", "z0"],
}
EXACT_SOL: set[str] = set()   # case ids of 3-standard, noise-free SOL calls (CONS-C3)


def conv(v):
    if isinstance(v, list) and len(v) == 2:
        return complex(v[0], v[1])
    return v


def sol_standards(spec: dict) -> list:
    """contract inputs.encoding.$sol: measured = e00 + e10e01 * a / (1 - e11 * a) + noise_i (Python complex)."""
    t = {k: complex(*v) for k, v in spec["terms"].items()}
    ids = spec.get("ids")
    noise = spec.get("noise")
    out = []
    for i, (re_, im_) in enumerate(spec["actual"]):
        a = complex(re_, im_)
        m = t["e00"] + t["e10e01"] * a / (1 - t["e11"] * a)
        if noise is not None:
            m = m + complex(noise[i][0], noise[i][1])
        out.append({"id": ids[i] if ids else f"STD{i}", "gamma_actual": [a.real, a.imag],
                    "gamma_measured": [m.real, m.imag], "definition_source": "registered synthetic standard"})
    return out


def expand(case_id: str, fn: str, args: dict) -> dict:
    if fn == "sol_error_terms" and isinstance(args.get("standards"), dict) and "$sol" in args["standards"]:
        spec = args["standards"]["$sol"]
        if spec.get("noise") is None and len(spec["actual"]) == 3:
            EXACT_SOL.add(case_id)
        return {"standards": sol_standards(spec)}
    return args


def py_call(fn, a):
    a = copy.deepcopy(a)
    name = fn.split(".", 1)[1]

    def call():
        if name == "parse_touchstone":
            return FW.parse_touchstone(a["text"], a["n_ports"], allow_spec_defaults=a.get("allow_spec_defaults",
                                                                                          False),
                                       source=a.get("source"))
        if name == "sol_error_terms":
            return FW.sol_error_terms(a["standards"])
        if name == "sol_correct":
            terms = {k: conv(v) for k, v in a["terms"].items()}
            return FW.sol_correct(conv(a["gamma_measured"]), terms)
        if name == "ladder_abcd":
            return FW.ladder_abcd(a["elements"])
        if name == "dissipated_fraction_matched":
            return FW.dissipated_fraction_matched(conv(a["s11"]), conv(a["s21"]))
        if name == "vi_power_and_impedance":
            return FW.vi_power_and_impedance(a["V_raw"], a["I_raw"], a["k_V"], a["k_I"], a["amplitude_convention"])
        if name == "cx":
            return RED.cx(a["v"], a["what"])
        if name == "p_bus_from_generator_input":
            return P1.p_bus_from_generator_input(a["record"])
        conv_set = CONVERTED.get(name, set())
        args = []
        for k in ARGS[name]:
            v = a[k]
            if k in ABCD_ARGS:
                v = tuple(conv(x) for x in v)
            elif k in conv_set:
                v = conv(v)
            args.append(v)
        return getattr(RED, name)(*args)
    return P.py_result(call)


# ============================================================================================== randomized domain
def rphase(rng):
    return rng.uniform(-math.pi, math.pi)


def cpair(z):
    return [z.real, z.imag]


def polar(rng, lo, hi):
    return cmath.rect(rng.uniform(lo, hi), rphase(rng))


def terms_draw(rng):
    return {"e00": cpair(polar(rng, 0.0, 0.2)), "e11": cpair(polar(rng, 0.0, 0.3)),
            "e10e01": cpair(polar(rng, 0.7, 1.0))}


def touchstone_draw(rng):
    n_ports = rng.choice([1, 2])
    unit = rng.choice(["HZ", "KHZ", "MHZ", "GHZ"])
    fmt = rng.choice(["RI", "MA", "DB"])
    r = rng.choice(["50", "75", "100"])
    npts = rng.randint(1, 12)
    f0, step = rng.uniform(1.0, 100.0), rng.uniform(0.001, 1.0)
    rows = []
    for i in range(npts):
        toks = [repr(f0 + i * step)]
        for _ in range(n_ports * n_ports):
            if fmt == "RI":
                toks += [repr(rng.uniform(-1, 1)), repr(rng.uniform(-1, 1))]
            elif fmt == "MA":
                toks += [repr(rng.uniform(0, 1)), repr(rng.uniform(-180, 180))]
            else:
                toks += [repr(rng.uniform(-60, 0)), repr(rng.uniform(-180, 180))]
        rows.append(toks)
    if rng.random() < 0.15:
        kind = rng.choice(["swap", "drop", "token"])
        if kind == "swap" and npts >= 2:
            i, j = rng.sample(range(npts), 2)
            rows[i][0], rows[j][0] = rows[j][0], rows[i][0]
        elif kind == "drop" or (kind == "swap" and npts < 2):
            rows[rng.randrange(npts)].pop()
        else:
            row = rows[rng.randrange(npts)]
            row.insert(rng.randint(1, len(row)), "x1")
    text = f"# {unit} S {fmt} R {r}\n" + "".join(" ".join(t) + "\n" for t in rows)
    return {"text": text, "n_ports": n_ports}


def sol_draw(rng):
    n = rng.randint(3, 6)
    spec = {"terms": terms_draw(rng), "actual": [cpair(polar(rng, 0.0, 1.0)) for _ in range(n)]}
    if rng.random() < 0.5:
        spec["noise"] = [[rng.uniform(-1e-3, 1e-3), rng.uniform(-1e-3, 1e-3)] for _ in range(n)]
    return {"standards": {"$sol": spec}}


def ladder_draw(rng):
    return {"elements": [{"id": f"E{j}", "kind": rng.choice(["series", "shunt"]),
                          "Z_ohm": [rng.uniform(0, 5), rng.uniform(-500, 500)]} for j in range(rng.randint(1, 5))]}


def vi_draw(rng):
    def u():
        return [rng.uniform(-10, 10), rng.uniform(-10, 10)]

    def k():
        return [rng.uniform(0.1, 200), rng.uniform(0.1, 200)]
    return {"V_raw": u(), "I_raw": u(), "k_V": k(), "k_I": k(), "amplitude_convention": rng.choice(["peak", "rms"])}


def abcd_draw(rng):
    return [[1.0 + rng.uniform(-0.2, 0.2), rng.uniform(-0.05, 0.05)], [rng.uniform(0, 10), rng.uniform(-500, 500)],
            [rng.uniform(0, 1e-3), rng.uniform(-0.05, 0.05)], [1.0 + rng.uniform(-0.2, 0.2), rng.uniform(-0.05, 0.05)]]


R7_DRAWS = [
    ("gamma_from_z", lambda r: {"z": [r.uniform(-100, 500), r.uniform(-500, 500)],
                                "z0": 0.0 if r.random() < 0.1 else r.choice([50.0, 75.0, 100.0])}),
    ("z_from_gamma", lambda r: {"g": cpair(polar(r, 0.0, 1.2)), "z0": r.choice([50.0, 75.0])}),
    ("vswr", lambda r: {"gmag": r.uniform(-0.2, 1.2)}),
    ("gamma_mag_from_powers", lambda r: {"p_fwd": r.uniform(-10.0, 1000.0), "p_ref": r.uniform(-10.0, 1100.0)}),
    ("s_to_abcd", lambda r: {"s11": cpair(polar(r, 0, 1)), "s12": cpair(polar(r, 0, 1)),
                             "s21": cpair(polar(r, 0, 1)), "s22": cpair(polar(r, 0, 1)),
                             "z0": r.choice([50.0, 75.0])}),
    ("abcd_to_s", lambda r: {"abcd": abcd_draw(r), "z0": r.choice([50.0, 75.0])}),
    ("transfer_efficiency", lambda r: {"abcd": abcd_draw(r), "z_load": [r.uniform(-5, 100), r.uniform(-200, 200)]}),
    ("correct_reflection", lambda r: dict({"m_raw": cpair(polar(r, 0, 1))}, **terms_draw(r))),
]


def build_calls(contract, seed):
    EXACT_SOL.clear()
    calls = []
    for c in contract["inputs"]["registered_cases"]:
        args = P.decode(c["args"])
        calls.append((c["id"], "rf." + c["fn"], expand(c["id"], c["fn"], args)))
    n = contract["inputs"]["randomized_domain"]["count"]
    gens = [("R1", 1, "parse_touchstone", touchstone_draw), ("R2", 2, "sol_error_terms", sol_draw),
            ("R3", 3, "sol_correct", lambda r: {"gamma_measured": cpair(polar(r, 0.0, 1.0)), "terms": terms_draw(r)}),
            ("R4", 4, "ladder_abcd", ladder_draw),
            ("R5", 5, "dissipated_fraction_matched", lambda r: {"s11": cpair(polar(r, 0, 1)),
                                                                "s21": cpair(polar(r, 0, 1))}),
            ("R6", 6, "vi_power_and_impedance", vi_draw)]
    for key, k, fn, gen in gens:
        rng = random.Random(seed * 1000 + k)
        for i in range(n[key]):
            cid = f"R{k}-{i}"
            calls.append((cid, "rf." + fn, expand(cid, fn, gen(rng))))
    rng = random.Random(seed * 1000 + 7)
    per = n["R7"] // len(R7_DRAWS)
    i = 0
    for fn, gen in R7_DRAWS:
        for _ in range(per):
            calls.append((f"R7-{i}", "rf." + fn, gen(rng)))
            i += 1
    return calls


# ============================================================================================== checks
def _cl(v):
    return complex(v[0], v[1]) if isinstance(v, list) else complex(v)


def invariants(rows):
    c2, c3 = [], []
    ident = [[1.0, 0.0], [0.0, 0.0], [0.0, 0.0], [1.0, 0.0]]
    n2 = n3 = 0
    for r in rows:
        for who in ("py", "rs"):
            res = r[who]
            if r["fn"] == "rf.p_bus_from_generator_input":
                n2 += 1
                if res["outcome"] != "RAISED" or res.get("class") != "PMainsNotPBusError":
                    c2.append((r["case"], who))
            if r["fn"] == "rf.ladder_abcd" and r["args"].get("elements") == []:
                n3 += 1
                if res["outcome"] != "RETURNED" or res["value"] != ident:
                    c3.append((r["case"], who))
    return {"INV-C02": {"pass": not c2 and n2 > 0, "detail": f"{n2} evaluations (both): p_bus_from_generator_input "
                                                             f"always PMainsNotPBusError; violations {c2[:10]}"},
            "INV-C03": {"pass": not c3 and n3 > 0, "detail": f"{n3} evaluations (both): ladder_abcd([]) is the "
                                                             f"identity ((1, 0), (0, 0), (0, 0), (1, 0)); violations "
                                                             f"{c3[:10]}"}}


def conservation(rows):
    out = {}
    for who, tag in (("rs", "Rust"), ("py", "Python, recorded")):
        b1, b2, n1, n2, worst1, worst2 = [], [], 0, 0, 0.0, 0.0
        for r in rows:
            res = r[who]
            if res["outcome"] != "RETURNED":
                continue
            if r["fn"] == "rf.ladder_abcd":
                a, b, c, d = (_cl(x) for x in res["value"])
                err = abs(a * d - b * c - 1)
                n1 += 1
                worst1 = max(worst1, err)
                if not err <= 1e-9:
                    b1.append(r["case"])
            if r["fn"] == "rf.dissipated_fraction_matched":
                s11, s21 = _cl(r["args"]["s11"]), _cl(r["args"]["s21"])
                raw = 1 - abs(s11) ** 2 - abs(s21) ** 2
                if raw >= 0:
                    n2 += 1
                    err = abs(res["value"] + abs(s11) ** 2 + abs(s21) ** 2 - 1)
                    worst2 = max(worst2, err)
                    if not err <= 1e-12:
                        b2.append(r["case"])
        out[f"CONS-C1 ({tag})"] = {"pass": not b1, "detail": f"{n1} ladders: max |AD - BC - 1| = {worst1:.3g} "
                                                             f"(tolerance 1e-9); violations {b1[:10]}"}
        out[f"CONS-C2 ({tag})"] = {"pass": not b2, "detail": f"{n2} unclipped matched two-ports: max |f + |S11|^2 + "
                                                             f"|S21|^2 - 1| = {worst2:.3g} (tolerance 1e-12); "
                                                             f"violations {b2[:10]}"}
    b3, n3, worst3 = [], 0, 0.0
    for r in rows:
        if r["case"] not in EXACT_SOL or r["rs"]["outcome"] != "RETURNED":
            continue
        v = r["rs"]["value"]
        e00, e11, e10 = _cl(v["e00"]), _cl(v["e11"]), _cl(v["e10e01"])
        for s in r["args"]["standards"]:
            m, ga = _cl(s["gamma_measured"]), _cl(s["gamma_actual"])
            corrected = (m - e00) / (e10 + e11 * (m - e00))
            err = abs(corrected - ga)
            n3 += 1
            worst3 = max(worst3, err)
            if not err <= 1e-9:
                b3.append(r["case"])
    out["CONS-C3 (Rust)"] = {"pass": not b3 and n3 > 0,
                             "detail": f"{n3} standards of {len(EXACT_SOL)} exactly determined noise-free SOL calls: "
                                       f"max |corrected - actual| = {worst3:.3g} (tolerance 1e-9); violations "
                                       f"{sorted(set(b3))[:10]}"}
    return out


def perf_specs(rows):
    by = {r["case"]: r for r in rows}
    return [("PERF-C01", "rf.parse_touchstone", by["TS-02"]["args"], 10000),
            ("PERF-C02", "rf.sol_error_terms", by["SO-02"]["args"], 10000)]


LEDGER_REQUEST = [
    {"component": CID, "status": "PARTIAL_ADMISSION", "parity": "PARITY_PASS",
     "scope": "named function subset (RM-R17): p2_framework.py parse_touchstone, sol_error_terms, sol_correct, "
              "ladder_abcd, dissipated_fraction_matched, vi_power_and_impedance; p2_impedance_reducer.py cx, "
              "gamma_from_z, z_from_gamma, vswr, gamma_mag_from_powers, s_to_abcd, abcd_to_s, cascade, z_in, "
              "deembed_load, transfer_efficiency, correct_reflection, fixture_to_plane, line_peak_stress",
     "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::power::{cplx, rf_match})",
     "python": "verify_line_match_loss and every other function of the P2 package stay PYTHON_REFERENCE (contract "
               "component.out_of_scope)"},
    {"component": "C-DOCS_EXPERIMENTS_HALL_ICP_P1_ICP_BENCH", "status": "PARTIAL_ADMISSION", "parity": "PARITY_PASS",
     "scope": "p1_reducer.p_bus_from_generator_input only (the P_mains refusal); the row stays SC-WP-03",
     "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::power::rf_match::"
                                     "p_bus_from_generator_input)"},
]

MESSAGE_CLASSES = {"TouchstoneError", "FrameworkError", "CalibrationSolveError", "RecordError", "PMainsNotPBusError",
                   "ZeroDivisionError", "ValueError"}


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
                                message_classes=MESSAGE_CLASSES, invariants_fn=invariants,
                                conservation_fn=conservation, perf_specs=perf_specs, ledger_request=LEDGER_REQUEST)
    print(json.dumps(summary, indent=1, ensure_ascii=False)[:8000])
    return 0 if summary["verdict"] == "ADMITTED" else 1


if __name__ == "__main__":
    sys.exit(main())
