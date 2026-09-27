"""Tests for the mass / thermal / life / start-up veto layer (fo_veto_layer).

docs/architecture_comparison/veto_layer/build_veto_layer.py is loaded by path. The tests check byte-for-byte
reproduction, schema validity, pin enforcement (missing / changed inputs raise, no fallback), the status rules, that an
elimination can only come from the lane-24 evaluator, that every number traces to a pinned input, and that no Hall
closure, screening candidate, ranking or winner appears.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "docs", "architecture_comparison", "veto_layer", "build_veto_layer.py")
JSON_FILE = os.path.join(ROOT, "docs", "architecture_comparison", "veto_layer", "veto_layer_v1.json")
MD_FILE = os.path.join(ROOT, "docs", "architecture_comparison", "veto_layer", "VETO_LAYER.md")


def _load():
    spec = importlib.util.spec_from_file_location("build_veto_layer", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vl = _load()


@pytest.fixture(scope="module")
def outs():
    return vl.outputs()


@pytest.fixture(scope="module")
def doc(outs):
    return json.loads(outs[vl.OUT_JSON])


@pytest.fixture(scope="module")
def inputs():
    return vl.load_inputs()


def test_committed_files_reproduce_byte_for_byte(outs):
    for path in (JSON_FILE, MD_FILE):
        with open(path, encoding="utf-8") as f:
            assert f.read() == outs[path], f"{os.path.relpath(path, ROOT)} is stale: rerun the build script"
    assert vl.main(["--check"]) == 0


def test_output_validates_against_schema(doc):
    vl.validate(doc)
    bad = copy.deepcopy(doc)
    bad["cells"]["hall_only"]["mass"]["status"] = "PASS"
    with pytest.raises(ValueError):
        vl.validate(bad)


def test_changed_or_missing_input_raises_without_fallback():
    pins = list(vl.PINS)
    rel, sha, lane, role = pins[1]
    pins[1] = (rel, "0" * 64, lane, role)
    with pytest.raises(vl.InputError, match="changed input"):
        vl.load_inputs(vl.ROOT, tuple(pins))
    pins = list(vl.PINS) + [("docs/does_not_exist_v1.json", "0" * 64, lane, "synthetic")]
    with pytest.raises(vl.InputError, match="missing input"):
        vl.load_inputs(vl.ROOT, tuple(pins))
    with pytest.raises(vl.InputError):
        vl.build(vl.ROOT, tuple(pins))


def test_every_input_is_pinned_with_a_lane(doc):
    assert len(doc["inputs"]) == len(vl.PINS)
    lanes = {i["lane"] for i in doc["inputs"]}
    for need in ("lane_21_mass_bom", "lane_15_thermal_life", "lane_24_hard_gates", "lane_19_cathode_integration",
                 "lane_20_ppu_magnet", "lane_22_scaling"):
        assert need in lanes
    for i in doc["inputs"]:
        assert os.path.isfile(os.path.join(ROOT, i["path"]))
        assert len(i["sha256"]) == 64 and len(i["lane_commit"]) == 40


def test_classify_rules():
    assert vl.classify([]) == "UNDETERMINED"
    assert vl.classify([{"side": "not_fail"}]) == "NO_VETO_WITHIN_EVIDENCE"
    assert vl.classify([{"side": "pass"}, {"side": "undecided"}]) == "NO_VETO_WITHIN_EVIDENCE"
    assert vl.classify([{"side": "not_fail"}, {"side": "fail"}]) == "VETO_CANDIDATE"


def test_elimination_only_through_the_lane24_evaluator():
    crit = [{"gate": "G3_mass"}]
    clean = {"architectures": {"rf_hall": {"eliminated": False, "elimination_basis": []}}}
    assert vl.final_status("VETO_CANDIDATE", "rf_hall", crit, clean) == "VETO_CANDIDATE"
    other_gate = {"architectures": {"rf_hall": {"eliminated": True, "elimination_basis": [{"gate": "G1_thrust"}]}}}
    assert vl.final_status("VETO_CANDIDATE", "rf_hall", crit, other_gate) == "VETO_CANDIDATE"
    failed = {"architectures": {"rf_hall": {"eliminated": True, "elimination_basis": [{"gate": "G3_mass"}]}}}
    assert vl.final_status("VETO_CANDIDATE", "rf_hall", crit, failed) == vl.FINAL_ONLY
    assert vl.final_status("UNDETERMINED", "rf_hall", crit, failed) == "UNDETERMINED"


def test_only_fail_sufficient_bases_make_a_veto_candidate(inputs):
    matrix = inputs["docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json"]
    cinfo = vl.criteria_info(matrix)
    inp = copy.deepcopy(inputs)
    reg = "docs/architecture_comparison/hard_gates/evidence_register_v1.json"
    base = {"criterion": "G3.mass_mev", "architectures": ["ecr_hall"], "value": {"kind": "lower_bound", "value": 55.0}}
    inp[reg]["items"] = [dict(base, id="SYN-lit", basis="measurement_similar_hardware"),
                         dict(base, id="SYN-assume", basis="assumption")]
    assert vl.classify(vl.eligible_bounds("mass", "ecr_hall", inp, cinfo)) == "UNDETERMINED"
    inp[reg]["items"].append(dict(base, id="SYN-bound", basis="hard_physical_bound"))
    b = vl.eligible_bounds("mass", "ecr_hall", inp, cinfo)
    assert [x["id"] for x in b] == ["SYN-bound"] and vl.classify(b) == "VETO_CANDIDATE"
    assert vl.classify(vl.eligible_bounds("mass", "hall_only", inp, cinfo)) == "UNDETERMINED"
    inp[reg]["items"] = [dict(base, id="SYN-low", basis="hard_physical_bound",
                              value={"kind": "lower_bound", "value": 12.0})]
    assert vl.classify(vl.eligible_bounds("mass", "ecr_hall", inp, cinfo)) == "NO_VETO_WITHIN_EVIDENCE"


def test_mass_screen_feeds_the_mass_cell(inputs):
    matrix = inputs["docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json"]
    cinfo = vl.criteria_info(matrix)
    bom = "docs/architecture_comparison/mass_bom/mass_bom_v1.json"
    assert vl.classify(vl.eligible_bounds("mass", "rf_hall", inputs, cinfo)) == "UNDETERMINED"
    inp = copy.deepcopy(inputs)
    scr = inp[bom]["plausibility_screen"]["architectures"]["rf_hall"]
    scr.update(items_with_lower_bound=["rf_source"], cbe_margin_free_lower_bound_kg=41.0,
               verdict="EXCEEDS_LIMIT_MARGIN_FREE", g3_fail_evidence=True)
    assert vl.classify(vl.eligible_bounds("mass", "rf_hall", inp, cinfo)) == "VETO_CANDIDATE"
    scr.update(cbe_margin_free_lower_bound_kg=9.0, verdict="NOT_EXCLUDED_PARTIAL_COVERAGE", g3_fail_evidence=False)
    assert vl.classify(vl.eligible_bounds("mass", "rf_hall", inp, cinfo)) == "NO_VETO_WITHIN_EVIDENCE"


def test_current_result_no_veto_no_elimination(doc):
    assert doc["veto_candidates"] == [] and doc["eliminated_within_tested_envelope"] == []
    ev = doc["lane24_evaluation"]
    assert ev["eliminated"] == [] and ev["admitted_members"] == []
    for a in vl.ARCHITECTURES:
        assert ev["architectures"][a]["eliminated"] is False
        for d in vl.DIMENSIONS:
            cell = doc["cells"][a][d]
            assert cell["status"] in vl.STATUSES
            if cell["final_status"] == vl.FINAL_ONLY:
                assert ev["architectures"][a]["eliminated"]
            if cell["status"] == "UNDETERMINED":
                assert cell["missing_inputs"], f"{a}/{d}: UNDETERMINED must name missing inputs"
                assert cell["margin"]["kind"] == "not_computable"
            for m in cell["missing_inputs"]:
                assert m["blocking"] and all(isinstance(x, str) and x for x in m["blocking"])


def test_submitted_risk_indicators_are_not_verdict_bearing(doc):
    ev = doc["lane24_evaluation"]
    assert ev["items_submitted"], "risk indicators with a lane-24 metric must be submitted to the evaluator"
    ris = {r["id"]: r for r in doc["risk_indicators"]}
    for iid in ev["items_submitted"]:
        ri = ris[iid.removeprefix("veto.")]
        assert ri["lane24_basis"] in ("measurement_similar_hardware", "engineering_estimate")
        for a in ri["architectures"]:
            nvb = {x["id"] for x in ev["architectures"][a]["items_not_verdict_bearing"]}
            assert iid in nvb


def test_risk_indicators_trace_to_pinned_inputs(doc, inputs):
    pinned = {p[0] for p in vl.PINS}
    for ri in doc["risk_indicators"]:
        assert ri["source_refs"]
        for s in ri["source_refs"]:
            assert s["file"] in pinned
        assert ri["evidence_class"] and ri["why_not_verdict_bearing"] and ri["to_become_verdict_bearing"]
        if ri["scope"] == "common_mode":
            assert ri["architectures"] == list(vl.ARCHITECTURES)
        else:
            assert len(ri["architectures"]) == 1 and ri["architectures"][0] != "hall_only"
        if ri["conditional_margin"] is not None:
            assert ri["conditional_margin"]["relation"]
    ris = {r["id"]: r for r in doc["risk_indicators"]}
    der = inputs["docs/architecture_comparison/cathode_integration/cathode_integration_derived_v1.json"]
    kg = [r["xe_kg_over_min_firing"] for r in der["xe_mass_vs_rfp"]["reference_flows"]]
    assert ris["RI-MASS-CATHODE-XE"]["values"]["xe_kg_over_min_firing"] == [min(kg), max(kg)]
    lim = doc["rfp_limits_as_recorded"]["G3.mass_mev"]["threshold"]
    assert ris["RI-MASS-CATHODE-XE"]["conditional_margin"]["range"] == [pytest.approx(lim - max(kg)),
                                                                        pytest.approx(lim - min(kg))]
    hs = inputs["docs/evidence/hall_sustainment/hall_sustainment_matrix.json"]
    e07 = next(e for e in hs["entries"] if e["id"] == "E07")
    life = next(q for q in e07["quantities"] if q["name"].startswith("ceramic-erosion-compatible lifetime"))
    assert ris["RI-LIFE-HALL-CHANNEL-AIR-EROSION"]["values"]["lifetime_estimate_h"] == life["value"]
    fire = doc["rfp_limits_as_recorded"]["G4.firing_life"]["threshold"]
    assert ris["RI-LIFE-HALL-CHANNEL-AIR-EROSION"]["conditional_margin"]["range"] == [
        pytest.approx(life["value"][0] / fire, rel=1e-5), pytest.approx(life["value"][1] / fire, rel=1e-5)]


def test_common_mode_vs_specific_split(doc):
    cm = doc["common_mode_vs_architecture_specific"]
    assert "RI-MASS-CATHODE-XE" in cm["common_mode_risk_indicators"]
    assert "RI-LIFE-HALL-CHANNEL-AIR-EROSION" in cm["common_mode_risk_indicators"]
    assert cm["architecture_specific_risk_indicators"]["hall_only"] == []
    assert cm["architecture_specific_risk_indicators"]["rf_hall"]
    assert cm["architecture_specific_risk_indicators"]["ecr_hall"]


def test_gate_mapping_respects_lane24_rules(doc):
    for a in vl.ARCHITECTURES:
        crit = {c["criterion"]: c for d in vl.DIMENSIONS for c in doc["cells"][a][d]["criteria"]}
        assert crit["G3.mass_mev"]["can_eliminate_on_this_dimension"] is True
        assert crit["P1.thermal_margin"]["can_eliminate_on_this_dimension"] is False     # PROPOSED gate
        assert crit["P2.cathode_life"]["can_eliminate_on_this_dimension"] is False
        assert crit["G2.bus_power_max"]["can_eliminate_on_this_dimension"] is False      # start-up not in fail cover
    els = {a: doc["cells"][a]["mass"]["criteria"][0]["elements"] for a in vl.ARCHITECTURES}
    assert "rf_source" in els["rf_hall"] and "rf_source" not in els["hall_only"]
    assert {"ecr_source", "ecr_magnet"} <= set(els["ecr_hall"])


def test_no_closure_screening_winner_or_filled_tbd(outs, doc):
    text = outs[vl.OUT_JSON] + outs[vl.OUT_MD]
    assert "sgb-screen-0" not in text
    low = text.lower()
    for word in ("winner\":", "ranking\":", "\"rank\"", "best architecture", "recommended architecture"):
        assert word not in low
    assert "never filled here" in outs[vl.OUT_JSON]
    for a in vl.ARCHITECTURES:
        startup = " ".join(m["input"] + m["requires"] for m in doc["cells"][a]["startup"]["missing_inputs"])
        assert "compressor bus draw" in startup
    assert doc["milestones"]["supports"] == ["A"]
    assert all(p["status"] == "PROPOSED" for p in doc["proposed_for_owner"])


LANE09_MATRIX = "docs/evidence/hall_sustainment/hall_sustainment_matrix.json"
LANE09_SHA = "76bba594eb1175b2186a8066b38665a2ce5e4cf77487c90f4af2e187a0b82dcc"


def test_lane09_matrix_pinned_to_repaired_version_and_mismatch_fails():
    """Pinned-hash mismatch must raise (a test failure, never a skip)."""
    pin = [p for p in vl.PINS if p[0] == LANE09_MATRIX]
    assert len(pin) == 1 and pin[0][1] == LANE09_SHA
    assert pin[0][2] == ("lane_09_hall_sustainment", "f458811a5720a20216379dd1f701a54d21faf2b6")
    pins = [(r, ("f" * 64 if r == LANE09_MATRIX else s), l, ro) for r, s, l, ro in vl.PINS]
    with pytest.raises(vl.InputError, match="changed input"):
        vl.build(vl.ROOT, tuple(pins))


def test_echt_historical_unsupported_status_is_carried(doc, inputs):
    hs = inputs[LANE09_MATRIX]
    status = vl._hs_repository_status(hs)
    assert status.get("E03", {}).get("status") == "HISTORICAL_UNSUPPORTED"
    assert status.get("E04", {}).get("status") == "HISTORICAL_UNSUPPORTED"
    # every source_ref citing a lane-09 entry with a repository_status carries it; none lacks it
    for ri in doc["risk_indicators"]:
        for ref in ri["source_refs"]:
            if ref["file"] != LANE09_MATRIX:
                continue
            eid = ref["path"].split("[", 1)[1].split("]", 1)[0]
            if eid in status:
                assert ref.get("repository_status") == status[eid]["status"]
            else:
                assert "repository_status" not in ref
    notes = [n for n in doc["not_used"] if "repository_status" in n["what"]]
    assert len(notes) == 1 and "E03: HISTORICAL_UNSUPPORTED" in notes[0]["what"]
    assert "E04: HISTORICAL_UNSUPPORTED" in notes[0]["what"]
    # a synthetic citation of E03 must get the status attached
    ris = [{"id": "SYN", "lane24_basis": "measurement_similar_hardware",
            "source_refs": [{"file": LANE09_MATRIX, "path": "entries[E03].observations"}]}]
    vl._carry_hs_repository_status(ris, hs, LANE09_MATRIX)
    assert ris[0]["source_refs"][0]["repository_status"] == "HISTORICAL_UNSUPPORTED"


# lane_15_thermal_life repaired (G11 wall-flux admission / wall_life_trustworthy gate), re-verified: 66ff83b
LANE15_COMMIT = "66ff83be5506097025905332b0b28e9e3fe4e19e"
LANE15_PINS = {
    "abep_sim/thermal_life.py": "dce2048233746ecc596866c1d561c8828f820c7960b9778db0d6d66a9c86d83c",
    "schemas/thermal_life/limits_v1.json": "0df363f76dcb6efcef41bc0a07e1775b6255c2c9d84b185228862958ef827dbb",
    "schemas/thermal_life/inputs_v1.json": "937e5c643ef6d1b567319ad788915cd8e9f9b6ab78fc8df91454bdb300f0777f",
    "docs/thermal_life/THERMAL_LIFE_FRAMEWORK.md":
        "c07c9441505669ee6d4c3fcd3cf54d2e03dc749ea991f99098e64c193d6f134e",
}


@pytest.mark.parametrize("rel", sorted(LANE15_PINS))
def test_lane15_files_pinned_to_repaired_version_and_mismatch_fails(rel):
    """Pinned-hash mismatch must raise (a test failure, never a skip)."""
    pin = [p for p in vl.PINS if p[0] == rel]
    assert len(pin) == 1 and pin[0][1] == LANE15_PINS[rel]
    assert pin[0][2] == ("lane_15_thermal_life", LANE15_COMMIT)
    assert vl._sha256_file(os.path.join(vl.ROOT, rel)) == LANE15_PINS[rel]
    pins = [(r, ("f" * 64 if r == rel else s), l, ro) for r, s, l, ro in vl.PINS]
    with pytest.raises(vl.InputError, match="changed input"):
        vl.build(vl.ROOT, tuple(pins))


def test_no_wall_flux_is_read_or_passed(doc, inputs):
    """The veto layer never forms a wall-flux verdict: the G11 gate exists, both inputs are TBD, no admitted member,
    and the build script never imports thermal_life or calls its wall-flux / feasibility entry points."""
    g = vl.wall_flux_gate_status(inputs)
    assert g["admitted_members"] == 0 and g["admissible_kinds"] == ["admitted_hallmap", "measured_hardware"]
    assert any(n["why"] == g["statement"] for n in doc["not_used"])
    import ast
    with open(SCRIPT, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):                     # code, not prose: imports and call targets
        if isinstance(node, ast.Import):
            assert not any("thermal_life" in a.name or "hall_map" in a.name for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not any(a.name in ("thermal_life", "hall_map") for a in node.names)
            assert "thermal_life" not in (node.module or "") and "hall_map" not in (node.module or "")
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            assert name not in ("hallmap_wall_inputs", "check_feasibility", "HallMap")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "sgb-screen-0" not in node.value     # no concrete screening-candidate id is ever referenced
    # a contract whose wall-flux input is no longer TBD, or an ensemble with a member, must stop the build
    bad = copy.deepcopy(inputs)
    bad["schemas/thermal_life/inputs_v1.json"]["components"]["hall_discharge"]["inputs"]["wall_ion_flux_m2s"]["now"] = "x"
    with pytest.raises(vl.InputError):
        vl.wall_flux_gate_status(bad)
    bad = copy.deepcopy(inputs)
    bad["hallthruster_bridge/ensemble/transport_ensemble_v0.json"]["members"] = [{"id": "m"}]
    with pytest.raises(vl.InputError):
        vl.wall_flux_gate_status(bad)
    for arch in vl.ARCHITECTURES:
        for dim in ("thermal", "life_firing"):
            assert doc["cells"][arch][dim]["status"] == "UNDETERMINED"
