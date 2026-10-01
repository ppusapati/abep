"""A9.19 / A9.20 design-layer rules: one Hall + one ICP neutralizer, two supply modes (AIR_PRIMARY / XE_CONTINGENCY),
no hollow cathode in flight, C1 ground-only (abep_sim/design/a9_19_architecture.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abep_sim import bus_boundary_a9 as bb
from abep_sim.design import a9_19_architecture as a919
from abep_sim.design import architecture_optimizer as ao
from abep_sim.design import upstream_a9_13 as u13

ROOT = Path(__file__).resolve().parents[1]


def test_decision_records_pinned():
    assert all(a919.verify_decision_records(ROOT).values())
    a919.require_decision_records(ROOT)
    md = (ROOT / a919.DECISIONS["A9.19"]["md"]).read_text(encoding="utf-8")
    for line in a919.VERBATIM_A9_19:
        assert line in md
    j = json.loads((ROOT / a919.DECISIONS["A9.19"]["json"]).read_text(encoding="utf-8"))
    assert j["decision"] == a919.DECISIONS["A9.19"]["decision_code"]
    assert j["architecture"]["hall_accelerators"] == a919.FLIGHT_ARCHITECTURE["hall_accelerators"] == 1
    j20 = json.loads((ROOT / a919.DECISIONS["A9.20"]["json"]).read_text(encoding="utf-8"))
    assert j20["decision"] == a919.DECISIONS["A9.20"]["decision_code"]


def test_rfp_clauses_registered():
    reg = json.dumps(json.loads((ROOT / a919.RFP_REGISTRATION).read_text(encoding="utf-8")))
    for cid in a919.RFP_CLAUSES.values():
        assert f'"{cid}"' in reg


def test_flight_configurations_only_icp_neutralizer():
    assert a919.FLIGHT_CONFIGURATIONS == ("hall_icp_neutralizer",)
    assert ao.CONFIGURATIONS == a919.FLIGHT_CONFIGURATIONS
    assert "hall_c1_reference" not in ao.CONFIGURATIONS
    assert ao.GROUND_REFERENCE_CONFIGURATIONS == ("hall_c1_reference",)
    fa = a919.FLIGHT_ARCHITECTURE
    assert fa["hall_accelerators"] == 1 and fa["electron_source_neutralizer"]["count"] == 1
    assert fa["electron_source_neutralizer"]["serves_supply_modes"] == ["AIR_PRIMARY", "XE_CONTINGENCY"]
    assert [m["mode"] for m in fa["supply_modes"]] == ["AIR_PRIMARY", "XE_CONTINGENCY"]
    assert fa["conventional_hollow_cathode"] == "NONE" and fa["separate_tanks"] is True
    assert fa["icp_feed_gas_baseline"]["primary"] == "G-REUSE" and fa["icp_feed_gas_baseline"]["declared_variant"] == "G-XE"
    assert fa["c1"]["status"] == "GROUND_ONLY_LAB_EQUIPMENT"


def test_hall_c1_reference_refused_as_flight_configuration():
    with pytest.raises(a919.ArchitectureRuleError, match="not a flight configuration"):
        a919.require_flight_configuration("hall_c1_reference")
    with pytest.raises(ao.OptimizerError, match="not a flight configuration"):
        ao.evaluate_system(None, "hall_c1_reference")
    with pytest.raises(a919.ArchitectureRuleError):
        ao.flight_configuration_elements("hall_c1_reference")
    gr = a919.ground_reference("hall_c1_reference", "C1-vs-ICP bench control")
    assert gr["label"] == "GROUND_REFERENCE" and gr["flight_candidate"] is False and gr["in_flight_budgets"] is False
    with pytest.raises(a919.ArchitectureRuleError):
        a919.ground_reference("hall_c1_reference", " ")
    with pytest.raises(a919.ArchitectureRuleError):
        a919.ground_reference("hall_icp_neutralizer", "x")


def test_no_hollow_cathode_element_in_flight_configuration():
    els = ao.flight_configuration_elements("hall_icp_neutralizer")
    assert a919.refuse_hollow_cathode_elements("hall_icp_neutralizer", els)["hollow_cathode_elements"] == []
    ev = ao.evaluate_system(None, "hall_icp_neutralizer")
    assert ev["hollow_cathode_check"] == "NO_HOLLOW_CATHODE_ELEMENT_LISTED"
    # every hollow-cathode marker is refused in a flight configuration
    for bad in ("c1_heater", "c1_keeper", "AL-C1", "hollow cathode", "LaB6 emitter", {"id": "X", "name": "C1"},
                {"id": "C-1"}, "cathode_heater", "C1 Xe branch"):
        with pytest.raises(a919.ArchitectureRuleError, match="hollow-cathode"):
            a919.refuse_hollow_cathode_elements("hall_icp_neutralizer", els + [bad])
    # the C1 configuration's own slots are all caught
    hits = a919.hollow_cathode_elements(bb.installed_slots("hall_c1_reference"))
    assert set(hits) >= {"c1_heater", "c1_keeper", "c1_common_tie"}
    # no false positive on the ICP flight elements
    assert a919.hollow_cathode_elements(bb.installed_slots("hall_icp_neutralizer")) == []


def test_hc10_separate_paths_xe_role_contingency_emergency():
    ok = u13.propellant_paths_check(ao.MODELLED_PROPELLANT_PATHS)
    assert ok["path_roles"] == {"air": "PRIMARY", "xe": "CONTINGENCY_EMERGENCY"}
    assert ok["supply_modes"] == {"air": "AIR_PRIMARY", "xe": "XE_CONTINGENCY"}
    assert ok["status"] == u13.C_NOT_EVALUATED                     # capability still NOT_EVALUATED, never PASS
    assert u13.PROPELLANT_POLICY["xe_path_role"] == "CONTINGENCY_EMERGENCY"
    assert any(c["decision"] == "A9.19" for c in ok["authority"])
    for bad in ({"air": list(u13.AIR_PATH)}, {"xe": list(u13.XE_PATH)},
                {"air": list(u13.AIR_PATH), "xe": ["xe_tank", "c1_feed", "valve"]},
                {"air": list(u13.AIR_PATH), "xe": ["xe_tank", "atmospheric_gas_chamber"]}):
        with pytest.raises(u13.A913RuleError):
            u13.propellant_paths_check(bad)
    hc10 = [c for c in ao.evaluate_constraints({}) if c["id"] == "HC-10"][0]
    assert hc10["status"] == ao.C_NOT_EVALUATED


def test_supply_modes_for_icp_records():
    assert a919.classify_gas("N2") == "AIR_PRIMARY"
    assert a919.classify_gas("nitrogen") == "AIR_PRIMARY"
    assert a919.classify_gas("O2") == "AIR_PRIMARY"
    assert a919.classify_gas("Xe") == "XE_CONTINGENCY"
    assert a919.classify_gas("Ar") == a919.BENCH_SUPPLY_MODE
    assert a919.check_supply_mode("Xe", "XE_CONTINGENCY")["role"] == "CONTINGENCY_EMERGENCY"
    assert a919.check_supply_mode("N2", "AIR_PRIMARY")["role"] == "PRIMARY"
    with pytest.raises(a919.ArchitectureRuleError):
        a919.check_supply_mode("Xe", "AIR_PRIMARY")
    with pytest.raises(a919.ArchitectureRuleError):
        a919.check_supply_mode("He", "AIR_PRIMARY")
    with pytest.raises(a919.ArchitectureRuleError):
        a919.check_supply_mode("N2", "XE_PRIMARY")


def test_architecture_questions_no_c1_flight_comparison():
    qs = {q["id"]: q for q in ao.architecture_questions()}
    assert "GROUND_REFERENCE" in qs["AQ-09"]["question"]
    assert "(or C1)" not in qs["AQ-07"]["question"]
    assert all(q["answer_state"] != "PASS" for q in qs.values())


def test_applied_row_cites_decision_hashes():
    r = a919.applied_row("A9.19", "x.json", ["R"], "how", ["t"])
    assert r["decision_json_sha256"] == a919.DECISIONS["A9.19"]["json_sha256"]
    assert r["decision_md_sha256"] == a919.DECISIONS["A9.19"]["md_sha256"]
    with pytest.raises(a919.ArchitectureRuleError):
        a919.applied_row("A9.15", "x", [], "")
