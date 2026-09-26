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
    known = set(ids) | {"ensemble_admitted_members"} | {o["id"] for o in reg.get("owner_dispositions", [])}
    for L in reg["lanes"]:
        assert set(L["deps"]) <= known
    produced = []
    for T in trig["triggers"]:
        for p in T.get("prerequisites", []):
            assert p["id"] in known, (T["id"], p["id"])
            assert p["state"] in ("verified", "scored", "structural_pass", "non_empty", "domain_path_open", "domain_path_closed")
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
                     {"id": "lane_e", "workflow_run": "wf1", "workflow_key": "E", "deps": []},
                     {"id": "lane_g", "workflow_run": "wf1", "workflow_key": "G", "deps": []}],
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
        ("build:E", None), ("build:G", B), ("verify1:G:evidence", P), ("verify1:G:rules", P),
        ("verify2:G:evidence", None), ("verify2:G:rules", None)])                                  # stale attempts, failed below
    jf = tmp_path / "j" / "wf1" / "journal.jsonl"
    rows = [json.loads(l) for l in jf.read_text().splitlines()]
    stale = [r["key"] for r in rows if r.get("label", "").startswith("verify2:G")]
    jf.write_text(jf.read_text() + "".join(json.dumps({"type": "failed", "key": k}) + "\n" for k in stale))
    fo = tmp_path / "fo"; (fo / "staged_x").mkdir(parents=True)
    (fo / "staged_x" / "structural_check.json").write_text(json.dumps({"PASS": True}))
    monkeypatch.setattr(m, "ORCH", str(orch)); monkeypatch.setattr(m, "VAL", str(tmp_path / "val"))
    s = m.status(str(tmp_path / "j"), str(fo))
    st = s["state"]
    assert st["lane_a"] == "verified" and st["lane_b"] == "done_open_issues" and st["lane_c"] == "verified_provisional"
    assert st["lane_d"] == "verifying" and st["lane_e"] == "building" and st["ds_x"] == "structural_pass"
    assert st["lane_g"] == "verified"                                                          # failed stale attempts ignored
    assert s["ready"] == ["T_A", "T_O4_SCORE:ds_x"]                                            # T_AC blocked by the provisional lane
    tl = m._ledger_module()                                                                      # claims live in the v2 ledger
    tl.claim("T_A", None, {}, {}); tl.claim("T_O4_SCORE", "ds_x", {}, {})
    assert m.status(str(tmp_path / "j"), str(fo))["ready"] == []                              # a live claim is never READY again


def test_operating_model_rules_recorded():
    txt = open(os.path.join(ORCH, "OPERATING_MODEL.md")).read()
    for s in ("CONDITIONAL_BASELINE", "NO_BASELINE_YET", "ELIMINATED_WITHIN_TESTED_ENVELOPE", "admissible only", "Question A",
              "Question B", "hard prerequisite", "feed-state pressure"):
        assert s in txt
    rt = json.load(open(os.path.join(ORCH, "runtime_state.json")))
    assert rt["mechanism"]["daemon"]["pid"] and rt["restart_semantics"] and rt["incidents"] and "STALE_CLAIM" in txt


def _ledger(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("tl", os.path.join(ROOT, "scripts", "orchestration", "trigger_ledger.py"))
    tl = importlib.util.module_from_spec(spec); spec.loader.exec_module(tl)
    monkeypatch.setattr(tl, "ORCH", str(tmp_path))
    return tl


def test_trigger_lifecycle_is_transactional_and_idempotent(tmp_path, monkeypatch):
    """READY -> CLAIMED -> LAUNCHED -> VERIFIED | FAILED (owner rule): the claim is persisted before launch with an exclusive
    create, a live claim can never be re-claimed (no double launch after a crash), transitions follow the allow-list, every
    transition needs evidence, FAILED allows a new attempt, and the execution key is deterministic in its inputs."""
    tl = _ledger(tmp_path, monkeypatch)
    pre, cfg = {"lane_x": {"state": "verified", "identity": "c1"}}, {"prereg_lock_sha256": "a", "trigger_registry_sha256": "b"}
    assert tl.execution_key("T", None, pre, cfg) == tl.execution_key("T", None, dict(pre), dict(cfg))
    assert tl.execution_key("T", None, {"lane_x": {"state": "verified", "identity": "c2"}}, cfg)[0] != tl.execution_key("T", None, pre, cfg)[0]
    k, a = tl.claim("T", None, pre, cfg)
    assert a == 1 and os.path.isfile(tmp_path / "claims" / f"{k}.1.claim")
    with pytest.raises(RuntimeError):                                  # crash after launch + re-derived READY: no second claim
        tl.claim("T", None, pre, cfg)
    with pytest.raises(OSError):                                       # the claim file itself is exclusive
        os.close(os.open(str(tmp_path / "claims" / f"{k}.1.claim"), os.O_WRONLY | os.O_CREAT | os.O_EXCL))
    with pytest.raises(RuntimeError):
        tl.record("VERIFIED", "T", None, k, a, {"artifact": "x"})    # VERIFIED before LAUNCHED is illegal
    with pytest.raises(ValueError):
        tl.record("LAUNCHED", "T", None, k, a, None)                   # no evidence, no transition
    tl.record("LAUNCHED", "T", None, k, a, {"workflow_run": "wf1", "workflow_key": "X"})
    tl.record("FAILED", "T", None, k, a, {"reason": "verification failed"})
    with pytest.raises(RuntimeError):
        tl.record("VERIFIED", "T", None, k, a, {"artifact": "x"})    # nothing leaves a completed state
    k2, a2 = tl.claim("T", None, pre, cfg)                              # FAILED allows a new attempt, same deterministic key
    assert a2 == 2 and k2 == k and tl.lifecycle()[("T", None)]["state"] == "CLAIMED"
    ev = [json.loads(l) for l in open(tmp_path / "trigger_ledger_v2.jsonl")]
    assert [e["event"] for e in ev] == ["CLAIMED", "LAUNCHED", "FAILED", "CLAIMED"] and all(e["record_origin"] == "live" for e in ev)
    (tmp_path / "wf1").mkdir(); (tmp_path / "wf1" / "journal.jsonl").write_text("")
    assert tl.launch_evidence_ok({"workflow_run": "wf1"}, str(tmp_path)) and not tl.launch_evidence_ok({"workflow_run": "wf9"}, str(tmp_path))
    log = tmp_path / "p.log"; log.write_text("12:00 start job_a\n")
    assert tl.launch_evidence_ok({"runner_log": str(log), "start_line": "start job_a"}, str(tmp_path))
    assert not tl.launch_evidence_ok({"runner_log": str(log), "start_line": "start job_b"}, str(tmp_path))


def test_retroactive_ledger_entries_are_marked():
    """The two firings that predate the transactional ledger are reconstructions, never indistinguishable from live events."""
    ev = [json.loads(l) for l in open(os.path.join(ORCH, "trigger_ledger_v2.jsonl"))]
    old = [e for e in ev if e["trigger"] in ("T_O4_SCORE", "T_O4_ESCALATE") and e.get("member") == "ds_staged_n2_n_exc_johnsonlow"]
    assert old and all(e["record_origin"] == "retroactive_reconstruction" for e in old)
    for e in old:
        r = e["reconstruction"]
        assert r["reconstructed_utc"] and r["original_event_utc"] and r["evidence"]


def test_stale_claim_and_unconfirmed_launch_alerts(tmp_path, monkeypatch):
    m = _load()
    orch = tmp_path / "orch"; orch.mkdir()
    (orch / "lane_registry_v1.json").write_text(json.dumps({"lanes": [], "datasets": [], "follow_ons": []}))
    (orch / "trigger_registry_v1.json").write_text(json.dumps({"triggers": [{"id": "T1", "prerequisites": []}, {"id": "T2", "prerequisites": []}]}))
    monkeypatch.setattr(m, "ORCH", str(orch)); monkeypatch.setattr(m, "VAL", str(tmp_path / "val")); monkeypatch.setattr(m, "STALE_CLAIM_S", -1)
    tl = m._ledger_module()
    k1, a1 = tl.claim("T1", None, {}, {})                                # claimed, never launched -> STALE_CLAIM
    k2, a2 = tl.claim("T2", None, {}, {})
    tl.record("LAUNCHED", "T2", None, k2, a2, {"workflow_run": "missing_wf", "workflow_key": "K"})   # unverifiable launch
    (tmp_path / "j").mkdir()
    s = m.status(str(tmp_path / "j"), str(tmp_path / "fo"))
    assert s["ready"] == []                                             # both claimed: neither is READY again
    assert any(a.startswith("STALE_CLAIM T1") for a in s["alerts"]) and any(a.startswith("LAUNCH_UNCONFIRMED T2") for a in s["alerts"])


def test_question_b_blocked_by_owner_disposition():
    """Owner decision 2026-09-26 (A-NO): T_V2_QUESTION_B needs the Question-A disposition to leave the domain path open, so it
    can never be READY under A-NO, whatever else is verified; the bounded D-X5 evidence trigger follows the closed path."""
    trig = {T["id"]: T for T in json.load(open(os.path.join(ORCH, "trigger_registry_v1.json")))["triggers"]}
    assert {"id": "od_v2_question_a", "state": "domain_path_open"} in trig["T_V2_QUESTION_B"]["prerequisites"]
    assert {"id": "od_v2_question_a", "state": "domain_path_closed"} in trig["T_DX5_EVIDENCE"]["prerequisites"]
    d = json.load(open(os.path.join(ROOT, "docs", "v2", "question_a", "QUESTION_A_DISPOSITION.json")))
    assert d["decision"] == "A-NO" and d["sub_decisions"]["D-X1_open_v2_now"] == "NO"
    m = _load()
    st = m.status(os.path.join(ROOT, "no_such_journals"), os.path.join(ROOT, "no_such_followon"))
    assert st["state"]["od_v2_question_a"] == "domain_path_closed"
    assert st["state"]["fo_v2_excitation_question_b"] == "BLOCKED_BY_QUESTION_A_DISPOSITION"
    assert "T_V2_QUESTION_B" not in st["ready"]
