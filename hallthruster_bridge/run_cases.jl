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

# Block molecular cases whose reaction set is incomplete: every rate_coeff_file named in the propellant config must exist.
function missing_rate_files(c)
    (haskey(c, :propellant_config) && !isempty(c.propellant_config)) || return String[]
    cfg = TOML.parsefile(joinpath(@__DIR__, c.propellant_config))
    dir = joinpath(@__DIR__, c.rate_dir)
    files = [r["rate_coeff_file"] for r in get(cfg, "reactions", []) if haskey(r, "rate_coeff_file")]
    return [f for f in files if !isfile(joinpath(dir, f))]
end

const TORR_TO_PA = 133.322368

# Measured B(z) from a cited CSV (z_mm, B_G; '#' comments, one header line). The file's exit plane is aligned with the
# case's exit plane (z = L_m) and B is scaled so that B at the exit plane ("exit") or its maximum ("max") equals B_ref_T.
# HallThruster.jl holds B constant beyond the data ends (no tail is invented here).
function measured_bfield(c)
    bp = c.B_profile
    rows = [split(l, ",") for l in eachline(joinpath(@__DIR__, bp.file)) if !startswith(l, "#") && !isempty(strip(l))]
    zf = [parse(Float64, r[1]) for r in rows[2:end]] .* 1e-3
    Bf = [parse(Float64, r[2]) for r in rows[2:end]] .* 1e-4
    z = zf .- bp.z_exit_in_file_mm * 1e-3 .+ c.L_m
    Bref = bp.scale_to == "exit" ? het.LinearInterpolation(z, Bf)(c.L_m) :
           bp.scale_to == "max" ? maximum(Bf) : error("B_profile.scale_to must be \"exit\" or \"max\"")
    return het.MagneticField(file = bp.file, z = z, B = Bf .* (c.B_ref_T / Bref)), c.B_ref_T / Bref
end

# Facility neutral ingestion, Brabston et al. JPP 2025 Eq. (13): mdot_en = A_en P sqrt(m / (2 pi k T0)).
entrained_flow(c, m) = c.entrainment_area_m2 * c.background_pressure_Torr * TORR_TO_PA * sqrt(m / (2π * het.kB * c.background_temperature_K))

function run_case(c)
    geom = het.Geometry1D(channel_length=c.L_m, inner_radius=c.r_in_m, outer_radius=c.r_out_m)
    bscale = 1.0
    if haskey(c, :B_profile)
        bfield, bscale = measured_bfield(c)
    else
        bpath = bfield_gaussian(joinpath(tempdir(), "b_$(c.id).csv"), c.L_m, c.B_max_T, c.B_sigma_in_m, c.B_sigma_out_m, c.domain_m)
        bfield = het.load_magnetic_field(bpath)
    end
    thruster = het.Thruster(name=c.thruster, geometry=geom, magnetic_field=bfield)
    kw = Dict{Symbol,Any}(:thruster => thruster, :domain => (0.0, c.domain_m), :discharge_voltage => c.Vd)
    ingest = get(c, :model_facility_ingestion, false)
    if ingest
        # v0.23.1 computes the ingested density as m*P/(kB*T) with P taken straight from `background_pressure_Torr`
        # (no Torr->Pa conversion; src/utilities/utility_functions.jl) and uses the channel area, not the entrainment
        # hemisphere. The multiplier restores Eq. (13) exactly; P stays in Torr for any pressure-dependent anom model.
        kw[:background_pressure_Torr] = c.background_pressure_Torr
        kw[:background_temperature_K] = c.background_temperature_K
        kw[:neutral_ingestion_multiplier] = TORR_TO_PA * c.entrainment_area_m2 / geom.channel_area
    end
    if haskey(c, :propellant_config) && !isempty(c.propellant_config)
        # case-file paths are relative to hallthruster_bridge/, independent of the launch directory
        kw[:propellant_config] = joinpath(@__DIR__, c.propellant_config)
        kw[:reaction_rate_directories] = String[joinpath(@__DIR__, c.rate_dir)]
        kw[:propellants] = [het.Propellant("N2", flow_rate_kg_s=c.mdot_kgps)]
    else
        kw[:propellants] = [het.Propellant(c.gas, flow_rate_kg_s=c.mdot_kgps, allowed_charges=[1])]
    end
    config = het.Config(; kw...)
    if ingest
        m = config.propellants[1].gas.m
        got = het.params_from_config(config).ingestion_flow_rates[1]
        isapprox(got, entrained_flow(c, m); rtol=1e-9) || error("ingestion flow $(got) != Eq. (13) $(entrained_flow(c, m))")
    end
    sp = het.SimParams(grid=het.EvenGrid(c.cells), dt=c.dt_s, duration=c.duration_s, verbose=false)
    t0 = time()
    sol = het.run_simulation(config, sp)
    out = Dict{String,Any}("id" => c.id, "retcode" => string(sol.retcode), "wall_s" => time() - t0,
                           "t_end_s" => sol.t[end], "converged" => sol.retcode == :success)
    haskey(c, :measured) && (out["measured"] = c.measured)
    out["model_facility_ingestion"] = ingest
    out["B_scale"] = bscale
    out["B_max_T"] = maximum(bfield.B)
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
    out["Id_min_A"], out["Id_max_A"] = minimum(tail), maximum(tail)
    # retcode :success only means no NaN/Inf. A deep relaxation oscillation (I_d swinging from ~0 to several times its
    # mean) averages to a number that is not an operating point, so it is not a validation comparison. Classification
    # threshold: RMS < 50 % of mean (observed runs fall at < 1 % or > 70 %, so the split is insensitive to it).
    out["quasi_steady"] = out["Id_rms_rel"] < 0.5
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
        if haskey(c, :background_pressure_Torr)
            # Brabston Eq. (14), zeta_A = 1.0: measured I_d corrected to vacuum (compare with ingestion OFF)
            mdot_en = entrained_flow(c, config.propellants[1].gas.m)
            out["mdot_entrained_kgps"] = mdot_en
            out["Id_corr_A"] = c.measured.Id_A - c.zeta_A * mdot_en * het.e / config.propellants[1].gas.m
            out["Id_err_rel_vs_corr"] = (Id - out["Id_corr_A"]) / out["Id_corr_A"]
        end
    end
    return out
end

rev = installed_commit()
rev == PINNED["commit"] || error("HallThruster.jl installed at rev '$rev', pinned commit is $(PINNED["commit"]); rerun setup.jl")
string(pkgversion(het)) == PINNED["version"] || error("HallThruster.jl version $(pkgversion(het)) != pinned $(PINNED["version"])")

cases = JSON3.read(read(ARGS[1], String))
for c in cases.cases
    miss = missing_rate_files(c)
    isempty(miss) || error("case $(c.id): reaction set incomplete, missing rate files in $(c.rate_dir): $(join(miss, ", "))")
end
results = Any[]
for c in cases.cases
    r = run_case(c)
    msg = r["retcode"] != "success" ? "FAILED ($(r["retcode"]))" :
          "Id = $(round(r["discharge_current_A"]; digits=3)) A (rms $(round(100 * r["Id_rms_rel"]; digits=0)) %" *
          (r["quasi_steady"] ? ")" : ", NOT QUASI-STEADY: I_d $(round(r["Id_min_A"]; digits=2))-$(round(r["Id_max_A"]; digits=1)) A)")
    haskey(r, "Id_err_rel") && (msg *= ", error vs measured $(round(100 * r["Id_err_rel"]; digits=1)) %")
    haskey(r, "Id_err_rel_vs_corr") && (msg *= ", vs vacuum-corrected $(round(100 * r["Id_err_rel_vs_corr"]; digits=1)) %")
    haskey(r, "model_facility_ingestion") && (msg *= r["model_facility_ingestion"] ? " [ingestion ON]" : " [vacuum]")
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
