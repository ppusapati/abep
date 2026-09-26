"""Hall-map production specification (docs/hallmap/HALLMAP_PRODUCTION_SPEC.md): keeps the provenance schema, the DRAFT
convergence pre-registration and the spec consistent with abep_sim/hall_map.py and abep_sim/hall_ensemble.py.

No map is generated and nothing is simulated here. The instance used below is a SYNTHETIC test fixture (obviously fake
hashes and names), never data. jsonschema is not a project dependency, so a minimal validator for exactly the keywords the
schema uses is included; it refuses any keyword it does not implement, so the schema cannot silently outgrow it.
"""
from __future__ import annotations
import copy, json, os, re

import pytest

from abep_sim import hall_map
from abep_sim.hall_ensemble import ADMISSION_FIELDS, load_ensemble

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(ROOT, "schemas", "hallmap", "hallmap_provenance_v1.json")
DRAFT_PATH = os.path.join(ROOT, "docs", "hallmap", "drafts", "hallmap_convergence_prereg_DRAFT.json")
SPEC_PATH = os.path.join(ROOT, "docs", "hallmap", "HALLMAP_PRODUCTION_SPEC.md")
PREREG_DIR = os.path.join(ROOT, "hallthruster_bridge", "prereg")


def _load(p):
    with open(p) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def schema():
    return _load(SCHEMA_PATH)


@pytest.fixture(scope="module")
def draft():
    return _load(DRAFT_PATH)


# ---------------------------------------------------------------- minimal JSON Schema (2020-12 subset) validator
_ANNOT = {"$schema", "$id", "$defs", "title", "description", "default", "examples"}
_KNOWN = {"type", "required", "properties", "additionalProperties", "const", "enum", "pattern", "items", "minItems",
          "maxItems", "uniqueItems", "minimum", "maximum", "exclusiveMinimum", "minLength", "$ref", "oneOf", "allOf",
          "not", "if", "then"} | _ANNOT
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is_type(v, t):
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


def _resolve(root, ref):
    assert ref.startswith("#/"), f"only local refs are supported: {ref}"
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def errors(inst, sch, root, path="$"):
    """List of validation errors of inst against sch (subset of JSON Schema 2020-12 used by hallmap_provenance_v1)."""
    unknown = {k for k in sch if not k.startswith("x-")} - _KNOWN
    assert not unknown, f"schema keyword(s) {unknown} at {path} are not implemented by the test validator"
    out = []
    if "$ref" in sch:
        out += errors(inst, _resolve(root, sch["$ref"]), root, path)
    if "type" in sch:
        ts = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_is_type(inst, t) for t in ts):
            return out + [f"{path}: type {type(inst).__name__} not in {ts}"]
    if "const" in sch and not (inst == sch["const"] and type(inst) is type(sch["const"])):
        out.append(f"{path}: {inst!r} != const {sch['const']!r}")
    if "enum" in sch and inst not in sch["enum"]:
        out.append(f"{path}: {inst!r} not in enum")
    if isinstance(inst, str):
        if "minLength" in sch and len(inst) < sch["minLength"]:
            out.append(f"{path}: shorter than {sch['minLength']}")
        if "pattern" in sch and not re.search(sch["pattern"], inst):
            out.append(f"{path}: {inst!r} does not match {sch['pattern']!r}")
    if _is_type(inst, "number"):
        if "minimum" in sch and inst < sch["minimum"]:
            out.append(f"{path}: < minimum")
        if "maximum" in sch and inst > sch["maximum"]:
            out.append(f"{path}: > maximum")
        if "exclusiveMinimum" in sch and inst <= sch["exclusiveMinimum"]:
            out.append(f"{path}: <= exclusiveMinimum")
    if isinstance(inst, list):
        if "minItems" in sch and len(inst) < sch["minItems"]:
            out.append(f"{path}: fewer than {sch['minItems']} items")
        if "maxItems" in sch and len(inst) > sch["maxItems"]:
            out.append(f"{path}: more than {sch['maxItems']} items")
        if sch.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in inst}) != len(inst):
            out.append(f"{path}: items not unique")
        if "items" in sch:
            for i, x in enumerate(inst):
                out += errors(x, sch["items"], root, f"{path}[{i}]")
    if isinstance(inst, dict):
        for k in sch.get("required", []):
            if k not in inst:
                out.append(f"{path}: missing required {k!r}")
        props = sch.get("properties", {})
        for k, v in inst.items():
            if k in props:
                out += errors(v, props[k], root, f"{path}.{k}")
            elif sch.get("additionalProperties") is False:
                out.append(f"{path}: additional property {k!r}")
    if "oneOf" in sch:
        n = sum(not errors(inst, s, root, path) for s in sch["oneOf"])
        if n != 1:
            out.append(f"{path}: matches {n} oneOf branches (need exactly 1)")
    for s in sch.get("allOf", []):
        out += errors(inst, s, root, path)
    if "not" in sch and not errors(inst, sch["not"], root, path):
        out.append(f"{path}: must not match {sch['not']}")
    if "if" in sch and not errors(inst, sch["if"], root, path) and "then" in sch:
        out += errors(inst, sch["then"], root, path)
    return out


def _walk(node):
    """Every sub-schema object of the schema (for keyword coverage checks)."""
    if isinstance(node, dict):
        yield node
        for k, v in node.items():
            if k in ("properties", "$defs"):
                for s in v.values():
                    yield from _walk(s)
            elif k in ("items", "not", "if", "then"):
                yield from _walk(v)
            elif k in ("oneOf", "allOf"):
                for s in v:
                    yield from _walk(s)


def _pointer_is_required(schema, pointer, node=None):
    """True if every segment of a /a/b pointer is a declared AND required property along the path (in EVERY oneOf
    branch where the path passes through a oneOf)."""
    node = schema if node is None else node
    parts = pointer.strip("/").split("/")
    if "$ref" in node:
        node = _resolve(schema, node["$ref"])
    if "oneOf" in node and "properties" not in node:
        return all(_pointer_is_required(schema, pointer, b) for b in node["oneOf"])
    part = parts[0]
    if part not in node.get("properties", {}) or part not in node.get("required", []):
        return False
    rest = "/".join(parts[1:])
    return True if not rest else _pointer_is_required(schema, rest, node["properties"][part])


# ---------------------------------------------------------------- SYNTHETIC fixture (not data)
FAKE = "0" * 64


def synthetic_instance():
    """A structurally valid provenance object with obviously synthetic values. It describes no real map."""
    return {
        "provenance_schema": "hallmap_provenance_v1",
        "hall_map_schema": {"name": "hall_map_schema_v1", "file": "hallthruster_bridge/hall_map_schema_v1.json", "sha256": FAKE},
        "map_set": {"map_set_id": "SYNTHETIC-TEST-FIXTURE", "status": "CANDIDATE", "generated_utc": "SYNTHETIC",
                    "generator": {"script": "SYNTHETIC", "git_commit": "0" * 40, "script_sha256": FAKE,
                                  "case_file": "SYNTHETIC", "case_file_sha256": FAKE}},
        "ensemble_member": {"ensemble_member_id": "synthetic-member", "transport_family": "SYNTHETIC",
                            "transport_parameters": {}, "transport_as_run": "SYNTHETIC",
                            "ensemble_file": "hallthruster_bridge/ensemble/transport_ensemble_v0.json",
                            "ensemble_file_sha256": FAKE,
                            "admission": {"promoted_from_screening_id": "synthetic-member", "campaign_id": "SYNTHETIC",
                                          "preregistration": "SYNTHETIC", "decision_file": "SYNTHETIC", "decision_sha256": FAKE,
                                          "scores_provenance_file": "SYNTHETIC", "scores_provenance_sha256": FAKE,
                                          "passing_layer1_members": ["SYNTHETIC"], "admitted_utc": "SYNTHETIC",
                                          "decided_by": "SYNTHETIC"}},
        "source_validation": {"campaign_id": "SYNTHETIC", "validation_release_file": "SYNTHETIC",
                              "validation_release_sha256": FAKE, "prereg_lock_file": "SYNTHETIC",
                              "prereg_lock_sha256": FAKE, "decision_sha256": FAKE},
        "hallthruster": {"package": "HallThruster.jl", "version": "SYNTHETIC", "pinned_commit": hall_map.pinned_commit(),
                         "installed_commit": hall_map.pinned_commit(), "pinned_toml_sha256": FAKE},
        "chemistry": {"kind": "hallthruster_builtin", "reaction_set_version": "SYNTHETIC", "limitation": "SYNTHETIC"},
        "propellant": {"gas": "SYNTHETIC", "composition_basis": "single gas"},
        "geometry": {"geometry_id": "SYNTHETIC", "version": "SYNTHETIC", "file": "synthetic/geometry.json", "sha256": FAKE,
                     "source": "SYNTHETIC", "evidence_class": "assumed", "channel_length_m": 1.0,
                     "inner_radius_m": 1.0, "outer_radius_m": 2.0, "domain_m": 3.0},
        "magnetic_field": {"bfield_id": "SYNTHETIC", "version": "SYNTHETIC", "file": "synthetic/bfield.csv", "sha256": FAKE,
                           "source": "SYNTHETIC", "evidence_class": "assumed",
                           "placement": {"align": "anode", "z_ref_in_file_mm": 0.0}, "scale_reference": "max",
                           "B_ref_T": 1.0, "shape_fixed": True,
                           "scale_mechanism": "B_ref_T scaling of the fixed-shape profile (bridge measured_bfield), solver magnetic_field_scale = 1"},
        "numerics": {"grid": {"type": "EvenGrid", "cells": 1}, "dt_s": 1.0, "duration_s": 1.0, "average_start_s": 0.0,
                     "averaging_window_s": 1.0, "num_save": 2,
                     "timestepping": {"adaptive": True, "CFL": 1.0, "min_dt_s": 1.0, "max_dt_s": 1.0, "max_small_steps": 1,
                                      "basis": "solver default at the pinned commit"},
                     "matches_admission_numerics": True,
                     "convergence": {"prereg_file": "SYNTHETIC", "prereg_sha256": FAKE, "verdict": "NOT_RUN"}},
        "wall": {"wall_loss_model": "SYNTHETIC", "ion_wall_losses": False, "shielded": False, "basis": "SYNTHETIC"},
        "facility_ingestion": False,
        "axes": [{"name": "Vd", "unit": "V", "values": [0.0, 1.0], "bounds_source": "SYNTHETIC", "evidence_class": "assumed"}],
        "fields_present": list(hall_map.REQUIRED_FIELDS),
        "observables_basis": {
            "thrust": "thrust_N as defined in hall_map_schema_v1 (1-D ion momentum flux); solver apply_thrust_divergence_correction not enabled by the bridge; no P5 beam-efficiency reading (A/B) applied",
            "failed_node_values": "null for every non-flag field of a node without solver output; flags false; never a number"},
        "trust": {"performance_rule": "HallMap query 'trustworthy': every surrounding grid node converged AND interpolated sustained > 0.999 AND every surrounding node chemistry_trustworthy",
                  "wall_life_rule": "HallMap query 'wall_life_trustworthy': performance trustworthy AND meta.ion_wall_losses is true AND every surrounding node wall_life_trustworthy",
                  "node_counts": {"total": 1, "converged": 0, "sustained": 0, "chemistry_trustworthy": 0, "wall_life_trustworthy": 0}},
        "validity_domain": {"axis_bounds_only": True, "extrapolation": "forbidden", "chemistry_domain": "SYNTHETIC",
                            "member_validation_domain": {"description": "SYNTHETIC", "source": "SYNTHETIC"},
                            "transfer_statement": "SYNTHETIC"},
        "evidence": {"evidence_level": 7, "quantity_type": "model-derived", "source": "SYNTHETIC", "uncertainty": "SYNTHETIC",
                     "applicability_domain": "SYNTHETIC", "validation_status": "SYNTHETIC", "transformation_chain": "SYNTHETIC"},
        "raw_records": {"file": "SYNTHETIC", "sha256_canonical_jsonl": FAKE, "per_reaction_chemistry_retained": True},
    }


# ---------------------------------------------------------------- schema
def test_schema_parses_and_uses_only_supported_keywords(schema):
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == "hallmap_provenance_v1" and schema["type"] == "object"
    for sub in _walk(schema):
        unknown = {k for k in sub if not k.startswith("x-")} - _KNOWN - {"properties"}
        assert not unknown, unknown
        if "pattern" in sub:
            re.compile(sub["pattern"])
            assert "(?" not in sub["pattern"], "inline regex flags are not ECMA-262 (JSON Schema) portable"
        if "$ref" in sub:
            _resolve(schema, sub["$ref"])
    assert errors(synthetic_instance(), schema, schema) == []


def test_fields_present_is_exactly_hall_map_required_fields(schema):
    fp = schema["properties"]["fields_present"]
    assert set(fp["items"]["enum"]) == set(hall_map.REQUIRED_FIELDS)
    assert fp["minItems"] == fp["maxItems"] == len(hall_map.REQUIRED_FIELDS) and fp["uniqueItems"] is True
    assert "fields_present" in schema["required"]
    inst = synthetic_instance()
    inst["fields_present"] = list(hall_map.REQUIRED_FIELDS)[:-1]           # one required field missing
    assert errors(inst, schema, schema)


def test_every_required_meta_key_maps_to_a_required_provenance_path(schema):
    mapping = {k: v for k, v in schema["x-hall_map_meta_mapping"].items() if k != "description"}
    assert set(mapping) == set(hall_map.REQUIRED_META)
    for key, pointer in mapping.items():
        assert _pointer_is_required(schema, pointer), f"meta.{key} -> {pointer} is not a required provenance path"


def test_trust_flags_are_required_fields_and_both_rules_are_recorded(schema):
    for flag in ("converged", "sustained", "chemistry_trustworthy", "wall_life_trustworthy"):
        assert flag in hall_map.REQUIRED_FIELDS
    trust = schema["properties"]["trust"]
    assert {"performance_rule", "wall_life_rule"} <= set(trust["required"])
    assert "ion_wall_losses" in trust["properties"]["wall_life_rule"]["const"]
    assert "chemistry_trustworthy" in trust["properties"]["performance_rule"]["const"]
    assert set(trust["properties"]["node_counts"]["required"]) >= {"converged", "sustained", "chemistry_trustworthy",
                                                                   "wall_life_trustworthy"}


def test_admission_record_and_pin_and_chemistry_domain(schema):
    adm = schema["$defs"]["admission_record"]
    assert set(ADMISSION_FIELDS) <= set(adm["required"])
    assert re.fullmatch(schema["$defs"]["git_commit"]["pattern"], hall_map.pinned_commit())
    proj = next(b for b in schema["properties"]["chemistry"]["oneOf"]
                if b["properties"]["kind"]["const"] == "project_propellant_config")
    assert proj["properties"]["f_out_tolerance"]["const"] == 1e-12
    assert proj["properties"]["rate_files"]["items"]["properties"]["validity_status"]["const"] == "verified"
    inst = synthetic_instance()
    del inst["ensemble_member"]["admission"]["decision_sha256"]            # admission evidence is not optional
    assert errors(inst, schema, schema)


def test_calibration_nuisance_can_never_be_an_axis(schema):
    forbidden = set(schema["$defs"]["forbidden_axis_names"]["enum"])
    assert set(load_ensemble()["calibration_nuisance"]) <= forbidden
    for name in sorted(load_ensemble()["calibration_nuisance"]):
        inst = synthetic_instance()
        inst["axes"].append({"name": name, "unit": "-", "values": [0.0, 1.0], "bounds_source": "SYNTHETIC",
                             "evidence_class": "assumed"})
        assert any("must not match" in e for e in errors(inst, schema, schema)), name


def test_flight_maps_own_geometry_and_frozen_convergence(schema):
    inst = synthetic_instance()
    inst["facility_ingestion"] = True
    assert errors(inst, schema, schema)
    for block, bad in (("magnetic_field", "bfield/p5_vacuum_Br_centerline_1p6kW.csv"), ("geometry", "cases/echt_n2.json")):
        inst = synthetic_instance()
        inst[block]["file"] = bad                                          # P5/ECHT evidence is never a design input
        assert errors(inst, schema, schema), bad
    inst = synthetic_instance()
    inst["numerics"]["convergence"]["prereg_file"] = "docs/hallmap/drafts/hallmap_convergence_prereg_DRAFT.json"
    assert errors(inst, schema, schema)
    inst = synthetic_instance()
    inst["map_set"]["status"] = "FROZEN"                                  # FROZEN needs convergence verdict PASS
    assert errors(inst, schema, schema)
    inst["numerics"]["convergence"]["verdict"] = "PASS"
    assert errors(inst, schema, schema) == []


# ---------------------------------------------------------------- DRAFT convergence pre-registration
def test_convergence_draft_is_a_draft_outside_prereg(draft):
    assert draft["status"] == "DRAFT_PENDING_OWNER"
    assert draft["frozen"] is False and draft["registered"] is None and draft["decided_by"] is None
    assert draft["hash_lock"] is None and draft["id"].endswith("_DRAFT")
    real = os.path.realpath(DRAFT_PATH)
    assert not real.startswith(os.path.realpath(PREREG_DIR) + os.sep)
    assert os.path.realpath(os.path.join(ROOT, "docs", "hallmap", "drafts")) == os.path.dirname(real)
    assert not [f for f in os.listdir(PREREG_DIR) if "hallmap" in f.lower()]


def test_convergence_draft_refinements_and_proposed_tolerances(draft):
    ref = {r["id"]: r for r in draft["refinements"]}
    assert ref["R1_grid"]["change"]["cells"] == {"baseline": 200, "refined": 400}
    dt = ref["R2_dt"]["change"]["dt_s"]
    assert dt["refined"] == pytest.approx(dt["baseline"] / 2)
    du = ref["R3_duration"]["change"]["duration_s"]
    assert du["refined"] == pytest.approx(2 * du["baseline"])
    obs = draft["observables"]
    assert {"discharge_current_A", "thrust_N", "mass_eff", "wall_ion_flux_m2s"} <= set(obs)
    for name, o in obs.items():
        assert o["status"] == "PROPOSED", name
        assert isinstance(o["proposed_tolerance"], float) and o["proposed_tolerance"] > 0, name
        assert o["rationale"] and all(isinstance(r, str) and r for r in o["rationale"]), name
    assert all(r["status"].startswith(("PROPOSED", "OPTIONAL")) for r in draft["refinements"])
    assert draft["owner_decisions_required"]


def test_convergence_draft_baseline_equals_admission_numerics(draft):
    """The proposed baseline is the numerics every P5-N2 case was run with (read only)."""
    cases = _load(os.path.join(ROOT, "hallthruster_bridge", "cases", "p5_n2.json"))["cases"]
    got = {(c["cells"], c["dt_s"], c["duration_s"], c["average_start_s"]) for c in cases}
    b = draft["baseline_numerics"]
    assert got == {(b["cells"], b["dt_s"], b["duration_s"], b["average_start_s"])}


# ---------------------------------------------------------------- spec document
def test_spec_covers_fields_nuisance_and_member_gate():
    text = open(SPEC_PATH).read()
    for f in hall_map.REQUIRED_FIELDS:
        assert f"`{f}`" in text, f
    for k in load_ensemble()["calibration_nuisance"]:
        assert f"`{k}`" in text, k
    for token in ("require_admitted", "wall_life_trustworthy", "chemistry_trustworthy", "f_out", "DRAFT_PENDING_OWNER",
                  "schemas/hallmap/hallmap_provenance_v1.json"):
        assert token in text, token
