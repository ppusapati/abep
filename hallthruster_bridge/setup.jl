# One-time local setup (Julia >= 1.10):  julia hallthruster_bridge/setup.jl
# Creates a project environment in hallthruster_bridge/ with HallThruster.jl pinned to the exact audited commit.
using Pkg
Pkg.activate(@__DIR__)
Pkg.add(url = "https://github.com/UM-PEPL/HallThruster.jl", rev = "bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5")  # v0.23.1
Pkg.add("JSON3")
Pkg.instantiate()
println("HallThruster.jl pinned: ", pkgversion(Base.require(Main, :HallThruster)))
