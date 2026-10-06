"""Parity campaign of contract C-ABEP_SIM_CONFIGURATION_PY v1 (configuration loaders + `abep config build --check`).

Python reference (abep_sim/configuration.py, scripts/config/build_config.py) vs the Rust CLI (`abep-config eval`,
`abep-config build --check`) on the preregistered case trees: deterministic loader cases L-D00..L-D62, environment
cases L-E01..L-E03, 240 seeded mutation cases L-S000..L-S239 and build cases B-00..B-22. Case trees are temporary;
the repository is never modified.

  python scripts/rust_migration/parity_config_v1.py --mode development --work DIR    development seed; no report
  python scripts/rust_migration/parity_config_v1.py --mode score --work DIR          scoring seed, ONCE; writes the report
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import random
import shutil
import subprocess
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_common as C  # noqa: E402

ROOT = C.ROOT
sys.path.insert(0, str(ROOT))
from abep_sim import configuration as cfg  # noqa: E402

CDIR = ROOT / "docs/rust_migration/contracts/C-ABEP_SIM_CONFIGURATION_PY"
CONTRACT = CDIR / "parity_prereg_v1.json"
A = "architecture/hall_icp_neutralizer_v1.json"
R = "requirements/rfp_constraints_v1.json"
CO = "constraints/engineering_constraints_v1.json"
M = "mission/mission_scenario_v2.json"
G = "assessment/gate_thresholds_v1.json"
D = "environment/design_state_set_ref_v1.json"
H = "hardware/hardware_bounds_v1.json"
S = "model_set/physics_model_set_v1.json"
MESSAGE_CLASSES = {"ConfigurationError", "BuildError"}


# ------------------------------------------------------------------------------------------------ mutations
def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def dump_doc(p: Path, doc) -> None:
    p.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def j_set(base: Path, rel: str, path: list, value) -> None:
    doc = load(base / rel)
    node = doc
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    dump_doc(base / rel, doc)


def j_del(base: Path, rel: str, path: list) -> None:
    doc = load(base / rel)
    node = doc
    for k in path[:-1]:
        node = node[k]
    del node[path[-1]]
    dump_doc(base / rel, doc)


def move_last(base: Path, rel: str, path: list, key: str) -> None:
    doc = load(base / rel)
    node = doc
    for k in path:
        node = node[k]
    node[key] = node.pop(key)
    dump_doc(base / rel, doc)


def space_before_newline(p: Path) -> None:
    b = p.read_bytes()
    p.write_bytes(b[:-1] + b" \n" if b.endswith(b"\n") else b + b" ")


def remanifest(c: Path) -> None:
    man = load(c / "MANIFEST.json")
    for rel in man["files"]:
        if (c / rel).is_file():
            b = (c / rel).read_bytes()
            man["files"][rel] = {"sha256": C.sha_bytes(b), "bytes": len(b)}
    (c / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")


def unlist(c: Path, rel: str) -> None:
    man = load(c / "MANIFEST.json")
    del man["files"][rel]
    (c / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")


def index_of(rel: str, key: str, path: str) -> int:
    doc = load(ROOT / "config" / rel)
    return next(i for i, e in enumerate(doc[key]) if e["path"] == path)


Z64 = "0" * 64
# id -> (note, list of (callable(c, repo) mutation), flags)
DET = {
    "L-D00": [],
    "L-D01": [lambda c, r: (c / "MANIFEST.json").unlink()],
    "L-D02": [lambda c, r: j_del(c, "MANIFEST.json", ["schema"])],
    "L-D03": [lambda c, r: j_set(c, "MANIFEST.json", ["files"], [])],
    "L-D04": [lambda c, r: (c / "MANIFEST.json").write_bytes((c / "MANIFEST.json").read_bytes()[:100])],
    "L-D05": [lambda c, r: j_del(c, "MANIFEST.json", ["files", A, "sha256"])],
    "L-D06": [lambda c, r: space_before_newline(c / A)],
    "L-D07": [lambda c, r: space_before_newline(c / CO)],
    "L-D08": [lambda c, r: space_before_newline(c / M)],
    "L-D09": [lambda c, r: unlist(c, G)],
    "L-D10": [lambda c, r: (c / D).unlink()],
    "L-D11": [lambda c, r: j_set(c, A, ["schema"], "abep_config_architecture_v0"), "remanifest"],
    "L-D12": [lambda c, r: j_set(c, R, ["snapshot_status"], "DRAFT"), "remanifest"],
    "L-D13": [lambda c, r: j_set(c, CO, ["set_status"], "X"), "remanifest"],
    "L-D14": [lambda c, r: j_set(c, CO, ["constraints", "thrust_sustained_min_mN", "status"], "X"), "remanifest"],
    "L-D15": [lambda c, r: j_del(c, CO, ["constraints", "firing_life_h"]), "remanifest"],
    "L-D16": [lambda c, r: j_set(c, CO, ["constraints", "altitude_band_km", "value"], [180]), "remanifest"],
    "L-D17": [lambda c, r: j_set(c, CO, ["constraints", "firing_life_h", "label"], "MISSION"), "remanifest"],
    "L-D18": [lambda c, r: j_set(c, CO, ["constraints", "mission_life_h", "g1_status"], "PENDING"), "remanifest"],
    "L-D19": [lambda c, r: j_set(c, CO, ["constraints", "ic_subsystem_min", "value", "pse"], "0.7"), "remanifest"],
    "L-D20": [lambda c, r: j_set(c, CO, ["constraints", "hall_preferred", "value"], 1), "remanifest"],
    "L-D21": [lambda c, r: j_del(c, CO, ["constraints", "propellant_capability", "value", "xe"]), "remanifest"],
    "L-D22": [lambda c, r: j_set(c, CO, ["constraints", "thrust_sustained_min_mN", "value"], "12"), "remanifest"],
    "L-D23": [lambda c, r: j_set(c, CO, ["constraints", "thrust_sustained_min_mN", "value"], True), "remanifest"],
    "L-D24": [lambda c, r: j_set(c, CO, ["id"], "engineering_constraints_v9"), "remanifest"],
    "L-D25": [lambda c, r: j_set(c, M, ["schema"], "abep_config_mission_scenario_v1"), "remanifest"],
    "L-D26": [lambda c, r: space_before_newline(c / M), "remanifest"],
    "L-D27": [lambda c, r: space_before_newline(c / M), "remanifest", "pin_override"],
    "L-D28": [lambda c, r: j_set(c, M, ["status"], "DRAFT"), "remanifest", "pin_override"],
    "L-D29": [lambda c, r: j_set(c, M, ["inputs", "mission_hours", "g1_status"], "PENDING"), "remanifest",
              "pin_override"],
    "L-D30": [lambda c, r: j_set(c, M, ["inputs", "firing_hours", "label"], "MISSION"), "remanifest", "pin_override"],
    "L-D31": [lambda c, r: j_set(c, M, ["inputs", "wet_mass_limit_kg"], {"value": 40}), "remanifest", "pin_override"],
    "L-D32": [lambda c, r: j_set(c, M, ["inputs", "xe_sizing_thrust_target_mN", "kind"], "CONSTRAINT_COPY"),
              "remanifest", "pin_override"],
    "L-D33": [lambda c, r: j_set(c, M, ["inputs", "commanded_thrust_cap_mN", "set_equal_to_constraint"], True),
              "remanifest", "pin_override"],
    "L-D34": [lambda c, r: j_del(c, M, ["inputs", "mission_hours", "historical_note"]), "remanifest", "pin_override"],
    "L-D35": [lambda c, r: j_set(c, M, ["inputs", "p_bus_throttling_cap_W", "value"], "1500"), "remanifest",
              "pin_override"],
    "L-D36": [lambda c, r: move_last(c, G, ["gates"], "HC-05"), "remanifest"],
    "L-D37": [lambda c, r: j_set(c, G, ["gates", "HC-07", "value"], 15000.0), "remanifest"],
    "L-D38": [lambda c, r: j_set(c, G, ["gates", "HC-09", "constraint_ref"], "no_such_constraint"), "remanifest"],
    "L-D39": [lambda c, r: j_set(c, G, ["gates", "HC-12", "value"], 1.0), "remanifest"],
    "L-D40": [lambda c, r: j_set(c, G, ["gates", "HC-06", "status"], "PROVISIONAL"), "remanifest"],
    "L-D41": [lambda c, r: j_set(c, G, ["gates", "HC-08", "kind"], "OTHER"), "remanifest"],
    "L-D42": [lambda c, r: j_set(c, G, ["gates", "HC-09", "scale_to_gate_units"], "1e-3"), "remanifest"],
    "L-D43": [lambda c, r: j_set(c, G, ["schema"], "x"), "remanifest"],
    "L-D44": [lambda c, r: j_set(c, D, ["sha256"], Z64), "remanifest"],
    "L-D45": [lambda c, r: j_set(c, D, ["manifest", "sha256"], Z64), "remanifest"],
    "L-D46": [lambda c, r: j_set(c, D, ["path"], "abep_sim/data/no_such_design_states.json"), "remanifest"],
    "L-D47": [lambda c, r: j_set(c, H, ["entries", 0, "sha256"], Z64), "remanifest"],
    "L-D48": [lambda c, r: j_set(c, H, ["entries", 1, "path"], "abep_sim/no_such_module.py"), "remanifest"],
    "L-D49": [lambda c, r: j_set(c, H, ["entries", 2, "kind"], "materials"), "remanifest"],
    "L-D50": [lambda c, r: j_set(c, S, ["schema"], "x"), "remanifest"],
    "L-D51": [lambda c, r: j_set(c, S, ["modules", index_of(S, "modules", "abep_sim/constants.py"), "sha256"], Z64),
              "remanifest"],
    "L-D52": [lambda c, r: j_set(c, S, ["data", 0, "path"], "abep_sim/data/no_such_golden.json"), "remanifest"],
    "L-D53": [lambda c, r: j_set(c, S, ["version_labels_flat", "arch_boundary.BOUNDARY_VERSION"], "changed"),
              "remanifest"],
    "L-D54": [("farm", "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json",
               lambda r: space_before_newline(r / "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json"))],
    "L-D55": [("farm", "abep_sim/rotor_strength.py", lambda r: (r / "abep_sim/rotor_strength.py").unlink())],
    "L-D56": [("farm", "abep_sim/constants.py",
               lambda r: (r / "abep_sim/constants.py").write_bytes((r / "abep_sim/constants.py").read_bytes()
                                                                   + b"# drift\n"))],
    "L-D57": [lambda c, r: (c / R).unlink()],
    "L-D58": [lambda c, r: (c / R).unlink(), lambda c, r: (c / CO).unlink(), lambda c, r: (c / G).unlink()],
    "L-D59": [lambda c, r: j_set(c, R, ["schema"], "x"), "remanifest"],
    "L-D60": [lambda c, r: (c / CO).write_bytes(b"\xff" + (c / CO).read_bytes()[1:]), "remanifest"],
    "L-D61": [lambda c, r: (c / CO).write_text(json.dumps([], indent=1) + "\n", encoding="utf-8"), "remanifest"],
    "L-D62": [lambda c, r: j_set(c, "MANIFEST.json", ["files", M], "x")],
}


def pool_value(expr: str):
    return eval(expr, {"__builtins__": {}}, {"float": float})  # noqa: S307 - registered literal pool


def node_paths(doc) -> list:
    out = []

    def walk(v, path):
        if isinstance(v, dict):
            for k, x in v.items():
                out.append(path + [k])
                walk(x, path + [k])
        elif isinstance(v, list):
            for i, x in enumerate(v):
                out.append(path + [i])
                walk(x, path + [i])
    walk(doc, [])
    return out


def seeded_cases(contract: dict, seed: int) -> list[dict]:
    rd = contract["inputs"]["randomized_domain"]
    rng = random.Random(seed)
    cases = []
    for k in range(rd["count"]):
        f = rng.choice(rd["TARGET_FILES"])
        doc = load(ROOT / "config" / f)
        p = rng.choice(node_paths(doc))
        op = rng.choice(["set", "set", "set", "delete"])
        value = rng.choice(rd["VALUE_POOL"]) if op == "set" else None
        rem = rng.random() < 0.9
        if f == "MANIFEST.json":
            rem = False
        pin = (f == M) and rng.random() < 0.5
        cases.append({"id": f"L-S{k:03d}", "file": f, "path": p, "op": op, "value": value, "remanifest": rem,
                      "pin_override": pin})
    return cases


# ------------------------------------------------------------------------------------------------ loader calls
def entry_points(ref_files: list[str]) -> list[tuple[str, dict]]:
    eps = [("load_manifest", {})]
    eps += [("load_verified", {"rel": r}) for r in ref_files + ["requirements/other.json"]]
    eps += [("load_architecture", {}), ("load_requirements_snapshot", {}), ("load_engineering_constraints_file", {}),
            ("load_engineering_constraints", {}), ("load_mission_scenario", {"verify_constraints": True}),
            ("load_mission_scenario", {"verify_constraints": False}), ("load_operating_inputs", {}),
            ("load_gate_thresholds", {}), ("load_design_state_set_ref", {"verify_target": True}),
            ("load_design_state_set_ref", {"verify_target": False}), ("load_hardware_bounds", {"verify_targets": True}),
            ("load_hardware_bounds", {"verify_targets": False}), ("load_model_set", {}), ("model_set_drift", {}),
            ("physics_configuration", {}), ("assessment_configuration", {})]
    return eps


def py_loader(name: str, kw: dict, root):
    fn = getattr(cfg, name)
    args = dict(kw)
    if name == "load_verified":
        return C.py_result(fn, args.pop("rel"), root)
    if name in ("physics_configuration", "assessment_configuration"):
        return C.py_result(lambda: fn(root).as_dict())
    return C.py_result(fn, root, **args)


class Case:
    def __init__(self, cid, config_root, repo, env=None, pin_sha=None, use_root=True):
        self.cid, self.config_root, self.repo, self.env, self.pin_sha, self.use_root = \
            cid, config_root, repo, env, pin_sha, use_root

    def run_python(self, eps):
        saved_repo, saved_pin = cfg.REPO_ROOT, dict(cfg.OPERATING_SCENARIO_PIN)
        saved_env = os.environ.get(cfg.CONFIG_ENV)
        try:
            cfg.REPO_ROOT = Path(self.repo)
            if self.pin_sha:
                cfg.OPERATING_SCENARIO_PIN["sha256"] = self.pin_sha
            if self.env is not None:
                os.environ[cfg.CONFIG_ENV] = self.env
            elif cfg.CONFIG_ENV in os.environ:
                del os.environ[cfg.CONFIG_ENV]
            root = Path(self.config_root) if self.use_root else None
            return [py_loader(n, kw, root) for n, kw in eps]
        finally:
            cfg.REPO_ROOT = saved_repo
            cfg.OPERATING_SCENARIO_PIN.clear()
            cfg.OPERATING_SCENARIO_PIN.update(saved_pin)
            if saved_env is None:
                os.environ.pop(cfg.CONFIG_ENV, None)
            else:
                os.environ[cfg.CONFIG_ENV] = saved_env

    def rust_calls(self, eps):
        base = {"repo": str(self.repo), "root": str(self.config_root) if self.use_root else None, "env": self.env,
                "pin_sha256": self.pin_sha}
        return [dict(base, fn=n, **kw) for n, kw in eps]


def build_loader_cases(work: Path, contract: dict, seed: int) -> tuple[list[Case], list[dict]]:
    cases = []
    for cid, muts in DET.items():
        d = work / cid
        c = d / "config"
        shutil.copytree(ROOT / "config", c)
        repo = ROOT
        flags = [m for m in muts if isinstance(m, str)]
        for m in muts:
            if isinstance(m, tuple):
                _, rel, fn = m
                repo = C.make_repo(d / "repo", {rel})
                fn(repo)
            elif callable(m):
                m(c, repo)
        if "remanifest" in flags:
            remanifest(c)
        pin = C.sha_file(c / M) if "pin_override" in flags else None
        cases.append(Case(cid, c, repo, pin_sha=pin))
    env_root = work / "L-E01" / "config"
    shutil.copytree(ROOT / "config", env_root)
    empty = work / "L-E03" / "no_manifest"
    empty.mkdir(parents=True)
    cases += [Case("L-E01", env_root, ROOT, env=str(env_root), use_root=False),
              Case("L-E02", ROOT / "config", ROOT, env="", use_root=False),
              Case("L-E03", empty, ROOT, env=str(empty), use_root=False)]
    seeded = seeded_cases(contract, seed)
    for sc in seeded:
        c = work / sc["id"] / "config"
        shutil.copytree(ROOT / "config", c)
        doc = load(c / sc["file"])
        node = doc
        for k in sc["path"][:-1]:
            node = node[k]
        if sc["op"] == "set":
            node[sc["path"][-1]] = pool_value(sc["value"])
        else:
            del node[sc["path"][-1]]
        dump_doc(c / sc["file"], doc)
        if sc["remanifest"]:
            remanifest(c)
        pin = C.sha_file(c / M) if sc["pin_override"] else None
        cases.append(Case(sc["id"], c, ROOT, pin_sha=pin))
    return cases, seeded


# ------------------------------------------------------------------------------------------------ build cases
def rvm_index(rid: str) -> int:
    doc = load(ROOT / "docs/requirements/rvm_a9/rvm_a9_v1.json")
    return next(i for i, r in enumerate(doc["rows"]) if r["id"] == rid)


def clause_index(cid: str) -> int:
    doc = load(ROOT / "docs/requirements/rfp_official/rfp_registration_v1.json")
    return next(i for i, c in enumerate(doc["clauses"]) if c["id"] == cid)


RVM = "docs/requirements/rvm_a9/rvm_a9_v1.json"
REG = "docs/requirements/rfp_official/rfp_registration_v1.json"


def build_cases(contract: dict) -> dict:
    label_module = contract["inputs"]["edge_cases"]["label_edge_module"]
    a919_md = "docs/decisions/OD_2026_10_01_A9_19_ARCHITECTURE_XE_CONTINGENCY_OWNER_DECISION.md"
    a920_json = "docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json"
    a9 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json"
    ds = "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json"

    def reg_text(r):
        i = clause_index("RFP-P19-01")
        j_set(r, REG, ["clauses", i, "text"], load(r / REG)["clauses"][i]["text"] + " ")

    def pinned(r):
        p = r / "hallthruster_bridge/PINNED.toml"
        t = p.read_text(encoding="utf-8")
        p.write_text(t.replace('version = "abep-n2n-0.11"', 'version = "abep-n2n-0.12"', 1), encoding="utf-8")

    return {
        "B-00": (set(), []),
        "B-01": (set(), [lambda r: space_before_newline(r / "config" / A)]),
        "B-02": (set(), [lambda r: ((r / "config/extra").mkdir(), (r / "config/extra/unlisted.json").write_text("{}\n"))]),
        "B-03": (set(), [lambda r: (r / "config" / H).unlink()]),
        "B-04": (set(), [lambda r: space_before_newline(r / "config" / M)]),
        "B-05": (set(), [lambda r: space_before_newline(r / "config/mission/mission_scenario_v1.json")]),
        "B-06": (set(), [lambda r: (r / "config" / M).unlink()]),
        "B-07": ({a919_md}, [lambda r: (r / a919_md).write_bytes((r / a919_md).read_bytes() + b" ")]),
        "B-08": ({a920_json}, [lambda r: space_before_newline(r / a920_json)]),
        "B-09": ({REG}, [reg_text]),
        "B-10": ({RVM}, [lambda r: j_set(r, RVM, ["rows", rvm_index("RVM-01"), "key"], "ALT_ENVELOPE")]),
        "B-11": ({RVM}, [lambda r: j_set(r, RVM, ["rows", rvm_index("RVM-02"), "limit", "value"], 13)]),
        "B-12": ({RVM}, [lambda r: j_set(r, RVM, ["rows", rvm_index("RVM-01"), "verification_note"], "edited (B-12)")]),
        "B-13": ({RVM}, [lambda r: j_del(r, RVM, ["rows", rvm_index("RVM-04"), "limit"])]),
        "B-14": ({"abep_sim/constants.py"}, [lambda r: (r / "abep_sim/constants.py").write_bytes(
            (r / "abep_sim/constants.py").read_bytes() + b"# drift\n")]),
        "B-15": ({"abep_sim/zz_labels.py"}, [lambda r: (r / "abep_sim/zz_labels.py").write_text(label_module,
                                                                                                  encoding="utf-8")]),
        "B-16": ({"abep_sim/data/rates/zz_new.dat"}, [lambda r: (r / "abep_sim/data/rates/zz_new.dat").write_text("1 2\n")]),
        "B-17": ({"abep_sim/rotor_strength.py"}, [lambda r: (r / "abep_sim/rotor_strength.py").unlink()]),
        "B-18": ({ds}, [lambda r: space_before_newline(r / ds)]),
        "B-19": ({"schemas/results/raw_closure_v2.json"}, [lambda r: (r / "schemas/results/raw_closure_v2.json").unlink()]),
        "B-20": ({"hallthruster_bridge/PINNED.toml"}, [pinned]),
        "B-21": ({"abep_sim/notes.txt", "abep_sim/zz.PY"},
                 [lambda r: ((r / "abep_sim/notes.txt").write_text("x\n"),
                             (r / "abep_sim/zz.PY").write_text('ZZ_VERSION = "no"\n'))]),
        "B-22": ({a9}, [lambda r: space_before_newline(r / a9)]),
    }


def py_builder(repo: Path):
    spec = importlib.util.spec_from_file_location("abep_build_config_parity", ROOT / "scripts/config/build_config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT, mod.CONFIG = Path(repo), Path(repo) / "config"
    return mod


def py_build(repo: Path) -> tuple[dict, dict]:
    mod = py_builder(repo)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        files = C.py_result(lambda: {k: {"sha256": C.sha_bytes(v), "bytes": len(v)} for k, v in mod.build_all().items()})

        def check():
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = mod.main(["--check"])
            return {"exit": rc, "line": buf.getvalue().strip()}
        chk = C.py_result(check)
    return files, chk


# ------------------------------------------------------------------------------------------------ campaign
def run(mode: str, work: Path) -> dict:
    contract_bytes = CONTRACT.read_bytes()
    contract = json.loads(contract_bytes)
    ref = contract["reference_implementation"]
    changed = [f["path"] for f in ref["files"] if C.sha_file(ROOT / f["path"]) != f["sha256_at_registration"]]
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

    # loaders
    ref_files = list(load(ROOT / "config/MANIFEST.json")["files"])
    eps = entry_points(ref_files)
    cases, seeded = build_loader_cases(work, contract, seed)
    (work / "seeded_cases.json").write_text(json.dumps(seeded, indent=1) + "\n", encoding="utf-8")
    py_results, py_again, calls, index = {}, {}, [], []
    for case in cases:
        py_results[case.cid] = case.run_python(eps)
        py_again[case.cid] = case.run_python(eps)
        for (n, kw), call in zip(eps, case.rust_calls(eps)):
            calls.append(call)
            index.append((case.cid, n, kw))
    rust, rust_bytes = C.rust_eval(binary, calls, work, "loaders")
    _, rust_bytes2 = C.rust_eval(binary, calls, work, "loaders_again")
    loader_fail, n_calls, outcomes = [], 0, {"RETURNED": 0, "RAISED": 0}
    per_class = {}
    for i, (cid, n, kw) in enumerate(index):
        py = py_results[cid][i % len(eps)]
        rs = rust[i]
        n_calls += 1
        outcomes[py["outcome"]] += 1
        if py["outcome"] == "RAISED":
            per_class[py["class"]] = per_class.get(py["class"], 0) + 1
        diff = C.compare(py, rs, MESSAGE_CLASSES)
        if diff:
            loader_fail.append({"case": cid, "entry": n, "args": kw, "diff": diff})
    py_det = all(C.canon(py_results[c]) == C.canon(py_again[c]) for c in py_results)

    # build
    build_fail, build_rows = [], []
    bcalls, bindex, py_build_res = [], [], {}
    for bid, (edits, muts) in build_cases(contract).items():
        repo = C.make_repo(work / bid / "repo", set(edits))
        for m in muts:
            m(repo)
        py_build_res[bid] = py_build(repo)
        bcalls += [{"fn": "build_all", "repo": str(repo)}, {"fn": "build_check", "repo": str(repo)}]
        bindex.append(bid)
    brust, brust_bytes = C.rust_eval(binary, bcalls, work, "build")
    _, brust_bytes2 = C.rust_eval(binary, bcalls, work, "build_again")
    for i, bid in enumerate(bindex):
        pf, pc = py_build_res[bid]
        rf, rc = brust[2 * i], brust[2 * i + 1]
        d = C.compare(pf, rf, MESSAGE_CLASSES) + C.compare(pc, rc, MESSAGE_CLASSES)
        build_rows.append({"case": bid, "python_files": pf.get("outcome"), "python_check": pc.get("value") or
                           {"class": pc.get("class")}, "parity": not d})
        if d:
            build_fail.append({"case": bid, "diff": d})

    # W13: the repository tree itself
    w13 = subprocess.run([str(binary), "build", "--check", "--repo", str(ROOT)], capture_output=True, text=True)
    committed = {k: {"sha256": C.sha_file(ROOT / "config" / k), "bytes": (ROOT / "config" / k).stat().st_size}
                 for k in brust[0]["value"]} if brust[0]["outcome"] == "RETURNED" else {}
    w13_ok = (w13.returncode == 0 and w13.stdout.strip() == "OK: 12 config files current"
              and brust[0]["outcome"] == "RETURNED" and C.canon(brust[0]["value"]) == C.canon(committed)
              and sorted(committed) == sorted(p.relative_to(ROOT / "config").as_posix()
                                              for p in (ROOT / "config").rglob("*") if p.is_file()))

    # invariants
    pyb = py_builder(ROOT)
    const_call = [{"fn": "builder_constants", "repo": str(ROOT)}]
    rconst = C.rust_eval(binary, const_call, work, "constants")[0][0]["value"]
    py_const = {"OPERATING_SCENARIO_PIN": pyb._code_pin("OPERATING_SCENARIO_PIN"), "DECISIONS": pyb.DECISIONS,
                "VERBATIM_A9_19": pyb.VERBATIM_A9_19, "MISSION_V1_SHA256": pyb.MISSION_V1_SHA256,
                "SNAPSHOT_RVM_SHA256": pyb.SNAPSHOT_RVM_SHA256, "ACCEPTED_RVM_BASIS_SHA256": pyb.ACCEPTED_RVM_BASIS_SHA256,
                "HW_ENTRIES": [list(e) for e in pyb.HW_ENTRIES], "DATA_FILES": pyb.DATA_FILES,
                "RESULT_SCHEMAS": pyb.RESULT_SCHEMAS,
                "FILES": [pyb.ARCH_FILE, pyb.REQ_FILE, pyb.CONSTRAINTS_FILE, pyb.MISSION_FILE, pyb.MISSION_V1_FILE,
                          pyb.GATES_FILE, pyb.DS_REF_FILE, pyb.HW_FILE, pyb.MODEL_SET_FILE, pyb.SOT_FILE],
                "GENERATED_BY": pyb.GENERATED_BY, "REGENERATE": pyb.REGENERATE, "README": pyb.README}
    inv03 = C.canon(py_const["OPERATING_SCENARIO_PIN"]) == C.canon(rconst["OPERATING_SCENARIO_PIN"]) \
        and C.canon(cfg.OPERATING_SCENARIO_PIN) == C.canon(rconst["OPERATING_SCENARIO_PIN"])
    inv04 = all(C.canon(py_const[k]) == C.canon(rconst[k]) for k in py_const if k != "OPERATING_SCENARIO_PIN")

    pos = {c.cid: i for i, c in enumerate(cases)}

    def rust_at(cid, name):
        return rust[pos[cid] * len(eps) + [n for n, _ in eps].index(name)]

    def ret(cid, name):
        k = [n for n, _ in eps].index(name)
        return py_results[cid][k]["outcome"] == "RETURNED" and rust_at(cid, name)["outcome"] == "RETURNED"
    inv02 = ret("L-D58", "load_operating_inputs") and ret("L-D57", "physics_configuration") \
        and ret("L-D57", "load_operating_inputs")

    def verdict_strings(v):
        if isinstance(v, dict):
            return any(verdict_strings(x) for x in v.values())
        if isinstance(v, list):
            return any(verdict_strings(x) for x in v)
        return isinstance(v, str) and v in ("PASS", "FAIL", "PASSED", "FAILED")
    computed = {"load_engineering_constraints", "load_operating_inputs", "load_gate_thresholds",
                "physics_configuration", "assessment_configuration"}
    inv05 = not any(verdict_strings(rust_at("L-D00", n).get("value")) for n in computed)
    gov = contract["governing_hashes"]
    l00 = rust_at("L-D00", "physics_configuration")["value"]
    governing_ok = (l00["architecture_sha256"] == gov["architecture_hash"] and l00["model_set_sha256"] ==
                    gov["model_set_hash"] and l00["design_state_set_sha256"] == gov["design_state_set_hash"] and
                    l00["config_manifest_sha256"] == gov["config_manifest"]["sha256"])
    invariants = {
        "INV-01": {"pass": rust_bytes == rust_bytes2 and brust_bytes == brust_bytes2 and py_det,
                   "detail": "Rust eval twice byte-identical (loaders, build); Python results twice identical"},
        "INV-02": {"pass": inv02, "detail": "L-D58 load_operating_inputs and L-D57 physics_configuration RETURNED in "
                                            "both implementations"},
        "INV-03": {"pass": inv03, "detail": "Rust scenario pin == ast.literal_eval(configuration.OPERATING_SCENARIO_PIN)"},
        "INV-04": {"pass": inv04, "detail": "Rust builder constants (decision pins, scenario v1 pin, RVM pins, HW_ENTRIES, "
                                            "DATA_FILES, RESULT_SCHEMAS, file names, README) == Python builder constants"},
        "INV-05": {"pass": inv05, "detail": "no string value PASS / FAIL / PASSED / FAILED in the computed loader outputs "
                                            "on the reference tree (verdict-free loaders)"},
    }

    # performance (reported only)
    def py_check():
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
            warnings.simplefilter("ignore")
            py_builder(ROOT).main(["--check"])
    perf = {
        "PERF-CFG-01": {"python_s": C.timed(py_check),
                        "rust_s": C.timed(lambda: subprocess.run([str(binary), "build", "--check", "--repo", str(ROOT)],
                                                                 capture_output=True))},
        "PERF-CFG-02": {"python_s": C.timed(lambda: cfg.physics_configuration()),
                        "rust_s": C.timed(lambda: C.rust_eval(binary, [{"fn": "physics_configuration",
                                                                        "repo": str(ROOT)}], work, "perf"))},
    }
    for v in perf.values():
        v["speedup"] = v["python_s"] / v["rust_s"] if v["rust_s"] else None

    ok = not loader_fail and not build_fail and w13_ok and all(v["pass"] for v in invariants.values()) \
        and not pinned_bad and governing_ok
    verdict = "ADMITTED" if ok else ("INPUT_MISMATCH" if (pinned_bad or not governing_ok) else "NOT_ADMITTED")
    return {
        "contract_sha256": C.sha_bytes(contract_bytes), "seed": seed, "mode": mode, "verdict": verdict,
        "pinned_inputs_changed": pinned_bad, "governing_hashes_reported": {k: l00[k] for k in (
            "architecture_sha256", "model_set_sha256", "design_state_set_sha256", "config_manifest_sha256")},
        "governing_hashes_match": governing_ok,
        "loaders": {"cases": len(cases), "entry_points_per_case": len(eps), "calls": n_calls, "outcomes": outcomes,
                    "python_exception_classes": dict(sorted(per_class.items())), "failures": loader_fail},
        "build": {"cases": len(bindex), "rows": build_rows, "failures": build_fail},
        "w13": {"pass": w13_ok, "exit": w13.returncode, "line": w13.stdout.strip()},
        "invariants": invariants, "performance": perf, "seeded_cases_sha256": C.sha_file(work / "seeded_cases.json"),
        "python_reference_results": {"loaders": py_results, "build": py_build_res},
        "rust_calls_sha256": C.sha_file(work / "calls_loaders.json"), "rust_build_calls_sha256":
            C.sha_file(work / "calls_build.json"), "wall_s": round(time.time() - t0, 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=["development", "score"], required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", default=None, help="score mode: where to write the raw campaign result (JSON)")
    a = ap.parse_args(argv)
    res = run(a.mode, Path(a.work))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    lf = res.get("loaders", {}).get("failures", [])
    bf = res.get("build", {}).get("failures", [])
    print(json.dumps({"verdict": res["verdict"], "loader_failures": len(lf), "build_failures": len(bf),
                      "w13": res.get("w13"), "invariants": {k: v["pass"] for k, v in res.get("invariants", {}).items()},
                      "calls": res.get("loaders", {}).get("calls")}, indent=1))
    for f in (lf + bf)[:40]:
        print(json.dumps(f)[:600])
    return 0 if res["verdict"] == "ADMITTED" else 1


if __name__ == "__main__":
    sys.exit(main())
