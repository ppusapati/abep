# BLIND state-envelope audit for the N^2+ -> N^3+ exclusion (owner decision 2026-09-26). Runs every P5-N2 operating point
# x the 9 SGB screening candidates x the 4 primary chemistry configs with ALL measured targets removed, and records only
# chemistry-state quantities, per saved frame of the averaging window:
#   max_cells n(N^2+)/n(N2);
#   F_ion = R(N^2+ -> N^3+) / (sum of all ionizing electron-impact rates + R3), reaction-weighted over cells (and its per-frame max);
#   F_S  = R3 / (N^2+ production: N2 -> N^2+ + N  plus  N^+ -> N^2+).
#   and (v2) direct N -> N^2+ (Hahn, Muller & Savin 2017 bound table): F_ion_direct, F_S_direct (share of N^2+ production),
#   and the reaction-weighted atomic fraction n_N / n_N2;
#   and (v3) molecular N2^2+: sequential N2+ -> N2^2+ (Tabata 2006 n2-69 fit to Bahati 2001) plus direct N2 -> N2^2+
#   (nominal 1 %-of-total and loose-upper envelopes), as shares of positive-ion production;
#   and (v4) the two N2^2+ routes separately, F_S of N2+ destruction by the sequential route, the sequential share of N2^2+
#   production, and every rate file whose activity extends beyond its validity limit.
# No I_d, thrust or fit-quality quantity is computed or written. This is NOT P5-N2 validation.
# Optional sharding: ... <out.jsonl> <duration_s> <shard> <nshards> [comma-separated keys to run]
# Region diagnostics: reaction-weighted T_e and axial position z/L of each multiply-charged channel's activity.
# julia --project=hallthruster_bridge hallthruster_bridge/checks/blind_state_envelope.jl <out.jsonl> [duration_s]
include(joinpath(@__DIR__, "..", "bridge_lib.jl"))
check_pin()
out_path = ARGS[1]
dur = length(ARGS) >= 2 ? parse(Float64, ARGS[2]) : 5e-4
base = JSON3.read(read(joinpath(@__DIR__, "..", "cases", "p5_n2.json"), String))
ens = JSON3.read(read(joinpath(@__DIR__, "..", "ensemble", "transport_ensemble_v0.json"), String))
configs = ["n2_n.toml", "n2_n_di_lower.toml", "n2_n_nel_wang.toml", "n2_n_di_lower_nel_wang.toml"]
shard = length(ARGS) >= 4 ? parse(Int, ARGS[3]) : 0
nshards = length(ARGS) >= 4 ? parse(Int, ARGS[4]) : 1
only_keys = length(ARGS) >= 5 ? Set(split(ARGS[5], ",")) : nothing
bt(f) = het.load_rate_coeff_file(joinpath(@__DIR__, "..", "audit", "bound_tables", f), "electron_impact")[2]
kseq = bt("ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.dat")
kdn = bt("ionization_N2_to_N2_Z2plus_nominal.dat"); kdu = bt("ionization_N2_to_N2_Z2plus_upper.dat")
_, kdd = het.load_rate_coeff_file(joinpath(@__DIR__, "..", "audit", "bound_tables", "ionization_N_to_N_Z2plus_hms2017.dat"), "electron_impact")
_, k3 = het.load_rate_coeff_file(joinpath(@__DIR__, "..", "audit", "bound_tables", "ionization_N_Z2plus_to_N_Z3plus_bell1983.dat"), "electron_impact")
done = Set{String}()
isfile(out_path) && for l in eachline(out_path); push!(done, String(JSON3.read(l).key)); end
combos = [(cand, cfg, pt) for cand in ens.screening_candidates for cfg in configs for pt in base.cases]
for (ic, (cand, cfg, pt)) in enumerate(combos)
    (ic - 1) % nshards == shard || continue
    key = "$(cand.ensemble_member_id)|$(cfg)|$(pt.id)"
    key in done && continue
    !isnothing(only_keys) && !(key in only_keys) && continue
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
        n2p_rx = only([r for r in rx if r.file == "ionization_N2_song2023.dat"])     # the only N2+ source
        r = run_case(c, "vacuum")
        rec["retcode"] = r["retcode"]; rec["sustained"] = get(r, "sustained", false)
        if r["retcode"] == "success"
            sol = LAST_SOL[]
            i0 = findfirst(>=(c.average_start_s), sol.t)
            z = collect(sol.grid); dz = [(z[min(i + 1, end)] - z[max(i - 1, 1)]) / (i == 1 || i == length(z) ? 1 : 2) for i in eachindex(z)]
            ratio_max = 0.0; R3t = 0.0; Riont = 0.0; Pz2t = 0.0; Fion_frame_max = 0.0; Te_at_ratio = 0.0
            Rddt = 0.0; Fdd_frame_max = 0.0; xN_w = 0.0; w_t = 0.0
            Rn2pt = 0.0; Rseqt = 0.0; Rdnt = 0.0; Rdut = 0.0; Fm_nom_frame_max = 0.0; Fm_up_frame_max = 0.0
            L = c.L_m; rw = Dict(k => zeros(4) for k in ("NZ3", "Ndd", "N2seq", "N2dir"))   # sum R, sum R*Te, sum R*z/L, sum R*n_e
            for f in sol.frames[i0:end]
                nN2 = reactant_density(f, :N2, 0); nZ2 = reactant_density(f, :N, 2); nN = reactant_density(f, :N, 0)
                nN2p = reactant_density(f, :N2, 1)
                dens_ion = [reactant_density(f, q.target, q.Z) for q in ion_rx]      # one lookup per frame
                dens_z2 = [reactant_density(f, q.target, q.Z) for q in prod_Z2]
                Rn2p = 0.0; R3 = 0.0; Rion = 0.0; Pz2 = 0.0; Rdd = 0.0; Rseq = 0.0; Rdn = 0.0; Rdu = 0.0
                for i in eachindex(z)
                    rr = nZ2[i] / max(nN2[i], 1.0)
                    rr > ratio_max && (ratio_max = rr; Te_at_ratio = f.Tev[i])
                    eps = 1.5 * f.Tev[i]; w = f.ne[i] * dz[i]
                    R3 += w * nZ2[i] * rate_at(k3, eps)
                    Rdd += w * nN[i] * rate_at(kdd, eps)
                    Rseq += w * nN2p[i] * rate_at(kseq, eps)
                    Rn2p += w * nN2[i] * rate_at(n2p_rx.k, eps)
                    Rdn += w * nN2[i] * rate_at(kdn, eps); Rdu += w * nN2[i] * rate_at(kdu, eps)
                    for (k, r) in (("NZ3", w * nZ2[i] * rate_at(k3, eps)), ("Ndd", w * nN[i] * rate_at(kdd, eps)),
                                   ("N2seq", w * nN2p[i] * rate_at(kseq, eps)), ("N2dir", w * nN2[i] * rate_at(kdn, eps)))
                        rw[k] .+= (r, r * f.Tev[i], r * z[i] / L, r * f.ne[i])
                    end
                    xN_w += w * nN[i]; w_t += w * nN2[i]
                    for (q, n) in zip(ion_rx, dens_ion)
                        Rion += w * n[i] * rate_at(q.k, eps)
                    end
                    for (q, n) in zip(prod_Z2, dens_z2)
                        Pz2 += w * n[i] * rate_at(q.k, eps)
                    end
                end
                Fion_frame_max = max(Fion_frame_max, R3 / (Rion + R3))
                Fdd_frame_max = max(Fdd_frame_max, Rdd / (Rion + Rdd))
                Fm_nom_frame_max = max(Fm_nom_frame_max, (Rseq + Rdn) / (Rion + Rseq + Rdn))
                Fm_up_frame_max = max(Fm_up_frame_max, (Rseq + Rdu) / (Rion + Rseq + Rdu))
                Rn2pt += Rn2p; Rseqt += Rseq; Rdnt += Rdn; Rdut += Rdu
                R3t += R3; Riont += Rion; Pz2t += Pz2; Rddt += Rdd
            end
            rec["max_ratio_NZ2_over_N2"] = ratio_max; rec["Te_at_max_ratio_eV"] = Te_at_ratio
            rec["F_ion_NZ2_to_NZ3"] = R3t / (Riont + R3t); rec["F_ion_frame_max"] = Fion_frame_max
            rec["F_S_NZ2_destruction"] = R3t / Pz2t
            rec["F_ion_N_to_NZ2_direct"] = Rddt / (Riont + Rddt); rec["F_ion_direct_frame_max"] = Fdd_frame_max
            rec["F_S_NZ2_production_direct"] = Rddt / (Pz2t + Rddt)
            rec["xN_ne_weighted"] = xN_w / w_t        # sum(n_e n_N dz) / sum(n_e n_N2 dz)
            rec["F_ion_N2Z2_seq_only"] = Rseqt / (Riont + Rseqt)
            rec["F_ion_N2Z2_nominal"] = (Rseqt + Rdnt) / (Riont + Rseqt + Rdnt)
            rec["F_ion_N2Z2_upper"] = (Rseqt + Rdut) / (Riont + Rseqt + Rdut)
            # (v4) the two N2^2+ routes separately; F_S of N2+ destruction uses N2+ production (= its steady-state loss)
            rec["F_ion_N2Z2_direct_nominal"] = Rdnt / (Riont + Rdnt); rec["F_ion_N2Z2_direct_upper"] = Rdut / (Riont + Rdut)
            rec["F_S_N2p_destruction_seq"] = Rseqt / Rn2pt
            rec["F_S_N2Z2_production_seq_nominal"] = Rseqt / (Rseqt + Rdnt); rec["F_S_N2Z2_production_seq_upper"] = Rseqt / (Rseqt + Rdut)
            rec["F_ion_N2Z2_nominal_frame_max"] = Fm_nom_frame_max; rec["F_ion_N2Z2_upper_frame_max"] = Fm_up_frame_max
            for (k, v) in rw
                v[1] > 0 && (rec["region_$(k)_Te_eV"] = v[2] / v[1]; rec["region_$(k)_z_over_L"] = v[3] / v[1]; rec["region_$(k)_ne_m3"] = v[4] / v[1])
            end
            rec["chemistry_trustworthy"] = r["chemistry_trustworthy"]
            rec["chemistry_files_beyond_limit"] = Dict(String(q["file"]) => q["extrapolated_fraction"] for q in r["chemistry_per_reaction"]
                                                       if !isnothing(q["extrapolated_fraction"]) && q["extrapolated_fraction"] > CHEM_FOUT_TOL)
            for k in ("chemistry_extrapolated_fraction_max", "chemistry_limiting_rate_file", "chemistry_max_mean_energy_active_eV", "converged")
                rec[k] = get(r, k, nothing)
            end
        end
    catch err
        rec["retcode"] = "error"; rec["error"] = sprint(showerror, err)
    end
    open(out_path, "a") do io; println(io, JSON3.write(rec)); end
    println(key, "  ", get(rec, "retcode", "?"), "  ratio_max=", get(rec, "max_ratio_NZ2_over_N2", NaN), "  F_ion=", get(rec, "F_ion_NZ2_to_NZ3", NaN))
end
