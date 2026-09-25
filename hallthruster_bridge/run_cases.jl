# Offline driver: julia --project=hallthruster_bridge hallthruster_bridge/run_cases.jl cases/p5_xenon.json out/p5_xenon.json
# Checked against the installed HallThruster.jl v0.23.1 source (commit in PINNED.toml): Config / Propellant /
# SimParams / Solution / Frame / postprocess.jl. No silent fallbacks: failed runs are reported with converged=false.
using HallThruster: HallThruster as het
using JSON3
using TOML

const PINNED = TOML.parsefile(joinpath(@__DIR__, "PINNED.toml"))["hallthruster"]
const SCHEMA = JSON3.read(read(joinpath(@__DIR__, "hall_map_schema_v1.json"), String))

# Fields of hall_map_schema_v1 that this record lacks (a point is map-ready only if none are missing).
schema_missing(out) = [String(k) for k in keys(SCHEMA.fields) if !haskey(out, String(k))]

# Number of atoms in a species formula, e.g. "Xe" -> 1, "N2" -> 2, "CO2" -> 3.
natoms(formula) = sum((isempty(m[1]) ? 1 : parse(Int, m[1])) for m in eachmatch(r"[A-Z][a-z]?(\d*)", String(formula)))

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

# Measured B(z) from a cited CSV (z_mm, B_G; '#' comments, one header line), placed on the model axis by an explicit
# rigid registration (never stretched):
#   align = "exit":  file point z_ref_in_file_mm sits at the model exit plane, z = L_m
#   align = "anode": file point z_ref_in_file_mm sits at the model anode, z = 0
# B is then scaled so that B at the model exit plane ("exit") or its maximum ("max") equals B_ref_T.
# HallThruster.jl holds B constant beyond the data ends (no tail is invented here).
function measured_bfield(c)
    bp = c.B_profile
    rows = [split(l, ",") for l in eachline(joinpath(@__DIR__, bp.file)) if !startswith(l, "#") && !isempty(strip(l))]
    zf = [parse(Float64, r[1]) for r in rows[2:end]] .* 1e-3
    Bf = [parse(Float64, r[2]) for r in rows[2:end]] .* 1e-4
    z0 = bp.align == "exit" ? c.L_m : bp.align == "anode" ? 0.0 : error("B_profile.align must be \"exit\" or \"anode\"")
    z = zf .- bp.z_ref_in_file_mm * 1e-3 .+ z0
    Bref = bp.scale_to == "exit" ? het.LinearInterpolation(z, Bf)(c.L_m) :
           bp.scale_to == "max" ? maximum(Bf) : error("B_profile.scale_to must be \"exit\" or \"max\"")
    return het.MagneticField(file = bp.file, z = z, B = Bf .* (c.B_ref_T / Bref)), c.B_ref_T / Bref, z[argmax(Bf)]
end

# Dominant frequency of the averaging-window I_d trace (mean removed; plain DFT, frames are evenly spaced in time).
function dominant_frequency(t, y)
    n = length(y); dt = (t[end] - t[1]) / (n - 1)
    maximum(abs.(diff(t) .- dt)) < 1e-6 * dt || error("saved frames are not evenly spaced")
    yc = y .- sum(y) / n
    amp = [abs(sum(yc[j] * cis(-2π * k * (j - 1) / n) for j in 1:n)) for k in 1:(n ÷ 2)]
    k = argmax(amp)
    return k / (n * dt), 2 * amp[k] / n
end

# Facility neutral ingestion, Brabston et al. JPP 2025 Eq. (13): mdot_en = A_en P sqrt(m / (2 pi k T0)).
entrained_flow(c, m) = c.entrainment_area_m2 * c.background_pressure_Torr * TORR_TO_PA * sqrt(m / (2π * het.kB * c.background_temperature_K))

# Validation comparison modes. The simulated flow and the experimental target must describe the same situation:
#   "facility": facility ingestion ON  (anode + Eq. 13 flow)  vs raw measured I_d = P_d/V_d
#   "vacuum":   facility ingestion OFF (anode flow only)       vs Eq. (14) vacuum-corrected I_d
# Never cross them (ingestion ON vs corrected, or OFF vs raw).
const MODES = ("facility", "vacuum")

function run_case(c, mode)
    mode in MODES || error("unknown comparison mode $mode")
    geom = het.Geometry1D(channel_length=c.L_m, inner_radius=c.r_in_m, outer_radius=c.r_out_m)
    bscale, zpeak = 1.0, NaN
    if haskey(c, :B_profile)
        bfield, bscale, zpeak = measured_bfield(c)
    else
        bpath = bfield_gaussian(joinpath(tempdir(), "b_$(c.id).csv"), c.L_m, c.B_max_T, c.B_sigma_in_m, c.B_sigma_out_m, c.domain_m)
        bfield = het.load_magnetic_field(bpath)
    end
    thruster = het.Thruster(name=c.thruster, geometry=geom, magnetic_field=bfield)
    kw = Dict{Symbol,Any}(:thruster => thruster, :domain => (0.0, c.domain_m), :discharge_voltage => c.Vd)
    ingest = mode == "facility"
    ingest && !haskey(c, :background_pressure_Torr) && error("case $(c.id): facility mode needs background_pressure_Torr")
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
    out = Dict{String,Any}("id" => "$(c.id)/$(mode)", "case_id" => c.id, "comparison_mode" => mode,
                           "retcode" => string(sol.retcode), "wall_s" => time() - t0,
                           "t_end_s" => sol.t[end], "converged" => sol.retcode == :success)
    haskey(c, :measured) && (out["measured"] = c.measured)
    out["model_facility_ingestion"] = ingest
    out["transport"] = "$(config.anom_model), transition_length $(config.transition_length) m"
    out["B_scale"] = bscale
    out["B_max_T"] = maximum(bfield.B)
    out["B_peak_minus_exit_m"] = zpeak - c.L_m
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
    out["Id_pp_rel"] = (maximum(tail) - minimum(tail)) / Id           # peak-to-peak / mean
    out["Id_rms_rel"] = sqrt(sum(abs2, tail .- Id) / length(tail)) / Id  # RMS / mean
    out["Id_min_A"], out["Id_max_A"] = minimum(tail), maximum(tail)
    out["Id_f_dominant_Hz"], out["Id_amp_dominant_A"] = dominant_frequency(sol.t[i0:end], tail)
    # Internal diagnostic only, not a validation criterion (50 % has no experimental meaning): runs so far fall at
    # < 1 % or > 65 % RMS. Validation compares the RMS, peak-to-peak and frequency above with measured traces.
    out["quasi_steady"] = out["Id_rms_rel"] < 0.5
    out["sustained"] = minimum(tail) > SCHEMA.conventions.sustained_min_Id_fraction * Id
    out["ion_current_A"] = het.ion_current(avg)[1]
    for f in (:anode_eff, :mass_eff, :voltage_eff, :current_eff, :divergence_eff)
        out[string(f)] = getfield(het, f)(avg)[1]
    end

    fr = avg.frames[1]
    exit_flux = Dict(sym => sum(ion.nu[end] for ion in ions) for (sym, ions) in fr.ions)   # ion number flux at exit
    out["ion_species_fraction_atomic"] = sum(v for (sym, v) in exit_flux if natoms(sym) == 1; init=0.0) / sum(values(exit_flux))
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
        out["Id_raw_A"] = c.measured.Id_A
        if mode == "facility"
            out["Id_target_A"], out["Id_target_kind"] = c.measured.Id_A, "raw P_d/V_d (facility)"
        elseif haskey(c, :background_pressure_Torr)
            # Brabston Eq. (14), zeta_A = 1.0: measured I_d corrected to vacuum
            m = config.propellants[1].gas.m
            out["mdot_entrained_kgps"] = entrained_flow(c, m)
            out["Id_target_A"] = c.measured.Id_A - c.zeta_A * out["mdot_entrained_kgps"] * het.e / m
            out["Id_target_kind"] = "Eq. (14) vacuum-corrected"
        else
            out["Id_target_A"], out["Id_target_kind"] = c.measured.Id_A, "raw P_d/V_d (facility pressure unknown, uncorrected)"
        end
        out["Id_err_rel"] = (Id - out["Id_target_A"]) / out["Id_target_A"]
    end
    out["schema"] = String(SCHEMA.schema)
    out["schema_missing"] = schema_missing(out)
    out["map_ready"] = isempty(out["schema_missing"])
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
fmt(x; d=0) = isnothing(x) ? "—" : string(round(x; digits=d))
results = Any[]
summary = Any[]
for c in cases.cases
    modes = haskey(c, :comparison_modes) ? collect(String, c.comparison_modes) : ["vacuum"]
    row = Dict{String,Any}("case_id" => c.id)
    for mode in modes
        r = run_case(c, mode)
        msg = r["retcode"] != "success" ? "FAILED ($(r["retcode"]))" :
              "Id = $(fmt(r["discharge_current_A"]; d=3)) A, target $(fmt(get(r, "Id_target_A", nothing); d=3)) A " *
              "[$(get(r, "Id_target_kind", "none"))], error $(fmt(100 * get(r, "Id_err_rel", NaN); d=1)) %, " *
              "rms $(fmt(100 * r["Id_rms_rel"])) %, p-p $(fmt(100 * r["Id_pp_rel"])) %, f $(fmt(r["Id_f_dominant_Hz"] / 1e3; d=1)) kHz"
        println(r["id"], ": ", msg, "  [", round(r["wall_s"]; digits=1), " s]")
        push!(results, r)
        if r["retcode"] == "success"
            for k in ("Id_err_rel", "Id_rms_rel", "Id_pp_rel", "Id_f_dominant_Hz", "discharge_current_A", "Id_target_A")
                haskey(r, k) && (row["$(mode)_$(k)"] = r[k])
            end
        end
    end
    push!(summary, row)
end
println("\nside-by-side (facility = ingestion ON vs raw P_d/V_d; vacuum = ingestion OFF vs Eq. 14 corrected)")
println(rpad("case", 16), rpad("err facility", 14), rpad("err vacuum", 12), rpad("rms fac/vac", 16), rpad("p-p fac/vac", 18), "f fac/vac [kHz]")
for row in summary
    g(k, sc=100, d=0) = haskey(row, k) ? fmt(sc * row[k]; d) : "—"
    println(rpad(row["case_id"], 16), rpad(g("facility_Id_err_rel", 100, 1) * " %", 14), rpad(g("vacuum_Id_err_rel", 100, 1) * " %", 12),
            rpad(g("facility_Id_rms_rel") * "/" * g("vacuum_Id_rms_rel") * " %", 16),
            rpad(g("facility_Id_pp_rel") * "/" * g("vacuum_Id_pp_rel") * " %", 18),
            g("facility_Id_f_dominant_Hz", 1e-3, 1) * "/" * g("vacuum_Id_f_dominant_Hz", 1e-3, 1))
end
meta = Dict("hallthruster_version" => string(pkgversion(het)), "hallthruster_commit" => rev, "julia" => string(VERSION),
            "case_file" => ARGS[1], "case_source" => get(cases, :source, ""), "case_assumptions" => get(cases, :assumptions, ""),
            "pinned" => read(joinpath(@__DIR__, "PINNED.toml"), String), "schema" => String(SCHEMA.schema))
mkpath(dirname(abspath(ARGS[2])))
open(ARGS[2], "w") do io
    JSON3.write(io, Dict("meta" => meta, "summary" => summary, "results" => results))
end
