# Check of the chemistry-validity guard (bridge_lib.jl: chemistry_activity), on synthetic frames with the real
# dissociation_N2.dat table and its 45 eV limit. It shows the two failure modes the guard exists for:
#   1. a transient hot cell in ONE saved frame (breathing) that the time-averaged T_e profile hides;
#   2. a low-density hot cell whose n_e n_n is < 1 % of peak but whose reaction activity is not negligible.
# Both must give f_out > 0 (chemistry not trustworthy); a cold case must give f_out = 0 exactly.
# julia --project=hallthruster_bridge hallthruster_bridge/checks/chemistry_validity_check.jl
include(joinpath(@__DIR__, "..", "bridge_lib.jl"))
check_pin()
_, k = het.load_rate_coeff_file(joinpath(@__DIR__, "..", "propellants", "dissociation_N2.dat"), "electron_impact")
rx = [(file="dissociation_N2.dat", target=:N2, Z=0, k=k, limit=45.0, basis="test")]
z = collect(range(0.0, 0.1; length=11))
frame(Te, ne, nn) = (Tev=Te, ne=ne, neutrals=Dict(:N2 => (n=nn,)))
ne = fill(1e17, 11); nn = fill(1e19, 11); cold = fill(20.0, 11)          # 3/2 T_e = 30 eV everywhere

f0 = only(chemistry_activity([frame(cold, ne, nn) for _ in 1:10], z, rx))
@assert f0.fout == 0.0 "cold case must be exactly inside the domain"

# 1. one of ten frames has a 40 eV (3/2 T_e = 60 eV) cell; its time average (22 eV -> 33 eV) is inside the limit
hot = copy(cold); hot[6] = 40.0
fr = [i == 5 ? frame(hot, ne, nn) : frame(cold, ne, nn) for i in 1:10]
@assert 1.5 * (9 * 20.0 + 40.0) / 10 <= 45.0
f1 = only(chemistry_activity(fr, z, rx))
@assert f1.fout > CHEM_FOUT_TOL "transient hot frame must be detected"

# 2. a hot cell with n_e n_n at 0.5 % of peak (below the old 1 % region cut) still carries activity
nel = copy(ne); nel[9] = 5e14; hot2 = copy(cold); hot2[9] = 40.0
@assert nel[9] * nn[9] < 0.01 * maximum(nel .* nn)
f2 = only(chemistry_activity([frame(hot2, nel, nn) for _ in 1:10], z, rx))
@assert f2.fout > CHEM_FOUT_TOL "low-density hot cell must be detected"
@assert f2.eps_active == 60.0

# reactant parsing: neutral, singly and doubly charged targets
@assert reactant_term("N2 + e -> N(+) + N + 2e") == ("N2", 0)
@assert reactant_term("N(+) + e -> N(2+) + 2e") == ("N", 1)
@assert reactant_term("N(2+) + e -> N(3+) + 2e") == ("N", 2)

# unresolved files never produce a fraction
fu = only(chemistry_activity([frame(cold, ne, nn)], z, [(rx[1]..., limit=nothing)]))
@assert isnothing(fu.fout)
println("chemistry validity check OK: f_out cold = $(f0.fout), transient frame = $(round(f1.fout; sigdigits=3)), ",
        "low-density hot cell = $(round(f2.fout; sigdigits=3))")
