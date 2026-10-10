"""Parity campaign of contract C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY v1 (the active-architecture invariant).

Python reference (abep_sim/design/a9_19_architecture.py) vs the Rust CLI (`abep-config eval`) on the preregistered
inputs: registered element vectors R-01..R-10, 400 seeded element lists, configurations, ground-reference requests,
decision-record trees V-00..V-05 and definition trees A-00..A-03 (A-01 / A-02 scored against the registered Rust
outcome of DIV-A01). Case trees are temporary; the repository is never modified.

  python scripts/rust_migration/parity_architecture_v1.py --mode development --work DIR
  python scripts/rust_migration/parity_architecture_v1.py --mode score --work DIR --out RESULT.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_common as C  # noqa: E402

ROOT = C.ROOT
sys.path.insert(0, str(ROOT))
from abep_sim import bus_boundary_a9_v2 as bb  # noqa: E402
from abep_sim.design import a9_19_architecture as a919  # noqa: E402
from abep_sim.design import architecture_optimizer as ao  # noqa: E402

CDIR = ROOT / "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY"
CONTRACT = CDIR / "parity_prereg_v1.json"
FLIGHT = "hall_icp_neutralizer"
ARCH = "architecture/hall_icp_neutralizer_v1.json"
MESSAGE_CLASSES = {"ArchitectureRuleError", "ConfigurationError"}
CONSTANT_NAMES = ["DECISIONS", "RFP_REGISTRATION", "RFP_CLAUSES", "VERBATIM_A9_19", "FLIGHT_CONFIGURATION",
                  "FLIGHT_CONFIGURATIONS", "GROUND_REFERENCE_CONFIGURATION", "GROUND_REFERENCE_LABEL",
                  "GROUND_ONLY_LAB_EQUIPMENT", "C1_ROLE", "SUPPLY_MODE_AIR", "SUPPLY_MODE_XE", "SUPPLY_MODES",
                  "XE_PATH_ROLE", "AIR_PATH_ROLE", "SUPPLY_MODE_GASES", "BENCH_ENGINEERING_GAS", "BENCH_SUPPLY_MODE",
                  "ICP_FEED_GAS_BASELINE", "FLIGHT_ARCHITECTURE", "C1_BOOKING_CONDITIONAL", "C1_BOOKING_EMBEDDED",
                  "C1_FLAGGED_BOOKINGS", "C1_DECLARED_ABSENT", "CHECK_CLEAN", "CHECK_FLAGGED"]

DEFINITION_SCRIPT = """
import json, sys
sys.path.insert(0, sys.argv[1])
names = json.loads(sys.argv[2])
try:
    from abep_sim.design import a9_19_architecture as m
    out = json.loads(json.dumps({n: getattr(m, n) for n in names}))
    print(json.dumps({"outcome": "RETURNED", "value": out}))
except Exception as e:
    print(json.dumps({"outcome": "RAISED", "class": type(e).__name__, "message": str(e)}))
"""


def jr(v):
    """JSON round trip: both implementations receive identical data."""
    return json.loads(json.dumps(v))


def element_cases(contract: dict) -> list[tuple[str, list]]:
    gv = contract["inputs"]["golden_vectors"]
    r01 = jr(ao.flight_configuration_elements(FLIGHT))
    cases = [("R-01", r01)]
    cases += [(f"R-02.{i:02d}", [e]) for i, e in enumerate(r01)]
    slots = jr(list(bb.GROUND_REFERENCE_TEST_METADATA["hall_c1_reference"]["base_slots_as_in_v1"]))
    cases += [("R-03", slots)] + [(f"R-03.{i:02d}", [s]) for i, s in enumerate(slots)]
    inst = jr(list(bb.installed_slots(FLIGHT)))
    cases += [("R-04", inst)] + [(f"R-04.{i:02d}", [s]) for i, s in enumerate(inst)]
    markers = ["c1_heater", "c1_keeper", "AL-C1", "hollow cathode", "LaB6 emitter", {"id": "X", "name": "C1"},
               {"id": "C-1"}, "cathode_heater", "C1 Xe branch"]
    cases += [(f"R-05.{i:02d}", r01 + [m]) for i, m in enumerate(markers)]
    base = {"line": "AL-99", "name": "Hall PPU", "floor_constituents": []}
    lines = [
        dict(base, name="Hall PPU (C1 heater/keeper electronics if C1 selected)"),
        dict(base, name="Hall PPU (C1 heater/keeper electronics)"),
        dict(base, floor_constituents=[{"what": "C1 cathode unit analog", "kg": 0.2}]),
        dict(base, c1_branch={"state": "C1_SELECTED", "in_AL08": 0.285}),
        dict(base, c1_branch={"state": "PENDING_C1_NOT_SELECTED", "in_AL08": 0.285}),
        dict(base, c1_branch={"state": "PENDING_C1_NOT_SELECTED", "in_AL08": None}),
        dict(base),
        dict(base, name="Hall PPU (incl. collector/bias supply; no C1 electronics - C1 is ground-only, A9.19 / A9.20)",
             c1_branch={"state": "NO_C1_XE_BRANCH_IN_FLIGHT (A9.19 / A9.20)", "in_AL08": False}),
        dict(base, name="Hall PPU (no C1 electronics; C1 heater/keeper supply)"),
        dict(base, c1_branch={"state": "NO_C1_XE_BRANCH_IN_FLIGHT", "in_AL08": 0.285}),
    ]
    cases += [(f"R-06.{i:02d}", jr(ao._line_hc_elements(ln, FLIGHT))) for i, ln in enumerate(lines)]
    mp = json.loads((ROOT / ao.MP_V3_REL).read_text(encoding="utf-8"))
    k = 0
    for _, lns in ao.ground_reference_lines(mp, "hall_c1_reference"):
        for ln in lns:
            cases.append((f"R-07.{k:02d}", jr(ao._line_hc_elements(ln, FLIGHT))))
            k += 1
    for i, t in enumerate(gv["registered_texts"]):
        cases += [(f"R-08.{i:03d}.s", [t]), (f"R-08.{i:03d}.name", [{"name": t}]), (f"R-08.{i:03d}.id", [{"id": t}])]
    cases += [(f"R-09.{i:02d}", [r]) for i, r in enumerate(gv["registered_records"])]
    cases += [(f"R-10.{i:02d}", [s]) for i, s in enumerate(gv["registered_scalars"])]
    return cases


def random_cases(contract: dict, seed: int) -> list[tuple[str, list]]:
    rd = contract["inputs"]["randomized_domain"]
    tokens, seps = rd["TOKENS"], rd["SEPARATORS"]
    scalars = contract["inputs"]["golden_vectors"]["registered_scalars"]
    rng = random.Random(seed)

    def text():
        k = rng.randint(1, 4)
        s = rng.choice(tokens)
        for _ in range(k - 1):
            s += rng.choice(seps) + rng.choice(tokens)
        u = rng.random()
        return s.upper() if u < 0.2 else s.lower() if u < 0.4 else s

    def pick(options):
        i = rng.randrange(len(options))
        return text() if options[i] is text else options[i]

    def record():
        r = {}
        for key in ["id", "name", "kind", "line", "slot", "booking", "state", "in_line", "kg"]:
            if rng.random() >= 0.4:
                continue
            if key in ("id", "line", "slot"):
                r[key] = text()
            elif key == "name":
                r[key] = rng.choice(scalars) if rng.random() < 0.1 else text()
            elif key == "kind":
                r[key] = pick(["mass_line", "c1_branch", "power_slot", "floor_constituent", text])
            elif key == "booking":
                r[key] = pick(["CONDITIONAL_NOT_BOOKED", "EMBEDDED_IN_FLOOR", "DECLARED_ABSENT", "NONE", text])
            elif key == "state":
                r[key] = pick(["NO_C1_XE_BRANCH_IN_FLIGHT", "no_c1 hardware", "C1_SELECTED", "PENDING_C1_NOT_SELECTED",
                               text])
            elif key == "in_line":
                r[key] = rng.choice([False, True, 0, 0.285, None, "", "x", []])
            else:
                r[key] = rng.choice([0.0, 0.285, 1.5])
        return r

    out = []
    for k in range(rd["count"]):
        els = []
        for _ in range(rng.randint(1, 6)):
            u = rng.random()
            els.append(text() if u < 0.45 else record() if u < 0.90 else rng.choice(scalars))
        out.append((f"RND-{k:03d}", jr(els)))
    return out


def run(mode: str, work: Path) -> dict:
    contract_bytes = CONTRACT.read_bytes()
    contract = json.loads(contract_bytes)
    changed = [f["path"] for f in contract["reference_implementation"]["files"]
               if C.sha_file(ROOT / f["path"]) != f["sha256_at_registration"]]
    seeds = contract["campaign_seeds"]
    seed = seeds["scoring_master_seed"] if mode == "score" else seeds["development_master_seed"]
    t0 = time.time()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    if changed:
        return {"verdict": "REFUSED_REFERENCE_CHANGED", "changed": changed}
    pinned_bad = [p for p, h in contract["pinned_inputs_sha256"].items() if C.sha_file(ROOT / p) != h]
    binary = C.cargo_build()
    base = {"repo": str(ROOT), "root": str(ROOT / "config")}

    rows, calls = [], []

    def add(cid, fn, py, **kw):
        rows.append({"case": cid, "fn": fn, "args": kw, "py": py})
        calls.append(dict(base, fn=fn, **kw))

    reg = element_cases(contract)
    rnd = random_cases(contract, seed)
    (work / "element_cases.json").write_text(json.dumps(reg + rnd, ensure_ascii=True) + "\n", encoding="utf-8")
    for cid, els in reg + rnd:
        add(cid, "hollow_cathode_elements", C.py_result(a919.hollow_cathode_elements, els), elements=els)
        add(cid, "refuse_hollow_cathode_elements",
            C.py_result(a919.refuse_hollow_cathode_elements, FLIGHT, els), config=FLIGHT, elements=els)
    r01 = reg[0][1]
    ed = contract["inputs"]["edge_cases"]
    for i, conf in enumerate(ed["require_flight_configuration"]):
        add(f"CFG-{i:02d}", "require_flight_configuration", C.py_result(a919.require_flight_configuration, conf),
            config=conf)
        add(f"CFG-{i:02d}", "refuse_hollow_cathode_elements", C.py_result(a919.refuse_hollow_cathode_elements, conf, r01),
            config=conf, elements=r01)
    for i, (conf, purpose) in enumerate(ed["ground_reference"]):
        add(f"GR-{i:02d}", "ground_reference", C.py_result(a919.ground_reference, conf, purpose), config=conf,
            purpose=purpose)
    d = a919.DECISIONS

    def tamper(md_or_json, key, how):
        def f(r):
            p = r / d[key][md_or_json]
            if how == "delete":
                p.unlink()
            elif how == "space":
                p.write_bytes(p.read_bytes() + b" ")
            else:
                b = p.read_bytes()
                p.write_bytes(b[:-1] + b" \n" if b.endswith(b"\n") else b + b" ")
        return (d[key][md_or_json], f)
    vcases = {"V-00": [], "V-01": [tamper("md", "A9.19", "space")], "V-02": [tamper("json", "A9.20", "nl")],
              "V-03": [tamper("md", "A9.15", "delete")],
              "V-04": [tamper("json", "A9.19", "delete"), tamper("md", "A9.20", "nl")],
              "V-05": [tamper("json", "A9.15", "nl")]}
    for vid, muts in vcases.items():
        farm = C.make_repo(work / vid / "repo", {rel for rel, _ in muts}) if muts else ROOT
        for _, f in muts:
            f(farm)
        add(vid, "verify_decision_records", C.py_result(a919.verify_decision_records, farm), decision_repo=str(farm))

    # definition trees
    arch_pin = contract["invariants_registered"]["architecture_file"]["sha256"]
    def_rows = []
    for aid in ("A-00", "A-01", "A-02", "A-03"):
        c = work / aid / "config"
        shutil.copytree(ROOT / "config", c)
        if aid in ("A-01", "A-03"):
            b = (c / ARCH).read_bytes()
            (c / ARCH).write_bytes(b[:-1] + b" \n")
        if aid == "A-02":
            doc = json.loads((c / ARCH).read_text(encoding="utf-8"))
            doc["title"] += " (edited)"
            (c / ARCH).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        if aid in ("A-01", "A-02"):
            man = json.loads((c / "MANIFEST.json").read_text(encoding="utf-8"))
            for rel in man["files"]:
                bb_ = (c / rel).read_bytes()
                man["files"][rel] = {"sha256": C.sha_bytes(bb_), "bytes": len(bb_)}
            (c / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
        env = dict(os.environ, ABEP_CONFIG_ROOT=str(c))
        out = subprocess.run([sys.executable, "-c", DEFINITION_SCRIPT, str(ROOT), json.dumps(CONSTANT_NAMES)],
                             capture_output=True, text=True, env=env)
        py = json.loads(out.stdout.strip().splitlines()[-1])
        def_rows.append({"case": aid, "py": py, "actual_sha256": C.sha_file(c / ARCH)})
        calls.append({"fn": "arch_definition", "repo": str(ROOT), "root": str(c)})

    rust, rbytes = C.rust_eval(binary, calls, work, "arch")
    _, rbytes2 = C.rust_eval(binary, calls, work, "arch_again")
    failures, n = [], 0
    for i, row in enumerate(rows):
        n += 1
        diff = C.compare(row["py"], rust[i], MESSAGE_CLASSES)
        if diff:
            failures.append({"case": row["case"], "fn": row["fn"], "diff": diff})
    definition = []
    for j, row in enumerate(def_rows):
        rs = rust[len(rows) + j]
        if row["case"] in ("A-01", "A-02"):
            want = {"outcome": "RAISED", "class": "ConfigurationError",
                    "message": f"config/{ARCH} sha256 {row['actual_sha256']} != pinned {arch_pin} (A9.29 architecture "
                               "hash pin: a changed architecture needs a new architecture version and pin)"}
            diff = C.compare(want, rs, MESSAGE_CLASSES)
            basis = "DIV-A01 registered Rust outcome"
        else:
            diff = C.compare(row["py"], rs, MESSAGE_CLASSES)
            basis = "Python reference"
        definition.append({"case": row["case"], "scored_against": basis, "python_outcome": row["py"]["outcome"],
                           "python_class": row["py"].get("class"), "rust_outcome": rs["outcome"],
                           "rust_class": rs.get("class"), "parity": not diff})
        if diff:
            failures.append({"case": row["case"], "fn": "arch_definition", "diff": diff})

    # invariants
    a00_py, a00_rs = def_rows[0]["py"], rust[len(rows)]

    def find(cid, fn):
        return [(r["py"], rust[i]) for i, r in enumerate(rows) if r["case"] == cid and r["fn"] == fn][0]
    inv_a1 = all(v["outcome"] == "RETURNED" and v["value"]["FLIGHT_ARCHITECTURE"]["conventional_hollow_cathode"] ==
                 "NONE" and v["value"]["FLIGHT_CONFIGURATIONS"] == [FLIGHT] for v in (a00_py, a00_rs))
    c1 = [i for i, c in enumerate(ed["require_flight_configuration"]) if c == "hall_c1_reference"][0]
    gr = [i for i, g in enumerate(ed["ground_reference"]) if g == ["hall_c1_reference", "C1-vs-ICP bench control"]][0]
    req_py, req_rs = find(f"CFG-{c1:02d}", "require_flight_configuration")
    gr_py, gr_rs = find(f"GR-{gr:02d}", "ground_reference")
    inv_a2 = req_py["outcome"] == req_rs["outcome"] == "RAISED" and all(
        v["outcome"] == "RETURNED" and v["value"]["flight_candidate"] is False and v["value"]["in_flight_budgets"] is False
        and v["value"]["label"] == "GROUND_REFERENCE" for v in (gr_py, gr_rs))
    r1_py, r1_rs = find("R-01", "refuse_hollow_cathode_elements")
    inv_a3 = all(v["outcome"] == "RETURNED" and v["value"]["check"] == a919.CHECK_CLEAN
                 and v["value"]["c1_provisions_flagged"] == [] for v in (r1_py, r1_rs))
    man = json.loads((ROOT / "config/MANIFEST.json").read_text(encoding="utf-8"))
    inv_a5 = a00_rs["outcome"] == "RETURNED" and C.sha_file(ROOT / "config" / ARCH) == man["files"][ARCH]["sha256"] \
        == arch_pin
    invariants = {
        "INV-A1": {"pass": inv_a1, "detail": "FLIGHT_ARCHITECTURE.conventional_hollow_cathode == NONE, "
                                             "FLIGHT_CONFIGURATIONS == [hall_icp_neutralizer] (both)"},
        "INV-A2": {"pass": inv_a2, "detail": "hall_c1_reference refused as flight configuration; ground_reference "
                                             "flight_candidate / in_flight_budgets false, label GROUND_REFERENCE (both)"},
        "INV-A3": {"pass": inv_a3, "detail": "R-01 (mass_power_a9_v5 flight elements) check NO_HOLLOW_CATHODE_ELEMENT_LISTED, "
                                             "no flagged provisions (both)"},
        "INV-A4": {"pass": rbytes == rbytes2, "detail": "Rust eval twice byte-identical"},
        "INV-A5": {"pass": inv_a5, "detail": "Rust pin accepted on the reference tree; architecture sha256 == MANIFEST "
                                             "entry == registered pin"},
    }
    perf = {"PERF-ARCH-01": {
        "python_s": C.timed(lambda: [a919.refuse_hollow_cathode_elements(FLIGHT, r01) for _ in range(1000)]),
        "rust_s": C.timed(lambda: C.rust_eval(binary, [dict(base, fn="refuse_hollow_cathode_elements", config=FLIGHT,
                                                            elements=r01)] * 1000, work, "perf")),
        "note": "Rust timing includes process start and one definition load per call (eval interface)"}}
    p = perf["PERF-ARCH-01"]
    p["speedup"] = p["python_s"] / p["rust_s"] if p["rust_s"] else None
    ok = not failures and all(v["pass"] for v in invariants.values()) and not pinned_bad
    outcomes = {"RETURNED": sum(r["py"]["outcome"] == "RETURNED" for r in rows),
                "RAISED": sum(r["py"]["outcome"] == "RAISED" for r in rows)}
    return {
        "contract_sha256": C.sha_bytes(contract_bytes), "seed": seed, "mode": mode,
        "verdict": "ADMITTED" if ok else ("INPUT_MISMATCH" if pinned_bad else "NOT_ADMITTED"),
        "pinned_inputs_changed": pinned_bad,
        "calls": {"total": n + len(def_rows), "element_cases_registered": len(reg), "element_cases_random": len(rnd),
                  "configurations": len(ed["require_flight_configuration"]), "ground_reference": len(ed["ground_reference"]),
                  "verify_decision_records": len(vcases), "definition": len(def_rows), "python_outcomes": outcomes,
                  "refusals_architecture_rule": sum(r["py"].get("class") == "ArchitectureRuleError" for r in rows)},
        "definition": definition, "failures": failures, "invariants": invariants, "performance": perf,
        "element_cases_sha256": C.sha_file(work / "element_cases.json"),
        "rust_calls_sha256": C.sha_file(work / "calls_arch.json"),
        "python_reference_results": {"rows": rows, "definition": def_rows}, "wall_s": round(time.time() - t0, 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=["development", "score"], required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    res = run(a.mode, Path(a.work))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": res["verdict"], "failures": len(res.get("failures", [])), "calls": res.get("calls"),
                      "invariants": {k: v["pass"] for k, v in res.get("invariants", {}).items()},
                      "definition": res.get("definition")}, indent=1))
    for f in res.get("failures", [])[:40]:
        print(json.dumps(f, ensure_ascii=False)[:700])
    return 0 if res["verdict"] == "ADMITTED" else 1


if __name__ == "__main__":
    sys.exit(main())
