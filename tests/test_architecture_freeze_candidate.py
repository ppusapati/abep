"""Tests for the A9.7 F9 architecture freeze candidate (docs/architecture/freeze_candidate/)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "docs" / "architecture" / "freeze_candidate"
BUILDER = LANE / "build_freeze_candidate.py"
JSON_PATH = LANE / "architecture_freeze_candidate_v1.json"
MD_PATH = LANE / "ARCHITECTURE_FREEZE_CANDIDATE.md"


def _load_builder():
    spec = importlib.util.spec_from_file_location("f9_freeze_candidate_builder_under_test", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def b():
    return _load_builder()


@pytest.fixture(scope="module")
def built(b):
    return b.build()


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _j(rel):
    d = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    if d.get("schema") == "f1_intake_synthesis_v1_core":      # F1 compact core view -> deliverable layout
        from abep_sim.design import intake_synthesis as isy
        d = isy.expand_core(d)
    return d


def test_committed_outputs_are_current(b, built):
    assert JSON_PATH.read_text(encoding="utf-8") == b.dumps(built)
    assert MD_PATH.read_text(encoding="utf-8") == b.render_md(built)


def test_architecture_stays_investigation_hypothesis(doc, b):
    assert doc["architecture_status"] == "INVESTIGATION_HYPOTHESIS"
    assert doc["frozen_reference_flight_architecture"] is False
    assert all(g["evidence_sufficient_for_freeze"] is False for g in doc["architecture_gates"])
    # the rule itself: one insufficient gate keeps the hypothesis status; all sufficient would freeze
    assert b.architecture_status([{"evidence_sufficient_for_freeze": True}]) == "FROZEN_REFERENCE_FLIGHT_ARCHITECTURE"
    assert b.architecture_status([{"evidence_sufficient_for_freeze": True},
                                  {"evidence_sufficient_for_freeze": False}]) == "INVESTIGATION_HYPOTHESIS"
    assert b.architecture_status([]) == "INVESTIGATION_HYPOTHESIS"


def test_required_gates_listed_with_blocking_evidence(doc):
    gates = {g["id"]: g for g in doc["architecture_gates"]}
    names = " ".join(g["gate"] for g in doc["architecture_gates"]).lower()
    for need in ("rvm rows", "hall credible", "icp-45", "coupled h-1 / icp thermal", "anode thermal",
                 "final anode material", "rf component ratings"):
        assert need in names, need
    plan_ids = {s["id"] for s in doc["evidence_plan"]}
    for g in gates.values():
        assert g["blocking_evidence"] and g["sources"] and g["evidence_plan_steps"]
        assert set(g["evidence_plan_steps"]) <= plan_ids
        assert "PASS" not in str(g["current_status"]).replace("'PASS': 0", "").replace("PASS 0", "")
    rvm = gates["AG-01"]["blocking_evidence"]["rows"]
    assert len(rvm) == len(_j("docs/requirements/rvm_a9/rvm_a9_v1.json")["rows"])
    assert all(r["status"]["hall_icp_neutralizer"] != "PASS" for r in rvm)
    assert {g for s in doc["evidence_plan"] for g in s["addresses_gates"]} == set(gates)


def test_parameter_row_contract(doc):
    fs_vocab = set(doc["freeze_status_vocabulary"])
    ecs = set(doc["evidence_classes"])
    ids = [r["id"] for r in doc["parameters"]]
    assert len(ids) == len(set(ids))
    for r in doc["parameters"]:
        for k in ("value", "tolerance", "evidence_class", "source", "freeze_status"):
            assert k in r, (r["id"], k)
        assert r["freeze_status"] in fs_vocab
        tbd = isinstance(r["value"], str) and r["value"].startswith("TBD")
        if tbd:
            assert r["evidence_class"] is None and r["freeze_status"] != "FREEZE_CANDIDATE", r["id"]
        else:
            assert r["evidence_class"] in ecs, r["id"]
        if r["freeze_status"] != "FREEZE_CANDIDATE":
            assert r["evidence_to_advance"], r["id"]
        if r.get("value_label") in ("PARAMETRIC_SENSITIVITY", "PARETO_SET"):
            assert r["freeze_status"] != "FREEZE_CANDIDATE", r["id"]
        assert r["source"]
        for s in r["source"]:
            assert (ROOT / s["path"]).is_file(), s["path"]
            assert len(s["sha256"]) == 64
            assert ("pointer" in s) or ("locator" in s)
    roll = doc["freeze_rollup"]
    assert roll["total"] == len(doc["parameters"]) == sum(roll["counts"].values())


def test_sections_cover_every_f9_bullet(doc, b):
    covered = {(r["section"], r["subsection"]) for r in doc["parameters"]}
    for sec, subs in b.SECTIONS.items():
        for sub in subs:
            assert (sec, sub) in covered, (sec, sub)
    directive = (ROOT / b.PINS["A97_MD"][0]).read_text(encoding="utf-8")
    for bullet in doc["a9_7_f9_coverage"]:
        assert bullet in directive


def test_a92_statuses_verbatim(doc):
    dec = _j("docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json")
    assert doc["a9_2_statuses"]["statuses"] == dec["decisions"]["a9_10_statuses"]
    assert len(doc["a9_2_statuses"]["statuses"]) == 10
    assert doc["a9_2_statuses"]["statuses"]["Hall->ICP architecture"] == "INVESTIGATION_HYPOTHESIS"


def test_pareto_sets_carried_never_selected(doc):
    up = doc["upstream_pareto"]
    # A9.13 F9-OQ-01 (owner decision): the robust set is carried, representative selection deferred
    assert up["representative"]["status"] == "DEFERRED_BY_OWNER" and up["representative"]["selected"] is None
    assert up["representative"]["owner_question"] == "F9-OQ-01" and up["carried_to_lock1_as_set"] is True
    f78 = _j("docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json")
    want = sorted(m["design_id"] for blk in f78["robust"]["robust_pareto_by_P_set"].values() for m in blk["members"])
    assert sorted(m["design_id"] for m in up["robust_set"]["members"]) == want
    surv = {r["design_id"] for r in _j("docs/design_synthesis/f7_f8_optimizer/f8_robust_candidates_v1.json")["rows"]}
    assert up["nominal_pareto_union"]["n_members"] == len(surv)
    pareto_rows = [r for r in doc["parameters"] if isinstance(r["value"], dict) and r["value"].get("kind") ==
                   "PARETO_SET"]
    assert pareto_rows and all(r["freeze_status"] != "FREEZE_CANDIDATE" for r in pareto_rows)
    by_id = {r["id"]: r for r in doc["parameters"]}
    assert by_id["AFC-UP-IN-01"]["value"]["robust_set_values"] == sorted({m["area_m2"] for m in
                                                                         up["robust_set"]["members"]})


def test_f5_rows_imported_unchanged(doc):
    f5 = _j("docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json")
    by_id = {r["id"]: r for r in doc["parameters"]}
    for p in f5["parameters"]:
        r = by_id["AFC-" + p["id"]]
        for k in ("value", "units", "tolerance", "evidence_class", "freeze_status"):
            assert r[k] == p[k], (p["id"], k)


def test_icp_geometry_all_tbd_until_p1_p2(doc):
    f6 = _j("docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json")
    by_id = {r["id"]: r for r in doc["parameters"]}
    for v in f6["design_vector"]["variables"]:
        r = by_id["AFC-" + v["id"]]
        assert r["value"].startswith("TBD") and r["freeze_status"] == "TBD_AFTER_EVIDENCE"


def test_owner_rollup_complete_and_unanswered(doc):
    ro = doc["owner_question_rollup"]
    v4 = _j("docs/budgets/owner_decisions/owner_questions_state_v4.json")
    want = sorted(r["no"] for r in v4["rows"] if r["status"] == "TBD_OWNER")
    assert sorted(q["no"] for q in ro["state_v4_tbd_owner"]) == want
    lane_files = ["docs/performance/PERFORMANCE_BASELINE_98fbbb9.json", "docs/performance/abep_core/parity_report_v1.json",
                  "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1_core.json",
                  "docs/design_synthesis/f2_filter/f2_filter_stage_v1.json",
                  "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json",
                  "docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json",
                  "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json",
                  "docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json",
                  "docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json"]
    lane_ids = {q["id"] for f in lane_files for q in _j(f)["open_owner_questions"]}
    assert {q["id"] for q in ro["a9_7_lane_questions"]} == lane_ids
    new = [q["id"] for q in doc["open_owner_questions"]]
    assert new == ro["new_f9_questions"] and all(i.startswith("F9-OQ-") for i in new)
    assert not set(new) & (lane_ids | {r["id"] for r in v4["rows"]})
    for q in doc["open_owner_questions"]:
        # A9.9 / A9.13 answered the four F9 questions (recorded, never answered by F9 itself)
        assert q["status_when_raised"] == "TBD_OWNER" and q["status"] == "OWNER_DECIDED"
        assert "answer" not in q and "owner_answer" not in q and q["answer_verbatim"]


def test_model_change_candidates_need_owner_and_history(doc):
    mcc = doc["model_change_candidates"]
    text = " ".join(m["finding"] for m in mcc)
    for need in ("F1-01", "F3-01", "F3-02", "G-05", "DIV-01", "DIV-02", "DIV-03"):
        assert need in text, need
    for m in mcc:
        # A9.9 F1Q-01 / UPSTREAM_ICD-Q7 / F9-OQ-04 (owner decisions) authorised all candidates; step 2 implements
        assert m["status"] == "OWNER_AUTHORISED_PENDING_STEP_2_MODEL_CHANGE" and m["implemented_here"] is False
        assert any("HISTORY" in x for x in m["required"]) and any("owner" in x for x in m["required"])
        assert m["owner_question"] and m["sources"]


def test_no_pass_no_winner_and_compliance(doc):
    for r in doc["parameters"]:
        assert r["freeze_status"] != "PASS"
    txt = json.dumps(doc).lower()
    for banned in ('"winner"', '"selected_design"', "best architecture", "recommended architecture"):
        assert banned not in txt, banned
    c = doc["compliance"]
    for k in ("existing_modules_modified", "frozen_data_modified", "decisions_modified", "wired_into_archengine",
              "tbd_converted_to_assumed_for_optimum", "single_optimum_or_winner_declared", "pass_declared",
              "owner_question_answered", "new_pytest_skips"):
        assert c[k] is False, k


def test_pins_verified_and_fail_closed(doc, b):
    for v in doc["pins"].values():
        assert hashlib.sha256((ROOT / v["path"]).read_bytes()).hexdigest() == v["sha256"]
    key = "A97_MD"
    saved = b.PINS[key]
    try:
        b.PINS[key] = (saved[0], "0" * 64)
        with pytest.raises(SystemExit):
            b.verify_pins()
    finally:
        b.PINS[key] = saved


def test_code_hygiene():
    for p in (BUILDER, Path(__file__)):
        src = p.read_text(encoding="utf-8")
        assert "xe" + "_ledger" not in src, p.name
    bsrc = BUILDER.read_text(encoding="utf-8")
    assert "import abep_sim" not in bsrc and "from abep_sim" not in bsrc and "archengine import" not in bsrc


def test_no_freeze_candidate_depends_on_open_row(doc):
    """PHY-03: no FREEZE_CANDIDATE row names an OPEN (non-FREEZE_CANDIDATE) H1F / AFC row, and the Hall magnet supply
    count / trim slot (contingent on the OPEN coil arrangement H1F-MC-02) is not a freeze candidate."""
    import re
    rows = doc["parameters"]
    st = {r["id"]: r["freeze_status"] for r in rows}
    f5 = {p["id"]: p["freeze_status"] for p in _j("docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json")["parameters"]}
    for r in rows:
        if r["freeze_status"] != "FREEZE_CANDIDATE":
            continue
        txt = json.dumps([r["value"], r["basis"], r.get("evidence_note", "")])
        for d in set(re.findall(r"H1F-[A-Z]{2}-\d\d", txt)):
            assert f5.get(d) in (None, "FREEZE_CANDIDATE"), (r["id"], d)
        for d in set(re.findall(r"AFC-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d\d", txt)) - {r["id"]}:
            assert st.get(d) in (None, "FREEZE_CANDIDATE"), (r["id"], d)
        srcs = json.dumps(r["source"])
        assert '"pointer": "/items/30' not in srcs, r["id"]          # A902-31 (H21-27, assumed (requirement))
    for pid in ("AFC-SY-PPU-03", "AFC-SY-PPU-04", "AFC-H1F-CO-14", "AFC-H1F-MC-02"):
        assert st[pid] != "FREEZE_CANDIDATE", pid
    ppu4 = next(r for r in rows if r["id"] == "AFC-SY-PPU-04")
    assert ppu4["evidence_class"] == "assumed"


def test_a9_19_a9_20_single_flight_configuration(doc, b):
    """A9.19: one Hall + one RF/ICP neutralizer for both supply modes (AIR_PRIMARY primary, XE_CONTINGENCY contingency
    / emergency), no hollow cathode; A9.20: hall_c1_reference only as a labelled GROUND_REFERENCE."""
    from abep_sim.design import a9_19_architecture as a919
    cfg = doc["configuration"]
    assert cfg["flight"] == "hall_icp_neutralizer" and cfg["flight_configurations"] == ["hall_icp_neutralizer"]
    assert "control_fallback" not in cfg and "primary" not in cfg
    assert cfg["ground_reference"] == {"configuration": "hall_c1_reference", "label": "GROUND_REFERENCE",
                                       "c1_status": "GROUND_ONLY_LAB_EQUIPMENT", "flight_candidate": False,
                                       "uses": a919.C1_ROLE["uses"]}
    fa = cfg["flight_architecture"]
    assert fa["hall_accelerators"] == 1 and fa["electron_source_neutralizer"]["count"] == 1
    assert fa["conventional_hollow_cathode"] == "NONE"
    assert fa["icp_feed_gas_baseline"]["primary"] == "G-REUSE"
    assert [(m["mode"], m["role"]) for m in fa["supply_modes"]] == [("AIR_PRIMARY", "PRIMARY"),
                                                                    ("XE_CONTINGENCY", "CONTINGENCY_EMERGENCY")]
    by = {r["id"]: r for r in doc["parameters"]}
    xe = by["AFC-SY-XE-01"]["value"]
    assert "XE_CONTINGENCY" in xe and "RFP-P17-05" in xe and "RFP-P18-08" in xe and "not a contingency" not in xe
    ctl = by["AFC-SY-CTL-01"]
    assert "C1-selected variant uses" not in ctl["evidence_note"] and "ground" in ctl["basis"]
    # AG-01: the flight column only; the C1 cells live only in the labelled ground-reference history section
    for r in doc["architecture_gates"][0]["blocking_evidence"]["rows"]:
        assert set(r["status"]) == {"hall_icp_neutralizer"}
    rows = doc["a9_19_owner_answers_applied"]
    assert {r["decision"] for r in rows} == {"A9.19", "A9.20"}
    for r in rows:
        assert r["decision_json_sha256"] == a919.DECISIONS[r["decision"]]["json_sha256"]
        assert r["decision_md_sha256"] == a919.DECISIONS[r["decision"]]["md_sha256"]
    assert "PASS" not in json.dumps(rows)
    for k in ("A919", "A920", "A919_MD", "A920_MD"):
        assert k in b.PINS


# ------------------------------------------------------------------------------- F9: one flight configuration only
FLIGHT = "hall_icp_neutralizer"
RETIRED = "hall_c1_reference"
# JSON top-level sections where the retired / ground-reference configuration name may appear: the labelled
# ground-reference entries, verbatim historical owner-question text, and the A9.19 / A9.20 application record
RETIRED_ALLOWED_TOP = {"configuration", "ground_reference_history", "owner_question_rollup", "open_owner_questions",
                       "a9_19_owner_answers_applied"}


def _paths_with(o, needle, path=()):
    if isinstance(o, dict):
        for k, v in o.items():
            if needle in k:
                yield path + (k,)
            yield from _paths_with(v, needle, path + (k,))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _paths_with(v, needle, path + (i,))
    elif isinstance(o, str) and needle in o:
        yield path


def test_only_flight_configuration_in_status_counts_objectives_and_gates(doc):
    hits = list(_paths_with(doc, RETIRED))
    assert hits, "the labelled ground-reference history must still record the retired configuration"
    assert {h[0] for h in hits} <= RETIRED_ALLOWED_TOP, sorted({h[0] for h in hits} - RETIRED_ALLOWED_TOP)
    # inside 'configuration' only the labelled ground_reference entry and its rule text
    assert {h[1] for h in hits if h[0] == "configuration"} <= {"ground_reference", "rule"}
    assert doc["configuration"]["ground_reference"]["flight_candidate"] is False
    for g in doc["architecture_gates"]:
        assert RETIRED not in json.dumps(g), g["id"]
        assert "ground_reference" not in json.dumps(g), g["id"]
    ag01 = doc["architecture_gates"][0]["blocking_evidence"]
    assert set(ag01["status_counts"]) == {FLIGHT}
    rvm = _j("docs/requirements/rvm_a9/rvm_a9_v1.json")
    assert ag01["status_counts"][FLIGHT] == rvm["status_counts"][FLIGHT]
    assert doc["architecture_gates"][0]["current_status"].startswith(FLIGHT + ":")
    for k in ("parameters", "upstream_pareto", "evidence_plan", "freeze_rollup", "findings", "standing_facts",
              "model_change_candidates", "interface_demands"):
        assert RETIRED not in json.dumps(doc[k]), k
    gh = doc["ground_reference_history"]
    assert gh["label"] == "GROUND_REFERENCE_AND_RETIRED_FLIGHT_CONFIGURATION_HISTORY"
    assert gh["configuration"] == RETIRED and gh["flight_status"].startswith("RETIRED_AS_FLIGHT_CONFIGURATION")
    for k in ("evaluated_for_flight", "in_status_counts", "in_gates", "in_objectives"):
        assert gh[k] is False, k
    assert gh["rvm_status_counts_as_carried"] == rvm["status_counts"].get(RETIRED)
    # Markdown: the retired name only in the header ground-reference line, the labelled history section, the verbatim
    # owner-question tables and the A9.19 / A9.20 application table
    md = MD_PATH.read_text(encoding="utf-8")
    section = None
    for ln in md.splitlines():
        if ln.startswith("## "):
            section = ln
        if RETIRED in ln:
            assert (section is None and ln.startswith("Flight configuration:")) or section in (
                "## Ground reference / retired flight configuration (history only; not evaluated for flight)",
                "## Owner-question roll-up (questions as raised by the lanes; current status from state v5)",
                "## A9.19 / A9.20 owner decisions applied"), (section, ln[:120])
    gates_md = md.split("## Architecture-level gates")[1].split("\n## ")[0]
    assert RETIRED not in gates_md and "C1 ground reference" not in gates_md
    # the verbatim A9.2 CONTROL_FALLBACK status of C1 is shown only as superseded history (A9.19 / A9.20)
    sup = doc["a9_2_statuses"]["superseded_as_flight_status"]
    assert set(sup) == {k for k, v in doc["a9_2_statuses"]["statuses"].items() if v == "CONTROL_FALLBACK"}
    assert sup and all("GROUND_ONLY_LAB_EQUIPMENT" in v and "superseded" in v for v in sup.values())


# ------------------------------------------------------------------------- AG-15 from the registered RFP + RVM
REG_PATH = "docs/requirements/rfp_official/rfp_registration_v1.json"


@pytest.fixture(scope="module")
def ag15(b):
    import ag15_f9  # the builder put the lane directory on sys.path
    return ag15_f9


def test_ag15_consumes_registered_rfp_and_rvm_rebase(doc, ag15):
    reg = _j(REG_PATH)
    rvm = _j("docs/requirements/rvm_a9/rvm_a9_v1.json")
    g = {x["id"]: x for x in doc["architecture_gates"]}["AG-15"]
    a = g["blocking_evidence"]["assessment"]
    # derived from the registration record (status, sha256, pages, clause count, file hash)
    assert reg["status"] == "REGISTERED_BY_HASH_PDF_CONTROLLED_EXTERNALLY"
    p = a["evidence_parts"]["official_rfp_registered_with_immutable_provenance_hash"]
    assert p["state"] == "EVIDENCE_PRESENT" and p["status"] == reg["status"]
    assert p["pdf_sha256"] == reg["document"]["sha256"] and p["pages"] == reg["document"]["pages"]
    assert p["n_registered_clauses"] == len(reg["clauses"])
    assert p["clauses_sha256"] == ag15.clauses_sha256(reg["clauses"]) == rvm["rfp_rebase"]["registration"]["clauses_sha256"]
    assert a["registration_file_sha256"] == hashlib.sha256((ROOT / REG_PATH).read_bytes()).hexdigest()
    assert any(s["path"] == REG_PATH for s in g["sources"])
    assert doc["consumed"]["RFP"]["path"] == REG_PATH
    # every registered clause is mapped to an RVM row (or recorded programmatic), checked independently here
    cov = {c["clause_id"]: c for c in rvm["rfp_rebase"]["clause_coverage"]}
    for c in reg["clauses"]:
        assert cov[c["id"]]["rvm_rows"] or cov[c["id"]]["not_system_requirement"]["class"], c["id"]
    rb = a["evidence_parts"]["rvm_requirements_rebased_against_it"]
    assert rb["state"] == "EVIDENCE_PRESENT" and rb["clauses_unmapped"] == []
    assert rb["clauses_mapped_to_rvm_rows"] + len(rb["clauses_recorded_programmatic"]) == len(reg["clauses"])
    assert rb["origin_counts"] == rvm["rfp_rebase"]["origin_counts"]
    # the registration is determining evidence for a 'requirement' gate ...
    assert a["determining_evidence"]["closes"] is True
    # ... but the gate stays open while the owner's closure / requirement_frozen is pending
    rfp_rows = [r for r in rvm["rows"] if r["requirement_origin"] == "RFP_CLAUSE"]
    if not all(r["requirement_frozen"] for r in rfp_rows) or not rvm["rfp_rebase"]["ag_15_status"].startswith("CLOSED"):
        assert a["status"] == ag15.STATUS_EVIDENCE_PRESENT
        assert g["current_status"].startswith(ag15.STATUS_EVIDENCE_PRESENT)
        assert [c["id"] for c in a["remaining_conditions"]] == ["AG15-RC-01"]
        assert a["closes"] is False and g["evidence_sufficient_for_freeze"] is False
    assert a["gate_text_verbatim"] in (ROOT / "docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_"
                                              "DECISIONS.md").read_text(encoding="utf-8")
    txt = json.dumps(doc["architecture_gates"])
    assert "BLOCKED_RFP_NOT_REGISTERED" not in txt and "NOT_IN_REPOSITORY" not in txt
    assert "PASS" not in g["current_status"]
    md_gates = MD_PATH.read_text(encoding="utf-8").split("## Architecture-level gates")[1].split("\n## ")[0]
    assert "BLOCKED_RFP_NOT_REGISTERED" not in md_gates and "AG-15 (A9.13 S6.22" in md_gates
    # the only remaining occurrence is the A9.16 step-1 application record (history), never a gate status
    hist = [h for h in _paths_with(doc, "BLOCKED_RFP_NOT_REGISTERED")]
    assert {h[0] for h in hist} <= {"a9_16_owner_answers_applied"}, hist
    ep01 = {s["id"]: s for s in doc["evidence_plan"]}["EP-01"]
    assert "owner closure of AG-15" in ep01["evidence"]


def test_ag15_fail_closed_on_missing_or_inconsistent_registration(ag15):
    import copy
    reg = _j(REG_PATH)
    rvm = _j("docs/requirements/rvm_a9/rvm_a9_v1.json")
    sha = hashlib.sha256((ROOT / REG_PATH).read_bytes()).hexdigest()
    assert ag15.assess(reg, rvm, sha)["status"] == ag15.STATUS_EVIDENCE_PRESENT
    refused = ag15.STATUS_REFUSED
    assert ag15.assess(None, rvm, sha)["status"] == refused                       # registration missing
    assert ag15.assess(reg, None, sha)["status"] == refused                       # RVM / re-base missing
    assert ag15.assess(reg, rvm, "not-a-hash")["status"] == refused

    def tampered(fn):
        r2, v2 = copy.deepcopy(reg), copy.deepcopy(rvm)
        fn(r2, v2)
        out = ag15.assess(r2, v2, sha)
        assert out["status"] == refused and out["closes"] is False and out["errors"], fn
        assert out["evidence_sufficient_for_freeze"] is False

    tampered(lambda r, v: r["document"].pop("sha256"))                             # hash missing
    tampered(lambda r, v: r["document"].__setitem__("sha256", "0" * 64))           # hash inconsistent with the RVM
    tampered(lambda r, v: r["document"].__setitem__("sha256", "xyz"))              # not a sha256
    tampered(lambda r, v: r.__setitem__("status", "PENDING"))                      # not registered
    tampered(lambda r, v: r["document"].__setitem__("pages", 0))
    tampered(lambda r, v: r["clauses"][0].__setitem__("text", r["clauses"][0]["text"] + " "))   # clause hash drift
    tampered(lambda r, v: r["clauses"].pop())                                      # clause count / hash drift
    tampered(lambda r, v: v["rfp_rebase"]["clause_coverage"].pop(0))               # a clause left unmapped
    tampered(lambda r, v: v["rows"][0].__setitem__("requirement_origin", "SECONDARY_TRANSCRIPTION"))
    tampered(lambda r, v: v["rows"][0].__setitem__("rfp_clauses", ["RFP-P99-99"]))
    # review fixes: origin_counts can no longer be dropped to skip the check, and a re-base with no RFP_CLAUSE row
    # (where 'every RFP row frozen' would hold vacuously) is refused, even with a recorded owner closure
    tampered(lambda r, v: v["rfp_rebase"].pop("origin_counts"))

    def no_rfp_rows(r, v):
        v["rfp_rebase"]["ag_15_status"] = "CLOSED by owner (hypothetical)"
        for row in v["rows"]:
            if row["requirement_origin"] == "RFP_CLAUSE":
                row["requirement_origin"] = "DERIVED_PROJECT_REQUIREMENT"
        counts = {}
        for row in v["rows"]:
            counts[row["requirement_origin"]] = counts.get(row["requirement_origin"], 0) + 1
        v["rfp_rebase"]["origin_counts"] = counts
    tampered(no_rfp_rows)


def test_ag15_closes_only_on_recorded_owner_closure(ag15):
    import copy
    reg = _j(REG_PATH)
    rvm = copy.deepcopy(_j("docs/requirements/rvm_a9/rvm_a9_v1.json"))
    sha = hashlib.sha256((ROOT / REG_PATH).read_bytes()).hexdigest()
    rvm["rfp_rebase"]["ag_15_status"] = "CLOSED by owner (hypothetical)"
    assert ag15.assess(reg, rvm, sha)["closes"] is False                           # RFP rows still unfrozen
    for r in rvm["rows"]:
        if r["requirement_origin"] == "RFP_CLAUSE":
            r["requirement_frozen"] = True
    out = ag15.assess(reg, rvm, sha)
    assert out["status"] == ag15.STATUS_CLOSABLE and out["closes"] is True and out["remaining_conditions"] == []


def test_builder_refuses_missing_or_inconsistent_registration():
    for mutate in ("missing_path", "tampered_record"):
        b2 = _load_builder()
        if mutate == "missing_path":
            b2.CONSUMED["RFP"] = "docs/requirements/rfp_official/rfp_registration_missing.json"
        else:
            reg = _j(REG_PATH)
            reg["document"]["sha256"] = "f" * 64
            b2._cache["RFP"] = reg
        with pytest.raises(SystemExit) as e:
            b2.ag15_assessment()
        assert "REFUSED: AG-15" in str(e.value)
    b3 = _load_builder()
    b3.REPO = ROOT / "nonexistent_root_for_test"
    with pytest.raises(SystemExit) as e:
        b3.ag15_assessment()
    assert "REFUSED" in str(e.value)


# ---------------------------------------------------------------------------------------------------------------------
# design-state set v2: F9 re-derives every F1 / F4 / F7 / F8-derived value; an empty robust set fails closed
# ---------------------------------------------------------------------------------------------------------------------
def _f78():
    return _j("docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json")


def test_empty_robust_set_yields_explicit_status_never_a_range(doc, b):
    f78 = _f78()
    members = [m for blk in f78["robust"]["robust_pareto_by_P_set"].values() for m in blk["members"]]
    rs = doc["upstream_pareto"]["robust_set"]
    if members:
        assert rs["status"] == b.ROBUST_NON_EMPTY and rs["status_summary"] is None
        return
    assert rs["status"] == b.EMPTY_ROBUST == "EMPTY_ROBUST_SET_NOT_EVALUATED"
    assert rs["n_members"] == 0 and rs["members"] == [] and rs["n_all_scenario_feasible_total"] == 0
    assert f78["robust"]["all_scenario_feasible"] == 0
    rows = [r for r in doc["parameters"] if isinstance(r["value"], dict) and "robust_set_status" in r["value"]]
    assert {r["id"] for r in rows} >= {"AFC-UP-IN-01", "AFC-UP-IN-09", "AFC-UP-CO-05", "AFC-UP-CO-06",
                                       "AFC-UP-CO-08", "AFC-UP-CO-09", "AFC-UP-PL-01", "AFC-UP-PL-02", "AFC-UP-PL-08"}
    for r in rows:
        assert r["value"]["robust_set_status"] == b.EMPTY_ROBUST, r["id"]
        for k, v in r["value"].items():
            if k.startswith("robust_set_range") or k == "robust_set_worst_case_range_mg_s":
                assert v is None, (r["id"], k)          # never a fabricated range
            if k == "robust_set_values":
                assert v == [], r["id"]
        assert r["freeze_status"] != "FREEZE_CANDIDATE"
    # offered feed records: explicit empty status with the transient reasons read from F4
    f4 = _j("docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json")
    vf06 = {r["id"]: r for r in doc["parameters"]}["AFC-UP-VF-06"]["value"]
    if not f4["offered_to_h1"]:
        assert vf06["status"] == b.EMPTY_OFFERED and vf06["n_records"] == 0 and vf06["P_range_Pa"] is None
        assert vf06["orbit_check_failure_reason_counts"]
    # design finding for the owner: recorded, no requirement relaxation, owner flow-gap order cited verbatim
    df = doc["design_findings_for_owner"]
    assert [d["id"] for d in df] == ["F9-DF-01"]
    assert df[0]["status"] == b.EMPTY_ROBUST and df[0]["requirement_relaxation_proposed"] is False
    assert df[0]["flow_gap_owner_order"] == f78["flow_gap_owner_order"]
    assert "NO_REQUIREMENT_RELAXATION" in df[0]["finding"] and "no robust upstream design survives" in df[0]["finding"]
    assert any(f["id"] == "F9-07" and f["design_finding"] == "F9-DF-01" for f in doc["findings"])
    assert doc["architecture_status"] == "INVESTIGATION_HYPOTHESIS"


def test_empty_set_helpers_fail_closed(b):
    assert b.robust_range({"members": []}, []) is None
    assert b.robust_range({"members": [{}]}, [2.0, 1.0]) == [1.0, 2.0]
    with pytest.raises(SystemExit):
        b._rng([])


def test_upstream_text_values_equal_current_outputs(doc):
    """No hard-coded F4 / F7 / F8 numbers: the values in F9 are the values in the current lane outputs."""
    f78, f4 = _f78(), _j("docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json")
    cols = f78["upstream_pareto_summary"]["columns"]
    rows = [dict(zip(cols, r)) for r in f78["upstream_pareto_summary"]["rows"]]
    f7front = max(r["frontier_mdot_delivered_min_mgps"] for r in rows if r["filter"] == "F4-FIL-NONE"
                  and r["wall"] == "WALL-G0" and r["frontier_mdot_delivered_min_mgps"] is not None)
    single, sched = [], []
    for blk in f4["steady"]["feasibility_regions"].values():
        if blk["filter"] == "F4-FIL-NONE" and blk["wall"] == "WALL-G0":
            for e in (e for lst in blk["per_scenario"].values() for e in lst):
                single += [e["frontier_mdot_mgps"]] if e["frontier_mdot_mgps"] is not None else []
                s = (e.get("scheduled_setpoint") or {}).get("frontier_mdot_mgps")
                sched += [s] if s is not None else []
    by = {r["id"]: r for r in doc["parameters"]}
    pl08 = by["AFC-UP-PL-08"]["value"]
    assert pl08["f7_nominal_context_all_state_frontier_mg_s"] == f7front
    assert pl08["all_state_single_setpoint_frontier_mg_s"] == max(single)
    assert pl08["all_state_scheduled_frontier_mg_s"] == max(sched)
    fnd = {f["id"]: f["finding"] for f in doc["findings"]}
    assert f"all-state frontier {f7front} mg/s" in fnd["F9-03"]
    ag12 = {g["id"]: g for g in doc["architecture_gates"]}["AG-12"]
    assert f"({f7front} mg/s all-state" in ag12["blocking_evidence"]["engineering_warning"]
    rs = doc["upstream_pareto"]["robust_set"]
    if doc["design_findings_for_owner"]:
        ev = doc["design_findings_for_owner"][0]["evidence"]
        f8rows = _j("docs/design_synthesis/f7_f8_optimizer/f8_robust_candidates_v1.json")["rows"]
        assert ev["F8"]["survivors"] == len(f8rows)
        assert ev["F8"]["all_scenario_feasible"] == f78["robust"]["all_scenario_feasible"] == \
            rs["n_all_scenario_feasible_total"]
        assert ev["F7"]["vector_status_totals"] == f78["upstream_status_totals"]
        assert ev["F7"]["n_pareto_members"] == sum(r["n_pareto"] for r in rows)
        assert ev["F4"]["offered_to_h1_records"] == len(f4["offered_to_h1"])
    # superseded F7 / F4 numbers occur only in the as-raised owner-question text, labelled as history
    stale = ("0.09832", "0.1192", "0.119186")
    rest = {k: v for k, v in doc.items() if k != "open_owner_questions"}
    assert not any(s in json.dumps(rest) for s in stale)
    for q in doc["open_owner_questions"]:
        if any(s in json.dumps(q) for s in stale):
            assert q["as_raised_numbers"] and q["current_upstream_values"]["all_state_frontier_mg_s_F7"] == f7front
    src = BUILDER.read_text(encoding="utf-8").split("F9_QUESTIONS = [", 1)[0]
    assert not any(s in src for s in stale)
    assert not any(s in (LANE / "a9_16_f9.py").read_text(encoding="utf-8") for s in stale)
