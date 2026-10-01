"""Orbit-resolved frozen NRLMSIS 2.1 atmosphere, version v1 (``atmosphere_msis21_orbit_v1``).

Authority (immutable owner records; cite path + json sha256 + question id):

* A9.13 S6.14 / OQ-F4-05 -- ``docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json``
  (sha256 9afaca459efe27556033d836814f71bd03203711627899f3ffc494567d763b23): authorises a CLAUDE.md rule-1 versioned,
  orbit-resolved frozen atmosphere dataset; the orbit-averaged ``atmosphere_msis21_v1.*`` stays unchanged; "do not invent
  an arbitrary density-modulation amplitude when an orbit-resolved producer can supply the physical variation".
* A9.14 S9.7 / OD2 and S9.8 / OD3 -- ``docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json``
  (sha256 c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c): statewise envelope quantifier (every
  required state, fail closed; worst state and orbit average reported additionally) and design states taken from this
  versioned dataset (nominal states + physical extrema of density / species / temperature / local time / solar activity).

The dataset is a tensor grid of NRLMSIS 2.1 (pymsis) evaluations over geodetic altitude, geodetic latitude, local solar
time, geographic longitude and day of year, for each of four discrete solar/geomagnetic driver scenarios taken verbatim
from ECSS-E-ST-10-04C Rev.1 (15 June 2020) Table 6-3. Scenarios are discrete: there is no interpolation between them.

Usage::

    python -m abep_sim.atmosphere_orbit build   # regenerate the CSV + JSON (rule 1: intentional rebuild only)
    python -m abep_sim.atmosphere_orbit check   # verify hashes and re-run a deterministic subset with pymsis

Nothing in the existing simulator imports this module (it is not wired into atmosphere.py / mission_env.py).
"""
from __future__ import annotations

import hashlib
import inspect
import io
import json
import math
import os
import sys
from dataclasses import dataclass

import numpy as np

from .constants import MU_EARTH, R_EARTH
from .mission_env import OMEGA_E, Spacecraft, sso_inclination_deg

DATASET_ID = "atmosphere_msis21_orbit_v1"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CSV_PATH = os.path.join(DATA_DIR, DATASET_ID + ".csv")
JSON_PATH = os.path.join(DATA_DIR, DATASET_ID + ".json")
DESIGN_PATH = os.path.join(DATA_DIR, DATASET_ID + "_design_states.json")
BUILD_COMMAND = "python -m abep_sim.atmosphere_orbit build"
CHECK_COMMAND = "python -m abep_sim.atmosphere_orbit check"

A9_13_JSON = "docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json"
A9_13_SHA256 = "9afaca459efe27556033d836814f71bd03203711627899f3ffc494567d763b23"
A9_14_JSON = "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json"
A9_14_SHA256 = "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c"

MSIS_VERSION = 2.1
PYMSIS_VERSION_BUILT = "0.13.0"
# MSIS evaluates day-of-year + UT seconds; the calendar year only maps doy to a datetime. A non-leap year keeps the doy
# axis 1..365 without a Feb-29 node. Year independence is verified at build time (recorded in the JSON).
EPOCH_YEAR = 2027

# ---------------------------------------------------------------------------------------------------------------------
# Grid (see GRID_TRADE for the measured interpolation errors that justify each step).
# ---------------------------------------------------------------------------------------------------------------------
ALT_KM = (180.0, 195.0, 215.0, 230.0)                           # both RFP endpoints; global cubic in altitude
LAT_DEG = tuple(float(a) for a in range(-90, 91, 10))             # full geodetic latitude band, poles included; cubic
LST_H = tuple(float(h) for h in range(0, 24, 3))                  # periodic (24 h == 0 h); trigonometric
LON_DEG = (0.0, 60.0, 120.0, 180.0, 240.0, 300.0)                # periodic (360 == 0); trigonometric
DOY_PERIOD = 365.0
DOY_M = 8
# integer MSIS days nearest to the equispaced positions 1 + k * 365/8 (trigonometric in doy, period 365 d)
DOY = tuple(float(1 + int(math.floor(k * DOY_PERIOD / DOY_M + 0.5))) for k in range(DOY_M))
AXES = {"alt_km": ALT_KM, "lat_deg": LAT_DEG, "lst_h": LST_H, "lon_deg": LON_DEG, "doy": DOY}
PERIODIC = {"lst_h": 24.0, "lon_deg": 360.0, "doy": DOY_PERIOD}
INTERPOLATION = {
    "quantity": "natural log of every output column (densities, rho and T)",
    "alt_km": "cubic Lagrange through the 4 altitude nodes",
    "lat_deg": "local cubic Lagrange (4 nearest nodes, clipped at the ends)",
    "lst_h": "trigonometric interpolation, 8 equispaced nodes, period 24 h",
    "lon_deg": "trigonometric interpolation, 6 equispaced nodes, period 360 deg",
    "doy": "trigonometric interpolation, period 365 d, 8 integer-day nodes nearest to 1 + k*365/8; doy is warped "
           "piecewise-linearly onto the equispaced positions (<= 0.5 d) so nodes are reproduced exactly",
    "scenario": "none (discrete)"}

ECSS_SOURCE = {
    "document": "ECSS-E-ST-10-04C Rev.1, Space engineering - Space environment, 15 June 2020",
    "table": "Table 6-3: Reference fixed index values (clause 6.2.2b; NOTE 1: rounded numbers from solar cycle 23)",
    "url": "https://ecss.nl/wp-content/uploads/2020/07/ECSS-E-ST-10-04C-Rev.1(15June2020).pdf",
    "pdf_sha256_as_downloaded_2026_10_01": "c8bbbc139066eab8300665206b581a2d1b40a9b6ace6342831403078fc4204bc",
    "access": "open download from ecss.nl",
    "evidence_level": 4,
    "quantity_type": "assumed (standardised reference index values; not a forecast of the mission epoch)",
}

# Scenario drivers verbatim from ECSS Table 6-3. The short-term high case uses F10.7 = 300 with the long-term high
# 81-day average 250, as ECSS Annex G lists it ("F10.7 = 300, F10.7avg = 250, ..., Ap = 240") and as clause 7.2.1
# NOTE 5 requires ("high short term values combined with high 81-day averaged values").
SCENARIOS = {
    "ECSS_LT_LOW": {"f107": 65.0, "f107a": 65.0, "ap": 0.0, "label": "long-term (27+ days) low",
                    "row_ref": "Table 6-3 long-term Low column"},
    "ECSS_LT_MODERATE": {"f107": 140.0, "f107a": 140.0, "ap": 15.0, "label": "long-term (27+ days) moderate",
                         "row_ref": "Table 6-3 long-term Moderate column"},
    "ECSS_LT_HIGH": {"f107": 250.0, "f107a": 250.0, "ap": 45.0, "label": "long-term (27+ days) high",
                     "row_ref": "Table 6-3 long-term High column"},
    "ECSS_ST_HIGH": {"f107": 300.0, "f107a": 250.0, "ap": 240.0, "label": "short-term (daily) high",
                     "row_ref": "Table 6-3 short-term High column (F10.7 300, Ap 240); F10.7avg 250 from Annex G "
                                "high-short-term case / clause 7.2.1 NOTE 5"},
}
SCENARIO_ORDER = tuple(SCENARIOS)
NOMINAL_SCENARIO = "ECSS_LT_MODERATE"

# Output columns (number densities m^-3, mass density kg m^-3, temperature K) straight from pymsis.Variable.
SPECIES = ("N2", "O2", "O", "He", "Ar", "N")
DROPPED_SPECIES = ("H", "ANOMALOUS_O", "NO")   # in rho, not stored; build records their max share
OUT_COLS = ("rho_kg_m3",) + tuple(f"n_{s}_m3" for s in SPECIES) + ("T_K",)
IN_COLS = ("scenario", "f107", "f107a", "ap", "doy", "alt_km", "lat_deg", "lon_deg", "lst_h", "ut_h")
COLUMNS = IN_COLS + OUT_COLS
FLOAT_FMT = "%.6e"
# Species entering the mole fractions reported by the accessor (the stored species; the dropped ones' measured max
# share of the total number density is recorded in the metadata under dropped_species).
FRACTION_SPECIES = ("O", "N2", "O2", "N", "He", "Ar")

GRID_TRADE = (
    "Size target < ~20 MB. A plain multilinear 5-D grid of that size (alt 10 km, lat 15 deg, LST 2 h, lon 90 deg, "
    "doy ~46 d) was built and validated first: joint max |rel. error| vs direct NRLMSIS was 6-8 % in rho and up to 27 % "
    "in n(O) (ECSS short-term high), so it was rejected. NRLMSIS log-densities are close to band-limited in LST, "
    "longitude and day of year (harmonic expansions) and smooth in latitude/altitude, so the grid stores fewer nodes "
    "and the accessor interpolates log quantities spectrally/cubically (see interpolation). One-axis studies vs direct "
    "NRLMSIS 2.1 (1500 random points; ECSS long-term low, moderate and short-term high; max |rel. error| over rho, "
    "n_N2, n_O2, n_O, T): LST 8 trig nodes <= 3.4 % (12 nodes <= 0.3 %; linear 12 nodes <= 13 %); lon 6 trig nodes "
    "<= 0.6 % (4 nodes <= 5.5 %; linear 4 nodes <= 15 %); doy 8 trig nodes (period 365) <= 1.4 % (cubic on 9 nodes "
    "<= 6.3 %); lat cubic 10 deg <= 1.1 % (15 deg <= 4.0 %); alt cubic 10 km <= 0.02 %, so 4 altitude nodes "
    "(180/195/215/230 km, both endpoints) suffice. LST is the binding axis (8 nodes); 12 LST nodes would need ~26 MB. "
    "Grid 4 alt x 19 lat x 8 LST x 6 lon x 8 doy x 4 scenarios = 116,736 rows. H, anomalous O and NO are not stored "
    "(dropped_species). The joint interpolation error is measured at build time for every scenario "
    "(interpolation_validation) and reported by the accessor with every interpolated state.")


# ---------------------------------------------------------------------------------------------------------------------
# Producer
# ---------------------------------------------------------------------------------------------------------------------
def _ut_h(lst_h, lon_deg):
    return np.mod(np.asarray(lst_h, float) - np.asarray(lon_deg, float) / 15.0, 24.0)


def _dates(doy, ut_h, year=EPOCH_YEAR):
    doy = np.asarray(doy, float); ut_h = np.asarray(ut_h, float)
    if np.any(doy != np.round(doy)):
        raise ValueError("MSIS day-of-year must be integral (fractional days are carried by UT)")
    sec = (np.round(doy).astype(np.int64) - 1) * 86400 + np.round(ut_h * 3600.0).astype(np.int64)
    return np.datetime64(f"{year}-01-01T00:00:00", "s") + sec.astype("timedelta64[s]")


def msis_points(scenario: str, doy, alt_km, lat_deg, lon_deg, lst_h, year=EPOCH_YEAR, raw: bool = False) -> np.ndarray:
    """Direct NRLMSIS 2.1 (pymsis) fly-through evaluation; returns an (n, len(OUT_COLS)) array in OUT_COLS order
    (raw=True: the full (n, 11) pymsis output in pymsis.Variable order)."""
    import pymsis
    if scenario not in SCENARIOS:
        raise KeyError(f"unknown scenario {scenario!r}; known: {SCENARIO_ORDER}")
    sc = SCENARIOS[scenario]
    alt_km, lat_deg, lon_deg, lst_h, doy = (np.atleast_1d(np.asarray(x, float)) for x in (alt_km, lat_deg, lon_deg, lst_h, doy))
    n = len(alt_km)
    ut = _ut_h(lst_h, lon_deg)
    d = _dates(doy, ut, year)
    out = pymsis.calculate(d, lon_deg, lat_deg, alt_km, f107s=np.full(n, sc["f107"]), f107as=np.full(n, sc["f107a"]),
                           aps=np.tile([sc["ap"]] * 7, (n, 1)), version=MSIS_VERSION)
    out = np.asarray(out, float).reshape(n, -1)
    if raw:
        return out
    V = pymsis.Variable
    order = [V.MASS_DENSITY, V.N2, V.O2, V.O, V.HE, V.AR, V.N, V.TEMPERATURE]
    res = out[:, [int(v) for v in order]]
    if not np.all(np.isfinite(res)):
        raise RuntimeError("NRLMSIS returned non-finite values inside the declared grid; refusing to freeze them")
    return res


def _grid_points():
    """Rows in canonical order: scenario, doy, alt, lat, lon, lst (lst fastest)."""
    g = np.meshgrid(DOY, ALT_KM, LAT_DEG, LON_DEG, LST_H, indexing="ij")
    return [x.ravel() for x in g]


def _fmt(v: float) -> str:
    return FLOAT_FMT % v


def _fmt_in(v: float) -> str:
    return repr(float(v)) if v != int(v) else str(int(v))


def _rows_text(scenario, doy, alt, lat, lon, lst, out) -> list[str]:
    sc = SCENARIOS[scenario]
    ut = _ut_h(lst, lon)
    lines = []
    head = ",".join([scenario, _fmt_in(sc["f107"]), _fmt_in(sc["f107a"]), _fmt_in(sc["ap"])])
    for i in range(len(alt)):
        lines.append(",".join([head, _fmt_in(doy[i]), _fmt_in(alt[i]), _fmt_in(lat[i]), _fmt_in(lon[i]), _fmt_in(lst[i]),
                               _fmt_in(round(float(ut[i]), 6))] + [_fmt(v) for v in out[i]]))
    return lines


def _year_independence() -> dict:
    """MSIS uses day-of-year and UT only; show it on a few points (recorded, not assumed)."""
    pts = dict(doy=[47.0, 230.0], alt_km=[180.0, 230.0], lat_deg=[-45.0, 60.0], lon_deg=[90.0, 270.0], lst_h=[4.0, 14.0])
    a = msis_points(NOMINAL_SCENARIO, year=EPOCH_YEAR, **pts)
    b = msis_points(NOMINAL_SCENARIO, year=2031, **pts)
    return {"years_compared": [EPOCH_YEAR, 2031], "max_abs_rel_diff": float(np.max(np.abs(b / a - 1.0)))}


def build() -> dict:
    import pymsis
    if pymsis.__version__ != PYMSIS_VERSION_BUILT:
        raise RuntimeError(f"pymsis {pymsis.__version__} installed; v1 is defined with {PYMSIS_VERSION_BUILT}. A different "
                           "producer version is a new dataset version (rule 1), not a silent rebuild.")
    doy, alt, lat, lon, lst = _grid_points()
    lines = [",".join(COLUMNS)]
    dropped = {}
    V = pymsis.Variable
    stored_idx = [int(V.N2), int(V.O2), int(V.O), int(V.HE), int(V.AR), int(V.N)]
    for s in SCENARIO_ORDER:
        full = msis_points(s, doy, alt, lat, lon, lst, raw=True)
        drop = {d: np.nan_to_num(full[:, int(getattr(V, d))]) for d in DROPPED_SPECIES}
        n_all = np.sum(full[:, stored_idx], axis=1) + sum(drop.values())
        dropped[s] = {d: float(np.max(v / n_all)) for d, v in drop.items()}
        out = msis_points(s, doy, alt, lat, lon, lst)
        lines += _rows_text(s, doy, alt, lat, lon, lst, out)
    text = "\n".join(lines) + "\n"
    with open(CSV_PATH, "w", newline="\n") as f:
        f.write(text)
    sha = hashlib.sha256(text.encode()).hexdigest()
    _CACHE.clear()
    meta = _metadata(sha, len(lines) - 1)
    meta["dropped_species"] = {"species": list(DROPPED_SPECIES), "in_rho": True,
                               "reason": "not requested by the lane; keeps the CSV < 20 MB",
                               "max_number_density_share_over_grid": dropped}
    with open(JSON_PATH, "w") as f:      # provisional (hash + grid) so the accessor can load for validation
        json.dump(meta, f)
    meta["year_independence_check"] = _year_independence()
    meta["interpolation_validation"] = _interpolation_validation()
    meta["check_subset"] = _check_subset_record()
    ds_text = _design_states_text()
    with open(DESIGN_PATH, "w", newline="\n") as f:
        f.write(ds_text)
    meta["design_states_file"] = {"file": os.path.basename(DESIGN_PATH),
                                  "sha256": hashlib.sha256(ds_text.encode()).hexdigest(),
                                  "producer": "design_states() on this dataset (A9.14 S9.8 OD3)"}
    with open(JSON_PATH, "w") as f:
        json.dump(meta, f, indent=1, sort_keys=False)
        f.write("\n")
    _CACHE.clear()
    return meta


def _metadata(sha: str, n_rows: int) -> dict:
    import pymsis
    return {
        "dataset_id": DATASET_ID,
        "file": os.path.basename(CSV_PATH),
        "sha256": sha,
        "row_count": n_rows,
        "bytes": os.path.getsize(CSV_PATH),
        "columns": list(COLUMNS),
        "units": {"f107": "sfu (1e-22 W m-2 Hz-1)", "f107a": "sfu, 81-day average", "ap": "daily Ap", "doy": "day of year",
                  "alt_km": "km, geodetic (WGS84)", "lat_deg": "deg, geodetic (WGS84)", "lon_deg": "deg east",
                  "lst_h": "h, local solar time = UT + lon/15", "ut_h": "h, UT = (lst_h - lon_deg/15) mod 24",
                  "rho_kg_m3": "kg m-3 total mass density (includes all MSIS species and anomalous O)",
                  **{f"n_{s}_m3": "m-3 number density" for s in SPECIES}, "T_K": "K, local neutral temperature"},
        "row_order": "scenario (as in scenarios), then doy, alt_km, lat_deg, lon_deg, lst_h (lst fastest)",
        "float_format": FLOAT_FMT,
        "producer": {"model": "NRLMSIS 2.1", "msis_version_argument": MSIS_VERSION, "package": "pymsis",
                     "pymsis_version": pymsis.__version__, "python": sys.version.split()[0],
                     "numpy": np.__version__, "call": "pymsis.calculate(dates, lons, lats, alts, f107s, f107as, aps, "
                     "version=2.1) in fly-through mode; default model switches; geomagnetic_activity = 1 (pymsis "
                     "default, msis.py: daily Ap mode, aps[1:] unused); aps given as [Ap]*7",
                     "reference": "Emmert, J. T., et al. (2022), NRLMSIS 2.1: An empirical model of nitric oxide "
                                  "incorporated into MSIS, J. Geophys. Res. Space Physics 127(10), e2022JA030896, "
                                  "doi:10.1029/2022JA030896 (DOI confirmed by web search 2026-10-01)"},
        "epoch": {"year": EPOCH_YEAR, "role": "calendar mapping of doy only; MSIS uses doy + UT seconds",
                  "status": "model assumption"},
        "drivers": {"source": ECSS_SOURCE, "scenarios": SCENARIOS, "scenario_order": list(SCENARIO_ORDER),
                    "interpolation_between_scenarios": "NONE (discrete scenarios; accessor refuses other drivers)",
                    "not_included": "Table 6-4 3-hourly ap storm profile; F10.7 = 380 / ap = 400 extremes "
                                    "(ECSS Table 6-3 NOTE 3: models not developed for them); the project's earlier "
                                    "F10.7 70/150/230 set (atmosphere.py) carries no external citation and is not reused"},
        "grid": {k: list(v) for k, v in AXES.items()},
        "grid_periodic": PERIODIC,
        "grid_trade": GRID_TRADE,
        "interpolation": INTERPOLATION,
        "domain": {"alt_km": [ALT_KM[0], ALT_KM[-1]], "lat_deg": [-90.0, 90.0], "lst_h": [0.0, 24.0],
                   "lon_deg": [-180.0, 360.0], "doy": [1.0, DOY_PERIOD],
                   "out_of_domain": "ValueError (no extrapolation); unknown scenario: ValueError"},
        "orbit_coverage": {
            "inclination_source": "abep_sim/mission_env.py sso_inclination_deg(alt) (J2 sun-synchronous condition) and "
                                  "Spacecraft.inc_deg = 96.33 / ltan_h = 6.0 defaults",
            "inclination_status": "MODEL_ASSUMPTION (not owner-registered); the grid covers the full latitude band "
                                  "-90..90 deg so any SSO inclination (180-230 km: 96.25-96.42 deg, max |lat| 83.6-83.75 "
                                  "deg) and any LTAN are inside the dataset",
            "sso_inclination_deg_at_grid_alt": {str(int(a)): round(sso_inclination_deg(a), 4) for a in ALT_KM}},
        "not_provided": {"winds": "NRLMSIS has no wind output; ECSS 7.2.2 names HWM07, which is not installed. The "
                                  "accessor reports the geometric co-rotating-atmosphere relative speed only "
                                  "(status: no thermospheric wind)."},
        "authority": {"A9.13 S6.14 OQ-F4-05": {"path": A9_13_JSON, "sha256": A9_13_SHA256},
                      "A9.14 S9.7 OD2": {"path": A9_14_JSON, "sha256": A9_14_SHA256},
                      "A9.14 S9.8 OD3": {"path": A9_14_JSON, "sha256": A9_14_SHA256},
                      "CLAUDE.md rule 1": "versioned rebuild; atmosphere_msis21_v1.* unchanged"},
        "evidence": {"evidence_level": 4, "quantity_type": "model-derived (empirical climatology model output)",
                     "uncertainty": "NRLMSIS climatological model uncertainty (not quantified here) + recorded grid "
                                    "interpolation error; ECSS 7.2.1 NOTE 1: models resolve ~1000 km / 3 h scales "
                                    "only; real density can deviate (e.g. +100 %/-50 % in 30 s)",
                     "applicability": "180-230 km geodetic, all latitudes / local times / longitudes / seasons, the "
                                      "four ECSS driver scenarios only",
                     "validation_status": "not independently validated by the project"},
        "build_command": BUILD_COMMAND,
        "check_command": CHECK_COMMAND,
    }


# ---------------------------------------------------------------------------------------------------------------------
# Loader + interpolating accessor
# ---------------------------------------------------------------------------------------------------------------------
_CACHE: dict = {}


def load(verify_hash: bool = True) -> dict:
    if "grid" in _CACHE:
        return _CACHE
    if not (os.path.exists(CSV_PATH) and os.path.exists(JSON_PATH)):
        raise FileNotFoundError(f"{DATASET_ID} not built; run `{BUILD_COMMAND}`")
    raw = open(CSV_PATH, "rb").read()
    meta = json.load(open(JSON_PATH))
    if verify_hash and hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise RuntimeError(f"{CSV_PATH} sha256 does not match {JSON_PATH}; frozen data altered")
    for k, v in AXES.items():
        if [float(x) for x in meta["grid"][k]] != list(v):
            raise RuntimeError(f"grid axis {k} in metadata differs from the module definition")
    lines = raw.decode().splitlines()
    if lines[0].split(",") != list(COLUMNS):
        raise RuntimeError("unexpected CSV header")
    shape = tuple(len(AXES[k]) for k in ("doy", "alt_km", "lat_deg", "lon_deg", "lst_h"))
    n_per = int(np.prod(shape))
    if len(lines) - 1 != n_per * len(SCENARIO_ORDER):
        raise RuntimeError("row count does not match the grid")
    data = np.loadtxt(io.StringIO("\n".join(l.split(",", 4)[4] for l in lines[1:])), delimiter=",")
    grid = {}
    for i, s in enumerate(SCENARIO_ORDER):
        block = data[i * n_per:(i + 1) * n_per]
        if lines[1 + i * n_per].split(",", 1)[0] != s or lines[(i + 1) * n_per].split(",", 1)[0] != s:
            raise RuntimeError("scenario blocks out of order")
        grid[s] = block[:, len(IN_COLS) - 4:].reshape(shape + (len(OUT_COLS),))
        if np.any(grid[s] <= 0.0):
            raise RuntimeError("non-positive value in the frozen grid; log interpolation undefined")
    _CACHE.update({"grid": grid, "log_grid": {k: np.log(v) for k, v in grid.items()}, "meta": meta, "shape": shape})
    return _CACHE


def _trig_weights(x: float, period: float, m: int) -> np.ndarray:
    """Weights of trigonometric interpolation on m equispaced nodes k*period/m (m even; Nyquist term as cosine)."""
    th = 2.0 * math.pi * (x - np.arange(m) * period / m) / period
    w = np.ones(m)
    for k in range(1, m // 2):
        w += 2.0 * np.cos(k * th)
    w += np.cos((m // 2) * th)
    return w / m


def _lagrange_weights(x: float, nodes) -> np.ndarray:
    """Local cubic Lagrange weights on the 4 nearest nodes (window clipped at the ends); exact at nodes."""
    nodes = np.asarray(nodes, float)
    n = len(nodes)
    w = np.zeros(n)
    hit = np.nonzero(nodes == x)[0]
    if hit.size:
        w[hit[0]] = 1.0
        return w
    i0 = int(np.clip(np.searchsorted(nodes, x) - 2, 0, n - 4))
    idx = range(i0, i0 + 4)
    for j in idx:
        wj = 1.0
        for k in idx:
            if k != j:
                wj *= (x - nodes[k]) / (nodes[j] - nodes[k])
        w[j] = wj
    return w


def _axis_weights(name: str, x: float) -> np.ndarray:
    if name == "doy":
        # piecewise-linear warp of integer node days onto the equispaced positions k*365/8 (|shift| <= 0.5 d), so
        # every stored doy node is reproduced exactly; doy 1 and 366 (== next year's 1) close the period.
        pos = np.interp(x, list(DOY) + [DOY[0] + DOY_PERIOD], [k * DOY_PERIOD / DOY_M for k in range(DOY_M + 1)])
        return _trig_weights(pos, DOY_PERIOD, DOY_M)
    if name == "lst_h":
        return _trig_weights(x % 24.0, 24.0, len(LST_H))
    if name == "lon_deg":
        return _trig_weights(x % 360.0, 360.0, len(LON_DEG))
    return _lagrange_weights(x, AXES[name])


@dataclass(frozen=True)
class Domain:
    alt_km: tuple = (ALT_KM[0], ALT_KM[-1])
    lat_deg: tuple = (-90.0, 90.0)
    lst_h: tuple = (0.0, 24.0)
    lon_deg: tuple = (-180.0, 360.0)
    doy: tuple = (1.0, DOY_PERIOD)


DOMAIN = Domain()


def _check_domain(alt_km, lat_deg, lst_h, lon_deg, doy, scenario):
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario {scenario!r} is not in {DATASET_ID} ({SCENARIO_ORDER}); no driver interpolation")
    for name, v in (("alt_km", alt_km), ("lat_deg", lat_deg), ("lst_h", lst_h), ("lon_deg", lon_deg), ("doy", doy)):
        if v is None or not isinstance(v, (int, float, np.floating, np.integer)) or not math.isfinite(float(v)):
            raise ValueError(f"{name} must be a finite number, got {v!r}")
        lo, hi = getattr(DOMAIN, name)
        if not lo <= float(v) <= hi:
            raise ValueError(f"{name} = {v} outside the {DATASET_ID} domain [{lo}, {hi}]; refusing to extrapolate")


def state(alt_km: float, lat_deg: float, lst_h: float, lon_deg: float, doy: float, scenario: str) -> dict:
    """Interpolated atmosphere state (see INTERPOLATION; log quantities, separable weights). Out-of-domain or
    unknown-scenario queries raise ValueError (no extrapolation, no fallback). Grid nodes are reproduced exactly."""
    _check_domain(alt_km, lat_deg, lst_h, lon_deg, doy, scenario)
    L = load()
    g = L["log_grid"][scenario]
    r = g
    for name, x in (("doy", doy), ("alt_km", alt_km), ("lat_deg", lat_deg), ("lon_deg", lon_deg), ("lst_h", lst_h)):
        r = np.tensordot(_axis_weights(name, float(x)), r, axes=(0, 0))
    vals_all = np.exp(r)
    acc_T = float(vals_all[-1])
    vals = vals_all[:-1]
    return _state_dict(vals, acc_T, scenario, alt_km, lat_deg, lst_h, lon_deg, doy, how="interpolated")


def _state_dict(vals, T, scenario, alt_km, lat_deg, lst_h, lon_deg, doy, how):
    L = load()
    n = {s: float(vals[1 + i]) for i, s in enumerate(SPECIES)}
    n_tot = sum(n[s] for s in SPECIES)
    x = {s: n[s] / n_tot for s in FRACTION_SPECIES}
    sc = SCENARIOS[scenario]
    iv = L["meta"].get("interpolation_validation", {}).get("by_scenario", {}).get(scenario, {})
    return {"alt_km": float(alt_km), "lat_deg": float(lat_deg), "lst_h": float(lst_h) % 24.0,
            "lon_deg": float(lon_deg) % 360.0, "doy": float(doy), "scenario": scenario, "f107": sc["f107"],
            "f107a": sc["f107a"], "ap": sc["ap"], "rho_kg_m3": float(vals[0]),
            **{f"n_{s}_m3": n[s] for s in SPECIES}, "n_total_m3": n_tot, "T_K": float(T),
            **{f"x_{s}": x[s] for s in FRACTION_SPECIES},
            "source": f"{DATASET_ID} sha256 {L['meta']['sha256']}", "evaluation": how,
            "interp_max_rel_err_rho": iv.get("rho_kg_m3", {}).get("max_abs_rel") if how == "interpolated" else 0.0}


def node_state(i_doy: int, i_alt: int, i_lat: int, i_lon: int, i_lst: int, scenario: str) -> dict:
    """Exact grid-node state (no interpolation)."""
    L = load()
    v = L["grid"][scenario][i_doy, i_alt, i_lat, i_lon, i_lst]
    return _state_dict(v[:-1], v[-1], scenario, ALT_KM[i_alt], LAT_DEG[i_lat], LST_H[i_lst], LON_DEG[i_lon],
                       DOY[i_doy], how="grid_node")


# ---------------------------------------------------------------------------------------------------------------------
# Orbit sampling
# ---------------------------------------------------------------------------------------------------------------------
def mission_env_orbit_assumption(alt_km: float) -> dict:
    """Inclination/LTAN as currently assumed in abep_sim/mission_env.py (not owner-registered)."""
    return {"inclination_deg": sso_inclination_deg(alt_km), "ltan_h": Spacecraft().ltan_h,
            "status": "MODEL_ASSUMPTION",
            "source": "abep_sim/mission_env.py: sso_inclination_deg(alt) (J2 SSO condition, RAAN drift 360/365.25 "
                      "deg/day); Spacecraft.ltan_h = 6.0 ('06:00 LTAN dawn-dusk')"}


def orbit_states(alt_km: float, inclination_deg: float, ltan_h: float, scenario: str, doy: int, ut_start_h: float,
                 n_samples: int) -> list[dict]:
    """Sample one circular revolution at constant geodetic altitude, equally spaced in time (argument of latitude u).

    Geometry (sun-fixed frame, ascending node at local time ``ltan_h``): lat = asin(sin i sin u); hour-angle offset
    from the node dα = atan2(cos i sin u, cos u); LST = ltan + dα/15; UT = ut_start + t/3600; lon = 15 (LST - UT).
    Approximations (recorded per state): geocentric latitude used as geodetic (<= 0.2 deg); constant geodetic altitude
    (the RFP altitude definition) rather than constant radius; node/Sun motion within one revolution neglected
    (< 0.1 deg). Relative speed: circular inertial velocity minus a rigidly co-rotating atmosphere (mission_env
    OMEGA_E), no thermospheric wind. Every state carries the equal-time weight 1/n_samples.
    """
    for name, v in (("alt_km", alt_km), ("inclination_deg", inclination_deg), ("ltan_h", ltan_h), ("doy", doy),
                    ("ut_start_h", ut_start_h), ("n_samples", n_samples)):
        if v is None:
            raise ValueError(f"orbit_states: {name} is required (no hidden defaults)")
    if int(n_samples) != n_samples or n_samples < 4:
        raise ValueError("n_samples must be an integer >= 4")
    if not 0.0 <= inclination_deg <= 180.0:
        raise ValueError("inclination_deg must be in [0, 180]")
    if int(doy) != doy:
        raise ValueError("doy must be integral (MSIS day of year)")
    a = R_EARTH + alt_km * 1e3
    v_orb = math.sqrt(MU_EARTH / a)
    T_orb = 2 * math.pi * math.sqrt(a ** 3 / MU_EARTH)
    inc = math.radians(inclination_deg)
    out = []
    for k in range(int(n_samples)):
        u = 2 * math.pi * k / n_samples
        t = T_orb * k / n_samples
        lat = math.degrees(math.asin(math.sin(inc) * math.sin(u)))
        dalpha = math.degrees(math.atan2(math.cos(inc) * math.sin(u), math.cos(u)))
        lst = (ltan_h + dalpha / 15.0) % 24.0
        ut = (ut_start_h + t / 3600.0) % 24.0
        doy_k = int(doy) + int((ut_start_h + t / 3600.0) // 24.0)
        if doy_k > DOY[-1]:
            raise ValueError("orbit crosses the end of the dataset year; choose doy/ut_start_h inside it")
        lon = (15.0 * (lst - ut)) % 360.0
        r = a * np.array([math.cos(u), math.cos(inc) * math.sin(u), math.sin(inc) * math.sin(u)])
        v = v_orb * np.array([-math.sin(u), math.cos(inc) * math.cos(u), math.sin(inc) * math.cos(u)])
        v_rel = v - np.cross([0.0, 0.0, OMEGA_E], r)
        s = state(alt_km, lat, lst, lon, float(doy_k), scenario)
        s.update({"t_s": t, "u_deg": math.degrees(u), "ut_h": ut, "inclination_deg": inclination_deg, "ltan_h": ltan_h,
                  "v_orb_m_s": v_orb, "v_rel_corot_m_s": float(np.linalg.norm(v_rel)),
                  "flux_corot_kg_m2_s": s["rho_kg_m3"] * float(np.linalg.norm(v_rel)),
                  "weight": 1.0 / n_samples, "state_id": f"orbit:{scenario}:alt{alt_km:g}:doy{doy_k}:k{k}",
                  "geometry": "circular, constant geodetic altitude, sun-fixed node at LTAN, co-rotating atmosphere, "
                              "no winds"})
        out.append(s)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Design states (S9.8 / OD3)
# ---------------------------------------------------------------------------------------------------------------------
EXTREMA_QUANTITIES = ("rho_kg_m3", "x_O", "x_N2", "x_O2", "T_K")


def reachable_lat_max_deg() -> float:
    """Max |latitude| reached by the SSO family over 180-230 km (mission_env.sso_inclination_deg)."""
    return max(180.0 - sso_inclination_deg(a) for a in ALT_KM)


def design_states() -> dict:
    """S9.8 design-state set, derived from the frozen dataset only (no hand-picked F10.7/density points).

    Candidate pool: every grid node with |lat| <= reachable_lat_max_deg() plus the interpolated latitude-boundary states
    at +/- reachable_lat_max_deg() for every other node coordinate (the SSO family reaches 83.6-83.75 deg, between the
    80 and 90 deg nodes). The pool is LTAN-agnostic (all local times), since the inclination/LTAN are not
    owner-registered. For every scenario x altitude node, the set contains: NOMINAL (state of median density), the
    max/min of rho, x_O, x_N2, x_O2, T, and LST_PEAK / LST_TROUGH (median-density state at the local time whose
    lat/lon/season-mean density is highest / lowest). Envelope extrema over all scenarios and altitudes are included.
    The mission nominal scenario is ECSS long-term moderate. Identical states are merged with all their labels.
    """
    L = load()
    lat_r = reachable_lat_max_deg()
    nd, na, nl, no, nt = L["shape"]
    lat_nodes = [i for i, v in enumerate(LAT_DEG) if abs(v) <= lat_r]
    states: dict = {}

    def add(st, label):
        key = (st["scenario"], st["alt_km"], round(st["lat_deg"], 6), st["lst_h"], st["lon_deg"], st["doy"])
        if key not in states:
            st = dict(st)
            st["labels"] = []
            st["state_id"] = "ds:{}:alt{:g}:lat{:+.4f}:lst{:g}:lon{:g}:doy{:g}".format(*key)
            states[key] = st
        if label not in states[key]["labels"]:
            states[key]["labels"].append(label)

    env = {}
    for s in SCENARIO_ORDER:
        for ia, alt in enumerate(ALT_KM):
            pool = []
            for idoy in range(nd):
                for ilo in range(no):
                    for ilt in range(nt):
                        for ila in lat_nodes:
                            pool.append(node_state(idoy, ia, ila, ilo, ilt, s))
                        for sgn in (-1.0, 1.0):
                            pool.append(state(alt, sgn * lat_r, LST_H[ilt], LON_DEG[ilo], DOY[idoy], s))
            rhos = np.array([p["rho_kg_m3"] for p in pool])
            order = np.argsort(rhos, kind="stable")
            add(pool[int(order[len(order) // 2])], f"NOMINAL_MEDIAN_RHO[{s},{alt:g}km]")
            for q in EXTREMA_QUANTITIES:
                vals = np.array([p[q] for p in pool])
                add(pool[int(np.argmax(vals))], f"MAX_{q}[{s},{alt:g}km]")
                add(pool[int(np.argmin(vals))], f"MIN_{q}[{s},{alt:g}km]")
                for kind, fn in (("MAX", np.argmax), ("MIN", np.argmin)):
                    cand = pool[int(fn(vals))]
                    cur = env.get((kind, q))
                    if cur is None or (kind == "MAX" and cand[q] > cur[q]) or (kind == "MIN" and cand[q] < cur[q]):
                        env[(kind, q)] = cand
            lst_means = {}
            for p in pool:
                lst_means.setdefault(p["lst_h"], []).append(math.log(p["rho_kg_m3"]))
            lm = {k: float(np.mean(v)) for k, v in lst_means.items()}
            for tag, lst_sel in (("LST_PEAK", max(lm, key=lm.get)), ("LST_TROUGH", min(lm, key=lm.get))):
                sub = sorted((p for p in pool if p["lst_h"] == lst_sel), key=lambda p: p["rho_kg_m3"])
                add(sub[len(sub) // 2], f"{tag}[{s},{alt:g}km]")
    for (kind, q), st in sorted(env.items()):
        add(st, f"ENVELOPE_{kind}_{q}")
    out = sorted(states.values(), key=lambda d: d["state_id"])
    for st in out:
        st["required"] = True
        st["nominal_mission_scenario"] = st["scenario"] == NOMINAL_SCENARIO
    return {"dataset_id": DATASET_ID, "dataset_sha256": L["meta"]["sha256"], "reachable_lat_max_deg": lat_r,
            "nominal_scenario": NOMINAL_SCENARIO,
            "authority": {"A9.14 S9.8 OD3": {"path": A9_14_JSON, "sha256": A9_14_SHA256}},
            "rule": inspect.cleandoc(design_states.__doc__), "n_states": len(out), "states": out}


def _design_states_text() -> str:
    _CACHE.clear()
    return json.dumps(design_states(), indent=1) + "\n"


def load_design_states() -> dict:
    """The frozen design-state set written at build time (hash-verified against the dataset metadata)."""
    meta = load()["meta"]
    raw = open(DESIGN_PATH, "rb").read()
    if hashlib.sha256(raw).hexdigest() != meta["design_states_file"]["sha256"]:
        raise RuntimeError("design-states file altered (sha256 mismatch)")
    d = json.loads(raw)
    if d["dataset_sha256"] != meta["sha256"]:
        raise RuntimeError("design-states file was produced from a different dataset")
    return d


# ---------------------------------------------------------------------------------------------------------------------
# Statewise quantifier (S9.7 / OD2)
# ---------------------------------------------------------------------------------------------------------------------
def statewise_quantifier(states, margin_fn, requirement_id: str) -> dict:
    """Evaluate ``margin_fn(state) -> float`` (>= 0 passes) or ``-> bool`` at every required state.

    Verdict is PASS only if every state passes; a non-finite or failing evaluation is fail-closed (MODEL_ERROR is
    reported separately from FAIL). The worst state (minimum margin) is always reported. An orbit average is reported
    only when every state carries a time ``weight`` (orbit_states); it is informational and never enters the verdict.
    """
    states = list(states)
    if not states:
        raise ValueError("statewise_quantifier: no states supplied; an empty set cannot satisfy a requirement")
    if not requirement_id:
        raise ValueError("requirement_id is required")
    per, errors = [], []
    for st in states:
        sid = st.get("state_id")
        if sid is None:
            raise ValueError("every state needs a state_id")
        try:
            m = margin_fn(st)
        except Exception as e:  # fail closed, never skip
            errors.append({"state_id": sid, "error": f"{type(e).__name__}: {e}"})
            per.append({"state_id": sid, "margin": None, "pass": False, "status": "MODEL_ERROR"})
            continue
        if isinstance(m, (bool, np.bool_)):
            val, ok = (0.0 if m else -1.0), bool(m)
        else:
            val = float(m)
            ok = math.isfinite(val) and val >= 0.0
            if not math.isfinite(val):
                errors.append({"state_id": sid, "error": "non-finite margin"})
                per.append({"state_id": sid, "margin": None, "pass": False, "status": "MODEL_ERROR"})
                continue
        per.append({"state_id": sid, "margin": val, "pass": ok, "status": "PASS" if ok else "FAIL"})
    finite = [p for p in per if p["margin"] is not None]
    worst = min(finite, key=lambda p: p["margin"]) if finite else None
    n_fail = sum(1 for p in per if p["status"] == "FAIL")
    verdict = "MODEL_ERROR" if errors else ("PASS" if n_fail == 0 else "FAIL")
    weights = [st.get("weight") for st in states]
    orbit_avg = None
    if not errors and all(w is not None for w in weights):
        W = sum(weights)
        orbit_avg = sum(w * p["margin"] for w, p in zip(weights, per)) / W
    return {"requirement_id": requirement_id, "verdict": verdict, "n_states": len(per), "n_fail": n_fail,
            "n_model_error": len(errors), "worst_state": worst, "orbit_average_margin": orbit_avg,
            "orbit_average_note": ("informational only; verdict is statewise (A9.14 S9.7 OD2, A9.13 S6.15)"
                                   if orbit_avg is not None else "not reported: states carry no time weights"),
            "average_hides_violation": bool(orbit_avg is not None and orbit_avg >= 0.0 and verdict != "PASS"),
            "per_state": per, "errors": errors,
            "authority": {"A9.14 S9.7 OD2": {"path": A9_14_JSON, "sha256": A9_14_SHA256}}}


# ---------------------------------------------------------------------------------------------------------------------
# Build-time interpolation validation + check
# ---------------------------------------------------------------------------------------------------------------------
INTERP_SEED = 20261001
INTERP_N = 1500


def _interpolation_validation() -> dict:
    rng = np.random.default_rng(INTERP_SEED)
    res = {"seed": INTERP_SEED, "n_points_per_scenario": INTERP_N,
           "method": "random points uniform in alt 180-230, lat -90..90, LST 0-24, lon 0-360, integer doy 1-365; "
                     "accessor interpolation vs direct pymsis NRLMSIS 2.1 at the same inputs", "by_scenario": {}}
    for s in SCENARIO_ORDER:
        alt = rng.uniform(180, 230, INTERP_N); lat = rng.uniform(-90, 90, INTERP_N)
        lst = rng.uniform(0, 24, INTERP_N); lon = rng.uniform(0, 360, INTERP_N)
        doy = rng.integers(1, 366, INTERP_N).astype(float)
        direct = msis_points(s, doy, alt, lat, lon, lst)
        interp = np.array([[st[c] for c in OUT_COLS] for st in
                           (state(alt[i], lat[i], lst[i], lon[i], doy[i], s) for i in range(INTERP_N))])
        rel = np.abs(interp / np.maximum(direct, 1e-300) - 1.0)
        res["by_scenario"][s] = {c: {"max_abs_rel": float(np.max(rel[:, j])), "p95_abs_rel": float(np.percentile(rel[:, j], 95))}
                                 for j, c in enumerate(OUT_COLS)}
    return res


CHECK_STRIDE = 97  # prime stride through the canonical row order -> deterministic subset touching every axis


def _check_subset_indices(n_rows: int):
    return list(range(0, n_rows, CHECK_STRIDE))


def _check_subset_record() -> dict:
    lines = open(CSV_PATH).read().splitlines()[1:]
    idx = _check_subset_indices(len(lines))
    sub = "\n".join(lines[i] for i in idx) + "\n"
    return {"stride": CHECK_STRIDE, "n_rows": len(idx), "sha256": hashlib.sha256(sub.encode()).hexdigest()}


def check() -> dict:
    """Verify file hash + metadata, then recompute the deterministic subset with pymsis and compare bytes/hashes."""
    import pymsis
    meta = json.load(open(JSON_PATH))
    raw = open(CSV_PATH, "rb").read()
    problems = []
    sha = hashlib.sha256(raw).hexdigest()
    if sha != meta["sha256"]:
        problems.append(f"csv sha256 {sha} != metadata {meta['sha256']}")
    if pymsis.__version__ != meta["producer"]["pymsis_version"]:
        problems.append(f"pymsis {pymsis.__version__} != recorded {meta['producer']['pymsis_version']}")
    lines = raw.decode().splitlines()
    if lines[0].split(",") != list(COLUMNS):
        problems.append("header mismatch")
    body = lines[1:]
    if len(body) != meta["row_count"]:
        problems.append("row count mismatch")
    idx = _check_subset_indices(len(body))
    stored = [body[i] for i in idx]
    rec = meta["check_subset"]
    if hashlib.sha256(("\n".join(stored) + "\n").encode()).hexdigest() != rec["sha256"]:
        problems.append("stored check-subset hash mismatch")
    regen = []
    for line in stored:
        f = line.split(",")
        s = f[0]
        doy, alt, lat, lon, lst = (float(x) for x in f[4:9])
        out = msis_points(s, [doy], [alt], [lat], [lon], [lst])
        regen += _rows_text(s, np.array([doy]), np.array([alt]), np.array([lat]), np.array([lon]), np.array([lst]), out)
    n_diff = sum(1 for a, b in zip(stored, regen) if a != b)
    if n_diff:
        problems.append(f"{n_diff} of {len(stored)} recomputed subset rows differ from the frozen file")
    regen_sha = hashlib.sha256(("\n".join(regen) + "\n").encode()).hexdigest()
    ds_raw = open(DESIGN_PATH, "rb").read() if os.path.exists(DESIGN_PATH) else b""
    if hashlib.sha256(ds_raw).hexdigest() != meta.get("design_states_file", {}).get("sha256"):
        problems.append("design-states file hash differs from the metadata")
    elif not problems:
        frozen = json.loads(ds_raw)
        fresh = design_states()
        if [x["state_id"] for x in frozen["states"]] != [x["state_id"] for x in fresh["states"]] or \
                [x["labels"] for x in frozen["states"]] != [x["labels"] for x in fresh["states"]]:
            problems.append("design states (ids/labels) do not reproduce from the frozen dataset")
        else:
            for a, b in zip(frozen["states"], fresh["states"]):
                for k in ("rho_kg_m3", "T_K", "x_O", "x_N2", "x_O2"):
                    if not math.isclose(a[k], b[k], rel_tol=1e-9):
                        problems.append(f"design state {a['state_id']} {k} does not reproduce")
                        break
    if regen_sha != rec["sha256"]:
        problems.append("recomputed subset hash differs from the recorded subset hash")
    expected = _metadata(meta["sha256"], meta["row_count"])
    for k in ("dataset_id", "columns", "grid", "drivers", "authority", "build_command", "interpolation", "domain"):
        if json.loads(json.dumps(expected[k])) != meta[k]:
            problems.append(f"metadata field {k} differs from the module definition")
    return {"ok": not problems, "problems": problems, "subset_rows": len(stored), "subset_sha256": regen_sha,
            "csv_sha256": sha}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["build"]:
        meta = build()
        print(f"{CSV_PATH} rows={meta['row_count']} bytes={meta['bytes']} sha256={meta['sha256']}")
        return 0
    if argv[:1] in (["check"], ["--check"]):
        r = check()
        print(("OK " if r["ok"] else "FAIL ") + json.dumps({k: v for k, v in r.items() if k != "ok"}))
        return 0 if r["ok"] else 1
    print("usage: python -m abep_sim.atmosphere_orbit build | check", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
