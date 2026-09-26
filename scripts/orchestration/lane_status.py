"""Machine-readable orchestration state (owner operating rules 2026-09-26). Read-only: derives every lane, dataset and
follow-on state from (a) the workflow journals (session-local, --journals), (b) campaign runner outputs (--followon) and the
frozen/scored datasets in hallthruster_bridge/validation/, and (c) the append-only fired-trigger ledger
docs/orchestration/trigger_ledger_v2.jsonl (transactional lifecycle, scripts/orchestration/trigger_ledger.py). Reports which
registered triggers are READY (all prerequisites in their terminal
state) and not yet fired. Nothing here launches work: actions are taken by the operator and recorded in the ledger.

Terminal states (docs/orchestration/lane_registry_v1.json): a workflow lane / follow-on is `verified` only if its final
verification round passed under its protocol AND every registered dep is verified; `verified_provisional`, `done_open_issues`
and anything in progress never satisfy a trigger. A dataset is `structural_pass` / `frozen` / `scored`.
Usage: python scripts/orchestration/lane_status.py [--journals DIR] [--followon DIR] [--json]
"""
import argparse, ast, glob, json, os, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
ORCH = os.path.join(ROOT, "docs", "orchestration")
VAL = os.path.join(ROOT, "hallthruster_bridge", "validation")


def _obj(x):
    if isinstance(x, dict):
        return x
    for f in (json.loads, ast.literal_eval):
        try:
            return f(x)
        except Exception:
            pass
    return {}


def journal_lanes(journals_dir):
    """{(workflow_run, key): {"build": result|None, "verify": {round: {lens: verdict|'running'}}, "fix_started": set, "old": {...}}}"""
    out = {}
    for d in glob.glob(os.path.join(journals_dir, "*", "")):
        wf, path = os.path.basename(d.rstrip("/")), os.path.join(d, "journal.jsonl")
        if not os.path.isfile(path):
            continue
        lab, res, failed = {}, {}, set()
        for line in open(path):
            j = json.loads(line)
            if j["type"] == "started":
                lab[j["key"]] = j.get("label", "")
                failed.discard(j["key"])
            elif j["type"] == "result":
                res[j["key"]] = j.get("result")
                failed.discard(j["key"])
            elif j["type"] == "failed":                     # an agent that errored (e.g. usage limit) is not in progress;
                failed.add(j["key"])                        # if the run is resumed and it re-runs, a later result supersedes
        for k, label in lab.items():
            if k in failed and k not in res:
                continue
            got = _obj(res[k]) if k in res else None
            m = re.match(r"^(build|verify(\d+)|fix(\d+)):([A-Za-z0-9_]+)(?::(evidence|rules))?$", label)
            m_old = re.match(r"^(verify|fix|reverify):([A-Za-z0-9_]+)$", label)   # first lanes script (single lens)
            if m_old:
                L = out.setdefault((wf, m_old.group(2)), {"build": None, "verify": {}, "fix_started": set(), "old": {}})
                L["old"][m_old.group(1)] = got if k in res else "running"
            elif m:
                L = out.setdefault((wf, m.group(4)), {"build": None, "verify": {}, "fix_started": set(), "old": {}})
                if m.group(1) == "build":
                    L["build"] = got
                elif m.group(2):
                    L["verify"].setdefault(int(m.group(2)), {})[m.group(5)] = got if k in res else "running"
                elif m.group(3):
                    L["fix_started"].add(int(m.group(3)))
    return out


def lane_state(L):
    if L is None:
        return "not_started"
    if L["build"] is None:
        return "building"
    if L["old"]:
        v, fx, rv = L["old"].get("verify"), L["old"].get("fix"), L["old"].get("reverify")
        if isinstance(v, dict) and v.get("pass"):
            return "verified_self"
        if isinstance(rv, dict):
            return "verified_self" if rv.get("pass") else "done_open_issues"
        return "fixing" if fx is not None else "verifying"
    if not L["verify"]:
        return "verifying"
    r = max(L["verify"])
    v = L["verify"][r]
    if not all(isinstance(v.get(x), dict) for x in ("evidence", "rules")):
        return "verifying"
    if all(v[x].get("pass") for x in ("evidence", "rules")):
        return "verified_self"
    if r >= 3:
        return "done_open_issues"
    return f"fixing{r}" if r in L["fix_started"] else f"verified{r}_fail"


def dataset_state(manifest, followon_dir):
    stem = os.path.join(VAL, f"p5_n2_campaign_v1_{manifest}")
    if manifest == "facility_mandatory":
        stem = os.path.join(VAL, "p5_n2_campaign_v1_facility")
    prov = stem + "_scores_provenance.json"
    if os.path.isfile(prov):
        p = json.load(open(prov))
        return "scored", (p.get("o4_trigger_fired") or {})
    if os.path.isfile(stem + "_raw_manifest.json"):
        return "frozen", {}
    sc = os.path.join(followon_dir, manifest, "structural_check.json")
    if os.path.isfile(sc):
        try:
            return ("structural_pass" if json.load(open(sc)).get("PASS") else "structural_fail"), {}
        except ValueError:
            return "structural_fail", {}
    return ("running" if os.path.isdir(os.path.join(followon_dir, manifest)) else "not_started"), {}


DEFAULT_JOURNALS = "/root/.claude/projects/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/subagents/workflows"
DEFAULT_FOLLOWON = "/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad/followon"
STALE_CLAIM_S = 900


def _ledger_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tl", os.path.join(os.path.dirname(os.path.abspath(__file__)), "trigger_ledger.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.ORCH = ORCH                                                   # same orchestration directory as this tracker
    return m


def dataset_identity(manifest, followon_dir, state):
    """sha256 of the file that establishes the dataset's state (scores provenance when scored, else the structural check)."""
    import hashlib
    stem = os.path.join(VAL, "p5_n2_campaign_v1_facility" if manifest == "facility_mandatory" else f"p5_n2_campaign_v1_{manifest}")
    p = {"scored": stem + "_scores_provenance.json", "frozen": stem + "_raw_manifest.json"}.get(
        state, os.path.join(followon_dir, manifest, "structural_check.json"))
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.isfile(p) else None


def status(journals_dir, followon_dir):
    reg = json.load(open(os.path.join(ORCH, "lane_registry_v1.json")))
    trig = json.load(open(os.path.join(ORCH, "trigger_registry_v1.json")))
    jl, tl = journal_lanes(journals_dir), _ledger_module()
    lc = tl.lifecycle()
    fired = {t + (":" + m if m else "") for (t, m), x in lc.items() if x["state"] != "FAILED"}   # live claim => never READY again
    produces = {T["id"]: T.get("produces") for T in trig["triggers"]}
    launched = {}
    for (t, m), x in lc.items():
        for ev in x["events"]:
            if ev["event"] == "LAUNCHED" and isinstance(ev.get("evidence"), dict) and ev["evidence"].get("workflow_key") and produces.get(t):
                launched[produces[t]] = ev["evidence"]
    alerts = []
    import datetime as _dt
    for (t, m), x in lc.items():
        name = t + (":" + m if m else "")
        age = (_dt.datetime.now(_dt.timezone.utc) - _dt.datetime.fromisoformat(x["events"][-1]["utc"])).total_seconds()
        if x["state"] == "CLAIMED" and age > STALE_CLAIM_S:
            alerts.append(f"STALE_CLAIM {name} attempt {x['attempt']} (claimed {int(age)} s ago, no LAUNCHED)")
        if x["state"] == "LAUNCHED" and not tl.launch_evidence_ok(x["events"][-1].get("evidence"), journals_dir):
            alerts.append(f"LAUNCH_UNCONFIRMED {name} attempt {x['attempt']}")
    st, info = {}, {}
    for L in reg["lanes"]:
        src = (L["workflow_run"], L["workflow_key"])
        if L.get("repairs"):                                        # operator repair of done_open_issues: latest repair run rules
            src = (L["repairs"][-1]["workflow_run"], L["repairs"][-1]["workflow_key"])
        st[L["id"]] = lane_state(jl.get(src))
        b = (jl.get(src) or {}).get("build") or {}
        info[L["id"]] = {k: b.get(k) for k in ("worktree_path", "branch", "commit")}
    for F in reg["follow_ons"]:
        a = launched.get(F["id"])
        st[F["id"]] = lane_state(jl.get((a["workflow_run"], a["workflow_key"]))) if a else "not_started"
        b = (jl.get((a["workflow_run"], a["workflow_key"])) or {}).get("build") or {} if a else {}
        info[F["id"]] = {k: b.get(k) for k in ("worktree_path", "branch", "commit")}
    ds_fired, ds_ident = {}, {}
    for D in reg["datasets"]:
        st[D["id"]], ds_fired[D["id"]] = dataset_state(D["manifest"], followon_dir)
        ds_ident[D["id"]] = dataset_identity(D["manifest"], followon_dir, st[D["id"]])
    try:
        import sys; sys.path.insert(0, ROOT)
        from abep_sim.hall_ensemble import load_ensemble
        st["ensemble_admitted_members"] = "non_empty" if load_ensemble()["members"] else "empty"
    except Exception as e:                                          # an invalid ensemble is reported, never treated as admitted
        st["ensemble_admitted_members"] = f"error: {e}"
    for O in reg.get("owner_dispositions", []):                   # owner decisions are prerequisites too (never inferred)
        f = os.path.join(ROOT, O["file"])
        if not os.path.isfile(f):
            st[O["id"]] = "pending"
        else:
            dec = json.load(open(f)).get("decision")
            st[O["id"]] = "domain_path_closed" if dec == "A-NO" else "domain_path_open" if dec in ("A-PARTIAL", "A-YES-WITH-CONDITIONS") else f"error: unknown decision {dec!r}"
    if st.get("od_v2_question_a") == "domain_path_closed" and st.get("fo_v2_excitation_question_b") == "not_started":
        st["fo_v2_excitation_question_b"] = "BLOCKED_BY_QUESTION_A_DISPOSITION"
    deps = {L["id"]: L.get("deps", []) for L in reg["lanes"]}

    def final(i):                                                   # verified only with verified deps
        s = st.get(i, "unknown")
        if s == "verified_self":
            return "verified" if all(final(d) == "verified" for d in deps.get(i, [])) else "verified_provisional"
        return s
    state = {i: final(i) for i in st}
    ready = []
    for T in trig["triggers"]:
        if "family" in T:                                           # per-dataset mechanical triggers
            for m in T["family"]:
                key = f"{T['id']}:{m}"
                if key in fired:
                    continue
                s, tf = state.get(m), ds_fired.get(m, {})
                if T["id"] == "T_O4_SCORE" and s == "structural_pass":
                    ready.append(key)
                if T["id"] == "T_O4_ESCALATE" and s == "scored" and any(tf.values()):
                    ready.append(key)
            continue
        if T["id"] in fired:
            continue
        ok = all(state.get(p["id"]) == p["state"] for p in T["prerequisites"])
        if ok and T["id"] == "T_O4_DISPOSITION_MATRIX":
            for D in reg["datasets"]:
                if D.get("escalations") and any(ds_fired.get(D["id"], {}).values()):
                    ok = ok and all(state.get(e) == "scored" for e in D["escalations"])
        if ok:
            ready.append(T["id"])
    return {"ready": ready, "state": state, "lane_build": info, "dataset_identity": ds_ident, "alerts": alerts,
            "lifecycle": {t + (":" + m if m else ""): x["state"] for (t, m), x in lc.items()}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--journals", default=DEFAULT_JOURNALS)
    ap.add_argument("--followon", default=DEFAULT_FOLLOWON)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    s = status(a.journals, a.followon)
    print(json.dumps(s if a.json else {"ready": s["ready"], "state": s["state"], "alerts": s["alerts"], "lifecycle": s["lifecycle"]}, sort_keys=True))
