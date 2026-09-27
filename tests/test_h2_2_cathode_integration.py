"""Tests for the H2-2 cathode integration lane (fo_h2_2_cathode_integration, trigger T_H2_2_CATHODE_INTEGRATION).

Fast (< 1 s): reproduction of the generated files, pins, vocabularies, the required H2 deliverable structure,
hand calculations of the derived relations and the refusal paths (no silent defaults).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs/hardware/h2/h2_2_cathode_integration"
BUILDER = LANE / "build_h2_2_cathode_integration.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_h2_2_cathode_integration", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load_builder()


@pytest.fixture(scope="module")
def doc():
    return B.build()


@pytest.fixture(scope="module")
def committed():
    return json.loads((LANE / B.JSON_NAME).read_text())


def test_generated_files_reproduce_byte_for_byte(doc):
    assert (LANE / B.JSON_NAME).read_text() == B.render_json(doc)
    assert (LANE / B.MD_NAME).read_text() == B.render_md(doc)


def test_decision_pins_match_files(committed):
    assert set(committed["decision_pins"]) == set(B.DECISION_PINS)
    for rel, sha in committed["decision_pins"].items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == sha, rel
    for rel in ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
                "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
                "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
                "docs/decisions/verification/A5_BASELINE_VERIFICATION.json"):
        assert rel in committed["decision_pins"]


def test_mutable_governance_never_pinned(committed):
    pinned = list(committed["decision_pins"]) + list(committed["provenance_reads_sha256"])
    for name in B.NEVER_PINNED:
        assert not any(name in p for p in pinned), name
    for p in B.PARALLEL_PATHS:
        assert not any(k.startswith(p) for k in pinned), p


def test_provenance_values_still_match_sources(committed):
    a5 = json.loads((REPO / B.A5_REL).read_text())["xe_mass_allocation"]
    inp = committed["inputs_read"]
    assert inp["mdot_design_mg_s"] == a5["cathode_flow_design_target_mg_s"] == 0.10
    assert inp["mdot_upper_test_mg_s"] == a5["cathode_flow_experimental_upper_test_point_mg_s"] == 0.15
    hw = json.loads((REPO / B.HWDEF_REL).read_text())
    req = {r["id"]: r for r in hw["requirements"]}
    assert inp["vd_set_V"] == req["HW-ENV-01"]["values"]["V_d_proposed_set_V"]["value"]
    assert inp["p_max_W"] == hw["rfp_basis"]["power_max_W"]["value"] == 1500
    xel = {s["id"]: s for s in json.loads((REPO / B.XEL_REL).read_text())["scenarios"]}
    assert inp["n_starts_sc1"] == xel["SC-1"]["parameters"]["N_starts"]["value"]
    assert inp["n_starts_sc2"] == xel["SC-2"]["parameters"]["N_starts"]["value"]


def test_required_structure_present(committed):
    for key in ("design_parameters", "interface_demands", "hard_incompatibility_check",
                "architecture_changing_blockers_touched", "m16_rows", "h3_procurement_inputs", "h4_test_inputs",
                "milestone", "location_options", "shielding_isolation", "flow_measurement", "sources"):
        assert committed[key], key
    assert set(committed["milestone"]) == {"A", "B", "C"}
    assert committed["architectures"] == ["hall_only", "rf_hall", "ecr_hall"]
    assert committed["configuration_items"]["primary"] == "C-1"


def test_design_parameter_vocabulary(committed):
    ids = [p["id"] for p in committed["design_parameters"]]
    assert len(ids) == len(set(ids))
    for p in committed["design_parameters"]:
        assert re.fullmatch(r"H22-\d{2}", p["id"]), p["id"]
        assert p["basis"] in B.BASES, p
        assert p["evidence_class"] in B.EVIDENCE_CLASSES, p
        assert p["article_class"] in B.ARTICLE_CLASSES, p
        assert p["source"], p["id"]
        st = p["status"]
        assert st == "PRELIMINARY" or st.startswith("PENDING docs/") or st.startswith("TBD - requires "), st
        if p["value"] is None:
            assert st != "PRELIMINARY", p["id"]
            assert p["evidence_class"] == "none", p["id"]
        if p["evidence_class"] == "none":
            assert p["value"] is None or p["basis"] == "pending", p["id"]
        if p["basis"] == "pending":
            assert p["value"] is None or "PENDING" in st or "TBD" in st, p["id"]


def test_article_classes_all_used_consistently(committed):
    by_id = {p["id"]: p for p in committed["design_parameters"]}
    assert by_id["H22-01"]["article_class"] == "FLIGHT_REPRESENTATIVE"
    assert by_id["H22-43"]["article_class"] == "H1_TEST_ARTICLE_ONLY"   # precision MFC is a test instrument
    assert by_id["H22-48"]["article_class"] == "GROUND_FACILITY_ONLY"   # calibration method


def test_m16_rows(committed):
    a5 = json.loads((REPO / B.A5_REL).read_text())["architecture"]
    names = set(a5["atmospheric_branch"] + a5["xe_branch"] + a5["propulsion"] + a5["support"])
    assert len(names) == 16
    for row in committed["m16_rows"]:
        assert row["subsystem"] in names, row["subsystem"]
        assert row["proposed_state"] in B.M16_STATES
        if row["proposed_state"] == "BLOCKED":
            assert isinstance(row["blocking_item"], str) and row["blocking_item"]
            assert row["rollup_category"] in B.ROLLUP
        else:
            assert row["blocking_item"] is None and row["rollup_category"] is None
    assert any(r["subsystem"] == "shielded Xe-fed LaB6 hollow cathode" for r in committed["m16_rows"])


def test_interface_demands_shape(committed):
    ids = set()
    for x in committed["interface_demands"]:
        assert set(x) >= {"id", "from", "to", "quantity", "value", "units", "status"}
        assert x["status"]
        assert x["id"] not in ids
        ids.add(x["id"])
    targets = " ".join(x["to"] + x["from"] for x in committed["interface_demands"])
    for lane in ("h2_1_hall_chamber_magnet", "h2_3_gas_path_plenum", "h2_4_ppu_bus", "h2_5_thermal_network",
                 "h2_6_diagnostics_fixture", "h2_7_mechanical_bom", "preionizer_module", "xe_ledger"):
        assert lane in targets, lane


def test_hard_incompatibility_and_blockers(committed):
    hic = committed["hard_incompatibility_check"]
    assert hic["verdict"] == "none found"
    assert len(hic["checked"]) >= 5 and all(c["veto"] is False for c in hic["checked"])
    assert {b["blocker"] for b in committed["architecture_changing_blockers_touched"]} <= {1, 2, 3}


def test_no_forbidden_performance_sources(committed):
    text = json.dumps(committed)
    assert "sgb-screen" not in text
    assert text.count("plasma_devices") == 1          # only in what_this_is_not
    assert "winner" not in text.replace("no winner", "")
    assert "ranking" not in committed


def test_sources_have_hash_or_repo_path(committed):
    for sid, s in committed["sources"].items():
        if "url" in s:
            assert re.fullmatch(r"[0-9a-f]{64}", s["sha256"]), sid
        else:
            assert (REPO / s["path"]).exists(), sid


def test_hand_calculations():
    assert B.mg_s_to_sccm(0.0983009) == pytest.approx(1.0)
    assert B.xe_mass_kg(0.10, 15000) == pytest.approx(5.4)
    assert B.xe_mass_kg(0.15, 15000) == pytest.approx(8.1)
    assert B.mfc_relative_u(0.10, 0.2, 0.005, 0.001) == pytest.approx(0.007)
    assert B.mfc_relative_u(0.10, 1.0, 0.0, 0.01) == pytest.approx(0.10)
    assert B.gravimetric_min_mass_g(10.0, 0.005) == pytest.approx(math.sqrt(2) * 2.0)
    rs = 8.314462618 / 0.131293
    assert B.rate_of_rise_Pa_s(0.10, 1.0, 293.15) == pytest.approx(1e-7 * rs * 293.15 / 1e-3)
    assert B.discharge_current_upper_bound_A(1500, 180) == pytest.approx(8.3333333)
    assert B.rss(3.0, 4.0) == pytest.approx(5.0)


def test_derived_consistency(committed):
    d = committed["derived"]
    assert d["cathode_xe_mass"]["consistent_with_a5"] is True
    row = next(r for r in d["flow_measurement_uncertainty"]["rows"]
               if r["spec"] == "SPEC-CAT-STD" and r["fs_mg_s"] == 0.2 and r["flow"] == "design_target")
    assert row["u_rel_spec"] == pytest.approx(0.007)
    assert row["u_m_15000h_kg_spec"] == pytest.approx(0.0378)
    assert all(r["setpoint_fraction_of_fs"] <= 1.0 for r in d["flow_measurement_uncertainty"]["rows"])
    assert d["echt_context"]["inner_channel_wall_diameter_mm"] == 80.0
    lo, hi = d["emitter_temperature_points"]["operating_span_K"]
    assert lo == pytest.approx(1844.5) and hi == pytest.approx(1973.15)


@pytest.mark.parametrize("call", [
    lambda: B.mg_s_to_sccm(None),
    lambda: B.xe_mass_kg(0.1, None),
    lambda: B.xe_mass_kg(0.0, 15000),
    lambda: B.mfc_relative_u(0.3, 0.2, 0.005, 0.001),      # setpoint above full scale
    lambda: B.mfc_relative_u(0.1, 0.2, 0.0, 0.0),           # empty specification
    lambda: B.mfc_relative_u(0.1, 0.2, None, 0.001),
    lambda: B.mfc_relative_u(True, 0.2, 0.005, 0.001),
    lambda: B.gravimetric_min_mass_g(1.0, 0.0),
    lambda: B.rate_of_rise_Pa_s(0.1, None, 293.15),
    lambda: B.discharge_current_upper_bound_A(1500, float("nan")),
    lambda: B.rss(),
])
def test_missing_inputs_raise(call):
    with pytest.raises(B.InputMissing):
        call()


def test_build_does_not_need_parallel_lanes():
    # build() must work whether or not the parallel lanes exist; it never reads them.
    src = BUILDER.read_text()
    body = src.split("def build()")[1].split("def _fmt")[0]
    assert "resolve_parallel" not in body
    assert isinstance(B.resolve_parallel(), dict)
