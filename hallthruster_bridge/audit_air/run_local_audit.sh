#!/usr/bin/env bash
# CA-HALL-AIR-v1 (NP-HALL-CHEM-AIR v1 + addendum 01): run the 576-case blind state envelope on a machine with the pinned
# Julia stack (1.11.7, HallThruster.jl v0.23.1 bfb3019f) and network access to the Julia package servers, freeze the shard
# outputs and compute the verdicts. STATUS when written: PREPARED_NOT_RUN (the authoring container cannot reach the Julia
# hosts). The verdicts stay PROVISIONAL while AIR_PINNED.toml lists a tier-1 gap.
#   hallthruster_bridge/audit_air/run_local_audit.sh <out_dir> [parallel jobs]
# Steps: build the Rust tool; regenerate and byte-check the audit case file and snapshot MANIFEST; instantiate the committed
# Manifest.toml; run the shards (threads / BLAS pinned to 1); freeze (sorted by key, gzip mtime 0, sha256 manifest); write
# the verdict file from the frozen records only. Resumable: a rerun skips keys already present in a shard output.
set -euo pipefail
OUT=${1:?usage: run_local_audit.sh <out_dir> [parallel jobs]}
PAR=${2:-$(nproc)}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
cd "$REPO"
export JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1

cargo build --locked --release -p abep-julia-bridge --bin abep-air-cases
BIN=target/release/abep-air-cases
"$BIN" audit-check

julia --project=hallthruster_bridge -e 'using Pkg; Pkg.instantiate()'
julia --project=hallthruster_bridge -e 'include("hallthruster_bridge/bridge_lib.jl"); println("HallThruster.jl pinned commit: ", check_pin())'
test -z "$(git status --porcelain hallthruster_bridge)" || { echo "the bridge checkout changed during instantiate" >&2; exit 1; }

NSHARDS=$PAR
mkdir -p "$OUT/shards"
seq 0 $((NSHARDS - 1)) | xargs -P "$PAR" -I{} julia --project=hallthruster_bridge \
    hallthruster_bridge/audit_air/air_state_envelope.jl "$OUT/shards/s{}.jsonl" {} "$NSHARDS"

NAME=ca_hall_air_v1_local
"$BIN" audit-freeze --name "$NAME" --out "$OUT/frozen" "$OUT"/shards/s*.jsonl
MSHA=$(sha256sum "$OUT/frozen/${NAME}_raw_manifest.json" | cut -d' ' -f1)
"$BIN" audit-verdicts --manifest "$OUT/frozen/${NAME}_raw_manifest.json" --manifest-sha256 "$MSHA" --out "$OUT/ca_hall_air_v1_verdicts.json"
echo "frozen manifest: $OUT/frozen/${NAME}_raw_manifest.json sha256 $MSHA"
echo "verdicts: $OUT/ca_hall_air_v1_verdicts.json (commit it under hallthruster_bridge/audit_air/ with the frozen files)"
