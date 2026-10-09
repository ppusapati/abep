# hall_air_rp1_v1 run library (NP-HALL-PARAMETRIC-ENVELOPE addendum A9-LP). PARAMETRIC / NOT_VALIDATED.
# Physics = hallthruster_bridge/air_bridge_lib.jl run_case_air (same Config: geometry, FE B(z) registration, ScaledGaussianBohm
# transport, AIR propellant config, per-species feed, vacuum mode, solver defaults otherwise). Numerics and observables =
# addendum A7 (hallthruster_bridge/a7_numerics.jl): a7_simparams and a7_window_stats are evaluated from that file unchanged
# (only its include of bridge_lib.jl is skipped, because air_bridge_lib.jl has already included it). Raw values only;
# status and convergence are applied by aggregate.jl.
const BRIDGE = normpath(joinpath(@__DIR__, "..", "..", "..", "hallthruster_bridge"))
include(joinpath(BRIDGE, "air_bridge_lib.jl"))
let path = joinpath(BRIDGE, "a7_numerics.jl"), src = read(path, String)
    inc = "include(joinpath(@__DIR__, \"bridge_lib.jl\"))\n"
    count(inc, src) == 1 || error("a7_numerics.jl: expected exactly one include of bridge_lib.jl")
    include_string(Main, replace(src, inc => ""), path)
end

const AMU = 1.66053906660e-27
const E_CHARGE = 1.602176634e-19
const G0 = 9.80665
const SPECIES_MASS_AMU = Dict("N2" => 28.0134, "N" => 14.0067, "O2" => 31.998, "O" => 15.999)  # air_nominal.toml masses

# Config of air_bridge_lib.run_case_air for case c, with the A7 numerics block of the case.
function air_a7_config(c)
    haskey(c, :B_profile) && haskey(c, :feed) && haskey(c, :propellant_config) || error("case $(c.case_id): incomplete AIR case")
    c.transport.model == "ScaledGaussianBohm" || error("case $(c.case_id): transport is not ScaledGaussianBohm")
    geom = het.Geometry1D(channel_length = Float64(c.L_m), inner_radius = Float64(c.r_in_m), outer_radius = Float64(c.r_out_m))
    bfield, bscale, zpeak = measured_bfield(c)
    thruster = het.Thruster(name = c.thruster, geometry = geom, magnetic_field = bfield)
    tr = c.transport
    nm = c.numerics
    config = het.Config(; thruster, domain = (0.0, Float64(c.domain_m)), discharge_voltage = Float64(c.Vd),
                        anom_model = het.ScaledGaussianBohm(Float64(tr.anom_scale), Float64(tr.barrier_scale), Float64(tr.width), Float64(tr.center)),
                        propellant_config = joinpath(BRIDGE, c.propellant_config),
                        reaction_rate_directories = String[joinpath(BRIDGE, c.rate_dir)],
                        propellants = air_propellants(c), reconstruct = Bool(nm.reconstruct),
                        implicit_energy = Float64(nm.implicit_energy))
    return config, bfield, bscale, zpeak
end

function level_numerics(c, level)
    lv = c.levels[Symbol(level)]
    nm = c.numerics
    return (cells = Int(lv.cells), dt_s = Float64(lv.dt_s), duration_s = Float64(c.duration_s), num_save = Int(c.num_save),
            CFL = Float64(nm.CFL), min_dt_s = Float64(nm.min_dt_s), max_dt_s = Float64(nm.max_dt_s),
            max_small_steps = Int(nm.max_small_steps), adaptive = Bool(nm.adaptive))
end

# First non-finite value in the saved frames (frame time, variable, cell, z), or nothing.
function first_nonfinite(sol, nvalid)
    z = sol.grid
    for k in 1:nvalid
        f = sol.frames[k]
        fields = Pair{String,Vector{Float64}}["ne" => f.ne, "Tev" => f.Tev, "potential" => f.potential, "ue" => f.ue]
        for (s, nt) in f.neutrals
            push!(fields, "n[$(s)]" => nt.n, "u[$(s)]" => nt.u)
        end
        for (s, ions) in f.ions, ion in ions
            push!(fields, "n[$(s)$(ion.Z)+]" => ion.n, "u[$(s)$(ion.Z)+]" => ion.u)
        end
        for (name, v) in fields
            i = findfirst(!isfinite, v)
            isnothing(i) || return Dict("frame" => k, "t_s" => sol.t[k], "variable" => name, "cell" => i, "z_m" => z[i],
                                        "z_over_L" => z[i] / sol.config.thruster.geometry.channel_length)
        end
        isfinite(f.discharge_current[]) || return Dict("frame" => k, "t_s" => sol.t[k], "variable" => "discharge_current")
    end
    return nothing
end

# Collapse diagnostics over the saved series (pure function): time I_d first falls below 1 % of its running maximum after
# the first 5 % of the run, last-frame I_d / series maximum, last-frame n_e,min and T_e,max.
function collapse_diagnostics(t, Id, ne_min, Te_max)
    tmax = t[end]
    run_max, t_drop = 0.0, nothing
    for k in eachindex(t)
        isfinite(Id[k]) || continue
        run_max = max(run_max, Id[k])
        if t_drop === nothing && t[k] > 0.05 * tmax && Id[k] < 0.01 * run_max
            t_drop = t[k]
        end
    end
    imax = maximum(x -> isfinite(x) ? x : -Inf, Id)
    return Dict{String,Any}("Id_series_max_A" => imax, "Id_last_frame_A" => Id[end],
                            "Id_last_over_max" => imax > 0 ? Id[end] / imax : nothing,
                            "t_Id_below_1pct_of_running_max_s" => t_drop,
                            "ne_min_last_frame_m3" => ne_min[end], "Te_max_last_frame_eV" => Te_max[end],
                            "collapse_detected" => (imax > 0 && isfinite(Id[end]) && Id[end] < 0.01 * imax) || ne_min[end] < 1e12 ||
                                                   !isfinite(Id[end]))
end

# Window statistics of a frame series with the A7 batch count, plus the oscillation numbers of the series.
function series_stats(t, y, t0)
    s = a7_window_stats(t, y, t0; nb = A7_NB)
    i0 = findfirst(>=(t0 * (1 - 1e-12)), t)
    f, amp = dominant_frequency(t[i0:end], y[i0:end])
    return Dict{String,Any}("mean" => s.mean, "se_batch" => s.se_batch, "half_means" => [s.mean_first_half, s.mean_second_half],
                            "rms_rel" => s.rms_rel, "pp_rel" => s.mean != 0 ? (s.max - s.min) / abs(s.mean) : nothing,
                            "min" => s.min, "max" => s.max, "rms_abs" => s.rms_rel * abs(s.mean),
                            "f_dominant_Hz" => f, "amp_dominant" => amp, "tau_int_samples" => s.tau_int_samples,
                            "se_acf" => s.se_acf, "n_samples" => s.n)
end

# One case at one A7 level. Returns the raw run record (no status).
function air_a7_record(c, level)
    n = level_numerics(c, level)
    config, bfield, bscale, zpeak = air_a7_config(c)
    sp = a7_simparams(n)
    t0 = time()
    sol = het.run_simulation(config, sp)
    wall = time() - t0
    nf = length(sol.frames)
    tt = sol.t[1:nf]
    nvalid = something(findlast(>(0.0), tt), 1)
    t = tt[1:nvalid]
    frames = sol.frames[1:nvalid]
    Id = [f.discharge_current[] for f in frames]
    ne_min = [minimum(f.ne) for f in frames]
    Te_max = [maximum(f.Tev) for f in frames]
    r = Dict{String,Any}("level" => level, "cells" => n.cells, "dt_s" => n.dt_s, "dx_mm" => 1e3 * c.domain_m / n.cells,
                         "duration_s" => n.duration_s, "average_start_s" => Float64(c.average_start_s), "num_save" => n.num_save,
                         "retcode" => string(sol.retcode), "converged" => sol.retcode == :success, "wall_s" => wall,
                         "n_frames_saved" => nvalid, "t_last_frame_s" => t[end],
                         "transport" => "$(config.anom_model), transition_length $(config.transition_length) m",
                         "B_scale" => bscale, "B_max_T" => maximum(bfield.B), "B_peak_minus_exit_m" => zpeak - c.L_m,
                         "apply_thrust_divergence_correction" => config.apply_thrust_divergence_correction,
                         "ion_wall_losses" => config.ion_wall_losses,
                         "feed_used" => [Dict("species" => String(p.gas.formula), "flow_rate_kg_s" => p.flow_rate_kg_s,
                                              "allowed_charges" => collect(p.allowed_charges)) for p in config.propellants])
    r["dt_limit_min_s"] = nvalid > 1 ? minimum(f.dt[] for f in frames[2:end]) : nothing
    r["collapse"] = collapse_diagnostics(t, Id, ne_min, Te_max)
    r["first_nonfinite"] = first_nonfinite(sol, nvalid)
    if sol.retcode != :success
        r["error"] = string(sol.error)
        r["finite"] = false
        return r
    end
    T = [het.thrust(sol, i) for i in 1:nvalid]
    Ii = [het.ion_current(sol, i) for i in 1:nvalid]
    tw = Float64(c.average_start_s)
    i0 = findfirst(>=(tw * (1 - 1e-12)), t)
    r["window_start_s"] = tw
    r["thrust"] = series_stats(t, T, tw)
    r["discharge_current"] = series_stats(t, Id, tw)
    r["ion_current"] = series_stats(t, Ii, tw)
    # Efficiency decomposition: time-means of the solver's per-frame definitions over the window.
    for (k, fn) in ("anode_eff_framemean" => het.anode_eff, "mass_eff" => het.mass_eff, "current_eff" => het.current_eff,
                    "voltage_eff" => het.voltage_eff, "divergence_eff" => het.divergence_eff)
        v = [fn(sol, i) for i in i0:nvalid]
        r[k] = sum(v) / length(v)
    end
    avg = het.time_average(sol, i0)
    r["thrust_avgstate_N"] = het.thrust(avg)[1]
    fr = avg.frames[1]
    r["Te_max_eV"] = maximum(fr.Tev)
    r["ne_max_m3"] = maximum(fr.ne)
    exit_flux = Dict(sym => sum(ion.nu[end] for ion in ions) for (sym, ions) in fr.ions)
    total_exit = sum(values(exit_flux))
    r["ion_exit_flux_fraction_by_gas"] = Dict(String(sym) => v / total_exit for (sym, v) in exit_flux)
    r["sustained_v1"] = r["discharge_current"]["min"] > SCHEMA.conventions.sustained_min_Id_fraction * r["discharge_current"]["mean"]
    r["finite"] = all(isfinite, Id) && all(isfinite, T) && isfinite(r["thrust"]["mean"]) && isfinite(r["discharge_current"]["mean"]) &&
                  isfinite(r["thrust"]["se_batch"]) && isfinite(r["discharge_current"]["se_batch"])
    # AIR model domain (addendum A1: DOM-AIR-01 table limits, DOM-AIR-02 audited 45 eV), per saved frame over the window.
    chem = chemistry_validity(sol, c, i0)
    resolved = [x for x in chem if !isnothing(x.fout)]
    r["chemistry_unresolved_rate_files"] = [x.file for x in chem if isnothing(x.fout)]
    r["chemistry_extrapolated_fraction_max"] = isempty(resolved) ? nothing : maximum(x.fout for x in resolved)
    r["chemistry_limiting_rate_file"] = isempty(resolved) ? nothing : argmax(x -> (x.fout, x.eps_active / x.limit), resolved).file
    r["chemistry_max_mean_energy_active_eV"] = maximum(x.eps_active for x in chem)
    dom = air_domain_activity(sol, c, i0)
    worst = argmax(x -> x.fout, dom)
    r["audit_domain_fraction_max"] = worst.fout
    r["audit_domain_limiting_rate_file"] = worst.file
    return r
end

# Equivalent full-single-ionization current of the feed, e * sum(mdot_s / m_s) [A] (EXTINCT reference, addendum A9-LP).
feed_current_equiv_A(c) = E_CHARGE * sum(Float64(f.flow_rate_kg_s) / (SPECIES_MASS_AMU[String(f.species)] * AMU) for f in c.feed)

# JSON has no NaN / Inf: a non-finite number is written as the string "NaN", "Inf" or "-Inf" (never silently dropped).
json_safe(x::AbstractFloat) = isfinite(x) ? x : string(x)
json_safe(x::AbstractDict) = Dict{String,Any}(string(k) => json_safe(v) for (k, v) in x)
json_safe(x::AbstractVector) = [json_safe(v) for v in x]
json_safe(x::Tuple) = [json_safe(v) for v in x]
json_safe(x) = x
