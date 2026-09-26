"""Tests for the v2 Question A owner-decision brief (docs/v2/question_a/).

The brief decides nothing (status DRAFT_PENDING_OWNER). These tests check its structure and that everything it copies
from the verified lane files (lane_01_n2_domain_extension @ 0636634, lane_02_ood_attribution @ 5e5c8a7) matches them.
The lane files are resolved read-only (checkout, then the lane commit, then .claude/worktrees/*); if they cannot be
found, the lane-dependent tests are skipped with a message saying so.
"""
from __future__ import annotations

import importlib.util
import json
import os

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QDIR = os.path.join(REPO, "docs", "v2", "question_a")
BRIEF_JSON = os.path.join(QDIR, "question_a_brief.json")
BRIEF_MD = os.path.join(QDIR, "QUESTION_A_BRIEF.md")
BUILDER = os.path.join(QDIR, "build_question_a_brief.py")

OPTION_IDS = ("A-NO", "A-PARTIAL", "A-YES-WITH-CONDITIONS")
FAMILY_SIZES = {"dissociation": 1, "electronic": 8, "rotational": 2, "vibrational": 10}
VERDICTS = {"SUPPORTED", "PARTIAL", "UNSUPPORTED", "UNRESOLVED-BY-SOURCE"}


def _brief() -> dict:
    with open(BRIEF_JSON, encoding="utf-8") as fh:
        return json.load(fh)


def _builder():
    spec = importlib.util.spec_from_file_location("build_question_a_brief", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _lane_json(path: str):
    mod = _builder()
    try:
        return mod.load_json(path)
    except mod.InputMissing as exc:
        pytest.skip(f"lane input not available in this checkout, its lane commit or any worktree "
                    f"(tests needing it are skipped): {exc}")


def _get(obj, path):
    cur = obj
    for k in path:
        if isinstance(cur, list):
            k = int(k)
        cur = cur[k]
    return cur


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


# ---------------------------------------------------------------------------------------------- structure only
def test_json_parses_and_is_a_pending_owner_draft():
    b = _brief()
    assert b["status"] == "DRAFT_PENDING_OWNER"
    assert b["lane"] == "fo_v2_domain_question_a"
    assert b["trigger"] == "T_V2_QUESTION_A"
    assert b["decides_nothing"] is True
    assert "INCONCLUSIVE" in b["v1_statement"]


def test_question_is_stated_verbatim_and_question_b_is_not_answered():
    q = _brief()["question"]
    assert q["verbatim_lane_task"].startswith("does INDEPENDENT PUBLISHED evidence justify expanding")
    assert "45 eV mean energy (T_e 30 eV)" in q["verbatim_lane_task"]
    assert "**Question A**" in q["verbatim_operating_model"]
    assert any("Question B" in s and "does not address" in s for s in q["scope_boundary"])
    assert any("Johnson-low" in s and "sensitivity" in s for s in q["scope_boundary"])


def test_every_option_present_and_none_chosen():
    b = _brief()
    ids = [o["id"] for o in b["options"]]
    assert ids == list(OPTION_IDS)
    assert b["chosen_option"] is None
    assert all(o["chosen"] is False for o in b["options"])
    assert b["owner_decisions"]["decided"] == []
    for o in b["options"]:
        for k in ("what_it_means", "requires_next", "admission_and_milestone_B", "ood_consequence_counting_only"):
            assert o[k], (o["id"], k)
    # no text anywhere marks an option as selected / recommended
    text = json.dumps(b).lower()
    for bad in ('"chosen": true', "recommended option", "we recommend", "selected option"):
        assert bad not in text


def test_every_table_family_is_covered_with_a_known_verdict():
    fams = _brief()["table_families"]
    assert set(fams) == set(FAMILY_SIZES)
    for f, n in FAMILY_SIZES.items():
        assert fams[f]["n_tables"] == n == len(fams[f]["per_table"])
        for row in fams[f]["per_table"]:
            assert row["verdict"] in VERDICTS
            assert row["family"] == f


def test_ood_consequences_are_labelled_counting_not_scoring():
    b = _brief()
    assert b["ood_consequence"]["label"].startswith("HYPOTHETICAL COUNTING ONLY")
    assert "not a score" in b["derived_bounds"]["label"]


def test_markdown_brief_states_status_and_every_option():
    with open(BRIEF_MD, encoding="utf-8") as fh:
        md = fh.read()
    assert "DRAFT_PENDING_OWNER" in md
    assert "decides nothing" in md
    for oid in OPTION_IDS:
        assert oid in md
    for fam in FAMILY_SIZES:
        assert fam.capitalize() in md or fam in md


# ---------------------------------------------------------------------------------------------- against lane files
def test_verdicts_match_lane01_audit():
    b = _brief()
    audit = _lane_json("docs/chemistry/n2_domain_extension/domain_extension_audit.json")
    lane_tables = audit["tables"]
    seen = set()
    for f, fam in b["table_families"].items():
        for row in fam["per_table"]:
            t = row["table"]
            seen.add(t)
            assert lane_tables[t]["family"] == f
            assert row["verdict"] == lane_tables[t]["verdict"], t
            assert row["proposed_extended_limit_mean_energy_eV"] == \
                lane_tables[t]["proposed_extended_limit_mean_energy_eV"], t
            assert fam["verdicts"][t] == lane_tables[t]["verdict"]
    assert seen == set(lane_tables)
    assert audit["draft_proposals"]["limits"] == {"dissociation_N2.dat": 60.0}
    assert b["table_families"]["dissociation"]["supported_extended_limits_mean_energy_eV_DRAFT"] == \
        audit["draft_proposals"]["limits"]


def test_every_quoted_number_resolves_to_its_source_field():
    mod = _builder()
    b = _brief()
    files = {}
    n = 0
    for node in _walk(b):
        if "value" in node and "file" in node and "path" in node:
            f = node["file"]
            if f not in files:
                if not f.endswith(".json"):
                    continue
                files[f] = _lane_json(f) if f in mod.INPUTS else None
            if files[f] is None:
                continue
            assert _get(files[f], node["path"]) == node["value"], (f, node["field"])
            n += 1
    assert n > 200


def test_copied_lane01_numbers_keep_their_requirements_path():
    b = _brief()
    req = _lane_json("docs/chemistry/n2_domain_extension/domain_extension_requirements.json")
    n = 0
    for fam in b["table_families"].values():
        for row in fam["per_table"]:
            for node in _walk({k: row.get(k) for k in ("criteria_numbers", "key_numbers", "independent_evidence")}):
                if "from" in node and "value" in node and isinstance(node["from"], list):
                    assert _get(req, node["from"]) == node["value"], node["from"]
                    n += 1
    assert n > 50


def test_cross_lane_checks_and_derived_bound():
    b = _brief()
    assert b["cross_lane_checks"] and all(c["equal"] for c in b["cross_lane_checks"])
    ood = _lane_json("docs/forensics/p5_n2_v1/ood_attribution/ood_attribution.json")
    pats = ood["co_occurrence"]["subfamily_pattern_counts"]
    r0 = sum(v for k, v in pats.items() if k.endswith("R0"))
    res = b["derived_bounds"]["results"]
    assert res["n_ood_runs_without_rotational_beyond"] == r0
    dmax = max(v["OOD_categories"]["DISSOCIATION_ONLY"] for v in ood["breakdown"]["candidate"].values())
    assert res["upper_bound_r0_ood_runs_per_candidate"] == dmax + (r0 - pats["D1 E0 V0 R0"])
    inc = ood["breakdown"]["official_member_verdict_vs_OOD_count"]["INCONCLUSIVE"]
    assert res["min_ood_runs_in_any_v1_inconclusive_member"] == min(int(k) for k in inc)
    assert res["no_member_can_reach_PASS_in_minimal_v2_with_rotational_at_45eV"] is \
        (res["upper_bound_r0_ood_runs_per_candidate"] < res["min_ood_runs_in_any_v1_inconclusive_member"])


def test_builder_reproduces_committed_json():
    mod = _builder()
    try:
        text = mod.dump(mod.build())
    except mod.InputMissing as exc:
        pytest.skip(f"lane inputs not available, cannot rebuild the brief: {exc}")
    with open(BRIEF_JSON, encoding="utf-8") as fh:
        assert fh.read() == text
