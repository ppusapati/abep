"""A9.22 items 6-7 (Phase B): raw physics closure separated from the assessment layer, with no numerical change.

* evaluate() must reproduce, bit for bit (key set, key order, value types, float repr), the records frozen at base
  commit 9eb302c before the split (tests/fixtures/evaluate_identity_base_9eb302c.json, generated once by
  tests/fixtures/make_evaluate_identity_fixture.py at that commit).
* physics_closure() (schema raw_closure_v2) carries no chk_* / rfp_* / ic_* / hall_preferred / compliance keys.
* assess() points checks at RVM rows (pointers only); constraints change the assessment, never the raw physics.
* The sweep's raw + assessment files join back to the legacy sweep table.
* Dead logic removed (G7): ignition_req_met ... or True, Budgets.duty_cycle, the unused RFP import in sizing.
"""
from __future__ import annotations
import dataclasses
import importlib.util
import inspect
import json
from pathlib import Path

import pandas as pd
import pytest

from abep_sim.assessment import (RAW_ONLY_KEYS, FORBIDDEN_RAW_PREFIXES, FORBIDDEN_RAW_KEYS, REQUIREMENT_POINTERS,
                                 RAW_SCHEMA_VERSION, assess, constraints_from_config, priors_from_config,
                                 legacy_merge)
from abep_sim.intake import IntakeParams, CompressorParams
from abep_sim.system import Config, Budgets, evaluate, physics_closure, RAW_CLOSURE_SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
FIX_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE = FIX_DIR / "evaluate_identity_base_9eb302c.json"
RVM = ROOT / "docs/requirements/rvm_a9/rvm_a9_v1.json"


def _gen():
    spec = importlib.util.spec_from_file_location("make_evaluate_identity_fixture", FIX_DIR / "make_evaluate_identity_fixture.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GEN = _gen()
FIX = json.loads(FIXTURE.read_text())


def _no_forbidden(raw: dict):
    bad = [k for k in raw if k.startswith(FORBIDDEN_RAW_PREFIXES) or k in FORBIDDEN_RAW_KEYS]
    assert not bad, f"raw closure carries assessment keys: {bad}"


def test_fixture_provenance():
    assert FIX["base_commit"].startswith("9eb302c") and len(FIX["rows"]) == 122
    assert RAW_SCHEMA_VERSION == RAW_CLOSURE_SCHEMA_VERSION == "raw_closure_v2"


@pytest.mark.parametrize("i", range(len(FIX["rows"])))
def test_evaluate_identical_to_base_commit(i):
    row = FIX["rows"][i]
    r = evaluate(GEN.build(row["config"]))
    assert list(r) == row["keys"], "key set / order changed"
    got = [GEN.encode(r[k]) for k in r]
    diff = [(k, a, b) for k, a, b in zip(row["keys"], got, row["values"]) if a != b]
    assert not diff, f"numerical / type change vs base commit 9eb302c: {diff[:5]}"


@pytest.mark.parametrize("i", [0, 57, 113, 117, 119, 121])
def test_physics_closure_is_raw_only(i):
    cfg = GEN.build(FIX["rows"][i]["config"])
    raw = physics_closure(cfg)
    _no_forbidden(raw)
    assert raw["raw_schema_version"] == "raw_closure_v2"
    for label in ("intake_model", "gaspath_model", "plasma_model", "engineering_model", "atm_source"):
        assert label in raw
    # raw + assessment == legacy evaluate() (same keys, order, values)
    a = assess(raw, constraints_from_config(cfg), priors_from_config(cfg))
    merged = legacy_merge(raw, a)
    assert list(merged) == FIX["rows"][i]["keys"]
    assert [GEN.encode(merged[k]) for k in merged] == FIX["rows"][i]["values"]
    assert set(RAW_ONLY_KEYS) & set(merged) == set()


def test_physics_closure_does_not_read_assessment_priors():
    """IC priors, the Hall-preference attribute, the CBE target and the power margin are assessment inputs only."""
    from abep_sim.thruster import CARDS
    import copy
    base_kw = FIX["rows"][2]["config"]                      # hall_1stage, parametric
    raw0 = physics_closure(GEN.build(base_kw))
    kw = json.loads(json.dumps(base_kw))
    kw["budgets"] = {"ic_intake": 0.1, "ic_compressor": 0.1, "ic_pse": 0.1, "ic_structure": 0.1,
                     "m_cbe_target_kg": 1.0, "p_margin_frac": 0.9}
    card0 = CARDS["hall_1stage"]
    try:
        CARDS["hall_1stage"] = dataclasses.replace(copy.deepcopy(card0), ic_thruster=0.01, hall=False)
        cfg = GEN.build(kw)
        raw1 = physics_closure(cfg)
        a1 = assess(raw1, constraints_from_config(cfg), priors_from_config(cfg))
    finally:
        CARDS["hall_1stage"] = card0
    assert [GEN.encode(raw1[k]) for k in raw1] == [GEN.encode(raw0[k]) for k in raw0]
    a0 = assess(raw0, constraints_from_config(GEN.build(base_kw)), priors_from_config(GEN.build(base_kw)))
    assert a0["chk_hall_preferred"] is True and a1["chk_hall_preferred"] is False
    assert a1["ic_total"] < a0["ic_total"] and a1["chk_ic_thruster"] is False


def test_constraint_change_moves_assessment_not_raw():
    cfg = GEN.build(FIX["rows"][2]["config"])
    raw = physics_closure(cfg)
    snap = [GEN.encode(raw[k]) for k in raw]
    c = constraints_from_config(cfg)
    pr = priors_from_config(cfg)
    a = assess(raw, c, pr)
    tight = dataclasses.replace(c, mass_max_kg=0.0, power_max_W=0.0)
    loose = dataclasses.replace(c, mass_max_kg=1e6, power_max_W=1e9, p_margin_frac=0.0)
    at, al = assess(raw, tight, pr), assess(raw, loose, pr)
    assert at["chk_mass"] is False and at["chk_power_air"] is False and at["rfp_compliant"] is False
    assert al["chk_mass"] is True and al["chk_power_air"] is True
    assert a["constraints"]["mass_max_kg"] == 40.0
    assert [GEN.encode(raw[k]) for k in raw] == snap          # raw physics untouched by assessment


def test_requirement_pointers_exist_in_rvm():
    rows = {r["id"]: r for r in json.loads(RVM.read_text())["rows"]}
    expect_keys = {"thrust_air_ge_req": "THRUST_12MN_SUSTAINED", "thrust_peak_25mN": "THRUST_25MN_CAPABILITY",
                   "mass": "MASS_LT_40KG_WET", "ic_total": "INDIGENOUS_CONTENT", "hall_preferred": "HALL_PREFERENCE",
                   "thermal": "THERMAL_CLOSURE"}
    for chk, ids in REQUIREMENT_POINTERS.items():
        for rid in ids:
            assert rid in rows, (chk, rid)
    for chk, key in expect_keys.items():
        assert rows[REQUIREMENT_POINTERS[chk][0]]["key"] == key
    cfg = GEN.build(FIX["rows"][0]["config"])
    raw = physics_closure(cfg)
    a = assess(raw, constraints_from_config(cfg), priors_from_config(cfg))
    checks = [k[4:] for k in a if k.startswith("chk_")]
    assert set(checks) <= set(a["requirement_pointers"])
    assert a["requirement_pointers"]["power_air"] == ["RVM-04", "RVM-05"]
    assert a["requirement_pointers"]["compressor_feasible"] == []


def test_assess_rejects_unversioned_raw():
    cfg = GEN.build(FIX["rows"][0]["config"])
    raw = physics_closure(cfg)
    raw.pop("raw_schema_version")
    with pytest.raises(ValueError):
        assess(raw, constraints_from_config(cfg), priors_from_config(cfg))


SMALL_GRID = {"architectures": ["hall_1stage", "hall_ecr"], "alt_km": [200], "solar": ["mean"],
              "intake_area_m2": [0.5, 1.5], "accommodation": [0.5], "comp_ratio": [500], "vd_V": [250],
              "T_required_mN": [None, 20.0], "body_area_m2": [0.0]}


def test_sweep_raw_assessment_join_equals_legacy(tmp_path):
    from abep_sim.sweep import run_grid, run_grid_split, main, EVIDENCE_STATUS
    legacy = run_grid(SMALL_GRID)
    raw, assessed, merged = run_grid_split(SMALL_GRID)
    pd.testing.assert_frame_equal(merged, legacy)
    assert (raw.evidence_status == "PARAMETRIC_SCREENING_NOT_EVIDENCE").all() and EVIDENCE_STATUS in set(raw.evidence_status)
    _no_forbidden({k: None for k in raw.columns})
    assert set(assessed.columns) - {"row_id", "assessment_schema_version", "raw_schema_version"} <= set(legacy.columns)
    joined = raw.merge(assessed, on="row_id", suffixes=("", "_a"))
    pd.testing.assert_frame_equal(joined[list(legacy.columns)], legacy)
    # files on disk
    import yaml
    g = tmp_path / "grid.yaml"; g.write_text(yaml.safe_dump(SMALL_GRID))
    assert main([str(g), "-o", str(tmp_path / "out")]) == 0
    sw = pd.read_csv(tmp_path / "out/sweep.csv")
    assert list(sw.columns) == list(legacy.columns) + ["evidence_status"]
    rs = pd.read_csv(tmp_path / "out/raw_sweep.csv"); asf = pd.read_csv(tmp_path / "out/assessment_sweep.csv")
    j = rs.merge(asf, on="row_id", suffixes=("", "_a"))
    pd.testing.assert_frame_equal(j[list(legacy.columns)], sw[list(legacy.columns)])
    summ = (tmp_path / "out/summary.txt").read_text()
    assert summ.startswith("PARAMETRIC SCREENING") and "RFP-compliant count" not in summ
    ptr = json.loads((tmp_path / "out/assessment_requirement_pointers.json").read_text())
    assert ptr["pointers"]["mass"] == ["RVM-06"]


def test_dead_logic_removed():
    from abep_sim import sizing, transient
    assert "duty_cycle" not in {f.name for f in dataclasses.fields(Budgets)}
    assert not hasattr(sizing, "RFP")
    src = inspect.getsource(transient)
    assert "ignition_req_met" not in src.replace('always-true "ignition_req_met" flag was removed', "")
    assert "or True" not in src
