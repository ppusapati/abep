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


def test_rvm_mapping_section_and_transcription_unchanged():
    import hashlib
    d = json.loads((D / "rfp_registration_v1.json").read_text(encoding="utf-8"))
    canon = json.dumps(d["clauses"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    # transcription byte-identical to the registered v1 (the RVM mapping section is additive)
    assert hashlib.sha256(canon).hexdigest() == "fd51a951a1d06ea8bebd39416147686aedb1f596170fb81b6583f4564148a8aa"
    m = d["rvm_mapping"]
    assert m["clauses_sha256"] == hashlib.sha256(canon).hexdigest()
    assert [c["clause_id"] for c in m["clauses"]] == [c["id"] for c in d["clauses"]]
    rvm = json.loads((ROOT / "docs/requirements/rvm_a9/rvm_a9_v1.json").read_text(encoding="utf-8"))
    rows = {r["id"] for r in rvm["rows"]}
    for c in m["clauses"]:
        assert c["rvm_rows"] or c["not_system_requirement"], c["clause_id"]
        assert set(c["rvm_rows"]) <= rows
    assert {r["origin"] for r in m["rows_not_from_rfp"]} <= {"DERIVED_PROJECT_REQUIREMENT", "OWNER_ALLOCATION"}
    for r in m["requirements_to_check_against_rvm_resolution"]:
        assert r["rvm_rows"], r["clause_id"]
    assert {"DISC-01", "DISC-02"} <= {x["id"] for x in m["discrepancies"]}
