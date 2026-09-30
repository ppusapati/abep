"""Tests for the A9-09 RFQ / quotation specification packages (fo_a9_09_rfq_packages).

Checks that docs/procurement/rfq_a9/ is reproducible from its builder, that every requirement is traced to an owner answer
row, an A9.1 decision (quoted verbatim) or a verified deliverable item, that owner-given values match the decision files,
that open items are TBD/PENDING with a freeze point, that every package carries the do-not-purchase banner, and that no
price, supplier ranking, winner or Hall-performance source appears. Run: python -m pytest -q tests/test_rfq_a9.py (seconds).
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "procurement" / "rfq_a9"
SCRIPT = LANE / "build_rfq_a9.py"
JSON_PATH = LANE / "rfq_a9_v1.json"
MD_PATH = LANE / "RFQ_A9.md"
ANS = REPO / "docs" / "decisions" / "OD_2026_09_29_owner_answers_147.json"
A91_JSON = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_1_followup_owner_decisions.json"
A91_MD = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md"

PINNED = {
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json":
        "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f",
    "docs/decisions/OD_2026_09_29_owner_answers_147.json":
        "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1",
    "docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md":
        "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976",
    "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json":
        "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4",
    "docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md":
        "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e",
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def reqs(doc):
    return {r["id"]: r for p in doc["packages"] for r in p["requirements"]}


@pytest.fixture(scope="module")
def answers():
    return {a["row"]: a for a in json.loads(ANS.read_text(encoding="utf-8"))["answers"]}


def _resolve(d, pointer):
    cur = d
    for raw in pointer[1:].split("/") if pointer else []:
        tok = raw.replace("~1", "/").replace("~0", "~")
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


def test_builder_check_reproduces_outputs():
    r = subprocess.run([sys.executable, str(SCRIPT), "--check"], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout


def test_identity_and_vocabulary(doc):
    assert doc["schema"] == "rfq_a9_v1"
    assert doc["follow_on"] == "fo_a9_09_rfq_packages" and doc["trigger"] == "T_A9_09_RFQ_PACKAGES"
    assert doc["configurations"] == ["hall_c1_reference", "hall_icp_neutralizer"]
    assert "NO_VIABLE_CASE" in doc["outcome_vocabulary"] and doc["status_not_outcome"] == ["OPEN"]
    assert "OPEN" not in doc["outcome_vocabulary"]
    assert doc["a9_status"] == "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE"
    assert doc["freeze_points"] == ["NOW", "LOCK-1", "LOCK-2", "after-evidence"]


def test_decision_pins_are_immutable_and_current(doc):
    pins = {p["path"]: p["sha256"] for p in doc["decision_pins"]}
    for path, sha in PINNED.items():
        assert pins[path] == sha
        assert _sha(REPO / path) == sha


def test_governance_files_never_pinned(doc):
    for p in doc["decision_pins"] + doc["deliverable_pins"]:
        assert "docs/orchestration/" not in p["path"]
        assert "runtime_state" not in p["path"]


def test_deliverable_pins_match_disk(doc):
    for p in doc["deliverable_pins"]:
        assert _sha(REPO / p["path"]) == p["sha256"], p["path"]


def test_nine_packages_with_banner(doc):
    ids = [p["id"] for p in doc["packages"]]
    assert ids == [f"RFQ-0{i}" for i in range(1, 10)]
    for p in doc["packages"]:
        assert "DO NOT PURCHASE" in p["banner"]
        assert "purchase orders are NOT authorized" in p["banner"]
        md = (REPO / p["package_file"]).read_text(encoding="utf-8")
        assert p["banner"] in md
        for r in p["requirements"]:
            assert r["id"] in md
    assert doc["packages"][-1].get("information_only") is True
    assert "DO NOT PURCHASE" in MD_PATH.read_text(encoding="utf-8")


def test_every_source_resolves(doc, answers):
    md = A91_MD.read_text(encoding="utf-8")
    a91 = json.loads(A91_JSON.read_text(encoding="utf-8"))
    for p in doc["packages"]:
        for r in p["requirements"]:
            assert r["sources"], r["id"]
            for s in r["sources"]:
                if s["type"] == "owner_row":
                    a = answers[s["row"]]
                    assert s["quote"] in a["owner_answer_verbatim"], (r["id"], s["row"])
                    assert s["answer_sha256"] == hashlib.sha256(a["owner_answer_verbatim"].encode()).hexdigest()
                elif s["type"] == "a9_1":
                    assert s["quote"] in md, (r["id"], s["id"])
                    assert s["id"] in a91["decisions"] or s["id"] == "A9-09"
                elif s["type"] == "deliverable_item":
                    node = _resolve(json.loads((REPO / s["path"]).read_text(encoding="utf-8")), s["pointer"])
                    assert s["id"] in (node.get("id"), node.get("slot")), (r["id"], s["id"])
                else:
                    _resolve(json.loads((REPO / s["path"]).read_text(encoding="utf-8")), s["pointer"])


def test_requirement_record_discipline(doc):
    pending_paths = set(doc["pending_lanes"].values())
    for p in doc["packages"]:
        for r in p["requirements"]:
            assert r["freeze_point"] in doc["freeze_points"]
            assert set(r["applies_to"]) <= {"hall_c1_reference", "hall_icp_neutralizer"}
            v = r["value"]
            if isinstance(v, str) and (v.startswith("TBD - requires") or v.startswith("PENDING ")):
                assert r["status"] in ("TBD", "PENDING") and r["evidence_class"] is None, r["id"]
                if v.startswith("PENDING "):
                    assert any(pp in v for pp in pending_paths), r["id"]
            else:
                assert r["evidence_class"] in doc["evidence_classes"], r["id"]
            if r["status"] == "OWNER_GIVEN":
                assert any(s["type"] in ("owner_row", "a9_1") for s in r["sources"]), r["id"]
        opened = {o["id"] for o in p["open_specification_items"]}
        expect = {r["id"] for r in p["requirements"] if isinstance(r["value"], str)
                  and (r["value"].startswith("TBD - requires") or r["value"].startswith("PENDING "))}
        assert opened == expect


def test_owner_given_values(reqs):
    assert reqs["RFQ-01-R01"]["value"] == "torsional baseline"
    assert reqs["RFQ-01-R03"]["value"] == 25.0
    assert reqs["RFQ-01-R05"]["value"] == 1.0 and "k = 1" in reqs["RFQ-01-R05"]["units"]
    assert any(s.get("id") == "UBQ-01" for s in reqs["RFQ-01-R05"]["sources"])
    assert reqs["RFQ-01-R06"]["value"] == 12.0
    assert reqs["RFQ-02-R02"]["value"] == 4
    assert reqs["RFQ-02-R08"]["value"] == [0.05, 0.2]
    assert reqs["RFQ-02-R09"]["value"] == 0.0005
    assert reqs["RFQ-02-R11"]["value"] == [0.6, 0.8]
    assert reqs["RFQ-03-R01"]["value"] == 200
    assert reqs["RFQ-04-R01"]["value"] == 13.56
    assert reqs["RFQ-04-R02"]["value"] == [0.0, 500.0]
    assert reqs["RFQ-06-R02"]["value"] == 100.0
    assert reqs["RFQ-06-R08"]["value"] == ">= 20" and reqs["RFQ-06-R08"]["units"] == "kHz"
    assert reqs["RFQ-06-R09"]["value"] == ">= 100" and reqs["RFQ-06-R09"]["units"] == "kSa/s"
    assert reqs["RFQ-07-R01"]["value"] == 323.0
    assert reqs["RFQ-07-R02"]["value"] == [2.0, 5.0, 10.0]
    assert reqs["RFQ-07-R05"]["value"] == 2
    assert reqs["RFQ-07-R07"]["value"] == 0.0
    assert reqs["RFQ-08-R04"]["value"] == [300.0, 600.0]
    assert reqs["RFQ-08-R05"]["value"]["design_isolation_basis_V"] == 900.0
    assert reqs["RFQ-08-R06"]["value"] == 1.0 and reqs["RFQ-08-R06"]["units"] == "kV DC"
    assert reqs["RFQ-05-R03"]["freeze_point"] == "after-evidence"  # collector material NOT frozen


def test_derived_arithmetic(doc):
    d = doc["derived"]
    assert math.isclose(d["u_T_standard_at_acceptance_point_mN"]["value"], 0.12)
    assert d["samples_per_1ms_window_at_min_rate"]["value"] == 100
    assert d["nyquist_at_min_rate_kHz"]["value"] >= 20.0
    assert d["keeper_isolation_basis_ratio"]["value"] == 1.5
    r6 = json.loads((REPO / "docs/procurement/web_track_v1/threads/R6_xe_inputs.json").read_text(encoding="utf-8"))
    rho = next(h for h in r6["hardware_mass_data"] if h["item"] == "Xe density (supercritical)")["values"]["323.15K"]
    for case, per in d["xe_tank_indicative_volume_L"]["value"].items():
        m = float(case.split()[0])
        for p, v in per.items():
            assert math.isclose(v, m / rho[p], rel_tol=1e-4)
    for name, row in d["mfc_four_range_check"]["value"].items():
        assert math.isclose(row["per_range_span_for_4_ranges"], row["turndown"] ** 0.25, rel_tol=1e-5), name
    for c in ("hall_c1_reference", "hall_icp_neutralizer"):
        assert d["p_bus_channel_slots"]["value"][c]["n_installed"] == len(d["p_bus_channel_slots"]["value"][c]["INSTALLED"])


def test_traceability_matrix_complete(doc, reqs):
    rows = doc["traceability_matrix"]["requirement_to_source"]
    assert sorted(r["requirement"] for r in rows) == sorted(reqs)
    assert all(r["sources"] for r in rows)


def test_required_sections(doc, answers):
    for k in ("interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse", "m16_impact",
              "h3_h4_inputs"):
        assert doc[k], k
    rows = {a["row"] for a in doc["owner_answers_applied"]}
    assert {8, 115, 116, 119, 120, 121, 123, 124, 125, 126, 127, 72, 113, 48, 50, 90, 49, 89} <= rows
    for a in doc["owner_answers_applied"]:
        assert a["answer_sha256"] == hashlib.sha256(answers[a["row"]]["owner_answer_verbatim"].encode()).hexdigest()
    m16 = json.loads((REPO / "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json").read_text(encoding="utf-8"))
    keys = {r["row"]: r["key"] for r in m16["rows"]}
    for m in doc["m16_impact"]:
        assert keys[m["m16_row"]] == m["key"]
        assert "no purchase order" in m["proposed_procurement_status"]
    for h in doc["historical_reuse"]["artifacts"]:
        assert _sha(REPO / h["path"]) == h["sha256"]
    assert doc["h3_h4_inputs"]["h3_procurement_gate"]["state"].endswith("PURCHASE ORDERS NOT AUTHORIZED")
    for q in doc["open_owner_questions"]:
        assert q["proposed_answer"]


def test_no_prices_ranking_winner_or_hall_performance_source(doc):
    blob = JSON_PATH.read_text(encoding="utf-8")
    low = blob.lower()
    for banned in ('"price"', '"cost"', "₹", " inr ", " usd", "winner:", "sgb-screen", "plasma_devices.py",
                   "hall_map.py", "hall_ensemble"):
        assert banned not in low, banned
    for p in doc["packages"]:
        for c in p["reference_data"]:
            assert c["use"].startswith("REFERENCE ONLY")


def test_builder_is_pure_and_contactless():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "xe_ledger" not in src
    for banned in ("import abep_sim", "from abep_sim", "import archengine", "subprocess", "urllib", "requests", "smtplib",
                   "socket", "http.client"):
        assert banned not in src, banned
