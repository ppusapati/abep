# NP-HALL-PARAMETRIC-ENVELOPE addendum A6 (XE grid at study-converged numerics) driver. PARAMETRIC / NOT_VALIDATED.
# Runs an A6 case file (the convergence study, or the XE grid at the production level), both Rust-generated from the
# frozen v1 case file with only the numerical fields changed, through hallthruster_bridge/bridge_lib.jl run_case in vacuum
# mode, and records the v1 raw observables only: no status, threshold or verdict.
#   julia --project=hallthruster_bridge docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/h1_envelope_a6_driver.jl \
#         <launch manifest file name in the NP directory> <out.jsonl> <shard> <nshards>
# Refuses unless the HallThruster.jl pin (check_pin), the A6 lock and its files, the v1 lock and its files, every input
# pinned by the v1 preregistration, the case file and this driver match the named A6 launch manifest. Resumable.
include(joinpath(@__DIR__, "..", "..", "..", "..", "..", "hallthruster_bridge", "bridge_lib.jl"))
using SHA
using Dates
rev = check_pin()
sha(p) = bytes2hex(open(sha256, p))
const NPDIR = normpath(joinpath(@__DIR__, ".."))
const REPO = normpath(joinpath(NPDIR, "..", "..", "..", ".."))
lm_name = ARGS[1]
lm_name in ("launch_manifest_a6_study_v1.json", "launch_manifest_a6_xe_grid_v1.json") || error("unknown A6 launch manifest $(lm_name)")
man = JSON3.read(read(joinpath(NPDIR, lm_name), String))
a6_lock_sha = sha(joinpath(NPDIR, "prereg_addendum_a6_xe_converged_grid_lock_v1.json"))
a6_lock_sha == man.addendum_lock_sha256 || error("A6 lock does not match the launch manifest")
for lockname in ("prereg_addendum_a6_xe_converged_grid_lock_v1.json", "prereg_lock_v1.json")
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
driver_sha = sha(@__FILE__)
driver_sha == man.driver_sha256 || error("driver does not match the launch manifest")
cases_path = joinpath(REPO, String(man.cases))
cases_sha = sha(cases_path)
cases_sha == man.cases_sha256 || error("case file does not match the launch manifest")
doc = JSON3.read(read(cases_path, String))
doc.addendum_lock_sha256 == a6_lock_sha || error("case file was generated under another A6 lock")

out_path = ARGS[2]
shard = parse(Int, ARGS[3])
nshards = parse(Int, ARGS[4])
nshards == man.n_shards || error("n_shards $(nshards) != launch manifest $(man.n_shards)")
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
                           "a6_level" => String(c.a6_level), "v1_key" => String(c.v1_key),
                           "v1_case_sha256" => String(c.v1_case_sha256), "cells" => c.cells, "dt_s" => c.dt_s,
                           "duration_s" => c.duration_s, "cases_file_sha256" => cases_sha,
                           "addendum_lock_sha256" => a6_lock_sha, "prereg_lock_sha256" => v1_lock_sha,
                           "driver_sha256" => driver_sha, "hallthruster_commit" => rev,
                           "hallthruster_version" => string(pkgversion(het)), "julia_version" => string(VERSION),
                           "threads_blas" => threads, "host" => Libc.gethostname(),
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
