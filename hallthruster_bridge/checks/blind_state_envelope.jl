# BLIND state-envelope audit for the N^2+ -> N^3+ exclusion (owner decision 2026-09-26). Runs every P5-N2 operating point
# x the 9 SGB screening candidates x the 4 primary chemistry configs with ALL measured targets removed, and records only
# chemistry-state quantities, per saved frame of the averaging window:
#   max_cells n(N^2+)/n(N2);
#   F_ion = R(N^2+ -> N^3+) / (sum of all ionizing electron-impact rates + R3), reaction-weighted over cells (and its per-frame max);
#   F_S  = R3 / (N^2+ production: N2 -> N^2+ + N  plus  N^+ -> N^2+).
# No I_d, thrust or fit-quality quantity is computed or written. This is NOT P5-N2 validation.
# julia --project=hallthruster_bridge hallthruster_bridge/checks/blind_state_envelope.jl <out.jsonl> [duration_s]
include(joinpath(@__DIR__, "..", "bridge_lib.jl"))
check_pin()
out_path = ARGS[1]
dur = length(ARGS) >= 2 ? parse(Float64, ARGS[2]) : 5e-4
base = JSON3.read(read(joinpath(@__DIR__, "..", "cases", "p5_n2.json"), String))
ens = JSON3.read(read(joinpath(@__DIR__, "..", "ensemble", "transport_ensemble_v0.json"), String))
configs = ["n2_n.toml", "n2_n_di_lower.toml", "n2_n_nel_wang.toml", "n2_n_di_lower_nel_wang.toml"]
_, k3 = het.load_rate_coeff_file(joinpath(@__DIR__, "..", "audit", "bound_tables", "ionization_N_Z2plus_to_N_Z3plus_bell1983.dat"), "electron_impact")
done = Set{String}()
isfile(out_path) && for l in eachline(out_path); push!(done, String(JSON3.read(l).key)); end
for cand in ens.screening_candidates, cfg in configs, pt in base.cases
    key = "$(cand.ensemble_member_id)|$(cfg)|$(pt.id)"
    key in done && continue
    tp = cand.transport_parameters
    c = Dict{Symbol,Any}(k => v for (k, v) in pairs(pt) if k != :measured)     # measured targets removed
    c[:id] = key; c[:propellant_config] = "propellants/$(cfg)"; c[:duration_s] = dur; c[:average_start_s] = dur / 2
    c[:transport] = (model="ScaledGaussianBohm", anom_scale=tp.anom_scale, barrier_scale=tp.barrier_scale,
                     center=tp.center_L, width=tp.width_L)
    c = (; c...)
    rec = Dict{String,Any}("key" => key, "candidate" => cand.ensemble_member_id, "config" => cfg, "point" => pt.id)
    try
        rx = chemistry_reactions(c)
        ion_rx = [r for r in rx if r.file != "" && occursin(r"(ionization|dissociative_ionization)", r.file)]
        prod_Z2 = [r for r in rx if occursin("N_Z2plus", r.file)]
        r = run_case(c, "vacuum")
        rec["retcode"] = r["retcode"]; rec["sustained"] = get(r, "sustained", false)
        if r["retcode"] == "success"
            sol = LAST_SOL[]
            i0 = findfirst(>=(c.average_start_s), sol.t)
            z = collect(sol.grid); dz = [(z[min(i + 1, end)] - z[max(i - 1, 1)]) / (i == 1 || i == length(z) ? 1 : 2) for i in eachindex(z)]
            ratio_max = 0.0; R3t = 0.0; Riont = 0.0; Pz2t = 0.0; Fion_frame_max = 0.0; Te_at_ratio = 0.0
            for f in sol.frames[i0:end]
                nN2 = reactant_density(f, :N2, 0); nZ2 = reactant_density(f, :N, 2)
                R3 = 0.0; Rion = 0.0; Pz2 = 0.0
                for i in eachindex(z)
                    rr = nZ2[i] / max(nN2[i], 1.0)
                    rr > ratio_max && (ratio_max = rr; Te_at_ratio = f.Tev[i])
                    eps = 1.5 * f.Tev[i]
                    R3 += f.ne[i] * nZ2[i] * rate_at(k3, eps) * dz[i]
                    for q in ion_rx
                        Rion += f.ne[i] * reactant_density(f, q.target, q.Z)[i] * rate_at(q.k, eps) * dz[i]
                    end
                    for q in prod_Z2
                        Pz2 += f.ne[i] * reactant_density(f, q.target, q.Z)[i] * rate_at(q.k, eps) * dz[i]
                    end
                end
                Fion_frame_max = max(Fion_frame_max, R3 / (Rion + R3))
                R3t += R3; Riont += Rion; Pz2t += Pz2
            end
            rec["max_ratio_NZ2_over_N2"] = ratio_max; rec["Te_at_max_ratio_eV"] = Te_at_ratio
            rec["F_ion_NZ2_to_NZ3"] = R3t / (Riont + R3t); rec["F_ion_frame_max"] = Fion_frame_max
            rec["F_S_NZ2_destruction"] = R3t / Pz2t
            rec["chemistry_trustworthy"] = r["chemistry_trustworthy"]
        end
    catch err
        rec["retcode"] = "error"; rec["error"] = sprint(showerror, err)
    end
    open(out_path, "a") do io; println(io, JSON3.write(rec)); end
    println(key, "  ", get(rec, "retcode", "?"), "  ratio_max=", get(rec, "max_ratio_NZ2_over_N2", NaN), "  F_ion=", get(rec, "F_ion_NZ2_to_NZ3", NaN))
end
