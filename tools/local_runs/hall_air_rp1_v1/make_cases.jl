# hall_air_rp1_v1 case generator (NP-HALL-PARAMETRIC-ENVELOPE addendum A9-LP, A9.39 item 4). PARAMETRIC / NOT_VALIDATED.
#   julia --project=hallthruster_bridge tools/local_runs/hall_air_rp1_v1/make_cases.jl generate   # writes cases_v1.json
#   julia --project=hallthruster_bridge tools/local_runs/hall_air_rp1_v1/make_cases.jl check      # byte-compares it
# Every physical value is read from a sha256-checked registered record; the selection (design table below) is the
# registered rule of the addendum. Nothing here runs HallThruster.jl.
using JSON3
using SHA

const PKG = @__DIR__
const REPO = normpath(joinpath(PKG, "..", "..", ".."))
sha(p) = bytes2hex(open(sha256, p))
shas(s::AbstractString) = bytes2hex(sha256(s))
function load(rel, want = nothing)
    p = joinpath(REPO, rel)
    h = sha(p)
    isnothing(want) || h == want || error("$(rel): sha256 $(h) != registered $(want)")
    return JSON3.read(read(p, String)), h
end

# Registered inputs (sha256 fixed here; a change of any of them is a new package version).
const DBF_LOCK = "docs/baseline/DBF-1.1/dbf1_1_lock_v1.json"
const DBF_LOCK_SHA = "257e141c" # prefix check only: the full value is recorded below
const CHEM_PREREG = ("docs/rust_migration/new_physics/NP-HALL-CHEM-AIR/prereg_v1.json",
                     "306712f78bbbf17e8aa50e804559c36a80680dbebc8ecf0f47f2c244443ea70f")
const ENSEMBLE = ("hallthruster_bridge/ensemble/transport_ensemble_v0.json",
                  "2d5069a3382ab667362befeeb5a737261f70a279d19cb89ee79cb61ae35ba08b")
const A7_RP1 = ("docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/cases/h1_parametric_envelope_a7_demo_rp1_cases_v1.json",
                nothing)
const AIR_CASES = ("docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/cases/h1_parametric_envelope_air_cases_v1.json",
                   "60bb9d009c53eafec8c0bec020a7fa9dc4f27e2101fb5d85d0a64f0e1bb61666")
const AIR_MANIFEST = ("docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/launch_manifest_air_v1.json", nothing)

# Registered levels (addendum A9-LP, selection rule SR-1..SR-5).
const COMPOSITIONS = ["CP-YLO-REC", "CP-YHI-DIS"]                       # SR-1: y_O hull extremes (diagonal corners)
const VD = Dict("VD-265" => 265.0, "VD-350" => 350.0)                   # SR-2: the two upper registered v1 V_d levels
const BP = Dict("BP-LO" => 69.93, "BP-HI" => 268.6)                     # SR-3: DBF1-BZ-03 operating levels [G]
const MF = Dict("MF-A" => 2.0e-7, "MF-B" => 5.0e-7, "MF-C" => 1.0e-6, "MF-D" => 2.0e-6)   # SR-4 [kg/s]
const TRANSPORTS = ["sgb-screen-01", "sgb-screen-04"]                  # SR-5: opposite corners of the (b, c, w) box
# SR-6 design table: half fraction comp x V_d x B (I = comp.V_d.B, coded YLO/265/LO = -1), two rows per flow level, each
# pair with both compositions, every row twice over the four flow levels; plus the sgb-screen-04 replicates of MF-C.
const DESIGN = [
    ("C01", "MF-A", "CP-YLO-REC", "VD-350", "BP-LO", "sgb-screen-01"),
    ("C02", "MF-A", "CP-YHI-DIS", "VD-265", "BP-LO", "sgb-screen-01"),
    ("C03", "MF-B", "CP-YLO-REC", "VD-265", "BP-HI", "sgb-screen-01"),
    ("C04", "MF-B", "CP-YHI-DIS", "VD-350", "BP-HI", "sgb-screen-01"),
    ("C05", "MF-C", "CP-YLO-REC", "VD-350", "BP-LO", "sgb-screen-01"),
    ("C06", "MF-C", "CP-YHI-DIS", "VD-350", "BP-HI", "sgb-screen-01"),
    ("C07", "MF-D", "CP-YLO-REC", "VD-265", "BP-HI", "sgb-screen-01"),
    ("C08", "MF-D", "CP-YHI-DIS", "VD-265", "BP-LO", "sgb-screen-01"),
    ("C09", "MF-C", "CP-YLO-REC", "VD-350", "BP-LO", "sgb-screen-04"),
    ("C10", "MF-C", "CP-YHI-DIS", "VD-350", "BP-HI", "sgb-screen-04"),
]

function build()
    lock, lock_sha = load(DBF_LOCK)
    startswith(lock_sha, DBF_LOCK_SHA) || error("DBF-1.1 lock sha256 $(lock_sha) is not the registered 257e141c...")
    for (f, h) in pairs(lock.files)
        sha(joinpath(REPO, "docs/baseline/DBF-1.1", String(f))) == h || error("DBF-1.1 lock mismatch: $(f)")
    end
    man_rel = "hallthruster_bridge/bfield/h1_fe_v1/MANIFEST.json"
    sha(joinpath(REPO, man_rel)) == lock.pinned_sources[Symbol(man_rel)] || error("B(z) MANIFEST differs from the DBF-1.1 lock")
    dbf, dbf_sha = load("docs/baseline/DBF-1.1/dbf1_1_config_v1.json", lock.files[Symbol("dbf1_1_config_v1.json")])
    bman, bman_sha = load(man_rel)
    h1 = dbf.h1
    h1.geometry_id == "G-RP1" && h1.bz_shape_id == "BZ-H1FE-V1" || error("DBF-1.1 is not G-RP1 / BZ-H1FE-V1")
    L = h1.L_mm * 1e-3; r_in = (h1.d_mean_mm - h1.h_mm) / 2 * 1e-3; r_out = (h1.d_mean_mm + h1.h_mm) / 2 * 1e-3
    for (k, v) in BP
        h1.B_peak_band_G[1] <= v <= h1.B_peak_band_G[2] || error("$(k) outside DBF1-BZ-02")
    end
    for v in values(VD)
        h1.V_d_band_V[1] <= v <= h1.V_d_band_V[2] || error("V_d outside DBF1-H1-05")
    end

    chem, chem_sha = load(CHEM_PREREG...)
    pts = Dict(String(p.id) => p for p in chem.composition.hall_composition_points.points)
    ens, ens_sha = load(ENSEMBLE...)
    tr = Dict(String(c.ensemble_member_id) => c for c in ens.screening_candidates)
    a7, a7_sha = load(A7_RP1...)
    a7c = Dict(String(c.a7_level) => c for c in a7.cases if c.geometry_id == "G-RP1")
    air, air_sha = load(AIR_CASES...)
    inlet = air.inlet
    lm, lm_sha = load(AIR_MANIFEST...)
    lm.chemistry_bound_member == "BV-AIR-LL-NOM" || error("AIR launch manifest is not BV-AIR-LL-NOM")

    P, C = a7c["A7-P"], a7c["A7-C"]
    (P.duration_s == C.duration_s && P.average_start_s == C.average_start_s && P.domain_m == C.domain_m &&
     P.L_m == L && P.r_in_m == r_in && P.r_out_m == r_out) || error("A7 RP-1 numerics do not match DBF-1.1 G-RP1")

    cases = []
    for (id, mf, cp, vd, bp, tid) in DESIGN
        prof = h1.bz_profiles.nominal[Symbol(bp)]
        fname = basename(String(prof.file))
        fe = bman.files[Symbol(fname)]
        fe.sha256 == prof.sha256 || error("$(fname): MANIFEST and DBF-1.1 sha256 differ")
        t = tr[tid].transport_parameters
        mdot = MF[mf]
        w = pts[cp].mass_fractions
        feed = [(species = s, flow_rate_kg_s = mdot * Float64(w[Symbol(s)]), velocity_m_s = Float64(inlet.velocity_m_s[Symbol(s)]),
                 temperature_K = Float64(inlet.temperature_K)) for s in ("N2", "N", "O2", "O")]
        key = "AIR|G-RP1|BZ-H1FE-V1|$(bp)|$(vd)|$(mf)|$(cp)|$(tid)"
        c = (case_id = id, key = key, family = "AIR", thruster = "H-1-RP1", geometry_id = "G-RP1", bz_shape_id = "BZ-H1FE-V1",
             B_peak_id = bp, Vd_id = vd, mdot_id = mf, composition_id = cp, transport_id = tid,
             L_m = L, r_in_m = r_in, r_out_m = r_out, domain_m = P.domain_m, Vd = VD[vd], mdot_kgps = mdot,
             B_ref_T = BP[bp] * 1e-4,
             B_profile = (file = "bfield/h1_fe_v1/$(fname)", align = "anode", z_ref_in_file_mm = 0.0, scale_to = "max"),
             B_operating_point = (profile_id = "BZ-H1FE-V1/NOM/$(bp)", B_peak_G = BP[bp], fe_file_B_peak_G = fe.B_peak_G,
                                  fe_file_z_peak_mm = fe.z_peak_mm, coil_NI_total_A_turns = fe.NI_total_A,
                                  coil_NI_basis = "NI_total of the FE solution at its own B_peak (fe_file_B_peak_G); the run scales B by B_peak_G / fe_file_B_peak_G",
                                  file_sha256 = fe.sha256, evidence = "FE-DERIVED (scikit-fem 10.0.2), NOT MEASURED"),
             transport = (model = "ScaledGaussianBohm", anom_scale = t.anom_scale, barrier_scale = t.barrier_scale,
                          center = t.center_L, width = t.width_L),
             propellant_config = String(lm.air_config), rate_dir = "propellants_air", feed = feed,
             composition = (y_O = pts[cp].y_O, f_O = pts[cp].f_O, f_N = pts[cp].f_N, mass_fractions = w),
             duration_s = P.duration_s, average_start_s = P.average_start_s, num_save = P.num_save, numerics = P.numerics,
             levels = (var"A7-P" = (cells = P.cells, dt_s = P.dt_s, dx_mm = 1e3 * P.domain_m / P.cells),
                       var"A7-C" = (cells = C.cells, dt_s = C.dt_s, dx_mm = 1e3 * C.domain_m / C.cells)))
        push!(cases, merge(c, (case_sha256 = shas(JSON3.write(c)),)))
    end
    doc = (schema = "abep_hall_air_rp1_local_cases_v1", package = "hall_air_rp1_v1", model_id = "NP-HALL-PARAMETRIC-ENVELOPE",
           addendum = "A9-LP (prereg_addendum_a9_local_air_rp1_v1.json)", owner_decision = "A9.39 item 4",
           layer = "PARAMETRIC / NOT_VALIDATED",
           labels = ["PARAMETRIC / NOT_VALIDATED", "AIR_CHEMISTRY_BOUNDED_NOT_COMPLETE (BV-AIR-LL-NOM, BOUNDED_ONE_SIDED_LOWER_ELECTRON_IMPACT_LOSS_NOT_COMPLETE)",
                     "B(z) FE-DERIVED NOT MEASURED", "TRANSPORT SCREENING CANDIDATES NOT ADMITTED (credible set EMPTY)",
                     "COMPOSITION_HULL_CORNERS_NOT_INTERIOR_BOUNDS", "NEUTRAL_INLET_EQUAL_T_SCALED_FROM_V1_DEFAULT",
                     "VACUUM MODE (no facility ingestion)"],
           baseline = (id = "DBF-1.1", lock = DBF_LOCK, lock_sha256 = lock_sha, config_sha256 = dbf_sha, bfield_manifest_sha256 = bman_sha),
           sources = (chem_prereg_sha256 = chem_sha, transport_ensemble_sha256 = ens_sha, a7_rp1_cases_sha256 = a7_sha,
                      air_cases_v1_sha256 = air_sha, air_launch_manifest_sha256 = lm_sha),
           air_chemistry = (label = lm.air_label, mode = lm.chemistry_mode, bound_set = lm.chemistry_bound_set,
                            bound_member = lm.chemistry_bound_member, bound_label = lm.chemistry_bound_label,
                            n2n_reaction_set = "abep-n2n-0.11 (referenced in place, ../propellants/)"),
           inlet = inlet, mode = "vacuum", n_cases = length(cases), levels = ["A7-P", "A7-C"], cases = cases)
    return JSON3.write(doc)
end

function pretty(s)
    io = IOBuffer()
    JSON3.pretty(io, JSON3.read(s), JSON3.AlignmentContext(indent = 1))
    return String(take!(io)) * "\n"
end

# Package manifest: sha256 of every package file (except this manifest, the README and reference outputs) and of every
# repository input a run reads. preflight.jl refuses a run when any of them differs.
const PACKAGE_FILES = ["make_cases.jl", "hall_air_rp1_lib.jl", "worker.jl", "aggregate.jl", "preflight.jl", "validate.jl",
                       "run_all.sh", "cases_v1.json", "results_schema_v1.json"]
function manifest()
    lm, _ = load(AIR_MANIFEST...)
    inputs = ["hallthruster_bridge/bridge_lib.jl", "hallthruster_bridge/air_bridge_lib.jl", "hallthruster_bridge/a7_numerics.jl",
              "hallthruster_bridge/hall_map_schema_v1.json", "hallthruster_bridge/PINNED.toml", "hallthruster_bridge/Project.toml",
              "hallthruster_bridge/Manifest.toml", "hallthruster_bridge/propellants_air/AIR_PINNED.toml",
              "hallthruster_bridge/propellants_air/rate_validity.toml", "hallthruster_bridge/" * String(lm.air_config)]
    doc = JSON3.read(read(joinpath(PKG, "cases_v1.json"), String))
    for c in doc.cases
        f = "hallthruster_bridge/" * String(c.B_profile.file)
        f in inputs || push!(inputs, f)
    end
    for f in keys(lm.rate_files)
        push!(inputs, normpath("hallthruster_bridge/propellants_air/" * String(f)))
    end
    return (schema = "abep_hall_air_rp1_package_manifest_v1", package = "hall_air_rp1_v1",
            package_files = Dict(f => sha(joinpath(PKG, f)) for f in PACKAGE_FILES),
            input_files = Dict(f => sha(joinpath(REPO, f)) for f in inputs))
end

mode = isempty(ARGS) ? "check" : ARGS[1]
if mode == "manifest"
    p = joinpath(PKG, "package_manifest_v1.json")
    write(p, pretty(JSON3.write(manifest())))
    println("wrote $(p) sha256 $(sha(p))")
    exit(0)
end
out = joinpath(PKG, "cases_v1.json")
txt = pretty(build())
if mode == "generate"
    write(out, txt)
    println("wrote $(out) sha256 $(shas(txt))")
elseif mode == "check"
    read(out, String) == txt || error("cases_v1.json does not reproduce from the registered sources")
    println("cases_v1.json reproduces (sha256 $(sha(out)))")
else
    error("usage: make_cases.jl generate|check")
end
