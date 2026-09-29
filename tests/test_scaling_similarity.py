"""Lane 22 scaling/similarity audit (scripts/architecture/scaling_similarity.py).

Checks: the script reproduces the committed JSON and Markdown; the P5 inputs match the repository case files; the
dimensionless groups agree with independent hand calculations; the evidence discipline of the inputs; missing inputs
raise; other lanes' contracts are resolved lazily and are not needed. Runs in well under a second; no Julia.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "architecture" / "scaling_similarity.py"
OUT = REPO / "docs" / "architecture_comparison" / "scaling"
JSON_PATH = OUT / "scaling_similarity.json"
MD_PATH = OUT / "SCALING_SIMILARITY.md"

# Independent constants for the hand checks: exact SI values (e, k_B), the repository's amu and species-mass convention
# (abep_sim/constants.py: N2 = 28.0 amu, Xe = 131.3 amu) and CODATA 2022 m_e.
E = 1.602176634e-19
KB = 1.380649e-23
AMU = 1.66053906660e-27
M_N2, M_XE = 28.0 * AMU, 131.3 * AMU
M_E = 9.1093837139e-31
REL = 2e-5  # outputs are rounded to 6 significant digits


def close(a, b, rel=REL):
    return math.isclose(a, b, rel_tol=rel, abs_tol=0.0)


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("scaling_similarity_under_test", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def fresh(mod):
    return mod.build()


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text())


def cases(gas):
    rel = {"N2": "hallthruster_bridge/cases/p5_n2.json", "Xe": "hallthruster_bridge/cases/p5_xenon.json"}[gas]
    return json.loads((REPO / rel).read_text())["cases"]


def rate_at(rel, Te):
    """Independent reader: linear interpolation in mean energy 3/2 T_e (HallThruster.jl table convention)."""
    lines = (REPO / rel).read_text().splitlines()
    rows = [[float(x) for x in ln.split()] for ln in lines[2:] if ln.strip()]
    eps = 1.5 * Te
    for (e0, k0), (e1, k1) in zip(rows, rows[1:]):
        if e0 <= eps <= e1:
            return k0 + (k1 - k0) * (eps - e0) / (e1 - e0)
    raise AssertionError("outside table")


def k_xe_fit(Te):
    """GK2008 Appendix E, >5 eV fit (p. 475), typed independently."""
    ve = math.sqrt(8 * E * Te / (math.pi * M_E))
    return 1e-20 * (-1.031e-4 * Te ** 2 + 6.386 * math.exp(-12.127 / Te)) * ve


# ---------------------------------------------------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------------------------------------------------
def test_script_reproduces_committed_outputs(mod, fresh):
    assert mod.dumps(fresh) == JSON_PATH.read_text()
    assert mod.render_md(fresh) == MD_PATH.read_text()
    assert mod.main(["--check"]) == 0


def test_build_is_deterministic(mod, fresh):
    assert mod.dumps(mod.build()) == mod.dumps(fresh)


def test_repository_input_hashes(doc):
    files = doc["inputs"]["repository_files"]
    for rel in ("hallthruster_bridge/cases/p5_n2.json", "hallthruster_bridge/cases/p5_xenon.json",
                "hallthruster_bridge/bfield/p5_vacuum_Br_centerline_1p6kW.csv",
                "hallthruster_bridge/bfield/p5_vacuum_Br_centerline_3p0kW.csv"):
        assert rel in files
    for rel, h in files.items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == h, rel


# ---------------------------------------------------------------------------------------------------------------------
# P5 inputs match the repository files
# ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("gas", ["N2", "Xe"])
def test_p5_points_match_case_files(doc, gas):
    pts = doc["inputs"]["p5"][gas]["points"]
    seen = {}
    for c in cases(gas):
        r = pts[c["point"]]
        for k in ("Vd", "mdot_kgps", "r_in_m", "r_out_m", "B_ref_T"):
            assert close(r[k], c[k]), (c["id"], k)
        for k in ("Pd_W", "Id_A", "T_corr_mN", "T_sigma_mN"):
            assert close(r[k], c["measured"][k]), (c["id"], k)
        assert r["T_corr_source"] == c["measured"]["T_corr_source"]
        seen.setdefault(c["point"], set()).add(c["L_m"])
    assert set(pts) == set(seen)
    for p, Ls in seen.items():
        assert sorted(Ls) == pts[p]["L_m"]
    assert set(seen) == ({"N1", "N2", "N3", "N4", "N5"} if gas == "N2" else {"Xe1", "Xe2", "Xe3"})


@pytest.mark.parametrize("gas", ["N2", "Xe"])
def test_p5_registrations_match_case_files(doc, gas):
    regs = doc["inputs"]["p5"][gas]["registrations"]
    for c in cases(gas):
        coil = c.get("coil_shape") or Path(c["B_profile"]["file"]).stem.rsplit("_", 1)[-1]
        r = regs[f"{c['registration']}|{coil}"]
        assert r["L_m"] == c["L_m"] and r["align"] == c["B_profile"]["align"]
        assert r["z_ref_in_file_mm"] == c["B_profile"]["z_ref_in_file_mm"]
        assert r["bfield_file"] == "hallthruster_bridge/" + c["B_profile"]["file"]


def test_echt_inputs_match_audit(doc):
    audit = json.loads((REPO / doc["inputs"]["echt"]["file"]).read_text())
    perf = audit["values"]["performance_table_6_2"]
    stable = [r for r in perf["rows"] if r["run"] not in perf["unstable_runs"]]
    pts = doc["inputs"]["echt"]["points"]
    assert doc["inputs"]["echt"]["unstable_runs_excluded"] == sorted(perf["unstable_runs"])
    n = sum(1 for r in stable for k in ("T_mN", "T_avg_mN") if r[k] is not None)
    assert len(pts) == n
    for r in stable:
        p = pts[f"{r['run'].replace(' ', '')}-one_side"]
        assert (p["Vd"], p["Id_A"], p["Pd_W"], p["T_mN"]) == (r["Vd"], r["Id"], r["P_anode_W"], r["T_mN"])
    g = audit["values"]["geometry"]
    assert close(doc["inputs"]["echt"]["L_m"], 1e-3 * g["channel_length"]["value_mm"])
    assert close(doc["inputs"]["echt"]["h_m"], 1e-3 * g["channel_height"]["value_mm"])


# ---------------------------------------------------------------------------------------------------------------------
# Hand-checked dimensionless groups
# ---------------------------------------------------------------------------------------------------------------------
def test_hand_checked_p5_n1_groups(doc):
    """P5-N1 (Brabston Table 2 via the case file): every T_e-independent group by hand, at both depth-bracket ends and
    both T_n ends."""
    c = next(c for c in cases("N2") if c["point"] == "N1")
    m = c["measured"]
    d, h = c["r_in_m"] + c["r_out_m"], c["r_out_m"] - c["r_in_m"]
    A = math.pi * d * h
    vn = {T: math.sqrt(2 * KB * T / M_N2) for T in (300.0, 800.0)}
    vi = math.sqrt(2 * E * c["Vd"] / M_N2)
    g = doc["p5_groups"]["N2"]["per_point"]["N1"]
    assert close(g["d_over_h"][0], 148.0 / 25.0) and close(g["d_over_h"][1], 5.92)
    assert close(g["L_over_h"][0], 32 / 25) and close(g["L_over_h"][1], 38 / 25)
    assert close(g["inv_h"][0], 40.0)
    assert close(g["n_n"][0], c["mdot_kgps"] / (M_N2 * vn[800.0] * A))
    assert close(g["n_n"][1], c["mdot_kgps"] / (M_N2 * vn[300.0] * A))
    assert close(g["n_n"][1], 2.1918e19, rel=2e-4)  # typed-out value: 5e-6 / (4.64951e-26 * 422.09 * 0.0116239)
    assert close(g["j_d"][0], m["Id_A"] / A)
    assert close(g["P_over_hd"][0], m["Pd_W"] / (h * d))
    assert close(g["q_wall"][0], 0.10 * m["Pd_W"] / (2 * math.pi * d * 0.038))
    assert close(g["eps_particle"][0], m["Pd_W"] * M_N2 / (E * c["mdot_kgps"]))
    assert close(g["I_d_over_I_m"][0], m["Id_A"] / (E * c["mdot_kgps"] / M_N2))
    assert close(g["alpha_app"][0], 1e-3 * m["T_corr_mN"] / (c["mdot_kgps"] * vi))
    assert close(g["T_over_P"][0], m["T_corr_mN"] / (m["Pd_W"] / 1e3))
    assert close(g["tau_res"][1], 0.038 / vn[300.0])
    assert close(g["n_e_exit"][0], m["Id_A"] / (E * vi * A))
    assert close(g["rLi_over_L"][0], math.sqrt(2 * M_N2 * c["Vd"] / E) / (c["B_ref_T"] * 0.038))


def test_hand_checked_electron_larmor(doc):
    # formula check against GK2008 p. 331: 25 eV, 150 G -> 0.13 cm
    rle = math.sqrt(8 * M_E * 25 / (math.pi * E)) / 0.015
    assert round(100 * rle, 2) == 0.13
    c = next(c for c in cases("N2") if c["point"] == "N1")
    rle10 = math.sqrt(8 * M_E * 10 / (math.pi * E)) / c["B_ref_T"]
    g = doc["p5_groups"]["N2"]["per_point"]["N1"]["per_Te"]["10"]
    assert close(g["rLe_over_L"][0], rle10 / 0.038) and close(g["rLe_over_L"][1], rle10 / 0.032)
    assert close(g["rLe_over_h"][0], rle10 / 0.025)


def test_hand_checked_ionization_rates_and_gas_factor(doc):
    base = "hallthruster_bridge/propellants/"
    for Te in (5.0, 10.0, 20.0, 30.0):
        te = f"{Te:g}"
        common = rate_at(base + "ionization_N2_song2023.dat", Te) + \
            rate_at(base + "dissociative_ionization_N2_to_N_Z2plus.dat", Te)
        k_lo = common + rate_at(base + "dissociative_ionization_N2_lower.dat", Te)
        k_hi = common + rate_at(base + "dissociative_ionization_N2_upper.dat", Te)
        f = doc["gas_transfer_factor"][te]
        assert close(f["k_iz_N2_m3s"][0], k_lo) and close(f["k_iz_N2_m3s"][1], k_hi)
        assert close(f["k_iz_Xe_m3s"], k_xe_fit(Te))
        ratio = math.sqrt(M_XE / M_N2)
        assert close(f["lambda_ratio_N2_over_Xe"][0], ratio * k_xe_fit(Te) / k_hi)
        assert close(f["lambda_ratio_N2_over_Xe"][1], ratio * k_xe_fit(Te) / k_lo)
        assert f["lambda_ratio_N2_over_Xe"][0] > 1.0  # N2 always has the longer ionization length here
    # the fit implementation agrees with GK2008 Table E-1 at 10 eV (3.90e-14 m^3/s)
    assert abs(doc["xe_fit_check"]["10"]["fit_over_table"] - 1.0) < 0.05
    assert close(doc["xe_fit_check"]["10"]["table_E1_m3s"], 3.90e-14)


def test_hand_checked_melikov_morozov_number(doc):
    """L/lambda_i = L n_e k / v_n for P5-N1, L = 38 mm, T_n = 300 K, T_e = 10 eV, upper DI variant (largest value)."""
    c = next(c for c in cases("N2") if c["point"] == "N1")
    d, h = c["r_in_m"] + c["r_out_m"], c["r_out_m"] - c["r_in_m"]
    A = math.pi * d * h
    vi = math.sqrt(2 * E * c["Vd"] / M_N2)
    ne = c["measured"]["Id_A"] / (E * vi * A)
    k_hi = doc["gas_transfer_factor"]["10"]["k_iz_N2_m3s"][1]
    mm = 0.038 * ne * k_hi / math.sqrt(2 * KB * 300.0 / M_N2)
    assert close(doc["p5_groups"]["N2"]["per_point"]["N1"]["per_Te"]["10"]["L_over_lambda_i"][1], mm, rel=1e-4)
    assert close(doc["p5_groups"]["N2"]["per_point"]["N1"]["per_Te"]["10"]["iz_fraction"][1], 1 - math.exp(-mm),
                 rel=1e-4)


def test_hand_checked_dual_gas_prefactor(doc):
    """(n_e/v_n)_N2 / (n_e/v_n)_Xe on the same P5 hardware, every N x Xe pair as measured."""
    n2 = {c["point"]: c for c in cases("N2")}
    xe = {c["point"]: c for c in cases("Xe")}
    prefs = []
    for a in n2.values():
        for b in xe.values():
            ne_ratio = (a["measured"]["Id_A"] / math.sqrt(2 * E * a["Vd"] / M_N2)) / \
                       (b["measured"]["Id_A"] / math.sqrt(2 * E * b["Vd"] / M_XE))
            prefs.append(ne_ratio * math.sqrt(M_N2 / M_XE))
    got = doc["dual_gas"]["P5_same_hardware_as_measured"]["ratios_N2_over_Xe"]["prefactor"]
    assert close(got[0], min(prefs)) and close(got[1], max(prefs))
    assert doc["dual_gas"]["P5_same_hardware_as_measured"]["pairs"] == 15


def test_required_Te_solves_the_matching_condition(mod, doc):
    gases, _ = mod.build_gases()
    sh = doc["dual_gas"]["P5_same_hardware_as_measured"]
    pref = sh["ratios_N2_over_Xe"]["prefactor"]
    r = sh["Te_N2_required_to_match_Xe_L_over_lambda_i"]["5"]
    assert r["exceeds_30eV_domain"] == "none"
    # best case: largest prefactor with the upper DI variant; worst case: smallest prefactor with the lower variant
    assert math.isclose(pref[1] * gases["N2"].k_iz(r["Te_N2_min_eV"])[1], k_xe_fit(5.0), rel_tol=1e-3)
    assert math.isclose(pref[0] * gases["N2"].k_iz(r["Te_N2_max_eV"])[0], k_xe_fit(5.0), rel_tol=1e-3)
    assert 2.0 <= r["Te_N2_min_eV"] <= r["Te_N2_max_eV"] <= 30.0
    # at T_e(Xe) = 10 eV the N2 value is not reached inside the 30 eV chemistry domain (reported, never extrapolated)
    assert sh["Te_N2_required_to_match_Xe_L_over_lambda_i"]["10"]["exceeds_30eV_domain"] == "all"


def test_envelope_operating_point_hand_check(doc):
    """Each anchor keeps alpha_app and I_d/I_m, so at thrust T every flow/current/power scales by T/T_anchor."""
    c = next(c for c in cases("N2") if c["point"] == "N1")["measured"]
    row = next(r for r in doc["vyovrinda_envelope"]["N2"]["operating_rows"]
               if r["anchor"] == "P5-N1" and r["thrust_mN"] == 25.0)
    s = 25.0 / c["T_corr_mN"]
    assert close(row["P_d_W"], c["Pd_W"] * s) and close(row["I_d_A"], c["Id_A"] * s)
    assert close(row["mdot_mgps"], 5.0 * s, rel=1e-4)


def test_bfield_registration_hand_check(doc):
    """L32-exit places the 38 mm file exit point at the 32 mm model exit: z_channel = z_file - 38 + 32."""
    z, b = [], []
    for ln in (REPO / "hallthruster_bridge/bfield/p5_vacuum_Br_centerline_1p6kW.csv").read_text().splitlines():
        if ln and not ln.startswith(("#", "z_")):
            zz, bb = ln.split(",")
            z.append(float(zz))
            b.append(float(bb))
    zpk = z[b.index(max(b))]
    reg = doc["b_field_topology"]["P5"]["registrations"]
    assert close(reg["L32-exit|1p6kW"]["z_peak_over_L"], (zpk - 38.0 + 32.0) / 32.0)
    assert close(reg["L38-hist|1p6kW"]["z_peak_over_L"], zpk / 38.0)


# ---------------------------------------------------------------------------------------------------------------------
# Verdict logic, register consistency, evidence discipline
# ---------------------------------------------------------------------------------------------------------------------
def test_divergence_and_verdict_logic(mod):
    assert mod.divergence([1.0, 2.0], [1.5, 3.0]) == (1.0, 1.5)
    assert mod.divergence([1.6, 2.0], [1.5, 3.0]) == (1.0, 1.0)
    best, worst = mod.divergence([10.0, 20.0], [1.0, 2.0])
    assert (best, worst) == (5.0, 10.0)
    assert mod.verdict(1.0, 1.9, False) == "MATCHES_WITHIN_2"
    assert mod.verdict(1.0, 4.0, False) == "DESIGN_DEPENDENT"
    assert mod.verdict(3.0, 4.0, False) == "DIVERGES"
    assert mod.verdict(6.0, 9.0, False) == "STRONGLY_DIVERGES"
    assert mod.verdict(1.0, 1.0, True) == "SET_BY_CONSTRUCTION"
    assert mod.verdict(None, None, False) == "NOT_COMPARABLE"


def test_register_consistent_with_verdicts(mod, fresh):
    assert mod.check_register(fresh["comparison"]) == []
    ids = [t["id"] for t in fresh["transfer_register"]]
    assert len(ids) == len(set(ids))
    for t in fresh["transfer_register"]:
        assert "{" not in t["why"] and t["risk"] in ("NONE", "LOW", "MEDIUM", "HIGH")
    closure = next(t for t in fresh["transfer_register"] if t["id"] == "TR-08")
    assert closure["transferability"] == "NOT_TRANSFERABLE" and closure["risk"] == "HIGH"


def test_carried_groups_are_not_scored_as_similarity(fresh):
    for gas in ("N2", "Xe"):
        for rows in fresh["comparison"][gas].values():
            for g in ("alpha_app", "T_over_P", "I_d_over_I_m", "d_over_h"):
                assert rows[g]["verdict"] == "SET_BY_CONSTRUCTION"


def test_evidence_discipline_of_inputs(fresh):
    srcs = fresh["sources"]
    for k, v in fresh["inputs"]["literature"].items():
        assert v["source"] in srcs, k
        assert v["locator"] and v["class"] and v["applicability"], k
    for k, v in fresh["inputs"]["analysis"].items():
        assert v["class"] and v["source"], k
    assert fresh["inputs"]["analysis"]["match_bands"]["class"].startswith("PROPOSED")
    for k, v in srcs.items():
        assert v["url"].startswith("https://"), k
    for g in fresh["group_definitions"]:
        assert g["relation_source"] and g["quantity_type"], g["id"]


def test_scope_rules(fresh):
    text = JSON_PATH.read_text()
    assert fresh["architectures"] == ["hall_only", "rf_hall", "ecr_hall"]
    assert "sgb-screen" not in text  # no screening candidate is carried as a source
    assert fresh["b_field_topology"]["admitted_members"] == 0
    for word in ("winner", "recommended architecture", "eliminated architecture"):
        assert word not in text.lower() and word not in MD_PATH.read_text().lower()
    # P5 calibration nuisance never becomes a Vyovrinda option or axis
    env = json.dumps(fresh["vyovrinda_envelope"])
    for token in ("L32", "L38", "1p6kW", "3p0kW", "registration", "coil_shape"):
        assert token not in env, token
    assert set(fresh["milestones"]) == {"A", "B", "C"}


# ---------------------------------------------------------------------------------------------------------------------
# No silent fallbacks; lazy other-lane contracts
# ---------------------------------------------------------------------------------------------------------------------
def test_missing_or_unverified_rate_inputs_raise(mod):
    rel = mod.IN_RATES["N2_ion"]
    with pytest.raises(KeyError):
        mod.RateTable(rel, {})
    with pytest.raises(ValueError):
        mod.RateTable(rel, {Path(rel).name: {"status": "unresolved", "max_mean_energy_eV": 255.0}})
    t = mod.RateTable(rel, {Path(rel).name: {"status": "verified", "max_mean_energy_eV": 45.0}})
    with pytest.raises(ValueError):
        t.at_Te(31.0)  # 46.5 eV mean energy beyond the declared limit
    with pytest.raises(ValueError):
        mod.k_iz_xe(31.0)


def test_related_contracts_resolve_lazily(mod):
    for key, rel in mod.RELATED_PATHS.items():
        try:
            p = mod.related_contract(key)
        except FileNotFoundError as exc:
            assert rel in str(exc)
        else:
            assert p.exists()
