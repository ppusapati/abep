"""Atmosphere v2 with HWM14 winds (abep_sim/atmosphere_orbit_v2.py, dataset atmosphere_msis21_hwm14_orbit_v2).

Authority: A9.17 WINDS / ORBIT / DATA_SIZE (docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json).
The accessor tests run from the frozen files only (no HWM14, no gfortran, no pymsis). The HWM14 re-run tests need the
verified NRL package in $ABEP_HWM14_DIR and gfortran; without them they do not skip (CLAUDE.md rule 9) but branch inside
the test and assert the documented refusal (check: re-run SKIPPED with the reason; runner: HWM14Unavailable).
"""
import gzip
import hashlib
import inspect
import json
import math
import os
import tomllib

import numpy as np
import pytest

from abep_sim import atmosphere_orbit as v1
from abep_sim import atmosphere_orbit_v2 as a2

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Frozen identities of this build (2026-10-01): uncompressed-CSV sha256 of the two tables.
NODE_CSV_SHA256 = "6d9e4f7a48682da759d970d79e1123bd81f5707220cc1b2b091254c2754b1969"
DIST_CSV_SHA256 = "040befc5ea02346ed86c4576332b4c51ff02583bd3a2cd37c0538195c5788609"


def _hwm14_available():
    try:
        a2.hwm14_dir()
        a2.gfortran_version()
    except a2.HWM14Unavailable as e:
        return str(e)
    return None


@pytest.fixture(scope="module")
def meta():
    return json.load(open(a2.JSON_PATH))


# --- frozen data / provenance ----------------------------------------------------------------------------------------
def test_hashes_rows_and_containers(meta):
    raw = a2.read_csv_bytes()
    draw = a2.read_dist_csv_bytes()
    assert hashlib.sha256(raw).hexdigest() == meta["sha256"] == NODE_CSV_SHA256
    assert hashlib.sha256(draw).hexdigest() == meta["disturbance_file"]["sha256"] == DIST_CSV_SHA256
    assert raw.count(b"\n") - 1 == meta["row_count"] == 4 * 19 * 8 * 6 * 8 * 4
    assert draw.count(b"\n") - 1 == meta["disturbance_file"]["row_count"] == 4 * 8 * 37 * 24 * 24
    for path, r in ((a2.GZ_PATH, raw), (a2.DIST_GZ_PATH, draw)):
        gz = open(path, "rb").read()
        assert gz[:10] == v1.GZIP_HEADER and gzip.decompress(gz) == r
        assert v1._gzip_bytes(r) == gz                       # deterministic container
    assert meta["container"]["bytes"] + meta["disturbance_file"]["container"]["bytes"] < 20e6


def test_v1_untouched_and_pinned(meta):
    assert v1.load()["meta"]["sha256"] == a2.V1_CSV_SHA256 == "c0ce282e99695be8cae0834270c5b9ff7853033255665abda7ec18c307566164"
    assert meta["composition"]["thermodynamic_state"]["csv_sha256"] == a2.V1_CSV_SHA256
    assert meta["grid"] == {k: list(v) for k, v in v1.AXES.items()}
    assert meta["scenarios"] == json.loads(json.dumps(v1.SCENARIOS))
    assert a2.DATASET_ID != v1.DATASET_ID and a2.GZ_PATH != v1.GZ_PATH and a2.JSON_PATH != v1.JSON_PATH


def test_grid_is_imported_not_copied():
    src = inspect.getsource(a2)
    assert "v1._grid_points()" in src and "v1.AXES" in src
    assert "ALT_KM = (" not in src and "LAT_DEG = tuple(float(a) for a in range(-90, 91, 10))" not in src


def test_authority_and_labels(meta):
    au = meta["authority"]["A9.17 WINDS"]
    assert au["path"] == "docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json"
    assert au["sha256"] == hashlib.sha256(open(os.path.join(ROOT, au["path"]), "rb").read()).hexdigest()
    assert au["answer"] == "AUTHORIZE_HWM14_ATMOSPHERE_V2_KEEP_V1_IMMUTABLE"
    vb = au["verbatim"]
    md = open(os.path.join(ROOT, vb["path"]), encoding="utf-8").read()
    assert hashlib.sha256(md.encode()).hexdigest() == vb["sha256"] and vb["quote"] in md
    assert meta["authority"]["A9.17 ORBIT"]["answer"] == "ORBIT_INCLINATION_LTAN_TBD_FROM_OFFICIAL_MISSION_ICD"
    assert meta["labels"]["dataset_status"] == "DESIGN_ENVELOPE_PARAMETRIC"
    assert meta["labels"]["mission_trajectory"] is False and meta["labels"]["requirement_input"] is False
    assert meta["orbit_coverage"]["status"] == "CODE_DEFAULT / PARAMETRIC"


def test_producer_records_hwm14_identity(meta):
    p = meta["producer"]
    assert p["version"] == "HWM14.123114"
    assert p["files_sha256"] == a2.HWM14_FILES and p["package"] == a2.HWM14_TGZ
    assert p["package"]["url"].startswith("https://map.nrl.navy.mil/map/pub/nrl/HWM/HWM14/")
    assert p["driver"]["sha256"] == a2.DRIVER_SHA256 == hashlib.sha256(a2.DRIVER_F90.encode()).hexdigest()
    assert p["compiler"].startswith("GNU Fortran") and p["compiler_flags"]
    chk = p["nrl_reference_check"]
    assert chk["passed"] is True
    g = chk["comparisons"]["Check/gfortran.txt"]
    assert g["identical_text"] and g["n_differing_lines"] == 0 and g["max_abs_numeric_diff"] == 0.0
    assert chk["output_sha256"] == a2.HWM14_FILES["Check/gfortran.txt"]   # same bytes as NRL's reference output
    assert meta["year_independence_check"]["max_abs_diff_m_s"] == 0.0
    assert set(p["kp_from_ap"]) == set(v1.SCENARIO_ORDER) and p["kp_from_ap"]["ECSS_LT_LOW"] == 0.0


def test_ap_input_recorded_per_row_and_in_manifest(meta):
    assert "ap(2)" in meta["ap_input"]["hwm14_argument"] and "constant" in meta["ap_input"]["value_passed"]
    raw = a2.read_csv_bytes().decode().splitlines()
    assert raw[0].split(",") == list(a2.COLUMNS)
    n = meta["row_count"] // 4
    for i, s in enumerate(v1.SCENARIO_ORDER):
        f = raw[1 + i * n].split(",")
        assert f[0] == s and float(f[1]) == v1.SCENARIOS[s]["ap"]
        assert int(f[2]) == (v1.EPOCH_YEAR % 100) * 1000 + int(float(f[3]))
        assert math.isclose(float(f[9]), float(f[8]) * 3600.0, abs_tol=1e-3)


def test_source_register_matches_module():
    reg = json.load(open(os.path.join(ROOT, a2.SOURCE_REGISTER)))
    nrl = reg["sources"]["nrl_public_repository"]
    assert nrl["extracted_files_sha256"] == a2.HWM14_FILES
    assert nrl["package_used"]["sha256"] == a2.HWM14_TGZ["sha256"] and nrl["package_used"]["url"] == a2.HWM14_TGZ["url"]
    assert reg["model"]["version"] == a2.HWM14_VERSION
    assert reg["authority"]["sha256"] == a2.A9_17_SHA256
    assert "TERMS_NOT_EXPLICIT" in reg["terms_and_licence"]["open_question_for_owner"]


def test_no_hwm14_code_or_data_redistributed():
    for d, _, files in os.walk(ROOT):
        if any(p in d for p in (".git", ".claude", "node_modules")):
            continue
        for f in files:
            assert f not in ("hwm14.f90", "hwm123114.bin", "dwm07b104i.dat", "gd2qd.dat", "checkhwm14.f90"), \
                os.path.join(d, f)


def test_excluded_from_installed_package():
    pp = tomllib.load(open(os.path.join(ROOT, "pyproject.toml"), "rb"))["tool"]["setuptools"]
    assert "data/atmosphere_msis21_hwm14_orbit_v2*" in pp["exclude-package-data"]["abep_sim"]
    assert not any("hwm14" in x for x in pp["package-data"]["abep_sim"])


def test_interpolation_validation_recorded(meta):
    iv = meta["interpolation_validation"]
    assert iv["n_points_per_scenario"] == a2.INTERP_N and set(iv["by_scenario"]) == set(v1.SCENARIO_ORDER)
    for s, r in iv["by_scenario"].items():
        for k in ("vector_total", "vector_quiet", "vector_disturbance", "relative_speed_corot_wind_m_s",
                  "flow_angle_corot_wind_deg"):
            assert r[k]["max_abs"] >= r[k]["p95_abs"] >= 0.0
        # measured joint error stays well below the wind itself and the orbital speed
        assert r["vector_total"]["max_abs"] < 0.05 * r["direct_wind_speed_max_m_s"] + 6.0
        assert r["flow_angle_corot_wind_deg"]["max_abs"] < 0.2
    dfa = meta["disturbance_file"]["altitude_independence_check"]
    assert max(dfa["max_abs_diff_vs_first_altitude_m_s"].values()) <= a2.DIST_ALT_TOL_M_S
    assert max(meta["node_reproduction"]["max_abs_diff_m_s"].values()) <= 2e-3


def test_missing_data_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(a2, "GZ_PATH", str(tmp_path / "absent.csv.gz"))
    a2._CACHE.clear()
    with pytest.raises(FileNotFoundError, match="abep_sim/data/atmosphere_msis21_hwm14_orbit_v2.csv.gz"):
        a2.load()
    a2._CACHE.clear()


# --- accessor --------------------------------------------------------------------------------------------------------
def test_nodes_reproduce_stored_values():
    L = a2.load()
    rng = np.random.default_rng(7)
    for s in v1.SCENARIO_ORDER:
        for _ in range(20):
            i = [int(rng.integers(n)) for n in L["shape"]]
            node = L["wind"][s][tuple(i)]
            w = a2.wind(v1.ALT_KM[i[1]], v1.LAT_DEG[i[2]], v1.LST_H[i[4]], v1.LON_DEG[i[3]], v1.DOY[i[0]], s)
            assert w["u_mer_quiet_m_s"] == pytest.approx(node[2], abs=1e-9)
            assert w["u_zon_quiet_m_s"] == pytest.approx(node[3], abs=1e-9)
            assert w["u_mer_m_s"] == pytest.approx(node[0], abs=2e-3)
            assert w["u_zon_m_s"] == pytest.approx(node[1], abs=2e-3)


def test_disturbance_nodes_exact():
    L = a2.load()
    s = "ECSS_ST_HIGH"
    for idx in [(0, 0, 0, 0), (3, 18, 7, 13), (7, 36, 23, 23), (5, 27, 11, 2)]:
        node = L["dist"][s][idx]
        w = a2.wind(205.0, a2.DIST_LAT_DEG[idx[1]], a2.DIST_LST_H[idx[3]], a2.DIST_LON_DEG[idx[2]], a2.DIST_DOY[idx[0]], s)
        assert w["u_mer_dist_m_s"] == pytest.approx(node[0], abs=1e-9)
        assert w["u_zon_dist_m_s"] == pytest.approx(node[1], abs=1e-9)


def test_state_combines_v1_and_winds():
    s = a2.state(200.0, 33.3, 14.2, 101.0, 77.0, "ECSS_LT_MODERATE")
    ref = v1.state(200.0, 33.3, 14.2, 101.0, 77.0, "ECSS_LT_MODERATE")
    for k in ("rho_kg_m3", "T_K", "n_O_m3", "x_N2"):
        assert s[k] == ref[k]
    assert s["dataset_status"] == "DESIGN_ENVELOPE_PARAMETRIC" and s["wind_model"] == "HWM14 HWM14.123114"
    assert s["u_mer_m_s"] == pytest.approx(s["u_mer_quiet_m_s"] + s["u_mer_dist_m_s"])
    assert s["wind_interp_max_abs_err_m_s"] is not None


@pytest.mark.parametrize("args", [(179.9, 0, 0, 0, 1), (230.1, 0, 0, 0, 1), (200, 90.5, 0, 0, 1),
                                  (200, 0, 0, 0, 0), (200, 0, 0, 0, 366), (200, 0, 0, 400, 1), (200, float("nan"), 0, 0, 1)])
def test_out_of_domain_refused(args):
    with pytest.raises(ValueError, match="atmosphere_msis21_hwm14_orbit_v2"):
        a2.wind(*args, "ECSS_LT_LOW")


def test_unknown_scenario_refused():
    with pytest.raises(ValueError):
        a2.wind(200, 0, 0, 0, 1, "F107_150")


# --- relative flow ---------------------------------------------------------------------------------------------------
def test_relative_flow_analytic():
    alt, v = 200.0, 7790.0
    corot = a2.OMEGA_E * (a2.R_EARTH + alt * 1e3)
    r = a2.relative_flow(alt, 0.0, [v, 0.0, 0.0], 0.0, 0.0)
    assert r["v_rel_corot_m_s"] == pytest.approx(v - corot) and r["v_rel_corot_wind_m_s"] == r["v_rel_corot_m_s"]
    assert r["angle_deg_corot"] == 0.0 and r["wind_vs_corot_angle_deg"] == 0.0
    r = a2.relative_flow(alt, 0.0, [v, 0.0, 0.0], 100.0, 0.0)            # eastward (tail) wind
    assert r["v_rel_corot_wind_m_s"] == pytest.approx(v - corot - 100.0)
    r = a2.relative_flow(alt, 0.0, [v, 0.0, 0.0], 0.0, 100.0, rho_kg_m3=1e-10)   # northward wind, eastward motion
    assert r["yaw_deg_corot_wind"] == pytest.approx(-math.degrees(math.atan2(100.0, v - corot)))
    assert r["angle_deg_corot_wind"] == pytest.approx(abs(r["yaw_deg_corot_wind"]))
    assert r["wind_cross_track_m_s"] == pytest.approx(100.0) and r["pitch_deg_corot_wind"] == pytest.approx(0.0)
    assert r["flux_corot_wind_kg_m2_s"] == pytest.approx(1e-10 * r["v_rel_corot_wind_m_s"])


@pytest.mark.parametrize("bad", [[0, 0, 0], [0, 0, 7000], [1, 2], [float("inf"), 0, 0]])
def test_relative_flow_rejects_bad_velocity(bad):
    with pytest.raises(ValueError):
        a2.relative_flow(200.0, 10.0, bad, 0.0, 0.0)


def test_orbit_states_require_parametric_inputs():
    sig = inspect.signature(a2.orbit_states)
    assert all(p.default is inspect.Parameter.empty for p in sig.parameters.values())
    with pytest.raises(ValueError):
        a2.orbit_states(200.0, None, 6.0, "ECSS_LT_MODERATE", 80, 0.0, 16)


@pytest.mark.parametrize("inc,ltan", [(96.3, 6.0), (51.6, 13.5), (90.0, 0.0)])
def test_orbit_states_both_relative_flows(inc, ltan):
    st = a2.orbit_states(200.0, inc, ltan, "ECSS_ST_HIGH", 120, 3.0, 24)
    base = v1.orbit_states(200.0, inc, ltan, "ECSS_ST_HIGH", 120, 3.0, 24)
    assert len(st) == 24
    for s, b in zip(st, base):
        assert s["v_rel_corot_m_s"] == pytest.approx(b["v_rel_corot_m_s"], abs=1e-6)
        assert s["rho_kg_m3"] == b["rho_kg_m3"] and s["inclination_deg"] == inc and s["ltan_h"] == ltan
        assert s["wind_included"] is True and s["dataset_status"] == "DESIGN_ENVELOPE_PARAMETRIC"
        assert s["orbit_inputs_status"].startswith("PARAMETRIC")
        assert abs(s["v_sc_enu_m_s"][2]) < 1e-6                          # circular: horizontal velocity
        assert math.hypot(*s["v_sc_enu_m_s"]) == pytest.approx(b["v_orb_m_s"])
        w = math.hypot(s["u_mer_m_s"], s["u_zon_m_s"])
        assert abs(s["v_rel_corot_wind_m_s"] - s["v_rel_corot_m_s"]) <= w + 1e-9
        assert s["flux_corot_wind_kg_m2_s"] == pytest.approx(s["rho_kg_m3"] * s["v_rel_corot_wind_m_s"])
    assert max(abs(s["v_rel_wind_minus_corot_m_s"]) for s in st) > 1.0  # winds matter at ECSS short-term high


# --- check mode / HWM14 re-run -----------------------------------------------------------------------------------------
def test_check_without_hwm14_skips_cleanly(monkeypatch):
    monkeypatch.delenv(a2.HWM_DIR_ENV, raising=False)
    r = a2.check()
    assert r["ok"], r["problems"]
    assert r["hwm14_rerun"]["status"] == "SKIPPED" and a2.HWM_DIR_ENV in r["hwm14_rerun"]["reason"]


def test_check_with_hwm14_reruns():
    why = _hwm14_available()
    if why:
        # HWM14 unavailable (CI): the re-run is SKIPPED with the same reason; the frozen-data checks still decide ok.
        r = a2.check()
        assert r["ok"], r["problems"]
        assert r["hwm14_rerun"]["status"] == "SKIPPED" and r["hwm14_rerun"]["reason"] == why
        return
    r = a2.check()
    assert r["ok"], r["problems"]
    rr = r["hwm14_rerun"]
    assert rr["status"] == "RUN" and rr["nrl_reference_check_passed"]
    assert rr["node_table"]["max_abs_diff_m_s"] <= a2.CHECK_ABS_TOL_M_S
    assert rr["disturbance_table"]["max_abs_diff_m_s"] <= a2.CHECK_ABS_TOL_M_S


def test_direct_hwm14_spot_checks_within_recorded_error(meta):
    why = _hwm14_available()
    if why:
        # HWM14 unavailable: the direct runner refuses cleanly; the frozen accessor still answers within its domain.
        with pytest.raises(a2.HWM14Unavailable):
            a2.HWM14Runner()
        w = a2.wind(200.0, 0.0, 12.0, 0.0, 80.0, v1.SCENARIO_ORDER[0])
        assert math.isfinite(w["u_mer_m_s"]) and math.isfinite(w["u_zon_m_s"])
        return
    runner = a2.HWM14Runner()
    try:
        rng = np.random.default_rng(99)
        for s in v1.SCENARIO_ORDER:
            n = 40
            alt, lat = rng.uniform(180, 230, n), rng.uniform(-90, 90, n)
            lst, lon = rng.uniform(0, 24, n), rng.uniform(0, 360, n)
            doy = rng.integers(1, 366, n).astype(float)
            d = a2.hwm14_points(runner, s, doy, alt, lat, lon, lst)
            tol = meta["interpolation_validation"]["by_scenario"][s]["vector_total"]["max_abs"]
            for i in range(n):
                w = a2.wind(alt[i], lat[i], lst[i], lon[i], doy[i], s)
                err = math.hypot(w["u_mer_m_s"] - d["total"][i, 0], w["u_zon_m_s"] - d["total"][i, 1])
                assert err <= 1.5 * tol
    finally:
        runner.close()


# --- repair findings (A9.17 WINDS review: HWM-2, HWM-3) ---------------------------------------------------------------
def test_hwm2_distribution_statement_matches_packaging_files(meta):
    """HWM-2: the frozen distribution statement must describe what pyproject.toml / MANIFEST.in actually do. It must
    never claim a MANIFEST.in exclude that does not exist (the original statement did)."""
    d = meta["distribution"]
    assert d == json.loads(json.dumps(a2._metadata(b"", b"", 0)["distribution"]))
    assert "MANIFEST.in exclude)" not in json.dumps(d) and "installed_package" not in d
    snap = meta["distribution_snapshot_at_build"]
    assert snap["status"] == "INSPECTED" and snap["wheel_excluded"] is True
    files = snap["files"]
    for name in (os.path.basename(a2.GZ_PATH), os.path.basename(a2.DIST_GZ_PATH), os.path.basename(a2.JSON_PATH)):
        assert files[name]["in_wheel_package_data"] is False, name
    assert files[os.path.basename(a2.GZ_PATH)]["in_sdist"] is False
    assert files[os.path.basename(a2.DIST_GZ_PATH)]["in_sdist"] is False
    # The statement records the build-time state of the manifest JSON in the sdist; it must agree with the snapshot.
    json_in_sdist = files[os.path.basename(a2.JSON_PATH)]["in_sdist"]
    assert ("so the sdist carried the manifest JSON" in d["sdist"]) == json_in_sdist
    assert "EXCLUDED" in d["installed_wheel"] and a2.PYPROJECT_EXCLUDE_GLOB in d["installed_wheel"]
    # Current repository: the tables are never shipped; if MANIFEST.in is unchanged the snapshot is reproduced exactly.
    now = a2.distribution_snapshot()
    assert now["wheel_excluded"] is True
    assert not any(v["in_wheel_package_data"] for v in now["files"].values())
    assert not now["files"][os.path.basename(a2.GZ_PATH)]["in_sdist"]
    assert not now["files"][os.path.basename(a2.DIST_GZ_PATH)]["in_sdist"]
    if now["MANIFEST.in_sha256"] == snap["MANIFEST.in_sha256"]:
        assert now == snap


def test_hwm2_distribution_snapshot_sees_a_manifest_in_exclude(tmp_path):
    """The snapshot inspects MANIFEST.in, so a later exclude line is detected (and not merely asserted in text)."""
    for fn in ("pyproject.toml",):
        (tmp_path / fn).write_bytes(open(os.path.join(ROOT, fn), "rb").read())
    base = open(os.path.join(ROOT, "MANIFEST.in")).read()
    (tmp_path / "MANIFEST.in").write_text(base)
    assert a2.distribution_snapshot(str(tmp_path)) == a2.distribution_snapshot()
    (tmp_path / "MANIFEST.in").write_text(base + "\nexclude abep_sim/data/atmosphere_msis21_hwm14_orbit_v2*\n")
    snap = a2.distribution_snapshot(str(tmp_path))
    assert not any(v["in_sdist"] for v in snap["files"].values())
    assert a2.distribution_snapshot(str(tmp_path / "nowhere"))["status"] == "NOT_A_REPOSITORY_CHECKOUT"


def test_hwm3_dwm07_height_statement_quotes_readme(meta):
    """HWM-3: the DWM07 height limitation quotes the NRL README verbatim (height-constant by construction, cutoff below
    125 km, representative above 225 km) and does not claim a 180-230 km 'transition'."""
    txt = a2.NOT_PROVIDED["disturbance_wind_height_dependence"]
    assert meta["not_provided"]["disturbance_wind_height_dependence"] == txt
    for q in a2.DWM07_README_QUOTE:
        assert q in txt
    assert "inside that transition" not in txt and "height-constant above ~225 km" not in txt
    assert "extrapolation" in txt and "verify" in txt
    # The measured height-constancy supports the statement.
    chk = meta["disturbance_file"]["altitude_independence_check"]
    assert max(chk["max_abs_diff_vs_first_altitude_m_s"].values()) <= chk["tolerance_m_s"]


def test_hwm3_readme_quote_verbatim_in_nrl_package():
    why = _hwm14_available()
    if why:
        # NRL package absent: the verbatim quote cannot be re-read here; the frozen statement must still carry it.
        assert all(q in a2.NOT_PROVIDED["disturbance_wind_height_dependence"] for q in a2.DWM07_README_QUOTE)
        return
    readme = open(os.path.join(a2.hwm14_dir(), "README.txt"), encoding="utf-8").read()
    norm = " ".join(readme.split())
    for q in a2.DWM07_README_QUOTE:
        assert q in norm, q
