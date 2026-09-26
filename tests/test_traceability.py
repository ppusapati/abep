"""Checks on the DRDO RFP requirement traceability matrix (docs/traceability/)."""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TDIR = os.path.join(ROOT, "docs", "traceability")
JSON_PATH = os.path.join(TDIR, "rtm_v1.json")
STATUSES = {"modeled", "partial", "open", "blocked_by_gate_3"}
METHODS = {"analysis", "test", "demonstration", "inspection"}
EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}


def _doc():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_json_parses_and_has_requirements():
    d = _doc()
    assert d["schema"] == "abep-rtm-v1"
    assert d["rfp_document_in_repository"] is False
    assert len(d["requirements"]) > 0
    ids = [r["id"] for r in d["requirements"]]
    assert len(ids) == len(set(ids))


def test_every_requirement_has_source_status_and_verification_method():
    for r in _doc()["requirements"]:
        assert r["source"]["where"].strip(), r["id"]
        pr = r["source"]["page_ref"]
        if r["category"] == "derived_project":
            assert "not an RFP clause" in pr, r["id"]
        else:
            assert pr == "verify against RFP document", r["id"]
        assert r["status"] in STATUSES, r["id"]
        assert r["verification_method"] and set(r["verification_method"]) <= METHODS, r["id"]
        assert r["open_gap"].strip(), r["id"]


def test_numeric_values_carry_source_and_evidence_class():
    for r in _doc()["requirements"]:
        v = r["value"]
        if v is None:
            continue
        assert v["value_source"].strip(), r["id"]
        assert v["evidence_class"] in EVIDENCE_CLASSES, r["id"]


def test_nothing_gate3_blocked_claims_verified():
    d = _doc()
    for r in d["requirements"]:
        if r["gate3_dependent"] or r["status"] == "blocked_by_gate_3":
            assert r["status"] != "verified", r["id"]
            assert "verified" not in r["verification_status"].lower().replace("not_verified", ""), r["id"]
    # no row anywhere is marked verified (nothing is hardware-verified yet)
    assert all(r["status"] != "verified" for r in d["requirements"])
    # Hall-performance requirements must be marked gate-3 dependent
    for rid in ("RFP-THR-MIN", "RFP-THR-MAX", "RFP-PWR", "RFP-FIRING", "DER-NETDRAG", "DER-HALL-CLOSURE"):
        r = next(x for x in d["requirements"] if x["id"] == rid)
        assert r["gate3_dependent"] and r["status"] == "blocked_by_gate_3", rid


def test_model_refs_exist_in_code():
    for r in _doc()["requirements"]:
        for m in r["model_quantities"]:
            path, name = m["ref"].split("::")
            src = open(os.path.join(ROOT, path), encoding="utf-8").read()
            assert re.search(rf"^\s*(def|class)\s+{re.escape(name)}\b", src, re.M), m["ref"]


def test_evidence_files_exist_and_chains_cover_requirements():
    d = _doc()
    for r in d["requirements"]:
        for e in r["current_evidence"]:
            assert os.path.exists(os.path.join(ROOT, e["ref"])), e["ref"]
    ids = {r["id"] for r in d["requirements"]}
    chained = {c["requirement_id"] for c in d["chains"]}
    assert chained == ids
    for c in d["chains"]:
        assert all(c[k].strip() for k in ("design_feature", "verification", "evidence"))


def test_generated_files_are_current():
    out = subprocess.run([sys.executable, os.path.join(TDIR, "build_rtm.py"), "--check"],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout + out.stderr
