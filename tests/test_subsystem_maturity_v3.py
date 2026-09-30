"""M16 v3 (A9-10 refresh): reproducible, v1/v2 untouched, row 17 superseded, ICP head and flight RF chain rows present,
every row owned (functional role per owner row 140), scheduler vocabulary from v2 plus the v3 addition.

    python -m pytest -q tests/test_subsystem_maturity_v3.py
"""
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
D0 = ROOT / "docs" / "budgets" / "subsystem_maturity"
D = D0
# declared scope deviation (OQ-A910-04): the immutable H2-7 v1 BOM builder scans subsystem_maturity/*.json
# non-recursively and pins every file, so the v3 JSON lives under an allowed A9-10 path
JSON = ROOT / "docs" / "experiments" / "hall_icp" / "integration" / "m16_v3" / "subsystem_maturity_v3.json"
BUILDER = D / "build_subsystem_maturity_v3.py"
BASE = "ecdad06e30bc5d2f172e862e4bd4843e86332d42"


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON.read_text(encoding="utf-8"))


def test_builder_check():
    r = subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, (r.stdout[-1500:], r.stderr[-1500:])


def test_v1_v2_byte_identical():
    for name in ("subsystem_maturity_v1.json", "SUBSYSTEM_MATURITY.md", "subsystem_maturity_v2.json",
                 "SUBSYSTEM_MATURITY_v2.md", "build_subsystem_maturity.py"):
        rel = f"docs/budgets/subsystem_maturity/{name}"
        base = subprocess.run(["git", "show", f"{BASE}:{rel}"], cwd=ROOT, capture_output=True).stdout
        assert base and (ROOT / rel).read_bytes() == base, name


def test_pins(doc):
    s = doc["supersedes_for_use"]
    assert hashlib.sha256((ROOT / s["path"]).read_bytes()).hexdigest() == s["sha256"]
    for p in doc["pins"] + doc["lane_deliverables_read"]:
        assert hashlib.sha256((ROOT / p["path"]).read_bytes()).hexdigest() == p["sha256"], p["path"]
        assert "lane_registry" not in p["path"] and "trigger_registry" not in p["path"]
        assert "runtime_state" not in p["path"]


def test_rows(doc):
    rows = {r["row"]: r for r in doc["rows"]}
    assert sorted(rows) == list(range(1, 22))                              # A9.2 adds rows 20 / 21 (anode)
    assert rows[17]["a9_refresh"]["execution_state"] == "SUPERSEDED_FOR_PRIMARY_LINE"
    assert rows[18]["key"] == "icp_neutralizer_head" and rows[19]["key"] == "flight_rf_chain"
    for k in (18, 19):
        assert rows[k]["baseline_flight_hardware"] is False and rows[k]["new_in_v3"] is True
    states = set(doc["scheduler_rule"]["states"]) | {"SUPERSEDED_FOR_PRIMARY_LINE"}
    vocab = set(doc["waits_on_vocabulary"])
    for r in doc["rows"]:
        a = r["a9_refresh"]
        assert a["execution_state"] in states, r["row"]
        assert a["owner"], r["row"]                                     # no row unowned (owner row 140)
        if a["execution_state"] != "SUPERSEDED_FOR_PRIMARY_LINE":
            assert a["blocking_item"], r["row"]
        if a["execution_state"] == "BLOCKED":
            assert a["waits_on"] in vocab, r["row"]


def test_rollup(doc):
    c = Counter(r["a9_refresh"]["execution_state"] for r in doc["rows"])
    assert dict(c) == doc["rollup"]["execution_states"]
    assert sum(doc["rollup"]["waits_on"].values()) == c["BLOCKED"]
    assert "READY" not in c or all(r["a9_refresh"]["owner"] for r in doc["rows"])


def test_status_and_no_winner(doc):
    assert doc["a9_status"] == "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE"
    t = json.dumps(doc).lower()
    assert "winner:" not in t and "recommended architecture" not in t
    for q in doc["open_owner_questions"]:
        assert q["proposed_answer"] and q["needed_by"]


def test_a9_2_rows_and_statuses(doc):
    rows = {r["row"]: r for r in doc["rows"]}
    st = doc["a9_2"]["statuses"]
    assert st["RF matching architecture"] == "LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT"
    assert st["coupled H-1/ICP thermal closure"] == "UNRESOLVED" and st["C1 conventional reference"] == "CONTROL_FALLBACK"
    assert rows[20]["key"] == "h1_anode_material" and rows[21]["key"] == "h1_anode_heat_path"
    for k in (20, 21):
        assert rows[k]["a9_refresh"]["execution_state"] == "BLOCKED" and rows[k]["baseline_flight_hardware"] is False
    assert rows[20]["a9_2"]["statuses"]["316L flight anode"] == "REJECTED_AS_CURRENT_BASELINE"
    assert rows[21]["a9_2"]["statuses"]["anode thermal closure"] == "UNRESOLVED"
    assert "coupled H-1 / ICP thermal model" in rows[13]["a9_refresh"]["blocking_item"]["text"]
    assert "impedance map" in rows[15]["a9_refresh"]["blocking_item"]["text"]
    assert "LOCAL matching network" in rows[19]["name"]
    assert rows[18]["a9_2"]["statuses"]["ICP electron-current capacity"] == "PENDING_ICP45"
    assert rows[11]["a9_2"]["statuses"]["C1 conventional reference"] == "CONTROL_FALLBACK"
