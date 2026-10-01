#!/usr/bin/env python3
"""A9.7 F1 intake geometry synthesis study (lane fo_a9_7_f1_intake_synthesis; owner directive
docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md).

Builds f1_intake_synthesis_v1.json and F1_INTAKE_SYNTHESIS.md (generated from the JSON) with
abep_sim/design/intake_synthesis.py. The study is deterministic (seeded direct TPMC with a bounded particle count; the
frozen TPMC surface only at exact nodes of its build state) and takes a few minutes of single-thread CPU.

What it is: a design-synthesis SCREENING of the intake design space (A, d, L/d, phi) under every supported surface-state
scenario (alpha, Maxwell/CLL), pointing angle and orbit state, with a documented non-dominated (Pareto) filter.
What it is not: a selection, a winner, a PASS, a flight design, a model change or a Hall prediction. Status stays
INVESTIGATION_HYPOTHESIS.

Usage:
  python docs/design_synthesis/f1_intake/build_f1_intake.py          # (re)write outputs
  python docs/design_synthesis/f1_intake/build_f1_intake.py --check  # exit 1 unless the committed files are reproduced
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from abep_sim.design import intake_synthesis as F1  # noqa: E402
from abep_sim.constants import RFP  # noqa: E402

OUT_DIR_REL = "docs/design_synthesis/f1_intake"
SCRIPT_REL = f"{OUT_DIR_REL}/build_f1_intake.py"
JSON_NAME = "f1_intake_synthesis_v1.json"
MD_NAME = "F1_INTAKE_SYNTHESIS.md"
BASE_COMMIT = "1c9d7a648cd4ce739e587248693271e5115698e1"
DIRECTIVE_REL = "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md"
DIRECTIVE_JSON_REL = "docs/decisions/OD_2026_10_01_A9_7_architecture_freeze_design_synthesis.json"
PINNED = (
    "abep_sim/data/intake_surface_v1.csv",
    "abep_sim/data/intake_surface_v1.json",
    "abep_sim/data/atmosphere_msis21_v1.csv",
    "abep_sim/data/atmosphere_msis21_v1.json",
    DIRECTIVE_REL,
)
REFERENCED_NOT_PINNED = (
    ("abep_sim/intake_tpmc.py", "called (intake_response, clausing_transmission, IntakeGeometry defaults); not modified"),
    ("abep_sim/intake.py", "IntakeSurface recombination convention examined (finding F1-01); not modified, not called"),
    ("abep_sim/atmosphere.py", "frozen dataset lookups (atmosphere()); not modified"),
    ("abep_sim/constants.py", "species masses, RFP thrust envelope; not modified"),
    ("abep_sim/materials.py", "Al6061 density cross-check (2700, literature-class prior)"),
    ("docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json",
     "setpoint ladder (p_ref sweep), DI-1.x owner questions, LIT-01..03 comparables, FC-01 backflow finding"),
    ("docs/interfaces/UPSTREAM_ICD.md", "IF-A1 intake -> filter interface; G-07 two-temperature gap"),
    ("docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json", "M16 rows 1 (intake) and 2 (filter)"),
)
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "requirement-as-recorded", "as-reported (secondary)", "TBD", "numerical-setting")

# compact columnar candidate table
CAND_COLS = ("candidate", "area_m2", "d_mm", "L_over_d", "phi", "depth_m", "wall_area_m2", "m_intake_code_default_case_kg",
             "mdot_captured_kgps", "mdot_captured_se_kgps", "drag_N", "drag_se_N", "eta_c_mix", "eta_c_mix_se",
             "C_D_mix", "C_D_mix_se", "CR_passive_mix", "CR_passive_mix_se", "off_axis_rel_eta_loss_per_deg",
             "off_axis_rel_eta_loss_per_deg_se", "off_axis_dCD_per_deg", "surface_state_rel_eta_per_alpha",
             "surface_state_rel_eta_per_alpha_se", "compressor_burden_per_Pa", "compressor_burden_per_Pa_se",
             "feasible", "pareto_status")
ENV_EXTRA = ("mdot_captured_kgps_worst_state", "drag_N_worst_state", "CR_passive_mix_worst_state",
             "compressor_burden_worst_state", "surface_state_rel_eta_per_alpha_worst_state")
SPECIES_COLS = ("state_id", "species", "L_over_d", "phi", "alpha", "theta_deg", "scattering", "source", "eta_c", "eta_c_se",
                "C_D_row", "C_D_species", "C_D_species_se", "K_back", "K_back_se", "CR_passive", "CR_passive_se",
                "unresolved_fraction", "converged", "n_particles", "seed")


def sha256(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def table(rows, cols):
    return {"columns": list(cols), "rows": [[r.get(c) for c in cols] for r in rows]}


def item(id_, name, value, units, basis, source, evidence_class, status, **kw):
    assert evidence_class in EVIDENCE_CLASSES, evidence_class
    d = {"id": id_, "name": name, "value": value, "units": units, "basis": basis, "source": source,
         "evidence_class": evidence_class, "status": status}
    d.update(kw)
    return d


def build_items(spec):
    g = F1.DEFAULT_GEOMETRY
    sm = F1.surface_meta()
    return [
        item("F1-P-01", "honeycomb wall material density (Al 6061-T6)", F1.RHO_AL6061_KG_M3, "kg m^-3",
             "datasheet value 2.70 g/cc", "REF-6061T6-DATASHEET", "as-reported (secondary)", "CITED",
             note="material choice itself is NOT decided (code default IntakeGeometry wall material); density applies "
                  "only if Al 6061 is chosen"),
        item("F1-P-02", "honeycomb wall thickness", "TBD", "mm", "no sourced Vyovrinda structural design",
             "none", "TBD", "TBD", parametric_case_value=g.wall_thickness_mm,
             parametric_case_source="abep_sim/intake_tpmc.py IntakeGeometry.wall_thickness_mm default (no cited source)"),
        item("F1-P-03", "AO-protective coating thickness", "TBD", "um", "no sourced coating design", "none", "TBD", "TBD",
             parametric_case_value=g.coating_thickness_um,
             parametric_case_source="IntakeGeometry.coating_thickness_um default (no cited source)"),
        item("F1-P-04", "AO-protective coating density", "TBD", "kg m^-3", "coating material undecided", "none", "TBD",
             "TBD", parametric_case_value=g.coating_density_kg_m3,
             parametric_case_source="IntakeGeometry.coating_density_kg_m3 default ('SiOx / alumina class', no cited "
                                    "source; abep_sim/materials.py Al2O3_anodised lists 3950)"),
        item("F1-P-05", "support / frame mass fraction", "TBD", "-", "no structural design", "none", "TBD", "TBD",
             parametric_case_value=g.support_mass_frac,
             parametric_case_source="IntakeGeometry.support_mass_frac default (no cited source)"),
        item("F1-P-06", "channel wall / plenum gas temperature T_wall", g.T_wall_K, "K",
             "the frozen TPMC surface was built with this value; CR_passive and the IF-A1 temperature use it",
             "abep_sim/intake_tpmc.py IntakeGeometry.T_wall_K default (no cited source); ICD G-07", "assumed",
             "ASSUMED_CODE_DEFAULT (not varied: varying it requires direct TPMC everywhere)"),
        item("F1-P-07", "surface state / accommodation alpha", "TBD", "-",
             "no measured accommodation for any Vyovrinda surface (DI-1.3 open); carried as scenario axis over the "
             "model-supported frozen-surface nodes, never optimised", "intake_surface_v1.json grid.alpha", "TBD", "TBD",
             scenario_values=list(spec.alphas)),
        item("F1-P-08", "gas-surface kernel", "TBD", "-",
             "Maxwell (alpha = diffuse fraction) and CLL (alpha_n = alpha_t = alpha) both carried as scenarios",
             "abep_sim/intake_tpmc.py; intake_surface_v1.json scattering", "TBD", "TBD", scenario_values=list(spec.kernels)),
        item("F1-P-09", "pointing error theta (intake axis vs relative wind)", "TBD", "deg",
             "no AOCS pointing budget; evaluated at 0 and at the largest frozen-surface node", "intake_surface_v1.json "
             "grid.theta_deg", "TBD", "TBD", evaluated_values=[0.0, spec.theta_hi_deg]),
        item("F1-P-10", "reference feed pressure p_ref for the compressor burden", "TBD", "Pa",
             "value from F4 / H-1 (TBD); parametric sweep only; the Pareto set is checked invariant under the sweep",
             "REF-FEED-STATE-CLOSURE (PROPOSED ladder; DI-1.6)", "TBD", "TBD", sweep_values=list(spec.p_ref_Pa)),
        item("F1-P-11", "RFP thrust maximum (hard-constraint bound on intake-face drag)", RFP.thrust_max_mN, "mN",
             "intake-face drag above the top of the RFP thrust range cannot be compensated inside that range",
             "REF-RFP-CONSTANTS", "requirement-as-recorded", "REQUIREMENT_AS_RECORDED (verify against official RFP)"),
        item("F1-P-12", "direct TPMC particles per point", spec.n_direct, "-", "bounded for the < 10 min CPU budget; "
             "statistical SE reported per point", "this study", "numerical-setting", "STUDY_SETTING"),
        item("F1-P-13", "frozen-surface particles per point", int(sm["n_per_point"]), "-", "surface metadata",
             "abep_sim/data/intake_surface_v1.json n_per_point", "numerical-setting", "FROZEN"),
        item("F1-P-14", "K_back (Clausing) particles per evaluation", F1.K_BACK_N, "-",
             "intake_response calls clausing_transmission with its default n; assumed unchanged since the surface build "
             "(not recorded in the surface metadata)", "abep_sim/intake_tpmc.py clausing_transmission signature",
             "numerical-setting", "CODE_DEFAULT"),
        item("F1-P-15", "relative flow speed", "V_orbital", "m s^-1",
             "atmosphere() returns no V_rel (co-rotation / winds), so V_rel = V_orb on every path", "docs/interfaces/"
             "UPSTREAM_ICD.md IF-A0 V_mps (partial)", "model-derived", "KNOWN_LIMITATION"),
        item("F1-P-16", "frontal-area design grid", list(spec.areas_m2), "m^2",
             "design-grid sample points (no evidence claim); upper end equals the largest A_f in the literature concept "
             "table (context only)", "feed_state_closure_v1.json published_comparables LIT-01 (Andreussi 2022 Table 1)",
             "assumed", "DESIGN_GRID"),
        item("F1-P-17", "channel-diameter design grid", list(spec.d_mm), "mm",
             "design-grid sample points; free-molecular outputs are d-invariant at fixed L/d (finding F1-02), d sets only "
             "depth and cell count", "this study", "assumed", "DESIGN_GRID"),
        item("F1-P-18", "L/d and phi design grid", {"L_over_d": list(spec.L_over_d), "phi": list(spec.phi)}, "-",
             "frozen-surface nodes (exact coverage at the build state; direct TPMC elsewhere)",
             "intake_surface_v1.json grid", "model-derived", "DESIGN_GRID"),
    ]


def summarize(res, spec):
    """Derived, data-backed findings (numbers come from the result; nothing is typed in)."""
    views = res["views"]
    cr = res["candidate_rows"]
    out = []
    b = res["species_recombination_bias"]
    out.append({"id": "F1-01", "evidence_class": "model-derived",
                "finding": f"abep_sim.intake.IntakeSurface recombines species rows by MASS fraction, but each species row's C_D is "
                           f"normalised by the mixture dynamic pressure of the build atmosphere (C_D_row = (m_s/m_mean) C_D_s) "
                           f"and CR_passive is a number-density ratio (mole weighting applies). At {b['node']} the IntakeSurface "
                           f"convention gives C_D x{b['C_D_ratio']:.4f} and CR_passive x{b['CR_ratio']:.4f} relative to the "
                           f"species-consistent recombination used here",
                "handling": "not fixed (module change outside this lane; goldens would move); this lane recombines from the "
                            "species rows directly; owner question F1Q-01"})
    out.append({"id": "F1-02", "evidence_class": "model-derived",
                "finding": "in the free-molecular TPMC every output (eta_c, C_D, K_back, CR_passive) is invariant to the channel "
                           "diameter d at fixed L/d (trajectories scale with R and L), and the geometric wall area 2 phi A L/d is "
                           "d-independent; d changes only intake depth L and cell count. CR_passive and K_back are also "
                           "independent of phi. Candidates differing only in d therefore tie in every objective (reported as "
                           "d-collapsed groups)", "handling": "pinned by tests (d-invariance, phi reconstruction)"})
    inv = all(v["pareto_set_invariant_under_p_ref_sweep"] for vw in views.values() for v in vw.values())
    out.append({"id": "F1-03", "evidence_class": "model-derived",
                "finding": f"compressor burden = p_ref / p_passive is a monotone transform of p_passive at every p_ref; the "
                           f"Pareto status of every candidate is identical across the p_ref sweep {list(spec.p_ref_Pa)} Pa in "
                           f"every view and scenario: {inv}", "handling": "p_ref stays TBD; no value was needed for the filter"})
    # drag constraint
    lines = []
    for vname in ("design_case", "envelope"):
        n_inf = {sid: v["counts"]["INFEASIBLE"] for sid, v in views[vname].items()}
        lines.append(f"{vname}: infeasible per scenario {n_inf}")
    out.append({"id": "F1-04", "evidence_class": "model-derived",
                "finding": "hard constraint C-DRAG-RFP (intake-face drag <= RFP thrust max) and MODEL_ERROR fail closed; "
                           + "; ".join(lines),
                "handling": "infeasible candidates are kept with reasons, never ranked"})
    # surface-state trade summary at the design case, L/d extremes, phi 0.9, area 1 (any d)
    ex = []
    for sid, rows in cr["design_case"].items():
        sel = {r["L_over_d"]: r for r in rows if r["area_m2"] == 1.0 and r["phi"] == max(spec.phi) and r["d_mm"] == spec.d_mm[0]}
        lo, hi = min(sel), max(sel)
        ex.append(f"{sid}: L/d {lo:g} eta_c {sel[lo]['eta_c_mix']:.3f} CR {sel[lo]['CR_passive_mix']:.0f} | L/d {hi:g} "
                  f"eta_c {sel[hi]['eta_c_mix']:.3f} CR {sel[hi]['CR_passive_mix']:.0f}")
    out.append({"id": "F1-05", "evidence_class": "model-derived",
                "finding": "collection vs passive compression trade at the design case (phi max, mixture): " + "; ".join(ex),
                "handling": "this is the trade the Pareto set exposes; alpha is a TBD scenario, not a choice"})
    chk = res["surface_reproduction_check"]
    out.append({"id": "F1-06", "evidence_class": "model-derived",
                "finding": f"direct TPMC at the surface build state reproduces the frozen surface nodes within 3 sigma: "
                           f"{chk['all_within_3sigma']} (z-scores in surface_reproduction_check)",
                "handling": "diagnostic of build-state / normalisation consistency only"})
    sr = res["speed_ratio_bracket"]
    out.append({"id": "F1-07", "evidence_class": "model-derived",
                "finding": f"over all {sr['n_grid_states']} frozen-atmosphere grid states in 180-230 km (all F10.7), the "
                           f"extremes of the species speed ratios, rho V and q occur at evaluated states: {sr['all_bracketed']}",
                "handling": "basis for the corner-state envelope; interior states are not evaluated"})
    oa = [r["off_axis_rel_eta_loss_per_deg"] for rows in cr["design_case"].values() for r in rows]
    out.append({"id": "F1-08", "evidence_class": "model-derived",
                "finding": f"relative collection loss per degree of pointing (secant 0-{spec.theta_hi_deg:g} deg, design case) "
                           f"spans {min(oa):.4f}-{max(oa):.4f} per deg across candidates and scenarios",
                "handling": "objective; the pointing budget itself is TBD (F1Q-03)"})
    dom = {vname: {sid: v["counts"]["DOMINATED"] + v["counts"]["NONDOMINATED_WITHIN_NOISE"] for sid, v in vw.items()}
           for vname, vw in views.items()}
    out.append({"id": "F1-10", "evidence_class": "model-derived",
                "finding": f"the non-dominated filter removes few feasible candidates (dominated or within-noise counts per "
                           f"scenario: {dom}): within a scenario A trades captured flow against drag and mass, and L/d trades "
                           f"eta_c and off-axis tolerance against passive compression; candidates are removed mainly where "
                           f"longer channels add mass without a compression or collection gain (near-specular scenarios)",
                "handling": "the Pareto sets are the deliverable; narrowing them needs the TBD inputs (alpha, p_ref, "
                            "structure, pointing) or downstream objectives (F2-F7), not a scalar weighting here"})
    m = [r["m_intake_code_default_case_kg"] for r in cr["design_case"][next(iter(cr["design_case"]))]]
    out.append({"id": "F1-09", "evidence_class": "assumed",
                "finding": f"m_intake is TBD for every candidate (wall thickness, coating and support fraction have no evidence). "
                           f"Under the labelled PARAMETRIC_SENSITIVITY_CASE SC-CODE-DEFAULT it spans {min(m):.2f}-{max(m):.2f} kg "
                           f"over the grid. Mass dominance uses (wall area, frontal area), which implies mass dominance for ANY "
                           f"positive structural parameters", "handling": "owner question F1Q-02"})
    return out


def build(progress=None):
    spec = F1.StudySpec()
    t0 = time.process_time()
    res = F1.run_study(spec, progress=progress)
    cpu = time.process_time() - t0
    views = res["views"]
    cand_tables = {}
    for vname, by_sc in res["candidate_rows"].items():
        cols = CAND_COLS + (ENV_EXTRA if vname == "envelope" else ())
        cand_tables[vname] = {sid: table(rows, cols) for sid, rows in by_sc.items()}
    reasons = {vname: {sid: {r["candidate"]: r["infeasible_reasons"] for r in rows if not r["feasible"]}
                       for sid, rows in by_sc.items()} for vname, by_sc in res["candidate_rows"].items()}

    doc = {
        "schema": F1.SCHEMA,
        "id": "F1_INTAKE_SYNTHESIS_v1",
        "lane": "fo_a9_7_f1_intake_synthesis",
        "directive": {"path": DIRECTIVE_REL, "json": DIRECTIVE_JSON_REL, "section": "F1 - Intake geometry synthesis"},
        "status": "INVESTIGATION_HYPOTHESIS",
        "deliverable_status": "DESIGN_SYNTHESIS_SCREENING_NOT_A_SELECTION",
        "base_commit": BASE_COMMIT,
        "generated_by": SCRIPT_REL,
        "module": "abep_sim/design/intake_synthesis.py",
        "test": "tests/test_design_f1_intake.py",
        "regenerate": f"python {SCRIPT_REL}  (verify: --check)",
        "what_this_is_not": [
            "not a selected intake, a winner, an optimum or a PASS",
            "not a flight design or a freeze candidate (that is F9; status stays INVESTIGATION_HYPOTHESIS)",
            "not a model change: no existing module or frozen dataset is modified; not wired into archengine; goldens unaffected",
            "not a Hall or thrust prediction (no admitted Hall response map; T and T - D are NOT_EVALUATED)",
            "no filter: intake_tpmc's placeholder filter fields are never used (the filter is F2's model)",
        ],
        "pins": [{"path": p, "sha256": sha256(p)} for p in PINNED],
        "referenced_not_pinned": [{"path": p, "use": u} for p, u in REFERENCED_NOT_PINNED],
        "references": F1.REFERENCES,
        "conventions": {
            "eta_c": "intake_tpmc definition: forward-transmitted flux into the plenum / free-stream flux on the aperture "
                     "A; eta_c = phi eta_open cos(theta); mixture eta_c mass-fraction weighted",
            "C_D": "intake-face drag coefficient referenced to the FULL ram aperture area A (open + solid) and q = 1/2 rho V^2 "
                   "of the free stream; per-species intrinsic C_D_s = C_D_row m_mean/m_s; mixture C_D = sum_s w_s C_D_s "
                   "(w_s mass fraction); drag D = q A C_D (intake face only; spacecraft body/arrays excluded)",
            "K_back": "intake_tpmc: Clausing transmission of one channel for wall-temperature thermal molecules entering "
                      "from the plenum side (fraction reaching the front)",
            "CR_passive": "number-density ratio n_plenum,s / n_inf,s = eta_c,s V / ((c_bar_s/4) phi K_back,s) at zero net "
                          "collection; mixture CR = sum_s x_s CR_s (x_s mole fraction)",
            "p_passive": "sum_s n_inf,s CR_s k T_wall (zero-net-flow plenum pressure; UPPER BOUND)",
            "compressor_burden": "lower bound p_ref / p_passive; objective carried per Pa of p_ref "
                                 "(compressor_burden_per_Pa = 1 / p_passive); values per p_ref via compressor_burden_sweep",
            "mdot_s_captured": "eta_c,s rho_s V A = forward transmission; net flow at plenum pressure p_s is "
                               "mdot_s (1 - p_s/p_passive,s) (UPPER BOUND when p_s -> 0; finding FC-01 of feed_state_closure)",
            "m_intake": "geometric: (A_wall t rho + (A_wall + A) t_c rho_c)(1 + f_support), A_wall = 2 phi A L/d (same "
                        "expression as intake_tpmc); TBD nominal, labelled parametric case reported",
            "uncertainty": "1-sigma TPMC statistical SE: Agresti-Coull binomial for eta_open and K_back; CR propagated in "
                           "quadrature; C_D from a replicate calibration (no closed form from intake_response aggregates); "
                           "species combined in quadrature (independent runs). Model-form uncertainty (kernel, alpha, "
                           "T_wall, single-channel TPMC) is NOT in the SE; it is carried as scenarios / limitations",
        },
        "coverage_rule": {
            "frozen_surface": "used only at an exact grid node (L/d, phi, alpha, theta, kernel, species) AND at its build state "
                              f"{F1.SURFACE_BUILD_STATE} (alt km, F10.7); never interpolated across the atmosphere, never "
                              "extrapolated",
            "direct_tpmc": "abep_sim.intake_tpmc.intake_response at phi = 1 (pure channel response; phi applied exactly, "
                           "pinned by a test), deterministic crc32 seeds, n per point = F1-P-12; converged iff unresolved "
                           "fraction <= 1e-3, else MODEL_ERROR (fail closed)",
            "orbit_states": [s.id for s in spec.states],
            "orbit_state_basis": "RFP band corners 180/230 km x F10.7 70/230 (extremes present in the frozen dataset) plus "
                                 "the surface build state 200 km / F10.7 150. Local-time states: NOT_IN_FROZEN_DATASET (the "
                                 "dataset is orbit-averaged over local solar time); live MSIS not used (rule 3)",
            "species": list(F1.SPECIES),
            "theta": "0 deg at every state; 5 deg (largest frozen node) at the design state for the off-axis objective",
        },
        "design_space": {"variables": {"area_m2": list(spec.areas_m2), "d_mm": list(spec.d_mm),
                                       "L_over_d": list(spec.L_over_d), "phi": list(spec.phi)},
                         "n_candidates": len(spec.candidates()),
                         "scenario_axes": {"alpha": list(spec.alphas), "scattering": list(spec.kernels)},
                         "scenario_rule": "alpha and the kernel are TBD evidence inputs: every scenario gets its own Pareto "
                                          "set; no scenario is chosen by the search"},
        "items": build_items(spec),
        "objectives": [{"key": k, "sense": s, "se_key": e} for k, s, e in F1.OBJECTIVES],
        "objective_notes": {
            "mass": "wall_area_m2 and frontal_area_m2 jointly stand for mass: dominance in both implies lower geometric mass "
                    "for every positive (t, rho, t_c, rho_c, f_support); m_intake itself is TBD",
            "off_axis": "relative eta_c loss per degree, secant 0 -> 5 deg at the design state (also used in the envelope view)",
            "surface_state": "|d eta_c / d alpha| / eta_c at the scenario alpha (central secant over neighbouring nodes)",
            "compressor_burden": "per Pa of p_ref; Pareto status verified identical across the p_ref sweep",
        },
        "pareto_method": {
            "filter": "non-dominated filter over feasible candidates per (view, scenario): a dominates b iff no worse in "
                      "every objective and strictly better in one; ties never dominate; O(N^2); no weights, no scalarisation",
            "statuses": ["NONDOMINATED", "NONDOMINATED_WITHIN_NOISE", "DOMINATED", "INFEASIBLE"],
            "noise_rule": "NONDOMINATED_WITHIN_NOISE: dominated on the means but no dominator is better by > 2 combined SE "
                          "in any objective",
            "views": {"design_case": f"state {F1.DESIGN_STATE.id}",
                      "envelope": "worst case of each objective over the evaluated orbit states (worst state recorded); "
                                  "feasibility requires every state"},
        },
        "hard_constraints": [
            {"id": "C-CONV", "rule": "TPMC unresolved fraction <= 1e-3 at every evaluated point", "on_fail": "MODEL_ERROR -> INFEASIBLE"},
            {"id": "C-DRAG-RFP", "rule": f"intake-face drag <= RFP thrust max {RFP.thrust_max_mN:g} mN (design state for the "
                                         f"design view; every state for the envelope view)",
             "basis": "F1-P-11; necessary, not sufficient (spacecraft drag beyond the intake face is not included)",
             "on_fail": "INFEASIBLE"},
            {"id": "C-NOT-APPLIED", "rule": "no thrust, flow-sufficiency or system-mass constraint is applied: thrust is "
                                            "NOT_EVALUATED (no admitted Hall map) and the intake mass allocation is not an "
                                            "evidence-backed requirement here", "on_fail": "n/a"},
        ],
        "uncertainty_calibration": res["calibration"],
        "surface_reproduction_check": res["surface_reproduction_check"],
        "species_recombination_bias": res["species_recombination_bias"],
        "speed_ratio_bracket_check": res["speed_ratio_bracket"],
        "pareto": views,
        "candidate_metrics": cand_tables,
        "infeasible_reasons": reasons,
        "compressor_burden_sweep": {"p_ref_Pa": list(spec.p_ref_Pa),
                                    "rule": "compressor_burden(p_ref) = p_ref x compressor_burden_per_Pa (candidate_metrics); "
                                            "lower bound, no floor at 1 (< 1 means p_passive alone exceeds p_ref at zero net "
                                            "flow)"},
        "envelope_per_state": "not duplicated: per-state candidate values follow from if_a1_interface.records_per_unit_area "
                              "(mdot, p_passive scale with A) and species_table (C_D_species, eta_c, CR, K_back per state); "
                              "the worst state of each envelope objective is in candidate_metrics.envelope",
        "species_table": table(res["species_rows"], SPECIES_COLS),
        "if_a1_interface": {"schema": F1.IF_A1_RECORD_SCHEMA,
                            "records_per_unit_area": res["if_a1_unit_area"],
                            "producer_function": "abep_sim.design.intake_synthesis.if_a1_record(evaluator, candidate, state, "
                                                 "scenario, theta)"},
        "findings": None,  # filled below
        "interface_demands": [
            {"id": "F1-ID-01", "direction": "F1 -> F2", "counterpart": "PENDING abep_sim/design/filter_stage.py",
             "content": "IF-A1 record per species (mdot_fwd, p_passive, T, x, K_back) at the intake exit plane; per unit area "
                        "in if_a1_interface.records_per_unit_area, absolute via if_a1_record()", "status": "PROVIDED"},
            {"id": "F1-ID-02", "direction": "F2 -> F1", "counterpart": "PENDING abep_sim/design/filter_stage.py",
             "content": "per-species forward and backflow transmission of the filter and its conductance: the filter changes "
                        "the plenum backflow (effective K_back) and so CR_passive / p_passive seen by the compressor; F1 "
                        "values are filter-less", "status": "DEMANDED"},
            {"id": "F1-ID-03", "direction": "F1 -> F3", "counterpart": "PENDING abep_sim/design/compressor_synthesis.py",
             "content": "inlet state candidates (through F2): per-species mdot, p_passive, T_wall, composition; burden "
                        "p_ref/p_passive per candidate", "status": "PROVIDED"},
            {"id": "F1-ID-04", "direction": "F3 -> F1", "counterpart": "PENDING abep_sim/design/compressor_synthesis.py",
             "content": "compressor inlet pressure / pumping speed actually achieved (fixes b = p_plenum/p_passive and the "
                        "net delivered flow (1 - b) mdot_fwd)", "status": "DEMANDED"},
            {"id": "F1-ID-05", "direction": "F4 -> F1", "counterpart": "fo_a9_7_f4_plenum_feed (wave B; path not assigned)",
             "content": "reference feed pressure p_ref and feed temperature (TBD; F1 uses a parametric sweep)",
             "status": "DEMANDED"},
            {"id": "F1-ID-06", "direction": "F5 -> F4 -> F1", "counterpart": "PENDING docs/hardware/h1_freeze_candidate/",
             "content": "H-1 inlet / plenum interface requirement (mdot_s, P, T, x_s) from which p_ref follows",
             "status": "DEMANDED"},
            {"id": "F1-ID-07", "direction": "F1 -> F7/F8", "counterpart": "fo_a9_7_f7_f8_coupled_optimizer (path not assigned)",
             "content": "x_intake = (A, d, L/d, phi) Pareto sets per scenario, intake-face drag and C_D (reference A), mass "
                        "proxies, uncertainty axes alpha / kernel / theta / atmosphere", "status": "PROVIDED"},
            {"id": "F1-ID-08", "direction": "F7 -> F1", "counterpart": "fo_a9_7_f7_f8_coupled_optimizer",
             "content": "spacecraft frontal area / body drag and AOCS pointing budget (drag closure beyond the intake face; "
                        "theta range)", "status": "DEMANDED"},
            {"id": "F1-ID-09", "direction": "F1 <-> F0", "counterpart": "PENDING docs/performance/",
             "content": "workload for profiling: the committed build runs direct TPMC (intake_response) at the counts in "
                        "direct_runs; F0 measurement decides whether a Rust TPMC kernel is admitted (A9.7 order 1-2)",
             "status": "PROVIDED / DEMANDED"},
            {"id": "F1-ID-10", "direction": "F1 -> F9", "counterpart": "fo_a9_7_f9_freeze_candidate",
             "content": "intake area and geometry rows (VALUE | TOLERANCE | EVIDENCE_CLASS | SOURCE | FREEZE_STATUS): none "
                        "freezable from this lane (alpha, structure, pointing, p_ref TBD)", "status": "PROVIDED"},
        ],
        "open_owner_questions": [
            {"id": "F1Q-01", "question": "IntakeSurface recombines species rows by mass fraction although its C_D rows are "
                                         "normalised by the mixture q and CR_passive needs mole weighting (finding F1-01). "
                                         "Authorise a controlled model change (goldens move, HISTORY entry), or keep the "
                                         "production convention and use the species-consistent recombination only in the "
                                         "design-synthesis layer?",
             "why_new": "new finding of this lane; not covered by DI-1.1..DI-1.12", "status": "TBD_OWNER"},
            {"id": "F1Q-02", "question": "Structural basis for the honeycomb (wall material and thickness, AO coating and its "
                                         "density, support fraction): supply a sourced design, or authorise a labelled "
                                         "assumption for budgeting only?",
             "why_new": "m_intake has been code defaults with no cited source everywhere; DI-1.x does not ask",
             "status": "TBD_OWNER"},
            {"id": "F1Q-03", "question": "Pointing (theta) budget of the intake axis vs the relative wind: is the frozen "
                                         "surface's 0-5 deg range adequate, or must larger angles be evaluated (direct TPMC)?",
             "why_new": "feed_state_closure carried theta 0/2/5 as PROPOSED sensitivities without an owner question",
             "status": "TBD_OWNER"},
            {"id": "F1Q-04", "question": "Authorise a frozen intake surface v2 at the envelope states (CLAUDE.md rule 1 "
                                         "rebuild) to replace the bounded direct TPMC used here off the build state?",
             "why_new": "feed_state_closure listed FC-07 only as a to-reach-B item; this lane needs it for precision",
             "status": "TBD_OWNER"},
        ],
        "m16_impact": [
            {"m16_row": 1, "key": "intake", "state_change": "none: design-synthesis screening, no measurement; provides the "
             "Pareto sets as input to the open DI-1.1 / DI-1.2 decisions (blocking item unchanged)"},
            {"m16_row": 2, "key": "filter", "state_change": "none: IF-A1 record defined for F2; blocking item ICD G-01 unchanged"},
        ],
        "limitations": [
            "single-channel TPMC (no edge / inter-channel effects), fixed T_wall, Maxwell or CLL with alpha_n = alpha_t",
            "orbit-averaged atmosphere only (no local time, no winds, V_rel = V_orb)",
            "off-axis objective evaluated at the design state only; theta > 5 deg not evaluated",
            "K_back unresolved fraction is not returned by intake_response (only the forward trace's)",
            "free-molecular validity inside the plenum is not checked here (p_passive is reported)",
            "C_D SE is a replicate-calibration estimate",
        ],
        "compliance": {
            "existing_modules_modified": False, "frozen_data_modified": False, "wired_into_archengine": False,
            "surface_extrapolated": False, "tbd_converted_to_assumed_for_optimum": False,
            "single_optimum_or_winner_declared": False, "pass_declared": False, "julia_used": False,
            "deterministic": True,
        },
        "direct_runs": res["direct_runs"],
    }
    doc["findings"] = summarize(res, spec)
    doc = F1.rnd(doc, 6)
    return doc, cpu


def fmt(v):
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def render_md(doc) -> str:
    L = []
    a = L.append
    a("# F1 intake geometry synthesis (A9.7)")
    a("")
    a(f"> Generated by `{SCRIPT_REL}` from `{JSON_NAME}`. Do not edit by hand; rerun the script (`--check` verifies).")
    a("")
    a(f"Status: **{doc['status']}**, {doc['deliverable_status']}. Lane `{doc['lane']}`; directive `{doc['directive']['path']}`.")
    a("")
    a("What this is not:")
    for x in doc["what_this_is_not"]:
        a(f"- {x}")
    a("")
    a("## Conventions")
    for k, v in doc["conventions"].items():
        a(f"- **{k}**: {v}")
    a("")
    a("## Coverage rule")
    for k, v in doc["coverage_rule"].items():
        a(f"- **{k}**: {v}")
    a("")
    a("## Parameters")
    a("| id | name | value | units | evidence class | status | source |")
    a("|---|---|---|---|---|---|---|")
    for it in doc["items"]:
        a(f"| {it['id']} | {it['name']} | {fmt(it['value'])} | {it['units']} | {it['evidence_class']} | {it['status']} | {it['source']} |")
    a("")
    a("## Design space and objectives")
    a(f"Variables: {doc['design_space']['variables']} ({doc['design_space']['n_candidates']} candidates). "
      f"Scenario axes: {doc['design_space']['scenario_axes']}. {doc['design_space']['scenario_rule']}.")
    a("")
    a("| objective | sense |")
    a("|---|---|")
    for o in doc["objectives"]:
        a(f"| {o['key']} | {o['sense']} |")
    for k, v in doc["objective_notes"].items():
        a(f"- {k}: {v}")
    a("")
    a("## Pareto method and hard constraints")
    a(doc["pareto_method"]["filter"] + ". " + doc["pareto_method"]["noise_rule"] + ".")
    for c in doc["hard_constraints"]:
        a(f"- **{c['id']}**: {c['rule']} -> {c['on_fail']}")
    a("")
    for vname in ("design_case", "envelope"):
        a(f"## Pareto sets: {vname} ({doc['pareto_method']['views'][vname]})")
        a("| scenario | non-dominated | within noise | dominated | infeasible | p_ref-invariant |")
        a("|---|---|---|---|---|---|")
        for sid, v in doc["pareto"][vname].items():
            c = v["counts"]
            a(f"| {sid} | {c['NONDOMINATED']} | {c['NONDOMINATED_WITHIN_NOISE']} | {c['DOMINATED']} | {c['INFEASIBLE']} | "
              f"{v['pareto_set_invariant_under_p_ref_sweep']} |")
        a("")
        a("Non-dominated groups (A m^2, L/d, phi; d values tie, F1-02), listed in grid order, not ranked:")
        a("")
        for sid, v in doc["pareto"][vname].items():
            g = ", ".join(f"({x['area_m2']:g}, {x['L_over_d']:g}, {x['phi']:g})" for x in v["nondominated_groups_d_collapsed"])
            a(f"- `{sid}`: {g if g else 'none'}")
        a("")
    a("## Diagnostics")
    chk = doc["surface_reproduction_check"]
    a(f"- Surface reproduction (direct TPMC vs frozen node, build state): all within 3 sigma = {chk['all_within_3sigma']}")
    cal = doc["uncertainty_calibration"]
    a(f"- C_D replicate calibration: rel SD {fmt(cal['rel_sd_max'])} at n = {cal['n_per_run']} ({cal['replicates']} seeds)")
    sr = doc["speed_ratio_bracket_check"]
    a(f"- Envelope bracket over {sr['n_grid_states']} frozen grid states: {sr['all_bracketed']}")
    a(f"- Direct TPMC runs in this build: {doc['direct_runs']}")
    sw = doc["compressor_burden_sweep"]
    a(f"- Compressor burden sweep p_ref = {sw['p_ref_Pa']} Pa: {sw['rule']}")
    a("")
    a("## Findings")
    for f in doc["findings"]:
        a(f"- **{f['id']}** ({f['evidence_class']}): {f['finding']}. Handling: {f['handling']}.")
    a("")
    a("## IF-A1 record for F2 (filter stage)")
    s = doc["if_a1_interface"]["schema"]
    a(f"Record `{s['record']}`; {s['interface']}. Plane: {s['plane']}.")
    for k, v in s["fields_per_species"].items():
        a(f"- `{k}`: {v}")
    a(f"- Not included: {s['not_included']}")
    a(f"- Records per unit area: {len(doc['if_a1_interface']['records_per_unit_area'])} in the JSON; producer "
      f"`{doc['if_a1_interface']['producer_function']}`.")
    a("")
    a("## Interface demands")
    a("| id | direction | counterpart | status | content |")
    a("|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        a(f"| {d['id']} | {d['direction']} | {d['counterpart']} | {d['status']} | {d['content']} |")
    a("")
    a("## Open owner questions (new)")
    for q in doc["open_owner_questions"]:
        a(f"- **{q['id']}** ({q['status']}): {q['question']} _Why new:_ {q['why_new']}.")
    a("")
    a("## M16 impact")
    for m in doc["m16_impact"]:
        a(f"- Row {m['m16_row']} ({m['key']}): {m['state_change']}")
    a("")
    a("## Limitations")
    for x in doc["limitations"]:
        a(f"- {x}")
    a("")
    a("## Pins")
    for p in doc["pins"]:
        a(f"- `{p['path']}` sha256 `{p['sha256']}`")
    a("")
    a("## Regenerate")
    a("```")
    a(f"python {SCRIPT_REL}")
    a(f"python {SCRIPT_REL} --check   # exit 1 unless the committed files are reproduced")
    a("```")
    a("")
    return "\n".join(L)


def _scalar(v) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def _pp(v, ind: int) -> str:
    """Deterministic pretty printer: dicts indented one space per level; lists of scalars and small flat dicts inline
    (keeps the large tables readable and the file small)."""
    pad, pad1 = " " * ind, " " * (ind + 1)
    if isinstance(v, dict):
        if not v:
            return "{}"
        if all(_scalar(x) for x in v.values()) and len(v) <= 8:
            return json.dumps(v, ensure_ascii=False)
        items = [f"{pad1}{json.dumps(k, ensure_ascii=False)}: {_pp(x, ind + 1)}" for k, x in v.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(v, list):
        if not v:
            return "[]"
        if all(_scalar(x) for x in v):
            return json.dumps(v, ensure_ascii=False)
        items = [f"{pad1}{_pp(x, ind + 1)}" for x in v]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    return json.dumps(v, ensure_ascii=False)


def dump(doc) -> str:
    text = _pp(doc, 0) + "\n"
    assert json.loads(text) == doc
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A9.7 F1 intake geometry synthesis study builder")
    ap.add_argument("--check", action="store_true", help="verify the committed outputs are reproduced")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    prog = None if args.quiet else (lambda m: print(m, file=sys.stderr, flush=True))
    doc, cpu = build(progress=prog)
    js, md = dump(doc), render_md(doc)
    out = REPO / OUT_DIR_REL
    print(f"cpu {cpu:.1f} s, direct runs {doc['direct_runs']}", file=sys.stderr)
    if args.check:
        ok = True
        for name, text in ((JSON_NAME, js), (MD_NAME, md)):
            p = out / name
            if not p.exists() or p.read_text() != text:
                print(f"MISMATCH {OUT_DIR_REL}/{name}", file=sys.stderr)
                ok = False
        print("OK" if ok else "FAIL")
        return 0 if ok else 1
    out.mkdir(parents=True, exist_ok=True)
    (out / JSON_NAME).write_text(js)
    (out / MD_NAME).write_text(md)
    print(f"wrote {OUT_DIR_REL}/{JSON_NAME}, {MD_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
