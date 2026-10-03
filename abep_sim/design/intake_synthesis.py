"""F1 intake geometry synthesis (owner directive A9.7, lane fo_a9_7_f1_intake_synthesis).

New design-synthesis code. It CALLS abep_sim.intake_tpmc (frozen TPMC response surface and direct TPMC),
abep_sim.atmosphere (frozen NRLMSIS 2.1 dataset) and abep_sim.constants; it never modifies them and is not wired into
archengine, so golden benchmarks cannot move.

What it computes, per geometry candidate (A, d, L/d, phi), surface-state scenario (alpha, scattering kernel),
pointing angle theta, atmospheric species s in {O, N2, O2} and orbit state (altitude, F10.7):
  eta_c        collection efficiency as intake_tpmc defines it (forward transmission into the plenum per incident
               free-stream flux on the aperture A): eta_c = phi * eta_open * cos(theta)
  C_D          intake-face drag coefficient referenced to the FULL ram aperture area A (open + solid face) and to the
               free-stream dynamic pressure q = 1/2 rho V^2; drag D = q * A * C_D (intake face only, not the spacecraft)
  K_back       Clausing transmission of one channel for thermal molecules entering from the plenum side (intake_tpmc)
  CR_passive   passive number-density compression n_plenum / n_inf from the TPMC flux balance (zero net collection)
  m_intake     geometric mass model (see mass_model): TBD for the nominal design (wall thickness, coating and support
               fraction have no evidence); a labelled parametric structural case is reported beside it
  mdot_s       forward (captured) mass flow per species, mdot_s = eta_c,s * rho_s * V * A

Rules implemented here (A9.7, CLAUDE.md rules 1, 3, 6, 10):
  * The frozen response surface (abep_sim/data/intake_surface_v1.*) is used ONLY at an exact grid node AND at its
    build state (200 km, F10.7 150, orbit-averaged). Everything else goes to the direct TPMC
    (intake_tpmc.intake_response, bounded particle count, deterministic seed, statistical uncertainty reported).
    The surface is never interpolated across the atmosphere and never extrapolated.
  * TBD evidence inputs are never replaced by assumed values to obtain an optimum. alpha (surface state) is a scenario
    axis, not an optimisation variable; the reference feed pressure p_ref is a parametric sweep; the structural mass
    inputs are TBD and mass dominance is decided on geometric quantities that are valid for ANY positive structural
    parameters.
  * Hard constraints fail closed (non-converged TPMC -> MODEL_ERROR; intake-face drag above the RFP thrust maximum).
  * The output is a Pareto set (non-dominated filter), never a single optimum, winner or PASS.

Orbit states (A9.14 S9.8 OD3 / A9.13 S6.14 OQ-F4-05 / A9.17 ORBIT / A9.21 EXTERNAL_INPUTS):
  * The REQUIRED state set is the versioned frozen design-state set atmosphere_msis21_orbit_v1_design_states_v2
    (``required_states()``; 196 states: per ECSS scenario x altitude node the median-density NOMINAL state, the
    max / min of rho, x_O, x_N2, x_O2, T, the local-time density peak / trough, plus the envelope extrema). It is pinned
    by sha256 (DESIGN_STATE_SET_SHA256) and cross-checked against the dataset manifest; a missing, altered or
    inconsistent file refuses (fail closed, no fallback to the five orbit-averaged states).
  * The set is a BROAD envelope over every inclination (0-180 deg) and every LTAN: inclination and LTAN are not
    specified (A9.21: the old 96.3 deg dawn-dusk code default is not mission truth). Every output carries
    ORBIT_BASIS_LABEL; nothing here is a mission-ICD orbit.
  * The free-stream speed at a design state is the circular inertial orbital speed at its altitude (V_REL_BASIS):
    the set carries no relative velocity, and Earth co-rotation / thermospheric winds depend on the TBD inclination.
    This is the convention F1 always used (orbit-averaged dataset: V_rel = V_orb).
  * DESIGN_STATE (200 km, F10.7 150, orbit-averaged atmosphere_msis21_v1) stays the DESIGN-CASE REFERENCE POINT
    only: the frozen intake surface's build state (the only state where the surface may be used), the design-case
    view, the off-axis node and the downstream transient reference. It is not a member of the required set; it is
    also kept in ``envelope_states()`` (feasibility there can only remove candidates, never add).
  * The frozen surface never covers a design state (built at one orbit-averaged state): every design-state point is
    direct TPMC with registered crc32 seeds; nothing is interpolated or extrapolated.
  * The previous five-state set (h200_f150 + four alt x F10.7 corners) is recorded as history only
    (HISTORY_FIVE_STATE_SET).
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
import zlib
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from ..atmosphere import atmosphere, orbital_velocity
from ..constants import K_B, M_SPECIES
from ..intake_tpmc import IntakeGeometry, clausing_transmission, frozen_surface_path, intake_response
from . import engineering_constraints as ec

SCHEMA = "f1_intake_synthesis_v1"
SPECIES = ("O", "N2", "O2")                      # the species carried by the frozen atmosphere (He/H/Ar/N dropped)
KERNELS = ("maxwell", "cll")                     # gas-surface kernels the TPMC and the frozen surface support
SURFACE_BUILD_STATE = (200.0, 150.0)             # intake_surface_v1.json: "NRLMSIS 2.1, 200 km, F10.7=150, orbit-averaged"
DEFAULT_GEOMETRY = IntakeGeometry()              # code defaults (T_wall, structural defaults); read, never changed
T_WALL_K = DEFAULT_GEOMETRY.T_wall_K             # the frozen surface was built with this wall temperature
K_BACK_N = inspect.signature(clausing_transmission).parameters["n"].default   # particles intake_response uses for K_back
UNRESOLVED_TOL = 1e-3                            # intake_tpmc convergence criterion (converged <=> unresolved <= 1e-3)

# Aluminium 6061-T6 density, open datasheet (see REFERENCES["REF-6061T6-DATASHEET"]); equals abep_sim.materials Al6061.
RHO_AL6061_KG_M3 = 2700.0


REFERENCES = {
    "REF-6061T6-DATASHEET": {
        "citation": "Aluminum 6061-T6 material datasheet (Alliance, allianceorg.com), 'Physical Properties: Density 2.70 g/cc "
                    "0.0975 lb/in^3'",
        "url": "https://www.allianceorg.com/pdfs/alumext/6061t6.pdf",
        "accessed": "2026-10-01 (open PDF, read via WebFetch; text extracted locally)",
        "retrieved_sha256": "84b09413ec656a8be202beb53275a1cff117d55b3f1cdd14d302a4fdc07047e7",
        "evidence_level": 5,
        "quantity_type": "as reported (secondary compilation / supplier datasheet; primary measurement not inspected)",
        "note": "agrees with abep_sim/materials.py DB['Al6061'].density = 2700 (literature-class prior, no citation there)",
    },
    "REF-FEED-STATE-CLOSURE": {
        "citation": "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json, design_axes.setpoint_ladder_Pa "
                    "and owner question DI-1.6 (valve-outlet pressure setpoint)",
        "note": "PROPOSED ladder (evidence class assumed); used here only as the parametric p_ref sweep, never as a value",
    },
    "REF-RFP-CONSTANTS": {
        "citation": "abep_sim/constants.py RFP.thrust_min_mN / thrust_max_mN (RFP envelope as recorded in CLAUDE.md; verify "
                    "against the official RFP)",
    },
    "REF-SURFACE": {
        "citation": "abep_sim/data/intake_surface_v1.{csv,json} (frozen TPMC response surface, CLAUDE.md rule 1)",
    },
    "REF-ATMOSPHERE": {
        "citation": "abep_sim/data/atmosphere_msis21_v1.{csv,json} (frozen NRLMSIS 2.1, orbit-averaged, ap 15)",
    },
}


# --------------------------------------------------------------------------------------------------------------------
# orbit states
# --------------------------------------------------------------------------------------------------------------------
class IntakeInputError(ValueError):
    """An F1 evaluation input is outside the supported domain (refused, never repaired or silently remapped)."""


def validate_point(L_over_d, phi, alpha, theta_deg, scattering, species) -> None:
    """Domain of the F1 evaluator (SW-04): scattering in KERNELS (intake_tpmc treats any other string as Maxwell, so an
    unknown kernel would be a silent fallback, rule 3), species in SPECIES, finite L/d > 0, 0 < phi <= 1,
    0 <= alpha <= 1, finite |theta| < 90 deg."""
    if scattering not in KERNELS:
        raise IntakeInputError(f"scattering kernel {scattering!r} not in {KERNELS}")
    if species not in SPECIES:
        raise IntakeInputError(f"species {species!r} not in {SPECIES}")

    def _f(name, v):
        if isinstance(v, bool) or not isinstance(v, (int, float, np.floating, np.integer)) or \
                not math.isfinite(float(v)):
            raise IntakeInputError(f"{name}={v!r} must be a finite number")
        return float(v)
    if not _f("L_over_d", L_over_d) > 0.0:
        raise IntakeInputError(f"L_over_d={L_over_d!r} must be > 0")
    if not 0.0 < _f("phi", phi) <= 1.0:
        raise IntakeInputError(f"phi={phi!r} must be in (0, 1]")
    if not 0.0 <= _f("alpha", alpha) <= 1.0:
        raise IntakeInputError(f"alpha={alpha!r} must be in [0, 1]")
    if not abs(_f("theta_deg", theta_deg)) < 90.0:
        raise IntakeInputError(f"theta_deg={theta_deg!r} must satisfy |theta| < 90")


@dataclass(frozen=True)
class OrbitState:
    alt_km: float
    f107: float

    def __post_init__(self):
        for k in ("alt_km", "f107"):
            v = getattr(self, k)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or \
                    not float(v) > 0.0:
                raise IntakeInputError(f"OrbitState.{k}={v!r} must be finite and > 0")

    @property
    def id(self) -> str:
        """Exact-value identifier (CLAUDE.md rule 5, consolidated verification SW-05): h200_f150 for integer states,
        h200.4_f150 otherwise, so caches keyed on it are pure functions of the evaluated point."""
        return f"h{float(self.alt_km):.12g}_f{float(self.f107):.12g}"

    @property
    def key(self) -> tuple:
        return (float(self.alt_km), float(self.f107))

    def atm(self) -> dict:
        a = atmosphere(float(self.alt_km), float(self.f107))
        if not str(a.get("source", "")).startswith("NRLMSIS 2.1 frozen scenario"):
            # CLAUDE.md rule 3: no silent fallback to live MSIS or the built-in table
            raise RuntimeError(f"atmosphere for {self.id} is not the frozen NRLMSIS dataset: {a.get('source')}")
        return a


DESIGN_STATE = OrbitState(*SURFACE_BUILD_STATE)
DESIGN_STATE_ROLE = ("DESIGN_CASE_REFERENCE_POINT: frozen intake surface build state (200 km, F10.7 150, orbit-averaged "
                     "atmosphere_msis21_v1); design-case view, off-axis node and downstream transient reference only; "
                     "NOT a member of the required design-state set (A9.14 S9.8)")

# Previous orbit-state set (A9.7 .. A9.20), kept as history only: replaced by the frozen design-state set v2 (OD3).
HISTORY_FIVE_STATE_SET = {
    "state_ids": ["h200_f150", "h180_f70", "h180_f230", "h230_f70", "h230_f230"],
    "basis": "h200_f150 (surface build state) + 180 / 230 km x F10.7 70 / 230 corners of the orbit-averaged "
             "atmosphere_msis21_v1 (hand-picked; no local time, latitude or season)",
    "status": "SUPERSEDED_BY_DESIGN_STATE_SET_V2 (A9.14 S9.8 OD3; A9.13 S6.14 OQ-F4-05)",
}


# --------------------------------------------------------------------------------------------------------------------
# frozen design-state set v2 (A9.14 S9.8 OD3; A9.17 ORBIT broad envelope)
# --------------------------------------------------------------------------------------------------------------------
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DESIGN_STATE_SET_ID = "atmosphere_msis21_orbit_v1_design_states_v2"
DESIGN_STATE_SET_REL = "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json"
DESIGN_STATE_SET_SHA256 = "60073e214cf5edb92d7eacf70be1491ad29ff72f19db0ef3b96a4b30da6f4049"
DESIGN_STATE_DATASET_ID = "atmosphere_msis21_orbit_v1"
DESIGN_STATE_DATASET_SHA256 = "c0ce282e99695be8cae0834270c5b9ff7853033255665abda7ec18c307566164"
DESIGN_STATE_MANIFEST_REL = "abep_sim/data/atmosphere_msis21_orbit_v1.json"
DESIGN_STATE_PRODUCER = "python -m abep_sim.atmosphere_orbit design-states-v2"
# A9.22 G5: mission_domain.altitude_km (frozen domain constraint from the engineering-constraints seam; no RFP parsing)
MISSION_DOMAIN_ALTITUDE_KM = ec.MISSION_DOMAIN_ALTITUDE_KM
ORBIT_BASIS_LABEL = "BROAD_ENVELOPE_ALL_INCLINATIONS_ALL_LTAN_NOT_MISSION_ICD"
ORBIT_BASIS_NOTE = ("inclination and LTAN are not specified (A9.21 EXTERNAL_INPUTS: not in the RFP; the old 96.3 deg "
                    "dawn-dusk code default is never mission truth; A9.17 ORBIT: TBD from DRDO / spacecraft ICD / PDR "
                    "mission definition). The design-state set v2 covers every latitude -90..90 deg and every local "
                    "time, so it does not depend on an orbit assumption; it is a broad design envelope, not a mission "
                    "trajectory. A registered orbit narrows it in a new version.")
V_REL_BASIS = ("V_ORB_INERTIAL_CIRCULAR: free-stream speed = circular inertial orbital speed sqrt(mu / (R_E + h)) at "
               "the state altitude (abep_sim.atmosphere.orbital_velocity, the F1 convention since A9.7); Earth "
               "co-rotation and thermospheric winds are NOT included (they depend on the TBD inclination / LTAN; "
               "the set carries no relative velocity)")
COMPOSITION_BASIS = ("rho = total NRLMSIS 2.1 mass density of the state (all species); mass fractions of O, N2, O2 "
                     "renormalised over those three (He, Ar, N dropped from the composition, as abep_sim.atmosphere "
                     "does); n = rho / m_mean")
SURFACE_COVERAGE_AT_DESIGN_STATES = ("NOT_COVERED: intake_surface_v1 was built at one orbit-averaged state (200 km, "
                                     "F10.7 150); every design-state point is direct TPMC with registered seeds")


class DesignStateSetError(RuntimeError):
    """The frozen design-state set is missing, altered or inconsistent (fail closed; no fallback state set)."""


@dataclass(frozen=True)
class DesignState:
    """One state of the frozen design-state set v2 (a point of the orbit-resolved frozen NRLMSIS dataset)."""
    state_id: str
    alt_km: float
    scenario: str
    f107: float
    f107a: float
    ap: float
    lat_deg: float
    lst_h: float
    lon_deg: float
    doy: float
    rho_kg_m3: float
    n_O_m3: float
    n_N2_m3: float
    n_O2_m3: float
    T_K: float
    labels: tuple
    evaluation: str
    interp_max_rel_err_rho: float | None
    nominal_mission_scenario: bool
    required: bool

    @property
    def id(self) -> str:
        return self.state_id

    @property
    def key(self) -> tuple:
        return ("ds2", self.state_id)

    @property
    def role(self) -> str:
        return "REQUIRED_DESIGN_STATE"

    def atm(self) -> dict:
        m = {"O": self.n_O_m3 * M_SPECIES["O"], "N2": self.n_N2_m3 * M_SPECIES["N2"],
             "O2": self.n_O2_m3 * M_SPECIES["O2"]}
        tot = sum(m.values())
        fO, fN2, fO2 = m["O"] / tot, m["N2"] / tot, m["O2"] / tot
        m_mean = 1.0 / (fO / M_SPECIES["O"] + fN2 / M_SPECIES["N2"] + fO2 / M_SPECIES["O2"])
        rho = self.rho_kg_m3
        n = rho / m_mean
        V = orbital_velocity(self.alt_km)
        return {"alt_km": self.alt_km, "f107": self.f107, "f107a": self.f107a, "ap": self.ap, "rho": rho, "fO": fO,
                "fN2": fN2, "fO2": fO2, "m_mean": m_mean, "n": n, "T": self.T_K, "V": V, "flux_kg_m2_s": rho * V,
                "p_ambient_Pa": n * K_B * self.T_K, "n_O": rho * fO / M_SPECIES["O"], "state_id": self.state_id,
                "source": f"{DESIGN_STATE_SET_ID} sha256 {DESIGN_STATE_SET_SHA256} state {self.state_id}",
                "V_basis": V_REL_BASIS, "orbit_basis": ORBIT_BASIS_LABEL}

    def record(self) -> dict:
        """Compact provenance record of the state (for the builders' coverage sections)."""
        return {"state_id": self.state_id, "scenario": self.scenario, "alt_km": self.alt_km, "lat_deg": self.lat_deg,
                "lst_h": self.lst_h, "lon_deg": self.lon_deg, "doy": self.doy, "f107": self.f107, "ap": self.ap,
                "labels": list(self.labels), "evaluation": self.evaluation,
                "interp_max_rel_err_rho": self.interp_max_rel_err_rho,
                "nominal_mission_scenario": self.nominal_mission_scenario}


def _sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@lru_cache(maxsize=1)
def load_design_state_set() -> dict:
    """The frozen design-state set v2, verified fail closed: file present, sha256 == DESIGN_STATE_SET_SHA256, the
    dataset manifest records the same file hash and the same dataset sha256, set id / count / unique ids, every state
    carries the dataset provenance and lies in the mission-domain altitude band (mission_domain.altitude_km). Read directly (no atmosphere_orbit import:
    the orbit dataset is repository-only data, A9.17 DATA_SIZE)."""
    path = os.path.join(DATA_DIR, os.path.basename(DESIGN_STATE_SET_REL))
    man = os.path.join(DATA_DIR, os.path.basename(DESIGN_STATE_MANIFEST_REL))
    for p in (path, man):
        if not os.path.exists(p):
            raise DesignStateSetError(f"{p} missing: the design layer needs the frozen design-state set "
                                      f"{DESIGN_STATE_SET_ID} (repository-only data); no fallback state set")
    h = _sha256_file(path)
    if h != DESIGN_STATE_SET_SHA256:
        raise DesignStateSetError(f"{DESIGN_STATE_SET_REL} sha256 {h} != pinned {DESIGN_STATE_SET_SHA256} (a changed "
                                  "design-state set is a new version: re-pin deliberately)")
    with open(man) as f:
        meta = json.load(f)
    rec = meta.get("design_states_file_v2") or {}
    if rec.get("sha256") != DESIGN_STATE_SET_SHA256 or rec.get("file") != os.path.basename(DESIGN_STATE_SET_REL):
        raise DesignStateSetError("dataset manifest does not record the pinned design-state set v2")
    if meta.get("sha256") != DESIGN_STATE_DATASET_SHA256:
        raise DesignStateSetError("dataset manifest sha256 differs from the pinned orbit dataset")
    with open(path) as f:
        d = json.load(f)
    if d.get("design_state_set_id") != DESIGN_STATE_SET_ID or d.get("version") != "v2":
        raise DesignStateSetError("design-state set id / version mismatch")
    if d.get("dataset_id") != DESIGN_STATE_DATASET_ID or d.get("dataset_sha256") != DESIGN_STATE_DATASET_SHA256:
        raise DesignStateSetError("design-state set was produced from a different dataset")
    st = d.get("states") or []
    if d.get("n_states") != len(st) or not st:
        raise DesignStateSetError("design-state set n_states inconsistent with its state list")
    ids = [x.get("state_id") for x in st]
    if len(set(ids)) != len(ids) or any(not isinstance(i, str) or not i for i in ids):
        raise DesignStateSetError("design-state ids missing or not unique")
    lo, hi = MISSION_DOMAIN_ALTITUDE_KM
    for x in st:
        if DESIGN_STATE_DATASET_SHA256 not in str(x.get("source", "")):
            raise DesignStateSetError(f"state {x['state_id']} does not carry the dataset provenance")
        if not lo <= float(x["alt_km"]) <= hi:
            raise DesignStateSetError(f"state {x['state_id']} outside the mission-domain altitude band "
                                      f"{MISSION_DOMAIN_ALTITUDE_KM}")
        if not isinstance(x.get("required"), bool):
            raise DesignStateSetError(f"state {x['state_id']} has no boolean 'required' flag")
        for k in ("rho_kg_m3", "n_O_m3", "n_N2_m3", "n_O2_m3", "T_K"):
            v = x.get(k)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or not v > 0:
                raise DesignStateSetError(f"state {x['state_id']}: {k}={v!r} is not a finite positive number")
    return d


def _design_state(x: dict) -> DesignState:
    return DesignState(
        state_id=x["state_id"], alt_km=float(x["alt_km"]), scenario=x["scenario"], f107=float(x["f107"]),
        f107a=float(x["f107a"]), ap=float(x["ap"]), lat_deg=float(x["lat_deg"]), lst_h=float(x["lst_h"]),
        lon_deg=float(x["lon_deg"]), doy=float(x["doy"]), rho_kg_m3=float(x["rho_kg_m3"]), n_O_m3=float(x["n_O_m3"]),
        n_N2_m3=float(x["n_N2_m3"]), n_O2_m3=float(x["n_O2_m3"]), T_K=float(x["T_K"]), labels=tuple(x["labels"]),
        evaluation=x["evaluation"], interp_max_rel_err_rho=x.get("interp_max_rel_err_rho"),
        nominal_mission_scenario=bool(x["nominal_mission_scenario"]), required=bool(x["required"]))


@lru_cache(maxsize=1)
def required_states() -> tuple:
    """Every state the design-state set flags required (all 196 in v2), in the file's order."""
    st = tuple(_design_state(x) for x in load_design_state_set()["states"] if x["required"])
    if not st:
        raise DesignStateSetError("design-state set flags no required state")
    return st


def envelope_states() -> tuple:
    """States the F1 envelope view and the F4 / F7 / F8 statewise checks evaluate: the design-case reference point
    first (index 0, the downstream design-state convention), then every required design state."""
    return (DESIGN_STATE,) + required_states()


@lru_cache(maxsize=1)
def state_index() -> dict:
    """state id -> state object (design reference + required design states)."""
    return {s.id: s for s in envelope_states()}


def state_alt_km(state_id: str) -> float:
    """Altitude of an evaluated state id (fail closed on an unknown id)."""
    st = state_index().get(state_id)
    if st is None:
        raise IntakeInputError(f"unknown orbit / design state id {state_id!r}")
    return float(st.alt_km)


def state_role(state_id: str) -> str:
    """DESIGN_CASE_REFERENCE_POINT or REQUIRED_DESIGN_STATE (fail closed on an unknown id)."""
    if state_id == DESIGN_STATE.id:
        return DESIGN_STATE_ROLE.split(":")[0]
    st = state_index().get(state_id)
    if st is None:
        raise IntakeInputError(f"unknown orbit / design state id {state_id!r}")
    return st.role


def design_state_set_record() -> dict:
    """Provenance of the evaluated state set, carried into every design-layer output (F1, F4, F7 / F8)."""
    d = load_design_state_set()
    req = required_states()
    labels: dict = {}
    for s in req:
        for lab in s.labels:
            k = lab.split("[")[0]
            labels[k] = labels.get(k, 0) + 1
    return {
        "design_state_set_id": DESIGN_STATE_SET_ID, "path": DESIGN_STATE_SET_REL, "sha256": DESIGN_STATE_SET_SHA256,
        "dataset_id": DESIGN_STATE_DATASET_ID, "dataset_sha256": DESIGN_STATE_DATASET_SHA256,
        "manifest": DESIGN_STATE_MANIFEST_REL, "producer": DESIGN_STATE_PRODUCER,
        "n_required_states": len(req),
        "n_nominal_mission_scenario_states": sum(1 for s in req if s.nominal_mission_scenario),
        "nominal_scenario": d.get("nominal_scenario"), "label_counts": dict(sorted(labels.items())),
        "scenarios": sorted({s.scenario for s in req}), "altitudes_km": sorted({s.alt_km for s in req}),
        "orbit_basis_label": ORBIT_BASIS_LABEL, "orbit_basis_note": ORBIT_BASIS_NOTE,
        "orbit_basis_in_set": d.get("orbit_basis"), "v_rel_basis": V_REL_BASIS, "composition_basis": COMPOSITION_BASIS,
        "surface_coverage": SURFACE_COVERAGE_AT_DESIGN_STATES,
        "authority": {"A9.14 S9.8 OD3": "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json",
                      "A9.13 S6.14 OQ-F4-05": "docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_"
                                              "decisions.json",
                      "A9.17 ORBIT": "docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json",
                      "A9.21 EXTERNAL_INPUTS": "docs/decisions/OD_2026_10_02_A9_21_open_items_and_hardware_programme_"
                                               "owner_decisions.json"},
        "design_case_reference_point": {"state_id": DESIGN_STATE.id, "role": DESIGN_STATE_ROLE},
        "evaluated_state_order": "index 0 = design-case reference point, then the required states in file order",
        "subset_used": False,
        "subset_note": "no subsampling: the set designates no design subset; every required state is evaluated",
        "history": HISTORY_FIVE_STATE_SET,
    }


def __getattr__(name):
    # lazy module attributes: loading the design-state set at import would make every import of the design layer
    # depend on repository-only data; the access itself still fails closed when the set is missing
    if name == "ENVELOPE_STATES":
        return envelope_states()
    if name == "REQUIRED_STATES":
        return required_states()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def frozen_atmosphere_grid():
    """(alt_km values, f107 values) of the frozen NRLMSIS dataset."""
    import pandas as pd
    p = os.path.join(os.path.dirname(frozen_surface_path()), "atmosphere_msis21_v1.csv")
    df = pd.read_csv(p)
    return sorted(float(x) for x in df.alt_km.unique()), sorted(float(x) for x in df.f107.unique())


def speed_ratio(atm: dict, species: str) -> float:
    """Molecular speed ratio S = V / sqrt(2 k T / m_s) of the free stream for one species."""
    return atm["V"] / math.sqrt(2.0 * K_B * atm["T"] / M_SPECIES[species])


def speed_ratio_bracket_check(states=None):
    """Where the free-stream speed ratios, rho*V and rho*V^2 reach their extremes over the evaluated required design
    states, and which design-state labels those states carry (the set holds the T and rho extrema of every scenario x
    altitude node by construction, and V depends on altitude only). Returned as a record; never asserted silently."""
    states = tuple(states) if states is not None else required_states()
    out = {"n_states": len(states), "state_set": DESIGN_STATE_SET_ID, "quantities": {}}
    qty = {f"S_{sp}": (lambda a, sp=sp: speed_ratio(a, sp)) for sp in SPECIES}
    qty["rhoV_kg_m2_s"] = lambda a: a["flux_kg_m2_s"]
    qty["q_Pa"] = lambda a: 0.5 * a["rho"] * a["V"] ** 2
    atms = {s.id: s.atm() for s in states}
    lab = {s.id: list(getattr(s, "labels", ())) for s in states}
    for name, f in qty.items():
        vals = [(f(atms[s.id]), s.id) for s in states]
        lo, hi = min(vals), max(vals)
        out["quantities"][name] = {"min": lo[0], "argmin": lo[1], "argmin_labels": lab[lo[1]], "max": hi[0],
                                   "argmax": hi[1], "argmax_labels": lab[hi[1]]}
    return out


# --------------------------------------------------------------------------------------------------------------------
# frozen surface (exact node lookup only)
# --------------------------------------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _surface():
    import pandas as pd
    df = pd.read_csv(frozen_surface_path())
    meta = json.load(open(frozen_surface_path().replace(".csv", ".json")))
    return df, meta


def surface_meta() -> dict:
    return _surface()[1]


def surface_grid() -> dict:
    return {k: [float(v) for v in vals] for k, vals in surface_meta()["grid"].items()}


def surface_node(scattering, species, L_over_d, phi, alpha, theta_deg):
    """Exact frozen-surface row or None. Never interpolates: a point between nodes is not 'covered'."""
    df, _ = _surface()
    m = ((df.scattering == scattering) & (df.species == species) & np.isclose(df.L_over_d, L_over_d, rtol=0, atol=1e-12)
         & np.isclose(df.phi, phi, rtol=0, atol=1e-12) & np.isclose(df.alpha, alpha, rtol=0, atol=1e-12)
         & np.isclose(df.theta_deg, theta_deg, rtol=0, atol=1e-12))
    rows = df[m]
    if len(rows) == 0:
        return None
    if len(rows) > 1:
        raise RuntimeError("frozen surface has duplicate nodes")
    return rows.iloc[0].to_dict()


def surface_covers(state, scattering, species, L_over_d, phi, alpha, theta_deg) -> bool:
    """Only the orbit-averaged build state itself (an OrbitState equal to SURFACE_BUILD_STATE) can be covered; a design
    state of the orbit-resolved set never is (different atmosphere; never interpolated or extrapolated)."""
    return (isinstance(state, OrbitState) and (state.alt_km, state.f107) == SURFACE_BUILD_STATE
            and surface_node(scattering, species, L_over_d, phi, alpha, theta_deg) is not None)


# --------------------------------------------------------------------------------------------------------------------
# statistics helpers
# --------------------------------------------------------------------------------------------------------------------
def binomial_se(p: float, n: int) -> float:
    """Agresti-Coull standard error of a Bernoulli fraction (finite even at p = 0 or 1)."""
    x = p * n
    pt = (x + 2.0) / (n + 4.0)
    return math.sqrt(pt * (1.0 - pt) / (n + 4.0))


def stable_seed(*parts, base: int = 0) -> int:
    return (zlib.crc32("|".join(str(p) for p in parts).encode()) + int(base)) % (2 ** 31 - 1)


# --------------------------------------------------------------------------------------------------------------------
# species-level physics point
# --------------------------------------------------------------------------------------------------------------------
@dataclass
class SpeciesPoint:
    state_id: str
    species: str
    L_over_d: float
    phi: float
    alpha: float
    theta_deg: float
    scattering: str
    source: str                  # FROZEN_SURFACE | DIRECT_TPMC
    eta_c: float
    eta_c_se: float
    C_D_row: float               # as intake_tpmc reports it (normalised by the MIXTURE dynamic pressure of the run atm)
    C_D_species: float           # intrinsic per-species C_D = C_D_row * m_mean(run atm) / m_s (finding F1-01)
    C_D_species_se: float
    K_back: float
    K_back_se: float
    CR_passive: float
    CR_passive_se: float
    unresolved_fraction: float
    converged: bool
    n_particles: int
    seed: int | None
    m_mean_run_kg: float

    def as_row(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def _c_solid_row(atm: dict, m: float, theta_deg: float, T_wall_K: float) -> float:
    """Front solid-face drag coefficient term of intake_tpmc.intake_response (same expression, same normalisation).
    Pinned to intake_response by tests/test_design_f1_intake.py::test_phi_reconstruction_matches_intake_response."""
    V = atm.get("V_rel", atm["V"])
    Vz = V * math.cos(math.radians(theta_deg))
    dp_solid = m * Vz + m * math.sqrt(math.pi * K_B * T_wall_K / (2 * m))
    return atm["n"] * Vz * dp_solid / (0.5 * atm["rho"] * V * V)


def _direct_job(job):
    """One phi = 1 direct TPMC run (process-pool worker; pure function of its arguments and seed)."""
    atm, L_over_d, alpha, theta_deg, scattering, species, n, seed = job
    g = IntakeGeometry(area_m2=DEFAULT_GEOMETRY.area_m2, d_mm=DEFAULT_GEOMETRY.d_mm, L_over_d=float(L_over_d), phi=1.0)
    return intake_response(g, atm, float(alpha), float(theta_deg), n=n, seed=seed, scattering=scattering,
                           species_mass=M_SPECIES[species])


def design_workers() -> int:
    """Worker processes for the direct-TPMC prefill (ABEP_DESIGN_WORKERS, default: CPU count). Results do not depend
    on it: every run is seeded from its own evaluation point."""
    v = os.environ.get("ABEP_DESIGN_WORKERS")
    return max(1, int(v)) if v else max(1, os.cpu_count() or 1)


class Evaluator:
    """Species-level TPMC evaluator with an explicit coverage rule (frozen surface at exact node + build state,
    direct TPMC otherwise) and a cache keyed on the exact evaluation point (CLAUDE.md rule 5)."""

    def prefill_direct(self, points, workers: int | None = None) -> int:
        """Run the direct-TPMC cores of ``points`` [(state, L/d, alpha, theta, kernel, species)] in a process pool and
        store them under exactly the keys / seeds direct_core uses (a cached point is not re-run). Identical to the
        serial path (each run is a pure function of its seeded inputs); returns the number of new runs."""
        jobs, keys, seen = [], [], set()
        for state, ld, al, th, kern, sp in points:
            validate_point(ld, 1.0, al, th, kern, sp)
            n = self.n_direct
            seed = stable_seed(state.id, ld, al, th, kern, sp, n, base=self.seed_base)
            key = (state.key, float(ld), float(al), float(th), kern, sp, n, seed)
            if key in self._direct_cache or key in seen:
                continue
            seen.add(key)
            keys.append(key)
            jobs.append((self.atm(state), float(ld), float(al), float(th), kern, sp, n, seed))
        if not jobs:
            return 0
        w = design_workers() if workers is None else max(1, int(workers))
        if w == 1:
            res = [_direct_job(j) for j in jobs]
        else:
            import multiprocessing as mp
            with ProcessPoolExecutor(max_workers=w, mp_context=mp.get_context("fork")) as ex:
                res = list(ex.map(_direct_job, jobs, chunksize=max(1, len(jobs) // (8 * w))))
        for key, j, r in zip(keys, jobs, res):
            self._direct_cache[key] = {"r": r, "n": j[6], "seed": j[7]}
        self.direct_runs += len(jobs)
        return len(jobs)

    def __init__(self, n_direct: int = 3000, seed_base: int = 0, cd_rel_sd_at_n: tuple | None = None,
                 force_direct: bool = False):
        self.n_direct = int(n_direct)
        self.seed_base = int(seed_base)
        # (relative SD of C_D per run, n at which it was measured) from replicate calibration; None -> not available
        self.cd_rel_sd_at_n = cd_rel_sd_at_n
        self.force_direct = force_direct
        self._direct_cache: dict = {}
        self._cache: dict = {}
        self._atm: dict = {}
        self.direct_runs = 0

    def atm(self, state: OrbitState) -> dict:
        if state.key not in self._atm:
            self._atm[state.key] = state.atm()
        return self._atm[state.key]

    def _cd_se(self, C: float, n: int) -> float:
        if self.cd_rel_sd_at_n is None:
            return float("nan")
        rel, n0 = self.cd_rel_sd_at_n
        return abs(C) * rel * math.sqrt(n0 / n)

    def direct_core(self, state: OrbitState, L_over_d, alpha, theta_deg, scattering, species, n=None, seed=None):
        """One direct TPMC run at phi = 1 (pure channel response). phi enters intake_response only linearly / not at all
        (eta_c = phi eta_open cos(theta); C_D = phi C_open + (1 - phi) C_solid; CR_passive and K_back phi-independent)."""
        validate_point(L_over_d, 1.0, alpha, theta_deg, scattering, species)
        n = int(n or self.n_direct)
        seed = stable_seed(state.id, L_over_d, alpha, theta_deg, scattering, species, n, base=self.seed_base) if seed is None else seed
        key = (state.key, float(L_over_d), float(alpha), float(theta_deg), scattering, species, n, seed)
        if key not in self._direct_cache:
            atm = self.atm(state)
            g = IntakeGeometry(area_m2=DEFAULT_GEOMETRY.area_m2, d_mm=DEFAULT_GEOMETRY.d_mm, L_over_d=float(L_over_d), phi=1.0)
            r = intake_response(g, atm, float(alpha), float(theta_deg), n=n, seed=seed, scattering=scattering,
                                species_mass=M_SPECIES[species])
            self.direct_runs += 1
            self._direct_cache[key] = {"r": r, "n": n, "seed": seed}
        return self._direct_cache[key]

    def point(self, state: OrbitState, L_over_d, phi, alpha, theta_deg, scattering, species) -> SpeciesPoint:
        validate_point(L_over_d, phi, alpha, theta_deg, scattering, species)
        key = (state.key, float(L_over_d), float(phi), float(alpha), float(theta_deg), scattering, species)
        if key in self._cache:
            return self._cache[key]
        m_s = M_SPECIES[species]
        atm = self.atm(state)
        cos_t = math.cos(math.radians(theta_deg))
        if not self.force_direct and surface_covers(state, scattering, species, L_over_d, phi, alpha, theta_deg):
            row = surface_node(scattering, species, L_over_d, phi, alpha, theta_deg)
            n = int(surface_meta()["n_per_point"])
            eta_open = float(row["eta_open"])
            eta_c = float(row["eta_c"])
            K = float(row["K_back"])
            CR = float(row["CR_passive"])
            C_row = float(row["C_D"])
            unresolved = float(row["unresolved_fraction"])
            converged = bool(row["converged"]) and unresolved <= UNRESOLVED_TOL
            src, seed = "FROZEN_SURFACE", None
        else:
            d = self.direct_core(state, L_over_d, alpha, theta_deg, scattering, species)
            r, n, seed = d["r"], d["n"], d["seed"]
            eta_open = float(r["eta_open"])
            eta_c = float(phi) * eta_open * cos_t
            K = float(r["K_back"])
            CR = float(r["CR_passive"])
            C_open = float(r["C_D"])               # phi = 1 run: pure open-area term
            C_row = float(phi) * C_open + (1.0 - float(phi)) * _c_solid_row(atm, m_s, theta_deg, DEFAULT_GEOMETRY.T_wall_K)
            unresolved = float(r["unresolved_fraction"])
            converged = bool(r["converged"])
            src = "DIRECT_TPMC"
        eta_se = float(phi) * cos_t * binomial_se(eta_open, n)
        K_se = binomial_se(K, K_BACK_N)
        eo_rel = binomial_se(eta_open, n) / eta_open if eta_open > 0 else float("inf")
        CR_se = CR * math.sqrt(eo_rel ** 2 + (K_se / K) ** 2) if K > 0 else float("inf")
        C_sp = C_row * atm["m_mean"] / m_s
        p = SpeciesPoint(state.id, species, float(L_over_d), float(phi), float(alpha), float(theta_deg), scattering, src,
                         eta_c, eta_se, C_row, C_sp, self._cd_se(C_sp, n), K, K_se, CR, CR_se, unresolved, converged, n,
                         seed, atm["m_mean"])
        self._cache[key] = p
        return p


# --------------------------------------------------------------------------------------------------------------------
# geometry candidates and mass model
# --------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class GeometryCandidate:
    area_m2: float
    d_mm: float
    L_over_d: float
    phi: float

    def __post_init__(self):
        for k in ("area_m2", "d_mm", "L_over_d"):
            v = getattr(self, k)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or \
                    not float(v) > 0.0:
                raise IntakeInputError(f"GeometryCandidate.{k}={v!r} must be finite and > 0")
        if isinstance(self.phi, bool) or not isinstance(self.phi, (int, float)) or \
                not math.isfinite(float(self.phi)) or not 0.0 < float(self.phi) <= 1.0:
            raise IntakeInputError(f"GeometryCandidate.phi={self.phi!r} must be in (0, 1]")

    @property
    def id(self) -> str:
        return f"A{self.area_m2:g}_d{self.d_mm:g}_Ld{self.L_over_d:g}_phi{self.phi:g}"

    @property
    def node_id(self) -> str:
        return f"Ld{self.L_over_d:g}_phi{self.phi:g}"

    @property
    def depth_m(self) -> float:
        return self.L_over_d * self.d_mm * 1e-3

    @property
    def n_cells(self) -> float:
        R = self.d_mm * 1e-3 / 2
        return self.phi * self.area_m2 / (math.pi * R * R)

    @property
    def wall_area_m2(self) -> float:
        """Shared-wall honeycomb wall area, the same expression intake_tpmc uses (n_cells * 2 pi R L * 0.5) = 2 phi A L/d.
        Independent of d at fixed L/d."""
        return 2.0 * self.phi * self.area_m2 * self.L_over_d


@dataclass(frozen=True)
class StructuralCase:
    """A labelled structural parameter set for the geometric mass model. NONE of these is a sourced design value."""
    id: str
    wall_thickness_mm: float | None
    wall_density_kg_m3: float | None
    coating_thickness_um: float | None
    coating_density_kg_m3: float | None
    support_mass_frac: float | None
    label: str
    status: str


STRUCTURAL_NOMINAL = StructuralCase("SC-NOMINAL", None, RHO_AL6061_KG_M3, None, None, None,
                                    "nominal design: wall thickness, coating and support fraction have no evidence", "TBD")
STRUCTURAL_CODE_DEFAULT = StructuralCase(
    "SC-CODE-DEFAULT", DEFAULT_GEOMETRY.wall_thickness_mm, DEFAULT_GEOMETRY.wall_density_kg_m3,
    DEFAULT_GEOMETRY.coating_thickness_um, DEFAULT_GEOMETRY.coating_density_kg_m3, DEFAULT_GEOMETRY.support_mass_frac,
    "PARAMETRIC_SENSITIVITY_CASE: abep_sim.intake_tpmc.IntakeGeometry code defaults (wall 0.15 mm Al, 2 um coating at "
    "2200 kg/m3, supports 35 %); only the Al density is cited; the rest is assumed (no cited source); budgeting only "
    "(A9.13 S6.1 F1Q-02): never a CBE, frozen intake mass or structural qualification; sourced structural definition "
    "required before LOCK-1",
    "PARAMETRIC_SENSITIVITY_CASE")


# A9.13 S6.1 / F1Q-02 (owner answer BUDGETING_ASSUMPTION_SOURCED_BEFORE_LOCK_1): the honeycomb structural inputs (wall
# material / thickness, AO coating / density, support fraction) are a labelled PARAMETRIC_SENSITIVITY for budgeting
# only. No intake mass computed here is ever a CBE, a frozen intake mass or a structural qualification statement; a
# sourced buildable structural definition is mandatory before LOCK-1.
F1Q02_AUTHORITY = "A9.13 S6.1 / F1Q-02 (BUDGETING_ASSUMPTION_SOURCED_BEFORE_LOCK_1)"
F1Q02_LABEL = "PARAMETRIC_SENSITIVITY"
F1Q02_USE = "BUDGETING_ONLY"
F1Q02_FORBIDDEN_USES = ("CBE", "FROZEN_INTAKE_MASS", "STRUCTURAL_QUALIFICATION")
F1Q02_LOCK1 = "SOURCED_STRUCTURAL_DEFINITION_REQUIRED_BEFORE_LOCK_1"
F1Q02_STRUCTURAL_INPUTS = ("wall_material", "wall_thickness_mm", "coating_ao", "coating_density_kg_m3",
                           "support_mass_frac")


class IntakeMassUseError(ValueError):
    """An intake structural mass was requested for a use the owner forbade (F1Q-02: budgeting only)."""


def f1q02_label() -> dict:
    """The F1Q-02 label carried by every intake structural-mass value and every consumer roll-up of it."""
    return {"label": F1Q02_LABEL, "use": F1Q02_USE, "not": list(F1Q02_FORBIDDEN_USES),
            "lock1_condition": F1Q02_LOCK1, "structural_inputs": list(F1Q02_STRUCTURAL_INPUTS),
            "authority": F1Q02_AUTHORITY,
            "statement": "parametric budgeting sensitivity only: never a CBE, a frozen intake mass or a structural "
                         "qualification statement; sourced structural definition required before LOCK-1"}


def require_budgeting_use(use: str) -> None:
    """Fail closed (F1Q-02): an intake structural mass may only be used as a budgeting sensitivity."""
    if use != F1Q02_USE:
        raise IntakeMassUseError(f"intake structural mass requested for use {use!r}: {F1Q02_AUTHORITY} allows "
                                 f"{F1Q02_USE} only (never {', '.join(F1Q02_FORBIDDEN_USES)}); "
                                 f"{F1Q02_LOCK1}")


def require_f1q02_label(rec) -> None:
    """Fail closed: a consumer roll-up may carry an intake structural mass only with the F1Q-02 label attached."""
    lab = (rec or {}).get("f1q02") if isinstance(rec, dict) else None
    if not lab or lab.get("label") != F1Q02_LABEL or lab.get("use") != F1Q02_USE or \
            lab.get("lock1_condition") != F1Q02_LOCK1:
        raise IntakeMassUseError("intake structural mass without the F1Q-02 PARAMETRIC_SENSITIVITY / BUDGETING_ONLY "
                                 "label (never a CBE, frozen intake mass or structural qualification)")


def intake_mass(c: GeometryCandidate, sc: StructuralCase, use: str = F1Q02_USE) -> dict:
    """Geometric intake mass (same expression as intake_tpmc.intake_response without filter). Returns value None and
    status TBD when any structural input is TBD (never filled with an assumed value). Every record carries the F1Q-02
    label (PARAMETRIC_SENSITIVITY, budgeting only); any other ``use`` is refused (IntakeMassUseError)."""
    require_budgeting_use(use)
    out = {"structural_case": sc.id, "wall_area_m2": c.wall_area_m2, "frontal_area_m2": c.area_m2,
           "f1q02": f1q02_label()}
    if sc.wall_density_kg_m3 is not None:
        out["substrate_mass_per_mm_wall_kg"] = c.wall_area_m2 * 1e-3 * sc.wall_density_kg_m3
    vals = (sc.wall_thickness_mm, sc.wall_density_kg_m3, sc.coating_thickness_um, sc.coating_density_kg_m3, sc.support_mass_frac)
    if any(v is None for v in vals):
        out.update({"m_intake_kg": None, "status": "TBD",
                    "missing": [n for n, v in zip(("wall_thickness_mm", "wall_density_kg_m3", "coating_thickness_um",
                                                   "coating_density_kg_m3", "support_mass_frac"), vals) if v is None]})
        return out
    m_sub = c.wall_area_m2 * sc.wall_thickness_mm * 1e-3 * sc.wall_density_kg_m3
    m_coat = (c.wall_area_m2 + c.area_m2) * sc.coating_thickness_um * 1e-6 * sc.coating_density_kg_m3
    out.update({"m_intake_kg": (m_sub + m_coat) * (1 + sc.support_mass_frac), "status": sc.status})
    return out


# --------------------------------------------------------------------------------------------------------------------
# candidate metrics
# --------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Scenario:
    alpha: float
    scattering: str

    @property
    def id(self) -> str:
        return f"{self.scattering}_a{self.alpha:g}"


def candidate_state_metrics(ev: Evaluator, c: GeometryCandidate, state: OrbitState, sc: Scenario,
                            theta_deg: float = 0.0) -> dict:
    """All per-species and mixture metrics of one candidate at one state / scenario / pointing angle."""
    atm = ev.atm(state)
    V = atm["V"]
    q = 0.5 * atm["rho"] * V * V
    sp_out = {}
    eta_mix = eta_mix_var = cd_mix = cd_mix_var = 0.0
    n_p = 0.0
    n_p_var = 0.0
    converged = True
    unresolved_max = 0.0
    sources = set()
    for s in SPECIES:
        p = ev.point(state, c.L_over_d, c.phi, sc.alpha, theta_deg, sc.scattering, s)
        w = atm[{"O": "fO", "N2": "fN2", "O2": "fO2"}[s]]          # mass fraction
        rho_s = atm["rho"] * w
        n_s = rho_s / M_SPECIES[s]
        mdot = p.eta_c * rho_s * V * c.area_m2
        n_plen = n_s * p.CR_passive
        sp_out[s] = {
            "mass_fraction_freestream": w, "n_freestream_m3": n_s,
            "eta_c": p.eta_c, "eta_c_se": p.eta_c_se,
            "C_D_species": p.C_D_species, "C_D_species_se": p.C_D_species_se,
            "K_back": p.K_back, "K_back_se": p.K_back_se,
            "CR_passive": p.CR_passive, "CR_passive_se": p.CR_passive_se,
            "mdot_captured_kgps": mdot, "mdot_captured_se_kgps": p.eta_c_se * rho_s * V * c.area_m2,
            "p_passive_Pa": n_plen * K_B * T_WALL_K, "p_passive_se_Pa": n_s * p.CR_passive_se * K_B * T_WALL_K,
            "source": p.source, "converged": p.converged, "unresolved_fraction": p.unresolved_fraction,
        }
        eta_mix += w * p.eta_c
        eta_mix_var += (w * p.eta_c_se) ** 2
        cd_mix += w * p.C_D_species
        cd_mix_var += (w * p.C_D_species_se) ** 2
        n_p += n_plen
        n_p_var += (n_s * p.CR_passive_se) ** 2
        converged &= p.converged
        unresolved_max = max(unresolved_max, p.unresolved_fraction)
        sources.add(p.source)
    for s in SPECIES:
        sp_out[s]["x_plenum_passive"] = sp_out[s]["p_passive_Pa"] / (n_p * K_B * T_WALL_K)
    mdot_tot = sum(v["mdot_captured_kgps"] for v in sp_out.values())
    p_pass = n_p * K_B * T_WALL_K
    return {
        "candidate": c.id, "state": state.id, "scenario": sc.id, "theta_deg": theta_deg,
        "species": sp_out,
        "eta_c_mix": eta_mix, "eta_c_mix_se": math.sqrt(eta_mix_var),
        "C_D_mix": cd_mix, "C_D_mix_se": math.sqrt(cd_mix_var),
        "drag_N": q * c.area_m2 * cd_mix, "drag_se_N": q * c.area_m2 * math.sqrt(cd_mix_var),
        "mdot_captured_kgps": mdot_tot,
        "mdot_captured_se_kgps": math.sqrt(sum(v["mdot_captured_se_kgps"] ** 2 for v in sp_out.values())),
        "CR_passive_mix": n_p / atm["n"], "CR_passive_mix_se": math.sqrt(n_p_var) / atm["n"],
        "p_passive_Pa": p_pass, "p_passive_se_Pa": math.sqrt(n_p_var) * K_B * T_WALL_K,
        "burden_per_Pa": 1.0 / p_pass if p_pass > 0 else float("inf"),
        "burden_per_Pa_se": (math.sqrt(n_p_var) * K_B * T_WALL_K) / p_pass ** 2 if p_pass > 0 else float("inf"),
        "converged": converged, "unresolved_max": unresolved_max, "sources": sorted(sources),
    }


def compressor_burden(p_ref_Pa: float, p_passive_Pa: float) -> float:
    """Lower bound on the pressure ratio the compressor must supply: p_ref / p_passive. p_passive is the zero-net-flow
    plenum state; any net delivered flow needs p_plenum = b p_passive (b < 1, net flow (1 - b) mdot_fwd), so the real
    ratio is p_ref / (b p_passive) >= this bound. No max(., 1) floor (keeps the ranking invariant under p_ref)."""
    return p_ref_Pa / p_passive_Pa


def net_flow_fraction(p_plenum_Pa: float, p_passive_Pa: float) -> float:
    """Free-molecular plenum balance: net/forward = 1 - p_plenum / p_passive (per species with the partial pressures)."""
    return 1.0 - p_plenum_Pa / p_passive_Pa


def off_axis_sensitivity(ev: Evaluator, c: GeometryCandidate, sc: Scenario, state: OrbitState = DESIGN_STATE,
                         theta_hi: float = 5.0) -> dict:
    """Relative collection loss per degree of pointing error, secant 0 -> theta_hi (largest theta on the frozen grid)."""
    m0 = candidate_state_metrics(ev, c, state, sc, 0.0)
    m1 = candidate_state_metrics(ev, c, state, sc, theta_hi)
    e0, e1 = m0["eta_c_mix"], m1["eta_c_mix"]
    s = (e0 - e1) / (theta_hi * e0)
    se = math.sqrt(m0["eta_c_mix_se"] ** 2 + m1["eta_c_mix_se"] ** 2) / (theta_hi * e0)
    return {"rel_eta_loss_per_deg": s, "rel_eta_loss_per_deg_se": se, "theta_hi_deg": theta_hi,
            "dCD_per_deg": (m1["C_D_mix"] - m0["C_D_mix"]) / theta_hi,
            "converged": m0["converged"] and m1["converged"], "state": state.id}


def surface_state_sensitivity(ev: Evaluator, c: GeometryCandidate, sc: Scenario, alphas, state: OrbitState) -> dict:
    """|d eta_c / d alpha| / eta_c at the scenario alpha, secant over the neighbouring alpha nodes (central inside,
    one-sided at the ends). Also d ln CR_passive / d alpha."""
    alphas = sorted(alphas)
    if len(alphas) < 2:
        raise ValueError("surface-state sensitivity needs at least two alpha nodes")
    i = alphas.index(sc.alpha)
    lo, hi = alphas[max(i - 1, 0)], alphas[min(i + 1, len(alphas) - 1)]
    m = candidate_state_metrics(ev, c, state, sc)
    mlo = candidate_state_metrics(ev, c, state, Scenario(lo, sc.scattering))
    mhi = candidate_state_metrics(ev, c, state, Scenario(hi, sc.scattering))
    da = hi - lo
    s = abs(mhi["eta_c_mix"] - mlo["eta_c_mix"]) / (da * m["eta_c_mix"])
    se = math.sqrt(mhi["eta_c_mix_se"] ** 2 + mlo["eta_c_mix_se"] ** 2) / (da * m["eta_c_mix"])
    dlncr = (math.log(mhi["CR_passive_mix"]) - math.log(mlo["CR_passive_mix"])) / da
    return {"rel_eta_per_alpha": s, "rel_eta_per_alpha_se": se, "dlnCR_dalpha": dlncr, "alpha_lo": lo, "alpha_hi": hi,
            "converged": m["converged"] and mlo["converged"] and mhi["converged"], "state": state.id}


# --------------------------------------------------------------------------------------------------------------------
# Pareto filter
# --------------------------------------------------------------------------------------------------------------------
# objective key, sense, uncertainty key (None = exact)
OBJECTIVES = (
    ("mdot_captured_kgps", "max", "mdot_captured_se_kgps"),
    ("drag_N", "min", "drag_se_N"),
    ("CR_passive_mix", "max", "CR_passive_mix_se"),
    ("wall_area_m2", "min", None),
    ("frontal_area_m2", "min", None),
    ("off_axis_rel_eta_loss_per_deg", "min", "off_axis_rel_eta_loss_per_deg_se"),
    ("surface_state_rel_eta_per_alpha", "min", "surface_state_rel_eta_per_alpha_se"),
    ("compressor_burden_per_Pa", "min", "compressor_burden_per_Pa_se"),
)


def _dominates(a: dict, b: dict, objectives) -> bool:
    better = False
    for k, sense, _ in objectives:
        va, vb = a[k], b[k]
        if sense == "max":
            va, vb = -va, -vb
        if va > vb:
            return False
        if va < vb:
            better = True
    return better


def _significantly_dominates(a: dict, b: dict, objectives, z: float = 2.0) -> bool:
    """a dominates b on the means AND is better by more than z combined standard errors in at least one objective."""
    if not _dominates(a, b, objectives):
        return False
    for k, sense, sek in objectives:
        va, vb = a[k], b[k]
        diff = (va - vb) if sense == "max" else (vb - va)
        se = 0.0 if sek is None else math.sqrt(a.get(sek, 0.0) ** 2 + b.get(sek, 0.0) ** 2)
        if not math.isfinite(se):
            continue
        if diff > z * se and diff > 0:
            return True
    return False


def pareto_filter(rows: list[dict], objectives=OBJECTIVES, z: float = 2.0) -> dict:
    """Non-dominated filter over FEASIBLE rows (row['feasible'] is True). Every row gets a status:
       INFEASIBLE                  failed a hard constraint or MODEL_ERROR (reasons kept)
       NONDOMINATED                no feasible row dominates it on the mean values
       NONDOMINATED_WITHIN_NOISE   dominated on the means, but no dominator is better by > z combined SE in any objective
       DOMINATED                   dominated by at least one row significantly
    Pareto dominance: a dominates b iff a is no worse in every objective and strictly better in at least one. Ties
    (identical vectors) never dominate each other. O(N^2); no scalarisation, no weights, no selection."""
    def _finite_row(r):
        def _fin(v):
            try:
                return v is not None and not isinstance(v, bool) and math.isfinite(float(v))
            except (TypeError, ValueError):
                return False
        return all(_fin(r.get(k)) for k, _s, _u in objectives)
    # OPT-04: a feasible row with a non-finite objective is NOT_EVALUATED and never enters dominance (fail closed)
    feas = [r for r in rows if r.get("feasible") and _finite_row(r)]
    status = {}
    for r in rows:
        if not r.get("feasible"):
            status[r["candidate"]] = "INFEASIBLE"
            continue
        if not _finite_row(r):
            status[r["candidate"]] = "NOT_EVALUATED_NON_FINITE_OBJECTIVE"
            continue
        doms = [o for o in feas if o is not r and _dominates(o, r, objectives)]
        if not doms:
            status[r["candidate"]] = "NONDOMINATED"
        elif any(_significantly_dominates(o, r, objectives, z) for o in doms):
            status[r["candidate"]] = "DOMINATED"
        else:
            status[r["candidate"]] = "NONDOMINATED_WITHIN_NOISE"
    return status


# --------------------------------------------------------------------------------------------------------------------
# IF-A1 record for the filter stage (F2)
# --------------------------------------------------------------------------------------------------------------------
IF_A1_RECORD_SCHEMA = {
    "record": "f1_if_a1_intake_exit_v1",
    "interface": "IF-A1 intake -> filter (docs/interfaces/UPSTREAM_ICD.md); consumers abep_sim/design/filter_stage.py "
                 "(F2-IF-01) and abep_sim/design/plenum_feed.py (F4-ID-01)",
    "plane": "intake exit plane = back face of the channel array (plenum side), upstream of any filter",
    "fields_per_species": {
        "mdot_fwd_kgps": "forward-transmitted (captured) mass flow eta_c,s rho_s V A; the delivered flow when the plenum is "
                         "pumped to p_s << p_passive,s (UPPER BOUND on net flow)",
        "mdot_fwd_se_kgps": "TPMC statistical standard error",
        "p_passive_Pa": "zero-net-flow (stagnation) partial pressure n_s,inf CR_passive,s k T; UPPER BOUND on the plenum "
                        "partial pressure",
        "T_K": "plenum gas temperature = TPMC wall temperature T_wall (thermalisation assumed by the TPMC flux balance; "
               "code default, evidence class assumed; ICD G-07 two-temperature issue)",
        "x_mole_passive": "mole fraction of the zero-net-flow plenum state",
        "K_back": "single-channel Clausing back-transmission (for the filter/plenum backflow coupling)",
        "net_flow_law": "mdot_net,s(p_s) = mdot_fwd,s (1 - p_s / p_passive,s) (free-molecular plenum balance)",
    },
    "not_included": "no filter is applied (intake_tpmc's placeholder filter fields are never used here; the filter is "
                    "F2's model); no intake-drag or spacecraft fields (they go to F7, not IF-A1)",
}


def if_a1_record(ev: Evaluator, c: GeometryCandidate, state: OrbitState, sc: Scenario, theta_deg: float = 0.0) -> dict:
    m = candidate_state_metrics(ev, c, state, sc, theta_deg)
    sp = {s: {"mdot_fwd_kgps": v["mdot_captured_kgps"], "mdot_fwd_se_kgps": v["mdot_captured_se_kgps"],
              "p_passive_Pa": v["p_passive_Pa"], "p_passive_se_Pa": v["p_passive_se_Pa"], "T_K": T_WALL_K,
              "x_mole_passive": v["x_plenum_passive"], "K_back": v["K_back"], "eta_c": v["eta_c"]}
          for s, v in m["species"].items()}
    return {"record": IF_A1_RECORD_SCHEMA["record"], "candidate": c.id, "state": state.id, "scenario": sc.id,
            "theta_deg": theta_deg, "species": sp, "mdot_fwd_total_kgps": m["mdot_captured_kgps"],
            "p_passive_total_Pa": m["p_passive_Pa"], "T_K": T_WALL_K, "converged": m["converged"],
            "status": "MODEL_DERIVED_INVESTIGATION_HYPOTHESIS" if m["converged"] else "MODEL_ERROR",
            "sources": m["sources"]}


# --------------------------------------------------------------------------------------------------------------------
# study
# --------------------------------------------------------------------------------------------------------------------
@dataclass
class StudySpec:
    areas_m2: tuple = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5)
    d_mm: tuple = (5.0, 10.0, 20.0)
    L_over_d: tuple = (3.0, 5.0, 10.0, 20.0)
    phi: tuple = (0.8, 0.9)
    alphas: tuple = (0.0, 0.2, 0.5, 0.8, 1.0)
    kernels: tuple = KERNELS
    states: tuple = field(default_factory=envelope_states)   # design reference + every required design state (OD3)
    theta_hi_deg: float = 5.0
    p_ref_Pa: tuple = (0.05, 0.1, 0.2, 0.3, 0.5, 1.0)
    n_direct: int = 3000
    seed_base: int = 0
    cd_calibration_nodes: tuple = ((3.0, 0.0, "O"), (3.0, 1.0, "N2"), (20.0, 1.0, "O"), (20.0, 0.5, "O2"))
    cd_calibration_replicates: int = 5
    surface_check_nodes: tuple = ((3.0, 0.9, 1.0, "N2"), (10.0, 0.9, 0.5, "O"), (20.0, 0.8, 1.0, "O2"))

    def candidates(self):
        return [GeometryCandidate(a, d, ld, ph) for a in self.areas_m2 for d in self.d_mm for ld in self.L_over_d
                for ph in self.phi]

    def scenarios(self):
        return [Scenario(a, k) for k in self.kernels for a in self.alphas]


def cd_replicate_calibration(spec: StudySpec, state: OrbitState = DESIGN_STATE, scattering="maxwell") -> dict:
    """Relative SD of the per-run C_D from independent seeds (C_D has no closed-form SE from intake_response's
    aggregate outputs). The max over the calibration nodes is applied to every point (scaled by sqrt(n0/n))."""
    ev = Evaluator(n_direct=spec.n_direct, seed_base=spec.seed_base + 7919)
    rows = []
    for ld, al, sp in spec.cd_calibration_nodes:
        vals = []
        for k in range(spec.cd_calibration_replicates):
            seed = stable_seed("cdcal", ld, al, sp, k, base=spec.seed_base)
            r = ev.direct_core(state, ld, al, 0.0, scattering, sp, n=spec.n_direct, seed=seed)["r"]
            vals.append(r["C_D"])
        vals = np.array(vals)
        rows.append({"L_over_d": ld, "alpha": al, "species": sp, "C_D_mean_phi1": float(vals.mean()),
                     "rel_sd": float(vals.std(ddof=1) / vals.mean())})
    rel = max(r["rel_sd"] for r in rows)
    return {"state": state.id, "scattering": scattering, "n_per_run": spec.n_direct,
            "replicates": spec.cd_calibration_replicates, "nodes": rows, "rel_sd_max": rel,
            "applied_as": "C_D SE = |C_D| * rel_sd_max * sqrt(n_per_run / n) for every point (estimate; the frozen surface "
                          "carries no C_D variance)"}


def surface_reproduction_check(spec: StudySpec, ev_direct: Evaluator) -> dict:
    """Direct TPMC at the surface build state vs the frozen surface node (consistency of the atmosphere/build state and
    of the species C_D normalisation; diagnostic only)."""
    out = []
    for ld, ph, al, sp in spec.surface_check_nodes:
        row = surface_node("maxwell", sp, ld, ph, al, 0.0)
        p = ev_direct.point(DESIGN_STATE, ld, ph, al, 0.0, "maxwell", sp)
        n_s = int(surface_meta()["n_per_point"])
        se_eta = math.sqrt(p.eta_c_se ** 2 + (ph * binomial_se(float(row["eta_open"]), n_s)) ** 2)
        se_K = math.sqrt(2) * p.K_back_se
        se_cd = math.sqrt(p.C_D_species_se ** 2 + (p.C_D_species_se * math.sqrt(p.n_particles / n_s)) ** 2)
        m_mean = ev_direct.atm(DESIGN_STATE)["m_mean"]
        cd_s = float(row["C_D"]) * m_mean / M_SPECIES[sp]
        z = {"eta_c": (p.eta_c - float(row["eta_c"])) / se_eta, "K_back": (p.K_back - float(row["K_back"])) / se_K,
             "C_D_species": (p.C_D_species - cd_s) / se_cd}
        out.append({"L_over_d": ld, "phi": ph, "alpha": al, "species": sp,
                    "direct": {"eta_c": p.eta_c, "K_back": p.K_back, "C_D_species": p.C_D_species, "n": p.n_particles},
                    "surface": {"eta_c": float(row["eta_c"]), "K_back": float(row["K_back"]), "C_D_species": cd_s},
                    "z": z, "within_3sigma": all(abs(v) <= 3 for v in z.values())})
    return {"nodes": out, "all_within_3sigma": all(o["within_3sigma"] for o in out),
            "interpretation": "diagnostic: a failure would indicate a build-state or normalisation inconsistency; it never "
                              "changes a value"}


def species_c_d_recombination_bias(ev: Evaluator, L_over_d=10.0, phi=0.9, alpha=1.0, scattering="maxwell") -> dict:
    """Finding F1-01: IntakeSurface recombines species rows by mass fraction. Its C_D rows are normalised by the mixture
    q of the build atmosphere (C_D_row = (m_s / m_mean) C_D_species) and CR_passive is a number-density ratio (mole
    weighting). Quantify both against the species-consistent recombination used here."""
    atm = ev.atm(DESIGN_STATE)
    w = {"O": atm["fO"], "N2": atm["fN2"], "O2": atm["fO2"]}
    x = {s: (w[s] / M_SPECIES[s]) * atm["m_mean"] for s in SPECIES}
    pts = {s: ev.point(DESIGN_STATE, L_over_d, phi, alpha, 0.0, scattering, s) for s in SPECIES}
    cd_massweighted_rows = sum(w[s] * pts[s].C_D_row for s in SPECIES)
    cd_consistent = sum(w[s] * pts[s].C_D_species for s in SPECIES)
    cr_mass = sum(w[s] * pts[s].CR_passive for s in SPECIES)
    cr_mole = sum(x[s] * pts[s].CR_passive for s in SPECIES)
    return {"node": {"L_over_d": L_over_d, "phi": phi, "alpha": alpha, "scattering": scattering, "state": DESIGN_STATE.id},
            "C_D_IntakeSurface_convention": cd_massweighted_rows, "C_D_species_consistent": cd_consistent,
            "C_D_ratio": cd_massweighted_rows / cd_consistent,
            "CR_IntakeSurface_mass_weighted": cr_mass, "CR_mole_weighted": cr_mole, "CR_ratio": cr_mass / cr_mole,
            "mass_fractions": w, "mole_fractions": x}


def _r(v, sig=7):
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return v
    v = float(v)
    if not math.isfinite(v):
        return str(v)
    if v == 0:
        return 0.0
    return float(f"{v:.{sig}g}")


def rnd(obj, sig=7):
    if isinstance(obj, dict):
        return {k: rnd(v, sig) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [rnd(v, sig) for v in obj]
    if isinstance(obj, (np.floating,)):
        return _r(float(obj), sig)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float):
        return _r(obj, sig)
    return obj


def run_study(spec: StudySpec, progress=None) -> dict:
    """Deterministic study. Returns a plain-dict result (the builder adds governance sections)."""
    cal = cd_replicate_calibration(spec)
    ev = Evaluator(n_direct=spec.n_direct, seed_base=spec.seed_base,
                   cd_rel_sd_at_n=(cal["rel_sd_max"], spec.n_direct))
    ev_check = Evaluator(n_direct=spec.n_direct, seed_base=spec.seed_base + 104729,
                         cd_rel_sd_at_n=(cal["rel_sd_max"], spec.n_direct), force_direct=True)
    check = surface_reproduction_check(spec, ev_check)
    bias = species_c_d_recombination_bias(ev)
    # A9.22 G2: C-DRAG-RFP stays a generation filter, limit from the frozen engineering-constraints snapshot
    rfp_max_N = ec.INTAKE_DRAG_GENERATION_LIMIT_N

    # species table: every physics point evaluated (one row per node x scenario x species x state x theta)
    nodes = sorted({(c.L_over_d, c.phi) for c in spec.candidates()})
    # direct-TPMC prefill (process pool) for every state the frozen surface cannot cover (all design states): exactly
    # the points / seeds the serial loops below request, so results and direct_runs are those of the serial path
    lds = sorted({ld for ld, _ph in nodes})
    ev.prefill_direct([(st, ld, sc.alpha, 0.0, sc.scattering, s) for st in spec.states
                       if not (isinstance(st, OrbitState) and st.key == SURFACE_BUILD_STATE)
                       for sc in spec.scenarios() for ld in lds for s in SPECIES])
    if progress:
        progress(f"direct-TPMC prefill done ({ev.direct_runs} direct runs)")
    species_rows = []
    thetas_design = (0.0, spec.theta_hi_deg)
    for st in spec.states:
        for sc in spec.scenarios():
            for ld, ph in nodes:
                for th in (thetas_design if st == DESIGN_STATE else (0.0,)):
                    for s in SPECIES:
                        species_rows.append(ev.point(st, ld, ph, sc.alpha, th, sc.scattering, s).as_row())
        if progress:
            progress(f"state {st.id} done ({ev.direct_runs} direct runs)")

    # per-candidate metrics per scenario: design-case view and envelope view (worst case over states)
    unit = {}   # metrics for a 1 m^2, d-independent reference geometry per node -> scaled per candidate
    views = {"design_case": {}, "envelope": {}}
    candidate_rows = {"design_case": {}, "envelope": {}}
    cands = spec.candidates()
    for sc in spec.scenarios():
        dc_rows, env_rows = [], []
        for c in cands:
            per_state = {st.id: candidate_state_metrics(ev, c, st, sc) for st in spec.states}
            oa = off_axis_sensitivity(ev, c, sc, DESIGN_STATE, spec.theta_hi_deg)
            ss = {st.id: surface_state_sensitivity(ev, c, sc, spec.alphas, st) for st in spec.states}
            dc = per_state[DESIGN_STATE.id]
            reasons_dc, reasons_env = [], []
            if not (dc["converged"] and oa["converged"] and ss[DESIGN_STATE.id]["converged"]):
                reasons_dc.append("MODEL_ERROR: TPMC unresolved fraction > 1e-3")
            if dc["drag_N"] > rfp_max_N:
                reasons_dc.append(f"C-DRAG-RFP: intake-face drag {dc['drag_N'] * 1e3:.2f} mN > RFP thrust max "
                                  f"{ec.INTAKE_DRAG_GENERATION_LIMIT_MN:g} mN at {DESIGN_STATE.id}")
            for sid, m in per_state.items():
                if not (m["converged"] and ss[sid]["converged"]):
                    reasons_env.append(f"MODEL_ERROR at {sid}")
                if m["drag_N"] > rfp_max_N:
                    reasons_env.append(f"C-DRAG-RFP at {sid}: {m['drag_N'] * 1e3:.2f} mN")
            if not oa["converged"]:
                reasons_env.append("MODEL_ERROR: off-axis evaluation")
            base = {"candidate": c.id, "node": c.node_id, "area_m2": c.area_m2, "d_mm": c.d_mm, "L_over_d": c.L_over_d,
                    "phi": c.phi, "depth_m": c.depth_m, "n_cells": c.n_cells, "wall_area_m2": c.wall_area_m2,
                    "frontal_area_m2": c.area_m2,
                    "m_intake_nominal": intake_mass(c, STRUCTURAL_NOMINAL),
                    "m_intake_code_default_case_kg": intake_mass(c, STRUCTURAL_CODE_DEFAULT)["m_intake_kg"],
                    "off_axis_rel_eta_loss_per_deg": oa["rel_eta_loss_per_deg"],
                    "off_axis_rel_eta_loss_per_deg_se": oa["rel_eta_loss_per_deg_se"],
                    "off_axis_dCD_per_deg": oa["dCD_per_deg"]}
            r_dc = dict(base)
            r_dc.update({k: dc[k] for k in ("mdot_captured_kgps", "mdot_captured_se_kgps", "drag_N", "drag_se_N",
                                             "eta_c_mix", "eta_c_mix_se", "C_D_mix", "C_D_mix_se", "CR_passive_mix",
                                             "CR_passive_mix_se", "p_passive_Pa", "p_passive_se_Pa", "burden_per_Pa",
                                             "burden_per_Pa_se", "sources")})
            r_dc["species"] = {s: {k: v[k] for k in ("mdot_captured_kgps", "eta_c", "K_back", "CR_passive",
                                                     "C_D_species", "p_passive_Pa", "x_plenum_passive")}
                               for s, v in dc["species"].items()}
            r_dc["surface_state_rel_eta_per_alpha"] = ss[DESIGN_STATE.id]["rel_eta_per_alpha"]
            r_dc["surface_state_rel_eta_per_alpha_se"] = ss[DESIGN_STATE.id]["rel_eta_per_alpha_se"]
            r_dc["surface_state_dlnCR_dalpha"] = ss[DESIGN_STATE.id]["dlnCR_dalpha"]
            r_dc["compressor_burden_per_Pa"] = dc["burden_per_Pa"]
            r_dc["compressor_burden_per_Pa_se"] = dc["burden_per_Pa_se"]
            r_dc["compressor_burden_by_p_ref"] = {f"{pr:g}": compressor_burden(pr, dc["p_passive_Pa"]) for pr in spec.p_ref_Pa}
            r_dc["feasible"] = not reasons_dc
            r_dc["infeasible_reasons"] = reasons_dc
            dc_rows.append(r_dc)

            # envelope: worst case of every objective over the evaluated states
            def worst(key, sense):
                vals = [(m[key], sid) for sid, m in per_state.items()]
                return min(vals) if sense == "max" else max(vals)
            r_env = dict(base)
            for key, sense, sek in (("mdot_captured_kgps", "max", "mdot_captured_se_kgps"), ("drag_N", "min", "drag_se_N"),
                                    ("CR_passive_mix", "max", "CR_passive_mix_se"), ("eta_c_mix", "max", "eta_c_mix_se")):
                v, sid = worst(key, sense)
                r_env[key] = v
                r_env[sek] = per_state[sid][sek]
                r_env[f"{key}_worst_state"] = sid
            bv, bsid = worst("burden_per_Pa", "min")
            r_env["compressor_burden_per_Pa"] = bv
            r_env["compressor_burden_per_Pa_se"] = per_state[bsid]["burden_per_Pa_se"]
            r_env["compressor_burden_worst_state"] = bsid
            r_env["compressor_burden_by_p_ref"] = {f"{pr:g}": pr * bv for pr in spec.p_ref_Pa}
            sv = max((ss[sid]["rel_eta_per_alpha"], sid) for sid in ss)
            r_env["surface_state_rel_eta_per_alpha"] = sv[0]
            r_env["surface_state_rel_eta_per_alpha_se"] = ss[sv[1]]["rel_eta_per_alpha_se"]
            r_env["surface_state_rel_eta_per_alpha_worst_state"] = sv[1]
            r_env["per_state"] = {sid: {"mdot_captured_kgps": m["mdot_captured_kgps"], "drag_N": m["drag_N"],
                                        "CR_passive_mix": m["CR_passive_mix"], "eta_c_mix": m["eta_c_mix"],
                                        "p_passive_Pa": m["p_passive_Pa"], "sources": m["sources"]}
                                  for sid, m in per_state.items()}
            r_env["feasible"] = not reasons_env
            r_env["infeasible_reasons"] = reasons_env
            env_rows.append(r_env)
        for vname, rows in (("design_case", dc_rows), ("envelope", env_rows)):
            st = pareto_filter(rows)
            # p_ref invariance: recompute the burden objective for every p_ref and re-filter
            invariant = True
            for pr in spec.p_ref_Pa:
                alt = [dict(r, compressor_burden_per_Pa=pr * r["compressor_burden_per_Pa"],
                            compressor_burden_per_Pa_se=pr * r["compressor_burden_per_Pa_se"]) for r in rows]
                if pareto_filter(alt) != st:
                    invariant = False
            for r in rows:
                r["pareto_status"] = st[r["candidate"]]
            nd = [r for r in rows if r["pareto_status"] == "NONDOMINATED"]
            groups = {}
            for r in nd:
                key = (r["area_m2"], r["L_over_d"], r["phi"])
                groups.setdefault(key, []).append(r["d_mm"])
            views[vname][sc.id] = {
                "counts": {s: sum(1 for r in rows if r["pareto_status"] == s)
                           for s in ("NONDOMINATED", "NONDOMINATED_WITHIN_NOISE", "DOMINATED", "INFEASIBLE")},
                "nondominated": [r["candidate"] for r in nd],
                "nondominated_within_noise": [r["candidate"] for r in rows if r["pareto_status"] == "NONDOMINATED_WITHIN_NOISE"],
                "nondominated_groups_d_collapsed": [{"area_m2": k[0], "L_over_d": k[1], "phi": k[2], "d_mm": sorted(v)}
                                                    for k, v in sorted(groups.items())],
                "pareto_set_invariant_under_p_ref_sweep": invariant,
            }
            candidate_rows[vname][sc.id] = rows
        if progress:
            progress(f"scenario {sc.id} done")

    if_a1 = []
    for st in spec.states:
        for sc in spec.scenarios():
            for ld, ph in nodes:
                c = GeometryCandidate(1.0, DEFAULT_GEOMETRY.d_mm, ld, ph)
                rec = if_a1_record(ev, c, st, sc)
                rec["candidate"] = f"unit_area_{c.node_id}"
                rec["note"] = "per 1 m^2 of frontal area; mdot scales linearly with A, pressures/T/x do not; d-invariant"
                if_a1.append(rec)

    return {"calibration": cal, "surface_reproduction_check": check, "species_recombination_bias": bias,
            "species_rows": species_rows, "views": views, "candidate_rows": candidate_rows, "if_a1_unit_area": if_a1,
            "speed_ratio_bracket": speed_ratio_bracket_check(tuple(st for st in spec.states if st is not DESIGN_STATE)),
            "direct_runs": ev.direct_runs + ev_check.direct_runs + len(spec.cd_calibration_nodes) * spec.cd_calibration_replicates}
