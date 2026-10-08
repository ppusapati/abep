"""Build M2_REPORT_v1.json / .md from the committed M2 closure record (addendum A8, DBF-1). Every number is read from
the sha256-pinned record or the DBF-1 record; nothing is evaluated here. The M3 decision is not written here.

Usage: python3 docs/milestones/M2_196_state_rfp_closure/build_m2_report.py [--check]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REL = "docs/milestones/M2_196_state_rfp_closure"
RECORD = (f"{REL}/m2_closure_record_v1.json", "600cf229ecdb5f91f0471f03cfdd6d287486ad21e9d9ebadde3cdafa54a37394")
MANIFEST = (f"{REL}/m2_run_manifest_v1.json", "7c29039800f623d59cbeb094dbc25b968e39cc4106d0035b3e6814ac8dee234f")
DBF1 = ("docs/baseline/DBF-1/dbf1_v1.json", "d20f1e8aa95c2d6ee0b307669500d7aaa5ea6abf4d21ddb944b7999525943e4f")

# What evidence would move each blocker family (registered records named; no new requirement).
MOVES = [
    ("HALL_NUMERICS_NOT_CONVERGED", "model-numerics",
     "a converged H-1 Hall subset from the A9.36 numerical-method investigation and a rerun of the registered envelope "
     "under its own addendum (A7), consumed on the DBF-1 hardware (G-RP1, BZ-P5B16) without a DCR (A8)"),
    ("A8_DBF1_*_BELOW_REQUIRED_* / A5_*_BELOW_REQUIRED_*", "design-variable",
     "a larger effective collection area / higher capture and delivered flow (a DBF-1 DCR with a physical reason: new "
     "intake / compressor design, measured accommodation DI-1.3, compressor coefficients T-1 / T-2); a FROZEN "
     "A_eff,max (A4-REG-01) would make the A4 bound eligible (CA4) - none is registered (A9.35)"),
    ("A8_DBF1_GAS_PATH_OUT_OF_DOMAIN_IN_SCENARIO", "design-variable",
     "dead-head at P_set 0.02 Pa in the low-accommodation scenarios (maxwell / cll alpha 0, 0.2): a DCR on P_set or the "
     "compressor, or a preregistered DI-1.3 accommodation measurement narrowing the scenario set"),
    ("A8_DBF1_SCENARIO_DEPENDENT / A8_DBF1_NECESSARY_CONDITION_MET_NOTHING_ESTABLISHED", "missing-evidence",
     "DI-1.3 accommodation evidence (scenario dependence) and a Hall closing point (a met necessary condition "
     "establishes nothing)"),
    ("ICP_CAPACITY_NOT_EVALUATED / IN-* / NP-ICP-CHEM-AIR:* / NP_ICP_* / DOM-* / SP-04 / CHG-04", "missing-evidence",
     "admitted NP-ICP-CHEM-AIR AIR and Xe rate sets, registered RF absorbed power / P2 coupling evidence, electrode "
     "potentials and bias range (P1-IT-36 / P1-IT-18), neutral-source pressure, edge-factor source, B_ICP; then a "
     "VALIDATED_BENCH I_e,cap (P1 ICP-45) for HC-05"),
    ("BUS_LEDGER_NOT_COMPLETE", "missing-evidence", "the 23 TBD ledger terms (Hall discharge at a closing point, magnet "
     "coils, RF chain, valves, controls, thermal control) from registered loads"),
    ("THERMAL_* / SPACECRAFT_THERMAL_ICD_ABSENT", "missing-evidence",
     "the host spacecraft thermal ICD (SCI-A values), a registered flight thermal case and evaluated Hall / ICP heat loads"),
    ("MASS_INCOMPLETE_EVIDENCE / WET_MASS_OBJECTIVE_NOT_EVALUATED / XE_LOAD_NOT_FROZEN", "missing-evidence",
     "a current-best-estimate dry mass (mass-closure actions MCA; compressor CBE vs AL-02) and a selected flight Xe load"),
    ("LIFE_NOT_EVALUATED / HALL_WALL_LIFE_INPUTS_NOT_TRUSTWORTHY / A8_DBF1_ANODE_MATERIAL_FROZEN_P4_EVIDENCE_INCOMPLETE",
     "missing-evidence", "wall_life_trustworthy Hall runs (ion_wall_losses = true) and P4 Q0 / Q1 coupon evidence for "
     "INCONEL 600 / 601"),
    ("HOST_DRAG_REFERENCE_PENDING_CUSTOMER_ICD", "missing-evidence", "the customer host-spacecraft drag ICD (A9.13 S6.18)"),
    ("CREDIBLE_HALL_TRANSPORT_SET_EMPTY", "missing-evidence", "an admitted Hall transport member (layer (b))"),
    ("XE_FEED_FLOW_NOT_REGISTERED", "missing-evidence", "a registered H-1 Xe flow (OQ-HPE-03)"),
]


class BuildError(RuntimeError):
    pass


def pinned(p):
    b = (ROOT / p[0]).read_bytes()
    if hashlib.sha256(b).hexdigest() != p[1]:
        raise BuildError(f"{p[0]}: sha256 differs from the pin")
    return json.loads(b)


def build():
    r = pinned(RECORD)
    pinned(MANIFEST)
    dbf = pinned(DBF1)
    st = r["states"]
    air = [s["air_dbf1"] for s in st]
    held = [a["mdot_del_held_min_max_kg_s"] for a in air if a["mdot_del_held_min_max_kg_s"]]
    alld = [x["mdot_del_kg_s"] for a in air for x in a["scenarios"] if x["mdot_del_kg_s"] is not None]
    pb_air = [s["AIR_PRIMARY"]["bus_layer_a"]["P_nonHall_LB_W"] for s in st]
    pb_xe = [s["XE_CONTINGENCY"]["bus_layer_a"]["P_nonHall_LB_W"] for s in st]
    tr = r["t_required_vs_rfp"]
    cls = r["classification"]
    nc = r["dbf1_necessary_conditions"]
    worst_del = nc["L-DEL-DBF1|T12"]["worst_state"]
    ood = [s["state_id"] for s, a in zip(st, air) if a["out_of_domain_scenarios"]]
    ncl_air = collections.Counter(s["AIR_PRIMARY"]["non_hall_closure"] for s in st)
    ncl_xe = collections.Counter(s["XE_CONTINGENCY"]["non_hall_closure"] for s in st)
    by_type = collections.OrderedDict()
    for b in cls["blockers"]:
        by_type.setdefault(b["blocker_type"], []).append({"code": b["code"], "cells": b["cells"], "category": b["category"]})
    rep = {
        "schema": "abep_m2_report_v1",
        "id": "M2_REPORT_v1",
        "milestone": "M2_196_STATE_RFP_CLOSURE",
        "design_baseline": "DBF-1",
        "date": "2026-10-08",
        "record": {"path": RECORD[0], "sha256": RECORD[1]},
        "run_manifest": {"path": MANIFEST[0], "sha256": MANIFEST[1]},
        "dbf1": {"path": DBF1[0], "sha256": DBF1[1]},
        "classification_verbatim": {"result": cls["result"], "procedure_step": cls["procedure_step"],
                                    "procedure": cls["procedure"]},
        "counts": {m: {k: r["per_mode"][m][k] for k in ("n_required_states", "layer_a_status_counts",
                                                       "layer_b_status_counts", "hall_closure_counts")}
                   for m in r["per_mode"]},
        "non_hall_closure_counts": {"AIR_PRIMARY": dict(sorted(ncl_air.items())), "XE_CONTINGENCY": dict(sorted(ncl_xe.items()))},
        "binding_constraints_ranked": {m: r["per_mode"][m]["binding_constraints_ranked"] for m in r["per_mode"]},
        "blockers_by_type": by_type,
        "what_would_move_each_blocker": [{"codes": c, "type": t, "evidence": e} for c, t, e in MOVES],
        "dbf1_baseline_deficiencies": [
            {"id": d["id"], "finding": d["finding"], "category": d["category"]} for d in dbf["baseline_deficiencies"]],
        "m2_confirmation_of_deficiencies": {
            "DBF1-BD-01": f"L-DEL-DBF1|T12 fails in every admitted scenario at "
                          f"{nc['L-DEL-DBF1|T12']['state_verdict_counts'].get('FAILS_IN_EVERY_SCENARIO', 0)} states "
                          f"(worst {worst_del['state_id']}, k_fav {worst_del['k_fav']:.4g}); L-DEL-DBF1|T25 at "
                          f"{nc['L-DEL-DBF1|T25']['state_verdict_counts'].get('FAILS_IN_EVERY_SCENARIO', 0)} states; "
                          f"L-AREA-DBF1|T12 at {nc['L-AREA-DBF1|T12']['state_verdict_counts'].get('FAILS_IN_EVERY_SCENARIO', 0)}",
            "DBF1-BD-02": f"steady point out of domain (dead-head, class R) in some admitted scenario at {len(ood)} states",
            "feed_stability": r["feed_stability"]["class_counts"],
        },
        "sec23_items": {
            "A_feasible_region": "NOT DETERMINABLE in M2: no Hall thrust value may enter (A9.36)",
            "B_physically_feasible_states": 0,
            "C_robust_states": 0,
            "D_worst_state": {"T_required": tr["worst_state"], "delivered_flow_T12": worst_del},
            "E_min_max": {
                "thrust": "NOT_EVALUATED (HALL_NUMERICS_NOT_CONVERGED)",
                "drag_T_required_mN": tr["range_over_states_and_scenarios_mN"],
                "T_minus_D": "NOT_EVALUATED (T_available not evaluated)",
                "bus_power_nonHall_lower_bound_W": {"AIR_PRIMARY": [min(pb_air), max(pb_air)],
                                                    "XE_CONTINGENCY": [min(pb_xe), max(pb_xe)],
                                                    "note": "TBD loads at 0 W; not a P_bus"},
                "delivered_atmospheric_mass_flow_kg_s": [min(alld), max(alld)],
                "delivered_flow_held_state_min_range_kg_s": [min(h[0] for h in held), max(h[0] for h in held)],
                "icp_electron_current_margin": "NOT_EVALUATED (I_e,cap not evaluable; I_d not evaluated)",
                "wet_mass_kg": {"planning_rollup_at_2kg_Xe": r["mass_dbf1"]["planning_wet_kg_at_reference"],
                                "status": "planning value, not a CBE"},
            },
            "F_constraints_physically_closing": "none is evaluated as closing (every constraint is OPEN, NOT_EVALUATED "
                                                "or NON_CLOSING-not-eligible)",
            "G_evidence_limited": "Hall thrust / I_d / P_d, ICP I_e,cap, bus ledger, thermal, mass CBE, life, T - D",
            "H_dominant_blocker": {"code": "HALL_NUMERICS_NOT_CONVERGED", "type": "model-numerics",
                                   "category": "MISSING_EVIDENCE"},
            "H_dominant_design_finding": "DBF-1 delivered flow below the A4 necessary condition (DESIGN_VARIABLE_LIMIT, "
                                         "never eligible)",
            "I_alternatives": "not part of M2 (M3)",
        },
        "t_required_distribution": tr,
        "conclusion_category_input_a9_31_sec_20": r["conclusion_category_input_a9_31_sec_20"],
        "not": ["not the M3 architecture decision", "not a performance prediction", "no Hall thrust value (A9.36)",
                "no change to DBF-1, an RFP requirement or an admitted / scored record"],
        "generated_by": f"{REL}/build_m2_report.py",
    }
    return rep


def md(rep) -> str:
    c = rep["classification_verbatim"]
    L = ["# M2 196-state RFP closure - DBF-1 (report v1)", "",
         f"Record `m2_closure_record_v1.json` (sha256 `{rep['record']['sha256']}`), run manifest "
         f"`m2_run_manifest_v1.json` (`{rep['run_manifest']['sha256']}`), DBF-1 `dbf1_v1.json` "
         f"(`{rep['dbf1']['sha256']}`), addendum A8. This report restates the record; it is not the M3 decision.", "",
         "## Classification (computed, verbatim)", "",
         f"**{c['result']}** at procedure step **{c['procedure_step']}** ({c['procedure']}).", "",
         "## Counts", "", "| mode | required states | layer (a) | layer (b) | Hall closure | non-Hall closure |",
         "|---|---|---|---|---|---|"]
    for m, v in rep["counts"].items():
        L.append(f"| {m} | {v['n_required_states']} | {json.dumps(v['layer_a_status_counts'])} | "
                 f"{json.dumps(v['layer_b_status_counts'])} | {json.dumps(v['hall_closure_counts'])} | "
                 f"{json.dumps(rep['non_hall_closure_counts'][m])} |")
    L += ["", "## Binding constraints, ranked (states)", ""]
    for m, rows in rep["binding_constraints_ranked"].items():
        L.append(f"**{m}**")
        L.append("")
        L.append("| constraint | code | category | type | states |")
        L.append("|---|---|---|---|---|")
        for x in rows:
            L.append(f"| {x['constraint']} | {x['code']} | {x['category']} | {x['blocker_type']} | {x['n_states']} |")
        L.append("")
    L += ["## Blockers by type (required cells, both modes)", ""]
    for t, rows in rep["blockers_by_type"].items():
        L.append(f"- **{t}**: " + ", ".join(f"{x['code']} ({x['cells']})" for x in rows))
    L += ["", "## What would move each blocker", "", "| codes | type | evidence |", "|---|---|---|"]
    for x in rep["what_would_move_each_blocker"]:
        L.append(f"| {x['codes']} | {x['type']} | {x['evidence']} |")
    L += ["", "## DBF-1 baseline deficiencies", "", "| id | finding | category |", "|---|---|---|"]
    for d in rep["dbf1_baseline_deficiencies"]:
        L.append(f"| {d['id']} | {d['finding']} | {d['category']} |")
    mc = rep["m2_confirmation_of_deficiencies"]
    L += ["", f"M2 confirms: BD-01 {mc['DBF1-BD-01']}. BD-02 {mc['DBF1-BD-02']}. Feed-loop classes "
              f"{json.dumps(mc['feed_stability'])} (Python reference, Rust R2 agreement on every row).", "",
          "## A9.31 sec. 23 items", ""]
    for k, v in rep["sec23_items"].items():
        L.append(f"- **{k}**: {json.dumps(v) if not isinstance(v, str) else v}")
    t = rep["t_required_distribution"]
    L += ["", "## T_required = D(state) against 12 / 25 mN", "",
          f"Range {t['range_over_states_and_scenarios_mN'][0]:.4g}-{t['range_over_states_and_scenarios_mN'][1]:.4g} mN "
          f"(body {t['D_body_range_mN'][0]:.4g}-{t['D_body_range_mN'][1]:.4g} mN, intake "
          f"{t['D_intake_range_mN'][0]:.4g}-{t['D_intake_range_mN'][1]:.4g} mN). Per state, unfavourable scenario: "
          f"{json.dumps(t['distribution_unfavourable_scenario (state max)'])}; favourable: "
          f"{json.dumps(t['distribution_favourable_scenario (state min)'])}. Worst {t['worst_state']['state_id']} "
          f"({t['worst_state']['T_required_max_mN']:.4g} mN). Reference body RC-DIAMANT, REFERENCE_PENDING_CUSTOMER_ICD; "
          "body sensitivity per declared case in the record.", "",
          "## Conclusion-category input (A9.31 sec. 20)", "",
          f"{rep['conclusion_category_input_a9_31_sec_20']['category_input']}: "
          f"{rep['conclusion_category_input_a9_31_sec_20']['text']}. Input to M3, not the decision.", ""]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    rep = build()
    out = {"M2_REPORT_v1.json": (json.dumps(rep, indent=1, ensure_ascii=False) + "\n").encode(),
           "M2_REPORT_v1.md": md(rep).encode()}
    if a.check:
        stale = [k for k, v in out.items() if not (HERE / k).is_file() or (HERE / k).read_bytes() != v]
        print("STALE: %s" % stale if stale else "OK")
        return 1 if stale else 0
    for k, v in out.items():
        (HERE / k).write_bytes(v)
    print("wrote", list(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
