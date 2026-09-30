"""Tests for the P4 anode / collector materials framework (docs/experiments/hall_icp/p4_anode_materials/, follow-on
fo_a9_6_p4_anode_materials, trigger T_A9_6_P4_ANODE_MATERIALS; owner directive A9.6 sec. 10, A9.2 sec. 3-4).

Checks: byte-for-byte reproduction; pins verified, governance never pinned; fixed statuses; fail-closed screening (missing
property / requirement -> INCOMPLETE_EVIDENCE, UNRESOLVED thermal forces CR-01 incomplete, out-of-domain distinct from a
violation, unit mismatch raises, synthetic evidence refused / never mixed); no PASS / selection anywhere; final material
OPEN for every input; Pareto view informational and incomplete rows not comparable; datasheet values tied to verbatim
rows; required sections (a)-(f); no invented source for sputtering.
Run: python -m pytest -q tests/test_p4_anode_materials.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "experiments" / "hall_icp" / "p4_anode_materials"
OUT_JSON = LANE / "p4_anode_materials_v1.json"
OUT_MD = LANE / "P4_ANODE_MATERIALS.md"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


B = _load("build_p4_anode_materials", LANE / "build_p4_anode_materials.py")
S = _load("p4_screening", LANE / "p4_screening.py")


@pytest.fixture(scope="module")
def doc():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


def _req(**kw):
    r = {"id": "RQ-T", "criterion": "CR-05", "application": "APP-ANODE", "property": "electrical_resistivity",
         "kind": "max", "value": 2e-6, "unit": "ohm*m", "status": "DEFINED_FROM_EVIDENCE", "source": "synthetic",
         "domain": ["bulk_property"]}
    r.update(kw)
    return r


def _prop(**kw):
    p = {"id": "PR-T", "candidate": "CAND-X", "property": "electrical_resistivity", "value_si": 1e-6,
         "unit_si": "ohm*m", "condition": {"temperature_C": 20}, "domain": ["bulk_property"], "source_id": "SYN",
         "locator": "synthetic", "quantity_type": "measured", "evidence_level": "synthetic",
         "admissible_for_gate": True, "synthetic": True}
    p.update(kw)
    return p


# ----------------------------------------------------------------------------------------------- reproduction / pins
def test_builder_reproduces_outputs():
    js, md = B.render()
    assert OUT_JSON.read_text(encoding="utf-8") == js
    assert OUT_MD.read_text(encoding="utf-8") == md
    assert B.main(["--check"]) == 0


def test_pins_match_files_and_governance_never_pinned(doc):
    for k, p in doc["pins"].items():
        h = hashlib.sha256((REPO / p["path"]).read_bytes()).hexdigest()
        assert h == p["sha256"], k
    pinned = {p["path"] for p in doc["pins"].values()}
    for g in ("lane_registry", "trigger_registry", "fired_triggers", "trigger_ledger", "runtime_state"):
        assert not any(g in p for p in pinned)


def test_pin_mismatch_refused(monkeypatch):
    bad = dict(B.PINS)
    path, _sha, role = bad["R8"]
    bad["R8"] = (path, "0" * 64, role)
    monkeypatch.setattr(B, "PINS", bad)
    with pytest.raises(B.BuildError):
        B.load_pins()


def test_json_parses_and_sections_present(doc):
    for k in ("items", "interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
              "m16_impact", "criteria", "candidates", "gate_matrix", "pareto_views", "test_plan"):
        assert doc[k], k
    for it in doc["items"]:
        for f in ("id", "value", "units", "basis", "source", "evidence_class", "status", "freeze_point"):
            assert f in it
        assert it["freeze_point"] in B.FREEZE_POINTS
    dirs = {i["direction"] for i in doc["interface_demands"]}
    assert any(d.startswith("P4 <-") for d in dirs) and any(d.startswith("P4 ->") for d in dirs)


# ----------------------------------------------------------------------------------------------- fixed statuses
def test_fixed_statuses(doc):
    fs = doc["fixed_statuses"]
    assert fs["316L_FLIGHT_ANODE"]["status"] == "REJECTED_AS_CURRENT_BASELINE"
    assert fs["FINAL_ANODE_MATERIAL"]["status"] == "OPEN"
    assert fs["ANODE_THERMAL_CLOSURE"]["status"] == "UNRESOLVED"
    assert fs["ICP_COUPLED_THERMAL"]["status"] == "UNRESOLVED"
    assert fs["FINAL_COLLECTOR_MATERIAL"]["status"] == "OPEN"
    assert set(doc["final_material_status"].values()) == {"OPEN"}
    c01 = next(c for c in doc["candidates"] if c["id"] == "CAND-01")
    assert "REJECTED_AS_CURRENT_BASELINE" in c01["owner_status"]["APP-ANODE"]


def test_criteria_cover_a96_list(doc):
    names = " ".join(c["name"] for c in doc["criteria"]).lower()
    for w in ("continuous-use temperature", "oxidation", "atomic-oxygen", "sputtering", "electrical conductivity",
              "thermal conductivity", "fabrication", "mass", "provenance"):
        assert w in names, w


# ----------------------------------------------------------------------------------------------- no PASS / no selection
def test_no_pass_or_selection_anywhere(doc):
    S.assert_no_forbidden_status(doc)
    outs = {m["outcome"] for m in doc["gate_matrix"]}
    assert outs == {"INCOMPLETE_EVIDENCE"}
    assert set(doc["candidate_screening_states"].values()) == {"INCOMPLETE_EVIDENCE"}
    assert "weight" not in json.dumps(doc["criteria"]).lower()
    for v in doc["pareto_views"]:
        assert v["label"] == "INFORMATIONAL_NOT_A_SELECTION"


def test_forbidden_status_detector():
    with pytest.raises(S.ScreeningError):
        S.assert_no_forbidden_status({"a": [{"status": "PASS"}]})
    with pytest.raises(S.ScreeningError):
        S.assert_no_forbidden_status({"final": "selected"})


def test_final_material_open_even_if_all_gates_satisfied():
    st = S.candidate_screening_state(["GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN"] * 8)
    assert st == "NOT_SCREENED_OUT"
    assert S.final_material_status({"x": st}) == "OPEN"


# ----------------------------------------------------------------------------------------------- fail-closed gates
def test_missing_property_incomplete():
    assert S.evaluate_gate(_req(), None)[0] == "INCOMPLETE_EVIDENCE"


def test_property_value_none_incomplete():
    assert S.evaluate_gate(_req(), _prop(value_si=None))[0] == "INCOMPLETE_EVIDENCE"


def test_non_admissible_property_incomplete():
    assert S.evaluate_gate(_req(), _prop(admissible_for_gate=False))[0] == "INCOMPLETE_EVIDENCE"


def test_unevidenced_requirement_incomplete():
    assert S.evaluate_gate(_req(value=None), _prop())[0] == "INCOMPLETE_EVIDENCE"
    assert S.evaluate_gate(_req(status="TBD"), _prop())[0] == "INCOMPLETE_EVIDENCE"
    assert S.evaluate_gate(_req(source=""), _prop())[0] == "INCOMPLETE_EVIDENCE"


def test_missing_field_raises():
    p = _prop()
    del p["locator"]
    with pytest.raises(S.ScreeningError):
        S.evaluate_gate(_req(), p)
    r = _req()
    del r["domain"]
    with pytest.raises(S.ScreeningError):
        S.evaluate_gate(r, _prop())


def test_unit_mismatch_raises():
    with pytest.raises(S.ScreeningError):
        S.evaluate_gate(_req(), _prop(unit_si="uOhm*m"))


def test_property_mismatch_raises():
    with pytest.raises(S.ScreeningError):
        S.evaluate_gate(_req(), _prop(property="density", unit_si="ohm*m"))


def test_out_of_domain_distinct_from_violation():
    o, _ = S.evaluate_gate(_req(domain=["O_bearing_plasma_service"]), _prop())
    assert o == "OUT_OF_DOMAIN"


def test_gate_satisfied_and_violated_when_both_evidenced():
    assert S.evaluate_gate(_req(), _prop())[0] == "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN"
    assert S.evaluate_gate(_req(), _prop(value_si=3e-6))[0] == "GATE_VIOLATED_BY_EVIDENCE"
    assert S.candidate_screening_state(["GATE_VIOLATED_BY_EVIDENCE", "INCOMPLETE_EVIDENCE"]) == \
        "SCREENED_OUT_BY_EVIDENCE"
    assert S.candidate_screening_state(["OUT_OF_DOMAIN", "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN"]) == \
        "INCOMPLETE_EVIDENCE"
    assert S.candidate_screening_state([]) == "INCOMPLETE_EVIDENCE"


def test_thermal_gate_unresolved_forces_incomplete():
    r = _req(criterion="CR-01", property="T_validated_continuous", kind="min_with_margin", value=50.0, unit="K",
             status="OWNER_GIVEN")
    p = _prop(property="T_validated_continuous", value_si=2000.0, unit_si="K")
    assert S.evaluate_gate(r, p, thermal_closure_status="UNRESOLVED", operating_temperature=300.0)[0] == \
        "INCOMPLETE_EVIDENCE"
    assert S.evaluate_gate(r, p, thermal_closure_status="CLOSED_BY_EVIDENCE", operating_temperature=None)[0] == \
        "INCOMPLETE_EVIDENCE"
    with pytest.raises(S.ScreeningError):
        S.evaluate_gate(r, p)                      # no default thermal status
    # margin rule T_op <= T_valid - 50 K (synthetic)
    assert S.evaluate_gate(r, p, thermal_closure_status="CLOSED_BY_EVIDENCE", operating_temperature=1950.0)[0] == \
        "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN"
    assert S.evaluate_gate(r, p, thermal_closure_status="CLOSED_BY_EVIDENCE", operating_temperature=1950.1)[0] == \
        "GATE_VIOLATED_BY_EVIDENCE"


def test_synthetic_refused_and_never_mixed():
    with pytest.raises(S.ScreeningError):
        S.check_evidence_mode([_prop()], synthetic_mode=False)
    with pytest.raises(S.ScreeningError):
        S.check_evidence_mode([_prop(), _prop(id="PR-U", synthetic=False)], synthetic_mode=True)
    with pytest.raises(S.ScreeningError):
        S.check_evidence_mode([_prop(synthetic=False)], synthetic_mode=True)
    S.check_evidence_mode([_prop()], synthetic_mode=True)


def test_builder_refuses_synthetic_property(monkeypatch):
    real = B.build_property_records

    def poisoned():
        out = real()
        out[0] = dict(out[0], synthetic=True)
        return out
    monkeypatch.setattr(B, "build_property_records", poisoned)
    with pytest.raises(B.SCR.ScreeningError):
        B.build_doc(B.load_pins())


def test_builder_thermal_gate_incomplete_even_with_synthetic_limit(doc):
    reqs = [r for r in doc["requirements"] if r["criterion"] == "CR-01"]
    assert reqs and all(r["status"] == "OWNER_GIVEN" and r["value"] == 50.0 for r in reqs)
    cells = [m for m in doc["gate_matrix"] if m["criterion"] == "CR-01"]
    assert cells and all(m["outcome"] == "INCOMPLETE_EVIDENCE" for m in cells)


# ----------------------------------------------------------------------------------------------- Pareto
def test_pareto_incomplete_not_comparable():
    v = S.pareto_view(["A", "B", "C"], {"A": {"x": 1, "y": 1}, "B": {"x": 2, "y": 2}, "C": {"x": None, "y": 0}},
                      {"x": "min", "y": "min"})
    assert v["non_dominated"] == ["A"] and v["dominated"] == {"B": ["A"]}
    assert v["not_comparable"] == {"C": "NOT_COMPARABLE_INCOMPLETE_EVIDENCE"}
    with pytest.raises(S.ScreeningError):
        S.pareto_view(["A"], {"A": {"x": 1}}, {"x": "best"})


def test_pareto_views_carry_caveats(doc):
    for v in doc["pareto_views"]:
        assert any("REJECTED_AS_CURRENT_BASELINE" in c for c in v["caveats"])
        assert len(v["compared"]) + len(v["not_comparable"]) == len(doc["candidates"])


# ----------------------------------------------------------------------------------------------- evidence discipline
def test_property_records_tied_to_verbatim_and_sources(doc):
    srcs = {s["id"]: s for s in doc["source_register"]["new_this_lane"]}
    for p in doc["property_records"]:
        s = srcs[p["source_id"]]
        assert s["url"].startswith("https://") and s["accessed"] == "2026-09-30" and len(s["pdf_sha256"]) == 64
        assert p["value_reported"].split()[0].split("-")[0].strip("(") in p["verbatim_row"]
        assert p["admissible_for_gate"] is False and p["admissibility_reason"]
        assert p["synthetic"] is False
        if p["property"] == "melting_range":
            assert p["value_si"] is None


def test_verbatim_check_fails_closed():
    with pytest.raises(B.BuildError):
        B.check_verbatim("8.03", "Density 0.29 (8.04)", "(8.04)")
    with pytest.raises(B.BuildError):
        B.check_verbatim("8.03", "Density 0.29 (8.03)", "(8.30)")


def test_si_conversions(doc):
    by = {p["id"]: p for p in doc["property_records"]}
    assert by["PR-001"]["value_si"] == 8030.0
    assert by["PR-002"]["value_si"] == pytest.approx(7.4e-7)
    assert by["PR-012"]["value_si"] == pytest.approx(1.03e-6)
    assert by["PR-021"]["value_si"] == 8110.0


def test_unpopulated_rows_have_no_values(doc):
    populated = {p["candidate"] for p in doc["property_records"]}
    assert populated == {"CAND-01", "CAND-02A", "CAND-03A"}
    for c in doc["candidates"]:
        assert c["row_population"] == ("DATASHEET_BULK_PROPERTIES_ONLY" if c["id"] in populated else "UNPOPULATED")


def test_qualitative_links_never_gate_admissible(doc):
    assert doc["evidence_links"]
    for e in doc["evidence_links"]:
        assert e["admissible_for_gate"] is False and e["locator"]


def test_no_sputter_value_carried(doc):
    assert not any(p["property"].startswith("sputter") for p in doc["property_records"])
    nifs = next(s for s in doc["source_register"]["new_this_lane"] if s["id"] == "NIFS_DATA_23")
    assert nifs["extraction"].startswith("NONE")


def test_h2_context_value_not_admissible(doc):
    it = next(i for i in doc["items"] if i["id"] == "IT-10")
    assert it["status"] == "CONTEXT_NOT_ADMISSIBLE"
    it9 = next(i for i in doc["items"] if i["id"] == "IT-09")
    assert it9["value"].startswith("TBD") and "p3_coupled_thermal" in it9["value"]


def test_owner_answers_copied_verbatim(doc):
    ans = json.loads((REPO / B.PINS["ANS"][0]).read_text(encoding="utf-8"))["answers"]
    by = {a["row"]: a["owner_answer_verbatim"] for a in ans}
    for o in doc["owner_answers_applied"]:
        if " row " in o["decision"]:
            row = int(o["decision"].rsplit(" row ", 1)[1])
            assert o["owner_answer_verbatim"] == by[row]


def test_open_questions_new_and_tbd_owner(doc):
    state = json.loads((REPO / B.PINS["OQ3"][0]).read_text(encoding="utf-8"))
    existing = {r["id"] for r in state["rows"]}
    for q in doc["open_owner_questions"]:
        assert q["id"] not in existing and q["status"] == "TBD_OWNER" and q["admissible_alternatives"]


def test_m16_no_readiness_change(doc):
    assert {m["m16_row"] for m in doc["m16_impact"]} == {18, 20, 21}
    for m in doc["m16_impact"]:
        assert m["readiness_change"].startswith("NONE")


def test_parallel_lanes_referenced_only_as_pending(doc):
    for v in doc["parallel_lanes_pending"].values():
        assert v.startswith("PENDING ")


def test_no_xe_ledger_substring():
    for f in LANE.glob("*.py"):
        assert "xe_ledger" not in f.read_text(encoding="utf-8")


def test_mutated_pinned_evidence_refused(monkeypatch):
    pins = B.load_pins()
    bad = copy.deepcopy(pins)
    bad["A96"]["summary"]["fixed_statuses"]["FINAL_ANODE_MATERIAL"] = "CLOSED"
    with pytest.raises(B.BuildError):
        B.build_fixed_statuses(bad)
    bad2 = copy.deepcopy(pins)
    bad2["R8"]["evidence"] = [e for e in bad2["R8"]["evidence"] if e["source_id"] != "SMOLIK2000"]
    with pytest.raises(B.BuildError):
        B.build_evidence_links(bad2)
