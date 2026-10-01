"""A9.18 golden design point (owner decision OD_2026_10_01_A9_18, decision GOLDEN:
NEW_ADMISSIBLE_CONVERGED_GOLDEN; RETAIN_OLD_AS_NONCONVERGED_REGRESSION_REFERENCE).

* golden_v1.json is kept byte-identical as history; golden.py reads golden_v2.json.
* The golden_v1 gas-path-dependent cases survive unchanged as the `nonconverged_reference` fixture
  (NONCONVERGED_REFERENCE / EXPECTED_NONCONVERGENCE) and must be refused by the solver.
* The canonical design point is chosen by a deterministic, performance-blind rule (first admissible point of the default
  close_architecture gas grid in loop order) and is converged / in domain / sized, with the S2.3 rotor label.
* The golden carries provenance and the sha256 of its frozen inputs.

The full numerical reproduction (all cases) runs in tests/test_sim.py::test_v151_golden_benchmarks_reproduce and
tests/test_golden_cli.py; the tests here are structural plus one cheap live case.
"""
from __future__ import annotations

import fnmatch
import hashlib
import inspect
import json
import os

import pytest

from abep_sim import golden as G

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V1 = os.path.join(ROOT, "abep_sim", "data", "golden_v1.json")
V2 = os.path.join(ROOT, "abep_sim", "data", "golden_v2.json")
V1_SHA256 = "1f7fbb626f79e38d743bf69516e9ea62b8ddef2ff2726d2f0fd4f4df6b377fb8"   # golden_v1.json as frozen before A9.18


def _sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="module")
def v2():
    with open(V2) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def v1():
    with open(V1) as f:
        return json.load(f)


def test_golden_file_is_v2_and_v1_kept_as_history(v2):
    assert os.path.abspath(G.GOLDEN_FILE) == os.path.abspath(V2)
    assert v2["version"] == "golden_v2"
    assert _sha(V1) == V1_SHA256                                    # golden_v1.json unchanged
    assert v2["provenance"]["previous_golden"]["sha256"] == V1_SHA256


def test_provenance_hashes_match_frozen_inputs(v2):
    pv = v2["provenance"]
    assert "A9.18" in pv["owner_decision"] and "NEW_ADMISSIBLE_CONVERGED_GOLDEN" in pv["owner_decision"]
    assert set(pv["frozen_inputs_sha256"]) == {f"abep_sim/data/{f}" for f in G.FROZEN_INPUTS}
    for rel, sha in pv["frozen_inputs_sha256"].items():
        assert _sha(os.path.join(ROOT, rel)) == sha, rel
    assert len(pv["code_version"]["git_head_at_generation"]) == 40
    assert pv["selection_rule"]["id"] == G.SELECTION_RULE["id"]
    assert pv["generator"] == "python -m abep_sim.golden generate"


def test_case_roles(v2):
    assert set(v2["case_roles"]) == set(G.CASES) == set(v2["cases"])
    assert v2["case_roles"]["nonconverged_reference"] == "NONCONVERGED_REFERENCE / EXPECTED_NONCONVERGENCE"
    assert v2["case_roles"]["design_point_selection"] == "SELECTION_RECORD"
    for k in ("atmosphere", "intake", "gas_path", "source_plasma", "hall", "accelerators", "architecture_closure", "mission"):
        assert v2["case_roles"][k] == "CANONICAL"


def test_unaffected_cases_identical_to_v1(v1, v2):
    # cases without a gas-path solver did not move (exact equality: regenerated values are bit-identical)
    for k in ("atmosphere", "intake", "source_plasma", "hall"):
        errs = []
        G._compare(v1["cases"][k], v2["cases"][k], k, 1e-12, errs)
        assert not errs, errs


def test_nonconverged_reference_keeps_v1_values_exactly(v1, v2):
    nr = v2["cases"]["nonconverged_reference"]
    assert nr["role"] == "NONCONVERGED_REFERENCE" and nr["expectation"] == "EXPECTED_NONCONVERGENCE"
    assert nr["design_point"] == {"area_m2": 1.3, "p_level_Pa": 0.05}
    assert set(nr["values"]) == set(G.NONCONVERGED_CASES)
    for k in G.NONCONVERGED_CASES:
        assert nr["values"][k] == v1["cases"][k], k               # verbatim, not recomputed floats


def test_nonconverged_reference_is_refused(v2):
    nr = v2["cases"]["nonconverged_reference"]
    assert nr["refusal_violations"] == {}
    assert G.refusal_violations(nr["refusal"]) == []
    c = nr["refusal"]["architecture_closure"]["ext_hall_2p5kW"]
    assert c["status"] == "MODEL_NOT_CONVERGED" and c["evidence_admissible"] is False and c["feasible"] is False
    assert "orifice_sizing" in c["gaspath_not_converged"]
    assert c["gaspath_domain_status"] == "OUT_OF_MODEL_DOMAIN"
    m = nr["refusal"]["mission"]["mission_4000h"]
    assert m["architecture_status"] == "MODEL_NOT_CONVERGED" and m["evidence_admissible"] is False
    for k in ("A0.7", "A1.3"):
        g = nr["refusal"]["gas_path"][k]
        assert g["gaspath_status"] == "MODEL_NOT_CONVERGED" and g["orifice_bracketed"] is False
        assert g["chk_compressor_feasible"] is False
    assert nr["refusal"]["accelerators"]["evidence_class"] == "MODEL_NOT_CONVERGED"
    # a fixture that is no longer refused is a violation
    bad = json.loads(json.dumps(nr["refusal"]))
    bad["architecture_closure"]["ext_hall_2p5kW"]["status"] = "OK"
    bad["architecture_closure"]["ext_hall_2p5kW"]["evidence_admissible"] = True
    assert G.refusal_violations(bad)


def test_default_grid_matches_close_architecture():
    from abep_sim import archengine as AE
    src = inspect.getsource(AE.close_architecture)
    assert 'gas_vars = gas_vars or {"area": [0.6, 0.7, 0.85], "p_level": [0.02, 0.05, 0.1]}' in src
    assert G.DEFAULT_GAS_GRID == {"area": [0.6, 0.7, 0.85], "p_level": [0.02, 0.05, 0.1]}
    # loop order of close_architecture: area outer, p_level inner (the selection rule walks the same order)
    assert src.index('for area in gas_vars["area"]') < src.index('for p_level in gas_vars["p_level"]')


def test_selection_rule_is_first_admissible_in_grid_order(monkeypatch):
    calls = []

    def fake(area, p):
        calls.append((area, p))
        ok = (area, p) in {(0.7, 0.1), (0.85, 0.1), (0.7, 0.05)}
        return {"verdict": "ADMISSIBLE" if ok else "X", "admissible": ok, "reason": ""}
    monkeypatch.setattr(G, "admissibility", fake)
    sel, visited = G.select_design_point()
    assert sel == {"area": 0.7, "p_level": 0.05}
    assert calls == [(0.6, 0.02), (0.6, 0.05), (0.6, 0.1), (0.7, 0.02), (0.7, 0.05)]     # stops at the first
    calls.clear()
    sel, visited = G.select_design_point(full_scan=True)
    assert sel == {"area": 0.7, "p_level": 0.05} and len(calls) == 9 and len(visited) == 9


def test_stored_selection_record(v2):
    s = v2["cases"]["design_point_selection"]
    assert s["rule_id"] == G.SELECTION_RULE["id"]
    assert s["selected"] == {"area_m2": G.GOLDEN_DESIGN_POINT["area"], "p_level_Pa": G.GOLDEN_DESIGN_POINT["p_level"]}
    assert list(s["visited"])[-1] == "A0.7_p0.05" and s["visited"]["A0.7_p0.05"]["verdict"] == "ADMISSIBLE"
    assert not any(v["admissible"] for k, v in s["visited"].items() if k != "A0.7_p0.05")
    scan = v2["provenance"]["full_grid_scan"]
    assert [(r["area"], r["p_level"]) for r in scan] == [(a, p) for a in G.DEFAULT_GAS_GRID["area"] for p in G.DEFAULT_GAS_GRID["p_level"]]
    first = next(r for r in scan if r["admissible"])
    assert (first["area"], first["p_level"]) == (0.7, 0.05)
    # the old point is not admissible and not in the default grid
    assert (G.V1_DESIGN_POINT["area"], G.V1_DESIGN_POINT["p_level"]) not in [(r["area"], r["p_level"]) for r in scan]
    # the documented cross-check (closest admissible to the v1 point: same p_level, then smallest |delta area|)
    adm = [(r["area"], r["p_level"]) for r in scan if r["admissible"]]
    near = min(adm, key=lambda t: (t[1] != G.V1_DESIGN_POINT["p_level"], abs(t[0] - G.V1_DESIGN_POINT["area"])))
    assert near == (0.7, 0.05)


def test_canonical_point_is_converged_in_domain_and_labelled(v2):
    c = v2["cases"]
    g = c["gas_path"]["A0.7_p0.05"]
    assert g["gaspath_status"] == "CONVERGED" and g["gaspath_domain_status"] == "IN_DOMAIN"
    for k in ("comp_converged", "res_converged", "orifice_converged", "orifice_bracketed", "comp_sized", "comp_gaede_domain_ok",
              "comp_rotor_within_legacy_sensitivity_cap"):
        assert g[k] is True, k
    assert g["comp_gaede_K_unclipped_min"] >= 1.0
    assert abs(g["p_in_Pa"] / g["p_target_Pa"] - 1) < 1e-6
    assert g["comp_rotor_qualification"] == "NOT_EVALUATED_MATERIAL_BASIS" and g["comp_sizing_mode"] == "PARAMETRIC_SENSITIVITY"
    a = c["architecture_closure"]["ext_hall_2p5kW"]
    assert (a["x_area"], a["x_p_level"]) == (0.7, 0.05)
    assert a["status"] == a["evidence_class"] == "PARAMETRIC_SENSITIVITY"
    assert a["closes_constraints"] is True and a["feasible"] is False and a["evidence_admissible"] is False
    assert a["gaspath_status"] == "CONVERGED" and a["gaspath_domain_status"] == "IN_DOMAIN"
    assert abs(a["ledger_resid"]) < 0.02
    m = c["mission"]["mission_4000h"]
    assert m["architecture_status"] == m["evidence_class"] == "PARAMETRIC_SENSITIVITY" and m["evidence_admissible"] is False
    gp = c["accelerators"]["gas_point"]
    assert gp["gaspath_status"] == "CONVERGED" and gp["gaspath_domain_status"] == "IN_DOMAIN"
    assert "NOT_EVALUATED_MATERIAL_BASIS" in v2["provenance"]["rotor_qualification_label"]


def test_check_reports_refusal_violation(tmp_path, monkeypatch):
    ref = {"cases": {"nonconverged_reference": {"role": "NONCONVERGED_REFERENCE", "refusal_violations": {}}}}
    p = tmp_path / "g.json"; p.write_text(json.dumps(ref))
    monkeypatch.setattr(G, "GOLDEN_FILE", str(p))
    monkeypatch.setattr(G, "CASES", {"nonconverged_reference": lambda: {"role": "NONCONVERGED_REFERENCE",
                                                                         "refusal_violations": {"0": "mission not refused"}}})
    errs = G.check()
    assert any("mission not refused" in e for e in errs)


def test_golden_v2_is_package_data():
    import tomllib
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        globs = tomllib.load(f)["tool"]["setuptools"]["package-data"]["abep_sim"]
    assert any(fnmatch.fnmatchcase("data/golden_v2.json", g) for g in globs)


def test_live_gas_path_and_refused_grid_point():
    """Cheap live checks: the canonical gas-path case reproduces, and a grid point with an unbracketed orifice is refused."""
    assert G.check(cases=["gas_path"]) == []
    v = G.admissibility(0.7, 0.02)
    assert v["admissible"] is False and v["verdict"] == "GASPATH_MODEL_NOT_CONVERGED"
