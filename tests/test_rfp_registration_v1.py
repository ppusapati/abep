"""AG-15: the official RFP registration is current and internally consistent."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs/requirements/rfp_official"


def test_registration_current():
    subprocess.run([sys.executable, str(D / "rfp_clauses_v1.py"), "--check"], check=True, cwd=ROOT)


def test_registration_identity_and_references():
    d = json.loads((D / "rfp_registration_v1.json").read_text(encoding="utf-8"))
    assert d["document"]["rfp_number"] == "DTDF/06/13516/DSP/ABEP/X/L/M/01"
    assert len(d["document"]["sha256"]) == 64 and d["document"]["pages"] == 40
    ids = {c["id"] for c in d["clauses"]}
    assert len(ids) == len(d["clauses"])
    assert all(1 <= c["page"] <= 40 for c in d["clauses"])
    for r in d["owner_rfp_fact_check"] + [{"clause_ids": [x["clause_id"]]} for x in d["requirements_to_check_against_rvm"]]:
        assert set(r["clause_ids"]) <= ids
