"""Pre-built launch manifests for the P5-N2 follow-on runs (owner decision 2026-09-26): nothing here is run automatically, and
no configuration is decided after results. Every manifest lists the exact expected record keys, the chemistry config with its
pre-registered sha256, the mode and the exact driver command lines (4 shards).
  facility_mandatory        1080 runs: 9 candidates x 4 mandatory chemistry x 30 cases, facility mode (secondary evidence;
                             launched only after the vacuum promotion result)
  staged_<sensitivity>       270 runs each, vacuum, against its pre-registered baseline (launch per O4 first stage)
  escalation_<combination>   270 runs each, vacuum (launch only if that sensitivity's O4 trigger fires)
`check(manifest, paths)` is the structural gate for these datasets (keys, mode, smoke, lock hash, HallThruster commit, return
codes counted only); the v1 vacuum gate (scripts/audit_p5_n2_campaign_records.py @ fcd6720) is left untouched.
Usage: python scripts/make_p5_n2_launch_manifests.py        (writes hallthruster_bridge/campaign/manifests/*.json)
"""
import collections, hashlib, json, os, sys, tomllib

ROOT = os.path.join(os.path.dirname(__file__), "..")
BR = os.path.join(ROOT, "hallthruster_bridge")
OUT = os.path.join(BR, "campaign", "manifests")
DRIVER = "hallthruster_bridge/campaign/p5_n2_campaign.jl"
h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()


def _inputs():
    crit = json.load(open(os.path.join(BR, "prereg", "p5_n2_validation_criteria_v1.json")))
    cands = [c["ensemble_member_id"] for c in json.load(open(os.path.join(BR, "ensemble", "transport_ensemble_v0.json")))["screening_candidates"]]
    cases = [c["id"] for c in json.load(open(os.path.join(BR, "cases", "p5_n2.json")))["cases"]]
    return crit, cands, cases


def manifest(name, chems, mode, role, crit, cands, cases, **extra):
    pins = crit["inputs_pinned"]["chemistry_configs_sha256"]
    keys = sorted(f"{cd}|{ch}|{cs}|{mode}" for cd in cands for ch in chems for cs in cases)
    return {"name": name, "role": role, "mode": mode, "chemistry": {c: pins[c] for c in chems}, "n_runs": len(keys),
            "expected_keys": keys, "driver": DRIVER, "driver_sha256": h(os.path.join(ROOT, DRIVER)),
            "prereg_lock_sha256": h(os.path.join(BR, "prereg", "p5_n2_prereg_lock_v1.json")),
            "commands": [f"julia --project=hallthruster_bridge {DRIVER} <out>/s{i}.jsonl {mode} {i} 4 {','.join(chems)}" for i in range(4)],
            "structural_gate": "python scripts/make_p5_n2_launch_manifests.py --check <manifest> <out>/s*.jsonl", **extra}


def build():
    crit, cands, cases = _inputs()
    ms = [manifest("facility_mandatory", crit["mandatory_chemistry"], "facility",
                   "secondary consistency evidence; launch after the vacuum promotion result (execution_order)", crit, cands, cases)]
    for sens, spec in crit["staged_sensitivities"].items():
        stem = sens[:-5]
        ms.append(manifest(f"staged_{stem}", [sens], "vacuum", "O4 first stage (compare with its baseline)", crit, cands, cases,
                           baseline=spec["baseline"]))
        for prim, esc in spec["escalation"].items():
            ms.append(manifest(f"escalation_{esc[:-5]}", [esc], "vacuum", f"O4 escalation of {sens}: launch only if its trigger fires",
                               crit, cands, cases, compare_with=prim, sensitivity=sens))
    return ms


def check(man, paths):
    pin = tomllib.load(open(os.path.join(BR, "PINNED.toml"), "rb"))
    commit = pin["commit"] if "commit" in pin else pin["hallthruster"]["commit"]
    recs = [json.loads(l) for p in paths for l in open(p) if l.strip()]
    keys = [r["key"] for r in recs]
    got, exp = set(keys), set(man["expected_keys"])
    res = {"n_records": len(recs), "n_expected": len(exp),
           "duplicates": [k for k, n in collections.Counter(keys).items() if n > 1],
           "missing": sorted(exp - got), "unexpected": sorted(got - exp),
           "mode_ok": all(r.get("mode") == man["mode"] for r in recs),
           "smoke_false": all(r.get("smoke") is False for r in recs),
           "lock_hash_ok": all(r.get("prereg_lock_sha256") == man["prereg_lock_sha256"] for r in recs),
           "hallthruster_commit_ok": all(r.get("hallthruster_commit") == commit for r in recs),
           "retcode_counts": dict(collections.Counter("success" if r.get("retcode") == "success" else "non-success" for r in recs))}
    res["PASS"] = (len(recs) == len(exp) and not res["duplicates"] and not res["missing"] and not res["unexpected"]
                   and res["mode_ok"] and res["smoke_false"] and res["lock_hash_ok"] and res["hallthruster_commit_ok"])
    return res


if __name__ == "__main__":
    if "--check" in sys.argv:
        i = sys.argv.index("--check")
        r = check(json.load(open(sys.argv[i + 1])), sys.argv[i + 2:])
        print(json.dumps({k: (v if not isinstance(v, list) or len(v) < 10 else f"{len(v)} items") for k, v in r.items()}, indent=1))
        sys.exit(0 if r["PASS"] else 1)
    os.makedirs(OUT, exist_ok=True)
    for m in build():
        json.dump(m, open(os.path.join(OUT, m["name"] + ".json"), "w"), indent=1)
        print(m["name"], m["n_runs"])
