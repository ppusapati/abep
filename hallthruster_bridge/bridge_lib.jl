# Shared library for the HallThruster.jl bridge (run_cases.jl, identify_worker.jl).
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

# Chemistry validity (no silent extrapolation). propellants/rate_validity.toml gives every rate file a status and, when
# "verified", the highest mean electron energy (3/2 T_e) up to which it rests on its cited cross sections. A file without
# an entry is an error, never a default. Returns one entry per reaction: (file, target neutral symbol, rate table on
# HallThruster's 0-255 eV grid, limit or nothing if unresolved, basis).
function chemistry_reactions(c)
    cfg = TOML.parsefile(joinpath(@__DIR__, c.propellant_config))
    dir = joinpath(@__DIR__, c.rate_dir)
    val = TOML.parsefile(joinpath(dir, "rate_validity.toml"))
    rx = []
    for r in get(cfg, "reactions", [])
        f = get(r, "rate_coeff_file", nothing)
        isnothing(f) && continue
        haskey(val, f) || error("rate file $f has no validity entry in $(c.rate_dir)/rate_validity.toml")
        v = val[f]
        v["status"] in ("verified", "unresolved") || error("rate_validity.toml: $f status must be verified|unresolved")
        target = haskey(r, "target_species") ? r["target_species"] :
                 strip(first(t for t in strip.(split(split(r["equation"], "->")[1], "+")) if t != "e"))
        _, k = het.load_rate_coeff_file(joinpath(dir, f), r["type"])
        lim = v["status"] == "verified" ? Float64(v["max_mean_energy_eV"]) : nothing
        push!(rx, (file=f, target=Symbol(target), k=k, limit=lim, basis=v["basis"]))
    end
    return rx
end

# Rate on HallThruster's own 1-eV mean-energy grid, clamped at the ends exactly as the solver does.
function rate_at(k, eps)
    x = clamp(eps, 0.0, length(k) - 1.0)
    i = min(floor(Int, x), length(k) - 2)
    return k[i + 1] + (x - i) * (k[i + 2] - k[i + 1])
end

# Reaction activity R_r = n_e n_target k_r(3/2 T_e), per saved frame of the averaging window and per cell (weighted by
# cell width; the 1-D area is constant). f_out,r = activity where 3/2 T_e > E_r,max / total activity. Per frame, not on
# the time-averaged state, because breathing produces transient high-T_e periods that averaging hides.
const CHEM_FOUT_TOL = 1e-12        # numerical tolerance on f_out (validation rule: f_out = 0)

function chemistry_validity(sol, c, i0)
    (haskey(c, :propellant_config) && !isempty(c.propellant_config)) || return nothing
    return chemistry_activity(sol.frames[i0:end], collect(sol.grid), chemistry_reactions(c))
end

# Pure function of (frames, cell centres, reactions): per reaction, the fraction of n_e n_target k_r dz summed over all
# frames and cells that comes from cells with 3/2 T_e above the reaction's limit (nothing if unresolved), and the highest
# mean energy at which the activity exceeds CHEM_FOUT_TOL of its maximum.
function chemistry_activity(frames, z, rx)
    dz = [(z[min(i + 1, end)] - z[max(i - 1, 1)]) / (i == 1 || i == length(z) ? 1 : 2) for i in eachindex(z)]
    res = []
    for r in rx
        acts = Float64[]; epss = Float64[]
        for f in frames
            haskey(f.neutrals, r.target) || error("reaction target $(r.target) ($(r.file)) is not a neutral fluid")
            nt = f.neutrals[r.target].n
            for i in eachindex(z)
                eps = 1.5 * f.Tev[i]
                push!(acts, f.ne[i] * nt[i] * rate_at(r.k, eps) * dz[i]); push!(epss, eps)
            end
        end
        Rmax = maximum(acts)
        tot, out, epsmax = 0.0, 0.0, 0.0
        for (R, eps) in zip(acts, epss)
            tot += R
            R > CHEM_FOUT_TOL * Rmax && (epsmax = max(epsmax, eps))
            !isnothing(r.limit) && eps > r.limit && (out += R)
        end
        push!(res, (file=r.file, limit=r.limit, basis=r.basis, fout=isnothing(r.limit) ? nothing : (tot > 0 ? out / tot : 0.0),
                    eps_active=epsmax))
    end
    return res
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

# Wall ion flux and impact energy, re-evaluated from the solver's own WallSheath sheath model (physics/wall_losses.jl):
# per wall area, Gamma_i = loss_scale * h * sum_s n_s sqrt(Z_s e T_e / m_s) (the Bohm flux that sets the electron wall loss),
# h = edge_to_center_density_ratio(); impact energy per ion = Z phi_s + T_e/2 (sheath + Bohm presheath), with
# phi_s = sheath_potential(T_e, gamma_SEE, m_eff) and gamma_SEE capped as in freq_electron_wall!. Evaluated in every saved
# frame of the averaging window over the channel cells (z <= L), then averaged (flux-weighted for energy): per-frame, not
# on the time-averaged state, because breathing makes the two differ. Returns (nothing, reason) when not reproducible.
function wall_ion_metrics(sol, config, i0)
    model = config.wall_loss_model
    model isa het.WallSheath || return nothing, "wall_loss_model is not WallSheath"
    config.thruster.shielded && return nothing, "shielded thruster: wall T_e needs solver cache not saved in frames"
    L = config.thruster.geometry.channel_length
    cells = findall(<=(L), sol.grid)
    h, ls = het.edge_to_center_density_ratio(), model.loss_scale
    flux_t, eflux_t = 0.0, 0.0
    frames = sol.frames[i0:end]
    for f in frames
        flux, eflux = 0.0, 0.0
        for i in cells
            Te = f.Tev[i]
            nsum = sum(ion.n[i] for ions in values(f.ions) for ion in ions)
            msum = sum(ion.n[i] * ion.m for ions in values(f.ions) for ion in ions)
            m_eff = nsum > 0 ? msum / nsum : first(first(values(f.ions))).m
            γ = het.SEE_yield(model.material, Te, 1 - 8.3 * sqrt(het.me / m_eff))
            ϕs = het.sheath_potential(Te, γ, m_eff)
            for ions in values(f.ions), ion in ions
                Γ = ls * h * ion.n[i] * sqrt(ion.Z * het.e * Te / ion.m)
                flux += Γ
                eflux += Γ * (ion.Z * ϕs + Te / 2)
            end
        end
        flux_t += flux / length(cells)
        eflux_t += eflux / length(cells)
    end
    flux_t /= length(frames); eflux_t /= length(frames)
    return (flux_t, eflux_t / flux_t), config.ion_wall_losses ? "ion_wall_losses=true: flux also removed from the ion fluid" :
           "ion_wall_losses=false: flux sets the electron wall loss but is not removed from the ion fluid"
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
        zpeak = c.L_m                    # bfield_gaussian peaks at the exit plane by construction
    end
    thruster = het.Thruster(name=c.thruster, geometry=geom, magnetic_field=bfield)
    kw = Dict{Symbol,Any}(:thruster => thruster, :domain => (0.0, c.domain_m), :discharge_voltage => c.Vd)
    # Optional transport override (identification runs). Absent -> HallThruster.jl defaults, TwoZoneBohm(1/160, 1/16),
    # transition 0.1 L. Only the families listed here are accepted, so a case can't silently switch model family.
    if haskey(c, :transport)
        tr = c.transport
        if tr.model == "TwoZoneBohm"
            kw[:anom_model] = het.TwoZoneBohm(tr.c1, tr.c2)
            kw[:transition_length] = tr.transition_length_m
        elseif tr.model == "ScaledGaussianBohm"      # c(z) = anom_scale (1 - barrier_scale exp(-((z - center L)/(width L))^2 / 2))
            kw[:anom_model] = het.ScaledGaussianBohm(tr.anom_scale, tr.barrier_scale, tr.width, tr.center)
        elseif tr.model == "MultiLogBohm"            # nodes in metres; log-linear c(z) between nodes, constant outside
            kw[:anom_model] = het.MultiLogBohm(collect(Float64, tr.zs_m), collect(Float64, tr.cs))
        else
            error("case $(c.id): unsupported transport.model $(tr.model)")
        end
    end
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

    wall, wall_basis = wall_ion_metrics(sol, config, i0)
    out["wall_ion_basis"] = wall_basis
    if !isnothing(wall)
        out["wall_ion_flux_m2s"], out["wall_ion_energy_eV"] = wall
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
    # Thrust targets. Brabston publishes the Eq. (16)-corrected (vacuum) thrust, T_corr = T (1 - zeta_en mdot_en/(mdot_a +
    # mdot_en)). Facility mode is compared with the raw stand thrust recovered by inverting Eq. (16) with the paper's zeta_en.
    if haskey(c, :measured) && haskey(c.measured, :T_corr_mN)
        Tcorr = c.measured.T_corr_mN * 1e-3
        if mode == "facility"
            m = config.propellants[1].gas.m
            f = c.zeta_en * entrained_flow(c, m) / (c.mdot_kgps + entrained_flow(c, m))
            out["T_target_N"], out["T_target_kind"] = Tcorr / (1 - f), "raw stand thrust (Eq. 16 inverted)"
        else
            out["T_target_N"], out["T_target_kind"] = Tcorr, "Eq. (16) corrected"
        end
        out["T_err_rel"] = (out["thrust_N"] - out["T_target_N"]) / out["T_target_N"]
        out["T_err_sigma"] = (out["thrust_N"] - out["T_target_N"]) / (c.measured.T_sigma_mN * 1e-3)
    end
    if get(c, :compact, false)            # identification grids: drop axial profiles to keep result files small
        for k in collect(keys(out))
            (startswith(k, "profile_") || k == "z_m") && delete!(out, k)
        end
    end
    out["ion_wall_losses"] = config.ion_wall_losses
    # Schema-complete (map_ready) is not the same as erosion-grade: wall flux is only dynamically self-consistent when the
    # solver actually removes it from the ion fluid.
    out["wall_life_trustworthy"] = out["converged"] && out["sustained"] && config.ion_wall_losses &&
                                   haskey(out, "wall_ion_flux_m2s") && haskey(out, "wall_ion_energy_eV")
    # No silent chemistry extrapolation: no reaction's activity may come from states beyond its table's validity domain
    # (validation rule f_out = 0), and every table in the set must have a verified domain.
    chem = chemistry_validity(sol, c, i0)
    if isnothing(chem)
        out["chemistry_basis"] = "HallThruster.jl built-in propellant tables (no project validity manifest)"
        out["chemistry_trustworthy"] = out["converged"] && out["sustained"]
    else
        resolved = [r for r in chem if !isnothing(r.fout)]
        out["chemistry_unresolved_rate_files"] = [r.file for r in chem if isnothing(r.fout)]
        out["chemistry_per_reaction"] = [Dict("file" => r.file, "max_mean_energy_eV" => r.limit, "extrapolated_fraction" => r.fout,
                                              "max_mean_energy_active_eV" => r.eps_active, "basis" => r.basis) for r in chem]
        if !isempty(resolved)
            # limiting file: largest extrapolated fraction; ties (e.g. all zero) broken by the smallest margin to its limit
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
    end
    out["schema"] = String(SCHEMA.schema)
    out["schema_missing"] = schema_missing(out)
    out["map_ready"] = isempty(out["schema_missing"])
    return out
end

# Refuse to run unless the installed HallThruster.jl is exactly the pinned commit and version.
function check_pin()
    rev = installed_commit()
    rev == PINNED["commit"] || error("HallThruster.jl installed at rev '$rev', pinned commit is $(PINNED["commit"]); rerun setup.jl")
    string(pkgversion(het)) == PINNED["version"] || error("HallThruster.jl version $(pkgversion(het)) != pinned $(PINNED["version"])")
    return rev
end

# Refuse the whole case file if any molecular case lacks a rate file.
function check_reaction_sets(cases)
    for c in cases.cases
        miss = missing_rate_files(c)
        isempty(miss) || error("case $(c.id): reaction set incomplete, missing rate files in $(c.rate_dir): $(join(miss, ", "))")
    end
end
