"""Owner decision brief P0 / P1 (docs/bid/owner_decision_brief_p0_p1.json + OWNER_DECISION_BRIEF_P0_P1.md).

Every quote in the brief names a file, a commit, a locator and the file's sha256. These tests re-read each file from git
at the cited commit and check (1) the sha256, (2) the exact value at the locator. They also check that the brief stays a
recorder brief: every referenced quote exists, recorder proposals are labelled as proposals, the 22 RFP_CLAUSE rows are
exactly the RVM rows at the base commit, and the bid commits agree with the bid freeze record.

The cited commits are pinned objects of the execution branch; in a checkout without them (e.g. a shallow clone) the
git-dependent tests skip with a message saying so (as the other provenance tests do, scripts/ci_checks.py).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BRIEF_JSON = os.path.join(ROOT, "docs", "bid", "owner_decision_brief_p0_p1.json")
BRIEF_MD = os.path.join(ROOT, "docs", "bid", "OWNER_DECISION_BRIEF_P0_P1.md")
BID_RECORD = os.path.join(ROOT, "docs", "bid", "bid_technical_baseline.json")
RVM = "docs/requirements/rvm_a9/rvm_a9_v1.json"
SEG = re.compile(r"^([^\[]*)(?:\[([^=\]]+)=([^\]]+)\])?$")
TEXT_LOC = re.compile(r"^L(\d+)(?:-L(\d+))?$")
PROPOSAL = "RECORDER_PROPOSAL_NOT_AN_OWNER_DECISION"
_BLOBS: dict = {}


def _brief() -> dict:
    with open(BRIEF_JSON, encoding="utf-8") as f:
        return json.load(f)


def _have_commit(commit: str) -> bool:
    try:
        r = subprocess.run(["git", "-C", ROOT, "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True,
                           timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def _blob(commit: str, path: str) -> bytes:
    key = (commit, path)
    if key not in _BLOBS:
        if not _have_commit(commit):
            pytest.skip(f"cited commit {commit} not available in this checkout (shallow clone?)")
        r = subprocess.run(["git", "-C", ROOT, "show", f"{commit}:{path}"], capture_output=True, timeout=60)
        assert r.returncode == 0, f"{path} does not exist at {commit}: {r.stderr.decode(errors='replace')}"
        _BLOBS[key] = r.stdout
    return _BLOBS[key]


def resolve(doc, locator: str):
    """The brief's locator syntax (see the JSON 'locator_syntax'); a selector must match exactly one element."""
    node = doc
    for seg in locator.strip("/").split("/"):
        m = SEG.match(seg)
        assert m, f"bad locator segment {seg!r} in {locator}"
        key, field, value = m.group(1), m.group(2), m.group(3)
        if key != "":
            node = node[int(key)] if isinstance(node, list) else node[key]
        if field is not None:
            hits = [x for x in node if isinstance(x, dict) and str(x.get(field)) == value]
            assert len(hits) == 1, f"{locator}: selector [{field}={value}] matches {len(hits)} elements"
            node = hits[0]
    return node


def _referenced_ids(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("quote_ids", "evidence_quote_ids"):
                out.extend(v)
            else:
                _referenced_ids(v, out)
    elif isinstance(o, list):
        for v in o:
            _referenced_ids(v, out)
    return out


# ------------------------------------------------------------------------------------------------- static structure
def test_brief_structure_and_quote_references():
    d = _brief()
    assert d["schema"] == "owner_decision_brief_p0_p1_v1"
    assert d["status"].startswith("RECORDER_BRIEF_FOR_OWNER")
    assert [it["no"] for it in d["items"]] == [1, 2, 3, 4, 5, 6, 7]
    assert [it["id"] for it in d["items"]] == ["AG-15", "MPV3Q-01", "XV3Q-01", "GNG-ICP-01", "BID-FREEZE-CAVEAT",
                                               "RECORDER-READINGS", "OUTSIDE-REPOSITORY"]
    qids = [q["id"] for q in d["quotes"]]
    assert len(qids) == len(set(qids)), "duplicate quote ids"
    missing = sorted(set(_referenced_ids(d["items"], [])) - set(qids))
    assert not missing, f"items reference unknown quotes: {missing}"
    for it in d["items"]:
        assert it.get("one_line_answer_form"), it["id"]
    files = {(f["path"], f["commit"]): f for f in d["files"]}
    for q in d["quotes"]:
        assert q["kind"] in ("json", "text"), q["id"]
        assert re.fullmatch(r"[0-9a-f]{40}", q["commit"]), q["id"]
        assert re.fullmatch(r"[0-9a-f]{64}", q["sha256"]), q["id"]
        assert files[(q["path"], q["commit"])]["sha256"] == q["sha256"], q["id"]
        if q["kind"] == "text":
            assert TEXT_LOC.match(q["locator"]), q["id"]


def test_brief_answers_no_owner_question():
    """Recorder proposals are labelled as such; options carry a recorded / observation origin, never a decision."""
    d = _brief()
    allowed = {"OPTION_AS_RECORDED_IN_REPOSITORY", "RECORDER_OBSERVATION_OF_REPOSITORY_FACT", PROPOSAL}
    for it in d["items"]:
        for o in it.get("options", []):
            assert o["origin"] in allowed, (it["id"], o["id"])
        for p in it.get("recorder_proposals", []):
            assert p["origin"] == PROPOSAL and "PROPOSAL" in p["status"], (it["id"], p["id"])
        for o in it.get("recorder_observations", []):
            assert o["origin"] == "RECORDER_OBSERVATION_OF_REPOSITORY_FACT", it["id"]
    gng = next(it for it in d["items"] if it["id"] == "GNG-ICP-01")
    assert gng["proposal_verbatim"]["origin"].startswith("RECORDER_PROPOSAL_RP-A919-01")


def test_bid_commits_agree_with_the_bid_freeze_record():
    d = _brief()
    with open(BID_RECORD, encoding="utf-8") as f:
        bid = json.load(f)
    assert d["bid_technical_source_commit"] == bid["bid_technical_source"]["commit"]
    assert d["post_freeze_commit_cited"].startswith(bid["post_freeze_commits_known_at_freeze"]["range"].split("..")[1])


def test_markdown_companion_cites_every_file_and_item():
    d = _brief()
    with open(BRIEF_MD, encoding="utf-8") as f:
        md = f.read()
    for fe in d["files"]:
        assert fe["sha256"] in md, fe["path"]
    for it in d["items"]:
        assert it["one_line_answer_form"].replace("|", "\\|") in md, it["id"]
    for p in (p for it in d["items"] for p in it.get("recorder_proposals", [])):
        assert f"RECORDER PROPOSAL {p['id']} (not a decision)" in md
    for q in d["quotes"]:   # every quote is shown or tabulated by id
        assert f"[{q['id']}]" in md or q["id"].startswith("Q1-RVM-") or q["id"].startswith("Q1-DISC-"), q["id"]


# ------------------------------------------------------------------------------------------------- git-backed checks
def test_every_cited_file_matches_its_sha256_at_the_cited_commit():
    d = _brief()
    for fe in d["files"]:
        b = _blob(fe["commit"], fe["path"])
        assert hashlib.sha256(b).hexdigest() == fe["sha256"], (fe["path"], fe["commit"])
        assert len(b) == fe["size_bytes"], (fe["path"], fe["commit"])


def test_every_quote_is_verbatim_at_its_locator():
    d = _brief()
    docs = {}
    for q in d["quotes"]:
        b = _blob(q["commit"], q["path"])
        assert hashlib.sha256(b).hexdigest() == q["sha256"], q["id"]
        if q["kind"] == "json":
            key = (q["commit"], q["path"])
            if key not in docs:
                docs[key] = json.loads(b.decode("utf-8"))
            assert resolve(docs[key], q["locator"]) == q["verbatim"], q["id"]
        else:
            m = TEXT_LOC.match(q["locator"])
            a, z = int(m.group(1)), int(m.group(2) or m.group(1))
            lines = b.decode("utf-8").split("\n")
            assert q["verbatim"] and q["verbatim"] in "\n".join(lines[a - 1:z]), q["id"]


def test_ag15_rows_are_exactly_the_open_rfp_clause_rows_at_the_base_commit():
    d = _brief()
    rvm = json.loads(_blob(d["base_commit"], RVM).decode("utf-8"))
    rfp_rows = [r["id"] for r in rvm["rows"] if r["requirement_origin"] == "RFP_CLAUSE"]
    assert len(rfp_rows) == 22 and all(r["requirement_frozen"] is False for r in rvm["rows"] if r["id"] in rfp_rows)
    ag15 = next(it for it in d["items"] if it["id"] == "AG-15")
    assert [r["row"] for r in ag15["rfp_clause_rows"]] == rfp_rows
    assert ag15["recorder_proposals"][0]["proposed_record"]["fields"]["frozen_rows"] == rfp_rows
    disc = [q["verbatim"]["id"] for q in d["quotes"] if q["id"].startswith("Q1-DISC-")]
    assert disc == [x["id"] for x in rvm["rfp_rebase"]["discrepancies"]]
