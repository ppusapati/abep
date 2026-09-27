"""Tests of the S1a engineering-readiness gate (fo_s1a_engineering_gate; scripts/experiments/s1a_readiness.py).

Synthetic repositories are built in tmp_path: the four owner decision files are copied byte-identical from this
repository (the authority pins them); every other artifact is synthetic and carries no physical value (quantities are
labelled test fixtures). No test reads or needs the N4 gate, another lane's worktree or any Julia output.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "experiments" / "s1a_readiness.py"
SPEC_REL = "docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json"
STATUS_REL = "docs/experiments/s1a_readiness/s1a_readiness_status_current.json"
DECISIONS = [
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A1_controls.json",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A2_execution_directive.json",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json",
]
P_HW = "docs/experiments/hardware/s1a_engineering_hardware_record.json"
P_LIM = "docs/experiments/hardware/s1a_safety_operational_limits.json"
P_FEED = "docs/architecture_comparison/feed_state_closure/s1a_feed_points.json"
P_FEED_S1 = "docs/architecture_comparison/feed_state_closure/s1_feed_points.json"
P_CAL = "docs/experiments/instrumentation/s1a_calibration_procedures_frozen.json"
P_FAC = "docs/decisions/OD_S1A_FACILITY.json"
P_FW = "docs/experiments/custody/s1a_data_firewall_frozen.json"
P_HWREQ = "docs/experiments/hardware/hardware_requirements_v1.json"
P_CLOSURE = "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json"
P_W5 = "docs/validation/hall_transport_v2_prereg/w5_fixture.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("s1a_readiness", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load_module()


# ---------------------------------------------------------------------------------------------------------- fixtures
def _write(root: Path, rel: str, obj) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1) if not isinstance(obj, str) else obj, encoding="utf-8")


def _ref(root: Path, rel: str) -> dict:
    return {"path": rel, "sha256": hashlib.sha256((root / rel).read_bytes()).hexdigest()}


def _q(unit="-"):
    return {"value": 1.0, "unit": unit, "source": "synthetic test fixture", "evidence_class": "assumed"}


def _spec() -> dict:
    return json.loads((REPO / SPEC_REL).read_text(encoding="utf-8"))


def _required(spec: dict, cid: str, field: str, key: str) -> list[str]:
    cond = next(c for c in spec["conditions"] if c["id"] == cid)
    for r in cond["alternatives"][0]["rules"]:
        if r["type"] == "covers" and r["field"] == field and r["key"] == key:
            return r["required"]
    raise KeyError((cid, field, key))


def base_repo(root: Path) -> Path:
    """Authority documents and spec only: every condition MISSING."""
    for rel in DECISIONS + [SPEC_REL]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, root / rel)
    return root


def add_firewall(root: Path, spec: dict, **over) -> None:
    _write(root, P_W5, {"fixture": "stand-in for a W5 pre-registration document"})
    fw = {
        "id": "s1a_data_firewall", "status": "FROZEN", "decided_by": "owner", "decided_utc": "2026-10-01",
        "w5_basis": _ref(root, P_W5), "data_custodian": "custodian role (fixture)",
        "h1_hall_discharge_in_s1a": "FORBIDDEN",
        "allowed_classes": [{"id": i, "definition": f"{i} (fixture)", "release_rule": "any track (fixture)"}
                            for i in _required(spec, "S1A-FW", "allowed_classes", "id")],
        "forbidden_or_embargoed": [{"id": i, "quantity": f"{i} (fixture)", "treatment": "FORBIDDEN_IN_S1A",
                                    "consequence_if_exposed": "OUTPUTS_SEEN per W5 (fixture)"}
                                   for i in _required(spec, "S1A-FW", "forbidden_or_embargoed", "id")],
        "registration_inputs": [{"id": i, "release_condition": "custodian after LOCK-H1 (fixture)"}
                                for i in _required(spec, "S1A-FW", "registration_inputs", "id")],
        "custody_rule": "fixture", "outputs_seen_rule": "fixture", "repository_rule": "fixture",
        "breach_response": "fixture", "release_log": "fixture",
    }
    for a in fw["allowed_classes"]:
        if a["id"] == "QUALITATIVE_RGA":
            a["no_dose_or_lifetime_claim"] = True
    fw.update(over)
    _write(root, P_FW, fw)


def complete_repo(root: Path) -> Path:
    base_repo(root)
    spec = _spec()
    _write(root, P_HWREQ, {"fixture": "stand-in W3 register"})
    _write(root, P_CLOSURE, {"fixture": "stand-in W1 closure"})
    add_firewall(root, spec)
    _write(root, P_HW, {
        "status": "IDENTIFIED_FOR_S1A", "recorded_by": "experiment team (fixture)", "recorded_utc": "2026-10-01",
        "accepted_by": "owner", "accepted_utc": "2026-10-02", "requirements_basis": _ref(root, P_HWREQ),
        "items": [{"id": i, "status": "AVAILABLE", "serial_or_part_id": f"SN-{i}",
                   "configuration_state": "RECORDED_NOT_FROZEN" if i == "H-1" else "FROZEN_FOR_QUALIFICATION",
                   "configuration_record": f"record {i}"} for i in _required(spec, "S1A-C1", "items", "id")],
    })
    _write(root, P_FAC, {
        "id": "od_s1a_facility", "decided_by": "owner", "decided_utc": "2026-10-01", "decision": "APPROVED",
        "facility": {"name": "facility (fixture)", "vacuum_facility": "chamber (fixture)",
                     "safety_responsible": "facility safety officer (fixture)", "same_as_hall_on_facility": False},
    })
    doms = {"magnet_current_max": "electrical", "supply_voltage_max": "electrical",
            "cathode_heater_current_max": "electrical", "background_pressure_max": "vacuum",
            "component_temperature_max": "thermal", "coil_winding_temperature_max": "thermal",
            "feed_pressure_max": "gas", "gas_handling_oxidizer": "gas"}
    _write(root, P_LIM, {
        "status": "APPROVED", "approved_by": "owner", "approved_utc": "2026-10-03",
        "facility_choice": _ref(root, P_FAC),
        "limits": [{"quantity": q, "domain": doms[q], "limit": "per source (fixture)", "source": "fixture",
                    "action_on_exceedance": "safe shutdown (fixture)"}
                   for q in _required(spec, "S1A-C2", "limits", "quantity")],
        "interlocks": [{"id": i, "function": "fixture", "verification": "fixture"}
                       for i in _required(spec, "S1A-C2", "interlocks", "id")],
        "abort_conditions": [{"id": "AB-1", "trigger": "fixture", "action": "fixture"}],
    })
    _write(root, P_FEED, {
        "status": "RELEASED_FOR_S1A", "decided_by": "owner", "decided_utc": "2026-10-01",
        "source_closure": _ref(root, P_CLOSURE), "use_restriction": "COLD_FLOW_CALIBRATION_NO_HALL_DISCHARGE",
        "test_points": [{"id": "GQ-1", "source_point_id": "TP1-X-L1", "flight_status": "GROUND_QUALIFICATION_POINT",
                         "gas": "N2", "m_dot_s": _q("kg/s"), "P_feed": _q("Pa"), "T_feed": _q("K"),
                         "x_s": _q("-")}],
    })
    _write(root, P_CAL, {
        "status": "FROZEN", "decided_by": "owner", "decided_utc": "2026-10-04", "data_firewall": _ref(root, P_FW),
        "procedures": [{"category": c, "procedure_id": f"PR-{k}", "procedure": "fixture", "traceability": "fixture",
                        "acceptance_rule": "fixture", "s1a_data_class": "CALIBRATION",
                        **({"cathode_temperature_labelling": "tube thermocouple never labelled emitter (fixture)"}
                           if c == "temperature_channels" else {})}
                       for k, c in enumerate(_required(spec, "S1A-C4", "procedures", "category"))],
    })
    return root


def _edit(root: Path, rel: str, fn) -> None:
    obj = json.loads((root / rel).read_text(encoding="utf-8"))
    fn(obj)
    _write(root, rel, obj)


def _state(rep: dict, cid: str) -> str:
    return next(c["state"] for c in rep["conditions"] if c["id"] == cid)


# ------------------------------------------------------------------------------------------------------------- tests
def test_spec_valid_and_firewall_mandatory():
    spec = gate.load_spec(REPO / SPEC_REL)
    ids = [c["id"] for c in spec["conditions"]]
    assert ids == ["S1A-C1", "S1A-C2", "S1A-C3", "S1A-C4", "S1A-C5", "S1A-FW"]
    bad = copy.deepcopy(spec)
    bad["conditions"] = [c for c in bad["conditions"] if c["id"] != "S1A-FW"]
    with pytest.raises(gate.SpecError):
        gate.validate_spec(bad)
    bad = copy.deepcopy(spec)
    next(c for c in bad["conditions"] if c["id"] == "S1A-FW")["fail_closed"] = False
    with pytest.raises(gate.SpecError):
        gate.validate_spec(bad)


def test_repository_today_not_ready_and_report_reproduces():
    rep = gate.evaluate(REPO)
    assert rep["authority"]["ok"], rep["authority"]["failures"]
    assert rep["verdict"] == "S1A_NOT_READY"
    assert rep["firewall"]["fail_closed"] is True
    assert rep["n_missing_items"] == len(rep["missing"]) >= 1
    committed = (REPO / STATUS_REL).read_text(encoding="utf-8")
    assert committed == gate.render(rep), "regenerate: python scripts/experiments/s1a_readiness.py --out " + STATUS_REL


def test_all_missing(tmp_path):
    rep = gate.evaluate(base_repo(tmp_path))
    assert rep["authority"]["ok"]
    assert rep["verdict"] == "S1A_NOT_READY"
    assert rep["n_satisfied"] == 0 and rep["n_missing_items"] == 6
    assert {m["state"] for m in rep["missing"]} == {"MISSING"}


def test_complete_fixture_ready(tmp_path):
    rep = gate.evaluate(complete_repo(tmp_path))
    assert rep["authority"]["ok"], rep["authority"]["failures"]
    assert rep["missing"] == [], json.dumps(rep["missing"], indent=1)[:3000]
    assert rep["verdict"] == "S1A_READY"
    assert rep["firewall"] == {**rep["firewall"], "state": "SATISFIED", "fail_closed": False}
    assert gate.main(["--repo-root", str(tmp_path)]) == 0


def test_firewall_missing_fails_closed(tmp_path):
    root = complete_repo(tmp_path)
    (root / P_FW).unlink()
    rep = gate.evaluate(root)
    assert rep["verdict"] == "S1A_NOT_READY"
    assert rep["firewall"]["state"] == "MISSING" and rep["firewall"]["fail_closed"] is True
    # the procedures that must match the firewall's allowed classes fail closed too
    assert _state(rep, "S1A-C4") == "INVALID"
    fails = next(m for m in rep["missing"] if m["condition"] == "S1A-C4")["needed"][0]["failures"]
    assert any("fails closed" in f for f in fails)
    for cid in ("S1A-C1", "S1A-C2", "S1A-C3", "S1A-C5"):
        assert _state(rep, cid) == "SATISFIED"


@pytest.mark.parametrize("token", ["DRAFT", "PROPOSED", "PENDING_OWNER"])
def test_draft_firewall_rejected_and_fails_closed(tmp_path, token):
    root = complete_repo(tmp_path)
    _edit(root, P_FW, lambda o: o.update(status=token))
    rep = gate.evaluate(root)
    assert _state(rep, "S1A-FW") == "REJECTED_DRAFT"
    assert rep["firewall"]["fail_closed"] and rep["verdict"] == "S1A_NOT_READY"
    assert _state(rep, "S1A-C4") == "INVALID"


@pytest.mark.parametrize("rel,path_to_status", [
    (P_HW, ("status",)), (P_LIM, ("status",)), (P_CAL, ("status",)), (P_FAC, ("decision",)),
    (P_HW, ("items", 0, "status")), (P_FEED, ("test_points", 0, "flight_status")),
])
def test_draft_artifacts_rejected(tmp_path, rel, path_to_status):
    root = complete_repo(tmp_path)

    def mark(o):
        cur = o
        for k in path_to_status[:-1]:
            cur = cur[k]
        cur[path_to_status[-1]] = "PROPOSED_FLIGHT_REPRESENTATIVE" if "flight_status" in path_to_status else "DRAFT"
    _edit(root, rel, mark)
    rep = gate.evaluate(root)
    assert rep["verdict"] == "S1A_NOT_READY"
    assert "REJECTED_DRAFT" in {m["state"] for m in rep["missing"]}


def test_firewall_forbids_hall_discharge_and_needs_all_classes(tmp_path):
    root = complete_repo(tmp_path)
    _edit(root, P_FW, lambda o: o.update(h1_hall_discharge_in_s1a="ALLOWED"))
    assert _state(gate.evaluate(root), "S1A-FW") == "INVALID"
    root2 = complete_repo(tmp_path / "b")
    _edit(root2, P_FW, lambda o: o.update(forbidden_or_embargoed=[x for x in o["forbidden_or_embargoed"]
                                                                  if x["id"] != "VO-ID"]))
    rep = gate.evaluate(root2)
    assert _state(rep, "S1A-FW") == "INVALID" and rep["firewall"]["fail_closed"]
    root3 = complete_repo(tmp_path / "c")
    _edit(root3, P_FW, lambda o: [a.pop("no_dose_or_lifetime_claim", None) for a in o["allowed_classes"]])
    assert _state(gate.evaluate(root3), "S1A-FW") == "INVALID"


def test_firewall_pin_to_w5_breaks_on_change(tmp_path):
    root = complete_repo(tmp_path)
    _write(root, P_W5, {"fixture": "W5 changed after the firewall was frozen"})
    rep = gate.evaluate(root)
    assert _state(rep, "S1A-FW") == "INVALID" and rep["verdict"] == "S1A_NOT_READY"


def test_procedure_class_must_be_allowed_by_firewall(tmp_path):
    root = complete_repo(tmp_path)
    _edit(root, P_CAL, lambda o: o["procedures"][0].update(s1a_data_class="VO-ID"))
    rep = gate.evaluate(root)
    assert _state(rep, "S1A-C4") == "INVALID" and _state(rep, "S1A-FW") == "SATISFIED"


def test_h1_recorded_not_frozen_ok_but_serial_required(tmp_path):
    root = complete_repo(tmp_path)
    assert gate.evaluate(root)["verdict"] == "S1A_READY"
    _edit(root, P_HW, lambda o: o["items"][0].update(serial_or_part_id="TBD - requires delivery"))
    assert _state(gate.evaluate(root), "S1A-C1") == "INVALID"


def test_feed_points_must_be_ground_qualification_with_n2(tmp_path):
    root = complete_repo(tmp_path)
    _edit(root, P_FEED, lambda o: o["test_points"][0].update(gas="Xe"))
    assert _state(gate.evaluate(root), "S1A-C3") == "INVALID"
    root2 = complete_repo(tmp_path / "b")
    _edit(root2, P_FEED, lambda o: o["test_points"][0]["m_dot_s"].update(evidence_class="guess"))
    assert _state(gate.evaluate(root2), "S1A-C3") == "INVALID"


def test_n4_s1_release_is_an_alternative(tmp_path):
    root = complete_repo(tmp_path)
    obj = json.loads((root / P_FEED).read_text(encoding="utf-8"))
    obj["status"] = "RELEASED_FOR_S1"
    obj.pop("use_restriction")
    _write(root, P_FEED_S1, obj)
    rep = gate.evaluate(root)
    # the S1a file still satisfies its own alternative; the gate reports both, and never chooses between locations
    assert _state(rep, "S1A-C3") == "SATISFIED"
    (root / P_FEED).unlink()
    rep = gate.evaluate(root)
    assert _state(rep, "S1A-C3") == "SATISFIED"
    c3 = next(c for c in rep["conditions"] if c["id"] == "S1A-C3")
    assert c3["satisfied_by"] == "S1A-C3-released-for-s1"


def test_invalid_date_and_wrong_owner_rejected(tmp_path):
    root = complete_repo(tmp_path)
    _edit(root, P_FAC, lambda o: o.update(decided_utc="2026-13-45"))
    assert _state(gate.evaluate(root), "S1A-C5") == "INVALID"
    root2 = complete_repo(tmp_path / "b")
    _edit(root2, P_LIM, lambda o: o.update(approved_by="engineering lead"))
    assert _state(gate.evaluate(root2), "S1A-C2") == "INVALID"


def test_safety_limits_chain_to_facility(tmp_path):
    root = complete_repo(tmp_path)
    _edit(root, P_FAC, lambda o: o["facility"].update(name="changed after approval"))
    rep = gate.evaluate(root)
    assert _state(rep, "S1A-C5") == "SATISFIED" and _state(rep, "S1A-C2") == "INVALID"


def test_authority_fails_closed(tmp_path):
    root = complete_repo(tmp_path)
    p = root / DECISIONS[3]
    p.write_bytes(p.read_bytes() + b" ")
    rep = gate.evaluate(root)
    assert not rep["authority"]["ok"] and rep["verdict"] == "S1A_NOT_READY"
    assert rep["missing"] == []  # every condition satisfied, yet not ready
    root2 = complete_repo(tmp_path / "b")
    (root2 / DECISIONS[0]).unlink()
    assert gate.evaluate(root2)["verdict"] == "S1A_NOT_READY"


def test_owner_text_and_clauses_verbatim(tmp_path):
    root = complete_repo(tmp_path)
    spec = _spec()
    spec["authority"]["owner_text"]["text"] = spec["authority"]["owner_text"]["text"].replace("only ", "")
    _write(root, SPEC_REL, spec)
    rep = gate.evaluate(root)
    assert not rep["authority"]["ok"] and rep["verdict"] == "S1A_NOT_READY"
    spec = _spec()
    spec["conditions"][0]["owner_clause"] = "any hardware at all"
    _write(root, SPEC_REL, spec)
    assert not gate.evaluate(root)["authority"]["ok"]


def test_deterministic_and_location_independent(tmp_path):
    a = gate.render(gate.evaluate(complete_repo(tmp_path / "one")))
    b = gate.render(gate.evaluate(complete_repo(tmp_path / "two" / "deeper")))
    assert a == b == gate.render(gate.evaluate(tmp_path / "one"))
    assert str(tmp_path) not in a


def test_reference_outside_repository_rejected(tmp_path):
    root = complete_repo(tmp_path)
    _edit(root, P_HW, lambda o: o.update(requirements_basis={"path": "../outside.json", "sha256": "0" * 64}))
    assert _state(gate.evaluate(root), "S1A-C1") == "INVALID"


def test_gate_is_independent_of_n4():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "import s1_readiness" not in src and "from s1_readiness" not in src
    assert "abep_sim" not in src.split('"""', 2)[2] and "hallthruster_bridge" not in src.split('"""', 2)[2]
    spec_text = (REPO / SPEC_REL).read_text(encoding="utf-8")
    assert "docs/experiments/s1_readiness/" not in json.dumps([c["alternatives"] for c in _spec()["conditions"]])
    assert "S1_NOT_READY 0/8" in spec_text
