# hall_air_rp1_v1 preflight: refuses (exit 1) unless the Julia version, the HallThruster.jl pin and every package / input file
# match. Writes <out>/preflight.json (copied into the result file's provenance).
#   julia --project=hallthruster_bridge tools/local_runs/hall_air_rp1_v1/preflight.jl <out_dir> <jobs>
include(joinpath(@__DIR__, "..", "..", "..", "hallthruster_bridge", "bridge_lib.jl"))
using SHA
using Dates
using LinearAlgebra

const PKG = @__DIR__
const REPO = normpath(joinpath(PKG, "..", "..", ".."))
const JULIA_REQUIRED = v"1.11.7"
sha(p) = bytes2hex(open(sha256, p))

out, jobs = ARGS[1], ARGS[2]
problems = String[]
allow_julia = get(ENV, "ABEP_ALLOW_OTHER_JULIA", "0") == "1"
VERSION == JULIA_REQUIRED || (allow_julia ? @warn("Julia $(VERSION) != $(JULIA_REQUIRED): allowed by ABEP_ALLOW_OTHER_JULIA=1 and recorded") :
                              push!(problems, "Julia $(VERSION) != required $(JULIA_REQUIRED) (the pinned Manifest was resolved with it)"))
rev = try
    check_pin()
catch err
    push!(problems, sprint(showerror, err)); nothing
end
man_path = joinpath(PKG, "package_manifest_v1.json")
man = JSON3.read(read(man_path, String))
for (f, h) in pairs(man.package_files)
    p = joinpath(PKG, String(f))
    isfile(p) || (push!(problems, "package file missing: $(f)"); continue)
    sha(p) == h || push!(problems, "package file changed: $(f)")
end
for (f, h) in pairs(man.input_files)
    p = joinpath(REPO, String(f))
    isfile(p) || (push!(problems, "input file missing: $(f)"); continue)
    sha(p) == h || push!(problems, "input file changed: $(f)")
end
rec = Dict{String,Any}("utc" => string(Dates.now(Dates.UTC)), "host" => Libc.gethostname(), "julia_version" => string(VERSION),
                       "julia_required" => string(JULIA_REQUIRED), "julia_version_override" => allow_julia && VERSION != JULIA_REQUIRED,
                       "hallthruster_commit" => rev, "hallthruster_version" => string(pkgversion(het)),
                       "hallthruster_pinned" => PINNED["commit"], "manifest_sha256" => sha(joinpath(REPO, "hallthruster_bridge", "Manifest.toml")),
                       "package_manifest_sha256" => sha(man_path), "package_files_sha256" => man.package_files,
                       "input_files_sha256" => man.input_files, "jobs" => parse(Int, jobs),
                       "threads_env" => Dict(k => get(ENV, k, nothing) for k in ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS")),
                       "julia_threads" => Threads.nthreads(), "blas_threads" => BLAS.get_num_threads(), "blas_config" => string(BLAS.get_config()),
                       "os" => "$(Sys.KERNEL) $(Sys.MACHINE)", "cpu" => Sys.cpu_info()[1].model, "cpu_threads" => Sys.CPU_THREADS,
                       "memory_GB" => round(Sys.total_memory() / 2^30; digits = 1), "problems" => problems, "ok" => isempty(problems))
mkpath(out)
open(joinpath(out, "preflight.json"), "w") do io
    JSON3.pretty(io, JSON3.write(rec), JSON3.AlignmentContext(indent = 1)); println(io)
end
if !isempty(problems)
    println(stderr, "PREFLIGHT REFUSED:\n  " * join(problems, "\n  "))
    exit(1)
end
println("preflight ok: Julia $(VERSION), HallThruster.jl $(pkgversion(het)) @ $(rev), $(length(man.package_files)) package + $(length(man.input_files)) input files verified")
