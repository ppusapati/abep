# Offline driver: julia --project=hallthruster_bridge hallthruster_bridge/run_cases.jl cases/p5_xenon.json out/p5_xenon.json
# Checked against the installed HallThruster.jl v0.23.1 source (commit in PINNED.toml): Config / Propellant /
# SimParams / Solution / Frame / postprocess.jl. No silent fallbacks: failed runs are reported with converged=false.
using HallThruster: HallThruster as het
using JSON3
using TOML

const PINNED = TOML.parsefile(joinpath(@__DIR__, "PINNED.toml"))["hallthruster"]

# Refuse to run against anything but the pinned commit (the Manifest records the rev Pkg checked out).
function installed_commit()
    manifest = TOML.parsefile(joinpath(@__DIR__, "Manifest.toml"))
    entry = only(manifest["deps"]["HallThruster"])
    return get(entry, "repo-rev", "")
end

function bfield_gaussian(path, L, peak, sig_in, sig_out, zmax)
    open(path, "w") do io
        for z in range(0.0, zmax; length=400)
            s = z <= L ? sig_in : sig_out
            println(io, z, ",", peak * exp(-((z - L) / s)^2))
        end
    end
    return path
end

function run_case(c)
    geom = het.Geometry1D(channel_length=c.L_m, inner_radius=c.r_in_m, outer_radius=c.r_out_m)
    bpath = bfield_gaussian(joinpath(tempdir(), "b_$(c.id).csv"), c.L_m, c.B_max_T, c.B_sigma_in_m, c.B_sigma_out_m, c.domain_m)
    thruster = het.Thruster(name=c.thruster, geometry=geom, magnetic_field=het.load_magnetic_field(bpath))
    kw = Dict{Symbol,Any}(:thruster => thruster, :domain => (0.0, c.domain_m), :discharge_voltage => c.Vd)
    if haskey(c, :propellant_config) && !isempty(c.propellant_config)
        kw[:propellant_config] = c.propellant_config
        kw[:reaction_rate_directories] = String[c.rate_dir]
        kw[:propellants] = [het.Propellant("N2", flow_rate_kg_s=c.mdot_kgps)]
    else
        kw[:propellants] = [het.Propellant(c.gas, flow_rate_kg_s=c.mdot_kgps, allowed_charges=[1])]
    end
    config = het.Config(; kw...)
    sp = het.SimParams(grid=het.EvenGrid(c.cells), dt=c.dt_s, duration=c.duration_s, verbose=false)
    t0 = time()
    sol = het.run_simulation(config, sp)
    out = Dict{String,Any}("id" => c.id, "retcode" => string(sol.retcode), "wall_s" => time() - t0,
                           "t_end_s" => sol.t[end], "converged" => sol.retcode == :success)
    haskey(c, :measured) && (out["measured"] = c.measured)
    if sol.retcode != :success
        out["error"] = sol.error
        return out
    end

    avg = het.time_average(sol, c.average_start_s)
    Id_t = het.discharge_current(sol)
    tail = Id_t[findfirst(>=(c.average_start_s), sol.t):end]
    Id = het.discharge_current(avg)[1]
    out["discharge_current_A"] = Id
    out["discharge_power_W"] = Id * c.Vd
    out["thrust_N"] = het.thrust(avg)[1]
    out["Id_osc_rel"] = (maximum(tail) - minimum(tail)) / Id
    out["Id_rms_rel"] = sqrt(sum(abs2, tail .- Id) / length(tail)) / Id
    for f in (:ion_current, :anode_eff, :mass_eff, :voltage_eff, :current_eff, :divergence_eff)
        out[string(f)] = getfield(het, f)(avg)[1]
    end

    fr = avg.frames[1]
    out["Te_max_eV"] = maximum(fr.Tev)
    out["ne_max_m3"] = maximum(fr.ne)
    out["z_m"] = collect(avg.grid)
    out["profile_B_T"] = collect(fr.B)
    out["profile_ne_m3"] = collect(fr.ne)
    out["profile_Tev"] = collect(fr.Tev)
    out["profile_potential_V"] = collect(fr.potential)
    out["profile_nu_an"] = collect(fr.nu_an)
    for (sym, st) in fr.neutrals
        out["profile_nn_$(sym)_m3"] = collect(st.n)
    end
    for (sym, ions) in fr.ions, ion in ions
        out["profile_ui_$(sym)$(ion.Z)+_ms"] = collect(ion.u)
    end
    if haskey(c, :measured) && haskey(c.measured, :Id_A)
        out["Id_err_rel"] = (Id - c.measured.Id_A) / c.measured.Id_A
    end
    return out
end

rev = installed_commit()
rev == PINNED["commit"] || error("HallThruster.jl installed at rev '$rev', pinned commit is $(PINNED["commit"]); rerun setup.jl")
string(pkgversion(het)) == PINNED["version"] || error("HallThruster.jl version $(pkgversion(het)) != pinned $(PINNED["version"])")

cases = JSON3.read(read(ARGS[1], String))
results = Any[]
for c in cases.cases
    r = run_case(c)
    msg = r["converged"] ? "Id = $(round(r["discharge_current_A"]; digits=3)) A" : "FAILED ($(r["retcode"]))"
    haskey(r, "Id_err_rel") && (msg *= ", error vs measured $(round(100 * r["Id_err_rel"]; digits=1)) %")
    println(r["id"], ": ", msg, "  [", round(r["wall_s"]; digits=1), " s]")
    push!(results, r)
end
meta = Dict("hallthruster_version" => string(pkgversion(het)), "hallthruster_commit" => rev, "julia" => string(VERSION),
            "case_file" => ARGS[1], "case_source" => get(cases, :source, ""), "case_assumptions" => get(cases, :assumptions, ""),
            "pinned" => read(joinpath(@__DIR__, "PINNED.toml"), String))
mkpath(dirname(abspath(ARGS[2])))
open(ARGS[2], "w") do io
    JSON3.write(io, Dict("meta" => meta, "results" => results))
end
