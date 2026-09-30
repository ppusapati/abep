"""A9-10 reconciliation (fo_a9_10_integration): record, overlay and immutability checks.

Independent of the builder where it matters: the immutability test re-reads every protected file at the A9-10 base
with ``git show`` and compares bytes; the numeric-change test recomputes, leaf by leaf, which numbers changed in each
A9 deliverable and requires every one to sit under a declared numeric change. Run:
    python -m pytest -q tests/test_a9_10_reconciliation.py
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
LANE = ROOT / "docs" / "experiments" / "hall_icp" / "integration"
BUILDER = LANE / "build_a9_10_reconciliation.py"
OVERLAY = LANE / "a9_10_overlay.py"
OUT_JSON = LANE / "a9_10_reconciliation_v1.json"
OUT_MD = LANE / "A9_10_RECONCILIATION.md"
BASE = "ecdad06e30bc5d2f172e862e4bd4843e86332d42"
A91 = ROOT / "docs" / "decisions" / "OD_2026_09_30_A9_1_followup_owner_decisions.json"
PROTECTED = [
    "docs/decisions", "docs/hardware/h2", "docs/budgets/" + "xe" + "_ledger", "docs/architecture_comparison/mass_bom",
    "docs/budgets/subsystem_maturity/subsystem_maturity_v1.json", "docs/budgets/subsystem_maturity/SUBSYSTEM_MATURITY.md",
    "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json",
    "docs/budgets/subsystem_maturity/SUBSYSTEM_MATURITY_v2.md",
    "docs/budgets/owner_decisions/OWNER_QUESTIONS_CONSOLIDATED.md",
    "docs/budgets/owner_decisions/owner_questions_consolidated.csv",
    "docs/budgets/owner_decisions/owner_questions_consolidated.xlsx",
    "docs/interfaces/preionizer_module", "schemas/interfaces/preionizer_module_icd_v1.json",
    "docs/experiments/phase1_prereg_framework", "docs/architecture_comparison/lock1", "abep_sim/arch_boundary.py",
]


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def ov():
    return _mod(OVERLAY, "a9_10_overlay_under_test")


@pytest.fixture(scope="module")
def doc():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


def _git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _leaves(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _leaves(v, p + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _leaves(v, p + f"[{i}]")
    else:
        yield p, o


def test_builder_check_passes():
    r = subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=ROOT, capture_output=True, text=True,
                       timeout=300)
    assert r.returncode == 0, (r.stdout[-2000:], r.stderr[-2000:])


def test_record_has_no_errors_and_required_sections(doc):
    assert doc["errors"] == []
    for k in ("items", "interface_demands", "owner_answers_applied", "new_open_questions", "historical_reuse",
              "m16_impact", "h3_h4_inputs", "changes_by_deliverable", "a9_1_decision_coverage",
              "pending_reevaluation", "dq_consumer_table", "annex_reconciliation", "interface_demand_matrix",
              "immutability", "cross_lane_reconciliation"):
        assert doc[k], k
    md = OUT_MD.read_text(encoding="utf-8")
    for h in ("## (a)", "## (b)", "## (c)", "## (d)", "## (e)", "## (f)", "## (g)"):
        assert h in md
    assert doc["a9_status"] == "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE"


def test_immutable_files_byte_identical_to_base():
    """Independent immutability check (every docs/decisions/** file, H2 v1, Xe ledger v1, mass BOM v1, M16 v1/v2, the
    v1 consolidated owner list, the historical pre-ionizer ICD / Phase-1 framework / LOCK-1 files, arch_boundary.py)."""
    n = 0
    for root in PROTECTED:
        files = [x for x in _git("ls-tree", "-r", "--name-only", BASE, "--", root).decode().splitlines() if x]
        assert files, root
        for rel in files:
            assert (ROOT / rel).read_bytes() == _git("show", f"{BASE}:{rel}"), rel
            n += 1
    assert n >= 50


def test_every_deliverable_carries_exactly_the_declared_changes(ov, doc):
    recs = ov.records()
    for x in doc["changes_by_deliverable"]:
        d = json.loads((ROOT / x["file"]).read_text(encoding="utf-8"))
        sec = d["a9_10_reconciliation"]
        assert [c["cid"] for c in sec["changes"]] == [r["cid"] for r in recs[x["deliverable"]]]
        assert sec["a9_1_decision"]["sha256"] == ov.A91_SHA
        assert x["unexplained"] == 0 and x["numeric_unexplained"] == 0
        for r in recs[x["deliverable"]]:
            assert r["driver"] and r["summary"], r["cid"]


def test_changed_numbers_only_under_numeric_records(ov, doc):
    """Independent recomputation: every changed / added number in every A9 JSON deliverable lies under a declared
    change flagged numeric (A9.1 decision or verified upstream value) or inside the A9-10 section itself."""
    recs = ov.records()
    for x in doc["changes_by_deliverable"]:
        after = json.loads((ROOT / x["file"]).read_text(encoding="utf-8"))
        before = json.loads(_git("show", f"{BASE}:{x['file']}").decode("utf-8"))
        lb, la = dict(_leaves(before)), dict(_leaves(after))
        prefixes = ["/a9_10_reconciliation"]
        for r in recs[x["deliverable"]]:
            if not r.get("numeric"):
                continue
            if r["op"] == "code":
                prefixes += r["scope"]
            else:
                prefixes += [p for p, _par, _k in ov.resolve(after, r["ptr"])]
        for p in set(lb) | set(la):
            vb, va = lb.get(p), la.get(p)
            num = any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (vb, va))
            if not num or (vb == va and type(vb) is type(va)):
                continue
            assert any(p == q or p.startswith(q + "/") or p.startswith(q + "[") for q in prefixes), (x["file"], p)


def test_every_a91_decision_is_applied_or_recorded(doc):
    a91 = json.loads(A91.read_text(encoding="utf-8"))["decisions"]
    cov = {c["decision"]: c for c in doc["a9_1_decision_coverage"]}
    assert set(cov) == set(a91)
    for k, c in cov.items():
        if not k.endswith("_accounting"):
            assert c["applied_by"], k


def test_overlay_refuses_a_mismatch(ov):
    """Negative control: an 'old' value that does not match makes the overlay raise (no silent skip)."""
    d = json.loads((ROOT / ov.PRE).read_text(encoding="utf-8"))
    bad = copy.deepcopy(d)
    bad.pop("a9_10_reconciliation")
    with pytest.raises(ov.OverlayError):
        ov.apply("A9-01", bad)          # already-applied values no longer match the declared 'old' values


def test_pending_reevaluated_with_reason(doc):
    p = doc["pending_reevaluation"]
    n = sum(x["pending_now"] for x in p["per_deliverable"])
    assert n == len(p["remaining"]) == sum(p["remaining_by_reason"].values())
    assert all(x["reason"] in p["reason_codes"] for x in p["remaining"])
    assert sum(x["pending_now"] for x in p["per_deliverable"]) < sum(x["pending_at_base"] for x in p["per_deliverable"])


def test_consumer_table_keeps_ids(doc):
    t = doc["dq_consumer_table"]
    assert t["status"].startswith("PROPOSED")
    ids = {r["ub_dq_id"] for r in t["rows"]}
    assert ids == {"UB-DQ-RF", "UB-DQ-NEUT", "UB-DQ-ID", "UB-DQ-FLOW", "UB-DQ-PB", "UB-DQ-BZ", "UB-DQ-TEMP"}
    assert all(q.startswith("DQ-HI-") for r in t["rows"] for q in r["dq_hi_consumers_declared"])


def test_annex_reconciled_and_a905_governs(doc):
    a = doc["annex_reconciliation"]
    assert all(r["governs"] == "A9-05" for r in a["rows"]) and a["differences_found"] >= 1
    icd = json.loads((ROOT / "schemas/interfaces/icp_neutralizer_icd_v1.json").read_text(encoding="utf-8"))
    assert "OQ-INT-04" in icd["published_analog_annex"]["source"]["authority_note"]


def test_interface_matrix_covers_all_lanes(doc):
    m = doc["interface_demand_matrix"]
    lanes = {r["lane"] for r in m["rows"]}
    assert {"A9-01", "A9-02", "A9-03", "A9-04", "A9-05ev", "A9-05vi", "A9-06", "A9-07", "A9-08", "A9-09"} <= lanes
    for r in m["rows"]:
        assert r["class"] in ("SATISFIED", "OFFERED", "PARTIAL", "OPEN", "NOT_APPLICABLE")
        if r["class"] in ("OPEN", "PARTIAL"):
            assert r["open_reason"], (r["lane"], r["id"])


def test_key_a91_applications_in_deliverables():
    import importlib
    B = importlib.import_module("abep_sim.bus_boundary_a9")
    assert B.TRANSIENT_WINDOW["window_s"] == 1.0e-3 and B.GATE_MIN_SAMPLE_RATE_SA_S == 100.0e3
    assert "flow_control_icp_feed" not in B.installed_slots("hall_icp_neutralizer")
    pre = json.loads((ROOT / "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json").read_text())
    st = {q["id"]: q["status"] for q in pre["open_owner_questions"]}
    assert all(v.startswith("ANSWERED_BY_A9_1") for v in st.values())
    assert pre["statistics_a9_1"]["alpha_family_wise"] == 0.05
    ub = json.loads((ROOT / "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json")
                    .read_text())
    assert ub["stop_rules"]["contrast_stop"]["owner_choice"].startswith("SR-C-MARGIN")
    icd = json.loads((ROOT / "schemas/interfaces/icp_neutralizer_icd_v1.json").read_text())
    by = {x["id"]: x for x in icd["items"]}
    assert "ICP-45A" in by["ICP-45"]["entry_condition_a9_1"] and by["ICP-46"]["a9_1_isolation_basis"][
        "design_isolation_basis_V"] == 900.0
    assert "_a9/" in json.dumps(icd["interface_demands"])       # Xe-ledger reference retargeted to the A9 ledger
    mass = json.loads((ROOT / "docs/budgets/mass_a9/mass_a9_v1.json").read_text())
    assert mass["wet_closure"]["residual"]["status"].startswith("IMPORTED once")
    rfq = json.loads((ROOT / "docs/procurement/rfq_a9/rfq_a9_v1.json").read_text())
    q = {x["id"]: x for x in rfq["open_owner_questions"]}["OQ-RFQ-05"]
    assert q["status"] == "ANSWERED_BY_OWNER_ROW_111"


def test_no_winner_no_prediction_no_open_question_answered(doc):
    txt = json.dumps(doc).lower()
    for banned in ("winner:", "best architecture", "recommended architecture", "sgb-screen", "ensemble_member_id",
                   "plasma_devices.py"):
        assert banned not in txt, banned
    for q in doc["new_open_questions"]:
        assert q["proposed_answer"] and q["needed_by"]
        assert "status" not in q or not str(q["status"]).startswith("ANSWERED")


def test_no_xe_ledger_substring_in_new_code():
    for p in (BUILDER, OVERLAY, ROOT / "docs/budgets/subsystem_maturity/v3/build_subsystem_maturity_v3.py",
              ROOT / "docs/budgets/owner_decisions/build_owner_questions_state_v2.py"):
        assert "xe" + "_ledger" not in p.read_text(encoding="utf-8"), p.name
    assert not re.search(r"^import (?!json|os|re|sys|copy|hashlib|argparse|subprocess|importlib|csv|io)",
                         BUILDER.read_text(encoding="utf-8"), re.M)
