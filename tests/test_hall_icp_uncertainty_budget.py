"""Tests for the A9-04 C1-vs-ICP uncertainty budget (fo_a9_04_hall_icp_uncertainty_budget, owner decision A9).

Pure file checks plus the deterministic builder; no network, no Julia, fast.
Run: python -m pytest -q tests/test_hall_icp_uncertainty_budget.py
"""
import importlib.util
import json
import math
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANE = os.path.join(ROOT, "docs", "experiments", "hall_icp", "uncertainty_budget")
BUILDER = os.path.join(LANE, "build_hall_icp_uncertainty_budget.py")
JSON_PATH = os.path.join(LANE, "hall_icp_uncertainty_budget_v1.json")
MD_PATH = os.path.join(LANE, "HALL_ICP_UNCERTAINTY_BUDGET.md")

EVIDENCE = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation"}
FREEZE = {"NOW", "LOCK-1", "LOCK-2", "after-evidence"}
STATUSES = {"OWNER_GIVEN", "PROPOSED", "TBD", "PENDING", "VERIFIED_INPUT"}
CONFIGS = ["hall_c1_reference", "hall_icp_neutralizer"]
A9_LANE_PATHS = ["docs/experiments/hall_icp/prereg_framework/", "abep_sim/bus_boundary_a9.py",
                 "docs/interfaces/icp_neutralizer/", "docs/evidence/icp_neutralizer/"]


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_hall_icp_uncertainty_budget", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def b():
    return _load_builder()


@pytest.fixture(scope="module")
def doc():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def answers():
    with open(os.path.join(ROOT, "docs", "decisions", "OD_2026_09_29_owner_answers_147.json"), encoding="utf-8") as f:
        return {a["row"]: a for a in json.load(f)["answers"]}


def test_outputs_reproduce_exactly(b):
    assert b.check() == []


def test_pins_hold(b):
    assert b.verify_pins() == []


def test_markdown_is_generated_from_json(b, doc):
    with open(MD_PATH, encoding="utf-8") as f:
        assert f.read() == b.render_md(doc)


def test_required_sections_present(doc):
    for key in ("decision_quantities", "items", "measurement_chains", "variance_groups", "stop_rules",
                "interpolation", "readiness_n", "interface_demands", "owner_answers_applied",
                "open_owner_questions", "historical_reuse", "m16_impact", "h3_procurement_inputs", "h4_test_inputs",
                "references", "authority_pins"):
        assert doc[key], key
    assert doc["lane"] == "fo_a9_04_hall_icp_uncertainty_budget"
    assert doc["trigger"] == "T_A9_04_UNCERTAINTY_BUDGET"
    assert doc["configurations"] == CONFIGS


A9_01_JSON = "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json"
# A9_INT (fo_a9_int_core_integration): provisional UB-DQ-* ids renamed to the final A9-01 DQ-HI-* ids where a unique
# counterpart exists; the others keep their UB-DQ-* id and are marked 'UNMAPPED - owner/A9-10'.
EXPECTED_MAPPING = {"UB-DQ-T": "DQ-HI-TABS", "UB-DQ-PBUS": "DQ-HI-PBUS", "UB-DQ-RF": None, "UB-DQ-NEUT": None,
                    "UB-DQ-ID": None, "UB-DQ-FLOW": None, "UB-DQ-PB": None, "UB-DQ-BZ": None, "UB-DQ-TEMP": None,
                    "UB-DQ-ETAU": "DQ-HI-ETAU"}


def test_decision_quantities_cover_the_lane_scope(doc):
    ids = {q["id"] for q in doc["decision_quantities"]}
    assert ids == {v or k for k, v in EXPECTED_MAPPING.items()}
    for q in doc["decision_quantities"]:
        if q["id"].startswith("DQ-HI-"):
            assert q["a9_01_dq_id"].startswith(A9_01_JSON + " " + q["id"] + " (role ")
        else:
            assert q["a9_01_dq_id"].startswith("PENDING docs/experiments/hall_icp/prereg_framework/")
        assert set(q["configurations"]) <= set(CONFIGS)
    chains = {c["dq"] for c in doc["measurement_chains"]}
    assert chains == ids
    rest = json.dumps({k: v for k, v in doc.items() if k != "dq_id_mapping"})
    for old_id in ("UB-DQ-T\"", "UB-DQ-T)", "UB-DQ-T ", "UB-DQ-PBUS", "UB-DQ-ETAU"):
        assert old_id not in rest, old_id


def test_dq_id_mapping_table(doc):
    m = doc["dq_id_mapping"]
    assert m["integration_record"] == "docs/experiments/hall_icp/integration/a9_core_integration_v1.json"
    rows = {r["ub_dq_id"]: r for r in m["rows"]}
    assert set(rows) == set(EXPECTED_MAPPING)
    for ub, dq in EXPECTED_MAPPING.items():
        r = rows[ub]
        assert r["dq_hi_id"] == dq
        assert r["status"] == ("MAPPED" if dq else "UNMAPPED - owner/A9-10")
        assert r["basis"] and r["ub_definition"] and r["a9_01_definition"]
    targets = [r["dq_hi_id"] for r in m["rows"] if r["dq_hi_id"]]
    assert len(targets) == len(set(targets))


def test_every_item_is_sourced_or_tbd(doc):
    seen = set()
    for it in doc["items"]:
        assert it["id"] not in seen
        seen.add(it["id"])
        assert it["freeze_point"] in FREEZE, it["id"]
        assert it["status"] in STATUSES, it["id"]
        assert set(it["configurations"]) <= set(CONFIGS)
        v = it["value"]
        if isinstance(v, str) and (v.startswith("TBD - requires ") or v.startswith("PENDING ")):
            assert it["evidence_class"] is None, it["id"]
            assert it["status"] in {"TBD", "PENDING", "PROPOSED"}, it["id"]
        else:
            assert it["evidence_class"] in EVIDENCE, it["id"]
            assert it["source"], it["id"]


def test_numbers_only_from_owner_answers_or_verified_inputs(doc, answers):
    for it in doc["items"]:
        v = it["value"]
        numeric = isinstance(v, (int, float)) or (isinstance(v, list) and all(isinstance(x, (int, float)) for x in v)) \
            or (isinstance(v, dict) and any(isinstance(x, (int, float, list, dict)) for x in v.values()))
        if not numeric:
            continue
        assert it["status"] in {"OWNER_GIVEN", "VERIFIED_INPUT"}, it["id"]
        if it["status"] == "OWNER_GIVEN":
            assert it["owner_rows"], it["id"]
            assert it["owner_text"], it["id"]
            assert any(it["owner_text"] in answers[r]["owner_answer_verbatim"] for r in it["owner_rows"]), it["id"]
        else:
            assert "docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json#H26-" in it["source"]


def test_owner_given_values(doc):
    by = {it["id"]: it for it in doc["items"]}
    assert by["UB-T-01"]["value"] == 1.0 and by["UB-T-01"]["owner_rows"] == [121]
    assert by["UB-T-02"]["value"] == 12.0 and by["UB-T-02"]["owner_rows"] == [120]
    assert by["UB-T-00"]["owner_rows"] == [115]
    assert by["UB-RF-00"]["value"] == 13.56 and by["UB-RF-01"]["value"] == [0.0, 500.0]
    assert by["UB-F-10"]["value"] == 0.005 and by["UB-F-10"]["owner_rows"] == [92]
    assert by["UB-F-11"]["value"] == {"t_ign_max_s": 120.0, "retries_max": 2}
    assert by["UB-K-00"]["value"] == 50.0 and by["UB-K-00"]["owner_rows"] == [86]
    assert by["UB-B-00"]["value"] == 2 and by["UB-B-00"]["owner_rows"] == [23]
    assert by["UB-C-05"]["value"] == 3 and by["UB-C-05"]["owner_rows"] == [19]
    assert by["UB-B-02"]["value"] == 200 and by["UB-I-00"]["value"] == 60.0


def test_no_frozen_decision_thresholds(doc):
    by = {it["id"]: it for it in doc["items"]}
    for iid in ("UB-C-01", "UB-C-02", "UB-C-03", "UB-C-04", "UB-C-06", "UB-C-08", "UB-Z-00", "UB-B-01", "UB-RF-08"):
        assert isinstance(by[iid]["value"], str) and by[iid]["value"].startswith(("TBD - requires", "PENDING")), iid
    for g in doc["variance_groups"]["groups"]:
        assert g["share"].startswith("TBD - requires"), g["id"]
    assert [g["id"] for g in doc["variance_groups"]["groups"]] == ["VG-1", "VG-2", "VG-3", "VG-4", "VG-5"]
    txt = json.dumps(doc["stop_rules"])
    # no numeric stop margin, alpha or effect size in the stop rules
    assert not re.search(r"delta_stop\"?\s*[:=]\s*[0-9]", txt)
    cs = doc["stop_rules"]["contrast_stop"]
    assert {f["id"] for f in cs["forms"]} == {"SR-C-SIGN", "SR-C-MARGIN"}
    assert cs["owner_choice"].startswith("OPEN")
    assert cs["historical_citation_only"]["rationale_quoted"]
    assert "superseded" in cs["historical_citation_only"]["status"]


def test_not_tested_and_vocabulary(doc):
    nt = doc["stop_rules"]["not_tested"]
    assert nt["outcome_vocabulary"] == CONFIGS + ["NO_VIABLE_CASE"]
    assert nt["status_vocabulary"] == ["OPEN"]
    assert "row 39" in nt["rule"]


def test_a4_interlocks_carried(doc):
    with open(os.path.join(ROOT, "docs", "decisions", "OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json"),
              encoding="utf-8") as f:
        a4 = json.load(f)["decisions"]
    assert doc["stop_rules"]["safety_interlocks"]["a4_minimum"] == a4["S1a_minimum_interlocks"]


def test_owner_answers_applied_are_verbatim(doc, answers):
    rows = [x["row"] for x in doc["owner_answers_applied"]]
    assert rows == sorted(set(rows))
    for must in (12, 13, 15, 18, 19, 23, 32, 72, 92, 93, 96, 97, 98, 115, 119, 120, 121, 123, 124, 125, 126, 127,
                 129, 131):
        assert must in rows, must
    for x in doc["owner_answers_applied"]:
        assert x["answer_verbatim"] == answers[x["row"]]["owner_answer_verbatim"]
        assert x["how_applied"]


def test_pins_immutable_only(doc):
    paths = [p["path"] for p in doc["authority_pins"]]
    for g in doc["governance_files_not_pinned"]:
        assert g not in paths
    assert not any("orchestration" in p for p in paths)
    for p in doc["authority_pins"]:
        assert re.fullmatch(r"[0-9a-f]{64}", p["sha256"])
    assert "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json" in paths
    assert "docs/decisions/OD_2026_09_29_owner_answers_147.json" in paths


def test_parallel_a9_lanes_only_pending(doc):
    txt = json.dumps(doc)
    for p in A9_LANE_PATHS:
        assert p in txt
        for m in re.finditer(re.escape(p), txt):
            window = txt[max(0, m.start() - 200):m.start()]
            # A9_INT: a resolved reference names a concrete file of the merged lane deliverable
            token = re.match(re.escape(p) + r"[A-Za-z0-9_./]*", txt[m.start():]).group(0)
            resolved = token.endswith((".json", ".py"))
            assert (resolved or "PENDING" in window or "A9-0" in window or "counterpart" in window), p
    for p in A9_LANE_PATHS:
        assert p not in [x["path"] for x in doc["authority_pins"]]


def test_no_historical_topology_as_configuration(doc):
    for sec in ("decision_quantities", "items", "measurement_chains", "variance_groups", "stop_rules"):
        txt = json.dumps(doc[sec])
        for old in ('"hall_only"', '"rf_hall"', '"ecr_hall"'):
            assert old not in txt, (sec, old)


def test_no_performance_prediction_sources(doc):
    txt = json.dumps({k: v for k, v in doc.items() if k not in ("compliance", "owner_answers_applied")})
    for banned in ("sgb-screen", "plasma_devices", "hall_map.py", "hall_ensemble"):
        assert banned not in txt, banned


def test_interface_demands_both_directions(doc):
    dirs = {x["direction"] for x in doc["interface_demands"]}
    for want in ("from_A9-01_to_this_lane", "from_this_lane_to_A9-01", "from_A9-02_to_this_lane",
                 "from_this_lane_to_A9-02", "from_A9-03_to_this_lane", "from_this_lane_to_A9-03",
                 "from_A9-05_to_this_lane", "from_this_lane_to_A9-05", "from_this_lane_to_H2-6",
                 "from_H2-6_to_this_lane", "from_this_lane_to_metrology_spec"):
        assert want in dirs, want
    for x in doc["interface_demands"]:
        assert x["units"] and x["status"] in STATUSES


def test_m16_rows_exist(doc):
    with open(os.path.join(ROOT, "docs", "budgets", "subsystem_maturity", "subsystem_maturity_v2.json"),
              encoding="utf-8") as f:
        rows = {r["row"]: r for r in json.load(f)["rows"]}
    for x in doc["m16_impact"]:
        assert rows[x["row"]]["key"] == x["key"]
    assert 15 in [x["row"] for x in doc["m16_impact"]]


def test_historical_reuse_pinned(doc):
    pins = {p["path"]: p["sha256"] for p in doc["authority_pins"]}
    for x in doc["historical_reuse"]:
        if x["sha256"] is not None:
            assert pins[x["path"]] == x["sha256"]
        assert x["not_reused"]


def test_builder_code_does_not_name_the_xe_module(b):
    with open(BUILDER, encoding="utf-8") as f:
        src = f.read()
    assert "xe" + "_ledger" not in src


# ------------------------------- readiness_n (synthetic inputs only; no claim about hardware)
def test_readiness_n_requires_inputs(b):
    base = dict(s_d=0.02, type_b=[(0.001, math.inf)], u_interp=0.0, h_target=0.05, alpha_fw=0.05, m_family=2,
                n_candidates=[3, 4, 5, 6])
    for k in base:
        bad = dict(base)
        bad[k] = None
        with pytest.raises(ValueError):
            b.readiness_n(**bad)
    with pytest.raises(ValueError):
        b.readiness_n(**dict(base, n_candidates=[2, 4]))
    with pytest.raises(ValueError):
        b.readiness_n(**dict(base, alpha_fw=1.5))
    with pytest.raises(TypeError):
        b.readiness_n(0.02, [], 0.0, 0.05, 0.05, 2, [3])


def test_readiness_n_monotone_and_minimum_three(b):
    kw = dict(type_b=[(0.001, math.inf)], u_interp=0.0, h_target=0.05, alpha_fw=0.05, m_family=2,
              n_candidates=list(range(3, 40)))
    n_small = b.readiness_n(s_d=0.01, **kw)
    n_large = b.readiness_n(s_d=0.04, **kw)
    assert n_small == 3
    assert n_large is not None and n_large > n_small
    # the rule holds at the returned n and fails at n - 1
    p = 1 - 0.05 / (2 * 2)

    def ok(n, s):
        comps = [(s / math.sqrt(n), n - 1.0), (0.001, math.inf)]
        sig = math.sqrt(sum(u * u for u, _ in comps))
        return b._t_quantile(p, b.welch_satterthwaite(comps)) * sig <= 0.05
    assert ok(n_large, 0.04) and not ok(n_large - 1, 0.04)


def test_readiness_n_floor_returns_none(b):
    # the non-averaging term alone exceeds the target: no n can satisfy the rule -> owner decision
    assert b.readiness_n(s_d=0.01, type_b=[(0.05, math.inf)], u_interp=0.0, h_target=0.05, alpha_fw=0.05,
                         m_family=1, n_candidates=[3, 6, 12, 24]) is None


def test_welch_satterthwaite_gum_form(b):
    assert b.welch_satterthwaite([(1.0, 4.0)]) == pytest.approx(4.0)
    assert math.isinf(b.welch_satterthwaite([(1.0, math.inf), (1.0, math.inf)]))
    assert b.welch_satterthwaite([(1.0, 4.0), (1.0, 4.0)]) == pytest.approx(8.0)
