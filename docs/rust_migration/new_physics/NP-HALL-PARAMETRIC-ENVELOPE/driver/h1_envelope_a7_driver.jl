# NP-HALL-PARAMETRIC-ENVELOPE addendum A7 (Hall numerical method) driver. PARAMETRIC / NOT_VALIDATED.
# Runs an A7 case file (the demonstration set or an XE grid stage), Rust-generated from the frozen v1 case file with only
# the numerical fields changed, through hallthruster_bridge/a7_numerics.jl a7_record (vacuum, XE, measured B; physics as
# bridge_lib.run_case) and records raw observables only: no status, threshold or verdict.
#   julia --project=hallthruster_bridge docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/h1_envelope_a7_driver.jl \
#         <launch manifest file name in the NP directory> <out.jsonl> <shard> <nshards>
# Refuses unless the HallThruster.jl pin (check_pin), the A7 lock and its files, the v1 lock and its files, every input
# pinned by the v1 preregistration, the A7 bridge file, the case file and this driver match the named launch manifest.
# Resumable: keys already in <out.jsonl> are skipped.
include(joinpath(@__DIR__, "..", "..", "..", "..", "..", "hallthruster_bridge", "a7_numerics.jl"))
using SHA
using Dates
rev = check_pin()
sha(p) = bytes2hex(open(sha256, p))
const NPDIR = normpath(joinpath(@__DIR__, ".."))
const REPO = normpath(joinpath(NPDIR, "..", "..", "..", ".."))
lm_name = ARGS[1]
startswith(lm_name, "launch_manifest_a7_") || error("not an A7 launch manifest: $(lm_name)")
man = JSON3.read(read(joinpath(NPDIR, lm_name), String))
a7_lock_sha = sha(joinpath(NPDIR, "prereg_addendum_a7_hall_numerical_method_lock_v1.json"))
a7_lock_sha == man.addendum_lock_sha256 || error("A7 lock does not match the launch manifest")
for lockname in ("prereg_addendum_a7_hall_numerical_method_lock_v1.json", "prereg_lock_v1.json")
    lk = JSON3.read(read(joinpath(NPDIR, lockname), String))
    for (f, h) in pairs(lk.files)
        sha(joinpath(NPDIR, String(f))) == h || error("$(lockname) mismatch: $(f)")
    end
end
v1_lock_sha = sha(joinpath(NPDIR, "prereg_lock_v1.json"))
v1_lock_sha == man.prereg_lock_sha256 || error("v1 preregistration lock does not match the launch manifest")
prereg = JSON3.read(read(joinpath(NPDIR, "prereg_v1.json"), String))
for (f, h) in pairs(prereg.pinned_inputs)
    sha(joinpath(REPO, String(f))) == h || error("pinned input changed: $(f)")
end
sha(joinpath(REPO, String(man.a7_bridge))) == man.a7_bridge_sha256 || error("A7 bridge file does not match the launch manifest")
driver_sha = sha(@__FILE__)
driver_sha == man.driver_sha256 || error("driver does not match the launch manifest")
cases_path = joinpath(REPO, String(man.cases))
cases_sha = sha(cases_path)
cases_sha == man.cases_sha256 || error("case file does not match the launch manifest")
doc = JSON3.read(read(cases_path, String))
doc.addendum_lock_sha256 == a7_lock_sha || error("case file was generated under another A7 lock")

out_path = ARGS[2]
shard = parse(Int, ARGS[3])
nshards = parse(Int, ARGS[4])
nshards == man.n_shards || error("n_shards $(nshards) != launch manifest $(man.n_shards)")
0 <= shard < nshards || error("shard $(shard) outside 0..$(nshards - 1)")
done = Set{String}()
isfile(out_path) && for l in eachline(out_path); isempty(strip(l)) || push!(done, String(JSON3.read(l).key)); end
threads = Dict(k => get(ENV, k, nothing) for k in ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"))
for (i, c) in enumerate(doc.cases)
    (i - 1) % nshards == shard || continue
    key = String(c.key)
    key in done && continue
    rec = Dict{String,Any}("key" => key, "family" => String(c.family), "case_sha256" => String(c.case_sha256),
                           "a7_level" => String(c.a7_level), "v1_key" => String(c.v1_key),
                           "v1_case_sha256" => String(c.v1_case_sha256), "cells" => c.cells, "dt_s" => c.dt_s,
                           "duration_s" => c.duration_s, "average_start_s" => c.average_start_s, "num_save" => c.num_save,
                           "cases_file_sha256" => cases_sha, "addendum_lock_sha256" => a7_lock_sha,
                           "prereg_lock_sha256" => v1_lock_sha, "driver_sha256" => driver_sha,
                           "a7_bridge_sha256" => String(man.a7_bridge_sha256), "hallthruster_commit" => rev,
                           "hallthruster_version" => string(pkgversion(het)), "julia_version" => string(VERSION),
                           "threads_blas" => threads, "host" => Libc.gethostname(),
                           "utc_start" => string(Dates.now(Dates.UTC)), "layer" => "PARAMETRIC / NOT_VALIDATED")
    try
        merge!(rec, a7_record(c))
    catch err
        rec["retcode"] = "error"; rec["error"] = sprint(showerror, err); rec["finite"] = false; rec["converged"] = false
    end
    LAST_SOL[] = nothing
    open(out_path, "a") do io
        JSON3.write(io, rec); println(io)
    end
    println(key, "  ", get(rec, "retcode", "?"), "  ", round(get(rec, "wall_s", 0.0); digits = 1), " s")
    flush(stdout)
    GC.gc()
end
