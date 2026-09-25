# Offline driver: julia --project=hallthruster_bridge hallthruster_bridge/run_cases.jl cases/p5_xenon.json out/p5_xenon.json
include(joinpath(@__DIR__, "bridge_lib.jl"))

rev = check_pin()
cases = JSON3.read(read(ARGS[1], String))
check_reaction_sets(cases)
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
