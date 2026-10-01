"""M16 subsystem maturity matrix v4 (A9.6 sec. 16 refresh; lane A9_6_M16): outputs current, evidence rules, fail-closed."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "docs" / "experiments" / "hall_icp" / "integration" / "m16_v4"
V3_REL = "docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json"
A92_REL = "docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json"
OQ4_REL = "docs/budgets/owner_decisions/owner_questions_state_v4.json"


def _builder():
    spec = importlib.util.spec_from_file_location("m16_v4_builder", HERE / "build_subsystem_maturity_v4.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _builder()
DOC = B.build()
ROWS = DOC["rows"]


def _load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_outputs_are_current_and_parse():
    for path, text in B.outputs(DOC).items():
        assert path.read_text(encoding="utf-8") == text, path.name
    json.loads((HERE / "subsystem_maturity_v4.json").read_text(encoding="utf-8"))


def test_v3_pinned_unchanged_and_every_row_refreshed():
    v3 = _load(V3_REL)
    assert hashlib.sha256((ROOT / V3_REL).read_bytes()).hexdigest() == B.PINS[V3_REL][0]
    assert [(r["row"], r["key"]) for r in ROWS] == [(r["row"], r["key"]) for r in v3["rows"]]
    for p in DOC["pins"]:
        assert hashlib.sha256((ROOT / p["path"]).read_bytes()).hexdigest() == p["sha256"], p["path"]
    for p in DOC["pins"]:
        assert not any(g in p["path"] for g in ("lane_registry", "trigger_registry", "fired_triggers", "trigger_ledger",
                                                "runtime_state"))


def test_nothing_written_under_the_globbed_h2_7_folder():
    folder = ROOT / "docs" / "budgets" / "subsystem_maturity"
    assert sorted(p.name for p in folder.glob("*.json")) == ["subsystem_maturity_v1.json", "subsystem_maturity_v2.json"]
    for path in B.outputs(DOC):
        assert folder not in path.parents


def test_state_vocabulary_is_the_v3_vocabulary():
    v3 = _load(V3_REL)
    assert set(DOC["state_vocabulary"]) == set(v3["scheduler_rule"]["states"]) | {"SUPERSEDED_FOR_PRIMARY_LINE"}
    assert DOC["waits_on_vocabulary"] == v3["waits_on_vocabulary"]
    for r in ROWS:
        assert r["execution_state"] in DOC["state_vocabulary"]
        assert r["waits_on"] is None or r["waits_on"] in DOC["waits_on_vocabulary"]
        assert "PASS" not in json.dumps(r["a9_2_statuses"])


def test_no_physical_row_ready_or_verified_without_measured_artifact():
    for r in ROWS:
        assert r["physical_item"] is True
        if r["execution_state"] in ("VERIFIED", "READY"):
            arts = r["evidence"]["new_measured_or_validated_artifacts"]
            assert arts and all(a["quantity_type"] == "measured" and (ROOT / a["path"]).exists() for a in arts), r["row"]
        for im in r["a9_6_implemented"]:
            assert im["counts_as_evidence"] is False and im["kind"] in DOC["implementation_kinds"]
    # A9.6 batch: frameworks only -> nothing READY / VERIFIED / RUNNING
    assert {r["execution_state"] for r in ROWS} <= {"BLOCKED", "SUPERSEDED_FOR_PRIMARY_LINE"}


def test_derive_state_adversarial():
    ok_meas = {"quantity_type": "measured", "kind": "HARDWARE_RECORD", "synthetic": False, "path_exists": True}
    base = {"superseded_for_primary_line": False, "physical": True, "interface_frozen": True,
            "readiness_conditions": [{"id": "C", "state": "SATISFIED"}], "measured_artifacts": [], "worked_by": None,
            "blocking_item": None, "contributing_open": [], "named_engineer": "N"}
    # software / framework completeness never verifies a physical row
    for kind in B.SPEC.IMPLEMENTATION_KINDS:
        rec = dict(base, measured_artifacts=[dict(ok_meas, kind=kind)])
        assert B.derive_state(rec)[0] != "VERIFIED", kind
    assert B.derive_state(dict(base, measured_artifacts=[dict(ok_meas, synthetic=True)]))[0] != "VERIFIED"
    assert B.derive_state(dict(base, measured_artifacts=[dict(ok_meas, path_exists=False)]))[0] != "VERIFIED"
    assert B.derive_state(dict(base, measured_artifacts=[dict(ok_meas, quantity_type="model-derived")]))[0] != "VERIFIED"
    assert B.derive_state(dict(base, measured_artifacts=[{k: v for k, v in ok_meas.items() if k != "synthetic"}]))[0] \
        != "VERIFIED"  # missing 'synthetic' flag -> treated as synthetic (fail closed)
    assert B.derive_state(dict(base, interface_frozen=False, measured_artifacts=[ok_meas]))[0] != "VERIFIED"
    assert B.derive_state(dict(base, readiness_conditions=[], measured_artifacts=[ok_meas]))[0] != "VERIFIED"
    assert B.derive_state(dict(base, measured_artifacts=[ok_meas]))[0] == "VERIFIED"  # positive control
    # READY needs no blocker and a named engineer (row 140)
    assert B.derive_state(dict(base, interface_frozen=False))[0] == "READY"
    assert B.derive_state(dict(base, interface_frozen=False, named_engineer=None))[0] == "BLOCKED"
    assert B.derive_state(dict(base, interface_frozen=False, contributing_open=[{"id": "X"}]))[0] == "BLOCKED"
    # RUNNING never for owner decisions / measurements / quotations
    wb = {"produces_every_missing_input": True}
    for kind in B.NEVER_RUNNING_BLOCKERS:
        rec = dict(base, interface_frozen=False, blocking_item={"kind": kind}, worked_by=wb)
        assert B.derive_state(rec)[0] == "BLOCKED", kind
    rec = dict(base, interface_frozen=False, blocking_item={"kind": "V3_CARRIED"}, worked_by={"produces_every_missing_input": False})
    assert B.derive_state(rec)[0] == "BLOCKED"
    rec = dict(base, interface_frozen=False, blocking_item={"kind": "V3_CARRIED"}, worked_by=wb)
    assert B.derive_state(rec)[0] == "RUNNING"
    assert B.derive_state(dict(base, superseded_for_primary_line=True))[0] == "SUPERSEDED_FOR_PRIMARY_LINE"


def test_ten_a9_2_statuses_verbatim():
    a92 = _load(A92_REL)["decisions"]["a9_10_statuses"]
    assert len(a92) == 10 and DOC["a9_2_statuses"]["statuses"] == a92
    carried = {}
    for r in ROWS:
        for k, v in r["a9_2_statuses"].items():
            assert a92[k] == v
            carried[k] = v
    assert carried == a92
    v3 = {r["row"]: (r.get("a9_2") or {}).get("statuses", {}) for r in _load(V3_REL)["rows"]}
    for r in ROWS:
        assert r["a9_2_statuses"] == v3[r["row"]], r["row"]
    by_key = {r["key"]: r for r in ROWS}
    assert by_key["icp_neutralizer_head"]["a9_2_statuses"]["ICP electron-current capacity"] == "PENDING_ICP45"
    assert by_key["h1_anode_material"]["a9_2_statuses"]["final anode material"] == "OPEN"
    assert by_key["thermal_control"]["a9_2_statuses"]["coupled H-1/ICP thermal closure"] == "UNRESOLVED"
    assert by_key["flight_rf_chain"]["a9_2_statuses"]["RF component ratings"] == "TBD_AFTER_IMPEDANCE_MAP"
    for key in ("icp_neutralizer_head", "h1_anode_material", "h1_anode_heat_path", "thermal_control", "flight_rf_chain"):
        assert by_key[key]["execution_state"] == "BLOCKED"


def test_every_blocking_id_resolves_in_state_v4():
    oq4 = {}
    for r in _load(OQ4_REL)["rows"]:
        oq4.setdefault(r["id"], []).append(r)
    used = set()
    for r in ROWS:
        for b in r["contributing_blockers"]:
            assert b["kind"] in DOC["blocker_kinds"]
            if b["kind"] == "OWNER_QUESTION":
                assert [x["status"] for x in oq4.get(b["id"], [])] == ["TBD_OWNER"], b["id"]
                used.add(b["id"])
        assert r["owner"]["owner_question"].startswith("M16-V3-Q-01")
    assert sorted(used) == DOC["owner_question_ids_used"]
    assert [x["status"] for x in oq4["M16-V3-Q-01"]] == ["TBD_OWNER"]
    for rid in ("OD2", "OD3", "OD6", "OD12", "OD14", "RVMQ-01"):  # register completion ids are usable blockers
        assert rid in used, rid


def test_implemented_ids_and_blockers_resolve_in_their_artifacts():
    ctx = B.Ctx()
    for r in ROWS:
        for im in r["a9_6_implemented"]:
            if "ids" in im:
                key = next(k for k, v in B.ARTIFACTS.items() if v[0] == im["artifact"])
                for i in im["ids"]:
                    assert B.find(ctx.docs[key], im["container"], i)["id"] == i
            else:
                for p in im["paths"]:
                    assert (ROOT / p).is_file()
        for b in r["contributing_blockers"]:
            assert (ROOT / b["artifact"]).is_file()


def test_diff_table_complete_and_row_13_repointed():
    assert [d["row"] for d in DOC["diff_v3_v4"]] == [r["row"] for r in ROWS]
    v3 = {r["row"]: r["a9_refresh"]["execution_state"] for r in _load(V3_REL)["rows"]}
    for d, r in zip(DOC["diff_v3_v4"], ROWS):
        assert d["state_v3"] == v3[d["row"]] and d["state_v4"] == r["execution_state"]
        assert d["state_changed"] == (d["state_v3"] != d["state_v4"]) and d["reason"]
        assert d["blocking_item_changed"] == bool(r["blocking_item"] and not r["blocking_item"]["carried_from_v3"])
    repointed = [d["row"] for d in DOC["diff_v3_v4"] if d["blocking_item_changed"]]
    assert repointed == [13]
    p3 = {i["id"]: i for i in _load("docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json")["items"]}
    for it in ROWS[12]["blocking_item"]["items"]:
        assert str(p3[it["id"]]["value"]).startswith("TBD"), it["id"]


def test_required_sections_present():
    for k in ("items", "interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
              "m16_impact", "readiness_rules", "pins", "referenced_not_pinned"):
        assert k in DOC, k
    dirs = {x["direction"] for x in DOC["interface_demands"]}
    assert dirs == {"consumes", "provides"}
    for it in DOC["items"]:
        for k in ("id", "value", "units", "basis", "source", "evidence_class", "status", "freeze_point"):
            assert k in it
    assert any(x["path"] == V3_REL for x in DOC["historical_reuse"])


def test_fail_closed(monkeypatch):
    rows = copy.deepcopy(B.SPEC.ROWS)
    rows[18]["contributing"].append(("OWNER_QUESTION", "OQ4", "P1Q-10"))  # answered by A9.4, not an open blocker
    monkeypatch.setattr(B.SPEC, "ROWS", rows)
    with pytest.raises(B.BuildError):
        B.build()
    rows = copy.deepcopy(B.SPEC.ROWS)
    rows[18]["contributing"] = [x for x in rows[18]["contributing"] if x[2] != "P1Q-10"]
    rows[13]["contributing"].append(("P3_INPUT", "P3", "P3-M-01"))  # owner-given value, not TBD
    monkeypatch.setattr(B.SPEC, "ROWS", rows)
    with pytest.raises(B.BuildError):
        B.build()
    rows = copy.deepcopy(B.SPEC.ROWS)
    rows[13]["contributing"] = [x for x in rows[13]["contributing"] if x[2] != "P3-M-01"]
    rows[1]["implemented"].append(("MP", "bom", ["A9B-DOES-NOT-EXIST"], "BUDGET", "x"))
    monkeypatch.setattr(B.SPEC, "ROWS", rows)
    with pytest.raises(B.BuildError):
        B.build()
    rows[1]["implemented"].pop()
    rows[5]["contributing"].append(("NOT_A_KIND", "OQ4", "OD2"))
    with pytest.raises(B.BuildError):
        B.build()
    rows[5]["contributing"].pop()
    pins = dict(B.PINS)
    pins[V3_REL] = ("0" * 64, "tampered")
    monkeypatch.setattr(B, "PINS", pins)
    with pytest.raises(B.BuildError):
        B.build()


def test_no_forbidden_substring_in_code():
    needle = "xe_" + "ledger"
    for p in list(HERE.glob("*.py")) + [Path(__file__)]:
        assert needle not in p.read_text(encoding="utf-8"), p.name


def test_s01_rvm_open_readings_agree_with_state_v4():
    """S-01 (consolidated verification): every RVM open reading carries the status of its row in owner-question state
    v4 (the current register); OD13 is SUPERSEDED in both; no RVM interface demand towards v4 reads PENDING."""
    rvm = json.loads((ROOT / "docs/requirements/rvm_a9/rvm_a9_v1.json").read_text(encoding="utf-8"))
    v4 = {r["id"]: r for r in json.loads((ROOT / "docs/budgets/owner_decisions/owner_questions_state_v4.json")
                                        .read_text(encoding="utf-8"))["rows"]}
    # A9.16 step 1: readings answered by the owner (A9.8 .. A9.15) name state v5 as their register and must be
    # answered there; the others still agree with state v4 by status
    v5 = {}
    for r in json.loads((ROOT / "docs/budgets/owner_decisions/owner_questions_state_v5.json")
                        .read_text(encoding="utf-8"))["rows"]:
        if r.get("v4_status") == "TBD_OWNER" or r["status"] == "TBD_OWNER":
            v5[r["id"]] = r
    n = 0
    for row in rvm["rows"]:
        for o in row.get("open_readings", []):
            if o["current_register"].endswith("owner_questions_state_v5.json"):
                assert o["status"] == "OWNER_DECIDED" and v4[o["id"]]["status"] == "TBD_OWNER", (row["id"], o["id"])
                assert v5[o["id"]]["status"].startswith(("ANSWERED_BY_A9_", "AMENDED_BY_A9_15")), (row["id"], o["id"])
            else:
                assert o["id"] in v4 and v4[o["id"]]["status"] == o["status"], (row["id"], o["id"])
            n += 1
    assert n > 0
    od13 = [o for r in rvm["rows"] if r["id"] == "RVM-12" for o in r["open_readings"] if o["id"] == "OD13"]
    assert od13 and od13[0]["status"] == "SUPERSEDED" == v4["OD13"]["status"]
    out = HERE / "subsystem_maturity_v4.json"
    doc = json.loads(out.read_text(encoding="utf-8"))
    rec = doc["rvm_register_reconciliation"]
    assert rec["all_agree"] is True and rec["n_readings"] == n
    assert "PENDING fo_a9_6_" not in out.read_text(encoding="utf-8")
