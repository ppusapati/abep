#!/bin/bash
# O4 escalation family ndd_hmslow, ATTEMPT 3 (owner decision 2026-09-27 after the container restart of 2026-09-27 ~05:46Z-06:36Z): only the
# remaining di_lower_nel_wang dataset, in a fresh <manifest>_attempt3 directory; the attempt-2 partial output is preserved under
# hallthruster_bridge/validation/interrupted/<manifest>_attempt2/ and never read. Same launch configuration as attempts 1-2
# (4 shards per dataset, pinned manifests, pinned driver in wt_followon). Execution provenance is written before any run.
S=/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad
W=$S/wt_followon
LOG=$S/followon/progress_escalation_ndd_hmslow_attempt3.log
cd $W
for M in escalation_n2_n_ndd_hmslow_di_lower_nel_wang; do
  OUT=$S/followon/${M}_attempt3
  if [ -e $OUT ]; then echo "$(date -u +%T) REFUSE $M: $OUT exists" >> $LOG; continue; fi
  mkdir -p $OUT
  MODE=$(python -c "import json;print(json.load(open('hallthruster_bridge/campaign/manifests/$M.json'))['mode'])")
  CHEM=$(python -c "import json;print(','.join(json.load(open('hallthruster_bridge/campaign/manifests/$M.json'))['chemistry']))")
  python3 - "$OUT/execution_provenance.json" "$M" <<'PY'
import json, os, subprocess, sys, hashlib, datetime, platform
out, m = sys.argv[1], sys.argv[2]
sh = lambda *a: subprocess.run(a, capture_output=True, text=True).stdout.strip()
man = f"hallthruster_bridge/campaign/manifests/{m}.json"
pin = open("hallthruster_bridge/PINNED.toml").read()
prov = {"dataset": m, "attempt": 3, "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "supersedes": f"hallthruster_bridge/validation/interrupted/{m}_attempt2/",
        "launch_manifest": man, "launch_manifest_sha256": hashlib.sha256(open(man, "rb").read()).hexdigest(),
        "runner_worktree_commit": sh("git", "rev-parse", "HEAD"), "runner_worktree_clean": sh("git", "status", "--porcelain") == "",
        "julia_version": sh("julia", "--version"),
        "hallthruster_pinned_commit": __import__("re").search(r'^commit\s*=\s*"([0-9a-f]{40})"', pin, __import__("re").M).group(1),
        "thread_env": {k: os.environ.get(k) for k in ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
        "shards": 4, "nproc": os.cpu_count(), "host": platform.node(), "python": platform.python_version()}
json.dump(prov, open(out, "w"), indent=1)
PY
  echo "$(date -u +%T) start $M ($MODE, $CHEM) attempt3" >> $LOG
  for i in 0 1 2 3; do
    julia --project=hallthruster_bridge hallthruster_bridge/campaign/p5_n2_campaign.jl $OUT/s$i.jsonl $MODE $i 4 $CHEM > $OUT/s$i.log 2>&1 &
  done
  wait
  python scripts/make_p5_n2_launch_manifests.py --check hallthruster_bridge/campaign/manifests/$M.json $OUT/s*.jsonl > $OUT/structural_check.json
  echo "$(date -u +%T) done $M structural_exit=$?" >> $LOG
done
echo "$(date -u +%T) ALL DONE" >> $LOG
