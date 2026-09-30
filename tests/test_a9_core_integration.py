"""A9_INT core integration (fo_a9_int_core_integration): mechanical integration of A9-01..A9-05.

Machine-checks the no-change statement independently of the builder: every numeric / bool / null leaf of every A9 JSON
deliverable is equal at the base commit (read with ``git show``) and after this lane, except inside the only added key
(A9-04 /dq_id_mapping, which carries no number). Also checks the id mapping, the declared resolutions, every A9 builder
``--check`` and that no historical / immutable file changed.

A9-10 (fo_a9_10_integration) froze this record as the step-1 snapshot: the "after" state is the snapshot commit (the
A9-10 base, read with ``git show``); A9-10's own changes are machine-checked by tests/test_a9_10_reconciliation.py.
"""
import copy
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "docs" / "experiments" / "hall_icp" / "integration" / "build_a9_core_integration.py"
OUT_JSON = ROOT / "docs" / "experiments" / "hall_icp" / "integration" / "a9_core_integration_v1.json"
OUT_MD = ROOT / "docs" / "experiments" / "hall_icp" / "integration" / "A9_CORE_INTEGRATION.md"
BASE = "88e4d478b81b25f0b4fd7de32aa5f76f0726c361"
SNAPSHOT = "ecdad06e30bc5d2f172e862e4bd4843e86332d42"   # A9-10 base: the frozen step-1 "after" state

A9_JSON = [
    "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json",
    "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
    "schemas/interfaces/bus_power_boundary_a9_v1.json",
    "schemas/interfaces/icp_neutralizer_icd_v1.json",
    "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json",
    "docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json",
    "docs/evidence/icp_neutralizer/takahashi2024_fig_pixels_v1.json",
    "docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json",
]
A9_04 = "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json"
A9_01 = "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json"
A9_BUILDERS = [
    "docs/experiments/hall_icp/prereg_framework/build_hall_icp_prereg_framework.py",
    "docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py",
    "docs/interfaces/icp_neutralizer/build_icp_neutralizer_icd.py",
    "docs/experiments/hall_icp/uncertainty_budget/build_hall_icp_uncertainty_budget.py",
    "docs/evidence/icp_neutralizer/build_icp_neutralizer_evidence.py",
    "docs/experiments/hall_icp/validation_inputs/build_hall_icp_validation_inputs.py",
    "docs/experiments/hall_icp/integration/build_a9_core_integration.py",
]
EXPECTED_MAPPING = {"UB-DQ-T": "DQ-HI-TABS", "UB-DQ-PBUS": "DQ-HI-PBUS", "UB-DQ-ETAU": "DQ-HI-ETAU",
                    "UB-DQ-RF": None, "UB-DQ-NEUT": None, "UB-DQ-ID": None, "UB-DQ-FLOW": None, "UB-DQ-PB": None,
                    "UB-DQ-BZ": None, "UB-DQ-TEMP": None}


def _git_show(rel, commit=BASE):
    r = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=ROOT, capture_output=True)
    assert r.returncode == 0, f"commit {commit} not available: {r.stderr!r}"
    return r.stdout


def _snap(rel):
    return json.loads(_git_show(rel, SNAPSHOT).decode("utf-8"))


def _load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _numeric_leaves(o, p=""):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(_numeric_leaves(v, p + "/" + k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out.update(_numeric_leaves(v, p + f"[{i}]"))
    elif o is None or isinstance(o, (bool, int, float)):
        out[p] = (type(o).__name__, o)
    return out


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("build_a9_core_integration", BUILDER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def built(mod):
    return mod.build()


@pytest.fixture(scope="module")
def doc():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


def test_builder_reproduces_outputs_and_all_checks_pass(mod, built):
    d, errors = built
    assert errors == []
    assert OUT_JSON.read_text(encoding="utf-8") == mod.dumps(d)
    assert OUT_MD.read_text(encoding="utf-8") == mod.render_md(d)


@pytest.mark.parametrize("rel", A9_JSON)
def test_numeric_leaves_unchanged_against_base(rel):
    """Independent no-change check: every numeric / bool / null leaf equal before (git show BASE) and after (the
    frozen step-1 snapshot)."""
    before = _numeric_leaves(json.loads(_git_show(rel).decode("utf-8")))
    after_doc = _snap(rel)
    after = _numeric_leaves(after_doc)
    if rel == A9_04:
        added = {p: v for p, v in after.items() if p.startswith("/dq_id_mapping")}
        assert all(v == ("NoneType", None) for v in added.values()), "the added mapping must carry no number"
        after = {p: v for p, v in after.items() if not p.startswith("/dq_id_mapping")}
    assert before == after


def test_negative_controls_detect_undeclared_changes(mod):
    rel = A9_04
    base = json.loads(_git_show(rel).decode("utf-8"))
    cur = _snap(rel)
    # a changed number is caught
    bad = copy.deepcopy(cur)
    bad["items"][1]["value"] = 2.0  # UB-T-01 owner value 1.0 (row 121)
    errs = []
    mod.compare_deliverable("A9-04", rel, errs, before=base, after=bad)
    assert any("numeric leaf changed" in e for e in errs)
    # an undeclared text change is caught
    bad = copy.deepcopy(cur)
    bad["items"][0]["name"] = bad["items"][0]["name"] + " (edited)"
    errs = []
    mod.compare_deliverable("A9-04", rel, errs, before=base, after=bad)
    assert any("not explained" in e for e in errs)
    # a removed list element is caught
    bad = copy.deepcopy(cur)
    bad["items"].pop()
    errs = []
    mod.compare_deliverable("A9-04", rel, errs, before=base, after=bad)
    assert errs
    # the real state passes
    errs = []
    mod.compare_deliverable("A9-04", rel, errs, before=base, after=cur)
    assert errs == []


def test_id_mapping(doc):
    a904 = _snap(A9_04)
    rows = a904["dq_id_mapping"]["rows"]
    assert {r["ub_dq_id"]: r["dq_hi_id"] for r in rows} == EXPECTED_MAPPING
    for r in rows:
        assert r["status"] == ("MAPPED" if r["dq_hi_id"] else "UNMAPPED - owner/A9-10")
    mirrored = [{k: v for k, v in r.items() if k not in ("a9_01_role", "a9_01_units")}
                for r in doc["dq_id_mapping"]["rows"]]
    assert mirrored == rows
    dq01 = {q["id"]: q for q in _snap(A9_01)["decision_quantities"]}
    for ub, dq in EXPECTED_MAPPING.items():
        if dq:
            assert dq in dq01
    ids_after = [q["id"] for q in a904["decision_quantities"]]
    ids_base = [q["id"] for q in json.loads(_git_show(A9_04).decode("utf-8"))["decision_quantities"]]
    assert ids_after == [EXPECTED_MAPPING[i] or i for i in ids_base]


def test_no_mapped_provisional_id_left(doc):
    for rel in A9_JSON:
        d = _load(rel)
        if rel == A9_04:
            d = {k: v for k, v in d.items() if k != "dq_id_mapping"}
        txt = json.dumps(d, ensure_ascii=False)
        for old in ("UB-DQ-T", "UB-DQ-PBUS", "UB-DQ-ETAU"):
            assert not re.search(re.escape(old) + r"(?![A-Za-z0-9])", txt), (rel, old)


def test_resolved_and_remaining_references(doc):
    res, rem = doc["resolved_references"], doc["remaining_references"]
    assert len(res) == doc["counts"]["resolved_references"] > 0
    for x in res:
        assert "PENDING" in x["old"] or "not in the base" in x["old"]
        assert "PENDING" not in x["new"]
        assert x["targets"] and all((ROOT / t["path"]).is_file() for t in x["targets"])
    assert all(x["reason"] in doc["reason_codes"] for x in rem)
    assert sum(doc["counts"]["remaining_by_reason"].values()) == len(rem)
    # every PENDING occurrence still in the deliverables is listed
    n = 0
    for rel in A9_JSON:
        n += len(re.findall("PENDING", json.dumps(_snap(rel), ensure_ascii=False)))
    assert n == len(rem)


def test_all_a9_builders_check_ok():
    for b in A9_BUILDERS:
        r = subprocess.run([sys.executable, b, "--check"], cwd=ROOT, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (b, r.stdout[-500:], r.stderr[-500:])


def test_historical_and_immutable_files_unchanged(doc):
    assert doc["historical_unchanged"]
    assert all(x["unchanged_since_base"] for x in doc["historical_unchanged"])
    for x in doc["historical_unchanged"]:
        assert (ROOT / x["path"]).read_bytes() == _git_show(x["path"])


def test_post_integration_pins_and_pinned_inputs(doc):
    import hashlib
    for x in doc["post_integration_pins"]:   # frozen step-1 snapshot pins
        assert hashlib.sha256(_git_show(x["path"], SNAPSHOT)).hexdigest() == x["sha256"], x["path"]
    for link in doc["pinned_input_updates"]["links"]:
        assert link["updated"] is False
    for p in doc["authority_pins"]:
        assert hashlib.sha256((ROOT / p["path"]).read_bytes()).hexdigest() == p["sha256"]
        assert "orchestration" not in p["path"]


def test_frozen_snapshot_points_to_a9_10_record(doc):
    assert doc["snapshot_commit"] == SNAPSHOT
    assert "a9_10_reconciliation_v1.json" in doc["a9_10_note"]
    st = {q["id"]: q["status"] for q in doc["open_owner_questions"]}
    assert st["OQ-INT-03"].startswith("ADDRESSED_IN_A9_10") and st["OQ-INT-04"].startswith("ADDRESSED_IN_A9_10")
    assert st["OQ-INT-01"].startswith("OPEN - owner call") and st["OQ-INT-02"] == "OPEN"


def test_required_sections(doc):
    for k in ("items", "interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
              "m16_impact", "h3_h4_inputs", "no_change_statement", "dq_id_mapping"):
        assert doc[k], k
    assert doc["no_change_statement"]["machine_checked"] is True
    assert doc["no_change_statement"]["errors"] == []
    md = OUT_MD.read_text(encoding="utf-8")
    for s in ("## (a)", "## (b)", "## (c)", "## (d)", "## (e)", "## (f)", "## (g)"):
        assert s in md
    txt = json.dumps(doc).lower()
    for banned in ("best architecture", "recommended architecture", "sgb-screen", "ensemble_member_id"):
        assert banned not in txt
