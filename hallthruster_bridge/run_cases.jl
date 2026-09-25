# Offline driver: julia --project=hallthruster_bridge hallthruster_bridge/run_cases.jl cases/p5_xenon.json out/p5_xenon.json
# UNTESTED in the development sandbox (no Julia). API per HallThruster.jl v0.23.1 docs/src/tutorials/simulation.md.
using HallThruster: HallThruster as het
using JSON3

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
    sp = het.SimParams(grid=het.EvenGrid(c.cells), dt=c.dt_s, duration=c.duration_s)
    sol = het.run_simulation(config, sp)
    avg = het.time_average(sol, c.average_start_s)
    Id_t = het.discharge_current(sol)
    out = Dict(
        "id" => c.id, "retcode" => string(sol.retcode),
        "thrust_N" => het.thrust(avg)[1], "discharge_current_A" => het.discharge_current(avg)[1],
        "anode_eff" => het.anode_eff(avg)[1],
        "Id_osc_rel" => (maximum(Id_t[end÷2:end]) - minimum(Id_t[end÷2:end])) / max(het.discharge_current(avg)[1], 1e-9),
    )
    for f in (:mass_eff, :voltage_eff, :current_eff, :divergence_eff, :ion_current)   # present in v0.23 post-processing
        try
            out[string(f)] = getfield(het, f)(avg)[1]
        catch
        end
    end
    try
        fr = avg.frames[1]
        out["z_m"] = collect(avg.grid.cell_centers)
        for k in (:ne, :Tev, :ϕ, :ui, :nn)
            haskey(fr, k) && (out["profile_" * string(k)] = collect(getfield(fr, k)))
        end
    catch
    end
    return out
end

cases = JSON3.read(read(ARGS[1], String))
results = [run_case(c) for c in cases.cases]
meta = Dict("hallthruster_version" => string(pkgversion(het)), "julia" => string(VERSION), "pinned" => read(joinpath(@__DIR__, "PINNED.toml"), String))
open(ARGS[2], "w") do io
    JSON3.write(io, Dict("meta" => meta, "results" => results))
end
