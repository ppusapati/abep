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
import hashlib
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


DRIFT_PATH = REPO / "docs" / "performance" / "dedicated_baseline_2026_10_01" / "DRIFT_AFTER_A9_9.json"


def test_historical_source_drift_is_reported_not_hidden(H, doc):
    """Profiled sources changed after measurement under authorised model changes (A9.9 S2, A9.18 golden): the check
    reports HISTORICAL_SOURCE_DRIFT with old/new sha256 instead of failing; timings stay untouched; the drift record
    names every drifted file (incl. abep_sim/golden.py) and requires the owner rerun (A9.18 PERF_RERUN)."""
    rec = json.loads(DRIFT_PATH.read_text())
    assert rec["status"] == "HISTORICAL_SOURCE_DRIFT" and rec["owner_rerun_required"] is True
    assert rec["rust_performance_admission"] == "BLOCKED_UNTIL_A9_18_PERF_RERUN" and "PERF_RERUN" in rec["statement"]
    recorded = {d["path"]: d for d in rec["drifted_files"]}
    assert "abep_sim/golden.py" in recorded
    old = {s["path"]: s["sha256"] for s in doc["profiled_sources"]}
    for p, d in recorded.items():
        assert d["old_sha256_a9_7"] == old[p] and d["new_sha256"] != old[p]
    drift = H.source_drift(doc)
    assert all(d["status"] == "HISTORICAL_SOURCE_DRIFT" and "error" not in d for d in drift)
    assert {d["path"] for d in drift} <= set(recorded)
    lines = H.drift_report_lines(doc)
    for d in drift:
        assert any(d["path"] in ln and d["old_sha256"] in ln and d["new_sha256"] in ln for ln in lines)
    if drift:
        assert "PERF_RERUN" in lines[-1]


def test_unrecorded_drift_still_fails(H, doc, monkeypatch, tmp_path):
    empty = tmp_path / "empty_drift.json"
    empty.write_text(json.dumps({"drifted_files": []}))
    monkeypatch.setattr(H, "DRIFT_REL", str(empty))       # REPO / absolute path -> the absolute path
    drift = H.source_drift(doc)
    if drift:
        assert all("not recorded" in d["error"] for d in drift)
        assert H.check()


def test_recorded_drift_changed_again_fails(H, doc, monkeypatch, tmp_path):
    """SW-05: a recorded drift is not an allowance for any later change. A record whose new sha256 differs from the
    current bytes (here: every recorded new sha256 replaced) fails --check."""
    rec = json.loads(DRIFT_PATH.read_text())
    stale = tmp_path / "stale_drift.json"
    for d in rec["drifted_files"]:
        d["new_sha256"] = "0" * 64
    stale.write_text(json.dumps(rec))
    monkeypatch.setattr(H, "DRIFT_REL", str(stale))
    monkeypatch.setattr(H, "DRIFT_ADDENDA_REL", ())
    drift = H.source_drift(doc)
    assert drift
    assert all("drifted again" in d["error"] for d in drift), drift
    assert any("drifted again" in e for e in H.check())


def test_drift_addendum_must_chain(H, doc, monkeypatch, tmp_path):
    """An addendum entry whose old sha256 is not the previous record's new sha256 is an error (no gap in the chain)."""
    drift0 = H.source_drift(doc)
    assert drift0 and all("error" not in d for d in drift0)
    p = drift0[0]["path"]
    bad = tmp_path / "bad_addendum.json"
    bad.write_text(json.dumps({"drifted_files": [{"path": p, "old_sha256": "1" * 64, "new_sha256": drift0[0]["new_sha256"]}]}))
    monkeypatch.setattr(H, "DRIFT_ADDENDA_REL", tuple(H.DRIFT_ADDENDA_REL) + (str(bad),))
    d = {x["path"]: x for x in H.source_drift(doc)}[p]
    assert "does not chain" in d["error"]


def test_drift_addenda_chain_to_current_bytes(H, doc):
    """Every addendum record chains on the earlier record and ends at the current bytes (A9.18 PERF_RERUN still owed)."""
    for rel in H.DRIFT_ADDENDA_REL:
        add = json.loads((REPO / rel).read_text())
        assert add["status"] == "HISTORICAL_SOURCE_DRIFT" and add["owner_rerun_required"] is True
        assert add["rust_performance_admission"] == "BLOCKED_UNTIL_A9_18_PERF_RERUN"
        for d in add["drifted_files"]:
            assert d["new_sha256"] == hashlib.sha256((REPO / d["path"]).read_bytes()).hexdigest(), d["path"]
    assert all("error" not in d for d in H.source_drift(doc))


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
