#!/usr/bin/env python3
"""A9.7 F3 compressor geometry synthesis study (follow-on fo_a9_7_f3_compressor_synthesis).

Runs abep_sim/design/compressor_synthesis.py over the W1 candidate-cases of the DI-1.4 compressor down-selection
requirement envelope (taken as PARAMETRIC_SENSITIVITY inlet records; the F1/F2 records exist but the F3 fronts are not
rebuilt on them - F4 / F7 couple F1 -> F2 -> F3 directly, see IFD-F3-01/02 and the INT-01 limitation), and
writes:
  f3_compressor_synthesis_v1.json   parameters, search variables, sources, strict-mode result, per-case summaries,
                                    Pareto fronts (full records), size_for() comparison, findings, interface demands,
                                    open owner questions, m16_impact
  f3_compressor_designs_v1.json     the design grid, every feasible record, and every rejected design with its reasons
  F3_COMPRESSOR_SYNTHESIS.md        generated from the JSON

What it is not: a compressor design, a CBE, a PASS, a winner or a model change. abep_sim/compressor.py (size_for
included) is not modified; nothing is wired into archengine; goldens cannot move.

Deterministic (no random numbers; no seed needed), no Julia, a few seconds of CPU.

Usage:
  python docs/design_synthesis/f3_compressor/build_f3_compressor.py           # (re)write outputs
  python docs/design_synthesis/f3_compressor/build_f3_compressor.py --check   # exit 1 unless reproduced and pins hold
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from abep_sim.design import compressor_synthesis as cs  # noqa: E402
from abep_sim.assessment import design_gates as ost  # noqa: E402  (owner-question state v5 reader; A9.22)

OUT_DIR_REL = "docs/design_synthesis/f3_compressor"
SCRIPT_REL = f"{OUT_DIR_REL}/build_f3_compressor.py"
JSON_NAME = "f3_compressor_synthesis_v1.json"
DESIGNS_NAME = "f3_compressor_designs_v1.json"
MD_NAME = "F3_COMPRESSOR_SYNTHESIS.md"
TEST_REL = "tests/test_design_f3_compressor.py"
BASE_COMMIT = "1c9d7a648cd4ce739e587248693271e5115698e1"
DOWNSELECT_REL = "docs/architecture_comparison/compressor_downselect/compressor_downselect_v2.json"
SIG = 10

# Immutable inputs (owner decisions are immutable after commit; the versioned v1 deliverables are frozen by version).
PINNED = (
    DOWNSELECT_REL,
    "docs/procurement/web_track_v1/threads/R1_compressor.json",
    "docs/decisions/OD_2026_09_29_owner_answers_147.json",
    "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md",
    "docs/decisions/OD_2026_10_01_A9_7_architecture_freeze_design_synthesis.json",
)
# Read but mutable (results are reproduced by --check instead of pinned).
REFERENCED_NOT_PINNED = (
    ("abep_sim/compressor.py", "DragCompressor.run / _run_once / size_for, dataclass defaults (called, never changed)"),
    ("abep_sim/materials.py", "DB['Ti6Al4V'] density and T_max_K (uncited priors)"),
    ("abep_sim/constants.py", "K_B, M_SPECIES"),
    ("abep_sim/design/compressor_synthesis.py", "the F3 synthesis module"),
    ("docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json", "A9B-04 compressor line (CBE TBD), MA-AL-02"),
    ("docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json", "row 3 compressor (BLOCKED)"),
)


def sha256(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def rnd(x):
    if isinstance(x, float):
        if not math.isfinite(x):
            return None if math.isnan(x) else ("inf" if x > 0 else "-inf")
        return float(f"{x:.{SIG}g}")
    if isinstance(x, dict):
        return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v) for v in x]
    return x


def inlet_cases() -> list[tuple[cs.InletRecord, dict]]:
    d = json.loads((REPO / DOWNSELECT_REL).read_text())
    out = []
    for cand, v in d["requirement_envelope"].items():
        for case_id, c in v["cases"].items():
            w = c["w_s_inlet"]
            if abs(sum(w.values()) - 1.0) > 1e-8:
                raise RuntimeError(f"{cand}/{case_id}: inlet mass fractions do not close")
            m = c["forward_flow_to_compressor_kgps"]
            rec = cs.InletRecord(
                record_id=f"{cand}/{case_id}", mdot_kgps={s: m * w[s] for s in cs.SPECIES},
                p_total_Pa=c["p_passive_Pa"], T_K=c["T_plenum_K"], label=cs.LABEL_PARAMETRIC,
                source=f"{DOWNSELECT_REL}#requirement_envelope/{cand}/cases/{case_id} (forward_flow_to_compressor_kgps x "
                       "w_s_inlet, p_passive_Pa, T_plenum_K)",
                evidence_class="model-derived",
                status=f"{v['status']}; {v['evidence_class']}; PARAMETRIC_SENSITIVITY inlet (down-selection envelope, not "
                       "the F1/F2 records)",
                extra={"altitude_km": c["altitude_km"], "solar_level": c["solar_level"], "setpoint_Pa": c["setpoint_Pa"],
                       "CR_required_upper_bound_flow_basis": c["CR_required"]["upper_bound_flow_basis"],
                       "CR_required_self_consistent_backflow": c["CR_required"]["self_consistent_backflow"]})
            out.append((rec, c))
    return out


DIAG_KEEP = ("stress_margin", "u_tip_turbo_mps", "recirculation_residual", "K_unclipped_min", "p_stage_max_Pa",
             "drag_Kn_min_upper_bound_O_omitted", "module_rotor_ok_uncited_db_yield")


def compact(r: dict) -> dict:
    """Record trimmed for the committed JSON: id, design, status, outputs and the gate diagnostics."""
    return {"id": r["id"], "design": r["design"], "status": r["status"], "outputs": r["outputs"],
            "diagnostics": {k: r["diagnostics"].get(k) for k in DIAG_KEEP}}


def _rng(vals):
    vals = [v for v in vals if v is not None]
    return [min(vals), max(vals)] if vals else None


def build() -> tuple[dict, dict]:
    grid = cs.SearchGrid()
    d = json.loads((REPO / DOWNSELECT_REL).read_text())
    a_rng = d["requirement_summary"]["A_inlet_min_m2"]["0.25"]
    if (a_rng["min"], a_rng["max"]) != cs.A_INLET_MIN_B025_RANGE_M2:
        raise RuntimeError("A_INLET_MIN_B025_RANGE_M2 no longer matches the pinned down-selection")
    design_grid = grid.designs()
    reason_code = {r: f"R{i + 1}" for i, r in enumerate(cs.REASONS)}

    cases, case_designs = [], {}
    strict = None
    all_front, all_feas, sizefor_all = [], [], []
    drag_feasible = 0
    for rec, c in inlet_cases():
        if strict is None:
            strict = cs.synthesize(rec, mode=cs.MODE_STRICT)
        res = cs.synthesize(rec, mode=cs.MODE_PARAMETRIC, grid=grid)
        recs = {r["id"]: r for r in res["designs"]}
        feas = [recs[i] for i in res["feasible_ids"]]
        front = [recs[i] for i in res["pareto_ids"]]
        drag_feasible += sum(1 for r in feas if r["design"]["N_drag"] > 0)
        all_front += front
        all_feas += feas
        counts = {}
        for r in res["designs"]:
            for x in r["reasons"]:
                counts[x] = counts.get(x, 0) + 1
        sp = rec.extra["setpoint_Pa"]
        sf = [cs.size_for_comparison(rec, rec.extra["CR_required_upper_bound_flow_basis"], a, front)
              for a in grid.a_turbo_m2]
        sizefor_all += sf
        fo = [r["outputs"] for r in front]
        cases.append({
            "case": rec.record_id, "inlet": rec.as_dict(), "label": res["label"], "status": res["status"],
            "n_designs": len(res["designs"]), "n_feasible": len(feas), "n_rejected": len(res["designs"]) - len(feas),
            "rejection_counts": dict(sorted(counts.items())),
            "pareto_ids": res["pareto_ids"], "pareto_with_S_ids": res["pareto_with_S_ids"],
            "pareto_records_in": f"{DESIGNS_NAME}#cases/{rec.record_id}/feasible (ids above)",
            "front_ranges": None if not fo else {
                "P_out_Pa": _rng([o["P_out_Pa"] for o in fo]), "CR_total": _rng([o["CR_total"] for o in fo]),
                "CR_O": _rng([o["CR_by_species"]["O"] for o in fo]),
                "P_compressor_el_W": _rng([o["P_compressor_el_W"] for o in fo]),
                "m_compressor_kg": _rng([o["m_compressor_kg"] for o in fo]),
                "T_compressor_K": _rng([o["T_compressor_K"] for o in fo]),
                "S_turbo_m3_s": _rng([o["S_turbo_m3_s"] for o in fo]),
                "x_O_out_partial_pressure": _rng([o["x_s_out_partial_pressure"]["O"] for o in fo]),
                "x_O_delivered_flow": _rng([o["x_s_delivered_flow_mole"]["O"] for o in fo])},
            "reference_setpoint_Pa": sp,
            "reference_setpoint_status": "PROPOSED (W1 setpoint ladder; informational, not a gate)",
            "n_feasible_reaching_reference_setpoint": sum(1 for r in feas if r["outputs"]["P_out_Pa"] >= sp),
            "size_for_comparison": sf,
        })
        by_id = {r["id"]: r for r in res["designs"]}
        if [x["id"] for x in design_grid] != [r["id"] for r in res["designs"]]:
            raise RuntimeError("design order differs from the design grid")
        case_designs[rec.record_id] = {
            "status_by_design": ["F" if by_id[x["id"]]["outputs"] else ",".join(reason_code[y] for y in
                                 by_id[x["id"]]["reasons"]) for x in design_grid],
            "feasible": [{"id": r["id"], "outputs": r["outputs"],
                          "diagnostics": {k: r["diagnostics"].get(k) for k in DIAG_KEEP}} for r in feas],
        }

    # --- findings (numbers generated from the study)
    n_cases = len(cases)
    zero_feas = [c["case"] for c in cases if c["n_feasible"] == 0]
    n_drag_designs = sum(1 for x in design_grid if x["N_drag"] > 0) * n_cases
    n_drag_clip = sum(1 for cd in case_designs.values() for x, codes in zip(design_grid, cd["status_by_design"])
                      if x["N_drag"] > 0 and reason_code[cs.R_CLIP] in codes.split(","))
    ti_u_allow = math.sqrt(cs.TI64_FTY_A_BASIS_PA / (cs.DragCompressor.stress_safety * cs.DB["Ti6Al4V"].density))
    db_u_allow = cs.DragCompressor(rotor_material="Ti6Al4V").u_max()
    sf_sized = [s for s in sizefor_all if s["size_for"].get("sized")]
    sf_gate_rej = [s for s in sizefor_all if s["gate_status"] == cs.ST_REJECTED]
    sf_reason_counts = {}
    for s in sf_gate_rej:
        for x in s["gate_reasons"]:
            sf_reason_counts[x] = sf_reason_counts.get(x, 0) + 1
    sf_on_front = sum(1 for s in sizefor_all if s["on_front"])
    sf_dominated = sum(1 for s in sizefor_all if s["dominated_by_front"])
    fo = [r["outputs"] for r in all_front]
    reach = sum(1 for c in cases if c["n_feasible_reaching_reference_setpoint"] > 0)
    setpoints_above_domain = sorted({c["reference_setpoint_Pa"] for c in cases
                                     if c["reference_setpoint_Pa"] > cs.P_MOLECULAR_LIMIT_PA})
    findings = [
        {"id": "F3-01", "finding": f"no design with drag stages is feasible: {n_drag_clip} of {n_drag_designs} "
         "drag-stage design evaluations have an unclipped Gaede K < 1 (throughput above the stage capacity S0 p at "
         "the code-default channel h, w, L, xi; since A9.9 S2.5 / MCC-02 the module reports the unclipped K and flags "
         "the stage OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY instead of silently using K = 1). Feasible drag-stage designs: "
         f"{drag_feasible}. Agrees with the down-selection drag-only probe (S_required / S0 ~ 1e3)",
         "evidence_class": "model-derived (from assumed code-default coefficients)"},
        {"id": "F3-02", "finding": f"rotor stress: with the cited Ti-6Al-4V A-basis Fty 827 MPa and the module safety "
         f"factor 2 (uncited), sigma = rho u^2 caps the tip speed at {ti_u_allow:.4g} m/s; the module's legacy "
         f"sensitivity tip-speed cap (uncited DB yield 880 MPa; since A9.9 S2.3 not a qualification: rotor_ok is False "
         f"without a registered strength basis) allows {db_u_allow:.4g} m/s, so size_for in PARAMETRIC_SENSITIVITY "
         "mode can return rotors this search rejects. "
         "Both are below the 500 m/s published TMP practice (Al alloys)",
         "evidence_class": "inferred (cited allowable) + assumed (safety factor, density)"},
        {"id": "F3-03", "finding": f"evidence domain: every stage outlet is capped at 0.1 Pa (free-molecular, "
         f"Chiggiato Sec. 4.1.2 / CD-04). Cases where a feasible design reaches the PROPOSED W1 setpoint: {reach} of "
         f"{n_cases}; PROPOSED setpoints above the domain: {setpoints_above_domain} Pa (cannot be evaluated by this "
         "model at all; needs T-1 data or a transitional-regime model)",
         "evidence_class": "inferred"},
        {"id": "F3-04", "finding": "mdot_delivered is invariant across converged designs at a fixed inlet record "
         "(DragCompressor.run delivers the captured flow in steady state), so it does not discriminate designs; the "
         "compressor's effect on delivered flow enters through the inlet pumping speed S_turbo and the plenum "
         "backflow (F1/F4 coupling), reported as a secondary Pareto objective. The delivered-flow composition equals "
         "the inlet composition; the outlet PARTIAL-PRESSURE composition is O-depleted (x_O "
         f"{_rng([o['x_s_out_partial_pressure']['O'] for o in fo])} on the fronts vs delivered-flow x_O "
         f"{_rng([o['x_s_delivered_flow_mole']['O'] for o in fo])})",
         "evidence_class": "model-derived (from assumed code-default coefficients)"},
        {"id": "F3-05", "finding": f"Pareto fronts (all cases): P_out {_rng([o['P_out_Pa'] for o in fo])} Pa, "
         f"P_compressor (electrical, eta_motor 0.8 code default) {_rng([o['P_compressor_el_W'] for o in fo])} W, "
         f"m_compressor {_rng([o['m_compressor_kg'] for o in fo])} kg vs the owner v0 allocation 5.5 kg (allocation, "
         f"not CBE), T_compressor {_rng([o['T_compressor_K'] for o in fo])} K. PARAMETRIC_SENSITIVITY values under "
         "uncited coefficients: not a CBE, not a design value",
         "evidence_class": "model-derived (from assumed code-default coefficients)"},
        {"id": "F3-06", "finding": f"size_for() consistency check ({len(sizefor_all)} calls = {n_cases} cases x "
         f"{len(grid.a_turbo_m2)} A_turbo): sized={len(sf_sized)}; rejected by this module's gates={len(sf_gate_rej)} "
         f"(reasons {dict(sorted(sf_reason_counts.items()))}); on the synthesis front={sf_on_front}; feasible but "
         f"dominated={sf_dominated}. size_for optimises the scalar mass + 0.02 P_el, checks only rotor_ok with an "
         "uncited yield, and applies no convergence, clipping or domain gate",
         "evidence_class": "model-derived"},
        {"id": "F3-07", "finding": f"cases with an empty feasible set: {len(zero_feas)} ({zero_feas}); they are "
         "reported, not relaxed", "evidence_class": "model-derived (from assumed code-default coefficients)"},
        {"id": "F3-08", "finding": "MODE_STRICT returns NOT_EVALUATED for every case: "
         f"{len(strict['blockers'])} blockers (all FIXED DragCompressor coefficients are uncited code defaults, the "
         "inlet is a PARAMETRIC_SENSITIVITY record, the rotor density is an uncited DB prior). Closing evidence: "
         "compressor_downselect T-1..T-9", "evidence_class": "inferred"},
    ]

    interface_demands = [
        {"id": "IFD-F3-01", "direction": "requires", "counterpart": "F1 (fo_a9_7_f1_intake_synthesis)",
         "path": "abep_sim/design/intake_synthesis.py (F1-ID-03)",
         "what": "intake-exit state per species (mdot_s, P, T) feeding F2. The F1 records exist, but this study's "
                 "fronts use PARAMETRIC_SENSITIVITY inlets from the down-selection requirement envelope; F4 "
                 "(abep_sim/design/plenum_feed.py F4-ID-01/05) and F7 couple F1 -> F3 at the F1 states over the "
                 "F3 front union only (INT-01 limitation recorded in F4 / F7 / F9)",
         "status": "AVAILABLE_NOT_CONSUMED_BY_THIS_STUDY (coupled in F4 / F7)"},
        {"id": "IFD-F3-02", "direction": "requires", "counterpart": "F2 (fo_a9_7_f2_filter_stage)",
         "path": "abep_sim/design/filter_stage.py (F2-IF-03)",
         "what": "filter-outlet record = compressor inlet: compressor_synthesis.InletRecord fields (mdot_kgps per O/N2/O2, "
                 "p_total_Pa, T_K, source, evidence_class, label F1_F2_INTERFACE_RECORD); optional p_species_Pa must "
                 "follow the DragCompressor convention (partial pressure proportional to number flow) or is refused. "
                 "Every F2 filter record is TBD / PARAMETRIC (no evidenced filter); F4 couples the filter cases",
         "status": "AVAILABLE_NOT_CONSUMED_BY_THIS_STUDY (F2 records TBD / PARAMETRIC; coupled in F4)"},
        {"id": "IFD-F3-03", "direction": "provides", "counterpart": "F1 / F2",
         "path": "abep_sim/design/intake_synthesis.py (F1-ID-04); abep_sim/design/filter_stage.py (F2-IF-04)",
         "what": "compressor inlet pumping speed S_turbo [m^3/s] per design (sets the plenum backflow / K_back "
                 "coupling) and the GAEDE_CHARACTERISTIC_CLIPPED rejection (inlet pressure not self-consistent with the "
                 "throughput)", "status": "AVAILABLE (PARAMETRIC_SENSITIVITY)"},
        {"id": "IFD-F3-04", "direction": "provides", "counterpart": "F4 (fo_a9_7_f4_plenum_feed)",
         "path": "abep_sim/design/plenum_feed.py (F4-ID-05)",
         "what": "per design: P_out, mdot_s delivered, x_s,out (partial pressure) and delivered-flow x_s, T_gas and "
                 "T_compressor, P_compressor", "status": "AVAILABLE (PARAMETRIC_SENSITIVITY)"},
        {"id": "IFD-F3-05", "direction": "requires", "counterpart": "F4 (fo_a9_7_f4_plenum_feed)",
         "path": "abep_sim/design/plenum_feed.py (F4-ID-06)",
         "what": "downstream plenum back-pressure / feed-control boundary (DragCompressor computes P_out from a fixed "
                 "inlet; a coupled plenum must close p_out against the H-1 demand)", "status": "TBD"},
        {"id": "IFD-F3-06", "direction": "requires", "counterpart": "F5 (fo_a9_7_f5_h1_freeze_candidate)",
         "path": "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json (IFD-F3-01, IFD-F4-01..05: TBD)",
         "what": "H-1 inlet demand (mdot_s, P, T, x_s); the W1 setpoints used here are PROPOSED references only",
         "status": "TBD"},
        {"id": "IFD-F3-07", "direction": "provides", "counterpart": "F0 (fo_a9_7_f0_profiling)",
         "path": "docs/performance/PERFORMANCE_BASELINE_98fbbb9.json",
         "what": f"compressor design-space search workload: {len(design_grid)} designs x {n_cases} inlets via "
                 f"`python {SCRIPT_REL}` (a few CPU seconds); size_for comparison {len(sizefor_all)} calls",
         "status": "AVAILABLE"},
        {"id": "IFD-F3-08", "direction": "provides", "counterpart": "F7/F8 (fo_a9_7_f7_f8_coupled_optimizer)",
         "path": "abep_sim/design/compressor_synthesis.py",
         "what": "x_compressor = (N_turbo, A_turbo, u_tip/RPM, N_drag, rotor_material) and evaluate_design(); "
                 "MODE_STRICT returns NOT_EVALUATED until the coefficient evidence exists (never an assumed value)",
         "status": "AVAILABLE"},
        {"id": "IFD-F3-09", "direction": "provides", "counterpart": "mass/power budgets (A9B-04, AL-02)",
         "path": "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json",
         "what": "model-derived mass/power ranges labelled PARAMETRIC_SENSITIVITY; they do NOT fill the CBE column",
         "status": "INFORMATIONAL"},
    ]
    open_owner_questions = [
        {"id": "OQ-F3-01", "question": "Safety factor and allowable basis for the compressor rotor: the module uses an "
         "uncited factor 2.0; the only cited allowable accessed is the Ti-6Al-4V annealed-plate A-basis Fty 827 MPa "
         "(MMPDS-06 via NASA-HDBK-6025, room temperature). Which factor and which product-form / temperature "
         "allowable govern?", "proposed_answer": "none proposed (design-policy decision)",
         "needed_by": "any F3 result used beyond PARAMETRIC_SENSITIVITY"},
        {"id": "OQ-F3-02", "question": "Turbo-stage geometry definition: hub ratio / blade span relating R_turbo to "
         "A_turbo (the search uses the zero-hub limit R = sqrt(A/pi))?", "proposed_answer": "none proposed",
         "needed_by": "F7 coupled vector"},
        {"id": "OQ-F3-03", "question": "The free-molecular domain caps every stage at 0.1 Pa while W1 PROPOSED setpoints "
         "reach 0.2 Pa: wait for T-1 data, or commission an open-literature transitional-regime stage model before "
         "any outlet above 0.1 Pa is evaluated?", "proposed_answer": "wait for T-1 (no extrapolation meanwhile)",
         "needed_by": "F4 plenum/feed closure"},
        {"id": "OQ-F3-04", "question": "Re-admit aluminium-alloy or CFRP rotors to the search once a cited allowable is "
         "supplied (CFRP also subject to the AO policy OD-C3)?", "proposed_answer": "only with a cited A/B-basis "
         "allowable and an AO disposition", "needed_by": "next F3 revision"},
    ]
    open_owner_questions = ost.apply_to_questions(open_owner_questions)       # RVF-02: v5 answer state applied
    m16_impact = [{"row": 3, "key": "compressor", "state_before": "BLOCKED", "state_after": "BLOCKED",
                   "change": "none: this artifact is a model-derived PARAMETRIC_SENSITIVITY screening under uncited code "
                             "defaults (counts_as_evidence false); the blocking inputs remain compressor_downselect "
                             "T-1..T-9 and the DI-1.4 concept freeze"}]

    doc = {
        "schema": cs.SCHEMA, "version": cs.VERSION, "lane": "A9_7_F3", "follow_on": "fo_a9_7_f3_compressor_synthesis",
        "directive": "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md (F3)",
        "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL, "module": "abep_sim/design/compressor_synthesis.py",
        "test": TEST_REL, "status": "PARAMETRIC_SENSITIVITY_SCREENING (INVESTIGATION_HYPOTHESIS; not a design, not a "
                                    "CBE, no PASS, no winner)",
        "what_it_is_not": ["a compressor design or freeze", "a replacement of DragCompressor.size_for (unchanged; goldens "
                           "unaffected)", "a CBE for A9B-04", "an evidence-gate change", "wired into archengine"],
        "determinism": "no random numbers are used (grid search); outputs rounded to 10 significant digits",
        "pins": {p: sha256(p) for p in PINNED},
        "referenced_not_pinned": [{"path": p, "use": u} for p, u in REFERENCED_NOT_PINNED],
        "sources": cs.SOURCES,
        "parameters": cs.CITED_VALUES,
        "coefficients": cs.coefficient_registry(),
        "search_variables": cs.search_variables(grid),
        "materials_excluded": cs.MATERIALS_EXCLUDED,
        "gates": [
            {"id": cs.R_ALLOWABLE_TBD, "rule": "rotor material must have a cited allowable", "basis": "A9.7 evidence rule"},
            {"id": cs.R_STRESS, "rule": "Fty / (SF rho u_max^2) - 1 >= 0, u_max = max(turbo, drag tip speed)",
             "basis": "P-TI64-FTY-A-BASIS, P-STRESS-SAFETY, P-TI64-DENSITY; sigma = rho u^2 (compressor.py docstring)"},
            {"id": cs.R_TIP_DOMAIN, "rule": "u_tip <= 500 m/s", "basis": "P-U-TIP-PUBLISHED-MAX"},
            {"id": cs.R_INLET_DOMAIN, "rule": "inlet p <= 0.1 Pa", "basis": "P-MOLECULAR-LIMIT"},
            {"id": cs.R_MODEL, "rule": "finite state, no exception, mirror reproduces _run_once p_out to 1e-12",
             "basis": "no silent fallback (CLAUDE.md rule 3)"},
            {"id": cs.R_NONCONV, "rule": "re-evaluated leak-recirculation residual <= 1e-4", "basis": "P-RECIRC-RTOL"},
            {"id": cs.R_CLIP, "rule": "every unclipped per-species Gaede K >= 1", "basis": "compressor.py _run_once clip "
             "max(min(K, K0), 1) hides an overloaded stage"},
            {"id": cs.R_DOMAIN_P, "rule": "every stage outlet p <= 0.1 Pa", "basis": "P-MOLECULAR-LIMIT"},
            {"id": cs.R_DOMAIN_KN, "rule": "drag channel Kn upper bound (O omitted) >= 0.5", "basis":
             "P-KN-FREE-MOLECULAR, P-SIGMA-C-N2/O2 (P-SIGMA-C-O TBD)"},
            {"id": cs.R_THERMAL, "rule": "T_compressor <= materials.DB T_max_K", "basis": "P-TI64-T-SERVICE (uncited)"},
        ],
        "reason_codes": {v: k for k, v in reason_code.items()},
        "objectives": {"primary": [list(o) for o in cs.PRIMARY_OBJECTIVES],
                       "secondary": [list(o) for o in cs.SECONDARY_OBJECTIVES],
                       "rule": "weak Pareto dominance over feasible designs of ONE inlet record; ties kept; no scalar "
                               "objective, no selected optimum"},
        "efficiency_basis": "P_compressor = (P_gas_drag + P_bearing) / eta_motor + P_ctrl (DragCompressor); eta_motor, "
                            "k_bear and P_ctrl are uncited code defaults (closing test T-4)",
        "mass_basis": "DragCompressor mass model: rotor discs (materials.DB density, uncited) x (1 + stator_mass_factor) "
                      "+ motor (motor_kg_per_Nm x torque + 0.25) + bearings; code defaults (closing test T-7)",
        "thermal_basis": "DragCompressor lumped node T = T_sink + losses / conductance_to_sink (code defaults, T-5); "
                         "T_gas_K (c_bar) is the inlet temperature and is not coupled to T_compressor by the module",
        "strict_mode": {"status": strict["status"], "blockers": strict["blockers"]},
        "cases": cases,
        "findings": findings,
        "interface_demands": interface_demands,
        "open_owner_questions": open_owner_questions,
        "m16_impact": m16_impact,
        "compliance": {"modified_existing_modules": False, "wired_into_archengine": False, "goldens_affected": False,
                       "new_pytest_skips": 0, "single_optimum_declared": False, "pass_declared": False},
    }
    designs = {"schema": "f3_compressor_designs_v1", "generated_by": SCRIPT_REL, "companion": JSON_NAME,
               "label": cs.LABEL_PARAMETRIC, "reason_codes": {v: k for k, v in reason_code.items()},
               "encoding": "cases[<case>].status_by_design[i] belongs to design_grid[i]: 'F' = feasible, otherwise "
                           "the comma-separated reason codes of the rejected design (every rejected design is kept)",
               "design_grid": design_grid, "cases": case_designs}
    return rnd(doc), rnd(designs)


def dump(o) -> str:
    return json.dumps(o, indent=1, sort_keys=False, ensure_ascii=False) + "\n"


def dump_compact(o) -> str:
    """One grid entry / one case per line: small and diff-friendly."""
    head = {k: v for k, v in o.items() if k not in ("design_grid", "cases")}
    lines = ["{"]
    for k, v in head.items():
        lines.append(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},")
    lines.append(' "design_grid": [')
    g = o["design_grid"]
    lines += [f"  {json.dumps(x, separators=(',', ':'))}{',' if i < len(g) - 1 else ''}" for i, x in enumerate(g)]
    lines.append(" ],")
    lines.append(' "cases": {')
    items = list(o["cases"].items())
    for i, (k, v) in enumerate(items):
        lines.append(f"  {json.dumps(k)}: {json.dumps(v, separators=(',', ':'))}{',' if i < len(items) - 1 else ''}")
    lines.append(" }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _f(x, n=4):
    return "-" if x is None else (f"{x:.{n}g}" if isinstance(x, float) else str(x))


def _r(r):
    return "-" if not r else f"{_f(r[0])}–{_f(r[1])}"


def render_md(doc: dict) -> str:
    L = []
    A = L.append
    A("# F3 — Compressor geometry synthesis (A9.7)")
    A("")
    A(f"> Generated by `{SCRIPT_REL}` from `{JSON_NAME}` (designs: `{DESIGNS_NAME}`). Do not edit by hand; "
      "`--check` verifies.")
    A("")
    A(f"**Status: {doc['status']}.** Module `{doc['module']}`; test `{doc['test']}`; base `{doc['base_commit'][:7]}`.")
    A("")
    A("This is a bounded design search beside `DragCompressor.size_for()`, which is not modified. It builds "
      "`DragCompressor` instances and runs the module's own self-consistent `run()`. It then applies fail-closed gates "
      "that `run()` and `size_for()` do not apply: a cited rotor allowable, a convergence re-check, characteristic "
      "clipping, the free-molecular evidence domain and a thermal limit. It returns feasible sets and Pareto fronts and "
      "keeps every rejected design with its reasons. It never selects an optimum.")
    A("")
    A("Every coefficient that is not searched is an uncited code default (compressor_downselect CD-01). For that reason "
      "**MODE_STRICT returns NOT_EVALUATED**, and every number below is a **PARAMETRIC_SENSITIVITY** result. None of "
      f"them is a design value, a CBE or a PASS. The inlet records are the {len(doc['cases'])} W1 candidate-cases of the DI-1.4 "
      "requirement envelope, which are PROPOSED and model-derived. The F1/F2 interface records exist, but this study's "
      "fronts are not rebuilt on them; F4 and F7 couple F1 -> F2 -> F3 directly over the F3 front union (a "
      "restriction recorded as a limitation in F4 / F7 / F9).")
    A("")
    A("## Search variables (A9.7 list)")
    A("")
    A("| variable | value / range | basis | evidence class | status |")
    A("|---|---|---|---|---|")
    for v in doc["search_variables"]:
        A(f"| {v['id']} | {v['value']} {v['units']} | {v['basis']} | {v['evidence_class']} | {v['status']} |")
    A("")
    A("## Cited and labelled parameters")
    A("")
    A("| id | value | units | source | evidence class | status |")
    A("|---|---|---|---|---|---|")
    for p in doc["parameters"]:
        A(f"| {p['id']} | {p['value']} | {p['units']} | {p['source']} | {p['evidence_class']} | {p['status']} |")
    A("")
    A("## Fixed module coefficients (not searched)")
    A("")
    A("| id | value | units | status |")
    A("|---|---|---|---|")
    for c in doc["coefficients"]:
        if c["role"] == "FIXED_CODE_DEFAULT":
            A(f"| {c['id']} | {c['value']} | {c['units']} | {c['status']} |")
    A("")
    A("## Gates (reject, fail closed)")
    A("")
    A("| code | gate | rule | basis |")
    A("|---|---|---|---|")
    inv = {v: k for k, v in doc["reason_codes"].items()}
    for g in doc["gates"]:
        A(f"| {inv[g['id']]} | `{g['id']}` | {g['rule']} | {g['basis']} |")
    A("")
    A(f"Strict mode: **{doc['strict_mode']['status']}** ({len(doc['strict_mode']['blockers'])} blockers).")
    A("")
    A("## Per-case results (PARAMETRIC_SENSITIVITY)")
    A("")
    A("| case | p_in Pa | feasible / designs | front | P_out Pa | P_el W | mass kg | T_comp K | x_O out (pp) | "
      "setpoint Pa (PROPOSED) | reaching it |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for c in doc["cases"]:
        fr = c["front_ranges"] or {}
        A(f"| {c['case']} | {_f(c['inlet']['p_total_Pa'])} | {c['n_feasible']} / {c['n_designs']} | "
          f"{len(c['pareto_ids'])} | {_r(fr.get('P_out_Pa'))} | {_r(fr.get('P_compressor_el_W'))} | "
          f"{_r(fr.get('m_compressor_kg'))} | {_r(fr.get('T_compressor_K'))} | {_r(fr.get('x_O_out_partial_pressure'))} | "
          f"{_f(c['reference_setpoint_Pa'])} | {c['n_feasible_reaching_reference_setpoint']} |")
    A("")
    A("## size_for() consistency check (not a replacement)")
    A("")
    A("| case | A_turbo m² | size_for rows/stages/rpm | sized | this module | on front |")
    A("|---|---|---|---|---|---|")
    for c in doc["cases"]:
        for s in c["size_for_comparison"]:
            sf = s["size_for"]
            rr = ",".join(inv[x] for x in s["gate_reasons"]) or "-"
            A(f"| {c['case']} | {_f(s['a_turbo_m2'])} | {sf.get('turbo_rows')}/{sf.get('n_stages')}/{_f(sf.get('rpm'), 6)} | "
              f"{sf.get('sized')} | {s['gate_status']} {rr} | {s['on_front']} |")
    A("")
    A("## Findings")
    A("")
    for f in doc["findings"]:
        A(f"- **{f['id']}** ({f['evidence_class']}): {f['finding']}")
    A("")
    A("## Interface demands")
    A("")
    A("| id | direction | counterpart | path | what | status |")
    A("|---|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        A(f"| {d['id']} | {d['direction']} | {d['counterpart']} | {d['path']} | {d['what']} | {d['status']} |")
    A("")
    A("## Owner questions raised by this lane")
    A("")
    A(f"Status from `{ost.OQ5_REL}` (as raised: TBD_OWNER).")
    A("")
    for q in doc["open_owner_questions"]:
        A(f"- **{q['id']}** ({q['status']}): {q['question']} Proposed (as raised): {q['proposed_answer']}. "
          f"Needed by: {q['needed_by']}.")
    A("")
    A("## M16 impact")
    A("")
    for m in doc["m16_impact"]:
        A(f"- row {m['row']} `{m['key']}`: {m['state_before']} → {m['state_after']}. {m['change']}")
    A("")
    A("## Sources")
    A("")
    for k, s in doc["sources"].items():
        A(f"- **{k}**: {s['citation']} ({s['access_level']}{', ' + s['url'] if 'url' in s else ''})")
    A("")
    return "\n".join(L)


def check_pins(doc_on_disk: dict) -> list[str]:
    bad = []
    for p, h in doc_on_disk.get("pins", {}).items():
        if not (REPO / p).exists() or sha256(p) != h:
            bad.append(p)
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the committed outputs are reproduced")
    a = ap.parse_args(argv)
    doc, designs = build()
    js, jd, md = dump(doc), dump_compact(designs), render_md(doc)
    out = REPO / OUT_DIR_REL
    if a.check:
        ok = True
        for name, text in ((JSON_NAME, js), (DESIGNS_NAME, jd), (MD_NAME, md)):
            if not (out / name).exists() or (out / name).read_text(encoding="utf-8") != text:
                print(f"MISMATCH: {name}")
                ok = False
        if ok:
            bad = check_pins(json.loads((out / JSON_NAME).read_text(encoding="utf-8")))
            if bad:
                print(f"PIN MISMATCH: {bad}")
                ok = False
        print("OK" if ok else "rerun the builder")
        return 0 if ok else 1
    out.mkdir(parents=True, exist_ok=True)
    (out / JSON_NAME).write_text(js, encoding="utf-8")
    (out / DESIGNS_NAME).write_text(jd, encoding="utf-8")
    (out / MD_NAME).write_text(md, encoding="utf-8")
    print(f"wrote {OUT_DIR_REL}/{JSON_NAME}, {DESIGNS_NAME}, {MD_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
