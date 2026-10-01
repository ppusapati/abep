"""Orbit-resolved frozen NRLMSIS 2.1 atmosphere (abep_sim/atmosphere_orbit.py, dataset atmosphere_msis21_orbit_v1).

Authority: A9.13 S6.14 / OQ-F4-05 (versioned orbit-resolved dataset), A9.14 S9.7 / OD2 (statewise quantifier) and
S9.8 / OD3 (design states from the dataset). The accessor tests run without pymsis; the producer re-run (check mode)
and the direct-MSIS spot checks are skipped when pymsis is absent (CI pymsis-absent leg).
"""
import gzip
import hashlib
import json
import math
import os
import zlib

import numpy as np
import pytest

from abep_sim import atmosphere_orbit as ao

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# sha256 of the uncompressed v1 CSV as frozen at build time (commit 2c6693a); A9.17 repacked it without changing it.
V1_CSV_SHA256 = "c0ce282e99695be8cae0834270c5b9ff7853033255665abda7ec18c307566164"
# sha256 of json.dumps(design["states"], sort_keys=True) of the v1 design-state set (A9.17 changed labels only).
V1_DESIGN_STATES_CONTENT_SHA256 = "3b854bc622e647810c6bd56008cb05a1b8a80f572cad4cd432c03f5fd01a84f3"


@pytest.fixture(scope="module")
def meta():
    return json.load(open(ao.JSON_PATH))


@pytest.fixture(scope="module")
def design():
    return ao.load_design_states()


# --- provenance / frozen data ----------------------------------------------------------------------------------------
def test_csv_hash_rowcount_and_size(meta):
    raw = ao.read_csv_bytes()
    assert hashlib.sha256(raw).hexdigest() == meta["sha256"] == V1_CSV_SHA256
    assert raw.count(b"\n") - 1 == meta["row_count"] == 4 * 19 * 8 * 6 * 8 * 4
    assert len(raw) == meta["bytes"] < 20e6
    assert meta["columns"] == list(ao.COLUMNS)


def test_provenance_fields(meta):
    p = meta["producer"]
    assert p["model"] == "NRLMSIS 2.1" and p["msis_version_argument"] == 2.1 and p["pymsis_version"] == "0.13.0"
    assert "10.1029/2022JA030896" in p["reference"]
    assert meta["build_command"] == "python -m abep_sim.atmosphere_orbit build"
    assert meta["year_independence_check"]["max_abs_rel_diff"] == 0.0
    assert meta["grid"]["alt_km"][0] == 180.0 and meta["grid"]["alt_km"][-1] == 230.0
    assert meta["grid"]["lat_deg"][0] == -90.0 and meta["grid"]["lat_deg"][-1] == 90.0
    assert meta["orbit_coverage"]["inclination_ltan_status"] == "CODE_DEFAULT / PARAMETRIC"
    assert meta["orbit_coverage"]["requirement_input"] is False
    assert "winds" in meta["not_provided"]
    for k in ("document", "table", "url", "evidence_level", "quantity_type"):
        assert k in meta["drivers"]["source"]
    for k in ("evidence_level", "quantity_type", "uncertainty", "applicability", "validation_status"):
        assert k in meta["evidence"]


def test_scenarios_are_ecss_table_6_3(meta):
    sc = meta["drivers"]["scenarios"]
    assert {k: (v["f107"], v["f107a"], v["ap"]) for k, v in sc.items()} == {
        "ECSS_LT_LOW": (65.0, 65.0, 0.0), "ECSS_LT_MODERATE": (140.0, 140.0, 15.0),
        "ECSS_LT_HIGH": (250.0, 250.0, 45.0), "ECSS_ST_HIGH": (300.0, 250.0, 240.0)}
    assert "Table 6-3" in meta["drivers"]["source"]["table"]


def test_authority_hashes_match_decision_records(meta):
    for key, rec in meta["authority"].items():
        if isinstance(rec, dict):
            with open(os.path.join(ROOT, rec["path"]), "rb") as f:
                assert hashlib.sha256(f.read()).hexdigest() == rec["sha256"], key
    d13 = json.load(open(os.path.join(ROOT, ao.A9_13_JSON)))
    d14 = json.load(open(os.path.join(ROOT, ao.A9_14_JSON)))
    assert d13["decisions"]["OQ-F4-05"]["sequenced_no"] == "S6.14"
    assert d14["decisions"]["OD2"]["sequenced_no"] == "S9.7"
    assert d14["decisions"]["OD3"]["sequenced_no"] == "S9.8"


def test_existing_orbit_averaged_dataset_unchanged():
    m = json.load(open(os.path.join(ROOT, "abep_sim", "data", "atmosphere_msis21_v1.json")))
    raw = open(os.path.join(ROOT, "abep_sim", "data", "atmosphere_msis21_v1.csv"), "rb").read()
    assert hashlib.sha256(raw).hexdigest()[:16] == m["sha256_16"] == "5e108c6e5cb7c03e"


def test_not_wired_into_existing_modules():
    pkg = os.path.join(ROOT, "abep_sim")
    for fn in os.listdir(pkg):
        if fn.endswith(".py") and fn != "atmosphere_orbit.py":
            assert "atmosphere_orbit" not in open(os.path.join(pkg, fn)).read(), fn


# --- accessor --------------------------------------------------------------------------------------------------------
def test_grid_nodes_reproduced_exactly():
    L = ao.load()
    for (i_doy, i_alt, i_lat, i_lon, i_lst) in [(0, 0, 0, 0, 0), (3, 1, 9, 2, 5), (7, 3, 18, 5, 7), (5, 2, 4, 1, 3)]:
        for s in ao.SCENARIO_ORDER:
            n = ao.node_state(i_doy, i_alt, i_lat, i_lon, i_lst, s)
            st = ao.state(ao.ALT_KM[i_alt], ao.LAT_DEG[i_lat], ao.LST_H[i_lst], ao.LON_DEG[i_lon], ao.DOY[i_doy], s)
            for c in ao.OUT_COLS:
                assert math.isclose(st[c], n[c], rel_tol=1e-9), (s, c)
            assert n["rho_kg_m3"] == L["grid"][s][i_doy, i_alt, i_lat, i_lon, i_lst][0]


@pytest.mark.parametrize("kw", [
    dict(alt_km=179.9), dict(alt_km=230.1), dict(lat_deg=90.5), dict(lat_deg=-91.0), dict(doy=0.5), dict(doy=366.0),
    dict(lst_h=24.5), dict(lst_h=-0.1), dict(lon_deg=361.0), dict(alt_km=float("nan")), dict(alt_km=None),
    dict(scenario="F107_150"), dict(scenario="ECSS_LT_MODERATE_"),
])
def test_out_of_domain_refused(kw):
    args = dict(alt_km=200.0, lat_deg=10.0, lst_h=12.0, lon_deg=30.0, doy=100.0, scenario="ECSS_LT_MODERATE")
    args.update(kw)
    with pytest.raises(ValueError):
        ao.state(**args)


def test_state_physics_sanity():
    lo = ao.state(200.0, 0.0, 14.0, 0.0, 80.0, "ECSS_LT_LOW")
    hi = ao.state(200.0, 0.0, 14.0, 0.0, 80.0, "ECSS_LT_HIGH")
    assert hi["rho_kg_m3"] > lo["rho_kg_m3"] and hi["T_K"] > lo["T_K"]
    a = ao.state(180.0, 0.0, 14.0, 0.0, 80.0, "ECSS_LT_MODERATE")
    b = ao.state(230.0, 0.0, 14.0, 0.0, 80.0, "ECSS_LT_MODERATE")
    assert a["rho_kg_m3"] > b["rho_kg_m3"] and b["x_O"] > a["x_O"]
    assert math.isclose(sum(a[f"x_{s}"] for s in ao.FRACTION_SPECIES), 1.0, rel_tol=1e-12)
    # periodicity: LST 24 == 0, lon 360 == 0, lon -90 == 270
    assert math.isclose(ao.state(200, 5, 0.0, 0, 80, "ECSS_LT_LOW")["rho_kg_m3"],
                        ao.state(200, 5, 24.0, 360, 80, "ECSS_LT_LOW")["rho_kg_m3"], rel_tol=1e-12)
    assert math.isclose(ao.state(200, 5, 3.0, -90, 80, "ECSS_LT_LOW")["rho_kg_m3"],
                        ao.state(200, 5, 3.0, 270, 80, "ECSS_LT_LOW")["rho_kg_m3"], rel_tol=1e-12)


def test_interpolation_validation_recorded_and_reported(meta):
    iv = meta["interpolation_validation"]
    assert iv["n_points_per_scenario"] >= 1000 and set(iv["by_scenario"]) == set(ao.SCENARIO_ORDER)
    for s, d in iv["by_scenario"].items():
        assert d["rho_kg_m3"]["max_abs_rel"] < 0.03, s
        for c in ("n_N2_m3", "n_O2_m3", "n_O_m3", "T_K"):
            assert d[c]["max_abs_rel"] < 0.04, (s, c)
    st = ao.state(201.0, 33.0, 7.3, 47.0, 150.0, "ECSS_ST_HIGH")
    assert st["interp_max_rel_err_rho"] == iv["by_scenario"]["ECSS_ST_HIGH"]["rho_kg_m3"]["max_abs_rel"]
    assert st["source"].endswith(meta["sha256"])


def test_direct_msis_spot_check(meta):
    pytest.importorskip("pymsis")
    rng = np.random.default_rng(7)
    for s in ao.SCENARIO_ORDER:
        bound = meta["interpolation_validation"]["by_scenario"][s]["rho_kg_m3"]["max_abs_rel"]
        for _ in range(10):
            alt, lat, lst, lon, doy = rng.uniform(180, 230), rng.uniform(-85, 85), rng.uniform(0, 24), rng.uniform(0, 360), float(rng.integers(1, 366))
            d = ao.msis_points(s, [doy], [alt], [lat], [lon], [lst])[0]
            st = ao.state(alt, lat, lst, lon, doy, s)
            assert abs(st["rho_kg_m3"] / d[0] - 1) <= 1.5 * bound


# --- orbit sampling --------------------------------------------------------------------------------------------------
def test_orbit_states_geometry():
    asm = ao.mission_env_orbit_assumption(205.0)
    assert asm["status"] == "CODE_DEFAULT / PARAMETRIC" and asm["requirement_input"] is False and asm["ltan_h"] == 6.0
    o = ao.orbit_states(205.0, asm["inclination_deg"], asm["ltan_h"], "ECSS_LT_MODERATE", 80, 0.0, 120)
    assert len(o) == 120 and math.isclose(sum(x["weight"] for x in o), 1.0)
    lats = [x["lat_deg"] for x in o]
    assert math.isclose(max(lats), 180.0 - asm["inclination_deg"], abs_tol=0.05)
    assert math.isclose(min(lats), -(180.0 - asm["inclination_deg"]), abs_tol=0.05)
    assert math.isclose(o[0]["lst_h"], 6.0, abs_tol=1e-9)                # ascending node at LTAN
    assert math.isclose(o[60]["lst_h"], 18.0, abs_tol=1e-9)               # descending node opposite
    for x in o:
        assert abs(x["v_rel_corot_m_s"] - x["v_orb_m_s"]) < 600.0
        assert x["v_rel_corot_m_s"] >= x["v_orb_m_s"] - 1e-6 or abs(x["lat_deg"]) > 60   # retrograde SSO: headwind
    assert len({x["state_id"] for x in o}) == 120


def test_orbit_states_requires_inputs():
    with pytest.raises(ValueError):
        ao.orbit_states(205.0, None, 6.0, "ECSS_LT_MODERATE", 80, 0.0, 60)
    with pytest.raises(ValueError):
        ao.orbit_states(205.0, 96.3, 6.0, "ECSS_LT_MODERATE", 80, 0.0, None)
    with pytest.raises(ValueError):
        ao.orbit_states(240.0, 96.3, 6.0, "ECSS_LT_MODERATE", 80, 0.0, 60)
    with pytest.raises(ValueError):
        ao.orbit_states(205.0, 96.3, 6.0, "ECSS_LT_MODERATE", 365, 23.9, 60)   # crosses the dataset year end


# --- design states (S9.8) --------------------------------------------------------------------------------------------
def test_design_states_cover_required_labels(design, meta):
    assert design["dataset_sha256"] == meta["sha256"]
    labels = {l for s in design["states"] for l in s["labels"]}
    for s in ao.SCENARIO_ORDER:
        for a in ao.ALT_KM:
            tag = f"[{s},{a:g}km]"
            for kind in ["NOMINAL_MEDIAN_RHO", "LST_PEAK", "LST_TROUGH"] + \
                        [f"{m}_{q}" for q in ao.EXTREMA_QUANTITIES for m in ("MAX", "MIN")]:
                assert kind + tag in labels, kind + tag
    for q in ao.EXTREMA_QUANTITIES:
        for m in ("MAX", "MIN"):
            assert f"ENVELOPE_{m}_{q}" in labels
    lat_r = design["reachable_lat_max_deg"]
    assert 83.5 < lat_r < 83.8
    for s in design["states"]:
        assert s["required"] is True and abs(s["lat_deg"]) <= lat_r + 1e-9
        assert s["source"].endswith(meta["sha256"]) and s["evaluation"] in ("grid_node", "interpolated")


def test_design_envelope_extrema_are_extreme(design):
    st = design["states"]
    for q in ao.EXTREMA_QUANTITIES:
        mx = [s for s in st if f"ENVELOPE_MAX_{q}" in s["labels"]][0]
        mn = [s for s in st if f"ENVELOPE_MIN_{q}" in s["labels"]][0]
        assert mx[q] == max(s[q] for s in st) and mn[q] == min(s[q] for s in st)
    scen = {s["scenario"] for s in st if any(l.startswith("ENVELOPE_MAX_rho") for l in s["labels"])}
    assert scen == {"ECSS_ST_HIGH"}


def test_design_file_hash(meta):
    raw = open(ao.DESIGN_PATH, "rb").read()
    assert hashlib.sha256(raw).hexdigest() == meta["design_states_file"]["sha256"]


# --- statewise quantifier (S9.7) -------------------------------------------------------------------------------------
def _orbit():
    return ao.orbit_states(205.0, 96.32, 6.0, "ECSS_LT_MODERATE", 80, 0.0, 60)


def test_quantifier_average_cannot_hide_violation():
    o = _orbit()
    rho = sorted(x["rho_kg_m3"] for x in o)
    thr = rho[2] * 1.0000001                                   # two states below threshold, average above
    r = ao.statewise_quantifier(o, lambda s: s["rho_kg_m3"] - thr, "TEST-RHO")
    assert r["verdict"] == "FAIL" and r["n_fail"] >= 2
    assert r["orbit_average_margin"] > 0 and r["average_hides_violation"] is True
    assert r["worst_state"]["margin"] == min(p["margin"] for p in r["per_state"]) < 0
    ok = ao.statewise_quantifier(o, lambda s: s["rho_kg_m3"] - rho[0] * 0.5, "TEST-RHO")
    assert ok["verdict"] == "PASS" and ok["average_hides_violation"] is False


def test_quantifier_fail_closed_and_inputs(design):
    o = _orbit()
    r = ao.statewise_quantifier(o, lambda s: float("nan") if s["u_deg"] == 0 else 1.0, "TEST")
    assert r["verdict"] == "MODEL_ERROR" and r["n_model_error"] == 1 and r["orbit_average_margin"] is None

    def boom(s):
        raise RuntimeError("x")
    assert ao.statewise_quantifier(o, boom, "TEST")["verdict"] == "MODEL_ERROR"
    with pytest.raises(ValueError):
        ao.statewise_quantifier([], lambda s: 1.0, "TEST")
    with pytest.raises(ValueError):
        ao.statewise_quantifier(o, lambda s: 1.0, "")
    b = ao.statewise_quantifier(design["states"], lambda s: s["T_K"] < 1700.0, "TEST-T")
    assert b["orbit_average_margin"] is None and b["verdict"] in ("PASS", "FAIL")
    assert b["verdict"] == ("PASS" if all(s["T_K"] < 1700.0 for s in design["states"]) else "FAIL")


# --- builder check ---------------------------------------------------------------------------------------------------
def test_check_mode_reproduces_subset():
    pytest.importorskip("pymsis")
    import pymsis
    if pymsis.__version__ != "0.13.0":
        pytest.skip("check mode is defined for the recorded pymsis version")
    r = ao.check()
    assert r["ok"], r["problems"]
    assert r["subset_rows"] > 1000


# --- repair lane ATM (review findings ATM-1..ATM-4) ------------------------------------------------------------------
@pytest.mark.parametrize("doy", [320, 321, 335, 350, 365])
def test_orbit_states_late_year_inside_domain(doy):
    # ATM-1: the year-end guard compares against the domain end (365), not the last grid node (320).
    o = ao.orbit_states(200.0, 96.3, 6.0, "ECSS_LT_MODERATE", doy, 0.0, 8)
    assert len(o) == 8 and all(x["doy"] == float(doy) for x in o)
    assert all(math.isfinite(x["rho_kg_m3"]) and x["rho_kg_m3"] > 0 for x in o)


def test_orbit_states_year_end_and_doy_domain_refused():
    with pytest.raises(ValueError, match="end of the dataset year"):
        ao.orbit_states(200.0, 96.3, 6.0, "ECSS_LT_MODERATE", 365, 23.9, 8)
    for doy in (0, 366):
        with pytest.raises(ValueError):
            ao.orbit_states(200.0, 96.3, 6.0, "ECSS_LT_MODERATE", doy, 0.0, 8)
    # crossing midnight inside the year moves to the next day and is fine
    o = ao.orbit_states(200.0, 96.3, 6.0, "ECSS_LT_MODERATE", 364, 23.9, 8)
    assert {x["doy"] for x in o} == {364.0, 365.0}


def test_rho_metadata_excludes_no(meta):
    # ATM-2: rho_kg_m3 is pymsis MASS_DENSITY, which excludes NO.
    assert meta["dropped_species"]["in_rho"] == {"H": True, "ANOMALOUS_O": True, "NO": False} == ao.DROPPED_IN_RHO
    assert "EXCLUDES NO" in meta["units"]["rho_kg_m3"] and "includes all MSIS species" not in meta["units"]["rho_kg_m3"]
    rc = meta["rho_composition_check"]
    assert rc["in_rho"]["NO"] is False
    assert all(rc["in_rho"][k] for k in ("N2", "O2", "O", "He", "H", "Ar", "N", "ANOMALOUS_O"))
    e1 = [e for e in meta["errata"] if e["id"] == "E1"][0]
    assert e1["review_finding"] == "ATM-2" and e1["data_file_changed"] is False
    # the correction left the frozen data file untouched
    assert hashlib.sha256(ao.read_csv_bytes()).hexdigest() == meta["sha256"]


def test_rho_composition_regression_direct():
    pytest.importorskip("pymsis")
    rc = ao._rho_composition_check()
    assert rc["in_rho"]["NO"] is False and abs(rc["implied_mass_amu"]["NO"]) < ao.RHO_COEF_THRESHOLD_AMU
    assert rc["max_abs_rel_residual"] < 1e-5
    for k in ("H", "ANOMALOUS_O"):
        assert rc["in_rho"][k] is True


@pytest.mark.parametrize("weights", [(0.0, 0.0), (1.0, -0.5), (1.0, float("nan")), (1.0, float("inf")),
                                     (1.0, True), (1.0, "1")])
def test_quantifier_rejects_invalid_weights(weights):
    # ATM-3: zero-sum, negative, non-finite or non-numeric weights are refused (no ZeroDivisionError, no silent avg).
    st = [{"state_id": "a", "weight": weights[0]}, {"state_id": "b", "weight": weights[1]}]
    with pytest.raises(ValueError):
        ao.statewise_quantifier(st, lambda s: 1.0, "TEST")


def test_quantifier_valid_zero_weight_member_allowed():
    st = [{"state_id": "a", "weight": 0.0}, {"state_id": "b", "weight": 2.0}]
    r = ao.statewise_quantifier(st, lambda s: -1.0 if s["state_id"] == "a" else 3.0, "TEST")
    assert r["verdict"] == "FAIL" and r["orbit_average_margin"] == 3.0 and r["average_hides_violation"] is True
    assert r["worst_state"]["state_id"] == "a"


def test_wind_omission_tracked_as_open_item(meta):
    # ATM-4: OQ-F4-05 lists wind; v1 does not deliver it -> explicit open deviation for owner disposition.
    oi = {x["id"]: x for x in meta["open_items"]}["ATM-OI-01"]
    assert oi["status"] == "OPEN_DEVIATION_FOR_OWNER_DISPOSITION"
    assert oi["authority"]["question_id"] == "OQ-F4-05"
    rec = open(os.path.join(ROOT, oi["authority"]["path"]), "rb").read()
    assert oi["authority"]["sha256"] == hashlib.sha256(rec).hexdigest()
    o = ao.orbit_states(205.0, 96.32, 6.0, "ECSS_LT_MODERATE", 80, 0.0, 8)
    assert all(x["wind_included"] is False and x["wind_open_item"] == "ATM-OI-01" for x in o)


# --- A9.17 DATA_SIZE: one canonical compressed copy, excluded from the installed package ---------------------------
A9_17 = "docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json"


def test_a9_17_authority_recorded(meta):
    rec = open(os.path.join(ROOT, A9_17), "rb").read()
    assert hashlib.sha256(rec).hexdigest() == ao.A9_17_SHA256
    md = open(os.path.join(ROOT, ao.A9_17_MD), "rb").read()
    assert hashlib.sha256(md).hexdigest() == ao.A9_17_MD_SHA256 == json.loads(rec)["verbatim"]["sha256"]
    d = json.loads(rec)["decisions"]
    assert d["DATA_SIZE"]["answer"] == meta["distribution"]["authority"]["answer"]
    assert d["ORBIT"]["answer"] == meta["orbit_coverage"]["authority"]["answer"]


def test_single_canonical_gzip_copy(meta):
    assert not os.path.exists(ao.LEGACY_CSV_PATH), "uncompressed copy must not be kept next to the .csv.gz"
    assert meta["file"] == os.path.basename(ao.GZ_PATH) == "atmosphere_msis21_orbit_v1.csv.gz"
    gz = open(ao.GZ_PATH, "rb").read()
    c = meta["container"]
    assert hashlib.sha256(gz).hexdigest() == c["sha256"] and len(gz) == c["bytes"]
    # deterministic header: magic, deflate, FLG 0 (no file name / comment / extra), MTIME 0, XFL 2, OS 255
    assert gz[:10] == b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff"
    assert c["mtime"] == 0 and c["fname_in_header"] is False and c["compresslevel"] == ao.GZIP_LEVEL
    raw = gzip.decompress(gz)
    assert hashlib.sha256(raw).hexdigest() == meta["sha256"] == V1_CSV_SHA256 and len(raw) == meta["bytes"]
    if zlib.ZLIB_VERSION == c["zlib_version"]:
        assert ao._gzip_bytes(raw) == gz                     # the writer reproduces the stored container
    e3 = {e["id"]: e for e in meta["errata"]}["E3"]
    assert e3["data_file_changed"] is False and V1_CSV_SHA256 in e3["now"]


def test_load_verifies_uncompressed_hash(tmp_path, monkeypatch):
    raw = ao.read_csv_bytes()
    bad = raw.replace(b"ECSS_LT_LOW,65", b"ECSS_LT_LOW,66", 1)
    p = tmp_path / "tampered.csv.gz"
    p.write_bytes(ao._gzip_bytes(bad))
    meta = json.load(open(ao.JSON_PATH))
    meta["container"]["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()   # container hash "fixed up"
    with pytest.raises(RuntimeError, match="uncompressed CSV sha256"):
        monkeypatch.setattr(ao, "GZ_PATH", str(p))
        ao.read_csv_bytes(meta)
    monkeypatch.undo()
    with pytest.raises(RuntimeError, match="container sha256"):
        monkeypatch.setattr(ao, "GZ_PATH", str(p))
        ao.read_csv_bytes()                                   # recorded container hash no longer matches


def test_missing_data_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ao, "GZ_PATH", str(tmp_path / "absent.csv.gz"))
    monkeypatch.setattr(ao, "_CACHE", {})
    with pytest.raises(FileNotFoundError) as e:
        ao.load()
    msg = str(e.value)
    assert "abep_sim/data/atmosphere_msis21_orbit_v1.csv.gz" in msg and "no fallback" in msg.lower()
    assert "A9.17" in msg
    with pytest.raises(FileNotFoundError):
        ao.state(200.0, 0.0, 12.0, 0.0, 80.0, "ECSS_LT_MODERATE")


def test_distribution_record(meta):
    d = meta["distribution"]
    assert d["installed_package"].startswith("EXCLUDED") and d["repository_path"] == ao.REPO_DATA_PATH
    assert d["authority"]["decision_key"] == "DATA_SIZE" and d["authority"]["sha256"] == ao.A9_17_SHA256


# --- A9.17 ORBIT: 96.3 deg / dawn-dusk is CODE_DEFAULT / PARAMETRIC, never a requirement input ----------------------
def test_orbit_default_labelled_code_default(meta, design):
    oc = meta["orbit_coverage"]
    assert oc["inclination_ltan_status"] == ao.ORBIT_STATUS == "CODE_DEFAULT / PARAMETRIC"
    assert oc["requirement_input"] is False and "TBD" in oc["real_orbit"]
    assert oc["authority"]["decision_key"] == "ORBIT" and oc["authority"]["sha256"] == ao.A9_17_SHA256
    assert "MODEL_ASSUMPTION" not in json.dumps(oc)
    ob = design["orbit_basis"]
    assert ob["status"] == "CODE_DEFAULT / PARAMETRIC" and ob["requirement_input"] is False
    assert "all local times" in ob["local_time"]
    assert "CODE_DEFAULT / PARAMETRIC" in design["rule"] and "A9.17 ORBIT" in design["authority"]
    for fn in (ao.mission_env_orbit_assumption, ao.reachable_lat_max_deg, ao.design_states, ao.orbit_states):
        assert "PARAMETRIC" in fn.__doc__, fn.__name__
    o = ao.orbit_states(205.0, 96.32, 6.0, "ECSS_LT_MODERATE", 80, 0.0, 4)
    assert all(x["orbit_inputs_status"].startswith("PARAMETRIC") for x in o)
    e4 = {e["id"]: e for e in meta["errata"]}["E4"]
    assert e4["data_file_changed"] is False


def test_design_states_content_unchanged_by_labels(design):
    # A9.17 regenerated the design-state file with label changes only: the 179 per-state records are the v1 ones.
    h = hashlib.sha256(json.dumps(design["states"], sort_keys=True).encode()).hexdigest()
    assert h == V1_DESIGN_STATES_CONTENT_SHA256 and design["n_states"] == len(design["states"]) == 179
    lats = [abs(s["lat_deg"]) for s in design["states"]]
    assert max(lats) == pytest.approx(design["reachable_lat_max_deg"])          # envelope still spans all LSTs
    assert {s["lst_h"] for s in design["states"]} >= {0.0, 3.0, 6.0, 15.0}
