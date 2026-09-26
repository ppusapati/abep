"""Machine-readable orchestration state (owner operating rules 2026-09-26). Read-only: derives every lane, dataset and
follow-on state from (a) the workflow journals (session-local, --journals), (b) campaign runner outputs (--followon) and the
frozen/scored datasets in hallthruster_bridge/validation/, and (c) the append-only fired-trigger ledger
docs/orchestration/fired_triggers.jsonl. Reports which registered triggers are READY (all prerequisites in their terminal
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
        lab, res = {}, {}
        for line in open(path):
            j = json.loads(line)
            if j["type"] == "started":
                lab[j["key"]] = j.get("label", "")
            elif j["type"] == "result":
                res[j["key"]] = j.get("result")
        for k, label in lab.items():
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


def ledger():
    p = os.path.join(ORCH, "fired_triggers.jsonl")
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.isfile(p) else []


def status(journals_dir, followon_dir):
    reg = json.load(open(os.path.join(ORCH, "lane_registry_v1.json")))
    trig = json.load(open(os.path.join(ORCH, "trigger_registry_v1.json")))
    jl, led = journal_lanes(journals_dir), ledger()
    fired = {e["trigger"] + (":" + e["member"] if e.get("member") else "") for e in led}
    launched = {e["produces"]: e["action"] for e in led if e.get("produces") and isinstance(e.get("action"), dict)
                and e["action"].get("workflow_run")}
    st, info = {}, {}
    for L in reg["lanes"]:
        st[L["id"]] = lane_state(jl.get((L["workflow_run"], L["workflow_key"])))
        b = (jl.get((L["workflow_run"], L["workflow_key"])) or {}).get("build") or {}
        info[L["id"]] = {k: b.get(k) for k in ("worktree_path", "branch", "commit")}
    for F in reg["follow_ons"]:
        a = launched.get(F["id"])
        st[F["id"]] = lane_state(jl.get((a["workflow_run"], a["workflow_key"]))) if a else "not_started"
    ds_fired = {}
    for D in reg["datasets"]:
        st[D["id"]], ds_fired[D["id"]] = dataset_state(D["manifest"], followon_dir)
    try:
        import sys; sys.path.insert(0, ROOT)
        from abep_sim.hall_ensemble import load_ensemble
        st["ensemble_admitted_members"] = "non_empty" if load_ensemble()["members"] else "empty"
    except Exception as e:                                          # an invalid ensemble is reported, never treated as admitted
        st["ensemble_admitted_members"] = f"error: {e}"
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
    return {"ready": ready, "state": state, "lane_build": info}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--journals", default="/root/.claude/projects/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/subagents/workflows")
    ap.add_argument("--followon", default="/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad/followon")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    s = status(a.journals, a.followon)
    print(json.dumps(s if a.json else {"ready": s["ready"], "state": s["state"]}, sort_keys=True))
