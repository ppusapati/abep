"""A9.16 repair lane: the immutable history builders keep reproducing after any P1 / P2 / P3 / P4 / RVM change.

COR-01: build_owner_questions_state_v4.py (immutable) reads the live P1 / P2 / P3 / P4 / RVM JSON back (open questions,
P1 derived-resolution dispositions, registration items); COR-02: build_rfq_a9_v2.py (immutable) reads P1 / P2 back
(item and measurement status / quantity text); COR-05: build_p3_coupled_thermal.py is a profiled source of the F0
performance baseline, itself sha-pinned by the Rust parity pre-registration. These tests run each immutable builder's
--check (never a write) and pin the P3 v1 builder to the profiled sha256, so a lane change that would silently break
the history fails here first. Fast (each builder runs in seconds; no Julia).

    python -m pytest -q tests/test_a9_16_repair_readback.py
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
P3_V1_BUILDER = "docs/experiments/hall_icp/p3_coupled_thermal/build_p3_coupled_thermal.py"
PERF = ROOT / "docs/performance/PERFORMANCE_BASELINE_98fbbb9.json"

IMMUTABLE_CHECKS = [
    ("docs/budgets/owner_decisions/build_owner_questions_state_v4.py", "owner-question state v4: current"),
    ("docs/procurement/rfq_a9_v2/build_rfq_a9_v2.py", "OK: 9 outputs reproduce"),
    ("docs/budgets/mass_power_a9_v2/build_mass_power_a9_v2.py", "OK"),
    ("docs/budgets/xe_accounting_a9_v2/build_xe_accounting_a9_v2.py", "OK"),
    (P3_V1_BUILDER, "OK: outputs reproduced"),
    ("scripts/perf/profile_baseline.py", "OK"),
]


def _sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


@pytest.mark.parametrize("builder,ok", IMMUTABLE_CHECKS, ids=[b.rsplit("/", 1)[-1] for b, _ in IMMUTABLE_CHECKS])
def test_immutable_history_builders_reproduce(builder, ok):
    r = subprocess.run([sys.executable, str(ROOT / builder), "--check"], capture_output=True, text=True, cwd=ROOT,
                       timeout=110)
    assert r.returncode == 0 and ok in r.stdout, (builder, r.stdout[-600:], r.stderr[-600:])


def test_p3_v1_builder_is_the_f0_profiled_source():
    prof = {s["path"]: s["sha256"] for s in json.loads(PERF.read_text(encoding="utf-8"))["profiled_sources"]}
    assert _sha(P3_V1_BUILDER) == prof[P3_V1_BUILDER]
    assert _sha("docs/experiments/hall_icp/p3_coupled_thermal/p3_thermal_lib.py") == \
        prof["docs/experiments/hall_icp/p3_coupled_thermal/p3_thermal_lib.py"]


def test_p3_v2_supersedes_v1_for_the_current_state():
    v1 = json.loads((ROOT / "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json").read_text())
    v2 = json.loads((ROOT / "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json").read_text())
    assert v1["id"] == "p3_coupled_thermal_v1" and v2["id"] == "p3_coupled_thermal_v2"
    assert v2["supersedes_for_current_state"]["path"].endswith("p3_coupled_thermal_v1.json")
    assert all(q["status"] == "TBD_OWNER" for q in v1["open_owner_questions"])          # as raised (A9.6)
    assert all(q["status"] == "OWNER_DECIDED" for q in v2["open_owner_questions"])      # A9.16 current state
    assert "a9_16_owner_rules" in v2 and "a9_16_owner_rules" not in v1


def test_lane_question_records_keep_as_raised_fields_and_current_state():
    """The as-raised fields read by state v4 hold only the values v4 accepts; every lane says what is open now."""
    lanes = {"P1": "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
             "P2": "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
             "P4": "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json"}
    for k, rel in lanes.items():
        d = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        assert {q.get("status") for q in d["open_owner_questions"]} <= {None, "OPEN", "TBD_OWNER"}, k
        assert d["owner_questions_open_now"] == [], k
    rvm = json.loads((ROOT / "docs/requirements/rvm_a9/rvm_a9_v1.json").read_text(encoding="utf-8"))
    assert rvm["open_owner_questions"][0]["status"] == "TBD_OWNER"
    assert rvm["open_owner_questions"][0]["status_current"] == "OWNER_DECIDED"
