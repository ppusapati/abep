"""Orbit-resolved atmosphere v2 with HWM14 neutral winds (``atmosphere_msis21_hwm14_orbit_v2``).

Status: **DESIGN_ENVELOPE_PARAMETRIC** -- a design-envelope / parametric dataset, not a mission trajectory.

Authority (immutable owner record; cite path + json sha256 + decision key):

* A9.17 WINDS -- ``docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json``
  (sha256 9fd77c95c2f3142bb3e2faf68145e1225a29b307d22f86bf93a8cd562914c3ad; verbatim
  ``OD_2026_10_01_A9_17_DATA_ARTIFACT_OWNER_DECISIONS.md`` sha256 540212c0...ba13), answer
  ``AUTHORIZE_HWM14_ATMOSPHERE_V2_KEEP_V1_IMMUTABLE``: "The new atmosphere dataset should therefore carry both the
  Earth-corotating atmosphere result and the HWM14-corrected neutral-wind result, with HWM14 version, Ap input, date/time,
  coordinates and provenance recorded. Do not overwrite v1. Until the actual spacecraft orbit is registered, v2 remains a
  design-envelope/parametric dataset rather than a mission-specific frozen trajectory."
* A9.17 ORBIT (same record), answer ``ORBIT_INCLINATION_LTAN_TBD_FROM_OFFICIAL_MISSION_ICD``: inclination and LTAN are
  caller inputs of the orbit sampler, never defaults (the mission_env 96.3 deg / dawn-dusk orbit is CODE_DEFAULT /
  PARAMETRIC).
* A9.17 DATA_SIZE (same record): one canonical deterministic-gzip copy, builder + manifest + sha256 in the repository,
  excluded from the installed wheel (pyproject exclude-package-data). The two .csv.gz tables are not in the sdist either;
  the small manifest JSON is carried by the sdist unless MANIFEST.in excludes it (see the manifest's ``distribution`` and
  ``distribution_snapshot_at_build``; finding HWM-2).

Composition. v2 = the frozen NRLMSIS 2.1 state of ``atmosphere_msis21_orbit_v1`` (read through
``abep_sim.atmosphere_orbit``, hash-verified, unchanged) + a frozen HWM14 wind table on exactly the same grid and the same
four ECSS scenarios (the grid is imported from ``abep_sim.atmosphere_orbit``, not copied). The wind file stores, per
node, the HWM14 meridional and zonal wind (total, i.e. quiet + DWM07 disturbance at the scenario ap) and the quiet-time
part (ap(2) < 0), with the exact HWM14 inputs (iyd, UT seconds, geodetic altitude / latitude / longitude, ap(2)).

HWM14 is not shipped and not needed at run time: the accessor works from the frozen file alone. ``build`` and the
HWM14 re-run in ``check`` need the NRL HWM14 package (``fetch-hwm14``; directory given by ``ABEP_HWM14_DIR``) and
gfortran; without them ``check`` verifies the frozen files and reports the re-run as SKIPPED with the reason.

Usage (repository checkout only)::

    python -m abep_sim.atmosphere_orbit_v2 fetch-hwm14 DIR   # download the NRL package, verify every sha256
    ABEP_HWM14_DIR=DIR python -m abep_sim.atmosphere_orbit_v2 build   # rule 1: intentional rebuild only
    ABEP_HWM14_DIR=DIR python -m abep_sim.atmosphere_orbit_v2 check   # without HWM14: hash checks, re-run SKIPPED

Nothing in the existing simulator imports this module.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zlib

import numpy as np

from . import atmosphere_orbit as v1
from .constants import MU_EARTH, R_EARTH
from .mission_env import OMEGA_E

DATASET_ID = "atmosphere_msis21_hwm14_orbit_v2"
DATASET_STATUS = "DESIGN_ENVELOPE_PARAMETRIC"
DATA_DIR = v1.DATA_DIR
GZ_PATH = os.path.join(DATA_DIR, DATASET_ID + ".csv.gz")
# Fine disturbance-wind (DWM07) table, see DIST_GRID_TRADE: same discipline (deterministic gzip, sha256 in the manifest).
DIST_GZ_PATH = os.path.join(DATA_DIR, DATASET_ID + ".disturbance.csv.gz")
JSON_PATH = os.path.join(DATA_DIR, DATASET_ID + ".json")
REPO_DATA_PATH = "abep_sim/data/" + DATASET_ID + ".csv.gz"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYPROJECT_EXCLUDE_GLOB = "data/" + DATASET_ID + "*"
# Finding HWM-2: the sdist statement says what MANIFEST.in does, not what it should do. MANIFEST.in is outside the A9.17
# WINDS lane; the actual state at build time is recorded in distribution_snapshot_at_build.
SDIST_STATEMENT = ("the two .csv.gz tables are not carried (MANIFEST.in recursive-include abep_sim/data matches *.json "
                   "*.csv *.dat *.md only). The manifest JSON is matched by *.json and is carried unless MANIFEST.in "
                   "excludes it; at this build MANIFEST.in had no exclude line for this dataset, so the sdist carried "
                   "the manifest JSON (distribution_snapshot_at_build; the exclude line is pending in a lane allowed "
                   "to edit MANIFEST.in)")
BUILD_COMMAND = "ABEP_HWM14_DIR=<dir> python -m abep_sim.atmosphere_orbit_v2 build"
CHECK_COMMAND = "python -m abep_sim.atmosphere_orbit_v2 check"
FETCH_COMMAND = "python -m abep_sim.atmosphere_orbit_v2 fetch-hwm14 <dir>"
HWM_DIR_ENV = "ABEP_HWM14_DIR"

A9_17_JSON = v1.A9_17_JSON
A9_17_SHA256 = v1.A9_17_SHA256
A9_17_MD = v1.A9_17_MD
A9_17_MD_SHA256 = v1.A9_17_MD_SHA256
A9_17_WINDS_QUOTE = ("The new atmosphere dataset should therefore carry both the Earth-corotating atmosphere result and "
                     "the HWM14-corrected neutral-wind result, with HWM14 version, Ap input, date/time, coordinates and "
                     "provenance recorded. Do not overwrite v1. Until the actual spacecraft orbit is registered, v2 "
                     "remains a design-envelope/parametric dataset rather than a mission-specific frozen trajectory.")
EVIDENCE_DIR = "docs/evidence/hwm14"
SOURCE_REGISTER = EVIDENCE_DIR + "/hwm14_source_register_v1.json"

# Thermodynamic state: the frozen v1 dataset, pinned by its uncompressed-CSV sha256 (dataset identity).
V1_DATASET_ID = v1.DATASET_ID
V1_CSV_SHA256 = "c0ce282e99695be8cae0834270c5b9ff7853033255665abda7ec18c307566164"

# ---------------------------------------------------------------------------------------------------------------------
# HWM14 source (NRL public repository; retrieved 2026-10-01). Not redistributed: only identities are recorded here.
# ---------------------------------------------------------------------------------------------------------------------
HWM14_VERSION = "HWM14.123114"          # README.txt: "Version HWM14.123114", release 31 Dec 2014
NRL_BASE_URL = "https://map.nrl.navy.mil/map/pub/nrl/HWM/HWM14/"
HWM14_TGZ = {"file": "HWM14_ess224-sup-0002-supinfo.tgz", "url": NRL_BASE_URL + "HWM14_ess224-sup-0002-supinfo.tgz",
             "sha256": "4de451beeadef7b3ec3aa5b91129ea98866b9e7156cecf4be1343c33a6f57978", "bytes": 216852}
# Files of the extracted package (tar member HWM14/<name>); sha256 of the bytes as extracted from the .tgz.
HWM14_FILES = {
    "README.txt": "14b6e5e48d346ff034e2f6bfd7f26dc550945c9b90ad9661c7710e721ac89b15",
    "hwm14.f90": "6bb4e031917b44c93201f0289ada8bf6f6d81eb3f292c89151c6937e2e7bf76e",
    "hwm123114.bin": "6e445f8337c7efc815b7ff7f9f967d8a9a16b469d93df9c46e54930553beb906",
    "dwm07b104i.dat": "f2b8eff002d55b0f6d49d202c73b7a9cb6685f2c6bb57f1291a2adc7aa07cf4f",
    "gd2qd.dat": "6bb1f2384e30b409240ee92c32726ed2a3d73eb550c05e0969d1178032319804",
    "checkhwm14.f90": "6a58eaafb065ffa9d34cfba409f865531b8cbe7c1a0ee274ca6c21fcbeb26091",
    "makefile": "de8f0ddcfb1a24084342de89232c4407f6cf0436397cb7cd0561195753ab76cf",
    "Check/gfortran.txt": "2b1d4f4f103be3531393c48bf32d034548babfb6c080549884cad9fd3a2c8652",
    "Check/ifort.nopt.txt": "32f6e5b5a8b33ac8dffae73767296c36ae10105b613f43d01a6da27f7eb80bb5",
    "Check/ifort.opt.txt": "e294e625690b22f0c988afc13a8556a583de95dc450d75ed3b0474001b4d0757",
}
HWM14_REFERENCE = ("Drob, D. P., et al. (2015), An update to the Horizontal Wind Model (HWM): The quiet time thermosphere, "
                   "Earth and Space Science 2, 301-319, doi:10.1002/2014EA000089 (Software S1 = the .tgz above); DWM07: "
                   "Emmert, J. T., et al. (2008), J. Geophys. Res. 113, doi:10.1029/2008JA013541")

# Compilation: gfortran with no flags (= gfortran default, -O0), as NRL's reference Check/gfortran.txt ("gfortran
# (v4.8.1) default flags"). -J only places the .mod files in the build directory (no effect on code generation).
FC = "gfortran"
FC_FLAGS: tuple = ()
GFORTRAN_VERSION_BUILT = "GNU Fortran (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0"

# Batch driver (project code, not NRL code): reads n, then n lines "iyd sec alt glat glon ap2"; for each point calls
# hwm14 twice, quiet (ap = [-1, -1]) and total (ap = [0, ap2]); writes the four winds as float32 in es16.8 (round-trip
# exact for real(4)). n = -1 followed by one ap value prints the DWM07 ap->Kp conversion (ap2kp) instead.
DRIVER_F90 = """program hwm14_points
    implicit none
    integer(4) :: n, i, iyd
    real(4) :: sec, alt, glat, glon, ap(2), apq(2), wq(2), wt(2), apin
    real(4), external :: ap2kp
    read(*,*) n
    if (n .lt. 0) then
        read(*,*) apin
        write(*,'(es16.8e3)') ap2kp(apin)
        stop
    end if
    apq = (/ -1.0, -1.0 /)
    do i = 1, n
        read(*,*) iyd, sec, alt, glat, glon, apin
        ap = (/ 0.0, apin /)
        call hwm14(iyd, sec, alt, glat, glon, 0.0, 0.0, 0.0, apq, wq)
        call hwm14(iyd, sec, alt, glat, glon, 0.0, 0.0, 0.0, ap, wt)
        write(*,'(4(1x,es16.8e3))') wq(1), wq(2), wt(1), wt(2)
    end do
end program hwm14_points
"""
DRIVER_SHA256 = hashlib.sha256(DRIVER_F90.encode()).hexdigest()

# HWM14 inputs. The HWM14 argument list is the HWM93 one: iyd = YYDDD (only mod(iyd, 1000) is used), sec = UT s,
# alt km, glat / glon geodetic deg, stl / f107a / f107 not used (passed 0.0), ap(1) not used (0.0), ap(2) = current
# 3-hour ap (README.txt "TO GET TOTAL WINDS"); a negative ap(2) returns the quiet-time winds only.
AP_INPUT = {
    "hwm14_argument": "ap(2) (current 3-hour ap); ap(1) = 0.0 (not used by HWM14)",
    "value_passed": "the scenario's ECSS Table 6-3 Ap (same value as the NRLMSIS daily Ap of v1), held constant as the "
                    "3-hour ap: ECSS_LT_LOW 0, ECSS_LT_MODERATE 15, ECSS_LT_HIGH 45, ECSS_ST_HIGH 240",
    "rationale": "v1 runs NRLMSIS with a constant ap history ([Ap]*7, daily-Ap mode); the same constant value is the only "
                 "ap consistent with it. ECSS Table 6-3 gives no separate 3-hour ap for these scenarios",
    "status": "assumed (model input convention; not a forecast). ap = 0 (ECSS_LT_LOW) still evaluates DWM07 at Kp = 0, "
              "which is not zero; the quiet-only part (ap(2) = -1) is stored separately",
    "quiet_columns": "ap(2) = -1.0 (HWM14 quiet-time winds only; README: 'Call HWM14 with a negative value for AP(2)')",
    "kp_from_ap": "DWM07 converts ap(2) to Kp internally (ap2kp); the values are recorded per scenario at build time",
    "ignored_by_hwm14": "F10.7 and F10.7avg (README: 'The F107 and F107A arguments are ignored in this version'; 'The "
                        "model currently contains no solar activity dependence'). The four scenarios therefore differ in "
                        "wind only through ap",
}

FLOAT_FMT_WIND = "%.4f"      # m/s; 0.1 mm/s, below the ~1 mm/s cross-compiler spread NRL documents (README.txt)
KEY_COLS = ("scenario", "ap_hwm", "iyd", "doy", "alt_km", "lat_deg", "lon_deg", "lst_h", "ut_h", "ut_s")
WIND_COLS = ("u_mer_m_s", "u_zon_m_s", "u_mer_quiet_m_s", "u_zon_quiet_m_s")
COLUMNS = KEY_COLS + WIND_COLS
UNITS = {"scenario": "ECSS scenario id (v1 SCENARIOS)", "ap_hwm": "ap(2) passed to HWM14 (3-hour ap)",
         "iyd": "YYDDD passed to HWM14 (YY = v1 EPOCH_YEAR mod 100)", "doy": "day of year", "alt_km": "km, geodetic",
         "lat_deg": "deg, geodetic", "lon_deg": "deg east, geodetic", "lst_h": "h, local solar time = UT + lon/15",
         "ut_h": "h, UT (v1 definition)", "ut_s": "s, UT passed to HWM14 as sec (= ut_h * 3600)",
         "u_mer_m_s": "m/s, HWM14 total meridional wind (+ northward), quiet + DWM07 disturbance at ap_hwm",
         "u_zon_m_s": "m/s, HWM14 total zonal wind (+ eastward), quiet + DWM07 disturbance at ap_hwm",
         "u_mer_quiet_m_s": "m/s, HWM14 quiet-time meridional wind (ap(2) = -1)",
         "u_zon_quiet_m_s": "m/s, HWM14 quiet-time zonal wind (ap(2) = -1)"}

# Disturbance-wind table. DWM07 depends on magnetic latitude / magnetic local time (and day of year through the
# subsolar point), so it is not band-limited on the v1 geographic grid: with the v1 grid alone the measured joint error
# of the total wind was up to 143 m/s (ECSS_ST_HIGH; 5.6 m/s ECSS_LT_LOW), while the quiet part interpolates within
# ~5 m/s. The disturbance part is therefore interpolated from its own finer table (measured, recorded below).
DIST_LAT_DEG = tuple(float(x) for x in range(-90, 91, 5))
DIST_LON_DEG = tuple(float(x) for x in range(0, 360, 15))
DIST_LST_H = tuple(float(x) for x in range(0, 24))
DIST_DOY = v1.DOY
DIST_ALT_KM = 230.0          # evaluation altitude; DWM07 is height-constant over 180-230 km (measured at build time)
DIST_AXES = {"doy": DIST_DOY, "lat_deg": DIST_LAT_DEG, "lon_deg": DIST_LON_DEG, "lst_h": DIST_LST_H}
DIST_ALT_TOL_M_S = 1e-2      # refuse the single-altitude table if DWM07 varies more than this over 180-230 km
DIST_KEY_COLS = ("scenario", "ap_hwm", "iyd", "doy", "alt_km", "lat_deg", "lon_deg", "lst_h", "ut_s")
DIST_WIND_COLS = ("u_mer_dist_m_s", "u_zon_dist_m_s")
DIST_COLUMNS = DIST_KEY_COLS + DIST_WIND_COLS
DIST_GRID_TRADE = (
    "Pre-build study (2026-10-01, this HWM14 build, ECSS_ST_HIGH = the largest disturbance winds, doy 172, 1500 random "
    "lat/lon/LST points, |error vector| of the interpolated DWM07 wind vs direct): grid lat 5 deg x lon 15 deg x LST 1 h "
    "with local cubic interpolation max 13.6 / p95 4.1 m/s (linear 44.8 / 18.8); 2.5 x 15 x 1 cubic 10.0 / 1.5; "
    "2.5 x 10 x 0.5 cubic 1.9 / 0.4 (4M rows, rejected for size); 1 x 5 x 0.5 cubic 0.5 / 0.1. One-axis studies on the "
    "v1 grid: DWM07 varies by <= 5.5e-4 m/s between 180 and 230 km (height-constant), and the 8 v1 doy nodes with "
    "trigonometric interpolation reproduce its seasonal (subsolar-point) dependence within 0.4 m/s, while doy 1 vs 172 "
    "differ by up to 118 m/s. Chosen: lat 5 deg (37) x lon 15 deg (24) x LST 1 h (24) x the 8 v1 doy nodes x 4 scenarios "
    "= 681,984 rows at one altitude (DIST_ALT_KM). The joint error is measured at build time (interpolation_validation).")
DIST_INTERPOLATION = {
    "quantity": "DWM07 disturbance wind components = HWM14 total - quiet (linear values)",
    "alt_km": "none: evaluated at DIST_ALT_KM; height-constancy over the v1 altitude nodes measured at build time",
    "lat_deg": "local cubic Lagrange (4 nearest of 37 nodes, 5 deg step, clipped at the ends)",
    "lon_deg": "periodic local cubic Lagrange (24 nodes, 15 deg step)",
    "lst_h": "periodic local cubic Lagrange (24 nodes, 1 h step)",
    "doy": v1.INTERPOLATION["doy"],
    "scenario": "none (discrete)"}

INTERPOLATION = {
    "quantity": "wind components (linear values, not logs; winds change sign). Total wind = quiet part interpolated "
                "on the v1 grid (node table) + DWM07 disturbance part interpolated on the disturbance table",
    "quiet_part": {**{k: v for k, v in v1.INTERPOLATION.items() if k not in ("quantity",)},
                   "weights": "abep_sim.atmosphere_orbit._axis_weights (identical separable weights to v1)"},
    "disturbance_part": DIST_INTERPOLATION,
    "node_table_total_columns": "stored HWM14 total winds at the v1 nodes (provenance + node check); the accessor's "
                                "composed total reproduces them within the recorded node_reproduction tolerance",
    "thermodynamic_state": "abep_sim.atmosphere_orbit.state (v1 accessor, unchanged)"}

LABELS = {"dataset_status": DATASET_STATUS, "mission_trajectory": False, "requirement_input": False,
          "orbit_inputs": "inclination / LTAN are caller-supplied PARAMETRIC inputs (no defaults)",
          "real_orbit": "TBD from DRDO / spacecraft ICD / PDR mission definition; then a new dataset version"}

# Verbatim phrases of HWM14 README.txt lines 155-157 (HWM14_FILES["README.txt"]); checked against the file when HWM14 is
# available (tests/test_atmosphere_orbit_v2.py). Finding HWM-3: the earlier paraphrase misquoted them.
DWM07_README_QUOTE = ("represents average disturbance winds in the upper thermosphere (above 225 km)",
                      "The disturbance winds are assumed to be constant with height, with a smooth artificial cutoff "
                      "below 125 km")

NOT_PROVIDED = {
    "vertical_wind": "HWM14 is a horizontal wind model; the vertical neutral wind is taken as 0 in the relative flow",
    "solar_activity_dependence_of_winds": "HWM14 has none (F10.7 ignored); quiet-time winds identical in all scenarios",
    "hwm14_model_uncertainty": "not quantified here (empirical climatology; storm-time and day-to-day variability are "
                               "not represented); only the grid interpolation error is measured",
    "disturbance_wind_height_dependence": (
        "HWM14 README.txt (MODEL LIMITATIONS, sha256 14b6e5e4...9b15): the DWM07 disturbed part '" + DWM07_README_QUOTE[0]
        + "'; '" + DWM07_README_QUOTE[1] + "'. DWM07 is therefore height-constant by construction (the README describes no "
        "transition at 180-230 km; measured variation over 180-230 km: disturbance_file.altitude_independence_check). "
        "Per the README it represents average disturbance winds above 225 km; applying it unchanged at 180-225 km is an "
        "applicability extrapolation of the source model (representativeness there not quantified; verify)"),
    "design_states": "no wind-specific design-state set: the relative-flow extremes depend on the (TBD) orbit; use "
                     "orbit_states() over the caller's parametric orbit range",
}


def _authority() -> dict:
    return {"A9.17 WINDS": {"path": A9_17_JSON, "sha256": A9_17_SHA256, "decision_key": "WINDS",
                            "answer": "AUTHORIZE_HWM14_ATMOSPHERE_V2_KEEP_V1_IMMUTABLE",
                            "verbatim": {"path": A9_17_MD, "sha256": A9_17_MD_SHA256, "quote": A9_17_WINDS_QUOTE}},
            "A9.17 ORBIT": {"path": A9_17_JSON, "sha256": A9_17_SHA256, "decision_key": "ORBIT",
                            "answer": "ORBIT_INCLINATION_LTAN_TBD_FROM_OFFICIAL_MISSION_ICD"},
            "A9.17 DATA_SIZE": {"path": A9_17_JSON, "sha256": A9_17_SHA256, "decision_key": "DATA_SIZE",
                                "answer": "KEEP_DATA_ARTIFACT_EXCLUDE_FROM_INSTALL_WHERE_POSSIBLE"},
            "v1 open item": {"id": "ATM-OI-01", "dataset": V1_DATASET_ID,
                             "relation": "resolved for v2 users by this dataset; v1 and its open item are unchanged"},
            "CLAUDE.md rule 1": "versioned new dataset; atmosphere_msis21_orbit_v1.* untouched"}


# ---------------------------------------------------------------------------------------------------------------------
# HWM14 package location, verification, compilation
# ---------------------------------------------------------------------------------------------------------------------
class HWM14Unavailable(RuntimeError):
    """HWM14 (NRL package or gfortran) is not available; the reason is in the message."""


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hwm14_dir(path: str | None = None) -> str:
    """The verified HWM14 package directory (``path`` or $ABEP_HWM14_DIR). Every file of HWM14_FILES must be present
    with its recorded sha256; otherwise HWM14Unavailable (no partial or unverified HWM14 is ever used)."""
    path = path or os.environ.get(HWM_DIR_ENV)
    if not path:
        raise HWM14Unavailable(f"${HWM_DIR_ENV} is not set (HWM14 package directory; obtain it with `{FETCH_COMMAND}`)")
    if not os.path.isdir(path):
        raise HWM14Unavailable(f"${HWM_DIR_ENV} = {path!r} is not a directory")
    bad = []
    for name, sha in HWM14_FILES.items():
        p = os.path.join(path, name)
        if not os.path.exists(p):
            bad.append(f"{name}: missing")
        elif _sha256_file(p) != sha:
            bad.append(f"{name}: sha256 differs from the NRL release")
    if bad:
        raise HWM14Unavailable(f"HWM14 package at {path!r} does not match {HWM14_VERSION}: " + "; ".join(bad))
    return os.path.abspath(path)


def fetch_hwm14(dest: str) -> str:
    """Download the NRL HWM14 package (public repository, HWM14_TGZ), verify the .tgz sha256, extract the regular files
    of HWM14/ (tar 'data' filter; macOS '._' resource forks skipped) into ``dest`` and verify every file sha256."""
    import urllib.request
    os.makedirs(dest, exist_ok=True)
    with urllib.request.urlopen(HWM14_TGZ["url"], timeout=120) as r:
        blob = r.read()
    if hashlib.sha256(blob).hexdigest() != HWM14_TGZ["sha256"]:
        raise RuntimeError("downloaded HWM14 .tgz sha256 differs from the recorded NRL release; not extracted")
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        for m in tf.getmembers():
            name = m.name[2:] if m.name.startswith("./") else m.name
            if not m.isfile() or not name.startswith("HWM14/"):
                continue
            rel = name[len("HWM14/"):]
            if os.path.basename(rel).startswith("._") or rel not in HWM14_FILES:
                continue
            out = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as f:
                f.write(tf.extractfile(m).read())
    return hwm14_dir(dest)


def gfortran_version() -> str:
    exe = shutil.which(FC)
    if exe is None:
        raise HWM14Unavailable(f"{FC} not found on PATH (needed to compile HWM14)")
    return subprocess.run([exe, "--version"], capture_output=True, text=True, check=True).stdout.splitlines()[0].strip()


def _compile(src_dir: str, work: str, sources, exe_name: str) -> list:
    cmd = [FC, *FC_FLAGS, *sources, "-J", work, "-o", os.path.join(work, exe_name)]
    r = subprocess.run(cmd, cwd=src_dir, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"HWM14 compilation failed: {' '.join(cmd)}\n{r.stderr}")
    return [FC, *FC_FLAGS, *sources, "-o", exe_name]


def _numbers(text: str) -> list:
    out = []
    for tok in text.replace(",", " ").split():
        try:
            out.append(float(tok))
        except ValueError:
            pass
    return out


def nrl_reference_check(src_dir: str, work: str) -> dict:
    """Compile NRL's own test driver checkhwm14.f90 and compare its output with the NRL reference outputs shipped in the
    package (Check/gfortran.txt is the reference for gfortran default flags; ifort files reported for information)."""
    cmd = _compile(src_dir, work, ["checkhwm14.f90", "hwm14.f90"], "checkhwm14.exe")
    r = subprocess.run([os.path.join(work, "checkhwm14.exe")], cwd=src_dir, capture_output=True, text=True,
                       env=dict(os.environ, HWMPATH=src_dir))
    if r.returncode != 0:
        raise RuntimeError(f"checkhwm14 failed: {r.stderr}")
    out = r.stdout.replace("\r", "")
    res = {"driver": "checkhwm14.f90 (NRL test driver)", "compile": cmd, "output_sha256": hashlib.sha256(
        out.encode()).hexdigest(), "comparisons": {}}
    mine = _numbers(out)
    for ref in ("Check/gfortran.txt", "Check/ifort.nopt.txt", "Check/ifort.opt.txt"):
        txt = open(os.path.join(src_dir, ref), encoding="utf-8").read().replace("\r", "")
        a, b = out.splitlines(), txt.splitlines()
        nums = _numbers(txt)
        same_n = len(nums) == len(mine)
        res["comparisons"][ref] = {
            "identical_text": a == b, "n_differing_lines": sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b)),
            "n_numbers": len(nums), "max_abs_numeric_diff": (float(f"{max(abs(x - y) for x, y in zip(mine, nums)):.3e}")
                                                              if same_n else None)}
    res["passed"] = res["comparisons"]["Check/gfortran.txt"]["identical_text"]
    res["criterion"] = ("output text identical to NRL Check/gfortran.txt (gfortran default flags); README.txt: compilers "
                        "differ by ~1e-4 m/s, ifort -O0 and gfortran identical")
    return res


class HWM14Runner:
    """Compiled HWM14 (verified package + project batch driver) in a private temporary directory."""

    def __init__(self, path: str | None = None):
        self.src = hwm14_dir(path)
        self.compiler = gfortran_version()
        self._tmp = tempfile.TemporaryDirectory(prefix="abep_hwm14_")
        self.work = self._tmp.name
        self.nrl_check = nrl_reference_check(self.src, self.work)
        if not self.nrl_check["passed"]:
            raise RuntimeError("HWM14 build does not reproduce NRL Check/gfortran.txt; refusing to use it: "
                               + json.dumps(self.nrl_check["comparisons"]))
        drv = os.path.join(self.work, "hwm14_points.f90")
        with open(drv, "w") as f:
            f.write(DRIVER_F90)
        self.driver_compile = _compile(self.src, self.work, ["hwm14.f90", drv], "hwm14_points.exe")
        self.driver_compile = [os.path.basename(x) if x == drv else x for x in self.driver_compile]
        self.exe = os.path.join(self.work, "hwm14_points.exe")

    def close(self):
        self._tmp.cleanup()

    def _run(self, text: str) -> str:
        r = subprocess.run([self.exe], input=text, capture_output=True, text=True, cwd=self.work,
                           env=dict(os.environ, HWMPATH=self.src))
        if r.returncode != 0:
            raise RuntimeError(f"HWM14 driver failed: {r.stderr}")
        return r.stdout

    def kp(self, ap: float) -> float:
        return float(self._run(f"-1\n{ap!r}\n").split()[0])

    def winds(self, iyd, sec, alt, glat, glon, ap2) -> np.ndarray:
        """(n, 4) array: quiet mer, quiet zon, total mer, total zon (m/s, float32 values from HWM14)."""
        n = len(iyd)
        lines = [str(n)] + [f"{int(a)} {float(b)!r} {float(c)!r} {float(d)!r} {float(e)!r} {float(g)!r}"
                            for a, b, c, d, e, g in zip(iyd, sec, alt, glat, glon, ap2)]
        out = np.loadtxt(io.StringIO(self._run("\n".join(lines) + "\n")), ndmin=2)
        if out.shape != (n, 4) or not np.all(np.isfinite(out)):
            raise RuntimeError("HWM14 returned a malformed or non-finite result; refusing to freeze it")
        return out


def hwm14_points(runner: HWM14Runner, scenario: str, doy, alt_km, lat_deg, lon_deg, lst_h) -> dict:
    """Direct HWM14 evaluation at the v1 coordinate convention (UT = (LST - lon/15) mod 24, iyd = YY*1000 + doy)."""
    if scenario not in v1.SCENARIOS:
        raise KeyError(f"unknown scenario {scenario!r}")
    doy, alt_km, lat_deg, lon_deg, lst_h = (np.atleast_1d(np.asarray(x, float))
                                            for x in (doy, alt_km, lat_deg, lon_deg, lst_h))
    if np.any(doy != np.round(doy)):
        raise ValueError("day of year must be integral (fractional days are carried by UT)")
    ut_h = v1._ut_h(lst_h, lon_deg)
    ut_s = ut_h * 3600.0
    iyd = (v1.EPOCH_YEAR % 100) * 1000 + np.round(doy).astype(int)
    ap = np.full(len(doy), float(v1.SCENARIOS[scenario]["ap"]))
    w = runner.winds(iyd, ut_s, alt_km, lat_deg, lon_deg, ap)
    return {"iyd": iyd, "ut_h": ut_h, "ut_s": ut_s, "ap": ap, "quiet": w[:, :2], "total": w[:, 2:]}


# ---------------------------------------------------------------------------------------------------------------------
# Producer
# ---------------------------------------------------------------------------------------------------------------------
def _fw(v: float) -> str:
    s = FLOAT_FMT_WIND % v
    return "0.0000" if s == "-0.0000" else s


def _rows_text(scenario, doy, alt, lat, lon, lst, res) -> list:
    lines = []
    for i in range(len(doy)):
        q, t = res["quiet"][i], res["total"][i]
        lines.append(",".join([scenario, v1._fmt_in(res["ap"][i]), str(int(res["iyd"][i])), v1._fmt_in(doy[i]),
                               v1._fmt_in(alt[i]), v1._fmt_in(lat[i]), v1._fmt_in(lon[i]), v1._fmt_in(lst[i]),
                               v1._fmt_in(round(float(res["ut_h"][i]), 6)), v1._fmt_in(round(float(res["ut_s"][i]), 3)),
                               _fw(t[0]), _fw(t[1]), _fw(q[0]), _fw(q[1])]))
    return lines


def _dist_grid_points():
    """Disturbance-table rows in canonical order: doy, lat, lon, lst (lst fastest)."""
    g = np.meshgrid(DIST_DOY, DIST_LAT_DEG, DIST_LON_DEG, DIST_LST_H, indexing="ij")
    return [x.ravel() for x in g]


def _dist_rows_text(scenario, doy, lat, lon, lst, res) -> list:
    d = res["total"] - res["quiet"]
    head = scenario + "," + v1._fmt_in(float(v1.SCENARIOS[scenario]["ap"]))
    return [",".join([head, str(int(res["iyd"][i])), v1._fmt_in(doy[i]), v1._fmt_in(DIST_ALT_KM), v1._fmt_in(lat[i]),
                      v1._fmt_in(lon[i]), v1._fmt_in(lst[i]), v1._fmt_in(round(float(res["ut_s"][i]), 3)),
                      _fw(d[i, 0]), _fw(d[i, 1])]) for i in range(len(doy))]


def _dist_altitude_check(runner) -> dict:
    """DWM07 height-constancy over the v1 altitude nodes on the full disturbance grid at one doy node per scenario."""
    doy, lat, lon, lst = _dist_grid_points()
    sel = doy == DIST_DOY[0]
    worst = {}
    for s in v1.SCENARIO_ORDER:
        ref = None
        m = 0.0
        for alt in v1.ALT_KM:
            r = hwm14_points(runner, s, doy[sel], np.full(int(sel.sum()), alt), lat[sel], lon[sel], lst[sel])
            d = r["total"] - r["quiet"]
            if ref is None:
                ref = d
            m = max(m, float(np.max(np.abs(d - ref))))
        worst[s] = float(f"{m:.3e}")
    if max(worst.values()) > DIST_ALT_TOL_M_S:
        raise RuntimeError(f"DWM07 varies by {worst} m/s over 180-230 km; the single-altitude table is not valid")
    return {"doy": DIST_DOY[0], "altitudes_km": list(v1.ALT_KM), "n_points_per_scenario": int(sel.sum()),
            "max_abs_diff_vs_first_altitude_m_s": worst, "tolerance_m_s": DIST_ALT_TOL_M_S}


def _container_record(gz: bytes, path: str = GZ_PATH) -> dict:
    spec = dict(v1.GZIP_SPEC)
    spec["writer"] = "abep_sim.atmosphere_orbit._gzip_bytes (shared with v1)"
    return {"file": os.path.basename(path), **spec, "sha256": hashlib.sha256(gz).hexdigest(), "bytes": len(gz),
            "zlib_version": zlib.ZLIB_VERSION,
            "note": "container hash identifies the stored file; the dataset identity is the uncompressed-CSV sha256"}


def _write_gz(path: str, raw: bytes) -> bytes:
    gz = v1._gzip_bytes(raw)
    if gzip.decompress(gz) != raw:
        raise RuntimeError("gzip round trip failed; refusing to write the container")
    with open(path, "wb") as f:
        f.write(gz)
    return gz


def _dist_file_record(raw: bytes, gz: bytes, n_rows: int) -> dict:
    return {"file": os.path.basename(DIST_GZ_PATH), "sha256": hashlib.sha256(raw).hexdigest(),
            "sha256_definition": "sha256 of the UNCOMPRESSED CSV bytes", "bytes": len(raw), "row_count": n_rows,
            "container": _container_record(gz, DIST_GZ_PATH), "columns": list(DIST_COLUMNS),
            "units": {"ut_s": UNITS["ut_s"], "alt_km": "km, geodetic (evaluation altitude DIST_ALT_KM)",
                      "u_mer_dist_m_s": "m/s, DWM07 disturbance meridional wind (HWM14 total - quiet, + northward)",
                      "u_zon_dist_m_s": "m/s, DWM07 disturbance zonal wind (HWM14 total - quiet, + eastward)"},
            "row_order": "scenario (v1 order), then doy, lat_deg, lon_deg, lst_h (lst fastest)",
            "grid": {k: list(v) for k, v in DIST_AXES.items()}, "alt_km": DIST_ALT_KM,
            "grid_trade": DIST_GRID_TRADE, "interpolation": DIST_INTERPOLATION}


def _year_independence(runner) -> dict:
    pts = dict(doy=[47.0, 230.0], alt_km=[180.0, 230.0], lat_deg=[-45.0, 60.0], lon_deg=[90.0, 270.0],
               lst_h=[4.0, 14.0])
    a = hwm14_points(runner, "ECSS_ST_HIGH", **pts)
    ut = v1._ut_h(pts["lst_h"], pts["lon_deg"])
    iyd_b = 31 * 1000 + np.asarray(pts["doy"], int)
    b = runner.winds(iyd_b, ut * 3600.0, pts["alt_km"], pts["lat_deg"], pts["lon_deg"], [240.0, 240.0])
    d = float(np.max(np.abs(np.hstack([a["quiet"], a["total"]]) - b)))
    return {"iyd_years_compared": [v1.EPOCH_YEAR % 100, 31], "max_abs_diff_m_s": d,
            "basis": "hwm14.f90 uses mod(iyd, 1000) only"}


def _source_record(runner) -> dict:
    return {"model": "HWM14 (quiet-time HWM14 + DWM07 disturbance winds)", "version": HWM14_VERSION,
            "release": "31 Dec 2014 (README.txt VERSION HISTORY); hwm14.f90 header date July 8, 2014",
            "reference": HWM14_REFERENCE, "public_repository": NRL_BASE_URL,
            "package": HWM14_TGZ, "files_sha256": dict(HWM14_FILES),
            "source_register": SOURCE_REGISTER,
            "compiler": runner.compiler, "compiler_flags": list(FC_FLAGS) or ["(none: gfortran default, -O0)"],
            "nrl_reference_check": runner.nrl_check,
            "driver": {"source": "DRIVER_F90 in abep_sim/atmosphere_orbit_v2.py (project code)",
                       "sha256": DRIVER_SHA256, "compile": runner.driver_compile,
                       "precision": "HWM14 arguments and outputs are real(4); inputs are rounded to float32 by the "
                                    "Fortran list-directed read; outputs printed es16.8 then stored %.4f"},
            "runtime": {"python": sys.version.split()[0], "numpy": np.__version__, "platform": sys.platform},
            "kp_from_ap": {s: runner.kp(v1.SCENARIOS[s]["ap"]) for s in v1.SCENARIO_ORDER}}


def build(path: str | None = None) -> dict:
    """Intentional rebuild (CLAUDE.md rule 1). Requires the verified HWM14 package + gfortran and the frozen v1 data."""
    v1_meta = v1.load()["meta"]
    if v1_meta["sha256"] != V1_CSV_SHA256:
        raise RuntimeError("frozen v1 dataset sha256 differs from the pinned V1_CSV_SHA256; v2 is defined on that v1")
    runner = HWM14Runner(path)
    try:
        doy, alt, lat, lon, lst = v1._grid_points()
        lines = [",".join(COLUMNS)]
        quiet_ref = None
        for s in v1.SCENARIO_ORDER:
            res = hwm14_points(runner, s, doy, alt, lat, lon, lst)
            if quiet_ref is None:
                quiet_ref = res["quiet"]
            elif not np.array_equal(quiet_ref, res["quiet"]):
                raise RuntimeError("HWM14 quiet-time winds differ between scenarios (they must not: no F10.7 input)")
            lines += _rows_text(s, doy, alt, lat, lon, lst, res)
        raw = ("\n".join(lines) + "\n").encode()
        gz = _write_gz(GZ_PATH, raw)
        alt_check = _dist_altitude_check(runner)
        ddoy, dlat, dlon, dlst = _dist_grid_points()
        dlines = [",".join(DIST_COLUMNS)]
        for s in v1.SCENARIO_ORDER:
            res = hwm14_points(runner, s, ddoy, np.full(len(ddoy), DIST_ALT_KM), dlat, dlon, dlst)
            dlines += _dist_rows_text(s, ddoy, dlat, dlon, dlst, res)
        draw = ("\n".join(dlines) + "\n").encode()
        dgz = _write_gz(DIST_GZ_PATH, draw)
        meta = _metadata(raw, gz, len(lines) - 1)
        meta["disturbance_file"] = _dist_file_record(draw, dgz, len(dlines) - 1)
        meta["disturbance_file"]["altitude_independence_check"] = alt_check
        meta["producer"] = _source_record(runner)
        meta["year_independence_check"] = _year_independence(runner)
        meta["distribution_snapshot_at_build"] = distribution_snapshot()
        _write_json(meta)                                  # provisional (hashes + grids) so the accessor can load
        meta["node_reproduction"] = _node_reproduction()
        meta["interpolation_validation"] = _interpolation_validation(runner)
        meta["check_subset"] = _check_subset_record(raw)
        meta["disturbance_file"]["check_subset"] = _check_subset_record(draw)
        _write_json(meta)
    finally:
        runner.close()
    return meta


def _write_json(meta: dict) -> None:
    with open(JSON_PATH, "w") as f:
        json.dump(meta, f, indent=1, sort_keys=False)
        f.write("\n")
    _CACHE.clear()


def _metadata(raw: bytes, gz: bytes, n_rows: int) -> dict:
    return {
        "dataset_id": DATASET_ID,
        "labels": LABELS,
        "file": os.path.basename(GZ_PATH),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sha256_definition": "sha256 of the UNCOMPRESSED CSV bytes (dataset identity)",
        "bytes": len(raw),
        "row_count": n_rows,
        "container": _container_record(gz),
        "distribution": {"installed_wheel": "EXCLUDED (pyproject.toml [tool.setuptools.exclude-package-data] "
                                            "'" + PYPROJECT_EXCLUDE_GLOB + "'; no package-data glob matches it)",
                         "sdist": SDIST_STATEMENT,
                         "repository_path": REPO_DATA_PATH,
                         "disturbance_repository_path": "abep_sim/data/" + os.path.basename(DIST_GZ_PATH),
                         "when_absent": "the accessor raises FileNotFoundError naming the repository path; no fallback"},
        "composition": {
            "thermodynamic_state": {"dataset_id": V1_DATASET_ID, "csv_sha256": V1_CSV_SHA256,
                                    "accessor": "abep_sim.atmosphere_orbit.state (unchanged, hash-verified on load)"},
            "winds": {"node_table": os.path.basename(GZ_PATH), "disturbance_table": os.path.basename(DIST_GZ_PATH),
                      "model": "HWM14 " + HWM14_VERSION},
            "why_not_duplicated": "A9.17 DATA_SIZE: the 17 MB NRLMSIS table is not stored twice; v2 rows carry the "
                                  "same grid keys as v1 rows (checked on load)"},
        "columns": list(COLUMNS),
        "units": UNITS,
        "row_order": "as v1: scenario (v1 order), then doy, alt_km, lat_deg, lon_deg, lst_h (lst fastest)",
        "float_format_wind": FLOAT_FMT_WIND,
        "grid": {k: list(v) for k, v in v1.AXES.items()},
        "grid_source": "imported from abep_sim.atmosphere_orbit (AXES, _grid_points); identical to " + V1_DATASET_ID,
        "scenarios": v1.SCENARIOS,
        "scenario_order": list(v1.SCENARIO_ORDER),
        "drivers_source": v1.ECSS_SOURCE,
        "ap_input": AP_INPUT,
        "date_time": {"epoch_year": v1.EPOCH_YEAR, "iyd": "YYDDD with YY = epoch_year mod 100 (HWM14 uses mod(iyd,1000))",
                      "ut": "UT = (LST - lon/15) mod 24 h, sec = UT * 3600 (v1 convention)",
                      "status": "model assumption (climatological day of year; no calendar epoch)"},
        "coordinates": {"alt": "geodetic km", "lat": "geodetic deg", "lon": "geodetic deg east",
                        "wind_frame": "local geodetic horizontal: meridional + northward, zonal + eastward"},
        "interpolation": INTERPOLATION,
        "domain": {"alt_km": list(v1.DOMAIN.alt_km), "lat_deg": list(v1.DOMAIN.lat_deg), "lst_h": list(v1.DOMAIN.lst_h),
                   "lon_deg": list(v1.DOMAIN.lon_deg), "doy": list(v1.DOMAIN.doy),
                   "out_of_domain": "ValueError (no extrapolation); unknown scenario: ValueError"},
        "relative_flow": RELATIVE_FLOW_DEFINITION,
        "orbit_coverage": {"status": v1.ORBIT_STATUS, "requirement_input": False,
                           "dataset_status": DATASET_STATUS,
                           "sampler": "orbit_states(alt_km, inclination_deg, ltan_h, scenario, doy, ut_start_h, "
                                      "n_samples): every argument required, no defaults (A9.17 ORBIT)",
                           "grid_coverage": "all latitudes, local times, longitudes and days of year"},
        "not_provided": NOT_PROVIDED,
        "authority": _authority(),
        "evidence": {"evidence_level": 4,
                     "quantity_type": "model-derived (empirical climatology model output: HWM14)",
                     "uncertainty": "HWM14 climatological uncertainty not quantified here; recorded grid interpolation "
                                    "error (interpolation_validation); HWM14 cross-compiler spread ~1e-4 m/s (README)",
                     "applicability": "180-230 km geodetic, all latitudes / local times / longitudes / seasons, the four "
                                      "ECSS scenarios with the constant ap of ap_input only",
                     "validation_status": "HWM14 build reproduces NRL's reference test output (producer."
                                          "nrl_reference_check); winds not independently validated by the project"},
        "build_command": BUILD_COMMAND,
        "check_command": CHECK_COMMAND,
        "fetch_command": FETCH_COMMAND,
    }


# ---------------------------------------------------------------------------------------------------------------------
# Loader + accessor
# ---------------------------------------------------------------------------------------------------------------------
_CACHE: dict = {}


def _manifest_in_patterns(text: str) -> tuple:
    """(recursive-include patterns under abep_sim/data, exclude patterns) of a MANIFEST.in text."""
    inc, exc = [], []
    for ln in text.splitlines():
        t = ln.split("#")[0].split()
        if t[:2] == ["recursive-include", "abep_sim/data"]:
            inc += t[2:]
        elif t[:1] == ["exclude"]:
            exc += t[1:]
    return inc, exc


def distribution_snapshot(root: str = REPO_ROOT) -> dict:
    """What the repository's packaging files actually do with this dataset (pure file inspection, no build): wheel
    exclusion from pyproject.toml, sdist membership from MANIFEST.in. Recorded at build time
    (``distribution_snapshot_at_build``) and compared with the stored claim by the tests (finding HWM-2)."""
    import fnmatch
    import tomllib
    pp_path, mi_path = os.path.join(root, "pyproject.toml"), os.path.join(root, "MANIFEST.in")
    if not (os.path.exists(pp_path) and os.path.exists(mi_path)):
        return {"status": "NOT_A_REPOSITORY_CHECKOUT"}
    pp_bytes, mi_bytes = open(pp_path, "rb").read(), open(mi_path, "rb").read()
    st = tomllib.loads(pp_bytes.decode())["tool"]["setuptools"]
    inc, exc = _manifest_in_patterns(mi_bytes.decode())
    out = {"status": "INSPECTED", "MANIFEST.in_sha256": hashlib.sha256(mi_bytes).hexdigest(),
           "wheel_excluded": PYPROJECT_EXCLUDE_GLOB in st.get("exclude-package-data", {}).get("abep_sim", []),
           "files": {}}
    for f in (GZ_PATH, DIST_GZ_PATH, JSON_PATH):
        name = os.path.basename(f)
        rel = "data/" + name
        out["files"][name] = {
            "in_wheel_package_data": any(fnmatch.fnmatchcase(rel, g) for g in st["package-data"]["abep_sim"]),
            "in_sdist": (any(fnmatch.fnmatchcase(name, g) for g in inc)
                         and not any(fnmatch.fnmatchcase("abep_sim/" + rel, g) for g in exc))}
    return out


def _missing_data_error() -> FileNotFoundError:
    return FileNotFoundError(
        f"{DATASET_ID} data files are not present at {DATA_DIR}. The dataset is repository evidence; its tables are not in "
        f"the installed abep-sim wheel or the sdist (A9.17 DATA_SIZE, {A9_17_JSON}): use a repository checkout, where it lives "
        f"at {REPO_DATA_PATH} (+ {DATASET_ID}.disturbance.csv.gz, {DATASET_ID}.json). There is no fallback dataset.")


def _read_gz(path: str, rec: dict, verify_hash: bool) -> bytes:
    gz = open(path, "rb").read()
    if verify_hash and hashlib.sha256(gz).hexdigest() != rec.get("container", {}).get("sha256"):
        raise RuntimeError(f"{path} container sha256 does not match {JSON_PATH}; frozen data altered")
    raw = gzip.decompress(gz)
    if verify_hash and hashlib.sha256(raw).hexdigest() != rec.get("sha256"):
        raise RuntimeError(f"{path} uncompressed CSV sha256 does not match {JSON_PATH}; frozen data altered")
    return raw


def _require_files():
    if not all(os.path.exists(p) for p in (GZ_PATH, DIST_GZ_PATH, JSON_PATH)):
        raise _missing_data_error()


def read_csv_bytes(meta: dict | None = None, verify_hash: bool = True) -> bytes:
    """Uncompressed node-table CSV (container + CSV sha256 verified against the manifest)."""
    _require_files()
    meta = json.load(open(JSON_PATH)) if meta is None else meta
    return _read_gz(GZ_PATH, meta, verify_hash)


def read_dist_csv_bytes(meta: dict | None = None, verify_hash: bool = True) -> bytes:
    """Uncompressed disturbance-table CSV (container + CSV sha256 verified against the manifest)."""
    _require_files()
    meta = json.load(open(JSON_PATH)) if meta is None else meta
    return _read_gz(DIST_GZ_PATH, meta.get("disturbance_file", {}), verify_hash)


def _parse(raw: bytes, columns, n_scen_rows: int) -> tuple:
    lines = raw.decode().splitlines()
    if lines[0].split(",") != list(columns):
        raise RuntimeError("unexpected CSV header")
    if len(lines) - 1 != n_scen_rows * len(v1.SCENARIO_ORDER):
        raise RuntimeError("row count does not match the grid")
    for i, s in enumerate(v1.SCENARIO_ORDER):
        if lines[1 + i * n_scen_rows].split(",", 1)[0] != s or lines[(i + 1) * n_scen_rows].split(",", 1)[0] != s:
            raise RuntimeError("scenario blocks out of order")
    return np.loadtxt(io.StringIO("\n".join(l.split(",", 1)[1] for l in lines[1:])), delimiter=",", ndmin=2)


def load(verify_hash: bool = True) -> dict:
    if "wind" in _CACHE:
        return _CACHE
    _require_files()
    meta = json.load(open(JSON_PATH))
    if meta.get("composition", {}).get("thermodynamic_state", {}).get("csv_sha256") != V1_CSV_SHA256:
        raise RuntimeError("v2 manifest does not reference the pinned v1 dataset")
    if v1.load(verify_hash=verify_hash)["meta"]["sha256"] != V1_CSV_SHA256:
        raise RuntimeError("frozen v1 dataset differs from the one v2 was built on")
    for k, v in v1.AXES.items():
        if [float(x) for x in meta["grid"][k]] != list(v):
            raise RuntimeError(f"grid axis {k} in the v2 manifest differs from the v1 module definition")
    for k, v in DIST_AXES.items():
        if [float(x) for x in meta["disturbance_file"]["grid"][k]] != list(v):
            raise RuntimeError(f"disturbance grid axis {k} in the manifest differs from the module definition")
    shape = tuple(len(v1.AXES[k]) for k in ("doy", "alt_km", "lat_deg", "lon_deg", "lst_h"))
    n_per = int(np.prod(shape))
    data = _parse(read_csv_bytes(meta, verify_hash), COLUMNS, n_per)
    keys = np.stack(v1._grid_points(), axis=1)                          # doy, alt, lat, lon, lst
    dshape = tuple(len(DIST_AXES[k]) for k in ("doy", "lat_deg", "lon_deg", "lst_h"))
    dn = int(np.prod(dshape))
    ddata = _parse(read_dist_csv_bytes(meta, verify_hash), DIST_COLUMNS, dn)
    dkeys = np.stack(_dist_grid_points(), axis=1)                      # doy, lat, lon, lst
    wind, dist = {}, {}
    for i, s in enumerate(v1.SCENARIO_ORDER):
        ap = float(v1.SCENARIOS[s]["ap"])
        block = data[i * n_per:(i + 1) * n_per]
        if not np.array_equal(block[:, 2:7], keys):
            raise RuntimeError("v2 row keys differ from the v1 grid (doy, alt, lat, lon, lst)")
        if not np.all(block[:, 0] == ap):
            raise RuntimeError("ap column differs from the scenario ap")
        wind[s] = block[:, len(KEY_COLS) - 1:].reshape(shape + (len(WIND_COLS),))
        db = ddata[i * dn:(i + 1) * dn]
        if not (np.array_equal(db[:, [2, 4, 5, 6]], dkeys) and np.all(db[:, 3] == DIST_ALT_KM) and np.all(db[:, 0] == ap)):
            raise RuntimeError("disturbance-table row keys differ from the module grid / altitude / scenario ap")
        dist[s] = db[:, len(DIST_KEY_COLS) - 1:].reshape(dshape + (len(DIST_WIND_COLS),))
    _CACHE.update({"wind": wind, "dist": dist, "meta": meta, "shape": shape, "dshape": dshape})
    return _CACHE


def _periodic_cubic_weights(x: float, period: float, m: int) -> np.ndarray:
    """Local cubic Lagrange weights on m equispaced periodic nodes k*period/m (nodes k-1..k+2); exact at nodes."""
    t = (x % period) / (period / m)
    i = int(math.floor(t))
    f = t - i
    w = np.zeros(m)
    if f == 0.0:
        w[i % m] = 1.0
        return w
    for j in (-1, 0, 1, 2):
        c = 1.0
        for k in (-1, 0, 1, 2):
            if k != j:
                c *= (f - k) / (j - k)
        w[(i + j) % m] += c
    return w


def _dist_weights(name: str, x: float) -> np.ndarray:
    if name == "doy":
        return v1._axis_weights("doy", x)
    if name == "lat_deg":
        return v1._lagrange_weights(x, DIST_LAT_DEG)
    if name == "lon_deg":
        return _periodic_cubic_weights(x, 360.0, len(DIST_LON_DEG))
    return _periodic_cubic_weights(x, 24.0, len(DIST_LST_H))


def _check_domain(alt_km, lat_deg, lst_h, lon_deg, doy, scenario):
    try:
        v1._check_domain(alt_km, lat_deg, lst_h, lon_deg, doy, scenario)
    except ValueError as e:
        raise ValueError(f"{DATASET_ID}: {e}") from None


def wind(alt_km: float, lat_deg: float, lst_h: float, lon_deg: float, doy: float, scenario: str) -> dict:
    """Interpolated HWM14 winds (m/s): quiet part from the v1-grid node table + DWM07 disturbance part from the
    disturbance table (INTERPOLATION). Out-of-domain or unknown-scenario queries raise ValueError (no extrapolation)."""
    _check_domain(alt_km, lat_deg, lst_h, lon_deg, doy, scenario)
    L = load()
    r = L["wind"][scenario][..., 2:]                                   # quiet columns
    for name, x in (("doy", doy), ("alt_km", alt_km), ("lat_deg", lat_deg), ("lon_deg", lon_deg), ("lst_h", lst_h)):
        r = np.tensordot(v1._axis_weights(name, float(x)), r, axes=(0, 0))
    d = L["dist"][scenario]
    for name, x in (("doy", doy), ("lat_deg", lat_deg), ("lon_deg", lon_deg), ("lst_h", lst_h)):
        d = np.tensordot(_dist_weights(name, float(x)), d, axes=(0, 0))
    iv = L["meta"].get("interpolation_validation", {}).get("by_scenario", {}).get(scenario, {})
    out = {"u_mer_quiet_m_s": float(r[0]), "u_zon_quiet_m_s": float(r[1]),
           "u_mer_dist_m_s": float(d[0]), "u_zon_dist_m_s": float(d[1])}
    out.update({"u_mer_m_s": out["u_mer_quiet_m_s"] + out["u_mer_dist_m_s"],
                "u_zon_m_s": out["u_zon_quiet_m_s"] + out["u_zon_dist_m_s"],
                "ap_hwm": float(v1.SCENARIOS[scenario]["ap"]), "wind_model": "HWM14 " + HWM14_VERSION,
                "wind_source": f"{DATASET_ID} sha256 {L['meta']['sha256']} + disturbance sha256 "
                               f"{L['meta']['disturbance_file']['sha256']}",
                "wind_interp_max_abs_err_m_s": iv.get("vector_total", {}).get("max_abs")})
    return out


def _node_reproduction() -> dict:
    """Composed accessor total vs the stored HWM14 total at every v1 node (max |difference|, m/s, per scenario)."""
    L = load()
    out = {}
    for s in v1.SCENARIO_ORDER:
        doy, alt, lat, lon, lst = v1._grid_points()
        stored = L["wind"][s][..., :2].reshape(-1, 2)
        sel = range(0, len(doy), 7)
        worst = max(max(abs(w["u_mer_m_s"] - stored[i, 0]), abs(w["u_zon_m_s"] - stored[i, 1])) for i, w in
                    ((i, wind(alt[i], lat[i], lst[i], lon[i], doy[i], s)) for i in sel))
        out[s] = float(f"{worst:.3e}")
    return {"stride": 7, "max_abs_diff_m_s": out,
            "expected": "<= DWM07 height variation (altitude_independence_check) + 1e-4 storage rounding"}


def state(alt_km: float, lat_deg: float, lst_h: float, lon_deg: float, doy: float, scenario: str) -> dict:
    """v1 NRLMSIS 2.1 state (abep_sim.atmosphere_orbit.state, unchanged) + HWM14 winds; labelled DESIGN_ENVELOPE_PARAMETRIC."""
    w = wind(alt_km, lat_deg, lst_h, lon_deg, doy, scenario)
    s = v1.state(alt_km, lat_deg, lst_h, lon_deg, doy, scenario)
    s.update(w)
    s.update({"dataset_id": DATASET_ID, "dataset_status": DATASET_STATUS})
    return s


# ---------------------------------------------------------------------------------------------------------------------
# Relative flow: (a) Earth-corotating atmosphere, (b) corotation + HWM14 horizontal wind
# ---------------------------------------------------------------------------------------------------------------------
RELATIVE_FLOW_DEFINITION = {
    "frame": "local east-north-up (ENU) at the state point; spherical Earth radius R_EARTH + alt (as v1); geodetic "
             "latitude used as geocentric (<= 0.2 deg, as v1)",
    "v_sc": "caller-supplied INERTIAL spacecraft velocity in ENU (m/s)",
    "corotation": "v_corot = OMEGA_E (R_EARTH + alt) cos(lat) east (mission_env OMEGA_E; v1 rigid co-rotation)",
    "wind": "HWM14 total wind: zonal east, meridional north, vertical 0",
    "a_corot": "v_rel = v_sc - v_corot",
    "b_corot_wind": "v_rel = v_sc - v_corot - v_wind",
    "angles": "relative to the caller's spacecraft velocity direction x = v_sc/|v_sc|; z' = local up made orthogonal to "
              "x; y = z' x x (left of track). angle_deg = angle(v_rel, x); yaw_deg = atan2(v_rel.y, v_rel.x); "
              "pitch_deg = atan2(v_rel.z', v_rel.x). v_rel is the spacecraft motion through the gas; the incoming "
              "flow seen on board is -v_rel. wind_vs_corot_angle_deg = angle between (a) and (b)",
    "flux": "rho * |v_rel| (kg m-2 s-1) for (a) and (b)",
}


def _angles(v_rel: np.ndarray, x: np.ndarray, y: np.ndarray, zp: np.ndarray) -> dict:
    sp = float(np.linalg.norm(v_rel))
    c = float(np.clip(np.dot(v_rel, x) / sp, -1.0, 1.0))
    return {"speed_m_s": sp, "angle_deg": math.degrees(math.acos(c)),
            "yaw_deg": math.degrees(math.atan2(float(np.dot(v_rel, y)), float(np.dot(v_rel, x)))),
            "pitch_deg": math.degrees(math.atan2(float(np.dot(v_rel, zp)), float(np.dot(v_rel, x))))}


def relative_flow(alt_km: float, lat_deg: float, v_sc_enu_m_s, u_zon_m_s: float, u_mer_m_s: float,
                  rho_kg_m3: float | None = None) -> dict:
    """Relative flow for (a) the Earth-corotating atmosphere and (b) corotation + HWM14 wind (RELATIVE_FLOW_DEFINITION).
    ``v_sc_enu_m_s`` is the caller's inertial spacecraft velocity (east, north, up), required."""
    v = np.asarray(v_sc_enu_m_s, float)
    if v.shape != (3,) or not np.all(np.isfinite(v)) or float(np.linalg.norm(v)) == 0.0:
        raise ValueError("v_sc_enu_m_s must be a finite, non-zero 3-vector (east, north, up) in m/s")
    for name, val in (("alt_km", alt_km), ("lat_deg", lat_deg), ("u_zon_m_s", u_zon_m_s), ("u_mer_m_s", u_mer_m_s)):
        if val is None or not math.isfinite(float(val)):
            raise ValueError(f"{name} must be finite")
    x = v / np.linalg.norm(v)
    up = np.array([0.0, 0.0, 1.0])
    zp = up - np.dot(up, x) * x
    if float(np.linalg.norm(zp)) < 1e-9:
        raise ValueError("spacecraft velocity is vertical; the flow angles are undefined")
    zp /= np.linalg.norm(zp)
    y = np.cross(zp, x)
    corot = np.array([OMEGA_E * (R_EARTH + alt_km * 1e3) * math.cos(math.radians(lat_deg)), 0.0, 0.0])
    w = np.array([float(u_zon_m_s), float(u_mer_m_s), 0.0])
    a = v - corot
    b = v - corot - w
    ra, rb = _angles(a, x, y, zp), _angles(b, x, y, zp)
    cab = float(np.clip(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)), -1.0, 1.0))
    out = {"v_sc_enu_m_s": [float(t) for t in v], "v_corot_east_m_s": float(corot[0]),
           "wind_east_m_s": float(w[0]), "wind_north_m_s": float(w[1]),
           "wind_along_track_m_s": float(np.dot(w, x)), "wind_cross_track_m_s": float(np.dot(w, y)),
           **{f"{k}_corot" if k != "speed_m_s" else "v_rel_corot_m_s": val for k, val in ra.items()},
           **{f"{k}_corot_wind" if k != "speed_m_s" else "v_rel_corot_wind_m_s": val for k, val in rb.items()},
           "wind_vs_corot_angle_deg": math.degrees(math.acos(cab))}
    out["v_rel_wind_minus_corot_m_s"] = out["v_rel_corot_wind_m_s"] - out["v_rel_corot_m_s"]
    if rho_kg_m3 is not None:
        out["flux_corot_kg_m2_s"] = rho_kg_m3 * out["v_rel_corot_m_s"]
        out["flux_corot_wind_kg_m2_s"] = rho_kg_m3 * out["v_rel_corot_wind_m_s"]
    return out


def flow_state(alt_km: float, lat_deg: float, lst_h: float, lon_deg: float, doy: float, scenario: str,
               v_sc_enu_m_s) -> dict:
    """state() + relative_flow() for a caller-supplied inertial spacecraft velocity (ENU)."""
    s = state(alt_km, lat_deg, lst_h, lon_deg, doy, scenario)
    s.update(relative_flow(alt_km, lat_deg, v_sc_enu_m_s, s["u_zon_m_s"], s["u_mer_m_s"], s["rho_kg_m3"]))
    return s


def orbit_states(alt_km: float, inclination_deg: float, ltan_h: float, scenario: str, doy: int, ut_start_h: float,
                 n_samples: int) -> list:
    """One circular revolution sampled as abep_sim.atmosphere_orbit.orbit_states (same mission_env geometry; every
    argument required, no defaults; inclination / LTAN are PARAMETRIC caller inputs, A9.17 ORBIT), with both relative
    flows (a) corotating and (b) corotating + HWM14 wind. The spacecraft velocity is the circular inertial velocity of
    that geometry, projected on the local ENU basis. Every state is labelled DESIGN_ENVELOPE_PARAMETRIC."""
    base = v1.orbit_states(alt_km, inclination_deg, ltan_h, scenario, doy, ut_start_h, n_samples)
    inc = math.radians(inclination_deg)
    out = []
    for s in base:
        u = math.radians(s["u_deg"])
        v_hat = np.array([-math.sin(u), math.cos(inc) * math.cos(u), math.sin(inc) * math.cos(u)])
        lam = math.atan2(math.cos(inc) * math.sin(u), math.cos(u))      # frame longitude of r (v1 geometry)
        phi = math.radians(s["lat_deg"])
        east = np.array([-math.sin(lam), math.cos(lam), 0.0])
        north = np.array([-math.sin(phi) * math.cos(lam), -math.sin(phi) * math.sin(lam), math.cos(phi)])
        up = np.array([math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi)])
        v_sc = s["v_orb_m_s"] * v_hat
        v_enu = np.array([np.dot(v_sc, east), np.dot(v_sc, north), np.dot(v_sc, up)])
        w = wind(alt_km, s["lat_deg"], s["lst_h"], s["lon_deg"], s["doy"], scenario)
        rf = relative_flow(alt_km, s["lat_deg"], v_enu, w["u_zon_m_s"], w["u_mer_m_s"], s["rho_kg_m3"])
        if abs(rf["v_rel_corot_m_s"] - s["v_rel_corot_m_s"]) > 1e-6:
            raise RuntimeError("corotating relative speed does not reproduce v1 orbit_states (geometry mismatch)")
        st = dict(s)
        st.update(w)
        st.update(rf)
        st.update({"dataset_id": DATASET_ID, "dataset_status": DATASET_STATUS, "wind_included": True,
                   "state_id": s["state_id"].replace("orbit:", "orbit_v2:", 1),
                   "geometry": "v1 orbit_states geometry (circular, constant geodetic altitude, sun-fixed node at "
                               "LTAN); relative flow (a) co-rotating atmosphere, (b) co-rotating + HWM14 horizontal "
                               "wind"})
        st.pop("wind_open_item", None)
        out.append(st)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Build-time interpolation validation + check
# ---------------------------------------------------------------------------------------------------------------------
INTERP_SEED = 20261002
INTERP_N = 1500
HIGH_LAT_DEG = 60.0


def _err_stats(e: np.ndarray) -> dict:
    a = np.abs(e)
    return {"max_abs": float(f"{np.max(a):.4e}"), "p95_abs": float(f"{np.percentile(a, 95):.4e}")}


def _interpolation_validation(runner) -> dict:
    rng = np.random.default_rng(INTERP_SEED)
    res = {"seed": INTERP_SEED, "n_points_per_scenario": INTERP_N,
           "method": "random points uniform in alt 180-230, lat -90..90, LST 0-24, lon 0-360, integer doy 1-365; "
                     "accessor interpolation vs direct HWM14 (same build) at the same inputs. Relative flow: circular "
                     "speed at the point, random horizontal direction; (b) speed / angle from interpolated vs direct "
                     "winds", "units": "m/s, deg", "high_lat_split_deg": HIGH_LAT_DEG, "by_scenario": {}}
    for s in v1.SCENARIO_ORDER:
        alt = rng.uniform(180, 230, INTERP_N); lat = rng.uniform(-90, 90, INTERP_N)
        lst = rng.uniform(0, 24, INTERP_N); lon = rng.uniform(0, 360, INTERP_N)
        doy = rng.integers(1, 366, INTERP_N).astype(float)
        az = rng.uniform(0, 2 * math.pi, INTERP_N)
        d = hwm14_points(runner, s, doy, alt, lat, lon, lst)
        it = [wind(alt[i], lat[i], lst[i], lon[i], doy[i], s) for i in range(INTERP_N)]
        tot = np.array([[w["u_mer_m_s"], w["u_zon_m_s"]] for w in it]) - d["total"]
        qui = np.array([[w["u_mer_quiet_m_s"], w["u_zon_quiet_m_s"]] for w in it]) - d["quiet"]
        dis = np.array([[w["u_mer_dist_m_s"], w["u_zon_dist_m_s"]] for w in it]) - (d["total"] - d["quiet"])
        vec = np.hypot(tot[:, 0], tot[:, 1])
        hi = np.abs(lat) > HIGH_LAT_DEG
        dsp, dang = [], []
        for i in range(INTERP_N):
            vo = math.sqrt(MU_EARTH / (R_EARTH + alt[i] * 1e3))
            vs = [vo * math.sin(az[i]), vo * math.cos(az[i]), 0.0]
            fi = relative_flow(alt[i], lat[i], vs, it[i]["u_zon_m_s"], it[i]["u_mer_m_s"])
            fd = relative_flow(alt[i], lat[i], vs, d["total"][i, 1], d["total"][i, 0])
            dsp.append(fi["v_rel_corot_wind_m_s"] - fd["v_rel_corot_wind_m_s"])
            dang.append(fi["angle_deg_corot_wind"] - fd["angle_deg_corot_wind"])
        res["by_scenario"][s] = {
            "u_mer_m_s": _err_stats(tot[:, 0]), "u_zon_m_s": _err_stats(tot[:, 1]),
            "u_mer_quiet_m_s": _err_stats(qui[:, 0]), "u_zon_quiet_m_s": _err_stats(qui[:, 1]),
            "vector_total": _err_stats(vec), "vector_quiet": _err_stats(np.hypot(qui[:, 0], qui[:, 1])),
            "vector_disturbance": _err_stats(np.hypot(dis[:, 0], dis[:, 1])),
            "vector_total_abs_lat_le_60": _err_stats(vec[~hi]), "vector_total_abs_lat_gt_60": _err_stats(vec[hi]),
            "direct_wind_speed_max_m_s": float(f"{np.max(np.hypot(*d['total'].T)):.4e}"),
            "relative_speed_corot_wind_m_s": _err_stats(np.array(dsp)),
            "flow_angle_corot_wind_deg": _err_stats(np.array(dang))}
    return res


CHECK_STRIDE = 97
CHECK_ABS_TOL_M_S = 2e-3     # other compiler builds: README ~1e-4 m/s spread + 0.5e-4 storage rounding, with margin


def _check_subset_record(raw: bytes) -> dict:
    body = raw.decode().splitlines()[1:]
    sub = "\n".join(body[i] for i in range(0, len(body), CHECK_STRIDE)) + "\n"
    return {"stride": CHECK_STRIDE, "n_rows": len(range(0, len(body), CHECK_STRIDE)),
            "sha256": hashlib.sha256(sub.encode()).hexdigest()}


def _check_file(path: str, rec: dict, label: str, problems: list, notes: list) -> list:
    """Hash / container / re-encoding / subset-hash checks of one stored table; returns the stored check-subset rows."""
    gz = open(path, "rb").read()
    raw = gzip.decompress(gz)
    if hashlib.sha256(raw).hexdigest() != rec.get("sha256"):
        problems.append(f"{label}: csv sha256 differs from the manifest")
    cont = rec.get("container", {})
    if hashlib.sha256(gz).hexdigest() != cont.get("sha256") or len(gz) != cont.get("bytes"):
        problems.append(f"{label}: container sha256/bytes differ from the manifest")
    if v1._gzip_bytes(raw) != gz:
        msg = f"{label}: re-encoding the CSV does not reproduce the stored container bytes"
        (problems if zlib.ZLIB_VERSION == cont.get("zlib_version") else notes).append(msg)
    if len(raw) != rec.get("bytes"):
        problems.append(f"{label}: uncompressed byte count differs from the manifest")
    exp_c = {k: v for k, v in _container_record(b"", path).items() if k not in ("sha256", "bytes", "zlib_version")}
    if any(cont.get(k) != json.loads(json.dumps(v)) for k, v in exp_c.items()):
        problems.append(f"{label}: container record differs from GZIP_SPEC")
    body = raw.decode().splitlines()[1:]
    if len(body) != rec.get("row_count"):
        problems.append(f"{label}: row count mismatch")
    stored = [body[i] for i in range(0, len(body), CHECK_STRIDE)]
    if hashlib.sha256(("\n".join(stored) + "\n").encode()).hexdigest() != rec.get("check_subset", {}).get("sha256"):
        problems.append(f"{label}: stored check-subset hash mismatch")
    return stored


def _rerun_subset(runner, stored, dist: bool, problems: list) -> dict:
    n_text_diff, worst = 0, 0.0
    by_s: dict = {}
    for line in stored:
        f = line.split(",")
        by_s.setdefault(f[0], []).append(f)
    nk = len(DIST_KEY_COLS) if dist else len(KEY_COLS)
    for s, rows in by_s.items():
        if dist:
            doy, alt, lat, lon, lst = (np.array([float(r[j]) for r in rows]) for j in (3, 4, 5, 6, 7))
            res = hwm14_points(runner, s, doy, alt, lat, lon, lst)
            regen = _dist_rows_text(s, doy, lat, lon, lst, res)
        else:
            doy, alt, lat, lon, lst = (np.array([float(r[j]) for r in rows]) for j in (3, 4, 5, 6, 7))
            res = hwm14_points(runner, s, doy, alt, lat, lon, lst)
            regen = _rows_text(s, doy, alt, lat, lon, lst, res)
        for a, b in zip(rows, regen):
            bf = b.split(",")
            if ",".join(a) != b:
                n_text_diff += 1
            if a[:nk] != bf[:nk]:
                problems.append(f"recomputed HWM14 inputs differ for row {','.join(a[:nk])}")
            worst = max(worst, max(abs(float(x) - float(y)) for x, y in zip(a[nk:], bf[nk:])))
    return {"rows": len(stored), "rows_text_differing": n_text_diff, "max_abs_diff_m_s": worst}


def check(path: str | None = None) -> dict:
    """Verify both tables (hashes, container, subset hash), the v1 dependency and the manifest; then, if HWM14 is
    available, re-run the NRL reference check and recompute a deterministic subset (stride 97) of both tables. Without
    HWM14 (package or gfortran) the re-run is SKIPPED with the reason; the frozen-data checks still decide ok."""
    problems, notes = [], []
    _require_files()
    meta = json.load(open(JSON_PATH))
    stored = _check_file(GZ_PATH, {**meta, "check_subset": meta.get("check_subset", {})}, "node table", problems, notes)
    dstored = _check_file(DIST_GZ_PATH, meta.get("disturbance_file", {}), "disturbance table", problems, notes)
    try:
        _CACHE.clear()
        load()
    except Exception as e:  # noqa: BLE001 - reported, fail closed
        problems.append(f"load failed: {type(e).__name__}: {e}")
    raw = gzip.decompress(open(GZ_PATH, "rb").read())
    gz = open(GZ_PATH, "rb").read()
    expected = _metadata(raw, gz, meta["row_count"])
    for k in ("dataset_id", "labels", "file", "columns", "units", "grid", "scenarios", "scenario_order", "ap_input",
              "date_time", "coordinates", "interpolation", "domain", "relative_flow", "orbit_coverage", "not_provided",
              "authority", "composition", "evidence", "distribution", "drivers_source", "grid_source"):
        if json.loads(json.dumps(expected[k])) != meta.get(k):
            problems.append(f"metadata field {k} differs from the module definition")
    drec = meta.get("disturbance_file", {})
    exp_d = _dist_file_record(b"", b"", 0)
    for k in ("file", "columns", "units", "row_order", "grid", "alt_km", "grid_trade", "interpolation"):
        if json.loads(json.dumps(exp_d[k])) != drec.get(k):
            problems.append(f"disturbance_file.{k} differs from the module definition")
    p = meta.get("producer", {})
    if p.get("files_sha256") != HWM14_FILES or p.get("package") != HWM14_TGZ or p.get("version") != HWM14_VERSION \
            or p.get("driver", {}).get("sha256") != DRIVER_SHA256 or not p.get("nrl_reference_check", {}).get("passed"):
        problems.append("producer record (HWM14 files / version / driver / NRL check) differs from the module definition")
    snap_build, snap_now = meta.get("distribution_snapshot_at_build"), distribution_snapshot()
    if not snap_build or snap_build.get("status") != "INSPECTED":
        problems.append("distribution_snapshot_at_build missing (finding HWM-2)")
    elif snap_now.get("status") == "INSPECTED" and snap_now != snap_build:
        notes.append("packaging files changed since the build (distribution_snapshot differs from "
                     "distribution_snapshot_at_build); the stored distribution statement describes the build-time state")
    rerun = {"status": "SKIPPED"}
    try:
        runner = HWM14Runner(path)
    except HWM14Unavailable as e:
        rerun["reason"] = str(e)
    else:
        try:
            same = runner.compiler == p.get("compiler")
            rerun = {"status": "RUN", "compiler": runner.compiler, "same_compiler_as_build": same,
                     "nrl_reference_check_passed": runner.nrl_check["passed"],
                     "node_table": _rerun_subset(runner, stored, False, problems),
                     "disturbance_table": _rerun_subset(runner, dstored, True, problems),
                     "tolerance_other_compiler_m_s": CHECK_ABS_TOL_M_S}
            for k in ("node_table", "disturbance_table"):
                r = rerun[k]
                if same and r["rows_text_differing"]:
                    problems.append(f"{k}: {r['rows_text_differing']} recomputed subset rows differ with the build compiler")
                if r["max_abs_diff_m_s"] > CHECK_ABS_TOL_M_S:
                    problems.append(f"{k}: recomputed winds differ by {r['max_abs_diff_m_s']} m/s > {CHECK_ABS_TOL_M_S}")
        finally:
            runner.close()
    return {"ok": not problems, "problems": problems, "notes": notes, "hwm14_rerun": rerun,
            "csv_sha256": meta.get("sha256"), "disturbance_csv_sha256": drec.get("sha256")}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["fetch-hwm14"] and len(argv) == 2:
        print(f"HWM14 {HWM14_VERSION} verified at {fetch_hwm14(argv[1])}")
        return 0
    if argv[:1] == ["build"]:
        meta = build()
        d = meta["disturbance_file"]
        print(f"{GZ_PATH} rows={meta['row_count']} csv_sha256={meta['sha256']} gz_bytes={meta['container']['bytes']} "
              f"gz_sha256={meta['container']['sha256']}\n{DIST_GZ_PATH} rows={d['row_count']} csv_sha256={d['sha256']} "
              f"gz_bytes={d['container']['bytes']} gz_sha256={d['container']['sha256']}")
        return 0
    if argv[:1] in (["check"], ["--check"]):
        r = check()
        print(("OK " if r["ok"] else "FAIL ") + json.dumps({k: v for k, v in r.items() if k != "ok"}))
        return 0 if r["ok"] else 1
    print("usage: python -m abep_sim.atmosphere_orbit_v2 fetch-hwm14 DIR | build | check", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
