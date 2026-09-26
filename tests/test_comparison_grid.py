"""Tests for the common operating-envelope comparison grid (lane 23, GRID).

Checks that docs/architecture_comparison/comparison_grid/comparison_grid_v1.json is reproduced by
scripts/architecture/build_comparison_grid.py, validates against
schemas/architecture_comparison/comparison_grid_v1.schema.json, gives hall_only, rf_hall and ecr_hall the identical base
point set (P_source = 0 only for hall_only; one common non-zero level set for the source arms), uses no calibration
nuisance as an axis, propagates TBD prerequisites instead of inventing values, records the grid hash and refuses a
freeze while blockers remain. The prerequisite files of other lanes are NOT required: the test that re-extracts from
them is skipped when they cannot be resolved.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "architecture" / "build_comparison_grid.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_comparison_grid", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bcg = _load_builder()
GRID_PATH = REPO / bcg.GRID_REL
SCHEMA_PATH = REPO / bcg.SCHEMA_REL
DOC_PATH = REPO / bcg.DOC_REL


@pytest.fixture(scope="module")
def committed() -> dict:
    return json.loads(GRID_PATH.read_text())


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from _walk_keys(x)


# ------------------------------------------------------------------------------------------------ reproducibility
def test_offline_rebuild_reproduces_committed_bytes(committed):
    rebuilt = bcg.build_document(committed["inputs"])
    assert bcg.dumps(rebuilt) == GRID_PATH.read_text()


def test_build_is_deterministic_and_does_not_mutate_inputs(committed):
    inputs = copy.deepcopy(committed["inputs"])
    a = bcg.dumps(bcg.build_document(inputs))
    b = bcg.dumps(bcg.build_document(inputs))
    assert a == b
    assert inputs == committed["inputs"]


def test_rebuild_from_prerequisites_when_available(committed):
    """Re-extract from the other lanes' files (repository path or $ABEP_FEED_ENVELOPE / $ABEP_HALL_REFERENCE)."""
    try:
        feed = bcg.resolve_prerequisite(None, bcg.ENV_FEED, bcg.FEED_REL, "feed envelope")
        hall = bcg.resolve_prerequisite(None, bcg.ENV_HALLREF, bcg.HALLREF_REL, "Hall reference")
    except bcg.PrerequisiteMissing as e:
        pytest.skip(f"prerequisite not resolvable here: {e}")
    assert bcg.file_sha256(feed) == committed["prerequisites"]["feed_envelope"]["sha256"], \
        "feed envelope changed since the grid was built: regenerate the grid (allowed only before freeze)"
    assert bcg.file_sha256(hall) == committed["prerequisites"]["hall_reference"]["sha256"], \
        "Hall reference changed since the grid was built: regenerate the grid (allowed only before freeze)"
    assert bcg.dumps(bcg.build_document(bcg.extract_inputs(feed, hall))) == GRID_PATH.read_text()


def test_forbidden_axes_track_the_current_ensemble_file(committed):
    ens = json.loads((REPO / bcg.ENSEMBLE_REL).read_text())
    assert set(ens["calibration_nuisance"]) <= set(committed["forbidden_axes"]["names"])
    assert committed["inputs"]["calibration_nuisance"]["names"] == sorted(ens["calibration_nuisance"])


# ------------------------------------------------------------------------------------------------------- schema
def test_committed_grid_validates_against_schema(committed, schema):
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert committed["schema"] == bcg.SCHEMA_REL
    errs = bcg.validate(committed, schema)
    assert not errs, errs[:10]
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(committed)


def test_schema_uses_only_supported_keywords(schema):
    unsupported = bcg.schema_keywords(schema) - bcg.SUPPORTED_SCHEMA_KEYWORDS - bcg.ANNOTATION_KEYWORDS
    assert not unsupported


@pytest.mark.parametrize("mutation", [
    "drop_architecture_from_base_point", "unknown_architecture", "tbd_level_with_value", "tbd_level_without_requires",
    "bad_status", "extra_top_level_key", "bad_hash", "negative_p_source", "unknown_feed_mode",
])
def test_validator_rejects_bad_documents(committed, schema, mutation):
    doc = copy.deepcopy(committed)
    if mutation == "drop_architecture_from_base_point":
        doc["base_points"][0]["architectures"] = ["hall_only", "rf_hall"]
    elif mutation == "unknown_architecture":
        doc["evaluations"][0]["architecture"] = "helicon_hall"
    elif mutation == "tbd_level_with_value":
        doc["axes"]["p_source_W"]["levels"][1]["value"] = 250.0
    elif mutation == "tbd_level_without_requires":
        del doc["axes"]["p_source_W"]["levels"][2]["requires"]
    elif mutation == "bad_status":
        doc["status"] = "APPROVED"
    elif mutation == "extra_top_level_key":
        doc["winner"] = "rf_hall"
    elif mutation == "bad_hash":
        doc["hashes"]["grid_content_sha256"] = "abc"
    elif mutation == "negative_p_source":
        doc["axes"]["p_source_W"]["levels"][0]["value"] = -1
    elif mutation == "unknown_feed_mode":
        doc["base_points"][0]["feed_mode"] = "air_only"
    assert bcg.validate(doc, schema), f"mutation {mutation} was not rejected"


# --------------------------------------------------------------------------------------- fairness / identity
def test_identical_base_point_sets_across_architectures(committed):
    by_arch = {a: {e["base_point_id"] for e in committed["evaluations"] if e["architecture"] == a}
               for a in bcg.ARCHITECTURES}
    all_bp = {p["base_point_id"] for p in committed["base_points"]}
    for a, s in by_arch.items():
        assert s == all_bp, f"{a} is not evaluated at every base point"
    assert committed["summary"]["identical_base_point_sets"] is True
    for p in committed["base_points"]:
        assert p["architectures"] == list(bcg.ARCHITECTURES)


def test_p_source_levels_zero_only_for_hall_only_and_common_for_source_arms(committed):
    levels = {lv["id"]: lv for lv in committed["axes"]["p_source_W"]["levels"]}
    per = {a: {} for a in bcg.ARCHITECTURES}
    for e in committed["evaluations"]:
        per[e["architecture"]].setdefault(e["base_point_id"], set()).add(e["p_source_level_id"])
    assert all(v == {"PS0"} for v in per["hall_only"].values())
    assert levels["PS0"]["value"] == 0 and levels["PS0"]["architectures"] == ["hall_only"]
    rf, ecr = per["rf_hall"], per["ecr_hall"]
    assert rf == ecr, "rf_hall and ecr_hall must be evaluated at the same P_source levels at every base point"
    src_levels = set().union(*rf.values())
    assert "PS0" not in src_levels and len(src_levels) == committed["axes"]["p_source_W"]["level_structure"][
        "nonzero_levels"]
    assert all(v == src_levels for v in rf.values())
    for lid in src_levels:
        lv = levels[lid]
        assert lv["architectures"] == ["rf_hall", "ecr_hall"]
        assert lv["value"] is None or lv["value"] > 0
    pmax = committed["axes"]["p_source_W"]["bound"]["P_bus_max_W"]["value"]
    nums = sorted(levels[l]["value"] for l in src_levels if levels[l]["value"] is not None)
    assert all(0 < v < pmax for v in nums)


def test_p_source_definition_matches_boundary_components(committed):
    comps = committed["inputs"]["hall_reference"]["bus_power_boundary"]["arm_specific_components"]
    assert comps == bcg.EXPECTED_ARM_COMPONENTS
    assert committed["inputs"]["hall_reference"]["bus_power_boundary"]["boundary_version"] == "bus_power_boundary_v1"
    text = committed["axes"]["p_source_W"]["definition"]["definition"]
    for arch, cs in comps.items():
        for c in cs:
            assert c in text


def test_every_architecture_at_every_base_point_counts(committed):
    s = committed["summary"]
    n_bp = len(committed["base_points"])
    n_src = committed["axes"]["p_source_W"]["level_structure"]["nonzero_levels"]
    assert s["n_base_points"] == n_bp
    assert s["n_evaluations"] == len(committed["evaluations"]) == n_bp * (1 + 2 * n_src)
    assert s["n_evaluations_by_architecture"] == {"hall_only": n_bp, "rf_hall": n_bp * n_src, "ecr_hall": n_bp * n_src}
    ids = [e["evaluation_id"] for e in committed["evaluations"]]
    assert len(ids) == len(set(ids))
    bps = [p["base_point_id"] for p in committed["base_points"]]
    assert len(bps) == len(set(bps))


def test_mode_applicability_is_architecture_free(committed):
    feed = {lv["id"]: lv for lv in committed["axes"]["feed_state"]["levels"]}
    vds = [lv["id"] for lv in committed["axes"]["discharge_voltage_V"]["levels"]]
    atm = [c["case_id"] for c in committed["inputs"]["feed_envelope"]["cases"]]
    by_mode = {}
    for p in committed["base_points"]:
        by_mode.setdefault(p["feed_mode"], []).append(p)
        assert p["feed_level_id"] in feed
        assert p["feed_mode"] in feed[p["feed_level_id"]]["applies_to_modes"]
    assert {p["feed_level_id"] for p in by_mode["xe_start"]} == {"xe_path"}
    assert {p["feed_level_id"] for p in by_mode["atmosphere_dominant"]} == set(atm)
    assert {p["feed_level_id"] for p in by_mode["mixed"]} == set(atm)
    for m, pts in by_mode.items():                 # the same V_d set in every mode (INV-V1 / GR-7)
        for fid in {p["feed_level_id"] for p in pts}:
            assert sorted(p["vd_level_id"] for p in pts if p["feed_level_id"] == fid) == sorted(vds)
    for lv in feed.values():
        assert not any(a in json.dumps(lv) for a in bcg.ARCHITECTURES), "feed levels must be architecture-free"


def test_discharge_voltage_levels_are_the_hall_reference_set(committed):
    ref = committed["inputs"]["hall_reference"]["discharge_voltage"]["evaluation_set_V"]
    lv = committed["axes"]["discharge_voltage_V"]["levels"]
    assert [x["value"] for x in lv] == ref["value"]
    assert all(x["status"] == ref["status"] and x["evidence_class"] == ref["evidence_class"] for x in lv)
    lo, hi = committed["inputs"]["hall_reference"]["discharge_voltage"]["range_V"]["value"]
    assert all(lo <= x["value"] <= hi for x in lv)


# ------------------------------------------------------------------------------------------------- nuisance
def test_no_calibration_nuisance_axis(committed):
    forbidden = set(committed["forbidden_axes"]["names"])
    nuisance_values = set(committed["forbidden_axes"]["calibration_nuisance_values"])
    assert not set(committed["axes"]) & forbidden
    assert set(committed["axes"]) == set(bcg.AXIS_NAMES)
    for part in ("axes", "base_points", "evaluations"):
        keys = set(_walk_keys(committed[part]))
        assert not keys & forbidden, f"{part} uses forbidden names {keys & forbidden}"
    level_ids = {lv["id"] for ax in committed["axes"].values() for lv in ax.get("levels", [])}
    assert not level_ids & (forbidden | nuisance_values)
    text = json.dumps([committed["base_points"], committed["evaluations"]])
    for name in forbidden:
        assert name not in text


# ----------------------------------------------------------------------------------------------------- hashes
def test_grid_hash_recorded_and_reproducible(committed):
    h = committed["hashes"]
    assert h["grid_content_sha256"] == bcg.canonical_sha256(bcg.grid_content(committed))
    assert h["inputs_sha256"] == bcg.canonical_sha256(committed["inputs"])
    assert h["grid_content_covers"] == ["axes", "base_points", "evaluations", "rules"]
    doc = copy.deepcopy(committed)
    doc["base_points"].pop()
    assert bcg.canonical_sha256(bcg.grid_content(doc)) != h["grid_content_sha256"]
    md = DOC_PATH.read_text()
    assert h["grid_content_sha256"] in md, "COMPARISON_GRID.md must quote the current grid hash"


def test_doc_quotes_counts_and_milestones(committed):
    md = DOC_PATH.read_text()
    s = committed["summary"]
    assert f"{s['n_base_points']} base points" in md and f"{s['n_evaluations']} evaluations" in md
    for m in ("milestone A", "milestone B", "milestone C"):
        assert m in md
    assert committed["milestones"]["supports"] == ["A"]
    assert committed["milestones"]["B"]["needs"] and committed["milestones"]["C"]["needs"]


# ------------------------------------------------------------------------------------------ TBD propagation
def test_tbd_levels_carry_null_and_requires(committed):
    for name, ax in committed["axes"].items():
        for lv in ax.get("levels", []):
            if lv.get("status") == "TBD" and "value" in lv:
                assert lv["value"] is None and lv["requires"].startswith("TBD")
    for lv in committed["axes"]["feed_state"]["levels"]:
        for k, q in lv["feed_state"].items():
            if q["status"] == "TBD":
                assert q.get("value", None) is None and all(v is None for v in q.get("values", {}).values())
                assert q["requires"].startswith("TBD")
                assert k in lv["tbd_fields"]


def test_feed_values_are_copied_never_invented(committed):
    inputs = committed["inputs"]["feed_envelope"]
    feed = {lv["id"]: lv for lv in committed["axes"]["feed_state"]["levels"]}
    for c in inputs["cases"]:
        assert feed[c["case_id"]]["feed_state"] == c["if_a5"]
    assert feed["xe_path"]["feed_state"] == inputs["xe_path"]["if_x2"]


def test_base_points_list_every_tbd_dependency(committed):
    feed = {lv["id"]: lv for lv in committed["axes"]["feed_state"]["levels"]}
    for p in committed["base_points"]:
        need = {f"feed_state:{p['feed_level_id']}.{k}" for k in feed[p["feed_level_id"]]["tbd_fields"]}
        if p["feed_mode"] == "mixed":
            need |= {f"feed_state:xe_path.{k}" for k in feed["xe_path"]["tbd_fields"]}
            need.add(f"xe_anode_mass_fraction:{p['xe_mix_level_id']}")
        assert need <= set(p["tbd_dependencies"])
        assert (p["status"] == "DEFINED") == (not p["tbd_dependencies"])


def test_resolved_feed_values_flow_through_unchanged(committed):
    inputs = copy.deepcopy(committed["inputs"])
    case = inputs["feed_envelope"]["cases"][0]
    q = case["if_a5"]["p_feed_Pa"]
    q.update(value=1.25, status="SOURCED", evidence_class="model-derived")
    q.pop("requires")
    doc = bcg.build_document(inputs)
    lv = next(l for l in doc["axes"]["feed_state"]["levels"] if l["id"] == case["case_id"])
    assert lv["feed_state"]["p_feed_Pa"]["value"] == 1.25
    assert "p_feed_Pa" not in lv["tbd_fields"]
    for p in doc["base_points"]:
        if p["feed_level_id"] == case["case_id"]:
            assert f"feed_state:{case['case_id']}.p_feed_Pa" not in p["tbd_dependencies"]
    assert doc["hashes"]["grid_content_sha256"] != committed["hashes"]["grid_content_sha256"]


# ------------------------------------------------------------------------------------------------------ freeze
def test_freeze_refused_while_blockers_remain(committed):
    assert committed["status"] == "DRAFT_PENDING_OWNER"
    assert committed["freeze_procedure"]["blockers"] == bcg.freeze_blockers(committed)
    assert committed["freeze_procedure"]["blockers"]
    with pytest.raises(bcg.FreezeRefused):
        bcg.make_lock(committed, "0" * 64, "OWNER-DEC-TEST", "2026-09-26")
    assert not (REPO / bcg.LOCK_REL).exists(), "the grid must not be hash-locked before the owner freezes it"


def _resolved(monkeypatch, committed):
    """A synthetic, fully resolved input set (test only): every TBD filled, every PROPOSED owner-decided."""
    inputs = copy.deepcopy(committed["inputs"])
    for c in inputs["feed_envelope"]["cases"] + [{"if_a5": inputs["feed_envelope"]["xe_path"]["if_x2"]}]:
        for q in c["if_a5"].values():
            if q["status"] == "TBD":
                if "values" in q:
                    q["values"] = {k: 0.5 for k in q["values"]}
                else:
                    q["value"] = 1.0
                q.update(status="SOURCED", evidence_class="model-derived")
                q.pop("requires", None)
    inputs["feed_envelope"]["status"] = "OWNER_APPROVED"
    inputs["hall_reference"]["status"] = "OWNER_APPROVED"
    inputs["hall_reference"]["discharge_voltage"]["evaluation_set_V"]["status"] = "OWNER_DECIDED"
    modes = copy.deepcopy(bcg.FEED_MODES)
    for m in modes:
        m["xe_anode_mass_fraction"].update(status="OWNER_DECIDED" if m["id"] != "xe_start" else "DEFINITION",
                                           evidence_class="assumed", value=m["xe_anode_mass_fraction"]["value"])
    modes[1]["xe_anode_mass_fraction"]["value"] = None
    modes[1]["xe_anode_mass_fraction"]["status"] = "DEFINITION"
    mixes = [{"id": "XMIX_0p2", "value": 0.2, "unit": "-", "status": "OWNER_DECIDED", "evidence_class": "assumed",
              "source": "test", "applies_to_modes": ["mixed"]}]
    levels = copy.deepcopy(bcg.P_SOURCE_LEVELS)
    for lv, v in zip(levels[1:], (100.0, 200.0)):
        lv.update(value=v, status="OWNER_DECIDED", evidence_class="assumed", source="test")
        lv.pop("requires")
    monkeypatch.setattr(bcg, "FEED_MODES", modes)
    monkeypatch.setattr(bcg, "FEED_MODE_AXIS", dict(bcg.FEED_MODE_AXIS, status="OWNER_DECIDED"))
    monkeypatch.setattr(bcg, "XE_MIX_LEVELS", mixes)
    monkeypatch.setattr(bcg, "P_SOURCE_LEVELS", levels)
    monkeypatch.setattr(bcg, "P_SOURCE_DEFINITION", dict(bcg.P_SOURCE_DEFINITION, status="OWNER_DECIDED"))
    monkeypatch.setattr(bcg, "P_SOURCE_LEVEL_STRUCTURE", dict(bcg.P_SOURCE_LEVEL_STRUCTURE, status="OWNER_DECIDED"))
    monkeypatch.setattr(bcg, "PREREQ_AT_AUTHORING", {k: dict(v, lane_verified=True)
                                                      for k, v in bcg.PREREQ_AT_AUTHORING.items()})
    return inputs


def test_freeze_lock_on_synthetic_resolved_inputs(monkeypatch, committed, schema):
    doc = bcg.build_document(_resolved(monkeypatch, committed))
    assert bcg.freeze_blockers(doc) == []
    assert not bcg.validate(doc, schema)
    assert doc["summary"]["n_base_points_pending_tbd"] == 0 and doc["summary"]["n_evaluations_pending_tbd"] == 0
    lock = bcg.make_lock(doc, "f" * 64, "OWNER-DEC-TEST", "2026-09-26")
    assert lock["grid_content_sha256"] == doc["hashes"]["grid_content_sha256"]
    assert lock["status"] == "FROZEN"
    with pytest.raises(bcg.FreezeRefused):
        bcg.make_lock(doc, "f" * 64, "", "2026-09-26")


# --------------------------------------------------------------------------------------- prerequisites / purity
def test_missing_prerequisite_raises_clear_error(tmp_path, monkeypatch):
    with pytest.raises(bcg.PrerequisiteMissing):
        bcg.resolve_prerequisite(str(tmp_path / "nope.json"), bcg.ENV_FEED, bcg.FEED_REL, "feed envelope")
    monkeypatch.setenv(bcg.ENV_FEED, str(tmp_path / "also_missing.json"))
    with pytest.raises(bcg.PrerequisiteMissing):
        bcg.resolve_prerequisite(None, bcg.ENV_FEED, bcg.FEED_REL, "feed envelope")


def test_invalid_prerequisites_are_refused():
    feed = {"architectures": {"ids": list(bcg.ARCHITECTURES), "architecture_dependent_fields": ["p_feed_Pa"]}}
    with pytest.raises(bcg.PrerequisiteInvalid):
        bcg.extract_feed(feed, "0" * 64)
    hall = {"architectures": list(bcg.ARCHITECTURES),
            "discharge_voltage_interface": {
                "proposed_evaluation_set_V": {"value": [180, 400], "status": "PROPOSED"},
                "proposed_range_V": {"value": [180, 305]},
                "requirements": {"power_max_W": {"value": 1500}}},
            "bus_power_boundary": {"boundary_version": "bus_power_boundary_v1",
                                   "arm_specific_components": bcg.EXPECTED_ARM_COMPONENTS}}
    with pytest.raises(bcg.PrerequisiteInvalid):           # evaluation set outside the proposed range
        bcg.extract_hall_reference(hall, "0" * 64)
    hall["discharge_voltage_interface"]["proposed_evaluation_set_V"]["value"] = [180, 305]
    hall["bus_power_boundary"]["arm_specific_components"] = {"hall_only": [], "rf_hall": ["rf_source"],
                                                             "ecr_hall": ["ecr_source"]}
    with pytest.raises(bcg.PrerequisiteInvalid):           # P_source definition needs the boundary components
        bcg.extract_hall_reference(hall, "0" * 64)


def test_builder_imports_no_model_or_hall_module():
    tree = ast.parse(SCRIPT.read_text())
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    abep = {m for m in mods if m.startswith("abep_sim")}
    assert abep <= {"abep_sim.constants"}, abep
    assert not {m for m in mods if "hall" in m or "arch" in m or "julia" in m.lower()}
