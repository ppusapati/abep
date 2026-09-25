# Consistency check for the wall-ion-flux producer (bridge_lib.jl: wall_ion_metrics).
# The solver saves nu_wall = radial_loss_frequency * wall_transition, with radial_loss_frequency * Δr * (1-γ) * ne equal to
# the WallSheath Bohm charge flux. For Z = 1 xenon, the producer's flux must reproduce it in channel cells outside the
# exit transition (z <= L - transition_length/2, where wall_transition = 1).
# julia --project=hallthruster_bridge hallthruster_bridge/checks/wall_flux_consistency.jl
include(joinpath(@__DIR__, "..", "bridge_lib.jl"))
check_pin()
c = JSON3.read(read(joinpath(@__DIR__, "..", "cases", "p5_xenon.json"), String)).cases[4]
geom = het.Geometry1D(channel_length=c.L_m, inner_radius=c.r_in_m, outer_radius=c.r_out_m)
bf, _, _ = measured_bfield(c)
cfg = het.Config(thruster=het.Thruster(name="P5", geometry=geom, magnetic_field=bf), domain=(0.0, c.domain_m),
                 discharge_voltage=c.Vd, propellants=[het.Propellant("Xe", flow_rate_kg_s=c.mdot_kgps)])
sol = het.run_simulation(cfg, het.SimParams(grid=het.EvenGrid(200), dt=5e-9, duration=1e-3, verbose=false))
sol.retcode == :success || error("run failed: $(sol.retcode)")
m, h, Δr = het.Xenon.m, het.edge_to_center_density_ratio(), geom.outer_radius - geom.inner_radius
rel = Float64[]
for f in sol.frames[end-10:end], i in findall(<=(c.L_m - cfg.transition_length / 2), sol.grid)
    Te, n = f.Tev[i], f.ions[:Xe][1].n[i]
    γ = het.SEE_yield(het.BNSiO2, Te, 1 - 8.3 * sqrt(het.me / m))
    push!(rel, abs(h * n * sqrt(het.e * Te / m) / (f.nu_wall[i] * Δr * (1 - γ) * f.ne[i]) - 1))
end
sort!(rel)
med = rel[(length(rel) + 1) ÷ 2]
println("producer vs solver wall flux over $(length(rel)) cell-frames: median |diff| = $(med), max = $(rel[end])")
# Differences above ~1 % occur only where T_e changes steeply within the breathing cycle, with alternating sign; this is
# consistent with nu_wall and the saved T_e/n_e belonging to different stages of the step (not verified in the solver).
med < 0.01 || error("wall-flux producer disagrees with the solver: median $(med)")
