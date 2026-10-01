"""A9.16 step 1 integration lane: focused tests of every rule applied from owner decisions A9.8 .. A9.15 to the
integration artifacts (H-1 / F9 freeze candidates, F6, RVM, M16 v4) and of the A9.16 application matrix.

Refusal paths are tested explicitly (fail-closed rules). Owner-supplied numbers only (754 degC, 0.05, 50 / 100 / 25 W,
4.2048 / 6.0 / 6.0528 kg, 75 / 80 / 80 / 60 / 70 %)."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))
import a9_16_lib as L  # noqa: E402


def _mod(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


H1 = _mod("docs/hardware/h1_freeze_candidate/a9_16_h1.py", "a916_h1")
F9 = _mod("docs/architecture/freeze_candidate/a9_16_f9.py", "a916_f9")
F6 = _mod("docs/design_synthesis/f6_icp_geometry/a9_16_f6.py", "a916_f6")
RV = _mod("docs/requirements/rvm_a9/a9_16_rvm.py", "a916_rvm")
M16 = _mod("docs/experiments/hall_icp/integration/m16_v4/a9_16_m16.py", "a916_m16")


def _j(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


H1DOC = _j("docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json")
F9DOC = _j("docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json")
F6DOC = _j("docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json")
RVMDOC = _j("docs/requirements/rvm_a9/rvm_a9_v1.json")
M16DOC = _j("docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json")
V5 = _j("docs/budgets/owner_decisions/owner_questions_state_v5.json")


# ------------------------------------------------------------------------------------------------ shared library
def test_decision_pins_and_verbatim_sections():
    for k in L.ORDER:
        d = L.LOADED[k]
        assert d["json_sha256"] == L.sha256_file(d["json"]) and d["md_sha256"] == L.sha256_file(d["md"])
        for q in L.decision_ids(k):
            assert L.verbatim(k, q) in d["md_text"]
    assert L.decision_key_of("F5-OQ-03") == "A9.14" and L.decision_key_of("P1Q-04") == "A9.8"
    with pytest.raises(SystemExit):
        L.decision_key_of("NOT-AN-ID")


def test_cite_carries_path_sha_and_question_id():
    c = L.cite("ICPQ-11")
    assert "A9.14 ICPQ-11" in c and L.LOADED["A9.14"]["json_sha256"] in c and L.LOADED["A9.14"]["json"] in c
    c = L.cite("XA9Q-07")
    assert "amended by A9.15" in c and L.LOADED["A9.15"]["json_sha256"] in c


def test_xe_contingency_detector():
    assert L.has_xe_contingency_wording("Xe remains contingency-only for the C1 electron source")
    assert not L.has_xe_contingency_wording("deferred until C1 is selected, but not because Xe is contingency-only")


def test_no_xe_contingency_reading_in_integration_artifacts():
    """A9.15 governs: no integration artifact states 'Xe contingency-only for C1' as a live reading (superseded
    statements in state v5 are quoted as superseded)."""
    for doc in (H1DOC, F9DOC, F6DOC, RVMDOC, M16DOC):
        txt = json.dumps(doc, ensure_ascii=False)
        txt = txt.replace("'Xe contingency-only for C1'", "")
        assert not L.has_xe_contingency_wording(txt)
    for r in V5["rows"]:
        if r.get("governing_reading"):
            assert not L.has_xe_contingency_wording(r["governing_reading"]["text"])


# ------------------------------------------------------------------------------------------------ H-1 (F5)
def test_h1_rows_follow_owner_decisions():
    by = {p["id"]: p for p in H1DOC["parameters"]}
    assert by["H1F-CH-11"]["freeze_status"] == "TBD_AFTER_EVIDENCE"
    assert by["H1F-CH-11"]["a9_16"]["status_when_selected"] == "ENGINEERING_FREEZE_CANDIDATE"
    assert by["H1F-MA-04"]["a9_16"]["necessary_curie_ceiling_C"] == 754
    assert by["H1F-MA-04"]["a9_16"]["role"] == "NECESSARY_CEILING_NOT_USABLE_LIMIT"
    assert by["H1F-MA-04"]["freeze_status"] == "TBD_AFTER_EVIDENCE"      # usable limit still needs B_sat(T)
    assert by["H1F-CO-08"]["freeze_status"] == "FREEZE_CANDIDATE" and by["H1F-CO-08"]["value"].startswith("plain")
    assert by["H1F-BZ-03"]["a9_16"]["role"] == "FEMM_MAGNETIC_DESIGN_TARGET_BAND_NOT_TRANSPORT_OPTIMUM"
    assert by["H1F-TH-02"]["a9_16"]["mount_heat_allocation_W"] == {"governing_provisional": 50,
                                                                    "contingency_sensitivity_ceiling": 100, "stretch": 25}
    assert by["H1F-MA-06"]["a9_16"]["coating_limit_status"] == "OPEN_COATING_LIMIT_NOT_SOURCED"
    assert by["H1F-CO-11"]["a9_16"]["limit_class"] == "SUPPLIER_PROVISIONAL"
    for q in H1DOC["open_owner_questions"]:
        assert q["status"] == "OWNER_DECIDED" and q["status_when_raised"] == "TBD_OWNER"


def test_h1_femm_points_authorised_not_run():
    fp = H1DOC["femm_analysis_points"]
    assert fp["status"] == "FEMM_AUTHORISED_NOT_RUN" and fp["role"] == "ANALYSIS_POINTS_NOT_SELECTION"
    assert fp["results"] == []
    auth = [p for p in fp["points"] if p["authorised_analysis_point"]]
    assert any(p["probe"].startswith("RP-1") for p in auth)
    for p in fp["points"]:
        if p["geometric_status"].get("worst_case_assumptions") != "WITHIN_DECLARED_GEOMETRIC_WINDOWS":
            assert p["femm_status"] == "NOT_AUTHORISED"


def test_h1_lock1_release_fail_closed():
    params = H1DOC["parameters"]
    r = H1.lock1_release_status(params, None)
    assert r["status"] == "RELEASE_BLOCKED" and r["blocker_count"] > 0
    assert set(r["missing_drawing_fields"]) == {"drawing_id", "revision", "content_sha256"}
    assert H1DOC["lock1_release"]["status"] == "RELEASE_BLOCKED"
    fc_only = [dict(p, freeze_status="FREEZE_CANDIDATE") for p in params]
    r = H1.lock1_release_status(fc_only, {"drawing_id": "D", "revision": "A", "content_sha256": "xyz"})
    assert r["status"] == "RELEASE_BLOCKED" and r["missing_drawing_fields"]          # not a sha256
    r = H1.lock1_release_status(fc_only, {"drawing_id": "D", "revision": "A", "content_sha256": "a" * 64})
    assert r["status"] == "RELEASE_BASIS_COMPLETE_PENDING_OWNER_RELEASE"
    assert "PASS" not in json.dumps(r)


# ------------------------------------------------------------------------------------------------ F9
def test_f9_gates_approved_with_determining_evidence_standard():
    gates = {g["id"]: g for g in F9DOC["architecture_gates"]}
    assert len(gates) == 15 and F9DOC["architecture_status"] == "INVESTIGATION_HYPOTHESIS"
    for g in gates.values():
        assert g["owner_approved"]["decision_code"] == "AG_01_15_APPROVED_DETERMINING_EVIDENCE"
        assert g["evidence_sufficient_for_freeze"] is False
    assert gates["AG-12"]["current_status"].startswith("NOT_EVALUATED")
    be = gates["AG-12"]["blocking_evidence"]
    assert be["characterization_coverage_mg_s"] == [0.38, 3.2]
    assert be["characterization_coverage_role"] == "CHARACTERIZATION_COVERAGE_ONLY_NOT_A_PASS_FAIL_REQUIREMENT"
    assert "statewise" in gates["AG-13"]["gate"]
    assert gates["AG-15"]["current_status"].startswith("BLOCKED_RFP_NOT_REGISTERED")
    assert "successor held-out" in gates["AG-03"]["gate"]


def test_f9_gate_closes_refuses_non_determining_evidence():
    for cls in F9.NOT_DETERMINING:
        r = F9.gate_closes("AG-10", [{"class": cls, "source": "x"}])
        assert r["closes"] is False
    assert F9.gate_closes("AG-10", [{"class": "MEASURED_TEST_EVIDENCE", "source": "rec"}])["closes"] is True
    # AG-15 needs the registered official document with provenance and hash
    assert F9.gate_closes("AG-15", [{"class": "OFFICIAL_SOURCE_DOCUMENT_REGISTERED", "source": "s"}])["closes"] is False
    assert F9.gate_closes("AG-15", [{"class": "OFFICIAL_SOURCE_DOCUMENT_REGISTERED", "source": "s", "sha256": "a" * 64,
                                     "provenance": "owner portal"}])["closes"] is True
    r = F9.gate_closes("AG-03", [{"class": "PREREGISTERED_HELD_OUT_PREDICTIVE_VALIDATION_ADMITTING_A_MEMBER",
                                  "source": "s", "rewrites_p5_n2_v1": True}])
    assert r["status"] == "REFUSED_P5_N2_V1_IS_IMMUTABLE"


def test_f9_ag12_feed_state_sufficiency_fail_closed():
    assert F9.ag12_feed_state_sufficiency([], True, fixed_flow_gate_mg_s=0.38)["status"] == "REFUSED_FIXED_MASS_FLOW_GATE"
    assert F9.ag12_feed_state_sufficiency([{"state": "s1"}], False)["status"] == "NOT_EVALUATED"
    full = {"mdot": 1.0, "pressure": 1.0, "temperature": 300.0, "composition": "N2/O", "transient_quality": "WITHIN_H1_TOLERANCE"}
    st = [{"state": "s1", "required": dict(full), "delivered": dict(full, mdot=0.9)}]
    assert F9.ag12_feed_state_sufficiency(st, True)["status"] == "STATEWISE_INSUFFICIENT"
    st[0]["delivered"]["mdot"] = 1.1
    assert F9.ag12_feed_state_sufficiency(st, True)["status"] == "STATEWISE_SUFFICIENT"
    st[0]["delivered"]["pressure"] = None
    assert F9.ag12_feed_state_sufficiency(st, True)["status"] == "NOT_EVALUATED"


def test_f9_ag13_statewise_never_hidden_by_average():
    assert F9.ag13_statewise([{"T_N": 1, "D_N": 0}], False)["status"] == "NOT_EVALUATED"
    r = F9.ag13_statewise([{"T_N": 0.020, "D_N": 0.010}, {"T_N": 0.012, "D_N": 0.013}], True)
    assert r["status"] == "STATEWISE_DEFICIT" and r["orbit_average_margin_N"] > 0 > r["worst_state_margin_N"]
    assert F9.ag13_statewise([{"T_N": None, "D_N": 0.01}], True)["status"] == "NOT_EVALUATED"


def test_f9_records():
    up = F9DOC["upstream_pareto"]
    assert up["representative"]["status"] == "DEFERRED_BY_OWNER" and up["representative"]["selected"] is None
    for m in F9DOC["model_change_candidates"]:
        assert m["status"] == "OWNER_AUTHORISED_PENDING_STEP_2_MODEL_CHANGE" and m["implemented_here"] is False
    m8 = [m for m in F9DOC["model_change_candidates"] if m["id"] == "MCC-08"][0]
    assert m8["owner_authorisation"]["basis_verbatim"] in L.verbatim("A9.9", "F9-OQ-04")
    by = {r["id"]: r for r in F9DOC["parameters"]}
    assert by["AFC-SY-MASS-AL-04"]["value"] == 4.2048 and by["AFC-SY-MASS-AL-07"]["value"] == 6.0
    assert by["AFC-SY-MASS-AL-08"]["value"] == 6.0528
    assert by["AFC-SY-XE-03"]["freeze_status"] == "FREEZE_CANDIDATE"
    assert "RFP-required" in by["AFC-SY-XE-01"]["value"] and "not a contingency" in by["AFC-SY-XE-01"]["value"]
    assert by["AFC-UP-FI-02"]["freeze_status"] == "FREEZE_CANDIDATE"
    assert by["AFC-PR-ICP-05"]["freeze_status"] == "OPEN" and "0.05" in by["AFC-PR-ICP-05"]["value"]
    assert "G-REUSE" in by["AFC-PR-CL-07"]["value"]                         # A9.1 ICP gas mode unchanged
    assert all(q["status"] == "OWNER_DECIDED" for q in F9DOC["open_owner_questions"])
    # A9.16 repair F11: XV3Q-01 (A9.1 HIQ-06 ICP-feed labels vs A9.15) is tracked as an open owner question
    assert F9DOC["owner_question_rollup"]["state_v5"]["open_owner_questions"] == ["MPV3Q-01", "XV3Q-01"]


def test_f9_repair_f8_rollup_status_and_current_xe_sources():
    """A9.16 repair F8: the F9 MD roll-up shows the state-v5 status of every as-raised question (the v4 table is
    historical); the Xe rows cite xe_accounting_a9_v3 / mass_power_a9_v3 / state v5 as current sources; AFC-SY-CTL-01
    records the OD5 sequence as decided and the dwell / thermal limits as pending registration."""
    md = (ROOT / "docs/architecture/freeze_candidate/ARCHITECTURE_FREEZE_CANDIDATE.md").read_text(encoding="utf-8")
    assert "Owner-question roll-up (not answered here)" not in md and "### State v4 TBD_OWNER (" not in md
    assert "### Historical: state v4 TBD_OWNER as raised" in md and "| status (v5) |" in md
    row335 = [ln for ln in md.splitlines() if ln.startswith("| 335 | XV2Q-01 |")][0]
    assert "AMENDED_BY_A9_15" in row335
    by = {r["id"]: r for r in F9DOC["parameters"]}
    for rid in ("AFC-SY-XE-01", "AFC-SY-XE-03", "AFC-SY-XE-04", "AFC-SY-XE-06", "AFC-SY-XE-08"):
        cur = by[rid]["current_sources"]
        assert cur and all(c.startswith(("docs/budgets/xe_accounting_a9_v3/", "docs/budgets/mass_power_a9_v3/",
                                         "docs/budgets/owner_decisions/owner_questions_state_v5.json")) for c in cur), rid
        for x in by[rid]["source"]:
            if isinstance(x, dict) and x["path"].endswith(("xe_accounting_a9_v2.json", "owner_questions_state_v4.json")):
                assert x["role"].startswith("HISTORY"), rid
    ctl = by["AFC-SY-CTL-01"]
    assert ctl["basis"].startswith("SEQUENCE OWNER_DECIDED (A9.14 OD5")
    assert ctl["a9_16"]["dwell_thermal_limits"].startswith("PENDING_REGISTRATION")


# ------------------------------------------------------------------------------------------------ F6
def test_f6_delta_b_acc_rule():
    roi = {"roi_id": "ROI-1", "frozen_utc": "2026-10-02T00:00:00Z", "magnet_states": ["MS-1"]}
    stray = {"ip_exit_T": 1e-3, "icp_volume_max_T": 2e-3}
    assert F6.delta_b_acc(None, [1.0], [1.0], stray)["status"] == "NOT_EVALUATED_ROI_NOT_PREREGISTERED"
    assert F6.delta_b_acc(roi, [1.0, 2.0], [1.02, 2.05], None)["status"] == "NOT_EVALUATED_STRAY_FIELD_NOT_REPORTED"
    assert F6.delta_b_acc(roi, [1.0], [1.0], stray, threshold=0.06)["status"] == "REFUSED_THRESHOLD_RELAXATION"
    r = F6.delta_b_acc(roi, [1.0, 2.0], [1.02, 2.05], stray)
    assert r["status"] == "WITHIN_PROVISIONAL_ALLOCATION" and abs(r["delta_B_acc"] - 0.025) < 1e-12
    assert F6.delta_b_acc(roi, [1.0, 2.0], [1.0, 2.2], stray)["status"] == "EXCEEDS_PROVISIONAL_ALLOCATION"
    assert F6.delta_b_acc(roi, [1.0, 2.0], [1.0, 2.2], stray, threshold=0.04)["status"] == "EXCEEDS_PROVISIONAL_ALLOCATION"
    with pytest.raises(F6.F6A16Error):
        F6.delta_b_acc(roi, [1.0], [1.0, 2.0], stray)
    assert F6DOC["a9_16_owner_decisions"]["hall_b_field_disturbance"]["provisional_max"] == 0.05


def test_f6_geometry_scope_drawing_bounds_and_built_geometries():
    env = {"revision": "B", "bounds": {"R_icp": [10.0, 20.0]}}
    g = {"geometry_id": "G1", "drawing_revision": "B", "variables": {"R_icp": 15.0}, "measured": False}
    assert F6.geometry_scope(g, None, {"G1"})["status"] == "NOT_EVALUATED_REGISTRATION"
    assert F6.geometry_scope(g, env, {"G1"})["status"] == "NOT_YET_MEASURED"
    assert F6.geometry_scope(dict(g, measured=True), env, {"G1"})["status"] == "MEASURED_GEOMETRY"
    assert F6.geometry_scope(g, env, set())["status"] == "OUT_OF_DOMAIN_NOT_IN_REGISTERED_BENCH_MATRIX"
    assert F6.geometry_scope(dict(g, variables={"R_icp": 25.0}), env, {"G1"})["status"] == "REFUSED_OUTSIDE_DRAWING_ENVELOPE"
    assert F6.geometry_scope(dict(g, variables={"L": 1.0}), env, {"G1"})["status"] == "REFUSED_VARIABLE_NOT_BOUNDED_BY_DRAWING"
    assert F6.geometry_scope(dict(g, drawing_revision="A"), env, {"G1"})["status"] == "REFUSED_OTHER_DRAWING_REVISION"
    assert F6.geometry_scope(dict(g, source="SURROGATE"), env, {"G1"})["status"] == "REFUSED_SURROGATE_NOT_VALIDATED"
    assert all(q["status"] == "OWNER_DECIDED" for q in F6DOC["open_owner_questions"])


# ------------------------------------------------------------------------------------------------ RVM
def test_rvm_statewise_envelope_and_ignition_class():
    ge = lambda v: v >= 0
    assert RV.statewise_envelope(None, {}, ge)["status"] == "NOT_EVALUATED_DESIGN_STATES_NOT_REGISTERED"
    assert RV.statewise_envelope(["a", "b"], {"a": 1.0}, ge)["status"] == "NOT_EVALUATED_STATE_MISSING"
    r = RV.statewise_envelope(["a", "b"], {"a": 5.0, "b": -1.0}, ge)
    assert r["status"] == "STATEWISE_VIOLATION" and r["orbit_average_value"] > 0 and r["violating_states"] == ["b"]
    assert RV.statewise_envelope(["a"], {"a": 1.0}, ge)["status"] == "ALL_REQUIRED_STATES_SATISFIED"
    assert RV.ignition_requirement_class(False) == "DERIVED_PROJECT_REQUIREMENT"


def test_rvm_rows_rebased():
    by = {r["id"]: r for r in RVMDOC["rows"]}
    assert by["RVM-14"]["a9_16"]["requirement_class"].startswith("DERIVED_PROJECT_REQUIREMENT")
    assert by["RVM-18"]["a9_16"]["subsystem_targets"] == {"thruster": "> 80 %", "intake": "> 80 %",
                                                          "compressor_storage": "> 60 %", "power_electronics": "> 70 %"}
    assert "DRDO" in by["RVM-18"]["a9_16"]["source_discrepancy"]
    assert "duplicate thrusters" in by["RVM-19"]["a9_16"]["not_required"]
    assert by["RVM-10"]["a9_16"]["air_plus_xe"].startswith("DUAL_PROPELLANT_CAPABILITY")
    assert "never a contingency" in by["RVM-10"]["a9_16"]["air_plus_xe"]
    assert ">= 15,000 h cumulative energized" in by["RVM-12"]["a9_16"]["icp_life_basis"]
    assert "Ignition Time" in by["RVM-12"]["a9_16"]["icp_life_basis"]
    assert by["RVM-01"]["a9_16"]["design_states"].startswith("PENDING_ORBIT_RESOLVED_DATASET_BUILD")
    for r in RVMDOC["rows"]:
        if r["category"].startswith("rfp"):
            assert r["requirement_frozen"] is False                       # AG-15 still open
        for c in r["configurations"].values():
            assert c["status"] != "PASS"
    assert {g["id"] for g in RVMDOC["a9_16_compliance_gates"]} == {"CG-IC", "CG-SPF", "CG-N2-AO"}


# ------------------------------------------------------------------------------------------------ M16
def test_m16_role_map_and_blocker_overlay():
    for r in M16DOC["rows"]:
        assert r["owner"]["owner_question"].startswith("M16-V3-Q-01 (A9.14 S9.4 ACCEPT_ROLE_MAP")
        assert r["execution_state"] != "READY"                     # no named engineer fabricated
        assert not r["owner"].get("named_engineer")
    ans = M16DOC["a9_16_owner_question_blockers_answered_since_v4"]["ids"]
    assert "OD2" in ans and "RVMQ-01" in ans
    idx = M16.v5_index(V5)
    with pytest.raises(ValueError):
        M16.overlay_blockers([{"contributing_blockers": [{"kind": "OWNER_QUESTION", "id": "NOPE"}]}], idx)
    ok, st, reg = M16.reconcile_reading({"id": "OD2", "status": "TBD_OWNER", "current_register": M16.V5}, {}, idx)
    assert ok is False                                     # a decided question cannot be carried as open


# ------------------------------------------------------------------------------------------------ S10.3 (Python canonical)
def test_frozen_and_score_bearing_paths_never_use_rust():
    """A9.14 RUST-OQ-01: frozen datasets, golden / reference rebuilds and score-bearing outputs come from the Python
    reference; no such path imports the Rust backend (abep_sim/design/tpmc_backend.py has no frozen-data path)."""
    for rel in ("abep_sim/intake_tpmc.py", "abep_sim/atmosphere.py", "abep_sim/golden.py", "abep_sim/intake.py",
                "scripts/score_p5_n2_staged.py"):
        p = ROOT / rel
        if p.exists():
            src = p.read_text(encoding="utf-8")
            assert "tpmc_backend" not in src and "abep_core" not in src, rel
    tb = (ROOT / "abep_sim/design/tpmc_backend.py").read_text(encoding="utf-8")
    assert 'DEFAULT_BACKEND = "python"' in tb


# ------------------------------------------------------------------------------------------------ application matrix
MX = _mod("docs/decisions/application/build_a9_16_application_matrix.py", "a916_matrix")
MXDOC = MX.build()


def test_matrix_outputs_current():
    for path, text in MX.outputs(MXDOC).items():
        assert path.read_text(encoding="utf-8") == text, path.name


def test_matrix_covers_every_decision_id_once():
    ids = [(e["decision"], e["question_id"]) for e in MXDOC["entries"]]
    assert len(ids) == len(set(ids))
    want = {(k, q) for k in L.ORDER if k != "A9.15" for q in L.decision_ids(k)} | {("A9.15", "A9.15 governing_rule")}
    later = {("A9.17", q) for q in ("WINDS", "ORBIT", "DATA_SIZE", "SPUTTER", "RFP", "PERF")} | \
        {("A9.18", q) for q in ("GOLDEN", "PERF_RERUN")}
    assert set(MX.LATER_APPS) == later
    want |= later
    assert set(ids) == want and len(want) == 136 + 8
    for e in MXDOC["entries"]:
        assert e["status"] in MX.STATUSES
        for r in e["residual"]:
            assert r["status"] in MX.RESIDUAL_STATUSES
    assert '"PASS"' not in json.dumps(MXDOC)


def test_matrix_status_classes():
    """A9.16 finalize: step-2 (A9.9) and step-3 (A9.13) decisions are APPLIED only through a verified step-2 / step-3
    application; the ones no commit applies are BLOCKED / PARTIAL with a stated reason (never PENDING after the steps)."""
    by = {e["question_id"]: e for e in MXDOC["entries"] if e["decision"] not in ("A9.17", "A9.18")}
    code_lanes = {"STEP2", "STEP3", "A9.13_DATA", "A9.17"}
    for q in L.decision_ids("A9.9"):
        e = by[q]
        assert e["status"] in ("APPLIED", "PARTIAL"), q
        assert any(a["lane"] == "STEP2" for a in e["applications"]), q
    assert by["F1Q-04"]["status"] == "PARTIAL"
    for q in MX.STEP3:
        assert L.decision_key_of(q) == "A9.13"
        e = by[q]
        if q in MX.STEP3_NOT_APPLIED:
            assert e["status"] == "BLOCKED" and e["status_reason"], q
        elif q in MX.STEP3_PARTIAL:
            assert e["status"] == "PARTIAL", q
        else:
            assert e["status"] == "APPLIED", q
            assert any(a["lane"] in code_lanes for a in e["applications"]), q
    for e in MXDOC["entries"]:
        assert e["status"] not in ("PENDING_STEP_2_MODEL_CHANGE", "PENDING_STEP_3_ARCHITECTURE", "PENDING_CI_CHANGE")
        assert all(r["status"] not in ("PENDING_STEP_2_MODEL_CHANGE", "PENDING_STEP_3_ARCHITECTURE")
                   for r in e["residual"])
    assert by["RUST-OQ-02"]["status"] == "APPLIED"
    assert any(a["artifact"] == ".github/workflows/rust-parity.yml" for a in by["RUST-OQ-02"]["applications"])
    assert by["F0-OQ-01"]["status"] == by["F0-OQ-02"]["status"] == "APPLIED"
    assert any("PERF_RERUN" in r["where"] for r in by["F0-OQ-02"]["residual"])
    assert by["RUST-OQ-01"]["status"] == "APPLIED"
    later = {(e["decision"], e["question_id"]): e for e in MXDOC["entries"] if e["decision"] in ("A9.17", "A9.18")}
    assert later[("A9.18", "PERF_RERUN")]["status"] == "BLOCKED"
    assert later[("A9.18", "GOLDEN")]["status"] == "APPLIED"
    assert any("golden_v2.json" in a["record_locations"] for a in later[("A9.18", "GOLDEN")]["applications"])
    for q in L.A915_AMENDED:
        assert by[q]["amended_by_a9_15"]
    assert by["A9.15 governing_rule"]["status"] == "APPLIED"


def test_matrix_applications_are_verifiable():
    import subprocess
    commits = set()
    for e in MXDOC["entries"]:
        if e["status"] == "APPLIED":
            gov = [a for a in e["applications"] if a["status"] == "APPLIED"
                   and not a["artifact"].endswith("owner_questions_state_v5.json")]
            assert gov, e["question_id"]
        for a in e["applications"]:
            assert (ROOT / a["artifact"]).exists(), a["artifact"]
            assert re.fullmatch(r"[0-9a-f]{40}", a["commit"]), a
            commits.add(a["commit"])
            if a["status"] != "APPLIED" or a["lane"] == "INTEGRATION":
                continue
            if a["lane"] in ("STEP2", "STEP3", "A9.13_DATA", "A9.17", "A9.18"):
                text = (ROOT / a["artifact"]).read_text(encoding="utf-8")
                assert a["record_locations"] and all(t in text for t in a["record_locations"]), (e["question_id"], a)
            elif e["decision"] != "A9.15":
                assert MX._locations(_j(a["artifact"]), e["question_id"]), (e["question_id"], a["artifact"])
    for c in commits:
        r = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", c + "^{commit}"], capture_output=True)
        assert r.returncode == 0, c


def test_matrix_refuses_unverifiable_lane_result(monkeypatch):
    lanes = dict(MX.LANES)
    c, art, q = lanes["P3"]
    lanes["P3"] = (c, art, q + ["F5-OQ-01"])           # an id the P3 artifact never mentions
    monkeypatch.setattr(MX, "LANES", lanes)
    with pytest.raises(SystemExit):
        MX.build()



def test_matrix_repair_lane_truthful_statuses():
    """A9.16 repair F7 / F1 / F2 / F5: S6.12 / S6.16 are PENDING_STEP_3_ARCHITECTURE (records not rebuilt), S7.2 is
    PARTIAL (rule recorded, point not selected); ICPQ-10 / OQ-A910-06 / P3Q-01 carry the repair-lane applications and
    no 'outside the allowed paths' residual; COR-04 (F7 / F8 not regenerated) is stated."""
    by = {e["question_id"]: e for e in MXDOC["entries"]}
    # A9.16 finalize: S6.12 / S6.16 are applied in the step-3 design-layer code; their F-lane record annotations stay
    # an explicit residual until the finalize design lane regenerates the records
    for q in ("OQ-F4-03", "OQ-F78-02"):
        assert by[q]["status"] == "APPLIED"
        assert any(r["status"] == "PENDING_FINALIZE_DESIGN_REGEN" for r in by[q]["residual"]), q
    assert by["F5-OQ-02"]["status"] == "PARTIAL"
    assert any("NOT_SELECTED_PENDING_FEMM" in r["what"] for r in by["F5-OQ-02"]["residual"])
    for q in ("ICPQ-10", "OQ-A910-06", "P3Q-01", "P1Q-19", "OQ-RFQV2-10", "P4-OQ-01"):
        e = by[q]
        assert e["status"] == "APPLIED", q
        assert any(a["lane"] == "REPAIR" and a["commit"] == MX.REPAIR_COMMIT for a in e["applications"]), q
        assert not any("outside the allowed paths" in r["where"] for r in e["residual"]), q
    assert re.fullmatch(r"[0-9a-f]{40}", MXDOC["repair_commit"])
    fixes = {f["id"]: f["what"] for f in MXDOC["repair_fixes"]}
    assert set(fixes) >= {"COR-01", "COR-02", "COR-03", "COR-04", "COR-05"} and "2-minute" in fixes["COR-04"]
    f0 = by["F0-OQ-01"]
    assert f0["status"] == "APPLIED" and any(
        a["artifact"].endswith("dedicated_baseline_2026_10_01/REGISTRATION.json") for a in f0["applications"])
