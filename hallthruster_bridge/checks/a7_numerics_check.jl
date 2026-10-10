# Check of the A7 bridge (hallthruster_bridge/a7_numerics.jl), NP-HALL-PARAMETRIC-ENVELOPE addendum A7.
# 1. a7_window_stats on synthetic series with known answers (constant; pure sine over whole periods; a step).
# 2. Equivalence: a7_config / a7_run at the v1 numerics (A7_SOLVER_DEFAULTS, the case's cells / dt / duration) reproduce
#    bridge_lib.run_case(c, "vacuum") bit for bit (time-averaged thrust and I_d) on two frozen A6 study cases at A6-L0.
# julia --project=hallthruster_bridge hallthruster_bridge/checks/a7_numerics_check.jl
include(joinpath(@__DIR__, "..", "a7_numerics.jl"))
check_pin()

t = collect(range(0.0, 1.0; length = 2001))
s = a7_window_stats(t, fill(3.0, length(t)), 0.5)
(s.mean == 3.0 && s.se_batch == 0.0 && s.rms_rel == 0.0 && s.mean_first_half == 3.0) || error("constant series: $(s)")
y = 2.0 .+ sin.(2π * 40 .* t)                      # 20 whole periods in [0.5, 1]
s = a7_window_stats(t, y, 0.5)
(abs(s.mean - 2.0) < 1e-3 && s.se_batch < 1e-3 && abs(s.rms_rel - 1 / (2 * sqrt(2))) < 1e-2) || error("sine series: $(s)")
y = [x < 0.75 ? 1.0 : 2.0 for x in t]
s = a7_window_stats(t, y, 0.5)
(s.mean_first_half == 1.0 && s.mean_second_half == 2.0) || error("step series: $(s)")
println("a7_window_stats: synthetic series OK")

doc = JSON3.read(read(joinpath(@__DIR__, "..", "..", "docs", "rust_migration", "new_physics", "NP-HALL-PARAMETRIC-ENVELOPE",
                               "cases", "h1_parametric_envelope_a6_study_cases_v1.json"), String))
for key in ("XE|G-AMINDHMAX-LH8603|BZ-P5B30|BP-LO|VD-180|MF-LO|sgb-screen-09|A6-L0",
            "XE|G-AMINDHMAX-LH8603|BZ-P5B30|BP-HI|VD-350|MF-HI|sgb-screen-08|A6-L0")
    c = only([c for c in doc.cases if c.key == key])
    r = run_case(c, "vacuum")
    n = merge(A7_SOLVER_DEFAULTS, (cells = c.cells, dt_s = c.dt_s, duration_s = c.duration_s))
    _, sol = a7_run(c, n)
    avg = het.time_average(sol, c.average_start_s)
    T, I = het.thrust(avg)[1], het.discharge_current(avg)[1]
    (T == r["thrust_N"] && I == r["discharge_current_A"]) || error("$(key): a7 ($(T), $(I)) != run_case ($(r["thrust_N"]), $(r["discharge_current_A"]))")
    println("$(key): a7_run reproduces run_case bit for bit (T = $(T) N, I_d = $(I) A)")
end
println("A7 bridge check OK")
