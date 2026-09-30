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
    "schemas/architecture_comparison/bus_power_boundary_v1.json",
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
    for p in (BUILDER, OVERLAY, ROOT / "docs/budgets/subsystem_maturity/build_subsystem_maturity_v3.py",
              ROOT / "docs/budgets/owner_decisions/build_owner_questions_state_v2.py"):
        assert "xe" + "_ledger" not in p.read_text(encoding="utf-8"), p.name
    assert not re.search(r"^import (?!json|os|re|sys|copy|hashlib|argparse|subprocess|importlib|csv|io)",
                         BUILDER.read_text(encoding="utf-8"), re.M)


# ------------------------------------------------------------------------------------------------ review repair
def test_no_catch_all_pending_rule():
    """OQ-INT-03: no regex catch-all may label a remaining 'PENDING <A9 lane>' as not defined by its target."""
    b = _mod(BUILDER, "a9_10_builder_under_test")
    assert "TARGET_MERGED_DOES_NOT_DEFINE" not in b.REASONS
    for dk, pk, tk, _reason in b.PENDING_RULES:
        if tk in (r".*", r"^PENDING"):       # a text catch-all is allowed only for one deliverable AND one pointer family
            assert dk != r".*" and pk != r".*", (dk, pk)
        assert "power_boundary_a9" not in tk and "A9-0[1-9]" not in tk, tk


def test_targets_that_supply_the_value_are_used(doc):
    """The reviewer's counter-examples: where the merged target (or A9.1) supplies the value, the source deliverable
    now says so (filled / SATISFIED / PARTIAL with the locator), never 'target does not define'."""
    icd = json.loads((ROOT / "schemas/interfaces/icp_neutralizer_icd_v1.json").read_text(encoding="utf-8"))
    dem = {d["id"]: d for d in icd["interface_demands"]}
    assert dem["ID-02"]["status"].startswith("SATISFIED") and "A9-03-Vd" in dem["ID-02"]["status"]
    assert dem["ID-04"]["status"].startswith("SATISFIED") and "stage_map" in dem["ID-04"]["status"]
    assert dem["ID-07"]["status"].startswith("PARTIAL") and "efficiencies" in dem["ID-07"]["status"]
    items = {x["id"]: x for x in icd["items"]}
    assert "icp_rf_source" in items["ICP-24"]["tbd"] and "OQ-A902-03" in items["ICP-24"]["requirement"]
    pre = json.loads((ROOT / "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json")
                     .read_text(encoding="utf-8"))
    pd = {d["id"]: d for d in pre["interface_demands"]}
    assert pd["IF-HI-01"]["status"].startswith("SATISFIED") and pd["IF-HI-02"]["status"].startswith("SATISFIED")
    ub = json.loads((ROOT / "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json")
                    .read_text(encoding="utf-8"))
    ui = {x["id"]: x for x in ub["items"]}
    assert "icp_rf_source" in ui["UB-P-01"]["value"] and "PENDING" not in ui["UB-P-01"]["value"]
    # A9.2 OQ-A907-11 supersedes the A9.1 reference plane for the baseline; the A9.1 value is kept as history
    assert "AFTER the matching network" in ui["UB-RF-09"]["value_before_a9_2"]
    assert "generator / 50-ohm side" in ui["UB-RF-09"]["value"] and ui["UB-RF-09"]["a9_1_decision"] == "A9-03-matching"
    assert "floating" in ui["UB-N-00"]["value"] and "PENDING" not in ui["UB-N-00"]["value"]
    assert ui["UB-P-07"]["value"]["window_s"] == 1.0e-3 and ui["UB-P-07"]["a9_1_decision"] == "OQ-A902-01"
    bpb = json.loads((ROOT / "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json")
                     .read_text(encoding="utf-8"))
    assert bpb["interface_demands"][1]["status"].startswith("SATISFIED")
    m = doc["interface_demand_matrix"]
    cls = {(r["lane"], r["id"]): r["class"] for r in m["rows"]}
    assert cls[("A9-03", "ID-02")] == "SATISFIED" and cls[("A9-01", "IF-HI-01")] == "SATISFIED"
    for r in m["rows"]:
        if r["class"] in ("OPEN", "PARTIAL"):
            assert "does not define this value" not in (r["open_reason"] or "")
            assert not re.fullmatch(r"(PENDING|OPEN)( .{0,25})?", r["open_reason"] or ""), (r["lane"], r["id"])


def test_m16_v3_location_declared_and_h2_7_scan_unchanged(doc):
    """The M16 v3 JSON is not placed in docs/budgets/subsystem_maturity/ (the immutable H2-7 v1 builder globs *.json
    there and pins each file); the deviation is declared (SD-A910-01, OQ-A910-04)."""
    base = sorted(x for x in _git("ls-tree", "--name-only", BASE, "docs/budgets/subsystem_maturity/").decode()
                  .splitlines() if x.endswith(".json"))
    now = sorted("docs/budgets/subsystem_maturity/" + p.name
                 for p in (ROOT / "docs/budgets/subsystem_maturity").glob("*.json"))
    assert now == base
    sd = {x["id"]: x for x in doc["scope_deviations"]}["SD-A910-01"]
    assert sd["within_allowed_paths"] and (ROOT / sd["actual_path"]).is_file()
    assert any(q["id"] == "OQ-A910-04" for q in doc["new_open_questions"])


# ------------------------------------------------------------------------------------------------------ A9.2
A92_STATUSES = {
    "Hall->ICP architecture": "INVESTIGATION_HYPOTHESIS",
    "ICP electron-current capacity": "PENDING_ICP45",
    "ICP RF power closure": "PENDING_HARDWARE",
    "RF matching architecture": "LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT",
    "RF component ratings": "TBD_AFTER_IMPEDANCE_MAP",
    "316L flight anode": "REJECTED_AS_CURRENT_BASELINE",
    "final anode material": "OPEN",
    "anode thermal closure": "UNRESOLVED",
    "coupled H-1/ICP thermal closure": "UNRESOLVED",
    "C1 conventional reference": "CONTROL_FALLBACK",
}
A92_COPY = LANE / "a9_2_inputs" / "OD_2026_09_30_A9_2_a907_followup_owner_decisions.json"
A92_MD_COPY = LANE / "a9_2_inputs" / "OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md"


def test_a9_2_pinned_copies_and_originals():
    import hashlib
    for p, sha, orig in ((A92_COPY, "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03",
                          "docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json"),
                         (A92_MD_COPY, "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9",
                          "docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md")):
        assert hashlib.sha256(p.read_bytes()).hexdigest() == sha
        if (ROOT / orig).is_file():                                     # present after the orchestrator merge
            assert (ROOT / orig).read_bytes() == p.read_bytes()


def test_a9_2_status_literals_exact(doc):
    """A9.2 item 9: each status literal exactly as given, in the JSON and in the Markdown."""
    got = {x["item"]: x["status"] for x in doc["a9_2"]["statuses"]}
    assert got == A92_STATUSES
    dec = json.loads(A92_COPY.read_text(encoding="utf-8"))["decisions"]["a9_10_statuses"]
    assert dec == A92_STATUSES
    md = OUT_MD.read_text(encoding="utf-8")
    for k, v in A92_STATUSES.items():
        assert f"| {k} | **{v}** |" in md, k
    assert doc["a9_status"] == "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE"


PASS_RX = re.compile(r"^(PASS|CLOSES\w*|CLOSED|RESOLVED|CONDITIONALLY_RESOLVED)\b")
STATUS_KEY_RX = re.compile(r"(^|_)(status|verdict|state|outcome|necessary_check|brief_verdict_at_baseline)$")
TOPIC_RX = re.compile(r"ICP-45|electron-current capa|P_ICP,available|ICP RF power|matching network|local match|"
                      r"TBD_AFTER_IMPEDANCE_MAP|component rating|316L|anode (worst|thermal|temperature|material)|"
                      r"coupled|ICP_COUPLED_THERMAL")


def _walk(o, p=""):
    if isinstance(o, dict):
        yield p, o
        for k, v in o.items():
            yield from _walk(v, p + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, p + f"[{i}]")


def test_a9_2_no_status_claims_pass_for_the_a9_2_items(doc):
    """Independent re-scan (not the builder's): no status-like field in any A9 deliverable, M16 v3 or the owner-question
    state claims PASS / CLOSES / RESOLVED for the A9.2 items; the hall_icp_neutralizer thermal rerun reports no pass at
    all; the scan is proven sensitive on the A9-10 base version of A9-07."""
    files = [c["file"] for c in doc["changes_by_deliverable"]] + [
        "docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json"]

    def scan(rel, d):
        bad = []
        for path, node in _walk(d):
            if path.startswith("/a9_10_reconciliation") or "before_a9_2" in path:
                continue
            for k, v in node.items():
                if not STATUS_KEY_RX.search(k) or "sensitivity" in k or "before_a9_2" in k:
                    continue
                for x in (v if isinstance(v, list) else [v]):
                    if not (isinstance(x, str) and PASS_RX.match(x)):
                        continue
                    thermal = "/recomputations/h25_thermal_rerun" in path and "hall_c1_reference" not in path
                    if thermal or TOPIC_RX.search(json.dumps(node, ensure_ascii=False)):
                        bad.append((rel, path, k, x))
        return bad
    bad = []
    for rel in files:
        bad += scan(rel, json.loads((ROOT / rel).read_text(encoding="utf-8")))
    assert bad == [], bad[:5]
    base = json.loads(_git("show", f"{BASE}:docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json"))
    assert len(scan("A9-07@base", base)) > 100            # the scan would catch the pre-A9.2 CLOSES verdicts
    assert doc["a9_2"]["status_scan"]["violations"] == []
    h2 = json.loads((ROOT / "docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json").read_text(encoding="utf-8"))
    assert h2["recomputations"]["h25_thermal_rerun"]["overall"]["status"] == "UNRESOLVED"


def test_a9_2_supersession_blockers_and_next_lanes(doc):
    g = doc["a9_2"]
    assert "LOCAL matching network" in g["supersession"]["by"] and "A9.1 A9-03-matching" in g["supersession"]["superseded"]
    assert g["anode"]["ANODE_BASELINE"] == "OPEN" and g["anode"]["no_rfq_implied"] is True
    assert [b["id"] for b in g["anode"]["design_blockers"]] == ["A9H-ANODE-01", "A9H-ANODE-02"]
    assert g["coupled_thermal"]["ICP_COUPLED_THERMAL"] == "UNRESOLVED"
    assert g["coupled_thermal"]["pole_allowance_warning"]["value_W"] == 13.0
    assert [x["id"] for x in g["recommended_next_lanes_not_launched"]] == ["P1", "P2", "P3", "P4"]
    cov = {c["decision"]: c for c in g["decision_coverage"]}
    for k in ("OQ-A907-11", "rf_measurement_reference", "rf_500W", "rf_protection", "icp_matching_strategy",
              "anode_316L", "anode_approach", "icp_coupled_thermal", "radiative_view_requirement",
              "13W_pole_allowance", "coil_mass_correction", "a9_10_statuses"):
        assert cov[k]["applied_by"], k
    assert "DRAFT" in g["pr_33"]
    icd = json.loads((ROOT / "schemas/interfaces/icp_neutralizer_icd_v1.json").read_text(encoding="utf-8"))
    it = {x["id"]: x for x in icd["items"]}
    assert "open-frame ICP support" in it["ICP-47"]["requirement"] and it["ICP-47"]["group"] == "mechanical"
    assert it["ICP-13"]["status"].startswith("OWNER_GIVEN (A9.2 OQ-A907-11: LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT")
    assert "off the moving thrust-stand platform" in it["ICP-13"]["value_before_a9_2"]
    assert it["ICP-15"]["tbd"].startswith("TBD - requires the ICP antenna impedance map")
    mass = json.loads((ROOT / "docs/budgets/mass_a9/mass_a9_v1.json").read_text(encoding="utf-8"))
    b = {x["id"]: x for x in mass["a9_flight_bom"]["flight"]}
    assert b["A9B-20"]["value"] is None and "ICP module" in b["A9B-20"]["name"]
    assert "NOT the MC-1 coil mass" in mass["lv_coil_sensitivity"]["a9_2_coil_mass_correction"]
    assert b["A9B-16"]["value"] == 3.504                                   # closure mass unchanged


def test_a9_2_residual_wording_scan_is_clean_and_sensitive(doc):
    """Review repair 3: the builder's text scan (pass-like values under any key, PASS / CLOSES sentences without an
    uncoupled-sensitivity label, 500 W texts without the delivered/operating label) finds nothing now, and finds the
    residual wording in the A9-10 base versions (sensitivity proof). Only the rules are taken from the builder."""
    b = _mod(BUILDER, "a9_10_builder_text_scan")
    assert doc["a9_2"]["text_scan"]["violations"] == []
    assert {x["id"]: x for x in doc["items"]}["REC-12"]["value"] == 0
    errs = []
    now = b.a92_text_scan(errs)
    assert now["violations"] == [] and errs == []
    h2 = json.loads(_git("show", f"{BASE}:docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json"))
    h2_md = _git("show", f"{BASE}:docs/hardware/h2_a9_revisions/H2_A9_REVISIONS.md").decode("utf-8")
    files = ["docs/procurement/rfq_a9/rfq_a9_v1.json", "schemas/interfaces/icp_neutralizer_icd_v1.json",
             "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json"]
    w_docs = {f: json.loads(_git("show", f"{BASE}:{f}")) for f in files}
    pk = "docs/procurement/rfq_a9/packages/RFQ-04_rf_chain.md"
    w_mds = {pk: _git("show", f"{BASE}:{pk}").decode("utf-8")}
    old = b.a92_text_scan([], h2=h2, h2_md=h2_md, w500_docs=w_docs, w500_mds=w_mds)
    assert old["value_violations"] and old["wording_violations"] and old["w500_violations"]
    assert any("Curie" in v["sentence"] for v in old["wording_violations"])
    assert any("/revision_register" in v["pointer"] for v in old["value_violations"])
    assert any("0-500 W forward" in v["text"] for v in old["w500_violations"])


PRE_REPAIR4 = "3a5b75c"   # A9-10 review repair 3 (the version the repair-4 reviewers read)


def test_a9_2_text_scan_covers_every_deliverable_and_is_sensitive(doc):
    """Review repair 4: the 500 W rule is checked 'anywhere' (every A9 deliverable JSON and Markdown, M16 v3, the
    owner-question state v2, the step-1 integration record, the RFQ packages) and the scan is proven sensitive on the
    repair-3 versions of the files the reviewers named (A9-01 H3 input, A9-02 H3-A902-01, A9-05 VI-RF-02 / H3 inputs,
    A9-05 evidence, A9-07 K11 / A9H-INS-01 / REV-35) and of the K2 / K6 CLOSES / PASS wording."""
    b = _mod(BUILDER, "a9_10_builder_text_scan_4")
    ts = doc["a9_2"]["text_scan"]
    for d in b.DELIVERABLES:
        assert d["json"] in ts["w500_files"] and d["md"] in ts["w500_md_files"], d["key"]
    for rel in (b.M16_V3, b.OQ_V2, b.INTEGRATION["json"]):
        assert rel in ts["w500_files"]
    assert "docs/procurement/rfq_a9/packages/RFQ-04_rf_chain.md" in ts["w500_md_files"]
    assert ts["violations"] == []
    named = ["docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json",
             "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
             "docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json",
             "docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json",
             "docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json"]
    old_docs = {f: json.loads(_git("show", f"{PRE_REPAIR4}:{f}")) for f in named}
    h2_old = old_docs[named[-1]]
    h2_md_old = _git("show", f"{PRE_REPAIR4}:docs/hardware/h2_a9_revisions/H2_A9_REVISIONS.md").decode("utf-8")
    old = b.a92_text_scan([], h2=h2_old, h2_md=h2_md_old, w500_docs=old_docs, w500_mds={})
    hit = {(v["file"], v["pointer"]) for v in old["w500_violations"]}
    for f, ptr in [(named[0], "/h3_h4_inputs/h3_procurement_inputs_quotations_only[0]"),
                   (named[1], "/h3_inputs[0]/item"), (named[2], "/items[1]/value"),
                   (named[2], "/h3_h4_inputs/h3_procurement_rfq_inputs[0]"),
                   (named[3], "/h3_h4_inputs/h3_procurement_rfq[0]"), (named[4], "/key_findings[10]"),
                   (named[4], "/new_items[0]/name"), (named[4], "/revision_register[34]/new/requirement")]:
        assert (f, ptr) in hit, (f, ptr)
    ptrs = {v["pointer"] for v in old["wording_violations"]}
    assert {"/key_findings[1]", "/key_findings[5]"} <= ptrs          # K2 'WO CLOSES', K6 'PO PASS, BP PASS'
    assert any("uncoupled_sensitivity" in v["pointer"] for v in old["value_violations"])


def test_bus_power_boundary_v1_schema_is_protected(doc):
    rows = {x["path"]: x for x in doc["immutability"]}
    x = rows["schemas/architecture_comparison/bus_power_boundary_v1.json"]
    assert x["byte_identical_to_base"] is True


def test_a9_2_decision_path_resolution_declared(doc):
    dec = doc["a9_2"]["decision"]
    assert "pinned copies" in dec["path_resolution"] and dec["pinned_copy"].startswith(
        "docs/experiments/hall_icp/integration/a9_2_inputs/")
