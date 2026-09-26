"""Structural integrity gate for the P5-N2 campaign records, run BEFORE the frozen scorer (owner decision 2026-09-26).
Reads identity and bookkeeping fields only; never reads discharge current, thrust or any residual.
Checks: expected record count; no duplicate keys; no missing expected keys (candidates x mandatory chemistry x cases x mode);
mode, smoke flag, pre-registration lock hash and HallThruster commit on every record; no staged-sensitivity or other-mode
records; every record has a terminal return code (success vs non-success counted, nothing else read).
Usage: python scripts/audit_p5_n2_campaign_records.py <mode> <runs.jsonl ...>   (exit code 0 = PASS)
"""
import collections, hashlib, json, os, sys, tomllib

ROOT = os.path.join(os.path.dirname(__file__), "..")
BR = os.path.join(ROOT, "hallthruster_bridge")
STRUCTURAL = ("key", "candidate", "chemistry", "case", "point", "registration", "coil_shape", "mode", "smoke",
              "prereg_lock_sha256", "hallthruster_commit", "retcode")


def expected_keys(mode):
    crit = json.load(open(os.path.join(BR, "prereg", "p5_n2_validation_criteria_v1.json")))
    cands = [c["ensemble_member_id"] for c in json.load(open(os.path.join(BR, "ensemble", "transport_ensemble_v0.json")))["screening_candidates"]]
    cases = [c["id"] for c in json.load(open(os.path.join(BR, "cases", "p5_n2.json")))["cases"]]
    return {f"{cd}|{ch}|{cs}|{mode}" for cd in cands for ch in crit["mandatory_chemistry"] for cs in cases}, cands, crit


def audit(mode, paths):
    exp, cands, crit = expected_keys(mode)
    lock_sha = hashlib.sha256(open(os.path.join(BR, "prereg", "p5_n2_prereg_lock_v1.json"), "rb").read()).hexdigest()
    pin = tomllib.load(open(os.path.join(BR, "PINNED.toml"), "rb"))
    commit = next(v for k, v in pin.get("hallthruster", pin).items() if k == "commit") if "hallthruster" in pin else pin["commit"]
    recs = []
    for p in paths:
        for line in open(p):
            r = json.loads(line)
            recs.append({k: r.get(k) for k in STRUCTURAL})            # structural fields only
    keys = [r["key"] for r in recs]
    dup = [k for k, n in collections.Counter(keys).items() if n > 1]
    got = set(keys)
    checks = {
        "n_records": len(recs), "n_expected": len(exp),
        "count_ok": len(recs) == len(exp),
        "duplicates": dup, "missing": sorted(exp - got), "unexpected": sorted(got - exp),
        "mode_ok": all(r["mode"] == mode for r in recs),
        "smoke_false": all(r["smoke"] is False for r in recs),
        "lock_hash_ok": all(r["prereg_lock_sha256"] == lock_sha for r in recs),
        "hallthruster_commit_ok": all(r["hallthruster_commit"] == commit for r in recs),
        "only_mandatory_chemistry": all(r["chemistry"] in crit["mandatory_chemistry"] for r in recs),
        "grid": {"candidates": len({r["candidate"] for r in recs}), "chemistries": len({r["chemistry"] for r in recs}),
                 "cases": len({r["case"] for r in recs})},
        "retcode_terminal": all(isinstance(r["retcode"], str) and r["retcode"] != "" for r in recs),
        "retcode_counts": dict(collections.Counter("success" if r["retcode"] == "success" else "non-success" for r in recs)),
    }
    checks["grid_ok"] = checks["grid"] == {"candidates": len(cands), "chemistries": len(crit["mandatory_chemistry"]), "cases": 30}
    ok = (checks["count_ok"] and not dup and not checks["missing"] and not checks["unexpected"] and checks["mode_ok"]
          and checks["smoke_false"] and checks["lock_hash_ok"] and checks["hallthruster_commit_ok"]
          and checks["only_mandatory_chemistry"] and checks["grid_ok"] and checks["retcode_terminal"])
    checks["PASS"] = ok
    return checks


if __name__ == "__main__":
    res = audit(sys.argv[1], sys.argv[2:])
    print(json.dumps({k: (v if not isinstance(v, list) or len(v) < 10 else f"{len(v)} items") for k, v in res.items()}, indent=1))
    sys.exit(0 if res["PASS"] else 1)
