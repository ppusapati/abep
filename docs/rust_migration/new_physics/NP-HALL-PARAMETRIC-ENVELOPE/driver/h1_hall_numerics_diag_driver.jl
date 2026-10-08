# Hall numerics investigation (A9.36), Phase 1 driver. DIAGNOSTIC ONLY, never score-bearing.
# Runs frozen v1 XE cases (by v1 key, physics unchanged) at numerics variants through hallthruster_bridge/a7_numerics.jl
# and writes one JSONL record per job with the per-frame series (t, I_d, instantaneous thrust, adaptive step limit,
# max T_e, min n_e) and the thrust of the time-averaged state over the second half (the v1 / A6 statistic).
#   julia --project=hallthruster_bridge <this> <jobs.json> <out.jsonl> <shard> <nshards>
# A job: {"job": id, "v1_key": key, "cells_factor": k, "duration_factor": d, "num_save": n, and optionally CFL, min_dt_s,
# max_small_steps, reconstruct, implicit_energy, init_ion_density_factor}. dt_s = v1 dt / cells_factor (the A6 ladder rule). Resumable by job id
# across all shard files of the output directory.
include(joinpath(@__DIR__, "..", "..", "..", "..", "..", "hallthruster_bridge", "a7_numerics.jl"))
using SHA
using Dates
rev = check_pin()
const NPDIR = normpath(joinpath(@__DIR__, ".."))
v1 = JSON3.read(read(joinpath(NPDIR, "cases", "h1_parametric_envelope_cases_v1.json"), String))
byk = Dict(String(c.key) => c for c in v1.cases if c.family == "XE")
jobs = JSON3.read(read(ARGS[1], String))
out_path, shard, nshards = ARGS[2], parse(Int, ARGS[3]), parse(Int, ARGS[4])
# Resume set: every job already recorded in any .jsonl of the output directory (shards may be re-ordered between runs).
done = Set{String}()
for f in readdir(dirname(abspath(out_path)); join = true)
    endswith(f, ".jsonl") || continue
    for l in eachline(f); isempty(strip(l)) || push!(done, String(JSON3.read(l).job)); end
end
driver_sha = bytes2hex(open(sha256, @__FILE__))
lib_sha = bytes2hex(open(sha256, joinpath(@__DIR__, "..", "..", "..", "..", "..", "hallthruster_bridge", "a7_numerics.jl")))
for (i, j) in enumerate(jobs)
    (i - 1) % nshards == shard || continue
    String(j.job) in done && continue
    c = byk[String(j.v1_key)]
    k, d = j.cells_factor, j.duration_factor
    n = (cells = round(Int, c.cells * k), dt_s = c.dt_s / k, duration_s = c.duration_s * d, num_save = j.num_save,
         CFL = Float64(get(j, :CFL, A7_SOLVER_DEFAULTS.CFL)), min_dt_s = Float64(get(j, :min_dt_s, A7_SOLVER_DEFAULTS.min_dt_s)),
         max_dt_s = A7_SOLVER_DEFAULTS.max_dt_s, max_small_steps = Int(get(j, :max_small_steps, A7_SOLVER_DEFAULTS.max_small_steps)),
         adaptive = true, reconstruct = Bool(get(j, :reconstruct, true)),
         implicit_energy = Float64(get(j, :implicit_energy, A7_SOLVER_DEFAULTS.implicit_energy)))
    haskey(j, :init_ion_density_factor) && (n = merge(n, (init_ion_density_factor = Float64(j.init_ion_density_factor),)))
    rec = Dict{String,Any}("job" => String(j.job), "v1_key" => String(j.v1_key), "label" => "DIAGNOSTIC_ONLY_NOT_SCORE_BEARING",
                           "numerics" => Dict(string(f) => getfield(n, f) for f in keys(n)), "duration_factor" => d,
                           "cells_factor" => k, "hallthruster_commit" => rev, "julia_version" => string(VERSION),
                           "driver_sha256" => driver_sha, "a7_numerics_sha256" => lib_sha,
                           "threads_blas" => get(ENV, "OPENBLAS_NUM_THREADS", nothing), "utc_start" => string(Dates.now(Dates.UTC)))
    try
        r, sol = a7_run(c, n)
        merge!(rec, r)
        if sol.retcode == :success
            rec["thrust_avgstate_second_half_N"] = het.thrust(het.time_average(sol, n.duration_s / 2))[1]
        end
    catch err
        rec["retcode"] = "bridge_error"; rec["error"] = sprint(showerror, err)
    end
    LAST_SOL[] = nothing
    open(out_path, "a") do io
        JSON3.write(io, rec); println(io)
    end
    println(j.job, "  ", get(rec, "retcode", "?"), "  ", round(get(rec, "wall_s", 0.0); digits = 1), " s")
    flush(stdout)
    GC.gc()
end
