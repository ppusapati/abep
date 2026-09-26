"""Orchestration registries (owner operating rules 2026-09-26): machine-addressable ids, registered triggers only, `verified`
terminal state (both lenses, verified deps), Bundle 1 with lane 24 as a hard prerequisite, O4 triggers registered."""
import importlib.util, json, os
import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
ORCH = os.path.join(ROOT, "docs", "orchestration")


def _load():
    spec = importlib.util.spec_from_file_location("ls", os.path.join(ROOT, "scripts", "orchestration", "lane_status.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_registries_are_closed_and_machine_addressable():
    reg = json.load(open(os.path.join(ORCH, "lane_registry_v1.json")))
    trig = json.load(open(os.path.join(ORCH, "trigger_registry_v1.json")))
    ids = [x["id"] for x in reg["lanes"] + reg["datasets"] + reg["follow_ons"]]
    assert len(ids) == len(set(ids))
    known = set(ids) | {"ensemble_admitted_members"}
    for L in reg["lanes"]:
        assert set(L["deps"]) <= known
    produced = []
    for T in trig["triggers"]:
        for p in T.get("prerequisites", []):
            assert p["id"] in known, (T["id"], p["id"])
            assert p["state"] in ("verified", "scored", "structural_pass", "non_empty")
        assert set(T.get("family", [])) <= known
        if T.get("produces"):
            assert T["produces"] in known
            produced.append(T["produces"])
    assert sorted(produced) == sorted(set(produced))                       # each follow-on produced by exactly one trigger
    assert {f["id"] for f in reg["follow_ons"]} <= set(produced)
    t = {T["id"]: T for T in trig["triggers"]}
    b1 = {p["id"]: p["state"] for p in t["T_BUNDLE1"]["prerequisites"]}
    assert b1["lane_24_hard_gates"] == "verified" and b1["lane_28_break_even"] == "verified"
    assert set(b1.values()) == {"verified"} and len(b1) == 12
    o4 = {p["id"] for p in t["T_O4_DISPOSITION_MATRIX"]["prerequisites"]}
    assert o4 == {d["id"] for d in reg["datasets"] if d["role"] == "O4 first stage"} and len(o4) == 5
    for k in ("T_O4_SCORE", "T_O4_ESCALATE", "T_JOHNSONLOW_ESCALATION_ASSESSMENT", "T_V2_QUESTION_A", "T_V2_QUESTION_B", "T_FACILITY_SCORE"):
        assert k in t


def _journal(d, wf, rows):
    p = d / wf; p.mkdir(parents=True, exist_ok=True)
    lines = [{"type": "launched"}]
    for i, (label, result) in enumerate(rows):
        lines.append({"type": "started", "key": f"k{i}", "label": label})
        if result is not None:
            lines.append({"type": "result", "key": f"k{i}", "result": result})
    (p / "journal.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))


def test_tracker_terminal_states(tmp_path, monkeypatch):
    m = _load()
    orch = tmp_path / "orch"; orch.mkdir()
    B = {"worktree_path": "/w", "branch": "b", "commit": "c"}
    P, F = {"pass": True, "issues": []}, {"pass": False, "issues": [{"severity": "major", "description": "x"}]}
    reg = {"lanes": [{"id": "lane_a", "workflow_run": "wf1", "workflow_key": "A", "deps": []},
                     {"id": "lane_b", "workflow_run": "wf1", "workflow_key": "B", "deps": []},
                     {"id": "lane_c", "workflow_run": "wf1", "workflow_key": "C", "deps": ["lane_b"]},
                     {"id": "lane_d", "workflow_run": "wf1", "workflow_key": "D", "deps": []},
                     {"id": "lane_e", "workflow_run": "wf1", "workflow_key": "E", "deps": []}],
           "datasets": [{"id": "ds_x", "manifest": "staged_x", "role": "O4 first stage", "escalations": []}], "follow_ons": []}
    trig = {"triggers": [{"id": "T_AC", "prerequisites": [{"id": "lane_a", "state": "verified"}, {"id": "lane_c", "state": "verified"}]},
                         {"id": "T_A", "prerequisites": [{"id": "lane_a", "state": "verified"}]},
                         {"id": "T_O4_SCORE", "family": ["ds_x"]}]}
    (orch / "lane_registry_v1.json").write_text(json.dumps(reg)); (orch / "trigger_registry_v1.json").write_text(json.dumps(trig))
    _journal(tmp_path / "j", "wf1", [
        ("build:A", B), ("verify1:A:evidence", P), ("verify1:A:rules", P),                       # verified in round 1
        ("build:B", B), ("verify1:B:evidence", F), ("verify1:B:rules", P), ("fix1:B", B),
        ("verify2:B:evidence", F), ("verify2:B:rules", P), ("fix2:B", B), ("verify3:B:evidence", F), ("verify3:B:rules", P),
        ("build:C", B), ("verify1:C:evidence", P), ("verify1:C:rules", P),                       # passes, but dep B is not verified
        ("build:D", B), ("verify1:D:evidence", P), ("verify1:D:rules", None),                    # one lens still running
        ("build:E", None)])
    fo = tmp_path / "fo"; (fo / "staged_x").mkdir(parents=True)
    (fo / "staged_x" / "structural_check.json").write_text(json.dumps({"PASS": True}))
    monkeypatch.setattr(m, "ORCH", str(orch)); monkeypatch.setattr(m, "VAL", str(tmp_path / "val"))
    s = m.status(str(tmp_path / "j"), str(fo))
    st = s["state"]
    assert st["lane_a"] == "verified" and st["lane_b"] == "done_open_issues" and st["lane_c"] == "verified_provisional"
    assert st["lane_d"] == "verifying" and st["lane_e"] == "building" and st["ds_x"] == "structural_pass"
    assert s["ready"] == ["T_A", "T_O4_SCORE:ds_x"]                                            # T_AC blocked by the provisional lane
    (orch / "fired_triggers.jsonl").write_text(json.dumps({"trigger": "T_A"}) + "\n" + json.dumps({"trigger": "T_O4_SCORE", "member": "ds_x"}) + "\n")
    assert m.status(str(tmp_path / "j"), str(fo))["ready"] == []                              # fires once


def test_operating_model_rules_recorded():
    txt = open(os.path.join(ORCH, "OPERATING_MODEL.md")).read()
    for s in ("CONDITIONAL_BASELINE", "NO_BASELINE_YET", "ELIMINATED_WITHIN_TESTED_ENVELOPE", "admissible only", "Question A",
              "Question B", "hard prerequisite", "feed-state pressure"):
        assert s in txt
    rt = json.load(open(os.path.join(ORCH, "runtime_state.json")))
    assert rt["mechanism"]["daemon"]["pid"] and rt["restart_semantics"] and rt["incident"]
