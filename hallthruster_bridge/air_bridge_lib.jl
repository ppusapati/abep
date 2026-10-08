# AIR (multi-species feed) runs for HallThruster.jl v0.23.1: NP-HALL-CHEM-AIR (capability audit L-07; addendum 01 NI-01).
# bridge_lib.jl run_case feeds only N2 when a propellant_config is given, and bridge_lib.jl is pinned by
# NP-HALL-PARAMETRIC-ENVELOPE v1, so the AIR run function lives in this separate file. It reuses the bridge helpers unchanged
# (check_pin, measured_bfield, chemistry_reactions, chemistry_activity, chemistry_validity, wall_ion_metrics,
# dominant_frequency, schema_missing, reactant_term, reactant_density, rate_at) and adds the audited-domain check DOM-AIR-02.
# No status, threshold or verdict is computed here. Written without a Julia installation in the authoring container
# (julialang hosts blocked): the first run on a machine with the pinned stack is its first execution.
include(joinpath(@__DIR__, "bridge_lib.jl"))

const AIR_AUDIT_DOMAIN_EV = 45.0   # NP-HALL-CHEM-AIR DOM-AIR-02: audited mean electron energy 3/2 T_e

# NI-01: one Propellant per configured neutral, with the case's anode flow, inlet velocity and temperature.
air_propellants(c) = [het.Propellant(String(f.species); flow_rate_kg_s=Float64(f.flow_rate_kg_s),
                                     velocity_m_s=Float64(f.velocity_m_s), temperature_K=Float64(f.temperature_K))
                      for f in c.feed]

# DOM-AIR-02: per reaction, the reaction-weighted activity share at 3/2 T_e above 45 eV over the averaging window, with the
# same per-frame sums as the bridge's DOM-AIR-01 (chemistry_activity with every limit set to 45 eV).
function air_domain_activity(sol, c, i0)
    rx = [merge(r, (limit=AIR_AUDIT_DOMAIN_EV,)) for r in chemistry_reactions(c)]
    return chemistry_activity(sol.frames[i0:end], collect(sol.grid), rx)
end

# One AIR case in vacuum mode (flight; no facility ingestion). Raw observables only, the keys of run_case plus the feed and
# the DOM-AIR-02 activity. A case without a measured B profile, a feed or the registered transport family is refused.
function run_case_air(c)
    haskey(c, :B_profile) || error("case $(c.id): AIR runs use a registered measured B profile")
    haskey(c, :feed) || error("case $(c.id): AIR case without a feed (NI-01)")
    haskey(c, :propellant_config) && haskey(c, :rate_dir) || error("case $(c.id): AIR case without a propellant configuration")
    geom = het.Geometry1D(channel_length=c.L_m, inner_radius=c.r_in_m, outer_radius=c.r_out_m)
    bfield, bscale, zpeak = measured_bfield(c)
    thruster = het.Thruster(name=c.thruster, geometry=geom, magnetic_field=bfield)
    tr = c.transport
    tr.model == "ScaledGaussianBohm" || error("case $(c.id): AIR runs use the registered ScaledGaussianBohm transport only")
    config = het.Config(; thruster=thruster, domain=(0.0, c.domain_m), discharge_voltage=c.Vd,
                        anom_model=het.ScaledGaussianBohm(tr.anom_scale, tr.barrier_scale, tr.width, tr.center),
                        propellant_config=joinpath(@__DIR__, c.propellant_config),
                        reaction_rate_directories=String[joinpath(@__DIR__, c.rate_dir)],
                        propellants=air_propellants(c))
    sp = het.SimParams(grid=het.EvenGrid(c.cells), dt=c.dt_s, duration=c.duration_s, verbose=false)
    t0 = time()
    sol = het.run_simulation(config, sp)
    LAST_SOL[] = sol
    out = Dict{String,Any}("id" => "$(c.id)/vacuum", "case_id" => c.id, "comparison_mode" => "vacuum",
                           "retcode" => string(sol.retcode), "wall_s" => time() - t0, "t_end_s" => sol.t[end],
                           "converged" => sol.retcode == :success, "model_facility_ingestion" => false)
    out["transport"] = "$(config.anom_model), transition_length $(config.transition_length) m"
    out["B_scale"] = bscale
    out["B_max_T"] = maximum(bfield.B)
    out["B_peak_minus_exit_m"] = zpeak - c.L_m
    out["feed_used"] = [Dict("species" => String(p.gas.formula), "flow_rate_kg_s" => p.flow_rate_kg_s,
                             "allowed_charges" => collect(p.allowed_charges)) for p in config.propellants]
    if sol.retcode != :success
        out["error"] = sol.error
        return out
    end

    avg = het.time_average(sol, c.average_start_s)
    Id_t = het.discharge_current(sol)
    i0 = findfirst(>=(c.average_start_s), sol.t)
    tail = Id_t[i0:end]
    Id = het.discharge_current(avg)[1]
    out["discharge_current_A"] = Id
    out["discharge_power_W"] = Id * c.Vd
    out["thrust_N"] = het.thrust(avg)[1]
    out["Id_pp_rel"] = (maximum(tail) - minimum(tail)) / Id
    out["Id_rms_rel"] = sqrt(sum(abs2, tail .- Id) / length(tail)) / Id
    out["Id_min_A"], out["Id_max_A"] = minimum(tail), maximum(tail)
    out["Id_f_dominant_Hz"], out["Id_amp_dominant_A"] = dominant_frequency(sol.t[i0:end], tail)
    out["quasi_steady"] = out["Id_rms_rel"] < 0.5
    out["sustained"] = minimum(tail) > SCHEMA.conventions.sustained_min_Id_fraction * Id
    out["finite"] = all(isfinite, Id_t) && isfinite(out["thrust_N"]) && isfinite(Id)
    out["ion_current_A"] = het.ion_current(avg)[1]
    for f in (:anode_eff, :mass_eff, :voltage_eff, :current_eff, :divergence_eff)
        out[string(f)] = getfield(het, f)(avg)[1]
    end
    wall, wall_basis = wall_ion_metrics(sol, config, i0)
    out["wall_ion_basis"] = wall_basis
    if !isnothing(wall)
        out["wall_ion_flux_m2s"], out["wall_ion_energy_eV"] = wall
    end
    fr = avg.frames[1]
    exit_flux = Dict(sym => sum(ion.nu[end] for ion in ions) for (sym, ions) in fr.ions)
    total_exit = sum(values(exit_flux))
    out["ion_species_fraction_atomic"] = sum(v for (sym, v) in exit_flux if natoms(sym) == 1; init=0.0) / total_exit
    out["ion_exit_flux_fraction_by_gas"] = Dict(String(sym) => v / total_exit for (sym, v) in exit_flux)
    out["Te_max_eV"] = maximum(fr.Tev)
    out["ne_max_m3"] = maximum(fr.ne)
    out["ion_wall_losses"] = config.ion_wall_losses

    chem = chemistry_validity(sol, c, i0)
    resolved = [r for r in chem if !isnothing(r.fout)]
    out["chemistry_unresolved_rate_files"] = [r.file for r in chem if isnothing(r.fout)]
    out["chemistry_per_reaction"] = [Dict("file" => r.file, "max_mean_energy_eV" => r.limit, "extrapolated_fraction" => r.fout,
                                          "max_mean_energy_active_eV" => r.eps_active) for r in chem]
    if !isempty(resolved)
        lim = argmax(r -> (r.fout, r.eps_active / r.limit), resolved)
        out["chemistry_extrapolated_fraction_max"] = lim.fout
        out["chemistry_limiting_rate_file"] = lim.file
        out["chemistry_max_mean_energy_active_eV"] = lim.eps_active
    else
        out["chemistry_extrapolated_fraction_max"] = nothing
        out["chemistry_limiting_rate_file"] = nothing
        out["chemistry_max_mean_energy_active_eV"] = nothing
    end
    out["chemistry_trustworthy"] = out["converged"] && out["sustained"] && isempty(out["chemistry_unresolved_rate_files"]) &&
                                   all(r.fout <= CHEM_FOUT_TOL for r in resolved)
    dom = air_domain_activity(sol, c, i0)
    worst = argmax(r -> r.fout, dom)
    out["audit_domain_fraction_max"] = worst.fout
    out["audit_domain_limiting_rate_file"] = worst.file
    out["air_in_domain"] = out["chemistry_trustworthy"] && worst.fout <= CHEM_FOUT_TOL
    out["schema"] = String(SCHEMA.schema)
    out["schema_missing"] = schema_missing(out)
    out["map_ready"] = isempty(out["schema_missing"])
    return out
end
