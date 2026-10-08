# NP-HALL-PARAMETRIC-ENVELOPE addendum A3 (numerics adequacy, RG-04) driver. PARAMETRIC / NOT_VALIDATED.
# Runs the Rust-generated A3 case file (cases/h1_parametric_envelope_a3_numerics_cases_v1.json: the 17 seeded check cases
# of the v1 grid at R0 = v1 numerics, R1 = 2 x cells, R3 = 2 x duration) through hallthruster_bridge/bridge_lib.jl run_case
# in vacuum mode and records the v1 raw observables only: no status, no tolerance, no verdict (the Rust scorer applies
# the v1 run-status rule and the A3 criteria).
#   julia --project=hallthruster_bridge docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/h1_envelope_a3_driver.jl \
#         <out.jsonl> <shard> <nshards>
# Refuses to run unless the HallThruster.jl pin (check_pin), the A3 lock and the files it locks, the v1 lock and the files
# it locks, every input pinned by the v1 preregistration, the A3 case file and this driver match
# launch_manifest_a3_numerics_v1.json. Resumable (skips keys already in out.jsonl).
include(joinpath(@__DIR__, "..", "..", "..", "..", "..", "hallthruster_bridge", "bridge_lib.jl"))
using SHA
using Dates
rev = check_pin()
sha(p) = bytes2hex(open(sha256, p))
const NPDIR = normpath(joinpath(@__DIR__, ".."))
const REPO = normpath(joinpath(NPDIR, "..", "..", "..", ".."))
man = JSON3.read(read(joinpath(NPDIR, "launch_manifest_a3_numerics_v1.json"), String))
a3_lock_sha = sha(joinpath(NPDIR, "prereg_addendum_a3_numerics_lock_v1.json"))
a3_lock_sha == man.addendum_lock_sha256 || error("A3 lock does not match the A3 launch manifest")
for lockname in ("prereg_addendum_a3_numerics_lock_v1.json", "prereg_lock_v1.json")
    lk = JSON3.read(read(joinpath(NPDIR, lockname), String))
    for (f, h) in pairs(lk.files)
        sha(joinpath(NPDIR, String(f))) == h || error("$(lockname) mismatch: $(f)")
    end
end
v1_lock_sha = sha(joinpath(NPDIR, "prereg_lock_v1.json"))
v1_lock_sha == man.prereg_lock_sha256 || error("v1 preregistration lock does not match the A3 launch manifest")
prereg = JSON3.read(read(joinpath(NPDIR, "prereg_v1.json"), String))
for (f, h) in pairs(prereg.pinned_inputs)
    sha(joinpath(REPO, String(f))) == h || error("pinned input changed: $(f)")
end
driver_sha = sha(@__FILE__)
driver_sha == man.driver_sha256 || error("driver does not match the A3 launch manifest")
cases_path = joinpath(REPO, String(man.cases))
cases_sha = sha(cases_path)
cases_sha == man.cases_sha256 || error("A3 case file does not match the A3 launch manifest")
doc = JSON3.read(read(cases_path, String))
doc.addendum_lock_sha256 == a3_lock_sha || error("A3 case file was generated under another A3 lock")

out_path = ARGS[1]
shard = parse(Int, ARGS[2])
nshards = parse(Int, ARGS[3])
nshards == man.n_shards || error("n_shards $(nshards) != A3 launch manifest $(man.n_shards)")
0 <= shard < nshards || error("shard $(shard) outside 0..$(nshards - 1)")
done = Set{String}()
isfile(out_path) && for l in eachline(out_path); isempty(strip(l)) || push!(done, String(JSON3.read(l).key)); end
threads = Dict(k => get(ENV, k, nothing) for k in ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"))
const KEEP = ("retcode", "converged", "t_end_s", "sustained", "quasi_steady", "thrust_N", "discharge_current_A", "discharge_power_W",
              "ion_current_A", "anode_eff", "mass_eff", "current_eff", "voltage_eff", "divergence_eff", "Te_max_eV", "ne_max_m3",
              "Id_rms_rel", "Id_pp_rel", "Id_f_dominant_Hz", "Id_min_A", "Id_max_A", "B_max_T", "B_scale", "B_peak_minus_exit_m",
              "ion_species_fraction_atomic", "wall_ion_basis", "chemistry_basis", "chemistry_unresolved_rate_files",
              "chemistry_per_reaction", "chemistry_extrapolated_fraction_max", "chemistry_limiting_rate_file",
              "chemistry_trustworthy", "transport", "error")
for (i, c) in enumerate(doc.cases)
    (i - 1) % nshards == shard || continue
    key = String(c.key)
    key in done && continue
    rec = Dict{String,Any}("key" => key, "family" => String(c.family), "case_sha256" => String(c.case_sha256),
                           "a3_refinement" => String(c.a3_refinement), "v1_key" => String(c.v1_key),
                           "v1_case_sha256" => String(c.v1_case_sha256), "cells" => c.cells, "duration_s" => c.duration_s,
                           "cases_file_sha256" => cases_sha, "addendum_lock_sha256" => a3_lock_sha,
                           "prereg_lock_sha256" => v1_lock_sha, "driver_sha256" => driver_sha,
                           "hallthruster_commit" => rev, "hallthruster_version" => string(pkgversion(het)),
                           "julia_version" => string(VERSION), "threads_blas" => threads, "host" => Libc.gethostname(),
                           "utc_start" => string(Dates.now(Dates.UTC)), "layer" => "PARAMETRIC / NOT_VALIDATED")
    t0 = time()
    try
        LAST_SOL[] = nothing
        r = run_case(c, "vacuum")
        for k in KEEP
            haskey(r, k) && (rec[k] = r[k])
        end
        sol = LAST_SOL[]
        if r["retcode"] == "success" && !isnothing(sol)
            Id_t = het.discharge_current(sol)
            rec["finite"] = all(isfinite, Id_t) && isfinite(r["thrust_N"]) && isfinite(r["discharge_current_A"])
        else
            rec["finite"] = false
        end
    catch err
        rec["retcode"] = "error"; rec["error"] = sprint(showerror, err); rec["finite"] = false
    end
    rec["wall_s"] = time() - t0
    open(out_path, "a") do io
        JSON3.write(io, rec); println(io)
    end
    println(key, "  ", get(rec, "retcode", "?"))
    flush(stdout)
end
