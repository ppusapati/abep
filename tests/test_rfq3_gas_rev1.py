"""Tests for RFQ3-GAS rev1 (A9.25 message 8 section 5): the GAS-only successor revision of the authorized RFQ v3 package.

Checks reproducibility, that RFQ v3 is preserved (pinned, never overwritten), the current AL-08 context read from mass /
power v4 (4.929 / 5.9148 kg, provisional, internal floor not a supplier maximum), that the v3 6.0528 / 5.044 kg context
survives only as labelled history, the quotation split, C1 lines ground-only, the dispatch rule and the other five
packages unchanged. Run: python -m pytest -q tests/test_rfq3_gas_rev1.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "procurement" / "rfq_a9_v3_gas_rev1"
BUILDER = LANE / "build_rfq3_gas_rev1.py"


def _mod():
    spec = importlib.util.spec_from_file_location("build_rfq3_gas_rev1_t", BUILDER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _doc():
    return json.loads((LANE / "rfq3_gas_rev1.json").read_text(encoding="utf-8"))


def test_check_reproduces():
    r = subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_v3_preserved_and_other_packages_unchanged():
    m = _mod()
    for p, s in m.PINS.values():
        assert hashlib.sha256((REPO / p).read_bytes()).hexdigest() == s, p
    d = _doc()
    assert sorted(d["unchanged_packages"]) == ["RFQ3-HALLEL", "RFQ3-MECH", "RFQ3-RF", "RFQ3-RFMET", "RFQ3-VAC"]
    for v in d["unchanged_packages"].values():
        assert hashlib.sha256((REPO / v["package"]).read_bytes()).hexdigest() == v["package_sha256"]
        assert hashlib.sha256((REPO / v["cover_note"]).read_bytes()).hexdigest() == v["cover_sha256"]
    assert d["authorized_v3_packages"] == ["RFQ3-RF", "RFQ3-GAS", "RFQ3-VAC", "RFQ3-HALLEL", "RFQ3-MECH", "RFQ3-RFMET"]


def test_current_al08_context():
    d = _doc()
    c = d["current_al08_context"]
    assert (c["AL-08_CBE_planning_floor_kg"], c["AL-08_MEV_planning_floor_kg"]) == (4.929, 5.9148)
    assert c["status"] == "PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN" and c["internal_planning_floor_not_supplier_requirement"]
    v = d["rfq2_gas_r28_rev1_value"]
    assert "NOT a supplier maximum-mass requirement" in v["internal_planning_floor"]
    assert v["history"]["label"].startswith("HISTORY") and v["history"]["v3_AL-08_MEV_planning_floor_kg"] == 6.0528
    pkg = (REPO / d["outputs"]["package"]).read_text(encoding="utf-8")
    for tok in ("6.0528", "5.044"):
        assert all("HISTORY" in ln for ln in pkg.splitlines() if tok in ln), tok
    assert pkg.count('"AL-08_MEV_planning_floor_kg": 5.9148') == 4
    assert hashlib.sha256(pkg.encode("utf-8")).hexdigest() == d["outputs"]["package_sha256"]


def test_split_c1_and_dispatch():
    d = _doc()
    cats = [s["category"] for s in d["quotation_split"]]
    assert cats[:6] == ["tank", "regulator", "two series isolation latches",
                        "anode / Xe-contingency proportional flow control", "plumbing", "mounting/thermal"]
    assert d["c1_lines"]["status"] == "GROUND_ONLY_LAB_EQUIPMENT" and d["c1_lines"]["in_flight_al08"] is False
    assert d["dispatch"]["v3_rfq3_gas_dispatch_status"].startswith("UNKNOWN_TO_REPOSITORY")
    assert "ONLY this successor" in d["dispatch"]["if_v3_not_sent"]
    assert "controlled addendum" in d["dispatch"]["if_v3_already_sent"]
    for t in ("purchase order", "advance payment", "supplier selection", "binding commitment"):
        assert t in d["dispatch"]["quotation_only"]
    add = (REPO / d["outputs"]["addendum"]).read_text(encoding="utf-8")
    assert "NOT a supplier maximum-mass requirement" in add and "QUOTATION ONLY" in add
    cover = (REPO / d["outputs"]["cover_note"]).read_text(encoding="utf-8")
    assert "RFQ3-GAS (package revision rev1, successor of v3)" in cover and "AUTHORIZED_PENDING_OWNER_SEND" in cover
