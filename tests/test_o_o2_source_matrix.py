"""Structural checks for the O/O2 source audit (docs/chemistry/o_o2/).

The audit is documentation only: these tests check that the files parse, that every matrix row carries a status and an
access field from the declared vocabularies, that every cited source key resolves, that LXCat is not used as an access
route, and that the completeness pre-registration is still a DRAFT living outside hallthruster_bridge/prereg/.
No network access, no solver, no chemistry is exercised.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "docs" / "chemistry" / "o_o2"
MATRIX_JSON = AUDIT_DIR / "o_o2_source_matrix_v1.json"
MATRIX_MD = AUDIT_DIR / "o_o2_source_matrix_v1.md"
DRAFT_JSON = AUDIT_DIR / "o_o2_completeness_prereg_DRAFT.json"
PREREG_DIR = ROOT / "hallthruster_bridge" / "prereg"
N2_PREREG = PREREG_DIR / "n2_completeness_audit_v1.json"

ROW_STATUS = {"source-identified", "source-open", "gap"}
ACCESS = {"open", "paywalled", "mixed", "not-verified", "none"}
ROW_ID = re.compile(r"^OO2-\d{2}$")


@pytest.fixture(scope="module")
def matrix():
    return json.loads(MATRIX_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def draft():
    return json.loads(DRAFT_JSON.read_text(encoding="utf-8"))


def test_files_exist_and_parse(matrix, draft):
    assert MATRIX_MD.is_file()
    assert matrix["id"] == "o_o2_source_matrix_v1"
    assert draft["id"].endswith("_DRAFT")
    assert matrix["rows"], "matrix has no rows"
    assert matrix["sources"], "matrix has no sources"


def test_vocabularies_match_declared(matrix):
    assert set(matrix["vocabulary"]["status"]) == ROW_STATUS
    assert set(matrix["vocabulary"]["access"]) == ACCESS


def test_every_row_has_status_and_access(matrix):
    ids = []
    for row in matrix["rows"]:
        rid = row.get("id")
        assert rid and ROW_ID.match(rid), f"bad row id {rid!r}"
        ids.append(rid)
        assert row.get("status") in ROW_STATUS, f"{rid}: status {row.get('status')!r}"
        assert row.get("access") in ACCESS, f"{rid}: access {row.get('access')!r}"
        assert isinstance(row.get("access_detail"), str) and row["access_detail"].strip(), f"{rid}: no access_detail"
        for key in ("target", "process", "reaction", "quantity_needed", "energy_range_eV", "stated_uncertainty",
                    "applicability", "solver_reaction_type", "proposed_tier_DRAFT"):
            assert isinstance(row.get(key), str) and row[key].strip(), f"{rid}: missing {key}"
        assert isinstance(row.get("open_issues"), list), f"{rid}: open_issues must be a list"
    assert len(ids) == len(set(ids)), "duplicate row ids"


def test_status_is_consistent_with_sources(matrix):
    for row in matrix["rows"]:
        rid = row["id"]
        if row["status"] == "gap":
            assert row["access"] == "none", f"{rid}: a gap row has no access route"
            assert row["recommended_source"] is None, f"{rid}: a gap row cannot name a recommended source"
        else:
            assert row["candidate_sources"], f"{rid}: {row['status']} row needs at least one candidate source"


def test_every_source_reference_resolves(matrix):
    sources = matrix["sources"]
    for row in matrix["rows"]:
        rec = row.get("recommended_source")
        if rec is not None:
            assert rec in sources, f"{row['id']}: unknown recommended source {rec}"
        for cand in row["candidate_sources"]:
            assert cand.get("source") in sources, f"{row['id']}: unknown source {cand.get('source')}"
            for key in ("role", "quantity_type", "energy_range_eV", "stated_uncertainty"):
                assert isinstance(cand.get(key), str) and cand[key].strip(), f"{row['id']}/{cand['source']}: {key}"
    for key in matrix.get("context_only_sources", {}):
        assert key in sources, f"unknown context-only source {key}"


def test_every_source_has_citation_access_and_evidence_level(matrix):
    for key, src in matrix["sources"].items():
        assert isinstance(src.get("citation"), str) and src["citation"].strip(), key
        assert src.get("access") in ACCESS, f"{key}: access {src.get('access')!r}"
        assert isinstance(src.get("verified_by"), str) and src["verified_by"].strip(), f"{key}: verified_by"
        assert src.get("evidence_level") in {1, 2, 3, 4, 5, 6, 7}, f"{key}: evidence_level"
        doi = src.get("doi")
        assert doi is None or doi.startswith("10."), f"{key}: malformed DOI {doi!r}"
        sha = src.get("document_sha256")
        assert sha is None or re.fullmatch(r"[0-9a-f]{64}", sha), f"{key}: malformed sha256"
        if sha is not None:
            assert src.get("url_accessed"), f"{key}: a hashed document needs the URL it was read from"


def test_lane_scope_is_covered(matrix):
    targets = {row["target"] for row in matrix["rows"]}
    for t in ("O", "O2", "O+", "O2+"):
        assert t in targets, f"target {t} missing"
    text = {row["id"]: (row["process"] + " " + row["reaction"]).lower() for row in matrix["rows"]}
    blob = " ".join(text.values())
    required = [
        "o ionization", "momentum transfer", "o electronic excitation", "o2 non-dissociative ionization",
        "dissociative ionization to o+ + o", "dissociation into neutrals", "vibrational", "rotational",
        "a1delta_g", "herzberg", "schumann-runge", "dissociative electron attachment", "o+ -> o^2+",
        "o2+ -> o2^2+", "recombination", "detachment",
    ]
    for phrase in required:
        assert phrase in blob, f"scope item {phrase!r} not covered by any row"


def test_lxcat_not_used(matrix):
    assert matrix["policy"]["lxcat"].startswith("NOT USED")
    for key, src in matrix["sources"].items():
        for field in ("url_accessed", "doi"):
            value = src.get(field) or ""
            assert "lxcat" not in value.lower(), f"{key}: LXCat used as {field}"


def test_markdown_lists_every_row(matrix):
    md = MATRIX_MD.read_text(encoding="utf-8")
    for row in matrix["rows"]:
        assert f"| {row['id']} |" in md, f"{row['id']} missing from the markdown table"
    assert "DRAFT_PENDING_OWNER" in md


def test_draft_is_a_draft_and_not_under_prereg(draft):
    assert draft["status"] == "DRAFT_PENDING_OWNER"
    assert draft["registered"] is None
    assert draft["decided_by"] is None
    assert PREREG_DIR.resolve() not in DRAFT_JSON.resolve().parents
    assert AUDIT_DIR.resolve() in DRAFT_JSON.resolve().parents
    leaked = [p.name for p in PREREG_DIR.glob("*") if re.search(r"o_o2|oxygen", p.name, re.IGNORECASE)]
    assert not leaked, f"O/O2 files found under hallthruster_bridge/prereg: {leaked}"


def test_draft_thresholds_mirror_n2_rule(draft):
    n2 = json.loads(N2_PREREG.read_text(encoding="utf-8"))
    for key, value in n2["thresholds"].items():
        assert draft["thresholds"][key] == value, f"threshold {key} differs from the N2 rule"
    assert draft["rule"].startswith(n2["rule"].rstrip("."))


def test_draft_tiers_reference_existing_rows(matrix, draft):
    ids = {row["id"] for row in matrix["rows"]}
    tier_text = json.dumps(draft["tiers"]) + json.dumps(draft["outside_this_rule"])
    referenced = set(re.findall(r"OO2-\d{2}", tier_text))
    assert referenced, "draft tiers reference no matrix rows"
    assert referenced <= ids, f"draft references unknown rows {sorted(referenced - ids)}"
    for tier in ("1_required_before_any_scoring", "2_assess_before_complete",
                 "3_assessed_not_included_unless_bound_exceeds"):
        assert draft["tiers"][tier], f"empty tier {tier}"
    for od, text in draft["owner_decisions_required"].items():
        assert re.fullmatch(r"OD-\d", od) and text.strip()
