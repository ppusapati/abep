# Identification worker: runs a list of (case, mode) jobs and appends one JSON line per job to an output file.
# julia --project=hallthruster_bridge hallthruster_bridge/identify_worker.jl jobs.json results.jsonl
# Jobs already present in the output (by job_id) are skipped, so an interrupted run resumes. Every job produces a line,
# including exceptions (recorded as retcode "exception" with the message): no failed fit is dropped.
include(joinpath(@__DIR__, "bridge_lib.jl"))

rev = check_pin()
jobs = JSON3.read(read(ARGS[1], String))
done = Set{String}()
isfile(ARGS[2]) && for l in eachline(ARGS[2])
    isempty(strip(l)) || push!(done, String(JSON3.read(l).job_id))
end
open(ARGS[2], "a") do io
    for j in jobs
        String(j.job_id) in done && continue
        r = try
            run_case(j.case, String(j.mode))
        catch e
            Dict{String,Any}("id" => "$(j.case.id)/$(j.mode)", "retcode" => "exception", "error" => sprint(showerror, e))
        end
        r["job_id"] = j.job_id
        r["hallthruster_commit"] = rev
        println(io, JSON3.write(r)); flush(io)
    end
end
