#!/usr/bin/env python3
"""W2 LOCK-1 decision brief (follow-on fo_lock1_decision_brief, trigger T_PIVOT_LOCK1_DECISION_BRIEF,
owner disposition od_hardware_pivot).

Builds, deterministically, from pinned repository inputs:

  lock1_decision_brief_v1.json   authoritative brief: D-01..D-15 (question, options, computed consequences,
                                 PROPOSED recommendation, dependencies), the pivot items P-01..P-04, the staged
                                 phases (Phase 1 sustainment knee on N2, Phase 2 three-arm common-condition
                                 comparison, Phase 3 absolute thrust demonstration), the ABSOLUTE THRUST GATE
                                 alongside R_arch, and the S1 qualification -> LOCK-2 procedure
  LOCK1_DECISION_BRIEF.md        human-readable rendering of the JSON
  LOCK1_DRAFT.json               DRAFT LOCK-1 file, status DRAFT_PENDING_OWNER_SIGNATURE (never locked)

Consequences of the D-xx options are the ones computed by the experiment-package builder
(docs/architecture_comparison/experiment_package/build_experiment_package.py) with the lane-25 tools
(docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py); this script re-runs that builder and
refuses to build unless it reproduces the pinned package byte for byte. New numbers (absolute-gate coverage
factors and uncertainty requirements, knee-bracket refinement, Phase-3 reading counts) are computed here with the
lane-25 statistics functions (t_one_sided, welch_satterthwaite, even_blocks).

Usage:  python docs/architecture_comparison/lock1/build_lock1_brief.py [--check]

Nothing here is decided or locked: every recommendation is PROPOSED; thresholds not in the RFP are PROPOSED; the
owner decides D-01..D-15 and P-01..P-04 and signs LOCK-1. Pure: not wired into archengine; no Julia; no Hall
closure; no screening candidate; no facility or supplier contact (owner's channel).
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REL_HERE = "docs/architecture_comparison/lock1"
SCRIPT_REF = f"{REL_HERE}/build_lock1_brief.py"
OUT_JSON = HERE / "lock1_decision_brief_v1.json"
OUT_MD = HERE / "LOCK1_DECISION_BRIEF.md"
OUT_DRAFT = HERE / "LOCK1_DRAFT.json"
BASE_COMMIT = "510e464fb8e128e4cf3325572a4d36ad33a4899d"
STATUS = "DRAFT_PENDING_OWNER_SIGNATURE"
REC = "PROPOSED"
SIG = 8
ARCHS = ("hall_only", "rf_hall", "ecr_hall")
DECISION_IDS = tuple(f"D-{i:02d}" for i in range(1, 16))

# key: (path, producer, sha256)
INPUTS = {
    "pivot": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json", "owner disposition od_hardware_pivot",
              "5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac"),
    "package": ("docs/architecture_comparison/experiment_package/experiment_package_v1.json",
                "fo_experiment_package", "9278dfffe43a37a2ea71c3215ce4a7eba022fa72e007ffa24f229371e1407e84"),
    "package_builder": ("docs/architecture_comparison/experiment_package/build_experiment_package.py",
                        "fo_experiment_package", "0de931c3288dfbf42ec94dff82ba280923d666ff93c7891c0cb89da3360add25"),
    "minexp_draft": ("docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json",
                     "lane_25_min_decisive_experiment",
                     "54b7b00a60134f2d92f2eb5c9fb49f18d23623a566e04a4b7d70325a0e332509"),
    "minexp_tools": ("docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py",
                     "lane_25_min_decisive_experiment",
                     "3ee68a28ddd98d25705a58e293944d89dc102b44caad7ac55b912e55fafd7f4b"),
    "protocol": ("docs/architecture_comparison/experiment_protocol/protocol_draft.json", "lane_06_experiment_protocol",
                 "287dd7ecd57087e46f2f3d786bfb2d64b01ac4fe29a29de21ef98b04c5ac96e3"),
    "hg_matrix": ("docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json", "lane_24_hard_gates",
                  "7d77d2831214f3f3d96c8254ea43643ada15e7d1ce0685dec86a65eb79a8f65f"),
    "hg_status": ("docs/architecture_comparison/hard_gates/hard_gate_status_v1.json", "lane_24_hard_gates",
                  "2c82b3277067b22c85eabd25539b18101f429e6d34ee698d2f5d6e183aa44527"),
    "p5n2_audit": ("hallthruster_bridge/identification/p5_n2_measurement_audit_findings_v1.json",
                   "physics track (P5-N2 measurement audit; read-only)",
                   "588ce98c26c8353a667ab0e57021034b7622a3d6f507d09d0d84e1fab98a1838"),
    "bundle1": ("docs/milestones/bundle1/bundle1_v4.json", "fo_bundle1 (Bundle 1 v4)",
                "7b1bac664b007529c1963db698492a3ff2dd3d5da0919c0276fa1fa010934d7c"),
    "constants": ("abep_sim/constants.py", "repository (RFP record as transcribed)",
                  "dd1c564324c139471bb361d27ef0f75b0f84de1878d100d4313aed12677f33d7"),
}

# parallel pivot workstreams (od_hardware_pivot.workstreams); referenced by follow-on id, never read or required
WORKSTREAMS = {
    "W1": "fo_feed_state_closure", "W3": "fo_hardware_definition", "W4": "fo_instrumentation_definition",
    "W5": "fo_hall_validation_prereg_draft", "W7": "fo_o_o2_chemistry_v0", "DX5": "fo_closed_access_acquisition",
}

FORBIDDEN_PATTERNS = (r"\bwinner\s+is\b", r"\bis\s+the\s+winner\b", r"\bbest\s+architecture\b",
                      r"\bpreferred\s+architecture\s+is\b")


class InputChanged(RuntimeError):
    pass


# ------------------------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_inputs(root: Path = ROOT, pins: dict = INPUTS) -> dict:
    out, bad = {}, []
    for key, (rel, _lane, sha) in pins.items():
        p = root / rel
        if not p.is_file():
            bad.append(f"{rel}: missing")
            continue
        got = sha256_file(p)
        if got != sha:
            bad.append(f"{rel}: sha256 {got[:16]} != pinned {sha[:16]}")
        out[key] = p
    if bad:
        raise InputChanged("pinned inputs changed or missing (re-pin deliberately and log it):\n  " + "\n  ".join(bad))
    return out


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _r(x):
    if isinstance(x, float):
        if math.isinf(x):
            return x
        return float(f"{x:.{SIG}g}")
    return x


def N(value, unit: str, evidence_class: str, source: str, note: str | None = None) -> dict:
    if isinstance(value, float) and math.isinf(value):
        raise ValueError("infinite values are not stored; state them in words")
    o = {"value": _r(value), "unit": unit, "evidence_class": evidence_class, "source": source}
    if note:
        o["note"] = note
    return o


def TBD(what: str, requires: str, blocked_by: list[str]) -> dict:
    return {"value": f"TBD - requires {requires}", "what": what, "blocked_by": blocked_by}


def comp(expr: str) -> str:
    return f"computed: {SCRIPT_REF}: {expr}"


def ptr(key: str, pointer: str) -> str:
    return f"{INPUTS[key][0]}#{pointer}"


def get_ptr(doc, pointer: str):
    cur = doc
    for part in pointer.strip("/").split("/"):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def lane25_threshold(draft: dict, tid: str) -> tuple[int, dict]:
    for i, t in enumerate(draft["thresholds"]):
        if t["id"] == tid:
            return i, t
    raise KeyError(f"lane-25 threshold {tid} not found")


def rfp_values(root: Path) -> dict:
    """RFP values as transcribed in abep_sim/constants.py (lane-24 status RFP_AS_RECORDED; verify against the RFP)."""
    mod = load_module(root / INPUTS["constants"][0], "_lock1_constants")
    rfp = mod.RFPConstraints()
    src = ("RFP DTDF/06/13516/DSP/ABEP/X/L/M/01 Part III Para 2 as transcribed in abep_sim/constants.py "
           "RFPConstraints.{}; lane-24 threshold_status RFP_AS_RECORDED - verify against the RFP document")
    return {"thrust_min": N(rfp.thrust_min_mN, "mN", "assumed", src.format("thrust_min_mN")),
            "thrust_max": N(rfp.thrust_max_mN, "mN", "assumed", src.format("thrust_max_mN")),
            "power_max": N(rfp.power_max_W, "W", "assumed", src.format("power_max_W"))}


# ------------------------------------------------------------------------------------------------------------------
# experiment package (re-run its own builder; it must reproduce the pinned JSON)
# ------------------------------------------------------------------------------------------------------------------
def load_package(paths: dict) -> dict:
    builder = load_module(paths["package_builder"], "_lock1_exppkg_builder")
    rebuilt = builder.dumps(builder.build())
    pinned = paths["package"].read_text(encoding="utf-8")
    if rebuilt != pinned:
        raise InputChanged("the experiment package does not reproduce with its own builder (lane-25 tools); "
                           "the consequences relayed by this brief would not be the computed ones")
    return json.loads(pinned)


# ------------------------------------------------------------------------------------------------------------------
# new computations (lane-25 statistics functions)
# ------------------------------------------------------------------------------------------------------------------
ALPHA_ABS = 0.05          # PROPOSED (P-02); mirrors lane-25 T-ALPHA-SCREEN (one-sided 0.05)
MARGINS = (0.05, 0.10, 0.20)   # PROPOSED planning grid for the absolute-gate uncertainty requirement (P-02)
M_REQ = 0.05              # PROPOSED resolution margin (P-02-A)
BRACKET_RATIOS = (2, 4, 8, 16)  # planning grid: knee-bracket width / min_flow_step (both TBD until S1a/W1)
PHASE3_ARMS = (1, 2, 3)


def absolute_gate_numbers(mx, draft: dict, pkg: dict, rfp: dict, audit: dict) -> dict:
    n_min = int(mx.threshold(draft, "T-N-MIN"))
    n_max = int(mx.threshold(draft, "T-N-MAX"))
    ns = mx.even_blocks(n_min, n_max)
    i_nmin, _ = lane25_threshold(draft, "T-N-MIN")
    i_nmax, _ = lane25_threshold(draft, "T-N-MAX")
    nsrc = (f"{ptr('minexp_draft', f'/thresholds/{i_nmin}')} and /thresholds/{i_nmax} (T-N-MIN, T-N-MAX, PROPOSED) "
            "via minexp_numbers.even_blocks")
    Tf, Tc, Pm = rfp["thrust_min"]["value"], rfp["thrust_max"]["value"], rfp["power_max"]["value"]
    alpha = N(ALPHA_ABS, "-", "assumed",
              "lock1 brief proposal P-02 (not in the RFP); same one-sided level as lane-25 T-ALPHA-SCREEN "
              f"({ptr('minexp_draft', '/thresholds/2')})")
    k1 = {}
    for n in ns:
        k1[f"nu={n - 1} (Type A only, n={n})"] = (n - 1, mx.t_one_sided(ALPHA_ABS, float(n - 1)))
    k1["nu=inf (Type B dominated)"] = (math.inf, mx.t_one_sided(ALPHA_ABS, math.inf))
    k1_objs = {lab: N(v, "-", "model-derived",
                      comp(f"minexp_numbers.t_one_sided(alpha_abs = {ALPHA_ABS}, nu = {nu})"))
               for lab, (nu, v) in k1.items()}

    def req_table(ref: float, sign: int, unit_abs: str, label: str) -> dict:
        rows = {}
        for m in MARGINS:
            row = {}
            for lab, (_nu, k) in k1.items():
                true = ref * (1 + sign * m)
                u_abs = abs(true - ref) / k
                row[lab] = {
                    "u_c_max_abs": N(u_abs, unit_abs, "model-derived",
                                     comp(f"u_c,max = |{label}_true - {label}_limit| / k1; {label}_true = "
                                          f"limit x (1 {'+' if sign > 0 else '-'} {m})")),
                    "u_c_max_rel": N(u_abs / true, "relative to the true value (1 sigma, combined)",
                                     "model-derived", comp(f"u_c,max / {label}_true, margin {m}"))}
            rows[f"margin={m}"] = row
        return rows

    floor = req_table(Tf, +1, "mN", "T")
    power = req_table(Pm, -1, "W", "P_bus")
    cap25 = req_table(Tc, +1, "mN", "T")

    # Type B thrust-scale allowance left after the lane-25 per-reading Type A target (D-01-A planning targets)
    d01a = next(o for o in pkg["decisions"][0]["options"] if o["id"] == "D-01-A")
    scale_allow = {}
    for n in ns:
        uT = d01a["consequences"]["statistics_and_targets"][str(n)]["u_T_max"]["value"]
        _nu, k = k1[f"nu={n - 1} (Type A only, n={n})"]
        u_rel = M_REQ / ((1 + M_REQ) * k)
        rem = u_rel ** 2 - uT ** 2 / n
        scale_allow[str(n)] = {
            "u_T_reading_max_lane25": N(uT, "relative (1 sigma, per reading)", "model-derived",
                                        f"{ptr('package', '/decisions/0/options/0/consequences/statistics_and_targets')}"
                                        f"/{n}/u_T_max (experiment package, D-01-A)"),
            "u_c_rel_max_floor": N(u_rel, "relative (1 sigma, combined)", "model-derived",
                                   comp(f"margin {M_REQ} / ((1 + {M_REQ}) k1), k1 at nu = {n - 1} (conservative)")),
            "u_Tscale_max": N(math.sqrt(rem), "relative (1 sigma, Type B thrust-stand scale)", "model-derived",
                              comp("sqrt(u_c,rel,max^2 - u_T,reading,max^2 / n)"))
            if rem > 0 else {"value": "none: the Type A target alone exhausts the budget"}}

    sigma_lit = get_ptr(audit, "/admissible_targets/thrust/sigma_mN")
    k_inf = k1["nu=inf (Type B dominated)"][1]
    lit = {
        "sigma_T_P5_N2": N(sigma_lit, "mN", "measured",
                           ptr("p5n2_audit", "/admissible_targets/thrust/sigma_mN") +
                           " (P5 on N2, published stand measurement, evidence level 3; context only, not a "
                           "requirement and not Vyovrinda hardware)"),
        "T_true_min_demonstrable_at_that_sigma": N(Tf + k_inf * sigma_lit, "mN", "model-derived",
                                                   comp("T_floor + k1(nu=inf) x sigma_T_P5_N2")),
    }
    return {"alpha_abs": alpha, "k1": k1_objs, "floor_requirement": floor, "power_requirement": power,
            "capability_25_requirement": cap25, "thrust_scale_allowance_at_margin_0.05": scale_allow,
            "literature_context": lit, "n_grid_source": nsrc, "ns": ns}


def knee_numbers(mx, draft: dict, pkg: dict) -> dict:
    i, t = lane25_threshold(draft, "T-KNEE-LEVELS")
    L = int(t["value"])
    coarse = pkg["decisions"][7]["options"][0]["consequences"]["knee_scan_readings"]
    ref = {
        "levels": N(L, "levels", "assumed", f"{ptr('minexp_draft', f'/thresholds/{i}')} (T-KNEE-LEVELS, PROPOSED)"),
        "coarse_spacing": N(1.0 / (L - 1), "fraction of (mdot_nom - mdot_min)", "model-derived",
                            comp("1 / (T-KNEE-LEVELS - 1): equally spaced levels (lane-25 knee_scan.levels)")),
        "coarse_scan_readings": copy.deepcopy(coarse),
    }
    steps = {}
    for r in BRACKET_RATIOS:
        s = math.ceil(math.log2(r))
        steps[f"bracket/min_flow_step={r}"] = {
            "bisection_steps": N(s, "steps", "model-derived", comp(f"ceil(log2({r}))")),
            "added_readings": N(2 * s, "readings (Hall-only, N2)", "model-derived",
                                comp(f"2 readings per step (down-approach and up-approach, P-01) x {s} steps")),
        }
    return {"coarse": ref, "refinement_by_bracket_ratio": steps,
            "note": "bracket width = coarse_spacing x (mdot_nom - mdot_min); mdot_min, mdot_nom TBD - require the "
                    "W1 valve-outlet test points (fo_feed_state_closure / IF-A5); min_flow_step TBD - requires MFC "
                    "resolution (S1a, lane-06 min_flow_step)"}


def phase3_counts(ns: list[int]) -> dict:
    points = {
        "3 (180/200/230 km, one atmosphere state)": (3, "owner disposition W1 altitudes "
                                                     f"({ptr('pivot', '/workstreams/W1_feed_state_closure')})"),
        "9 (180/200/230 km x low/mean/high)": (9, "W1 altitudes x lane-24 OD3 PROPOSED atmosphere states "
                                               f"({ptr('hg_matrix', '/open_owner_decisions/2')})"),
    }
    out = {}
    for lab, (np_, src) in points.items():
        row = {"points": N(np_, "feed-state test points", "assumed", src)}
        for a in PHASE3_ARMS:
            for n in ns:
                row[f"arms={a},n={n}"] = N(np_ * a * n, "Hall-on absolute readings (excl. stand zero/calibration)",
                                           "model-derived", comp(f"points {np_} x arms {a} x visits n {n}"))
        out[lab] = row
    return out


# ------------------------------------------------------------------------------------------------------------------
# decisions D-01..D-15: question, options (package + pivot), consequences, PROPOSED recommendation, dependencies
# ------------------------------------------------------------------------------------------------------------------
QUESTIONS = {
    "D-01": "How is the planning uncertainty budget of ln R_arch split over the variance groups G1-G5 (it sets the "
            "instrument and mount specifications, not any classification)?",
    "D-02": "Does an arm stop (D3) when the simultaneous upper bound of ln R_arch is below 0 (sign form) or below "
            "-delta (STOP-MARGIN)?",
    "D-03": "Must a stop taken from the confirmation subset rest on Hall-on data at P_lo as well as P_hi?",
    "D-04": "Is the iso-power chord error u_interp a pre-registered Type B bound or measured with a V_mid reading?",
    "D-05": "Where do the signed LOCK-1 and LOCK-2 files live?",
    "D-06": "How are the three configurations HW-0 / HW-RF / HW-ECR realised on H-1 and C-1 (spacer + re-mounts, "
            "in-vacuum diverter, both applicators installed, or separate builds with shams)?",
    "D-07": "What equivalence / decision margin delta on ln R_arch is locked?",
    "D-08": "Which block counts n are admissible (n itself is computed at LOCK-2 by readiness_n from S1)?",
    "D-09": "Is the tested Hall unit H-1 the Vyovrinda design (evidence level 1) or a surrogate (level 3)?",
    "D-10": "Is a single protocol basis (lane 25 + lane 06 reconciliation) adopted for boundary, classes, "
            "multiplicity, extinction, ordering and controls?",
    "D-11": "How are the unmeasured common loads (compressor bus draw, valve-outlet feed state) handled until the "
            "upstream ICD and the W1 feed closure supply them?",
    "D-12": "Which facility requirements apply per stage, what is T-PB-MAX, and how many elevated background-pressure "
            "levels are classified?",
    "D-13": "Are ignition / start attempts measured (per arm; xenon-assisted and air-only)?",
    "D-14": "Does the physics track pre-register part of the new measurements as held-out Hall-transport validation "
            "evidence before any data?",
    "D-15": "Which scope extensions outside the minimum are added (Xe health check; Xe-augmented peak points)?",
}

DEPENDS = {
    "D-01": ["D-06 (a no-vent switch removes G5 and re-allocates the shares: D-01-B)",
             "S1b values (D0 uses the measured components, never the shares)"],
    "D-02": ["D-07 (delta)", "D-03 (what the confirmation subset contains)"],
    "D-03": ["D-02 (stop form)", "lane-25 T-PLO-FRACTION (P_lo definition)"],
    "D-04": ["V_nom, V_hi (TBD - require the Vyovrinda Hall design point, lane-17 hall_reference, and the bus "
             "allocation)"],
    "D-05": ["D-10 (one protocol basis -> one lock location)"],
    "D-06": [f"W3 {WORKSTREAMS['W3']}: feasibility of the flow-equivalent spacer and of removable RF/ECR modules "
             "on one H-1 / C-1 with one magnetic circuit", "D-01 (G5 share)"],
    "D-07": ["S1 repeatability through D0 (widening delta after S1 is a LOCK-1 restart)"],
    "D-08": ["D0 readiness_n with S1 values"],
    "D-09": ["existence and schedule of the Vyovrinda H-1 design point (lane-17 hall_reference DI-2; W3 "
             f"{WORKSTREAMS['W3']})", "lane-24 evidence policy OD11 (verdict-bearing bases)"],
    "D-10": ["lane 06 and lane 25 drafts (both pinned)"],
    "D-11": ["lane_33_upstream_icd compressor bus power (V1 basis)",
             f"W1 {WORKSTREAMS['W1']} valve-outlet test points {{mdot_s, P_feed, T_feed, x_s}}"],
    "D-12": ["facility specification (owner's channel; no facility is named or contacted by the team)",
             f"W1 {WORKSTREAMS['W1']} total grid flow (sets S_eff = Q/p_b)",
             "OD1 reading of '12-25 mN' (thrust-stand range for the 25 mN condition)"],
    "D-13": ["owner start-cycle target (ignition_p_min, attempts)", "lane-24 OD5 / OD14 (air-only start)",
             "cathode lanes (air-only start admissibility)"],
    "D-14": [f"W5 {WORKSTREAMS['W5']} (the physics-track pre-registration itself, filed before S1)"],
    "D-15": ["lane-24 OD1 (reading (ii) needs Xe-augmented peak capability)", "Xe anode feed line (W3)"],
}

PHASES_AFFECTED = {
    "D-01": ["S1", "LOCK-2", "Phase 2"], "D-02": ["Phase 2"], "D-03": ["Phase 2"], "D-04": ["Phase 2"],
    "D-05": ["LOCK-1", "LOCK-2"], "D-06": ["S1", "Phase 1", "Phase 2", "Phase 3"], "D-07": ["LOCK-2", "Phase 2"],
    "D-08": ["LOCK-2", "Phase 2", "Phase 3"], "D-09": ["Phase 1", "Phase 2", "Phase 3"],
    "D-10": ["all"], "D-11": ["Phase 2", "Phase 3"], "D-12": ["S1", "Phase 1", "Phase 2", "Phase 3"],
    "D-13": ["Phase 1", "Phase 2", "Phase 3"], "D-14": ["S1 (filed before)", "Phase 1", "Phase 2", "Phase 3"],
    "D-15": ["Phase 2", "Phase 3"],
}


def pivot_consequences(did: str, g: dict) -> dict:
    """Consequences the od_hardware_pivot adds to each option (per option id), and new pivot options."""
    k_inf = g["k1"]["nu=inf (Type B dominated)"]["value"]
    pc: dict[str, list[str]] = {}
    new_opts: list[dict] = []
    if did == "D-01":
        txt = ("R_arch only: a thrust-stand scale error common to both arms cancels in ln R_arch (minexp_numbers."
               "sigma_lnR has no thrust-scale term), but it does not cancel in the ABSOLUTE thrust gate; the "
               "absolute gate therefore adds its own Type B thrust-scale requirement (absolute_thrust_gate."
               "uncertainty_requirement), independent of this allocation")
        pc = {o: [txt] for o in ("D-01-A", "D-01-B", "D-01-C")}
    elif did == "D-02":
        txt = ("a D3 stop ends the arm's remaining Phase-2 rows only; it is not an elimination and does not remove "
               "the arm from Phase 3 under P-03-A (absolute feasibility is a separate owner decision)")
        pc = {o: [txt] for o in ("D-02-A", "D-02-B")}
    elif did == "D-03":
        pc = {"D-03-B": ["Phase 2 is centred on the Phase-1 knee: P_lo data at OP1-OP3 give the source-power "
                         "dependence on both sides of the knee for any stopped arm"],
              "D-03-A": ["a stopped arm's P_lo behaviour around the knee stays NOT_TESTED"]}
    elif did == "D-05":
        new_opts.append({"id": "D-05-D", "label": "docs/architecture_comparison/lock1/ (this workstream's "
                         "directory; holds the DRAFT only)", "origin": "lock1_brief (pivot)",
                         "consequences": {"governance": "keeps the draft and the signed lock together; lane 06 "
                                          "and lane 25 then need pointers; separates the lock from the single "
                                          "protocol basis adopted under D-10-A"}})
        pc = {"D-05-A": ["the signed LOCK-1 records the sha256 of this brief and of LOCK1_DRAFT.json as its "
                         "decision source"]}
    elif did == "D-06":
        pc = {"D-06-A": ["consistent with the pivot statement: one H-1, one C-1, the same magnetic circuit, only the "
                         "pre-ionizer module changes (HW-0 = flow-equivalent spacer)"],
              "D-06-B": ["consistent with the pivot statement if the diverter keeps the magnetic circuit and feed "
                         "path identical; feasibility is a W3 question"],
              "D-06-C": ["conflicts with 'same magnetic circuit' for the hall_only reference while an ECR permanent "
                         "magnet is installed (lane 25 Sec. 2); would need an HW-0 anchor"],
              "D-06-D": ["separate builds of the same H-1 / C-1 with shams; replicate builds play the S1b role"]}
    elif did == "D-07":
        txt = ("delta applies to R_arch only; the absolute gate uses the RFP limits (12 mN, 25 mN, 1500 W) with its "
               "own one-sided confidence bound (P-02), so delta does not move the absolute outcome")
        pc = {o: [txt] for o in ("D-07-A", "D-07-B")}
    elif did == "D-08":
        pc = {"D-08-A": ["PROPOSED for Phase 3: the same n (from LOCK-2) visits per absolute test point, each visit "
                         "separated by a shutdown and restart; reading counts in phases.phase_3.reading_counts"]}
    elif did == "D-09":
        new_opts.append({"id": "D-09-C", "label": "Vyovrinda H-1 for every score-bearing phase, plus a surrogate "
                         "Hall unit for a disclosed, non-score-bearing procedure pilot (lane-06 PR-2 form)",
                         "origin": "lock1_brief (pivot)",
                         "consequences": {"hard_gate_basis": "as D-09-A for all score-bearing data",
                                          "schedule": "lets S1-style instrument and knee-procedure shakedown start "
                                                      "before the Vyovrinda H-1 exists; pilot data never enter any "
                                                      "decision analysis or LOCK-2 value",
                                          "cost": "a second Hall unit and its mount; counts TBD - requires W3"}})
        pc = {"D-09-A": ["the absolute thrust gate can be registered as lane-24 G1/G2 evidence only on basis "
                         "measurement_vyovrinda (or measurement_same_hardware): lane-24 pass_sufficient_bases"],
              "D-09-B": ["Phase 3 gives no gate-bearing absolute result: measurement_similar_hardware is not a "
                         "pass-sufficient basis for G1.thrust_floor or G2.bus_power_max"]}
    elif did == "D-11":
        txt = ("absolute gate: loads are non-negative, so P_bus on the PARTIAL basis (no compressor) is a lower "
               "bound of the V1 P_bus; P_bus,PARTIAL < 1500 W is necessary but not sufficient -> outcome "
               "ABS_NECESSARY_ONLY_PARTIAL_BOUNDARY until the ICD compressor draw exists")
        pc = {"D-11-A": [txt], "D-11-B": ["would fill the compressor draw before lane 33 is verified (not allowed)"]}
    elif did == "D-12":
        pc = {"D-12-A": ["Phase 3: the absolute gate uses the smaller of the base-p_b and elevated-p_b lower bounds "
                         "where S5 exists at that point (P-02)"],
              "D-12-B": ["as D-12-A with two elevated levels"]}
    elif did == "D-13":
        pc = {"D-13-B": ["gives startup-mode data that G2.bus_power_max PASS needs (every mode) and G6.ignition; "
                         "attempt counts for zero-failure demonstration are in the package consequences"]}
    elif did == "D-14":
        pc = {"D-14-B": ["consistent with od_hardware_pivot ('part of the new measurements are pre-registered, "
                         "before any data, as held-out Hall-transport validation evidence'); the pre-registration "
                         f"itself is W5 ({WORKSTREAMS['W5']}); P5-N2 v1 stays INCONCLUSIVE"],
              "D-14-A": ["conflicts with the owner's pivot statement unless the owner revises it"]}
    elif did == "D-15":
        new_opts.append({"id": "D-15-C", "label": "D-15-B plus Phase-3 Xe-augmented peak-capability points, only if "
                         "the owner adopts OD1 reading (ii)", "origin": "lock1_brief (pivot)",
                         "consequences": {"evidence": "the only way the 25 mN capability condition under OD1 "
                                          "reading (ii) (G1.peak_capability_25mN) is measured; under reading (i) it "
                                          "reduces to D-15-B", "hardware": "Xe anode feed line (as D-15-B)",
                                          "readings": "one Xe-augmented peak condition per Phase-3 point and arm, n "
                                          "visits; counts scale as phases.phase_3.reading_counts"}})
        pc = {"D-15-B": ["the 25 mN condition under OD1 reading (ii) stays unmeasured"]}
    return {"per_option": pc, "new_options": new_opts, "_k_inf": k_inf}


RECS = {  # PROPOSED recommendation and rationale; None -> keep the package recommendation unchanged
    "D-09": None, "D-05": None,
    "D-15": ("D-15-C", "The pivot names the registered 25 mN capability condition as part of Phase 3; under OD1 "
             "reading (ii) that needs Xe augmentation, which D-15-B does not provide. D-15-C reduces to D-15-B "
             "under reading (i), so it adds readings only if the owner adopts reading (ii)."),
}


def facility_by_stage(pkg: dict) -> dict:
    """D-12: requirements per stage only (no facility named or contacted; the owner's channel)."""
    req = {r["id"]: i for i, r in enumerate(pkg["requirements"])}

    def refs(*ids):
        return [ptr("package", f"/requirements/{req[i]}") + f" ({i})" for i in ids]
    fs = "/facility_split/stages/"
    return {
        "rule": "requirements only; which facility serves which stage, and any contact with a facility or supplier, "
                "is the owner's channel",
        "stages": [
            {"stage": "S1a (no plasma)", "lane25": [ptr("minexp_draft", fs + "S1a_no_plasma")],
             "requirements": refs("REQ-HW-01", "REQ-HW-02", "REQ-HW-03", "REQ-HW-06", "REQ-HW-07")},
            {"stage": "S1b + Phase 1 + Phase 2 Hall-on (S2, S4, S5, S6)",
             "lane25": [ptr("minexp_draft", fs + "S1b_hall_on"), ptr("minexp_draft", fs + "S2_S4_S5_hall_on")],
             "requirements": refs("REQ-FAC-01", "REQ-FAC-02", "REQ-FAC-03", "REQ-FAC-04", "REQ-FAC-05",
                                  "REQ-HW-01", "REQ-HW-02", "REQ-HW-04")},
            {"stage": "Phase 2 source bench (S3, Hall off)", "lane25": [ptr("minexp_draft", fs + "S3_source_bench")],
             "requirements": refs("REQ-HW-03", "REQ-HW-05")},
            {"stage": "Phase 3 (absolute demonstration)",
             "lane25": ["none (stage introduced by od_hardware_pivot)"],
             "requirements": refs("REQ-FAC-01", "REQ-FAC-03", "REQ-FAC-04", "REQ-HW-01", "REQ-HW-02"),
             "additional_PROPOSED": [
                 "the same facility, stand and mount procedure as Phase 2, so that the S1a thrust-scale calibration "
                 "(u_Tscale) and the S1b repeatability apply to Phase 3",
                 "REQ-FAC-01 evaluated at the largest Phase-3 total flow (W1 test points)",
                 "thrust-stand range covering the Phase-3 thrusts including the 25 mN condition: TBD - requires the "
                 "Vyovrinda Hall design point and P-04",
                 "Xe anode feed line and Xe-compatible pumping if D-15-C / P-04-ii"]},
        ],
    }


def lock1_inputs() -> list[dict]:
    return [
        TBD("mdot_min, mdot_nom, composition (air-surrogate O2 fraction)", "W1 valve-outlet test points (IF-A5)",
            [WORKSTREAMS["W1"], "lane_16_feed_envelope"]),
        TBD("V_nom, V_hi", "the Vyovrinda Hall design point (lane-17 hall_reference DI-2) and the bus allocation",
            ["lane_17_hall_reference", WORKSTREAMS["W3"], "lane_11_bus_boundary"]),
        TBD("P_hi per source arm; f_src and w_c allocations", "the source allocation in bus_power_boundary_v1",
            ["owner", "lane_11_bus_boundary"]),
        TBD("ledger inputs with evidence classes and T-LEDGER-SENSITIVITY bounds", "an owner decision at LOCK-1",
            ["owner", "lane_11_bus_boundary"]),
        TBD("compressor bus draw per operating point (V1 basis)", "upstream ICD compressor bus power",
            ["lane_33_upstream_icd"]),
        TBD("T-PB-MAX", "the facility specification (owner's channel) and an owner decision", ["owner"]),
        TBD("DUMMY_LOAD_PICKUP acceptance level", "an owner decision at LOCK-1", ["owner"]),
        TBD("hardware protection limits for scans (P1-S2)", "the H-1 / C-1 hardware definition", [WORKSTREAMS["W3"]]),
        TBD("instrument list and uncertainty budget", "the W4 instrumentation definition", [WORKSTREAMS["W4"]]),
        TBD("seed and configuration-order draw", "owner signature (drawn and published at LOCK-1)", ["owner"]),
        TBD("frozen analysis script sha256", "the frozen analysis script implementing lane-25 Sec. 6 and 9 and the "
            "absolute gate", ["owner"]),
        TBD("physics-track pre-registration (held-out validation measurements)", "W5, filed before S1",
            [WORKSTREAMS["W5"]]),
    ]


def decisions(pkg: dict, g: dict) -> list[dict]:
    out = []
    ids = [d["id"] for d in pkg["decisions"]]
    if tuple(ids) != DECISION_IDS:
        raise InputChanged(f"experiment package decisions are {ids}, expected D-01..D-15")
    for i, d in enumerate(pkg["decisions"]):
        did = d["id"]
        pv = pivot_consequences(did, g)
        opts = []
        for j, o in enumerate(d["options"]):
            cons = {k: copy.deepcopy(v) for k, v in o.items() if k not in ("id", "label")}
            opts.append({"id": o["id"], "label": o["label"], "origin": "experiment_package",
                         "consequences_source": ptr("package", f"/decisions/{i}/options/{j}"),
                         "consequences": cons,
                         "pivot_consequences": pv["per_option"].get(o["id"], [])})
        for no in pv["new_options"]:
            opts.append({**no, "consequences_source": comp(f"pivot option of {did}"), "pivot_consequences": []})
        extras = {k: copy.deepcopy(v) for k, v in d.items()
                  if k not in ("id", "title", "source", "status", "options", "recommendation")}
        prec = d["recommendation"]
        if RECS.get(did):
            opt, why = RECS[did]
            changed = True
        else:
            opt, why = prec["option"], prec["rationale"]
            changed = False
            if did == "D-09":
                why += (" Under the pivot this is stronger: the absolute thrust gate is gate-bearing only on "
                        "Vyovrinda (or same-hardware) data; D-09-C is compatible if the owner wants an early "
                        "surrogate procedure pilot.")
            if did == "D-05":
                why += " The DRAFT lives in docs/architecture_comparison/lock1/ until signature."
        out.append({
            "id": did, "title": d["title"], "question": QUESTIONS[did], "status": "OPEN_OWNER_DECISION",
            "package_source": ptr("package", f"/decisions/{i}"),
            "lane_sources": d["source"],
            "options": opts,
            "package_context": extras,
            "package_recommendation": {"option": prec["option"], "status": prec["status"],
                                       "rationale": prec["rationale"]},
            "recommendation": {"status": REC, "option": opt, "rationale": why,
                               "changed_from_package": changed},
            "depends_on": DEPENDS[did],
            "phases_affected": PHASES_AFFECTED[did],
            "owner_choice": None,
        })
        if did == "D-12":
            out[-1]["facility_by_stage"] = facility_by_stage(pkg)
    return out


# ------------------------------------------------------------------------------------------------------------------
# pivot items P-01..P-04
# ------------------------------------------------------------------------------------------------------------------
def pivot_items(kn: dict, g: dict) -> list[dict]:
    return [
        {"id": "P-01", "title": "Phase-1 knee location: coarse scan only, or coarse scan plus bracket refinement; "
                                "meaning of 'sustained in both directions'",
         "status": "OPEN_OWNER_DECISION",
         "options": [
             {"id": "P-01-A", "label": "lane-25 coarse scan only (T-KNEE-LEVELS levels, down then up)",
              "consequences": {"resolution": "knee located to one coarse spacing (knee_numbers.coarse.coarse_spacing)",
                               "readings": copy.deepcopy(kn["coarse"]["coarse_scan_readings"])}},
             {"id": "P-01-B", "label": "coarse scan, then bisection of the bracket [lowest level sustained both "
                                       "ways, next lower level] down to min_flow_step; each probe approached from "
                                       "above (discharge on) and from below (re-ignition at the next lower "
                                       "unsustained level, counted as a D-13 attempt if D-13-B)",
              "consequences": {"added_readings": copy.deepcopy(kn["refinement_by_bracket_ratio"]),
                               "score_bearing": "sustainment classes only (Hall-only); no R_arch row changes; "
                                                "the paired / randomised Phase-2 design is unchanged"}},
         ],
         "recommendation": {"status": REC, "option": "P-01-B",
                            "rationale": "OP2 is defined by the knee; a quarter-interval bracket leaves the break-"
                                         "even location coarse, while the refinement costs at most a few Hall-only "
                                         "readings (computed) and touches no paired row. The approach-from-below "
                                         "rule makes 'both directions' operational."},
         "depends_on": ["min_flow_step (S1a MFC resolution, lane-06)", "W1 mdot_min, mdot_nom"],
         "owner_choice": None},
        {"id": "P-02", "title": "Absolute thrust gate: confidence level, uncertainty requirement, facility "
                                "treatment",
         "status": "OPEN_OWNER_DECISION",
         "options": [
             {"id": "P-02-A", "label": f"one-sided alpha_abs = {ALPHA_ABS}; requirement: a true value {M_REQ:.0%} "
                                       "beyond each limit must be demonstrable; base/elevated p_b: smaller lower "
                                       "bound governs",
              "consequences": {"uncertainty_requirement": "absolute_thrust_gate.uncertainty_requirement at margin "
                                                          f"{M_REQ}", "thrust_scale_allowance":
                               copy.deepcopy(g["thrust_scale_allowance_at_margin_0.05"])}},
             {"id": "P-02-B", "label": f"as P-02-A with a {MARGINS[1]:.0%} requirement margin",
              "consequences": {"uncertainty_requirement": "absolute_thrust_gate.uncertainty_requirement at margin "
                                                          f"{MARGINS[1]} (looser instruments; true thrust between "
                                                          "12 and 13.2 mN is then likely UNRESOLVED)"}},
             {"id": "P-02-C", "label": "point estimate against the limit (no confidence bound)",
              "consequences": {"compliance": "not consistent with lane-24 G1/G2, whose PASS needs lower/upper "
                                             "bounds, not point estimates"}},
         ],
         "recommendation": {"status": REC, "option": "P-02-A",
                            "rationale": "Bounds (not point estimates) are what lane-24 G1/G2 accept. A 5 % "
                                         "resolution margin leaves a Type B thrust-stand scale allowance of about "
                                         "2-2.5 % after the lane-25 Type A target (computed); whether the stand "
                                         "achieves it is TBD - requires S1a (D0-ABS record). A looser margin widens "
                                         "the band above 12 mN in which the outcome stays UNRESOLVED."},
         "depends_on": ["W4 instrumentation uncertainty budget (fo_instrumentation_definition)", "D-12"],
         "owner_choice": None},
        {"id": "P-03", "title": "Phase-3 scope: arms and feed-state test points",
         "status": "OPEN_OWNER_DECISION",
         "options": [
             {"id": "P-03-A", "label": "every arm not INFEASIBLE at every flow (G-SRC), at every W1 test point",
              "consequences": {"readings": "phases.phase_3.reading_counts (arms = 3 unless G-SRC stops an arm)"}},
             {"id": "P-03-B", "label": "only arms not stopped in Phase 2 (D3)",
              "consequences": {"risk": "couples the absolute decision to the discrimination decision, which the "
                                       "owner keeps separate; a stopped arm may still meet 12 mN"}},
             {"id": "P-03-C", "label": "hall_only only",
              "consequences": {"evidence": "absolute feasibility of rf_hall / ecr_hall stays unmeasured"}},
         ],
         "recommendation": {"status": REC, "option": "P-03-A",
                            "rationale": "Absolute feasibility and architecture discrimination are separate owner "
                                         "decisions; a D3 stop is experiment-internal, not an elimination."},
         "depends_on": [f"W1 {WORKSTREAMS['W1']} test points", "D-08 (n)", "D-02"],
         "owner_choice": None},
        {"id": "P-04", "title": "Which '25 mN' condition Phase 3 demonstrates (lane-24 OD1 reading of '12-25 mN')",
         "status": "OPEN_OWNER_DECISION",
         "options": [
             {"id": "P-04-i", "label": "reading (i): operating window, 25 mN as a cap (G1.thrust_ceiling): a "
                                       "sustained condition with T upper bound <= 25 mN at the point",
              "consequences": {"test": "one throttled condition per point and arm (lower V_d or flow within the "
                                       "feed envelope); no Xe"}},
             {"id": "P-04-ii", "label": "reading (ii): 12 mN sustained floor plus 25 mN peak capability with Xe "
                                        "(G1.peak_capability_25mN): T lower bound >= 25 mN with P_bus upper bound "
                                        "< 1500 W",
              "consequences": {"test": "Xe-augmented peak points (D-15-C)"}},
         ],
         "recommendation": {"status": REC, "option": None,
                            "rationale": "This is the owner's reading of the RFP (lane-24 OD1), not a design "
                                         "choice; the brief prepares both tests and does not recommend a reading."},
         "depends_on": ["RFP text (verify)", "lane-24 OD1"],
         "owner_choice": None},
    ]


# ------------------------------------------------------------------------------------------------------------------
# phases, absolute gate, S1 -> LOCK-2
# ------------------------------------------------------------------------------------------------------------------
def extinction_rule(protocol: dict) -> dict:
    thr = protocol["sustainment_and_extinction"]["extinction"]["threshold"]
    params = {}
    for j, p in enumerate(thr["parameters"]):
        src = ptr("protocol", f"/sustainment_and_extinction/extinction/threshold/parameters/{j}")
        if isinstance(p.get("value"), (int, float)):
            params[p["id"]] = N(p["value"], p["unit"], p["evidence_class"], src + " (PROPOSED)")
        else:
            params[p["id"]] = TBD(p["id"], p.get("tbd_requires", "S1"), ["S1b / Hall-only pilot"])
    return {"threshold_id": thr["threshold_id"], "status": thr["status"], "rule": thr["rule"],
            "parameters": params,
            "not_extinction": protocol["sustainment_and_extinction"]["extinction"]["not_extinction"],
            "source": ptr("protocol", "/sustainment_and_extinction/extinction"),
            "adopted_via": "D-10-A reconciliation: lane-06 THR-EXTINCTION is the operational definition inside "
                           "lane-25 T-SUSTAIN"}


def phases(draft: dict, protocol: dict, pkg: dict, kn: dict, g: dict) -> dict:
    i_sus, sus = lane25_threshold(draft, "T-SUSTAIN")
    i_fb, fb = lane25_threshold(draft, "T-OP2-FALLBACK")
    d08 = pkg["decisions"][7]["options"][0]["consequences"]
    return {
        "sequence": "resolve D-01..D-15 and P-01..P-04 -> LOCK-1 (owner signature) -> hardware and instrumentation "
                    "(W3, W4) -> S1 qualification -> D0 -> LOCK-2 (S1 values, n) -> Phase 1 -> Phase 2 -> Phase 3 "
                    "(od_hardware_pivot experiment path; no score-bearing reading before LOCK-2)",
        "mapping_to_lane25": {"S0": "LOCK-1", "S1a/S1b/D0": "S1 qualification", "S2/D1": "Phase 1",
                              "S3/D2, S4/D3, S5/D4, D5, S6/D6": "Phase 2", "(new)": "Phase 3"},
        "phase_1": {
            "name": "Hall-only sustainment knee on N2",
            "configuration": "HW-0 on H-1 / C-1, V_nom, N2; lane-25 S2 (rows R01-R06 of the run matrix)",
            "locate": ("coarse scan: T-KNEE-LEVELS equally spaced flows from mdot_nom down to mdot_min, then back "
                       "up (lane-25 knee_scan); knee = lowest level SUSTAINED in both directions (T-OP2-FALLBACK)"),
            "bracket": ("bracket = [knee level, next lower level that is not sustained in both directions]; under "
                        "P-01-B refined by bisection to min_flow_step; the reported knee is the bracket with both "
                        "ends measured, never an interpolated flow"),
            "knee_numbers": kn,
            "sustained": {"rule": sus["rule"], "source": ptr("minexp_draft", f"/thresholds/{i_sus}"),
                          "dwell": TBD("T-SUSTAIN dwell", "S1 thermal settling time (M12)", ["S1b"])},
            "extinction": extinction_rule(protocol),
            "fallback_rule": {"rule": fb["rule"], "source": ptr("minexp_draft", f"/thresholds/{i_fb}")},
            "stop_rules": [
                "P1-S1 facility: base p_b > T-PB-MAX at a level -> that level NOT_SCOREABLE_FACILITY; the bracket "
                "is reported with the level excluded",
                "P1-S2 hardware protection (limits TBD - require W3 hardware definition): scan aborted and reported; "
                "no score-bearing data after the abort",
                "P1-S3 no level sustained (incl. mdot_nom): mdot_knee = mdot_nom (T-OP2-FALLBACK); Phase 2 runs as "
                "an enablement test (ENABLES / NEITHER_SUSTAINED); D5 EXPERIMENT_MOOT is evaluated after Phase 2",
                "P1-S4 every level sustained: knee not bracketed inside [mdot_min, mdot_nom] -> reported as "
                "'knee below mdot_min (censored)', mdot_knee = midpoint (T-OP2-FALLBACK); no extension below "
                "mdot_min (outside the delivered feed envelope)",
                "P1-S5 hysteresis: a level sustained on the down-approach only counts as not sustained for the knee "
                "(both directions required); the hysteresis width is reported",
            ],
            "outputs": ["mdot_knee and its bracket", "per-level SUSTAINED flags both directions", "I_d traces",
                        "thrust where sustained", "B(z) at the actual coil currents (W5 evidence if pre-registered)"],
            "score_bearing": "sustainment classes (Hall-only); fixes OP2 for Phase 2",
        },
        "phase_2": {
            "name": "common-condition three-arm comparison around the knee",
            "content": "lane-25 S3 (source bench, Hall off), S4 (paired Hall-on, randomised), S5 (elevated p_b), "
                       "S6 (HW-0 re-installation check) at OP1 (mdot_min), OP2 (mdot_knee), OP3 (mdot_nom), "
                       "OP2H/OP3H (iso-power, Hall-only), OP5 (air surrogate at mdot_knee, last in each block)",
            "paired_randomised_structure": [
                "HW-0 first (S2) and last (S6); a seeded coin published at LOCK-1 orders HW-RF and HW-ECR between them",
                "within a block the operating-point order is a seeded permutation re-drawn per block; OP5 (oxygen-"
                "bearing) last in every block (D-10-A)",
                "every source-arm visit bracketed: off, lo, hi, off (or off, hi, off): installed-off reference and "
                "drift bracket",
                "even n between T-N-MIN and T-N-MAX, fixed at LOCK-2 by readiness_n; alternating source-level order "
                "cancels linear drift over block pairs",
                "each block an independent start (shutdown and restart between consecutive visits of a point; "
                "lane-06 replication definition, D-10-A)"],
            "decisive_metric": "R_arch = (T/P_bus)_{rf_hall|ecr_hall} / (T/P_bus)_{hall_only} on bus_power_boundary_v1 "
                               "(PARTIAL_BOUNDARY label until the ICD compressor draw exists, D-11)",
            "stop_rules": ["G-SRC: source cannot sustain within P_hi at a flow -> INFEASIBLE_AT_POINT; at every flow "
                           "-> arm STOPPED", "D2 screen -> STOP_CANDIDATE -> confirmation subset (D-03)",
                           "D3 stop rule (form per D-02)", "D4 facility robustness (D-12)",
                           "D5 EXPERIMENT_MOOT", "D6 re-installation check"],
            "reading_counts_source": ptr("package", "/decisions/7/options/0/consequences"),
            "reading_counts": copy.deepcopy(d08),
            "score_bearing": "R_arch size classes, sustainment classes, R_iso, y, kappa, C*, eta_src_be",
        },
        "phase_3": {
            "name": "absolute thrust demonstration over the representative feed envelope",
            "points": TBD("Phase-3 test points {mdot_s, P_feed, T_feed, x_s}",
                          "W1 valve-outlet test points at 180/200/230 km (fo_feed_state_closure), reproduced on the "
                          "ground with MFCs, pressure control and bottles", [WORKSTREAMS["W1"]]),
            "composition": "bottled N2 / N2+O2 surrogate at the W1 composition; no atomic O (qualifier "
                           "COMPOSITION_SURROGATE on every outcome)",
            "arms": "per P-03 (PROPOSED P-03-A)",
            "visits": "n (from LOCK-2) visits per point and arm, each after a shutdown and restart; seeded "
                      "point order per block; oxygen-bearing points last",
            "gate": "absolute_thrust_gate",
            "reading_counts": phase3_counts(g["ns"]),
            "relation_to_R_arch": "none: Phase 3 is not paired and never enters R_arch; R_arch comes only from "
                                  "Phase 2",
            "stop_rules": ["an arm STOPPED by G-SRC at every flow is NOT_TESTED in Phase 3",
                           "P1-S1 / P1-S2 facility and hardware rules apply per point",
                           "a point whose visits are not all SUSTAINED is FLOOR_NOT_MET_AT_POINT (sustainment), "
                           "never excluded"],
            "score_bearing": "absolute gate outcomes per point and arm",
        },
    }


def absolute_gate(g: dict, rfp: dict, hg: dict) -> dict:
    crit = {c["id"]: c for gate in hg["gates"] for c in gate["criteria"]}
    need = ("G1.thrust_floor", "G1.thrust_ceiling", "G1.peak_capability_25mN", "G2.bus_power_max")
    for cid in need:
        if cid not in crit:
            raise InputChanged(f"lane-24 criterion {cid} missing")
    return {
        "status": REC,
        "purpose": "od_hardware_pivot decision (1): absolute thrust feasibility on the actual delivered feed within "
                   "P_bus < 1.5 kW, reported alongside (never merged into) R_arch",
        "limits": rfp,
        "quantities": {
            "T_measured": "vacuum-equivalent axial thrust from the thrust stand (M1), mean of n visits at the point; "
                          "facility corrections stated in the transformation chain (lane-24 G1.thrust_floor "
                          "definition)",
            "P_bus": "sum over every bus_power_boundary_v1 component of the arm of load / efficiency (contract basis, "
                     "D-10-A); PARTIAL (no compressor) vs V1 labelled (D-11)",
            "sustained": "every visit SUSTAINED per T-SUSTAIN with THR-EXTINCTION (Phase 1 definitions)",
            "u_c(T)": "sqrt(s_T^2 / n + (u_Tscale T)^2 [+ stated facility-correction term]); Type A with n - 1 dof, "
                      "Type B thrust-stand scale from S1a (nu = inf); nu_eff by minexp_numbers.welch_satterthwaite",
            "u_c(P_bus)": "sqrt(s_P^2 / n + sum_c (P_c u_c,scale)^2 + ledger-efficiency bound terms); same rule",
            "bounds": "T_LB = T_hat - k1 u_c(T), T_UB = T_hat + k1 u_c(T), P_LB = P_hat - k1 u_c(P), P_UB = P_hat + "
                      "k1 u_c(P), k1 = "
                      "minexp_numbers.t_one_sided(alpha_abs, nu_eff)",
        },
        "parameters": {"alpha_abs": g["alpha_abs"], "k1": g["k1"], "n_grid_source": g["n_grid_source"]},
        "pass_logic": {
            "per_point": [
                "FLOOR_DEMONSTRATED: all visits SUSTAINED AND T_LB >= 12 mN AND P_UB < 1500 W on the same visits "
                "AND (where S5 exists at the point) the smaller of the base-p_b and elevated-p_b T_LB >= 12 mN",
                "FLOOR_NOT_MET_AT_POINT: any visit NOT_SUSTAINED, OR T_UB < 12 mN at the tested P_bus",
                "POWER_NOT_MET_AT_POINT: P_LB >= 1500 W",
                "UNRESOLVED: otherwise",
            ],
            "over_tested_envelope": "ABS_FLOOR_DEMONSTRATED_OVER_TESTED_POINTS iff FLOOR_DEMONSTRATED at every "
                                    "Phase-3 point of the arm. This is an intersection of per-point claims: the "
                                    "probability of wrongly claiming all of them is at most the largest per-point "
                                    "error probability, so per-point alpha_abs needs no multiplicity correction.",
            "capability_25": {
                "P-04-i": "CEILING_DEMONSTRATED at a point iff a sustained condition exists with T_UB <= 25 mN "
                          "(G1.thrust_ceiling)",
                "P-04-ii": "CAPABILITY_25_DEMONSTRATED at a point iff, with Xe augmentation (D-15-C) in peak mode, "
                           "T_LB >= 25 mN AND P_UB < 1500 W (G1.peak_capability_25mN)",
            },
            "qualifiers": ["PARTIAL_BOUNDARY (no compressor): P_UB < 1500 W is necessary only -> "
                           "ABS_NECESSARY_ONLY_PARTIAL_BOUNDARY replaces FLOOR_DEMONSTRATED until the V1 basis exists",
                           "COMPOSITION_SURROGATE (no atomic O)", "FACILITY_UNCHECKED where S5 did not run",
                           "SURROGATE_HARDWARE if D-09-B (never gate-bearing)"],
        },
        "uncertainty_requirement": {
            "definition": "largest combined standard uncertainty for which a true value at the stated margin beyond "
                          "the limit yields a confident outcome on average: u_c,max = |true - limit| / k1",
            "thrust_floor_12mN": g["floor_requirement"],
            "bus_power_1500W": g["power_requirement"],
            "capability_25mN": g["capability_25_requirement"],
            "thrust_scale_allowance_at_margin_0.05": g["thrust_scale_allowance_at_margin_0.05"],
            "literature_context": g["literature_context"],
            "PROPOSED_requirement": f"P-02-A: margin {M_REQ} (the owner may choose another margin); the S1 D0-ABS "
                                    "check compares the S1 values with it",
        },
        "consistency_with_lane24": {
            "G1.thrust_floor": {"comparator": crit["G1.thrust_floor"]["comparator"],
                                "pass_sufficient_bases": crit["G1.thrust_floor"]["pass_sufficient_bases"],
                                "source": ptr("hg_matrix", "/gates/0/criteria/0")},
            "G1.thrust_ceiling": {"comparator": crit["G1.thrust_ceiling"]["comparator"],
                                  "source": ptr("hg_matrix", "/gates/0/criteria/1")},
            "G1.peak_capability_25mN": {"comparator": crit["G1.peak_capability_25mN"]["comparator"],
                                        "source": ptr("hg_matrix", "/gates/0/criteria/2")},
            "G2.bus_power_max": {"comparator": crit["G2.bus_power_max"]["comparator"],
                                 "pass_sufficient_bases": crit["G2.bus_power_max"]["pass_sufficient_bases"],
                                 "source": ptr("hg_matrix", "/gates/1/criteria/0")},
            "what_a_phase3_pass_is": "a lower bound (thrust) and an upper bound (P_bus) at tested Vyovrinda "
                                     "points: registrable by the owner in the lane-24 evidence register as "
                                     "measurement_vyovrinda (point_design scope) once the feed state is mapped to "
                                     "an envelope point and P_bus is on the V1 basis; a lane-24 G1 PASS further "
                                     "needs every altitude x atmosphere state and the atmospheric feed (atomic O "
                                     "included), which a bottled surrogate does not give",
            "what_a_phase3_miss_is_not": "never an architecture elimination: a single tested unit is point_design "
                                         "scope and lane-24 FAIL needs covering bounds on atmospheric and Xe-augmented "
                                         "feeds (experiment package outcome templates T1/T2: UNDETERMINED)",
        },
    }


def s1_to_lock2(draft: dict) -> list[dict]:
    rows = [
        ("S1a", "M1 thrust-stand in-situ calibrations (>= 10 before and after, REF-POLK2017 per lane 25)",
         "u_Tscale (Type B thrust scale) and the calibration record", "certificate / calibration regression -> "
         "relative scale uncertainty", "absolute gate u_c(T) only (cancels in R_arch)"),
        ("S1a", "M2 load-plane DC power channels", "u_c per common consumer (G4) and the P_bus scale",
         "calibration certificates", "readiness_n common terms; absolute gate u_c(P_bus)"),
        ("S1a", "M3 RF / microwave load-plane characterisation", "u_src (G3), reconstructed loss",
         "coupler/sensor calibration and matching/cable loss characterisation", "readiness_n f_src u_src term"),
        ("S1a", "DUMMY_LOAD_PICKUP on common diagnostics (no plasma)", "pickup bound per diagnostic",
         "maximum pickup reading with generators on into matched dummy loads; acceptance level TBD - requires an "
         "owner decision at LOCK-1", "D0 (a pickup above the LOCK-1 level fails D0)"),
        ("S1a", "M9 gauges, M10 MFC calibrations (N2, O2, Xe)", "flow uncertainty; min_flow_step",
         "MFC resolution in the final configuration", "Phase-1 bracket resolution (P-01)"),
        ("S1a", "M11 B(z) per configuration at the operating coil currents", "reference B(z) per configuration",
         "Hall-probe map before and after", "installation checks; W5 validation evidence if pre-registered"),
        ("S1b", "K re-installations x r readings at OP3 on HW-0", "u_T, u_P (K(r-1) dof), u_inst (nu_rm = K-1)",
         "lane-25 s1_plan.S1b_hall_on.outputs", "D0: readiness_n -> n (recorded at LOCK-2)"),
        ("S1b", "M12 temperatures", "T-SETTLE, T-SUSTAIN dwell", "thermal time constants and stand drift",
         "every score-bearing reading"),
        ("S1b", "I_d traces (high-bandwidth)", "THR-EXTINCTION ext_window; discharge_sampling_rate",
         "discharge oscillation band", "sustainment classes (Phases 1-3)"),
        ("S1b", "p_b at OP3 (Hall-on) and cold-flow p_b at the other flows", "D0 (v) record",
         "compare with T-PB-MAX", "D0"),
        ("S1b", "u_T (Type A) with u_Tscale", "D0-ABS record (PROPOSED)", "predicted u_c(T) at 12 mN vs the P-02 "
         "requirement; a miss is reported to the owner and does not block Phases 1-2", "Phase 3"),
        ("S1b / pilot", "start sequences", "ignition_timeout", "start-sequence design and Hall-only starts",
         "D-13 attempts"),
    ]
    _ = draft
    return [{"id": f"S1-{i + 1:02d}", "stage": st, "measurement": m, "sets_lock2_parameter": s, "rule": r,
             "used_by": u} for i, (st, m, s, r, u) in enumerate(rows)]


def milestones(pkg: dict) -> dict:
    m = copy.deepcopy(pkg["milestones"])
    return {
        "supports": ["A"],
        "A": {"this_brief_enables": [
            "the owner can decide D-01..D-15 and P-01..P-04 and sign LOCK-1 (LOCK1_DRAFT.json is the draft)",
            "after LOCK-1: hardware and instrumentation (W3, W4) and S1; after D0: LOCK-2 and the score-bearing phases",
            "conditional-selection statements of the form 'architecture X is baseline provided ...' can cite Phase-2 "
            "classes (R_arch, ENABLES) and Phase-3 absolute-gate outcomes as the demonstrated conditions"],
              "package_unlocks": m["A"]["unlocks"], "does_not": m["A"]["does_not"] + [
                  "change the Bundle-1 outcome (NO_BASELINE_YET) before measured discriminators exist"]},
        "to_reach_B": m["to_reach_B"] + [
            "Phase-3 absolute outcomes on the V1 boundary (ICD compressor draw) and at W1 test points mapped to "
            "envelope points",
            "held-out Hall-transport validation (W5) scored as pre-registered; an admitted closure to carry tested-"
            "point results to the design envelope"],
        "to_reach_C": m["to_reach_C"],
    }


# ------------------------------------------------------------------------------------------------------------------
# build / validate / render
# ------------------------------------------------------------------------------------------------------------------
def collect_tbd(obj, path="$", out=None):
    out = [] if out is None else out
    if isinstance(obj, dict):
        v = obj.get("value")
        if isinstance(v, str) and v.startswith("TBD"):
            if v == "TBD" and obj.get("requires"):
                v = f"TBD - requires {obj['requires']}"
            out.append({"path": path, "what": obj.get("what", ""), "value": v,
                        "blocked_by": obj.get("blocked_by", [])})
        for k, vv in obj.items():
            collect_tbd(vv, f"{path}.{k}", out)
    elif isinstance(obj, list):
        for i, vv in enumerate(obj):
            collect_tbd(vv, f"{path}[{i}]", out)
    return out


def build(root: Path = ROOT) -> dict:
    paths = verify_inputs(root)
    docs = {k: load_json(p) for k, p in paths.items() if p.suffix == ".json"}
    pkg = load_package(paths)
    mx = load_module(paths["minexp_tools"], "_lock1_minexp")
    draft = mx.load_draft(paths["minexp_draft"])
    pivot = docs["pivot"]
    if pivot.get("decision") != "APPROVED" or pivot.get("id") != "od_hardware_pivot":
        raise InputChanged("od_hardware_pivot is not APPROVED")
    rfp = rfp_values(root)
    g = absolute_gate_numbers(mx, draft, pkg, rfp, docs["p5n2_audit"])
    kn = knee_numbers(mx, draft, pkg)
    hgs = docs["hg_status"]
    b1 = docs["bundle1"]["outcome"]
    brief = {
        "schema": "abep_lock1_decision_brief_v1",
        "id": "fo_lock1_decision_brief_v1",
        "follow_on": "fo_lock1_decision_brief",
        "trigger": "T_PIVOT_LOCK1_DECISION_BRIEF",
        "owner_disposition": "od_hardware_pivot",
        "status": STATUS,
        "locked": False,
        "base_commit": BASE_COMMIT,
        "generated_by": SCRIPT_REF,
        "not_locked": "Nothing here is decided, pre-registered or locked. Every recommendation is PROPOSED; "
                      "thresholds not in the RFP are PROPOSED; the owner decides D-01..D-15 and P-01..P-04 and "
                      "signs LOCK-1 at the D-05 location. No score-bearing reading before LOCK-2.",
        "compliance": [
            "no absolute Hall performance from any closure (credible set empty; gate 3 FAIL); no screening "
            "candidate as a performance source; no retuning",
            "the paired / randomised Phase-2 design of lane 25 is kept intact (phases.phase_2."
            "paired_randomised_structure)",
            "no architecture named preferred; eliminations only via lane-24 hard gates (none issued)",
            "P5 calibration nuisance is never a design variable or axis; Hall-closure uncertainty does not reach "
            "the intake, compressor, gas chambers or valves",
            "valve-outlet feed state (W1) and compressor bus draw (lane 33) are TBD, never filled",
            "facility and supplier contact is the owner's channel; this brief states requirements only",
            "every number carries a unit, evidence class and source, else TBD with what it requires"],
        "inputs": [{"key": k, "path": v[0], "producer": v[1], "sha256": v[2]} for k, v in INPUTS.items()],
        "context": {
            "pivot_statement": pivot["statement"],
            "hard_gate_status": {"eliminated": hgs["eliminated"], "not_eliminated": hgs["not_eliminated"],
                                 "admitted_members": hgs["admitted_members"],
                                 "source": INPUTS["hg_status"][0]},
            "bundle1_outcome": {"form": b1["form"], "source": ptr("bundle1", "/outcome/form")},
            "parallel_workstreams": {k: v for k, v in WORKSTREAMS.items()},
        },
        "milestones": milestones(pkg),
        "decisions": decisions(pkg, g),
        "lock1_inputs": lock1_inputs(),
        "pivot_items": pivot_items(kn, g),
        "phases": phases(draft, docs["protocol"], pkg, kn, g),
        "absolute_thrust_gate": absolute_gate(g, rfp, docs["hg_matrix"]),
        "s1_to_lock2": {"rule": "LOCK-2 may only add S1 values and what the LOCK-1 rules compute from them, "
                                "without discretion; any change to a LOCK-1 item voids LOCK-1 and restarts S0; "
                                "score-bearing data taken before LOCK-2 are excluded (lane 25 Sec. 10)",
                        "source": ptr("minexp_draft", "/s1_plan"),
                        "rows": s1_to_lock2(draft),
                        "d0": "T-READINESS (lane 25) plus the PROPOSED D0-ABS record; D0 fail -> owner (raise "
                              "delta, improve instruments or mount, adopt OPTION-DIVERTER, or move facility)"},
    }
    brief["tbd_register"] = collect_tbd(brief)
    g.pop("ns")
    validate(brief)
    return brief


def numeric_leaf_errors(obj, path="$", parent=None, key=None) -> list[str]:
    errs = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            errs += numeric_leaf_errors(v, f"{path}.{k}", obj, k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            errs += numeric_leaf_errors(v, f"{path}[{i}]", obj, None)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        ok = key == "value" and isinstance(parent, dict) and all(parent.get(f) for f in
                                                                  ("unit", "evidence_class", "source"))
        if not ok:
            errs.append(path)
    return errs


def lock_violations(obj, path="$") -> list[str]:
    """Anything that marks this draft as locked / signed / decided."""
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if k == "locked" and v is not False:
                bad.append(p)
            if k == "status" and isinstance(v, str) and re.search(r"\bLOCKED\b|\bSIGNED\b|\bREGISTERED\b|"
                                                                 r"\bDECIDED\b|\bAPPROVED\b", v) \
                    and not v.startswith("DRAFT") and path != "$.context":
                bad.append(p)
            if k == "owner_choice" and v is not None:
                bad.append(p)
            bad += lock_violations(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += lock_violations(v, f"{path}[{i}]")
    return bad


def validate(brief: dict) -> None:
    bad = numeric_leaf_errors(brief)
    if bad:
        raise ValueError("numbers without unit / evidence class / source:\n  " + "\n  ".join(bad[:20]))
    text = json.dumps(brief, ensure_ascii=False)
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, text, flags=re.I):
            raise ValueError(f"forbidden pattern {pat!r}")
    if brief["status"] != STATUS or brief["locked"] is not False:
        raise ValueError("the brief must stay DRAFT_PENDING_OWNER_SIGNATURE and unlocked")
    lv = lock_violations(brief)
    if lv:
        raise ValueError("lock markers present: " + ", ".join(lv[:10]))
    ids = [d["id"] for d in brief["decisions"]]
    if tuple(ids) != DECISION_IDS:
        raise ValueError(f"decisions {ids} != D-01..D-15")
    for d in brief["decisions"] + brief["pivot_items"]:
        if len(d["options"]) < 2 or any(not o.get("consequences") for o in d["options"]):
            raise ValueError(f"{d['id']}: needs >= 2 options, each with consequences")
        r = d["recommendation"]
        if r["status"] != REC:
            raise ValueError(f"{d['id']}: recommendation must be PROPOSED")
        if r["option"] is not None and r["option"] not in {o["id"] for o in d["options"]}:
            raise ValueError(f"{d['id']}: recommended option not among the options")
        if not r["rationale"]:
            raise ValueError(f"{d['id']}: recommendation needs a rationale")
    for a in ARCHS:
        if a not in text:
            raise ValueError(f"architecture id {a} missing")


def lock1_draft(brief: dict, brief_sha: str, draft: dict) -> dict:
    thr = [{"id": t["id"], "lane25_source": ptr("minexp_draft", f"/thresholds/{i}"), "status": "PROPOSED",
            "owner_choice": None} for i, t in enumerate(draft["thresholds"])]
    return {
        "schema": "abep_lock1_draft_v1",
        "id": "LOCK-1",
        "status": STATUS,
        "locked": False,
        "note": "DRAFT for owner review. Not a lock: it becomes LOCK-1 only when the owner records every choice "
                "below, signs, and files it at the D-05 location. LOCK-2 is written only after S1 and D0.",
        "decision_source": {"path": f"{REL_HERE}/lock1_decision_brief_v1.json", "sha256": brief_sha},
        "signature": {"owner": None, "date": None, "lock_location": None,
                      "sha256_of_signed_file": None},
        "decisions": [{"id": d["id"], "title": d["title"], "options": [o["id"] for o in d["options"]],
                       "proposed": d["recommendation"]["option"], "owner_choice": None}
                      for d in brief["decisions"]],
        "pivot_items": [{"id": p["id"], "title": p["title"], "options": [o["id"] for o in p["options"]],
                         "proposed": p["recommendation"]["option"], "owner_choice": None}
                        for p in brief["pivot_items"]],
        "lock1_contents": [
            {"item": "L1-1", "what": "decision on every PROPOSED threshold and rule (lane 25 Sec. 10 item 1)",
             "thresholds": thr},
            {"item": "L1-2", "what": "mdot_min, mdot_nom, composition, V_nom, V_hi, P_hi",
             "value": "TBD - requires W1 valve-outlet test points (fo_feed_state_closure), the Vyovrinda Hall design "
                      "point (lane-17 DI-2) and the source allocation in bus_power_boundary_v1"},
            {"item": "L1-3", "what": "ledger inputs with evidence classes and T-LEDGER-SENSITIVITY bounds; f_src and "
                                     "w_c allocations", "value": "TBD - requires owner and lane_11_bus_boundary; "
                                                                 "compressor draw per D-11"},
            {"item": "L1-4", "what": "T-PB-MAX and T-ISO-INTERP",
             "value": "TBD - requires the facility specification (owner's channel) and D-04"},
            {"item": "L1-5", "what": "S1 plan (K, r, S1b point) and instrument list",
             "value": "K, r per lane-25 T-S1-REMOUNT-CYCLES / T-S1-READINGS-PER-CYCLE (PROPOSED); instrument list "
                      "TBD - requires W4 (fo_instrumentation_definition)"},
            {"item": "L1-6", "what": "seed and configuration-order draw",
             "value": "TBD - drawn and published at signature"},
            {"item": "L1-7", "what": "frozen analysis script (sha256) implementing lane-25 Sec. 6 and 9 and the "
                                     "absolute gate", "value": "TBD - requires the frozen analysis script"},
            {"item": "L1-8", "what": "score-bearing rows", "value": "lane-25 run matrix R01-R40 "
                                                                   f"({ptr('minexp_draft', '/run_matrix')}) plus "
                                                                   "Phase-3 rows TBD - requires W1 test points"},
            {"item": "L1-9", "what": "physics-track pre-registration (D-14)",
             "value": "TBD - requires W5 (fo_hall_validation_prereg_draft), filed before S1"},
            {"item": "L1-10", "what": "phase sequence and stop rules", "value": f"{REL_HERE}/"
                                                                               "lock1_decision_brief_v1.json#/phases"},
            {"item": "L1-11", "what": "absolute thrust gate parameters (P-02, P-04)",
             "value": f"{REL_HERE}/lock1_decision_brief_v1.json#/absolute_thrust_gate"},
            {"item": "L1-12", "what": "S1 -> LOCK-2 procedure",
             "value": f"{REL_HERE}/lock1_decision_brief_v1.json#/s1_to_lock2"},
        ],
    }


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def fmt(x) -> str:
    if isinstance(x, dict) and "value" in x:
        v = x["value"]
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return f"{v:g} {x.get('unit', '')}".strip()
        return str(v)
    return str(x)


def md_cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def md_lines(v, limit: int = 14) -> list[str]:
    lines = [ln[len("consequences: "):] if ln.startswith("consequences: ") else ln for ln in flat(v)]
    if len(lines) > limit:
        lines = lines[:limit] + [f"... {len(lines) - limit} more values in the JSON"]
    return lines


def flat(v, prefix="") -> list[str]:
    out = []
    if isinstance(v, dict) and "value" in v and ("unit" in v or isinstance(v["value"], str)):
        out.append(f"{prefix}{fmt(v)}")
    elif isinstance(v, dict):
        for k, vv in v.items():
            if k in ("source", "evidence_class", "unit", "note"):
                continue
            out += flat(vv, f"{prefix}{k}: ")
    elif isinstance(v, list):
        for vv in v:
            out += flat(vv, prefix)
    else:
        out.append(f"{prefix}{v}")
    return out


def render_md(b: dict) -> str:
    L = []
    a = L.append
    a("# LOCK-1 decision brief (W2, DRAFT for owner review)")
    a("")
    a(f"**Status: {b['status']}.** Follow-on `{b['follow_on']}` (trigger `{b['trigger']}`, owner disposition "
      f"`{b['owner_disposition']}`), base commit `{b['base_commit'][:10]}`. {b['not_locked']}")
    a("")
    a(f"Generated by `{b['generated_by']}` (`--check` reproduces this file, `lock1_decision_brief_v1.json` and "
      "`LOCK1_DRAFT.json` byte for byte). The JSON is authoritative; every number there carries unit, evidence class "
      "and source. Option consequences are those computed by the experiment-package builder with the lane-25 tools "
      "(re-run and reproduced at build time).")
    a("")
    a("## 0. The pivot in one paragraph")
    a("")
    a(b["context"]["pivot_statement"])
    a("")
    hs = b["context"]["hard_gate_status"]
    a(f"Current state: lane-24 eliminated {hs['eliminated']}, admitted Hall members {hs['admitted_members']}; "
      f"Bundle 1 outcome {b['context']['bundle1_outcome']['form']}. Compliance:")
    a("")
    for c in b["compliance"]:
        a(f"- {c}")
    a("")
    m = b["milestones"]
    a("## 1. Milestones")
    a("")
    a(f"Supports milestone **{', '.join(m['supports'])}** (conditional selection).")
    a("")
    for x in m["A"]["this_brief_enables"]:
        a(f"- {x}")
    a("")
    a("Does not:")
    a("")
    for x in m["A"]["does_not"]:
        a(f"- {x}")
    a("")
    a("To reach B:")
    a("")
    for x in m["to_reach_B"]:
        a(f"- {x}")
    a("")
    a("To reach C:")
    a("")
    for x in m["to_reach_C"]:
        a(f"- {x}")
    a("")
    a("## 2. Decisions D-01..D-15 (all open; recommendations PROPOSED)")
    a("")
    a("| id | question | options | PROPOSED | changed vs package |")
    a("|---|---|---|---|---|")
    for d in b["decisions"]:
        a(f"| {d['id']} | {md_cell(d['question'])} | {', '.join(o['id'] for o in d['options'])} | "
          f"{d['recommendation']['option']} | {'yes' if d['recommendation']['changed_from_package'] else 'no'} |")
    a("")
    for d in b["decisions"]:
        a(f"### {d['id']}. {d['title']}")
        a("")
        a(f"*Question.* {d['question']}")
        a("")
        for o in d["options"]:
            a(f"- **{o['id']}** ({o['label']}; {o['origin']})")
            for line in md_lines(o["consequences"]):
                a(f"  - {md_cell(line)}")
            for pcx in o["pivot_consequences"]:
                a(f"  - *pivot:* {md_cell(pcx)}")
        a("")
        r = d["recommendation"]
        a(f"*PROPOSED:* {r['option']}. {r['rationale']}")
        a("")
        a(f"*Depends on:* {'; '.join(d['depends_on'])}. *Phases:* {', '.join(d['phases_affected'])}. "
          f"Full consequences: `{d['package_source']}`.")
        a("")
        if "facility_by_stage" in d:
            fb = d["facility_by_stage"]
            a(f"*Facility requirements by stage* ({fb['rule']}):")
            a("")
            a("| stage | requirements (experiment package) | additional (PROPOSED) |")
            a("|---|---|---|")
            for st in fb["stages"]:
                ids = ", ".join(r.split("(")[-1].rstrip(")") for r in st["requirements"])
                a(f"| {st['stage']} | {ids} | {md_cell('; '.join(st.get('additional_PROPOSED', [])) or '-')} |")
            a("")
    a("## 3. Pivot items P-01..P-04 (introduced by the pivot; all open)")
    a("")
    for p in b["pivot_items"]:
        a(f"### {p['id']}. {p['title']}")
        a("")
        for o in p["options"]:
            a(f"- **{o['id']}** {o['label']}")
            for line in md_lines(o["consequences"]):
                a(f"  - {md_cell(line)}")
        r = p["recommendation"]
        a("")
        a(f"*PROPOSED:* {r['option'] if r['option'] else 'no recommendation (owner reading)'}. {r['rationale']}")
        a("")
        a(f"*Depends on:* {'; '.join(p['depends_on'])}.")
        a("")
    ph = b["phases"]
    a("## 4. Staged sequence")
    a("")
    a(ph["sequence"])
    a("")
    p1 = ph["phase_1"]
    a(f"### Phase 1: {p1['name']}")
    a("")
    a(f"- configuration: {p1['configuration']}")
    a(f"- locate: {p1['locate']}")
    a(f"- bracket: {p1['bracket']}")
    a(f"- sustained: {p1['sustained']['rule']} (dwell {p1['sustained']['dwell']['value']})")
    ex = p1["extinction"]
    a(f"- extinction ({ex['threshold_id']}, {ex['status']}): {ex['rule']}; parameters: "
      + "; ".join(f"{k} = {fmt(v)}" for k, v in ex["parameters"].items()) + f". Not extinction: "
      f"{ex['not_extinction']}.")
    a(f"- fallback: {p1['fallback_rule']['rule']}")
    kn = p1["knee_numbers"]
    a(f"- coarse spacing {fmt(kn['coarse']['coarse_spacing'])}; coarse scan {fmt(kn['coarse']['coarse_scan_readings'])}")
    a("")
    a("| bracket / min_flow_step | bisection steps | added readings |")
    a("|---|---|---|")
    for k, v in kn["refinement_by_bracket_ratio"].items():
        a(f"| {k.split('=')[1]} | {fmt(v['bisection_steps'])} | {fmt(v['added_readings'])} |")
    a("")
    a("Stop rules:")
    a("")
    for s in p1["stop_rules"]:
        a(f"- {s}")
    a("")
    p2 = ph["phase_2"]
    a(f"### Phase 2: {p2['name']}")
    a("")
    a(p2["content"] + ".")
    a("")
    a("Paired / randomised structure (kept intact):")
    a("")
    for s in p2["paired_randomised_structure"]:
        a(f"- {s}")
    a("")
    a(f"Decisive metric: {p2['decisive_metric']}. Stop rules: {'; '.join(p2['stop_rules'])}.")
    a("")
    a("Reading counts (experiment package, D-08-A): " + "; ".join(flat(p2["reading_counts"])))
    a("")
    p3 = ph["phase_3"]
    a(f"### Phase 3: {p3['name']}")
    a("")
    a(f"- points: {p3['points']['value']}")
    a(f"- composition: {p3['composition']}")
    a(f"- arms: {p3['arms']}; visits: {p3['visits']}")
    a(f"- relation to R_arch: {p3['relation_to_R_arch']}")
    for s in p3["stop_rules"]:
        a(f"- stop: {s}")
    a("")
    rc = p3["reading_counts"]
    ns_keys = [k for k in next(iter(rc.values())) if k != "points"]
    a("| points | " + " | ".join(ns_keys) + " |")
    a("|---|" + "---|" * len(ns_keys))
    for lab, row in rc.items():
        a(f"| {lab} | " + " | ".join(f"{row[k]['value']:g}" for k in ns_keys) + " |")
    a("")
    g = b["absolute_thrust_gate"]
    a("## 5. Absolute thrust gate (alongside R_arch; PROPOSED)")
    a("")
    a(g["purpose"] + ".")
    a("")
    for k, v in g["limits"].items():
        a(f"- {k}: {fmt(v)} ({v['source']})")
    for k, v in g["quantities"].items():
        a(f"- {k}: {v}")
    a("")
    a("Coverage factors k1 (one-sided, alpha_abs = " + fmt(g["parameters"]["alpha_abs"]) + "): " +
      "; ".join(f"{k}: {v['value']:.4g}" for k, v in g["parameters"]["k1"].items()))
    a("")
    a("Pass logic per point:")
    a("")
    for s in g["pass_logic"]["per_point"]:
        a(f"- {s}")
    a(f"- over the tested envelope: {g['pass_logic']['over_tested_envelope']}")
    for k, v in g["pass_logic"]["capability_25"].items():
        a(f"- 25 mN condition under {k}: {v}")
    a(f"- qualifiers: {'; '.join(g['pass_logic']['qualifiers'])}")
    a("")
    ur = g["uncertainty_requirement"]
    a(f"Uncertainty requirement. {ur['definition']}. {ur['PROPOSED_requirement']}.")
    a("")
    for key, lab, unit in (("thrust_floor_12mN", "thrust floor 12 mN", "mN"),
                           ("bus_power_1500W", "P_bus 1500 W", "W"), ("capability_25mN", "25 mN capability", "mN")):
        tab = ur[key]
        cols = list(next(iter(tab.values())).keys())
        a(f"*{lab}: largest u_c ({unit}; relative in brackets)*")
        a("")
        a("| margin | " + " | ".join(cols) + " |")
        a("|---|" + "---|" * len(cols))
        for mg, row in tab.items():
            a(f"| {mg.split('=')[1]} | " + " | ".join(
                f"{row[c]['u_c_max_abs']['value']:.4g} ({row[c]['u_c_max_rel']['value']:.3%})" for c in cols) + " |")
        a("")
    a("*Thrust-stand Type B scale allowance at margin 0.05 (after the lane-25 per-reading Type A target):*")
    a("")
    a("| n | u_T per reading (lane 25) | u_c,rel max | u_Tscale max |")
    a("|---|---|---|---|")
    for n, row in ur["thrust_scale_allowance_at_margin_0.05"].items():
        a(f"| {n} | {row['u_T_reading_max_lane25']['value']:.4%} | {row['u_c_rel_max_floor']['value']:.4%} | "
          f"{fmt(row['u_Tscale_max']) if isinstance(row['u_Tscale_max']['value'], str) else format(row['u_Tscale_max']['value'], '.4%')} |")
    a("")
    lc = ur["literature_context"]
    a(f"Context only: the published P5-N2 thrust sigma is {fmt(lc['sigma_T_P5_N2'])} (level 3, not Vyovrinda "
      f"hardware); with that value as u_c(T) and k1(nu=inf), the floor is demonstrable only for a true thrust of at "
      f"least "
      f"{fmt(lc['T_true_min_demonstrable_at_that_sigma'])}.")
    a("")
    cl = g["consistency_with_lane24"]
    a("Consistency with lane 24:")
    a("")
    for k in ("G1.thrust_floor", "G1.thrust_ceiling", "G1.peak_capability_25mN", "G2.bus_power_max"):
        v = cl[k]
        a(f"- {k}: comparator `{v['comparator']}`" + (f", pass bases {v['pass_sufficient_bases']}"
                                                      if "pass_sufficient_bases" in v else "") + f" (`{v['source']}`)")
    a(f"- a Phase-3 pass is: {cl['what_a_phase3_pass_is']}")
    a(f"- a Phase-3 miss is not: {cl['what_a_phase3_miss_is_not']}")
    a("")
    s = b["s1_to_lock2"]
    a("## 6. S1 qualification -> LOCK-2")
    a("")
    a(s["rule"] + ".")
    a("")
    a("| id | stage | S1 measurement | sets (LOCK-2) | rule | used by |")
    a("|---|---|---|---|---|---|")
    for r in s["rows"]:
        a(f"| {r['id']} | {r['stage']} | {md_cell(r['measurement'])} | {md_cell(r['sets_lock2_parameter'])} | "
          f"{md_cell(r['rule'])} | {md_cell(r['used_by'])} |")
    a("")
    a(f"D0: {s['d0']}.")
    a("")
    a("## 7. TBD register")
    a("")
    a("| path | value | blocked by |")
    a("|---|---|---|")
    seen = set()
    for t in b["tbd_register"]:
        key = (t["value"], tuple(t["blocked_by"]))
        if key in seen:
            continue
        seen.add(key)
        a(f"| `{md_cell(t['path'])}` | {md_cell(t['value'])} | {md_cell(', '.join(t['blocked_by']))} |")
    a("")
    a("## 8. Pinned inputs")
    a("")
    a("| path | producer | sha256 |")
    a("|---|---|---|")
    for i in b["inputs"]:
        a(f"| `{i['path']}` | {i['producer']} | `{i['sha256'][:16]}` |")
    a("")
    a("Parallel pivot workstreams (referenced by follow-on id, not read): " +
      ", ".join(f"{k} `{v}`" for k, v in b["context"]["parallel_workstreams"].items()) + ".")
    a("")
    return "\n".join(L)


def outputs(root: Path = ROOT) -> dict:
    brief = build(root)
    js = dumps(brief)
    sha = hashlib.sha256(js.encode("utf-8")).hexdigest()
    mx = load_module(root / INPUTS["minexp_tools"][0], "_lock1_minexp2")
    draft = mx.load_draft(root / INPUTS["minexp_draft"][0])
    ld = lock1_draft(brief, sha, draft)
    lv = lock_violations(ld)
    if lv or ld["status"] != STATUS:
        raise ValueError("LOCK1_DRAFT carries lock markers: " + ", ".join(lv))
    return {OUT_JSON: js, OUT_MD: render_md(brief), OUT_DRAFT: dumps(ld)}


def main(argv: list[str]) -> int:
    outs = outputs()
    if "--check" in argv:
        bad = [str(p.relative_to(ROOT)) for p, t in outs.items()
               if not p.is_file() or p.read_text(encoding="utf-8") != t]
        if bad:
            print("NOT REPRODUCED: " + ", ".join(bad), file=sys.stderr)
            return 1
        print("OK: LOCK-1 brief reproduces byte for byte")
        return 0
    for p, t in outs.items():
        p.write_text(t, encoding="utf-8")
    print("wrote " + ", ".join(str(p.relative_to(ROOT)) for p in outs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
