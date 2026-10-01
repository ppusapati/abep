"""Regression tests for the design-area review repairs (RVF-01/02, PHY-01/03, SW-02, RFP-02).

Each test pins the root-cause fix, not a number: the S6.8 domain gate in the W1 closure is covered in
tests/test_feed_state_closure.py; here the downstream records, the owner-answer state of the F-lane records, the
H2-6 source verification and the F7/F8 budget inputs are checked.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _j(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ RVF-02 owner state
F_RECORDS = {
    "F1": ("docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json",
           "docs/design_synthesis/f1_intake/F1_INTAKE_SYNTHESIS.md"),
    "F2": ("docs/design_synthesis/f2_filter/f2_filter_stage_v1.json",
           "docs/design_synthesis/f2_filter/F2_FILTER_STAGE.md"),
    "F3": ("docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json",
           "docs/design_synthesis/f3_compressor/F3_COMPRESSOR_SYNTHESIS.md"),
}


def test_owner_state_reads_v5_and_never_fabricates():
    from abep_sim.design import owner_state as ost
    s = ost.owner_state("F1Q-01")
    assert s["answered"] and s["decision"] == "A9.9 S2.1" and s["decision_code"] == "YES_PRODUCTION_FIX"
    assert ost.owner_state("NO-SUCH-QUESTION-ID")["status"] == ost.TBD_OWNER
    assert ost.status_label("NO-SUCH-QUESTION-ID") == ost.TBD_OWNER


@pytest.mark.parametrize("lane", sorted(F_RECORDS))
def test_f_lane_questions_carry_v5_answer_state(lane):
    from abep_sim.design import owner_state as ost
    js, md = F_RECORDS[lane]
    doc = _j(js)
    text = (REPO / md).read_text(encoding="utf-8")
    assert doc["open_owner_questions"]
    for q in doc["open_owner_questions"]:
        s = ost.owner_state(q["id"])
        assert q["status_as_raised"] == "TBD_OWNER"
        if s["answered"]:
            assert q["status"] == s["status_detail"] and q["decision_code"] == s["decision_code"], q["id"]
            assert f"**{q['id']}** (TBD_OWNER)" not in text and f"**{q['id']}**: " not in text
        else:
            assert q["status"] == "TBD_OWNER"


def test_no_stale_tbd_owner_for_answered_questions():
    f2 = (REPO / F_RECORDS["F2"][1]).read_text(encoding="utf-8")
    assert "admissibility TBD_OWNER" not in f2 and "TBD_OWNER (F2-OQ-0" not in f2
    f2j = _j(F_RECORDS["F2"][0])
    if8 = next(d for d in f2j["interface_demands"] if d["id"] == "F2-IF-08")
    assert "TBD_OWNER" not in if8["status"] and "S6.6" in if8["status"]
    f3 = (REPO / F_RECORDS["F3"][1]).read_text(encoding="utf-8")
    assert "TBD_OWNER for flight" not in f3
    f3j = _j(F_RECORDS["F3"][0])
    ps = next(p for p in f3j["parameters"] if p["id"] == "P-STRESS-SAFETY")
    assert "A9.9 S2.3" in ps["status"] and "TBD_OWNER" not in ps["status"]


def test_f1_01_is_historical_against_the_fixed_production_code():
    f1 = _j(F_RECORDS["F1"][0])
    f = next(x for x in f1["findings"] if x["id"] == "F1-01")
    assert f["finding"].startswith("HISTORICAL")
    assert "FIXED in production" in f["handling"] and "A9.9 S2.1" in f["handling"]
    src = (REPO / "abep_sim" / "intake_tpmc.py").read_text(encoding="utf-8")
    assert "owner decision A9.9 S2.1 / F1Q-01" in src     # the fix the record now cites


# ------------------------------------------------------------------------------------- PHY-01 / PHY-03 downstream
def test_compressor_downselect_and_f3_use_in_domain_w1_only():
    w1 = _j("docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json")
    closed = sorted(c for c, v in w1["closure"].items() if v["status"] == "CLOSED")
    assert all(sp <= 0.1 for c in closed for sp in w1["closure"][c]["common_feasible_setpoints_Pa"])
    cd = _j("docs/architecture_comparison/compressor_downselect/compressor_downselect_v1.json")
    assert sorted(cd["requirement_envelope"]) == closed
    from abep_sim.design import compressor_synthesis as cs
    a = cd["requirement_summary"]["A_inlet_min_m2"]["0.25"]
    assert (a["min"], a["max"]) == cs.A_INLET_MIN_B025_RANGE_M2
    f3 = _j("docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json")
    assert len(f3["cases"]) == sum(len(v["cases"]) for v in cd["requirement_envelope"].values())


# ------------------------------------------------------------------------------------------------------------ SW-02
def _h26():
    import importlib.util
    import sys
    p = REPO / "docs/hardware/h2/h2_6_diagnostics_fixture/build_h2_6_diagnostics_fixture.py"
    spec = importlib.util.spec_from_file_location("_h26_repairs", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_h26_repairs"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_h2_6_check_runs_the_live_source_verification(monkeypatch):
    """SW-02: --check must fail on a stale transcription, not only --verify-sources."""
    mod = _h26()
    monkeypatch.setattr(mod, "check", lambda *a, **k: [])
    monkeypatch.setattr(mod, "verify_sources", lambda *a, **k: ["mdot_O2_max_W1_kgps: live source != consumed"])
    assert mod.main(["--check"]) == 1
    monkeypatch.setattr(mod, "verify_sources", lambda *a, **k: [])
    assert mod.main(["--check"]) == 0


# ----------------------------------------------------------------------------------------------------------- RFP-02
def test_optimizer_reads_the_a9_15_applied_budgets():
    from abep_sim.design import architecture_optimizer as ao
    assert ao.MP_REL.endswith("mass_power_a9_v3/mass_power_a9_v3.json")
    assert ao.RFQ_REL.endswith("rfq_a9_v3/rfq_a9_v3.json")
    assert ao.P3_REL.endswith("p3_coupled_thermal_v2.json")
    mp = _j(ao.MP_REL)
    w = ao.wet_mass("hall_icp_neutralizer")
    want = [x["wet_known_kg"] for r in mp["rollups"] if r["configuration"] == "hall_icp_neutralizer"
            for x in r["wet"] if x["reference"] == "HARD_40_WET"]
    assert w["wet_known_allocation_envelope_kg"] == [min(want), max(want)]
    assert w["wet_rollup_states"] == ["DOES_NOT_CLOSE"]          # A9.15 v3: primary config fails 40 kg wet
    assert min(want) > 40.0
    assert {x["xe_case_kg"] for x in w["wet_rollup_by_xe_case"]} == {2.0, 5.0, 10.0}


def test_committed_f7_record_uses_v3_wet_rollup():
    from abep_sim.design import architecture_optimizer as ao
    doc = _j("docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json")
    text = json.dumps(doc)
    for stale in ("mass_power_a9_v2", "rfq_a9_v2", "p3_coupled_thermal_v1"):
        assert stale not in text, stale
    aq6 = next(q for q in ao.architecture_questions() if q["id"] == "AQ-06")
    assert "hall_icp_neutralizer ['DOES_NOT_CLOSE']" in aq6["basis"]
    assert aq6["basis"] in text
