"""Thruster feed-envelope definition v1 (architecture-comparison lane 16, FEED).

Checks that scripts/architecture/build_feed_envelope.py reproduces the committed envelope, that the envelope validates
against schemas/architecture_comparison/feed_envelope_v1.schema.json, that species fractions close, that the envelope is
architecture- and Hall-closure-independent, and that the script refuses missing / unprovenanced design inputs and a
non-frozen atmosphere. Run: python -m pytest -q tests/test_feed_envelope.py  (~5 s; the design-conditional test runs the
command line once in a subprocess).
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "architecture" / "build_feed_envelope.py"
OUT_DIR = REPO / "docs" / "architecture_comparison" / "feed_envelope"
JSON_PATH = OUT_DIR / "feed_envelope_v1.json"
MD_PATH = OUT_DIR / "FEED_ENVELOPE.md"
SCHEMA_PATH = REPO / "schemas" / "architecture_comparison" / "feed_envelope_v1.schema.json"
ENSEMBLE_PATH = REPO / "hallthruster_bridge" / "ensemble" / "transport_ensemble_v0.json"
FORBIDDEN_PRODUCER_PREFIXES = ("abep_sim.hall_map", "abep_sim.hall_ensemble", "abep_sim.hall1d",
                               "abep_sim.plasma_devices", "abep_sim.plasma_chem", "hallthruster_bridge")


def _load_script():
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location("build_feed_envelope", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bfe = _load_script()


@pytest.fixture(scope="module")
def committed() -> dict:
    return json.loads(JSON_PATH.read_text())


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _assert_same(a, b, path="$"):
    """Structural equality; floats to 1e-9 relative (the output is rounded to 12 significant digits)."""
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None or isinstance(a, str):
        assert a == b, f"{path}: {a!r} != {b!r}"
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=0.0), f"{path}: {a!r} != {b!r}"
    elif isinstance(a, dict):
        assert isinstance(b, dict) and list(a) == list(b), f"{path}: keys {list(a)} != {list(b) if isinstance(b, dict) else b}"
        for k in a:
            _assert_same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), f"{path}: list lengths differ"
        for i, (x, y) in enumerate(zip(a, b)):
            _assert_same(x, y, f"{path}[{i}]")
    else:
        raise AssertionError(f"{path}: unexpected type {type(a)}")


def _keys(obj, out=None):
    out = set() if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            _keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, out)
    return out


def _producer_modules(obj, out=None):
    out = [] if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("producer", "atmosphere", "chain") and isinstance(v, dict) and "module" in v:
                out.append(v["module"])
            _producer_modules(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _producer_modules(v, out)
    return out


def _fixture_design_inputs(doc: dict, compressor_mode="size_for", valve_mode="pressure_setpoint") -> dict:
    """TEST FIXTURE ONLY, not a design baseline: values are the repository's code defaults (as listed with
    adopted=false in the committed contract), arranged the way system.evaluate chains them, and the historical 0.05 Pa
    reference setpoint quoted in not_adopted. Evidence class 'assumed' throughout."""
    inputs = {"compressor.mode": {"value": compressor_mode, "source": "TEST FIXTURE", "evidence_class": "assumed"},
              "valve.mode": {"value": valve_mode, "source": "TEST FIXTURE", "evidence_class": "assumed"}}
    catalog = {e["name"]: e for e in doc["design_input_contract"]}

    def default(name, prefer=None):
        cds = catalog[name]["code_defaults"]
        for cd in cds:
            if prefer and prefer in cd["source"]:
                return cd
        return cds[0]

    for name in bfe.required_design_inputs(inputs):
        if name in inputs:
            continue
        if name == "valve.p_feed_setpoint_Pa":
            na = next(n for n in doc["not_adopted"] if n["quantity"] == "valve.p_feed_setpoint_Pa")
            cd = {"value": na["value"], "source": f"{na['file']} (not adopted; quoted in not_adopted)"}
        else:
            prefer = "gas_path_state" if name.startswith("intake.") else "Config" if name in (
                "compressor.rotor_material", "chamber.wall_material") else None
            cd = default(name, prefer)
        inputs[name] = {"value": cd["value"], "source": "TEST FIXTURE ONLY - " + cd["source"],
                        "evidence_class": "assumed"}
    area, phi = inputs["intake.area_m2"]["value"], inputs["intake.phi"]["value"]
    rotor = inputs["compressor.rotor_material"]["value"]
    # system.evaluate (gaspath_physics) conventions, abep_sim/system.py
    inputs["compressor.turbo_area_m2"]["value"] = min(0.45, 0.9 * area * phi)
    inputs["compressor.turbo_radius_m"]["value"] = min(0.45, math.sqrt(area / math.pi))
    inputs["chamber.upstream_material"]["value"] = rotor if rotor in ("Ti6Al4V", "Al6061") else "Al2O3_anodised"
    inputs["chamber.T_K"]["value"] = bfe.TOKEN_T_FROM_COMPRESSOR
    inputs["chamber.upstream_collisions"]["value"] = bfe.TOKEN_UPSTREAM_COLLISIONS
    return {"format": bfe.DESIGN_INPUTS_FORMAT, "label": "test-fixture-code-defaults (NOT a baseline)",
            "inputs": inputs}


# ------------------------------------------------------------------------------------------------ reproduction
def test_script_reproduces_committed_envelope(committed):
    rebuilt = bfe.build_document()
    _assert_same(rebuilt, committed)
    assert bfe.render_markdown(committed) == MD_PATH.read_text(), "FEED_ENVELOPE.md is not the rendering of the JSON"


def test_input_file_hashes_are_current(committed):
    for f in committed["provenance"]["input_files"]:
        assert bfe.sha256_file(f["path"]) == f["sha256"], f"{f['path']} changed: rerun {bfe.SCRIPT_REL}"


# ---------------------------------------------------------------------------------------------------- schema
def test_committed_envelope_validates_against_schema(committed, schema):
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert committed["schema"] == bfe.SCHEMA_REL
    errs = bfe.validate(committed, schema)
    assert errs == [], "\n".join(errs[:20])
    bfe.validate_document(committed)
    try:                                        # independent check when jsonschema happens to be installed
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(committed)


def test_schema_uses_only_supported_keywords(schema):
    used = bfe.schema_keywords(schema)
    unsupported = used - bfe.SUPPORTED_SCHEMA_KEYWORDS - bfe.ANNOTATION_KEYWORDS
    assert not unsupported, f"schema uses keywords the built-in validator does not implement: {unsupported}"


@pytest.mark.parametrize("mutation", [
    "value_with_tbd_class", "null_without_requires", "wrong_unit", "closure_field_added", "architecture_ids",
    "ok_status_with_null_feed", "unknown_evidence_class", "free_stream_species_xe"])
def test_validator_rejects_bad_documents(committed, schema, mutation):
    doc = copy.deepcopy(committed)
    c = doc["cases"][0]
    if mutation == "value_with_tbd_class":
        c["free_stream"]["rho_kgpm3"]["evidence_class"] = "TBD"
    elif mutation == "null_without_requires":
        c["free_stream"]["rho_kgpm3"]["value"] = None
        c["free_stream"]["rho_kgpm3"]["evidence_class"] = "TBD"
    elif mutation == "wrong_unit":
        c["free_stream"]["p_ambient_Pa"]["unit"] = "Torr"
    elif mutation == "closure_field_added":
        c["feed_state"]["ensemble_member_id"] = "sgb-screen-01"
    elif mutation == "architecture_ids":
        doc["architectures"]["ids"] = ["hall_only", "rf_hall"]
    elif mutation == "ok_status_with_null_feed":
        c["status"] = "OK"
    elif mutation == "unknown_evidence_class":
        c["free_stream"]["T_ambient_K"]["evidence_class"] = "estimated"
    elif mutation == "free_stream_species_xe":
        c["free_stream"]["w_s"]["values"]["Xe"] = 0.0
    assert bfe.validate(doc, schema), f"mutation {mutation} was not rejected"


# ------------------------------------------------------------------------------------------ closure and content
def test_species_fractions_close(committed):
    from abep_sim.constants import M_SPECIES
    n = 0
    for c in committed["cases"]:
        for blk in ("free_stream", "feed_state"):
            for key in ("w_s", "x_s"):
                vals = c[blk][key]["values"]
                if all(v is None for v in vals.values()):
                    assert c[blk][key]["evidence_class"] == "TBD" and c[blk][key]["requires"].startswith("TBD")
                    continue
                assert set(vals) == {"O", "N2", "O2"}
                assert all(0.0 <= v <= 1.0 for v in vals.values())
                assert abs(sum(vals.values()) - 1.0) <= bfe.MASS_FRACTION_CLOSURE_TOL, (c["case_id"], blk, key)
                n += 1
        w = c["free_stream"]["w_s"]["values"]
        x = c["free_stream"]["x_s"]["values"]
        z = {s: w[s] / M_SPECIES[s] for s in w}
        for s in w:                                      # x_s is the mole-fraction transform of w_s
            assert math.isclose(x[s], z[s] / sum(z.values()), rel_tol=1e-9)
    assert n == 2 * len(committed["cases"])
    for key in ("w_s", "x_s"):
        assert committed["xe_path"]["feed_state"][key]["values"] == {"Xe": 1.0}


def test_cases_cover_rfp_grid_on_frozen_nodes(committed):
    import pandas as pd
    from abep_sim import atmosphere as A
    df = pd.read_csv(REPO / "abep_sim" / "data" / "atmosphere_msis21_v1.csv")
    cases = committed["cases"]
    assert {(c["alt_km"], c["atmosphere_level"]) for c in cases} == {
        (a, l) for a in (180.0, 200.0, 230.0) for l in ("low", "mean", "high")}
    assert len(cases) == 9
    for c in cases:
        assert c["averaging"] == "orbit_averaged" and c["architecture_dependent"] is False
        assert c["f107"] == c["f107a"] == A._SOLAR_F107[c["atmosphere_level"]] and c["ap"] == 15.0
        row = df[(df.alt_km == c["alt_km"]) & (df.f107 == c["f107"])].iloc[0]
        fs = c["free_stream"]
        assert math.isclose(fs["rho_kgpm3"]["value"], row.rho, rel_tol=1e-10)
        assert math.isclose(fs["T_ambient_K"]["value"], row["T"], rel_tol=1e-10)
        for s, col in (("O", "fO"), ("N2", "fN2"), ("O2", "fO2")):
            assert math.isclose(fs["w_s"]["values"][s], row[col], rel_tol=1e-10)
        assert math.isclose(fs["mass_flux_kgpm2ps"]["value"], row.rho * fs["V_mps"]["value"], rel_tol=1e-10)
        assert fs["atmosphere_source"]["value"].startswith("NRLMSIS 2.1 frozen scenario ")
        for k, q in fs.items():
            if "evidence_class" in q:
                assert q["evidence_class"] == "model-derived", k
        # no documented design baseline -> every valve-outlet quantity is TBD and names its missing inputs
        assert c["status"] == "DESIGN_INPUTS_MISSING" and c["chain_detail"] is None
        for k, q in c["feed_state"].items():
            assert q["evidence_class"] == "TBD" and q["requires_design_inputs"], k
    assert committed["extremes"]["status"] == "TBD"
    assert committed["milestones"]["supports"] == ["A"]
    assert committed["envelope_ranges"]["feed_state"]["status"] == "TBD"


def test_no_architecture_or_hall_closure_dependence(committed):
    keys = _keys(committed)
    nuisance = set(json.loads(ENSEMBLE_PATH.read_text())["calibration_nuisance"])
    forbidden = nuisance | {"ensemble_member_id", "transport", "hall_only", "rf_hall", "ecr_hall"}
    assert not {k for k in keys for f in forbidden if f in k}, "closure / nuisance / architecture key in the envelope"
    for m in _producer_modules(committed):
        assert not m.startswith(FORBIDDEN_PRODUCER_PREFIXES), m
    tree = ast.parse(SCRIPT.read_text())
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not {m for m in imported if m.startswith(FORBIDDEN_PRODUCER_PREFIXES)}
    # at run time, building the envelope loads no Hall / plasma module
    prefixes = tuple(p for p in FORBIDDEN_PRODUCER_PREFIXES if p.startswith("abep_sim."))
    code = ("import sys, importlib.util\n"
            f"sys.path.insert(0, {str(REPO)!r})\n"
            f"s = importlib.util.spec_from_file_location('b', {str(SCRIPT)!r})\n"
            "m = importlib.util.module_from_spec(s); s.loader.exec_module(m); m.build_document()\n"
            f"print(sorted(k for k in sys.modules if k.startswith({prefixes!r})))\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, cwd=str(REPO))
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip() == "[]", out.stdout


def test_not_adopted_values_are_quoted_from_their_files(committed):
    for n in committed["not_adopted"]:
        if n["evidence_token"]:
            assert n["evidence_token"] in (REPO / n["file"]).read_text(), n
    for e in committed["design_input_contract"]:
        assert e["documented_baseline"] is None and e["status"] == "TBD"
        assert all(cd["adopted"] is False and cd["evidence_class"] == "assumed" for cd in e["code_defaults"])


# --------------------------------------------------------------------------------------------------- refusals
def test_refuses_missing_design_input(committed, tmp_path):
    fx = _fixture_design_inputs(committed)
    assert bfe.validate_design_inputs(fx)                       # the complete fixture is accepted
    for name in ("intake.area_m2", "valve.p_feed_setpoint_Pa", "compressor.xi", "chamber.volume_m3",
                 "compressor.size_for.rpm_max", "compressor.mode"):
        bad = copy.deepcopy(fx)
        del bad["inputs"][name]
        with pytest.raises(bfe.MissingDesignInput, match=name.replace(".", r"\.")):
            bfe.validate_design_inputs(bad)
    # the same refusal through the command line
    bad = copy.deepcopy(fx)
    del bad["inputs"]["intake.area_m2"]
    p = tmp_path / "design.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(bfe.MissingDesignInput):
        bfe.main(["--design-inputs", str(p), "--out-dir", str(tmp_path / "out")])
    assert not (tmp_path / "out").exists()
    # design inputs never overwrite the committed, baseline-free envelope implicitly
    p.write_text(json.dumps(fx))
    with pytest.raises(SystemExit):
        bfe.main(["--design-inputs", str(p)])


@pytest.mark.parametrize("case", ["no_source", "tbd_class", "unknown_input", "off_axis_out_of_grid",
                                  "accommodation_out_of_grid", "sized_field_in_size_for", "size_for_with_orifice",
                                  "bad_material", "bad_token", "negative_area"])
def test_rejects_invalid_design_input(committed, case):
    fx = _fixture_design_inputs(committed)
    inp = fx["inputs"]
    if case == "no_source":
        del inp["intake.phi"]["source"]
    elif case == "tbd_class":
        inp["intake.phi"]["evidence_class"] = "TBD"
    elif case == "unknown_input":
        inp["intake.area_cm2"] = {"value": 1.0, "source": "x", "evidence_class": "assumed"}
    elif case == "off_axis_out_of_grid":
        inp["intake.off_axis_deg"]["value"] = 7.0
    elif case == "accommodation_out_of_grid":
        inp["intake.accommodation"]["value"] = 1.2
    elif case == "sized_field_in_size_for":
        inp["compressor.rpm"] = {"value": 1.0, "source": "x", "evidence_class": "assumed"}
    elif case == "size_for_with_orifice":
        inp["valve.mode"]["value"] = "orifice_area"
        del inp["valve.p_feed_setpoint_Pa"]
        inp["valve.anode_orifice_area_m2"] = {"value": 1e-5, "source": "x", "evidence_class": "assumed"}
    elif case == "bad_material":
        inp["chamber.wall_material"]["value"] = "Unobtainium"
    elif case == "bad_token":
        inp["chamber.T_K"]["value"] = "room_temperature"
    elif case == "negative_area":
        inp["intake.area_m2"]["value"] = -1.0
    with pytest.raises(bfe.InvalidDesignInput):
        bfe.validate_design_inputs(fx)


def test_refuses_non_frozen_atmosphere(monkeypatch):
    from abep_sim import atmosphere as A
    monkeypatch.setattr(A, "_MSIS_CACHE", {})
    monkeypatch.setenv("ABEP_ALLOW_TABLE_ATMOSPHERE", "1")         # would switch atmosphere() to the approximate table
    with pytest.raises(bfe.FrozenAtmosphereRequired):
        bfe.frozen_state(200.0, "mean")


# --------------------------------------------------------------------------------- design-conditional chain
@pytest.mark.parametrize("modes", [("size_for", "pressure_setpoint"), ("fixed", "orifice_area")])
def test_design_conditional_chain(committed, tmp_path, modes):
    """Runs the command line with the code-default TEST FIXTURE (not a design result) on all nine cases, in a
    subprocess with single-threaded BLAS: results do not depend on the thread count, but the first evaluation of the
    frozen TPMC interpolant is very slow with multi-threaded OpenBLAS on a loaded machine."""
    import os
    fx = _fixture_design_inputs(committed, *modes)
    di = tmp_path / "design.json"
    di.write_text(json.dumps(fx))
    out_dir = tmp_path / "out"
    env = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    before = JSON_PATH.read_text()
    run = subprocess.run([sys.executable, str(SCRIPT), "--design-inputs", str(di), "--out-dir", str(out_dir)],
                         capture_output=True, text=True, timeout=300, cwd=str(REPO), env=env)
    assert run.returncode == 0, run.stderr[-3000:]
    assert JSON_PATH.read_text() == before                         # the committed envelope is untouched
    doc = json.loads((out_dir / bfe.JSON_NAME).read_text())
    assert (out_dir / bfe.MD_NAME).read_text() == bfe.render_markdown(doc)
    bfe.validate_document(doc)
    assert doc["design_inputs"]["supplied"] is True and doc["design_inputs"]["label"] == fx["label"]
    by = {c["case_id"]: c for c in doc["cases"]}
    area = fx["inputs"]["intake.area_m2"]["value"]
    p_set = fx["inputs"].get("valve.p_feed_setpoint_Pa", {}).get("value")
    statuses = {k: c["status"] for k, c in by.items()}
    assert set(statuses.values()) <= {"OK", "INFEASIBLE", "MODEL_ERROR"}
    for k, c in by.items():
        det = c["chain_detail"]["chain_freestream_split"]
        fs = c["feed_state"]
        if c["status"] == "OK":
            m = fs["mdot_total_kgps"]["value"]
            assert fs["mdot_total_kgps"]["evidence_class"] == "model-derived"
            assert 0.0 < m <= area * c["free_stream"]["mass_flux_kgpm2ps"]["value"]           # eta_c <= 1
            assert math.isclose(m, sum(fs["mdot_s_kgps"]["values"].values()), rel_tol=1e-9)
            assert abs(sum(fs["w_s"]["values"].values()) - 1.0) < 1e-9
            assert abs(sum(fs["x_s"]["values"].values()) - 1.0) < 1e-9
            assert det["chamber"]["mass_balance_residual"] <= bfe.RES_BALANCE_RTOL             # conservation gate
            if p_set is not None:
                assert math.isclose(fs["p_feed_Pa"]["value"],
                                    p_set * (1 + det["chamber"]["setpoint_relative_residual"]), rel_tol=1e-9)
            assert 300.0 <= fs["T_gas_K"]["value"] <= 500.0       # system.evaluate temperature convention (token)
            scen = fs["w_s"]["uncertainty"]["scenarios"]
            assert [s["convention"] for s in scen] == ["chain_freestream_split", "species_resolved_surface"]
            assert c["feed_scaling"]["A_eff_m2"]["value"] <= area
        else:
            assert c["status_reasons"], k
            assert fs["mdot_total_kgps"]["value"] is None and fs["p_feed_Pa"]["value"] is None
            assert all(v is None for v in fs["w_s"]["values"].values())
    n_ok = sum(v == "OK" for v in statuses.values())
    if modes[0] == "fixed":
        # the dataclass-default compressor (3 rows, 4 stages, 60000 rpm) on the system.evaluate rotor size exceeds the
        # rotor stress limit and its leak recirculation diverges: every case must be refused, none may carry a value
        assert n_ok == 0 and set(statuses.values()) <= {"MODEL_ERROR", "INFEASIBLE"}
        assert doc["envelope_ranges"]["feed_state"]["status"] == "TBD"
        return
    assert n_ok >= 1
    assert doc["envelope_ranges"]["feed_state"]["n_ok_cases"] == n_ok
    # the fixture mirrors the historical reference gas state; at 200 km mean its setpoint lies outside the orifice
    # bracket, which system.evaluate passes silently (ICD G-05) - here it must be MODEL_ERROR, not a value
    mean200 = by["alt200_mean_orbit_averaged"]
    assert mean200["status"] == "MODEL_ERROR"
    assert mean200["chain_detail"]["chain_freestream_split"]["chamber"]["orifice_bracket_hit"] is True
