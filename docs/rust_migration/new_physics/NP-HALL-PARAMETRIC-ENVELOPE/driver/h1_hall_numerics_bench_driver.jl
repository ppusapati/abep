# Hall numerics investigation (A9.36), Phase 1 H-BENCH driver. DIAGNOSTIC ONLY, never score-bearing.
# Runs HallThruster.jl's own SPT-100 tutorial regression case (test/regression/spt100_tutorial.json of the pinned v0.23.1:
# SPT-100 geometry and B, domain 0-80 mm, 300 V, Xe 5 mg/s single charge, default TwoZoneBohm(1/160, 1/16)) at the
# bridge numerics ladder (cells, dt, duration, num_save given per job) and writes the same per-frame series as the H-1
# diagnostic driver.
#   julia --project=hallthruster_bridge <this> <jobs.json> <out.jsonl> <shard> <nshards>
include(joinpath(@__DIR__, "..", "..", "..", "..", "..", "hallthruster_bridge", "bridge_lib.jl"))
using Dates
rev = check_pin()
jobs = JSON3.read(read(ARGS[1], String))
out_path, shard, nshards = ARGS[2], parse(Int, ARGS[3]), parse(Int, ARGS[4])
done = Set{String}()
isfile(out_path) && for l in eachline(out_path); isempty(strip(l)) || push!(done, String(JSON3.read(l).job)); end
for (i, j) in enumerate(jobs)
    (i - 1) % nshards == shard || continue
    String(j.job) in done && continue
    config = het.Config(thruster = het.SPT_100, domain = (0.0, 0.08), discharge_voltage = 300.0,
                        propellants = [het.Propellant("Xe", flow_rate_kg_s = 5e-6, allowed_charges = [1])])
    sp = het.SimParams(grid = het.EvenGrid(j.cells), dt = j.dt_s, duration = j.duration_s, num_save = j.num_save,
                       verbose = false, print_errors = false)
    rec = Dict{String,Any}("job" => String(j.job), "label" => "DIAGNOSTIC_ONLY_NOT_SCORE_BEARING", "bench" => "spt100_tutorial",
                           "cells" => j.cells, "dt_s" => j.dt_s, "duration_s" => j.duration_s, "num_save" => j.num_save,
                           "hallthruster_commit" => rev, "julia_version" => string(VERSION), "utc_start" => string(Dates.now(Dates.UTC)))
    t0 = time()
    sol = het.run_simulation(config, sp)
    nf = length(sol.frames)
    rec["retcode"] = string(sol.retcode); rec["wall_s"] = time() - t0; rec["n_frames"] = nf
    rec["series_t_s"] = sol.t[1:nf]
    rec["series_Id_A"] = [f.discharge_current[] for f in sol.frames]
    rec["series_thrust_N"] = [het.thrust(sol, k) for k in 1:nf]
    rec["series_dt_limit_s"] = [f.dt[] for f in sol.frames]
    sol.retcode == :success && (rec["thrust_avgstate_second_half_N"] = het.thrust(het.time_average(sol, j.duration_s / 2))[1])
    open(out_path, "a") do io
        JSON3.write(io, rec); println(io)
    end
    println(j.job, "  ", rec["retcode"], "  ", round(rec["wall_s"]; digits = 1), " s")
    flush(stdout)
    GC.gc()
end
