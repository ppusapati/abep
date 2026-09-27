"""Thermal / life accounting framework (THL lane). Pure module; NOT wired into archengine.

Purpose: once an architecture closes on power, check whether its heat loads and life-limited parts are feasible.
This module only accounts heat and compares against sourced limits. It predicts no plasma physics, and it never
fills a missing quantity.

Contracts (single source of truth, read at run time):
  schemas/thermal_life/limits_v1.json  sourced limits and relations (evidence attributes per docs/EVIDENCE.md);
                                       records are 'sourced' or 'TBD' (a TBD record/value is refused, never defaulted)
  schemas/thermal_life/inputs_v1.json  every required input per component, its unit and the lane expected to supply it
  hallthruster_bridge/hall_map_schema_v1.json  HallMap field names/units (read, not modified)

Component names coordinate with the bus-power boundary components (BUS_POWER_COMPONENTS); that module is NOT
imported. Thermal nodes group them: 'cathode' is fed by cathode_keeper + cathode_heater.

Heat sources (equations; sources and page numbers are in limits_v1.json 'relations'):
  hall_magnet     P = I^2 R_ref r(T)/r(T_ref) + Q_ext; copper r(T) from NBS Handbook 100 (IACS linear, 0-200 C, or the
                  Roeser ratio table, -100-500 C). Constant-current drive only. The coil temperature is solved
                  self-consistently and is never extrapolated outside the copper model's domain: the result is then
                  reported as a one-sided bound.
  hall_discharge  wall ion heat  Q_i = e Gamma_i eps_i A_wall (HallMap fields wall_ion_flux_m2s, wall_ion_energy_eV);
                  wall electron heat Q_e = e Gamma_i 2 T_e,w / (1 - gamma) A_wall (Goebel & Katz 2008 Eqs. 7.3-28,
                  7.3-43, 7.3-45); anode heat P_a = 2 I_d T_e,anode (Eq. 7.3-53, accounted only). Sum <= P_d (gate).
                  Wall flux/energy gate (G11): accepted only from an ADMITTED ensemble member's Hall-map point with
                  wall_life_trustworthy (re-checked via hall_ensemble.require_admitted) or measured hardware data
                  with an evidence record; anything else raises. Credible set empty => refused today.
                  hallmap_wall_inputs binds the member id to the queried map's meta (id, commit, ion_wall_losses) and
                  records its sha256. Wall T_e and SEE yield are separate inputs: their consistency with the sheath
                  inside wall_ion_energy_eV is NOT checked (listed in NOT_COVERED).
  rf_source / ecr_source  antenna/coupler copper, dielectric and plasma-to-structure heat = input fractions x RF power.
  ecr_magnet      heat = input fraction x ECR power; margins vs the grade's maximum use temperature, reversible Br loss
                  (Br(T)/Br20 = 1 + alpha (T - 20)/100 inside the coefficient range), and irreversible loss (opposing
                  field below the knee field at >= the magnet temperature; Hcj(T) as a necessary condition).
  cathode         keeper fraction + heater duty x heater power + emitter plasma heating; emitter temperature from
                  Richardson-Dushman over the four LaB6 parameter sets of Goebel & Katz Table 6-1 (envelope, none selected);
                  evaporation-limited life (Goebel & Katz sec. 6.8.4) and an O2 poisoning screen (p. 306).

Rejection: each node rejects through declared paths (conductance to a sink, or radiation eps sigma A F (T^4 - T_s^4));
the paths are inputs (thermal geometry: TBD). Steady state only.

Outcomes: each check is PASS, FAIL or NOT_DEMONSTRATED (inputs complete but the sourced evidence cannot decide, e.g. a
temperature outside a coefficient's measured range). The overall status is FAIL, NOT_DEMONSTRATED or
PASS_CHECKED_ITEMS; the last one is NOT a thermal qualification (see NOT_COVERED). Missing/unsourced/mis-unitted inputs,
numeric records without uncertainty/applicability_domain/validation_status statements, TBD limits and non-physical
input sets (heat fractions > 1, heat above the discharge power) raise ValueError.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os

from .constants import E_CHARGE, K_B

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMITS_FILE = os.path.join(_ROOT, "schemas", "thermal_life", "limits_v1.json")
INPUTS_FILE = os.path.join(_ROOT, "schemas", "thermal_life", "inputs_v1.json")
HALL_MAP_SCHEMA_FILE = os.path.join(_ROOT, "hallthruster_bridge", "hall_map_schema_v1.json")

LIMITS_SCHEMA = "thermal_life_limits_v1"
INPUTS_SCHEMA = "thermal_life_inputs_v1"
RESULT_SCHEMA = "thermal_life_result_v1"

# Names shared with the bus-power boundary lane (not imported).
BUS_POWER_COMPONENTS = ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater",
                        "rf_source", "ecr_source", "ecr_magnet")
THERMAL_COMPONENTS = ("hall_discharge", "hall_magnet", "cathode", "rf_source", "ecr_source", "ecr_magnet")
QUANTITY_TYPES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
HALLMAP_FIELDS_USED = ("discharge_power_W", "discharge_current_A", "wall_ion_flux_m2s", "wall_ion_energy_eV")

SIGMA_SB = 5.670374419e-8      # W m^-2 K^-4, exact (NIST CODATA 2022; source id nist_codata_sigma)
T_ZERO_C_K = 273.15            # K, exact (SI definition of the degree Celsius)
EV_PER_K = K_B / E_CHARGE      # Boltzmann constant in eV/K (exact SI constants, abep_sim.constants)

PASS, FAIL, NOT_DEMONSTRATED = "PASS", "FAIL", "NOT_DEMONSTRATED"
OVERALL_PASS = "PASS_CHECKED_ITEMS"

NOT_COVERED = (
    "transient and eclipse thermal cycling (steady-state lumped nodes only)",
    "Hall anode node temperature (anode heat is accounted; no anode rejection model or limit in v1)",
    "coupling between nodes (each node rejects to its own declared sinks; heat one node passes to another, e.g. "
    "discharge heat reaching the coil, must be supplied as that node's input)",
    "PPU / converter losses (bus-power lane)",
    "radiation dose, atomic-oxygen and outgassing effects on insulation, magnets and emitter",
    "keeper erosion life and heater failure modes other than the qualified-cycle count",
    "consistency of the wall electron-heat inputs (wall_electron_temperature_eV, wall_see_yield) with the sheath "
    "(T_e, gamma, phi_s) already contained in HallMap wall_ion_energy_eV (bridge_lib.jl wall_ion_metrics): these "
    "quantities are not hall_map_schema_v1 fields, so the caller must take them from the same solve; not checked in v1",
    "provenance of admitted_hallmap wall-flux records beyond member id, commit and map-meta hash form (no map registry)",
)


# ----------------------------------------------------------------------------------------------- contracts
def _canonical_sha256(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_limits(path: str = LIMITS_FILE) -> dict:
    """Load and structurally validate the limits file (every sourced record fully attributed, every TBD explained)."""
    with open(path) as fh:
        d = json.load(fh)
    if d.get("schema") != LIMITS_SCHEMA:
        raise ValueError(f"{path} is not {LIMITS_SCHEMA}")
    validate_limits(d)
    return d


def validate_limits(d: dict) -> None:
    sources = d.get("sources", {})
    for sid, s in sources.items():
        for k in ("citation", "url", "access", "accessed_on"):
            if not s.get(k):
                raise ValueError(f"limits source {sid!r} lacks {k!r}")
    for rid, r in d.get("records", {}).items():
        st = r.get("status")
        if st == "TBD":
            if not r.get("requires"):
                raise ValueError(f"TBD limit record {rid!r} must say what it requires")
            continue
        if st != "sourced":
            raise ValueError(f"limit record {rid!r}: status must be 'sourced' or 'TBD', got {st!r}")
        if r.get("source_id") not in sources:
            raise ValueError(f"limit record {rid!r}: unknown source_id {r.get('source_id')!r}")
        for k in ("kind", "locator", "evidence_level", "quantity_type", "values", "transformation_chain",
                  "uncertainty", "applicability_domain", "validation_status"):
            if k not in r or r[k] in (None, "", {}):
                raise ValueError(f"limit record {rid!r} lacks {k!r}")
        _check_evidence(r["evidence_level"], r["quantity_type"], f"limit record {rid!r}")
        for vk, v in r["values"].items():
            if "unit" not in v or not v.get("as_published"):
                raise ValueError(f"limit record {rid!r} value {vk!r} lacks unit/as_published")
            if v.get("value") is None and not v.get("TBD"):
                raise ValueError(f"limit record {rid!r} value {vk!r} is null without a TBD statement")
            if "quantity_type" in v and v["quantity_type"] not in QUANTITY_TYPES:
                raise ValueError(f"limit record {rid!r} value {vk!r}: bad quantity_type")
    for name, rel in d.get("relations", {}).items():
        if rel.get("source_id") not in sources or not rel.get("locator"):
            raise ValueError(f"relation {name!r} is not sourced")


def load_inputs_contract(path: str = INPUTS_FILE) -> dict:
    with open(path) as fh:
        c = json.load(fh)
    if c.get("schema") != INPUTS_SCHEMA:
        raise ValueError(f"{path} is not {INPUTS_SCHEMA}")
    if tuple(c["bus_power_components"]) != BUS_POWER_COMPONENTS:
        raise ValueError("inputs contract bus_power_components disagree with thermal_life.BUS_POWER_COMPONENTS")
    if set(c["components"]) != set(THERMAL_COMPONENTS):
        raise ValueError("inputs contract components disagree with thermal_life.THERMAL_COMPONENTS")
    wk = c.get("wall_flux_provenance", {}).get("kinds", {})
    if (tuple(wk.get(PROV_ADMITTED_HALLMAP, {}).get("fields", ())) != ADMITTED_HALLMAP_PROV_FIELDS
            or tuple(wk.get(PROV_MEASURED_HARDWARE, {}).get("evidence_record_fields", ())) != HARDWARE_EVIDENCE_FIELDS):
        raise ValueError("inputs contract wall_flux_provenance disagrees with thermal_life (gap G11 gate)")
    return c


def load_hall_map_schema(path: str = HALL_MAP_SCHEMA_FILE) -> dict:
    with open(path) as fh:
        s = json.load(fh)
    if s.get("schema") != "hall_map_schema_v1":
        raise ValueError(f"{path} is not hall_map_schema_v1")
    missing = [f for f in HALLMAP_FIELDS_USED if f not in s["fields"]]
    if missing:
        raise ValueError(f"hall_map_schema_v1 no longer defines {missing}: thermal_life must be updated")
    return s


def limit_record(limits: dict, rid: str, kind: str | None = None) -> dict:
    """A sourced limit record; ValueError if it is absent, TBD or of another kind (no fallback)."""
    r = limits.get("records", {}).get(rid)
    if r is None:
        raise ValueError(f"limit record {rid!r} is not in the limits file")
    if r.get("status") != "sourced":
        raise ValueError(f"limit record {rid!r} is TBD - requires: {r.get('requires')}")
    if kind is not None and r.get("kind") != kind:
        raise ValueError(f"limit record {rid!r} is of kind {r.get('kind')!r}, expected {kind!r}")
    return r


def limit_value(limits: dict, rid: str, key: str, kind: str | None = None):
    r = limit_record(limits, rid, kind)
    v = r["values"].get(key)
    if v is None:
        raise ValueError(f"limit record {rid!r} has no value {key!r}")
    if v.get("value") is None:
        raise ValueError(f"limit {rid}.{key} is TBD - requires: {v.get('TBD')}")
    return v["value"]


def _has_value(limits: dict, rid: str, key: str) -> bool:
    v = limit_record(limits, rid)["values"].get(key)
    return v is not None and v.get("value") is not None


# ----------------------------------------------------------------------------------------------- input records
def _check_evidence(level, qtype, where: str) -> None:
    if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 7:
        raise ValueError(f"{where}: evidence_level must be an integer 1-7 (docs/EVIDENCE.md), got {level!r}")
    if qtype not in QUANTITY_TYPES:
        raise ValueError(f"{where}: quantity_type must be one of {QUANTITY_TYPES}, got {qtype!r}")


NUMBER_RECORD_FIELDS = ("value", "unit", "source", "evidence_level", "quantity_type", "uncertainty",
                        "applicability_domain", "validation_status")
NUMBER_RECORD_TEXT_FIELDS = ("uncertainty", "applicability_domain", "validation_status")   # CLAUDE.md rule 10


def _number(rec, unit: str, where: str) -> float:
    if not isinstance(rec, dict):
        raise ValueError(f"{where}: input must be a record with {'/'.join(NUMBER_RECORD_FIELDS)}")
    for k in NUMBER_RECORD_FIELDS:
        if k not in rec:
            raise ValueError(f"{where}: input record lacks {k!r}")
    for k in NUMBER_RECORD_TEXT_FIELDS:
        if not isinstance(rec[k], str) or not rec[k].strip():
            raise ValueError(f"{where}: input record field {k!r} must be a non-empty statement "
                             "(write 'unquantified' / 'TBD - requires ...' explicitly; docs/EVIDENCE.md, CLAUDE.md rule 10)")
    if rec["unit"] != unit:
        raise ValueError(f"{where}: unit {rec['unit']!r} is not the contract unit {unit!r} (no unit conversion is done)")
    if not isinstance(rec["source"], str) or not rec["source"].strip():
        raise ValueError(f"{where}: input has no source")
    _check_evidence(rec["evidence_level"], rec["quantity_type"], where)
    v = rec["value"]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"{where}: value must be a finite number, got {v!r}")
    return float(v)


def _ident(rec, spec: dict, where: str) -> str:
    if not isinstance(rec, dict) or not {"value", "unit", "source"} <= set(rec):
        raise ValueError(f"{where}: selection input must be a record with value/unit/source")
    if rec["unit"] != "id" or not isinstance(rec["source"], str) or not rec["source"].strip():
        raise ValueError(f"{where}: selection input needs unit 'id' and a source")
    v = rec["value"]
    if "allowed" in spec and v not in spec["allowed"]:
        raise ValueError(f"{where}: {v!r} is not one of {spec['allowed']}")
    if "allowed_prefix" in spec and not (isinstance(v, str) and v.startswith(spec["allowed_prefix"])):
        raise ValueError(f"{where}: {v!r} must be a limits record id starting with {spec['allowed_prefix']!r}")
    return v


def _paths(recs, contract: dict, where: str) -> list[dict]:
    if not isinstance(recs, list) or not recs:
        raise ValueError(f"{where}: at least one rejection path is required (thermal geometry: TBD)")
    out = []
    for i, p in enumerate(recs):
        kinds = contract["rejection_path"]
        if not isinstance(p, dict) or p.get("kind") not in kinds:
            raise ValueError(f"{where}[{i}]: kind must be one of {sorted(kinds)}")
        spec = kinds[p["kind"]]
        extra = set(p) - set(spec) - {"kind"}
        if extra:
            raise ValueError(f"{where}[{i}]: unknown fields {sorted(extra)}")
        q = {"kind": p["kind"]}
        for f, fs in spec.items():
            if f not in p:
                raise ValueError(f"{where}[{i}].{f} missing ({fs['from']})")
            q[f] = _number(p[f], fs["unit"], f"{where}[{i}].{f}")
        if q["T_sink_K"] <= 0:
            raise ValueError(f"{where}[{i}]: T_sink_K must be > 0")
        if p["kind"] == "conductance" and q["G_W_per_K"] <= 0:
            raise ValueError(f"{where}[{i}]: G_W_per_K must be > 0")
        if p["kind"] == "radiation":
            if not (0 < q["emissivity"] <= 1 and 0 < q["view_factor"] <= 1 and q["area_m2"] > 0):
                raise ValueError(f"{where}[{i}]: need 0 < emissivity <= 1, 0 < view_factor <= 1, area > 0")
        out.append(q)
    return out


class _ComponentInputs:
    """Validated access to one component's inputs; refuses missing, unknown or unsourced entries up front."""

    def __init__(self, component: str, raw: dict, contract: dict):
        if not isinstance(raw, dict):
            raise ValueError(f"{component}: inputs must be a dict")
        self.c, self.raw, self.contract = component, raw, contract
        self.spec = contract["components"][component]["inputs"]
        missing = [k for k in self.spec if k not in raw]
        if missing:
            lines = [f"{k} ({self.spec[k]['from']}; now: {self.spec[k].get('now', '?')})" for k in missing]
            raise ValueError(f"{component}: missing required inputs (no defaults): " + "; ".join(lines))
        unknown = sorted(set(raw) - set(self.spec))
        if unknown:
            raise ValueError(f"{component}: unknown inputs {unknown} (not in {INPUTS_SCHEMA})")

    def num(self, key: str) -> float:
        s = self.spec[key]
        if s["kind"] != "number":
            raise ValueError(f"{self.c}.{key} is not a number input")
        return _number(self.raw[key], s["unit"], f"{self.c}.{key}")

    def ident(self, key: str) -> str:
        s = self.spec[key]
        if s["kind"] != "id":
            raise ValueError(f"{self.c}.{key} is not a selection input")
        return _ident(self.raw[key], s, f"{self.c}.{key}")

    def paths(self, key: str = "rejection_paths") -> list[dict]:
        return _paths(self.raw[key], self.contract, f"{self.c}.{key}")

    def source(self, key: str) -> str:
        return self.raw[key]["source"]


def _fraction(x: float, where: str) -> float:
    if not 0.0 <= x <= 1.0:
        raise ValueError(f"{where}: fraction must lie in [0, 1], got {x}")
    return x


# ----------------------------------------------------------------------------------------------- heat rejection
def rejected_heat_W(paths: list[dict], T_K: float) -> float:
    """Heat leaving a node at temperature T_K through its declared paths (negative if the sinks are hotter)."""
    q = 0.0
    for p in paths:
        if p["kind"] == "conductance":
            q += p["G_W_per_K"] * (T_K - p["T_sink_K"])
        elif p["kind"] == "radiation":
            q += p["emissivity"] * SIGMA_SB * p["area_m2"] * p["view_factor"] * (T_K ** 4 - p["T_sink_K"] ** 4)
        else:
            raise ValueError(f"unknown rejection path kind {p['kind']!r}")
    return q


def solve_node_temperature(heat_W, paths: list[dict], T_min_K: float | None = None,
                           T_max_K: float | None = None) -> dict:
    """Steady state rejected_heat_W(T) = heat(T) for a lumped node.

    heat_W is a constant or a non-decreasing callable of T_K. With a model domain [T_min_K, T_max_K] (e.g. the copper
    resistance model) the heat is never evaluated outside it: if the balance lies outside, the result is a one-sided
    bound {'T_K': None, 'bound': ('above' | 'below', T)} instead of an extrapolated number."""
    q = heat_W if callable(heat_W) else (lambda T, _h=float(heat_W): _h)

    def f(T):
        return rejected_heat_W(paths, T) - q(T)

    lo = min(p["T_sink_K"] for p in paths)
    if T_max_K is not None and lo > T_max_K:
        return {"T_K": None, "bound": ("above", T_max_K)}   # coldest sink already above the model domain
    if T_min_K is not None and lo < T_min_K:
        lo = T_min_K
        if f(lo) > 0.0:
            return {"T_K": None, "bound": ("below", T_min_K)}
    if f(lo) >= 0.0:
        return {"T_K": lo, "bound": None}
    if T_max_K is not None:
        hi = T_max_K
        if f(hi) < 0.0:
            return {"T_K": None, "bound": ("above", T_max_K)}
    else:
        hi = lo + 1.0
        while f(hi) < 0.0:
            hi = lo + 2.0 * (hi - lo)
            if hi > 1.0e5:
                raise ValueError("no steady state below 1e5 K: the declared rejection paths cannot carry the heat")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) < 0.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12 * max(1.0, hi):
            break
    return {"T_K": 0.5 * (lo + hi), "bound": None}


def _margin_check(name: str, margin: float, unit: str, detail: dict) -> dict:
    return {"name": name, "status": PASS if margin >= 0.0 else FAIL, "margin": margin, "unit": unit, **detail}


def _nd(name: str, why: str, **detail) -> dict:
    return {"name": name, "status": NOT_DEMONSTRATED, "margin": None, "why": why, **detail}


# ----------------------------------------------------------------------------------------------- copper / coil
def copper_resistance_ratio(T_C: float, T_ref_C: float, model: str, limits: dict) -> float:
    """R(T)/R(T_ref) for annealed copper (NBS Handbook 100). ValueError outside the model domain (no extrapolation)."""
    lo, hi = copper_model_domain_C(model, limits)
    for t in (T_C, T_ref_C):
        if not lo <= t <= hi:
            raise ValueError(f"copper model {model!r} is defined on [{lo}, {hi}] C; {t} C is outside (no extrapolation)")
    rec = limit_record(limits, model)
    if rec["kind"] == "copper_resistance_linear":
        a = limit_value(limits, model, "alpha_20C")
        return (1.0 + a * (T_C - 20.0)) / (1.0 + a * (T_ref_C - 20.0))
    if rec["kind"] == "copper_resistance_ratio_table":
        ts = limit_value(limits, model, "T_C")
        rs = limit_value(limits, model, "R_over_R0")
        return _interp(T_C, ts, rs) / _interp(T_ref_C, ts, rs)
    raise ValueError(f"{model!r} is not a copper resistance model")


def copper_model_domain_C(model: str, limits: dict) -> tuple[float, float]:
    rec = limit_record(limits, model)
    if rec["kind"] == "copper_resistance_linear":
        return float(limit_value(limits, model, "T_min_C")), float(limit_value(limits, model, "T_max_C"))
    if rec["kind"] == "copper_resistance_ratio_table":
        ts = limit_value(limits, model, "T_C")
        return float(ts[0]), float(ts[-1])
    raise ValueError(f"{model!r} is not a copper resistance model")


def _interp(x: float, xs: list, ys: list) -> float:
    if not xs[0] <= x <= xs[-1]:
        raise ValueError(f"{x} outside the tabulated range [{xs[0]}, {xs[-1]}]")
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            w = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + w * (ys[i + 1] - ys[i])
    raise ValueError("tabulated abscissae must increase")


def coil_resistance_from_geometry(length_m: float, area_m2: float, limits: dict) -> float:
    """Winding resistance at 20 C from conductor length and cross-section, IACS resistivity (NBS HB100 p. 3)."""
    if length_m <= 0 or area_m2 <= 0:
        raise ValueError("length and area must be > 0")
    return limit_value(limits, "copper_iacs_linear", "rho_20C") * length_m / area_m2


def winding_temperature_rise_mil_prf_27(R_hot_ohm: float, r_cold_ohm: float, t_initial_C: float,
                                        T_ambient_shutoff_C: float) -> float:
    """MIL-PRF-27 4.7.13 resistance-method rise as quoted in EEE-INST-002 M1 Table 4 note 1/a:
    dT = (R - r)/r (t + 234.5) - (T - t); the note requires |T - t| <= 5 C."""
    if abs(T_ambient_shutoff_C - t_initial_C) > 5.0:
        raise ValueError("EEE-INST-002 note 1/a: T shall not differ from t by more than 5 C")
    return (R_hot_ohm - r_cold_ohm) / r_cold_ohm * (t_initial_C + 234.5) - (T_ambient_shutoff_C - t_initial_C)


def insulation_allowable_C(class_C: float, policy: str, limits: dict) -> dict:
    """Allowable hot-spot temperature of a winding for an IEC 60085 thermal class under an explicit derating policy.

    Returns the allowable temperature and the life basis that the cited source attaches to it (or why none exists)."""
    classes = limit_value(limits, "iec60085_thermal_classes", "classes_C", "insulation_thermal_classes")
    if class_C not in classes and not (class_C > 250 and (class_C - 250) % 25 == 0):
        raise ValueError(f"{class_C} C is not an IEC 60085 thermal class {classes} (+25 C steps above 250)")
    rid = "eee_inst_002_magnetics"
    if policy == "none":
        life = limit_record(limits, "iec60085_thermal_classes")["values"]["life_basis_h"]
        return {"allowable_C": float(class_C), "policy": policy, "life_basis_h": None,
                "life_basis_status": "TBD", "life_basis_note": life.get("TBD")}
    if policy == "eee_inst_002_custom_0p75":
        f = limit_value(limits, rid, "custom_derating_factor")
        return {"allowable_C": f * class_C, "policy": policy,
                "life_basis_h": limit_value(limits, rid, "life_basis_at_derated_h"), "life_basis_status": "inferred",
                "life_basis_note": "note 1/b states 50,000 h for the Table 4 derated temperatures; carrying it over to "
                                   "the note 1/c 0.75 factor is our inference (verify); 0.75 applied in C (verify)"}
    if policy == "eee_inst_002_class_c_minus_20":
        if class_C <= 125:
            raise ValueError("the 'Max. Temp. - 20 C' row of EEE-INST-002 Table 4 is for class C ratings > +125 C")
        # Note 1/b states the 50,000 h basis for MIL-style inductive parts; note 1/c assigns custom devices (a thruster
        # coil is one) the 0.75 factor instead. Mapping an IEC 60085 EIS class onto the MIL class C row is an analogy,
        # so the life basis is 'inferred' here, never 'stated' (insulation_life then stays NOT_DEMONSTRATED).
        return {"allowable_C": class_C - limit_value(limits, rid, "class_c_derating_K"), "policy": policy,
                "life_basis_h": limit_value(limits, rid, "life_basis_at_derated_h"), "life_basis_status": "inferred",
                "life_basis_note": "EEE-INST-002 M1 Table 4 note 1/b states 50,000 h for MIL-style inductive parts at "
                                   "rated voltage; applying the MIL class C row to an IEC 60085 class of a custom "
                                   "thruster coil (note 1/c territory) is an analogy (verify)"}
    raise ValueError(f"unknown derating policy {policy!r}")


def _check_hall_magnet(ci: _ComponentInputs, limits: dict, mission: dict) -> dict:
    I, R_ref, T_ref = ci.num("coil_current_A"), ci.num("coil_resistance_ref_ohm"), ci.num("coil_resistance_ref_T_C")
    model, Q_ext = ci.ident("copper_model"), ci.num("external_heat_W")
    alloc, cls, policy = ci.num("bus_power_allocation_W"), ci.num("insulation_class_C"), ci.ident("derating_policy")
    hs, paths = ci.num("hot_spot_allowance_K"), ci.paths()
    if I < 0 or R_ref <= 0 or Q_ext < 0 or hs < 0 or alloc < 0:
        raise ValueError("hall_magnet: need I >= 0, R_ref > 0, external heat >= 0, hot-spot allowance >= 0, allocation >= 0")
    lo_C, hi_C = copper_model_domain_C(model, limits)
    copper_resistance_ratio(T_ref, T_ref, model, limits)            # reference temperature must lie in the domain

    def coil_W(T_K):
        return I * I * R_ref * copper_resistance_ratio(T_K - T_ZERO_C_K, T_ref, model, limits)

    sol = solve_node_temperature(lambda T: coil_W(T) + Q_ext, paths, lo_C + T_ZERO_C_K, hi_C + T_ZERO_C_K)
    ins = insulation_allowable_C(cls, policy, limits)
    allow = ins["allowable_C"]
    checks = []
    if sol["T_K"] is not None:
        T_C = sol["T_K"] - T_ZERO_C_K
        P = coil_W(sol["T_K"])
        checks.append(_margin_check("winding_hot_spot_temperature", allow - (T_C + hs), "K",
                                    {"T_mean_C": T_C, "T_hot_spot_C": T_C + hs, "allowable_C": allow}))
        checks.append(_margin_check("coil_power_vs_bus_allocation", alloc - P, "W", {"P_coil_W": P, "allocation_W": alloc}))
        temp_ok = checks[0]["status"] == PASS
        heat = {"coil_I2R_W": P, "external_W": Q_ext}
    else:
        side, T_edge_K = sol["bound"]
        edge_C = T_edge_K - T_ZERO_C_K
        P_edge = coil_W(T_edge_K)
        if side == "above":          # true T > edge (resistance rises monotonically), so T_hot > edge + hs and P > P_edge
            c1 = (_margin_check("winding_hot_spot_temperature", allow - (edge_C + hs), "K",
                                {"T_mean_C": f"> {edge_C}", "allowable_C": allow, "bound": "above copper model domain"})
                  if edge_C + hs >= allow else
                  _nd("winding_hot_spot_temperature", f"coil balance lies above the copper model domain ({edge_C} C) "
                      "but that bound is below the allowable temperature", allowable_C=allow))
            c2 = (_margin_check("coil_power_vs_bus_allocation", alloc - P_edge, "W", {"P_coil_W": f"> {P_edge}"})
                  if P_edge > alloc else
                  _nd("coil_power_vs_bus_allocation", "coil power above the domain-edge value; not bounded from above"))
        else:                        # true T < edge, so T_hot < edge + hs and P < P_edge
            c1 = (_margin_check("winding_hot_spot_temperature", allow - (edge_C + hs), "K",
                                {"T_mean_C": f"< {edge_C}", "allowable_C": allow, "bound": "below copper model domain"})
                  if edge_C + hs <= allow else
                  _nd("winding_hot_spot_temperature", "balance below the copper model domain", allowable_C=allow))
            c2 = (_margin_check("coil_power_vs_bus_allocation", alloc - P_edge, "W", {"P_coil_W": f"< {P_edge}"})
                  if P_edge <= alloc else
                  _nd("coil_power_vs_bus_allocation", "coil power below the domain-edge value; not bounded from below"))
        checks += [c1, c2]
        temp_ok = c1["status"] == PASS
        heat = {"coil_I2R_W": None, "coil_I2R_bound_W": (side, P_edge), "external_W": Q_ext}
    req = mission["required_firing_h"]
    if not temp_ok:
        checks.append(_nd("insulation_life", "hot-spot temperature not shown to be within the allowable temperature"))
    elif ins["life_basis_status"] == "stated":
        checks.append(_margin_check("insulation_life", ins["life_basis_h"] - req, "h",
                                    {"life_basis_h": ins["life_basis_h"], "required_h": req, "note": ins["life_basis_note"]}))
    else:
        checks.append(_nd("insulation_life", f"life basis is {ins['life_basis_status']}: {ins['life_basis_note']}",
                          life_basis_h=ins["life_basis_h"], required_h=req))
    return {"heat_W": heat, "T_node": sol, "insulation": ins, "checks": checks}


# ----------------------------------------------------------------------------------------------- Hall walls
def hall_wall_ion_heat_W(wall_ion_flux_m2s: float, wall_ion_energy_eV: float, wall_area_m2: float) -> float:
    """e Gamma_i eps_i A: the HallMap flux is the time-averaged z <= L cell average and the energy is flux-weighted over
    the same frames/cells (bridge_lib.jl wall_ion_metrics), so the product is the ion energy flux integral."""
    if wall_ion_flux_m2s < 0 or wall_ion_energy_eV < 0 or wall_area_m2 <= 0:
        raise ValueError("wall ion flux and energy must be >= 0 and the wall area > 0")
    return E_CHARGE * wall_ion_flux_m2s * wall_ion_energy_eV * wall_area_m2


def hall_wall_electron_heat_W(wall_ion_flux_m2s: float, Te_wall_eV: float, see_yield: float, wall_area_m2: float) -> float:
    """Goebel & Katz 2008: zero net current I_iw = I_ew (1 - gamma) (Eq. 7.3-28) and 2 T_e deposited per primary
    electron (Eqs. 7.3-43/7.3-45, secondary-electron cooling neglected): Q_e = e Gamma_i 2 T_e / (1 - gamma) A."""
    if not 0.0 <= see_yield < 1.0:
        raise ValueError("the zero-net-current relation needs 0 <= gamma < 1 (space-charge-limited cap, Eq. 7.3-42)")
    if wall_ion_flux_m2s < 0 or Te_wall_eV < 0 or wall_area_m2 <= 0:
        raise ValueError("flux and T_e must be >= 0 and the area > 0")
    return E_CHARGE * wall_ion_flux_m2s * 2.0 * Te_wall_eV / (1.0 - see_yield) * wall_area_m2


def hall_anode_heat_W(discharge_current_A: float, Te_anode_eV: float) -> float:
    """Goebel & Katz 2008 Eq. (7.3-53): P_a = 2 I_d T_eV(anode)."""
    if discharge_current_A < 0 or Te_anode_eV < 0:
        raise ValueError("I_d and T_e must be >= 0")
    return 2.0 * discharge_current_A * Te_anode_eV


# Hall wall-flux provenance gate (gap G11, docs/evidence/wall_life/). Wall ion flux and energy drive both the wall heat
# and the erosion life, so they are accepted only from (a) a query of a Hall map produced by an ADMITTED transport-
# ensemble member with wall_life_trustworthy = true, re-verified against the ensemble at check time
# (abep_sim.hall_ensemble.require_admitted: screening candidates and unknown ids are refused), or (b) measured hardware
# data carrying its evidence record. Anything else (hand-entered, screening-candidate, unadmitted-closure or
# unprovenanced values) raises: no PASS/FAIL is ever produced from it.
WALL_FLUX_INPUTS = ("wall_ion_flux_m2s", "wall_ion_energy_eV")
WALL_FLUX_PROVENANCE_KEY = "wall_flux_provenance"
PROV_ADMITTED_HALLMAP = "admitted_hallmap"
PROV_MEASURED_HARDWARE = "measured_hardware"
ADMITTED_HALLMAP_PROV_FIELDS = ("kind", "ensemble_member_id", "trustworthy", "wall_life_trustworthy",
                                "hallthruster_commit", "map_meta_sha256")
# Known limit (v1): check_feasibility re-verifies the member id (hall_ensemble.require_admitted), the commit and the
# form of map_meta_sha256, but it cannot re-open the map file, so the trust flags are only as good as the producer
# (hallmap_wall_inputs, which binds them to the HallMap meta). A hand-written admitted_hallmap record naming an admitted
# id would pass once members exist; closing this needs a map registry with file hashes (owner decision).
HARDWARE_EVIDENCE_FIELDS = ("test_article", "facility", "document", "measurement_method", "uncertainty",
                            "operating_point", "applicability_domain")


def _require_admitted_member(member_id: str) -> None:
    """Lazy gate on the baseline transport ensemble (hall_ensemble is read, never modified). Refuses screening
    candidates (sgb-screen-*) and unknown ids; the credible set is empty as of 2026-09-26, so every id is refused today."""
    from abep_sim import hall_ensemble
    hall_ensemble.require_admitted(member_id)


def _pinned_hall_commit() -> str:
    from abep_sim.hall_map import pinned_commit
    return pinned_commit()


def _check_wall_flux_provenance(raw: dict, where: str) -> dict:
    """Validate the provenance of hall_discharge wall_ion_flux_m2s / wall_ion_energy_eV. Returns the provenance
    summary for the result; raises ValueError for anything that is not an admitted-member Hall-map point or measured
    hardware data with a complete evidence record."""
    provs = []
    for f in WALL_FLUX_INPUTS:
        rec = raw[f]
        prov = rec.get(WALL_FLUX_PROVENANCE_KEY) if isinstance(rec, dict) else None
        if not isinstance(prov, dict):
            raise ValueError(f"{where}.{f}: no {WALL_FLUX_PROVENANCE_KEY!r}. Hall wall flux/energy are accepted only from "
                             "an admitted-member Hall-map point (hallmap_wall_inputs) or measured hardware data with its "
                             "evidence record (gap G11; hand-entered or screening-candidate values are refused)")
        kind = prov.get("kind")
        if kind == PROV_ADMITTED_HALLMAP:
            if set(prov) != set(ADMITTED_HALLMAP_PROV_FIELDS):
                raise ValueError(f"{where}.{f}: admitted_hallmap provenance must have exactly {ADMITTED_HALLMAP_PROV_FIELDS}")
            if rec.get("quantity_type") != "model-derived":
                raise ValueError(f"{where}.{f}: a Hall-map value is 'model-derived', got {rec.get('quantity_type')!r}")
            mid = prov["ensemble_member_id"]
            if not isinstance(mid, str) or not mid:
                raise ValueError(f"{where}.{f}: admitted_hallmap provenance needs an ensemble_member_id")
            _require_admitted_member(mid)
            if prov["trustworthy"] is not True:
                raise ValueError(f"{where}.{f}: Hall-map point is not trustworthy")
            if prov["wall_life_trustworthy"] is not True:
                raise ValueError(f"{where}.{f}: Hall-map point is not wall_life_trustworthy: wall flux/energy are "
                                 "diagnostic only")
            if prov["hallthruster_commit"] != _pinned_hall_commit():
                raise ValueError(f"{where}.{f}: Hall-map point was not produced with the pinned HallThruster.jl commit")
            h = prov["map_meta_sha256"]
            if not (isinstance(h, str) and len(h) == 64 and all(ch in "0123456789abcdef" for ch in h)):
                raise ValueError(f"{where}.{f}: map_meta_sha256 must be the 64-hex sha256 of the HallMap meta "
                                 "(written by hallmap_wall_inputs)")
        elif kind == PROV_MEASURED_HARDWARE:
            if set(prov) != {"kind", "evidence_record"} or not isinstance(prov["evidence_record"], dict):
                raise ValueError(f"{where}.{f}: measured_hardware provenance must be {{'kind', 'evidence_record'}}")
            ev = prov["evidence_record"]
            bad = [k for k in HARDWARE_EVIDENCE_FIELDS
                   if not isinstance(ev.get(k), str) or not ev[k].strip()]
            if bad:
                raise ValueError(f"{where}.{f}: measured-hardware evidence record lacks {bad} "
                                 f"(required: {HARDWARE_EVIDENCE_FIELDS})")
            if rec.get("quantity_type") != "measured":
                raise ValueError(f"{where}.{f}: hardware wall-flux data must be quantity_type 'measured', "
                                 f"got {rec.get('quantity_type')!r}")
        else:
            raise ValueError(f"{where}.{f}: provenance kind must be {PROV_ADMITTED_HALLMAP!r} or "
                             f"{PROV_MEASURED_HARDWARE!r}, got {kind!r}")
        provs.append(prov)
    if provs[0] != provs[1]:
        raise ValueError(f"{where}: wall_ion_flux_m2s and wall_ion_energy_eV must come from the same Hall-map point or "
                         "hardware record (identical provenance)")
    return copy.deepcopy(provs[0])


def hallmap_wall_inputs(point: dict, ensemble_member_id: str, evidence_level: int, *, map_meta: dict,
                        uncertainty: str, applicability_domain: str, validation_status: str,
                        schema: dict | None = None) -> dict:
    """Input records for hall_discharge from one HallMap query (abep_sim.hall_map.HallMap.__call__ output).

    map_meta is the queried map's meta (HallMap.meta). The query output does not carry the member id, so the id is
    bound to the map here: map_meta['ensemble_member_id'] must equal ensemble_member_id, map_meta['hallthruster_commit']
    must equal the query commit, and the canonical sha256 of map_meta is recorded in the provenance. uncertainty,
    applicability_domain and validation_status are the caller's explicit statements (no defaults; CLAUDE.md rule 10).

    Refuses unless ensemble_member_id is an ADMITTED transport-ensemble member (hall_ensemble.require_admitted:
    screening candidates and unknown ids raise), the query is performance-trustworthy AND wall_life_trustworthy
    (ion_wall_losses=true, WallSheath, unshielded), and it carries the pinned HallThruster.jl commit. The credible
    transport set is empty (2026-09-26), so no member is admitted and this path refuses every id today. The wall
    flux/energy records carry 'wall_flux_provenance', which check_feasibility re-verifies (admission included).
    evidence_level has no default: the caller states it per docs/EVIDENCE.md (a transport closure admitted on P5
    data and applied to Vyovrinda geometry is an extrapolation outside its directly validated domain);
    quantity_type is always 'model-derived'."""
    if not ensemble_member_id:
        raise ValueError("a HallMap point must name its admitted ensemble member")
    _check_evidence(evidence_level, "model-derived", "hallmap_wall_inputs")
    _require_admitted_member(ensemble_member_id)
    schema = schema or load_hall_map_schema()
    if point.get("trustworthy") is not True:
        raise ValueError("HallMap query is not trustworthy (convergence, sustainment or chemistry validity)")
    if point.get("wall_life_trustworthy") is not True:
        raise ValueError("HallMap query is not wall_life_trustworthy: wall flux/energy are diagnostic only")
    commit = point.get("hallthruster_commit")
    if commit != _pinned_hall_commit():
        raise ValueError(f"HallMap query commit {commit!r} is not the pinned HallThruster.jl commit")
    if not isinstance(map_meta, dict):
        raise ValueError("map_meta must be the queried HallMap's meta dict")
    if map_meta.get("ensemble_member_id") != ensemble_member_id:
        raise ValueError(f"map meta ensemble_member_id {map_meta.get('ensemble_member_id')!r} is not "
                         f"{ensemble_member_id!r}: the point must be labelled with the member that produced its map")
    if map_meta.get("hallthruster_commit") != commit:
        raise ValueError("map meta hallthruster_commit differs from the query commit")
    if map_meta.get("ion_wall_losses") is not True:
        raise ValueError("map meta ion_wall_losses is not true: wall flux/energy are diagnostic only")
    stmts = {"uncertainty": uncertainty, "applicability_domain": applicability_domain,
             "validation_status": validation_status}
    for k, v in stmts.items():
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"hallmap_wall_inputs: {k} must be an explicit non-empty statement")
    prov = {"kind": PROV_ADMITTED_HALLMAP, "ensemble_member_id": ensemble_member_id, "trustworthy": True,
            "wall_life_trustworthy": True, "hallthruster_commit": commit,
            "map_meta_sha256": _canonical_sha256(map_meta)}
    out = {}
    for f in HALLMAP_FIELDS_USED:
        if f not in point:
            raise ValueError(f"HallMap query lacks {f!r}")
        out[f] = {"value": float(point[f]), "unit": schema["fields"][f]["unit"],
                  "source": f"HallMap query, ensemble member {ensemble_member_id}, hall_map_schema_v1 field {f}, "
                            f"HallThruster.jl {commit}",
                  "evidence_level": evidence_level, "quantity_type": "model-derived", **stmts}
        if f in WALL_FLUX_INPUTS:
            out[f][WALL_FLUX_PROVENANCE_KEY] = dict(prov)
    return out


def _check_hall_discharge(ci: _ComponentInputs, limits: dict, mission: dict) -> dict:
    wall_prov = _check_wall_flux_provenance(ci.raw, ci.c)       # G11 gate before any heat or life number is formed
    Pd, Id = ci.num("discharge_power_W"), ci.num("discharge_current_A")
    G, eps, A = ci.num("wall_ion_flux_m2s"), ci.num("wall_ion_energy_eV"), ci.num("wall_area_m2")
    Q_i = hall_wall_ion_heat_W(G, eps, A)
    Q_e = hall_wall_electron_heat_W(G, ci.num("wall_electron_temperature_eV"), ci.num("wall_see_yield"), A)
    P_a = hall_anode_heat_W(Id, ci.num("anode_electron_temperature_eV"))
    Q_add = ci.num("additional_wall_heat_W")
    if Q_add < 0 or Pd <= 0:
        raise ValueError("hall_discharge: additional wall heat must be >= 0 and the discharge power > 0")
    total = Q_i + Q_e + Q_add + P_a
    if total > Pd:
        raise ValueError(f"hall_discharge: accounted heat {total:.6g} W exceeds the discharge power {Pd:.6g} W "
                         "(energy conservation gate; inputs are inconsistent)")
    mat, env = ci.ident("wall_material_record"), ci.ident("wall_environment")
    key = {"oxidizing": "T_use_max_oxidizing_C", "inert_or_vacuum": "T_use_max_inert_vacuum_C"}[env]
    T_lim = limit_value(limits, mat, key, "wall_ceramic_grade")
    hs = ci.num("hot_spot_allowance_K")
    if hs < 0:
        raise ValueError("hall_discharge: hot-spot allowance must be >= 0")
    Q_wall = Q_i + Q_e + Q_add
    sol = solve_node_temperature(Q_wall, ci.paths())
    T_C = sol["T_K"] - T_ZERO_C_K
    checks = [_margin_check("wall_temperature", T_lim - (T_C + hs), "K",
                            {"T_mean_C": T_C, "T_hot_spot_C": T_C + hs, "limit_C": T_lim, "limit_record": mat,
                             "environment": env})]
    depth, peak, Y = (ci.num("allowable_erosion_depth_m"), ci.num("peak_to_average_flux_ratio"),
                      ci.num("volumetric_sputter_yield_m3_per_ion"))
    if depth <= 0 or peak < 1.0 or Y < 0:
        raise ValueError("hall_discharge: erosion depth > 0, peak/average flux >= 1 and sputter yield >= 0 required")
    rate = G * peak * Y
    life_h = math.inf if rate == 0 else depth / rate / 3600.0
    req = mission["required_firing_h"]
    checks.append(_margin_check("wall_erosion_life", life_h - req, "h",
                                {"erosion_rate_m_per_s": rate, "life_h": life_h, "required_h": req}))
    return {"heat_W": {"wall_ion_W": Q_i, "wall_electron_W": Q_e, "wall_additional_W": Q_add, "anode_W": P_a,
                       "wall_total_W": Q_wall, "heat_fraction_of_discharge_power": total / Pd},
            "wall_flux_provenance": wall_prov, "T_node": sol, "checks": checks,
            "sheath_consistency": "NOT_CHECKED: T_e,w and gamma must come from the same solve as wall_ion_energy_eV "
                                  "(not hall_map_schema_v1 fields; see not_covered)"}


# ----------------------------------------------------------------------------------------------- permanent magnets
def magnet_property_fraction(T_C: float, grade: str, limits: dict, coeff: str = "alpha_Br_pct_per_C") -> float:
    """X(T)/X(20 C) = 1 + c (T - 20)/100 (Arnold RTC slides 11-13), only inside the grade's coefficient range."""
    c = limit_value(limits, grade, coeff, "permanent_magnet_grade")
    lo, hi = limit_value(limits, grade, "coeff_T_min_C"), limit_value(limits, grade, "coeff_T_max_C")
    if not lo <= T_C <= hi:
        raise ValueError(f"{grade}: coefficient measured on [{lo}, {hi}] C; {T_C} C is outside (no extrapolation)")
    return 1.0 + c * (T_C - 20.0) / 100.0


def _check_ecr_magnet(ci: _ComponentInputs, limits: dict, mission: dict) -> dict:
    grade = ci.ident("magnet_grade_record")
    limit_record(limits, grade, "permanent_magnet_grade")
    P, f = ci.num("ecr_rf_power_W"), _fraction(ci.num("heat_fraction_to_magnets"), "ecr_magnet.heat_fraction_to_magnets")
    if ci.num("bus_power_allocation_W") != 0.0:
        raise ValueError("ecr_magnet: only permanent magnets are covered (bus-power allocation must be 0 W)")
    if P < 0:
        raise ValueError("ecr_magnet: ECR power must be >= 0")
    Br_min, Hd = ci.num("min_Br_fraction_required"), ci.num("demag_field_max_A_per_m")
    Hk, Hk_T = ci.num("knee_field_A_per_m"), ci.num("knee_field_at_T_C")
    hs = ci.num("hot_spot_allowance_K")
    if hs < 0 or Hd < 0 or Hk <= 0 or not 0 < Br_min <= 1:
        raise ValueError("ecr_magnet: need hot-spot >= 0, |H_d| >= 0, knee field > 0, 0 < min Br fraction <= 1")
    T_max_use = limit_value(limits, grade, "T_max_use_C")
    Q = f * P
    sol = solve_node_temperature(Q, ci.paths())
    T_mag = sol["T_K"] - T_ZERO_C_K + hs
    checks = [_margin_check("magnet_max_use_temperature", T_max_use - T_mag, "K",
                            {"T_magnet_C": T_mag, "T_max_use_C": T_max_use, "grade": grade})]
    try:
        frac = magnet_property_fraction(T_mag, grade, limits)
        checks.append(_margin_check("reversible_Br_loss", frac - Br_min, "-",
                                    {"Br_fraction": frac, "required_fraction": Br_min}))
    except ValueError as e:
        checks.append(_nd("reversible_Br_loss", str(e)))
    have_hcj = _has_value(limits, grade, "Hcj_min_20C_A_per_m") and _has_value(limits, grade, "beta_Hcj_pct_per_C")
    if have_hcj:
        Hcj20 = limit_value(limits, grade, "Hcj_min_20C_A_per_m")
        try:
            Hcj_knee_T = Hcj20 * magnet_property_fraction(Hk_T, grade, limits, "beta_Hcj_pct_per_C")
        except ValueError as e:        # knee temperature outside the Hcj coefficient range: say so, never skip silently
            Hcj_knee_T = None
            checks.append(_nd("knee_field_Hcj_consistency", f"knee field vs minimum Hcj not evaluated: {e}"))
        if Hcj_knee_T is not None and Hk > Hcj_knee_T:
            raise ValueError(f"ecr_magnet: knee field {Hk} A/m exceeds the grade's minimum Hcj {Hcj_knee_T:.6g} A/m "
                             f"at {Hk_T} C: inconsistent inputs")
    if Hk_T < T_mag:
        checks.append(_nd("irreversible_loss_knee", f"knee field given at {Hk_T} C, below the magnet temperature "
                          f"{T_mag:.6g} C (knee fields fall with temperature)"))
    else:
        checks.append(_margin_check("irreversible_loss_knee", Hk - Hd, "A/m",
                                    {"knee_field_A_per_m": Hk, "knee_T_C": Hk_T, "demag_field_A_per_m": Hd}))
    necessary = None
    if have_hcj:
        try:
            Hcj_T = limit_value(limits, grade, "Hcj_min_20C_A_per_m") * magnet_property_fraction(
                T_mag, grade, limits, "beta_Hcj_pct_per_C")
            necessary = {"Hcj_min_at_T_A_per_m": Hcj_T, "satisfied": Hd < Hcj_T}
            if Hd >= Hcj_T:
                checks.append(_margin_check("demag_field_below_Hcj", Hcj_T - Hd, "A/m", {"Hcj_min_at_T_A_per_m": Hcj_T}))
        except ValueError as e:
            necessary = {"not_evaluated": str(e)}
    return {"heat_W": {"to_magnets_W": Q}, "T_node": sol, "Hcj_necessary_condition": necessary, "checks": checks}


# ----------------------------------------------------------------------------------------------- RF / ECR sources
def _source_fractions(ci: _ComponentInputs) -> dict:
    fr = {k: _fraction(ci.num(k), f"{ci.c}.{k}") for k in
          ("heat_fraction_antenna_copper", "heat_fraction_coupler_dielectric", "heat_fraction_plasma_to_structure")}
    return fr


def _check_source(ci: _ComponentInputs, limits: dict, mission: dict) -> dict:
    P = ci.num("rf_power_W")
    if P < 0:
        raise ValueError(f"{ci.c}: RF power must be >= 0")
    fr = _source_fractions(ci)
    if sum(fr.values()) > 1.0:
        raise ValueError(f"{ci.c}: heat fractions sum to {sum(fr.values())} > 1 (conservation)")
    rid = ci.ident("structure_limit_record")
    T_lim = limit_value(limits, rid, "T_max_C", "component_temperature_limit")
    hs = ci.num("hot_spot_allowance_K")
    if hs < 0:
        raise ValueError(f"{ci.c}: hot-spot allowance must be >= 0")
    heat = {k.replace("heat_fraction_", "") + "_W": v * P for k, v in fr.items()}
    Q = sum(heat.values())
    sol = solve_node_temperature(Q, ci.paths())
    T_C = sol["T_K"] - T_ZERO_C_K
    return {"heat_W": {**heat, "total_W": Q}, "T_node": sol,
            "checks": [_margin_check("structure_temperature", T_lim - (T_C + hs), "K",
                                     {"T_mean_C": T_C, "T_hot_spot_C": T_C + hs, "limit_C": T_lim})]}


# ----------------------------------------------------------------------------------------------- cathode (LaB6)
def richardson_current_density(T_K: float, s: dict) -> float:
    """J = P T^2 exp(-(phi0 + alpha T)/(k T / e)) [A/m^2] for one Goebel & Katz Table 6-1 parameter set."""
    if T_K <= 0:
        raise ValueError("T must be > 0 K")
    phi = s["phi0_eV"] + s["alpha_eV_per_K"] * T_K
    return s["prefactor_A_per_m2K2"] * T_K * T_K * math.exp(-phi / (EV_PER_K * T_K))


def emitter_temperature_K(J_A_m2: float, s: dict, T_lo: float = 300.0, T_hi: float = 4000.0) -> float:
    """Temperature at which a parameter set emits J (monotone in T). The [300, 4000] K bracket is numerical only."""
    if J_A_m2 <= 0:
        raise ValueError("current density must be > 0")
    if not richardson_current_density(T_lo, s) <= J_A_m2 <= richardson_current_density(T_hi, s):
        raise ValueError(f"J = {J_A_m2} A/m^2 not reached within the numerical bracket [{T_lo}, {T_hi}] K")
    lo, hi = T_lo, T_hi
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if richardson_current_density(mid, s) < J_A_m2:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-9:
            break
    return 0.5 * (lo + hi)


def emitter_temperature_envelope(J_A_m2: float, limits: dict) -> dict:
    """Emitter temperature for J under every LaB6 set of Goebel & Katz Table 6-1 (no set is selected)."""
    sets = limit_value(limits, "lab6_richardson_goebel_table6_1", "sets", "thermionic_parameter_sets")
    T = {s["id"]: emitter_temperature_K(J_A_m2, s) for s in sets}
    return {"per_set_K": T, "T_min_K": min(T.values()), "T_max_K": max(T.values())}


def lab6_evaporation_life_h(insert_mass_kg: float, usable_fraction: float, evaporation_rate_kg_m2s: float,
                            emitting_area_m2: float) -> float:
    """Goebel & Katz sec. 6.8.4: life = usable fraction x insert mass / (evaporation rate x emitting area)."""
    if insert_mass_kg <= 0 or emitting_area_m2 <= 0 or evaporation_rate_kg_m2s < 0:
        raise ValueError("insert mass and area must be > 0 and the evaporation rate >= 0")
    _fraction(usable_fraction, "usable_fraction")
    if evaporation_rate_kg_m2s == 0:
        return math.inf
    return usable_fraction * insert_mass_kg / (evaporation_rate_kg_m2s * emitting_area_m2) / 3600.0


def lab6_evaporation_rate(T_K: float, limits: dict) -> float:
    """Evaporation rate from the sourced table (log-linear interpolation in T, inside the table only)."""
    ts = limit_value(limits, "lab6_evaporation_rate", "T_K", "emitter_evaporation_rate")
    rs = limit_value(limits, "lab6_evaporation_rate", "rate_kg_m2s", "emitter_evaporation_rate")
    if any(r <= 0 for r in rs):
        raise ValueError("tabulated evaporation rates must be > 0 for log interpolation")
    return math.exp(_interp(T_K, ts, [math.log(r) for r in rs]))


def _check_cathode(ci: _ComponentInputs, limits: dict, mission: dict) -> dict:
    Pk, fk = ci.num("keeper_power_W"), _fraction(ci.num("keeper_heat_fraction_to_cathode"), "cathode.keeper_heat_fraction")
    Ph, duty = ci.num("heater_power_W"), _fraction(ci.num("heater_steady_state_duty"), "cathode.heater_steady_state_duty")
    Pem, Ie, Aem = ci.num("emitter_plasma_heating_W"), ci.num("emission_current_A"), ci.num("emitting_area_m2")
    m_ins, pO2 = ci.num("insert_mass_kg"), ci.num("emitter_pO2_Torr")
    cyc_q, cyc_req = ci.num("heater_qualified_cycles"), ci.num("required_heater_cycles")
    if min(Pk, Ph, Pem, pO2, cyc_q, cyc_req) < 0 or Ie <= 0 or Aem <= 0 or m_ins <= 0:
        raise ValueError("cathode: powers, pO2 and cycle counts must be >= 0; emission current, area and insert mass > 0")
    rid = ci.ident("assembly_limit_record")
    T_lim = limit_value(limits, rid, "T_max_C", "component_temperature_limit")
    hs = ci.num("hot_spot_allowance_K")
    if hs < 0:
        raise ValueError("cathode: hot-spot allowance must be >= 0")
    heat = {"keeper_W": fk * Pk, "heater_W": duty * Ph, "emitter_plasma_W": Pem}
    Q = sum(heat.values())
    sol = solve_node_temperature(Q, ci.paths())
    T_C = sol["T_K"] - T_ZERO_C_K
    checks = [_margin_check("assembly_temperature", T_lim - (T_C + hs), "K",
                            {"T_mean_C": T_C, "T_hot_spot_C": T_C + hs, "limit_C": T_lim})]
    env = emitter_temperature_envelope(Ie / Aem, limits)
    # evaporation: the hottest set is the conservative one; poisoning: the coolest set is the conservative one
    rate = lab6_evaporation_rate(env["T_max_K"], limits)
    f_use = limit_value(limits, "lab6_usable_fraction_goebel", "usable_fraction")
    life = lab6_evaporation_life_h(m_ins, f_use, rate, Aem)
    req = mission["required_firing_h"]
    checks.append(_margin_check("emitter_evaporation_life", life - req, "h",
                                {"T_emitter_K": env["T_max_K"], "rate_kg_m2s": rate, "life_h": life, "required_h": req}))
    T_ok = limit_value(limits, "lab6_poisoning_goebel", "T_no_degradation_min_C")
    p_ok = limit_value(limits, "lab6_poisoning_goebel", "pO2_no_degradation_max_Torr")
    T_emit_min_C = env["T_min_K"] - T_ZERO_C_K
    if T_emit_min_C >= T_ok and pO2 <= p_ok:
        checks.append({"name": "emitter_O2_poisoning_screen", "status": PASS, "margin": None,
                       "why": f"inside the reported no-degradation point (T >= {T_ok} C, pO2 <= {p_ok} Torr)"})
    else:
        checks.append(_nd("emitter_O2_poisoning_screen", "outside the single reported no-degradation point "
                          f"(T >= {T_ok} C and pO2 <= {p_ok} Torr); requires poisoning data for this condition",
                          T_emitter_min_C=T_emit_min_C, pO2_Torr=pO2))
    checks.append(_margin_check("heater_cycles", cyc_q - cyc_req, "cycles", {"qualified": cyc_q, "required": cyc_req}))
    return {"heat_W": {**heat, "total_W": Q}, "T_node": sol, "emitter_temperature": env, "checks": checks}


_CHECKS = {"hall_magnet": _check_hall_magnet, "hall_discharge": _check_hall_discharge, "ecr_magnet": _check_ecr_magnet,
           "rf_source": _check_source, "ecr_source": _check_source, "cathode": _check_cathode}


# ----------------------------------------------------------------------------------------------- entry point
def check_feasibility(inputs: dict, limits: dict, components: list[str], contract: dict | None = None) -> dict:
    """Thermal/life margins per component. Refuses (ValueError) on any missing/unsourced input or TBD limit.

    inputs = {'mission': {'required_firing_h': record}, '<component>': {...}} for every listed component."""
    contract = contract if contract is not None else load_inputs_contract()
    validate_limits(limits)
    if not components:
        raise ValueError("name the components to check (the architecture decides which exist)")
    if len(set(components)) != len(components):
        raise ValueError("duplicate component names")
    unknown = [c for c in components if c not in THERMAL_COMPONENTS]
    if unknown:
        raise ValueError(f"unknown thermal components {unknown}; known: {THERMAL_COMPONENTS}")
    extra = set(inputs) - set(components) - {"mission"}
    if extra:
        raise ValueError(f"inputs given for components not requested: {sorted(extra)}")
    mission_raw = inputs.get("mission")
    if not isinstance(mission_raw, dict) or set(mission_raw) != set(contract["mission"]):
        raise ValueError(f"mission inputs must be exactly {sorted(contract['mission'])}")
    mission = {k: _number(mission_raw[k], s["unit"], f"mission.{k}") for k, s in contract["mission"].items()}
    if mission["required_firing_h"] <= 0:
        raise ValueError("mission.required_firing_h must be > 0")
    cis = {}
    for c in components:
        if c not in inputs:
            raise ValueError(f"{c}: no inputs given (all of {sorted(contract['components'][c]['inputs'])} are required)")
        cis[c] = _ComponentInputs(c, inputs[c], contract)
    if "ecr_source" in cis and "ecr_magnet" in cis:        # both take heat from the same ECR power
        P_s, P_m = cis["ecr_source"].num("rf_power_W"), cis["ecr_magnet"].num("ecr_rf_power_W")
        if P_s != P_m:
            raise ValueError(f"ecr_source.rf_power_W ({P_s}) and ecr_magnet.ecr_rf_power_W ({P_m}) must be the same power")
        s = sum(_source_fractions(cis["ecr_source"]).values()) + cis["ecr_magnet"].num("heat_fraction_to_magnets")
        if s > 1.0:
            raise ValueError(f"ECR heat fractions (source + magnets) sum to {s} > 1 (conservation)")
    results = {}
    for c in components:
        r = _CHECKS[c](cis[c], limits, mission)
        r["bus_power_components"] = contract["components"][c]["bus_power_components"]
        st = [k["status"] for k in r["checks"]]
        r["status"] = FAIL if FAIL in st else (NOT_DEMONSTRATED if NOT_DEMONSTRATED in st else PASS)
        results[c] = r
    sts = [r["status"] for r in results.values()]
    overall = FAIL if FAIL in sts else (NOT_DEMONSTRATED if NOT_DEMONSTRATED in sts else OVERALL_PASS)
    return {"schema": RESULT_SCHEMA, "status": overall, "components": results,
            "limits_schema": limits.get("schema"), "limits_sha256": _canonical_sha256(limits),
            "not_covered": list(NOT_COVERED),
            "note": "PASS_CHECKED_ITEMS means no violation among the implemented checks; it is not a thermal "
                    "qualification (see not_covered) and carries the evidence levels of its inputs"}
