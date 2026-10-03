"""AG-15: the official RFP registration is current and internally consistent."""
import hashlib
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


def test_page_coverage_screens_part_iv_items():
    """A9.16 repair RFP-07: every Part IV(B) item (no waivers) is a registered clause or a screened-out
    PROGRAMMATIC_BID_QUALIFICATION item; Part IV(C) criteria other than 5 are recorded as evaluation scoring."""
    d = json.loads((D / "rfp_registration_v1.json").read_text(encoding="utf-8"))
    pc = d["page_coverage"]
    so = {r["section"]: r for r in pc["screened_out"]}
    for item in ("1", "2", "4"):
        r = so[f"Part IV(B) {item}"]
        assert r["class"] == "PROGRAMMATIC_BID_QUALIFICATION" and "RFP-P21-03" in r["no_waiver"]
    reg = {c["section"] for c in d["clauses"]}
    assert any(s.startswith("Part IV(B) 3") for s in reg) and any(s.startswith("Part IV(B) 5") for s in reg)
    for item in ("1", "2", "3", "4", "6"):
        assert so[f"Part IV(C) {item}"]["class"] == "BID_EVALUATION_CRITERION"
    assert "UNSCREENED" in pc["pages_not_screened_as_registered"] and "pages_not_screened" not in pc
    pr = pc["owner_page_review"]                       # A9.22 G3: owner-stated review disposition (cited by sha256)
    assert pr["status"] == "OWNER_REVIEWED_NO_ADDITIONAL_TECHNICAL_PERFORMANCE_REQUIREMENT" and pr["pages"] == "1-15, 34-40"
    assert pr["decision"]["json_sha256"] == hashlib.sha256((ROOT / pr["decision"]["json"]).read_bytes()).hexdigest()
    md = (ROOT / pr["decision"]["md"]).read_text(encoding="utf-8")
    assert " ".join(pr["owner_statement_verbatim"].split()) in " ".join(md.split())
    assert set(pc["pages_with_registered_clauses"]) <= set(pc["pages_screened_for_clauses"])
