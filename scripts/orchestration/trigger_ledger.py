"""Transactional, idempotent trigger lifecycle (owner rule 2026-09-26):  READY -> CLAIMED -> LAUNCHED -> VERIFIED | FAILED.

* Execution key (deterministic): sha256 of {trigger, member, dependency-state hash, config hash}; the dependency-state hash
  covers every prerequisite's id, terminal state and identity (lane build commit / dataset scores or structural-check sha256);
  the config hash covers the pre-registration lock and the trigger registry.
* CLAIMED is persisted BEFORE any launch, by exclusive creation of docs/orchestration/claims/<key>.<attempt>.claim
  (O_CREAT | O_EXCL: two claimants can never both succeed) and an event appended to the ledger. A trigger with a live claim
  (CLAIMED or LAUNCHED or VERIFIED) is never READY again, so a crash after launch cannot cause a second launch.
* LAUNCHED requires launch evidence that the tracker can check (a workflow run whose journal exists, or a runner log 'start'
  line / structural-check file); a claim that never reaches LAUNCHED, or LAUNCHED without checkable evidence, is reported
  (STALE_CLAIM / LAUNCH_UNCONFIRMED), never silently relaunched. Recovery: record LAUNCHED (recovered, with evidence) if the
  launch did happen, else FAILED(launch_not_acknowledged) and claim attempt n+1.
* VERIFIED / FAILED are completion events with the evidence that established them.
* The ledger (docs/orchestration/trigger_ledger_v2.jsonl) is append-only; every event carries record_origin (live |
  retroactive_reconstruction) and, for reconstructions, the reconstruction time and the evidence used.
"""
import datetime, hashlib, json, os


def raise_(e):
    raise e

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
ORCH = os.path.join(ROOT, "docs", "orchestration")
EVENTS = ("CLAIMED", "LAUNCHED", "VERIFIED", "FAILED")
now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
canon = lambda o: json.dumps(o, sort_keys=True, separators=(",", ":")).encode()


def ledger_path():
    return os.path.join(ORCH, "trigger_ledger_v2.jsonl")


def execution_key(trigger, member, prerequisites, config):
    """prerequisites: {id: {"state": ..., "identity": commit|sha256}}; config: {"prereg_lock_sha256": ..., "trigger_registry_sha256": ...}"""
    dep_hash = hashlib.sha256(canon(prerequisites)).hexdigest()
    cfg_hash = hashlib.sha256(canon(config)).hexdigest()
    key = hashlib.sha256(canon({"trigger": trigger, "member": member, "deps": dep_hash, "config": cfg_hash})).hexdigest()
    return key, dep_hash, cfg_hash


def events():
    p = ledger_path()
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.isfile(p) else []


def _append(ev):
    line = (json.dumps(ev, sort_keys=True) + "\n").encode()
    fd = os.open(ledger_path(), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line); os.fsync(fd)
    finally:
        os.close(fd)


def lifecycle():
    """{(trigger, member): {"key", "attempt", "state", "events": [...]}} for the latest attempt of each trigger/member."""
    out = {}
    for ev in events():
        k = (ev["trigger"], ev.get("member"))
        cur = out.get(k)
        if ev["event"] == "CLAIMED" and (cur is None or ev["attempt"] > cur["attempt"]):
            out[k] = {"key": ev["execution_key"], "attempt": ev["attempt"], "state": "CLAIMED", "events": [ev]}
        elif cur is not None and ev.get("execution_key") == cur["key"] and ev.get("attempt") == cur["attempt"]:
            cur["events"].append(ev)
            cur["state"] = ev["event"]
    return out


def claim(trigger, member, prerequisites, config, record_origin="live", reconstruction=None):
    """Persist CLAIMED before launching. Raises if the trigger/member already has a live claim (CLAIMED, LAUNCHED, VERIFIED)."""
    lc = lifecycle().get((trigger, member))
    if lc and lc["state"] != "FAILED":
        raise RuntimeError(f"{trigger}:{member} already {lc['state']} (key {lc['key'][:12]}, attempt {lc['attempt']})")
    attempt = (lc["attempt"] + 1) if lc else 1
    key, dep_hash, cfg_hash = execution_key(trigger, member, prerequisites, config)
    os.makedirs(os.path.join(ORCH, "claims"), exist_ok=True)
    fd = os.open(os.path.join(ORCH, "claims", f"{key}.{attempt}.claim"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        os.write(fd, canon({"trigger": trigger, "member": member, "attempt": attempt, "claimed_utc": now()})); os.fsync(fd)
    finally:
        os.close(fd)
    ev = {"event": "CLAIMED", "trigger": trigger, "member": member, "attempt": attempt, "execution_key": key,
          "dependency_state_hash": dep_hash, "config_hash": cfg_hash, "prerequisites": prerequisites, "config": config,
          "utc": now(), "record_origin": record_origin}
    if reconstruction:
        ev["reconstruction"] = reconstruction
    _append(ev)
    return key, attempt


def record(event, trigger, member, key, attempt, evidence, record_origin="live", reconstruction=None, **extra):
    if event not in EVENTS[1:]:
        raise ValueError(event)
    lc = lifecycle().get((trigger, member))
    if not lc or lc["key"] != key or lc["attempt"] != attempt:
        raise RuntimeError(f"{trigger}:{member}: no matching claim (key {key[:12]}, attempt {attempt})")
    allowed = {"CLAIMED": ("LAUNCHED", "FAILED"), "LAUNCHED": ("VERIFIED", "FAILED")}
    if event not in allowed.get(lc["state"], ()):
        raise RuntimeError(f"{trigger}:{member}: illegal transition {lc['state']} -> {event}")
    if not evidence:
        raise ValueError("every transition needs evidence")
    ev = {"event": event, "trigger": trigger, "member": member, "attempt": attempt, "execution_key": key, "evidence": evidence,
          "utc": now(), "record_origin": record_origin, **extra}
    if reconstruction:
        ev["reconstruction"] = reconstruction
    _append(ev)


def launch_evidence_ok(evidence, journals_dir):
    """Checkable launch evidence: {'workflow_run': id} with an existing journal, or {'runner_log': path, 'start_line': text}
    present in that log, or {'artifact': path} that exists."""
    if not isinstance(evidence, dict):
        return False
    if evidence.get("workflow_run"):
        return os.path.isfile(os.path.join(journals_dir, evidence["workflow_run"], "journal.jsonl"))
    if evidence.get("runner_log"):
        p = evidence["runner_log"]
        return os.path.isfile(p) and evidence.get("start_line", "") in open(p).read()
    if evidence.get("artifact"):
        return os.path.exists(os.path.join(ROOT, evidence["artifact"]))
    return False


def snapshot(trigger, member, st):
    """Prerequisite snapshot {id: {state, identity}} from a lane_status.status() result, for the execution key."""
    reg = json.load(open(os.path.join(ORCH, "trigger_registry_v1.json")))
    T = next(t for t in reg["triggers"] if t["id"] == trigger)
    ids = [member] if "family" in T else [p["id"] for p in T["prerequisites"]]
    snap = {}
    for i in ids:
        ident = (st["lane_build"].get(i) or {}).get("commit") if i in st.get("lane_build", {}) else None
        if i.startswith("ds_"):
            ident = st.get("dataset_identity", {}).get(i)
        snap[i] = {"state": st["state"].get(i), "identity": ident}
    lock = os.path.join(ROOT, "hallthruster_bridge", "prereg", "p5_n2_prereg_lock_v1.json")
    cfg = {"prereg_lock_sha256": hashlib.sha256(open(lock, "rb").read()).hexdigest(),
           "trigger_registry_sha256": hashlib.sha256(open(os.path.join(ORCH, "trigger_registry_v1.json"), "rb").read()).hexdigest()}
    return snap, cfg


if __name__ == "__main__":
    import argparse, importlib.util, sys
    ap = argparse.ArgumentParser(description="claim | launched | verified | failed | show")
    ap.add_argument("cmd"); ap.add_argument("trigger", nargs="?"); ap.add_argument("member", nargs="?")
    ap.add_argument("--evidence", default=None, help="JSON object"); ap.add_argument("--journals", default=None)
    a = ap.parse_args()
    spec = importlib.util.spec_from_file_location("ls", os.path.join(os.path.dirname(os.path.abspath(__file__)), "lane_status.py"))
    ls = importlib.util.module_from_spec(spec); spec.loader.exec_module(ls)
    jd = a.journals or ls.DEFAULT_JOURNALS
    if a.cmd == "show":
        print(json.dumps({f"{t}:{m}" if m else t: {k: v for k, v in x.items() if k != "events"} for (t, m), x in lifecycle().items()}, indent=1))
        sys.exit(0)
    st = ls.status(jd, ls.DEFAULT_FOLLOWON)
    name = f"{a.trigger}:{a.member}" if a.member else a.trigger
    if a.cmd == "claim":
        if name not in st["ready"]:
            raise SystemExit(f"{name} is not READY: refusing to claim")
        snap, cfg = snapshot(a.trigger, a.member, st)
        print(json.dumps(dict(zip(("execution_key", "attempt"), claim(a.trigger, a.member, snap, cfg)))))
    else:
        lc = lifecycle().get((a.trigger, a.member)) or raise_(SystemExit(f"no claim for {name}"))
        ev = json.loads(a.evidence) if a.evidence else None
        if a.cmd == "launched" and not launch_evidence_ok(ev, jd):
            raise SystemExit("launch evidence not checkable (workflow journal / runner log line / artifact): refusing LAUNCHED")
        record(a.cmd.upper(), a.trigger, a.member, lc["key"], lc["attempt"], ev)
        print(json.dumps({"recorded": a.cmd.upper(), "execution_key": lc["key"], "attempt": lc["attempt"]}))
