"""A9.16 step 1 - owner rules applied to the P3 coupled-thermal package (docs/experiments/hall_icp/p3_coupled_thermal/
p3_a9_16_rules.py, a9_16_application.py): A9.8 P3Q-01; A9.12 ICPQ-10, OQ-A907-03, OQ-A907-05, OQ-A907-06, OQ-A907-08,
OQ-A907-09, OQ-A907-10, OQ-A910-06, P3Q-02; A9.14 ICPQ-03 / ICPQ-09; A9.15 reviewed.

Every numeric input here is SYNTHETIC_TEST_DATA_NOT_EVIDENCE (rule checks, not results).
Run: python -m pytest -q tests/test_p3_a9_16_owner_rules.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "experiments" / "hall_icp" / "p3_coupled_thermal"
OUT_JSON = LANE / "p3_coupled_thermal_v1.json"
SYN = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def R():
    return _load("p3_a9_16_rules_under_test", LANE / "p3_a9_16_rules.py")


@pytest.fixture(scope="module")
def APP():
    return _load("p3_a9_16_app_under_test", LANE / "a9_16_application.py")


@pytest.fixture(scope="module")
def d():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


def W(v, src=SYN, **kw):
    return dict({"value": v, "units": "W", "source": src}, **kw)


def _cal(R, **over):
    rec = {"route": "CALORIMETRIC_ENERGY_BALANCE", "Q_collector_W": 12.0, "u_W": 1.0, "units": "W", "source": SYN}
    rec.update({k: "REG-" + k for k in R.CALORIMETRY_ELEMENTS})
    rec.update(over)
    return rec


# ------------------------------------------------------------------------------------------------ decision pins
def test_p3_a9_16_decision_pins_and_rows(APP, d):
    for k, (j, js, m, ms) in APP.DEC.items():
        assert hashlib.sha256((REPO / j).read_bytes()).hexdigest() == js, j
        assert hashlib.sha256((REPO / m).read_bytes()).hexdigest() == ms, m
    rows = [r for r in d["owner_answers_applied"] if r.get("step") == "A9.16 step 1"]
    got = {(r["kind"], r["decision"]) for r in rows}
    for need in [("A9.8", "P3Q-01")] + [("A9.12", q) for q in (
            "ICPQ-10", "OQ-A907-03", "OQ-A907-05", "OQ-A907-06", "OQ-A907-08", "OQ-A907-09", "OQ-A907-10",
            "OQ-A910-06", "P3Q-02")]:
        assert need in got, need
    for r in rows:
        assert r["sha256"] == APP.DEC[r["kind"]][1] and r["verbatim_sha256"] == APP.DEC[r["kind"]][3]
        # answer codes match the machine-readable decision records
        decs = json.loads((REPO / r["path"]).read_text()).get("decisions", {})
        if r["kind"] != "A9.15":
            assert decs[r["decision"]]["answer"] == r["answer"], r["decision"]
    # every test named in the record exists in this file
    src = Path(__file__).read_text(encoding="utf-8")
    for r in rows:
        for t in r["tests"]:
            assert f"def {t.split(' ')[0]}(" in src, t
    pinned = {p["path"] for p in d["decision_pins"]}
    for k, (j, _, m, _) in APP.DEC.items():
        assert j in pinned and m in pinned


# ------------------------------------------------------------------------------------------------ A9.8 P3Q-01
def test_p3_a9_16_q_collector_calorimetry_primary(R):
    out = R.q_collector_evidence(_cal(R))
    assert out["primary_route"] == "CALORIMETRIC_ENERGY_BALANCE" and out["status"] == "COMPUTED_CONDITIONAL"
    for el in R.CALORIMETRY_ELEMENTS:          # every calorimetric element must be registered
        with pytest.raises(R.RuleRefusal) as e:
            R.q_collector_evidence(_cal(R, **{el: None}))
        assert e.value.code == "INCOMPLETE_EVIDENCE"
    probe = {"route": "PROBE_SHEATH_MODEL", "Q_collector_W": 11.0, "u_W": 2.0, "units": "W", "source": SYN}
    with pytest.raises(R.RuleRefusal) as e:   # probe never primary
        R.q_collector_evidence(None, probe)
    assert e.value.code == "PROBE_ROUTE_IS_CROSS_CHECK_ONLY"
    with pytest.raises(R.RuleRefusal) as e:
        R.q_collector_evidence(dict(probe))
    assert e.value.code == "PROBE_ROUTE_IS_CROSS_CHECK_ONLY"
    with pytest.raises(R.RuleRefusal):
        R.q_collector_evidence(None)
    out = R.q_collector_evidence(_cal(R), dict(probe, matched_diagnostic_run=False))
    assert out["Q_collector_W"] == 12.0 and out["cross_check_matched_diagnostic_run"] is False
    assert "never used to replace" in out["cross_check_note"]


def test_p3_a9_16_probe_cross_check_criterion_slot(R):
    prim = R.q_collector_evidence(_cal(R))
    probe = {"Q_collector_W": 20.0, "u_W": 2.0}
    for crit in (None, {"k": 2.0, "source": SYN}, {"k": 2.0, "registered_before_data": True}):
        with pytest.raises(R.RuleRefusal) as e:
            R.q_collector_cross_check(prim, probe, crit)
        assert e.value.code == "NOT_EVALUATED_CROSS_CHECK_CRITERION_TBD"
    crit = {"k": 2.0, "source": SYN, "registered_before_data": True}
    out = R.q_collector_cross_check(prim, probe, crit)
    assert out["agreement"] == "SHEATH_MODEL_DISAGREEMENT" and out["Q_collector_governing_W"] == 12.0
    out = R.q_collector_cross_check(prim, {"Q_collector_W": 13.0, "u_W": 2.0}, crit)
    assert out["agreement"] == "AGREEMENT" and out["governing_route"] == "CALORIMETRIC_ENERGY_BALANCE"


def test_p3_a9_16_icp45_probe_contamination_refused(R):
    assert R.icp45_record_probe_admissibility({"probe_present": False})["icp45_record_admissible_wrt_probe"]
    with pytest.raises(R.RuleRefusal) as e:
        R.icp45_record_probe_admissibility({"probe_present": True})
    assert e.value.code == "PROBE_PERTURBATION_NOT_SHOWN_NEGLIGIBLE"
    with pytest.raises(R.RuleRefusal):
        R.icp45_record_probe_admissibility({})
    ok = R.icp45_record_probe_admissibility({"probe_present": True, "perturbation_negligible_evidence": "REC-X"})
    assert ok["icp45_record_admissible_wrt_probe"]


# ------------------------------------------------------------------------------------------------ A9.12 ICPQ-10
def test_p3_a9_16_icp43_bound_rule(R):
    out = R.icp43_total_module_bound(W(400.0, registration="P2-ENV-SYN"), W(900.0, registration="H1-PD-SYN"))
    assert out["Q_ICP_bound_W"] == pytest.approx(1.2 * 1300.0) and out["margin"] == 1.2
    assert out["status"] == "COMPUTED_CONDITIONAL" and "not a statement" in out["note"]


def test_p3_a9_16_icp43_refuses_bus_ceiling_and_missing(R):
    good = W(900.0, registration="H1-PD-SYN")
    for bad in (None, W("TBD_AFTER_IMPEDANCE_MAP", registration="X"), W(400.0)):  # missing / TBD / unregistered
        with pytest.raises(R.RuleRefusal) as e:
            R.icp43_total_module_bound(bad, good)
        assert e.value.code == "INCOMPLETE_EVIDENCE"
    with pytest.raises(R.RuleRefusal) as e:
        R.icp43_total_module_bound(W(400.0, registration="E"), W(1500.0, registration="BUS", basis="BUS_CEILING"))
    assert e.value.code == "OWNER_RULE_VIOLATION"
    with pytest.raises(R.RuleRefusal) as e:
        R.icp43_total_module_bound(W(400.0, registration="E"), good, margin=1.0)
    assert e.value.code == "OWNER_RULE_VIOLATION"


def test_p3_a9_16_icp43_measured_terms_keep_margin(R):
    terms = {"Q_RF_match": W(300.0, evidence_class="measured"), "Q_collector": W(50.0, evidence_class="measured")}
    out = R.icp43_total_module_bound(None, None, measured_coupled_terms=terms)
    assert out["basis"] == "MEASURED_COUPLED_HEAT_TERMS" and out["Q_ICP_bound_W"] == pytest.approx(420.0)
    with pytest.raises(R.RuleRefusal):
        R.icp43_total_module_bound(None, None, measured_coupled_terms={"x": W(1.0, evidence_class="assumed")})
    with pytest.raises(R.RuleRefusal):
        R.icp43_total_module_bound(None, None, margin=1.1, measured_coupled_terms=terms)


def test_p3_a9_16_registered_inputs_refused(d):
    a = d["a9_16_owner_rules"]
    assert a["icp43_bound"]["registered_evaluation"]["status"] == "INCOMPLETE_EVIDENCE"
    assert a["q_collector_evidence"]["registered_evaluation"]["status"] == "INCOMPLETE_EVIDENCE"
    assert a["bounding_corners"]["registered_evaluation"]["status"] == "NOT_EVALUATED_ADMISSIBILITY_TBD"
    assert a["search_sensitive"]["registered_evaluation"]["status"] == "NOT_EVALUATED_SEARCH_ALLOWANCE_TBD"
    assert a["rf_allocation"]["registered_total"]["status"] == "INCOMPLETE_EVIDENCE"
    assert a["model_class"]["registered_evaluation"]["status"] == "NOT_EVALUATED_CORRELATION_PLAN_TBD"
    assert a["node_limits"]["coating_node"]["limit_state"] == "OPEN_COATING_LIMIT_NOT_SOURCED"
    items = {i["id"]: i for i in d["items"]}
    assert items["P3-B-02"]["status"] == "OWNER_REJECTED"
    for i in ("P3-A-01", "P3-C-01", "P3-C-02", "P3-C-03", "P3-C-04", "P3-C-05", "P3-M-07"):
        assert items[i]["status"] == "TBD" and items[i]["evidence_class"] is None
    assert d["closure_statuses"]["ICP_COUPLED_THERMAL"] == "UNRESOLVED"
    assert d["closure_statuses"]["ANODE_THERMAL_CLOSURE"] == "UNRESOLVED"


# ------------------------------------------------------------------------------------------------ A9.12 OQ-A907-03
def test_p3_a9_16_admissible_corners(R):
    factors = {"env": ("HOT", "COLD"), "rf": ("RF_ON_MAX",), "hall": ("HALL_ON", "HALL_OFF")}
    with pytest.raises(R.RuleRefusal) as e:
        R.admissible_corners(factors, {"source": SYN, "exclusions": []})   # not registered before evaluation
    assert e.value.code == "NOT_EVALUATED_ADMISSIBILITY_TBD"
    decl = {"registered_before_evaluation": True, "source": SYN, "exclusions": [
        {"when": {"env": "COLD", "hall": "HALL_ON"}, "reason": "KNOWN_CORRELATED_EXTREMES", "source": SYN}]}
    adm, exc = R.admissible_corners(factors, decl)
    assert len(adm) + len(exc) == 4 and len(exc) == 1
    assert exc[0]["corner"] == {"env": "COLD", "hall": "HALL_ON", "rf": "RF_ON_MAX"}
    for bad in ({"when": {"env": "COLD"}, "reason": "CONVENIENT", "source": SYN},
                {"when": {"env": "COLD"}, "reason": "MUTUALLY_EXCLUSIVE_STATES"},
                {"when": {"env": "WARM"}, "reason": "MUTUALLY_EXCLUSIVE_STATES", "source": SYN}):
        with pytest.raises(R.RuleRefusal):
            R.admissible_corners(factors, dict(decl, exclusions=[bad]))


def test_p3_a9_16_bounding_case_every_node(R):
    case = {"corner": {"env": "HOT"}, "dissipated_margin_applied": 1.2, "environment_boundary": "HOT"}
    limits = {"A": {"node": "A", "limit_class": "T_VALIDATED_CONTINUOUS", "T_limit_C": 500.0, "source": SYN,
                    "validation_evidence": SYN},
              "B": {"node": "B", "limit_class": "SUPPLIER_PROVISIONAL", "T_limit_C": 900.0, "source": SYN}}
    out = R.bounding_case_evaluation(case, ["A", "B"], {"A": 440.0, "B": 860.0}, limits)
    cls = {r["node"]: r["margin_class"] for r in out["nodes"]}
    assert cls["A"] == "MARGIN_MET_CONDITIONAL"
    assert cls["B"] == "UNRESOLVED_CONDITIONAL_ON_PROVISIONAL_LIMIT_MARGIN_NOT_MET"
    assert out["closure"] == "UNRESOLVED"
    with pytest.raises(R.RuleRefusal):   # every temperature-limited node must be evaluated
        R.bounding_case_evaluation(case, ["A", "B"], {"A": 440.0}, limits)
    with pytest.raises(R.RuleRefusal):
        R.bounding_case_evaluation(dict(case, dissipated_margin_applied=1.0), ["A"], {"A": 1.0}, limits)
    with pytest.raises(R.RuleRefusal):
        R.bounding_case_evaluation(dict(case, environment_boundary=None), ["A"], {"A": 1.0}, limits)
    with pytest.raises(R.RuleRefusal):   # 50 K never relaxed
        R.node_margin(400.0, R.node_limit(limits["A"]), margin_K=30.0)


# ------------------------------------------------------------------------------------------------ A9.12 OQ-A907-05 / 08
def test_p3_a9_16_provisional_supplier_limits(R):
    lim = R.node_limit({"node": "BN", "limit_class": "SUPPLIER_PROVISIONAL", "T_limit_C": 900.0, "source": SYN})
    assert lim["limit_state"] == "PROVISIONAL_SUPPLIER_RATING"
    for use in R.PROVISIONAL_ALLOWED_USES:
        assert R.limit_use_check(lim, use)
    for use in R.CLOSURE_USES:
        with pytest.raises(R.RuleRefusal) as e:
            R.limit_use_check(lim, use)
        assert e.value.code == "UNRESOLVED_PROVISIONAL_OR_OPEN_LIMIT"
    assert R.node_margin(100.0, lim)["margin_class"] == "UNRESOLVED_CONDITIONAL_ON_PROVISIONAL_LIMIT"
    with pytest.raises(R.RuleRefusal):   # a validated limit needs validation evidence
        R.node_limit({"node": "X", "limit_class": "T_VALIDATED_CONTINUOUS", "T_limit_C": 900.0, "source": SYN})


def test_p3_a9_16_coating_node_open(R):
    for cs in (None, {"coating": "Z-93-class"}, {"coating": "Z-93-class", "substrate": "Al"}):
        lim = R.node_limit({"node": "COAT", "is_coating": True, "coating_system": cs, "T_limit_C": 400.0,
                            "limit_class": "T_VALIDATED_CONTINUOUS", "source": SYN, "validation_evidence": SYN})
        assert lim["limit_state"] == "OPEN_COATING_LIMIT_NOT_SOURCED"
        assert R.node_margin(100.0, lim)["margin_class"] == "UNRESOLVED_LIMIT_OPEN"
        with pytest.raises(R.RuleRefusal):
            R.limit_use_check(lim, "lock1_thermal_closure")
    full = {"coating": "SYN-COAT", "substrate": "SYN-SUB", "application": "SYN-PROC"}
    lim = R.node_limit({"node": "COAT", "is_coating": True, "coating_system": full, "T_limit_C": 400.0,
                        "limit_class": "T_VALIDATED_CONTINUOUS", "source": SYN, "validation_evidence": SYN})
    assert R.node_margin(360.0, lim)["margin_class"] == "MARGIN_NOT_MET"          # ceiling 400 - 50 = 350 degC
    assert R.node_margin(350.0, lim)["margin_class"] == "MARGIN_MET_CONDITIONAL"


# ------------------------------------------------------------------------------------------------ A9.12 OQ-A907-09
def test_p3_a9_16_margin_dissipated_only(R):
    out = R.apply_heat_load_margin([W(100.0, name="coil", category="coil"),
                                    W(50.0, name="sun", category="solar", envelope_case="HOT-SYN")])
    by = {o["name"]: o for o in out}
    assert by["coil"]["design_W"] == pytest.approx(120.0) and by["sun"]["design_W"] == 50.0
    for bad in ([W(50.0, name="sun", category="solar", envelope_case="HOT", apply_margin=True)],
                [W(50.0, name="sun", category="solar")],
                [W(10.0, name="mystery", category=None)]):
        with pytest.raises(R.RuleRefusal):
            R.apply_heat_load_margin(bad)
    with pytest.raises(R.RuleRefusal):
        R.apply_heat_load_margin([W(1.0, name="coil", category="coil")], margin=1.3)
    enl = R.apply_heat_load_margin([W(60.0, name="olr", category="outgoing_ir", envelope_case="HOT",
                                      enlarged_bound_source="SYN-ENLARGE")])
    assert "explicitly enlarged" in enl[0]["treatment"]


# ------------------------------------------------------------------------------------------------ A9.12 OQ-A907-06
def test_p3_a9_16_mount_heat_allocations(R):
    assert R.MOUNT_HEAT_ALLOCATION_W == {"stretch": 25.0, "governing_provisional": 50.0,
                                         "contingency_sensitivity": 100.0}
    r = R.mount_heat_report(80.0)
    assert r["classification"] == "ONLY_WITHIN_100W_CONTINGENCY_NOT_CLOSED" and r["governing_W"] == 50.0
    assert set(r["sensitivity_cases"]) == {"stretch", "governing_provisional", "contingency_sensitivity"}
    assert "not a claimed spacecraft requirement" in r["label"]
    assert R.mount_heat_report(40.0)["classification"] == "WITHIN_GOVERNING_ALLOCATION_CONDITIONAL"
    assert R.mount_heat_report(120.0)["classification"] == "EXCEEDS_100W_CONTINGENCY"
    icd = R.mount_heat_report(40.0, spacecraft_icd=W(30.0))
    assert icd["governing_source"] == "SPACECRAFT_THERMAL_ICD" and icd["classification"] != \
        "WITHIN_GOVERNING_ALLOCATION_CONDITIONAL"
    with pytest.raises(R.RuleRefusal):
        R.mount_heat_report(-1.0)


# ------------------------------------------------------------------------------------------------ A9.12 OQ-A907-10
def test_p3_a9_16_search_sensitive_label_only(R):
    allow = {"value_K": 5.0, "registered_before_outcome": True, "source": SYN}
    r = R.search_sensitivity("COMPUTED_CONDITIONAL", 7.0, allow)
    assert r["labels"] == ["SEARCH_SENSITIVE"] and r["status"] == "COMPUTED_CONDITIONAL"
    assert R.search_sensitivity("COMPUTED_CONDITIONAL", 10.0, allow)["labels"] == []
    with pytest.raises(R.RuleRefusal) as e:
        R.search_sensitivity("COMPUTED_CONDITIONAL", 7.0, {"value_K": 5.0, "source": SYN})
    assert e.value.code == "NOT_EVALUATED_SEARCH_ALLOWANCE_TBD"


def test_p3_a9_16_search_sensitive_needs_independent_bound(R):
    allow = {"value_K": 5.0, "registered_before_outcome": True, "source": SYN}
    lab = R.search_sensitivity("COMPUTED_CONDITIONAL", 7.0, allow)
    with pytest.raises(R.RuleRefusal) as e:
        R.lock1_use_of_search_result(lab)
    assert e.value.code == "NOT_EVALUATED_INDEPENDENT_BOUND_REQUIRED"
    with pytest.raises(R.RuleRefusal):
        R.lock1_use_of_search_result(lab, {"method": "local_search", "source": SYN, "margin_K": 3.0})
    out = R.lock1_use_of_search_result(lab, {"method": "interval_bounding_analysis", "source": SYN, "margin_K": 3.0})
    assert out["governing_margin_K"] == 3.0 and out["governing_source"] == "independent_bound"
    out = R.lock1_use_of_search_result(lab, {"method": "global_optimization", "source": SYN, "margin_K": 9.0})
    assert out["governing_margin_K"] == 7.0
    with pytest.raises(R.RuleRefusal) as e:   # allowance never increased after the outcome
        R.lock1_use_of_search_result(lab, allowance_used_K=8.0, allowance=allow)
    assert e.value.code == "OWNER_RULE_VIOLATION"


# ------------------------------------------------------------------------------------------------ A9.12 OQ-A910-06
def test_p3_a9_16_rf_allocation_600w_labels(R, d):
    rec = R.rf_allocation_record()
    assert rec["Q_RF_allocation_W"] == 600.0 == R.RF_ALLOCATION_BASE_W * R.HEAT_LOAD_MARGIN
    assert len(rec["labels"]) == 4 and all(x.startswith("not ") for x in rec["labels"])
    with pytest.raises(R.RuleRefusal):        # P_line/match,loss additional: total refused without it
        R.rf_thermal_basis()
    out = R.rf_thermal_basis(P_line_match_loss=W(30.0))
    assert out["Q_RF_thermal_W"] == pytest.approx(630.0)
    for use in R.RF_ALLOCATION_FORBIDDEN_USES:
        with pytest.raises(R.RuleRefusal) as e:
            R.rf_thermal_basis(P_line_match_loss=W(30.0), use=use)
        assert e.value.code == "OWNER_RULE_VIOLATION"
    b3 = [i for i in d["items"] if i["id"] == "P3-B-03"][0]
    assert b3["value"] == 600.0 and b3["status"] == "OWNER_GIVEN" and "not a component rating" in b3["note"]


def test_p3_a9_16_rf_allocation_superseded_by_p2(R):
    env = {k: {"upper_bound_incl_uncertainty_W": v, "status": "VERIFIED", "source": SYN, "uncertainty_basis": SYN}
           for k, v in (("P_delivered", 400.0), ("line_match_loss", 40.0), ("antenna_plasma_loading", 0.0))}
    out = R.rf_thermal_basis(env)
    assert out["basis"] == "P2_DERIVED_RF_THERMAL_ENVELOPE" and out["allocation_600W"] == "SUPERSEDED"
    assert out["Q_RF_thermal_W"] == pytest.approx(1.2 * 440.0)
    bad = json.loads(json.dumps(env))
    bad["line_match_loss"]["status"] = "UNVERIFIED"
    with pytest.raises(R.RuleRefusal):
        R.rf_thermal_basis(bad)
    bad = {k: v for k, v in env.items() if k != "antenna_plasma_loading"}
    with pytest.raises(R.RuleRefusal):
        R.rf_thermal_basis(bad)


# ------------------------------------------------------------------------------------------------ A9.12 P3Q-02
def _plan(**over):
    p = {"sensor_locations": ["TC-SYN-1"], "measurement_uncertainty": {"TC-SYN-1": 1.0},
         "comparison_quantities": ["T_A", "T_B"], "residual_band": {"abs_K": 5.0},
         "sensor_placement_contact_treatment": "SYN", "registered_before_correlation_data": True}
    p.update(over)
    return p


def test_p3_a9_16_correlation_plan_slots(R):
    assert R.correlation_plan_check(_plan())["model_class"] == R.MODEL_CLASS_A
    for slot in R.CORRELATION_PLAN_SLOTS:
        with pytest.raises(R.RuleRefusal) as e:
            R.correlation_plan_check(_plan(**{slot: None}))
        assert e.value.code == "NOT_EVALUATED_CORRELATION_PLAN_TBD"
    for over in ({"registered_before_correlation_data": False}, {"residual_band": "TBD"},
                 {"residual_band": {"abs_K": 0}}):
        with pytest.raises(R.RuleRefusal):
            R.correlation_plan_check(_plan(**over))


def test_p3_a9_16_correlation_escalation(R):
    ok = R.correlation_outcome(_plan(), {"T_A": 2.0, "T_B": -4.0}, False)
    assert ok["outcome"] == "CORRELATED_WITHIN_REGISTERED_BAND"
    out = R.correlation_outcome(_plan(), {"T_A": 2.0, "T_B": -6.0}, False)
    assert out["outcome"] == "ESCALATE_TO_FINER_MODEL_MANDATORY" and out["outside_band"] == ["T_B"]
    assert out["lock1_thermal_closure_with_model_class_A"] == "BLOCKED"
    hs = R.correlation_outcome(_plan(), {"T_A": 0.0, "T_B": 0.0}, True)
    assert hs["outcome"] == "ESCALATE_TO_FINER_MODEL_MANDATORY"
    with pytest.raises(R.RuleRefusal):
        R.correlation_outcome(_plan(), {"T_A": 0.0}, False)        # every comparison quantity needs a residual
    with pytest.raises(R.RuleRefusal):
        R.correlation_outcome(_plan(), {"T_A": 0.0, "T_B": 0.0}, None)


# ------------------------------------------------------------------------------------------------ A9.14 / A9.15
def test_p3_a9_16_carried_questions_answered(d):
    c = d["existing_open_owner_questions_carried"]
    assert c["ICPQ-03"]["answer"] == "YES_BOTH_MODULES_ON_MOVING_PLATFORM"
    assert c["ICPQ-09"]["answer"] == "PLUME_INTERCEPTION_INSIDE_SYSTEM_BOUNDARY"
    k02 = [i for i in d["items"] if i["id"] == "P3-K-02"][0]
    assert "moving thrust platform" in k02["value"] and "A9.14 ICPQ-03" in k02["source"]
    assert d["heat_terms"]["Q_plume"]["function"]


def test_p3_a9_16_no_xe_contingency_text():
    """A9.15: no 'Xe contingency-only' wording anywhere in the package, except the A9.15 review record itself."""
    for p in list(LANE.glob("*.py")) + list(LANE.glob("*.json")) + list(LANE.glob("*.md")):
        if p.name == "a9_16_application.py":
            continue   # records the A9.15 review itself
        if p.suffix == ".json":
            doc = json.loads(p.read_text(encoding="utf-8"))
            doc["owner_answers_applied"] = [r for r in doc["owner_answers_applied"] if r.get("kind") != "A9.15"]
            t = json.dumps(doc).lower()
        else:
            t = "\n".join(x for x in p.read_text(encoding="utf-8").splitlines() if "A9.15" not in x).lower()
        assert "contingency-only" not in t and "xe contingency" not in t, p.name


def test_p3_a9_16_no_pass_and_out_of_lane_listed(d):
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k, v
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)
    for k, v in walk(d["a9_16_owner_rules"]):
        if isinstance(v, str) and ("status" in str(k).lower() or "class" in str(k).lower()):
            assert "PASS" not in v.upper().split("_"), (k, v)
    paths = " ".join(o["path"] for o in d["a9_16_owner_rules"]["out_of_lane"])
    assert "docs/hardware/h2_a9_revisions/" in paths and "p1_icp_bench" in paths
