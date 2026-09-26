"""T_O4_SCORE action for one O4 dataset, through the transactional lifecycle (owner rule 2026-09-26):
claim -> freeze (scripts/score_p5_n2_staged.py freeze) -> LAUNCHED (evidence: freeze manifest) -> score once -> VERIFIED
(evidence: provenance sha256, scores sha256, mandatory reproduced, o4_trigger_fired). Any exception leaves the claim in its
last state; recovery is by the operator with evidence (never an automatic re-run).
Usage: python scripts/orchestration/o4_score_dataset.py <manifest_name> [--followon DIR]
"""
import hashlib, json, os, subprocess, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
FOLLOWON = "/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad/followon"
h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()


def run(*a):
    r = subprocess.run([sys.executable, *a], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{' '.join(a)} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def main(name, followon=FOLLOWON):
    member = f"ds_{name}"
    shards = [os.path.join(followon, name, f"s{i}.jsonl") for i in range(4)]
    print(run("scripts/orchestration/trigger_ledger.py", "claim", "T_O4_SCORE", member).strip())
    run("scripts/score_p5_n2_staged.py", "freeze", f"hallthruster_bridge/campaign/manifests/{name}.json", *shards)
    V = f"hallthruster_bridge/validation/p5_n2_campaign_v1_{name}_"
    run("scripts/orchestration/trigger_ledger.py", "launched", "T_O4_SCORE", member, "--evidence",
        json.dumps({"artifact": V + "raw_manifest.json", "sha256": h(os.path.join(ROOT, V + "raw_manifest.json"))}))
    run("scripts/score_p5_n2_staged.py", "score", V + "raw_manifest.json")
    p = json.load(open(os.path.join(ROOT, V + "scores_provenance.json")))
    assert h(os.path.join(ROOT, V + "scores.json")) == p["output_sha256"] and p["mandatory_reproduced"]
    chem = list(p["o4"]["chemistry"])[0]
    ev = json.load(open(os.path.join(ROOT, V + "scores.json")))["staged_escalation"][chem]
    run("scripts/orchestration/trigger_ledger.py", "verified", "T_O4_SCORE", member, "--evidence", json.dumps(
        {"artifact": V + "scores_provenance.json", "sha256": h(os.path.join(ROOT, V + "scores_provenance.json")),
         "scores_sha256": p["output_sha256"], "mandatory_reproduced": True, "o4_trigger_fired": ev["trigger_fired"]}))
    import collections
    summary = {"dataset": name, "chemistry": chem, "baseline": ev["baseline"], "trigger_fired": ev["trigger_fired"],
               "n_run_level_triggers": len(ev["run_level_triggers"]),
               "by_kind": dict(collections.Counter(t[1].split(" ")[0] for t in ev["run_level_triggers"])),
               "verdict_changes": ev["verdict_changes"], "scores_sha256": p["output_sha256"]}
    print(json.dumps(summary))
    return summary


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[sys.argv.index("--followon") + 1] if "--followon" in sys.argv else FOLLOWON)
