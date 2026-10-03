"""M16 v5 (scheduler blocking items re-derived from the owner answers A9.8 .. A9.21, the A9.21 programme order and
GNG-ICP-01): outputs current, v4 byte-identical, every v4 row / blocker dispositioned, no readiness advance without
determining evidence, pins, fail-closed."""
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "docs" / "experiments" / "hall_icp" / "integration" / "m16_v5"
V4_DIR = ROOT / "docs" / "experiments" / "hall_icp" / "integration" / "m16_v4"
V4_REL = "docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json"
V3_REL = "docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json"
sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))
import a9_16_lib as L  # noqa: E402
import a9_later_lib as X  # noqa: E402


def _builder():
    spec = importlib.util.spec_from_file_location("m16_v5_builder", HERE / "build_subsystem_maturity_v5.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _builder()
DOC = B.build()
ROWS = DOC["rows"]
V4 = json.loads((ROOT / V4_REL).read_text(encoding="utf-8"))
_OQ5 = {}
for _r in json.loads((ROOT / B.REFERENCED["OQ5"][0]).read_text(encoding="utf-8"))["rows"]:
    _OQ5.setdefault(_r["id"], []).append(_r)
OQ5 = {k: v[0] for k, v in _OQ5.items() if len(v) == 1}


def _sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def test_outputs_are_current_and_parse():
    for path, text in B.outputs(DOC).items():
        assert path.read_text(encoding="utf-8") == text, path.name
    json.loads((HERE / "subsystem_maturity_v5.json").read_text(encoding="utf-8"))


def test_v4_and_v3_byte_identical_and_pinned():
    for rel, (sha, _) in B.PINS.items():
        assert _sha(rel) == sha, rel
    for name in ("subsystem_maturity_v4.json", "SUBSYSTEM_MATURITY_v4.md", "build_subsystem_maturity_v4.py",
                 "m16_v4_rows.py", "a9_16_m16.py", "a9_19_m16.py"):
        assert f"docs/experiments/hall_icp/integration/m16_v4/{name}" in B.PINS, name
    # v3 stays the file M16 v4 pinned
    v4b = B.B4
    assert _sha(V3_REL) == v4b.PINS[V3_REL][0]
    for p in DOC["pins"]:
        assert _sha(p["path"]) == p["sha256"], p["path"]
        assert not any(g in p["path"] for g in ("lane_registry", "trigger_registry", "fired_triggers",
                                                "trigger_ledger", "runtime_state"))
    assert DOC["supersedes_for_use"] == {"path": V4_REL, "sha256": B.PINS[V4_REL][0],
                                         "note": "v4 (and v1 / v2 / v3) stay byte-identical; v4 is pinned"}


def test_v4_builder_check_still_current():
    assert V4_DIR.joinpath("subsystem_maturity_v4.json").read_text(encoding="utf-8") == \
        B.B4.outputs()[V4_DIR / "subsystem_maturity_v4.json"]


def test_nothing_written_under_the_globbed_h2_7_folder():
    folder = ROOT / "docs" / "budgets" / "subsystem_maturity"
    assert sorted(p.name for p in folder.glob("*.json")) == ["subsystem_maturity_v1.json", "subsystem_maturity_v2.json"]
    for path in B.outputs(DOC):
        assert folder not in path.parents


def test_every_v4_row_present_in_order():
    assert [(r["row"], r["key"]) for r in ROWS] == [(r["row"], r["key"]) for r in V4["rows"]]
    for i, r in enumerate(ROWS):
        assert r["v4_ref"] == f"{V4_REL}#/rows/{i}"
        assert r["state_v4"] == V4["rows"][i]["execution_state"]


def test_every_v4_blocker_dispositioned():
    for r, r4 in zip(ROWS, V4["rows"]):
        if r4["execution_state"] == "SUPERSEDED_FOR_PRIMARY_LINE":
            assert r["blocking_item"] is None and r["remaining_blockers"] == []
            continue
        removed = {(x["v4_blocker"]["kind"], x["v4_blocker"].get("id")) for x in r["removed_blockers"]}
        remaining = {(x["kind"], x["id"]) for x in r["remaining_blockers"]}
        for c in r4["contributing_blockers"]:
            if c["kind"] == "OWNER_QUESTION":
                assert ("OWNER_QUESTION", c["id"]) in removed, (r["row"], c["id"])
            else:
                assert (c["kind"], c["id"]) in remaining, (r["row"], c["id"])
        sched_removed = any(x["v4_blocker"]["kind"] == "V4_SCHEDULER" for x in r["removed_blockers"])
        sched_kept = ("V4_SCHEDULER_CARRIED", "V4-SCHED") in remaining
        assert sched_removed != sched_kept, r["row"]
        if sched_kept:
            assert r["remaining_blockers"][0]["detail"].startswith(" ".join(r4["blocking_item"]["text"].split())[:40])


def test_removed_owner_blockers_cite_pinned_answers_a9_8_to_a9_21():
    pinned = {**{k: L.LOADED[k] for k in L.ORDER}, **{k: X.LOADED[k] for k in X.ORDER}}
    for r in ROWS:
        refs = {a["ref"]: a for a in r["answers_applied"]}
        for x in r["removed_blockers"]:
            by = x["removed_by"] if isinstance(x["removed_by"], list) else [x["removed_by"]]
            for ref in by:
                a = refs[ref]
                assert a["decision"] in pinned, ref
                d = pinned[a["decision"]]
                assert a["decision_json_sha256"] == d["json_sha256"] and a["decision_md_sha256"] == d["md_sha256"]
                assert a["pointer"].startswith(d["json"] + "#/"), ref
                if "/" not in ref:              # state v5 is the source of truth for answered / amended statuses
                    assert OQ5[ref]["status"].startswith(("ANSWERED_BY_A9_", "AMENDED_BY_A9_")), ref
                    assert a["state_v5_status"] == OQ5[ref]["status"] and a["pointer"] == OQ5[ref]["answer_pointer"]
            if x["v4_blocker"]["kind"] == "OWNER_QUESTION":
                assert x["decision_json_sha256"] == pinned[x["decision"]]["json_sha256"]


def test_remaining_blockers_categorised_and_open():
    cats = set(DOC["blocker_categories"])
    assert cats == {"OWNER_ACT", "EVIDENCE", "HARDWARE_RUN", "EXTERNAL_INPUT"}
    for r in ROWS:
        for b in r["remaining_blockers"]:
            assert b["category"] in cats and b["kind"] in DOC["blocker_kinds"], (r["row"], b["id"])
            assert "PASS" not in str(b["state"]) and b["state"] not in ("GO", "MET", "DONE")
        if r["blocking_item"]:
            ids = [b["id"] for b in r["remaining_blockers"]]
            assert r["blocking_item"]["id"] in ids
            assert r["waits_on"] in DOC["waits_on_vocabulary"]
            for a in r["answers_applied"]:
                assert a["effect"] in DOC["answer_effects"]
                for t in a["now_waits_on"]:
                    assert t in ids, (r["row"], a["ref"], t)


def test_state_vocabulary_unchanged_and_no_advance_without_evidence():
    assert DOC["state_vocabulary"] == V4["state_vocabulary"]
    assert DOC["waits_on_vocabulary"][:len(V4["waits_on_vocabulary"])] == V4["waits_on_vocabulary"]
    for r in ROWS:
        assert r["execution_state"] in DOC["state_vocabulary"]
        assert r["determining_evidence"] == []
        assert r["execution_state"] == r["state_v4"], r["row"]          # no determining evidence exists anywhere
    assert DOC["rollup"]["execution_states_v5"] == DOC["rollup"]["execution_states_v4"]
    assert B.MEASURED_REGISTRY == {}


def test_derive_state_v5_adversarial():
    meas = {"quantity_type": "measured", "kind": "HARDWARE_RECORD", "synthetic": False, "path_exists": True}
    clear = {"physical": True, "interface_frozen": False, "readiness_conditions": [], "measured_artifacts": [],
             "worked_by": None, "blocking_item": None, "contributing_open": [], "named_engineer": "someone"}
    # every blocker removed by answers that only authorise work / record a rule: v4 rule says READY, v5 refuses
    assert B.B4.derive_state(clear)[0] == "READY"
    assert B.derive_state_v5("BLOCKED", clear) == ("BLOCKED", "R-M16V5-03")
    assert B.derive_state_v5("BLOCKED", {**clear, "measured_artifacts": [dict(meas, synthetic=True)]})[0] == "BLOCKED"
    assert B.derive_state_v5("BLOCKED", {**clear, "measured_artifacts": [dict(meas, path_exists=False)]})[0] == "BLOCKED"
    assert B.derive_state_v5("BLOCKED", {**clear, "measured_artifacts": [dict(meas, quantity_type="model-derived")]}
                             )[0] == "BLOCKED"
    assert B.derive_state_v5("BLOCKED", {**clear, "measured_artifacts": [meas]})[0] == "READY"
    # never READY without a named engineer, whatever the evidence
    assert B.derive_state_v5("BLOCKED", {**clear, "named_engineer": None, "measured_artifacts": [meas]})[0] == "BLOCKED"
    # a remaining blocker keeps the row BLOCKED
    assert B.derive_state_v5("BLOCKED", {**clear, "blocking_item": {"kind": "PROGRAMME_STEP"}})[0] == "BLOCKED"


def test_registered_evidence_must_be_measured(monkeypatch):
    monkeypatch.setitem(B.MEASURED_REGISTRY, 9, [{"path": "docs/EVIDENCE.md", "quantity_type": "model-derived",
                                                  "synthetic": False}])
    with pytest.raises(B.BuildError):
        B.determining_evidence(9)
    monkeypatch.setitem(B.MEASURED_REGISTRY, 9, [{"path": "no/such/file.json", "quantity_type": "measured",
                                                  "synthetic": False}])
    with pytest.raises(B.BuildError):
        B.determining_evidence(9)


def test_named_persons_none_fabricated():
    for r in ROWS:
        assert r["owner"].get("named_engineer") is None
        if r["blocking_item"]:
            ne = [b for b in r["remaining_blockers"] if b["kind"] == "NAMED_ENGINEER"]
            assert len(ne) == 1 and ne[0]["state"] == "PENDING_EVIDENCE" and ne[0]["category"] == "OWNER_ACT"
            assert r["owner"]["named_engineer_status"].startswith("PENDING_EVIDENCE")
    m = DOC["owner_answers_applied"][0]
    assert m["question_id"] == "M16-V3-Q-01" and m["decision"] == "A9.14"
    assert m["decision_code"] == "ACCEPT_ROLE_MAP_NAMES_FROM_STAFFING_LEDGER"
    assert m["rederivation"] == "APPLIED" and m["rows_covered"] == len(V4["rows"]) == 21
    assert m["named_persons"].startswith("PENDING_EVIDENCE")


def test_gng_icp_01_and_programme_order():
    r18 = ROWS[17]
    ids = {b["id"]: b for b in r18["remaining_blockers"]}
    assert ids["GNG-ICP-01/criteria"]["category"] == "OWNER_ACT"
    assert ids["GNG-ICP-01/criteria"]["state"] == "criteria PENDING_OWNER_ACCEPTANCE"
    assert ids["GNG-ICP-01/evaluation"]["state"].startswith("NOT_EVALUATED")
    assert DOC["inputs"]["gate"]["placement"] == "BEFORE_LOCK-1"
    prog = json.loads((ROOT / B.REFERENCED["PROG"][0]).read_text(encoding="utf-8"))
    steps = {s["id"]: s for s in prog["steps"]}
    seen = set()
    for r in ROWS:
        for b in r["remaining_blockers"]:
            if b["kind"] == "PROGRAMME_STEP":
                s = steps[b["id"]]
                seen.add(b["id"])
                assert b["state"] == s["entry_status_now"]
                assert b["predecessors"] == [p["step"] for p in s["predecessors"]]
    # row 9 re-pointed to the first H-1 step (FEMM authorised is not FEMM run); row 11 to the C1 reference run
    assert ROWS[8]["blocking_item"]["id"] == "H1-S7.1" and ROWS[10]["blocking_item"]["id"] == "C1-REF"
    assert ROWS[14]["blocking_item"]["id"] == "P2-MAP"
    assert {"H1-S7.1", "C1-REF", "ICP-45N", "P2-MAP", "P3-THERMAL", "P4-ACCEPTANCE-EXPOSURE"} <= seen


def test_fail_closed(monkeypatch):
    ctx = B.Ctx()
    with pytest.raises(B.BuildError):
        B.resolve_answer(ctx, "MPV3Q-01")                       # TBD_OWNER is not an answer
    with pytest.raises(B.BuildError):
        B.resolve_answer(ctx, "A9.7/whatever")                  # not a later decision
    with pytest.raises(B.BuildError):
        B.resolve_v5(ctx, "PROGRAMME_STEP", "NO-SUCH-STEP", V4["rows"][0])
    with pytest.raises(B.BuildError):
        B.resolve_v5(ctx, "OWNER_QUESTION_V5", "OD2", V4["rows"][0])   # answered: no longer an open owner question
    with pytest.raises(B.BuildError):
        B.resolve_v5(ctx, "NOT_A_KIND", "x", V4["rows"][0])
    # a v4 owner-question blocker without a reviewed answer entry
    spec = copy.deepcopy(B.SPEC.ROWS)
    del spec[6]["answers"]["XA9Q-06"]
    monkeypatch.setattr(B.SPEC, "ROWS", spec)
    with pytest.raises(B.BuildError):
        B.build()
    # scheduler item that is not a remaining blocker
    monkeypatch.undo()
    spec = copy.deepcopy(B.SPEC.ROWS)
    spec[9]["scheduler"] = ("NOT-A-BLOCKER", "x")
    monkeypatch.setattr(B.SPEC, "ROWS", spec)
    with pytest.raises(B.BuildError):
        B.build()
    monkeypatch.undo()
    spec = copy.deepcopy(B.SPEC.ROWS)
    spec[11]["answers"]["P1Q-07"] = ("AUTHORIZES_WORK", [], "x")       # authorisation must name what it waits on
    monkeypatch.setattr(B.SPEC, "ROWS", spec)
    with pytest.raises(B.BuildError):
        B.build()
    monkeypatch.undo()
    monkeypatch.setitem(B.PINS, V4_REL, ("0" * 64, "tampered"))
    with pytest.raises(B.BuildError):
        B.Ctx()
