#!/usr/bin/env bash
# NP-HALL-PARAMETRIC-ENVELOPE addendum 01 (A9.33 Q2): run the AIR family on a machine with the pinned Julia stack.
# PARAMETRIC / NOT_VALIDATED. The launch gate refuses unless the AIR reaction set is COMPLETE_FOR_PARAMETRIC_ENVELOPE
# (hallthruster_bridge/propellants_air/AIR_PINNED.toml); today it is INCOMPLETE_EVIDENCE, so this script stops at step 2.
#   docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/run_local_air.sh <out_dir> [composition id | ALL] [jobs]
set -euo pipefail
OUT=${1:?usage: run_local_air.sh <out_dir> [composition id | ALL] [parallel jobs]}
CORNER=${2:-ALL}
PAR=${3:-$(nproc)}
REPO=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$REPO"
export JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1

cargo build --locked --release -p abep-julia-bridge --bin abep-air-cases
BIN=target/release/abep-air-cases
"$BIN" check
"$BIN" launch-manifest            # the launch gate: refuses (exit 1) while the AIR set is not admitted

julia --project=hallthruster_bridge -e 'using Pkg; Pkg.instantiate()'
julia --project=hallthruster_bridge -e 'include("hallthruster_bridge/bridge_lib.jl"); println("HallThruster.jl pinned commit: ", check_pin())'
test -z "$(git status --porcelain hallthruster_bridge)" || { echo "the bridge checkout changed during instantiate" >&2; exit 1; }

NSHARDS=$PAR
mkdir -p "$OUT/shards"
seq 0 $((NSHARDS - 1)) | xargs -P "$PAR" -I{} julia --project=hallthruster_bridge \
    docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/h1_envelope_air_driver.jl "$OUT/shards/s{}.jsonl" {} "$NSHARDS" "$CORNER"

NAME="h1_parametric_envelope_air_v1_${CORNER}_local"
"$BIN" freeze --name "$NAME" --out "$OUT/frozen" "$OUT"/shards/s*.jsonl
(cd "$OUT/frozen" && sha256sum ./* > SHA256SUMS)
echo "frozen manifest: $OUT/frozen/${NAME}_raw_manifest.json"
