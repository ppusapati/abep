#!/usr/bin/env bash
# hall_air_rp1_v1: run every case of the package and write ONE result file (A9.39 item 4; NP-HALL-PARAMETRIC-ENVELOPE
# addendum A9-LP). PARAMETRIC / NOT_VALIDATED. Linux / macOS (Windows: WSL2). See README.md.
#   ./run_all.sh [--jobs N] [--out DIR] [--cases C01,C05,...] [--levels A7-P,A7-C] [--skip-instantiate]
# Rerunning the same command resumes: finished runs (out/runs/*.json) are kept, unfinished ones are restarted.
set -euo pipefail

PKG=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$PKG/../../.." && pwd)
PROJ="$REPO/hallthruster_bridge"
JULIA=${JULIA:-julia}
NCPU=$( (command -v nproc >/dev/null && nproc) || sysctl -n hw.ncpu 2>/dev/null || echo 2)
JOBS=$(( NCPU > 1 ? NCPU - 1 : 1 )); [ "$JOBS" -gt 6 ] && JOBS=6
OUT="$PKG/out"
CASES=ALL
LEVELS="A7-P,A7-C"
INSTANTIATE=1
while [ $# -gt 0 ]; do
    case "$1" in
        --jobs) JOBS=$2; shift 2 ;;
        --out) OUT=$2; shift 2 ;;
        --cases) CASES=$2; shift 2 ;;
        --levels) LEVELS=$2; shift 2 ;;
        --skip-instantiate) INSTANTIATE=0; shift ;;
        -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
        *) echo "unknown argument $1" >&2; exit 2 ;;
    esac
done
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)

command -v "$JULIA" >/dev/null || { echo "Julia not found (set JULIA=/path/to/julia; required 1.11.7)" >&2; exit 1; }
JV=$("$JULIA" --startup-file=no -e 'print(VERSION)')
if [ "$JV" != "1.11.7" ] && [ "${ABEP_ALLOW_OTHER_JULIA:-0}" != "1" ]; then
    echo "Julia $JV found; this package requires 1.11.7 (the pinned Manifest). See README.md." >&2; exit 1
fi

LOCK="$OUT/.run_all.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    if [ -f "$LOCK/pid" ] && kill -0 "$(cat "$LOCK/pid")" 2>/dev/null; then
        echo "another run_all.sh (pid $(cat "$LOCK/pid")) is using $OUT" >&2; exit 1
    fi
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

# One thread per process; parallelism is across runs.
export JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
JL=("$JULIA" --startup-file=no --project="$PROJ")

if [ "$INSTANTIATE" = 1 ]; then
    echo "== instantiating the pinned Manifest (HallThruster.jl v0.23.1 @ bfb3019f; first time: downloads + precompile, ~5-15 min)"
    "${JL[@]}" -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
fi
echo "== case file reproduces from the registered sources"
"${JL[@]}" "$PKG/make_cases.jl" check
echo "== preflight (Julia version, HallThruster.jl pin, package and input sha256)"
"${JL[@]}" "$PKG/preflight.jl" "$OUT" "$JOBS"

# Queue: every selected case at every selected level, production level first.
IDS=$("${JL[@]}" -e 'using JSON3; d = JSON3.read(read(ARGS[1], String)); print(join([c.case_id for c in d.cases], ","))' "$PKG/cases_v1.json")
[ "$CASES" = ALL ] && CASES=$IDS
for c in ${CASES//,/ }; do
    case ",$IDS," in *",$c,"*) ;; *) echo "unknown case $c (cases: $IDS)" >&2; exit 2 ;; esac
done
: > "$OUT/queue.txt"
for lv in ${LEVELS//,/ }; do
    case "$lv" in A7-P|A7-C) ;; *) echo "unknown level $lv" >&2; exit 2 ;; esac
    for c in ${CASES//,/ }; do echo "$c $lv" >> "$OUT/queue.txt"; done
done
rm -rf "$OUT/claims"; rm -f "$OUT"/runs/*.tmp 2>/dev/null || true
mkdir -p "$OUT/logs" "$OUT/runs"
NQ=$(wc -l < "$OUT/queue.txt" | tr -d ' ')
NDONE=$(cd "$OUT/runs" && ls -1 2>/dev/null | grep -c '\.json$' || true)
echo "== running $NQ runs ($NDONE records already present) with $JOBS parallel jobs; logs in $OUT/logs"
T0=$(date +%s)
pids=()
for k in $(seq 1 "$JOBS"); do
    "${JL[@]}" "$PKG/worker.jl" "$OUT" "$k" > "$OUT/logs/worker_$k.log" 2>&1 &
    pids+=($!)
done
fail=0
for p in "${pids[@]}"; do wait "$p" || fail=1; done
echo "== workers finished in $(( $(date +%s) - T0 )) s"
[ "$fail" = 0 ] || echo "WARNING: a worker exited with an error (see $OUT/logs); the result file marks missing runs NOT_RUN" >&2

echo "== aggregating"
"${JL[@]}" "$PKG/aggregate.jl" "$OUT"
echo "== validating"
"${JL[@]}" "$PKG/validate.jl" "$OUT/hall_air_rp1_v1_results.json"
echo
echo "Send back this ONE file: $OUT/hall_air_rp1_v1_results.json"
echo "(optional: $OUT/hall_air_rp1_v1_results.csv for a quick look)"
