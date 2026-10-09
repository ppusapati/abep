# hall_air_rp1_v1 aggregation: reads <out>/runs/*.json and <out>/preflight.json and writes the ONE result file
# <out>/hall_air_rp1_v1_results.json (plus <out>/hall_air_rp1_v1_results.csv). Applies the addendum A9-LP run-status,
# convergence and case-outcome rules (A7 rules + the A1 AIR domain rule). Pure function of the run records.
#   julia --project=hallthruster_bridge tools/local_runs/hall_air_rp1_v1/aggregate.jl <out_dir>
using JSON3
using SHA
using Dates

const PKG = @__DIR__
const OUT = ARGS[1]
const LEVELS = ("A7-P", "A7-C")
const AMU = 1.66053906660e-27
const E_CHARGE = 1.602176634e-19
const G0 = 9.80665
const SPECIES_MASS_AMU = Dict("N2" => 28.0134, "N" => 14.0067, "O2" => 31.998, "O" => 15.999)
const CHEM_FOUT_TOL = 1e-12
const EVALUATED = ("PASS", "NOT_SUSTAINED")

num(x) = x isa Number ? Float64(x) : NaN                     # "NaN" / "Inf" strings and null -> NaN
fin(x) = x isa Number && isfinite(x)
getn(r, ks...) = (v = r; for k in ks; (v isa AbstractDict && haskey(v, k)) || return nothing; v = v[k]; end; v)
feed_current_equiv_A(c) = E_CHARGE * sum(Float64(f.flow_rate_kg_s) / (SPECIES_MASS_AMU[String(f.species)] * AMU) for f in c.feed)

# Run status (addendum A9-LP): NUMERICAL_FAILURE > EXTINCT > OUT_OF_DOMAIN > NOT_SUSTAINED > NON_STATIONARY >
# STATISTICALLY_UNRESOLVED > PASS; NOT_RUN when the record is absent. Returns (status, reasons).
function run_status(r, c)
    isnothing(r) && return "NOT_RUN", ["no record"]
    why = String[]
    T, I = getn(r, "thrust"), getn(r, "discharge_current")
    ok = r["retcode"] == "success" && r["converged"] == true && r["finite"] == true && !isnothing(T) && !isnothing(I)
    if ok
        for (nm, s) in (("thrust", T), ("discharge_current", I)), k in ("mean", "se_batch", "rms_rel")
            fin(s[k]) || (ok = false; push!(why, "$(nm).$(k) not finite"))
        end
        for s in (T, I)
            all(fin, s["half_means"]) || (ok = false; push!(why, "half-window mean not finite"))
        end
    end
    if !ok
        pushfirst!(why, "retcode=$(r["retcode"])" * (haskey(r, "error") ? ": $(first(string(r["error"]), 300))" : ""))
        return "NUMERICAL_FAILURE", why
    end
    Iext = 1e-3 * feed_current_equiv_A(c)
    I["mean"] < Iext && return "EXTINCT", ["mean I_d $(I["mean"]) A < 1e-3 x e sum(mdot_s/m_s) = $(Iext) A"]
    ood = String[]
    isempty(r["chemistry_unresolved_rate_files"]) || push!(ood, "DOM-AIR-01 unresolved tables $(r["chemistry_unresolved_rate_files"])")
    fx = r["chemistry_extrapolated_fraction_max"]
    (fx === nothing || num(fx) > CHEM_FOUT_TOL) && push!(ood, "DOM-AIR-01 table-limit activity share $(fx) ($(r["chemistry_limiting_rate_file"]))")
    fa = r["audit_domain_fraction_max"]
    num(fa) > CHEM_FOUT_TOL && push!(ood, "DOM-AIR-02 activity share above 45 eV $(fa) ($(r["audit_domain_limiting_rate_file"]))")
    isempty(ood) || return "OUT_OF_DOMAIN", ood
    r["sustained_v1"] == true || return "NOT_SUSTAINED", ["min I_d <= 0.01 x mean I_d over the window"]
    for (nm, s) in (("thrust", T), ("I_d", I))
        d = abs(s["half_means"][1] - s["half_means"][2])
        d > 0.02 * abs(s["mean"]) + 2 * 2 * s["se_batch"] && push!(why, "$(nm) half-means differ by $(d / abs(s["mean"]))")
    end
    isempty(why) || return "NON_STATIONARY", why
    for (nm, s) in (("thrust", T), ("I_d", I))
        s["se_batch"] / abs(s["mean"]) > 0.025 && push!(why, "$(nm) SE/mean $(s["se_batch"] / abs(s["mean"])) > 0.025")
    end
    isempty(why) || return "STATISTICALLY_UNRESOLVED", why
    return "PASS", String[]
end
status_class(s) = s in EVALUATED ? s : (s == "NOT_RUN" ? "NOT_RUN" : "UNKNOWN")

# A7 convergence of one case (A7-P vs A7-C) and its outcome.
function convergence(rp, rc, sp, sc)
    out = Dict{String,Any}("status_P" => sp, "status_C" => sc)
    if "NOT_RUN" in (sp, sc)
        out["outcome"] = "INCOMPLETE_NOT_RUN"
        return out
    end
    cp, cc = status_class(sp), status_class(sc)
    out["C-STATUS"] = cp == cc
    crit = Bool[out["C-STATUS"]]
    if cp in EVALUATED && cc in EVALUATED
        qp, qc = rp["discharge_current"]["rms_rel"] < 0.5, rc["discharge_current"]["rms_rel"] < 0.5
        out["C-QUIET"] = qp == qc
        push!(crit, out["C-QUIET"])
    end
    for (nm, k) in (("C-T", "thrust"), ("C-ID", "discharge_current"))
        sP, sC = getn(rp, k), getn(rc, k)
        (isnothing(sP) || isnothing(sC) || !fin(sP["mean"]) || !fin(sC["mean"])) && continue
        d = abs(sP["mean"] - sC["mean"])
        tol = 0.02 * abs(sC["mean"]) + 2 * sqrt(num(sP["se_batch"])^2 + num(sC["se_batch"])^2)
        blk = Dict{String,Any}("P" => sP["mean"], "C" => sC["mean"], "abs_diff" => d,
                               "rel_diff" => sC["mean"] != 0 ? d / abs(sC["mean"]) : nothing, "tolerance" => tol,
                               "applies" => sp == "PASS" && sc == "PASS")
        blk["pass"] = d <= tol
        out[nm] = blk
        blk["applies"] && push!(crit, blk["pass"])
    end
    out["outcome"] = cp == "UNKNOWN" && cc == "UNKNOWN" ? "PERSISTENT_UNKNOWN" :
                     (cp in EVALUATED && cc in EVALUATED && all(crit)) ? "CONVERGED_EVALUATED" : "NOT_CONVERGED"
    return out
end

# Headline numbers of one level (labelled with its status; never dropped).
function headline(r, c, status)
    isnothing(r) && return nothing
    T, I = getn(r, "thrust"), getn(r, "discharge_current")
    h = Dict{String,Any}("status" => status, "retcode" => r["retcode"], "wall_s" => get(r, "wall_total_s", nothing))
    (isnothing(T) || isnothing(I)) && return h
    mdot = Float64(c.mdot_kgps); Vd = Float64(c.Vd)
    Tm, Im = num(T["mean"]), num(I["mean"])
    h["thrust_mN"] = 1e3 * Tm
    h["thrust_se_mN"] = 1e3 * num(T["se_batch"])
    h["thrust_half_means_mN"] = 1e3 .* num.(T["half_means"])
    h["thrust_avgstate_mN_reported_only"] = 1e3 * num(r["thrust_avgstate_N"])
    h["Id_A"] = Im
    h["Id_se_A"] = num(I["se_batch"])
    h["Id_half_means_A"] = num.(I["half_means"])
    h["discharge_power_W"] = Im * Vd
    h["discharge_power_se_W"] = num(I["se_batch"]) * Vd
    h["ion_current_A"] = num(r["ion_current"]["mean"])
    h["Isp_s"] = Tm / (mdot * G0)
    h["eta_anode"] = Tm^2 / (2 * mdot * Vd * Im)
    h["eta_anode_framemean"] = r["anode_eff_framemean"]
    h["eta_total"] = nothing
    h["eta_total_reason"] = "NOT_EVALUATED: needs magnet, RF/ICP neutralizer, PPU and gas-path powers (bus_power_boundary_a9_v2); this package is Hall-discharge only"
    h["efficiency_decomposition"] = Dict(k => r[k] for k in ("mass_eff", "current_eff", "voltage_eff", "divergence_eff"))
    h["thrust_per_power_mN_per_kW"] = 1e3 * Tm / (Im * Vd) * 1e3
    osc(s, unit) = Dict("f_dominant_Hz" => s["f_dominant_Hz"], "rms_rel" => s["rms_rel"], "rms_abs_$(unit)" => s["rms_abs"],
                        "pp_rel" => s["pp_rel"], "min_$(unit)" => s["min"], "max_$(unit)" => s["max"],
                        "amp_dominant_$(unit)" => s["amp_dominant"], "tau_int_samples" => s["tau_int_samples"])
    h["oscillation"] = Dict("Id" => osc(I, "A"), "thrust" => osc(T, "N"), "quiet_class" => num(I["rms_rel"]) < 0.5,
                            "window_samples" => I["n_samples"], "window_s" => [r["window_start_s"], r["t_last_frame_s"]])
    h["stationarity"] = Dict("thrust_half_diff_rel" => abs(num(T["half_means"][1]) - num(T["half_means"][2])) / abs(Tm),
                             "Id_half_diff_rel" => abs(num(I["half_means"][1]) - num(I["half_means"][2])) / abs(Im),
                             "thrust_se_rel" => num(T["se_batch"]) / abs(Tm), "Id_se_rel" => num(I["se_batch"]) / abs(Im))
    h["plasma"] = Dict("Te_max_eV" => r["Te_max_eV"], "ne_max_m3" => r["ne_max_m3"],
                       "ion_exit_flux_fraction_by_gas" => r["ion_exit_flux_fraction_by_gas"])
    h["chemistry_domain"] = Dict(k => r[k] for k in ("chemistry_unresolved_rate_files", "chemistry_extrapolated_fraction_max",
                                                     "chemistry_limiting_rate_file", "chemistry_max_mean_energy_active_eV",
                                                     "audit_domain_fraction_max", "audit_domain_limiting_rate_file"))
    return h
end

function failure_block(r)
    isnothing(r) && return nothing
    Dict{String,Any}("retcode" => r["retcode"], "error" => get(r, "error", nothing), "t_last_frame_s" => get(r, "t_last_frame_s", nothing),
                     "collapse" => get(r, "collapse", nothing), "first_nonfinite" => get(r, "first_nonfinite", nothing),
                     "dt_limit_min_s" => get(r, "dt_limit_min_s", nothing))
end

function main()
    cases_path = joinpath(PKG, "cases_v1.json")
    doc = JSON3.read(read(cases_path, String))
    cases_sha = bytes2hex(open(sha256, cases_path))
    pre_path = joinpath(OUT, "preflight.json")
    pre = isfile(pre_path) ? JSON3.read(read(pre_path, String), Dict{String,Any}) : nothing
    recs = Dict{Tuple{String,String},Dict{String,Any}}()
    for f in readdir(joinpath(OUT, "runs"); join = true)
        endswith(f, ".json") || continue
        r = JSON3.read(read(f, String), Dict{String,Any})
        r["cases_file_sha256"] == cases_sha || error("$(f): run record from another case file")
        recs[(r["case_id"], r["level"])] = r
    end
    rows = []
    hosts, commits, jv = Set{String}(), Set{String}(), Set{String}()
    for c in doc.cases
        cid = String(c.case_id)
        rp, rc = get(recs, (cid, "A7-P"), nothing), get(recs, (cid, "A7-C"), nothing)
        for r in (rp, rc)
            isnothing(r) && continue
            r["case_sha256"] == c.case_sha256 || error("$(cid): case_sha256 mismatch")
            push!(hosts, r["host"]); push!(commits, r["hallthruster_commit"]); push!(jv, r["julia_version"])
        end
        sp, wp = run_status(rp, c)
        sc, wc = run_status(rc, c)
        conv = convergence(rp, rc, sp, sc)
        hp = headline(rp, c, sp)
        row = Dict{String,Any}(
            "case_id" => cid, "key" => String(c.key), "case_sha256" => String(c.case_sha256),
            "inputs" => Dict("composition" => merge(Dict("id" => String(c.composition_id)), Dict(String(k) => v for (k, v) in pairs(c.composition))),
                             "feed" => c.feed, "mdot_kg_s" => c.mdot_kgps, "mdot_mg_s" => round(1e6 * c.mdot_kgps; sigdigits = 12), "mdot_id" => String(c.mdot_id),
                             "Vd_V" => c.Vd, "Vd_id" => String(c.Vd_id), "B_operating_point" => c.B_operating_point,
                             "B_peak_id" => String(c.B_peak_id), "transport_id" => String(c.transport_id), "transport" => c.transport,
                             "geometry" => Dict("id" => String(c.geometry_id), "L_m" => c.L_m, "r_in_m" => c.r_in_m, "r_out_m" => c.r_out_m,
                                                "domain_m" => c.domain_m)),
            "status" => sp, "status_reasons" => wp, "status_check_level" => sc, "status_check_level_reasons" => wc,
            "outcome" => conv["outcome"],
            "result" => hp, "check_level_result" => headline(rc, c, sc), "convergence" => conv,
            "runtime_s" => Dict("A7-P" => isnothing(rp) ? nothing : rp["wall_total_s"], "A7-C" => isnothing(rc) ? nothing : rc["wall_total_s"],
                                "total" => sum((r["wall_total_s"] for r in (rp, rc) if !isnothing(r)); init = 0.0)),
            "failure" => Dict("A7-P" => sp == "PASS" ? nothing : failure_block(rp), "A7-C" => sc == "PASS" ? nothing : failure_block(rc)),
            "raw" => Dict("A7-P" => rp, "A7-C" => rc))
        push!(rows, row)
    end
    n_runs = length(recs)
    complete = all(r -> r["outcome"] != "INCOMPLETE_NOT_RUN", rows)
    count_by(f) = (d = Dict{String,Int}(); for r in rows; k = f(r); d[k] = get(d, k, 0) + 1; end; d)
    git = try
        (commit = readchomp(`git -C $(PKG) rev-parse HEAD`), dirty = !isempty(readchomp(`git -C $(PKG) status --porcelain -- $(PKG)`)))
    catch
        (commit = nothing, dirty = nothing)
    end
    res = Dict{String,Any}(
        "schema" => "abep_hall_air_rp1_results_v1", "package" => "hall_air_rp1_v1",
        "addendum" => "NP-HALL-PARAMETRIC-ENVELOPE A9-LP (prereg_addendum_a9_local_air_rp1_v1.json)",
        "owner_decision" => "A9.39 item 4", "layer" => "PARAMETRIC / NOT_VALIDATED", "labels" => doc.labels,
        "not" => ["not measured or demonstrated H1 performance (EM verification item)", "not a closure, selection or non-closure",
                  "not a validation: the transports are unadmitted screening candidates (credible set EMPTY)",
                  "AIR chemistry BOUNDED, not complete (BV-AIR-LL-NOM); literature values are never presented as measured",
                  "never pooled with surrogate-B(z) (BZ-P5B16 / P5B30) records"],
        "complete" => complete, "n_cases" => length(rows), "n_runs_expected" => 2 * length(rows), "n_runs_present" => n_runs,
        "summary" => Dict("by_status_production" => count_by(r -> r["status"]), "by_outcome" => count_by(r -> r["outcome"]),
                          "wall_s_total" => sum(r["runtime_s"]["total"] for r in rows)),
        "definitions" => Dict(
            "thrust" => "time-mean over the window (t >= average_start_s) of the per-frame instantaneous HallThruster.jl thrust(sol, i) (exit ion momentum flux minus anode term; no divergence correction); SE = batch means (10 contiguous batches)",
            "Id" => "time-mean of the per-frame discharge current over the window, batch-means SE",
            "discharge_power_W" => "mean I_d x V_d (discharge only)",
            "Isp_s" => "thrust / (mdot_anode x g0), g0 = 9.80665 m/s^2, mdot = total delivered anode flow of the case",
            "eta_anode" => "thrust^2 / (2 mdot V_d I_d) with the time-means (eta_anode_framemean = window mean of the solver's per-frame anode_eff, reported)",
            "eta_total" => "NOT_EVALUATED here (needs the non-discharge loads of bus_power_boundary_a9_v2)",
            "oscillation" => "over the window: dominant frequency of I_d and thrust (plain DFT, mean removed), RMS/|mean|, (max-min)/|mean|, integrated autocorrelation time in samples",
            "convergence" => "A7: production A7-P (0.25 mm cells) vs check A7-C (0.125 mm); C-STATUS, C-QUIET (Id_rms_rel < 0.5), C-T and C-ID |X_P - X_C| <= 0.02 |X_C| + 2 sqrt(SE_P^2 + SE_C^2) when both PASS",
            "stationarity" => "half-window means: NON_STATIONARY when |h1 - h2| > 0.02 |mean| + 4 SE (thrust or I_d)",
            "status_precedence" => "NUMERICAL_FAILURE > EXTINCT > OUT_OF_DOMAIN > NOT_SUSTAINED > NON_STATIONARY > STATISTICALLY_UNRESOLVED > PASS; NOT_RUN if absent",
            "EXTINCT" => "mean I_d < 1e-3 x e x sum_s(mdot_s / m_s) (A7 rule with the AIR feed in place of Xe)",
            "OUT_OF_DOMAIN" => "A1 DOM-AIR-01 (table-limit activity share > 1e-12 or unresolved table) or DOM-AIR-02 (activity above 45 eV mean energy > 1e-12); numbers are still reported, as information",
            "collapse" => "failure / collapse diagnostics per level: retcode and solver error; t_Id_below_1pct_of_running_max_s = first time after 5 % of the run at which I_d < 1 % of its running maximum (deep breathing can also trigger it); collapse_detected = last-frame I_d < 1 % of the series maximum, last-frame n_e,min < 1e12 m^-3, or a non-finite last-frame I_d; first_nonfinite = first saved frame / variable / cell / z with a non-finite value",
            "evaluated_physics" => "PASS and NOT_SUSTAINED; every other status is an unknown",
            "case_outcome" => "CONVERGED_EVALUATED / PERSISTENT_UNKNOWN / NOT_CONVERGED (A7); INCOMPLETE_NOT_RUN if a level is missing",
            "headline_level" => "result = A7-P (production); check_level_result = A7-C"),
        "provenance" => Dict(
            "hosts" => collect(hosts), "hallthruster_commits" => collect(commits), "julia_versions" => collect(jv),
            "aggregated_on" => Libc.gethostname(), "utc_generated" => string(Dates.now(Dates.UTC)),
            "os" => "$(Sys.KERNEL) $(Sys.MACHINE)", "cpu" => Sys.cpu_info()[1].model, "cpu_threads" => Sys.CPU_THREADS,
            "memory_GB" => round(Sys.total_memory() / 2^30; digits = 1), "cases_file_sha256" => cases_sha,
            "git_commit" => git.commit, "git_package_dirty" => git.dirty, "preflight" => pre),
        "cases" => rows)
    open(joinpath(OUT, "hall_air_rp1_v1_results.json"), "w") do io
        JSON3.pretty(io, JSON3.write(json_safe(res)), JSON3.AlignmentContext(indent = 1))
        println(io)
    end
    cols = ["case_id", "composition", "mdot_mg_s", "Vd_V", "B_peak_id", "B_peak_G", "coil_NI_A_turns", "transport_id", "status",
            "outcome", "thrust_mN", "thrust_se_mN", "Id_A", "Id_se_A", "P_d_W", "Isp_s", "eta_anode", "Id_f_dom_Hz", "Id_rms_rel",
            "Id_pp_rel", "thrust_C_mN", "dT_rel_PC", "Id_C_A", "dId_rel_PC", "status_C", "wall_P_s", "wall_C_s"]
    g(h, k) = isnothing(h) ? "" : string(something(get(h, k, ""), ""))
    open(joinpath(OUT, "hall_air_rp1_v1_results.csv"), "w") do io
        println(io, join(cols, ","))
        for r in rows
            h, hc, cv, inp = r["result"], r["check_level_result"], r["convergence"], r["inputs"]
            osc = isnothing(h) ? nothing : get(h, "oscillation", nothing)
            v = [r["case_id"], inp["composition"]["id"], inp["mdot_mg_s"], inp["Vd_V"], inp["B_peak_id"], inp["B_operating_point"].B_peak_G,
                 inp["B_operating_point"].coil_NI_total_A_turns, inp["transport_id"], r["status"], r["outcome"], g(h, "thrust_mN"),
                 g(h, "thrust_se_mN"), g(h, "Id_A"), g(h, "Id_se_A"), g(h, "discharge_power_W"), g(h, "Isp_s"), g(h, "eta_anode"),
                 isnothing(osc) ? "" : osc["Id"]["f_dominant_Hz"], isnothing(osc) ? "" : osc["Id"]["rms_rel"],
                 isnothing(osc) ? "" : osc["Id"]["pp_rel"], g(hc, "thrust_mN"),
                 haskey(cv, "C-T") ? cv["C-T"]["rel_diff"] : "", g(hc, "Id_A"), haskey(cv, "C-ID") ? cv["C-ID"]["rel_diff"] : "",
                 r["status_check_level"], something(r["runtime_s"]["A7-P"], ""), something(r["runtime_s"]["A7-C"], "")]
            println(io, join(string.(v), ","))
        end
    end
    println("wrote $(joinpath(OUT, "hall_air_rp1_v1_results.json")) ($(n_runs) / $(2 * length(rows)) runs, complete = $(complete))")
end

json_safe(x::AbstractFloat) = isfinite(x) ? x : string(x)
json_safe(x::AbstractDict) = Dict{String,Any}(string(k) => json_safe(v) for (k, v) in x)
json_safe(x::JSON3.Object) = Dict{String,Any}(string(k) => json_safe(v) for (k, v) in pairs(x))
json_safe(x::AbstractVector) = [json_safe(v) for v in x]
json_safe(x::Tuple) = [json_safe(v) for v in x]
json_safe(x) = x

main()
