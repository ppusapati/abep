"""Technical annexure rev 2 (docs/proposal/technical_annexure_dbf1_2/, DRAFT_FOR_OWNER_REVIEW): evidence-discipline checks.

The design source is one pin (annexure_pin_v1.json): the DBF-1.2 freeze commit and its lock sha256. The generator reads
everything at that commit and hash-verifies it; these tests check the pin, reproducibility, the clause register, the
status-change rule, the labels DBF-1.2 must never carry, the withdrawn 0-D Hall phrases, and that the historical bid
package is untouched.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ANX = os.path.join(ROOT, "docs", "proposal", "technical_annexure_dbf1_2")
sys.path.insert(0, ANX)
import annexure_data as ad  # noqa: E402
import build_annexure as ba  # noqa: E402

PIN = json.load(open(os.path.join(ANX, "annexure_pin_v1.json"), encoding="utf-8"))
MD = ["README.md", "A1_COMPLIANCE_MATRIX.md", "A2_TECHNICAL_DESCRIPTION.md", "A3_VERIFICATION_PLAN.md",
      "A4_RISK_REGISTER.md"]
WITHDRAWN_PHRASES = ["2.5 kW closure", "2.5 kW Hall closure", "110-120 kg", "110–120 kg", "110 - 120 kg",
                     "110 to 120 kg", "P(success) 0.77", "0.77 vs 0.63", "0.77 versus 0.63"]
NEGATED = re.compile(r"\b(no|not|never|none|nor|without)\b", re.IGNORECASE)


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True)


@pytest.fixture(scope="module")
def sources():
    for c in (PIN["dbf1_2"]["commit"], PIN["historical_bid_package"]["package_commit"]):
        if _git("cat-file", "-e", c + "^{commit}").returncode != 0:
            pytest.skip("pinned commit not present in this clone (shallow checkout)")
    return True


def _read(name):
    with open(os.path.join(ANX, name), encoding="utf-8") as f:
        return f.read()


def _matrix():
    return json.loads(_read("compliance_matrix_dbf1_2_v1.json"))


def test_pin_is_the_dbf1_2_freeze(sources):
    lock = _git("show", f"{PIN['dbf1_2']['commit']}:{PIN['dbf1_2']['lock_path']}").stdout
    assert hashlib.sha256(lock).hexdigest() == PIN["dbf1_2"]["lock_sha256"]
    assert json.loads(lock)["baseline"] == "DBF-1.2"


def test_generated_files_current(sources):
    out = ba.build_all()
    for name, text in out.items():
        assert _read(name) == text, f"{name} is stale: run build_annexure.py"


def test_every_registered_clause_once_in_order(sources):
    reg = json.loads(_git("show", f"{PIN['dbf1_2']['commit']}:docs/requirements/rfp_official/rfp_registration_v1.json").stdout)
    assert [c["id"] for c in _matrix()["clauses"]] == [c["id"] for c in reg["clauses"]]
    assert len(reg["clauses"]) == 37


def test_status_rule():
    j = _matrix()
    for c in j["clauses"]:
        assert c["status"] in ad.STATUSES
        if c["status"] == "COMPLY":
            assert c["previous_status_bid_package_2de86ab"] == "COMPLY", c["id"]
        if c["status"] != c["previous_status_bid_package_2de86ab"] and c["status"] == "COMPLY_PLANNED_WITH_EVIDENCE_PATH":
            assert c["dbf1_2_trace"], f"{c['id']} changed status without a DBF-1.2 trace row"
    by = {c["id"]: c for c in j["clauses"]}
    assert by["RFP-P19-03"]["status"] == "COMPLY" and by["RFP-P18-07"]["status"] == "COMPLY"
    assert by["RFP-P18-08"]["status"] == "COMPLY_PLANNED_WITH_EVIDENCE_PATH"  # A9.27 split kept
    for life_like in ("RFP-P19-01", "RFP-P17-02", "RFP-P20-03"):
        assert by[life_like]["status"] == "NOT_YET_DEMONSTRATED"
    assert sum(j["status_counts"].values()) == 37


def test_never_labelled_affirmatively():
    for name in MD:
        text = _read(name)
        for w in ba.FORBIDDEN:
            for m in re.finditer(re.escape(w), text):
                sentence = re.split(r"[.:]|\n\n", text[max(0, m.start() - 200):m.start()])[-1]
                assert NEGATED.search(sentence), f"{name}: '{w}' used affirmatively"


def test_no_withdrawn_hall_result_phrases():
    for name in MD + ["compliance_matrix_dbf1_2_v1.json"]:
        for ph in WITHDRAWN_PHRASES:
            assert ph not in _read(name), f"withdrawn Hall phrase {ph!r} in {name}"


def test_mass_and_power_read_from_dbf1_2(sources):
    d = json.loads(_git("show", f"{PIN['dbf1_2']['commit']}:docs/baseline/DBF-1.2/dbf1_2_v1.json").stdout)
    a2 = _read("A2_TECHNICAL_DESCRIPTION.md")
    assert f"**{d['mass_rollup']['wet_kg']:.3f}**" in a2
    assert d["mass_rollup"]["bid_wording"] in a2
    assert f"{d['power_rollup']['air_12mN']['reference']['P_bus_W']:.1f}" in a2
    assert "PARAMETRIC / NOT_VALIDATED" in a2 and "MR-DCR001-01" in a2


def test_open_thermal_dcr_and_closure_states_disclosed():
    a2, a4 = _read("A2_TECHNICAL_DESCRIPTION.md"), _read("A4_RISK_REGISTER.md")
    for t in (a2, a4):
        assert "DCR-DBF1-003" in t and "BLOCKED BY SPECIFIC MISSING EVIDENCE" in t and "DCR REQUIRED" in t


def test_historical_bid_package_untouched(sources):
    pkg = PIN["historical_bid_package"]["package_commit"]
    r = _git("diff", "--quiet", pkg, "--", "docs/bid/package")
    assert r.returncode == 0, "docs/bid/package differs from the terminal bid package state"
    assert not os.path.exists(os.path.join(ROOT, "docs", "bid", "annexure_dbf1_2"))
