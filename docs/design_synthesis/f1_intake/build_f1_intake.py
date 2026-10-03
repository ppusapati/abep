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
  python docs/design_synthesis/f1_intake/build_f1_intake.py --check-core  # fast (no TPMC): core view, MD, archive
  python docs/design_synthesis/f1_intake/build_f1_intake.py --write-core  # core view from the local full JSON

A9.22 item 9: the full JSON (36.7 MB) is an evidence archive (docs/evidence_archives/f1_intake/, built and verified by
scripts/evidence/f1_archive.py) and is git-ignored; Git keeps the compact consumer view f1_intake_synthesis_v1_core.json
(abep_sim/design/intake_synthesis.py core_from_full / load_f1_view), the Markdown and the archive manifest. A rebuild
that changes the full output needs a new archive (new run id) before the changed core view is committed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from abep_sim.design import intake_synthesis as F1  # noqa: E402
from abep_sim.design import owner_state as ost  # noqa: E402
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
    F1.DESIGN_STATE_SET_REL,
    F1.DESIGN_STATE_MANIFEST_REL,
    DIRECTIVE_REL,
)
# A9.14 S9.8 OD3 / A9.13 S6.14: the orbit-state set changed from five hand-picked orbit-averaged states to the frozen
# design-state set v2. The builder keeps no output history, so the superseded run is recorded here (facts of the
# committed output at 61eefc4, read from that file; never recomputed).
STATE_SET_HISTORY = {
    "superseded_state_set": F1.HISTORY_FIVE_STATE_SET,
    "superseded_output": {"path": "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json", "commit": "61eefc4",
                          "sha256": "85c79045047a6b09a10c8f199782b25defad2b5446386fa68496a16cf41c2ff2",
                          "direct_runs": 503,
                          "feasible_of_144_per_scenario": {
                              "design_case": {"maxwell_a0": 120, "maxwell_a0.2": 120, "maxwell_a0.5": 120,
                                              "maxwell_a0.8": 120, "maxwell_a1": 120, "cll_a0": 120, "cll_a0.2": 120,
                                              "cll_a0.5": 120, "cll_a0.8": 120, "cll_a1": 120},
                              "envelope": {"maxwell_a0": 48, "maxwell_a0.2": 48, "maxwell_a0.5": 48, "maxwell_a0.8": 48,
                                           "maxwell_a1": 48, "cll_a0": 48, "cll_a0.2": 48, "cll_a0.5": 48,
                                           "cll_a0.8": 48, "cll_a1": 48}}},
    "reason": "A9.14 S9.8 OD3 (design states come from the versioned orbit-resolved dataset; no hand-picked F10.7 / "
              "density points) and A9.13 S6.14 OQ-F4-05 (application-matrix residual RVF-03)",
}
REFERENCED_NOT_PINNED = (
    ("abep_sim/intake_tpmc.py", "called (intake_response, clausing_transmission, IntakeGeometry defaults); not modified"),
    ("abep_sim/intake.py", "IntakeSurface recombination convention examined (finding F1-01, since fixed in "
                          "abep_sim/intake_tpmc.py by A9.9 S2.1); not modified, not called"),
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
        item("F1-P-12", "direct TPMC particles per point", spec.n_direct, "-", "bounded per point (unchanged since A9.7); "
             "statistical SE reported per point; with the full design-state set the direct runs are spread over a "
             "seeded process pool (results independent of the worker count)", "this study", "numerical-setting",
             "STUDY_SETTING"),
        item("F1-P-13", "frozen-surface particles per point", int(sm["n_per_point"]), "-", "surface metadata",
             "abep_sim/data/intake_surface_v1.json n_per_point", "numerical-setting", "FROZEN"),
        item("F1-P-14", "K_back (Clausing) particles per evaluation", F1.K_BACK_N, "-",
             "intake_response calls clausing_transmission with its default n; assumed unchanged since the surface build "
             "(not recorded in the surface metadata)", "abep_sim/intake_tpmc.py clausing_transmission signature",
             "numerical-setting", "CODE_DEFAULT"),
        item("F1-P-15", "relative flow speed", "V_orbital", "m s^-1", F1.V_REL_BASIS,
             "abep_sim/atmosphere.py orbital_velocity; docs/interfaces/UPSTREAM_ICD.md IF-A0 V_mps (partial)",
             "model-derived", "KNOWN_LIMITATION (inclination / LTAN TBD, A9.21)"),
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
        item("F1-P-19", "orbit / atmosphere state set", F1.DESIGN_STATE_SET_ID, "-",
             f"every required state of the frozen design-state set v2 ({len(F1.required_states())} states; nominal "
             "median-density states and physical extrema of density, composition, temperature, local time and solar "
             "activity per ECSS scenario x altitude node) plus the design-case reference point "
             f"{F1.DESIGN_STATE.id}; orbit basis {F1.ORBIT_BASIS_LABEL}",
             f"{F1.DESIGN_STATE_SET_REL} sha256 {F1.DESIGN_STATE_SET_SHA256}", "model-derived",
             "FROZEN_DATASET (A9.14 S9.8 OD3; broad envelope, not a mission orbit)"),
    ]


def summarize(res, spec):
    """Derived, data-backed findings (numbers come from the result; nothing is typed in)."""
    views = res["views"]
    cr = res["candidate_rows"]
    out = []
    b = res["species_recombination_bias"]
    out.append({"id": "F1-01", "evidence_class": "model-derived",
                "finding": f"HISTORICAL (pre-fix production code, before owner decision A9.9 S2.1): "
                           f"abep_sim.intake.IntakeSurface recombined species rows by MASS fraction, although each species "
                           f"row's C_D is normalised by the mixture dynamic pressure of the build atmosphere (C_D_row = "
                           f"(m_s/m_mean) C_D_s) and CR_passive is a number-density ratio (mole weighting applies). At "
                           f"{b['node']} that pre-fix convention gives C_D x{b['C_D_ratio']:.4f} and CR_passive "
                           f"x{b['CR_ratio']:.4f} relative to the species-consistent recombination (this lane's value; "
                           f"the ratios quantify the superseded convention, re-evaluated from the species rows)",
                "handling": f"FIXED in production: abep_sim/intake_tpmc.py IntakeSurface now recombines the species rows by "
                            f"their physical definitions (F1Q-01 {ost.status_label('F1Q-01')}); this lane recombines "
                            f"from the species rows directly, consistent with the fixed production code"})
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
    ext = "; ".join(f"{k} {v['min']:.4g}..{v['max']:.4g} (max at {v['argmax_labels'][0] if v['argmax_labels'] else v['argmax']})"
                    for k, v in sr["quantities"].items())
    out.append({"id": "F1-07", "evidence_class": "model-derived",
                "finding": f"over the {sr['n_states']} required states of {sr['state_set']} (every scenario x altitude "
                           f"node with its density / composition / temperature / local-time extrema) the free-stream "
                           f"ranges are: {ext}",
                "handling": "every required state is evaluated (no corner bracketing, no subset); orbit basis "
                            f"{F1.ORBIT_BASIS_LABEL}"})
    oa = [r["off_axis_rel_eta_loss_per_deg"] for rows in cr["design_case"].values() for r in rows]
    out.append({"id": "F1-08", "evidence_class": "model-derived",
                "finding": f"relative collection loss per degree of pointing (secant 0-{spec.theta_hi_deg:g} deg, design case) "
                           f"spans {min(oa):.4f}-{max(oa):.4f} per deg across candidates and scenarios",
                "handling": "objective; the pointing budget is an AOCS-envelope requirement (F1Q-03 "
                            f"{ost.status_label('F1Q-03')}); its value is not yet supplied"})
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
                           f"positive structural parameters", "handling": f"F1Q-02 {ost.status_label('F1Q-02')}: "
                                                       f"{F1.F1Q02_LABEL}, {F1.F1Q02_USE} (never "
                                                       f"{', '.join(F1.F1Q02_FORBIDDEN_USES)}); {F1.F1Q02_LOCK1}",
                "f1q02": F1.f1q02_label()})
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
            "orbit_state_basis": f"index 0: design-case reference point {F1.DESIGN_STATE.id} (surface build state, "
                                 "orbit-averaged atmosphere_msis21_v1); then every required state of the frozen "
                                 f"design-state set v2 {F1.DESIGN_STATE_SET_ID} (sha256 {F1.DESIGN_STATE_SET_SHA256}): "
                                 "nominal states and physical extrema of density / composition / temperature / local "
                                 "time / solar activity of the frozen orbit-resolved dataset (A9.14 S9.8 OD3). No subset; "
                                 "live MSIS not used (rule 3)",
            "orbit_basis_label": F1.ORBIT_BASIS_LABEL,
            "design_state_coverage": F1.SURFACE_COVERAGE_AT_DESIGN_STATES,
            "design_state_set": F1.design_state_set_record(),
            "design_states": table([s.record() for s in spec.states if s is not F1.DESIGN_STATE],
                                   ("state_id", "scenario", "alt_km", "lat_deg", "lst_h", "lon_deg", "doy", "f107",
                                    "ap", "labels", "evaluation", "interp_max_rel_err_rho",
                                    "nominal_mission_scenario")),
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
            {"id": "F1-ID-01", "direction": "F1 -> F2", "counterpart": "abep_sim/design/filter_stage.py (F2-IF-01); "
             "coupled in abep_sim/design/plenum_feed.py (F4-ID-01, F4-ID-03)",
             "content": "IF-A1 record per species (mdot_fwd, p_passive, T, x, K_back) at the intake exit plane; per unit area "
                        "in if_a1_interface.records_per_unit_area, absolute via if_a1_record()", "status": "PROVIDED"},
            {"id": "F1-ID-02", "direction": "F2 -> F1", "counterpart": "abep_sim/design/filter_stage.py (F2-IF-02)",
             "content": "per-species forward and backflow transmission of the filter and its conductance: the filter changes "
                        "the plenum backflow (effective K_back) and so CR_passive / p_passive seen by the compressor; F1 "
                        "values are filter-less", "status": "DEMANDED"},
            {"id": "F1-ID-03", "direction": "F1 -> F3", "counterpart": "abep_sim/design/compressor_synthesis.py (IFD-F3-01: "
             "the F3 study fronts use the down-selection envelope inlets, not these records); coupled F1 -> F3 in "
             "abep_sim/design/plenum_feed.py (F4-ID-01, F4-ID-05)",
             "content": "inlet state candidates (through F2): per-species mdot, p_passive, T_wall, composition; burden "
                        "p_ref/p_passive per candidate", "status": "PROVIDED"},
            {"id": "F1-ID-04", "direction": "F3 -> F1", "counterpart": "abep_sim/design/compressor_synthesis.py (IFD-F3-03); "
             "abep_sim/design/plenum_feed.py (F4-ID-02)",
             "content": "compressor inlet pressure / pumping speed actually achieved (fixes b = p_plenum/p_passive and the "
                        "net delivered flow (1 - b) mdot_fwd)", "status": "DEMANDED"},
            {"id": "F1-ID-05", "direction": "F4 -> F1", "counterpart": "abep_sim/design/plenum_feed.py (F4-ID-02)",
             "content": "reference feed pressure p_ref and feed temperature (TBD; F1 uses a parametric sweep)",
             "status": "DEMANDED"},
            {"id": "F1-ID-06", "direction": "F5 -> F4 -> F1", "counterpart": "docs/hardware/h1_freeze_candidate/"
             "h1_freeze_candidate_v1.json (IFD-F4-01..05, H1F-IN-04: TBD)",
             "content": "H-1 inlet / plenum interface requirement (mdot_s, P, T, x_s) from which p_ref follows",
             "status": "DEMANDED"},
            {"id": "F1-ID-07", "direction": "F1 -> F7/F8", "counterpart": "abep_sim/design/architecture_optimizer.py (F78-ID-01)",
             "content": "x_intake = (A, d, L/d, phi) Pareto sets per scenario, intake-face drag and C_D (reference A), mass "
                        "proxies, uncertainty axes alpha / kernel / theta / atmosphere", "status": "PROVIDED"},
            {"id": "F1-ID-08", "direction": "F7 -> F1", "counterpart": "abep_sim/design/architecture_optimizer.py (F78-ID-02)",
             "content": "spacecraft frontal area / body drag and AOCS pointing budget (drag closure beyond the intake face; "
                        "theta range)", "status": "DEMANDED"},
            {"id": "F1-ID-09", "direction": "F1 <-> F0", "counterpart": "docs/performance/PERFORMANCE_BASELINE_98fbbb9.json; "
             "docs/performance/abep_core/parity_report_v1.json (RUST-ID-03: F1 does not opt in to the Rust backend)",
             "content": "workload for profiling: the committed build runs direct TPMC (intake_response) at the counts in "
                        "direct_runs; F0 measurement decides whether a Rust TPMC kernel is admitted (A9.7 order 1-2)",
             "status": "PROVIDED / DEMANDED"},
            {"id": "F1-ID-10", "direction": "F1 -> F9", "counterpart": "docs/architecture/freeze_candidate/"
             "architecture_freeze_candidate_v1.json (F9-ID-01)",
             "content": "intake area and geometry rows (VALUE | TOLERANCE | EVIDENCE_CLASS | SOURCE | FREEZE_STATUS): none "
                        "freezable from this lane (alpha, structure, pointing, p_ref TBD)", "status": "PROVIDED"},
        ],
        "open_owner_questions": ost.apply_to_questions([
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
        ]),
        "m16_impact": [
            {"m16_row": 1, "key": "intake", "state_change": "none: design-synthesis screening, no measurement; provides the "
             "Pareto sets as input to the open DI-1.1 / DI-1.2 decisions (blocking item unchanged)"},
            {"m16_row": 2, "key": "filter", "state_change": "none: IF-A1 record defined for F2; blocking item ICD G-01 unchanged"},
        ],
        "limitations": [
            "single-channel TPMC (no edge / inter-channel effects), fixed T_wall, Maxwell or CLL with alpha_n = alpha_t",
            "V_rel = V_orb (inertial circular): Earth co-rotation and thermospheric winds not included (inclination / "
            "LTAN TBD, A9.21; the design-state set carries no relative velocity)",
            "the design-state set is a broad envelope (every inclination and LTAN), not a mission orbit: statewise "
            "results are design-envelope results, never mission-ICD results (" + F1.ORBIT_BASIS_LABEL + ")",
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
        "orbit_basis_label": F1.ORBIT_BASIS_LABEL,
        "state_set_history": STATE_SET_HISTORY,
        "intake_structural_mass_label": F1.f1q02_label(),
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
        if k == "orbit_states":
            a(f"- **{k}**: {len(v)} states (index 0 `{v[0]}` = design-case reference point; the rest = the required "
              f"design states, ids in the JSON)")
        elif k == "design_states":
            a(f"- **{k}**: {len(v['rows'])} required-state records (scenario, altitude, latitude, local time, longitude, "
              f"day of year, labels) in the JSON")
        elif k == "design_state_set":
            a(f"- **{k}**: `{v['design_state_set_id']}` (`{v['path']}`, sha256 `{v['sha256']}`), "
              f"{v['n_required_states']} required states ({v['n_nominal_mission_scenario_states']} in the nominal "
              f"mission scenario {v['nominal_scenario']}); scenarios {v['scenarios']}; altitudes {v['altitudes_km']} km; "
              f"labels {v['label_counts']}; orbit basis **{v['orbit_basis_label']}**: {v['orbit_basis_note']} "
              f"Speed: {v['v_rel_basis']}. Composition: {v['composition_basis']}. Subset used: {v['subset_used']} "
              f"({v['subset_note']}).")
        else:
            a(f"- **{k}**: {v}")
    a("")
    h = doc["state_set_history"]
    a("## State-set change (history)")
    a(f"- Superseded: {h['superseded_state_set']['state_ids']} ({h['superseded_state_set']['basis']}; "
      f"{h['superseded_state_set']['status']}). Reason: {h['reason']}.")
    so = h["superseded_output"]
    a(f"- Superseded output `{so['path']}` at {so['commit']} (sha256 `{so['sha256']}`, {so['direct_runs']} direct runs); "
      f"feasible candidates of 144 per scenario: design case {so['feasible_of_144_per_scenario']['design_case']}, "
      f"envelope {so['feasible_of_144_per_scenario']['envelope']}.")
    lab = doc["intake_structural_mass_label"]
    a(f"- Intake structural mass label ({lab['authority']}): {lab['label']}, {lab['use']}; never {', '.join(lab['not'])}; "
      f"{lab['lock1_condition']}.")
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
    for k, v in sr["quantities"].items():
        a(f"- {k} over the {sr['n_states']} required design states: {fmt(v['min'])} ({', '.join(v['argmin_labels'])}) "
          f"to {fmt(v['max'])} ({', '.join(v['argmax_labels'])})")
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
    a("## Owner questions raised by this lane")
    a(f"Status from `{ost.OQ5_REL}` (as raised: TBD_OWNER).")
    a("")
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


def check_core() -> int:
    """Fast check (no TPMC; A9.22 item 9): the committed core view is the core view of the full output (when the full
    JSON is present locally), the Markdown renders from the expanded core view, and the evidence-archive manifest agrees
    with the core view, the full output and the archive (whichever are present locally)."""
    out = REPO / OUT_DIR_REL
    ok = True
    core_txt = (REPO / F1.F1_CORE_REL).read_text()
    full_p = out / JSON_NAME
    if full_p.is_file():
        if F1.core_text_from_full_bytes(full_p.read_bytes()) != core_txt:
            print(f"MISMATCH {F1.F1_CORE_REL} (not the core view of {OUT_DIR_REL}/{JSON_NAME})", file=sys.stderr)
            ok = False
    else:
        print(f"NOTE {OUT_DIR_REL}/{JSON_NAME} not present locally (archived): core view checked against the "
              "archive manifest only", file=sys.stderr)
    if (out / MD_NAME).read_text() != render_md(F1.expand_core(json.loads(core_txt))):
        print(f"MISMATCH {OUT_DIR_REL}/{MD_NAME} (does not render from the core view)", file=sys.stderr)
        ok = False
    spec = importlib.util.spec_from_file_location("_f1_archive", REPO / "scripts/evidence/f1_archive.py")
    arch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(arch)
    ok = (arch.verify() == 0) and ok
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


def write_core() -> int:
    """Derive the committed core view from the local full output (no TPMC)."""
    full_p = REPO / OUT_DIR_REL / JSON_NAME
    if not full_p.is_file():
        print(f"REFUSED: {OUT_DIR_REL}/{JSON_NAME} is not present (fetch the evidence archive first)", file=sys.stderr)
        return 1
    (REPO / F1.F1_CORE_REL).write_text(F1.core_text_from_full_bytes(full_p.read_bytes()))
    print(f"wrote {F1.F1_CORE_REL}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A9.7 F1 intake geometry synthesis study builder")
    ap.add_argument("--check", action="store_true", help="full rebuild (slow); verify the committed core view and "
                    "Markdown are reproduced (and the full JSON, when present locally)")
    ap.add_argument("--check-core", action="store_true", help="fast, no TPMC: core view vs local full output, Markdown "
                    "vs core view, evidence-archive manifest")
    ap.add_argument("--write-core", action="store_true", help="derive the core view from the local full output")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    if args.check_core:
        return check_core()
    if args.write_core:
        return write_core()
    prog = None if args.quiet else (lambda m: print(m, file=sys.stderr, flush=True))
    doc, cpu = build(progress=prog)
    js, md = dump(doc), render_md(doc)
    core = F1.core_text_from_full_bytes(js.encode())
    out = REPO / OUT_DIR_REL
    print(f"cpu {cpu:.1f} s, direct runs {doc['direct_runs']}", file=sys.stderr)
    if args.check:
        ok = True
        targets = [(MD_NAME, md), (Path(F1.F1_CORE_REL).name, core)]
        if (out / JSON_NAME).is_file():
            targets.append((JSON_NAME, js))
        else:
            print(f"NOTE {OUT_DIR_REL}/{JSON_NAME} not present locally (archived): compared through the core view, "
                  "whose full_output.sha256 pins the full output", file=sys.stderr)
        for name, text in targets:
            p = out / name
            if not p.exists() or p.read_text() != text:
                print(f"MISMATCH {OUT_DIR_REL}/{name}", file=sys.stderr)
                ok = False
        print("OK" if ok else "FAIL")
        return 0 if ok else 1
    out.mkdir(parents=True, exist_ok=True)
    # The full output is written to the working tree for local use and archiving only: it is git-ignored and is never
    # committed as an ordinary Git blob (A9.22 item 9). A changed full output needs a new evidence archive
    # (scripts/evidence/f1_archive.py build, new run id) before the core view that pins it is committed.
    (out / JSON_NAME).write_text(js)
    (out / MD_NAME).write_text(md)
    (REPO / F1.F1_CORE_REL).write_text(core)
    print(f"wrote {OUT_DIR_REL}/{JSON_NAME} (archive only, not committed), {MD_NAME}, {Path(F1.F1_CORE_REL).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
