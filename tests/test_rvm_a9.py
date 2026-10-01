"""Tests for the A9 system requirement-verification matrix (docs/requirements/rvm_a9/, follow-on fo_a9_6_rvm, trigger
T_A9_6_RVM; owner directive A9.6 sec. 15).

Checks: byte-for-byte reproduction and --check; pins verified, governance never pinned, pin mismatch refused; status
vocabulary is exactly the six A9.6 states; no row is PASS without a cited verified measurement artifact; rule engine
(synthetic refused, missing field refused, plan / allocation / budget can never PASS, verified measurement PASS / FAIL,
basis-not-frozen downgrade, floor FAIL only under every reading with a verified lower bound, OUT_OF_DOMAIN distinct from
FAIL, NUMERICAL_FAILURE); every required top-level row present for both configurations; statuses derive from the
probes (mass INCOMPLETE_EVIDENCE with per-reading results, power NOT_EVALUATED, AO / thermal INCOMPLETE_EVIDENCE);
fail-closed probes (non-empty credible set, changed power verdict); every cited artifact path exists; required sections
(a)-(f); no forbidden substring.
Run: python -m pytest -q tests/test_rvm_a9.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "requirements" / "rvm_a9"
OUT_JSON = LANE / "rvm_a9_v1.json"
OUT_MD = LANE / "RVM_A9.md"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


B = _load("build_rvm_a9", LANE / "build_rvm_a9.py")
R = _load("rvm_rules_t", LANE / "rvm_rules.py")

SIX = ("PASS", "FAIL", "NOT_EVALUATED", "OUT_OF_DOMAIN", "INCOMPLETE_EVIDENCE", "NUMERICAL_FAILURE")


@pytest.fixture(scope="module")
def doc():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


def _a(**kw):
    a = {"path": "x/y.json", "id": "T-1", "role": "DETERMINING", "kind": "PLAN_OR_FRAMEWORK",
         "evidence_state": "test", "evaluated": False, "verified": False, "measured": False, "synthetic": False,
         "in_domain": None, "meets": None, "coverage_complete": False, "evidenced_terms": 0,
         "numerical_failure": False, "lower_bound_verified": False, "exceeds_limit_every_reading": None}
    a.update(kw)
    return a


def _meas(**kw):
    base = dict(kind="MEASUREMENT", measured=True, evaluated=True, verified=True, in_domain=True, meets=True,
                coverage_complete=True, evidenced_terms=1)
    base.update(kw)
    return _a(**base)


# ------------------------------------------------------------------------------------------ reproduction / pins
def test_builder_reproduces_outputs():
    js, md = B.render()
    assert OUT_JSON.read_text(encoding="utf-8") == js
    assert OUT_MD.read_text(encoding="utf-8") == md
    assert B.main(["--check"]) == 0


def test_pins_match_and_governance_never_pinned(doc):
    for p in doc["pins"]:
        assert hashlib.sha256((REPO / p["path"]).read_bytes()).hexdigest() == p["sha256"], p["path"]
    pinned = {p["path"] for p in doc["pins"]} | {p["path"] for p in doc["referenced_not_pinned"]}
    for g in ("lane_registry", "trigger_registry", "fired_triggers", "trigger_ledger", "runtime_state"):
        assert not any(g in p for p in pinned)
    for h in doc["historical_reuse"]["artifacts"]:
        assert hashlib.sha256((REPO / h["path"]).read_bytes()).hexdigest() == h["sha256"]


def test_pin_mismatch_refused(monkeypatch):
    bad = dict(B.PINS)
    path, _sha, role = bad["ANS"]
    bad["ANS"] = (path, "0" * 64, role)
    monkeypatch.setattr(B, "PINS", bad)
    with pytest.raises(B.BuildError):
        B.load_pins()


def test_reference_identity_checked(monkeypatch):
    bad = dict(B.REFS)
    path, field, _v, role = bad["MP"]
    bad["MP"] = (path, field, "some_other_id", role)
    monkeypatch.setattr(B, "REFS", bad)
    with pytest.raises(B.BuildError):
        B.load_refs()


# ------------------------------------------------------------------------------------------ vocabulary / PASS
def test_status_vocabulary_is_exactly_the_six(doc):
    assert tuple(R.STATUSES) == SIX
    assert tuple(doc["status_vocabulary"]) == SIX
    a96 = json.loads((REPO / B.PINS["A96"][0]).read_text(encoding="utf-8"))
    assert tuple(a96["summary"]["rvm_states"]) == SIX
    R.assert_status_vocabulary(doc)
    for row in doc["rows"]:
        for cell in row["configurations"].values():
            assert cell["status"] in SIX


def test_no_row_pass_without_verified_measurement_artifact(doc):
    R.assert_no_pass_without_measurement(doc)
    for row in doc["rows"]:
        for cfg, cell in row["configurations"].items():
            if cell["status"] == "PASS":
                ms = [a for a in cell["artifacts"] if a["kind"] == "MEASUREMENT" and a["verified"] and a["measured"]]
                assert ms and all((REPO / a["path"]).exists() for a in ms)
    # today: nothing in the repository is such an artifact -> no PASS anywhere
    assert all(doc["status_counts"][c]["PASS"] == 0 for c in B.CONFIGS)
    kinds = {a["kind"] for r in doc["rows"] for c in r["configurations"].values() for a in c["artifacts"]}
    assert "MEASUREMENT" not in kinds


def test_assert_no_pass_catches_forged_pass(doc):
    forged = copy.deepcopy(doc)
    forged["rows"][0]["configurations"]["hall_icp_neutralizer"]["status"] = "PASS"
    with pytest.raises(R.RvmError):
        R.assert_no_pass_without_measurement(forged)
    forged["rows"][0]["configurations"]["hall_icp_neutralizer"]["status"] = "COMPLIANT"
    with pytest.raises(R.RvmError):
        R.assert_status_vocabulary(forged)


# ------------------------------------------------------------------------------------------ rule engine
def test_plans_allocations_budgets_never_pass():
    for kind in ("PLAN_OR_FRAMEWORK", "PUBLISHED_ANALOG", "PROCUREMENT"):
        s, rule, _ = R.assign_status([_a(kind=kind)], True)
        assert s == "NOT_EVALUATED" and rule == "R7-NOT-EVALUATED"
    for kind in ("BUDGET_EVALUATION", "FRAMEWORK_EVALUATION", "VALIDATED_ANALYSIS"):
        with pytest.raises(R.RvmError):   # only a measurement can 'meet'
            R.assign_status([_a(kind=kind, evaluated=True, in_domain=True, meets=True, evidenced_terms=3)], True)
        s, _, _ = R.assign_status([_a(kind=kind, evaluated=True, in_domain=True, evidenced_terms=3)], True)
        assert s == "INCOMPLETE_EVIDENCE"
    s, _, _ = R.assign_status([_a(kind="BUDGET_EVALUATION", evaluated=True, in_domain=True, evidenced_terms=0)], True)
    assert s == "NOT_EVALUATED"


def test_missing_field_and_synthetic_refused():
    a = _a()
    del a["in_domain"]
    with pytest.raises(R.RvmError):
        R.assign_status([a], True)
    with pytest.raises(R.RvmError):
        R.assign_status([_meas(synthetic=True)], True)
    with pytest.raises(R.RvmError):   # mixed synthetic + measured refused
        R.assign_status([_meas(), _meas(id="S", synthetic=True)], True)
    with pytest.raises(R.RvmError):
        R.assign_status([_a(kind="PLAN_OR_FRAMEWORK", measured=True)], True)
    with pytest.raises(R.RvmError):
        R.assign_status([_a(role="SUPPORTING")], True)   # no determining artifact
    with pytest.raises(R.RvmError):
        R.assign_status([], True)


def test_measurement_pass_fail_and_downgrades():
    assert R.assign_status([_meas()], True)[0] == "PASS"
    assert R.assign_status([_meas()], False)[1] == "R3b-BASIS-NOT-FROZEN"
    assert R.assign_status([_meas(coverage_complete=False)], True)[1] == "R3c-COVERAGE"
    assert R.assign_status([_meas(meets=False)], True)[0] == "FAIL"
    assert R.assign_status([_meas(), _meas(id="M2", meets=False)], True)[0] == "FAIL"
    # an unverified measurement never passes
    s, rule, _ = R.assign_status([_meas(verified=False)], True)
    assert s == "INCOMPLETE_EVIDENCE" and rule == "R6-INCOMPLETE"
    # an out-of-domain measurement never passes and is not a FAIL
    s, rule, _ = R.assign_status([_meas(in_domain=False, meets=False)], True)
    assert s == "OUT_OF_DOMAIN"


def test_numerical_failure_distinct():
    s, rule, _ = R.assign_status([_a(kind="FRAMEWORK_EVALUATION", evaluated=True, in_domain=True, evidenced_terms=2,
                                     numerical_failure=True)], True)
    assert (s, rule) == ("NUMERICAL_FAILURE", "R1-NUMERICAL")


def test_floor_fail_rule():
    ok = dict(kind="BUDGET_EVALUATION", evaluated=True, in_domain=True, evidenced_terms=3)
    assert R.assign_status([_a(**ok, lower_bound_verified=True, exceeds_limit_every_reading=True)], True)[0] == "FAIL"
    assert R.assign_status([_a(**ok, lower_bound_verified=False, exceeds_limit_every_reading=True)],
                           True)[0] == "INCOMPLETE_EVIDENCE"
    assert R.assign_status([_a(**ok, lower_bound_verified=True, exceeds_limit_every_reading=False)],
                           True)[0] == "INCOMPLETE_EVIDENCE"
    c = R.floor_fail_check([{"reading": "a", "floor_only_kg": 41.0}, {"reading": "b", "floor_only_kg": 39.0}], 40.0,
                           True)
    assert c["exceeds_every_reading"] is False and c["n_exceeding"] == 1
    c = R.floor_fail_check([{"reading": "a", "floor_only_kg": 40.0}], 40.0, True)
    assert c["exceeds_every_reading"] is True          # strict '<': 40.0 violates
    c = R.floor_fail_check([{"reading": "a", "floor_only_kg": 40.0}], 40.0, False)
    assert c["exceeds_every_reading"] is False         # '<=': 40.0 is fine
    with pytest.raises(R.RvmError):
        R.floor_fail_check([], 40.0, True)
    with pytest.raises(R.RvmError):
        R.floor_fail_check([{"reading": "a", "floor_only_kg": float("nan")}], 40.0, True)


# ------------------------------------------------------------------------------------------ coverage of the matrix
REQUIRED_KEYS = ("ALTITUDE_ENVELOPE", "THRUST_12MN_SUSTAINED", "THRUST_25MN_CAPABILITY", "PBUS_LT_1500W_FULL_BUS",
                 "INTERNAL_1350W_ALLOCATION", "MASS_LT_40KG_WET", "ATMOSPHERIC_PROPELLANT", "XE_CAPABILITY",
                 "HALL_PREFERENCE", "FIRING_GT_15000H_PROVISIONAL", "MISSION_LIFE_GE_26280H", "STARTUP_RESTART",
                 "NEUTRALIZATION", "AO_MATERIAL_COMPATIBILITY")


def test_required_rows_present_for_both_configurations(doc):
    keys = {r["key"] for r in doc["rows"]}
    for k in REQUIRED_KEYS:
        assert k in keys, k
    for r in doc["rows"]:
        assert set(r["configurations"]) == set(B.CONFIGS)
        assert r["sources"], r["id"]
        assert r["verification_methods"] and set(r["verification_methods"]) <= set(B.VERIFICATION_METHODS)
        for cell in r["configurations"].values():
            assert cell["reason"] and cell["rule"] in R.RULES
            assert any(a["role"] == "DETERMINING" for a in cell["artifacts"])
            for a in cell["artifacts"]:
                assert (REPO / a["path"]).exists(), a["path"]
                assert a["id"]


def test_rfp_rows_not_frozen_and_no_interpretation_frozen(doc):
    for r in doc["rows"]:
        if r["category"] in ("rfp_recorded", "rfp_inferred_from_repo_text"):
            assert r["requirement_frozen"] is False, r["id"]
    assert doc["rfp_document_in_repository"] is False


def _row(doc, key):
    return next(r for r in doc["rows"] if r["key"] == key)


def test_expected_statuses_today(doc):
    for key in ("THRUST_12MN_SUSTAINED", "THRUST_25MN_CAPABILITY", "ALTITUDE_ENVELOPE", "NEUTRALIZATION",
                "PBUS_LT_1500W_FULL_BUS", "INTERNAL_1350W_ALLOCATION", "HALL_PREFERENCE",
                "FIRING_GT_15000H_PROVISIONAL", "MISSION_LIFE_GE_26280H", "STARTUP_RESTART", "XE_CAPABILITY",
                "ATMOSPHERIC_PROPELLANT"):
        for c in B.CONFIGS:
            assert _row(doc, key)["configurations"][c]["status"] == "NOT_EVALUATED", (key, c)
    for key in ("MASS_LT_40KG_WET", "INTERNAL_34_36KG_ALLOCATION", "AO_MATERIAL_COMPATIBILITY"):
        for c in B.CONFIGS:
            assert _row(doc, key)["configurations"][c]["status"] == "INCOMPLETE_EVIDENCE", (key, c)
    # TH-05: every P3 heat term and the coupled network are refused (INCOMPLETE_EVIDENCE inputs): 0 evaluated terms,
    # so the thermal row is NOT_EVALUATED (R7), never an 'evaluation with evidenced terms'
    for c in B.CONFIGS:
        cell = _row(doc, "THERMAL_CLOSURE")["configurations"][c]
        assert cell["status"] == "NOT_EVALUATED", c
        det = [a for a in cell["artifacts"] if a["role"] == "DETERMINING" and a["kind"] == "FRAMEWORK_EVALUATION"]
        assert det and all(a["evidenced_terms"] == 0 for a in det), c


def test_mass_rows_report_per_reading_and_no_fail(doc):
    for c in B.CONFIGS:
        cell = _row(doc, "MASS_LT_40KG_WET")["configurations"][c]
        det = [a for a in cell["artifacts"] if a["role"] == "DETERMINING"]
        assert len(det) == 1 and det[0]["kind"] == "BUDGET_EVALUATION"
        an = det[0]["detail"]["analyses"][0]
        assert an["lower_bound_verified"] is False
        assert an["floor_only_readings"] and an["mixed_basis_states"]
        assert an["floor_fail_check"]["exceeds_every_reading"] is False
        assert "FAIL not admissible" in det[0]["evidence_state"]
        assert cell["status"] != "FAIL"


def test_hall_performance_rows_cite_empty_credible_set(doc):
    for key in ("THRUST_12MN_SUSTAINED", "THRUST_25MN_CAPABILITY"):
        for c in B.CONFIGS:
            arts = _row(doc, key)["configurations"][c]["artifacts"]
            hall = [a for a in arts if a["kind"] == "VALIDATED_ANALYSIS"]
            assert hall and not hall[0]["evaluated"] and "EMPTY" in hall[0]["evidence_state"]


def test_neutralization_icp_uses_icp45_and_never_hall_on(doc):
    arts = _row(doc, "NEUTRALIZATION")["configurations"]["hall_icp_neutralizer"]["artifacts"]
    ids = [a["id"] for a in arts]
    assert any(i.endswith(":P1-S7") for i in ids) and any(i.endswith(":ICP-45") for i in ids)
    s7h = next(a for a in arts if a["id"].endswith(":P1-S7H"))
    assert s7h["role"] == "SUPPORTING"
    tk = next(a for a in arts if a["kind"] == "PUBLISHED_ANALOG")
    assert tk["role"] == "CONTEXT" and tk["in_domain"] is False


# ------------------------------------------------------------------------------------------ fail-closed probes
def test_nonempty_credible_set_refused(monkeypatch):
    pins = B.load_pins()
    refs = B.load_refs()
    refs["ENS"] = copy.deepcopy(refs["ENS"])
    refs["ENS"]["members"] = [{"ensemble_member_id": "fake"}]
    with pytest.raises(B.BuildError):
        B.probe_hall_analysis(B.Ctx(pins, refs))


def test_power_verdict_change_refused():
    pins = B.load_pins()
    refs = B.load_refs()
    refs["MP"] = copy.deepcopy(refs["MP"])
    refs["MP"]["power"]["configurations"]["hall_icp_neutralizer"]["rfp_gate_1ms"]["verdict"] = "PASS"
    with pytest.raises(B.BuildError):
        B.probe_power(B.Ctx(pins, refs), "hall_icp_neutralizer")
    refs["MP"]["power"]["configurations"]["hall_c1_reference"]["slots"][0]["MEASURED_W"] = 100.0
    with pytest.raises(B.BuildError):
        B.probe_power(B.Ctx(pins, refs), "hall_c1_reference")


def test_unknown_artifact_id_refused():
    ctx = B.Ctx(B.load_pins(), B.load_refs())
    with pytest.raises(B.BuildError):
        B.plan(ctx, "PRE", "DQ-HI-DOES-NOT-EXIST")
    with pytest.raises(B.BuildError):
        ctx.answer(4, "a token that is not in row 4")


def test_open_questions_not_answered(doc):
    ctx = B.Ctx(B.load_pins(), B.load_refs())
    for r in doc["rows"]:
        for o in r["open_readings"]:
            # A9.16 step 1: the owner answered every carried reading (A9.12 / A9.14, A9.15 amendments); the RVM records
            # the decision and never answers anything itself
            assert o["status"] in ("OWNER_DECIDED", "SUPERSEDED"), (r["id"], o["id"])
            if o["status"] == "OWNER_DECIDED":
                assert o["status_when_carried"] == "TBD_OWNER" and o["decision"]
                assert o["current_register"] == "docs/budgets/owner_decisions/owner_questions_state_v5.json"
                assert "answered by the owner" in o["handling"]
            else:                       # S-01: only an owner answer to the same question supersedes (OD13, row 3)
                assert o["current_register"] == "docs/budgets/owner_decisions/owner_questions_state_v4.json"
                assert (r["id"], o["id"]) == ("RVM-12", "OD13") and o["superseded_by"]["owner_row"] == 3
    demands = {d["id"]: d for d in doc["interface_demands"]}
    for dem in ("RVM-ID-08", "RVM-ID-10", "RVM-ID-11"):    # S-01 / PHYS-01: consumed downstream, never PENDING
        assert demands[dem]["status"] == "CONSUMED" and "PENDING" not in json.dumps(demands[dem])
    assert "PENDING fo_a9_6_" not in json.dumps(doc)
    with pytest.raises(B.BuildError):   # an ANSWERED question cannot be carried as open
        B.oq(ctx, "OD1")
    assert [q["id"] for q in doc["open_owner_questions"]] == ["RVMQ-01"]
    # A9.14 RVMQ-01 (S9.13); A9.16 repair COR-01: 'status' keeps the as-raised value read back by the immutable
    # state-v4 builder, status_current governs (updated test)
    assert doc["open_owner_questions"][0]["status_current"] == "OWNER_DECIDED"
    assert doc["open_owner_questions"][0]["status"] == "TBD_OWNER"
    assert doc["open_owner_questions"][0]["status_when_raised"] == "TBD_OWNER"


# ------------------------------------------------------------------------------------------ sections / hygiene
def test_sections_present(doc):
    for k in ("items", "interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
              "m16_impact"):
        assert doc[k], k
    for it in doc["items"]:
        for f in ("id", "value", "units", "basis", "source", "evidence_class", "status", "freeze_point"):
            assert f in it
        assert it["freeze_point"] in B.FREEZE_POINTS
    dirs = [d["direction"] for d in doc["interface_demands"]]
    assert any(d.startswith("RVM <-") for d in dirs) and any(d.startswith("RVM ->") for d in dirs)
    for o in doc["owner_answers_applied"]:
        ans = json.loads((REPO / B.PINS["ANS"][0]).read_text(encoding="utf-8"))
        v = next(a for a in ans["answers"] if a["row"] == o["row"])["owner_answer_verbatim"]
        assert hashlib.sha256(v.encode("utf-8")).hexdigest() == o["answer_sha256"] and o["owner_answer_verbatim"] == v
    for m in doc["m16_impact"]:
        assert m["state_change"].startswith("none")


def test_fixed_statuses_carried_unchanged(doc):
    fs = doc["a9_6_fixed_statuses_carried"]
    assert fs["316L_FLIGHT_ANODE"] == "REJECTED_AS_CURRENT_BASELINE"
    assert fs["FINAL_ANODE_MATERIAL"] == "OPEN"
    assert fs["ANODE_THERMAL_CLOSURE"] == "UNRESOLVED" and fs["ICP_COUPLED_THERMAL"] == "UNRESOLVED"
    assert fs["RF_COMPONENT_RATINGS"] == "TBD_AFTER_IMPEDANCE_MAP"
    assert doc["a9_2_statuses_carried"]["C1 conventional reference"] == "CONTROL_FALLBACK"


def test_no_forbidden_substrings():
    for p in list(LANE.glob("*.py")) + [OUT_JSON, OUT_MD, Path(__file__)]:
        text = p.read_text(encoding="utf-8")
        assert "xe_" + "ledger" not in text, p
    for p in LANE.glob("*.py"):   # no screening candidate is used as a source (the JSON only cites the v1 release)
        assert "sgb-" + "screen" not in p.read_text(encoding="utf-8"), p



def test_rvm14_od5_atmospheric_sequence_has_no_c1_dwell_number(doc):
    """A9.16 repair F3: OD5 (S9.9) limits the ICP-first atmospheric start only by registered dwell / thermal limits
    (values from the actual hardware, A9.10 P1Q-02); the 120 s / 360 s numbers are the C1 ignition-dwell Xe booking of
    S9.1 XA9Q-02 / S8.15 OQ-A907-01 and appear only for the C1-selected variant."""
    r = {x["id"]: x for x in doc["rows"]}["RVM-14"]["a9_16"]
    assert "registered dwell / thermal limits" in r["attempts"] and "P1Q-02" in r["attempts"]
    assert "120 s" not in r["attempts"] and "360 s" not in r["attempts"]
    assert "120 s" in r["c1_variant"] and "360 s" in r["c1_variant"] and "C1 variant only" in r["c1_variant"]
