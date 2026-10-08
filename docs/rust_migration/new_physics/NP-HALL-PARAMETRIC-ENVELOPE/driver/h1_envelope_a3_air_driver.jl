# NP-HALL-PARAMETRIC-ENVELOPE addendum A3 (numerics adequacy, RG-04), AIR scope by reference. PARAMETRIC / NOT_VALIDATED.
# Runs the Rust-generated A3 AIR case file (cases/h1_parametric_envelope_a3_numerics_air_cases_v1.json: the 17 seeded AIR
# check cases at R0 = v1 numerics, R1 = 2 x cells, R3 = 2 x duration) through hallthruster_bridge/air_bridge_lib.jl
# run_case_air in vacuum mode under the committed addendum A1 AIR launch manifest (LP-BOUNDED BV-AIR-LL-NOM today: every
# record carries chemistry_mode and the BV fields; information only) and records raw observables only.
#   julia --project=hallthruster_bridge docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/h1_envelope_a3_air_driver.jl \
#         <out.jsonl> <shard> <nshards>
# Refuses unless the HallThruster.jl pin, the A3 lock and its files, the A1 lock and its files, the A1 AIR launch manifest
# and every file it pins (both Julia libraries, AIR_PINNED.toml, the configuration, the validity file, every rate file,
# chemistry addendum 03 for LP-BOUNDED), the A3 AIR case file and this driver match launch_manifest_a3_numerics_air_v1.json.
# Resumable (skips keys already in out.jsonl).
include(joinpath(@__DIR__, "..", "..", "..", "..", "..", "hallthruster_bridge", "air_bridge_lib.jl"))
using SHA
using Dates
rev = check_pin()
sha(p) = bytes2hex(open(sha256, p))
const NPDIR = normpath(joinpath(@__DIR__, ".."))
const REPO = normpath(joinpath(NPDIR, "..", "..", "..", ".."))
const BRIDGE = joinpath(REPO, "hallthruster_bridge")
a3m = JSON3.read(read(joinpath(NPDIR, "launch_manifest_a3_numerics_air_v1.json"), String))
a3_lock_sha = sha(joinpath(NPDIR, "prereg_addendum_a3_numerics_lock_v1.json"))
a3_lock_sha == a3m.addendum_lock_sha256 || error("A3 lock does not match the A3 AIR launch manifest")
for lockname in ("prereg_addendum_a3_numerics_lock_v1.json", "prereg_addendum_a1_air_family_lock.json")
    lk = JSON3.read(read(joinpath(NPDIR, lockname), String))
    for (f, h) in pairs(lk.files)
        sha(joinpath(NPDIR, String(f))) == h || error("$(lockname) mismatch: $(f)")
    end
end
lm_path = joinpath(NPDIR, "launch_manifest_air_v1.json")
isfile(lm_path) || error("AIR launch gate closed: no launch_manifest_air_v1.json")
sha(lm_path) == a3m.air_launch_manifest_sha256 || error("AIR launch manifest does not match the A3 AIR launch manifest")
man = JSON3.read(read(lm_path, String))
a1_lock_sha = sha(joinpath(NPDIR, "prereg_addendum_a1_air_family_lock.json"))
a1_lock_sha == man.addendum_lock_sha256 || error("A1 lock does not match the AIR launch manifest")
sha(joinpath(BRIDGE, "air_bridge_lib.jl")) == man.air_bridge_lib_sha256 || error("air_bridge_lib.jl changed")
sha(joinpath(BRIDGE, "bridge_lib.jl")) == man.bridge_lib_sha256 || error("bridge_lib.jl changed")
air_pinned_sha = sha(joinpath(BRIDGE, "propellants_air", "AIR_PINNED.toml"))
air_pinned_sha == man.air_pinned_sha256 || error("AIR_PINNED.toml changed since the launch manifest")
config_sha = sha(joinpath(BRIDGE, String(man.air_config)))
config_sha == man.air_config_sha256 || error("AIR configuration changed since the launch manifest")
sha(joinpath(BRIDGE, "propellants_air", "rate_validity.toml")) == man.rate_validity_sha256 || error("rate_validity.toml changed")
for (f, h) in pairs(man.rate_files)
    sha(joinpath(BRIDGE, "propellants_air", String(f))) == h || error("rate file $(f) changed")
end
chem_mode = String(man.chemistry_mode)
chem_mode in ("COMPLETE", "BOUNDED_VARIANT") || error("unknown chemistry_mode $(chem_mode) in the AIR launch manifest")
bv(k) = chem_mode == "BOUNDED_VARIANT" ? String(man[k]) : nothing
if chem_mode == "BOUNDED_VARIANT"
    CH = joinpath(REPO, "docs", "rust_migration", "new_physics", "NP-HALL-CHEM-AIR")
    sha(joinpath(CH, "addendum_03_bounded_treatment.json")) == man.chem_addendum_03_sha256 || error("chem addendum 03 changed")
    sha(joinpath(CH, "addendum_03_lock.json")) == man.chem_addendum_03_lock_sha256 || error("chem addendum 03 lock changed")
end
driver_sha = sha(@__FILE__)
driver_sha == a3m.driver_sha256 || error("driver does not match the A3 AIR launch manifest")
cases_path = joinpath(REPO, String(a3m.cases))
cases_sha = sha(cases_path)
cases_sha == a3m.cases_sha256 || error("A3 AIR case file does not match the A3 AIR launch manifest")
doc = JSON3.read(read(cases_path, String))
doc.addendum_lock_sha256 == a3_lock_sha || error("A3 AIR case file was generated under another A3 lock")
doc.air_launch_manifest_sha256 == a3m.air_launch_manifest_sha256 || error("A3 AIR case file was generated under another AIR launch manifest")

out_path = ARGS[1]
shard = parse(Int, ARGS[2])
nshards = parse(Int, ARGS[3])
nshards == a3m.n_shards || error("n_shards $(nshards) != A3 AIR launch manifest $(a3m.n_shards)")
0 <= shard < nshards || error("shard $(shard) outside 0..$(nshards - 1)")
done = Set{String}()
isfile(out_path) && for l in eachline(out_path); isempty(strip(l)) || push!(done, String(JSON3.read(l).key)); end
threads = Dict(k => get(ENV, k, nothing) for k in ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"))
const KEEP = ("retcode", "converged", "finite", "t_end_s", "sustained", "quasi_steady", "thrust_N", "discharge_current_A",
              "discharge_power_W", "ion_current_A", "anode_eff", "mass_eff", "current_eff", "voltage_eff", "divergence_eff",
              "Te_max_eV", "ne_max_m3", "Id_rms_rel", "Id_pp_rel", "Id_f_dominant_Hz", "Id_min_A", "Id_max_A", "B_max_T", "B_scale",
              "B_peak_minus_exit_m", "ion_species_fraction_atomic", "ion_exit_flux_fraction_by_gas", "wall_ion_basis",
              "chemistry_unresolved_rate_files", "chemistry_per_reaction", "chemistry_extrapolated_fraction_max",
              "chemistry_limiting_rate_file", "chemistry_trustworthy", "audit_domain_fraction_max", "audit_domain_limiting_rate_file",
              "air_in_domain", "feed_used", "transport", "error")
for (i, c) in enumerate(doc.cases)
    (i - 1) % nshards == shard || continue
    key = String(c.key)
    key in done && continue
    rec = Dict{String,Any}("key" => key, "family" => String(c.family), "composition_id" => String(c.composition_id),
                           "case_sha256" => String(c.case_sha256), "a3_refinement" => String(c.a3_refinement),
                           "v1_key" => String(c.v1_key), "v1_case_sha256" => String(c.v1_case_sha256), "cells" => c.cells,
                           "duration_s" => c.duration_s, "cases_file_sha256" => cases_sha,
                           "addendum_lock_sha256" => a3_lock_sha, "a1_addendum_lock_sha256" => a1_lock_sha,
                           "prereg_lock_sha256" => sha(joinpath(NPDIR, "prereg_lock_v1.json")), "driver_sha256" => driver_sha,
                           "air_label" => String(man.air_label), "air_pinned_sha256" => air_pinned_sha,
                           "air_config_sha256" => config_sha, "chemistry_mode" => chem_mode,
                           "chemistry_bound_set" => bv(:chemistry_bound_set),
                           "chemistry_bound_member" => bv(:chemistry_bound_member),
                           "chemistry_bound_label" => bv(:chemistry_bound_label), "hallthruster_commit" => rev,
                           "hallthruster_version" => string(pkgversion(het)), "julia_version" => string(VERSION),
                           "threads_blas" => threads, "host" => Libc.gethostname(), "utc_start" => string(Dates.now(Dates.UTC)),
                           "layer" => "PARAMETRIC / NOT_VALIDATED")
    t0 = time()
    try
        LAST_SOL[] = nothing
        r = run_case_air(c)
        for k in KEEP
            haskey(r, k) && (rec[k] = r[k])
        end
        haskey(rec, "finite") || (rec["finite"] = false)
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
