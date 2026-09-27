"""W1 feed-state closure v1 (fo_feed_state_closure).

Checks that docs/architecture_comparison/feed_state_closure/build_feed_state_closure.py reproduces the committed
outputs (--check), that the JSON validates against its schema, that mass and species fractions close, that every test
point traces to a closed design candidate and a frozen altitude/solar case, that the ground surrogates conserve the
oxygen-element mass, that every design input carries a source and an evidence class (lane-16 contract, missing input
raises), and that no Hall closure, screening candidate or P5 calibration nuisance appears.
Run: python -m pytest -q tests/test_feed_state_closure.py   (~25 s; the reproduction test runs the builder once).
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "docs" / "architecture_comparison" / "feed_state_closure"
SCRIPT = DIR / "build_feed_state_closure.py"
JSON_PATH = DIR / "feed_state_closure_v1.json"
SCHEMA_PATH = DIR / "feed_state_closure_v1.schema.json"
MD_PATH = DIR / "FEED_STATE_CLOSURE.md"
EVIDENCE = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
CASES = {f"alt{a}_{l}" for a in (180, 200, 230) for l in ("low", "mean", "high")}
FORBIDDEN_TOKENS = ("ensemble_member_id", "sgb-screen", "screening_candidate", "registration", "coil_shape",
                    "beam_efficiency", "facility_ingestion", "hall_map", "hall_ensemble", "plasma_devices",
                    "plasma_chem", "hall1d", "hallthruster_bridge/ensemble")


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(JSON_PATH.read_text())


def _load(path: Path, name: str):
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ minimal JSON-schema validator (keywords in use)
def _types(v):
    if v is None:
        return {"null"}
    if isinstance(v, bool):
        return {"boolean"}
    if isinstance(v, int):
        return {"integer", "number"}
    if isinstance(v, float):
        return {"number"}
    if isinstance(v, str):
        return {"string"}
    if isinstance(v, list):
        return {"array"}
    if isinstance(v, dict):
        return {"object"}
    return set()


def validate(v, s, path="$") -> list[str]:
    errs = []
    if "const" in s and v != s["const"]:
        errs.append(f"{path}: {v!r} != const {s['const']!r}")
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: {v!r} not in {s['enum']}")
    if "type" in s:
        t = s["type"] if isinstance(s["type"], list) else [s["type"]]
        if not (_types(v) & set(t)):
            return errs + [f"{path}: type {_types(v)} not {t}"]
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in s and v < s["minimum"]:
            errs.append(f"{path}: {v} < {s['minimum']}")
        if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
            errs.append(f"{path}: {v} <= {s['exclusiveMinimum']}")
        if "maximum" in s and v > s["maximum"]:
            errs.append(f"{path}: {v} > {s['maximum']}")
    if isinstance(v, dict):
        for r in s.get("required", []):
            if r not in v:
                errs.append(f"{path}: missing {r}")
        props = s.get("properties", {})
        ap = s.get("additionalProperties")
        if ap is False:
            extra = set(v) - set(props)
            if extra:
                errs.append(f"{path}: additional {sorted(extra)}")
        elif isinstance(ap, dict):
            for k in set(v) - set(props):
                errs += validate(v[k], ap, f"{path}.{k}")
        for k, sub in props.items():
            if k in v:
                errs += validate(v[k], sub, f"{path}.{k}")
    if isinstance(v, list):
        if "minItems" in s and len(v) < s["minItems"]:
            errs.append(f"{path}: fewer than {s['minItems']} items")
        if "items" in s:
            for i, x in enumerate(v):
                errs += validate(x, s["items"], f"{path}[{i}]")
    return errs


def test_schema_uses_only_supported_keywords():
    ok = {"$schema", "$id", "title", "description", "type", "required", "properties", "additionalProperties", "enum",
          "const", "items", "minimum", "exclusiveMinimum", "maximum", "minItems"}

    def walk(s, in_props=False):
        if isinstance(s, dict):
            for k, v in s.items():
                if not in_props:
                    assert k in ok, f"unsupported schema keyword {k}"
                walk(v, in_props=(k == "properties" and not in_props))
        elif isinstance(s, list):
            for x in s:
                walk(x)
    walk(json.loads(SCHEMA_PATH.read_text()))


def test_schema_rejects_bare_valve_outlet_record(doc):
    schema = json.loads(SCHEMA_PATH.read_text())
    bad = copy.deepcopy(doc)
    cid = next(iter(bad["valve_outlet"]))
    k = next(iter(bad["valve_outlet"][cid]))
    del bad["valve_outlet"][cid][k]["nominal"]["evidence_class"]
    bad["test_points"]["phase1_knee_N2"][0].pop("status")
    errs = validate(bad, schema)
    assert any("nominal: missing evidence_class" in e for e in errs)
    assert any("phase1_knee_N2[0]: missing status" in e for e in errs)


def test_validates_against_schema(doc):
    errs = validate(doc, json.loads(SCHEMA_PATH.read_text()))
    assert not errs, errs[:10]


def test_builder_reproduces_committed_outputs():
    r = subprocess.run([sys.executable, str(SCRIPT), "--check"], cwd=REPO, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr


# ------------------------------------------------------------------------------------------------ independence
def test_no_hall_closure_or_calibration_nuisance(doc):
    text = json.dumps(doc)
    for tok in FORBIDDEN_TOKENS:
        assert tok not in text, f"forbidden token {tok!r} in the closure output"
    src = SCRIPT.read_text()
    for mod in ("abep_sim.hall_map", "abep_sim.hall_ensemble", "abep_sim.plasma", "abep_sim.hall1d",
                "abep_sim.archengine", "hallthruster_bridge"):
        assert f"import {mod}" not in src and f"from {mod}" not in src


def test_architecture_independent(doc):
    assert doc["architectures"] == ["hall_only", "rf_hall", "ecr_hall"]
    for cid, rows in doc["valve_outlet"].items():
        for k, r in rows.items():
            assert not ({"hall_only", "rf_hall", "ecr_hall"} & set(json.dumps(r["nominal"]).split('"')))
    for t in doc["test_points"]["phase2_common_condition"]:
        assert t["arms"] == ["hall_only", "rf_hall", "ecr_hall"]


def test_literature_is_context_only(doc):
    for c in doc["published_comparables"]:
        assert c["role"] == "context_only" and c["ref"] in doc["references"]
    for rid, r in doc["references"].items():
        assert r["doi"] and r["accessed"] and r["access"] in ("full_text_open", "abstract_only")


# ------------------------------------------------------------------------------------------------ design inputs
def test_design_inputs_have_source_and_evidence(doc):
    for cid, d in doc["design_input_documents"].items():
        for name, e in d["inputs"].items():
            assert isinstance(e["source"], str) and e["source"].strip(), (cid, name)
            assert e["evidence_class"] in EVIDENCE, (cid, name)
    for e in doc["design_input_inventory"]:
        if e["status"] == "TBD":
            assert e["value"] is None and "TBD" in e["source"]
        elif e["status"] == "PROPOSED":
            assert e["evidence_class"] in EVIDENCE and e["source"]
    for c in doc["candidates"]:
        assert c["status"] == "PROPOSED" and c["evidence_class"] == "assumed"


def test_missing_design_input_raises(doc):
    fe = _load(REPO / "scripts" / "architecture" / "build_feed_envelope.py", "_fsc_lane16")
    d = copy.deepcopy(next(iter(doc["design_input_documents"].values())))
    fe.validate_design_inputs(d)
    del d["inputs"]["intake.area_m2"]
    with pytest.raises(fe.MissingDesignInput):
        fe.validate_design_inputs(d)
    d2 = copy.deepcopy(next(iter(doc["design_input_documents"].values())))
    d2["inputs"]["intake.phi"]["evidence_class"] = "guess"
    with pytest.raises(fe.InvalidDesignInput):
        fe.validate_design_inputs(d2)


def test_sizing_rule_reproduces_design_thrust(doc):
    k = doc["design_axes"]["design_case"]
    for c in doc["candidates"]:
        if c["id"] in doc["valve_outlet"]:
            D = doc["valve_outlet"][c["id"]][k]["intake_drag"]["D_int_mN"]
            assert math.isclose(D, c["design_thrust_mN"], rel_tol=1e-9)


# ------------------------------------------------------------------------------------------------ conservation
def test_valve_outlet_closes(doc):
    assert doc["valve_outlet"], "no closed candidate"
    for cid, rows in doc["valve_outlet"].items():
        assert doc["closure"][cid]["status"] == "CLOSED"
        assert set(rows) == CASES
        for k, r in rows.items():
            n = r["nominal"]
            assert math.isclose(sum(n["mdot_s_kgps"].values()), n["mdot_total_kgps"], rel_tol=1e-9)
            assert math.isclose(sum(n["x_s"].values()), 1.0, rel_tol=1e-9)
            assert math.isclose(sum(n["w_s"].values()), 1.0, rel_tol=1e-9)
            assert math.isclose(n["p_feed_Pa"], n["setpoint_Pa"], rel_tol=1e-3)
            assert 300.0 <= n["T_feed_K"] <= 500.0
            rng = r["scenario_range"]
            assert rng["mdot_total_kgps"]["min"] <= n["mdot_total_kgps"] * (1 + 1e-12)
            assert rng["mdot_total_kgps"]["max"] >= n["mdot_total_kgps"] * (1 - 1e-12)
            assert rng["kind"] == "scenario_set"
            # ground surrogate conserves the total and the O-element mass
            a = r["ground"]["air_surrogate_N2_O2"]
            assert math.isclose(a["mdot_N2_kgps"] + a["mdot_O2_kgps"], n["mdot_total_kgps"], rel_tol=1e-9)
            assert math.isclose(a["mdot_O2_kgps"], n["mdot_s_kgps"]["O"] + n["mdot_s_kgps"]["O2"], rel_tol=1e-9)
            assert a["particle_flow_ratio_ground_over_flight"] <= 1.0 + 1e-12


def test_not_closed_candidates_have_reasons_and_no_test_points(doc):
    tp_cands = {t["candidate"] for ph in doc["test_points"].values() for t in ph}
    for cid, cl in doc["closure"].items():
        if cl["status"] != "CLOSED":
            assert cl["failure_reasons"] and cl["nominal_setpoint_Pa"] is None
            assert cid not in tp_cands and cid not in doc["valve_outlet"]
        else:
            assert cl["nominal_setpoint_Pa"] == min(cl["common_feasible_setpoints_Pa"])


# ------------------------------------------------------------------------------------------------ test points
def test_test_points_traceable(doc):
    tp = doc["test_points"]
    ids = [t["id"] for ph in tp.values() for t in ph]
    assert len(ids) == len(set(ids))
    k_des = doc["design_axes"]["design_case"]
    for t in tp["phase1_knee_N2"]:
        rows = doc["valve_outlet"][t["candidate"]]
        md = [r["nominal"]["mdot_total_kgps"] for r in rows.values()]
        if t["id"].endswith("-BFL"):
            lo = min(r["mdot_total_kgps_bracket"]["lower"] for r in rows.values())
            assert math.isclose(t["mdot_N2_kgps"], lo, rel_tol=1e-9) and lo < min(md)
            continue
        assert min(md) * (1 - 1e-9) <= t["mdot_N2_kgps"] <= max(md) * (1 + 1e-9)
        for case in t["trace"]["from"].values():
            assert case in CASES
    for cid in doc["valve_outlet"]:
        levels = [t for t in tp["phase1_knee_N2"] if t["candidate"] == cid and t["id"].split("-")[-1].startswith("L")]
        assert math.isclose(levels[0]["mdot_N2_kgps"], doc["valve_outlet"][cid][k_des]["nominal"]["mdot_total_kgps"],
                            rel_tol=1e-9)
    for t in tp["phase3_absolute_demonstration"]:
        assert t["trace"]["case"] in CASES
        r = doc["valve_outlet"][t["candidate"]][t["trace"]["case"]]
        if t["gas"] == "N2":
            assert math.isclose(t["mdot_N2_kgps"], r["nominal"]["mdot_total_kgps"], rel_tol=1e-9)
    n_closed = len(doc["valve_outlet"])
    assert len(tp["phase3_absolute_demonstration"]) == 2 * 9 * n_closed
    op2 = [t for t in tp["phase2_common_condition"] if t["operating_point"] == "OP2"]
    assert all(t["mdot_N2_kgps"] is None and t["value_status"].startswith("TBD") for t in op2)


def test_atomic_oxygen_not_claimed_on_ground(doc):
    ao = doc["atomic_oxygen"]
    assert ao["can_atomic_O_be_supplied_from_bottles"] is False
    proposed = [s for s in ao["surrogates"] if s.get("status") == "PROPOSED"]
    assert [s["id"] for s in proposed] == ["S-O2E"]


def test_milestones_and_owner_decisions(doc):
    assert doc["milestones"]["supports"] == ["A"]
    ids = [o["id"] for o in doc["owner_decisions_DI1"]]
    assert ids == [f"DI-1.{i}" for i in range(1, len(ids) + 1)]
    md = MD_PATH.read_text()
    assert "DRAFT for owner review" in md and "Owner decisions needed to freeze DI-1" in md


# ------------------------------------------------------------------------------------------------ backflow (FC-01)
def test_backflow_self_consistent_bracket(doc):
    sens_ids = {s["id"] for s in doc["design_axes"]["sensitivities"]}
    assert "SEN-BACKFLOW-0.5" in sens_ids
    union_lo = doc["mfc_range_requirement"]["mdot_min_kgps"]
    for cid, rows in doc["valve_outlet"].items():
        for k, r in rows.items():
            b = r["backflow_self_consistent"]
            assert b["closed"] and 0.0 < b["b"] < 1.0
            assert 0.0 < b["delivered_factor"] < 1.0
            assert math.isclose(b["mdot_total_kgps"], b["delivered_factor"] * r["nominal"]["mdot_total_kgps"],
                                rel_tol=1e-9)
            assert math.isclose(b["CR_required"], r["nominal"]["setpoint_Pa"] / b["p_plenum_Pa"], rel_tol=1e-9)
            br = r["mdot_total_kgps_bracket"]
            assert br["lower"] <= b["mdot_total_kgps"] * (1 + 1e-12)
            assert br["lower"] <= r["scenario_range"]["mdot_total_kgps"]["min"] * (1 + 1e-12)
            assert br["upper"] >= r["nominal"]["mdot_total_kgps"] * (1 - 1e-12)
            assert union_lo <= br["lower"] * (1 + 1e-12)
    for t in doc["test_points"]["phase3_absolute_demonstration"]:
        r = doc["valve_outlet"][t["candidate"]][t["trace"]["case"]]
        assert t["mdot_backflow_lower_kgps"] == r["mdot_total_kgps_bracket"]["lower"]


def test_sensitivity_ranking_puts_closure_loss_first(doc):
    for sr in doc["sensitivity_ranking"]:
        keys = [(-e["cases_losing_closure"], -e["max_rel_change_mdot"]) for e in sr["ranked"]]
        assert keys == sorted(keys)
        ids = {e["id"] for e in sr["ranked"]}
        assert "SC-BACKFLOW" in ids and set(sr["ranked_by_x_O"]) <= ids and set(sr["ranked_by_T_feed"]) <= ids
        xo = {e["id"]: e["max_abs_change_x_O"] for e in sr["ranked"]}
        vals = [xo[i] for i in sr["ranked_by_x_O"]]
        assert vals == sorted(vals, reverse=True)


def test_phase2_cross_references_iso_power_points(doc):
    for t in doc["test_points"]["phase2_common_condition"]:
        if t["operating_point"] in ("OP2", "OP3"):
            assert t["iso_power_reference"].startswith(t["operating_point"] + "H")


def test_knee_levels_missing_draft_raises(monkeypatch):
    mod = _load(SCRIPT, "_fsc_builder")
    monkeypatch.setattr(mod, "LANE25_DRAFT_REL", "docs/architecture_comparison/does_not_exist.json")
    with pytest.raises(mod.FeedClosureError):
        mod._knee_levels()


# ------------------------------------------------------------------ owner control C2 (A1 addendum): flight status
FS_FLIGHT = "PROPOSED_FLIGHT_REPRESENTATIVE"
FS_GROUND = "GROUND_QUALIFICATION_POINT"


def test_flight_status_labels_c2(doc):
    fsc = doc["flight_status_control"]
    assert fsc["control"] == "C2_W1_flight_status"
    assert set(fsc["values"]) == {FS_FLIGHT, FS_GROUND}
    assert (REPO / fsc["decision_file"]).exists()
    assert any(f["path"] == fsc["decision_file"] for f in doc["provenance"]["input_files"])
    n_vo = {FS_FLIGHT: 0, FS_GROUND: 0}
    for rows in doc["valve_outlet"].values():
        for r in rows.values():
            for rec in (r, r["nominal"], r["backflow_self_consistent"]):
                assert rec["flight_status"] == FS_FLIGHT
                assert rec["status"] == "PROPOSED (candidate-conditional)"
                assert rec["evidence_class"] == "model-derived (from assumed inputs)"
            n_vo[r["flight_status"]] += 1
    assert fsc["counts"]["valve_outlet_records"] == n_vo
    tp = doc["test_points"]
    for t in tp["phase1_knee_N2"]:
        assert t["flight_status"] == FS_GROUND
    for t in tp["phase2_common_condition"]:
        want = FS_GROUND if t["operating_point"] == "OP2" else FS_FLIGHT
        assert t["flight_status"] == want, t["id"]
    for t in tp["phase3_absolute_demonstration"]:
        assert t["flight_status"] == FS_FLIGHT
    for ph, pts in tp.items():
        assert fsc["counts"]["test_points"][ph] == {v: sum(1 for t in pts if t["flight_status"] == v)
                                                    for v in (FS_FLIGHT, FS_GROUND)}


def test_schema_rejects_missing_or_wrong_flight_status(doc):
    schema = json.loads(SCHEMA_PATH.read_text())
    bad = copy.deepcopy(doc)
    cid = next(iter(bad["valve_outlet"]))
    k = next(iter(bad["valve_outlet"][cid]))
    del bad["valve_outlet"][cid][k]["flight_status"]
    assert validate(bad, schema)
    bad = copy.deepcopy(doc)
    bad["test_points"]["phase3_absolute_demonstration"][0]["flight_status"] = FS_GROUND
    assert validate(bad, schema)
    bad = copy.deepcopy(doc)
    bad["test_points"]["phase2_common_condition"][0]["flight_status"] = "FLIGHT_CONDITION"
    assert validate(bad, schema)
    bad = copy.deepcopy(doc)
    bad["test_points"]["phase1_knee_N2"][0]["flight_status"] = FS_FLIGHT
    assert validate(bad, schema)
