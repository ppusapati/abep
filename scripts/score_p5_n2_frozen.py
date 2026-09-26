"""Score a FROZEN P5-N2 dataset exactly once, and bind the result to its provenance (owner decision 2026-09-26).

  verify dataset SHA256 against its freeze manifest and the pre-registration lock hash
  -> run the frozen scorer (scripts/score_p5_n2_campaign.py, unchanged since PR #28) on the canonical records
  -> write a provenance manifest: input dataset SHA, scorer file SHA + commit, prereg lock SHA, scoring time, output SHA.
Refuses to run if a score for this dataset already exists ("score once"); a rescore would need a new, dated decision.
Usage: python scripts/score_p5_n2_frozen.py hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_raw_manifest.json
"""
import datetime, gzip, hashlib, importlib.util, json, os, subprocess, sys, tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
BR = os.path.join(ROOT, "hallthruster_bridge")
SCORER = os.path.join(os.path.dirname(__file__), "score_p5_n2_campaign.py")
h = lambda b: hashlib.sha256(b).hexdigest()


def score_frozen(manifest_path, allow_existing=False):
    man = json.load(open(manifest_path))
    raw = gzip.decompress(open(os.path.join(BR, man["dataset"]), "rb").read())
    if h(raw) != man["sha256_canonical_jsonl"]:
        raise SystemExit("dataset SHA256 does not match its freeze manifest")
    lock = h(open(os.path.join(BR, "prereg", "p5_n2_prereg_lock_v1.json"), "rb").read())
    if lock != man["prereg_lock_sha256"]:
        raise SystemExit("pre-registration lock changed since the dataset was frozen")
    stem = manifest_path.replace("_raw_manifest.json", "")
    out, prov = stem + "_scores.json", stem + "_scores_provenance.json"
    if not allow_existing and (os.path.exists(out) or os.path.exists(prov)):
        raise SystemExit(f"already scored (score once): {out}")
    with tempfile.NamedTemporaryFile("wb", suffix=".jsonl", delete=False) as t:
        t.write(raw); tmp = t.name
    spec = importlib.util.spec_from_file_location("scorer", SCORER)
    s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
    s.main([tmp, "--out", out])
    os.unlink(tmp)
    try:
        scorer_commit = subprocess.run(["git", "log", "-1", "--format=%H", "--", SCORER], cwd=ROOT, capture_output=True,
                                       text=True).stdout.strip()
    except OSError:
        scorer_commit = None
    p = {"input_dataset": man["dataset"], "input_sha256_canonical_jsonl": man["sha256_canonical_jsonl"],
         "input_n_records": man["n_records"], "mode": man["mode"],
         "scorer": os.path.relpath(SCORER, ROOT), "scorer_sha256": h(open(SCORER, "rb").read()),
         "scorer_last_commit": scorer_commit, "prereg_lock_sha256": lock,
         "scored_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         "output": os.path.relpath(out, BR), "output_sha256": h(open(out, "rb").read()),
         "chain": {k: man[k] for k in ("driver_commit", "integrity_gate_commit", "scorer_commit", "preregistration")}}
    json.dump(p, open(prov, "w"), indent=1)
    return p


if __name__ == "__main__":
    print(json.dumps(score_frozen(sys.argv[1]), indent=1))
