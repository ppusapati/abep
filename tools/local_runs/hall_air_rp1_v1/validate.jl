# hall_air_rp1_v1 result-file validator. Exit 0 = valid, 1 = invalid (every problem is listed).
#   julia --project=hallthruster_bridge tools/local_runs/hall_air_rp1_v1/validate.jl <hall_air_rp1_v1_results.json> [--require-complete]
# Checks results_schema_v1.json (JSON-Schema subset: type, required, properties, items, enum, const, minimum, minItems) and
# the package rules: the case set equals cases_v1.json, every record names the pinned HallThruster.jl commit, the labels are
# present, counts and the completeness flag are consistent, and a case with evaluated physics carries its observables.
using JSON3
using SHA

const PKG = @__DIR__
errs = String[]

jtype(x) = x === nothing ? "null" : x isa Bool ? "boolean" : x isa Integer ? "integer" : x isa Number ? "number" :
           x isa AbstractString ? "string" : x isa AbstractVector ? "array" : (x isa AbstractDict || x isa JSON3.Object) ? "object" : "unknown"
type_ok(x, t::AbstractString) = (jt = jtype(x); jt == t || (t == "number" && jt == "integer"))
type_ok(x, ts) = any(t -> type_ok(x, t), ts)
haskey_(o, k) = o isa JSON3.Object ? haskey(o, Symbol(k)) : haskey(o, k)
get_(o, k) = o isa JSON3.Object ? o[Symbol(k)] : o[k]

function check(x, s, path)
    if haskey_(s, "const")
        x == get_(s, "const") || push!(errs, "$(path): expected $(get_(s, "const")), got $(x)")
    end
    if haskey_(s, "enum")
        x in get_(s, "enum") || push!(errs, "$(path): $(x) not in $(collect(get_(s, "enum")))")
    end
    if haskey_(s, "type")
        t = get_(s, "type")
        type_ok(x, t isa AbstractString ? t : collect(t)) || (push!(errs, "$(path): type $(jtype(x)) not $(t)"); return)
    end
    if haskey_(s, "minimum") && x isa Number
        x >= get_(s, "minimum") || push!(errs, "$(path): $(x) < minimum $(get_(s, "minimum"))")
    end
    if jtype(x) == "object"
        if haskey_(s, "required")
            for k in get_(s, "required")
                haskey_(x, k) || push!(errs, "$(path): missing required '$(k)'")
            end
        end
        if haskey_(s, "properties")
            for (k, sub) in pairs(get_(s, "properties"))
                haskey_(x, String(k)) && check(get_(x, String(k)), sub, "$(path)/$(k)")
            end
        end
    elseif jtype(x) == "array"
        haskey_(s, "minItems") && length(x) < get_(s, "minItems") && push!(errs, "$(path): fewer than $(get_(s, "minItems")) items")
        if haskey_(s, "items")
            for (i, v) in enumerate(x)
                check(v, get_(s, "items"), "$(path)/$(i - 1)")
            end
        end
    end
end

function main()
    isempty(ARGS) && error("usage: validate.jl <results.json> [--require-complete]")
    res = JSON3.read(read(ARGS[1], String))
    schema = JSON3.read(read(joinpath(PKG, "results_schema_v1.json"), String))
    check(res, schema, "")
    isempty(errs) || return
    cases = JSON3.read(read(joinpath(PKG, "cases_v1.json"), String))
    cases_sha = bytes2hex(open(sha256, joinpath(PKG, "cases_v1.json")))
    res.provenance.cases_file_sha256 == cases_sha || push!(errs, "cases_file_sha256 differs from this package's cases_v1.json")
    want = Dict(String(c.case_id) => String(c.case_sha256) for c in cases.cases)
    got = Dict(String(c.case_id) => String(c.case_sha256) for c in res.cases)
    want == got || push!(errs, "case set / case_sha256 differ from cases_v1.json")
    res.n_cases == length(want) || push!(errs, "n_cases $(res.n_cases) != $(length(want))")
    res.n_runs_expected == 2 * length(want) || push!(errs, "n_runs_expected inconsistent")
    nraw = sum(count(lv -> res.cases[i].raw[Symbol(lv)] !== nothing, ("A7-P", "A7-C")) for i in eachindex(res.cases))
    res.n_runs_present == nraw || push!(errs, "n_runs_present $(res.n_runs_present) != raw records $(nraw)")
    complete = all(c -> c.outcome != "INCOMPLETE_NOT_RUN", res.cases)
    res.complete == complete || push!(errs, "complete flag inconsistent")
    "--require-complete" in ARGS && !complete && push!(errs, "result file is not complete")
    for lab in ("PARAMETRIC / NOT_VALIDATED", "B(z) FE-DERIVED NOT MEASURED")
        lab in res.labels || push!(errs, "label missing: $(lab)")
    end
    any(l -> occursin("AIR_CHEMISTRY_BOUNDED_NOT_COMPLETE", l), res.labels) || push!(errs, "AIR chemistry BOUNDED label missing")
    for c in res.cases
        for lv in ("A7-P", "A7-C")
            r = c.raw[Symbol(lv)]
            r === nothing && continue
            r.hallthruster_commit == "bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5" || push!(errs, "$(c.case_id) $(lv): HallThruster commit $(r.hallthruster_commit)")
            r.level == lv || push!(errs, "$(c.case_id) $(lv): level mismatch")
        end
        if c.status in ("PASS", "NOT_SUSTAINED")
            for k in ("thrust_mN", "thrust_se_mN", "Id_A", "Id_se_A", "discharge_power_W", "Isp_s", "eta_anode", "oscillation")
                haskey(c.result, Symbol(k)) && c.result[Symbol(k)] isa Union{Number,JSON3.Object} ||
                    push!(errs, "$(c.case_id): evaluated case without $(k)")
            end
        end
        (c.raw[Symbol("A7-P")] === nothing) == (c.status == "NOT_RUN") || push!(errs, "$(c.case_id): NOT_RUN inconsistent with the record")
    end
end

main()
if isempty(errs)
    println("VALID: $(ARGS[1])")
else
    println(stderr, "INVALID: $(ARGS[1])\n  " * join(errs, "\n  "))
    exit(1)
end
