"""DI-1.4 compressor down-selection v1 (fo_compressor_downselect).

Checks that docs/architecture_comparison/compressor_downselect/build_compressor_downselect.py reproduces the committed
JSON + MD (--check), that the owner decision files are unchanged (sha256 pins), that every literature value carries a
reference, an evidence class and an access level (secondary / search-excerpt values flagged 'verify'), that the
requirement envelope matches the W1 feed-state closure it reads, that the gate matrix is complete and eliminations carry
explicit hard-gate logic, that nothing ranks hall_only / rf_hall / ecr_hall, that no Hall closure / screening candidate /
P5 nuisance token appears, and that missing inputs raise.
Run: python -m pytest -q tests/test_compressor_downselect.py   (~15 s; the reproduction test runs the builder once).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "docs" / "architecture_comparison" / "compressor_downselect"
SCRIPT = DIR / "build_compressor_downselect.py"
JSON_PATH = DIR / "compressor_downselect_v1.json"
MD_PATH = DIR / "COMPRESSOR_DOWNSELECT.md"
CLOSURE = REPO / "docs" / "architecture_comparison" / "feed_state_closure" / "feed_state_closure_v1.json"
EVIDENCE = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
CASES = {f"alt{a}_{l}" for a in (180, 200, 230) for l in ("low", "mean", "high")}
FORBIDDEN_TOKENS = ("ensemble_member_id", "sgb-screen", "screening_candidate", "coil_shape", "beam_efficiency",
                    "facility_ingestion", "hall_ensemble", "plasma_devices", "plasma_chem", "hall1d",
                    "hallthruster_bridge/ensemble")


def _load():
    spec = importlib.util.spec_from_file_location("_compressor_downselect_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(JSON_PATH.read_text())


def test_reproduces_committed_outputs(mod):
    assert mod.main(["--check"]) == 0


def test_decision_files_pinned(doc):
    assert len(doc["decision_pins"]) == 4
    for rel, h in doc["decision_pins"].items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == h, rel
    assert "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json" in doc["decision_pins"]


def test_header_and_scope(doc):
    assert doc["schema"] == "compressor_downselect_v1"
    assert doc["follow_on"] == "fo_compressor_downselect"
    assert doc["trigger"] == "T_PIVOT_COMPRESSOR_DOWNSELECT"
    assert doc["architectures"] == ["hall_only", "rf_hall", "ecr_hall"]
    assert "COMMON_MODE" in doc["architecture_neutrality"]
    assert "candidate range, not a flight truth" in doc["flow_range_status"]
    assert doc["milestones"]["supports"] == ["A"]
    assert doc["milestones"]["to_B"] and doc["milestones"]["to_C"]


def test_evidence_discipline(doc):
    refs = doc["references"]
    for r in refs.values():
        assert r["access_level"] in ("full_text", "abstract_only", "secondary_citation", "search_engine_excerpt")
        assert r["doi_or_url"] and r["accessed"] == "2026-09-27"
    for e in doc["evidence"]:
        assert e["ref"] in refs, e["id"]
        assert e["evidence_class"] in EVIDENCE, e["id"]
        assert e["where"] and e["statement"] and e["used_for"]
        if refs[e["ref"]]["access_level"] in ("secondary_citation", "search_engine_excerpt"):
            assert e["verify"] is True, f"{e['id']} not read first-hand must be flagged verify"
    ids = {e["id"] for e in doc["evidence"]}
    for c in doc["concepts"]:
        for eid in c["published_basis"]:
            assert eid in ids
        for gr in c["gates"].values():
            for eid in gr["evidence"]:
                assert eid in ids
            assert gr["evidence_class"] in EVIDENCE
    for f in doc["findings"]:
        assert f["evidence_class"] in EVIDENCE


def test_proposed_levels_are_labelled(doc):
    for k, v in doc["proposed_levels"].items():
        assert "value" in v and "unit" in v and v["meaning"], k
    gates = {g["id"]: g for g in doc["gates"]}
    assert gates["HG-1b"]["status"] == "PROPOSED"
    assert "RFP" in gates["HG-1"]["origin"] and "RFP" in gates["HG-2"]["origin"]


def test_envelope_matches_w1_closure(doc):
    cl = json.loads(CLOSURE.read_text())
    closed = sorted(c for c, v in cl["closure"].items() if v["status"] == "CLOSED")
    env = doc["requirement_envelope"]
    assert sorted(env) == closed
    for cid in closed:
        assert set(env[cid]["cases"]) == CASES
        for cs, r in env[cid]["cases"].items():
            sc = cl["valve_outlet"][cid][cs]["backflow_self_consistent"]
            assert math.isclose(r["p_passive_Pa"], sc["p_plenum_chain_Pa"], rel_tol=1e-8)
            assert math.isclose(r["CR_required"]["self_consistent_backflow"], sc["CR_required"], rel_tol=1e-8)
            assert abs(sum(r["w_s_inlet"].values()) - 1.0) < 1e-9
            # jet-power bound of 12 mN (RFP minimum) at the self-consistent flow
            m = r["mdot_valve_kgps"]["self_consistent_backflow"]
            assert math.isclose(r["P_jet_min_W_at_12mN"]["self_consistent_backflow"], 0.012 ** 2 / (2 * m),
                                rel_tol=1e-8)
            # pumping-speed requirement: (1-b) Q / (b p_passive)
            for b in (0.5, 0.25, 0.1):
                S = (1 - b) * r["Q_Pa_m3_s"] / (b * r["p_passive_Pa"])
                assert math.isclose(r["S_required_m3_s"][str(b)], S, rel_tol=1e-8)
    s = doc["requirement_summary"]
    assert s["candidate_cases"] == 9 * len(closed)
    assert 2.3 < s["CR_required_self_consistent"]["min"] < 2.4
    assert 141 < s["CR_required_self_consistent"]["max"] < 143
    assert 0.029 < s["mdot_valve_bracket_kgps"]["min"] * 1e6 < 0.031
    assert 3.13 < s["mdot_valve_bracket_kgps"]["max"] * 1e6 < 3.15


def test_matrix_complete_and_eliminations_explicit(doc):
    gate_ids = [g["id"] for g in doc["gates"]]
    assert gate_ids == ["HG-1", "HG-1b", "HG-2", "HG-3", "HG-4", "HG-5", "HG-6"]
    allowed = {"PASS", "FAIL", "FAIL_AT_PUBLISHED_POINT", "CONDITIONAL", "NOT_EVALUABLE", "OUT_OF_SCOPE"}
    ids = [c["id"] for c in doc["concepts"]]
    assert ids == ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
    for c in doc["concepts"]:
        assert set(c["gates"]) == set(gate_ids)
        assert doc["downselect_matrix"][c["id"]] == {g: c["gates"][g]["result"] for g in gate_ids}
        for g, gr in c["gates"].items():
            assert gr["result"] in allowed
            if gr["result"] in ("FAIL", "FAIL_AT_PUBLISHED_POINT", "OUT_OF_SCOPE"):
                assert len(gr["basis"]) > 40, f"{c['id']} {g}: elimination needs explicit logic"
    c3 = next(c for c in doc["concepts"] if c["id"] == "C3")
    assert c3["gates"]["HG-4"]["result"] == "FAIL" and "WITHIN" in c3["gates"]["HG-4"]["basis"]
    c7 = next(c for c in doc["concepts"] if c["id"] == "C7")
    assert c7["gates"]["HG-6"]["result"] == "OUT_OF_SCOPE"
    # no concept claims sourced DragCompressor parameters today (all code defaults are uncited)
    for c in doc["concepts"]:
        assert c["dragcompressor_mapping"]["parameters_sourced_today"] == []


def test_recommendation_is_proposed_and_neutral(doc):
    r = doc["recommendation"]
    assert r["status"].startswith("PROPOSED")
    assert r["primary"]["concept"] == "C1" and r["primary"]["conditions"]
    assert "never ranks" in r["never"]
    text = json.dumps(doc).lower()
    for word in ("winner", "baseline architecture is"):
        assert word not in text
    tests = doc["minimum_data_to_freeze_DI_1_4"]
    assert [t["id"] for t in tests] == [f"T-{i}" for i in range(1, 10)]


def test_no_hall_closure_tokens():
    blob = JSON_PATH.read_text() + MD_PATH.read_text() + SCRIPT.read_text()
    for tok in FORBIDDEN_TOKENS:
        assert tok not in blob, tok


def test_missing_input_raises(mod):
    with pytest.raises(mod.DownselectError):
        mod.need({"a": 1}, "b", "unit test")
    with pytest.raises(mod.DownselectError):
        mod.need({"a": None}, "a", "unit test")
    with pytest.raises(mod.DownselectError):
        mod.ev("EV-99")


def test_atomic_o_scaling(mod):
    # EV-02: ln K0 ~ sqrt(m) -> ln K_O / ln K_N2 = sqrt(16/28)
    k = mod.published_O_capability(3500.0)
    assert math.isclose(math.log(k) / math.log(3500.0), math.sqrt(16.0 / 28.0), rel_tol=1e-9)
