# NP-HALL-PARAMETRIC-ENVELOPE addendum A7 (Hall numerical method): bridge-side numerics for the XE vacuum H-1 cases.
# Includes bridge_lib.jl unchanged (it is sha-pinned by prereg v1) and builds the same HallThruster.jl Config as its
# run_case on the XE / vacuum / measured-B path; refuses any other path. Exposes only options the pinned HallThruster.jl
# v0.23.1 already has (SimParams: grid, dt, duration, num_save, CFL, min_dt, max_dt, max_small_steps, adaptive; Config:
# reconstruct, implicit_energy). Physics (geometry, B(z), V_d, flow, transport, wall model, chemistry) is untouched.
# Observables are computed from the saved frames by a7_window_stats, a pure function of the series.
include(joinpath(@__DIR__, "bridge_lib.jl"))

# Numerics a v1 / A6 case gets from bridge_lib.run_case (SimParams / Config defaults of the pinned version).
const A7_SOLVER_DEFAULTS = (num_save = 1000, CFL = 0.799, min_dt_s = 1e-10, max_dt_s = 1e-7, max_small_steps = 100,
                            adaptive = true, reconstruct = true, implicit_energy = 1.0)

# Config of bridge_lib.run_case(c, "vacuum") for an XE case with a measured B profile, with optional numerics overrides.
function a7_config(c; reconstruct::Bool = A7_SOLVER_DEFAULTS.reconstruct, implicit_energy::Float64 = A7_SOLVER_DEFAULTS.implicit_energy,
                   initial_condition = het.DefaultInitialization())
    c.gas == "Xe" || error("A7 bridge: case $(c.id) is not an Xe case")
    haskey(c, :B_profile) || error("A7 bridge: case $(c.id) has no measured B profile")
    (haskey(c, :propellant_config) && !isempty(c.propellant_config)) && error("A7 bridge: case $(c.id) has a propellant config")
    haskey(c, :transport) && c.transport.model == "ScaledGaussianBohm" || error("A7 bridge: case $(c.id) transport is not ScaledGaussianBohm")
    geom = het.Geometry1D(channel_length = c.L_m, inner_radius = c.r_in_m, outer_radius = c.r_out_m)
    bfield, bscale, zpeak = measured_bfield(c)
    thruster = het.Thruster(name = c.thruster, geometry = geom, magnetic_field = bfield)
    tr = c.transport
    config = het.Config(; thruster, domain = (0.0, c.domain_m), discharge_voltage = c.Vd,
                        anom_model = het.ScaledGaussianBohm(tr.anom_scale, tr.barrier_scale, tr.width, tr.center),
                        propellants = [het.Propellant(c.gas, flow_rate_kg_s = c.mdot_kgps, allowed_charges = [1])],
                        reconstruct, implicit_energy, initial_condition)
    return config, bfield, bscale, zpeak
end

function a7_simparams(n)
    return het.SimParams(grid = het.EvenGrid(n.cells), dt = n.dt_s, duration = n.duration_s, num_save = n.num_save,
                         CFL = n.CFL, min_dt = n.min_dt_s, max_dt = n.max_dt_s, max_small_steps = n.max_small_steps,
                         adaptive = n.adaptive, verbose = false, print_errors = false)
end

_mean(x) = sum(x) / length(x)

# Window statistics of an evenly sampled series y(t) over t >= t_start (pure function of its inputs):
#   mean, batch-means standard error with nb contiguous batches (SE = sd(batch means) / sqrt(nb)), the two half-window
#   means, RMS / |mean|, and the integrated autocorrelation time (initial-positive-sequence sum of the normalized ACF,
#   in units of the sample spacing) with the SE it implies.
function a7_window_stats(t, y, t_start; nb::Int = 10)
    idx = findall(>=(t_start * (1 - 1e-12)), t)
    w = Float64.(y[idx])
    N = length(w)
    N >= 2nb || error("window has $(N) samples, fewer than 2 x $(nb) batches")
    m = _mean(w)
    L = N ÷ nb
    bm = [_mean(w[((k - 1) * L + 1):(k * L)]) for k in 1:nb]
    sd_b = sqrt(sum(abs2, bm .- _mean(bm)) / (nb - 1))
    h = N ÷ 2
    m1, m2 = _mean(w[1:h]), _mean(w[(h + 1):end])
    v = sum(abs2, w .- m) / N
    rms_rel = m != 0 ? sqrt(v) / abs(m) : Inf
    tau = 0.5
    if v > 0
        for k in 1:(N - 1)
            r = sum((w[i] - m) * (w[i + k] - m) for i in 1:(N - k)) / (N * v)
            r <= 0 && break
            tau += r
        end
    end
    se_acf = sqrt(v * 2 * tau / N)
    return (n = N, mean = m, se_batch = sd_b / sqrt(nb), batch_means = bm, mean_first_half = m1, mean_second_half = m2,
            rms_rel = rms_rel, min = minimum(w), max = maximum(w), tau_int_samples = tau, se_acf = se_acf)
end

# Run one case at numerics n (fields of A7_SOLVER_DEFAULTS plus cells, dt_s, duration_s, average_start_s). Returns the
# raw run record: retcode, the time of the last saved frame (on failure HallThruster.jl leaves the unfilled times at 0,
# so sol.t[end] is not the failure time), failure-frame diagnostics, and per-frame series t, I_d, thrust (instantaneous,
# HallThruster.jl thrust(sol, frame)), the solver's adaptive step limit, max T_e and min n_e. No status or verdict.
function a7_run(c, n)
    # Diagnostic-only override of the DefaultInitialization densities (H-FAIL ignition test); absent -> package default.
    ic = haskey(n, :init_ion_density_factor) ?
         het.DefaultInitialization(min_ion_density = 2.0e17 * n.init_ion_density_factor, max_ion_density = 1.0e18 * n.init_ion_density_factor) :
         het.DefaultInitialization()
    config, bfield, bscale, zpeak = a7_config(c; reconstruct = n.reconstruct, implicit_energy = n.implicit_energy, initial_condition = ic)
    sp = a7_simparams(n)
    t0 = time()
    sol = het.run_simulation(config, sp)
    LAST_SOL[] = sol
    nf = length(sol.frames)
    t = sol.t[1:nf]
    out = Dict{String,Any}("retcode" => string(sol.retcode), "wall_s" => time() - t0, "n_frames" => nf,
                           "t_last_frame_s" => t[end], "converged" => sol.retcode == :success,
                           "transport" => "$(config.anom_model), transition_length $(config.transition_length) m",
                           "B_scale" => bscale, "B_max_T" => maximum(bfield.B), "B_peak_minus_exit_m" => zpeak - c.L_m)
    sol.retcode == :error && (out["error"] = sol.error)
    out["series_t_s"] = t
    out["series_Id_A"] = [f.discharge_current[] for f in sol.frames]
    out["series_thrust_N"] = [het.thrust(sol, i) for i in 1:nf]
    out["series_dt_limit_s"] = [f.dt[] for f in sol.frames]
    out["series_Te_max_eV"] = [maximum(f.Tev) for f in sol.frames]
    out["series_ne_min_m3"] = [minimum(f.ne) for f in sol.frames]
    return out, sol
end

# A7 registered observables of one case (fields cells, dt_s, duration_s, average_start_s, num_save and the A7 numerics
# block; physics fields as v1). Raw values only, no status: the run status and every comparison are applied in Rust.
#   thrust_N, discharge_current_A, ion_current_A: time-means of the per-frame instantaneous values over the window
#   t >= average_start_s (HallThruster.jl thrust(sol, i), discharge_current, ion_current), with batch-means standard errors
#   (10 contiguous batches), the two half-window means and the integrated-autocorrelation diagnostic;
#   Id_rms_rel, Id_pp_rel, Id_min_A, Id_max_A over the window; sustained as v1 (min I_d > 1 % of the window mean);
#   thrust_avgstate_N: thrust of the time-averaged state over the same window (the v1 / A6 statistic), report only.
const A7_NB = 10

function a7_record(c)
    nm = c.numerics
    n = (cells = Int(c.cells), dt_s = Float64(c.dt_s), duration_s = Float64(c.duration_s), num_save = Int(c.num_save),
         CFL = Float64(nm.CFL), min_dt_s = Float64(nm.min_dt_s), max_dt_s = Float64(nm.max_dt_s),
         max_small_steps = Int(nm.max_small_steps), adaptive = Bool(nm.adaptive), reconstruct = Bool(nm.reconstruct),
         implicit_energy = Float64(nm.implicit_energy))
    r, sol = a7_run(c, n)
    t, Id, T = r["series_t_s"], r["series_Id_A"], r["series_thrust_N"]
    out = Dict{String,Any}(k => r[k] for k in ("retcode", "wall_s", "n_frames", "t_last_frame_s", "converged", "transport",
                                                 "B_scale", "B_max_T", "B_peak_minus_exit_m"))
    haskey(r, "error") && (out["error"] = r["error"])
    out["Id_series_max_A"] = maximum(Id)
    out["Id_last_frame_A"] = Id[end]
    out["ne_min_last_frame_m3"] = r["series_ne_min_m3"][end]
    out["Te_max_last_frame_eV"] = r["series_Te_max_eV"][end]
    out["dt_limit_min_s"] = length(t) > 1 ? minimum(r["series_dt_limit_s"][2:end]) : nothing
    if sol.retcode != :success
        out["finite"] = false
        return out
    end
    Ii = het.ion_current(sol)
    sI = a7_window_stats(t, Id, c.average_start_s; nb = A7_NB)
    sT = a7_window_stats(t, T, c.average_start_s; nb = A7_NB)
    sJ = a7_window_stats(t, Ii, c.average_start_s; nb = A7_NB)
    out["window_start_s"] = c.average_start_s
    out["window_samples"] = sI.n
    out["thrust_N"] = sT.mean
    out["thrust_se_N"] = sT.se_batch
    out["thrust_half_means_N"] = [sT.mean_first_half, sT.mean_second_half]
    out["thrust_tau_int_samples"] = sT.tau_int_samples
    out["thrust_rms_rel"] = sT.rms_rel
    out["discharge_current_A"] = sI.mean
    out["discharge_current_se_A"] = sI.se_batch
    out["discharge_current_half_means_A"] = [sI.mean_first_half, sI.mean_second_half]
    out["discharge_current_tau_int_samples"] = sI.tau_int_samples
    out["discharge_power_W"] = sI.mean * c.Vd
    out["ion_current_A"] = sJ.mean
    out["ion_current_se_A"] = sJ.se_batch
    out["Id_rms_rel"] = sI.rms_rel
    out["Id_pp_rel"] = (sI.max - sI.min) / sI.mean
    out["Id_min_A"], out["Id_max_A"] = sI.min, sI.max
    i0 = findfirst(>=(c.average_start_s * (1 - 1e-12)), t)
    out["Id_f_dominant_Hz"], out["Id_amp_dominant_A"] = dominant_frequency(t[i0:end], Id[i0:end])
    out["quasi_steady"] = sI.rms_rel < 0.5
    out["sustained"] = sI.min > SCHEMA.conventions.sustained_min_Id_fraction * sI.mean
    avg = het.time_average(sol, i0)
    out["thrust_avgstate_N"] = het.thrust(avg)[1]
    out["Te_max_eV"] = maximum(avg.frames[1].Tev)
    out["ne_max_m3"] = maximum(avg.frames[1].ne)
    out["finite"] = all(isfinite, Id) && all(isfinite, T) && isfinite(sT.mean) && isfinite(sI.mean) &&
                    isfinite(sT.se_batch) && isfinite(sI.se_batch)
    return out
end
