"""A9.21 HW_PROGRAMME (owner items 6-11): programme-order record + fail-closed entry logic, and its use by the stage
artifacts (H-1 freeze candidate, P1, P2, P3 v2, P4). Synthetic registrations below are TEST DATA ONLY (ids, hashes and
timestamps are placeholders; no physical value is asserted)."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROG_DIR = ROOT / "docs" / "experiments" / "hall_icp" / "programme"
sys.path.insert(0, str(PROG_DIR))
import build_hw_programme as B  # noqa: E402
import hw_programme_a9_21 as P  # noqa: E402

H = "a" * 64
T0, T1, T2, T3 = "2027-01-01T00:00:00Z", "2027-01-02T00:00:00Z", "2027-01-03T00:00:00Z", "2027-01-04T00:00:00Z"


def reg(rid="R-1", t=T0, **kw):
    d = {"registration_id": rid, "frozen_utc": t, "sha256": H}
    d.update(kw)
    return d


def done(rid="C-1", t=T0):
    return {"record_id": rid, "completed_utc": t, "sha256": H}


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ record
def test_builder_reproduces():
    assert B.main(["--check"]) == 0


def test_record_cites_pinned_a9_21_and_items_verbatim():
    doc = load(P.RECORD_REL)
    d = doc["decision"]
    assert d["decision_md_sha256"] == hashlib.sha256((ROOT / d["decision_md"]).read_bytes()).hexdigest()
    assert d["decision_json_sha256"] == hashlib.sha256((ROOT / d["decision_json"]).read_bytes()).hexdigest()
    md = (ROOT / d["decision_md"]).read_text(encoding="utf-8")
    assert sorted(doc["owner_items_verbatim"], key=int) == ["6", "7", "8", "9", "10", "11"]
    for it in doc["owner_items_verbatim"].values():
        assert it["verbatim"] in md


def test_programme_order_and_explicit_dependencies():
    order = [s["id"] for s in P.STEPS]
    pred = {s["id"]: {p["step"]: p["basis"] for p in s["predecessors"]} for s in P.STEPS}
    for a, b in (("H1-S7.1", "H1-S7.2"), ("C1-REF", "ICP-45A-P1-S7"), ("ICP-45A-P1-S7", "ICP-45N"),
                 ("ICP-45N", "ICP-XE-MODE"), ("COUPLED-H1-ICP", "P3-THERMAL"), ("P3-THERMAL", "P4-ACCEPTANCE-EXPOSURE"),
                 ("H1-THRUST-FEED-MAP", "AG-12"), ("AG-12", "AG-13")):
        assert order.index(a) < order.index(b)
        assert pred[b][a] == "EXPLICIT_A9_21", (a, b)
    # recorder-only dependency is labelled as such
    assert pred["C1-REF"] == {"H1-S7.2": "PHYSICAL_PREREQUISITE_RECORDER"}
    # the Ar reference P1-S0..S6 needs no C1 registration (A9.10 P1Q-07 gates P1-S7 only)
    assert not pred["ICP-AR-REF"]
    assert {s["artifact"] for s in P.STEPS if s["id"] in ("AG-12", "AG-13")} == {"F9"}


def test_nothing_registered_today_no_step_registered_no_pass():
    doc = load(P.RECORD_REL)
    for s in doc["steps"]:
        assert s["entry_status_now"] in P.ENTRY_STATUSES
        assert s["entry_status_now"] != P.ENTRY_REGISTERED, s["id"]
    text = json.dumps(doc)
    for w in ('"PASS"', '"GO"', '"START_AUTHORISED"', '"READY"'):
        assert w not in text


def test_record_refuses_stale(monkeypatch):
    real = P.document

    def changed():
        d = real()
        d["title"] = d["title"] + " (changed)"
        return d
    monkeypatch.setattr(P, "document", changed)
    with pytest.raises(P.ProgrammeError, match="stale"):
        P.record_sha256()


# ------------------------------------------------------------------------------------------------ item 6 H-1
def femm(points=("A", "B"), results=("A", "B"), t=T0):
    return reg("FEMM-REG", t, authorised_points=list(points),
               results=[{"probe": p, "result_id": f"FR-{p}", "sha256": H, "geometry_id": f"G-{p}",
                         "solver_configuration_id": "S-1"} for p in results])


def test_s7_2_needs_s7_1_results_for_every_authorised_point():
    ev = {"completed": {"H1-S7.1": done()}, "registrations": {"H1-S7.2-PRE-01": femm(results=("A",))}}
    r = P.entry_status("H1-S7.2", ev)
    assert r["status"] == P.NOT_STARTABLE_PRECONDITION and any("'B'" in x for x in r["precondition_reasons"])
    assert P.entry_status("H1-S7.2", {"registrations": {"H1-S7.2-PRE-01": femm()}})["status"] == \
        P.NOT_STARTABLE_PREDECESSOR
    ev["registrations"]["H1-S7.2-PRE-01"] = femm()
    assert P.entry_status("H1-S7.2", ev)["status"] == P.ENTRY_REGISTERED
    ev["first_record_utc"] = T0
    assert P.entry_status("H1-S7.2", ev)["status"] == P.ENTRY_NOT_MET_LATE


def sel(**kw):
    s = {"selection_id": "SEL-1", "point_id": "A", "frozen_utc": T1, "status": P.H1_POINT_STATUS,
         "optimisation_basis": P.H1_NOT_THRUST_OPTIMISED,
         "criteria": {c: {"record_id": f"CR-{c}"} for c in P.H1_SELECTION_CRITERIA}}
    s.update(kw)
    return s


def test_s7_2_selection_engineering_freeze_candidate_never_thrust_optimised():
    assert P.s7_2_selection_check(sel(), femm())["status"] == "ENGINEERING_FREEZE_CANDIDATE"
    with pytest.raises(P.ProgrammeError, match="before S7.1"):
        P.s7_2_selection_check(sel(), femm(results=("A",)))
    bad = sel()
    bad["criteria"]["thrust_margin"] = {"record_id": "X"}
    with pytest.raises(P.ProgrammeError, match="not thrust-optimised"):
        P.s7_2_selection_check(bad, femm())
    bad = sel()
    del bad["criteria"]["manufacturability"]
    with pytest.raises(P.ProgrammeError, match="missing assessments"):
        P.s7_2_selection_check(bad, femm())
    with pytest.raises(P.ProgrammeError, match="only ENGINEERING_FREEZE_CANDIDATE"):
        P.s7_2_selection_check(sel(status="FROZEN"), femm())
    with pytest.raises(P.ProgrammeError, match="S7.1 first"):
        P.s7_2_selection_check(sel(frozen_utc=T0), femm())
    with pytest.raises(P.ProgrammeError, match="not an authorised"):
        P.s7_2_selection_check(sel(point_id="Z"), femm())


def test_h1_artifact_records_its_place_and_stays_unselected():
    h1 = load(P.ARTIFACTS["H1"])
    v = h1["a9_21_programme"]
    assert [s["id"] for s in v["steps"]] == P.ARTIFACT_STEPS["H1"] == ["H1-S7.1", "H1-S7.2", "H1-THRUST-FEED-MAP"]
    assert v["h1f_ch_11"]["point_status"] == "NOT_SELECTED_PENDING_FEMM"
    assert v["h1f_ch_11"]["status_when_selected"] == "ENGINEERING_FREEZE_CANDIDATE"
    assert v["h1f_ch_11"]["selection_criteria_a9_21"] == list(P.H1_SELECTION_CRITERIA)
    assert v["ag12_ag13_dependency"]["AG-12"]["programme_input"] == "NOT_EVALUATED"


# ------------------------------------------------------------------------------------------------ item 7 C1 reference
def idreg(**kw):
    red = P.P1RED
    d = {"registration_id": "IDM-1", "I_d_max_H1_A": 1.0, "basis": red.REGISTRATION_BASIS, "source": "C1REF-1",
         "registered_point_ids": ["HP-1"], "propellant": red.I_D_MAX_PROPELLANT, "characterization_id": "C1REF-1",
         "electron_source": red.I_D_MAX_ELECTRON_SOURCE, "envelope_id": red.I_D_MAX_ENVELOPE, "u_I_d_max_H1_A": 0.1,
         "frozen_utc": T1, "scope": red.I_D_MAX_SCOPE}
    d.update(kw)
    return d


def test_p1_s7_needs_c1_reference_registration_before_first_p1_s7():
    comp = {"C1-REF": done(t=T0), "ICP-AR-REF": done(t=T0)}
    assert P.entry_status("ICP-45A-P1-S7", {"completed": {"ICP-AR-REF": done()}})["status"] == \
        P.NOT_STARTABLE_PREDECESSOR
    assert P.entry_status("ICP-45A-P1-S7", {"completed": comp})["status"] == P.NOT_STARTABLE_PRECONDITION
    r = P.entry_status("ICP-45A-P1-S7", {"completed": comp,
                                         "registrations": {"ICP-45A-P1-S7-PRE-01": idreg(electron_source="ICP")}})
    assert r["status"] == P.NOT_STARTABLE_PRECONDITION and "electron_source" in r["precondition_reasons"][0]
    ok = {"completed": comp, "registrations": {"ICP-45A-P1-S7-PRE-01": idreg()}, "first_record_utc": T2}
    assert P.entry_status("ICP-45A-P1-S7", ok)["status"] == P.ENTRY_REGISTERED
    ok["first_record_utc"] = T1
    assert P.entry_status("ICP-45A-P1-S7", ok)["status"] == P.ENTRY_NOT_MET_LATE


def test_ar_reference_keeps_existing_per_stage_rules_delegated():
    r = P.entry_status("ICP-AR-REF")
    assert r["status"] == P.DELEGATED_ONLY
    assert {d["id"] for d in r["delegated_preconditions"]} == {f"ICP-AR-REF-PRE-0{i}" for i in range(1, 5)}


# ------------------------------------------------------------------------------------------------ item 8 ICP campaigns
def campaign(step="ICP-45N", gas="N2", mode="AIR_PRIMARY", dom="DOM-N2-1", rset="RS-N2-1", first=None, **closures):
    c = {"campaign_id": f"CAMP-{step}", "programme_step": step, "gas": gas, "supply_mode": mode,
         "operating_domain": {"domain_id": dom, "frozen_utc": T0, "basis": "registered hardware", "sha256": H},
         "provenance": {"registration_set_id": rset, "frozen_utc": T0, "sha256": H, "source": "registration"},
         "closures": {k: reg(f"CL-{k}", T0) for k in P.ICP_CAMPAIGN_CLOSURES}, "first_record_utc": first}
    c["closures"].update(closures)
    return c


def test_icp_campaign_own_domain_and_provenance_refusals():
    assert P.icp_campaign_check(campaign())["status"] == P.ENTRY_REGISTERED
    c = campaign()
    del c["operating_domain"]["domain_id"]
    with pytest.raises(P.ProgrammeError, match="no own operating domain"):
        P.icp_campaign_check(c)
    c = campaign()
    c["provenance"] = None
    with pytest.raises(P.ProgrammeError, match="no own provenance"):
        P.icp_campaign_check(c)
    xe = campaign("ICP-XE-MODE", "Xe", "XE_CONTINGENCY", dom="DOM-N2-1", rset="RS-XE-1")
    with pytest.raises(P.ProgrammeError, match="own operating domain"):
        P.icp_campaign_check(xe, [campaign()])
    xe = campaign("ICP-XE-MODE", "Xe", "XE_CONTINGENCY", dom="DOM-XE-1", rset="RS-N2-1")
    with pytest.raises(P.ProgrammeError, match="own provenance"):
        P.icp_campaign_check(xe, [campaign()])
    with pytest.raises(P.ProgrammeError, match="Ar reference"):
        P.icp_campaign_check(campaign(dom="DOM-AR-S4"), ar_reference_domain_ids=["DOM-AR-S4"])
    with pytest.raises(P.ProgrammeError, match="one gas / mode"):
        P.icp_campaign_check(campaign(gas="Xe", mode="XE_CONTINGENCY"))
    with pytest.raises(P.ProgrammeError):
        P.icp_campaign_check(campaign(gas="Ar", mode="BENCH_AR_ENGINEERING_GROUND_ONLY"))
    with pytest.raises(P.ProgrammeError, match="not a registered gas"):
        P.icp_campaign_check(campaign(step="ICP-AR-REF"))


def test_icp_campaign_closures_registered_before_first_record():
    r = P.icp_campaign_check(campaign(dwv_leakage_criteria=None))
    assert r["status"] == P.NOT_STARTABLE_PRECONDITION and any("dwv_leakage_criteria" in m for m in r["missing"])
    r = P.icp_campaign_check(campaign(first=T1, stable_region_criteria=reg("SC", T1)))
    assert r["status"] == P.ENTRY_NOT_MET_LATE
    assert P.icp_campaign_check(campaign(first=T1))["status"] == P.ENTRY_REGISTERED


def test_icp_campaign_order_ar_then_n2_then_xe():
    assert P.entry_status("ICP-45N")["status"] == P.NOT_STARTABLE_PREDECESSOR
    assert P.entry_status("ICP-45N", {"completed": {"ICP-45A-P1-S7": done()}})["status"] == \
        P.NOT_STARTABLE_PRECONDITION
    ok = {"completed": {"ICP-45A-P1-S7": done()}, "campaign": campaign(first=T1)}
    assert P.entry_status("ICP-45N", ok)["status"] == P.ENTRY_REGISTERED
    xe = campaign("ICP-XE-MODE", "Xe", "XE_CONTINGENCY", dom="DOM-XE-1", rset="RS-XE-1", first=T2)
    assert P.entry_status("ICP-XE-MODE", {"campaign": xe})["status"] == P.NOT_STARTABLE_PREDECESSOR
    assert P.entry_status("ICP-XE-MODE", {"campaign": xe, "completed": {"ICP-45N": done(t=T1)},
                                          "other_campaigns": [campaign(first=T1)]})["status"] == P.ENTRY_REGISTERED
    with pytest.raises(P.ProgrammeError, match="registered for"):
        P.entry_status("ICP-XE-MODE", {"campaign": campaign(), "completed": {"ICP-45N": done()}})


def test_p1_artifact_records_campaign_rule_and_reading():
    v = load(P.ARTIFACTS["P1"])["a9_21_programme"]
    assert [s["id"] for s in v["steps"]] == ["C1-REF", "ICP-AR-REF", "ICP-45A-P1-S7", "ICP-45N", "ICP-XE-MODE"]
    assert v["icp_campaign_rule"]["closures"] == list(P.ICP_CAMPAIGN_CLOSURES)
    assert {r["id"] for r in v["recorder_readings"]} == {"RR-01", "RR-02", "RR-03"}


# ------------------------------------------------------------------------------------------------ item 9 P2
def vi_cal(route="IN_HOUSE_VNA_TRACEABLE"):
    R = P.P2RULES
    content = {k: {"record_id": f"VI-{k}"} for k in R.IN_HOUSE_REQUIRED}
    content["rp_vi_to_rp_ant_fixture"] = {"form": "CHARACTERIZED", "record_id": "VI-FIX"}
    content["uncertainty_propagation"] = {"u_relative_phase_deg": 1.0, "u_magnitude_rel": 0.01, "record_id": "VI-UP",
                                          "relative_phase_basis": "reactive_reference"}
    return {"route": route, "accredited_scope_unavailable_basis": "no accredited scope (test data)", "content": content,
            "cal_p2_15_at_power_validation": {"status": "VERIFIED", "record_ids": ["CAL15-1"]}}


def test_p2_map_after_frozen_in_house_calibration_and_budget():
    assert P.entry_status("P2-MAP")["status"] == P.NOT_STARTABLE_PRECONDITION
    regs = {"P2-MAP-PRE-01": reg("VI-1", T0, calibration_record=vi_cal()),
            "P2-MAP-PRE-02": reg("UB-1", T0, budget_id="UB-VI-1")}
    assert P.entry_status("P2-MAP", {"registrations": regs, "first_record_utc": T1})["status"] == P.ENTRY_REGISTERED
    bad = copy.deepcopy(regs)
    del bad["P2-MAP-PRE-01"]["calibration_record"]["content"]["repeatability"]
    r = P.entry_status("P2-MAP", {"registrations": bad})
    assert r["status"] == P.NOT_STARTABLE_PRECONDITION and "REFUSED_IN_HOUSE_CONTENT_INCOMPLETE" in \
        r["precondition_reasons"][0]
    bad = copy.deepcopy(regs)
    bad["P2-MAP-PRE-01"]["calibration_record"]["route"] = "ACCREDITED_ISO_IEC_17025_OR_NABL"
    assert P.entry_status("P2-MAP", {"registrations": bad})["status"] == P.NOT_STARTABLE_PRECONDITION
    bad = copy.deepcopy(regs)
    del bad["P2-MAP-PRE-02"]
    assert P.entry_status("P2-MAP", {"registrations": bad})["status"] == P.NOT_STARTABLE_PRECONDITION
    late = copy.deepcopy(regs)
    late["P2-MAP-PRE-02"]["frozen_utc"] = T2
    assert P.entry_status("P2-MAP", {"registrations": late, "first_record_utc": T1})["status"] == P.ENTRY_NOT_MET_LATE


# ------------------------------------------------------------------------------------------------ item 10 P3 -> P4
def lock2():
    return {"status": "LOCK2_FROZEN", "thresholds": {s: {"source": "test"} for s in P.P4RULES.LOCK2_THRESHOLD_SLOTS}}


def test_coupled_then_thermal_then_p4_with_lock2_before_exposure():
    assert P.entry_status("P3-THERMAL")["status"] == P.NOT_STARTABLE_PREDECESSOR
    assert P.entry_status("P3-THERMAL", {"completed": {"COUPLED-H1-ICP": done()}})["status"] == P.ENTRY_REGISTERED
    ev = {"completed": {"P3-THERMAL": done()}, "registrations": {"P4-PRE-01": reg("L2", T1, lock2=lock2())},
          "first_record_utc": T2}
    assert P.entry_status("P4-ACCEPTANCE-EXPOSURE", ev)["status"] == P.ENTRY_REGISTERED
    assert P.entry_status("P4-ACCEPTANCE-EXPOSURE", dict(ev, completed={}))["status"] == P.NOT_STARTABLE_PREDECESSOR
    nl = copy.deepcopy(ev)
    nl["registrations"]["P4-PRE-01"]["lock2"]["status"] = "NOT_EVALUATED_LOCK2_TBD"
    assert P.entry_status("P4-ACCEPTANCE-EXPOSURE", nl)["status"] == P.NOT_STARTABLE_PRECONDITION
    late = dict(ev, first_record_utc=T1)
    assert P.entry_status("P4-ACCEPTANCE-EXPOSURE", late)["status"] == P.ENTRY_NOT_MET_LATE


def test_p3_p4_artifacts_record_place_and_stay_unresolved():
    p3 = load(P.ARTIFACTS["P3"])
    assert [s["id"] for s in p3["a9_21_programme"]["steps"]] == ["COUPLED-H1-ICP", "P3-THERMAL"]
    assert p3["a9_21_programme"]["p3_thermal_entry_now"] == P.NOT_STARTABLE_PREDECESSOR
    assert p3["compliance"]["closure_statuses_unresolved"] is True
    p4 = load(P.ARTIFACTS["P4"])["a9_21_programme"]
    assert [s["id"] for s in p4["steps"]] == ["P4-ACCEPTANCE-EXPOSURE"]
    assert p4["p4_acceptance_exposure_entry_now"] != P.ENTRY_REGISTERED
    assert p4["lock2_registered_freeze_now"] != "LOCK2_FROZEN"


# ------------------------------------------------------------------------------------------------ item 11
def test_thrust_feed_map_drives_ag12_then_ag13():
    assert P.ag12_ag13_dependency()["AG-12"]["programme_input"] == "NOT_EVALUATED"
    m = P.ag12_ag13_dependency(reg("MAP", T0, evidence_class="model-derived"))
    assert m["AG-12"]["programme_input"] == "NOT_EVALUATED" and m["AG-13"]["programme_input"] == "NOT_EVALUATED"
    m = P.ag12_ag13_dependency(reg("MAP", T0, evidence_class="measured"))
    assert m["AG-12"]["programme_input"] == m["AG-13"]["programme_input"] == "INPUT_REGISTERED_EVALUATE_IN_F9"
    assert m["AG-13"]["after"] == "AG-12"
    assert P.entry_status("AG-13", {"completed": {"AG-12": done()}})["status"] == P.ENTRY_REGISTERED
    assert P.entry_status("AG-12", {"completed": {"H1-THRUST-FEED-MAP": done()},
                                    "registrations": {"AG-12-PRE-01": reg(evidence_class="model-derived")}})[
        "status"] == P.NOT_STARTABLE_PRECONDITION


# ------------------------------------------------------------------------------------------------ all stage artifacts
@pytest.mark.parametrize("key", ["H1", "P1", "P2", "P3", "P4"])
def test_stage_artifact_pins_current_programme_record(key):
    v = load(P.ARTIFACTS[key])["a9_21_programme"]
    assert v["programme_record"] == P.RECORD_REL
    assert v["programme_record_sha256"] == hashlib.sha256((ROOT / P.RECORD_REL).read_bytes()).hexdigest()
    assert [s["id"] for s in v["steps"]] == P.ARTIFACT_STEPS[key]
    assert v["order"] == [s["id"] for s in P.STEPS]
    for s in v["steps"]:
        assert s["entry_status_now"] != P.ENTRY_REGISTERED


def test_malformed_inputs_refused():
    with pytest.raises(P.ProgrammeError):
        P.entry_status("NO-SUCH-STEP")
    with pytest.raises(P.ProgrammeError):
        P.entry_status("P2-MAP", {"first_record_utc": "yesterday"})
    r = P.entry_status("H1-S7.2", {"completed": {"H1-S7.1": done()},
                                   "registrations": {"H1-S7.2-PRE-01": dict(femm(), sha256="not-a-hash")}})
    assert r["status"] == P.NOT_STARTABLE_PRECONDITION
