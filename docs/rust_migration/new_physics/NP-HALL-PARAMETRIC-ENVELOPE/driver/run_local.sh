#!/usr/bin/env bash
# NP-HALL-PARAMETRIC-ENVELOPE v1 (A9.32): run the preregistered H-1 HallThruster.jl envelope on a machine that has the pinned
# Julia (1.11.7) and network access to the Julia package servers. PARAMETRIC / NOT_VALIDATED.
#   docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/run_local.sh <out_dir> [XE|N2_PROXY|ALL] [parallel jobs]
# Steps: build the Rust tool; regenerate + dry-run the case file (byte equality); instantiate the committed Manifest.toml
# (HallThruster.jl v0.23.1, bfb3019f...); run the 64 shards (threads / BLAS pinned to 1, Rust launch: pin, input hashes,
# Julia version, sidecar); freeze the outputs into one sha-pinned raw file; print the closure-run command.
# Resumable: a rerun skips keys already present in a shard output.
set -euo pipefail
OUT=${1:?usage: run_local.sh <out_dir> [XE|N2_PROXY|ALL] [parallel jobs]}
FAMILY=${2:-XE}
PAR=${3:-$(nproc)}
REPO=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$REPO"
export JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1

cargo build --locked --release -p abep-julia-bridge --bin abep-h1-envelope-cases -p abep-assess --bin abep-assess-closure
BIN=target/release/abep-h1-envelope-cases
"$BIN" check

julia --project=hallthruster_bridge -e 'using Pkg; Pkg.instantiate()'
julia --project=hallthruster_bridge -e 'include("hallthruster_bridge/bridge_lib.jl"); println("HallThruster.jl pinned commit: ", check_pin())'
test -z "$(git status --porcelain hallthruster_bridge)" || { echo "the bridge checkout changed during instantiate" >&2; exit 1; }

NSHARDS=$(sed -n 's/^ "n_shards": \([0-9]*\),$/\1/p' docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/launch_manifest_v1.json)
mkdir -p "$OUT/shards"
seq 0 $((NSHARDS - 1)) | xargs -P "$PAR" -I{} "$BIN" run-shard --shard {} --out "$OUT/shards" --family "$FAMILY"

NAME="h1_parametric_envelope_v1_${FAMILY}_local"
"$BIN" freeze --name "$NAME" --out "$OUT/frozen" "$OUT"/shards/s*.jsonl
cp "$OUT"/shards/*.sidecar.json "$OUT/frozen/"
MSHA=$(sha256sum "$OUT/frozen/${NAME}_raw_manifest.json" | cut -d' ' -f1)
(cd "$OUT/frozen" && sha256sum ./* > SHA256SUMS)
echo "frozen manifest: $OUT/frozen/${NAME}_raw_manifest.json sha256 $MSHA"
echo "closure run: target/release/abep-assess-closure --envelope $OUT/frozen/${NAME}_raw_manifest.json --envelope-sha256 $MSHA --rust-commit $(git rev-parse HEAD) --out <record.json>"
