#!/usr/bin/env python3
"""P3 coupled H-1 / downstream-ICP thermal FRAMEWORK (lane fo_a9_6_p3_coupled_thermal, trigger
T_A9_6_P3_COUPLED_THERMAL; owner directive A9.6 sec. 10; A9.2 icp_coupled_thermal, radiative_view_requirement,
13W_pole_allowance, anode_approach).

Deterministic; numpy only (pinned); runs in a few seconds; no Julia.

What it does
  * verifies the sha256 of every pinned immutable input and refuses to run on any mismatch (CLAUDE.md rule 3);
  * registers every input the coupled thermal problem needs (items table: value or TBD, units, basis, source,
    evidence class, status, freeze point, who supplies it: P1 / P2 / hardware / Phase-1 Hall data / owner);
  * evaluates the four A9.2 heat terms (Q_RF/match, Q_collector, Q_plume, Q_Hall->ICP) and the coupled network on
    the REGISTERED inputs: because the P1 / P2 / hardware inputs are TBD, every evaluation is refused and the refusal
    (missing-input list) is recorded - the fail-closed behaviour is part of the deliverable;
  * verifies the view-factor engine against six closed-form catalogue entries (Howell C-40/41/52/77/80/81) and the
    radiosity / network solvers against analytic cases (SYNTHETIC_TEST_DATA_NOT_EVIDENCE geometry and loads);
  * checks that the H2-5 coupling adapter with NO ICP body reproduces the pinned H2-5 v1 solve (temperatures not
    reported: method check only);
  * runs the A9.2 radiative-view design-objective PARAMETRIC STUDY: ICP-induced change of the H-1 radiative view
    factors over a dimensionless ICP geometry grid (evaluation grid, not a design; H-1 at H2-5 range midpoints,
    analog/assumed) and the geometric plume interception of uniform-cone TEST distributions (not plume predictions);
  * writes p3_coupled_thermal_v1.json and P3_COUPLED_THERMAL.md (generated from the JSON).

What it is not: a thermal result, a thermal PASS (ICP_COUPLED_THERMAL and ANODE_THERMAL_CLOSURE stay UNRESOLVED), a
Hall performance prediction (no Hall closure, no 0-D model; plume/discharge quantities are measured inputs, TBD),
an ICP design, an answer to an open owner question, or a change to any H2 / ICD / P1 / P2 deliverable.
Not wired into archengine (goldens do not move).

    python docs/experiments/hall_icp/p3_coupled_thermal/build_p3_coupled_thermal.py          # (re)write outputs
    python docs/experiments/hall_icp/p3_coupled_thermal/build_p3_coupled_thermal.py --check  # exit 1 unless reproduced
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LANE_REL = "docs/experiments/hall_icp/p3_coupled_thermal"
SCRIPT_REL = f"{LANE_REL}/build_p3_coupled_thermal.py"
LIB_REL = f"{LANE_REL}/p3_thermal_lib.py"
JSON_NAME = "p3_coupled_thermal_v1.json"
MD_NAME = "P3_COUPLED_THERMAL.md"
TEST_REL = "tests/test_p3_coupled_thermal.py"
BASE_COMMIT = "c33b22c78b14cd4d6a51ed9bd5de4e046bc98cae"
DATE = "2026-09-30"
LANE = "fo_a9_6_p3_coupled_thermal"
TRIGGER = "T_A9_6_P3_COUPLED_THERMAL"
FREEZE_POINTS = ("NOW", "P1-G0", "LOCK-1", "LOCK-2", "after-evidence")
ITEM_STATUSES = ("OWNER_GIVEN", "DEFINED", "PROPOSED", "TBD", "TBD_AFTER_EVIDENCE", "TBD_AFTER_IMPEDANCE_MAP",
                 "TBD_OWNER", "PENDING", "ANALOG_EVALUATION_ONLY")
SUPPLIERS = ("P1", "P2", "hardware", "phase1_hall", "owner", "H2-5/A9-07 (analog)", "P4", "facility", "this lane")


def _load_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


LIB = _load_module("p3_thermal_lib", LIB_REL)

# ------------------------------------------------------------------------------------------------ pinned inputs
DECISIONS = {
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "governing owner decision A9"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "147 owner answers (machine-readable)"),
    "PACK": ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
             "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976", "147 owner answers (verbatim pack)"),
    "A91": ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
            "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4", "A9.1 follow-up owner decisions"),
    "A92": ("docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json",
            "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03", "A9.2 A9-07 follow-up owner decisions"),
    "A92MD": ("docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md",
              "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9", "A9.2 (verbatim)"),
    "A93": ("docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json",
            "81c69b200b9ce51f8aa745636d7aa4dbbddc39005b064235841722ebfdedad1b", "A9.3 post-A9 tier-1 owner decisions"),
    "A94": ("docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json",
            "b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d", "A9.4 P1/P2 owner decisions"),
    "A95": ("docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json",
            "c9e101f2c409c2d28ad256818c22f13ee801bc532d7e4ef470f375d7bb1fe1d3", "A9.5 P1 closure owner decisions"),
    "A96": ("docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json",
            "d8d8496f4141a7096496d3a893c95c3db524ca501055a26cc868fb35d0ae9327", "A9.6 implementation-first directive"),
    "A96MD": ("docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md",
              "c6ee26e57ea5ca559f4fa4e4a8809b1aa8f3a217e50c534b943fc3ad99240634", "A9.6 (verbatim; binds this lane)"),
}
DELIVERABLES = {
    "H25": ("docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json",
            "68c5be61443d0ef1c7308c4aba265426137292dcf9363e57903e0a1f6c8bc083", "H2-5 thermal network v1 (H-1 side)"),
    "H25PY": ("docs/hardware/h2/h2_5_thermal_network/build_h2_5_thermal_network.py",
              "4e937fa97b104d1004765f5a8a3c624bf702375fb822b81bc97b979446aebbec",
              "H2-5 builder (imported read-only: assemble / solve / property functions)"),
    "H2A9": ("docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json",
             "b428565299c1c41487d9ffa50c174986d2d52c544539f89ca21b7bdbc2ae44fa",
             "A9-07 H2 revisions (uncoupled thermal rerun, ICP heat allowances, A9H-TH-01)"),
    "ICD": ("schemas/interfaces/icp_neutralizer_icd_v1.json",
            "8ec092f284505e7a538d17f568c0d9d763155f9a2ce4541223ddd114169a452c", "A9-03 ICP neutralizer ICD"),
    "OQ3": ("docs/budgets/owner_decisions/owner_questions_state_v3.json",
            "1c2e74340852dfe8c58b1804c3cfda2bfbfb3bfb5d631aaebd715cf716b76af2", "owner-question state v3 (snapshot)"),
    "M16": ("docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json",
            "636cbd3318831f6f56e9833813c4d8c259aef7db3de1c6e503cccce14dade7e2", "M16 v3 subsystem maturity"),
    "EVID": ("docs/EVIDENCE.md", "a2950352141890c12ad33e66766cd003215c807cb29203d21df090349ab90b61",
             "evidence rules (CLAUDE.md rule 10)"),
}
NEVER_PINNED = ["docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                "docs/orchestration/fired_triggers.jsonl", "docs/orchestration/trigger_ledger_v2.jsonl",
                "docs/orchestration/runtime_state.json"]
# P1 / P2 are verified deliverables that parallel A9.6 lanes may extend; they are referenced by id (read at the base
# commit), NOT pinned, so that an A9.6 revision of them cannot break this builder; the test checks the ids still exist.
REFERENCED_NOT_PINNED = {
    "P1": "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
    "P2": "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
}
P1_IDS = ("P1-M-01", "P1-M-02", "P1-M-03", "P1-M-07", "P1-M-10", "P1-M-11", "P1-M-12", "P1-M-14", "P1-M-21",
          "P1-M-27", "P1-IT-26", "P1-IT-36", "P1-IT-42", "P1-IT-19")
P2_IDS = ("RP-CPL", "RP-MIN", "RP-ANT", "HM-F01", "HM-R08", "HM-R09", "CAL-P2-02", "CAL-P2-03", "CAL-P2-08",
          "INS-P2-09")
PENDING_LANES = [
    {"path": "docs/experiments/hall_icp/p4_anode_materials/", "lane": "fo_a9_6_p4_anode_materials (A9.6 sec. 10)",
     "needed_for": "validated continuous-use limits and emittances of the collector / anode candidate materials "
                   "(P3-M-04, P3-R-04); ANODE_THERMAL_CLOSURE stays UNRESOLVED until a material and its limit exist"},
    {"path": "docs/budgets/mass_power_a9_v2/", "lane": "fo_a9_6_mass_power_integration (A9.6 sec. 11)",
     "needed_for": "the ICP / RF / collector power slots whose dissipation enters Q_RF/match and the generator "
                   "conversion loss Q_gen (ICD ICP-43)"},
    {"path": "docs/budgets/xe_accounting_a9_v2/", "lane": "fo_a9_6_xe_accounting (A9.6 sec. 12)",
     "needed_for": "none for the thermal terms (G-REUSE: no dedicated ICP flow); listed for completeness"},
    {"path": "docs/procurement/rfq_a9_v2/", "lane": "fo_a9_6_rfq_completion (A9.6 sec. 13)",
     "needed_for": "thermocouple / sink-sensor lines that measure the P3 verification temperatures"},
]
EXTERNAL_SOURCES = {
    "EXT-HOWELL-CATALOG": {
        "citation": "J. R. Howell, 'A Catalog of Radiation Heat Transfer Configuration Factors' (online edition), "
                    "Section C: factors from finite areas to finite areas",
        "access": "open web pages; equations are published as images; read 2026-09-30 and transcribed into "
                  f"{LIB_REL} (docstrings name each entry); image sha256 recorded",
        "entries": {
            "C-40": {"url": "https://www.thermalradiation.net/sectionc/C-40.html",
                     "title": "Disk to parallel coaxial disk of same radius",
                     "equation_image_sha256": "dc76abbe83d271d14768cf01366dfd47dfb4d3a9442a76f4bd83370f2a3d6169"},
            "C-41": {"url": "https://www.thermalradiation.net/sectionc/C-41.html",
                     "title": "Disk to parallel coaxial disk of unequal radius",
                     "equation_image_sha256": "935ee94d671a8cad39b993bf7c425d6bb084b3f89a6bdd1dcd97742a8dce0301"},
            "C-52": {"url": "https://www.thermalradiation.net/sectionc/C-52.html",
                     "title": "Ring to parallel coaxial ring",
                     "equation_image_sha256": "79975ce65626e631355faea0a99f633eb6fb90bea5cc06d7861329bafe619275"},
            "C-77": {"url": "https://www.thermalradiation.net/sectionc/C-77.html",
                     "title": "Outer surface of cylinder to annular disk at end of cylinder",
                     "equation_image_sha256": "a9099e67b1ffb90f4a618e590c51fe1c29f8ed16210d1b442102a930d32672ad"},
            "C-80": {"url": "https://www.thermalradiation.net/sectionc/C-80.html",
                     "title": "Disk in cylinder base or top to inside surface of right circular cylinder",
                     "equation_image_sha256": "2680447c40a27d1dbe1563f2b6bbf248073867d7b75bcae5ce6ac9127b422b85"},
            "C-81": {"url": "https://www.thermalradiation.net/sectionc/C-81.html",
                     "title": "Inside surface of right cylinder to coaxial disk of same diameter separated from "
                              "base of cylinder",
                     "equation_image_sha256": "29b3865aeaaa9086da61e995ad8829635d38b0d696d86d834f3c0b5294269f58"},
        },
        "evidence_class": "published analog (closed-form geometry relations; exact for the stated configuration)",
    },
    "EXT-GOEBEL-KATZ-2008": {
        "citation": "D. M. Goebel, I. Katz, 'Fundamentals of Electric Propulsion: Ion and Hall Thrusters', JPL Space "
                    "Science and Technology Series, Jet Propulsion Laboratory / California Institute of Technology, "
                    "March 2008",
        "url": "https://descanso.jpl.nasa.gov/SciTechBook/series1/Goebel__cmprsd_opt.pdf",
        "access": "full text, open (JPL DESCANSO); read 2026-09-30",
        "sha256": "a373c8a26137b7c7cd989880c303c4f6c1f84f20a11a02770047f6ba4c249e4e",
        "locators": {
            "electron_energy_2Te": "Eq. (4.2-9), p. 95 (energy removed from the plasma per electron 2kTe/e + phi; "
                                   "derived in Appendix C, Eq. (C-2), p. 467); Eq. (7.3-47), p. 356 and Eq. (7.3-61), "
                                   "pp. 360-361 ('each electron deposits 2kTe/e to the anode for positive plasma "
                                   "potentials')",
            "accelerating_sheath": "p. 356 ('If the plasma potential is negative relative to the anode ... the "
                                   "positive-going sheath potential accelerating electrons into the anode' increases "
                                   "the heating; Eq. (7.3-47) is then 'reasonable, but not worst-case')",
            "ion_energy": "Eq. (4.2-10), p. 95 (ion energy kTe/2e (pre-sheath) + phi (sheath))",
            "wall_power": "Eq. (7.3-45), p. 354 (secondary-electron cooling neglected, p. 355)",
        },
        "evidence_class": "published analog (textbook sheath energy-transmission relations; applicability to the "
                          "ICP collector sheath is an assumption to be checked with P1 data)",
    },
}


def _sha(rel):
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_pins():
    bad = [(rel, h, _sha(rel)) for rel, h, _ in list(DECISIONS.values()) + list(DELIVERABLES.values())
           if _sha(rel) != h]
    if bad:
        raise SystemExit(f"pinned input changed, refusing to build: {bad}")


def _load(key):
    table = DECISIONS if key in DECISIONS else DELIVERABLES
    return json.loads((REPO / table[key][0]).read_text(encoding="utf-8"))


def row(ans, n):
    a = next(x for x in ans["answers"] if x["row"] == n)
    return {"kind": "owner_row", "path": DECISIONS["ANS"][0], "row": n, "covers_ids": a["covers_ids"],
            "answer_sha256": hashlib.sha256(a["owner_answer_verbatim"].encode("utf-8")).hexdigest(),
            "answer_verbatim": a["owner_answer_verbatim"]}


def dec(key, did):
    doc = _load(key)
    decs = doc.get("decisions", {})
    if did not in decs:
        raise SystemExit(f"decision {did} not in {key}")
    return {"kind": {"A91": "A9.1", "A92": "A9.2", "A93": "A9.3", "A94": "A9.4", "A95": "A9.5"}[key],
            "path": DECISIONS[key][0], "sha256": DECISIONS[key][1], "decision": did}


def _find_oq(oq3, qid):
    r = [x for x in oq3["rows"] if x["id"] == qid]
    if not r:
        raise SystemExit(f"owner question {qid} not in owner_questions_state_v3")
    return r[0]


def _r(x, n=5):
    if x is None:
        return None
    return float(f"{x:.{n}g}")


TBD_P1 = "TBD_AFTER_EVIDENCE - requires P1 data"
TBD_P2 = "TBD_AFTER_IMPEDANCE_MAP - requires P2 data"


def item(iid, name, value, units, basis, source, evidence_class, status, freeze_point, supplier, used_by,
         lib_key=None, note=""):
    if status not in ITEM_STATUSES:
        raise SystemExit(f"{iid}: status {status}")
    if freeze_point not in FREEZE_POINTS:
        raise SystemExit(f"{iid}: freeze point {freeze_point}")
    if supplier not in SUPPLIERS:
        raise SystemExit(f"{iid}: supplier {supplier}")
    if status.startswith("TBD") or status == "PENDING":
        if not (isinstance(value, str) and value.startswith(("TBD", "PENDING"))):
            raise SystemExit(f"{iid}: TBD item must carry a 'TBD - requires ...' value")
        if evidence_class is not None:
            raise SystemExit(f"{iid}: TBD item has no evidence class")
    elif evidence_class not in LIB.EVIDENCE_CLASSES:
        raise SystemExit(f"{iid}: evidence class {evidence_class!r}")
    return {"id": iid, "name": name, "value": value, "units": units, "basis": basis, "source": source,
            "evidence_class": evidence_class, "status": status, "freeze_point": freeze_point, "supplier": supplier,
            "used_by": used_by, "lib_key": lib_key, "note": note}


# ------------------------------------------------------------------------------------------------ items
def build_items(h25pm, a92, ans):
    I = []
    P = lambda k: h25pm[k]  # noqa: E731
    # ---- geometry (hardware; LOCK-1)
    I += [
        item("P3-G-01", "axial standoff L of the ICP module datum IP-NEU downstream of IP-EXIT",
             "TBD - requires the KC-1 / ICP module drawing (ICD ICP-02)", "m", "pending", "ICD ICP-02", None, "TBD",
             "LOCK-1", "hardware", ["view factors", "plume interception"], "z_lo of the ICP body"),
        item("P3-G-02", "ICP clear aperture radius r_ap (plume passage; open-tube coaxial first build, A9.3 OQ-VI-03)",
             "TBD - requires the frozen H-1 channel OD and the measured plume divergence (ICD ICP-04)", "m", "pending",
             "ICD ICP-04; A9.3 OQ-VI-03", None, "TBD", "LOCK-1", "hardware", ["view factors", "plume interception"],
             "r_in of the ICP body"),
        item("P3-G-03", "ICP module outer radius r_mod (minimum necessary downstream obstruction, A9.2)",
             "TBD - requires the module envelope (ICD ICP-07)", "m", "pending", "ICD ICP-07; ICP-47", None, "TBD",
             "LOCK-1", "hardware", ["view factors"], "r_out of the ICP body"),
        item("P3-G-04", "ICP module axial length H", "TBD - requires the module envelope (ICD ICP-07)", "m",
             "pending", "ICD ICP-07", None, "TBD", "LOCK-1", "hardware", ["view factors", "plume interception"]),
        item("P3-G-05", "open-frame support open-area fraction tau (A9.2 open-frame support; gray, direction-independent "
             "approximation in the engine)", "TBD - requires the support drawing (ICD ICP-47)", "-", "pending",
             "ICD ICP-47; A9.2 radiative_view_requirement", None, "TBD", "LOCK-1", "hardware", ["view factors"]),
        item("P3-G-06", "ICP surface -> thermal node map (dielectric tube, antenna, collector, body, match) and the "
             "surfaces' zoning", "TBD - requires the ICP module drawing (ICD ICP-07, ICP-21, ICP-47)", "-",
             "pending", "ICD ICP-07 / ICP-21 / ICP-47", None, "TBD", "LOCK-1", "hardware", ["network"],
             "no default map: h25_coupled_network() refuses an unmapped surface"),
        item("P3-G-07", "collector geometry and position relative to the bore / plume (Takahashi-type ion collector)",
             "TBD - requires the ICP module design (ICD ICP-21)", "m", "pending", "ICD ICP-21", None, "TBD",
             "LOCK-1", "hardware", ["view factors", "Q_plume", "Q_collector"]),
        item("P3-G-08", "H-1 front-face radii and body length (R_pf, R_i, R_o, R_ow, R_b, L_b)",
             "TBD - requires the frozen H-1 geometry (PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/, "
             "docs/hardware/h2/h2_7_mechanical_bom/)", "m", "pending",
             f"H2-5 {P('L_ch_m')['id']}, {P('h_ch_m')['id']}, {P('D_out_m')['id']}, {P('t_wall_m')['id']}, "
             f"{P('D_body_m')['id']}, {P('L_body_m')['id']} (analog / assumed ranges; the parametric study uses the "
             "range midpoints as an evaluation point only)", None, "PENDING", "LOCK-1", "H2-5/A9-07 (analog)",
             ["view factors", "network"]),
    ]
    # ---- radiative properties
    I += [
        item("P3-R-01", "ICP upstream-face (Hall-facing) hemispherical emittance",
             "TBD - requires the selected face material / finish data (PENDING docs/experiments/hall_icp/"
             "p4_anode_materials/ for metal candidates)", "-", "pending", "ICD ICP-47", None, "TBD", "after-evidence",
             "P4", ["network", "Q_Hall->ICP"], "icp_eps[<ICP>.up]"),
        item("P3-R-02", "ICP outward-facing surfaces emittance (A9.2 objective: high-emittance outward surfaces)",
             "TBD - requires the selected coating / finish and its temperature capability", "-", "pending",
             "A9.2 radiative_view_requirement; ICD ICP-47", None, "TBD", "after-evidence", "hardware", ["network"],
             "icp_eps[<ICP>.outer], icp_eps[<ICP>.down]"),
        item("P3-R-03", "ICP bore / dielectric tube emittance", "TBD - requires the dielectric material selection",
             "-", "pending", "ICD ICP-07", None, "TBD", "after-evidence", "hardware", ["network"],
             "icp_eps[<ICP>.bore]"),
        item("P3-R-04", "collector emittance", "TBD - requires the collector material (A9.1 A9-03-collector: not "
             "frozen; PENDING docs/experiments/hall_icp/p4_anode_materials/)", "-", "pending",
             "A9.1 A9-03-collector", None, "TBD", "after-evidence", "P4", ["network"]),
        item("P3-R-05", "H-1 exterior emittances (BN walls, metal, anode, finish)",
             {"eps_BN": P("eps_BN")["value"], "eps_metal": P("eps_metal")["value"],
              "eps_anode": P("eps_anode")["value"]}, "-", "analog",
             f"H2-5 {P('eps_BN')['id']}, {P('eps_metal')['id']}, {P('eps_anode')['id']}; finishes H2-5 FINISHES "
             "(EXT-HENNINGER1984)", "published analog", "ANALOG_EVALUATION_ONLY", "after-evidence",
             "H2-5/A9-07 (analog)", ["network"], note="room-temperature / band values used as total hemispherical "
             "(H2-5 limitation, verify)"),
        item("P3-R-06", "facility radiative sink temperature (ground)",
             "TBD_AFTER_EVIDENCE - measured per run (owner row 131); ~300 K chamber walls are a planning case only, "
             "never a score-bearing input", "K", "owner answer", "owner row 131", None, "TBD_AFTER_EVIDENCE",
             "after-evidence", "facility", ["network"], "T_space (ground)"),
        item("P3-R-07", "orbit radiative sink and environmental loads", "H2-5 orbit cases (deep space 0 K; "
             "NASA/TM-2001-211221 solar / albedo / OLR) - carried unchanged; ICP shading of H-1 environmental loads "
             "is NOT modelled (conservative for hot, non-conservative for cold cases)", "K; W/m2", "analog",
             "H2-5 H25-37..42", "published analog", "ANALOG_EVALUATION_ONLY", "LOCK-1", "H2-5/A9-07 (analog)",
             ["network"]),
    ]
    # ---- conduction (hardware)
    I += [
        item("P3-K-01", "conductance ICP body <-> KC-1 carrier (A9.2 objective: thermally isolated mounting)",
             "TBD - requires the mount design (isolators, 350 V class P1Q-14) and a measured / sourced joint "
             "conductance", "W/K", "pending", "A9.2 radiative_view_requirement; A9.4 P1Q-14", None, "TBD", "LOCK-1",
             "hardware", ["network", "Q_Hall->ICP (conductive)"], "icp_cond"),
        item("P3-K-02", "conductance KC-1 carrier <-> H-1 (through the stand / moving platform)",
             "TBD - requires the KC-1 / stand design; depends on the open owner question ICPQ-03 (moving platform)",
             "W/K", "pending", "ICD ICP-06 / ICP-10; owner question ICPQ-03 (OPEN)", None, "TBD", "LOCK-1",
             "hardware", ["network", "Q_Hall->ICP (conductive)"], "icp_cond"),
        item("P3-K-03", "conductance KC-1 carrier <-> stand / spacecraft boundary", "TBD - requires the KC-1 / "
             "stand design (ground) and the spacecraft thermal ICD (flight; owner row 85 cases)", "W/K", "pending",
             "owner row 85; ICD ICP-06", None, "TBD", "LOCK-1", "hardware", ["network"], "icp_cond / icp_fixed"),
        item("P3-K-04", "conductance antenna <-> ICP body", "TBD - requires the antenna mounting design", "W/K",
             "pending", "ICD ICP-19 / ICP-44", None, "TBD", "LOCK-1", "hardware", ["network"], "icp_cond"),
        item("P3-K-05", "conductance collector <-> ICP body (through its 350 V-class insulator)",
             "TBD - requires the collector insulator design (A9.4 P1Q-14)", "W/K", "pending", "A9.4 P1Q-14; ICD ICP-21",
             None, "TBD", "LOCK-1", "hardware", ["network"], "icp_cond"),
        item("P3-K-06", "conductance local match <-> ICP body / carrier (match on / immediately adjacent to the module, "
             "A9.2 OQ-A907-11)", "TBD - requires the selected match hardware and its mounting", "W/K", "pending",
             "A9.2 OQ-A907-11; ICD ICP-13", None, "TBD", "LOCK-1", "hardware", ["network"], "icp_cond"),
        item("P3-K-07", "H-1 internal conductances and mount (H2-5 links)", "H2-5 ranges (H25-30..33): mostly "
             "ASSUMED; G_mount first-ranked driver in H2-5 F4", "W/K; W/(m2 K)", "analog", "H2-5 H25-30..H25-33",
             "assumed", "ANALOG_EVALUATION_ONLY", "LOCK-1", "H2-5/A9-07 (analog)", ["network"]),
    ]
    # ---- P1 inputs
    I += [
        item("P3-P1-01", "ion current collected by the ICP ion-collecting electrode (particle-current magnitude)",
             f"{TBD_P1}: P1-M-11 (collector current, I_e > 0 = net electrons extracted, P1-IT-42) with P1-M-12 (body "
             "current); the ion / electron split at the electrode must be registered", "A", "pending",
             "P1-M-11, P1-M-12, P1-IT-42", None, "TBD_AFTER_EVIDENCE", "after-evidence", "P1", ["Q_collector"],
             "I_ion_collected_A"),
        item("P3-P1-02", "electron current collected by a collecting electrode (particle-current magnitude)",
             f"{TBD_P1}: P1-M-27 (dedicated electron-collecting electrode, ICP45_CAPACITY records, discharge OFF, "
             "A9.4 P1Q-10) or P1-M-11 split", "A", "pending", "P1-M-27, P1-M-11; A9.4 P1Q-10", None,
             "TBD_AFTER_EVIDENCE", "after-evidence", "P1", ["Q_collector"], "I_electron_collected_A"),
        item("P3-P1-03", "collector (surface) potential", f"{TBD_P1}: P1-M-10 V_collector (reference per P1-IT-36)",
             "V", "pending", "P1-M-10, P1-IT-36", None, "TBD_AFTER_EVIDENCE", "after-evidence", "P1", ["Q_collector"],
             "V_surface_V"),
        item("P3-P1-04", "plasma potential at the collector sheath edge",
             "TBD - requires a diagnostic not in the P1 measurement list (new owner question P3Q-01)", "V", "pending",
             "P1 measurement list (no plasma-potential channel)", None, "TBD", "P1-G0", "P1", ["Q_collector"],
             "V_plasma_V"),
        item("P3-P1-05", "electron temperature at the collector sheath edge",
             "TBD - requires a diagnostic not in the P1 measurement list (new owner question P3Q-01)", "eV",
             "pending", "P1 measurement list (no T_e channel)", None, "TBD", "P1-G0", "P1", ["Q_collector"], "T_e_eV"),
        item("P3-P1-06", "switch: surface energy terms (electron work function, ion neutralization) in Q_collector",
             "TBD - requires a cited source for the surface heat-transmission terms (from memory - verify) before the "
             "switch may be INCLUDED; EXCLUDED must be declared explicitly", "-", "pending",
             "this lane (p3_thermal_lib.q_collector)", None, "TBD", "P1-G0", "this lane", ["Q_collector"],
             "surface_energy_terms"),
        item("P3-P1-07", "ICP-module temperatures for model verification (antenna, dielectric, collector, match, "
             "H-1 inner / outer pole, sink)", f"{TBD_P1}: P1-M-21 (records only; ICP_COUPLED_THERMAL = UNRESOLVED)",
             "degC", "pending", "P1-M-21, P1-IT-26", None, "TBD_AFTER_EVIDENCE", "after-evidence", "P1",
             ["verification"]),
        item("P3-P1-08", "Hall discharge current / voltage at Hall-ON consistency points",
             f"{TBD_P1}: P1-M-14 (measured; never predicted)", "A, V", "pending", "P1-M-14", None,
             "TBD_AFTER_EVIDENCE", "after-evidence", "P1", ["Q_collector (Hall-ON)"]),
    ]
    # ---- P2 inputs
    I += [
        item("P3-P2-01", "forward RF power at RP-CPL (generator / 50-ohm side of the local match)",
             f"{TBD_P2}: P1-M-01 / P2 HM-F01", "W", "pending", "P1-M-01; P2 RP-CPL, HM-F01; A9.2 "
             "rf_measurement_reference", None, "TBD_AFTER_IMPEDANCE_MAP", "after-evidence", "P2", ["Q_RF/match"],
             "P_forward_W"),
        item("P3-P2-02", "reflected RF power at RP-CPL", f"{TBD_P2}: P1-M-02", "W", "pending", "P1-M-02; P2 RP-CPL",
             None, "TBD_AFTER_IMPEDANCE_MAP", "after-evidence", "P2", ["Q_RF/match"], "P_reflected_W"),
        item("P3-P2-03", "P_line/match,loss (line + local match, at the logged tuning state)",
             f"{TBD_P2}: P1-M-03; P2 HM-R08 from the CAL-P2-02 / CAL-P2-03 two-ports", "W", "pending",
             "P1-M-03; P2 HM-R08, CAL-P2-02, CAL-P2-03", None, "TBD_AFTER_IMPEDANCE_MAP", "after-evidence", "P2",
             ["Q_RF/match"], "P_line_match_loss_W"),
        item("P3-P2-04", "share of P_line/match,loss dissipated on the ICP module / moving platform",
             f"{TBD_P2}: split of the CAL-P2-02 (line RP-CPL -> RP-MIN) and CAL-P2-03 (match RP-MIN -> RP-ANT) "
             "losses by location", "-", "pending", "P2 CAL-P2-02, CAL-P2-03, RP-MIN", None,
             "TBD_AFTER_IMPEDANCE_MAP", "after-evidence", "P2", ["Q_RF/match"], "f_line_match_loss_on_module"),
        item("P3-P2-05", "share of P_delivered leaving the ICP assembly (extracted electrons / plasma enthalpy, "
             "optical emission)", "TBD_AFTER_EVIDENCE - requires a module energy balance (thermocouple map with RF "
             "on/off, ICD ICP-36 verification); f = 0 (all delivered power dissipated on the module) is admissible "
             "only as an explicitly labelled bound", "-", "pending", "ICD ICP-36 / ICP-43", None,
             "TBD_AFTER_EVIDENCE", "after-evidence", "P2", ["Q_RF/match"], "f_delivered_leaving_module"),
        item("P3-P2-06", "antenna RF current (rms)", f"{TBD_P2}: P1-M-07; P2 INS-P2-09", "A", "pending",
             "P1-M-07; P2 INS-P2-09", None, "TBD_AFTER_IMPEDANCE_MAP", "after-evidence", "P2",
             ["Q_RF/match (antenna ohmic breakdown)"], "I_antenna_rms_A"),
        item("P3-P2-07", "cold antenna resistance at the operating antenna temperature", f"{TBD_P2}: CAL-P2-08",
             "ohm", "pending", "P2 CAL-P2-08", None, "TBD_AFTER_IMPEDANCE_MAP", "after-evidence", "P2",
             ["Q_RF/match (antenna ohmic breakdown)"], "R_antenna_cold_ohm"),
        item("P3-P2-08", "RF generator / match conversion loss Q_gen and its location (module vs platform vs "
             "spacecraft)", "TBD - requires the selected generator's published efficiency or a measured DC-in / RF-out "
             "balance (ICD ICP-43); P_mains,in of the laboratory generator is GROUND/FACILITY_ONLY (A9.3 OQ-RFQ-06)",
             "W", "pending", "ICD ICP-43; A9.3 OQ-RFQ-06", None, "TBD", "LOCK-1", "P2", ["network"]),
    ]
    # ---- Hall plume / discharge (Phase-1 measured; never predicted)
    I += [
        item("P3-H-01", "Hall ion beam current I_beam", "TBD_AFTER_EVIDENCE - requires Phase-1 Faraday-probe data "
             "(no Hall-closure or 0-D prediction may be used: credible Hall set EMPTY)", "A", "pending",
             "CLAUDE.md gate 3; A9 evidence_sequence", None, "TBD_AFTER_EVIDENCE", "after-evidence", "phase1_hall",
             ["Q_plume"], "I_beam_A"),
        item("P3-H-02", "mean ion energy of the intercepted plume", "TBD_AFTER_EVIDENCE - requires Phase-1 RPA / E x B "
             "data", "eV", "pending", "A9 evidence_sequence", None, "TBD_AFTER_EVIDENCE", "after-evidence",
             "phase1_hall", ["Q_plume"], "E_ion_mean_eV"),
        item("P3-H-03", "plume angular current distribution (cumulative fraction vs angle)", "TBD_AFTER_EVIDENCE - "
             "requires a Phase-1 Faraday-probe angular sweep; the uniform-cone distributions of the parametric study "
             "are geometric test distributions, not predictions", "deg, -", "pending", "A9 evidence_sequence", None,
             "TBD_AFTER_EVIDENCE", "after-evidence", "phase1_hall", ["Q_plume"], "cdf_table"),
        item("P3-H-04", "energy accommodation of intercepted plume ions", 1.0, "-", "bound (all ion energy "
             "deposited); a measured value supersedes it", "this lane", "assumed", "PROPOSED", "LOCK-1", "this lane",
             ["Q_plume"], "alpha_energy_accommodation"),
        item("P3-H-05", "H-1 discharge heat deposition fractions and discharge power (H-1 node loads)",
             "H2-5 H25-04..07 xenon-analog ranges; P_d bound H25-02 (air / N2 values unknown; measured in Phase 1)",
             "-; W", "analog", "H2-5 H25-02, H25-04..H25-07", "inferred", "ANALOG_EVALUATION_ONLY", "after-evidence",
             "H2-5/A9-07 (analog)", ["network"]),
        item("P3-H-06", "I_d,max,H1 (registered H-1 maximum discharge current; ICP-45 requirement) and the 8.33 A "
             "stand ceiling (collector-circuit rating only)", "TBD - requires measured / registered H-1 operation "
             "(A9.3 OQ-A907-02); 8.33 A is not evidence that H-1 requires it", "A", "pending",
             "A9.3 OQ-A907-02", None, "TBD", "after-evidence", "P1", ["Q_collector (Hall-ON bound)"]),
    ]
    # ---- margins / rules / limits
    r86 = row(ans, 86)
    I += [
        item("P3-M-01", "heat-load design margin applied to the ICP heat terms", 1.2, "-", "owner answer",
             "owner row 86; ICD ICP-37", "owner-allocation", "OWNER_GIVEN", "NOW", "owner", ["network"],
             note="whether it also applies to environmental loads is the open question OQ-A907-09 (not answered)"),
        item("P3-M-02", "minimum margin below each validated continuous-use temperature limit", 50.0, "K",
             "owner answer", "owner row 86; ICD ICP-37", "owner-allocation", "OWNER_GIVEN", "NOW", "owner",
             ["verification"]),
        item("P3-M-03", "score-bearing temperature abort", "validated continuous-use limit - 50 K", "K",
             "owner decision", "A9.1 UBQ-06", "owner-allocation", "OWNER_GIVEN", "NOW", "owner", ["verification"]),
        item("P3-M-04", "validated continuous-use temperature limits of ICP parts (dielectric, antenna insulation, "
             "collector, feedthrough, match components, carrier interface) and of the H-1 anode",
             "TBD - requires the selected materials' sourced data (PENDING docs/experiments/hall_icp/"
             "p4_anode_materials/; owner row 87: no unsourced anode target)", "degC", "pending",
             "owner rows 86, 87; ICD ICP-37", None, "TBD", "after-evidence", "P4", ["verification"]),
        item("P3-M-05", "mounting-interface cases (temperature and allowable conducted heat)",
             {"T_mount_degC": [20, 40, 60], "Q_mount_allowable_W": [25, 50, 100]}, "degC; W", "owner answer",
             "owner row 85", "owner-allocation", "OWNER_GIVEN", "NOW", "owner", ["network"]),
        item("P3-M-06", "A9-07 uncoupled ICP-heat allowances into H-1 (PO / BP injection; comparison reference, not a "
             "limit)", "copied in a907_allowance_port (from the pinned A9-07 JSON)", "W", "model-derived",
             "docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json recomputations.h25_thermal_rerun."
             "icp_heat_into_h1.min_allowance_W", "model-derived", "DEFINED", "NOW", "H2-5/A9-07 (analog)",
             ["A9-07 allowance port"], note="A9.2 13W_pole_allowance: design-driving warning, not grounds to reject A9"),
    ]
    # ---- ICPQ-10 alternatives carried side by side (owner question OPEN)
    I += [
        item("P3-B-01", "ICP-43 total module heat-load bound, alternative A: 1.20 x (P_fwd,max + P_d,max)",
             "TBD_OWNER - ICPQ-10 OPEN; P_fwd,max TBD_AFTER_IMPEDANCE_MAP, P_d,max TBD (A9.3 OQ-A907-02)", "W",
             "owner question ICPQ-10 alternative A", "ICD ICP-43; owner row 86", None, "TBD_OWNER", "LOCK-1", "owner",
             ["network (bounding)"]),
        item("P3-B-02", "ICP-43 total module heat-load bound, alternative B: 1.20 x 1.5 kW envelope (H2-6 H26-44)",
             "TBD_OWNER - ICPQ-10 OPEN; arithmetic of the alternative if chosen: 1.2 x 1500 W = 1800 W (owner rows "
             "86, 108)", "W", "owner question ICPQ-10 alternative B", "ICD ICP-43; owner rows 86, 108", None,
             "TBD_OWNER", "LOCK-1", "owner", ["network (bounding)"]),
        item("P3-B-03", "RF-path heat allocation basis ICP-36 (500 W x 1.2 = 600 W, allocation term, not a bound)",
             "TBD_OWNER - OQ-A910-06 OPEN (keep 600 W or re-derive from P2); P_line/match,loss adds on top (A9.2)",
             "W", "owner question OQ-A910-06", "ICD ICP-36", None, "TBD_OWNER", "LOCK-1", "owner",
             ["Q_RF/match (allocation cross-check)"]),
    ]
    # ---- numerics
    I += [
        item("P3-N-01", "ray-quadrature resolution (n_pos, n_u, n_phi) of the parametric study / verification",
             {"parametric": list(RES_STUDY), "verification": list(RES_VERIFY), "h25_reproduction": list(RES_REPRO)},
             "-", "evaluation setting", "this lane (verification errors recorded in closed_form_verification)",
             "model-derived", "DEFINED", "NOW", "this lane", ["view factors"]),
        item("P3-N-02", "network solver convergence and energy-closure tolerances",
             {"step_K": 1e-7, "energy_closure_rel": 1e-6}, "K; -", "evaluation setting", "this lane (p3_thermal_lib."
             "solve_network)", "model-derived", "DEFINED", "NOW", "this lane", ["network"]),
    ]
    ids = [x["id"] for x in I]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate item ids")
    return I


RES_STUDY = (8, 16, 32)
RES_VERIFY = (16, 32, 64)
RES_REPRO = (8, 16, 32)
VERIFY_TOL = 0.003


# ------------------------------------------------------------------------------------------------ fail-closed evaluations
def registry_inputs(items):
    """Quantity records for the library, straight from the registry (TBD values stay TBD)."""
    rec = {}
    for it in items:
        if it["lib_key"] and it["lib_key"].isidentifier():
            rec[it["lib_key"]] = {"value": it["value"], "units": it["units"], "evidence_class": it["evidence_class"],
                                  "source": it["source"]}
    return rec


def fail_closed_evaluations(items):
    rec = registry_inputs(items)
    out = {}
    for name, fn in (("Q_RF/match", lambda: LIB.q_rf_match(rec)), ("Q_collector", lambda: LIB.q_collector(rec)),
                     ("Q_plume", lambda: LIB.q_plume(rec, {}))):
        try:
            fn()
            raise SystemExit(f"{name} evaluated on TBD inputs: fail-closed rule broken")
        except LIB.MissingInputError as e:
            out[name] = {"status": "INCOMPLETE_EVIDENCE", "missing": e.missing,
                         "items": sorted({it["id"] for it in items if it["lib_key"] in e.missing})}
    out["Q_Hall->ICP"] = {"status": "INCOMPLETE_EVIDENCE",
                          "missing": ["geometry P3-G-01..08", "emittances P3-R-01..04", "conductances P3-K-01..06",
                                      "Q_plume inputs"],
                          "note": "needs the enclosure (geometry + emittances) solved with ICP temperatures, the carrier "
                                  "conductance path and Q_plume"}
    out["coupled_network"] = {"status": "INCOMPLETE_EVIDENCE",
                              "missing": ["ICP body geometry (P3-G-01..05)", "surface -> node map (P3-G-06)",
                                          "ICP emittances (P3-R-01..04)", "ICP conductances (P3-K-01..06)",
                                          "ICP heat terms (Q_RF/match, Q_collector, Q_plume)",
                                          "measured facility sink per run (P3-R-06, ground)"],
                              "note": "h25_coupled_network() refuses unmapped surfaces / missing emissivities; "
                                      "solve_network() refuses non-convergence and non-closing energy balance"}
    return out


# ------------------------------------------------------------------------------------------------ verification
def closed_form_verification():
    """Engine vs catalogue on SYNTHETIC normalized geometries (method verification, not evidence)."""
    B = LIB.Body
    cases = []

    def run(cid, bodies, emitter, target, ref, args):
        vf = LIB.view_factors(bodies, RES_VERIFY, emitters=[emitter])
        f = vf["F"][emitter][target]
        cases.append({"entry": cid, "configuration_args": args, "closed_form": _r(ref, 6), "engine": _r(f, 6),
                      "abs_error": _r(abs(f - ref), 3), "within_tol": abs(f - ref) <= VERIFY_TOL})
    a = 0.6
    run("C-41", [B("A", 0, 0.5, -0.1, 0), B("B", 0, 0.8, a, a + 0.1)], "A.down", "B.up",
        LIB.vf_disk_to_parallel_coaxial_disk(0.5, 0.8, a), {"r1": 0.5, "r2": 0.8, "a": a})
    run("C-40", [B("A", 0, 0.5, -0.1, 0), B("B", 0, 0.5, a, a + 0.1)], "A.down", "B.up",
        LIB.vf_disk_to_parallel_coaxial_disk_same_radius(0.5, a), {"r": 0.5, "a": a})
    run("C-52", [B("A", 0.2, 0.5, -0.1, 0), B("B", 0.3, 0.8, a, a + 0.1)], "A.down", "B.up",
        LIB.vf_annulus_to_parallel_coaxial_annulus(0.2, 0.5, 0.3, 0.8, a),
        {"r1": 0.2, "r2": 0.5, "r3": 0.3, "r4": 0.8, "a": a})
    run("C-77", [B("C", 0, 0.3, 0, 0.4), B("R", 0.3, 0.8, -0.1, 0)], "C.outer", "R.down",
        LIB.vf_cylinder_outer_to_end_annulus(0.3, 0.8, 0.4), {"r1": 0.3, "r2": 0.8, "h": 0.4})
    run("C-80", [B("A", 0, 0.3, -0.1, 0), B("T", 0.4, 0.6, 0.0, 1.0)], "A.down", "T.bore",
        LIB.vf_disk_in_base_to_cylinder_inside(0.3, 0.4, 1.0), {"r1": 0.3, "r2": 0.4, "h": 1.0})
    run("C-81", [B("T", 0.4, 0.6, 0, 0.5), B("D", 0, 0.4, 0.8, 0.9)], "T.bore", "D.up",
        LIB.vf_cylinder_inside_to_coaxial_disk(0.4, 0.5, 0.3), {"r": 0.4, "h1": 0.5, "h2": 0.3})
    algebra = {"C-52_vs_C-41_disk_algebra_abs_diff": _r(abs(
        LIB.vf_annulus_to_parallel_coaxial_annulus(0.2, 0.5, 0.3, 0.8, a)
        - LIB.vf_annulus_to_annulus_by_disk_algebra(0.2, 0.5, 0.3, 0.8, a)), 3),
        "C-40_vs_C-41_abs_diff": _r(abs(LIB.vf_disk_to_parallel_coaxial_disk_same_radius(0.5, a)
                                        - LIB.vf_disk_to_parallel_coaxial_disk(0.5, 0.5, a)), 3),
        "C-80_vs_1_minus_C-41_abs_diff": _r(abs(LIB.vf_disk_in_base_to_cylinder_inside(0.3, 0.4, 1.0)
                                                - (1 - LIB.vf_disk_to_parallel_coaxial_disk(0.3, 0.4, 1.0))), 3)}
    # summation / reciprocity on a full two-body enclosure
    full = LIB.view_factors([B("H", 0, 0.8, -0.5, 0), B("I", 0.5, 1.0, 0.3, 0.8)], RES_VERIFY)
    summ = max(abs(sum(full["F"][i].values()) - 1.0) for i in full["surfaces"])
    if not all(c["within_tol"] for c in cases):
        raise SystemExit(f"view-factor engine outside tolerance: {cases}")
    return {"data_class": LIB.SYN, "resolution": list(RES_VERIFY), "tolerance_abs": VERIFY_TOL, "cases": cases,
            "closed_form_consistency": algebra, "summation_rule_max_abs_error": _r(summ, 3),
            "reciprocity_max_rel_error_pairs_F_gt_1e-3": _r(full["reciprocity_max_rel"], 3),
            "note": "summation holds by construction (every ray ends on a surface or SPACE); reciprocity is a "
                    "quadrature check; enforce_reciprocity() symmetrizes before any radiosity solve"}


def solver_verification():
    """Analytic checks of the radiosity and network solvers (SYNTHETIC)."""
    S = LIB.SIGMA_SB
    # two infinite-like parallel plates through a closed 2-surface enclosure: q = sigma (T1^4 - T2^4) / (1/e1 + 1/e2 - 1)
    ids = ["a", "b"]
    F = {"a": {"a": 0.0, "b": 1.0, "SPACE": 0.0}, "b": {"a": 1.0, "b": 0.0, "SPACE": 0.0}}
    area = {"a": 1.0, "b": 1.0}
    e1, e2, T1, T2 = 0.8, 0.3, 600.0, 300.0
    res = LIB.radiosity_solve(ids, area, F, {"a": e1, "b": e2}, {"a": T1, "b": T2}, 0.0)
    ref = S * (T1 ** 4 - T2 ** 4) / (1 / e1 + 1 / e2 - 1)
    # one node radiating to black space with a load: T = (Q / (eps A sigma) + T_env^4)^(1/4)
    net = LIB.Network(unknown=["n"], fixed={}, loads={"n": 100.0}, env_rad=[("n", 0.5 * 0.01, 0.0, 3.0)])
    sol = LIB.solve_network(net)
    Tref = (100.0 / (0.5 * 0.01 * S) + 3.0 ** 4) ** 0.25
    # conduction chain to a fixed node: T = T_b + Q (1/G1 + 1/G2)
    net2 = LIB.Network(unknown=["a", "b"], fixed={"c": 300.0}, loads={"a": 10.0}, cond=[("a", "b", 2.0), ("b", "c", 0.5)])
    sol2 = LIB.solve_network(net2)
    return {"data_class": LIB.SYN,
            "parallel_plates_rel_error": _r(abs(res["q_W"]["a"] - ref) / ref, 3),
            "single_node_radiation_abs_error_K": _r(abs(sol["T_K"]["n"] - Tref), 3),
            "conduction_chain_abs_error_K": _r(abs(sol2["T_K"]["a"] - (300.0 + 10.0 * (1 / 2.0 + 1 / 0.5))), 3)}


def h25_reproduction(h25):
    """The H2-5 coupling adapter with NO ICP body must reproduce the pinned H2-5 solve (method check only)."""
    pm = h25.param_map(h25.build_parameters())
    fx = h25.fixed_inputs(pm)
    out = []
    for case in ("ground", "orbit_hot", "orbit_cold"):
        rg = h25.ranges_for(case, pm)
        x = {k: 0.5 * (a + b) for k, (a, b) in rg.items()}
        for finish in ("bare_machined_stainless", "z93_white_inorganic"):
            ref, _ = h25.run(x, fx, case, finish, 1350.0)
            net, info = LIB.h25_coupled_network(h25, x, fx, case, finish, 1350.0, [], {}, {}, RES_REPRO)
            sol = LIB.solve_network(net, T0=450.0)
            out.append({"case": case, "finish": finish,
                        "max_abs_dT_K": _r(max(abs(sol["T_K"][n] - ref[n]) for n in h25.NODES), 3)})
    worst = max(o["max_abs_dT_K"] for o in out)
    if worst > 1e-6:
        raise SystemExit(f"H2-5 reproduction failed: {out}")
    return {"evaluation_point": "H2-5 range midpoints of every uncertain input at P_d = 1350 W (H25-02 bound); "
                                "temperatures NOT reported (method check only, not a thermal result)",
            "cases": out, "max_abs_dT_K": worst,
            "aperture_split": "AN / WI / WO pseudo-surface areas A_k F_k->exit (H2-5 crossed-string factors) sum "
                              "exactly to the aperture annulus area (planar-slot reciprocity), so the split is exact"}


# ------------------------------------------------------------------------------------------------ parametric study
GRID = {"L_over_Ro": (0.5, 1.0, 2.0, 4.0), "rap_over_Ro": (1.0, 1.2, 1.5), "wall_over_Ro": (0.2, 0.6),
        "H_over_Ro": (1.0, 3.0), "tau": (0.0, 0.5)}
PLUME_HALF_ANGLES_DEG = (20.0, 40.0, 60.0)
H1_ZONES = ("H1.PI_face", "H1.aperture", "H1.PO_face", "H1.PO_lateral")


def h1_eval_geometry(h25):
    pm = h25.param_map(h25.build_parameters())
    fx = h25.fixed_inputs(pm)
    rg = h25.ranges_for("ground", pm)
    x = {k: 0.5 * (a + b) for k, (a, b) in rg.items()}
    g = LIB.h25_front_geometry(h25, x, fx)
    src = {k: pm[k]["id"] for k in ("L_ch_m", "h_ch_m", "D_out_m", "t_wall_m", "D_body_m", "L_body_m")}
    return g, src


def uniform_cone_cdf(theta_c_deg, n=91):
    """Uniform current per solid angle inside a cone: C(theta) = (1 - cos theta) / (1 - cos theta_c) (TEST only)."""
    tc = math.radians(theta_c_deg)
    th = [theta_c_deg * i / (n - 1) for i in range(n)]
    return [(t, (1 - math.cos(math.radians(t))) / (1 - math.cos(tc))) for t in th]


def parametric_view_study(h25):
    g, src = h1_eval_geometry(h25)
    Ro = g["R_o"]
    h1 = LIB.h1_body(g)
    base = LIB.view_factors([h1], RES_STUDY, emitters=list(H1_ZONES))
    rows = []
    for L in GRID["L_over_Ro"]:
        for rap in GRID["rap_over_Ro"]:
            for wall in GRID["wall_over_Ro"]:
                for H in GRID["H_over_Ro"]:
                    for tau in GRID["tau"]:
                        icp = LIB.Body("ICP", rap * Ro, (rap + wall) * Ro, L * Ro, (L + H) * Ro, tau=tau)
                        vf = LIB.view_factors([h1, icp], RES_STUDY, emitters=list(H1_ZONES))
                        r = {"L_over_Ro": L, "rap_over_Ro": rap, "wall_over_Ro": wall, "H_over_Ro": H, "tau": tau}
                        for z in H1_ZONES:
                            f_icp = sum(v for k, v in vf["F"][z].items() if k.startswith("ICP."))
                            r[z] = {"F_to_ICP": _r(f_icp, 4), "F_to_SPACE": _r(vf["F"][z]["SPACE"], 4),
                                    "AF_to_ICP_m2": _r(vf["area_m2"][z] * f_icp, 4)}
                        rows.append(r)
    # plume geometric interception of test distributions (opaque bodies, longest body)
    plume = []
    for L in GRID["L_over_Ro"]:
        for rap in GRID["rap_over_Ro"]:
            icp = LIB.Body("ICP", rap * Ro, (rap + 0.6) * Ro, L * Ro, (L + 3.0) * Ro)
            for tc in PLUME_HALF_ANGLES_DEG:
                f = LIB.plume_interception([h1, icp], h1, "H1.aperture", uniform_cone_cdf(tc), RES_STUDY)
                plume.append({"L_over_Ro": L, "rap_over_Ro": rap, "wall_over_Ro": 0.6, "H_over_Ro": 3.0,
                              "cone_half_angle_deg": tc,
                              "f_upstream_face": _r(f["ICP.up"], 4), "f_bore": _r(f["ICP.bore"], 4),
                              "f_escape": _r(f["SPACE"], 4)})
    return {
        "label": "PARAMETRIC_STUDY_NOT_A_DESIGN",
        "status": "COMPUTED_CONDITIONAL",
        "purpose": "A9.2 radiative-view-factor design objective (ICD ICP-47) as a parametric structure: open-frame "
                   "support (tau), minimum obstruction (wall thickness), annular / open optical path (aperture), "
                   "Hall-to-ICP spacing (L), module length (H); isolated mounting and high-emittance outward surfaces "
                   "enter the network (P3-K-01, P3-R-02), not the view factors",
        "h1_geometry": {"values_m": {k: _r(v, 5) for k, v in g.items() if k != "vf"}, "source_ids": src,
                        "basis": "H2-5 range midpoints (ECHT analog + assumed; PENDING H2-1 / H2-7): evaluation point "
                                 "only, not the H-1 design",
                        "evidence_class": "assumed"},
        "icp_model": "one coaxial annular body r_ap..r_ap+wall, z = L..L+H (open-tube coaxial first build, A9.3 "
                     "OQ-VI-03); tau = geometric open-area fraction (gray, direction-independent)",
        "grid": {k: list(v) for k, v in GRID.items()}, "resolution": list(RES_STUDY),
        "baseline_without_icp": {z: {"F_to_SPACE": _r(base["F"][z]["SPACE"], 4),
                                     "area_m2": _r(base["area_m2"][z], 4)} for z in H1_ZONES},
        "rows": rows,
        "plume_geometric_interception": {
            "label": "GEOMETRIC_TEST_DISTRIBUTION_NOT_A_PLUME_PREDICTION",
            "distribution": "uniform current per solid angle inside a cone of the given half-angle, emitted "
                            "identically from every point of the channel-exit annulus",
            "rows": plume},
        "limitations": ["the channel-exit aperture is treated as a diffuse emitter / absorber (cavity radiation is not "
                        "strictly diffuse)", "coarse quadrature on the lateral zone (8 axial points): small F values "
                        "are indicative", "no H-1 thermal consequence is computed here (needs the network with ICP "
                        "inputs)"],
        "reading_rule": "F_to_ICP of a zone = share of its diffuse emission first intercepted by the ICP assembly "
                        "(the ICP-induced loss of view to space); multiplied by the zone emittance and "
                        "sigma (T^4 - T_ICP^4) it bounds the first-order change of that zone's rejection; the "
                        "closure needs the full network with ICP temperatures (INCOMPLETE_EVIDENCE)",
    }


def a907_allowance_port(h2a9):
    ih = h2a9["recomputations"]["h25_thermal_rerun"]["icp_heat_into_h1"]
    lv = ih["min_allowance_W"]["LV-BASE"]
    return {"source": DELIVERABLES["H2A9"][0] + " recomputations.h25_thermal_rerun.icp_heat_into_h1.min_allowance_W",
            "sha256": DELIVERABLES["H2A9"][1],
            "LV-BASE": {"PO": lv["PO"], "BP": lv["BP"]},
            "evidence_class": "model-derived (uncoupled sensitivity; 0 W ICP heat, v1 exterior views)",
            "comparison_rule": "P3 equivalent heat into H-1 (equivalent_heat_into_h1 + carrier conduction + plume "
                               "back-flow) at PO / BP is reported beside these allowances as a ratio; a ratio > 1 is "
                               "a design-driving warning; a ratio <= 1 is NOT a closure (the allowances assume v1 "
                               "exterior views, which the ICP changes) - status stays COMPUTED_CONDITIONAL / "
                               "UNRESOLVED",
            "status": "NOT_EVALUATED (ICP temperatures and heat terms TBD)",
            "a9_2_warning": "A9.2 13W_pole_allowance: the outer coil CO tolerates only about 13 W of ICP heat "
                            "injected at PO at LV-BASE; design-driving warning, not grounds to reject A9"}


# ------------------------------------------------------------------------------------------------ build
def build():
    verify_pins()
    ans, a92, oq3, h2a9, m16 = _load("ANS"), _load("A92"), _load("OQ3"), _load("H2A9"), _load("M16")
    h25 = _load_module("h25_builder_readonly", DELIVERABLES["H25PY"][0])
    h25pm = h25.param_map(h25.build_parameters())
    items = build_items(h25pm, a92, ans)
    a92s = a92["decisions"]["a9_10_statuses"]
    if a92s.get("coupled H-1/ICP thermal closure") != "UNRESOLVED" or a92s.get("anode thermal closure") != "UNRESOLVED":
        raise SystemExit("A9.2 closure statuses changed")
    fixed = _load("A96")["summary"]["fixed_statuses"]
    existing_oq = {}
    for qid in ("ICPQ-03", "ICPQ-09", "ICPQ-10", "OQ-A907-06", "OQ-A907-09", "OQ-A907-10", "OQ-A910-06"):
        r = _find_oq(oq3, qid)
        existing_oq[qid] = {"status": r["status"], "question": r["question"],
                            "p3_handling": {
                                "ICPQ-03": "carrier conduction path P3-K-02 carried for both mountings (platform / "
                                           "fixed); no choice made",
                                "ICPQ-09": "plume interception is computed and reported inside the system boundary "
                                           "(Q_plume); the reporting decision stays the owner's",
                                "ICPQ-10": "both bounding alternatives carried side by side (P3-B-01, P3-B-02)",
                                "OQ-A907-06": "mount-heat lever choice not made; P3 reports carrier / mount heat",
                                "OQ-A907-09": "1.2 margin applied to dissipated ICP loads only; environmental "
                                              "application left open (P3-M-01)",
                                "OQ-A907-10": "no search allowance rule is changed; P3 does not produce closures",
                                "OQ-A910-06": "600 W allocation basis carried as P3-B-03 beside the P2-derived "
                                              "Q_RF/match formula",
                            }[qid]}
    m16_rows = {r["key"]: r for r in m16["rows"]}
    for k in ("thermal_control", "icp_neutralizer_head", "h1_anode_heat_path"):
        if k not in m16_rows:
            raise SystemExit(f"M16 v3 row {k} missing")
    doc = {
        "schema": "p3_coupled_thermal_v1",
        "id": "p3_coupled_thermal_v1",
        "lane": LANE, "trigger": TRIGGER, "date": DATE, "base_commit": BASE_COMMIT,
        "status": "FRAMEWORK_IMPLEMENTED_INPUTS_TBD",
        "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
        "closure_statuses": {"ICP_COUPLED_THERMAL": "UNRESOLVED", "ANODE_THERMAL_CLOSURE": "UNRESOLVED",
                             "source": "A9.2 a9_10_statuses; A9.6 summary.fixed_statuses",
                             "a96_fixed_statuses": fixed},
        "a9_2_statuses_carried": a92s,
        "result_status_vocabulary": list(LIB.RESULT_STATUSES),
        "result_status_rule": "no result of this framework is ever PASS; computed values are COMPUTED_CONDITIONAL "
                              "(with the list of non-measured inputs they are conditional on); refusals are "
                              "INCOMPLETE_EVIDENCE (missing / TBD inputs), OUT_OF_DOMAIN (formula / geometry domain) "
                              "or NUMERICAL_FAILURE (no convergence / energy balance not closed)",
        "generated_by": SCRIPT_REL, "library": LIB_REL, "companion_document": f"{LANE_REL}/{MD_NAME}",
        "test": TEST_REL,
        "what_this_is_not": [
            "not a thermal result and not a thermal PASS: ICP_COUPLED_THERMAL = UNRESOLVED, ANODE_THERMAL_CLOSURE = "
            "UNRESOLVED (A9.2, A9.6)",
            "not a Hall performance prediction: no Hall closure (credible set EMPTY), no 0-D model; beam current, ion "
            "energy, plume divergence and discharge current are measured inputs (TBD)",
            "not an ICP design: the geometry grid is an evaluation grid; no geometry is chosen",
            "not an answer to any open owner question (existing ones carried; two new ones raised)",
            "not a change to H2-5, A9-07, the ICD, P1 or P2 (all read-only)",
            "not wired into abep_sim/archengine.py (goldens do not move)"],
        "decision_pins": [{"key": k, "path": p, "sha256": h, "role": r} for k, (p, h, r) in DECISIONS.items()],
        "deliverable_pins": [{"key": k, "path": p, "sha256": h, "role": r} for k, (p, h, r) in DELIVERABLES.items()],
        "referenced_not_pinned": {"paths": REFERENCED_NOT_PINNED, "p1_ids": list(P1_IDS), "p2_ids": list(P2_IDS),
                                  "rule": "verified deliverables that parallel A9.6 lanes may extend; referenced by id "
                                          "as read at the base commit; tests/test_p3_coupled_thermal.py checks the ids "
                                          "still exist"},
        "never_pinned": NEVER_PINNED,
        "pending_parallel_lanes": [dict(p, status="PENDING (parallel lane; not read, content never assumed)")
                                   for p in PENDING_LANES],
        "external_sources": EXTERNAL_SOURCES,
        "heat_terms": {
            "Q_RF/match": {"function": "q_rf_match", "formula": "Q = f_on_module P_line/match,loss + (1 - f_leaving) "
                           "P_delivered; P_delivered = P_forward - P_reflected - P_line/match,loss (A9.2); P_forward is "
                           "never P_plasma", "inputs": ["P3-P2-01", "P3-P2-02", "P3-P2-03", "P3-P2-04", "P3-P2-05"],
                           "optional_breakdown": "antenna ohmic I_ant,rms^2 R_ant,cold (P3-P2-06, P3-P2-07) with a "
                                                 "consistency flag vs P_delivered"},
            "Q_collector": {"function": "q_collector", "formula": "Q = I_e,coll (2 T_e + max(0, V_s - V_p)) + I_i,coll "
                            "(T_e/2 + max(0, V_p - V_s)) [+ I_e phi_wf + I_i (E_iz - phi_wf) only if the switch is "
                            "INCLUDED]", "source": "EXT-GOEBEL-KATZ-2008 Eq. (4.2-9), (4.2-10), (7.3-47), (7.3-61), "
                            "Appendix C; surface terms from memory - verify",
                            "inputs": ["P3-P1-01", "P3-P1-02", "P3-P1-03", "P3-P1-04", "P3-P1-05", "P3-P1-06"],
                            "note": "Hall-ON: the discharge loop closes through the ICP ion collector (ICD ICP-22), "
                                    "so its ion current scales with I_d; ICP-45 capacity (discharge OFF, A9.4 P1Q-10): "
                                    "the dedicated electron-collecting electrode takes 2 T_e (+ acceleration) per "
                                    "electron"},
            "Q_plume": {"function": "plume_interception + q_plume", "formula": "Q_s = alpha_E f_int,s I_beam "
                        "E_ion,mean, f_int from the ray engine with the measured angular CDF",
                        "inputs": ["P3-H-01", "P3-H-02", "P3-H-03", "P3-H-04", "P3-G-01..05", "P3-G-07"],
                        "omitted_terms": ["charge-exchange ions", "fast neutrals", "plume electrons",
                                          "sputtered-atom deposition"]},
            "Q_Hall->ICP": {"function": "q_hall_to_icp (+ exchange_between, network carrier links)",
                            "formula": "Q = Q_rad (net H-1 -> ICP, radiosity) + Q_cond,carrier + Q_plume",
                            "inputs": ["P3-G-*", "P3-R-*", "P3-K-01", "P3-K-02", "Q_plume inputs"]},
            "H-1_view_change": {"function": "h1_view_change / equivalent_heat_into_h1",
                                "formula": "Delta F_space per H-1 zone; equivalent heat = net radiative loss without "
                                           "ICP - with ICP at fixed temperatures (first order)",
                                "inputs": ["P3-G-*", "P3-R-*", "H-1 temperatures (network)"]},
            "coupled_network": {"function": "h25_coupled_network + solve_network",
                                "nodes_h1": list(h25.NODES), "nodes_icp": "declared per design (e.g. ICP_BODY, "
                                "ICP_DIELECTRIC, ICP_ANTENNA, ICP_COLLECTOR, ICP_MATCH, KC1_CARRIER) - no default set",
                                "coupling": "H-1 front radiators (AN / WI / WO through the exit aperture, PI face, PO "
                                            "front annulus and lateral) and ICP surfaces in one gray-diffuse radiosity "
                                            "enclosure closed by SPACE; H2-5 internal links, coil R(T) and remaining "
                                            "boundaries unchanged; carrier conduction links to H-1 BP or the mount",
                                "limitations": ["ICP shading of H-1 solar / albedo / OLR loads not modelled",
                                                "H-1 wall-end rings reradiating (not in H2-5)",
                                                "open-frame bodies: gray direction-independent open-area fraction",
                                                "diffuse gray surfaces; room-temperature emittances (H2-5 limitation)",
                                                "lumped nodes; steady state only"]},
        },
        "items": items,
        "fail_closed_evaluations": fail_closed_evaluations(items),
        "closed_form_verification": closed_form_verification(),
        "solver_verification": solver_verification(),
        "h25_reproduction_check": h25_reproduction(h25),
        "radiative_view_parametric_study": parametric_view_study(h25),
        "a907_allowance_port": a907_allowance_port(h2a9),
        "inputs_by_supplier": {s: [(it["id"], it["freeze_point"]) for it in items if it["supplier"] == s]
                               for s in SUPPLIERS},
    }
    doc["interface_demands"] = interface_demands()
    doc["owner_answers_applied"] = owner_answers_applied(ans)
    doc["open_owner_questions"] = open_owner_questions()
    doc["existing_open_owner_questions_carried"] = existing_oq
    doc["historical_reuse"] = [
        {"path": DELIVERABLES[k][0], "sha256": DELIVERABLES[k][1], "use": u} for k, u in (
            ("H25PY", "H-1 side: assemble / solve / property functions imported read-only; the coupled adapter "
                      "reproduces its solve with no ICP body"),
            ("H25", "H-1 parameter ids and ranges (analog / assumed) for the evaluation geometry"),
            ("H2A9", "A9-07 uncoupled ICP-heat allowances (PO / BP) and A9H-TH-01 requirement"),
            ("ICD", "ICP-02, ICP-04, ICP-07, ICP-13, ICP-21, ICP-22, ICP-29, ICP-36, ICP-37, ICP-43, ICP-47"),
            ("M16", "rows thermal_control, icp_neutralizer_head, h1_anode_heat_path"))]
    doc["m16_impact"] = m16_impact(m16_rows)
    doc["compliance"] = {
        "no_pass_status": True, "closure_statuses_unresolved": True, "no_hall_prediction": True,
        "tbd_items_have_no_evidence_class": all(it["evidence_class"] is None for it in items
                                                if it["status"].startswith("TBD") or it["status"] == "PENDING"),
        "governance_files_not_pinned": True, "archengine_untouched": True,
        "outputs_regenerable": f"python {SCRIPT_REL} --check"}
    return doc


def interface_demands():
    return {
        "p3_needs": [
            {"from": "P1 (docs/experiments/hall_icp/p1_icp_bench/)", "what": "collector ion / electron currents, "
             "collector potential, body current, Hall I_d / V_d at consistency points, module temperature records",
             "items": ["P3-P1-01", "P3-P1-02", "P3-P1-03", "P3-P1-07", "P3-P1-08"], "freeze": "after-evidence"},
            {"from": "P1 (registration at P1-G0)", "what": "plasma potential and T_e at the collector sheath edge, or "
             "an accepted calorimetric alternative (P3Q-01)", "items": ["P3-P1-04", "P3-P1-05"], "freeze": "P1-G0"},
            {"from": "P2 (docs/experiments/hall_icp/p2_impedance_map/)", "what": "P_forward, P_reflected, "
             "P_line/match,loss and its on-module share, P_delivered, antenna current, cold antenna resistance",
             "items": ["P3-P2-01", "P3-P2-02", "P3-P2-03", "P3-P2-04", "P3-P2-06", "P3-P2-07"],
             "freeze": "after-evidence (TBD_AFTER_IMPEDANCE_MAP)"},
            {"from": "hardware (KC-1 / ICP module drawing; H2-1 / H2-7 frozen H-1 geometry)", "what": "standoff, "
             "aperture, envelope, open-frame fraction, surface-node map, collector position, conductances, emittances",
             "items": ["P3-G-01..08", "P3-K-01..06", "P3-R-02", "P3-R-03"], "freeze": "LOCK-1"},
            {"from": "Phase-1 Hall data", "what": "I_beam, mean ion energy, angular current distribution (never "
             "predicted)", "items": ["P3-H-01", "P3-H-02", "P3-H-03"], "freeze": "after-evidence"},
            {"from": "P4 (PENDING docs/experiments/hall_icp/p4_anode_materials/)", "what": "validated continuous-use "
             "limits and emittances of collector / anode candidates", "items": ["P3-M-04", "P3-R-01", "P3-R-04"],
             "freeze": "after-evidence"},
            {"from": "facility", "what": "radiative sink temperature measured per run (owner row 131)",
             "items": ["P3-R-06"], "freeze": "after-evidence"},
            {"from": "owner", "what": "ICPQ-10 bound choice; P3Q-01; P3Q-02", "items": ["P3-B-01", "P3-B-02",
                                                                                      "P3-B-03"], "freeze": "LOCK-1"},
        ],
        "p3_supplies": [
            {"to": "ICD ICP-43 (total module heat load)", "what": "the Q_RF/match + Q_collector + Q_plume "
             "decomposition and the functions that evaluate it once inputs exist"},
            {"to": "ICD ICP-47 (radiative-view objective)", "what": "view-factor calculator and the parametric "
             "structure over standoff / aperture / wall / length / open-area fraction"},
            {"to": "ICD ICP-37 / A9.1 UBQ-06", "what": "node temperatures of the coupled network (once inputs exist) "
             "for the >= 50 K margin and abort checks; never a PASS by itself"},
            {"to": "A9-07 / H2 (docs/hardware/h2_a9_revisions/, read-only)", "what": "equivalent heat into H-1 PO / "
             "BP comparable with the A9-07 allowances (a907_allowance_port)"},
            {"to": "P1 / P2 instrumentation", "what": "the verification temperature set (P3-P1-07) and the "
             "calorimetric energy balance that fixes f_leaving (P3-P2-05)"},
            {"to": "M16 v3 rows thermal_control / icp_neutralizer_head / h1_anode_heat_path", "what": "framework "
             "status (m16_impact)"},
            {"to": "system RVM (A9.6 sec. 15; parallel lane)", "what": "thermal rows stay INCOMPLETE_EVIDENCE"},
        ],
    }


def owner_answers_applied(ans):
    rows = []
    for n, how in ((70, "collector bias measured / controlled separately: its potential is an explicit Q_collector "
                        "input (P3-P1-03)"),
                   (72, "13.56 MHz; directional-coupler forward / reflected are the Q_RF/match inputs (P3-P2-01/02)"),
                   (85, "20/40/60 degC mount and 25/50/100 W conducted-heat cases registered (P3-M-05)"),
                   (86, ">= 50 K margin and 1.2 heat-load margin registered (P3-M-01/02); never relaxed"),
                   (87, "no anode temperature target invented; ANODE_THERMAL_CLOSURE stays UNRESOLVED"),
                   (108, "1.5 kW used only as the ICPQ-10 alternative-B arithmetic (P3-B-02), not chosen"),
                   (131, "facility sink measured per run; ~300 K only a planning case (P3-R-06)"),
                   (133, "matched sham routing unaffected; the sham's thermal equivalence is OQ-A910-05 territory "
                         "(not answered)")):
        r = row(ans, n)
        r["applied"] = how
        rows.append(r)
    for key, did, how in (
            ("A92", "icp_coupled_thermal", "all five required terms implemented; status UNRESOLVED"),
            ("A92", "radiative_view_requirement", "parametric study structure over the six objective parameters"),
            ("A92", "13W_pole_allowance", "negligible-coupling assumption not used anywhere; A9-07 allowance port"),
            ("A92", "anode_approach", "anode heat path stays a network input (H2-5 G_anode_mount); no material chosen"),
            ("A92", "anode_316L", "316L REJECTED_AS_CURRENT_BASELINE carried; no anode material assumed"),
            ("A92", "rf_measurement_reference", "P_delivered = P_forward - P_reflected - P_line/match,loss in "
                                                "q_rf_match; P_forward never used as plasma power"),
            ("A92", "OQ-A907-11", "local match on / adjacent to the module: its loss is a module-side heat term"),
            ("A92", "rf_500W", "500 W never used as a rating; only in the carried OQ-A910-06 allocation item"),
            ("A92", "a9_10_statuses", "all ten statuses carried unchanged"),
            ("A91", "UBQ-06", "abort at validated limit - 50 K registered (P3-M-03)"),
            ("A91", "A9-03-collector", "collector material not frozen: its emittance / limit TBD (P3-R-04, P3-M-04)"),
            ("A91", "HIQ-06", "G-REUSE primary: no dedicated ICP gas flow enters the thermal terms"),
            ("A91", "OQ-A902-03", "no fixed Hall/ICP power split assumed"),
            ("A93", "OQ-VI-03", "open-tube coaxial first build -> coaxial annular ICP body model"),
            ("A93", "OQ-A907-02", "8.33 A stand ceiling only a rating; I_d,max,H1 TBD (P3-H-06)"),
            ("A93", "OQ-RFQ-06", "laboratory mains generator GROUND/FACILITY_ONLY: P_mains,in never a P_bus input"),
            ("A94", "P1Q-10", "capacity records discharge OFF: Q_collector for the dedicated electron collector"),
            ("A94", "P1Q-13", "anode floating during capacity records: no discharge heat in that configuration"),
            ("A94", "P1Q-14", "350 V class isolation of body / collector: conductance paths through isolators TBD"),
            ("A95", "P1Q-15", "signed terminal currents stay in P1 records; Q_collector takes particle-current "
                              "magnitudes whose split must be registered"),
            ("A95", "P1Q-16", "I_e,cap signed formula untouched (not a thermal input)")):
        d = dec(key, did)
        d["applied"] = how
        rows.append(d)
    rows.append({"kind": "A9.6", "path": DECISIONS["A96"][0], "sha256": DECISIONS["A96"][1],
                 "decision": "sec. 10 P3 / summary.fixed_statuses",
                 "applied": "framework built now with every missing input TBD; no thermal PASS"})
    return rows


def open_owner_questions():
    return [
        {"id": "P3Q-01", "question": "Q_collector needs the plasma potential and electron temperature at the collector "
         "sheath edge (P3-P1-04/05), which are not in the P1 measurement list. Add a probe diagnostic (Langmuir or "
         "emissive probe near the collector) to P1, or accept a calorimetric collector energy balance (thermocouple "
         "map + registered conductances, RF on/off and current steps) as the Q_collector evidence instead?",
         "alternatives": ["A: probe diagnostic added at P1-G0 (sheath-term route)",
                          "B: calorimetric energy balance (direct heat route; sheath terms become a cross-check)",
                          "C: both (probe + calorimetry)"],
         "status": "TBD_OWNER", "needed_by": "P1-G0", "blocks": ["Q_collector", "ICP-43"]},
        {"id": "P3Q-02", "question": "For the coupled thermal closure at LOCK-1, is the lumped H2-5 network coupled "
         "through this P3 radiosity enclosure the accepted model class, or is a finer (finite-element / "
         "multi-node) H-1 + ICP model required before any closure statement?",
         "alternatives": ["A: lumped network (this framework) + S1a thermocouple correlation",
                          "B: finer model required before closure"],
         "status": "TBD_OWNER", "needed_by": "LOCK-1", "blocks": ["ICP_COUPLED_THERMAL closure path"]},
    ]


def m16_impact(rows):
    out = []
    for key, note in (
            ("thermal_control", "coupled H-1 / ICP thermal framework exists (software); thermal closure UNRESOLVED; "
                                "blocking inputs P3-G/K/R (hardware), P1/P2 data"),
            ("icp_neutralizer_head", "ICP-43 / ICP-47 now have calculators; values TBD; physical ICP not VERIFIED"),
            ("h1_anode_heat_path", "anode heat path is a network input; ANODE_THERMAL_CLOSURE UNRESOLVED (P4 PENDING)")):
        out.append({"row": rows[key]["row"], "key": key, "proposed_change": "none to maturity (framework only)",
                    "note": note, "rule": "a row becomes READY / VERIFIED only under the repository's evidence rules; "
                                          "software completeness is not physical verification (A9.6 sec. 16)"})
    return out


# ------------------------------------------------------------------------------------------------ markdown
def _v(x):
    if isinstance(x, (dict, list)):
        return "`" + json.dumps(x, ensure_ascii=False) + "`"
    return str(x)


def render_md(doc):
    L = [f"# P3 coupled H-1 / downstream-ICP thermal framework", "",
         f"Generated by `{doc['generated_by']}` from `{LANE_REL}/{JSON_NAME}` (do not edit by hand). Lane `{doc['lane']}`, "
         f"trigger `{doc['trigger']}`, base `{doc['base_commit']}`. Status **{doc['status']}**; A9 status "
         f"`{doc['a9_status']}`. Library: `{doc['library']}`.", "",
         "**Closure statuses:** " + ", ".join(f"{k} = **{v}**" for k, v in doc["closure_statuses"].items()
                                            if k in ("ICP_COUPLED_THERMAL", "ANODE_THERMAL_CLOSURE")) +
         ". Result-status rule: " + doc["result_status_rule"] + ".", "",
         "## What this is not", ""]
    L += [f"- {x}" for x in doc["what_this_is_not"]]
    L += ["", "## A9.2 statuses carried", "", "| item | status |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in doc["a9_2_statuses_carried"].items()]
    L += ["", "## Heat terms", "", "| term | function | formula | inputs |", "|---|---|---|---|"]
    for k, v in doc["heat_terms"].items():
        L.append(f"| {k} | `{v['function']}` | {v.get('formula', v.get('coupling', ''))} | "
                 f"{', '.join(v['inputs']) if 'inputs' in v else '-'} |")
    net = doc["heat_terms"]["coupled_network"]
    L += ["", "Coupled network: " + net["coupling"] + ". H-1 nodes: " + ", ".join(net["nodes_h1"]) + "; ICP nodes: " +
          net["nodes_icp"] + ". Limitations: " + "; ".join(net["limitations"]) + ".", ""]
    L += ["## (a) Items", "",
          "| id | name | value | units | basis | source | evidence | status | freeze | supplier | used by |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for it in doc["items"]:
        L.append(f"| {it['id']} | {it['name']} | {_v(it['value'])} | {it['units']} | {it['basis']} | {it['source']} | "
                 f"{it['evidence_class'] or '-'} | {it['status']} | {it['freeze_point']} | {it['supplier']} | "
                 f"{', '.join(it['used_by'])} |")
    L += ["", "### Inputs by supplier (id, freeze point)", ""]
    for s, lst in doc["inputs_by_supplier"].items():
        if lst:
            L.append(f"- **{s}**: " + ", ".join(f"{i} ({f})" for i, f in lst))
    L += ["", "## Fail-closed evaluations on the registered inputs", "", "| term | status | missing |", "|---|---|---|"]
    for k, v in doc["fail_closed_evaluations"].items():
        L.append(f"| {k} | {v['status']} | {', '.join(v['missing'])} |")
    cf = doc["closed_form_verification"]
    L += ["", "## View-factor engine verification (SYNTHETIC geometry; method check, not evidence)", "",
          f"Resolution {cf['resolution']}, tolerance {cf['tolerance_abs']} (absolute).", "",
          "| catalogue entry | args | closed form | engine | abs error |", "|---|---|---|---|---|"]
    for c in cf["cases"]:
        L.append(f"| {c['entry']} | {_v(c['configuration_args'])} | {c['closed_form']} | {c['engine']} | "
                 f"{c['abs_error']} |")
    L += ["", f"Closed-form consistency: {_v(cf['closed_form_consistency'])}. Summation-rule max error "
          f"{cf['summation_rule_max_abs_error']}; reciprocity max relative error (pairs F > 1e-3) "
          f"{cf['reciprocity_max_rel_error_pairs_F_gt_1e-3']} ({cf['note']}).", ""]
    sv = doc["solver_verification"]
    L += [f"Solver checks (SYNTHETIC): parallel plates rel. error {sv['parallel_plates_rel_error']}; single radiating "
          f"node {sv['single_node_radiation_abs_error_K']} K; conduction chain {sv['conduction_chain_abs_error_K']} K.",
          ""]
    hr = doc["h25_reproduction_check"]
    L += ["## H2-5 reproduction (coupled adapter with no ICP body)", "", hr["evaluation_point"] + ".", "",
          "| case | finish | max abs dT (K) |", "|---|---|---|"]
    L += [f"| {c['case']} | {c['finish']} | {c['max_abs_dT_K']} |" for c in hr["cases"]]
    L += ["", hr["aperture_split"] + ".", ""]
    ps = doc["radiative_view_parametric_study"]
    L += ["## Radiative-view parametric study (" + ps["label"] + ", " + ps["status"] + ")", "", ps["purpose"] + ".", "",
          "H-1 evaluation geometry (" + ps["h1_geometry"]["basis"] + "): " + _v(ps["h1_geometry"]["values_m"]) +
          " from " + _v(ps["h1_geometry"]["source_ids"]) + ". ICP model: " + ps["icp_model"] + ".", "",
          "Without ICP: " + ", ".join(f"{z} F_space {v['F_to_SPACE']} (A {v['area_m2']} m2)"
                                      for z, v in ps["baseline_without_icp"].items()) + ".", "",
          "| L/R_o | r_ap/R_o | wall/R_o | H/R_o | tau | aperture F_ICP | PO face F_ICP | PI face F_ICP | "
          "PO lateral F_ICP |", "|---|---|---|---|---|---|---|---|---|"]
    for r in ps["rows"]:
        L.append(f"| {r['L_over_Ro']} | {r['rap_over_Ro']} | {r['wall_over_Ro']} | {r['H_over_Ro']} | {r['tau']} | "
                 f"{r['H1.aperture']['F_to_ICP']} | {r['H1.PO_face']['F_to_ICP']} | {r['H1.PI_face']['F_to_ICP']} | "
                 f"{r['H1.PO_lateral']['F_to_ICP']} |")
    pl = ps["plume_geometric_interception"]
    L += ["", f"Plume geometric interception ({pl['label']}; {pl['distribution']}):", "",
          "| L/R_o | r_ap/R_o | cone half-angle (deg) | upstream face | bore | escape |", "|---|---|---|---|---|---|"]
    L += [f"| {r['L_over_Ro']} | {r['rap_over_Ro']} | {r['cone_half_angle_deg']} | {r['f_upstream_face']} | "
          f"{r['f_bore']} | {r['f_escape']} |" for r in pl["rows"]]
    L += ["", ps["reading_rule"] + ". Limitations: " + "; ".join(ps["limitations"]) + ".", ""]
    ap = doc["a907_allowance_port"]
    L += ["## A9-07 allowance port", "", f"LV-BASE allowances (W; {ap['evidence_class']}): PO {_v(ap['LV-BASE']['PO'])}; "
          f"BP {_v(ap['LV-BASE']['BP'])}. {ap['comparison_rule']}. Status: {ap['status']}. {ap['a9_2_warning']}.", ""]
    L += ["## (b) Interface demands", "", "P3 needs:", ""]
    L += [f"- from {d['from']}: {d['what']} ({', '.join(d['items'])}; freeze {d['freeze']})"
          for d in doc["interface_demands"]["p3_needs"]]
    L += ["", "P3 supplies:", ""]
    L += [f"- to {d['to']}: {d['what']}" for d in doc["interface_demands"]["p3_supplies"]]
    L += ["", "## (c) Owner answers applied", "", "| source | id | applied |", "|---|---|---|"]
    for r in doc["owner_answers_applied"]:
        rid = f"row {r['row']}" if r["kind"] == "owner_row" else r["decision"]
        L.append(f"| {r['kind']} `{r['path']}` | {rid} | {r['applied']} |")
    L += ["", "## (d) Open owner questions (new)", ""]
    for q in doc["open_owner_questions"]:
        L.append(f"- **{q['id']}** ({q['status']}, needed by {q['needed_by']}): {q['question']} Alternatives: " +
                 "; ".join(q["alternatives"]) + ".")
    L += ["", "Existing open questions carried (not answered here):", ""]
    for k, v in doc["existing_open_owner_questions_carried"].items():
        L.append(f"- {k} ({v['status']}): {v['p3_handling']}")
    L += ["", "## (e) Historical reuse", "", "| path | sha256 | use |", "|---|---|---|"]
    L += [f"| `{h['path']}` | `{h['sha256']}` | {h['use']} |" for h in doc["historical_reuse"]]
    L += ["", "## (f) M16 impact", "", "| row | key | proposed change | note |", "|---|---|---|---|"]
    L += [f"| {m['row']} | {m['key']} | {m['proposed_change']} | {m['note']} |" for m in doc["m16_impact"]]
    L += ["", "## Pins", "", "| key | path | sha256 |", "|---|---|---|"]
    L += [f"| {p['key']} | `{p['path']}` | `{p['sha256']}` |" for p in doc["decision_pins"] + doc["deliverable_pins"]]
    L += ["", "Referenced, not pinned (parallel A9.6 lanes may extend them): " +
          ", ".join(f"`{v}`" for v in doc["referenced_not_pinned"]["paths"].values()) + ". Parallel lanes PENDING: " +
          ", ".join(f"`{p['path']}`" for p in doc["pending_parallel_lanes"]) + ". Never pinned: " +
          ", ".join(f"`{p}`" for p in doc["never_pinned"]) + ".", "", "## External sources", ""]
    for k, v in doc["external_sources"].items():
        L.append(f"- **{k}**: {v['citation']}. {v['access']}. Evidence: {v['evidence_class']}.")
        if "entries" in v:
            L += [f"  - {e}: {d['title']} ({d['url']})" for e, d in v["entries"].items()]
        if "locators" in v:
            L.append(f"  - {v['url']} (sha256 `{v['sha256']}`); " + "; ".join(f"{a}: {b}" for a, b in
                                                                           v["locators"].items()))
    L.append("")
    return "\n".join(L)


def render():
    doc = build()
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n", render_md(doc)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the outputs are reproduced byte for byte")
    args = ap.parse_args(argv)
    js, md = render()
    outs = ((HERE / JSON_NAME, js), (HERE / MD_NAME, md))
    if args.check:
        bad = [p.name for p, t in outs if not p.exists() or p.read_text(encoding="utf-8") != t]
        if bad:
            print("NOT REPRODUCED:", ", ".join(bad))
            return 1
        print("OK: outputs reproduced")
        return 0
    for p, t in outs:
        p.write_text(t, encoding="utf-8")
    print("wrote", ", ".join(p.name for p, _ in outs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
