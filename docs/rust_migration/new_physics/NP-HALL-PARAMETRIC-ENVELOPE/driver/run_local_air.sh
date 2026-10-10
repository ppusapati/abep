#!/usr/bin/env bash
# NP-HALL-PARAMETRIC-ENVELOPE prereg addendum A1 (A9.33 Q2, A9.34 M1): run the AIR family on a machine with the pinned
# Julia stack. PARAMETRIC / NOT_VALIDATED. The launch path is explicit: complete (LP-COMPLETE, refused while the AIR set in
# hallthruster_bridge/propellants_air/AIR_PINNED.toml is not COMPLETE_FOR_PARAMETRIC_ENVELOPE; today it is
# INCOMPLETE_EVIDENCE) or bounded (LP-BOUNDED, the registered BV-AIR-LL-NOM, labelled information only).
# The launch manifest is regenerated and must equal the committed one when one is committed.
#   docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/run_local_air.sh <out_dir> <complete|bounded> [composition id | ALL] [jobs]
set -euo pipefail
OUT=${1:?usage: run_local_air.sh <out_dir> <complete|bounded> [composition id | ALL] [parallel jobs]}
LPATH=${2:?launch path: complete or bounded}
CORNER=${3:-ALL}
PAR=${4:-$(nproc)}
REPO=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$REPO"
export JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1

cargo build --locked --release -p abep-julia-bridge --bin abep-air-cases
BIN=target/release/abep-air-cases
"$BIN" check
"$BIN" launch-manifest --path "$LPATH"   # the launch gate (exit 1 when refused)
test -z "$(git status --porcelain docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE)" || { echo "the AIR launch manifest differs from the committed one" >&2; exit 1; }

julia --project=hallthruster_bridge -e 'using Pkg; Pkg.instantiate()'
julia --project=hallthruster_bridge -e 'include("hallthruster_bridge/bridge_lib.jl"); println("HallThruster.jl pinned commit: ", check_pin())'
test -z "$(git status --porcelain hallthruster_bridge)" || { echo "the bridge checkout changed during instantiate" >&2; exit 1; }

NSHARDS=$PAR
mkdir -p "$OUT/shards"
seq 0 $((NSHARDS - 1)) | xargs -P "$PAR" -I{} julia --project=hallthruster_bridge \
    docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/h1_envelope_air_driver.jl "$OUT/shards/s{}.jsonl" {} "$NSHARDS" "$CORNER"

NAME="h1_parametric_envelope_air_v1_${LPATH}_${CORNER}_local"
"$BIN" freeze --name "$NAME" --out "$OUT/frozen" "$OUT"/shards/s*.jsonl
(cd "$OUT/frozen" && sha256sum ./* > SHA256SUMS)
echo "frozen manifest: $OUT/frozen/${NAME}_raw_manifest.json"
