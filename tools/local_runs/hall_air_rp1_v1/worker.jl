# hall_air_rp1_v1 worker: claims runs (case x level) from <out>/queue.txt one at a time (atomic mkdir claim) and writes
# one raw record per run to <out>/runs/<case>_<level>.json (written to a temporary file, then renamed). Runs whose record
# exists are skipped (resume on rerun). Started by run_all.sh; never edits inputs.
#   julia --project=hallthruster_bridge tools/local_runs/hall_air_rp1_v1/worker.jl <out_dir> <worker_id>
include(joinpath(@__DIR__, "hall_air_rp1_lib.jl"))
using SHA
using Dates
using LinearAlgebra

const OUT = ARGS[1]
const WID = ARGS[2]
rev = check_pin()
cases_path = joinpath(@__DIR__, "cases_v1.json")
cases_sha = bytes2hex(open(sha256, cases_path))
doc = JSON3.read(read(cases_path, String))
byid = Dict(String(c.case_id) => c for c in doc.cases)
queue = [split(strip(l), " ") for l in eachline(joinpath(OUT, "queue.txt")) if !isempty(strip(l))]
mkpath(joinpath(OUT, "runs")); mkpath(joinpath(OUT, "claims"))
envs = Dict(k => get(ENV, k, nothing) for k in ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"))

for (cid, level) in queue
    rec_path = joinpath(OUT, "runs", "$(cid)_$(level).json")
    isfile(rec_path) && continue
    try
        mkdir(joinpath(OUT, "claims", "$(cid)_$(level)"))
    catch
        continue                                    # another worker holds it
    end
    c = byid[cid]
    println("[worker $(WID)] $(Dates.now()) start $(cid) $(level)  $(c.key)"); flush(stdout)
    rec = Dict{String,Any}("case_id" => cid, "key" => String(c.key), "level" => level, "case_sha256" => String(c.case_sha256),
                           "cases_file_sha256" => cases_sha, "hallthruster_commit" => rev,
                           "hallthruster_version" => string(pkgversion(het)), "julia_version" => string(VERSION),
                           "threads_env" => envs, "julia_threads" => Threads.nthreads(),
                           "blas_threads" => LinearAlgebra.BLAS.get_num_threads(), "host" => Libc.gethostname(),
                           "worker" => WID, "utc_start" => string(Dates.now(Dates.UTC)))
    t0 = time()
    try
        merge!(rec, air_a7_record(c, level))
    catch err
        rec["retcode"] = "exception"
        rec["converged"] = false
        rec["finite"] = false
        rec["error"] = sprint(showerror, err)
    end
    rec["wall_total_s"] = time() - t0
    rec["utc_end"] = string(Dates.now(Dates.UTC))
    tmp = rec_path * ".tmp"
    open(tmp, "w") do io
        JSON3.write(io, json_safe(rec))
    end
    mv(tmp, rec_path; force = true)
    println("[worker $(WID)] $(Dates.now()) done  $(cid) $(level)  retcode=$(rec["retcode"])  wall=$(round(rec["wall_total_s"]; digits = 1)) s")
    flush(stdout)
end
