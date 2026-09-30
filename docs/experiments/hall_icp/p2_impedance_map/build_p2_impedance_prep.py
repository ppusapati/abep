#!/usr/bin/env python3
"""P2 ICP impedance-map INSTRUMENT PREPARATION package (follow-on fo_a9_p2_impedance_prep, trigger
T_A9_P2_IMPEDANCE_PREP; owner decision A9.3 authorizations.P2; owner A9.4 P2Q-05 incorporated mechanically by
fo_a9_4_incorporation, trigger T_A9_4_INCORPORATION).

Deterministic, standard library only, no Julia, well under a second.

What it does
  * verifies the sha256 of every pinned immutable input (owner decisions A4..A7, A9, the 147 answers + verbatim pack,
    A9.1, A9.2, A9.3 + their verbatim records, and the verified A9 deliverables it reads) and refuses to run on any
    mismatch (no fallback, CLAUDE.md rule 3);
  * cross-checks every id it cites (UB-RF-xx, ICP-xx, A9H-xx, RFQ-04-Rxx, VI-RF-xx, TK-xx, RF-matrix entries, M16 v3
    rows, owner-question ids, owner rows) against the pinned inputs and copies analog values from them (never typed);
  * writes p2_impedance_prep_v1.json (the package), P2_IMPEDANCE_PREP.md (generated from the JSON) and
    p2_impedance_record_schema_v1.json (the record / calibration-set JSON Schema, generated from the reducer's own
    field tuples so the data model and the reducer cannot drift);
  * runs the pure reducer (p2_impedance_reducer.py) on SYNTHETIC closed-form cases and records the results labelled
    SYNTHETIC_TEST_DATA_NOT_EVIDENCE.

What it is not: the plasma impedance map (that starts only after P1 hands over a stable ICP operating region, A9.3),
a prediction of any impedance, thrust, efficiency, current or plasma state, a component rating (RF ratings stay
TBD_AFTER_IMPEDANCE_MAP, A9.2), a trip threshold, a procurement or an answer to any open owner question. Not wired into
archengine (goldens do not move).

    python docs/experiments/hall_icp/p2_impedance_map/build_p2_impedance_prep.py          # (re)write outputs
    python docs/experiments/hall_icp/p2_impedance_map/build_p2_impedance_prep.py --check  # exit 1 unless reproduced
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
LANE_REL = "docs/experiments/hall_icp/p2_impedance_map"
SCRIPT_REL = f"{LANE_REL}/build_p2_impedance_prep.py"
REDUCER_REL = f"{LANE_REL}/p2_impedance_reducer.py"
JSON_NAME = "p2_impedance_prep_v1.json"
MD_NAME = "P2_IMPEDANCE_PREP.md"
SCHEMA_NAME = "p2_impedance_record_schema_v1.json"
TEST_REL = "tests/test_p2_impedance_prep.py"
BASE_COMMIT = "ee9dc7db7d11e0b5f1d8b514258778ac1b6030d3"
A94_INC_BASE = "875ed6d0a87202bc92706b28551b0e22eda2014d"   # base of the A9.4 incorporation (fo_a9_4_incorporation)
DATE = "2026-09-30"
LANE = "fo_a9_p2_impedance_prep"
TRIGGER = "T_A9_P2_IMPEDANCE_PREP"
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation", "owner-stated", "published analog")
STATUSES = ("OWNER_GIVEN", "DEFINED", "PROPOSED", "TBD", "PENDING", "TBD_AFTER_IMPEDANCE_MAP")
P1_PENDING = "PENDING docs/experiments/hall_icp/p1_icp_bench/"
RFQV2_PENDING = "PENDING docs/procurement/rfq_a9_v2/"
RATINGS_TBD = "TBD_AFTER_IMPEDANCE_MAP"

_spec = importlib.util.spec_from_file_location("p2_impedance_reducer", str(HERE / "p2_impedance_reducer.py"))
RED = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RED)

# ------------------------------------------------------------------------------------------------ pinned inputs
DECISIONS = {
    "A4": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json",
           "beec91f9eca3ca0257c5ee88dcd193c87481660b9368b65c6d10b3b3bdae23b4", "A4 owner decisions (force/DC/RF traceability)"),
    "A5": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
           "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621", "A5 (binding; historical upstream topology)"),
    "A6": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
           "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180", "A6 (binding)"),
    "A7": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
           "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925", "A7 execution model (binding)"),
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "governing owner decision A9"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "147 owner answers (machine-readable)"),
    "PACK": ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
             "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976", "147 owner answers (verbatim pack)"),
    "A91": ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
            "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4", "A9.1 follow-up owner decisions"),
    "A91MD": ("docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md",
              "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e", "A9.1 (verbatim)"),
    "A92": ("docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json",
            "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03", "A9.2 A9-07 follow-up owner decisions"),
    "A92MD": ("docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md",
              "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9", "A9.2 (verbatim)"),
    "A93": ("docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json",
            "81c69b200b9ce51f8aa745636d7aa4dbbddc39005b064235841722ebfdedad1b", "A9.3 post-A9 tier-1 owner decisions"),
    "A93MD": ("docs/decisions/OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md",
              "55a1fd84558a9590705bb82aa11db5e2b9136dd1d83a957d26614c435c707411", "A9.3 (verbatim; binds this lane)"),
    "A94": ("docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json",
            "b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d", "A9.4 P1/P2 owner decisions"),
    "A94MD": ("docs/decisions/OD_2026_09_30_A9_4_P1_P2_OWNER_DECISIONS.md",
              "53cc026d63f85bd416f8ed8f4e8f9f7e7d7fc4429dccc45b86a51390b5c08b1c", "A9.4 (verbatim; P2Q-05)"),
}
DELIVERABLES = {
    "UB": ("docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json",
           "c6567e6d0bbc008bedd5b9c14a9716f117144ab6952b9c498f7b0c75e02a624d", "A9-04 uncertainty budget"),
    "ICD": ("schemas/interfaces/icp_neutralizer_icd_v1.json",
            "8ec092f284505e7a538d17f568c0d9d763155f9a2ce4541223ddd114169a452c", "A9-03 ICP neutralizer ICD"),
    "H2A9": ("docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json",
             "b428565299c1c41487d9ffa50c174986d2d52c544539f89ca21b7bdbc2ae44fa", "A9-07 H2 revisions (RF reference plane)"),
    "RFQ": ("docs/procurement/rfq_a9/rfq_a9_v1.json",
            "d2e654cf49d89b8f84a65e5bf7626517a37c02d0a4a0de97f128c3155ef4a84b", "A9-09 RFQ v1 (predates A9.2/A9.3)"),
    "RFQ04": ("docs/procurement/rfq_a9/packages/RFQ-04_rf_chain.md",
              "0ea196f72e8da254e50787c4f58bdb665939f770028a0013a9f9bc57b0b0e9a4", "RFQ v1 package RFQ-04 (RF chain)"),
    "M16": ("docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json",
            "636cbd3318831f6f56e9833813c4d8c259aef7db3de1c6e503cccce14dade7e2", "M16 v3 subsystem maturity"),
    "EVI": ("docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json",
            "092e4ca8e1827dd2e9558058a204f46510f2633316ce188e7126b697ec6d0b53", "A9-05 Takahashi 2024 extraction"),
    "RFM": ("docs/evidence/rf_source/rf_evidence_matrix.json",
            "5f6d4e0ede8b2e21e45b740c28ac9320e7ddd6cfd70ef05012f85712ae0ac8e8", "RF-source evidence matrix (historical)"),
    "VI": ("docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json",
           "fac472e370b54875df5dea90c3c7740403da5ac1edd1af29b43ed09ee679d450", "A9-05vi validation-input list"),
    "OQ3": ("docs/budgets/owner_decisions/owner_questions_state_v3.json",
            "1c2e74340852dfe8c58b1804c3cfda2bfbfb3bfb5d631aaebd715cf716b76af2", "owner-question state v3 (snapshot)"),
    "INS": ("docs/experiments/instrumentation/instrumentation_definition_v1.json",
            "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96", "W4 instrumentation definition"),
    "MS": ("docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json",
           "55c11dc2d22fd92d95b498f72d60f2cdc0c62a45940da2446514049bd5130865", "metrology measurement spec"),
    "BUS": ("docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
            "9f6e074cc2cdd1e2445d00a14eec04b4cc33f239655f8619a789e7ae863c43e6", "A9-02 bus power boundary"),
    "EVID": ("docs/EVIDENCE.md", "a2950352141890c12ad33e66766cd003215c807cb29203d21df090349ab90b61",
             "evidence rules (CLAUDE.md rule 10)"),
}
NEVER_PINNED = ["docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                "docs/orchestration/fired_triggers.jsonl", "docs/orchestration/trigger_ledger_v2.jsonl",
                "docs/orchestration/runtime_state.json"]
PENDING_LANES = [
    {"path": "docs/experiments/hall_icp/p1_icp_bench/", "lane": "P1 ICP electron-source bench (A9.3 authorizations.P1)",
     "needed_for": "the stable ICP operating region (factor levels of the hot map), the selected laboratory generator, the "
                   "adjustable local match hardware and its tuning range, the antenna / module geometry and the "
                   "registered procedure's provisional limits",
     "status": "PENDING (built in parallel; not read, not imported, content never assumed)"},
    {"path": "docs/procurement/rfq_a9_v2/", "lane": "RFQ v2 split by supplier speciality (A9.3 OQ-RFQ-07)",
     "needed_for": "the RF-package line ids to which the P2 instrument list maps",
     "status": "PENDING (built in parallel; not read, not imported, content never assumed)"},
]


# every A9.3 decision id must carry a disposition in owner_answers_applied (checked in build() and by the test)
A93_DECISION_IDS = ("OQ-VI-03", "OQ-VI-05", "OQ-A907-02", "ICPQ-06", "OQ-RFQ-06", "OQ-RFQ-07", "OQ-RFQ-02",
                    "OQ-RFQ-10")
POWERED_STEP_RULE = "HM-R13"


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


def _find(obj, key, val):
    """First dict anywhere in obj with obj[key] == val (raises when absent: a cited id must exist)."""
    stack = [obj]
    while stack:
        o = stack.pop(0)
        if isinstance(o, dict):
            if o.get(key) == val:
                return o
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
    raise SystemExit(f"cited id {key}={val!r} not found in a pinned input")


# ------------------------------------------------------------------------------------------------ helpers
def row(ans, n):
    a = next(x for x in ans["answers"] if x["row"] == n)
    return {"kind": "owner_row", "path": DECISIONS["ANS"][0], "row": n, "covers_ids": a["covers_ids"],
            "answer_sha256": hashlib.sha256(a["owner_answer_verbatim"].encode("utf-8")).hexdigest()}


def dec(key, did):
    doc = _load(key)
    decs = doc["decisions"]
    if did not in decs and did not in doc.get("authorizations", {}) and did not in doc.get("execution_decisions", {}):
        raise SystemExit(f"decision {did} not in {key}")
    return {"kind": {"A91": "A9.1", "A92": "A9.2", "A93": "A9.3", "A94": "A9.4"}[key],
            "path": DECISIONS[key][0], "sha256": DECISIONS[key][1], "decision": did}


def item(iid, name, value, units, basis, source, evidence_class, status, freeze_point, **extra):
    d = {"id": iid, "name": name, "value": value, "units": units, "basis": basis, "source": source,
         "evidence_class": evidence_class, "status": status, "freeze_point": freeze_point}
    d.update(extra)
    return d


def _r(x, n=6):
    return float(f"{x:.{n}g}")


# ------------------------------------------------------------------------------------------------ synthetic self-check
def _c(z):
    return [z.real, z.imag]


def synthetic_cal(z0, line_abcd, match_abcd, e00, e11, e10e01, fixture_abcd, k_v=1 + 0j, k_i=1 + 0j):
    """A SYNTHETIC calibration set (for the closed-form self-check and the tests only; not evidence)."""
    def sp(abcd, a, b):
        s11, s12, s21, s22 = RED.abcd_to_s(abcd, z0)
        return {"from_plane": a, "to_plane": b, "S11": _c(s11), "S12": _c(s12), "S21": _c(s21), "S22": _c(s22),
                "cal_id": "SYN-2P", "phase_calibrated": True}
    return {
        "schema": RED.CAL_SCHEMA_ID, "calibration_set_id": "SYN-CAL-01", "data_class": "synthetic_test",
        "f_Hz": 13.56e6, "Z0_ohm": z0,
        "power_sensors": {"SYN-PS": {"CF_fwd": 1.0, "CF_ref": 1.0, "certificate": "SYNTHETIC - no certificate"}},
        "coupler": {"cal_id": "SYN-CPL", "plane": "RP-CPL", "phase_calibrated": True, "e00": _c(e00),
                    "e11": _c(e11), "e10e01": _c(e10e01)},
        "two_ports": {"line": sp(line_abcd, "RP-CPL", "RP-MIN"),
                      "match_states": {"TS-SYN-1": sp(match_abcd, "RP-MIN", "RP-ANT")}},
        "vi_probe": {"cal_id": "SYN-VI", "phase_calibrated": True, "k_V": _c(k_v), "k_I": _c(k_i),
                     "fixture_abcd": [[_c(fixture_abcd[0]), _c(fixture_abcd[1])],
                                      [_c(fixture_abcd[2]), _c(fixture_abcd[3])]],
                     "fixture_from_plane": "RP-VI", "fixture_to_plane": "RP-ANT", "amplitude_convention": "peak"},
        "loss_bounds": {}, "cold_references": {}, "antenna_current_probe": None,
    }


def synthetic_record(cal, z_ant, p_fwd, phase="DUMMY_LOAD"):
    """Synthesize a SYNTHETIC record whose readings are exactly consistent with z_ant (for round-trip checks)."""
    z0 = cal["Z0_ohm"]
    tp = cal["two_ports"]
    net = RED.cascade(RED.s_to_abcd(*[RED.cx(tp["line"][k], k) for k in ("S11", "S12", "S21", "S22")], z0),
                      RED.s_to_abcd(*[RED.cx(tp["match_states"]["TS-SYN-1"][k], k)
                                      for k in ("S11", "S12", "S21", "S22")], z0))
    g_in = RED.gamma_from_z(RED.z_in(net, z_ant), z0)
    cc = cal["coupler"]
    e00, e11, e10e01 = (RED.cx(cc[k], k) for k in ("e00", "e11", "e10e01"))
    m_raw = e00 + e10e01 * g_in / (1 - e11 * g_in)
    fx = cal["vi_probe"]["fixture_abcd"]
    a, b, c, d = (RED.cx(fx[0][0], "A"), RED.cx(fx[0][1], "B"), RED.cx(fx[1][0], "C"), RED.cx(fx[1][1], "D"))
    i_a = 1.0 + 0j
    v_a = z_ant * i_a
    v_p, i_p = a * v_a + b * i_a, c * v_a + d * i_a
    return {
        "schema": RED.SCHEMA_ID, "record_id": "SYN-REC-01", "data_class": "synthetic_test", "phase": phase,
        "calibration_set_id": cal["calibration_set_id"], "f_Hz": 13.56e6, "Z0_ohm": z0,
        "reference_planes": {"coupler_powers": "RP-CPL", "coupler_reflection": "RP-CPL", "vi_probe": "RP-VI"},
        "methods": ["vi_probe", "deembed"], "loss_method": "two_port",
        "coupler": {"P_sens_fwd_W": p_fwd, "P_sens_ref_W": p_fwd * abs(g_in) ** 2, "power_sensor_cal_id": "SYN-PS",
                    "reflection_raw": _c(m_raw)},
        "vi_probe": {"V_raw": _c(v_p), "I_raw": _c(i_p), "vi_cal_id": "SYN-VI"},
        "match_state": {"tuning_state_id": "TS-SYN-1", "positions": {"C_series": "SYN", "C_shunt": "SYN"},
                        "auto_tune": False, "loss_bound_id": None},
        "factors": {k: None for k in RED.REQUIRED_FACTOR_FIELDS},
        "plasma_state": {"lit": False, "mode": "UNLIT", "optical_signal_V": None, "unlit_threshold_V": None,
                         "unlit_threshold_source": None, "threshold_basis": None,
                         "photodiode_line_of_sight_ok": None, "photodiode_saturated": None,
                         "electrical_ignition_or_mode_transition": None, "electrical_indicator_basis": None},
        "sweep": {"sweep_id": "SYN", "direction": "single", "index": 0},
        "settling": {"dwell_s": None, "settled": None},
        "temperatures_K": {}, "cold_reference_id": None, "p1_stable_region_ref": None, "antenna_current": None,
    }


def lossy_series_shunt(z0, zs, ys):
    """ABCD of a series impedance zs followed by a shunt admittance ys (synthetic network)."""
    return RED.cascade((1 + 0j, zs, 0j, 1 + 0j), (1 + 0j, 0j, ys, 1 + 0j))


def selfcheck(h2a9):
    rev = h2a9["recomputations"]["rf_reference_plane"]["sensitivity_loads"]["review_case_20+j50"]
    z0 = 50.0
    g = RED.gamma_from_z(complex(20, 50), z0)
    out = [{"id": "SC-01", "what": "|Gamma| and VSWR of 20 + j50 ohm on 50 ohm (closed form)",
            "reducer": {"gamma_mag": _r(abs(g)), "VSWR": _r(RED.vswr(abs(g)))},
            "a9_07_review_case": {"gamma_mag": rev["gamma_mag"], "VSWR": rev["VSWR"],
                                  "source": DELIVERABLES["H2A9"][0] + " recomputations.rf_reference_plane."
                                            "sensitivity_loads.review_case_20+j50"},
            "agrees_to_4_significant_digits": _r(abs(g), 4) == _r(rev["gamma_mag"], 4)
            and _r(RED.vswr(abs(g)), 4) == _r(rev["VSWR"], 4)}]
    # SC-02: round trip through a synthetic lossless line + synthetic lossy L-network + synthetic coupler error terms
    th = math.radians(30.0)
    line = (complex(math.cos(th)), 1j * z0 * math.sin(th), 1j * math.sin(th) / z0, complex(math.cos(th)))
    match = lossy_series_shunt(z0, complex(0.5, -80.0), complex(0.0002, 0.012))
    fix = (1 + 0j, complex(0.05, 3.0), 0j, 1 + 0j)
    cal = synthetic_cal(z0, line, match, complex(0.01, -0.02), complex(0.03, 0.01), complex(0.98, 0.05), fix)
    z_ant = complex(2.0, 80.0)
    rec = synthetic_record(cal, z_ant, 100.0)
    red = RED.reduce_record(rec, {cal["calibration_set_id"]: cal})
    net = RED.cascade(line, match)
    s11, s12, s21, s22 = RED.abcd_to_s(net, z0)
    gl = RED.gamma_from_z(z_ant, z0)
    gi = s11 + s12 * s21 * gl / (1 - s22 * gl)
    eta_s = abs(s21) ** 2 * (1 - abs(gl) ** 2) / (abs(1 - s22 * gl) ** 2 * (1 - abs(gi) ** 2))
    out.append({"id": "SC-02", "what": "round trip: synthetic Z_antenna = 2 + j80 ohm through a synthetic 30-degree "
                                       "lossless 50-ohm line, a synthetic lossy series/shunt network and synthetic "
                                       "coupler error terms; recovered by both methods",
                "input_Z_ohm": [2.0, 80.0],
                "recovered_vi_probe": [red["Z_antenna"]["vi_probe"]["R_ohm"], red["Z_antenna"]["vi_probe"]["X_ohm"]],
                "recovered_deembed": [red["Z_antenna"]["deembed"]["R_ohm"], red["Z_antenna"]["deembed"]["X_ohm"]],
                "match_line_efficiency_abcd": _r(red["match_line_efficiency"]),
                "match_line_efficiency_s_formula": _r(eta_s),
                "s_formula_source": DELIVERABLES["H2A9"][0] + " recomputations.rf_reference_plane.relations.load_power"})
    out.append({"id": "SC-03", "what": "P_delivered = P_forward - P_reflected - P_line/match,loss for SC-02",
                "P_forward_W": red["at_RP_CPL"]["P_forward_W"], "P_reflected_W": red["at_RP_CPL"]["P_reflected_W"],
                "P_line_match_loss_W": red["P_line_match_loss_W"], "P_delivered_W": red["P_delivered_W"],
                "closes": abs(red["at_RP_CPL"]["P_forward_W"] - red["at_RP_CPL"]["P_reflected_W"]
                    - red["P_line_match_loss_W"] - red["P_delivered_W"]) < 1e-6})
    for o in out:
        o["evidence_status"] = RED.SYNTHETIC_LABEL
        o["evidence_class"] = "model-derived"
    return out


# ------------------------------------------------------------------------------------------------ content
def build():
    verify_pins()
    ans = _load("ANS")
    a92 = _load("A92")["decisions"]
    a93 = _load("A93")
    ub = _load("UB")
    icd = _load("ICD")
    h2a9 = _load("H2A9")
    rfq = _load("RFQ")
    m16 = _load("M16")
    evi = _load("EVI")
    rfm = _load("RFM")
    vi = _load("VI")
    oq3 = _load("OQ3")
    ins = _load("INS")
    ms = _load("MS")
    bus = _load("BUS")

    # ---- cross-checks of every cited id (raise when absent)
    for i in ("UB-RF-00", "UB-RF-01", "UB-RF-02", "UB-RF-03", "UB-RF-04", "UB-RF-05", "UB-RF-06", "UB-RF-07",
              "UB-RF-08", "UB-RF-09"):
        _find(ub["items"], "id", i)
    for i in ("LA-02", "LA-03"):
        _find(ub["stop_rules"], "id", i)
    for i in ("ICP-11", "ICP-12", "ICP-13", "ICP-14", "ICP-15", "ICP-16", "ICP-17", "ICP-18", "ICP-21", "ICP-34",
              "ICP-36", "ICP-43", "ICP-44"):
        _find(icd["items"], "id", i)
    for i in ("A9H-INS-01", "A9H-INS-02", "A9H-INS-03", "A9H-INS-15", "A9H-INS-16", "A9H-CAL-02", "A9H-CAL-05",
              "A9H-RF-LM-01", "A9H-RF-PROT-01"):
        _find(h2a9["new_items"], "id", i)
    _find(h2a9["interface_demands"], "id", "IDA7-21")
    rfq04 = _find(rfq["packages"], "id", "RFQ-04")
    for i in ("RFQ-04-R07", "RFQ-04-R08", "RFQ-04-R09", "RFQ-04-R10", "RFQ-04-R11", "RFQ-04-R12", "RFQ-04-R16",
              "RFQ-04-R17"):
        _find(rfq04, "id", i)
    for i in ("VI-RF-02", "VI-RF-03", "VI-RF-04", "VI-RF-05", "VI-RF-06", "VI-RF-07", "VI-RF-08", "VI-RF-10",
              "VI-RF-11"):
        _find(vi["items"], "id", i)
    for i in ("INS-03", "INS-18"):
        _find(ins["instruments"], "id", i)
    for i in ("MS-G-01", "MS-G-02", "MS-G-03"):
        _find(ms["general_requirements"], "id", i)
    for i in ("A902-21", "A902-22"):
        _find(bus, "id", i)
    oq_rows = {r["id"]: r for r in oq3["rows"]}
    for i in ("ICPQ-10", "ICPQ-11", "OQ-A910-06"):
        if oq_rows[i]["status"] != "OPEN":
            raise SystemExit(f"{i} is no longer OPEN in the pinned state v3")
    m16_rows = {r["row"]: r for r in m16["rows"]}
    if m16_rows[15]["key"] != "sensors_diagnostics" or m16_rows[18]["key"] != "icp_neutralizer_head" or \
            m16_rows[19]["key"] != "flight_rf_chain" or m16_rows[17]["key"] != "preionizer_interface":
        raise SystemExit("M16 v3 row keys changed")
    a910 = a92["a9_10_statuses"]
    for k, v in (("RF component ratings", "TBD_AFTER_IMPEDANCE_MAP"),
                 ("RF matching architecture", "LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT"),
                 ("coupled H-1/ICP thermal closure", "UNRESOLVED"), ("anode thermal closure", "UNRESOLVED"),
                 ("final anode material", "OPEN"), ("ICP electron-current capacity", "PENDING_ICP45")):
        if a910[k] != v:
            raise SystemExit(f"A9.2 status {k} changed")
    if "P2" not in a93["authorizations"]:
        raise SystemExit("A9.3 P2 authorization missing")

    # ---- analog context (copied from the pinned extraction; never Vyovrinda values)
    tk = []
    for i in ("TK-20", "TK-21", "TK-22", "TK-23", "TK-24", "TK-25", "TK-26"):
        e = _find(evi["extraction"], "id", i)
        tk.append({"id": i, "quantity": e["quantity"], "value": e["value"], "unit": e["unit"], "locator": e["locator"],
                   "epistemic": e["epistemic"], "evidence_class": e["evidence_class"],
                   "source": DELIVERABLES["EVI"][0], "use_here": "method context only (what the analog measured and "
                   "how); never a Vyovrinda impedance, power or rating"})
    rf_prec = []
    use = {"RF-TAKA22-01": "antenna-current / resistance-split method (method C, VI-RF-05..07)",
           "RF-TAKA22-03": "R_vac convention: the no-plasma resistance measured through the net power includes "
                           "feedthrough and matching-box losses (method C note)",
           "RF-VOLK18-01": "phase-resolved V/I sensing near the coil as a precedent for method A",
           "RF-VOLK18-02": "load resistance changes with flow: report mismatch effects separately from plasma physics",
           "RF-IPT20-07": "forward/reflected accounting must separate matching-network and antenna losses",
           "RF-IPT20-06": "cold (no-plasma) antenna S11 measured with a VNA before matching (CAL-P2-08 precedent)",
           "RF-SCHU24-05": "lane inference, not stated by the source (the entry records only reflected power <= 1 % with "
                           "automatic matching): a low reflected power does not by itself separate matchbox / coil "
                           "dissipation, hence HM-R08",
           "RF-DALT08-01": "E-H hysteresis vs applied power vs plasma power corrected for matching losses: plot the "
                           "map against P_forward AND P_delivered (hysteresis rule HM-R05)",
           "RF-IPG6S-06": "operating points lost to reflected-power trips of an unmatched supply: log trips as "
                          "observations, never drop them"}
    for i, u in use.items():
        e = _find(rfm["entries"], "id", i)
        rf_prec.append({"id": i, "citation": e["source"]["citation"], "doi_or_url": e["source"]["doi_or_url"],
                        "access": e["source"]["access"], "quantity": e["quantity"], "locator": e["locator"],
                        "evidence_class": e["evidence_class"], "use_here": u, "source": DELIVERABLES["RFM"][0]})

    r8, r62, r64, r70, r72, r86, r108, r117, r130, r133, r144, r145 = (
        row(ans, n) for n in (8, 62, 64, 70, 72, 86, 108, 117, 130, 133, 144, 145))
    A92_REF = {k: dec("A92", k) for k in ("OQ-A907-11", "rf_measurement_reference", "rf_500W", "rf_protection",
                                             "icp_matching_strategy", "a9_10_statuses", "post_a9_priorities",
                                             "icp_coupled_thermal")}
    A93_REF = {k: dec("A93", k) for k in A93_DECISION_IDS + ("P1", "P2")}
    A94_REF = {k: dec("A94", k) for k in ("P2Q-05", "P1Q-14", "p1_needed_rfqs")}
    a94 = _load("A94")
    if a94["decisions"]["P2Q-05"]["state_classes"] != list(RED.MODE_LABELS):
        raise SystemExit("A9.4 P2Q-05 state classes differ from the reducer's MODE_LABELS")
    A91_REF = {k: dec("A91", k) for k in ("UBQ-03", "UBQ-04", "UBQ-05", "A9-03-matching")}

    # ================================================================ (1) reference planes
    planes = [
        item("RP-GEN", "generator output connector", "RF generator output; generator-internal forward/reflected meters "
             "are not a measurement plane (ICD ICP-14: generator-internal meters alone are not sufficient; the "
             "analog relied on them: TK-22/TK-23 in docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json, "
             "the same fact the ICD cites as its annex row TAK-04)", "-", "definition", [ "ICD ICP-14"], "assumed", "DEFINED", "NOW",
             measured_here=["P_mains,in of the mains-powered laboratory generator (A9.3 OQ-RFQ-06; engineering quantity, "
                            "GROUND/FACILITY_ONLY, never P_bus evidence)"]),
        item("RP-CPL", "directional-coupler plane on the generator / 50-ohm side of the LOCAL matching network",
             a92["rf_measurement_reference"], "-", "owner decision A9.2",
             [A92_REF["OQ-A907-11"], A92_REF["rf_measurement_reference"], "UB-RF-09", "ICD ICP-14"],
             "owner-allocation", "OWNER_GIVEN", "NOW",
             measured_here=["P_forward, P_reflected (primary power measurement, row 72)", "|Gamma|, VSWR",
                            "complex reflection Gamma_in (vector reflectometer / VNA receiver, method B)"]),
        item("RP-MIN", "input connector of the local matching network", "end of the 50-ohm line on the ICP module "
             "(after the flexible stand-crossing coax and the vacuum RF feedthrough); the residual mismatch after the "
             "local match is the |Gamma| seen here, transformed to RP-CPL by the characterized line two-port",
             "-", "definition from the A9.2 chain generator -> coupler -> 50-ohm line -> local match -> antenna",
             [A92_REF["OQ-A907-11"], "H2-A9 recomputations.rf_reference_plane.a9_2_segments.retained_50_ohm_segment"],
             "assumed", "PROPOSED", "LOCK-1", physical_location="TBD - requires the ICP module drawings (ICD ICP-02/04/07) "
             "and " + P1_PENDING),
        item("RP-ANT", "antenna terminals (output side of the local matching network) - plane of Z_antenna = R + jX",
             "the pair of antenna feed terminals at which Z_antenna is reported; it excludes the matching elements and "
             "includes the antenna, its in-vacuum leads up to the terminal pair and, when lit, the plasma loading",
             "-", "A9.2 icp_matching_strategy (Z_antenna = R + jX measured vs mdot, P_RF, p, gas composition, Hall "
             "operating point)", [A92_REF["icp_matching_strategy"],
                                  "H2-A9 recomputations.rf_reference_plane.a9_2_segments.short_match_to_antenna_segment"],
             "assumed", "PROPOSED", "LOCK-1", physical_location="TBD - requires the antenna/terminal drawing (" +
             P1_PENDING + "; ICD ICP-07)"),
        item("RP-VI", "V/I probe sensing plane", "the plane at which the V/I probe senses voltage and current; joined to "
             "RP-ANT by a characterized fixture two-port (the identity only when declared and verified)", "-",
             "method A", ["this package CAL-P2-06"], "assumed", "PROPOSED", "LOCK-1",
             physical_location="TBD - requires the probe selection (INS-P2-01) and the module drawings"),
    ]

    z0_basis = h2a9["recomputations"]["rf_reference_plane"]["Z0_ohm"]
    chain = [
        item("P2-F-01", "RF drive frequency", 13.56, "MHz", "owner answer", [r72, "UB-RF-00", "ICD ICP-11"],
             "owner-allocation", "OWNER_GIVEN", "NOW"),
        item("P2-F-02", "reference (system) impedance Z0 of the 50-ohm segment and of all S-parameters",
             z0_basis["value"], "ohm", z0_basis["basis"], [DELIVERABLES["H2A9"][0] + " recomputations.rf_reference_plane"
                                                           ".Z0_ohm"], "assumed", "PROPOSED", "LOCK-1",
             note="the actual line / coupler impedance is verified by CAL-P2-01/02; the reducer refuses a record whose "
                  "Z0 differs from its calibration set"),
        item("P2-F-03", "laboratory delivered/operating RF investigation capability (not a component rating)",
             [0.0, 500.0], "W", "row 72 as interpreted by A9.2 rf_500W", [r72, A92_REF["rf_500W"], "UB-RF-01"],
             "owner-allocation", "OWNER_GIVEN", "NOW",
             rating="TBD_AFTER_IMPEDANCE_MAP (A9.2 a9_10_statuses 'RF component ratings')"),
    ]

    # ================================================================ (1b) how Z_antenna is obtained
    methods = [
        {"id": "ZM-A", "name": "V/I probe at the antenna terminals (RP-VI -> RP-ANT by fixture de-embedding)",
         "principle": "calibrated complex voltage and current at RP-VI; Z_ant = V_ant / I_ant after the fixture inverse "
                      "ABCD; reducer method 'vi_probe'",
         "pros": ["direct at the reporting plane: independent of the matching network model and of its tuning state",
                  "insensitive to line / feedthrough / match loss and to coupler directivity",
                  "gives antenna-terminal V and I directly (the stresses ICP-44 / ICPQ-11 need)",
                  "precedent: phase-resolved V/I sensing near the coil (RF-VOLK18-01)"],
         "cons": ["for a strongly reactive antenna R = |Z| cos(phi) is dominated by the phase error: "
                  "|dR| ~ |X| u(phi) when R << |X| (standard relation; verify) - phase calibration is the critical term",
                  "probe at RF voltage near the plasma, in vacuum on the module: vacuum/thermal compatibility, pickup, "
                  "and (on the thrust stand) an extra service line and mass",
                  "probe ratings TBD - require the cold antenna impedance and the generator selection"],
         "status": "PROPOSED", "role": "PRIMARY on the P1/P2 bench"},
        {"id": "ZM-B", "name": "de-embedding from the calibrated complex reflection at RP-CPL",
         "principle": "Gamma_in at RP-CPL from the vector-corrected coupler/reflectometer (three-term one-port error "
                      "model); Z_in = Z0 (1 + Gamma_in) / (1 - Gamma_in); Z_ant = (D Z_in - B) / (A - C Z_in) with ABCD "
                      "of line (RP-CPL -> RP-MIN) cascaded with the local match at the logged tuning state "
                      "(RP-MIN -> RP-ANT); reducer method 'deembed'",
         "pros": ["uses the 50-ohm-side chain that is present anyway (A9.2 RP-CPL measurement)",
                  "no hardware at the antenna: usable on the thrust stand without an extra service line",
                  "the same two-port data give P_line/match,loss (the A9-07 load-power relation)"],
         "cons": ["needs the two-port of the match at EVERY tuning state used (grid + declared interpolation rule, "
                  "CAL-P2-04) and phase-calibrated reflection; scalar |Gamma| alone cannot de-embed",
                  "near a good match Gamma_in ~ 0 and Z_ant is set almost entirely by the network model: errors of the "
                  "S-parameters propagate strongly into a sub-ohm-class R (UB-P2-Z-03)",
                  "the network is characterized cold at VNA power; element heating at operating power shifts it "
                  "(UB-P2-Z-05; checked on the antenna-simulator load at power, CAL-P2-10)",
                  "coupler directivity limits the reflection accuracy (UB-RF-04, A9-07 IDA7-21)"],
         "status": "PROPOSED", "role": "CROSS-CHECK at every bench point; candidate primary on the thrust stand only "
                                       "after bench agreement (P2Q-01, P2Q-06)"},
        {"id": "ZM-C", "name": "antenna RF current probe + delivered power (resistance only)",
         "principle": "R_total = P_delivered / I_rms^2 at RP-ANT; with P_net instead of P_delivered the line/match loss "
                      "is lumped into the resistance (R_vac convention, RF-TAKA22-03); resistance split "
                      "R_p = R_hot - R_cold (anchor Eq. (1) method, VI-RF-05..07)",
         "pros": ["simple, robust magnitude-only measurement (Rogowski / current transformer)",
                  "the published analog and RF precedents use it (TK-24/TK-25; RF-TAKA22-01)"],
         "cons": ["gives R only, not X", "needs P_delivered (hence the loss characterization) or accepts lumped loss",
                  "R_cold must be taken at a comparable antenna temperature (UB-P2-Z-07)"],
         "status": "PROPOSED", "role": "INDEPENDENT R CROSS-CHECK and resistance split"},
    ]
    recommendation = {
        "primary": "ZM-A (V/I probe at the antenna terminals) on the P1/P2 bench",
        "cross_check": "ZM-B (de-embedding from the 50-ohm-side complex reflection) at every bench point; ZM-C for R",
        "transfer_rule": "on the thrust stand ZM-B may become the primary method only if, on the bench, its Z_ant agrees "
                         "with ZM-A over the P1 stable region under the agreement rule (form LOCK-1, value LOCK-2; "
                         "P2Q-03); otherwise the stand needs the V/I probe with matched sham routing (rows 117, 133)",
        "status": "PROPOSED", "freeze_point": "LOCK-1", "owner_question": "P2Q-01",
        "sensitivity_relations": {
            "phase": "R = |Z| cos(phi), X = |Z| sin(phi); dR = -|Z| sin(phi) dphi = -X dphi (first order)",
            "evidence_class": "model-derived (standard relation; verify)",
            "analog_context": "the published analog reports antenna resistances of order 0.4 ohm without / with plasma "
                              "(TK-24, TK-25; published analog, never Vyovrinda values): IF a Vyovrinda antenna is of "
                              "that class, the plasma-induced R change is small against |X|, which is why phase "
                              "calibration, not magnitude, sets the uncertainty of R - the required u(phi) is "
                              "TBD - requires the cold antenna impedance (CAL-P2-08) and the u(R) target (LOCK-2)"},
    }

    # ================================================================ (2) calibration plan + uncertainty links
    def cal(iid, name, planes_, standards, when, ub_ids, ms_ids, closes, value, freeze, note=""):
        return item(iid, name, value, "-", "calibration step", ["this package"] + ub_ids, None if value.startswith(
            "TBD") else "assumed", "TBD" if value.startswith("TBD") else "PROPOSED", freeze, planes=planes_,
            standards=standards, when=when, uncertainty_links=ub_ids, metrology_links=ms_ids, closes=closes, note=note)
    calplan = [
        cal("CAL-P2-01", "VNA calibration (one-port SOL at each measurement plane; two-port SOLT for two-port "
            "characterization) at 13.56 MHz and over the cold-antenna sweep span",
            ["RP-CPL", "RP-MIN", "RP-ANT"], ["coaxial SOL/SOLT kit with data-based standard definitions (INS-P2-05)",
                                            "antenna-terminal fixture standards (short / open / known load) for RP-ANT"],
            "S-01, before every two-port or cold-antenna set; verified by a check standard", ["UB-P2-Z-08"],
            ["MS-G-01", "MS-G-02", "MS-G-03", "MS-P2-02"], ["UB-P2-Z-08"],
            "TBD - requires the VNA and kit certificates (residual directivity / source match / tracking)", "LOCK-2"),
        cal("CAL-P2-02", "two-port S-parameters of the 50-ohm line segment RP-CPL -> RP-MIN (coupler output cable, "
            "flexible stand-crossing coax, vacuum feedthrough)", ["RP-CPL", "RP-MIN"],
            ["CAL-P2-01 two-port calibration"], "S-02; repeated after any re-routing and pre/post each block "
            "(phase with stand motion: CAL-P2-12)", ["UB-RF-05", "UB-P2-Z-03"], ["MS-P2-02"], ["UB-RF-05 (line part)"],
            "TBD - requires the installed line (" + P1_PENDING + ")", "LOCK-2",
            note="the live and sham coax pair is characterized as a pair (rows 117, 133)"),
        cal("CAL-P2-03", "two-port S-parameters of the adjustable local match RP-MIN -> RP-ANT at each tuning state of "
            "a declared grid over its tuning range (or a fitted equivalent-circuit model of the measured data, "
            "evidence class 'reconstructed')", ["RP-MIN", "RP-ANT"], ["CAL-P2-01 two-port calibration",
                                                                     "antenna-terminal fixture adapter"],
            "S-03; grid spacing TBD from the P1 tuning range", ["UB-RF-05", "UB-P2-Z-03", "UB-P2-Z-04"], ["MS-P2-02"],
            ["UB-RF-05 (match part)", "A9H-INS-03"], "TBD - requires the selected matching network and its tuning range "
            "(" + P1_PENDING + "; RFQ-04-R07)", "LOCK-2"),
        cal("CAL-P2-04", "tuning-state interpolation rule and its verification at off-grid states",
            ["RP-MIN", "RP-ANT"], ["CAL-P2-03 grid", "verification states not used to build the rule"],
            "S-03", ["UB-P2-Z-04"], ["MS-P2-02"], ["UB-P2-Z-04"],
            "TBD - requires CAL-P2-03 data; the reducer refuses an uncharacterized tuning state (no silent "
            "interpolation)", "LOCK-2"),
        cal("CAL-P2-05", "V/I probe calibration: complex gains k_V, k_I (magnitude AND relative phase) at 13.56 MHz",
            ["RP-VI"], ["short (current only)", "open (voltage only)", "precision 50-ohm termination",
                        "reactive standard of VNA-measured impedance (phase check near +/-90 degrees)",
                        "all at low level (VNA / signal source), never at generator power; the at-power verification "
                        "is CAL-P2-15"],
            "S-04 (unpowered); pre/post each block", ["UB-P2-Z-01", "UB-P2-Z-02"], ["MS-P2-03"], ["UB-P2-Z-01", "UB-P2-Z-02"],
            "TBD - requires the probe selection (INS-P2-01) and the calibration data", "LOCK-2"),
        cal("CAL-P2-06", "V/I probe fixture (RP-VI -> RP-ANT) ABCD, or a verified declaration that RP-VI = RP-ANT",
            ["RP-VI", "RP-ANT"], ["CAL-P2-01 at the antenna terminals", "known loads at RP-ANT"], "S-04",
            ["UB-P2-Z-06"], ["MS-P2-03"], ["UB-P2-Z-06"], "TBD - requires the module drawings and the probe mount",
            "LOCK-2"),
        cal("CAL-P2-07", "directional coupler + forward/reflected sensors: coupling factors (incl. cable), directivity "
            "and sensor calibration factor / linearity at 13.56 MHz; in-situ checks into a matched load (directivity "
            "floor) and into short/open (full reflection) at LOW LEVEL ONLY (VNA / low-level signal source through the "
            "coupler; never generator power into a short or open: total reflection and an unbounded open-circuit "
            "voltage); then the calorimetric cross-check at power into the matched 50-ohm calorimetric load only, "
            "with k_x = 2, under HM-R13",
            ["RP-CPL"], ["traceable certificates (A9H-CAL-02; A4 force_DC_RF_traceability)",
                         "50-ohm calorimetric dummy load (RFQ-04-R10)"],
            "S-00 (certificates), S-05 (in situ: low level first, then at power into the 50-ohm load)", ["UB-RF-02", "UB-RF-03", "UB-RF-04", "UB-RF-08"],
            ["MS-G-01", "MS-G-02", "MS-G-03", "MS-P2-01"], ["UB-RF-02", "UB-RF-03", "UB-RF-04", "UB-RF-08 (check)"],
            "TBD - requires coupler and sensor certificates; D_min at LOCK-2 (UB-RF-04, A9H-INS-16)", "LOCK-2",
            note="bare +/-a bounds enter as a/sqrt(3) unless the certificate states otherwise (A9.1 UBQ-03)"),
        cal("CAL-P2-08", "cold antenna impedance vs frequency around 13.56 MHz (installed on the module; no plasma: gas "
            "off, and gas on unlit), VNA at RP-ANT and via RP-MIN (unpowered: VNA excitation only)", ["RP-ANT", "RP-MIN"],
            ["CAL-P2-01"],
            "S-06 (before the antenna simulator is specified, CAL-P2-10); repeated at more than one antenna "
            "temperature for the R_cold reference; powered-unlit records follow at S-08 (gas off, base pressure; HM-R13 and "
            "the P1 registered procedure; unlit verified by INS-P2-10)",
            ["UB-P2-Z-07"], ["MS-P2-02"], ["VI-RF-06 (cold part)", "sizing input of INS-P2-01 ranges"],
            "TBD - requires the antenna (" + P1_PENDING + "); sweep span TBD - requires the antenna design "
            "(self-resonance must be located, not assumed)", "LOCK-2"),
        cal("CAL-P2-09", "dummy-load checks of the complete chain at power: 50-ohm calorimetric load (P_net vs "
            "calorimetry, k_x = 2) and the harmonic spectrum into the matched load", ["RP-CPL", "RP-MIN"],
            ["50-ohm calorimetric dummy load", "spectrum measurement (INS-P2-04 receiver mode or analyser)"],
            "S-05 (powered, HM-R13)",
            ["UB-RF-06", "UB-RF-07", "UB-RF-08"], ["MS-P2-01"], ["UB-RF-06", "UB-RF-07 (bench part)"],
            "TBD - requires the generator (" + P1_PENDING + ")", "LOCK-2"),
        cal("CAL-P2-10", "end-to-end method validation on an antenna-simulator load of VNA-known Z (low-R, high-X "
            "network in place of the antenna, built to the S-06 cold impedance): Z by ZM-A, ZM-B and ZM-C vs the VNA value, "
            "first at VNA level, then at power with the local match pre-tuned on the VNA into the simulator (HM-R13)",
            ["RP-ANT", "RP-VI", "RP-CPL"], ["antenna-simulator load (INS-P2-07b)", "CAL-P2-01..09"],
            "S-07 (after S-06 cold impedance and S-05 at-power chain check)",
            ["UB-P2-Z-01", "UB-P2-Z-02", "UB-P2-Z-03", "UB-P2-Z-05"], ["MS-P2-02", "MS-P2-03"],
            ["method agreement evidence for the P2Q-01 transfer rule"],
            "TBD - requires the simulator design (from CAL-P2-08 cold impedance) and data", "LOCK-2"),
        cal("CAL-P2-11", "phase drift and temperature: reference-load re-measurement before / during / after each block;"
            " temperatures of probe, match elements and cables logged; pre/post shift in the budget and as a block "
            "exclusion rule", ["RP-VI", "RP-CPL", "RP-ANT"], ["reference load of CAL-P2-05/10"],
            "every block (S-11)", ["UB-P2-Z-05"], ["MS-P2-03"], ["UB-P2-Z-05", "A9H-CAL-05 (P2 part)"],
            "TBD - requires metrology-only drift evidence; rule form LOCK-1, number LOCK-2 (A9.1 UBQ-05; A9H-CAL-05)", "LOCK-2"),
        cal("CAL-P2-12", "phase-stable cable characterization: phase of the VNA test cables and of the flexible "
            "stand-crossing coax vs flexure / stand position and temperature", ["RP-CPL", "RP-MIN"],
            ["CAL-P2-01"], "S-01, S-02", ["UB-P2-Z-05", "UB-P2-Z-03"], ["MS-P2-02"], ["UB-P2-Z-05 (cable part)"],
            "TBD - requires the cables (INS-P2-08) and the stand routing (ICP-18)", "LOCK-2"),
        cal("CAL-P2-13", "RF pickup on the V/I, current-probe and optical channels (generator into dummy load; ICP "
            "energized, H-1 off) - part of the ICP-17 / row-64 pickup check", ["RP-VI"], ["dummy load; ICP on/H-1 off"],
            "S-09 (powered, HM-R13; ICP energized only under the P1 registered procedure, " + P1_PENDING + ")",
            ["UB-P2-Z-01", "UB-P2-Z-02"], ["MS-P2-03"], ["ICP-17 (P2 channels)", "VI-RF-11"],
            "TBD - requires the S1a pickup test (ICD ICP-17)", "LOCK-2"),
        cal("CAL-P2-14", "time-base alignment of RF, V/I, optical, Hall, collector, pressure and flow channels (INS-18)",
            ["-"], ["common trigger"], "S-01", ["UB-P2-Z-05"], ["-"], ["INS-18 (P2 channels)"],
            "TBD - requires the skew allowance from the P1 stability band", "LOCK-2"),
        cal("CAL-P2-15", "V/I probe at-power verification (magnitude and phase) against the known power of the "
            "50-ohm calorimetric load (established by CAL-P2-07/09) and against the VNA-known antenna-simulator "
            "impedance (CAL-P2-10)", ["RP-VI"], ["50-ohm calorimetric dummy load (INS-P2-07a)",
                                                 "antenna-simulator load (INS-P2-07b)"],
            "S-07 (powered, HM-R13; after S-05 established the known power)", ["UB-P2-Z-01", "UB-P2-Z-02"],
            ["MS-P2-03"], ["UB-P2-Z-01 (at-power part)", "UB-P2-Z-02 (at-power part)"],
            "TBD - requires CAL-P2-05 low-level data, the S-05 calorimetric power and the simulator", "LOCK-2"),
    ]
    ub_new = [
        item("UB-P2-Z-01", "V/I probe magnitude calibration (k_V, k_I) at 13.56 MHz", "TBD - requires CAL-P2-05 data",
             "relative", "calibration", ["REF-GUM2008 4.3.3 (via A9-04 references)"], None, "TBD", "LOCK-2",
             proposed_addition_to="A9-04 UB-DQ-RF chain (interface demand IDP2-06)"),
        item("UB-P2-Z-02", "V/I probe relative phase calibration", "TBD - requires CAL-P2-05 data; u(phi) target "
             "from u(R) target / |X| (LOCK-2)", "rad", "calibration", ["REF-GUM2008 4.3.3"], None, "TBD", "LOCK-2",
             proposed_addition_to="A9-04 UB-DQ-RF chain"),
        item("UB-P2-Z-03", "de-embedding: propagated S-parameter uncertainty of line + match into Z_ant",
             "TBD - requires CAL-P2-02/03 uncertainties; propagation by the law of propagation applied to the real and "
             "imaginary parts through the reducer (numerical Jacobian; REF-GUM2008 5.1.2 / 5.2.2 as read by A9-04)",
             "ohm", "calibration + propagation", ["REF-GUM2008 5.1.2, 5.2.2"], None, "TBD", "LOCK-2",
             proposed_addition_to="A9-04 UB-DQ-RF chain"),
        item("UB-P2-Z-04", "tuning-state interpolation error", "TBD - requires CAL-P2-04 verification states", "ohm",
             "calibration", ["this package CAL-P2-04"], None, "TBD", "LOCK-2", proposed_addition_to="A9-04 UB-DQ-RF"),
        item("UB-P2-Z-05", "phase drift / temperature / cable flexure between calibration and reading",
             "TBD - requires CAL-P2-11/12 data", "rad", "calibration", ["this package CAL-P2-11/12"], None, "TBD",
             "LOCK-2", proposed_addition_to="A9-04 UB-DQ-RF"),
        item("UB-P2-Z-06", "V/I fixture correction RP-VI -> RP-ANT", "TBD - requires CAL-P2-06", "ohm", "calibration",
             ["this package CAL-P2-06"], None, "TBD", "LOCK-2", proposed_addition_to="A9-04 UB-DQ-RF"),
        item("UB-P2-Z-07", "cold-reference resistance change with antenna temperature (resistance split)",
             "TBD - requires CAL-P2-08 at more than one antenna temperature", "ohm", "calibration",
             ["this package CAL-P2-08"], None, "TBD", "LOCK-2", proposed_addition_to="A9-04 UB-DQ-RF"),
        item("UB-P2-Z-08", "VNA calibration residuals (directivity, source match, tracking) at each plane",
             "TBD - requires VNA / kit certificates and check-standard data", "-", "certificate",
             ["REF-GUM2008 4.3.3"], None, "TBD", "LOCK-2", proposed_addition_to="A9-04 UB-DQ-RF"),
        item("UB-P2-M-01", "Ar flow factor-level uncertainty (hot-map mdot factor, Ar stage)",
             "TBD - requires the Ar MFC calibration by the rate-of-rise / transfer path (A9.3 OQ-RFQ-02; one or two "
             "overlapping Ar ranges); engineering-only, non-scoring", "relative", "calibration",
             [A93_REF["OQ-RFQ-02"]], None, "TBD", "LOCK-2",
             proposed_addition_to="P1 gas metrology (interface demand IDP2-14); not a scoring component"),
    ]
    ms_new = [
        item("MS-P2-01", "RF power at 13.56 MHz (sensors + coupler incl. cable) - calibration-lab scope requirement",
             "ISO/IEC 17025 (NABL in India) scope covering 13.56 MHz and the power range of the selected sensors; GUM "
             "budget with k; raw data (general requirements MS-G-01..03 extended, as A9-04 IF-16 requests)",
             "-", "A4 force_DC_RF_traceability; A9-04 IF-16", ["A4 force_DC_RF_traceability", "MS-G-01", "MS-G-02",
                                                              "MS-G-03"], "owner-allocation", "PROPOSED", "LOCK-1"),
        item("MS-P2-02", "VNA and coaxial calibration-kit verification (standard definitions, check standard)",
             "traceable kit data and a verification standard; same MS-G requirements", "-", "A4; A9-04 IF-16",
             ["MS-G-01", "MS-G-02", "MS-G-03"], "owner-allocation", "PROPOSED", "LOCK-1"),
        item("MS-P2-03", "V/I probe magnitude and phase calibration at 13.56 MHz",
             "calibration against known loads (CAL-P2-05) with a stated uncertainty budget; accredited scope where one "
             "exists, otherwise an in-house procedure traceable through the VNA (MS-P2-02) - owner call P2Q-07",
             "-", "A4 force_DC_RF_traceability (no invented class where the standard defines none)",
             ["A4 force_DC_RF_traceability"], "owner-allocation", "PROPOSED", "LOCK-1"),
        item("MS-P2-04", "antenna RF current probe (magnitude) at 13.56 MHz", "calibration against the V/I probe or a "
             "known current in a reference load; stated uncertainty", "-", "A4", ["A4 force_DC_RF_traceability"],
             "owner-allocation", "PROPOSED", "LOCK-1"),
    ]

    # ================================================================ (3) hot-map methodology
    factors = [
        item("HM-F01", "RF power (setpoint; recorded as P_forward, P_reflected, P_delivered)",
             "levels TBD - " + P1_PENDING + " (stable region); bounded by the 0-500 W delivered/operating investigation "
             "capability (row 72 as interpreted by A9.2 rf_500W; not a component rating) and the P1 registered limits",
             "W", "row 72; A9.2 rf_500W", [r72, A92_REF["rf_500W"]], "owner-allocation", "PENDING", "after-evidence",
             owner_bound=[0.0, 500.0], owner_bound_evidence_class="owner-allocation"),
        item("HM-F02", "mass flow through the ICP (G-REUSE: Hall anode flow; dedicated ICP flow)",
             "Hall anode flow levels TBD - " + P1_PENDING + "; dedicated ICP flow = 0 in the primary mode (G-REUSE); a "
             "dedicated feed is a diagnostic variable only (quote option, never silently the baseline; booked in the "
             "corresponding ledger if activated). Ar stage (A9.3 OQ-RFQ-02): calibrated Ar flow over the neighbourhood of the "
             "Takahashi anchor (70 sccm ~ 2.1 mg/s, owner-stated in A9.3 OQ-RFQ-02; its attribution to the Takahashi "
             "experiment is to be confirmed by the P1 lane per the A9.3 recorder note - verify) and above/below it; one Ar MFC range "
             "if it covers the sweep, two overlapping ranges only if one cannot (the row-123 four-range rule is not "
             "applied to Ar; atmospheric score-bearing paths keep four overlapping ranges); the Ar controller is "
             "verified by the rate-of-rise / transfer calibration path (IDP2-14, UB-P2-M-01); Ar records carry the "
             "evidence tag ENGINEERING_ONLY_NON_SCORING whatever the metrology quality. A dedicated G-ATM / G-XE "
             "diagnostic line that bridges isolated potentials needs the ~1 kV-class representative-gas isolator "
             "qualification before use (A9.3 ICPQ-06; IDP2-15)", "mg/s",
             "A9.3 OQ-RFQ-10, OQ-RFQ-02, ICPQ-06; A9.1 HIQ-06",
             [A93_REF["OQ-RFQ-10"], A93_REF["OQ-RFQ-02"], A93_REF["ICPQ-06"]], "owner-allocation", "PENDING",
             "after-evidence", owner_value_dedicated=0.0, owner_value_ar_anchor="70 sccm ~ 2.1 mg/s (owner-stated, "
             "A9.3 OQ-RFQ-02; neighbourhood centre, not a level)"),
        item("HM-F03", "pressure (ICP source volume via the ICP-34 port; chamber background)",
             "levels TBD - " + P1_PENDING, "Pa", "ICD ICP-34", ["ICD ICP-34"], None, "PENDING", "after-evidence"),
        item("HM-F04", "gas composition", "evidence order Ar (engineering-only) -> N2 -> O2-bearing (NO_ATOMIC_O); "
             "levels inside each stage TBD - " + P1_PENDING, "-", "A9 evidence order", ["A9"], "owner-allocation",
             "PENDING", "after-evidence", note="Ar data stay ENGINEERING_ONLY_NON_SCORING (A9.3 OQ-RFQ-02); the reducer "
             "derives an evidence_tag from factors.gas and the mismatch envelope never mixes tags"),
        item("HM-F05", "plasma state / mode (UNLIT, E_MODE, H_MODE, UNCERTAIN)", "observed response, not a set factor; "
             "classified per record by rule HM-R14 (A9.4 P2Q-05: the photodiode INS-P2-10 is the required independent "
             "optical indicator, RF / electrical signals corroborate; optical UNLIT with electrical evidence of "
             "ignition / mode transition -> UNCERTAIN) with the E/H indicators of HM-R06", "-",
             "A9.4 P2Q-05; VI-RF-10", [A94_REF["P2Q-05"], "VI-RF-10", "RF-DALT08-01"], "owner-stated", "OWNER_GIVEN",
             "NOW"),
        item("HM-F06", "Hall operating point (off / on; V_d, I_d, coil currents)",
             "levels TBD - inside the registered H-1 operating envelope (" + P1_PENDING + "); current-sensor range uses "
             "the 8.33 A stand ceiling, which is a rating ceiling and not a level (A9.3 OQ-A907-02). The map must reach "
             "the Hall operating point that sets the ICP-45 requirement: I_e,required = I_d,max,H1 "
             "(ICP45_REQUIRED_CURRENT = H1_REGISTERED_MAX, A9.3 OQ-A907-02), i.e. the maximum H-1 discharge current "
             "of the registered envelope, PENDING H-1 registration (IDP2-10)", "V; A",
             "A9.3 OQ-A907-02; A9.2 icp_matching_strategy", [A93_REF["OQ-A907-02"], A92_REF["icp_matching_strategy"]],
             None, "PENDING", "after-evidence"),
        item("HM-F07", "collector bias (V_collector, I_collector)", "levels TBD - requires the collector / bias V-I "
             "range (ICD ICP-21) and " + P1_PENDING + "; a bias level that puts a potential difference across an ICP "
             "gas line (or the floating ICP body against grounded plumbing) is applied only after that line's ~1 kV-"
             "class representative-gas isolator qualification (A9.3 ICPQ-06, ICD ICP-23; IDP2-15); ICP body / "
             "collector circuits stay inside the 350 V operating class with >= 525 V design withstand and the initial "
             "1.05 kV DC / 60 s DWV done before first HV/RF operation (A9.4 P1Q-14)", "V; A",
             "row 70; ICD ICP-21; A9.3 ICPQ-06; A9.4 P1Q-14",
             [r70, "ICD ICP-21", A93_REF["ICPQ-06"], "ICD ICP-23", A94_REF["P1Q-14"]], None,
             "PENDING", "after-evidence"),
        item("HM-F08", "local-match tuning state (logged state variable)", "policy: re-tuned for minimum reflected "
             "power at every point, plus fixed-tune sub-sweeps around representative points (P2Q-04); positions logged "
             "per record and linked to a characterized tuning state (CAL-P2-03/04)", "-",
             "A9.2 icp_matching_strategy (flight implementation only after Z_antenna is measured)",
             [A92_REF["icp_matching_strategy"]], "assumed", "PROPOSED", "LOCK-1"),
        item("HM-F09", "thermal state (antenna, dielectric, collector, match, cables)", "covariate logged per record; no "
             "level", "K", "ICD ICP-34", ["ICD ICP-34"], "assumed", "PROPOSED", "LOCK-1"),
    ]
    rules = [
        item("HM-R01", "map only inside the P1 stable region", "no HOT_MAP record without a P1 stable-region reference "
             "(the reducer raises SequenceError)", "-", "A9.3 authorizations.P2", [A93_REF["P2"]], "owner-allocation",
             "OWNER_GIVEN", "NOW"),
        item("HM-R02", "dwell and settling criterion", "form: a point is recorded when rolling-window statistics of "
             "P_forward, P_reflected, Z_ant, antenna current, pressure and temperatures lie inside declared bands; the "
             "time to settle is logged; unsettled points are kept and flagged, never deleted. Window length and bands "
             "TBD - require P1 stability data (UB-RF-07)", "s", "rule", ["UB-RF-07"], None, "TBD", "LOCK-2",
             form_freeze_point="LOCK-1"),
        item("HM-R03", "repeats and drift bracketing", "N_repeat TBD - requires UB-RF-07 repeatability (LOCK-2); a "
             "reference point is repeated at the start, middle and end of every block", "-", "rule", ["UB-RF-07"],
             None, "TBD", "LOCK-2", form_freeze_point="LOCK-1"),
        item("HM-R04", "sweep order", "one-factor monotonic up-then-down sweeps at fixed other factors, plus a randomized"
             " replicate subset for drift detection; sweep id, direction and index logged per record", "-", "rule",
             ["this package"], "assumed", "PROPOSED", "LOCK-1"),
        item("HM-R05", "hysteresis", "every 1-D sweep is run up and down; the map and any hysteresis are reported "
             "against P_forward AND P_delivered (RF-DALT08-01: hysteresis vs applied power may vanish vs plasma power "
             "corrected for matching losses); up/down agreement rule: form LOCK-1, value LOCK-2 (P2Q-03)", "-",
             "rule", ["RF-DALT08-01"], "assumed", "PROPOSED", "LOCK-1"),
        item("HM-R06", "mode-jump (E/H) detection", "indicators per record: step in R_ant and X_ant, step in |Gamma| at "
             "fixed tuning, antenna current step, optical emission step (INS-P2-10, the required independent optical "
             "indicator, A9.4 P2Q-05); a jump is declared when "
             "adjacent-point changes exceed the declared multiple of the combined uncertainty (form LOCK-1, value "
             "LOCK-2); step size is refined around a detected jump (refinement rule LOCK-1)", "-", "rule",
             ["VI-RF-10", "RF-DALT08-01", "RF-SCHU24-05"], "assumed", "PROPOSED", "LOCK-1"),
        item("HM-R07", "matching-state logging", "per record: tuning-state id, element positions/encoder counts, "
             "auto-tune on/off, tune time, loss-bound id if used", "-", "A9.2 icp_matching_strategy",
             [A92_REF["icp_matching_strategy"]], "owner-allocation", "PROPOSED", "LOCK-1"),
        item("HM-R08", "P_line/match,loss", "measured from the two-port characterization at the logged tuning state "
             "(transfer efficiency from ABCD, identical to the A9-07 S-parameter load-power relation); coax/feedthrough"
             " loss from CAL-P2-02; bounded by a declared loss fraction when a two-port is missing; cross-checked by "
             "match/cable temperature rise and calorimetry; P_delivered is 'TBD' when neither exists (never P_net)",
             "W", "A9.2 rf_measurement_reference", [A92_REF["rf_measurement_reference"], "UB-RF-05", "A9H-INS-03"],
             "owner-allocation", "PROPOSED", "LOCK-1"),
        item("HM-R09", "never P_forward = P_plasma", "the reducer refuses any plasma-power input or label; the "
             "resistance split gives only a reconstructed diagnostic (P_delivered_x_Rsplit_fraction_W, UB-P2-Z-07) "
             "that is never P_plasma evidence for any gate", "-",
             "A9.2 rf_measurement_reference", [A92_REF["rf_measurement_reference"]], "owner-allocation",
             "OWNER_GIVEN", "NOW"),
        item("HM-R10", "generator input power", "P_mains,in of the mains-powered laboratory generator is logged as an "
             "engineering quantity labelled GROUND/FACILITY_ONLY; never P_bus evidence; the flight question needs a "
             "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE", "W", "A9.3 OQ-RFQ-06", [A93_REF["OQ-RFQ-06"]], "owner-allocation",
             "OWNER_GIVEN", "NOW"),
        item("HM-R11", "protection during the map (S-11; the powered preparation steps follow HM-R13)", "only the provisional limits of the P1 registered procedure apply "
             "(" + P1_PENDING + "); reflected-power / VSWR trip thresholds are an OUTPUT of this characterization "
             "(A9.2 rf_protection), never invented here; a trip is logged as an observation (RF-IPG6S-06)", "-",
             "A9.2 rf_protection", [A92_REF["rf_protection"], "A9H-RF-PROT-01"], "owner-allocation", "OWNER_GIVEN",
             "NOW"),
        item("HM-R12", "analysis frozen before data", "reducer version, calibration-set ids and the rules above are "
             "frozen (sha256) before the first HOT_MAP record; no re-analysis choice after seeing data", "-",
             "CLAUDE.md rule 10 (no tuning to force agreement)", ["docs/EVIDENCE.md"], "assumed", "PROPOSED", "LOCK-1"),
        item("HM-R13", "RF-on prerequisites for every powered step (S-05, S-07, S-08, S-09, S-11)",
             "(i) before any RF power into a non-50-ohm load (antenna simulator, cold antenna, ICP) the local match is "
             "pre-tuned at low level with the VNA into that load and the tuning state logged (CAL-P2-03), so the "
             "generator never drives an unmatched reactive load; generator power into a short or open is never "
             "applied (CAL-P2-07 short/open checks are low level only); (ii) whenever RF is on, the calibrated "
             "coupler chain (CAL-P2-07) monitors P_forward / P_reflected, the provisional reflected-power / VSWR "
             "limits and generator foldback of the P1 registered procedure (" + P1_PENDING + ") are active, and the "
             "ICD ICP-16 RF interlock permissives are in force with the functional interlock test done before first "
             "RF-on and at every configuration change (ICP-16 verification); no limit value is set here (A9.2 "
             "rf_protection: thresholds after characterization); (iii) RF enclosure / shielding, personnel RF-exposure"
             " control and antenna-terminal high-voltage clearance per the facility RF-safety procedure and the ICD "
             "ICP-44 antenna-circuit rating - values TBD, requiring that procedure and the ICP-44 rating; a powered "
             "step whose (i)-(iii) are not satisfied is not started", "-",
             "ICD ICP-16, ICP-44; A9.2 rf_protection; A9.3 authorizations.P1 ('subject to existing safety/interlock/"
             "metrology requirements')", ["ICD ICP-16", "ICD ICP-44", A92_REF["rf_protection"], A93_REF["P1"]],
             "assumed", "PROPOSED", "LOCK-1"),
        item("HM-R14", "plasma-state classification with the photodiode (A9.4 P2Q-05)", "classes exactly UNLIT / "
             "E_MODE / H_MODE / UNCERTAIN (reducer classify_plasma_state). The photodiode (INS-P2-10) is the required "
             "independent ignition / unlit and E/H-transition indicator; record simultaneously photodiode intensity, "
             "reflected RF power, antenna current, collector / current-path response and pressure. A "
             "COLD_ANTENNA_POWERED_UNLIT record is valid only when the optical channel demonstrates that the plasma did "
             "not ignite; optical UNLIT with electrical evidence of an ignition / mode transition -> UNCERTAIN (never "
             "forced to UNLIT); a lost line of sight or a saturated photodiode is not automatically valid (refused as "
             "UNLIT evidence); UNCERTAIN records never serve as cold references or map points without "
             "re-classification", "-", "owner decision A9.4 P2Q-05", [A94_REF["P2Q-05"]], "owner-stated",
             "OWNER_GIVEN", "NOW"),
        item("HM-R15", "photodiode unlit threshold", "TBD - requires the dark / background, RF-powered known-unlit and "
             "known-lit P1 plasma photodiode records (" + P1_PENDING + "); frozen before the P2 map; no arbitrary "
             "photodiode voltage threshold is assigned now (A9.4 P2Q-05); each record carries the value, its source and "
             "threshold_basis (the three record ids, frozen_before_p2_map = true)", "V",
             "owner decision A9.4 P2Q-05 (rule)", [A94_REF["P2Q-05"]], None, "TBD", "after-evidence"),
    ]
    R13 = POWERED_STEP_RULE
    sequence = [
        {"step": "S-00", "powered": False, "what": "instrument receipt; certificates checked (CAL-P2-07 certificates)",
         "gate": "H3 procurement gate (row 8: quotations only now)"},
        {"step": "S-01", "powered": False, "what": "VNA calibration, cable phase characterization, time base "
                                                   "(CAL-P2-01, -12, -14)"},
        {"step": "S-02", "powered": False, "what": "line + feedthrough two-port (CAL-P2-02)"},
        {"step": "S-03", "powered": False, "what": "local-match two-port over the tuning grid + interpolation "
                                                   "verification (CAL-P2-03/04)"},
        {"step": "S-04", "powered": False, "what": "V/I probe and fixture calibration on known loads at low level "
                                                   "(VNA / signal source) (CAL-P2-05/06)"},
        {"step": "S-05", "powered": True, "prerequisites": [R13], "what": "coupler / sensors in situ: matched, short and "
         "open checks at LOW LEVEL only; then at power into the matched 50-ohm calorimetric load only: calorimetric "
         "cross-check (establishes the known power) + harmonics (CAL-P2-07/09)"},
        {"step": "S-06", "powered": False, "what": "cold antenna impedance vs frequency by VNA only, gas off and gas on "
         "unlit (CAL-P2-08); its result specifies the antenna-simulator load (INS-P2-07b)"},
        {"step": "S-07", "powered": True, "prerequisites": [R13], "what": "antenna simulator built to the S-06 cold "
         "impedance and VNA-measured; end-to-end validation of ZM-A/B/C first at VNA level, then at power with the "
         "local match pre-tuned on the VNA (CAL-P2-10); V/I probe at-power verification on the calorimetric load "
         "and the simulator (CAL-P2-15)"},
        {"step": "S-08", "powered": True, "prerequisites": [R13, "P1 registered procedure (" + P1_PENDING + ")",
                                                            "HM-R15 photodiode threshold frozen (A9.4 P2Q-05)"],
         "what": "powered-unlit records into the installed antenna, local match pre-tuned on the VNA into the cold "
         "antenna (phase COLD_ANTENNA_POWERED_UNLIT; CAL-P2-08 follow-on), energized only under the P1 registered "
         "procedure. Vacuum/gas state: gas off at chamber base pressure (factors.gas null, both mdot = 0, p_chamber "
         "logged; 'gas on unlit' stays a VNA-only, unpowered CAL-P2-08 condition). RF power level: TBD - requires the "
         "P1 registered procedure (no ceiling is set here). Unlit verification per record: INS-P2-10 optical signal "
         "below the unlit threshold of the P1 procedure (value, source and threshold basis carried in the record), "
         "line of sight kept, no saturation, and no electrical evidence of ignition / mode transition in the "
         "simultaneous reflected-power, antenna-current, collector / current-path and pressure records; otherwise "
         "the record is UNCERTAIN and never a cold reference (A9.4 P2Q-05, HM-R14). Ignition or "
         "breakdown (e.g. at the antenna terminals or feedthrough in residual gas): RF off (abort), record flagged, "
         "never reduced and never a cold reference (reducer IgnitionDetectedError / PlasmaStateError); the local-match "
         "tuning state is re-checked on the VNA before RF is re-applied"},
        {"step": "S-09", "powered": True, "prerequisites": [R13, "P1 registered procedure (" + P1_PENDING + ")"],
         "what": "RF pickup on P2 channels (CAL-P2-13; ICP-17)"},
        {"step": "S-10", "powered": False, "what": "GATE: P1 hands over a stable ICP operating region (" + P1_PENDING
         + "); photodiode threshold frozen before the P2 map (HM-R15, A9.4 P2Q-05)"},
        {"step": "S-11", "powered": True, "prerequisites": [R13, "HM-R01", "HM-R11"],
         "what": "hot map (phase HOT_MAP) under HM-R01..R15 with CAL-P2-11 bracketing"},
    ]

    # ================================================================ (4) data model
    data_model = {
        "schema_file": f"{LANE_REL}/{SCHEMA_NAME}", "reducer": REDUCER_REL, "record_schema_id": RED.SCHEMA_ID,
        "calibration_schema_id": RED.CAL_SCHEMA_ID, "required_record_fields": list(RED.REQUIRED_RECORD_FIELDS),
        "required_factor_fields": list(RED.REQUIRED_FACTOR_FIELDS),
        "required_calibration_fields": list(RED.REQUIRED_CAL_FIELDS), "planes": list(RED.PLANES),
        "record_phases": list(RED.RECORD_PHASES), "methods": list(RED.METHODS), "loss_methods": list(RED.LOSS_METHODS),
        "refusals": {
            "MissingCalibrationError": "calibration set / sensor / coupler error model / two-port / tuning state / V/I "
                                       "/ loss bound / cold reference / current probe absent, or frequency / Z0 mismatch",
            "ReferencePlaneError": "record without reference_planes, undeclared or unknown plane, powers not at RP-CPL, "
                                   "two-port or fixture planes not as declared",
            "UncalibratedPhaseError": "de-embedding with scalar-only data or a non-phase-calibrated coupler / two-port; "
                                      "V/I probe without phase calibration",
            "ForwardAsPlasmaError": "any P_plasma* / P_absorbed_plasma* input key, any power-like key containing "
                                    "'plasma' at any depth, or a power label (key or value) naming plasma power",
            "SequenceError": "HOT_MAP record without a P1 stable-region reference (or one that is PENDING/TBD)",
            "PlasmaStateError (SequenceError)": "lit plasma in a DUMMY_LOAD / COLD_ANTENNA_POWERED_UNLIT record, lit/"
                                                "mode inconsistent or lit not boolean, powered-unlit record without "
                                                "gas off (gas null, both mdot = 0, p_chamber logged) or without the "
                                                "optical unlit verification, a COLD_ANTENNA_POWERED_UNLIT / HOT_MAP "
                                                "record without the simultaneous photodiode, reflected-power, antenna-"
                                                "current, collector-response and pressure records or without the "
                                                "threshold basis, a HOT_MAP mode that differs from the photodiode "
                                                "classification, cold reference not from a verified-unlit source",
            "UncertainPlasmaStateError (PlasmaStateError)": "plasma state UNCERTAIN (A9.4 P2Q-05): optical UNLIT with "
                                                            "electrical evidence of ignition / mode transition, lost "
                                                            "line of sight, saturated photodiode, or lit without an "
                                                            "E/H assignment; never a cold reference or map point "
                                                            "without re-classification",
            "IgnitionDetectedError (PlasmaStateError)": "powered-unlit record whose optical signal reached the unlit "
                                                        "threshold of the P1 registered procedure (abort and flag, "
                                                        "S-08)",
            "RecordError": "malformed or non-finite values, P_reflected > P_forward, singular transforms, missing "
                           "nested sub-fields, HOT_MAP without factors.gas; mismatch envelope mixing data classes / "
                           "evidence statuses or evidence tags"},
        "evidence_tags": list(RED.EVIDENCE_TAGS),
        "plasma_state_classes": list(RED.MODE_LABELS),
        "outputs": ["at_RP_CPL: P_forward, P_reflected, P_net, |Gamma| (powers and complex), VSWR",
                    "Z_antenna per method at RP-ANT (R, X), primary method, method difference",
                    "P_line/match,loss, P_delivered, match/line efficiency (or TBD / declared-bound interval)",
                    "antenna-current cross-check, resistance split (reconstructed; its P_delivered_x_Rsplit_fraction_W"
                    " is a diagnostic, never P_plasma evidence for any gate)",
                    "unlit_verification of powered-unlit records (state_class UNLIT, A9.4 P2Q-05); "
                    "plasma_state_classification of HOT_MAP records (UNLIT / E_MODE / H_MODE; UNCERTAIN refused); "
                    "classify_plasma_state(); cold_reference_from_reduced() for R_cold entries",
                    "evidence_tag per record (from factors.gas / engineering_control; Ar and OQ-VI-05 records are "
                    "non-scoring)",
                    "mismatch_envelope(): ranges, line peak stresses referred to RP-CPL, antenna peaks split into "
                    "V/I-measured and derived-from-P_delivered, coverage counts with excluded record ids; "
                    "rating_status "
                    "TBD_AFTER_IMPEDANCE_MAP; synthetic data labelled SYNTHETIC_TEST_DATA_NOT_EVIDENCE"],
        "complex_encoding": "[re, im]",
        "two_port_convention": "ABCD, port 1 toward the generator, port 2 toward the antenna; S referenced to Z0",
    }

    # ================================================================ (5) instrument list
    def ins_(iid, name, a93_line, rfq_v1, specs, status="PROPOSED"):
        return item(iid, name, "see required_specs", "-", "P2 preparation (A9.3 authorizations.P2)",
                    [A93_REF["P2"], A93_REF["OQ-RFQ-07"]], "assumed", status, "LOCK-1",
                    a9_3_rf_package_line=a93_line, rfq_v2_line=RFQV2_PENDING, rfq_v1_line=rfq_v1,
                    required_specs=specs, purchase="quotation only; no purchase order (row 8; H3 gate); dispatch by "
                    "the owner / procurement, never by this lane (A9.3 OQ-RFQ-07); A9.4 authorizes the owner / "
                    "procurement to send the P1_NEEDED packages for quotation (RFQ, technical clarification, indicative "
                    "lead time, commercial quotation, datasheets / certificates), not purchase orders, advance payments "
                    "or binding commitments")
    f_spec = {"quantity": "frequency coverage", "value": "must include 13.56 MHz", "units": "MHz",
              "source": "row 72; UB-RF-00", "evidence_class": "owner-allocation"}
    instruments = [
        ins_("INS-P2-01", "V/I probe (complex V and I, phase-resolved) for RP-VI",
             "not in the A9.3 RF package list -> proposed addition (P2Q-02)", None,
             [f_spec, {"quantity": "voltage / current range", "value": "TBD - requires the cold antenna impedance "
                       "(CAL-P2-08) and the generator selection (" + P1_PENDING + "); sizing relations "
                       "I_ant,pk <= sqrt(2 P_del,max / R_ant,cold) if the plasma adds non-negative resistance (verify at "
                       "hot conditions) and V_ant,pk = I_ant,pk |Z_ant|", "units": "V; A", "source": "this package",
                       "evidence_class": None},
              {"quantity": "relative phase uncertainty", "value": "TBD - u(phi) <= u(R)_target / |X| (LOCK-2)",
               "units": "rad", "source": "ZM-A sensitivity relation", "evidence_class": None},
              {"quantity": "vacuum / thermal compatibility and mounting", "value": "TBD - requires the module drawings",
               "units": "-", "source": "ICD ICP-07", "evidence_class": None}]),
        ins_("INS-P2-02", "dual directional coupler (RP-CPL)", "directional coupler (A9.3 RF package)",
             "RFQ-04 'dual directional coupler + forward/reflected sensors' (RFQ-04-R08/R09)",
             [f_spec, {"quantity": "directivity", "value": "TBD - D >= D_min, D_min frozen at LOCK-2 (UB-RF-04, "
                       "A9H-INS-16)", "units": "dB", "source": "A9-07 IDA7-21", "evidence_class": None},
              {"quantity": "power rating", "value": RATINGS_TBD + " (A9.2 rf_500W; must cover the selected generator's "
                                                                  "forward power at the residual |Gamma|)",
               "units": "W", "source": "A9.2 rf_500W", "evidence_class": None},
              {"quantity": "vector (phase) output for method ZM-B", "value": "required if ZM-B is to run from the "
               "coupler; otherwise a VNA-receiver or vector reflectometer at RP-CPL", "units": "-",
               "source": "this package ZM-B", "evidence_class": "assumed"}]),
        ins_("INS-P2-03", "forward / reflected power sensors", "forward/reflected sensors (A9.3 RF package)",
             "RFQ-04 (RFQ-04-R08/R09)",
             [f_spec, {"quantity": "range / linearity", "value": "TBD - requires the coupler coupling factor and the "
                       "generator selection; covering the 0-500 W delivered/operating investigation capability plus "
                       "the characterized mismatch (UB-RF-03)", "units": "W", "source": "row 72; UB-RF-03",
                       "evidence_class": None},
              {"quantity": "calibration", "value": "traceable certificate at 13.56 MHz (A9H-CAL-02; MS-P2-01)",
               "units": "-", "source": "A4; A9H-CAL-02", "evidence_class": "owner-allocation"}]),
        ins_("INS-P2-04", "vector network analyser (one-port and two-port; receiver/spectrum mode if available)",
             "not in the A9.3 RF package list -> proposed addition (P2Q-02)", None,
             [{"quantity": "frequency coverage", "value": "must include 13.56 MHz and the cold-antenna sweep span "
               "(TBD - requires the antenna design) and, for harmonics, N_h x 13.56 MHz with N_h TBD (UB-RF-06, LOCK-2)",
               "units": "MHz", "source": "row 72; UB-RF-06", "evidence_class": None},
              {"quantity": "port power / input protection", "value": "TBD - the VNA never sees generator power; "
               "attenuators and a switching procedure isolate it (INS-P2-06)", "units": "dBm", "source": "this package",
               "evidence_class": None}]),
        ins_("INS-P2-05", "calibration kits: coaxial SOL/SOLT with standard data + antenna-terminal fixture standards",
             "not in the A9.3 RF package list -> proposed addition (P2Q-02)", None,
             [{"quantity": "connector family", "value": "TBD - requires the selected coax / feedthrough (ICD ICP-15)",
               "units": "-", "source": "ICD ICP-15", "evidence_class": None},
              {"quantity": "fixture standards", "value": "TBD - requires the antenna-terminal drawing", "units": "-",
               "source": "this package CAL-P2-01", "evidence_class": None}]),
        ins_("INS-P2-06", "fixed attenuators (sensor / VNA protection, coupling-arm padding)",
             "not in the A9.3 RF package list -> proposed addition (P2Q-02)", None,
             [f_spec, {"quantity": "attenuation and power rating", "value": "TBD - requires the coupler coupling "
                       "factor and the generator selection", "units": "dB; W", "source": "this package",
                       "evidence_class": None}]),
        ins_("INS-P2-07", "dummy loads: (a) 50-ohm calorimetric load; (b) antenna-simulator load of VNA-known low-R / "
             "high-X impedance", "dummy load (A9.3 RF package) for (a); (b) proposed addition (P2Q-02)",
             "RFQ-04 'calorimetric cross-check load' (RFQ-04-R10) for (a)",
             [f_spec, {"quantity": "power rating", "value": "TBD - requires the generator selection (" + P1_PENDING +
                       ")", "units": "W", "source": "this package", "evidence_class": None},
              {"quantity": "simulator impedance", "value": "TBD - requires the cold antenna impedance (CAL-P2-08); "
               "never taken from the analog", "units": "ohm", "source": "this package CAL-P2-10",
               "evidence_class": None}]),
        ins_("INS-P2-08", "phase-stable test cables (VNA) + characterized flexible stand-crossing coax pair",
             "RF coax (A9.3 RF package)", "RFQ-04 'flexible RF coax, identical live + sham pair' (RFQ-04-R11)",
             [f_spec, {"quantity": "phase stability vs flexure / temperature", "value": "TBD - requires the "
                       "UB-P2-Z-05 allocation (LOCK-2)", "units": "deg", "source": "this package CAL-P2-12",
                       "evidence_class": None}]),
        ins_("INS-P2-09", "antenna RF current probe (Rogowski / current transformer)",
             "not in the A9.3 RF package list -> proposed addition (P2Q-02)", None,
             [f_spec, {"quantity": "current range", "value": "TBD - same sizing relation as INS-P2-01",
                       "units": "A", "source": "this package", "evidence_class": None}]),
        ins_("INS-P2-10", "optical-emission photodiode + amplifier + DAQ channel, with optical access / window (REQUIRED "
             "independent ignition / unlit and E/H-mode indicator; S-08 unlit verification; A9.4 P2Q-05)",
             "not in the A9.3 RF package list -> added by A9.4 P2Q-05 to the P1_NEEDED / P2 preparation instrumentation "
             "quote (photodiode, optical access / window, amplifier, DAQ channel)", None,
             [{"quantity": "spectral band / view", "value": "TBD - requires the module optical access", "units": "-",
               "source": "this package HM-R06", "evidence_class": None},
              {"quantity": "line of sight to the ICP source volume and its loss detection", "value": "TBD - requires "
               "the module / chamber optical access geometry", "units": "-", "source": "A9.4 P2Q-05",
               "evidence_class": None},
              {"quantity": "amplifier gain / bandwidth and saturation (over-range) indication", "value": "TBD - requires "
               "the P1 dark / unlit / lit emission levels (no threshold set now)", "units": "V/A; Hz",
               "source": "A9.4 P2Q-05", "evidence_class": None},
              {"quantity": "DAQ channel on the common time base, simultaneous with P_reflected, antenna current, "
               "collector / current-path and pressure channels", "value": "1 channel (sample rate TBD - requires the "
               "P1 plan)", "units": "-", "source": "A9.4 P2Q-05; INS-18", "evidence_class": "owner-stated"}],
             status="OWNER_GIVEN"),
        ins_("INS-P2-11", "input power analyser for P_mains,in of the laboratory generator",
             "13.56 MHz generator line (A9.3 OQ-RFQ-06 measurement requirement)", "RFQ-04-R04",
             [{"quantity": "range", "value": "TBD - requires the generator selection", "units": "W",
               "source": "A9.3 OQ-RFQ-06", "evidence_class": None}]),
        ins_("INS-P2-12", "match element position read-out / encoders", "local matching network components (A9.3 RF "
             "package)", "RFQ-04-R07 / R17", [{"quantity": "resolution", "value": "TBD - requires the CAL-P2-03 grid "
                                                "and CAL-P2-04 interpolation error", "units": "-",
                                                "source": "this package", "evidence_class": None}]),
    ]

    # ================================================================ (6) outputs P2 feeds later
    outputs_later = [
        {"id": "ICPQ-10", "what": "total ICP module heat-load bound (ICP-43)", "p2_supplies":
         "P_forward, P_delivered and P_line/match,loss envelope over the P1 stable region (mismatch_envelope)",
         "status": "OPEN (owner call; not answered here)", "source": DELIVERABLES["OQ3"][0]},
        {"id": "ICPQ-11", "what": "k_RF between rated antenna-circuit RF voltage and V_ant,peak (ICP-44)",
         "p2_supplies": "measured antenna-terminal V_peak / I_peak envelope (ZM-A) at the maximum operating point",
         "status": "OPEN (owner call; no value proposed)", "source": DELIVERABLES["OQ3"][0]},
        {"id": "OQ-A910-06", "what": "interim 600 W RF-path heat-allocation basis of ICP-36", "p2_supplies":
         "P_delivered and P_line/match,loss envelope to re-derive ICP-36", "status": "OPEN (owner call)",
         "source": DELIVERABLES["OQ3"][0]},
        {"id": "RF_COMPONENT_RATINGS", "what": "generator, coupler, coax, connectors, local-match elements "
         "(voltage / current), feedthroughs (UB-RF-01 rating, ICP-15, A9H-INS-15/16, A9H-RF-LM-01, RFQ-04-R07/R11/R12/"
         "R17)", "p2_supplies": "mismatch envelope (rating_status TBD_AFTER_IMPEDANCE_MAP until real data exist)",
         "status": RATINGS_TBD, "source": "A9.2 a9_10_statuses"},
        {"id": "LOCAL_MATCH_FLIGHT_IMPLEMENTATION", "what": "fixed / switched / electronically tuned / other "
         "(ICP-13)", "p2_supplies": "Z_antenna = R + jX vs mdot, P_RF, p, gas, Hall operating point; fixed-tune "
         "sub-sweeps (HM-F08)", "status": "DEFERRED by A9.2 icp_matching_strategy", "source": "A9.2"},
        {"id": "RF_INTERLOCK_TRIP_THRESHOLDS", "what": "reflected-power / VSWR trips (ICP-16, A9H-RF-PROT-01, "
         "RFQ-04-R16, A9-04 LA-03)", "p2_supplies": "characterized reflected-power / VSWR envelope incl. mode jumps "
         "and tuning transients", "status": "after-evidence (A9.2 rf_protection)", "source": "A9.2"},
        {"id": "VALIDATION_INPUTS", "what": "VI-RF-02..07, VI-RF-10", "p2_supplies": "reduced records",
         "status": "HARDWARE_ONLY (unchanged)", "source": DELIVERABLES["VI"][0]},
    ]

    # ================================================================ (b) interface demands
    idem = [
        ("IDP2-01", "P1 -> P2", "stable ICP operating region (factor ranges of P_RF, mdot, p, gas, Hall point, "
         "collector bias) and its hand-over record", "W; mg/s; Pa; -; V, A", P1_PENDING),
        ("IDP2-02", "P1 -> P2", "selected laboratory generator, adjustable local match (tuning range, element "
         "read-out), antenna / terminal geometry, provisional protection limits", "-", P1_PENDING),
        ("IDP2-03", "P2 -> P1", "calibrated RF chain and reducer usable by P1 for P_delivered (C_e = P_RF,delivered / "
         "I_e, A9.3 OQ-RFQ-06) and for the OQ-VI-05 time series P_RF,fwd(t), P_RF,refl(t)", "W", "OFFERED"),
        ("IDP2-04", "P2 -> RFQ v2", "instrument list INS-P2-01..12 with required specs as quantities or TBD",
         "-", "OFFERED; mapping " + RFQV2_PENDING),
        ("IDP2-05", "RFQ v2 -> P2", "RF-package line ids for the instruments", "-", RFQV2_PENDING),
        ("IDP2-06", "P2 -> A9-04 uncertainty budget", "new PROPOSED components UB-P2-Z-01..08 for the UB-DQ-RF chain; "
         "closes UB-RF-02..07 via CAL-P2-02/03/07/09", "relative; ohm; rad",
         "OFFERED (adoption is an A9-04 successor / owner item; the merged budget is not edited)"),
        ("IDP2-07", "A9-04 -> P2", "k_x = 2 coupler-vs-calorimetry rule (UB-RF-08), D_min (UB-RF-04), u(P_net) "
         "allocation", "-", "OWNER_GIVEN (k_x) / TBD LOCK-2 (D_min)"),
        ("IDP2-08", "ICD (A9-03) -> P2", "ICP-13 chain, ICP-14 plane, ICP-17 pickup test, ICP-18 coax, ICP-21 "
         "collector, ICP-34 telemetry/pressure port", "-", "read (merged)"),
        ("IDP2-09", "P2 -> ICD / H2 (A9-07)", "antenna-terminal V/I envelope for ICP-44 / ICPQ-11; P_delivered and "
         "loss envelope for ICP-36 / ICP-43; ratings for ICP-15 / A9H-INS-15/16 / A9H-RF-LM-01", "V; A; W",
         "LATER (after the hot map)"),
        ("IDP2-10", "H2 / H-1 -> P2", "Hall operating-point channels (V_d, I_d, coil currents) and registered "
         "envelope incl. I_d,max,H1, which sets the ICP-45 requirement I_e,required = I_d,max,H1 "
         "(ICP45_REQUIRED_CURRENT = H1_REGISTERED_MAX) and hence the Hall points the map must cover; I_d sensor range "
         "to the 8.33 A stand ceiling (a rating ceiling, not a requirement)", "V; A", "PENDING (H-1 registration; "
         "A9.3 OQ-A907-02)"),
        ("IDP2-11", "A9-02 bus boundary -> P2", "A902-21 generator DC-input -> forward-power efficiency and A902-22 "
         "match DC draw stay TBD; P2 logs P_mains,in only as a GROUND/FACILITY_ONLY engineering quantity", "W",
         "TBD LOCK-2 / LOCK-1 (unchanged)"),
        ("IDP2-12", "P2 -> thermal (P3)", "P_line/match,loss on the module (heat source for the coupled thermal "
         "model); coupled H-1/ICP thermal closure stays UNRESOLVED", "W", "LATER"),
        ("IDP2-13", "P2 -> INS-18 time base", "P2 channels on the common time base", "s", "PROPOSED"),
        ("IDP2-14", "P1 gas metrology -> P2", "Ar MFC (one range, or two overlapping ranges only if one cannot cover "
         "the sweep) calibration record via the rate-of-rise / transfer path, for the HM-F02 Ar levels and "
         "UB-P2-M-01 (A9.3 OQ-RFQ-02); Ar data ENGINEERING_ONLY_NON_SCORING", "mg/s; sccm", P1_PENDING),
        ("IDP2-15", "ICD ICP-23 / P1 -> P2", "~1 kV-class representative-gas isolator qualification record for any "
         "ICP gas line bridging isolated potentials (dedicated G-ATM / G-XE diagnostic feed of HM-F02; any line across "
         "the floating ICP body when HM-F07 biases the collector); none required where both ends are intentionally "
         "at the same floating potential (A9.3 ICPQ-06)", "V", "PENDING (qualification not yet run)"),
        ("IDP2-16", "P2 -> P1", "powered-step prerequisites HM-R13 (match pre-tuned on the VNA, calibrated coupler "
         "monitoring, P1 provisional limits / foldback, ICP-16 interlocks, facility RF safety) offered for the P1 "
         "bench RF-on sequence", "-", "OFFERED"),
        ("IDP2-17", "P1 -> P2", "photodiode dark / background, RF-powered known-unlit and known-lit P1 plasma records "
         "(with simultaneous P_reflected, antenna current, collector / current-path response, pressure) for the HM-R15 "
         "threshold, frozen before the P2 map (A9.4 P2Q-05)", "V; W; A; Pa", P1_PENDING),
        ("IDP2-18", "P2 -> RFQ v2", "INS-P2-10 photodiode, optical access / window, amplifier and DAQ channel for the "
         "P1_NEEDED / P2 preparation instrumentation quote (A9.4 P2Q-05)", "-", "OFFERED; mapping " + RFQV2_PENDING),
    ]
    interface_demands = [{"id": i, "direction": d, "quantity": q, "units": u, "status": s} for i, d, q, u, s in idem]

    # ================================================================ (c) owner answers applied
    oaa = [
        {"ref": r72, "how": "13.56 MHz; directional-coupler forward/reflected is the primary power measurement; "
                            "calorimetry independent cross-check (CAL-P2-07/09); 0-500 W delivered/operating "
                            "capability as the HM-F01 bound, not a rating"},
        {"ref": r8, "how": "instrument list is quotation-only (no purchase order before H3)"},
        {"ref": r62, "how": "RF forward/reflected, interlock and temperatures in the record model"},
        {"ref": r64, "how": "RF pickup of the P2 channels (CAL-P2-13)"},
        {"ref": r70, "how": "collector bias as a separate factor HM-F07 (never hard-grounded by default)"},
        {"ref": r86, "how": "not applied to any value here; thermal items stay UNRESOLVED (no PASS)"},
        {"ref": r108, "how": "P_mains,in is never P_bus evidence (HM-R10)"},
        {"ref": r117, "how": "flexible coax characterized as a live/sham pair (CAL-P2-02/12)"},
        {"ref": r130, "how": "telemetry channels in the record model"},
        {"ref": r133, "how": "sham routing kept if a V/I probe line is used on the stand (ZM-B transfer rule)"},
        {"ref": r144, "how": "every TBD carries LOCK-1 / LOCK-2 / after-evidence"},
        {"ref": r145, "how": "outputs feed the Hall->ICP validation inputs VI-RF-02..07/10"},
        {"ref": A91_REF["UBQ-03"], "how": "bare +/-a certificate bounds rectangular (CAL-P2-07)"},
        {"ref": A91_REF["UBQ-04"], "how": "k_x = 2 coupler-vs-calorimetry rule reused, not changed"},
        {"ref": A91_REF["UBQ-05"], "how": "pre/post calibration shift rule for CAL-P2-11"},
        {"ref": A91_REF["A9-03-matching"], "how": "superseded for the baseline by A9.2 OQ-A907-11 (history only)"},
        {"ref": A92_REF["OQ-A907-11"], "how": "reference-plane chain RP-CPL -> RP-MIN -> RP-ANT"},
        {"ref": A92_REF["rf_measurement_reference"], "how": "retained quantities; P_delivered definition; reducer "
                                                            "refuses P_forward = P_plasma"},
        {"ref": A92_REF["rf_500W"], "how": "no rating from 500 W; all 50-ohm chain ratings TBD_AFTER_IMPEDANCE_MAP"},
        {"ref": A92_REF["rf_protection"], "how": "trip thresholds are an output (HM-R11)"},
        {"ref": A92_REF["icp_matching_strategy"], "how": "adjustable local match for development; Z_antenna vs "
                                                         "mdot, P_RF, p, gas, Hall point is the map definition"},
        {"ref": A92_REF["a9_10_statuses"], "how": "statuses carried unchanged; no open item converted to PASS"},
        {"ref": A92_REF["post_a9_priorities"], "how": "this lane prepares P2"},
        {"ref": A92_REF["icp_coupled_thermal"], "how": "P2 supplies Q_RF/match inputs later; thermal stays UNRESOLVED"},
        {"ref": A93_REF["P1"], "how": "P1 runs 'subject to existing safety/interlock/metrology requirements': HM-R13 "
                                      "carries that into every powered P2 preparation step; P1 content is PENDING"},
        {"ref": A93_REF["P2"], "how": "V/I sensing, coupler chain, calibration, S-parameter/impedance methodology, data "
                                      "model prepared; the plasma map waits for P1 (HM-R01, S-10 gate)"},
        {"ref": A93_REF["OQ-VI-03"], "how": "the antenna of the open-tube coaxial first build is the map object; "
                                            "orificed variants not addressed"},
        {"ref": A93_REF["OQ-VI-05"], "how": "record model carries P_RF,fwd(t), P_RF,refl(t) on the common time base; "
                                            "records of that sequence set engineering_control = 'OQ-VI-05' and the "
                                            "reducer tags them REQUIRED_ENGINEERING_CONTROL_NON_SCORING (not a PASS/"
                                            "FAIL gate); envelopes never mix them with other tags"},
        {"ref": A93_REF["OQ-A907-02"], "how": "8.33 A only as a sensor-range ceiling (HM-F06, IDP2-10); the ICP-45 "
                                              "requirement I_e,required = I_d,max,H1 (ICP45_REQUIRED_CURRENT = "
                                              "H1_REGISTERED_MAX) fixes that the map must cover the registered H-1 "
                                              "maximum discharge current point, PENDING H-1 registration; no current "
                                              "value is set or predicted here"},
        {"ref": A93_REF["ICPQ-06"], "how": "applies where P2 puts a potential difference across ICP gas plumbing: "
                                           "a dedicated G-ATM / G-XE diagnostic feed (HM-F02) or a collector-bias / "
                                           "floating-body level (HM-F07) is used only after the ~1 kV-class "
                                           "representative-gas isolator qualification of that line (IDP2-15); not "
                                           "applicable to the primary G-REUSE mode where no dedicated line is used, "
                                           "nor to lines whose ends sit at the same floating potential; P2 runs no "
                                           "isolator qualification itself"},
        {"ref": A93_REF["OQ-RFQ-02"], "how": "Ar mdot levels (HM-F02) use one Ar MFC range, or two overlapping ranges "
                                             "only if one cannot cover the sweep around the owner-stated 70 sccm ~ "
                                             "2.1 mg/s anchor; controller verified by the rate-of-rise / transfer path "
                                             "(IDP2-14, UB-P2-M-01); Ar records tagged ENGINEERING_ONLY_NON_SCORING "
                                             "by the reducer; the row-123 four-range rule stays for atmospheric "
                                             "score-bearing paths (not an RF instrument: no INS-P2 line)"},
        {"ref": A93_REF["OQ-RFQ-06"], "how": "mains generator, P_mains,in logged GROUND/FACILITY_ONLY (HM-R10, "
                                             "INS-P2-11)"},
        {"ref": A93_REF["OQ-RFQ-07"], "how": "instrument list mapped to the RF package; no supplier contact"},
        {"ref": A93_REF["OQ-RFQ-10"], "how": "dedicated ICP flow = 0 in the primary mode; diagnostic only (HM-F02)"},
        {"ref": A94_REF["P2Q-05"], "how": "ANSWERED (OWNER_DECIDED - PHOTODIODE_REQUIRED): INS-P2-10 is the required "
                                          "independent ignition / unlit and E/H indicator (OWNER_GIVEN); state classes "
                                          "UNLIT / E_MODE / H_MODE / UNCERTAIN (reducer MODE_LABELS, "
                                          "classify_plasma_state; HM-F05, HM-R14); COLD_ANTENNA_POWERED_UNLIT valid only "
                                          "with optical proof; optical UNLIT + electrical evidence -> UNCERTAIN; lost "
                                          "line of sight / saturation refused as UNLIT evidence; UNCERTAIN never a cold "
                                          "reference or map point; threshold HM-R15 TBD from P1 dark / unlit / lit "
                                          "records, frozen before the map (S-10); procurement IDP2-18; P2Q-05 removed "
                                          "from the open list"},
        {"ref": A94_REF["P1Q-14"], "how": "HM-F07: ICP body / collector bias levels stay inside the 350 V class with "
                                          ">= 525 V design withstand and the initial 1.05 kV DC / 60 s DWV before first "
                                          "HV/RF operation (P1 bench item); ICP-44 RF insulation stays OPEN"},
        {"ref": A94_REF["p1_needed_rfqs"], "how": "instrument list: the owner / procurement may send the P1_NEEDED "
                                                  "packages for quotation (RFQ, clarification, indicative lead time, "
                                                  "commercial quotation, datasheets / certificates); no purchase order, "
                                                  "advance payment or binding commitment; this lane contacts no "
                                                  "supplier"},
    ]

    # ================================================================ (d) new open owner questions
    new_q = [
        {"id": "P2Q-01", "question": "Adopt ZM-A (V/I probe at the antenna terminals) as the primary Z_antenna method on "
         "the P1/P2 bench, with ZM-B (de-embedding) as the per-point cross-check and ZM-C (antenna current) for R?",
         "proposed_answer": "yes (PROPOSED)", "needed_by": "LOCK-1"},
        {"id": "P2Q-02", "question": "The owner's A9.3 RF package list does not name the V/I probe, VNA, calibration "
         "kits, attenuators, antenna-simulator load, antenna current probe or phase-stable test cables. Add them to the "
         "RF package, or to a separate RF-metrology package under the common interface document?",
         "proposed_answer": "owner call; proposal: a separate RF-metrology package (different supplier speciality)",
         "needed_by": "RFQ v2 dispatch"},
        {"id": "P2Q-03", "question": "Agreement rules for ZM-A vs ZM-B and for up/down sweeps (hysteresis): same "
         "normalized-statistic form as UB-RF-08 with a k frozen at LOCK-1?", "proposed_answer": "owner call on the "
         "form; no value proposed", "needed_by": "LOCK-1"},
        {"id": "P2Q-04", "question": "Hot-map tuning policy: re-tune for minimum reflected power at every point, plus "
         "fixed-tune sub-sweeps around representative points to inform the flight match implementation?",
         "proposed_answer": "yes (PROPOSED)", "needed_by": "LOCK-1"},
        {"id": "P2Q-06", "question": "On the thrust stand, rely on ZM-B (no V/I probe line across the stage) once the "
         "bench shows agreement, rather than routing a V/I probe line with a matched sham?",
         "proposed_answer": "yes, conditional on the P2Q-03 bench agreement (PROPOSED)", "needed_by": "LOCK-1"},
        {"id": "P2Q-07", "question": "Where no accredited scope exists for V/I-probe phase calibration at 13.56 MHz, "
         "accept an in-house procedure traceable through the VNA and its kit (MS-P2-03)?",
         "proposed_answer": "owner call", "needed_by": "LOCK-1"},
        {"id": "P2Q-08", "question": "Does the A9.3 ICPQ-06 isolator qualification ('wherever ICP plumbing bridges "
         "isolated potentials') also cover the ICP-34 pressure-sensing line when the ICP body floats or the collector "
         "is biased during P2?", "proposed_answer": "yes where that line bridges isolated potentials (PROPOSED; same "
         "plumbing logic)", "needed_by": "before the first biased / floating P2 point (S-11)"},
        {"id": "P2Q-09", "question": "Which recorded signals and step criteria constitute the 'electrical evidence of "
         "an ignition / mode transition' that turns an optically UNLIT record into UNCERTAIN (A9.4 P2Q-05): the HM-R06 "
         "indicators (step in reflected power / |Gamma| at fixed tuning, antenna-current step, collector / current-"
         "path response step, pressure step) with the same declared multiple of the combined uncertainty?",
         "proposed_answer": "yes (PROPOSED): reuse the HM-R06 indicator set; form frozen at LOCK-1, multiple at LOCK-2, "
         "before the P2 map; each record states the basis (electrical_indicator_basis)", "needed_by": "LOCK-1"},
    ]
    dispositioned = {o["ref"].get("decision") for o in oaa if isinstance(o["ref"], dict)}
    miss = [i for i in A93_DECISION_IDS if i not in dispositioned]
    if miss or set(A93_DECISION_IDS) != set(_load("A93")["decisions"]):
        raise SystemExit(f"A9.3 decisions without a disposition: {miss}")
    for q in new_q:
        if q["id"] in oq_rows:
            raise SystemExit(f"new question id {q['id']} collides with state v3")

    # ================================================================ (e) historical reuse
    hist = [
        {"path": DELIVERABLES["RFM"][0], "sha256": DELIVERABLES["RFM"][1],
         "reused": "method precedents only (entries listed in published_method_precedents)",
         "not_reused": "no value is used as a Vyovrinda impedance, power, efficiency or rating"},
        {"path": DELIVERABLES["INS"][0], "sha256": DELIVERABLES["INS"][1],
         "reused": "INS-03 principle (coupler at / upstream of the load plane with S1a loss characterization) and "
                   "INS-18 common time base", "not_reused": "INS-03 required-uncertainty numbers (pre-A9 lane-25 "
                                                            "model-derived allocation for the upstream RF source)"},
        {"path": DELIVERABLES["H2A9"][0], "sha256": DELIVERABLES["H2A9"][1],
         "reused": "RF reference-plane relations (gamma, peaks, load-power) and the 20 + j50 review case as a closed-"
                   "form check", "not_reused": "sensitivity loads as antenna data or ratings"},
        {"path": DELIVERABLES["EVI"][0], "sha256": DELIVERABLES["EVI"][1],
         "reused": "TK-20..26 as method context", "not_reused": "any analog number as Vyovrinda performance"},
        {"path": DELIVERABLES["RFQ04"][0], "sha256": DELIVERABLES["RFQ04"][1],
         "reused": "v1 line mapping (coupler/sensors, calorimetric load, live/sham coax)",
         "not_reused": "v1 predates A9.2/A9.3; v2 mapping PENDING"},
    ]

    # ================================================================ (f) m16 impact
    m16_impact = [
        {"row": 15, "key": "sensors_diagnostics", "how": "supplies PROPOSED RF calibration procedures CAL-P2-01..15 "
         "and the P2 channel list toward the row's S1A-C4 blocker; state unchanged (BLOCKED; procedures not frozen, "
         "instruments not procured)"},
        {"row": 18, "key": "icp_neutralizer_head", "how": "defines how Z_antenna and the antenna-terminal V/I "
         "envelope (ICP-44 input) will be measured; state unchanged (BLOCKED on ICP module design)"},
        {"row": 19, "key": "flight_rf_chain", "how": "methodology and data model for the analysis_test_needed "
         "'ICP impedance map'; ratings stay TBD_AFTER_IMPEDANCE_MAP; state unchanged"},
        {"row": 17, "key": "preionizer_interface", "how": "not touched (historical)"},
    ]
    h3h4 = {
        "h3_procurement_inputs": [f"{i['id']} {i['name']}" for i in instruments],
        "h4_test_inputs": [f"{s['step']}: {s['what']}" for s in sequence],
    }
    selfc = selfcheck(h2a9)
    if not selfc[0]["agrees_to_4_significant_digits"]:
        raise SystemExit("closed-form check SC-01 disagrees with the A9-07 review case")

    all_items = chain + planes + ub_new + ms_new + calplan + factors + rules + instruments
    items_table = [{k: it[k] for k in ("id", "name", "value", "units", "basis", "source", "evidence_class", "status",
                                       "freeze_point")} for it in all_items]

    doc = {
        "schema": "p2_impedance_prep_v1", "id": "p2_impedance_prep_v1", "lane": LANE, "trigger": TRIGGER,
        "title": "P2 ICP impedance-map instrument preparation", "date": DATE, "base_commit": BASE_COMMIT,
        "status": "PREPARATION_ONLY_NOT_RUN (plasma impedance map waits for the P1 stable region; A9.3)",
        "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
        "a9_2_statuses_carried": a910,
        "generated_by": SCRIPT_REL, "companion_document": f"{LANE_REL}/{MD_NAME}", "test": TEST_REL,
        "what_this_is_not": ["the plasma impedance map (not run, not predicted)",
                             "a prediction of impedance, thrust, efficiency, discharge or electron current or plasma "
                             "state (no Hall closure is admitted; the credible Hall set is empty)",
                             "an RF component rating or trip threshold (TBD_AFTER_IMPEDANCE_MAP / after-evidence)",
                             "a procurement, a supplier contact, an architecture ranking or a winner",
                             "an answer to any open owner question"],
        "decision_pins": [{"key": k, "path": p, "sha256": h, "what": w} for k, (p, h, w) in DECISIONS.items()],
        "deliverable_pins": [{"key": k, "path": p, "sha256": h, "what": w} for k, (p, h, w) in DELIVERABLES.items()],
        "never_pinned": NEVER_PINNED, "pending_lanes": PENDING_LANES,
        "a9_4_incorporation": {
            "follow_on": "fo_a9_4_incorporation", "trigger": "T_A9_4_INCORPORATION", "base_commit": A94_INC_BASE,
            "decision": {"path": DECISIONS["A94"][0], "sha256": DECISIONS["A94"][1]},
            "verbatim": {"path": DECISIONS["A94MD"][0], "sha256": DECISIONS["A94MD"][1]},
            "rule": "applied mechanically (owner step 2): only what A9.4 decides changed; ids and verified behaviour "
                    "otherwise kept",
            "answered": {"P2Q-05": a94["decisions"]["P2Q-05"]["status"]},
            "also_applied": ["P1Q-14 (HM-F07 note)", "execution_decisions.p1_needed_rfqs (instrument purchase note)"],
            "state_classes": a94["decisions"]["P2Q-05"]["state_classes"],
            "m16_impact_change": "none: A9.4 changes no M16 v3 row state"},
        "chain_parameters": chain, "reference_planes": planes, "z_antenna_methods": methods, "z_antenna_recommendation": recommendation,
        "calibration_plan": calplan, "uncertainty_items_new": ub_new, "metrology_items_new": ms_new,
        "hot_map_methodology": {"factors": factors, "rules": rules, "sequence": sequence},
        "data_model": data_model, "instrument_list": instruments, "p2_outputs_later": outputs_later,
        "items": items_table, "interface_demands": interface_demands, "owner_answers_applied": oaa,
        "open_owner_questions": new_q, "historical_reuse": hist, "m16_impact": m16_impact, "h3_h4_inputs": h3h4,
        "published_analog_context": tk, "published_method_precedents": rf_prec, "reducer_selfcheck": selfc,
        "compliance": {
            "no_prediction": True, "no_rating": True, "no_trip_threshold": True, "no_supplier_contact": True,
            "not_wired_into_archengine": True, "julia_run": False,
            "open_items_never_pass": "RF component ratings TBD_AFTER_IMPEDANCE_MAP; ICP / coupled thermal UNRESOLVED; "
                                     "anode OPEN / UNRESOLVED - carried unchanged",
            "pending_lanes_not_read": [p["path"] for p in PENDING_LANES]},
    }
    return doc


# ------------------------------------------------------------------------------------------------ schema
FIELD_DOCS = {
    "schema": ("string", "-", None, f"constant '{RED.SCHEMA_ID}'"),
    "record_id": ("string", "-", None, "unique id"),
    "data_class": ("string", "-", None, "measured | synthetic_test (synthetic output is labelled "
                                         "SYNTHETIC_TEST_DATA_NOT_EVIDENCE)"),
    "phase": ("string", "-", None, " | ".join(RED.RECORD_PHASES)),
    "calibration_set_id": ("string", "-", None, "id of the calibration set used (must be supplied to the reducer)"),
    "f_Hz": ("number", "Hz", None, "drive frequency; must equal the calibration frequency"),
    "Z0_ohm": ("number", "ohm", None, "reference impedance; must equal the calibration Z0"),
    "reference_planes": ("object", "-", "declares the plane of each measurement",
                         "keys coupler_powers (RP-CPL), coupler_reflection (RP-CPL, if complex reflection recorded), "
                         "vi_probe (RP-VI); values in " + ", ".join(RED.PLANES)),
    "methods": ("array", "-", None, "subset of " + ", ".join(RED.METHODS)),
    "loss_method": ("string", "-", None, " | ".join(RED.LOSS_METHODS)),
    "coupler": ("object", "W; [re, im]", "RP-CPL", "P_sens_fwd_W, P_sens_ref_W (sensor readings, W), "
                "power_sensor_cal_id, reflection_raw ([re, im] raw reflection ratio or null)"),
    "vi_probe": ("object|null", "V; A", "RP-VI", "V_raw, I_raw ([re, im]), vi_cal_id; null when not installed"),
    "match_state": ("object", "-", "RP-MIN -> RP-ANT", "tuning_state_id, positions, auto_tune, loss_bound_id"),
    "factors": ("object", "W; mg/s; Pa; V; A", None, "fields: " + ", ".join(RED.REQUIRED_FACTOR_FIELDS) +
                " (explicit null where not applicable; P_mains_in_W is GROUND/FACILITY_ONLY)"),
    "plasma_state": ("object", "-; V", None, "lit (boolean), mode (" + ", ".join(RED.MODE_LABELS) + "; UNLIT iff lit "
                     "is false; UNCERTAIN is never reduced), optical_signal_V (INS-P2-10 photodiode), unlit_threshold_V "
                     "and unlit_threshold_source (from the P1 registered procedure), threshold_basis {" +
                     ", ".join(RED.THRESHOLD_BASIS_FIELDS) + "}, photodiode_line_of_sight_ok, photodiode_saturated, "
                     "electrical_ignition_or_mode_transition and electrical_indicator_basis (A9.4 P2Q-05; required for "
                     + " and ".join(RED.CLASSIFIED_PHASES) + ", with antenna_current, factors.I_collector_A and "
                     "factors.p_chamber_Pa recorded simultaneously). Phases " + ", ".join(RED.UNLIT_PHASES) +
                     " must be unlit"),
    "sweep": ("object", "-", None, "sweep_id, direction (" + ", ".join(RED.SWEEP_DIRECTIONS) + "), index"),
    "settling": ("object", "s", None, "dwell_s, settled"),
    "temperatures_K": ("object", "K", None, "antenna, dielectric, collector, match, cables, probe"),
    "cold_reference_id": ("string|null", "-", "RP-ANT", "id of the cold-antenna reference in the calibration set"),
    "p1_stable_region_ref": ("string|null", "-", None, "required non-PENDING reference for HOT_MAP records"),
    "antenna_current": ("object|null", "A", "RP-ANT", "I_rms_A, probe_cal_id"),
}


_NUM = {"type": "number"}
_NUMN = {"type": ["number", "null"]}
_STR = {"type": "string"}
_STRN = {"type": ["string", "null"]}
_CX = {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2, "description": "[re, im]"}
_CXN = {"type": ["array", "null"], "items": {"type": "number"}, "minItems": 2, "maxItems": 2,
        "description": "[re, im] or null"}
SUBFIELD_TYPES = {
    "coupler": {"P_sens_fwd_W": dict(_NUM, **{"x-units": "W"}), "P_sens_ref_W": dict(_NUM, **{"x-units": "W"}),
                "power_sensor_cal_id": _STR, "reflection_raw": _CXN},
    "vi_probe": {"V_raw": dict(_CX, **{"x-units": "V (raw)"}), "I_raw": dict(_CX, **{"x-units": "A (raw)"}),
                 "vi_cal_id": _STR},
    "match_state": {"tuning_state_id": _STRN, "positions": {"type": "object"}, "auto_tune": {"type": ["boolean", "null"]},
                    "loss_bound_id": _STRN},
    "plasma_state": {"lit": {"type": "boolean"}, "mode": {"enum": list(RED.MODE_LABELS)},
                     "optical_signal_V": dict(_NUMN, **{"x-units": "V"}),
                     "unlit_threshold_V": dict(_NUMN, **{"x-units": "V"}), "unlit_threshold_source": _STRN,
                     "threshold_basis": {"type": ["object", "null"], "required": list(RED.THRESHOLD_BASIS_FIELDS),
                                         "properties": {"dark_background_record_id": _STR,
                                                        "rf_powered_known_unlit_record_id": _STR,
                                                        "known_lit_p1_record_id": _STR,
                                                        "frozen_before_p2_map": {"const": True}}},
                     "photodiode_line_of_sight_ok": {"type": ["boolean", "null"]},
                     "photodiode_saturated": {"type": ["boolean", "null"]},
                     "electrical_ignition_or_mode_transition": {"type": ["boolean", "null"]},
                     "electrical_indicator_basis": _STRN},
    "sweep": {"sweep_id": _STR, "direction": {"enum": list(RED.SWEEP_DIRECTIONS)}, "index": {"type": "integer"}},
    "settling": {"dwell_s": dict(_NUMN, **{"x-units": "s"}), "settled": {"type": ["boolean", "null"]}},
    "antenna_current": {"I_rms_A": dict(_NUM, **{"x-units": "A"}), "probe_cal_id": _STR},
    "factors": {"P_RF_setpoint_W": dict(_NUMN, **{"x-units": "W"}), "mdot_hall_anode_mg_s": dict(_NUMN, **{"x-units": "mg/s"}),
                "mdot_icp_dedicated_mg_s": dict(_NUMN, **{"x-units": "mg/s"}), "gas_mode": _STRN,
                "gas": dict(_STRN, description="evidence tag derived by the reducer (Ar -> ENGINEERING_ONLY_NON_SCORING)"),
                "p_icp_source_Pa": dict(_NUMN, **{"x-units": "Pa"}), "p_chamber_Pa": dict(_NUMN, **{"x-units": "Pa"}),
                "hall_state": {"type": ["string", "object", "null"]}, "V_collector_V": dict(_NUMN, **{"x-units": "V"}),
                "I_collector_A": dict(_NUMN, **{"x-units": "A"}),
                "P_mains_in_W": dict(_NUMN, **{"x-units": "W"}, description="GROUND/FACILITY_ONLY; never P_bus")},
}


def build_schema():
    missing = [f for f in RED.REQUIRED_RECORD_FIELDS if f not in FIELD_DOCS]
    if missing:
        raise SystemExit(f"schema docs missing for {missing}")
    props = {}
    for f in RED.REQUIRED_RECORD_FIELDS:
        t, u, plane, desc = FIELD_DOCS[f]
        types = t.split("|")
        props[f] = {"type": types if len(types) > 1 else types[0], "description": desc, "x-units": u,
                    "x-reference-plane": plane}
        if f in RED.NESTED_REQUIRED:
            req = list(RED.NESTED_REQUIRED[f])
            if set(SUBFIELD_TYPES[f]) != set(req):
                raise SystemExit(f"schema sub-field types for {f} out of step with the reducer")
            props[f]["required"] = req
            props[f]["properties"] = {k: SUBFIELD_TYPES[f][k] for k in req}
    props["power_labels"] = {"type": "object", "description": "optional; any label naming plasma power is refused",
                             "x-units": "-", "x-reference-plane": None}
    props["engineering_control"] = {"type": ["string", "null"], "enum": list(RED.ENGINEERING_CONTROLS) + [None],
                                    "description": "optional; 'OQ-VI-05' marks the A9.3 required engineering-control "
                                                   "sequence (tag REQUIRED_ENGINEERING_CONTROL_NON_SCORING)",
                                    "x-units": "-", "x-reference-plane": None}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{LANE_REL}/{SCHEMA_NAME}", "title": "P2 ICP impedance-map record (p2_impedance_record_v1)",
        "description": "Generated by " + SCRIPT_REL + " from the reducer's field tuples; complex values are [re, im]. "
                       "Forbidden keys (any depth): names starting with " + ", ".join(RED.FORBIDDEN_KEY_PREFIXES) +
                       ", and any power-like key (P_/p_ prefix, 'power', 'pwr' or a watt suffix) containing 'plasma'. "
                       "Nested required sub-fields mirror the reducer's NESTED_REQUIRED contract.",
        "type": "object", "required": list(RED.REQUIRED_RECORD_FIELDS), "properties": props,
        "$defs": {"calibration_set": {
            "type": "object", "required": list(RED.REQUIRED_CAL_FIELDS),
            "description": "schema '" + RED.CAL_SCHEMA_ID + "': power_sensors {id: {CF_fwd, CF_ref, certificate}}; "
                           "coupler {cal_id, plane RP-CPL, phase_calibrated, e00, e11, e10e01}; two_ports {line "
                           "(RP-CPL->RP-MIN), match_states {tuning_state_id: two-port RP-MIN->RP-ANT}} with S11, S12, "
                           "S21, S22, cal_id, phase_calibrated; vi_probe {cal_id, phase_calibrated, k_V, k_I, "
                           "fixture_abcd, fixture_from_plane RP-VI, fixture_to_plane RP-ANT, amplitude_convention}; "
                           "loss_bounds {id: {loss_fraction_max, source, evidence_class}}; cold_references {id: "
                           "{" + ", ".join(RED.COLD_REF_FIELDS) + "} with source_phase in "
                           + " | ".join(RED.COLD_REF_SOURCES) + " and a verified-unlit unlit_verification "
                           "(cold_reference_from_reduced() builds it from a reduced powered-unlit record)}; "
                           "antenna_current_probe {cal_id, k_mag, certificate} | null"}},
    }


# ------------------------------------------------------------------------------------------------ markdown
def _v(x):
    if isinstance(x, (dict, list)):
        return "`" + json.dumps(x, ensure_ascii=False) + "`"
    return str(x).replace("|", "\\|").replace("\n", " ")


def _src(s):
    if isinstance(s, list):
        return "; ".join(_src(x) for x in s)
    if isinstance(s, dict):
        if s.get("kind") == "owner_row":
            return f"row {s['row']}"
        return f"{s.get('kind')} {s.get('decision')}"
    return str(s)


def render_md(doc):
    L = [f"# {doc['title']} ({doc['id']})", "",
         f"Generated by `{doc['generated_by']}` from `{LANE_REL}/{JSON_NAME}` - do not edit by hand. Lane `{LANE}`, "
         f"trigger `{TRIGGER}`, base `{BASE_COMMIT}`.", "",
         f"**Status:** {doc['status']}. A9 status: `{doc['a9_status']}`.", "",
         "**A9.4 incorporation** (`{f}`, trigger `{t}`, base `{b}`): {r}. Decision `{dp}` (sha256 `{ds}`); verbatim "
         "`{vp}` (sha256 `{vs}`). Answered: {a}. Also applied: {o}. Plasma-state classes: {c}. M16: {m}.".format(
             f=doc["a9_4_incorporation"]["follow_on"], t=doc["a9_4_incorporation"]["trigger"],
             b=doc["a9_4_incorporation"]["base_commit"], r=doc["a9_4_incorporation"]["rule"],
             dp=doc["a9_4_incorporation"]["decision"]["path"], ds=doc["a9_4_incorporation"]["decision"]["sha256"],
             vp=doc["a9_4_incorporation"]["verbatim"]["path"], vs=doc["a9_4_incorporation"]["verbatim"]["sha256"],
             a="; ".join(f"{k} = {v}" for k, v in doc["a9_4_incorporation"]["answered"].items()),
             o="; ".join(doc["a9_4_incorporation"]["also_applied"]),
             c=", ".join(doc["a9_4_incorporation"]["state_classes"]),
             m=doc["a9_4_incorporation"]["m16_impact_change"]), "",
         "**What this is not:** " + "; ".join(doc["what_this_is_not"]) + ".", "",
         "A9.2 statuses carried unchanged: " + "; ".join(f"{k} = `{v}`" for k, v in doc["a9_2_statuses_carried"].items())
         + ".", "", "## 1. Reference planes", "", "| id | name | definition | status | freeze |", "|---|---|---|---|---|"]
    for p in doc["reference_planes"]:
        L.append(f"| {p['id']} | {_v(p['name'])} | {_v(p['value'])} | {p['status']} | {p['freeze_point']} |")
    L += ["", "### How Z_antenna is obtained", ""]
    for m in doc["z_antenna_methods"]:
        L += [f"**{m['id']} - {m['name']}** ({m['status']}; role: {m['role']})", "", f"Principle: {m['principle']}", "",
              "Pros:", *[f"- {x}" for x in m["pros"]], "", "Cons:", *[f"- {x}" for x in m["cons"]], ""]
    r = doc["z_antenna_recommendation"]
    L += [f"**Recommendation ({r['status']}, {r['freeze_point']}, {r['owner_question']}):** primary {r['primary']}; "
          f"cross-check {r['cross_check']}. Transfer rule: {r['transfer_rule']}", "",
          f"Sensitivity: {r['sensitivity_relations']['phase']} ({r['sensitivity_relations']['evidence_class']}). "
          f"{r['sensitivity_relations']['analog_context']}", "", "## 2. Calibration plan", "",
          "| id | step | planes | standards | when | uncertainty | metrology | value | status | freeze |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for c in doc["calibration_plan"]:
        L.append(f"| {c['id']} | {_v(c['name'])} | {', '.join(c['planes'])} | {_v('; '.join(c['standards']))} | "
                 f"{_v(c['when'])} | {', '.join(c['uncertainty_links'])} | {', '.join(c['metrology_links'])} | "
                 f"{_v(c['value'])} | {c['status']} | {c['freeze_point']} |")
    L += ["", "New uncertainty components (PROPOSED additions to the A9-04 UB-DQ-RF chain; the merged budget is not "
          "edited):", "", "| id | name | value | units | status | freeze |", "|---|---|---|---|---|---|"]
    for u in doc["uncertainty_items_new"]:
        L.append(f"| {u['id']} | {_v(u['name'])} | {_v(u['value'])} | {u['units']} | {u['status']} | "
                 f"{u['freeze_point']} |")
    L += ["", "New metrology items:", "", "| id | name | requirement | status | freeze |", "|---|---|---|---|---|"]
    for u in doc["metrology_items_new"]:
        L.append(f"| {u['id']} | {_v(u['name'])} | {_v(u['value'])} | {u['status']} | {u['freeze_point']} |")
    hm = doc["hot_map_methodology"]
    L += ["", "## 3. Hot-map methodology (not run)", "", "Factors:", "", "| id | factor | levels / value | units | "
          "status | freeze |", "|---|---|---|---|---|---|"]
    for f in hm["factors"]:
        L.append(f"| {f['id']} | {_v(f['name'])} | {_v(f['value'])} | {f['units']} | {f['status']} | "
                 f"{f['freeze_point']} |")
    L += ["", "Rules:", "", "| id | rule | text | status | freeze |", "|---|---|---|---|---|"]
    for f in hm["rules"]:
        L.append(f"| {f['id']} | {_v(f['name'])} | {_v(f['value'])} | {f['status']} | {f['freeze_point']} |")
    L += ["", "Sequence (powered steps start only when their prerequisites hold):", ""] + \
        [f"- **{s['step']}** [{'POWERED' if s['powered'] else 'unpowered'}] {s['what']}"
         + (f" (prerequisites: {', '.join(s['prerequisites'])})" if s.get("prerequisites") else "")
         + (f" (gate: {s['gate']})" if "gate" in s else "") for s in hm["sequence"]]
    dm = doc["data_model"]
    L += ["", "## 4. Data model", "", f"Schema `{dm['schema_file']}` (record `{dm['record_schema_id']}`, calibration "
          f"set `{dm['calibration_schema_id']}`); reducer `{dm['reducer']}` (pure, standard library).", "",
          "Required record fields: " + ", ".join(f"`{x}`" for x in dm["required_record_fields"]) + ".", "",
          f"Two-port convention: {dm['two_port_convention']}; complex values {dm['complex_encoding']}.", "",
          "Refusals:", ""] + [f"- `{k}`: {v}" for k, v in dm["refusals"].items()] + ["", "Outputs:", ""] + \
         [f"- {o}" for o in dm["outputs"]]
    L += ["", "Reducer self-check (SYNTHETIC_TEST_DATA_NOT_EVIDENCE, closed form):", ""]
    for s in doc["reducer_selfcheck"]:
        body = {k: v for k, v in s.items() if k not in ("id", "what", "evidence_status", "evidence_class")}
        L.append(f"- **{s['id']}** {s['what']}: `{json.dumps(body, ensure_ascii=False)}`")
    L += ["", "## 5. Instrument list (quotation only; mapped to the A9.3 RF package; RFQ v2 mapping PENDING)", "",
          "| id | instrument | A9.3 RF package line | RFQ v1 line | required specs |", "|---|---|---|---|---|"]
    for i in doc["instrument_list"]:
        specs = "; ".join(f"{s['quantity']}: {s['value']} [{s['units']}]" for s in i["required_specs"])
        L.append(f"| {i['id']} | {_v(i['name'])} | {_v(i['a9_3_rf_package_line'])} | {_v(i['rfq_v1_line'])} | "
                 f"{_v(specs)} |")
    L += ["", "## 6. Outputs P2 will feed later (not answered now)", "", "| id | what | P2 supplies | status |",
          "|---|---|---|---|"]
    for o in doc["p2_outputs_later"]:
        L.append(f"| {o['id']} | {_v(o['what'])} | {_v(o['p2_supplies'])} | {_v(o['status'])} |")
    L += ["", "## (a) Items / parameters", "", "| id | name | value | units | basis | source | evidence class | status "
          "| freeze |", "|---|---|---|---|---|---|---|---|---|"]
    for it in doc["items"]:
        L.append(f"| {it['id']} | {_v(it['name'])} | {_v(it['value'])} | {it['units']} | {_v(it['basis'])} | "
                 f"{_v(_src(it['source']))} | {it['evidence_class'] or 'n/a (no numeric value; TBD / PENDING)'} | {it['status']} | {it['freeze_point']} |")
    L += ["", "## (b) Interface demands", "", "| id | direction | quantity | units | status |", "|---|---|---|---|---|"]
    for d in doc["interface_demands"]:
        L.append(f"| {d['id']} | {d['direction']} | {_v(d['quantity'])} | {d['units']} | {_v(d['status'])} |")
    L += ["", "## (c) Owner answers applied", "", "| ref | how applied |", "|---|---|"]
    for o in doc["owner_answers_applied"]:
        L.append(f"| {_src(o['ref'])} | {_v(o['how'])} |")
    L += ["", "## (d) Open owner questions (new)", "", "| id | question | proposed answer | needed by |",
          "|---|---|---|---|"]
    for q in doc["open_owner_questions"]:
        L.append(f"| {q['id']} | {_v(q['question'])} | {_v(q['proposed_answer'])} | {q['needed_by']} |")
    L += ["", "## (e) Historical reuse", "", "| path | sha256 | reused | not reused |", "|---|---|---|---|"]
    for h in doc["historical_reuse"]:
        L.append(f"| {h['path']} | `{h['sha256'][:16]}...` | {_v(h['reused'])} | {_v(h['not_reused'])} |")
    L += ["", "## (f) M16 v3 impact", "", "| row | key | how |", "|---|---|---|"]
    for m in doc["m16_impact"]:
        L.append(f"| {m['row']} | {m['key']} | {_v(m['how'])} |")
    L += ["", "## (g) H3 / H4 inputs", "", "H3 (procurement, quotation only):", ""] + \
         [f"- {x}" for x in doc["h3_h4_inputs"]["h3_procurement_inputs"]] + ["", "H4 (test):", ""] + \
         [f"- {x}" for x in doc["h3_h4_inputs"]["h4_test_inputs"]]
    L += ["", "## Published analog context (method only; never Vyovrinda values)", "",
          "| id | quantity | value | unit | locator | class |", "|---|---|---|---|---|---|"]
    for t in doc["published_analog_context"]:
        L.append(f"| {t['id']} | {_v(t['quantity'])} | {_v(t['value'])} | {t['unit'] or '-'} | {_v(t['locator'])} | "
                 f"{t['evidence_class']} ({t['epistemic']}) |")
    L += ["", "## Published method precedents", "", "| id | citation | locator | access | use here |",
          "|---|---|---|---|---|"]
    for t in doc["published_method_precedents"]:
        L.append(f"| {t['id']} | {_v(t['citation'])} | {_v(t['locator'])} | {t['access']} | {_v(t['use_here'])} |")
    L += ["", "## Pins", "", "| key | path | sha256 |", "|---|---|---|"]
    for p in doc["decision_pins"] + doc["deliverable_pins"]:
        L.append(f"| {p['key']} | {p['path']} | `{p['sha256']}` |")
    L += ["", "Never pinned (mutable governance): " + ", ".join(doc["never_pinned"]) + ".", "",
          "Pending parallel lanes (not read, not imported): " + "; ".join(f"{p['path']} ({p['needed_for']})"
                                                                         for p in doc["pending_lanes"]) + ".", ""]
    return "\n".join(L)


def render():
    doc = build()
    js = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    md = render_md(doc)
    sc = json.dumps(build_schema(), indent=1, ensure_ascii=False) + "\n"
    return js, md, sc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the outputs are reproduced byte for byte")
    args = ap.parse_args(argv)
    js, md, sc = render()
    outs = ((HERE / JSON_NAME, js), (HERE / MD_NAME, md), (HERE / SCHEMA_NAME, sc))
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
