# P5-N2 no-retuning validation campaign driver (pre-registration prereg/p5_n2_validation_criteria_v1.json, merged in PR #27).
# Runs  screening candidate x chemistry config x case (cases/p5_n2.json: 5 points x 3 registrations x 2 coil shapes)  in ONE
# comparison mode per invocation, and records raw observables only. It never scores: status, verdicts and residuals come from
# scripts/score_p5_n2_campaign.py, which implements the frozen rules. Nothing here is tuned per case, point or result.
#   julia --project=hallthruster_bridge hallthruster_bridge/campaign/p5_n2_campaign.jl <out.jsonl> <vacuum|facility> \
#         [shard nshards] [chemistry configs, comma-separated; default = the four mandatory]
# Refuses to run unless every file in prereg/p5_n2_prereg_lock_v1.json and every chemistry config pinned in the criteria
# matches its sha256 (so a run can only ever use the pre-registered inputs). Resumable (skips keys already in out.jsonl).
# The log prints run keys and return codes only - no current, thrust or residual.
# P5N2_SMOKE=1: 2 us construction check with the measured targets stripped; records carry "smoke": true and are never scored.
include(joinpath(@__DIR__, "..", "bridge_lib.jl"))
using SHA
rev = check_pin()
const BR = joinpath(@__DIR__, "..")
sha(p) = bytes2hex(open(sha256, p))
crit = JSON3.read(read(joinpath(BR, "prereg", "p5_n2_validation_criteria_v1.json"), String))
lock = JSON3.read(read(joinpath(BR, "prereg", "p5_n2_prereg_lock_v1.json"), String))
for (f, h) in pairs(lock.files)
    sha(joinpath(BR, String(f))) == h || error("pre-registration lock mismatch: $(f)")
end
for (f, h) in pairs(crit.inputs_pinned.chemistry_configs_sha256)
    sha(joinpath(BR, "propellants", String(f))) == h || error("pinned chemistry config changed: $(f)")
end
out_path, mode = ARGS[1], ARGS[2]
mode in ("vacuum", "facility") || error("mode must be vacuum or facility")
shard = length(ARGS) >= 4 ? parse(Int, ARGS[3]) : 0
nshards = length(ARGS) >= 4 ? parse(Int, ARGS[4]) : 1
chems = length(ARGS) >= 5 ? String.(split(ARGS[5], ",")) : String.(crit.mandatory_chemistry)
for ch in chems
    haskey(crit.inputs_pinned.chemistry_configs_sha256, Symbol(ch)) || error("chemistry config not pre-registered: $(ch)")
end
cases = JSON3.read(read(joinpath(BR, "cases", "p5_n2.json"), String)).cases
cands = JSON3.read(read(joinpath(BR, "ensemble", "transport_ensemble_v0.json"), String)).screening_candidates
done = Set{String}()
isfile(out_path) && for l in eachline(out_path); push!(done, String(JSON3.read(l).key)); end
jobs = [(cand, ch, c) for cand in cands for ch in chems for c in cases]
lock_sha = sha(joinpath(BR, "prereg", "p5_n2_prereg_lock_v1.json"))
for (ij, (cand, ch, c0)) in enumerate(jobs)
    (ij - 1) % nshards == shard || continue
    key = "$(cand.ensemble_member_id)|$(ch)|$(c0.id)|$(mode)"
    key in done && continue
    tp = cand.transport_parameters
    smoke = get(ENV, "P5N2_SMOKE", "0") == "1"         # construction check only: 2 us, targets stripped, never scored
    c = Dict{Symbol,Any}(k => v for (k, v) in pairs(c0) if !(smoke && k == :measured))
    smoke && (c[:duration_s] = 2e-6; c[:average_start_s] = 1e-6)
    c[:id] = key; c[:propellant_config] = "propellants/$(ch)"
    c[:transport] = (model="ScaledGaussianBohm", anom_scale=tp.anom_scale, barrier_scale=tp.barrier_scale,
                     center=tp.center_L, width=tp.width_L)
    c = (; c...)
    rec = Dict{String,Any}("key" => key, "candidate" => String(cand.ensemble_member_id), "chemistry" => ch, "case" => String(c0.id),
                           "point" => String(c0.point), "registration" => String(c0.registration),
                           "coil_shape" => String(c0.coil_shape), "mode" => mode, "prereg_lock_sha256" => lock_sha,
                           "hallthruster_commit" => rev, "smoke" => smoke)
    try
        LAST_SOL[] = nothing
        r = run_case(c, mode)
        for k in ("retcode", "converged", "t_end_s", "discharge_current_A", "thrust_N", "Id_rms_rel", "Id_pp_rel",
                  "Id_f_dominant_Hz", "Id_min_A", "Id_max_A", "sustained", "ion_current_A", "Id_target_A", "Id_target_kind",
                  "T_target_N", "T_target_kind", "chemistry_unresolved_rate_files", "chemistry_per_reaction",
                  "model_facility_ingestion", "B_max_T", "Te_max_eV", "error")
            haskey(r, k) && (rec[k] = r[k])
        end
        sol = LAST_SOL[]
        if r["retcode"] == "success" && !isnothing(sol)
            Id_t = het.discharge_current(sol)
            tf = sol.t[end]
            sel = findall(t -> t >= 0.9 * tf, sol.t)                         # O1: final 10 % of the simulated time
            rec["Id_final10_samples_A"] = Id_t[sel]
            rec["finite"] = all(isfinite, Id_t) && isfinite(r["thrust_N"]) && isfinite(r["discharge_current_A"])
            avg = het.time_average(sol, c.average_start_s)
            fr = avg.frames[1]
            outlet = Dict{String,Any}()
            for (sym, ions) in fr.ions, ion in ions                          # O5: outlet velocity and flux per species
                outlet["$(sym)_Z$(ion.Z)"] = Dict("Z" => ion.Z, "u_ms" => ion.u[end], "n_m3" => ion.n[end], "flux_m2s" => ion.nu[end])
            end
            rec["outlet_ions"] = outlet
        end
    catch err
        rec["retcode"] = "error"; rec["error"] = sprint(showerror, err)
    end
    open(out_path, "a") do io
        JSON3.write(io, rec); println(io)
    end
    println(key, "  ", get(rec, "retcode", "?"))
    flush(stdout)
end
