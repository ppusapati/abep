"""S1-readiness gate (fo_s1_readiness_gate; scripts/experiments/s1_readiness.py, docs/experiments/s1_readiness/).

Checks: an empty repository gives S1_NOT_READY with all eight owner conditions missing; a synthetic complete fixture gives
S1_READY; DRAFT / PROPOSED / PENDING artifacts never satisfy a condition; sha256 references, the LOCK-1 location rule,
the demonstration-vs-design-analysis rule and the flight-status labels are enforced; output is deterministic and the gate
writes nothing. Every fixture lives in tmp_path; the repository is only read. Fast (well under a second per test).
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "experiments" / "s1_readiness.py"
SPEC = ROOT / "docs" / "experiments" / "s1_readiness" / "s1_readiness_conditions_v1.json"
REPORT = ROOT / "docs" / "experiments" / "s1_readiness" / "s1_readiness_status_current.json"


def _load():
    spec = importlib.util.spec_from_file_location("_test_s1_readiness", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load()

OWNER_CONDITIONS = [
    "LOCK-1 signed by the owner",
    "H-1/C-1 configuration frozen sufficiently for qualification",
    "DI-1 or explicitly labelled ground-qualification feed points available",
    "instrumentation capability demonstrated",
    "calibration plan frozen",
    "data custody / blinding plan frozen",
    "facility chosen",
    "safety / operational limits defined",
]
CATEGORIES = ["thrust_stand", "bus_power_metering", "discharge_current", "flow", "pressure", "temperature",
              "magnetic_field_Bz", "stability_oscillations", "species_divergence"]
LIMITS = ["discharge_voltage_max", "discharge_current_max", "magnet_current_max", "cathode_heater_current_max",
          "cathode_keeper_current_max", "background_pressure_max", "component_temperature_max", "gas_handling_oxidizer"]

P_OD = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json"
P_A1 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A1_controls.json"
P_A2 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A2_execution_directive.json"
OD_FILES = (P_OD, P_A1, P_A2)
P_BRIEF = "docs/architecture_comparison/lock1/lock1_decision_brief_v1.json"
P_LOCK1 = "docs/architecture_comparison/lock1/LOCK1.json"
P_HWREQ = "docs/experiments/hardware/hardware_requirements_v1.json"
P_FREEZE = "docs/experiments/hardware/configuration_freeze_H1_C1.json"
P_CLOSURE = "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json"
P_DI1 = "docs/architecture_comparison/feed_state_closure/DI1_FROZEN.json"
P_POINTS = "docs/architecture_comparison/feed_state_closure/s1_feed_points.json"
P_CAL = "docs/experiments/instrumentation/calibration_plan_frozen.json"
P_CAP = "docs/experiments/instrumentation/capability_demonstration_v1.json"
P_CUST = "docs/experiments/custody/custody_blinding_plan_frozen.json"
P_FAC = "docs/decisions/OD_S1_FACILITY.json"
P_SAFE = "docs/experiments/hardware/s1_safety_operational_limits.json"
P_RAW = "docs/experiments/instrumentation/raw/{}.csv"


# ------------------------------------------------------------------------------------------------------ fixtures
def _write(root: Path, rel: str, obj) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    data = obj if isinstance(obj, (bytes, str)) else json.dumps(obj, indent=1, sort_keys=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _ref(root: Path, rel: str) -> dict:
    return {"path": rel, "sha256": hashlib.sha256((root / rel).read_bytes()).hexdigest()}


def _base(root: Path) -> Path:
    """Spec + the real, immutable owner decision files (the gate's authority); every condition artifact absent."""
    for rel in (str(SPEC.relative_to(ROOT)),) + OD_FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, root / rel)
    return root


def _q(value, unit, ec="assumed"):
    return {"value": value, "unit": unit, "source": "synthetic test fixture", "evidence_class": ec}


def _complete(root: Path, feed_alt: str = "points", lock1_path: str = P_LOCK1, d05: str = "D-05-D",
              mutate: dict | None = None) -> Path:
    """Synthetic complete fixture (test data only; no value here is a project number). mutate: rel -> fn(obj)."""
    mutate = mutate or {}
    _base(root)

    def put(rel, obj):
        if rel in mutate:
            obj = mutate[rel](copy.deepcopy(obj))
        _write(root, rel, obj)

    _write(root, P_BRIEF, {"schema": "synthetic brief"})
    put(lock1_path, {
        "id": "LOCK-1", "status": "SIGNED", "locked": True, "decided_by": "owner", "decided_utc": "2026-10-01",
        "decision_source": _ref(root, P_BRIEF),
        "decisions": [{"id": f"D-{i:02d}", "owner_choice": (d05 if i == 5 else f"D-{i:02d}-A")} for i in range(1, 16)],
    })
    lock1 = _ref(root, lock1_path)
    _write(root, P_HWREQ, {"schema": "synthetic hw register"})
    put(P_FREEZE, {
        "status": "FROZEN_FOR_QUALIFICATION", "decided_by": "owner", "decided_utc": "2026-10-02", "lock1": lock1,
        "requirements_basis": _ref(root, P_HWREQ),
        "items": [{"id": i, "status": "FROZEN", "serial_or_part_id": f"SN-{i}", "configuration_record": f"rec-{i}"}
                  for i in ("H-1", "C-1", "MC-1")],
    })
    test_points = [
        {"id": "TP-1", "flight_status": "GROUND_QUALIFICATION_POINT", "gas": "N2", "m_dot_s": _q(1.0, "mg/s"),
         "P_feed": _q(1.0, "Pa"), "T_feed": _q(1.0, "K"), "x_s": _q({"N2": 1.0}, "mole fraction")},
        {"id": "TP-2", "flight_status": "GROUND_QUALIFICATION_POINT", "gas": "N2/O2", "m_dot_s": _q(1.0, "mg/s"),
         "P_feed": _q(1.0, "Pa"), "T_feed": _q(1.0, "K"), "x_s": _q({"N2": 0.5, "O2": 0.5}, "mole fraction")},
    ]
    if feed_alt == "points":
        _write(root, P_CLOSURE, {"schema": "synthetic closure"})
        put(P_POINTS, {
            "status": "RELEASED_FOR_S1", "decided_by": "owner", "decided_utc": "2026-10-02", "lock1": lock1,
            "source_closure": _ref(root, P_CLOSURE), "test_points": test_points,
        })
    else:
        _write(root, P_CLOSURE, {"schema": "synthetic closure"})
        put(P_DI1, {"id": "DI-1", "status": "FROZEN", "decided_by": "owner", "decided_utc": "2026-10-02",
                    "closure_basis": _ref(root, P_CLOSURE), "test_points": test_points})
    put(P_CAL, {
        "status": "FROZEN", "decided_by": "owner", "decided_utc": "2026-10-02", "lock1": lock1,
        "procedures": [{"category": c, "procedure": f"proc-{c}", "traceability": "cert", "acceptance_rule": "rule"}
                       for c in CATEGORIES],
    })
    for c in CATEGORIES:
        _write(root, P_RAW.format(c), f"t,reading\n0,{len(c)}\n")
    put(P_CAP, {
        "status": "DEMONSTRATED", "evidence_basis": "calibration_measurement", "accepted_by": "owner",
        "accepted_utc": "2026-10-05", "calibration_plan": _ref(root, P_CAL),
        "instruments": [{"category": c, "evidence_class": "measured", "calibration_date": "2026-10-04",
                         "raw_data": _ref(root, P_RAW.format(c)), "demonstrated_uncertainty": _q(0.01, "relative", "measured")}
                        for c in CATEGORIES],
    })
    put(P_CUST, {
        "status": "FROZEN", "decided_by": "owner", "decided_utc": "2026-10-02", "lock1": lock1,
        "data_custodian": "owner-designated custodian role", "partition_frozen_before_h1_data": True,
        "partition": {"calibration_registration": [{"id": "CAL-1"}], "held_out_prediction": [{"id": "HO-1"}]},
        "raw_data_freeze_rule": "sha256 before analysis", "blinding_rule": "coded arm labels", "release_log": "log.jsonl",
    })
    put(P_FAC, {
        "id": "od_s1_facility", "decided_by": "owner", "decided_utc": "2026-10-02", "decision": "APPROVED", "lock1": lock1,
        "facility": {"name": "synthetic facility", "hall_on_vacuum_facility": "chamber X", "thrust_stand": "stand Y",
                     "same_for_S1b_and_score_bearing_stages": True},
    })
    fac = _ref(root, P_FAC)
    put(P_SAFE, {
        "status": "APPROVED", "approved_by": "owner", "approved_utc": "2026-10-03", "lock1": lock1, "facility_choice": fac,
        "limits": [{"quantity": q, "limit": "synthetic", "source": "synthetic", "action_on_exceedance": "trip"} for q in LIMITS],
        "abort_conditions": [{"id": "AB-1"}],
    })
    return root


def _cond(rep, cid):
    return next(c for c in rep["conditions"] if c["id"] == cid)


# ------------------------------------------------------------------------------------------------------ spec
def test_spec_matches_owner_conditions_verbatim():
    spec = G.load_spec(SPEC)
    a2 = json.loads((ROOT / P_A2).read_text())
    assert a2["execution_directive_2026_09_27"]["S1_readiness_conditions"] == OWNER_CONDITIONS
    assert a2["amends"] == P_OD and a2["amends_sha256"] == hashlib.sha256((ROOT / P_OD).read_bytes()).hexdigest()
    pins = {d["path"]: d["sha256"] for d in spec["authority"]["documents"]}
    assert pins == {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in OD_FILES}
    assert [c["owner_condition"] for c in spec["conditions"]] == OWNER_CONDITIONS
    assert spec["status"].startswith("DRAFT")
    assert set(spec["milestones"]["supports"]) <= {"A", "B", "C"}


def test_spec_carries_no_hall_performance_or_forbidden_paths():
    text = SPEC.read_text()
    for bad in ("sgb-screen", "hallthruster_bridge/ensemble", "abep_sim/"):
        assert bad not in text
    spec = G.load_spec(SPEC)
    for c in spec["conditions"]:
        for a in c["alternatives"]:
            for p in a["paths"]:
                assert not p.startswith("hallthruster_bridge/") and "DRAFT" not in p


def test_bad_spec_is_a_spec_error(tmp_path):
    spec = json.loads(SPEC.read_text())
    spec["conditions"] = spec["conditions"][:7]
    p = tmp_path / "s.json"
    p.write_text(json.dumps(spec))
    with pytest.raises(G.SpecError):
        G.load_spec(p)
    spec = json.loads(SPEC.read_text())
    spec["conditions"][0]["alternatives"][0]["rules"].append({"type": "guess", "field": "x"})
    p.write_text(json.dumps(spec))
    with pytest.raises(G.SpecError):
        G.load_spec(p)
    spec = json.loads(SPEC.read_text())
    spec["conditions"][0]["alternatives"][0]["paths"] = ["../outside.json"]
    p.write_text(json.dumps(spec))
    with pytest.raises(G.SpecError):
        G.load_spec(p)


# ------------------------------------------------------------------------------------------------------ verdicts
def test_all_missing_is_not_ready_with_eight_items(tmp_path):
    rep = G.evaluate(_base(tmp_path))
    assert rep["authority"]["ok"] is True
    assert rep["verdict"] == "S1_NOT_READY"
    assert rep["n_missing_items"] == 8 and len(rep["missing"]) == 8
    assert [m["owner_condition"] for m in rep["missing"]] == OWNER_CONDITIONS
    assert all(m["state"] == "MISSING" and m["availability"] == "NONE" for m in rep["missing"])
    for m in rep["missing"]:
        assert m["needed"] and all(n["expected_paths"] and n["produced_by"] and n["required"] for n in m["needed"])


def test_complete_fixture_is_ready(tmp_path):
    rep = G.evaluate(_complete(tmp_path))
    bad = {c["id"]: c["alternatives"] for c in rep["conditions"] if c["state"] != "SATISFIED"}
    assert not bad, json.dumps(bad, indent=1)[:3000]
    assert rep["verdict"] == "S1_READY" and rep["n_satisfied"] == 8 and rep["missing"] == []


def test_di1_alternative_satisfies_feed_condition(tmp_path):
    rep = G.evaluate(_complete(tmp_path, feed_alt="di1"))
    c3 = _cond(rep, "S1-C3")
    assert c3["state"] == "SATISFIED" and c3["satisfied_by"] == "S1-C3-DI1-frozen"
    assert rep["verdict"] == "S1_READY"


@pytest.mark.parametrize("d05,where", [("D-05-A", "docs/architecture_comparison/experiment_protocol/prereg/LOCK1.json"),
                                       ("D-05-C", "docs/architecture_comparison/experiment_package/prereg/LOCK1.json")])
def test_lock1_at_other_d05_locations(tmp_path, d05, where):
    rep = G.evaluate(_complete(tmp_path, lock1_path=where, d05=d05))
    assert rep["verdict"] == "S1_READY"


@pytest.mark.parametrize("rel", OD_FILES)
def test_authority_fails_closed_if_a_decision_file_is_missing(tmp_path, rel):
    root = _complete(tmp_path)
    (root / rel).unlink()
    rep = G.evaluate(root)
    assert rep["n_satisfied"] == 8 and rep["authority"]["ok"] is False
    assert rep["verdict"] == "S1_NOT_READY"
    assert "not found" in " ".join(rep["authority"]["failures"])


@pytest.mark.parametrize("rel", OD_FILES)
def test_authority_fails_closed_if_a_decision_file_is_altered(tmp_path, rel):
    root = _complete(tmp_path)
    obj = json.loads((root / rel).read_text())
    obj["decided_utc"] = "2026-09-28"
    (root / rel).write_text(json.dumps(obj, indent=1))
    rep = G.evaluate(root)
    assert rep["authority"]["ok"] is False and rep["verdict"] == "S1_NOT_READY"
    assert "altered" in " ".join(rep["authority"]["failures"])


def test_authority_records_both_hashes_and_reads_conditions_from_a2(tmp_path):
    rep = G.evaluate(_base(tmp_path))
    docs = {d["path"]: d for d in rep["authority"]["documents"]}
    for rel in OD_FILES:
        assert docs[rel]["ok"] and docs[rel]["sha256"] == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    assert rep["authority"]["conditions_source"] == {
        "path": P_A2, "field": "execution_directive_2026_09_27.S1_readiness_conditions"}


def test_authority_checks_amendment_chain_and_conditions(tmp_path):
    # the original pivot no longer carries the directive: pointing the condition source at it fails closed
    root = _complete(tmp_path)
    spec = json.loads(SPEC.read_text())
    for d in spec["authority"]["documents"]:
        if "conditions_field" in d:
            d["path"] = P_OD
            d["sha256"] = hashlib.sha256((ROOT / P_OD).read_bytes()).hexdigest()
            d.pop("amends_role"), d.pop("amends_sha256_field")
            d["rules"] = [{"type": "equals", "field": "decided_by", "value": "owner"}]
    spec["authority"]["documents"] = [d for d in spec["authority"]["documents"] if d["role"] != "original_disposition"] + \
        [{"role": "original_disposition", "path": "docs/other/x.json", "sha256": "0" * 64,
          "rules": [{"type": "equals", "field": "id", "value": "x"}]}]
    sp = tmp_path / "spec.json"
    sp.write_text(json.dumps(spec))
    rep = G.evaluate(root, sp)
    fails = " ".join(rep["authority"]["failures"])
    assert rep["authority"]["ok"] is False and "owner conditions verbatim" in fails and "amended document" in fails
    assert rep["verdict"] == "S1_NOT_READY"
    # a spec whose condition wording drifts from A2 fails closed too
    spec = json.loads(SPEC.read_text())
    spec["conditions"][6]["owner_condition"] = "facility selected"
    sp.write_text(json.dumps(spec))
    rep = G.evaluate(_complete(tmp_path / "b"), sp)
    assert rep["authority"]["ok"] is False and rep["verdict"] == "S1_NOT_READY"


# ------------------------------------------------------------------------------------------------------ rejections
DRAFTABLE = [(P_LOCK1, "S1-C1"), (P_FREEZE, "S1-C2"), (P_POINTS, "S1-C3"), (P_CAP, "S1-C4"), (P_CAL, "S1-C5"),
             (P_CUST, "S1-C6"), (P_SAFE, "S1-C8")]


@pytest.mark.parametrize("status", ["DRAFT", "DRAFT_PENDING_OWNER", "PROPOSED", "pending owner"])
@pytest.mark.parametrize("rel,cid", DRAFTABLE)
def test_draft_or_proposed_artifact_never_satisfies(tmp_path, rel, cid, status):
    def m(o):
        o["status"] = status
        return o
    rep = G.evaluate(_complete(tmp_path, mutate={rel: m}))
    assert _cond(rep, cid)["state"] == "REJECTED_DRAFT"
    assert rep["verdict"] == "S1_NOT_READY"
    assert [x["condition"] for x in rep["missing"]] == [cid]


def test_proposed_facility_decision_never_satisfies(tmp_path):
    def m(o):
        o["decision"] = "PROPOSED"
        return o
    rep = G.evaluate(_complete(tmp_path, mutate={P_FAC: m}))
    assert _cond(rep, "S1-C7")["state"] == "REJECTED_DRAFT" and rep["verdict"] == "S1_NOT_READY"


def test_lock1_draft_file_is_only_a_precursor(tmp_path):
    root = _base(tmp_path)
    _write(root, "docs/architecture_comparison/lock1/LOCK1_DRAFT.json", {"id": "LOCK-1", "status": "SIGNED"})
    c1 = _cond(G.evaluate(root), "S1-C1")
    assert c1["state"] == "MISSING" and c1["availability"] == "PARTIAL_PRECURSORS_ONLY"


def test_lock1_must_be_signed_by_owner_with_all_decisions(tmp_path):
    def m(o):
        o["decided_by"] = "team"
        o["decisions"] = o["decisions"][:14]
        return o
    c1 = _cond(G.evaluate(_complete(tmp_path, mutate={P_LOCK1: m})), "S1-C1")
    fails = " ".join(c1["alternatives"][0]["failures"])
    assert c1["state"] == "INVALID" and "decided_by" in fails and "D-15" in fails


def test_lock1_brief_hash_mismatch_is_invalid(tmp_path):
    root = _complete(tmp_path)
    (root / P_BRIEF).write_text('{"schema": "brief edited after signing"}')
    c1 = _cond(G.evaluate(root), "S1-C1")
    assert c1["state"] == "INVALID" and "sha256 mismatch" in " ".join(c1["alternatives"][0]["failures"])


def test_lock1_location_must_match_d05_choice(tmp_path):
    c1 = _cond(G.evaluate(_complete(tmp_path, d05="D-05-A")), "S1-C1")
    assert c1["state"] == "INVALID" and "D-05" in " ".join(c1["alternatives"][0]["failures"])


def test_lock1_at_two_locations_is_ambiguous(tmp_path):
    root = _complete(tmp_path)
    _write(root, "docs/architecture_comparison/experiment_package/prereg/LOCK1.json", (root / P_LOCK1).read_bytes())
    rep = G.evaluate(root)
    assert _cond(rep, "S1-C1")["state"] == "AMBIGUOUS"
    # chained records cannot be verified against an ambiguous LOCK-1
    assert _cond(rep, "S1-C2")["state"] == "INVALID" and rep["verdict"] == "S1_NOT_READY"


def test_chained_record_must_reference_the_signed_lock1(tmp_path):
    root = _complete(tmp_path)
    other = "docs/other/LOCK1_copy.json"
    _write(root, other, (root / P_LOCK1).read_bytes())

    def m(o):
        o["lock1"] = _ref(root, other)
        return o
    rep = G.evaluate(_complete(root, mutate={P_CAL: m}))
    assert _cond(rep, "S1-C5")["state"] == "INVALID"


def test_design_analysis_is_not_a_demonstration(tmp_path):
    def m(o):
        o["evidence_basis"] = "design_analysis"
        o["instruments"][0]["evidence_class"] = "model-derived"
        return o
    c4 = _cond(G.evaluate(_complete(tmp_path, mutate={P_CAP: m})), "S1-C4")
    fails = " ".join(c4["alternatives"][0]["failures"])
    assert c4["state"] == "INVALID" and "evidence_basis" in fails and "evidence_class" in fails


def test_capability_needs_every_instrument_category_and_raw_data(tmp_path):
    def m(o):
        o["instruments"] = [i for i in o["instruments"] if i["category"] != "magnetic_field_Bz"]
        return o
    c4 = _cond(G.evaluate(_complete(tmp_path, mutate={P_CAP: m})), "S1-C4")
    assert c4["state"] == "INVALID" and "magnetic_field_Bz" in " ".join(c4["alternatives"][0]["failures"])
    root = _complete(tmp_path / "b")
    (root / P_RAW.format("flow")).write_text("edited\n")
    assert _cond(G.evaluate(root), "S1-C4")["state"] == "INVALID"


def test_feed_points_need_explicit_labels_and_no_flight_assertion(tmp_path):
    def m(o):
        o["test_points"][1]["flight_status"] = "FLIGHT_CONDITION"
        return o
    c3 = _cond(G.evaluate(_complete(tmp_path, mutate={P_POINTS: m})), "S1-C3")
    assert c3["state"] == "INVALID" and "flight_status" in " ".join(c3["alternatives"][1]["failures"])

    def m2(o):
        del o["test_points"][0]["flight_status"]
        return o
    assert _cond(G.evaluate(_complete(tmp_path / "b", mutate={P_POINTS: m2})), "S1-C3")["state"] == "INVALID"


@pytest.mark.parametrize("feed_alt,rel", [("points", P_POINTS), ("di1", P_DI1)])
def test_proposed_flight_representative_points_are_precursors_only(tmp_path, feed_alt, rel):
    def m(o):
        o["test_points"][0]["flight_status"] = "PROPOSED_FLIGHT_REPRESENTATIVE"
        return o
    rep = G.evaluate(_complete(tmp_path, feed_alt=feed_alt, mutate={rel: m}))
    assert _cond(rep, "S1-C3")["state"] == "REJECTED_DRAFT" and rep["verdict"] == "S1_NOT_READY"


def test_labels_alone_never_satisfy_feed_condition(tmp_path):
    root = _complete(tmp_path)
    # an unapproved record carrying only correctly labelled points (as the W1 closure does) never satisfies S1-C3
    def m(o):
        del o["decided_by"], o["decided_utc"]
        o["status"] = "SELECTED"
        return o
    c3 = _cond(G.evaluate(_complete(root, mutate={P_POINTS: m})), "S1-C3")
    fails = " ".join(c3["alternatives"][1]["failures"])
    assert c3["state"] == "INVALID" and "decided_by" in fails and "status" in fails

    def m2(o):
        del o["source_closure"]
        return o
    assert _cond(G.evaluate(_complete(tmp_path / "b", mutate={P_POINTS: m2})), "S1-C3")["state"] == "INVALID"


def test_w1_closure_is_only_a_precursor(tmp_path):
    root = _base(tmp_path)
    _write(root, P_CLOSURE, {"status": "DRAFT", "test_points": {"phase1_knee_N2": [
        {"id": "TP1", "flight_status": "GROUND_QUALIFICATION_POINT", "status": "PROPOSED (candidate-conditional)"}]}})
    c3 = _cond(G.evaluate(root), "S1-C3")
    assert c3["state"] == "MISSING" and c3["availability"] == "PARTIAL_PRECURSORS_ONLY"


def test_tbd_values_never_fill_a_condition(tmp_path):
    def m(o):
        o["data_custodian"] = "TBD - requires owner designation"
        return o
    assert _cond(G.evaluate(_complete(tmp_path, mutate={P_CUST: m})), "S1-C6")["state"] == "INVALID"

    def m2(o):
        o["test_points"][0]["P_feed"] = {"value": "TBD", "unit": "Pa", "source": "x", "evidence_class": "assumed"}
        return o
    assert _cond(G.evaluate(_complete(tmp_path / "b", mutate={P_POINTS: m2})), "S1-C3")["state"] == "INVALID"


def test_custody_needs_frozen_partition(tmp_path):
    def m(o):
        o["partition_frozen_before_h1_data"] = False
        o["partition"]["held_out_prediction"] = []
        return o
    c6 = _cond(G.evaluate(_complete(tmp_path, mutate={P_CUST: m})), "S1-C6")
    fails = " ".join(c6["alternatives"][0]["failures"])
    assert c6["state"] == "INVALID" and "partition_frozen_before_h1_data" in fails and "held_out_prediction" in fails


def test_safety_limits_cover_required_set(tmp_path):
    def m(o):
        o["limits"] = o["limits"][1:]
        o["abort_conditions"] = []
        return o
    c8 = _cond(G.evaluate(_complete(tmp_path, mutate={P_SAFE: m})), "S1-C8")
    fails = " ".join(c8["alternatives"][0]["failures"])
    assert c8["state"] == "INVALID" and "discharge_voltage_max" in fails and "abort_conditions" in fails


def test_references_outside_the_repository_are_rejected(tmp_path):
    root = _complete(tmp_path / "repo")
    (tmp_path / "outside.json").write_text("{}")

    def m(o):
        o["requirements_basis"] = {"path": "../outside.json", "sha256": "0" * 64}
        return o
    c2 = _cond(G.evaluate(_complete(root, mutate={P_FREEZE: m})), "S1-C2")
    assert c2["state"] == "INVALID" and "repository-relative" in " ".join(c2["alternatives"][0]["failures"])


def test_non_json_artifact_is_invalid(tmp_path):
    root = _complete(tmp_path)
    (root / P_FAC).write_text("not json")
    assert _cond(G.evaluate(root), "S1-C7")["state"] == "INVALID"


# ------------------------------------------------------------------------------------------------------ review repairs
@pytest.mark.parametrize("bad", ["2026-13-45", "2026-02-30", "2026-10-01T25:00Z", "2026-10-01T12:61:00Z", "01/10/2026"])
def test_impossible_dates_are_rejected(tmp_path, bad):
    def m(o):
        o["decided_utc"] = bad
        return o
    c1 = _cond(G.evaluate(_complete(tmp_path, mutate={P_LOCK1: m})), "S1-C1")
    assert c1["state"] == "INVALID" and "decided_utc" in " ".join(c1["alternatives"][0]["failures"])


@pytest.mark.parametrize("good", ["2026-10-01", "2026-10-01T12:30Z", "2026-10-01T12:30:59Z"])
def test_valid_dates_are_accepted(good):
    assert G._is_iso_date(good)


def test_capability_uncertainty_must_be_measured(tmp_path):
    for ec in ("assumed", "model-derived", "inferred"):
        def m(o, ec=ec):
            for i in o["instruments"]:
                i["demonstrated_uncertainty"]["evidence_class"] = ec
            return o
        c4 = _cond(G.evaluate(_complete(tmp_path / ec, mutate={P_CAP: m})), "S1-C4")
        assert c4["state"] == "INVALID"
        assert "demonstrated_uncertainty.evidence_class" in " ".join(c4["alternatives"][0]["failures"])


def test_capability_raw_data_must_be_raw_data_not_a_plan(tmp_path):
    root = _complete(tmp_path)

    def m(o):
        o["instruments"][0]["raw_data"] = _ref(root, P_CAL)
        return o
    c4 = _cond(G.evaluate(_complete(root, mutate={P_CAP: m})), "S1-C4")
    assert c4["state"] == "INVALID" and "must lie under" in " ".join(c4["alternatives"][0]["failures"])


@pytest.mark.parametrize("rel,cid,path", [
    (P_LOCK1, "S1-C1", ("decisions", 0)),
    (P_FREEZE, "S1-C2", ("items", 1)),
    (P_POINTS, "S1-C3", ("test_points", 0)),
    (P_CAL, "S1-C5", ("procedures", 2)),
])
@pytest.mark.parametrize("token", ["DRAFT", "PROPOSED", "pending"])
def test_nested_draft_markers_reject(tmp_path, rel, cid, path, token):
    def m(o):
        o[path[0]][path[1]]["status"] = token
        return o
    rep = G.evaluate(_complete(tmp_path, mutate={rel: m}))
    assert _cond(rep, cid)["state"] == "REJECTED_DRAFT" and rep["verdict"] == "S1_NOT_READY"


def test_nested_decision_marker_rejects(tmp_path):
    def m(o):
        o["facility"]["decision"] = "PENDING owner"
        return o
    assert _cond(G.evaluate(_complete(tmp_path, mutate={P_FAC: m})), "S1-C7")["state"] == "REJECTED_DRAFT"


@pytest.mark.parametrize("choice", ["PROPOSED", "PENDING", "OPEN", "D-01-A (tentative)", "D-02-A", "yes"])
def test_lock1_owner_choice_must_be_an_option_id(tmp_path, choice):
    def m(o):
        o["decisions"][0]["owner_choice"] = choice
        return o
    rep = G.evaluate(_complete(tmp_path, mutate={P_LOCK1: m}))
    c1 = _cond(rep, "S1-C1")
    assert c1["state"] == "INVALID" and "D-01" in " ".join(c1["alternatives"][0]["failures"])
    assert rep["verdict"] == "S1_NOT_READY"


def test_di1_needs_labelled_feed_points(tmp_path):
    def m(o):
        del o["test_points"]
        return o
    c3 = _cond(G.evaluate(_complete(tmp_path, feed_alt="di1", mutate={P_DI1: m})), "S1-C3")
    assert c3["state"] == "INVALID" and "test_points" in " ".join(c3["alternatives"][0]["failures"])

    def m2(o):
        for tp in o["test_points"]:
            tp["gas"] = "Xe"
        return o
    c3 = _cond(G.evaluate(_complete(tmp_path / "b", feed_alt="di1", mutate={P_DI1: m2})), "S1-C3")
    assert c3["state"] == "INVALID"


def test_bad_spec_options_are_spec_errors(tmp_path):
    p = tmp_path / "s.json"
    for mut in ("pattern", "prefix"):
        spec = json.loads(SPEC.read_text())
        rules = spec["conditions"][0]["alternatives"][0]["rules"] if mut == "pattern" else \
            next(r for r in spec["conditions"][3]["alternatives"][0]["rules"] if r["type"] == "each_item")["rules"]
        for r in rules:
            if mut == "pattern" and r["type"] == "decisions_decided":
                r["choice_pattern"] = "^D-[A-Z]$"
            if mut == "prefix" and r["type"] == "sha256_ref":
                r["path_prefix"] = "../raw/"
        p.write_text(json.dumps(spec))
        with pytest.raises(G.SpecError):
            G.load_spec(p)


# ------------------------------------------------------------------------------------------------------ determinism / purity
def test_deterministic_and_location_independent(tmp_path):
    a = G.render(G.evaluate(_complete(tmp_path / "a")))
    b = G.render(G.evaluate(_complete(tmp_path / "b")))
    assert a == b == G.render(G.evaluate(tmp_path / "a"))
    assert str(tmp_path) not in a
    e1, e2 = (G.render(G.evaluate(_base(tmp_path / x))) for x in ("c", "d"))
    assert e1 == e2


def test_gate_writes_nothing(tmp_path):
    root = _complete(tmp_path)

    def snap():
        return {str(p): (p.stat().st_mtime_ns, p.stat().st_size) for p in root.rglob("*")}
    before = snap()
    G.evaluate(root)
    assert snap() == before


def test_cli_exit_codes_and_check(tmp_path, capsys):
    root = _complete(tmp_path / "ready")
    out = tmp_path / "rep.json"
    assert G.main(["--repo-root", str(root), "--out", str(out)]) == 0
    assert G.main(["--repo-root", str(root), "--check", str(out)]) == 0
    empty = _base(tmp_path / "empty")
    assert G.main(["--repo-root", str(empty), "--check", str(out)]) == 1
    assert G.main(["--repo-root", str(empty)]) == 1
    assert G.main(["--repo-root", str(empty), "--spec", str(tmp_path / "missing.json")]) == 2
    capsys.readouterr()


def test_module_is_standalone():
    import ast
    tree = ast.parse(SCRIPT.read_text())
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= {"__future__", "argparse", "datetime", "hashlib", "json", "os", "re", "sys", "pathlib"}, mods
    src = SCRIPT.read_text()
    assert "time" not in mods and "random" not in mods
    for bad in ("datetime.now", "datetime.utcnow", "date.today", "time.time()", "random"):
        assert bad not in src


# ------------------------------------------------------------------------------------------------------ committed report
def test_committed_status_report_is_a_not_ready_snapshot_of_this_spec():
    rep = json.loads(REPORT.read_text())
    assert rep["schema"] == G.REPORT_SCHEMA and rep["generated_by"] == "scripts/experiments/s1_readiness.py"
    assert rep["spec"]["path"] == "docs/experiments/s1_readiness/s1_readiness_conditions_v1.json"
    assert rep["spec"]["sha256"] == hashlib.sha256(SPEC.read_bytes()).hexdigest()
    assert rep["verdict"] == "S1_NOT_READY" and rep["n_conditions"] == 8
    assert rep["authority"]["ok"] is True
    assert {d["path"]: d["sha256"] for d in rep["authority"]["documents"]} == \
        {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in OD_FILES}
    assert rep["n_missing_items"] == 8 and [m["owner_condition"] for m in rep["missing"]] == OWNER_CONDITIONS
    assert all(c["state"] != "SATISFIED" for c in rep["conditions"])
    assert os.sep + "home" + os.sep not in REPORT.read_text()
