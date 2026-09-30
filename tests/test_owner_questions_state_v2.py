"""Owner-question state v2 (A9-10): reproducible, v1 untouched, no OPEN question answered, yellow column on OPEN rows only.

    python -m pytest -q tests/test_owner_questions_state_v2.py
"""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs" / "budgets" / "owner_decisions"
BUILDER = D / "build_owner_questions_state_v2.py"
J = D / "owner_questions_state_v2.json"
BASE = "ecdad06e30bc5d2f172e862e4bd4843e86332d42"
V1 = ["OWNER_QUESTIONS_CONSOLIDATED.md", "owner_questions_consolidated.csv", "owner_questions_consolidated.xlsx",
      "owner_decision_register_v1.json", "OWNER_DECISION_REGISTER.md"]


@pytest.fixture(scope="module")
def doc():
    return json.loads(J.read_text(encoding="utf-8"))


def test_builder_check():
    r = subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, (r.stdout[-1500:], r.stderr[-1500:])


def test_v1_files_byte_identical_to_base():
    for name in V1:
        rel = f"docs/budgets/owner_decisions/{name}"
        base = subprocess.run(["git", "show", f"{BASE}:{rel}"], cwd=ROOT, capture_output=True).stdout
        assert base and (ROOT / rel).read_bytes() == base, name


def test_pins_match(doc):
    for p in doc["pins"]:
        assert hashlib.sha256((ROOT / p["path"]).read_bytes()).hexdigest() == p["sha256"], p["path"]
    for gov in ("lane_registry_v1.json", "trigger_registry_v1.json", "runtime_state.json", "trigger_ledger"):
        assert not any(gov in p["path"] for p in doc["pins"]), gov


def test_counts_and_open_rows(doc):
    rows = doc["rows"]
    assert doc["open_count"] == sum(r["status"] == "OPEN" for r in rows) == doc["counts"]["OPEN"] > 0
    assert len({(r["id"], r["source"]) for r in rows}) == len(rows)   # an A9.1 decision row and the lane row may share an id
    for r in rows:                                                      # a shared id never has an OPEN copy
        if r["status"] == "OPEN":
            assert sum(x["id"] == r["id"] for x in rows) == 1, r["id"]
    assert [r["no"] for r in rows] == list(range(1, len(rows) + 1))
    for r in rows:
        if r["status"] == "OPEN":
            assert r["answer_pointer"] == "" and r["answer_excerpt"] == "", r["id"]   # never answered here
            assert r["needed_by"], r["id"]
        else:
            assert r["answer_pointer"], r["id"]


def test_a91_answers_point_to_the_decision_file(doc):
    for r in doc["rows"]:
        if r["status"] == "ANSWERED_BY_A9_1" or r["status_detail"] == "ANSWERED (A9.1)":
            assert "OD_2026_09_30_A9_1_followup_owner_decisions" in r["answer_pointer"], r["id"]


def test_csv_and_xlsx_match_json(doc):
    with open(D / "owner_questions_state_v2.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0][-1] == "Your answer"
    body = rows[1:]
    assert len(body) == len(doc["rows"])
    assert all(b[1] == r["id"] and b[4] == r["status"] and b[-1] == "" for b, r in zip(body, doc["rows"]))
    import importlib.util
    spec = importlib.util.spec_from_file_location("oqs_v2_builder", D / "build_owner_questions_state_v2.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    grid = b.xlsx_grid(D / "owner_questions_state_v2.xlsx")          # stdlib reader: no openpyxl, no skip
    hdr = next(i for i in range(5) if grid[i][0][0] == "No")
    for k, r in enumerate(doc["rows"]):
        row = grid[hdr + 1 + k]
        assert row[1][0] == r["id"]
        assert row[8][0] is None
        assert row[8][1] == (r["status"] == "OPEN"), r["id"]


def test_no_winner(doc):
    txt = json.dumps(doc).lower()
    assert "winner:" not in txt and "recommended architecture" not in txt


def test_status_is_canonical(doc):
    vocab = set(doc["status_vocabulary"])
    assert {r["status"] for r in doc["rows"]} <= vocab
    for k, v in doc["counts"].items():
        assert v == sum(r["status"] == k for r in doc["rows"]), k
    assert sum(doc["counts"].values()) == len(doc["rows"])


def test_every_lane_open_question_is_listed(doc):
    """Review repair: every open_owner_questions id of every A9 deliverable, incl. the M16 v3 refresh, is a row."""
    ids = {r["id"] for r in doc["rows"]}
    srcs = ["docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json",
            "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
            "schemas/interfaces/icp_neutralizer_icd_v1.json",
            "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json",
            "docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json",
            "docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json",
            "docs/budgets/mass_a9/mass_a9_v1.json", "docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json",
            "docs/budgets/" + "xe" + "_ledger_a9/" + "xe" + "_ledger_a9_v1.json",
            "docs/procurement/rfq_a9/rfq_a9_v1.json",
            "docs/experiments/hall_icp/integration/a9_core_integration_v1.json",
            "docs/experiments/hall_icp/integration/a9_10_reconciliation_v1.json",
            "docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json"]
    for rel in srcs:
        for q in json.loads((ROOT / rel).read_text(encoding="utf-8")).get("open_owner_questions", []):
            assert q["id"] in ids, (rel, q["id"])
    assert any(r["id"] == "M16-V3-Q-01" and r["status"] == "OPEN" for r in doc["rows"])


def test_a9_2_rows_and_oq_a907_11(doc):
    by = {(r["id"], r["kind"]): r for r in doc["rows"]}
    q = [r for r in doc["rows"] if r["id"] == "OQ-A907-11"][0]
    assert q["status"] == "ANSWERED_BY_A9_2" and "decisions.OQ-A907-11" in q["answer_pointer"]
    a92 = [r for r in doc["rows"] if r["kind"] == "a9_2"]
    keys = json.loads((ROOT / "docs/experiments/hall_icp/integration/a9_2_inputs/"
                               "OD_2026_09_30_A9_2_a907_followup_owner_decisions.json").read_text(encoding="utf-8"))
    assert sorted(r["id"] for r in a92) == sorted("A9.2 " + k for k in keys["decisions"])
    assert all(r["status"] == "ANSWERED" and r["status_detail"] == "ANSWERED (A9.2)" for r in a92)
    assert "OQ-A907-11" in by[("A9.2 OQ-A907-11", "a9_2")]["answers_lane_questions"]
    assert "ANSWERED_BY_A9_2" in doc["status_vocabulary"]
    assert any(r["id"] == "OQ-A910-05" and r["status"] == "OPEN" for r in doc["rows"])


def test_a9_2_supersession_pointers_and_affected_open_rows(doc):
    """Review repair 3: the A9.1 off-platform matching answer carries an explicit A9.2 OQ-A907-11 supersession pointer
    (A9.1 decision row and ICPQ-05); the OPEN ICPQ-10 / ICPQ-11 are marked A9.2-affected and stay OPEN."""
    by = {(r["id"], r["kind"]): r for r in doc["rows"]}
    for key in (("A9-03-matching", "a9_1"), ("ICPQ-05", "lane")):
        r = by[key]
        assert r["status"] in ("ANSWERED", "ANSWERED_BY_A9_1")
        assert "OQ-A907-11" in r["superseded_in_part_by_a9_2"] and "SUPERSEDED IN PART" in r["superseded_in_part_by_a9_2"]
    for qid in ("ICPQ-10", "ICPQ-11"):
        r = by[(qid, "lane")]
        assert r["status"] == "OPEN" and "A9.2 rf_500W" in r["a9_2_affected"] and "impedance map" in r["needed_by"]
    assert "not at a 500 W component rating" in by[("ICPQ-11", "lane")]["question"]
    csv_txt = (ROOT / "docs/budgets/owner_decisions/owner_questions_state_v2.csv").read_text(encoding="utf-8")
    assert csv_txt.count("SUPERSEDED IN PART") >= 2 and "A9.2-affected" in csv_txt
