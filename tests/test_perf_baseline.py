"""Tests for the F0 performance baseline (lane fo_a9_7_f0_profiling, owner directive A9.7 sec. F0).

Schema / reproducibility checks only - no timing assertions (timings are machine- and load-dependent):
  * the committed docs/performance/PERFORMANCE_BASELINE_98fbbb9.json parses, is full mode, carries every required key,
    covers all eight F0 categories, labels the base commit, carries the exact commands and passes the builder --check
    (MD reproduces from JSON, workload specs and profiled sources unchanged);
  * the harness quick mode runs (cheap subset, < 30 s) and emits the required keys.
Run: python -m pytest -q tests/test_perf_baseline.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "scripts" / "perf" / "profile_baseline.py"
JSON_PATH = REPO / "docs" / "performance" / "PERFORMANCE_BASELINE_98fbbb9.json"
MD_PATH = REPO / "docs" / "performance" / "PERFORMANCE_BASELINE_98fbbb9.md"
QUICK_SUBSET = ("tpmc_trace_channel", "compressor_size_for", "system_evaluate_gas_path", "p3_view_factors_verify")


@pytest.fixture(scope="module")
def H():
    spec = importlib.util.spec_from_file_location("perf_profile_baseline", HARNESS)
    m = importlib.util.module_from_spec(spec)
    sys.modules["perf_profile_baseline"] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text())


def test_committed_baseline_schema(H, doc):
    assert H.validate(doc) == []
    assert doc["schema"] == H.SCHEMA and doc["mode"] == "full"
    assert doc["base_commit_label"] == "98fbbb9" and len(doc["measured_head"] or "") == 40
    assert doc["commands"] == H.COMMANDS and "full" in doc["commands"] and "quick" in doc["commands"]
    assert {w["category"] for w in doc["workloads"]} >= set(H.F0_CATEGORIES)
    env = doc["environment"]
    for k in ("cpu_model", "logical_cpus", "python", "numpy", "blas"):
        assert env.get(k) not in (None, "", {})


def test_committed_baseline_workload_records(doc):
    for w in doc["workloads"]:
        assert w["repeats"] >= 3 or w.get("repeats_override") == 1
        assert w["median_wall_s"] > 0 and len(w["wall_s"]) == w["repeats"]
        assert w["deterministic_across_repeats"] is True
        j = w["port_judgement"]
        assert j["judgement"] in ("PORT_CANDIDATE", "MARGINAL", "NOT_A_BOTTLENECK", "COVERED_BY", "NOT_RANKED")
        if w.get("profile", None) is not None:
            fr = w["profile"]["tottime_fractions"]
            assert abs(sum(fr.values()) - 1.0) < 0.01
    ranks = [r["rank"] for r in doc["ranking"]]
    assert ranks == list(range(1, len(ranks) + 1))
    adds = [r["addressable_interpreter_s_upper_bound"] for r in doc["ranking"]]
    assert adds == sorted(adds, reverse=True)
    # every workload driving the withdrawn 0-D Hall closure is flagged DEFER, never a plain port recommendation
    for w in doc["workloads"]:
        if w.get("physics_note"):
            assert "qualifier" in w["port_judgement"] and w["port_judgement"]["qualifier"].startswith("DEFER_PORT")


def test_committed_baseline_sections(doc):
    for d in doc["interface_demands"]:
        assert {"id", "direction", "counterparty", "demand", "status"} <= set(d)
    for p in doc["parameters"]:
        assert {"id", "value", "units", "basis", "source", "evidence_class", "status"} <= set(p)
    assert all({"id", "question"} <= set(q) for q in doc["open_owner_questions"])
    assert doc["m16_impact"] and doc["robust_design_search_status"]["exists_in_base"] is True
    assert '"PASS"' not in JSON_PATH.read_text()


def test_builder_check_passes(H):
    assert H.check() == []


def test_md_reproduces(H, doc):
    assert MD_PATH.read_text() == H.render_md(doc)


def test_quick_mode_runs_and_emits_required_keys(H, tmp_path):
    out = tmp_path / "quick.json"
    rc = H.main(["--quick", "--only", ",".join(QUICK_SUBSET), "--out-json", str(out)])
    assert rc == 0
    q = json.loads(out.read_text())
    assert q["mode"] == "quick"
    assert H.validate(q, require_all=False) == []
    assert [w["id"] for w in q["workloads"]] == list(QUICK_SUBSET)
    for w in q["workloads"]:
        for k in H.REQUIRED_WORKLOAD:
            assert k in w
        for k in H.REQUIRED_PROFILE:
            assert k in w["profile"]
    assert (tmp_path / "quick.md").read_text() == H.render_md(q)


def test_quick_mode_refuses_to_overwrite_baseline(H):
    with pytest.raises(SystemExit):
        H.main(["--quick"])
