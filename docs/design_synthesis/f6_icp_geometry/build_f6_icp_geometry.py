#!/usr/bin/env python3
"""F6 downstream ICP geometry synthesis - deterministic builder (owner directive A9.7 F6; lane fo_a9_7_f6_icp_geometry).

Writes f6_icp_geometry_v1.json and F6_ICP_GEOMETRY.md (generated from the JSON) next to this script:
  * the F6 design vector x_ICP with bound sources (all bounds TBD) and the hard geometric constraints;
  * the eight-objective evaluator contract and today's status of every objective (computed by running the real
    evaluator, which calls the real P1 reducer / P3 library: capacity NOT_EVALUATED, plume NOT_EVALUATED, matching
    TBD_AFTER_IMPEDANCE_MAP, RF power NOT_EVALUATED, B-field TBD, view factor EVALUATED_GEOMETRIC_CONDITIONAL,
    collector heating NOT_EVALUATED, mass NOT_EVALUATED);
  * the fail-closed Pareto rule and its demonstration (REFUSED_INCOMPLETE) and the search refusal (bounds TBD);
  * the GEOMETRIC_SCREENING_NOT_A_DESIGN study: view-factor obstruction (P3 ray quadrature) and envelope shell areas
    over the P3 dimensionless evaluation grid at the P3 verification resolution, with a convergence check; module
    mass NOT_EVALUATED; AL-05 areal-density ceiling only;
  * items, interface demands (both directions), new open owner questions, M16 impact.

Deterministic (no random numbers; numpy ray quadrature), a few seconds of CPU, no Julia, no network.

    python docs/design_synthesis/f6_icp_geometry/build_f6_icp_geometry.py          # (re)write outputs
    python docs/design_synthesis/f6_icp_geometry/build_f6_icp_geometry.py --check  # exit 1 unless reproduced
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from abep_sim.design import icp_geometry_synthesis as F  # noqa: E402

LANE_REL = "docs/design_synthesis/f6_icp_geometry"
SCRIPT_REL = f"{LANE_REL}/build_f6_icp_geometry.py"
MODULE_REL = "abep_sim/design/icp_geometry_synthesis.py"
TEST_REL = "tests/test_design_f6_icp_geometry.py"
JSON_NAME = "f6_icp_geometry_v1.json"
MD_NAME = "F6_ICP_GEOMETRY.md"
BASE_COMMIT = "1c9d7a648cd4ce739e587248693271e5115698e1"
DATE = "2026-10-01"
TRIGGER = "T_A9_7_F6_ICP_GEOMETRY"

# immutable inputs only (owner decision records are never edited after commit)
DECISION_PINS = {
    "A97_MD": ("docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md",
               "fb51328d6fe07a6eaf257ef9ef9592cb0c0039ae3e8cf04ef0420007c985b129",
               "A9.7 verbatim owner directive (F6 section)"),
    "A97_JSON": ("docs/decisions/OD_2026_10_01_A9_7_architecture_freeze_design_synthesis.json",
                 "3199a670c901967ae4dca930022470b024cac14b263335da0adc3d423c37f372",
                 "A9.7 machine-readable record (f6_condition, optimizer_rule, recorder_notes)"),
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f",
           "A9 governing decision (Hall + downstream 13.56 MHz RF ICP neutralizer; INVESTIGATION_HYPOTHESIS)"),
}
REFERENCED_NOT_PINNED = (
    (F.P3_LIB_REL, "view_factors, h1_body, Body, plume_interception_record, q_collector (imported by path, read-only)"),
    (F.P3_JSON_REL, "H-1 evaluation geometry (H2-5 range midpoints, assumed) and the dimensionless evaluation grid"),
    (F.P1_REDUCER_REL, "icp45a_evaluate (capacity), derive_rf (P_RF,delivered), ICP45A_STATUSES (imported by path)"),
    (F.P2_FRAMEWORK_REL, "validate_map (p2_impedance_map_v1) (imported by path)"),
    (F.MP_V2_REL, "MA-AL-05 owner v0 dry allocation 'ICP neutralizer'"),
    (F.P4_REL, "collector material candidates and cited densities (FINAL_COLLECTOR_MATERIAL OPEN)"),
    ("docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json", "M16 v4 rows 10, 13, 18, 19"),
)
PENDING_LANES = {
    "F0": "PENDING docs/performance/ (fo_a9_7_f0_profiling)",
    "F1": "PENDING abep_sim/design/intake_synthesis.py (fo_a9_7_f1_intake_synthesis)",
    "F2": "PENDING abep_sim/design/filter_stage.py (fo_a9_7_f2_filter_stage)",
    "F3": "PENDING abep_sim/design/compressor_synthesis.py (fo_a9_7_f3_compressor_synthesis)",
    "F4": "PENDING fo_a9_7_f4_plenum_feed (path not yet assigned)",
    "F5": "PENDING docs/hardware/h1_freeze_candidate/ (fo_a9_7_f5_h1_freeze_candidate)",
    "F7_F8": "PENDING fo_a9_7_f7_f8_coupled_optimizer (path not yet assigned)",
    "F9": "PENDING fo_a9_7_f9_freeze_candidate (path not yet assigned)",
}
CONV_TOL_ABS_F = 0.01      # acceptance of the screening-resolution F_to_ICP vs the convergence resolution (numerical)


def sha256(rel):
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_pins():
    bad = [(k, p) for k, (p, h, _) in DECISION_PINS.items() if sha256(p) != h]
    if bad:
        raise SystemExit(f"pinned input sha256 mismatch: {bad} (refusing to build)")


def _r(x, n=6):
    if x is None:
        return None
    return float(f"{x:.{n}g}")


def item(i, name, value, units, basis, source, evidence_class, status, note=""):
    return {"id": i, "name": name, "value": value, "units": units, "basis": basis, "source": source,
            "evidence_class": evidence_class, "status": status, "note": note}


def build_items(h1, al05, grid):
    it = []
    for v in F.DESIGN_VARIABLES:
        it.append(item(v["id"], f"{v['symbol']}: {v['name']}", "TBD", v["units"], "design variable (x_ICP)",
                       "bounds require: " + v["bounds"]["requires"], None, "TBD",
                       "maps to " + (", ".join(v["maps_to"]) or "no P3 item") + "; used by " + ", ".join(v["used_by"])))
    it.append(item("F6-P-01", "H-1 front-face evaluation geometry (R_pf, R_i, R_o, R_ow, R_b, L_b)",
                   {k: h1["value"][k] for k in F.H1_KEYS}, "m", "evaluation point for the geometric screening only "
                   "(not the H-1 design; F5 " + PENDING_LANES["F5"] + ")", h1["source"], h1["evidence_class"],
                   "ANALOG_EVALUATION_ONLY"))
    it.append(item("F6-P-02", "owner v0 dry allocation AL-05 'ICP neutralizer'", al05["value"], al05["units"],
                   "necessary-condition check of module mass; match mapping AL-05 vs AL-06 open (MQ-07)",
                   al05["source"], al05["evidence_class"], al05["status"]))
    it.append(item("F6-P-03", "view-factor quadrature resolution (n_pos, n_u, n_phi)", list(F.RES_SCREEN), "-",
                   "P3 verification resolution RES_VERIFY (P3 found ~0.009 absolute error at its parametric "
                   "resolution (8, 16, 32)); convergence checked here against " + str(list(F.RES_CONVERGENCE)),
                   "docs/experiments/hall_icp/p3_coupled_thermal/build_p3_coupled_thermal.py RES_VERIFY", None,
                   "DEFINED", "numerical setting, not a physical value"))
    it.append(item("F6-P-04", "geometric screening grid (dimensionless, x R_o)", grid, "-",
                   "the P3 radiative-view evaluation grid reused verbatim (evaluation grid, not a design range)",
                   F.P3_JSON_REL + " radiative_view_parametric_study.grid", None, "DEFINED",
                   "not a bound: the F6 search refuses until sourced bounds exist"))
    it.append(item("F6-P-05", "Pareto required objective set", list(F.REQUIRED_OBJECTIVES), "-",
                   "A9.7 F6 'simultaneously evaluate' list (eight objectives); not caller-selectable",
                   F.DIRECTIVE + " (F6)", None, "DEFINED", "definitions / directions await F6-OQ-01"))
    return it


def current_objective_state(h1):
    """Run the real evaluator on an envelope-only vector with today's evidence (H-1 assumed geometry only) and the
    real P1 reducer with no registration: every non-geometric objective must refuse."""
    p1 = F.p1_reducer().icp45a_evaluate([], registration=None)
    x = {"geometry_id": "F6-STATE-PROBE", "L_standoff": h1["value"]["R_o"], "r_aperture": 1.2 * h1["value"]["R_o"],
         "r_module": 1.8 * h1["value"]["R_o"], "L_module": 3.0 * h1["value"]["R_o"], "tau_support": 0.0}
    e = F.evaluate(x, {"h1_front_geometry": h1, "p1_capacity": p1})
    rows = []
    for name in F.REQUIRED_OBJECTIVES:
        o = e["objectives"][name]
        d = F.OBJ_BY_NAME[name]
        rows.append({"objective": name, "direction": d["direction"], "units": d["units"], "source": d["source"],
                     "admission_rule": d["admission_rule"], "status_today": o["status"], "rankable": o["rankable"],
                     "reason_today": o.get("reason") or o.get("label"), "needs": o.get("needs")})
    pareto = F.pareto_filter([e])
    try:
        F.search({}, 3, {"h1_front_geometry": h1})
        search = {"status": "UNEXPECTED_RUN"}
    except F.SearchRefused as exc:
        search = {"status": "REFUSED", "reason": str(exc)}
    return {"probe_vector": {k: _r(v) if isinstance(v, float) else v for k, v in x.items()},
            "probe_note": "probe geometry = one P3 grid point (L/R_o 1, r_ap/R_o 1.2, wall/R_o 0.6, H/R_o 3, tau 0) "
                          "used only to exercise the evaluator; not a design",
            "p1_icp45a_status_used": p1["status"], "objectives": rows,
            "pareto_demonstration": {"status": pareto["status"], "missing": pareto.get("missing"),
                                     "rule": pareto["rule"]},
            "search_demonstration": search}


def convergence_check(h1, grid):
    Ro = h1["value"]["R_o"]
    out = []
    for L in (min(grid["L_over_Ro"]), max(grid["L_over_Ro"])):
        for rap in (min(grid["rap_over_Ro"]), max(grid["rap_over_Ro"])):
            wall, H, tau = min(grid["wall_over_Ro"]), max(grid["H_over_Ro"]), min(grid["tau"])
            x = {"geometry_id": "conv", "L_standoff": L * Ro, "r_aperture": rap * Ro, "r_module": (rap + wall) * Ro,
                 "L_module": H * Ro, "tau_support": tau}
            vals, _ = F.validate_design_vector(x)
            lo = F.view_factor_obstruction(vals, h1, F.RES_SCREEN)
            hi = F.view_factor_obstruction(vals, h1, F.RES_CONVERGENCE)
            for z in F.H1_ZONES:
                a, b = lo["zones"][z]["F_to_ICP"], hi["zones"][z]["F_to_ICP"]
                out.append({"L_over_Ro": L, "rap_over_Ro": rap, "wall_over_Ro": wall, "H_over_Ro": H, "tau": tau,
                            "zone": z, "F_screen": _r(a, 5), "F_convergence": _r(b, 5), "abs_diff": _r(abs(a - b), 3)})
    mx = max(r["abs_diff"] for r in out)
    return {"resolution_screen": list(F.RES_SCREEN), "resolution_convergence": list(F.RES_CONVERGENCE),
            "tolerance_abs_F": CONV_TOL_ABS_F, "max_abs_diff": mx,
            "status": "WITHIN_NUMERICAL_TOLERANCE" if mx <= CONV_TOL_ABS_F else "NUMERICAL_FAILURE", "rows": out}


def screening(h1, al05, grid):
    rows = F.geometric_screening(h1, grid, al05)
    out = []
    for r in rows:
        out.append({"geometry_id": r["geometry_id"], "L_over_Ro": r["L_over_Ro"], "rap_over_Ro": r["rap_over_Ro"],
                    "wall_over_Ro": r["wall_over_Ro"], "H_over_Ro": r["H_over_Ro"], "tau": r["tau"],
                    "x_m": {k: _r(v, 6) for k, v in r["x_m"].items()},
                    "vf_status": r["vf_status"], "total_AF_to_ICP_m2": _r(r["total_AF_to_ICP_m2"], 4),
                    "F_to_ICP": {z: _r(v, 3) for z, v in r["F_to_ICP"].items()},
                    "shell_area_gross_m2": _r(r["shell_area_gross_m2"], 5),
                    "shell_area_net_m2": _r(r["shell_area_net_m2"], 5),
                    "envelope_volume_m3": _r(r["envelope_volume_m3"], 5),
                    "module_mass_status": r["module_mass_status"],
                    "al05_mean_areal_density_ceiling_kg_m2": _r(r["al05_mean_areal_density_ceiling_kg_m2"], 4)})
    by_L = {}
    for r in out:
        by_L.setdefault(r["L_over_Ro"], []).append(r["total_AF_to_ICP_m2"])
    trend = [{"L_over_Ro": L, "min_total_AF_to_ICP_m2": min(v), "max_total_AF_to_ICP_m2": max(v), "n": len(v)}
             for L, v in sorted(by_L.items())]
    return {
        "label": F.SCREENING_LABEL,
        "status": "COMPUTED_CONDITIONAL (H-1 geometry assumed; no ranking, no selection)",
        "what": "view-factor obstruction of the H-1 front zones by the ICP envelope (P3 ray quadrature) and envelope "
                "shell areas vs geometry; module mass NOT_EVALUATED (materials and thicknesses TBD)",
        "h1_geometry": h1,
        "grid": grid, "grid_source": F.P3_JSON_REL + " radiative_view_parametric_study.grid",
        "geometry_mapping": "L_standoff = L/R_o x R_o; r_aperture = r_ap/R_o x R_o; r_module = (r_ap + wall)/R_o x "
                            "R_o; L_module = H/R_o x R_o; tau_support = tau",
        "resolution": list(F.RES_SCREEN),
        "convergence_check": convergence_check(h1, grid),
        "mass_relation": "m_module = sum_i A_i,net t_i rho_i (envelope shells: bore, outer, up, down) + "
                         "N_ant 2 pi r_ant pi d_ant^2 / 4 rho_ant + pi (r_coll,out^2 - r_coll,in^2) t_coll rho_coll; "
                         "t_i, rho_i, antenna and collector geometry TBD -> NOT_EVALUATED",
        "al05_ceiling_reading": "al05_mean_areal_density_ceiling_kg_m2 = m_AL05 / sum_i A_i,net: the largest mean "
                                "t x rho of the envelope shells if the WHOLE AL-05 allocation went to them (antenna, "
                                "collector, local match, feedthroughs, gas port lower it); a ceiling, not a mass",
        "rows": out,
        "descriptive_summary_by_standoff": trend,
        "reading_rule": "total_AF_to_ICP_m2 = sum over H-1 front zones (PI face, channel-exit aperture, PO face, PO "
                        "lateral) of A_z F_z->ICP: the diffuse radiative view the ICP envelope takes from H-1. It is "
                        "one of eight F6 objectives and never a ranking by itself; with tau > 0 the P3 gray "
                        "open-frame approximation applies",
        "limitations": [
            "H-1 front geometry is the assumed H2-5 range-midpoint evaluation point (rounded to 0.1 mm in the P3 "
            "JSON); every number moves with the F5 freeze candidate",
            "the ICP is one coaxial annular envelope body (open-tube coaxial first build); antenna, collector and "
            "internal surfaces are not separate radiating bodies",
            "diffuse gray view factors only: no temperatures, no heat flows, no thermal PASS "
            "(ICP_COUPLED_THERMAL UNRESOLVED)",
            "no plume interception: no measured angular distribution exists (P3 already reports test-cone "
            "geometry; not repeated)"],
    }


def interface_demands():
    p1, p2, p3 = ("docs/experiments/hall_icp/p1_icp_bench/", "docs/experiments/hall_icp/p2_impedance_map/",
                  "docs/experiments/hall_icp/p3_coupled_thermal/")
    return {
        "f6_needs": [
            {"id": "F6-IF-N01", "from": "F5 " + PENDING_LANES["F5"], "what": "frozen H-1 front-face geometry at "
             "IP-EXIT (R_pf, R_i, R_o, R_ow, R_b, L_b) as a non-assumed record", "units": "m",
             "status": "PENDING", "unlocks": "view_factor_obstruction EVALUATED_GEOMETRIC; plume interception "
             "geometry"},
            {"id": "F6-IF-N02", "from": "F5 " + PENDING_LANES["F5"], "what": "H-1 magnetic-circuit field B(r, z) "
             "including the downstream near field to z >= L_standoff + L_module (measured or cited model) and the coil "
             "operating envelope", "units": "T", "status": "PENDING", "unlocks": "hall_b_field_disturbance"},
            {"id": "F6-IF-N03", "from": "P1 " + p1, "what": "icp45a_evaluate result (status EVALUATED_ENGINEERING_ONLY) "
             "per BUILT ICP geometry, bound by geometry_id and p1_record_id; derive_rf P_RF_DELIVERED at the same "
             "capacity record", "units": "A; W", "status": "TBD_AFTER_EVIDENCE (ICP45 NOT_EVALUATED; I_d,max,H1 "
             "not registered)", "unlocks": "electron_current_capacity, rf_power_delivered"},
            {"id": "F6-IF-N04", "from": "P2 " + p2, "what": "validated MEASURED p2_impedance_map_v1 per built geometry "
             "(binding carries map content_sha256)", "units": "ohm; W", "status": "TBD_AFTER_IMPEDANCE_MAP",
             "unlocks": "rf_match_loss_fraction"},
            {"id": "F6-IF-N05", "from": "P3 " + p3 + " (P3-IF-N01 / N02 via P1)", "what": "measured collector "
             "currents, T_e and V_plasma at the collector sheath edge (P3Q-01 OPEN)", "units": "A; eV; V",
             "status": "TBD_AFTER_EVIDENCE", "unlocks": "collector_heating"},
            {"id": "F6-IF-N06", "from": "Phase-1 Hall data (P3-H-03)", "what": "measured angular current "
             "distribution of the H-1 plume (Faraday probe; never predicted)", "units": "deg; -",
             "status": "TBD_AFTER_EVIDENCE", "unlocks": "plume_interception_fraction"},
            {"id": "F6-IF-N07", "from": "P4 " + F.P4_REL + " and RFQ / hardware", "what": "selected materials and "
             "cited densities of dielectric, housing / shells, antenna conductor and collector "
             "(FINAL_COLLECTOR_MATERIAL OPEN)", "units": "kg/m3", "status": "TBD", "unlocks": "module_mass"},
            {"id": "F6-IF-N08", "from": "hardware (KC-1 / ICP module drawing; ICD ICP-02, -04, -07, -21, -47)",
             "what": "sourced bounds of every design variable F6-X-01..17", "units": "m; -", "status": "TBD (LOCK-1)",
             "unlocks": "search (refused until then)"},
        ],
        "f6_supplies": [
            {"id": "F6-IF-S01", "to": "F7/F8 " + PENDING_LANES["F7_F8"], "what": "x_ICP definition "
             "(DESIGN_VARIABLES), the eight-objective vector with per-objective status, and the fail-closed Pareto "
             "semantics (REFUSED_INCOMPLETE)", "status": "DEFINED (framework); values TBD"},
            {"id": "F6-IF-S02", "to": "F9 " + PENDING_LANES["F9"], "what": "downstream ICP geometry parameter rows "
             "VALUE | TOLERANCE | EVIDENCE_CLASS | SOURCE | FREEZE_STATUS: all TBD (INVESTIGATION_HYPOTHESIS)",
             "status": "TBD"},
            {"id": "F6-IF-S03", "to": "F5 " + PENDING_LANES["F5"], "what": "view-factor obstruction of the H-1 front "
             "zones vs ICP envelope (screening rows) for the H-1 radiative design; demand that B(r, z) covers the "
             "ICP region", "status": "COMPUTED_CONDITIONAL (assumed H-1 geometry)"},
            {"id": "F6-IF-S04", "to": "P3 " + p3, "what": "screening rows at the P3 verification resolution with "
             "a convergence check (complements the P3 parametric study; no P3 file changed)",
             "status": "COMPUTED_CONDITIONAL"},
            {"id": "F6-IF-S05", "to": "F0 " + PENDING_LANES["F0"], "what": "a P3 ray / view-factor workload (96 "
             "envelopes x 4 emitters at (16, 32, 64) plus 8 at (32, 64, 128)) for profiling (Rust order item 6)",
             "status": "AVAILABLE (builder)"},
            {"id": "F6-IF-S06", "to": "F1 / F2 / F3 / F4 (" + "; ".join(PENDING_LANES[k] for k in
                                                                       ("F1", "F2", "F3", "F4")) + ")",
             "what": "no direct geometric interface; carried flag: the ICP gas feed is unbooked (A9 recorder flag) "
             "and the dedicated ICP gas port stays capped (A9.3 OQ-RFQ-10) - any ICP gas demand on the feed path "
             "comes from P1 records, not from F6", "status": "NO_INTERFACE_NOW"},
        ],
    }


def open_owner_questions():
    return [
        {"id": "F6-OQ-01", "question": "Approve the F6 objective definitions and directions (eight objectives; "
         "worst-case P2 loss fraction as the matching metric; P_RF,delivered at the ICP45 capacity point as the RF "
         "power metric; sum A_z F_z->ICP as the view-factor metric) and the fail-closed Pareto rule (no subset "
         "ranking)?", "status": "TBD_OWNER", "blocks": "any F6 Pareto set"},
        {"id": "F6-OQ-02", "question": "Which source fixes the design-variable bounds F6-X-01..17: the KC-1 / ICP "
         "module drawing envelope at LOCK-1, or a registered P1 / P2 bench geometry matrix?", "status": "TBD_OWNER",
         "blocks": "search()"},
        {"id": "F6-OQ-03", "question": "P1 / P2 measure built geometries only. Does the owner want (a) a multi-"
         "geometry P1 / P2 bench matrix (each candidate built and measured) or (b) a separately validated model of "
         "I_e,cap and Z_antenna vs geometry? Without one, the F6 'search' is an evaluation over built geometries.",
         "status": "TBD_OWNER", "blocks": "geometry search beyond built articles"},
        {"id": "F6-OQ-04", "question": "Define the Hall magnetic-field disturbance metric (e.g. max |dB|/|B| in the "
         "acceleration region vs at IP-EXIT) and its acceptance threshold.", "status": "TBD_OWNER",
         "blocks": "hall_b_field_disturbance"},
    ]


def m16_impact():
    rule = "no maturity change: software framework only; a row changes only under the repository evidence rules"
    return [
        {"row": 18, "key": "icp_neutralizer_head", "proposed_change": "none", "note": "the v4 blocking item 'ICP "
         "module design ... no registered lane designs the ICP module' is now addressed by an F6 FRAMEWORK only; no "
         "ICP design exists (all bounds TBD)", "rule": rule},
        {"row": 19, "key": "flight_rf_chain", "proposed_change": "none", "note": "RF matching / power objectives "
         "wait on P2 / P1 (TBD_AFTER_IMPEDANCE_MAP)", "rule": rule},
        {"row": 13, "key": "thermal_control", "proposed_change": "none", "note": "view-factor obstruction "
         "screening is geometric only; ICP_COUPLED_THERMAL UNRESOLVED", "rule": rule},
        {"row": 10, "key": "magnetic_circuit", "proposed_change": "none", "note": "F6 adds the demand that the H-1 "
         "field model covers the ICP region (F6-IF-N02)", "rule": rule},
    ]


def build():
    verify_pins()
    p3 = json.loads((REPO / F.P3_JSON_REL).read_text(encoding="utf-8"))
    mp = json.loads((REPO / F.MP_V2_REL).read_text(encoding="utf-8"))
    h1 = F.h1_record_from_p3(p3)
    al05 = F.al05_allocation(mp)
    grid = p3["radiative_view_parametric_study"]["grid"]
    doc = {
        "schema": "abep_design_synthesis_f6_v1", "id": "F6_ICP_GEOMETRY_v1", "lane": F.LANE, "lane_key": F.LANE_KEY,
        "trigger": TRIGGER, "directive": F.DIRECTIVE, "date": DATE, "base_commit": BASE_COMMIT,
        "status": "FRAMEWORK_DEFINED; SEARCH_NOT_RUN (A9.7 F6: search once P1 / P2 evidence exists)",
        "a9_status": F.A9_STATUS, "architecture_status": "INVESTIGATION_HYPOTHESIS",
        "generated_by": f"python {SCRIPT_REL}", "module": MODULE_REL, "test": TEST_REL, "companion_document": MD_NAME,
        "what_this_is_not": ["an ICP design or geometry selection", "a ranking, winner or PASS",
                             "an ICP-45 evaluation (NOT_EVALUATED)", "a thermal result (ICP_COUPLED_THERMAL "
                             "UNRESOLVED)", "a Hall prediction", "an archengine change (goldens do not move)"],
        "decision_pins": [{"key": k, "path": p, "sha256": h, "role": r} for k, (p, h, r) in DECISION_PINS.items()],
        "referenced_not_pinned": [{"path": p, "use": u} for p, u in REFERENCED_NOT_PINNED],
        "pending_lanes": PENDING_LANES,
        "design_vector": {"variables": list(F.DESIGN_VARIABLES),
                          "hard_constraints": [{"id": i, "rule": r, "basis": b} for i, r, b in F.HARD_CONSTRAINTS],
                          "fail_closed": "a violated hard constraint returns INFEASIBLE with no objective values"},
        "objective_contract": {"required_objectives": list(F.REQUIRED_OBJECTIVES),
                               "status_vocabulary": list(F.OBJECTIVE_STATUSES),
                               "rankable_statuses": list(F.RANKABLE_STATUSES),
                               "pareto_status_vocabulary": list(F.PARETO_STATUSES),
                               "pareto_choice": "REFUSE (fail closed): no subset ranking, no INCOMPLETE-flagged "
                                                "order; reason in the module docstring"},
        "current_objective_state": current_objective_state(h1),
        "items": build_items(h1, al05, grid),
        "geometric_screening": screening(h1, al05, grid),
        "interface_demands": interface_demands(),
        "open_owner_questions": open_owner_questions(),
        "m16_impact": m16_impact(),
        "compliance": {"no_pass_status": True, "no_winner": True, "no_tbd_converted_to_value": True,
                       "archengine_untouched": True, "p1_p2_p3_files_unmodified": True,
                       "deterministic": True, "outputs_regenerable": f"python {SCRIPT_REL} --check"},
    }
    return doc


def _fmt(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True)
    return "" if v is None else str(v)


def render_md(doc):
    L = [f"# F6 downstream ICP geometry synthesis ({doc['id']})", "",
         f"Generated by `{doc['generated_by']}` from `{JSON_NAME}`; do not edit by hand. Lane `{doc['lane']}`, "
         f"directive `{doc['directive']}`, base `{doc['base_commit'][:7]}`, {doc['date']}.", "",
         f"**Status:** {doc['status']}. **A9:** {doc['a9_status']}. **Architecture:** {doc['architecture_status']}.",
         "", "This is not: " + "; ".join(doc["what_this_is_not"]) + ".", "",
         "## Objective state today (real evaluator, real P1 reducer)", "",
         "| objective | direction | units | status today | rankable | reason |", "|---|---|---|---|---|---|"]
    for r in doc["current_objective_state"]["objectives"]:
        L.append(f"| {r['objective']} | {r['direction']} | {r['units']} | {r['status_today']} | {r['rankable']} | "
                 f"{_fmt(r['reason_today'])} |")
    cs = doc["current_objective_state"]
    L += ["", f"Pareto filter: **{cs['pareto_demonstration']['status']}** - {cs['pareto_demonstration']['rule']}.",
          f"Search: **{cs['search_demonstration']['status']}** - {cs['search_demonstration'].get('reason', '')}", "",
          f"Pareto choice: {doc['objective_contract']['pareto_choice']}.", "",
          "## Design vector x_ICP (all bounds TBD)", "", "| id | symbol | units | bounds require | maps to |",
          "|---|---|---|---|---|"]
    for v in doc["design_vector"]["variables"]:
        L.append(f"| {v['id']} | {v['symbol']} | {v['units']} | {v['bounds']['requires']} | "
                 f"{', '.join(v['maps_to'])} |")
    L += ["", "Hard constraints (fail closed):", ""]
    L += [f"- {c['id']}: {c['rule']} ({c['basis']})" for c in doc["design_vector"]["hard_constraints"]]
    gs = doc["geometric_screening"]
    cc = gs["convergence_check"]
    L += ["", f"## {gs['label']}", "", f"Status: {gs['status']}. {gs['what']}.", "",
          f"H-1 geometry: {_fmt(gs['h1_geometry']['value'])} m, evidence class `{gs['h1_geometry']['evidence_class']}`"
          f" ({gs['h1_geometry']['source']}).", "", f"Grid ({gs['grid_source']}): {_fmt(gs['grid'])}; "
          f"{gs['geometry_mapping']}.", "",
          f"Resolution {cc['resolution_screen']}; convergence vs {cc['resolution_convergence']}: max |dF| = "
          f"{cc['max_abs_diff']} (tolerance {cc['tolerance_abs_F']}, {cc['status']}).", "",
          gs["reading_rule"] + ".", "", gs["mass_relation"] + ".", "", gs["al05_ceiling_reading"] + ".", "",
          "| L/R_o | r_ap/R_o | wall/R_o | H/R_o | tau | sum A F->ICP (m2) | F PI | F aperture | F PO face | "
          "F PO lat | shell area net (m2) | AL-05 t*rho ceiling (kg/m2) | mass |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in gs["rows"]:
        f = r["F_to_ICP"]
        L.append(f"| {r['L_over_Ro']} | {r['rap_over_Ro']} | {r['wall_over_Ro']} | {r['H_over_Ro']} | {r['tau']} | "
                 f"{r['total_AF_to_ICP_m2']} | {f['H1.PI_face']} | {f['H1.aperture']} | {f['H1.PO_face']} | "
                 f"{f['H1.PO_lateral']} | {r['shell_area_net_m2']} | {r['al05_mean_areal_density_ceiling_kg_m2']} | "
                 f"{r['module_mass_status']} |")
    L += ["", "Descriptive range by standoff (not a ranking):", ""]
    L += [f"- L/R_o = {t['L_over_Ro']}: sum A F->ICP {t['min_total_AF_to_ICP_m2']} .. {t['max_total_AF_to_ICP_m2']} "
          f"m2 over {t['n']} envelopes" for t in gs["descriptive_summary_by_standoff"]]
    L += ["", "Limitations:", ""] + [f"- {x}" for x in gs["limitations"]]
    L += ["", "## Items", "", "| id | name | value | units | evidence class | status | source |",
          "|---|---|---|---|---|---|---|"]
    for it in doc["items"]:
        L.append(f"| {it['id']} | {it['name']} | {_fmt(it['value'])} | {it['units']} | {_fmt(it['evidence_class'])} "
                 f"| {it['status']} | {it['source']} |")
    L += ["", "## Interface demands", "", "F6 needs:", ""]
    L += [f"- {n['id']} from {n['from']}: {n['what']} [{n['units']}] - {n['status']} (unlocks {n['unlocks']})"
          for n in doc["interface_demands"]["f6_needs"]]
    L += ["", "F6 supplies:", ""]
    L += [f"- {s['id']} to {s['to']}: {s['what']} - {s['status']}" for s in doc["interface_demands"]["f6_supplies"]]
    L += ["", "## New open owner questions", ""]
    L += [f"- {q['id']} ({q['status']}; blocks {q['blocks']}): {q['question']}" for q in doc["open_owner_questions"]]
    L += ["", "## M16 impact", ""]
    L += [f"- row {m['row']} {m['key']}: {m['proposed_change']} - {m['note']}" for m in doc["m16_impact"]]
    L += ["", "## Pins", ""]
    L += [f"- `{p['path']}` sha256 `{p['sha256']}` ({p['role']})" for p in doc["decision_pins"]]
    L += ["", "Referenced, not pinned (mutable deliverables; reproduction is checked byte-for-byte by --check):", ""]
    L += [f"- `{p['path']}`: {p['use']}" for p in doc["referenced_not_pinned"]]
    return "\n".join(L) + "\n"


def outputs():
    doc = build()
    js = json.dumps(doc, indent=1, sort_keys=False, ensure_ascii=True, allow_nan=False) + "\n"
    return {JSON_NAME: js, MD_NAME: render_md(json.loads(js))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the committed outputs are reproduced")
    a = ap.parse_args(argv)
    outs = outputs()
    if a.check:
        bad = [n for n, t in outs.items() if not (HERE / n).exists() or (HERE / n).read_text(encoding="utf-8") != t]
        if bad:
            print(f"NOT REPRODUCED: {bad}")
            return 1
        print("OK: outputs reproduced")
        return 0
    for n, t in outs.items():
        (HERE / n).write_text(t, encoding="utf-8")
    print("wrote", ", ".join(outs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
