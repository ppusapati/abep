#!/bin/bash
# Pre-registered follow-on runs from the pinned worktree: O4 first-stage sensitivities (vacuum), then facility mandatory.
S=/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad
W=$S/wt_followon
cd $W
for M in staged_n2_n_exc_johnsonlow staged_n2_n_rot_off staged_n2_n_ndd_hmslow staged_n2_n_ndd_hmshigh staged_n2_n_n2dication facility_mandatory; do
  OUT=$S/followon/$M; mkdir -p $OUT
  MODE=$(python -c "import json;print(json.load(open('hallthruster_bridge/campaign/manifests/$M.json'))['mode'])")
  CHEM=$(python -c "import json;print(','.join(json.load(open('hallthruster_bridge/campaign/manifests/$M.json'))['chemistry']))")
  echo "$(date -u +%T) start $M ($MODE, $CHEM)" >> $S/followon/progress.log
  for i in 0 1 2 3; do
    julia --project=hallthruster_bridge hallthruster_bridge/campaign/p5_n2_campaign.jl $OUT/s$i.jsonl $MODE $i 4 $CHEM > $OUT/s$i.log 2>&1 &
  done
  wait
  python scripts/make_p5_n2_launch_manifests.py --check hallthruster_bridge/campaign/manifests/$M.json $OUT/s*.jsonl > $OUT/structural_check.json
  echo "$(date -u +%T) done $M structural_exit=$?" >> $S/followon/progress.log
done
echo "$(date -u +%T) ALL DONE" >> $S/followon/progress.log
