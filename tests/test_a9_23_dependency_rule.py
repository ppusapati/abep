"""A9.23 simulation architecture (owner directive 2026-10-03, docs/decisions/OD_2026_10_03_A9_23_*): dependency rule.

    requirements / provenance                         -> frozen engineering constraints
    architecture + frozen constraints + design states + physics -> raw results
    raw results + frozen constraints                  -> assessment / compliance

Checks
  sot   config/SOURCES_OF_TRUTH.json: exactly one authoritative artefact per role; each exists and matches its pin; no
        second file claims a listed role; the raw / assessment result schemas match the actual outputs.
  (a)   physics modules (abep_sim/** except abep_sim/assessment/** and the configuration loader) never reference the
        requirements snapshot / its loaders, never import (module level, transitively) a module that does, and run /
        import with config/requirements and docs/requirements hidden.
  (b)   changing a frozen constraint threshold (P_bus limit, sustained-thrust floor, temp config copy) changes the
        assessment, raw physics stays byte-identical and the operating scenario (file and values) is untouched
        (A9.24 item 4); an edited operating scenario is refused unless it is a new pinned version.
  (c)   changing a physics model parameter changes raw physics; the requirements snapshot and the engineering
        constraints (files, builder output and loaded values) are untouched.
  (d)   swapping the design-state set reference does not rewrite the architecture artefact or its loaded values.
  (e)   requirements snapshot -> engineering constraints is the only derivation path (builder regenerates them from
        the snapshot; constraints carry the snapshot sha256; no other writer).
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from abep_sim import configuration as cfg

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
SOT = CONFIG / cfg.SOURCES_OF_TRUTH_REL
ROLES = ("frozen_architecture", "frozen_engineering_constraints", "frozen_design_state_set", "physics_model_set",
         "raw_simulation_result", "assessment_result", "requirements_provenance")


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _builder():
    spec = importlib.util.spec_from_file_location("abep_build_config_a923", ROOT / "scripts/config/build_config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _remanifest(root: Path):
    man = _json(root / cfg.MANIFEST_REL)
    for rel in man["files"]:
        b = (root / rel).read_bytes()
        man["files"][rel] = {"sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
    (root / cfg.MANIFEST_REL).write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")


def _edit_constraint(root: Path, cid: str, value):
    """Change one frozen constraint value in a config copy and refresh the manifest, as a rebuild of the pins would.
    A9.24 item 4: the operating scenario does not pin the constraints and is not touched."""
    p = root / cfg.CONSTRAINTS_REL
    d = _json(p)
    d["constraints"][cid]["value"] = value
    p.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
    _remanifest(root)


@pytest.fixture()
def cfg_copy(tmp_path):
    dst = tmp_path / "config"
    shutil.copytree(CONFIG, dst)
    return dst


# ============================================================================================ source-of-truth index
def test_sources_of_truth_one_artefact_per_role_and_pins_match():
    sot = cfg.load_verified(cfg.SOURCES_OF_TRUTH_REL)
    assert sot["schema"] == "abep_sources_of_truth_v1"
    src = sot["sources"]
    assert tuple(src) == ROLES
    paths = [e["artefact"] for e in src.values()]
    assert len(set(paths)) == len(paths), "one artefact may hold only one role"
    man = cfg.load_manifest()["files"]
    for role, e in src.items():
        p = ROOT / e["artefact"]
        assert p.is_file(), (role, e["artefact"])
        assert _sha(p) == e["sha256"], role
        if e["artefact"].startswith("config/"):
            rel = e["artefact"][len("config/"):]
            assert man[rel]["sha256"] == e["sha256"], role                      # pinned by config/MANIFEST.json
        else:
            assert e["pinned_by"], role
    # role -> exact artefact (the owner's list; A9.23)
    assert src["frozen_architecture"]["artefact"] == "config/architecture/hall_icp_neutralizer_v1.json"
    assert src["frozen_engineering_constraints"]["artefact"] == "config/constraints/engineering_constraints_v1.json"
    assert src["physics_model_set"]["artefact"] == "config/model_set/physics_model_set_v1.json"
    assert src["raw_simulation_result"]["artefact"] == "schemas/results/raw_closure_v2.json"
    assert src["assessment_result"]["artefact"] == "schemas/results/closure_assessment_v2.json"
    assert src["requirements_provenance"]["artefact"] == "config/requirements/rfp_constraints_v1.json"
    assert src["requirements_provenance"]["layer"] == "PROVENANCE"
    # design states: the data file via the config reference, pinned by the dataset manifest and the reference
    ds = src["frozen_design_state_set"]
    ref = cfg.load_design_state_set_ref()
    assert ds["artefact"] == ref["path"] == "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json"
    assert ds["alias"] == "vleo_design_states_v2" and ds["id"] == ref["id"]
    assert ds["reference"] == "config/" + cfg.DESIGN_STATE_REF_REL
    assert ds["reference_sha256"] == man[cfg.DESIGN_STATE_REF_REL]["sha256"]
    dm = _json(ROOT / ref["manifest"]["path"])
    assert dm["design_states_file_v2"]["sha256"] == ds["sha256"] == ref["sha256"]
    # result schemas: their $id is the version constant of the producer
    from abep_sim import system
    from abep_sim.assessment import closure_checks as cc
    assert src["raw_simulation_result"]["id"] == system.RAW_CLOSURE_SCHEMA_VERSION == "raw_closure_v2"
    assert src["assessment_result"]["id"] == cc.ASSESSMENT_SCHEMA_VERSION == "closure_assessment_v2"


def _claims(path: Path):
    """(schema identifier, artefact id) a JSON file claims, or None."""
    try:
        d = _json(path)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(d, dict):
        return None
    return d.get("schema") or d.get("$schema"), d.get("id") or d.get("$id") or d.get("design_state_set_id")


def test_no_second_file_claims_a_listed_role():
    src = cfg.load_verified(cfg.SOURCES_OF_TRUTH_REL)["sources"]
    scan = [p for d in ("config", "schemas") for p in (ROOT / d).rglob("*.json")] + \
        list((ROOT / "abep_sim" / "data").glob("*.json"))
    for role, e in src.items():
        listed = {(ROOT / e["artefact"]).resolve()}
        if e.get("reference"):                             # the declared reference (design states) is not a copy
            listed.add((ROOT / e["reference"]).resolve())
        for p in scan:
            if p.resolve() in listed:
                continue
            c = _claims(p)
            if c is None:
                continue
            schema, ident = c
            assert ident != e["id"], f"{p.relative_to(ROOT)} claims id {ident!r} of role {role}"
            if e["artefact"].startswith("config/"):        # config schema identifiers are role-specific
                assert schema != e["schema"], f"{p.relative_to(ROOT)} claims schema {schema!r} of role {role}"
    # exactly one engineering-constraints file, one architecture file, one requirements snapshot under config/
    for sub in ("constraints", "architecture", "requirements", "model_set"):
        assert len(list((CONFIG / sub).glob("*.json"))) == 1, sub


def test_readme_names_the_sources_of_truth():
    txt = (CONFIG / "README.md").read_text(encoding="utf-8")
    assert "## Sources of truth (A9.23)" in txt
    for e in cfg.load_verified(cfg.SOURCES_OF_TRUTH_REL)["sources"].values():
        assert e["artefact"] in txt, e["artefact"]


# --------------------------------------------------------------------------------------------- result schemas
def _jtype(v):
    return ("null" if v is None else "boolean" if isinstance(v, bool) else "number" if isinstance(v, (int, float))
            else "string" if isinstance(v, str) else "array" if isinstance(v, (list, tuple)) else "object")


def _conforms(rec: dict, schema: dict):
    props = schema["properties"]
    assert set(schema["required"]) <= set(rec), sorted(set(schema["required"]) - set(rec))
    assert set(rec) <= set(props), sorted(set(rec) - set(props))
    for k, v in rec.items():
        p = props[k]
        if "const" in p:
            assert v == p["const"], k
        else:
            t = p["type"] if isinstance(p["type"], list) else [p["type"]]
            assert _jtype(v) in t, (k, _jtype(v), t)


def _parametric_cfg():
    from abep_sim.intake import IntakeParams, CompressorParams
    from abep_sim.system import Config
    return Config("hall_1stage", 200, "mean", IntakeParams(area_m2=1.5), CompressorParams(ratio=500), vd_V=250)


def test_result_schemas_match_actual_outputs():
    from abep_sim.system import physics_closure
    from abep_sim.assessment import assess, constraints_from_config, priors_from_config
    from abep_sim.assessment import FORBIDDEN_RAW_PREFIXES, FORBIDDEN_RAW_KEYS
    raw_s = _json(ROOT / "schemas/results/raw_closure_v2.json")
    as_s = _json(ROOT / "schemas/results/closure_assessment_v2.json")
    c = _parametric_cfg()
    raw = physics_closure(c)
    _conforms(raw, raw_s)
    assert set(raw) == set(raw_s["required"])            # the parametric path is the schema's base key set
    _conforms(assess(raw, constraints_from_config(c), priors_from_config(c)), as_s)
    assert not [k for k in raw_s["properties"] if k.startswith(FORBIDDEN_RAW_PREFIXES) or k in FORBIDDEN_RAW_KEYS]
    groups = raw_s["x-abep"]["path_conditional_keys"]
    assert list(groups) == ["gaspath_physics", "plasma_physics", "engineering_physics"]
    assert all(set(raw_s["required"]).isdisjoint(v) for v in groups.values())
    assert set(raw_s["required"]).union(*groups.values()) == set(raw_s["properties"])
    assert as_s["x-abep"]["path_conditional_keys"] == {"engineering_physics": ["chk_thermal"]}


# ============================================================================================ (a) physics never reads requirements
REQ_TOKENS = ("config/requirements", "requirements/rfp_constraints", "rfp_constraints_v1", "load_requirements_snapshot",
              "load_rfp_constraints_compat", "assessment_configuration", "REQUIREMENTS_REL")


def _physics_modules():
    for p in sorted((ROOT / "abep_sim").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("abep_sim/assessment/") or rel == "abep_sim/configuration.py":
            continue
        yield rel, p


def _uses_requirement_tokens(tree) -> list[int]:
    """Lines where a requirement-snapshot path / loader is used as code (names, attributes, strings outside
    docstrings / comments)."""
    doc_nodes = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body and \
                isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            doc_nodes.add(id(n.body[0].value))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id in REQ_TOKENS or isinstance(n, ast.Attribute) and n.attr in REQ_TOKENS:
            out.append(n.lineno)
        elif isinstance(n, ast.alias) and n.name in REQ_TOKENS:
            out.append(getattr(n, "lineno", 0))
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc_nodes and \
                any(t in n.value for t in REQ_TOKENS):
            out.append(n.lineno)
    return out


def test_physics_modules_never_reference_the_requirements_snapshot():
    bad = []
    for rel, p in _physics_modules():
        bad += [f"{rel}:{ln}" for ln in _uses_requirement_tokens(ast.parse(p.read_text(encoding="utf-8")))]
    assert not bad, f"physics / design module references the requirements snapshot or its loaders: {bad}"


def test_the_token_check_is_effective():
    tree = ast.parse('"""docstring mentions config/requirements/ freely"""\n'
                     'from abep_sim.configuration import load_requirements_snapshot\n'
                     'x = cfg.load_rfp_constraints_compat()\nP = "config/requirements/rfp_constraints_v1.json"\n')
    assert sorted(set(_uses_requirement_tokens(tree))) == [2, 3, 4]


def _module_name(rel: str) -> str:
    return rel[:-3].replace("/", ".").removesuffix(".__init__")


def _toplevel_imports(rel: str, tree) -> set[str]:
    """abep_sim modules imported at module level (executed on import), resolved to module names."""
    pkg = _module_name(rel).split(".")
    if not rel.endswith("__init__.py"):
        pkg = pkg[:-1]
    out = set()
    for n in tree.body:
        nodes = [n] + ([x for x in ast.walk(n) if isinstance(x, (ast.Import, ast.ImportFrom))]
                       if isinstance(n, (ast.If, ast.Try)) else [])
        for x in nodes:
            if isinstance(x, ast.Import):
                out |= {a.name for a in x.names if a.name.startswith("abep_sim")}
            elif isinstance(x, ast.ImportFrom):
                base = x.module or ""
                if x.level:
                    base = ".".join(pkg[: len(pkg) - (x.level - 1)] + ([x.module] if x.module else []))
                if base.startswith("abep_sim"):
                    out.add(base)
                    out |= {f"{base}.{a.name}" for a in x.names}
    return out


def test_physics_modules_do_not_import_modules_that_read_requirements():
    """Module-level import closure: no physics module pulls in abep_sim.assessment (which may read the requirements
    snapshot for compliance mapping), except the pre-existing compatibility / runner shims frozen in
    tests/test_layer_separation_physics.py ASSESSMENT_IMPORT_ALLOWLIST / PROGRAMME_IMPORT_ALLOWLIST (module-level
    entries only). abep_sim/programme/** is the runner layer (it may import the assessment layer) and is not checked as
    a physics module; a physics module reaching it at module level is caught unless it is a listed edge."""
    from tests.test_layer_separation_physics import ASSESSMENT_IMPORT_ALLOWLIST, PROGRAMME_IMPORT_ALLOWLIST
    shims = {rel for (rel, fn, _m) in {**ASSESSMENT_IMPORT_ALLOWLIST, **PROGRAMME_IMPORT_ALLOWLIST}
             if fn in ("<module>", "*")}
    mods = {}
    for rel, p in [(r.relative_to(ROOT).as_posix(), r) for r in sorted((ROOT / "abep_sim").rglob("*.py"))]:
        mods[_module_name(rel)] = (rel, _toplevel_imports(rel, ast.parse(p.read_text(encoding="utf-8"))))
    reads_req = {m for m in mods if m.startswith("abep_sim.assessment")}
    bad = []
    for name, (rel, _) in mods.items():
        if name in reads_req or rel == "abep_sim/configuration.py" or rel in shims or \
                rel.startswith("abep_sim/programme/"):
            continue
        seen, stack = set(), [name]
        while stack:
            m = stack.pop()
            if m in seen or m not in mods:
                continue
            seen.add(m)
            if mods[m][0] in shims:
                continue
            stack += [x for x in mods[m][1] if x in mods]
        hit = sorted(seen & reads_req)
        if hit:
            bad.append(f"{rel} -> {hit[0]}")
    assert not bad, f"physics module imports (transitively, at module level) the assessment layer: {bad}"


RUNTIME = r'''
import importlib, importlib.abc, json, os, pkgutil, sys
sys.path.insert(0, sys.argv[1])
BAD = ("/docs/requirements/", "/config/requirements/")
def hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.fsdecode(args[0]).replace(os.sep, "/")
        if any(b in p for b in BAD):
            raise PermissionError(f"physics layer opened {p}")
sys.addaudithook(hook)
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "abep_sim.assessment" or name.startswith("abep_sim.assessment."):
            raise ImportError(f"physics layer imported {name}")
sys.meta_path.insert(0, Block())
SKIP = set(json.loads(sys.argv[2]))
import abep_sim
from abep_sim import configuration as cfg
names = []
for m in pkgutil.walk_packages(abep_sim.__path__, "abep_sim."):
    if m.name.startswith("abep_sim.assessment") or m.name.endswith("__main__") or m.name in SKIP:
        continue
    names.append(m.name)
failed = {}
for n in names:
    try:
        importlib.import_module(n)
    except Exception as e:
        failed[n] = f"{type(e).__name__}: {e}"
from abep_sim import operating_inputs as OI
from abep_sim.design import engineering_constraints as ec
from abep_sim.intake import IntakeParams, CompressorParams
from abep_sim.system import Config, physics_closure
r = physics_closure(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=1.5), CompressorParams(ratio=500), vd_V=250))
pc = cfg.physics_configuration()
print(json.dumps({"n": len(names), "failed": failed, "oi": OI.as_dict()["P_bus_max_W"], "ec": ec.P_BUS_MAX_W,
                  "drag": ec.INTAKE_DRAG_GENERATION_LIMIT_N, "alt": list(ec.MISSION_DOMAIN_ALTITUDE_KM),
                  "schema": r["raw_schema_version"], "req": pc.requirements_snapshot_id,
                  "ecid": pc.engineering_constraints_id}))
'''


def test_physics_and_design_seams_run_with_requirements_hidden(tmp_path):
    """Runtime: every abep_sim module (physics + design; the assessment layer and the module-level compatibility /
    runner shims excepted) imports, both seams load and the raw closure runs with config/requirements removed,
    docs/requirements unreadable and abep_sim.assessment unimportable."""
    from tests.test_layer_separation_physics import ASSESSMENT_IMPORT_ALLOWLIST, PROGRAMME_IMPORT_ALLOWLIST
    shims = sorted({_module_name(rel) for (rel, fn, _m) in {**ASSESSMENT_IMPORT_ALLOWLIST, **PROGRAMME_IMPORT_ALLOWLIST}
                    if fn in ("<module>",)}
                   # the programme-runner layer may import the assessment layer at module level (A9.22 programme split)
                   | {_module_name(r.relative_to(ROOT).as_posix()) for r in (ROOT / "abep_sim" / "programme").glob("*.py")})
    root = tmp_path / "config"
    shutil.copytree(CONFIG, root)
    shutil.rmtree(root / "requirements")
    script = tmp_path / "probe.py"
    script.write_text(RUNTIME, encoding="utf-8")
    env = {**os.environ, "ABEP_CONFIG_ROOT": str(root), "MPLBACKEND": "Agg"}
    res = subprocess.run([sys.executable, str(script), str(ROOT), json.dumps(shims)], cwd=tmp_path, env=env,
                         capture_output=True, text=True, timeout=900)
    assert res.returncode == 0, res.stderr[-3000:]
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert out["n"] > 60 and out["failed"] == {}, out["failed"]
    assert (out["oi"], out["ec"], out["drag"], out["alt"]) == (1500.0, 1500.0, 0.025, [180.0, 230.0])
    assert out["schema"] == "raw_closure_v2" and out["req"] is None and out["ecid"] == "engineering_constraints_v1"


# ============================================================================================ (b) threshold -> assessment only
ASSESS_RUN = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from abep_sim.intake import IntakeParams, CompressorParams
from abep_sim.system import Config, physics_closure
from abep_sim.assessment import assess, constraints_from_config, priors_from_config
from abep_sim.assessment import design_gates as dg
from abep_sim import operating_inputs as OI
c = Config("hall_1stage", 200, "mean", IntakeParams(area_m2=1.5), CompressorParams(ratio=500), vd_V=250)
raw = physics_closure(c)
a = assess(raw, constraints_from_config(c), priors_from_config(c))
print(json.dumps({"raw": json.dumps(raw, sort_keys=True), "assess": a, "oi": OI.as_dict(),
                  "gate_limits": dg.HARD_CONSTRAINT_LIMITS}))
'''


def _run_closure_and_assessment(tmp_path, root: Path) -> dict:
    script = tmp_path / "assess_run.py"
    script.write_text(ASSESS_RUN, encoding="utf-8")
    env = {**os.environ, "ABEP_CONFIG_ROOT": str(root), "MPLBACKEND": "Agg"}
    res = subprocess.run([sys.executable, str(script), str(ROOT)], cwd=tmp_path, env=env, capture_output=True,
                         text=True, timeout=900)
    assert res.returncode == 0, res.stderr[-3000:]
    return json.loads(res.stdout.strip().splitlines()[-1])


def test_constraint_threshold_changes_assessment_not_raw_physics(tmp_path, cfg_copy):
    base = _run_closure_and_assessment(tmp_path, CONFIG)
    raw = json.loads(base["raw"])
    a0 = base["assess"]
    margin = a0["constraints"]["p_margin_frac"]
    # pick a P_bus limit that flips the power checks (no knowledge of the answer is assumed)
    p_cap_needed = raw["P_total_air_W"] / (1 - margin)
    new_limit = round(p_cap_needed * (0.5 if a0["chk_power_air"] else 2.0), 3)
    _edit_constraint(cfg_copy, "p_bus_max_W", new_limit)
    shutil.rmtree(cfg_copy / "requirements")          # the threshold path needs no requirements snapshot either
    snap_before = (CONFIG / cfg.REQUIREMENTS_REL).read_bytes()
    mod = _run_closure_and_assessment(tmp_path, cfg_copy)
    assert mod["raw"] == base["raw"], "raw physics changed when only a frozen constraint threshold changed"
    a1 = mod["assess"]
    assert a1["constraints"]["power_max_W"] == new_limit != a0["constraints"]["power_max_W"] == 1500.0
    assert a1["chk_power_air"] != a0["chk_power_air"]
    assert a1["chk_power_peak"] == (raw["P_total_peak_W"] <= new_limit * (1 - margin))
    assert (CONFIG / cfg.REQUIREMENTS_REL).read_bytes() == snap_before
    # the operating-scenario choices are untouched (the P_bus throttling cap is not the constraint; A9.24 item 4)
    assert cfg.load_operating_inputs(cfg_copy)["P_bus_max_W"] == 1500.0
    assert cfg.load_engineering_constraints(cfg_copy)["power_max_W"] == new_limit
    assert (cfg_copy / cfg.MISSION_REL).read_bytes() == (CONFIG / cfg.MISSION_REL).read_bytes()
    assert mod["oi"] == base["oi"]
    assert mod["gate_limits"]["HC-03"] == new_limit != base["gate_limits"]["HC-03"]


def test_thrust_floor_threshold_changes_assessment_not_scenario_or_raw_physics(tmp_path, cfg_copy):
    """A9.24 items 3-4: the Xe-sizing thrust target (operating scenario, 12 mN) is not the sustained-thrust floor
    (engineering constraint): changing the floor changes the assessment limits only; raw physics is byte-identical
    and the operating scenario (file and the four choices) is unchanged."""
    base = _run_closure_and_assessment(tmp_path, CONFIG)
    _edit_constraint(cfg_copy, "thrust_sustained_min_mN", 14)
    mod = _run_closure_and_assessment(tmp_path, cfg_copy)
    assert mod["raw"] == base["raw"], "raw physics changed when only the sustained-thrust floor changed"
    assert mod["gate_limits"]["HC-01"] == 14 * 1e-3 != base["gate_limits"]["HC-01"] == 0.012
    assert mod["oi"] == base["oi"]
    assert (mod["oi"]["thrust_min_mN"], mod["oi"]["thrust_max_mN"], mod["oi"]["P_bus_max_W"],
            mod["oi"]["mission_hours"]) == (12.0, 25.0, 1500.0, 26280.0)
    assert (cfg_copy / cfg.MISSION_REL).read_bytes() == (CONFIG / cfg.MISSION_REL).read_bytes()
    assert cfg.load_engineering_constraints(cfg_copy)["thrust_min_mN"] == 14.0


def test_hc07_threshold_changes_assessment_not_firing_hours_or_raw_physics(tmp_path, cfg_copy):
    """Owner ruling 2026-10-04 (item 3 + couplings, section 4): the physics firing / integration duration is the
    operating choice mission_scenario_v2 firing_hours (15,000 h); the HC-07 firing-life acceptance threshold resolves
    to the engineering constraint firing_life_h. Changing that threshold alone changes the assessment limit only:
    raw physics byte-identical, firing_hours and the scenario file unchanged."""
    base = _run_closure_and_assessment(tmp_path, CONFIG)
    _edit_constraint(cfg_copy, "firing_life_h", 20000)
    mod = _run_closure_and_assessment(tmp_path, cfg_copy)
    assert mod["raw"] == base["raw"], "raw physics changed when only the HC-07 firing-life threshold changed"
    assert mod["gate_limits"]["HC-07"] == 20000 != base["gate_limits"]["HC-07"] == 15000
    assert mod["oi"] == base["oi"] and mod["oi"]["firing_hours"] == 15000.0
    assert cfg.load_operating_inputs(cfg_copy)["firing_hours"] == 15000.0
    assert (cfg_copy / cfg.MISSION_REL).read_bytes() == (CONFIG / cfg.MISSION_REL).read_bytes()


def test_edited_operating_scenario_needs_a_new_version(cfg_copy):
    """A9.24 item 4: changing an operating choice needs a new scenario version. An edited scenario is refused even
    with a refreshed manifest (code-side pin: id, scenario_version, sha256); so is a relabelled id / version."""
    assert cfg.load_operating_inputs(cfg_copy)["thrust_min_mN"] == 12.0
    p = cfg_copy / cfg.MISSION_REL
    for edit in (lambda d: d["inputs"]["xe_sizing_thrust_target_mN"].update(value=13),
                 lambda d: d.update(scenario_version=3, id="mission_scenario_v3"),
                 lambda d: d["inputs"]["p_bus_throttling_cap_W"].update(value=1400),
                 lambda d: d["inputs"]["firing_hours"].update(value=16000)):      # owner ruling 2026-10-04
        shutil.copy2(CONFIG / cfg.MISSION_REL, p)
        d = _json(p)
        edit(d)
        p.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
        _remanifest(cfg_copy)
        with pytest.raises(cfg.ConfigurationError, match="does not match its pin"):
            cfg.load_operating_inputs(cfg_copy)
    # the builder refuses an edited scenario as well (it never regenerates it)
    b = _builder()
    assert b.MISSION_FILE == cfg.MISSION_REL
    pin = b._code_pin("OPERATING_SCENARIO_PIN")
    assert pin == cfg.OPERATING_SCENARIO_PIN and pin["sha256"] == _sha(CONFIG / cfg.MISSION_REL)


def test_operating_choices_are_independent_of_the_constraints():
    """A9.24 item 4: the four operating choices carry explicit values with initial_basis provenance naming the
    constraint; the builder does not derive them (a changed requirement leaves the scenario bytes unchanged)."""
    ms = cfg.load_mission_scenario()
    assert ms["id"] == "mission_scenario_v2" and ms["scenario_version"] == 2 and ms["status"] == "FROZEN"
    assert "sha256" not in ms["engineering_constraints"]
    want = {"xe_sizing_thrust_target_mN": (12, "thrust_sustained_min_mN"),
            "commanded_thrust_cap_mN": (25, "thrust_capability_mN"),
            "p_bus_throttling_cap_W": (1500, "p_bus_max_W"), "mission_hours": (26280, "mission_life_h"),
            "firing_hours": (15000, "firing_life_h")}          # owner ruling 2026-10-04 (independent of HC-07)
    for k, (v, cid) in want.items():
        e = ms["inputs"][k]
        assert e["kind"] == "OPERATING_SCENARIO_CHOICE" and e["value"] == v, k
        assert e["initial_basis"]["constraint_id"] == cid and e["initial_basis"]["role"] == "PROVENANCE_ONLY", k
        assert "set_equal_to_constraint" not in e, k
    assert set(ms["inputs"]) == set(want)                   # no wet-mass / altitude-band entry (owner ruling)
    assert cfg.OPERATING_CHOICE_KEYS == {k: cid for k, (v, cid) in want.items()}
    # historical v1 is kept byte-identical and listed, never loaded
    assert ms["supersedes"]["sha256"] == _sha(CONFIG / cfg.MISSION_V1_REL) == cfg.load_manifest()["files"][
        cfg.MISSION_V1_REL]["sha256"]


# ============================================================================================ (c) physics -> not requirements
def test_physics_parameter_changes_raw_physics_not_requirements_or_constraints(monkeypatch):
    from abep_sim import system, thruster
    files = {rel: (CONFIG / rel).read_bytes() for rel in (cfg.REQUIREMENTS_REL, cfg.CONSTRAINTS_REL)}
    vals = (cfg.load_rfp_constraints_compat(), cfg.load_engineering_constraints())
    c = _parametric_cfg()
    raw0 = system.physics_closure(c)
    monkeypatch.setattr(thruster, "G0", thruster.G0 * 1.01)          # a physics coefficient of the closure (Isp)
    raw1 = system.physics_closure(c)
    assert json.dumps(raw1, sort_keys=True) != json.dumps(raw0, sort_keys=True)
    assert raw1["Isp_air_s"] != raw0["Isp_air_s"]
    assert {rel: (CONFIG / rel).read_bytes() for rel in files} == files
    assert (cfg.load_rfp_constraints_compat(), cfg.load_engineering_constraints()) == vals
    # derivation: a different physics model set leaves the builder's requirements / constraints output unchanged
    b = _builder()
    real = b.build_model_set
    monkeypatch.setattr(b, "build_model_set", lambda: {**real(), "modules": [], "id": "physics_model_set_changed"})
    out = b.build_all()
    assert out[b.MODEL_SET_FILE] != (CONFIG / cfg.MODEL_SET_REL).read_bytes()
    assert out[b.REQ_FILE] == files[cfg.REQUIREMENTS_REL] and out[b.CONSTRAINTS_FILE] == files[cfg.CONSTRAINTS_REL]


# ============================================================================================ (d) design states -> not architecture
def test_design_state_swap_does_not_rewrite_the_architecture(cfg_copy, monkeypatch):
    arch_bytes = (CONFIG / cfg.ARCHITECTURE_REL).read_bytes()
    arch0, pc0 = cfg.load_architecture(), cfg.physics_configuration()
    alt_rel = "abep_sim/data/atmosphere_msis21_orbit_v1_design_states.json"          # the v1 set (179 states)
    ref = _json(cfg_copy / cfg.DESIGN_STATE_REF_REL)
    ref.update(id="swapped_design_state_set_for_test", path=alt_rel, sha256=_sha(ROOT / alt_rel))
    (cfg_copy / cfg.DESIGN_STATE_REF_REL).write_text(json.dumps(ref, indent=1) + "\n", encoding="utf-8")
    _remanifest(cfg_copy)
    pc1 = cfg.physics_configuration(cfg_copy)
    assert pc1.design_state_set_id == "swapped_design_state_set_for_test" != pc0.design_state_set_id
    assert pc1.design_state_set_sha256 != pc0.design_state_set_sha256
    assert (cfg_copy / cfg.ARCHITECTURE_REL).read_bytes() == arch_bytes == (CONFIG / cfg.ARCHITECTURE_REL).read_bytes()
    assert cfg.load_architecture(cfg_copy) == arch0
    assert (pc1.architecture_id, pc1.architecture_sha256) == (pc0.architecture_id, pc0.architecture_sha256)
    assert (pc1.engineering_constraints_id, pc1.engineering_constraints_sha256) == \
        (pc0.engineering_constraints_id, pc0.engineering_constraints_sha256)
    # builder: a different design-state reference regenerates nothing of the architecture / constraints
    b = _builder()
    real = b.build_design_state_ref
    monkeypatch.setattr(b, "build_design_state_ref", lambda: {**real(), "id": "swapped", "sha256": "0" * 64})
    out = b.build_all()
    assert out[b.DS_REF_FILE] != (CONFIG / cfg.DESIGN_STATE_REF_REL).read_bytes()
    assert out[b.ARCH_FILE] == arch_bytes
    assert out[b.CONSTRAINTS_FILE] == (CONFIG / cfg.CONSTRAINTS_REL).read_bytes()
    from abep_sim.design import a9_19_architecture as a
    assert a.FLIGHT_CONFIGURATION == arch0["constants"]["flight_configuration"]


# ============================================================================================ (e) only derivation path
def _resolve(d: dict, dotted: str):
    if dotted.startswith("rvm_limits["):
        rid = dotted[len("rvm_limits["):-1]
        return next(e for e in d["rvm_limits"] if e["rvm_row"] == rid)["limit"]["value"]
    for part in dotted.split("."):
        d = d[part]
    return d["value"] if isinstance(d, dict) and "value" in d else d


def test_constraints_are_derived_from_the_snapshot_only(monkeypatch):
    snap_rel, cons_rel = cfg.REQUIREMENTS_REL, cfg.CONSTRAINTS_REL
    snap = cfg.load_requirements_snapshot()
    cons = cfg.load_engineering_constraints_file()
    # constraints carry the snapshot sha256 (provenance) and every value equals the snapshot field it cites
    pv = cons["provenance"]["requirements_snapshot"]
    assert pv["path"] == "config/" + snap_rel and pv["sha256"] == _sha(CONFIG / snap_rel) == \
        cfg.load_manifest()["files"][snap_rel]["sha256"]
    assert pv["snapshot_status"] == snap["snapshot_status"]
    for cid, e in cons["constraints"].items():
        provs = e["provenance"] if isinstance(e["provenance"], list) else [e["provenance"]]
        for p in provs:
            assert p["rvm_row"] and isinstance(p["rfp_clauses"], list)
        if isinstance(e["provenance"], dict):
            assert _resolve(snap, e["provenance"]["snapshot_field"]) == e["value"], cid
        want = "FROZEN" if all(p["requirement_frozen"] for p in provs) else "PROVISIONAL"
        assert e["status"] == want, cid
        assert e["units"] and e["comparator"], cid
    assert cons["set_status"] == ("FROZEN" if all(e["status"] == "FROZEN" for e in cons["constraints"].values())
                                  else "PROVISIONAL")
    # the builder regenerates the constraints from the snapshot (byte for byte) ...
    b = _builder()
    out = b.build_all()
    assert out[b.CONSTRAINTS_FILE] == (CONFIG / cons_rel).read_bytes()
    assert out[b.MISSION_FILE] == (CONFIG / cfg.MISSION_REL).read_bytes()
    # ... and a changed requirement (RVM P_bus limit) flows snapshot -> constraints, nowhere else (A9.24 item 4: the
    # operating scenario is not regenerated and keeps its bytes)
    real = b.read_json

    def rvm_changed(rel):
        d = copy.deepcopy(real(rel))
        if rel == b.RVM_REL:
            for r in d["rows"]:
                if r["id"] == "RVM-04":
                    r["limit"]["value"] = 1400
        return d

    monkeypatch.setattr(b, "read_json", rvm_changed)
    out2 = b.build_all()
    c2 = json.loads(out2[b.CONSTRAINTS_FILE])
    assert c2["constraints"]["p_bus_max_W"]["value"] == 1400
    assert c2["provenance"]["requirements_snapshot"]["sha256"] == hashlib.sha256(out2[b.REQ_FILE]).hexdigest()
    assert out2[b.MISSION_FILE] == out[b.MISSION_FILE] and out2[b.MISSION_V1_FILE] == out[b.MISSION_V1_FILE]
    for k in (b.ARCH_FILE, b.DS_REF_FILE, b.HW_FILE, b.MODEL_SET_FILE):
        assert out2[k] == out[k], k


def test_only_the_builder_writes_the_engineering_constraints():
    """No other producer: every Python file that names the constraints file (outside tests) either is the builder or
    contains no file-writing call."""
    writes = ("write_bytes", "write_text", "json.dump(", "open(")
    named, writers = set(), set()
    for d in ("abep_sim", "scripts", "hallthruster_bridge", "docs"):
        for p in (ROOT / d).rglob("*.py"):
            src = p.read_text(encoding="utf-8", errors="ignore")
            if "engineering_constraints_v1.json" in src or "CONSTRAINTS_FILE" in src or "CONSTRAINTS_REL" in src:
                rel = p.relative_to(ROOT).as_posix()
                named.add(rel)
                if any(w in src for w in writes):
                    writers.add(rel)
    assert {"scripts/config/build_config.py", "abep_sim/configuration.py"} <= named
    # the C-ABEP_SIM_CONFIGURATION_PY v1 parity harness writes mutated copies of config/ into temporary case trees
    # only (refusal cases); it never writes the repository and derives no constraint (A9.29 lane A2)
    assert writers <= {"scripts/config/build_config.py", "scripts/config/build_result_schemas.py",
                       "scripts/rust_migration/parity_config_v1.py"}, writers


def test_physics_seams_read_values_only_from_constraints_and_scenario(cfg_copy):
    """The scenario restates no constraint value; the seams fail closed when a constraint is missing. A9.24 item 4:
    the scenario carries no constraints sha256 pin, so an edited constraints file (refreshed manifest) still loads."""
    ms = cfg.load_mission_scenario()
    for k, e in ms["inputs"].items():
        assert e["kind"] in ("CONSTRAINT_REFERENCE", "OPERATING_SCENARIO_CHOICE"), k
        if e["kind"] == "CONSTRAINT_REFERENCE":
            assert "value" not in e and e["constraint_ref"] in cfg.CONSTRAINT_IDS, k
        else:
            assert e["initial_basis"]["constraint_id"] in cfg.CONSTRAINT_IDS, k
    assert "sha256" not in ms["engineering_constraints"]
    # an edited constraints file (manifest refreshed) does not invalidate the scenario
    p = cfg_copy / cfg.CONSTRAINTS_REL
    d = _json(p)
    d["title"] += " (edited)"
    p.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
    _remanifest(cfg_copy)
    assert cfg.load_operating_inputs(cfg_copy) == cfg.load_operating_inputs()
    # constraint missing
    del d["constraints"]["firing_life_h"]
    p.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
    _remanifest(cfg_copy)
    with pytest.raises(cfg.ConfigurationError, match="missing"):
        cfg.load_engineering_constraints(cfg_copy)
