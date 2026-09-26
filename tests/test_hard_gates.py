"""Architecture hard-gate matrix and evaluator (abep_sim/hard_gates.py; docs/architecture_comparison/hard_gates/).

Every evidence item built here is a SYNTHETIC test fixture (ids 'SYN-*', sources 'SYNTHETIC test fixture', obviously fake
hashes and member ids): it exercises the verdict logic and is never evidence about any architecture. The committed
evidence register is empty, and the committed status file must say so.

Synthetic admitted members ('SYN-member-*') exist only in an injected SYNTHETIC ensemble (evaluate(..., ensemble=)), and
the derivation script the fixtures cite exists only in a temporary SYNTHETIC repository root (evaluate(..., repo_root=)).
The repository's own ensemble (credible set empty, screening candidates sgb-screen-*) is used wherever a test checks the
real admission guard.

No other lane's module or file is required: shared contracts are checked only when they happen to be importable.
"""
from __future__ import annotations

import atexit
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

from abep_sim import hard_gates as hg

MATRIX = hg.load_matrix()
SCHEMA = hg.load_schema()
CRIT = {c["id"]: (g["id"], c) for g in MATRIX["gates"] for c in g["criteria"]}
PIN = MATRIX["hall_pin"]["hallthruster_commit"]
FAKE_SHA = "0" * 64
SYN = "SYNTHETIC test fixture"
SYN_SCRIPT = "scripts/SYNTHETIC_bound_fixture.py"
SYN_ROOT = tempfile.mkdtemp(prefix="hard_gates_synthetic_root_")
atexit.register(shutil.rmtree, SYN_ROOT, ignore_errors=True)
os.makedirs(os.path.join(SYN_ROOT, "scripts"))
with open(os.path.join(SYN_ROOT, SYN_SCRIPT), "w", encoding="utf-8") as _f:
    _f.write("# SYNTHETIC test fixture: stands in for a committed derivation script; computes nothing\n")
SYN_ENSEMBLE = {"members": [{"ensemble_member_id": "SYN-member-a"}, {"ensemble_member_id": "SYN-member-b"}],
                "screening_candidates": [{"ensemble_member_id": "SYN-screen-x"}]}


def evaluate(arch, evidence, **kw):
    """hg.evaluate with the SYNTHETIC ensemble and repository root (overridable)."""
    kw.setdefault("ensemble", SYN_ENSEMBLE)
    kw.setdefault("repo_root", SYN_ROOT)
    return hg.evaluate(arch, evidence, **kw)


def evaluate_all(evidence, **kw):
    kw.setdefault("ensemble", SYN_ENSEMBLE)
    kw.setdefault("repo_root", SYN_ROOT)
    return hg.evaluate_all(evidence, **kw)


_DEFAULTS = {
    "hard_physical_bound": ("model-derived", 4),
    "measurement_vyovrinda": ("measured", 1),
    "measurement_same_hardware": ("measured", 2),
    "model_closure_independent": ("model-derived", 4),
    "model_admitted_closure": ("model-derived", 4),
    "measurement_similar_hardware": ("measured", 3),
    "model_unadmitted_closure": ("model-derived", 6),
    "engineering_estimate": ("model-derived", 6),
    "assumption": ("assumed", 7),
}


def _conditions(crit: dict, arch: str, basis: str, fail_side: bool) -> dict:
    cond = {d: hg._resolve(v, arch) for d, v in crit["envelope"].items()}
    if fail_side:
        cond.update({d: hg._resolve(v, arch) for d, v in crit["fail_must_cover"].items()})
    cond = {d: list(v) for d, v in cond.items()}
    if crit["requires_power_boundary"]:
        cond["power_boundary"] = crit["requires_power_boundary"]
    if basis.startswith("measurement_") and "altitude_km" in cond:
        cond["feed_equivalence"] = f"{SYN}: feed state mapped through the upstream ICD thruster-inlet interface"
    return cond


def item(iid: str, crit_id: str, value: dict, *, archs=("rf_hall",), basis="hard_physical_bound", design=None,
         member=None, fail_side=None, cond=None, **extra) -> dict:
    """A SYNTHETIC evidence item with complete provenance fields; `design` makes it point-design scope."""
    gid, crit = CRIT[crit_id]
    qt, level = _DEFAULTS[basis]
    if fail_side is None:
        fail_side = hg._side(value, crit["comparator"], crit["threshold"],
                             crit.get("threshold_equality_open", False)) == "fail"
    it = {
        "id": iid, "architectures": list(archs), "gate": gid, "criterion": crit_id, "metric": crit["metric"],
        "unit": crit["unit"], "value": value, "basis": basis, "quantity_type": qt, "evidence_level": level,
        "scope": "point_design" if design else "architecture",
        "conditions": cond if cond is not None else _conditions(crit, archs[0], basis, fail_side),
        "hall_closure": {"status": "none"},
        "source": SYN, "uncertainty": SYN, "applicability_domain": SYN, "validation_status": SYN,
        "transformation_chain": SYN,
    }
    if design:
        it["design_id"] = design
    else:
        it["scope_justification"] = f"{SYN}: holds for every design of the architecture"
    if basis in ("hard_physical_bound", "model_closure_independent", "model_admitted_closure"):
        it["derivation_script"] = SYN_SCRIPT
    if basis == "model_closure_independent":
        it["validated_for_this_use"] = True
    flags = {}
    if basis == "model_admitted_closure":
        it["hall_closure"] = {"status": "admitted", "member_id": member, "hall_map_sha256": FAKE_SHA,
                              "hallthruster_commit": PIN}
        flags = {"hall_map_trustworthy": True, "wall_life_trustworthy": True, "numerically_valid": True,
                 "chemistry_trustworthy": True}
    for f in crit.get("required_flags", {}).get(basis, {}).get("fail" if fail_side else "pass", []):
        flags[f] = True
    if flags:
        it["flags"] = flags
    if basis == "model_unadmitted_closure":
        it["hall_closure"] = {"status": "unadmitted", "member_id": member or "sgb-screen-01"}
    it.update(extra)
    return it


UB = lambda v: {"kind": "upper_bound", "value": v}      # noqa: E731
LB = lambda v: {"kind": "lower_bound", "value": v}      # noqa: E731
TRUE = {"kind": "boolean", "value": True}
FALSE = {"kind": "boolean", "value": False}


def verdicts(res: dict) -> dict:
    return {g: r["verdict"] for g, r in res["gates"].items()}


def full_pass_bundle(arch: str, design: str) -> list:
    """SYNTHETIC measurement items that pass every counted criterion of every binding gate for one design."""
    vals = {"G1.thrust_floor": LB(13), "G1.thrust_ceiling": UB(20), "G1.peak_capability_25mN": LB(26),
            "G2.bus_power_max": UB(1400), "G3.mass_mev": UB(39), "G4.firing_life": LB(16000),
            "G5.mission_capability": LB(27000), "G6.sustainment": TRUE, "G6.ignition": TRUE,
            "G7.xenon_operation": TRUE, "G7.feed_switching": TRUE, "G7.mixed_feed": TRUE}
    return [item(f"SYN-{design}-{cid}", cid, v, archs=(arch,), basis="measurement_vyovrinda", design=design)
            for cid, v in vals.items()]


# ------------------------------------------------------------------------------------------------ matrix and schema
def test_schema_uses_only_supported_keywords_and_matrix_validates():
    hg.check_schema_keywords(SCHEMA)
    assert SCHEMA["$schema"].endswith("2020-12/schema")
    assert hg.schema_errors(MATRIX, SCHEMA) == []
    assert MATRIX["schema"] == hg.MATRIX_SCHEMA and MATRIX["status"] == "DRAFT_PENDING_OWNER"


def test_validator_refuses_unimplemented_keywords():
    with pytest.raises(hg.SchemaKeywordError):
        hg.check_schema_keywords({"type": "object", "properties": {"a": {"type": "string", "format": "date"}}})
    with pytest.raises(hg.SchemaKeywordError):
        hg.schema_errors({}, {"type": "object", "dependentRequired": {}})


@pytest.mark.parametrize("mutate, match", [
    (lambda m: m["gates"][0].pop("rfp_source"), "rfp_source"),
    (lambda m: m["gates"][-1].__setitem__("binding", True), "binding"),
    (lambda m: m["gates"][5]["criteria"][0].__setitem__("threshold", 1), "threshold"),
    (lambda m: m["gates"][0]["criteria"][0]["fail_sufficient_bases"].append("model_unadmitted_closure"),
     "not verdict-bearing"),
    (lambda m: m["gates"][2]["criteria"][0]["pass_sufficient_bases"].append("model_admitted_closure"), "leak"),
    (lambda m: m["gates"][0]["criteria"][0].__setitem__("issuable_at", {"FAIL": "B", "PASS": "A"}), "issuable_at"),
    (lambda m: m["gates"][0]["criteria"][1].__setitem__("counts_for_fail", True), "counts_for_fail"),
    (lambda m: m["gates"][0]["criteria"][1].pop("fail_reading_dependence"), "fail_reading_dependence"),
    (lambda m: m["gates"][5]["criteria"][2].__setitem__("counts_for_fail", True), "counts_for_fail"),
    (lambda m: m["gates"][0]["criteria"][1].__setitem__("fail_reading_dependence", "OD99: no such decision"),
     "unknown owner decision"),
    (lambda m: m["gates"][0]["criteria"][0].__setitem__("counts_for_fail", False), "fail_reading_dependence"),
    (lambda m: m["architectures"].__setitem__("hall_ecr", "legacy id"), "hall_ecr"),
    (lambda m: m["gates"][5]["criteria"][2].update(counts_toward_gate=True, fail_reading_dependence="OD5"), "TBD"),
    (lambda m: m["gates"][0]["rfp_source"]["refs"].append("R99"), "unknown RFP record"),
])
def test_broken_matrix_is_rejected(mutate, match):
    m = copy.deepcopy(MATRIX)
    mutate(m)
    with pytest.raises(ValueError, match=match):
        hg.validate_matrix(m, SCHEMA)


def test_architecture_ids_are_exact():
    assert hg.ARCHITECTURES == ("hall_only", "rf_hall", "ecr_hall")
    assert tuple(MATRIX["architectures"]) == hg.ARCHITECTURES
    for bad in ("hall", "Hall_only", "hall_ecr", "rf+hall"):
        with pytest.raises(ValueError):
            evaluate(bad, [])


def test_one_binding_gate_per_rfp_requirement_and_proposed_gates_marked():
    binding = [g for g in MATRIX["gates"] if g["binding"]]
    assert [g["id"] for g in binding] == ["G1_thrust", "G2_bus_power", "G3_mass", "G4_firing_life", "G5_mission",
                                          "G6_ignition_sustainment", "G7_air_xenon"]
    for g in binding:
        assert g["status"] == "RFP"
        assert g["rfp_source"]["verify"].startswith("verify against RFP document")
        for c in g["criteria"]:
            assert c["fail_evidence"] and c["pass_evidence"] and c["definition"]
            assert c["threshold_status"] in ("RFP_AS_RECORDED", "NOT_APPLICABLE", "TBD")
            if c["threshold_status"] == "TBD":
                assert not c["counts_toward_gate"] and c["threshold"] is None
    proposed = [g for g in MATRIX["gates"] if not g["binding"]]
    assert [g["id"] for g in proposed] == ["P1_thermal", "P2_cathode"]
    for g in proposed:
        assert g["status"] == "PROPOSED" and "PROPOSED" in g["title"] and g["proposal"]["owner_decision"]
    # every numeric threshold that is not from the RFP record is marked PROPOSED (nothing hidden)
    for g in MATRIX["gates"]:
        for c in g["criteria"]:
            if c["threshold"] is not None and c["threshold_status"] != "RFP_AS_RECORDED":
                assert c["threshold_status"] == "PROPOSED" and g["status"] == "PROPOSED"


def test_thresholds_equal_the_repository_rfp_record():
    from abep_sim.constants import RFP
    th = {cid: c["threshold"] for cid, (_, c) in CRIT.items()}
    assert th["G1.thrust_floor"] == RFP.thrust_min_mN
    assert th["G1.thrust_ceiling"] == th["G1.peak_capability_25mN"] == RFP.thrust_max_mN
    assert th["G2.bus_power_max"] == RFP.power_max_W
    assert th["G3.mass_mev"] == RFP.mass_max_kg
    assert th["G4.firing_life"] == th["P2.cathode_life"] == RFP.ignition_hours
    assert th["G5.mission_capability"] == RFP.mission_hours
    for cid, (_, c) in CRIT.items():
        if "altitude_km" in c["envelope"]:
            assert c["envelope"]["altitude_km"] == [RFP.alt_min_km, RFP.alt_max_km], cid
    rec = " ".join(r["text_as_recorded"] for r in MATRIX["rfp"]["recorded_in"])
    for s in ("180–230 km", "12–25 mN", "< 1.5 kW", "< 40 kg", "26,000 h mission", "> 15,000 h firing", "air + Xe"):
        assert s in rec
    assert MATRIX["rfp"]["document_in_repository"] is False


def test_nuisance_pin_and_boundary_match_the_repository():
    from abep_sim.hall_ensemble import load_ensemble
    from abep_sim.hall_map import pinned_commit
    assert set(MATRIX["calibration_nuisance_forbidden"]["keys"]) == set(load_ensemble()["calibration_nuisance"])
    assert PIN == pinned_commit()
    g2 = CRIT["G2.bus_power_max"][1]
    assert g2["envelope"]["elements"] == MATRIX["power_boundary"]["components"]
    assert MATRIX["power_boundary"]["version"] == "bus_power_boundary_v1"
    if importlib.util.find_spec("abep_sim.arch_boundary") is not None:     # other lane present: check the contract
        hg.check_boundary_contract(MATRIX)


def test_shared_contracts_resolve_lazily_with_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="another lane"):
        hg.resolve_contract("bus_power_boundary", MATRIX, root=str(tmp_path))
    with pytest.raises(KeyError):
        hg.resolve_contract("no_such_contract", MATRIX)
    code = ("import sys, abep_sim.hard_gates; "
            "print(any(m in sys.modules for m in ('abep_sim.arch_boundary', 'abep_sim.arch_compare', "
            "'abep_sim.thermal_life', 'abep_sim.archengine')))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=hg.ROOT, timeout=60)
    assert out.returncode == 0 and out.stdout.strip() == "False"


# ------------------------------------------------------------------------------------------------ UNDETERMINED by default
@pytest.mark.parametrize("arch", hg.ARCHITECTURES)
def test_every_gate_undetermined_without_evidence(arch):
    res = evaluate(arch, [])
    hg.validate_result(res, SCHEMA)
    assert set(verdicts(res).values()) == {"UNDETERMINED"}
    assert not res["eliminated"] and res["elimination_basis"] == [] and res["conflicts"] == []
    a = res["milestones"]["A"]
    assert a["conditional_selection_available"] and "not a selection" in a["statement"]
    counted = {c["id"] for g in MATRIX["gates"] if g["binding"] for c in g["criteria"] if c["counts_toward_gate"]}
    assert {c["criterion"] for c in a["conditions"]} == counted
    for c in a["conditions"]:
        assert c["can_eliminate"] is CRIT[c["criterion"]][1]["counts_for_fail"]
    assert sum(c["can_eliminate"] for c in a["conditions"]) == 8 and len(a["conditions"]) == 12
    for c in a["conditions"]:
        if "model_admitted_closure" in CRIT[c["criterion"]][1]["pass_sufficient_bases"]:
            assert any("credible Hall-transport set is empty" in b for b in c["blockers"])
    assert not res["milestones"]["B"]["ready"] and not res["milestones"]["C"]["ready"]
    assert res["milestones"]["C"]["integrated_designs"] == []


def test_evaluate_all_has_no_ranking_and_no_winner():
    s = evaluate_all([])
    hg.validate_result(s, SCHEMA)
    assert s["eliminated"] == [] and s["not_eliminated"] == list(hg.ARCHITECTURES)
    text = json.dumps(s)
    for key in ('"winner"', '"ranking"', '"rank"', '"score"', '"selected"'):
        assert key not in text
    bad = copy.deepcopy(s)
    bad["winner"] = "hall_only"
    with pytest.raises(ValueError):
        hg.validate_result(bad, SCHEMA)


def test_missing_or_malformed_evidence_container_raises():
    with pytest.raises(TypeError):
        evaluate("hall_only", None)
    with pytest.raises(TypeError):
        evaluate("hall_only", "no evidence")
    with pytest.raises(ValueError, match="matrix"):
        evaluate("hall_only", {"schema": hg.EVIDENCE_SCHEMA, "matrix_version": "0.0.1", "items": [], "note": SYN})
    with pytest.raises(TypeError):
        evaluate("hall_only", [], admitted_members="sgb-screen-01")


# ------------------------------------------------------------------------------------------------ FAIL needs sufficient evidence
@pytest.mark.parametrize("basis", ["measurement_similar_hardware", "model_unadmitted_closure", "engineering_estimate",
                                   "assumption"])
def test_insufficient_evidence_classes_never_fail(basis):
    it = item("SYN-weak", "G1.thrust_floor", UB(1.0), basis=basis)
    res = evaluate("rf_hall", [it])
    assert res["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED" and not res["eliminated"]
    nvb = {x["id"]: x["reasons"] for x in res["evidence_not_verdict_bearing"]}
    assert any("never verdict-bearing" in r for r in nvb["SYN-weak"])


def test_unadmitted_member_evidence_is_not_verdict_bearing():
    it = item("SYN-map-b", "G1.thrust_floor", UB(1.0), basis="model_admitted_closure", member="SYN-member-b")
    for admitted in ((), ("SYN-member-a",)):
        res = evaluate("rf_hall", [it], admitted_members=admitted)
        assert res["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED" and not res["eliminated"]
        reasons = res["evidence_not_verdict_bearing"][0]["reasons"]
        assert any("not in the admitted transport-ensemble set" in r for r in reasons)


@pytest.mark.parametrize("ensemble", [None, SYN_ENSEMBLE])
def test_screening_candidate_passed_as_admitted_raises(ensemble):
    """Reviewer probe: a screening candidate supplied as an admitted member must never make its maps verdict-bearing."""
    probe = item("SYN-screen", "G1.thrust_floor", UB(1.0), basis="model_admitted_closure", member="sgb-screen-01")
    for evidence in ([probe], []):
        with pytest.raises(ValueError, match="SCREENING"):
            evaluate("rf_hall", evidence, admitted_members=("sgb-screen-01",), ensemble=ensemble)
    with pytest.raises(ValueError, match="SCREENING"):
        evaluate_all([], admitted_members=["sgb-screen-01"], ensemble=ensemble)
    with pytest.raises(ValueError, match="SCREENING"):
        evaluate("rf_hall", [], admitted_members=("SYN-screen-x",), ensemble=SYN_ENSEMBLE)
    with pytest.raises(ValueError, match="SCREENING"):
        hg.build_status(admitted_members=["sgb-screen-01"])


def test_screening_candidate_labelled_admitted_raises():
    probe = item("SYN-screen", "G1.thrust_floor", UB(1.0), basis="model_admitted_closure", member="sgb-screen-01")
    with pytest.raises(ValueError, match="SCREENING candidate labelled as an admitted closure"):
        evaluate("rf_hall", [probe])
    with pytest.raises(ValueError, match="SCREENING candidate labelled as an admitted closure"):
        evaluate("rf_hall", [probe], ensemble=None)


def test_admitted_ids_must_be_ensemble_members():
    from abep_sim.hall_ensemble import member_ids
    assert member_ids() == set()                     # credible set is empty in the repository today
    with pytest.raises(ValueError, match="not an admitted"):
        hg.evaluate("rf_hall", [], admitted_members=("SYN-member-a",))        # repository ensemble
    with pytest.raises(ValueError, match="not an admitted"):
        evaluate("rf_hall", [], admitted_members=("SYN-member-z",))
    bad = copy.deepcopy(SYN_ENSEMBLE)
    bad["members"].append({"ensemble_member_id": "sgb-screen-01"})        # an ensemble cannot promote a screening id
    with pytest.raises(ValueError, match="screening candidate"):
        evaluate("rf_hall", [], admitted_members=("SYN-member-a",), ensemble=bad)
    res = evaluate("rf_hall", [], admitted_members=("SYN-member-a",))
    assert res["admitted_members"] == ["SYN-member-a"] and "caller-supplied" in res["admitted_members_checked_against"]
    assert "transport_ensemble_v0.json" in hg.evaluate("rf_hall", [])["admitted_members_checked_against"]


@pytest.mark.parametrize("script, reason", [
    ("scripts/SYNTHETIC_does_not_exist.py", "does not exist in the repository"),
    ("../outside.py", "repository-relative"),
    ("/tmp/abs.py", "repository-relative"),
])
def test_derivation_script_must_exist_in_the_repository(script, reason):
    it = item("SYN-bound", "G1.thrust_floor", UB(5.0), derivation_script=script)
    res = evaluate("rf_hall", [it])
    assert res["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED" and not res["eliminated"]
    assert any(reason in r for r in res["evidence_not_verdict_bearing"][0]["reasons"])
    # the same synthetic script is not in the real repository: never verdict-bearing there
    assert hg.evaluate("rf_hall", [item("SYN-b2", "G1.thrust_floor", UB(5.0))],
                       ensemble=SYN_ENSEMBLE)["eliminated"] is False


def test_point_estimate_and_non_deciding_bounds_are_inconclusive():
    items = [item("SYN-pe", "G1.thrust_floor", {"kind": "point_estimate", "value": 1.0}),
             item("SYN-lb", "G1.thrust_floor", LB(1.0), fail_side=True),
             item("SYN-iv", "G1.thrust_floor", {"kind": "interval", "lo": 10.0, "hi": 14.0}, fail_side=True)]
    res = evaluate("rf_hall", items)
    assert res["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED"
    assert {x["id"] for x in res["evidence_not_verdict_bearing"]} == {"SYN-pe", "SYN-lb", "SYN-iv"}


def test_hard_bound_over_the_envelope_fails_and_eliminates_at_milestone_A():
    it = item("SYN-bound", "G1.thrust_floor", UB(5.0))
    s = evaluate_all([it])
    hg.validate_result(s, SCHEMA)
    res = s["architectures"]["rf_hall"]
    g1 = res["gates"]["G1_thrust"]
    assert g1["verdict"] == "FAIL" and g1["milestone"] == "A" and g1["evidence_used"] == ["SYN-bound"]
    assert res["eliminated"] and res["elimination_basis"] == [
        {"gate": "G1_thrust", "criteria": ["G1.thrust_floor"], "evidence": ["SYN-bound"], "milestone": "A"}]
    assert not res["milestones"]["A"]["conditional_selection_available"]
    assert "ELIMINATED" in res["milestones"]["A"]["statement"]
    assert s["eliminated"] == ["rf_hall"] and s["not_eliminated"] == ["hall_only", "ecr_hall"]


def test_fail_must_cover_the_whole_envelope():
    part = item("SYN-top", "G1.thrust_floor", UB(5.0), cond={**_conditions(CRIT["G1.thrust_floor"][1], "rf_hall",
                                                                              "hard_physical_bound", True),
                                                               "altitude_km": [205, 230]})
    res = evaluate("rf_hall", [part])
    assert res["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED" and not res["eliminated"]
    assert any("altitude gap" in m for m in res["gates"]["G1_thrust"]["criteria"]["G1.thrust_floor"]["missing_for_fail"])
    low = copy.deepcopy(part)
    low.update(id="SYN-bottom")
    low["conditions"]["altitude_km"] = [180, 205]
    assert evaluate("rf_hall", [part, low])["gates"]["G1_thrust"]["verdict"] == "FAIL"
    one_state = copy.deepcopy(part)
    one_state.update(id="SYN-low-solar")
    one_state["conditions"].update(altitude_km=[180, 230], atmosphere_states=["low"])
    assert evaluate("rf_hall", [one_state])["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED"


def test_point_design_failure_is_recorded_but_never_eliminates():
    it = item("SYN-d1-fail", "G1.thrust_floor", UB(5.0), basis="measurement_vyovrinda", design="D1")
    res = evaluate("rf_hall", [it])
    crit = res["gates"]["G1_thrust"]["criteria"]["G1.thrust_floor"]
    assert crit["verdict"] == "UNDETERMINED" and not res["eliminated"]
    assert crit["design_failures"] == {"D1": {"milestone": "A", "evidence": ["SYN-d1-fail"]}}


def test_admitted_closure_evidence_needs_every_member_and_is_milestone_B():
    members = ("SYN-member-a", "SYN-member-b")
    a = item("SYN-map-a", "G1.thrust_floor", UB(5.0), archs=("ecr_hall",), basis="model_admitted_closure",
             member=members[0])
    b = item("SYN-map-b", "G1.thrust_floor", UB(5.0), archs=("ecr_hall",), basis="model_admitted_closure",
             member=members[1])
    only_a = evaluate("ecr_hall", [a], admitted_members=members)
    assert only_a["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED"
    both = evaluate("ecr_hall", [a, b], admitted_members=members)
    assert both["gates"]["G1_thrust"]["verdict"] == "FAIL" and both["gates"]["G1_thrust"]["milestone"] == "B"
    assert both["eliminated"]
    untrusted = copy.deepcopy(b)
    untrusted["flags"]["hall_map_trustworthy"] = False
    assert evaluate("ecr_hall", [a, untrusted], admitted_members=members)["gates"]["G1_thrust"]["verdict"] \
        == "UNDETERMINED"
    wrong_pin = copy.deepcopy(b)
    wrong_pin["hall_closure"]["hallthruster_commit"] = "1" * 40
    assert evaluate("ecr_hall", [a, wrong_pin], admitted_members=members)["gates"]["G1_thrust"]["verdict"] \
        == "UNDETERMINED"
    # a hard bound mixed with admitted-closure evidence: the hard bound alone already fails at A
    hb = item("SYN-hb", "G1.thrust_floor", UB(5.0), archs=("ecr_hall",))
    assert evaluate("ecr_hall", [a, hb], admitted_members=members)["gates"]["G1_thrust"]["milestone"] == "A"


def test_sustainment_extinction_from_maps_needs_numerical_and_chemistry_validity():
    members = ("SYN-member-a",)
    it = item("SYN-ext", "G6.sustainment", FALSE, archs=("hall_only",), basis="model_admitted_closure",
              member=members[0])
    assert evaluate("hall_only", [it], admitted_members=members)["gates"]["G6_ignition_sustainment"]["verdict"] \
        == "FAIL"
    ood = copy.deepcopy(it)
    ood["flags"]["chemistry_trustworthy"] = False       # OUT_OF_DOMAIN is never evidence
    res = evaluate("hall_only", [ood], admitted_members=members)
    assert res["gates"]["G6_ignition_sustainment"]["verdict"] == "UNDETERMINED" and not res["eliminated"]


def test_n2_surrogate_does_not_cover_atmospheric_propellant():
    it = item("SYN-n2", "G6.sustainment", TRUE, basis="measurement_vyovrinda", design="D1")
    it["conditions"]["propellants"] = ["n2_surrogate"]
    res = evaluate("rf_hall", [it])
    assert res["gates"]["G6_ignition_sustainment"]["criteria"]["G6.sustainment"]["verdict"] == "UNDETERMINED"


def test_ignition_fail_must_exclude_xenon_assisted_start_and_maps_are_not_accepted():
    air = item("SYN-noign-air", "G6.ignition", FALSE)
    air["conditions"]["start_sequences"] = ["air_only"]
    crit = lambda r: r["gates"]["G6_ignition_sustainment"]["criteria"]["G6.ignition"]   # noqa: E731
    assert crit(evaluate("rf_hall", [air]))["verdict"] == "UNDETERMINED"
    both = item("SYN-noign-both", "G6.ignition", FALSE)
    assert both["conditions"]["start_sequences"] == ["air_only", "xenon_assisted"]
    assert crit(evaluate("rf_hall", [both]))["verdict"] == "FAIL"
    xe_start = item("SYN-ign-xe", "G6.ignition", TRUE, basis="measurement_vyovrinda", design="D1")
    xe_start["conditions"]["start_sequences"] = ["xenon_assisted"]
    assert crit(evaluate("rf_hall", [xe_start]))["verdict"] == "UNDETERMINED"
    m = item("SYN-ign-map", "G6.ignition", FALSE, basis="model_admitted_closure", member="SYN-member-a")
    r = evaluate("rf_hall", [m], admitted_members=("SYN-member-a",))
    assert crit(r)["verdict"] == "UNDETERMINED"
    assert any("not sufficient for FAIL" in x for x in r["evidence_not_verdict_bearing"][0]["reasons"])


def test_measurement_must_map_its_feed_to_the_envelope_point():
    it = item("SYN-nofeed", "G1.thrust_floor", LB(13), basis="measurement_vyovrinda", design="D1")
    del it["conditions"]["feed_equivalence"]
    res = evaluate("rf_hall", [it])
    assert any("feed_equivalence" in r for r in res["evidence_not_verdict_bearing"][0]["reasons"])


def test_power_must_be_stated_at_the_common_boundary():
    it = item("SYN-pwr", "G2.bus_power_max", LB(2000))
    it["conditions"]["power_boundary"] = "thruster_terminals"
    res = evaluate("rf_hall", [it])
    assert res["gates"]["G2_bus_power"]["verdict"] == "UNDETERMINED"
    ok = item("SYN-pwr-ok", "G2.bus_power_max", LB(2000), cond={**_conditions(CRIT["G2.bus_power_max"][1], "rf_hall",
                                                                                 "hard_physical_bound", True),
                                                                   "elements": ["hall_discharge", "rf_source"]})
    assert evaluate("rf_hall", [ok])["gates"]["G2_bus_power"]["verdict"] == "FAIL"
    foreign = copy.deepcopy(ok)
    foreign.update(id="SYN-pwr-ecr")
    foreign["conditions"]["elements"] = ["hall_discharge", "ecr_source"]       # not a component of rf_hall
    assert evaluate("rf_hall", [foreign])["gates"]["G2_bus_power"]["verdict"] == "UNDETERMINED"


def test_mass_sum_semantics():
    arch = "ecr_hall"
    need = hg._resolve(CRIT["G3.mass_mev"][1]["envelope"]["elements"], arch)
    sub = item("SYN-cbe", "G3.mass_mev", LB(41), archs=(arch,), basis="measurement_same_hardware",
               cond={"elements": ["compressor", "ecr_magnet"]})
    assert evaluate(arch, [sub])["gates"]["G3_mass"]["verdict"] == "FAIL"
    out = copy.deepcopy(sub)
    out["conditions"]["elements"] = ["compressor", "spacecraft_bus"]
    assert evaluate(arch, [out])["gates"]["G3_mass"]["verdict"] == "UNDETERMINED"
    partial = item("SYN-mev-part", "G3.mass_mev", UB(30), archs=(arch,), basis="measurement_vyovrinda", design="D1",
                   cond={"elements": need[:-1]})
    assert evaluate(arch, [partial])["gates"]["G3_mass"]["verdict"] == "UNDETERMINED"
    full = item("SYN-mev", "G3.mass_mev", UB(30), archs=(arch,), basis="model_closure_independent", design="D1",
                cond={"elements": need})
    res = evaluate(arch, [full])
    assert res["gates"]["G3_mass"]["verdict"] == "PASS" and res["gates"]["G3_mass"]["milestone"] == "B"


# ------------------------------------------------------------------------------------------------ rule violations raise
def test_rule_violations_raise():
    nuis = item("SYN-nuis", "G1.thrust_floor", UB(5.0))
    nuis["conditions"]["p5_registration"] = "L32-anode"
    with pytest.raises(ValueError, match="calibration nuisance"):
        evaluate("rf_hall", [nuis])
    leak = item("SYN-leak", "G3.mass_mev", UB(30), basis="model_admitted_closure", member="SYN-member-a",
                design="D1", cond={"elements": ["compressor"]})
    with pytest.raises(ValueError, match="must not leak"):
        evaluate("rf_hall", [leak], admitted_members=("SYN-member-a",))
    mislabel = item("SYN-mislabel", "G1.thrust_floor", UB(5.0))
    mislabel["hall_closure"] = {"status": "unadmitted", "member_id": "sgb-screen-01"}
    with pytest.raises(ValueError, match="hall_closure.status"):
        evaluate("rf_hall", [mislabel])


@pytest.mark.parametrize("mutate, exc", [
    (lambda it: it.__setitem__("metric", "thrust_mN"), ValueError),
    (lambda it: it.__setitem__("criterion", "G1.no_such"), ValueError),
    (lambda it: it.__setitem__("gate", "G9_nothing"), ValueError),
    (lambda it: it.pop("source"), ValueError),
    (lambda it: it.pop("scope_justification"), ValueError),
    (lambda it: it.__setitem__("value", {"kind": "interval", "lo": 9.0, "hi": 3.0}), ValueError),
    (lambda it: it.__setitem__("value", {"kind": "upper_bound", "value": float("nan")}), ValueError),
    (lambda it: it["conditions"].__setitem__("altitude_km", [230, 180]), ValueError),
    (lambda it: it.__setitem__("architectures", ["hall_ecr"]), ValueError),
])
def test_malformed_items_raise(mutate, exc):
    it = item("SYN-bad", "G1.thrust_floor", UB(5.0))
    mutate(it)
    with pytest.raises(exc):
        evaluate("rf_hall", [it])
    with pytest.raises(ValueError, match="duplicate"):
        evaluate("rf_hall", [item("SYN-dup", "G1.thrust_floor", UB(5.0))] * 2)


def test_inputs_are_not_mutated():
    ev = [item("SYN-bound", "G1.thrust_floor", UB(5.0))] + full_pass_bundle("hall_only", "D1")
    before = copy.deepcopy(ev)
    m = copy.deepcopy(MATRIX)
    evaluate("hall_only", ev, matrix=m)
    assert ev == before and m == MATRIX


# ------------------------------------------------------------------------------------------------ elimination logic
def test_proposed_gate_failure_reports_but_never_eliminates_until_adopted():
    it = item("SYN-hot", "P1.thermal_margin", UB(-5.0), archs=("ecr_hall",),
              cond={"operating_modes": ["steady"], "elements": ["ecr_source"], "power_boundary": "bus_power_boundary_v1"})
    res = evaluate("ecr_hall", [it])
    assert res["gates"]["P1_thermal"]["verdict"] == "FAIL" and not res["eliminated"]
    assert res["proposed_gate_failures"][0]["gate"] == "P1_thermal"
    adopted = copy.deepcopy(MATRIX)
    p1 = next(g for g in adopted["gates"] if g["id"] == "P1_thermal")
    p1.update(status="OWNER_ADOPTED", binding=True)
    res2 = evaluate("ecr_hall", [it], matrix=adopted)
    assert res2["eliminated"] and res2["elimination_basis"][0]["gate"] == "P1_thermal"


@pytest.mark.parametrize("cid, value, od", [
    ("G1.peak_capability_25mN", UB(20.0), "OD1"),       # reading (ii) only
    ("G1.thrust_ceiling", LB(30.0), "OD1"),             # reading (i) only: under (ii) a 30 mN minimum still complies
    ("G7.feed_switching", FALSE, "OD6"),
    ("G7.mixed_feed", FALSE, "OD6"),
])
def test_reading_dependent_criterion_never_fails_its_gate(cid, value, od):
    gid = CRIT[cid][0]
    it = item("SYN-reading", cid, value, archs=("hall_only",))
    res = evaluate("hall_only", [it])
    g = res["gates"][gid]
    assert g["criteria"][cid]["verdict"] == "FAIL" and not g["criteria"][cid]["counts_for_fail"]
    assert g["verdict"] == "UNDETERMINED" and not res["eliminated"]
    assert any("open owner reading" in r for r in g["reasons"])
    assert any(o["criterion"] == cid and od in o["fail_reading_dependence"]
               for o in res["milestones"]["A"]["open_owner_items"])
    cond = next(c for c in res["milestones"]["A"]["conditions"] if c["criterion"] == cid)
    assert cond["can_eliminate"] is False


def test_non_counting_criterion_is_reported_only():
    it = item("SYN-restarts-low", "G6.restart_count", UB(1.0), archs=("hall_only",))
    res = evaluate("hall_only", [it])
    assert res["gates"]["G6_ignition_sustainment"]["verdict"] == "UNDETERMINED" and not res["eliminated"]
    assert "G6.restart_count" not in {c["criterion"] for c in res["milestones"]["A"]["conditions"]}


def _fail_cond(cid, arch="rf_hall", **override):
    c = _conditions(CRIT[cid][1], arch, "hard_physical_bound", True)
    c.update(override)
    return c


def test_floor_fail_must_hold_with_xenon_augmentation_OD4():
    air_only = item("SYN-floor-air", "G1.thrust_floor", UB(5.0),
                    cond=_fail_cond("G1.thrust_floor", operating_modes=["steady"], propellants=["atmospheric"]))
    res = evaluate("rf_hall", [air_only])
    assert res["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED" and not res["eliminated"]
    both = item("SYN-floor-both", "G1.thrust_floor", UB(5.0))
    assert both["conditions"]["propellants"] == ["atmospheric", "atmospheric_xenon_mixed"]
    assert evaluate("rf_hall", [both])["eliminated"]


def test_power_fail_needs_steady_mode_OD8():
    elements = {"elements": ["hall_discharge"]}
    startup = item("SYN-pwr-startup", "G2.bus_power_max", LB(1600),
                   cond=_fail_cond("G2.bus_power_max", operating_modes=["startup"], **elements))
    peak = item("SYN-pwr-peak", "G2.bus_power_max", LB(1600),
                cond=_fail_cond("G2.bus_power_max", operating_modes=["peak"], **elements))
    res = evaluate("rf_hall", [startup, peak])
    assert res["gates"]["G2_bus_power"]["verdict"] == "UNDETERMINED" and not res["eliminated"]
    air_only = item("SYN-pwr-air", "G2.bus_power_max", LB(1600),
                    cond=_fail_cond("G2.bus_power_max", propellants=["atmospheric"], **elements))
    assert evaluate("rf_hall", [air_only])["gates"]["G2_bus_power"]["verdict"] == "UNDETERMINED"   # OD4
    steady = item("SYN-pwr-steady", "G2.bus_power_max", LB(1600), cond=_fail_cond("G2.bus_power_max", **elements))
    assert steady["conditions"]["operating_modes"] == ["steady"]
    assert evaluate("rf_hall", [steady])["gates"]["G2_bus_power"]["verdict"] == "FAIL"


def test_mass_limit_form_and_margin_policy_OD7():
    at_limit = item("SYN-m40", "G3.mass_mev", LB(40.0), cond={"elements": ["compressor"]}, fail_side=True)
    res = evaluate("rf_hall", [at_limit])
    assert res["gates"]["G3_mass"]["verdict"] == "UNDETERMINED" and not res["eliminated"]
    over = item("SYN-m405", "G3.mass_mev", LB(40.5), cond={"elements": ["compressor"]})
    assert over["flags"] == {"mass_margin_free_lower_bound": True}
    assert evaluate("rf_hall", [over])["gates"]["G3_mass"]["verdict"] == "FAIL"
    no_flag = item("SYN-m405-mev", "G3.mass_mev", LB(40.5), cond={"elements": ["compressor"]}, flags={})
    r = evaluate("rf_hall", [no_flag])
    assert r["gates"]["G3_mass"]["verdict"] == "UNDETERMINED"
    assert any("mass_margin_free_lower_bound" in x for x in r["evidence_not_verdict_bearing"][0]["reasons"])
    need = hg._resolve(CRIT["G3.mass_mev"][1]["envelope"]["elements"], "rf_hall")
    ok = item("SYN-m39", "G3.mass_mev", UB(39.9), basis="measurement_vyovrinda", design="D1", cond={"elements": need})
    assert ok["flags"] == {"mass_includes_max_margin_policy": True}
    assert evaluate("rf_hall", [ok])["gates"]["G3_mass"]["verdict"] == "PASS"
    edge = item("SYN-m40-ub", "G3.mass_mev", UB(40.0), basis="measurement_vyovrinda", design="D1",
                cond={"elements": need}, fail_side=False)
    assert evaluate("rf_hall", [edge])["gates"]["G3_mass"]["verdict"] == "UNDETERMINED"
    mga_only = item("SYN-m39-mga", "G3.mass_mev", UB(39.0), basis="measurement_vyovrinda", design="D1",
                    cond={"elements": need}, flags={})
    assert evaluate("rf_hall", [mga_only])["gates"]["G3_mass"]["verdict"] == "UNDETERMINED"


def test_xenon_fail_must_cover_every_xenon_feed_OD6():
    xe_only = item("SYN-xe", "G7.xenon_operation", FALSE,
                   cond=_fail_cond("G7.xenon_operation", operating_modes=["steady"], propellants=["xenon"]))
    assert evaluate("rf_hall", [xe_only])["gates"]["G7_air_xenon"]["verdict"] == "UNDETERMINED"
    every = item("SYN-xe-all", "G7.xenon_operation", FALSE)
    assert set(every["conditions"]["propellants"]) == {"xenon", "atmospheric_xenon_mixed"}
    assert evaluate("rf_hall", [every])["gates"]["G7_air_xenon"]["verdict"] == "FAIL"


def test_hall_closure_never_reaches_upstream_elements():
    members = ("SYN-member-a",)
    upstream = item("SYN-comp-life", "G4.firing_life", UB(100.0), basis="model_admitted_closure", member=members[0],
                    cond={"elements": ["compressor"]})
    with pytest.raises(ValueError, match="must not leak"):
        evaluate("rf_hall", [upstream], admitted_members=members)
    xe = item("SYN-xe-cal", "G5.mission_capability", UB(100.0), basis="model_admitted_closure", member=members[0],
              cond={"elements": ["xenon_chamber_and_xenon_load"]})
    with pytest.raises(ValueError, match="must not leak"):
        evaluate("rf_hall", [xe], admitted_members=members)
    channel = item("SYN-wall-life", "G4.firing_life", UB(100.0), basis="model_admitted_closure", member=members[0],
                   cond={"elements": ["hall_discharge_channel"]})
    assert evaluate("rf_hall", [channel], admitted_members=members)["gates"]["G4_firing_life"]["verdict"] == "FAIL"
    total = item("SYN-pwr-map", "G2.bus_power_max", LB(1600), basis="model_admitted_closure", member=members[0],
                 cond=_fail_cond("G2.bus_power_max", elements=["hall_discharge", "compressor"]))
    assert evaluate("rf_hall", [total], admitted_members=members)["gates"]["G2_bus_power"]["verdict"] == "FAIL"
    assert set(MATRIX["hall_closure_scope"]["closure_independent_elements"]) == {
        "intake", "filter", "compressor", "atmospheric_gas_chamber", "xenon_chamber_and_xenon_load",
        "valves_and_flow_control"}


def test_conflicting_sufficient_evidence_is_flagged_and_eliminates_nothing():
    fail = item("SYN-mass-bound", "G3.mass_mev", LB(45), archs=("rf_hall",), cond={"elements": ["compressor"]})
    need = hg._resolve(CRIT["G3.mass_mev"][1]["envelope"]["elements"], "rf_hall")
    ok = item("SYN-mass-meas", "G3.mass_mev", UB(35), archs=("rf_hall",), basis="measurement_vyovrinda", design="D1",
              cond={"elements": need})
    res = evaluate("rf_hall", [fail, ok])
    assert res["gates"]["G3_mass"]["verdict"] == "UNDETERMINED" and res["gates"]["G3_mass"]["conflict"]
    assert not res["eliminated"] and res["conflicts"]
    assert not res["milestones"]["A"]["conditional_selection_available"]


def test_architecture_scope_pass_contradicted_by_a_design_failure_is_a_conflict():
    need = hg._resolve(CRIT["G3.mass_mev"][1]["envelope"]["elements"], "rf_hall")
    all_designs = item("SYN-mass-all", "G3.mass_mev", UB(30), basis="measurement_vyovrinda", cond={"elements": need})
    d1 = item("SYN-mass-d1", "G3.mass_mev", LB(45), basis="measurement_vyovrinda", design="D1",
              cond={"elements": ["compressor"]})
    res = evaluate("rf_hall", [all_designs, d1])
    crit = res["gates"]["G3_mass"]["criteria"]["G3.mass_mev"]
    assert crit["conflict"] and crit["verdict"] == "UNDETERMINED" and not res["eliminated"]
    assert evaluate("rf_hall", [all_designs])["gates"]["G3_mass"]["pass_designs"] == {
        hg.ARCH_KEY: {"milestone": "A", "evidence": ["SYN-mass-all"]}}


def test_tbd_thresholds_never_decide():
    it = item("SYN-restarts", "G6.restart_count", LB(1e6), archs=("hall_only",), fail_side=False,
              basis="measurement_vyovrinda", design="D1")
    res = evaluate("hall_only", [it])
    crit = res["gates"]["G6_ignition_sustainment"]["criteria"]["G6.restart_count"]
    assert crit["verdict"] == "UNDETERMINED" and any("TBD" in r for r in crit["reasons"])
    assert any("threshold TBD" in r for x in res["evidence_not_verdict_bearing"] for r in x["reasons"])
    life = item("SYN-cath", "P2.cathode_life", LB(20000), archs=("hall_only",), basis="measurement_vyovrinda",
                design="D1")
    res2 = evaluate("hall_only", [life])
    assert res2["gates"]["P2_cathode"]["criteria"]["P2.cathode_life"]["verdict"] == "PASS"
    assert res2["gates"]["P2_cathode"]["verdict"] == "UNDETERMINED"       # P2.start_cycles is TBD


# ------------------------------------------------------------------------------------------------ PASS and milestones
def test_pass_needs_every_criterion_and_full_coverage():
    floor = item("SYN-floor", "G1.thrust_floor", LB(13), archs=("hall_only",), basis="measurement_vyovrinda",
                 design="D1")
    res = evaluate("hall_only", [floor])
    assert res["gates"]["G1_thrust"]["criteria"]["G1.thrust_floor"]["verdict"] == "PASS"
    assert res["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED"            # ceiling not yet shown
    ceil = item("SYN-ceil", "G1.thrust_ceiling", UB(20), archs=("hall_only",), basis="measurement_vyovrinda",
                design="D1")
    assert evaluate("hall_only", [floor, ceil])["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED"   # OD1 (ii) open
    peak = item("SYN-peak", "G1.peak_capability_25mN", LB(26), archs=("hall_only",), basis="measurement_vyovrinda",
                design="D1")
    res = evaluate("hall_only", [floor, ceil, peak])
    assert res["gates"]["G1_thrust"]["verdict"] == "PASS" and res["gates"]["G1_thrust"]["milestone"] == "A"
    assert list(res["gates"]["G1_thrust"]["pass_designs"]) == ["D1"]
    other = copy.deepcopy(ceil)
    other.update(id="SYN-ceil-d2", design_id="D2")
    res = evaluate("hall_only", [floor, other, peak])
    assert res["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED"            # different point designs


def test_pass_from_admitted_closures_is_tagged_B():
    members = ("SYN-member-a", "SYN-member-b")
    items = [item(f"SYN-{cid}-{m}", cid, v, archs=("rf_hall",), basis="model_admitted_closure", member=m, design="D1")
             for m in members for cid, v in (("G1.thrust_floor", LB(13)), ("G1.thrust_ceiling", UB(20)),
                                             ("G1.peak_capability_25mN", LB(26)))]
    res = evaluate("rf_hall", items, admitted_members=members)
    assert res["gates"]["G1_thrust"]["verdict"] == "PASS" and res["gates"]["G1_thrust"]["milestone"] == "B"
    assert evaluate("rf_hall", items)["gates"]["G1_thrust"]["verdict"] == "UNDETERMINED"   # nothing admitted


def _approved_matrix_without_open_items() -> dict:
    """SYNTHETIC owner decisions: every PROPOSED gate waived, every reading-dependent or TBD criterion dropped."""
    m = copy.deepcopy(MATRIX)
    m["status"] = "OWNER_APPROVED"
    m["gates"] = [g for g in m["gates"] if g["status"] != "PROPOSED"]
    for g in m["gates"]:
        g["criteria"] = [c for c in g["criteria"] if c["counts_for_fail"] and c["status"] == "RFP"]
    return m


def _only_in(matrix: dict, ev: list) -> list:
    keep = {c["id"] for g in matrix["gates"] for c in g["criteria"]}
    return [x for x in ev if x["criterion"] in keep]


def test_milestone_B_and_C_readiness_and_integration():
    ev = full_pass_bundle("rf_hall", "D1")
    res = evaluate("rf_hall", ev)
    hg.validate_result(res, SCHEMA)
    assert all(res["gates"][g]["verdict"] == "PASS" for g in res["binding_gates"])
    assert res["milestones"]["B"]["all_binding_gates_pass"]
    assert not res["milestones"]["B"]["ready"]                              # matrix is DRAFT_PENDING_OWNER
    assert res["milestones"]["C"]["integrated_designs"] == ["D1"] and not res["milestones"]["C"]["ready"]
    assert any("PROPOSED gate P1_thermal" in x for x in res["milestones"]["C"]["missing"])
    approved = _approved_matrix_without_open_items()
    ev = _only_in(approved, ev)
    res = evaluate("rf_hall", ev, matrix=approved)
    assert res["milestones"]["B"]["ready"] and res["milestones"]["C"]["ready"]
    assert res["milestones"]["A"]["conditions"] == []
    split = [copy.deepcopy(x) for x in ev]
    for x in split:
        if x["gate"] == "G3_mass":
            x["design_id"] = "D2"
    res = evaluate("rf_hall", split, matrix=approved)
    assert res["milestones"]["B"]["ready"] and not res["milestones"]["C"]["ready"]
    assert "no single integrated design passes every binding gate" in res["milestones"]["C"]["missing"]
    assert evaluate("hall_only", ev)["milestones"]["B"]["all_binding_gates_pass"] is False   # rf_hall-only evidence


# ------------------------------------------------------------------------------------------------ committed artefacts
def test_doc_table_is_generated_from_the_matrix():
    doc = open(hg.DOC_FILE, encoding="utf-8").read()
    body = doc.split(hg.TABLE_BEGIN, 1)[1].split(hg.TABLE_END, 1)[0]
    assert body.strip() == hg.render_table(MATRIX).strip()
    for g in MATRIX["gates"]:
        assert g["id"] in doc
    for od in MATRIX["open_owner_decisions"]:
        assert od["id"] in doc


def test_register_is_empty_and_status_file_reproduces():
    reg = json.load(open(hg.REGISTER_FILE, encoding="utf-8"))
    assert reg["schema"] == hg.EVIDENCE_SCHEMA and reg["items"] == []
    committed = json.load(open(hg.STATUS_FILE, encoding="utf-8"))
    assert json.loads(hg._dump(hg.build_status())) == committed
    hg.validate_result(committed, SCHEMA)
    assert committed["eliminated"] == [] and committed["admitted_members"] == []
    for arch in hg.ARCHITECTURES:
        assert set(verdicts(committed["architectures"][arch]).values()) == {"UNDETERMINED"}
