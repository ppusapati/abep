"""Checks for the descriptive, NON-GATING scoreable-subset forensics of the P5-N2 v1 vacuum campaign
(scripts/forensics/p5_n2_v1_scoreable_subset.py -> docs/forensics/p5_n2_v1/scoreable_subset/).

The forensics must read official statuses and reasons (never recompute them), reconcile exactly with the official counts
and the official report, be deterministic, and avoid ranking / admission wording. Nothing here re-scores a run.
"""
import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "forensics", "p5_n2_v1_scoreable_subset.py")
VAL = os.path.join(ROOT, "hallthruster_bridge", "validation")
REPORT = os.path.join(VAL, "p5_n2_campaign_v1_vacuum_scores_report.md")
SCORES = os.path.join(VAL, "p5_n2_campaign_v1_vacuum_scores.json")
DECISION = os.path.join(VAL, "p5_n2_campaign_v1_vacuum_scores_decision.json")
OUT = os.path.join(ROOT, "docs", "forensics", "p5_n2_v1", "scoreable_subset")
COLS = ["PASS", "FAIL_VALIDATION", "OUT_OF_DOMAIN", "NUMERICAL_FAILURE", "CURRENT", "THRUST", "SUSTAINMENT"]


def _load_module():
    spec = importlib.util.spec_from_file_location("p5_n2_v1_scoreable_subset", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


@pytest.fixture(scope="module")
def doc(mod):
    return mod.build()


@pytest.fixture(scope="module")
def scores():
    return json.load(open(SCORES))


def _report_table(title):
    """Parse one '| vacuum by <x> | PASS | ... |' table of the official report into {row: {col: int}}."""
    lines = open(REPORT, encoding="utf-8").read().splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith(f"| {title} |"))
    cols = [c.strip() for c in lines[head].strip("|").split("|")][1:]
    out = {}
    for ln in lines[head + 2:]:
        if not ln.startswith("|"):
            break
        cells = [c.strip() for c in ln.strip("|").split("|")]
        out[cells[0]] = {c: int(v) for c, v in zip(cols, cells[1:])}
    return out


def test_totals_reconcile_with_official_counts(doc, scores):
    t = doc["s1_coverage"]["totals"]
    assert (t["PASS"], t["FAIL_VALIDATION"], t["OUT_OF_DOMAIN"], t["NUMERICAL_FAILURE"]) == (32, 700, 1428, 0)
    assert (t["CURRENT"], t["THRUST"], t["SUSTAINMENT"]) == (552, 308, 260)
    assert t["n"] == 2160 and t["scoreable"] == 732
    official = scores["status_counts"]["vacuum"]
    for s in ("PASS", "FAIL_VALIDATION", "OUT_OF_DOMAIN"):
        assert t[s] == official[s]
    rec = doc["totals_reconciliation"]
    assert all(v["this_analysis"] == v["official_scores_file"] for v in rec["status_run_readings"].values())
    assert rec["runs"] == 1080 and rec["scoreable_runs"] == 366


def test_per_candidate_chemistry_point_counts_equal_official_report(doc):
    s1 = doc["s1_coverage"]
    for title, ours in (("vacuum by candidate", s1["by_candidate"]), ("vacuum by chemistry", s1["by_chemistry"]),
                        ("vacuum by point", s1["by_point"])):
        rep = _report_table(title)
        assert set(rep) == set(ours), title
        for row, vals in rep.items():
            assert {c: ours[row][c] for c in COLS} == {c: vals[c] for c in COLS}, (title, row)


def test_statuses_and_reasons_are_the_official_ones(mod, doc, scores):
    """Every grid code equals the code of the official status/reasons; nothing is re-labelled."""
    grid = doc["s1_coverage"]["grid"]
    seen = 0
    for r in scores["runs"]:
        k = mod.parse_key(r["key"])
        member = f"{k['registration']}|{k['coil']}|{r['reading']}"
        got = grid[k["candidate"]][member][k["chemistry"]][mod.POINTS.index(k["point"])]
        if r["status"] == "PASS":
            want = "P"
        elif r["status"] == "FAIL_VALIDATION":
            want = "".join(mod.REASON_CODE[q] for q in mod.REASONS if q in r["reasons"])
        elif r["status"] == "OUT_OF_DOMAIN":
            want = "·"
        else:
            want = "X"
        assert got == want, r["key"]
        seen += 1
    assert seen == 2160


def test_member_and_candidate_verdicts_copied_and_consistent(doc, scores):
    vac = scores["candidates"]["vacuum"]
    decision = json.load(open(DECISION))
    assert doc["official_outcome_unchanged"]["candidate_verdicts"] == decision["candidates"]
    assert all(v == "INCONCLUSIVE / NOT ELIGIBLE" for v in decision["candidates"].values())
    s4 = doc["s4_member_coverage"]
    for c, members in s4["members"].items():
        for m, v in members.items():
            assert v["official_member_verdict"] == vac[c]["members"][m]
            assert v["n_scoreable"] == v["n_pass"] + v["n_fail_validation"]
            # tabulation consistency with O3 (not a re-derivation of any verdict)
            if v["n_fail_validation"]:
                assert v["official_member_verdict"] == "FAIL"
            elif v["n_pass"] < 20:
                assert v["official_member_verdict"] == "INCONCLUSIVE"
    assert not any(v["n_pass"] == 20 for ms in s4["members"].values() for v in ms.values())


def test_coverage_label_and_scope_statements(mod, doc):
    md = open(os.path.join(OUT, "SCOREABLE_SUBSET.md"), encoding="utf-8").read()
    label = "coverage description, not a verdict, not a promotion; the official verdicts are final"
    assert doc["s4_member_coverage"]["label"] == label == mod.COVERAGE_LABEL
    assert label in md
    assert "INCONCLUSIVE / NOT ELIGIBLE" in md and "non-gating" in md
    assert "n = 9" in doc["s3_transport_parameter_relations"]["caveat"]
    assert "not a fit" in doc["s3_transport_parameter_relations"]["caveat"]


def test_forbidden_wording_absent(mod):
    label = mod.COVERAGE_LABEL
    for name in ("SCOREABLE_SUBSET.md", "scoreable_subset.json"):
        text = open(os.path.join(OUT, name), encoding="utf-8").read()
        for pat in (r"\bbest\b", r"recommended candidate", r"\bpromising\b", r"\bpromote[sd]?\b", r"would pass if",
                    r"\bwinner\b", r"\bPROMOTABLE\b"):
            assert not re.search(pat, text, flags=re.IGNORECASE), (name, pat)
        # the word 'promotion' appears only inside the mandated coverage label
        assert text.lower().count("promotion") == text.count(label)


def test_sustainment_section_reconciles(doc):
    s5 = doc["s5_sustainment_collapse"]
    assert s5["n_runs"] == 130 and s5["n_run_readings"] == 260 == doc["s1_coverage"]["totals"]["SUSTAINMENT"]
    assert sum(v["sustainment"] for v in s5["by_candidate"].values()) == 130
    assert sum(v["scoreable"] for v in s5["by_candidate"].values()) == 366
    assert s5["Id_statistics"]["collapsed"]["dI_rel"]["n"] == 130


def test_sign_pattern_counts_are_run_level_and_complete(doc):
    sp = doc["s2_residuals"]["sign_patterns"]
    n_cur_runs = sum(v["over"] + v["under"] for v in sp["current_failures_by_point"].values())
    assert 2 * n_cur_runs == doc["s1_coverage"]["totals"]["CURRENT"]          # CURRENT is reading-independent
    thr = sp["thrust_failures_run_readings"]
    assert sum(thr[rd]["total"]["over"] + thr[rd]["total"]["under"] for rd in ("A", "B")) == \
        doc["s1_coverage"]["totals"]["THRUST"]


def test_spearman_helper(mod):
    assert mod.spearman([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])["rho"] == 1.0
    assert mod.spearman([1, 2, 3, 4, 5], [5, 4, 3, 2, 1])["rho"] == -1.0
    assert mod.spearman([1, 1, 1, 1, 1], [1, 2, 3, 4, 5])["rho"] is None          # constant x
    assert mod.spearman([1, 2, 3, 4], [1, 2, 3, 4])["rho"] is None                # n < 5
    assert mod.avg_ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]


def test_json_and_markdown_deterministic_and_committed(mod, doc):
    js1, md1 = mod.dumps(doc), mod.render(doc)
    doc2 = mod.build()
    assert mod.dumps(doc2) == js1 and mod.render(doc2) == md1
    assert open(os.path.join(OUT, "scoreable_subset.json"), encoding="utf-8").read() == js1
    assert open(os.path.join(OUT, "SCOREABLE_SUBSET.md"), encoding="utf-8").read() == md1
