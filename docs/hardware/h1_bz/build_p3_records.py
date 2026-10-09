"""P3 (A9.38) records from the FE B(z) record: the DCR-002 request (DBF1-BZ-04) and the P3 closure-state record.

Reads docs/hardware/h1_bz/h1_bz_fe_v1.json (and its prereg / lock) and writes
  docs/baseline/DBF-1/dcr/DCR-DBF1-002_request_v1.json
  docs/closure/P3_h1_magnetic_field_closure_v1.json
Usage: python build_p3_records.py [--check]   (stdlib only)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REC = os.path.join(HERE, "h1_bz_fe_v1.json")
PRE = os.path.join(HERE, "h1_bz_fe_prereg_v4.json")
LOCK = os.path.join(HERE, "h1_bz_fe_prereg_lock_v4.json")
DCR = os.path.join(ROOT, "docs", "baseline", "DBF-1", "dcr", "DCR-DBF1-002_request_v1.json")
CLO = os.path.join(ROOT, "docs", "closure", "P3_h1_magnetic_field_closure_v1.json")
STMT = "docs/closure/statements/P3_h1_magnetic_field.md"


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def pin(p, pointer=None):
    d = {"path": rel(p), "sha256": sha(p)}
    if pointer:
        d["pointer"] = pointer
    return d


def build():
    r = json.load(open(REC))
    ok = r["field_outcome"] == "FE_DERIVED_VERIFIED"
    ex = r["exact_levels_nominal_L3"]
    env = r["uncertainty_envelope"]
    a2, a3 = r["acceptance"]["H1F-BZ-02"], r["acceptance"]["H1F-BZ-03"]
    sc = r["surrogate_comparison_DCR_002"]
    files = r["hallthruster_files"]["files"]
    nominal_files = {f: m for f, m in files.items() if m["variant"] == "NOM"}
    dbf = os.path.join(ROOT, "docs", "baseline", "DBF-1", "dbf1_v1.json")
    dbf_lock = os.path.join(ROOT, "docs", "baseline", "DBF-1", "dbf1_lock_v1.json")
    env_pre = os.path.join(ROOT, "docs", "rust_migration", "new_physics", "NP-HALL-PARAMETRIC-ENVELOPE", "prereg_v1.json")
    m2 = os.path.join(ROOT, "docs", "milestones", "M2_196_state_rfp_closure", "m2_closure_record_v1.json")

    def lev(l, k):
        return ex.get(l, {}).get(k)

    new_value = {
        "id": "BZ-H1FE-V1",
        "label": "H1_FE_DERIVED_NOT_MEASURED",
        "per_level_files": {l: {"file": f"{r['hallthruster_files']['dir']}/{f}", "sha256": m["sha256"], "NI_total_A": m["NI_total_A"]}
                            for f, m in nominal_files.items() for l in [m["level"]]},
        "registration": "B_profile = {file, align: 'anode', z_ref_in_file_mm: 0.0, scale_to: 'max'}, B_ref_T = B_peak_G x 1e-4 (no rigid shift: the file z is the H-1 z)",
        "evidence_class": r["evidence_class"],
        "uncertainty": {k: env["BP-HI"][k] for k in ("z_peak_minus_L_mm", "B_anode_over_B_peak", "FWHM_mm", "NI_A") if env["BP-HI"].get(k)},
    }
    dcr = {
        "schema": "abep_dcr_request_v1",
        "id": "DCR-DBF1-002",
        "alias": "DCR-002 (A9.38 closure board P3)",
        "status": "REQUESTED_PENDING_OWNER_APPROVAL" if ok else "NOT_PROPOSED_FIELD_NOT_VERIFIED",
        "date": "2026-10-08",
        "requested_by": "lane L-H1-BZ (A9.38 P3)",
        "approved_by": None,
        "approval_record": None,
        "process": "docs/baseline/DBF-1/DCR_PROCESS.md (a DCR is approved and committed before any rerun that uses the changed value; this file is the request; the register entry is made in a new register version by the register owner)",
        "register_note": "dcr_register_v1.json is the empty register at the freeze and is never edited; this request is to be entered in dcr_register_v2.json (or the next version) together with any concurrent DCR (e.g. DCR-DBF1-001, P1 intake)",
        "baseline": {"DBF-1": pin(dbf), "lock": pin(dbf_lock)},
        "items": [{
            "id": "DBF1-BZ-04",
            "old_value": "BZ-P5B16",
            "old_evidence_class": "digitized literature shape (surrogate); label SOURCED_SURROGATE_P5_SHAPE_NOT_H1_BZ",
            "new_value": new_value if ok else None,
        }],
        "unchanged_items": ["DBF1-BZ-01 (shape target)", "DBF1-BZ-02 (band 69.93-268.6 G)", "DBF1-BZ-03 (BP-LO / BP-HI levels)",
                            "DBF1-BZ-05 (capability 403 G)", "DBF1-H1-01..06"],
        "physical_or_evidence_reason": {
            "deficiency": "DBF1-BD-05 (closure condition: an H-1 B(z) from FEMM of MC-1 or a measured map, H1F-BZ-01)",
            "quantitative": [
                "the DBF1-BZ-04 surrogate is a P5 shape: its anode-to-peak ratio 0.201, gradient and high-field width are P5 properties (DBF1-BZ-04 uncertainty); under the envelope prereg bz_family classification_effect a Hall non-closure under it is never eligible (NOT_DETERMINABLE, blocker H1_BZ_NOT_REGISTERED)",
                f"the FE-derived H-1 field of the registered MC-1 circuit (outcome {r['field_outcome']}) differs from it: at BP-HI the FE anode-to-peak ratio is {lev('BP-HI', 'B_anode_over_B_peak')} (surrogate {sc['surrogate_descriptors']['B_anode_over_B_peak']}), FWHM {lev('BP-HI', 'FWHM_mm')} mm (surrogate {sc['surrogate_descriptors']['FWHM_mm']} mm), peak at z - L = {lev('BP-HI', 'z_peak_minus_L_mm')} mm (surrogate 0 by registration); max normalised profile difference over z = 0 .. L + 66 mm {sc['per_level'].get('BP-HI', {}).get('max_normalised_difference')} ({sc['per_level'].get('BP-HI', {}).get('materiality_flag')})",
            ],
            "evidence": {"record": pin(REC), "prereg": pin(PRE), "lock": pin(LOCK)},
            "never_the_reason": "Hall / M2 performance: no Hall simulation was run with the FE field and none is used; the proposal follows from the evidence class (prereg v4 dcr_002_evaluation.method), whether the FE shape is favourable or not",
        },
        "evaluation_method": {"preregistered_in": pin(PRE, "/dcr_002_evaluation"), "committed_alone_before_comparison": True,
                              "rule": "propose iff the field outcome is FE_DERIVED_VERIFIED"},
        "results_seen_before_request": [
            {"record": pin(m2), "what": "M2 closure record v1 summary: NOT_DETERMINABLE at C1, HALL_NUMERICS_NOT_CONVERGED on all required cells (no Hall value entered)"},
            {"record": "docs/baseline/DBF-1/DBF1_v1.md", "what": "DBF-1 items and BD-01..06"},
            {"record": "docs/closure/CLOSURE_BOARD_v1.md", "what": "P1-P9 board"},
            {"record": rel(REC), "what": "this lane's FE record (all numbers)"},
        ],
        "impact": {
            "DBF-1": "DBF1-BZ-04 value and evidence class change; DBF1-BD-05 closes on approval (a measured map stays an EM verification item); a new baseline version (DBF-1.1) with its own files and lock is created by the baseline owner on approval",
            "NP-HALL-PARAMETRIC-ENVELOPE": "a new prereg addendum declaring bz_family kind H1_REGISTERED (FE-DERIVED) with the files above is required before any Hall run uses them; the v1 prereg and addenda A1-A8 are not edited",
            "M2": "every M2 record computed under BZ-P5B16 stays history (surrogate records are never relabelled); the M2 rerun after P2 / P1 cites the new baseline lock",
            "h1_freeze_candidate": "H1F-BZ-01 / BZ-02 / BZ-05 evidence is supplied by this record; the freeze-candidate record itself is immutable history",
            "hardware": "no hardware value changes (the FE used the registered MC-1 circuit); measured B(z) remains an EM verification item",
        },
        "new_baseline": {"version": "DBF-1.1 (proposed)", "files": "to be generated by the baseline owner on approval", "lock": None},
    }
    statuses = {
        "H1F-BZ-01": "FE-DERIVED H-1 B(z) registered (this record); measured map = EM verification item",
        "H1F-BZ-02": a2["outcome"],
        "H1F-BZ-03": a3["B1"]["result"] + " / " + a3["B2"]["result"],
        "H1F-BZ-04 / DBF1-BZ-05": a3["B3"]["result"],
        "H1F-BZ-05": f"B_anode/B_peak reported ({lev('BP-HI', 'B_anode_over_B_peak')} at BP-HI); owner tolerance still TBD_OWNER",
    }
    state = "FROZEN FOR EM" if ok and a2["outcome"] == "SHAPE_CONSISTENT" and a3["B1"]["result"].startswith("BAND") else (
        "DCR REQUIRED" if ok else "BLOCKED BY SPECIFIC MISSING EVIDENCE")
    clo = {
        "schema": "abep_closure_item_v1",
        "id": "P3",
        "item": "H1 magnetic field B(z)",
        "date": "2026-10-08",
        "governance": "A9.38",
        "owner_lane": "L-H1-BZ",
        "closure_state": state,
        "closure_state_basis": ("the H-1 field is FE-derived from the registered MC-1 circuit, verified on analytic / image / nonlinear "
                                "benchmarks, mesh-converged, with an uncertainty envelope over the registered assumption ranges; it meets the "
                                "registered shape and band targets; verification by test (measured B(z) on the engineering model) is pending. "
                                "Adoption into the controlled baseline is through DCR-DBF1-002 (requested, owner approval pending); until "
                                "then DBF-1 Hall runs keep the surrogate and stay surrogate records") if state == "FROZEN FOR EM" else
                               "see the FE record outcome and acceptance",
        "field_outcome": r["field_outcome"],
        "evidence_class": r["evidence_class"],
        "key_numbers": {
            "NI_total_A": {l: lev(l, "NI_A") for l in ("BP-LO", "BP-HI", "CAP-403")},
            "B_peak_G": {l: lev(l, "B_peak_G") for l in ("BP-LO", "BP-HI", "CAP-403")},
            "z_peak_minus_L_mm": {l: lev(l, "z_peak_minus_L_mm") for l in ("BP-LO", "BP-HI", "CAP-403")},
            "B_anode_over_B_peak": {l: lev(l, "B_anode_over_B_peak") for l in ("BP-LO", "BP-HI", "CAP-403")},
            "coil_currents_at_registered_turns": a3["coil_currents_at_registered_turns"],
            "envelope_BP_HI": env["BP-HI"],
        },
        "item_statuses": statuses,
        "dcr": {"id": "DCR-DBF1-002", "request": rel(DCR), "status": dcr["status"]},
        "governing_evidence": [pin(REC), pin(PRE), pin(LOCK), pin(os.path.join(HERE, "bh_curves_v1.json")),
                               pin(os.path.join(ROOT, r["hallthruster_files"]["manifest"]))],
        "submission_safe_statement": STMT,
        "remaining_blockers": [
            "owner approval of DCR-DBF1-002 and the DBF-1.1 lock before any Hall run cites the FE field; then an NP-HALL-PARAMETRIC-ENVELOPE addendum (bz_family H1_REGISTERED)",
            "shielded pole contour H1F-MC-05 (the FE field is the registered pre-shielding flat-pole circuit; a shielded design is a new FE version)",
            "hot-pole B-H (H1F-MA-03 / 04) and the procured-lot B-H (HW-MC-13)",
            "measured B(z) on the engineering model (H1F-EX-08 probe path, H1F-MC-09 hot-state sensor)",
        ],
        "findings": [
            "the centreline peak lies in the exit pole gap at z - L = -4.5 mm (envelope -5.5 .. -2.6 mm): inside the lane's preregistered S2 screening window [-h/2, +h]; 'at or just downstream of L' still has no owner tolerance (H1F-BZ-05 TBD_OWNER)",
            "B_anode / B_peak is about -0.001 (a slight reversal; the iron back plate under the anode face), far below the surrogate's 0.201",
            "the centreline response is linear within 1 % up to 1500 A-turns (0.454-0.458 G per A-turn); saturation lowers it by 6 % at 2008 and 19 % at 3000 A-turns",
            "local iron |B| maxima reach B_sat already at about 520 A-turns: these sit at the sharp re-entrant corners of the flat-pole geometry (field singularities, not mesh-converged and not a gate); the H1F-MC-07 working-flux factor (0.7 B_sat) cannot be checked before the detailed pole contour (H1F-MC-05) with corner radii exists",
            "BP-LO envelope: the uncertainty variants started their preregistered sweep at 260 A-turns, so BP-LO (about 154 A-turns) was NOT_REACHED_IN_SWEEP for every variant; only the nominal BP-LO is evaluated (its shape descriptors equal the BP-HI ones to 0.1 %, the response being linear there; this is an observation, not a substitute for the envelope)",
            "per-coil currents at the registered f_NI 2 turns (357 / 157) at BP-HI are 0.82 / 1.87 A: the inner coil sits below the analog 1-5 A supply window (a gauge / supply item, H1F-CO-03 / CO-06, not a field item)",
        ],
        "separation": r["separation"],
    }
    return dcr, clo


def main():
    dcr, clo = build()
    out = {DCR: json.dumps(dcr, indent=1, ensure_ascii=False) + "\n", CLO: json.dumps(clo, indent=1, ensure_ascii=False) + "\n"}
    if "--check" in sys.argv:
        bad = [p for p, t in out.items() if not os.path.exists(p) or open(p, encoding="utf-8").read() != t]
        print("OK" if not bad else "DIFFERS: " + ", ".join(bad))
        sys.exit(1 if bad else 0)
    for p, t in out.items():
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(t)
    print("wrote", rel(DCR), rel(CLO), "state", clo["closure_state"])


if __name__ == "__main__":
    main()
