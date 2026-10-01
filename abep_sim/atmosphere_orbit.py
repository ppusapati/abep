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

* A9.17 DATA_SIZE and ORBIT -- ``docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json``
  (sha256 9fd77c95c2f3142bb3e2faf68145e1225a29b307d22f86bf93a8cd562914c3ad; verbatim
  ``OD_2026_10_01_A9_17_DATA_ARTIFACT_OWNER_DECISIONS.md``): the dataset is kept as repository evidence in ONE canonical
  compressed copy (``atmosphere_msis21_orbit_v1.csv.gz``, deterministic gzip; the manifest records the sha256 of the
  uncompressed CSV bytes -- the dataset identity, unchanged since v1 was built -- and of the .gz container) and is NOT
  shipped in the installed wheel/sdist (no installed production module imports this module); the 96.3 deg / dawn-dusk
  orbit of ``mission_env`` is a CODE_DEFAULT / PARAMETRIC value, never a requirement input (inclination and LTAN are TBD
  from the official mission ICD). The design-state envelope is kept broad: the current set
  ``atmosphere_msis21_orbit_v1_design_states_v2.json`` searches every doy / longitude / local-time node at every
  integer latitude -90..90 deg, independent of the code-default orbit; the v1 design-state file (bounded at ~83.75 deg by that default) stays immutable.

Usage (repository checkout only; the data files are not part of the installed package)::

    python -m abep_sim.atmosphere_orbit build   # regenerate the .csv.gz + JSON (rule 1: intentional rebuild only)
    python -m abep_sim.atmosphere_orbit check   # verify hashes and re-run a deterministic subset with pymsis
    python -m abep_sim.atmosphere_orbit correct-metadata   # apply ERRATA / storage / labels to the JSON (data untouched)
    python -m abep_sim.atmosphere_orbit design-states-v2   # write the broad-envelope design-state set v2 (A9.17 ORBIT)

Nothing in the existing simulator imports this module (it is not wired into atmosphere.py / mission_env.py).
"""
from __future__ import annotations

import gzip
import hashlib
import inspect
import io
import json
import math
import os
import struct
import sys
import zlib
from dataclasses import dataclass

import numpy as np

from .constants import MU_EARTH, R_EARTH
from .mission_env import OMEGA_E, Spacecraft, sso_inclination_deg

DATASET_ID = "atmosphere_msis21_orbit_v1"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
# Canonical stored copy (A9.17 DATA_SIZE): deterministic gzip of the CSV text. LEGACY_CSV_PATH is the pre-A9.17 storage
# form; it is read only by ``correct-metadata`` to repack it (hash-verified) and is then removed.
GZ_PATH = os.path.join(DATA_DIR, DATASET_ID + ".csv.gz")
LEGACY_CSV_PATH = os.path.join(DATA_DIR, DATASET_ID + ".csv")
REPO_DATA_PATH = "abep_sim/data/" + DATASET_ID + ".csv.gz"
JSON_PATH = os.path.join(DATA_DIR, DATASET_ID + ".json")
DESIGN_PATH = os.path.join(DATA_DIR, DATASET_ID + "_design_states.json")
# Versioned broad-envelope design-state set (A9.17 ORBIT): candidate pool = every stored grid node, latitude -90..90 deg,
# all local times; independent of the mission_env code-default orbit. DESIGN_PATH (v1) is kept immutable.
DESIGN_V2_ID = DATASET_ID + "_design_states_v2"
DESIGN_V2_PATH = os.path.join(DATA_DIR, DESIGN_V2_ID + ".json")
DESIGN_V2_COMMAND = "python -m abep_sim.atmosphere_orbit design-states-v2"
BUILD_COMMAND = "python -m abep_sim.atmosphere_orbit build"
CHECK_COMMAND = "python -m abep_sim.atmosphere_orbit check"

A9_13_JSON = "docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json"
A9_13_SHA256 = "9afaca459efe27556033d836814f71bd03203711627899f3ffc494567d763b23"
A9_14_JSON = "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json"
A9_14_SHA256 = "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c"
A9_17_JSON = "docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json"
A9_17_SHA256 = "9fd77c95c2f3142bb3e2faf68145e1225a29b307d22f86bf93a8cd562914c3ad"
A9_17_MD = "docs/decisions/OD_2026_10_01_A9_17_DATA_ARTIFACT_OWNER_DECISIONS.md"
A9_17_MD_SHA256 = "540212c0c8862528e549555244f0fd39f8f9c9272f84dfb450bfef9dc54eba13"
ORBIT_STATUS = "CODE_DEFAULT / PARAMETRIC"

# Deterministic gzip container (RFC 1952, single member). Header written explicitly (not by the gzip module, whose OS
# byte / FNAME behaviour varies across Python versions): magic 1f 8b, CM 8 (deflate), FLG 0 (no FNAME / FCOMMENT /
# FEXTRA / FHCRC), MTIME 0, XFL 2 (maximum compression), OS 255 (unknown). Body: zlib raw deflate (wbits -15) at
# GZIP_LEVEL, memLevel 8, default strategy. Trailer: CRC-32 and ISIZE, little-endian.
GZIP_LEVEL = 9
GZIP_MEMLEVEL = 8
GZIP_HEADER = b"\x1f\x8b\x08\x00" + struct.pack("<I", 0) + b"\x02\xff"
GZIP_SPEC = {"format": "gzip (RFC 1952), single member", "mtime": 0, "fname_in_header": False, "flags": 0,
             "xfl": 2, "os_byte": 255, "compresslevel": GZIP_LEVEL, "deflate": "zlib raw deflate, wbits -15, "
             f"memLevel {GZIP_MEMLEVEL}, Z_DEFAULT_STRATEGY", "writer": "abep_sim.atmosphere_orbit._gzip_bytes"}

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
DROPPED_SPECIES = ("H", "ANOMALOUS_O", "NO")   # not stored; build records their max share
# Whether each dropped species is contained in the stored pymsis MASS_DENSITY (rho_kg_m3). Derived, not asserted: the
# rho composition regression (_rho_composition_check, run at build/check/correct-metadata) must reproduce this map.
# NRLMSIS 2.1 / pymsis 0.13.0 MASS_DENSITY excludes NO (erratum E1, review finding ATM-2).
DROPPED_IN_RHO = {"H": True, "ANOMALOUS_O": True, "NO": False}
RHO_UNITS = ("kg m-3 total mass density as output by pymsis/NRLMSIS 2.1 (Variable.MASS_DENSITY): mass-weighted sum of "
             "N2, O2, O, He, H, Ar, N and anomalous O; EXCLUDES NO (see rho_composition_check, erratum E1)")
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


# Owner-listed content that v1 does not deliver (fail-closed disclosure + tracked deviation; review finding ATM-4).
OPEN_ITEMS = (
    {"id": "ATM-OI-01",
     "title": "thermospheric wind not provided",
     "against": "A9.13 S6.14 OQ-F4-05 (dataset content 'relative flow/wind state'; json summary lists 'wind')",
     "authority": {"path": A9_13_JSON, "sha256": A9_13_SHA256, "question_id": "OQ-F4-05"},
     "status": "OPEN_DEVIATION_FOR_OWNER_DISPOSITION",
     "what_v1_provides": "geometric relative speed against a rigidly co-rotating atmosphere only (orbit_states "
                         "v_rel_corot_m_s / flux_corot_kg_m2_s, each state flagged wind_included = False)",
     "why": "NRLMSIS 2.1 has no wind output; ECSS-E-ST-10-04C Rev.1 clause 7.2.2 names HWM07 for winds, and no wind "
            "model is installed in the project environment",
     "consequence": "downstream drag / captured-flux users must not treat v_rel_corot_m_s as wind-inclusive; any wind "
                    "contribution is unquantified (TBD), not zero",
     "candidate_resolution": "owner decision: a v2 dataset adding a horizontal wind model (e.g. HWM14 via an open "
                             "package - verify availability and licence) under a new rule-1 version, or an explicit "
                             "owner acceptance of the co-rotating-atmosphere approximation for v1 users"},
)

# Controlled metadata corrections applied to the frozen JSON without regenerating the CSV (rule 1: the data file and
# its sha256 are unchanged; only descriptive metadata is corrected). Applied by ``correct-metadata``; idempotent.
ERRATA = (
    {"id": "E1", "date": "2026-10-01", "review_finding": "ATM-2",
     "fields": ["units.rho_kg_m3", "dropped_species.in_rho", "rho_composition_check"],
     "was": {"units.rho_kg_m3": "kg m-3 total mass density (includes all MSIS species and anomalous O)",
             "dropped_species.in_rho": True},
     "now": "rho_kg_m3 excludes NO; in_rho = {H: true, ANOMALOUS_O: true, NO: false}, derived by the rho composition "
            "regression recorded under rho_composition_check",
     "data_file_changed": False,
     "quantitative_effect": "descriptive only; the stored rho values are unchanged. NO's number-density share over the "
                            "grid is recorded under dropped_species (<= 0.21 %)"},
    {"id": "E2", "date": "2026-10-01", "review_finding": "ATM-4", "fields": ["open_items"],
     "now": "wind omission against OQ-F4-05 tracked as open item ATM-OI-01 for owner disposition",
     "data_file_changed": False},
    {"id": "E3", "date": "2026-10-01", "decision": "A9.17 DATA_SIZE",
     "authority": {"path": A9_17_JSON, "sha256": A9_17_SHA256, "decision_key": "DATA_SIZE"},
     "fields": ["file", "sha256_definition", "bytes_definition", "container", "distribution"],
     "was": {"file": DATASET_ID + ".csv", "storage": "uncompressed CSV, shipped as package data"},
     "now": "one canonical deterministic gzip copy (" + DATASET_ID + ".csv.gz); manifest records the uncompressed-CSV "
            "sha256 (unchanged, c0ce282e99695be8cae0834270c5b9ff7853033255665abda7ec18c307566164) and the container "
            "sha256; excluded from the installed wheel/sdist",
     "data_file_changed": False,
     "quantitative_effect": "storage only: the decompressed bytes are identical to the v1 CSV (same sha256, same rows)"},
    {"id": "E4", "date": "2026-10-01", "decision": "A9.17 ORBIT",
     "authority": {"path": A9_17_JSON, "sha256": A9_17_SHA256, "decision_key": "ORBIT"},
     "fields": ["orbit_coverage", "design_states_file (rule / orbit_basis / authority labels)"],
     "was": {"orbit_coverage.inclination_status": "MODEL_ASSUMPTION (not owner-registered)"},
     "now": "the mission_env 96.3 deg / dawn-dusk orbit is labelled CODE_DEFAULT / PARAMETRIC, never a requirement "
            "input; inclination / LTAN TBD from the official mission ICD. Design-states file regenerated with label "
            "changes only (top-level rule / orbit_basis / authority; the 179 per-state records kept verbatim)",
     "data_file_changed": False,
     "known_v1_defect_not_changed": "per-state interp_max_rel_err_rho is null for the 26 interpolated "
                                    "latitude-boundary design states (build() generated them before "
                                    "interpolation_validation was written to the JSON); physical values unaffected; "
                                    "left as frozen, open for the next design-state version"},
    {"id": "E5", "date": "2026-10-01", "decision": "A9.17 ORBIT", "review_finding": "PKG-1",
     "authority": {"path": A9_17_JSON, "sha256": A9_17_SHA256, "decision_key": "ORBIT"},
     "fields": ["design_states_file_v2", "orbit_coverage.design_state_envelope"],
     "was": {"design_state_envelope": "v1 set only, bounded at |lat| <= ~83.75 deg by the CODE_DEFAULT SSO family"},
     "now": "versioned broad-envelope design-state set " + DESIGN_V2_ID + ".json added (candidate pool = every grid "
            "doy / longitude / local-time node x every integer latitude -90..90 deg; independent of "
            "mission_env.sso_inclination_deg); v1 design-"
            "state file kept byte-identical",
     "data_file_changed": False,
     "resolves": "E4 open item (latitude bound) and, for new use, the per-state interp_max_rel_err_rho null defect: "
                 "v2 is generated after interpolation_validation is in the manifest, so every off-node v2 state "
                 "carries its scenario's recorded interpolation error and grid-node states carry 0.0"},
)

# Rho composition regression: an independent, mass-table-free determination of which pymsis species MASS_DENSITY
# contains. Over a fixed point set spanning 100-2000 km (wide altitude range so H, He and anomalous O are resolvable),
# solve rho = sum_i c_i n_i by least squares on rho-normalised rows; c_i is the implied particle mass. A species is
# "in rho" iff |c_i| exceeds RHO_COEF_THRESHOLD_AMU (the lightest resolved species, H, implies ~1 amu).
RHO_CHECK_POINTS = {"alt_km": (100.0, 150.0, 200.0, 300.0, 450.0, 600.0, 800.0, 1000.0, 1500.0, 2000.0),
                    "lat_deg": (-80.0, -30.0, 0.0, 40.0, 75.0), "lon_deg": (0.0, 90.0, 180.0, 270.0),
                    "date": "2027-03-01T12:00", "scenarios": ("ECSS_LT_LOW", "ECSS_LT_MODERATE", "ECSS_LT_HIGH")}
RHO_CHECK_SPECIES = ("N2", "O2", "O", "HE", "H", "AR", "N", "ANOMALOUS_O", "NO")
RHO_COEF_THRESHOLD_AMU = 0.1


def _rho_composition_check() -> dict:
    import pymsis
    from .constants import AMU
    V = pymsis.Variable
    P = RHO_CHECK_POINTS
    rows = []
    for s in P["scenarios"]:
        sc = SCENARIOS[s]
        o = pymsis.calculate(np.datetime64(P["date"]), list(P["lon_deg"]), list(P["lat_deg"]), list(P["alt_km"]),
                             [sc["f107"]], [sc["f107a"]], [[sc["ap"]] * 7], version=MSIS_VERSION)
        o = np.asarray(o, float)
        rows.append(o.reshape(-1, o.shape[-1]))
    o = np.concatenate(rows)
    rho = o[:, int(V.MASS_DENSITY)]
    A = np.nan_to_num(o[:, [int(getattr(V, k)) for k in RHO_CHECK_SPECIES]])
    c, *_ = np.linalg.lstsq(A / rho[:, None], np.ones(len(rho)), rcond=None)
    amu = {k: float(v / AMU) for k, v in zip(RHO_CHECK_SPECIES, c)}
    resid = float(np.max(np.abs(A @ c / rho - 1.0)))
    name = {"HE": "He", "AR": "Ar"}
    in_rho = {name.get(k, k): bool(abs(v) > RHO_COEF_THRESHOLD_AMU) for k, v in amu.items()}
    return {"method": "least squares rho = sum_i c_i n_i on rho-normalised rows (no mass table assumed)",
            "points": {k: list(v) if isinstance(v, tuple) else v for k, v in P.items()},
            "n_points": int(len(rho)), "max_abs_rel_residual": float(f"{resid:.3e}"),
            "implied_mass_amu": {name.get(k, k): round(v, 3) + 0.0 for k, v in amu.items()},
            "threshold_amu": RHO_COEF_THRESHOLD_AMU, "in_rho": in_rho,
            "evidence": "model-derived (pymsis NRLMSIS 2.1 output); amu values diagnostic, AMU from abep_sim/constants.py"}


def correct_metadata() -> dict:
    """Apply ERRATA, the A9.17 storage fields and orbit labels to the frozen JSON, and regenerate the design-states file
    when only its labels change (refused if any state would change). The data bytes are never altered: the uncompressed
    CSV sha256 must match the manifest. A pre-A9.17 uncompressed CSV, if present, is repacked into the canonical .csv.gz
    and removed. Idempotent."""
    meta = json.load(open(JSON_PATH))
    if os.path.exists(GZ_PATH):
        gz = open(GZ_PATH, "rb").read()
        raw = gzip.decompress(gz)
    elif os.path.exists(LEGACY_CSV_PATH):
        raw = open(LEGACY_CSV_PATH, "rb").read()
        gz = None
    else:
        raise _missing_data_error()
    if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise RuntimeError("csv sha256 does not match the metadata; refusing to correct metadata of altered data")
    rc = _rho_composition_check()
    if {k: rc["in_rho"][k] for k in DROPPED_IN_RHO} != DROPPED_IN_RHO:
        raise RuntimeError(f"rho composition regression {rc['in_rho']} contradicts DROPPED_IN_RHO {DROPPED_IN_RHO}")
    if gz is None:
        gz = _write_gz(raw)
    meta.update(storage_fields(raw, gz))
    meta["orbit_coverage"] = orbit_coverage()
    meta["authority"] = _authority()
    meta["units"]["rho_kg_m3"] = RHO_UNITS
    meta["dropped_species"]["in_rho"] = dict(DROPPED_IN_RHO)
    meta["rho_composition_check"] = rc
    meta["open_items"] = [dict(x) for x in OPEN_ITEMS]
    meta["errata"] = [dict(e) for e in ERRATA]
    _write_json(meta)
    if not os.path.exists(DESIGN_PATH):
        raise _missing_data_error()
    old = json.load(open(DESIGN_PATH))
    fresh = json.loads(_design_states_text())
    if _states_physical(old["states"]) != _states_physical(fresh["states"]):
        raise RuntimeError("design states would change content (not only labels); that is a rebuild, not a correction")
    # Label-only regeneration: the frozen per-state records are kept verbatim; only the top-level descriptive fields
    # (rule text, orbit_basis, authority) are taken from the current module definition.
    new = {k: (old["states"] if k == "states" else fresh[k]) for k in fresh}
    ds_text = json.dumps(new, indent=1) + "\n"
    with open(DESIGN_PATH, "w", newline="\n") as f:
        f.write(ds_text)
    meta["design_states_file"]["sha256"] = hashlib.sha256(ds_text.encode()).hexdigest()
    _write_json(meta)
    if os.path.exists(LEGACY_CSV_PATH):
        os.remove(LEGACY_CSV_PATH)          # one canonical copy (A9.17 DATA_SIZE)
    _CACHE.clear()
    return meta


# Per-state field excluded from the label-only comparison: in the v1 file it is null for the interpolated
# latitude-boundary states, because build() generated the design states while the provisional JSON did not yet carry
# interpolation_validation (known v1 defect, recorded in ERRATA E4; the stored states are kept verbatim).
_DS_ANNOTATION_FIELDS = ("interp_max_rel_err_rho",)


def _states_physical(states) -> list:
    return [{k: v for k, v in st.items() if k not in _DS_ANNOTATION_FIELDS} for st in states]


def _write_json(meta: dict) -> None:
    with open(JSON_PATH, "w") as f:
        json.dump(meta, f, indent=1, sort_keys=False)
        f.write("\n")
    _CACHE.clear()


# ---------------------------------------------------------------------------------------------------------------------
# Canonical compressed storage (A9.17 DATA_SIZE)
# ---------------------------------------------------------------------------------------------------------------------
def _gzip_bytes(raw: bytes) -> bytes:
    """Deterministic gzip container of ``raw`` (see GZIP_SPEC): same bytes for the same input and zlib build."""
    c = zlib.compressobj(GZIP_LEVEL, zlib.DEFLATED, -15, GZIP_MEMLEVEL, zlib.Z_DEFAULT_STRATEGY)
    body = c.compress(raw) + c.flush()
    return GZIP_HEADER + body + struct.pack("<II", zlib.crc32(raw) & 0xFFFFFFFF, len(raw) & 0xFFFFFFFF)


def _missing_data_error() -> FileNotFoundError:
    return FileNotFoundError(
        f"{DATASET_ID} data files are not present at {DATA_DIR}. The dataset is repository evidence and is excluded "
        f"from the installed abep-sim wheel/sdist (A9.17 DATA_SIZE, {A9_17_JSON}): use a repository checkout, where it "
        f"lives at {REPO_DATA_PATH} (+ {DATASET_ID}.json, {DATASET_ID}_design_states.json, {DESIGN_V2_ID}.json); in a "
        f"checkout without it, "
        f"rebuild with `{BUILD_COMMAND}`. There is no fallback dataset.")


def _write_gz(raw: bytes) -> bytes:
    gz = _gzip_bytes(raw)
    if gzip.decompress(gz) != raw:          # independent decoder round trip before anything is written
        raise RuntimeError("gzip round trip failed; refusing to write the container")
    with open(GZ_PATH, "wb") as f:
        f.write(gz)
    return gz


def _container_record(gz: bytes) -> dict:
    return {"file": os.path.basename(GZ_PATH), **GZIP_SPEC, "sha256": hashlib.sha256(gz).hexdigest(),
            "bytes": len(gz), "zlib_version": zlib.ZLIB_VERSION,
            "note": "container hash identifies the stored file; the dataset identity is the uncompressed-CSV sha256 "
                    "(field sha256). Another zlib build may encode the same CSV to different container bytes."}


def read_csv_bytes(meta: dict | None = None, verify_hash: bool = True) -> bytes:
    """Uncompressed CSV bytes of the frozen dataset, read from the canonical .csv.gz. With ``verify_hash`` the
    container sha256 and the uncompressed-CSV sha256 recorded in the manifest are both checked (fail closed)."""
    if not (os.path.exists(GZ_PATH) and os.path.exists(JSON_PATH)):
        raise _missing_data_error()
    meta = json.load(open(JSON_PATH)) if meta is None else meta
    gz = open(GZ_PATH, "rb").read()
    if verify_hash and hashlib.sha256(gz).hexdigest() != meta.get("container", {}).get("sha256"):
        raise RuntimeError(f"{GZ_PATH} container sha256 does not match {JSON_PATH}; frozen data altered")
    raw = gzip.decompress(gz)
    if verify_hash and hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise RuntimeError(f"{GZ_PATH} uncompressed CSV sha256 does not match {JSON_PATH}; frozen data altered")
    return raw


def storage_fields(raw: bytes, gz: bytes) -> dict:
    """Manifest fields describing the stored data (A9.17 DATA_SIZE)."""
    return {
        "file": os.path.basename(GZ_PATH),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sha256_definition": "sha256 of the UNCOMPRESSED CSV bytes (dataset identity; unchanged by the A9.17 repack)",
        "bytes": len(raw),
        "bytes_definition": "size of the uncompressed CSV in bytes",
        "container": _container_record(gz),
        "distribution": {
            "installed_package": "EXCLUDED: the .csv.gz, this manifest and the design-states files are not shipped in "
                                 "the abep-sim wheel/sdist (pyproject exclude-package-data + MANIFEST.in exclude); no "
                                 "installed production module imports abep_sim.atmosphere_orbit",
            "repository_path": REPO_DATA_PATH,
            "when_absent": "the accessor raises FileNotFoundError naming the repository path; no fallback",
            "authority": {"path": A9_17_JSON, "sha256": A9_17_SHA256, "decision_key": "DATA_SIZE",
                          "answer": "KEEP_DATA_ARTIFACT_EXCLUDE_FROM_INSTALL_WHERE_POSSIBLE",
                          "verbatim": {"path": A9_17_MD, "sha256": A9_17_MD_SHA256}}},
    }


def orbit_coverage() -> dict:
    """Orbit labelling (A9.17 ORBIT): the mission_env 96.3 deg / dawn-dusk orbit is CODE_DEFAULT / PARAMETRIC."""
    return {
        "inclination_ltan_status": ORBIT_STATUS,
        "requirement_input": False,
        "code_default": "abep_sim/mission_env.py sso_inclination_deg(alt) (J2 sun-synchronous condition; ~96.3 deg, "
                        "96.25-96.42 deg over 180-230 km) and Spacecraft.inc_deg = 96.33 / ltan_h = 6.0 (dawn-dusk); "
                        "a parametric code default, never a requirement input",
        "real_orbit": "TBD from the official mission definition (DRDO / spacecraft ICD / PDR mission definition); the RFP "
                      "fixes only 180-230 km. Once supplied, a new orbit-resolved dataset version is built; this default "
                      "is never reinterpreted as the real orbit",
        "dataset_grid_coverage": "full geodetic latitude band -90..90 deg, all local solar times, all longitudes, all "
                                 "days of year: any inclination and any LTAN lie inside the dataset",
        "design_state_envelope": {
            "current_set": os.path.basename(DESIGN_V2_PATH),
            "v2": {"file": os.path.basename(DESIGN_V2_PATH), "status": "BROAD_ENVELOPE (A9.17 ORBIT)",
                   "local_time": "all local times (LTAN-agnostic)",
                   "latitude": "every integer geodetic latitude -90..90 deg (all 19 nodes, poles included; off-node "
                               "latitudes via the accessor interpolation); independent of "
                               "mission_env.sso_inclination_deg and of any inclination / LTAN",
                   "covers": "every inclination 0-180 deg and every LTAN, at the dataset grid resolution"},
            "v1": {"file": os.path.basename(DESIGN_PATH), "status": "IMMUTABLE_V1_PARAMETRIC_BOUND (kept for "
                   "traceability; not the broad envelope)",
                   "local_time": "all local times (LTAN-agnostic)",
                   "latitude": "|lat| <= reachable_lat_max_deg(), the max |latitude| of the CODE_DEFAULT SSO family over "
                               "180-230 km (83.6-83.75 deg); does not cover inclinations strictly between ~83.75 and "
                               "~96.25 deg or polar orbits"},
            "latitude_status": "RESOLVED by the versioned v2 set (all latitudes); the v1 set keeps its PARAMETRIC "
                               "83.75 deg bound unchanged (rule 1)"},
        "sso_inclination_deg_at_grid_alt": {str(int(a)): round(sso_inclination_deg(a), 4) for a in ALT_KM},
        "authority": {"path": A9_17_JSON, "sha256": A9_17_SHA256, "decision_key": "ORBIT",
                      "answer": "ORBIT_INCLINATION_LTAN_TBD_FROM_OFFICIAL_MISSION_ICD"},
    }


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
    raw = ("\n".join(lines) + "\n").encode()
    gz = _write_gz(raw)
    if os.path.exists(LEGACY_CSV_PATH):
        os.remove(LEGACY_CSV_PATH)          # one canonical copy (A9.17 DATA_SIZE)
    _CACHE.clear()
    meta = _metadata(raw, gz, len(lines) - 1)
    meta["dropped_species"] = {"species": list(DROPPED_SPECIES), "in_rho": dict(DROPPED_IN_RHO),
                               "reason": "not requested by the lane; keeps the CSV < 20 MB",
                               "max_number_density_share_over_grid": dropped}
    meta["rho_composition_check"] = _rho_composition_check()
    meta["errata"] = [dict(e) for e in ERRATA]
    with open(JSON_PATH, "w") as f:      # provisional (hash + grid) so the accessor can load for validation
        json.dump(meta, f)
    meta["year_independence_check"] = _year_independence()
    meta["interpolation_validation"] = _interpolation_validation()
    meta["check_subset"] = _check_subset_record(raw)
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
    if os.path.exists(DESIGN_V2_PATH):
        os.remove(DESIGN_V2_PATH)           # full intentional rebuild (rule 1): v2 is re-derived from the new dataset
    return write_design_states_v2()


def _authority() -> dict:
    return {"A9.13 S6.14 OQ-F4-05": {"path": A9_13_JSON, "sha256": A9_13_SHA256},
            "A9.14 S9.7 OD2": {"path": A9_14_JSON, "sha256": A9_14_SHA256},
            "A9.14 S9.8 OD3": {"path": A9_14_JSON, "sha256": A9_14_SHA256},
            "A9.17 DATA_SIZE": {"path": A9_17_JSON, "sha256": A9_17_SHA256},
            "A9.17 ORBIT": {"path": A9_17_JSON, "sha256": A9_17_SHA256},
            "CLAUDE.md rule 1": "versioned rebuild; atmosphere_msis21_v1.* unchanged"}


def _metadata(raw: bytes, gz: bytes, n_rows: int) -> dict:
    import pymsis
    st = storage_fields(raw, gz)
    return {
        "dataset_id": DATASET_ID,
        "file": st.pop("file"),
        "sha256": st.pop("sha256"),
        "row_count": n_rows,
        **st,
        "columns": list(COLUMNS),
        "units": {"f107": "sfu (1e-22 W m-2 Hz-1)", "f107a": "sfu, 81-day average", "ap": "daily Ap", "doy": "day of year",
                  "alt_km": "km, geodetic (WGS84)", "lat_deg": "deg, geodetic (WGS84)", "lon_deg": "deg east",
                  "lst_h": "h, local solar time = UT + lon/15", "ut_h": "h, UT = (lst_h - lon_deg/15) mod 24",
                  "rho_kg_m3": RHO_UNITS,
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
        "orbit_coverage": orbit_coverage(),
        "not_provided": {"winds": "NRLMSIS has no wind output; ECSS 7.2.2 names HWM07, which is not installed. The "
                                  "accessor reports the geometric co-rotating-atmosphere relative speed only "
                                  "(status: no thermospheric wind)."},
        "open_items": [dict(x) for x in OPEN_ITEMS],
        "authority": _authority(),
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
    if not (os.path.exists(GZ_PATH) and os.path.exists(JSON_PATH)):
        raise _missing_data_error()
    meta = json.load(open(JSON_PATH))
    raw = read_csv_bytes(meta, verify_hash=verify_hash)    # container + uncompressed-CSV sha256 (A9.17 DATA_SIZE)
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
    """Inclination/LTAN code default of abep_sim/mission_env.py (~96.3 deg SSO, dawn-dusk): CODE_DEFAULT / PARAMETRIC,
    never a requirement input (A9.17 ORBIT; inclination and LTAN are TBD from the official mission ICD)."""
    return {"inclination_deg": sso_inclination_deg(alt_km), "ltan_h": Spacecraft().ltan_h,
            "status": ORBIT_STATUS, "requirement_input": False,
            "source": "abep_sim/mission_env.py: sso_inclination_deg(alt) (J2 SSO condition, RAAN drift 360/365.25 "
                      "deg/day); Spacecraft.ltan_h = 6.0 ('06:00 LTAN dawn-dusk')",
            "authority": {"path": A9_17_JSON, "sha256": A9_17_SHA256, "decision_key": "ORBIT"}}


def orbit_states(alt_km: float, inclination_deg: float, ltan_h: float, scenario: str, doy: int, ut_start_h: float,
                 n_samples: int) -> list[dict]:
    """Sample one circular revolution at constant geodetic altitude, equally spaced in time (argument of latitude u).

    Geometry (sun-fixed frame, ascending node at local time ``ltan_h``): lat = asin(sin i sin u); hour-angle offset
    from the node dα = atan2(cos i sin u, cos u); LST = ltan + dα/15; UT = ut_start + t/3600; lon = 15 (LST - UT).
    Approximations (recorded per state): geocentric latitude used as geodetic (<= 0.2 deg); constant geodetic altitude
    (the RFP altitude definition) rather than constant radius; node/Sun motion within one revolution neglected
    (< 0.1 deg). Relative speed: circular inertial velocity minus a rigidly co-rotating atmosphere (mission_env
    OMEGA_E), no thermospheric wind. Every state carries the equal-time weight 1/n_samples.
    ``inclination_deg`` / ``ltan_h`` are caller-supplied PARAMETRIC inputs; passing the mission_env code default
    (96.3 deg dawn-dusk) does not make it a requirement input (A9.17 ORBIT, status recorded per state).
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
    if not DOMAIN.doy[0] <= doy <= DOMAIN.doy[1]:
        raise ValueError(f"doy = {doy} outside the {DATASET_ID} domain {list(DOMAIN.doy)}")
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
        if doy_k > DOMAIN.doy[1]:      # domain end (365), not the last grid node (ATM-1)
            raise ValueError("orbit crosses the end of the dataset year; choose doy/ut_start_h inside it")
        lon = (15.0 * (lst - ut)) % 360.0
        r = a * np.array([math.cos(u), math.cos(inc) * math.sin(u), math.sin(inc) * math.sin(u)])
        v = v_orb * np.array([-math.sin(u), math.cos(inc) * math.cos(u), math.sin(inc) * math.cos(u)])
        v_rel = v - np.cross([0.0, 0.0, OMEGA_E], r)
        s = state(alt_km, lat, lst, lon, float(doy_k), scenario)
        s.update({"t_s": t, "u_deg": math.degrees(u), "ut_h": ut, "inclination_deg": inclination_deg, "ltan_h": ltan_h,
                  "orbit_inputs_status": "PARAMETRIC (caller-supplied; not a requirement input)",
                  "v_orb_m_s": v_orb, "v_rel_corot_m_s": float(np.linalg.norm(v_rel)),
                  "flux_corot_kg_m2_s": s["rho_kg_m3"] * float(np.linalg.norm(v_rel)),
                  "wind_included": False, "wind_open_item": OPEN_ITEMS[0]["id"],
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
    """Max |latitude| reached by the CODE_DEFAULT / PARAMETRIC SSO family over 180-230 km
    (mission_env.sso_inclination_deg); a parametric bound of the immutable v1 design-state rule only, not a requirement
    input. The current design-state set (design_states_v2) does not use it."""
    return max(180.0 - sso_inclination_deg(a) for a in ALT_KM)


def _select_design_states(L: dict, lat_nodes, boundary_lats) -> list:
    """Design-state selection shared by the v1 and v2 sets. Candidate pool per scenario x altitude node: every grid node
    whose latitude index is in ``lat_nodes`` plus the interpolated states at each latitude in ``boundary_lats`` (empty
    for v2), for every doy / longitude / local-time node. Selection rule: see design_states()."""
    nd, na, nl, no, nt = L["shape"]
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
                        for blat in boundary_lats:
                            pool.append(state(alt, blat, LST_H[ilt], LON_DEG[ilo], DOY[idoy], s))
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
    return out


# v2 latitude pool: every integer degree -90..90 (contains the 19 grid nodes). Off-node values come from the accessor's
# own latitude interpolation (cubic in log, INTERPOLATION["lat_deg"]); the v1 rho minimum, for example, sits off-node
# near -83.75 deg, ~1.5 % below the -80 deg node (direct NRLMSIS also has its minimum between the -80 and -90 deg
# nodes there), so a node-only pool would not contain it.
V2_LAT_STEP_DEG = 1.0
V2_LAT_DEG = tuple(float(x) for x in np.arange(-90.0, 90.0 + 0.5 * V2_LAT_STEP_DEG, V2_LAT_STEP_DEG))


def _pool_arrays(L: dict, scenario: str, ia: int, lats) -> dict:
    """Vectorised candidate pool for one scenario x altitude node: all doy / lon / LST nodes x ``lats`` (latitude-only
    interpolation of the log grid with the accessor's latitude weights; node latitudes are reproduced exactly).
    Pool order: doy, lon, LST, lat (lat fastest)."""
    lg = L["log_grid"][scenario][:, ia]                               # (doy, lat, lon, lst, col)
    W = np.array([_axis_weights("lat_deg", float(x)) for x in lats])  # (n_lat_pool, n_lat_nodes)
    v = np.exp(np.einsum("fl,dlotc->dotfc", W, lg))                    # (doy, lon, lst, lat_pool, col)
    nd, no, nt, nf, nc = v.shape
    v = v.reshape(-1, nc)
    idx = np.indices((nd, no, nt, nf)).reshape(4, -1)
    n = v[:, 1:1 + len(SPECIES)]
    ntot = np.sum(n, axis=1)
    out = {"rho_kg_m3": v[:, 0], "T_K": v[:, -1], "i_doy": idx[0], "i_lon": idx[1], "i_lst": idx[2], "i_lat": idx[3],
           "lst_h": np.asarray(LST_H)[idx[2]]}
    for q in ("O", "N2", "O2"):
        out[f"x_{q}"] = n[:, SPECIES.index(q)] / ntot
    return out


def _select_design_states_v2(L: dict, lats) -> list:
    """Selection rule of design_states() applied to the vectorised pool of _pool_arrays (stable orderings, as v1).
    Each selected candidate is materialised with node_state (node latitude) or state (off-node latitude)."""
    states: dict = {}

    def mk(s, ia, P, k):
        lat = float(lats[P["i_lat"][k]])
        idoy, ilo, ilt = int(P["i_doy"][k]), int(P["i_lon"][k]), int(P["i_lst"][k])
        if lat in LAT_DEG:
            return node_state(idoy, ia, LAT_DEG.index(lat), ilo, ilt, s)
        return state(ALT_KM[ia], lat, LST_H[ilt], LON_DEG[ilo], DOY[idoy], s)

    def add(st, label):
        key = (st["scenario"], st["alt_km"], round(st["lat_deg"], 6), st["lst_h"], st["lon_deg"], st["doy"])
        if key not in states:
            st = dict(st)
            st["labels"] = []
            st["state_id"] = "ds2:{}:alt{:g}:lat{:+.4f}:lst{:g}:lon{:g}:doy{:g}".format(*key)
            states[key] = st
        if label not in states[key]["labels"]:
            states[key]["labels"].append(label)

    env = {}
    for s in SCENARIO_ORDER:
        for ia, alt in enumerate(ALT_KM):
            P = _pool_arrays(L, s, ia, lats)
            order = np.argsort(P["rho_kg_m3"], kind="stable")
            add(mk(s, ia, P, int(order[len(order) // 2])), f"NOMINAL_MEDIAN_RHO[{s},{alt:g}km]")
            for q in EXTREMA_QUANTITIES:
                for kind, fn in (("MAX", np.argmax), ("MIN", np.argmin)):
                    k = int(fn(P[q]))
                    st = mk(s, ia, P, k)
                    add(st, f"{kind}_{q}[{s},{alt:g}km]")
                    cur = env.get((kind, q))
                    if cur is None or (kind == "MAX" and P[q][k] > cur[0]) or (kind == "MIN" and P[q][k] < cur[0]):
                        env[(kind, q)] = (float(P[q][k]), st)
            logr = np.log(P["rho_kg_m3"])
            lm = {float(h): float(np.mean(logr[P["lst_h"] == h])) for h in LST_H}
            for tag, lst_sel in (("LST_PEAK", max(lm, key=lm.get)), ("LST_TROUGH", min(lm, key=lm.get))):
                sub = np.nonzero(P["lst_h"] == lst_sel)[0]
                sub = sub[np.argsort(P["rho_kg_m3"][sub], kind="stable")]
                add(mk(s, ia, P, int(sub[len(sub) // 2])), f"{tag}[{s},{alt:g}km]")
    for (kind, q), (_, st) in sorted(env.items(), key=lambda kv: kv[0]):
        add(st, f"ENVELOPE_{kind}_{q}")
    out = sorted(states.values(), key=lambda d: d["state_id"])
    for st in out:
        st["required"] = True
        st["nominal_mission_scenario"] = st["scenario"] == NOMINAL_SCENARIO
    return out


def _lat_refinement_sensitivity(L: dict, fine_step: float = 0.25) -> dict:
    """Measured change of the per-scenario x altitude extrema when the v2 latitude pool step is refined from
    V2_LAT_STEP_DEG to ``fine_step`` (same interpolant): max relative change per quantity (recorded in the v2 file)."""
    fine = tuple(float(x) for x in np.arange(-90.0, 90.0 + 0.5 * fine_step, fine_step))
    worst = {q: 0.0 for q in EXTREMA_QUANTITIES}
    for s in SCENARIO_ORDER:
        for ia in range(len(ALT_KM)):
            a, b = _pool_arrays(L, s, ia, V2_LAT_DEG), _pool_arrays(L, s, ia, fine)
            for q in EXTREMA_QUANTITIES:
                worst[q] = max(worst[q], abs(b[q].max() / a[q].max() - 1.0), abs(b[q].min() / a[q].min() - 1.0))
    return {"fine_step_deg": fine_step, "max_abs_rel_change_of_extrema": {q: float(f"{v:.3e}") for q, v in worst.items()}}


def design_states() -> dict:
    """S9.8 design-state set, derived from the frozen dataset only (no hand-picked F10.7/density points).

    Candidate pool: every grid node with |lat| <= reachable_lat_max_deg() plus the interpolated latitude-boundary states
    at +/- reachable_lat_max_deg() for every other node coordinate (the CODE_DEFAULT / PARAMETRIC SSO family of
    mission_env reaches 83.6-83.75 deg, between the 80 and 90 deg nodes; it is not a requirement input). The pool is
    LTAN-agnostic (all local times): inclination and LTAN are TBD from the official mission ICD (A9.17 ORBIT).
    For every scenario x altitude node, the set contains: NOMINAL (state of median density), the max/min of rho, x_O, x_N2, x_O2, T, and LST_PEAK / LST_TROUGH (median-density state at the local time whose
    lat/lon/season-mean density is highest / lowest). Envelope extrema over all scenarios and altitudes are included.
    The mission nominal scenario is ECSS long-term moderate. Identical states are merged with all their labels.
    """
    L = load()
    lat_r = reachable_lat_max_deg()
    lat_nodes = [i for i, v in enumerate(LAT_DEG) if abs(v) <= lat_r]
    out = _select_design_states(L, lat_nodes, (-lat_r, lat_r))
    return {"dataset_id": DATASET_ID, "dataset_sha256": L["meta"]["sha256"], "reachable_lat_max_deg": lat_r,
            "nominal_scenario": NOMINAL_SCENARIO,
            "orbit_basis": {"status": ORBIT_STATUS, "requirement_input": False,
                            "local_time": "all local times (LTAN-agnostic)",
                            "latitude": "|lat| <= reachable_lat_max_deg() of the CODE_DEFAULT SSO family (parametric)",
                            "real_orbit": "TBD from the official mission ICD; a new dataset version when supplied"},
            "authority": {"A9.14 S9.8 OD3": {"path": A9_14_JSON, "sha256": A9_14_SHA256},
                          "A9.17 ORBIT": {"path": A9_17_JSON, "sha256": A9_17_SHA256}},
            "rule": inspect.cleandoc(design_states.__doc__), "n_states": len(out), "states": out}


def _design_states_text() -> str:
    _CACHE.clear()
    return json.dumps(design_states(), indent=1) + "\n"


# Verbatim sentence of the A9.17 ORBIT decision that the v2 set implements (from A9_17_MD, item 2).
A9_17_ORBIT_QUOTE = ("Keep the atmosphere/design-state envelope broad enough until DRDO, the spacecraft ICD, or the PDR "
                     "mission definition supplies the real inclination and LTAN.")


def design_states_v2() -> dict:
    """S9.8 design-state set v2 (A9.17 ORBIT broad envelope), derived from the frozen dataset only.

    Candidate pool, for each scenario x altitude node: every doy, longitude and local-time grid node x every integer
    geodetic latitude -90..90 deg (V2_LAT_DEG; contains all 19 latitude nodes, poles included; off-node latitudes are
    evaluated with the accessor's latitude interpolation and carry its recorded error). There is no latitude bound: the
    pool does not depend on mission_env.sso_inclination_deg or on any inclination / LTAN, so it covers every inclination
    0-180 deg and every LTAN (inclination and LTAN are TBD from the official mission ICD; the 96.3 deg / dawn-dusk
    mission_env orbit is CODE_DEFAULT / PARAMETRIC and is not used here). The measured effect of a finer latitude step
    on the extrema is recorded under lat_refinement_sensitivity.
    Selection rule (as v1): for every scenario x altitude node, NOMINAL (state of median density), the max/min of rho,
    x_O, x_N2, x_O2, T, and LST_PEAK / LST_TROUGH (median-density state at the local time whose lat/lon/season-mean
    density is highest / lowest); envelope extrema over all scenarios and altitudes. The mission nominal scenario is
    ECSS long-term moderate. Identical states are merged with all their labels.
    """
    L = load()
    out = _select_design_states_v2(L, V2_LAT_DEG)
    v1_sha = L["meta"].get("design_states_file", {}).get("sha256")
    return {"design_state_set_id": DESIGN_V2_ID, "version": "v2", "dataset_id": DATASET_ID,
            "dataset_sha256": L["meta"]["sha256"], "latitude_band_deg": [LAT_DEG[0], LAT_DEG[-1]],
            "latitude_pool_step_deg": V2_LAT_STEP_DEG, "lat_refinement_sensitivity": _lat_refinement_sensitivity(L),
            "nominal_scenario": NOMINAL_SCENARIO,
            "orbit_basis": {"status": "BROAD_ENVELOPE (inclination / LTAN TBD from the official mission ICD)",
                            "requirement_input": False,
                            "inclination_deg": "any (0-180): every geodetic latitude -90..90 deg (1 deg step) is in "
                                               "the pool",
                            "local_time": "all local times (LTAN-agnostic)",
                            "code_default_orbit": "mission_env 96.3 deg / dawn-dusk is " + ORBIT_STATUS + "; not used "
                                                  "to bound this set",
                            "real_orbit": "TBD from DRDO / spacecraft ICD / PDR mission definition; once supplied, a new "
                                          "dataset / design-state version narrows the envelope"},
            "supersedes": {"file": os.path.basename(DESIGN_PATH), "sha256": v1_sha,
                           "relation": "v1 is kept immutable (CLAUDE.md rule 1; A9.17 WINDS keeps v1 immutable). Its "
                                       "candidate pool is bounded at |lat| <= reachable_lat_max_deg() (~83.75 deg) of "
                                       "the CODE_DEFAULT SSO family, so it does not cover inclinations between ~83.75 "
                                       "and ~96.25 deg or polar orbits; v2 is the broad-envelope set for new use"},
            "authority": {"A9.14 S9.8 OD3": {"path": A9_14_JSON, "sha256": A9_14_SHA256},
                          "A9.17 ORBIT": {"path": A9_17_JSON, "sha256": A9_17_SHA256, "decision_key": "ORBIT",
                                          "answer": "ORBIT_INCLINATION_LTAN_TBD_FROM_OFFICIAL_MISSION_ICD",
                                          "verbatim": {"path": A9_17_MD, "sha256": A9_17_MD_SHA256,
                                                       "quote": A9_17_ORBIT_QUOTE}}},
            "producer": DESIGN_V2_COMMAND,
            "rule": inspect.cleandoc(design_states_v2.__doc__), "n_states": len(out), "states": out}


def _design_states_v2_text() -> str:
    _CACHE.clear()
    return json.dumps(design_states_v2(), indent=1) + "\n"


def _design_v2_record(text: str) -> dict:
    return {"file": os.path.basename(DESIGN_V2_PATH), "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "producer": "design_states_v2() on this dataset (A9.14 S9.8 OD3; A9.17 ORBIT broad envelope)",
            "command": DESIGN_V2_COMMAND, "status": "CURRENT design-state set (broad envelope)",
            "authority": {"path": A9_17_JSON, "sha256": A9_17_SHA256, "decision_key": "ORBIT"}}


def write_design_states_v2() -> dict:
    """Write the v2 design-state file and record it in the manifest. Deterministic and idempotent; refuses to overwrite
    an existing v2 file whose content differs (that is a new version, CLAUDE.md rule 1). The dataset is not touched."""
    meta = json.load(open(JSON_PATH))
    read_csv_bytes(meta)                                    # hash-verified dataset (fail closed)
    text = _design_states_v2_text()
    if os.path.exists(DESIGN_V2_PATH):
        if open(DESIGN_V2_PATH, "rb").read() != text.encode():
            raise RuntimeError(f"{DESIGN_V2_PATH} exists with different content; a changed design-state set is a new "
                               "version, not an overwrite (CLAUDE.md rule 1)")
    else:
        with open(DESIGN_V2_PATH, "w", newline="\n") as f:
            f.write(text)
    meta["design_states_file_v2"] = _design_v2_record(text)
    _write_json(meta)
    return meta


def load_design_states(version: str = "v2") -> dict:
    """A frozen design-state set, hash-verified against the dataset metadata. ``version="v2"`` (default) is the broad
    envelope set (all latitudes, all local times; A9.17 ORBIT). ``version="v1"`` is the immutable v1 set bounded by
    the CODE_DEFAULT / PARAMETRIC SSO latitude (~83.75 deg); it is kept for traceability only."""
    meta = load()["meta"]
    if version == "v2":
        path, rec = DESIGN_V2_PATH, meta.get("design_states_file_v2")
    elif version == "v1":
        path, rec = DESIGN_PATH, meta.get("design_states_file")
    else:
        raise ValueError(f"design-state version {version!r} unknown (v1, v2)")
    if not os.path.exists(path):
        raise _missing_data_error()
    if rec is None:
        raise RuntimeError(f"design-state {version} is not recorded in {JSON_PATH}; run {DESIGN_V2_COMMAND}")
    raw = open(path, "rb").read()
    if hashlib.sha256(raw).hexdigest() != rec["sha256"]:
        raise RuntimeError(f"design-states file {version} altered (sha256 mismatch)")
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
    Weights, where given, must be finite and >= 0, and a fully weighted set must have a positive sum (else ValueError).
    """
    states = list(states)
    if not states:
        raise ValueError("statewise_quantifier: no states supplied; an empty set cannot satisfy a requirement")
    if not requirement_id:
        raise ValueError("requirement_id is required")
    weights = [st.get("weight") for st in states]
    if any(w is not None for w in weights):
        for st, w in zip(states, weights):
            if w is None:
                continue
            if isinstance(w, (bool, np.bool_)) or not isinstance(w, (int, float, np.floating, np.integer)) \
                    or not math.isfinite(float(w)) or float(w) < 0.0:
                raise ValueError(f"state {st.get('state_id')!r}: weight must be a finite number >= 0, got {w!r}")
        if all(w is not None for w in weights) and not sum(float(w) for w in weights) > 0.0:
            raise ValueError("statewise_quantifier: state weights sum to 0; no orbit average can be formed")
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
    orbit_avg = None
    if not errors and all(w is not None for w in weights):
        W = sum(float(w) for w in weights)
        orbit_avg = sum(float(w) * p["margin"] for w, p in zip(weights, per)) / W
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


def _check_subset_record(raw: bytes) -> dict:
    lines = raw.decode().splitlines()[1:]
    idx = _check_subset_indices(len(lines))
    sub = "\n".join(lines[i] for i in idx) + "\n"
    return {"stride": CHECK_STRIDE, "n_rows": len(idx), "sha256": hashlib.sha256(sub.encode()).hexdigest()}


def check() -> dict:
    """Verify file hash + metadata, then recompute the deterministic subset with pymsis and compare bytes/hashes."""
    import pymsis
    if not (os.path.exists(GZ_PATH) and os.path.exists(JSON_PATH)):
        raise _missing_data_error()
    meta = json.load(open(JSON_PATH))
    gz = open(GZ_PATH, "rb").read()
    raw = gzip.decompress(gz)
    problems, notes = [], []
    sha = hashlib.sha256(raw).hexdigest()
    if sha != meta["sha256"]:
        problems.append(f"csv sha256 {sha} != metadata {meta['sha256']}")
    gz_sha = hashlib.sha256(gz).hexdigest()
    cont = meta.get("container", {})
    if gz_sha != cont.get("sha256") or len(gz) != cont.get("bytes"):
        problems.append(f"container sha256/bytes {gz_sha}/{len(gz)} != metadata {cont.get('sha256')}/{cont.get('bytes')}")
    if len(raw) != meta.get("bytes"):
        problems.append("uncompressed CSV byte count differs from the metadata")
    if os.path.exists(LEGACY_CSV_PATH):
        problems.append(f"legacy uncompressed copy {LEGACY_CSV_PATH} present (one canonical .csv.gz only)")
    if _gzip_bytes(raw) != gz:
        msg = "re-encoding the CSV with GZIP_SPEC does not reproduce the stored container bytes"
        if zlib.ZLIB_VERSION == cont.get("zlib_version"):
            problems.append(msg)
        else:   # different zlib build: identity is the uncompressed sha256 (checked above); record, do not fail
            notes.append(f"{msg} (zlib {zlib.ZLIB_VERSION} here vs {cont.get('zlib_version')} recorded)")
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
    v2_raw = open(DESIGN_V2_PATH, "rb").read() if os.path.exists(DESIGN_V2_PATH) else b""
    v2_rec = meta.get("design_states_file_v2") or {}
    if hashlib.sha256(v2_raw).hexdigest() != v2_rec.get("sha256"):
        problems.append("design-states v2 file hash differs from the metadata (or file / record missing)")
    elif not problems:
        if _design_states_v2_text().encode() != v2_raw:
            problems.append("design states v2 do not reproduce byte-identically from the frozen dataset")
        if {k: v for k, v in v2_rec.items() if k != "sha256"} != \
                {k: v for k, v in json.loads(json.dumps(_design_v2_record(""))).items() if k != "sha256"}:
            problems.append("design_states_file_v2 record differs from the module definition")
    if regen_sha != rec["sha256"]:
        problems.append("recomputed subset hash differs from the recorded subset hash")
    expected = _metadata(raw, gz, meta["row_count"])
    for k in ("dataset_id", "file", "sha256_definition", "bytes_definition", "distribution", "columns", "grid",
              "drivers", "authority", "build_command", "interpolation", "domain", "units", "open_items",
              "not_provided", "orbit_coverage"):
        if json.loads(json.dumps(expected[k])) != meta.get(k):
            problems.append(f"metadata field {k} differs from the module definition")
    if meta.get("dropped_species", {}).get("in_rho") != DROPPED_IN_RHO:
        problems.append("dropped_species.in_rho differs from DROPPED_IN_RHO")
    if meta.get("errata") != json.loads(json.dumps(list(ERRATA))):
        problems.append("errata record differs from the module definition")
    rc = _rho_composition_check()
    rec_rc = meta.get("rho_composition_check") or {}
    if any(rc[k] != json.loads(json.dumps(rec_rc.get(k))) for k in ("method", "points", "n_points", "in_rho",
                                                                     "threshold_amu")) \
            or any(abs(v - rec_rc.get("implied_mass_amu", {}).get(k, float("inf"))) > 0.01
                   for k, v in rc["implied_mass_amu"].items()):
        problems.append("rho composition check does not reproduce the recorded one")
    if {k: rc["in_rho"][k] for k in DROPPED_IN_RHO} != DROPPED_IN_RHO:
        problems.append(f"rho composition regression contradicts DROPPED_IN_RHO: {rc['in_rho']}")
    exp_c = {k: v for k, v in expected["container"].items() if k not in ("sha256", "bytes", "zlib_version")}
    if any(cont.get(k) != json.loads(json.dumps(v)) for k, v in exp_c.items()):
        problems.append("container record differs from GZIP_SPEC")
    return {"ok": not problems, "problems": problems, "notes": notes, "subset_rows": len(stored),
            "subset_sha256": regen_sha, "csv_sha256": sha, "container_sha256": gz_sha}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["build"]:
        meta = build()
        print(f"{GZ_PATH} rows={meta['row_count']} csv_bytes={meta['bytes']} csv_sha256={meta['sha256']} "
              f"gz_bytes={meta['container']['bytes']} gz_sha256={meta['container']['sha256']}")
        return 0
    if argv[:1] in (["check"], ["--check"]):
        r = check()
        print(("OK " if r["ok"] else "FAIL ") + json.dumps({k: v for k, v in r.items() if k != "ok"}))
        return 0 if r["ok"] else 1
    if argv[:1] == ["correct-metadata"]:
        meta = correct_metadata()
        print(f"{JSON_PATH}: errata {[e['id'] for e in meta['errata']]} applied; csv sha256 {meta['sha256']} unchanged; "
              f"container {meta['container']['file']} sha256 {meta['container']['sha256']}")
        return 0
    if argv[:1] == ["design-states-v2"]:
        meta = write_design_states_v2()
        r = meta["design_states_file_v2"]
        print(f"{DESIGN_V2_PATH}: sha256 {r['sha256']} (dataset csv sha256 {meta['sha256']} unchanged)")
        return 0
    print("usage: python -m abep_sim.atmosphere_orbit build | check | correct-metadata | design-states-v2",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
