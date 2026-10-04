"""A9.22 items 6-7 (Phase B): raw physics closure separated from the assessment layer, with no numerical change.

* evaluate() must reproduce (key set, key order, value types exactly; finite floats bit for bit on the generating
  machine and under the cross-platform identity rule A1/A2 below on other platforms), the records frozen at base
  commit 9eb302c before the split (tests/fixtures/evaluate_identity_base_9eb302c.json, generated once by
  tests/fixtures/make_evaluate_identity_fixture.py at that commit), EXCEPT the keys moved or added by the governed
  A9.22 G1 baseline change (system.py completion; docs/HISTORY.md 'A9.22 G1 governed baseline change (system.py
  completion)'), which are listed explicitly below (G1_MOVED_KEYS, G1_ADDED_KEYS) and checked against the 26,280 /
  26,000 h scaling instead. The 9eb302c fixture is kept unedited as the historical no-change proof of Phase B.
* The same records must reproduce, with no exclusion and under the same cross-platform identity rule, the post-G1 fixture
  tests/fixtures/evaluate_identity_g1.json (generated once by tests/fixtures/make_evaluate_identity_fixture_g1.py at
  the G1 completion commit): the reference for future no-change checks.
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
import math
from pathlib import Path

import pandas as pd
import pytest

from abep_sim.assessment import (RAW_ONLY_KEYS, FORBIDDEN_RAW_PREFIXES, FORBIDDEN_RAW_KEYS, REQUIREMENT_POINTERS,
                                 RAW_SCHEMA_VERSION, assess, constraints_from_config, priors_from_config,
                                 legacy_merge)
from abep_sim.intake import IntakeParams, CompressorParams
from abep_sim.system import Config, Budgets, physics_closure, RAW_CLOSURE_SCHEMA_VERSION
from abep_sim.programme.closure import evaluate

ROOT = Path(__file__).resolve().parents[1]
FIX_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE = FIX_DIR / "evaluate_identity_base_9eb302c.json"
FIXTURE_G1 = FIX_DIR / "evaluate_identity_g1.json"
RVM = ROOT / "docs/requirements/rvm_a9/rvm_a9_v1.json"


def _gen():
    spec = importlib.util.spec_from_file_location("make_evaluate_identity_fixture", FIX_DIR / "make_evaluate_identity_fixture.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GEN = _gen()
FIX = json.loads(FIXTURE.read_text())
FIX_G1 = json.loads(FIXTURE_G1.read_text()) if FIXTURE_G1.is_file() else None

# A9.22 G1 governed baseline change (system.py completion): mission-integrated outputs moved from the 26,000 h to the
# 26,280 h mission-duration basis (exact factor 26280/26000); new keys carry the basis / mission reliability.
G1_MOVED_KEYS = ("ao_fluence_mission_m2", "erosion_kapton_um", "erosion_graphite_um", "erosion_silver_um",
                 "eng_cathode_starts")
G1_SCALED_KEYS = G1_MOVED_KEYS[:4]                       # linear in the mission hours
G1_ADDED_KEYS = ("ao_fluence_basis_h", "eng_R_mission", "eng_R_mission_h")
G1_FACTOR = 26280.0 / 26000.0


# Cross-platform numerical-identity rule for the fixtures (owner decision 2026-10-04, A9.24 steering response item 1,
# Option A, exact form A1-A6). Purpose: cross-platform identity of the SAME physics implementation, not a scientific
# acceptance tolerance. The identity fixtures were generated on the execution container; GitHub ubuntu runners
# reproduce the records except for floating-point rounding differences that depend on the runner hardware:
#   run 37190383021: C_D 2.0549076096691596 vs 2.05490760966916 (1 ULP), active_ratio 16.534084977161054 vs
#                    16.53408497716106 (2 ULP);
#   run 37192387572 (pymsis-present leg): xe_peak_mgps 0.007530565601447853 vs 0.0075305656014480705 (251 ULP, rel
#                    2.9e-14), xe_aug_kg (227 ULP, rel 2.9e-14), eng_R_26000h (47 ULP), m_mga_kg (24 ULP);
#                    res_balance_residual_rel 9.07e-17 vs 3.48e-17 (two roundoff residues of a closed balance).
# A2 ordinary finite floats: equal, or (relative difference <= 1e-13 AND ULP distance <= 512); a zero never matches a
#    non-zero. 1e-13 is about 3.4x the worst observed relative difference (2.9e-14), 512 ULP about 2x the worst
#    observed ULP distance (251): limited portability headroom only.
# A1 residual / closure-noise fields (explicit allowlist, mathematically zero): no ULP comparison; both the actual and
#    the reference value must satisfy |x| <= 1e-14. The conservation gate itself is unchanged and separately enforced.
# A3 everything else exact: ints, bools, strings, None, NaN (only NaN), +/-inf, container kinds, lengths, key sets and
#    key order. A4 same-process comparisons in this file stay bit-exact.
FLOAT_IDENTITY_MAX_REL = 1e-13
FLOAT_IDENTITY_MAX_ULP = 512
RESIDUAL_ABS_MAX = 1e-14
# Only fields demonstrated to be roundoff residues of a quantity that is mathematically zero:
#   res_balance_residual_rel = max per-species |inflow + recombination source - outflow - sink| / total inflow at the
#   returned reservoir steady state (abep_sim/reservoir.py steady_state; system.py passes it through).
RESIDUAL_NOISE_FIELDS = frozenset({"res_balance_residual_rel"})
_FLOAT_TAGS = ("float", "np_float")


def _ulp_distance(a: float, b: float) -> float:
    return abs(a - b) / max(math.ulp(a), math.ulp(b))


def _float_close(a: float, b: float) -> bool:
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    if math.isinf(a) or math.isinf(b):
        return a == b
    if a == b:
        return True
    if a == 0.0 or b == 0.0:
        return False
    return abs(a - b) / max(abs(a), abs(b)) <= FLOAT_IDENTITY_MAX_REL and _ulp_distance(a, b) <= FLOAT_IDENTITY_MAX_ULP


def _residual_ok(a, b) -> bool:
    if not (isinstance(a, dict) and isinstance(b, dict) and list(a) == list(b) and len(a) == 1
            and next(iter(a)) in _FLOAT_TAGS):
        return False
    tag = next(iter(a))
    x, y = float(a[tag]), float(b[tag])
    return math.isfinite(x) and math.isfinite(y) and abs(x) <= RESIDUAL_ABS_MAX and abs(y) <= RESIDUAL_ABS_MAX


def _enc_equal(a, b, key: str | None = None) -> bool:
    """Equality of two GEN.encode() values under the cross-platform identity rule (A1 for RESIDUAL_NOISE_FIELDS,
    A2 for other finite floats, A3 exact for everything else)."""
    if key in RESIDUAL_NOISE_FIELDS:
        return _residual_ok(a, b)
    if isinstance(a, dict) and isinstance(b, dict):
        if list(a) != list(b):
            return False
        if len(a) == 1:
            (tag,) = a
            if tag in _FLOAT_TAGS:
                return _float_close(float(a[tag]), float(b[tag]))
            if tag in ("list", "tuple"):
                return len(a[tag]) == len(b[tag]) and all(_enc_equal(x, y) for x, y in zip(a[tag], b[tag]))
            if tag == "map":
                return (len(a[tag]) == len(b[tag]) and [k for k, _ in a[tag]] == [k for k, _ in b[tag]]
                        and all(_enc_equal(x, y) for (_, x), (_, y) in zip(a[tag], b[tag])))
        return a == b
    return type(a) is type(b) and a == b


def _decode(e):
    return float(e["float"]) if "float" in e else e["int"]


def _check_against_9eb302c(row, r: dict):
    """Identity (cross-platform rule A1/A2/A3) vs the 9eb302c record except the explicitly listed G1 keys (checked by their scaling)."""
    keys = [k for k in r if k not in G1_ADDED_KEYS]
    assert keys == row["keys"], "key set / order changed (beyond the listed G1 additions)"
    assert set(G1_ADDED_KEYS[:1]) <= set(r)
    old = dict(zip(row["keys"], row["values"]))
    diff = [(k, GEN.encode(r[k]), old[k]) for k in keys if k not in G1_MOVED_KEYS and not _enc_equal(GEN.encode(r[k]), old[k], k)]
    assert not diff, f"numerical / type change vs base commit 9eb302c outside the G1 keys: {diff[:5]}"
    assert r["ao_fluence_basis_h"] == 26280.0
    for k in G1_SCALED_KEYS:
        assert r[k] == pytest.approx(_decode(old[k]) * G1_FACTOR, rel=1e-12), k
    if "eng_cathode_starts" in r:
        assert old["eng_cathode_starts"] == {"int": int(26000.0 / 24 * 0.5)} and r["eng_cathode_starts"] == int(26280.0 / 24 * 0.5)
        assert r["eng_R_mission_h"] == 26280.0 and 0 < r["eng_R_mission"] <= r["eng_R_26000h"]


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
    _check_against_9eb302c(row, r)
    if FIX_G1 is not None:                                  # post-G1 reference: no exclusion
        g = FIX_G1["rows"][i]
        assert g["config"] == row["config"] and list(r) == g["keys"]
        got = [GEN.encode(r[k]) for k in r]
        diff = [(k, a, b) for k, a, b in zip(g["keys"], got, g["values"]) if not _enc_equal(a, b, k)]
        assert not diff, f"numerical / type change vs the G1 fixture: {diff[:5]}"


def test_g1_fixture_present_and_provenanced():
    assert FIX_G1 is not None, "tests/fixtures/evaluate_identity_g1.json missing"
    assert FIX_G1["generator"] == "tests/fixtures/make_evaluate_identity_fixture_g1.py"
    assert FIX_G1["mission_hours_basis_h"] == 26280.0 and FIX_G1["firing_hours_assumption_h"] == 15000.0
    assert len(FIX_G1["rows"]) == len(FIX["rows"]) == 122


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
    _check_against_9eb302c(FIX["rows"][i], merged)
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
    from abep_sim.programme.sweep import run_grid, run_grid_split, main, EVIDENCE_STATUS
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


def test_float_identity_rule_is_narrow():
    """A5: the cross-platform comparator (owner Option A exact form)."""
    F = lambda v: {"float": repr(v)}
    up = lambda v, n: v + n * math.ulp(v)
    # 1. the observed worst case (251 ULP, rel 2.9e-14) passes
    assert _enc_equal(F(0.007530565601447853), F(0.0075305656014480705))
    assert _enc_equal(F(2.0549076096691596), F(2.05490760966916))
    # 2. > 512 ULP fails even though the relative difference is below 1e-13
    x = 1.9375                                    # near the top of a binade: 513 ULP is rel 5.9e-14 < 1e-13
    assert (513 * math.ulp(x)) / x < FLOAT_IDENTITY_MAX_REL
    assert _enc_equal(F(x), F(up(x, 512))) and not _enc_equal(F(x), F(up(x, 513)))
    # 3. relative > 1e-13 fails even when the ULP count is small (subnormal range: 1 ULP is a large relative step)
    t = 5 * math.ulp(0.0)
    assert _ulp_distance(t, t + math.ulp(0.0)) <= 1 and not _enc_equal(F(t), F(t + math.ulp(0.0)))
    # 4. residual values: both <= 1e-14 pass without any ULP / relative comparison
    assert _enc_equal(F(9.074563138469054e-17), F(3.4771690530582354e-17), "res_balance_residual_rel")
    assert not _enc_equal(F(9.074563138469054e-17), F(3.4771690530582354e-17))      # not for unlisted fields
    # 5. a residual above 1e-14 (either side) fails
    assert not _enc_equal(F(2e-14), F(3e-17), "res_balance_residual_rel")
    assert not _enc_equal(F(3e-17), F(2e-14), "res_balance_residual_rel")
    assert not _enc_equal(F(float("nan")), F(0.0), "res_balance_residual_rel")
    assert not _enc_equal({"int": 0}, F(0.0), "res_balance_residual_rel")
    assert RESIDUAL_NOISE_FIELDS == {"res_balance_residual_rel"}
    # 6. zero vs non-zero ordinary fields fail; exact zeros pass
    assert not _enc_equal(F(0.0), F(1e-300)) and not _enc_equal(F(1e-300), F(0.0)) and _enc_equal(F(0.0), F(0.0))
    # 7. int / bool / string / None / container differences fail
    assert not _enc_equal({"int": 3}, {"int": 4}) and not _enc_equal({"int": 3}, F(3.0))
    assert not _enc_equal(True, False) and not _enc_equal(True, 1) and not _enc_equal("a", "b")
    assert not _enc_equal(None, F(0.0)) and _enc_equal(None, None)
    assert not _enc_equal({"np_int": 1}, {"np_int": 2}) and not _enc_equal({"np_bool": True}, {"np_bool": False})
    assert not _enc_equal({"list": [F(1.0)]}, {"list": [F(1.0), F(1.0)]})
    assert not _enc_equal({"list": [F(1.0)]}, {"tuple": [F(1.0)]})
    assert not _enc_equal({"map": [["a", F(1.0)]]}, {"map": [["b", F(1.0)]]})
    assert _enc_equal({"map": [["a", {"list": [F(x)]}]]}, {"map": [["a", {"list": [F(up(x, 2))]}]]})
    # 8. NaN / inf exact
    assert _enc_equal(F(float("nan")), F(float("nan"))) and not _enc_equal(F(float("nan")), F(1.0))
    assert _enc_equal(F(float("inf")), F(float("inf"))) and not _enc_equal(F(float("inf")), F(float("-inf")))
    assert not _enc_equal(F(1.7976931348623157e308), F(float("inf")))
