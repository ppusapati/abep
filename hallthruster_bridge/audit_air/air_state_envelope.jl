# CA-HALL-AIR-v1 blind state envelope (NP-HALL-CHEM-AIR v1 + addendum 01). STATUS: PREPARED_NOT_RUN.
# Runs the 576 Rust-generated audit cases (air_state_envelope_cases_v1.json: G-RP1, BZ-P5B16, BP-LO/HI, VD-180/350,
# MF-LO/HI, 4 composition corners, sgb-screen-01..09, AIR-NOM / AIR-ALT snapshot configurations) through run_case_air and
# records only chemistry-state sums: per saved frame of the averaging window, reaction-weighted activities
# R = sum_i n_e n_target k(3/2 T_e) dz_i of every included channel class (denominators) and of every bound process, plus the
# channel-wall recombination rates at gamma = 1. The per-frame maxima of the addendum-01 metrics are computed here; the
# window metrics, bounds and verdicts are computed by the Rust reader (abep-air-cases audit-verdicts) from the frozen file.
# No thrust, current or efficiency is written. This is NOT a validation and decides nothing by itself.
#   julia --project=hallthruster_bridge hallthruster_bridge/audit_air/air_state_envelope.jl <out.jsonl> <shard> <nshards>
# Refuses to run unless the pin, the snapshot MANIFEST (configurations, rate files, bound tables, case file) and the
# addendum-01 lock match. Resumable (skips keys already in out.jsonl).
include(joinpath(@__DIR__, "..", "air_bridge_lib.jl"))
using SHA
using Dates
rev = check_pin()
sha(p) = bytes2hex(open(sha256, p))
const AUDIT = @__DIR__
const BRIDGE = normpath(joinpath(@__DIR__, ".."))
const REPO = normpath(joinpath(BRIDGE, ".."))
man = JSON3.read(read(joinpath(AUDIT, "configs", "MANIFEST.json"), String))
sha(joinpath(REPO, String(man.addendum_lock))) == man.addendum_lock_sha256 || error("NP-HALL-CHEM-AIR addendum-01 lock changed")
for (name, e) in pairs(man.configs)
    sha(joinpath(AUDIT, "configs", String(name))) == e.sha256 || error("snapshot $(name) changed")
    for (f, h) in pairs(e.rate_files)
        sha(joinpath(BRIDGE, "propellants_air", String(f))) == h || error("rate file $(f) of $(name) changed")
    end
end
for (f, h) in pairs(man.bound_tables)
    sha(joinpath(BRIDGE, String(f))) == h || error("bound table $(f) changed")
end
cases_path = joinpath(AUDIT, "air_state_envelope_cases_v1.json")
cases_sha = sha(cases_path)
cases_sha == man.cases_sha256 || error("audit case file does not match the MANIFEST")
doc = JSON3.read(read(cases_path, String))
manifest_sha = sha(joinpath(AUDIT, "configs", "MANIFEST.json"))
script_sha = sha(@__FILE__)

out_path = ARGS[1]
shard = parse(Int, ARGS[2])
nshards = parse(Int, ARGS[3])
0 <= shard < nshards || error("shard $(shard) outside 0..$(nshards - 1)")
done = Set{String}()
isfile(out_path) && for l in eachline(out_path); isempty(strip(l)) || push!(done, String(JSON3.read(l).key)); end
threads = Dict(k => get(ENV, k, nothing) for k in ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"))

# Bound processes (addendum 01): id => (header energy, rate table, reactant gas, reactant charge).
function bound(rel, gas, Z)
    E, k = het.load_rate_coeff_file(joinpath(BRIDGE, rel), "electron_impact")
    return (E=E, k=k, gas=gas, Z=Z)
end
const BOUND = [
    "HA-O2-DI-02" => bound("audit_air/bound_tables/dissociative_ionization_O2_to_O_Z2plus_song2026.dat", :O2, 0),
    "HA-O2-ATT-01" => bound("audit_air/bound_tables/attachment_O2_song2026.dat", :O2, 0),
    "HA-N2N-R1" => bound("audit/bound_tables/ionization_N_Z2plus_to_N_Z3plus_bell1983.dat", :N, 2),
    "HA-N2N-R2:nominal" => bound("audit/bound_tables/ionization_N2_to_N2_Z2plus_nominal.dat", :N2, 0),
    "HA-N2N-R2:upper" => bound("audit/bound_tables/ionization_N2_to_N2_Z2plus_upper.dat", :N2, 0),
    "HA-N2N-R3" => bound("audit/bound_tables/ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.dat", :N2, 1),
]
# The assessed processes must not be in the configuration that generates the state (snapshot rule).
const ASSESSED = r"(O2_to_O_Z2plus|attachment_O2|N_Z2plus_to_N_Z3plus|N2_to_N2_Z2plus|N2_Z1plus_to_N2_Z2plus)"

# "2e" -> (sym = "e", Z = -1, n = 2); "N(2+)" -> ("N", 2, 1); "O2(+)" -> ("O2", 1, 1).
function air_term(t)
    m = match(r"^(\d*)([A-Za-z][A-Za-z0-9]*?)(?:\((\d*)([+-])\))?$", strip(t))
    isnothing(m) && error("cannot parse term \"$t\"")
    n = isempty(m[1]) ? 1 : parse(Int, m[1])
    Z = isnothing(m[4]) ? 0 : (isempty(m[3]) ? 1 : parse(Int, m[3])) * (m[4] == "+" ? 1 : -1)
    return (sym=String(m[2]), Z=m[2] == "e" ? -1 : Z, n=n)
end

# Included channels of a configuration: kind, target, charge, table, header energy, ionizing flag, electrons produced, heavy
# products (from the equation).
function included_channels(c)
    cfg = TOML.parsefile(joinpath(BRIDGE, c.propellant_config))
    ch = []
    for r in cfg["reactions"]
        typ = r["type"]
        f = r["rate_coeff_file"]
        occursin(ASSESSED, f) && error("$(c.propellant_config) already contains assessed process $(f)")
        E, k = het.load_rate_coeff_file(joinpath(BRIDGE, c.rate_dir, f), typ)
        if typ == "electron_impact"
            gas, Z = reactant_term(r["equation"])
            rhs = [air_term(t) for t in split(split(r["equation"], "->")[2], r"\s\+\s")]
            heavy = [t for t in rhs if t.sym != "e"]
            e_out = sum((t.n for t in rhs if t.sym == "e"); init=0)
            push!(ch, (typ=typ, gas=Symbol(gas), Z=Z, k=k, E=E, ionizing=any(t.Z != Z for t in heavy), nu_e=e_out - 1, heavy=heavy))
        else
            push!(ch, (typ=typ, gas=Symbol(r["target_species"]), Z=0, k=k, E=E, ionizing=false, nu_e=0, heavy=[]))
        end
    end
    return ch
end

const SUM_KEYS = ["R_ion", "R_e", "P_inel", "D_O2", "D_O", "D_N", "S_NZ2", "S_N2Z1", "W:HA-WALL-02", "W:HA-WALL-03",
                  [("R:" * id) for (id, _) in BOUND]...]

# Per-frame sums of one saved frame (cells weighted by width; the 1-D area is constant).
function frame_sums(f, z, dz, ch, c, vbar)
    s = Dict(k => 0.0 for k in SUM_KEYS)
    wall = 2.0 / (c.r_out_m - c.r_in_m)
    dens = [reactant_density(f, q.gas, q.Z) for q in ch]
    bdens = [reactant_density(f, b.gas, b.Z) for (_, b) in BOUND]
    nO = f.neutrals[:O].n
    nN = f.neutrals[:N].n
    for i in eachindex(z)
        eps = 1.5 * f.Tev[i]
        w = f.ne[i] * dz[i]
        for (q, n) in zip(ch, dens)
            q.typ == "elastic" && continue
            R = w * n[i] * rate_at(q.k, eps)
            s["P_inel"] += R * q.E
            q.typ == "electron_impact" || continue
            if q.ionizing
                s["R_ion"] += R
                s["R_e"] += q.nu_e * R
            end
            q.Z == 0 && q.gas in (:O2, :O, :N) && (s["D_$(q.gas)"] += R)
            for t in q.heavy
                t.sym == "N" && t.Z == 2 && (s["S_NZ2"] += t.n * R)
                t.sym == "N2" && t.Z == 1 && (s["S_N2Z1"] += t.n * R)
            end
        end
        for ((id, b), n) in zip(BOUND, bdens)
            s["R:" * id] += w * n[i] * rate_at(b.k, eps)
        end
        if z[i] <= c.L_m
            s["W:HA-WALL-02"] += nO[i] * vbar[:O] / 4 * wall * dz[i]
            s["W:HA-WALL-03"] += nN[i] * vbar[:N] / 4 * wall * dz[i]
        end
    end
    return s
end

ratio(a, b) = b > 0 ? a / b : (a > 0 ? Inf : 0.0)
# Addendum-01 metrics of one set of sums (window or frame): "process|metric|member" => value.
function metrics(s)
    m = Dict{String,Float64}()
    hdr = Dict(id => b.E for (id, b) in BOUND)
    for (u, mem) in ((0.9, "lower"), (1.0, "nominal"), (1.1, "upper"))
        R = u * s["R:HA-O2-DI-02"]
        m["HA-O2-DI-02|F_ion|$mem"] = ratio(R, s["R_ion"] + R)
        m["HA-O2-DI-02|F_P|$mem"] = ratio(R * hdr["HA-O2-DI-02"], s["P_inel"] + R * hdr["HA-O2-DI-02"])
        m["HA-O2-DI-02|F_S(O2 destruction)|$mem"] = ratio(R, s["D_O2"] + R)
        R = u * s["R:HA-N2N-R1"]
        m["HA-N2N-R1|F_ion|$mem"] = ratio(R, s["R_ion"] + R)
        m["HA-N2N-R1|F_P|$mem"] = ratio(R * hdr["HA-N2N-R1"], s["P_inel"] + R * hdr["HA-N2N-R1"])
        m["HA-N2N-R1|F_S(N^2+ destruction)|$mem"] = ratio(R, s["S_NZ2"])
    end
    for (u, mem) in ((0.8, "lower"), (1.0, "nominal"), (1.2, "upper"))
        R = u * s["R:HA-O2-ATT-01"]
        m["HA-O2-ATT-01|F_e_loss|$mem"] = ratio(R, s["R_e"])
        m["HA-O2-ATT-01|F_S(O2 destruction)|$mem"] = ratio(R, s["D_O2"] + R)
    end
    for (u, mem) in ((0.86, "lower"), (1.0, "nominal"), (1.11, "upper"))
        R = u * s["R:HA-N2N-R3"]
        m["HA-N2N-R3|F_ion|$mem"] = ratio(R, s["R_ion"] + R)
        m["HA-N2N-R3|F_S(N2+ destruction)|$mem"] = ratio(R, s["S_N2Z1"])
    end
    for (key, mem) in (("HA-N2N-R2:nominal", "lower"), ("HA-N2N-R2:nominal", "nominal"), ("HA-N2N-R2:upper", "upper"))
        R = s["R:" * key]
        m["HA-N2N-R2|F_ion|$mem"] = ratio(R, s["R_ion"] + R)
        m["HA-N2N-R2|F_P|$mem"] = ratio(R * hdr[key], s["P_inel"] + R * hdr[key])
    end
    for (id, gas) in (("HA-WALL-02", "O"), ("HA-WALL-03", "N"))
        W = s["W:" * id]
        m["$id|F_S($gas destruction)|lower"] = 0.0
        m["$id|F_S($gas destruction)|upper"] = ratio(W, s["D_$gas"] + W)
    end
    return m
end

for (i, c) in enumerate(doc.cases)
    (i - 1) % nshards == shard || continue
    key = String(c.key)
    key in done && continue
    rec = Dict{String,Any}("key" => key, "case_sha256" => String(c.case_sha256), "cases_file_sha256" => cases_sha,
                           "manifest_sha256" => manifest_sha, "script_sha256" => script_sha, "config" => String(c.chemistry_id),
                           "composition_id" => String(c.composition_id), "transport_id" => String(c.transport_id),
                           "hallthruster_commit" => rev, "hallthruster_version" => string(pkgversion(het)),
                           "julia_version" => string(VERSION), "threads_blas" => threads, "host" => Libc.gethostname(),
                           "utc_start" => string(Dates.now(Dates.UTC)), "status" => "AUDIT_STATE_ENVELOPE_NOT_A_VALIDATION")
    t0 = time()
    try
        ch = included_channels(c)
        LAST_SOL[] = nothing
        r = run_case_air(c)
        for k in ("retcode", "converged", "finite", "sustained", "chemistry_unresolved_rate_files", "chemistry_extrapolated_fraction_max",
                  "chemistry_limiting_rate_file", "audit_domain_fraction_max", "audit_domain_limiting_rate_file", "air_in_domain",
                  "Te_max_eV", "error")
            haskey(r, k) && (rec[k] = r[k])
        end
        sol = LAST_SOL[]
        if r["retcode"] == "success" && !isnothing(sol)
            i0 = findfirst(>=(c.average_start_s), sol.t)
            z = collect(sol.grid)
            dz = [(z[min(j + 1, end)] - z[max(j - 1, 1)]) / (j == 1 || j == length(z) ? 1 : 2) for j in eachindex(z)]
            vbar = Dict(g => sqrt(8 * het.kB * 500.0 / (π * het.Gas(String(g)).m)) for g in (:O, :N))
            win = Dict(k => 0.0 for k in SUM_KEYS)
            fmax = Dict{String,Float64}()
            for f in sol.frames[i0:end]
                s = frame_sums(f, z, dz, ch, c, vbar)
                for (k, v) in s
                    win[k] += v
                end
                for (k, v) in metrics(s)
                    fmax[k] = max(get(fmax, k, -Inf), v)
                end
            end
            rec["sums"] = win
            rec["headers"] = Dict(id => b.E for (id, b) in BOUND)
            rec["frame_max"] = fmax
            rec["n_frames"] = length(sol.frames) - i0 + 1
        end
    catch err
        rec["retcode"] = "error"; rec["error"] = sprint(showerror, err); rec["finite"] = false
    end
    rec["wall_s"] = time() - t0
    open(out_path, "a") do io
        JSON3.write(io, rec); println(io)
    end
    println(key, "  ", get(rec, "retcode", "?"))
    flush(stdout)
end
