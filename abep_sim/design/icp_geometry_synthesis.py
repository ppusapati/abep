"""F6 downstream ICP geometry synthesis (owner directive A9.7, lane fo_a9_7_f6_icp_geometry).

Framework now; the geometry SEARCH runs once P1 / P2 evidence exists (A9.7 F6: "Once P1/P2 evidence exists, search the
downstream ICP physical geometry ... Never optimize ICP electron current alone").

What is here
  * the F6 design vector x_ICP (DESIGN_VARIABLES): standoff, clear aperture, module envelope, open-frame fraction,
    antenna geometry, collector geometry and envelope shell thicknesses. Every bound is TBD with the source that must
    supply it (no bound is invented); physical-consistency constraints (positivity, nesting inside the envelope,
    no overlap with H-1) are hard and fail closed (GeometryConstraintError);
  * a multi-objective evaluator (evaluate) that SIMULTANEOUSLY computes or refuses all eight A9.7 F6 objectives
    (OBJECTIVES): electron-current capacity (P1 icp45a_evaluate result), plume interception (P3 interception record
    with a MEASURED angular distribution), RF impedance / matching (P2 measured impedance map), RF power (P1
    P_RF,delivered at the capacity point), Hall magnetic-field disturbance (measured or cited-model record only),
    view-factor obstruction (P3 ray-quadrature view factors, computable now, labelled geometric), collector heating
    (P3 q_collector on measured inputs) and module mass (geometry x cited densities). It returns the full vector,
    one status per objective; nothing is ever defaulted;
  * the fail-closed Pareto filter (pareto_filter): it REFUSES to rank (status REFUSED_INCOMPLETE, no set returned)
    whenever any required objective of any candidate is not rankable. Chosen behaviour (A9.7 F6 lane brief offered
    "refuse" or "rank the evaluated subset with an INCOMPLETE flag"): REFUSE. Reason: a subset ranking today would
    rank on geometry alone (view factor + mass), i.e. exactly the single-property optimisation A9.7 forbids for
    electron current, and an INCOMPLETE-flagged order is easily quoted without its flag. The required set is the
    module constant REQUIRED_OBJECTIVES (all eight); callers cannot pass a smaller set;
  * a deterministic grid search driver (search) that refuses unless every design variable has a sourced bound
    (no TBD bound is ever replaced by an assumed one, A9.7 F7 / optimizer_rule);
  * the geometric-only screening (geometric_screening): view-factor obstruction and envelope shell areas vs geometry,
    labelled GEOMETRIC_SCREENING_NOT_A_DESIGN; module mass stays NOT_EVALUATED (materials / thicknesses TBD) and only
    the derived ceiling "AL-05 allocation / envelope shell area" is reported.

What it is not: an ICP design, a selection, a ranking, a PASS, an ICP-45 evaluation, a thermal result, a Hall
prediction. It imports the P1 / P2 / P3 code by file path (they are not packages) and modifies none of them; it is not
wired into abep_sim/archengine.py (goldens cannot move).
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LANE = "fo_a9_7_f6_icp_geometry"
LANE_KEY = "A9_7_F6"
DIRECTIVE = "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md"
A9_STATUS = "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE"
SCREENING_LABEL = "GEOMETRIC_SCREENING_NOT_A_DESIGN"

P3_LIB_REL = "docs/experiments/hall_icp/p3_coupled_thermal/p3_thermal_lib.py"
P3_JSON_REL = "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json"
P1_REDUCER_REL = "docs/experiments/hall_icp/p1_icp_bench/p1_reducer.py"
P2_FRAMEWORK_REL = "docs/experiments/hall_icp/p2_impedance_map/p2_framework.py"
MP_V2_REL = "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json"
P4_REL = "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json"

# ------------------------------------------------------------------------------------------------ statuses
EVALUATED = "EVALUATED"                                      # rankable: evidence-backed value
EVALUATED_GEOMETRIC = "EVALUATED_GEOMETRIC"                  # rankable: pure geometry on a non-assumed H-1 geometry
EVALUATED_GEOMETRIC_CONDITIONAL = "EVALUATED_GEOMETRIC_CONDITIONAL"   # geometry on an ASSUMED H-1 geometry: not rankable
NOT_EVALUATED = "NOT_EVALUATED"
TBD_AFTER_IMPEDANCE_MAP = "TBD_AFTER_IMPEDANCE_MAP"
TBD = "TBD"
SYNTHETIC = "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE"
OBJECTIVE_STATUSES = (EVALUATED, EVALUATED_GEOMETRIC, EVALUATED_GEOMETRIC_CONDITIONAL, NOT_EVALUATED,
                      TBD_AFTER_IMPEDANCE_MAP, TBD, SYNTHETIC)
RANKABLE_STATUSES = (EVALUATED, EVALUATED_GEOMETRIC)
PARETO_STATUSES = ("REFUSED_INCOMPLETE", "REFUSED_NO_FEASIBLE_CANDIDATE", "PARETO_SET_COMPUTED_NOT_A_SELECTION")
SYN_CLASS = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"               # P3 / repository synthetic evidence class
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation", "published analog", SYN_CLASS)
TBD_PREFIXES = ("TBD", "PENDING")


class F6Error(ValueError):
    """Malformed F6 input (refused)."""


class GeometryConstraintError(F6Error):
    """A hard geometric-consistency constraint is violated (fail closed; the vector is infeasible)."""


class SearchRefused(F6Error):
    """The search cannot run: a bound is TBD / unsourced (never replaced by an assumed value)."""


def _is_tbd(v):
    return v is None or (isinstance(v, str) and v.strip().upper().startswith(TBD_PREFIXES))


def _finite(x, what):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
        raise F6Error(f"{what} must be a finite real number, got {x!r}")
    return float(x)


# ------------------------------------------------------------------------------------------------ path imports
_MODS = {}


def _load(name, rel):
    """Import a non-package module by file path (read-only; registered under an F6-private name)."""
    if name not in _MODS:
        spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod          # dataclasses resolve annotations through sys.modules
        spec.loader.exec_module(mod)
        _MODS[name] = mod
    return _MODS[name]


def p3_lib():
    return _load("abep_f6_p3_thermal_lib", P3_LIB_REL)


def p1_reducer():
    return _load("abep_f6_p1_reducer", P1_REDUCER_REL)


def p2_framework():
    return _load("abep_f6_p2_framework", P2_FRAMEWORK_REL)


def _read_json(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ design vector
def _var(i, sym, name, units, kind, bound_source, maps_to, used_by):
    return {"id": i, "symbol": sym, "name": name, "units": units, "kind": kind,
            "bounds": {"lo": TBD, "hi": TBD, "status": TBD,
                       "requires": bound_source, "evidence_class": None},
            "maps_to": maps_to, "used_by": used_by}


DESIGN_VARIABLES = (
    _var("F6-X-01", "L_standoff", "axial standoff of the ICP module upstream face downstream of IP-EXIT", "m",
         "continuous", "KC-1 / ICP module drawing (ICD ICP-02) and the H-1 exit-plane definition IP-EXIT (F5 "
         "H1F-EX-01 FREEZE_CANDIDATE; standoff H1F-EX-03 TBD)", ["P3-G-01"],
         ["view_factor_obstruction", "plume_interception_fraction", "hall_b_field_disturbance"]),
    _var("F6-X-02", "r_aperture", "ICP clear aperture radius (plume passage; open-tube coaxial first build, A9.3 "
         "OQ-VI-03)", "m", "continuous", "frozen H-1 channel OD (F5 H1F-EX-04 TBD_AFTER_EVIDENCE) and the MEASURED "
         "plume angular "
         "distribution (P3-H-03, Phase-1 Faraday probe) (ICD ICP-04)", ["P3-G-02"],
         ["view_factor_obstruction", "plume_interception_fraction", "module_mass"]),
    _var("F6-X-03", "r_module", "ICP module envelope outer radius (minimum necessary downstream obstruction, A9.2)",
         "m", "continuous", "module envelope (ICD ICP-07, ICP-47)", ["P3-G-03"],
         ["view_factor_obstruction", "module_mass"]),
    _var("F6-X-04", "L_module", "ICP module envelope axial length", "m", "continuous", "module envelope (ICD ICP-07)",
         ["P3-G-04"], ["view_factor_obstruction", "plume_interception_fraction", "module_mass"]),
    _var("F6-X-05", "tau_support", "open-frame support geometric open-area fraction (gray, direction-independent "
         "approximation of the P3 engine)", "-", "continuous", "support drawing (ICD ICP-47)", ["P3-G-05"],
         ["view_factor_obstruction", "plume_interception_fraction", "module_mass"]),
    _var("F6-X-06", "N_ant", "antenna number of turns", "-", "integer", "ICP antenna design (P1 bench build; P2 "
         "impedance map per geometry)", [], ["module_mass", "rf_match_loss_fraction"]),
    _var("F6-X-07", "r_ant", "antenna coil mean radius", "m", "continuous", "ICP antenna design (P1 bench build)", [],
         ["module_mass", "rf_match_loss_fraction"]),
    _var("F6-X-08", "L_ant", "antenna axial length", "m", "continuous", "ICP antenna design (P1 bench build)", [],
         ["rf_match_loss_fraction"]),
    _var("F6-X-09", "d_ant", "antenna conductor diameter", "m", "continuous", "ICP antenna design (P1 bench build; "
         "P2 CAL-P2-08 cold resistance)", [], ["module_mass"]),
    _var("F6-X-10", "r_coll_in", "collector inner radius", "m", "continuous", "ICP collector design (ICD ICP-21; "
         "P3-G-07)", ["P3-G-07"], ["module_mass", "collector_heating"]),
    _var("F6-X-11", "r_coll_out", "collector outer radius", "m", "continuous", "ICP collector design (ICD ICP-21; "
         "P3-G-07)", ["P3-G-07"], ["module_mass", "collector_heating"]),
    _var("F6-X-12", "z_coll", "collector axial position from the ICP module upstream face", "m", "continuous",
         "ICP collector design (ICD ICP-21; P3-G-07)", ["P3-G-07"], ["collector_heating"]),
    _var("F6-X-13", "t_coll", "collector thickness", "m", "continuous", "ICP collector design (ICD ICP-21)", [],
         ["module_mass"]),
    _var("F6-X-14", "t_bore", "bore (r = r_aperture) envelope shell thickness", "m", "continuous",
         "ICP module drawing (ICD ICP-07)", [], ["module_mass"]),
    _var("F6-X-15", "t_outer", "outer (r = r_module) envelope shell thickness", "m", "continuous",
         "ICP module drawing (ICD ICP-07)", [], ["module_mass"]),
    _var("F6-X-16", "t_up", "upstream (Hall-facing) end plate thickness", "m", "continuous",
         "ICP module drawing (ICD ICP-07, ICP-47)", [], ["module_mass"]),
    _var("F6-X-17", "t_down", "downstream end plate thickness", "m", "continuous", "ICP module drawing (ICD ICP-07)",
         [], ["module_mass"]),
)
VAR_BY_SYMBOL = {v["symbol"]: v for v in DESIGN_VARIABLES}
ENVELOPE_SYMBOLS = ("L_standoff", "r_aperture", "r_module", "L_module", "tau_support")
SHELL_SYMBOLS = {"bore": "t_bore", "outer": "t_outer", "up": "t_up", "down": "t_down"}
MASS_COMPONENTS = ("bore", "outer", "up", "down", "antenna", "collector")

HARD_CONSTRAINTS = (
    ("HC-01", "every given length > 0, N_ant a positive integer, 0 <= tau_support < 1",
     "geometric validity (P3 Body domain: 0 <= tau < 1)"),
    ("HC-02", "r_module > r_aperture", "annular envelope (P3 Body: r_in < r_out)"),
    ("HC-03", "L_standoff > 0 (the ICP envelope lies wholly downstream of IP-EXIT, z_H1 <= 0)",
     "no overlap with the H-1 body (P3 check_geometry)"),
    ("HC-04", "r_aperture <= r_ant - d_ant/2 and r_ant + d_ant/2 <= r_module; L_ant <= L_module",
     "antenna inside the module envelope (definition of the envelope, P3-G-03 / P3-G-04)"),
    ("HC-05", "0 <= r_coll_in < r_coll_out <= r_module; 0 <= z_coll and z_coll + t_coll <= L_module",
     "collector inside the module envelope (definition of the envelope)"),
    ("HC-06", "every shell thickness < its available envelope dimension (t_bore + t_outer < r_module - r_aperture; "
              "t_up + t_down < L_module)", "shells fit the envelope"),
)


def validate_design_vector(x):
    """x = {'geometry_id': str, '<symbol>': value | 'TBD...'}. Returns (values, tbd_symbols). Unknown symbols, a
    missing geometry_id or non-finite values are refused; every hard constraint whose inputs are all given is checked
    and a violation raises GeometryConstraintError (fail closed). A TBD value is never defaulted."""
    if not isinstance(x, dict) or not isinstance(x.get("geometry_id"), str) or not x["geometry_id"].strip():
        raise F6Error("design vector needs a non-empty 'geometry_id'")
    unknown = sorted(set(x) - set(VAR_BY_SYMBOL) - {"geometry_id"})
    if unknown:
        raise F6Error(f"unknown design variables {unknown}")
    vals, tbd = {}, []
    for sym, var in VAR_BY_SYMBOL.items():
        v = x.get(sym)
        if _is_tbd(v):
            tbd.append(sym)
            continue
        f = _finite(v, sym)
        if var["kind"] == "integer" and (f != int(f) or f < 1):
            raise GeometryConstraintError(f"HC-01: {sym} must be a positive integer, got {v!r}")
        vals[sym] = f
    g = vals.get
    for sym, f in vals.items():
        if sym == "tau_support":
            if not (0.0 <= f < 1.0):
                raise GeometryConstraintError(f"HC-01: tau_support must lie in [0, 1), got {f}")
        elif sym in ("r_coll_in", "z_coll"):
            if f < 0:
                raise GeometryConstraintError(f"HC-01: {sym} must be >= 0, got {f}")
        elif f <= 0:
            raise GeometryConstraintError(f"HC-01: {sym} must be > 0, got {f}")

    def need(*s):
        return all(k in vals for k in s)
    if need("r_aperture", "r_module") and not g("r_module") > g("r_aperture"):
        raise GeometryConstraintError("HC-02: r_module must exceed r_aperture")
    if need("r_ant", "d_ant", "r_aperture", "r_module") and not (
            g("r_aperture") <= g("r_ant") - g("d_ant") / 2 and g("r_ant") + g("d_ant") / 2 <= g("r_module")):
        raise GeometryConstraintError("HC-04: antenna conductor outside the radial envelope")
    if need("L_ant", "L_module") and g("L_ant") > g("L_module"):
        raise GeometryConstraintError("HC-04: antenna longer than the module")
    if need("r_coll_in", "r_coll_out") and not g("r_coll_in") < g("r_coll_out"):
        raise GeometryConstraintError("HC-05: r_coll_in must be < r_coll_out")
    if need("r_coll_out", "r_module") and g("r_coll_out") > g("r_module"):
        raise GeometryConstraintError("HC-05: collector outside the radial envelope")
    if need("z_coll", "t_coll", "L_module") and g("z_coll") + g("t_coll") > g("L_module"):
        raise GeometryConstraintError("HC-05: collector outside the axial envelope")
    if need("t_bore", "t_outer", "r_aperture", "r_module") and \
            not g("t_bore") + g("t_outer") < g("r_module") - g("r_aperture"):
        raise GeometryConstraintError("HC-06: radial shells do not fit the envelope")
    if need("t_up", "t_down", "L_module") and not g("t_up") + g("t_down") < g("L_module"):
        raise GeometryConstraintError("HC-06: end plates do not fit the envelope")
    return vals, tbd


# ------------------------------------------------------------------------------------------------ objectives
def _obj(name, direction, units, source, rule):
    return {"name": name, "direction": direction, "units": units, "source": source, "admission_rule": rule}


OBJECTIVES = (
    _obj("electron_current_capacity", "maximize", "A",
         "P1 icp45a_evaluate (" + P1_REDUCER_REL + "): I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF, "
         "OWNER_DECIDED A9.4 P1Q-10 / A9.5 P1Q-16",
         "EVALUATED only from a P1 result with status EVALUATED_ENGINEERING_ONLY bound to this geometry_id; "
         "NOT_EVALUATED otherwise (ICP45 NOT_EVALUATED until I_d,max,H1 is registered and P1 data exist)"),
    _obj("plume_interception_fraction", "minimize", "-",
         "P3 plume_interception_record (" + P3_LIB_REL + "): share of the H-1 channel-exit ion current first "
         "intercepted by the ICP assembly",
         "EVALUATED only with a MEASURED angular current distribution (P3-H-03, Phase-1 Faraday probe); a test / "
         "assumed distribution is NOT_EVALUATED; synthetic -> SYNTHETIC_TEST_ONLY_NOT_EVIDENCE"),
    _obj("rf_match_loss_fraction", "minimize", "-",
         "P2 measured impedance map (" + P2_FRAMEWORK_REL + ", p2_impedance_map_v1): worst-case "
         "P_line/match,loss / (P_line/match,loss + P_delivered) over the map's numeric points",
         "EVALUATED only from a validated MEASURED map bound to this geometry_id (binding carries the map "
         "content_sha256); TBD_AFTER_IMPEDANCE_MAP otherwise"),
    _obj("rf_power_delivered", "minimize", "W",
         "P1 derive_rf: P_RF,delivered at RP-CPL minus the VERIFIED line/match loss at the ICP45 capacity point",
         "EVALUATED only for kind P_RF_DELIVERED at the same record as the capacity objective; upper bounds and "
         "anything named as a bus quantity are refused (P_mains is never P_bus)"),
    _obj("hall_b_field_disturbance", "minimize", "-",
         "measured or cited-field-model record of the ICP-induced relative change of the H-1 magnetic field",
         "TBD unless a measured record or a cited field model (H-1 magnetic circuit B(r,z) incl. the downstream near "
         "field, ICP component permeabilities) bound to this geometry_id exists"),
    _obj("view_factor_obstruction", "minimize", "m2",
         "P3 view_factors (" + P3_LIB_REL + "): sum over the H-1 front zones of A_z F_z->ICP (diffuse radiative "
         "view lost to the ICP assembly)",
         "computed now (geometric); EVALUATED_GEOMETRIC only on a non-assumed H-1 front geometry record, "
         "EVALUATED_GEOMETRIC_CONDITIONAL (not rankable) on the assumed H2-5 evaluation geometry"),
    _obj("collector_heating", "minimize", "W",
         "P3 q_collector (" + P3_LIB_REL + "): Goebel & Katz particle heating of the collector",
         "EVALUATED only when q_collector returns basis MEASURED_INPUTS_ONLY on P1 records bound to this geometry_id; "
         "NOT_EVALUATED otherwise (needs P1 collector currents and T_e / V_plasma, P3Q-01 OPEN)"),
    _obj("module_mass", "minimize", "kg",
         "geometry x cited densities: sum_i A_i t_i rho_i (envelope shells) + antenna + collector",
         "EVALUATED only when every component has its geometry and a cited density record; NOT_EVALUATED otherwise "
         "(materials OPEN: FINAL_COLLECTOR_MATERIAL OPEN in P4; dielectric / housing / antenna materials TBD)"),
)
OBJ_BY_NAME = {o["name"]: o for o in OBJECTIVES}
REQUIRED_OBJECTIVES = tuple(o["name"] for o in OBJECTIVES)
DENSITY_EVIDENCE = ("measured", "digitized", "published analog")


def _result(name, status, value=None, reason=None, **extra):
    o = OBJ_BY_NAME[name]
    if status not in OBJECTIVE_STATUSES:
        raise F6Error(f"internal: status {status!r}")
    r = {"status": status, "value": value, "units": o["units"], "direction": o["direction"],
         "rankable": status in RANKABLE_STATUSES}
    if reason:
        r["reason"] = reason
    r.update(extra)
    return r


def _binding(b, geometry_id, what, required=()):
    """A geometry binding record {'geometry_id', 'source', ...}: refuses a binding for another geometry."""
    if not isinstance(b, dict):
        raise F6Error(f"{what}: binding must be an object with geometry_id and source")
    miss = [k for k in ("geometry_id", "source") + tuple(required) if not b.get(k)]
    if miss:
        raise F6Error(f"{what}: binding lacks {miss}")
    if b["geometry_id"] != geometry_id:
        raise F6Error(f"{what}: bound to geometry {b['geometry_id']!r}, not {geometry_id!r}")
    return b


def _refuse_bus(obj, what, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if "bus" in str(k).lower().replace("_", ""):
                raise F6Error(f"{what}: field {path + str(k)!r} reads as a bus quantity (P_mains / P_RF is never P_bus)")
            _refuse_bus(v, what, path + str(k) + ".")


# ---- electron-current capacity (P1)
def capacity_objective(p1_result, binding, geometry_id):
    """From a P1 icp45a_evaluate() result. Only status EVALUATED_ENGINEERING_ONLY (Ar, engineering-only) bound to
    this geometry gives a value; the margin M_n,LB is carried, never turned into a PASS."""
    name = "electron_current_capacity"
    if p1_result is None:
        return _result(name, NOT_EVALUATED, reason="no P1 ICP45 capacity result (P1 has no data; ICP45 NOT_EVALUATED "
                       "until I_d,max,H1 is registered - A9.4 / A9.5)")
    if not isinstance(p1_result, dict) or p1_result.get("status") not in p1_reducer().ICP45A_STATUSES:
        raise F6Error("capacity: not a P1 icp45a_evaluate() result")
    st = p1_result["status"]
    if st == "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE":
        _binding(binding, geometry_id, "capacity")
        return _result(name, SYNTHETIC, value=p1_result.get("I_e_cap_A"),
                       reason="P1 synthetic candidates: arithmetic only")
    if st != "EVALUATED_ENGINEERING_ONLY":
        return _result(name, NOT_EVALUATED, reason="P1 ICP45 status %s: %s" % (st, p1_result.get("reason", "")))
    b = _binding(binding, geometry_id, "capacity", ("p1_record_id",))
    if b["p1_record_id"] != p1_result.get("I_e_cap_record"):
        raise F6Error("capacity: binding p1_record_id %r != P1 I_e_cap_record %r"
                      % (b["p1_record_id"], p1_result.get("I_e_cap_record")))
    return _result(name, EVALUATED, value=_finite(p1_result["I_e_cap_A"], "I_e_cap_A"),
                   basis="P1 EVALUATED_ENGINEERING_ONLY (Ar engineering-only; ICP-45N on N2 still required)",
                   M_n_lower=p1_result.get("M_n_lower"), I_d_max_H1_A=p1_result.get("I_d_max_H1_A"),
                   p1_record_id=b["p1_record_id"], source=b["source"])


# ---- RF power (P1 derive_rf at the capacity point)
def rf_power_objective(p1_rf, binding, geometry_id, capacity):
    name = "rf_power_delivered"
    if p1_rf is None:
        return _result(name, NOT_EVALUATED, reason="no P1 derive_rf record at an evaluated ICP45 capacity point")
    _refuse_bus(p1_rf, "rf_power")
    _refuse_bus(binding, "rf_power")
    kind = p1_rf.get("P_delivered_kind")
    if kind != "P_RF_DELIVERED":
        return _result(name, NOT_EVALUATED, reason=f"P1 P_delivered_kind {kind!r}: only a verified-loss "
                       "P_RF_DELIVERED counts (upper bounds are never an objective value)")
    b = _binding(binding, geometry_id, "rf_power", ("p1_record_id",))
    if capacity.get("status") != EVALUATED or capacity.get("p1_record_id") != b["p1_record_id"]:
        return _result(name, NOT_EVALUATED, reason="P_RF,delivered is defined at the evaluated ICP45 capacity point; "
                       "the capacity objective is not EVALUATED at this record")
    return _result(name, EVALUATED, value=_finite(p1_rf["P_delivered_W"], "P_delivered_W"),
                   basis="P1 derive_rf P_RF_DELIVERED (generator / 50-ohm side of the local match minus the verified "
                         "line/match loss)", p1_record_id=b["p1_record_id"], source=b["source"])


# ---- RF matching (P2 map)
def rf_matching_objective(p2_map, binding, geometry_id):
    name = "rf_match_loss_fraction"
    if p2_map is None:
        return _result(name, TBD_AFTER_IMPEDANCE_MAP, reason="no P2 impedance map (RF ratings / matching "
                       "TBD_AFTER_IMPEDANCE_MAP; P2 has no data)")
    fw = p2_framework()
    fw.validate_map(p2_map)
    b = _binding(binding, geometry_id, "rf_matching", ("map_content_sha256",))
    if b["map_content_sha256"] != p2_map["content_sha256"]:
        raise F6Error("rf_matching: binding map_content_sha256 does not match the map")
    fr = []
    for p in p2_map["points"]:
        lo, de = p.get("P_line_match_loss_W"), p.get("P_delivered_W")
        if isinstance(lo, (int, float)) and isinstance(de, (int, float)) and not isinstance(lo, bool) \
                and not isinstance(de, bool) and lo >= 0 and de >= 0 and lo + de > 0:
            fr.append(lo / (lo + de))
    if p2_map["data_class"] == "synthetic_test":
        return _result(name, SYNTHETIC, value=max(fr) if fr else None, reason="synthetic P2 map: arithmetic only")
    if not fr:
        return _result(name, NOT_EVALUATED, reason="P2 map has no point with numeric (non-REFUSED) loss and "
                       "delivered power")
    return _result(name, EVALUATED, value=max(fr), n_points=len(fr), map_id=p2_map["map_id"],
                   basis="worst case over measured map points (P2 p2_impedance_map_v1)", source=b["source"])


# ---- Hall B-field disturbance
B_FIELD_NEEDS = (
    "H-1 magnetic-circuit field B(r, z) including the downstream near field out to z >= L_standoff + L_module "
    "(F5 H1F-EX-05 TBD_AFTER_EVIDENCE: FEMM of MC-1 and a measured B map; a cited magnetostatic model)",
    "magnetic properties (relative permeability, any magnetised parts) of every ICP-module component (materials "
    "OPEN / TBD)",
    "a cited field solver or a measured field map with and without the ICP module at registered coil currents",
    "an owner-defined disturbance metric and threshold (F6-OQ-04)")


def b_field_objective(record, binding, geometry_id):
    name = "hall_b_field_disturbance"
    if record is None:
        return _result(name, TBD, reason="no cited H-1 field model or measurement exists", needs=list(B_FIELD_NEEDS))
    _binding(binding, geometry_id, "b_field")
    ec = record.get("evidence_class")
    if ec == SYN_CLASS:
        return _result(name, SYNTHETIC, value=record.get("value"), reason="synthetic")
    if ec not in ("measured", "model-derived") or not record.get("source") or record.get("units") != "-":
        raise F6Error("b_field: record must be measured or model-derived (units '-', with a source)")
    if ec == "model-derived" and not record.get("field_model_ref"):
        raise F6Error("b_field: a model-derived record needs field_model_ref (a cited field model)")
    return _result(name, EVALUATED, value=_finite(record["value"], "b_field value"), evidence_class=ec,
                   source=record["source"], metric=record.get("metric"))


# ---- view-factor obstruction (P3)
H1_ZONES = ("H1.PI_face", "H1.aperture", "H1.PO_face", "H1.PO_lateral")
H1_KEYS = ("R_pf", "R_i", "R_o", "R_ow", "R_b", "L_b")
RES_SCREEN = (16, 32, 64)        # = P3 RES_VERIFY (build_p3_coupled_thermal.py); P3 found ~0.009 abs error at (8,16,32)
RES_CONVERGENCE = (32, 64, 128)


def h1_record_from_p3(p3_doc):
    """The H-1 evaluation geometry the P3 parametric study used (H2-5 range midpoints; evidence_class assumed):
    an evaluation point, not the H-1 design (F5 H1F-EX-04 / H1F-EX-05 TBD_AFTER_EVIDENCE)."""
    g = p3_doc["radiative_view_parametric_study"]["h1_geometry"]
    return {"value": {k: g["values_m"][k] for k in H1_KEYS}, "units": "m", "evidence_class": g["evidence_class"],
            "source": P3_JSON_REL + " radiative_view_parametric_study.h1_geometry (" + g["basis"] + "; ids "
                      + ", ".join(f"{k} {v}" for k, v in sorted(g["source_ids"].items())) + ")"}


def _h1_geometry(rec):
    if not isinstance(rec, dict) or rec.get("units") != "m" or rec.get("evidence_class") not in EVIDENCE_CLASSES \
            or not rec.get("source") or not isinstance(rec.get("value"), dict):
        raise F6Error("H-1 front geometry must be a record {value: {R_pf,R_i,R_o,R_ow,R_b,L_b}, units 'm', "
                      "evidence_class, source}")
    g = {k: _finite(rec["value"].get(k), f"H-1 {k}") for k in H1_KEYS}
    if not (0 < g["R_pf"] < g["R_i"] < g["R_o"] < g["R_ow"] < g["R_b"]) or g["L_b"] <= 0:
        raise GeometryConstraintError("H-1 front geometry must satisfy 0 < R_pf < R_i < R_o < R_ow < R_b, L_b > 0")
    return g


def icp_body(vals):
    L = vals["L_standoff"]
    return p3_lib().Body("ICP", vals["r_aperture"], vals["r_module"], L, L + vals["L_module"],
                         tau=vals["tau_support"])


def view_factor_obstruction(vals, h1_rec, res=RES_SCREEN):
    """Per H-1 front zone: F_z->ICP and A_z F_z->ICP; total sum_z A_z F_z->ICP (m2)."""
    lib = p3_lib()
    g = _h1_geometry(h1_rec)
    h1 = lib.h1_body(g)
    vf = lib.view_factors([h1, icp_body(vals)], res, emitters=list(H1_ZONES))
    zones = {}
    for z in H1_ZONES:
        f = sum(v for k, v in vf["F"][z].items() if k.startswith("ICP."))
        zones[z] = {"F_to_ICP": f, "AF_to_ICP_m2": vf["area_m2"][z] * f, "area_m2": vf["area_m2"][z]}
    return {"zones": zones, "total_AF_to_ICP_m2": sum(z["AF_to_ICP_m2"] for z in zones.values()),
            "resolution": list(res)}


def geometric_status(h1_evidence_class):
    """Status of a geometry-only objective from the evidence class of the H-1 front geometry record: synthetic ->
    SYNTHETIC; assumed (e.g. the H2-5 evaluation point) -> EVALUATED_GEOMETRIC_CONDITIONAL (not rankable);
    otherwise EVALUATED_GEOMETRIC."""
    if h1_evidence_class not in EVIDENCE_CLASSES:
        raise F6Error(f"unknown evidence class {h1_evidence_class!r}")
    if h1_evidence_class == SYN_CLASS:
        return SYNTHETIC
    if h1_evidence_class == "assumed":
        return EVALUATED_GEOMETRIC_CONDITIONAL
    return EVALUATED_GEOMETRIC


def vf_objective(vals, tbd, h1_rec, res=RES_SCREEN):
    name = "view_factor_obstruction"
    miss = [s for s in ENVELOPE_SYMBOLS if s in tbd]
    if miss:
        return _result(name, NOT_EVALUATED, reason="design variables TBD: " + ", ".join(miss))
    if h1_rec is None:
        return _result(name, NOT_EVALUATED, reason="no H-1 front geometry record (F5 H1F-EX-04 exit-face channel "
                       "OD TBD_AFTER_EVIDENCE, docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json)")
    r = view_factor_obstruction(vals, h1_rec, res)
    ec = h1_rec["evidence_class"]
    st = geometric_status(ec)
    return _result(name, st, value=r["total_AF_to_ICP_m2"], zones=r["zones"], resolution=r["resolution"],
                   h1_geometry_evidence_class=ec, h1_geometry_source=h1_rec["source"],
                   label="geometric (diffuse gray view factors; no thermal consequence computed)")


# ---- plume interception (P3 with a measured angular distribution)
def plume_objective(vals, tbd, h1_rec, cdf_record, res=RES_SCREEN):
    name = "plume_interception_fraction"
    if cdf_record is None:
        return _result(name, NOT_EVALUATED, reason="no MEASURED plume angular current distribution (P3-H-03 "
                       "TBD_AFTER_EVIDENCE: Phase-1 Faraday-probe sweep)")
    ec = cdf_record.get("evidence_class") if isinstance(cdf_record, dict) else None
    if ec not in ("measured", SYN_CLASS):
        return _result(name, NOT_EVALUATED, reason=f"angular distribution evidence_class {ec!r}: only a measured "
                       "distribution is admitted (test / assumed cones are not plume predictions)")
    miss = [s for s in ENVELOPE_SYMBOLS if s in tbd]
    if miss or h1_rec is None:
        return _result(name, NOT_EVALUATED, reason="design variables TBD: " + ", ".join(miss) if miss else
                       "no H-1 front geometry record")
    lib = p3_lib()
    h1 = lib.h1_body(_h1_geometry(h1_rec))
    rec = lib.plume_interception_record([h1, icp_body(vals)], h1, "H1.aperture", cdf_record, res)
    f = sum(v for k, v in rec["fractions"].items() if k.startswith("ICP."))
    st = SYNTHETIC if ec == SYN_CLASS or h1_rec["evidence_class"] == SYN_CLASS else (
        EVALUATED if h1_rec["evidence_class"] != "assumed" else EVALUATED_GEOMETRIC_CONDITIONAL)
    return _result(name, st, value=f, f_escape=rec["fractions"]["SPACE"], distribution_source=rec["source"],
                   resolution=list(res))


# ---- collector heating (P3 q_collector on measured P1 inputs)
def collector_objective(inputs, binding, geometry_id):
    name = "collector_heating"
    if inputs is None:
        return _result(name, NOT_EVALUATED, reason="no P1 collector records (I_e / I_i collected, T_e, V_plasma, "
                       "V_surface; P3-IF-N01 / N02, P3Q-01 OPEN)")
    _binding(binding, geometry_id, "collector_heating")
    lib = p3_lib()
    try:
        r = lib.q_collector(inputs)
    except lib.MissingInputError as e:
        return _result(name, NOT_EVALUATED, reason=str(e))
    basis = r["provenance"]["basis"]
    if basis == lib.SYN:
        return _result(name, SYNTHETIC, value=r["Q_collector_W"], reason="synthetic inputs")
    if basis != "MEASURED_INPUTS_ONLY":
        return _result(name, NOT_EVALUATED, value=None, reason="q_collector conditional on non-measured inputs "
                       + ", ".join(r["provenance"]["conditional_on"]))
    return _result(name, EVALUATED, value=r["Q_collector_W"], terms_W=r["terms_W"],
                   surface_energy_terms=r["surface_energy_terms"], source=binding["source"])


# ---- module mass (geometry x cited densities)
def shell_areas(vals):
    """Envelope shell areas (m2) of the P3 annular body: bore and outer cylinders over L_module, upstream and
    downstream annular end faces; gross and scaled by (1 - tau_support)."""
    ra, rm, L, tau = vals["r_aperture"], vals["r_module"], vals["L_module"], vals["tau_support"]
    gross = {"bore": 2 * math.pi * ra * L, "outer": 2 * math.pi * rm * L,
             "up": math.pi * (rm * rm - ra * ra), "down": math.pi * (rm * rm - ra * ra)}
    return {"gross_m2": gross, "net_of_open_frame_m2": {k: a * (1.0 - tau) for k, a in gross.items()},
            "envelope_volume_m3": math.pi * (rm * rm - ra * ra) * L}


def component_volumes(vals):
    """Material volume per component (m3) where every needed variable is given; None otherwise."""
    out = {}
    try:
        net = shell_areas(vals)["net_of_open_frame_m2"]
    except KeyError:
        net = None
    for comp, t in SHELL_SYMBOLS.items():
        out[comp] = net[comp] * vals[t] if net is not None and t in vals else None
    a = ("N_ant", "r_ant", "d_ant")
    out["antenna"] = (vals["N_ant"] * 2 * math.pi * vals["r_ant"] * math.pi * vals["d_ant"] ** 2 / 4
                      if all(k in vals for k in a) else None)
    c = ("r_coll_in", "r_coll_out", "t_coll")
    out["collector"] = (math.pi * (vals["r_coll_out"] ** 2 - vals["r_coll_in"] ** 2) * vals["t_coll"]
                        if all(k in vals for k in c) else None)
    return out


def mass_objective(vals, materials):
    """materials: {component: {'value': density, 'units': 'kg/m3', 'evidence_class', 'source'}} for every component
    in MASS_COMPONENTS. Antenna mass: helical length approximated by N_ant x 2 pi r_ant (pitch neglected, stated)."""
    name = "module_mass"
    vols = component_volumes(vals)
    materials = materials or {}
    miss_geom = [c for c in MASS_COMPONENTS if vols[c] is None]
    miss_mat, syn = [], False
    for c in MASS_COMPONENTS:
        m = materials.get(c)
        if m is None or _is_tbd(m.get("value") if isinstance(m, dict) else None):
            miss_mat.append(c)
            continue
        if m.get("units") != "kg/m3" or not m.get("source") or m.get("evidence_class") not in DENSITY_EVIDENCE + (SYN_CLASS,):
            raise F6Error(f"mass: density record of {c} must have units kg/m3, a source and evidence class in "
                          f"{DENSITY_EVIDENCE}")
        _finite(m["value"], f"density {c}")
        if not float(m["value"]) > 0.0:                    # a zero / negative density would rank as light (PR #36)
            raise F6Error(f"mass: density of {c} must be > 0 kg/m3, got {m['value']!r}")
        syn = syn or m["evidence_class"] == SYN_CLASS
    if miss_geom or miss_mat:
        return _result(name, NOT_EVALUATED, reason="mass needs every component's geometry and a cited density",
                       missing_geometry=miss_geom, missing_density=miss_mat,
                       component_volumes_m3={k: v for k, v in vols.items() if v is not None})
    per = {c: vols[c] * float(materials[c]["value"]) for c in MASS_COMPONENTS}
    if syn and any(materials[c]["evidence_class"] != SYN_CLASS for c in MASS_COMPONENTS):
        raise F6Error("mass: synthetic and evidence density records mixed")
    return _result(name, SYNTHETIC if syn else EVALUATED, value=sum(per.values()), per_component_kg=per,
                   note="antenna helix length N x 2 pi r (pitch neglected); fasteners, match, feedthroughs and gas "
                        "port not included (not in the design vector)")


def al05_allocation(mp_doc):
    """Owner v0 dry allocation AL-05 'ICP neutralizer' read from the merged mass / power v2 (owner-allocation, not a
    CBE; mapping of the local match AL-05 vs AL-06 open, MQ-07)."""
    it = next(i for i in mp_doc["items"] if i.get("id") == "MA-AL-05")
    return {"id": "MA-AL-05", "value": _finite(it["value"], "AL-05"), "units": it["units"],
            "evidence_class": it["evidence_class"], "status": it["status"],
            "source": MP_V2_REL + " items MA-AL-05 (" + it["basis"] + ")"}


# ------------------------------------------------------------------------------------------------ evaluator
CONTEXT_KEYS = ("h1_front_geometry", "p1_capacity", "p1_capacity_binding", "p1_rf", "p1_rf_binding", "p2_map",
                "p2_map_binding", "plume_cdf", "b_field", "b_field_binding", "collector_inputs",
                "collector_binding", "materials", "al05")


def context_fingerprint(context):
    """sha256 of the canonical evidence context (all candidates in one Pareto filter must share it)."""
    ctx = {k: context.get(k) for k in CONTEXT_KEYS if k in ("h1_front_geometry", "plume_cdf", "materials", "al05")}
    return hashlib.sha256(json.dumps(ctx, sort_keys=True, default=str).encode()).hexdigest()


def evaluate(x, context=None, res=RES_SCREEN):
    """Evaluate one design vector against every F6 objective SIMULTANEOUSLY. context keys: CONTEXT_KEYS (all
    optional; absent evidence -> NOT_EVALUATED / TBD, never a default). Returns the objective vector, the hard
    constraint outcome and rankability. A violated hard constraint returns status INFEASIBLE (no objectives)."""
    context = context or {}
    unknown = sorted(set(context) - set(CONTEXT_KEYS))
    if unknown:
        raise F6Error(f"unknown context keys {unknown}")
    gid = x.get("geometry_id") if isinstance(x, dict) else None
    try:
        vals, tbd = validate_design_vector(x)
    except GeometryConstraintError as e:
        return {"geometry_id": gid, "status": "INFEASIBLE", "hard_constraints": "VIOLATED", "reason": str(e),
                "objectives": None, "rankable": False, "context_fingerprint": context_fingerprint(context)}
    h1 = context.get("h1_front_geometry")
    cap = capacity_objective(context.get("p1_capacity"), context.get("p1_capacity_binding"), gid)
    objs = {
        "electron_current_capacity": cap,
        "plume_interception_fraction": plume_objective(vals, tbd, h1, context.get("plume_cdf"), res),
        "rf_match_loss_fraction": rf_matching_objective(context.get("p2_map"), context.get("p2_map_binding"), gid),
        "rf_power_delivered": rf_power_objective(context.get("p1_rf"), context.get("p1_rf_binding"), gid, cap),
        "hall_b_field_disturbance": b_field_objective(context.get("b_field"), context.get("b_field_binding"), gid),
        "view_factor_obstruction": vf_objective(vals, tbd, h1, res),
        "collector_heating": collector_objective(context.get("collector_inputs"), context.get("collector_binding"),
                                                 gid),
        "module_mass": mass_objective(vals, context.get("materials")),
    }
    assert tuple(objs) == REQUIRED_OBJECTIVES
    alloc = context.get("al05")
    alloc_check = {"status": NOT_EVALUATED, "reason": "module mass not EVALUATED or no AL-05 record"}
    if alloc is not None and objs["module_mass"]["status"] == EVALUATED:
        exceeds = objs["module_mass"]["value"] > alloc["value"]
        alloc_check = {"status": "EXCEEDS_ALLOCATION" if exceeds else "NOT_EXCEEDING_ALLOCATION",
                       "allocation_kg": alloc["value"], "allocation_source": alloc["source"],
                       "note": "necessary condition only (AL-05 owner allocation, not a CBE; never a PASS)"}
    infeasible = alloc_check["status"] == "EXCEEDS_ALLOCATION"
    return {"geometry_id": gid, "status": "INFEASIBLE" if infeasible else "EVALUATED_VECTOR",
            # OPT-05: an unevaluated allocation check is never worded as satisfied
            "hard_constraints": "VIOLATED" if infeasible else (
                "SATISFIED_FOR_GIVEN_VARIABLES" if alloc_check["status"] == "NOT_EXCEEDING_ALLOCATION"
                else "NOT_EVALUATED (geometric hard constraints met; AL-05 allocation check NOT_EVALUATED)"),
            "tbd_variables": tbd, "objectives": objs, "al05_check": alloc_check,
            "not_rankable": [k for k, o in objs.items() if not o["rankable"]],
            "rankable": all(o["rankable"] for o in objs.values()) and not infeasible,
            "context_fingerprint": context_fingerprint(context)}


# ------------------------------------------------------------------------------------------------ Pareto filter
def _dominates(a, b, directions):
    better = False
    for v, w, d in zip(a, b, directions):
        if d == "minimize":
            if v > w:
                return False
            better |= v < w
        else:
            if v < w:
                return False
            better |= v > w
    return better


def nondominated(points, directions):
    """Indices of the non-dominated points (pure arithmetic; ties are all kept)."""
    if any(d not in ("minimize", "maximize") for d in directions):
        raise F6Error("directions must be minimize / maximize")
    # OPT-04: points with a non-finite component are excluded (never nondominated, never a dominator)
    def _fin(v):
        try:
            return not isinstance(v, bool) and math.isfinite(float(v))
        except (TypeError, ValueError):
            return False
    ok = [all(_fin(v) for v in p) for p in points]
    return [i for i, p in enumerate(points) if ok[i]
            and not any(_dominates(q, p, directions) for j, q in enumerate(points) if j != i and ok[j])]


def pareto_filter(evaluations):
    """Fail-closed Pareto filter over REQUIRED_OBJECTIVES (all eight; not caller-selectable).
    REFUSED_INCOMPLETE (no set, no order) if any feasible candidate has a non-rankable objective; the refusal lists
    every missing (geometry_id, objective). Candidates must share one evidence context. Never selects a winner."""
    if not evaluations:
        raise F6Error("pareto_filter needs at least one evaluation")
    fps = {e["context_fingerprint"] for e in evaluations}
    if len(fps) != 1:
        raise F6Error("candidates were evaluated against different evidence contexts")
    feas = [e for e in evaluations if e["status"] != "INFEASIBLE"]
    infeasible = [e["geometry_id"] for e in evaluations if e["status"] == "INFEASIBLE"]
    base = {"required_objectives": list(REQUIRED_OBJECTIVES), "infeasible": infeasible,
            "rule": "refuse to rank unless every required objective of every feasible candidate is rankable "
                    "(EVALUATED / EVALUATED_GEOMETRIC); no subset ranking; never a winner"}
    if not feas:
        return dict(base, status="REFUSED_NO_FEASIBLE_CANDIDATE", pareto_set=None)
    missing = {e["geometry_id"]: [k for k in REQUIRED_OBJECTIVES if not e["objectives"][k]["rankable"]]
               for e in feas}
    missing = {k: v for k, v in missing.items() if v}
    if missing:
        return dict(base, status="REFUSED_INCOMPLETE", pareto_set=None, missing=missing)
    dirs = [OBJ_BY_NAME[k]["direction"] for k in REQUIRED_OBJECTIVES]
    pts = [[e["objectives"][k]["value"] for k in REQUIRED_OBJECTIVES] for e in feas]
    idx = nondominated(pts, dirs)
    return dict(base, status="PARETO_SET_COMPUTED_NOT_A_SELECTION",
                pareto_set=sorted(feas[i]["geometry_id"] for i in idx))


# ------------------------------------------------------------------------------------------------ search driver
def _bound(rec, sym):
    var = VAR_BY_SYMBOL[sym]
    if not isinstance(rec, dict) or _is_tbd(rec.get("lo")) or _is_tbd(rec.get("hi")):
        raise SearchRefused(f"bound of {sym} is TBD (requires: {var['bounds']['requires']}); a TBD bound is never "
                            "replaced by an assumed value (A9.7 optimizer_rule)")
    if rec.get("units") != var["units"] or not rec.get("source") or rec.get("evidence_class") not in EVIDENCE_CLASSES:
        raise SearchRefused(f"bound of {sym} needs units {var['units']!r}, a source and an evidence class")
    if rec.get("evidence_class") == "assumed" and not rec.get("parametric_sensitivity_label"):
        raise SearchRefused(f"bound of {sym} is assumed: allowed only as an explicitly labelled parametric "
                            "sensitivity case (parametric_sensitivity_label)")
    lo, hi = _finite(rec["lo"], sym + " lo"), _finite(rec["hi"], sym + " hi")
    if hi < lo:
        raise SearchRefused(f"bound of {sym}: hi < lo")
    return lo, hi


def search(bounds, n_levels, context=None, res=RES_SCREEN):
    """Deterministic full-factorial grid over every design variable (n_levels per continuous variable; integer
    variables take every integer in their bounds). Refuses (SearchRefused) unless every variable has a sourced bound.
    Every vector is evaluated against all eight objectives and the fail-closed Pareto filter decides; with today's
    evidence it returns REFUSED_INCOMPLETE. Note: P1 / P2 evidence exists only for BUILT geometries (geometry_id
    bindings); a search over unbuilt geometries needs a validated geometry-to-evidence model (F6-OQ-03)."""
    if not isinstance(n_levels, int) or n_levels < 2:
        raise F6Error("n_levels must be an integer >= 2")
    axes = []
    for sym, var in VAR_BY_SYMBOL.items():
        lo, hi = _bound((bounds or {}).get(sym), sym)
        if var["kind"] == "integer":
            axes.append([float(k) for k in range(int(math.ceil(lo)), int(math.floor(hi)) + 1)])
        else:
            axes.append([lo + (hi - lo) * i / (n_levels - 1) for i in range(n_levels)])
    labelled = sorted(s for s in VAR_BY_SYMBOL if bounds[s].get("parametric_sensitivity_label"))
    evals = []
    for k, combo in enumerate(itertools.product(*axes)):
        x = dict(zip(VAR_BY_SYMBOL, combo), geometry_id=f"F6-GRID-{k:06d}")
        evals.append(evaluate(x, context, res))
    out = {"n_vectors": len(evals), "pareto": pareto_filter(evals), "evaluations": evals}
    if labelled:
        out["label"] = "PARAMETRIC_SENSITIVITY_CASE_NOT_A_DESIGN (assumed bounds: %s)" % ", ".join(labelled)
    return out


# ------------------------------------------------------------------------------------------------ geometric screening
def geometric_screening(h1_rec, grid, al05=None, res=RES_SCREEN):
    """GEOMETRIC_SCREENING_NOT_A_DESIGN: for every grid point (dimensionless ratios x R_o of the H-1 record) the
    view-factor obstruction (status per the H-1 record class) and the envelope shell areas; module mass stays
    NOT_EVALUATED; reported instead: the AL-05 ceiling on the mean envelope-shell areal density
    (t rho)_max = m_AL05 / sum_i A_i,net (an upper bound if the whole allocation went to the envelope shells;
    antenna, collector, match, feedthroughs would lower it). No ranking, no non-dominated set, no selection."""
    Ro = _h1_geometry(h1_rec)["R_o"]
    rows = []
    for L, rap, wall, H, tau in itertools.product(grid["L_over_Ro"], grid["rap_over_Ro"], grid["wall_over_Ro"],
                                                  grid["H_over_Ro"], grid["tau"]):
        x = {"geometry_id": f"SCREEN-L{L}-A{rap}-W{wall}-H{H}-T{tau}", "L_standoff": L * Ro,
             "r_aperture": rap * Ro, "r_module": (rap + wall) * Ro, "L_module": H * Ro, "tau_support": tau}
        vals, tbd = validate_design_vector(x)
        vf = vf_objective(vals, tbd, h1_rec, res)
        sa = shell_areas(vals)
        net_total = sum(sa["net_of_open_frame_m2"].values())
        row = {"geometry_id": x["geometry_id"], "L_over_Ro": L, "rap_over_Ro": rap, "wall_over_Ro": wall,
               "H_over_Ro": H, "tau": tau, "x_m": {k: x[k] for k in ENVELOPE_SYMBOLS},
               "vf_status": vf["status"], "total_AF_to_ICP_m2": vf["value"],
               "F_to_ICP": {z: vf["zones"][z]["F_to_ICP"] for z in H1_ZONES},
               "shell_area_gross_m2": sum(sa["gross_m2"].values()), "shell_area_net_m2": net_total,
               "envelope_volume_m3": sa["envelope_volume_m3"], "module_mass_status": NOT_EVALUATED}
        if al05 is not None:
            row["al05_mean_areal_density_ceiling_kg_m2"] = al05["value"] / net_total
        rows.append(row)
    return rows
