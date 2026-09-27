"""W4 capability-demonstration preparation (fo_capability_demo_prep; docs/experiments/capability_demo/) and the metrology
measurement specification (docs/experiments/instrumentation/metrology_spec/).

Checks: byte-for-byte reproduction from sha256-pinned inputs; missing / changed inputs raise; number discipline (every
number is a quantity with unit, evidence class and source); nothing claims a demonstration; PROPOSED thresholds; targets
copied exactly from the instrumentation definition; S1-C4 category coverage; every bus_power_boundary_v1 component
exactly once; the pass/fail analysis functions (on clearly synthetic test vectors, never written as data); the S1-C4
record-item validator incl. the owner addendum A3 cathode-temperature labelling rule; the A3 metrology standards.
Fast (well under a second of computation); no Julia, no simulator run.
"""
from __future__ import annotations

import functools
import importlib.util
import json
import math
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "experiments" / "capability_demo"
SPEC_DIR = ROOT / "docs" / "experiments" / "instrumentation" / "metrology_spec"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load("_test_capdemo_builder", DIR / "build_capability_demo_prep.py")
A = B.A


@functools.lru_cache(maxsize=None)
def _doc():
    return json.loads((DIR / "capability_demo_prep_v1.json").read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def _spec():
    return json.loads((SPEC_DIR / "metrology_measurement_spec_v1.json").read_text(encoding="utf-8"))


def _ins():
    return json.loads((ROOT / B.INS_REL).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------------------- build
def test_reproduces_byte_for_byte():
    outs = B.build_all()
    for p, s in outs.items():
        assert p.read_text(encoding="utf-8") == s, p
    assert B.main(["--check"]) == 0


def test_outputs_only_in_allowed_paths_and_never_the_s1c4_artifact():
    allowed = ("docs/experiments/capability_demo/", "docs/experiments/instrumentation/metrology_spec/")
    for p in B.build_all():
        rel = p.relative_to(ROOT).as_posix()
        assert rel.startswith(allowed), rel
        assert not rel.startswith("docs/experiments/instrumentation/raw/")
        assert rel != _doc()["s1_contract"]["artifact_path"]


def test_inputs_pinned_and_tamper_detected(tmp_path):
    assert B.verify_inputs() == B.PINNED
    for rel in B.PINNED:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tmp_path / rel)
    old = B.ROOT
    try:
        B.ROOT = tmp_path
        assert B.verify_inputs() == B.PINNED
        with open(tmp_path / B.A3_REL, "a", encoding="utf-8") as f:
            f.write(" ")
        with pytest.raises(B.InputChanged):
            B.verify_inputs()
        (tmp_path / B.A3_REL).unlink()
        with pytest.raises(FileNotFoundError):
            B.verify_inputs()
    finally:
        B.ROOT = old


# --------------------------------------------------------------------------------------------- evidence discipline
def test_number_discipline_and_tamper_detection():
    assert B.numeric_leaf_errors(_doc()) == []
    assert B.numeric_leaf_errors(_spec()) == []
    bad = json.loads(json.dumps(_doc()))
    bad["demonstrations"][0]["analysis"]["bare"] = 0.5
    assert B.numeric_leaf_errors(bad)
    with pytest.raises(ValueError):
        B.validate(bad)
    bad = json.loads(json.dumps(_doc()))
    bad["planning_tables"]["low_dof_threshold"]["evidence_class"] = "guessed"
    assert B.numeric_leaf_errors(bad)
    with pytest.raises(ValueError):
        B.q(float("nan"), "x", "assumed", "s")
    with pytest.raises(ValueError):
        B.q(1.0, "x", "guessed", "s")


def test_never_claims_a_demonstration_and_thresholds_proposed():
    doc = _doc()
    assert doc["status"] == "DRAFT_PENDING_OWNER" and _spec()["status"] == "DRAFT_PENDING_OWNER"
    assert "No calibration has been performed" in doc["not_a_demonstration"]
    for t in doc["proposed_thresholds"]:
        assert t["status"] == "PROPOSED" and t["evidence_class"] == "assumed" and t["id"].startswith("CD-P-")
    for c in doc["calibration_plan_candidates"]:
        assert c["status"] == "PROPOSED"
    bad = json.loads(json.dumps(doc))
    bad["status"] = "DEMONSTRATED"
    with pytest.raises(ValueError):
        B.validate(bad)
    # every record item template declares evidence 'measured' but carries no number
    for d in doc["demonstrations"]:
        du = d["record"]["demonstrated_uncertainty"]
        assert du["evidence_class"] == "measured" and isinstance(du["value"], str)


def test_owner_decisions_pinned_and_a3_carried():
    doc = _doc()
    files = {o["file"] for o in doc["owner_decisions"]}
    assert files == {B.OD_REL, B.A1_REL, B.A2_REL, B.A3_REL}
    a3 = json.loads((ROOT / B.A3_REL).read_text(encoding="utf-8"))
    assert doc["a3_rules_carried"]["cathode_temperature"] == a3["decisions"]["cathode_temperature"]
    assert doc["decided_inputs"]["k_planning"]["value"] == 2.0
    assert "v1-r2" in doc["a3_rules_carried"]["instrumentation_version"]


def test_targets_copied_exactly_from_instrumentation_definition():
    ins = _ins()
    t = _doc()["lane25_and_w4_targets"]
    for key in ("u_T_max", "u_P_max", "u_inst_max"):
        for n, v in ins["requirement_basis"]["lane25_by_n"].items():
            assert t[key][f"n={n}"]["value"] == v[key]["value"]
    thr = {x["id"]: x for x in ins["proposed_thresholds"]}
    for tid in ("I-U-ABS-T", "I-U-ABS-P", "I-U-ID-FLOOR"):
        assert t[tid]["value"] == thr[tid]["value"] and t[tid]["status"] == "PROPOSED"


def test_references_cited_exist():
    doc = _doc()
    ids = {r["id"] for r in doc["references"]}
    text = json.dumps(doc) + json.dumps(_spec())
    import re
    for ref in set(re.findall(r"REF-[A-Z0-9-]+[A-Z0-9]", text)):
        assert ref in ids, ref
    for r in doc["references"]:
        assert r["access"]


# --------------------------------------------------------------------------------------------- scope and contract
def test_seven_owner_items_present():
    titles = " | ".join(d["title"] for d in _doc()["demonstrations"])
    for needle in ("thrust-stand force calibration", "mass-change", "reinstallation reproducibility",
                   "bus_power_boundary_v1", "low-flow range", "gas correction", "zero drift", "B(z)",
                   "synchronization", "temperature-channel", "A3 cathode"):
        assert needle in titles, needle
    for d in _doc()["demonstrations"]:
        for k in ("equipment", "procedure", "repeats", "analysis", "acceptance", "record", "failure_meaning"):
            assert d[k], (d["id"], k)


def test_s1c4_contract_matches_gate():
    s1 = json.loads((ROOT / B.S1_REL).read_text(encoding="utf-8"))
    c4 = next(c for c in s1["conditions"] if c["id"] == "S1-C4")
    req = next(r for r in c4["alternatives"][0]["rules"] if r["type"] == "covers")["required"]
    s = _doc()["s1_contract"]
    assert s["required_categories"] == req
    assert set(s["uncovered_categories"]) == {"pressure", "species_divergence"}
    assert s["artifact_path"] == "docs/experiments/instrumentation/capability_demonstration_v1.json"


def test_every_bus_power_component_exactly_once_and_compressor_never_numeric():
    ins = _ins()
    cd03 = next(d for d in _doc()["demonstrations"] if d["id"] == "CD-03")
    comps = [c["component"] for c in cd03["channels"]]
    assert sorted(comps) == sorted(c["component"] for c in ins["bus_power_channels"])
    assert len(comps) == len(set(comps))
    comp = next(c for c in cd03["channels"] if c["component"] == "compressor")
    assert comp["lab_status"] == "ABSENT_IN_LAB" and "never zero" in comp["demonstration"]
    archs = {a for c in cd03["channels"] for a in c["architectures"]}
    assert archs == set(B.ARCHS)


def test_mfc_range_from_feed_state_closure():
    feed = json.loads((ROOT / B.FEED_REL).read_text(encoding="utf-8"))["mfc_range_requirement"]
    r = next(d for d in _doc()["demonstrations"] if d["id"] == "CD-04")["range"]
    assert r["mdot_min"]["value"] == pytest.approx(feed["mdot_min_kgps"] * 1e6, rel=1e-5)
    assert r["mdot_min"]["value"] == pytest.approx(0.030, abs=0.001)
    ratio = feed["mdot_max_kgps"] / feed["mdot_min_kgps"]
    assert r["turndown_ratio"]["value"] == pytest.approx(ratio, rel=1e-5)
    assert r["single_device_u_at_min"]["value"] > 1.0  # one device cannot resolve the low end
    assert r["ranges_needed"]["min_setpoint_fraction=0.2"]["value"] == math.ceil(math.log(ratio) / math.log(5))


# --------------------------------------------------------------------------------------------- analysis functions
# (synthetic vectors below are test fixtures, not data)
def test_type_a_and_upper_bound():
    t = A.type_a([1.0, 2.0, 3.0, 4.0])
    assert t["mean"] == 2.5 and t["nu"] == 3 and t["s"] == pytest.approx(math.sqrt(5 / 3))
    assert A.sigma_upper_bound(1.0, 9, 0.95) == pytest.approx(1.6452, rel=1e-4)
    assert A.sigma_upper_bound(1.0, 29, 0.95) < A.sigma_upper_bound(1.0, 5, 0.95)
    with pytest.raises(ValueError):
        A.type_a([1.0])
    with pytest.raises(ValueError):
        A.type_a([1.0, float("nan")])
    with pytest.raises(ValueError):
        A.type_a(None)


def test_welch_satterthwaite_and_coverage():
    assert A.nu_eff([(1.0, math.inf), (1.0, math.inf)]) == math.inf
    assert A.nu_eff([(1.0, 4)]) == pytest.approx(4)
    assert A.nu_eff([(1.0, 4), (1.0, 4)]) == pytest.approx(8)
    cf = A.coverage_factor(math.inf, 2.0, 0.05)
    assert cf["k"] == 2.0 and not cf["low_effective_dof"]
    cf = A.coverage_factor(5, 2.0, 0.05)
    assert cf["low_effective_dof"] and cf["k"] == pytest.approx(2.649, abs=1e-3)
    assert A.P_K2 == pytest.approx(0.9545, abs=1e-4)
    thr = _doc()["planning_tables"]["low_dof_threshold"]["value"]
    assert not A.coverage_factor(thr, 2.0, 0.05)["low_effective_dof"]
    assert A.coverage_factor(thr - 1, 2.0, 0.05)["low_effective_dof"]
    with pytest.raises(ValueError):
        A.coverage_factor(0, 2.0, 0.05)
    with pytest.raises(ValueError):
        A.nu_eff([])


def test_implied_n_and_verdict_against_lane25_targets():
    tgt = {int(k.split("=")[1]): v["value"] for k, v in _doc()["lane25_and_w4_targets"]["u_T_max"].items()}
    assert A.implied_n(0.004, tgt) == 4
    assert A.implied_n(0.006, tgt) == 6
    assert A.implied_n(0.007, tgt) == 8
    assert A.implied_n(0.009, tgt) is None
    v = A.repeatability_verdict(0.0049, 9, tgt, 0.95)
    assert v["verdict"] == "MEETS_N4" and v["confident"] is False  # 0.0049 * 1.645 > every target
    v = A.repeatability_verdict(0.004, 9, tgt, 0.95)
    assert v["verdict"] == "MEETS_N4" and v["implied_n_upper_bound"] == 8
    v = A.repeatability_verdict(0.002, 29, tgt, 0.95)
    assert v["verdict"] == "MEETS_N4" and v["confident"] is True
    assert A.repeatability_verdict(0.01, 9, tgt, 0.95)["verdict"] == "EXCEEDS_ALL_TARGETS"
    with pytest.raises(ValueError):
        A.implied_n(0.004, {})


def test_calibration_fit_installation_and_configuration_shift():
    fit = A.linear_calibration([0, 1, 2, 3, 4], [0.1, 2.1, 4.1, 6.1, 8.1])
    assert fit["slope"] == pytest.approx(2.0) and fit["intercept"] == pytest.approx(0.1)
    assert fit["s_residual"] == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(ValueError):
        A.linear_calibration([1, 1, 1], [1, 2, 3])
    r = A.ln_reproducibility([1.0, math.e])
    assert r["mean"] == pytest.approx(0.5) and r["nu"] == 1
    with pytest.raises(ValueError):
        A.ln_reproducibility([1.0, -1.0])
    same = A.configuration_slope_shift((1.0, 0.001), (1.0005, 0.001), 2.0, 0.05, 9, 9)
    assert same["verdict"] == "NOT_DETECTED"
    moved = A.configuration_slope_shift((1.0, 0.001), (1.05, 0.001), 2.0, 0.05, 9, 9)
    assert moved["verdict"] == "DETECTED" and moved["ln_shift"] == pytest.approx(math.log(1.05))


def test_drift_mfc_errors_skew_phase():
    d = A.drift_rate([0, 3600, 7200], [0.0, 1.0, 2.0])
    assert d["drift_per_hour"] == pytest.approx(1.0)
    assert A.drift_rate([0, 1, 2], [5.0, 5.0, 5.0])["drift_per_hour"] == 0.0
    assert A.relative_point_errors([1.1, 2.0], [1.0, 2.0]) == pytest.approx([0.1, 0.0])
    with pytest.raises(ValueError):
        A.relative_point_errors([1.0], [0.0])
    sk = A.channel_skew({"a": [0.0, 1.0, 2.0], "b": [1e-6, 1.000001, 2.000001]})
    assert sk["worst_skew_s"] == pytest.approx(1e-6) and sk["channels"]["b"]["mean_offset_s"] == pytest.approx(1e-6)
    with pytest.raises(ValueError):
        A.channel_skew({"a": [0.0, 1.0, 2.0]})
    with pytest.raises(ValueError):
        A.channel_skew({"a": [0.0, 1.0, 2.0], "b": [0.0, 1.0]})
    assert A.phase_error_deg(1e4, 2.77778e-7) == pytest.approx(1.0, rel=1e-5)


# --------------------------------------------------------------------------------------------- S1-C4 record items
def _item(**over):
    it = {"category": "temperature", "instrument_id": "INS-23", "demonstration_id": "CD-07",
          "evidence_class": "measured", "calibration_date": "2026-10-01",
          "raw_data": {"path": "docs/experiments/instrumentation/raw/example.csv", "sha256": "0" * 64},
          "demonstrated_uncertainty": {"value": 1.0, "unit": "K", "source": "fixture", "evidence_class": "measured"},
          "coverage": {"k": 2.0, "nu_eff": "inf", "low_effective_dof": False},
          "analysis_script_sha256": "1" * 64, "calibration_plan_sha256": "2" * 64, "verdict": "fixture",
          "scope": "cathode_c1", "emitter_temperature_status": "unmeasured",
          "channels": [{"id": "TC-1", "label": "cathode_tube_temperature", "sensor_type": "thermocouple"}]}
    it.update(over)
    return it


def test_record_item_validator_and_a3_cathode_rule():
    assert A.record_item_errors(_item()) == []
    assert A.record_item_errors(_item(evidence_class="model-derived"))
    assert A.record_item_errors(_item(raw_data={"path": "docs/other/x.csv", "sha256": "0" * 64}))
    assert A.record_item_errors(_item(calibration_date="2026-13-45"))
    assert A.record_item_errors(_item(category="thrust"))
    du = dict(_item()["demonstrated_uncertainty"], evidence_class="assumed")
    assert A.record_item_errors(_item(demonstrated_uncertainty=du))
    # A3: thermocouple labelled emitter -> fail
    tc_em = [{"id": "TC-1", "label": "emitter_temperature", "sensor_type": "thermocouple"}]
    assert A.record_item_errors(_item(channels=tc_em))
    # A3: no pyrometer -> emitter must be 'unmeasured'
    assert A.record_item_errors(_item(emitter_temperature_status="1800 K"))
    # A3: pyrometer with emissivity treatment -> emitter label allowed
    ok = [{"id": "TC-1", "label": "cathode_tube_temperature", "sensor_type": "thermocouple"},
          {"id": "PY-1", "label": "emitter_temperature", "sensor_type": "pyrometer", "emissivity_treatment": "rec"}]
    assert A.record_item_errors(_item(channels=ok, emitter_temperature_status="measured")) == []
    no_eps = [{"id": "PY-1", "label": "emitter_temperature", "sensor_type": "pyrometer"}]
    assert A.record_item_errors(_item(channels=no_eps))


def test_record_schema_consistent_with_validator():
    schema = json.loads((DIR / "capability_record_item_v1.schema.json").read_text(encoding="utf-8"))
    assert set(schema["properties"]["category"]["enum"]) == set(A.S1C4_CATEGORIES)
    for f in ("category", "evidence_class", "calibration_date", "raw_data", "demonstrated_uncertainty",
              "analysis_script_sha256", "calibration_plan_sha256", "coverage"):
        assert f in schema["required"]
        assert A.record_item_errors({k: v for k, v in _item().items() if k != f})
    import re  # no jsonschema dependency (not in the locked environment): check the schema patterns directly
    it = _item()
    assert re.match(schema["properties"]["calibration_date"]["pattern"], it["calibration_date"])
    assert re.match(schema["properties"]["raw_data"]["properties"]["path"]["pattern"], it["raw_data"]["path"])
    assert re.match(schema["properties"]["raw_data"]["properties"]["sha256"]["pattern"], it["raw_data"]["sha256"])
    assert re.match(schema["properties"]["demonstration_id"]["pattern"], it["demonstration_id"])


# --------------------------------------------------------------------------------------------- metrology spec
def test_metrology_spec_a3_standards_and_no_lab_named():
    spec = _spec()
    text = json.dumps(spec)
    for needle in ("ISO/IEC 17025", "NABL", "OIML", "E2", "ISO 25178-700", "ASTM E1508", "ISO 15472"):
        assert needle in text, needle
    assert spec["authority"]["file"] == B.A3_REL and spec["authority"]["sha256"] == B.PINNED[B.A3_REL]
    assert "No laboratory is named" in spec["not_a_procurement"]
    e2 = spec["measurands"][0]["planning_values"]["e2_table_subset"]
    assert e2["1 g"]["mpe"]["value"] == 0.03 and e2["100 mg"]["mpe"]["value"] == 0.016
    for v in e2.values():
        assert v["U_max_k2"]["value"] == pytest.approx(v["mpe"]["value"] / 3, rel=1e-5)
        assert v["mpe"]["evidence_class"] == "assumed"
    for m in spec["measurands"]:
        assert m["required_uncertainty"]["value"] == "TBD"
